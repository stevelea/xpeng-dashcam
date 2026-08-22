#!/bin/bash
# Werkt de viewer bij na nieuwe opnames: index, miniaturen, ritten en locaties.
# Draaien mag altijd — wat er al is blijft staan.
set -e
cd "$(dirname "$0")"
P=.venv/bin/python

echo "== 0/4 database veiligstellen =="
./backup_db.sh

echo "== 1/4 index bijwerken =="
$P scan.py

echo "== 2/4 miniaturen maken =="
caffeinate -i $P thumbs.py

echo "== 3/4 ritten opnieuw indelen =="
$P ritten.py

echo "== 4/4 locaties uit foto's koppelen =="
$P -c "import fotos; print(fotos.link_all(geocode=True))"

echo "== klaar =="
