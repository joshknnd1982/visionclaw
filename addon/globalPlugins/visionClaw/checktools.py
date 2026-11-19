# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tool for a check on a web page that asks whether the visitor is a person: "I'm not a robot",
# "Verify you are human", a puzzle of pictures, a piece to drag. Such a check shuts a blind person out wherever
# its way without sight is missing or broken. This tool makes the check perceivable and workable for the person
# in front of the computer, and no more than that (claw/humancheck.py says the same, and has every sentence):
#   - it says which kind of check is there, what it shows, and the ways through it that need no sight, first;
#   - it presses the check's box for the person: with NVDA's own action, and with one mouse click on the box only
#     if that did nothing that can be seen;
#   - it reads what a puzzle asks from the page or from the text in its picture, and has the model that sees say
#     what each square shows, one square at a time; the model is never told what the puzzle asks for;
#   - it clicks the squares the person names by their numbers, and a button of the check the person names;
#   - it turns on pointer mode with the pointer on a handle that must be dragged; the person drags it.
# THE PERSON ANSWERS THE CHECK. What this file must never do, and tests/test_humancheck.py guards it:
#   - decide which squares are selected: the numbers are read from the user's own words by plain code, and a
#     number that is not in the request the user made is not clicked;
#   - press anything without asking first: every press goes through mustAgree, whatever the settings say;
#   - work in the background, or try again by itself: one request, one look, the presses the user named, one
#     look afterwards, and the user is told what the check shows then, never that it was passed;
#   - imitate a hand: clicks are plain clicks with one fixed pause between them, the same every time; nothing is
#     made to look like a person's movement, and nothing about the browser is changed;
#   - use any service outside this computer.
# The page is asked first (what NVDA keeps of it in browse mode), then the window's picture. After a press the
# check is looked at again. Nothing of this has run in a real browser against a real check.

import math
import re
import time

import addonHandler
import config

from . import deepquery, fixruntime, mousetools, ocr, pagetools
from .claw import dragcontrol, humancheck, pointer, policy, prompts, spots
from .claw.catalog import VISION
from .claw.llm import clip
from .claw.tools import VERBATIM
from .engine import prepareImage
from .vclog import log

addonHandler.initTranslation()

# How long the page is given after a press before it is looked at again.
SETTLE_SECONDS = 0.8
# The one pause between two clicks on squares: so that the page takes each. It is the same every time.
BETWEEN_SECONDS = 0.3
# A page with no more controls than this that names a check is taken to be the check's own page.
SMALL_PAGE = 80
# A square is made at least this large before the model that sees is asked about it.
SQUARE_SIDE = 224
_SLIDES = re.compile(r"\b(slide|slider|drag|puzzle piece|handle)\b", re.IGNORECASE)


def _label(node):
	return " ".join(str(node.get("name") or node.get("text") or "").split())


def _under(node, frames):
	up = node.get("up")
	while up is not None:
		if any(up is frame for frame in frames):
			return True
		up = up.get("up")
	return False


def _shown(node):
	return not node.get("hidden") and "INVISIBLE" not in (node.get("states") or ())


def _nodeBox(document, node):
	"""Where a control of the page is on the screen, or None. Main thread."""
	key = node.get("key")
	if not key:
		return None
	try:
		obj = document.getNVDAObjectFromIdentifier(int(key[0]), int(key[1]))
	except Exception:
		return None
	return deepquery.boxOf(obj) if obj is not None else None


def _pressNode(document, node):
	"""Press a control of the page with NVDA's own action, as Enter does in browse mode. Main thread."""
	fixruntime.locate(document, node)
	fixruntime.activateOnPage(document, node)


def _pointerOn(plugin, point):
	"""Turn pointer mode on, with the mouse pointer on a place when one is given. Returns how far one press of an
	arrow key moves the pointer, plainly and with Shift. Main thread."""
	mode = plugin.pointerMode
	mode.place()
	mode.active, mode.holding = True, False
	box = mode._box()
	if point is not None:
		mode.x, mode.y = pointer.clamp(int(point[0]), int(point[1]), box)
		mousetools.moveTo(mode.x, mode.y)
		mode.scale = mousetools.scaleAt(mode.x, mode.y)
	return pointer.stepFor(pointer.STEP, box, mode.scale), pointer.stepFor(pointer.FINE, box, mode.scale)


def readPage(task, onMain):
	"""What the web page says of a check, as NVDA has it in browse mode: None when the user is in no web page;
	else {"document"; "frames": the frames whose titles name a check; "titles"; "texts": the lines of text of the
	check; "boxes", "buttons", "handles": its check boxes, its buttons, and what is dragged, as controls of the page}."""
	found = onMain(pagetools._where)
	if found is None:
		return None
	document = found[0]
	nodes = [node for node in pagetools.pageNodes(task, document, onMain) if _shown(node)]
	frames = [node for node in nodes if node.get("role") in ("INTERNALFRAME", "FRAME") and humancheck.isCheck(_label(node))]
	if frames:
		inner = [node for node in nodes if _under(node, frames)]
	else:
		# A check that is part of the page itself: its own controls name it, or the page holds nothing else.
		named = [node for node in nodes if humancheck.isCheck(_label(node))]
		inner = nodes if named and len(nodes) <= SMALL_PAGE else named
	texts = []
	for node in inner:
		said = _label(node)
		if said and said not in texts:
			texts.append(said)
	return {
		"document": document, "frames": frames, "titles": [_label(frame) for frame in frames], "texts": texts,
		"boxes": [node for node in inner if node.get("role") == "CHECKBOX"],
		"buttons": [node for node in inner if node.get("role") == "BUTTON"],
		"handles": [node for node in inner if node.get("role") == "SLIDER"
			or (node.get("role") in ("BUTTON", "GRAPHIC") and _SLIDES.search(_label(node)))],
	}


class Check:
	"""One look at a check for one request, and what the user asked to be done with it."""

	def __init__(self, task, plugin, onMain, mustAgree, screen):
		self.task, self.plugin, self.onMain, self.mustAgree, self.screen = task, plugin, onMain, mustAgree, screen

	# --- Looking ---

	def look(self):
		"""The check as it is now: what the page says of it, and the picture of the window with the text in it."""
		task = self.task
		try:
			page = readPage(task, self.onMain)
		except Exception as e:
			if type(e).__name__ == "Cancelled":
				raise
			log.debugWarning("VisionClaw: the page could not be read for a check", exc_info=True)
			page = None
		task.check()
		image, box = self.screen.picture("window")
		origin = (box[0], box[1]) if box else (0, 0)
		lines = (ocr.recognize(image) if config.conf["visionClaw"]["useOcr"] else None) or []
		task.check()
		rows = [" ".join(word.get("text", "") for word in line) for line in lines]
		own = page["texts"] if page else []
		kind = humancheck.kindOf(page["titles"] if page else [], own + rows)
		frames = []
		for frame in (page["frames"] if page else ()):
			place = self.onMain(_nodeBox, page["document"], frame)
			if place is not None:
				frames.append((place[0] - origin[0], place[1] - origin[1], place[2] - origin[0], place[3] - origin[1]))
		asks = humancheck.asksOf(own) or humancheck.asksOf(rows)
		asksBox = None
		for line, said in zip(lines, rows):
			if line and humancheck.asksOf([said]):
				asksBox = (min(word["x"] for word in line), min(word["y"] for word in line),
					max(word["x"] + word["width"] for word in line), max(word["y"] + word["height"] for word in line))
				break
		return {
			"page": page, "image": image, "origin": origin, "lines": lines, "rows": rows, "kind": kind, "asks": asks,
			"asksBox": asksBox, "frames": frames, "status": humancheck.statusOf(own),
			"checked": any("CHECKED" in (node.get("states") or ()) for node in (page["boxes"] if page else ())),
			"stage": humancheck.stageOf(own + rows) if kind is not None else None,
		}

	@staticmethod
	def summary(state):
		return {key: state[key] for key in ("kind", "stage", "asks", "status", "checked")}

	@staticmethod
	def area(state):
		"""The part of the window's picture that holds the check, or None for all of it."""
		frames = state["frames"]
		if not frames:
			return None
		width, height = state["image"].size
		box = (max(0, min(f[0] for f in frames)), max(0, min(f[1] for f in frames)),
			min(width, max(f[2] for f in frames)), min(height, max(f[3] for f in frames)))
		return box if box[2] - box[0] >= 8 and box[3] - box[1] >= 8 else None

	def squares(self, state):
		"""The squares of the puzzle in the picture, or None: (rows, columns, their boxes in the picture)."""
		return humancheck.squaresIn(state["image"], humancheck.areasFor(state["image"].size, state["frames"], state["asksBox"]))

	def changed(self, before, after):
		"""Whether anything VisionClaw can see is different after a press."""
		if self.summary(before) != self.summary(after):
			return True
		first, second = before["image"], after["image"]
		area = self.area(before)
		if area is not None and first.size == second.size:
			first, second = first.crop(area), second.crop(area)
		return dragcontrol.changed(first, second) >= dragcontrol.CHANGED

	def seer(self):
		return policy.roleName(VISION, policy.isOneModel(self.plugin.runtime))

	def ask(self, picture, prompt, tokens):
		"""One small question about one picture to the model that sees."""
		answer = self.plugin.runtime.describe(
			prepareImage(picture, config.conf["visionClaw"]["detailSize"]), prompt, tokens, cancel=self.task.cancel,
			system=prompts.seeing())
		self.task.check()
		return answer or ""

	# --- What the user can ask for ---

	def tell(self, wished):
		state = self.look()
		if state["kind"] is None:
			return humancheck.NO_CHECK
		page = state["page"]
		stage = humancheck.PUZZLE if state["asks"] or self.squares(state) else state["stage"]
		return humancheck.tellText(
			state["kind"], stage, state["asks"], state["status"],
			[_label(node) for node in (page["boxes"] if page else ())],
			[_label(node) for node in (page["buttons"] if page else ())], wished["wholeCheck"])

	def describe(self, wished, asked):
		task = self.task
		state = self.look()
		# Only a check is described here: a grid of pictures on a page that names no check is none of this tool's.
		if state["kind"] is None:
			return humancheck.NO_CHECK
		found = self.squares(state)
		if found is None:
			if state["kind"] == humancheck.SLIDER:
				area = self.area(state)
				gap = self.ask(state["image"].crop(area) if area else state["image"], humancheck.GAP_PROMPT, 90)
				said = " ".join(gap.split()) or "nothing"
				return (
					f"{humancheck.kindText(state['kind'], state['stage'], state['asks'], state['status'])} The {self.seer()} says "
					f"of its picture, and a model can be wrong: {said} You drag it; say: take hold of the slider. {humancheck.SHORT_NOTICE}")
			lead = humancheck.NOT_CHOSEN + " " if wished["byContent"] else ""
			return f"{lead}{humancheck.kindText(state['kind'], state['stage'], state['asks'], state['status'])} {humancheck.NO_SQUARES}"
		rows, columns, tiles = found
		wanted = humancheck.describeSome(asked, len(tiles))
		prompt = humancheck.ONE_SQUARE_PROMPT if len(wanted) == 1 else humancheck.SQUARE_PROMPT
		said = []
		for number in wanted:
			task.check()
			square = state["image"].crop(tiles[number - 1])
			grow = max(1, math.ceil(SQUARE_SIDE / max(1, min(square.size))))
			if grow > 1:
				square = square.resize((square.size[0] * grow, square.size[1] * grow))
			task.emit("detail", f"Square {number} of {len(tiles)}.")
			# The model is asked what this one square shows, and nothing about what the puzzle asks for.
			said.append((number, self.ask(square, prompt, 90 if len(wanted) == 1 else 40)))
		# What each square was said to show is kept in the request's work sheet with the other small questions
		# (claw/worksheet.py); the sheet is deleted when the request ends.
		sheet = getattr(task, "sheet", None)
		if sheet is not None and said:
			sheet.section("Squares of the check", "\n".join(f"{number}. {clip(str(text), 200)}" for number, text in said))
		left, top = state["origin"]
		task.checkSquares = {
			"tiles": [(left + box[0], top + box[1], left + box[2], top + box[3]) for box in tiles], "rows": rows,
			"columns": columns, "summary": self.summary(state)}
		return humancheck.puzzleText(state["asks"], rows, columns, said, self.seer(), wished["byContent"])

	def _button(self, state, button):
		"""The button of the check that the user named: ("page", its control, its name), ("picture", where it is on
		the screen, its word), or None."""
		page = state["page"]
		if page:
			names = [_label(node) for node in page["buttons"]]
			index = humancheck.buttonIn(button, names)
			if index is not None:
				return "page", page["buttons"][index], names[index]
		pattern = re.compile(humancheck.BUTTON_WORDS[button], re.IGNORECASE)
		area = self.area(state)
		left, top = state["origin"]
		for line in state["lines"]:
			# A button's own words stand alone; the same word inside a sentence, as in what the puzzle asks, is no button.
			if len(line) > 3:
				continue
			for word in line:
				box = spots.wordBox(word)
				if area is not None and not (area[0] <= box[0] and box[2] <= area[2] and area[1] <= box[1] and box[3] <= area[3]):
					continue
				if pattern.fullmatch(word.get("text", "").strip(" .,:;!?")):
					x, y = spots.middleOf(box)
					return "picture", (left + x, top + y), word["text"].strip(" .,:;!?")
		return None

	def _press(self, state, found):
		how, target, _name = found
		if how == "page":
			self.onMain(_pressNode, state["page"]["document"], target)
		else:
			self._click([target])

	def _click(self, points):
		"""Plain clicks, one after another with one fixed pause, and the pointer put back."""
		old = mousetools.position()
		try:
			for index, (x, y) in enumerate(points):
				self.task.check()
				if index:
					time.sleep(BETWEEN_SECONDS)
				mousetools.click(int(round(x)), int(round(y)))
		finally:
			mousetools.moveTo(*old)

	def select(self, wished, asked):
		task = self.task
		kept = getattr(task, "checkSquares", None)
		state = None
		if kept:
			tiles, before = kept["tiles"], kept["summary"]
		else:
			state = self.look()
			if state["kind"] is None:
				return humancheck.NO_CHECK
			found = self.squares(state)
			if found is None:
				return humancheck.NO_SQUARES
			left, top = state["origin"]
			tiles = [(left + box[0], top + box[1], left + box[2], top + box[3]) for box in found[2]]
			before = self.summary(state)
		# Only numbers the user said: in the words of this step, and in the request as the user made it.
		named = humancheck.numbers(asked, len(tiles))
		request = getattr(task, "request", "") or ""
		if request:
			own = humancheck.numbers(request, len(tiles))
			named = [number for number in named if number in own]
		if not named:
			return humancheck.NO_NUMBERS
		then = wished["then"]
		self.mustAgree(humancheck.selectQuestion(named, then))
		picture, box = self.screen.picture("window")
		origin = (box[0], box[1]) if box else (0, 0)
		self._click([spots.middleOf(tiles[number - 1]) for number in named])
		time.sleep(SETTLE_SECONDS)
		task.items = None
		task.check()
		after, _box = self.screen.picture("window")
		taken = []
		for number in named:
			tile = tiles[number - 1]
			inside = (tile[0] - origin[0], tile[1] - origin[1], tile[2] - origin[0], tile[3] - origin[1])
			taken.append(dragcontrol.changed(picture.crop(inside), after.crop(inside)) >= dragcontrol.CHANGED
				if after.size == picture.size else None)
		pressed = None
		now = self.look()
		said = humancheck.afterText(before, self.summary(now))
		if then:
			found = self._button(now, then)
			pressed = found is not None
			if pressed:
				# The button the user named in the same words; the question named it too.
				self._press(now, found)
				time.sleep(SETTLE_SECONDS)
				task.checkSquares = None  # the check has probably changed
				later = self.look()
				said = humancheck.afterText(before, self.summary(later), self.changed(now, later))
		return humancheck.selectedText(named, taken, then, pressed, "" if said == humancheck.STILL else said)

	def button(self, wished):
		state = self.look()
		if state["kind"] is None:
			return humancheck.NO_CHECK
		found = self._button(state, wished["button"])
		if found is None:
			page = state["page"]
			return humancheck.noButton(wished["button"], [_label(node) for node in (page["buttons"] if page else ())])
		self.mustAgree(humancheck.buttonQuestion(found[2]))
		self._press(state, found)
		time.sleep(SETTLE_SECONDS)
		self.task.items = self.task.checkSquares = None
		after = self.look()
		return humancheck.buttonText(found[2], humancheck.afterText(self.summary(state), self.summary(after), self.changed(state, after)))

	def _boxInPicture(self, state):
		"""Where the check's box is in the picture, from the words written next to it: ((x, y) on the screen, "mouse"
		when a box was found there, "beside" when only the words were), or None."""
		image, lines = state["image"], state["lines"]
		left, top = state["origin"]
		for words in humancheck.BOX_WORDS:
			places = spots.phrase(lines, words)
			if not places:
				continue
			label = places[0]
			scale = self.onMain(mousetools.scaleAt, left + label[0], top + label[1])
			square = spots.squareFor(label, spots.squares(image, scale))
			if square is not None:
				x, y = spots.middleOf(square["box"])
				return (left + x, top + y), "mouse"
			tall = max(6, label[3] - label[1])
			return (left + label[0] - round(1.5 * tall), top + (label[1] + label[3]) // 2), "beside"
		return None

	def box(self):
		task = self.task
		state = self.look()
		if state["kind"] is None:
			return humancheck.NO_CHECK
		page = state["page"]
		node = page["boxes"][0] if page and page["boxes"] else None
		if node is not None and "CHECKED" in (node.get("states") or ()):
			said = "Nothing was pressed: the check's box is already checked, as NVDA has it."
			return said + (f" The check itself says: {state['status']}" if state["status"] else "")
		place = None if node is not None else self._boxInPicture(state)
		if node is None and place is None:
			return humancheck.NO_BOX
		self.mustAgree(humancheck.boxQuestion(state["kind"], _label(node) if node is not None else ""))
		before = self.summary(state)
		task.items = None
		if node is not None:
			pressed = True
			try:
				self.onMain(_pressNode, page["document"], node)
			except Exception:
				log.debugWarning("VisionClaw: NVDA's own action did not press the check's box", exc_info=True)
				pressed = False
			time.sleep(SETTLE_SECONDS)
			after = self.look()
			if pressed and self.changed(state, after):
				return humancheck.boxText("nvda", humancheck.afterText(before, self.summary(after), True))
			# NVDA's own action did nothing that can be seen. The mouse on the box, once; this is the same press.
			where = self.onMain(_nodeBox, page["document"], node)
			place = (spots.middleOf(where), "mouse") if where is not None else self._boxInPicture(after)
			if place is None:
				return (
					"NVDA's own action on the check's box did nothing VisionClaw can see, and where the box is on the screen "
					f"is not known, so the mouse was not used. {humancheck.afterText(before, self.summary(after), False)}")
			state = after
		point, how = place
		self._click([point])
		time.sleep(SETTLE_SECONDS)
		after = self.look()
		return humancheck.boxText(how, humancheck.afterText(before, self.summary(after), self.changed(state, after)))

	def hold(self):
		state = self.look()
		if state["kind"] is None:
			return humancheck.NO_CHECK + " For a slider of a program that is no such check, ask to work the slider with the arrow keys."
		page = state["page"]
		left, top = state["origin"]
		area = self.area(state)
		point, where = None, "middle"
		for handle in (page["handles"] if page else ()):
			place = self.onMain(_nodeBox, page["document"], handle)
			if place is not None:
				tall = place[3] - place[1]
				# A long control is the track, with its handle at its left end; a short one is the handle itself.
				point = (place[0] + tall // 2, (place[1] + place[3]) // 2) if place[2] - place[0] > 3 * tall else spots.middleOf(place)
				where = "page"
				break
		if point is None:
			for line, said in zip(state["lines"], state["rows"]):
				if line and _SLIDES.search(said):
					tall = max(6, max(word["height"] for word in line))
					start = area[0] + tall if area is not None else min(word["x"] for word in line) - 2 * tall
					middle = sum(word["y"] + word["height"] / 2.0 for word in line) / len(line)
					point, where = (left + max(0, start), top + middle), "words"
					break
		picture = state["image"].crop(area) if area is not None else state["image"]
		# Where the gap is helps, but pointer mode must not depend on a model being there.
		try:
			gap = self.ask(picture, humancheck.GAP_PROMPT, 90)
		except Exception as e:
			if type(e).__name__ == "Cancelled":
				raise
			log.debugWarning("VisionClaw: the model that sees could not be asked where the gap is", exc_info=True)
			gap = ""
		plain, fine = self.onMain(_pointerOn, self.plugin, point)
		steps = None
		if area is not None and plain and fine:
			wide = area[2] - area[0]
			steps = (math.ceil(wide / plain), math.ceil(wide / fine))
		return humancheck.holdText(where, gap, self.seer(), steps)


def register(add, plugin, text, onMain, confirm, mustAgree, screen):
	def humanCheck(task, asked):
		said = asked or task.request
		wished = humancheck.wish(said)
		check = Check(task, plugin, onMain, mustAgree, screen)
		what = wished["what"]
		if what == humancheck.DESCRIBE:
			return check.describe(wished, said)
		if what == humancheck.SELECT:
			return check.select(wished, said)
		if what == humancheck.PRESS_BOX:
			return check.box()
		if what == humancheck.VERIFY:
			return check.button(wished)
		if what == humancheck.HOLD:
			return check.hold()
		return check.tell(wished)

	add("human_check",
		"for a check on a web page that asks whether you are a person (I'm not a robot, Verify you are human, a puzzle "
		"of pictures, a piece to drag): say which kind it is and the ways through it that need no sight, press its box, "
		"say what the puzzle asks and what each square shows, click the squares the user names by their numbers, press "
		"a button of the check, or turn on pointer mode on its handle; the user answers the check, never VisionClaw",
		humanCheck, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Looking at the check", tell=VERBATIM)
