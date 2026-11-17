# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - keeping speech and braille alive. A screen reader user who loses both has lost the computer, so
# before a speech synthesizer or braille display is switched, plain rules decide whether the switch is refused,
# needs a warning, or is fine. What happened with each driver on this computer is remembered, so the user can
# be warned before a driver that failed here is tried again. No NVDA dependencies.

import json
import os
import threading
import time

SYNTH, DISPLAY = "synthesizer", "braille display"
KINDS = [SYNTH, DISPLAY]
REFUSE, WARN, FINE = "refuse", "warn", "fine"
# What happened when a driver was tried.
WORKED, FAILED, REVERTED = "worked", "failed", "reverted"
# The drivers that give no output at all.
NO_SPEECH = "silence"
NO_BRAILLE = "noBraille"
# A speech volume below this cannot be heard.
QUIET_VOLUME = 10


def kindOf(part):
	"""Which kind of driver a request is about, from its words."""
	return DISPLAY if "braille" in (part or "").lower() else SYNTH


class DriverNotes:
	"""What happened with each driver on this computer, kept between sessions."""

	def __init__(self, path):
		self._path = path
		self._lock = threading.Lock()
		self._notes = None

	def _load(self):
		if self._notes is None:
			try:
				with open(self._path, encoding="utf-8") as f:
					data = json.load(f)
				self._notes = data if isinstance(data, dict) else {}
			except (OSError, ValueError):
				self._notes = {}
		return self._notes

	def record(self, kind, name, outcome):
		with self._lock:
			note = self._load().setdefault(f"{kind}:{name}", {WORKED: 0, FAILED: 0, REVERTED: 0})
			note[outcome] = note.get(outcome, 0) + 1
			note["last"] = outcome
			note["time"] = time.time()
			try:
				os.makedirs(os.path.dirname(self._path), exist_ok=True)
				tmp = self._path + ".tmp"
				with open(tmp, "w", encoding="utf-8") as f:
					json.dump(self._notes, f, indent=1)
				os.replace(tmp, self._path)
			except OSError:
				pass

	def get(self, kind, name):
		with self._lock:
			return dict(self._load().get(f"{kind}:{name}", {}))

	def warning(self, kind, name, shown=None):
		"""A sentence about trouble with this driver earlier on this computer, or ""."""
		note = self.get(kind, name)
		shown = shown or name
		failed, reverted, worked = note.get(FAILED, 0), note.get(REVERTED, 0), note.get(WORKED, 0)
		if not failed and not reverted:
			return ""
		parts = []
		if failed:
			parts.append(f"could not be started {_times(failed)}")
		if reverted:
			parts.append(f"was switched back {_times(reverted)} because it was not confirmed to work")
		text = f"Earlier on this computer, {shown} " + " and ".join(parts) + "."
		if worked and note.get("last") == WORKED:
			text += " The last time it worked."
		return text

	def problems(self, kind):
		"""Sentences about every driver of a kind that gave trouble here."""
		with self._lock:
			names = [key.split(":", 1)[1] for key in self._load() if key.startswith(kind + ":")]
		return [text for text in (self.warning(kind, name) for name in names) if text]


def _times(count):
	return "once" if count == 1 else f"{count} times"


def judge(kind, target, synth, display, notes=None, targetShown=None):
	"""Whether a switch may go ahead. target is the driver to switch to; synth and display are the drivers in
	use now (None if there is none). Returns (verdict, message): REFUSE with the reason, WARN with what the user
	must know first, or FINE with an empty message."""
	shown = targetShown or target
	hasSpeech = bool(synth) and synth != NO_SPEECH
	hasBraille = bool(display) and display != NO_BRAILLE
	if kind == SYNTH and target == NO_SPEECH:
		if not hasBraille:
			return REFUSE, (
				"That would leave you with no speech and no braille, so you could not use the computer. "
				"Connect a braille display first. To silence NVDA for a moment, press NVDA+S instead; "
				"pressing it again brings speech back."
			)
		return WARN, "This turns speech off completely. You will have braille only."
	if kind == DISPLAY and target == NO_BRAILLE:
		if not hasSpeech:
			return REFUSE, "That would leave you with no braille and no speech, so you could not use the computer."
		return WARN, "This turns braille off. You will have speech only."
	trouble = notes.warning(kind, target, shown) if notes is not None else ""
	return (WARN, trouble) if trouble else (FINE, "")


def judgeVolume(value, display):
	"""Whether the speech volume may be set to value. Returns (verdict, message) like judge."""
	if value >= QUIET_VOLUME:
		return FINE, ""
	if not display or display == NO_BRAILLE:
		return REFUSE, (
			f"A volume of {value} is too quiet to hear, and there is no braille display, so you could not use "
			f"the computer. The lowest volume VisionClaw will set without braille is {QUIET_VOLUME}."
		)
	return WARN, f"A volume of {value} is too quiet to hear. You will have braille only."
