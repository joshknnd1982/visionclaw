# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Questions about the control the user is on (claw/focus.py), and choosing without a question between two ways that
only look (consensus._bothLook, orchestrator._nextWays). Plain Python, with a scripted model.

The owner asked on 2026-11-19 "what is the current focused control", and VisionClaw said it was not sure and asked
whether to look at the screen or run an NVDA command. Every request of the owner's that went wrong belongs here.

  python tests/test_focus.py
"""
import re

import harness  # noqa: F401
from test_core import FakeRuntime, makeRegistry, script
from visionClaw.claw import consensus, focus, lookup, orchestrator, planner, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION

# --- What the words ask: plain code, no model ---
ASKS = {
	# The owner's own words, from VisionClaw's log of 2026-11-17 to 2026-11-19.
	"tell me about the focused control.": (focus.FOCUS, {focus.WHAT}),
	"tell me about the currently focused button.": (focus.FOCUS, {focus.WHAT}),
	"what does this button do?": (focus.FOCUS, {focus.DOES}),
	"What is currently highlighted? What will happen if I press enter where I am at now?": (focus.FOCUS, {focus.DOES}),
	"Ask nvda about the currently selected icon on my desktop.": (focus.FOCUS, {focus.WHAT}),
	"look at my desktop and tell me what object is currently selected.": (focus.FOCUS, {focus.WHAT}),
	# Other ways of asking.
	"what is the current focused control": (focus.FOCUS, {focus.WHAT}),
	"what has focus": (focus.FOCUS, {focus.WHAT}),
	"what am I focused on": (focus.FOCUS, {focus.WHAT}),
	"what kind of control is this": (focus.FOCUS, {focus.WHAT}),
	"is this checkbox checked": (focus.FOCUS, {focus.STATE}),
	"is this button turned on or off": (focus.FOCUS, {focus.STATE}),
	"does this thing have a shortcut key": (focus.FOCUS, {focus.KEYS}),
	"what's the shortcut key for this button": (focus.FOCUS, {focus.KEYS}),
	"what is this field for": (focus.FOCUS, {focus.DOES}),
	"what is the navigator object on": (focus.NAVIGATOR, {focus.WHAT}),
	"what's under my mouse": (focus.MOUSE, {focus.WHAT}),
	"which link is focused on this page": (focus.FOCUS, {focus.WHAT}),
	# "Describe" asks what it is too, and how it looks.
	"describe the focused control": (focus.FOCUS, {focus.WHAT, focus.LOOKS}),
}
for said, (which, asks) in ASKS.items():
	found = focus.wish(said)
	assert found is not None, said
	assert (found["object"], found["asks"]) == (which, asks), (said, found)
	assert planner.hint(said) == "about_focus", (said, planner.hint(said))

# Words that look like such a question and ask for something else.
for said in (
	"switch to focus mode", "turn on the focus highlight", "stop nvda from saying focus mode and browse mode out loud",
	"move the focus to the address bar", "set focus to the search box", "check this checkbox", "click the ok button",
	"press this button for me", "name this unlabeled button Send", "give this site keys to move between posts",
	"type my email address into this field", "how do I get nvda to tell me what's focused", "read me what's selected",
	"read the selected text", "which program has the focus", "what colour is this button", "what does this dialog say",
	"what does this picture show", "what's the window class of this control", "describe what's in this window",
	"what program am I in", "what's on my screen", "what time is it",
):
	assert focus.wish(said) is None or planner.hint(said) != "about_focus", (said, focus.wish(said), planner.hint(said))
# Everything NVDA knows about a control, and its technical facts, stay with object_facts.
for said in ("tell me everything about this control", "Tell me everything NVDA knows about this control.",
		"tell me the name, role and state of this object"):
	assert planner.hint(said) == "object_facts", (said, planner.hint(said))

# A question about the control the user is on is decided by plain code: no model is asked, and nobody is asked.
reg = makeRegistry({})
reg.add(tools.Tool("about_focus", "say what the control the user is on is", lambda task, asked: f"About: {asked}",
	{"asked": {"type": "string", "description": "the words", "auto": True}}, looks=True, title="Asking NVDA about it",
	tell=tools.VERBATIM))
for said in ASKS:
	assert planner.decided(said, reg) == "about_focus", said
assert planner.fitted("about_focus", "what program am I in", "where_am_i") == "where_am_i"
# A question the model finds no job for is looked up, not planned freely; something to do still is planned.
for said in ("tell me a joke", "what's 15 times 12", "is it raining", "do I have mail", "please tell me a story"):
	assert planner.fitted(planner.OTHER, said, planner.hint(said)) == "nvda_question", said
for said in ("Do something unusual with the speech", "could you do something weird with the speech"):
	assert planner.fitted(planner.OTHER, said, planner.hint(said)) == planner.OTHER, said
# NVDA's focus mode and browse mode switched now are its command, decided without a model; how the switch sounds is not.
for said in ("switch to focus mode", "go into focus mode please", "toggle browse mode"):
	assert planner.decided(said, reg) is None or planner.hint(said) == "do_command", said
	assert planner.hint(said) == "do_command", (said, planner.hint(said))
assert planner.hint("make nvda beep when it switches to focus mode") != "do_command"
# "Remember me" on a form is a box, not something to keep.
assert planner.hint("is the remember me box ticked") != "remember"
assert planner.hint("remember that I like short answers") == "remember"

# --- The answer: NVDA's facts in plain words, starting with the answer ---
menu = {"name": "Menu", "role": "BUTTON", "roleText": "button", "states": ["COLLAPSED", "HASPOPUP", "FOCUSABLE", "FOCUSED"],
	"app": "claude", "title": "Claude", "inside": "tool bar \"Navigation\"", "nextTime": "NVDA+Tab"}
said = focus.answer(menu, focus.wish("what is the current focused control"))
assert said.startswith("The focus is on the button \"Menu\" in the window \"Claude\" of the program claude."), said
assert "It is collapsed, it opens a menu or list." in said and "focusable" not in said and "focused," not in said, said
assert said.endswith("Press Space or Enter to press it. Next time, NVDA+Tab says what has the focus."), said
said = focus.answer(dict(menu, does="It opens the main menu of the program."), focus.wish("what does this button do"))
assert "Pressing Enter or Space presses the button \"Menu\"." in said, said
assert "A guess from its name and picture, which may be wrong: It opens the main menu of the program." in said, said
assert "Press Space or Enter to press it." not in said, said
# A description says what it does; no guess is wanted then.
assert not focus.needsGuess(dict(menu, description="Opens the menu"), focus.wish("what does this button do"))
assert focus.needsGuess(menu, focus.wish("what does this button do"))
assert not focus.needsGuess(menu, focus.wish("what is the focused control"))
assert not focus.needsGuess(dict(menu, role="LINK"), focus.wish("what does this link do"))
# Yes or no, from the states.
box = {"name": "Remember me", "role": "CHECKBOX", "roleText": "check box", "states": []}
assert focus.answer(box, focus.wish("is this checkbox checked")).startswith("No. The focus is on the check box"), box
assert "It is not checked." in focus.answer(box, focus.wish("is this checkbox checked"))
assert focus.answer(box, focus.wish("is this box unchecked")).startswith("Yes.")
assert focus.answer(dict(box, states=["CHECKED"]), focus.wish("is this checkbox ticked")).startswith("Yes.")
assert focus.answer({"name": "Save", "role": "BUTTON", "roleText": "button", "states": ["UNAVAILABLE"]},
	focus.wish("is this button greyed out")).startswith("Yes.")
assert focus.answer({"name": "Save", "role": "BUTTON", "roleText": "button", "states": []},
	focus.wish("is this button enabled")).startswith("Yes.")
said = focus.answer({"name": "Save", "role": "BUTTON", "roleText": "button", "states": []}, focus.wish("is this button turned on or off"))
assert not said.startswith(("Yes", "No")) and "NVDA reports no state for it" in said, said
# A name for an object without one is said with where it is from, and "probably" where it is not sure.
bare = {"name": "", "vagueName": "btn", "role": "BUTTON", "roleText": "button", "states": [], "named": ("Play", False, focus.PICTURE)}
said = focus.answer(bare, focus.wish("what is this button"))
assert "It has no name of its own (NVDA says only \"btn\"); from its picture it is probably \"Play\"." in said, said
said = focus.answer(dict(bare, named=("Play", True, focus.BY_YOU)), focus.wish("what is this button"))
assert "you named it \"Play\"" in said and "probably" not in said, said
# The navigator object and the mouse have their own sentences.
assert focus.answer(menu, focus.wish("what is the navigator object on"), focus.NAVIGATOR).startswith("The navigator object is the button")
assert focus.answer(menu, focus.wish("what's under my mouse"), focus.MOUSE).startswith("The mouse pointer is over the button")
assert focus.answer(menu, focus.wish("which link is focused"), focus.BROWSE).startswith("In browse mode, the reading position is on")
# A model's guess that says nothing is no guess.
for empty in ("", "Unknown", "It is not known what it does.", "Menu", "button", "I cannot tell"):
	assert focus.cleanGuess(empty, menu) == "", empty
assert focus.cleanGuess("Opens the main menu.", menu) == "Opens the main menu"
# Nothing in it needs sight, and every key every keyboard has where VisionClaw names one of its own.
for sentence in list(focus._USE.values()) + list(focus._ENTER.values()):
	assert not re.search(r"\b(click|colou?r|look at|see|hover)\b", sentence, re.IGNORECASE), sentence

# --- Two ways that only look: no question to the user ---
assert planner.onlyLooks("describe", reg) and planner.onlyLooks("nvda_question", reg)
assert not planner.onlyLooks("change_setting", reg) and not planner.onlyLooks("press_keys", reg)
assert planner.firstWay("describe", "nvda_question") == ("nvda_question", "describe")
assert planner.firstWay("nvda_question", "describe") == ("nvda_question", "describe")
assert planner.firstWay("explain_keys", "nvda_question") == ("explain_keys", "nvda_question")


def runWith(request, choices, otherChoices=None, lookUp=None, oneModel=False, forms=()):
	state, asked = {}, []

	def askUser(question, options):
		asked.append((question, options))
		return None

	registry = makeRegistry(state)
	if lookUp is not None:
		registry.add(tools.Tool("look_up", "ask NVDA, the program, the window and Windows about a question", lookUp,
			{"question": {"type": "string", "description": "the question", "auto": True}}, looks=True,
			title="Asking NVDA, the program, the window and Windows"))

	class Runtime(FakeRuntime):
		def oneModel(self):
			return oneModel

	rt = Runtime(script(choices=choices, otherChoices=otherChoices, forms=list(forms)))
	orch = orchestrator.Orchestrator(rt, registry, askUser, lambda: "Program: notepad.", None)
	task = taskModule.Task(request)
	orch.run(task)
	return task, state, asked


def talked(task, words):
	return any(words in text for _t, kind, text in task.log if kind == taskModule.TALK)


# Two models that still differ after looking again, both on ways that only look: the user is not asked. The picture
# comes after what NVDA says.
task, state, asked = runWith("what is going on in here", ["describe"], ["nvda_question"])
assert not asked, asked
assert task.state == taskModule.DONE, task.state
assert talked(task, "Both ways only look and change nothing, so VisionClaw does not ask"), task.log
assert [s.recipe for s in task.steps if s.tool != tools.ANSWER] == ["nvda_question"], [s.recipe for s in task.steps]
assert "looked" not in state, state
# Where the first way finds nothing, the other is tried, and the user is told.
task, state, asked = runWith("what is going on in here", ["describe"], ["nvda_question"],
	lookUp=lambda task, question: lookup.nothingText(question))
assert not asked and task.state == taskModule.DONE, (asked, task.state)
assert [s.recipe for s in task.steps if s.tool != tools.ANSWER] == ["nvda_question", "describe"], [s.recipe for s in task.steps]
assert "looked" in state and talked(task, "That did not answer it, so VisionClaw tried another way"), task.log
# Where the first way fails outright, the other is tried, and nobody is asked what to do.


def failing(task, question):
	raise tools.ToolError("Nothing could be asked.")


# The model is asked to correct the form after the error, as with every failed step, before the other way is tried.
task, state, asked = runWith("what is going on in here", ["describe"], ["nvda_question"], lookUp=failing,
	forms=[{"question": "what is going on in here"}] * 4)
assert not asked and "looked" in state, (asked, state)
# Where one of the two ways changes something, the user still decides.
task, state, asked = runWith("what is going on in here", ["describe"], ["press_keys"])
assert asked and "The two models do not agree" in asked[0][0], asked
# One model for both jobs, its choice questioned by the words, and both ways only look: no question either.
task, state, asked = runWith("read the text that is shown", ["describe"], oneModel=True)
assert not asked or "not sure" not in asked[0][0], asked
print("OK")
