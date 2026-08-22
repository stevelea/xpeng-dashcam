#!/usr/bin/env python3
"""Thuis als vertrekpunt — maar alleen waar dat te verdedigen valt.

De meeste ritten van een dag vertrekken vanaf de thuislocatie. Dat is precies het
ontbrekende stuk: zonder vertrekpunt valt er geen route te tekenen.

⚠️ Blind aannemen mag niet: tijdens een reis klopt het niet. Daarom worden de periodes
weg van huis **uit de gegevens zelf afgeleid** — dagen waarop een bekend punt (foto of
logger) meer dan 50 km van de thuislocatie lag. Binnen zo'n periode wordt er niets
aangenomen.

Een aangenomen punt heet in de database `aangenomen` en is in de app te herkennen.
Een punt uit een foto of de logger gaat er altijd voor.

Wat NIET werkte: het eerste beeld van een rit vergelijken met voorbeelden van de drie
parkeerstanden (neus vooruit, neus achteruit, oprit). Gemeten op 20-08 met rasters van
64, 256 en 1024 bits: thuisdagen scoorden 0,16–0,48 en dagen in Spanje 0,34–0,50 — de
groepen overlappen bij elke instelling. Straten met huizen lijken nu eenmaal op elkaar.
Niet opnieuw proberen zonder een wezenlijk ander idee.
"""
import sys
from datetime import date, timedelta
from math import radians, sin, cos, asin, sqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

VER_KM = 50           # verder dan dit van huis = niet thuis
GAT_DAGEN = 3         # zoveel dagen zonder ver punt sluit een periode af


def afstand_km(a, b, c, d):
    r = 6371.0
    dl, dn = radians(c - a), radians(d - b)
    x = sin(dl / 2) ** 2 + cos(radians(a)) * cos(radians(c)) * sin(dn / 2) ** 2
    return 2 * r * asin(sqrt(x))


def thuis_coord(cfg=None):
    cfg = cfg or store.load_config()
    t = cfg.get('thuis', {})
    return t.get('lat'), t.get('lon')


def weg_periodes(con, cfg=None):
    """Periodes dat de auto aantoonbaar niet thuis stond, uit de bekende punten."""
    lat, lon = thuis_coord(cfg)
    if lat is None:
        return []
    ver = set()
    per_dag = {}
    for w in con.execute('SELECT ts, lat, lon FROM waypoints ORDER BY ts'):
        dag = w['ts'][:10]
        d = afstand_km(lat, lon, w['lat'], w['lon'])
        per_dag[dag] = min(per_dag.get(dag, 1e9), d)
    for dag, d in per_dag.items():
        if d > VER_KM:
            ver.add(dag)

    periodes = []
    for dag in sorted(ver):
        d = date.fromisoformat(dag)
        if periodes and d - periodes[-1][1] <= timedelta(days=GAT_DAGEN):
            periodes[-1][1] = d
        else:
            periodes.append([d, d])
    return [(a.isoformat(), b.isoformat()) for a, b in periodes]


def was_weg(dag, periodes):
    return any(a <= dag <= b for a, b in periodes)


def thuis_anker(con, trip, periodes=None, cfg=None):
    """Thuis als vertrekpunt, of None als dat niet te verdedigen is.

    Alleen voor de **eerste rit van een dag**: dan stond de auto de nacht ervoor
    voor de deur. Bij latere ritten begint de auto waar de vorige eindigde, en dat
    weten we niet."""
    cfg = cfg or store.load_config()
    lat, lon = thuis_coord(cfg)
    if lat is None:
        return None
    periodes = weg_periodes(con, cfg) if periodes is None else periodes
    if was_weg(trip['day'], periodes):
        return None
    eerste = con.execute('SELECT id FROM trips WHERE day = ? ORDER BY start_ts LIMIT 1',
                         (trip['day'],)).fetchone()
    if not eerste or eerste['id'] != trip['id']:
        return None
    return {'ts': trip['start_ts'], 'lat': lat, 'lon': lon,
            'label': cfg.get('thuis', {}).get('naam', 'thuis'), 'source': 'aangenomen'}


def thuis_eind_anker(con, trip, periodes, cfg):
    """Thuis als eindpunt van de laatste rit van een dag.

    De redenering: staat de auto de volgende opnamedag weer voor de deur, dan heeft
    hij daar sindsdien gestaan — er zijn immers geen ritten tussendoor, en de dashcam
    neemt op zodra de auto rijdt. Dus eindigde de laatste rit van die dag thuis."""
    lat, lon = thuis_coord(cfg)
    if lat is None or was_weg(trip['day'], periodes):
        return None
    laatste = con.execute('SELECT id FROM trips WHERE day = ? ORDER BY start_ts DESC LIMIT 1',
                          (trip['day'],)).fetchone()
    if not laatste or laatste['id'] != trip['id']:
        return None
    volgende = con.execute('SELECT day, id FROM trips WHERE day > ? ORDER BY start_ts LIMIT 1',
                           (trip['day'],)).fetchone()
    if not volgende or was_weg(volgende['day'], periodes):
        return None
    return {'ts': trip['end_ts'], 'lat': lat, 'lon': lon,
            'label': cfg.get('thuis', {}).get('naam', 'thuis'), 'source': 'aangenomen'}


def zet_ankers(con=None, cfg=None):
    """Zet het aangenomen thuis-punt bij elke eerste rit van een dag."""
    own = con is None
    con = con or store.connect()
    cfg = cfg or store.load_config()
    periodes = weg_periodes(con, cfg)
    con.execute("DELETE FROM waypoints WHERE source = 'aangenomen'")
    gezet = 0
    for t in con.execute('SELECT id, day, start_ts, end_ts FROM trips ORDER BY start_ts'):
        for a in (thuis_anker(con, t, periodes, cfg),
                  thuis_eind_anker(con, t, periodes, cfg)):
            if not a:
                continue
            con.execute('INSERT OR REPLACE INTO waypoints '
                        '(trip_id, ts, lat, lon, label, source) VALUES (?,?,?,?,?,?)',
                        (t['id'], a['ts'], a['lat'], a['lon'], a['label'], 'aangenomen'))
            gezet += 1
    con.commit()
    if own:
        con.close()
    return {'gezet': gezet, 'weg_periodes': periodes}


if __name__ == '__main__':
    print(zet_ankers())
