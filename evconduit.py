#!/usr/bin/env python3
"""Wat de auto zelf van een rit weet, opgehaald bij EVConduit.

De dashcam en de auto beschrijven dezelfde rit en hebben geen enkele sleutel
gemeen. Onze ritten zijn rijnummers die bij elke herindeling opnieuw worden
uitgedeeld (zie ritten.build()); die van EVConduit zijn UUID's uit een
XPENG-export. Een dashcam-bestandsnaam bevat geen VIN. Er blijft dus maar één
ding over om op te koppelen: **de tijd**.

En zelfs de tijd is niet hetzelfde: de dashcam schrijft lokale tijd in de
bestandsnaam, de auto meldt UTC via XPENG. Daar komt een derde klok bij — de
GPS-logger. Twee minuten verschil is gewoon, en dat is precies waarom EVConduit
zelf al met een `pad_seconds` werkt. Wij doen hetzelfde met `marge_s`, maar we
verbergen de afwijking niet: hij gaat mee in het antwoord, want een programma dat
stilzwijgend 90 seconden wegpoetst beweert een nauwkeurigheid die het niet heeft.

Twee dingen die dit bestand expres NIET doet:

* **De afstand van de auto vervangt niet die van ons.** Onze kilometers komen uit
  de snelheid die in het beeld staat (OCR), die van de auto uit 1 Hz CAN-data.
  Het zijn twee metingen van hetzelfde, dus ze horen naast elkaar te staan. Een
  verschil tussen die twee is het interessantste dat deze functie oplevert.
* **Een rit die alleen op de marge past wordt niet als "gevonden" gepresenteerd.**
  Dat heet hier `twijfel` en het wordt ook zo teruggegeven.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

TIJDSLIMIET = 20
MAX_PUNTEN = 1500

# Welk deel van ONZE rit moet door de rit van de auto gedekt zijn voordat we het
# een treffer noemen. Daaronder is het een vermoeden en dat zeggen we ook.
ZEKER_VANAF = 0.5
# Twee ritten van de auto die allebei een flink stuk van de onze dekken: dan is de
# indeling kennelijk anders en moet een mens kijken, niet wij.
DUBBEL_VANAF = 0.3


class Fout(Exception):
    """Iets mis met EVConduit zelf: niet ingesteld, onbereikbaar, of geweigerd."""


# ── Instellingen ──────────────────────────────────────────────────────────────
# Zodat de testknop kan proberen wat er in het formulier staat voordat het bewaard
# is. Zonder dit moet je eerst een verkeerde sleutel opslaan om te ontdekken dat
# hij verkeerd is.
_tijdelijk = {}


def tijdelijk(url=None, sleutel=None, marge_s=None):
    global _tijdelijk
    _tijdelijk = {'url': url or None, 'sleutel': sleutel or None, 'marge_s': marge_s}


def wis_tijdelijk():
    global _tijdelijk
    _tijdelijk = {}


def instellingen():
    cfg = dict(store.load_config().get('evconduit') or {})
    if _tijdelijk.get('url'):
        cfg['url'] = _tijdelijk['url']
    if _tijdelijk.get('sleutel'):
        cfg['sleutel'] = _tijdelijk['sleutel']
    if _tijdelijk.get('marge_s') is not None:
        cfg['marge_s'] = _tijdelijk['marge_s']
    basis = (cfg.get('url') or '').strip().rstrip('/')
    sleutel = (cfg.get('sleutel') or '').strip()
    try:
        marge = int(cfg.get('marge_s', 180))
    except (TypeError, ValueError):
        marge = 180
    return {'url': basis, 'sleutel': sleutel, 'marge_s': max(0, min(marge, 3600)),
            'aan': bool(cfg.get('aan', True))}


def _basis():
    """Het adres van de API. Accepteert .../ zowel als .../api als beginpunt."""
    cfg = instellingen()
    if not cfg['url'] or not cfg['sleutel']:
        raise Fout('EVConduit is niet ingesteld')
    basis = cfg['url']
    if not basis.endswith('/api'):
        basis += '/api'
    return basis, cfg['sleutel']


def _kop():
    basis, sleutel = _basis()
    return basis, {'Authorization': f'Bearer {sleutel}',
                   'Accept': 'application/json',
                   'User-Agent': 'xpeng-dashcam/1.0'}


def ingesteld():
    cfg = instellingen()
    return bool(cfg['aan'] and cfg['url'] and cfg['sleutel'])


# ── Tijd ──────────────────────────────────────────────────────────────────────
def _utc(waarde):
    """Een tijdstip van EVConduit naar UTC. 'Z' komt voor, leeg ook."""
    if not waarde:
        return None
    try:
        d = datetime.fromisoformat(str(waarde).replace('Z', '+00:00'))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _naief(waarde):
    """Een tijdstip zonder zone, of None als het geen tijdstip is."""
    try:
        d = datetime.fromisoformat(str(waarde).replace(' ', 'T'))
    except ValueError:
        return None
    return d.replace(tzinfo=None)


def _ons_venster(trip):
    """De rit van de dashcam als UTC-venster.

    Onze tijd is lokale tijd zonder zone — de bestandsnaam zegt niets over zones —
    dus de zone uit config.json bepaalt wat het in UTC is. Per aanroep opzoeken,
    zodat een gewijzigde tijdzone meteen geldt en niet pas na een herstart.
    """
    tz = store.tijdzone()
    start, eind = _naief(trip['start_ts']), _naief(trip['end_ts'])
    if start is None or eind is None:
        return None
    return (start.replace(tzinfo=tz).astimezone(timezone.utc),
            eind.replace(tzinfo=tz).astimezone(timezone.utc))


# ── Ophalen ───────────────────────────────────────────────────────────────────
def _haal(basis, kop, pad, params=None):
    try:
        r = httpx.get(basis + pad, params=params, headers=kop, timeout=TIJDSLIMIET)
    except Exception as exc:
        raise Fout(f'EVConduit niet bereikbaar: {exc}')
    if r.status_code in (401, 403):
        raise Fout('EVConduit weigert de sleutel')
    if r.status_code == 404:
        return None
    if r.status_code >= 400:
        raise Fout(f'EVConduit gaf {r.status_code}')
    try:
        return r.json()
    except ValueError:
        raise Fout('EVConduit gaf geen leesbaar antwoord')


def ritten():
    """Alle ritten die EVConduit voor deze gebruiker heeft, nieuwste eerst."""
    basis, kop = _kop()
    d = _haal(basis, kop, '/user/xpeng/trips')
    return (d or {}).get('trips') or []


def toets():
    """Voor de instellingenpagina: werken het adres en de sleutel?"""
    try:
        rijen = ritten()
    except Fout as exc:
        return {'ok': False, 'reden': str(exc)}
    if not rijen:
        return {'ok': True, 'ritten': 0,
                'melding': 'De sleutel werkt, maar er staan nog geen ritten in EVConduit.'}
    nieuwste = max((r.get('started_at') or '') for r in rijen)
    return {'ok': True, 'ritten': len(rijen), 'nieuwste': nieuwste}


# ── Koppelen op tijd ──────────────────────────────────────────────────────────
def _kandidaten(ons, rijen, marge_s):
    """Ritten van de auto die onze rit kunnen zijn, beste eerst.

    Twee cijfers per kandidaat, en het verschil ertussen is de hele reden dat dit
    een functie is:

    * `dekking` — welk deel van ONZE rit door die van de auto gedekt wordt. Dat
      bepaalt of we het een treffer noemen.
    * de afwijkingen — hoeveel later de auto zegt dat de rit begon en eindigde.
      Een constante afwijking is klokverschil; een wisselende is iets anders, en
      dan moet je niet aan elkaar plakken wat niet bij elkaar hoort.
    """
    d_start, d_eind = ons
    zoek_van = d_start - timedelta(seconds=marge_s)
    zoek_tot = d_eind + timedelta(seconds=marge_s)
    onze_duur = max(1.0, (d_eind - d_start).total_seconds())

    uit = []
    for r in rijen:
        e_start, e_eind = _utc(r.get('started_at')), _utc(r.get('ended_at'))
        if e_start is None or e_eind is None:
            continue
        # Kan deze rit überhaupt binnen het gezochte venster vallen?
        if e_eind < zoek_van or e_start > zoek_tot:
            continue
        raak = (min(d_eind, e_eind) - max(d_start, e_start)).total_seconds()
        uit.append({
            'rit': _dun(r),
            'dekking': round(max(0.0, raak) / onze_duur, 3),
            'overlap_s': int(max(0.0, raak)),
            'start_afwijking_s': int((e_start - d_start).total_seconds()),
            'eind_afwijking_s': int((e_eind - d_eind).total_seconds()),
            'duur_auto_s': int((e_eind - e_start).total_seconds()),
        })
    uit.sort(key=lambda k: (k['overlap_s'], k['dekking']), reverse=True)
    return uit


# De velden die we bewaren. `user_id` en `export_id` gaan eruit: die zeggen de
# dashcam niets en horen niet in een cache thuis.
_VELDEN = ('id', 'vin', 'started_at', 'ended_at', 'duration_seconds', 'moving_seconds',
           'distance_km', 'odometer_start', 'odometer_end', 'max_speed_kmh',
           'mean_moving_speed_kmh', 'energy_kwh', 'regen_kwh', 'soc_start', 'soc_end')


def _dun(rij):
    return {k: rij.get(k) for k in _VELDEN}


def _spoor(xpeng_id, marge_s):
    """Het gereden spoor bij deze rit, als er een logger naar EVConduit post.

    EVConduit antwoordt altijd met `available`, want "geen spoor" is de gewone
    toestand voor iemand zonder logger. De reden reist mee, zodat wij kunnen zeggen
    wat er aan de hand is in plaats van een leeg vak te tonen.
    """
    basis, kop = _kop()
    d = _haal(basis, kop, f'/user/xpeng/trips/{xpeng_id}/track',
              {'max_points': MAX_PUNTEN, 'pad_seconds': marge_s})
    if not d:
        return None
    lat, lon = d.get('lat') or [], d.get('lon') or []
    lijn = None
    if d.get('available') and len(lat) >= 2 and len(lat) == len(lon):
        # GeoJSON is [lon, lat] — precies omgekeerd aan hoe het hier gelezen wordt.
        lijn = {'type': 'LineString',
                'coordinates': [[round(lo, 6), round(la, 6)] for la, lo in zip(lat, lon)]}
    return {
        'beschikbaar': bool(d.get('available')),
        'reden': d.get('reason'),
        'geojson': lijn,
        'punten': d.get('point_count') or 0,
        'punten_bron': d.get('source_point_count') or 0,
        'dekking': d.get('coverage'),
        'gedekt_s': d.get('covered_seconds'),
        'rit_s': d.get('trip_seconds'),
        'grootste_gat_s': d.get('largest_gap_seconds'),
        'spoor_km': d.get('track_distance_km'),
        'venster': d.get('window'),
    }


# ── Het antwoord dat de app gebruikt ──────────────────────────────────────────
def _leeg(reden, **extra):
    return {'beschikbaar': False, 'reden': reden, 'rit': None, 'spoor': None,
            'kandidaten': [], **extra}


def koppel(con, trip, forceer=False):
    """Zoek de rit van de auto bij deze dashcam-rit, en bewaar wat we vinden.

    De sleutel in de cache is onze eigen `start_ts`. Opnieuw ophalen kan altijd met
    forceer=True; standaard gebruiken we wat er staat, want een rit van gisteren
    verandert niet meer en EVConduit is een externe dienst.
    """
    start_ts = trip['start_ts']

    # Uitgeschakeld is uit, ook voor wat al bewaard is. Anders doet de schakelaar in
    # de instellingen niet wat erop staat.
    if not instellingen()['aan']:
        return _leeg('geen_evconduit')

    # De cache gaat vóór de vraag of het ingesteld is. Een adres tijdelijk weghalen
    # of een sleutel intypen mag de gegevens van gisteren niet van het scherm halen:
    # die zijn al opgehaald en blijven een eigenschap van de rit.
    if not forceer:
        rij = con.execute('SELECT * FROM xpeng_ritten WHERE start_ts = ?', (start_ts,)).fetchone()
        if rij:
            return _uit_cache(rij)

    if not ingesteld():
        return _leeg('geen_evconduit')

    try:
        rijen = ritten()
    except Fout as exc:
        return _leeg('onbereikbaar', melding=str(exc))

    ons = _ons_venster(trip)
    if ons is None:
        return _leeg('geen_tijd')

    marge_s = instellingen()['marge_s']
    kandidaten = _kandidaten(ons, rijen, marge_s)
    if not kandidaten:
        _bewaar(con, start_ts, None, None, None, None, marge_s, 0, None)
        return _leeg('geen_rit')

    beste = kandidaten[0]
    dubbel = [k for k in kandidaten[1:] if k['dekking'] >= DUBBEL_VANAF]
    twijfel = int(beste['dekking'] < ZEKER_VANAF)
    afwijking = {'start_s': beste['start_afwijking_s'], 'eind_s': beste['eind_afwijking_s']}

    spoor = None
    if beste['dekking'] >= ZEKER_VANAF:
        try:
            spoor = _spoor(beste['rit']['id'], marge_s)
        except Fout as exc:
            # De rit is gevonden, alleen het spoor lukte niet. Dat is geen reden om
            # de gegevens van de auto zelf weg te gooien.
            spoor = {'beschikbaar': False, 'reden': 'onbereikbaar', 'melding': str(exc),
                     'geojson': None, 'punten': 0, 'punten_bron': 0, 'dekking': None,
                     'gedekt_s': None, 'rit_s': None, 'grootste_gat_s': None,
                     'spoor_km': None, 'venster': None}

    _bewaar(con, start_ts, beste['rit'], spoor, beste['dekking'], dubbel, marge_s, twijfel,
            afwijking)

    return _uit_cache(con.execute('SELECT * FROM xpeng_ritten WHERE start_ts = ?',
                                  (start_ts,)).fetchone())


def _bewaar(con, start_ts, rit, spoor, dekking, dubbel, marge_s, twijfel, afwijking):
    inhoud = json.dumps({'spoor': spoor, 'dubbel': dubbel or [],
                         'afwijking': afwijking}) if (spoor or dubbel or afwijking) else None
    con.execute(
        'INSERT OR REPLACE INTO xpeng_ritten '
        '(start_ts, xpeng_id, vin, rit, spoor, dekking, marge_s, twijfel, opgehaald) '
        'VALUES (?,?,?,?,?,?,?,?,?)',
        (start_ts,
         (rit or {}).get('id'),
         (rit or {}).get('vin'),
         json.dumps(rit) if rit else None,
         inhoud,
         dekking, marge_s, twijfel,
         datetime.now().astimezone().isoformat(timespec='seconds')))
    con.commit()


def _uit_cache(rij):
    if rij is None:
        return _leeg('geen_rit')

    rit = json.loads(rij['rit']) if rij['rit'] else None
    bewaard = json.loads(rij['spoor']) if rij['spoor'] else {}
    spoor, dubbel = bewaard.get('spoor'), (bewaard.get('dubbel') or [])
    afwijking = bewaard.get('afwijking')

    if rit is None:
        return _leeg('geen_rit', opgehaald=rij['opgehaald'])

    if rij['twijfel']:
        return {'beschikbaar': False, 'reden': 'twijfel', 'rit': rit, 'spoor': None,
                'kandidaten': dubbel, 'dekking': rij['dekking'], 'afwijking': afwijking,
                'marge_s': rij['marge_s'], 'opgehaald': rij['opgehaald']}

    return {'beschikbaar': True, 'reden': None, 'rit': rit, 'spoor': spoor,
            'kandidaten': dubbel, 'dekking': rij['dekking'], 'afwijking': afwijking,
            'marge_s': rij['marge_s'], 'opgehaald': rij['opgehaald']}


def status(con):
    """Hoeveel van onze ritten hebben gegevens van de auto?"""
    r = con.execute('SELECT count(*) n, sum(1 - twijfel) zeker, max(opgehaald) laatste '
                    'FROM xpeng_ritten').fetchone()
    totaal = con.execute('SELECT count(*) n FROM trips').fetchone()['n']
    cfg = instellingen()
    return {'ingesteld': ingesteld(), 'url': cfg['url'], 'marge_s': cfg['marge_s'],
            'heeft_sleutel': bool(cfg['sleutel']),
            'gekoppeld': r['zeker'] or 0, 'geprobeerd': r['n'] or 0,
            'ritten': totaal, 'laatste': r['laatste']}


def vergeet(con, start_ts=None):
    if start_ts:
        con.execute('DELETE FROM xpeng_ritten WHERE start_ts = ?', (start_ts,))
    else:
        con.execute('DELETE FROM xpeng_ritten')
    con.commit()
    return True


if __name__ == '__main__':
    print(json.dumps(toets(), indent=2, ensure_ascii=False))
