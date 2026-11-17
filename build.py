# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Builds the VisionClaw add-on.

Usage:
  python build.py

Needs the engine binaries in addon/engine (see BUILD.md). Writes to dist/:
  VisionClaw-<version>.nvda-addon   the add-on
  VisionClaw.nvda-addon             the same file under a fixed name, for the README's direct download link
"""
import os
import re
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "addon")
DIST = os.path.join(ROOT, "dist")
ENGINE = os.path.join(SRC, "engine", "vcengine.exe")


def main():
	if not os.path.isfile(ENGINE):
		sys.exit("The engine is missing: addon/engine/vcengine.exe. See BUILD.md for where to get it.")
	manifest = open(os.path.join(SRC, "manifest.ini"), encoding="utf-8").read()
	version = re.search(r"^version\s*=\s*(\S+)", manifest, re.M).group(1)
	os.makedirs(DIST, exist_ok=True)
	out = os.path.join(DIST, f"VisionClaw-{version}.nvda-addon")
	count = 0
	with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
		for dirpath, dirnames, files in os.walk(SRC):
			dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
			for name in sorted(files):
				if name.endswith((".pyc", ".log", ".part")):
					continue
				full = os.path.join(dirpath, name)
				z.write(full, os.path.relpath(full, SRC))
				count += 1
	# releases/latest/download/VisionClaw.nvda-addon then always downloads the newest version.
	shutil.copyfile(out, os.path.join(DIST, "VisionClaw.nvda-addon"))
	print(f"Built {out}: {count} files, {os.path.getsize(out) / 2 ** 20:.1f} MB")


if __name__ == "__main__":
	main()
