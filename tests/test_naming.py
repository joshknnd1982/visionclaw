# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Object names (claw/naming.py, nametools.py): every role of NVDA sorted, which names are vague, which objects are
named, what tells an object apart, how sure a name is, the names kept and shared; and the NVDA side driven with
stand-ins: an object reached by the focus or object navigation, a control of a page in browse mode, a name the user
gives, names turned off, and a model that gives no name. The model, the screen and the reading of text in pictures
are stand-ins; nothing here ran in NVDA.

  python tests/test_naming.py
"""
import json
import os
import sys
import tempfile
import types

# A stand-in for wx that runs what is handed to the main thread at once.
_wx = types.ModuleType("wx")
_wx.CallAfter = lambda fn, *args, **kwargs: fn(*args, **kwargs)
_wx.CallLater = lambda ms, fn, *args, **kwargs: fn(*args, **kwargs)
_wx.IsMainThread = lambda: True
sys.modules["wx"] = _wx

import nvdastandin  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from visionClaw.claw import naming  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Every role of NVDA is sorted, once ---

with open(os.path.join(ROOT, "tests", "nvda_objects.json"), encoding="utf-8") as f:
	objects = json.load(f)
roles = objects["roles"]
assert len(roles) == 156 and objects["nvda"] == "2026.3.1", (len(roles), objects["nvda"])
for role in roles:
	assert naming.known(role), f"NVDA's role {role} is not sorted in claw/naming.py"
	assert (role in naming.NAMED) + (role in naming.WHEN_CLICKABLE) + (role in naming.LEFT) == 1, role
for role in naming.NAMED | naming.WHEN_CLICKABLE | naming.LEFT:
	assert role in roles, f"{role} is no role of NVDA {objects['nvda']}"
for state in naming.CLICKABLE_STATES | naming.UNSEEN_STATES:
	assert state in objects["states"], state
assert len(objects["states"]) == 53 and "CLICKABLE" in objects["states"]
# The list for the owner says the same.
listText = open(os.path.join(ROOT, "docs", "NVDA-OBJECTS.md"), encoding="utf-8").read()
assert "## Roles: 156 kinds of object" in listText and "## States: 53" in listText
for heading in ("### Object navigation", "### Text review", "### Browse mode quick navigation", "### System focus",
		"### Mouse", "### Tables in documents"):
	assert heading in listText, heading

# --- Vague names ---

for name, role in (
		("", "BUTTON"), ("   ", "LINK"), ("button", "BUTTON"), ("btnClose", "BUTTON"), ("button1", "BUTTON"),
		("ic_settings_24", "BUTTON"), ("X", "BUTTON"), ("+", "BUTTON"), ("", "BUTTON"), ("⚙", "BUTTON"),
		("icon_close.svg", "GRAPHIC"), ("image", "GRAPHIC"), ("logo", "GRAPHIC"), ("IMG_4021", "GRAPHIC"),
		("https://example.com/a.png", "LINK"), ("edit", "EDITABLETEXT"), ("unlabeled", "BUTTON"),
		("3f2a9c1b7d4e8f60a1b2", "GRAPHIC")):
	assert naming.vague(name, role), (name, role)
for name, role in (
		("Edit", "BUTTON"), ("Picture", "BUTTON"), ("Download", "BUTTON"), ("OK", "BUTTON"), ("Go", "BUTTON"),
		("iPhone", "LINK"), ("eBay", "LINK"), ("None", "RADIOBUTTON"), ("Search", "EDITABLETEXT"),
		("Company logo", "GRAPHIC"), ("Clear", "BUTTON"), ("A", "STATICTEXT"), ("Password", "PASSWORDEDIT"),
		("Menu", "MENUBUTTON"), ("Search", "COMBOBOX"), ("Email address", "EDITABLETEXT")):
	assert not naming.vague(name, role), (name, role)

# --- Truly unlabelled: what the interfaces give is a label, however short or odd ---
# The owner said on 2026-11-19: object names named buttons and objects that Windows' and the browsers' accessibility
# interfaces already name; only the truly unlabelled may be named.

for name, role in (
		("", "BUTTON"), ("   ", "LINK"), ("", "BUTTON"), ("​", "BUTTON"), (" ‍", "LINK"),
		("button", "BUTTON"), ("Button", "BUTTON"), ("btn", "BUTTON"), ("link", "LINK"), ("check box", "CHECKBOX"),
		("edit", "EDITABLETEXT"), ("undefined", "BUTTON"), ("null", "LINK"), ("unlabeled", "BUTTON"),
		("[object Object]", "BUTTON"), ("IMG_4021.jpg", "GRAPHIC"), ("image", "GRAPHIC"), ("Image 3", "GRAPHIC"),
		("https://example.com/a.png", "GRAPHIC"), ("3f2a9c1b7d4e8f60a1b2", "BUTTON"), ("spacer", "GRAPHIC")):
	assert naming.unlabelled(name, role), (name, role)
for name, role in (
		("2", "LINK"), ("A", "LINK"), ("X", "BUTTON"), ("Q", "BUTTON"), ("7", "BUTTON"), ("+", "BUTTON"),
		("×", "BUTTON"), ("⚙", "BUTTON"), ("😀", "BUTTON"), ("…", "BUTTON"), ("IMG_4021.jpg", "LISTITEM"),
		("photo.jpg", "DESKTOPICON"), ("report.pdf", "LISTITEM"), ("btnClose", "BUTTON"), ("button1", "BUTTON"),
		("ic_settings_24", "BUTTON"), ("Untitled", "LISTITEM"), ("Untitled document", "LINK"), ("Logo", "GRAPHIC"),
		("Company logo", "GRAPHIC"), ("Text", "EDITABLETEXT"), ("Password", "PASSWORDEDIT"), ("Menu", "MENUBUTTON"),
		("Edit", "BUTTON"), ("Picture", "BUTTON"), ("Download", "GRAPHIC"), ("https://example.com", "LINK"),
		("3f2a9c1b7d4e8f60a1b2", "LISTITEM"), ("Search", "EDITABLETEXT"), ("OK", "BUTTON")):
	assert not naming.unlabelled(name, role), (name, role)
# A label from elsewhere: a description, the hint in an empty field, the object that labels it.
assert naming.labelled("", "EDITABLETEXT", ["", "Search the site"])
assert naming.labelled("", "BUTTON", ["Opens the settings", ""])
assert not naming.labelled("", "BUTTON", ["", "", None])
assert naming.interfaceName("EDITABLETEXT", label="Quantity") == "Quantity"
assert naming.interfaceName("BUTTON", inside="Save") == "Save", "a button's words inside it, as browse mode reads them"
assert naming.interfaceName("PANE", inside="Save") == "", "a pane is not named by what it holds"
assert naming.interfaceName("BUTTON", label="", inside="") == ""
# A model's name without the kind NVDA says itself after it; a state is part of a name.
assert naming.withoutKind("Search field", "EDITABLETEXT") == "Search"
assert naming.withoutKind("Shuffle toggle button", "TOGGLEBUTTON") == "Shuffle"
assert naming.withoutKind("Delete selected", "BUTTON") == "Delete selected"
assert naming.withoutKind("Button", "BUTTON") == "Button", "nothing is taken where nothing would be left"
assert naming.decide("Search field", "", "", "EDITABLETEXT") == ("Search", False)

# --- Which objects are named ---

assert not naming.wanted("LINK", [], "2"), "a page number is a label"
assert not naming.wanted("LISTITEM", ["FOCUSABLE"], "IMG_4021.jpg"), "a file in a list of files is named by its file"
assert not naming.wanted("TABLECELL", ["FOCUSABLE", "FOCUSED"], ""), "an empty cell of a spreadsheet is no control"
assert naming.wanted("TABLECELL", ["CLICKABLE"], ""), "an empty cell made to be pressed is"
assert not naming.wanted("LIST", ["FOCUSABLE"], "") and not naming.wanted("DOCUMENT", ["FOCUSED"], "")
assert naming.wanted("LISTITEM", ["FOCUSABLE"], ""), "a picture in a gallery list"
assert not naming.wanted("PANE", ["FOCUSABLE"], "", holds=True), "a pane that holds objects: those are named"
assert not naming.wanted("LISTITEM", ["FOCUSABLE"], "", text="Blue shirt"), "the words inside it"
assert not naming.wanted("EDITABLETEXT", ["FOCUSABLE"], "", others=["", "Search the site"]), "the hint in the field"
assert not naming.wanted("BUTTON", ["FOCUSABLE"], "", others=["Close the window", ""]), "its description"
assert not naming.wanted("EDITABLETEXT", ["FOCUSABLE"], "", others=["", "", "Quantity"]), "the object that labels it"
assert naming.wanted("BUTTON", ["FOCUSABLE"], ""), "only the picture of an icon font"
assert naming.wanted("BUTTON", ["FOCUSABLE"], "")
assert naming.wanted("GRAPHIC", [], "photo_123.jpg")
assert not naming.wanted("BUTTON", ["FOCUSABLE"], "Save")
assert not naming.wanted("HEADING2", [], "")
assert not naming.wanted("BUTTON", ["INVISIBLE"], "")
assert not naming.wanted("BUTTON", [], "", hidden=True)
assert not naming.wanted("SECTION", [], ""), "a box that cannot be pressed holds things; it is not named"
assert naming.wanted("SECTION", ["CLICKABLE"], "")
assert not naming.wanted("SECTION", ["CLICKABLE"], "", text="Read the article")
assert naming.wanted("PANE", ["FOCUSED", "FOCUSABLE"], "")
assert not naming.wanted("LINK", [], "", text="Home"), "a link with words in it is named by them"
assert naming.wanted("LINK", [], "", text="")

# --- What tells an object apart ---

assert naming.ruleFor({"role": "BUTTON", "ident": "search-button"}) == {"role": "BUTTON", "ident": "search-button"}
assert naming.ruleFor({"role": "BUTTON", "ident": ":r1a:"}) is None, "an id made at random tells nothing"
assert naming.ruleFor({"role": "BUTTON", "autoId": "SettingsButton"})["autoId"] == "SettingsButton"
assert naming.ruleFor({"role": "GRAPHIC", "src": "close.svg"}) == {"role": "GRAPHIC", "src": "close.svg"}
assert naming.ruleFor({"role": "BUTTON", "cls": ["icon-button"]}) is None, "class names are shared by unrelated controls"
assert naming.ruleFor({"role": "BUTTON", "controlId": 1001, "windowClass": "Button"}) is None
assert naming.ruleFor({"role": "BUTTON", "controlId": 1001, "windowClass": "Button"}, "Options")["dialog"] == "Options"
key = naming.ruleKey({"role": "BUTTON", "ident": "x-close"})
assert key.startswith(naming.RULE) and naming.checkKey(key)
assert naming.webScope("https://www.example.com/a?b") == "site:example.com" and naming.webScope("") is None
assert naming.placeWords("site:example.com") == "the website example.com"

# --- How sure a name is ---

assert naming.sure("Settings", code="settings") and naming.sure("Play", code="play pause")
assert naming.sure("Save", read="Save") and naming.sure("Save as", read="Save As")
assert not naming.sure("Settings"), "a name from an icon alone is probable"
assert not naming.sure("Save", read="Total amount due this month")
assert naming.decide("Settings", "", "settings") == ("Settings", True)
assert naming.decide("Settings", "", "") == ("Settings", False)
assert naming.decide("", "Save", "") == ("Save", False), "the text in the picture, where the model gave nothing"
assert naming.decide("", "", "close") == ("Close", False)
assert naming.decide("", "#@!", "") == ("", False)
# A model's name that is itself vague is no name (Qwen3.5 4B on a field with nothing around it, 2026-11-19).
assert naming.decide("Edit field", "", "", "EDITABLETEXT") == ("", False)
assert naming.decide("Button", "", "", "BUTTON") == ("", False)
assert naming.decide("Edit", "", "", "BUTTON") == ("Edit", False), "an Edit button is a real name"
assert naming.spoken({"name": "Play", "by": naming.MODEL, "sure": False}) == "probably Play"
assert naming.spoken({"name": "Play", "by": naming.MODEL, "sure": True}) == "Play"
assert naming.spoken({"name": "Mute", "by": naming.YOU, "sure": True}) == "Mute"
assert naming.spoken({"name": "Mute", "by": naming.PERSON, "sure": False}) == "Mute"
assert naming.spoken({"name": "Play", "by": naming.MODEL}, "vermutlich {name}") == "vermutlich Play"

# --- The question and the picture ---

assert naming.question("BUTTON").startswith("The picture shows one button that has no name.")
assert naming.question("EDITABLETEXT").startswith("The picture shows one edit field that has no name.")
# The space before a narrow field is as wide as for a wide one: its label is there too ("Quantity" was cut).
assert naming.pictureBox("SPINBUTTON", (140, 46, 220, 74))[0] == 140 - 28 * 8
assert naming.pictureBox("BUTTON", (100, 100, 120, 120)) == (95, 95, 125, 125)
field = naming.pictureBox("EDITABLETEXT", (300, 200, 500, 220), (0, 0, 1000, 800))
assert field[0] == 140 and field[1] == 180 and field[2] > 500, field
assert naming.pictureBox("BUTTON", (0, 0, 20, 20), (0, 0, 800, 600))[:2] == (0, 0)

# --- Said once: a small model is best ---

text = naming.firstTimeText("Qwen3.5 9B", "vision model")
assert text.startswith("This is said once") and "7B or smaller" in text and "Qwen3.5 9B" in text and "NVDA+Alt+M" in text
assert "Qwen3.5 2B" not in naming.firstTimeText("Qwen3.5 2B") and "is larger" not in naming.firstTimeText("Qwen3.5 2B")
assert "The model you use now" in naming.firstTimeText("Qwen3.5 9B", "model"), "one model is never called two"
assert naming.billions("Qwen3.5 0.8B") == 0.8 and naming.billions("Qwen3-VL 2B (already on this computer)") == 2

# --- Browse mode: which controls of a stretch need a name ---


class Command:
	def __init__(self, command, field):
		self.command, self.field = command, field


class Role:
	def __init__(self, name):
		self.name = name


def start(role, name="", **more):
	field = {"role": Role(role), "name": name, "states": set(), "controlIdentifier_docHandle": "7",
		"controlIdentifier_ID": str(more.pop("ID", 1))}
	field.update(more)
	return Command("controlStart", field)


def end():
	return Command("controlEnd", None)


stretch = [
	start("BUTTON", "Back", ID=1), "Back", end(),
	start("LINK", "", ID=2), start("GRAPHIC", "", ID=3, **{"IAccessible2::attribute_src": "https://x.com/home.svg"}), end(), end(),
	start("BUTTON", "", ID=4), "", end(),
	start("LINK", "", ID=5), "Read more about it", end(),
	start("BUTTON", "Forward", ID=6), "Forward", end(),
]
found = naming.candidates(stretch, limit=5)
assert [f[0]["controlIdentifier_ID"] for f in found] == ["2", "4"], [f[0]["controlIdentifier_ID"] for f in found]
assert found[0][2] == [("button", "Back")], found[0][2]
assert ("button", "Forward") in found[1][3], found[1][3]
assert len(naming.candidates(stretch, limit=1)) == 1
# What the page tells NVDA is a label: page numbers, letters, a field's hint, a description; and a picture deep inside a
# link is part of the link.
labelledStretch = [
	start("LINK", "2", ID=11), "2", end(),
	start("LINK", "", ID=12), "A", end(),
	start("EDITABLETEXT", "", ID=13, placeholder="Search the site"), end(),
	start("EDITABLETEXT", "", ID=14, **{"IAccessible2::attribute_placeholder": "Email"}), "me@example.com", end(),
	start("BUTTON", "", ID=15, description="Close the window"), "", end(),
	start("LINK", "Home", ID=16), start("SECTION", "", ID=17), start("GRAPHIC", "", ID=18), end(), end(), "Home", end(),
	start("TABLECELL", "", ID=19, states=[Role("FOCUSABLE")]), end(),
]
assert naming.candidates(labelledStretch, limit=10) == [], [f[0]["controlIdentifier_ID"] for f in naming.candidates(
	labelledStretch, limit=10)]
assert [f[0]["controlIdentifier_ID"] for f in naming.candidates(
	[start("BUTTON", "", ID=20), "", end(), start("EDITABLETEXT", "", ID=21), end()], limit=5)] == ["20", "21"]

# --- The names kept ---

folder = tempfile.mkdtemp(prefix="vc-names-")
path = os.path.join(folder, "labels.json")
# A file as VisionClaw 1.12 wrote it is read as it is.
with open(path, "w", encoding="utf-8") as f:
	json.dump({"spotify": {"user": {"a" * 20: "Shuffle"}, "guess": {"b" * 20: "Repeat"}}}, f)
store = naming.NameStore(path)
assert store.get("spotify", "a" * 20) == ("Shuffle", True)
assert store.get("spotify", "b" * 20) == ("Repeat", False)
assert store.entry("spotify", "b" * 20) == {"name": "Repeat", "by": naming.MODEL, "sure": False, "role": ""}
version = store.version
assert not store.setGuess("spotify", "a" * 20, "Random"), "a model never replaces the user's name"
assert store.setGuess("spotify", "c" * 20, "Like", sure=True, role="BUTTON")
assert store.version > version
store.setUser("spotify", "c" * 20, "Heart")
assert store.entry("spotify", "c" * 20)["by"] == naming.YOU
store.setGuess("site:example.com", "d" * 20, "Menu", by=naming.PERSON)
assert not store.setGuess("site:example.com", "d" * 20, "Hamburger"), "a model never replaces a person's name"
assert store.save()
again = naming.NameStore(path)
assert again.get("spotify", "c" * 20) == ("Heart", True) and again.entry("site:example.com", "d" * 20)["by"] == naming.PERSON
# An older VisionClaw finds what it knows where it always was.
raw = json.load(open(path, encoding="utf-8"))
assert raw["spotify"]["user"]["c" * 20] == "Heart" and raw["spotify"]["guess"]["b" * 20] == "Repeat"
assert [scope for scope, _count in again.places()] == ["spotify", "site:example.com"]
assert [entry["name"] for _key, entry in again.entries("spotify")] == ["Heart", "Repeat", "Shuffle"]
assert again.forget("spotify", "b" * 20) and again.entry("spotify", "b" * 20) is None
setUserEmpty = again.setUser("spotify", "a" * 20, "")
assert again.entry("spotify", "a" * 20) is None
assert naming.describe({"by": naming.MODEL, "sure": False}) == "guessed by the model, said with probably"
# A name the user asked the model for is said even over a label, and a name the model gives by itself never replaces it.
asking = naming.NameStore(os.path.join(folder, "asked.json"))
assert not asking.overriding() and not asking.overriding("notepad")
assert asking.setGuess("notepad", "h" * 20, "Close", role="BUTTON", asked=True)
assert asking.entry("notepad", "h" * 20) == {"name": "Close", "by": naming.MODEL, "sure": False, "role": "BUTTON",
	"asked": True}
assert naming.overrides(asking.entry("notepad", "h" * 20)) and asking.overriding("notepad") and asking.overriding()
assert not asking.overriding("spotify")
assert not asking.setGuess("notepad", "h" * 20, "Exit"), "a name the model gives by itself never replaces an asked one"
assert asking.setGuess("notepad", "h" * 20, "Quit", asked=True), "asked again, the new answer is kept"
assert asking.setGuess("notepad", "i" * 20, "Play") and not naming.overrides(asking.entry("notepad", "i" * 20))
assert naming.describe(asking.entry("notepad", "h" * 20)) == "asked for by you, guessed by the model, said with probably"
assert asking.save() and naming.NameStore(os.path.join(folder, "asked.json")).entry("notepad", "h" * 20)["asked"]
asking.forget("notepad", "h" * 20)
assert not asking.overriding("notepad")

# --- Sharing ---

shared = again.shared(["spotify", "site:example.com"], maker="VisionClaw 1.13.0")
assert shared["visionclaw-names"] == naming.SHARE_FORMAT and {n["by"] for n in shared["names"]} == {naming.PERSON}
assert {n["name"] for n in shared["names"]} == {"Heart", "Menu"}
other = naming.NameStore(os.path.join(folder, "other.json"))
other.setUser("spotify", "c" * 20, "Love it")
other.setGuess("site:example.com", "d" * 20, "Lines")
added, replaced, kept = other.addShared(json.dumps(shared).encode("utf-8"))
assert (added, replaced, kept) == (0, 1, 1), (added, replaced, kept)
assert other.entry("spotify", "c" * 20)["name"] == "Love it", "a shared name never replaces the user's own"
assert other.entry("site:example.com", "d" * 20) == {"name": "Menu", "by": naming.PERSON, "sure": False, "role": ""}
for bad in (b"not json", b"[]", json.dumps({"visionclaw-names": 2, "names": []}).encode()):
	try:
		other.addShared(bad)
		raise AssertionError(bad)
	except ValueError:
		pass
# What does not fit is left out, never used: code in a key, a long name, an unknown fact, a place that is no name.
checked = naming.readShared({"visionclaw-names": 1, "names": [
	{"place": "notepad", "key": "e" * 20, "name": "Bold", "by": "person"},
	{"place": "notepad", "key": "rule:" + json.dumps({"role": "BUTTON", "exec": "x"}), "name": "Bad"},
	{"place": "notepad", "key": "rule:" + json.dumps({"role": "BUTTON", "ident": "close-x"}), "name": "Close"},
	{"place": "../../etc", "key": "f" * 20, "name": "Bad"},
	{"place": "notepad", "key": "__import__('os')", "name": "Bad"},
	{"place": "notepad", "key": "9" * 20, "name": "x" * 500},
	{"place": "notepad", "key": "8" * 20, "name": "image", "role": "GRAPHIC"},
	{"place": "notepad", "key": "g" * 20, "name": "Not a picture key"},
	"not an entry",
]})
assert [c["name"] for c in checked] == ["Bold", "Close", "x" * naming.MAX_NAME], [c["name"] for c in checked]
assert checked[0]["by"] == naming.PERSON and checked[1]["by"] == naming.MODEL

# --- The NVDA side, with stand-ins ---

api = sys.modules["api"]
sys.modules["config"].conf["visionClaw"].update({"detailSize": 448})


class Location(tuple):
	def __new__(cls, left, top, width, height):
		return super().__new__(cls, (left, top, width, height))

	width = property(lambda self: self[2])
	height = property(lambda self: self[3])


class Base:
	"""A stand-in for NVDAObject: its own classes give it a name; the name is asked through _get_name."""

	def _get_name(self):
		return ""

	name = property(lambda self: self._get_name())


sys.modules["NVDAObjects"].NVDAObject = Base

from visionClaw import labels, nametools  # noqa: E402
from visionClaw.claw import task as taskModule  # noqa: E402


class State:
	def __init__(self, name):
		self.name = name


class Thing(Base):
	"""A control of a program, with what NVDA would know of it."""

	def __init__(self, role, ownName="", place=(100, 100, 24, 24), autoId="", app="spotify", handle=1, states=("FOCUSABLE",)):
		self.role, self.ownName, self.location = Role(role), ownName, Location(*place)
		self.UIAAutomationId, self.windowHandle = autoId, handle
		self.appModule = types.SimpleNamespace(appName=app)
		self.states = [State(s) for s in states]
		self.treeInterceptor = None
		self.IA2UniqueID = None
		self.UIAElement = None
		self.IAccessibleChildID = 0
		self.previous = self.next = self.parent = None

	def _get_name(self):
		return self.ownName

	def __eq__(self, other):
		return isinstance(other, Thing) and other.location == self.location and other.windowHandle == self.windowHandle

	__hash__ = object.__hash__


said, beeps, asked, ocrRead = [], [], [], {"text": ""}


class Model:
	"""The model that sees: what it answers for the next questions."""
	answers = []


class FakeLLM:
	def __init__(self, runtime, task):
		self.task = task

	def json(self, role, system, user, schema, maxTokens=300, reasoning=None, image=None):
		asked.append(user)
		self.task.check()
		answer = Model.answers.pop(0) if Model.answers else "unknown"
		if answer == "STOP":
			self.task.cancel.set()
			self.task.check()
		return {"name": answer}


nametools.LLM = FakeLLM
nametools.ocr = types.SimpleNamespace(
	recognize=lambda image: [[{"text": word}] for word in ocrRead["text"].split()] if ocrRead["text"] else None,
	linesText=lambda lines: " ".join(word["text"] for line in lines for word in line))
api.getForegroundObject = lambda: types.SimpleNamespace(role=Role("WINDOW"), name="Spotify Premium",
	location=Location(0, 0, 1000, 800))
api.getMouseObject = lambda: None


class Plugin:
	def __init__(self, store):
		self.labels = store
		self.dataDir = folder
		self.runtime = types.SimpleNamespace(entry=lambda role: {"name": "Qwen3.5 2B", "small": True})
		self.board = None
		self.jobs = []

	def _dataReady(self):
		return True

	def _grabOrReport(self, box, quiet=False):
		image = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), "white")
		ImageDraw.Draw(image).ellipse((4, 4, image.width - 4, image.height - 4), outline=(box[0] % 255, 0, 0), width=2)
		return image

	def _queueBackground(self, job, key, first=False):
		self.jobs.append(job)
		return True

	def run(self):
		while self.jobs:
			job = self.jobs.pop(0)
			cancel = taskModule.Task("x").cancel
			if job(cancel) is False:
				self.jobs.append(job)
				return


namesOn = {"on": True}
plugin = Plugin(labels.LabelStore(os.path.join(folder, "names.json")))
namer = nametools.Namer(plugin, said.append, lambda: namesOn["on"], onWay=lambda: beeps.append(1))
assert namer.on


def made(*args, **kwargs):
	"""An object as NVDA would make it: with the class VisionClaw puts first where it may need a name."""
	thing = Thing(*args, **kwargs)
	classes = []
	namer.chooseOverlay(thing, classes)
	if not classes:
		return thing
	thing.__class__ = type("Made", (classes[0], Thing), {})
	return thing


# A heading gets no class of VisionClaw's; a button does.
assert type(made("HEADING1")) is Thing and type(made("BUTTON")) is not Thing

# The focused button without a name: NVDA asks its name, the user is told a name is on its way, the model names it, the
# name is said with "probably", kept, and said by NVDA from then on.
gear = made("BUTTON")
api.getFocusObject = api.getNavigatorObject = lambda: gear
Model.answers = ["Settings"]
assert gear.name == "", "nothing is known yet: NVDA's own name, while the model is asked"
plugin.run()
assert beeps == [1], beeps
assert asked and asked[0].startswith("The picture shows one button that has no name.")
assert said == ["probably Settings"], said
assert gear.name == "probably Settings"
assert made("BUTTON").name == "probably Settings", "the same button made again by NVDA"
assert plugin.labels.entry("spotify", labels.imageKey(namer._pictured("BUTTON", (100, 100, 124, 124), None, False)["own"]))["name"] == "Settings"

# A button whose own code says what it is: the model agrees, so the name is sure and said without "probably"; kept by
# its automation id too, so the same button elsewhere on the screen is named without asking the model.
said.clear()
asked.clear()
mute = made("BUTTON", place=(300, 100, 24, 24), autoId="MuteButton")
api.getFocusObject = api.getNavigatorObject = lambda: mute
Model.answers = ["Mute"]
assert mute.name == ""
plugin.run()
assert said == ["Mute"], said
moved = made("BUTTON", place=(600, 400, 32, 32), autoId="MuteButton")
assert moved.name == "Mute" and len(asked) == 1

# Object navigation: the navigator object, not the focus, is reached; it is named the same way.
said.clear()
tile = made("LISTITEM", place=(100, 300, 120, 90), states=("FOCUSABLE", "SELECTABLE"))
api.getFocusObject = lambda: gear
api.getNavigatorObject = lambda: tile
Model.answers = ["Album cover"]
tile.name
plugin.run()
assert said == ["probably Album cover"], said
assert asked[-1].startswith("The picture shows one list item")

# A model that gives no name: nothing is said, NVDA's own name stays, and it is not asked again at once.
said.clear()
asked.clear()
blank = made("BUTTON", place=(500, 500, 20, 20))
api.getFocusObject = api.getNavigatorObject = lambda: blank
Model.answers = ["unknown"]
blank.name
plugin.run()
assert said == [] and blank.name == "" and len(asked) == 1
blank.name
plugin.run()
assert len(asked) == 1, "an object the model could not name is not asked about again at once"

# Stopped while the model looks: the object waits, and is named when the work goes on.
said.clear()
dial = made("BUTTON", place=(700, 100, 30, 30))
api.getFocusObject = api.getNavigatorObject = lambda: dial
Model.answers = ["STOP", "Volume"]
dial.name
plugin.run()
assert said == [] and plugin.jobs, "stopped: tried again later"
plugin.run()
assert said == ["probably Volume"], said

# The user's own name wins, and is said as it is.
said.clear()
api.getFocusObject = api.getNavigatorObject = lambda: gear
here = namer.current()
assert here["name"] == "Settings" and here["role"] == "BUTTON" and here["keys"], here
namer.giveName(here, "Preferences")
assert gear.name == "Preferences" and made("BUTTON").name == "Preferences"
# A heading is read from its text: it is not named.
api.getNavigatorObject = lambda: made("HEADING1")
assert "read from its own text" in namer.current()

# Text written in the button's picture agrees with the model: sure.
said.clear()
ocrRead["text"] = "Sign in"
signIn = made("BUTTON", place=(100, 600, 60, 20))
api.getFocusObject = api.getNavigatorObject = lambda: signIn
Model.answers = ["Sign in"]
signIn.name
plugin.run()
assert said == ["Sign in"], said
ocrRead["text"] = ""

# --- Only the truly unlabelled are named (the owner, 2026-11-19) ---

said.clear()
asked.clear()
beeps.clear()
# A field labelled by another object (UI Automation's LabeledBy, IAccessible2's labelled-by), which NVDA does not say
# by itself: that label is said as it is, and no model is asked.
quantity = made("EDITABLETEXT", place=(80, 700, 60, 20))
quantity.labeledBy = Thing("STATICTEXT", "Quantity", place=(10, 700, 60, 20))
api.getFocusObject = api.getNavigatorObject = lambda: quantity
assert quantity.name == "Quantity"
# A button whose words are in an object inside it, as WPF gives them: said as they are.
draft = made("BUTTON", place=(190, 695, 80, 30))
draft.firstChild = Thing("STATICTEXT", "Save draft", place=(200, 700, 50, 20))
api.getFocusObject = api.getNavigatorObject = lambda: draft
assert draft.name == "Save draft"
# A button with a description, a page number, a file in a list of files, an empty cell of a table and a pane that
# holds other objects: none is named.
described = made("BUTTON", place=(300, 700, 20, 20))
described.description = "Close the window"
holder = made("PANE", place=(0, 0, 400, 300))
holder.firstChild = Thing("BUTTON", "OK")
for thing in (quantity, draft, described, made("LINK", "2", place=(340, 700, 12, 20)),
		made("LISTITEM", "IMG_4021.jpg", place=(360, 700, 80, 60)),
		made("TABLECELL", place=(460, 700, 60, 20), states=("FOCUSABLE", "FOCUSED")), holder):
	api.getFocusObject = api.getNavigatorObject = lambda thing=thing: thing
	thing.name
	plugin.run()
assert asked == [] and said == [] and beeps == [], (asked, said, beeps)
assert described.name == "" and made("LISTITEM", "IMG_4021.jpg").name == "IMG_4021.jpg"
# A name the model gave by itself before, where the object has a label (VisionClaw 1.13.0 named such objects), is not
# said over the label.
plugin.labels.setGuess("spotify", naming.ruleKey({"role": "LINK", "autoId": "PageTwo"}), "Next page", role="LINK")
assert made("LINK", "2", place=(340, 700, 12, 20), autoId="PageTwo").name == "2"

# NVDA+Shift+Alt+B: the user asks the model for a name where the object has a label of its own. The name is said at
# once and from then on, also where NVDA makes the same button again.
closeBox = made("BUTTON", "X", place=(900, 20, 20, 20), autoId="CloseBox")
api.getFocusObject = api.getNavigatorObject = lambda: closeBox
Model.answers = ["Close"]
assert namer.askHere() is None
plugin.run()
assert said == ["Close"] and beeps == [1], "sure: its own code calls it CloseBox"
assert closeBox.name == "Close"
assert made("BUTTON", "X", place=(500, 300, 20, 20), autoId="CloseBox").name == "Close"
assert plugin.labels.entry("spotify", naming.ruleKey({"role": "BUTTON", "autoId": "CloseBox"}))["asked"]
# Asked where the model cannot tell: that is said, not nothing.
said.clear()
mystery = made("BUTTON", place=(940, 20, 20, 20))
api.getFocusObject = api.getNavigatorObject = lambda: mystery
Model.answers = ["unknown"]
assert namer.askHere() is None
plugin.run()
assert said == ["The model could not tell from its picture what this is."], said
api.getNavigatorObject = lambda: made("HEADING1")
assert "read from its own text" in namer.askHere()
api.getNavigatorObject = lambda: made("BUTTON", place=(10, 10, 0, 0))
assert "not on the screen" in namer.askHere()

# Names off: nothing is given and no class is put first.
namesOn["on"] = False
namer.refresh()
assert gear.name == "", "names off: NVDA's own name"
assert type(made("BUTTON")) is Thing
# NVDA+Shift+Alt+B still names the object where the user is, and says that names are off.
said.clear()
options = Thing("BUTTON", "Opt", place=(960, 60, 20, 20))
api.getFocusObject = api.getNavigatorObject = lambda: options
Model.answers = ["Options"]
assert namer.askHere() is None
plugin.run()
assert said == ["probably Options. Object names are off, so it is said only now; NVDA+Alt+B turns them on."], said
namesOn["on"] = True
namer.refresh()
# After NVDA restarts, nothing in its code tells that button apart, so it is found by its picture when the user is on
# it: the name asked for is said, and NVDA says it from then on.
said.clear()
namer._session.clear()
options = made("BUTTON", "Opt", place=(960, 60, 20, 20))
api.getFocusObject = api.getNavigatorObject = lambda: options
assert options.name == "Opt", "not known yet: its own label"
assert said == ["probably Options"], said
assert options.name == "probably Options"
other = made("BUTTON", "Opt", place=(10, 760, 20, 20))
api.getFocusObject = api.getNavigatorObject = lambda: other
assert other.name == "Opt" and said == ["probably Options"], "another button with that label keeps its own"

# --- Browse mode, with a stand-in page ---

textInfos = sys.modules["textInfos"]


class PageInfo:
	"""NVDA's copy of a page: _normalizeControlField is what VisionClaw's class wraps."""

	def __init__(self, document, commands):
		self.obj, self.commands = document, commands

	def _normalizeControlField(self, attrs):
		return attrs

	def getTextWithFields(self, formatConfig=None):
		out = []
		for command in self.commands:
			if isinstance(command, Command) and command.command == "controlStart":
				command = Command("controlStart", self._normalizeControlField(dict(command.field)))
			out.append(command)
		return out


class Page:
	documentConstantIdentifier = "https://www.example-music.com/player"
	rootNVDAObject = types.SimpleNamespace(name="Player", appModule=types.SimpleNamespace(appName="chrome"))

	def __init__(self):
		self.TextInfo = PageInfo

	def getNVDAObjectFromIdentifier(self, docHandle, ID):
		return types.SimpleNamespace(location=Location(200 + 40 * ID, 200, 24, 24))


page = Page()
namer.prepare(page)
assert page.TextInfo is not PageInfo and namer._patched
namer.prepare(page)
assert page.TextInfo.__mro__[1] is PageInfo, "a page is given its names once"
said.clear()
asked.clear()
beeps.clear()
Model.answers = ["Home", "Menu"]
line = page.TextInfo(page, stretch)
namer.reachedText(line, "caret")
plugin.run()
assert said == ["probably Home", "probably Menu"], "the controls of the line reached, in reading order"
assert beeps == [1], "one beep for the names on their way"
assert len(asked) == 2
# NVDA reads the page again: the link has its name now, in browse mode, without leaving it.
fields = [c.field for c in page.TextInfo(page, stretch).getTextWithFields() if isinstance(c, Command) and c.command == "controlStart"]
link = [field for field in fields if field["controlIdentifier_ID"] == "2"][0]
assert link["name"] == "probably Home" and link["alwaysReportName"], link
# Kept by its picture's file on the website, so a new visit has it at once.
assert namer.store.entry("site:example-music.com", naming.ruleKey({"role": "GRAPHIC", "src": "home.svg"})) is None
namer._session.clear()
again = [c.field for c in page.TextInfo(page, stretch).getTextWithFields() if isinstance(c, Command) and c.command == "controlStart"]
assert [field for field in again if field["controlIdentifier_ID"] == "2"][0]["name"] == "", (
	"the link itself has nothing fixed in its code; on a new visit its picture finds it")

# A picture whose file is known on the website is named on a new visit from its code alone.
namer.store.setGuess("site:example-music.com", naming.ruleKey({"role": "GRAPHIC", "src": "logo-wave.png"}), "Wave Music",
	sure=True, role="GRAPHIC")
alone = [start("GRAPHIC", "", ID=9, **{"IAccessible2::attribute_src": "https://cdn.x.com/logo-wave.png"}), end()]
picture = [c.field for c in page.TextInfo(page, alone).getTextWithFields() if isinstance(c, Command) and c.command == "controlStart"]
assert picture[0]["name"] == "Wave Music", picture

# NVDA+Shift+Alt+B in browse mode: the control at the cursor, which has a label of its own, is named by the model when
# asked, and NVDA says that name there from then on, in browse mode.
textInfos.FieldCommand = Command


class Caret:
	def __init__(self, commands):
		self.commands = commands

	def expand(self, unit):
		pass

	def getTextWithFields(self, formatConfig=None):
		return self.commands


goLine = [start("BUTTON", "Go", ID=12), "Go", end()]
page.passThrough = False
page.makeTextInfo = lambda position: Caret(goLine)
api.getFocusObject = lambda: types.SimpleNamespace(treeInterceptor=page)
said.clear()
Model.answers = ["Search"]
assert namer.askHere() is None
plugin.run()
assert said == ["probably Search"], said
goField = [c.field for c in page.TextInfo(page, goLine).getTextWithFields() if isinstance(c, Command) and c.command == "controlStart"]
assert goField[0]["name"] == "probably Search", goField
page.makeTextInfo = lambda position: Caret(["Plain text"])
assert "no control or picture here" in namer.askHere()

namer.terminate()
assert page.TextInfo is PageInfo, "the page's own class is put back when VisionClaw closes"
print("OK")
