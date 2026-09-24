#!/usr/bin/env python3
"""Snelle controle op de voorkant: bestaan alle elementen die de code zoekt, en
staan alle aangeroepen functies er nog?

Aanleiding: bij het herschrijven van een blok verdween per ongeluk de hele
kaart-sectie. De pagina laadde nog wel, maar de kaart deed niets meer. Zo'n stille
breuk zie je niet aan een 200-antwoord."""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
html = (HERE / 'static' / 'index.html').read_text()
js = (HERE / 'static' / 'app.js').read_text()

fouten = []

ids = set(re.findall(r'\bid="([^"]+)"', html))
gezocht = set(re.findall(r"\$\('#([a-zA-Z0-9_-]+)'", js)) | \
          set(re.findall(r"\$\$\('#([a-zA-Z0-9_-]+)", js))
for g in sorted(gezocht - ids):
    fouten.append(f'element #{g} wordt gezocht maar staat niet in de pagina')

gedefinieerd = set(re.findall(r'(?:async\s+)?function\s+([a-zA-Z0-9_]+)', js))
gedefinieerd |= set(re.findall(r'(?:const|let|var|window\.)\s*([a-zA-Z0-9_.]+)\s*=', js))
gedefinieerd = {n.split('.')[-1] for n in gedefinieerd}
ingebouwd = {'if', 'for', 'while', 'switch', 'catch', 'return', 'async', 'await',
             'setTimeout', 'setInterval', 'clearInterval', 'alert', 'parseInt', 'parseFloat',
             'Number', 'String', 'Boolean', 'Error', 'fetch', 'require', 'Promise', 'Object',
             'Array', 'Math', 'Date', 'JSON', 'URLSearchParams', 'encodeURIComponent',
             'decodeURIComponent', 'isNaN', 'console', 'localStorage', 'getComputedStyle',
             'prompt', 'confirm', 'navigator', 'location',
             # CSS-functies: die staan in tekstregels, het zijn geen JS-aanroepen
             'rgba', 'rgb', 'url', 'hsl', 'hsla', 'rotate', 'scale', 'translate',
             'translateX', 'translateY', 'calc', 'var', 'clamp', 'linear', 'cubic'}
# geen spatie toestaan vóór het haakje: anders leest hij "bestaat niet (meer)"
# in een Nederlandse zin als een functieaanroep
for naam in sorted(set(re.findall(r'\b([a-zA-Z][a-zA-Z0-9_]{3,})\(', js))):
    if naam in gedefinieerd or naam in ingebouwd:
        continue
    if re.search(rf'\.{naam}\s*\(', js) or f'L.{naam}' in js:
        continue
    fouten.append(f'functie {naam}() wordt aangeroepen maar is nergens gedefinieerd')

for f in fouten:
    print('✗', f)
print('✓ voorkant sluitend' if not fouten else f'\n{len(fouten)} probleem(en)')
sys.exit(1 if fouten else 0)
