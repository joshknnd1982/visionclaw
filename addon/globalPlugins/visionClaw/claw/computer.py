# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - working the computer itself for the user: opening a program, a folder, the Recycle Bin or a page
# of Windows Settings by its name; how full the Recycle Bin is and whether it is worth emptying; the volume of
# the computer; the windows that are open; the files in the user's folders; facts about the computer; locking,
# restarting and shutting down; and requests that depend on something ("if you see the Recycle Bin, open it").
# Everything here is plain code: which thing is meant, how loud, which window, which folder and what the
# condition is are read from the user's own words, so that a small model has at most to choose among the few
# things that were found. Nothing here touches Windows; that is done in computertools.py. No NVDA dependencies.

import re

from . import match

# What the planner puts after a part that needs the part before it to be understood (planner.settle).
_FOLLOWS = re.compile(r"\s*\(this follows: .*\)\s*$", re.IGNORECASE | re.DOTALL)
_POLITE = r"(?:(?:hey |ok |okay )?visionclaw[,:]?\s+)?(?:please\s+)?(?:(?:can|could|would|will) you\s+)?(?:please\s+)?"
# Verbs a thing to do begins with. Used to tell where one thing to do ends and the next begins, and where the
# condition of a request ends and what is to be done begins.
ACTS = (
	"open", "close", "click", "double-click", "right-click", "press", "type", "tell", "say", "read", "turn", "set",
	"make", "check", "go", "switch", "start", "launch", "run", "show", "find", "search", "minimize", "minimise",
	"maximize", "maximise", "restore", "scroll", "empty", "look", "describe", "list", "give", "put", "change",
	"increase", "decrease", "lower", "raise", "mute", "unmute", "lock", "restart", "reboot", "shut", "delete", "remove",
	"play", "pause", "stop", "copy", "paste", "save", "download", "remember", "forget", "drag", "hover", "select",
	"choose", "bring", "take", "move", "zoom", "write", "enter", "fill", "sign", "log", "let", "ask", "see", "get",
	"announce", "report", "name", "label", "fix", "inspect", "learn", "update", "add", "activate", "visit", "browse",
	"navigate", "focus", "hide", "clear", "do", "use", "speak", "summarize", "summarise", "count", "quit", "exit",
	"adjust", "locate", "pick", "toggle", "enable", "disable", "uncheck", "tick", "untick", "rename", "create",
	"install", "connect", "disconnect", "send", "print", "undo", "refresh", "reload", "reopen", "expand", "collapse",
	"confirm", "verify", "apply")
_ACT = "(?:" + "|".join(re.escape(verb) for verb in ACTS) + ")"
ACT = _ACT
STARTS_ACT = re.compile(
	rf"^\s*{_POLITE}(?:(?:i want you to|i need you to|i'd like you to|i would like you to)\s+)?"
	rf"(?:(?:please|and|then|also|now|just)\s+)*{_ACT}\b", re.IGNORECASE)


def own(part):
	"""A part of a request in the user's own words, without what the planner added to it."""
	return _FOLLOWS.sub("", " ".join(str(part or "").split())).strip()


def _plain(text):
	return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _has(text, phrase):
	"""Whether a phrase is in a text as whole words."""
	return f" {phrase} " in f" {text} " if phrase else False


# --- Sizes and numbers in words ---

def sizeText(count):
	"""A number of bytes the way it is said: 1.4 GB, 340 MB, 12 KB."""
	count = max(0, int(count or 0))
	for unit, size in (("TB", 1 << 40), ("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
		if count >= size:
			value = count / size
			return f"{value:.1f} {unit}" if value < 10 and unit in ("TB", "GB") else f"{round(value)} {unit}"
	return f"{count} bytes"


def many(count, one, more=None):
	return f"{count} {one if count == 1 else (more or one + 's')}"


def spanText(seconds):
	"""A length of time in words: 3 days and 4 hours, 2 hours and 10 minutes, 5 minutes."""
	minutes = max(0, int(seconds)) // 60
	days, hours, minutes = minutes // 1440, minutes % 1440 // 60, minutes % 60
	if days:
		return many(days, "day") + (f" and {many(hours, 'hour')}" if hours else "")
	if hours:
		return many(hours, "hour") + (f" and {many(minutes, 'minute')}" if minutes else "")
	return many(minutes, "minute")


# --- Things that can be opened ---

PLACE, SETTING, TOOL, PROGRAM, ON_DESKTOP, FILE, FOLDER = (
	"a place of Windows", "a page of Windows Settings", "a tool of Windows", "a program", "on your desktop", "a file",
	"a folder")
# Where a thing is opened from. Each is fixed here or found on the computer by plain code (computertools.py); a
# model only ever chooses among the ids of what was found, and never writes what is opened.
# The names after "shell:" are the folders' own names in Windows; each was seen to exist on Windows 11 on
# 2026-11-18. The pages of Settings are from Microsoft's page "Launch Windows Settings", read the same day: when
# they are brought up to date, read that page again, do not write an address from memory.
# (id, name, kind, what is opened, other words people use for it)
PLACES = (
	("recycle-bin", "Recycle Bin", PLACE, "shell:RecycleBinFolder", ("recycling bin", "recycle", "trash", "trash can", "wastebasket", "deleted files")),
	("desktop", "Desktop folder", PLACE, "shell:Desktop", ("desktop", "my desktop")),
	("documents", "Documents", PLACE, "shell:Personal", ("my documents", "documents folder", "document folder")),
	("downloads", "Downloads", PLACE, "shell:Downloads", ("my downloads", "downloads folder", "download folder")),
	("pictures", "Pictures", PLACE, "shell:My Pictures", ("my pictures", "pictures folder", "photos folder", "my photos")),
	("music", "Music", PLACE, "shell:My Music", ("my music", "music folder")),
	("videos", "Videos", PLACE, "shell:My Video", ("my videos", "videos folder", "video folder")),
	("this-pc", "This PC", PLACE, "shell:MyComputerFolder", ("my computer", "computer folder", "my drives", "drives")),
	("home", "Your user folder", PLACE, "shell:Profile", ("user folder", "home folder", "my user folder", "profile folder")),
	("control-panel", "Control Panel", PLACE, "shell:ControlPanelFolder", ("the control panel",)),
	("file-explorer", "File Explorer", TOOL, "explorer.exe", ("explorer", "windows explorer", "file manager", "my files")),
	("task-manager", "Task Manager", TOOL, "taskmgr.exe", ("the task manager",)),
	("notepad", "Notepad", TOOL, "notepad.exe", ()),
	("calculator", "Calculator", TOOL, "calc.exe", ("the calculator",)),
	("command-prompt", "Command Prompt", TOOL, "cmd.exe", ("cmd", "command line", "dos prompt")),
	("settings", "Windows Settings", SETTING, "ms-settings:", ("settings", "the settings", "settings app", "pc settings", "system settings", "computer settings")),
	("settings-sound", "Sound settings", SETTING, "ms-settings:sound", ("sound", "audio settings", "volume settings")),
	("settings-volume-mixer", "Volume mixer", SETTING, "ms-settings:apps-volume", ("the volume mixer", "app volume")),
	("settings-bluetooth", "Bluetooth settings", SETTING, "ms-settings:bluetooth", ("bluetooth", "bluetooth devices")),
	("settings-wifi", "Wi-Fi settings", SETTING, "ms-settings:network-wifi", ("wifi", "wi fi", "wifi settings", "wireless settings", "wireless")),
	("settings-network", "Network and internet settings", SETTING, "ms-settings:network-status", ("network settings", "internet settings", "network and internet")),
	("settings-display", "Display settings", SETTING, "ms-settings:display", ("display", "screen settings", "monitor settings")),
	("settings-update", "Windows Update", SETTING, "ms-settings:windowsupdate", ("update settings", "windows updates", "updates for windows")),
	("settings-apps", "Installed apps", SETTING, "ms-settings:appsfeatures", ("apps and features", "installed programs", "installed apps", "uninstall a program", "apps settings")),
	("settings-default-apps", "Default apps", SETTING, "ms-settings:defaultapps", ("default programs", "default apps settings")),
	("settings-startup", "Startup apps", SETTING, "ms-settings:startupapps", ("startup programs", "startup settings")),
	("settings-storage", "Storage settings", SETTING, "ms-settings:storagesense", ("storage", "disk settings")),
	("settings-power", "Power and sleep settings", SETTING, "ms-settings:powersleep", ("power settings", "sleep settings", "power and sleep")),
	("settings-battery", "Battery settings", SETTING, "ms-settings:batterysaver", ("battery saver", "battery settings")),
	("settings-notifications", "Notification settings", SETTING, "ms-settings:notifications", ("notifications", "notification settings")),
	("settings-printers", "Printers and scanners", SETTING, "ms-settings:printers", ("printers", "printer settings", "scanners")),
	("settings-mouse", "Mouse settings", SETTING, "ms-settings:mousetouchpad", ("mouse settings", "touchpad settings")),
	("settings-typing", "Typing settings", SETTING, "ms-settings:typing", ("typing", "keyboard settings")),
	("settings-date", "Date and time settings", SETTING, "ms-settings:dateandtime", ("date and time", "time settings", "clock settings", "time zone")),
	("settings-language", "Language settings", SETTING, "ms-settings:regionlanguage", ("language", "languages", "region and language")),
	("settings-accessibility", "Accessibility settings", SETTING, "ms-settings:easeofaccess-display", ("accessibility", "ease of access")),
	("settings-narrator", "Narrator settings", SETTING, "ms-settings:easeofaccess-narrator", ("narrator",)),
	("settings-personalization", "Personalization settings", SETTING, "ms-settings:personalization", ("personalization", "personalisation", "themes and colours")),
	("settings-background", "Background settings", SETTING, "ms-settings:personalization-background", ("wallpaper", "desktop background")),
	("settings-taskbar", "Taskbar settings", SETTING, "ms-settings:taskbar", ("taskbar",)),
	("settings-privacy", "Privacy settings", SETTING, "ms-settings:privacy", ("privacy",)),
	("settings-microphone", "Microphone privacy settings", SETTING, "ms-settings:privacy-microphone", ("microphone settings", "microphone permission")),
	("settings-camera", "Camera privacy settings", SETTING, "ms-settings:privacy-webcam", ("camera settings", "webcam settings", "camera permission")),
	("settings-accounts", "Your account settings", SETTING, "ms-settings:yourinfo", ("account settings", "my account", "your info")),
	("settings-sign-in", "Sign-in options", SETTING, "ms-settings:signinoptions", ("sign in options", "password settings", "pin settings")),
	("settings-about", "About this computer", SETTING, "ms-settings:about", ("about this pc", "about my computer", "system information", "about settings")),
	("settings-security", "Windows Security", SETTING, "ms-settings:windowsdefender", ("windows defender", "security settings", "virus protection")),
	("settings-troubleshoot", "Troubleshoot settings", SETTING, "ms-settings:troubleshoot", ("troubleshooting", "troubleshooter")),
	("settings-recovery", "Recovery settings", SETTING, "ms-settings:recovery", ("recovery", "reset this pc")),
	("settings-clipboard", "Clipboard settings", SETTING, "ms-settings:clipboard", ("clipboard history",)),
)
# What may be handed to Windows to open: only what is fixed above or was found on this computer. A thing a
# fetched or generated text names is never opened.
MAX_FOUND = 6
# Words of a request to open something that are not part of its name.
_OPEN_START = re.compile(
	rf"^\s*{_POLITE}(?:(?:first|then|next|now|and|also|just)[, ]+)*(?:open(?: up)?|launch|start(?: up)?|run|bring up|"
	r"pull up|show me|show|go (?:in)?to|go in|get (?:in)?to|take me (?:in)?to|take me|load|fire up|switch to|"
	r"double[- ]click(?: on)?|find|look for|where is|where are)\s+", re.IGNORECASE)
_OPEN_FILLER = re.compile(
	r"\b(my|the|a|an|your|some|program|programme|app|application|software|called|named|for me|please|now|again|"
	r"on (my|the|this) (computer|pc|laptop|desktop|screen)|in (my |the )?windows|from (the|my) (start menu|desktop)|"
	r"icon|shortcut|window|page)\b", re.IGNORECASE)
_PRONOUN = re.compile(r"^(it|this|that|them|these|those|this one|that one|one)$", re.IGNORECASE)


def wanted(part):
	"""What the user wants opened, from their own words: "open my Recycle Bin, please" is "recycle bin"."""
	text = _OPEN_START.sub("", own(part), count=1)
	text = re.sub(r"\s+(?:in|with|using)\s+(?:my |the )?(?:google chrome|chrome|firefox|mozilla firefox|microsoft edge|edge|brave|opera|browser)\b.*$", "", text, flags=re.IGNORECASE)
	text = _OPEN_FILLER.sub(" ", text)
	return _plain(text)


_OPENS = re.compile(
	rf"^\s*{_POLITE}(?:(?:first|then|next|now|and|also|just)[, ]+)*(?:open(?: up)?|launch|start(?: up)?|run|bring up|"
	r"pull up|show me|go (?:in)?to|go in|get (?:in)?to|take me (?:in)?to|load|fire up|double[- ]click(?: on)?)\s+",
	re.IGNORECASE)
_NOT_WINDOWS = re.compile(r"\b(nvda|visionclaw|add-?ons?|skills?|notes?|memor(y|ies)|library|web ?sites?|web ?pages?)\b", re.IGNORECASE)


def opensPlace(part):
	"""Whether the user's own words ask for a place, tool or settings page of Windows to be opened, by its
	name: "go into my Windows settings", "open the Recycle Bin". A question about how, and anything of NVDA's
	or VisionClaw's own, is not meant."""
	text = own(part)
	if _ASKS_HOW.search(text) or _NOT_WINDOWS.search(text) or not _OPENS.match(text):
		return False
	return find(wanted(text), places())[1]


def places():
	"""The things Windows itself has, as things that can be opened."""
	return [{"id": f"place-{ident}" if kind == PLACE else ident, "name": name, "kind": kind, "target": target,
		"words": tuple(_plain(word) for word in words)} for ident, name, kind, target, words in PLACES]


def slug(text):
	return "-".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))[:60] or "thing"


def thing(prefix, name, kind, target, words=()):
	"""Something found on this computer that can be opened: a program of the Start menu, an item on the
	desktop, a file or a folder."""
	return {"id": f"{prefix}-{slug(name)}", "name": name, "kind": kind, "target": target,
		"words": tuple(_plain(word) for word in words)}


_KIND_ORDER = (ON_DESKTOP, PROGRAM, PLACE, TOOL, SETTING, FOLDER, FILE)


def find(words, things, limit=MAX_FOUND):
	"""The things a request to open something is about, best first; words is what `wanted` gave.
	(things, sure): sure when exactly one
	thing has the name the user said, word for word; then nothing needs to be chosen.
	A thing is found when the user's words are its name or one of its other names; when all the user's words are
	in its name ("word" finds "Word 2021"); or when its whole name is in the user's words. Nothing is found by
	one shared everyday word, because opening the wrong thing is worse than saying that nothing was found."""
	asked = _plain(words)
	if not asked or _PRONOUN.match(asked):
		return [], False
	askedWords = asked.split()
	scored = []
	for index, item in enumerate(things):
		names = [_plain(item["name"])] + [word for word in item.get("words", ()) if word]
		best = 0
		for name in names:
			if not name:
				continue
			nameWords = name.split()
			if name == asked:
				best = max(best, 400)
			elif _has(asked, name) and (len(nameWords) > 1 or len(name) >= 4):
				# The whole name is said, among other words: the longer the name, the surer.
				best = max(best, 300 + len(nameWords))
			elif all(word in nameWords for word in askedWords):
				# Everything the user said is in the name: the shorter the name, the closer.
				best = max(best, 200 - min(50, len(nameWords)))
			elif len(askedWords) == 1 and len(asked) >= 4 and any(word.startswith(asked) for word in nameWords):
				best = max(best, 100)
		if best:
			order = _KIND_ORDER.index(item["kind"]) if item["kind"] in _KIND_ORDER else len(_KIND_ORDER)
			scored.append((-best, order, len(item["name"]), index))
	if not scored:
		return [], False
	scored.sort()
	top = -scored[0][0]
	# Only what is as good as the best kind of match: a name said word for word shuts out what merely shares words.
	tier = 400 if top >= 400 else 300 if top >= 300 else 150 if top >= 150 else 100
	kept, seen = [], set()
	for score, _order, _length, index in scored:
		item = things[index]
		key = (_plain(item["name"]), item["kind"])
		if -score < tier or key in seen:
			continue
		seen.add(key)
		kept.append(item)
	sure = top >= 400 and sum(1 for score, *_rest in scored if -score >= 400) == 1
	return ([kept[0]] if sure else kept[:limit]), sure


def foundText(things):
	"""What was found, one to a line, each beginning with its id: the only answers a model may then give."""
	return "\n".join(f"{item['id']}: {item['name']}, {item['kind']}." for item in things)


def nothingFound(words):
	asked = _plain(words) or own(words)
	return (
		f"Nothing called \"{asked}\" was found among the programs of the Start menu, the things on the desktop, the "
		"folders, tools and settings pages of Windows, or the files in your own folders. If it is a button or an item "
		"in the window in front, ask to click it instead.")


# --- Parts of Windows itself ---

# The parts of Windows that are not in any program's window and that Windows opens with a key of its own: the
# Start menu, search, the taskbar, the notification area and the rest. They are opened with that key, by plain
# code, and the user is told the key for next time. The keys are from claw/knowledge/windows-keyboard.md, which
# was written from Microsoft's page "Keyboard shortcuts in Windows", read on 2026-11-17; when a key is changed,
# read that page again, do not write a key from memory. Asked for on 2026-11-18, after "click the start button",
# "click the windows start button using the mouse" and "open the windows start menu" all failed: the Start
# button is on the taskbar, not in the window in front, so it was never among the items, and a small model then
# chose another item.
# (id, name, keys sent, keys said to the user, what to do once there, words that are sure, words that need
# nothing else in the window to fit them)
WINDOWS_PARTS = (
	("start", "the Start menu", "control+escape", "the Windows key, or Control+Escape",
		"Type the name of a program, file or setting and press Enter. The arrow keys and Tab move through it, and "
		"Escape closes it.",
		(r"start ?menu", r"windows start( button| screen)?", r"start button (of|in|on) windows", r"start screen",
			r"start button (on|in) the task ?bar", r"task ?bar'?s? start button", r"start button of the task ?bar",
			r"windows (logo )?(key )?menu"),
		(r"start button", r"start", r"start icon")),
	("quick-link", "the Quick Link menu", "windows+x", "Windows+X",
		"It is what a right-click on the Start button shows. The arrow keys move through it, Enter chooses, and "
		"Escape closes it.",
		(r"quick ?link menu", r"power ?user menu", r"win(dows)? ?\+? ?x menu", r"right[- ]?click(ing)? (on )?(the )?(windows )?start( button| menu)?"),
		()),
	("search", "Windows search", "windows+s", "Windows+S",
		"Type what you are looking for, use the arrow keys to move through the results, and press Enter.",
		(r"windows search", r"search (box|bar|field|button) (of|in|on) (windows|the task ?bar)", r"task ?bar search",
			r"start (menu )?search"),
		(r"search button", r"search box", r"search")),
	("taskbar", "the taskbar", "windows+t", "Windows+T",
		"Windows+T again goes to the next program, Windows+Shift+T to the one before, and Enter opens the one you "
		"are on.",
		(r"task ?bar",),
		()),
	("tray", "the notification area", "windows+b", "Windows+B",
		"The arrow keys move between its icons, Enter opens one, and Shift+F10 opens its menu.",
		(r"system ?tray", r"notification area", r"tray icons?", r"hidden icons", r"show hidden icons", r"systray"),
		()),
	("quick-settings", "quick settings", "windows+a", "Windows+A",
		"Tab and the arrow keys move between its buttons and sliders, such as volume, Wi-Fi and Bluetooth, and "
		"Escape closes it.",
		(r"quick settings", r"action cent(er|re)", r"control cent(er|re)"),
		()),
	("notifications", "the notification center", "windows+n", "Windows+N",
		"The arrow keys and Tab move through the notifications and the calendar, and Escape closes it.",
		(r"notification (center|centre|panel|list|pane)", r"(my |the |all )?notifications"),
		()),
	("task-view", "Task View", "windows+tab", "Windows+Tab",
		"The arrow keys move between the open windows, Enter switches to one, and Escape closes it.",
		(r"task ?view", r"virtual desktops"),
		()),
	("run", "the Run dialog", "windows+r", "Windows+R",
		"Type the name of a program, folder or web address and press Enter.",
		(r"run (dialog|box|window|command|prompt)", r"windows run"),
		()),
	("clipboard", "clipboard history", "windows+v", "Windows+V",
		"The arrow keys move through what was copied, and Enter pastes it. The first time, Windows offers to turn "
		"clipboard history on.",
		(r"clipboard (history|manager)",),
		()),
	("emoji", "the emoji panel", "windows+period", "Windows+period",
		"Type to search for an emoji, use the arrow keys to choose, and press Enter to type it.",
		(r"emoji (panel|picker|keyboard|menu|window)", r"emojis? (and|or) symbols"),
		()),
)
# Words that ask for something to be opened, gone to, shown or clicked. A part named with nothing else is meant too.
_PART_ACTS = re.compile(
	rf"^\s*{_POLITE}(?:(?:i want you to|i need you to|i'd like you to|i would like to|i want to|let me|help me)\s+)?"
	r"(?:(?:first|then|next|now|and|also|just|please)[, ]+)*"
	r"(?:open(?: up)?|launch|start|bring up|pull up|show(?: me)?|display|go (?:in)?to|get (?:in)?to|take me (?:in)?to|"
	r"move (?:in)?to|jump to|switch to|focus(?: on)?|put me (?:in|on|at)|(?:double[- ]|left[- ]|right[- ])?click(?: on)?|"
	r"press|push|hit|tap|select|activate|use|get|give me|find)\b", re.IGNORECASE)
# Words around the name of a part that say nothing about which part it is.
_PART_FILL = re.compile(
	r"^(?:(?:the|my|on|in|at|to|of|up)\s+)*|\s*(?:\b(?:button|icon|key)\b)?(?:\s*\b(?:with|using|by) (?:the |my |a )?"
	r"(?:mouse|keyboard|pointer)\b)?(?:\s*\b(?:please|for me|now|again)\b)*\s*[.!]*\s*$", re.IGNORECASE)
# What is not a part of Windows to be opened: a question about how, its settings, NVDA's own, or closing it.
_PART_NOT = re.compile(
	r"\b(settings?|options|preferences)\b(?<!quick settings)|\b(close|hide|turn off|disable|remove|unpin|pin|"
	r"customi[sz]e|change|resize|move the|nvda|visionclaw|add-?ons?)\b|\?\s*$", re.IGNORECASE)


def windowsPart(part, loose=False):
	"""The part of Windows itself that the user's words ask to have opened, as its id, or None. loose: also the
	words that only say it where nothing in the window in front fits them, as "click the start button", for a
	program can have a Start button of its own."""
	text = " ".join(own(part).lower().replace("’", "'").split())
	if not text or _ASKS_HOW.search(text) or _PART_NOT.search(text.replace("quick settings", "quick")):
		return None
	# A part named with nothing else ("start menu"): its name must be all there is, so that a question that names
	# it is not taken for a wish.
	alone = _PART_FILL.sub("", text.strip()).strip()
	for ident, _name, _keys, _said, _next, sure, _maybe in WINDOWS_PARTS:
		if any(re.fullmatch(rf"(?:windows'?s? )?{words}", alone) for words in sure):
			return ident
	acts = _PART_ACTS.match(text)
	if not acts:
		return None
	# What is to be opened: the words after the verb, without what says nothing about which part it is.
	rest = _PART_FILL.sub("", text[acts.end():].strip()).strip()
	if not rest:
		return None
	# A right-click on the Start button shows the Quick Link menu.
	rightClick = re.search(r"right[- ]?click", acts.group(0))
	for ident, _name, _keys, _said, _next, sure, maybe in WINDOWS_PARTS:
		# After a verb the name may stand among other words: "the start menu on my computer".
		if any(re.search(rf"\b{words}\b", rest) for words in sure) or (loose and any(re.fullmatch(rf"(?:windows'?s? )?{words}", rest) for words in maybe)):
			return "quick-link" if rightClick and ident == "start" else ident
	return None


def windowsPartOf(ident):
	"""(name, keys sent, keys said, what to do there) of a part of Windows, by its id."""
	for one, name, keys, said, there, _sure, _maybe in WINDOWS_PARTS:
		if one == ident:
			return name, keys, said, there
	raise KeyError(ident)


def windowsPartText(ident, focus="", notInWindow=False):
	"""What the user is told after a part of Windows was opened: what it is, where NVDA is, the key for next
	time, and what to do there. notInWindow: the user asked to click it, and it was not in the window in front."""
	name, _keys, said, there = windowsPartOf(ident)
	start = (
		f"That is not in the window in front: it is part of Windows itself. VisionClaw opened {name} with {said}, "
		"which does the same as clicking it." if notInWindow else f"Opened {name} with {said}.")
	where = f" NVDA is now on: {focus}." if focus else ""
	return f"{start}{where} Next time you can press {said} yourself. {there}"


# A browser the user names for a web address.
BROWSERS = (
	("chrome.exe", "Google Chrome", r"\b(google )?chrome\b"),
	("firefox.exe", "Firefox", r"\b(mozilla )?firefox\b"),
	("msedge.exe", "Microsoft Edge", r"\b(microsoft )?edge\b"),
	("brave.exe", "Brave", r"\bbrave\b"),
	("opera.exe", "Opera", r"\bopera\b"),
	("vivaldi.exe", "Vivaldi", r"\bvivaldi\b"),
)


def browserOf(part):
	"""The browser the user's words name for a web address, as (its program file, its name), or None."""
	text = own(part).lower()
	for exe, name, pattern in BROWSERS:
		if re.search(r"\b(in|with|using|on|through)\s+(my |the )?" + pattern[2:], text) or re.search(pattern + r"\s+browser\b", text):
			return exe, name
	return None


# --- The Recycle Bin ---

BIN = r"(?:recycle bin|recycling bin|recycle|trash can|trash|wastebasket|rubbish bin)"
_BIN = re.compile(rf"\b{BIN}\b", re.IGNORECASE)
_EMPTY_IT = re.compile(
	rf"\b(empty|clear|clean out|clear out|purge|flush)\b.{{0,30}}\b{BIN}\b"
	rf"|\b(delete|remove|get rid of|erase)\b.{{0,12}}\b(everything|all|what is|what's|the files|the items)\b.{{0,24}}\b{BIN}\b",
	re.IGNORECASE)
_ASKS_HOW = re.compile(r"\bhow (do|can|would|should|could) (i|we|you|one)\b|\bhow to\b|\bwhat (key|keys|shortcut|command)\b", re.IGNORECASE)
# From this much, or this share of the room that is left on the drive, emptying is worth it.
BIN_BIG = 1 << 30
BIN_SHARE = 0.1
# A drive with less room left than this share of it, or than this much, is called nearly full.
LOW_SHARE = 0.1
LOW_BYTES = 10 << 30


def aboutBin(part):
	return bool(_BIN.search(own(part)))


def emptiesBin(part):
	"""Whether the user's own words ask for the Recycle Bin to be emptied now; a question about it, or about
	whether it needs emptying, does not."""
	text = own(part)
	if _ASKS_HOW.search(text) or re.search(r"\b(needs?|should|whether|if|do i (need|have)|does it|is it|worth)\b", text, re.IGNORECASE):
		return False
	return bool(_EMPTY_IT.search(text))


# Words that ask about the Recycle Bin, and words that do something else with it: a file dragged onto it, a
# file brought back from it, the bin opened or clicked.
_BIN_ASKS = re.compile(
	r"\b(check|see|look|how (full|much|many|big)|what('s| is| does)?|anything|something|is|are|does|do|needs?|should|"
	r"whether|status|size|tell me|say|empty|full)\b", re.IGNORECASE)
_BIN_ELSE = re.compile(
	r"\b(drag|move|put|send|drop|throw|restore|recover|undelete|click|press|open|go (in)?to|onto|into|bring back|get back)\b",
	re.IGNORECASE)


def asksAboutBin(part):
	"""Whether a part of a request is about the Recycle Bin without asking how something is done. What the
	planner added to a part that says "it" counts, because it says what "it" is."""
	text = " ".join(str(part or "").split())
	mine = own(part)
	return bool(_BIN.search(text) and _BIN_ASKS.search(mine)) and not _BIN_ELSE.search(mine) and not _ASKS_HOW.search(mine)


def binText(count, size, free=None, total=None):
	"""What the Recycle Bin holds and whether it is worth emptying, in sentences. count is None when Windows
	did not say. free and total: the room on the drive Windows is on."""
	if count is None:
		return "Windows did not say what the Recycle Bin holds."
	if count <= 0:
		return "The Recycle Bin is empty. There is nothing to empty."
	said = f"The Recycle Bin holds {many(count, 'item')}, {sizeText(size)} in all."
	low = free is not None and total and (free < LOW_SHARE * total or free < LOW_BYTES)
	if size >= BIN_BIG or (free and size >= BIN_SHARE * free) or (low and size >= 100 << 20):
		why = f" The drive has {sizeText(free)} free" + (", which is little" if low else "") + "." if free is not None else ""
		return f"{said} It is worth emptying: that would free {sizeText(size)}.{why} To empty it, say: empty the Recycle Bin."
	room = f" The drive has {sizeText(free)} free, so room is not short." if free is not None and not low else ""
	return (
		f"{said} It does not need emptying for room: that would free only {sizeText(size)}.{room} "
		"To empty it anyway, say: empty the Recycle Bin.")


def binState(text):
	"""What a sentence of binText says: "empty", "worth" emptying, or "some" things that need no emptying; ""
	when it says none of these."""
	if "Recycle Bin is empty" in text:
		return "empty"
	if "worth emptying" in text:
		return "worth"
	return "some" if "Recycle Bin holds" in text else ""


# --- The volume of the computer ---

_SYSTEM = r"(?:system|computer'?s?|pc'?s?|laptop'?s?|windows|master|main|overall|device|speakers?|headphones?|sound ?card)"
_VOLUME = re.compile(
	rf"\b{_SYSTEM}\b.{{0,24}}\b(volume|sound|audio|loudness)\b|\b(volume|sound|audio)\b.{{0,24}}\bof (my |the |this )?{_SYSTEM}\b"
	rf"|\b(mute|unmute|silence)\b.{{0,20}}\b{_SYSTEM}\b|\b(mute|unmute) (my |the |all )?(sound|audio|volume)\b"
	r"|\bvolume of (my |the |this )?(computer|pc|laptop|machine)\b"
	rf"|\b{_SYSTEM}\b.{{0,24}}\b(too|so|very|really|way too|much too) (loud|quiet|soft|noisy|low)\b", re.IGNORECASE)
_NVDA = re.compile(r"\b(nvda|speech|voice|synthesi[sz]er|screen ?reader|speaking|talking)\b", re.IGNORECASE)
UP, DOWN, SET, MUTE, UNMUTE, SAY = "up", "down", "set", "mute", "unmute", "say"
# Below this the screen reader cannot be heard on most speakers. A request to turn the volume down stops here.
QUIET = 10
_STEP, _BIG_STEP, _SMALL_STEP = 10, 25, 5


def volumeOf(part):
	"""What the user's own words ask of the computer's volume, or None when they are not about it:
	(what, amount). "Turn down my system volume" is (DOWN, 10), "a lot" 25, "a little" 5, "by 20" 20; "set the
	computer's volume to 40 percent" is (SET, 40). NVDA's own speech volume is a setting of NVDA and not meant."""
	text = own(part).lower()
	if not _VOLUME.search(text) or (_NVDA.search(text) and not re.search(rf"\b{_SYSTEM}\b", text)):
		return None
	if re.search(r"\bunmute\b|\bturn (the |my )?(sound|audio|volume) (back )?on\b|\bsound back\b", text):
		return (UNMUTE, 0)
	if re.search(r"\b(mute|silence)\b|\bturn (the |my )?(sound|audio) off\b|\bsound off\b", text):
		return (MUTE, 0)
	exact = re.search(r"\b(?:to|at)\s+(\d{1,3})\s*(?:percent|%)?", text)
	if exact:
		return (SET, max(0, min(100, int(exact.group(1)))))
	if re.search(r"\b(all the way|fully|completely|as far as it goes|maximum|max|full)\b", text) and re.search(r"\b(up|louder|raise|increase|max|maximum|full)\b", text):
		return (SET, 100)
	if re.search(r"\b(half|halfway|medium|middle)\b", text):
		return (SET, 50)
	up = bool(re.search(r"\b(up|louder|raise|increase|higher|more)\b|\btoo (quiet|soft|low)\b", text))
	down = bool(re.search(r"\b(down|quieter|lower|decrease|reduce|softer|less)\b|\b(too|so|very|really) (loud|noisy)\b", text))
	if up == down:
		return (SAY, 0)
	by = re.search(r"\bby\s+(\d{1,3})\b", text)
	amount = int(by.group(1)) if by else _BIG_STEP if re.search(r"\b(a lot|much|way|far|lots)\b", text) else (
		_SMALL_STEP if re.search(r"\b(a little|a bit|slightly|a touch|a tad|bit)\b", text) else _STEP)
	return (UP if up else DOWN, max(1, min(100, amount)))


def volumeNew(level, wish):
	"""The new volume, 0 to 100, for a wish that changes it, and whether it was held back so that the screen
	reader can still be heard: (new level, held back). A wish to turn it down stops at QUIET; an exact number
	is taken as it is, and whoever sets it decides what a very low one needs."""
	what, amount = wish
	if what == UP:
		return min(100, level + amount), False
	if what == DOWN:
		wanted_ = level - amount
		if level <= QUIET:
			return level, True
		return max(QUIET, wanted_), wanted_ < QUIET
	return max(0, min(100, amount)), False


def volumeText(level, muted):
	return f"The computer's volume is at {level} percent" + (", and the sound is muted." if muted else ".")


# --- Locking, sleeping, restarting, shutting down ---

LOCK, SLEEP, RESTART, SHUTDOWN, SIGN_OUT, CANCEL = "lock", "sleep", "restart", "shut down", "sign out", "cancel"
_MACHINE = r"(?:computer|pc|laptop|machine|windows|system|desktop computer|notebook)"
_POWER = (
	(CANCEL, rf"\b(cancel|abort|stop|call off)\b.{{0,20}}\b(shut ?down|restart|reboot|sign ?out|log ?off)\b"),
	(LOCK, rf"\block\b.{{0,16}}\b({_MACHINE}|screen|workstation)\b"),
	(SLEEP, rf"\b(put|send)\b.{{0,16}}\b{_MACHINE}\b.{{0,12}}\b(to sleep|asleep|into sleep)\b|\b(sleep|suspend|hibernate)\b.{{0,12}}\b{_MACHINE}\b"),
	(RESTART, rf"\b(restart|reboot)\b.{{0,16}}\b{_MACHINE}\b"),
	(SHUTDOWN, rf"\b(shut ?down|power off|power down|switch off|turn off)\b.{{0,16}}\b{_MACHINE}\b|\bshut (my |the |this )?{_MACHINE} down\b"),
	(SIGN_OUT, rf"\b(sign|log) (me )?(out|off)\b(?!\s+(of|from)\b)|\b(sign|log) (me )?(out|off) (of|from) (windows|(my|the|this) {_MACHINE})\b"),
)
# How long Windows waits before it restarts or shuts down, so that it can still be called off.
POWER_WAIT = 30


def powerOf(part):
	"""Which of locking, sleeping, restarting, shutting down, signing out or calling it off the user's own
	words ask for, or None. Nothing about NVDA itself is meant: "restart NVDA" is NVDA's own command."""
	text = own(part).lower()
	if _ASKS_HOW.search(text) or re.search(r"\b(nvda|screen ?reader|program|app|application|add-?on|visionclaw|browser)\b", text):
		return None
	for what, pattern in _POWER:
		if re.search(pattern, text):
			return what
	return None


# --- Windows that are open ---

SWITCH, CLOSE, MINIMIZE, MAXIMIZE, RESTORE = "switch to", "close", "minimize", "maximize", "restore"
WINDOW_ACTIONS = [SWITCH, CLOSE, MINIMIZE, MAXIMIZE, RESTORE]
_WINDOW_WORDS = frozenset((
	"switch", "to", "go", "bring", "up", "front", "focus", "close", "quit", "exit", "shut", "minimize", "minimise",
	"maximize", "maximise", "restore", "the", "my", "a", "window", "windows", "program", "app", "application", "please",
	"of", "in", "into", "back", "over", "show", "me", "this", "that", "current", "it", "now", "again", "and", "then",
	"hide", "make", "full", "screen", "bigger", "smaller", "put", "down", "open", "first", "activate", "get", "take"))
# What people call a program whose file has another name.
APP_NAMES = {
	"msedge": "microsoft edge", "winword": "microsoft word", "excel": "microsoft excel", "powerpnt": "powerpoint",
	"outlook": "microsoft outlook", "explorer": "file explorer", "systemsettings": "windows settings",
	"applicationframehost": "", "chrome": "google chrome", "firefox": "mozilla firefox", "wmplayer": "windows media player",
	"windowsterminal": "terminal", "cmd": "command prompt", "taskmgr": "task manager", "calculatorapp": "calculator",
	"thunderbird": "mozilla thunderbird", "code": "visual studio code", "notepad": "notepad"}


def windowActionOf(part):
	"""What to do with a window, from the user's own words."""
	text = own(part).lower()
	if re.search(r"\b(close|quit|exit|shut)\b", text):
		return CLOSE
	if re.search(r"\b(minimi[sz]e|hide)\b", text):
		return MINIMIZE
	if re.search(r"\b(maximi[sz]e|full ?screen|as big as|make\b.*\bbigger)\b", text):
		return MAXIMIZE
	if re.search(r"\b(restore|un-?minimi[sz]e|un-?maximi[sz]e|normal size)\b", text):
		return RESTORE
	return SWITCH


_ABOUT_WINDOW = re.compile(
	r"\b(switch|alt[- ]tab) (back |over )?to\b"
	r"|\b(close|minimi[sz]e|maximi[sz]e|restore|un-?minimi[sz]e)\b.*\b(windows?|programs?|apps?|applications?)\b"
	r"|\b(close|minimi[sz]e|maximi[sz]e) (it|this|that|everything|all)\b"
	r"|\bbring\b.{0,40}\b(to the front|to the foreground|forward)\b"
	r"|^\s*(?:please\s+)?(?:close|quit|exit|minimi[sz]e|maximi[sz]e)\b(?!.*\b(tab|tabs|menu|nvda|speech|braille|document|file|add-?on|dialog|mode|reading|speaking|curtain|skills?)\b)",
	re.IGNORECASE)


def aboutWindow(part):
	"""Whether the user's own words ask for a window to be switched to, closed, minimized, maximized or
	restored, or for every window to be minimized."""
	text = own(part)
	return not _ASKS_HOW.search(text) and bool(_ABOUT_WINDOW.search(text) or allWindows(text))


def listed(what, result):
	"""Whether a window the user named is among the windows a result of windowsText lists."""
	windows = []
	for line in str(result or "").splitlines():
		hit = re.match(r"^\d{1,3}\. (.+?)(?: \(([^()]*)\))?(?:, in front)?(?:, minimized)?$", line.strip())
		if hit:
			windows.append({"title": hit.group(1), "app": hit.group(2) or ""})
	return bool(windowsMeant(what, windows)) if _plain(what) else False


def windowLine(window):
	"""A window as it is listed: its title and the program it belongs to."""
	app = window.get("app") or ""
	title = window.get("title") or "no title"
	# The program is named as people call it, and only where the title does not already say which it is.
	known = APP_NAMES.get(app.lower(), app)
	said = set(_plain(title).split())
	return f"{title} ({known})" if known and not said & set(_plain(known).split()) else title


def windowsText(windows):
	if not windows:
		return "No windows are open."
	lines = [f"{number}. {windowLine(window)}" + (", in front" if window.get("front") else "")
		+ (", minimized" if window.get("minimized") else "") for number, window in enumerate(windows, 1)]
	return f"{many(len(windows), 'window')} open:\n" + "\n".join(lines)


def windowsMeant(part, windows):
	"""The windows the user's own words name, best first. "This window" and a request that names none mean
	the window in front. A window is named by its whole title, by its program ("close Chrome"), or by words
	that are all in its title or its program's names."""
	text = _plain(own(part))
	asked = [word for word in text.split() if word not in _WINDOW_WORDS]
	if not asked:
		return [window for window in windows if window.get("front")][:1]
	scored = []
	for index, window in enumerate(windows):
		title = _plain(window.get("title"))
		app = _plain(window.get("app"))
		known = _plain(APP_NAMES.get(app, ""))
		have = set(title.split()) | set(app.split()) | set(known.split())
		if title and _has(text, title):
			score = 4
		elif (app and len(app) > 2 and _has(text, app)) or (known and _has(text, known)):
			score = 3
		elif all(word in have for word in asked):
			score = 2
		elif len(asked) > 1 and sum(word in have for word in asked) / len(asked) >= 0.6:
			score = 1
		else:
			continue
		scored.append((-score, 0 if window.get("front") else 1, index))
	scored.sort()
	if not scored:
		return []
	best = scored[0][0]
	return [windows[index] for score, _front, index in scored if score == best]


def allWindows(part):
	"""Whether every window is meant: "minimize all windows", "show the desktop"."""
	return bool(re.search(
		r"\b(all|every) (of )?(the |my |open )*(windows|programs|apps)\b|\b(minimi[sz]e|hide) everything\b"
		r"|\bshow (me )?(the |my )?desktop\b", own(part).lower()))


# --- The user's folders and files ---

FOLDERS = ("desktop", "documents", "downloads", "pictures", "music", "videos")
_FOLDER_WORDS = {
	"desktop": r"\bdesktop\b", "documents": r"\b(my )?documents?( folder)?\b", "downloads": r"\bdownloads?( folder)?\b",
	"pictures": r"\b(pictures|photos)( folder)?\b", "music": r"\bmusic( folder)?\b", "videos": r"\bvideos?( folder)?\b"}
KINDS = {
	"pdf": (".pdf",), "word": (".docx", ".doc", ".rtf", ".odt"), "text": (".txt", ".md", ".log"),
	"spreadsheet": (".xlsx", ".xls", ".csv", ".ods"), "presentation": (".pptx", ".ppt"),
	"picture": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"),
	"music": (".mp3", ".wav", ".flac", ".m4a", ".ogg", ".wma", ".aac"), "video": (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"),
	"zip": (".zip", ".7z", ".rar"), "program": (".exe", ".msi"), "book": (".epub", ".mobi", ".azw3"),
	"add-on": (".nvda-addon",)}
_KIND_SAID = (
	("pdf", r"\bpdfs?\b"), ("word", r"\bword (documents?|files?)\b|\bdocx?\b"), ("spreadsheet", r"\b(spreadsheets?|excel (files?|sheets?)|csv)\b"),
	("presentation", r"\b(presentations?|powerpoints?|slides)\b"), ("picture", r"\b(pictures?|photos?|images?|screenshots?) (files?)?\b"),
	("music", r"\b(songs?|music files?|mp3s?|audio files?)\b"), ("video", r"\b(videos?|movies?|films?) ?(files?)?\b"),
	("zip", r"\b(zip|zipped|compressed) (files?|folders?)\b|\bzips?\b"), ("program", r"\b(installers?|setup files?|exe files?)\b"),
	("book", r"\b(e-?books?|epubs?)\b"), ("add-on", r"\b(nvda )?add-?on (files?|packages?)\b"), ("text", r"\btext (files?|documents?)\b"),
)
_FILE_FILLER = frozenset((
	"what", "whats", "which", "is", "are", "in", "my", "the", "a", "an", "of", "list", "show", "me", "tell", "find", "search",
	"for", "look", "file", "files", "folder", "folders", "named", "called", "name", "with", "that", "have", "has", "there",
	"any", "do", "i", "how", "many", "newest", "latest", "recent", "recently", "most", "last", "new", "downloaded", "saved",
	"added", "oldest", "biggest", "largest", "on", "inside", "contents", "content", "and", "please", "where", "did", "put",
	"to", "it", "all", "everything", "check", "see", "say", "read", "out", "first", "from", "today", "this", "week", "s",
	"desktop", "documents", "document", "downloads", "download", "pictures", "photos", "music", "videos", "video", "count",
	"number", "kept", "stored", "located", "exist", "exists", "get", "give", "can", "you", "computer", "pc", "somewhere"))
NEWEST, BIGGEST, BY_NAME = "newest", "biggest", "name"
FILES_SHOWN = 12


def fileWish(part):
	"""What the user's own words ask about files: {"folders": which of the user's folders, all when none is
	named; "kinds": the kinds of file named; "words": words of the name looked for; "order": newest, biggest
	or by name; "count": whether only how many is asked}."""
	text = own(part).lower()
	folders = [name for name in FOLDERS if re.search(_FOLDER_WORDS[name], text)]
	# "Pictures" and "music" name a folder and a kind of file; with another folder named, they are the kind.
	kinds = [kind for kind, pattern in _KIND_SAID if re.search(pattern, text)]
	if len(folders) > 1:
		for folder, kind in (("pictures", "picture"), ("music", "music"), ("videos", "video")):
			if folder in folders and len(folders) > 1 and kind in kinds:
				folders.remove(folder)
	elif folders and folders[0] in ("pictures", "music", "videos"):
		kinds = [kind for kind in kinds if kind not in ("picture", "music", "video")]
	named = re.search(r"\b(?:named|called|titled)\s+[\"']?([\w .-]{1,60}?)[\"']?\s*(?:$|[,.?!]|\bin\b|\bon\b)", text)
	if named:
		words = _plain(named.group(1)).split()
	else:
		taken = set()
		for kind, pattern in _KIND_SAID:
			for hit in re.finditer(pattern, text):
				taken |= set(_plain(hit.group(0)).split())
		words = [word for word in _plain(text).split() if word not in _FILE_FILLER and word not in taken and len(word) > 1]
	order = BIGGEST if re.search(r"\b(biggest|largest|most space|take up)\b", text) else (
		NEWEST if not words or re.search(r"\b(newest|latest|recent|recently|last|just)\b", text) else BY_NAME)
	return {
		"folders": folders or list(FOLDERS), "named": bool(folders), "kinds": kinds, "words": words, "order": order,
		"count": bool(re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", text))}


_FILE_ASK = re.compile(
	r"^\s*(?:please\s+)?(?:can you\s+)?(what|what's|whats|which|list|show|how many|find|search|look|where|is there|are there|do i have|any|"
	r"tell me|read|check|count|give me)\b", re.IGNORECASE)
_FILE_PLACE = re.compile(
	r"\b(in|on|inside|from|of) (my |the )?(desktop|documents|downloads|pictures|photos|music|videos)( folder)?\b"
	r"|\b(my|the) (desktop|documents|downloads|pictures|music|videos) folder\b"
	r"|\b(find|search for|look for|where is|where are|where did)\b.*\b(files?|folders?|documents?|pdfs?|spreadsheets?|pictures?|photos?|songs?|videos?)\b"
	r"|\b(new|newest|latest|biggest|largest|recent|recently|last) (downloaded |saved )?(files?|downloads?|documents?)\b"
	r"|\b(files?|folders?) (named|called)\b"
	r"|\bwhat (did|have) i (just |recently |last )?(download(ed)?|save[d]?)\b", re.IGNORECASE)
_NOT_FILES = re.compile(r"\b(web|internet|online|google|page|site|library|notes?|click|press|icon|see|window|screen)\b", re.IGNORECASE)


def aboutFiles(part):
	"""Whether the user's own words ask what is in one of their folders, or for a file of theirs to be found."""
	text = own(part)
	return bool(_FILE_ASK.match(text) and _FILE_PLACE.search(text)) and not _NOT_FILES.search(text) and not _ASKS_HOW.search(text)


def fileFits(name, wish):
	"""Whether a file's name fits what was asked for: its kind and every word of the name looked for."""
	low = name.lower()
	if wish["kinds"] and not any(low.endswith(ending) for kind in wish["kinds"] for ending in KINDS[kind]):
		return False
	have = _plain(low)
	return all(word in have for word in wish["words"])


def filesText(wish, found, folders, total=None, cut=False):
	"""What was found, in sentences and lines. found: (name, folder's name, size, modified as text, is a folder)
	already in the order asked for. total: how many fit in all."""
	where = " and ".join(folders) if wish["named"] else "your Desktop, Documents, Downloads, Pictures, Music and Videos"
	total = len(found) if total is None else total
	early = " The search was stopped early because there are very many files." if cut else ""
	if wish["words"]:
		named = " ".join(wish["words"])
		if not total:
			return f"Nothing with {named} in its name was found in {where}.{early}"
		head = f"{many(total, 'thing')} with {named} in the name, in {where}."
	else:
		what = " ".join(wish["kinds"]) + " file" if wish["kinds"] else "item"
		if not total:
			return f"No {what} was found in {where}.{early}"
		head = f"{many(total, what)} in {where}."
	if wish["count"] and not wish["words"]:
		return head
	order = {NEWEST: "The newest first", BIGGEST: "The biggest first", BY_NAME: "By name"}[wish["order"]]
	lines = [
		f"{number}. {name}" + (", a folder" if isFolder else f", {sizeText(size)}") + f", in {folder}, changed {modified}"
		for number, (name, folder, size, modified, isFolder) in enumerate(found[:FILES_SHOWN], 1)]
	more = f"\n... and {total - FILES_SHOWN} more." if total > FILES_SHOWN else ""
	return f"{head} {order}:\n" + "\n".join(lines) + more + ("\n" + early.strip() if cut else "")


# --- Changing the user's files ---

MAKE_FOLDER, MAKE_FILE, RENAME, MOVE, COPY, DELETE = "make folder", "make file", "rename", "move", "copy", "delete"
_FILE_NOUN = re.compile(
	r"\b(files?|folders?|directory|documents?|pdfs?|pictures?|photos?|images?|songs?|videos?|spreadsheets?|shortcuts?)\b", re.IGNORECASE)
ENDINGS = tuple(sorted({ending for endings in KINDS.values() for ending in endings} | {
	".html", ".htm", ".json", ".xml", ".ini", ".py", ".lnk", ".url", ".bat", ".ps1", ".pptx", ".jpg"}))
_FILE_NAME = re.compile(r"\S+(?:" + "|".join(re.escape(ending) for ending in ENDINGS) + r")(?=$|[\s,;!?])", re.IGNORECASE)


def namesFile(part):
	"""Whether the words write the name of a file with its ending, as in "open report.pdf": that is a file, and no
	address of a website."""
	return bool(_FILE_NAME.search(str(part or "").rstrip(" .!?")))
_TASK_START = rf"^\s*{_POLITE}(?:(?:first|then|next|now|and|also|just)[, ]+)*"
_MAKE = re.compile(
	_TASK_START + r"(?:create|make|add)\s+(?:me\s+)?(?:an?\s+)?(?:new\s+)?(?:empty\s+|blank\s+)?"
	r"(?P<kind>folder|directory|text file|text document|file)\b(?P<rest>.*)$", re.IGNORECASE)
_RENAME = re.compile(_TASK_START + r"rename\s+(?P<src>.+?)\s+(?:to|as)\s+(?P<new>.+)$", re.IGNORECASE)
_MOVE = re.compile(
	_TASK_START + r"(?P<verb>move|copy|put|duplicate)\s+(?P<src>.+?)\s+(?:to|into|onto)\s+(?P<dest>.+)$", re.IGNORECASE)
_PUT = re.compile(_TASK_START + r"(?P<verb>put|move|copy)\s+(?P<src>.+?)\s+(?:in|on|inside)\s+(?P<dest>(?:my|the)\s+.+)$", re.IGNORECASE)
_DELETE = re.compile(
	_TASK_START + r"(?:delete|remove|erase|trash|recycle|get rid of|throw away|throw out)\s+(?P<src>.+)$", re.IGNORECASE)
_CALLED = re.compile(r"\b(?:called|named|titled|with the name)\s+(?P<name>.+)$", re.IGNORECASE)
_IN_PLACE = re.compile(
	r"\s+(?:in|on|inside|under|to)\s+(?:my\s+|the\s+)?(?:desktop|documents?|downloads?|pictures|photos|music|videos?)(?:\s+folder)?\s*$",
	re.IGNORECASE)
# What Windows does not take in a name, and names it keeps for itself.
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = frozenset(["con", "prn", "aux", "nul"] + [f"com{n}" for n in range(1, 10)] + [f"lpt{n}" for n in range(1, 10)])
NAME_CHARS = 120
# More files than this that fit a name are not put to the user to choose from; they are asked to say more of it.
MAX_TO_CHOOSE = 6


def _quoted(text):
	return " ".join(str(text or "").split()).strip(" \"'“”‘’").rstrip(".!?,;").strip(" \"'“”‘’")


def cleanName(name):
	"""A name for a file or folder that Windows takes, as the user said it. Raises ValueError with a sentence
	for the user when it cannot be one."""
	name = _quoted(name)
	if not name:
		raise ValueError("The request does not say the new name.")
	if _BAD_CHARS.search(name):
		raise ValueError(f"\"{name}\" cannot be a name: Windows does not take these characters in one: < > : \" / \\ | ? *")
	if len(name) > NAME_CHARS:
		raise ValueError(f"That name is longer than {NAME_CHARS} characters, which is too long.")
	if name.split(".")[0].strip().lower() in _RESERVED or name.endswith((".", " ")):
		raise ValueError(f"\"{name}\" cannot be a name: Windows keeps it for itself.")
	return name


def endingOf(name):
	"""The ending of a file's name, such as ".pdf", or "" where it has none that is known."""
	low = str(name or "").lower()
	return next((ending for ending in sorted(ENDINGS, key=len, reverse=True) if low.endswith(ending)), "")


def _source(said):
	"""Which file or folder the user's words name, as a wish for the search: its folder, its kind, and the
	words of its name. A name written with its ending is taken as it is."""
	said = _quoted(said)
	# "The file", "the folder" and "the document" say that a file is meant, and are no part of its name.
	said = re.sub(
		r"^\s*(?:the|my|a|an|this|that)?\s*(?:file|folder|directory|document)\b\s*(?:called\s+|named\s+)?", "", said,
		flags=re.IGNORECASE).strip()
	wish = fileWish(said)
	written = _FILE_NAME.search(said)
	if written:
		wish = dict(wish, words=_plain(written.group(0)).split(), kinds=[])
	return dict(wish, order=BY_NAME, count=False, said=said)


def _destination(said):
	"""Where a file is to go: one of the user's own folders, and the words of a folder inside it where one is
	named ("the Taxes folder in my documents")."""
	text = _quoted(said).lower()
	keys = [name for name in FOLDERS if re.search(_FOLDER_WORDS[name], text)]
	rest = text
	for name in keys:
		rest = re.sub(_FOLDER_WORDS[name], " ", rest)
	words = [word for word in _plain(rest).split() if word not in (
		"my", "the", "a", "folder", "folders", "in", "on", "inside", "of", "called", "named", "into", "to", "directory")]
	return {"key": keys[-1] if keys else None, "words": words, "said": _quoted(said)}


def fileTask(part):
	"""What the user's own words ask to be done to a file or folder of theirs, or None when they ask no such
	thing: {"what": MAKE_FOLDER, MAKE_FILE, RENAME, MOVE, COPY or DELETE; "src": which file, as a wish for the
	search; "new": the new name as the user wrote it; "dest": where it goes; "place" and "placeSaid": the folder
	a new one is made in, and whether the user said it}.
	The words must speak of a file, a folder or a document, or write a name with its ending: "delete the notes
	on this program" and "copy the window title" are other things."""
	text = own(part).strip().rstrip(".!")
	if _ASKS_HOW.search(text):
		return None
	hit = _MAKE.match(text)
	if hit:
		rest = hit.group("rest")
		place = next((name for name in FOLDERS if re.search(_FOLDER_WORDS[name], _IN_PLACE.search(rest).group(0).lower())), None) \
			if _IN_PLACE.search(rest) else None
		rest = _IN_PLACE.sub("", rest)
		called = _CALLED.search(rest)
		name = _quoted(called.group("name") if called else re.sub(r"^\s*(?:for|of)\b", "", rest))
		folder = hit.group("kind").lower() in ("folder", "directory")
		if not folder and not called:
			return None  # "make a file" of what? Only a file that is given a name is made.
		return {"what": MAKE_FOLDER if folder else MAKE_FILE, "new": name, "place": place or "documents",
			"placeSaid": place is not None, "src": None, "dest": None}
	if not (_FILE_NOUN.search(text) or _FILE_NAME.search(text)):
		return None
	hit = _RENAME.match(text)
	if hit:
		return {"what": RENAME, "src": _source(hit.group("src")), "new": _quoted(hit.group("new")), "dest": None}
	hit = _MOVE.match(text) or _PUT.match(text)
	if hit:
		dest = hit.group("dest")
		if re.search(r"\b(clipboard|screen|window|top|bottom|front|back|left|right|next|previous)\b", dest, re.IGNORECASE):
			return None
		if _BIN.search(dest):
			return {"what": DELETE, "src": _source(hit.group("src")), "new": "", "dest": None}
		what = COPY if hit.group("verb").lower() in ("copy", "duplicate") else MOVE
		return {"what": what, "src": _source(hit.group("src")), "new": "", "dest": _destination(dest)}
	hit = _DELETE.match(text)
	if hit and not _BIN.search(hit.group("src")) or (hit and re.search(r"\bfrom (my |the )?" + BIN, hit.group("src"), re.IGNORECASE)):
		return {"what": DELETE, "src": _source(re.sub(r"\s+from (my |the )?.*$", "", hit.group("src")) if _BIN.search(hit.group("src")) else hit.group("src")),
			"new": "", "dest": None}
	return None


def bestFiles(said, hits):
	"""Of the files a search found, those the user most likely means: one whose name is exactly what was said,
	with or without its ending, shuts out those that merely have the words. hits: (name, ...) tuples."""
	wanted = _plain(said)
	wanted = " ".join(word for word in wanted.split() if word not in ("the", "my", "a", "file", "folder", "document"))
	exact = [hit for hit in hits if _plain(hit[0]) == wanted or _plain(hit[0][:len(hit[0]) - len(endingOf(hit[0]))]) == wanted]
	return exact or list(hits)


def renamed(old, new):
	"""The new name for a file: as the user said it, with the old ending kept where they gave none."""
	ending = endingOf(old)
	return new if not ending or endingOf(new) else new + old[len(old) - len(ending):]


# --- Facts about the computer ---

DISK, MEMORY, PROCESSOR, UPTIME, NETWORK, PROGRAMS, SYSTEM, OVERVIEW = (
	"disk", "memory", "processor", "uptime", "network", "programs", "system", "overview")
TOPICS = [DISK, MEMORY, PROCESSOR, UPTIME, NETWORK, PROGRAMS, SYSTEM, OVERVIEW]
_TOPICS = (
	(DISK, r"\b(disk|disc|drive|drives|storage|free space|space (left|free)|hard drive|ssd|room (left|on))\b"),
	(MEMORY, r"\b(memory|ram)\b"),
	(PROCESSOR, r"\b(processor|cpu|cores?|chip)\b"),
	(UPTIME, r"\b(up ?time|how long\b.*\b(on|running|up|awake)|since\b.*\b(restart|reboot|start)|last (restart|reboot|started))\b"),
	(NETWORK, r"\b(network|internet|wi-?fi|online|offline|connected|connection|ip address|ethernet)\b"),
	(PROGRAMS, r"\b(running|programs?|apps?|applications?|processes|tasks)\b"),
	(SYSTEM, r"\b(windows version|version of windows|which windows|what windows|computer name|name of (my|this|the) (computer|pc)|user ?name|who am i|signed in)\b"),
)
_ABOUT_COMPUTER = re.compile(
	r"\b(disk|disc|drive|drives|storage|free space|space (left|free)|hard drive|ssd|memory|ram|processor|cpu|up ?time|"
	r"ip address|computer name)\b|\bhow long\b.{0,30}\b(computer|pc|laptop|windows)\b.{0,20}\b(on|running|up)\b"
	r"|\b(am i|is (my|the|this) (computer|pc|laptop)) (online|offline|connected)\b|\b(connected to|have) (the )?internet\b"
	r"|\b(which|what) (programs|apps|applications) are (running|open)\b|\bwhat('s| is) running\b"
	r"|\babout (my|this) (computer|pc|laptop)\b|\b(my|this) (computer|pc|laptop)('s)? (specs|specifications)\b", re.IGNORECASE)


def aboutComputer(part):
	text = own(part)
	# The computer's memory is meant, not what VisionClaw remembers, and nothing of NVDA's own.
	return bool(_ABOUT_COMPUTER.search(text)) and not _ASKS_HOW.search(text) and not re.search(
		r"\b(nvda|visionclaw|add-?ons?|skills?)\b|\b(your|its) memor(y|ies)\b", text, re.IGNORECASE)


def topicOf(part):
	"""Which fact about the computer the user's own words ask for."""
	text = own(part).lower()
	for topic, pattern in _TOPICS:
		if re.search(pattern, text):
			return topic
	return OVERVIEW


def diskText(drives):
	"""drives: (letter like "C:", its label, free bytes, total bytes)."""
	if not drives:
		return "Windows named no drives."
	lines = []
	for letter, label, free, total in drives:
		low = total and (free < LOW_SHARE * total or free < LOW_BYTES)
		share = round(100 * free / total) if total else 0
		lines.append(
			f"Drive {letter}" + (f" ({label})" if label else "") + f" has {sizeText(free)} free of {sizeText(total)}, "
			f"{share} percent" + (". That is little." if low else "."))
	return " ".join(lines)


def memoryText(free, total):
	used = round(100 * (total - free) / total) if total else 0
	return f"The computer has {sizeText(total)} of memory. {used} percent of it is in use, and {sizeText(free)} is free."


# --- Requests that depend on something ---

SEEN, BIN_IS, RUNNING = "seen", "bin", "running"
_LEAD = r"^\s*(?:(?:and|then|first|next|also|please|now|ok|okay)[, ]+)*"
_ON_SCREEN = r"(?:\s+(?:anywhere |somewhere )?(?:on|in) (?:my |the |this )?(?:screen|desktop|window|page|display|computer))?(?:\s+(?:there|anywhere))?"
_THEN = rf"\s*(?:[,;:]\s*(?:and\s+)?(?:then\s+)?|\s+then\s+|\s+(?=(?:please\s+)?{_ACT}\b))"
_IF_SEEN = re.compile(
	_LEAD + r"if (?:you |visionclaw |there is |there's |there are )?(?:can |could |do |happen to )?(?:see|find|spot|notice)?s?\s*"
	r"(?:an? |the |my |any |some )?(?P<what>.+?)" + _ON_SCREEN + _THEN + r"(?P<then>.+)$", re.IGNORECASE)
_SEES = re.compile(r"^\s*(?:(?:and|then|first|next|also|please|now)[, ]+)*if (?:(?:you|visionclaw) (?:can |could |do |happen to )?(?:see|find|spot|notice)|there(?:'s| is| are))\b", re.IGNORECASE)
_IS_ON_SCREEN = re.compile(
	_LEAD + r"if (?:an? |the |my )?(?P<what>.+?) (?:is|are|shows?|appears?) (?:shown |showing |visible |up )?(?:on|in) (?:my |the |this )?"
	r"(?:screen|desktop|window|page|display)" + _THEN + r"(?P<then>.+)$", re.IGNORECASE)
_SEEN_AFTER = re.compile(
	r"^(?P<then>.+?),?\s+if (?:you |visionclaw )?(?:can |could |do |happen to )?(?:see|find|spot|notice)s?\s+"
	r"(?P<what>it|one|them|.+?)" + _ON_SCREEN + r"\s*[.!]?$", re.IGNORECASE)
_IF_BIN = re.compile(
	_LEAD + rf"if (?:my |the )?{BIN} (?P<state>is not empty|isn'?t empty|is empty|is full|is getting full|is too full|"
	r"has (?:anything|something|stuff|files|items|things)(?: in it)?|holds (?:anything|something)|"
	r"needs (?:to be )?empt(?:ied|ying)|needs it|should be emptied)" + _THEN + r"(?P<then>.+)$", re.IGNORECASE)
_IF_RUNNING = re.compile(
	_LEAD + r"if (?:an? |the |my )?(?P<what>.+?) (?P<state>is not|isn'?t|is|are not|aren'?t|are) (?:already |currently |still )?"
	r"(?:open|running|started|up)(?: right now| already| at the moment)?" + _THEN + r"(?P<then>.+)$", re.IGNORECASE)
_BACK = re.compile(r"\b(it|them|that one|this one)\b", re.IGNORECASE)


def _resolved(then, what):
	"""What is to be done, with "it" said as the thing the condition names: "open it" is "open recycle bin"."""
	then = then.strip().rstrip(".!")
	return _BACK.sub(what, then, count=1) if what else then


def condition(part):
	"""A request that depends on something plain code can find out, or None:
	{"kind": SEEN, BIN_IS or RUNNING; "what": the thing named; "state": for the Recycle Bin "empty", "some" or
	"worth", for a program True when it must be open; "then": what is to be done, in the user's words with "it"
	said as the thing; "asked": the condition as the user said it}.
	Only these three kinds are understood. Any other "if" is left to be planned as before."""
	text = own(part).strip()
	if not re.search(r"\bif\b", text, re.IGNORECASE):
		return None
	hit = _IF_BIN.match(text)
	if hit:
		said = hit.group("state").lower()
		state = "empty" if said == "is empty" else "worth" if re.search(r"full|needs|should", said) else "some"
		return {"kind": BIN_IS, "what": "the Recycle Bin", "state": state, "then": _resolved(hit.group("then"), "the recycle bin"),
			"asked": text}
	hit = _IF_RUNNING.match(text)
	if hit and not _SEES.match(text):
		what = hit.group("what").strip()
		return {"kind": RUNNING, "what": what, "state": not re.search(r"not|n'?t", hit.group("state").lower()),
			"then": _resolved(hit.group("then"), what), "asked": text}
	hit = (_IF_SEEN.match(text) if _SEES.match(text) else None) or _IS_ON_SCREEN.match(text)
	if hit:
		what = hit.group("what").strip(" ,")
		if what and not STARTS_ACT.match(what):
			return {"kind": SEEN, "what": what, "state": True, "then": _resolved(hit.group("then"), what), "asked": text}
	hit = _SEEN_AFTER.match(text)
	if hit and STARTS_ACT.match(hit.group("then")):
		what = hit.group("what").strip()
		then = hit.group("then").strip()
		if _PRONOUN.match(what):
			what = wanted(then) or _plain(re.sub(rf"^\s*(?:please\s+)?{_ACT}\s+(?:on\s+)?", "", then, flags=re.IGNORECASE))
		if what:
			return {"kind": SEEN, "what": what, "state": True, "then": then.rstrip(".!"), "asked": text}
	return None


_ONLY_TELLS = re.compile(
	r"^\s*(?:please\s+)?(?:just\s+)?(tell me|let me know|say so|say it|say yes|report it|report|warn me|notify me)"
	r"(\s+(about it|so|that|if so))?\s*[.!]?\s*$", re.IGNORECASE)


def onlyTells(then):
	"""Whether what is to be done after a condition is only to say so: then the check's own answer is all."""
	return bool(_ONLY_TELLS.match(then or ""))


def seenWhat(part):
	"""For the form of the step that checks the screen: the thing the user's condition names."""
	found = condition(part)
	return found["what"] if found else own(part)


def seenIn(what, lines):
	"""The line of what is on the screen that has the thing the user named, word for word, or None."""
	wanted_ = match.plain(what)
	if not wanted_:
		return None
	for line in lines:
		if _has(match.plain(line), wanted_):
			return " ".join(str(line).split())
	return None


YES, NO = "Yes:", "No:"


def says(result):
	"""Whether the result of a step that checks something says yes."""
	return str(result or "").lstrip().startswith(YES)
