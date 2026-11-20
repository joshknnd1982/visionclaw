# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""VisionClaw's own logs read, what went wrong said, and its own code corrected, only when the user asks
(claw/diagnose.py): what the user's words ask, errors read from a log with the place in the code where they happened,
the function around a line, what cannot be corrected while VisionClaw runs, the checks on a correction, what it
changes in words, and a correction put in place of a function of a module made by the test, undone, used again at
start-up for its own version only, and turned off when it fails itself. Plain Python; nothing of VisionClaw's own code
is changed.

  python tests/test_diagnose.py
"""
import json
import os
import shutil
import sys
import tempfile
import textwrap
import types

import harness  # noqa: F401
from visionClaw.claw import diagnose, planner

d = diagnose

# --- What the user asks, and only then ---

for said, do in (
		("fix your bug", d.FIX), ("fix this bug in your code", d.FIX), ("fix the read ahead error in your code", d.FIX),
		("can you repair yourself", d.FIX), ("debug and fix your own code", d.FIX),
		("why did my last request fail", d.WHY), ("diagnose your last error", d.WHY), ("why did you crash", d.WHY),
		("what went wrong with my last request", d.WHY), ("what errors are in your log", d.ERRORS),
		("check your log for errors", d.ERRORS), ("show me the errors in your log", d.ERRORS),
		("which fixes did you make to your own code", d.FIXES), ("undo the fix you made", d.REMOVE),
		("remove the corrections to your own code", d.REMOVE)):
	assert (d.wish(said) or {}).get("do") == do, (said, d.wish(said))
# Words that do not ask it of VisionClaw itself: nothing is read and nothing is corrected.
for said in ("open your log", "show me your log", "fix the add-on", "what went wrong", "why did that fail",
		"turn off typing echo", "fix the error on this form", "fix this page", "what time is it", "fix the spelling",
		"read the error message on the screen", "why does nvda say clickable", "what's wrong with this button"):
	assert d.wish(said) is None, (said, d.wish(said))
assert d.wish("fix the second error in your log")["which"] == 2 and d.wish("diagnose the first error in your log")["which"] == 1
assert d.wish("fix the read ahead error in your code")["about"] == "ahead read"
# The planner sends them to their jobs by plain code, and offers them nowhere else: a model never chooses them alone.
for said, job in (("fix your bug", "fix_self"), ("why did my last request fail", "own_errors"),
		("what errors are in your log", "own_errors"), ("which fixes did you make to your own code", "own_fixes"),
		("show me your log", "visionclaw_log")):
	assert planner.hint(said) == job, (said, planner.hint(said))
for job in ("own_errors", "fix_self", "own_fixes"):
	assert job in planner._SURE and job in planner._WHOLE and planner._NEEDS[job]("turn off typing echo") is None, job

# --- The log ---

ROOT = r"C:\Users\Sam\AppData\Roaming\nvda\addons\visionClaw\globalPlugins\visionClaw"
LOG = textwrap.dedent("""\
	2026-11-19 12:00:00.001 [visionClaw-task] task: New request: 'read ahead please'. Reasoning setting: auto.
	2026-11-19 12:00:01.000 [visionClaw-task] tool: list_items could not do it after 0.20 s: Nothing was found in the window.
	2026-11-19 12:00:02.557 [visionClaw-task] addon: ERROR: VisionClaw: read ahead failed
	\tTraceback (most recent call last):
	\t  File "C:\\Users\\Sam\\AppData\\Roaming\\nvda\\addons\\visionClaw\\globalPlugins\\visionClaw\\__init__.py", line 1849, in _readAhead
	\t    ahead.move(textInfos.UNIT_LINE, READ_AHEAD_LINES, endPoint="end")
	\t    ~~~~~~~~~~^^^^^^^^^
	\t  File "textInfos\\offsets.pyc", line 838, in move
	\t  File "virtualBuffers\\__init__.pyc", line 276, in _getStoryLength
	\tOSError: [WinError 1775] A null context handle was passed
	2026-11-19 12:00:03.000 [visionClaw-task] task: Request ended as failed after 3.0 seconds. Steps: []. Answer: ''
	2026-11-19 12:05:00.000 [MainThread] addon: ERROR: VisionClaw: read ahead failed
	\tTraceback (most recent call last):
	\t  File "C:\\Users\\Sam\\AppData\\Roaming\\nvda\\addons\\visionClaw\\globalPlugins\\visionClaw\\__init__.py", line 1850, in _readAhead
	\t  File "virtualBuffers\\__init__.pyc", line 276, in _getStoryLength
	\tOSError: [WinError 1775] A null context handle was passed
	2026-11-19 12:06:00.000 [MainThread] speech: ERROR: Speech failed inside NVDA
	\tTraceback (most recent call last):
	\t  File "speech\\speech.pyc", line 10, in speak
	\tRuntimeError: no synth
	""")
found = d.errors(LOG)
assert [error.message for error in found] == ["Speech failed inside NVDA", "VisionClaw: read ahead failed"], [e.message for e in found]
ahead = found[1]
assert ahead.count == 2 and ahead.first == "2026-11-19 12:00:02" and ahead.when == "2026-11-19 12:05:00"
# The newest is told: its line fits the code that runs now.
assert d.ownFrame(ahead, ROOT) == ("__init__.py", 1850, "_readAhead")
assert d.ownFrame(found[0], ROOT) is None
assert ahead.request == "read ahead please" and ahead.kind() == "OSError"
assert d.otherCode(ahead, ROOT) == ["virtualBuffers (__init__)"], d.otherCode(ahead, ROOT)
now = 1_795_132_800 + 13 * 3600  # 2026-11-19 in the afternoon, local time does not matter for "today"
told = d.errorText(ahead, ROOT, now=__import__("time").mktime(__import__("time").strptime("2026-11-19 18:00:00", "%Y-%m-%d %H:%M:%S")))
assert told.startswith("VisionClaw: read ahead failed. It happened today at 12:05, 2 times, the first today at 12:00."), told
assert "the function _readAhead in VisionClaw's main file, line 1850" in told and "virtualBuffers" in told
assert d.fileWords("claw/llm.py") == "the file claw/llm.py" and d.fileWords("claw/__init__.py") == "the main file of its folder claw"
assert "OSError: [WinError 1775]" in told and "the request \"read ahead please\"" in told
listed = d.listText(found, ROOT)
assert listed.startswith("VisionClaw's log has 2 different errors, the newest first.") and "inside NVDA's or Python's own code" in listed
assert d.listText([], ROOT) == "VisionClaw's log has no errors."
story = d.lastRequest(LOG)
assert d.storyText(story) == (
	"Your last request, \"read ahead please\", ended as failed after 3.0 seconds. The tool list_items could not do it: "
	"Nothing was found in the window. An error happened: VisionClaw: read ahead failed"), d.storyText(story)
# Which error a request means: the newest, by number, by its words; a correction: the newest in VisionClaw's code.
assert d.chosen(found, {"do": d.WHY}) is found[0]
assert d.chosen(found, {"do": d.FIX}, ROOT) is ahead
assert d.chosen(found, {"do": d.WHY, "which": 2}) is ahead
assert d.chosen(found, {"do": d.WHY, "about": "ahead read"}) is ahead
assert d.own(r"C:\x\globalPlugins\visionClaw\claw\llm.py", ROOT) == "claw/llm.py" and d.own("speech\\speech.pyc", ROOT) == ""
# As Python knows it while VisionClaw runs: globalPlugins.visionClaw inside NVDA, visionClaw in these tests.
assert d.moduleName("claw/llm.py") == d.PACKAGE + ".claw.llm" and d.moduleName("__init__.py") == d.PACKAGE
assert d.PACKAGE == "visionClaw"

# --- VisionClaw's own code: the function around a line, and what cannot be corrected ---

SOURCE = textwrap.dedent('''\
	import re


	def slug(name):
		"""A name for a file."""
		made = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
		return made[:60]


	class Reader:
		count = 0

		def readAhead(self, info):
			moved = info.move(5)
			self.count += moved
			return moved

		def __init__(self):
			def inner():
				return 1
			self.inner = inner

		@staticmethod
		def helper():
			return 2
	''')
place = d.functionAt(SOURCE, 14)
assert (place["qualname"], place["start"], place["end"], place["owner"], place["nested"]) == ("Reader.readAhead", 13, 16, "Reader", False), place
assert d.refusal("reader.py", place) == ""
assert "made inside another" in d.refusal("reader.py", d.functionAt(SOURCE, 20))
assert "only while VisionClaw starts" in d.refusal("reader.py", d.functionAt(SOURCE, 18))
assert "never changes itself" in d.refusal("claw/diagnose.py", place) and "never changes itself" in d.refusal("installTasks.py", place)
assert d.functionAt(SOURCE, 2) is None

# --- A correction, checked by plain code ---

GOOD = textwrap.dedent('''\
	def readAhead(self, info):
		try:
			moved = info.move(5)
		except OSError:
			return 0
		self.count += moved
		return moved
	''')
assert d.checkFix(SOURCE, place, GOOD) == []
for bad, said in (
		("def readAhead(self, info)\n\treturn 0\n", "Syntax error"),
		("def readAhead(self):\n\treturn 0\n", "keep its arguments"),
		("def readBehind(self, info):\n\treturn 0\n", "keep its name"),
		("def readAhead(self, info):\n\timport os\n\treturn 0\n", "Do not add imports"),
		("def readAhead(self, info):\n\tos.remove('x')\n\treturn 0\n", "Do not add remove"),
		("def readAhead(self, info):\n\treturn eval('1')\n", "Do not add eval"),
		(textwrap.dedent(place["text"]), "the function as it was"),
		("x = 1\ndef readAhead(self, info):\n\treturn 0\n", "only the one function"),
		("@staticmethod\ndef readAhead(self, info):\n\treturn 0\n", "Leave out the lines above"),
		("def readAhead(self, info):\n" + "".join(f"\tx{n} = {n}\n" for n in range(40)) + "\treturn 0\n", "changes too much")):
	problems = d.checkFix(SOURCE, place, bad)
	assert problems and said in " ".join(problems), (bad, problems)
assert d.extractFunction("Here it is:\n```python\n" + GOOD + "```\nDone.") == GOOD
assert d.extractFunction("    def readAhead(self, info):\n        return 0") == "def readAhead(self, info):\n    return 0\n"
assert d.extractFunction("no code at all") == ""
whole = d.replaced(SOURCE, place, GOOD)
compile(whole, "x", "exec")
assert "\t\ttry:\n\t\t\tmoved = info.move(5)\n\t\texcept OSError:" in whole
change = d.changeText(place["text"], GOOD)
assert change == "It adds 4 lines and takes out 1. When the error OSError happens there, it now stops that piece of work quietly.", change
assert "It now also calls notify." in d.changeText("def f():\n\treturn 1\n", "def f():\n\tnotify()\n\treturn 1\n")
assert "it now catches it and goes on." in d.changeText("def f(i):\n\ti.move()\n", "def f(i):\n\ttry:\n\t\ti.move()\n\texcept OSError:\n\t\tpass\n")
assert d._superFixed("def m(self):\n\tsuper().m()\n", "Reader") == "def m(self):\n\tsuper(Reader, self).m()\n"
# A model that indents with spaces where the file uses tabs: plain code writes tabs (measured with Qwen3.5 4B).
spaced = GOOD.replace("\t", "    ")
assert d.tidy(spaced, place) == GOOD and d.checkFix(SOURCE, place, d.tidy(spaced, place)) == []
assert d.tidy("def f():\n  return 1\n", place) == "def f():\n\treturn 1\n"
# A method's body copied as it stood in its class, under a def line at the left edge (measured with Qwen3.5 4B).
assert d.bodyAligned("def f(self):\n\t\tx = 1\n\t\treturn x\n") == "def f(self):\n\tx = 1\n\treturn x\n"
assert d.bodyAligned("def f(self):\n\tx = 1\n") == "def f(self):\n\tx = 1\n"
# The model is shown the function from the left edge.
assert "```python\ndef readAhead(self, info):\n\tmoved" in d.facts(ahead, ROOT, SOURCE, place)

# --- Put in place, undone, used again at start-up for its own version only, turned off when it fails ---

folder = tempfile.mkdtemp()
root = tempfile.mkdtemp()
try:
	os.makedirs(os.path.join(root, "claw"))
	with open(os.path.join(root, "claw", "reader.py"), "w", encoding="utf-8") as f:
		f.write(SOURCE)
	module = types.ModuleType(d.moduleName("claw/reader.py"))
	exec(compile(SOURCE, "reader.py", "exec"), module.__dict__)
	other = types.ModuleType(d.moduleName("claw/user.py"))
	other.slug = module.slug  # took it in by its name: "from .reader import slug"
	modules = {module.__name__: module, other.__name__: other}
	fixes = d.Fixes(folder, root, "1.17.0", modules=modules, load=lambda name: (_ for _ in ()).throw(ImportError(name)))
	readAhead = module.Reader.readAhead

	class Info:
		def __init__(self, fails):
			self.fails = fails

		def move(self, count):
			if self.fails:
				raise OSError("the page is gone")
			return count

	reader = module.Reader()
	try:
		reader.readAhead(Info(True))
		raise AssertionError("the bug must be there before")
	except OSError:
		pass
	fix = d.Fix(id="fix-1-readAhead", file="claw/reader.py", qualname="Reader.readAhead", version="1.17.0",
		oldDigest=d.digest(place["text"]), old=place["text"], new=GOOD, error="VisionClaw: read ahead failed (OSError)",
		made="2026-11-19 18:00:00")
	worked, why = fixes.add(fix, d.report(fix, "facts", "", "It adds 4 lines.", "No problem found."))
	assert worked, why
	assert reader.readAhead(Info(True)) == 0 and reader.readAhead(Info(False)) == 5 and reader.count == 5
	assert getattr(module.Reader.readAhead, "__visionclawFix__") == "fix-1-readAhead"
	stored = json.load(open(os.path.join(folder, d.FIXES_FILE), encoding="utf-8"))
	assert stored[0]["state"] == "on" and stored[0]["new"] == GOOD
	report = open(os.path.join(folder, "fix-1-readAhead.md"), encoding="utf-8").read()
	assert report.startswith("# VisionClaw's correction of Reader.readAhead") and "## The function as it was" in report
	assert "VisionClaw's own files were not changed" in report
	# VisionClaw's own file is as it was.
	assert open(os.path.join(root, "claw", "reader.py"), encoding="utf-8").read() == SOURCE
	assert "Reader.readAhead in the file claw/reader.py" in fixes.text() and "It is in use." in fixes.text()
	# Undone: the function as it was is used again.
	assert fixes.remove(fix.id).state == "undone" and module.Reader.readAhead is readAhead
	assert "It is undone." in fixes.text()
	# Used again when VisionClaw starts: for its own version, while the code is still as it was.
	fixes._set(fix.id, state="on")
	again = d.Fixes(folder, root, "1.17.0", modules=modules)
	assert again.startUp() == (1, 0) and reader.readAhead(Info(True)) == 0
	again.takeAway(fix.id)
	assert d.Fixes(folder, root, "1.18.0", modules=modules).startUp() == (0, 1)
	assert "It is put aside: It was made for VisionClaw 1.17.0, and this is 1.18.0." in fixes.text(), fixes.text()
	assert module.Reader.readAhead is readAhead
	# A module-level function is given to the modules that took it in by its name too.
	slugPlace = d.functionAt(SOURCE, 6)
	slugFix = d.Fix(id="fix-2-slug", file="claw/reader.py", qualname="slug", version="1.17.0",
		oldDigest=d.digest(slugPlace["text"]), old=slugPlace["text"], made="2026-11-19 18:01:00", error="x",
		new='def slug(name):\n\tmade = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")\n\treturn made[:10]\n')
	worked, why = fixes.add(slugFix, "report")
	assert worked, why
	assert module.slug("a" * 30) == "a" * 10 and other.slug("a" * 30) == "a" * 10
	fixes.remove(slugFix.id)
	assert module.slug("a" * 70) == "a" * 60 and other.slug("a" * 70) == "a" * 60
	# A correction that fails itself turns itself off: the error is passed on once, then the old function is used.
	broken = d.Fix(id="fix-3-readAhead", file="claw/reader.py", qualname="Reader.readAhead", version="1.17.0",
		oldDigest=d.digest(place["text"]), old=place["text"], made="2026-11-19 18:02:00", error="x",
		new="def readAhead(self, info):\n\treturn info.missing()\n")
	assert fixes.add(broken, "report")[0]
	try:
		reader.readAhead(Info(False))
		raise AssertionError("the failing correction's error is passed on")
	except AttributeError:
		pass
	assert reader.readAhead(Info(False)) == 5  # the old function, from now on
	assert next(fix for fix in fixes.all() if fix.id == broken.id).state == "failed"
	assert "turned off, because it failed itself: AttributeError" in fixes.text(), fixes.text()
	fixes.takeAway(broken.id)
	# What the work of a function raises in the ordinary course is no failure of a correction.
	Cancelled = type("Cancelled", (Exception,), {})
	calls = []
	wrapper = d.guarded(broken, lambda: calls.append("old"), lambda: (_ for _ in ()).throw(Cancelled()), lambda f, e: calls.append("failed"))
	for _round in range(2):
		try:
			wrapper()
		except Cancelled:
			pass
	assert calls == [], calls
	# A correction for code that has changed since is not put in place.
	changed = d.Fix(**dict(fix.asDict(), id="fix-4", oldDigest="0" * 64))
	assert d.Fixes(folder, root, "1.17.0", modules=modules).apply(changed)[0] is False
	# A part of VisionClaw that is not loaded and cannot be loaded: not put in place, and said.
	lost = d.Fix(**dict(fix.asDict(), id="fix-5"))
	assert d.Fixes(folder, root, "1.17.0", modules={}, load=lambda name: (_ for _ in ()).throw(ImportError(name))).apply(lost) == (
		False, "The part of VisionClaw that has Reader.readAhead is not loaded.")
	# Not a plain function: refused.
	static = d.Fix(**dict(fix.asDict(), id="fix-6", qualname="Reader.helper",
		oldDigest=d.digest(d.functionAt(SOURCE, 25)["text"])))
	assert d.Fixes(folder, root, "1.17.0", modules=modules).apply(static)[0] is False
finally:
	shutil.rmtree(folder, ignore_errors=True)
	shutil.rmtree(root, ignore_errors=True)

# --- A complaint about what VisionClaw just did, with no error in the log ---
# The owner said on 2026-11-19, after the focus landed on Make screen black instead of the Logging level combo box:
# "visionclaw must be able to fix such focus and other bugs by itself ... when I complain about a problem like this."

for said in (
		"you opened NVDA's settings but the focus went to Make screen black instead of the Logging level combo box",
		"the focus landed on make screen black instead of the logging level combo box, fix it",
		"you put the focus on the wrong control, it should have been the logging level combo box",
		"you selected the first item instead of Documents", "there's a bug, you opened the wrong settings page",
		"visionclaw is broken, it keeps reading the wrong line", "you were supposed to open the system tray, not the start menu",
		"you said the volume is 0.5 percent but it is at half", "can you fix it, you put the focus on the wrong control",
		"it didn't work"):
	want = d.wish(said)
	assert want and want["do"] == d.FIX and want["complaint"] == said, (said, want)
	assert planner.hint(said) == "fix_self", (said, planner.hint(said))
# Asked why: answered, and nothing is corrected.
said = "why did the focus go to make screen black instead of the logging level combo box"
assert d.wish(said)["do"] == d.WHY and d.wish(said)["complaint"] and planner.hint(said) == "own_errors"
# No complaint: a request to do something, a question, someone else's doing, a correction, the user's own key press, an
# add-on VisionClaw made (fix_addon), and the words that asked before.
for said in ("the focus is on the wrong control, press Tab", "move the focus to the OK button", "this button doesn't work",
		"NVDA keeps saying every word I type, make it stop", "my printer doesn't work", "what's wrong with this button",
		"no, I meant turn off the typing echo", "you opened the wrong window, open Notepad instead", "Word is broken",
		"the focus went to the wrong place when I pressed tab", "it should be louder", "did you put the focus in the wrong place?",
		"I think you should have a look at my screen", "that didn't work, try again", "undo that, it was wrong",
		"you're speaking too fast", "the add-on you made doesn't work, fix it", "what time is it"):
	assert d.complaintOf(said) is None, said
	assert not (d.wish(said) or {}).get("complaint"), said
for said in ("fix that bug in your code", "fix your bug", "why did my last request fail", "what went wrong with my last request"):
	assert d.wish(said)["complaint"] == "", said
assert planner.hint("the focus is on the wrong control, press Tab") != "fix_self"
assert planner.hint("the add-on you made doesn't work, fix it") == "fix_addon"
# The skill for it starts on a complaint too, and only for its own jobs.
from visionClaw.claw.skills import Skills  # noqa: E402
lib = Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
for said in ("you put the focus on the wrong control", "the focus landed on make screen black instead of the logging level combo box"):
	assert "fix-visionclaw" in [skill.slug for skill in lib.choose(said)], said
assert "fix-visionclaw" not in [skill.slug for skill in lib.choose("use Word instead of Notepad")]

# What the requests before did: from the log, and as the orchestrator keeps them in memory.
STORY_LOG = textwrap.dedent("""\
	2026-11-19 13:00:00.000 [visionClaw-task] task: New request: 'check NVDA\\'s log'. Reasoning setting: auto.
	2026-11-19 13:00:00.100 [visionClaw-task] tool: nvda_log starts. Form: {'asked': "check NVDA's log"}
	2026-11-19 13:00:01.000 [visionClaw-task] ask: Asking the user: Open NVDA's settings? Choices: ['Yes, open them', 'No']
	2026-11-19 13:00:02.000 [visionClaw-task] ask: The user chose: Yes, open them
	2026-11-19 13:00:02.100 [visionClaw-task] tool: nvda_log worked after 2.00 s.
	2026-11-19 13:00:02.100 [visionClaw-task] tool: nvda_log result:
	\tNVDA's settings are open.
	\tPress Tab.
	2026-11-19 13:00:02.200 [visionClaw-task] task: Request ended as done after 2.2 seconds. Steps: [('nvda_log', 'done')]. Answer: "NVDA's settings are open. Press Tab."
	""")
stories = d.requests(LOG + STORY_LOG)
assert [story["request"] for story in stories] == ["read ahead please", "check NVDA's log"], stories
assert stories[-1]["steps"] == [{"tool": "nvda_log", "status": "done", "result": "NVDA's settings are open.\nPress Tab."}], stories[-1]
assert stories[-1]["asked"] == [["Open NVDA's settings?", "Yes, open them"]] and stories[-1]["answer"] == "NVDA's settings are open. Press Tab."
assert d.lastRequest(LOG + STORY_LOG)["request"] == "check NVDA's log"
step = types.SimpleNamespace(tool="nvda_log", title="Reading NVDA's own log", status="done", result="Opened.")
kept = d.record(types.SimpleNamespace(request="check NVDA's log", original="check nvda log", answer="Opened.", state="done",
	steps=[step]), 12.0)
assert kept["said"] == "check nvda log" and kept["steps"][0]["tool"] == "nvda_log" and kept["when"] == 12.0
# Which request a complaint is about: the newest that was not itself about VisionClaw's own code. "Fix that bug" right
# after a complaint VisionClaw was asked why about carries that complaint.
why = {"said": "why did the focus go to make screen black instead of the logging level combo box", "steps": [{"tool": "own_errors"}]}
assert d.complaintTarget([why, kept], "") == (why["said"], kept)
assert d.complaintTarget([kept], "you put the focus on the wrong control") == ("you put the focus on the wrong control", kept)
assert d.complaintTarget([kept], "") == ("", None) and d.complaintTarget([why], "x")[1] is None
assert "The step nvda_log (Reading NVDA's own log) ended as done: Opened." in d.doneText(kept)
assert "VisionClaw answered" not in d.doneText(kept)  # the answer is the step's own result, said once
assert d.aboutText("it was wrong", stories[-1]) == "You said: \"it was wrong\" That is about your request \"check NVDA's log\", " + d.ago("2026-11-19 13:00:00") + "."

# The functions a tool uses, found in modules made by the test without running anything: through its closure, a local
# name, an import inside it, "self", a module's name; a function made inside the tool is no level.
HELPERS = textwrap.dedent('''\
	from . import selfother


	def shown(name):
		"""What is said of a name."""
		return f"Shown {name}."


	def opener(path):
		"""Opens a page of the settings."""
		return selfother.focusOn(path)


	class Store:
		def __init__(self):
			self.items = []

		def add(self, name):
			self.items.append(self._clean(name))
			return shown(name)

		def _clean(self, name):
			return name.strip()


	def register(add, plugin):
		def helper(word):
			return shown(word)

		def tool(task, asked):
			store = plugin.store
			store.add(asked)
			from .selfother import later
			later()
			return helper(asked) + opener(asked)

		add("tool", tool)
	''')
OTHER = textwrap.dedent('''\
	def focusOn(path):
		"""Puts the focus on a control."""
		return deeper(path)


	def deeper(path):
		return path


	def later():
		return 1
	''')
root = tempfile.mkdtemp()
made = {}
try:
	for name, text in (("selfother", OTHER), ("selfhelpers", HELPERS)):
		with open(os.path.join(root, f"{name}.py"), "w", encoding="utf-8") as f:
			f.write(text)
		made[name] = types.ModuleType(f"visionClaw.{name}")
		made[name].__package__ = "visionClaw"
		sys.modules[made[name].__name__] = made[name]
		exec(compile(text, os.path.join(root, f"{name}.py"), "exec"), made[name].__dict__)
	tools = {}
	plugin = types.SimpleNamespace(store=made["selfhelpers"].Store())
	made["selfhelpers"].register(lambda name, function: tools.setdefault(name, function), plugin)
	read = lambda relative: open(os.path.join(root, *relative.split("/")), encoding="utf-8").read()  # noqa: E731
	found = d.usedFunctions(tools["tool"], read, root, sys.modules)
	depths = {entry["qualname"]: entry["depth"] for entry in found}
	assert depths == {"register.tool": 0, "register.helper": 0, "Store.add": 1, "later": 1, "opener": 1, "shown": 1,
		"Store._clean": 2, "focusOn": 2}, depths
	assert found[0]["qualname"] == "register.tool" and "made inside another" in found[0]["refusal"]
	byName = {entry["qualname"]: entry for entry in found}
	assert byName["Store._clean"]["refusal"] == "" and byName["focusOn"]["file"] == "selfother.py"
	assert any(caller == "opener" and "selfother.focusOn(path)" in around for caller, around in byName["focusOn"]["uses"])
	# Ranked by the complaint's words: what the function is called and says it does counts most.
	offered = d.fitting(found, "you put the focus on the wrong control")
	assert offered and offered[0]["qualname"] == "focusOn", [entry["qualname"] for entry in offered]
	assert all(not entry["refusal"] for entry in offered) and len(offered) <= d.MAX_OFFERED
	assert d.fitting(found, "it was wrong") == [] and d.fitting(found, "it was wrong", "Shown Sam.")[0]["qualname"] == "shown"
	question = d.chooseQuestion("you put the focus on the wrong control", "The request \"go\".", offered)
	assert question.startswith("The user said: \"you put the focus on the wrong control\"") and "1. focusOn in selfother.py, used by opener" in question
	assert d.chooseSchema(3, True)["properties"]["number"]["enum"] == [0, 1, 2, 3] and d.chooseSchema(3, False)["properties"]["number"]["enum"] == [1, 2, 3]
	assert "Give 0" not in d.CHOOSE_SYSTEM and "for example" not in (d.CHOOSE_SYSTEM + d.COMPLAINT_FIX_TASK).lower()
	facts = d.complaintFacts("you put the focus on the wrong control", "The request \"go\".", offered[0], ["X, a class of gui."])
	assert "def focusOn(path):" in facts and "Where opener uses it:" in facts and "- X, a class of gui." in facts

	# What the running program has for the names a function uses: a class of NVDA's, with what its code sets on each
	# object, the complaint's words first; read from loaded modules only, nothing imported or called.
	panels = types.ModuleType("gui.panels")
	exec(compile(textwrap.dedent('''\
		class Base:
			def __init__(self):
				self.parent = None
				self.makeSettings()

		class Panel(Base):
			def makeSettings(self):
				self.first = 1
				self._levelCombo = 2
				def later():
					self.lateName = 3
				later()

			def onSave(self):
				pass
		'''), "gui/panels.py", "exec"), panels.__dict__)
	assert d.storedAttributes(panels.Panel) == ["first", "_levelCombo", "lateName", "parent"], d.storedAttributes(panels.Panel)
	source = "def openIt():\n\tfrom gui.panels import Panel\n\treturn Panel\n"
	space = {"__package__": "visionClaw", "__name__": "visionClaw.opener"}
	exec(compile(source, "opener.py", "exec"), space)
	place = d.allPlaces(source)[0]
	said = d.namesFacts(space["openIt"], place, {"gui.panels": panels}, "the level combo box")
	assert said == ["Panel, a class of gui.panels. Its code sets on each object: _levelCombo, first, lateName, parent. Its methods: "
		"makeSettings, onSave."], said
	assert d.namesFacts(space["openIt"], place, {}, "") == []  # not loaded: nothing is imported
	# Names a correction uses that the running program does not have: said to the model, with the close ones.
	gui = types.ModuleType("gui")
	gui.mainFrame = types.SimpleNamespace(popupSettingsDialog=lambda *args: None)
	space["gui"] = gui
	said = d.unknownNames("def openIt():\n\tfrom gui.panels import Panel\n\tgui.mainFrame.getFocus()\n\tPanel.makeSetings()\n"
		"\treturn missing\n", space["openIt"], {"gui.panels": panels})
	assert sorted(said) == ["Panel.makeSetings does not exist in the running NVDA: Panel has nothing called makeSetings. Names it "
		"has that are close: makeSettings.",
		"gui.mainFrame.getFocus does not exist in the running NVDA: gui.mainFrame has nothing called getFocus.",
		"missing is used but never imported or defined."], said
	# A name the class's code sets on each object it makes is said to be on such an object, not on the class.
	assert d.unknownNames("def openIt():\n\tfrom gui.panels import Panel\n\treturn Panel._levelCombo\n", space["openIt"],
		{"gui.panels": panels}) == ["Panel._levelCombo is not on the class Panel: its code sets _levelCombo on each object of it "
		"that is made, so it is found on such an object, not on the class."]
	# A name the function gives a value itself is not judged: it cannot be told without running it; nor is a name of
	# something that makes its names when asked (__getattr__).
	assert d.unknownNames("def openIt():\n\tgui = 1\n\tgui.anything()\n\tfor x in []:\n\t\tx.y\n", space["openIt"], {}) == []
	gui.mainFrame = type("Dispatch", (), {"__getattr__": lambda self, name: 1})()
	assert d.unknownNames("def openIt():\n\tgui.mainFrame.getFocus()\n", space["openIt"], {}) == []
	# What its class gives when asked counts: wx's classes load their methods when first asked for.
	lazy = type("LazyType", (type,), {"__getattr__": lambda cls, name: (lambda self: None) if name == "SetFocus" else (_ for _ in ()).throw(AttributeError(name))})
	gui.mainFrame = lazy("Frame", (), {})()
	assert d.unknownNames("def openIt():\n\tgui.mainFrame.SetFocus()\n\tgui.mainFrame.getFocus()\n", space["openIt"], {}) == [
		"gui.mainFrame.getFocus does not exist in the running NVDA: gui.mainFrame has nothing called getFocus."]
finally:
	for name in made:
		sys.modules.pop(f"visionClaw.{name}", None)
	shutil.rmtree(root, ignore_errors=True)

# A correction made from a complaint: checked with its own words, kept with what the user said, and reported; what could
# not be corrected is written as a report for VisionClaw's developer.
assert "it would do the same again" in " ".join(d.checkFix(SOURCE, place_ := d.functionAt(SOURCE, 14), textwrap.dedent(place_["text"]), True))
folder = tempfile.mkdtemp()
try:
	fixes = d.Fixes(folder, tempfile.gettempdir(), "1.18.0")
	fix = d.Fix(id="fix-7-openPanel", file="nvdalogtools.py", qualname="openPanel", version="1.18.0", old="def openPanel():\n\tpass\n",
		new="def openPanel():\n\treturn 1\n", error="What you said was wrong: the focus went to the wrong control",
		complaint="the focus went to the wrong control", made="2026-11-19 18:00:00")
	fixes._save([fix])
	assert "openPanel in the file nvdalogtools.py" in fixes.text() and "for what you said was wrong: the focus went to the wrong control." in fixes.text()
	written = d.report(fix, "facts", "The model chose openPanel.", "It adds 1 lines.", "")
	assert "## What you said was wrong\n\nthe focus went to the wrong control" in written and "## How this function was chosen" in written
	name = fixes.note("report-20261119-180000", d.complaintReport("it was wrong", "The request \"go\".", [], "Nothing fits.", "1.18.0", ["nvda_log"]))
	assert name == "report-20261119-180000.md"
	text = open(os.path.join(folder, name), encoding="utf-8").read()
	assert text.startswith("# What VisionClaw could not correct by itself") and "Nothing was changed." in text and "nvda_log" in text
	# An older list without complaints is read as before.
	assert d.Fix(**{key: value for key, value in fix.asDict().items() if key != "complaint"}).complaint == ""
finally:
	shutil.rmtree(folder, ignore_errors=True)

print("test_diagnose: OK")
