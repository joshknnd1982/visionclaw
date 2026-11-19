# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""An add-on written piece by piece, and the work sheet every request is fed from (claw/codeplan.py,
claw/worksheet.py). Plain Python: scripted models, and stand-ins for NVDA's modules that the generated add-ons run
against.

  python tests/test_codeplan.py
"""
import os
import shutil
import sys
import tempfile
import types

import addonstandin as standin
import harness  # noqa: F401
from visionClaw.claw import codeplan, microaddons, planner, policy, worksheet
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.task import Step
from visionClaw.claw.tools import ToolError

# --- Reading a request into pieces ---

HERE = "Program: notepad. Window title: notes.txt - Notepad."


def read(text, facts=HERE):
	pieces, why = codeplan.read(text, facts)
	return pieces, why


pieces, _why = read("Say hello when I press NVDA+shift+H.")
assert [(p.kind, p.gesture, p.action) for p in pieces] == [("key", "kb:NVDA+shift+h", "Say hello")], pieces
pieces, _why = read("Beep when a link gets the focus.")
assert [(p.kind, p.event, p.role, p.action) for p in pieces] == [("event", "gainFocus", "LINK", "Beep")], pieces
pieces, _why = read("In notepad, say the name of the focused control when I press NVDA+shift+N.")
assert pieces[0].program == "notepad" and pieces[0].action == "say the name of the focused control", pieces
# A big request: two pieces, and a program for both, said in a clause of its own.
pieces, _why = read("make an addon that says heading whenever I land on a heading, says the time with nvda+alt+t, "
	"and only works in firefox")
assert [(p.kind, p.event or p.gesture, p.role, p.program, p.action) for p in pieces] == [
	("event", "gainFocus", "HEADING", "firefox", "say heading"), ("key", "kb:NVDA+alt+t", "", "firefox", "say the time")], pieces
# A key said in words is not split at its "plus", and a key and an event in one clause are two pieces.
pieces, _why = read("write an add-on that beeps when a link gets focus and says the time with NVDA plus alt plus T")
assert [(p.event or p.gesture, p.action) for p in pieces] == [("gainFocus", "beep"), ("kb:NVDA+alt+t", "say the time")], pieces
pieces, _why = read("I want a plugin: when I press nvda+shift+b it reads the battery, and it beeps when a link gets focus")
assert [(p.gesture or p.event, p.action) for p in pieces] == [("kb:NVDA+shift+b", "read the battery"), ("gainFocus", "beep")]
# What happens may be said before when: "when a dialog opens, say its title".
pieces, _why = read("when a dialog opens, say its title. Also, when I press control+alt+r, read the status bar.")
assert [(p.event or p.gesture, p.role, p.action) for p in pieces] == [
	("foreground", "DIALOG", "say its title"), ("kb:control+alt+r", "", "read the status bar")], pieces
# More of what one piece does, said after it: it belongs to that piece.
pieces, _why = read("beep when a button gets the focus, and also say its name")
assert len(pieces) == 1 and pieces[0].action == "beep and say its name", pieces
# "nvda a bit" is no key; "this program" is the program in front; "for word" is not the program Word.
pieces, _why = read("write an add-on that makes nvda a bit quieter when a button gets focus")
assert pieces[0].kind == "event" and pieces[0].action == "make nvda a bit quieter", pieces
pieces, _why = read("write an add-on for this program that says the value whenever a progress bar changes")
assert (pieces[0].event, pieces[0].role, pieces[0].program) == ("valueChange", "PROGRESSBAR", "notepad"), pieces
pieces, _why = read("say the word count for word when I press nvda+shift+w")
assert pieces[0].program == "" and pieces[0].gesture == "kb:NVDA+shift+w", pieces
pieces, _why = read("in word, say the word count when I press nvda+shift+w")
assert pieces[0].program == "winword", pieces
# Each kind of event NVDA has, read from words.
for said, event in (("each time I type a letter, beep", "typedCharacter"), ("let me know when an alert appears", "alert"),
		("say checked when a checkbox gets checked", "stateChange"), ("beep when the cursor moves", "caret"),
		("say the new title when the title of the window changes", "nameChange"),
		("say what it says when a program sends a notification", "UIA_notification")):
	pieces, _why = read(said)
	assert pieces and pieces[0].event == event, (said, pieces)
# A key command whose key is not named gets a free one from plain code, and the user is told.
pieces, _why = read("give me a key that reads the window title")
codeplan.chooseKeys(pieces, used=["NVDA+alt+1"])
assert pieces[0].gesture == "kb:NVDA+alt+2" and pieces[0].action == "read the window title", pieces
assert any("VisionClaw chose NVDA+alt+2" in line for line in codeplan.limits(pieces))
# What plain code cannot frame is written as one piece, and why is said.
for said in ("every hour say the time", "say the time when NVDA starts", "add a settings panel for the voice",
		"say the time", "say hi with nvda+shift+h and say bye with nvda+shift+h"):
	pieces, why = read(said)
	assert not pieces and why, (said, pieces)
pieces, why = read("say hi in this program when I press nvda+shift+h", facts="")
assert not pieces and "not known" in why, why
assert codeplan.gestureOf("press NVDA plus shift plus F5 to read") == "kb:NVDA+shift+f5"
assert codeplan.gestureOf("alt text") == "" and codeplan.gestureOf("make nvda a bit louder") == ""
assert codeplan.gestureOf("control alt page up") == "kb:control+alt+pageUp"

# --- What plain code writes, and the add-on put together ---

assert codeplan.plainBody("beep") == ("tones.beep(880, 80)", {"tones"})
assert codeplan.plainBody("play a high beep")[0] == "tones.beep(1200, 80)"
assert codeplan.plainBody("say heading") == ("ui.message('heading')", {"ui"})
assert codeplan.plainBody("beep and say 'checked'")[0] == "tones.beep(880, 80)\nui.message('checked')"
# A word that names something that has a value is no fixed sentence: a model writes it.
assert codeplan.plainBody("say the time") == ("", set()) and codeplan.plainBody("say time") == ("", set())


def Fake(app="firefox"):
	"""Stand-ins for NVDA's modules (tests/addonstandin.py), with the focus in a program."""
	return standin.Fake(focus=standin.control(app=app))


def run(source, fake):
	return standin.load(source, fake)


pieces, _why = read("make an addon that beeps whenever I land on a link, says heading when a heading gets focus, "
	"says hello with nvda+shift+h, and only works in firefox")
codeplan.chooseKeys(pieces)
codeplan.name(pieces)
for piece in pieces:
	piece.body, piece.imports = codeplan.plainBody(piece.action)
source = codeplan.assemble(pieces)
assert microaddons.check(source) == [], microaddons.check(source)
# Two pieces that wait for the same event share one method, each in a try of its own; NVDA is passed the event once.
assert source.count("def event_gainFocus") == 1 and source.count("try:") == 2, source
assert "script_sayHello" in source and "gesture='kb:NVDA+shift+h'" in source
# What checking the code says in words, for the user who cannot read code, names the program it is limited to.
assert "It works only in: firefox." in microaddons.describe(source), microaddons.describe(source)
fake = Fake("firefox")
plugin = run(source, fake)
calls = []
link = types.SimpleNamespace(role="LINK", appModule=types.SimpleNamespace(appName="firefox"))
plugin.event_gainFocus(link, lambda: calls.append(1))
heading = types.SimpleNamespace(role="HEADING", appModule=types.SimpleNamespace(appName="firefox"))
plugin.event_gainFocus(heading, lambda: calls.append(2))
plugin.script_sayHello(types.SimpleNamespace(send=lambda: fake.sent.append("key")))
assert fake.beeps == [880] and fake.said == ["heading", "hello"] and calls == [1, 2] and fake.sent == [], (fake.beeps, fake.said)
# In another program nothing happens: the key goes to that program, and NVDA still gets the event.
fake = Fake("chrome")
plugin = run(source, fake)
plugin.event_gainFocus(types.SimpleNamespace(role="LINK", appModule=types.SimpleNamespace(appName="chrome")), lambda: calls.append(3))
plugin.script_sayHello(types.SimpleNamespace(send=lambda: fake.sent.append("key")))
assert fake.beeps == [] and fake.said == [] and fake.sent == ["key"] and calls[-1] == 3
# A piece whose lines fail does not stop NVDA, nor the other pieces of the same event.
pieces[0].body = "tones.beep(obj.missing, 80)"
plugin = run(codeplan.assemble(pieces), Fake("firefox"))
plugin.event_gainFocus(link, lambda: calls.append(4))
assert calls[-1] == 4
# What the add-on cannot do, said before it is turned on.
assert any("browse mode" in line for line in codeplan.limits(pieces))
# "Gets checked" is only when it is now checked, not when it is unchecked.
pieces, _why = read("say checked when a checkbox gets checked")
codeplan.name(pieces)
pieces[0].body, pieces[0].imports = codeplan.plainBody(pieces[0].action)
source = codeplan.assemble(pieces)
fake = Fake("notepad")
plugin = run(source, fake)
assert standin.event(plugin, "stateChange", standin.control("Bold", "CHECKBOX", states=["CHECKED"]), fake) == 1
assert standin.event(plugin, "stateChange", standin.control("Bold", "CHECKBOX"), fake) == 1
assert fake.said == ["checked"], fake.said
pieces, _why = read("say unchecked when a check box gets unchecked")
assert pieces[0].state == ("CHECKED", False) and "no longer checked" in pieces[0].when(), pieces

# A title NVDA's objects do not have, as the real model wrote it on 2026-11-19, is corrected by plain code, in a piece
# and in an add-on written as one piece.
assert microaddons.fixNames("ui.message(obj.appModule.windowTitle)") == "ui.message(api.getForegroundObject().name)"
assert microaddons.fixNames("title = api.getForegroundObject().title") == "title = api.getForegroundObject().name"
assert microaddons.fixNames("self.title = 1") == "self.title = 1"
# As Qwen2.5 Coder 1.5B wrote them on 2026-11-19: a kind of control with an underscore NVDA does not write, and now on
# the module datetime. A kind NVDA writes with an underscore, and datetime imported from the module, stay.
assert microaddons.fixNames("controlTypes.Role.PROGRESS_BAR") == "controlTypes.Role.PROGRESSBAR"
assert microaddons.fixNames("controlTypes.Role.BUSY_INDICATOR") == "controlTypes.Role.BUSY_INDICATOR"
assert microaddons.fixNames("ui.message(datetime.now().strftime('%H'))") == "ui.message(datetime.datetime.now().strftime('%H'))"
assert microaddons.fixNames("datetime.datetime.now()") == "datetime.datetime.now()"
assert microaddons.fixNames("from datetime import datetime\nx = datetime.now()").endswith("x = datetime.now()")
# Typing a character is something that happens by itself, also for the add-on written as one piece; pressing a named
# key is not.
assert microaddons._wantsEvent("Each time I type a character, beep.") and not microaddons._wantsEvent("say hi when I press NVDA+x")
tidied = microaddons.tidy(microaddons.EXAMPLE_KEY.replace("obj.name or", "obj.appModule.windowTitle or"), "say the title on NVDA+shift+f9")
assert "api.getForegroundObject().name" in tidied and "windowTitle" not in tidied, tidied

# --- The lines a model writes for one piece ---

body, imports = codeplan.bodyOf("```python\nimport time\nui.message(time.strftime('%H:%M'))\n```")
assert body == "ui.message(time.strftime('%H:%M'))" and imports == {"time"}, (body, imports)
# A model that writes the whole method, or the whole add-on, anyway: its first method's lines are taken.
whole = ("```python\nimport globalPluginHandler\nimport ui\nfrom scriptHandler import script\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n"
	"\t@script(description='x', gesture='kb:NVDA+alt+t')\n\tdef script_sayTime(self, gesture):\n\t\timport time\n"
	"\t\tui.message(time.strftime('%H:%M'))\n```")
body, imports = codeplan.bodyOf(whole)
assert body == "ui.message(time.strftime('%H:%M'))" and imports == {"time"}, (body, imports)
# Lines written indented, as they stand in the method: how Qwen3.5 9B answered on 2026-11-19. Taking the first line's
# indentation alone made every answer a syntax error the model could not correct.
body, _imports = codeplan.bodyOf("```python\n\ttitle = api.getForegroundObject().title\n\tui.message(title)\n```")
assert body == "title = api.getForegroundObject().title\nui.message(title)", repr(body)
body, _imports = codeplan.bodyOf("title = x\n\tui.message(title)")
assert body == "title = x\nui.message(title)", repr(body)
body, _imports = codeplan.bodyOf("```python\n\tif x:\n\t\ty()\n```")
assert body == "if x:\n\ty()", repr(body)
body, _imports = codeplan.bodyOf("```python\ndef event_gainFocus(self, obj, nextHandler):\n    ui.message(obj.name)\n    nextHandler()\n```")
assert body == "ui.message(obj.name)", body
piece = codeplan.Piece("key", "x", "say the time", gesture="kb:NVDA+alt+t")
codeplan.name([piece])
assert codeplan.problems(piece, "ui.message(time.strftime('%H:%M'))") == []
assert any("not allowed" in p for p in codeplan.problems(piece, "exec('x')"))
assert any("program" in p for p in codeplan.problems(piece, "if api.getFocusObject().appModule.appName == 'x':\n\tpass"))
assert codeplan.problems(piece, "")


class FakeLLM:
	"""A scripted model: texts for what it writes, verdicts for its reviews. Every question is kept."""

	def __init__(self, texts, verdicts=()):
		self.texts, self.verdicts, self.calls = list(texts), list(verdicts), []

	def text(self, role, system, user, **options):
		self.calls.append((role, system, user))
		return self.texts.pop(0)

	def json(self, role, system, user, schema, **options):
		self.calls.append((role, system, user))
		return self.verdicts.pop(0) if self.verdicts else {"ok": True, "problem": ""}


params = policy.select({"complexity": "complex", "needs_code": True})
folder = tempfile.mkdtemp()
try:
	task = taskModule.Task("write an add-on")
	task.sheet = worksheet.Sheet(folder, task.request)
	llm = FakeLLM([
		"```python\nui.message(time.strftime('%H:%M'))\n```",
		"```python\nexec('x')\n```", "```python\nui.message(api.getFocusObject().name or 'no name')\n```",
	])
	purpose = ("write an add-on that says the time with nvda+alt+t, beeps when a link gets the focus, and says the name of "
		"the focused control with nvda+shift+n")
	source = codeplan.write(llm, task, purpose, HERE, "WHOLE NOTES", params, CODER, VISION,
		notesFor=lambda words: f"notes for: {words}", sheet=task.sheet)
	assert microaddons.check(source) == [], source
	writes = [call for call in llm.calls if call[0] == CODER]
	reviews = [call for call in llm.calls if call[0] == VISION]
	# The beep was written by plain code: the model wrote two pieces, one of them twice.
	assert len(writes) == 3 and len(reviews) == 2, llm.calls
	first = writes[0][2]
	# A piece is given its own words, its own method and its own notes, and nothing of the other pieces.
	assert "say the time" in first and "kb:NVDA+alt+t" in first and "notes for: say the time" in first
	assert "link" not in first and "focused control" not in first and "WHOLE NOTES" not in first, first
	assert writes[0][1].startswith("You write the lines inside one method")
	# Who the add-on is for comes with every piece, as with every add-on (prompts.coding).
	assert "blind" in writes[0][1]
	# A piece that fails its check is sent back alone, with what is wrong.
	assert "exec() is not allowed" in writes[2][2] and "say the name of the focused control" in writes[2][2]
	# The work sheet holds the plan of the pieces, each piece's question word for word, and the whole add-on.
	text = open(task.sheet.path, encoding="utf-8").read()
	assert "## The add-on, piece by piece" in text and "## Piece 1: the key NVDA+alt+t" in text, text
	assert first.splitlines()[0] in text and "Written by plain code" in text and "## The whole add-on" in text
	assert os.path.isfile(task.sheet.path)
	task.sheet.close()
	assert not os.path.exists(task.sheet.path) and os.listdir(folder) == []
	# What plain code cannot read into pieces is written as one piece, as before, and the user is told why.
	task = taskModule.Task("write an add-on")
	one = "```python\n" + microaddons.EXAMPLE_KEY + "```"
	llm = FakeLLM([one] * 10)
	try:
		codeplan.write(llm, task, "say the time every hour", HERE, "WHOLE NOTES", params, CODER, VISION)
	except ToolError:
		pass  # whether the one piece passes is microaddons.write's own business (tests/test_parts.py)
	assert "WHOLE NOTES" in llm.calls[0][2] and llm.calls[0][1].startswith("You write small add-ons")
	assert any("written as one piece" in text for _s, _k, text in task.log)
	# A piece that never passes: the add-on is written as one piece instead.
	task = taskModule.Task("write an add-on")
	llm = FakeLLM(["```python\nexec('x')\n```"] * (params.codeRepairs + 1) + [one])
	source = codeplan.write(llm, task, "say the time with nvda+alt+t", HERE, "", params, CODER, VISION)
	assert "script_sayName" in source and any(call[1].startswith("You write small add-ons") for call in llm.calls)
	# A fault the reviewer finds is sent back once; lines that pass every check are kept, and the doubt is kept for
	# the user.
	task = taskModule.Task("write an add-on")
	llm = FakeLLM(["```python\nui.message('x')\n```", "```python\nui.message('x')\n```"],
		[{"ok": False, "problem": "It says x, not the time."}, {"ok": False, "problem": "Still not the time."}])
	source = codeplan.write(llm, task, "say the time with nvda+alt+t", HERE, "", params._replace(codeReviews=1), CODER, VISION)
	assert "It says x, not the time." in llm.calls[2][2] and task.codeDoubt == "It says x, not the time.", (llm.calls, task.codeDoubt)
	# With one model for both jobs it is never called two.
	task = taskModule.Task("write an add-on")
	llm = FakeLLM(["```python\nui.message('x')\n```"], [{"ok": False, "problem": "Wrong."}])
	codeplan.write(llm, task, "say the time with nvda+alt+t", HERE, "", params._replace(oneModel=True, codeRepairs=0), CODER, VISION)
	said = " ".join(text for _s, _k, text in task.log)
	assert "reviewing model" not in said and "coder model" not in said and "The model read this piece again" in said, said

	# --- Correcting only the method where an add-on failed ---
	failing = ("import globalPluginHandler\nimport ui\nimport api\nfrom scriptHandler import script\n\n\n"
		"class GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\n"
		"\t@script(description='Say the focus', gesture='kb:NVDA+shift+j')\n\tdef script_sayFocus(self, gesture):\n"
		"\t\tui.message(api.getFocus().name)\n\n\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message(obj.name)\n"
		"\t\tnextHandler()\n")
	assert codeplan.methodAt(failing, 11) == (9, 11) and codeplan.methodAt(failing, 13) == (13, 15)
	task = taskModule.Task("fix")
	llm = FakeLLM(["```python\n@script(description='Say the focus', gesture='kb:NVDA+shift+j')\ndef script_sayFocus(self, gesture):\n"
		"    ui.message(api.getFocusObject().name)\n```"])
	fixed = codeplan.fixMethod(llm, task, "say the focus", failing, [
		"When it ran in NVDA, script_sayFocus failed with AttributeError: module 'api' has no attribute 'getFocus'. "
		"The failing line is line 11, in script_sayFocus: ui.message(api.getFocus().name)"], "", params, CODER, VISION)
	sent = llm.calls[0][2]
	assert "script_sayFocus" in sent and "event_gainFocus" not in sent, sent
	assert "api.getFocusObject().name" in fixed and "def event_gainFocus" in fixed and microaddons.check(fixed) == [], fixed
	# Two methods that failed, or the user's own words: the whole add-on is corrected, as before.
	task = taskModule.Task("fix")
	llm = FakeLLM(["```python\n" + failing.replace("getFocus()", "getFocusObject()") + "```"] * 4)
	codeplan.fixMethod(llm, task, "say the focus on NVDA+shift+j, and say the name when the focus moves", failing,
		["The user says: it should beep too."], "", params, CODER, VISION)
	assert llm.calls[0][1].startswith("You write small add-ons") and "event_gainFocus" in llm.calls[0][2]

	# --- The work sheet of a request ---
	stale = os.path.join(folder, "request-old.md")
	open(stale, "w").write("left over")
	keep = os.path.join(folder, "notes.md")
	open(keep, "w").write("not a work sheet")
	assert worksheet.clean(folder) == 1 and not os.path.exists(stale) and os.path.exists(keep)
	os.remove(keep)
	steps = [
		Step("Finding the setting", "find_setting", "speak faster", "speak faster", recipe="change_setting"),
		Step("Changing it", "set_setting", "speak faster", "speak faster", recipe="change_setting"),
		Step("Typing", "type_text", "type hello", "type hello", recipe="type_text"),
		Step("Pressing it", "click_item", "click it", "click it", recipe="click"),
		Step("Planned by a model", "press_keys", "x", "do something", recipe=None),
		planner.answerStep(),
	]
	steps[0].status, steps[0].result = taskModule.STEP_DONE, "rate: 50"
	steps[1].status, steps[1].result = taskModule.STEP_DONE, "The rate is now 60."
	steps[2].status, steps[2].result = taskModule.STEP_DONE, "Typed."
	sheet = worksheet.Sheet(folder, "speak faster, type hello and click it")
	sheet.plan(steps, ["change_setting", "type_text", "click"])
	# A step is given what its own part found; one that speaks of "it", and one a model planned, are given all.
	assert sheet.feed(steps, 1) == "1. Finding the setting: rate: 50"
	assert sheet.feed(steps, 2) == "Nothing yet."
	assert "1. Finding the setting" in sheet.feed(steps, 3) and "3. Typing" in sheet.feed(steps, 3)
	assert "2. Changing it" in sheet.feed(steps, 4)
	text = open(sheet.path, encoding="utf-8").read()
	assert "## Plan" in text and "1. [x] Finding the setting (find_setting): done." in text and "Step 2 was given: step 1." in text, text
	assert "deleted" in text and "Request: \"speak faster, type hello and click it\"" in text
	sheet.close()
	assert os.listdir(folder) == []
	# Without a folder the sheet is kept in memory, and writes nothing.
	sheet = worksheet.Sheet(None, "x")
	sheet.section("A", "b")
	assert "## A" in sheet.text() and sheet.path is None
	sheet.close()
finally:
	shutil.rmtree(folder, ignore_errors=True)
print("OK")
