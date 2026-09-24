#!/usr/bin/env python3
"""Neemt de route van een rit over uit de locatie-tracker.

De tracker kijkt naar dezelfde GPS-punten, maar legt ze met map-matching op de weg.
Dat is een stuk beter dan wat route.py doet: die dunt uit tot 24 punten en laat een
routeplanner de rest raden, en dan kiest hij soms een andere straat.

De tracker ziet ook lopen en fietsen. Alleen stukken met wijze 'rijden' tellen mee,
en alleen als ze in de tijd overlappen met de dashcamrit.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

VANAF = '2026-08-21'      # daarvoor heeft de logger geen posities
OVERLAP_MIN = 3           # zoveel minuten samenval is genoeg om het dezelfde rit te noemen
ONDERGRENS = 0.6          # map-match korter dan dit deel van de rauwe lijn = mislukt
BOVENGRENS = 2.0


def _basis(cfg=None):
    cfg = cfg or store.load_config()
    return (cfg.get('tracker') or {}).get('url', '').rstrip('/')


def dag_ritten(basis, dag, cache):
    """Alle autostukken van één dag uit de tracker, gemeten en al op de weg gelegd."""
    if dag in cache:
        return cache[dag]
    try:
        r = httpx.get(f'{basis}/api/dag/{dag}', timeout=120)
        r.raise_for_status()
        delen = r.json().get('delen', [])
    except Exception as exc:
        print(f'  {dag}: tracker antwoordt niet ({exc.__class__.__name__})', flush=True)
        cache[dag] = []
        return []
    uit = []
    for d in delen:
        if d.get('soort') != 'onderweg' or d.get('wijze') != 'rijden':
            continue
        vorm = d.get('spoor') or []
        km = d.get('km_weg')
        rauw_km = d.get('km') or 0
        # Een map-match die veel korter of langer uitkomt dan de rauwe lijn is
        # mislukt. Gemeten 04-09: 28,5 km rauw werd 0,09 km op de weg.
        if not (km and rauw_km and ONDERGRENS * rauw_km <= km <= BOVENGRENS * rauw_km):
            vorm = d.get('spoor_ruw') or vorm
            km = rauw_km
        if len(vorm) >= 2:
            uit.append({'van': d['van'], 'tot': d['tot'], 'spoor': vorm, 'km': km})
    cache[dag] = uit
    return uit


def stukken_voor(trip, delen):
    a1 = datetime.fromisoformat(trip['start_ts'])
    a2 = datetime.fromisoformat(trip['end_ts'])
    if a1.tzinfo is None:
        a1, a2 = a1.astimezone(), a2.astimezone()
    raak = []
    for d in delen:
        b1, b2 = datetime.fromisoformat(d['van']), datetime.fromisoformat(d['tot'])
        if (min(a2, b2) - max(a1, b1)).total_seconds() / 60 >= OVERLAP_MIN:
            raak.append(d)
    return sorted(raak, key=lambda d: d['van'])


def zet(con, trip, delen):
    raak = stukken_voor(trip, delen)
    if not raak:
        return None
    coords, km = [], 0.0
    for d in raak:
        coords += [[lon, lat] for lat, lon in d['spoor']]
        km += d['km'] or 0
    geo = {'type': 'LineString', 'coordinates': coords}
    con.execute('INSERT OR REPLACE INTO routes '
                '(trip_id, soort, geojson, km, punten, bijgewerkt) VALUES (?,?,?,?,?,?)',
                (trip['id'], 'gemeten', json.dumps(geo), round(km, 1), len(coords),
                 datetime.now().astimezone().isoformat(timespec='seconds')))
    con.commit()
    return {'stukken': len(raak), 'punten': len(coords), 'km': round(km, 1)}


def run(vanaf=VANAF, alleen_nieuwe=False):
    basis = _basis()
    if not basis:
        print('geen tracker.url in config.json')
        return {}
    con = store.connect()
    sql = 'SELECT id, day, start_ts, end_ts FROM trips WHERE day >= ?'
    if alleen_nieuwe:
        sql += " AND id NOT IN (SELECT trip_id FROM routes WHERE soort = 'gemeten')"
    ritten = con.execute(sql + ' ORDER BY start_ts', (vanaf,)).fetchall()
    print(f'{len(ritten)} ritten vanaf {vanaf}\n', flush=True)
    cache, uit = {}, {'gezet': 0, 'geen stuk': 0}
    for t in ritten:
        r = zet(con, t, dag_ritten(basis, t['day'], cache))
        tijd = f"#{t['id']} {t['day']} {t['start_ts'][11:16]}-{t['end_ts'][11:16]}"
        if r:
            uit['gezet'] += 1
            print(f"  {tijd}  {r['stukken']} stuk(ken) → {r['punten']} punten · {r['km']} km", flush=True)
        else:
            uit['geen stuk'] += 1
            print(f'  {tijd}  geen autostuk in de tracker', flush=True)
    con.close()
    print(f'\n{uit}')
    return uit


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    run(args[0] if args else VANAF, alleen_nieuwe='--nieuw' in sys.argv)
