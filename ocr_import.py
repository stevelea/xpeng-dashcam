#!/usr/bin/env python3
"""Neemt gelezen tekst uit een andere app over. Alleen de tekst — geen snelheden,
geen coordinaten, geen ritindeling. Die maken we zelf, en beter.

De bron wordt met een kopie gelezen, zodat er aan die app niets verandert."""
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

AMS = ZoneInfo('Europe/Amsterdam')
BRON = Path('~/My_Projects/xpeng-route-google/data/routes.db').expanduser()


def haal(bron=BRON, con=None):
    bron = Path(bron).expanduser()
    if not bron.exists():
        raise SystemExit(f'bron niet gevonden: {bron}')

    fd, tmp = tempfile.mkstemp(suffix='.db', prefix='ocr-bron-')
    Path(tmp).unlink(missing_ok=True)
    shutil.copy2(bron, tmp)
    try:
        b = sqlite3.connect(f'file:{tmp}?mode=ro', uri=True)
        b.row_factory = sqlite3.Row
        rijen = b.execute('SELECT timestamp, date, detected_text FROM clips').fetchall()
        b.close()
    finally:
        Path(tmp).unlink(missing_ok=True)

    own = con is None
    con = con or store.connect()
    n = leeg = 0
    for r in rijen:
        try:
            teksten = json.loads(r['detected_text'] or '[]')
        except json.JSONDecodeError:
            continue
        if not teksten:
            leeg += 1
            continue
        try:
            ts = datetime.strptime(f"{r['date']} {r['timestamp']}", '%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
        iso = ts.replace(tzinfo=AMS).isoformat(timespec='seconds')
        for t in teksten:
            t = (t or '').strip()
            if t:
                con.execute('INSERT OR IGNORE INTO ocr_tekst (ts, tekst) VALUES (?, ?)', (iso, t))
                n += 1
    con.commit()
    totaal = con.execute('SELECT count(*) FROM ocr_tekst').fetchone()[0]
    if own:
        con.close()
    return {'overgenomen': n, 'clips_zonder_tekst': leeg, 'totaal_in_db': totaal}


if __name__ == '__main__':
    print(haal())
