# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - VisionClaw's own log, for finding out afterwards why something went wrong. NVDA's log is often
# switched off, and then nothing could be read; this one is a plain text file in VisionClaw's data folder that
# does not depend on NVDA's logging level. It records every request, every step, every form a model filled in,
# every question put to a model with its answer, every tool with its result, and every error with the place in
# the code where it happened. It stays on this computer: nothing here sends it anywhere.
# The file is kept small: when it is full it is put aside under a number, and only a few old ones are kept.
# Nothing here may raise: a log that fails must never stop the work it records. No NVDA dependencies.

import os
import sys
import threading
import time
import traceback

DETAILED, BRIEF, OFF = "detailed", "brief", "off"
LEVELS = (DETAILED, BRIEF, OFF)
NAME = "visionclaw.log"
MAX_BYTES = 2 * 2 ** 20
# How many full logs are kept beside the one being written.
KEPT = 3
# One entry is cut at this length, so that a single huge prompt cannot fill the log.
MAX_ENTRY = 24000

_lock = threading.Lock()
_state = {"path": None, "level": OFF, "max": MAX_BYTES}


def start(folder, level=DETAILED, maxBytes=MAX_BYTES):
	"""Begin writing to visionclaw.log in a folder. Returns the path, or None if the folder cannot be used."""
	try:
		os.makedirs(folder, exist_ok=True)
		with _lock:
			_state["path"] = os.path.join(folder, NAME)
			_state["level"] = level if level in LEVELS else DETAILED
			_state["max"] = max(4096, int(maxBytes))
	except Exception:
		return None
	return _state["path"]


def stop():
	with _lock:
		_state["path"] = None
		_state["level"] = OFF


def setLevel(level):
	with _lock:
		_state["level"] = level if level in LEVELS else DETAILED


def level():
	return _state["level"]


def path():
	"""Where the log is written, or None when it was never started."""
	return _state["path"]


def on():
	return _state["path"] is not None and _state["level"] != OFF


def detailed():
	return _state["path"] is not None and _state["level"] == DETAILED


def _rotate(path):
	"""Put the full log aside as .1, the one before it as .2, and so on; the oldest is dropped."""
	for number in range(KEPT, 0, -1):
		old = f"{path}.{number - 1}" if number > 1 else path
		try:
			if os.path.isfile(old):
				os.replace(old, f"{path}.{number}")
		except OSError:
			pass


def _write(area, text):
	try:
		text = str(text)
		if len(text) > MAX_ENTRY:
			text = text[:MAX_ENTRY] + f" ...[{len(text) - MAX_ENTRY} more characters left out]"
		now = time.time()
		stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)) + f".{int(now * 1000) % 1000:03d}"
		lines = text.splitlines() or [""]
		entry = f"{stamp} [{threading.current_thread().name}] {area}: {lines[0]}\n" + "".join(
			f"\t{line}\n" for line in lines[1:])
		with _lock:
			path = _state["path"]
			if path is None:
				return
			try:
				if os.path.getsize(path) + len(entry) > _state["max"]:
					_rotate(path)
			except OSError:
				pass
			with open(path, "a", encoding="utf-8", errors="replace") as f:
				f.write(entry)
	except Exception:
		pass


def log(area, text):
	"""Something worth knowing in every log: a request, a step, a result, a choice."""
	if on():
		_write(area, text)


def detail(area, text):
	"""Something only the detailed log holds: whole prompts, whole answers, whole results."""
	if detailed():
		_write(area, text)


def error(area, text, exc=None):
	"""An error, with the place in the code where it happened. exc: the exception; without it, the one being
	handled now, if any."""
	if not on():
		return
	try:
		if exc is None:
			exc = sys.exc_info()[1]
		trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc is not None else ""
	except Exception:
		trace = ""
	_write(area, f"ERROR: {text}" + (f"\n{trace.rstrip()}" if trace else ""))


def tail(lines=40):
	"""The last lines of the log, for showing or for a test."""
	path = _state["path"]
	if path is None:
		return ""
	try:
		with _lock:
			with open(path, encoding="utf-8", errors="replace") as f:
				return "".join(f.readlines()[-lines:])
	except OSError:
		return ""


def files():
	"""The log and the older ones kept beside it, newest first."""
	path = _state["path"]
	if path is None:
		return []
	return [name for name in [path] + [f"{path}.{number}" for number in range(1, KEPT + 1)] if os.path.isfile(name)]
