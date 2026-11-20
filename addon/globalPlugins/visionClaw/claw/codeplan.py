# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - an add-on written piece by piece: a big request broken into bite-size pieces a model of 1 to 9
# billion parameters can do well.
# The owner said on 2026-11-19: "for coding with visionclaw, build an orchestrator in python that takes a big prompt
# and breaks it down into bite-size pieces a small 1b to 9b model can understand", and that the plan and the pieces
# are fed to the model from temporary Markdown files that are deleted when the job is done.
# How it is done:
#   1. Plain code reads the request into pieces, the way a text adventure reads a command: each piece is one key
#      command or one thing that happens by itself, with what it does in the user's own words. "Say the time with
#      NVDA+alt+T, beep when a link gets the focus, and only in Firefox" is two pieces and one program. The keys, the
#      events, the kinds of control and the program are read by plain code (KEY_WORDS, EVENTS, ROLE_WORDS,
#      APP_NAMES); a model never decides them.
#   2. Plain code writes everything around each piece: the imports, the class, the key or the event, the check for
#      the program and the kind of control, the try and the nextHandler() of an event. A piece whose work is a beep
#      or a fixed sentence is written by plain code too.
#   3. The model writes only the few lines inside one method, fed from that piece's section of the work sheet
#      (claw/worksheet.py) and nothing else: what the piece does, when it runs, the method with the place for its
#      lines, and the notes that fit this piece's own words (bite-size retrieval). The other pieces are never shown.
#   4. Each piece is checked on its own (microaddons.check), corrected on its own, and reviewed on its own by the
#      other model, or by the same model reading it again. The checks decide; the review only advises.
#   5. Plain code puts the pieces together and checks the whole file once more.
# Where plain code cannot read a request into pieces for certain (a timer, NVDA's start, a settings panel, a key
# command whose key is taken twice, a clause that says nothing to do), or a piece cannot be written, the add-on is
# written as one piece by microaddons.write, as before, and the user is told. A fault inside a generated add-on is
# corrected the same way: only the method where it happened is sent to the model (fixMethod).
# No NVDA dependencies.

import ast
import re
import textwrap

from . import debuglog, fixes, microaddons, prompts, understand
from .llm import LLMError, clip, uncut
from .tools import ToolError

KEY, EVENT = "key", "event"
# More pieces than this is no small add-on.
MAX_PIECES = 8
# The lines of one piece. More means the model has lost its way.
MAX_BODY_LINES = 20
# What a piece's notes may take up in its question.
NOTES_CHARS = 900
# The modules a piece may use besides NVDA's own (microaddons.check refuses the dangerous ones).
_STANDARD = ("time", "datetime", "re", "math", "json", "collections", "random", "string")
_NVDA_MODULES = microaddons._MODULES

PIECE_SYSTEM = (
	"You write the lines inside one method of a small NVDA add-on, in Python. VisionClaw has already written the "
	"method itself, the key or event it runs on, the check for the program, the imports and the end of the method. "
	"Answer with only the lines that go inside, in a ```python block, and nothing else.\n"
	"Rules:\n"
	"- Do exactly what this piece asks and nothing more.\n"
	"- Keep it short: 1 to 8 lines.\n"
	"- Speak with ui.message(\"text\"). Beep with tones.beep(frequency, milliseconds).\n"
	"- In an event, obj is the control the event is about. In a key command, get the focused control with "
	"api.getFocusObject().\n"
	"- Compare the kind of a control with controlTypes.Role, never with a text.\n"
	"- Do not write def, class, @script, import, nextHandler() or a check of the program: VisionClaw writes those.\n"
	"- Use only NVDA's modules and these: re, time, datetime, json, math, collections.\n"
	"- Never use subprocess, the internet, eval, exec, open, or anything that deletes or writes files."
)
_REVIEW_SCHEMA = microaddons._REVIEW_SCHEMA
_REVIEW_SYSTEM = (
	"You review one piece of a small NVDA screen reader add-on. Compare the code with what this piece must do. "
	"VisionClaw wrote the method around the lines, the key or event, and the check for the program; judge only "
	"whether the lines do what the piece asks. Say ok=true if they would. Say ok=false only for a real fault: they "
	"do something else, miss a part, or would raise an error. Name the fault in one sentence."
)
_METHOD_SYSTEM = (
	"You correct one method of a small NVDA add-on in Python. Answer with the whole corrected method, its def line "
	"and its decorator included, in a ```python block, and nothing else. Change only what the problem needs."
)


class Fallback(Exception):
	"""The add-on cannot be written piece by piece; it is written as one piece. The message says why."""


class Piece:
	"""One key command or one thing that happens by itself, and what it does."""

	def __init__(self, kind, said, action, gesture="", event="", role="", program="", state=None):
		self.kind = kind
		# For a change of state, the state it must now have or not have: ("CHECKED", True) for "gets checked".
		self.state = state
		# The user's own words for this piece.
		self.said = said
		# What it does, in the user's words, without the words that say when.
		self.action = action
		self.gesture = gesture
		self.event = event
		self.role = role
		self.program = program
		self.chosenKey = False
		self.name = ""
		self.body = ""
		self.imports = set()
		self.plain = False
		self.doubt = ""

	def when(self):
		"""When the piece runs, in plain words."""
		if self.kind == KEY:
			text = f"when the user presses {self.gesture.replace('kb:', '')}"
		else:
			text = _EVENT_WORDS.get(self.event, f"on NVDA's event {self.event}")
			if self.role:
				text += f", only for a {ROLE_SAID.get(self.role, self.role.lower())}"
			if self.state:
				text += f", only when it is {'now' if self.state[1] else 'no longer'} {STATE_SAID.get(self.state[0], self.state[0].lower())}"
		if self.program:
			text += f", only in the program {self.program}"
		return text

	def __repr__(self):
		return f"Piece({self.kind}, {self.gesture or self.event}, {self.role or '-'}, {self.program or '-'}: {self.action!r})"


# --- Reading a request into pieces ---

# Where a key is said: "NVDA+shift+H", "nvda shift h", "control plus alt plus t", "alt f5".
_MODIFIER = r"(?:nvda|control|ctrl|alt|shift|windows)"
_KEYNAME = (r"(?:f(?:1[0-2]|[1-9])|enter|escape|esc|tab|space|backspace|delete|home|end|page ?up|page ?down|"
	r"up ?arrow|down ?arrow|left ?arrow|right ?arrow|numpad ?[0-9]|[a-z0-9])")
_SEP = r"\s*(?:\+|\bplus\b|-|\s)\s*"
_GESTURE = re.compile(rf"\b{_MODIFIER}(?:{_SEP}{_MODIFIER}){{0,3}}{_SEP}{_KEYNAME}\b", re.IGNORECASE)
# Words around a key that only say that it is a key: they are not what the piece does.
_KEY_AROUND = re.compile(
	r"(?:\b(?:when(?:ever)?|if|each time|every time|once)\s+(?:i|you|the user)\s+(?:press|hit|use|type)(?:es)?\s+"
	r"|\b(?:by )?pressing\s+|\bon pressing\s+|\b(?:press|hit)\s+|\b(?:with|using|via|on|bound to|under|assigned to)\s+"
	r"(?:the )?(?:(?:hot ?)?keys?|shortcut|gesture|combination)?\s*|\b(?:the )?(?:hot ?)?keys?\s+|\bshortcut\s+)$",
	re.IGNORECASE)
_KEY_AFTER = re.compile(r"^\s*(?:is pressed|gets pressed|key|keys|hotkey|shortcut)\b", re.IGNORECASE)
# A key command whose key is not named: plain code chooses one that is free (fixes.freeKeys).
_WANTS_KEY = re.compile(r"\b(?:a|an|its own|one|some) (?:key|hot ?key|shortcut|keyboard shortcut|key command)\b"
	r"|\bwhen i press (?:a|its) key\b", re.IGNORECASE)
_WHEN = re.compile(r"\b(?:when(?:ever)?|every time|each time|as soon as|once|if|after|on)\b", re.IGNORECASE)
# What happens by itself, by NVDA's event, in the order they are tried: the narrowest first.
# (event, the words that say it)
EVENTS = (
	("typedCharacter", r"\b(?:type|press|enter|hit)(?:s)? (?:a |any |each |every )?(?:character|letter|key|char)\b"
		r"|\b(?:each|every|any) (?:character|letter|key|char)s? (?:i|you|the user) (?:types?|press(?:es)?)\b|\bas (?:i|you) type\b"),
	("gainFocus", r"\b(?:gets?|gains?|receives?|takes?|has|get) (?:the )?focus\b|\bfocus (?:moves|goes|lands|is moved) (?:to|on|onto)\b"
		r"|\b(?:i|you|the user) (?:move|moves|tab|tabs|arrow|arrows|land|lands|get|gets|go|goes|come|comes) (?:to|on|onto|into)\b"
		r"|\b(?:is|becomes?) focused\b|\b(?:land|lands|arrive|arrives) on\b|\bon focus\b"),
	("foreground", r"\b(?:window|dialog|dialogue|program|app|application) (?:opens|appears|comes (?:up|to the front|to the foreground)"
		r"|pops up|is opened|comes forward)\b|\b(?:i |you )?(?:switch|switches|change|changes) (?:to )?(?:another|a different|a new|the)? ?"
		r"(?:program|window|app|application)s?\b"),
	("nameChange", r"\b(?:name|title|label) (?:of [\w ]{1,30} )?changes?\b|\bchanges? (?:its|the) (?:name|title|label)\b"),
	("valueChange", r"\b(?:value|progress|percentage|percent|level|slider|progress bar|number) (?:of [\w ]{1,30} )?"
		r"(?:changes?|moves?|goes (?:up|down)|updates?|rises|falls|drops)\b"),
	("stateChange", r"\b(?:gets?|becomes?|is|are) (?:checked|unchecked|pressed|selected|unselected|expanded|collapsed|disabled|enabled|busy)\b"
		r"|\bstate (?:of [\w ]{1,30} )?changes?\b"),
	("caret", r"\b(?:cursor|caret|insertion point) moves?\b"),
	("alert", r"\balerts? (?:appears?|shows? up|pops? up|comes? up|is shown)\b|\bthere is an alert\b|\ban alert\b"),
	("liveRegionChange", r"\blive region\b|\b(?:part|section) of (?:the )?(?:page|window) (?:updates?|changes?)\b"),
	("UIA_notification", r"\bnotifications? (?:appears?|comes?|arrives?|is sent|pops? up)\b|\b(?:sends?|gets?|receives?) a notification\b"),
	("show", r"\b(?:appears?|shows? up|pops? up|becomes? visible|is shown)\b"),
)
_EVENTS = tuple((name, re.compile(words, re.IGNORECASE)) for name, words in EVENTS)
# What the event's object is, for the model.
_EVENT_OBJ = {
	"typedCharacter": "obj is the control that was typed in, and ch is the character that was typed.",
	"gainFocus": "obj is the control that got the focus.",
	"foreground": "obj is the window that came to the front.",
	"nameChange": "obj is the control whose name changed.",
	"valueChange": "obj is the control whose value changed.",
	"stateChange": "obj is the control whose state changed.",
	"caret": "obj is the text control in which the cursor moved.",
	"alert": "obj is the alert.",
	"liveRegionChange": "obj is the part that changed.",
	"UIA_notification": "obj is the control that sent it, and displayString is what the notification says.",
	"show": "obj is what appeared.",
}
_EVENT_WORDS = dict(microaddons._EVENT_WORDS, UIA_notification="when a program sends a notification")
# What an event's method takes after (self, obj, nextHandler).
_EVENT_ARGS = {"typedCharacter": ", ch=None", "UIA_notification": ", displayString=None, **kwargs"}
# A change of state as people say it, and NVDA's state with whether the control has it now (controlTypes.State).
STATES = (
	("unchecked", ("CHECKED", False)), ("checked", ("CHECKED", True)), ("ticked", ("CHECKED", True)),
	("unticked", ("CHECKED", False)), ("unpressed", ("PRESSED", False)), ("pressed", ("PRESSED", True)),
	("unselected", ("SELECTED", False)), ("deselected", ("SELECTED", False)), ("selected", ("SELECTED", True)),
	("expanded", ("EXPANDED", True)), ("opened", ("EXPANDED", True)), ("collapsed", ("COLLAPSED", True)),
	("disabled", ("UNAVAILABLE", True)), ("greyed out", ("UNAVAILABLE", True)), ("grayed out", ("UNAVAILABLE", True)),
	("enabled", ("UNAVAILABLE", False)), ("busy", ("BUSY", True)),
)
STATE_SAID = {"CHECKED": "checked", "PRESSED": "pressed", "SELECTED": "selected", "EXPANDED": "expanded",
	"COLLAPSED": "collapsed", "UNAVAILABLE": "unavailable", "BUSY": "busy"}
_STATE = re.compile(r"\b(?:gets?|becomes?|is|are|was|were|goes)\s+(" + "|".join(re.escape(w) for w, _s in STATES) + r")\b",
	re.IGNORECASE)
# Kinds of control as people say them, and NVDA's names for them (controlTypes.Role, read from NVDA in
# tests/test_working.py). The longer words first.
ROLE_WORDS = (
	("radio button", "RADIOBUTTON"), ("toggle button", "TOGGLEBUTTON"), ("check box", "CHECKBOX"), ("checkbox", "CHECKBOX"),
	("combo box", "COMBOBOX"), ("combobox", "COMBOBOX"), ("drop down", "COMBOBOX"), ("dropdown", "COMBOBOX"),
	("edit field", "EDITABLETEXT"), ("edit box", "EDITABLETEXT"), ("text field", "EDITABLETEXT"), ("text box", "EDITABLETEXT"),
	("input field", "EDITABLETEXT"), ("list item", "LISTITEM"), ("menu item", "MENUITEM"), ("tree item", "TREEVIEWITEM"),
	("tree view item", "TREEVIEWITEM"), ("progress bar", "PROGRESSBAR"), ("table cell", "TABLECELL"), ("status bar", "STATUSBAR"),
	("tool bar", "TOOLBAR"), ("toolbar", "TOOLBAR"), ("menu bar", "MENUBAR"), ("spin button", "SPINBUTTON"),
	("button", "BUTTON"), ("link", "LINK"), ("heading", "HEADING"), ("graphic", "GRAPHIC"), ("image", "GRAPHIC"),
	("picture", "GRAPHIC"), ("slider", "SLIDER"), ("dialog", "DIALOG"), ("table", "TABLE"), ("cell", "TABLECELL"),
	("tab", "TAB"), ("menu", "MENU"), ("document", "DOCUMENT"), ("paragraph", "PARAGRAPH"), ("list", "LIST"),
	("window", "WINDOW"),
)
ROLE_SAID = {name: words for words, name in reversed(ROLE_WORDS)}
_ROLE = re.compile(r"\b(?:a|an|the|any|each|every|some)\s+(" + "|".join(re.escape(w) for w, _n in ROLE_WORDS) + r")s?\b",
	re.IGNORECASE)
_ROLE_AFTER = re.compile(r"\s+(?:(?:a|an|the|any|each|every|some)\s+)?(?:" + "|".join(re.escape(w) for w, _n in ROLE_WORDS)
	+ r")s?\b", re.IGNORECASE)
_TAIL = re.compile(r"\s+(?:appears?|shows? up|pops? up|comes? up|opens?|changes?|is shown|gets? (?:the )?focus|is focused)\b",
	re.IGNORECASE)
# Kinds of control that a web page's browse mode moves to without moving the focus: an event of the focus never
# comes for them there. The user is told.
_NO_FOCUS_IN_BROWSE = ("HEADING", "PARAGRAPH", "GRAPHIC", "TABLE", "TABLECELL", "LIST", "LISTITEM", "DOCUMENT")
# Programs as people name them, and the names NVDA's app modules have.
APP_NAMES = {
	"microsoft word": "winword", "ms word": "winword", "word": "winword", "excel": "excel", "outlook": "outlook",
	"powerpoint": "powerpnt", "microsoft edge": "msedge", "edge": "msedge", "google chrome": "chrome", "chrome": "chrome",
	"firefox": "firefox", "notepad++": "notepad++", "notepad": "notepad", "file explorer": "explorer",
	"windows explorer": "explorer", "explorer": "explorer", "thunderbird": "thunderbird", "vlc": "vlc", "spotify": "spotify",
	"brave": "brave", "vs code": "code", "visual studio code": "code",
}
_PROGRAM = re.compile(
	r"\b(?P<how>only (?:in|inside|for|within)|in|inside|within|for|while (?:i'?m |i am )?in)\s+(?:the program |the app |the application )?"
	r"(?P<name>this (?:program|app|application|game|window|player|editor|browser)|"
	+ "|".join(re.escape(name) for name in sorted(APP_NAMES, key=len, reverse=True)) + r")(?: only)?\b", re.IGNORECASE)
# Names that are everyday words too: "for word" may be about a word. They name a program after "in" or "only for".
_NOT_FOR = ("word", "edge", "explorer", "excel", "outlook")
_ONLY_PROGRAM = re.compile(r"^\s*(?:and\s+|but\s+)?(?:it\s+|this\s+|all of (?:it|this|them)\s+|everything\s+)?(?:should\s+|must\s+)?"
	r"(?:only\s+)?(?:works?|run|runs|act|acts|be|is|apply|applies)?\s*(?:only\s+)?$", re.IGNORECASE)
# What plain code cannot frame, so the add-on is written as one piece.
_UNFRAMED = re.compile(
	r"\bevery (?:\d+ |few |other |half an? |single )?(?:seconds?|minutes?|hours?|day|days|morning|evening)\b|\bevery hour\b|\bhourly\b"
	r"|\bat \d{1,2}(?::\d\d)?\s*(?:am|pm|o'?clock)\b|\bafter \d+ (?:seconds?|minutes?|hours?)\b|\btimer\b|\bschedule\b"
	r"|\b(?:when|as soon as|once|after) nvda (?:starts?|loads?|is started|restarts?|opens?)\b|\b(?:at|on) (?:start ?up|nvda start)\b"
	r"|\bsettings? (?:panel|dialog|page|category)\b|\bnvda menu\b|\boverlay\b|\bapp ?module\b|\bbraille display\b"
	r"|\b(?:menu item|item) (?:in|to) (?:the )?(?:nvda|tools) menu\b|\bclass\b", re.IGNORECASE)
_ADDON_HEAD = re.compile(
	r"^\s*(?:please\s+)?(?:can you\s+|could you\s+)?(?:(?:i want|i need|i'd like|i would like)\s+(?:you to\s+)?)?"
	r"(?:write|make|create|build|code|program|give)?\s*(?:me\s+)?(?:an?|the|my)?\s*(?:new\s+|small\s+|little\s+)?"
	r"(?:nvda\s+)?(?:add-?on|plug-?in|script)s?\b\s*(?:for nvda\s*)?(?:that|which|to|so that|:|,)?\s*", re.IGNORECASE)
_CLAUSE = re.compile(r"\s*(?:[.;:!?]+\s+|,\s*(?:and\s+(?:also\s+)?|also\s+|then\s+|plus\s+)?|\s+and also\s+|\s+also\s+|\s+plus\s+)",
	re.IGNORECASE)
_AND = re.compile(r"\s+and\s+(?:also\s+|then\s+)?", re.IGNORECASE)
# Words at the start of what a piece does that only lead up to it.
_LEAD_IN = re.compile(
	r"^(?:(?:and|then|also|so|to|it|it'?ll|it will|it should|it must|it can|should|will|must|can|please|nvda|"
	r"make it|have it|let it|get it to|i want it to|i want to|i'd like it to|i would like it to|i want nvda to|"
	r"give me|give it|i want|i need|i'd like|i would like|that|which|this add-?on|the add-?on|also make it)\s+)+"
	r"|^(?:make|let|have|get)\s+(?=(?:say|read|beep|speak|announce|tell|report|play|show|click|press|move|copy|open|give|"
	r"type|send|focus|toggle|switch|mute|jump|go|bring|describe|list|count|check|spell|repeat|stop|start|turn|set|select|"
	r"close|ding)\b)",
	re.IGNORECASE)
_TRAIL = re.compile(r"\s*(?:,?\s*(?:please|for me|too|as well|also|instead))+\s*[.!]?$", re.IGNORECASE)
# A verb that says what the piece does, as the user wrote it about the add-on ("it says"), and as it is asked.
_VERBS = {
	"says": "say", "reads": "read", "beeps": "beep", "speaks": "speak", "announces": "announce", "plays": "play",
	"tells": "tell", "reports": "report", "shows": "show", "clicks": "click", "presses": "press", "moves": "move",
	"copies": "copy", "opens": "open", "gives": "give", "makes": "make", "puts": "put", "types": "type",
	"sends": "send", "focuses": "focus", "toggles": "toggle", "switches": "switch", "mutes": "mute",
	"lets": "let", "jumps": "jump", "goes": "go", "brings": "bring", "describes": "describe", "lists": "list",
	"counts": "count", "checks": "check", "spells": "spell", "repeats": "repeat", "stops": "stop", "starts": "start",
	"turns": "turn", "sets": "set", "selects": "select", "closes": "close", "dings": "ding", "vibrates": "vibrate",
}


def _sentenceCase(text):
	return text[:1].upper() + text[1:]


def gestureOf(words):
	"""The key named in words, as NVDA writes it ("kb:NVDA+shift+h"), or "". A key needs a key that is held."""
	found = _keyIn(words or "")
	return _gesture(found.group(0)) if found else ""


def _keyIn(words):
	"""Where a key is named in words, or None. "Make nvda a bit quieter" names no key: a key of one letter that is
	a word of its own, said with spaces only, is no key."""
	for found in _GESTURE.finditer(words):
		if _gesture(found.group(0)):
			return found
	return None


def _gesture(said):
	parts = [p for p in re.split(r"\s*(?:\+|\bplus\b|-)\s*|\s+", said.strip()) if p]
	# Two-word key names that were split by their space.
	joined = []
	for part in parts:
		low = part.lower()
		if joined and joined[-1].lower() in ("page", "up", "down", "left", "right", "numpad") and (
				low in ("up", "down", "arrow") or low.isdigit()):
			joined[-1] = joined[-1] + part
		else:
			joined.append(part)
	held, key = joined[:-1], joined[-1].lower()
	if key in ("a", "i") and not re.search(r"\+|\bplus\b|-", said, re.IGNORECASE):
		return ""
	order = {"nvda": 0, "insert": 0, "control": 1, "ctrl": 1, "alt": 2, "shift": 3, "windows": 4, "win": 4}
	names = {"nvda": "NVDA", "insert": "NVDA", "ctrl": "control", "control": "control", "alt": "alt", "shift": "shift",
		"windows": "windows", "win": "windows"}
	held = sorted({names[h.lower()] for h in held if h.lower() in names}, key=lambda h: order[h.lower()])
	if not held:
		return ""
	key = {"esc": "escape", "pageup": "pageUp", "pagedown": "pageDown", "uparrow": "upArrow", "downarrow": "downArrow",
		"leftarrow": "leftArrow", "rightarrow": "rightArrow"}.get(key, key)
	if key.startswith("numpad") and key[6:].isdigit():
		key = "numpad" + key[6:]
	return "kb:" + "+".join(held + [key])


def _action(text):
	"""What a piece does, cleaned of the words that only lead up to it."""
	text = " ".join(text.split()).strip(" ,.;:!-")
	for _again in range(3):
		before = text
		text = _LEAD_IN.sub("", text).strip(" ,")
		text = _TRAIL.sub("", text).strip(" ,")
		if text == before:
			break
	first, _sep, rest = text.partition(" ")
	if first.lower() in _VERBS:
		text = _VERBS[first.lower()] + (" " + rest if rest else "")
	# "say heading and beep": every part of it gets its verb as asked.
	text = re.sub(r"\b(and|then)\s+(" + "|".join(_VERBS) + r")\b", lambda m: f"{m.group(1)} {_VERBS[m.group(2).lower()]}",
		text, flags=re.IGNORECASE)
	return text.strip(" ,.")


def _trigger(clause):
	"""What makes a clause run: (KEY, gesture, the words left) or (EVENT, event, role, the words left), or None."""
	found = _keyIn(clause)
	if found:
		before, after = clause[:found.start()], clause[found.end():]
		before = _KEY_AROUND.sub("", before)
		after = _KEY_AFTER.sub("", after)
		return KEY, _gesture(found.group(0)), f"{before} {after}"
	if not _WHEN.search(clause) and not re.search(r"\bas (?:i|you) type\b", clause, re.IGNORECASE):
		return None
	for name, pattern in _EVENTS:
		hit = pattern.search(clause)
		if not hit:
			continue
		# The words that say when: from the word "when" before the event's own words, to their end.
		start = hit.start()
		when = None
		for w in _WHEN.finditer(clause[:hit.start()]):
			when = w
		if when is not None and hit.start() - when.end() <= 60:
			start = when.start()
		end = hit.end()
		after = _ROLE_AFTER.match(clause, end)
		if after:
			end = after.end()
		tail = _TAIL.match(clause, end)
		if tail:
			end = tail.end()
		said = clause[start:end]
		role = ""
		roleFound = _ROLE.search(said)
		if roleFound:
			role = next(n for w, n in ROLE_WORDS if w == roleFound.group(1).lower())
		state = None
		if name == "stateChange":
			found = _STATE.search(said)
			if found:
				state = next(value for word, value in STATES if word == found.group(1).lower())
		return EVENT, name, role, f"{clause[:start]} {clause[end:]}", state
	return None


def _programName(name, facts):
	"""The name NVDA's app module has for a program named in words, or ""."""
	low = name.lower()
	if low.startswith("this "):
		here = re.search(r"Program: ([\w.+-]+?)\.?(?:\s|$)", facts or "")
		return here.group(1).lower() if here else ""
	return APP_NAMES.get(low, low)


def _clauses(text):
	"""The clauses of a request, split where one thing to do ends; a clause with two triggers is split at its "and"."""
	clauses = [c.strip() for c in _CLAUSE.split(text) if c and c.strip(" ,.;")]
	out = []
	for clause in clauses:
		pieces = [clause]
		for _again in range(3):
			changed = False
			for i, piece in enumerate(pieces):
				parts = _AND.split(piece)
				if len(parts) < 2:
					continue
				for cut in range(1, len(parts)):
					left, right = " and ".join(parts[:cut]), " and ".join(parts[cut:])
					if _trigger(left) is not None and _trigger(right) is not None:
						pieces[i:i + 1] = [left, right]
						changed = True
						break
				if changed:
					break
			if not changed:
				break
		out += pieces
	return out


def read(purpose, facts=""):
	"""A request read into pieces: (pieces, why). pieces is empty when plain code cannot read it into pieces for
	certain; then why says so in a sentence."""
	text = " ".join(str(purpose or "").replace("’", "'").replace("“", '"').replace("”", '"').split())
	# The request in the plain words its pieces are read from, by the lines of understanding.md "in add-ons" and the
	# user's own words (claw/understand.py): "chimes whenever focus hits a link" is "beeps whenever focus lands on a
	# link". Words in quotes and keys stay as they are.
	reading = understand.current().read(text, where=understand.ADDON)
	if reading.changed and reading.text:
		debuglog.log("codeplan", f"The add-on request is read as: {reading.text!r}")
		text = reading.text
	text = _ADDON_HEAD.sub("", text, count=1).strip()
	if not text:
		return [], "the request says nothing the add-on is to do"
	if _UNFRAMED.search(text):
		return [], "it asks for something that is more than a key command or an event, such as a timer or a settings panel"
	# Keys are written as NVDA writes them first, so that "NVDA plus shift plus H" is not split at its "plus".
	text = _GESTURE.sub(lambda m: _gesture(m.group(0))[3:] or m.group(0), text)
	everywhere = ""
	pieces, waiting = [], None
	for clause in _clauses(text):
		program = ""
		named = _PROGRAM.search(clause)
		if named and named.group("how").lower() == "for" and named.group("name").lower() in _NOT_FOR:
			named = None
		if named:
			program = _programName(named.group("name"), facts)
			if not program:
				return [], "it names this program, and which program is in front is not known"
			clause = (clause[:named.start()] + " " + clause[named.end():]).strip()
		if program and _ONLY_PROGRAM.match(clause):
			everywhere = program
			continue
		trigger = _trigger(clause)
		if trigger is None and _WANTS_KEY.search(clause):
			rest = _WANTS_KEY.sub(" ", clause)
			trigger = (KEY, "", rest)
		if trigger is None:
			action = _action(clause)
			if not action:
				continue
			if waiting is not None:
				waiting.action = action
				waiting = None
			elif pieces:
				pieces[-1].action = f"{pieces[-1].action} and {action}" if pieces[-1].action else action
			else:
				return [], f"it does not say when \"{uncut(clause)}\" is to happen"
			continue
		if trigger[0] == KEY:
			piece = Piece(KEY, clause, _action(trigger[2]), gesture=trigger[1], program=program)
		else:
			piece = Piece(EVENT, clause, _action(trigger[3]), event=trigger[1], role=trigger[2], program=program,
				state=trigger[4])
		pieces.append(piece)
		waiting = piece if not piece.action else None
	pieces = [piece for piece in pieces if piece.action]
	if not pieces:
		return [], "no key command and nothing that happens by itself was found in it"
	if len(pieces) > MAX_PIECES:
		return [], f"it has more than {MAX_PIECES} pieces"
	keys = [piece.gesture.lower() for piece in pieces if piece.gesture]
	if len(keys) != len(set(keys)):
		return [], "it gives one key two jobs"
	for piece in pieces:
		piece.program = piece.program or everywhere
	return pieces, ""


def chooseKeys(pieces, used=()):
	"""Give a key that nothing else uses to every key command whose key was not named. Raises Fallback when none
	is left."""
	taken = list(used) + [piece.gesture.replace("kb:", "") for piece in pieces if piece.gesture]
	for piece in pieces:
		if piece.kind == KEY and not piece.gesture:
			free = fixes.freeKeys(1, taken)
			if not free:
				raise Fallback("no free key was left for a key command")
			piece.gesture = "kb:" + free[0]
			piece.chosenKey = True
			taken.append(free[0])


# --- Writing what plain code can write ---

_VALUE_WORDS = frozenset((
	"time", "date", "day", "battery", "name", "title", "value", "text", "line", "word", "number", "count", "state", "role",
	"status", "focus", "selection", "clipboard", "percentage", "level", "volume", "it", "this", "that", "something",
	"nothing", "what", "which", "who", "where", "when", "how", "its", "the", "a", "an", "out", "aloud", "loud", "me",
	"everything", "all", "description", "label", "position", "character", "letter", "row", "column", "cell"))
_BEEP = re.compile(r"^(?:play|make|give|sound)?\s*(?:a|an)?\s*(?:short|quick|little|small|soft)?\s*"
	r"(?P<pitch>high|higher|low|lower|deep)?\s*(?:-?pitched\s+)?(?:beep|tone|ding|blip)(?:\s+sound)?$", re.IGNORECASE)
_SAY_QUOTED = re.compile(r"^(?:say|speak|announce|read out|tell me)\s+(?:the words?\s+)?[\"'](?P<text>[^\"']{1,120})[\"']$",
	re.IGNORECASE)
_SAY_WORD = re.compile(r"^(?:say|speak|announce)\s+(?:the word\s+)?(?P<text>[a-z][\w'-]{0,30})$", re.IGNORECASE)


def plainBody(action):
	"""The lines plain code writes for a piece whose work is a beep or a fixed sentence, or "" when a model is
	needed. A piece that does several such things in a row gets all of them."""
	lines, imports = [], set()
	for part in re.split(r"\s*,?\s+(?:and|then|and then)\s+", action.strip(), flags=re.IGNORECASE):
		part = part.strip(" ,.")
		beep = _BEEP.match(part)
		if beep:
			pitch = (beep.group("pitch") or "").lower()
			frequency = 1200 if pitch in ("high", "higher") else 330 if pitch in ("low", "lower", "deep") else 880
			lines.append(f"tones.beep({frequency}, 80)")
			imports.add("tones")
			continue
		said = _SAY_QUOTED.match(part) or _SAY_WORD.match(part)
		if said and said.group("text").lower() not in _VALUE_WORDS:
			lines.append(f"ui.message({said.group('text')!r})")
			imports.add("ui")
			continue
		return "", set()
	return "\n".join(lines), imports


# --- Putting the pieces together ---

def _identifier(action, used):
	words = re.findall(r"[a-z0-9]+", action.lower())[:4] or ["piece"]
	name = words[0] + "".join(word.capitalize() for word in words[1:])
	if name[0].isdigit():
		name = "piece" + name.capitalize()
	unique, number = name, 2
	while unique in used:
		unique, number = f"{name}{number}", number + 1
	used.add(unique)
	return unique


def name(pieces):
	"""Give each key command a method name of its own, made from what it does."""
	used = set()
	for piece in pieces:
		if piece.kind == KEY:
			piece.name = "script_" + _identifier(piece.action, used)
		else:
			piece.name = "event_" + piece.event


_HERE = "# Your lines go here."


def frame(piece, body=None):
	"""The method of one piece as plain code writes it, with its lines, or with the place for them."""
	lines = (body if body is not None else _HERE).splitlines() or [_HERE]
	if piece.kind == KEY:
		out = [f"\t@script(description={_sentenceCase(piece.action)!r}, gesture={piece.gesture!r})",
			f"\tdef {piece.name}(self, gesture):"]
		if piece.program:
			out += [f"\t\tif api.getFocusObject().appModule.appName != {piece.program!r}:", "\t\t\tgesture.send()",
				"\t\t\treturn"]
		out += ["\t\t" + line if line.strip() else "" for line in lines]
		return "\n".join(out)
	return "\n".join([f"\tdef {piece.name}(self, obj, nextHandler{_EVENT_ARGS.get(piece.event, '')}):"]
		+ _eventPart(piece, lines) + ["\t\tnextHandler()"])


def _eventPart(piece, lines):
	"""One piece inside its event's method: its condition and its lines, in a try of its own."""
	conditions = []
	if piece.role:
		conditions.append(f"obj.role == controlTypes.Role.{piece.role}")
	if piece.state:
		conditions.append(f"controlTypes.State.{piece.state[0]} {'in' if piece.state[1] else 'not in'} obj.states")
	if piece.program:
		# Inside the piece's own try: a control without a program raises, and NVDA still gets the event. Written plainly,
		# so that what the code does is said rightly in words (microaddons.describe).
		conditions.append(f"obj.appModule.appName == {piece.program!r}")
	indent = "\t\t\t\t" if conditions else "\t\t\t"
	out = ["\t\ttry:"]
	if conditions:
		out.append("\t\t\tif " + " and ".join(conditions) + ":")
	out += [indent + line if line.strip() else "" for line in lines]
	out += ["\t\texcept Exception:", "\t\t\tpass"]
	return out


def assemble(pieces):
	"""The whole add-on from its pieces: the imports, the class, every key command, and every event with the pieces
	that wait for it, each in a try of its own."""
	imports = {"globalPluginHandler"}
	for piece in pieces:
		imports |= piece.imports
		if piece.program and piece.kind == KEY:
			imports.add("api")
		if piece.role or piece.state:
			imports.add("controlTypes")
	methods, events = [], {}
	for piece in pieces:
		if piece.kind == KEY:
			methods.append(frame(piece, piece.body))
		else:
			events.setdefault(piece.event, []).append(piece)
	for event, waiting in events.items():
		head = f"\tdef event_{event}(self, obj, nextHandler{_EVENT_ARGS.get(event, '')}):"
		body = []
		for piece in waiting:
			body += _eventPart(piece, (piece.body or "pass").splitlines())
		methods.append("\n".join([head] + body + ["\t\tnextHandler()"]))
	header = [f"import {module}" for module in sorted(imports, key=str.lower)]
	if any(piece.kind == KEY for piece in pieces):
		header.append("from scriptHandler import script")
	source = "\n".join(header) + "\n\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\n" + "\n\n".join(methods) + "\n"
	return microaddons._addImports(microaddons.fixRoles(source))


def limits(pieces):
	"""What the add-on cannot do, in plain words, from how plain code framed it: said before it is turned on."""
	said = []
	for piece in pieces:
		if piece.kind == EVENT and piece.event == "gainFocus" and piece.role in _NO_FOCUS_IN_BROWSE:
			said.append(
				f"On a web page in browse mode, moving to a {ROLE_SAID.get(piece.role, piece.role.lower())} does not move the "
				"focus, so that part works only where it gets the focus, as in focus mode or in a program.")
		if piece.chosenKey:
			said.append(f"No key was named for \"{uncut(piece.action)}\", so VisionClaw chose "
				f"{piece.gesture.replace('kb:', '')}, which nothing else uses.")
	return said


# --- What the model writes for one piece ---

def _block(answer):
	"""The code in a model's answer with every line's indentation as it was written, the indentation all lines share
	taken away. Measured with Qwen3.5 9B on 2026-11-19: it writes the lines of a piece indented, as they stand in the
	method; stripping the whole answer took the first line's indentation alone, and every answer then looked like a
	syntax error the model could not correct."""
	blocks = microaddons._FENCE.findall(answer or "")
	if blocks:
		code = max(blocks, key=len)
	else:
		code = re.sub(r"^\s*```(?:python|py)?[ \t]*\n", "", answer or "")
		code = re.sub(r"\n```\s*$", "", code)
	lines = [line.rstrip() for line in code.splitlines()]
	while lines and not lines[0].strip():
		lines.pop(0)
	while lines and not lines[-1].strip():
		lines.pop()
	code = textwrap.dedent("\n".join(lines))
	# A first line that lost its indentation elsewhere, before the rest that kept theirs: the rest is put level with it.
	rest = [line for line in code.splitlines()[1:] if line.strip()]
	if code and not code[0].isspace() and rest and all(line[0].isspace() for line in rest):
		try:
			ast.parse(code)
		except SyntaxError:
			first, *others = code.splitlines()
			code = first + "\n" + textwrap.dedent("\n".join(others))
	return code + "\n" if code else ""


def bodyOf(answer):
	"""The lines inside a method, from a model's answer: (body, imports). A model that wrote the whole method or the
	whole add-on anyway has the lines of its first method taken. Imports are kept apart; nextHandler() is taken out,
	because the frame calls it."""
	code = _block(answer)
	try:
		tree = ast.parse(code)
	except SyntaxError:
		tree = None
	if tree is not None:
		functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
		if functions:
			chosen = next((f for f in functions if f.name.startswith(("script_", "event_"))), functions[0])
			lines = code.splitlines()
			code = "\n".join(lines[chosen.body[0].lineno - 1:chosen.end_lineno]) if chosen.body else ""
	imports, kept = set(), []
	for line in textwrap.dedent(code).splitlines():
		bare = line.strip()
		found = re.match(r"^import\s+([\w.]+)\s*$", bare) or re.match(r"^from\s+([\w.]+)\s+import\b", bare)
		if found:
			imports.add(found.group(1).split(".")[0])
			continue
		if bare in ("nextHandler()", "pass") or bare.startswith("@script") or bare.startswith("class GlobalPlugin"):
			continue
		kept.append(line.rstrip())
	while kept and not kept[0].strip():
		kept.pop(0)
	while kept and not kept[-1].strip():
		kept.pop()
	body = textwrap.dedent("\n".join(kept))
	return body, {name for name in imports if name in _STANDARD or name in _NVDA_MODULES}


def _withImports(body, imports):
	"""The modules a piece uses that plain code adds: those it names that are allowed."""
	used = set(re.findall(r"\b([A-Za-z_]\w*)\.", body))
	return set(imports) | {name for name in used if name in _STANDARD or name in _NVDA_MODULES}


def problems(piece, body):
	"""What is wrong with a piece's lines, as sentences a model can act on. Empty if nothing."""
	if not body.strip():
		return ["Nothing was written. Write the lines that do what this piece asks."]
	if len(body.splitlines()) > MAX_BODY_LINES:
		return [f"That is far too long for one piece. Write it again in under {MAX_BODY_LINES // 2} lines."]
	if "appName" in body:
		# A small model keeps what it once wrote: a check of the same program that the frame checks already does no
		# harm and is left. A check of another program, or of a program where none was asked, is a fault.
		named = {text.lower() for text in re.findall(r"""appName\s*[!=]=\s*["']([^"']+)["']|["']([^"']+)["']\s*[!=]=\s*[\w.]*appName""",
			body) for text in text if text}
		if not piece.program or named - {piece.program.lower()} or not named:
			return ["Do not check the program: VisionClaw does that. Write only what the piece does."]
	if re.search(r"^\s*(?:class|@script)\b", body, re.MULTILINE):
		return ["Write only the lines inside the method: no class and no @script."]
	alone = Piece(piece.kind, piece.said, piece.action, piece.gesture, piece.event, piece.role, piece.program, piece.state)
	alone.name, alone.body, alone.imports = piece.name, body, _withImports(body, piece.imports)
	source = assemble([alone])
	found = microaddons.check(source)
	# The frame is plain code's own; what remains is about the lines.
	return [p for p in found if "must take" not in p and "must call nextHandler" not in p]


def _notes(notesFor, piece):
	if notesFor is None:
		return ""
	try:
		return clip(notesFor(f"{piece.action} {piece.when()}") or "", NOTES_CHARS)
	except Exception as e:
		debuglog.error("codeplan", "The notes for a piece could not be found", e)
		return ""


def question(piece, notes=""):
	"""What the model is given for one piece: its own section of the work sheet, and nothing of the others."""
	lines = [
		f"This piece of the add-on must: {piece.action}.",
		f"It runs {piece.when()}. " + (_EVENT_OBJ.get(piece.event, "") if piece.kind == EVENT else ""),
		"The method VisionClaw wrote, with the place for your lines:",
		"```python", frame(piece), "```",
	]
	if notes:
		lines += ["Notes that may help:", notes]
	lines.append(f"Write only the lines that go where it says \"{_HERE}\". They must: {piece.action}.")
	return "\n".join(line.rstrip() for line in lines)


def _sheetText(piece, asked, wrote, said):
	parts = [f"What it must do: {piece.action}", f"When it runs: {piece.when()}", f"The user's words: \"{piece.said}\""]
	if piece.plain:
		parts.append("Written by plain code, without a model.")
	elif asked:
		parts += ["", "What the model is given, and nothing else:", "", "```text", asked, "```"]
	if wrote:
		parts += ["", "The lines:", "", "```python", wrote, "```"]
	if said:
		parts += ["", f"Check: {said}"]
	return "\n".join(parts)


def _say(sheet, number, piece, asked="", wrote="", said=""):
	if sheet is None:
		return
	title = f"Piece {number}: " + (f"the key {piece.gesture.replace('kb:', '')}" if piece.kind == KEY else _EVENT_WORDS.get(piece.event, piece.event))
	sheet.section(title, _sheetText(piece, asked, wrote, said))


def _writer(params):
	return "model" if getattr(params, "oneModel", False) else "coder model"


def writePiece(llm, task, piece, number, params, coder, reviewer, notesFor=None, sheet=None):
	"""The lines of one piece, written by plain code where it can, else by the model, checked, corrected and
	reviewed on their own. Raises Fallback when no lines that pass the checks were written."""
	body, imports = plainBody(piece.action)
	if body:
		piece.body, piece.imports, piece.plain = body, imports, True
		_say(sheet, number, piece, wrote=body, said="passes.")
		task.emit("detail", f"Piece {number} ({piece.action}) was written by plain code.")
		return
	notes = _notes(notesFor, piece)
	asked = question(piece, notes)
	system = prompts.coding(PIECE_SYSTEM, piece.action, given=asked)
	_say(sheet, number, piece, asked=asked)
	user = asked
	reviews = params.codeReviews
	doubt = ""
	for attempt in range(params.codeRepairs + 1):
		task.check()
		try:
			answer = llm.text(coder, system, user, maxTokens=min(params.codeTokens, 600), reasoning=params.reasoning,
				temperature=0, code=True)
		except LLMError as e:
			raise Fallback(f"the {_writer(params)} gave no answer for a piece: {e}")
		body, imports = bodyOf(answer)
		# What plain code can correct, it corrects before anything is sent back (microaddons.fixNames).
		body = microaddons.fixNames(body)
		found = problems(piece, body)
		if not found and reviews > 0:
			reviews -= 1
			found, doubt = _review(llm, task, piece, body, params, reviewer)
		_say(sheet, number, piece, asked=asked, wrote=body, said="passes." if not found else " ".join(found))
		if not found:
			piece.body, piece.imports, piece.doubt = body, _withImports(body, imports), doubt
			return
		task.emit("detail", f"Piece {number}: " + " ".join(found[:3]))
		user = (f"{asked}\nYou wrote:\n```python\n{clip(body, 1500)}\n```\nIt has these problems:\n"
			+ "\n".join(f"- {clip(p, 300)}" for p in found[:4]) + "\nWrite the corrected lines, and only them.")
	# The checks decide: lines that pass every check are kept even when the review still doubts them.
	if body and not problems(piece, body):
		piece.body, piece.imports, piece.doubt = body, _withImports(body, imports), doubt
		return
	raise Fallback(f"piece {number} ({uncut(piece.action)}) did not pass the checks")


def _review(llm, task, piece, body, params, reviewer):
	"""The other model, or the same model reading again, says whether the lines do what the piece asks: (problems,
	doubt). The review only advises; a fault it names is sent back to the writer once."""
	one = getattr(params, "oneModel", False)
	alone = Piece(piece.kind, piece.said, piece.action, piece.gesture, piece.event, piece.role, piece.program, piece.state)
	alone.name = piece.name
	try:
		verdict = llm.json(reviewer, prompts.coding(_REVIEW_SYSTEM, piece.action),
			f"This piece must: {uncut(piece.action)}\nIt runs {piece.when()}.\nCode:\n{clip(frame(alone, body), 3000)}",
			_REVIEW_SCHEMA, maxTokens=120, reasoning=params.reasoning)
	except LLMError:
		return [], ""
	fault = " ".join(str(verdict.get("problem") or "").split())
	if not verdict.get("ok") and fault:
		task.emit("talk", (f"The model read this piece again and found a fault: {fault}" if one
			else f"The reviewing model found a fault in this piece: {fault}"))
		return [fault], fault
	task.emit("talk", "The model read this piece again: no fault found." if one
		else "The reviewing model checked this piece: no fault found.")
	return [], ""


def write(llm, task, purpose, facts, notes, params, coder, reviewer, notesFor=None, sheet=None, usedKeys=()):
	"""An add-on for purpose, written piece by piece where plain code can read it into pieces, else as one piece
	(microaddons.write). notes: what fits the whole request, for the add-on written as one piece; notesFor(text):
	what fits one piece's own words. sheet: the request's work sheet, from which each piece is fed. Returns the
	source; task.codeLimits holds what the add-on cannot do, in sentences. Raises ToolError when nothing passes."""
	task.codeLimits = []
	pieces, why = read(purpose, facts)
	if pieces:
		try:
			return _inPieces(llm, task, purpose, pieces, params, coder, reviewer, notesFor, sheet, usedKeys)
		except Fallback as e:
			why = str(e)
	debuglog.log("codeplan", f"{purpose!r} is written as one piece: {why}.")
	task.emit("detail", f"The add-on is written as one piece, because {why}.")
	if sheet is not None:
		sheet.section("The add-on as one piece", f"Written as one piece, because {why}.")
	task.codeLimits = []
	return microaddons.write(llm, task, purpose, facts, notes, params, coder, reviewer)


def _inPieces(llm, task, purpose, pieces, params, coder, reviewer, notesFor, sheet, usedKeys):
	chooseKeys(pieces, usedKeys)
	name(pieces)
	debuglog.log("codeplan", f"{purpose!r} read into {len(pieces)} pieces: {pieces}")
	if sheet is not None:
		sheet.section("The add-on, piece by piece", "\n".join(
			f"{number}. {_sentenceCase(piece.action)}: {piece.when()}." for number, piece in enumerate(pieces, 1)))
	task.emit("talk", f"The add-on is written in {len(pieces)} piece{'s' if len(pieces) != 1 else ''}: " + "; ".join(
		f"{number}. {piece.action}, {piece.when()}" for number, piece in enumerate(pieces, 1)) + ".")
	task.codeDoubt = ""
	for number, piece in enumerate(pieces, 1):
		task.emit("detail", f"The {_writer(params)} is writing piece {number} of {len(pieces)}: {piece.action}.")
		writePiece(llm, task, piece, number, params, coder, reviewer, notesFor, sheet)
	source = assemble(pieces)
	left = microaddons.check(source)
	if left:
		raise Fallback("the pieces put together did not pass the checks: " + " ".join(left[:2]))
	doubts = [piece.doubt for piece in pieces if piece.doubt]
	task.codeDoubt = " ".join(doubts)
	task.codeLimits = limits(pieces)
	if sheet is not None:
		sheet.section("The whole add-on", "```python\n" + source.rstrip() + "\n```")
	return source


# --- Correcting one method of an add-on that failed ---

def methodAt(source, line):
	"""The method of an add-on that holds a line: (first line, last line), counted from 1 and with its decorators,
	or None."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return None
	best = None
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.lineno <= line <= node.end_lineno:
			first = min([d.lineno for d in node.decorator_list] + [node.lineno])
			if best is None or first >= best[0]:
				best = (first, node.end_lineno)
	return best


def _methods(source):
	try:
		return sum(isinstance(node, ast.FunctionDef) for node in ast.walk(ast.parse(source)))
	except SyntaxError:
		return 0


def fixMethod(llm, task, purpose, source, problems_, notes, params, coder, reviewer, facts="", sheet=None):
	"""Correct an add-on that failed in NVDA. When the error names a line inside one of several methods, only that
	method is sent to the model, and put back; else the whole add-on is corrected as before (microaddons.fix)."""
	spans = set()
	for problem in problems_:
		for found in re.finditer(r"\bline (\d+)\b", problem):
			spans.add(methodAt(source, int(found.group(1))))
	named = set(re.findall(r"\b((?:script|event)_\w+) failed\b", " ".join(problems_)))
	# Only where everything that went wrong is in one method: the user's own words name no line, and are about
	# the whole add-on.
	whole = (len(spans) != 1 or None in spans or len(named) > 1
		or any(problem.startswith("The user says") for problem in problems_))
	span = None if whole else next(iter(spans))
	if span is None or _methods(source) < 2:
		return microaddons.fix(llm, task, purpose, source, problems_, notes, params, coder, reviewer, facts)
	lines = source.splitlines()
	method = textwrap.dedent("\n".join(lines[span[0] - 1:span[1]]))
	indent = re.match(r"^\s*", lines[span[0] - 1]).group(0)
	task.emit("detail", f"The {_writer(params)} is correcting only the method where it failed: " + uncut(problems_[0]))
	user = (f"The add-on as a whole is for: {uncut(purpose)}\nThis method of it fails:\n```python\n{clip(method, 2500)}\n```\n"
		"Problems:\n" + "\n".join(f"- {clip(p, 500)}" for p in problems_[:5]))
	if notes:
		user += f"\nNotes about NVDA that may help:\n{clip(notes, 900)}"
	user += "\nWrite the whole corrected method."
	if sheet is not None:
		sheet.section("Correcting one method", f"Lines {span[0]} to {span[1]} of the add-on.\n\n```text\n{user}\n```")
	for _attempt in range(params.codeRepairs + 1):
		task.check()
		try:
			answer = llm.text(coder, prompts.coding(_METHOD_SYSTEM, purpose, given=user), user, maxTokens=params.codeTokens,
				reasoning=params.reasoning, temperature=0, code=True)
		except LLMError:
			break
		code = microaddons.extractCode(answer)
		try:
			tree = ast.parse(textwrap.dedent(code))
			if not any(isinstance(node, ast.FunctionDef) for node in tree.body):
				raise SyntaxError("no method")
		except SyntaxError:
			user += "\nAnswer with the whole method, its def line included."
			continue
		new = "\n".join(indent + l if l.strip() else "" for l in textwrap.dedent(code).rstrip().splitlines())
		fixed = microaddons._addImports("\n".join(lines[:span[0] - 1] + [new] + lines[span[1]:]) + "\n")
		left = microaddons.check(fixed)
		if not left:
			return fixed
		user += "\nThat still has problems: " + " ".join(left[:3])
	return microaddons.fix(llm, task, purpose, source, problems_, notes, params, coder, reviewer, facts)
