#!/usr/bin/env python3
"""Vult een lege viewer met de meegeleverde demodag.

De beelden in demo/footage zijn geblurd. Daardoor is de snelheid er niet meer uit te
lezen, dus de ritten, de kilometers en de route staan hier kant-en-klaar in. De route
is VERZONNEN: hij hoort niet bij de plek waar de beelden gemaakt zijn.

    ./.venv/bin/python load_demo.py
"""
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fragment
import remmen
import store
import thumbs

FOOTAGE = HERE / 'demo' / 'footage'

# Verzonnen ritten in Utrecht. Bewust een andere plek dan waar de beelden vandaan
# komen, en twee verschillende wegen - niet dezelfde lijn heen en terug.
RIT1 = [(52.0907, 5.1214), (52.0929, 5.1272), (52.0956, 5.1325), (52.0987, 5.1361),
        (52.1020, 5.1381), (52.1053, 5.1408), (52.1081, 5.1447)]
RIT2 = [(52.1081, 5.1447), (52.1074, 5.1379), (52.1046, 5.1318), (52.1008, 5.1281),
        (52.0971, 5.1249), (52.0938, 5.1225), (52.0907, 5.1214)]
DOEL_KM = [3.7, 3.6]


def km_tussen(a, b):
    R = 6371.0
    dlat, dlon = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    x = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(x))


def lengte(punten):
    return sum(km_tussen(punten[i], punten[i + 1]) for i in range(len(punten) - 1))


def schaal_naar(punten, doel_km):
    """Rekt of krimpt de route rond zijn beginpunt tot hij de gewenste lengte heeft."""
    nu = lengte(punten)
    if nu == 0:
        return punten
    f = doel_km / nu
    lat0, lon0 = punten[0]
    return [(lat0 + (lat - lat0) * f, lon0 + (lon - lon0) * f) for lat, lon in punten]


def verdicht(punten, stappen=8):
    """Tussenpunten erbij, zodat de lijn op de kaart vloeiend loopt."""
    uit = []
    for i in range(len(punten) - 1):
        a, b = punten[i], punten[i + 1]
        for s in range(stappen):
            f = s / stappen
            uit.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    uit.append(punten[-1])
    return uit


def main():
    if not FOOTAGE.exists():
        raise SystemExit(f'{FOOTAGE} ontbreekt - is de demo meegeleverd?')
    bestanden = sorted(FOOTAGE.glob('*.mp4'))
    if not bestanden:
        raise SystemExit(f'geen mp4-bestanden in {FOOTAGE}')

    con = store.connect()
    dagen = set()
    toegevoegd = 0
    for pad in bestanden:
        gelezen = store.parse_name(pad.name)
        if gelezen is None:
            print(f'  overgeslagen (naam): {pad.name}')
            continue
        dt, view = gelezen
        cid = store.clip_id(str(pad))
        con.execute(
            'INSERT INTO clips (id, path, ts, day, kind, view, bytes) VALUES (?,?,?,?,?,?,?) '
            'ON CONFLICT(id) DO UPDATE SET bytes = excluded.bytes',
            (cid, str(pad), dt.isoformat(timespec='seconds'), dt.strftime('%Y-%m-%d'),
             'normaal', view, pad.stat().st_size))
        dagen.add(dt.strftime('%Y-%m-%d'))
        toegevoegd += 1
    con.commit()
    dag = sorted(dagen)[0]
    print(f'{toegevoegd} clips ingelezen voor {dag}')

    # Ritten uit de clips zelf afleiden, zodat de tijden altijd kloppen
    rijen = con.execute(
        "SELECT ts FROM clips WHERE day=? AND view='front' ORDER BY ts", (dag,)).fetchall()
    tijden = [datetime.fromisoformat(r['ts']) for r in rijen]
    groepen, huidig = [], [tijden[0]]
    for vorige, nu in zip(tijden, tijden[1:]):
        if (nu - vorige).total_seconds() > 300:
            groepen.append(huidig); huidig = []
        huidig.append(nu)
    groepen.append(huidig)
    print(f'{len(groepen)} ritten gevonden')

    con.execute('DELETE FROM trips WHERE day = ?', (dag,))
    sporen = [RIT1, RIT2]
    for i, groep in enumerate(groepen):
        vorm = schaal_naar(sporen[i % len(sporen)], DOEL_KM[i % len(DOEL_KM)])
        spoor = verdicht(vorm)
        km = round(lengte(spoor), 1)
        start, eind = groep[0], groep[-1]
        cur = con.execute(
            'INSERT INTO trips (day, start_ts, end_ts, clips, seconds, km, measured, note) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (dag, start.isoformat(timespec='seconds'), eind.isoformat(timespec='seconds'),
             len(groep), int((eind - start).total_seconds()) + 60, km, len(groep),
             'demo - verzonnen route'))
        trip_id = cur.lastrowid
        geo = {'type': 'LineString', 'coordinates': [[lon, lat] for lat, lon in spoor]}
        con.execute(
            'INSERT OR REPLACE INTO routes (trip_id, soort, geojson, km, punten, bijgewerkt) '
            'VALUES (?,?,?,?,?,?)',
            (trip_id, 'gemeten', json.dumps(geo), km, len(spoor),
             datetime.now().astimezone().isoformat(timespec='seconds')))
        print(f'  rit {i + 1}: {start:%H:%M}-{eind:%H:%M}  {len(groep)} clips  {km} km')
    con.commit()

    # Eén VOORBEELD van hard remmen. In de geblurde beelden is de snelheid niet te lezen, dus
    # remmen.py kan hier niets herkennen; dit moment en zijn cijfers zijn verzonnen, alleen om de
    # functie te laten zien. Het filmpje wordt wel echt uit de demobeelden geknipt.
    rcon = remmen.connect()
    eerste = groepen[0]
    moment = eerste[0] + (eerste[-1] - eerste[0]) / 2 + timedelta(seconds=25)
    clip = rcon.execute("SELECT id FROM clips WHERE day = ? AND view = 'front' AND ts <= ? "
                        "ORDER BY ts DESC LIMIT 1", (dag, moment.isoformat(timespec='seconds'))).fetchone()
    rcon.execute('DELETE FROM remmomenten WHERE day = ?', (dag,))
    films = fragment.maak(rcon, str(HERE / 'demo'), 'REM', moment, remmen.MARGE, remmen.MARGE)
    rcon.execute('INSERT INTO remmomenten (ts, day, van_kmh, naar_kmh, daling, duur, clip_id, films, gemaakt) '
                 'VALUES (?,?,?,?,?,?,?,?,?)',
                 (moment.isoformat(timespec='seconds'), dag, 64, 0, 12.5, 6.0, clip['id'],
                  json.dumps(films), datetime.now().astimezone().isoformat(timespec='seconds')))
    rcon.commit()
    print(f'  voorbeeld hard remmen: {moment:%H:%M:%S}  ({len(films)} camerabeelden)')

    print('miniaturen maken...')
    print(' ', thumbs.run(verbose=False))
    print(f'\nKlaar. Start de viewer en kies {dag}.')


if __name__ == '__main__':
    main()
