# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - carries out one step of a plan. A step is one tool. What code can fill in of the tool's form,
# it fills in; the model fills in the rest; Python runs the tool. If the tool reports an error, the model sees
# the error and corrects the form. If that does not help, the other model is asked for a hint.
# What the steps before found is given from the request's work sheet (claw/worksheet.py): only what the steps of
# this step's own part found, so that a small model reads a few lines about its own piece of the work.
# No NVDA dependencies.

import json

from . import debuglog, policy, prompts, shapes
from . import task as taskModule
from .llm import LLMError, clip, uncut

_FORM_SYSTEM = (
	prompts.IDENTITY + " You fill in one small tool form at a time.\n"
	"Rules: Use only what the user asked for and the results so far. Never make up names, ids or numbers: "
	"copy them exactly as they appear in the results. Fill in every field, as briefly as possible."
)
_FIELD_SYSTEM = (
	prompts.IDENTITY + " You answer one small question at a time, with one value.\n"
	"Rules: Use only what the user asked for and the results so far. Copy names, ids and numbers exactly as they "
	"appear in the results. Give the value itself, never the question or its description."
)
# In a form filled in one field at a time, an answer needs no more room than this.
FIELD_TOKENS = 90
_HINT_SCHEMA = {
	"type": "object",
	"properties": {"hint": {"type": "string", "maxLength": 260}},
	"required": ["hint"],
}
_HINT_SYSTEM = (
	"Another model is stuck on one step of a task inside the NVDA screen reader. "
	"Read what it tried and the error it got. Give one short, concrete hint on how to fill in the tool form "
	"so the step works. Use only names and ids that appear in the results."
)
RESULT_CHARS = 500


class _Filled(Exception):
	"""Every field of a form was filled in from the user's own words."""


def resultsText(steps, upTo):
	"""What the finished steps found, shortened, for the next step's prompt."""
	lines = []
	for i, step in enumerate(steps[:upTo], 1):
		if step.status == taskModule.STEP_DONE:
			lines.append(f"{i}. {step.title}: {clip(step.result, RESULT_CHARS)}")
		elif step.status in (taskModule.STEP_FAILED, taskModule.SKIPPED):
			lines.append(f"{i}. {step.title}: was not done.")
	return "\n".join(lines) or "Nothing yet."


def found(task, steps, index):
	"""What step index is given of what was found so far: from the task's work sheet when it has one, else every
	step before it. A fault in the sheet never ends the step."""
	sheet = getattr(task, "sheet", None)
	if sheet is not None:
		try:
			return sheet.feed(steps, index)
		except Exception as e:
			debuglog.error("worksheet", "What the step is given could not be taken from the work sheet", e)
	return resultsText(steps, index)


def _asked(request, step):
	"""What this step is for: its own part of the request if it has one, else the whole request."""
	return step.part or request


def _fieldPrompt(request, steps, index, tool, name, shape, form, tries, hint, given=None):
	"""The prompt for one field of a form: as little as a very small model needs for one answer."""
	step = steps[index]
	parts = [
		f"The user asked: \"{uncut(_asked(request, step))}\"",
		f"Results so far:\n{given if given is not None else resultsText(steps, index)}",
		f"Step: {step.title}.",
	]
	done = [f"{field} = {value}" for field, value in form.items() if not tool.fields[field].get("auto")]
	if done:
		parts.append("Already filled in: " + "; ".join(done))
	for old, error in tries[-1:]:
		if name in old:
			parts.append(f"Before, {name} = {json.dumps(old[name])} was tried. It failed: {clip(error, 300)}")
	if hint:
		parts.append(f"Hint from the other model: {hint}")
	parts.append("Fill in one thing. " + tool.fieldText(name, shape))
	return "\n".join(parts)


def fillOneByOne(llm, task, lead, request, steps, index, tool, skip, form, tries, hint, params, given=None):
	"""Fill in a form one field at a time: one small question, one value, and what the value may be is
	narrowed by the fields already filled in. For models too small to fill in a whole form at once."""
	if given is None:
		given = found(task, steps, index)
	for name, spec in tool.fields.items():
		if name in skip:
			continue
		task.check()
		if not tries:
			# What the user's own words already say is not asked of a model.
			known = shapes.said(tool.name, name, _asked(request, steps[index]), steps, index, form)
			if known is not None:
				form[name] = known
				continue
		shape = shapes.shapes(tool.name, [name], steps, index, form).get(name, {})
		schema = tool.schema([other for other in tool.fields if other != name], {name: shape})
		prompt = _fieldPrompt(request, steps, index, tool, name, shape, form, tries, hint, given)
		value = None
		for _again in range(2):
			value = llm.json(
				lead, _FIELD_SYSTEM, prompt, schema, maxTokens=min(params.formTokens, FIELD_TOKENS), reasoning=params.reasoning,
			).get(name)
			free = "enum" not in spec and "enum" not in shape and isinstance(value, str)
			if not free or not shapes.echoes(value, tool.name, name, spec.get("description", "")):
				break
			# Said in general words: a small model copies an example as if it were the answer.
			prompt += "\nThat answer repeated the question. Give the value itself."
		else:
			# It repeated the question twice. The user's own words are at least true, and the tools read them.
			value = uncut(_asked(request, steps[index]))
		form[name] = value
	return form


def _formPrompt(request, steps, index, tool, tries, hint, skip, narrowed=None, given=None):
	step = steps[index]
	parts = [
		f"The user asked: \"{uncut(_asked(request, step))}\"",
		f"Results so far:\n{given if given is not None else resultsText(steps, index)}",
		f"Now do this step: {step.title}." + (f" {step.detail}" if step.detail and step.detail != step.part else ""),
		tool.formText(skip, narrowed),
	]
	# What a chosen skill says about this kind of step. Not for the very smallest models, which are asked one
	# field at a time and would copy it into the field.
	if getattr(step, "guide", ""):
		parts.insert(3, step.guide)
	for form, error in tries[-2:]:
		parts.append(f"This form was tried: {json.dumps(form)}\nIt failed: {clip(error, 400)}\nCorrect the form.")
	if hint:
		parts.append(f"Hint from the other model: {hint}")
	return "\n".join(parts)


def askHint(llm, role, request, steps, index, tool, tries, given=None):
	"""The other model looks at a stuck step and suggests how to fill in the form."""
	step = steps[index]
	given = given if given is not None else resultsText(steps, index)
	user = (
		f"The user asked: \"{uncut(_asked(request, step))}\"\nResults so far:\n{given}\n"
		f"Stuck step: {step.title}.\n{tool.formText()}\n"
		+ "\n".join(f"Tried: {json.dumps(form)} -> {clip(error, 300)}" for form, error in tries[-2:])
	)
	try:
		return " ".join(str(llm.json(role, _HINT_SYSTEM, user, _HINT_SCHEMA, maxTokens=120).get("hint") or "").split())
	except LLMError:
		return ""


def runStep(llm, task, registry, request, steps, index, params, lead=policy.LEAD, other=policy.OTHER):
	"""Carry out steps[index]. Returns True if it worked; the step's status and result are set."""
	step = steps[index]
	tool = registry.get(step.tool)
	step.status = taskModule.RUNNING
	# In a recipe, code fills in what it can from the user's own words. That is tried first.
	auto = tool.autoForm(step.part) if step.recipe and step.part else {}
	tries = []
	hint = ""
	asked = False
	attempts = 1 + params.retries
	attempt = 0
	# What the steps before found, for this step: taken from the work sheet once, since it does not change while
	# this step is tried again.
	given = found(task, steps, index)
	while attempt < attempts:
		task.check()
		attempt += 1
		skip = tuple(auto) if not tries else ()  # after a failure the model fills in every field itself
		if params.oneByOne and tries:
			# A very small model never rewrites the user's own words; it corrects the other fields.
			skip = tuple(name for name in auto if name == "asked")
		form = {name: auto[name] for name in skip}
		if any(name not in skip for name in tool.fields):
			try:
				if params.oneByOne:
					fillOneByOne(llm, task, lead, request, steps, index, tool, skip, form, tries, hint, params, given)
				else:
					if not tries:
						# What the user's own words already say is not asked of a model.
						for name in tool.fields:
							known = None if name in skip else shapes.said(tool.name, name, _asked(request, step), steps, index, form)
							if known is not None:
								form[name] = known
								skip += (name,)
					if all(name in skip for name in tool.fields):
						raise _Filled()
					# What the results so far allow for a field is all the model can write there.
					narrowed = shapes.shapes(tool.name, [name for name in tool.fields if name not in skip], steps, index, form)
					form.update(llm.json(
						lead, _FORM_SYSTEM, _formPrompt(request, steps, index, tool, tries, hint, skip, narrowed, given),
						tool.schema(skip, narrowed), maxTokens=params.formTokens, reasoning=params.reasoning,
					))
			except _Filled:
				pass  # code filled in every field; no model was needed
			except LLMError as e:
				tries.append(({}, str(e)))
				continue
		task.emit(taskModule.DETAIL, f"{tool.name} {json.dumps(form)}" if form else tool.name)
		task.check()
		worked, result = registry.call(task, tool.name, form)
		task.emit(taskModule.DETAIL, ("Result: " if worked else "Problem: ") + uncut(result))
		if worked:
			step.status, step.result = taskModule.STEP_DONE, result
			# A form that was corrected is worth remembering, but not for a tool that only searches: that
			# another search found something does not make it the right thing, and such a lesson would steer
			# later requests to the wrong place.
			if tries and tries[-1][0] and not tool.looks:
				step.lesson = (
					f"Tool {tool.name}: this form failed: {json.dumps(tries[-1][0])} ({clip(tries[-1][1], 120)}). "
					f"This form worked: {json.dumps(form)}."
				)
			return True
		# The same form again would fail again, and a tool without fields cannot be corrected.
		repeated = any(form == old for old, _e in tries)
		tries.append((form, result))
		if repeated or not tool.fields:
			attempt = attempts
		# Out of tries: ask the other model for a hint, once, and try one more time with it.
		if attempt >= attempts and not asked and tool.fields:
			asked = True
			# With one model for both jobs the hint is the same model's, asked in another way; it is not
			# called another model's.
			one = getattr(params, "oneModel", False)
			task.emit(taskModule.TALK, (
				"The model is stuck and looks at the step in another way." if one
				else f"The {policy.ROLE_NAMES[lead]} is stuck and asks the {policy.ROLE_NAMES[other]}."))
			hint = askHint(llm, other, request, steps, index, tool, tries, given)
			if hint:
				task.emit(taskModule.TALK, (
					f"What the model came up with: {hint}" if one else f"Hint from the {policy.ROLE_NAMES[other]}: {hint}"))
				attempts += 1
	step.status = taskModule.STEP_FAILED
	step.result = tries[-1][1] if tries else "The step could not be done."
	return False
