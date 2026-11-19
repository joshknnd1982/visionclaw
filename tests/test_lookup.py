# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Answering a question from NVDA, the program in front, its window and Windows, in that order, and only with
what is about the question. Plain Python: no NVDA and no model.

The commands are every command of NVDA 2026.3.1 (tests/nvda_commands.json); the notes are VisionClaw's own
knowledge files, among them the keys of Windows; the page of help is a small stand-in for NVDA's user guide.

  python tests/test_lookup.py
"""
import json
import os

import harness  # noqa: F401
from visionClaw.claw import lookup, orchestrator, planner, policy, ranking, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.knowledge import Knowledge

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "nvda_commands.json"), encoding="utf-8") as f:
	NVDA = json.load(f)


def keysOf(command):
	keys = [g.split(":", 1)[1] for g in command["gestures"] if g.startswith(("kb:", "kb(desktop):"))]
	return " or ".join(keys) if keys else "no key assigned"


GUIDE = """
<html><head><title>User Guide</title><style>h1 {color: red}</style></head><body>
<h1>NVDA User Guide</h1><p>Table of contents: Browse Mode. Screen Curtain. The desktop keyboard layout.</p>
<h2>Browse Mode</h2>
<p>Complex read-only documents such as web pages are browsed in NVDA using browse mode.</p>
<p>In browse mode the arrow keys move through the page as if it were a text document.</p>
<table><tr><th>Name</th><th>Desktop key</th><th>Laptop key</th><th>Description</th></tr>
<tr><td>Toggle browse and focus modes</td><td>NVDA+space</td><td>NVDA+space</td><td>Toggles between focus mode and browse mode</td></tr>
<tr><td>Find</td><td>NVDA+control+f</td><td>NVDA+control+f</td><td>Finds text in the page</td></tr></table>
<h3>Single Letter Navigation</h3>
<ul><li>h: heading</li><li>k: link</li></ul><p>Press h to move to the next heading &amp; shift+h to move back.</p>
<h2>Screen Curtain</h2>
<p>NVDA contains a feature called Screen Curtain, which can be enabled to make the screen black.</p>
<h2>The NVDA Modifier Key</h2>
<p>The NVDA modifier key is either the insert key or the capsLock key.</p>
</body></html>
"""

# --- A page of help as passages: table headings are left out, and a row stays with its keys ---
sections = lookup.htmlSections(GUIDE)
titles = [title for title, _body in sections]
assert titles == ["Browse Mode", "Single Letter Navigation", "Screen Curtain", "The NVDA Modifier Key"], titles
browse = dict(sections)["Browse Mode"]
assert "Desktop key" not in browse and "Laptop key" not in browse and "color" not in browse, browse
assert "Toggle browse and focus modes, NVDA+space, NVDA+space, Toggles between focus mode and browse mode;" in browse, browse
assert "next heading & shift+h" in dict(sections)["Single Letter Navigation"]
assert lookup.chunks("One. Two. Three.", 8) == ["One.", "Two.", "Three."] and lookup.chunks("") == []
assert all(len(piece) <= 700 for piece in lookup.chunks("word " * 2000))
assert lookup.shorten("First sentence here. Second sentence here. Third.", 44) == "First sentence here. Second sentence here."

knowledge = Knowledge()
knowledge.addSource("userGuide", lambda: [(title, body, "userGuide") for title, body in sections])
COMMANDS = [lookup.fromCommand(
	c["name"], c["description"], c["category"],
	f"{c['name']}: {c['description'].strip().rstrip('.')}. Keys: {keysOf(c)}.") for c in NVDA]
PROGRAM = lookup.Passage(
	lookup.APP, "The program in front", "The program in front is notepad, version 11.2.", "the program notepad", here=True)
WINDOW = lookup.Passage(
	lookup.WINDOW, "The window in front", "The window in front is called Untitled - Notepad.", "this window", here=True)
KEYS = lookup.Passage(
	lookup.WINDOW, "Keys of the controls in this window", "Word wrap (check box): Alt+W; Zoom in (button): Control+Plus.",
	"this window")
OPEN = lookup.Passage(
	lookup.SYSTEM, "The windows that are open now", "2 windows are open now: Untitled - Notepad; Inbox - Mail.")
# In another order than they are asked, to show that the order of the answer does not depend on it.
POOL = [OPEN, KEYS, WINDOW, PROGRAM] + lookup.fromSections(knowledge.everything()) + COMMANDS


def found(question):
	return lookup.about(question, POOL)


def lines(question):
	return lookup.resultText(found(question)).splitlines()


# --- The question that went wrong ---
# "How can I use the keyboard to navigate my desktop?" was put to NVDA's commands alone, and the command that
# switches between the desktop and laptop keyboard layouts was given as the answer.
asked = "How can I use the keyboard to navigate my desktop?"
said, light = lookup.asked(asked)
assert said - light == {"navig", "desktop"} and light == {"keyboard"}, (said, light)
answer = lines(asked)
assert answer[0].startswith(
	"From Windows: The desktop: going to it and navigating its icons with the keyboard. Press Windows+D to go to the desktop;"), answer
assert "arrow keys move from icon to icon" in answer[0] and "Enter opens it" in answer[0]
assert not any("toggleKeyboardLayout" in line for line in answer), answer
# The answer for the very smallest models is that line, word for word.
assert lookup.quoted("\n".join(answer)) == answer[0]
# Every NVDA command was among what was asked, and plain code left the wrong one out.
assert any("toggleKeyboardLayout" in passage.text for passage in POOL)

# --- NVDA is asked first, and answers what is NVDA's ---
answer = lines("How do I read the window title?")
assert answer[0].startswith("From NVDA: title: Reports the title of the current application or foreground window."), answer
assert answer[0].endswith("Keys: NVDA+t."), answer
assert lines("what key reads the current line")[0].startswith("From NVDA: reportCurrentLine:")
assert lines("how do I find out what time it is") == [
	"From NVDA: dateTime: If pressed once, reports the current time. If pressed twice, reports the current date. Keys: NVDA+f12."]
assert lines("how do I make NVDA read everything")[0].startswith("From NVDA: sayAll:")
assert lines("how do I open the NVDA menu")[0] == "From NVDA: showGui: Shows the NVDA menu. Keys: NVDA+n."

# --- Windows answers what is Windows' ---
for question, key in (
	("how do I switch between open windows", "Alt+Tab switches between open windows"),
	("how do I open the start menu", "Press the Windows key, or Control+Escape, to open or close the Start menu"),
	("how do I rename a file", "F2 renames it"),
	("how do I get to the system tray", "Windows+B moves to the first icon in the notification area"),
	("how do I lock my computer", "Windows+L locks the computer"),
	("how do I go to the taskbar", "Windows+T moves to the taskbar"),
	("how do I minimize a window", "minimizes"),
	("how do I save a file", "Control+S saves the file"),
	("how do I select text", "Hold Shift with any key that moves the cursor"),
	("how do I close this program", "Alt+F4 closes the window in use"),
	("how do I shut down the computer", "Alt+F4 offers to shut down"),
):
	answer = lines(question)
	assert answer[0].startswith("From Windows: ") and key in answer[0], (question, answer)
# Where NVDA and Windows both have an answer, both are given, NVDA's first; and the smallest models say both.
answer = lines("how do I copy text")
assert answer[0].startswith("From NVDA: ") and any(
	line.startswith("From Windows: Copy, cut, paste, undo and redo. Control+C copies") for line in answer), answer
both = lookup.quoted("\n".join(answer))
assert both.startswith("From NVDA: ") and "From Windows: Copy, cut, paste, undo and redo. Control+C copies" in both, both

# --- What something is: an explanation, from where its section begins, not a command ---
answer = lines("what is browse mode")
assert answer[0].startswith(
	"From NVDA's user guide: Browse Mode. Complex read-only documents such as web pages are browsed in NVDA using "
	"browse mode. In browse mode the arrow keys move through the page as if it were a text document. Toggle browse "
	"and focus modes, NVDA+space, NVDA+space, Toggles between focus mode and browse mode;"), answer
assert not answer[0].startswith("From NVDA: ")
assert lines("What is a screen curtain?")[0].startswith("From NVDA's user guide: Screen Curtain. NVDA contains a feature")
# "NVDA" and "key" say nothing in most questions; here they are what is asked about.
assert lookup.asked("what is the NVDA key")[0] == {"nvda", "key"}
assert "From NVDA's user guide: The NVDA modifier key is either the insert key or the capsLock key." in lines("what is the NVDA key")
assert lookup.isWhatIs("what is browse mode") and lookup.isWhatIs("how do I use object navigation")
assert not lookup.isWhatIs("what is the shortcut for copy") and not lookup.isWhatIs("what key reads the title")
assert not lookup.isWhatIs("How can I use the keyboard to navigate my desktop?") and not lookup.isWhatIs("what does NVDA+T do")

# --- A key that is written out finds what that key does ---
assert lookup.keysIn("what does NVDA+T do") == ["nvda+t"] and lookup.keysIn("what is ctrl + alt+n for") == ["control+alt+n"]
assert lookup.keysIn("what does win+d do") == ["windows+d"] and lookup.keysIn("how do I read the title") == []
assert lookup.hasKey("Keys: NVDA+t.", "nvda+t") and not lookup.hasKey("Keys: NVDA+tab.", "nvda+t")
assert not lookup.hasKey("Keys: control+NVDA+t.", "nvda+t")
assert lines("what does NVDA+T do")[0].startswith("From NVDA: title: Reports the title")
assert lines("what does Windows+D do")[0].startswith("From Windows: The desktop: going to it")
assert lines("What does NVDA+space do?")[0].startswith("From NVDA")

# --- Where the user is: the program and the window are the answer, or part of it ---
assert lookup.isHere("what can I do here") and lookup.isHere("how do I close this program")
assert not lookup.isHere("what key reads the current line") and not lookup.isHere("how do I read the title")
assert lines("What can I do here?") == [
	"From the program notepad: The program in front is notepad, version 11.2.",
	"From this window: The window in front is called Untitled - Notepad."]
assert lines("what does this program do") == lines("What can I do here?")
answer = lines("How do I read the title of this window?")
assert answer[0].startswith("From NVDA: title:") and answer[-2:] == lines("What can I do here?"), answer
# The window's own controls answer for themselves, with their keys.
answer = lines("how do I turn on word wrap")
assert answer[0] == "From this window: Keys of the controls in this window. Word wrap (check box): Alt+W; Zoom in (button): Control+Plus.", answer
assert lines("which windows are open")[0].startswith("From Windows: The windows that are open now. 2 windows are open now: Untitled - Notepad;")

# For the smallest models, where the user is, is said whole: the program and the window together.
assert lookup.quoted("\n".join(lines("What can I do here?"))) == (
	"From the program notepad: The program in front is notepad, version 11.2. "
	"From this window: The window in front is called Untitled - Notepad.")
# Words that only ask how much do not stand in the way of what is asked about.
assert lines("How much battery is left?")[0].startswith("From NVDA: say_battery_status:"), lines("How much battery is left?")

# --- Among equally good answers the order is NVDA, the program, the window, Windows ---
same = [
	lookup.Passage(lookup.SYSTEM, "Quokka care", "Feed the quokka."), lookup.Passage(lookup.WINDOW, "Quokka care", "Feed the quokka."),
	lookup.Passage(lookup.APP, "Quokka care", "Feed the quokka."), lookup.Passage(lookup.NVDA, "Quokka care", "Feed the quokka."),
]
assert [passage.source for passage in lookup.about("how do I care for a quokka", same, limit=4)] == list(lookup.ORDER)

# --- Nothing fits: plain code says so, because a small model cannot say "none of these" ---
assert found("how do I bake a cake") == [] and found("") == [] and found("xyzzy plugh") == []
nothing = lookup.nothingText("how do I bake a cake", "notepad", "Untitled - Notepad")
assert nothing == (
	"Nothing was found about bake or cake. Asked were: NVDA's commands and user guide, the program notepad, its "
	"window Untitled - Notepad, and what VisionClaw knows about Windows."), nothing
assert lookup.isNothing(nothing) and not lookup.isNothing("From NVDA: title")
assert lookup.nothingText("how?").startswith("Nothing was found about that. Asked were: NVDA's commands and user guide, the program in front")
# Notes written for people who write add-ons are left out of a user's question, and are there for theirs.
assert not any(passage.developer for passage in found("how do I read the window title"))
assert any(passage.developer for passage in found("how does an add-on script bind a gesture in code"))
assert lookup.isDeveloper("which function gives the focus") and not lookup.isDeveloper("how do I copy text")

# --- Words: endings and the few words that mean the same ---
for a, b in (("navigate", "navigating"), ("navigation", "navigator"), ("close", "closing"), ("move", "moving"),
		("stop", "stopping"), ("rename", "renames"), ("minimize", "minimizing"), ("talking", "speech"), ("app", "application")):
	assert lookup.textWords(a) == lookup.textWords(b), (a, b, lookup.textWords(a), lookup.textWords(b))
assert lookup.textWords("format") != lookup.textWords("form") and lookup.textWords("the NVDA key") == {"nvda", "key"}

# --- Ranking: what must be covered ---
things = [({"keyboard", "layout"}, {"desktop", "laptop"}), ({"desktop"}, {"navigate", "icon"}), ({"mouse"}, {"navigate"})]
assert ranking.rank({"navigate", "desktop"}, things, share=0.3) == [1, 2, 0]  # without the rule, one shared word is enough
assert ranking.rank({"navigate", "desktop"}, things, share=0.3, cover=0.6) == [1]
# A word nothing has counts for half of the rarest word: it does not shut out what has the other word,
# and where it is the only word that tells, nothing is found.
assert ranking.rank({"quokka", "desktop"}, things, share=0.3, cover=0.5) == [1, 0]
assert ranking.rank({"quokka", "desktop"}, things, share=0.3, cover=0.6) == []
assert lines("how do I read the darn window title")[0].startswith("From NVDA: title:")

# --- The plan: a question is looked up in all four, not put to NVDA's commands ---
assert planner.RECIPES["explain_keys"][2] == ("look_up",) and planner.RECIPES["nvda_question"][2] == ("look_up",)
for request, recipe in (
	("How can I use the keyboard to navigate my desktop?", "explain_keys"), ("how do I switch between open windows", "explain_keys"),
	("what is browse mode", "nvda_question"), ("Can I rename a file with the keyboard?", "nvda_question"),
	("Where is the notification area?", "nvda_question"), ("what time is it", "do_command"), ("speak faster", "change_setting"),
	("Which windows are open?", "nvda_question"), ("which windows are open", "nvda_question"), ("which window am I in", "where_am_i"),
	("who made NVDA", "nvda_question"), ("How much battery is left?", "do_command"), ("what is the battery level", "do_command"),
	("What is on my screen?", "describe"), ("where am I", "where_am_i"), ("click the OK button", "click"),
):
	assert planner.hint(request) == recipe, (request, planner.hint(request))


# --- The whole request, through the orchestrator, with the model seen in the real run ---
def lookUp(task, question):
	return lookup.resultText(lookup.about(question, POOL)) or lookup.nothingText(question, "notepad", "Untitled - Notepad")


registry = tools.Registry()
registry.add(tools.Tool(lookup.TOOL, "answer a question", lookUp,
	{"question": {"type": "string", "description": "the question", "maxLength": 300, "auto": True}},
	looks=True, title="Asking NVDA, the program, the window and Windows"))
registry.add(tools.Tool(tools.ANSWER, "tell the user the result", lambda task: ""))


class Model:
	"""One model for both jobs. small: it is asked one small question at a time and its answers are quoted."""

	def __init__(self, small, answer=""):
		self.small, self.answer, self.prompts = small, answer, []

	def oneModel(self):
		return True

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"id": "m", "name": "Model", "suggest": not self.small}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		system, user = messages[0]["content"], messages[-1]["content"]
		self.prompts.append((system, user))
		schema = ((options or {}).get("response_format") or {}).get("json_schema", {}).get("schema", {}).get("properties", {})
		if "choice" in schema:
			return json.dumps({"choice": "explain_keys"})
		if system.startswith("You are VisionClaw, an assistant inside the NVDA screen reader. Answer"):
			return self.answer
		raise AssertionError(f"an unexpected question to the model: {user}")


def run(request, small, answer=""):
	model = Model(small, answer)
	runner = orchestrator.Orchestrator(model, registry, lambda question, choices: 0)
	runner.stepwise = lambda: policy.AUTO
	return runner.run(taskModule.Task(request)), model


# The run that went wrong, with a model that is asked one small question at a time: the answer is the line
# plain code found, and it is about the desktop.
task, model = run("How can I use the keyboard to navigate my desktop?", small=True)
assert task.state == taskModule.DONE and [step.tool for step in task.steps] == ["look_up", "answer"], task.log
assert task.answer.startswith(
	"From Windows: The desktop: going to it and navigating its icons with the keyboard. Press Windows+D to go to the desktop;"), task.answer
assert "layout" not in task.answer
# The model only chose what to do (a very small model is asked that same choice more than once: claw/llm.py's votes);
# it was not asked to pick or to rephrase.
assert len(set(model.prompts)) == 1
# A larger model puts what was found into its own words, and is shown where each piece is from.
task, model = run("How do I copy text?", small=False, answer="Press Control+C to copy.")
assert task.answer == "Press Control+C to copy."
system, user = model.prompts[-1]
assert "use the pieces that are about the question and leave out the others" in system
assert "never put steps from two pieces together" in system
assert "\n1. From NVDA: " in user and "\n2. From Windows: Copy, cut, paste, undo and redo. Control+C copies" in user, user
assert lookup.numbered("From NVDA: one.") == "From NVDA: one." and lookup.numbered("A page.\nIts text.") == "A page.\nIts text."
# Nothing was found: that is said as it is, by plain code. No model is asked to put nothing into words.
for small in (True, False):
	task, model = run("How do I bake a cake?", small=small, answer="MADE UP")
	assert task.state == taskModule.DONE and task.answer == nothing, task.answer
	assert not any(system.startswith("You are VisionClaw, an assistant inside the NVDA screen reader. Answer")
		for system, _user in model.prompts)

print("OK")
