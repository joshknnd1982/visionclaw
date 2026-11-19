# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Finding the right NVDA command among all the real ones, how often its key is pressed for what was asked,
the list of everything inside NVDA, VisionClaw's own log, and a fault inside a tool. Plain Python: no NVDA and
no model.

tests/nvda_commands.json holds the name and description of every command in NVDA 2026.3.1's globalCommands.py,
written by tools/write_command_fixture.py from NVDA's source.

  python tests/test_commands.py
"""
import json
import os
import sys
import tempfile
import types

import harness  # noqa: F401
from visionClaw.claw import commands, debuglog, inside, planner, ranking, shapes
from visionClaw.claw import task as taskModule
from visionClaw.claw.memory import stem
from visionClaw.claw.tools import Registry, Tool, ToolError

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "nvda_commands.json"), encoding="utf-8") as f:
	NVDA = json.load(f)
ENTRIES = [(c["name"], c["description"], c["category"]) for c in NVDA]
BY_NAME = {c["name"]: c for c in NVDA}
assert len(NVDA) > 250 and "dateTime" in BY_NAME


def found(asked):
	return [ENTRIES[i][0] for i in commands.find(asked, ENTRIES)]


def pressed(asked, name):
	return commands.presses(asked, name, BY_NAME[name]["description"])


# --- The request that went wrong: "ask nvda to give me the current time and then the date" ---
# It was split into these two parts. The old search counted shared words: "current" and the "times" of
# "pressed three times" made the status bar command look as good as the clock, and the model took it.
assert found("ask nvda to give me the current time") == ["dateTime"], found("ask nvda to give me the current time")
assert found("ask nvda to give me the date") == ["dateTime"], found("ask nvda to give me the date")
assert "reportStatusLine" not in found("ask nvda to give me the current time")
# One press says the time, two say the date: NVDA says so in the command's description, and plain code reads it.
assert commands.byPress(BY_NAME["dateTime"]["description"]) == {
	1: "If pressed once, reports the current time.", 2: "If pressed twice, reports the current date"}
assert pressed("ask nvda to give me the current time", "dateTime") == [1]
assert pressed("ask nvda to give me the date", "dateTime") == [2]
assert pressed("tell me the time and the date", "dateTime") == [1, 2]
assert pressed("what time is it", "dateTime") == [1] and pressed("what day is it today", "dateTime") == [2]
assert found("what time is it")[0] == "dateTime" and found("what day is it today")[0] == "dateTime"
# The user's own words can say how often.
assert pressed("press the title command twice", "title") == [2] and pressed("run it three times", "title") == [3]
assert commands.pressText(1) == "once" and commands.pressText(2) == "twice" and commands.pressText(3) == "three times"

# --- Other commands, among all 265 ---
for asked, first in (
	("read the window title", "title"), ("say the battery level", "say_battery_status"),
	("how much battery is left", "say_battery_status"), ("open the NVDA menu", "showGui"),
	("start reading from here", "sayAll"), ("toggle input help", "toggleInputHelp"),
	("open the speech viewer", "toggleSpeechViewer"), ("restart NVDA", "restart"),
	("read the current word", "review_currentWord"), ("tell me the formatting of this text", "reportFormattingAtCaret"),
):
	assert found(asked)[0] == first, (asked, found(asked))
for asked, among in (
	("read the status bar", "reportStatusLine"), ("report the focus", "reportCurrentFocus"),
	("what is on the clipboard", "reportClipboardText"), ("report the navigator object", "navigatorObject_current"),
	("turn the screen curtain on", "toggleScreenCurtain"), ("open the add-on store", "activateAddonsManager"),
):
	assert among in found(asked)[:3], (asked, found(asked))
# What has no command finds nothing, instead of whatever shares the word "say": plain code decides that
# nothing fits, because a small model cannot say "none of these".
assert found("say the version of NVDA") == [], found("say the version of NVDA")
assert found("") == [] and found("xyzzy plugh") == []
# A second or third press is only taken when the words ask for what it does.
assert pressed("read the window title", "title") == [1]
assert pressed("copy the window title to the clipboard", "title") == [3]
assert pressed("spell the current line", "reportCurrentLine") == [2]
assert pressed("read the current line", "reportCurrentLine") == [1]
assert pressed("read the status bar", "reportStatusLine") == [1]
# "three times" in a description is not the time.
assert "time" not in commands.telling("Pressing three times spells it. Pressing four times shows it.")
assert commands.pressCount("If pressed twice, spells it") == 2 and commands.pressCount("Pressing four times") == 4
assert stem("copies") == "copy" and stem("entries") == "entry" and stem("faster") == "fast"

# --- Ranking: a rare word tells more than a common one, a name more than a description ---
things = [({"report", "status"}, {"current", "bar"}), ({"date", "time"}, {"current", "report"}), ({"current", "line"}, {"report"})]
assert ranking.rank({"current", "time"}, things) == [1]
assert ranking.rank({"current"}, things)[0] == 2  # in its name
assert ranking.rank(set(), things) == [] and ranking.rank({"nothing"}, things) == []
# A word that only asks does not carry a thing that shares nothing else.
assert ranking.rank({"report", "time"}, things, light={"report"}) == [1]
assert set(ranking.rank({"report"}, things, light={"report"})) == {0, 1, 2}

# --- Recipes that the words point to ---
for request, recipe in (
	("ask nvda to give me the current time", "do_command"), ("ask nvda to give me the date", "do_command"),
	("what time is it", "do_command"), ("what is the date", "do_command"), ("tell me the time", "do_command"),
	("open the visionclaw log", "visionclaw_log"), ("show me the debug log", "visionclaw_log"),
	("audit nvda", "audit_nvda"), ("do a full audit of all nvda commands, objects and functions", "audit_nvda"),
	("list everything inside nvda", "audit_nvda"),
	("what does the function api.getFocusObject do", "inside_nvda"),
	("which functions does nvda have for braille", "inside_nvda"),
	("tell me everything about this control", "object_facts"),
	("what is the window class of the focused control", "object_facts"),
	("inspect this page for accessibility problems", "check_access"), ("audit this web page", "check_access"),
	("write an add-on that beeps on links", "write_addon"), ("speak faster", "change_setting"),
	("what model is installed", "visionclaw_models"),
):
	assert planner.hint(request) == recipe, (request, planner.hint(request))
for name in ("object_facts", "inside_nvda", "audit_nvda", "visionclaw_log"):
	assert name in planner.RECIPES
assert planner.RECIPES["inside_nvda"][2] == ("find_nvda", "inspect_nvda")

# --- Everything inside NVDA, listed from the loaded modules themselves ---
api = types.ModuleType("api")
api.__doc__ = "General functions for NVDA. More words here."


def getFocusObject():
	"""Gets the object with focus.
	@returns: the object with focus
	"""
	return types.SimpleNamespace(name="OK", role=types.SimpleNamespace(displayString="button"))


def setFocusObject(obj):
	"""Sets the object with focus."""


class Handler:
	"""Keeps the braille display."""

	def __init__(self):
		self.display = "focus40"
		self._hidden = 1

	def _get_displaySize(self):
		"""The number of cells."""
		return 40

	def message(self, text):
		"""Shows a message for a while."""

	def script_scrollBack(self, gesture):
		pass


for thing in (getFocusObject, setFocusObject, Handler):
	thing.__module__ = "api"
api.getFocusObject, api.setFocusObject, api.Handler = getFocusObject, setFocusObject, Handler
api.handler = Handler()
api.VERSION = "2026.3"
api._private = 1
api.os = os  # brought in from elsewhere: not api's own
package = types.ModuleType("synthDrivers")
package.__path__ = [os.path.join(HERE, "nothing-here")]
modules = {"api": api, "os": os, "json": json, "synthDrivers": package, "wx": types.ModuleType("wx"), "gone": None}
entries = inside.index(modules, stdlib={"os", "json"})
names = {entry.name: entry for entry in entries}
assert "os" not in names and "json" not in names and "wx" not in names  # Python's own and the libraries are not NVDA
for name, kind in (
	("api", inside.MODULE), ("api.getFocusObject", inside.FUNCTION), ("api.Handler", inside.CLASS),
	("api.Handler.message", inside.METHOD), ("api.Handler.displaySize", inside.PROPERTY),
	("api.Handler.script_scrollBack", inside.METHOD), ("api.handler", inside.VALUE),
	("api.handler.display", inside.VALUE), ("api.VERSION", inside.VALUE),
):
	assert name in names and names[name].kind == kind, (name, sorted(names))
assert "api._private" not in names and "api.os" not in names and "api.handler._hidden" not in names
assert names["api.getFocusObject"].line() == "api.getFocusObject: function. getFocusObject(). Gets the object with focus."
assert names["api"].summary == "General functions for NVDA."
count = inside.counts(entries)
assert count[inside.FUNCTION] == 2 and count[inside.CLASS] == 1 and count["commands"] == 1, count
# Found by describing it, or by its name written out.
assert inside.search(entries, "the object with focus")[0].name in ("api.getFocusObject", "api.setFocusObject")
assert inside.search(entries, "what does api.getFocusObject give back")[0].name == "api.getFocusObject"
assert inside.search(entries, "braille display handler")[0].name.startswith("api.")
assert inside.search(entries, "quokka zebra") == []
assert inside.namesIn("call api.getFocusObject() and controlTypes.Role.BUTTON") == ["api.getFocusObject", "controlTypes.Role.BUTTON"]
# A function that only reports something and needs nothing may be called; nothing else is.
assert inside.reports("getFocusObject", getFocusObject) and not inside.reports("setFocusObject", setFocusObject)
assert not inside.reports("getThing", lambda needed: needed) and inside.reports("isRunning", lambda flag=True: flag)
assert not inside.reports("Handler", Handler) and not inside.reports("restart", lambda: None)
assert inside.describe(getFocusObject()) .startswith('an object NVDA reads: button called "OK"')
assert inside.describe(None) == "nothing (None)" and inside.describe(True) == "yes (True)" and inside.describe(7) == "7"
assert inside.describe([1, 2, 3]).startswith("a list with 3 items") and inside.describe({"a": 1}).startswith("a dictionary with 1 entries")
assert "display" in inside.publicNames(api.handler) and "displaySize" in inside.publicNames(api.handler)
assert inside.firstLine("Speaks text.\n@param text: the text") == "Speaks text."
text = inside.auditText("Audit", [("Totals", ["Commands: 3."])], entries)
assert text.startswith("# Audit\n\n## Totals\n\nCommands: 3.\n") and "\napi.getFocusObject: function." in text
# Modules of a loaded package that are not loaded are listed by name, and nothing is loaded for it.
with tempfile.TemporaryDirectory() as folder:
	for name in ("espeak.py", "oneCore.py", "_private.py"):
		with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
			f.write("raise RuntimeError('this must never be run by listing it')\n")
	package.__path__ = [folder]
	assert inside.unloaded(modules, stdlib={"os", "json"}) == ["synthDrivers.espeak", "synthDrivers.oneCore"]
	listed = {entry.name: entry for entry in inside.index(modules, stdlib={"os", "json"})}
	assert listed["synthDrivers.espeak"].summary == inside.NOT_LOADED and "synthDrivers.espeak" not in sys.modules
# A dotted name the user wrote out is the one that is meant; no model is asked.
step = taskModule.Step("Searching inside NVDA", "find_nvda")
step.status = taskModule.STEP_DONE
step.result = "api.getFocusObject: function. Gets the focus.\napi.setFocusObject: function. Sets the focus."
steps = [step, taskModule.Step("Looking inside NVDA", "inspect_nvda")]
assert shapes.shapes("inspect_nvda", ["name"], steps, 1) == {"name": {"enum": ["api.getFocusObject", "api.setFocusObject"]}}
assert shapes.said("inspect_nvda", "name", "what does api.getFocusObject do", steps, 1) == "api.getFocusObject"
assert shapes.said("inspect_nvda", "name", "which one gets the focus", steps, 1) is None

# One command found: its line stays whole when it is quoted as the answer, so the keys are not lost.
line = "title: Reports the title of the current application or foreground window. If pressed twice, spells the title. Keys: NVDA+t."
assert shapes.quote("How do I read the title of this window?", line)[0] == [line]
# A paragraph that is not a list of ids is still answered with its telling sentence.
assert shapes.quote("what is the refund policy", "We sell tools. You can return any product within 30 days for a refund.")[0] == [
	"You can return any product within 30 days for a refund."]

# --- VisionClaw's own log ---
with tempfile.TemporaryDirectory() as folder:
	assert debuglog.path() is None and not debuglog.on()
	debuglog.log("test", "written before the log was started: goes nowhere, and does not fail")
	path = debuglog.start(os.path.join(folder, "logs"), debuglog.DETAILED, maxBytes=5000)
	assert path.endswith("visionclaw.log") and debuglog.on() and debuglog.detailed()
	debuglog.log("task", "New request: 'the time'")
	debuglog.detail("model", "a whole prompt\nwith a second line")
	try:
		None.wasInSayAll
	except AttributeError as e:
		debuglog.error("tool", "run_command failed", e)
	written = debuglog.tail(40)
	assert "task: New request: 'the time'" in written and "\n\twith a second line\n" in written
	# An error is written with the place in the code where it happened.
	assert "tool: ERROR: run_command failed" in written and "AttributeError" in written and "test_commands.py" in written
	assert written[:4].isdigit() and "[MainThread]" in written  # each entry has its time and its thread
	# Brief leaves the whole prompts out; off writes nothing.
	debuglog.setLevel(debuglog.BRIEF)
	debuglog.detail("model", "DETAIL-ONLY")
	debuglog.log("task", "BRIEF-TOO")
	debuglog.setLevel(debuglog.OFF)
	debuglog.log("task", "NOTHING-WHEN-OFF")
	debuglog.error("task", "NOTHING-WHEN-OFF")
	written = debuglog.tail(40)
	assert "BRIEF-TOO" in written and "DETAIL-ONLY" not in written and "NOTHING-WHEN-OFF" not in written
	# A full log is put aside, and only a few old ones are kept, so the folder never grows without end.
	debuglog.setLevel(debuglog.DETAILED)
	for number in range(400):
		debuglog.log("fill", f"entry {number} " + "x" * 100)
	kept = debuglog.files()
	assert kept[0] == path and 2 <= len(kept) <= debuglog.KEPT + 1, kept
	assert all(os.path.getsize(name) <= 5000 + 300 for name in kept), [os.path.getsize(name) for name in kept]
	assert sorted(os.listdir(os.path.dirname(path))) == sorted(os.path.basename(name) for name in kept)
	assert "entry 399" in debuglog.tail(3)
	# One enormous entry is written whole, never cut: the owner reads whole prompts in the log.
	debuglog.log("big", "y" * 30000 + "the end")
	assert ("y" * 30000 + "the end") in debuglog.tail(2) and "left out" not in debuglog.tail(2)

	# --- A fault inside a tool ends its step, not the whole request, and is written down ---
	registry = Registry()

	def broken(task):
		return None.wasInSayAll

	def refuses(task):
		raise ToolError("No command matches.")

	def stopped(task):
		raise taskModule.Cancelled()

	registry.add(Tool("broken", "fails inside", broken))
	registry.add(Tool("refuses", "cannot do it", refuses))
	registry.add(Tool("stopped", "the user stopped it", stopped))
	registry.add(Tool("fine", "works", lambda task, words: f"Found {words}.", {"words": {"type": "string"}}))
	task = taskModule.Task("the time")
	worked, result = registry.call(task, "broken", {})
	assert not worked and "a fault inside VisionClaw (AttributeError" in result and "VisionClaw's log" in result, result
	worked, result = registry.call(task, "refuses", {})
	assert not worked and result == "No command matches."
	try:
		registry.call(task, "stopped", {})
		raise AssertionError("stopping a request must not be swallowed as a fault")
	except taskModule.Cancelled:
		pass
	worked, result = registry.call(task, "fine", {"words": "the clock"})
	assert worked and result == "Found the clock."
	written = debuglog.tail(60)
	assert "tool: ERROR: broken failed" in written and "wasInSayAll" in written
	assert "tool: fine starts. Form: {'words': 'the clock'}" in written and "fine result:\n\tFound the clock." in written
	# Everything a request reports is in the log too.
	task.emit(taskModule.DETAIL, "find_command {\"words\": \"the time\"}")
	assert "task detail: find_command {\"words\": \"the time\"}" in debuglog.tail(3)
	debuglog.stop()
	assert debuglog.path() is None

print("OK")
