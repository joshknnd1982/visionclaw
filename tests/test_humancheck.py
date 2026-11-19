# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Checks that ask whether the visitor is a person, made perceivable and workable; the person answers them.
Plain Python: no NVDA, no model, no browser, and nothing on the real computer is clicked. The pictures and pages
are drawn by tests/checkdrawn.py and are no real check of any provider; NVDA, the mouse, the reading of text in
pictures and the model that sees are stand-ins. So this says what VisionClaw's own code does with what it is
given, and nothing about a real check on a real website: none of this has run in a browser.

What is guarded here above all is the line: VisionClaw never chooses the squares, never presses without asking,
never tries again by itself, and nothing in it imitates a hand or goes outside this computer.

  python tests/test_humancheck.py
"""
import builtins
import inspect
import os
import re
import sys
import types

import harness  # noqa: F401
import checkdrawn
import drawn
from visionClaw.claw import humancheck as hc
from visionClaw.claw import task as taskModule
from visionClaw.claw import tools

# --- Which check a page has ---

for frames, texts, kind in (
	(["reCAPTCHA"], [], hc.RECAPTCHA),
	(["recaptcha challenge expires in two minutes"], ["Select all images with", "crosswalks"], hc.RECAPTCHA),
	(["Widget containing checkbox for hCaptcha security challenge"], [], hc.HCAPTCHA),
	(["Widget containing a Cloudflare security challenge"], ["Verify you are human"], hc.TURNSTILE),
	([], ["Verify you are human", "example.org needs to review the security of your connection", "Performance and security by Cloudflare"], hc.TURNSTILE),
	(["Verification challenge"], ["Protected by Arkose Labs"], hc.ARKOSE),
	([], ["Slide to verify"], hc.SLIDER), ([], ["Drag the puzzle piece into place"], hc.SLIDER),
	([], ["Type the characters you see in the picture"], hc.TEXT),
	([], ["Please verify you are human"], hc.UNKNOWN), ([], ["I'm not a robot"], hc.UNKNOWN),
	([], ["Complete the CAPTCHA to go on"], hc.UNKNOWN),
	# A provider's name in a frame's title tells more than words in the page's text.
	(["hCaptcha"], ["this site is protected by reCAPTCHA too"], hc.HCAPTCHA),
	([], ["Winter boots", "Add to cart", "Sign in with your email address"], None),
	(["Advertisement", "YouTube video player"], ["Gift wrap", "Search"], None),
	# "With captcha" holds no h and no re of its own.
	([], ["Sign in with captcha"], hc.UNKNOWN),
):
	assert hc.kindOf(frames, texts) == kind, (frames, texts, hc.kindOf(frames, texts))
assert hc.isCheck("reCAPTCHA") and hc.isCheck("Verify you are human") and not hc.isCheck("Newsletter sign-up")

# --- What a puzzle asks, word for word, and what the check says of itself ---

assert hc.asksOf(["Select all squares with", "traffic lights", "Click verify once there are none left."]) == (
	"Select all squares with traffic lights. Click verify once there are none left.")
assert hc.asksOf(["Email address", "Select all images with crosswalks", "If there are none, click skip"]) == (
	"Select all images with crosswalks. If there are none, click skip")
assert hc.asksOf(["Please click each image containing a bus"]) == "Please click each image containing a bus"
assert hc.asksOf(["I'm not a robot", "Privacy", "Terms"]) == "" and hc.asksOf([]) == ""
assert hc.statusOf(["I'm not a robot", "You are verified"]) == "You are verified"
assert hc.statusOf(["Verification expired, check the checkbox again for a new challenge"]).startswith("Verification expired")
assert hc.statusOf(["Select all images with errors", "Privacy"]) == ""
assert hc.stageOf(["I'm not a robot"]) == hc.BOX and hc.stageOf(["Select all squares with", "buses"]) == hc.PUZZLE
assert hc.stageOf([], squares=9) == hc.PUZZLE

# --- The numbers of squares: only what the user's own words name ---

for said, count, wanted in (
	("select squares 1, 4 and 7", 9, [1, 4, 7]), ("click 2 and 9 then verify", 9, [2, 9]),
	("pick the first and the last one", 9, [1, 9]), ("select tiles three, five and eight", 9, [3, 5, 8]),
	("the second and the 4th square", 16, [2, 4]), ("choose images 3 and 12", 9, [3]), ("select square 0 and 10", 9, []),
	("squares 1 1 and 1", 9, [1]), ("click number 16", 16, [16]), ("click number 16", 9, []),
	# Numbers that count something else are no squares.
	("it is a 3 by 3 grid", 9, []), ("the 4x4 one", 16, []), ("wait 2 seconds and try 3 times", 9, []),
	("describe this one", 9, []), ("what is in that one", 9, []), ("give me another one", 9, []),
	# What a puzzle itself asks names no square, and neither does a request to choose by what is shown.
	("select all squares with traffic lights", 9, []), ("select every image that shows a bus", 9, []),
	("solve this captcha", 9, []), ("get me past this", 9, []), ("select all of them", 9, []), ("", 9, []),
):
	assert hc.numbers(said, count) == wanted, (said, hc.numbers(said, count))
assert list(inspect.signature(hc.numbers).parameters) == ["part", "count"]

# --- What the user's words ask ---

for said, what in (
	("what kind of check is this", hc.TELL), ("is this a captcha", hc.TELL), ("what are my options for this captcha", hc.TELL),
	("how do I get past this captcha", hc.TELL), ("is there an audio version of this check", hc.TELL),
	("help me with this captcha", hc.TELL), ("there is a captcha here", hc.TELL),
	("Locate and click the 'Verify you are human' Cloudflare Turnstile checkbox on screen", hc.PRESS_BOX),
	("click the I'm not a robot box", hc.PRESS_BOX), ("press the verify you are human check box", hc.PRESS_BOX),
	("tick the I am human box for me", hc.PRESS_BOX), ("check the box of the captcha", hc.PRESS_BOX),
	("what does the puzzle ask", hc.DESCRIBE), ("describe the squares", hc.DESCRIBE), ("what do the squares show", hc.DESCRIBE),
	("describe square 5", hc.DESCRIBE), ("what is in squares 2 and 3", hc.DESCRIBE), ("read out the challenge", hc.DESCRIBE),
	("tell me what the captcha wants", hc.DESCRIBE),
	("select squares 1, 4 and 7", hc.SELECT), ("click 2 and 9 then verify", hc.SELECT), ("pick the first and the last one", hc.SELECT),
	("squares 3 and 6", hc.SELECT), ("select tile five and press verify", hc.SELECT), ("select all of them", hc.SELECT),
	("press verify", hc.VERIFY), ("click the Verify button", hc.VERIFY), ("skip this one", hc.VERIFY),
	("get an audio challenge", hc.VERIFY), ("give me a new puzzle", hc.VERIFY), ("now press next", hc.VERIFY),
	("take hold of the slider", hc.HOLD), ("Drag the puzzle piece into the missing slot.", hc.HOLD),
	("slide the handle to verify", hc.HOLD),
):
	assert hc.wish(said)["what"] == what, (said, hc.wish(said))
# Asking VisionClaw to choose the squares, or to do the whole check, never becomes a selection.
for said in (
	"select all squares with traffic lights", "Select all squares with crosswalks", "click every image with a bicycle",
	"select the squares that show buses", "pick the tiles containing motorcycles", "which squares have traffic lights",
	"select the right squares", "click all the images of stairs and then verify", "choose the ones with a boat",
):
	found = hc.wish(said)
	assert found["what"] == hc.DESCRIBE and found["byContent"] and hc.numbers(said, 16) == [], (said, found)
for said in (
	"solve this captcha", "get me past this", "do the captcha for me", "bypass this check", "complete this verification",
	"just get through it", "pass this check for me", "answer this captcha", "beat this puzzle", "get rid of this captcha",
):
	found = hc.wish(said)
	assert found["what"] == hc.TELL and found["wholeCheck"] and hc.numbers(said, 16) == [], (said, found)
assert hc.wish("click 2 and 9 then verify")["then"] == hc.B_VERIFY and hc.wish("select 3 and skip")["then"] == hc.B_SKIP
assert hc.wish("select squares 3 and 6")["then"] is None and hc.wish("click 2 and 9")["then"] is None
assert hc.wish("select squares 1 and 2, then press skip")["then"] == hc.B_SKIP
assert hc.wish("get an audio challenge")["button"] == hc.B_AUDIO and hc.wish("give me a new puzzle")["button"] == hc.B_NEW
assert hc.wish("skip this one")["button"] == hc.B_SKIP and hc.wish("press verify")["button"] == hc.B_VERIFY
assert hc.describeSome("describe square 5", 9) == [5] and hc.describeSome("what is in squares 2 and 3", 9) == [2, 3]
assert hc.describeSome("describe the squares", 9) == list(range(1, 10))
assert hc.describeSome("select all squares with traffic lights", 9) == list(range(1, 10))
names = ["Get a new challenge", "Get an audio challenge", "Help", "Verify"]
assert hc.buttonIn(hc.B_VERIFY, names) == 3 and hc.buttonIn(hc.B_AUDIO, names) == 1 and hc.buttonIn(hc.B_NEW, names) == 0
assert hc.buttonIn(hc.B_SKIP, names) is None

# --- The sentences ---

ALL = (hc.RECAPTCHA, hc.HCAPTCHA, hc.TURNSTILE, hc.ARKOSE, hc.SLIDER, hc.TEXT, hc.UNKNOWN)
# Nothing the user is told may promise that a check was got through; only the check's own words may say "verified".
PROMISES = re.compile(r"\b(solved|passed|you are through|got through|is done for you|beaten|bypassed|defeated)\b", re.IGNORECASE)
SIGHTED = re.compile(r"\b(headphone icon|blue button|as you can see|look at the|hover over|at the top right|icon at)\b", re.IGNORECASE)
for kind in ALL:
	ways = hc.waysText(kind)
	assert ways and not PROMISES.search(ways) and not SIGHTED.search(ways), kind
	told = hc.tellText(kind, hc.PUZZLE, "Select all squares with traffic lights. Click verify once there are none left.",
		"Recaptcha requires verification", ["I'm not a robot"], ["Get a new challenge", "Get an audio challenge", "Help", "Verify"] * 3)
	assert len(told) <= tools.RESULT_CHARS, (kind, len(told))
	assert hc.NAMES[kind] in told and hc.NOTICE in told and "You answer the check" in told or "you answer the check" in told, kind
	assert not PROMISES.search(told) and not SIGHTED.search(told), kind
assert "Get an audio challenge" in hc.waysText(hc.RECAPTCHA) and "PLAY" in hc.waysText(hc.RECAPTCHA)
assert "hcaptcha.com/accessibility" in hc.waysText(hc.HCAPTCHA) and "no audio challenge" in hc.waysText(hc.HCAPTCHA)
assert "no pictures or text to make out" in hc.waysText(hc.TURNSTILE)
assert "says nothing about how its puzzles are done without sight" in hc.waysText(hc.ARKOSE)
assert hc.tellText(hc.TURNSTILE, hc.BOX, wholeCheck=True).startswith("VisionClaw does not get through a check for you")
assert "built to be hard for programs" in hc.NOTICE and "audio challenge or accessibility option" in hc.NOTICE
said = [(number, "A long row of parked cars beside a street with trees, houses, a bus stop and a traffic light at the far end of it") for number in range(1, 17)]
text = hc.puzzleText("Select all squares with traffic lights. Click verify once there are none left.", 4, 4, said)
assert len(text) <= tools.RESULT_CHARS and "Square 16:" in text and text.startswith("The check asks: Select all squares with traffic lights."), len(text)
assert "16 squares, 4 rows of 4, numbered from left to right and from the top down" in text
assert "a model can be wrong" in text and "VisionClaw selects only the squares you name" in text
text = hc.puzzleText("", 3, 3, [(n, "a tree") for n in range(1, 10)], byContent=True)
assert text.startswith(hc.NOT_CHOSEN) and "could not be read as text" in text and "Square 9: a tree." in text
assert hc.squareText("  ") == "no description" and hc.squareText("A bus.") == "A bus"
question = hc.selectQuestion([1, 4, 7], hc.B_VERIFY)
assert question.startswith("Click squares 1, 4 and 7 of the check with the mouse, as you said, and then press its button Verify?")
assert "may not get through" in question and hc.selectQuestion([3]).startswith("Click square 3 of the check")
assert hc.boxQuestion(hc.TURNSTILE, "Verify you are human").startswith(
	"Press the check box of Cloudflare's Turnstile, Verify you are human, for you?")
assert hc.numbersText([2]) == "2" and hc.numbersText([2, 9]) == "2 and 9" and hc.numbersText([1, 4, 7]) == "1, 4 and 7"
before = {"kind": hc.RECAPTCHA, "stage": hc.BOX, "asks": "", "status": "Recaptcha requires verification", "checked": False}
assert hc.afterText(before, None).startswith("No check is found here any more") and "for the page to say" in hc.afterText(before, None)
assert hc.afterText(before, dict(before, status="You are verified")) == "The check itself now says: You are verified."
assert hc.afterText(before, dict(before, stage=hc.PUZZLE, asks="Select all images with buses")).startswith(
	"The check has opened a puzzle. It asks: Select all images with buses.")
puzzled = dict(before, stage=hc.PUZZLE, asks="Select all images with buses")
assert hc.afterText(puzzled, dict(puzzled, asks="Select all images with boats")).startswith("The check now shows another puzzle.")
assert hc.afterText(before, dict(before, checked=True)) == "The check's box is now checked, as NVDA has it."
assert hc.afterText(before, dict(before), changed=False).startswith("The check looks the same as before")
assert hc.afterText(before, dict(before)) == hc.STILL
for after in (None, dict(before), dict(before, checked=True), puzzled):
	for changed in (None, True, False):
		assert not PROMISES.search(hc.afterText(before, after, changed))
done = hc.selectedText([1, 4, 7], [True, False, True], hc.B_VERIFY, True, "The check now shows another puzzle. It asks: boats.")
assert done.startswith("Clicked squares 1, 4 and 7, as you said. Nothing VisionClaw can see changed at 4,") and "Pressed the button Verify." in done
assert "was not found, so it was not pressed" in hc.selectedText([2], [True], hc.B_SKIP, False)
assert "this is a guess" in hc.holdText("words") and "You drag it; VisionClaw does not." in hc.holdText("page", "The piece is on the left.", steps=(17, 85))
assert "letting go is your answer to the check" in hc.holdText("middle")

# --- The squares of a puzzle found in a picture ---

image, boxes = drawn.tiles(3, 3)


def near(found, wanted, slack=2):
	return len(found) == len(wanted) and all(all(abs(a - b) <= slack for a, b in zip(one, other)) for one, other in zip(found, wanted))


rows, columns, tiles = hc.squaresIn(image)
assert (rows, columns) == (3, 3) and near(tiles, boxes)
# Inside a frame that also holds a heading and buttons, the rows of squares are told from the bands between plain rows.
for size in ((3, 3), (4, 4), (2, 4)):
	drawing = checkdrawn.puzzle(*size)
	found = hc.squaresIn(drawing["page"].image, hc.areasFor(drawing["page"].image.size, [drawing["frame"]]))
	assert found is not None and (found[0], found[1]) == size and near(found[2], drawing["tiles"]), (size, found and found[:2])
# Without the frame's place, the words that say what is asked point to where the squares are.
drawing = checkdrawn.puzzle()
asksBox = next((min(w["x"] for w in line), min(w["y"] for w in line), max(w["x"] + w["width"] for w in line),
	max(w["y"] + w["height"] for w in line)) for line in drawing["page"].lines if line[0]["text"] == "Select")
found = hc.squaresIn(drawing["page"].image, hc.areasFor(drawing["page"].image.size, [], asksBox))
assert found is not None and (found[0], found[1]) == (3, 3) and near(found[2], drawing["tiles"])
# A window with no puzzle has no squares; neither has a check that shows only its box.
assert hc.squaresIn(checkdrawn.plain()["page"].image) is None
assert hc.squaresIn(checkdrawn.boxCheck()["page"].image, hc.areasFor((900, 500), [checkdrawn.boxCheck()["frame"]])) is None
assert hc.MAX_SQUARES == 16

# --- NVDA's keys named here are NVDA's own. Where NVDA is installed on this computer, its user guide is asked. ---

guide = r"C:\Program Files\NVDA\documentation\en\userGuide.html"
if os.path.isfile(guide):
	import html
	manual = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", open(guide, encoding="utf-8").read())).split())
	for needed in ("x: checkbox", "b: button", "e: edit field", "Toggle browse/focus modes NVDA+space"):
		assert needed in manual, needed
	guideChecked = True
else:
	guideChecked = False

# --- The tool, with stand-ins for NVDA, the mouse, the reading of text and the model that sees ---


class _Meta(type):
	def __getattr__(cls, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return type(name, (Anything,), {})


class Anything(metaclass=_Meta):
	"""A class that has every attribute, can be called and subclassed, and never complains."""

	def __init__(self, *args, **kwargs):
		pass

	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return Anything()

	def __call__(self, *args, **kwargs):
		return Anything()

	def __iter__(self):
		return iter(())

	def __getitem__(self, key):
		return Anything()


class Stub(types.ModuleType):
	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		found = type(name, (Anything,), {})
		setattr(self, name, found)
		return found


builtins._ = lambda text: text
for name in ("addonHandler", "api", "config", "controlTypes", "globalPluginHandler", "logHandler", "speech", "textInfos",
		"textInfos.offsets", "tones", "ui", "browseMode", "mouseHandler", "winUser"):
	if name not in sys.modules:
		sys.modules[name] = Stub(name)
sys.modules["addonHandler"].initTranslation = lambda: None
sys.modules["config"].conf = {"visionClaw": {"useOcr": True, "detailSize": 448}}
sys.modules["logHandler"].log = Anything()

from visionClaw import checktools, mousetools, ocr, pagetools  # noqa: E402

checktools.SETTLE_SECONDS = checktools.BETWEEN_SECONDS = 0
ORIGIN = (100, 50)


class No(Exception):
	"""The user said no."""


class World:
	"""A window with a check in it, and everything that is done to it written down in order."""

	def __init__(self, drawing, nodes=None, found=None):
		self.drawing, self.nodes, self.found = drawing, nodes, found or {}
		self.events, self.asked, self.prompts = [], [], []
		self.no = False
		self.places = {}
		self.onPress = {}
		self.onClick = None
		self.says = "a street with parked cars"

	# The screen, the reading of text and the page.
	def picture(self, target):
		image = self.drawing["page"].image.copy()
		return image, (ORIGIN[0], ORIGIN[1], ORIGIN[0] + image.size[0], ORIGIN[1] + image.size[1])

	def place(self, node, box):
		self.places[id(node)] = (box[0] + ORIGIN[0], box[1] + ORIGIN[1], box[2] + ORIGIN[0], box[3] + ORIGIN[1])

	def where(self):
		return (self, "A page", "https://example.org/") if self.nodes is not None else None

	# What is done.
	def agree(self, question):
		self.asked.append(question)
		self.events.append(("agree",))
		if self.no:
			raise No()

	def press(self, document, node):
		self.events.append(("press", node["name"]))
		action = self.onPress.get(id(node))
		if action is not None:
			action()

	def click(self, x, y, *more):
		self.events.append(("click", x, y))
		if self.onClick is not None:
			self.onClick(x - ORIGIN[0], y - ORIGIN[1])

	def describe(self, jpeg, prompt, tokens, cancel=None, system=None, **more):
		self.prompts.append((prompt, system))
		return self.says

	def presses(self):
		return [event for event in self.events if event[0] in ("press", "click")]


world = None
pagetools._where = lambda: world.where()
pagetools.pageNodes = lambda task, document, onMain: list(world.nodes)
ocr.recognize = lambda image, *more: [list(line) for line in world.drawing["page"].lines]
checktools._nodeBox = lambda document, node: world.places.get(id(node))
checktools._pressNode = lambda document, node: world.press(document, node)
checktools._pointerOn = lambda plugin, point: world.events.append(("pointer", point)) or (20, 4)
mousetools.click = lambda x, y, *more: world.click(x, y)
mousetools.position = lambda: (5, 5)
mousetools.moveTo = lambda x, y: world.events.append(("move", x, y))
mousetools.scaleAt = lambda x, y: 1.0
pluginStandIn = types.SimpleNamespace(
	runtime=types.SimpleNamespace(describe=lambda *args, **more: world.describe(*args, **more), oneModel=lambda: False))
registered = {}


def add(name, description, fn, fields=None, **options):
	registered[name] = (description, fn, fields, options)


checktools.register(
	add, pluginStandIn, lambda description, **extra: dict({"type": "string", "description": description}, **extra),
	lambda fn, *args: fn(*args), lambda question: (_ for _ in ()).throw(AssertionError("confirm is never used here")),
	lambda question: world.agree(question), types.SimpleNamespace(picture=lambda target: world.picture(target)))
assert list(registered) == ["human_check"]
description, tool, fields, options = registered["human_check"]
assert list(fields) == ["asked"] and fields["asked"]["auto"] is True and fields["asked"]["maxLength"] == 300
assert options == {"changes": True, "title": "Looking at the check", "tell": tools.VERBATIM}
assert "the user answers the check, never VisionClaw" in description


def ask(said, request=None):
	"""One request to the tool, as a step of a request the user made."""
	return tool(taskModule.Task(request if request is not None else said), asked=said)


def puzzleWorld(open_=True):
	"""A page with a check whose puzzle of nine squares is open, as NVDA has it and as its picture."""
	drawing = checkdrawn.puzzle()
	nodes, found = checkdrawn.recaptchaPage(open_=open_)
	made = World(drawing, nodes, found)
	made.place(found["frame"], (40, 90, 200, 100))
	if open_:
		made.place(found["challenge"], drawing["frame"])

	def clicked(x, y):
		for tile in drawing["tiles"]:
			if tile[0] <= x < tile[2] and tile[1] <= y < tile[3]:
				checkdrawn.markTile(drawing["page"], tile)
	made.onClick = clicked
	return made


def middle(box):
	return ((box[0] + box[2]) // 2 + ORIGIN[0], (box[1] + box[3]) // 2 + ORIGIN[1])


def close(point, wanted, slack=3):
	return abs(point[0] - wanted[0]) <= slack and abs(point[1] - wanted[1]) <= slack


# 1. What kind of check is this: told, with the ways that need no sight first; nothing is asked or pressed.
world = puzzleWorld()
result = ask("what kind of check is this")
assert result.startswith("This is Google's reCAPTCHA. It shows a puzzle that asks: Select all squares with traffic lights"), result
assert "Get an audio challenge" in result and hc.NOTICE in result and "The check itself says: Recaptcha requires verification." in result
assert world.asked == [] and world.presses() == [] and world.prompts == []
assert result.index("Google describes a way that needs no sight") < result.index("VisionClaw can press")

# 2. "Solve this captcha": it is not solved. The user is told what is there and what VisionClaw does.
for said in ("solve this captcha", "get me past this", "do the captcha for me"):
	world = puzzleWorld()
	result = ask(said)
	assert result.startswith("VisionClaw does not get through a check for you; here is what is there and what it can do. This is Google's reCAPTCHA."), result
	assert world.asked == [] and world.presses() == [] and world.prompts == [], said

# 3. What the squares show: one small question for each square, and the model is never told what the puzzle asks for.
world = puzzleWorld()
task = taskModule.Task("what does the puzzle ask and what do the squares show")
result = tool(task, asked=task.request)
assert len(world.prompts) == 9 and all(prompt is hc.SQUARE_PROMPT for prompt, _system in world.prompts)
assert all(system for _prompt, system in world.prompts), "every question about a picture is told who the user is"
for word in ("traffic", "lights", "verify", "select", "match", "fit", "{", "contain"):
	assert word not in hc.SQUARE_PROMPT.lower() and word not in hc.ONE_SQUARE_PROMPT.lower(), word
assert result.startswith("The check asks: Select all squares with traffic lights. Click verify once there are none left. It has 9 squares"), result
assert "It has 9 squares, 3 rows of 3" in result and "Square 1: a street with parked cars." in result and "Square 9:" in result
assert "These are the vision model's words for each square, and a model can be wrong." in result
assert world.asked == [] and world.presses() == []
assert len(task.checkSquares["tiles"]) == 9 and close(task.checkSquares["tiles"][0][:2], (world.drawing["tiles"][0][0] + ORIGIN[0], world.drawing["tiles"][0][1] + ORIGIN[1]))
# One square alone is described with more words.
world = puzzleWorld()
result = ask("describe square 5")
assert len(world.prompts) == 1 and world.prompts[0][0] is hc.ONE_SQUARE_PROMPT and "Square 5: a street with parked cars." in result
assert "Square 4:" not in result

# 4. "Select all squares with traffic lights" is what the check asks the user. VisionClaw describes, and clicks nothing.
for said in ("Select all squares with traffic lights.", "click every image with a bicycle and then verify", "select the right squares"):
	world = puzzleWorld()
	result = ask(said)
	assert result.startswith(hc.NOT_CHOSEN + " The check asks:"), (said, result)
	assert world.asked == [] and world.presses() == [] and len(world.prompts) == 9, said

# 5. The squares the user names are clicked, after one question, in the order said; then the button the user named.
world = puzzleWorld()


def verified():
	"""After Verify, this stand-in check is gone from the page and from the picture."""
	world.drawing = checkdrawn.plain()
	world.nodes = checkdrawn.storePage()[0]


world.onPress[id(world.found["verify"])] = verified
tilesNow = list(world.drawing["tiles"])
result = ask("select squares 1, 4 and 7, then verify")
assert world.asked == ["Click squares 1, 4 and 7 of the check with the mouse, as you said, and then press its button Verify? "
	"These checks are built to be hard for programs, so this may not get through."], world.asked
clicks = [event for event in world.events if event[0] == "click"]
assert len(clicks) == 3 and all(close(click[1:], middle(tilesNow[number - 1])) for click, number in zip(clicks, (1, 4, 7))), clicks
assert world.events[0] == ("agree",) and world.events.index(("agree",)) < world.events.index(clicks[0])
assert ("press", "Verify") in world.events and world.events.index(("press", "Verify")) > world.events.index(clicks[-1])
assert ("move", 5, 5) in world.events, "the mouse pointer is put back"
assert result.startswith("Clicked squares 1, 4 and 7, as you said. Pressed the button Verify. No check is found here any more"), result
assert "for the page to say" in result and result.endswith(hc.SHORT_NOTICE) and not PROMISES.search(result)
# Without "then verify", nothing but the squares is pressed, and the squares that were found are kept for the request.
world = puzzleWorld()
task = taskModule.Task("describe the squares, then select squares 2 and 3")
tool(task, asked="describe the squares")
result = tool(task, asked="select squares 2 and 3")
assert [event[0] for event in world.presses()] == ["click", "click"] and len(world.asked) == 1
assert result.startswith("Clicked squares 2 and 3, as you said.") and "Verify" not in result
# A square whose picture did not change is named, never passed over in silence.
world = puzzleWorld()
world.onClick = None
result = ask("click square 6")
assert "Nothing VisionClaw can see changed at 6, so the click may not have been taken there." in result, result
# Numbers outside the puzzle are left out, and the question says exactly what will be clicked.
world = puzzleWorld()
result = ask("select squares 3 and 12")
assert world.asked[0].startswith("Click square 3 of the check with the mouse, as you said?") and len(world.presses()) == 1

# 6. A no leaves everything untouched.
for said in ("select squares 1, 4 and 7, then verify", "click the I'm not a robot box", "press verify", "get an audio challenge"):
	world = puzzleWorld()
	world.no = True
	try:
		ask(said)
		raise AssertionError(f"{said}: went on after a no")
	except No:
		pass
	assert len(world.asked) == 1 and world.presses() == [], (said, world.events)

# 7. A number the user did not say is not clicked: a form filled in by a model names squares the request never named.
world = puzzleWorld()
result = ask("select squares 2 and 3", request="help me with this check")
assert result == hc.NO_NUMBERS and world.asked == [] and world.presses() == []
world = puzzleWorld()
result = ask("select squares 2, 3 and 8", request="select squares 2 and 3")
assert world.asked[0].startswith("Click squares 2 and 3 of the check") and len(world.presses()) == 2
for said in ("select all of them", "select every square"):
	world = puzzleWorld()
	assert ask(said) == hc.NO_NUMBERS and world.asked == [] and world.presses() == [], said

# 8. A button of the check, by the name the user said: asked about, pressed with NVDA's own action.
world = puzzleWorld()
result = ask("get an audio challenge")
assert world.asked == ["Press the check's button Get an audio challenge for you?"] and world.presses() == [("press", "Get an audio challenge")]
assert result.startswith("Pressed the check's button Get an audio challenge.") and result.endswith(hc.SHORT_NOTICE), result
world = puzzleWorld()
result = ask("now press next")
assert result.startswith("Nothing was pressed: the check has no button for next that VisionClaw can find.") and world.asked == []
assert "Get a new challenge; Get an audio challenge; Help; Verify" in result and world.presses() == []
# Only in the picture: the button's word is found as text inside the check, and clicked there.
world = puzzleWorld()
world.nodes = None
result = ask("press verify")
assert world.asked == ["Press the check's button VERIFY for you?"] and len(world.presses()) == 1
assert close(world.presses()[0][1:], middle(world.drawing["verify"]), 6), world.presses()

# 9. The check's box: NVDA's own action first; the mouse on the box only if that did nothing; one question.
def boxWorld(works):
	drawing = checkdrawn.boxCheck()
	nodes, found = checkdrawn.turnstilePage()
	made = World(drawing, nodes, found)
	made.place(found["frame"], drawing["frame"])
	made.place(found["box"], drawing["box"])

	def tick(*where):
		found["box"]["states"].append("CHECKED")
		checkdrawn.tickBox(drawing["page"], drawing["box"])
	if works:
		made.onPress[id(found["box"])] = tick
	made.onClick = tick
	return made


world = boxWorld(True)
result = ask("Locate and click the 'Verify you are human' Cloudflare Turnstile checkbox on screen.")
assert world.asked == [
	"Press the check box of Cloudflare's Turnstile, Verify you are human, for you? NVDA's own way is tried first, and the "
	"mouse on the box if that does nothing. These checks are built to be hard for programs, so this may not get through."]
assert world.presses() == [("press", "Verify you are human")], world.presses()
assert result.startswith("Pressed the check's box with NVDA's own action. The check's box is now checked, as NVDA has it."), result
world = boxWorld(False)
result = ask("press the verify you are human box")
assert len(world.asked) == 1 and [event[0] for event in world.presses()] == ["press", "click"], world.presses()
assert close(world.presses()[1][1:], middle(world.drawing["box"])), world.presses()
assert result.startswith("Pressed the check's box with a mouse click on it. The check's box is now checked, as NVDA has it."), result
# Already checked: nothing is asked and nothing is pressed.
world = boxWorld(True)
world.found["box"]["states"].append("CHECKED")
result = ask("click the verify you are human box")
assert result.startswith("Nothing was pressed: the check's box is already checked") and world.asked == [] and world.presses() == []
# No page for NVDA at all: the box is found next to its words in the picture.
world = boxWorld(False)
world.nodes = None
result = ask("click the verify you are human box")
assert len(world.asked) == 1 and len(world.presses()) == 1 and close(world.presses()[0][1:], middle(world.drawing["box"])), world.presses()
assert result.startswith("Pressed the check's box with a mouse click on it."), result
# Words but no box to be found: the click goes just before the words, and that is said.
drawing = checkdrawn.boxCheck(square=False)
world = World(drawing)
result = ask("click the verify you are human box")
assert result.startswith("No box was found in the picture next to the check's words, so VisionClaw clicked just before the words"), result
assert len(world.asked) == 1 and len(world.presses()) == 1 and world.presses()[0][1] < drawing["label"][0] + ORIGIN[0]

# 10. A handle that must be dragged: pointer mode on it, the user drags; nothing is pressed and no button goes down.
drawing = checkdrawn.slider()
world = World(drawing)
world.says = "The handle is at the far left. The empty cut-out is about seven tenths of the way across."
result = ask("Drag the puzzle piece into the missing slot.")
pointerOn = [event for event in world.events if event[0] == "pointer"]
assert len(pointerOn) == 1 and pointerOn[0][1] is not None and world.presses() == [] and world.asked == []
assert world.prompts == [(hc.GAP_PROMPT, world.prompts[0][1])]
assert result.startswith("Pointer mode is on, with the mouse pointer at the start of the line that holds the check's words"), result
assert "this is a guess" in result and "The vision model says of the picture, and a model can be wrong: The handle is at the far left." in result
assert "You drag it; VisionClaw does not." in result
# Where NVDA has the handle, the pointer is put on it, and the width of the check is said in key presses.
world = World(drawing, [checkdrawn.node("DOCUMENT", "Sign in")], {})
frame = checkdrawn.node("INTERNALFRAME", "Slider captcha", world.nodes[0])
handle = checkdrawn.node("SLIDER", "Slide to verify", frame)
world.nodes += [frame, handle]
world.place(frame, drawing["frame"])
world.place(handle, drawing["handle"])
result = ask("take hold of the slider")
pointerOn = [event for event in world.events if event[0] == "pointer"]
assert close(pointerOn[0][1], middle(drawing["handle"])) and "where NVDA has it" in result and "presses of Right Arrow wide" in result

# 11. No check here: said plainly, whatever was asked; nothing is asked of a model and nothing is pressed.
for said in ("what kind of check is this", "describe the squares", "select squares 1 and 2", "click the I'm not a robot box",
		"press verify", "take hold of the slider"):
	world = World(checkdrawn.plain(), checkdrawn.storePage()[0])
	result = ask(said)
	assert result.startswith(hc.NO_CHECK) and world.asked == [] and world.presses() == [] and world.prompts == [], (said, result)
# A grid of pictures on a page that names no check is no check: it is neither described here nor clicked.
for said in ("describe the squares", "select squares 1 and 2"):
	world = World(checkdrawn.puzzle(asks=("Holiday photos",)), checkdrawn.storePage()[0])
	assert hc.squaresIn(world.drawing["page"].image, hc.areasFor((900, 700), [world.drawing["frame"]])) is not None
	result = ask(said)
	assert result.startswith(hc.NO_CHECK) and world.asked == [] and world.presses() == [] and world.prompts == [], (said, result)
# With no page for NVDA at all, the puzzle is found from the words in the picture, described, and worked the same way.
world = puzzleWorld()
world.nodes = None
task = taskModule.Task("what do the squares show, then select squares 2 and 8")
result = tool(task, asked="what do the squares show")
assert "It has 9 squares, 3 rows of 3" in result and len(world.prompts) == 9 and world.presses() == []
tilesNow = list(world.drawing["tiles"])
result = tool(task, asked="select squares 2 and 8")
clicks = [event for event in world.events if event[0] == "click"]
assert len(world.asked) == 1 and len(clicks) == 2 and close(clicks[0][1:], middle(tilesNow[1])) and close(clicks[1][1:], middle(tilesNow[7])), clicks
assert result.startswith("Clicked squares 2 and 8, as you said."), result
# A check that shows only its box has no squares to describe.
world = boxWorld(True)
result = ask("describe the squares")
assert result.startswith("This is Cloudflare's Turnstile.") and hc.NO_SQUARES in result and world.prompts == []

# 12. Whatever is asked, nothing is ever pressed before the user agreed, and never more often than the user named.
for said in ("select squares 1, 4 and 7, then verify", "click 2 and 9 then verify", "press verify", "get an audio challenge",
		"click the I'm not a robot box", "give me a new puzzle", "select square 5"):
	world = puzzleWorld()
	ask(said)
	pressed = world.presses()
	if pressed:
		assert world.events.index(("agree",)) < world.events.index(pressed[0]), said
	assert len(world.asked) <= 1, (said, world.asked)
	named = hc.numbers(said, 9)
	assert len([event for event in pressed if event[0] == "click"]) <= max(1, len(named)), (said, pressed)

# --- The line, guarded: no code that chooses, imitates a hand or leaves the computer ---

FORBIDDEN_NAMES = re.compile(r"solve|answer|auto|pick ?squares|choose ?squares|matching", re.IGNORECASE)
FORBIDDEN_DOCS = re.compile(
	r"by itself|(decides|chooses|picks|selects) (the|which) squares|squares that (fit|match|contain)|human-?like|like a (person|human|hand)",
	re.IGNORECASE)
for module in (hc, checktools):
	source = inspect.getsource(module)
	own = [(name, value) for name, value in vars(module).items()
		if not name.startswith("__") and getattr(value, "__module__", module.__name__) == module.__name__]
	for name, value in own:
		assert not FORBIDDEN_NAMES.search(name), f"{module.__name__}.{name}"
		members = [(name, value)] + ([(f"{name}.{inner}", method) for inner, method in vars(value).items() if callable(method)]
			if inspect.isclass(value) else [])
		for label, member in members:
			assert not FORBIDDEN_NAMES.search(label.split(".")[-1]), f"{module.__name__}.{label}"
			if callable(member) or inspect.isclass(member):
				assert not FORBIDDEN_DOCS.search(inspect.getdoc(member) or ""), f"{module.__name__}.{label}"
	# Nothing random, nothing that waits a varying time, nothing that leaves the computer or runs another program.
	for word in ("import random", "random.", "urllib", "socket", "requests", "http.client", "webbrowser", "subprocess",
			"User-Agent", "userAgent", "bezier", "jitter", "gauss"):
		assert word not in source, f"{module.__name__} has {word}"
assert set(re.findall(r"time\.sleep\(([^)]*)\)", inspect.getsource(checktools))) == {"SETTLE_SECONDS", "BETWEEN_SECONDS"}
# The numbers of squares are only ever read from the words of the step and of the user's request.
uses = re.findall(r"humancheck\.numbers\(([^,]+),", inspect.getsource(checktools))
assert uses and set(uses) == {"asked", "request"}, uses
# The questions to the model that sees are fixed sentences: what a puzzle asks cannot be put into them.
for prompt in (hc.SQUARE_PROMPT, hc.ONE_SQUARE_PROMPT, hc.GAP_PROMPT):
	assert "{" not in prompt and "%s" not in prompt
assert len(re.findall(r"self\.ask\(", inspect.getsource(checktools))) == 3
# Every press in the tool's code stands after a question in the same function.
for method in (checktools.Check.select, checktools.Check.button, checktools.Check.box):
	body = inspect.getsource(method)
	first = min(at for at in (body.find("self._click("), body.find("self._press("), body.find("_pressNode,")) if at >= 0)
	assert 0 <= body.find("self.mustAgree(") < first, method.__name__
assert "mustAgree" not in inspect.getsource(checktools.Check.tell) and "_click" not in inspect.getsource(checktools.Check.describe)
assert "_click" not in inspect.getsource(checktools.Check.hold) and "_press" not in inspect.getsource(checktools.Check.hold)

print("The user guide of the NVDA on this computer was asked for the keys." if guideChecked else "NVDA is not installed here: the keys were not compared with its user guide.")
print("OK")
