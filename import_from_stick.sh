#!/usr/bin/env bash
# Move dashcam clips from a USB stick into your archive folder.
#
# MOVE, not copy: the stick has to end up empty, otherwise it fills up and the
# dashcam stops recording. A file is only deleted from the stick once it exists in
# the destination with the SAME byte size and larger than zero. If that check fails
# the file stays where it is and the script says why - silence is worse than mess.
#
# Files are sorted into YYYY/MM folders taken from the FILE NAME. The file's
# modification date is the moment you copied it and is not reliable.
#
# Without "go" the script only shows what it would do.
#
#   ./import_from_stick.sh <source-folder> <destination-folder> [go]
set -u

BRON="${1:-}"
DOEL="${2:-}"
GO="${3:-}"

[ -n "$BRON" ] && [ -n "$DOEL" ] || { echo "usage: $0 <source-folder> <destination-folder> [go]"; exit 2; }
[ -d "$BRON" ] || { echo "source does not exist: $BRON"; exit 2; }
[ -d "$DOEL" ] || { echo "destination does not exist: $DOEL"; exit 2; }

[ "$GO" = "go" ] || echo "DRY RUN - nothing is moved. Add 'go' as the third argument to do it for real."
echo "source:      $BRON"
echo "destination: $DOEL"
echo

verplaatst=0; overgeslagen=0; fout=0

# -print0 zodat spaties in namen niets slopen
find "$BRON" -type f -iname '*.mp4' -print0 | while IFS= read -r -d '' pad; do
  naam=$(basename "$pad")
  # 14 tot 17 cijfers = JJJJMMDDuummss(mmm)
  stamp=$(printf '%s' "$naam" | grep -oE '[0-9]{14,17}' | head -1)
  if [ -z "$stamp" ]; then
    echo "SKIP  $naam - no timestamp in the file name"
    overgeslagen=$((overgeslagen + 1)); continue
  fi
  jaar=${stamp:0:4}; maand=${stamp:4:2}
  map="$DOEL/$jaar/$maand"
  doelpad="$map/$naam"

  bron_bytes=$(wc -c < "$pad" | tr -d ' ')
  if [ "$bron_bytes" -eq 0 ]; then
    echo "SKIP  $naam - zero bytes"
    overgeslagen=$((overgeslagen + 1)); continue
  fi

  if [ "$GO" != "go" ]; then
    echo "WOULD MOVE  $naam -> $jaar/$maand/"
    continue
  fi

  mkdir -p "$map"
  if [ ! -f "$doelpad" ]; then
    cp -p "$pad" "$doelpad" || { echo "FAIL  $naam - copy failed"; fout=$((fout + 1)); continue; }
  fi

  doel_bytes=$(wc -c < "$doelpad" 2>/dev/null | tr -d ' ')
  if [ "${doel_bytes:-0}" -eq "$bron_bytes" ] && [ "${doel_bytes:-0}" -gt 0 ]; then
    rm -f "$pad"
    echo "MOVED $naam -> $jaar/$maand/"
    verplaatst=$((verplaatst + 1))
  else
    echo "KEEP  $naam - size mismatch (source $bron_bytes, destination ${doel_bytes:-missing})"
    fout=$((fout + 1))
  fi
done

echo
echo "Done. Run scan.py, thumbs.py and ritten.py to pick up the new footage."
