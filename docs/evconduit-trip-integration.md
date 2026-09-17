# EVConduit trip data in XPENG Dashcam Viewer — what exists, and the one thing we need

Written for whoever maintains EVConduit (`/Volumes/projects/evconduit`). The
consumer is a separate, self-hosted app: **XPENG Dashcam Viewer**
(`/Volumes/projects/XpengDVRCopy`), a small FastAPI + SQLite app that indexes
XPENG dashcam `.mp4` files, groups them into trips, draws thumbnails and reads
the speed digits off the video.

The ask is small: we want to show the car's own figures for a drive next to the
footage of it, and draw the GPS track if there is one. Almost all of it already
exists. **One lookup is missing**, described in section 4.

---

## 1. The shape of the problem

The two apps describe the same physical event — a drive — and share **no key at
all**.

| | Dashcam Viewer | EVConduit |
|---|---|---|
| Identity | `INTEGER` rowid, reassigned on every re-index | `uuid` |
| Time | `start_ts` / `end_ts`, **local, naive** ISO | `started_at` / `ended_at`, **UTC** |
| Clock source | the dashcam's own filename timestamps | the car, via XPENG, as 1 Hz CAN data |
| Distance | OCR of the speed digits burned into the video | integrated from 1 Hz speed (+0.1% vs odometer) |
| Location | none | none in the export; only from the owner's GPS logger |

So the only join key is **time**, and even that is three clocks disagreeing: the
car, the dashcam, and the GPS logger. EVConduit already knows this — it is what
`pad_seconds` exists for in `xpeng/track.py`.

## 2. What already works, unchanged

Everything below is confirmed present in the current code. **No change needed.**

- **Auth.** `get_supabase_user` (`app/auth/supabase_auth.py`) accepts a
  per-account **API key** in `Authorization: Bearer <key>` as well as a Supabase
  JWT. A server-to-server consumer needs exactly this and nothing else.
- **`GET /api/user/xpeng/trips`** — `select *` from `xpeng_trips`, newest first,
  `limit` 200, lookback-cutoff applied by tier.
- **`GET /api/user/xpeng/trips/{trip_id}/track`** — the GPS track, decimated by
  distance, as parallel `seconds` / `lat` / `lon` arrays. Carries `available`,
  `reason` (`no_subject` / `no_positions` / `too_few_points` / `trip_incomplete`),
  `coverage`, `largest_gap_seconds`, `source_point_count` and `track_distance_km`.
  This is better than anything we would have asked for: the honesty fields are
  the reason a route can be shown without implying more than was measured.
- **`GET /api/user/xpeng/trips/{trip_id}/samples`** — 1 Hz signals, including
  `speed_kmh`. Useful later to check our OCR against the car; heavy, so phase 2.

Fields we intend to display, all already on the trip row: `started_at`,
`ended_at`, `duration_seconds`, `distance_km`, `odometer_start`, `odometer_end`,
`mean_moving_speed_kmh`, `max_speed_kmh`, `energy_kwh`, `regen_kwh`, `soc_start`,
`soc_end`, `vin`. Plus the driver's own `origin` / `destination` / `purpose` /
`comment` from `/trip-notes`, which are the only place names that exist.

## 3. Why id-based lookup cannot work

The Dashcam Viewer cannot hold an EVConduit trip id. Its own trip ids are
**reassigned whenever footage is re-indexed** — `ritten.build()` deletes every
`trips` row and reinserts, re-linking waypoints by timestamp (see the warning in
`ritten.measure()`). A cached `uuid` would point at a different drive after the
next index.

Storing the EVConduit id is therefore not an option, and there is no VIN in a
dashcam filename. **Time is the only join that survives.**

## 4. The one change we need: a time-window lookup

### Requested endpoint

```
GET /api/user/xpeng/trips/window
      ?from=<iso8601>              # required, UTC
      &to=<iso8601>                # required, UTC
      &tolerance_seconds=180       # optional, default 180, 0..3600
      &limit=10                    # optional, default 10, 1..50
```

`from`/`to` is the dashcam's trip window, converted to UTC by the caller.
`tolerance_seconds` widens the search at both ends so the two clocks may
disagree, exactly as `pad_seconds` does on the track endpoint.

### Response

```json
{
  "from": "2026-09-14T12:23:00+00:00",
  "to":   "2026-09-14T12:41:00+00:00",
  "tolerance_seconds": 180,
  "cutoff": "2026-06-16T00:00:00+00:00",
  "trips": [
    {
      "trip": { "...the same row /trips returns..." },
      "overlap_seconds": 1080,
      "overlap_fraction_of_query": 1.0,
      "start_delta_seconds": -14,
      "end_delta_seconds": 22
    }
  ]
}
```

### Semantics that matter to us

1. **Candidates, plural, ranked by `overlap_seconds` descending.** The two apps
   segment drives differently — we cut on 300 s recording gaps and on sustained
   standstill, EVConduit cuts on its own CAN trip detection — so a clean 1:1
   mapping is not guaranteed. Returning a ranked list lets us show "this drive"
   and let the operator see if two of ours landed on one of yours.

2. **`start_delta_seconds` / `end_delta_seconds` are signed and reported, not
   hidden.** `E_start − from` and `E_end − to`. We want to *display* the skew
   rather than silently pad it away: a viewer that quietly absorbs 90 seconds of
   clock error is asserting a precision it does not have. This matches how
   `pad_seconds` is reported on the track endpoint rather than applied invisibly.

3. **Empty `trips` is a 200, not a 404.** "No drive at that time" is the ordinary
   answer — for an account with no export, or before it uploaded one. The caller
   distinguishes that from an error.

4. **`cutoff` is the lookback date actually applied to this account.** This is
   the one thing we most want beyond the bare lookup. A free account silently
   gets 90 days; if the footage is older we would otherwise report "no car data
   for this drive", which is *wrong* — the data may well exist and simply be
   outside the plan. With `cutoff` in the response we can say "outside your
   history window" instead of "nothing recorded". The same `_lookback_cutoff`
   logic already used by `/trips` is all it takes.

5. **No positions are read by this endpoint.** It is an index lookup on a btree
   that already exists (`idx_xpeng_trips_user_started`). The track is then
   fetched by id from the endpoint that already works.

### Acceptable alternative

If a dedicated path is unwelcome, a plain filter on the existing list is enough
for a first version:

```
GET /api/user/xpeng/trips?started_after=<iso>&started_before=<iso>&limit=50
```

We would do the overlap ranking ourselves. What that loses is `cutoff`,
`start_delta_seconds` and the ranking — i.e. exactly the parts that let us be
honest about *why* there is no match.

## 5. Optional, nice-to-have

- **`GET /api/user/xpeng/trips/{trip_id}/detail`** -> `{"trip": {...}, "track": {...}}`.
  One round trip instead of two. Purely an optimisation; not a blocker.
- **A projected trip row for third-party callers.** `/trips` returns `select *`,
  so `user_id` and `export_id` come along. Harmless, but noise in a payload
  consumed by another service.
- **Provenance on the track.** Worth considering now that there is more than one
  feed (section 7): `vehicle_positions.source` exists and defaults to `webhook`,
  but the ingest (`api/positions.py`) never passes anything else, so every row in
  the table says the same thing. A consumer drawing an *independent* track wants
  to say where it came from — "your HA tracker", "your phone" — and today it
  cannot. Letting the ingest set `source` per caller, and returning the distinct
  sources beside `source_point_count`, would close that.

## 6. What we will do on our side

For context, so the shape of the request makes sense:

- Call the endpoint with the dashcam trip window converted to UTC using the
  timezone already in `config.json`.
- Cache per **dashcam `start_ts`** (stable across re-indexes), not per row id,
  and re-match on demand — so a re-parse on your side that moves a trip's start
  time is tolerated rather than cached forever.
- Show the car's `distance_km` **beside** our OCR-derived distance, never
  replacing it. Our figure is a measurement off the video and yours is a
  measurement off the CAN bus; they should be visibly two numbers, because a
  disagreement between them is the interesting part.
- Draw the track as a **measured** layer with `coverage` and
  `largest_gap_seconds` shown, reusing our existing measured-vs-reconstructed
  distinction. A track spanning 12% of a drive will say so.
- Never show the API key back out of our settings API.

## 7. One thing to be clear about

EVConduit's export carries **no location data** (`docs/xpeng-data-export.md`),
and `/trips/{id}/track` is filled only from the owner's own logger posting to
`/api/positions/<subject>`. Your own measurement in `docs/xpeng-trip-map.md`
section 1 rules out the Enode charging samples as a route source (median gap
247 s; 0-1 located samples per drive).

So for an account with no logger pointed at EVConduit, **every** track response
is `available: false, reason: "no_positions"` — correct, and by design. The
Dashcam Viewer will report that as "no track" and fall back to what it already
does. Nothing here asks EVConduit to produce a route it does not have.

### The feeds are not interchangeable

Some owners' GPS arrives from a feed that has nothing to do with the dashcam —
Home Assistant forwarding a `device_tracker`, or a phone logger. That is fine for
the track, and it is exactly the case `pad_seconds` and the coverage figures
exist for, but two things are worth stating plainly:

- **Home Assistant reaches the table.** It posts to `/api/positions/<subject>`
  with the account's API key, which is the same door every other logger uses
  (`docs/xpeng-trip-map.md` section 5).
- **ABRP does not.** In this codebase ABRP is *outbound*:
  `services/abrp_service.py` sends telemetry **to** ABRP for route planning and
  reads no position back, and nothing outside `storage/positions.py` and
  `lib/demo.py` touches `vehicle_positions`. So a drive whose only GPS was
  recorded by ABRP is **not** in EVConduit and will return `no_positions` — not
  a bug, but a real limit worth knowing before someone concludes the feature is
  broken.

Consequently a track we draw may come from a *different* device than the one the
Dashcam Viewer already reads through its own `logger` setting. The two can
disagree, and neither is wrong: they are two independent measurements of the same
drive. We will show them as such rather than silently picking one, which is what
the provenance note above is for.

## 8. Minimal example

```bash
# 14:23-14:41 Europe/Amsterdam on 2026-09-14 == 12:23-12:41 UTC
curl -sS -H "Authorization: Bearer $EVCONDUIT_API_KEY" \
  "$EVCONDUIT/api/user/xpeng/trips/window?from=2026-09-14T12:23:00Z&to=2026-09-14T12:41:00Z&tolerance_seconds=180"

# then, with the matched id
curl -sS -H "Authorization: Bearer $EVCONDUIT_API_KEY" \
  "$EVCONDUIT/api/user/xpeng/trips/<trip_id>/track?max_points=1500&pad_seconds=180"
```

---

## Summary for the maintainer

| | |
|---|---|
| **Blocking** | `GET /api/user/xpeng/trips/window` — time-window trip lookup returning ranked candidates, signed clock deltas, and the account's `cutoff`. |
| **Acceptable fallback** | `started_after` / `started_before` filters on the existing `/trips`. |
| **Nice to have** | `/trips/{id}/detail` combining trip + track; per-caller `source` on the position ingest so an independent track can be attributed. |
| **No change** | Auth via API key, `/trips`, `/trips/{id}/track`, `/trips/{id}/samples`, `/trip-notes`. |
