# Installation

From nothing to a working viewer. Takes about ten minutes, most of it waiting for
thumbnails.

---

## 1. Prerequisites

**Python 3.11 or newer**

```bash
python3 -V
```

> Using Docker instead? Skip to **[5b](#5b-or-run-it-with-docker)** — the image brings
> Python and ffmpeg with it, so none of this section is needed.

**ffmpeg** — needed for thumbnails and for reading the speed off the video.

```bash
# macOS
brew install ffmpeg
# Debian / Ubuntu
sudo apt install ffmpeg
```

Check it:

```bash
ffmpeg -version
```

---

## 2. Install

```bash
git clone <your-fork-url> xpeng-dashcam-viewer
cd xpeng-dashcam-viewer
./setup.sh
```

`setup.sh` creates a virtual environment, installs the three Python packages, makes the
`data/` and `thumbs/` folders, and copies `config.example.json` to `config.json`. It
never overwrites an existing `config.json`.

---

## 3. Start it

```bash
./run.sh
```

Open <http://127.0.0.1:8965>. The viewer is **empty** at this point. That is expected.

To reach it from another machine on your network, edit `run.sh` and keep
`--host 0.0.0.0`. Only do that on a network you trust: there is no login.

---

## 4. Point it at your footage

Click the **gear icon** in the top right.

| Field | What to put in it |
|---|---|
| Folder with your dashcam files | The top folder of your archive, e.g. `/Volumes/MY_STICK` |
| Sub-folder for normal recordings | `XP_DCIM` on most XPENG models. Leave empty if your files are not in sub-folders. |
| Sub-folder for emergency recordings | `XP_EMER_DCIM`. Leave empty if you do not have one. |
| Time zone | Your own, e.g. `Europe/Amsterdam` or `America/New_York` |
| Main camera | The word after the time in the file name, usually `front` |

Press **Test folder**. It reports how many usable clips it can see. If it says
*"no recognisable file names"*, jump to Troubleshooting below.

Press **Save**.

### Why the time zone matters

The recording time comes from the **file name**, which has no time zone in it. The app
has to be told which zone those numbers are in. Get this wrong and every timestamp in
the app is off by a fixed number of hours, silently.

### Your folder layout does not matter

The scan walks every sub-folder. A `YYYY/MM` layout is not required. All of these work:

```
archive/XP_DCIM/2025/10/DVR_20251028112014305_front.mp4
archive/XP_DCIM/DVR_20251028112014305_front.mp4
archive/DVR_20251028112014305_front.mp4
```

---

## 4b. Or start with the demo day

If you just want to see what the app does before pointing it at your own archive:

```bash
./.venv/bin/python load_demo.py
```

This reads `demo/footage/`, creates two trips, draws a route and builds the thumbnails.
Start the viewer and pick **13 August 2026**.

Two honest notes about the demo:

- The video is blurred on purpose. You will not recognise any surroundings.
- The route is **invented** and has nothing to do with where the clips were filmed.
  Blurring also destroys the speed digits the app normally reads off the picture, so the
  demo carries its distances as stored values.

Your own footage is not affected. To go back to a clean index, delete `data/clips.db`
and run `scan.py` again.

---

## 5. Build the index

Back in a terminal, in the project folder, in this order:

```bash
./.venv/bin/python scan.py      # find the clips        (seconds)
./.venv/bin/python thumbs.py    # make the thumbnails   (slow, needs ffmpeg)
./.venv/bin/python ritten.py    # group them into trips (minutes)
```

`thumbs.py` can be interrupted and restarted — it skips whatever is already done. To do
a first batch of, say, 200 to see if it works:

```bash
./.venv/bin/python thumbs.py 200
```

Refresh the browser. Your days should now appear in the calendar.

---

## 5b. Or run it with Docker

If you would rather not install Python and ffmpeg on the host — on a NAS or a home
server, say — everything above works from a container instead.

```bash
cp config.example.json config.json     # then set "root" to /footage
# and put your own footage folder on the left of ":/footage:ro" in docker-compose.yml
docker compose up -d --build
```

Steps 2 to 4 are then replaced by the container, and the index is built with:

```bash
docker compose run --rm app python scan.py
docker compose run --rm app python thumbs.py
docker compose run --rm app python ritten.py
```

The same `thumbs.py 200` limit works: `docker compose run --rm app python thumbs.py 200`.

`config.json`, `data/` and `thumbs/` are bind-mounted from the project folder, so your
settings and index survive a rebuild, and the footage is mounted read-only. Set the
footage path in `docker-compose.yml` and keep the container's `TZ` equal to the
`timezone` in `config.json`.

---

## 6. Importing new footage from the stick

`import_from_stick.sh` moves clips off the stick into your archive, sorted into
`YYYY/MM` folders based on the file name.

It **moves** rather than copies on purpose: a full stick makes the dashcam stop
recording. A file is only removed from the stick after it exists at the destination with
exactly the same byte size.

Always do a dry run first — without `go` it changes nothing:

```bash
./import_from_stick.sh /Volumes/MY_STICK /path/to/archive
```

Then for real:

```bash
./import_from_stick.sh /Volumes/MY_STICK /path/to/archive go
```

Afterwards, re-run the three commands from step 5 to pick up the new footage.

---

## 7. Configuration file

Everything the settings screen writes ends up in `config.json`. You can also edit it by
hand. It is git-ignored, so your own paths never end up in a commit.

| Key | Meaning |
|---|---|
| `root` | Top folder of your archive |
| `folders` | Sub-folders for normal and emergency recordings |
| `timezone` | Zone the file-name timestamps are in |
| `views.primary` | Main camera name, usually `front` |
| `web.port` | Port the app listens on (default 8965) |
| `thumbs` | Thumbnail size, quality and how many to make at once |
| `trips.gap_seconds` | Gap after which a new trip starts (default 300) |
| `thuis` | Your home coordinates. Optional; used as a starting point for routes. |
| `logger` | Location logger URL. Optional; leave empty to disable routes. |
| `photos` | Photo library path. Optional; only timestamps and coordinates are read. |
| `herinnering` | Reminder settings. Optional; leave `ha_url` empty to disable. |

Leaving an optional section empty simply switches that feature off. Nothing breaks.

---

## Troubleshooting

**"Test folder" says no recognisable file names**

The app expects a timestamp of 14 to 17 digits, then an underscore, then a camera name:

```
DVR_20251028112014305_front.mp4
    ^^^^^^^^^^^^^^^^^ ^^^^^
    20251028 11:20:14  camera
```

Check one of your own file names against that. If your model names files differently,
open an issue with an example name — the pattern lives in `store.py` and is easy to widen.

**No thumbnails**

`ffmpeg` is missing or not on your `PATH`. Run `ffmpeg -version` to confirm, then re-run
`thumbs.py`.

**Times are wrong by a fixed number of hours**

The time zone is wrong. Fix it in the settings screen, then re-run `scan.py`. Existing
rows are updated in place.

**No trips, only loose clips**

You have not run `ritten.py` yet, or your clips are far enough apart that each becomes
its own trip. Lower or raise `trips.gap_seconds` in `config.json`.

**No routes on the map**

Routes need a location logger, which is optional and off by default. Without it you still
get clips, trips, thumbnails and distance.

**Port already in use**

Change `web.port` in `config.json` and the port in `run.sh`.
