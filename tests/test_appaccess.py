# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A whole program made accessible, one window after another (claw/appaccess.py), with plain Python.

The owner asked on 2026-11-19 for a skill that learns the window of a program the user is in, plans the fixes for all its
accessibility problems, makes them, and learns the other windows of the program as the user moves to them, knowing that
two, twenty or a hundred windows belong to one program. This checks, without NVDA and without a model:
- which words ask for it, and that the words of other jobs are left to them (the known and evaluation requests too);
- which window it is: the same window of a program with another document in it, and a page of a website;
- the plan from inspections of several windows: each fix once for the whole program with every window it is in, the
  simplest first, what needs its window open, what no add-on can fix; made or not, read from the add-on itself;
- what the user asked VisionClaw to remember about the program moving its steps forward;
- the map kept as two sections of the program's access notes, read back as written, and a hundred windows on it;
- that nothing said is cut, the request is kept whole, and the skill, the notes and the instructions for answers fit.
The tools against stand-ins for NVDA are in tests/test_nvda_stub.py.

  python tests/test_appaccess.py
"""
import json
import os
import re
import tempfile

import harness  # noqa: F401
from visionClaw.claw import accessnotes, appaccess, audit, fixes, lookup, planner, prompts
from visionClaw.claw.skills import Skills

A = appaccess

# --- What the words ask ---

ASKS = {
	"learn all about the current window of this program, make a plan to fix all accessibility issues, and then fix those "
	"issues": A.ALL,
	"Learn all about this window, make a plan to fix the accessibility problems, then fix them": A.ALL,
	"make every window of this program accessible": A.ALL,
	"make the whole program accessible": A.ALL,
	"fix every window of this program": A.ALL,
	"fix all the windows of this app": A.ALL,
	"learn this window": A.LEARN,
	"learn this window too": A.LEARN,
	"this window too": A.LEARN,
	"learn the windows of this program": A.LEARN,
	"check every window of this program for accessibility problems": A.LEARN,
	"learn this window's keyboard shortcuts": A.LEARN,
	"make a plan to fix this program's windows": A.PLAN,
	"learn this window and make a plan to fix it": A.PLAN,
	"add this dialog to the plan": A.PLAN,
	"carry out the plan": A.FIX,
	"make the planned fixes for this program": A.FIX,
	"make the remaining fixes for this program": A.FIX,
	"implement all the accessibility fixes": A.FIX,
	"which windows of this program have you learned": A.WINDOWS_SAID,
	"what windows do you know in this program": A.WINDOWS_SAID,
	"what's the plan for this program": A.PLAN_SAID,
	"show me the accessibility plan": A.PLAN_SAID,
	"what's left to fix in this program": A.PLAN_SAID,
	"keep learning the windows of this program": A.FOLLOW,
	"learn each new window as I move to it": A.FOLLOW,
	"stop learning windows of this program": A.UNFOLLOW,
	"forget the windows of this program": A.FORGET,
	"forget the plan for this program": A.FORGET,
}
for said, do in ASKS.items():
	found = A.wish(said)
	assert found is not None and found["do"] == do, (said, found)
	assert A.makes(said) == (do in A.MAKES), said
# What other jobs do stays with them: one window inspected or fixed, the notes from the internet, the windows that are
# open, a page explored, being led through a task, add-ons and scratchpads.
for said in ("fix this window", "make this program accessible", "inspect this window", "learn about this program",
		"learn about this game", "close all windows", "switch to the other window", "fix the add-on", "plan a job on a scratchpad",
		"what is the plan for today", "make the page accessible", "fix all of it", "what windows are open",
		"list all open windows", "delete the windows folder", "forget my notes on this program", "what have you learned here",
		"fix the accessibility problems in this window", "make a plan on my scratchpad to install the game",
		"tell me when the inbox count changes", "explore this page", "go through this window with me", "how far is the plan",
		"fix your own bugs", "change the settings of this program", "learn the keys of NVDA"):
	assert A.wish(said) is None, (said, A.wish(said))
# Not one request whose job is known, and none of the evaluation sets, is taken by these words.
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval")
known = json.load(open(os.path.join(HERE, "known.json"), encoding="utf-8"))["jobs"]
taken = [text for texts in known.values() for text in texts if A.wish(text) is not None]
assert not taken, taken
for name in ("requests.json", "requests2.json", "requests3.json", "requests4.json", "requests5.json", "requests6.json",
		"requests-ten.json", "requests-ten2.json"):
	data = json.load(open(os.path.join(HERE, name), encoding="utf-8"))
	items = data if isinstance(data, list) else data.get("requests") or []
	texts = [item.get("request") or item.get("text") or "" if isinstance(item, dict) else str(item[0]) for item in items]
	assert texts and not [text for text in texts if A.wish(text) is not None], name
assert A.targetOf("learn this page") == "page" and A.targetOf("learn this window") == "window" and A.targetOf("carry out the plan") == "auto"

# The planner: the job is read from the words before any model, and one job told in clauses is kept whole; a clause that
# asks for something else is a part of its own.
for said, job in (("make every window of this program accessible", "fix_program"), ("learn this window too", "program_access"),
		("which windows of this program have you learned", "program_access"), ("carry out the plan", "fix_program"),
		("make this program accessible", "fix_access"), ("fix this window", "fix_access"), ("learn about this program", "learn_app"),
		("how do I make every window of this program accessible", "explain_keys")):
	assert planner.hint(said) == job, (said, planner.hint(said))
assert {"program_access", "fix_program"} <= set(planner._SURE) and {"program_access", "fix_program"} <= set(planner._WHOLE)
assert planner.RECIPES["fix_program"][2] == ("learn_program", "fix_program") and planner.RECIPES["program_access"][2] == ("learn_program",)
request = ("learn all about the current window of this program, make a plan to fix all accessibility issues, and then fix "
	"those issues")
assert planner.split(None, None, request) == [request]
assert planner.split(None, None, "Learn this window, then make a plan to fix it, then fix everything.") == [
	"Learn this window, then make a plan to fix it, then fix everything."]
parts = planner.split(None, None, "learn this window and then open notepad")
assert len(parts) == 2 and planner.hint(parts[0]) == "program_access" and planner.hint(parts[1]) == "open_thing", parts
assert planner._NEEDS["program_access"]("open notepad") is None and planner._NEEDS["fix_program"]("learn this window") is None

# --- Which window it is ---

NOTEPAD = ["notepad", "Microsoft Notepad"]
assert A.titleShape("Untitled - Notepad", NOTEPAD) == A.titleShape("notes.txt - Notepad", NOTEPAD) == "* - notepad"
assert A.windowId("Notepad", "Untitled - Notepad", NOTEPAD) == A.windowId("Notepad", "Shopping list.txt - Notepad", NOTEPAD)
assert A.windowId("#32770", "Font", NOTEPAD) != A.windowId("#32770", "Page Setup", NOTEPAD)
assert A.titleShape("Downloads - File Explorer", ["explorer", "Windows Explorer"]) == "* - file explorer"
assert A.titleShape("main.py - project - Visual Studio Code", ["code", "Visual Studio Code"]) == "* - visual studio code"
assert A.titleShape("Report - Writer", []) == "* - writer"
assert A.titleShape("Save changes to \"notes.txt\"?", NOTEPAD) == "save changes to *?"
assert A.titleShape("Page 3 of 10", []) == "page # of #" and A.titleShape("", NOTEPAD) == ""
assert A.pageId("https://shop.example/orders/12345?x=1#top") == {"page": "/orders/*"}
assert A.pageId("https://www.example.com/") == {"page": "/"} and A.pageId("https://x.example/user/ab12cd34ef/posts") == {"page": "/user/*/posts"}
assert A.kindOf("DIALOG", "") == "dialog" and A.kindOf("WINDOW", "#32770") == "dialog" and A.kindOf("WINDOW", "Notepad") == "window"
assert A.kindOf(page=True) == "page"

# --- The plan, from inspections of several windows ---


def button(name="", autoId="", controlId=0, states=("FOCUSABLE",)):
	return {"role": "BUTTON", "name": name, "text": "", "value": "", "states": list(states), "autoId": autoId,
		"controlId": controlId, "windowClass": "#32770", "cls": [], "tag": "", "ident": "", "src": ""}


def window(*nodes):
	return [{"role": "DIALOG", "name": "", "text": "", "value": "", "states": [], "autoId": "", "controlId": 0,
		"windowClass": "#32770", "cls": [], "tag": "", "ident": "", "src": ""}] + list(nodes)


scope = fixes.scopeOf(app="notepad")
options = audit.auditWindow(window(button(autoId="closeBtn"), button(controlId=1001), button("Details"), button("Details"),
	button("Details"), button("OK")), title="Options", app="notepad")
optionsId = A.windowId("#32770", "Options", NOTEPAD)
optionsRef = A.ref(optionsId)
steps = A.stepsFrom(options, optionsRef)
kinds = sorted((step.kind, step.fix["kind"] if step.kind == A.FIX_STEP else "") for step in steps)
# The button whose code calls it closeBtn is named from its code; the one with nothing in its code waits for its picture;
# names that say nothing are advice: no add-on can fix them.
assert kinds == [(A.ADVICE, ""), (A.FIX_STEP, fixes.NAME), (A.LOOK, "")], kinds
look = next(step for step in steps if step.kind == A.LOOK)
assert look.sentence() == "1 button without a name, to be named from its picture while the window is open", look.sentence()
# Named from its picture while the window was open, the look becomes a fix, said to be a guess.
named = {A.ruleKey(look.fix["rule"]): "Settings"}
steps = A.stepsFrom(options, optionsRef, named)
guess = next(step for step in steps if step.kind == A.FIX_STEP and step.fix.get("guess"))
assert guess.sentence() == "Buttons without a name are called Settings, a guess from a picture that can be wrong", guess.sentence()
plan = A.merged([], steps, optionsRef)
place = A.placeFrom(options, optionsId, "Options", "dialog")
assert place.controls == 7 and place.problems == ["controls without a name", "names that say nothing"], place.problems

# A second window with the same close button: one step for the whole program, in both windows.
font = audit.auditWindow(window(button(autoId="closeBtn"), button("Bold")), title="Font", app="notepad")
fontRef = A.ref(A.windowId("#32770", "Font", NOTEPAD))
plan = A.merged(plan, A.stepsFrom(font, fontRef), fontRef)
close = [step for step in plan if step.kind == A.FIX_STEP and step.fix["label"] == "close"]
assert len(close) == 1 and close[0].windows == [optionsRef, fontRef], [(s.fix, s.windows) for s in close]
# Learned again without its close button, Options keeps the step only through Font; a guess from a picture gives way to a
# name from the program's code; what is gone from a window it alone had is dropped.
again = audit.auditWindow(window(button("OK"), button("Cancel"), button("Apply")), title="Options", app="notepad")
plan = A.merged(plan, A.stepsFrom(again, optionsRef), optionsRef)
assert [step.windows for step in plan if step.kind == A.FIX_STEP and step.fix["label"] == "close"] == [[fontRef]]
assert not [step for step in plan if optionsRef in step.windows], [step.sentence() for step in plan]
plan = A.merged(plan, A.stepsFrom(options, optionsRef, named), optionsRef)
assert len([step for step in plan if step.kind == A.FIX_STEP and step.fix["label"] == "close"]) == 1
coded = A.Step(A.FIX_STEP, {"kind": fixes.NAME, "rule": guess.fix["rule"], "label": "Preferences"}, windows=[optionsRef])
fresh = [coded if step.kind == A.FIX_STEP and step.fix.get("guess") else step for step in A.stepsFrom(options, optionsRef, named)]
plan = A.merged(plan, fresh, optionsRef)
assert [step.fix["label"] for step in plan if step.kind == A.FIX_STEP and A.ruleKey(step.fix["rule"]) == A.ruleKey(guess.fix["rule"])] == [
	"Preferences"]

# Made or not is read from the add-on: a fix it has is made, with its keys; one it no longer has is to make again.
press = A.Step(A.FIX_STEP, {"kind": fixes.PRESS, "rule": {"role": "BUTTON", "names": ["bold"]}, "label": "Bold"}, windows=[fontRef])
plan.append(press)
assert press.sentence() == "A key that presses Bold, wherever you are in it"
inAddon = [{"kind": fixes.PRESS, "rule": {"role": "BUTTON", "names": ["bold"]}, "label": "Bold", "keys": ["NVDA+alt+1"]}]
plan = A.refreshed(plan, inAddon)
assert press.status == A.MADE and press.sentence() == "NVDA+alt+1 presses Bold, wherever you are", press.sentence()
assert all(step.status == A.PLANNED for step in plan if step.kind == A.FIX_STEP and step is not press)
assert A.refreshed(plan, [])[-1].status == A.PLANNED
plan = A.refreshed(plan, inAddon)
make, made, needs, advice = A.counts(plan)
assert (made, advice) == (1, 1) and make == len(A.toMake(plan)) == 2, A.counts(plan)
# The simplest remedy first: names, then a key; what no add-on can fix last.
ordered, moved = A.favoured(plan, [])
assert moved == 0 and [step.rank() for step in ordered] == sorted(step.rank() for step in ordered)
assert ordered[-1].kind == A.ADVICE
# What the user asked VisionClaw to remember about the program moves the steps it is about forward, among those to make.
fontName = A.Step(A.FIX_STEP, {"kind": fixes.NAME, "rule": {"role": "BUTTON", "autoId": "boldBtn"}, "label": "Bold"}, windows=[fontRef])
withFont = A.refreshed(plan + [fontName], inAddon)
ordered, moved = A.favoured(withFont, ["In notepad: I use the Bold button in the Font dialog all the time."])
# The Bold button of the Font dialog first, then the other step of the Font dialog.
assert moved == 2 and ordered[0] is fontName and ordered[1].fix["label"] == "close", [step.sentence() for step in ordered]

# --- What is said ---

places = [place, A.placeFrom(font, A.windowId("#32770", "Font", NOTEPAD), "Font", "dialog")]
text = A.planText(ordered, scope, places, moved)
assert text.startswith("The plan for the program notepad, from the 2 windows VisionClaw has learned, has 5 steps: 3 to make, "
	"1 made and 1 that no add-on can fix."), text
assert "2 steps that what you asked VisionClaw to remember is about come first." in text
assert "1. To make: Buttons without a name are called Bold. In the window Font." in text, text
assert "Made: NVDA+alt+1 presses Bold, wherever you are. In the window Font." in text, text
assert "No add-on can fix this: 3 controls have a name that says nothing, such as \"details\". Read the text before one to learn " \
	"what it is for. In the window Options." in text, text
assert text.endswith("To make the 3 fixes still to make, say: make the planned fixes for this program. VisionClaw asks before it "
	"turns them on.")
listed = A.windowsText(places, scope)
assert listed.startswith("VisionClaw has learned 2 windows of the program notepad, and all of them belong to it:"), listed
assert "1. Options, a dialog. NVDA knows 7 controls in it, 6 that can be used and 4 with a name. 2 problems: controls without " \
	"a name and names that say nothing. Learned 1 time, the last time when you asked." in listed, listed
assert listed.endswith("A fix made for the program notepad works in every one of these windows.")
assert A.windowsText([], scope).startswith("VisionClaw has learned no windows of the program notepad yet.")
said = A.learnedText(place, scope, options.findings, [s for s in ordered if optionsRef in s.windows], ordered, places,
	["From NVDA's log, just now: The app module for notepad had an error."])
assert said.startswith("Learned the dialog Options of the program notepad.\nFound 2 problems in it:\n1. "), said
assert "VisionClaw now knows 2 windows of the program notepad, all of them part of it: Options and Font." in said
assert "From NVDA's log, just now: The app module for notepad had an error." in said
assert said.endswith("When you move to another window of it, VisionClaw learns that one too, and tells you."), said
quiet = A.learnedText(place, scope, [], [], [], places[:1], followed=A.FOLLOW_OFF, nextStep=False)
assert "None of the problems VisionClaw checks for were found in it." in quiet and "It is the first window" in quiet
assert quiet.endswith("To learn another window, move to it and say: learn this window too.") and "make the planned" not in quiet
assert A.followedText(place, scope, options.findings, [guess], 2) == (
	"VisionClaw learned this dialog of notepad: 2 problems, 1 step for it in the plan. Say: make the planned fixes for this program.")
left = A.leftText(ordered, A.namesOf(places), scope)
assert left.startswith("Still left in the plan: 4 steps.") and "No add-on can fix this" in left, left
assert A.leftText([press], {}, scope) == "Every step of the plan for the program notepad is made."
# A hundred windows and more belong to the program, and every one of them is said when the list is asked for.
many = [A.Place({"cls": "#32770", "title": f"tool {n}"}, f"Tool window number {n}", "dialog") for n in range(120)]
listed = A.windowsText(many, scope)
assert listed.count("Tool window number") == 120 and "Tool window number 119, a dialog." in listed
assert "VisionClaw now knows 120 windows of the program notepad, all of them part of it. To hear every one, say: which windows " \
	"of this program have you learned." == A.knownText(many, scope, many[-1])
for said in (text, listed, left, A.learnedText(place, scope, options.findings, ordered, ordered, many)):
	assert "[cut]" not in said and "..." not in said and "…" not in said and "and more" not in said, said[:200]

# --- The map, kept as two sections of the program's access notes ---

folder = tempfile.mkdtemp(prefix="vcmap-")
notes = accessnotes.AccessNotes(folder)
notes.keepName(scope, accessnotes.keyOf({"role": "BUTTON", "autoId": "gear"}), "button", "Settings")
assert notes.knownName(scope, accessnotes.keyOf({"autoId": "gear", "role": "BUTTON"})) == "Settings"
assert notes.knownName(scope, accessnotes.keyOf({"autoId": "other", "role": "BUTTON"})) == ""
notes.setEntries(scope, accessnotes.WINDOWS, A.placeLines(places))
notes.setEntries(scope, accessnotes.PLAN, A.planLines(ordered, places, scope))
again = A.placesFrom(notes.entries(scope, accessnotes.WINDOWS))
assert [(p.key(), p.name, p.kind, p.controls, p.problems) for p in again] == [
	(p.key(), p.name, p.kind, p.controls, p.problems) for p in places]
back = A.planFrom(notes.entries(scope, accessnotes.PLAN))
assert [step.key() for step in back] == [step.key() for step in ordered] and [s.status for s in back] == [s.status for s in ordered]
written = notes.text(scope)
assert "## Windows and pages learned" in written and "## The plan to fix it" in written and "## Names read from pictures" in written
# A line the user deleted stays deleted, and the other sections are left as they were.
lines = written.splitlines()
cut = [line for line in lines if line.startswith("- ") and "Options, a dialog." in line]
with open(notes.path(scope), "w", encoding="utf-8") as f:
	f.write("\n".join(line for line in lines if line not in cut))
assert [p.name for p in A.placesFrom(notes.entries(scope, accessnotes.WINDOWS))] == ["Font"]
assert notes.knownName(scope, accessnotes.keyOf({"role": "BUTTON", "autoId": "gear"})) == "Settings"
# The findings of inspections are still kept to their own limit; the windows of the map are not counted in it.
for n in range(200):
	notes.keepFound(scope, f"Inspection {n} found something")
assert len(A.placesFrom(notes.entries(scope, accessnotes.WINDOWS))) == 1
assert len(notes.entries(scope, accessnotes.FOUND)) <= accessnotes.MAX_LINES
notes.setEntries(scope, accessnotes.WINDOWS, A.placeLines(many))
assert len(A.placesFrom(notes.entries(scope, accessnotes.WINDOWS))) == 120
# A window learned again takes its own place, and goes last.
moved = A.withPlace(many, A.Place({"cls": "#32770", "title": "tool 3"}, "Tool window number 3", "dialog", times=2))
assert len(moved) == 120 and moved[-1].times == 2 and moved[-1].name == "Tool window number 3"

# --- Following the user from window to window ---

known = {A.ref(optionsId)}
fontKey = A.ref(A.windowId("#32770", "Font", NOTEPAD))
assert A.follows(A.FOLLOW_TELL, [], scope, known, fontKey) and A.follows(A.FOLLOW_QUIET, [], scope, known, fontKey)
assert not A.follows(A.FOLLOW_OFF, [], scope, known, fontKey)
assert not A.follows(A.FOLLOW_TELL, [], scope, known, A.ref(optionsId))  # known already
assert not A.follows(A.FOLLOW_TELL, ["notepad"], scope, known, fontKey)  # the user said stop
assert not A.follows(A.FOLLOW_TELL, [], scope, set(), fontKey)  # nothing learned of the program: not followed
assert A.belongs("make a plan to fix all accessibility issues") and A.belongs("then fix those issues")
assert not A.belongs("open notepad") and not A.belongs("tell me a joke")

# --- The skill, the notes and the instructions for an answer ---

lib = Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
for said in ("make every window of this program accessible", "learn this window too", "what's the plan for the whole program",
		"make the planned fixes for this program"):
	chosen = [skill.slug for skill in lib.choose(said)]
	assert "whole-program-accessible" in chosen and "stubborn-program" not in chosen, (said, chosen)
for said in ("what time is it", "describe the screen", "fix this button", "open notepad"):
	assert "whole-program-accessible" not in [skill.slug for skill in lib.choose(said)], said
gate = lookup.NOTES["visionclaw-program-access"][2]
for question in ("how do I make every window of a program accessible", "what is the accessibility plan",
		"how does visionclaw learn new windows", "does a fix work in the other windows of this program"):
	assert gate.search(question), question
for question in ("how do I close a window", "how do I read the title bar"):
	assert not gate.search(question), question
note = os.path.join(os.path.dirname(lookup.__file__), "knowledge", "visionclaw-program-access.md")
sections = re.split(r"\n## ", open(note, encoding="utf-8").read())[1:]
assert len(sections) >= 6 and all(len(section.split("\n", 1)[1].strip()) <= 360 for section in sections), [
	len(s.split("\n", 1)[1].strip()) for s in sections]
found = "From what VisionClaw learned about the windows of the program notepad: Made: NVDA+alt+1 presses Bold."
assert "programHelp" in prompts.aboutFound(found) and prompts.PROGRAM_HELP in prompts.speaking("Answer.", found)
assert "programHelp" not in prompts.aboutFound("From the program notepad: Control+S saves.")
assert "programHelp" in prompts.PARTS and prompts.DEFAULTS["programHelp"] == prompts.PROGRAM_HELP
assert fixes.MAX_FIXES >= 80

print("test_appaccess: OK")
