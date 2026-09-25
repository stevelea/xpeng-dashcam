# Running this on another computer

Written after setting the whole thing up once. It records which machine does
what, everything you have to supply, and which parts are specific to this
installation rather than to the software.

If you only want the viewer running on one machine, **you do not need this
file** — [INSTALL.md](INSTALL.md) covers that and it is self-contained. This is
for reproducing the full arrangement: a Pi that copies cards, a NAS that stores
them, and a machine that serves the viewer.

## The three roles

They are separate on purpose, and each can live anywhere.

| Role | What it does | Where it runs here |
|---|---|---|
| **Archiver** | Detects a plugged-in USB card and copies it to the share. No UI. | Raspberry Pi Zero W, `192.168.1.213` |
| **Storage** | Holds the footage and the shared archive folder. | NAS, `192.168.1.235`, share `Shared_Drive` |
| **Viewer** | Indexes the archive, serves the web UI, publishes MQTT status. | `pantry`, `192.168.1.109` (Linux, Docker) |
| **Broker** | Carries the status entities to Home Assistant. | `192.168.1.88` (also the HA host) |

The viewer and the archiver never talk to each other. They meet at the share:
the archiver writes files, the viewer indexes them. That is the whole coupling,
so you can run the viewer without the archiver, or move either one.

## What you must supply

Nothing secret is in the repository, by design. A new machine needs:

| Secret | Used by | Where it goes |
|---|---|---|
| SMB username + password for the share | Viewer (mount), Archiver (mount) | `/etc/samba/creds-<name>`, mode 600, root-owned |
| MQTT username + password | Viewer, Archiver | `/etc/xpg-camera-copy.conf` |
| EVConduit URL + API key | Viewer | Settings page, or `config.json` under `evconduit` |

The EVConduit key is the only one you enter through the UI. The others are files
you create, so a fresh checkout has none of them and runs with everything off
rather than failing.

## Setting up the viewer

Confirmed working from a clean checkout — these are the exact steps, and the
test suites pass at the end of them.

```bash
git clone https://github.com/stevelea/xpeng-dashcam.git
cd xpeng-dashcam
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp config.example.json config.json          # set "root" to the archive folder
./.venv/bin/python scan.py
./.venv/bin/python thumbs.py
./.venv/bin/python ritten.py
./.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8965
```

Requirements: Python 3.11+, `ffmpeg` on PATH. On the Docker route use the compose
file described under [Updating the viewer](#updating-the-viewer) instead of the
venv — on `pantry` that is `docker-compose.v1.yml`, and plain
`docker-compose up -d --build` there would use the wrong build context.

Point `root` at the **mounted** archive folder. On this install that is a CIFS
mount at `/mnt/xpg006camera`; on another machine it can be any path, including a
local directory, which is the simplest way to try it.

### Running it under Docker

`docker-compose.yml` in the repository root is a working template. Two things in
it are machine-specific:

- the footage mount on the left of the volume line
- `TZ`, which only affects the container's own clock, not how footage is dated

Indexing stays a manual step, so a timer or cron is needed if you want the
viewer to keep up by itself. On this install that is a systemd timer running
`scan.py`, `thumbs.py` and `ritten.py` every 15 minutes, plus a small listener
that accepts a re-index request over MQTT.

## Updating the viewer

The viewer's source is **baked into its image** — the Dockerfile ends in `COPY . .`
— and only the index, the thumbnails and `config.json` are bind-mounted. A restart
therefore changes nothing: the image has to be rebuilt, and the source has to be on
the machine first. There is deliberately **no git checkout on `pantry`**; that tree
is a plain copy, so nothing there pulls on its own.

`deploy/deploy-viewer.sh` does the whole round trip:

```bash
cd /Volumes/projects/XpengDashcamViewer     # the checkout you edit
bash deploy/deploy-viewer.sh                # test, copy, rebuild, verify
```

It runs the test suites first and refuses to deploy if one fails, copies the source
over SSH, tags the outgoing image as `xpeng-dashcam:previous`, rebuilds, and then
checks that `/healthz` answers and which JS version is being served.

| Flag | What it does |
|---|---|
| `--dry-run` | list exactly what would be copied, change nothing |
| `--skip-tests` | copy and rebuild without running the suites |
| `--rollback` | retag `:previous` over `:local` and restart |

Overridable through the environment: `HOST`, `TARGET`, `CONTAINER`, `IMAGE`,
`PREVIOUS`, `PORT`, `PY`. The defaults are this installation's, so a bare run does
the right thing here and a different machine needs only `HOST=` and `TARGET=`.

What it copies is the source tree minus anything belonging to the machine: no
`config.json`, no index or thumbnails, no `.git`, no `demo/` footage, and no
`deploy/live/` (which carries credentials). New files are picked up automatically,
which is why it builds a list rather than naming files.

### Three things it exists to get right

Each of these has already cost a deploy.

1. **Which compose file made the running container.** It is `docker-compose.v1.yml`,
   whose build context is `./app-src`. The repository's `docker-compose.yml` uses
   `context: .` and **cannot build at all**: its Dockerfile runs
   `COPY requirements.txt ./`, and that file lives in `app-src`, not in the project
   root. Running the wrong one either fails or produces an image with no application
   in it. The script asks the running container which file it came from, via the
   `com.docker.compose.project.config_files` label, instead of guessing. Note also
   that `pantry` has only the standalone `docker-compose` 1.29, not the `docker
   compose` plugin, so the two-argument form will not work there.

2. **Rebuild, not restart.** `docker restart` and `docker compose up -d` both leave
   the old code running. Only `--build` replaces it.

3. **AppleDouble files, and where they really come from.** macOS writes a `._name`
   companion beside a file whenever it must carry extended attributes somewhere that
   cannot hold them. Copying through the SMB share does that, which is the obvious
   half of it.

   The less obvious half is that **tar over SSH does it too, even though the archive
   contains no such entries.** `bsdtar` writes the macOS extended attributes into PAX
   headers; GNU tar on the far end does not ignore them, it *reconstructs* an
   AppleDouble file beside every file to hold them. Measured on this tree: 64 files
   in, 128 files out. `COPY . .` then bakes all the copies into the image, where they
   sit next to the real files.

   The cure is `COPYFILE_DISABLE=1` in the environment of the tar that *creates* the
   archive. `--no-xattrs` and `--no-fflags` sound like they should do it and do not.
   The script sets all three, and also sweeps away anything that arrived by other
   means before it copies — reporting what it actually removed rather than the count
   from before the delete, which is the tempting number to print and not the same one.

### The Dockerfile that is actually built lives one level up

`docker-compose.v1.yml` builds with `context: ./app-src` and
`dockerfile: ../Dockerfile`, so the Dockerfile in use is
`xpeng-dashcam/Dockerfile` — **not** the copy the deploy drops in `app-src`. The
script now refreshes it from the checkout on every deploy, because a stale copy
there silently keeps applying whatever local patch it carries.

That is not hypothetical: this installation's Dockerfile patched `speed.py` to
stop hardcoding `-hwaccel videotoolbox`, which is macOS-only. Upstream took the
same fix over in v0.3, the patch's anchor disappeared with it, and the next
build failed on `expected 1 ffmpeg hwaccel site, found 0`. The patch step is gone
and `app-src/patches/` is now unused.

The build step also captures the compose output instead of piping it through
`tail` on the far side. `... | tail -6` ends in `tail` and exits 0, so that first
failed build was reported as a success while the old image carried on serving.

### What survives a rebuild, and what does not

| | |
|---|---|
| **Survives** | `data/clips.db` (the index), `thumbs/`, `config.json` — all bind-mounted from the project folder |
| **Survives** | the previous image, retagged `xpeng-dashcam:previous` |
| **Does not** | anything installed inside the container; the image is replaced wholesale |

No database migration is needed when the schema changes: `store.connect()` runs
`CREATE TABLE IF NOT EXISTS` on every connection, so a new table appears the first
time the app touches the database.

### After deploying

Hard-refresh the browser (`Ctrl`/`Cmd`-`Shift`-`R`). The static assets are versioned
in `index.html` (`app.js?v=34`), and the script prints the version it is serving, but
a cached page can still outlive the build.

## Setting up the archiver

The Pi side is a **separate project with its own repository**:
<https://github.com/stevelea/XpengDVRCopy> — do not look for its source in this
one.

It is a udev rule plus a systemd service running a shell script. It needs:

- `cifs-utils`, `rsync`, `mosquitto-clients`
- an `/etc/fstab` entry for the share, with `nofail` so the Pi still boots when
  the NAS is off
- the script, the service and the udev rule

### The two checkouts sit next to each other, and the names do not help

| Folder on the share | Repository | What it is |
|---|---|---|
| `/Volumes/projects/XpengDashcamViewer` | `stevelea/xpeng-dashcam` | **the viewer** — the thing you deploy |
| `/Volumes/projects/XpengDVRCopy` | `stevelea/XpengDVRCopy` | **the archiver** — the Pi's card copier |

Both have occupied the folder named `XpengDVRCopy` at different times, which is a
reliable way to spend an afternoon editing one while deploying the other. `git
remote -v` settles it in a second. `deploy-viewer.sh` copies the tree it actually
sits in, not the one you meant to be in, so run it from the viewer checkout.

The two projects share no code and never talk to each other directly — they meet
at the share. The archiver only needs to be told where to write; it has no idea
a viewer exists.

Its own README covers the install, the packages, and why the dedupe is done by
hand rather than with `rsync --ignore-existing`.

## What differs on another machine

Everything below is configuration, not code:

| Item | Here | Change it in |
|---|---|---|
| NAS address and share | `192.168.1.235`, `Shared_Drive` | Viewer `config.json` root; archiver `/etc/fstab` |
| Mount point | `/mnt/xpg006camera` | The same two places |
| MQTT host, user, topic prefix | `192.168.1.88`, `mqtt`, `xpg006camera` | `/etc/xpg-camera-copy.conf` |
| Time zone | `Australia/Sydney` | Viewer Settings — it should be the zone **the car records in** |
| Viewer port | 8965 | `config.json` `port`, and the compose port mapping |

### One upstream script assumes someone else's NAS

`nieuwe_opnames.sh`, which comes from upstream, defaults to
`root@192.168.1.218` — the original author's NAS. It is overridable:

```bash
NAS=root@your-nas ./nieuwe_opnames.sh
```

It is not used in this arrangement, but it will pause for eight seconds and then
continue if you run it without setting `NAS`.

## Checking it works

Three suites, all runnable without a network:

```bash
./.venv/bin/python toets_frontend.py        # every element and word list the script uses
./.venv/bin/python toets_evconduit.py       # trip matching, margins, caching, key handling
./.venv/bin/python toets_evconduit_api.py   # HTTP endpoint through to the drawn response
```

`toets_frontend.py` is the useful one when changing the UI: it catches a
mistyped translation key, which otherwise shows the key itself on screen instead
of failing.

For the archiver there is a test that needs no root, no NAS and no card: it
builds a mock environment and asserts that a first plug copies everything, a
second plug of the same card copies nothing and creates no folder, and adding
one clip transfers exactly that clip.

## Known rough edges

- **Indexing is always manual.** Nothing watches the archive. If the viewer
  looks stale, that is why.
- **The index is a snapshot.** A copy still in progress appears only after the
  next index run.
- **git on a CIFS share is awkward.** `core.fileMode` must be false, and file
  locking can block operations that otherwise report success or failure
  inconsistently. Cloning locally and pushing is more reliable than working in
  place.
