# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools for shopping and booking on a web page or in a program:
#   pick_option   chooses an option of a product (a size, a colour, a storage size) by its name or, for a swatch
#                 with no name, by its colour as measured from the pixels; and says whether an option is chosen,
#                 from what the page itself tells NVDA (claw/shopping.py);
#   pick_seat     reads a seat map, says which free seats fit what was asked, and after a question presses one
#                 (claw/seats.py);
#   guardPurchase is called by other tools before a button is pressed: where the button buys, books or pays, the
#                 total is read from the page word for word and the user is always asked.
# Options and seats are looked for in three places, the surest first, as a calendar is (datetools.py):
#   1. the web page the user is in, from what NVDA keeps of it in browse mode: every control's name and state;
#   2. the window in front, from what NVDA knows of its controls;
#   3. the window's picture: blocks of one colour in a row for swatches, the numbers and colours of seats for a map.
# In the first two a thing is pressed the way NVDA presses it; in the third the mouse clicks the place and is put
# back where it was. After a press the page is read again, and the answer says what it shows now: a click alone
# is never called chosen. No model is asked anywhere here.

import time

import addonHandler
import api
import config

from . import deepquery, fixruntime, mousetools, ocr
from .claw import colours, dragcontrol, seats, shopping, spots
from .claw.fixmatch import labelOf
from .claw.scrolling import pixels
from .claw.tools import VERBATIM, ToolError
from .vclog import log

addonHandler.initTranslation()

# How long a page is given to show that an option or a seat was taken.
SETTLE_SECONDS = 0.5
PAGE, WINDOW, PICTURE = "page", "window", "picture"
MAX_CONTROLS = 4000
# At most this many controls with no name are measured for their colour, and at most this many swatches are
# taken from a picture.
MAX_MEASURED, MAX_SWATCHES = 60, 24
# A swatch is no larger than this on a plain screen at 100 percent.
SWATCH_SIDE = 120
MARKED = ("SELECTED", "PRESSED", "CHECKED")
# The most text of a page that is looked through for what is to be paid.
PAGE_CHARS = 200000


def _page():
	"""The web page the user is in, or None. Main thread."""
	from . import pagetools
	found = pagetools._where()
	return found[0] if found else None


def _windowNodes():
	"""The controls of the window in front, as NVDA knows them. Main thread."""
	return list(fixruntime.windowNodes(api.getForegroundObject()))


def _nodes(task, onMain, place):
	"""The controls of one place as plain data, with the page they are in: (nodes, document), or (None, None)
	when the user is not in such a place."""
	if place == PAGE:
		from . import pagetools
		document = onMain(_page)
		if document is None:
			return None, None
		return pagetools.pageNodes(task, document, onMain), document
	return onMain(_windowNodes), None


def _shown(node):
	states = node.get("states") or ()
	return not node.get("hidden") and "INVISIBLE" not in states


def _groupOf(node):
	"""The name of what a control is inside: the nearest thing around it that has a name, at most three up."""
	up = node.get("up")
	for _level in range(3):
		if up is None:
			break
		if up.get("name"):
			return up["name"]
		up = up.get("up")
	return ""


def _optionControls(nodes):
	"""The controls of a page or window as claw/shopping.py takes them."""
	return [{
		"label": labelOf(node) or node.get("value") or "", "role": node.get("role") or "", "states": list(node.get("states") or ()),
		# What a combo box shows: its value in a window; on a page, the text inside it where it also has a name.
		"value": node.get("value") or (node.get("text") if node.get("name") else "") or "",
		"group": _groupOf(node), "colour": None, "ref": node} for node in nodes[:MAX_CONTROLS] if _shown(node)]


def _seatControls(nodes):
	"""The controls of a page or window as claw/seats.py takes them."""
	found = []
	for node in nodes[:MAX_CONTROLS]:
		if not _shown(node):
			continue
		label = labelOf(node) or node.get("value") or ""
		if not label:
			continue
		states = node.get("states") or ()
		found.append({
			"label": label, "ref": node, "usable": "UNAVAILABLE" not in states, "marked": any(state in states for state in MARKED)})
	return found


def _boxesOf(document, nodes):
	"""Where each control is on the screen, (left, top, right, bottom), or None. Main thread."""
	found = []
	for node in nodes:
		try:
			if document is not None:
				key = node.get("key")
				obj = document.getNVDAObjectFromIdentifier(int(key[0]), int(key[1])) if key else None
			else:
				obj = node.get("obj")
			found.append(deepquery.boxOf(obj) if obj is not None else None)
		except Exception:
			found.append(None)
	return found


def _pressNode(document, node):
	"""Press a control the way NVDA presses it: on a page as Enter does in browse mode, in a window with the
	control's own action. Main thread."""
	if document is not None:
		fixruntime.locate(document, node)
		fixruntime.activateOnPage(document, node)
	else:
		fixruntime.pressObject(node["obj"])


def _picture(screen):
	"""The picture of the window in front and where it is on the screen: (PIL image, (left, top, right, bottom))."""
	return screen.picture("window")


def _read(image):
	"""The text in a picture, as ocr.py's lines of words; [] when it cannot be read or reading is turned off."""
	if not config.conf["visionClaw"]["useOcr"]:
		return []
	return ocr.recognize(image) or []


def _inside(box, frame):
	return box is not None and frame is not None and box[0] >= frame[0] and box[1] >= frame[1] and box[2] <= frame[2] and box[3] <= frame[3]


def _measure(task, onMain, screen, document, controls):
	"""Measure the colour of the controls that may be swatches with no colour in their name, from the window's
	picture, and write it into each as a plain name; each also gets its place on the screen as "box". Where some
	of them stand in a row as swatches do, only those are measured."""
	wanted = sorted((control for control in controls if shopping.needsColour(control)), key=shopping.measureFirst)[:MAX_MEASURED]
	if not wanted:
		return None
	image, frame = _picture(screen)
	task.check()
	if frame is None:
		return image
	boxes = onMain(_boxesOf, document, [control["ref"] for control in wanted])
	scale = onMain(mousetools.scaleAt, (frame[0] + frame[2]) // 2, (frame[1] + frame[3]) // 2)
	largest = pixels(SWATCH_SIDE, scale)
	fitting = [index for index, box in enumerate(boxes)
		if _inside(box, frame) and max(box[2] - box[0], box[3] - box[1]) <= largest
		and max(box[2] - box[0], box[3] - box[1]) <= 3 * min(box[2] - box[0], box[3] - box[1])]
	rows = shopping.swatchRows([boxes[index] for index in fitting])
	if rows:
		fitting = [fitting[index] for row in rows for index in row]
	for index in fitting:
		box = boxes[index]
		measured = colours.middle(image, (box[0] - frame[0], box[1] - frame[1], box[2] - frame[0], box[3] - frame[1]))
		if measured is not None:
			wanted[index]["colour"] = colours.name(measured)
			wanted[index]["box"] = box
	return image


def _fromPicture(task, onMain, screen, wish):
	"""Options found only in the window's picture: the words of the option's name where they are read, and small
	blocks of one colour in a row for a colour. Each has the place to click as its ref."""
	image, frame = _picture(screen)
	task.check()
	left, top = (frame[0], frame[1]) if frame else (0, 0)
	found = []
	if wish.get("name"):
		for box in spots.phrase(_read(image), wish["name"]):
			x, y = spots.middleOf(box)
			found.append({
				"label": wish["name"], "colour": None, "measured": False, "chosen": None, "usable": True, "role": "", "group": "",
				"ref": (left + x, top + y), "box": (left + box[0], top + box[1], left + box[2], top + box[3]),
				"where": "read in the window's picture"})
	if wish.get("colour") and not found:
		scale = onMain(mousetools.scaleAt, (frame[0] + frame[2]) // 2, (frame[1] + frame[3]) // 2) if frame else 1.0
		blocks = shopping.blocks(image, scale)
		for row in shopping.swatchRows(blocks):
			for index in row:
				box = blocks[index]
				measured = colours.middle(image, box)
				if measured is None or len(found) >= MAX_SWATCHES:
					continue
				x, y = spots.middleOf(box)
				found.append({
					"label": "", "colour": colours.name(measured), "measured": True, "chosen": None, "usable": True, "role": "",
					"group": "", "ref": (left + x, top + y), "box": (left + box[0], top + box[1], left + box[2], top + box[3]),
					"where": "found in the window's picture"})
	return found, image


def _signature(control):
	return (control.get("label") or "", control.get("role") or "", control.get("group") or "")


def _stateAgain(task, onMain, place, option, nth):
	"""Whether the page marks an option as chosen when it is read again: True, False, or None when the page does
	not say or the option is not found again. nth: which of the controls with its name, kind and group it was."""
	try:
		nodes, _document = _nodes(task, onMain, place)
	except Exception:
		log.debugWarning("VisionClaw: the options could not be read again", exc_info=True)
		return None
	if not nodes:
		return None
	same = [control for control in _optionControls(nodes) if _signature(control) == _signature(option)]
	if nth >= len(same):
		return None
	again = same[nth]
	return shopping.chosenOf(again["role"], again["states"], again["label"])


def _pageLines(plugin, onMain):
	"""The text of the page or window the user is in, as lines, for finding what is to be paid."""
	from . import webtools

	def whole():
		import textInfos
		document = webtools.page()
		if document is None:
			return None
		return (document.makeTextInfo(textInfos.POSITION_ALL).text or "")[:PAGE_CHARS]
	text = onMain(whole)
	if text:
		return text.splitlines()
	if not config.conf["visionClaw"]["useOcr"]:
		return []
	image, _frame = _picture(plugin.clawScreen)
	return ocr.rowsText(ocr.recognize(image)).splitlines()


def guardPurchase(plugin, onMain, name):
	"""Before a button is pressed: where its name buys, books, pays or orders (claw/shopping.py), what is to be
	paid is read from the page word for word and the user is asked, always, whatever the settings say. Returns
	True to go on, False when the user said no. A page that cannot be read is no fault: the question then says
	that no total was found."""
	if not shopping.isPurchase(name):
		return True
	lines = []
	try:
		lines = _pageLines(plugin, onMain) or []
	except Exception:
		log.debugWarning("VisionClaw: the page could not be read for what is to be paid", exc_info=True)
	found = shopping.totals(lines)
	log.info(f"VisionClaw: asking before \"{name}\" is pressed; {len(found)} lines say what is to be paid")
	answer = plugin.clawAsk(shopping.purchaseQuestion(name, found), [
		# Translators: A choice when VisionClaw asks before pressing a button that buys, books or pays.
		_("Yes, press it"),
		# Translators: A choice when VisionClaw asks before pressing a button that buys, books or pays.
		_("No, do not press it")])
	return answer == 0


class SeatReader:
	"""Reads the seat map that is showing, and presses a seat, in the one of the three places where a map was
	found first."""

	def __init__(self, task, onMain, screen):
		self.task, self.onMain, self.screen = task, onMain, screen
		self.place = None
		self._document = None
		self._frame = None
		self._mouse = None

	def _from(self, place):
		if place == PICTURE:
			image, frame = _picture(self.screen)
			self._frame = frame
			return seats.fromPicture(_read(image), lambda box: colours.middle(image, box))
		nodes, document = _nodes(self.task, self.onMain, place)
		if not nodes:
			return None
		self._document = document
		return seats.fromNames(_seatControls(nodes))

	def read(self):
		"""The seat map as it shows now, or None."""
		self.task.check()
		places = (self.place,) if self.place is not None else (PAGE, WINDOW, PICTURE)
		for place in places:
			if place == PICTURE and not config.conf["visionClaw"]["useOcr"]:
				continue
			try:
				found = self._from(place)
			except ToolError:
				raise
			except Exception:
				log.debugWarning(f"VisionClaw: no seat map could be looked for in the {place}", exc_info=True)
				continue
			if found is not None and found.isMap():
				self.place = place
				return found
		return None

	def press(self, seat):
		self.task.check()
		if self.place == PICTURE:
			if self._mouse is None:
				self._mouse = mousetools.position()
			left, top = (self._frame[0], self._frame[1]) if self._frame else (0, 0)
			mousetools.click(round(left + seat.ref[0]), round(top + seat.ref[1]))
		else:
			self.onMain(_pressNode, self._document, seat.ref)

	def finish(self):
		"""Put the mouse back where it was, if it was used."""
		if self._mouse is not None:
			try:
				mousetools.moveTo(*self._mouse)
			except Exception:
				pass
			self._mouse = None


def register(add, plugin, text, onMain, confirm, mustAgree, screen):
	"""Add the tools. add, text, confirm and mustAgree are nvdatools' own; onMain runs a function on NVDA's main
	thread; screen is nvdatools.Screen."""

	def gather(task, wish):
		"""The options the wish may be about, from the surest place that has any: (options, place, document, what
		to say when there are none because the page uses a combo box)."""
		combo = ""
		for place in (PAGE, WINDOW):
			try:
				nodes, document = _nodes(task, onMain, place)
			except ToolError:
				raise
			except Exception:
				log.debugWarning(f"VisionClaw: no options could be looked for in the {place}", exc_info=True)
				continue
			if not nodes:
				continue
			controls = _optionControls(nodes)
			if wish.get("colour"):
				try:
					_measure(task, onMain, screen, document, controls)
				except ToolError:
					raise
				except Exception:
					log.debugWarning("VisionClaw: the colours of the options could not be measured", exc_info=True)
			options = shopping.asOptions(controls, wish)
			combo = combo or shopping.comboText(wish, controls)
			# Each option remembers which of the controls with its name, kind and group it is, to find it again.
			seen = {}
			for control in controls:
				signature = _signature(control)
				for option in options:
					if option["ref"] is control["ref"]:
						option["nth"] = seen.get(signature, 0)
						option["box"] = control.get("box")
				seen[signature] = seen.get(signature, 0) + 1
			if options:
				return options, place, document, combo
		if combo:
			# The page has a combo box for this: its picture would only show the one that is chosen.
			return [], None, None, combo
		if config.conf["visionClaw"]["useOcr"] and (wish.get("name") or wish.get("colour")):
			try:
				options, _image = _fromPicture(task, onMain, screen, wish)
			except ToolError:
				raise
			except Exception:
				log.debugWarning("VisionClaw: no options could be looked for in the window's picture", exc_info=True)
				options = []
			if options:
				return options, PICTURE, None, ""
		return [], None, None, ""

	def pickOption(task, asked):
		wish = shopping.optionWish(asked or task.request)
		if wish is None:
			raise ToolError(shopping.NO_WISH)
		options, place, document, combo = gather(task, wish)
		task.check()
		# A combo box for what was asked counts for more than a link or button that only has the name in it.
		if combo and (not options or (wish.get("name") and not wish.get("colour") and not shopping.namedExactly(wish, options))):
			return combo
		if wish["what"] == shopping.CHECK:
			# Only told; nothing is pressed.
			return shopping.checkText(wish, options)
		index, how = shopping.pickOption(wish, options)
		if index is None:
			if not how:
				return shopping.noFit(wish, options)
			chosen = plugin.clawAsk(shopping.whichQuestion(wish), shopping.choices(options, how) + [
				# Translators: The last choice when VisionClaw asks which of several options of a product is meant.
				_("None of these")])
			if chosen is None or not 0 <= chosen < len(how):
				return "You did not say which option, so nothing was pressed."
			index = how[chosen]
		option = options[index]
		if not option.get("usable", True):
			return shopping.unusableText(option)
		number = index + 1
		confirm(shopping.chooseQuestion(option, number))
		box = option.get("box")
		if box is None and place != PICTURE:
			# Where the option is on the screen, to see afterwards whether its picture changed.
			try:
				box = onMain(_boxesOf, document, [option["ref"]])[0]
			except Exception:
				box = None
		before = None
		if box is not None:
			try:
				before = plugin._grab(_around(box))
			except Exception:
				before = None
		if place == PICTURE:
			old = mousetools.position()
			try:
				mousetools.click(round(option["ref"][0]), round(option["ref"][1]))
				time.sleep(SETTLE_SECONDS)
			finally:
				mousetools.moveTo(*old)
		else:
			onMain(_pressNode, document, option["ref"])
			time.sleep(SETTLE_SECONDS)
		task.check()
		task.items = None  # the page has probably changed
		after = None if place == PICTURE else _stateAgain(task, onMain, place, option, option.get("nth", 0))
		changed = None
		if after is None and before is not None:
			try:
				changed = dragcontrol.changed(before, plugin._grab(_around(box))) >= dragcontrol.CHANGED
			except Exception:
				changed = None
		return shopping.doneText(option, after, changed, number)

	def _around(box):
		"""A control's place on the screen with a little around it, where a ring is drawn around a chosen option."""
		grow = max(4, (box[3] - box[1]) // 3)
		return (box[0] - grow, box[1] - grow, box[2] + grow, box[3] + grow)

	add("pick_option",
		"choose an option of a product on a shopping page, such as a size, a colour or a storage size, by its name or "
		"by its colour; or say whether an option is the one chosen",
		pickOption, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Choosing the option", tell=VERBATIM)

	def pickSeat(task, asked):
		wish = seats.seatWish(asked or task.request)
		if wish is None:
			raise ToolError(seats.NO_WISH)
		reader = SeatReader(task, onMain, screen)
		seatMap = reader.read()
		if seatMap is None:
			return seats.NO_MAP
		found, notes = seats.choose(seatMap, wish)
		said = seats.told(seatMap, wish, found, notes)
		if not wish["act"] or not found:
			return said
		# Choosing a seat may cost money, so it is always asked about, whatever the settings say.
		question, choices = seats.question(found)
		answer = plugin.clawAsk(question, choices)
		if answer is None or not 0 <= answer < len(found):
			return said + " You did not choose one, so nothing was pressed."
		seat = found[answer]
		try:
			reader.press(seat)
			time.sleep(SETTLE_SECONDS)
			task.check()
			after = None
			try:
				again = reader.read()
				after = again.seats.get(seat.id) if again is not None else None
			except ToolError:
				raise
			except Exception:
				log.debugWarning("VisionClaw: the seat map could not be read again", exc_info=True)
		finally:
			reader.finish()
		task.items = None  # the page has probably changed
		return " ".join([seats.mapText(seatMap)] + list(notes) + [seats.done(seat, after)])

	add("pick_seat",
		"on a seat map that is showing, such as an airline's: find the free seats that fit what the user asks (window, "
		"aisle, front, back, near a row, ahead of the wing, an exit row, or one seat by its number) and, if asked to, "
		"choose one after a question",
		pickSeat, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Finding a seat", tell=VERBATIM)
