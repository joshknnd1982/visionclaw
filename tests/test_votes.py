# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A small model's choice asked more than once, and most of its answers taken (claw/llm.py, policy.votes). Plain
Python with a scripted model: no NVDA, no engine.

  python tests/test_votes.py
"""
import json

import harness  # noqa: F401
from visionClaw.claw import llm as llmModule, policy
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION

CHOICE = {"type": "object", "properties": {"choice": {"type": "string", "enum": ["a", "b", "c"]}}, "required": ["choice"]}
FREE = {"type": "object", "properties": {"request": {"type": "string"}}, "required": ["request"]}
TWO = {"type": "object", "properties": {"id": {"type": "string", "enum": ["x", "y"]}, "value": {"type": "string"}},
	"required": ["id", "value"]}
SWITCH = {"type": "object", "properties": {"on": {"type": "boolean"}}, "required": ["on"]}


class Scripted:
	"""A runtime whose model gives the answers in order, and writes down how it was asked."""

	def __init__(self, entry, answers):
		self._entry = entry
		self.answers = list(answers)
		self.asked = []

	def entry(self, role):
		return self._entry

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		self.asked.append(dict(options or {}))
		answer = self.answers.pop(0)
		if isinstance(answer, Exception):
			raise answer
		return answer if isinstance(answer, str) else json.dumps(answer)


def run(entry, answers, schema=CHOICE, image=None, votes=None):
	runtime = Scripted(entry, answers)
	task = taskModule.Task("test", lambda *a: None)
	model = llmModule.LLM(runtime, task)
	if votes is not None:
		model.votes = votes
	found = model.json(VISION, "system", "user", schema, image=image)
	return found, runtime.asked


SMALL = {"id": "qwen3.5-2b", "small": True}
TINY = {"id": "qwen3.5-0.8b", "small": True, "suggest": False}
LARGE = {"id": "qwen3.5-9b", "small": False}
a, b, c = {"choice": "a"}, {"choice": "b"}, {"choice": "c"}

# How many answers, by the model's size.
assert policy.votes(LARGE) == 1 and policy.votes(SMALL) == 3 and policy.votes(TINY) == 3 and policy.votes(None) == 1

# A large model is asked once.
found, asked = run(LARGE, [a])
assert found == a and len(asked) == 1 and asked[0]["temperature"] == 0

# A small model: the first answer is greedy, the next ones have a little chance in them and a seed each.
found, asked = run(SMALL, [a, b, b])
assert found == b, found
assert [options["temperature"] for options in asked] == [0, llmModule.VOTE_TEMPERATURE, llmModule.VOTE_TEMPERATURE]
assert "seed" not in asked[0] and asked[1]["seed"] != asked[2]["seed"]
# Two answers that agree are already most of three: it is not asked a third time.
found, asked = run(SMALL, [a, a])
assert found == a and len(asked) == 2
# Three different answers: the first, greedy one wins.
found, asked = run(SMALL, [c, a, b])
assert found == c and len(asked) == 3
# More answers, where a model is given them, stop once one answer has more than half.
model = llmModule.LLM(Scripted(TINY, [a, b, b, b]), taskModule.Task("test", lambda *x: None))
model.votes = 5
assert model.json(VISION, "system", "user", CHOICE) == b and len(model.runtime.asked) == 4
model = llmModule.LLM(Scripted(TINY, [a, b, c, b, a]), taskModule.Task("test", lambda *x: None))
model.votes = 5
assert model.json(VISION, "system", "user", CHOICE) == a and len(model.runtime.asked) == 5  # a tie: the first answer wins
# The smallest model gives three answers, as a small one does.
found, asked = run(TINY, [a, b, b])
assert found == b and len(asked) == 3
# A later answer that fails only ends the voting.
found, asked = run(SMALL, [a, llmModule.LLMError("cut off"), b])
assert found == a and len(asked) == 2

# Not voted on: a form with free text, a form with two fields, a question with a picture, and when turned off.
for schema, answer in ((FREE, {"request": "x"}), (TWO, {"id": "x", "value": "1"})):
	found, asked = run(SMALL, [answer], schema)
	assert found == answer and len(asked) == 1
found, asked = run(SMALL, [a], image=b"jpeg")
assert len(asked) == 1
found, asked = run(SMALL, [a], votes=1)
assert len(asked) == 1
policy.VOTING = False
found, asked = run(TINY, [a])
assert len(asked) == 1
policy.VOTING = True
# On or off is a choice too.
found, asked = run(SMALL, [{"on": True}, {"on": False}, {"on": False}], SWITCH)
assert found == {"on": False}
assert llmModule.votedField(CHOICE) == "choice" and llmModule.votedField(SWITCH) == "on"
assert llmModule.votedField(FREE) is None and llmModule.votedField(TWO) is None
# A short reasoning written before the answer is not what is voted on.
found, asked = run(SMALL, [{"reasoning": "x", "choice": "a"}, {"reasoning": "y", "choice": "b"},
	{"reasoning": "z", "choice": "b"}], CHOICE)
assert found == {"choice": "b"}, found
print("OK")
