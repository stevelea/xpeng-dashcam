#!/usr/bin/env python3
"""XPENG dashcam-viewer: bladeren per dag, miniaturen, zoeken op tijd."""
import json
import logging
import mimetypes
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
log = logging.getLogger('xpeng-dashcam')

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import store
import scan as scan_mod
import thumbs as thumbs_mod
import ritten as ritten_mod
import route as route_mod
import fotos as fotos_mod
import evconduit as evconduit_mod

AMS = store.tijdzone()
STATIC = HERE / 'static'
app = FastAPI(title='XPENG dashcam')


class NoCacheStatic(StaticFiles):
    """Zonder dit haalt de browser index.html/app.js niet opnieuw op na een wijziging."""
    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers['Cache-Control'] = 'no-cache'
        return resp


def row_to_clip(r):
    ts = datetime.fromisoformat(r['ts'])
    return {'id': r['id'], 'ts': r['ts'], 'time': ts.strftime('%H:%M:%S'),
            'day': r['day'], 'kind': r['kind'], 'view': r['view'],
            'mb': round(r['bytes'] / 1024 ** 2, 1), 'thumb': bool(r['thumb'])}


# ── Overzicht ─────────────────────────────────────────────────────────────────
@app.get('/api/overview')
def overview():
    con = store.connect()
    totals = con.execute(
        'SELECT count(*) n, sum(bytes) b, sum(thumb) t, min(day) f, max(day) l FROM clips'
    ).fetchone()
    per_kind = {r['kind']: r['n'] for r in
                con.execute('SELECT kind, count(*) n FROM clips GROUP BY kind')}
    days = [dict(r) for r in con.execute(
        'SELECT day, count(*) n, sum(bytes) b, '
        "sum(CASE WHEN kind='noodgeval' THEN 1 ELSE 0 END) noodgeval "
        'FROM clips GROUP BY day ORDER BY day DESC')]
    scanned = store.get_meta(con, 'scanned_utc')
    con.close()
    for d in days:
        d['gb'] = round((d['b'] or 0) / 1024 ** 3, 2)
        del d['b']
    return {'clips': totals['n'], 'gb': round((totals['b'] or 0) / 1024 ** 3, 1),
            'thumbs': totals['t'] or 0, 'first_day': totals['f'], 'last_day': totals['l'],
            'per_kind': per_kind, 'days': days, 'scanned_utc': scanned}


@app.get('/api/day/{day}')
def day(day: str, kind: str = 'alle'):
    con = store.connect()
    sql = 'SELECT * FROM clips WHERE day = ?'
    args = [day]
    if kind != 'alle':
        sql += ' AND kind = ?'
        args.append(kind)
    rows = con.execute(sql + ' ORDER BY ts, view', args).fetchall()
    con.close()

    moments = {}
    for r in rows:
        m = moments.setdefault(r['ts'], {'ts': r['ts'], 'time': r['ts'][11:19],
                                         'kind': r['kind'], 'views': {}})
        m['views'][r['view']] = row_to_clip(r)
    return {'day': day, 'moments': sorted(moments.values(), key=lambda x: x['ts'])}


@app.get('/api/search')
def search(ts: str, window_min: int = 30):
    """Clips rond een tijdstip. Verwacht 'JJJJ-MM-DD HH:MM' of 'JJJJ-MM-DDTHH:MM'."""
    try:
        want = datetime.fromisoformat(ts.replace(' ', 'T'))
    except ValueError:
        raise HTTPException(400, 'tijd niet begrepen, gebruik JJJJ-MM-DD UU:MM')
    if want.tzinfo is None:
        want = want.replace(tzinfo=AMS)
    lo = (want - timedelta(minutes=window_min)).isoformat(timespec='seconds')
    hi = (want + timedelta(minutes=window_min)).isoformat(timespec='seconds')
    con = store.connect()
    rows = con.execute('SELECT * FROM clips WHERE ts BETWEEN ? AND ? ORDER BY ts, view',
                       (lo, hi)).fetchall()
    con.close()
    moments = {}
    for r in rows:
        m = moments.setdefault(r['ts'], {'ts': r['ts'], 'time': r['ts'][11:19],
                                         'day': r['day'], 'kind': r['kind'], 'views': {}})
        m['views'][r['view']] = row_to_clip(r)
    return {'gezocht': want.isoformat(timespec='minutes'),
            'moments': sorted(moments.values(), key=lambda x: x['ts'])}


# ── Bestanden ─────────────────────────────────────────────────────────────────
def clip_row(cid):
    con = store.connect()
    r = con.execute('SELECT * FROM clips WHERE id = ?', (cid,)).fetchone()
    con.close()
    if not r:
        raise HTTPException(404, 'clip niet gevonden')
    return r


@app.get('/thumb/{cid}')
def thumb(cid: str):
    p = thumbs_mod.thumb_path(cid)
    if not p.exists():
        raise HTTPException(404, 'nog geen miniatuur')
    return FileResponse(p, media_type='image/jpeg',
                        headers={'Cache-Control': 'public, max-age=604800'})


@app.get('/video/{cid}')
def video(cid: str, request: Request):
    """Met bereik-ondersteuning, anders kan de speler niet vooruitspoelen."""
    r = clip_row(cid)
    path = Path(r['path'])
    if not path.exists():
        raise HTTPException(404, 'bestand niet bereikbaar — is de share gekoppeld?')
    size = path.stat().st_size
    media = mimetypes.guess_type(path.name)[0] or 'video/mp4'
    rng = request.headers.get('range')

    if not rng:
        return FileResponse(path, media_type=media,
                            headers={'Accept-Ranges': 'bytes', 'Content-Length': str(size)})

    unit, _, spec = rng.partition('=')
    start_s, _, end_s = spec.partition('-')
    try:
        start = int(start_s) if start_s else 0
        end = int(end_s) if end_s else size - 1
    except ValueError:
        raise HTTPException(416, 'bereik niet begrepen')
    start = max(0, start)
    end = min(end, size - 1)
    if unit.strip() != 'bytes' or start > end:
        return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})

    length = end - start + 1

    def chunks(block=1024 * 512):
        with open(path, 'rb') as f:
            f.seek(start)
            left = length
            while left > 0:
                data = f.read(min(block, left))
                if not data:
                    break
                left -= len(data)
                yield data

    return StreamingResponse(chunks(), status_code=206, media_type=media, headers={
        'Content-Range': f'bytes {start}-{end}/{size}',
        'Accept-Ranges': 'bytes',
        'Content-Length': str(length),
    })


@app.get('/download/{cid}')
def download(cid: str):
    r = clip_row(cid)
    path = Path(r['path'])
    if not path.exists():
        raise HTTPException(404, 'bestand niet bereikbaar')
    return FileResponse(path, media_type='video/mp4', filename=path.name)


# ── Onderhoud ─────────────────────────────────────────────────────────────────
@app.post('/api/scan')
def api_scan():
    try:
        return scan_mod.scan(verbose=False)
    except SystemExit as exc:
        raise HTTPException(503, str(exc))


@app.get('/api/thumb-progress')
def thumb_progress():
    con = store.connect()
    r = con.execute('SELECT count(*) n, sum(thumb) t FROM clips').fetchone()
    con.close()
    return {'clips': r['n'], 'klaar': r['t'] or 0}


# ── Ritten ────────────────────────────────────────────────────────────────────
def trip_dict(r):
    return {'id': r['id'], 'day': r['day'],
            'start': r['start_ts'], 'end': r['end_ts'],
            'start_time': r['start_ts'][11:16], 'end_time': r['end_ts'][11:16],
            'clips': r['clips'], 'minutes': round(r['seconds'] / 60),
            'km': r['km'], 'measured': r['measured'], 'note': r['note']}


@app.get('/api/trips/{day}')
def api_trips(day: str):
    con = store.connect()
    rows = con.execute('SELECT * FROM trips WHERE day = ? ORDER BY start_ts', (day,)).fetchall()
    wp = {r['trip_id']: r['n'] for r in con.execute(
        'SELECT trip_id, count(*) n FROM waypoints GROUP BY trip_id')}
    con.close()
    out = []
    for r in rows:
        d = trip_dict(r)
        d['waypoints'] = wp.get(r['id'], 0)
        out.append(d)
    return {'day': day, 'trips': out}


@app.get('/api/trips/{day}/auto')
def api_trips_auto(day: str):
    """De afstand van de auto per rit van deze dag, voor de ritttegels.

    Alleen voor ritten waar wij zelf nog geen kilometers hebben gemeten; de tegel
    laat onze eigen meting staan als die er is. De rittenlijst van EVConduit wordt
    hier één keer opgehaald en niet per rit — zie evconduit.koppel_veel.
    """
    con = store.connect()
    rows = con.execute('SELECT * FROM trips WHERE day = ? ORDER BY start_ts', (day,)).fetchall()
    try:
        auto = evconduit_mod.dag_auto(con, [dict(r) for r in rows])
    except Exception as exc:                 # een externe dienst mag de dag niet breken
        auto = {}
        log.warning('EVConduit-dagoverzicht mislukt: %s', exc)
    finally:
        con.close()
    return {'day': day, 'auto': auto}


@app.get('/api/trip/{trip_id}')
def api_trip(trip_id: int):
    con = store.connect()
    r = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not r:
        con.close()
        raise HTTPException(404, 'rit niet gevonden')
    d = trip_dict(r)
    d['waypoints'] = [dict(w) for w in con.execute(
        'SELECT ts, lat, lon, label, source FROM waypoints WHERE trip_id = ? ORDER BY ts',
        (trip_id,))]
    for w in d['waypoints']:
        w['time'] = w['ts'][11:16]
    d['speed'] = [dict(x) for x in con.execute(
        'SELECT c.ts, s.offset_s, s.kmh FROM speeds s JOIN clips c ON c.id = s.clip_id '
        "WHERE c.ts BETWEEN ? AND ? AND c.view='front' ORDER BY c.ts, s.offset_s",
        (r['start_ts'], r['end_ts']))]
    con.close()
    return d


@app.get('/api/trip/{trip_id}/fragmenten')
def api_fragmenten(trip_id: int):
    """De clips van een rit als strip: tijd, snelheid en miniatuur."""
    con = store.connect()
    t = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not t:
        con.close()
        raise HTTPException(404, 'rit niet gevonden')
    rows = con.execute(
        'SELECT * FROM clips WHERE ts BETWEEN ? AND ? ORDER BY ts, view',
        (t['start_ts'], t['end_ts'])).fetchall()
    snelheden = {}
    for r in con.execute(
            'SELECT s.clip_id, avg(s.kmh) g, max(s.kmh) m FROM speeds s '
            'JOIN clips c ON c.id = s.clip_id WHERE c.ts BETWEEN ? AND ? GROUP BY s.clip_id',
            (t['start_ts'], t['end_ts'])):
        snelheden[r['clip_id']] = (round(r['g']), round(r['m']))
    con.close()

    momenten = {}
    for r in rows:
        m = momenten.setdefault(r['ts'], {'ts': r['ts'], 'time': r['ts'][11:19],
                                          'kind': r['kind'], 'views': {}})
        s_ = snelheden.get(r['id'])
        m['views'][r['view']] = {'id': r['id'], 'thumb': bool(r['thumb']),
                                 'mb': round(r['bytes'] / 1024 ** 2, 1)}
        if s_ and 'kmh' not in m:
            m['kmh'], m['kmh_max'] = s_
    return {'trip': trip_dict(t),
            'fragmenten': sorted(momenten.values(), key=lambda x: x['ts'])}


@app.get('/api/trip/{trip_id}/route')
def api_route(trip_id: int):
    con = store.connect()
    r = con.execute('SELECT * FROM routes WHERE trip_id = ?', (trip_id,)).fetchone()
    punten = [dict(w) for w in con.execute(
        'SELECT ts, lat, lon, label, source FROM waypoints WHERE trip_id = ? ORDER BY ts',
        (trip_id,))]
    con.close()
    if not r:
        return {'soort': None, 'geojson': None, 'punten': punten}
    return {'soort': r['soort'], 'km': r['km'], 'aantal': r['punten'],
            'bijgewerkt': r['bijgewerkt'],
            'geojson': json.loads(r['geojson']) if r['geojson'] else None,
            'punten': punten}


@app.post('/api/trip/{trip_id}/route')
def api_route_bouw(trip_id: int):
    try:
        return route_mod.bouw(trip_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


# ── Wat de auto zelf van de rit weet (EVConduit) ──────────────────────────────
@app.get('/api/trip/{trip_id}/auto')
def api_trip_auto(trip_id: int):
    """De gegevens van de auto bij deze rit, plus het gereden spoor als er een is.

    Gekoppeld op tijd, niet op nummer: zie de uitleg bovenin evconduit.py. Wat we
    eerder ophaalden komt uit de cache; een POST haalt het opnieuw op.
    """
    con = store.connect()
    r = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not r:
        con.close()
        raise HTTPException(404, 'rit niet gevonden')
    try:
        d = evconduit_mod.koppel(con, r)
    finally:
        con.close()
    d['trip'] = trip_dict(r)
    return d


@app.post('/api/trip/{trip_id}/auto')
def api_trip_auto_ververs(trip_id: int):
    con = store.connect()
    r = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not r:
        con.close()
        raise HTTPException(404, 'rit niet gevonden')
    try:
        d = evconduit_mod.koppel(con, r, forceer=True)
    finally:
        con.close()
    d['trip'] = trip_dict(r)
    return d


@app.delete('/api/trip/{trip_id}/auto')
def api_trip_auto_vergeet(trip_id: int):
    """De koppeling weggooien. Nodig als een rit opnieuw is ingedeeld."""
    con = store.connect()
    r = con.execute('SELECT start_ts FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not r:
        con.close()
        raise HTTPException(404, 'rit niet gevonden')
    evconduit_mod.vergeet(con, r['start_ts'])
    con.close()
    return {'ok': True}


@app.get('/api/evconduit/status')
def api_evconduit_status():
    con = store.connect()
    try:
        return evconduit_mod.status(con)
    finally:
        con.close()


@app.post('/api/evconduit/toets')
async def api_evconduit_toets(request: Request):
    """Testen met wat er in het formulier staat, nog voordat het bewaard is.

    POST en geen GET: in een query string zou de sleutel in het logboek van deze
    server én van elke proxy daarvoor terechtkomen.
    """
    try:
        binnen = await request.json()
    except Exception:
        binnen = {}
    if not isinstance(binnen, dict):
        binnen = {}
    return evconduit_mod.toets(url=(binnen.get('url') or '').strip(),
                               sleutel=(binnen.get('sleutel') or '').strip())


@app.post('/api/evconduit/vergeet')
def api_evconduit_vergeet():
    con = store.connect()
    try:
        evconduit_mod.vergeet(con)
    finally:
        con.close()
    return {'ok': True}


@app.get('/api/routes')
def api_routes():
    """Alle ritten waarvan een route bekend is, met de plaatsen die erbij horen."""
    con = store.connect()
    rows = con.execute(
        'SELECT r.trip_id, r.soort, r.km, r.punten, t.day, t.start_ts, t.end_ts, t.km AS trip_km '
        'FROM routes r JOIN trips t ON t.id = r.trip_id '
        'WHERE r.geojson IS NOT NULL ORDER BY t.start_ts DESC').fetchall()
    uit = []
    for r in rows:
        namen = [w['label'] for w in con.execute(
            'SELECT DISTINCT label FROM waypoints WHERE trip_id = ? AND label IS NOT NULL '
            'ORDER BY ts', (r['trip_id'],)) if w['label']]
        kort = []
        for n in namen:
            plaats = n.split(',')[-1].strip() if ',' in n else n
            if plaats not in kort:
                kort.append(plaats)
        uit.append({'trip_id': r['trip_id'], 'day': r['day'],
                    'start_time': r['start_ts'][11:16], 'end_time': r['end_ts'][11:16],
                    'soort': r['soort'], 'km': r['km'], 'punten': r['punten'],
                    'trip_km': r['trip_km'],
                    'plaatsen': ' → '.join(kort[:4])})
    con.close()
    return {'routes': uit}


@app.post('/api/trips/rebuild')
def api_trips_rebuild():
    return {'trips': ritten_mod.build()}


@app.post('/api/trip/{trip_id}/measure')
def api_trip_measure(trip_id: int):
    cfg = cfg_trips()
    try:
        return ritten_mod.measure(trip_id, every=cfg['sample_every'], workers=cfg['workers'])
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.post('/api/trip/{trip_id}/photos')
def api_trip_photos(trip_id: int):
    margin = store.load_config().get('photos', {}).get('margin_min', 20)
    try:
        return {'punten': fotos_mod.link_trip(trip_id, margin_min=margin)}
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.post('/api/trip/{trip_id}/waypoint')
def api_trip_waypoint(trip_id: int, query: str = '', lat: float = None,
                      lon: float = None, label: str = '', ts: str = ''):
    """Punt met de hand toevoegen: op naam (wordt opgezocht) of op coordinaat."""
    import httpx
    con = store.connect()
    t = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not t:
        con.close()
        raise HTTPException(404, 'rit niet gevonden')
    naam = label
    if lat is None or lon is None:
        if not query:
            con.close()
            raise HTTPException(400, 'geef een plaatsnaam of een coordinaat')
        try:
            r = httpx.get('https://nominatim.openstreetmap.org/search',
                          params={'q': query, 'format': 'jsonv2', 'limit': 1,
                                  'accept-language': 'nl'},
                          headers={'User-Agent': 'xpeng-dashcam/1.0 (persoonlijk)'},
                          timeout=15)
            r.raise_for_status()
            hits = r.json()
        except Exception as exc:
            con.close()
            raise HTTPException(502, f'opzoeken mislukt: {exc}')
        if not hits:
            con.close()
            raise HTTPException(404, f'niets gevonden voor "{query}"')
        lat, lon = float(hits[0]['lat']), float(hits[0]['lon'])
        naam = naam or hits[0]['display_name'].split(',')[0]
    con.execute('INSERT OR REPLACE INTO waypoints (trip_id, ts, lat, lon, label, source) '
                'VALUES (?,?,?,?,?,?)',
                (trip_id, ts or t['start_ts'], lat, lon, naam, 'handmatig'))
    con.commit()
    con.close()
    return {'lat': lat, 'lon': lon, 'label': naam}


@app.delete('/api/trip/{trip_id}/waypoint')
def api_trip_waypoint_del(trip_id: int, ts: str, source: str = 'handmatig'):
    con = store.connect()
    con.execute('DELETE FROM waypoints WHERE trip_id = ? AND ts = ? AND source = ?',
                (trip_id, ts, source))
    con.commit()
    con.close()
    return {'ok': True}


def cfg_trips():
    c = store.load_config().get('trips', {})
    return {'sample_every': c.get('sample_every', 5), 'workers': c.get('workers', 6)}


@app.get('/api/locaties')
def api_locaties(van: str = '', tot: str = ''):
    """Alle bekende punten, eventueel begrensd op datum."""
    con = store.connect()
    sql = ('SELECT w.ts, w.lat, w.lon, w.label, w.source, w.trip_id, t.day, t.km '
           'FROM waypoints w JOIN trips t ON t.id = w.trip_id')
    args, waar = [], []
    if van:
        waar.append('t.day >= ?'); args.append(van)
    if tot:
        waar.append('t.day <= ?'); args.append(tot)
    if waar:
        sql += ' WHERE ' + ' AND '.join(waar)
    rows = con.execute(sql + ' ORDER BY w.ts', args).fetchall()
    grens = con.execute('SELECT min(day), max(day) FROM trips').fetchone()
    con.close()
    return {'punten': [dict(r) for r in rows],
            'eerste_dag': grens[0], 'laatste_dag': grens[1]}


@app.post('/api/locaties/zoek-fotos')
def api_locaties_zoek(geocode: bool = True):
    margin = store.load_config().get('photos', {}).get('margin_min', 20)
    return fotos_mod.link_all(margin_min=margin, geocode=geocode)


@app.get('/api/spoor')
def api_spoor(van: str, tot: str, bron: str = ''):
    """Haalt het gereden spoor op bij de locatie-logger op de server."""
    import httpx
    basis = store.load_config().get('logger', {}).get('url')
    if not basis:
        raise HTTPException(503, 'geen locatie-logger ingesteld')
    try:
        r = httpx.get(basis.rstrip('/') + '/api/track',
                      params={'van': van, 'tot': tot, 'bron': bron}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        raise HTTPException(502, f'logger niet bereikbaar: {exc}')


@app.get('/api/settings')
def settings_lezen():
    """Alleen de velden die een gebruiker zelf mag zetten. Geen tokens, geen paden
    naar andere diensten."""
    cfg = store.load_config()
    ev = cfg.get('evconduit') or {}
    return {
        'root': cfg.get('root', ''),
        'folders': cfg.get('folders', {}),
        'timezone': cfg.get('timezone', 'Europe/Amsterdam'),
        'primary_view': (cfg.get('views') or {}).get('primary', 'front'),
        'port': (cfg.get('web') or {}).get('port'),
        # De sleutel gaat er NOOIT uit, ook niet terug naar de eigen pagina. Alleen
        # of hij er is, zodat het formulier kan zeggen "er staat een sleutel" zonder
        # hem te tonen.
        'evconduit': {'url': ev.get('url', ''), 'marge_s': ev.get('marge_s', 180),
                      'aan': bool(ev.get('aan', True)),
                      'heeft_sleutel': bool((ev.get('sleutel') or '').strip())},
    }


@app.get('/api/settings/check')
def settings_toetsen(root: str, folders: str = ''):
    """Kijkt of de opgegeven map bestaat en hoeveel bruikbare clips erin zitten.
    Zo ziet iemand meteen of hij de juiste map koos, nog voor hij bewaart."""
    pad = Path(root).expanduser()
    if not pad.exists():
        return {'ok': False, 'reden': 'map bestaat niet', 'pad': str(pad)}
    if not pad.is_dir():
        return {'ok': False, 'reden': 'dit is geen map', 'pad': str(pad)}
    namen = [f.strip() for f in folders.split(',') if f.strip()]
    bases = [pad / n for n in namen if (pad / n).exists()] or [pad]
    gevonden = herkend = 0
    for base in bases:
        for f in base.rglob('*.mp4'):
            gevonden += 1
            if store.parse_name(f.name):
                herkend += 1
            if gevonden >= 2000:      # genoeg om het te weten; niet de hele schijf lezen
                break
        if gevonden >= 2000:
            break
    return {
        'ok': herkend > 0,
        'pad': str(pad),
        'submappen': [b.name for b in bases if b != pad],
        'mp4_gezien': gevonden,
        'herkend': herkend,
        'reden': '' if herkend else 'wel mp4-bestanden, maar geen herkende namen',
    }


@app.post('/api/settings')
async def settings_bewaren(request: Request):
    binnen = await request.json()
    cfg = dict(store.load_config())

    root = (binnen.get('root') or '').strip()
    if root:
        pad = Path(root).expanduser()
        if not pad.is_dir():
            raise HTTPException(400, f'{pad} is geen bestaande map')
        cfg['root'] = str(pad)

    tz = (binnen.get('timezone') or '').strip()
    if tz:
        try:
            ZoneInfo(tz)
        except Exception:
            raise HTTPException(400, f'onbekende tijdzone: {tz}')
        cfg['timezone'] = tz

    mappen = binnen.get('folders')
    if isinstance(mappen, dict) and mappen:
        cfg['folders'] = {k: str(v) for k, v in mappen.items() if str(v).strip()}

    hoofd = (binnen.get('primary_view') or '').strip().lower()
    if hoofd:
        cfg['views'] = {**(cfg.get('views') or {}), 'primary': hoofd}

    ev = binnen.get('evconduit')
    if isinstance(ev, dict):
        cfg['evconduit'] = _evconduit_bewaren(cfg.get('evconduit') or {}, ev)

    store.save_config(cfg)
    return settings_lezen()


def _waar(waarde):
    """Een vinkje komt als boolean, maar uit een formulier ook als 'true' of 'aan'."""
    if isinstance(waarde, bool):
        return waarde
    return str(waarde).strip().lower() in ('1', 'true', 'ja', 'aan', 'on', 'yes')


def _evconduit_bewaren(oud, nieuw):
    """De EVConduit-instellingen bijwerken zonder de bewaarde sleutel te verliezen.

    Een leeg sleutelveld betekent "laat staan", niet "wissen". Anders moet je het
    token opnieuw plakken zodra je alleen de marge verzet. Wissen kan met
    `sleutel_wis`, zodat het een bewuste handeling is.
    """
    uit = dict(oud)
    if 'url' in nieuw:
        url = (nieuw.get('url') or '').strip().rstrip('/')
        if url and not url.startswith(('http://', 'https://')):
            raise HTTPException(400, 'het adres moet met http:// of https:// beginnen')
        uit['url'] = url
    if (nieuw.get('sleutel') or '').strip():
        uit['sleutel'] = nieuw['sleutel'].strip()
    if nieuw.get('sleutel_wis'):
        uit['sleutel'] = ''
    if 'marge_s' in nieuw:
        try:
            uit['marge_s'] = max(0, min(int(nieuw['marge_s']), 3600))
        except (TypeError, ValueError):
            raise HTTPException(400, 'de marge moet een aantal seconden zijn')
    if 'aan' in nieuw:
        uit['aan'] = _waar(nieuw['aan'])
    return uit


@app.get('/healthz')
def healthz():
    return {'ok': True}


@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html', headers={'Cache-Control': 'no-cache'})


app.mount('/', NoCacheStatic(directory=STATIC), name='static')
