#!/bin/bash
#
# Deploy the viewer to the machine that serves it.
#
#   deploy/deploy-viewer.sh                # test, copy, rebuild, verify
#   deploy/deploy-viewer.sh --dry-run      # list what would be copied, change nothing
#   deploy/deploy-viewer.sh --skip-tests   # copy and rebuild without running the suites
#   deploy/deploy-viewer.sh --rollback     # put the previous image back
#
# Everything machine-specific is overridable:
#
#   HOST=user@machine TARGET=/path/to/app-src CONTAINER=xpeng-dashcam \
#     deploy/deploy-viewer.sh
#
# The test step uses the project's .venv when there is one, otherwise python3.
# Point it somewhere else with PY=/path/to/python (PYTHONPATH is inherited).
#
# Note: on the NAS share this repository lives on, the mount is not executable,
# so run it as `bash deploy/deploy-viewer.sh` rather than `./deploy/deploy-viewer.sh`.
#
# Three things about this arrangement are easy to get wrong, and each of them has
# already cost a deploy. The script exists mainly to encode them:
#
#   1. **The source is baked into the image.** The Dockerfile ends in `COPY . .`
#      and only the index, the thumbnails and config.json are bind-mounted, so a
#      restart changes nothing at all. The image must be rebuilt.
#
#   2. **The compose file that made the running container is not the obvious one.**
#      Here it is `docker-compose.v1.yml`, whose build context is `./app-src`.
#      The repository's `docker-compose.yml` uses `context: .` and cannot build:
#      its Dockerfile runs `COPY requirements.txt ./`, and that file lives in
#      app-src. Running the wrong one either fails or builds an image with no
#      application in it. So this asks the running container which file it came
#      from instead of guessing.
#
#   3. **Copying through the NAS share litters the tree with AppleDouble `._*`
#      files,** and `COPY . .` then bakes every one of them into the image. The
#      copy here goes over SSH and filters them out.
#
set -uo pipefail

HOST="${HOST:-pantry}"
TARGET="${TARGET:-/home/stevelea/xpeng-dashcam/app-src}"
CONTAINER="${CONTAINER:-xpeng-dashcam}"
IMAGE="${IMAGE:-xpeng-dashcam:local}"
PREVIOUS="${PREVIOUS:-xpeng-dashcam:previous}"
PORT="${PORT:-8965}"
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"

DROOG=0
TOETSEN=1
TERUG=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DROOG=1 ;;
    --skip-tests) TOETSEN=0 ;;
    --rollback)   TERUG=1 ;;
    -h|--help)    sed -n '3,29p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

stap() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
fout() { printf '\033[31mFAILED:\033[0m %s\n' "$*" >&2; }

# ── What goes over ────────────────────────────────────────────────────────────
# Everything the image needs and nothing belonging to the machine: no index, no
# thumbnails, no config.json, no git, no demo footage. New files are picked up
# automatically, which is the reason this builds a list rather than naming files.
bestandslijst() {
  cd "$SOURCE" || exit 1
  find . \
    \( -name .git -o -name demo -o -name thumbs -o -name __pycache__ \
       -o -name '.venv' -o -name '.memsearch' -o -path './deploy/live' \) -prune \
    -o -type f \
       ! -name '.DS_Store' ! -name '._*' ! -name '*.log' \
       ! -name 'config.json' ! -name 'config.json.bak' \
       ! -name '*.db' ! -name '*.db-wal' ! -name '*.db-shm' \
       -print | sort
}

# ── Which compose file really made the running container ──────────────────────
compose_bestand() {
  local cfg
  cfg="$(ssh "$HOST" "docker inspect $CONTAINER --format '{{index .Config.Labels \"com.docker.compose.project.config_files\"}}'" 2>/dev/null)"
  if [ -n "$cfg" ] && [ "$cfg" != "<no value>" ]; then printf '%s' "$cfg"
  else printf 'docker-compose.yml'; fi
}

# ── Reach the host, and work out how to talk to Docker there ──────────────────
stap "Preparing"
ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" 'echo ok' >/dev/null 2>&1 || {
  fout "no SSH to $HOST. Install a key, or pass HOST=user@machine."; exit 1; }

if ssh "$HOST" 'docker compose version >/dev/null 2>&1'; then
  COMPOSE_CMD="docker compose"
else
  COMPOSE_CMD="docker-compose"          # pantry has only the standalone v1
fi

COMPOSE_FILE="$(compose_bestand)"
PROJECT="$(dirname "$TARGET")"

ssh "$HOST" "test -d '$TARGET'" || { fout "$TARGET does not exist on $HOST"; exit 1; }
ssh "$HOST" "test -f '$PROJECT/$COMPOSE_FILE'" || {
  fout "$PROJECT/$COMPOSE_FILE does not exist on $HOST"; exit 1; }

# ── Rollback, now that we know how to rebuild here ────────────────────────────
if [ "$TERUG" = 1 ]; then
  stap "Restoring the previous image on $HOST"
  ssh "$HOST" "docker image inspect $PREVIOUS >/dev/null 2>&1" || {
    fout "no $PREVIOUS on $HOST — nothing to roll back to"; exit 1; }
  ssh "$HOST" "docker tag $PREVIOUS $IMAGE && cd '$PROJECT' && $COMPOSE_CMD -f '$COMPOSE_FILE' up -d" \
    || exit 1
  printf '\nRolled back to the previous image.\n'
  exit 0
fi

printf '  source      : %s\n' "$SOURCE"
printf '  target      : %s:%s\n' "$HOST" "$TARGET"
printf '  project     : %s\n' "$PROJECT"
printf '  compose     : %s -f %s\n' "$COMPOSE_CMD" "$COMPOSE_FILE"
if [ -d "$SOURCE/.git" ]; then
  vies="$(cd "$SOURCE" && git status --porcelain | wc -l | tr -d ' ')"
  [ "$vies" != 0 ] && printf '  note        : %s uncommitted change(s) in the working tree\n' "$vies"
fi

# ── Tests ─────────────────────────────────────────────────────────────────────
if [ "$TOETSEN" = 1 ] && [ "$DROOG" = 0 ]; then
  stap "Tests"
  # PY= wins, then the project venv, then whatever python3 happens to be here.
  if [ -z "${PY:-}" ]; then
    PY="python3"
    [ -x "$SOURCE/.venv/bin/python" ] && PY="$SOURCE/.venv/bin/python"
  fi
  if ! "$PY" "$SOURCE/toets_frontend.py" >/tmp/deploy-toets.log 2>&1; then
    cat /tmp/deploy-toets.log; fout "toets_frontend.py failed — not deploying."; exit 1
  fi
  printf '  %s\n' "$(tail -1 /tmp/deploy-toets.log)"
  # The EVConduit suites need fastapi and httpx. Missing them is not a reason to
  # block a deploy, but it is a reason to say so rather than to look like it passed.
  if "$PY" -c 'import fastapi, httpx' 2>/dev/null; then
    for t in toets_evconduit.py toets_evconduit_api.py; do
      if ! "$PY" "$SOURCE/$t" >/tmp/deploy-toets.log 2>&1; then
        cat /tmp/deploy-toets.log; fout "$t failed — not deploying."; exit 1
      fi
      printf '  %s\n' "$(tail -1 /tmp/deploy-toets.log)"
    done
  else
    printf '  (fastapi/httpx not importable; EVConduit suites skipped)\n'
  fi
elif [ "$TOETSEN" = 0 ]; then
  stap "Tests skipped (--skip-tests)"
fi

# ── Copy ──────────────────────────────────────────────────────────────────────
stap "Copying"
AANTAL="$(bestandslijst | wc -l | tr -d ' ')"
printf '  %s files\n' "$AANTAL"
if [ "$DROOG" = 1 ]; then
  bestandslijst | sed 's/^/    /'
  printf '\nDry run: nothing copied, nothing built.\n'
  exit 0
fi

# Clear out AppleDouble droppings left by earlier copies. They are never legitimate
# and `COPY . .` bakes them into the image, where they sit next to the real files.
# Reported as the difference between two counts rather than as the first one: the
# number that matters is what actually went, not what we hoped to remove.
tel_troep() { ssh "$HOST" "find '$TARGET' \\( -name '._*' -o -name '.DS_Store' \\) | wc -l" 2>/dev/null | tr -d ' '; }
TROEP_VOOR="$(tel_troep)"
if [ -n "$TROEP_VOOR" ] && [ "$TROEP_VOOR" != 0 ]; then
  ssh "$HOST" "find '$TARGET' \\( -name '._*' -o -name '.DS_Store' \\) -delete"
  TROEP_NA="$(tel_troep)"
  printf '  removed %s macOS leftover file(s)\n' "$((TROEP_VOOR - TROEP_NA))"
fi

# COPYFILE_DISABLE=1 is the one that matters, and it is not obvious. bsdtar writes the
# macOS extended attributes into PAX headers; GNU tar on the far end does not ignore
# them, it reconstructs an AppleDouble `._name` file next to every single file to hold
# them. So a 64-file copy arrives as 128 files, and `COPY . .` then bakes the copies
# into the image. Measured: without this, 64 of 64 files gain a `._` twin; with it,
# none do. It also stops the "Ignoring unknown extended header keyword" warnings.
# --no-xattrs/--no-fflags are belt and braces for tar versions that need them.
bestandslijst | COPYFILE_DISABLE=1 tar --no-xattrs --no-fflags -cf - -T - \
  | ssh "$HOST" "tar -xf - -C '$TARGET'" || { fout "copy failed"; exit 1; }
printf '  copied\n'

# ── Build ─────────────────────────────────────────────────────────────────────
stap "Building the image and restarting"
# Keep the image we are replacing, so --rollback has somewhere to go.
if ssh "$HOST" "docker image inspect $IMAGE >/dev/null 2>&1"; then
  ssh "$HOST" "docker tag $IMAGE $PREVIOUS" && printf '  current image kept as %s\n' "$PREVIOUS"
fi

ssh "$HOST" "cd '$PROJECT' && $COMPOSE_CMD -f '$COMPOSE_FILE' up -d --build 2>&1 | tail -6" || {
  fout "build or restart failed"; exit 1; }

# ── Verify ────────────────────────────────────────────────────────────────────
stap "Verifying"
GEZOND=0
for _ in $(seq 1 30); do
  if ssh "$HOST" "curl -fsS -m 4 http://127.0.0.1:$PORT/healthz >/dev/null 2>&1"; then
    GEZOND=1; break
  fi
  sleep 2
done
[ "$GEZOND" = 1 ] || { fout "the viewer is not answering on port $PORT"; exit 1; }
printf '  /healthz          ok\n'

STATUS="$(ssh "$HOST" "curl -fsS -m 8 http://127.0.0.1:$PORT/api/evconduit/status" 2>/dev/null)"
printf '  evconduit status  %s\n' "${STATUS:-(absent — old image?)}"

VERSIE="$(ssh "$HOST" "curl -fsS -m 8 http://127.0.0.1:$PORT/ | grep -o 'app.js?v=[0-9]*' | head -1" 2>/dev/null)"
printf '  served JS         %s\n' "${VERSIE:-(unknown)}"

printf '\nDone. Hard-refresh the page (Ctrl/Cmd-Shift-R) if the browser still shows the old build.\n'
