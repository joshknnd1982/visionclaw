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

print("test_diagnose: OK")
