# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The ways cloud models use their scratchpads, made small (claw/scratchpad.py, claw/orchestrator.py): lines that earn
trust from how the requests they were given to went, and are set aside when they do not help; what did not work kept in
view; a request stopped in the middle carried on from where it stopped; the task scratchpad's list carried out a thing at
a time and checked off when it went well; the program's lines given to the model that writes an add-on; and the
instructions that go with lines from a scratchpad. Plain Python, with a scripted model.

  python tests/test_scratch_ways.py
"""
import os
import shutil
import tempfile

import harness  # noqa: F401
from test_core import FakeRuntime
from visionClaw.claw import orchestrator, planner, prompts, scratchpad, tools, worksheet
from visionClaw.claw import task as taskModule
from visionClaw.claw.tools import VERBATIM

pad = scratchpad

# --- A line's trust, written into its line and read back ---

note = pad.Note("The Mixer button is item 80 of the list.", pad.BY_MODEL, "Reaper", good=2, bad=1, when=0)
assert "used 3 times, 2 went well" in note.line(), note.line()
back = pad.parseNote(note.line())
assert (back.good, back.bad, back.by, back.program) == (2, 1, pad.BY_MODEL, "Reaper"), back.line()
assert abs(back.trust() - 3 / 5) < 1e-9 and not back.doubtful()
assert pad.Note("never used", pad.BY_MODEL).trust() == 0.5
# Hand-made numbers are read forgivingly: more that went well than were used counts as all.
odd = pad.parseNote("- a line (by the model; used 1 time, 5 went well; 2026-11-19 10:00)")
assert (odd.good, odd.bad) == (1, 0)
# Set aside after the second request that did not go well with no success, after the third with one.
assert not pad.Note("x", pad.BY_MODEL, bad=1).doubtful()
assert pad.Note("x", pad.BY_MODEL, bad=2).doubtful()
assert not pad.Note("x", pad.BY_MODEL, good=1, bad=2).doubtful()
assert pad.Note("x", pad.BY_MODEL, good=1, bad=3).doubtful()
# The user's own lines are never set aside: they are the user's to change.
assert not pad.Note("x", pad.BY_YOU, bad=9).doubtful()

# --- Judged on a scratchpad: counted, set aside, kept in the file, moved back by the user ---

learned = pad.Pad(pad.LEARNING, "Reaper")
learned.add(pad.Note("The Mixer button is item 80 of the list.", pad.BY_MODEL, "Reaper"))
learned.add(pad.Note("The track list is called Tracks.", pad.BY_MODEL, "Reaper"))
assert learned.judge("The Mixer button is item 80 of the list.", True).good == 1
assert learned.judge("nothing like it", True) is None
learned.judge("The track list is called Tracks.", False)
learned.judge("The track list is called Tracks.", False)
assert [n.text for n in learned.notes] == ["The Mixer button is item 80 of the list."]
assert [n.text for n in learned.aside] == ["The track list is called Tracks."]
text = learned.text()
assert "## Set aside" in text and "The models no longer read them" in text and "used 2 times, 0 went well" in text, text
again = pad.Pad.parse(text, pad.LEARNING)
assert [n.text for n in again.aside] == ["The track list is called Tracks."]
assert [n.text for n in again.notes] == ["The Mixer button is item 80 of the list."] and again.notes[0].good == 1
# The user moves the line back up under Notes: it starts over and is used again.
moved = text.replace("## Set aside", "## Gone").replace("## Notes\n", "## Notes\n\n" + learned.aside[0].line() + "\n")
moved = pad.Pad.parse(moved, pad.LEARNING)
back = [n for n in moved.notes if n.text == "The track list is called Tracks."][0]
assert (back.good, back.bad) == (0, 0) and not back.doubtful()

# --- Ranking: what helped comes first, what was set aside is not given ---

helped = pad.Note("The volume slider is the third control in the mixer.", pad.BY_MODEL, "Reaper", good=4)
failed = pad.Note("The volume slider is the first control in the mixer.", pad.BY_MODEL, "Reaper", good=1, bad=2)
fresh = pad.Note("The volume slider is the second control in the mixer.", pad.BY_MODEL, "Reaper")
order = [n.text for n in pad.rank("where is the volume slider in the mixer", [failed, fresh, helped], "Reaper")]
assert order[0] == helped.text and order.index(fresh.text) < order.index(failed.text) if failed.text in order else True, order
gone = pad.Note("The volume slider is the fourth control in the mixer.", pad.BY_MODEL, "Reaper", bad=2)
assert gone.text not in [n.text for n in pad.rank("where is the volume slider in the mixer", [gone, fresh], "Reaper")]

# --- Judged through the files, from the lines a request was given ---

folder = tempfile.mkdtemp()
try:
	pads = pad.Pads(folder)
	pads.learn("Reaper", "The Mixer button is item 80 of the list.", pad.BY_MODEL)
	pads.learn("Reaper", "For \"open the mixer\", reading the window's text found nothing here.", pad.BY_VISIONCLAW)
	given = []
	context = pads.contextText("click the Mixer button", "Reaper", given)
	assert "item 80" in context and [n.text for n in given] == ["The Mixer button is item 80 of the list."], (context, given)
	assert given[0].pad == (pad.LEARNING, "Reaper")
	assert pads.judge(given + given, True) == []
	line = pads.learning("Reaper").notes[0]
	assert (line.good, line.bad) == (1, 0), "each line is counted once however often it was given"
	assert "used 1 time, 1 went well" in open(pads.learning("Reaper").path, encoding="utf-8").read()
	for _time in range(3):
		pads.judge(pads.notesFor("click the Mixer button", "Reaper"), False)
	assert [n.text for n in pads.learning("Reaper").aside] == ["The Mixer button is item 80 of the list."]
	assert "item 80" not in pads.contextText("click the Mixer button", "Reaper", [])
	# The descriptions and the list of a task are not counted: they say what happened, not how to do something.
	pads.start("mixing", todo=["record vocals"])
	assert pads.judge(pads.active().lines(), False) == []
	# The work sheet keeps the lasting lines it gave to a step.
	pads.learn("Reaper", "The Record button is item 12 of the list.", pad.BY_MODEL)
	sheet = worksheet.Sheet(None, "press Record")
	sheet.lasting = lambda query: pads.notesFor(query, "Reaper")
	steps = [taskModule.Step("Clicking the Record button", "click_item", part="press the Record button", recipe="click"),
		planner.answerStep()]
	assert "item 12" in sheet.feed(steps, 0)
	assert [n.text for n in sheet.given] == ["The Record button is item 12 of the list."]

	# --- The lines given to the model that writes an add-on for this program ---

	pads.learn("Reaper", "The track list is a list called Tracks, and each track says its name and number.", pad.BY_MODEL)
	pads.learn("Reaper", "For \"read the tracks\", reading the window's text found nothing here.", pad.BY_VISIONCLAW)
	written = pads.forCoder("Reaper", "announce the name of the track in the track list when it changes")
	assert written.startswith(prompts.PAD_HEAD) and "a list called Tracks" in written, written
	assert "found nothing" not in written and "Record button" not in written, written
	assert pads.forCoder("Reaper", "say the time when I press NVDA+Shift+T") == ""
	assert pads.forCoder("Audacity", "announce the name of the track") == ""
	# Its instructions come only with them.
	assert prompts.CODE_PAD in prompts.coding("Write an add-on.", "announce the track", given=written)
	assert prompts.CODE_PAD not in prompts.coding("Write an add-on.", "announce the track", given="Notes: nothing")
	# An answer from the scratchpads gets the instructions for them, and only then.
	found = pad.foundText(pads.search("Mixer button", "Reaper") + [pad.Note("To do: record vocals", pad.BY_YOU)])
	assert "padHelp" in prompts.aboutFound(found) and prompts.PAD_HELP in prompts.speaking("Answer.", found), found
	assert "padHelp" not in prompts.aboutFound("From the program Reaper: Control+R records.")
	for text in (prompts.PAD_HELP, prompts.CODE_PAD):
		assert "for example" not in text.lower() and "vision model" not in text and "coder model" not in text
finally:
	shutil.rmtree(folder, ignore_errors=True)
	pad.setState(task=False, descriptions=False)

# --- The words: carrying on, and carrying out a thing of the list ---

for said in ("carry on", "Continue.", "resume please", "continue where you left off", "pick up where you left off",
		"go on where you stopped", "finish what you were doing", "ok, carry on with it", "could you continue please",
		"continue with what you were doing", "keep going from where you stopped"):
	assert pad.carryOn(said), said
for said in ("go on", "keep going", "continue reading", "carry on reading the page", "continue the lesson",
		"what happens if I continue", "continue to the next page", "resume the music"):
	assert not pad.carryOn(said), said
pad.setState(task=False)
assert pad.doWish("do the next one") is None, "without an open task and without the list named"
assert pad.doWish("do the next thing on my scratchpad") == {"number": None}
assert pad.doWish("do step 3 on my scratchpad") == {"number": 3}
pad.setState(task=True)
try:
	for said, number in (("do the next one", None), ("let's do the next step", None), ("do the second thing", 2),
			("work on item 4", 4), ("ok, do the last one", -1), ("go ahead with the next item on the list", None)):
		assert pad.doWish(said) == {"number": number}, said
	for said in ("do the next one and then tell me the time", "what is the next step", "do the dishes",
			"do the next page", "press the next button", "do I have a next step"):
		assert pad.doWish(said) is None, said
finally:
	pad.setState(task=False)
task = pad.Pad(pad.TASK, "setting up Reaper")
task.todo = [["turn on track announcements", True], ["set the speech rate to 60", False], ["learn the record keys", False]]
assert pad.itemOf(task, None) == (2, "set the speech rate to 60")
assert pad.itemOf(task, 1) == (1, "turn on track announcements")
assert pad.itemOf(task, -1) == (3, "learn the record keys")
assert pad.itemOf(task, 7)[0] is None and "has 3 things on its list, so there is no number 7" in pad.itemOf(task, 7)[1]
assert pad.itemOf(None, None)[0] is None and "No task scratchpad is open" in pad.itemOf(None, None)[1]
task.todo[1][1] = task.todo[2][1] = True
assert "Everything on the scratchpad setting up Reaper is done" in pad.itemOf(task, None)[1]
assert "not checked off, because it did not go as it should" in pad.tickedText(None, 2, "x", False)
assert "because you said no to a step" in pad.tickedText(None, 2, "x", None)

# --- Whole requests: carried on after a stop, and a thing of the list carried out and checked off ---


def scripted(role, system, user):
	raise AssertionError(f"No model should be asked: {system[:80]}")


def registry(log, stopAt=None):
	reg = tools.Registry()

	def first(task):
		log.append("first")
		return "The window has three buttons: Play, Stop and Mixer."

	def second(task):
		log.append("second")
		if stopAt == "second":
			task.cancel.set()
			task.check()
		return "Pressed Mixer."

	reg.add(tools.Tool("look_first", "look", first, looks=True, tell=VERBATIM))
	reg.add(tools.Tool("press_second", "press", second, changes=True, tell=VERBATIM))
	return reg


def planned(task, request):
	steps = [taskModule.Step("Looking at the window", "look_first", part=request, recipe="look"),
		taskModule.Step("Pressing Mixer", "press_second", part=request, recipe="press"), planner.answerStep()]
	return steps


folder = tempfile.mkdtemp()
try:
	log = []
	rt = FakeRuntime(scripted)
	orch = orchestrator.Orchestrator(rt, registry(log, stopAt="second"), lambda q, c: 0)
	orch.workFolder = None
	# The plan is made as a skill's would be, so that no model is asked to choose.
	orch._skillPlan = lambda task, skill, request: (planned(task, request), "skill", ["look", "press"])
	plannedBefore = orchestrator.skillsModule.planned
	orchestrator.skillsModule.planned = lambda skills, request: type("Skill", (), {"name": "a plan of the test"})()
	stopped = orch.run(taskModule.Task("open the mixer"))
	assert stopped.state == taskModule.CANCELLED and log == ["first", "second"], (stopped.state, log)
	assert orch.stopped is not None and orch.stopped.request == "open the mixer"
	# "Carry on": the first step is not done again, the one that was stopped is.
	orch.registry = registry(log)
	going = orch.run(taskModule.Task("carry on"))
	assert going.state == taskModule.DONE, (going.state, going.answer)
	assert log == ["first", "second", "second"], log
	said = [t for _w, k, t in going.log if k == taskModule.TALK]
	assert any("Carrying on with \"open the mixer\" from step 2 of 2" in t and "may be out of date" in t for t in said), said
	assert going.answer.startswith("Understood as: open the mixer."), going.answer
	assert orch.stopped is None
	# Nothing stopped: said so by plain code, and nothing is done.
	nothing = orch.run(taskModule.Task("carry on"))
	assert nothing.state == taskModule.DONE and "nothing to carry on with" in nothing.answer and log[-1] == "second"
	# Stopped too long ago: not carried on.
	orch.registry = registry(log, stopAt="second")
	orch.run(taskModule.Task("open the mixer"))
	orch.stopped.when -= pad.STOPPED_SECONDS + 1
	orch.registry = registry(log)
	late = orch.run(taskModule.Task("continue where you left off"))
	assert "nothing to carry on with" in late.answer, late.answer

	# The task scratchpad's list: "do the next one" carries out the next thing, and checks it off when it went well.
	orch.pads = pad.Pads(folder)
	orch.learning = lambda: True
	orch.subject = lambda: "Reaper"
	orch.pads.start("setting up Reaper", todo=["open the mixer", "learn the record keys"])
	done = orch.run(taskModule.Task("do the next one"))
	assert done.state == taskModule.DONE and done.request == "open the mixer", (done.state, done.request)
	assert "Checked off 1, open the mixer, on the scratchpad setting up Reaper. Next: 2, learn the record keys." in done.answer, done.answer
	assert orch.pads.active().todo[0][1] is True
	assert "\"open the mixer\": " in open(orch.pads.active().path, encoding="utf-8").read(), "recorded in its own words"
	# One that did not go well stays on the list.
	orch.registry.get("look_first").fn = lambda task: "Nothing was found."
	orch.pads.active().todo[0][1] = False
	orch.pads.save(orch.pads.active())
	failed = orch.run(taskModule.Task("do step 1 on my scratchpad"))
	assert "is not checked off" in failed.answer and orch.pads.active().todo[0][1] is False, failed.answer
	# Nothing on the list: said by plain code.
	orch.pads.finish()
	none = orch.run(taskModule.Task("do the next thing on my scratchpad"))
	assert "No task scratchpad is open" in none.answer
finally:
	orchestrator.skillsModule.planned = plannedBefore
	shutil.rmtree(folder, ignore_errors=True)
	pad.setState(task=False, descriptions=False)

# An answer worded from the scratchpads alone is followed by where it is from, said by plain code; any other is not.
told = type("Told", (), {})()
told.infoTools = ["scratchpad_search"]
assert "written down on a scratchpad before" in orchestrator.Orchestrator._fromPads(told)
for tools_ in ([], ["look_up", "scratchpad_search"], ["look_up"]):
	told.infoTools = tools_
	assert orchestrator.Orchestrator._fromPads(told) == "", tools_
import answercheck  # noqa: E402
for sentence in ("This was written down on a scratchpad before, and may be out of date.",
		pad.tickedText(pad.Pad(pad.TASK, "setting up Reaper"), 1, "open the mixer", True),
		pad.tickedText(None, 2, "open the mixer", False), pad.itemOf(None, None)[1],
		"No request was stopped in the last 30 minutes, so there is nothing to carry on with. Say what you want done."):
	assert not answercheck.problems(sentence, [sentence]), (sentence, answercheck.problems(sentence, [sentence]))

# --- "What have you learned here", the skills that use the scratchpads, and VisionClaw's notes on them ---

from visionClaw.claw import lookup  # noqa: E402
from visionClaw.claw.skills import Skills  # noqa: E402

for said in ("what have you learned here", "what did you find out in this game", "what have you learned about this site",
		"what has VisionClaw written down in this program"):
	assert pad.wish(said) == {"do": pad.SHOW, "pad": pad.LEARNING}, said
	assert "scratchpad" in planner.hinted(said), said
for said in ("learn about this program", "what do you know about this program", "what have you learned about Reaper",
		"what did you learn", "go online and learn about this game"):
	assert pad.wish(said) is None, said
lib = Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
for said, slug in (("what have you learned here", "what-was-learned-here"),
		("what was the phone number in the picture you described", "earlier-descriptions"),
		("write on the scratchpad for this program that the record key is R", "teach-visionclaw-this-program"),
		("start a scratchpad for setting up Reaper: install it, then learn the keys", "plan-a-job-on-a-scratchpad"),
		("read my scratchpad", "keep-a-scratchpad")):
	chosen = [skill.slug for skill in lib.choose(said)]
	assert slug in chosen, (said, chosen)
	# A skill made for one kind of scratchpad request takes the place of the general one, so neither is cut in half.
	assert slug == "keep-a-scratchpad" or "keep-a-scratchpad" not in chosen, (said, chosen)
for said in ("learn about this program", "what time is it", "describe the screen", "turn off typing echo", "how do I learn NVDA"):
	assert not {"what-was-learned-here", "earlier-descriptions", "teach-visionclaw-this-program",
		"plan-a-job-on-a-scratchpad"} & {skill.slug for skill in lib.choose(said)}, said
gate = lookup.NOTES["visionclaw-scratchpad"][2]
for question in ("how do I carry on after I stopped a request", "can you continue where you left off",
		"why was a line set aside", "do notes earn trust", "how do I see what you have learned"):
	assert gate.search(question), question
for question in ("how do I continue reading", "how do I stop speech", "what is the trust center in Word"):
	assert not gate.search(question), question

print("test_scratch_ways: OK")
