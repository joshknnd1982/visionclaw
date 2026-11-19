# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tool for a form that is only a picture: a scanned or flattened PDF, where NVDA finds no fields.
# "Click the blank line next to Applicant Full Name and type my name", "click the dotted line labelled Authorized
# Signature at the bottom so I can sign". What is asked is read from the user's own words (claw/paper.py); the
# label is found in the text read from the window's picture, and its line or check box in the pixels
# (claw/spots.py); a model is asked nothing. Then, after a question, the place is clicked with the mouse and the
# text is typed, the picture is read again, and the user is told what was done and whether the text shows there.
# What is typed is the user's own: given in the request, taken word for word from what they asked VisionClaw to
# remember, or asked for. VisionClaw never signs.
# The program must already be ready to take the click: in Adobe Acrobat, the Fill & Sign tool chosen first.

import datetime
import time

import addonHandler
import config

from . import mousetools, ocr
from .claw import dragcontrol, paper, spots
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()

# How long the program is given to take a click, and to show what was typed.
SETTLE_SECONDS = 0.5


def _own(plugin, what):
	"""One of the user's own facts to type: from what they asked VisionClaw to remember, or asked for now."""
	if what == paper.DATE:
		now = datetime.date.today()
		return paper.today(now.year, now.month, now.day)
	bodies = []
	try:
		bodies = [entry.body for entry in plugin.memories.all()]
	except Exception:
		bodies = []
	known = paper.remembered(what, bodies)
	if known:
		return known
	answer = plugin.clawAskText(paper.ownQuestion(what))
	return (answer or "").strip() or None


def _shows(image, rule, tall, typed):
	"""Whether what was typed is read in the picture at the line: True, False, or None when nothing could be read."""
	left, top, right, bottom = rule["box"]
	area = (max(0, left - tall), max(0, top - 3 * tall), min(image.size[0], right + tall), min(image.size[1], bottom + tall))
	lines = ocr.recognize(image.crop(area))
	if lines is None:
		return None
	if spots.phrase(lines, typed):
		return True
	read = " ".join(word.get("text", "") for line in lines for word in line).lower()
	wanted = [word for word in typed.lower().split() if len(word) >= 3]
	return bool(wanted) and all(word in read for word in wanted)


def register(add, plugin, text, onMain, confirm, mustAgree, screen):
	def fillBlank(task, asked):
		from . import nvdatools
		wished = paper.wish(asked or task.request)
		if wished is None:
			raise ToolError(paper.NO_WISH)
		if not config.conf["visionClaw"]["useOcr"]:
			return (
				"Nothing was clicked: reading text in pictures is turned off in VisionClaw's settings, and the labels of "
				"a form that is only a picture are found by reading them.")
		image, box = screen.picture("window")
		task.check()
		lines = ocr.recognize(image)
		task.check()
		places = spots.phrase(lines, wished["label"])
		if not places:
			return paper.notFound(wished, bool(lines))
		index = paper.choose(places, wished["which"])
		if index is None:
			index = plugin.clawAsk(paper.whichQuestion(wished["label"], len(places)), paper.placeChoices(places, image.size))
			if index is None:
				raise nvdatools.UserSaidNo()
		label = places[index]
		tall = max(6, label[3] - label[1])
		left, top = (box[0], box[1]) if box else (0, 0)
		scale = onMain(mousetools.scaleAt, left + label[0], top + label[1])
		ticked = written = None
		dotted = False
		if wished["kind"] == paper.BOX:
			square = spots.squareFor(label, spots.squares(image, scale))
			if square is None:
				return paper.noBlank(wished)
			point, how, area, ticked = spots.middleOf(square["box"]), spots.NEXT, square["box"], square["ticked"]
			rule = None
		else:
			found = spots.blankFor(label, spots.rules(image, scale), wished["side"])
			if found is None:
				return paper.noBlank(wished)
			rule, how = found
			dotted = rule["dotted"]
			point = spots.writePoint(rule, tall)
			written = spots.written(image, rule, tall, label if how == spots.UNDER else None)
			area = (rule["box"][0], rule["box"][1] - 2 * tall, rule["box"][2], rule["box"][3] + tall)
		typed = wished["typed"]
		if wished["own"]:
			typed = _own(plugin, wished["own"])
			if not typed:
				return "Nothing was clicked: " + paper.NOT_TYPED[0].lower() + paper.NOT_TYPED[1:]
		task.check()
		confirm(paper.question(wished, how, typed, dotted, written, ticked))
		spot = (round(left + point[0]), round(top + point[1]))
		old = mousetools.position()
		shows = changed = None
		try:
			mousetools.click(*spot)
			time.sleep(SETTLE_SECONDS)
			task.check()
			if typed:
				onMain(nvdatools.typeUnicode, typed)
				time.sleep(SETTLE_SECONDS)
		finally:
			mousetools.moveTo(*old)
		task.items = None  # the window has changed
		after = None
		try:
			after = plugin._grab(box)
		except Exception:
			after = None
		if after is not None and after.size == image.size:
			if typed and rule is not None:
				shows = _shows(after, rule, tall, typed)
			else:
				changed = dragcontrol.changed(image.crop(area), after.crop(area)) >= dragcontrol.CHANGED
		return paper.done(wished, how, typed, dotted, shows, changed)

	add("fill_blank",
		"on a form that is only a picture, such as a scanned or flattened PDF: click the printed line or check box "
		"that belongs to a label, and type the user's text on it",
		fillBlank, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Finding the place on the form", tell=VERBATIM)
