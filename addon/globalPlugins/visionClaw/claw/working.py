# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - how a control is worked. A sighted person sees a control and knows what to do with it: click it,
# type into it, drag it, turn it. Here that knowledge is plain data: what NVDA's own facts about a control say,
# which controls the facts say nothing about (those are shown to the models, one small question each), how the
# two models' answers are settled, what stands in the keyboard's way, and which remedy fits. Also what the
# class of a window says about the toolkit or game engine that draws it.
# No NVDA dependencies. Controls are the plain dictionaries of fixmatch.

import re

CLICK, DOUBLE, RIGHT, TYPE, CHOOSE = "click", "double click", "right click", "type", "open and choose"
UPDOWN, SIDEWAYS, AROUND, DRAG_TO = "drag up and down", "drag sideways", "turn in a circle", "drag to another place"
WHEEL, SHOWS, UNSURE = "mouse wheel", "only shows something", "cannot tell"
WAYS = [CLICK, DOUBLE, RIGHT, TYPE, CHOOSE, UPDOWN, SIDEWAYS, AROUND, DRAG_TO, WHEEL, SHOWS, UNSURE]
# Ways that change a value by moving the mouse: arrow keys can stand in for them.
TURNED = (UPDOWN, SIDEWAYS, AROUND, WHEEL)
PRESSED = (CLICK, DOUBLE, RIGHT)
# What can be done about a control the keyboard does not work.
NOTHING, PRESS_KEY, ARROW_KEYS, ADVICE = "nothing", "press key", "arrow keys", "advice"

_BY_ROLE = {
	"BUTTON": CLICK, "LINK": CLICK, "CHECKBOX": CLICK, "RADIOBUTTON": CLICK, "SWITCH": CLICK, "TOGGLEBUTTON": CLICK,
	"TAB": CLICK, "MENUITEM": CLICK, "LISTITEM": CLICK, "TREEVIEWITEM": CLICK, "TABLECOLUMNHEADER": CLICK,
	"DATAITEM": CLICK, "COLORCHOOSER": CLICK, "ICON": DOUBLE,
	"EDITABLETEXT": TYPE, "PASSWORDEDIT": TYPE, "RICHEDIT": TYPE, "TERMINAL": TYPE, "SPINBUTTON": TYPE,
	"HOTKEYFIELD": TYPE, "DATEEDITOR": TYPE,
	"COMBOBOX": CHOOSE, "MENUBUTTON": CHOOSE, "DROPDOWNBUTTON": CHOOSE, "SPLITBUTTON": CHOOSE,
	"DIAL": AROUND,
}
# Kinds that only hold or show other things. Never shown to a model as something to work.
_PASSIVE = frozenset((
	"STATICTEXT", "PROGRESSBAR", "GROUPING", "SEPARATOR", "HEADING", "PARAGRAPH", "LIST", "TABLE", "TABLECELL",
	"TABLEROW", "DOCUMENT", "SECTION", "LANDMARK", "TITLEBAR", "MENUBAR", "TOOLBAR", "STATUSBAR", "DIALOG",
	"WINDOW", "FRAME", "INTERNALFRAME", "PROPERTYPAGE", "TABCONTROL", "TREEVIEW", "MENU", "POPUPMENU", "TOOLTIP",
	"APPLICATION", "ARTICLE", "REGION", "FORM", "LABEL", "TEXTFRAME", "BLOCKQUOTE", "FOOTER", "HEADER", "ALERT",
	"SCROLLPANE", "SCROLLBAR", "LISTITEM_MARKER", "CAPTION", "TABLEBODY", "TABLEHEADER", "TABLEFOOTER", "ROOTPANE",
	"LAYEREDPANE", "GLASSPANE", "DESKTOPPANE", "OPTIONPANE", "VIEWPORT", "DEFINITION", "TERM", "FIGURE", "MARKED_CONTENT",
))
# Inside these, a control that does not take the focus is as it should be: the title bar's buttons, the
# arrows of a scrollbar, the parts of a combo box.
_INNER = frozenset(("TITLEBAR", "SCROLLBAR", "MENUBAR", "MENU", "POPUPMENU", "COMBOBOX", "SPINBUTTON", "SLIDER", "TOOLTIP"))
_OUT_OF_SIGHT = frozenset(("INVISIBLE", "OFFSCREEN", "UNAVAILABLE"))
MAX_JUDGED = 6
MAX_KEYS_OFFERED = 6

JUDGE_SCHEMA = {
	"type": "object",
	"properties": {"way": {"type": "string", "enum": WAYS}},
	"required": ["way"],
}
# What the vision model is asked about the picture of one control.
VISION_SYSTEM = (
	"You look at a picture of one control from a computer program or game, with a little of what is around it. "
	"You say how a person works it with a mouse. Choose one:\n"
	"click: a button, a link, a box to tick, a tab, an icon that is pressed.\n"
	"double click: a file, a folder or a desktop icon that is opened.\n"
	"right click: something that only opens a menu.\n"
	"type: a field for text or numbers.\n"
	"open and choose: a list that drops down.\n"
	"drag up and down: a slider or fader that stands upright.\n"
	"drag sideways: a slider that lies flat, or a bar that is dragged left and right.\n"
	"turn in a circle: a round dial or knob.\n"
	"drag to another place: a thing that is picked up and dropped somewhere else.\n"
	"mouse wheel: a long list or a view that is scrolled.\n"
	"only shows something: text, a picture or a meter that cannot be worked.\n"
	"cannot tell: the picture does not show what it is."
)
# What the coder model is asked about the facts of one control.
CODER_SYSTEM = (
	"You know how programs and web pages are built. You are given what the screen reader and Windows report "
	"about one control. You say how a person works that control with a mouse. Choose one of: "
	+ ", ".join(WAYS) + ". A slider, range or scrollbar is dragged; a dial or knob is turned in a circle; "
	"something with an invoke, press, click or toggle action is clicked; something that takes text is typed "
	"into; a plain text, image or progress bar only shows something. If the facts do not say, choose cannot tell."
)


def byRole(node, box=None):
	"""How a control is worked, from the kind NVDA says it is, or None when the kind does not say.
	box: its place (left, top, right, bottom), which says which way a slider lies."""
	role = node.get("role") or ""
	if role == "SLIDER":
		if box is not None and box[3] - box[1] > box[2] - box[0]:
			return UPDOWN
		return SIDEWAYS
	return _BY_ROLE.get(role)


_WEB_ROLES = {
	"slider": SIDEWAYS, "scrollbar": UPDOWN, "button": CLICK, "link": CLICK, "checkbox": CLICK, "switch": CLICK,
	"radio": CLICK, "tab": CLICK, "menuitem": CLICK, "option": CLICK, "treeitem": CLICK, "textbox": TYPE,
	"searchbox": TYPE, "spinbutton": TYPE, "combobox": CHOOSE, "listbox": CHOOSE,
}
_PRESS_ACTIONS = ("click", "press", "invoke", "activate", "toggle", "check", "uncheck", "jump", "open", "select")


def byFacts(facts):
	"""How a control is worked, where a deep query says it outright, whatever kind NVDA calls it: a value in a
	range is dragged, an action to press it means it is clicked, a text value that can be changed is typed.
	None when the facts do not say; then the models are asked."""
	box = facts.get("box")
	upright = box is not None and box[3] - box[1] > box[2] - box[0]
	patterns = facts.get("patterns") or ()
	span = facts.get("range")
	if span is not None or "a value in a range" in patterns:
		return UPDOWN if upright else SIDEWAYS
	role = str((facts.get("web") or {}).get("xml-roles") or "").split(" ")[0].lower()
	if role in _WEB_ROLES:
		return UPDOWN if role == "slider" and upright else _WEB_ROLES[role]
	if "expand and collapse" in patterns:
		return CHOOSE
	if "invoke" in patterns or "toggle" in patterns:
		return CLICK
	if any(str(action).lower().startswith(_PRESS_ACTIONS) for action in facts.get("actions") or ()):
		return CLICK
	states = set(facts.get("states") or ())
	if "a value as text" in patterns and not states & {"READONLY", "UNAVAILABLE"}:
		return TYPE
	return None


def telling(facts):
	"""Whether a deep query found anything for the coder model to reason from. A bare window of a game gives
	nothing, and an answer made from nothing would be a guess that sounds like knowledge."""
	return bool(
		facts.get("name") or facts.get("value") or facts.get("actions") or facts.get("patterns") or facts.get("web")
		or facts.get("drawn") or set(facts.get("states") or ()) - {"FOCUSABLE", "FOCUSED"})


def _under(node, roles):
	up = node.get("up")
	for _ in range(40):
		if up is None:
			return False
		if up.get("role") in roles:
			return True
		up = up.get("up")
	return False


def _showing(node):
	return not node.get("hidden") and not _OUT_OF_SIGHT & set(node.get("states") or ())


def survey(nodes, page=False):
	"""What the controls of a window or page are, by how they are worked, from NVDA's facts alone:
	ways       {way: how many controls}
	mouseOnly  controls whose kind says how they are worked but that never take the keyboard focus
	unsure     controls that look worked but whose kind says nothing; these are for the models to look at
	On a web page NVDA's browse mode reaches and presses every link and button itself, so there only
	controls that are dragged count as mouse only."""
	parents = {id(node["up"]) for node in nodes if node.get("up") is not None}
	ways, mouseOnly, unsure = {}, [], []
	for node in nodes:
		if not _showing(node):
			continue
		role = node.get("role") or ""
		states = set(node.get("states") or ())
		way = byRole(node)
		if way is not None:
			ways[way] = ways.get(way, 0) + 1
			if "FOCUSABLE" in states or _under(node, _INNER) or role == "MENUITEM":
				continue
			if not page or way in TURNED:
				mouseOnly.append(node)
			continue
		# Something that only holds or shows other things is not worked, unless the page says it is clicked.
		if "CLICKABLE" not in states and (role in _PASSIVE or id(node) in parents):
			continue
		if _under(node, frozenset(_BY_ROLE) | _INNER):
			continue  # a part of a control that is already counted
		if "CLICKABLE" in states or (not page and ("FOCUSABLE" in states or role in ("GRAPHIC", "CANVAS", "UNKNOWN", "PANE"))):
			unsure.append(node)
	return {"ways": ways, "mouseOnly": mouseOnly, "unsure": unsure}


def waysText(ways):
	"""How many controls are worked in which way, as one sentence, or ""."""
	if not ways:
		return ""
	words = {
		CLICK: "clicked", DOUBLE: "double-clicked", TYPE: "typed into", CHOOSE: "opened to choose from",
		UPDOWN: "dragged up and down", SIDEWAYS: "dragged sideways", AROUND: "turned in a circle",
	}
	parts = [f"{count} {'is' if count == 1 else 'are'} {words[way]}"
		for way, count in sorted(ways.items(), key=lambda pair: (-pair[1], WAYS.index(pair[0]))) if way in words]
	return "Of the controls whose kind NVDA can tell, with a mouse " + ", ".join(parts) + "." if parts else ""


def settle(seen, thought, oneModel=False):
	"""One answer from what the vision model saw in the picture and what the coder model made of the facts.
	Either may be None (not asked, or it failed). Returns (way, whether the two agree, who said so).
	oneModel: one model does both jobs. Its two answers still come from two different things, the picture and
	what is reported, but they are never called the answers of two models."""
	seen = seen if seen in WAYS and seen != UNSURE else None
	thought = thought if thought in WAYS and thought != UNSURE else None
	both = "the model, from the picture and from what is reported" if oneModel else "both models"
	if seen and thought:
		if seen == thought:
			return seen, True, both
		# Both mean a value that is changed by moving the mouse: which way is found out by trying.
		if seen in TURNED and thought in TURNED:
			return seen, True, both
		if oneModel:
			return seen, False, f"the model, from the picture; from what is reported it says {thought}"
		return seen, False, f"the vision model; the coder model says {thought}"
	if seen:
		return seen, False, "the model, from the picture" if oneModel else "the vision model"
	if thought:
		return thought, False, "the model, from what is reported" if oneModel else "the coder model"
	return UNSURE, False, "the model" if oneModel else "neither model"


def remedy(way, focusable):
	"""What can be done for a control that is worked this way."""
	if way in TURNED:
		# A slider that takes the focus is worked with the arrow keys already.
		return NOTHING if focusable else ARROW_KEYS
	if way in PRESSED:
		return NOTHING if focusable else PRESS_KEY
	if way in (TYPE, CHOOSE):
		return NOTHING if focusable else ADVICE
	if way == SHOWS:
		return NOTHING
	return ADVICE


def adviceFor(way):
	return {
		DRAG_TO: "Ask VisionClaw to drag it onto something by name, or pick it up with G in the overlay.",
		TYPE: "Ask VisionClaw to click it, then type.",
		CHOOSE: "Ask VisionClaw to click it, then to list what is in the window.",
	}.get(way, "Pointer mode (NVDA+Alt+K) lets you put the mouse pointer on it and try it.")


# --- What draws a window ---

# The start of a window's class name, the toolkit or engine, and what that means for a screen reader.
_TOOLKITS = (
	("UnityWndClass", "the Unity game engine", "It gives a screen reader nothing unless the game has its own speech."),
	("UnrealWindow", "the Unreal game engine", "It gives a screen reader nothing unless the game has its own speech."),
	("SDL_app", "the SDL library, used by many games", "The whole window is one picture to a screen reader."),
	("GLFW", "the GLFW library, used by games and graphics programs", "The whole window is one picture to a screen reader."),
	("LWJGL", "a Java game library", "The whole window is one picture to a screen reader."),
	("SFML_Window", "the SFML library, used by games", "The whole window is one picture to a screen reader."),
	("AllegroWindow", "the Allegro game library", "The whole window is one picture to a screen reader."),
	("Engine", "a game engine", "The whole window is probably one picture to a screen reader."),
	("JUCE_", "JUCE, used by music programs and plug-ins", "Its dials and sliders are usually dragged up and down, and often reach a screen reader poorly."),
	("Qt", "the Qt toolkit", "Its standard controls can be read; controls a program draws itself often cannot."),
	("SunAwt", "Java", "It can only be read when the Java Access Bridge is turned on."),
	("Chrome_", "the Chromium browser engine, as in Chrome, Edge and Electron programs", "It is read like a web page."),
	("Mozilla", "the Firefox browser engine", "It is read like a web page."),
	("HwndWrapper", "Windows Presentation Foundation", "It is read through UI Automation; controls a program draws itself need the program's help."),
	("Windows.UI.Core.CoreWindow", "a modern Windows app", "It is read through UI Automation."),
	("ApplicationFrameWindow", "a modern Windows app", "It is read through UI Automation."),
	("FLUTTER", "the Flutter toolkit", "It can be read when its accessibility support is switched on by the program."),
	("TkTopLevel", "the Tk toolkit", "It gives a screen reader very little; it is best worked from its picture."),
	("TkChild", "the Tk toolkit", "It gives a screen reader very little; it is best worked from its picture."),
	("wxWindow", "the wxWidgets toolkit", "Its standard controls can be read."),
	("gdkWindow", "the GTK toolkit", "It gives a screen reader on Windows very little."),
	("Afx:", "Microsoft Foundation Classes", "Its standard controls can be read; controls it draws itself cannot."),
	("ThunderRT", "Visual Basic 6", "Its standard controls can be read; picture controls cannot."),
	("WindowsForms", "Windows Forms", "Its standard controls can be read."),
	("TForm", "Delphi", "Its standard controls can be read; many of its own controls are only partly reported."),
	("ConsoleWindowClass", "the Windows console", "Its text can be read."),
)


def toolkitOf(windowClass, framework=""):
	"""(what draws this window, what that means), from the class of the window, or ("", "")."""
	text = str(windowClass or "")
	for start, name, meaning in _TOOLKITS:
		if text.startswith(start):
			return name, meaning
	known = {"WPF": "Windows Presentation Foundation", "XAML": "a modern Windows app", "Win32": "plain Windows controls",
		"WinForm": "Windows Forms", "DirectUI": "Windows' own DirectUI", "Qt": "the Qt toolkit"}
	if framework in known:
		return known[framework], ""
	return "", ""


# --- Facts in sentences ---

def factsText(facts):
	"""What a deep query of one control found, in plain sentences: for the user, and for the coder model."""
	lines = []
	kind = facts.get("roleText") or facts.get("role") or "control"
	name = facts.get("name")
	lines.append(f"It is reported as: {kind}" + (f", called {name}." if name else ", with no name."))
	if facts.get("value"):
		lines.append(f"Its value is {str(facts['value'])[:60]}.")
	states = [state for state in facts.get("states") or () if state]
	if states:
		lines.append("Its states: " + ", ".join(states[:8]).lower() + ".")
	lines.append("It takes the keyboard focus." if facts.get("focusable") else "It does not take the keyboard focus.")
	if facts.get("actions"):
		lines.append("Actions a program can ask of it: " + ", ".join(facts["actions"][:5]) + ".")
	if facts.get("patterns"):
		lines.append("Windows UI Automation offers for it: " + ", ".join(facts["patterns"][:8]) + ".")
	span = facts.get("range")
	if span:
		lines.append(
			f"Its value runs from {span['low']:g} to {span['high']:g} and stands at {span['now']:g}"
			+ (", and cannot be set from outside." if span.get("readOnly") else ", and can be set without the mouse."))
	if facts.get("api"):
		lines.append(f"NVDA reads it through {facts['api']}.")
	web = facts.get("web") or {}
	if web:
		lines.append("In the page's code: " + ", ".join(f"{key} {value}" for key, value in list(web.items())[:6]) + ".")
	if facts.get("windowClass"):
		toolkit, meaning = toolkitOf(facts["windowClass"], facts.get("framework") or "")
		lines.append(
			f"Its window has the class {facts['windowClass']}" + (f", which is {toolkit}. {meaning}".rstrip() if toolkit else "."))
	if facts.get("children"):
		lines.append(f"It has {facts['children']} parts inside it.")
	if facts.get("drawn"):
		lines.append(f"Text drawn in it, from NVDA's off-screen model: {facts['drawn'][:120]}.")
	if facts.get("under") and facts["under"] != (facts.get("role"), facts.get("name")):
		role, underName = facts["under"]
		lines.append(f"At its middle, Windows itself finds: {role.lower()}" + (f" {underName}." if underName else "."))
	return " ".join(line if line.endswith(".") else line + "." for line in lines)


_STRIP = re.compile(r"[^a-z ]")


def wayFrom(answer):
	"""The way a model named, from a form or from loose words, or None."""
	if isinstance(answer, dict):
		answer = answer.get("way")
	text = " ".join(_STRIP.sub(" ", str(answer or "").lower()).split())
	for way in sorted(WAYS, key=len, reverse=True):
		if text == way or text.startswith(way):
			return way
	return None
