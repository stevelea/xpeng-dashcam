# Linking to footage from another app

The viewer accepts a few query parameters, so an external app — a trip log, for
instance — can link straight to the clips for a moment instead of dropping the
user on a calendar. Nothing is needed on the viewer side beyond the link: no API
key, no registration.

The viewer's own address, wherever it runs:

```
http://viewer.local:8965/
```

## Parameters

| Parameter | Meaning | Default |
|---|---|---|
| `dag` | Date to show, `YYYY-MM-DD` | first indexed day |
| `tijd` | **Centre** of the window, `HH:MM` or `HH:MM:SS` | — |
| `venster` | Half-width of the window in **minutes** | `30` |
| `rit` | Trip id to open directly | — |

- `time` is an alias for `tijd`, `window` for `venster`.
- With no `tijd`, `dag` opens the ordinary day view.
- With `tijd`, the viewer shows a search result — "Around …" — listing every
  clip inside `tijd ± venster`.
- `dag` may be omitted when `tijd` is present; the first indexed day is used.
- An unparseable or non-positive `venster` falls back to the default.

## The window is a centre, not a range

This is the one thing to be careful about:

```
?dag=2026-07-02&tijd=17:35&venster=10     →  17:25 … 17:45
```

So for a trip running `17:26`–`17:41`, pass the **midpoint** and roughly half
the duration:

```
start 17:26, end 17:41  →  centre 17:33, half-width 12
http://viewer.local:8965/?dag=2026-07-02&tijd=17:33&venster=12
```

Passing the start time with the default 30-minute window is usually good enough
and simpler — you get the trip plus half an hour either side.

## Examples

```
# whole day
http://viewer.local:8965/?dag=2026-07-02

# 30 minutes either side of a moment
http://viewer.local:8965/?dag=2026-07-02&tijd=17:33

# tight: 5 minutes either side
http://viewer.local:8965/?dag=2026-07-02&tijd=17:33&venster=5

# wide
http://viewer.local:8965/?dag=2026-07-02&tijd=17:33&venster=180

# open a trip directly, by id
http://viewer.local:8965/?dag=2026-07-02&rit=4

# seconds are accepted
http://viewer.local:8965/?dag=2026-07-02&tijd=17:26:58
```

A colon may be sent literally or percent-encoded (`17%3A33`); both work.

## Building a link

Clip file names carry the recording time, so if you already have the file name
you can build the link without asking the viewer anything:

```
DVR_20260702172658840_front.mp4
    └──────┬──────┘
     2026-07-02 17:26:58
```

### JavaScript

```js
const pad = n => String(n).padStart(2, '0');

function linkForClip(fileName, baseUrl = 'http://viewer.local:8965/') {
  const m = /(\d{14})/.exec(fileName);
  if (!m) return null;
  const s = m[1];                       // YYYYMMDDHHMMSS from the file name
  return `${baseUrl}?dag=${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` +
         `&tijd=${s.slice(8, 10)}:${s.slice(10, 12)}:${s.slice(12, 14)}&venster=15`;
}

function linkForTrip(start, end, baseUrl = 'http://viewer.local:8965/') {
  const mins = s => { const [h, m] = s.slice(11, 16).split(':').map(Number); return h * 60 + m; };
  const hhmm = t => `${pad(Math.floor(t / 60) % 24)}:${pad(t % 60)}`;
  const a = mins(start), b = mins(end);
  const half = Math.max(5, Math.floor((b - a) / 2) + 5);
  return `${baseUrl}?dag=${start.slice(0, 10)}&tijd=${hhmm(a + Math.floor((b - a) / 2))}&venster=${half}`;
}
```

`linkForClip('DVR_20260702172658840_front.mp4')` →
`…?dag=2026-07-02&tijd=17:26:58&venster=15`

`linkForTrip('2026-07-02T17:26:58', '2026-07-02T17:41:00')` →
`…?dag=2026-07-02&tijd=17:33&venster=12`

### Python

```python
import re
from datetime import datetime

def link_for_clip(file_name, base="http://viewer.local:8965/"):
    m = re.search(r"(\d{14})", file_name)
    if not m:
        return None
    t = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    return f"{base}?dag={t:%Y-%m-%d}&tijd={t:%H:%M:%S}&venster=15"

def link_for_trip(start: datetime, end: datetime, base="http://viewer.local:8965/"):
    mid = start + (end - start) / 2
    half = max(5, int((end - start).total_seconds() / 120) + 5)
    return f"{base}?dag={mid:%Y-%m-%d}&tijd={mid:%H:%M}&venster={half}"
```

Both produce the same links as the JavaScript versions.

## Time zone — please read this one

`tijd` is **wall-clock time**, not UTC. It is read in the time zone configured in
the viewer's own settings, so pass the time exactly as it appears on the footage
and do not convert it.

The time zone is a **per-installation setting**, chosen by whoever runs the
viewer (Settings → Time zone). It should be the zone the car was recording in,
which is not necessarily where the viewer runs. Read it back rather than
assuming it:

```
GET /api/settings      →  { "timezone": "<the zone the car records in>", ... }
```

In particular, **do not build these strings with `new Date()`**, or the result
depends on the time zone of the machine generating the link rather than the
car's:

```js
// WRONG on a server in a different zone - this yields that machine's local
// midpoint, which the viewer then reads as if it were the car's local time.
const mid = new Date((new Date(start) + new Date(end)) / 2);
```

The helper functions above avoid `Date` arithmetic for exactly this reason: they
slice the wall-clock text you already have and never reinterpret it. If a link
lands on the wrong moment, a time-zone mismatch is the first thing to check.

### Changing the time zone does not re-date existing clips

Timestamps are written into the index when a clip is first scanned, using
whatever zone was configured at that moment. Changing the setting afterwards
affects newly indexed clips only; already-indexed ones keep their original
offset. If the zone was wrong from the start, the fix is to re-index
(`scan.py` then `ritten.py`) after correcting it.

## Clip layout and timing

Each recording is normally two files, one per camera:

```
DVR_20260702172658840_front.mp4
DVR_20260702172658840_front_and_360.mp4
```

They share a timestamp and appear as a single tile; the player switches between
`front` and `360`. Recordings are about **one minute** apart, so a 15-minute
trip is roughly 15 clips.

## Current data (for reference)

| Day | Clips | Trip |
|---|---|---|
| 2026-07-01 | 2 | id 3, 17:08 |
| 2026-07-02 | 29 | id 4, 17:26–17:41 (15 clips) |

Trip ids are assigned by the viewer and change if the index is rebuilt, so for
links you store, prefer `dag` + `tijd`. Use `rit` only for links generated on
the spot.

## Fetching the data instead

If you would rather read the clips than link to the page, the page itself calls:

```
GET /api/search?ts=YYYY-MM-DDTHH:MM&window_min=30
```

This returns every clip within `ts ± window_min`. The URL parameter `venster=N`
is passed straight through as `window_min=N`.

Also available:

| Endpoint | Returns |
|---|---|
| `/api/overview` | clip and day counts, first/last day |
| `/api/day/<YYYY-MM-DD>` | every clip on a day |
| `/api/trips/<YYYY-MM-DD>` | trips on a day, with start/end and clip counts |
| `/api/trip/<id>` | one trip |
| `/api/trip/<id>/route` | route for a trip (GeoJSON, if one was built) |

There is no authentication on these; keep the viewer on the LAN.
