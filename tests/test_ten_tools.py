# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The tools of docs/PLAN-ten-scenarios.md that the main parts share, each driven from its request to its answer:
fill_blank on a form that is only a picture, look_picture on a page with pictures, step_through on an installer,
form_trouble where only a red outline says what is wrong, and set_control for a drawn knob that is to show a number.

Plain Python with stand-ins (tests/nvdastandin.py) for NVDA, the mouse, the reading of text in pictures and the
model that sees. The forms and pictures are drawn by tests/drawn.py; the installer, the page and the knob are made
up here. Nothing is clicked or typed on the real computer, and none of this is a run in NVDA.

  python tests/test_ten_tools.py
"""
import sys
import threading
import types

import nvdastandin
import drawn
from PIL import Image, ImageDraw
from visionClaw.claw import guide, images, pictures, target, wizard
from visionClaw.claw import task as taskModule
from visionClaw.claw.tools import ToolError

conf = nvdastandin.conf["visionClaw"]


class SaidNo(Exception):
	"""The user said no."""


# papertools reaches the typing through nvdatools, which needs all of the add-on: a stand-in with what it uses.
typed = []
fakeTools = types.ModuleType("visionClaw.nvdatools")
fakeTools.typeUnicode = typed.append
fakeTools.UserSaidNo = SaidNo
fakeTools.Screen = types.SimpleNamespace(click=lambda result, item: None)
sys.modules["visionClaw.nvdatools"] = fakeTools

from visionClaw import controltools, guidetools, mousetools, ocr, pagetools, papertools, picturetools, wizardtools  # noqa: E402

papertools.SETTLE_SECONDS = picturetools.SCROLL_SETTLE = wizardtools.SETTLE_SECONDS = 0
ORIGIN = (200, 100)
mouse = {"at": (5, 5), "clicks": [], "moves": []}
mousetools.position = lambda: mouse["at"]
mousetools.moveTo = lambda x, y: mouse["moves"].append((x, y))
mousetools.scaleAt = lambda x, y: 1.0
mousetools._onMain = lambda fn, *args: fn(*args)


class Memory:
	def __init__(self, body):
		self.body = body


class Plugin:
	"""The add-on as the tools see it: the screen's pixels, the user's memories and answers, the model that sees."""

	def __init__(self, world):
		self.world = world
		self.memories = types.SimpleNamespace(all=lambda: [Memory(body) for body in world.remembered])
		self.runtime = types.SimpleNamespace(describe=world.describe, oneModel=lambda: False)
		self.asked, self.answers = [], []

	def _grab(self, box=None):
		return self.world.grab(box)

	def clawAsk(self, question, choices):
		self.asked.append((question, list(choices)))
		return self.answers.pop(0) if self.answers else 0

	def clawAskText(self, question):
		self.asked.append((question, None))
		return self.answers.pop(0) if self.answers else ""


class Screen:
	def __init__(self, world):
		self.world = world

	def picture(self, target):
		image = self.world.image()
		return image, (ORIGIN[0], ORIGIN[1], ORIGIN[0] + image.size[0], ORIGIN[1] + image.size[1])

	def box(self, target):
		width, height = self.world.image().size
		return (ORIGIN[0], ORIGIN[1], ORIGIN[0] + width, ORIGIN[1] + height)


class World:
	"""A window whose picture is a page drawn by the test, with what is remembered and what the model says."""

	def __init__(self, page):
		self.page, self.remembered, self.prompts, self.says = page, [], [], "A cat."
		self.reads = True
		self.grabbed = []

	def image(self):
		return self.page.image.copy()

	def grab(self, box=None):
		self.grabbed.append(box)
		image = self.image()
		if box is None:
			return image
		return image.crop((box[0] - ORIGIN[0], box[1] - ORIGIN[1], box[2] - ORIGIN[0], box[3] - ORIGIN[1]))

	def describe(self, jpeg, prompt, tokens, cancel=None, system=None, **more):
		self.prompts.append(prompt)
		return self.says(prompt) if callable(self.says) else self.says


def setUp(page):
	world = World(page)
	plugin = Plugin(world)
	tools = nvdastandin.Tools(plugin, Screen(world))
	del typed[:]
	mouse["clicks"], mouse["moves"] = [], []
	return world, plugin, tools


# --- fill_blank: a form that is only a picture ---

def paperWorld():
	page, where = drawn.paperForm()
	world, plugin, tools = setUp(page)
	tools.register(papertools)

	def recognize(image):
		# The whole window gives the form's own words; a small part gives what was typed there, if it can be read.
		if image.size == page.image.size:
			return page.lines
		if typed and world.reads:
			return [[{"x": 5, "y": 5, "width": 60, "height": 12, "text": word} for word in typed[-1].split()]]
		return []
	ocr.recognize = recognize
	mousetools.click = lambda x, y, *more: mouse["clicks"].append((x, y))
	return world, plugin, tools, where


def inRule(click, rule):
	"""Whether a click landed on a line to write on: a little in from its left end and just above it."""
	x, y = click[0] - ORIGIN[0], click[1] - ORIGIN[1]
	return rule[0] < x < rule[0] + 24 and rule[1] - 12 < y < rule[1]


task = taskModule.Task("test")
world, plugin, tools, where = paperWorld()
world.remembered = ["You like to be called Sam.", "Your name is Josh Kennedy."]
said = tools.call("fill_blank", task, asked="click directly on the blank line next to 'Applicant Full Name,' and type my name")
assert tools.asked == ["Click the line to the right of \"Applicant Full Name\" with the mouse and type \"Josh Kennedy\"?"], tools.asked
assert len(mouse["clicks"]) == 1 and inRule(mouse["clicks"][0], where["nameRule"]), (mouse["clicks"], where["nameRule"])
assert typed == ["Josh Kennedy"] and mouse["moves"][-1] == (5, 5)  # the mouse pointer is put back
assert said == "Clicked the line to the right of \"Applicant Full Name\" and typed \"Josh Kennedy\". The text is now read there in the picture.", said
assert plugin.asked == []  # the name was remembered, so nothing was asked for

# The name is not known: it is asked for, never made up; and with no answer nothing is clicked.
world, plugin, tools, where = paperWorld()
plugin.answers = ["Sam Example"]
said = tools.call("fill_blank", task, asked="click the blank line next to 'Applicant Full Name' and type my name")
assert "What should be typed as your name?" in plugin.asked[0][0] and typed == ["Sam Example"], (plugin.asked, typed)
world, plugin, tools, where = paperWorld()
said = tools.call("fill_blank", task, asked="click the blank line next to 'Applicant Full Name' and type my name")
assert said == "Nothing was clicked: nothing was typed, because nothing was given to type." and mouse["clicks"] == [] and typed == [], said
# Text given in the request is typed as it is; what cannot be read back is said.
world, plugin, tools, where = paperWorld()
world.reads = False
said = tools.call("fill_blank", task, asked="Click the line next to Date of Birth and type 3 March 1990")
assert typed == ["3 March 1990"] and inRule(mouse["clicks"][0], where["birthRule"]) and "could not read the text back" in said, (said, mouse["clicks"])
assert tools.asked == ["Click the dotted line to the right of \"Date of Birth\" with the mouse and type \"3 March 1990\"?"], tools.asked
# A line to sign: clicked, nothing typed, and VisionClaw does not sign.
world, plugin, tools, where = paperWorld()
said = tools.call("fill_blank", task, asked="Find the dotted line labeled 'Authorized Signature' at the bottom of the page and click there so I can place my digital signature.")
assert typed == [] and inRule(mouse["clicks"][0], where["signRule"]), (mouse["clicks"], where["signRule"])
assert said.startswith("Clicked the dotted line above \"Authorized Signature\". VisionClaw does not sign for you"), said
# A label that stands twice: the words say which; where they do not, the user is asked.
world, plugin, tools, where = paperWorld()
said = tools.call("fill_blank", task, asked="click the line labelled Date at the bottom and type today's date")
assert inRule(mouse["clicks"][0], where["dateRule"]) and len(typed) == 1 and typed[0].endswith(", 20" + typed[0][-2:]), (mouse["clicks"], typed)
world, plugin, tools, where = paperWorld()
plugin.answers = [1]
said = tools.call("fill_blank", task, asked="click the line labelled Date and type tomorrow")
assert plugin.asked[0] == ("The words \"Date\" stand in this picture 2 times. Which one do you mean?",
	["Number 1, near the top, on the left", "Number 2, near the bottom"]), plugin.asked
assert inRule(mouse["clicks"][0], where["dateRule"]) and typed == ["tomorrow"]
# A line that is written on already: the question says so.
world, plugin, tools, where = paperWorld()
tools.call("fill_blank", task, asked="click the line next to Email and type sam@example.org")
assert "Something seems to be written on that line already." in tools.asked[0], tools.asked
# The user says no: nothing is clicked and nothing is typed.
world, plugin, tools, where = paperWorld()
tools.no = True
try:
	tools.call("fill_blank", task, asked="Click the line next to Date of Birth and type 3 March 1990")
	raise AssertionError("it went on after a no")
except nvdastandin.Refused:
	assert mouse["clicks"] == [] and typed == []
# A label that is not there, a request that names none, and reading of pictures turned off.
world, plugin, tools, where = paperWorld()
said = tools.call("fill_blank", task, asked="click the blank line next to 'Mother's maiden name' and type Smith")
assert said.startswith("Nothing was clicked: the words \"Mother's maiden name\" were not found") and mouse["clicks"] == [], said
try:
	tools.call("fill_blank", task, asked="click the Next button")
	raise AssertionError("a request that names no line was taken")
except ToolError as e:
	assert "does not say which line or box" in str(e)
conf["useOcr"] = False
said = tools.call("fill_blank", task, asked="Click the line next to Date of Birth and type 3 March 1990")
assert said.startswith("Nothing was clicked: reading text in pictures is turned off") and mouse["clicks"] == [], said
conf["useOcr"] = True
# A printed check box: clicked in its middle; whether the picture changed is said.
world, plugin, tools, where = paperWorld()
said = tools.call("fill_blank", task, asked="check the box next to I agree to the rules of the library in this scanned form")
box = where["agreeBox"]
assert mouse["clicks"] == [(ORIGIN[0] + (box[0] + box[2]) // 2, ORIGIN[1] + (box[1] + box[3]) // 2)], (mouse["clicks"], box)
assert tools.asked == ["Click the check box at \"I agree to the rules of the library\" with the mouse? It looks empty."], tools.asked
assert said.endswith("so the box may not have taken the click."), said
world, plugin, tools, where = paperWorld()
mousetools.click = lambda x, y, *more: (mouse["clicks"].append((x, y)), world.page.square(40, 340, ticked=True))
said = tools.call("fill_blank", task, asked="check the box next to I agree to the rules of the library in this scanned form")
assert said.endswith("The picture of the box changed, so the click was taken."), said

# --- look_picture: one picture of a page, a chat or a gallery ---


class Thing:
	"""A control as NVDA gives it: where it is, and whether it was brought into view."""

	def __init__(self, box, onScroll=None):
		self.location = nvdastandin.Location(*box)
		self.onScroll, self.scrolled = onScroll, 0

	def scrollIntoView(self):
		self.scrolled += 1
		if self.onScroll:
			self.location = nvdastandin.Location(*self.onScroll)


class Document:
	"""A web page as NVDA keeps it: its controls by their numbers."""

	def __init__(self, things, box=None):
		self.things = things
		self.rootNVDAObject = types.SimpleNamespace(
			location=nvdastandin.Location(*(box or (ORIGIN[0], ORIGIN[1], ORIGIN[0] + 900, ORIGIN[1] + 700))), hasIrrelevantLocation=False)

	def getNVDAObjectFromIdentifier(self, first, second):
		return self.things[second]


def onScreen(box):
	return (box[0] + ORIGIN[0], box[1] + ORIGIN[1], box[2] + ORIGIN[0], box[3] + ORIGIN[1])


def chatPage():
	"""A chat drawn here: two little faces, a photo, and a meme with words, in the page's order."""
	page = drawn.Page(900, 700)
	boxes = [(10, 20, 46, 56), (70, 20, 370, 220), (10, 260, 46, 296), (70, 260, 470, 560)]
	names = ["Sam", "IMG_2231.jpg", "Alex", "A dog at a desk"]
	for box, colour in zip(boxes, ((200, 120, 60), (60, 140, 90), (90, 90, 200), (240, 240, 240))):
		page.block(box, colour)
	page.text(90, 280, "I have no idea what I am doing")
	nodes = [{"role": "GRAPHIC", "name": name, "key": (1, index), "states": []} for index, name in enumerate(names)]
	nodes.insert(1, {"role": "LINK", "name": "Sam", "key": (1, 99), "states": []})
	return page, boxes, nodes


page, boxes, nodes = chatPage()
world, plugin, tools = setUp(page)
tools.register(picturetools)
things = {index: Thing(onScreen(box)) for index, box in enumerate(boxes)}
document = Document(things)
pagetools._where = lambda: (document, "Chat", "https://chat.example.org/")
pagetools.pageNodes = lambda task, doc, onMain: nodes
ocr.recognize = lambda image: page.lines if image.size == (400, 300) else []
world.says = lambda prompt: "It says: I have no idea what I am doing." if "Read the text" in prompt else "A dog sits at a desk like an office worker."
said = tools.call("look_picture", task, asked="Read the text inside the latest image posted in this WhatsApp chat and explain the visual joke.")
# The meme was cut out, not the faces and not the photo before it; two questions, each with the rule of its kind.
assert world.grabbed == [onScreen(boxes[3])], world.grabbed
assert len(world.prompts) == 2 and pictures.RULES[pictures.TEXT] in world.prompts[0] and images.JOKE_RULE in world.prompts[1], world.prompts
assert "the page calls it \"A dog at a desk\"" in world.prompts[0] and "I have no idea what I am doing" in world.prompts[0], world.prompts[0]
assert said.startswith("The last picture on this page, which the page calls \"A dog at a desk\": "), said
assert "It says: I have no idea what I am doing." in said and "A dog sits at a desk like an office worker." in said, said
# The first picture, by the words.
world.grabbed, world.prompts = [], []
said = tools.call("look_picture", task, asked="What's in the first photo on this page?")
assert world.grabbed == [onScreen(boxes[1])] and said.startswith("The first picture on this page: "), (world.grabbed, said)
# A picture that is mostly outside the window is brought into view first.
things[3] = Thing(onScreen((70, 660, 470, 960)), onScroll=onScreen(boxes[3]))
world.grabbed = []
tools.call("look_picture", task, asked="describe the last picture in this chat")
assert things[3].scrolled == 1 and world.grabbed == [onScreen(boxes[3])], (things[3].scrolled, world.grabbed)

# A product's photo and a question about its colour: what was measured comes first, for the model and for the user.
shop = drawn.Page(900, 700)
shop.block((300, 60, 700, 560), (250, 250, 250))
shop.block((380, 100, 620, 520), (22, 28, 62))
shop.block((20, 20, 52, 52), (200, 30, 30))
world, plugin, tools = setUp(shop)
tools.register(picturetools)
things = {0: Thing(onScreen((20, 20, 52, 52))), 1: Thing(onScreen((300, 60, 700, 560)))}
document = Document(things)
nodes = [{"role": "GRAPHIC", "name": "logo", "key": (1, 0), "states": []}, {"role": "GRAPHIC", "name": "Storm jacket", "key": (1, 1), "states": []}]
pagetools._where = lambda: (document, "Shop", "https://shop.example.org/")
pagetools.pageNodes = lambda task, doc, onMain: nodes
ocr.recognize = lambda image: []
world.says = "It looks navy."
said = tools.call("look_picture", task, asked="Look at the product photo, is this jacket navy blue or solid black, and does it have any printed logos?")
assert world.grabbed == [onScreen((300, 60, 700, 560))] and len(world.prompts) == 2, (world.grabbed, world.prompts)
assert "Measured from the picture's pixels: leaving out the white background, almost all dark blue" in world.prompts[0], world.prompts[0]
assert "Measured from the picture's pixels" not in world.prompts[1]  # the second question is not about a colour
assert said.startswith("The largest picture on this page, which the page calls \"Storm jacket\": Measured from the picture's pixels:"), said
assert "dark blue is there; black is hardly there" in said and "It looks navy." in said, said

# The photos of a gallery: each is asked the question, and the user is told which answer is whose.
gallery = drawn.Page(900, 700)
rooms = [(20 + 290 * index, 100, 280 + 290 * index, 320) for index in range(3)]
for index, box in enumerate(rooms):
	gallery.block(box, (80 + 40 * index, 120, 160))
world, plugin, tools = setUp(gallery)
tools.register(picturetools)
things = {index: Thing(onScreen(box)) for index, box in enumerate(rooms)}
document = Document(things)
nodes = [{"role": "GRAPHIC", "name": f"Room photo {index + 1}", "key": (1, index), "states": []} for index in range(3)]
pagetools._where = lambda: (document, "Hotel", "https://hotel.example.org/")
pagetools.pageNodes = lambda task, doc, onMain: nodes
answers = iter(["The balcony faces the sea.", "A bed and a desk.", "A bathroom."])
world.says = lambda prompt: next(answers)
said = tools.call("look_picture", task, asked="Look at the room gallery photos and tell me whether the balcony overlooks the ocean or the mountains.")
assert world.grabbed == [onScreen(box) for box in rooms], world.grabbed
assert said.splitlines()[0] == "Picture 1 of 3 on this page, which the page calls \"Room photo 1\": The balcony faces the sea.", said
assert said.splitlines()[2].startswith("Picture 3 of 3 on this page") and len(said.splitlines()) == 3, said

# No web page: the pictures the program's window tells NVDA about. None there either: a photo found in the pixels.
from visionClaw import fixruntime, imaging  # noqa: E402

page, boxes, nodes = chatPage()
world, plugin, tools = setUp(page)
tools.register(picturetools)
pagetools._where = lambda: None
windowNodes = [{"role": "GRAPHIC", "name": "", "obj": Thing(onScreen(boxes[1])), "states": []}, {"role": "GRAPHIC", "name": "A dog at a desk", "obj": Thing(onScreen(boxes[3])), "states": []}]
fixruntime.windowNodes = lambda root, *more: iter(windowNodes)
world.says = "A dog."
said = tools.call("look_picture", task, asked="what is in the photo my friend just sent")
assert world.grabbed == [onScreen(boxes[3])] and said == "The last picture in this window, which the program calls \"A dog at a desk\": A dog.", (world.grabbed, said)
fixruntime.windowNodes = lambda root, *more: iter(())
found = {"calls": []}
imaging.findPhoto = lambda image: found["calls"].append(image.size) or ((70, 10, 470, 310) if image.size[1] == 350 else None)
world.grabbed = []
said = tools.call("look_picture", task, asked="what is in the photo my friend just sent")
# The newest picture of a chat is looked for in the lower half of the window first.
assert found["calls"] == [(900, 350)] and said == "The picture found in the lower part of this window: A dog.", (found["calls"], said)
imaging.findPhoto = lambda image: None
said = tools.call("look_picture", task, asked="what is in the photo my friend just sent")
assert said == images.NOT_FOUND
try:
	tools.call("look_picture", task, asked="Make NVDA talk faster")
	raise AssertionError("a request that names no picture was taken")
except ToolError as e:
	assert str(e) == images.NO_WISH

# --- step_through: an installer, page after page ---

T = guide.Thing


class Installer:
	"""A made-up installer: pages of things; pressing a check box sets it, the page's button goes on."""

	def __init__(self, pages):
		self.pages, self.at, self.pressed, self.program = pages, 0, [], "setup"

	def look(self, task, onMain, screen):
		title, things = self.pages[self.at]
		return list(things), title, self.program

	def press(self, task, thing, onMain):
		self.pressed.append(thing.name)
		if thing.kind == "check box":
			thing.checked = not thing.checked
		elif thing.kind == "radio button":
			thing.checked = True
		elif self.at < len(self.pages) - 1:
			self.at += 1


def installer():
	return Installer([
		("Setup - Welcome", [T("Next >", "button"), T("Cancel", "button")]),
		("Setup - Additional Tasks", [
			T("Create a desktop shortcut", "check box", checked=True), T("Install the Ask Toolbar", "check box", checked=True),
			T("Next >", "button"), T("Cancel", "button")]),
		("Setup - Ready to Install", [T("< Back", "button"), T("Install", "button"), T("Cancel", "button")]),
		("Setup - Installing", [T("Cancel", "button")]),
	])


world, plugin, tools = setUp(drawn.Page(100, 100))
tools.register(wizardtools)
setup = installer()
guidetools.lookAt, guidetools.pressThing = setup.look, setup.press
guidetools.inFront = lambda: ("setup", "Setup - Welcome")
guidetools.ownWindow = lambda: False
request = "Uncheck any bundled promotional toolbars in this installer and click Next until the installation starts."
said = tools.call("step_through", task, asked=request)
# Asked once before anything is pressed, whatever the settings say; then page after page.
assert tools.asked == [wizard.startQuestion(wizard.wish(request), "Setup - Welcome")], tools.asked
assert setup.pressed == ["Next >", "Install the Ask Toolbar", "Next >", "Install"], setup.pressed
assert "Press Install?" in plugin.asked[0][0] and "unchecked Install the Ask Toolbar; pressed Next >." in said, (plugin.asked, said)
assert said.endswith("pressed Install, as you said. The window now says that it is under way. VisionClaw stops here."), said
# A no to the first question: nothing is pressed.
setup = installer()
guidetools.lookAt, guidetools.pressThing = setup.look, setup.press
tools.no = True
try:
	tools.call("step_through", task, asked=request)
	raise AssertionError("it went on after a no")
except nvdastandin.Refused:
	assert setup.pressed == []
tools.no = False
# VisionClaw's own windows are never gone through, and a request that names no button is not taken.
guidetools.ownWindow = lambda: True
assert tools.call("step_through", task, asked=request) == guide.NOT_OWN and setup.pressed == []
guidetools.ownWindow = lambda: False
try:
	tools.call("step_through", task, asked="click the Next button")
	raise AssertionError("one click was taken for a walk")
except ToolError as e:
	assert str(e) == wizard.NO_WISH

# --- form_trouble: where only a red outline says which field is wrong ---

form, fields = drawn.webForm(wrong=(1, 3))
world, plugin, tools = setUp(form)
tools.screen = None
pagetools.register(tools.add, plugin, tools.text, tools.onMain)
things = {index: Thing(onScreen(box)) for index, box in enumerate(fields)}
document = Document(things, (ORIGIN[0], ORIGIN[1], ORIGIN[0] + form.image.size[0], ORIGIN[1] + form.image.size[1]))
labels = ("First name", "Email address", "Phone number", "Postcode")
nodes = [{"role": "EDITABLETEXT", "name": label, "key": (1, index), "states": [], "start": 10 * index + 5} for index, label in enumerate(labels)]
pagetools._where = lambda: (document, "Sign up", "https://example.org/")
pagetools.pageNodes = lambda task, doc, onMain: nodes
moved = []
pagetools._moveTo = lambda doc, node: moved.append(node["name"])
ocr.recognize = lambda image: form.lines
said = tools.call("form_trouble", task)
assert "In the picture of the page, 2 fields are outlined in red" in said and "Email address" in said and "Postcode" in said, said
assert "First name" not in said.split("outlined in red")[1].split(".")[0], said
assert moved == ["Email address"] and "NVDA's reading position is now on the first of them, Email address." in said, (moved, said)
assert "Written in red in the picture: Please check this field." in said and "measured from the colours of the 4 fields" in said, said
# Nothing is outlined in red: that is said, and the reading position stays where it is.
form, fields = drawn.webForm(wrong=())
world.page = form
moved = []
pagetools._moveTo = lambda doc, node: moved.append(node["name"])
ocr.recognize = lambda image: form.lines
said = tools.call("form_trouble", task)
assert moved == [] and "No field on the screen is outlined in red and nothing is written in red there." in said, said
# What the page itself marks comes first, as before: then the picture is not measured at all.
nodes[2]["states"] = ["INVALID_ENTRY"]
world.grabbed = []
said = tools.call("form_trouble", task)
assert moved == ["Phone number"] and "is marked as not valid" in said and world.grabbed == [] and "outlined in red" not in said, (moved, said)

# --- set_control: a drawn knob that is to show a number ---


class Knob:
	def __init__(self, value):
		self.value, self.strokes, self.stopped = value, [], 0
		self._lock = threading.Lock()

	def _box(self):
		return (ORIGIN[0], ORIGIN[1], ORIGIN[0] + 400, ORIGIN[1] + 300)

	def start(self, control):
		self.control = control
		return True, ""

	def stop(self, say=True):
		self.stopped += 1

	def _readLines(self, box):
		return ["Gain 12 dB", f"Mix {self.value:g}%"]

	def _stroke(self, box, direction, size):
		before = self.value
		self.value = max(0, min(100, self.value + direction * {target.FINE: 1, target.STEP: 4, target.FAR: 16}[size]))
		self.strokes.append((direction, size))
		return self.value != before


world, plugin, tools = setUp(drawn.Page(400, 300))
knob = Knob(80)
plugin.controlKeys = knob
items = [
	{"kind": "text", "text": "Mix", "plain": "Mix", "box": (100, 100, 130, 115)}, {"kind": "icon", "name": "", "text": "", "box": (95, 120, 135, 160)},
	{"kind": "text", "text": "Gain", "plain": "Gain", "box": (200, 100, 235, 115)}]
info = types.SimpleNamespace(convertXToScreen=lambda x: x + ORIGIN[0], convertYToScreen=lambda y: y + ORIGIN[1])
tools.screen = types.SimpleNamespace(items=lambda: types.SimpleNamespace(items=items, imageInfo=info, web=False))
controltools._nodes = lambda: []
controltools.register(tools.add, plugin, tools.text, tools.onMain, tools.confirm, tools.screen)
said = tools.call("set_control", task, asked="Turn the graphical Mix knob down to 35 percent")
assert tools.asked == [target.question("Mix", 35, True)], tools.asked
assert knob.value == 35 and knob.stopped == 1, (knob.value, knob.stopped)
assert said.startswith("Mix now shows 35 percent, which is what was asked for. It showed 80 percent before."), said
# The knob was taken hold of at the drawn thing under its name, not at the name.
assert knob.control["name"] == "Mix", knob.control
# With reading of pictures turned off the number cannot be read, and that is said before anything is moved.
conf["useOcr"] = False
knob = Knob(80)
plugin.controlKeys = knob
try:
	tools.call("set_control", task, asked="Turn the Mix knob down to 35 percent")
	raise AssertionError("a number was set without reading it")
except ToolError as e:
	assert "reading text in pictures is turned off" in str(e) and knob.strokes == []
conf["useOcr"] = True
# The user says no: the knob is not touched.
knob = Knob(80)
plugin.controlKeys = knob
tools.no = True
try:
	tools.call("set_control", task, asked="Turn the Mix knob down to 35 percent")
	raise AssertionError("it went on after a no")
except nvdastandin.Refused:
	assert knob.strokes == [] and knob.value == 80

print("OK")
