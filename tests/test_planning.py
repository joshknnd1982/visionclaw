# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Smarter planning: the parts of Windows itself opened by plain code, the check that a clicked item fits the
user's own words, and claw/planning.py (where the user is, planning notes ranked by BM25, plans that worked
before with Laplace's rule and ageing, the jobs of the skills that fit). Plain Python: no NVDA, no model.

  python tests/test_planning.py
"""
import json
import os
import tempfile

import harness  # noqa: F401
from visionClaw.claw import computer, consensus, match, planner, planning, skills, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.tools import Tool

# --- The parts of Windows itself, from the user's own words ---

# The owner's own requests of 2026-11-18, which all failed in 1.7.1.
for said, sure, loose in (
	("click the start button.", None, "start"),
	("click the windows start button using the mouse.", "start", "start"),
	("Click the windows start button with the mouse", "start", "start"),
	("open the windows start menu.", "start", "start"),
	("start menu", "start", "start"), ("take me to the start menu please", "start", "start"),
	("I want to open the start menu", "start", "start"),
	("go to the system tray", "tray", "tray"), ("show hidden icons", "tray", "tray"),
	("open quick settings", "quick-settings", "quick-settings"), ("open the action center", "quick-settings", "quick-settings"),
	("open notifications", "notifications", "notifications"), ("go to the taskbar", "taskbar", "taskbar"),
	("right-click the start button", "quick-link", "quick-link"), ("open clipboard history", "clipboard", "clipboard"),
	("open the run dialog", "run", "run"), ("bring up task view", "task-view", "task-view"),
	("open the emoji panel", "emoji", "emoji"), ("open windows search", "search", "search"),
	("click the search button", None, "search"), ("open start", None, "start"),
	# Not a wish to open a part of Windows: its settings, a question, closing it, or a program to be started.
	("open notification settings", None, None), ("open taskbar settings", None, None),
	("how do I open the start menu?", None, None), ("close the start menu", None, None),
	("start notepad", None, None), ("search for cats", None, None), ("what is in the start menu", None, None),
	("Make NVDA speak faster", None, None),
):
	assert computer.windowsPart(said) == sure, (said, computer.windowsPart(said))
	assert computer.windowsPart(said, loose=True) == loose, (said, computer.windowsPart(said, loose=True))
# Every part has a name, a key that is sent, a key that is said and what to do there.
for ident, *_rest in computer.WINDOWS_PARTS:
	name, keys, said, there = computer.windowsPartOf(ident)
	assert name and keys and said and there.endswith("."), ident
	assert "+" in keys or keys in ("windows",), keys
text = computer.windowsPartText("start", "Search box, edit")
assert text.startswith("Opened the Start menu with the Windows key, or Control+Escape.") and "Search box" in text, text
assert "not in the window in front" in computer.windowsPartText("start", "", notInWindow=True)
# The keys are the ones in the notes written from Microsoft's page.
notes = open(os.path.join(harness.PLUGIN_DIR, "claw", "knowledge", "windows-keyboard.md"), encoding="utf-8").read()
for said in ("Control+Escape", "Windows+T", "Windows+B", "Windows+A", "Windows+N", "Windows+Tab", "Windows+R", "Windows+X",
		"Windows+V", "Windows+S"):
	assert said in notes, said

# --- Which recipe: plain code is sure, and no model is asked ---


def text(description, **options):
	field = {"type": "string", "description": description}
	field.update(options)
	return field


registry = tools.Registry()
for name in ("windows_part", "list_items", "click_item", "press_keys", "find_thing", "open_thing", "find_setting",
		"set_setting", "look", "look_up"):
	registry.add(Tool(name, name, lambda task, asked="": "Done.", {"asked": text("asked", auto=True)}))
for said in ("click the windows start button using the mouse.", "open the windows start menu.", "go to the system tray",
		"open notifications", "Click the windows start button with the mouse"):
	assert planner.hint(said) == "windows_part", (said, planner.hint(said))
	assert planner.decided(said, registry) == "windows_part", said
# "click the start button" alone may be a Start button of the program in front: it stays a click, and the click
# opens the Start menu when nothing in the window has that name (tests/test_nvda_stub.py).
assert planner.hint("click the start button.") == "click" and planner.decided("click the start button.", registry) is None
assert "windows_part" in planner.offered("click the start button.", registry)
# A model that chose the click for words that are sure of a part of Windows is corrected.
assert planner.fitted("click", "open the windows start menu.", planner.hint("open the windows start menu.")) == "windows_part"
# Settings pages of Windows that share a word stay what they were.
assert planner.hint("open taskbar settings") == "open_thing" and planner.hint("open notification settings") == "open_thing"
# The words of the split request of 2026-11-18 go to the part, after the look.
parts = planner.plainSplit("look at the current screen, then click the windows start button with the mouse.")
assert parts and planner.decided(parts[-1], registry) == "windows_part", parts

# --- The click: the item a model chose must fit the user's own words ---

assert match.saysNone("None of the items in the list is the Windows Start menu.")
assert match.saysNone("not found") and match.saysNone("The list does not contain the start button")
assert not match.saysNone("Settings button") and not match.saysNone("10") and not match.saysNone("Brave icon")
# A short text inside a long sentence is no match any more: "te" was clicked for a sentence in 1.7.1.
items = ["nologue 97 Settings button", "Settings button", "Recycle Bin", "Brave icon", "te", "Steam link"]
assert match.itemIndex("None of the items in the list is the Windows Start menu.", items) is None
assert match.itemIndex("Recycle Bin", items) == 2 and match.itemIndex("brave", items) == 3 and match.itemIndex("3", items) == 2
assert match.telling("click the start button.") == ["start"]
assert match.telling("click the windows start button using the mouse.") == ["windows", "start"]
assert match.telling("click the second button") == [] and match.telling("click it") == []
assert not match.fits("click the start button.", "Settings button")
assert not match.fits("click the windows start button using the mouse.", "Brave icon")
assert match.fits("click the recycle bin", "Recycle Bin") and match.fits("click google chrome", "Googe hrom link")
assert match.fits("click the button that sends it", "Send") and match.fits("click the second link", "Anything")
assert match.fits("press the Send button", "Send") and match.fits("", "Anything")

# --- Where the user is, in plain words ---

assert "Windows desktop" in planning.placeText("explorer", "Program Manager", "Progman")
assert "Start button" in planning.place("explorer", "Program Manager", "")
assert planning.place("explorer", "", "Shell_TrayWnd") == "the taskbar of Windows"
assert planning.place("chrome", "Gmail", "Chrome_WidgetWin_1") == "a web browser"
assert planning.place("notepad", "Untitled - Notepad", "#32770") == "a dialog box"
assert planning.place("notepad", "Untitled - Notepad", "Notepad") == "" and planning.placeText("notepad") == ""

# --- Planning notes, called up by the words and ranked by BM25 ---

available = set(planner.RECIPES)
found = planning.notesFor("open the windows start menu.", available)
assert found and "windows_part" in found[0], found
assert planning.notesFor("click the start button.", available)[0].startswith("The Start button"), planning.notesFor("click the start button.", available)
assert len(planning.notesFor("open the start menu and press enter key every time", available)) == planning.MAX_NOTES
assert planning.notesFor("tell me a joke", available) == []
# A note about no recipe that can be used here is left out.
assert planning.notesFor("open the windows start menu.", {"click"}) == []
# BM25: the text with the request's rare word wins; a word every text has counts for little.
scores = planning.bm25("taskbar icons", ["the taskbar of windows", "the icons of the desktop", "the window of a program"])
assert scores[0] > scores[2] and scores[1] > scores[2] and scores[2] == 0, scores
assert planning.bm25("anything", []) == []
for _pattern, recipes, note in planning.NOTES:
	assert note.endswith(".") and len(note) <= 300 and all(recipe in planner.RECIPES for recipe in recipes), note
	assert "for example" not in note.lower() and " like " not in note.lower(), note

# --- Plans that worked before: Laplace's rule, ageing, and the most weight wins ---

assert planning.rate(0, 0) == 0.5 and abs(planning.rate(1, 0) - 2 / 3) < 1e-9 and planning.rate(1, 1) == 0.5
assert planning.alike("open the windows start menu", "open the start menu of windows") == 1.0
assert planning.alike("open it", "open that") == 0.0  # too few telling words to compare
now = [1_800_000_000.0]
folder = tempfile.mkdtemp()
path = os.path.join(folder, "plans.json")
plans = planning.Plans(path, clock=lambda: now[0])
assert plans.recall("open the windows start menu") is None
plans.keep("open the windows start menu", "windows_part")
assert plans.recall("Open the Windows Start menu, please.") == ("open the windows start menu", "windows_part")
assert plans.recall("open the windows start menu", {"click"}) is None  # not usable here
assert plans.recall("make nvda speak faster") is None
# One failure after one success: no longer sure enough to be named.
plans.keep("open the windows start menu please", "windows_part", good=False)
assert plans.count() == 1 and plans.recall("open the windows start menu") is None
plans.keep("open the windows start menu", "windows_part")
plans.keep("open the windows start menu", "windows_part")
assert plans.recall("open the windows start menu") == ("open the windows start menu", "windows_part")
saved = json.load(open(path, encoding="utf-8"))
assert saved[0]["good"] == 3 and saved[0]["bad"] == 1, saved
# Read again from the file.
again = planning.Plans(path, clock=lambda: now[0])
assert again.recall("open the windows start menu")[1] == "windows_part"
# Two recipes for alike requests: the newer one weighs more once the older one has aged.
plans.keep("open the start menu of windows", "press_keys")
assert plans.count() == 2
now[0] += 400 * 86400
plans.keep("open the start menu of windows", "press_keys")
assert plans.recall("open the windows start menu")[1] == "press_keys"
plans.forget()
assert plans.count() == 0 and planning.Plans(path).count() == 0
# A file that cannot be read is no fault.
open(path, "w", encoding="utf-8").write("{not json")
assert planning.Plans(path).recall("open the windows start menu") is None

# How a request went, for counting its plan.
step = lambda status, result: type("Step", (), {"status": status, "result": result})()  # noqa: E731
went = lambda *steps: planning.outcome(type("Task", (), {"steps": list(steps)})())  # noqa: E731
assert went(step("done", "Opened the Start menu."), step("done", "Opened the Start menu.")) is True
assert went(step("done", "Listed."), step("failed", "There is no item.")) is False
assert went(step("done", "Listed."), step("done", "Nothing was clicked: nothing in the window is called start.")) is False
assert went(step("done", "Listed."), step("done", "You said no, so nothing was changed.")) is None
assert went() is None

# --- The skills that fit: their jobs are offered ---

lib = skills.Skills(os.path.join(harness.PLUGIN_DIR, "claw", "skills"), os.path.join(folder, "mine"))
chosen = lib.choose("click the start button.")
assert "parts-of-windows" in [skill.slug for skill in chosen], [skill.slug for skill in chosen]
assert "windows_part" in planning.skillJobs(chosen, set(planner.available(registry)))
assert planning.skillJobs(chosen, {"click"}) == ["click"]

# --- The brief a model is given, and that it reaches the model ---

brief, before = planning.brief("open the windows start menu", available, again, planner.label)
assert brief.startswith("Good to know: ") and "Earlier, \"open the windows start menu\" was done well" in brief, brief
assert before == "windows_part"
assert planning.brief("tell me a joke", available) == ("", None)


class Model:
	"""A stand-in model that says what it was asked."""
	def __init__(self, answer):
		self.answer, self.asked = answer, []

	def json(self, role, system, user, schema, maxTokens=0):
		self.asked.append((system, user, schema["properties"]["choice"]["enum"]))
		return {"choice": self.answer}


model = Model("click")
task = taskModule.Task("click the start button.")
task.plans, task.skills = again, chosen
recipe, how = consensus._onRecipe(model, task, "click the start button.", "Program: explorer.", registry,
	lambda question, choices: 0, "vision", "coder", single=True)
assert recipe == "click" and how == consensus.AGREED, (recipe, how)
system, user, offered = model.asked[0]
assert "Good to know: The Start button" in user and "windows_part" in offered, (user, offered)
# Where Windows' own shell is in front, "click the start button" can only mean that of Windows: no model is asked.
from visionClaw.claw import router  # noqa: E402
assert planning.isShell("explorer", "Program Manager", "Progman") and planning.isShell("explorer", "", "Shell_TrayWnd")
assert planning.isShell("explorer", "Downloads", "CabinetWClass") and not planning.isShell("spacetrader", "Space Trader", "")
assert not planning.isShell("chrome", "Gmail", "Chrome_WidgetWin_1")
model = Model("click")
task = taskModule.Task("click the start button.")
task.facts = {router.SHELL: True}
recipe, how = consensus._onRecipe(model, task, "click the start button.", "", registry, lambda question, choices: 0,
	"vision", "coder", single=True)
assert recipe == "windows_part" and how == consensus.AGREED and model.asked == [], (recipe, model.asked)
# Not for words that name no part of Windows, and not where a program is in front.
recipe, _how = consensus._onRecipe(model, task, "click the OK button.", "", registry, lambda question, choices: 0,
	"vision", "coder", single=True)
assert recipe == "click" and model.asked, recipe
task.facts = {router.SHELL: False}
model = Model("click")
recipe, _how = consensus._onRecipe(model, task, "click the start button.", "", registry, lambda question, choices: 0,
	"vision", "coder", single=True)
assert recipe == "click" and model.asked, recipe
# A fault in the planning brief never ends the request.
task.plans = object()
assert consensus._brief(task, "click the start button.", registry)[0].startswith("Good to know")

print("OK")
