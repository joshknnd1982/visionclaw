# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - everything VisionClaw keeps lives inside the add-on's own folder, and the whole of it can be
# carried away. The owner said on 2026-11-18: "everything in the data folder, no exceptions, must be moved,
# copied, made portable. and on subsequent installs of the addon onto local machines, non-portable, the data
# folder must go inside the addon folder itself."
#
# What this file does, all of it plain Python:
#   the data folder is "data" inside the add-on folder; at start, what an older VisionClaw kept in NVDA's
#     configuration folder ("visionClaw") is moved in (moveIn);
#   NVDA deletes an add-on's folder when it is updated or removed, after asking the old copy's onUninstall.
#     There the data folder is moved into the newer version's folder, or, when VisionClaw is removed, back to
#     NVDA's configuration folder, where a later install finds it (carryOver). Nothing is deleted;
#   a portable copy is the whole add-on folder, the data folder with nothing left out, and the VisionClaw
#     settings: as one .nvda-addon file that installs on any computer (writeBundle), or copied straight into a
#     portable NVDA, as on a flash drive (copyTo). The settings are taken over once, by an NVDA whose
#     VisionClaw has no models chosen yet (takeSettings).
# Moving within one drive is a rename, so even many gigabytes of models move at once. Every long job takes a
# stop event and says how far it is.
# No NVDA dependencies: installTasks.py loads this file by its path.

import json
import os
import shutil
import zipfile

DATA = "data"
# The folder in NVDA's configuration where VisionClaw 1.3.0 and older kept everything, and where the data
# waits after the add-on was removed.
OLD_NAME = "visionClaw"
PENDING = ".pendingInstall"
# The VisionClaw settings, carried in the data folder of a copy and taken over once.
SETTINGS_FILE = "carried-settings.json"
# Settings that belong to this computer, not to the copy.
NOT_CARRIED = frozenset(("updateLastCheck",))
BUNDLE_NAME = "VisionClaw-{version}-portable.nvda-addon"
# FAT32, used by many flash drives, holds no file of 4 GB or more.
FAT_LIMIT = 4 * 1024 ** 3 - 1
FAT_NAMES = frozenset(("FAT", "FAT32", "FAT16", "FAT12"))
# Room left over on the drive, so that it is not filled to the last byte.
SPARE = 64 * 1024 ** 2
CHUNK = 4 * 1024 * 1024
# Files that do not get smaller in a zip file, or are too big to be worth the time: kept as they are.
STORED_EXTS = frozenset((
	".gguf", ".bin", ".zip", ".nvda-addon", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".gz", ".7z", ".mp3",
	".ogg", ".part"))
STORED_SIZE = 32 * 1024 ** 2
ZIP64_SIZE = 1024 ** 3
# A file is the same when its size is and its time is within this many seconds (FAT keeps times in 2 seconds).
SAME_TIME = 2
# What findNvda says about a folder.
PORTABLE, INSTALLED = "portable", "installed"
# What check says is wrong with a place.
NO_SPACE, TOO_BIG_FOR_FAT = "space", "fat"


class Stopped(Exception):
	"""The user stopped the copy."""


def _same(a, b):
	return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def inside(path, folder):
	"""Whether path is folder or something in it."""
	path, folder = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))
	return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def _remove(path):
	if os.path.isdir(path) and not os.path.islink(path):
		shutil.rmtree(path)
	else:
		os.remove(path)


def _move(src, dst):
	try:
		os.replace(src, dst)
	except OSError:
		# Another drive: copied, then deleted.
		shutil.move(src, dst)


def merge(src, dst):
	"""Move everything in src into dst. Where both have a file of the same name, src's is kept: src is what this
	computer had. Folders are merged. src is removed when it is left empty. Gives back (moved, problems): how
	many things were moved, and (path, error) for each that could not be, which stays where it was."""
	moved, problems = 0, []
	try:
		os.makedirs(dst, exist_ok=True)
		names = sorted(os.listdir(src))
	except OSError as e:
		return 0, [(src, e)]
	for name in names:
		s, d = os.path.join(src, name), os.path.join(dst, name)
		try:
			if not os.path.lexists(d):
				_move(s, d)
				moved += 1
			elif os.path.isdir(s) and os.path.isdir(d):
				more, trouble = merge(s, d)
				moved += more
				problems.extend(trouble)
			else:
				_remove(d)
				_move(s, d)
				moved += 1
		except OSError as e:
			problems.append((s, e))
	try:
		os.rmdir(src)
	except OSError:
		pass
	return moved, problems


def moveIn(oldDir, dataDir):
	"""At start: what an older VisionClaw, or a removed one, kept in oldDir comes into the add-on's data folder.
	Gives back (moved, problems) as merge does; (0, []) when there is nothing to move."""
	if not os.path.isdir(oldDir) or _same(oldDir, dataDir):
		return 0, []
	return merge(oldDir, dataDir)


def carryOver(addonDir, configDir):
	"""For installTasks.onUninstall, which NVDA calls just before it deletes the add-on's folder: the data
	folder goes into the newer version's folder when this is an update, or back to NVDA's configuration folder
	when VisionClaw is removed, so that nothing is lost and a later install takes it in again. A copy that was
	never finished installing has no data of this computer's: nothing is done for it. Gives back the folder
	the data went to, or None."""
	addonDir = os.path.abspath(addonDir).rstrip(os.sep)
	data = os.path.join(addonDir, DATA)
	if not os.path.isdir(data) or addonDir.endswith(PENDING):
		return None
	pending = addonDir + PENDING
	kept = os.path.join(configDir, OLD_NAME)
	target = os.path.join(pending, DATA) if os.path.isdir(pending) else kept
	merge(data, target)
	if os.path.isdir(data) and target != kept:
		# What could not go into the newer version waits in the configuration folder; it is moved in at start.
		merge(data, kept)
	return target


def files(addonDir):
	"""Every file of the add-on, as (full path, name in the copy, size): the data folder with nothing left out,
	and the rest without Python's compiled files, which NVDA makes again."""
	addonDir = os.path.abspath(addonDir)
	found = []
	for dirpath, dirnames, names in os.walk(addonDir):
		rel = os.path.relpath(dirpath, addonDir)
		inData = rel == DATA or rel.startswith(DATA + os.sep)
		dirnames.sort()
		if not inData:
			dirnames[:] = [d for d in dirnames if d != "__pycache__"]
		for name in sorted(names):
			if not inData and name.endswith(".pyc"):
				continue
			full = os.path.join(dirpath, name)
			try:
				size = os.path.getsize(full)
			except OSError:
				continue
			found.append((full, os.path.relpath(full, addonDir).replace(os.sep, "/"), size))
	return found


def parts(dataDir):
	"""What is in the data folder, as (name, size, number of files), biggest first: for telling the user."""
	result = []
	try:
		names = os.listdir(dataDir)
	except OSError:
		return result
	for name in names:
		full = os.path.join(dataDir, name)
		if os.path.isdir(full):
			size = count = 0
			for dirpath, _dirs, names2 in os.walk(full):
				for n in names2:
					try:
						size += os.path.getsize(os.path.join(dirpath, n))
						count += 1
					except OSError:
						pass
		else:
			try:
				size, count = os.path.getsize(full), 1
			except OSError:
				continue
		result.append((name, size, count))
	result.sort(key=lambda p: (-p[1], p[0]))
	return result


def sizeText(size):
	"""A size as a person says it."""
	for unit, step in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
		if size >= step:
			value = size / step
			return f"{value:.1f} {unit}" if value < 100 else f"{value:.0f} {unit}"
	return f"{size} bytes"


def check(bundle, sizes, free, fileSystem):
	"""What stands in the way of writing these files to a place, or None. bundle: one .nvda-addon file holds
	them all. Gives back (NO_SPACE, needed) or (TOO_BIG_FOR_FAT, size of the biggest file)."""
	total = sum(sizes)
	biggest = total if bundle else max(sizes, default=0)
	if (fileSystem or "").upper() in FAT_NAMES and biggest > FAT_LIMIT:
		return TOO_BIG_FOR_FAT, biggest
	if free is not None and total + SPARE > free:
		return NO_SPACE, total + SPARE
	return None


def findNvda(folder):
	"""The NVDA in a folder, or in one of the folders just inside it, as (its folder, PORTABLE or INSTALLED),
	or (None, None). An installed NVDA has its uninstaller beside it; its add-ons are not kept there."""
	candidates = [folder]
	try:
		candidates += [os.path.join(folder, n) for n in sorted(os.listdir(folder))]
	except OSError:
		pass
	found = [c for c in candidates if os.path.isfile(os.path.join(c, "nvda.exe"))]
	if not found:
		return None, None
	portable = [c for c in found if not os.path.isfile(os.path.join(c, "uninstall.exe"))]
	if portable:
		return portable[0], PORTABLE
	return found[0], INSTALLED


def addonFolderOf(nvdaDir):
	"""Where VisionClaw goes in a portable NVDA."""
	return os.path.join(nvdaDir, "userConfig", "addons", OLD_NAME)


def settingsText(section):
	"""The VisionClaw settings as the text of SETTINGS_FILE."""
	return json.dumps({k: v for k, v in section.items() if k not in NOT_CARRIED}, indent=1, sort_keys=True)


def takeSettings(dataDir, current):
	"""The carried settings to take over, or None. They are taken only by a VisionClaw that has no model chosen
	yet: one that was used already keeps its own. The file is taken away either way, so this happens once."""
	path = os.path.join(dataDir, SETTINGS_FILE)
	if not os.path.isfile(path):
		return None
	try:
		with open(path, encoding="utf-8") as f:
			carried = json.load(f)
	except (OSError, ValueError):
		carried = None
	try:
		os.remove(path)
	except OSError:
		pass
	if not isinstance(carried, dict) or current.get("visionModel") or current.get("coderModel"):
		return None
	return {k: v for k, v in carried.items() if k in current and k not in NOT_CARRIED}


def _copyStream(src, dst, stop, progress, done, total, name):
	while True:
		if stop is not None and stop.is_set():
			raise Stopped()
		chunk = src.read(CHUNK)
		if not chunk:
			return done
		dst.write(chunk)
		done += len(chunk)
		if progress:
			progress(done, total, name)


def writeBundle(found, out, extras=None, stop=None, progress=None):
	"""One .nvda-addon file with every file of found and extras ({name in the copy: bytes}). Written beside
	out first and put in its place only when whole; stopped or failed, nothing is left behind. Gives back its
	size."""
	extras = extras or {}
	total = sum(size for _full, _arc, size in found) + sum(len(b) for b in extras.values())
	temp = out + ".part"
	done = 0
	try:
		with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
			for full, arc, size in found:
				if arc in extras:
					continue
				info = zipfile.ZipInfo.from_file(full, arc, strict_timestamps=False)
				if size >= STORED_SIZE or os.path.splitext(arc)[1].lower() in STORED_EXTS:
					info.compress_type = zipfile.ZIP_STORED
				else:
					info.compress_type = zipfile.ZIP_DEFLATED
				with open(full, "rb") as src, z.open(info, "w", force_zip64=size >= ZIP64_SIZE) as dst:
					done = _copyStream(src, dst, stop, progress, done, total, arc)
			for arc, data in sorted(extras.items()):
				if stop is not None and stop.is_set():
					raise Stopped()
				z.writestr(arc, data)
				done += len(data)
				if progress:
					progress(done, total, arc)
		os.replace(temp, out)
	except BaseException:
		try:
			os.remove(temp)
		except OSError:
			pass
		raise
	return os.path.getsize(out)


def _unchanged(full, target):
	try:
		a, b = os.stat(full), os.stat(target)
	except OSError:
		return False
	return a.st_size == b.st_size and abs(a.st_mtime - b.st_mtime) <= SAME_TIME


def copyTo(found, destDir, extras=None, stop=None, progress=None):
	"""Every file of found, and extras, copied into destDir as the add-on's folder. What is there already and
	not in found stays; a file that is there with the same size and time is skipped, so a copy that was
	stopped is finished quickly the next time. Gives back (copied, skipped)."""
	extras = extras or {}
	total = sum(size for _full, _arc, size in found) + sum(len(b) for b in extras.values())
	done = copied = skipped = 0
	for full, arc, size in found:
		if arc in extras:
			continue
		target = os.path.join(destDir, *arc.split("/"))
		if _unchanged(full, target):
			done += size
			skipped += 1
			if progress:
				progress(done, total, arc)
			continue
		os.makedirs(os.path.dirname(target), exist_ok=True)
		temp = target + ".vccopy"
		try:
			with open(full, "rb") as src, open(temp, "wb") as dst:
				done = _copyStream(src, dst, stop, progress, done, total, arc)
			shutil.copystat(full, temp)
			os.replace(temp, target)
		except BaseException:
			try:
				os.remove(temp)
			except OSError:
				pass
			raise
		copied += 1
	for arc, data in sorted(extras.items()):
		if stop is not None and stop.is_set():
			raise Stopped()
		target = os.path.join(destDir, *arc.split("/"))
		os.makedirs(os.path.dirname(target), exist_ok=True)
		with open(target, "wb") as f:
			f.write(data)
		done += len(data)
		copied += 1
		if progress:
			progress(done, total, arc)
	return copied, skipped
