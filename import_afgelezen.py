#!/usr/bin/env python3
"""Neemt afgelezen locaties over uit een geplakte tabel, maar alleen na controle.

Een taalmodel dat borden leest, leest echte dingen en geeft ze soms een verzonnen
naam. Daarom gaat hier niets naar binnen zonder toets:

- de naam wordt zelf opgezocht bij de geocoder;
- staat er ook een coordinaat bij, dan moeten die twee bij elkaar in de buurt liggen;
- wat niet klopt, komt op een lijstje in plaats van op de kaart.

Invoer: één regel per waarneming, kolommen gescheiden door tab of |.
Herkende kolommen (volgorde maakt niet uit):
    bestandsnaam of tijdstip   ·   plaatsnaam   ·   optioneel lat,lon

Voorbeeld:
    DVR_20260101101815728_front.mp4 | 10:18:15 | Stationsplein, Utrecht
    DVR_20260101102015837_front.mp4 | 10:20:15 | Croeselaan, Utrecht | 52.0874, 5.1099
"""
import re
import sys
import time
from datetime import datetime, timedelta
from math import radians, sin, cos, asin, sqrt
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

AMS = ZoneInfo('Europe/Amsterdam')
STAMP = re.compile(r'([0-9]{17})')
COORD = re.compile(r'^\s*(-?\d{1,2}\.\d{3,})\s*,\s*(-?\d{1,3}\.\d{3,})\s*$')
MAX_AFWIJKING_M = 1500
_laatste = [0.0]


def afstand_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def zoek(naam):
    """Zoekt een naam op. Geeft (lat, lon, volledige naam) of None."""
    pauze = 1.1 - (time.time() - _laatste[0])
    if pauze > 0:
        time.sleep(pauze)
    _laatste[0] = time.time()
    try:
        r = httpx.get('https://nominatim.openstreetmap.org/search',
                      params={'q': naam, 'format': 'jsonv2', 'limit': 1,
                              'accept-language': 'nl'},
                      headers={'User-Agent': 'xpeng-dashcam/1.0 (persoonlijk)'}, timeout=20)
        r.raise_for_status()
        d = r.json()
    except Exception:
        return None
    if not d:
        return None
    return float(d[0]['lat']), float(d[0]['lon']), d[0]['display_name']


def lees_regels(tekst):
    """Haalt uit elke regel: tijdstip, naam en eventueel een coordinaat."""
    uit = []
    for regel in tekst.splitlines():
        regel = regel.strip().strip('|')
        if not regel or regel.lower().startswith(('bestandsnaam', '#', '---', 'nr')):
            continue
        velden = [v.strip() for v in re.split(r'\t|\|', regel) if v.strip()]
        if len(velden) < 2:
            continue

        tijd = naam = None
        lat = lon = None
        for v in velden:
            m = STAMP.search(v)
            if m and tijd is None:
                try:
                    tijd = datetime.strptime(m.group(1)[:14], '%Y%m%d%H%M%S').replace(tzinfo=AMS)
                except ValueError:
                    pass
                continue
            c = COORD.match(v)
            if c:
                lat, lon = float(c.group(1)), float(c.group(2))
                continue
            if re.fullmatch(r'\d{1,2}:\d{2}(:\d{2})?', v):
                continue
            if re.fullmatch(r'\d+\s*km/h.*', v, re.I) or re.fullmatch(r'[DPRN]', v):
                continue
            if naam is None and len(v) > 3:
                naam = v
        if tijd and naam:
            uit.append({'tijd': tijd, 'naam': naam, 'lat': lat, 'lon': lon})
    return uit


def rit_bij(con, tijd):
    r = con.execute('SELECT id FROM trips WHERE ? BETWEEN start_ts AND end_ts',
                    (tijd.isoformat(timespec='seconds'),)).fetchone()
    if r:
        return r['id']
    # net buiten een rit: pak de dichtstbijzijnde binnen 10 minuten
    r = con.execute(
        'SELECT id, start_ts, end_ts FROM trips WHERE day = ? ORDER BY start_ts',
        (tijd.strftime('%Y-%m-%d'),)).fetchall()
    for x in r:
        s = datetime.fromisoformat(x['start_ts']) - timedelta(minutes=10)
        e = datetime.fromisoformat(x['end_ts']) + timedelta(minutes=10)
        if s <= tijd <= e:
            return x['id']
    return None


def verwerk(tekst, opslaan=True):
    con = store.connect()
    goed, twijfel, fout = [], [], []

    for regel in lees_regels(tekst):
        gevonden = zoek(regel['naam'])
        if not gevonden:
            fout.append({**regel, 'reden': 'naam bestaat niet volgens de geocoder'})
            continue
        glat, glon, volledig = gevonden

        afwijking = None
        if regel['lat'] is not None:
            afwijking = afstand_m(glat, glon, regel['lat'], regel['lon'])
            if afwijking > MAX_AFWIJKING_M:
                twijfel.append({**regel, 'geocoder': volledig,
                                'reden': f'coordinaat wijkt {afwijking / 1000:.1f} km af'})
                continue

        trip = rit_bij(con, regel['tijd'])
        if trip is None:
            twijfel.append({**regel, 'geocoder': volledig,
                            'reden': 'geen rit op dat tijdstip'})
            continue

        if opslaan:
            con.execute(
                'INSERT OR REPLACE INTO waypoints (trip_id, ts, lat, lon, label, source) '
                'VALUES (?,?,?,?,?,?)',
                (trip, regel['tijd'].isoformat(timespec='seconds'), glat, glon,
                 volledig.split(',')[0] + ', ' + volledig.split(',')[-4].strip()
                 if volledig.count(',') >= 4 else volledig[:60],
                 'afgelezen'))
        goed.append({**regel, 'trip': trip, 'geocoder': volledig,
                     'afwijking_m': None if afwijking is None else round(afwijking)})

    con.commit()
    con.close()
    return {'opgenomen': goed, 'twijfel': twijfel, 'afgekeurd': fout}


if __name__ == '__main__':
    tekst = Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else sys.stdin.read()
    r = verwerk(tekst, opslaan='--proef' not in sys.argv)
    print(f"opgenomen : {len(r['opgenomen'])}")
    for x in r['opgenomen']:
        extra = '' if x['afwijking_m'] is None else f" (coordinaat klopt, {x['afwijking_m']} m)"
        print(f"   {x['tijd']:%d-%m %H:%M}  rit {x['trip']}  {x['naam']}{extra}")
    print(f"\ntwijfel   : {len(r['twijfel'])}")
    for x in r['twijfel']:
        print(f"   {x['tijd']:%d-%m %H:%M}  {x['naam']} — {x['reden']}")
    print(f"\nafgekeurd : {len(r['afgekeurd'])}")
    for x in r['afgekeurd']:
        print(f"   {x['tijd']:%d-%m %H:%M}  {x['naam']} — {x['reden']}")
