# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Corrections read by plain code, and what may be offered to keep as the user's own words (claw/corrections.py).
Plain Python: no NVDA, no model.

  python tests/test_corrections.py
"""
import harness  # noqa: F401
from visionClaw.claw import corrections

# What was meant, from the ways people correct a request.
for said, meant in (
		("no, I meant turn off the typing echo", "turn off the typing echo"),
		("No I meant to open the system tray", "open the system tray"),
		("nope, I wanted you to read the title", "read the title"),
		("I meant the volume of the computer", "the volume of the computer"),
		("not that, I meant the notification area", "the notification area"),
		("not that one, the second link", "the second link"),
		("that's not what I meant, I wanted the start menu", "the start menu"),
		("That is not what I asked for. Open quick settings instead.", "Open quick settings"),
		("wrong one, I meant the Save button", "the Save button"),
		("no, turn it off", "turn it off"),
		("No, open Notepad please", "open Notepad"),
		("no no, I meant speak slower", "speak slower")):
	assert corrections.correctionOf(said) == meant, (said, corrections.correctionOf(said))
# Not corrections: an answer, a request of its own, a word taught, an everyday "no".
for said in ("no, that's fine", "I want to open Notepad", "nobody is in the photo", "no problem", "notepad please",
		"what does no mean", "I mean it, stop talking", "noted, thanks"):
	assert corrections.correctionOf(said) is None, (said, corrections.correctionOf(said))

# What may be offered to keep: the words that were understood wrongly, and what was meant.
assert corrections.offer("kill the typing echo", "turn off the typing echo") == ("kill the typing echo", "turn off the typing echo")
assert corrections.offer("Kill the typing echo.", "turn off the typing echo") == ("Kill the typing echo", "turn off the typing echo")
assert corrections.offer("echo", "turn off the typing echo") is None  # one word: too little to be sure of
assert corrections.offer("x" * 70 + " y", "something") is None  # too long to be one way of saying one thing
assert corrections.offer("turn off the typing echo", "Turn off the typing echo") is None  # the same
assert corrections.offer("remember that I like short answers", "something") is None
assert corrections.offer('type "hello there"', "something") is None
assert corrections.offer("no, I meant the start menu", "the start menu") is None
assert corrections.offer("kill the echo", "turn off typing echo", refusal=lambda s, m: "cannot") is None
assert corrections.offer("kill the echo", "turn off typing echo", refusal=lambda s, m: "") == ("kill the echo", "turn off typing echo")
question = corrections.question("kill the echo", "turn off typing echo")
assert question.startswith('Should VisionClaw understand "kill the echo" as "turn off typing echo" from now on?'), question
assert 'say "forget the word kill the echo" to undo it' in question

# --- Whole requests through the orchestrator, with a scripted model ---

import shutil  # noqa: E402
import tempfile  # noqa: E402

from test_core import FakeRuntime, makeRegistry, script  # noqa: E402
from visionClaw.claw import memories, orchestrator, understand  # noqa: E402
from visionClaw.claw import task as taskModule  # noqa: E402

GOOD = {"setting": "speech.rate", "value": "70"}


def runner(own, answers, remembering=memories.AUTO, forms=None):
	questions = []

	def ask(question, choices):
		questions.append((question, list(choices)))
		return answers.pop(0) if answers else None
	orch = orchestrator.Orchestrator(FakeRuntime(script(forms=forms or [GOOD] * 6)), makeRegistry({}), ask,
		lambda: "Program: notepad.")
	orch.understanding = understand.Grammar(own)
	orch.remembering = lambda: remembering
	return orch, questions


own = tempfile.mkdtemp()
try:
	orch, questions = runner(own, [0])
	first = orch.run(taskModule.Task("kill the echo please"))
	assert first.state == taskModule.DONE, first.log
	# The correction is done instead, and then the user is asked once whether to keep the words.
	task = orch.run(taskModule.Task("no, I meant make nvda talk faster"))
	assert task.state == taskModule.DONE, task.log
	assert any('So the request before, "kill the echo please", was not what you meant' in str(entry) for entry in task.log), task.log
	assert len(questions) == 1 and questions[0][0].startswith(
		'That was done. Should VisionClaw understand "kill the echo" as "make nvda talk faster" from now on?'), questions
	assert questions[0][1] == list(corrections.CHOICES)
	assert task.answer.endswith(
		'From now on, VisionClaw understands "kill the echo" as "make nvda talk faster". To undo it, say forget the word kill the echo.'), task.answer
	assert understand.Grammar(own).own() == [("kill the echo", "make nvda talk faster")]
	# The next time the same words are understood rightly at once, and the user is told so.
	again = orch.run(taskModule.Task("kill the echo"))
	assert again.answer.startswith("Understood as: make nvda talk faster."), again.answer
	assert len(questions) == 1
	# A no keeps nothing.
	shutil.rmtree(own)
	orch, questions = runner(own, [1])
	orch.run(taskModule.Task("zap the echo"))
	task = orch.run(taskModule.Task("not that, I meant make nvda talk faster"))
	assert task.state == taskModule.DONE and len(questions) == 1 and not task.answer.endswith("forget the word zap the echo.")
	assert understand.Grammar(own).own() == []
	# When VisionClaw may only keep what the user asks it to keep, it does not ask.
	orch, questions = runner(own, [0], remembering=memories.ASKED)
	orch.run(taskModule.Task("zap the echo"))
	task = orch.run(taskModule.Task("no, I meant make nvda talk faster"))
	assert task.state == taskModule.DONE and questions == [] and understand.Grammar(own).own() == []
	# A correction with no request before it is simply done.
	orch, questions = runner(own, [0])
	task = orch.run(taskModule.Task("no, I meant make nvda talk faster"))
	assert task.state == taskModule.DONE and questions == [], (task.log, questions)
	# A corrected request that did not go well is not offered.
	orch, questions = runner(own, [0], forms=[GOOD] + [{"setting": "nope", "value": "1"}] * 20)
	orch.run(taskModule.Task("zap the echo"))
	task = orch.run(taskModule.Task("no, I meant make nvda talk faster"))
	# (The user was asked what to do about the failed step, which is no offer to keep words.)
	assert not any("Should VisionClaw understand" in question for question, _choices in questions), questions
	assert understand.Grammar(own).own() == [], understand.Grammar(own).own()
finally:
	shutil.rmtree(own, ignore_errors=True)
print("OK")
