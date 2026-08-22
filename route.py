#!/usr/bin/env python3
"""De route van een rit bepalen, met een duidelijk verschil tussen weten en afleiden.

Twee soorten, en die worden nooit door elkaar gehaald:

**gemeten** — echte GPS-punten van de locatie-logger. Dit is waar de auto reed.

**gereconstrueerd** — er zijn alleen losse ankerpunten (uit foto's, met de hand
gezet, of afgelezen van een bord én goedgekeurd). Een routeplanner rijdt daar de
kortste weg tussen. Dat is een aannemelijke lijn, geen bewijs.

Een gelezen plaatsnaam komt er alleen doorheen als hij twee horden neemt:
1. de geocoder kent hem als **woonplaats** — winkels, kentekens en reclame vallen af;
2. hij is **haalbaar** vanaf het vorige punt, gemeten aan de eigen topsnelheid.
   Zo sneuvelt een wegwijzer: die noemt een stad die honderden kilometers verderop ligt.
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta
from math import radians, sin, cos, asin, sqrt
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

NOMINATIM = 'https://nominatim.openstreetmap.org/search'
OSRM = 'https://router.project-osrm.org/route/v1/driving/'
UA = 'xpeng-dashcam/1.0 (persoonlijk gebruik)'
MARGE = 1.35
MIN_KMH = 60
MAX_ANKERS = 24          # OSRM weigert heel lange reeksen
MAX_GAT_S = 90           # groter gat = de weg ertussen is geraden, niet gemeten
_laatste = [0.0]

KENTEKEN = re.compile(r'^[A-Z0-9]{1,3}[- ][A-Z0-9]{1,3}[- ][A-Z0-9]{1,3}$')
PLAATS_SOORTEN = {'city', 'town', 'village', 'hamlet', 'municipality',
                  'suburb', 'borough', 'quarter', 'isolated_dwelling'}


def afstand_km(a, b, c, d):
    r = 6371.0
    dl, dn = radians(c - a), radians(d - b)
    x = sin(dl / 2) ** 2 + cos(radians(a)) * cos(radians(c)) * sin(dn / 2) ** 2
    return 2 * r * asin(sqrt(x))


# ── Gelezen plaatsnamen ───────────────────────────────────────────────────────
def kansrijk(tekst):
    t = tekst.strip()
    if not 3 < len(t) <= 40:
        return False
    if sum(c.isalpha() for c in t) < len(t) * 0.6:
        return False
    if KENTEKEN.match(t.upper()):
        return False
    return not any(c in t for c in '|%@[]{}<>')


def zoek_plaats(con, tekst):
    sleutel = tekst.strip().lower()
    row = con.execute('SELECT lat, lon, naam FROM plaatsnamen WHERE tekst = ?',
                      (sleutel,)).fetchone()
    if row:
        return (row['lat'], row['lon'], row['naam']) if row['lat'] is not None else None

    pauze = 1.1 - (time.time() - _laatste[0])
    if pauze > 0:
        time.sleep(pauze)
    _laatste[0] = time.time()

    lat = lon = naam = None
    try:
        r = httpx.get(NOMINATIM, params={'q': tekst, 'format': 'jsonv2', 'limit': 1,
                                         'featuretype': 'settlement',
                                         'accept-language': 'nl'},
                      headers={'User-Agent': UA}, timeout=20)
        r.raise_for_status()
        d = r.json()
        # featuretype alleen is niet genoeg: Nominatim geeft ook winkels terug.
        if d and d[0].get('category') == 'place' and d[0].get('type') in PLAATS_SOORTEN:
            lat, lon, naam = float(d[0]['lat']), float(d[0]['lon']), d[0]['display_name']
    except Exception:
        return None

    con.execute('INSERT OR REPLACE INTO plaatsnamen (tekst, lat, lon, naam) VALUES (?,?,?,?)',
                (sleutel, lat, lon, naam))
    con.commit()
    return (lat, lon, naam) if lat is not None else None


def topsnelheid(con, trip):
    r = con.execute(
        'SELECT max(s.kmh) m FROM speeds s JOIN clips c ON c.id = s.clip_id '
        "WHERE c.view='front' AND c.ts BETWEEN ? AND ?",
        (trip['start_ts'], trip['end_ts'])).fetchone()
    return max(r['m'] or 0, MIN_KMH)


def keur_gelezen(con, trip, start=None):
    """Zeeft gelezen tekst tot plaatsen die je écht bezocht kunt hebben."""
    grens = topsnelheid(con, trip) * MARGE
    rijen = con.execute('SELECT ts, tekst FROM ocr_tekst WHERE ts BETWEEN ? AND ? ORDER BY ts',
                        (trip['start_ts'], trip['end_ts'])).fetchall()
    goed, afgewezen, vorige = [], [], start
    for r in rijen:
        if not kansrijk(r['tekst']):
            continue
        gevonden = zoek_plaats(con, r['tekst'])
        if not gevonden:
            continue
        lat, lon, naam = gevonden
        ts = datetime.fromisoformat(r['ts'])
        if vorige:
            minuten = (ts - vorige[0]).total_seconds() / 60.0
            afstand = afstand_km(vorige[1], vorige[2], lat, lon)
            nodig = afstand / (minuten / 60.0) if minuten > 0 else 1e9
            if nodig > grens:
                afgewezen.append({'gelezen': r['tekst'], 'werd': naam.split(',')[0],
                                  'reden': f'{afstand:.0f} km in {minuten:.0f} min '
                                           f'= {nodig:.0f} km/h nodig'})
                continue
        if goed and afstand_km(goed[-1][1], goed[-1][2], lat, lon) < 1:
            continue
        goed.append((ts, lat, lon, naam.split(',')[0], r['tekst']))
        vorige = (ts, lat, lon)
    return goed, afgewezen


# ── Gemeten spoor ─────────────────────────────────────────────────────────────
def gemeten_spoor(trip, marge_min=3, met_tijd=False):
    """Echte GPS-punten van de locatie-logger, als die er zijn."""
    basis = store.load_config().get('logger', {}).get('url')
    if not basis:
        return []
    van = (datetime.fromisoformat(trip['start_ts']) - timedelta(minutes=marge_min))
    tot = (datetime.fromisoformat(trip['end_ts']) + timedelta(minutes=marge_min))
    try:
        r = httpx.get(basis.rstrip('/') + '/api/track',
                      params={'van': van.isoformat(timespec='seconds'),
                              'tot': tot.isoformat(timespec='seconds')}, timeout=20)
        r.raise_for_status()
        punten = r.json().get('punten', [])
    except Exception:
        return []
    # De telefoon eerst: die meldt ook tijdens het rijden. De auto meldt alleen als
    # hij stilstaat en levert dus nooit een spoor.
    per_bron = {}
    for p in punten:
        per_bron.setdefault(p['bron'], []).append(p)
    if not per_bron:
        return []
    volgorde = store.load_config().get('logger', {}).get('volgorde', [])
    reeks = None
    for bron in volgorde:
        if len(per_bron.get(bron, [])) >= 3:
            reeks = per_bron[bron]
            break
    if reeks is None:
        reeks = max(per_bron.values(), key=len)
    schoon = []
    for p in reeks:
        if schoon and afstand_km(schoon[-1][0], schoon[-1][1], p['lat'], p['lon']) < 0.05:
            continue
        schoon.append((p['lat'], p['lon'], p['ts']))
    if met_tijd:
        return schoon
    return [(a, b) for a, b, _ in schoon]


# ── Ankers en routeren ────────────────────────────────────────────────────────
def ankers(con, trip):
    """Alle punten waarvan we weten dat de auto er was, op tijd geordend."""
    rijen = con.execute(
        "SELECT ts, lat, lon, label, source FROM waypoints "
        "WHERE trip_id = ? AND source != 'gelezen' ORDER BY ts", (trip['id'],)).fetchall()
    return [(datetime.fromisoformat(r['ts']), r['lat'], r['lon'],
             r['label'] or 'punt', r['source']) for r in rijen]


def start_anker(con, trip):
    r = con.execute(
        "SELECT ts, lat, lon FROM waypoints WHERE trip_id = ? AND source != 'gelezen' "
        'ORDER BY ts LIMIT 1', (trip['id'],)).fetchone()
    if not r:
        r = con.execute(
            "SELECT ts, lat, lon FROM waypoints WHERE ts < ? AND source != 'gelezen' "
            'ORDER BY ts DESC LIMIT 1', (trip['start_ts'],)).fetchone()
    return (datetime.fromisoformat(r['ts']), r['lat'], r['lon']) if r else None


def omsluitend(con, trip):
    """Laatst bekende plek vóór de rit en eerste bekende plek erna.

    De tijd ertussen doet er niet toe, wél of de auto ondertussen gereden heeft. De
    dashcam neemt namelijk op zodra de auto rijdt: zit er geen enkele rit tussen dat
    punt en deze rit, dan stond de auto daar nog. Zo mag een foto van gisteravond thuis
    het vertrekpunt van vanochtend zijn — maar een punt van vóór een tussenliggende rit
    niet, want toen is de auto verplaatst.
    """
    def zoek(richting):
        if richting == 'voor':
            w = con.execute(
                "SELECT ts, lat, lon, label FROM waypoints WHERE source != 'gelezen' "
                'AND ts < ? ORDER BY ts DESC LIMIT 1', (trip['start_ts'],)).fetchone()
            if not w:
                return None
            tussen = con.execute(
                'SELECT count(*) n FROM trips WHERE id != ? AND start_ts > ? AND end_ts < ?',
                (trip['id'], w['ts'], trip['start_ts'])).fetchone()['n']
            return None if tussen else w
        w = con.execute(
            "SELECT ts, lat, lon, label FROM waypoints WHERE source != 'gelezen' "
            'AND ts > ? ORDER BY ts LIMIT 1', (trip['end_ts'],)).fetchone()
        if not w:
            return None
        tussen = con.execute(
            'SELECT count(*) n FROM trips WHERE id != ? AND start_ts > ? AND end_ts < ?',
            (trip['id'], trip['end_ts'], w['ts'])).fetchone()['n']
        return None if tussen else w

    maak = lambda r, wat: (datetime.fromisoformat(r['ts']), r['lat'], r['lon'],
                           r['label'] or wat, wat)
    v, n = zoek('voor'), zoek('na')
    return (maak(v, 'vertrek') if v else None, maak(n, 'aankomst') if n else None)


def rijd(punten):
    """Verbindt punten over echte wegen. Punten zijn (lat, lon)."""
    if len(punten) < 2:
        return None, None
    if len(punten) > MAX_ANKERS:
        stap = len(punten) / MAX_ANKERS
        punten = [punten[int(i * stap)] for i in range(MAX_ANKERS)] + [punten[-1]]
    coords = ';'.join(f'{lon},{lat}' for lat, lon in punten)
    try:
        r = httpx.get(OSRM + coords, params={'overview': 'full', 'geometries': 'geojson'},
                      headers={'User-Agent': UA}, timeout=45)
        r.raise_for_status()
        d = r.json()
    except Exception:
        return None, None
    if d.get('code') != 'Ok' or not d.get('routes'):
        return None, None
    return d['routes'][0]['geometry'], d['routes'][0]['distance'] / 1000.0


def grootste_gat(trip):
    """Het grootste gat in seconden tussen twee gemeten punten TIJDENS de rit.

    ⚠️ Alleen punten tussen start en eind tellen mee. Het spoor wordt met een paar
    minuten marge opgehaald, en in die marge staat de auto stil — daar meldt de
    telefoon veel trager. Op 21-08 duwde dat het grootste gat naar 89 s terwijl de
    rit zelf een mediaan van 10 s had: bijna ten onrechte als geraden bestempeld.
    Het gaat om de dichtheid onderweg, niet om die ervoor en erna."""
    reeks = gemeten_spoor(trip, met_tijd=True)
    start = datetime.fromisoformat(trip['start_ts'])
    eind = datetime.fromisoformat(trip['end_ts'])
    tijden = sorted(t for t in (datetime.fromisoformat(x[2]) for x in reeks)
                    if start <= t <= eind)
    if len(tijden) < 2:
        return 10 ** 9
    return max((b - a).total_seconds() for a, b in zip(tijden, tijden[1:]))


def bouw(trip_id, gebruik_gelezen=True, con=None):
    own = con is None
    con = con or store.connect()
    trip = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not trip:
        raise ValueError('rit bestaat niet')

    afgewezen = []
    spoor = gemeten_spoor(trip)

    if len(spoor) >= 3:
        aantal = len(spoor)
        namen = []
        # Alleen een DICHT spoor mag 'gemeten' heten. Staan de punten ver uit elkaar in
        # de tijd, dan verzint OSRM de weg ertussen en kan die er glad naast zitten:
        # op 20-08 koos hij voor rit 3043 een andere terugweg dan de Ketelweg. Zo'n lijn
        # hoort als gereconstrueerd getekend te worden, anders lijkt een gok een meting.
        soort = 'gemeten' if grootste_gat(trip) <= MAX_GAT_S else 'gereconstrueerd'
        # De telefoon meldt tijdens het rijden maar om de paar minuten. Een rechte lijn
        # tussen die punten snijdt elke bocht af: gemeten op 20-08 gaf dat 6,5 km waar
        # de snelheid in beeld 9,1 km aanwees. Daarom de punten over echte wegen
        # verbinden. Lukt dat niet, dan blijft de rechte lijn staan — liever een ruwe
        # lijn dan geen lijn.
        geo, km = rijd(spoor)
        if not geo:
            geo = {'type': 'LineString', 'coordinates': [[lon, lat] for lat, lon in spoor]}
            km = sum(afstand_km(a[0], a[1], b[0], b[1]) for a, b in zip(spoor, spoor[1:]))
    else:
        soort = 'gereconstrueerd'
        punten = ankers(con, trip)
        if gebruik_gelezen:
            gelezen, afgewezen = keur_gelezen(con, trip, start=start_anker(con, trip))
            con.execute("DELETE FROM waypoints WHERE trip_id = ? AND source = 'gelezen'",
                        (trip_id,))
            for ts, lat, lon, naam, _ in gelezen:
                con.execute('INSERT OR REPLACE INTO waypoints '
                            '(trip_id, ts, lat, lon, label, source) VALUES (?,?,?,?,?,?)',
                            (trip_id, ts.isoformat(timespec='seconds'), lat, lon, naam, 'gelezen'))
            punten = sorted(punten + [(t, a, b, n, 'gelezen') for t, a, b, n, _ in gelezen],
                            key=lambda x: x[0])
        voor, na = omsluitend(con, trip)
        if voor and (not punten or afstand_km(voor[1], voor[2], punten[0][1], punten[0][2]) > .2):
            punten.insert(0, voor)
        if na and (not punten or afstand_km(na[1], na[2], punten[-1][1], punten[-1][2]) > .2):
            punten.append(na)
        geo, km = rijd([(p[1], p[2]) for p in punten])
        aantal = len(punten)
        namen = [{'tijd': p[0].strftime('%H:%M'), 'naam': p[3], 'bron': p[4]} for p in punten]

    con.execute('INSERT OR REPLACE INTO routes '
                '(trip_id, soort, geojson, km, punten, bijgewerkt) VALUES (?,?,?,?,?,?)',
                (trip_id, soort, json.dumps(geo) if geo else None,
                 round(km, 1) if km else None, aantal,
                 datetime.now().astimezone().isoformat(timespec='seconds')))
    con.commit()
    if own:
        con.close()
    return {'soort': soort, 'punten': aantal, 'route_km': round(km, 1) if km else None,
            'namen': namen, 'afgewezen': afgewezen, 'heeft_lijn': geo is not None}


if __name__ == '__main__':
    r = bouw(int(sys.argv[1]))
    print(f"soort: {r['soort']}  ·  {r['punten']} punten  ·  {r['route_km']} km over de weg")
    for n in r['namen']:
        print(f"   {n['tijd']}  {n['naam'][:50]}  ({n['bron']})")
    if r['afgewezen']:
        print(f"\nafgewezen: {len(r['afgewezen'])}")
        for a in r['afgewezen'][:6]:
            print(f"   {a['gelezen']} → {a['werd']} — {a['reden']}")
