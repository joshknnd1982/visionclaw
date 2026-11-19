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

from . import computer, debuglog, planner, planning, policy, router
from . import task as taskModule
from .llm import LLMError, clip, uncut

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
		f"The user asked: \"{uncut(request)}\"\nTools used in the plan:\n{tools}\n"
		f"Plan:\n{planner.detailText(steps)}\nDo you agree with this plan?"
	)
	found = llm.json(role, _REVIEW_SYSTEM, user, _REVIEW_SCHEMA, maxTokens=110, reasoning=params.reasoning)
	problem = " ".join(str(found.get("problem") or "").split())
	# An objection without a reason cannot be acted on, so it does not count.
	return bool(found.get("agree")) or not problem, problem


def _brief(task, part, registry):
	"""(what the model that chooses is told besides the request, the recipes it is offered whatever the router
	says), from claw/planning.py. ("", ()) when nothing helps or something went wrong."""
	try:
		available = planner.available(registry)
		brief, before = planning.brief(part, available, getattr(task, "plans", None), planner.label)
		also = planning.skillJobs(getattr(task, "skills", None), available)
		if before and before not in also:
			also.append(before)
		if brief:
			task.emit(taskModule.DETAIL, "Also told to the model: " + brief)
		return brief, tuple(also)
	except Exception as e:
		debuglog.error("planning", "The brief for the model could not be made", e)
		return "", ()


def _onRecipe(llm, task, part, context, registry, askUser, lead, other, single=False, before=None):
	"""Both models choose how to handle one part. Returns (recipe, how). before: the recipe of the part before."""
	leadName, otherName = policy.ROLE_NAMES[lead], policy.ROLE_NAMES[other]
	facts = getattr(task, "facts", None)
	# Where the words can hardly mean anything else, no model is asked.
	sure = planner.decided(part, registry, before)
	# Where Windows' own shell is in front, nothing there has a Start button or a taskbar of its own: words that
	# name one mean that of Windows. Measured with Qwen3.5 9B on 2026-11-18: for "click the start button." the
	# model chose the part of Windows and the words' plain hint said click, so the user had to choose.
	if sure is None and (facts or {}).get(router.SHELL) and "windows_part" in planner.available(registry) \
			and computer.windowsPart(part, loose=True) is not None:
		sure = "windows_part"
	if sure is not None:
		task.emit(taskModule.TALK, f"\"{part}\": your words say it: {planner.label(sure)}.")
		return sure, AGREED
	# What plain code found that helps the choice (claw/planning.py): planning notes the words call up, what worked
	# before for a request like it, and the jobs of the skills that fit. It only helps: a fault here is no fault.
	brief, also = _brief(task, part, registry)
	told = router.offeredText(len(planner.offered(part, registry, facts, before, also)), len(planner.available(registry)))
	if told:
		task.emit(taskModule.DETAIL, told)
	mine = planner.classify(llm, lead, part, context, registry, before=before, facts=facts, brief=brief, also=also)
	task.check()
	if single:
		# One model does both jobs. Its second answer to the same question would be the same as its first, so
		# that question is not put again. Its choice is checked against the user's own words instead, by plain
		# code (planner.hint). Where the words point to another choice, the model is told which and looks
		# again; if it still chooses differently, the user decides, as when two models differ. With the real
		# 9B model this happened in 2 of 55 parts, and both times the words were right and the model was not.
		task.emit(taskModule.TALK, f"\"{part}\": the model chose to {planner.label(mine)}.")
		guess = planner.challenger(part, mine, before)
		if guess is None or guess not in planner.available(registry):
			return mine, AGREED
		task.check()
		note = (
			f"The user's words point to: {guess} ({planner.label(guess)}). You chose {mine}. Read the request again, "
			"word by word, and choose the one that fits what the user asked.")
		again = planner.classify(llm, lead, part, context, registry, note, before=before, facts=facts, brief=brief, also=also)
		if again == guess:
			task.emit(taskModule.TALK, f"After checking against your words, the model chose to {planner.label(again)}.")
			return again, REVISED
		task.emit(taskModule.TALK, (
			f"Your words could also mean: {planner.label(guess)}. The model looked again and still chose to "
			f"{planner.label(again)}."))
		looked = _bothLook(task, part, registry, again, guess)
		if looked is not None:
			return looked, REVISED
		ways = [guess, again]
		choices = [_sentence(planner.label(way)) for way in ways] + ["Cancel. I will ask in a different way."]
		question = f"VisionClaw is not sure what you mean by \"{uncut(part)}\". What should it do?"
		task.setState(taskModule.WAITING, "Not sure what you mean. Waiting for your choice.")
		picked = askUser(question, choices)
		task.check()
		if picked not in (0, 1):
			raise Declined()
		task.emit(taskModule.TALK, f"You chose: {choices[picked]}")
		return ways[picked], USER_CHOSE
	theirs = planner.classify(llm, other, part, context, registry, before=before, facts=facts, brief=brief, also=also)
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
		llm, lead, part, context, registry, note.format(choice=theirs, text=planner.label(theirs)), before=before, facts=facts,
		brief=brief, also=also)
	theirsAgain = planner.classify(
		llm, other, part, context, registry, note.format(choice=mine, text=planner.label(mine)), before=before, facts=facts,
		brief=brief, also=also)
	if mineAgain == theirsAgain:
		task.emit(taskModule.TALK, f"After looking again, both models chose to {planner.label(mineAgain)}.")
		return mineAgain, REVISED
	# Each swapping to the other's first choice is still a disagreement, so the first choices stand.
	task.emit(taskModule.TALK, "The models still do not agree.")
	looked = _bothLook(task, part, registry, mine, theirs)
	if looked is not None:
		return looked, REVISED
	choices = [
		f"As the {leadName} suggests: {planner.label(mine)}",
		f"As the {otherName} suggests: {planner.label(theirs)}",
		"Cancel. I will ask in a different way.",
	]
	question = f"The two models do not agree on how to handle this: \"{uncut(part)}\". What should VisionClaw do?"
	task.setState(taskModule.WAITING, "The models do not agree. Waiting for your choice.")
	picked = askUser(question, choices)
	task.check()
	if picked not in (0, 1):
		raise Declined()
	task.emit(taskModule.TALK, f"You chose: {choices[picked]}")
	return (mine, theirs)[picked], USER_CHOSE


def _bothLook(task, part, registry, chosen, other):
	"""Where two ways are left for a part and both only find something out, the user is not asked to choose: nothing
	is changed either way. The first (planner.firstWay) is planned, the other is kept to be tried where the first does
	not answer (orchestrator._nextWays), and the user is told. The owner said on 2026-11-19, after "tell me about the
	focused control" was put to the owner as a choice between a picture and an NVDA command: "you must make visionclaw more
	confident". Returns the way planned, or None where one of them changes something: then the user decides."""
	if chosen == other or not (planner.onlyLooks(chosen, registry) and planner.onlyLooks(other, registry)):
		return None
	first, second = planner.firstWay(chosen, other)
	task.otherWays = getattr(task, "otherWays", {})
	task.otherWays[part] = second
	task.emit(taskModule.TALK, (
		f"Both ways only look and change nothing, so VisionClaw does not ask: it will {planner.label(first)}, and if that "
		f"does not answer it, {planner.label(second)}."))
	return first


def _onlyLooking(steps, registry):
	"""Whether every step of a plan only finds something out."""
	try:
		return bool(steps) and all(registry.get(s.tool).looks and not registry.get(s.tool).changes for s in steps)
	except KeyError:
		return False


def _onOwnPlan(llm, task, part, context, registry, params, askUser, lead):
	"""A part that fits no recipe, with one model for both jobs: the model writes a plan and checks it itself,
	with the reviewer's question. Nothing here is called an agreement. Returns (steps, how)."""
	facts = getattr(task, "facts", None)
	steps = planner.freeSteps(llm, lead, part, context, registry, params, facts=facts)
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
	revised = planner.freeSteps(llm, lead, part, context, registry, params, note, facts=facts)
	task.emit(taskModule.TALK, f"New plan:\n{planner.planText(revised)}")
	fine, problemAgain = review(llm, lead, part, revised, registry, params)
	if fine:
		task.emit(taskModule.TALK, "The model checked the new plan and found no problem.")
		return revised, REVISED
	task.emit(taskModule.TALK, f"The model still finds a problem: {problemAgain}")
	task.check()
	if _onlyLooking(revised, registry):
		task.emit(taskModule.TALK, "The new plan only looks and changes nothing, so VisionClaw does not ask and uses it.")
		return revised, REVISED
	choices = ["Use the new plan: " + _oneLine(revised)]
	plans = [revised]
	if planner.planText(steps) != planner.planText(revised):
		choices.append("Use the first plan: " + _oneLine(steps))
		plans.append(steps)
	choices.append("Cancel. I will ask in a different way.")
	question = (
		f"The model is not sure how to do this: \"{uncut(part)}\". Its concern: "
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
	facts = getattr(task, "facts", None)
	steps = planner.freeSteps(llm, lead, part, context, registry, params, facts=facts)
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
	revised = planner.freeSteps(llm, lead, part, context, registry, params, note, facts=facts)
	task.emit(taskModule.TALK, f"New plan from the {leadName}:\n{planner.planText(revised)}")
	agrees, problemAgain = review(llm, other, part, revised, registry, params)
	if agrees:
		task.emit(taskModule.TALK, f"The {otherName} agrees with the new plan.")
		return revised, REVISED
	task.emit(taskModule.TALK, f"The {otherName} still disagrees: {problemAgain}")
	task.check()
	if _onlyLooking(revised, registry):
		task.emit(taskModule.TALK, (
			f"The {leadName}'s new plan only looks and changes nothing, so VisionClaw does not ask and uses it."))
		return revised, REVISED
	try:
		note = f"Another model's plan had this problem: {clip(problemAgain, 300)}\nWrite your own plan."
		theirs = planner.freeSteps(llm, other, part, context, registry, params, note, facts=facts)
	except LLMError:
		theirs = []
	choices = [f"Use the {leadName}'s plan: " + _oneLine(revised)]
	plans = [revised]
	if theirs and planner.planText(theirs) != planner.planText(revised):
		choices.append(f"Use the {otherName}'s plan: " + _oneLine(theirs))
		plans.append(theirs)
	choices.append("Cancel. I will ask in a different way.")
	question = (
		f"The two models do not agree on how to do this: \"{uncut(part)}\". The {otherName}'s concern: "
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
	before = None
	for whole in parts:
		task.check()
		# A part that depends on something plain code can find out: the step that checks it comes first, and
		# what is to be done is planned as always, and done only if the check says so.
		check = planner.conditional(whole, registry)
		gate, actions = check if check is not None else (None, [whole])
		if gate is not None:
			steps.append(gate)
			recipes.append(planner.IF)
			task.emit(taskModule.TALK, (
				f"\"{whole}\": first {gate.title[:1].lower()}{gate.title[1:]}. "
				+ ("Only if so: " + "; ".join(actions) + "." if actions else "The answer to that is all that was asked.")))
		for part in actions:
			task.check()
			recipe, partHow = _onRecipe(llm, task, part, context, registry, askUser, lead, other, single, before)
			if recipe == planner.OTHER:
				partSteps, planHow = _onFreePlan(llm, task, part, context, registry, params, askUser, lead, other)
				partHow = max(partHow, planHow, key=_RANK.get)
			else:
				partSteps = planner.recipeSteps(recipe, part, registry)
			otherWay = getattr(task, "otherWays", {}).get(part) if recipe != planner.OTHER else None
			for step in partSteps:
				step.onlyIf = gate
				# The other way that only looks, tried where this one does not answer (_bothLook).
				step.otherWay = otherWay
			steps += partSteps
			recipes.append(recipe)
			before = recipe
			how = max(how, partHow, key=_RANK.get)
	steps.append(planner.answerStep())
	task.emit(taskModule.TALK, ("The steps:\n" if single else "The agreed steps:\n") + planner.planText(steps))
	return steps, how, recipes


def _sentence(text):
	"""A recipe's few words as a choice the user can pick: with a capital letter and a full stop."""
	return text[:1].upper() + text[1:] + "."


def _oneLine(steps):
	return "; ".join(s.title for s in steps if s.tool != "answer") or "answer directly"
