# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The answer to a request said a sentence at a time while the model writes it, with a scripted stand-in for the
model that writes its answer in small pieces, as the engine does: what plain code has ready first, the model's
sentences as they come with keys written as NVDA writes them and nothing of the question it was given, the rest
after it; the whole answer still comes for reading, and nothing is lost on the way. And where it is not done: the
user turned it off, the model would not be the one writing, the other model checks the answer, a question may follow
it."""
import json

import harness  # noqa: F401
from visionClaw.claw import orchestrator, planner, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION

ANSWER_START = "You are VisionClaw, an assistant inside the NVDA screen reader. Answer"
FOUND = "From NVDA: title: Reports the title of the window. Keys: NVDA+t."
WRITTEN = (
	"Based on the information found, the key is NVDA plus t. Press it once to hear the title of the window you are "
	"in.\nPress it twice to have the title spelled, which helps with a name you did not catch.")


class StreamingRuntime:
	"""Answers model calls from a script, and writes a text answer to onText in pieces of `size` characters."""

	def __init__(self, script, size=5, stopAt=None):
		self.script = script
		self.size = size
		self.stopAt = stopAt
		self.calls = []
		self.streamed = []

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None,
			context=None):
		if cancel is not None and cancel.is_set():
			return None
		system, user = messages[0]["content"], messages[1]["content"]
		self.calls.append((role, system, user))
		answer = self.script(role, system, user)
		if not isinstance(answer, str):
			return json.dumps(answer)
		if onText is not None:
			for at in range(0, len(answer), self.size):
				if self.stopAt is not None and at >= self.stopAt:
					cancel.set()
					return None
				self.streamed.append(answer[at:at + self.size])
				onText(answer[at:at + self.size])
		return answer


def script(written=WRITTEN, choices=("explain_keys",), free=None):
	chosen = list(choices)

	def run(role, system, user):
		if system.startswith("You choose how VisionClaw"):
			return {"choice": chosen.pop(0) if len(chosen) > 1 else chosen[0]}
		if system.startswith("You plan the work"):
			return free
		if system.startswith("You review a plan"):
			return {"agree": True, "problem": ""}
		if system.startswith(ANSWER_START):
			return written
		if system.startswith("You check finished work"):
			return {"done": True, "missing": ""}
		if system.startswith("You check a plan while it runs"):
			return {"change": False, "why": ""}
		if "by its number" in system or "choose 0" in system:
			return {"line": 1}  # which line of what was looked up answers the question
		if system.startswith("You are VisionClaw, an assistant inside the NVDA screen reader, helping"):
			return {"question": "how do I read the title of the window"}  # a form of a plan the model wrote itself
		raise AssertionError("unexpected prompt: " + system[:60])
	return run


def registry():
	reg = tools.Registry()
	reg.add(tools.Tool("look_up", "ask NVDA, the program, the window and Windows about a question",
		lambda task, question: FOUND,
		{"question": {"type": "string", "description": "the question", "auto": True}}, looks=True,
		title="Asking NVDA, the program, the window and Windows"))
	reg.add(tools.Tool("look", "look at the screen with the vision model",
		lambda task, target, question: "The screen shows a game menu with four buttons.", {
			"target": {"type": "string", "description": "what to look at", "enum": ["window", "screen"],
				"auto": lambda part: "screen"},
			"question": {"type": "string", "description": "what to find out", "auto": True},
		}, looks=True, title="Looking at the screen", tell=tools.VERBATIM))
	reg.add(tools.Tool(tools.ANSWER, "tell the user the result", lambda task: ""))
	return reg


def run(request="How do I read the window title?", streaming=True, size=5, stopAt=None, setup=None, reasoning="auto",
		**scripted):
	rt = StreamingRuntime(script(**scripted), size=size, stopAt=stopAt)
	orch = orchestrator.Orchestrator(rt, registry(), lambda question, options: None, lambda: "Program: notepad.")
	orch.streaming = lambda: streaming
	if setup is not None:
		setup(orch)
	heard = []
	task = taskModule.Task(request, onEvent=lambda task, kind, text: heard.append((kind, text)), reasoning=reasoning)
	orch.run(task)
	said = [text for kind, text in heard if kind == taskModule.SAY]
	answers = [text for kind, text in heard if kind == taskModule.ANSWER]
	return task, said, answers, heard, rt


def words(text):
	return " ".join(str(text).split())


# Said while the model writes: each sentence as it comes, keys as NVDA writes them, without the words of the question
# the model was given, and the sentence that lost them begins with a capital. The whole answer still comes once, for
# reading, and is what it was before; the add-on is told that it was said already.
task, said, answers, heard, rt = run()
assert task.state == taskModule.DONE, task.state
assert len(said) >= 3, said
assert said[0] == "The key is NVDA+t.", said
assert not any("information found" in piece.lower() or "NVDA plus" in piece for piece in said), said
assert task.streamed is True and answers == [task.answer], answers
assert words(" ".join(said)) == words(task.answer), (said, task.answer)
# The first sentence was said before the model had finished writing: it came after only part of the answer.
first = next(i for i, (kind, _text) in enumerate(heard) if kind == taskModule.SAY)
answerAt = next(i for i, (kind, _text) in enumerate(heard) if kind == taskModule.ANSWER)
assert first < answerAt
streamedBefore = len(rt.streamed)
assert streamedBefore > 10, streamedBefore

# Turned off: nothing is said in pieces, and the whole answer is the same, word for word.
plain, saidOff, answersOff, _heard, _rt = run(streaming=False)
assert saidOff == [] and plain.streamed is False and answersOff == [plain.answer]
assert plain.answer == task.answer, (plain.answer, task.answer)

# Whatever pieces the engine writes in, the same answer is said, and nothing of it is lost. Its key is the one that was
# looked up: a key nothing looked up has is never said (the test below).
LONG = " ".join(
	f"Item {n} of the list: press NVDA plus t for the {n}th thing, which is said in full." for n in range(60))
for size in (1, 7, 64, 5000):
	whole, saidLong, _answers, _heard, _rt = run(written=LONG, size=size)
	assert whole.streamed and words(" ".join(saidLong)) == words(whole.answer), size
	assert len(whole.answer) > 4000 and "[cut]" not in whole.answer and not any("[cut]" in piece for piece in saidLong)
	assert len(saidLong) >= 60 if size < 5000 else len(saidLong) >= 2, (size, len(saidLong))

# A key that nothing looked up has (llm.keysNotFound) is never said, not even while the answer is written: neither that
# sentence nor any after it. What was found is said instead, and the whole answer has no made-up key either.
for size in (1, 5, 5000):
	madeUp, saidMadeUp, _answers, _heard, _rt = run(
		written="The key for the title is NVDA plus t, as NVDA's commands say. Then press the Jump key to go on to the "
			"next part, and NVDA plus shift plus j to come back again.", size=size)
	assert madeUp.state == taskModule.DONE, madeUp.state
	assert not any("Jump" in piece or "shift" in piece.lower() for piece in saidMadeUp), (size, saidMadeUp)
	assert "Jump" not in madeUp.answer and "NVDA+t" in madeUp.answer, (size, madeUp.answer)
	assert any("NVDA+t" in piece for piece in saidMadeUp), (size, saidMadeUp)

# What the request was taken as is said first, and what is added after the answer is said after it.
def told(orch):
	orch._taken = lambda task, request: "Understood as: how do I read the window title."
	orch.offer = lambda request, recipes: "This is said once: the NVDA developer guides can be downloaded for you."


task, said, answers, _heard, _rt = run(setup=told)
assert said[0] == "Understood as: how do I read the window title.", said
assert said[-1] == "This is said once: the NVDA developer guides can be downloaded for you.", said
assert task.answer.startswith("Understood as: how do I read the window title. The key is NVDA+t."), task.answer
assert task.answer.endswith("This is said once: the NVDA developer guides can be downloaded for you."), task.answer
assert words(" ".join(said)) == words(task.answer), (said, task.answer)

# A model that writes nothing that can be said: what was found is said as it is, as in the whole answer.
task, said, answers, _heard, _rt = run(written="Based on the information found,")
assert task.streamed and words(" ".join(said)) == words(task.answer), (said, task.answer)
assert "NVDA+t" in task.answer and said, said

# Stopped while the model writes: what was said stays said, the rest is not, and no answer follows.
task, said, answers, _heard, _rt = run(stopAt=120)
assert task.state == taskModule.CANCELLED and answers == [], (task.state, answers)
assert said and words(" ".join(said)) in words(WRITTEN.replace("Based on the information found, the", "The").replace(
	"NVDA plus t", "NVDA+t")), said

# Where plain code says everything, it is ready at once and is said whole, as before.
task, said, answers, _heard, _rt = run("What is on the screen?", choices=("describe",))
assert [s.tool for s in task.steps] == ["look", "answer"], task.steps
assert said == [] and not task.streamed and answers == [task.answer] and "game menu" in task.answer

# The very smallest models are not asked to word the answer: what was looked up is quoted, and said whole.
task, said, answers, _heard, _rt = run(setup=lambda orch: setattr(orch, "stepwise", lambda: "always"))
assert said == [] and not task.streamed and answers == [task.answer], said

# Where the other model checks the answer and may change it, it is not said before it is checked; where a question
# about a correction may follow, it is not said in pieces either, as a window that comes up silences NVDA; and where
# the setting cannot be read, it is said whole.
orch = orchestrator.Orchestrator(StreamingRuntime(script()), registry(), lambda q, o: None)
orch.streaming = lambda: True
fresh = taskModule.Task("anything")
assert isinstance(orch._spoken(fresh, verified=False), orchestrator._Spoken)
assert orch._spoken(fresh, verified=True) is None
fresh.corrects = "kill the echo please"
assert orch._spoken(fresh, verified=False) is None
orch.streaming = lambda: (_ for _ in ()).throw(KeyError("streamAnswers"))
assert orch._spoken(taskModule.Task("anything"), verified=False) is None
# The orchestrator says nothing in pieces unless the add-on turns it on: the tests and the evaluation scripts hear
# the answer whole, as before.
assert orchestrator.Orchestrator(StreamingRuntime(script()), registry(), lambda q, o: None).streaming() is False

# A plan the model writes itself, with the other model checking the result: said whole after the check.
FREE = {"steps": [{"tool": "look_up", "detail": "ask about the title"}]}
task, said, answers, _heard, rt = run(
	"Do something unusual with the window title", choices=(planner.OTHER,), free=FREE, reasoning="low")
assert [(s.tool, s.recipe) for s in task.steps] == [("look_up", None), ("answer", None)], task.steps
assert task.params.verify and any(system.startswith("You check finished work") for _r, system, _u in rt.calls)
assert said == [] and not task.streamed and answers == [task.answer] and "NVDA+t" in task.answer, (said, task.answer)

# A piece of the model's answer on its own: a piece that is only the words of the question says nothing, and the next
# piece begins the sentence; a long first sentence begun at a comma keeps its comma.
heardPieces = []
piecesTask = taskModule.Task("x", onEvent=lambda task, kind, text: heardPieces.append(text) if kind == taskModule.SAY else None)
spoken = orchestrator._Spoken(piecesTask)
assert spoken._piece("Based on the information found,") is False and not spoken.used
assert spoken._piece("the key is NVDA plus control plus escape.") is True
assert heardPieces == ["The key is NVDA+control+escape."], heardPieces
assert spoken._piece("To read the title of the window you are in right now,") is True
assert heardPieces[-1] == "To read the title of the window you are in right now,", heardPieces
assert spoken._piece("- **Press** NVDA+t\n") is True and heardPieces[-1] == "Press NVDA+t.", heardPieces
assert spoken.used and spoken.fromModel
assert spoken.say("") is False and spoken.say("Plain code's sentence.") is True
print("OK")
