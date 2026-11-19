# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - choosing a date in a calendar that cannot be worked with the keyboard (claw/dates.py). The tool
# pick_date reads the date from the user's own words, finds the calendar that is showing, gets it to the right
# month with the calendar's own buttons, presses the day, and says what happened.
# The calendar is looked for in three places, the surest first:
#   1. the web page the user is in, from what NVDA keeps of it in browse mode: every control's name;
#   2. the window in front, from what NVDA knows of its controls;
#   3. the window's picture, from the text in it: for a calendar that is only drawn.
# In the first two the calendar's buttons are pressed the way NVDA presses them; in the third the mouse clicks
# the place, and is put back where it was. After every press the calendar is read again.

import datetime
import time

import addonHandler
import api
import config

from . import fixruntime, mousetools, ocr
from .claw import dates
from .claw.fixmatch import labelOf
from .claw.tools import ToolError
from .vclog import log

addonHandler.initTranslation()

# How long a calendar is given to show another month after its button was pressed.
SETTLE_SECONDS = 0.4
# After a question, how long the calendar's window is given to be in front again.
BACK_SECONDS = 3.0
MARKED = ("SELECTED", "PRESSED", "CHECKED")
MAX_CONTROLS = 4000


def _controls(nodes):
	"""The controls of a page or window as claw/dates.py takes them."""
	found = []
	for node in nodes[:MAX_CONTROLS]:
		if node.get("hidden") or "INVISIBLE" in (node.get("states") or ()):
			continue
		label = labelOf(node) or node.get("value") or ""
		if not label:
			continue
		states = node.get("states") or ()
		found.append({
			"label": label, "ref": node, "usable": "UNAVAILABLE" not in states,
			"marked": any(state in states for state in MARKED), "inside": node.get("up")})
	return found


def _page():
	"""The web page the user is in, or None. Main thread."""
	from . import pagetools
	found = pagetools._where()
	return found[0] if found else None


def _windowNodes():
	"""The controls of the window in front, as NVDA knows them. Main thread."""
	return list(fixruntime.windowNodes(api.getForegroundObject()))


def _pressOnPage(document, node):
	fixruntime.locate(document, node)
	fixruntime.activateOnPage(document, node)


class Reader:
	"""Reads the calendar that is showing, and presses its buttons, in the one of the three places where a
	calendar was found first."""

	def __init__(self, task, plugin, onMain, screen):
		self.task, self.plugin, self.onMain, self.screen = task, plugin, onMain, screen
		self.place = None  # "page", "window" or "picture", once a calendar was found
		self._document = None
		self._box = None
		self._mouse = None

	def _fromPage(self):
		from . import pagetools
		document = self.onMain(_page)
		if document is None:
			return None
		self._document = document
		return dates.fromControls(_controls(pagetools.pageNodes(self.task, document, self.onMain)))

	def _fromWindow(self):
		return dates.fromControls(_controls(self.onMain(_windowNodes)))

	def _fromPicture(self):
		from . import imaging
		image, box = self.screen.picture("window")
		lines = ocr.recognize(image) or []
		words = [word for line in lines for word in line]
		icons = []
		if words:
			try:
				scale = mousetools.scaleAt((box[0] + box[2]) // 2, (box[1] + box[3]) // 2) if box else 1.0
				icons = imaging.findIcons(image, [(w["x"], w["y"], w["width"], w["height"]) for w in words], scale)
			except Exception:
				log.debugWarning("VisionClaw: the shapes beside the calendar's heading could not be looked for", exc_info=True)
		self._box = box
		view = dates.fromWords(lines, icons)
		return view

	def read(self):
		"""The calendar as it shows now, or None."""
		self.task.check()
		readers = {"page": self._fromPage, "window": self._fromWindow, "picture": self._fromPicture}
		if self.place is not None:
			try:
				return readers[self.place]()
			except ToolError:
				raise
			except Exception:
				log.debugWarning("VisionClaw: the calendar could not be read again", exc_info=True)
				return None
		for place in ("page", "window", "picture"):
			if place == "picture" and not config.conf["visionClaw"]["useOcr"]:
				continue
			try:
				view = readers[place]()
			except ToolError:
				raise
			except Exception:
				log.debugWarning(f"VisionClaw: no calendar could be looked for in the {place}", exc_info=True)
				continue
			if view is not None and view.isCalendar():
				self.place = place
				return view
		return None

	def press(self, ref):
		self.task.check()
		if self.place == "page":
			self.onMain(_pressOnPage, self._document, ref)
		elif self.place == "window":
			self.onMain(fixruntime.pressObject, ref["obj"])
		else:
			if self._mouse is None:
				self._mouse = mousetools.position()
			left, top = (self._box[0], self._box[1]) if self._box else (0, 0)
			mousetools.click(round(left + ref[0]), round(top + ref[1]))

	def pause(self):
		time.sleep(SETTLE_SECONDS)

	def finish(self):
		"""Put the mouse back where it was, if it was used."""
		if self._mouse is not None:
			try:
				mousetools.moveTo(*self._mouse)
			except Exception:
				pass
			self._mouse = None


def afterText(reader, date):
	"""What the calendar shows after the day was pressed, in a sentence; "" when that says nothing."""
	try:
		reader.pause()
		view = reader.read()
	except Exception:
		return ""
	if view is None or not view.isCalendar():
		return " The calendar is gone now, as most are once a day is chosen."
	cell = dates.dayCell(view, date)
	if cell is not None and cell.marked:
		return " The calendar marks that day as chosen."
	if reader.place == "picture":
		return ""
	return " The calendar is still showing and does not say which day is chosen, so check the date field."


def register(add, plugin, text, onMain, confirm, screen):
	"""Add the tool. add, text and confirm are nvdatools' own; onMain runs a function on NVDA's main thread."""

	def pickDate(task, asked):
		wish = dates.wish(asked or task.request, datetime.date.today())
		if wish is None:
			found = dates.parse(asked or task.request, datetime.date.today())
			if not found:
				raise ToolError(
					"The request names no date. Say the date with its day and month, and the year where it is not this one.")
			wish = {"dates": found, "said": asked or task.request}
		choices = wish["dates"]
		date = choices[0]
		if len(choices) > 1:
			question, labels = dates.ambiguous(choices)
			chosen = plugin.clawAsk(question, labels)
			if chosen is None or not 0 <= chosen < len(choices):
				return "You did not say which date, so nothing was pressed."
			date = choices[chosen]
		reader = Reader(task, plugin, onMain, screen)
		view = reader.read()
		if view is None:
			return dates.NO_CALENDAR
		where = {
			"page": "on this web page", "window": "in this window", "picture": "in this window, read from its picture"}[reader.place]
		shows = f" It shows {dates.monthSaid(view.shown)}." if view.shown else ""
		# Translators: Asked before VisionClaw presses the buttons of a calendar. {date} is the date, {where} where the calendar is.
		confirm(_("Choose {date} in the calendar {where}?{shows} VisionClaw will press the calendar's own buttons.").format(
			date=dates.said(date), where=where, shows=shows))
		# The question was a window of NVDA: the calendar is read again once its window is in front again.
		deadline = time.monotonic() + BACK_SECONDS
		while time.monotonic() < deadline:
			again = reader.read()
			if again is not None and again.isCalendar():
				break
			task.check()
			time.sleep(0.2)
		try:
			done, said, _moved = dates.choose(reader.read, reader.press, date, reader.pause, task.check)
			if done:
				said += afterText(reader, date)
		finally:
			reader.finish()
		return said

	add("pick_date",
		"choose a date in a calendar or date picker that is showing in the web page or window in front, by pressing its "
		"buttons for the month and the day; for a calendar that cannot be worked with the keyboard",
		pickDate, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Choosing the date in the calendar")
