# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools the models can use. A tool is a small form (its fields) and a Python function that
# does the work. The models only ever fill in forms. No NVDA dependencies; the NVDA tools are in nvdatools.py.

from .llm import clip

RESULT_CHARS = 1500
# The tool every plan ends with. The orchestrator runs it itself.
ANSWER = "answer"
# How a tool's result reaches the user at the end of a task.
VERBATIM, SUMMARIZE = "verbatim", "summarize"


class ToolError(Exception):
	"""A tool could not do what was asked. The message is shown to the model so it can correct the form."""


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
				form[name] = clip(part, spec.get("maxLength", 200)).replace(" ...[cut]", "")
			elif callable(auto):
				form[name] = auto(part)
		return form

	def schema(self, skip=()):
		properties = {
			name: {k: v for k, v in spec.items() if k not in ("description", "auto")}
			for name, spec in self.fields.items() if name not in skip
		}
		return {"type": "object", "properties": properties, "required": list(properties)}

	def formText(self, skip=()):
		"""The tool as shown to a model that is about to fill it in."""
		lines = [f"Tool: {self.name} - {self.description}"]
		for name, spec in self.fields.items():
			if name in skip:
				continue
			options = f" One of: {', '.join(spec['enum'])}." if "enum" in spec else ""
			lines.append(f"  {name}: {spec.get('description', '')}{options}")
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
			return False, f"There is no tool called {name}."
		missing = [f for f in tool.fields if f not in form]
		if missing:
			return False, f"The form is missing: {', '.join(missing)}."
		try:
			result = tool.fn(task, **{f: form[f] for f in tool.fields})
		except ToolError as e:
			return False, clip(str(e), RESULT_CHARS)
		return True, clip(result if result else "Done.", RESULT_CHARS)
