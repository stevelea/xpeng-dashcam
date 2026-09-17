#!/usr/bin/env python3
"""Make speed.py's ffmpeg hardware-acceleration flag portable.

`speed.py` hardcodes the VideoToolbox hardware decoder:

    cmd = ['ffmpeg', '-nostdin', '-loglevel', 'error', '-hwaccel', 'videotoolbox', ...]

VideoToolbox only exists on macOS. On Linux ffmpeg aborts with
`Unknown option` before reading the file, so `sample_clip()` returns `[]` for
every clip and the speed bar - and therefore the distance per trip - silently
produces nothing.

This patch keeps VideoToolbox where it works and uses plain software decoding
everywhere else. It is idempotent: if the line has already been made portable
(upstream may apply this directly), the script reports that and exits 0, so a
Docker build keeps working either way.

Usage:
    python3 patches/0001-ffmpeg-hwaccel-portable.py [path/to/speed.py]
"""
import pathlib
import re
import sys

target = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "speed.py")
if not target.exists():
    sys.exit(f"patch: {target} not found (run from the project root)")

source = target.read_text(encoding="utf-8")

if "sys.platform == 'darwin'" in source:
    print(f"patch: {target} already portable - nothing to do")
    sys.exit(0)

# Match the whole argument list up to and including the macOS-only flag:
#   ['ffmpeg', '-nostdin', ..., '-hwaccel', 'videotoolbox',
# The captured group keeps every real argument and drops only the hwaccel pair.
pattern = re.compile(r"(\[[^\]]*?'ffmpeg'[^\]]*?),\s*'-hwaccel',\s*'videotoolbox',", re.S)
replacement = r"\1, *(['-hwaccel', 'videotoolbox'] if sys.platform == 'darwin' else []),"

patched, count = pattern.subn(replacement, source)
if count != 1:
    sys.exit(f"patch: expected exactly 1 ffmpeg hwaccel site, found {count} - "
             f"speed.py has changed, please update this patch")

# The new expression needs sys.
if not re.search(r"^import sys$", patched, re.M):
    lines = patched.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")) and "__future__" not in line:
            lines.insert(i, "import sys")
            break
    else:
        lines.insert(1, "import sys")
    patched = "\n".join(lines)

target.write_text(patched, encoding="utf-8")
print(f"patch: {target} patched ({count} site) - hwaccel is now platform-aware")
