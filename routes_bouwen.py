#!/usr/bin/env python3
"""Bouwt routes voor een reeks ritten. Ritnummers verschuiven bij een herindeling,
dus selecteren gaat op datum, niet op nummer."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store, route


def kies(con, aantal=20, vanaf=None):
    sql = '''SELECT t.id, t.day, t.start_ts, t.end_ts, t.km,
                    (SELECT count(*) FROM waypoints w
                      WHERE w.trip_id = t.id AND w.source != 'gelezen') AS ankers
             FROM trips t'''
    args = []
    if vanaf:
        sql += ' WHERE t.day >= ?'
        args.append(vanaf)
    sql += ' ORDER BY t.start_ts DESC LIMIT ?'
    args.append(aantal)
    return con.execute(sql, args).fetchall()


def run(aantal=20, vanaf=None):
    con = store.connect()
    ritten = kies(con, aantal, vanaf)
    print(f'{len(ritten)} ritten\n', flush=True)
    uit = {'gemeten': 0, 'gereconstrueerd': 0, 'geen lijn': 0}
    for t in ritten:
        try:
            r = route.bouw(t['id'], con=con)
        except Exception as exc:
            print(f"  #{t['id']} {t['day']}  FOUT {exc.__class__.__name__}: {exc}", flush=True)
            continue
        if not r['heeft_lijn']:
            uit['geen lijn'] += 1
            merk = 'geen lijn'
        else:
            uit[r['soort']] += 1
            merk = f"{r['soort']} · {r['route_km']} km over de weg"
        print(f"  #{t['id']} {t['day']} {t['start_ts'][11:16]}-{t['end_ts'][11:16]}  "
              f"{t['ankers']} ankers → {r['punten']} punten  {merk}", flush=True)
    con.close()
    print(f'\n{uit}')
    return uit


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    vanaf = sys.argv[2] if len(sys.argv) > 2 else None
    run(n, vanaf)
