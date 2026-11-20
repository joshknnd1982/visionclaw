# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - accessibility trouble noticed where the user stays, and help offered in one sentence, which the user takes
# with NVDA+Alt+Y or refuses by doing nothing (claw/troubles.py says what is trouble and what is said). Where the user
# stays a moment after the focus moved, NVDA's facts of the place are read (gototools.spot) and, where the user lets
# VisionClaw read it, how many errors NVDA logged in the program just now (nvdalogfeed.py). Nothing is ever done by
# itself: the help is a request the user starts with the key, carried out like any other and asked about before
# anything is changed. Never a fault: an error here is written to VisionClaw's log and nothing is said.

import os
import time

import addonHandler
import config
import scriptHandler
import ui
import wx

from . import gototools
from .claw import debuglog, landing, troubles

addonHandler.initTranslation()

# How long NVDA waits for a second press of the key, in milliseconds.
DOUBLE_MS = 450


def _conf():
	return config.conf["visionClaw"]


class HelpOffers:
	"""Noticing trouble and offering help, for one running VisionClaw. speak: how VisionClaw speaks (_speak)."""

	def __init__(self, plugin, folder, speak):
		self.plugin = plugin
		self.speak = speak
		self.offers = troubles.Offers(os.path.join(folder, troubles.FILE) if folder else None)
		self._timer = None
		self._generation = 0
		self._press = None
		self._lastLog = None

	def on(self):
		try:
			return bool(_conf()["offerHelp"])
		except Exception:
			return False

	# --- Noticing ---

	def focusMoved(self):
		"""The focus moved: the place is looked at once the user stays there a moment. Main thread; never a fault."""
		try:
			self._generation += 1
			if self._timer is not None:
				self._timer.Stop()
				self._timer = None
			if self.on():
				self._timer = wx.CallLater(troubles.SETTLE_MS, self._look, self._generation)
		except Exception as e:
			debuglog.error("offer", "The look for trouble could not be planned", e)

	def _busy(self):
		"""Whether this is no moment for an offer: VisionClaw works on a request, the overlay is open, the microphone is
		open, or NVDA reads on by itself."""
		plugin = self.plugin
		task = getattr(plugin, "clawTask", None)
		if task is not None and not task.finished:
			return True
		if getattr(plugin, "_overlayDoc", None) is not None:
			return True
		try:
			if plugin.voice.listening():
				return True
		except Exception:
			pass
		try:
			from speech.sayAll import SayAllHandler
			if SayAllHandler.isRunning():
				return True
		except Exception:
			pass
		return False

	def _followed(self, app):
		"""Whether the user is already having this program made accessible window after window (appaccesstools.py)."""
		try:
			from . import appaccesstools
			from .claw import fixes
			return bool(appaccesstools.isFollowed(self.plugin, fixes.scopeOf(app=app)))
		except Exception:
			return False

	def _errors(self, app):
		"""How many errors NVDA logged in the program in front in the last minute, read at most once a minute; 0 where the
		user does not let VisionClaw read NVDA's log. VisionClaw's own errors never count."""
		now = time.monotonic()
		if self._lastLog is not None and now - self._lastLog < troubles.LOG_SECONDS:
			return 0
		self._lastLog = now
		feed = getattr(self.plugin, "nvdaLogFeed", None)
		if feed is None or not app:
			return 0
		try:
			entries = feed.recent(troubles.LOG_SECONDS)
		except Exception:
			return 0
		app = app.lower()
		count = 0
		for entry in entries:
			path = (getattr(entry, "codepath", "") or "").lower()
			if getattr(entry, "level", "") not in ("ERROR", "CRITICAL") or "visionclaw" in path:
				continue
			if f"appmodules.{app}" in path or app in " ".join(getattr(entry, "lines", [])[:3]).lower():
				count += 1
		return count

	def _namesOn(self):
		return bool(getattr(getattr(self.plugin, "namer", None), "on", False))

	def _look(self, generation):
		try:
			if generation != self._generation or not self.on() or self._busy():
				return
			# The window's controls are counted only where the focus looks like trouble already: NVDA's main thread is not
			# held up after every move.
			facts = gototools.spot(False)
			if landing.nowhere(facts) or facts.get("focusRole") == "DIALOG":
				facts = gototools.spot(True)
			app = facts.get("app") or ""
			errors = self._errors(app)
			kind = troubles.detect(facts, self._namesOn(), errors, self._followed(app))
			if kind is None or not self.offers.due(kind, facts):
				return
			self.offers.offered(kind, facts)
			text = troubles.offerText(kind, facts, errors)
			debuglog.log("offer", f"Trouble noticed ({kind}) where the user is: {facts}. Offered: {text}")
			self.speak(text)
		except Exception as e:
			debuglog.error("offer", "Where the user is could not be checked for trouble", e)

	# --- The key ---

	def press(self):
		"""NVDA+Alt+Y: once, the help offered is taken (or, with nothing offered, the place is looked at now, and offers
		in a program where they were stopped are allowed again); twice, no more offers in this program. Main thread."""
		if scriptHandler.getLastScriptRepeatCount() >= 1:
			if self._press is not None:
				self._press.Stop()
				self._press = None
			app = gototools.spot(False).get("app") or ""
			self.offers.decline(app)
			debuglog.log("offer", f"The user wants no more offers of help in {app}.")
			ui.message(troubles.declinedText(app))
			return
		self._press = wx.CallLater(DOUBLE_MS, self._pressedOnce)

	def _pressedOnce(self):
		self._press = None
		try:
			taken = self.offers.take()
			facts = gototools.spot(True)
			app = facts.get("app") or ""
			if taken is None:
				if self.offers.allow(app):
					ui.message(troubles.allowedText(app))
					return
				# Nothing was offered: the place is looked at now, and the help is given at once where there is trouble.
				kind = troubles.detect(facts, False, 0, False)
				if kind is None:
					ui.message(troubles.nothingText(app))
					return
				taken = (kind, facts)
			self._help(*taken)
		except Exception as e:
			debuglog.error("offer", "The help that was offered could not be started", e)
			# Translators: Said when the help VisionClaw offered could not be started.
			ui.message(_("The help could not be started. Ask VisionClaw in words instead, with NVDA+Alt+C."))

	def _help(self, kind, facts):
		debuglog.log("offer", f"The user took the help offered for {kind}.")
		self._keepOnPad(kind, facts)
		if kind == troubles.UNLABELLED:
			# A name from its picture, asked of the model that sees, as NVDA+Shift+Alt+B asks for it.
			self.plugin.script_nameByModel(None)
			return
		request = troubles.requestFor(kind, facts)
		if request:
			self.plugin.startClawTask(request, _conf()["reasoning"])

	def _keepOnPad(self, kind, facts):
		"""What was noticed, on the learning scratchpad of the program, where the user lets VisionClaw keep scratchpads.
		Plain code writes it; a fault here is no fault."""
		pads = getattr(self.plugin, "pads", None)
		app = facts.get("app") or ""
		if pads is None or not app:
			return
		try:
			if not _conf()["scratchpads"]:
				return
			from .claw import scratchpad
			where = f"The window \"{facts['title']}\"" if facts.get("title") else "A window"
			said = {troubles.UNREADABLE: "tells NVDA almost nothing; VisionClaw reads it from its picture",
				troubles.NO_FOCUS: "opens with nothing in it focused",
				troubles.UNLABELLED: f"has a {facts.get('focusRoleText') or 'control'} without a name",
				troubles.LOG_ERRORS: "made NVDA log errors"}.get(kind, "")
			if said:
				pads.learn(app, f"{where} {said}.", scratchpad.BY_VISIONCLAW, "noticed by VisionClaw")
		except Exception as e:
			debuglog.error("offer", "What was noticed could not be written on the scratchpad", e)
