# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - asking a model for one small thing: a JSON form that must match a schema, or a short text.
# The context size is chosen for each request from how long it is, and the reasoning level decides how much
# the model may think first. No NVDA dependencies.

import base64
import collections
import copy
import json
import re

from . import debuglog
from . import runtime as runtimeModule
from . import task as taskModule
from ..engine import EngineError

OFF, LOW, MEDIUM, HIGH = "off", "low", "medium", "high"
LEVELS = (OFF, LOW, MEDIUM, HIGH)
# How long the written-out reasoning before a JSON answer may be, in characters.
_THOUGHT_CHARS = {LOW: 160, MEDIUM: 400, HIGH: 900}
# Extra tokens a model with its own thinking mode may spend thinking before a text answer.
_THINK_TOKENS = {MEDIUM: 700, HIGH: 1800}
_IMAGE_TOKENS = 1300
THOUGHT = "reasoning"
# How much chance is in the answers after the first, when a small model's choice is voted on, and the first seed.
VOTE_TEMPERATURE = 0.7
VOTE_SEED = 1000


class LLMError(EngineError):
	"""The model did not give a usable answer."""


def clip(text, chars):
	"""Cut text to a length a small model can take in, saying that it was cut. Only for what a model reads of
	results, notes, pages and code: never for the user's own words, never for what the user reads or hears, and
	never for the log (uncut)."""
	text = str(text or "").strip()
	return text if len(text) <= chars else text[:chars].rstrip() + CUT


# What clip puts at the end of a text it cut. The user never reads or hears it (tests/test_whole.py).
CUT = " ...[cut]"


def uncut(text):
	"""Text as it is, however long: for the user's own words wherever they go, and for everything the user reads
	or hears. The owner said on 2026-11-19: "ensure the whole prompt is always displayed no matter how long"."""
	return str(text or "").strip()


_MARKUP = re.compile(r"\*\*|__|`|^\s*#+\s*|^\s*[-*\u2022]\s+", re.MULTILINE)


def plainSpeech(text):
	"""Text as it should be spoken: one flowing line, without Markdown marks or list bullets."""
	lines = []
	for line in str(text or "").splitlines():
		line = " ".join(_MARKUP.sub("", line).split())
		if line:
			# A list item or heading becomes a clause of its own, so items are not run together.
			lines.append(line if line[-1] in ".,:;!?" else line + ",")
	spoken = " ".join(lines)
	return spoken[:-1] + "." if spoken.endswith(",") else spoken


def tokens(text):
	"""A safe guess of how many tokens a text is."""
	return len(text) // 3 + 8


def withThought(schema, chars):
	"""The same schema, with a short reasoning text first. Writing its reasoning down before the answer is how a
	small model without a thinking mode thinks; the schema keeps it short."""
	schema = copy.deepcopy(schema)
	if "anyOf" in schema:
		schema["anyOf"] = [withThought(s, chars) for s in schema["anyOf"]]
		return schema
	properties = {THOUGHT: {"type": "string", "maxLength": chars}}
	properties.update(schema.get("properties", {}))
	schema["properties"] = properties
	schema["required"] = [THOUGHT] + [r for r in schema.get("required", []) if r != THOUGHT]
	return schema


def votedField(schema):
	"""The one field of a form that is voted on: a form with one field whose answers are fixed, or None."""
	properties = (schema or {}).get("properties") or {}
	if "anyOf" in (schema or {}) or len(properties) != 1:
		return None
	name, field = next(iter(properties.items()))
	return name if len(field.get("enum") or ()) >= 2 or field.get("type") == "boolean" else None


def _hashable(value):
	return json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value


class LLM:
	"""Talks to the models of a runtime for one task. votes: how often a choice is asked of a model; None decides
	by the model's size (policy.votes)."""

	votes = None

	def __init__(self, runtime, task):
		self.runtime = runtime
		self.task = task

	def _messages(self, system, user, image):
		content = user
		if image is not None:
			b64 = base64.b64encode(image).decode("ascii")
			content = [
				{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
				{"type": "text", "text": user},
			]
		return [{"role": "system", "content": system}, {"role": "user", "content": content}]

	def _context(self, system, user, image, maxTokens):
		need = tokens(system) + tokens(user) + maxTokens + (_IMAGE_TOKENS if image is not None else 0) + 128
		return runtimeModule.contextFor(need)

	def _loaded(self, role):
		"""Whether the model for a role is in memory and answers without being started first. A runtime that cannot
		say counts as loaded."""
		loaded = getattr(self.runtime, "loaded", None)
		try:
			return True if loaded is None else bool(loaded(role))
		except Exception:
			return True

	def waiting(self, role, thinking=OFF):
		"""What a task waits for while a model is asked, in a sentence, as it is now: the model is starting, thinking
		first, or answering. A large model can take a minute to start and longer to think; this says which."""
		from . import policy  # policy imports this module
		name = policy.roleName(role, policy.isOneModel(self.runtime))
		if not self._loaded(role):
			return f"Starting the {name}."
		if thinking in _THOUGHT_CHARS:
			return f"The {name} is thinking before it answers; thinking is set to {thinking}."
		return f"The {name} is answering."

	def _ask(self, role, messages, maxTokens, options, context, onText=None, raw=True, thinking=OFF):
		self.task.check()
		info = {}
		debuglog.detail("model", f"Asking the {role} model, context {context}, at most {maxTokens} tokens.")
		self.task.now = lambda: self.waiting(role, thinking)
		try:
			answer = self.runtime.chat(
				role, messages, maxTokens, onText=onText, cancel=self.task.cancel, options=options, raw=raw, info=info,
				context=context,
			)
		finally:
			self.task.now = None
		if answer is None:
			debuglog.log("model", f"The question to the {role} model was stopped.")
			raise taskModule.Cancelled()
		if info.get("thinking"):
			self.task.emit(taskModule.THINK, f"{role}: {uncut(info['thinking'])}")
		return answer, info

	def json(self, role, system, user, schema, maxTokens=300, reasoning=OFF, image=None):
		"""Ask for a JSON object matching schema. The engine only lets the model write JSON that fits it. A small
		model is asked a choice among fixed answers more than once, and most of its answers decide (_vote)."""
		field = votedField(schema)
		found = self._json(role, system, user, schema, maxTokens, reasoning, image)
		count = self._votes(role) if field and image is None else 1
		if count > 1 and found.get(field) is not None:
			found = self._vote(role, system, user, schema, maxTokens, reasoning, found, field, count)
		return found

	def _votes(self, role):
		if self.votes is not None:
			return max(1, int(self.votes))
		try:
			from . import policy
			return policy.votes(self.runtime.entry(role))
		except Exception:
			return 1

	def _vote(self, role, system, user, schema, maxTokens, reasoning, first, field, count):
		"""The answer most of count answers gave: the first, greedy one, and the rest written with a little chance
		in them (VOTE_TEMPERATURE, each with a seed of its own). Asking stops as soon as one answer has more than half.
		Among answers given equally often, the first one wins. A fault in a later answer only ends the voting."""
		answers = [first]
		tally = collections.Counter([_hashable(first[field])])
		for number in range(1, count):
			if tally.most_common(1)[0][1] * 2 > count:
				break
			try:
				found = self._json(role, system, user, schema, maxTokens, reasoning, None,
					temperature=VOTE_TEMPERATURE, seed=VOTE_SEED + number, quiet=True)
			except LLMError:
				break
			if found.get(field) is None:
				continue
			answers.append(found)
			tally[_hashable(found[field])] += 1
		best = max(tally.values())
		winner = next(answer for answer in answers if tally[_hashable(answer[field])] == best)
		debuglog.log("model", (
			f"The {role} model answered {len(answers)} times for {field!r}: "
			+ ", ".join(f"{value!r} {times} times" for value, times in tally.most_common())
			+ f". Taken: {winner[field]!r}."))
		if winner is not first:
			self.task.emit(taskModule.THINK, f"{role}: most of its answers chose {winner[field]!r}, not its first answer.")
		return winner

	def _json(self, role, system, user, schema, maxTokens=300, reasoning=OFF, image=None, temperature=0, seed=None,
			quiet=False):
		if reasoning in _THOUGHT_CHARS:
			chars = _THOUGHT_CHARS[reasoning]
			schema = withThought(schema, chars)
			maxTokens += chars // 3
		for attempt in range(2):
			options = {
				"response_format": {"type": "json_schema", "json_schema": {"name": "form", "strict": True, "schema": schema}},
				"temperature": temperature,
			}
			if seed is not None:
				options["seed"] = seed
			messages = self._messages(system, user + "\nAnswer with the JSON form only.", image)
			answer, info = self._ask(
				role, messages, maxTokens, options, self._context(system, user, image, maxTokens),
				thinking=reasoning if reasoning in _THOUGHT_CHARS else OFF)
			try:
				found = json.loads(answer)
				if not isinstance(found, dict):
					raise ValueError("not an object")
			except ValueError:
				debuglog.log("model", (
					f"The {role} model's answer was not a complete form (try {attempt + 1}, it stopped because: "
					f"{info.get('finish')}): {answer!r}"))
				if attempt == 0:
					maxTokens *= 2  # most often it was cut off before the closing brace
					continue
				raise LLMError(f"The {role} model did not give a complete answer.")
			thought = found.pop(THOUGHT, None)
			if thought and not quiet:
				self.task.emit(taskModule.THINK, f"{role}: {thought}")
			return found

	def text(self, role, system, user, maxTokens=300, reasoning=OFF, image=None, temperature=0.2, onText=None,
			code=False):
		"""Ask for plain text. code is for program code: nothing is filtered out of it."""
		options = {"temperature": temperature}
		entry = self.runtime.entry(role)
		thinks = reasoning in _THINK_TOKENS and entry is not None and entry.get("thinking")
		limit = maxTokens
		if thinks:
			options["chat_template_kwargs"] = {"enable_thinking": True}
			limit += _THINK_TOKENS[reasoning]
		messages = self._messages(system, user, image)
		answer, info = self._ask(
			role, messages, limit, options, self._context(system, user, image, limit), onText,
			raw="code" if code else False, thinking=reasoning if thinks else OFF)
		if thinks and not (answer or "").strip():
			# A model with its own thinking mode can think until no tokens are left, and then the answer is empty:
			# measured with Qwen3.5 9B writing an add-on at reasoning High. Asked again without thinking, it answers.
			debuglog.log("model", (
				f"The {role} model thought until it had no tokens left (it stopped because: {info.get('finish')}) "
				"and gave no answer; asking again without thinking."))
			options = {"temperature": temperature}
			answer, _info = self._ask(
				role, messages, maxTokens, options, self._context(system, user, image, maxTokens), onText,
				raw="code" if code else False)
		return answer
