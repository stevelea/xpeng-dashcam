#!/usr/bin/env python3
"""Toets de koppeling tussen onze ritten en die van EVConduit, zonder netwerk.

Draaien:  python3 toets_evconduit.py

De interessantste gevallen zijn niet "vindt hij de rit" maar de randen: een rit
die alleen op de marge past mag geen treffer heten, en de zomertijd moet niet
stilletjes een uur verschuiven.
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import store
import evconduit

TMP = Path(tempfile.mkdtemp())
store.DB_PATH = TMP / 'toets.db'
store._config = {
    'timezone': 'Europe/Amsterdam',
    'evconduit': {'url': 'https://voorbeeld.test', 'sleutel': 'geheim',
                  'marge_s': 180, 'aan': True},
}

fouten = []


def check(label, ok, detail=''):
    print(f"{'OK  ' if ok else 'FOUT'}  {label}{'  — ' + str(detail) if detail else ''}")
    if not ok:
        fouten.append(label)


def rit(start_ts, end_ts):
    return {'id': 1, 'day': start_ts[:10], 'start_ts': start_ts, 'end_ts': end_ts,
            'clips': 10, 'seconds': 1080, 'km': 14.3, 'measured': 10, 'note': None}


def auto(started, ended, **extra):
    rij = {'id': 'uuid-1', 'vin': 'L1NSPGHB1PA000001', 'started_at': started,
           'ended_at': ended, 'duration_seconds': int(
               (datetime.fromisoformat(ended.replace('Z', '+00:00'))
                - datetime.fromisoformat(started.replace('Z', '+00:00'))).total_seconds()),
           'distance_km': 14.1, 'energy_kwh': 2.4, 'max_speed_kmh': 112,
           'mean_moving_speed_kmh': 47, 'odometer_start': 12000, 'odometer_end': 12014,
           'soc_start': 71, 'soc_end': 66, 'regen_kwh': 0.4, 'user_id': 'prive',
           'export_id': 'ook-prive'}
    rij.update(extra)
    return rij


TIJDEN = None


def nep_get(url, params=None, headers=None, timeout=None):
    """Doet zich voor als EVConduit. Onthoudt welke paden zijn opgevraagd."""
    TIJDEN.append(url)
    class R:
        status_code = 200
        def __init__(self, d):
            self._d = d
        def json(self):
            return self._d
    if url.endswith('/user/xpeng/trips'):
        return R({'trips': NEP_RITTEN})
    if '/track' in url:
        return R(NEP_SPOOR)
    return R({})


NEP_RITTEN = []
NEP_SPOOR = {}


def met_ritten(rijen, spoor=None):
    global NEP_RITTEN, NEP_SPOOR
    NEP_RITTEN = rijen
    NEP_SPOOR = spoor or {'available': False, 'reason': 'no_positions', 'seconds': [],
                          'lat': [], 'lon': [], 'point_count': 0, 'source_point_count': 0,
                          'coverage': None, 'covered_seconds': None, 'trip_seconds': None,
                          'largest_gap_seconds': None, 'track_distance_km': None,
                          'window': None}


evconduit.httpx.get = nep_get

# ── 1. Tijdzone: lokale dashcam-tijd moet UTC worden ──────────────────────────
con = store.connect()
t = rit('2026-09-14T14:23:00', '2026-09-14T14:41:00')
ons = evconduit._ons_venster(t)
check('zomertijd: 14:23 lokaal is 12:23 UTC',
      ons[0].strftime('%H:%M') == '12:23' and ons[1].strftime('%H:%M') == '12:41',
      f'{ons[0].isoformat()} .. {ons[1].isoformat()}')

# wintertijd: dezelfde kloktijd is een uur eerder in UTC
store._config['timezone'] = 'Europe/Amsterdam'
t_winter = rit('2026-01-14T14:23:00', '2026-01-14T14:41:00')
ons_w = evconduit._ons_venster(t_winter)
check('wintertijd: 14:23 lokaal is 13:23 UTC',
      ons_w[0].strftime('%H:%M') == '13:23', ons_w[0].isoformat())

# ── 2. Een rit die precies past ───────────────────────────────────────────────
TIJDEN = []
met_ritten([auto('2026-09-14T12:23:14Z', '2026-09-14T12:41:22Z')])
d = evconduit.koppel(con, t)
check('precies passende rit wordt gevonden', d['beschikbaar'], d['reden'])
check('dekking is 0.987: de auto begint 14 s later dan wij',
      d['dekking'] == 0.987, d['dekking'])
check('klokverschil wordt gemeld, niet weggepoetst',
      d['rit'] is not None, json.dumps(d.get('rit', {}).get('started_at')))
kand = evconduit._kandidaten(ons, NEP_RITTEN, 180)[0]
check('startafwijking is +14 s', kand['start_afwijking_s'] == 14, kand['start_afwijking_s'])
check('eindafwijking is +22 s', kand['eind_afwijking_s'] == 22, kand['eind_afwijking_s'])
check('prive-velden niet bewaard', 'user_id' not in (d['rit'] or {}), list((d['rit'] or {}).keys())[:4])

# ── 3. Ver uit elkaar: geen treffer, en dat is geen fout ──────────────────────
met_ritten([auto('2026-09-14T05:00:00Z', '2026-09-14T05:20:00Z')])
d = evconduit.koppel(con, t, forceer=True)
check('rit van uren later is geen treffer', d['reden'] == 'geen_rit', d['reden'])

# ── 4. Alleen op de marge: twijfel, geen treffer ──────────────────────────────
# Onze rit eindigt 12:41; de auto begint 12:44 — 3 min later, dus binnen marge 180 s
met_ritten([auto('2026-09-14T12:44:00Z', '2026-09-14T13:00:00Z')])
d = evconduit.koppel(con, t, forceer=True)
check('alleen op de marge = twijfel', d['reden'] == 'twijfel', (d['reden'], d.get('dekking')))
check('bij twijfel geen spoor', d['spoor'] is None, d['spoor'])

# ── 5. Twee ritten die allebei een stuk dekken: ambigu ────────────────────────
met_ritten([auto('2026-09-14T12:23:00Z', '2026-09-14T12:50:00Z', id='a'),
            auto('2026-09-14T12:30:00Z', '2026-09-14T13:10:00Z', id='b')])
d = evconduit.koppel(con, t, forceer=True)
check('beste treffer gekozen', d['beschikbaar'] and d['rit']['id'] == 'a', d.get('rit', {}).get('id'))
check('tweede kandidaat wordt gemeld', len(d['kandidaten']) == 1, len(d['kandidaten']))

# ── 6. Spoor wordt GeoJSON met [lon, lat] ─────────────────────────────────────
met_ritten([auto('2026-09-14T12:23:00Z', '2026-09-14T12:41:00Z')],
           spoor={'available': True, 'reason': None, 'seconds': [0, 60, 120],
                  'lat': [52.1, 52.2, 52.3], 'lon': [5.1, 5.2, 5.3],
                  'point_count': 3, 'source_point_count': 900, 'coverage': 0.87,
                  'covered_seconds': 940, 'trip_seconds': 1080,
                  'largest_gap_seconds': 42, 'track_distance_km': 13.8,
                  'window': {'from': 'x', 'to': 'y'}})
d = evconduit.koppel(con, t, forceer=True)
s = d['spoor']
check('spoor beschikbaar', bool(s and s['beschikbaar']))
check('GeoJSON is [lon, lat]', s['geojson']['coordinates'][0] == [5.1, 52.1],
      s['geojson']['coordinates'][0])
check('dekking van het spoor reist mee', s['dekking'] == 0.87, s['dekking'])
check('grootste gat reist mee', s['grootste_gat_s'] == 42, s['grootste_gat_s'])
check('spoorlengte naast ritafstand', s['spoor_km'] == 13.8 and d['rit']['distance_km'] == 14.1)

# ── 7. Niets ingesteld: geen aanroep, geen fout ───────────────────────────────
store._config['evconduit'] = {'url': '', 'sleutel': '', 'marge_s': 180, 'aan': True}
evconduit.vergeet(con)
TIJDEN = []
d = evconduit.koppel(con, t)
check('zonder instelling geen netwerkverkeer', TIJDEN == [], TIJDEN)
check('en de reden is geen_evconduit', d['reden'] == 'geen_evconduit', d['reden'])

# ── 7b. Uitgeschakeld betekent uit, ook voor de cache ────────────────────────
met_ritten([auto('2026-09-14T12:23:00Z', '2026-09-14T12:41:00Z')])
store._config['evconduit'] = {'url': 'https://voorbeeld.test', 'sleutel': 'geheim',
                              'marge_s': 180, 'aan': True}
evconduit.koppel(con, t, forceer=True)          # vult de cache
store._config['evconduit'] = {**store._config['evconduit'], 'aan': False}
d = evconduit.koppel(con, t)
check('uitgeschakeld verbergt ook wat bewaard is', d['reden'] == 'geen_evconduit', d['reden'])
store._config['evconduit'] = {**store._config['evconduit'], 'aan': True}
d = evconduit.koppel(con, t)
check('weer aan: de cache is er nog', d['beschikbaar'], d['reden'])

# ── 8. Cache: tweede keer geen nieuwe oproep ──────────────────────────────────
store._config['evconduit'] = {'url': 'https://voorbeeld.test', 'sleutel': 'geheim',
                              'marge_s': 180, 'aan': True}
met_ritten([auto('2026-09-14T12:23:00Z', '2026-09-14T12:41:00Z')])
evconduit.vergeet(con)
TIJDEN = []
evconduit.koppel(con, t, forceer=True)
eerste = len(TIJDEN)
TIJDEN = []
evconduit.koppel(con, t)
check('tweede keer komt uit de cache', TIJDEN == [], f'eerste={eerste} tweede={TIJDEN}')

# ── 9. De sleutel komt nooit naar buiten ──────────────────────────────────────
import app as app_mod
gelezen = app_mod.settings_lezen()
check('sleutel niet in /api/settings', 'sleutel' not in gelezen['evconduit'],
      list(gelezen['evconduit'].keys()))
check('wel of er een sleutel staat', gelezen['evconduit']['heeft_sleutel'] is True)

# ── 10. Leeg sleutelveld laat de sleutel staan ────────────────────────────────
bewaard = app_mod._evconduit_bewaren({'url': 'https://a.test', 'sleutel': 'bestaand'},
                                     {'url': 'https://b.test', 'marge_s': '240'})
check('leeg sleutelveld wist niet', bewaard['sleutel'] == 'bestaand', bewaard)
check('marge wordt een getal', bewaard['marge_s'] == 240 and isinstance(bewaard['marge_s'], int))
check('url bijgewerkt', bewaard['url'] == 'https://b.test', bewaard['url'])
try:
    app_mod._evconduit_bewaren({}, {'url': 'javascript:alert(1)'})
    check('onzin-adres geweigerd', False, 'geen fout')
except Exception as exc:
    check('onzin-adres geweigerd', 'http' in str(exc), exc)

con.close()
print()
if fouten:
    print(f'{len(fouten)} mislukt: ' + ', '.join(fouten))
    sys.exit(1)
print('alles goed')
