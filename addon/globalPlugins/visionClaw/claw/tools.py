# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools the models can use. A tool is a small form (its fields) and a Python function that
# does the work. The models only ever fill in forms. No NVDA dependencies; the NVDA tools are in nvdatools.py.

import time

from . import debuglog
from .llm import uncut

# How much of a tool's result a model is shown at most, where a model is shown it whole. The result itself is kept
# whole, and what the user is told of it is never cut: a model's own prompt is trimmed where it is made.
RESULT_CHARS = 1500
# The tool every plan ends with. The orchestrator runs it itself.
ANSWER = "answer"
# How a tool's result reaches the user at the end of a task.
VERBATIM, SUMMARIZE = "verbatim", "summarize"


class ToolError(Exception):
	"""A tool could not do what was asked. The message is shown to the model so it can correct the form."""


# What is not a fault of a tool but ends more than its step: the user stopped the request or said no to all of
# it, or the engine is gone. These are passed on to whoever runs the request. By name, because the classes
# live in modules this one must not depend on.
PASSED_ON = frozenset(("Cancelled", "Declined", "EngineError", "LLMError", "ModelMissing"))
PASSED_ON_KINDS = (KeyboardInterrupt, SystemExit)


class Tool:
	"""fields: {name: JSON schema of the field, with a "description"}. All fields are required.
	  A field with "auto" is filled in by code, not by a model, when the step comes from a recipe:
	  auto=True puts in the part of the request the step is for; auto=function puts in function(part).
	fn(task, **fields) returns a text result or raises ToolError.
	looks: the tool only finds things out, so the plan may be rethought after it.
	changes: the tool changes something, so the user is asked first unless they turned that off.
	before: a tool that a plan must use before this one, like find_setting before set_setting.
	title: what the tool is doing, for telling the user the progress.
	tell: VERBATIM if the result is a sentence for the user as it is; SUMMARIZE if a model must put it in words."""

	def __init__(self, name, description, fn, fields=None, looks=False, changes=False, before=None, title=None,
			tell=None):
		self.name = name
		self.description = description
		self.fn = fn
		self.fields = fields or {}
		self.looks = looks
		self.changes = changes
		self.before = before
		self.title = title or description[:1].upper() + description[1:60]
		self.tell = tell or (VERBATIM if changes else SUMMARIZE)

	def autoForm(self, part):
		"""The fields code can fill in for a part of the request."""
		form = {}
		for name, spec in self.fields.items():
			auto = spec.get("auto")
			if auto is True:
				# The user's own words, whole: a tool that reads them must see all of them, however long.
				form[name] = uncut(part)
			elif callable(auto):
				form[name] = auto(part)
		return form

	def schema(self, skip=(), shapes=None):
		"""The form as the engine enforces it. shapes: {field: {"enum": [...]} or {"pattern": ...}}, what a
		field may be according to the results so far (claw/shapes.py); the model can then write nothing else."""
		properties = {}
		for name, spec in self.fields.items():
			if name in skip:
				continue
			properties[name] = {k: v for k, v in spec.items() if k not in ("description", "auto")}
			shape = (shapes or {}).get(name)
			if shape:
				# A list of allowed answers needs no limit on its length, and some engines refuse both together.
				properties[name].pop("maxLength", None)
				properties[name].update(shape)
		return {"type": "object", "properties": properties, "required": list(properties)}

	def fieldText(self, name, shape=None):
		"""One field as shown to a model: its name, what it is, and the allowed answers if there are only some."""
		spec = self.fields[name]
		choices = (shape or {}).get("enum") or spec.get("enum")
		options = f" One of: {', '.join(str(choice) for choice in choices)}." if choices else ""
		if (shape or {}).get("pattern"):
			options = " A number only, with + or - in front to change it by that much."
		return f"{name}: {spec.get('description', '')}{options}"

	def formText(self, skip=(), shapes=None):
		"""The tool as shown to a model that is about to fill it in."""
		lines = [f"Tool: {self.name} - {self.description}"]
		for name in self.fields:
			if name in skip:
				continue
			lines.append("  " + self.fieldText(name, (shapes or {}).get(name)))
		return "\n".join(lines)


class Registry:
	def __init__(self):
		self._tools = {}

	def add(self, tool):
		self._tools[tool.name] = tool
		return tool

	def get(self, name):
		return self._tools.get(name)

	def names(self):
		return list(self._tools)

	def has(self, names):
		return all(name in self._tools for name in names)

	def listText(self):
		"""One line per tool, for the planning prompt."""
		return "\n".join(f"- {t.name}: {t.description}" for t in self._tools.values())

	def call(self, task, name, form):
		"""Run a tool. Returns (worked, result text)."""
		tool = self._tools.get(name)
		if tool is None:
			debuglog.log("tool", f"{name}: there is no such tool. Form: {form}")
			return False, f"There is no tool called {name}."
		missing = [f for f in tool.fields if f not in form]
		if missing:
			debuglog.log("tool", f"{name}: the form is missing {missing}. Form: {form}")
			return False, f"The form is missing: {', '.join(missing)}."
		debuglog.log("tool", f"{name} starts. Form: {form}")
		started = time.monotonic()
		try:
			result = tool.fn(task, **{f: form[f] for f in tool.fields})
		except ToolError as e:
			debuglog.log("tool", f"{name} could not do it after {time.monotonic() - started:.2f} s: {e}")
			return False, uncut(str(e))
		except Exception as e:
			if type(e).__name__ in PASSED_ON or isinstance(e, PASSED_ON_KINDS):
				debuglog.log("tool", f"{name} ended after {time.monotonic() - started:.2f} s with {type(e).__name__}: {e}")
				raise
			# A fault inside a tool is VisionClaw's own mistake. It ends this step, not the whole request: the
			# other parts of the request can still be done. Where it happened is written to the log.
			debuglog.error("tool", f"{name} failed after {time.monotonic() - started:.2f} s. Form: {form}", e)
			return False, (
				f"This did not work because of a fault inside VisionClaw ({type(e).__name__}: {uncut(str(e))}). "
				"Where it happened is written in VisionClaw's log.")
		debuglog.log("tool", f"{name} worked after {time.monotonic() - started:.2f} s.")
		debuglog.detail("tool", f"{name} result:\n{result}")
		# The whole result: what the user is told of it is never cut, and a model's prompt trims it where it is made.
		return True, uncut(result if result else "Done.")
