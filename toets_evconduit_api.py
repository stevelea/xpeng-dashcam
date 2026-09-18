#!/usr/bin/env python3
"""De hele weg: van het HTTP-eindpunt tot het antwoord dat de pagina tekent.

Draaien:  PYTHONPATH=<map met fastapi+httpx> python3 toets_evconduit_api.py

De eenheidstoetsen hiernaast kijken naar het koppelen. Deze kijkt naar de bedrading
eromheen: komt de sleutel het scherm op, overleeft hij een keer bewaren zonder dat
je hem opnieuw intypt, en staat de afstand van de auto echt NAST die van ons.
"""
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import store

TMP = Path(tempfile.mkdtemp())
store.DB_PATH = TMP / 'api.db'
store.HERE = TMP                       # config.json gaat naar de temp, niet de repo
store._config = {'timezone': 'Europe/Amsterdam',
                 'evconduit': {'url': '', 'sleutel': '', 'marge_s': 180, 'aan': True}}

import evconduit
import app as app_mod
from fastapi.testclient import TestClient

fouten = []


def check(label, ok, detail=''):
    print(f"{'OK  ' if ok else 'FOUT'}  {label}{'  — ' + str(detail) if detail else ''}")
    if not ok:
        fouten.append(label)


RIJEN = [{'id': 'uuid-a', 'vin': 'L1NSPGHB1PA000001',
          'started_at': '2026-09-14T12:23:14Z', 'ended_at': '2026-09-14T12:41:22Z',
          'duration_seconds': 1088, 'distance_km': 14.1, 'energy_kwh': 2.4,
          'max_speed_kmh': 112, 'mean_moving_speed_kmh': 47,
          'odometer_start': 12000, 'odometer_end': 12014,
          'soc_start': 71, 'soc_end': 66, 'regen_kwh': 0.4,
          'user_id': 'mag-niet-door', 'export_id': 'ook-niet'}]

SPOOR = {'available': True, 'reason': None, 'seconds': [0, 60, 120],
         'lat': [52.1, 52.2, 52.3], 'lon': [5.1, 5.2, 5.3], 'point_count': 3,
         'source_point_count': 900, 'coverage': 0.87, 'covered_seconds': 940,
         'trip_seconds': 1080, 'largest_gap_seconds': 42, 'track_distance_km': 13.8,
         'window': {'from': 'a', 'to': 'b'}}

gezien = []


def nep_get(url, params=None, headers=None, timeout=None):
    gezien.append({'url': url, 'headers': headers or {}, 'params': params or {}})
    class R:
        status_code = 200
        def json(self):
            return {'trips': RIJEN} if url.endswith('/user/xpeng/trips') else SPOOR
    return R()


evconduit.httpx.get = nep_get
cli = TestClient(app_mod.app)

# ── Een rit in de index zetten ────────────────────────────────────────────────
con = store.connect()
con.execute("INSERT INTO trips (day, start_ts, end_ts, clips, seconds, km, measured, note) "
            "VALUES ('2026-09-14','2026-09-14T14:23:00','2026-09-14T14:41:00',10,1080,14.3,10,NULL)")
con.commit()
trip_id = con.execute('SELECT id FROM trips').fetchone()['id']

# ── 1. Niets ingesteld: geen gegevens, geen crash ─────────────────────────────
r = cli.get(f'/api/trip/{trip_id}/auto')
check('onbekende rit geeft 404', cli.get('/api/trip/99999/auto').status_code == 404)
check('niet ingesteld antwoordt netjes', r.status_code == 200 and r.json()['reden'] == 'geen_evconduit',
      r.json().get('reden'))

# ── 2. Instellingen bewaren, sleutel erin ─────────────────────────────────────
r = cli.post('/api/settings', json={
    'root': str(TMP),
    'evconduit': {'url': 'https://voorbeeld.test/', 'sleutel': 'geheime-sleutel',
                  'marge_s': '240', 'aan': True},
})
check('bewaren lukt', r.status_code == 200, r.status_code)
body = r.json()
check('sleutel staat NIET in het antwoord', 'sleutel' not in body['evconduit'],
      list(body['evconduit'].keys()))
check('wel dat er een sleutel is', body['evconduit']['heeft_sleutel'] is True)
check('url zonder sluithaak', body['evconduit']['url'] == 'https://voorbeeld.test',
      body['evconduit']['url'])
check('marge als getal bewaard', store.load_config()['evconduit']['marge_s'] == 240,
      store.load_config()['evconduit']['marge_s'])

# ── 3. Tweede keer bewaren zonder de sleutel opnieuw in te typen ──────────────
cli.post('/api/settings', json={'root': str(TMP),
                                'evconduit': {'url': 'https://voorbeeld.test', 'sleutel': ''}})
check('sleutel overleeft een leeg veld',
      store.load_config()['evconduit']['sleutel'] == 'geheime-sleutel')

# ── 4. De gegevens van de auto komen eraan ────────────────────────────────────
gezien.clear()
r = cli.get(f'/api/trip/{trip_id}/auto')
d = r.json()
check('rit gevonden via het eindpunt', d['beschikbaar'], d.get('reden'))
check('onze eigen rit reist mee', d['trip']['km'] == 14.3, d['trip'].get('km'))
check('afstand van de auto', d['rit']['distance_km'] == 14.1)
check('klokverschil aanwezig', d['afwijking'] == {'start_s': 14, 'eind_s': 22}, d.get('afwijking'))
check('privevelden eruit', 'user_id' not in d['rit'] and 'export_id' not in d['rit'])
check('spoor met GeoJSON', d['spoor']['geojson']['coordinates'][0] == [5.1, 52.1],
      d['spoor']['geojson']['coordinates'][0])
check('spoor vraagt om de marge uit de instellingen',
      gezien[-1]['params'].get('pad_seconds') == 240, gezien[-1]['params'])
check('sleutel gaat als Bearer mee',
      gezien[-1]['headers'].get('Authorization') == 'Bearer geheime-sleutel')
check('adres krijgt /api ervoor',
      gezien[-1]['url'].startswith('https://voorbeeld.test/api/user/xpeng/trips'),
      gezien[-1]['url'])

# ── 5. Tweede keer komt uit de cache ─────────────────────────────────────────
gezien.clear()
cli.get(f'/api/trip/{trip_id}/auto')
check('tweede keer geen verkeer naar buiten', gezien == [], len(gezien))

# ── 6. Verversen haalt het wel opnieuw op ────────────────────────────────────
gezien.clear()
cli.post(f'/api/trip/{trip_id}/auto')
check('verversen belt EVConduit weer', len(gezien) == 2, len(gezien))

# ── 7. Verbinding testen met wat in het formulier staat ──────────────────────
gezien.clear()
r = cli.post('/api/evconduit/toets', json={'url': 'https://ander.test', 'sleutel': 'tijdelijk'})
check('toets zegt hoeveel ritten', r.json().get('ok') and r.json().get('ritten') == 1, r.json())
check('toets gebruikt het ingetypte adres, niet het bewaarde',
      gezien[0]['url'].startswith('https://ander.test/api/'), gezien[0]['url'])
check('en de ingetypte sleutel',
      gezien[0]['headers'].get('Authorization') == 'Bearer tijdelijk')
r = cli.post('/api/evconduit/toets', json={})
check('toets zonder invoer gebruikt het bewaarde adres',
      gezien[-1]['url'].startswith('https://voorbeeld.test/api/'), gezien[-1]['url'])

# ── 8. Vergeten en opnieuw opbouwen ──────────────────────────────────────────
cli.post('/api/evconduit/vergeet')
r = cli.get('/api/evconduit/status')
check('status telt niets meer', r.json()['geprobeerd'] == 0, r.json())
check('status verklapt de sleutel niet', 'sleutel' not in r.json(), list(r.json().keys()))
check('status zegt wel dat er een sleutel is', r.json()['heeft_sleutel'] is True)

# ── 9. Uitzetten verbergt ook de cache ───────────────────────────────────────
cli.get(f'/api/trip/{trip_id}/auto')                      # vult de cache
cli.post('/api/settings', json={'evconduit': {'aan': False}})
d = cli.get(f'/api/trip/{trip_id}/auto').json()
check('uitgeschakeld geeft geen gegevens', d['reden'] == 'geen_evconduit', d['reden'])
cli.post('/api/settings', json={'evconduit': {'aan': True}})
d = cli.get(f'/api/trip/{trip_id}/auto').json()
check('weer aan: cache nog intact', d['beschikbaar'], d.get('reden'))

# ── 10. Een sleutel in de query string wordt niet geaccepteerd ───────────────
# De statische mount achteraan vangt alles wat geen route is, dus dit wordt een 404
# en geen 405. Waar het om gaat is dat de sleutel langs deze weg niet werkt.
r = cli.get('/api/evconduit/toets?sleutel=lekkage')
check('toets is geen GET: sleutel in de query string werkt niet',
      r.status_code != 200, r.status_code)

# ── 11. De ritttegels: de afstand van de auto per rit ────────────────────────
r = cli.get('/api/trips/2026-09-14/auto')
d = r.json()
check('dag-eindpunt antwoordt', r.status_code == 200 and d['day'] == '2026-09-14', r.status_code)
check('sleutelt op ons eigen ritnummer', str(trip_id) in d['auto'], list(d['auto']))
check('geeft de afstand van de auto', d['auto'][str(trip_id)]['km'] == 14.1, d['auto'])
check('en of de koppeling zeker is', d['auto'][str(trip_id)]['zeker'] is True)
check('een dag zonder ritten geeft een leeg overzicht',
      cli.get('/api/trips/2020-01-01/auto').json()['auto'] == {})

# ── 12. Een onbereikbaar EVConduit mag de dag niet breken ────────────────────
def nep_stuk(url, params=None, headers=None, timeout=None):
    raise RuntimeError('netwerk stuk')


bewaard = evconduit.httpx.get
evconduit.httpx.get = nep_stuk
try:
    evconduit.vergeet(con)                     # anders antwoordt de cache
    r = cli.get('/api/trips/2026-09-14/auto')
    d = r.json()
    check('onbereikbaar geeft nog steeds 200', r.status_code == 200, r.status_code)
    check('en geen afstand in plaats van een fout',
          d['auto'].get(str(trip_id), {}).get('km') is None, d['auto'].get(str(trip_id)))
    # De rittitellijst zelf mag hier niet door omvallen; dat is de kern van de dag.
    check('de ritten van de dag komen er nog wel',
          len(cli.get('/api/trips/2026-09-14').json()['trips']) == 1)
    check('een rit openen meldt onbereikbaar, geen crash',
          cli.get(f'/api/trip/{trip_id}/auto').json()['reden'] == 'onbereikbaar')
finally:
    evconduit.httpx.get = bewaard

# ── 13. Een link met van/tot wijst de rit zelf aan, geen zoekvenster ─────────
# docs/xpeng-camera.md §1: van/tot is het venster van de rit van de auto, als
# muurklok in onze eigen zone op deze dag (hier 14:23 lokaal = 12:23 UTC).
cli.post('/api/settings', json={'evconduit': {'marge_s': 180}})
r = cli.get('/api/trips/2026-09-14/bij', params={'van': '14:23:00', 'tot': '14:41:00'})
d = r.json()
check('van/tot wijst onze rit aan', r.status_code == 200 and d['trip'] == trip_id, d)
check('met de dekking erbij', d.get('dekking') == 1.0, d.get('dekking'))

d = cli.get('/api/trips/2026-09-14/bij',
            params={'van': '14:24:30', 'tot': '14:42:00'}).json()
check('een kleine klokafwijking past nog', d['trip'] == trip_id, d)
check('en de afwijking wordt gemeld', d.get('start_afwijking_s') == 90, d)

d = cli.get('/api/trips/2026-09-14/bij',
            params={'van': '18:00:00', 'tot': '18:10:00'}).json()
check('geen rit op dat moment geeft trip: null', d['trip'] is None, d)

d = cli.get('/api/trips/2026-09-14/bij',
            params={'van': 'niet-een-tijd', 'tot': '14:41:00'}).json()
check('een onbruikbare link geeft geen treffer in plaats van een fout',
      d['trip'] is None, d)

check('een dag zonder ritten geeft ook niets',
      cli.get('/api/trips/2020-01-01/bij',
              params={'van': '14:23:00', 'tot': '14:41:00'}).json()['trip'] is None)

con.close()
print()
if fouten:
    print(f'{len(fouten)} mislukt: ' + ', '.join(fouten))
    sys.exit(1)
print('alles goed')
