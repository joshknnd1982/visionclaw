# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - asking a model for one small thing: a JSON form that must match a schema, or a short text.
# The context size is chosen for each request from how long it is, and the reasoning level decides how much
# the model may think first. No NVDA dependencies.

import base64
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


class LLMError(EngineError):
	"""The model did not give a usable answer."""


def clip(text, chars):
	"""Cut text to a length a small model can take in, saying that it was cut."""
	text = str(text or "").strip()
	return text if len(text) <= chars else text[:chars].rstrip() + " ...[cut]"


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


class LLM:
	"""Talks to the models of a runtime for one task."""

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

	def _ask(self, role, messages, maxTokens, options, context, onText=None, raw=True):
		self.task.check()
		info = {}
		debuglog.detail("model", f"Asking the {role} model, context {context}, at most {maxTokens} tokens.")
		answer = self.runtime.chat(
			role, messages, maxTokens, onText=onText, cancel=self.task.cancel, options=options, raw=raw, info=info,
			context=context,
		)
		if answer is None:
			debuglog.log("model", f"The question to the {role} model was stopped.")
			raise taskModule.Cancelled()
		if info.get("thinking"):
			self.task.emit(taskModule.THINK, f"{role}: {clip(info['thinking'], 600)}")
		return answer, info

	def json(self, role, system, user, schema, maxTokens=300, reasoning=OFF, image=None):
		"""Ask for a JSON object matching schema. The engine only lets the model write JSON that fits it."""
		if reasoning in _THOUGHT_CHARS:
			chars = _THOUGHT_CHARS[reasoning]
			schema = withThought(schema, chars)
			maxTokens += chars // 3
		for attempt in range(2):
			options = {
				"response_format": {"type": "json_schema", "json_schema": {"name": "form", "strict": True, "schema": schema}},
				"temperature": 0,
			}
			messages = self._messages(system, user + "\nAnswer with the JSON form only.", image)
			answer, info = self._ask(role, messages, maxTokens, options, self._context(system, user, image, maxTokens))
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
			if thought:
				self.task.emit(taskModule.THINK, f"{role}: {thought}")
			return found

	def text(self, role, system, user, maxTokens=300, reasoning=OFF, image=None, temperature=0.2, onText=None,
			code=False):
		"""Ask for plain text. code is for program code: nothing is filtered out of it."""
		options = {"temperature": temperature}
		entry = self.runtime.entry(role)
		if reasoning in _THINK_TOKENS and entry is not None and entry.get("thinking"):
			options["chat_template_kwargs"] = {"enable_thinking": True}
			maxTokens += _THINK_TOKENS[reasoning]
		messages = self._messages(system, user, image)
		answer, _info = self._ask(
			role, messages, maxTokens, options, self._context(system, user, image, maxTokens), onText,
			raw="code" if code else False)
		return answer
