#!/usr/bin/env python3
"""XPENG dashcam-viewer: bladeren per dag, miniaturen, zoeken op tijd."""
import json
import mimetypes
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import store
import scan as scan_mod
import thumbs as thumbs_mod
import ritten as ritten_mod
import route as route_mod
import fotos as fotos_mod
import fragment as fragment_mod
import remmen as remmen_mod
import weer as weer_mod

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


def bestand_sturen(path, request, download=False):
    """Met bereik-ondersteuning, anders kan de speler niet vooruitspoelen."""
    path = Path(path)
    if not path.exists():
        raise HTTPException(404, 'bestand niet bereikbaar — is de share gekoppeld?')
    if download:
        return FileResponse(path, media_type='video/mp4', filename=path.name)
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


@app.get('/video/{cid}')
def video(cid: str, request: Request):
    return bestand_sturen(clip_row(cid)['path'], request)


# ── Remmomenten en fragmenten ─────────────────────────────────────────────────
def _views(films):
    uit = {}
    for view, pad in films.items():
        p = Path(pad)
        uit[view] = {'url': f'fragment/{p.name}',
                     'mb': round(p.stat().st_size / 1024 ** 2, 1) if p.exists() else 0}
    return uit


@app.get('/api/remmen')
def api_remmen():
    con = remmen_mod.connect()
    rows = con.execute('SELECT r.*, c.thumb FROM remmomenten r LEFT JOIN clips c ON c.id = r.clip_id '
                       'ORDER BY r.ts DESC').fetchall()
    con.close()
    uit = []
    for r in rows:
        views = _views(json.loads(r['films'] or '{}'))
        for v in views.values():           # miniatuur van de clip waarin het remmen begint
            v.update(id=r['clip_id'], thumb=bool(r['thumb']))
        uit.append({'id': r['id'], 'ts': r['ts'], 'day': r['day'], 'time': r['ts'][11:19],
                    'kind': 'rem', 'van_kmh': r['van_kmh'], 'naar_kmh': r['naar_kmh'],
                    'daling': r['daling'], 'views': views})
    con = remmen_mod.connect()
    maanden = [r[0] for r in con.execute(
        'SELECT DISTINCT substr(c.day, 1, 7) FROM snelheid_fijn_gelezen g '
        'JOIN clips c ON c.id = g.clip_id ORDER BY 1')]
    con.close()
    return {'momenten': uit, 'maanden': maanden}


@app.post('/api/fragment')
async def api_fragment(request: Request):
    """Exporteert voor, na seconden rond ts (+ offset in seconden), voor elk camerabeeld."""
    body = await request.json()
    try:
        moment = datetime.fromisoformat(body['ts']) + timedelta(seconds=float(body.get('offset', 0)))
    except (KeyError, ValueError):
        raise HTTPException(400, 'ts ontbreekt of klopt niet')
    moment = moment.replace(microsecond=0)
    voor, na = float(body.get('voor', 10)), float(body.get('na', 10))
    if not (0 < voor <= 60 and 0 < na <= 60):
        raise HTTPException(400, 'voor en na tussen 0 en 60 seconden')
    con = store.connect()
    films = fragment_mod.maak(con, store.load_config()['root'], 'EXP', moment, voor, na)
    con.close()
    if not films:
        raise HTTPException(404, 'geen opnames rond dit moment')
    return {'ts': moment.isoformat(), 'views': _views(films)}


@app.get('/fragment/{naam}')
def fragment_bestand(naam: str, request: Request, download: int = 0):
    pad = fragment_mod.pad_voor(store.load_config()['root'], naam)
    if pad is None:
        raise HTTPException(404, 'onbekend fragment')
    if not pad.exists():                       # het voorbeeld van load_demo.py staat in demo/
        demo = fragment_mod.pad_voor(Path(__file__).resolve().parent / 'demo', naam)
        if demo and demo.exists():
            pad = demo
    return bestand_sturen(pad, request, bool(download))


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
            'km': r['km'], 'measured': r['measured'], 'note': r['note'],
            'zakelijk': bool(r['zakelijk'])}


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


@app.get('/api/trip/{trip_id}/weer')
def api_weer(trip_id: int):
    """Weer tijdens de rit (KNMI, dichtstbijzijnde station, alleen Nederland)."""
    con = store.connect()
    t = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not t:
        con.close()
        raise HTTPException(404, 'rit niet gevonden')
    try:
        return weer_mod.voor_rit(con, dict(t))
    finally:
        con.close()


@app.post('/api/trip/{trip_id}/zakelijk')
async def api_zakelijk_zetten(trip_id: int, request: Request):
    """Markeert een rit als zakelijk of privé. Alleen het vinkje; bedragen rekent deze app niet uit."""
    waarde = bool((await request.json()).get('zakelijk'))
    con = store.connect()
    n = con.execute('UPDATE trips SET zakelijk = ? WHERE id = ?', (int(waarde), trip_id)).rowcount
    con.commit()
    con.close()
    if not n:
        raise HTTPException(404, 'rit niet gevonden')
    return {'id': trip_id, 'zakelijk': waarde}


@app.get('/api/zakelijk')
def api_zakelijk(van: str, tot: str):
    """Zakelijke ritten tussen twee dagen (t/m), bv. voor een declaratie in een andere app."""
    con = store.connect()
    rows = con.execute('SELECT * FROM trips WHERE zakelijk = 1 AND day BETWEEN ? AND ? '
                       'ORDER BY start_ts', (van, tot)).fetchall()
    con.close()
    return {'van': van, 'tot': tot, 'ritten': [trip_dict(r) for r in rows]}


@app.post('/api/trip/{trip_id}/route')
def api_route_bouw(trip_id: int):
    try:
        return route_mod.bouw(trip_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


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
    return {
        'root': cfg.get('root', ''),
        'folders': cfg.get('folders', {}),
        'timezone': cfg.get('timezone', 'Europe/Amsterdam'),
        'primary_view': (cfg.get('views') or {}).get('primary', 'front'),
        'port': (cfg.get('web') or {}).get('port'),
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

    store.save_config(cfg)
    return settings_lezen()


@app.get('/healthz')
def healthz():
    return {'ok': True}


@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html', headers={'Cache-Control': 'no-cache'})


app.mount('/', NoCacheStatic(directory=STATIC), name='static')
