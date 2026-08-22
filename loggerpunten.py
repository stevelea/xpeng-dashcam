#!/usr/bin/env python3
"""Zet de posities uit de locatie-logger om in ankerpunten bij ritten.

**De telefoon is de bron.** Die zit altijd op zak en meldt ook tijdens het rijden. De
volgorde staat in `config.json` onder `logger.volgorde`.

⚠️ Gemeten op 20-08-2026: de **auto meldt zich alleen als hij stilstaat**, ongeveer elke
vier minuten. Van 1.677 punten lagen er zes verder dan 300 m van huis, en die zes waren
dezelfde geparkeerde plek. Uit de auto komt dus géén spoor. Hij blijft als reserve staan
voor begin- en eindpunten.

Deze punten heten `logger` en gaan vóór een aangenomen thuis-punt: ze zijn gemeten.
"""
import sys
from datetime import datetime, timedelta
from math import radians, sin, cos, asin, sqrt
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

MARGE_MIN = 25          # zover voor en na een rit mag een punt vandaan komen


def bronnen(cfg):
    """De telefoon eerst: die meldt ook tijdens het rijden. De auto is reserve.

    Geen volgorde ingesteld betekent geen bronnen: dan blijven de routes gewoon uit.
    Een vaste naam hier zou bij iedere andere gebruiker toch niets opleveren."""
    return cfg.get('logger', {}).get('volgorde', [])


def afstand_km(a, b, c, d):
    r = 6371.0
    dl, dn = radians(c - a), radians(d - b)
    x = sin(dl / 2) ** 2 + cos(radians(a)) * cos(radians(c)) * sin(dn / 2) ** 2
    return 2 * r * asin(sqrt(x))


def haal(cfg, van, tot, bron=''):
    basis = cfg.get('logger', {}).get('url')
    if not basis:
        return []
    try:
        r = httpx.get(basis.rstrip('/') + '/api/track',
                      params={'van': van.isoformat(timespec='seconds'),
                              'tot': tot.isoformat(timespec='seconds'), 'bron': bron},
                      timeout=30)
        r.raise_for_status()
        return r.json().get('punten', [])
    except Exception:
        return []


def zet_ankers(con=None, cfg=None, vanaf=None):
    """Geeft elke rit een begin- en eindpunt uit de logger, waar die er zijn."""
    own = con is None
    con = con or store.connect()
    cfg = cfg or store.load_config()

    sql = 'SELECT id, day, start_ts, end_ts FROM trips'
    args = []
    if vanaf:
        sql += ' WHERE day >= ?'
        args.append(vanaf)
    ritten = con.execute(sql + ' ORDER BY start_ts', args).fetchall()

    con.execute("DELETE FROM waypoints WHERE source = 'logger'")
    gezet = 0
    for t in ritten:
        start = datetime.fromisoformat(t['start_ts'])
        eind = datetime.fromisoformat(t['end_ts'])
        voor = na = []
        for bron in bronnen(cfg):
            voor = voor or haal(cfg, start - timedelta(minutes=MARGE_MIN), start, bron)
            na = na or haal(cfg, eind, eind + timedelta(minutes=MARGE_MIN), bron)
            if voor and na:
                break
        for punten, ts, wat in ((voor, t['start_ts'], 'vertrek'), (na, t['end_ts'], 'aankomst')):
            if not punten:
                continue
            p = punten[-1] if wat == 'vertrek' else punten[0]
            con.execute('INSERT OR REPLACE INTO waypoints '
                        '(trip_id, ts, lat, lon, label, source) VALUES (?,?,?,?,?,?)',
                        (t['id'], ts, p['lat'], p['lon'], wat, 'logger'))
            gezet += 1
    # een aangenomen punt is overbodig zodra er een gemeten punt op hetzelfde moment ligt
    con.execute("""DELETE FROM waypoints WHERE source = 'aangenomen' AND EXISTS
                   (SELECT 1 FROM waypoints w2 WHERE w2.trip_id = waypoints.trip_id
                     AND w2.ts = waypoints.ts AND w2.source = 'logger')""")
    con.commit()
    if own:
        con.close()
    return {'gezet': gezet}


if __name__ == '__main__':
    print(zet_ankers(vanaf=sys.argv[1] if len(sys.argv) > 1 else None))
