#!/usr/bin/env python3
"""Loopt de share door en zet elke clip in de index. Veilig om opnieuw te draaien:
bestaande regels blijven staan, inclusief de vlag dat er al een miniatuur is."""
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store
import thumbs


def scan(verbose=True):
    cfg = store.load_config()
    if not cfg.get('root'):
        raise SystemExit('Geen map ingesteld — vul "root" in config.json of in het instellingenscherm')
    root = Path(cfg['root']).expanduser()
    if not root.exists():
        raise SystemExit(f'{root} bestaat niet — koppel de share of kies een andere map')

    con = store.connect()
    thumbs.herstel_vlaggen(con)
    seen = set()
    added = skipped = 0

    # Staan de mappen van XPENG er niet, dan ligt alles waarschijnlijk plat in de
    # hoofdmap. Die doorzoeken we dan zelf, anders vindt de scan niets.
    mappen = [(kind, root / folder) for kind, folder in cfg['folders'].items()]
    if not any(base.exists() for _, base in mappen):
        mappen = [('normaal', root)]

    for kind, base in mappen:
        if not base.exists():
            continue
        for path in base.rglob('*.mp4'):
            parsed = store.parse_name(path.name)
            if parsed is None:
                skipped += 1
                continue
            dt, view = parsed
            try:
                size = path.stat().st_size
            except OSError:
                skipped += 1
                continue
            if size == 0:
                skipped += 1
                continue
            spath = str(path)
            cid = store.clip_id(spath)
            seen.add(cid)
            con.execute(
                'INSERT INTO clips (id, path, ts, day, kind, view, bytes) '
                'VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET bytes = excluded.bytes',
                (cid, spath, dt.isoformat(timespec='seconds'), dt.strftime('%Y-%m-%d'),
                 kind, view, size))
            added += 1
            if verbose and added % 2000 == 0:
                con.commit()
                print(f'  {added} clips…', flush=True)

    con.commit()

    # Alleen weggooien wat écht van de schijf verdwenen is. Een clip die deze ronde
    # niet meegeteld werd (leesfout, 0 byte, share even weg) mag NIET sneuvelen:
    # bij een volgende scan komt hij terug als nieuwe regel en is zijn miniatuur-vlag
    # kwijt, waarna alle beeldjes opnieuw gemaakt zouden worden.
    gone = []
    for r in con.execute('SELECT id, path FROM clips').fetchall():
        if r['id'] in seen:
            continue
        if not Path(r['path']).exists():
            gone.append(r['id'])
    for cid in gone:
        con.execute('DELETE FROM clips WHERE id = ?', (cid,))
    store.set_meta(con, 'scanned_utc', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    con.commit()
    total = con.execute('SELECT count(*) FROM clips').fetchone()[0]
    con.close()
    return {'gevonden': added, 'overgeslagen': skipped, 'verwijderd': len(gone), 'totaal': total}


if __name__ == '__main__':
    print(scan())
