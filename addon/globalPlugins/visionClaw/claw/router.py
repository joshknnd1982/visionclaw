# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the router: which kinds of request, and which tools, a model is offered for one thing the user
# asked. A small model chooses well among a dozen things and badly among eighty. So plain code first leaves out
# what cannot be meant where the user is and by what they said:
#   - what needs a web page is offered when a web page or a browser is in front, when the part before opened
#     one, or when the words speak of a page;
#   - what needs a game controller, when one is connected or named;
#   - what reads everything from the user's own words (a shutdown, the Recycle Bin, a touch gesture) only when
#     the words say it, because its tool could do nothing otherwise;
#   - what is about one subject (skills, notes, downloads, VisionClaw's log) when the words name the subject.
# What is always offered is the everyday core. What the user's own words point to is always offered, whatever
# the place: the router never hides what was asked for. And where a model finds nothing that fits among what it
# was offered, it is offered everything, once (planner.classify): the router narrows, it never forbids.
# Where the words can hardly mean anything else, no model is asked at all (`decides`).
# The facts about where the user is come from the add-on (a dict). A fact that is missing is unknown, and
# unknown never hides anything. No NVDA dependencies.

import re

# Facts about where the user is. True, False, or missing when it could not be found out.
WEB, CONTROLLER, DIRECT = "web", "controller", "direct"
# Windows' own shell is in front: the desktop, the taskbar, the Start menu or a folder window of File Explorer.
# None of them has a Start button or a taskbar of its own (claw/planning.py, SHELL_PLACES).
SHELL = "shell"
# What the part of the request before this one did, when that opens a place: after a web page was opened, the
# next part may ask about it, though no browser was in front when the request was planned.
_OPENS_WEB = ("open_website", "search_web", "page_navigate", "go_to", "fill_field", "web_page")

_WEB_WORDS = (
	r"\b(pages?|sites?|web ?sites?|web|links?|headings?|articles?|browser|tabs?|forms?|fields?|box|url|address|online|"
	r"internet|reload|refresh|go back|go forward|comments?|posts?|inbox|e-?mails?|messages?|results?|sections?)\b"
	r"|\b[a-z0-9-]+\.(com|org|net|edu|gov|io|co|uk|de|fr|ca|au)\b")
_PAD_WORDS = r"\b(controllers?|game ?pads?|joy ?pads?|joysticks?|xbox|playstation|triggers?|bumpers?|d-?pad|thumb ?sticks?)\b"
_NOTES = r"\bnotes?\b|\b(learn|study|research|read up)\b"
_MEMORY = r"\b(remember\w*|forget|memor\w+|know about me|keep in mind|bear in mind)\b"
_DOWNLOADS = (
	r"\b(guides?|training|materials?|download\w*|lessons?|tutorials?|workshops?|wiki|afb|hadley|markdown|documentation)\b")
_COACH = r"\b(coach\w*|teach|train|tutor|lessons?|hints?|clues?|tutorials?)\b"
_DEVELOPER = (
	r"\b(functions?|methods?|class(es)?|modules?|objects?|code|api|python|source|audit|inventory|properties|property|"
	r"attributes?|facts|details|everything|window class|class name|control id|handle|role|states|coordinates)\b"
	r"|\bnvda know\b|\b[a-z_]\w*\.[a-z_]\w+")
_MADE = r"\b(add-?ons?|plug-?ins?|helpers?|hot ?keys?|shortcuts?|made|wrote|written|created|built)\b"
_CHANGES = r"\b(undo|revert|restore|back|before|changed?|changes|was)\b"
_PROFILES = (
	r"\bprofiles?\b|\b(own|different|special|separate) (nvda )?settings?\b|\bsettings? (for|of|in|from)\b|\beverywhere\b"
	r"|\b(other|every other) programs?\b")
_VOICE = r"\b(voice|speech|speak\w*|talk\w*|dictat\w*|microphone|out loud|asr|listen\w*|hear)\b"
_DRIVERS = r"\b(synth\w*|voices?|braille|drivers?|displays?|version|add-?ons?|espeak|one ?core|sapi\w*|eloquence|cells)\b"
_ACCESS = (
	r"\b(accessib\w*|inspect\w*|audit|fix\w*|repair\w*|scan|check|usab\w*|unlabell?ed|unnamed|labels?|names?|keys?|"
	r"announce|let me know|tell me when|wrong with|deep|query|problems?|navigable|sighted)\b")
_POINTER = r"\b(pointer|mouse|keyboard|navigable|arrow keys?|cursor)\b"
# name: (the fact that opens it, or None; the words that open it, or None).
GATES = {
	"web_page": (WEB, _WEB_WORDS), "page_outline": (WEB, _WEB_WORDS), "go_to": (WEB, _WEB_WORDS),
	"explore_page": (WEB, _WEB_WORDS + r"|\b(landmarks?|laid out|layout|explore)\b"),
	"form_trouble": (WEB, _WEB_WORDS + r"|\b(submit\w*|required|errors?|invalid|sign up|register|check ?out)\b"),
	"page_navigate": (WEB, _WEB_WORDS), "fill_field": (WEB, _WEB_WORDS + r"|\b(type|enter|fill|put|write)\b"),
	"note_page": (None, _NOTES),
	"controller_info": (CONTROLLER, _PAD_WORDS), "controller_mode": (CONTROLLER, _PAD_WORDS),
	"mouse_way": (DIRECT, r"\b(mouse|pointer|cursor|game|view|camera|aim|crosshairs?)\b"),
	"add_skill": (None, r"\bskills?\b"), "list_skills": (None, r"\bskills?\b"), "show_skill": (None, r"\bskills?\b"),
	"manage_skill": (None, r"\bskills?\b"),
	"learn_app": (None, _NOTES), "app_notes": (None, _NOTES), "forget_notes": (None, _NOTES),
	"memories": (None, _MEMORY), "forget_memory": (None, _MEMORY), "library": (None, r"\blibrary\b"),
	"update_guides": (None, _DOWNLOADS), "guides_info": (None, _DOWNLOADS), "remove_guides": (None, _DOWNLOADS),
	"update_training": (None, _DOWNLOADS), "training_info": (None, _DOWNLOADS), "remove_training": (None, _DOWNLOADS),
	"downloads_info": (None, _DOWNLOADS), "coach": (None, _COACH),
	"visionclaw_log": (None, r"\blogs?\b"),
	"update_visionclaw": (None, r"\b(updates?|upgrade|versions?|up to date|newer|latest)\b"),
	"visionclaw_models": (None, r"\b(models?|qwen|llms?|ai|a\.i\.)\b"),
	"model_advice": (None, r"\b(models?|qwen|llms?|ai|a\.i\.|quants?)\b"),
	"inside_nvda": (None, _DEVELOPER), "audit_nvda": (None, _DEVELOPER), "object_facts": (None, _DEVELOPER),
	"list_made": (None, _MADE), "remove_made": (None, _MADE), "fix_addon": (None, _MADE), "save_addon": (None, _MADE),
	"addon_question": (None, r"\badd-?ons?\b"),
	"make_hotkey": (None, r"\b(hot ?keys?|shortcuts?|keys?|buttons?)\b"),
	"name_button": (None, r"\b(name|label|call|unlabell?ed|unnamed)\b"),
	"undo_change": (None, _CHANGES), "list_changes": (None, _CHANGES),
	"program_settings": (None, _PROFILES), "remove_program_settings": (None, _PROFILES),
	"voice_info": (None, _VOICE), "get_voice": (None, _VOICE), "remove_voice": (None, _VOICE),
	"own_voice": (None, r"\b(voice|pitch)\b"),
	"switch_driver": (None, _DRIVERS), "nvda_info": (None, _DRIVERS),
	"check_access": (None, _ACCESS), "fix_access": (None, _ACCESS), "add_fix": (None, _ACCESS),
	"drag": (None, r"\b(drag\w*|sliders?|drop)\b"),
	"work_control": (None, r"\b(dials?|knobs?|faders?|sliders?|levers?|arrow keys?|dragg\w*)\b"),
	"scroll": (None, r"\b(scroll\w*|wheel|zoom\w*)\b"), "keyboard_mouse": (None, _POINTER),
	"open_thing": (None, r"\b(open|launch|start|run|go|bring|show|take|load|fire|double[- ]click)\b"),
	"window": (None, r"\b(switch|close|quit|exit|minimi[sz]e|maximi[sz]e|restore|windows?|bring|desktop)\b"),
	"files": (None, r"\b(files?|folders?|documents?|downloads?|pictures|photos|music|videos?|desktop|pdfs?|newest|find|where)\b"),
	"computer_info": (None,
		r"\b(disk|disc|drives?|space|storage|memory|ram|processor|cpu|computer|pc|laptop|network|internet|online|"
		r"running|up ?time|ip)\b"),
}


def opened(name, text, facts, before):
	"""Whether a gated kind of request is opened by where the user is, by the part before, or by the words."""
	fact, words = GATES[name]
	# A fact that could not be found out is unknown, and unknown hides nothing.
	if fact is not None and facts.get(fact, True) is True:
		return True
	if fact == WEB and before in _OPENS_WEB:
		return True
	return bool(words and re.search(words, text))


def route(part, names, facts=None, before=None, hinted=(), needs=None):
	"""The kinds of request a model is offered for one part, in the order of names.
	facts: where the user is ({WEB: True, ...}); before: the recipe of the part before this one;
	hinted: every recipe a pattern of the planner finds in the words, which is always offered;
	needs: {recipe: function(part)} for recipes whose tool reads everything from the words; such a recipe is
	offered only when its function finds what the tool needs."""
	facts, needs = facts or {}, needs or {}
	text = " ".join(str(part or "").lower().split())
	hinted = set(hinted)
	offered = []
	for name in names:
		if name in needs:
			if needs[name](part) is not None:
				offered.append(name)
		elif name in hinted or name not in GATES or opened(name, text, facts, before):
			offered.append(name)
	return offered


def closed(names, offered):
	"""The kinds of request that were left out, for the log."""
	kept = set(offered)
	return [name for name in names if name not in kept]


def tools(toolNames, recipes, offered, always=()):
	"""The tools a model may use in a plan it writes itself: those of the kinds of request it was offered, and
	those no kind of request uses, which nothing can be said against. recipes: {name: (label, text, tools)}."""
	open_ = set(always)
	gated = set()
	for name, recipe in recipes.items():
		(open_ if name in offered else gated).update(recipe[2])
	return [name for name in toolNames if name in open_ or name not in gated]


def offeredText(count, total):
	"""One sentence for the user's log about how many kinds of request were there to choose from."""
	if count >= total:
		return ""
	return f"Offered for this: {count} of {total} kinds of request, those that fit where you are and what you said."
