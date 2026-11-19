# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the places of Windows itself, read by plain code. A request is about something and somewhere. The
# somewhere is often not the window in front: the icons of the system tray, the programs on the taskbar, the icons
# on the desktop, the notifications, quick settings, the Start menu. A picture of the window in front cannot show
# them, and a small model that is asked to describe it says "I cannot see the system tray". So plain code reads
# from the user's own words which place is meant and what is wanted there (wish), and the add-on reads that place
# from what Windows itself tells screen readers about it (placetools.py), word for word, without a model.
# Asked for by the owner on 2026-11-18, after "tell me all objects that are currently in the system tray." was
# answered with "I cannot see the system tray in this image": "visionclaw must be even smarter and plan a lot
# smarter ... learn to generalize". So the place is a slot of its own, read the same way for every place, and the
# looking tools and the click use it too.
#
# What the add-on hands over for each thing it found is plain data (a dict): its name, its kind as Windows'
# number for it (KINDS), its class and automation id, where it is on the screen, the classes of the windows and
# elements above it (path), whether it is hidden, and its state where it has one (on, off, a value). Everything
# here sorts and words that data. No NVDA dependencies.

import re

from . import computer
from .memory import stem

# --- The places ---

# (id, name, words that name it, the part of Windows in computer.WINDOWS_PARTS whose keys go there, whether it is
# always on the screen). A place that is always there is read as it is; one that exists only while it is open
# (the Start menu, quick settings, the notification center, clipboard history) is opened with its own key first,
# read, and left open for the user, who is told that Escape closes it.
TRAY, TASKBAR, DESKTOP = "tray", "taskbar", "desktop"
PLACES = (
	(TRAY, "the notification area", (
		r"system ?tray", r"notification area", r"systray", r"(?:the|my|windows'?s?) tray", r"tray icons?",
		r"hidden icons", r"notification icons", r"status icons", r"icons? (?:in|on|at) the (?:bottom|lower) right( corner)?"),
		"tray", True),
	(TASKBAR, "the taskbar", (r"task ?bar",), "taskbar", True),
	(DESKTOP, "the desktop", (r"desktop",), None, True),
	("start", "the Start menu", (r"start ?menu", r"start screen", r"windows start"), "start", False),
	("quick-settings", "quick settings", (r"quick settings", r"action cent(?:er|re)"), "quick-settings", False),
	("notifications", "the notification center", (
		r"notification (?:center|centre|panel|list|pane)", r"notifications", r"alerts? (?:from|in) windows"),
		"notifications", False),
	("clipboard", "clipboard history", (r"clipboard history",), "clipboard", False),
)
_IDS = tuple(place[0] for place in PLACES)


def placeOf(ident):
	"""(name, words, part of Windows, always there) of a place, by its id."""
	for one, name, words, part, always in PLACES:
		if one == ident:
			return name, words, part, always
	raise KeyError(ident)


def nameOf(ident):
	return placeOf(ident)[0]


def always(ident):
	"""Whether a place is always on the screen, and is read without opening anything."""
	return placeOf(ident)[3]


# What is wanted of a place.
LIST, COUNT, HAS = "list", "count", "has"

# Words that ask to be told something. Somewhere in the request, before or after the place.
_READS = re.compile(
	r"\b(tell|list|name|say|read|enumerate|report|describe|announce|speak|identify|check|summari[sz]e|count|"
	r"what(?:'s| is| are|s)?|which|any|anything|how many|number of|is there|are there|do i have|does .{0,30} have|"
	r"is .{1,40} (?:in|on|running|showing)|are .{1,40} (?:in|on|running|showing))\b", re.IGNORECASE)
# Words for the things in a place. With one of them, "show me" asks what is there, not to go there.
_THINGS = (
	r"objects?|icons?|items?|things?|programs?|apps?|applications?|entries|buttons?|shortcuts?|stuff|everything|"
	r"anything|notifications?|pinned|running|open|tiles?|options?|toggles?|switches|sliders?")
_SHOWS = re.compile(rf"\b(show|display|give|get|bring)\b(?: me)?\b.*\b({_THINGS})\b|\bshow me what\b", re.IGNORECASE)
# What is no wish to be told what is there: changing, clicking, closing, its settings, or how something looks.
_NOT = re.compile(
	r"\b(click\w*|double[- ]?click\w*|right[- ]?click\w*|press|push|tap|activate|drag|close|hide|unhide|turn (?:on|off)|"
	r"switch (?:on|off)|enable|disable|remove|delete|unpin|pin (?:it|this|to)|customi[sz]e|rearrange|resize|move|change|"
	r"settings?(?<!quick settings)|preferences|colou?rs?|look(?:s)? like|appearance|wallpaper|background|theme|"
	r"transparent|picture|image|photo|screenshot|empty|clear|dismiss|go to|take me|switch to|open (?:the |my )?\w+$)\b",
	re.IGNORECASE)
# "What is the system tray", "what does the taskbar do": a question about what a place is, not what is in it.
_WHAT_IS = r"^\W*(?:{polite})?(?:what|explain)(?:'s| is| are| does)? (?:the |a |an |my )?(?:windows'?s? )?{place}\W*(?:for|do|mean|used for|exactly)?\W*$"
# Files and folders on the desktop are the user's own files (computer.aboutFiles), not the icons there.
_FILES = re.compile(r"\b(files?|folders?|documents?|pdfs?|downloads?|photos|pictures)\b", re.IGNORECASE)
_DESKTOP_THINGS = re.compile(rf"\b({_THINGS})\b", re.IGNORECASE)


def _clean(part):
	return " ".join(computer.own(part).lower().replace("’", "'").split())


def named(part):
	"""The places a request names, in the order it names them, at most two."""
	text = _clean(part)
	found = []
	for ident, _name, words, _part, _always in PLACES:
		for pattern in words:
			hit = re.search(rf"\b{pattern}\b", text)
			if hit:
				found.append((hit.start(), ident))
				break
	# "The hidden icons" are the tray's, "the task bar" is no desktop, and a place is named once.
	found.sort()
	places = []
	for _start, ident in found:
		if ident not in places:
			places.append(ident)
	return places[:2]


def _asksWhatIs(text, ident):
	words = "|".join(placeOf(ident)[1])
	return bool(re.match(_WHAT_IS.format(polite=computer._POLITE, place=f"(?:{words})"), text))


def wish(part):
	"""What the user's own words want to know about a place of Windows itself, as {"places": [ids], "how": LIST,
	COUNT or HAS, "thing": the words of a thing asked about or ""}, or None when the words ask for no such thing:
	to open or go to it (computer.windowsPart), to click something in it, to change it, how it looks, how to do
	something there, or what it is."""
	text = _clean(part)
	places = named(text)
	if not places or computer._ASKS_HOW.search(text) or _NOT.search(text):
		return None
	if any(_asksWhatIs(text, ident) for ident in places):
		return None
	if not (_READS.search(text) or _SHOWS.search(text)):
		return None
	if places == [DESKTOP] and (_FILES.search(text) or not _DESKTOP_THINGS.search(text)):
		# "What is on my desktop" and "which files are on my desktop" are about the user's own files there.
		return None
	how = LIST
	if re.search(r"\b(how many|number of|count)\b", text):
		how = COUNT
	thing = _thingOf(text, places)
	if thing:
		how = HAS
	return {"places": places, "how": how, "thing": thing}


# The things that are asked about by name: "is Dropbox in the system tray", "does my taskbar have Firefox".
_HAS = (
	re.compile(r"\b(?:is|are) (?:there )?(?:an? |the |my )?(?P<thing>[\w' .+&-]{2,40}?)(?: icons?| programs?| apps?)? "
		r"(?:still )?(?:in|on|running in|showing in|shown in|pinned to|pinned on|open on|there in)\b", re.IGNORECASE),
	re.compile(r"\b(?:does|do) (?:the |my )?[\w ]{2,30}? (?:have|show|hold|contain) (?:an? |the |my )?(?P<thing>[\w' .+&-]{2,40}?)"
		r"(?: icons?| programs?| apps?)?\W*$", re.IGNORECASE),
	re.compile(r"\b(?:find|look for|check for|search for|is there) (?:an? |the |my )?(?P<thing>[\w' .+&-]{2,40}?)"
		r"(?: icons?| programs?| apps?)? (?:in|on)\b", re.IGNORECASE),
)
# Words that are no thing's name.
_GENERIC = frozenset((
	"there", "it", "they", "them", "this", "that", "these", "those", "any", "anything", "something", "everything", "all",
	"what", "which", "who", "icon", "icons", "item", "items", "object", "objects", "thing", "things", "program",
	"programs", "app", "apps", "application", "applications", "entry", "entries", "notification", "notifications",
	"button", "buttons", "shortcut", "shortcuts", "stuff", "currently", "now", "still", "open", "running", "pinned",
	"new", "unread", "more", "other", "hidden", "a", "an", "the", "my", "some", "of", "many", "how", "much"))


def _thingOf(text, places):
	for pattern in _HAS:
		found = pattern.search(text)
		if not found:
			continue
		words = [word for word in found.group("thing").split() if word not in _GENERIC]
		# The place itself is no thing in it.
		named = " ".join(words)
		if not words or any(re.fullmatch(rf"(?:{'|'.join(placeOf(ident)[1])})", named) for ident in places):
			continue
		return named
	return ""


def asks(part):
	"""Whether the words ask what is in a place of Windows itself."""
	return wish(part) is not None


_CLICKS = re.compile(
	r"\b(click|double[- ]?click|right[- ]?click|middle[- ]?click|press|push|tap|activate|choose|select|hover(?: over)?|"
	r"point at|open)\b", re.IGNORECASE)
_FILL = frozenset(("on", "the", "a", "an", "my", "please", "can", "could", "would", "will", "you", "i", "want", "to",
	"with", "mouse", "using", "left", "and", "then", "for", "me", "just", "now", "visionclaw"))


def clicksIn(part):
	"""The place of Windows that holds what the words ask to have clicked: "click the volume icon in the system
	tray", "right-click Dropbox in the notification area", "double-click the Recycle Bin on the desktop". None when
	the words name no thing there, or name a part of Windows of its own ("the Start button on the taskbar")."""
	text = _clean(part)
	ident = within(text)
	if ident is None or not _CLICKS.search(text) or computer._ASKS_HOW.search(text):
		return None
	words = "|".join(placeOf(ident)[1])
	head = re.split(rf"\b(?:in|on|from|inside|at) (?:the |my |windows'?s? )?(?:{words})\b", text, maxsplit=1)[0]
	thing = [word for word in re.findall(r"[\w'+.-]+", _CLICKS.sub(" ", head)) if word not in _GENERIC and word not in _FILL]
	if not thing or computer.windowsPart("click " + " ".join(thing), loose=True) is not None:
		return None
	return ident


def within(part):
	"""The place of Windows that the words put what they name in, for a click or a list of items there: "the
	volume icon in the system tray", "the Firefox button on the taskbar". Only the places that are always on the
	screen, and only when the place is said with in, on or from; else None."""
	text = _clean(part)
	for ident in named(text):
		if not always(ident):
			continue
		words = "|".join(placeOf(ident)[1])
		if re.search(rf"\b(?:in|on|from|inside|at) (?:the |my |windows'?s? )?(?:{words})\b", text):
			return ident
	return None


# --- What Windows reports, sorted ---

# Windows' own numbers for the kinds of things UI Automation reports (UIA_ButtonControlTypeId and the rest, read
# from Microsoft's page "Control Type Identifiers"), and how each is said.
KINDS = {
	50000: "button", 50001: "calendar", 50002: "check box", 50003: "combo box", 50004: "edit", 50005: "link",
	50006: "picture", 50007: "list item", 50008: "list", 50009: "menu", 50010: "menu bar", 50011: "menu item",
	50012: "progress bar", 50013: "radio button", 50014: "scroll bar", 50015: "slider", 50016: "spin button",
	50017: "status bar", 50018: "tab", 50019: "tab", 50020: "text", 50021: "tool bar", 50022: "tool tip",
	50023: "tree", 50024: "tree item", 50025: "custom", 50026: "group", 50027: "thumb", 50028: "data grid",
	50029: "data item", 50030: "document", 50031: "split button", 50032: "window", 50033: "pane", 50034: "header",
	50035: "header item", 50036: "table", 50037: "title bar", 50038: "separator",
}
# The kinds that are things a person finds and uses in a place; the rest only hold them.
_USED = frozenset((50000, 50002, 50003, 50005, 50007, 50011, 50013, 50015, 50016, 50019, 50024, 50029, 50031))
# Names of things on the taskbar and in the tray that are no icon of a program: they are said apart.
_CHEVRON = re.compile(r"^(show|hide) hidden icons$|notification chevron|^show more icons$", re.IGNORECASE)
_SHOW_DESKTOP = re.compile(r"^show desktop$", re.IGNORECASE)
_CLOCK = re.compile(r"^clock\b", re.IGNORECASE)
# A name of a program's button on the taskbar of Windows 11: "Claude - 1 running window", "Microsoft Edge pinned".
_RUNNING = re.compile(r"^(?P<name>.+?) - (?P<count>\d+) running windows?$", re.IGNORECASE)
_PINNED = re.compile(r"^(?P<name>.+?) pinned$", re.IGNORECASE)
# Classes that say where on the taskbar a thing is: Windows 11's own, and those of Windows 10's taskbar.
_TRAY_CLASSES = ("TrayNotifyWnd", "SysPager", "NotifyIconOverflowWindow", "TopLevelWindowForOverflowXamlIsland")
_TASK_CLASSES = ("MSTaskListWClass", "MSTaskSwWClass")
# Bidirectional marks Windows puts into dates and times: they say nothing.
_MARKS = re.compile(r"[‎‏‪-‮⁦-⁩]")
MAX_SAID = 60
# What one answer may be at most; tools.RESULT_CHARS cuts at 1500, and the keys for next time come last.
MAX_CHARS = 1300


def clean(name):
	"""A name as Windows reports it, said in one line: its line breaks become commas, its hidden marks go."""
	text = _MARKS.sub("", str(name or ""))
	parts = [" ".join(line.split()) for line in re.split(r"[\r\n]+", text)]
	return ", ".join(part for part in parts if part)


def _path(item):
	return tuple(item.get("path") or ())


def isTray(item):
	"""Whether a thing Windows reports on the taskbar is an icon of the notification area."""
	cls = str(item.get("cls") or "")
	return (item.get("aid") == "SystemTrayIcon" or cls.startswith("SystemTray.") or item.get("hidden") is True
		or any(one in _path(item) for one in _TRAY_CLASSES))


def isProgram(item):
	"""Whether a thing on the taskbar is the button of a program, pinned or running."""
	return (item.get("cls") == "Taskbar.TaskListButtonAutomationPeer" or str(item.get("aid") or "").startswith(("Appid:", "Window:"))
		or any(one in _path(item) for one in _TASK_CLASSES))


def usable(items):
	"""The things a person finds and uses, with a name, each once, in the order Windows gave them."""
	seen = set()
	kept = []
	for item in items or ():
		name = clean(item.get("name"))
		if not name or (item.get("kind") is not None and item.get("kind") not in _USED):
			continue
		key = (name.lower(), bool(item.get("hidden")))
		if key in seen:
			continue
		seen.add(key)
		kept.append(dict(item, name=name))
	return kept


def tray(items):
	"""The notification area sorted: (icons that are shown, icons that are hidden, the clock or "", whether there
	is a button that shows the hidden icons)."""
	shown, hidden, clock, chevron = [], [], "", False
	for item in usable(items):
		if not isTray(item):
			continue
		name = item["name"]
		if _CHEVRON.search(name):
			chevron = True
		elif _SHOW_DESKTOP.search(name):
			continue
		elif _CLOCK.search(name):
			clock = clock or name
		elif item.get("hidden"):
			hidden.append(name)
		else:
			shown.append(name)
	# An icon that shows among the hidden ones too is said where it is shown.
	hidden = [name for name in hidden if name not in shown]
	return shown, hidden, clock, chevron


def taskbar(items):
	"""The taskbar sorted: (its own buttons: Start, Search and the like; the programs as (name, how), how being
	"pinned", "1 running window" or ""; how many icons the notification area has)."""
	own, programs, icons = [], [], 0
	for item in usable(items):
		if isTray(item):
			if not (item.get("hidden") or _CHEVRON.search(item["name"]) or _SHOW_DESKTOP.search(item["name"])
					or _CLOCK.search(item["name"])):
				icons += 1
			continue
		name = item["name"]
		if isProgram(item):
			running, pinned = _RUNNING.match(name), _PINNED.match(name)
			if running:
				count = int(running.group("count"))
				programs.append((running.group("name"), f"{count} running window" + ("" if count == 1 else "s")))
			elif pinned:
				programs.append((pinned.group("name"), "pinned"))
			else:
				programs.append((name, ""))
		elif not _SHOW_DESKTOP.search(name) and item.get("kind") in (50000, 50031, None):
			own.append(name)
	return own, programs, icons


def _stateText(item):
	state = str(item.get("state") or "").strip()
	return f"{item['name']}, {state}" if state else item["name"]


def opened(items):
	"""What is in a part of Windows that was opened, as names with their state, each once."""
	return [_stateText(item) for item in usable(items)]


# --- In words ---

def many(count, word, plural=None):
	return f"{count} {word if count == 1 else (plural or word + 's')}"


def _listed(names, limit=MAX_SAID):
	shown = list(names[:limit])
	rest = len(names) - len(shown)
	return "; ".join(shown) + (f"; and {rest} more" if rest > 0 else "")


def _keys(ident):
	"""How the user goes there with the keyboard, from computer.WINDOWS_PARTS; "" for the desktop."""
	part = placeOf(ident)[2]
	if ident == DESKTOP:
		return "To go to the desktop yourself, press Windows+D; the arrow keys then move between its icons."
	if part is None:
		return ""
	name, _keys, said, there = computer.windowsPartOf(part)
	return f"To go to {name} yourself, press {said}. {there}"


def _fits(thing, name):
	"""Whether a name is the thing asked about: every telling word of the thing is in it, or nearly."""
	wanted = [stem(word) for word in re.findall(r"[a-z0-9+]+", thing.lower()) if word not in _GENERIC]
	have = [stem(word) for word in re.findall(r"[a-z0-9+]+", name.lower())]
	if not wanted:
		return False
	return all(any(word == other or (len(word) >= 4 and other.startswith(word)) for other in have) for word in wanted)


def found(wanted, names):
	"""The names that are the thing asked about."""
	return [name for name in names if _fits(wanted, name)]


def _fitted(text):
	"""An answer cut to what a tool may give back, at the end of a listed name."""
	if len(text) <= MAX_CHARS:
		return text
	cut = text[:MAX_CHARS].rsplit("; ", 1)[0]
	return cut + "; and more."


def trayText(sorted_, how=LIST, thing="", hiddenRead=True):
	"""What the notification area holds, in sentences. sorted_: what tray() gives. hiddenRead: whether the hidden
	icons could be read; when not, the user is told how to get to them."""
	shown, hidden, clock, chevron = sorted_
	name = nameOf(TRAY)
	every = shown + hidden
	if thing:
		hits = found(thing, every)
		if hits:
			where = "among the hidden icons" if all(hit in hidden for hit in hits) else "shown on the taskbar"
			head = f"Yes. In {name}, {where}: {_listed(hits)}."
		elif not every and not clock:
			return ""
		else:
			unread = " The hidden icons could not be read." if chevron and not hiddenRead else ""
			head = f"No icon in {name} is called {thing}.{unread} These are there: {_listed(every) or 'nothing but the clock'}."
		return _fitted(f"{head} {_keys(TRAY)}")
	if not every and not clock:
		return ""
	if how == COUNT:
		head = f"{name.capitalize()} has {many(len(shown), 'icon')} shown" + (
			f" and {len(hidden)} hidden behind Show hidden icons" if hidden else "") + "."
	else:
		head = f"{name.capitalize()} has {many(len(shown), 'icon')} shown on the taskbar."
	parts = [head]
	if how != COUNT or len(every) <= 12:
		if shown:
			parts.append(f"{'Shown' if how == COUNT else 'They are'}: {_listed(shown)}.")
		if hidden:
			parts.append(f"Hidden behind Show hidden icons, {many(len(hidden), 'more icon')}: {_listed(hidden)}.")
	if chevron and not hidden:
		parts.append(
			"There are more icons behind the button Show hidden icons, which could not be read." if not hiddenRead
			else "Show hidden icons has no icons in it.")
	if clock:
		parts.append(f"The clock says: {clock[len('clock'):].strip(' ,:') or clock}.")
	parts.append(_keys(TRAY))
	return _fitted(" ".join(parts))


def taskbarText(sorted_, how=LIST, thing=""):
	"""What the taskbar holds, in sentences. sorted_: what taskbar() gives."""
	own, programs, icons = sorted_
	name = nameOf(TASKBAR)
	said = [f"{program}, {state}" if state else program for program, state in programs]
	if thing:
		hits = found(thing, [program for program, _state in programs])
		if not programs and not own:
			return ""
		if hits:
			states = [f"{program}, {state}" if state else program for program, state in programs if program in hits]
			head = f"Yes. On {name}: {_listed(states)}."
		else:
			head = f"No program on {name} is called {thing}. These are there: {_listed(said) or 'none'}."
		return _fitted(f"{head} {_keys(TASKBAR)}")
	if not programs and not own:
		return ""
	parts = [f"{name.capitalize()} has {many(len(programs), 'program')}" + (f": {_listed(said)}." if said and how != COUNT else ".")]
	if own:
		parts.append(f"Its own buttons: {_listed(own)}.")
	if icons:
		parts.append(f"{nameOf(TRAY).capitalize()} at its end has {many(icons, 'icon')}; ask what is in the system tray to hear them.")
	parts.append(_keys(TASKBAR))
	return _fitted(" ".join(parts))


def listText(ident, names, how=LIST, thing="", left=False):
	"""What a place holds that is a plain list of names: the desktop, or a part of Windows that was opened. left:
	the part was opened to be read, and is left open."""
	name = nameOf(ident)
	opened_ = (f" {name[0].upper() + name[1:]} is open now; Escape closes it." if left else "")
	if thing:
		hits = found(thing, names)
		if not names:
			return ""
		head = (f"Yes. On {name}: {_listed(hits)}." if hits
			else f"Nothing on {name} is called {thing}. These are there: {_listed(names)}.")
		return _fitted(f"{head}{opened_} {_keys(ident)}".strip())
	if not names:
		return ""
	word = "icon" if ident == DESKTOP else "item"
	head = f"{name[0].upper() + name[1:]} has {many(len(names), word)}" + (f": {_listed(names)}." if how != COUNT or len(names) <= 12 else ".")
	return _fitted(f"{head}{opened_} {_keys(ident)}".strip())


def nothingText(ident, opened_=False):
	"""What is said when Windows told nothing about a place."""
	name = nameOf(ident)
	if opened_:
		return (
			f"{name[0].upper() + name[1:]} was opened, but Windows did not say what is in it. NVDA is there now: use the "
			f"arrow keys and Tab to move through it, and Escape to close it.")
	return (
		f"Windows did not say what is in {name}. {_keys(ident)}".strip())


def notOpenedText(ident):
	"""What is said when a part of Windows that must be opened to be read did not open."""
	name = nameOf(ident)
	return f"{name[0].upper() + name[1:]} did not open, so it could not be read. {_keys(ident)}".strip()
