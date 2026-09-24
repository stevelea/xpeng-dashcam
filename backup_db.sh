#!/bin/bash
# Veilige kopie van de database, ook als de app draait. Bewaart de laatste 7.
set -e
cd "$(dirname "$0")"
mkdir -p data/backups
STAMP=$(date +%Y%m%d-%H%M%S)
.venv/bin/python -c "
import sqlite3, store
bron = sqlite3.connect(store.DB_PATH)
doel = sqlite3.connect('data/backups/clips-$STAMP.db')
bron.backup(doel)
doel.close(); bron.close()
print('data/backups/clips-$STAMP.db')
"
ls -1t data/backups/clips-*.db | tail -n +8 | xargs -r rm --
