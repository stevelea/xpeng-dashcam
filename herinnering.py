#!/usr/bin/env python3
"""Stuurt een seintje als het dashcam-archief achterloopt.

De beelden komen alleen binnen als de gebruiker de stick uitleest. Loopt dat te lang,
dan kunnen nieuwe ritten niet aan een route gekoppeld worden. Dit script kijkt hoe oud
de nieuwste opname is en stuurt na een instelbaar aantal dagen een melding.

Niet zeuren: hooguit één melding per week.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import store

_CFG = store.load_config().get('herinnering') or {}
GRENS_DAGEN = _CFG.get('grens_dagen', 21)
STILTE_DAGEN = _CFG.get('stilte_dagen', 7)
HA_URL = _CFG.get('ha_url', '')
DIENST = _CFG.get('dienst', '')


def ha_token():
    t = os.environ.get('HA_TOKEN')
    if t:
        return t
    # Bestand met HA_TOKEN=..., in te stellen als herinnering.token_bestand in config.json
    env = Path(_CFG.get('token_bestand') or '~/.config/xpeng-dashcam/env').expanduser()
    if env.exists():
        for regel in env.read_text().splitlines():
            if regel.startswith('HA_TOKEN='):
                return regel.split('=', 1)[1].strip()
    return None


def stuur(titel, bericht):
    t = ha_token()
    if not t:
        return False, 'geen HA-token'
    try:
        r = httpx.post(f'{HA_URL}/api/services/{DIENST}',
                       headers={'Authorization': f'Bearer {t}',
                                'Content-Type': 'application/json'},
                       json={'title': titel, 'message': bericht}, timeout=20)
        r.raise_for_status()
        return True, 'verstuurd'
    except Exception as exc:
        return False, f'{exc.__class__.__name__}: {exc}'


def controleer(stuur_echt=True):
    con = store.connect()
    laatste = con.execute('SELECT max(day) FROM clips').fetchone()[0]
    if not laatste:
        con.close()
        return {'status': 'geen clips'}

    ouderdom = (date.today() - date.fromisoformat(laatste)).days
    vorige = store.get_meta(con, 'herinnering_verstuurd')
    net_gestuurd = bool(vorige) and \
        (date.today() - date.fromisoformat(vorige[:10])).days < STILTE_DAGEN

    uit = {'laatste_opname': laatste, 'dagen_oud': ouderdom,
           'grens': GRENS_DAGEN, 'gestuurd': False}

    if ouderdom < GRENS_DAGEN:
        uit['status'] = 'bij'
    elif net_gestuurd:
        uit['status'] = f'achter, maar al gemeld op {vorige[:10]}'
    else:
        weken = ouderdom // 7
        ok, hoe = (stuur(
            'Dashcam loopt achter',
            f'De nieuwste opname is van {laatste}, {ouderdom} dagen geleden '
            f'({weken} weken). Steek de stick in de NAS, dan haal ik ze op.'
        ) if stuur_echt else (True, 'proefdraai'))
        uit['status'] = 'gemeld' if ok else f'melden mislukt: {hoe}'
        uit['gestuurd'] = ok
        if ok and stuur_echt:
            store.set_meta(con, 'herinnering_verstuurd', datetime.now().astimezone().isoformat())
            con.commit()
    con.close()
    return uit


if __name__ == '__main__':
    print(json.dumps(controleer(stuur_echt='--proef' not in sys.argv),
                     ensure_ascii=False, indent=2))
