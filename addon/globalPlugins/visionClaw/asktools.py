# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - answering a question by asking what is on this computer, always in the same order: NVDA (its
# commands where the user is, its user guide, the help of its add-ons), then the program in front, then that
# program's window and the control that has the focus, then Windows itself (its version, the windows that are
# open, and VisionClaw's notes on the keys of Windows). Each gives what it has as small passages; which of
# them are about the question is decided by plain code in claw/lookup.py. Nothing here changes anything, and
# nothing goes online.

import ctypes
import os
import time

import addonHandler
import api

from .claw import partners
from .claw import debuglog, helpfiles, learn, lookup, memories, policy, training
from .claw import task as taskModule
from .claw.catalog import VISION
from .claw.llm import LLM

addonHandler.initTranslation()

# How much of a window is walked for controls that have a key of their own, at most.
MAX_WALKED = 300
WALK_SECONDS = 0.4
MAX_WITH_KEYS = 40
MAX_WINDOWS = 30
# The passages that stay the same while NVDA runs: the user guide, the notes, the help of the add-ons.
_kept = {"count": None, "passages": [], "guide": None, "news": None, "training": [], "trainingStamp": None}


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def _one(text, chars=120):
	text = " ".join(str(text or "").split())
	return text if len(text) <= chars else text[:chars].rstrip() + " ..."


def guideSections(helpDir=""):
	"""All of NVDA's own user guide, as it is on this computer, at its headings. helpDir: where it is kept as
	a Markdown file, made when the guide is newer or another one; it is then read from there."""
	import documentationUtils
	path = documentationUtils.getDocFilePath("userGuide.html")
	if not path or not os.path.isfile(path):
		return []
	if helpDir:
		found = helpfiles.kept(path, os.path.join(helpDir, "nvda-user-guide.md"), "NVDA's user guide", lookup.htmlSections)
	else:
		with open(path, encoding="utf-8", errors="replace") as f:
			found = lookup.htmlSections(f.read())
	return [(title, body, "userGuide") for title, body in found]


def newsSections(helpDir=""):
	"""NVDA's own list of what is new in its newest versions, as it is on this computer; kept as a Markdown
	file like the user guide."""
	import documentationUtils
	path = documentationUtils.getDocFilePath("changes.html")
	if not path or not os.path.isfile(path):
		return []
	if helpDir:
		found = helpfiles.kept(path, os.path.join(helpDir, "nvda-whats-new.md"), "What is new in NVDA", lookup.newsSections)
	else:
		with open(path, encoding="utf-8", errors="replace") as f:
			found = lookup.newsSections(f.read())
	return [(title, body, lookup.NEWS) for title, body in found]


def keptPassages(plugin):
	"""The user guide, VisionClaw's notes and the add-ons' help as passages. Read once, and again when the
	knowledge has changed, as after the developer guides were downloaded."""
	count = _safe(plugin.knowledge.count, 0)
	if _kept["guide"] is None:
		try:
			_kept["guide"] = lookup.fromSections(guideSections(getattr(plugin, "helpDir", "")))
		except Exception as e:
			debuglog.error("lookup", "NVDA's user guide could not be read", e)
			_kept["guide"] = []
	if _kept["news"] is None:
		# Asked only when a question is about what is new or what changed (lookup._NEWS).
		try:
			_kept["news"] = lookup.fromSections(newsSections(getattr(plugin, "helpDir", "")))
		except Exception as e:
			debuglog.error("lookup", "NVDA's list of what is new could not be read", e)
			_kept["news"] = []
	if _kept["count"] != count:
		_kept["count"] = count
		# The whole user guide is read above; the knowledge keeps only the start of each of its sections.
		# The training material is asked as passages of its own below, each only about what its page is about.
		_kept["passages"] = lookup.fromSections(plugin.knowledge.everything(exclude=("userGuide", training.SOURCE)))
	folder = getattr(plugin, "trainingDir", "")
	stamp = _safe(lambda: os.path.getmtime(os.path.join(folder, training.RECORD)), 0) if folder else 0
	if _kept["trainingStamp"] != stamp:
		# Read again after it was downloaded or deleted.
		_kept["trainingStamp"] = stamp
		_kept["training"] = (_safe(lambda: training.passages(folder), []) or []) if stamp else []
	return _kept["guide"] + _kept["news"] + _kept["passages"] + _kept["training"]


def forPicture(plugin, question):
	"""For a question in the description window that asks how something is done: the one command of NVDA,
	among those that work where the user is, that the question names, with its key (followup.known); "" for a
	question about the picture itself. Called from the thread that answers; the commands are read on NVDA's
	main thread."""
	from . import followup, nvdatools
	if not followup.asksHow(question):
		return ""
	known = _safe(lambda: nvdatools.onMain(nvdatools._commands), []) or []
	return followup.known(question, commandPassages(known, "this program"))


def commandPassages(known, app, owners=None):
	"""NVDA's commands where the user is. Those that belong to the program in front are the program's, and
	one that an add-on adds says which add-on it is from (owners: accesstools.addonOwners)."""
	found = []
	for command in known:
		if not command.documented:
			continue  # a command nobody described cannot answer a question
		ofApp = command.source.startswith("appModules.")
		addon = (owners or {}).get(command.source, "")
		origin = f"the add-on {addon}" if addon else f"NVDA's commands for {app}" if ofApp else ""
		found.append(lookup.fromCommand(
			command.scriptName, command.description, command.category, command.line(),
			lookup.APP if ofApp else lookup.NVDA, origin))
	return found


def _control(obj):
	"""A control in a few words: its kind and its name."""
	role = _safe(lambda: obj.role.displayString) or ""
	name = _one(_safe(lambda: obj.name), 80)
	return f"{role} \"{name}\"" if name else (role or "a control without a name")


def _withKeys(window):
	"""The controls of a window that have a key of their own, as "name (kind): key". Stops after a short
	time, so that a huge window does not hold NVDA up."""
	found, seen, queue = [], 0, [window]
	until = time.monotonic() + WALK_SECONDS
	while queue and seen < MAX_WALKED and len(found) < MAX_WITH_KEYS and time.monotonic() < until:
		obj = queue.pop(0)
		child = _safe(lambda o=obj: o.firstChild)
		while child is not None and seen < MAX_WALKED and time.monotonic() < until:
			seen += 1
			key = _one(_safe(lambda c=child: c.keyboardShortcut), 40)
			name = _one(_safe(lambda c=child: c.name), 60)
			if key and name:
				role = _safe(lambda c=child: c.role.displayString) or ""
				line = f"{name}{f' ({role})' if role else ''}: {key}"
				if line not in found:
					found.append(line)
			queue.append(child)
			child = _safe(lambda c=child: c.next)
	return found


def programNow():
	"""The program in front as plain facts: the name of its file, what its maker called it, its version, its
	window's title, and the control that has the focus. Main thread."""
	fg = api.getForegroundObject()
	focus = api.getFocusObject()
	module = _safe(lambda: focus.appModule) or _safe(lambda: fg.appModule)
	return {
		"app": _one(_safe(lambda: module.appName), 60) or "unknown",
		"product": _one(_safe(lambda: module.productName), 80),
		"version": _one(_safe(lambda: module.productVersion), 40),
		"title": _one(_safe(lambda: fg.name), 100),
		"focus": _control(focus),
		"focusName": _one(_safe(lambda: focus.name), 80),
	}


def herePassages(plugin):
	"""What the program in front and its window say: (passages, program name, window title, how many
	controls of the window have a key of their own). Main thread."""
	fg = api.getForegroundObject()
	focus = api.getFocusObject()
	module = _safe(lambda: focus.appModule) or _safe(lambda: fg.appModule)
	app = _one(_safe(lambda: module.appName), 60) or "unknown"
	title = _one(_safe(lambda: fg.name), 100)
	found = []
	# The program.
	product = _one(_safe(lambda: module.productName), 80)
	version = _one(_safe(lambda: module.productVersion), 40)
	text = f"The program in front is {app}"
	if product and product.lower() != app.lower():
		text += f", which is {product}"
	text += f", version {version}." if version else "."
	if (_safe(lambda: type(module).__module__) or "").startswith("appModules."):
		text += " NVDA has extra support made for this program."
	origin = f"the program {app}"
	found.append(lookup.Passage(lookup.APP, "The program in front", text, origin, here=True))
	made = _safe(lambda: plugin.helpers.appLines(app), []) or []
	if made:
		found.append(lookup.Passage(
			lookup.APP, f"Hotkeys VisionClaw made for {app}", " ".join(made), origin, here=True))
	# The window, and the control that has the focus.
	text = f"The window in front is called {title}." if title else "The window in front has no title."
	if _safe(lambda: focus.treeInterceptor) is not None:
		text += " It shows a document or web page that NVDA reads in browse mode."
	found.append(lookup.Passage(lookup.WINDOW, "The window in front", text, "this window", here=True))
	text = f"The focus is on: {_control(focus)}."
	value = _one(_safe(lambda: focus.value), 80)
	if value:
		text += f" Its value is {value}."
	states = sorted(
		_safe(lambda s=state: s.displayString, "") or "" for state in (_safe(lambda: focus.states) or ()))
	states = [state for state in states if state and state not in ("focusable", "focused")]
	if states:
		text += f" It is {', '.join(states[:6])}."
	place = _safe(lambda: focus.positionInfo) or {}
	if place.get("indexInGroup") and place.get("similarItemsInGroup"):
		text += f" It is {place['indexInGroup']} of {place['similarItemsInGroup']}."
	key = _one(_safe(lambda: focus.keyboardShortcut), 40)
	if key:
		text += f" Its own key is {key}."
	described = _one(_safe(lambda: focus.description), 160)
	if described:
		text += f" About it: {described}."
	above = [_control(obj) for obj in (_safe(api.getFocusAncestors, []) or [])[1:] if _safe(lambda o=obj: o.name)]
	if above:
		text += " It is inside: " + ", then ".join(above[-4:]) + "."
	found.append(lookup.Passage(lookup.WINDOW, "The control that has the focus", text, "this window", here=True))
	status = _safe(lambda: api.getStatusBarText(api.getStatusBar()))
	if status:
		found.append(lookup.Passage(
			lookup.WINDOW, "The status bar of this window", f"The status bar says: {_one(status, 240)}.", "this window"))
	keys = _withKeys(fg)
	for at in range(0, len(keys), 8):
		found.append(lookup.Passage(
			lookup.WINDOW, "Keys of the controls in this window", "; ".join(keys[at:at + 8]) + ".", "this window"))
	return found, app, title, len(keys)


def openWindows():
	"""The titles of the windows that are open and visible, as Windows itself lists them."""
	user32 = ctypes.windll.user32
	found = []

	@ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
	def each(hwnd, _extra):
		if len(found) >= MAX_WINDOWS or not user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
			return True
		# A tool window is a floating helper, not a window the user switches to.
		if user32.GetWindowLongW(ctypes.c_void_p(hwnd), -20) & 0x80:
			return True
		# Windows keeps some windows of sleeping apps "cloaked": they count as visible and are shown nowhere.
		cloaked = ctypes.c_int(0)
		try:
			ctypes.windll.dwmapi.DwmGetWindowAttribute(ctypes.c_void_p(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
		except Exception:
			pass
		if cloaked.value:
			return True
		length = user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
		if length <= 0:
			return True
		buffer = ctypes.create_unicode_buffer(length + 1)
		user32.GetWindowTextW(ctypes.c_void_p(hwnd), buffer, length + 1)
		title = _one(buffer.value, 80)
		if title and title != "Program Manager" and title not in found:
			found.append(title)
		return True

	user32.EnumWindows(each, None)
	return found


def windowsName():
	"""Which Windows this is, as NVDA knows it."""
	import winVersion
	version = winVersion.getWinVer()
	name = _safe(lambda: version.releaseName) or "Windows"
	build = _safe(lambda: version.build)
	return f"{name}, build {build}" if build else name


def systemPassages():
	"""What Windows itself says: which Windows this is, and which windows are open."""
	found = []
	name = _safe(windowsName) or "Windows"
	found.append(lookup.Passage(
		lookup.SYSTEM, "The version of Windows on this computer", f"This computer runs {name}.", here=False))
	titles = _safe(openWindows, []) or []
	if titles:
		found.append(lookup.Passage(
			lookup.SYSTEM, "The windows that are open now",
			f"{len(titles)} windows are open now: " + "; ".join(titles) + ".", here=False))
	return found, name, len(titles)


def register(plugin, add, text, onMain, commandsNow):
	"""The tool that asks around. add and text are the helpers of nvdatools.build; commandsNow gives NVDA's
	commands where the user is and must run on the main thread."""

	def lookUp(task, question):
		# Always in this order: NVDA, the program, its window, Windows. Every one is asked every time; which
		# of their answers are about the question is decided afterwards, over all of them together.
		known = onMain(commandsNow)
		task.commands = known
		kept = keptPassages(plugin)
		task.emit(taskModule.DETAIL, (
			f"Asked NVDA: {sum(1 for command in known if command.documented)} commands that work where you are, "
			"its user guide, and the help of its add-ons."))
		task.check()
		here, app, title, withKeys = onMain(herePassages, plugin)
		# A command that an add-on adds says which add-on it is from.
		from . import accesstools
		owners = _safe(lambda: onMain(accesstools.addonOwners), {}) or {}
		passages = commandPassages(known, app, owners) + kept + here
		task.emit(taskModule.DETAIL, (
			f"Asked the program {app}, and its window{f' {title}' if title else ''}. "
			f"Controls in it with a key of their own: {withKeys}."))
		task.check()
		# The notes VisionClaw made about this program from the internet, if the user had it learn about it.
		who = onMain(programNow)
		ident = plugin.appNotes.forProgram(app, learn.candidates(app, who["product"], title))
		noted = learn.passages(plugin.appNotes.read(ident), plugin.appNotes.nameOf(ident) or app) if ident else []
		if noted:
			passages += noted
			task.emit(taskModule.DETAIL, f"Asked VisionClaw's notes on {plugin.appNotes.nameOf(ident) or app}: {len(noted)} passages.")
		system, windowsIs, openCount = systemPassages()
		passages += system
		task.emit(taskModule.DETAIL, f"Asked Windows: {windowsIs}, {openCount} open windows, and the keys of Windows.")
		task.check()
		# Then the documents the user put into the library, and what the user asked VisionClaw to remember.
		names = [name for name in (app, who["product"]) if name and name != "unknown"]
		shelved = _safe(lambda: plugin.library.passages(names), []) or []
		mine = _safe(lambda: lookup.fromMemories(plugin.memories.all()), []) or []
		# What the user asked to be remembered about themselves opens what is only asked when it is named:
		# someone who said once that they come from JAWS is given the page for that without saying it again.
		about = _safe(lambda: [entry.text() for entry in plugin.memories.all() if entry.kind == memories.YOU], []) or []
		passages += shelved + mine
		if shelved or mine:
			task.emit(taskModule.DETAIL, (
				f"Asked your library: {len(shelved)} passages, and what you asked VisionClaw to remember: {len(mine)}."))
		task.check()
		# A question that points at something, "what does this do", is put to a model with where the user is:
		# it says whether the program, the window or the focused control is meant. Plain code offers the three.
		extra = ""
		if lookup.pointsAt(question):
			choices = [
				(lookup.PROGRAM_MEANT, " ".join(part for part in (app, who["product"]) if part)), (lookup.WINDOW_MEANT, title),
				(lookup.CONTROL_MEANT, who["focus"] if who["focusName"] else "")]
			choices = [choice for choice in choices if choice[1]]
			said = lookup.saysWhich(question)
			if said:
				# "This program", "this button": the user's own words say which, and no model is asked.
				meant = next((at for at, (what, _named) in enumerate(choices) if what == said), None)
			else:
				meant = lookup.referent(LLM(plugin.runtime, task), VISION, question, choices)
			if meant is not None:
				what, named = choices[meant]
				extra = who["focusName"] if what == lookup.CONTROL_MEANT else title if what == lookup.WINDOW_MEANT else ""
				if not said:
					task.emit(taskModule.DETAIL, (
						f"The {policy.roleName(VISION, policy.isOneModel(plugin.runtime))} takes the question to be about "
						f"{what}: {named}."))
		found = lookup.about(question, passages, extra=extra, program=names + training.comesFrom(about + (["I come from JAWS"] if partners.has(partners.JAWS) else [])))
		debuglog.log("lookup", (
			f"Asked {len(passages)} passages about \"{question}\". Telling words: {sorted(lookup.asked(question)[0])}. "
			f"Found: {[(passage.origin, passage.title or passage.text[:50]) for passage in found]}"))
		if not found:
			return lookup.nothingText(
				question, app, title, notes=bool(noted), library=bool(shelved), memories=bool(mine),
				guides=_safe(lambda: plugin.devGuides.here()))
		return lookup.resultText(found)

	add(lookup.TOOL,
		"answer a question about how to do something with the keyboard or what something is: asks NVDA (its "
		"commands and user guide), then the program in front, then its window, then Windows, then the user's "
		"library and memories, and gives what they say that is about the question",
		lookUp, {"question": text("the user's question, in their own words", maxLength=300, auto=True)},
		looks=True, title="Asking NVDA, the program, the window and Windows")
