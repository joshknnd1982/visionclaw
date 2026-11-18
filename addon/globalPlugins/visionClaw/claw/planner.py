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
		"click, double-click, right-click or point at a button, link or other item, in the window in front or on "
		"the web page",
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
		"list only what VisionClaw itself has made: its hotkey helpers and the small add-ons it wrote",
		("list_helpers",)),
	"remove_made": (
		"remove something VisionClaw made",
		"remove a helper or add-on VisionClaw made",
		("list_helpers", "remove_helper")),
	"open_website": (
		"open a website",
		"open a website or a web address in the browser",
		("web_open",)),
	"search_web": (
		"search the web",
		"search the web for something and say what was found",
		("web_search", "read_page")),
	"web_page": (
		"read the web page and answer",
		"answer a question about the web page that is open in the browser, or summarize it",
		("read_page",)),
	"page_outline": (
		"say how the web page is laid out",
		"list the headings of the web page, or say how the page is laid out and what is on it",
		("page_outline",)),
	"go_to": (
		"move to a place on the web page",
		"move NVDA's reading position to a heading, section, link or field of the web page, to read on from there",
		("list_items", "go_to_item")),
	"page_navigate": (
		"go back, forward or reload",
		"go back or forward one page in the browser, or reload the page",
		("page_navigate",)),
	"fill_field": (
		"type into a field",
		"type text into a named field or box, such as a search box or a field of a form",
		("list_items", "fill_field")),
	"nvda_info": (
		"tell you what NVDA has and uses",
		"say which speech synthesizer, voice, braille display, braille table, driver or version NVDA has or "
		"uses and how they are set, or which add-ons are installed in NVDA",
		("nvda_info",)),
	"visionclaw_models": (
		"tell you which AI models VisionClaw uses",
		"say which AI model or models VisionClaw itself, the assistant, has installed, downloaded or stored and "
		"is using or running, how big they are, and where they run",
		("model_info",)),
	"switch_driver": (
		"switch the speech synthesizer or braille display",
		"switch NVDA to a different speech synthesizer or a different braille display",
		("nvda_info", "switch_driver")),
	"fix_addon": (
		"debug and correct an add-on",
		"fix, debug or change an add-on VisionClaw wrote that fails or does not do what it should",
		("list_helpers", "repair_addon")),
	"undo_change": (
		"put a setting back",
		"undo a change VisionClaw made: put a setting back to what it was before, restore it, revert it",
		("undo_change",)),
	"list_changes": (
		"say what VisionClaw has changed",
		"say which settings VisionClaw has changed",
		("list_changes",)),
	"save_addon": (
		"save an add-on as a file",
		"save an add-on VisionClaw wrote as a file that can be installed for good or shared",
		("list_helpers", "export_addon")),
	"check_access": (
		"inspect this page or window for accessibility problems",
		"inspect the web page, the program's window or the focused control in depth, and report what makes it "
		"hard to use with a screen reader and what can be fixed",
		("check_access",)),
	"fix_access": (
		"fix the accessibility problems here with an add-on",
		"fix the accessibility problems of the website or program the user is in, all of them or the one they "
		"name, with an add-on that stays; make a website or a program accessible",
		("check_access", "fix_access")),
	"add_fix": (
		"add one lasting fix for this website or program",
		"for the website or program the user is in, make one lasting fix they describe: a key that presses or "
		"reads a control by its name, keys that move between posts, results or other items, a name for a control "
		"that has none, or being told when a part of it changes",
		("check_access", "add_fix")),
	"addon_question": (
		"answer a question about an installed add-on",
		"say what one add-on installed in NVDA does, whether it is on, which keys it has, or how to use it",
		("addon_info",)),
	"drag": (
		"drag something with the mouse",
		"drag an item with the mouse onto another item or in a direction, or move a slider",
		("list_items", "drag_item")),
	"work_control": (
		"let the arrow keys work a dial or slider",
		"let the arrow keys work a dial, knob, custom slider or other control that is only worked by dragging it "
		"with the mouse, and say what it shows",
		("work_control",)),
	"update_visionclaw": (
		"look for a newer version of VisionClaw",
		"look for a newer version of VisionClaw itself, the add-on, and get it; check whether VisionClaw is up to date",
		("check_update",)),
	"update_guides": (
		"download the latest NVDA developer guides",
		"download the latest NVDA developer guide and add-on development guide from the internet, for the models "
		"to read up in",
		("update_guides",)),
	"scroll": (
		"scroll with the mouse wheel",
		"scroll what the window shows up, down, left or right with the mouse wheel, a little, a page or to the "
		"end, where the keyboard does not scroll it",
		("scroll_view",)),
	"keyboard_mouse": (
		"let you work the mouse pointer with the keyboard",
		"turn on pointer mode, so the user can work a control, canvas or game that has nothing to list: the arrow "
		"keys move the mouse pointer, and keys click, right-click and drag",
		("pointer_mode",)),
	"where_am_i": (
		"say where you are",
		"say which program, window and control the user is in",
		("focus_info",)),
	"object_facts": (
		"say what NVDA knows about a control",
		"give the technical facts of one control or window on the screen, for the focused control, the navigator "
		"object, the window in front or what is under the mouse: its kind, states, position and size, window "
		"class, process",
		("object_info",)),
	"inside_nvda": (
		"look inside NVDA's program code",
		"say what a function, class, module, object or value inside NVDA's own program code or an add-on's code "
		"is, how it is called, and what it holds or gives back now; for people who write add-ons",
		("find_nvda", "inspect_nvda")),
	"audit_nvda": (
		"list everything in this NVDA",
		"make a full audit of this NVDA: count and list every command, module, function, class and object it "
		"has, and how it works its speech synthesizer and braille display, and save the list as a file",
		("audit_nvda",)),
	"visionclaw_log": (
		"open VisionClaw's log",
		"open VisionClaw's own debug log, the file that records what VisionClaw did and every error, to find "
		"out why something went wrong",
		("show_log",)),
}
# Words that point to a recipe. Checked in this order; the first that matches is the hint given to the model,
# and the choice when the model fails.
_HINTS = (
	("update_visionclaw", r"\b(update|upgrade|updates|new version|newer version|latest version|up to date)\b.*\bvisionclaw\b"
		r"|\bvisionclaw\b.*\b(update|updates|upgrade|new version|newer version|latest version|up to date)\b"
		r"|\b(check|look) for (an? |any )?(updates?|new(er)? version)\b"),
	("update_guides", r"\b(download|get|pull|fetch|update|refresh|renew)\b.*\b(developer|development|dev)\b.*\bguides?\b"
		r"|\b(developer|development|dev) guides?\b.*\b(up to date|latest|newest|download|update)\b"),
	# A control that is dragged or turned: the arrow keys take over. Before the hotkey, mouse and drag hints.
	("work_control", r"\b(dial|knob|fader)s?\b"
		r"|\barrow keys?\b.*\b(work|turn|move|operate|control)\b.*\b(slider|control|lever)\b"
		r"|\b(work|turn|operate|move)\b.*\b(slider|control|lever)\b.*\b(arrow keys?|keyboard|keys)\b"
		r"|\b(used|worked|operated|moved) (only )?by (clicking and )?dragging\b"),
	# All of NVDA at once. Before the inspection of a page or window, which the word "audit" also means.
	("audit_nvda", r"^(?!.*\b(page|site|web|window|button|control)\b).*(\b(audit|inventory)\b.*\bnvda\b"
		r"|\bnvda\b.*\b(audit|inventory)\b"
		r"|\b(list|count|show)\b.*\b(every|all|everything)\b.*\b(in|inside|of)\b.*\bnvda\b"
		r"|\beverything (that is )?(in|inside) nvda\b)"),
	# VisionClaw's own log; NVDA's log viewer is an NVDA command.
	("visionclaw_log", r"\bvisionclaw('s)? (debug |error )?log\b|\b(debug|error) log\b"
		r"|\blog\b.*\b(of|from|for) visionclaw\b"),
	# Something inside NVDA's code, by its kind or by a dotted name like api.getFocusObject. Before the
	# add-on hints, which the word "code" would otherwise set off.
	("inside_nvda", r"\b(function|method|class|module|python object)s?\b.*\b(nvda|add-?on)('s)?\b"
		r"|\b(nvda|add-?on)('s)?\b.*\b(functions?|methods?|class(es)?|modules?|python objects?|source code)\b"
		r"|\b[a-z_]\w*\.(get|is|has|set)[a-z_]\w+|\binside nvda('s)? (code|program)\b"),
	("save_addon", r"\b(save|export|package|share)\b.*\badd-?on"),
	("list_changes", r"\bwhat\b.*\b(did|have|has)\b.*\b(you|visionclaw)\b.*\bchanged?\b|\bwhich settings\b.*\bchanged\b"),
	("undo_change", r"\b(undo|revert|restore)\b|\b(put|change|set|turn)\b.*\bback\b|\bback to (what|how|the way)\b"
		r"|\bas it was\b|\bwhat it was before\b"),
	# Fixing a website or a program, not an add-on: "fix the add-on ..." stays with fix_addon below.
	# These three are kept narrow on purpose: each needs words that can hardly mean anything else, because a
	# hint is what the model is told the words suggest, and the choice when the model fails.
	("fix_access", r"^(?!.*\b(fix|repair|correct|debug) (the |my |that |this )?add-?on\b)(?=.*("
		r"\b(fix|repair)\b.*\baccessib\w*"
		r"|\b(fix|repair) (this|the|that) (web ?page|page|web ?site|site|window|program|app|game)\b"
		r"|\b(fix|repair) (everything|all of (it|them)|(it|them) all|number \d+|problem \d+)\b"
		r"|\b(fix|repair)\b.*\b(unlabell?ed|unnamed|nameless)\b"
		r"|\b(fix|repair)\b.*\b(buttons?|links?|controls?|fields?|images?)\b.*\b(no|without|missing)\b.*\b(names?|labels?)\b"
		r"|\b(fix|repair)\b.*\b(on|of) (this|the) (web ?page|page|web ?site|site)\b"
		r"|\bmake\b.*\b(page|web ?site|site|window|program|app|game)\b.*\b(accessible|usable|easier to use)\b"
		r"|\bmake (it|this|that) (more |fully )?accessible\b"
		r"|^(please )?fix (it|them|these|those)( all)?( please)?[.!]?$))"),
	("check_access", r"\b(inspect|audit)\b|\bdeep(ly)? (inspection|look|check|scan|query)\b"
		r"|\b(check|scan|test|analy[sz]e|review|query|examine)\b.*\b(accessib\w*|usab\w*)\b"
		r"|\baccessib\w* (problems?|issues?|check|report)\b|\bis (this|the) .*\baccessible\b|\bhow accessible\b"
		r"|\bwrong with (this|the) (web ?page|page|web ?site|site|window|program|app|button|control)\b"),
	("add_fix", r"\b(make|give|add|create|set up)\b.*\b(keys?|hot ?keys?|shortcuts?)\b.*\b(page|web ?site|site|posts?|feed|videos?|player|results?)\b"
		r"|\b(make|give|add|create|set up)\b.*\b(page|web ?site|site)\b.*\b(keys?|hot ?keys?|shortcuts?)\b"
		r"|\b(make|let|have)\b.*\b(nvda|control|ctrl|alt|shift)\s*\+\s*\w+.*\b(press|click|read|say|activate)\b"
		r"|\b(tell me|announce|let me know)\b.*\bwhen\b.*\b(changes?|updates?|arrives?)\b"
		r"|^(please )?(name|label|rename)\b.*\b(on|for|in) (this|the) (web ?page|page|web ?site|site)\b"),
	("fix_addon", r"\b(fix|repair|correct|debug)\b.*\badd-?on|\badd-?on\b.*\b(does(n't| not) work|is broken|stopped working|fails|wrong)\b"),
	("remove_made", r"\b(remove|delete|get rid of)\b.*\b(helper|hot ?key|add-?on)"),
	("list_made", r"\b(list|show|which|what)\b.*\b(helpers?|add-?ons?)\b.*\b(you|visionclaw)\b.*\b(made?|wrote|writes?|written|created?|built|build)\b"
		r"|\b(list|show|which|what)\b.*\b(you|visionclaw)\b.*\b(made|wrote|written|created|built)\b"),
	("write_addon", r"\b(write|make|create|build|code|program)\b.*\b(add-?on|plug-?in|code|script)\b|every time|whenever|automatically|when (a|an|the|i) .* (gets?|gains?|changes?|appears?|opens?)"),
	("make_hotkey", r"hot ?key|shortcut (key )?(for|to|that)|\bkey (for|to|that)\b"),
	("name_button", r"\b(name|label|call)\b.*\b(button|control|icon)|unlabel|no label|has no name"),
	("switch_driver", r"\b(switch|change|use|set)\b.*\b(synthesi[sz]ers?|synths?|braille (display|driver))\b"
		r"|\b(switch|change) to (espeak|one ?core|sapi|eloquence|no speech|no braille)"),
	("page_navigate", r"\b(go|navigate|move|take me)\s+(back|forward)\b|\b(previous|last|next) page\b|\b(reload|refresh)\b"),
	("page_outline", r"\b(headings|outline|laid out|layout|structure)\b"),
	("go_to", r"\b(go|jump|move|take me|skip)\b.*\b(to|down to)\b.*\b(heading|section|part|link|field|box|form|main content|comments?)\b"),
	("search_web", r"\b(search|look up|google)\b.*\b(web|internet|online|for)\b"),
	("open_website", r"\b(open|go to|visit|load|browse to)\b.*(\w\.[a-z]{2,}\b|web ?site|web ?page|\burl\b)"),
	("fill_field", r"\b(type|enter|write|fill|put)\b.*\b(in|into)\b.*\b(field|box|form|search)\b"),
	# One add-on, named: "the Clock add-on". Questions about add-ons in general stay with nvda_info below.
	("addon_question", r"\b(what|how|which|tell me|explain|help|does|is)\b.*\b(the|my) [\w .-]{0,40}add-?on\b(?!s)"
		r"|\b(about|use|using) (the|my) [\w .-]{0,40}add-?on\b(?!s)"),
	("nvda_info", r"\b(which|what|list|show|tell me|do i have)\b.*\b(synthesi[sz]ers?|synths?|voices?|braille|drivers?|add-?ons?|version)\b"),
	# VisionClaw's own models. After nvda_info, so that the model of a braille display stays there; and not for
	# a model that is shown in a picture or named on a page.
	("visionclaw_models", r"^(?!.*\b(picture|image|photo|screen|window|page|site|article|car|phone|printer)\b)(?=.*("
		r"\b(which|what|list|show|tell me|do i have|do you have|how many|how big|how large|is|are|name)\b.*\b(models?|qwen|llms?)\b"
		r"|\b(models?|qwen|llms?)\b.*\b(installed|downloaded|stored|loaded|running|in use|being used|chosen|selected)\b"
		r"|\bwhat (ai|a\.i\.) (is|are)\b|\bwhich (ai|a\.i\.)\b))"),
	("explain_keys", r"how (do|can|would|to) |what (key|keys|command|shortcut)|which (key|keys|command)|shortcut for"),
	("keyboard_mouse", r"\bpointer mode\b|\bmouse (mode|keys)\b|\b(keyboard|arrow keys?)\b.*\b(mouse|pointer)\b"
		r"|\b(mouse|pointer)\b.*\b(keyboard|arrow keys?)\b|\bkeyboard[- ](navigable|accessible)\b"),
	("drag", r"\bdrag\b|\bslider\b|\bdrop\b.*\b(on|onto|into)\b"),
	("scroll", r"\bscroll(s|ed|ing)?\b|\bmouse wheel\b"),
	("change_setting", r"speed|rate\b|faster|slower|louder|quieter|volume|pitch|voice|punctuation|echo|braille|setting|turn (on|off)|switch (on|off)|enable|disable|stop (saying|reading|announcing|speaking)"),
	("click", r"\bright[- ]click\b|\bdouble[- ]click\b|\bhover\b|\bpoint (at|to)\b"),
	("click", r"\b(click|press|push|activate|select|choose|start|open)\b.*\b(button|link|item|menu|tab|icon|game|option)|\bclick\b"),
	("press_keys", r"\bpress\b.*\b(key|enter|escape|tab|control|alt|shift|f\d+)\b"),
	("type_text", r"\btype\b|\bwrite\b.*\binto\b"),
	# The facts NVDA holds about one object. Kept narrow: "report the navigator object" is an NVDA command.
	("object_facts", r"\b(properties|property|attributes?|facts|details|everything|all)\b.*\b(about|of|on)\b.*"
		r"\b(control|object|button|element|field|focus)\b"
		r"|\b(window class|class name|control id|window handle|process id|automation id|role|states|coordinates)\b"
		r".*\b(of|for)\b.*\b(this|the|focused|current|navigator|control|object|button|window)\b"
		r"|\bwhat does nvda know about\b"),
	("do_command", r"\b(read|say|speak|tell me|report)\b.*\b(title|time|date|battery|clipboard|status|focus)\b|say all|start reading"
		r"|\b(give|get|tell|check|what('s| is| are))\b.*\b(time|date|battery)\b|\bwhat (time|day|date) is it\b"),
	("read_text", r"\bread\b.*\b(text|everything)\b|\bread (me )?(the |this |all of the )?(whole )?(window|screen)\b"),
	("web_page", r"\b(this|the|current) (web ?page|page|web ?site|site|article)\b|summari[sz]e"),
	("describe", r"what('s| is| does)? .*(look|show|screen|window|picture|image|photo)|describe|look at|colou?r|what do you see|on (the|my) screen"),
	("where_am_i", r"where am i|which (program|app|window|control)|what (program|app|window) (is|am)"),
	("nvda_question", r"what (is|are|does)|explain|tell me about|why"),
)
_CONNECTORS = re.compile(r"\b(and|then|also|after that|afterwards|plus)\b|[;]|,\s*(and|then)?", re.IGNORECASE)
MAX_PARTS = 4
# A part that speaks of "it" cannot be understood without the part before it.
_REFERS_BACK = re.compile(r"\b(it|its|they|them|their|that one|this one)\b", re.IGNORECASE)

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
	return settle(parts[:MAX_PARTS]) or [request]


def settle(parts):
	"""Make every part understandable alone, by plain rules, since small models split too eagerly.
	A fragment of one or two words ("search", "press it") belongs to the part before it. A part that speaks of
	"it" is given the part before it as its background."""
	settled, plain = [], []
	for part in parts:
		if settled and len(part.split()) < 3:
			settled[-1] = f"{settled[-1]} and {part[0].lower()}{part[1:]}"
			plain[-1] = settled[-1]
		elif settled and _REFERS_BACK.search(part):
			settled.append(f"{part} (this follows: {plain[-1]})")
			plain.append(part)
		else:
			settled.append(part)
			plain.append(part)
	return settled


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
		"needs_vision": any(r in ("describe", "click", "make_hotkey", "read_text", "fix_access", "check_access") for r in recipes),
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
