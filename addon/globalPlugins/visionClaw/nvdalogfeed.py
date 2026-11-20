# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - NVDA's own log, read while VisionClaw works, and watched for errors where the user wants that
# (docs/PLAN-nvda-log.md). The owner said on 2026-11-19: "visionclaw can query the various nvda logs to get all kinds of
# realtime info. this is for new visionclaw skills, system prompts, future features", and that "all existing skills and
# system prompts should be able to query the log".
#   - While VisionClaw works on a request, and only where the setting "useNvdaLog" is on (the default): a place at the end
#     of the log before each step (mark), what NVDA wrote during the step (since), what it wrote in the last minutes
#     (recent) for the skills and for a question about what went wrong, and the add-ons' names, so that a line names the
#     add-on it came from (claw/orchestrator.py, claw/skilllog.py).
#   - The watch, only where the user turned on "nvdaLogWatch" (off by default): every WATCH_SECONDS, what NVDA wrote since
#     the last look; an error or a freeze is said in one sentence, at most once a minute for each add-on or part of NVDA,
#     never while the microphone is open, never about VisionClaw's own errors.
# Only what nvdalogtools may read: never the levels IO, DEBUG and DEBUG_UNREDACTED (claw/nvdalog.py). Nothing is sent
# anywhere. Nothing here may raise.

import threading
import time

from . import nvdalogtools
from .claw import debuglog, nvdalog, skilllog
from .nvdatools import onMain

# How often the watch looks at the end of NVDA's log, and how long it says nothing more about one source.
WATCH_SECONDS = 5
QUIET_SECONDS = 60
# How long the add-ons' names are kept before they are read again from the running NVDA.
ADDONS_SECONDS = 60


class Feed:
	"""using() and watching(): the two settings. say(text): VisionClaw's own speech. stopped: an event set when NVDA closes.
	listening(): whether the microphone is open, when nothing may be spoken."""

	def __init__(self, using, watching, say, stopped, listening=lambda: False, clock=time.time):
		self._using = using
		self._watching = watching
		self._say = say
		self._stopped = stopped
		self._listening = listening
		self._clock = clock
		self._addons = (None, None)
		self._addonsWhen = None
		self._told = {}
		self._toldOnce = False
		self._thread = None

	def _on(self):
		try:
			return bool(self._using())
		except Exception:
			return False

	# For the orchestrator, while it works on a request.

	def mark(self):
		"""A place at the end of NVDA's log, or None where it is not read or there is none."""
		return nvdalogtools.mark() if self._on() else None

	def since(self, place):
		"""What NVDA wrote after a place from mark(), readable entries only."""
		return nvdalogtools.since(place) if place else []

	def recent(self, seconds=skilllog.RECENT_SECONDS):
		"""What NVDA wrote in the last minutes, readable entries only; [] where the log is not read."""
		if not self._on():
			return []
		try:
			found = nvdalogtools.readCurrent()
			if not found:
				return []
			return nvdalog.entriesSince(found[0], since=self._clock() - seconds)
		except Exception as e:
			debuglog.error("nvdalog", "NVDA's recent log could not be read", e)
			return []

	def addons(self):
		"""(modules, names) of the installed add-ons, read from the running NVDA at most once a minute."""
		now = self._clock()
		if self._addonsWhen is None or now - self._addonsWhen > ADDONS_SECONDS:
			try:
				names, modules = onMain(nvdalogtools.addonsKnown) or ({}, {})
				self._addons = (modules, names)
			except Exception:
				self._addons = (None, None)
			self._addonsWhen = now
		return self._addons

	# The watch.

	def startWatch(self):
		if self._thread is None:
			self._thread = threading.Thread(target=self._watch, name="VisionClaw watches NVDA's log", daemon=True)
			self._thread.start()

	def _watch(self):
		place = None
		while not self._stopped.wait(WATCH_SECONDS):
			try:
				if not self._watching():
					place = None
					continue
				if place is None:
					place = nvdalogtools.mark()
					continue
				entries = nvdalogtools.since(place)
				place = nvdalogtools.mark() or place
				for sentence in self.news(entries):
					if not self._listening():
						self._say(sentence)
			except Exception as e:
				debuglog.error("nvdalog", "The watch of NVDA's log failed once", e)

	def news(self, entries):
		"""The sentences the watch says about new entries: one for each add-on or part of NVDA that logged an error, and one
		for a freeze NVDA recovered from, each at most once in QUIET_SECONDS; never about VisionClaw's own errors. The
		first sentence of a run says how to hear more."""
		modules, names = self.addons()
		now = self._clock()
		said = []
		for fact in nvdalog.factsFor(entries, "errors", modules, names):
			if nvdalog.isOwn(fact, modules):
				continue
			addon = fact.get("addon") or ""
			source = addon or "nvda"
			if now - self._told.get(source, -QUIET_SECONDS - 1) < QUIET_SECONDS:
				continue
			self._told[source] = now
			name = (names or {}).get(addon) or addon
			said.append(f"NVDA logged an error from the add-on {name}." if addon else "NVDA logged an error.")
		for freeze in nvdalog.freezes(entries, modules):
			# Only a freeze NVDA recovered from: while NVDA is frozen it says nothing anyway.
			recovered = getattr(freeze, "recovered", None)
			seconds = recovered if isinstance(recovered, (int, float)) and not isinstance(recovered, bool) else None
			if not seconds or now - self._told.get("freeze", -QUIET_SECONDS - 1) < QUIET_SECONDS:
				continue
			self._told["freeze"] = now
			said.append(f"NVDA was frozen for {nvdalog.durationWords(seconds)}.")
		if said and not self._toldOnce:
			self._toldOnce = True
			said[-1] += " To hear more, ask VisionClaw to check NVDA's log."
		return said
