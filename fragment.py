"""Knipt een fragment rond een moment uit de minuutclips, voor elk camerabeeld.

Gedeeld door de remmomenten (automatisch, map Remmomenten) en de handmatige export uit de speler
(map Exports, bv. voor de verzekering). Gemeten 14-09-2026: 20 s over twee minuutclips heen kost
~6 s met hevc_videotoolbox; 6 Mbit geeft ~15 MB per beeld. De mappen staan op de share naast
XP_DCIM; de scan leest alleen config.folders, dus deze komen niet in de index.
"""
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Onder launchd staat /opt/homebrew/bin niet in het PATH (gemeten 14-09-2026).
FFMPEG = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'

BITRATE = '6M'
NAAM = re.compile(r'^(REM|EXP)_(\d{4})(\d{2})\d{2}_\d{6}_[A-Za-z0-9_]+\.mp4$')
MAPPEN = {'REM': 'Remmomenten', 'EXP': 'Exports'}


def pad_voor(root, naam):
    """Bestandsnaam → pad op de share, of None als de naam niet klopt (geen ../ en dergelijke)."""
    m = NAAM.match(naam)
    if not m:
        return None
    return Path(root) / MAPPEN[m.group(1)] / f'{m.group(2)}-{m.group(3)}' / naam


def maak(con, root, prefix, moment, voor=10, na=10):
    """Geeft {view: pad} terug. Bestaat het bestand al, dan wordt het niet opnieuw gemaakt."""
    start, eind = moment - timedelta(seconds=voor), moment + timedelta(seconds=na)
    doelmap = Path(root) / MAPPEN[prefix] / moment.strftime('%Y-%m')
    doelmap.mkdir(parents=True, exist_ok=True)
    grens = ((start - timedelta(seconds=60)).isoformat(timespec='seconds'),
             eind.isoformat(timespec='seconds'))
    clips = []
    for kind in ('normaal', 'noodgeval'):      # noodopnames alleen als er geen gewone zijn
        clips = con.execute('SELECT view, path, ts FROM clips WHERE kind = ? AND ts > ? AND ts <= ? '
                            'ORDER BY view, ts', (kind, *grens)).fetchall()
        if clips:
            break
    per_view = {}
    for c in clips:
        per_view.setdefault(c['view'], []).append(c)

    films = {}
    for view, reeks in per_view.items():
        uit = doelmap / f'{prefix}_{moment:%Y%m%d_%H%M%S}_{view}.mp4'
        if not uit.exists():
            eerste = datetime.fromisoformat(reeks[0]['ts'])
            with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as lijst:
                for c in reeks:
                    lijst.write(f"file '{c['path']}'\n")
            cmd = [FFMPEG, '-nostdin', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0',
                   '-i', lijst.name, '-ss', f'{max(0.0, (start - eerste).total_seconds()):.2f}',
                   '-t', f'{voor + na:g}', '-an', '-c:v', 'hevc_videotoolbox', '-b:v', BITRATE,
                   '-tag:v', 'hvc1', '-movflags', '+faststart', str(uit)]
            r = subprocess.run(cmd, capture_output=True, timeout=300)
            if r.returncode != 0:
                # Geen Mac (geen videotoolbox)? Dan de gewone software-encoder.
                i = cmd.index('hevc_videotoolbox')
                cmd[i:i + 3] = ['libx264', '-crf', '23']
                cmd.remove('-tag:v'); cmd.remove('hvc1')
                r = subprocess.run(cmd, capture_output=True, timeout=600)
            Path(lijst.name).unlink(missing_ok=True)
            if r.returncode != 0 or not uit.exists():
                print(f'  fragment mislukt {uit.name}: {r.stderr.decode()[-200:]}', flush=True)
                continue
        films[view] = str(uit)
    return films
