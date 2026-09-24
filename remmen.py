#!/usr/bin/env python3
"""Harde remmomenten uit de snelheid in beeld, met een filmpje van 10 s ervoor tot 10 s erna.

Er zit geen G-sensor in de clips (gemeten: alleen een videostroom). De snelheid wordt daarom elke
halve seconde uit de balk gelezen via speed.py — ~6 s per clip, even duur als elke seconde, want
het decoderen kost de tijd. De fijne reeks wordt bewaard, zodat de herkenning met andere grenzen
opnieuw kan zonder alles opnieuw te lezen.

    python remmen.py 2026-09            lezen, herkennen en filmpjes maken voor die maand
    python remmen.py 2026-09 --herken   alleen opnieuw herkennen uit de bewaarde reeks
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fragment
import speed
import store

STAP = 0.5            # seconden tussen metingen
MIN_DALING = 11.0     # km/h per seconde (≈ 3 m/s²). Op een testmaand: 13 → 1 moment, 11 → 4, 7 = gewoon stoppen
MIN_DUUR = 1.5        # zo lang moet die daling minstens duren
MAX_VENSTER = 3.0
MIN_START = 20        # km/h
MIN_METINGEN = 3
MAX_GAT = 1.0         # hoogstens één gemiste meting binnen een remming
VOORAF_S = 3          # 'van' = hoogste snelheid in deze seconden vóór het remmen
MARGE = 10            # seconden vóór en na in het filmpje

SCHEMA = """
CREATE TABLE IF NOT EXISTS snelheid_fijn (
    clip_id TEXT NOT NULL,
    t       REAL NOT NULL,
    kmh     INTEGER NOT NULL,
    PRIMARY KEY (clip_id, t)
);
CREATE TABLE IF NOT EXISTS snelheid_fijn_gelezen (
    clip_id  TEXT PRIMARY KEY,
    metingen INTEGER NOT NULL,
    gelezen  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS remmomenten (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL UNIQUE,
    day      TEXT NOT NULL,
    van_kmh  INTEGER NOT NULL,
    naar_kmh INTEGER NOT NULL,
    daling   REAL NOT NULL,
    duur     REAL NOT NULL,
    clip_id  TEXT NOT NULL,
    films    TEXT,
    gemaakt  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rem_day ON remmomenten(day);
"""


def connect():
    con = store.connect()
    con.executescript(SCHEMA)
    return con


def _nu():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


# ── Lezen ────────────────────────────────────────────────────────────────────
def lees(con, maand):
    rows = con.execute(
        "SELECT c.id, c.path, c.ts FROM clips c WHERE c.view = 'front' AND c.kind = 'normaal' "
        "AND c.day LIKE ? AND EXISTS (SELECT 1 FROM trips t WHERE c.ts BETWEEN t.start_ts AND t.end_ts) "
        "AND NOT EXISTS (SELECT 1 FROM snelheid_fijn_gelezen g WHERE g.clip_id = c.id) ORDER BY c.ts",
        (maand + '%',)).fetchall()
    n, t0 = len(rows), time.time()
    print(f'{n} rijclips te lezen in {maand}', flush=True)
    for i, r in enumerate(rows, 1):
        if not Path(r['path']).exists():
            print(f'  niet bereikbaar: {r["path"]}', flush=True)
            continue
        reeks = speed.sample_clip(r['path'], every=STAP)
        if not reeks:              # time-out of haperende share: volgende keer opnieuw
            continue
        con.executemany('INSERT OR REPLACE INTO snelheid_fijn VALUES (?,?,?)',
                        [(r['id'], t, k) for t, k in reeks])
        con.execute('INSERT OR REPLACE INTO snelheid_fijn_gelezen VALUES (?,?,?)',
                    (r['id'], len(reeks), _nu()))
        con.commit()
        if i % 20 == 0 or i == n:
            rest = (time.time() - t0) / i * (n - i) / 60
            print(f'  {i}/{n} clips  nog ~{rest:.0f} min', flush=True)


# ── Herkennen ────────────────────────────────────────────────────────────────
def _zonder_uitschieters(p):
    """Eén verkeerd gelezen cijfer (48, 18, 47) mag geen remming worden."""
    uit = []
    for i, x in enumerate(p):
        if 0 < i < len(p) - 1:
            a, b = p[i - 1][1], p[i + 1][1]
            if abs(a - b) <= 6 and abs(x[1] - a) > 15 and abs(x[1] - b) > 15:
                continue
        uit.append(x)
    return uit


def herken(punten):
    """punten: [(tijdstip, km/h, clip_id)] van één rit, op tijd gesorteerd."""
    p = _zonder_uitschieters(punten)
    kandidaten = []
    for i in range(len(p)):
        if p[i][1] < MIN_START:
            continue
        for j in range(i + 1, len(p)):
            dt = (p[j][0] - p[i][0]).total_seconds()
            if dt > MAX_VENSTER:
                break
            if dt < MIN_DUUR or j - i + 1 < MIN_METINGEN:
                continue
            stuk = p[i:j + 1]
            if any((stuk[k + 1][0] - stuk[k][0]).total_seconds() > MAX_GAT for k in range(len(stuk) - 1)):
                continue
            if any(stuk[k + 1][1] > stuk[k][1] + 2 for k in range(len(stuk) - 1)):   # moet blijven dalen
                continue
            daling = (p[i][1] - p[j][1]) / dt
            if daling >= MIN_DALING:
                kandidaten.append((p[i][0], p[j][0], p[i][1], p[j][1], daling, p[i][2]))
    momenten = []
    for k in sorted(kandidaten):          # overlappende vensters zijn één remming
        if momenten and k[0] <= momenten[-1]['eind']:
            m = momenten[-1]
            m['eind'] = max(m['eind'], k[1])
            m['naar'] = min(m['naar'], k[3])
            m['daling'] = max(m['daling'], k[4])
        else:
            momenten.append({'begin': k[0], 'eind': k[1], 'van': k[2], 'naar': k[3],
                             'daling': k[4], 'clip_id': k[5]})
    for m in momenten:
        # Toon de hele stop, niet alleen het steilste stuk (12-09-2026: steil 69→48, hele stop 73→0).
        # 'daling' blijft de steilste daling; 'duur' loopt tot het laagste punt.
        i0 = next(i for i, x in enumerate(p) if x[0] >= m['begin'])
        i1 = next(i for i, x in enumerate(p) if x[0] >= m['eind'])
        m['van'] = max(x[1] for x in p[:i0 + 1] if (m['begin'] - x[0]).total_seconds() <= VOORAF_S)
        j = i1
        while (j + 1 < len(p) and p[j + 1][1] <= p[j][1] + 2
               and (p[j + 1][0] - p[j][0]).total_seconds() <= MAX_GAT):
            j += 1
        laagste = min(range(i0, j + 1), key=lambda k: p[k][1])
        m['naar'] = p[laagste][1]
        m['duur'] = (p[laagste][0] - p[i0][0]).total_seconds()
    return momenten


def herken_maand(con, maand):
    gevonden = []
    for t in con.execute('SELECT start_ts, end_ts FROM trips WHERE day LIKE ? ORDER BY start_ts',
                         (maand + '%',)).fetchall():
        rows = con.execute(
            'SELECT c.id, c.ts, f.t, f.kmh FROM snelheid_fijn f JOIN clips c ON c.id = f.clip_id '
            'WHERE c.ts BETWEEN ? AND ? ORDER BY c.ts, f.t', (t['start_ts'], t['end_ts'])).fetchall()
        punten = [(datetime.fromisoformat(r['ts']) + timedelta(seconds=r['t']), r['kmh'], r['id'])
                  for r in rows]
        gevonden += herken(punten)
    # Opnieuw herkennen vervangt de lijst van die maand; de filmpjes op de share blijven staan.
    con.execute('DELETE FROM remmomenten WHERE day LIKE ?', (maand + '%',))
    for m in gevonden:
        con.execute('INSERT OR REPLACE INTO remmomenten (ts, day, van_kmh, naar_kmh, daling, duur, '
                    'clip_id, films, gemaakt) VALUES (?,?,?,?,?,?,?,?,?)',
                    (m['begin'].isoformat(timespec='seconds'), m['begin'].strftime('%Y-%m-%d'),
                     m['van'], m['naar'], round(m['daling'], 1), m['duur'], m['clip_id'], None, _nu()))
    con.commit()
    print(f'{len(gevonden)} remmomenten in {maand}', flush=True)
    return gevonden


# ── Filmpjes ─────────────────────────────────────────────────────────────────
def film(con, cfg, rij):
    films = fragment.maak(con, cfg['root'], 'REM', datetime.fromisoformat(rij['ts']), MARGE, MARGE)
    con.execute('UPDATE remmomenten SET films = ? WHERE id = ?', (json.dumps(films), rij['id']))
    con.commit()
    return films


def films_maand(con, maand):
    cfg = store.load_config()
    rijen = con.execute('SELECT * FROM remmomenten WHERE day LIKE ? ORDER BY ts', (maand + '%',)).fetchall()
    for i, rij in enumerate(rijen, 1):
        f = film(con, cfg, rij)
        print(f"  {i}/{len(rijen)} {rij['ts'][:19]}  {rij['van_kmh']}→{rij['naar_kmh']} km/h "
              f"({rij['daling']} km/h/s)  {len(f)} beeld(en)", flush=True)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    maand = sys.argv[1]
    con = connect()
    if '--herken' not in sys.argv:
        lees(con, maand)
    herken_maand(con, maand)
    films_maand(con, maand)
    con.close()
