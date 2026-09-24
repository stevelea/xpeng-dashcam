"""Weer tijdens een rit, uit de KNMI-uurgegevens van het dichtstbijzijnde station — alleen Nederland.

Er gaat geen locatie naar buiten: het station wordt hier gekozen, KNMI krijgt alleen stationsnummer
en datum. Gemeten 14-09-2026: de uurgegevens lopen ~2 dagen achter (12-09 wel, 13-09 nog niet);
een lege dag wordt dus niet vastgelegd maar later opnieuw gevraagd.

KNMI-uurvak H loopt van (H-1):00 tot H:00 UT, met H = 1..24. Eenheden: T in 0,1 °C, RH in 0,1 mm
(-1 = minder dan 0,05 mm), DR in 0,1 uur, FH/FX in 0,1 m/s, N in achtsten (9 = hemel onzichtbaar),
M/R/S/O/Y = mist/regen/sneeuw/onweer/ijzel (0/1).
"""
import json
import math
from datetime import datetime, timedelta, timezone

import httpx

URL = 'https://www.daggegevens.knmi.nl/klimatologie/uurgegevens'
VARS = 'T:RH:DR:FH:FX:N:VV:M:R:S:O:Y'
MAX_KM = 40            # verder van elk station = buitenland of op zee: geen weer
MAX_UUR_ANDERE_RIT = 3  # locatie lenen van een rit dezelfde dag, als deze rit er zelf geen heeft

# (stationsnummer, lat, lon, naam) — uit de kop van de KNMI-uurgegevens, 14-09-2026
STATIONS = [
    (209, 52.465, 4.518, 'IJmond'),
    (210, 52.171, 4.43, 'VALKENBURG VK'),
    (215, 52.141, 4.437, 'Voorschoten'),
    (225, 52.463, 4.555, 'IJmuiden'),
    (235, 52.928, 4.781, 'De Kooy Airport'),
    (240, 52.318, 4.79, 'Schiphol Airport'),
    (242, 53.241, 4.921, 'Vlieland Vliehors'),
    (248, 52.634, 5.174, 'Wijdenes'),
    (249, 52.644, 4.979, 'Berkhout'),
    (251, 53.392, 5.346, 'Hoorn Terschelling'),
    (257, 52.506, 4.603, 'Wijk aan Zee'),
    (258, 52.649, 5.401, 'Houtribdijk'),
    (260, 52.1, 5.18, 'De Bilt'),
    (265, 52.13, 5.274, 'Soesterberg'),
    (267, 52.898, 5.384, 'Stavoren'),
    (269, 52.458, 5.52, 'Lelystad Airport'),
    (270, 53.224, 5.752, 'Leeuwarden Airport'),
    (273, 52.703, 5.888, 'Marknesse'),
    (275, 52.056, 5.873, 'Deelen Airport'),
    (277, 53.413, 6.2, 'Lauwersoog'),
    (278, 52.435, 6.259, 'Heino'),
    (279, 52.75, 6.574, 'Hoogeveen'),
    (280, 53.125, 6.585, 'Groningen Airport Eelde'),
    (283, 52.069, 6.657, 'Hupsel'),
    (285, 53.575, 6.399, 'Huibertgat'),
    (286, 53.196, 7.15, 'Nieuw Beerta'),
    (290, 52.274, 6.891, 'Twenthe Airport'),
    (308, 51.381, 3.379, 'Cadzand'),
    (310, 51.442, 3.596, 'Vlissingen'),
    (311, 51.379, 3.672, 'Hoofdplaat'),
    (312, 51.768, 3.622, 'Oosterschelde'),
    (313, 51.505, 3.242, 'Vlakte van De Raan'),
    (315, 51.447, 3.998, 'Hansweert'),
    (316, 51.657, 3.694, 'Schaar'),
    (319, 51.226, 3.861, 'Westdorpe'),
    (323, 51.527, 3.884, 'Wilhelminadorp'),
    (324, 51.596, 4.006, 'Stavenisse'),
    (330, 51.992, 4.122, 'Hoek van Holland'),
    (331, 51.48, 4.193, 'Tholen'),
    (340, 51.449, 4.342, 'Woensdrecht Airport'),
    (343, 51.893, 4.313, 'Rotterdam Geulhaven'),
    (344, 51.962, 4.447, 'Rotterdam Airport'),
    (348, 51.97, 4.926, 'Cabauw'),
    (350, 51.566, 4.936, 'Gilze-Rijen Airport'),
    (356, 51.859, 5.146, 'Herwijnen'),
    (370, 51.451, 5.377, 'Eindhoven Airport'),
    (375, 51.659, 5.707, 'Volkel'),
    (377, 51.198, 5.763, 'Ell'),
    (380, 50.906, 5.762, 'Maastricht Airport'),
    (391, 51.498, 6.197, 'Arcen'),
    (392, 51.486836, 6.056189, 'Horst'),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS weer_uur (
    station INTEGER NOT NULL,
    datum   TEXT NOT NULL,
    uur     INTEGER NOT NULL,
    data    TEXT NOT NULL,
    PRIMARY KEY (station, datum, uur)
);
"""


def _km(lat1, lon1, lat2, lon2):
    r = math.radians
    a = (math.sin(r(lat2 - lat1) / 2) ** 2 +
         math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(r(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def dichtstbij(lat, lon):
    stn, slat, slon, naam = min(STATIONS, key=lambda s: _km(lat, lon, s[1], s[2]))
    afstand = _km(lat, lon, slat, slon)
    return (stn, naam, round(afstand, 1)) if afstand <= MAX_KM else None


def uurvak(moment):
    """Tijdstip → (datum 'JJJJMMDD', uur 1..24) in UT, zoals KNMI het uurvak noemt."""
    ut = moment.astimezone(timezone.utc)
    vak = ut.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if vak.hour == 0:                      # 23:xx UT hoort bij uur 24 van dezelfde dag
        return (vak - timedelta(days=1)).strftime('%Y%m%d'), 24
    return vak.strftime('%Y%m%d'), vak.hour


def _dag(con, station, datum):
    rows = con.execute('SELECT uur, data FROM weer_uur WHERE station = ? AND datum = ?',
                       (station, datum)).fetchall()
    if rows:
        return {r['uur']: json.loads(r['data']) for r in rows}
    r = httpx.post(URL, data={'start': f'{datum}01', 'end': f'{datum}24', 'stns': station,
                                 'vars': VARS, 'fmt': 'json'}, timeout=30)
    r.raise_for_status()
    uit = {x['hour']: x for x in r.json()}
    if uit:                                # leeg = nog niet gepubliceerd: niet vastleggen
        con.executemany('INSERT OR REPLACE INTO weer_uur VALUES (?,?,?,?)',
                        [(station, datum, u, json.dumps(x)) for u, x in uit.items()])
        con.commit()
    return uit


def _route_begin(con, trip_id):
    r = con.execute('SELECT geojson FROM routes WHERE trip_id = ? AND geojson IS NOT NULL',
                    (trip_id,)).fetchone()
    if not r:
        return None
    coords = (json.loads(r['geojson']) or {}).get('coordinates') or []
    return (coords[0][1], coords[0][0]) if coords else None     # GeoJSON is [lon, lat]


def locatie(con, trip):
    """Plek van de rit: eigen punt, anders eigen route, anders een rit dezelfde dag die dichtbij in
    tijd ligt. Recente ritten hebben vaak geen punten maar wel een route uit de locatie-tracker."""
    w = con.execute('SELECT lat, lon FROM waypoints WHERE trip_id = ? ORDER BY ts LIMIT 1',
                    (trip['id'],)).fetchone()
    if w:
        return w['lat'], w['lon'], 'rit'
    r = _route_begin(con, trip['id'])
    if r:
        return r[0], r[1], 'route'
    midden = datetime.fromisoformat(trip['start_ts'])
    kandidaten = [(w['ts'], w['lat'], w['lon']) for w in con.execute(
        'SELECT w.ts, w.lat, w.lon FROM waypoints w JOIN trips t ON t.id = w.trip_id WHERE t.day = ?',
        (trip['day'],))]
    for t in con.execute('SELECT id, start_ts FROM trips WHERE day = ? AND id != ?',
                         (trip['day'], trip['id'])):
        r = _route_begin(con, t['id'])
        if r:
            kandidaten.append((t['start_ts'], r[0], r[1]))
    beste = None
    for ts, lat, lon in kandidaten:
        dt = abs((datetime.fromisoformat(ts) - midden).total_seconds()) / 3600
        if dt <= MAX_UUR_ANDERE_RIT and (beste is None or dt < beste[0]):
            beste = (dt, lat, lon)
    return (beste[1], beste[2], 'andere rit') if beste else None


def voor_rit(con, trip):
    con.executescript(SCHEMA)
    plek = locatie(con, trip)
    if not plek:
        return {'status': 'geen_locatie'}
    st = dichtstbij(plek[0], plek[1])
    if not st:
        return {'status': 'buitenland'}
    start, eind = datetime.fromisoformat(trip['start_ts']), datetime.fromisoformat(trip['end_ts'])
    datum, uur = uurvak(start + (eind - start) / 2)
    try:
        x = _dag(con, st[0], datum).get(uur)
    except httpx.HTTPError:
        return {'status': 'knmi_onbereikbaar'}
    if not x or x.get('T') is None:
        return {'status': 'nog_niet', 'station': st[1]}

    def tiende(k):
        return None if x.get(k) is None else x[k] / 10

    rh = x.get('RH')
    return {
        'status': 'ok', 'station': st[1], 'station_km': st[2], 'plek': plek[2],
        'uurvak_ut': f'{uur - 1:02d}–{uur:02d} UT',
        'temp': tiende('T'),
        'neerslag_mm': 0.0 if rh in (None, 0) else (0.02 if rh == -1 else rh / 10),
        'regen': bool(x.get('R')) or (rh not in (None, 0)),
        'wind': tiende('FH'), 'windstoot': tiende('FX'),
        'bewolking': x.get('N'),
        'mist': bool(x.get('M')), 'sneeuw': bool(x.get('S')),
        'onweer': bool(x.get('O')), 'ijzel': bool(x.get('Y')),
    }
