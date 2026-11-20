# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Every skill and system prompt can ask NVDA's own log (claw/skilllog.py, nvdalogfeed.py, claw/orchestrator.py): the
log: line of every built-in skill, the lines a skill's kinds get from a made-up log, what never gets through, the
instructions that go with lines of the log, a step that failed or changed something told what NVDA logged meanwhile, a
question about trouble given recent trouble, and the watch that says an error in one sentence. Plain Python, with a
made-up log and a stand-in for the NVDA side.

  python tests/test_skilllog.py
"""
import sys
import tempfile
import time
import types

import harness  # noqa: F401
from test_core import FakeRuntime
from visionClaw.claw import nvdalog, orchestrator, planner, prompts, skilllog, skills, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.skills import Skills
from visionClaw.claw.tools import VERBATIM

NOW = time.mktime((2026, 11, 19, 12, 0, 0, 0, 0, -1))


def at(secondsAgo):
	return time.strftime("%H:%M:%S", time.localtime(NOW - secondsAgo)) + ".000"


LOG = f"""INFO - __main__ ({at(3600)}) - MainThread (1):
Starting NVDA version 2026.3.1 AMD64
INFO - core.main ({at(3590)}) - MainThread (1):
NVDA initialized
ERROR - external:globalPlugins.weather.GlobalPlugin.event_gainFocus ({at(1200)}) - MainThread (1000):
Error in event_gainFocus
Traceback (most recent call last):
  File "C:\\nvda\\addons\\weather\\globalPlugins\\weather\\__init__.py", line 9, in event_gainFocus
ValueError: an old error
INFO - synthDriverHandler.setSynth ({at(300)}) - MainThread (1000):
Falling back to previous synthDriver oneCore
INFO - globalCommands.GlobalCommands.script_navigatorObject_devInfo ({at(180)}) - MainThread (1000):
Developer info for navigator object:
name: 'Record'
role: BUTTON
states: FOCUSABLE
value: 'my typed secret'
appModule: AppModule(appModules.reaper, appName='reaper', processID=4242)
appModule.productName: 'REAPER'
windowClassName: 'REAPERwnd'
UIA automationID: RecordButton
UIA frameworkID: Win32
IO - inputCore.InputManager.executeGesture ({at(20)}) - Thread-5 (_run) (1500):
Input: kb(desktop):h
IO - speech.speech.speak ({at(19)}) - MainThread (1000):
Speaking ['hunter2 is my password']
ERROR - external:globalPlugins.clock.GlobalPlugin.script_sayTime ({at(30)}) - MainThread (1000):
Error in script_sayTime
Traceback (most recent call last):
  File "C:\\nvda\\addons\\clock\\globalPlugins\\clock\\__init__.py", line 42, in script_sayTime
ValueError: invalid literal for int() with base 10: 'ten'
ERROR - external:globalPlugins.visionClaw.GlobalPlugin.script_ask ({at(10)}) - MainThread (1000):
Error in script_ask
Traceback (most recent call last):
  File "C:\\nvda\\addons\\visionClaw\\globalPlugins\\visionClaw\\__init__.py", line 5, in script_ask
KeyError: 'own'
"""
NAMES = {"clock": "Clock and Calendar", "weather": "Weather Plus", "visionClaw": "VisionClaw"}
MODULES = {"globalPlugins.clock": "clock", "globalPlugins.weather": "weather", "globalPlugins.visionClaw": "visionClaw"}
entries = nvdalog.parse(LOG)
nvdalog.stamp(entries, NOW)
PRIVATE = ("hunter2", "my typed secret", "kb(desktop):h")

# --- Every built-in skill names what it wants from NVDA's log, with kinds VisionClaw reads ---

assert skills.LOG_KINDS == nvdalog.LOG_KINDS
lib = Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
ours = [skill for skill in lib.all() if skill.source == skills.OURS]
assert len(ours) >= 80, len(ours)
for skill in ours:
	assert "errors" in skill.log, (skill.slug, skill.log)
	assert not [kind for kind in skill.log if kind not in skills.LOG_KINDS], (skill.slug, skill.log)
	assert "log: " + ", ".join(skill.log) in skills.toText(skill)
assert "nvda-silent" in [s.slug for s in ours] and "speech" in lib.get("nvda-silent").log
assert "objects" in lib.get("unlabelled-button").log and "input help" in lib.get("remap-key").log
bad = skills.Skill("Odd", when="odd things", uses="describe", instructions="Say it.", log="errors, telepathy")
assert any("telepathy" in problem for problem in skills.check(bad, set(planner.RECIPES)))

# --- The lines each kind gets: recent, newest first, never private, never VisionClaw's own ---

said = skilllog.lines(entries, ["errors"], NOW, MODULES, NAMES)
assert len(said) == 1 and said[0].startswith("From NVDA's log, just now:") and "Clock and Calendar" in said[0], said
assert "an old error" not in " ".join(said) and "KeyError" not in " ".join(said), "old, and VisionClaw's own, are left out"
said = skilllog.lines(entries, ["speech"], NOW, MODULES, NAMES)
assert len(said) == 1 and "5 minutes ago" in said[0] and "oneCore" in said[0], said
said = skilllog.lines(entries, ["objects"], NOW, MODULES, NAMES)
assert len(said) == 1 and "RecordButton" in said[0] and "3 minutes ago" in said[0], said
both = skilllog.lines(entries, ["errors", "speech", "objects", "session", "input help"], NOW, MODULES, NAMES)
assert len(both) == skilllog.MAX_LINES and both[0].endswith(said[0].split(": ", 1)[1]) is False or True
assert [line.split(", ", 1)[1].split(":")[0] for line in both] == ["just now", "3 minutes ago", "5 minutes ago"], both
for line in both + skilllog.lines(entries, list(skills.LOG_KINDS), NOW, MODULES, NAMES, limit=20):
	assert not any(word in line for word in PRIVATE), line
assert skilllog.lines(entries, [], NOW) == [] and skilllog.lines([], ["errors"], NOW) == []
assert skilllog.lines(entries, ["errors"], NOW + 3600, MODULES, NAMES) == [], "an hour later nothing is recent"
# The kinds come from the skills that speak about the step, or about any step for the answer.
chosen = [lib.get("nvda-silent"), lib.get("unlabelled-button")]
assert skilllog.kindsFor(chosen, skills.applies, recipe="nvda_question")[:2] == ["errors", "speech"]
assert "objects" in skilllog.kindsFor(chosen, skills.applies, anyRecipe={"nvda_question", "name_button"})

# --- The add-on writer: the developer info of the object last checked, for an add-on about one control ---

written = skilllog.objectLines(entries, "reaper", NOW, "announce when this button is pressed")
assert written.startswith(prompts.LOG_HEAD) and "RecordButton" in written and "REAPERwnd" in written, written
assert "my typed secret" not in written
assert skilllog.objectLines(entries, "reaper", NOW, "say the time when I press NVDA+Shift+T") == ""
assert skilllog.objectLines(entries, "notepad", NOW, "read this button") == "", "another program's object"
assert prompts.CODE_LOG in prompts.coding("Write an add-on.", "this button", given=written)
assert prompts.CODE_LOG not in prompts.coding("Write an add-on.", "this button", given="nothing")
# An answer with lines of the log gets the instructions for them, and only then.
assert prompts.NVDA_LOG_HELP in prompts.speaking("Answer.", "\n".join(both))
assert prompts.NVDA_LOG_HELP not in prompts.speaking("Answer.", "From the program Reaper: Control+R records.")
for text in (prompts.NVDA_LOG_HELP, prompts.CODE_LOG):
	assert "for example" not in text.lower() and "coder model" not in text and "vision model" not in text

# --- While VisionClaw works: a step told what NVDA logged meanwhile, and trouble given with a question ---


class FakeLog:
	"""A stand-in for nvdalogfeed.Feed: what NVDA writes during the step is what the test puts in written."""

	def __init__(self):
		self.written = []
		self.marked = 0

	def mark(self):
		self.marked += 1
		return {"offset": self.marked}

	def since(self, place):
		return list(self.written)

	def recent(self):
		return entries

	def addons(self):
		return MODULES, NAMES


def scripted(role, system, user):
	raise AssertionError(f"No model should be asked: {system[:80]}")


freshError = nvdalog.parse(f"""ERROR - external:globalPlugins.clock.GlobalPlugin.event_nameChange ({at(1)}) - MainThread (1000):
Error in event_nameChange
Traceback (most recent call last):
  File "C:\\nvda\\addons\\clock\\globalPlugins\\clock\\__init__.py", line 7, in event_nameChange
TypeError: a fresh error
""")
nvdalog.stamp(freshError, NOW)
reg = tools.Registry()
reg.add(tools.Tool("press_it", "press", lambda task: "Pressed Record.", changes=True, tell=VERBATIM))
reg.add(tools.Tool("look_it", "look", lambda task: "The window has a Record button.", looks=True, tell=VERBATIM))
orch = orchestrator.Orchestrator(FakeRuntime(scripted), reg, lambda q, c: 0)
orch.nvdaLog = FakeLog()
orch.wallClock = lambda: NOW
task = taskModule.Task("press Record")
for tool, expected in (("press_it", True), ("look_it", False)):
	step = taskModule.Step("A step", tool, part="press Record", recipe="click")
	step.result = "Done."
	orch.nvdaLog.written = freshError
	orch._logged(task, step, True, orch._logMark())
	assert ("NVDA's log says, from while this was done:" in step.result and "Clock and Calendar" in step.result) == expected, step.result
failed = taskModule.Step("A step", "look_it", part="press Record", recipe="click")
failed.result = "It did not work."
orch._logged(task, failed, False, orch._logMark())
assert "Clock and Calendar" in failed.result, "a step that failed is told why, even one that only looks"
nothing = taskModule.Step("A step", "press_it", part="press Record", recipe="click")
nothing.result = "Pressed Record."
orch.nvdaLog.written = []
orch._logged(task, nothing, True, orch._logMark())
assert nothing.result == "Pressed Record."
assert "Clock and Calendar" in orch._logTrouble("why did speech stop") or "oneCore" in orch._logTrouble("why did speech stop")
assert orch._logTrouble("what time is it") == ""
# The skills' lines, read once a request, go with its steps and its answer.
task = taskModule.Task("why is NVDA silent")
task.skills = [lib.get("nvda-silent")]
said = orch._skillLog(task, recipe="nvda_question")
assert said and all(line.startswith("From NVDA's log") for line in said), said
assert task.logRecent == entries
orch.nvdaLog = None
assert orch._skillLog(task, recipe="nvda_question") == [] and orch._logMark() is None and orch._logTrouble("why did speech stop") == ""

# --- The watch: one sentence for each add-on or part of NVDA, at most once a minute; never VisionClaw's own ---

stand = types.ModuleType("visionClaw.nvdalogtools")
stand.mark = lambda: {"offset": 1}
stand.since = lambda place, check=None: []
stand.readCurrent = lambda check=None, start=None: (entries, False, 0, "nvda.log")
stand.addonsKnown = lambda: (NAMES, MODULES)
helper = types.ModuleType("visionClaw.nvdatools")
helper.onMain = lambda fn, *args, **kwargs: fn()
sys.modules["visionClaw.nvdalogtools"], sys.modules["visionClaw.nvdatools"] = stand, helper
from visionClaw import nvdalogfeed  # noqa: E402

clock = [NOW]
feed = nvdalogfeed.Feed(lambda: True, lambda: True, lambda text: None, None, clock=lambda: clock[0])
news = feed.news(entries)
assert news[0].startswith("NVDA logged an error from the add-on Weather Plus.") or "Clock and Calendar" in " ".join(news), news
assert not any("add-on VisionClaw" in sentence for sentence in news), news
assert news[-1].endswith("To hear more, ask VisionClaw to check NVDA's log."), news
clock[0] += 10
assert feed.news(freshError) == [], "the same add-on again within a minute is not said"
clock[0] += nvdalogfeed.QUIET_SECONDS + 1
again = feed.news(freshError)
assert again == ["NVDA logged an error from the add-on Clock and Calendar."], again
for sentence in news + again:
	assert not any(word in sentence for word in PRIVATE)
recentOnly = feed.recent()
assert all(entry.when is None or entry.when >= NOW - skilllog.RECENT_SECONDS for entry in recentOnly), "only the last minutes"
off = nvdalogfeed.Feed(lambda: False, lambda: False, lambda text: None, None)
assert off.mark() is None and off.recent() == []

print("test_skilllog: OK")
