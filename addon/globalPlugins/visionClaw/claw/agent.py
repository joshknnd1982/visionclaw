# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - carries out one step of a plan. A step is one tool. What code can fill in of the tool's form,
# it fills in; the model fills in the rest; Python runs the tool. If the tool reports an error, the model sees
# the error and corrects the form. If that does not help, the other model is asked for a hint.
# No NVDA dependencies.

import json

from . import policy
from . import task as taskModule
from .llm import LLMError, clip

_FORM_SYSTEM = (
	"You are VisionClaw, an assistant inside the NVDA screen reader, helping a blind person. "
	"You fill in one small tool form at a time.\n"
	"Rules: Use only what the user asked for and the results so far. Never make up names, ids or numbers: "
	"copy them exactly as they appear in the results. Fill in every field, as briefly as possible."
)
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


def resultsText(steps, upTo):
	"""What the finished steps found, shortened, for the next step's prompt."""
	lines = []
	for i, step in enumerate(steps[:upTo], 1):
		if step.status == taskModule.STEP_DONE:
			lines.append(f"{i}. {step.title}: {clip(step.result, RESULT_CHARS)}")
		elif step.status in (taskModule.STEP_FAILED, taskModule.SKIPPED):
			lines.append(f"{i}. {step.title}: was not done.")
	return "\n".join(lines) or "Nothing yet."


def _asked(request, step):
	"""What this step is for: its own part of the request if it has one, else the whole request."""
	return step.part or request


def _formPrompt(request, steps, index, tool, tries, hint, skip):
	step = steps[index]
	parts = [
		f"The user asked: \"{clip(_asked(request, step), 600)}\"",
		f"Results so far:\n{resultsText(steps, index)}",
		f"Now do this step: {step.title}." + (f" {step.detail}" if step.detail and step.detail != step.part else ""),
		tool.formText(skip),
	]
	for form, error in tries[-2:]:
		parts.append(f"This form was tried: {json.dumps(form)}\nIt failed: {clip(error, 400)}\nCorrect the form.")
	if hint:
		parts.append(f"Hint from the other model: {hint}")
	return "\n".join(parts)


def askHint(llm, role, request, steps, index, tool, tries):
	"""The other model looks at a stuck step and suggests how to fill in the form."""
	step = steps[index]
	user = (
		f"The user asked: \"{clip(_asked(request, step), 500)}\"\nResults so far:\n{resultsText(steps, index)}\n"
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
	while attempt < attempts:
		task.check()
		attempt += 1
		skip = tuple(auto) if not tries else ()  # after a failure the model fills in every field itself
		form = {name: auto[name] for name in skip}
		if any(name not in skip for name in tool.fields):
			try:
				form.update(llm.json(
					lead, _FORM_SYSTEM, _formPrompt(request, steps, index, tool, tries, hint, skip), tool.schema(skip),
					maxTokens=params.formTokens, reasoning=params.reasoning,
				))
			except LLMError as e:
				tries.append(({}, str(e)))
				continue
		task.emit(taskModule.DETAIL, f"{tool.name} {json.dumps(form)}" if form else tool.name)
		task.check()
		worked, result = registry.call(task, tool.name, form)
		task.emit(taskModule.DETAIL, ("Result: " if worked else "Problem: ") + clip(result, 300))
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
			task.emit(taskModule.TALK, f"The {policy.ROLE_NAMES[lead]} is stuck and asks the {policy.ROLE_NAMES[other]}.")
			hint = askHint(llm, other, request, steps, index, tool, tries)
			if hint:
				task.emit(taskModule.TALK, f"Hint from the {policy.ROLE_NAMES[other]}: {hint}")
				attempts += 1
	step.status = taskModule.STEP_FAILED
	step.result = tries[-1][1] if tries else "The step could not be done."
	return False
