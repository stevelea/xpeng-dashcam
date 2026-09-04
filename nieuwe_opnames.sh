#!/bin/bash
# Werkt de viewer bij na nieuwe opnames: index, miniaturen, ritten en locaties.
# Draaien mag altijd — wat er al is blijft staan.
set -e
cd "$(dirname "$0")"
P=.venv/bin/python

NAS=${NAS:-root@192.168.1.218}

echo "== 0/5 beelden van de stick halen =="
# Zit er een stick in de NAS, dan die eerst leegtrekken. Geen stick, NAS niet
# bereikbaar of geen nieuwe beelden? Dan gewoon door — dit mag de rest nooit blokkeren.
# ⚠️ Het script op de NAS VERPLAATST: de stick blijft leeg achter, zodat de dashcam
# door kan met opnemen. Verwijderen gebeurt pas na een controle op bytegrootte.
if ssh -o ConnectTimeout=8 -o BatchMode=yes "$NAS" true 2>/dev/null; then
  STICK=$(ssh "$NAS" 'for d in /usbvolume/*/; do [ -d "$d/XP_DCIM" ] && echo "${d%/}" && break; done' 2>/dev/null)
  if [ -n "$STICK" ]; then
    AANTAL=$(ssh "$NAS" "find '$STICK/XP_DCIM' -type f -name '*.mp4' | wc -l" 2>/dev/null || echo 0)
    if [ "${AANTAL:-0}" -gt 0 ]; then
      echo "   stick gevonden: $STICK ($AANTAL clips)"
      scp -q nas-scripts/xpeng_from_stick.sh "$NAS":/tmp/ 2>/dev/null || true
      ssh "$NAS" "sh /tmp/xpeng_from_stick.sh '$STICK' go" 2>&1 | tail -6 || true
    else
      echo "   stick zit erin maar is al leeg"
    fi
  else
    echo "   geen stick in de NAS — overslaan"
  fi
else
  echo "   NAS niet bereikbaar — overslaan"
fi

echo "== 1/5 database veiligstellen =="
./backup_db.sh

echo "== 2/5 index bijwerken =="
$P scan.py

echo "== 3/5 miniaturen maken =="
caffeinate -i $P thumbs.py

echo "== 4/5 ritten opnieuw indelen =="
$P ritten.py

echo "== 5/5 locaties uit foto's koppelen =="
$P -c "import fotos; print(fotos.link_all(geocode=True))"

echo "== klaar =="
