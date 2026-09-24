#!/bin/bash
# Werkt de viewer bij na nieuwe opnames: index, miniaturen, ritten en locaties.
# Draaien mag altijd — wat er al is blijft staan.
set -e
cd "$(dirname "$0")"
P=.venv/bin/python

# Adres van de NAS waar de dashcam-stick in zit, als user@host. Staat bewust
# NIET in dit bestand: zet hem in config.json onder nas.ssh, of geef hem mee
# als NAS=... voor het commando. Leeg = stap 0 wordt overgeslagen.
NAS=${NAS:-$($P -c "import store;print((store.load_config().get('nas') or {}).get('ssh',''))" 2>/dev/null)}

echo "== 0/6 beelden van de stick halen =="
# Zit er een stick in de NAS, dan die eerst leegtrekken. Geen stick, NAS niet
# bereikbaar of geen nieuwe beelden? Dan gewoon door — dit mag de rest nooit blokkeren.
# ⚠️ Het script op de NAS VERPLAATST: de stick blijft leeg achter, zodat de dashcam
# door kan met opnemen. Verwijderen gebeurt pas na een controle op bytegrootte.
if [ -n "$NAS" ] && ssh -o ConnectTimeout=8 -o BatchMode=yes "$NAS" true 2>/dev/null; then
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

echo "== 1/6 database veiligstellen =="
./backup_db.sh

echo "== 2/6 index bijwerken =="
$P scan.py

echo "== 3/6 miniaturen maken =="
caffeinate -i $P thumbs.py

echo "== 4/6 ritten opnieuw indelen =="
$P ritten.py

echo "== 5/6 routes bouwen (laatste 30 dagen) =="
# Alleen recent: verder terug heeft de logger geen posities, dus daar valt niets te
# meten. Het venster schuift vanzelf mee.
VANAF=$(date -v-30d +%F 2>/dev/null || date -d "30 days ago" +%F)
# Eerst de oude weg (ankerpunten), daarna de tracker eroverheen: die legt
# dezelfde GPS-punten met map-matching op de weg en is dus beter. Deze
# volgorde zorgt dat de betere lijn wint.
$P routes_bouwen.py 60 "$VANAF"
$P route_uit_tracker.py "$VANAF"

echo "== 6/6 locaties uit foto's koppelen =="
$P -c "import fotos; print(fotos.link_all(geocode=True))"

echo "== klaar =="
