# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the two models must agree before anything runs.
# For each part of the request, both models choose, each on its own, how to handle it. If they choose the
# same, they agree. If not, each is told the other's choice and chooses again. If they still differ, the user
# is given both and decides. A plan that a model has to write itself is reviewed by the other model, corrected
# once if it objects, and put to the user if they still do not agree.
# When one model does both jobs (params.oneModel) there are not two that could agree, and nothing is called an
# agreement: the model chooses once, because asked the same question again it gives the same answer; its
# choice is checked against the user's own words by plain code, and where the two differ after a second look
# the user decides; and it checks a plan it wrote itself with the reviewer's question, which is a different
# one. No NVDA dependencies.

from . import planner, policy
from . import task as taskModule
from .llm import LLMError, clip

AGREED, REVISED, USER_CHOSE = "agreed", "revised", "user"
_RANK = {AGREED: 0, REVISED: 1, USER_CHOSE: 2}

_REVIEW_SCHEMA = {
	"type": "object",
	"properties": {"agree": {"type": "boolean"}, "problem": {"type": "string", "maxLength": 240}},
	"required": ["agree", "problem"],
}
_REVIEW_SYSTEM = (
	"You review a plan made by another model, for VisionClaw, an assistant inside the NVDA screen reader for a "
	"blind person. The plan will be run step by step with the tools listed. Finding something before changing "
	"it is correct and expected.\n"
	"Say agree=true if the steps would do what the user asked. Say agree=false only for a real problem: "
	"a wrong tool for what was asked, a part of the request with no step, or a step that does something the "
	"user did not ask for. If you disagree, say the problem in one sentence. If you agree, problem is an empty text."
)


class Declined(Exception):
	"""The user chose not to go ahead."""


def review(llm, role, request, steps, registry, params):
	"""One model's verdict on a plan: (agrees, problem)."""
	used = {s.tool for s in steps}
	tools = "\n".join(f"- {name}: {registry.get(name).description}" for name in registry.names() if name in used)
	user = (
		f"The user asked: \"{clip(request, 600)}\"\nTools used in the plan:\n{tools}\n"
		f"Plan:\n{planner.detailText(steps)}\nDo you agree with this plan?"
	)
	found = llm.json(role, _REVIEW_SYSTEM, user, _REVIEW_SCHEMA, maxTokens=110, reasoning=params.reasoning)
	problem = " ".join(str(found.get("problem") or "").split())
	# An objection without a reason cannot be acted on, so it does not count.
	return bool(found.get("agree")) or not problem, problem


def _onRecipe(llm, task, part, context, registry, askUser, lead, other, single=False):
	"""Both models choose how to handle one part. Returns (recipe, how)."""
	leadName, otherName = policy.ROLE_NAMES[lead], policy.ROLE_NAMES[other]
	mine = planner.classify(llm, lead, part, context, registry)
	task.check()
	if single:
		# One model does both jobs. Its second answer to the same question would be the same as its first, so
		# that question is not put again. Its choice is checked against the user's own words instead, by plain
		# code (planner.hint). Where the words point to another choice, the model is told which and looks
		# again; if it still chooses differently, the user decides, as when two models differ. With the real
		# 9B model this happened in 2 of 55 parts, and both times the words were right and the model was not.
		task.emit(taskModule.TALK, f"\"{part}\": the model chose to {planner.label(mine)}.")
		guess = planner.hint(part)
		if guess == mine or guess not in planner.available(registry):
			return mine, AGREED
		task.check()
		note = (
			f"The user's words point to: {guess} ({planner.label(guess)}). You chose {mine}. Read the request again, "
			"word by word, and choose the one that fits what the user asked.")
		again = planner.classify(llm, lead, part, context, registry, note)
		if again == guess:
			task.emit(taskModule.TALK, f"After checking against your words, the model chose to {planner.label(again)}.")
			return again, REVISED
		task.emit(taskModule.TALK, (
			f"Your words could also mean: {planner.label(guess)}. The model looked again and still chose to "
			f"{planner.label(again)}."))
		ways = [guess, again]
		choices = [_sentence(planner.label(way)) for way in ways] + ["Cancel. I will ask in a different way."]
		question = f"VisionClaw is not sure what you mean by \"{clip(part, 200)}\". What should it do?"
		task.setState(taskModule.WAITING, "Not sure what you mean. Waiting for your choice.")
		picked = askUser(question, choices)
		task.check()
		if picked not in (0, 1):
			raise Declined()
		task.emit(taskModule.TALK, f"You chose: {choices[picked]}")
		return ways[picked], USER_CHOSE
	theirs = planner.classify(llm, other, part, context, registry)
	if mine == theirs:
		task.emit(taskModule.TALK, f"\"{part}\": both models chose to {planner.label(mine)}.")
		return mine, AGREED
	task.emit(taskModule.TALK, (
		f"\"{part}\": the {leadName} chose to {planner.label(mine)}; the {otherName} chose to {planner.label(theirs)}. "
		"They look again."
	))
	# One more round: each model is told the other's choice and chooses again.
	task.check()
	note = "Another model chose: {choice} ({text}). If that fits better than your choice, choose it."
	mineAgain = planner.classify(
		llm, lead, part, context, registry, note.format(choice=theirs, text=planner.label(theirs)))
	theirsAgain = planner.classify(
		llm, other, part, context, registry, note.format(choice=mine, text=planner.label(mine)))
	if mineAgain == theirsAgain:
		task.emit(taskModule.TALK, f"After looking again, both models chose to {planner.label(mineAgain)}.")
		return mineAgain, REVISED
	# Each swapping to the other's first choice is still a disagreement, so the first choices stand.
	task.emit(taskModule.TALK, "The models still do not agree.")
	choices = [
		f"As the {leadName} suggests: {planner.label(mine)}",
		f"As the {otherName} suggests: {planner.label(theirs)}",
		"Cancel. I will ask in a different way.",
	]
	question = f"The two models do not agree on how to handle this: \"{clip(part, 200)}\". What should VisionClaw do?"
	task.setState(taskModule.WAITING, "The models do not agree. Waiting for your choice.")
	picked = askUser(question, choices)
	task.check()
	if picked not in (0, 1):
		raise Declined()
	task.emit(taskModule.TALK, f"You chose: {choices[picked]}")
	return (mine, theirs)[picked], USER_CHOSE


def _onOwnPlan(llm, task, part, context, registry, params, askUser, lead):
	"""A part that fits no recipe, with one model for both jobs: the model writes a plan and checks it itself,
	with the reviewer's question. Nothing here is called an agreement. Returns (steps, how)."""
	steps = planner.freeSteps(llm, lead, part, context, registry, params)
	task.emit(taskModule.TALK, f"Plan for \"{part}\":\n{planner.planText(steps)}")
	fine, problem = review(llm, lead, part, steps, registry, params)
	if fine:
		task.emit(taskModule.TALK, "The model checked its plan and found no problem.")
		return steps, AGREED
	task.emit(taskModule.TALK, f"The model checked its plan and found a problem: {problem}")
	task.check()
	note = (
		f"An earlier plan was:\n{planner.detailText(steps)}\n"
		f"A reviewer found this problem with it: {clip(problem, 300)}\nWrite a better plan that fixes it."
	)
	revised = planner.freeSteps(llm, lead, part, context, registry, params, note)
	task.emit(taskModule.TALK, f"New plan:\n{planner.planText(revised)}")
	fine, problemAgain = review(llm, lead, part, revised, registry, params)
	if fine:
		task.emit(taskModule.TALK, "The model checked the new plan and found no problem.")
		return revised, REVISED
	task.emit(taskModule.TALK, f"The model still finds a problem: {problemAgain}")
	task.check()
	choices = ["Use the new plan: " + _oneLine(revised)]
	plans = [revised]
	if planner.planText(steps) != planner.planText(revised):
		choices.append("Use the first plan: " + _oneLine(steps))
		plans.append(steps)
	choices.append("Cancel. I will ask in a different way.")
	question = (
		f"The model is not sure how to do this: \"{clip(part, 200)}\". Its concern: "
		f"{problemAgain or problem} Which plan should be used?"
	)
	task.setState(taskModule.WAITING, "The model is not sure of its plan. Waiting for your choice.")
	picked = askUser(question, choices)
	task.check()
	if picked is None or picked >= len(plans):
		raise Declined()
	task.emit(taskModule.TALK, f"You chose: {choices[picked]}")
	return plans[picked], USER_CHOSE


def _onFreePlan(llm, task, part, context, registry, params, askUser, lead, other):
	"""A part that fits no recipe: the lead writes a plan, the other reviews it. Returns (steps, how)."""
	if getattr(params, "oneModel", False):
		return _onOwnPlan(llm, task, part, context, registry, params, askUser, lead)
	leadName, otherName = policy.ROLE_NAMES[lead], policy.ROLE_NAMES[other]
	steps = planner.freeSteps(llm, lead, part, context, registry, params)
	task.emit(taskModule.TALK, f"Plan from the {leadName} for \"{part}\":\n{planner.planText(steps)}")
	agrees, problem = review(llm, other, part, steps, registry, params)
	if agrees:
		task.emit(taskModule.TALK, f"The {otherName} agrees.")
		return steps, AGREED
	task.emit(taskModule.TALK, f"The {otherName} disagrees: {problem}")
	task.check()
	note = (
		f"An earlier plan was:\n{planner.detailText(steps)}\n"
		f"A reviewer found this problem with it: {clip(problem, 300)}\nWrite a better plan that fixes it."
	)
	revised = planner.freeSteps(llm, lead, part, context, registry, params, note)
	task.emit(taskModule.TALK, f"New plan from the {leadName}:\n{planner.planText(revised)}")
	agrees, problemAgain = review(llm, other, part, revised, registry, params)
	if agrees:
		task.emit(taskModule.TALK, f"The {otherName} agrees with the new plan.")
		return revised, REVISED
	task.emit(taskModule.TALK, f"The {otherName} still disagrees: {problemAgain}")
	task.check()
	try:
		note = f"Another model's plan had this problem: {clip(problemAgain, 300)}\nWrite your own plan."
		theirs = planner.freeSteps(llm, other, part, context, registry, params, note)
	except LLMError:
		theirs = []
	choices = [f"Use the {leadName}'s plan: " + _oneLine(revised)]
	plans = [revised]
	if theirs and planner.planText(theirs) != planner.planText(revised):
		choices.append(f"Use the {otherName}'s plan: " + _oneLine(theirs))
		plans.append(theirs)
	choices.append("Cancel. I will ask in a different way.")
	question = (
		f"The two models do not agree on how to do this: \"{clip(part, 200)}\". The {otherName}'s concern: "
		f"{problemAgain or problem} Which plan should be used?"
	)
	task.setState(taskModule.WAITING, "The models do not agree. Waiting for your choice.")
	picked = askUser(question, choices)
	task.check()
	if picked is None or picked >= len(plans):
		raise Declined()
	task.emit(taskModule.TALK, f"You chose: {choices[picked]}")
	return plans[picked], USER_CHOSE


def agree(llm, task, request, context, registry, params, askUser, lead=policy.LEAD, other=policy.OTHER):
	"""Break the request into steps that both models agree on, or that the user picked.
	askUser(question, choices) returns the index of the chosen choice, or None.
	Returns (steps, how, recipes): how is AGREED, REVISED or USER_CHOSE; recipes has one name per part.
	With one model for both jobs (params.oneModel), AGREED means that the model chose and found no problem.
	Raises Declined if the user cancels."""
	single = bool(getattr(params, "oneModel", False))
	task.setState(taskModule.PLANNING, "Breaking your request into small steps.")
	parts = planner.split(llm, lead, request)
	if len(parts) > 1:
		task.emit(taskModule.TALK, "The request has these parts: " + "; ".join(parts))
	task.setState(taskModule.AGREEING, (
		"The model is choosing what to do." if single else "The two models are agreeing on what to do."))
	steps, recipes, how = [], [], AGREED
	for part in parts:
		task.check()
		recipe, partHow = _onRecipe(llm, task, part, context, registry, askUser, lead, other, single)
		if recipe == planner.OTHER:
			partSteps, planHow = _onFreePlan(llm, task, part, context, registry, params, askUser, lead, other)
			partHow = max(partHow, planHow, key=_RANK.get)
		else:
			partSteps = planner.recipeSteps(recipe, part, registry)
		steps += partSteps
		recipes.append(recipe)
		how = max(how, partHow, key=_RANK.get)
	steps.append(planner.answerStep())
	task.emit(taskModule.TALK, ("The steps:\n" if single else "The agreed steps:\n") + planner.planText(steps))
	return steps, how, recipes


def _sentence(text):
	"""A recipe's few words as a choice the user can pick: with a capital letter and a full stop."""
	return text[:1].upper() + text[1:] + "."


def _oneLine(steps):
	return "; ".join(s.title for s in steps if s.tool != "answer") or "answer directly"
