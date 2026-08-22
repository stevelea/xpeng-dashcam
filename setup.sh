#!/usr/bin/env bash
# Zet een lege viewer klaar: virtuele omgeving, pakketten, mappen en een eigen
# config.json. Raakt een bestaande config.json nooit aan.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "==> Python controleren"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "    Python 3 not found. Install Python 3.11 or newer and try again." >&2
  exit 1
fi
"$PY" - <<'CHECK'
import sys
if sys.version_info < (3, 11):
    sys.exit(f'    Python 3.11+ required, found {sys.version.split()[0]}')
CHECK
echo "    $("$PY" -V)"

echo "==> Virtuele omgeving"
[ -d .venv ] || "$PY" -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt
echo "    packages installed"

echo "==> Mappen"
mkdir -p data thumbs
echo "    data/ and thumbs/ ready"

echo "==> Instellingen"
if [ -f config.json ]; then
  echo "    config.json already exists - left untouched"
else
  cp config.example.json config.json
  echo "    config.json created from the example"
fi

echo "==> ffmpeg"
if command -v ffmpeg >/dev/null 2>&1; then
  echo "    $(ffmpeg -version 2>/dev/null | head -1 | cut -c1-40)"
else
  echo "    NOT found - thumbnails and speed reading will not work."
  echo "    macOS: brew install ffmpeg   |   Debian/Ubuntu: sudo apt install ffmpeg"
fi

cat <<'NEXT'

Done. Next steps:

  1. Start the viewer:        ./run.sh
  2. Open it:                 http://127.0.0.1:8965
  3. Click the gear icon and set the folder that holds your dashcam files.
     Use "Test folder" to confirm the app recognises your clips.
  4. Back in the terminal, build the index (in this order):

         ./.venv/bin/python scan.py      # find the clips
         ./.venv/bin/python thumbs.py    # make the thumbnails (needs ffmpeg)
         ./.venv/bin/python ritten.py    # group the clips into trips

  The viewer starts empty. Nothing appears until step 4 has run.
  Re-run the same three commands whenever you add new footage.

NEXT
