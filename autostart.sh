#!/bin/bash
# Start the viewer, but only once the footage folder is actually there.
#
# On a Mac a network share is mounted a little after login. Starting straight away
# gives a viewer that finds nothing, which looks like data loss rather than a timing
# problem. So we wait, and give up after a while so the supervisor can retry.
cd "$(dirname "$0")" || exit 1

WACHT_MAX=${WACHT_MAX:-600}      # seconden
STAP=5

lees_config() {
  ./.venv/bin/python - "$1" <<'PY'
import json, sys
try:
    cfg = json.load(open('config.json'))
except Exception:
    sys.exit(1)
if sys.argv[1] == 'root':
    print(cfg.get('root', ''))
else:
    print((cfg.get('web') or {}).get('port', 8965))
PY
}

ROOT=$(lees_config root)
POORT=$(lees_config port)
[ -n "$POORT" ] || POORT=8965

if [ -n "$ROOT" ]; then
  gewacht=0
  while [ ! -d "$ROOT" ]; do
    if [ "$gewacht" -ge "$WACHT_MAX" ]; then
      echo "$(date '+%F %T')  $ROOT nog steeds niet gekoppeld na ${WACHT_MAX}s - stoppen, launchd probeert straks opnieuw"
      exit 1
    fi
    [ "$gewacht" -eq 0 ] && echo "$(date '+%F %T')  wachten op $ROOT ..."
    sleep "$STAP"
    gewacht=$((gewacht + STAP))
  done
  echo "$(date '+%F %T')  $ROOT is er (na ${gewacht}s) - viewer starten op poort $POORT"
else
  echo "$(date '+%F %T')  geen map ingesteld; viewer start toch op poort $POORT"
fi

export PROC_NAME=XpengViewer
exec ./.venv/bin/uvicorn app:app --host 0.0.0.0 --port "$POORT"
