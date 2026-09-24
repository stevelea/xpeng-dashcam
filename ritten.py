#!/usr/bin/env python3
"""Ritten afleiden uit de clip-tijden, en de afstand uit de snelheid in beeld."""
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store
import speed as speed_mod

GAP_SECONDS = 300
CLIP_SPAN_MAX = 65
STIL_KMH = 2          # hieronder telt de auto als stilstaand
STIL_CLIPS = 3        # zoveel stilstaande clips op rij = de rit is onderbroken


def _gemiddelde_snelheden(con):
    """Gemiddelde snelheid per clip, voor zover al gemeten."""
    return {r['ts']: r['g'] for r in con.execute(
        "SELECT c.ts AS ts, avg(s.kmh) AS g FROM speeds s JOIN clips c ON c.id = s.clip_id "
        "WHERE c.view='front' GROUP BY c.ts")}


def _knip_op_beweging(groep, snelheden):
    """Splitst een aaneengesloten opname op langere stilstand.

    De dashcam loopt door als de auto geparkeerd staat, dus een uur opname is niet
    hetzelfde als een uur rijden. Waar de snelheid bekend is, worden stilstaande
    stukken eruit geknipt. Is de snelheid niet gemeten, dan blijft de groep heel —
    liever grof dan verkeerd.
    """
    bekend = [t for t in groep if snelheden.get(t.isoformat(timespec='seconds')) is not None]
    if len(bekend) < len(groep) / 2:
        return [groep]

    def stil(t):
        g = snelheden.get(t.isoformat(timespec='seconds'))
        return g is not None and g < STIL_KMH

    segmenten, huidig, stilrij = [], [], []
    for t in groep:
        if stil(t):
            stilrij.append(t)
            continue
        if len(stilrij) >= STIL_CLIPS and huidig:
            segmenten.append(huidig)
            huidig = []
        elif stilrij:
            huidig.extend(stilrij)          # korte stop hoort gewoon bij de rit
        stilrij = []
        huidig.append(t)
    if huidig:
        segmenten.append(huidig)
    return [s for s in segmenten if s] or [groep]


def build(con=None):
    """Groepeert clips tot ritten: eerst op opnamepauzes, dan op stilstand."""
    own = con is None
    con = con or store.connect()
    rows = con.execute("SELECT ts FROM clips WHERE view='front' ORDER BY ts").fetchall()
    if not rows:
        return 0
    times = [datetime.fromisoformat(r['ts']) for r in rows]

    ruw, cur = [], [times[0]]
    for a, b in zip(times, times[1:]):
        if (b - a).total_seconds() > GAP_SECONDS:
            ruw.append(cur)
            cur = [b]
        else:
            cur.append(b)
    ruw.append(cur)

    snelheden = _gemiddelde_snelheden(con)
    groepen = []
    for g in ruw:
        groepen.extend(_knip_op_beweging(g, snelheden))

    # Handwerk (km, notitie, zakelijk) hoort bij het starttijdstip en overleeft het herindelen.
    bewaard = {r['start_ts']: (r['km'], r['measured'], r['note'], r['zakelijk'])
               for r in con.execute('SELECT start_ts, km, measured, note, zakelijk FROM trips')}
    # Een route hangt aan het ritnummer, en dat nummer verandert hieronder. Onthoud per starttijd
    # welke route erbij hoorde en hang hem na het indelen terug. Zonder dit verloor elke herindeling
    # alle routes buiten het venster van nieuwe_opnames.sh (gemeten 14-09-2026: 572 van 601 los).
    route_bij_start = {r['start_ts']: r['trip_id'] for r in con.execute(
        'SELECT t.start_ts, r.trip_id FROM routes r JOIN trips t ON t.id = r.trip_id')}
    con.execute('DELETE FROM trips')
    for g in groepen:
        start, eind = g[0], g[-1]
        seconden = int((eind - start).total_seconds()) + 60
        key = start.isoformat(timespec='seconds')
        km, measured, note, zakelijk = bewaard.get(key, (None, 0, None, 0))
        con.execute(
            'INSERT INTO trips (day, start_ts, end_ts, clips, seconds, km, measured, note, zakelijk) '
            'VALUES (?,?,?,?,?,?,?,?,?)',
            (start.strftime('%Y-%m-%d'), key, eind.isoformat(timespec='seconds'),
             len(g), seconden, km, measured, note, zakelijk))
    nieuw = {r['start_ts']: r['id'] for r in con.execute('SELECT id, start_ts FROM trips')}
    # Eerst naar tijdelijke negatieve nummers: trip_id is de sleutel van routes en mag niet botsen.
    for oud in route_bij_start.values():
        con.execute('UPDATE routes SET trip_id = ? WHERE trip_id = ?', (-oud, oud))
    for start, oud in route_bij_start.items():
        # Bestaat de starttijd niet meer (rit gesplitst of samengevoegd), dan blijft het oude nummer
        # staan; routes_bouwen.py maakt die rit later opnieuw.
        con.execute('UPDATE routes SET trip_id = ? WHERE trip_id = ?', (nieuw.get(start, oud), -oud))
    con.commit()
    herkoppel_waypoints(con)
    n = con.execute('SELECT count(*) FROM trips').fetchone()[0]
    if own:
        con.close()
    return n


def _clip_spans(rows):
    """Hoe lang elke clip meetelt: tot de start van de volgende, hoogstens 65 s."""
    out = []
    for i, r in enumerate(rows):
        if i + 1 < len(rows):
            d = (datetime.fromisoformat(rows[i + 1]['ts'])
                 - datetime.fromisoformat(r['ts'])).total_seconds()
            span = min(d, CLIP_SPAN_MAX)
        else:
            span = 60
        out.append(span)
    return out


def measure(trip_id, every=5, workers=6, con=None):
    """Meet de snelheid van elke clip in de rit en telt de afstand op."""
    own = con is None
    con = con or store.connect()
    trip = con.execute('SELECT * FROM trips WHERE id = ?', (trip_id,)).fetchone()
    if not trip:
        raise ValueError('rit bestaat niet')
    rows = con.execute(
        "SELECT id, path, ts FROM clips WHERE view='front' AND ts BETWEEN ? AND ? ORDER BY ts",
        (trip['start_ts'], trip['end_ts'])).fetchall()
    spans = _clip_spans(rows)

    todo = [r for r in rows
            if not con.execute('SELECT 1 FROM speeds WHERE clip_id = ? LIMIT 1',
                               (r['id'],)).fetchone()]
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(
                lambda r: (r['id'], speed_mod.sample_clip(r['path'], every=every)), todo))
        for cid, samples in results:
            con.executemany('INSERT OR REPLACE INTO speeds (clip_id, offset_s, kmh) VALUES (?,?,?)',
                            [(cid, o, k) for o, k in samples])
        con.commit()

    km = 0.0
    gemeten = 0
    for r, span in zip(rows, spans):
        s = con.execute('SELECT kmh FROM speeds WHERE clip_id = ?', (r['id'],)).fetchall()
        if not s:
            continue
        gemiddeld = sum(x['kmh'] for x in s) / len(s)
        km += gemiddeld * span / 3600.0
        gemeten += 1

    con.execute('UPDATE trips SET km = ?, measured = ? WHERE id = ?',
                (round(km, 1), gemeten, trip_id))
    con.commit()
    # LET OP: hier NIET opnieuw indelen. build() maakt alle ritten opnieuw aan en dan
    # kloppen de nummers van andere ritten niet meer — dat brak een lopende reeks
    # metingen af. Draai build() + herbereken_km() pas na een hele reeks.
    if own:
        con.close()
    return {'km': round(km, 1), 'clips_gemeten': gemeten, 'clips_totaal': len(rows)}


def herkoppel_waypoints(con, marge_min=20):
    """Hangt de ankerpunten weer aan de juiste rit.

    build() maakt alle ritten opnieuw aan, dus de nummers verschuiven en de punten
    raken los. Ze hebben een tijdstip, dus daarop is opnieuw te koppelen. Punten die
    net buiten een rit vallen gaan naar de dichtstbijzijnde rit binnen de marge.

    ⚠️ Eerst dubbelen opruimen. Eenzelfde foto-punt kan aan meerdere ritten blijven
    hangen; komen die door het herkoppelen op dezelfde rit uit, dan botsen ze op de
    sleutel (trip_id, ts, source) en breekt de hele herberekening af. Weggegooid wordt
    alleen wat op EXACT dezelfde plek ligt — staat er een dubbele met andere
    coordinaten, dan blijft die staan en loopt het bewust stuk, want dan is er iets
    anders aan de hand dan een dubbeling."""
    con.execute("""
        DELETE FROM waypoints WHERE rowid NOT IN (
            SELECT min(rowid) FROM waypoints
            GROUP BY ts, source, round(lat, 6), round(lon, 6))
    """)
    con.execute("""
        UPDATE waypoints SET trip_id = COALESCE(
            (SELECT t.id FROM trips t WHERE waypoints.ts BETWEEN t.start_ts AND t.end_ts LIMIT 1),
            trip_id)
    """)
    los = con.execute("""
        SELECT w.rowid AS rid, w.ts FROM waypoints w
        WHERE NOT EXISTS (SELECT 1 FROM trips t WHERE t.id = w.trip_id
                          AND w.ts BETWEEN t.start_ts AND t.end_ts)
    """).fetchall()
    hersteld = 0
    for w in los:
        t = con.execute("""
            SELECT id FROM trips
            ORDER BY MIN(ABS(strftime('%s', start_ts) - strftime('%s', ?)),
                         ABS(strftime('%s', end_ts)   - strftime('%s', ?))) LIMIT 1
        """, (w['ts'], w['ts'])).fetchone()
        if not t:
            continue
        r = con.execute('SELECT start_ts, end_ts FROM trips WHERE id = ?', (t['id'],)).fetchone()
        from datetime import datetime as _dt
        ts = _dt.fromisoformat(w['ts'])
        s_, e_ = _dt.fromisoformat(r['start_ts']), _dt.fromisoformat(r['end_ts'])
        binnen = min(abs((ts - s_).total_seconds()), abs((ts - e_).total_seconds())) / 60
        if binnen <= marge_min:
            con.execute('UPDATE waypoints SET trip_id = ? WHERE rowid = ?', (t['id'], w['rid']))
            hersteld += 1
    con.commit()
    return hersteld


def herbereken_km(con=None):
    """Rekent de afstand opnieuw uit de al gemeten snelheden — zonder ffmpeg.

    Na een nieuwe rit-indeling verschuiven de grenzen; de metingen per clip blijven
    bestaan, dus de kilometers kunnen er zo weer uit."""
    own = con is None
    con = con or store.connect()
    bijgewerkt = 0
    for t in con.execute('SELECT id, start_ts, end_ts FROM trips').fetchall():
        rows = con.execute(
            "SELECT id, ts FROM clips WHERE view='front' AND ts BETWEEN ? AND ? ORDER BY ts",
            (t['start_ts'], t['end_ts'])).fetchall()
        if not rows:
            continue
        spans = _clip_spans(rows)
        km, gemeten = 0.0, 0
        for r, span in zip(rows, spans):
            s = con.execute('SELECT kmh FROM speeds WHERE clip_id = ?', (r['id'],)).fetchall()
            if not s:
                continue
            km += sum(x['kmh'] for x in s) / len(s) * span / 3600.0
            gemeten += 1
        if gemeten:
            con.execute('UPDATE trips SET km = ?, measured = ? WHERE id = ?',
                        (round(km, 1), gemeten, t['id']))
            bijgewerkt += 1
    con.commit()
    if own:
        con.close()
    return bijgewerkt


if __name__ == '__main__':
    n = build()
    k = herbereken_km()
    print(f'{n} ritten, kilometers herberekend voor {k}')
