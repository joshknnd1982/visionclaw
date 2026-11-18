# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The data folder inside the add-on, kept when NVDA deletes the add-on's folder, and portable copies with
everything in them (claw/portable.py, installTasks.py). Plain Python, in folders of the test's own.

  python tests/test_portable.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import threading
import types
import zipfile

import harness  # noqa: F401
from visionClaw.claw import portable

ROOT = harness.ROOT
WORK = tempfile.mkdtemp()


def write(path, text="x"):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		f.write(text)


def read(path):
	with open(path, encoding="utf-8") as f:
		return f.read()


def tree(folder):
	found = set()
	for dirpath, _dirs, names in os.walk(folder):
		for name in names:
			found.add(os.path.relpath(os.path.join(dirpath, name), folder).replace(os.sep, "/"))
	return found


# --- Merging: everything is moved, this computer's own file wins, nothing is deleted that has no copy ---

src, dst = os.path.join(WORK, "src"), os.path.join(WORK, "dst")
write(os.path.join(src, "models", "a", "model.gguf"), "mine")
write(os.path.join(src, "memories", "one.md"), "remembered")
write(os.path.join(src, "lessons.json"), "[1]")
write(os.path.join(dst, "models", "a", "model.gguf"), "theirs")
write(os.path.join(dst, "models", "b", "other.gguf"), "only theirs")
write(os.path.join(dst, "skills", "s", "SKILL.md"), "skill")
moved, problems = portable.merge(src, dst)
assert not problems and not os.path.exists(src), problems
assert tree(dst) == {"models/a/model.gguf", "models/b/other.gguf", "skills/s/SKILL.md", "memories/one.md", "lessons.json"}
assert read(os.path.join(dst, "models", "a", "model.gguf")) == "mine"
assert moved == 3, moved

# At start: nothing to move is no fault, and a folder is never moved into itself.
assert portable.moveIn(os.path.join(WORK, "none"), dst) == (0, [])
assert portable.moveIn(dst, dst) == (0, []) and os.path.isdir(dst)
old = os.path.join(WORK, "config", "visionClaw")
write(os.path.join(old, "notes", "game.md"), "notes")
data = os.path.join(WORK, "config", "addons", "visionClaw", "data")
assert portable.moveIn(old, data) == (1, []) and not os.path.exists(old)
assert read(os.path.join(data, "notes", "game.md")) == "notes"

# --- When NVDA deletes the add-on's folder: an update, a removal, an install that never finished ---

config = os.path.join(WORK, "config")
addonDir = os.path.join(config, "addons", "visionClaw")
pending = addonDir + portable.PENDING
write(os.path.join(pending, "manifest.ini"), "name = visionClaw")
# A portable copy that is being installed brings data of its own; this computer's wins where both have a file.
write(os.path.join(pending, "data", "notes", "game.md"), "the copy's notes")
write(os.path.join(pending, "data", "models", "c", "big.gguf"), "the copy's model")
assert portable.carryOver(addonDir, config) == os.path.join(pending, "data")
assert not os.path.exists(os.path.join(addonDir, "data"))
assert read(os.path.join(pending, "data", "notes", "game.md")) == "notes"
assert read(os.path.join(pending, "data", "models", "c", "big.gguf")) == "the copy's model"
# The pending install itself being taken away keeps nothing: its data is not this computer's.
assert portable.carryOver(pending, config) is None
# Removed: the data waits in NVDA's configuration folder, and is moved in again by a later install.
os.rmdir(addonDir)  # NVDA deletes the old folder and puts the newer one in its place
os.replace(pending, addonDir)
assert portable.carryOver(addonDir, config) == os.path.join(config, "visionClaw")
assert read(os.path.join(config, "visionClaw", "notes", "game.md")) == "notes"
assert not os.path.exists(os.path.join(addonDir, "data"))
assert portable.carryOver(addonDir, config) is None  # nothing left to carry

# installTasks.onUninstall does the same inside NVDA, loading portable.py from the add-on by its path.
for name, values in (
	("addonHandler", {"initTranslation": lambda: None}), ("gui", {}), ("wx", {}),
	("globalVars", {"appArgs": types.SimpleNamespace(configPath=config)}),
	("logHandler", {"log": types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None)}),
):
	sys.modules[name] = types.SimpleNamespace(**values)
fake = os.path.join(config, "addons", "visionClaw")
os.makedirs(os.path.join(fake, "globalPlugins", "visionClaw", "claw"), exist_ok=True)
for rel in (("installTasks.py",), ("globalPlugins", "visionClaw", "claw", "portable.py")):
	with open(os.path.join(ROOT, "addon", *rel), encoding="utf-8") as f:
		write(os.path.join(fake, *rel), f.read())
write(os.path.join(fake, "data", "memories", "two.md"), "also remembered")
write(fake + portable.PENDING + "/manifest.ini", "name = visionClaw")
spec = importlib.util.spec_from_file_location("installTasksUnderTest", os.path.join(fake, "installTasks.py"))
tasks = importlib.util.module_from_spec(spec)
tasks._ = lambda text: text
spec.loader.exec_module(tasks)
tasks.onUninstall()
assert read(os.path.join(fake + portable.PENDING, "data", "memories", "two.md")) == "also remembered"
assert not os.path.exists(os.path.join(fake, "data"))

# --- What a portable copy holds: the add-on and its whole data folder ---

addon = os.path.join(WORK, "addon")
write(os.path.join(addon, "manifest.ini"), "name = visionClaw\nversion = 9.9.9")
write(os.path.join(addon, "globalPlugins", "visionClaw", "__init__.py"), "# code")
write(os.path.join(addon, "globalPlugins", "visionClaw", "__pycache__", "x.cpython-311.pyc"), "compiled")
write(os.path.join(addon, "engine", "vcengine.exe"), "engine")
write(os.path.join(addon, "data", "models", "q", "model.gguf"), "m" * 5000)
write(os.path.join(addon, "data", "memories", "MEMORY.md"), "index")
write(os.path.join(addon, "data", "logs", "visionclaw.log"), "log")
write(os.path.join(addon, "data", "helpers", "__pycache__", "h.pyc"), "the data folder keeps everything")
write(os.path.join(addon, "data", "models", "r", "half.gguf.part"), "a download that was not finished")
found = portable.files(addon)
names = {arc for _full, arc, _size in found}
assert names == {
	"manifest.ini", "globalPlugins/visionClaw/__init__.py", "engine/vcengine.exe", "data/models/q/model.gguf",
	"data/memories/MEMORY.md", "data/logs/visionclaw.log", "data/helpers/__pycache__/h.pyc",
	"data/models/r/half.gguf.part"}, names
# The size is whatever is there now: what is added later is in the next copy.
before = sum(size for _f, _a, size in found)
write(os.path.join(addon, "data", "skills", "mine", "SKILL.md"), "a new skill")
assert sum(size for _f, _a, size in portable.files(addon)) == before + len("a new skill")
found = portable.files(addon)
parts = portable.parts(os.path.join(addon, "data"))
assert parts[0][0] == "models" and parts[0][2] == 2, parts
assert portable.sizeText(8.6 * 1024 ** 3) == "8.6 GB" and portable.sizeText(500) == "500 bytes"

# The place: room, and FAT32's limit of 4 GB for one file.
gb = 1024 ** 3
assert portable.check(True, [3 * gb, 2 * gb], 100 * gb, "FAT32") == (portable.TOO_BIG_FOR_FAT, 5 * gb)
assert portable.check(False, [3 * gb, 2 * gb], 100 * gb, "FAT32") is None
assert portable.check(False, [5 * gb], 100 * gb, "FAT32")[0] == portable.TOO_BIG_FOR_FAT
assert portable.check(True, [5 * gb], 100 * gb, "exFAT") is None
assert portable.check(True, [5 * gb], 5 * gb, "NTFS") == (portable.NO_SPACE, 5 * gb + portable.SPARE)
assert portable.check(True, [5 * gb], None, "") is None

# A portable NVDA in the folder or just inside it; an installed one is not taken for one.
drive = os.path.join(WORK, "drive")
write(os.path.join(drive, "readme.txt"))
assert portable.findNvda(drive) == (None, None)
write(os.path.join(drive, "NVDA", "nvda.exe"))
assert portable.findNvda(drive) == (os.path.join(drive, "NVDA"), portable.PORTABLE)
assert portable.findNvda(os.path.join(drive, "NVDA")) == (os.path.join(drive, "NVDA"), portable.PORTABLE)
installed = os.path.join(WORK, "Program Files", "NVDA")
write(os.path.join(installed, "nvda.exe"))
write(os.path.join(installed, "uninstall.exe"))
assert portable.findNvda(installed) == (installed, portable.INSTALLED)
assert portable.addonFolderOf(os.path.join(drive, "NVDA")) == os.path.join(drive, "NVDA", "userConfig", "addons", "visionClaw")
assert portable.inside(os.path.join(addon, "data", "x"), addon) and not portable.inside(addon + "2", addon)

# --- The settings: carried, taken over once and only by a VisionClaw with no models chosen ---

settings = {"visionModel": "qwen3.5-9b", "coderModel": "qwen3.5-9b-coder", "searchEngine": "google", "updateLastCheck": "1"}
text = portable.settingsText(settings)
assert "updateLastCheck" not in json.loads(text)
target = os.path.join(WORK, "taken")
write(os.path.join(target, portable.SETTINGS_FILE), text)
fresh = {"visionModel": "", "coderModel": "", "searchEngine": "duckduckgo", "updateLastCheck": ""}
assert portable.takeSettings(target, fresh) == {"visionModel": "qwen3.5-9b", "coderModel": "qwen3.5-9b-coder", "searchEngine": "google"}
assert not os.path.exists(os.path.join(target, portable.SETTINGS_FILE))
assert portable.takeSettings(target, fresh) is None
write(os.path.join(target, portable.SETTINGS_FILE), text)
assert portable.takeSettings(target, dict(fresh, visionModel="qwen3.5-2b")) is None
assert not os.path.exists(os.path.join(target, portable.SETTINGS_FILE))
write(os.path.join(target, portable.SETTINGS_FILE), "not json")
assert portable.takeSettings(target, fresh) is None

# --- One .nvda-addon file with everything, which NVDA can open like any other ---

extras = {"data/" + portable.SETTINGS_FILE: text.encode("utf-8")}
out = os.path.join(WORK, "out", portable.BUNDLE_NAME.format(version="9.9.9"))
os.makedirs(os.path.dirname(out))
seen = []
size = portable.writeBundle(found, out, extras, threading.Event(), lambda done, total, name: seen.append((done, total)))
assert size == os.path.getsize(out) and not os.path.exists(out + ".part")
assert seen[-1][0] == seen[-1][1] == sum(s for _f, _a, s in found) + len(extras["data/" + portable.SETTINGS_FILE])
with zipfile.ZipFile(out) as z:
	assert z.testzip() is None
	assert set(z.namelist()) == {arc for _f, arc, _s in found} | set(extras)
	assert z.getinfo("data/models/q/model.gguf").compress_type == zipfile.ZIP_STORED
	assert z.getinfo("manifest.ini").compress_type == zipfile.ZIP_DEFLATED
	unpacked = os.path.join(WORK, "unpacked")
	z.extractall(unpacked)
assert read(os.path.join(unpacked, "data", "models", "q", "model.gguf")) == "m" * 5000
assert portable.takeSettings(os.path.join(unpacked, "data"), fresh)["searchEngine"] == "google"

# Stopped, nothing is left behind, and the file that was there stays as it was.
stop = threading.Event()
stop.set()
try:
	portable.writeBundle(found, out, extras, stop)
	raise AssertionError("not stopped")
except portable.Stopped:
	pass
assert os.path.getsize(out) == size and os.listdir(os.path.dirname(out)) == [os.path.basename(out)]

# --- Straight into a portable NVDA: copied, and a second copy skips what is there already ---

into = portable.addonFolderOf(os.path.join(drive, "NVDA"))
write(os.path.join(into, "data", "memories", "theirs.md"), "the drive's own memory")
copied, skipped = portable.copyTo(found, into, extras)
assert (copied, skipped) == (len(found) + 1, 0)
assert tree(into) == {arc for _f, arc, _s in found} | set(extras) | {"data/memories/theirs.md"}
copied, skipped = portable.copyTo(found, into, extras)
assert (copied, skipped) == (1, len(found)), (copied, skipped)
write(os.path.join(addon, "data", "memories", "MEMORY.md"), "a changed index")
copied, skipped = portable.copyTo(portable.files(addon), into, extras)
assert read(os.path.join(into, "data", "memories", "MEMORY.md")) == "a changed index"
try:
	portable.copyTo(found, os.path.join(WORK, "stopped"), extras, stop)
	raise AssertionError("not stopped")
except portable.Stopped:
	pass
assert not any(name.endswith(".vccopy") for name in tree(os.path.join(WORK, "stopped")))

# A build never carries anyone's data folder.
with open(os.path.join(ROOT, "build.py"), encoding="utf-8") as f:
	assert 'd == "data"' in f.read()

print("OK")
