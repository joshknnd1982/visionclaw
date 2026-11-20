# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the user put exactly where they asked to be, as plain logic. The owner said on 2026-11-19: "The user
# can't just be thrown randomly into a dialog box or left in the middle of nowhere on a website either in browse mode
# or focus mode or in any app or game ... when he wants to be placed on page two in the advanced dialog in a certain
# edit field or on a certain kind of specific control with a specific label", "this goes for all kinds of games, apps,
# inaccessible windows and apps and dialogs", and "if no accessible object or window or control is found, once some
# are made accessible, user is placed on the one that is the most likely to be helpful depending on app, task, window
# or control type, label, color, etcetera." What follows from it:
#   - Plain code reads the place from the user's own words (wish): the window or dialog, the page of a dialog with tabs
#     (by its number or its name), the kind of control, its label, which one of several, and whether the user wants to
#     type there. A model writes nothing here.
#   - Plain code picks among what NVDA, the web page or the window's picture shows (pickPage, pickControls, opener),
#     and where nothing is named, the item most likely to help (helpful): by the words of the request, the kind of
#     program and window, the kind of control, its label, whether the program marks it, and its colour.
#   - The way there is learned as a line the user owns (routeLine) and read again (routeFrom), from the scratchpad of
#     the program and from what the user asked VisionClaw to remember.
# Every sentence the user hears about it is here. No NVDA dependencies (gototools.py does the work in NVDA).

import re

from . import computer, controls

# The kinds of control, by the words people use for them: an id, the words, the roles NVDA gives them
# (tests/nvda_objects.json, NVDA 2026.3.1), the kinds of webtools.KINDS for a web page, and the roles of the overlay's
# items for a window read from its picture. The order matters: "check box" before "box", "combo box" before "box".
KINDS = (
	("check", r"check ?box(?:es)?|tick ?box(?:es)?", ("CHECKBOX", "CHECKMENUITEM", "SWITCH"), ("checkbox",), ("checkbox",)),
	("radio", r"radio ?buttons?|option ?buttons?", ("RADIOBUTTON", "RADIOMENUITEM"), ("radio button",), ("radio",)),
	("combo", r"combo ?box(?:es)?|drop[- ]?downs?(?: lists?| box(?:es)?| menus?)?|pull[- ]?downs?(?: lists?| menus?)?|select boxe?s?",
		("COMBOBOX", "DROPLIST", "DROPDOWNBUTTON"), ("combo box",), ()),
	("list", r"list ?box(?:es)?|list ?views?|lists?", ("LIST", "DATAGRID"), (), ()),
	("tree", r"tree ?views?|trees?", ("TREEVIEW", "TREEVIEWITEM"), (), ()),
	("slider", r"sliders?|faders?|track ?bars?|volume bars?", ("SLIDER", "DIAL"), (), ()),
	("spin", r"spin ?(?:box|button)(?:es|s)?|up[- ]?down (?:box|control)(?:es|s)?|number (?:box|field)(?:es|s)?", ("SPINBUTTON",), (), ()),
	("field", r"edit ?(?:fields?|box(?:es)?|controls?)|text ?(?:fields?|box(?:es)?|areas?|inputs?)|input (?:fields?|box(?:es)?)|inputs?"
		r"|entry (?:fields?|box(?:es)?)|search (?:box|field|bar)(?:es|s)?|password (?:box|field)(?:es|s)?|message body|body of the message"
		r"|fields?|box(?:es)?",
		("EDITABLETEXT", "PASSWORDEDIT", "RICHEDIT", "EDITBAR", "IPADDRESS", "HOTKEYFIELD", "DATEEDITOR", "TERMINAL", "DOCUMENT"),
		("edit field",), ("field",)),
	("menu", r"menu ?items?|menu (?:entry|entries|options?)", ("MENUITEM",), (), ()),
	("link", r"links?|hyper ?links?", ("LINK",), ("link",), ("link",)),
	("table", r"tables?|grids?|spread ?sheets?", ("TABLE", "TABLECELL", "DATAGRID"), (), ()),
	("button", r"buttons?|icons?", ("BUTTON", "TOGGLEBUTTON", "SPLITBUTTON", "MENUBUTTON", "ICON", "DESKTOPICON"), ("button",), ("button",)),
)
_KIND_IDS = tuple(kind for kind, *_rest in KINDS)
_KIND_WORDS = "|".join(f"(?:{words})" for _kind, words, *_rest in KINDS)
# How each kind is said to the user.
KIND_SAID = {"check": "check box", "radio": "radio button", "combo": "combo box", "list": "list", "tree": "tree view",
	"slider": "slider", "spin": "spin box", "field": "edit field", "menu": "menu item", "link": "link", "table": "table",
	"button": "button"}
# Kinds a click only puts the focus in, without doing anything: where a program does not let the focus move to one,
# a click in it is safe. A button, a check box or a link would be pressed by a click, so they never are.
CLICK_SAFE = ("field", "combo", "list", "tree", "table", "spin")
# Kinds the user types into, and kinds where the user wants focus mode on a web page.
TYPED = ("field", "combo", "spin")

_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
	"eleven": 11, "twelve": 12}
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
	"tenth": 10, "last": -1, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5, "6th": 6}
_NUMBER = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_ORDINAL = r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|1st|2nd|3rd|4th|5th|6th)"

# The words that say "put me there". Only these start the job: "where is the proxy field" asks, and moves nobody.
_PUT = (
	r"\b(?:put|place|take|bring|get|drop|land|move|send|leave|set|park|stick|plonk|pop)\s+(?:me|us)\s+(?:right\s+)?"
	r"(?:on|in|into|at|to|onto|inside|over to|back (?:on|in|to))\b"
	r"|\b(?:put|place|set|move|bring|give|get|land)\s+(?:the|my|nvda'?s?|keyboard)?\s*(?:keyboard\s+)?(?:focus|cursor|caret)\s+"
	r"(?:on|in|into|to|at|onto|inside|over to|over on|back to|back on)\b"
	r"|\b(?:focus|refocus)\s+(?:on\s+)?(?:the|that|my|this)\b"
	r"|\b(?:i(?:\s+(?:want|need|would like)|['’]d like)\s+to\s+(?:be|get|go|land|end up)|i\s+wanna\s+(?:be|get|go))\s+(?:right\s+)?"
	r"(?:on|in|into|at|to|onto|inside)\b"
	r"|\b(?:go|jump|navigate|move|skip|switch|head|get|tab)\s+(?:straight\s+|right\s+)?(?:to|into|over to|onto)\b"
	r"|\b(?:put|place|take|bring|get|drop|land|move|leave)\s+me\s+(?:somewhere|where|there)\b")
_PUT_RE = re.compile(_PUT, re.IGNORECASE)
# What is not this job: a question, a web address, a heading or part of a page (moving the reading position there is
# the job go_to), a part of Windows, something to be typed, set, clicked or opened besides.
_ASKS = re.compile(
	r"^\W*(?:please\s+)?(?:how|where|what|which|why|when|is|are|does|do|can i|could i)\b(?!.*\b(?:put|take|place|bring) me\b)",
	re.IGNORECASE)
_NOT_THIS = re.compile(
	r"\b(headings?|sections?|landmarks?|main (?:content|part|region)|comments?(?! (?:box|field|area))|articles?|paragraphs?|top of the page|"
	r"bottom of the page|end of the page|next page|previous page|last page you|line \d+|chapter|bookmark)\b"
	r"|\b[a-z0-9-]+\.(com|org|net|edu|gov|io|co|uk|de|fr|ca|au)\b|https?:|www\."
	# A field in trouble is found by what stops the form (form_trouble), not by its name: "put my focus in the first
	# required field that I still need to complete".
	r"|\b(required|mandatory|still (?:need|have) to (?:complete|fill)|still empty|invalid|in error|has an error|marked (?:as )?wrong|"
	r"red (?:border|outline|box))\b", re.IGNORECASE)
_DOES_MORE = re.compile(
	r"\b(?:and|then|,)\s*(?:then\s+)?(?:type|write|enter|fill|click|press|check|uncheck|tick|turn|set|select|choose|"
	r"open|close|delete|submit|send|read|tell|describe)\b(?!\s+(?:it|there|in it|into it)\b.{0,0}$)", re.IGNORECASE)
# A place of its own in a request: a dialog or a window by its name.
_WINDOW_KIND = r"dialog(?:ue)?(?: box)?|window|properties|preferences|property sheet|screen|panel|pop-?up|message box"
_WINDOW_WORD = re.compile(rf"\b(?:{_WINDOW_KIND})\b", re.IGNORECASE)
_DETERMINER = re.compile(r"\b(?:the|this|that|my|its|an?)\s+", re.IGNORECASE)


class _Window:
	"""Where a window is named in the words: group(1) its name words, or None for "this dialog" alone."""

	def __init__(self, name):
		self.name = name

	def group(self, index):
		return self.name


def _windowOf(low):
	"""The name of the dialog or window the words name: the words right before "dialog", "window" and the like, back to
	the nearest "the", "this" or "my" (at most four); "the name field of the options dialog" names the options dialog."""
	for kind in _WINDOW_WORD.finditer(low):
		before = low[:kind.start()]
		determiners = list(_DETERMINER.finditer(before))
		if not determiners:
			continue
		last = determiners[-1]
		words = before[last.end():].split()
		if len(words) > 4:
			continue
		return _Window(" ".join(words) if words else None)
	return None
_PAGE_NUMBER = re.compile(rf"\b(?:page|tab|tab page|property page)\s+(?:number\s+)?{_NUMBER}\b", re.IGNORECASE)
_PAGE_ORDINAL = re.compile(rf"\b(?:the\s+)?{_ORDINAL}\s+(?:page|tab|tab page|property page)\b", re.IGNORECASE)
_PAGE_NAMED = re.compile(
	r"\b(?:the|its|that|this)\s+([\w'.&+-]+(?:\s+[\w'.&+-]+){0,3}?)\s+(?:tab|page|tab page|property page)\b", re.IGNORECASE)
_LABEL_SAID = re.compile(
	r"\b(?:labell?ed|called|named|titled|marked|captioned|that says|which says|saying|reading|with the (?:label|name|text|caption)|"
	r"with (?:label|name|text)|for)\s+(?:the\s+)?[\"'“‘]?([^\"'”’,.;!?]{1,60}?)[\"'”’]?"
	r"(?=\s*(?:$|[,.;!?]|\b(?:on|in|of|at|inside|so|please|then|and|tab|page|dialog|window)\b))", re.IGNORECASE)
_QUOTED = re.compile(r"[\"“]([^\"”]{1,60})[\"”]|(?<![\w])'([^']{1,60})'(?![\w])")
_NTH = re.compile(rf"\b(?:the\s+)?{_ORDINAL}\s+(?:one|(?:{_KIND_WORDS}))\b|\b(?:{_KIND_WORDS})\s+(?:number\s+)?(\d{{1,2}})\b", re.IGNORECASE)
_TYPING = re.compile(r"\b(type|write|enter|fill (?:in|out)|so i can type|to type|to write|search)\b", re.IGNORECASE)
_BEST = re.compile(
	r"\b(?:most|more|best|first|main)\s+(?:useful|helpful|likely|important|sensible|obvious)?\s*(?:control|thing|item|place|spot|option|button|field)\b"
	r"|\bsomewhere\s+(?:useful|helpful|sensible|i can (?:work|start|type))\b|\bwhere (?:i|you) (?:should|can|need to) (?:be|start)\b"
	r"|\bwhere (?:should|can|do|would) (?:i|we) (?:start|begin|be)\b"
	r"|\bsomething i can (?:use|work|press|type)\b|\bfirst (?:control|thing|item)\b", re.IGNORECASE)
# Words that say where, or what to do, and are no part of a label.
_NOT_LABEL = frozenset((
	"put", "place", "take", "bring", "get", "drop", "land", "move", "send", "leave", "set", "park", "stick", "plonk", "pop",
	"me", "us", "on", "in", "into", "at", "to", "onto", "inside", "over", "back", "right", "straight", "focus", "refocus",
	"cursor", "caret", "keyboard", "nvda", "nvdas", "go", "jump", "navigate", "skip", "switch", "head", "tab", "the", "a", "an",
	"my", "this", "that", "its", "of", "for", "please", "i", "want", "need", "would", "like", "be", "wanna", "so", "can",
	"type", "write", "there", "then", "and", "now", "just", "end", "up", "page", "number", "one", "dialog", "dialogue",
	"window", "control", "item", "thing", "with", "where", "is", "it", "could", "you"))
_SPLIT_WORDS = re.compile(r"[a-z0-9']+")


def _words(text):
	return _SPLIT_WORDS.findall(str(text or "").lower())


def _number(text):
	text = str(text or "").lower()
	if text.isdigit():
		return int(text)
	return _NUMBERS.get(text) or _ORDINALS.get(text)


def kindOf(role):
	"""The kind of a control by the role NVDA gives it, or ""."""
	role = str(role or "").upper()
	for kind, _words, roles, _web, _overlay in KINDS:
		if role in roles:
			return kind
	return ""


def kindOfWord(words):
	"""The kind the user's words name, or ""."""
	text = str(words or "").lower()
	for kind, pattern, *_rest in KINDS:
		if re.search(rf"\b(?:{pattern})\b", text):
			return kind
	return ""


def rolesOf(kind):
	return next((roles for name, _words, roles, _web, _overlay in KINDS if name == kind), ())


def webKindsOf(kind):
	return next((web for name, _words, _roles, web, _overlay in KINDS if name == kind), ())


def overlayRolesOf(kind):
	return next((roles for name, _words, _roles, _web, roles in KINDS if name == kind), ())


def targets(text):
	"""The places a text names, whatever it asks: {"window": the name words of a dialog or window, "" for the one in
	front, or None; "page": {"number": n} (-1 for the last) or {"name": words}, or None; "kind": a kind id or "";
	"label": the words of a label or ""; "nth": which one of several of the kind (-1 for the last), or None}."""
	text = " ".join(str(text or "").split())
	low = text.lower()
	found = {"window": None, "page": None, "kind": "", "label": "", "nth": None}
	# Quoted words are a label as they are, and nothing in them is a kind, a page or a window.
	quoted = _QUOTED.search(text)
	if quoted:
		found["label"] = (quoted.group(1) or quoted.group(2) or "").strip()
	plain = _QUOTED.sub(" ", text)
	low = plain.lower()
	page = _PAGE_NUMBER.search(low) or _PAGE_ORDINAL.search(low)
	if page:
		found["page"] = {"number": _number(page.group(1))}
	else:
		named = _PAGE_NAMED.search(low)
		if named:
			name = " ".join(word for word in _words(named.group(1)) if word not in _NOT_LABEL and word not in _ORDINALS)
			if name and not kindOfWord(name):
				found["page"] = {"name": name}
	window = _windowOf(low)
	if window:
		name = window.group(1)
		if name is None:
			found["window"] = ""
		else:
			# "page two in the advanced dialog": the name is what is left after the page, a kind and the place words.
			words = [word for word in _words(name) if word not in _NOT_LABEL and word not in _ORDINALS
				and word not in _NUMBERS and not word.isdigit()]
			words = [word for word in words if not kindOfWord(word)]
			found["window"] = " ".join(words)
	kind = ""
	kindAt = None
	for name, pattern, *_rest in KINDS:
		hit = re.search(rf"\b(?:{pattern})\b", low)
		if hit and (kindAt is None or hit.start() < kindAt.start() or (hit.start() == kindAt.start() and hit.end() > kindAt.end())):
			kind, kindAt = name, hit
	# "the Connection tab" is a page, "page two" too: neither is a kind of control.
	found["kind"] = kind
	nth = _NTH.search(low)
	if nth:
		found["nth"] = _number(nth.group(1) or nth.group(2))
	if not found["label"]:
		said = _LABEL_SAID.search(plain)
		if said and kindOfWord(said.group(1)) != said.group(1).strip().lower():
			label = " ".join(word for word in said.group(1).split() if word.lower() not in ("the", "a", "an"))
			if label and label.lower() not in _NOT_LABEL:
				found["label"] = label
	if not found["label"] and kindAt is not None and re.match(r"(search|password|message)\b", kindAt.group(0)):
		# "The search box", "the password field" and "the message body" say their label in the kind's own words.
		found["label"] = kindAt.group(0).split()[0]
	if not found["label"] and kindAt is not None:
		# The words right before the kind: "the proxy server edit field", "the Save button".
		before = low[:kindAt.start()]
		cut = max(before.rfind(" the "), before.rfind(" a "), before.rfind(" an "), before.rfind(" my "), before.rfind(" that "),
			before.rfind(" this "))
		chunk = before[cut:] if cut >= 0 else before
		words = [word for word in _words(chunk) if word not in _NOT_LABEL and word not in _ORDINALS and not word.isdigit()]
		words = [word for word in words if word not in _NUMBERS]
		if found["window"]:
			taken = set(_words(found["window"]))
			words = [word for word in words if word not in taken] if len(words) > len(taken) else words
		if words:
			found["label"] = " ".join(words)
	return found


def wish(part):
	"""Where the user's own words ask to be put, or None when they ask for no place, or for more than being put there:
	the targets of targets(), with "typing": whether they want to type there, and "best": whether they asked for the
	most useful place rather than a named one. A part that only asks something, names a web address, a heading or a
	part of a page, or a part of Windows itself, is None: other jobs do those."""
	text = computer.own(part) if hasattr(computer, "own") else str(part or "")
	text = " ".join(str(text or "").split())
	if not text or not _PUT_RE.search(text) or _ASKS.match(text):
		return None
	if _NOT_THIS.search(_QUOTED.sub(" ", text)):
		return None
	if hasattr(computer, "windowsPart") and computer.windowsPart(text) is not None:
		return None
	if _DOES_MORE.search(text):
		return None
	found = targets(text)
	found["typing"] = bool(_TYPING.search(text)) or found["kind"] in TYPED
	found["best"] = bool(_BEST.search(text)) and not found["label"]
	if found["best"]:
		return found
	if not (found["kind"] or found["page"] or found["window"] is not None or found["label"]):
		return None
	# "Go to the Accessibility dialog" alone is a window to switch to; "go to the X" alone names nothing to be on.
	if found["window"] is not None and not (found["kind"] or found["page"] or found["label"]) and not re.search(
			r"\b(?:put|place|take|bring|drop|land|leave|set|park) me\b", text, re.IGNORECASE):
		return None
	if found["kind"] == "" and found["page"] is None and found["window"] is None:
		# A label alone: only where the words put the user or the focus there, not "go to Gmail".
		if not re.search(r"\b(?:me|focus|cursor|caret)\b", text, re.IGNORECASE):
			return None
	return found


def pickPage(names, page):
	"""Which page of a dialog is meant: the index among its tabs in order, or None. names: the tabs' names."""
	if not page or not names:
		return None
	number = page.get("number")
	if number is not None:
		if number == -1:
			return len(names) - 1
		return number - 1 if 1 <= number <= len(names) else None
	found = controls.pick(page.get("name") or "", list(names))
	return found[0] if len(found) == 1 else (found[0] if found else None)


def windowFits(title, name):
	"""Whether a window's title is the one the user named: every telling word of the name is in the title."""
	if name is None or name == "":
		return True
	wanted = [word for word in _words(name) if word not in ("settings", "options")] or _words(name)
	have = set(_words(title))
	return bool(wanted) and all(word in have or word.rstrip("s") in have for word in wanted)


def opener(labels, name):
	"""Which button of the window in front opens the named dialog: the index, or None. "Advanced..." for "the advanced
	dialog". A label that ends in three dots says that it opens a window, and wins among equals."""
	if not name:
		return None
	found = controls.pick(name, list(labels))
	if not found:
		return None
	return sorted(found, key=lambda index: (0 if str(labels[index]).rstrip().endswith(("...", "…")) else 1, index))[0]


def pickControls(items, found):
	"""Which controls fit, as indexes, the best first. items: [{"label", "kind"}] in reading order. found: a wish."""
	kind, label, nth = found.get("kind") or "", found.get("label") or "", found.get("nth")
	pool = [index for index, item in enumerate(items) if not kind or item.get("kind") == kind]
	if label:
		labels = [items[index].get("label") or "" for index in pool]
		chosen = [pool[index] for index in controls.pick(label, labels)]
		if not chosen and kind:
			# The label may belong to a control of another kind than the user said: "the Proxy box" is a combo box.
			allLabels = [item.get("label") or "" for item in items]
			chosen = controls.pick(label, allLabels)
		pool = chosen
	if nth is not None and pool:
		if nth == -1:
			return [pool[-1]]
		return [pool[nth - 1]] if 1 <= nth <= len(pool) else []
	return pool


# What makes an item likely to help when the user named none, each with what is said about it. Plain code, from the
# words of the request, the program and window, the kind and label of the item, whether the program marks it, its colour.
_GAME_START = re.compile(r"\b(play|continue|resume|start|new game|single ?player|campaign|load game|story|begin)\b", re.IGNORECASE)
_GOES_ON = re.compile(r"^\W*(ok|okay|next|continue|yes|done|finish|save|apply|close|start|install|sign in|log in|search|go|submit|send|open)\b",
	re.IGNORECASE)
_LATER = re.compile(r"^\W*(cancel|no|back|skip|later|not now|decline|dismiss|close|exit|quit)\b", re.IGNORECASE)


def helpful(items, context):
	"""The items ranked by how likely each is to help, as [(index, reason)], the best first, never an item that is
	unavailable or hidden. items: [{"label", "kind", "states" (NVDA's state names), "marked" (the program marks it: it is
	focused, selected or highlighted in its picture), "colourful" (its colour stands out from the window's)}] in reading
	order. context: {"words": the request, "game": whether a game is in front, "dialog": whether a dialog is, "typing":
	whether the user wants to type}. The reason is a few words for the user: why this item."""
	asked = {word for word in _words(context.get("words")) if word not in _NOT_LABEL and len(word) > 2}
	scored = []
	for index, item in enumerate(items):
		states = set(item.get("states") or ())
		if states & {"UNAVAILABLE", "INVISIBLE", "OFFSCREEN", "DEFUNCT"}:
			continue
		label, kind = str(item.get("label") or ""), item.get("kind") or ""
		score, reasons = 0.0, []
		shared = asked & set(_words(label))
		if shared:
			score += 5 * len(shared)
			reasons.append("its name has words of your request")
		if item.get("marked") or states & {"FOCUSED", "SELECTED", "DEFAULT"}:
			score += 3
			reasons.append("the program marks it as the current or default one")
		if context.get("typing") and kind in TYPED:
			score += 3
			if not item.get("value"):
				score += 1
			reasons.append("you can type in it")
		if context.get("game") and _GAME_START.search(label):
			score += 3
			reasons.append("it is where a game usually goes on")
		elif (context.get("dialog") or context.get("game")) and _GOES_ON.match(label):
			score += 2
			reasons.append("it is the usual way on in a window like this")
		if _LATER.match(label):
			score -= 1
		if "REQUIRED" in states and not item.get("value"):
			score += 2
			reasons.append("it must be filled in and is empty")
		# What a sighted person's eye goes to first, said in words: the item that is larger than the others, and the one
		# whose colour stands out from the window's own.
		if item.get("large"):
			score += 1.5
			reasons.append("it is larger than the other items, so it is what the eye goes to first")
		if item.get("colourful"):
			score += 1
			reasons.append(f"its colour, {item['colourful']}, stands out" if isinstance(item.get("colourful"), str)
				else "its colour stands out")
		if item.get("warning"):
			score += 2
			reasons.append("it shows a warning or an error")
		if kind in ("field", "combo", "list", "button", "check", "radio", "link", "tree", "slider", "spin", "menu", "table"):
			score += 0.5
		if not label:
			score -= 2
		# Earlier in reading order wins among equals.
		scored.append((-score, index, reasons[0] if reasons else "it is the first control in reading order"))
	scored.sort()
	return [(index, reason) for _score, index, reason in scored]


# --- The way there, learned and read again ---

def routeLine(label, kindSaid, page="", window=""):
	"""The line written on the program's scratchpad after the user was put on a control: where it is."""
	where = []
	if page:
		where.append(f"on the page {page}")
	if window:
		where.append(f"of the window \"{window}\"")
	if not where:
		return ""
	return f"The {kindSaid} \"{label}\" is " + " ".join(where) + "."


def routeFrom(lines, found):
	"""Where a line the user or VisionClaw wrote says the control is: {"window", "page"}, or None. Only a line that has
	every telling word of the label, and names a page or a window."""
	label = [word for word in _words(found.get("label")) if word not in _NOT_LABEL]
	if not label:
		return None
	for line in lines or ():
		text = str(line or "")
		if not all(word in set(_words(text)) for word in label):
			continue
		place = targets(text)
		window = place["window"]
		quoted = re.search(r"window \"([^\"]{1,80})\"", text)
		if quoted:
			window = quoted.group(1)
		page = place["page"]
		named = re.search(r"\bon the page ([^.,\"]{1,40}?)(?: of the window|\.|,|$)", text)
		if named:
			page = {"number": _number(named.group(1))} if _number(named.group(1)) else {"name": named.group(1).strip()}
		if page or window:
			return {"window": window or None, "page": page}
	return None


# --- What the user is told ---

def kindSaid(kind, roleText=""):
	return roleText or KIND_SAID.get(kind, "control")


def wantedText(found):
	"""What the user asked to be on, in words: the edit field "Proxy", on page 2, in the Advanced dialog."""
	parts = []
	what = KIND_SAID.get(found.get("kind") or "", "")
	label = found.get("label") or ""
	if found.get("best"):
		parts.append("the most useful control")
	elif label and what:
		parts.append(f"the {what} \"{label}\"")
	elif label:
		parts.append(f"\"{label}\"")
	elif what:
		nth = found.get("nth")
		parts.append(f"the {'last' if nth == -1 else _ORDINAL_SAID.get(nth, 'first')} {what}" if nth else f"a {what}")
	page = found.get("page") or {}
	if page.get("number"):
		parts.append("on the last page" if page["number"] == -1 else f"on page {page['number']}")
	elif page.get("name"):
		parts.append(f"on the page {page['name']}")
	if found.get("window"):
		parts.append(f"in the {found['window']} window")
	return " ".join(parts) or "that place"


_ORDINAL_SAID = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
	9: "ninth", 10: "tenth"}


def listText(labels, kind=""):
	"""The controls there are, said whole: the user picks from them."""
	named = [f"\"{label}\"" for label in labels if label]
	if not named:
		return ""
	what = KIND_SAID.get(kind, "control")
	plural = "es" if what.endswith("box") else "s"
	return f"The {what}{plural if len(named) > 1 else ''} there: " + ", ".join(named) + "."
