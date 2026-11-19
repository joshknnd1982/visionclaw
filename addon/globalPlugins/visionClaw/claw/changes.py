# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a record of every setting VisionClaw has changed: what it was, what it became, when, and which
# request asked for it. Nothing VisionClaw changes is lost: the user can ask what was changed and have any of
# it put back. Kept between sessions. No NVDA dependencies.

import json
import os
import threading
import time

from .memory import words

MAX_CHANGES = 200
# Words that ask for an undo; they do not say which setting is meant.
_UNDO_WORDS = words(
	"undo revert restore put back change changed changes return reset previous before again last earlier original "
	"visionclaw setting settings was were what how way had")


class ChangeLog:
	def __init__(self, path):
		self._path = path
		self._lock = threading.Lock()
		self._changes = None

	def _load(self):
		if self._changes is None:
			try:
				with open(self._path, encoding="utf-8") as f:
					data = json.load(f)
				self._changes = [c for c in data if isinstance(c, dict) and "setting" in c]
			except (OSError, ValueError):
				self._changes = []
		return self._changes

	def _save(self):
		try:
			os.makedirs(os.path.dirname(self._path), exist_ok=True)
			tmp = self._path + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				json.dump(self._changes, f, indent=1)
			os.replace(tmp, self._path)
		except OSError:
			pass

	def add(self, setting, label, old, new, oldShown, newShown, request="", profile="", program=""):
		"""Record a change. old and new are the values as the setting stores them; the shown ones are for people.
		profile and program: for a setting changed for one program only, NVDA's configuration profile that holds
		it and what the program is called (claw/profiles.py)."""
		with self._lock:
			changes = self._load()
			entry = {
				"setting": setting, "label": label, "old": old, "new": new, "oldShown": str(oldShown),
				"newShown": str(newShown), "request": request[:200], "time": time.time(), "undone": False,
			}
			if profile:
				entry["profile"], entry["program"] = profile, program or profile
			changes.append(entry)
			del changes[:-MAX_CHANGES]
			self._save()

	def pending(self):
		"""The changes that have not been undone, newest first."""
		with self._lock:
			return [dict(c) for c in reversed(self._load()) if not c.get("undone")]

	def markProfileGone(self, profile):
		"""A program's configuration profile was deleted: what was changed in it is gone with it."""
		with self._lock:
			for stored in self._load():
				if stored.get("profile") == profile:
					stored["undone"] = True
			self._save()

	def markUndone(self, change):
		with self._lock:
			for stored in self._load():
				if stored["time"] == change["time"] and stored["setting"] == change["setting"]:
					stored["undone"] = True
			self._save()

	def text(self, limit=12):
		"""The changes that still stand, newest first, in sentences."""
		lines = []
		for change in self.pending()[:limit]:
			when = time.strftime("%d %B at %H:%M", time.localtime(change["time"]))
			# A capital at the start only: the name of a file keeps its own capitals.
			label = change["label"][:1].upper() + change["label"][1:]
			where = f", only in {change.get('program') or change['profile']}" if change.get("profile") else ""
			lines.append(f"{label}{where}: from {change['oldShown']} to {change['newShown']}, on {when}.")
		return "\n".join(lines)


def meant(what):
	"""The words of a request that say which setting is meant, without the words that only ask for an undo."""
	return words(what) - _UNDO_WORDS


def choose(what, pending, describe):
	"""Which recorded change a request to undo is about.
	describe(change) gives the words a setting is known by. Returns (change, None), or (None, reason) where
	reason is "nothing" (nothing was changed) or "other" (the request names something that was not changed)."""
	if not pending:
		return None, "nothing"
	named = meant(what)
	if not named:
		return pending[0], None  # "undo that": the newest change
	for change in pending:
		if named & describe(change):
			return change, None
	return None, "other"
