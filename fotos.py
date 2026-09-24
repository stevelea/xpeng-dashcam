#!/usr/bin/env python3
"""Haalt ALLEEN tijd en coordinaat uit de fotobibliotheek, om ritten een locatie te geven.

Bewust beperkt:
- er worden drie velden gelezen: tijdstip, breedte- en lengtegraad;
- er wordt geen bestandsnaam, geen id en geen afbeelding gelezen of bewaard;
- de bibliotheek wordt nooit gewijzigd;
- de tijdelijke kopie van de database (nodig omdat Foto's zijn eigen bestand
  open houdt) wordt na afloop meteen verwijderd.
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)
_last_geocode = [0.0]
_cache = {'punten': None, 'tijd': 0.0}
CACHE_SECONDS = 900


def library_db(cfg):
    lib = cfg.get('photos', {}).get('library', '~/Pictures/Photos Library.photoslibrary')
    return Path(lib).expanduser() / 'database' / 'Photos.sqlite'


def alle_punten(cfg, force=False):
    """Alle (tijd, lat, lon) uit de bibliotheek. Eén keer lezen, daarna uit geheugen."""
    if not force and _cache['punten'] is not None and time.time() - _cache['tijd'] < CACHE_SECONDS:
        return _cache['punten']

    db = library_db(cfg)
    if not db.exists():
        _cache.update(punten=[], tijd=time.time())
        return []

    fd, tmp = tempfile.mkstemp(suffix='.sqlite', prefix='fotos-tijdelijk-')
    os.close(fd)
    try:
        shutil.copy2(db, tmp)
        con = sqlite3.connect(f'file:{tmp}?mode=ro', uri=True)
        rows = con.execute(
            'SELECT ZDATECREATED, ZLATITUDE, ZLONGITUDE FROM ZASSET '
            'WHERE ZLATITUDE > -90 ORDER BY ZDATECREATED').fetchall()
        con.close()
    finally:
        for rest in (tmp, tmp + '-wal', tmp + '-shm'):
            Path(rest).unlink(missing_ok=True)

    punten = [((APPLE_EPOCH + timedelta(seconds=d)).astimezone(), la, lo)
              for d, la, lo in rows]
    _cache.update(punten=punten, tijd=time.time())
    return punten


def punten_tussen(cfg, start, end):
    return [(t, la, lo) for t, la, lo in alle_punten(cfg) if start <= t <= end]


def place_name(con, lat, lon):
    """Plaatsnaam bij een coordinaat, blijvend gecachet. Zonder internet: None."""
    import httpx
    cell = f'{round(lat, 3):.3f},{round(lon, 3):.3f}'
    row = con.execute('SELECT name FROM places WHERE cell = ?', (cell,)).fetchone()
    if row:
        return row['name']
    wacht = 1.1 - (time.time() - _last_geocode[0])
    if wacht > 0:
        time.sleep(wacht)
    _last_geocode[0] = time.time()
    try:
        r = httpx.get('https://nominatim.openstreetmap.org/reverse',
                      params={'lat': lat, 'lon': lon, 'format': 'jsonv2',
                              'zoom': 16, 'accept-language': 'nl'},
                      headers={'User-Agent': 'xpeng-dashcam/1.0 (persoonlijk)'}, timeout=12)
        r.raise_for_status()
        a = r.json().get('address', {})
        plaats = a.get('city') or a.get('town') or a.get('village') or a.get('municipality')
        naam = ', '.join(x for x in (a.get('road'), plaats) if x) or None
    except Exception:
        return None
    if naam:
        con.execute('INSERT OR REPLACE INTO places (cell, name) VALUES (?, ?)', (cell, naam))
        con.commit()
    return naam


def link_trip(trip_id, margin_min=20, geocode=True, con=None, cfg=None):
    own = con is None
    con = con or store.connect()
    cfg = cfg or store.load_config()
    t = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not t:
        raise ValueError('rit bestaat niet')
    start = datetime.fromisoformat(t['start_ts']) - timedelta(minutes=margin_min)
    end = datetime.fromisoformat(t['end_ts']) + timedelta(minutes=margin_min)

    con.execute("DELETE FROM waypoints WHERE trip_id = ? AND source = 'foto'", (trip_id,))
    n, vorig = 0, None
    for ts, lat, lon in punten_tussen(cfg, start, end):
        if vorig and abs(lat - vorig[0]) < 2e-4 and abs(lon - vorig[1]) < 2e-4:
            continue
        vorig = (lat, lon)
        naam = place_name(con, lat, lon) if geocode else None
        con.execute('INSERT OR IGNORE INTO waypoints (trip_id, ts, lat, lon, label, source) '
                    'VALUES (?,?,?,?,?,?)',
                    (trip_id, ts.isoformat(timespec='seconds'), lat, lon, naam, 'foto'))
        n += 1
    con.commit()
    if own:
        con.close()
    return n


def link_all(margin_min=20, geocode=False, con=None):
    own = con is None
    con = con or store.connect()
    cfg = store.load_config()
    alle_punten(cfg, force=True)
    totaal = met = 0
    for r in con.execute('SELECT id FROM trips ORDER BY start_ts').fetchall():
        n = link_trip(r['id'], margin_min=margin_min, geocode=geocode, con=con, cfg=cfg)
        totaal += n
        met += 1 if n else 0
    if own:
        con.close()
    return {'punten': totaal, 'ritten_met_locatie': met}


if __name__ == '__main__':
    print(link_all())
