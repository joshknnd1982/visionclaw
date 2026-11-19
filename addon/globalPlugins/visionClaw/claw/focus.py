# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - questions about the object the user is on: the focused control, the place in a web page in browse
# mode, the navigator object, what is under the mouse pointer. The owner asked on 2026-11-19 "what is the current
# focused control", and VisionClaw said it was not sure and asked whether to look at the screen or run an NVDA
# command: the words "tell me ... focused" had set off the pattern for NVDA's commands, the model had chosen a
# picture, and the two were put to the user. Of 25 such questions in the fifth evaluation set (tests/eval), the model
# chose a way that answers them 1 time. The owner then said: "you must make visionclaw more confident in all kinds of
# all possible situations".
#
# So plain code reads from the user's own words that such a question is asked (wish), about which object, and what
# about it: what it is, what it does, its state, its keys, what it looks like, or everything. The answer is NVDA's
# own facts about that object, in plain words, starting with the answer (answer), and how it is worked from the
# keyboard (useText), from the kind NVDA says it is. A model is asked only for what NVDA does not know: a name for an
# object without one, from its picture, and what a button probably does where nothing says it; both are said to be a
# model's guess. No NVDA imports.

import re

from . import computer

FOCUS, BROWSE, NAVIGATOR, MOUSE = "focus", "browse", "navigator", "mouse"
WHAT, DOES, STATE, KEYS, LOOKS, ALL = "what", "does", "state", "keys", "looks", "all"
# Where a name for an object without one came from: the user named it, it was saved before (object names), or the
# model that sees read it from its picture now.
BY_YOU, SAVED, PICTURE = "you", "saved", "picture"
_NAMED = {
	BY_YOU: ("you named it \"{name}\"", "you named it \"{name}\""),
	SAVED: ("its saved name is \"{name}\"", "its saved name is probably \"{name}\""),
	PICTURE: ("its picture shows the name \"{name}\"", "from its picture it is probably \"{name}\""),
}
# NVDA's own commands that say this object, by their script's name in NVDA (tests/nvda_commands.json): their keys are
# read from the running NVDA and told for next time, so that a person new to NVDA learns them.
NEXT_TIME_SCRIPTS = {FOCUS: "reportCurrentFocus", NAVIGATOR: "navigatorObject_current", MOUSE: "moveNavigatorObjectToMouse"}
_NEXT_TIME = {
	FOCUS: "Next time, {keys} says what has the focus.",
	NAVIGATOR: "Next time, {keys} says the navigator object.",
	MOUSE: "Next time, {keys} moves the navigator object to what is under the mouse and says it.",
}
# Kinds that only hold text: in browse mode the user is on what holds them, a link or a button.
_PLAIN_TEXT = ("STATICTEXT", "TEXTFRAME", "PARAGRAPH", "SECTION", "UNKNOWN", "GROUPING", "LABEL", "CAPTION")


def isPlainText(role):
	return role in _PLAIN_TEXT

# The kinds of thing a person may be on. Not a window, a dialog, a page or the screen: those are read or described
# as a whole ("what does this dialog say" is its text). Not a picture: "what's in this picture" is the picture.
_THING = (
	r"(?:control|object|item|element|button|toggle button|field|edit ?(?:box|field|control|area)?|text ?(?:box|field|area)|"
	r"input|check ?box|checkbox|tick ?box|radio ?button|option button|link|icon|tab|list ?(?:box|item|view)?|menu ?(?:item|button)?|"
	r"combo ?box|drop[- ]?down(?: list| box| menu)?|slider|switch|toggle|spin ?(?:box|button)|entry|thing|widget|cell|row|"
	r"node|tree ?(?:item|view)?|heading|label|setting|choice|option|selection|box)")
_THINGS = re.compile(rf"\b{_THING}s?\b", re.IGNORECASE)
# Words that say which object is meant: the focus, what is selected or highlighted, "this button", where the user is.
_ON_FOCUS = (
	r"\bfocus(?:ed|sed)?\b(?! (?:mode|highlight|ring|follows|tracking|sound|beep|assist))",
	r"\b(?:currently|now|presently)\s+(?:selected|highlighted|focused|active|chosen)\b",
	r"\b(?:selected|highlighted|focused|active|current|chosen)\s+(?:\w+\s+)?" + _THING + r"s?\b",
	r"\b(?:what|which|whats|what's)\s+(?:\w+\s+){0,2}(?:is|are|'s)\s+(?:currently\s+|now\s+|being\s+)?(?:selected|highlighted|focused|active)\b",
	r"\bwhat(?:'s| is|s)?\s+(?:currently\s+)?(?:selected|highlighted)\b",
	r"\b(?:this|that)\s+(?:\w+\s+)?" + _THING + r"s?\b",
	r"\b(?:the\s+)?" + _THING + r"\s+(?:that\s+)?(?:i'?m|i am|im)\s+(?:on|at|in|sitting on|stuck on)\b",
	r"\bwhat\s+(?:" + _THING + r"\s+)?(?:am\s+i|i'?m|i am)\s+(?:on|at|focused on|sitting on|stuck on)\b",
	r"\bwhat\s+" + _THING + r"\s+(?:am\s+i|i'?m|i am)\s+in\b",
	r"\b(?:i'?m|i am|im)\s+(?:on|at|sitting on|stuck on)\s+(?:something|a\s+\w+|an\s+\w+)\b",
	r"\b(?:where(?:'s| is)?|what(?:'s| is)?)\s+(?:the|my)\s+focus\b",
	r"\bif i (?:press|hit|push|activate)\s+(?:enter|return|space|the space ?bar|it|this)\b(?:\s+(?:here|now|on (?:it|this)))?",
	r"\bwhat(?:'s| is| are)?\s+(?:it|this|that)\s+(?:\w+\s+){0,2}for\b",
	r"\b(?:what|which)\s+(?:kind|sort|type)\s+of\s+" + _THING + r"\s+is\s+(?:this|that|it)\b",
	r"\b(?:what|which)\s+" + _THING + r"\s+is\s+(?:this|that)\b",
)
_ON_NAVIGATOR = r"\bnavigator(?: object)?\b"
_ON_MOUSE = (
	r"\b(?:under|below|beneath|at)\s+(?:the|my)\s+(?:mouse|pointer|mouse pointer|mouse cursor)\b",
	r"\b(?:mouse|pointer)\s+(?:is\s+)?(?:on|over|pointing (?:at|to)|hovering over)\b")
# The words must ask something: a question, or "tell me", "explain", "describe", "give me".
_ASKS = re.compile(
	rf"^\W*{computer._POLITE}(?:(?:and|so|but|also|ok|okay|hey|um|uh)\W+)*"
	r"(?:what|which|whats|what's|who|where|is|are|does|do|did|will|would|has|have|can|could|tell|explain|describe|give me|identify|"
	r"name|say|ask|i want to know|i'd like to know|i would like to know|do you know|any idea|info|details|status|state|"
	r"check (?:if|whether|what|and see|to see))\b"
	r"|\b(?:what|which|whats|what's|is it|are they)\b.{0,80}\??\s*$|\?\s*$", re.IGNORECASE)
# Words that ask for something to be done to the object, or that are about something else with the same words.
_NOT = re.compile(
	r"^\W*(?:please\s+)?(?:(?:can|could|would|will) you\s+)?(?:please\s+)?(?:click|double[- ]?click|right[- ]?click|press|push|tap|"
	r"activate|type|enter|write|fill|name|rename|label|call|move|put|go|open|close|select|choose|pick|tick|uncheck|toggle|turn|"
	r"set|change|drag|scroll|copy|cut|paste|delete|remove|clear|read|focus on|find|search|make|create|add|"
	r"switch|expand|collapse|hover|zoom|stop|start|run|show me how|teach|remember|forget|save|undo)\b"
	# "Read me what's selected" is NVDA's own command that reads the selected text; "which program has the focus" is
	# the program, not a control in it.
	r"|\b(?:program|app|application|window|game|browser)\s+(?:has|had|is in|gets)\s+(?:the\s+)?focus\b"
	# A question with something to do after it is two things: "what's focused, then click it".
	r"|(?:\band\b|\bthen\b|,|;)\s+(?:then\s+)?(?:please\s+)?(?:click|double[- ]?click|right[- ]?click|press|push|tap|activate|"
	r"type|open|close|select|choose|uncheck|tick|toggle|turn|set|change|name|rename|label|move|go|read|drag|scroll|"
	r"switch|delete|remove|copy)\b"
	r"|^\W*(?:please\s+)?(?:(?:can|could) you\s+)?(?:tell me\s+)?how (?:do|can|would|should|could|might|to|does one)\b"
	r"|^\W*(?:please\s+)?check\s+(?!if\b|whether\b|what\b|and see\b|to see\b)"
	r"|\bfocus (?:mode|highlight|ring|tracking|follows)\b|\bbrowse mode\b"
	r"|\b(?:window class|class name|control id|window handle|hwnd|process id|automation id|coordinates|pixels|python class|"
	r"nvda'?s class|attributes|properties|property|iaccessible|msaa|uia|ui automation|api|role)\b"
	r"|\b(?:picture|image|photo|screenshot|screen|window|dialog|page|web ?site|site|document|desktop wallpaper)\b"
	r"(?!\s+(?:button|link|item|icon|field|control|check ?box|tab))(?=.*\b(?:say|show|shows|contain|in it|on it|look)\b)",
	re.IGNORECASE)
# What is asked about the object.
_DOES = re.compile(
	r"\bwhat\s+(?:does|do|will|would|can|could)\s+(?:it|this|that|they|the\s+[\w ]{1,30}?)\s+(?:\w+\s+)?do\b"
	r"|\bwhat(?:'s| is| are)?\s+(?:it|this|that|they|the\s+[\w ]{1,30}?)\s+(?:\w+\s+){0,2}for\b"
	r"|\bwhat happens\b|\bwhat (?:will|would) happen\b|\bpurpose\b|\bwhat(?:'s| is) the point\b|\bwhat (?:is|are) .{0,40}\bused for\b"
	r"|\bwhat\b.{0,30}\bdoes\b.{0,30}\bdo\b", re.IGNORECASE)
_LOOKS = re.compile(r"\blooks? like\b|\bcolou?rs?\b|\bwhat does it look\b|\bdescribe\b|\bappearance\b|\bshape\b|\bicon look", re.IGNORECASE)
_KEYS = re.compile(
	r"\b(?:shortcut|short cut|hot ?key|access key|accelerator|keyboard key|key for it|keystroke|key (?:to|for) (?:it|this|that))\b",
	re.IGNORECASE)
_ALL = re.compile(r"\b(?:everything|all about|all (?:the )?(?:info|information|details)|details|info|information|facts|more)\b",
	re.IGNORECASE)
_YES_NO = re.compile(r"^\W*(?:please\s+)?(?:is|are|isn't|aren't|was|has|does|did|can|check (?:if|whether))\b", re.IGNORECASE)
# A state asked about with yes or no: (its words, the states that make the answer yes, whether the answer is yes when
# none of those states is there). "Is this checkbox checked": yes when CHECKED is among the states; "is it enabled":
# yes when UNAVAILABLE is not. Read top to bottom: "not checked" before "checked".
STATE_WORDS = (
	(r"\b(?:un ?checked|unticked|not checked|not ticked|unmarked)\b", ("CHECKED", "HALFCHECKED"), True),
	(r"\bhalf[- ]?checked\b|\bpartly checked\b|\bindeterminate\b|\bmixed\b", ("HALFCHECKED", "INDETERMINATE"), False),
	(r"\b(?:checked|ticked|marked|check ?marked)\b", ("CHECKED",), False),
	(r"\b(?:turned off|switched off|is (?:it|this|that)(?: \w+)? off|not pressed|unpressed)\b", ("PRESSED", "ON", "CHECKED"), True),
	(r"\b(?:turned on|switched on|is (?:it|this|that)(?: \w+)? on|pressed|toggled|active)\b", ("PRESSED", "ON", "CHECKED"), False),
	(r"\b(?:collapsed|closed)\b", ("COLLAPSED",), False),
	(r"\b(?:expanded|opened|open)\b", ("EXPANDED",), False),
	(r"\b(?:disabled|greyed(?: out)?|grayed(?: out)?|dimmed|unavailable)\b", ("UNAVAILABLE",), False),
	(r"\b(?:enabled|available|usable)\b", ("UNAVAILABLE",), True),
	(r"\b(?:required|mandatory)\b", ("REQUIRED",), False),
	(r"\bread[- ]?only\b", ("READONLY",), False),
	(r"\b(?:editable|can i type)\b", ("READONLY",), True),
	(r"\bvisited\b", ("VISITED",), False),
	(r"\b(?:selected|chosen)\b", ("SELECTED",), False),
	(r"\b(?:busy|loading)\b", ("BUSY",), False),
	(r"\b(?:invalid|wrong)\b", ("INVALID_ENTRY",), False),
)
# A state asked about as one of two: "is it on or off". Answered with the one it is, without yes or no.
_EITHER = re.compile(r"\b(?:on or off|off or on|checked or (?:not|un ?checked)|open or closed|expanded or collapsed)\b", re.IGNORECASE)
_STATE = re.compile(r"\b(?:state|status|on or off|checked|ticked|turned on|turned off|pressed|expanded|collapsed|disabled|enabled|"
	r"greyed|grayed|unavailable|required|read[- ]?only|visited|selected or not)\b", re.IGNORECASE)

# What NVDA's states are, said to the user. States that say nothing to a person are left out (FOCUSED, FOCUSABLE,
# SELECTABLE, CHECKABLE, CLICKABLE, EDITABLE on a field, OFFSCREEN, INVISIBLE, DEFUNCT and the like).
_STATE_SAID = {
	"CHECKED": "checked", "HALFCHECKED": "half checked", "INDETERMINATE": "half checked", "PRESSED": "pressed",
	"HALF_PRESSED": "half pressed", "ON": "on", "EXPANDED": "expanded", "COLLAPSED": "collapsed", "SELECTED": "selected",
	"UNAVAILABLE": "unavailable (greyed out)", "READONLY": "read only", "REQUIRED": "required", "INVALID_ENTRY": "marked as not valid",
	"BUSY": "busy", "VISITED": "visited", "HASPOPUP": "it opens a menu or list", "HASPOPUP_DIALOG": "it opens a dialog",
	"HASPOPUP_GRID": "it opens a grid", "HASPOPUP_LIST": "it opens a list", "HASPOPUP_TREE": "it opens a tree",
	"PROTECTED": "protected", "MULTILINE": "multi line", "MODAL": "modal", "AUTOCOMPLETE": "it suggests as you type",
	"SORTED_ASCENDING": "sorted ascending", "SORTED_DESCENDING": "sorted descending", "PINNED": "pinned", "HASNOTE": "has a note",
	"HASCOMMENT": "has a comment", "HASFORMULA": "has a formula", "DRAGGABLE": "can be dragged", "MULTISELECTABLE":
	"more than one item can be selected", "LINKED": "", "INTERNAL_LINK": "it leads to another place on this page",
}
_CHECKS = ("CHECKBOX", "CHECKMENUITEM", "TOGGLEBUTTON", "SWITCH")
# How each kind of control is worked with the keyboard, as Windows and NVDA work it. Keys of Windows and of NVDA are
# said as they are.
_USE = {
	"BUTTON": "Press Space or Enter to press it.",
	"TOGGLEBUTTON": "Press Space or Enter to switch it.",
	"SPLITBUTTON": "Press Space or Enter to press it; Alt+Down Arrow often opens its other choices.",
	"MENUBUTTON": "Press Space or Enter to open its menu, then the arrow keys to move in it.",
	"DROPDOWNBUTTON": "Press Space or Enter, or Alt+Down Arrow, to open it.",
	"CHECKBOX": "Press Space to check or uncheck it.",
	"CHECKMENUITEM": "Press Enter to check or uncheck it.",
	"RADIOBUTTON": "Use the arrow keys to choose another option of its group.",
	"RADIOMENUITEM": "Press Enter to choose it.",
	"SWITCH": "Press Space to turn it on or off.",
	"EDITABLETEXT": "Type to write in it; the arrow keys move through its text.",
	"PASSWORDEDIT": "Type to write in it; what is typed is not read out.",
	"COMBOBOX": "Use the Up and Down Arrow keys to choose another item; Alt+Down Arrow opens its list.",
	"LINK": "Press Enter to follow it.",
	"LIST": "Use the Up and Down Arrow keys to move between its items.",
	"LISTITEM": "Use the Up and Down Arrow keys to move to the other items; Enter usually opens or uses this one.",
	"MENUITEM": "Press Enter to choose it; Escape closes the menu.",
	"MENU": "Use the Up and Down Arrow keys to move in it, Enter to choose, Escape to close it.",
	"MENUBAR": "Use the Left and Right Arrow keys to move between its menus, and Enter or Down Arrow to open one.",
	"TAB": "Use the Left and Right Arrow keys to move to another tab.",
	"TABCONTROL": "Use the Left and Right Arrow keys to move to another tab.",
	"TREEVIEWITEM": "Use the Up and Down Arrow keys to move between items, Right Arrow to open a branch and Left Arrow to close it.",
	"TREEVIEW": "Use the Up and Down Arrow keys to move between items, Right Arrow to open a branch and Left Arrow to close it.",
	"SLIDER": "Use the arrow keys to change its value.",
	"SPINBUTTON": "Use the Up and Down Arrow keys to change its value, or type a number.",
	"SCROLLBAR": "Use the arrow keys to move it.",
	"TABLECELL": "Use NVDA's Control+Alt with the arrow keys to move between cells.",
	"TABLE": "Use NVDA's Control+Alt with the arrow keys to move between cells.",
	"DATAGRID": "Use the arrow keys to move between cells.",
	"DOCUMENT": "Use the arrow keys to read it.",
	"TERMINAL": "Type commands; NVDA reads what comes out.",
	"ICON": "Press Enter to open it.",
}
# Kinds whose own name says what they do when pressed: their name is the plain answer to "what does it do".
_PRESSED = ("BUTTON", "TOGGLEBUTTON", "SPLITBUTTON", "MENUBUTTON", "DROPDOWNBUTTON", "MENUITEM", "LINK", "ICON", "LISTITEM",
	"TAB", "TREEVIEWITEM", "CHECKMENUITEM", "RADIOMENUITEM")
# What pressing Enter or Space does, by kind, said for "what happens if I press Enter here".
_ENTER = {
	"BUTTON": "pressing Enter or Space presses {thing}",
	"TOGGLEBUTTON": "pressing Space or Enter switches {thing}",
	"MENUBUTTON": "pressing Enter or Space opens the menu of {thing}",
	"SPLITBUTTON": "pressing Enter or Space presses {thing}",
	"DROPDOWNBUTTON": "pressing Enter or Space opens {thing}",
	"LINK": "pressing Enter follows {thing}",
	"MENUITEM": "pressing Enter chooses {thing}",
	"CHECKBOX": "pressing Space checks or unchecks {thing}; Enter usually presses the dialog's default button",
	"RADIOBUTTON": "Enter usually presses the dialog's default button; the arrow keys choose another option",
	"LISTITEM": "pressing Enter usually opens or uses {thing}",
	"ICON": "pressing Enter opens {thing}",
	"TREEVIEWITEM": "pressing Enter usually opens or uses {thing}",
	"EDITABLETEXT": "in a one-line field, pressing Enter usually sends the form or does what the field is for; in a multi-line field it starts a new line",
	"COMBOBOX": "pressing Enter usually confirms the item that is chosen",
	"TAB": "pressing Enter or Space shows {thing}",
}


def _search(patterns, text):
	return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def objectOf(part):
	"""Which object the words are about: the navigator object, what is under the mouse, or the focus; None when the
	words name none of them."""
	text = computer.own(part).lower()
	if re.search(_ON_NAVIGATOR, text):
		return NAVIGATOR
	if _search(_ON_MOUSE, text):
		return MOUSE
	if _search(_ON_FOCUS, text):
		return FOCUS
	return None


def wish(part):
	"""What a request asks about the object the user is on, or None when it asks no such thing:
	{"object": FOCUS, NAVIGATOR or MOUSE, "asks": a set of WHAT, DOES, STATE, KEYS, LOOKS, ALL, "state": the state asked
	about or None}. Narrow by design: anything that asks for something to be done, a how-question, a setting, a
	technical fact (left to object_facts), and a picture, window or page as a whole are None."""
	said = " ".join(computer.own(part).split())
	if not said or len(said) > 220:
		return None
	text = said.lower().replace("’", "'")
	if _NOT.search(text) or not _ASKS.search(text):
		return None
	which = objectOf(text)
	if which is None:
		return None
	asks = set()
	if _DOES.search(text):
		asks.add(DOES)
	if _LOOKS.search(text):
		asks.add(LOOKS)
	if _KEYS.search(text):
		asks.add(KEYS)
		# "What's the shortcut key for this button" asks for its key, not what it is for.
		if not re.search(r"\bdo(?:es)?\b|\bhappens?\b|\bpurpose\b", text):
			asks.discard(DOES)
	if _ALL.search(text):
		asks.add(ALL)
	state = stateAsked(text)
	if state is not None or _STATE.search(text):
		asks.add(STATE)
	# "Describe the focused control" asks what it is too; only how it looks, as "what colour is this button", is the
	# picture's, and describing the picture is another job.
	if re.search(r"\bdescribe\b", text):
		asks.add(WHAT)
	if asks == {LOOKS}:
		return None
	if not asks:
		asks.add(WHAT)
	return {"object": which, "asks": asks, "state": state}


def stateAsked(text):
	"""The state a yes-or-no question asks about, as (its words, the states that make the answer yes, whether the
	answer is yes when none of them is there), or None. A question that asks which of two ("on or off") is no yes-or-no
	question: the states line answers it."""
	text = str(text or "").lower()
	if not _YES_NO.search(text) or _EITHER.search(text):
		return None
	for pattern, states, absentYes in STATE_WORDS:
		found = re.search(pattern, text, re.IGNORECASE)
		if found:
			return (found.group(0), tuple(states), absentYes)
	return None


def yesNo(state, states):
	"""Yes or No for a state asked about (stateAsked), from NVDA's states."""
	_words, wanted, absentYes = state
	there = any(s in (states or ()) for s in wanted)
	return "No." if there == absentYes else "Yes."


def stateWords(states, role=""):
	"""NVDA's states as words a person uses, the ones that say something."""
	said = []
	for state in states or ():
		word = _STATE_SAID.get(state, "")
		if state == "EDITABLE" or not word or word in said:
			continue
		said.append(word)
	if role in _CHECKS and "CHECKED" not in states and "HALFCHECKED" not in states and "PRESSED" not in states \
			and "ON" not in states and "INDETERMINATE" not in states:
		said.insert(0, "not checked" if role in ("CHECKBOX", "CHECKMENUITEM") else "off")
	return said


def useText(role, states=()):
	"""How the object is worked from the keyboard, from its kind; "" for a kind that says nothing."""
	if "UNAVAILABLE" in (states or ()):
		return "It is unavailable now, so pressing it does nothing."
	return _USE.get(role, "")


def kindName(facts):
	"""Its kind and name as a person says it: button "Menu"."""
	kind = facts.get("roleText") or "control"
	name = facts.get("name") or ""
	return f"{kind} \"{name}\"" if name else kind


def _lead(facts, which):
	place = []
	if facts.get("title"):
		place.append(f"in the window \"{facts['title']}\"")
	if facts.get("app"):
		place.append(f"of the program {facts['app']}")
	where = (" " + " ".join(place)) if place else ""
	what = kindName(facts)
	if which == BROWSE:
		return f"In browse mode, the reading position is on the {what}{where}."
	if which == NAVIGATOR:
		return f"The navigator object is the {what}{where}."
	if which == MOUSE:
		return f"The mouse pointer is over the {what}{where}."
	return f"The focus is on the {what}{where}."


def _sentence(text):
	text = " ".join(str(text or "").split())
	if not text:
		return ""
	text = text[:1].upper() + text[1:]
	return text if text[-1] in ".!?" else text + "."


def answer(facts, want, which=FOCUS):
	"""What is said about the object, from NVDA's facts (a dict the add-on makes): it starts with the answer, then what
	was asked, then how it is worked. facts: name, role, roleText, value, description, states, shortcut, position
	(index, count, level), inside, app, title, selection, named (a name for an object without one: (name, sure,
	from where)), does (a model's guess of what it does), looks (a model's description of its picture)."""
	want = want or {"asks": {WHAT}, "state": None}
	asks = set(want.get("asks") or {WHAT})
	role = facts.get("role") or ""
	states = list(facts.get("states") or ())
	name = facts.get("name") or ""
	lines = []
	state = want.get("state")
	if state is not None:
		lines.append(yesNo(state, states))
	lines.append(_lead(facts, which))
	named = facts.get("named")
	if not name:
		own = f" (NVDA says only \"{facts['vagueName']}\")" if facts.get("vagueName") else ""
		if named and named[0]:
			guess, sure, source = named
			certain, probable = _NAMED.get(source, _NAMED[PICTURE])
			lines.append(f"It has no name of its own{own}; " + (certain if sure else probable).format(name=guess) + ".")
		else:
			lines.append(f"It has no name of its own{own}, and none could be found for it.")
	said = stateWords(states, role)
	if said:
		lines.append("It is " + ", ".join(said) + ".")
	elif STATE in asks:
		lines.append("NVDA reports no state for it, such as checked, pressed or expanded.")
	if facts.get("value") and facts["value"] != name:
		lines.append(f"Its value is: {facts['value']}.")
	if facts.get("selection"):
		lines.append(f"The selected text is: {facts['selection']}.")
	position = facts.get("position") or {}
	if position.get("index"):
		place = f"It is {position['index']} of {position['count']}" if position.get("count") else f"It is number {position['index']}"
		if position.get("level"):
			place += f", level {position['level']}"
		lines.append(place + ".")
	if facts.get("inside") and (ALL in asks or WHAT in asks):
		lines.append(f"It is inside the {facts['inside']}.")
	description = facts.get("description") or ""
	if description and description != name:
		lines.append(f"It says of itself: {_sentence(description)}")
	if DOES in asks:
		lines.append(doesText(facts, description))
	if KEYS in asks or ALL in asks or facts.get("shortcut"):
		if facts.get("shortcut"):
			lines.append(f"Its own shortcut key is {facts['shortcut']}.")
		elif KEYS in asks:
			lines.append("It has no shortcut key of its own.")
	use = useText(role, states)
	# What pressing it does was said already for "what does it do".
	if use and not (DOES in asks and role in _ENTER and "UNAVAILABLE" not in states):
		lines.append(use)
	if facts.get("looks"):
		lines.append(f"What its picture shows, as a model sees it: {_sentence(facts['looks'])}")
	if facts.get("nextTime") and which in _NEXT_TIME:
		lines.append(_NEXT_TIME[which].format(keys=facts["nextTime"]))
	text = " ".join(line for line in lines if line)
	return text


def doesText(facts, description=""):
	"""What pressing the object does, in plain words, by plain code where its kind and name tell it; a model's guess
	(facts["does"]) is said to be one."""
	role = facts.get("role") or ""
	name = facts.get("name") or ""
	enter = _ENTER.get(role, "")
	if "UNAVAILABLE" in (facts.get("states") or ()):
		return "It is unavailable now, so pressing it does nothing until the program makes it available."
	parts = []
	if enter:
		parts.append(_sentence(enter.format(thing=f"the {kindName(facts)}" if name else "it")))
	if facts.get("does") and not description:
		parts.append(f"A guess from its name and picture, which may be wrong: {_sentence(facts['does'])}")
	elif role in _PRESSED and not description and not name:
		parts.append("Nothing tells what it does: it has no name and no description.")
	if not parts:
		if description:
			return "What it does is what its description says."
		return f"Its kind is {facts.get('roleText') or 'not known'}; nothing more about what it does is known."
	return " ".join(parts)


def needsGuess(facts, want):
	"""Whether a model is to be asked what the object probably does: only where the user asked what it does, it is
	something that is pressed, and neither a description nor its kind says it. A link says where it leads."""
	if DOES not in set((want or {}).get("asks") or ()):
		return False
	role = facts.get("role") or ""
	return role in _PRESSED and role != "LINK" and not facts.get("description")


DOES_SYSTEM = (
	"You say in one short sentence what pressing one control of a computer program most likely does, from its kind, its "
	"name, where it is and its picture. Write for a blind person who will hear it. Never describe its colour, its shape "
	"or where it is on the screen. If nothing tells what it does, answer that it is not known.")
DOES_SCHEMA = {"type": "object", "properties": {"does": {"type": "string", "maxLength": 160}}, "required": ["does"]}


def doesQuestion(facts):
	"""The question to the model that sees about what pressing the object does."""
	where = []
	if facts.get("app"):
		where.append(f"the program {facts['app']}")
	if facts.get("title"):
		where.append(f"the window \"{facts['title']}\"")
	if facts.get("inside"):
		where.append(f"inside the {facts['inside']}")
	text = (
		f"The picture shows a {facts.get('roleText') or 'control'}"
		+ (f" named \"{facts['name']}\"" if facts.get("name") else " without a name")
		+ (f", in {', '.join(where)}" if where else "") + ". What does pressing it most likely do?")
	return " ".join(text.split())


def cleanGuess(text, facts):
	"""A model's sentence about what the object does, or "" when it says nothing: it only repeats the name or kind,
	says it is not known, or is too short to tell anything."""
	said = " ".join(str(text or "").split()).strip(" .")
	low = said.lower()
	if len(said) < 8 or re.search(r"\b(?:not known|unknown|cannot tell|can't tell|not sure|no idea|unclear|cannot be determined|"
			r"cannot determine|not possible to)\b", low):
		return ""
	plain = re.sub(r"[^a-z0-9 ]", "", low)
	name = re.sub(r"[^a-z0-9 ]", "", (facts.get("name") or "").lower())
	if plain in (name, (facts.get("roleText") or "").lower()):
		return ""
	return said
