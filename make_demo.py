#!/usr/bin/env python3
"""Maakt de demobeelden: neemt één dag uit een echt archief en blurt het beeld,
maar laat de snelheidsbalk scherp. Zo blijft het meten van kilometers werken zonder
dat er iets van de omgeving herkenbaar is.

Alleen nodig voor wie de demo samenstelt. Een gebruiker draait load_demo.py.

    ./.venv/bin/python make_demo.py 2026-08-13
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store
import speed

UIT = HERE / 'demo' / 'footage'
# De snelheid wordt in de demo NIET uit het beeld gelezen (blurren en samendrukken
# tasten de cijfers te veel aan). De cijfers staan kant-en-klaar in de demo-database.
# Daardoor mag het beeld klein en hard samengedrukt: het is alleen om naar te kijken.
CRF = '38'
BREEDTE = 960


def blur(bron, doel):
    x1, y1, x2, y2 = speed.CROP
    b, h = x2 - x1, y2 - y1
    # Balk scherp houden is alleen nog voor het oog; daarna gaat alles omlaag in maat.
    filt = (f'[0:v]split=2[bg][bar];[bg]boxblur=24:3[blur];'
            f'[bar]crop={b}:{h}:{x1}:{y1}[cut];[blur][cut]overlay={x1}:{y1},'
            f'scale={BREEDTE}:-2[v]')
    cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(bron),
           '-filter_complex', filt, '-map', '[v]', '-an',
           '-c:v', 'libx264', '-crf', CRF, '-preset', 'faster',
           '-pix_fmt', 'yuv420p', str(doel)]
    return subprocess.run(cmd).returncode == 0


def main(dag):
    con = store.connect()
    rijen = con.execute(
        'SELECT path FROM clips WHERE day = ? ORDER BY ts', (dag,)).fetchall()
    if not rijen:
        raise SystemExit(f'geen clips gevonden voor {dag}')
    UIT.mkdir(parents=True, exist_ok=True)

    bron_bytes = doel_bytes = 0
    for i, r in enumerate(rijen, 1):
        bron = Path(r['path'])
        if not bron.exists():
            print(f'  overslaan (weg): {bron.name}')
            continue
        doel = UIT / bron.name
        print(f'  [{i}/{len(rijen)}] {bron.name}', flush=True)
        if not blur(bron, doel):
            print('     MISLUKT'); continue
        bron_bytes += bron.stat().st_size
        doel_bytes += doel.stat().st_size

    print(f'\nbron : {bron_bytes/1e6:.0f} MB')
    print(f'demo : {doel_bytes/1e6:.1f} MB  ({bron_bytes/max(doel_bytes,1):.0f}x kleiner)')
    print(f'staat in: {UIT}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '2026-08-13')
