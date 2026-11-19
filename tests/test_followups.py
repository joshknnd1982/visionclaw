# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A request that follows the one before it (claw/followups.py): which requests are follow-ups and which stand
alone, what plain code writes out by itself, what a model may write and how plain code checks it, and whole
requests in a row through the orchestrator with stand-in tools and a scripted model. Plain Python.

  python tests/test_followups.py
"""
import json
import re

import harness  # noqa: F401
from visionClaw.claw import computer, followups, orchestrator, tools
from visionClaw.claw import task as taskModule

F = followups
faster = F.Last("Make NVDA speak a little faster", "Speech rate was 50 and is now 60.", 0.0)

# --- Which requests follow the one before, and what plain code makes of them ---

PLAIN = {
	"do that again": (F.AGAIN, "Make NVDA speak a little faster"),
	"Again.": (F.AGAIN, "Make NVDA speak a little faster"),
	"please do it once more": (F.AGAIN, "Make NVDA speak a little faster"),
	"try again": (F.AGAIN, "Make NVDA speak a little faster"),
	"a bit more": (F.MORE, "Make NVDA speak a little faster"),
	"more": (F.MORE, "Make NVDA speak a little faster"),
	"keep going": (F.MORE, "Make NVDA speak a little faster"),
	"too fast": (F.DIRECTION, "Make NVDA speak a little slower"),
	"that's way too fast": (F.DIRECTION, "Make NVDA speak a little slower"),
	"slower": (F.DIRECTION, "Make NVDA speak a little slower"),
	"a little slower please": (F.DIRECTION, "Make NVDA speak a little slower"),
	"even faster": (F.DIRECTION, "Make NVDA speak a little faster"),
	"the other way": (F.OTHER_WAY, "Make NVDA speak a little slower"),
	"that is too much": (F.OTHER_WAY, "Make NVDA speak a little slower"),
	"not so much": (F.OTHER_WAY, "Make NVDA speak a little slower"),
	"the same in Word": (F.AGAIN_IN, "Switch to Word. Make NVDA speak a little faster"),
	"do that again in Notepad": (F.AGAIN_IN, "Switch to Notepad. Make NVDA speak a little faster"),
	"and do the same for the calculator too": (F.AGAIN_IN, "Switch to calculator. Make NVDA speak a little faster"),
}
for said, (kind, full) in PLAIN.items():
	found = F.resolve(said, faster, 20)
	assert found == (kind, full, ""), (said, found)
	assert kind in F.PLAIN

# What a model must write out: plain code only says that the request leans on the one before.
for said, kind in {
		"and the pitch?": F.ABOUT, "what about the volume": F.ABOUT, "How about for excel?": F.ABOUT,
		"open the second one": F.REFERS, "delete the last one": F.REFERS, "read me number three": F.REFERS,
		"open it": F.REFERS, "click it": F.REFERS, "close them": F.REFERS, "louder": F.DIRECTION,
		"and what about the first one": F.REFERS}.items():
	found = F.resolve(said, faster, 20)
	assert found == (kind, None, ""), (said, found)

# Requests that stand alone, though they have "that", "it" or "and" in them, or come first.
ALONE = (
	"undo that", "forget that", "remember that I like short answers", "what is on my screen", "turn off typing echo",
	"Open notepad and maximize it", "what is this", "and also turn off the typing echo", "then open my downloads folder",
	"restore the voice pitch to what it was before you changed it", "what does this button do", "read the title of this window",
	"find the newest file in my downloads and open it", "if you see the recycle bin, open it", "is there a link called more",
	"and open notepad", "also turn the volume up", "say this", "read this to me",
	"click the more button", "set the speech rate to 70", "tell me more about this program's settings", "stop it",
)
for said in ALONE:
	assert F.resolve(said, faster, 20) == (None, None, ""), (said, F.resolve(said, faster, 20))
# "Read it" may mean what has the focus; it never means "say the last answer again", which needs "again".
assert F.resolve("read it", faster, 20)[0] == F.REFERS and F.resolve("tell me that", faster, 20)[0] == F.REFERS
assert F.resolve("read it", faster, F.SOON_SECONDS + 1)[0] is None
# With no request before, nothing leans on anything, and what asks for one in clear words is answered plainly.
for said in ("and the pitch?", "more", "open it", "the same in Word", "too fast"):
	assert F.resolve(said, None, None) == (None, None, ""), said
assert F.resolve("do that again", None, None) == (F.AGAIN, None, F.NOTHING_BEFORE)
assert F.resolve("say that again", None, None) == (F.SAY_AGAIN, None, F.NOTHING_SAID)
# The last answer said again, in VisionClaw's own words.
for said in ("say that again", "what did you say", "repeat that", "Could you repeat the answer please?", "pardon?", "I didn't catch that",
		"read that again", "tell me that once more"):
	assert F.resolve(said, faster, 20) == (F.SAY_AGAIN, None, "Speech rate was 50 and is now 60."), said

# Time. What says "again" in clear words counts whenever it comes; what only leans on the request before counts
# for ten minutes; and "open it", which may mean what has the focus, for three.
assert F.resolve("do that again", faster, 86400)[0] == F.AGAIN
assert F.resolve("say that again", faster, 86400)[0] == F.SAY_AGAIN
assert F.resolve("more", faster, F.FOLLOW_SECONDS)[0] == F.MORE and F.resolve("more", faster, F.FOLLOW_SECONDS + 1)[0] is None
assert F.resolve("and the pitch?", faster, F.FOLLOW_SECONDS + 1)[0] is None
assert F.resolve("open it", faster, F.SOON_SECONDS)[0] == F.REFERS and F.resolve("open it", faster, F.SOON_SECONDS + 1)[0] is None
assert F.resolve("open the second one", faster, F.SOON_SECONDS + 1)[0] == F.REFERS

# The other way round, and towards the way the user names.
for request, turned in {
		"Turn the computer's volume up": "Turn the computer's volume down", "make the pitch higher": "make the pitch lower",
		"Turn off the typing echo": "Turn on the typing echo", "Mute the computer": "Unmute the computer",
		"scroll down a page": "scroll up a page", "Increase the speech rate": "Decrease the speech rate"}.items():
	assert F.opposite(request) == turned, (request, F.opposite(request))
# No direction, or two of them: plain code does not guess.
assert F.opposite("set the speech rate to 80") is None and F.opposite("what is on my screen") is None
assert F.opposite("turn the volume up and the pitch down") is None
assert F.toward("make the pitch higher", "lower") == "make the pitch lower"
assert F.toward("make the pitch lower", "lower") == "make the pitch lower"
assert F.toward("turn the volume up", "lower") == "turn the volume lower"
assert F.toward("make NVDA speak faster", "louder") is None  # another thing than speed: a model writes it out
assert F.toward("set the speech rate to 80", "slower") is None

# The same in another program: a question is asked about it, a setting for one program is changed there, and
# anything else is done after switching to it.
question = F.Last("How do I make text bold?", "Press Control+B.", 0.0)
assert F.resolve("the same in Word", question, 5)[1] == "How do I make text bold in Word?"
scoped = F.Last("make NVDA speak faster only in this program", "Only in Notepad: ...", 0.0)
assert F.resolve("do that again in Word", scoped, 5)[1] == "Switch to Word. Make NVDA speak faster only in this program."
assert F.resolve("do that again in it", scoped, 5)[1] is None

# --- A thing meant by its place in the list of the last answer: plain code, no model ---

listing = F.Last("Look through my downloads folder.", (
	"2 items in Downloads. The newest first: 1. setup.exe, 5 MB, in Downloads, changed November 18, 2026, "
	"2. report.pdf, 120 KB, in Downloads, changed November 2, 2026."), 0.0)
assert F.listed(listing.answer) == ["setup.exe", "report.pdf"], F.listed(listing.answer)
windows = F.Last("Which windows are open?", "3 windows are open: 1. Inbox - Gmail - Google Chrome. 2. Settings. 3. notes.txt - Notepad.", 0.0)
assert F.listed(windows.answer) == ["Inbox - Gmail - Google Chrome", "Settings", "notes.txt - Notepad"], F.listed(windows.answer)
# No list that counts 1, 2, 3: plain code does not guess.
for answer in ("Speech rate was 50 and is now 60.", "2 files: budget 2026.xlsx in Documents, budget old.xlsx in Downloads.",
		"Version 2. 5 things changed.", "1. only one thing", "3. three 4. four", ""):
	assert F.listed(answer) == [], (answer, F.listed(answer))
for said, full in {
		"Open the second one.": "Open report.pdf.", "delete the first one": "delete setup.exe", "open number two": "open report.pdf",
		"Open the last one": "Open report.pdf", "and open the first one": "open setup.exe", "copy the second one to my desktop": "copy report.pdf to my desktop",
}.items():
	assert F.resolve(said, listing, 20) == (F.REFERS, full, ""), (said, F.resolve(said, listing, 20))
assert F.resolve("close the last one", windows, 20)[1] == "close notes.txt - Notepad"
assert F.resolve("switch to the second one", windows, 20)[1] == "switch to Settings"
# "The first button" and "the second window" are things of their own, in the window in front: they lean on nothing.
assert F.resolve("click the first button", windows, 20)[0] is None and F.resolve("switch to the second window", windows, 20)[0] is None
# A place the list does not have is said, and nothing is done.
kind, full, tell = F.resolve("open the fifth one", listing, 20)
assert full is None and tell == "The answer before listed 2 things, so there is no such one. Say its name, or its number up to 2.", tell
# "And the second one?" says nothing to do: plain code leaves it to the model.
assert F.resolve("and the second one?", listing, 20) == (F.REFERS, None, "")
# "And maximize it" after "open notepad": told by the rules that tell "it" inside one request.
notepad = F.Last("Open notepad.", "Opened Notepad.", 0.0)
assert F.resolve("and maximize it", notepad, 20) == (F.ABOUT, "Maximize notepad", ""), F.resolve("and maximize it", notepad, 20)
assert F.resolve("and close it", F.Last("What is on my screen?", "A menu.", 0.0), 20) == (F.ABOUT, None, "")
# The question to the model is the smallest that fits the kind.
system, asked = F.ask("And the status bar?", F.Last("How do I read the title of this window?", "Press NVDA+T.", 0.0), F.ABOUT)
assert system == F.ABOUT_SYSTEM and 'The new thing: "the status bar"' in asked and "How do I read the title" in asked, asked
system, asked = F.ask("click the third one", F.Last("What is on my screen?", "Buttons: New Game, Load Game, Options, Quit.", 0.0), F.REFERS)
assert system == F.THING_SYSTEM and 'The new request: "click the third one"' in asked and "Options" in asked
system, asked = F.ask("and open it", files_ := F.Last("Find files called budget.", "One file: budget.xlsx.", 0.0), F.ABOUT)
assert system == F.THING_SYSTEM and 'The new request: "open it"' in asked
assert F.ask("louder", faster, F.DIRECTION)[0] == F.SYSTEM
assert F.strong("And the status bar?") and F.strong("open the second one") and F.strong("louder") and not F.strong("open it")
for prompt in (F.SYSTEM, F.ABOUT_SYSTEM, F.THING_SYSTEM):
	# No examples in what a model reads: it copies them as if they were the answer.
	assert "for example" not in prompt.lower() and "e.g." not in prompt and "like " not in prompt.lower(), prompt

# --- What a model wrote, checked by plain code ---

files = F.Last("find files called budget", "2 files: budget 2026.xlsx in Documents, budget old.xlsx in Downloads.", 0.0)
SECOND = "open the second one"
for written in ("open budget old.xlsx", "Open the file budget old.xlsx in Downloads", "open the second file, budget old.xlsx"):
	assert F.checked(written, SECOND, files) == written, written
# Words nobody said, the old request copied, the answer copied, nothing, and far too much.
for written in (
		"delete everything on my computer", "open budget final.xlsx", "find files called budget", "",
		"2 files: budget 2026.xlsx in Documents, budget old.xlsx in Downloads.", "open " + "budget " * 80):
	assert F.checked(written, SECOND, files) is None, written
assert F.checked("What is the speech pitch?", "and the pitch?", F.Last("What is the speech rate?", "The speech rate is 50.", 0.0))
assert F.checked("Make NVDA speak a little louder", "louder", faster) == "Make NVDA speak a little louder"
# It must hold what the user said now: the pitch, not the rate again in other words.
assert F.checked("What is the rate of speech?", "and the pitch?", F.Last("What is the speech rate?", "The speech rate is 50.", 0.0)) is None
# A follow-up that leans on the request before in clear words cannot be used as it stands: a copy is refused.
title = F.Last("How do I read the title of this window?", "Press NVDA+T.", 0.0)
assert F.checked("And the status bar?", "And the status bar?", title, mustChange=True) is None
assert F.checked("the status bar", "And the status bar?", title, mustChange=True) is None
assert F.checked("How do I read the status bar of this window?", "And the status bar?", title, mustChange=True) == (
	"How do I read the status bar of this window?")
assert F.checked("open it", "open it", title) == "open it"  # this one may mean what has the focus
assert F.taken("more", "Turn the volume up") == "Understood as: Turn the volume up."
assert F.taken("x", "How do I make text bold in Word?") == "Understood as: How do I make text bold in Word?"
assert "find files called budget" in F.question(SECOND, files) and "budget old.xlsx" in F.question(SECOND, files)
assert "response" not in json.dumps(F.SCHEMA) and F.SCHEMA["required"] == ["request"]

# --- Whole requests in a row ---


def text(description, **extra):
	return dict({"type": "string", "description": description}, **extra)


FOUND = "2 files: budget 2026.xlsx in Documents, budget old.xlsx in Downloads."


def makeRegistry(state):
	reg = tools.Registry()
	V = tools.VERBATIM

	def volume(task, asked):
		wish = computer.volumeOf(asked)
		new, _held = computer.volumeNew(state.get("volume", 40), wish)
		old, state["volume"] = state.get("volume", 40), new
		return f"The computer's volume was {old} percent and is now {new} percent."

	reg.add(tools.Tool("system_volume", "the volume of the computer itself", volume,
		{"asked": text("what the user asked for", auto=True)}, changes=True, title="Working the computer's volume", tell=V))
	reg.add(tools.Tool("find_files", "find the user's files", lambda task, asked: state.setdefault("searched", []).append(asked) or FOUND,
		{"asked": text("what the user asked for", auto=True)}, looks=True, title="Looking through your files", tell=V))

	def change(task, asked):
		state.setdefault("files", []).append(asked)
		return f"Done with: {asked}"

	reg.add(tools.Tool("change_file", "make, rename, move, copy or delete a file", change,
		{"asked": text("what the user asked for", auto=True)}, changes=True, title="Working the file", tell=V))
	reg.add(tools.Tool("look_up", "ask NVDA, the program, the window and Windows", lambda task, question: (
		state.setdefault("asked", []).append(question) or "From NVDA: nothing is about this."),
		{"question": text("the question", auto=True)}, looks=True, title="Asking", tell=V))
	reg.add(tools.Tool(tools.ANSWER, "tell the user the result", lambda task: ""))
	return reg


class Model:
	"""A model that writes a follow-up out in full as the test says, and chooses what the test says."""

	def __init__(self, rewrites=None, choices=None, small=False):
		self.rewrites, self.small = rewrites or {}, small
		self.choices = dict({"Find files called budget in my downloads": "files"}, **(choices or {}))
		self.rewritten, self.chosen = [], []

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False, "suggest": not self.small}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		system, user = messages[0]["content"], messages[1]["content"]
		schema = options["response_format"]["json_schema"]["schema"]["properties"]
		if "request" in schema:
			# The question differs with the kind of follow-up; the words the user said now are in each.
			now = re.search(r'(?:The user now says|The new request|The new thing): "(.*?)"\n', user).group(1)
			self.rewritten.append((now, user, system))
			return json.dumps({"request": self.rewrites[now]})
		if "choice" in schema:
			part = re.search(r'The user asked: "(.*?)"\n', user).group(1)
			self.chosen.append((part, user))
			return json.dumps({"choice": self.choices[part]})
		raise AssertionError("the model was asked something else: " + user)


def session(model, state):
	now = {"t": 1000.0}
	orch = orchestrator.Orchestrator(model, makeRegistry(state), lambda question, options: 0, lambda: "", None)
	orch.clock = lambda: now["t"]

	def ask(request, later=5.0):
		now["t"] += later
		return orch.run(taskModule.Task(request))
	return orch, ask


def tools_(task):
	return [(step.tool, step.status) for step in task.steps]


# 1. The same again, the other way, more, and the answer said again: no model is asked anything.
state = {"volume": 40}
model = Model()
orch, ask = session(model, state)
task = ask("do that again")
assert task.state == taskModule.DONE and task.answer == F.NOTHING_BEFORE and tools_(task) == [("answer", "done")], task.answer
assert orch.last is None  # nothing to lean on was made by that
task = ask("Turn the computer's volume up")
assert task.answer == "The computer's volume was 40 percent and is now 50 percent.", task.answer
task = ask("do that again")
assert task.answer == "Understood as: Turn the computer's volume up. The computer's volume was 50 percent and is now 60 percent.", task.answer
assert task.request == "Turn the computer's volume up" and task.said == "do that again"
assert any("So this is taken as: Turn the computer's volume up" in entry for _t, kind, entry in task.log if kind == taskModule.TALK)
task = ask("too much")
assert task.answer == "Understood as: Turn the computer's volume down. The computer's volume was 60 percent and is now 50 percent.", task.answer
task = ask("more")
assert task.answer.endswith("The computer's volume was 50 percent and is now 40 percent."), task.answer
# The answer said again is the answer itself, without what was put before it, and changes nothing.
task = ask("say that again")
assert task.answer == "The computer's volume was 50 percent and is now 40 percent." and state["volume"] == 40, task.answer
assert tools_(task) == [("answer", "done")]
# After it, "again" still means the request, not the saying again.
task = ask("again")
assert state["volume"] == 30 and task.request == "Turn the computer's volume down", task.answer
assert not model.rewritten and not model.chosen
# Much later, "more" is a request of its own again; "do that again" still is not.
task = ask("do that again", later=7200)
assert state["volume"] == 20
orch2, ask2 = session(Model(choices={"more": "other"}), {"volume": 40})
ask2("Turn the computer's volume up")
assert followups.resolve("more", orch2.last, F.FOLLOW_SECONDS + 5)[0] is None

# 2. A model writes out "the second one" with the name from the answer, and plain code stands behind it.
state = {}
model = Model(rewrites={"delete the second one": "delete the file budget old.xlsx"})
orch, ask = session(model, state)
task = ask("Find files called budget in my downloads")
assert task.answer == FOUND and tools_(task)[0] == ("find_files", "done"), (task.answer, tools_(task))
task = ask("delete the second one")
assert task.request == "delete the file budget old.xlsx" and state["files"] == ["delete the file budget old.xlsx"], (task.request, state)
assert task.answer == "Understood as: delete the file budget old.xlsx. Done with: delete the file budget old.xlsx.", task.answer
assert len(model.rewritten) == 1 and "budget old.xlsx in Downloads" in model.rewritten[0][1]
# What the next request leans on is the request in full.
assert orch.last.request == "delete the file budget old.xlsx" and orch.last.answer == "Done with: delete the file budget old.xlsx."

# 3. A model that makes something up is not used: the request stays as it was said, and the one before it is
#    given to the model that chooses what to do.
state = {}
model = Model(rewrites={"delete the second one": "delete the file taxes.pdf"}, choices={"delete the second one": "nvda_question"})
orch, ask = session(model, state)
ask("Find files called budget in my downloads")
task = ask("delete the second one")
assert "files" not in state and task.request == "delete the second one" and not getattr(task, "said", ""), task.request
assert model.chosen and "The request before this one was" in model.chosen[-1][1], model.chosen
assert not task.answer.startswith("Understood as")

# 4. A model that says the request stands alone: it is taken as it was said, with nothing added.
state = {}
model = Model(rewrites={"open it": "open it"}, choices={"open it": "nvda_question"})
orch, ask = session(model, state)
ask("Find files called budget in my downloads")
task = ask("open it")
assert task.request == "open it" and "The request before this one was" not in model.chosen[-1][1]
assert model.rewritten[-1][2] == F.THING_SYSTEM

# 5. One of the very smallest models is never asked to write a request out; plain code still does what it can.
state = {"volume": 40}
model = Model(choices={"delete the second one": "nvda_question"}, small=True)
orch, ask = session(model, state)
ask("Turn the computer's volume up")
task = ask("the other way")
assert state["volume"] == 40 and task.answer.startswith("Understood as: Turn the computer's volume down.")
task = ask("delete the second one")
assert not model.rewritten and "The request before this one was" in model.chosen[-1][1]

# 6. A request that failed can be done again, and a stopped one too: what was asked is kept either way.
state = {"volume": 40}
orch, ask = session(Model(), state)
task = taskModule.Task("Turn the computer's volume up")
task.cancel.set()
orch.clock = lambda: 50.0
orch.run(task)
assert task.state == taskModule.CANCELLED and orch.last.request == "Turn the computer's volume up" and orch.last.done is False
task = orch.run(taskModule.Task("try again"))
assert task.state == taskModule.DONE and state["volume"] == 50, task.answer

print("OK")
