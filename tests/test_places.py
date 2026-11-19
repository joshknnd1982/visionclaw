# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The places of Windows itself, and planning that generalizes: claw/places.py (which place a request means and what
is wanted there, and what Windows reports there in words), claw/concepts.py (words that mean the same thing), and
claw/planning.py's check that what was found answers the request, with the next way when it does not, and what is
learned from it. Plain Python: no NVDA, no model; whole requests with stand-in tools and a scripted model.

The owner's request of 2026-11-18 that failed: "tell me all objects that are currently in the system tray." was
sent to a description of the desktop's picture, which answered "I cannot see the system tray in this image", and
the request ended as "Finished".

  python tests/test_places.py
"""
import json
import re

import harness  # noqa: F401
from visionClaw.claw import concepts, orchestrator, places, planner, planning, tools
from visionClaw.claw import task as taskModule

OWNER = "tell me all objects that are currently in the system tray."

# --- Which place, and what is wanted there, from the user's own words ---

# (words, places, how, the thing asked about); None: no wish to be told what is in a place.
WISHES = (
	(OWNER, ["tray"], places.LIST, ""),
	("what's in my system tray?", ["tray"], places.LIST, ""),
	("what icons are in the notification area", ["tray"], places.LIST, ""),
	("list the tray icons", ["tray"], places.LIST, ""),
	("anything in the system tray?", ["tray"], places.LIST, ""),
	("check the system tray", ["tray"], places.LIST, ""),
	("read the hidden icons", ["tray"], places.LIST, ""),
	("show me the icons in the system tray", ["tray"], places.LIST, ""),
	("how many icons are in the system tray", ["tray"], places.COUNT, ""),
	("is NVDA running in the system tray?", ["tray"], places.HAS, "nvda"),
	("Is Dropbox in the system tray", ["tray"], places.HAS, "dropbox"),
	("which programs are on my taskbar", ["taskbar"], places.LIST, ""),
	("does my taskbar have firefox", ["taskbar"], places.HAS, "firefox"),
	("is there a steam icon on the taskbar", ["taskbar"], places.HAS, "steam"),
	("what icons are on my desktop", ["desktop"], places.LIST, ""),
	("read my notifications", ["notifications"], places.LIST, ""),
	("do I have any notifications", ["notifications"], places.LIST, ""),
	("what's pinned in the start menu", ["start"], places.LIST, ""),
	("tell me what's in quick settings", ["quick-settings"], places.LIST, ""),
	("what is in clipboard history", ["clipboard"], places.LIST, ""),
	# Going there, clicking in it, how it looks, how to get there, what it is: no wish to be told what is in it.
	("show me the system tray", None, None, None), ("Go to the system tray.", None, None, None),
	("open the system tray", None, None, None), ("open the windows start menu.", None, None, None),
	("what is the system tray?", None, None, None), ("what's the system tray for", None, None, None),
	("how do I get to the system tray", None, None, None), ("click the volume icon in the system tray", None, None, None),
	("what color is my taskbar", None, None, None), ("make nvda speak faster", None, None, None),
	# What is on the desktop without a word for its icons is the user's own files there (computer.aboutFiles).
	("what's on my desktop", None, None, None), ("which files are on my desktop", None, None, None),
)
for said, where, how, thing in WISHES:
	found = places.wish(said)
	if where is None:
		assert found is None, (said, found)
		continue
	assert found == {"places": where, "how": how, "thing": thing}, (said, found)

# Which job: decided by plain code, and no model is asked. Going there stays the part of Windows that is opened.


class _Registry:
	def has(self, names):
		return True


for said, job in (
		(OWNER, "read_place"), ("how many icons are in the system tray", "read_place"),
		("which programs are on my taskbar", "read_place"), ("read my notifications", "read_place"),
		("show me the icons in the system tray", "read_place"),
		("Go to the system tray.", "windows_part"), ("open the windows start menu.", "windows_part"),
		("click the volume icon in the system tray", "click"), ("right-click Dropbox in the notification area", "click"),
		("double-click the recycle bin on the desktop", "click")):
	assert planner.hint(said) == job and planner.decided(said, _Registry()) == job, (said, planner.hint(said))
# What a click names inside a place, and a part of Windows of its own on the taskbar.
assert places.clicksIn("click the volume icon in the system tray") == "tray"
assert places.clicksIn("click the start button on the taskbar") is None and planner.hint("click the start button on the taskbar") == "windows_part"
assert places.clicksIn("how do I click the volume icon in the system tray") is None
assert places.within("the Firefox button on the taskbar") == "taskbar" and places.within("read my notifications") is None
assert planner.hint("what is the system tray?") == "nvda_question" and planner.hint("how do I get to the system tray") == "explain_keys"
# Only offered where the words name a place: a router need, like the others that read everything from the words.
assert planner._NEEDS["read_place"]("make nvda speak faster") is None and planner._NEEDS["read_place"](OWNER)

# --- What Windows reports, sorted and said ---

# The taskbar of the owner's Windows 11, read with UI Automation on 2026-11-18, in the shape placetools.py gives.
B = lambda x: (x, 1198, x + 40, 1258)  # noqa: E731
BAR = [
	{"name": "Start", "kind": 50000, "cls": "ToggleButton", "aid": "StartButton", "box": B(708)},
	{"name": "Search", "kind": 50000, "cls": "ToggleButton", "aid": "SearchButton", "box": B(764)},
	{"name": "", "kind": 50006, "cls": "Microsoft.UI.Xaml.Controls.AnimatedVisualPlayer", "aid": "Icon", "box": B(777)},
	{"name": "Microsoft Edge pinned", "kind": 50000, "cls": "Taskbar.TaskListButtonAutomationPeer", "aid": "Appid: MSEdge", "box": B(819)},
	{"name": "Claude - 1 running window", "kind": 50000, "cls": "Taskbar.TaskListButtonAutomationPeer", "aid": "Window: 0x2a04f6", "box": B(874)},
	{"name": "Show Hidden Icons", "kind": 50000, "cls": "SystemTray.NormalButton", "aid": "SystemTrayIcon", "box": B(1663)},
	{"name": "Network JoshKennedy\nInternet access", "kind": 50000, "cls": "SystemTray.AccentButton", "aid": "SystemTrayIcon", "box": B(1708)},
	{"name": "Volume Speakers (Realtek(R) Audio): 20%", "kind": 50000, "cls": "SystemTray.OmniButtonCenter", "aid": "SystemTrayIcon", "box": B(1743)},
	{"name": "Power Battery status: fully charged 100%", "kind": 50000, "cls": "SystemTray.AccentButton", "aid": "SystemTrayIcon", "box": B(1778)},
	{"name": "Clock 10:29 PM\n‎11/‎18/‎2026", "kind": 50000, "cls": "SystemTray.OmniButton", "aid": "SystemTrayIcon", "box": B(1823)},
]
HIDDEN = [
	{"name": "NVDA", "kind": 50000, "cls": "SystemTray.NormalButton", "aid": "NotifyItemIcon", "box": None, "hidden": True},
	{"name": "Dropbox\nUp to date", "kind": 50000, "cls": "SystemTray.NormalButton", "aid": "NotifyItemIcon", "box": None, "hidden": True},
	# Shown and hidden at once is said where it is shown.
	{"name": "Volume Speakers (Realtek(R) Audio): 20%", "kind": 50000, "cls": "SystemTray.NormalButton", "box": None, "hidden": True},
]
# Windows 10's taskbar: toolbar buttons inside TrayNotifyWnd and MSTaskListWClass, told apart by where they are.
OLD = [
	{"name": "Start", "kind": 50000, "cls": "Start", "path": ("Shell_TrayWnd",)},
	{"name": "Firefox", "kind": 50000, "cls": "", "path": ("Shell_TrayWnd", "ReBarWindow32", "MSTaskSwWClass", "MSTaskListWClass")},
	{"name": "Notification Chevron", "kind": 50000, "cls": "Button", "path": ("Shell_TrayWnd", "TrayNotifyWnd")},
	{"name": "Speakers: 30%", "kind": 50000, "cls": "", "path": ("Shell_TrayWnd", "TrayNotifyWnd", "SysPager", "ToolbarWindow32")},
	{"name": "Steam", "kind": 50000, "cls": "", "path": ("NotifyIconOverflowWindow", "ToolbarWindow32"), "hidden": True},
]
assert places.clean("Clock 10:29 PM\n‎11/‎18/‎2026") == "Clock 10:29 PM, 11/18/2026"
shown, hidden, clock, chevron = places.tray(BAR + HIDDEN)
assert shown == ["Network JoshKennedy, Internet access", "Volume Speakers (Realtek(R) Audio): 20%", "Power Battery status: fully charged 100%"], shown
assert hidden == ["NVDA", "Dropbox, Up to date"] and clock == "Clock 10:29 PM, 11/18/2026" and chevron
assert places.tray(OLD) == (["Speakers: 30%"], ["Steam"], "", True), places.tray(OLD)
own, programs, icons = places.taskbar(BAR + HIDDEN)
assert own == ["Start", "Search"] and programs == [("Microsoft Edge", "pinned"), ("Claude", "1 running window")] and icons == 3
assert places.taskbar(OLD) == (["Start"], [("Firefox", "")], 1), places.taskbar(OLD)
said = places.trayText(places.tray(BAR + HIDDEN))
assert said.startswith(
	"The notification area has 3 icons shown on the taskbar. They are: Network JoshKennedy, Internet access; Volume "
	"Speakers (Realtek(R) Audio): 20%; Power Battery status: fully charged 100%. Hidden behind Show hidden icons, 2 more "
	"icons: NVDA; Dropbox, Up to date. The clock says: 10:29 PM, 11/18/2026. To go to the notification area yourself, "
	"press Windows+B. The arrow keys move between its icons"), said
assert places.trayText(places.tray(BAR + HIDDEN), places.COUNT).startswith(
	"The notification area has 3 icons shown and 2 hidden behind Show hidden icons.")
assert places.trayText(places.tray(BAR + HIDDEN), places.HAS, "dropbox").startswith(
	"Yes. In the notification area, among the hidden icons: Dropbox, Up to date.")
assert places.trayText(places.tray(BAR + HIDDEN), places.HAS, "steam").startswith("No icon in the notification area is called steam.")
# Hidden icons that could not be read are said to be there, not to be none.
assert "There are more icons behind the button Show hidden icons, which could not be read." in places.trayText(
	places.tray(BAR), hiddenRead=False)
assert places.trayText(places.tray([])) == "" and places.taskbarText(places.taskbar([])) == ""
assert places.taskbarText(places.taskbar(BAR), places.HAS, "edge").startswith("Yes. On the taskbar: Microsoft Edge, pinned.")
# A very long list is cut at a name, within what a tool may give back, and says so.
many = places.listText(places.DESKTOP, [f"Shortcut number {number} with a long name" for number in range(80)])
assert len(many) <= places.MAX_CHARS and many.endswith("; and more."), many[-60:]
# Nothing is said only by sight: no colour, no "look", no "see" in what the user is told.
for text in (said, places.taskbarText(places.taskbar(BAR)), places.listText("quick-settings", ["Wi-Fi, on"], left=True),
		places.nothingText(places.TRAY), places.notOpenedText("start")):
	assert not re.search(r"\b(colou?r|look|see|click the icon)\b", text, re.IGNORECASE), text
assert places.opened([{"name": "Wi-Fi", "kind": 50000, "state": "on"}, {"name": "", "kind": 50000},
	{"name": "Wi-Fi", "kind": 50000, "state": "on"}, {"name": "Pane", "kind": 50033}]) == ["Wi-Fi, on"]

# --- Words that mean the same thing ---

assert concepts.tokens(OWNER) == ["@tell", "@item", "@tray"], concepts.tokens(OWNER)
assert concepts.tokens("which icons are in my notification area") == ["@tell", "@item", "@tray"]
# "Start menu" is one thing, not "start" and "menu"; a word that can mean two things is joined only in a phrase.
assert concepts.tokens("open the start menu") == ["@open", "@start"] and "@start" not in concepts.tokens("start notepad")
assert planning.alike(OWNER, "which icons are in my notification area") == 1.0
assert planning.alike(OWNER, "make nvda speak faster") == 0.0
assert planning.alike("open it", "open that") == 0.0  # still too few to compare
# A note is called up by words that mean what it is about, and its words name both jobs.
note = planning.notesFor(OWNER, None)[0]
assert note.startswith("The Start button") and "read_place" in note and "windows_part" in note and len(note) <= 300, note
assert planning.notesFor("open the windows start menu.", {"windows_part"})[0] == note

# --- What is no answer, and the next way ---

for result, empty in (
		("I cannot see the system tray in this image. The image shows the desktop icons and the background wallpaper, "
			"but the bottom right corner where the system tray is located is not visible.", True),
		("The system tray is not visible in this picture.", True), ("The screenshot does not show the taskbar.", True),
		("Windows did not say what is in the notification area. To go there yourself, press Windows+B.", True),
		("No text was found there.", True),
		# Answers, also when they say no.
		("The window shows a list of 5 files.", False), ("No, there is no error message on the screen.", False),
		("I can't see any errors on the screen.", False), ("Yes. In the notification area: NVDA.", False), ("", False)):
	assert planning.unanswered(result) is empty, (result, empty)
ALL = planner.RECIPES
assert planning.nextWay(OWNER, ["describe"], ALL) == "read_place"
assert planning.nextWay(OWNER, ["read_text"], ALL) == "read_place"
assert planning.nextWay("what's in my system tray?", ["read_place"], ALL) == "describe"
assert planning.nextWay("what icons are on my desktop", ["read_place"], ALL) is None  # its picture is the whole screen
assert planning.nextWay(OWNER, ["describe", "read_place"], ALL) is None  # each way once
assert planning.nextWay("what is on the screen", ["describe"], ALL) is None
assert planning.nextWay(OWNER, ["describe"], {"describe": 1}) is None  # not usable here
assert planning.nextWay(OWNER, ["click"], ALL) is None  # only after a way that looks
# Every next way only looks, and changes nothing: it is not asked about.
for before, way, _fits in planning.NEXT_WAYS:
	assert way in planner.RECIPES and all(name in planner.RECIPES for name in before), way
	assert way in planner._LOOKS, way
# A request whose way of looking found nothing went not well, and is not learned as the way to do it.
step = taskModule.Step("Looking at the screen", "look", part=OWNER, recipe="describe")
step.status, step.result = taskModule.STEP_DONE, "I cannot see the system tray in this image."
assert planning.outcome(type("Task", (), {"steps": [step]})()) is False

# --- Whole requests, with stand-in tools and a scripted model ---

V = tools.VERBATIM
TRAY_SAID = places.trayText(places.tray(BAR + HIDDEN))


def text(description, **extra):
	return dict({"type": "string", "description": description}, **extra)


def makeRegistry(state):
	reg = tools.Registry()

	def add(name, description, fn, fields=None, **options):
		reg.add(tools.Tool(name, description, fn, fields, **options))

	def look(task, target, question):
		state.setdefault("looked", []).append(question)
		return state.get("picture", "I cannot see the system tray in this image. The bottom right corner is not visible.")

	add("look", "look at the screen", look, {
		"target": text("what", enum=["window", "screen"], auto=lambda part: "window"), "question": text("what to find out", auto=True),
	}, looks=True, title="Looking at the screen", tell=V)
	add("read_text", "read the text", lambda task, target: "No text was found there.",
		{"target": text("where", enum=["window"], auto=lambda part: "window")}, looks=True, title="Reading the text", tell=V)

	def readPlace(task, asked):
		state.setdefault("read", []).append(asked)
		said = state.get("place", TRAY_SAID)
		if isinstance(said, Exception):
			raise said
		return said

	add("read_place", "read a part of Windows", readPlace, {"asked": text("asked", auto=True)},
		looks=True, title="Reading a part of Windows", tell=V)
	add("look_up", "ask NVDA", lambda task, question: "From NVDA: nothing.", {"question": text("q", auto=True)},
		looks=True, title="Asking")
	add(tools.ANSWER, "tell the user the result", lambda task: "")
	return reg


class Scripted:
	"""A model that chooses what the test says for each part, and the first allowed answer in a form."""

	def __init__(self, choices):
		self.choices = choices
		self.chosen = []

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		user = messages[1]["content"]
		schema = options["response_format"]["json_schema"]["schema"]["properties"]
		if "choice" in schema:
			part = re.search(r'The user asked: "(.*?)"\n', user).group(1)
			self.chosen.append(part)
			wanted = self.choices[part]
			assert wanted in schema["choice"]["enum"], (part, wanted)
			return json.dumps({"choice": wanted})
		if "done" in schema:
			return json.dumps({"done": True, "missing": ""})
		return json.dumps({name: (spec.get("enum") or ["x"])[0] for name, spec in schema.items()})


def run(request, choices=None, plans=None, **state):
	state = dict(state)
	asked = []
	model = Scripted(choices or {})
	orch = orchestrator.Orchestrator(model, makeRegistry(state), lambda question, options: asked.append(question) or 0,
		lambda: "Program: explorer. Window title: Program Manager. This is the Windows desktop.", None)
	orch.plans = plans
	task = orch.run(taskModule.Task(request))
	return task, state, model, asked


def statuses(task):
	return [(step.tool, step.status) for step in task.steps]


# 1. The owner's request: plain code reads which place and what is wanted, no model is asked, and the answer is what
#    Windows reports, word for word.
plans = planning.Plans(None)
task, state, model, asked = run(OWNER, plans=plans)
assert task.state == taskModule.DONE, task.log
assert statuses(task) == [("read_place", "done"), ("answer", "done")] and model.chosen == [] and "looked" not in state
assert task.answer == TRAY_SAID, task.answer
assert plans.recall("which icons are in my notification area") == (OWNER, "read_place")

# 2. Where a model sent such a request to the picture anyway, as it did before, the picture's "I cannot see it" is
#    noticed, the place is read from Windows instead, the user is told so, and the picture's answer is not said.
#    The way that failed is counted as not well, and the next request in other words that mean the same is told
#    the way that worked.
sure = planner._SURE
planner._SURE = tuple(name for name in sure if name != "read_place")
realDecided = planner.decided
planner.decided = lambda part, registry, before=None: None
try:
	plans = planning.Plans(None)
	task, state, model, asked = run(OWNER, {OWNER: "describe"}, plans=plans)
	assert task.state == taskModule.DONE, task.log
	assert statuses(task) == [("look", "done"), ("read_place", "done"), ("answer", "done")], statuses(task)
	assert task.steps[0].replaced and not getattr(task.steps[1], "replaced", False)
	assert task.answer == (
		"That did not answer it, so VisionClaw tried another way, which only looks: say what is in the system tray, on the "
		"taskbar or another part of Windows. " + TRAY_SAID), task.answer
	assert "I cannot see" not in task.answer and asked == []
	assert any("What was found before: I cannot see the system tray" in entry for _t, _kind, entry in task.log)
	assert task.tried == [(OWNER, "describe", "read_place")]
	assert plans.recall(OWNER) == (OWNER, "read_place")
	assert plans.recall("what icons are in my notification area?") == (OWNER, "read_place")
	kept = {plan["recipe"]: (plan["good"], plan["bad"]) for plan in plans._load()}
	assert kept == {"describe": (0, 1), "read_place": (1, 0)}, kept
	# The brief for the next request in other words names the way that worked.
	brief, before = planning.brief("which icons are in the notification area", planner.RECIPES, plans, planner.label)
	assert before == "read_place" and "was done well this way: read_place" in brief, brief

	# 3. Windows says nothing about the tray: its picture is looked at instead, and what the picture shows is said.
	task, state, model, asked = run(OWNER, {OWNER: "read_place"},
		place="Windows did not say what is in the notification area. To go there yourself, press Windows+B.",
		picture="The taskbar shows icons for the network, the volume and the battery, and the clock.")
	assert statuses(task) == [("read_place", "done"), ("look", "done"), ("answer", "done")], statuses(task)
	assert task.answer.endswith("The taskbar shows icons for the network, the volume and the battery, and the clock."), task.answer

	# 4. Both ways find nothing: the last is said, and each way is tried once.
	task, state, model, asked = run(OWNER, {OWNER: "describe"},
		place="Windows did not say what is in the notification area. To go there yourself, press Windows+B.")
	assert [step.tool for step in task.steps] == ["look", "read_place", "answer"], statuses(task)
	assert task.answer.endswith("Windows did not say what is in the notification area. To go there yourself, press Windows+B."), task.answer

	# 5. The next way fails outright: what the first way found is said as it was, and nothing is claimed.
	task, state, model, asked = run(OWNER, {OWNER: "describe"}, place=tools.ToolError("No part of Windows."))
	assert task.state == taskModule.DONE and task.answer.startswith("I cannot see the system tray"), task.answer
	assert asked and asked[0].startswith("This step did not work: Reading a part of Windows."), asked
finally:
	planner._SURE = sure
	planner.decided = realDecided

# 6. A picture that answers is said as it is, and nothing more is tried.
task, state, model, asked = run("what is on my screen?", {"what is on my screen?": "describe"},
	picture="The desktop shows 44 icons and the taskbar.")
assert statuses(task) == [("look", "done"), ("answer", "done")] and task.answer == "The desktop shows 44 icons and the taskbar."
assert "read" not in state

print("OK")
