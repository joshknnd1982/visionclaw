# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - accessibility trouble noticed where the user is, and help offered, which the user may always refuse. The
# owner said on 2026-11-19: "visionclaw must have an option in settings, along with auto-skills and system prompts along
# with using scratchpads and nvda logs, that trigger and offer to help the user with inaccessible windows, apps,
# controls, dialogs, windows, websites, controls on websites and so on. and the user can always refuse such help.
# although it is automatic, user has final say." What follows from it:
#   - Plain code notices the trouble from NVDA's facts (detect): a window that tells NVDA almost nothing, a dialog where
#     nothing has the focus, a focused control without a label (naming.wanted), and errors NVDA logged in the program
#     just now (claw/nvdalog.py). A model decides nothing here.
#   - Help is offered in one sentence, never done: the user presses NVDA+Alt+Y to take it, or does nothing. Pressed twice,
#     no more offers are made in that program, which is kept as data (Offers, helpoffers.json); pressed once when nothing
#     is offered, offers there are allowed again. The setting "offerHelp" turns all of it off.
#   - Taken, the help is a request in plain words (requestFor), carried out like any other, with its skills, scratchpads
#     and NVDA's log, and asked about before anything is changed.
#   - Never too often: once for a place and a kind of trouble while NVDA runs, never sooner than QUIET_SECONDS after the
#     last offer, never while VisionClaw works, listens or reads, never in VisionClaw's own windows, never in a program the
#     user is already having made accessible, and never for a control without a name while object names are on, which
#     name it by themselves.
# No NVDA dependencies (helpoffer.py does the noticing in NVDA).

import json
import os
import time

from . import landing, naming

UNREADABLE, NO_FOCUS, UNLABELLED, LOG_ERRORS = "unreadable", "nofocus", "unlabelled", "logerrors"
KINDS = (UNREADABLE, NO_FOCUS, UNLABELLED, LOG_ERRORS)
FILE = "helpoffers.json"
# How long the user stays somewhere before it is looked at, in milliseconds: passing through is no trouble.
SETTLE_MS = 1500
# At least this long between two offers, in seconds.
QUIET_SECONDS = 45
# How long an offer can be taken with the key, in seconds.
TAKE_SECONDS = 120
# How many errors NVDA logged in the program in the last minute before it is offered.
LOG_ERRORS_AT = 2
# How long NVDA's log is looked back at, in seconds.
LOG_SECONDS = 60
KEY = "NVDA+Alt+Y"


def detect(facts, namesOn=False, errors=0, followed=False):
	"""The trouble where the user is, or None. facts: gototools.spot(); namesOn: whether object names are on (they name a
	control without a label by themselves); errors: how many errors NVDA logged in this program just now; followed:
	whether the user is already having this program made accessible (appaccesstools.isFollowed)."""
	if not facts or facts.get("own") or followed:
		return None
	role, name = facts.get("focusRole") or "", facts.get("focusName") or ""
	named, controls = facts.get("named"), facts.get("controls")
	nowhere = landing.nowhere(facts)
	if nowhere and named is not None and named < landing.FEW_NAMED:
		return UNREADABLE
	# A dialog whose focus is the dialog itself, or a pane of it, while it has controls: nothing in it has the focus.
	if (nowhere or role == "DIALOG") and facts.get("windowRole") == "DIALOG" and (controls or 0) > 0:
		return NO_FOCUS
	if (not namesOn and facts.get("browse") is not True
			and naming.wanted(role, facts.get("focusStates") or (), name, others=(facts.get("focusDescription") or "",))):
		return UNLABELLED
	if errors >= LOG_ERRORS_AT:
		return LOG_ERRORS
	return None


def offerText(kind, facts, errors=0):
	"""The one sentence that offers help, with the key that takes it and the way to stop the offers."""
	app = facts.get("app") or "this program"
	what = facts.get("focusRoleText") or "control"
	said = {
		UNREADABLE: "This window tells NVDA almost nothing.",
		NO_FOCUS: "Nothing in this dialog has the focus.",
		UNLABELLED: f"This {what} has no name NVDA can say.",
		LOG_ERRORS: f"NVDA logged {errors} errors in {app} just now.",
	}[kind]
	help = {
		UNREADABLE: "VisionClaw can read it from its picture and put you on the most useful item",
		NO_FOCUS: "VisionClaw can put you on the most useful control",
		UNLABELLED: "VisionClaw can name it from its picture",
		LOG_ERRORS: "VisionClaw can say what went wrong",
	}[kind]
	return f"{said} {help}: press {KEY}. Ignore this to say no; press {KEY} twice for no more offers in {app}."


def requestFor(kind, facts):
	"""The words carried out when the user takes the help: a request like any other, or "" where the help is no request
	(a name for the control, which the add-on asks the model that sees for)."""
	return {
		UNREADABLE: "This window tells NVDA almost nothing: put me on the most useful item in it.",
		NO_FOCUS: "Nothing in this dialog has the focus: put me on the most useful control in this dialog.",
		LOG_ERRORS: "NVDA logged errors in this program just now: check NVDA's log and tell me what went wrong.",
	}.get(kind, "")


def placeOf(facts):
	"""What an offer is made once for: the program, the window and, for a control, the control."""
	return (str(facts.get("app") or "").lower(), facts.get("title") or "", facts.get("focusRole") or "")


class Offers:
	"""What was offered while NVDA runs, the offer that can be taken now, and the programs where the user wants no
	offers, kept in a file of VisionClaw's data. Plain data; never a fault."""

	def __init__(self, path=None, clock=time.monotonic):
		self.path, self.clock = path, clock
		self.made = set()
		self.last = None
		self.pending = None
		self.declined = set()
		try:
			if path and os.path.isfile(path):
				with open(path, encoding="utf-8") as file:
					self.declined = {str(app).lower() for app in json.load(file).get("declined", [])}
		except Exception:
			self.declined = set()

	def _write(self):
		if not self.path:
			return
		try:
			with open(self.path, "w", encoding="utf-8") as file:
				json.dump({"declined": sorted(self.declined)}, file, indent=1)
		except Exception:
			pass

	def due(self, kind, facts):
		"""Whether this trouble may be offered now."""
		app = str(facts.get("app") or "").lower()
		if not kind or not app or app in self.declined or (kind, placeOf(facts)) in self.made:
			return False
		return self.last is None or self.clock() - self.last >= QUIET_SECONDS

	def offered(self, kind, facts):
		"""An offer was made: it can be taken for TAKE_SECONDS, and is not made again for this place."""
		self.made.add((kind, placeOf(facts)))
		self.last = self.clock()
		self.pending = (kind, dict(facts), self.last)

	def take(self):
		"""The offer the user takes now, as (kind, facts), or None when there is none or it is too old. Taken once."""
		pending, self.pending = self.pending, None
		if pending is None or self.clock() - pending[2] > TAKE_SECONDS:
			return None
		return pending[0], pending[1]

	def decline(self, app):
		"""No more offers in a program, until the user allows them again."""
		app = str(app or "").lower()
		self.pending = None
		if app:
			self.declined.add(app)
			self._write()

	def allow(self, app):
		"""Offers in a program again. Returns whether they had been stopped there."""
		app = str(app or "").lower()
		if app not in self.declined:
			return False
		self.declined.discard(app)
		self._write()
		return True


def declinedText(app):
	return f"No more offers of help in {app or 'this program'}. Press {KEY} there to have them again."


def allowedText(app):
	return f"Offers of help are back on in {app or 'this program'}."


def nothingText(app):
	return (f"VisionClaw has nothing to offer here now: NVDA can read where you are. Ask VisionClaw if something here does "
		"not work for you.")
