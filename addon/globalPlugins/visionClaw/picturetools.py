# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tool that looks at one picture on a web page or in a program's window and answers what the
# user asks about it: the latest picture in a chat, a screenshot someone shared, a product's photo, the photos of
# a gallery. Which picture is meant is read from the user's own words and chosen by plain code (claw/images.py)
# among the pictures found, the surest way first:
#   1. the pictures the web page itself tells NVDA about in browse mode, in the page's order, with what the
#      page calls each;
#   2. the pictures the program's window tells NVDA about;
#   3. a photo found in the pixels of the window's picture, for a window that tells NVDA nothing.
# The picture is brought into view when it is not, cut out of the screen, its text is read, and the model that
# sees is asked each of the user's questions about that picture alone, one at a time, each with the one rule of
# its kind. A question about a colour gets what plain code measured from the pixels first (claw/colours.py).
# Nothing is changed and nothing is clicked; bringing a picture into view may scroll the page.

import time

import addonHandler
import api
import config

from . import deepquery, fixruntime, imaging, mousetools, ocr, pagetools
from .claw import colours, images, pictures, policy, prompts
from .claw.catalog import VISION
from .claw.llm import clip
from .claw.skills import stepGuide
from .claw.tools import VERBATIM, ToolError
from .engine import prepareImage
from .vclog import log

addonHandler.initTranslation()

# At most this many pictures of a page or a window are asked for their place on the screen.
MAX_PICTURES = 150
SCROLL_SETTLE = 0.45
_PICTURE_ROLES = ("GRAPHIC", "IMAGEMAP", "CANVAS", "FIGURE")


def _onPage(document, nodes):
	"""The pictures of a web page with their places on the screen, in the page's order. Main thread."""
	focus, navigator = api.getFocusObject(), api.getNavigatorObject()
	found = []
	for order, node in enumerate(nodes):
		if len(found) >= MAX_PICTURES:
			break
		key = node.get("key")
		if node.get("role") not in _PICTURE_ROLES or not key or node.get("hidden"):
			continue
		try:
			obj = document.getNVDAObjectFromIdentifier(int(key[0]), int(key[1]))
		except Exception:
			continue
		box = deepquery.boxOf(obj) if obj is not None else None
		if box is None:
			continue
		found.append({"box": box, "name": node.get("name") or "", "order": order, "obj": obj,
			"focused": obj == focus or obj == navigator})
	return found


def _inWindow():
	"""The pictures a program's window tells NVDA about, with their places on the screen. Main thread."""
	focus, navigator = api.getFocusObject(), api.getNavigatorObject()
	found = []
	for order, node in enumerate(fixruntime.windowNodes(api.getForegroundObject())):
		obj = node.get("obj")
		if obj is None or node.get("role") not in _PICTURE_ROLES or "INVISIBLE" in node.get("states", ()):
			continue
		box = deepquery.boxOf(obj)
		if box is None:
			continue
		found.append({"box": box, "name": node.get("name") or node.get("text") or "", "order": order, "obj": obj,
			"focused": obj == focus or obj == navigator})
		if len(found) >= MAX_PICTURES:
			break
	return found


def _intoView(picture, window, onMain):
	"""Bring a picture into the window when most of it is outside, and say where it is then."""
	if images.visible(picture["box"], window) >= 0.6:
		return picture["box"]
	obj = picture.get("obj")
	if obj is None:
		return picture["box"]
	try:
		onMain(obj.scrollIntoView)
		time.sleep(SCROLL_SETTLE)
		return onMain(deepquery.boxOf, obj) or picture["box"]
	except Exception:
		log.debugWarning("VisionClaw: a picture could not be brought into view", exc_info=True)
		return picture["box"]


def _clamp(box, window):
	if window is None:
		return box
	return (max(box[0], window[0]), max(box[1], window[1]), min(box[2], window[2]), min(box[3], window[3]))


def register(add, plugin, text, onMain, confirm, mustAgree, screen):
	def ask(task, image, what, questions):
		"""Ask the model that sees each question about one picture, one at a time. Returns the answer as text."""
		lines = ocr.recognize(image) if config.conf["visionClaw"]["useOcr"] else []
		guide = stepGuide(task)
		seer = policy.roleName(VISION, policy.isOneModel(plugin.runtime))
		prepared = prepareImage(image, config.conf["visionClaw"]["detailSize"])
		if len(questions) > 1:
			task.emit("talk", f"The question is asked in {len(questions)} parts, one at a time: " + "; ".join(asked for _kind, asked in questions) + ".")
		answers, facts = [], ""
		for kind, asked in questions:
			task.check()
			known = ""
			if kind == pictures.COLOUR:
				# What plain code measured goes to the model and to the user: a small model is not sure of colours.
				known = images.measured(image, colours.wanted(asked))
				facts = facts or known
			prompt = (
				ocr.promptPart(lines) + (f"{known}\n" if known else "")
				+ f"Look at this picture, {what}, and answer: {asked} "
				f"Answer in a few short sentences. {images.rule(kind)} If you cannot see it, say so instead of guessing.")
			if guide:
				prompt += f"\n{guide}"
			task.emit("talk", f"Asked the {seer}: {asked}")
			answer = plugin.runtime.describe(prepared, prompt, 350, cancel=task.cancel, system=prompts.seeing())
			task.check()
			task.emit("talk", f"The {seer} answered: {clip(answer, 400)}")
			answers.append((asked, answer or f"The {seer} gave no answer."))
		sheet = getattr(task, "sheet", None)
		if sheet is not None and len(questions) > 1:
			sheet.section("Questions about the picture", "\n".join(
				f"{number}. {asked} ({kind}): {clip(answer, 300)}"
				for number, ((kind, asked), (_asked, answer)) in enumerate(zip(questions, answers), 1)))
		said = pictures.together(answers)
		if facts:
			said = f"{facts}\nThe {seer} says: {said}" if len(answers) == 1 else f"{facts}\n{said}"
		return said

	def lookPicture(task, asked):
		words = asked or task.request
		wished = images.wish(words)
		if wished is None:
			raise ToolError(images.NO_WISH)
		questions = images.asks(words)
		window = onMain(screen.box, "window")
		scale = onMain(mousetools.scaleAt, *(window[:2] if window else (0, 0)))
		where, found = "page", []
		page = onMain(pagetools._where)
		if page is not None:
			nodes = pagetools.pageNodes(task, page[0], onMain)
			found = onMain(_onPage, page[0], nodes)
		chosen, more = images.choose(wished, found, window, scale)
		if not chosen:
			where = "window"
			found = onMain(_inWindow)
			chosen, more = images.choose(wished, found, window, scale)
		task.check()
		if not chosen:
			# A window that tells NVDA nothing: a photo is looked for in its pixels, in its lower part first when
			# the newest picture of a chat is meant.
			whole, box = screen.picture("window")
			left, top = (box[0], box[1]) if box else (0, 0)
			spot = None
			if wished["which"] == images.LATEST:
				lower = (0, whole.size[1] // 2, whole.size[0], whole.size[1])
				inner = imaging.findPhoto(whole.crop(lower))
				if inner is not None:
					spot = (inner[0], inner[1] + lower[1], inner[2], inner[3] + lower[1])
			if spot is None:
				spot = imaging.findPhoto(whole)
			if spot is None:
				return images.NOT_FOUND
			picture = {"box": (left + spot[0], top + spot[1], left + spot[2], top + spot[3]), "name": "", "order": 0}
			said = ask(task, whole.crop(spot), "which was found in the window in front", questions)
			return f"{images.lead(wished, picture, where='picture')}: {said}"
		answers = []
		for number, picture in enumerate(chosen, 1):
			task.check()
			box = _clamp(_intoView(picture, window, onMain), window)
			if box[2] - box[0] < 8 or box[3] - box[1] < 8:
				answers.append(f"{images.lead(wished, picture, number, len(chosen), where)}: it could not be brought into view.")
				continue
			try:
				image = plugin._grab(box)
			except Exception as e:
				raise ToolError(f"The screen could not be captured: {e}")
			what = "which is one picture " + ("of a web page" if where == "page" else "from a program's window")
			named = images.calls(picture)
			if named:
				what += f"; the {'page' if where == 'page' else 'program'} calls it \"{clip(named, 120)}\""
			said = ask(task, image, what, questions)
			answers.append(f"{images.lead(wished, picture, number, len(chosen), where)}: {said}")
		return "\n".join(answers) + images.leftOut(more)

	add("look_picture",
		"look at one picture on the web page or in the window in front and answer a question about it: the latest "
		"picture in a chat, a screenshot or meme someone sent, a product's photo, the photos of a gallery; reads its "
		"text, says what it shows, measures its colours",
		lookPicture, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking at the picture", tell=VERBATIM)
