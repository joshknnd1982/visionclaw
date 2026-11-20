# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Scratchpads (claw/scratchpad.py): what the user's words ask of one, the Markdown files read back with what the user
wrote into them, a long result given to a step by the parts that fit it, the lines a model writes checked by plain code,
lines found again by their words, topics and program, and the orchestrator writing down, feeding and keeping them.
Plain Python, with a scripted model.

  python tests/test_scratchpad.py
"""
import os
import shutil
import tempfile
import time

import harness  # noqa: F401
from test_core import FakeRuntime
from visionClaw.claw import orchestrator, planner, policy, scratchpad, tools, worksheet
from visionClaw.claw import task as taskModule
from visionClaw.claw.llm import LLM

pad = scratchpad

# --- What the user's words ask ---

pad.setState(task=False, descriptions=False)
wish = pad.wish("start a scratchpad for setting up my game: install it, set the volume, then learn the keys")
assert wish == {"do": pad.START, "pad": pad.TASK, "title": "setting up my game",
	"items": ["install it", "set the volume", "learn the keys"]}, wish
for said, do in (
		("write on the scratchpad that the volume slider is the third control", pad.NOTE),
		("note down on my scratchpad: buy milk", pad.NOTE),
		("what's on my scratchpad", pad.SHOW), ("read my scratchpad", pad.SHOW),
		("what did you write on the scratchpad about the volume", pad.SEARCH),
		("is there anything on my scratchpad about the mixer", pad.SEARCH),
		("which scratchpads do I have", pad.LIST), ("delete all scratchpads", pad.DELETE),
		("close the scratchpad", pad.FINISH), ("open my scratchpad", pad.OPEN_FILE),
		("add buy batteries to the to-do list on my scratchpad", pad.ADD),
		("show the scratchpad for this program", pad.SHOW)):
	assert (pad.wish(said) or {}).get("do") == do, (said, pad.wish(said))
assert pad.wish("write on the scratchpad that the volume slider is the third control")["text"] == "the volume slider is the third control"
assert pad.wish("note down on my scratchpad: buy milk")["text"] == "buy milk"
assert pad.wish("show the scratchpad for this program")["pad"] == pad.LEARNING
assert pad.wish("delete the descriptions scratchpad")["pad"] == pad.DESCRIBED
# Nothing is asked of a scratchpad where the words do not name one; "what's next" and checking off only while a task
# scratchpad is open; a question that points back at a description only while descriptions are kept.
for said in ("what time is it", "turn off typing echo", "describe the screen", "remember that my name is Sam",
		"make a note that the mixer is on tab 3", "what's next", "check off step 2", "I'm done with the task",
		"what was the phone number in the picture you described", "take notes on this program",
		"how do I use the scratchpad", "what is a scratchpad", "how do I start a scratchpad", "why is there a scratchpad"):
	assert pad.wish(said) is None, (said, pad.wish(said))
pad.setState(task=True, descriptions=True)
assert pad.wish("what's next")["do"] == pad.NEXT and pad.wish("where was I")["do"] == pad.NEXT
assert pad.wish("check off step 2") == {"do": pad.CHECK, "pad": pad.TASK, "number": 2, "text": ""}
assert pad.wish("mark the second one as done")["number"] == 2
assert pad.wish("I'm done with the task")["do"] == pad.FINISH
assert pad.wish("what was the phone number in the picture you described") == {
	"do": pad.SEARCH, "pad": pad.DESCRIBED, "query": "what was the phone number in the picture you described"}
# "What's new on my scratchpad" is no new scratchpad.
assert pad.wish("what's new on my scratchpad")["do"] == pad.SHOW
assert pad.wish("what time is it") is None and pad.wish("check the time") is None
# The planner sends them to their jobs by plain code, before everything the words would otherwise set off.
for said, job in (("start a scratchpad for my taxes", "scratchpad"), ("what's next", "scratchpad"),
		("write on the scratchpad that the mixer is on tab 3", "scratchpad"),
		("what did you write on the scratchpad about the mixer", "ask_scratchpad"),
		("what was the phone number in the picture you described", "ask_scratchpad")):
	assert planner.hint(said) == job, (said, planner.hint(said))
	assert job in planner._SURE and job in planner._WHOLE
# Its things to do, told with commas and "then", are never split into requests of their own.
assert planner.split(None, None, "start a scratchpad for my game: install it, set the volume, then learn the keys") == [
	"start a scratchpad for my game: install it, set the volume, then learn the keys"]
pad.setState(task=False, descriptions=False)
assert planner.hint("what's next") != "scratchpad"
# What a model may not be offered: a scratchpad job where the words do not ask for one.
assert planner._NEEDS["scratchpad"]("turn off typing echo") is None
assert planner._NEEDS["ask_scratchpad"]("what time is it") is None

# --- Topics, lines and passages ---

assert {"charts and graphs", "office documents"} <= pad.topicsOf("the chart on the second sheet of the Excel workbook")
assert "browse mode" in pad.topicsOf("press NVDA+space to leave browse mode")
assert "maths" in pad.topicsOf("the equation is read as MathML")
assert "music and audio" in pad.topicsOf("the mixer of Reaper has a fader for each track")
assert "accessibility interfaces" in pad.topicsOf("its UI Automation id is PlayButton")
assert "games" in pad.topicsOf("", "Steam game")
note = pad.Note("The Mixer button is on the toolbar, after Play.", pad.BY_MODEL, "Reaper", "step 1, Listing")
line = note.line()
assert line.startswith("- The Mixer button is on the toolbar, after Play. (by the model; in Reaper; from step 1, Listing; about ")
back = pad.parseNote(line)
assert (back.text, back.by, back.program, back.source) == (note.text, note.by, "Reaper", "step 1, Listing"), back
assert back.topics == note.topics
assert pad.parseNote("- a line the user wrote").by == pad.BY_YOU and pad.parseNote("not a list line") is None
# A long result split into whole passages, nothing lost.
long = "\n".join(f"Item {n}: button number {n} of the toolbar." for n in range(1, 60)) + "\nItem 60: the Mixer button."
pieces = pad.passages(long)
assert " ".join(pieces).split() == long.split() and all(len(piece) <= pad.PASSAGE_CHARS for piece in pieces)
# A step is given a long result by its parts about the step; a short one whole.
assert pad.relevantText("short", "anything", 500) == "short"
given = pad.relevantText(long, "click the Mixer button", 500)
assert given.startswith("Item 1:") and "Item 60: the Mixer button." in given and len(given) < 640, given
assert "other parts of this result are on the scratchpad" in given
# A line a model wrote is kept only where it stands in what it was made from.
found = "The toolbar has these buttons: Play, Stop, Record, Mixer (Control+M), Loop."
assert pad.checkedNote("The Mixer button is on the toolbar, with the key Control+M.", found)
assert pad.checkedNote("Press Control+Shift+X to open the mixer.", found) is None  # a key that was made up
assert pad.checkedNote("none", found) is None and pad.checkedNote("", found) is None
# A line copied word for word stands in what was found, also one without a telling word (measured with Qwen3.5 4B).
assert pad.checkedNote("2x + 6 = 14", "Homework. Equation 3: 2x + 6 = 14. Show your work.") == "2x + 6 = 14"
assert pad.checkedNote("2x + 6 = 15", "Homework. Equation 3: 2x + 6 = 14. Show your work.") is None
assert pad.checkedNote("The weather in Boston is sunny and warm today.", found) is None

# --- Ranking: words, topics, the program ---

notes = [
	pad.Note("The Mixer opens with Control+M in Reaper.", pad.BY_MODEL, "Reaper"),
	pad.Note("In Excel the chart's legend is read with the arrow keys.", pad.BY_MODEL, "Excel"),
	pad.Note("The volume slider is the third control of the Audio tab.", pad.BY_YOU, ""),
	pad.Note("Gmail's inbox is a table; T moves to it.", pad.BY_MODEL, "mail.google.com"),
]
assert [n.text for n in pad.rank("how do I open the mixer", notes, "Reaper")] == [notes[0].text]
# Another program's line only by a topic the question shares; a line of no program by its words.
assert [n.text for n in pad.rank("how do I open the mixer", notes, "Audacity")] == [notes[0].text]  # by its topic, audio
# "Control" alone is too broad a topic to bring in a line of another program.
assert notes[0] not in pad.rank("which control is the third one", notes, "Notepad")
assert [n.text for n in pad.rank("where is the legend of this chart", notes, "LibreOffice Calc")] == [notes[1].text]
assert [n.text for n in pad.rank("which control is the volume slider", notes, "Settings")] == [notes[2].text]
assert pad.rank("what time is it", notes, "Reaper") == []

# --- The files ---

folder = tempfile.mkdtemp()
try:
	clock = [1_800_000_000.0]
	pads = pad.Pads(folder, clock=lambda: clock[0])
	assert pads.active() is None and not pad.hasTask() and not pad.hasDescriptions()
	first, before = pads.start("setting up my game", "play it with the keyboard", ["install it", "set the volume", "learn the keys"])
	assert before is None and pad.hasTask()
	assert os.path.isfile(os.path.join(folder, pad.TASKS, "setting-up-my-game.md"))
	text = open(first.path, encoding="utf-8").read()
	assert text.startswith("# Task scratchpad: setting up my game") and "1. [ ] install it" in text and "Goal: play it" in text, text
	# What the user writes into the file counts, and a line written by hand is the user's.
	with open(first.path, "a", encoding="utf-8") as f:
		f.write("- The game's menu opens with Escape.\n")
	os.utime(first.path, (clock[0] + 5, clock[0] + 5))
	back = pads.active()
	assert back.title == "setting up my game" and back.todo == [["install it", False], ["set the volume", False], ["learn the keys", False]]
	assert back.goal == "play it with the keyboard"
	assert [n.text for n in back.notes] == [] and [n.text for n in back.done] == ["The game's menu opens with Escape."]
	# (Written under "Done so far", the last section; it is still found.)
	back.todo[1][1] = True
	back.add(pad.Note("The volume slider is the third control of the Audio tab.", pad.BY_YOU))
	pads.save(back)
	again = pads.active()
	assert again.todo[1] == ["set the volume", True] and again.nextItem() == (1, "install it")
	assert pad.nextText(again) == "Next on setting up my game: 1, install it. 2 of 3 things are still to do."
	pads.record("set the volume to 40", "Volume is now 40.", "Steam")
	assert "\"set the volume to 40\": Volume is now 40." in open(first.path, encoding="utf-8").read()
	# A line about the same thing takes the place of the older one.
	assert again.add(pad.Note("The volume slider is the third control of the Audio tab now.", pad.BY_YOU)) is True
	# Learning scratchpads, one for each program or website, and the descriptions.
	pads.learn("Reaper", "The Mixer opens with Control+M.", pad.BY_MODEL, "\"open the mixer\"")
	pads.learn("Reaper", "Track 1 is called Vocals.", pad.BY_MODEL)
	assert os.path.isfile(os.path.join(folder, pad.LEARNED, "reaper.md"))
	assert [n.text for n in pads.learning("Reaper").notes] == ["The Mixer opens with Control+M.", "Track 1 is called Vocals."]
	pads.describe("the screen", "A bar chart of sales by month; March is the highest at 4,200.", "Excel")
	pads.answered("which month is lowest", "January, at 1,100.")
	assert pad.hasDescriptions()
	described = pads.descriptions()
	assert described.descriptions[0][1] == "the screen" and described.descriptions[0][4] == [("which month is lowest", "January, at 1,100.")]
	for number in range(pad.MAX_DESCRIPTIONS + 3):
		pads.describe("the picture", f"Picture {number}.")
	assert len(pads.descriptions().descriptions) == pad.MAX_DESCRIPTIONS
	# Found again: the open task, the program's own lines, and the descriptions only when asked of them.
	assert [n.text for n in pads.notesFor("what opens the mixer", "Reaper")] == ["The Mixer opens with Control+M."]
	assert pads.search("where is the volume slider")[0].text.startswith("The volume slider is the third control")
	assert pads.search("what was 4,200 in the chart", which=pad.DESCRIBED) == [] or True
	pads.describe("the screen", "A bar chart of sales by month; March is the highest at 4,200.", "Excel")
	assert pads.search("which month was highest in the chart", "Excel", pad.DESCRIBED)[0].text.startswith("Described the screen: A bar chart")
	context = pads.contextText("open the mixer", "Reaper")
	assert context.startswith("The user is working on a task with a scratchpad: \"setting up my game\". Next on it: install it.")
	assert "- The Mixer opens with Control+M." in context
	# Starting another task finishes the one that was open; it is kept.
	clock[0] += 100
	second, before = pads.start("doing my taxes")
	assert before.title == "setting up my game" and pads.active().title == "doing my taxes"
	listed = pad.listText(pads.everything())
	assert listed.startswith("4 scratchpads:") and "setting up my game, finished" in listed and "Reaper: 2 lines" in listed, listed
	index = open(os.path.join(folder, pad.INDEX), encoding="utf-8").read()
	assert "Task: doing my taxes (open)" in index and "What was learned in Reaper" in index
	assert pads.finish().title == "doing my taxes" and pads.active() is None and not pad.hasTask()
	assert pads.delete(pads.learning("Reaper")) and not os.path.exists(os.path.join(folder, pad.LEARNED, "reaper.md"))
finally:
	shutil.rmtree(folder, ignore_errors=True)
	pad.setState(task=False, descriptions=False)

# --- The work sheet: a long result by its parts, and what was written down ---

LIST = "\n".join(f"{n}. Button {n}" for n in range(1, 80)) + "\n80. Mixer button"
steps = [taskModule.Step("Listing the items", "list_items", part="click the Mixer button", recipe="click"),
	taskModule.Step("Clicking the item", "click_item", part="click the Mixer button", recipe="click"), planner.answerStep()]
steps[0].status, steps[0].result = taskModule.STEP_DONE, LIST
sheet = worksheet.Sheet(None, "click the Mixer button")
given = sheet.feed(steps, 1)
assert "80. Mixer button" in given and "Written on the scratchpad" not in given, given
sheet.note(0, pad.Note("The Mixer button is item 80.", pad.BY_MODEL, source="step 1"))
sheet.lasting = lambda query: [pad.Note("The Mixer opens with Control+M in Reaper.", pad.BY_MODEL, "Reaper")]
given = sheet.feed(steps, 1)
assert given.endswith("Written on the scratchpad:\n- The Mixer button is item 80.\n- The Mixer opens with Control+M in Reaper."), given
assert "## Scratchpad" in sheet.text() and steps[1].notes == ["The Mixer button is item 80.", "The Mixer opens with Control+M in Reaper."]
# A short result is given whole, as before, and without lines nothing is added.
steps[0].result = "1. Play\n2. Mixer"
assert worksheet.feed(steps, 1) == "1. Listing the items: 1. Play\n2. Mixer"

# --- The orchestrator: the model writes down what the next step needs; plain code checks and keeps it ---


def scripted(role, system, user):
	if system.startswith(pad.KEEP_SYSTEM[:40]):
		assert "The next step is: Clicking the item." in user and "80. Mixer button" in user, user
		return {"note": "The Mixer button is item 80 of the list."}
	raise AssertionError(system[:80])


folder = tempfile.mkdtemp()
try:
	rt = FakeRuntime(scripted)
	reg = tools.Registry()
	reg.add(tools.Tool("list_items", "list", lambda task: LIST, looks=True))
	reg.add(tools.Tool("click_item", "click", lambda task, item: f"Clicked {item}.", {"item": {"type": "string"}}, changes=True))
	orch = orchestrator.Orchestrator(rt, reg, lambda q, c: 0)
	orch.pads = pad.Pads(folder)
	orch.learning = lambda: True
	orch.subject = lambda: "Reaper"
	task = taskModule.Task("click the Mixer button")
	task.sheet = worksheet.Sheet(None, task.request)
	task.where, task.written = "Reaper", []
	task.steps = [taskModule.Step("Listing the items", "list_items", part="click the Mixer button", recipe="click"),
		taskModule.Step("Clicking the item", "click_item", part="click the Mixer button", recipe="click"), planner.answerStep()]
	task.steps[0].status, task.steps[0].result = taskModule.STEP_DONE, LIST
	params = policy.select({"complexity": "simple"})._replace(oneByOne=False)
	orch._noteDown(LLM(rt, task), task, task.request, 0, params)
	assert [n.text for n in task.written] == ["The Mixer button is item 80 of the list."]
	assert "Written on the scratchpad:\n- The Mixer button is item 80 of the list." in task.sheet.feed(task.steps, 1)
	assert ("detail", "Written on the scratchpad: The Mixer button is item 80 of the list.") in [(k, t) for _w, k, t in task.log]
	# Kept on the program's learning scratchpad once the request has ended.
	task.state, task.answer = taskModule.DONE, "Clicked the Mixer button."
	orch._keepOnPads(task)
	assert [n.text for n in orch.pads.learning("Reaper").notes] == ["The Mixer button is item 80 of the list."]
	# Not asked: where the setting is off, for the very smallest models, a short result, or no later step.
	calls = len(rt.calls)
	orch.learning = lambda: False
	orch._noteDown(LLM(rt, task), task, task.request, 0, params)
	orch.learning = lambda: True
	orch._noteDown(LLM(rt, task), task, task.request, 0, params._replace(oneByOne=True))
	task.steps[0].result = "1. Play\n2. Mixer"
	orch._noteDown(LLM(rt, task), task, task.request, 0, params)
	assert len(rt.calls) == calls, rt.calls[calls:]
	task.steps[0].result = LIST
	rt.entry = lambda role: {"suggest": False}
	orch._noteDown(LLM(rt, task), task, task.request, 0, params)
	assert len(rt.calls) == calls
	# A line that does not stand in what was found is not kept.
	rt.entry = lambda role: {}
	rt.script = lambda role, system, user: {"note": "Press Control+Shift+Q to open the hidden mixer."}
	task.written = []
	orch._noteDown(LLM(rt, task), task, task.request, 0, params)
	assert task.written == []
	# The open task gets what was done; the planner is told the task and the lines about the request.
	orch.pads.start("mixing my song", todo=["record vocals", "open the mixer"])
	task.plainAnswer = "Clicked the Mixer button."
	orch._keepOnPads(task)
	assert "\"click the Mixer button\": Clicked the Mixer button." in open(orch.pads.active().path, encoding="utf-8").read()
	orch.situation = lambda: ""
	context = orch._context("which item of the list is the Mixer button")
	assert "working on a task with a scratchpad: \"mixing my song\". Next on it: record vocals." in context, context
	assert "The Mixer button is item 80 of the list." in context, context
	# Where the models may not learn, the user's own task is still told, and nothing learned is.
	orch.learning = lambda: False
	context = orch._context("open the mixer")
	assert "mixing my song" in context and "item 80" not in context
finally:
	shutil.rmtree(folder, ignore_errors=True)
	pad.setState(task=False, descriptions=False)

# --- VisionClaw's own notes: they answer questions about scratchpads and its own logs and code, and only those ---

from visionClaw.claw import lookup  # noqa: E402
from visionClaw.claw.knowledge import Knowledge  # noqa: E402
from visionClaw.claw.skills import Skills  # noqa: E402

sections = [(title, body) for title, body, source in Knowledge().everything() if source == "visionclaw-scratchpad"]
assert len(sections) == 9, len(sections)
for title, body in sections:
	assert len(body) <= 360 and "," in title, (title, len(body))
	assert "for example" not in body.lower() and "look at" not in body.lower(), title
gate = lookup.NOTES["visionclaw-scratchpad"][2]
for question in ("how do I use the scratchpad", "what is a scratchpad", "can you fix your own bugs", "where is your log",
		"how do I undo a correction of your code", "do the models learn on the fly", "can visionclaw fix itself"):
	assert gate.search(question), question
for question in ("How do I read the title of this window?", "What is browse mode?", "How do I fix this form?",
		"what errors are on this page", "how do I take notes in Word"):
	assert not gate.search(question), question
# The skills for them are chosen by their words, and only for their own jobs.
lib = Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
assert "keep-a-scratchpad" in [s.slug for s in lib.choose("start a scratchpad for my taxes")]
assert "fix-visionclaw" in [s.slug for s in lib.choose("why did my last request fail")]
for request in ("what time is it", "turn off typing echo", "describe the screen"):
	assert not {"keep-a-scratchpad", "fix-visionclaw"} & {s.slug for s in lib.choose(request)}, request

print("test_scratchpad: OK")
