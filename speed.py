#!/usr/bin/env python3
"""Leest de snelheid uit de zwarte balk van de dashcam. Het lettertype en de plek
liggen vast, dus de cijfers worden vergeleken met voorbeelden — dat is exacter en
sneller dan gewone tekstherkenning."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Onder launchd staat /opt/homebrew/bin niet in het PATH (gemeten 14-09-2026).
FFMPEG = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TEMPLATES = HERE / 'data' / 'digits.json'
CROP = (960, 20, 1056, 78)          # even afmetingen: ffmpeg past oneven maten stil aan
BOX = (14, 22)                      # elk cijfer wordt hierop genormaliseerd
THRESHOLD = 130


def _mask(gray_rows):
    return [[1 if v > THRESHOLD else 0 for v in row] for row in gray_rows]


def _split(mask):
    h, w = len(mask), len(mask[0])
    cols = [sum(mask[y][x] for y in range(h)) for x in range(w)]
    groups, start = [], None
    for x, c in enumerate(cols):
        if c and start is None:
            start = x
        elif not c and start is not None:
            if x - start >= 3:
                groups.append((start, x))
            start = None
    if start is not None and w - start >= 3:
        groups.append((start, w))
    return groups


def _normalise(mask, x0, x1):
    rows = [y for y in range(len(mask)) if any(mask[y][x] for x in range(x0, x1))]
    if not rows:
        return None
    y0, y1 = rows[0], rows[-1] + 1
    bw, bh = BOX
    out = []
    for j in range(bh):
        sy = y0 + int(j * (y1 - y0) / bh)
        out.append([mask[sy][x0 + int(i * (x1 - x0) / bw)] for i in range(bw)])
    return out


def glyphs(gray_rows):
    mask = _mask(gray_rows)
    return [g for g in (_normalise(mask, a, b) for a, b in _split(mask)) if g]


def load_templates():
    with open(TEMPLATES) as f:
        return {k: v for k, v in json.load(f).items()}


def match(glyph, templates):
    best, score = None, -1
    total = BOX[0] * BOX[1]
    for digit, tpl in templates.items():
        same = sum(1 for j in range(BOX[1]) for i in range(BOX[0])
                   if glyph[j][i] == tpl[j][i])
        if same > score:
            best, score = digit, same
    return best, score / total


def read(gray_rows, templates, min_score=0.86):
    gs = glyphs(gray_rows)
    if not gs or len(gs) > 3:
        return None
    out = ''
    for g in gs:
        d, s = match(g, templates)
        if s < min_score:
            return None
        out += d
    return int(out)


# ── Beelden uit een clip halen ────────────────────────────────────────────────
def sample_clip(path, every=5):
    """Geeft [(seconde, km/h)] terug. Eén ffmpeg-pass, alleen de balk uitgesneden."""
    x1, y1, x2, y2 = CROP
    cmd = [FFMPEG, '-nostdin', '-loglevel', 'error', '-hwaccel', 'videotoolbox',
           '-i', str(path),
           '-vf', f'fps=1/{every},crop={x2-x1}:{y2-y1}:{x1}:{y1},format=gray',
           '-f', 'rawvideo', '-']
    w, h = x2 - x1, y2 - y1
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=180).stdout
    except subprocess.TimeoutExpired:
        return []
    frame = w * h
    templates = load_templates()
    out = []
    for n in range(len(raw) // frame):
        buf = raw[n * frame:(n + 1) * frame]
        rows = [list(buf[y * w:(y + 1) * w]) for y in range(h)]
        kmh = read(rows, templates)
        if kmh is not None:
            out.append((n * every, kmh))
    return out
