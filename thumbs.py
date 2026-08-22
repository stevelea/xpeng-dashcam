#!/usr/bin/env python3
"""Maakt één miniatuur per clip met ffmpeg. Kan altijd opnieuw: wat er al staat
wordt overgeslagen, dus een afgebroken run pakt vanzelf verder waar hij stopte."""
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

THUMB_DIR = HERE / 'thumbs'


def thumb_path(cid):
    return THUMB_DIR / cid[:2] / f'{cid}.jpg'


def make_one(cid, path, cfg):
    out = thumb_path(cid)
    if out.exists() and out.stat().st_size > 0:
        return cid, True
    out.parent.mkdir(parents=True, exist_ok=True)
    t = cfg['thumbs']

    def attempt(seek):
        cmd = ['ffmpeg', '-nostdin', '-loglevel', 'error']
        if seek:
            cmd += ['-ss', str(seek)]
        cmd += ['-i', path, '-frames:v', '1', '-vf', f"scale={t['width']}:-2",
                '-q:v', str(t['quality']), '-y', str(out)]
        try:
            subprocess.run(cmd, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            return False
        return out.exists() and out.stat().st_size > 0

    # Sommige clips zijn korter dan de zoektijd; dan valt er niets te pakken en
    # moet het vanaf het begin.
    if attempt(t['seek_seconds']) or attempt(0):
        return cid, True
    out.unlink(missing_ok=True)
    return cid, False


def herstel_vlaggen(con=None):
    """Zet de vlag terug voor clips waarvan het beeldje gewoon op schijf staat.

    De vlag en het bestand kunnen uit de pas lopen — bijvoorbeeld als een clip
    tijdens een scan even onleesbaar was en opnieuw is toegevoegd. Opnieuw maken
    is dan zonde: kijken of het bestand er is, is genoeg."""
    own = con is None
    con = con or store.connect()
    hersteld = 0
    for r in con.execute('SELECT id FROM clips WHERE thumb = 0').fetchall():
        p = thumb_path(r['id'])
        if p.exists() and p.stat().st_size > 0:
            con.execute('UPDATE clips SET thumb = 1 WHERE id = ?', (r['id'],))
            hersteld += 1
    con.commit()
    if own:
        con.close()
    return hersteld


def run(limit=None, verbose=True):
    cfg = store.load_config()
    con = store.connect()
    hersteld = herstel_vlaggen(con)
    if hersteld and verbose:
        print(f'{hersteld} beeldjes stonden al op schijf, vlag hersteld', flush=True)
    rows = con.execute('SELECT id, path FROM clips WHERE thumb = 0 ORDER BY ts DESC').fetchall()
    if limit:
        rows = rows[:limit]
    todo = [(r['id'], r['path']) for r in rows]
    if verbose:
        print(f'{len(todo)} clips zonder miniatuur', flush=True)

    done = failed = 0
    start = time.time()
    with ThreadPoolExecutor(max_workers=cfg['thumbs']['workers']) as pool:
        futures = [pool.submit(make_one, cid, path, cfg) for cid, path in todo]
        for fut in futures:
            cid, ok = fut.result()
            if ok:
                con.execute('UPDATE clips SET thumb = 1 WHERE id = ?', (cid,))
                done += 1
            else:
                failed += 1
            if (done + failed) % 200 == 0:
                con.commit()
                if verbose:
                    el = time.time() - start
                    per = el / max(done + failed, 1)
                    left = (len(todo) - done - failed) * per / 60
                    print(f'  {done + failed}/{len(todo)}  mislukt {failed}  '
                          f'nog ~{left:.0f} min', flush=True)
    con.commit()
    con.close()
    return {'gemaakt': done, 'mislukt': failed, 'duur_min': round((time.time() - start) / 60, 1)}


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(run(limit=n))
