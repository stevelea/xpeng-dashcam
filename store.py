#!/usr/bin/env python3
"""Index van de dashcam-clips. De tijd komt uit de BESTANDSNAAM; de wijzigingsdatum
is de kopieerdatum en klopt niet."""
import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / 'data' / 'clips.db'
DEFAULTS = {
    'root': '',
    'folders': {'normaal': 'XP_DCIM', 'noodgeval': 'XP_EMER_DCIM'},
    'timezone': 'Europe/Amsterdam',
    'views': {'primary': 'front'},
}
# 14 cijfers is de tijd (JJJJMMDDuummss); sommige modellen zetten er milliseconden
# achter. De weergave achter het onderstrepingsteken is vrij: front, front_and_360,
# rear, ... zodat een andere XPENG-firmware niet stil wordt overgeslagen.
STAMP = re.compile(r'[^0-9]([0-9]{14,17})_([A-Za-z0-9_]+)\.mp4$', re.IGNORECASE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    id       TEXT PRIMARY KEY,
    path     TEXT UNIQUE NOT NULL,
    ts       TEXT NOT NULL,
    day      TEXT NOT NULL,
    kind     TEXT NOT NULL,
    view     TEXT NOT NULL,
    bytes    INTEGER NOT NULL,
    thumb    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_clips_day ON clips(day, ts);
CREATE INDEX IF NOT EXISTS idx_clips_ts  ON clips(ts);
CREATE INDEX IF NOT EXISTS idx_clips_thumb ON clips(thumb);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS ocr_tekst (
    ts    TEXT NOT NULL,
    tekst TEXT NOT NULL,
    PRIMARY KEY (ts, tekst)
);
CREATE INDEX IF NOT EXISTS idx_ocr_ts ON ocr_tekst(ts);

CREATE TABLE IF NOT EXISTS routes (
    trip_id    INTEGER PRIMARY KEY,
    soort      TEXT NOT NULL DEFAULT 'gereconstrueerd',
    geojson    TEXT,
    km         REAL,
    punten     INTEGER,
    bijgewerkt TEXT
);

CREATE TABLE IF NOT EXISTS plaatsnamen (
    tekst  TEXT PRIMARY KEY,
    lat    REAL,
    lon    REAL,
    naam   TEXT
);

CREATE TABLE IF NOT EXISTS trips (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    day       TEXT NOT NULL,
    start_ts  TEXT NOT NULL UNIQUE,
    end_ts    TEXT NOT NULL,
    clips     INTEGER NOT NULL,
    seconds   INTEGER NOT NULL,
    km        REAL,
    measured  INTEGER NOT NULL DEFAULT 0,
    note      TEXT
);
CREATE INDEX IF NOT EXISTS idx_trips_day ON trips(day, start_ts);

CREATE TABLE IF NOT EXISTS speeds (
    clip_id  TEXT NOT NULL,
    offset_s INTEGER NOT NULL,
    kmh      INTEGER NOT NULL,
    PRIMARY KEY (clip_id, offset_s)
);

CREATE TABLE IF NOT EXISTS waypoints (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER NOT NULL,
    ts      TEXT NOT NULL,
    lat     REAL NOT NULL,
    lon     REAL NOT NULL,
    label   TEXT,
    source  TEXT NOT NULL,
    UNIQUE (trip_id, ts, source)
);
CREATE INDEX IF NOT EXISTS idx_wp_trip ON waypoints(trip_id, ts);

CREATE TABLE IF NOT EXISTS places (
    cell TEXT PRIMARY KEY,
    name TEXT
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=60)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript(SCHEMA)
    return con


_config = None


def load_config(herlaad=False):
    """Leest config.json en vult ontbrekende sleutels aan met DEFAULTS, zodat een
    kort eigen configbestand nooit een KeyError geeft."""
    global _config
    if _config is not None and not herlaad:
        return _config
    pad = HERE / 'config.json'
    eigen = {}
    if pad.exists():
        with open(pad, encoding='utf-8') as f:
            eigen = json.load(f)
    cfg = dict(DEFAULTS)
    cfg.update(eigen)
    for sleutel in ('folders', 'views'):
        samen = dict(DEFAULTS[sleutel])
        samen.update(eigen.get(sleutel) or {})
        cfg[sleutel] = samen
    _config = cfg
    return cfg


def save_config(nieuw):
    """Schrijft config.json en vergeet de gecachte versie."""
    global _config
    pad = HERE / 'config.json'
    if pad.exists():
        pad.with_suffix('.json.bak').write_text(pad.read_text(encoding='utf-8'), encoding='utf-8')
    with open(pad, 'w', encoding='utf-8') as f:
        json.dump(nieuw, f, indent=2, ensure_ascii=False)
    _config = None
    return load_config()


def tijdzone():
    try:
        return ZoneInfo(load_config().get('timezone') or 'Europe/Amsterdam')
    except Exception:
        return ZoneInfo('Europe/Amsterdam')


def clip_id(path):
    return hashlib.sha1(path.encode('utf-8')).hexdigest()[:16]


def parse_name(name):
    m = STAMP.search(name)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1)[:14], '%Y%m%d%H%M%S')
    except ValueError:
        return None
    return dt.replace(tzinfo=tijdzone()), m.group(2).lower()


def get_meta(con, key, default=None):
    row = con.execute('SELECT value FROM meta WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else default


def set_meta(con, key, value):
    con.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', (key, str(value)))
