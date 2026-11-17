# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - breaks a request into bite-size steps for small models.
#   1. The request is split into its separate parts ("turn off typing echo and set punctuation to all" is two).
#   2. Each part is matched to a recipe: a fixed, proven list of steps, one tool each.
#   3. Only a part that fits no recipe is planned freely by the model, and that plan is repaired by plain rules.
# A small model is good at choosing between a few named options and poor at inventing a plan, so it is asked
# to choose. No NVDA dependencies.

import re

from . import policy
from .llm import LLMError, clip
from .task import Step
from .tools import ANSWER

# --- Recipes ---

OTHER = "other"
# name: (a few words for the user; what the user wants, for the model that chooses; the tools, in order)
RECIPES = {
	"change_setting": (
		"change an NVDA setting",
		"change how NVDA speaks or behaves: speed, voice, volume, pitch, punctuation, typing echo, or another setting",
		("find_setting", "set_setting")),
	"do_command": (
		"run an NVDA command now",
		"do one thing NVDA has a command for, now: read the window title, say the time or battery, start reading, "
		"open the NVDA menu",
		("find_command", "run_command")),
	"explain_keys": (
		"tell you which keys to use",
		"tell the user which keys or which command to use for something in NVDA; questions like how do I ...",
		("find_command",)),
	"nvda_question": (
		"answer a question about NVDA",
		"answer a question about NVDA, what something in NVDA is, or how NVDA works",
		("search_help",)),
	"describe": (
		"look at the screen and describe it",
		"say what the screen, the window, a picture or a control looks like or shows",
		("look",)),
	"read_text": (
		"read out the text that is shown",
		"read out the exact text shown in the window or on the screen",
		("read_text",)),
	"click": (
		"click an item in the window",
		"click or press a button, link or other item in the window in front",
		("list_items", "click_item")),
	"press_keys": (
		"press keys in the program",
		"press keyboard keys in the program in front",
		("press_keys",)),
	"type_text": (
		"type text into the program",
		"type text into the program in front",
		("type_text",)),
	"make_hotkey": (
		"give this program a hotkey",
		"give this program a hotkey that clicks something or reads something in its window",
		("list_items", "create_helper")),
	"name_button": (
		"give the focused button a name",
		"give the focused button, which has no useful name, a name",
		("name_control",)),
	"write_addon": (
		"write an add-on",
		"write an NVDA add-on: new behaviour such as speaking or beeping when something happens, "
		"or anything the other choices cannot do",
		("create_addon",)),
	"list_made": (
		"list what VisionClaw has made",
		"list the helpers and add-ons VisionClaw has made",
		("list_helpers",)),
	"remove_made": (
		"remove something VisionClaw made",
		"remove a helper or add-on VisionClaw made",
		("list_helpers", "remove_helper")),
	"where_am_i": (
		"say where you are",
		"say which program, window and control the user is in",
		("focus_info",)),
}
# Words that point to a recipe. Checked in this order; the first that matches is the hint given to the model,
# and the choice when the model fails.
_HINTS = (
	("write_addon", r"add-?on|plug-?in|write (me )?(a |some )?(code|script)|every time|whenever|automatically|when (a|an|the|i) .* (gets?|gains?|changes?|appears?|opens?)"),
	("remove_made", r"\b(remove|delete|get rid of)\b.*\b(helper|hot ?key|add-?on)"),
	("list_made", r"\b(list|show|which|what)\b.*\b(helpers?|add-?ons?)\b.*\b(made|have|wrote|written|created)"),
	("make_hotkey", r"hot ?key|shortcut (key )?(for|to|that)|\bkey (for|to|that)\b"),
	("name_button", r"\b(name|label|call)\b.*\b(button|control|icon)|unlabel|no label|has no name"),
	("explain_keys", r"how (do|can|would|to) |what (key|keys|command|shortcut)|which (key|keys|command)|shortcut for"),
	("change_setting", r"speed|rate\b|faster|slower|louder|quieter|volume|pitch|voice|punctuation|echo|braille|setting|turn (on|off)|switch (on|off)|enable|disable|stop (saying|reading|announcing|speaking)"),
	("click", r"\b(click|press|push|activate|select|choose|start|open)\b.*\b(button|link|item|menu|tab|icon|game|option)|\bclick\b"),
	("press_keys", r"\bpress\b.*\b(key|enter|escape|tab|control|alt|shift|f\d+)\b"),
	("type_text", r"\btype\b|\bwrite\b.*\binto\b"),
	("do_command", r"\b(read|say|speak|tell me|report)\b.*\b(title|time|date|battery|clipboard|status|focus)\b|say all|start reading"),
	("read_text", r"\bread\b.*\b(text|everything)\b|\bread (me )?(the |this |all of the )?(whole )?(window|screen)\b"),
	("describe", r"what('s| is| does)? .*(look|show|screen|window|picture|image|photo)|describe|look at|colou?r|what do you see|on (the|my) screen"),
	("where_am_i", r"where am i|which (program|app|window|control)|what (program|app|window) (is|am)"),
	("nvda_question", r"what (is|are|does)|explain|tell me about|why"),
)
_CONNECTORS = re.compile(r"\b(and|then|also|after that|afterwards|plus)\b|[;]|,\s*(and|then)?", re.IGNORECASE)
MAX_PARTS = 4

_SPLIT_SCHEMA = {
	"type": "object",
	"properties": {
		"parts": {"type": "array", "minItems": 1, "maxItems": MAX_PARTS, "items": {"type": "string", "maxLength": 200}},
	},
	"required": ["parts"],
}
_SPLIT_SYSTEM = (
	"You split a request made to a screen reader assistant into the separate things the user wants done, in order.\n"
	"Rules: Keep the user's own words. Each part must be understandable alone, so repeat what a part refers to. "
	"If the request is one thing, give one part. Never add anything the user did not ask for. "
	"Do not split one action into smaller actions.\n"
	"Examples:\n"
	"Request: Turn off the typing echo and set punctuation to all\n"
	"parts: [\"Turn off the typing echo\", \"Set punctuation to all\"]\n"
	"Request: Make NVDA talk faster\n"
	"parts: [\"Make NVDA talk faster\"]\n"
	"Request: Look at this window and tell me what the buttons are\n"
	"parts: [\"Look at this window and tell me what the buttons are\"]\n"
	"Request: Click Options, then tell me what the new window shows\n"
	"parts: [\"Click Options\", \"Tell me what the new window shows\"]"
)


def hint(part):
	"""The recipe a part's words point to, or OTHER."""
	text = part.lower()
	for name, pattern in _HINTS:
		if re.search(pattern, text):
			return name
	return OTHER


def label(recipe):
	"""A recipe in a few words, for telling the user."""
	return RECIPES[recipe][0] if recipe in RECIPES else "work out the steps itself"


def recipeSteps(recipe, part, registry):
	"""The steps of a recipe for one part of the request. Code fills in what it can from the part's own words."""
	return [Step(registry.get(name).title, name, part, part, recipe=recipe) for name in RECIPES[recipe][2]]


def available(registry):
	"""The recipes whose tools all exist."""
	return {name: recipe for name, recipe in RECIPES.items() if registry.has(recipe[2])}


def split(llm, role, request, note=""):
	"""The separate things a request asks for, in order."""
	request = " ".join(request.split())
	if len(request) < 200 and not _CONNECTORS.search(request):
		return [request]  # clearly one thing: no model needed
	user = f"Request: {clip(request, 800)}"
	if note:
		user += f"\n{note}"
	try:
		found = llm.json(role, _SPLIT_SYSTEM, user, _SPLIT_SCHEMA, maxTokens=220)
	except LLMError:
		return [request]
	parts = [" ".join(str(p).split()) for p in found.get("parts") or [] if str(p).strip()]
	# A part that is not in the request at all was made up; then the request is kept whole.
	words = set(re.findall(r"[a-z0-9]{3,}", request.lower()))
	for part in parts:
		mine = set(re.findall(r"[a-z0-9]{3,}", part.lower()))
		if mine and len(mine & words) / len(mine) < 0.5:
			return [request]
	return parts[:MAX_PARTS] or [request]


def classify(llm, role, part, context, registry, note=""):
	"""The recipe that fits a part of the request, or OTHER."""
	recipes = available(registry)
	guess = hint(part)
	if guess not in recipes:
		guess = OTHER
	lines = "\n".join(f"- {name}: {text}" for name, (_label, text, _tools) in recipes.items())
	system = (
		"You choose how VisionClaw, an assistant inside the NVDA screen reader for a blind person, should handle "
		"one thing the user asked for. Choose the one that fits best:\n" + lines
		+ f"\n- {OTHER}: none of the above fits"
	)
	schema = {
		"type": "object",
		"properties": {"choice": {"type": "string", "enum": list(recipes) + [OTHER]}},
		"required": ["choice"],
	}
	user = f"The user asked: \"{clip(part, 400)}\"\n"
	if context:
		user += f"What is known: {clip(context, 400)}\n"
	if guess != OTHER:
		user += f"Its words suggest: {guess}.\n"
	if note:
		user += f"{note}\n"
	user += "Which one fits?"
	try:
		return llm.json(role, system, user, schema, maxTokens=40)["choice"]
	except (LLMError, KeyError):
		return guess


def complexity(recipes):
	"""How demanding a request is, from the recipes its parts use."""
	if len(recipes) >= 3 or OTHER in recipes or "write_addon" in recipes:
		return policy.COMPLEX
	if len(recipes) == 2 or any(len(RECIPES[r][2]) > 1 for r in recipes if r in RECIPES):
		return policy.MODERATE
	return policy.SIMPLE


def quickTriage(request):
	"""A first sorting of a request from its words alone, before any model is asked."""
	parts = [p for p in _CONNECTORS.split(request) if p and len(p.strip()) > 8] or [request]
	recipes = [hint(p) for p in parts[:MAX_PARTS]]
	return {
		"kind": recipes[0],
		"complexity": complexity(recipes),
		"needs_vision": any(r in ("describe", "click", "make_hotkey", "read_text") for r in recipes),
		"needs_code": "write_addon" in recipes,
	}


# --- Plans ---

def _freeSchema(toolNames, maxSteps):
	return {
		"type": "object",
		"properties": {
			"steps": {
				"type": "array", "minItems": 1, "maxItems": maxSteps,
				"items": {
					"type": "object",
					"properties": {
						"tool": {"type": "string", "enum": toolNames},
						"detail": {"type": "string", "maxLength": 200},
					},
					"required": ["tool", "detail"],
				},
			},
		},
		"required": ["steps"],
	}


def _freeSystem(registry, maxSteps):
	return (
		"You plan the work of VisionClaw, an assistant inside the NVDA screen reader for a blind person.\n"
		"Break what the user asked for into small steps. Rules:\n"
		"- Each step uses exactly one tool and does one small thing.\n"
		"- Look before you act: find a setting before changing it, find a command before running it, "
		"list the items in a window before clicking one.\n"
		"- Do only what was asked. Use as few steps as possible.\n"
		"- Prefer the simplest tool that does the job. Write an add-on only when no other tool can do it.\n"
		f"- Use at most {maxSteps} steps. detail says exactly what to do in that step, in plain words.\n\n"
		"Tools:\n" + registry.listText()
	)


def freeSteps(llm, role, part, context, registry, params, note=""):
	"""A plan written by the model, for a part that fits no recipe. Repaired by plain rules."""
	names = [n for n in registry.names() if n != ANSWER]
	user = f"The user asked: \"{clip(part, 600)}\"\n"
	if context:
		user += f"What is known:\n{clip(context, 700)}\n"
	if note:
		user += f"{note}\n"
	user += "Write the steps."
	found = llm.json(
		role, _freeSystem(registry, params.maxSteps), user, _freeSchema(names, params.maxSteps),
		maxTokens=params.planTokens, reasoning=params.reasoning,
	)
	return normalize(found.get("steps") or [], registry, params.maxSteps, part)


def normalize(rawSteps, registry, maxSteps, part=""):
	"""Repair a model's plan by plain rules, so that it can be run. Returns a list of Step, without the answer."""
	steps = []
	for raw in rawSteps[:maxSteps]:
		tool = registry.get(raw.get("tool"))
		if tool is None or tool.name == ANSWER:
			continue
		detail = " ".join(str(raw.get("detail") or "").split())
		if steps and steps[-1].tool == tool.name and steps[-1].detail == detail:
			continue  # the same step twice in a row
		# A step that needs something found first gets that step put before it.
		if tool.before and registry.get(tool.before) and not any(s.tool == tool.before for s in steps):
			steps.append(Step(registry.get(tool.before).title, tool.before, detail, part))
		steps.append(Step(tool.title, tool.name, detail, part))
	return steps


def planText(steps):
	return "\n".join(f"{i}. {s.title} [{s.tool}]" for i, s in enumerate(steps, 1))


def detailText(steps):
	return "\n".join(f"{i}. {s.title} [{s.tool}] {s.detail}" for i, s in enumerate(steps, 1))


def answerStep():
	return Step("Telling you the result", ANSWER, "say what was done or found, in plain words")


def plan(llm, role, request, context, registry, params, note=""):
	"""Break a request into steps. note is extra guidance, like another model's objection to an earlier plan.
	Returns (steps, recipes): the steps end with the answer; recipes are the recipe names used, one per part."""
	steps, used = [], []
	for part in split(llm, role, request, note):
		recipe = classify(llm, role, part, context, registry, note)
		used.append(recipe)
		if recipe == OTHER:
			steps += freeSteps(llm, role, part, context, registry, params, note)
			continue
		steps += recipeSteps(recipe, part, registry)
	return steps + [answerStep()], used


def revise(llm, role, request, context, steps, objection, registry, params):
	"""Plan again, taking another model's objection into account."""
	note = (
		f"An earlier plan was:\n{detailText(steps)}\n"
		f"A reviewer found this problem with it: {clip(objection, 300)}\nChoose again so that the problem is fixed."
	)
	return plan(llm, role, request, context, registry, params, note)


_RETHINK_SCHEMA = {
	"type": "object",
	"properties": {"change": {"type": "boolean"}, "why": {"type": "string", "maxLength": 160}},
	"required": ["change", "why"],
}


def rethink(llm, role, request, results, remaining, registry, params):
	"""After a step that looked at something, in a plan the model wrote itself: should the rest change?
	Returns new steps (ending with the answer) or None."""
	system = (
		"You check a plan while it runs, for an assistant inside the NVDA screen reader. "
		"Say change=true only if what was just found shows that the remaining steps cannot work or would do "
		"the wrong thing. If they still fit, say change=false."
	)
	user = (
		f"Request: \"{clip(request, 500)}\"\nFound so far:\n{clip(results, 1200)}\n"
		f"Remaining steps:\n{detailText(remaining)}"
	)
	found = llm.json(role, system, user, _RETHINK_SCHEMA, maxTokens=80)
	if not found.get("change"):
		return None
	note = (
		f"Already done and found:\n{clip(results, 1200)}\nThe old remaining steps no longer fit because: "
		f"{found.get('why', '')}\nWrite only the steps that are still needed."
	)
	return freeSteps(llm, role, request, "", registry, params, note) + [answerStep()]
