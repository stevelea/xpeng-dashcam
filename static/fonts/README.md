# Fonts

Lokaal gehost in plaats van via de Google Fonts CDN. Reden: het dashboard draait in
het HA-ingress-frame, en zo houdt het dezelfde stijl zonder internet en ongeacht een
eventueel CSP dat externe bronnen blokkeert.

| Bestand | Familie | Gebruik |
|---|---|---|
| `lexenddeca-latin.woff2` | Lexend Deca (variabel, 300–700) | body / UI |
| `fraunces-latin.woff2` | Fraunces (variabel, 400–700) | koppen en cijfers |

Beide staan onder de SIL Open Font License 1.1, die zelf hosten toestaat.
Het zijn de `latin`-subsets van Google Fonts; samen ~73 KB.

Vervangen door een nieuwere versie:

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
curl -s -A "$UA" "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Lexend+Deca:wght@400;500;600&display=swap"
# pak uit de output de woff2-URL's onder de /* latin */-blokken
```

De `@font-face`-regels staan bovenaan `../style.css`.
