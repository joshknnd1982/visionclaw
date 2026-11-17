# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools the models can use inside NVDA. Each tool is a small form and a function.
# The functions run on the task's worker thread; everything that touches NVDA is passed to NVDA's main thread.

import difflib
import html
import importlib
import inspect
import os
import re
import threading
import time

import addonHandler
import api
import config
import inputCore
import scriptHandler
import synthDriverHandler
import ui
import wx
from logHandler import log

from . import nvdainfo, ocr, webtools
from .claw import drivers, match, microaddons, policy, web
from .claw.catalog import CODER, VISION
from .claw.llm import LLM, clip
from .claw.memory import score
from .claw.tools import ANSWER, VERBATIM, Registry, Tool, ToolError
from .engine import EngineError, prepareImage

addonHandler.initTranslation()

MAX_ITEMS_SHOWN = 45
MAX_FOUND = 6
CLICK_SETTLE_SECONDS = 0.7
# After an address is given to the browser: the shortest and longest wait for the page to be there.
WEB_SETTLE_SECONDS = 1.5
WEB_WAIT_SECONDS = 25
# An add-on about something on screen is written with the vision model's view of the window.
_ABOUT_SCREEN = re.compile(
	r"\b(this|these|that|current|focused|unlabell?ed|no name|button|window|program|app|game|screen|control)\b", re.IGNORECASE)
# The browser's own keys for moving between pages.
_PAGE_KEYS = {"back": "alt+leftArrow", "forward": "alt+rightArrow", "reload": "f5"}
_PAGE_DONE = {"back": "Went back", "forward": "Went forward", "reload": "Reloaded the page"}


def directionOf(part):
	"""Which way to go in the browser, from what the user said."""
	text = (part or "").lower()
	if re.search(r"reload|refresh", text):
		return "reload"
	return "forward" if re.search(r"forward|next page", text) else "back"


_SUBMITS = re.compile(r"\b(search|submit|send|go|log ?in|sign ?in|press enter|and enter)\b", re.IGNORECASE)
# Settings that are not for changing by a model: they can lock the user out, need a restart, or hold secrets.
_SKIP_SECTIONS = frozenset((
	"update", "addonStore", "development", "upgrade", "debugLog", "visionClaw", "remote", "automatedImageDescriptions",
))
_SKIP_KEYS = frozenset(("synth", "outputDevice", "display", "port", "language", "loggingLevel", "playErrorSound"))
# Extra words people use for a setting, so it is found by plain language.
_ALIASES = {
	"speech.rate": "speed fast faster slow slower quick quicker talk talking speaking tempo",
	"speech.pitch": "tone high higher low lower deep",
	"speech.volume": "loud louder quiet quieter soft softer sound level",
	"speech.voice": "speaker person male female accent",
	"speech.symbolLevel": "punctuation symbols level read commas periods",
	"keyboard.speakTypedCharacters": "echo typing letters keys characters typed say what I type",
	"keyboard.speakTypedWords": "echo typing words typed",
	"keyboard.speakCommandKeys": "echo command keys shortcuts",
	"keyboard.useCapsLockAsNVDAModifierKey": "caps lock nvda key modifier",
	"keyboard.keyboardLayout": "desktop laptop layout",
	"mouse.enableMouseTracking": "mouse follow pointer read under mouse",
	"mouse.audioCoordinatesOnMouseMove": "mouse beeps coordinates",
	"speech.autoLanguageSwitching": "language switch automatically",
	"speech.includeCLDR": "emoji emojis symbols descriptions",
	"presentation.reportTooltips": "tooltips hints",
	"presentation.reportHelpBalloons": "notifications balloons toasts",
	"presentation.progressBarUpdates.progressBarOutputMode": "progress bar beeps speak percent",
	"documentFormatting.reportSpellingErrors": "spelling mistakes errors",
	"documentFormatting.reportFontName": "font name",
	"documentFormatting.reportFontSize": "font size",
	"documentFormatting.reportHeadings": "headings",
	"documentFormatting.reportLinks": "links",
	"reviewCursor.followFocus": "review cursor follow focus",
	"virtualBuffers.autoSayAllOnPageLoad": "web page read automatically say all browse",
	"audio.audioDuckingMode": "ducking lower other sounds music volume while speaking",
	"speech.variant": "voice variant style",
	"speech.inflection": "intonation expressive monotone",
	"speech.rateBoost": "rate boost extra fast speed",
	"braille.tetherTo": "braille follow focus review cursor tether",
	"braille.showCursor": "braille cursor show",
	"braille.cursorBlink": "braille cursor blink",
	"braille.showMessages": "braille messages show",
	"braille.wordWrap": "braille word wrap avoid splitting words",
	"braille.readByParagraph": "braille paragraph",
	"braille.expandAtCursor": "braille computer braille expand cursor word",
	"speech.speakTypedCharacters": "echo",
}
_NAMED_VALUES = {"speech.symbolLevel": {"none": 0, "some": 100, "most": 200, "all": 300}}
_SYNTH_NUMBERS = ("rate", "pitch", "volume")
_TARGETS = ["window", "screen", "control"]
# After a switch of synthesizer or braille display, how long the user has to say that it works.
KEEP_SECONDS = 20
# NVDA commands that can take speech or NVDA itself away. The user is always asked first, and told how to undo it.
_RISKY_COMMANDS = {
	"speechMode": "This can turn NVDA's speech off. Running the same command again brings it back.",
	"quit": "This closes NVDA, so the computer stops talking until NVDA is started again.",
	"restart": "This restarts NVDA. Speech stops for a few seconds.",
	"toggleCurrentAppSleepMode": "This makes NVDA silent in the current program until it is run again there.",
}


def targetOf(part):
	"""What a request wants looked at, from its words: the whole screen, the focused control, or the window."""
	text = part.lower()
	if re.search(r"\b(screen|desktop|everything)\b", text):
		return "screen"
	if re.search(r"\b(this|the|focused|current) (button|control|icon|item|image|picture|photo|field)\b", text):
		return "control"
	return "window"


def onMain(fn, *args, timeout=20):
	"""Run fn on NVDA's main thread and return its result."""
	if wx.IsMainThread():
		return fn(*args)
	done = threading.Event()
	box = {}

	def run():
		try:
			box["value"] = fn(*args)
		except Exception as e:
			box["error"] = e
		done.set()

	wx.CallAfter(run)
	if not done.wait(timeout):
		raise ToolError("NVDA did not answer in time.")
	if "error" in box:
		raise box["error"]
	return box.get("value")


def pickItem(reference, items, prefer=()):
	"""Which item a model means. A number from the list, the item's full text ("Refund policy heading"), or its
	name. Where several items have the same name, one of the preferred kinds wins: a heading when moving
	there, a link or button when clicking."""
	wanted = " ".join(str(reference or "").lower().split())
	for i, item in enumerate(items):
		if item["text"].lower() == wanted:
			return i
	names = [item.get("plain") or item.get("name") or item["text"] for item in items]
	index = match.itemIndex(reference, names)
	if index is None:
		return match.itemIndex(reference, [item["text"] for item in items])
	if not wanted.isdigit():
		same = [i for i, name in enumerate(names) if match.plain(name) == match.plain(names[index])]
		for kind in prefer:
			for i in same:
				if items[i].get("kind") == kind:
					return i
	return index


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


class Refused(Exception):
	"""VisionClaw will not do this, because it would leave the user without speech and braille. Not an error
	to retry: the step is finished, with nothing changed, and the reason is told to the user."""


class UserSaidNo(Exception):
	"""The user was asked and declined. Not an error: the step is finished, with nothing changed."""


# --- NVDA settings ---

class _Setting:
	def __init__(self, ident, label, kind, read, write, low=None, high=None, options=None):
		self.id = ident
		self.label = label
		self.kind = kind  # "bool", "number", "option"
		self.read = read
		self.write = write
		self.low, self.high, self.options = low, high, options

	def shown(self, value=None):
		value = self.read() if value is None else value
		if self.kind == "bool":
			return "on" if value else "off"
		named = _NAMED_VALUES.get(self.id)
		if named:
			for name, number in named.items():
				if number == value:
					return name
		return str(value)

	def allowed(self):
		if self.kind == "bool":
			return "on or off"
		if self.kind == "number":
			return f"a number from {self.low} to {self.high}"
		return "one of: " + ", ".join(str(o) for o in self.options)

	def parse(self, raw):
		if self.kind == "bool":
			value = match.toBool(raw)
			if value is None:
				raise ValueError(f"\"{raw}\" is not allowed. Allowed: on or off.")
			return value
		if self.kind == "number":
			return match.toNumber(raw, self.read(), self.low, self.high)
		chosen = match.toOption(raw, self.options)
		return _NAMED_VALUES.get(self.id, {}).get(chosen, chosen)


def _confSetting(path, spec):
	"""A setting from NVDA's own configuration, or None if it is not a kind a model should change."""
	ident = ".".join(path)
	section, key = path[:-1], path[-1]

	def node():
		found = config.conf
		for name in section:
			found = found[name]
		return found

	def read():
		return node()[key]

	def write(value):
		node()[key] = value

	label = f"{match.label(section[-1])} {match.label(key)}"
	if ident in _NAMED_VALUES:
		return _Setting(ident, label, "option", read, write, options=list(_NAMED_VALUES[ident]))
	if spec.startswith("boolean"):
		return _Setting(ident, label, "bool", read, write)
	if spec.startswith("integer"):
		low, high = re.search(r"min\s*=\s*(-?\d+)", spec), re.search(r"max\s*=\s*(-?\d+)", spec)
		if not (low and high):
			return None
		return _Setting(ident, label, "number", read, write, int(low.group(1)), int(high.group(1)))
	if spec.startswith("option"):
		options = re.findall(r"[\"']([^\"']+)[\"']", spec.split("default")[0])
		return _Setting(ident, label, "option", read, write, options=options) if options else None
	return None


def _walkSpec(spec, path=()):
	for key, value in spec.items():
		if key.startswith("__") or key in _SKIP_KEYS or (not path and key in _SKIP_SECTIONS):
			continue
		if hasattr(value, "items"):
			if len(path) < 3:
				yield from _walkSpec(value, path + (key,))
		elif isinstance(value, str) and path:
			yield path + (key,), value


def _driverSettings(driver, prefix, label, section):
	"""Every setting a synthesizer or braille display driver offers, such as voice, variant, rate, pitch and
	whatever else that driver has. prefix starts the setting's id; section is where NVDA saves it."""
	found = []
	if driver is None:
		return found

	def save(name, value):
		setattr(driver, name, value)
		try:
			config.conf[section][driver.name][name] = value
		except Exception:
			log.debugWarning("VisionClaw: could not save the driver setting", exc_info=True)

	for setting in _safe(lambda: list(driver.supportedSettings), []) or []:
		name = _safe(lambda s=setting: s.id)
		if not name:
			continue
		ident, shown = f"{prefix}.{name}", f"{label} {match.label(name)}"
		kind = type(setting).__name__
		if kind == "NumericDriverSetting":
			found.append(_Setting(
				ident, shown, "number", lambda n=name: int(getattr(driver, n)), lambda v, n=name: save(n, v),
				_safe(lambda s=setting: int(s.minVal), 0), _safe(lambda s=setting: int(s.maxVal), 100),
			))
		elif kind == "BooleanDriverSetting":
			found.append(_Setting(ident, shown, "bool", lambda n=name: bool(getattr(driver, n)), lambda v, n=name: save(n, v)))
		else:
			choices = _safe(lambda n=name: getattr(driver, f"available{n[0].upper()}{n[1:]}s")) or {}
			if len(choices) < 2:
				continue
			names = {info.displayName: key for key, info in choices.items()}
			found.append(_Setting(
				ident, shown, "option",
				lambda n=name, names=names: next((d for d, k in names.items() if k == getattr(driver, n)), getattr(driver, n)),
				lambda v, n=name, names=names: save(n, names.get(v, v)), options=list(names)[:40],
			))
	return found


def _synthSettings():
	import braille
	found = _driverSettings(synthDriverHandler.getSynth(), "speech", "speech", "speech")
	display = _safe(lambda: braille.handler.display)
	if display is not None and _safe(lambda: display.name) not in (None, "noBraille"):
		found += _driverSettings(display, "brailleDisplay", "braille display", "braille")
	return found


def allSettings():
	"""Every setting a model may change. Must be called on the main thread."""
	found = _synthSettings()
	for path, spec in _walkSpec(config.conf.spec):
		try:
			setting = _confSetting(path, spec)
			if setting is not None:
				setting.read()  # leaves out settings that do not exist on this version of NVDA
				found.append(setting)
		except Exception:
			continue
	return found


def _findSettings(words):
	scored = []
	for setting in allSettings():
		text = f"{setting.label} {setting.id.replace('.', ' ')} {_ALIASES.get(setting.id, '')}"
		s = score(words, text)
		if s >= 0.34:
			scored.append((s, setting))
	scored.sort(key=lambda x: -x[0])
	return [
		f"{s.id}: {s.label}. Now: {s.shown()}. Allowed: {s.allowed()}." for _score, s in scored[:MAX_FOUND]
	]


def _resolveSetting(ident):
	settings = allSettings()
	for setting in settings:
		if setting.id == ident:
			return setting
	index = match.best(str(ident).replace(".", " "), [s.id.replace(".", " ") for s in settings], least=0.85)
	return settings[index] if index is not None else None


# --- NVDA commands ---

class _Command:
	def __init__(self, ident, info, keys):
		self.id = ident
		self.info = info
		self.keys = keys
		self.text = f"{info.displayName} ({info.category})"


def _commands():
	"""Every command NVDA has where the user is now, with its keys. Must be called on the main thread."""
	focus = api.getFocusObject()
	mappings = inputCore.manager.getAllGestureMappings(obj=focus, ancestors=api.getFocusAncestors())
	layout = _safe(lambda: config.conf["keyboard"]["keyboardLayout"], "desktop")
	found, used = [], {}
	for _category, scripts in mappings.items():
		for _name, info in scripts.items():
			keys = []
			for gesture in info.gestures:
				if not (gesture.startswith("kb:") or gesture.startswith(f"kb({layout}):")):
					continue
				shown = _safe(lambda g=gesture: inputCore.getDisplayTextForGestureIdentifier(g)[1])
				if shown and shown not in keys:
					keys.append(shown)
			ident = info.scriptName
			used[ident] = used.get(ident, 0) + 1
			if used[ident] > 1:
				ident = f"{ident}{used[ident]}"
			found.append(_Command(ident, info, keys))
	return found


def _driverState():
	"""The speech synthesizer and braille display in use, and those installed, as (name, description) pairs."""
	import braille
	synth = synthDriverHandler.getSynth()
	display = _safe(lambda: braille.handler.display)
	return {
		drivers.SYNTH: (_safe(lambda: synth.name), _safe(lambda: synth.description) or _safe(lambda: synth.name)),
		drivers.DISPLAY: (_safe(lambda: display.name), _safe(lambda: display.description) or _safe(lambda: display.name)),
		"installed": {
			drivers.SYNTH: [(n, d) for n, d in (_safe(synthDriverHandler.getSynthList, []) or [])],
			drivers.DISPLAY: [(n, d) for n, d in (_safe(lambda: braille.getDisplayList(), []) or [])],
		},
	}


def _setDriver(kind, name):
	"""Switch the speech synthesizer or the braille display. True only if it is really in use afterwards."""
	import braille
	try:
		if kind == drivers.SYNTH:
			synthDriverHandler.setSynth(name)
			return synthDriverHandler.getSynth().name == name
		braille.handler.setDisplayByName(name)
		return braille.handler.display.name == name
	except Exception:
		log.warning(f"VisionClaw: could not switch the {kind} to {name}", exc_info=True)
		return False


def _commandTarget(cls):
	"""The live object a command belongs to."""
	import globalCommands
	import globalPluginHandler
	focus = api.getFocusObject()
	candidates = [globalCommands.commands] + list(globalPluginHandler.runningPlugins)
	candidates += [_safe(lambda: focus.appModule), _safe(lambda: focus.treeInterceptor), focus]
	candidates += list(reversed(api.getFocusAncestors()))
	for candidate in candidates:
		if candidate is not None and isinstance(candidate, cls):
			return candidate
	return None


def _runCommand(command):
	from keyboardHandler import KeyboardInputGesture
	target = _commandTarget(command.info.cls)
	func = getattr(target, "script_" + command.info.scriptName, None) if target is not None else None
	if func is None:
		raise ToolError(f"The command {command.id} cannot be used where the user is now.")
	gesture = None
	for keys in command.keys:
		gesture = _safe(lambda k=keys: KeyboardInputGesture.fromName(k.replace(" ", "")))
		if gesture is not None:
			break
	scriptHandler.executeScript(func, gesture)


class _SpeechCapture:
	"""Collects what NVDA says for a moment, so a model can use what a command reported."""

	def __init__(self):
		self.texts = []
		self._filter = None

	def __enter__(self):
		try:
			from speech import extensions
			self._filter = getattr(extensions, "filter_speechSequence", None)
			if self._filter is not None:
				self._filter.register(self._collect)
		except Exception:
			self._filter = None
		return self

	def _collect(self, value):
		try:
			self.texts += [item for item in value if isinstance(item, str) and item.strip()]
		except Exception:
			pass
		return value

	def __exit__(self, *exc):
		if self._filter is not None:
			try:
				self._filter.unregister(self._collect)
			except Exception:
				pass


# --- What is on the screen ---

class Screen:
	"""Pictures and items of what the user is working with."""

	def __init__(self, plugin):
		self.plugin = plugin

	def where(self):
		"""(program name, window title, the window in front, the focused control). Main thread."""
		fg = api.getForegroundObject()
		focus = api.getFocusObject()
		return (_safe(lambda: fg.appModule.appName) or "?", _safe(lambda: fg.name) or "", fg, focus)

	def controlFacts(self):
		"""What NVDA knows about the focused control, in the terms add-on code uses to pick it out."""
		app, title, fg, focus = self.where()
		role = _safe(lambda: focus.role.name) or "UNKNOWN"
		lines = [
			f"The focused control: appName {app!r}, role controlTypes.Role.{role}, name {_safe(lambda: focus.name)!r}, "
			f"windowClassName {_safe(lambda: focus.windowClassName)!r}, windowControlID {_safe(lambda: focus.windowControlID)!r}.",
		]
		parent = _safe(lambda: focus.parent)
		if parent is not None:
			lines.append(
				f"Its parent: role controlTypes.Role.{_safe(lambda: parent.role.name) or 'UNKNOWN'}, "
				f"name {_safe(lambda: parent.name)!r}.")
		lines.append(f"The window in front: windowClassName {_safe(lambda: fg.windowClassName)!r}, title {title!r}.")
		return "\n".join(lines)

	def situation(self):
		app, title, _fg, focus = self.where()
		role = _safe(lambda: focus.role.displayString) or ""
		name = _safe(lambda: focus.name) or "no name"
		return f"Program: {app}. Window title: {title or 'none'}. Focused control: {role}, {name}."

	def box(self, target):
		"""The screen rectangle of a target as (left, top, right, bottom), or None for the whole screen. Main thread."""
		if target == "screen":
			return None
		_app, _title, fg, focus = self.where()
		if target == "control":
			loc = _safe(lambda: focus.location)
			if loc and loc.width > 0 and loc.height > 0:
				return (loc.left, loc.top, loc.left + loc.width, loc.top + loc.height)
		loc = self.plugin.windowBox(fg)
		return (loc.left, loc.top, loc.left + loc.width, loc.top + loc.height)

	def picture(self, target):
		box = onMain(self.box, target)
		try:
			return self.plugin._grab(box), box
		except Exception as e:
			raise ToolError(f"The screen could not be captured: {e}")

	def items(self):
		"""What can be acted on where the user is. In a web page: its links, buttons and fields, as NVDA knows
		them. Anywhere else: the texts and icons of the window in front, read from its picture."""
		found = onMain(webtools.pageItems)
		if found is not None and found.items:
			return found
		from contentRecog import RecogImageInfo
		from . import overlay
		app, title, _fg, _focus = onMain(self.where)
		image, box = self.picture("window")
		lines = ocr.recognize(image)
		recognizer = overlay.OverlayRecognizer(self.plugin, app, live=False, underCurtain=False, title=title)
		info = RecogImageInfo.createFromRecognizer(box[0], box[1], box[2] - box[0], box[3] - box[1], recognizer)
		return recognizer._makeResult(image, lines, info)

	@staticmethod
	def names(result):
		return [item.get("plain") or item.get("name") or item["text"] for item in result.items]

	@staticmethod
	def click(result, item):
		"""Activate a web page item the way NVDA does, or click the middle of an item in a window and put the
		mouse back. Main thread."""
		if item.get("web") is not None:
			webtools.activate(item)
			return
		import mouseHandler
		import winUser
		x, y = result.screenPoint(item)
		old = winUser.getCursorPos()
		winUser.setCursorPos(x, y)
		mouseHandler.doPrimaryClick()
		wx.CallLater(150, winUser.setCursorPos, *old)


# --- Knowledge ---

def userGuideSections():
	"""NVDA's own user guide, as sections, so the models can read how NVDA works."""
	import documentationUtils
	path = documentationUtils.getDocFilePath("userGuide.html")
	if not path or not os.path.isfile(path):
		return []
	with open(path, encoding="utf-8", errors="replace") as f:
		page = f.read()
	found = []
	parts = re.split(r"<h[1-4][^>]*>(.*?)</h[1-4]>", page, flags=re.DOTALL)
	for i in range(1, len(parts) - 1, 2):
		title = html.unescape(re.sub(r"<[^>]+>", "", parts[i])).strip()
		body = html.unescape(re.sub(r"<[^>]+>", " ", parts[i + 1]))
		body = " ".join(body.split())
		if title and len(body) > 40:
			found.append((title, body[:1500], "userGuide"))
	return found


def _inspect(name):
	"""What a module, class or function of NVDA is: its kind, how it is called, its help text and members."""
	parts = [p for p in re.split(r"[.\s]+", str(name).strip()) if p]
	if not parts or not all(p.isidentifier() for p in parts):
		raise ToolError("Give a dotted name like api.getFocusObject or controlTypes.Role.")
	if parts[0] in microaddons.FORBIDDEN_MODULES:
		raise ToolError(f"{parts[0]} is not an NVDA module that add-ons may use.")
	found = None
	for cut in range(len(parts), 0, -1):
		try:
			found = importlib.import_module(".".join(parts[:cut]))
		except Exception:
			continue
		for attr in parts[cut:]:
			if not hasattr(found, attr):
				raise ToolError(f"{'.'.join(parts[:cut])} has nothing called {attr}. It has: {_members(found)}")
			found = getattr(found, attr)
		break
	if found is None:
		raise ToolError(f"NVDA has no module called {parts[0]}.")
	lines = [f"{'.'.join(parts)} is a {type(found).__name__}."]
	if callable(found):
		signature = _safe(lambda: str(inspect.signature(found)))
		if signature:
			lines.append(f"Call it as {parts[-1]}{signature}.")
	doc = inspect.getdoc(found)
	if doc:
		lines.append(clip(doc, 500))
	if inspect.ismodule(found) or inspect.isclass(found):
		lines.append("It has: " + _members(found))
	return "\n".join(lines)


def failingLine(trace):
	"""Where in the add-on's own code an error happened, from NVDA's traceback."""
	found = re.findall(r'File "[^"]*plugin\.py", line (\d+), in (\w+)\n\s*(.+)', trace or "")
	if not found:
		return ""
	number, function, code = found[-1]
	return f"The failing line is line {number}, in {function}: {code.strip()}"


def debugFacts(error):
	"""What NVDA really offers where an add-on used something that does not exist. This is how the models
	learn how NVDA works from their own mistakes: by looking inside the running NVDA."""
	facts = []
	missing = re.search(r"module '([\w.]+)' has no attribute '(\w+)'", error)
	if missing:
		module = _safe(lambda: importlib.import_module(missing.group(1)))
		if module is not None:
			names = [n for n in dir(module) if not n.startswith("_")]
			close = difflib.get_close_matches(missing.group(2), names, 6, 0.4)
			facts.append(
				f"{missing.group(1)} has nothing called {missing.group(2)}. "
				+ (f"Names it does have that are close: {', '.join(close)}." if close else f"It has: {clip(', '.join(names), 400)}"))
	undefined = re.search(r"name '(\w+)' is not defined", error)
	if undefined:
		facts.append(f"{undefined.group(1)} is used but was never imported or defined. Import it, or define it first.")
	if re.search(r"object has no attribute '(\w+)'", error) and not missing:
		facts.append(
			"An object was asked for something it does not have. NVDA's controls have: name, role, states, value, "
			"description, location, parent, children, firstChild, next, previous, appModule, windowClassName, "
			"windowControlID. Check for None before using a control.")
	if "NoneType" in error:
		facts.append("Something was None. Check that the control and its properties are not None before using them.")
	return facts


def fixAddon(plugin, task, name, said=""):
	"""Have the models debug and correct an add-on VisionClaw wrote. said is what the user says is wrong; the
	errors NVDA reported while the add-on ran are added. Returns a sentence for the user."""
	store = plugin.helpers.store
	names = [meta["name"] for meta in store.list()]
	index = match.best(name, names)
	if index is None:
		raise ToolError(f"There is no add-on called \"{name}\". Use a name from list_helpers.")
	ident = names[index]
	meta, source = store.meta(ident), store.source(ident)
	purpose = meta.get("purpose") or ident
	problems, mistakes = [], []
	if said:
		problems.append(f"The user says: {said}")
	for entry in plugin.helpers.errors.get(ident, [])[-2:]:
		problems.append(
			f"When it ran in NVDA, {entry['where']} failed with {entry['error']}. {failingLine(entry['trace'])}".strip())
		problems += debugFacts(entry["error"])
		mistakes.append(entry["error"])
	if not problems:
		raise ToolError("Say what the add-on does wrong, or what it should do instead.")
	if task.params is None:
		task.params = policy.select({"complexity": policy.COMPLEX, "needs_code": True}, task.reasoning)
	notes = plugin.knowledge.text(
		f"{purpose} {' '.join(mistakes)}", limit=2, chars=600, sources=("addon-development", "objects-and-events"))
	lessons = plugin.memory.search("NVDA add-on code mistake " + purpose, limit=3)
	if lessons:
		notes += "\nMistakes made before on this computer:\n" + "\n".join(f"- {text}" for text in lessons)
	fixed = microaddons.fix(LLM(plugin.runtime, task), task, purpose, source, problems, notes, task.params, CODER, VISION)
	repairs = meta.get("repairs", 0) + 1
	store.save(ident, fixed, purpose, repairs=repairs)
	try:
		onMain(plugin.helpers.loadAddon, ident)
	except Exception as e:
		store.save(ident, source, purpose, enabled=False, repairs=repairs)
		raise ToolError(f"The corrected add-on did not start either: {type(e).__name__}: {e}")
	plugin.helpers.errors.pop(ident, None)
	for mistake in mistakes:
		plugin.memory.add(f"NVDA add-on code mistake to avoid: {mistake}", topic="add-on code")
	return f"The add-on {ident} was corrected and is on again."


def _members(obj):
	names = [n for n in dir(obj) if not n.startswith("_")]
	return clip(", ".join(names), 700)


# --- Building the tools ---

def build(plugin):
	"""The tools for one running VisionClaw. plugin is the global plugin."""
	registry = Registry()
	screen = plugin.clawScreen

	def confirm(question):
		"""Ask the user before changing something, unless they turned that off."""
		if not config.conf["visionClaw"]["confirmChanges"]:
			return
		# Translators: The two choices when VisionClaw asks before it changes something.
		if plugin.clawAsk(question, [_("Yes, do it"), _("No, leave it")]) != 0:
			raise UserSaidNo()

	def mustAgree(question):
		"""For anything that could take speech or braille away: always asked, whatever the settings say."""
		# Translators: The two choices when VisionClaw asks before something that could cut off speech or braille.
		if plugin.clawAsk(question, [_("Yes, do it"), _("No, leave it")]) != 0:
			raise UserSaidNo()

	def guarded(fn):
		"""A tool function where the user saying no ends the step quietly instead of as an error."""
		def run(task, **form):
			try:
				return fn(task, **form)
			except UserSaidNo:
				return "You said no, so nothing was changed."
			except Refused as e:
				return f"VisionClaw did not do this. {e}"
			except ValueError as e:
				raise ToolError(str(e))
		return run

	def add(name, description, fn, fields=None, **options):
		registry.add(Tool(name, description, guarded(fn), fields, **options))

	def text(description, **extra):
		spec = {"type": "string", "description": description}
		spec.update(extra)
		return spec

	# Where the user is.
	add("focus_info", "say which program, window and control the user is in", lambda task: onMain(screen.situation),
		looks=True, title="Checking where you are", tell=VERBATIM)

	# Looking, with the vision model.
	def look(task, target, question):
		image, _box = screen.picture(target)
		task.check()
		lines = ocr.recognize(image) if config.conf["visionClaw"]["useOcr"] else []
		prompt = (
			ocr.promptPart(lines) + f"Look at this picture of the user's {target} and answer: {question} "
			"Answer in a few short sentences. If you cannot see it, say so instead of guessing."
		)
		task.emit("talk", f"Asked the vision model: {question}")
		answer = plugin.runtime.describe(prepareImage(image, config.conf["visionClaw"]["detailSize"]), prompt, 350,
			cancel=task.cancel)
		task.check()
		task.emit("talk", f"The vision model answered: {clip(answer, 400)}")
		return answer or "The vision model gave no answer."

	add("look", "look at the screen with the vision model and answer a question about what is shown", look, {
		"target": text("what to look at", enum=_TARGETS, auto=targetOf),
		"question": text("what to find out, as a full question", maxLength=200, auto=True),
	}, looks=True, title="Looking at the screen", tell=VERBATIM)

	def readText(task, target):
		image, _box = screen.picture(target)
		found = ocr.rowsText(ocr.recognize(image)).strip()
		return found or "No text was found there."

	add("read_text", "read the exact text shown in the window, on the screen or in the focused control", readText,
		{"target": text("where to read", enum=_TARGETS, auto=targetOf)}, looks=True, title="Reading the text",
		tell=VERBATIM)

	def listItems(task, about):
		result = screen.items()
		isWeb = getattr(result, "web", False)
		# What is being looked for comes first, so it is among the items a small model is shown.
		result.items.sort(key=lambda item: -score(about, item["text"]))
		task.items = result
		names = [item["text"] for item in result.items]
		if not names:
			return "Nothing was found in this window."
		shown = "\n".join(f"{i}. {name}" for i, name in enumerate(names[:MAX_ITEMS_SHOWN], 1))
		more = f"\n... and {len(names) - MAX_ITEMS_SHOWN} more." if len(names) > MAX_ITEMS_SHOWN else ""
		where = f"on the web page {result.title}" if isWeb else "in the window"
		return f"{len(names)} items {where}:\n{shown}{more}"

	add("list_items",
		"list what can be clicked or filled in: the links, buttons and fields of a web page, or the buttons, texts "
		"and icons of a window, even one NVDA cannot read",
		listItems, {"about": text("what is being looked for, in a few words", maxLength=120, auto=True)},
		looks=True, title="Listing what is there")

	def clickItem(task, item):
		result = getattr(task, "items", None)
		if result is None or not result.items:
			raise ToolError("Use list_items first.")
		index = pickItem(item, result.items, ("link", "button"))
		if index is None:
			raise ToolError(f"There is no item called \"{item}\". Use a number or a name from list_items.")
		found = result.items[index]
		if found.get("kind") != "link":  # following a link only goes to another page
			# Translators: Asked before VisionClaw clicks something. {item} is what will be clicked.
			confirm(_("Click {item}?").format(item=found["text"]))
		onMain(Screen.click, result, found)
		time.sleep(CLICK_SETTLE_SECONDS)
		task.items = None  # the window has probably changed
		return f"Clicked {found['text']}."

	add("click_item", "click one item from list_items: follow a link, press a button, click an item in a window",
		clickItem,
		{"item": text("the number or the name of the item, from list_items", maxLength=80)},
		changes=True, before="list_items", title="Clicking the item")

	def pressKeys(task, keys):
		from keyboardHandler import KeyboardInputGesture
		names = [k.strip().replace(" ", "") for k in re.split(r",|\bthen\b", keys) if k.strip()]
		if not names:
			raise ToolError("Give at least one key, like enter or control+s.")
		gestures = []
		for name in names[:8]:
			try:
				gestures.append(KeyboardInputGesture.fromName(name))
			except Exception:
				raise ToolError(f"\"{name}\" is not a key. Examples: enter, escape, tab, control+s, alt+f4, downArrow.")
		# Translators: Asked before VisionClaw presses keys for the user. {keys} are the keys.
		confirm(_("Press {keys} in the program?").format(keys=", ".join(names)))
		for gesture in gestures:
			onMain(gesture.send)
			time.sleep(0.12)
		return f"Pressed {', '.join(names)}."

	add("press_keys", "press keys in the program in front, as if the user typed them", pressKeys,
		{"keys": text("the keys, separated by commas, like alt+f, enter", maxLength=120)}, changes=True,
		title="Pressing keys")

	def typeText(task, textToType):
		import brailleInput
		# Translators: Asked before VisionClaw types text for the user. {text} is the text.
		confirm(_("Type \"{text}\" into the program?").format(text=clip(textToType, 80)))
		onMain(brailleInput.handler.sendChars, textToType)
		return f"Typed: {clip(textToType, 80)}"

	registry.add(Tool("type_text", "type text into the program in front", guarded(lambda task, text: typeText(task, text)),
		{"text": text("the text to type", maxLength=400)}, changes=True, title="Typing"))

	def nameControl(task, name):
		def work():
			focus = api.getFocusObject()
			image = plugin._buttonImage(focus)
			if image is None:
				raise ToolError("Only a focused button with an icon can be named this way. For other items, make an app helper.")
			from . import labels
			plugin.labels.setUser(_safe(lambda: focus.appModule.appName), labels.imageKey(image), name.strip())
		onMain(work)
		return f"The focused button is now called {name}."

	add("name_control", "give the focused button, which has no useful name, a name that NVDA will say from now on",
		nameControl, {"name": text("the new name, 1 to 4 words", maxLength=40)}, changes=True,
		title="Naming the button")

	# Settings.
	def findSetting(task, words):
		found = onMain(_findSettings, words)
		if not found:
			raise ToolError("No setting matches those words. Try other words, like speech rate, punctuation or typing echo.")
		return "\n".join(found)

	add("find_setting", "find NVDA settings by describing them; gives each setting's id, value now and allowed values",
		findSetting, {"words": text("2 to 4 keywords for the setting, like: speech rate", maxLength=80, auto=True)},
		looks=True, title="Finding the setting")

	def setSetting(task, setting, value):
		def work():
			found = _resolveSetting(setting)
			if found is None:
				raise ToolError(f"There is no setting with the id {setting}. Copy an id exactly from find_setting.")
			new = found.parse(value)
			old = found.shown()
			if found.id == "speech.volume":
				verdict, why = drivers.judgeVolume(new, _driverState()[drivers.DISPLAY][0])
				if verdict == drivers.REFUSE:
					raise Refused(why)
				if verdict == drivers.WARN:
					return found, new, old, f"{why} " + _("Change {setting} from {old} to {new}?").format(
						setting=found.label, old=old, new=found.shown(new)), True
			# Translators: Asked before VisionClaw changes an NVDA setting.
			return found, new, old, _("Change {setting} from {old} to {new}?").format(
				setting=found.label, old=old, new=found.shown(new)), False
		found, new, old, question, risky = onMain(work)
		mustAgree(question) if risky else confirm(question)
		onMain(found.write, new)
		return f"{found.label.capitalize()} was {old} and is now {onMain(found.shown)}."

	add("set_setting", "change one NVDA setting", setSetting, {
		"setting": text("the id of the setting, copied from find_setting", maxLength=80),
		"value": text("the new value: on, off, a number, +10 or -10 to change a number, or one of the allowed values",
			maxLength=60),
	}, changes=True, before="find_setting", title="Changing the setting")

	# Commands.
	def findCommand(task, words):
		commands = onMain(_commands)
		task.commands = commands
		scored = sorted(((score(words, c.text + " " + match.label(c.id)), c) for c in commands), key=lambda x: -x[0])
		found = [c for s, c in scored[:MAX_FOUND] if s >= 0.34]
		if not found:
			raise ToolError("No NVDA command matches those words. Try other words, like title, time, battery or say all.")
		return "\n".join(
			f"{c.id}: {c.info.displayName}. Keys: {' or '.join(c.keys) if c.keys else 'no key assigned'}." for c in found)

	add("find_command", "find NVDA commands by describing what they do; gives each command's id and its keys",
		findCommand, {"words": text("2 to 4 keywords for what the command does, like: window title", maxLength=80,
			auto=True)}, looks=True, title="Finding the command")

	def runCommand(task, command):
		commands = getattr(task, "commands", None) or onMain(_commands)
		index = match.best(command, [c.id for c in commands], least=0.85)
		if index is None:
			raise ToolError(f"There is no command with the id {command}. Copy an id exactly from find_command.")
		chosen = commands[index]
		risk = _RISKY_COMMANDS.get(chosen.info.scriptName)
		if risk:
			# Translators: Asked before an NVDA command that can silence or close NVDA. {command} is the command.
			mustAgree(f"{risk} " + _("Run the command: {command}?").format(command=chosen.info.displayName))
		with _SpeechCapture() as heard:
			onMain(_runCommand, chosen)
			time.sleep(0.6)
		said = " ".join(heard.texts).strip()
		keys = f" Next time you can press {' or '.join(chosen.keys)} for this." if chosen.keys else ""
		done = f"NVDA said: {clip(said, 500)}" if said else f"Done: {chosen.info.displayName}"
		return f"{done.rstrip('.')}.{keys}"

	add("run_command", "run one NVDA command for the user", runCommand,
		{"command": text("the id of the command, copied from find_command", maxLength=60)},
		changes=True, before="find_command", title="Running the command")

	# Learning about NVDA.
	def searchHelp(task, words):
		found = plugin.knowledge.text(words, limit=3, chars=600)
		lessons = plugin.memory.search(words, limit=2)
		if lessons:
			found += "\n\nLearned earlier on this computer:\n" + "\n".join(f"- {t}" for t in lessons)
		if not found.strip():
			raise ToolError("Nothing was found for those words. Try other words.")
		return found

	add("search_help", "read NVDA's user guide and VisionClaw's notes on NVDA and its add-on system", searchHelp,
		{"words": text("2 to 4 keywords for what you need to know", maxLength=80, auto=True)}, looks=True,
		title="Reading up on it")

	add("inspect_nvda", "look inside NVDA's code: what a module, class or function is and how to call it",
		lambda task, name: _inspect(name),
		{"name": text("a dotted name like api.getFocusObject or controlTypes.Role", maxLength=80)}, looks=True,
		title="Looking inside NVDA")

	def remember(task, note):
		plugin.memory.add(note, topic=task.request[:120])
		return "Remembered for next time."

	add("remember", "keep a short note about what worked, for similar requests later", remember,
		{"note": text("one sentence worth remembering", maxLength=300)}, title="Remembering", tell=VERBATIM)

	def askUserTool(task, question):
		answer = plugin.clawAskText(question)
		task.check()
		return f"The user answered: {answer}" if answer else "The user gave no answer."

	add("ask_user", "ask the user a question when something needed is not known", askUserTool,
		{"question": text("the question, in plain words", maxLength=200)}, looks=True, title="Asking you")

	# App helpers and add-ons.
	def createHelper(task, key, action, item):
		result = getattr(task, "items", None) or screen.items()
		index = match.itemIndex(item, Screen.names(result))
		if index is None:
			raise ToolError(f"There is no item called \"{item}\" in the window. Use a name from list_items.")
		name = Screen.names(result)[index]
		app = onMain(screen.where)[0]
		keyId = onMain(plugin.helpers.keyId, key)
		if keyId is None:
			raise ToolError(f"\"{key}\" is not a key. Use something like NVDA+alt+1 or NVDA+shift+p.")
		# Translators: Asked before VisionClaw saves a hotkey for a program.
		confirm(_("In {app}, make {key} {action} \"{item}\"?").format(app=app, key=key, action=action, item=name))
		plugin.helpers.add(app, key, keyId, action, name)
		return f"In {app}, pressing {key} now does this: {action} \"{name}\"."

	add("create_helper",
		"give the program in front its own hotkey that clicks an item or reads the text at an item, found by name each time",
		createHelper, {
			"key": text("the hotkey, like NVDA+alt+1", maxLength=30),
			"action": text("click presses the item; read speaks the item and the text after it", enum=["click", "read"]),
			"item": text("the name of the item, from list_items", maxLength=80),
		}, changes=True, before="list_items", title="Making the hotkey")

	def createAddon(task, name, purpose):
		params = task.params
		llm = LLM(plugin.runtime, task)
		facts = onMain(screen.situation) + "\n" + onMain(screen.controlFacts)
		if _ABOUT_SCREEN.search(purpose):
			# The two models work together: the vision model says what is there, the coder writes the fix for it.
			try:
				seen = look(task, "window", "Which buttons, labels and controls does this window show? Name them briefly.")
				facts += "\nWhat the vision model sees in the window: " + clip(seen, 500)
			except (ToolError, EngineError):
				pass
		notes = plugin.knowledge.text(purpose, limit=3, chars=700, sources=("addon-development", "objects-and-events"))
		lessons = plugin.memory.search("NVDA add-on code mistake " + purpose, limit=3)
		if lessons:
			notes += "\nMistakes made before on this computer:\n" + "\n".join(f"- {t}" for t in lessons)
		source = microaddons.write(llm, task, purpose, facts, notes, params, CODER, VISION)
		keys = microaddons.gestures(source)
		keyText = " Keys: " + "; ".join(f"{k} ({d})" if d else k for k, d in keys) + "." if keys else ""
		# What the code really does, found by checking it, in plain words: nobody has to read code.
		checked = " ".join(microaddons.describe(source))
		# Translators: Asked before a newly written add-on is turned on. {facts} are plain sentences about it.
		question = _(
			"VisionClaw wrote an add-on called {name}. You asked for: {purpose}. "
			"Checking the code shows: {facts} Turn it on?"
		).format(name=name, purpose=purpose.rstrip("."), facts=checked)
		if getattr(task, "codeDoubt", ""):
			# Translators: Added to the question when the reviewing model is not sure about the code.
			question = _("The reviewing model has a doubt about it: {doubt} ").format(doubt=task.codeDoubt) + question
		# Translators: Choices when a newly written add-on is ready.
		choices = [_("Turn it on"), _("Do not use it"), _("Show me the code first")]
		choice = plugin.clawAsk(question, choices)
		if choice == 2:
			wx.CallAfter(ui.browseableMessage, source, name)
			choice = plugin.clawAsk(_("Turn the add-on {name} on?").format(name=name), choices[:2])
		if choice != 0:
			raise UserSaidNo()
		for attempt in range(params.codeRepairs + 1):
			task.check()
			plugin.helpers.store.save(name, source, purpose)
			try:
				onMain(plugin.helpers.loadAddon, name)
				return f"The add-on {microaddons.slug(name)} is on.{keyText}"
			except Exception as e:
				error = f"{type(e).__name__}: {e}"
				task.emit("detail", f"The add-on did not start: {error}")
				plugin.helpers.store.remove(name)
				if attempt == params.codeRepairs:
					break
				source = microaddons.repair(llm, CODER, purpose, source, [f"NVDA could not start it: {error}"], params)
				problems = microaddons.check(source)
				if problems:
					source = microaddons.repair(llm, CODER, purpose, source, problems, params)
				if microaddons.check(source):
					break
		raise ToolError("The add-on could not be made to start. Try describing what it should do in a simpler way.")

	add("create_addon",
		"have the coder model write a small NVDA add-on, for new behaviour that no other tool can give", createAddon, {
			"name": text("a short name for the add-on, 1 to 3 words", maxLength=40),
			"purpose": text("exactly what the add-on must do, when, in which program, and with which key", maxLength=500,
				auto=True),
		}, changes=True, title="Writing the add-on")

	add("list_helpers", "list the app helpers and add-ons VisionClaw has made on this computer",
		lambda task: plugin.helpers.listText() or "VisionClaw has not made any helpers or add-ons yet.", looks=True,
		title="Listing what VisionClaw made", tell=VERBATIM)

	def removeHelper(task, name):
		# Translators: Asked before VisionClaw removes a helper or add-on it made.
		confirm(_("Remove {name}?").format(name=name))
		if not onMain(plugin.helpers.remove, name):
			raise ToolError(f"Nothing called \"{name}\" was found. Use a name or key from list_helpers.")
		return f"Removed {name}."

	add("remove_helper", "remove an app helper hotkey or an add-on that VisionClaw made", removeHelper,
		{"name": text("the add-on's name or the helper's key, from list_helpers", maxLength=60)},
		changes=True, before="list_helpers", title="Removing it")

	add("repair_addon",
		"have the models debug and correct an add-on VisionClaw wrote that fails or does the wrong thing",
		lambda task, name, problem: fixAddon(plugin, task, name, problem), {
			"name": text("the add-on's name, from list_helpers", maxLength=60),
			"problem": text("what the add-on does wrong, or should do instead", maxLength=400, auto=True),
		}, before="list_helpers", title="Debugging the add-on", tell=VERBATIM)

	def exportAddon(task, name):
		names = [meta["name"] for meta in plugin.helpers.store.list()]
		index = match.best(name, names)
		if index is None:
			raise ToolError(f"There is no add-on called \"{name}\". Use a name from list_helpers.")
		folder = os.path.join(os.path.expanduser("~"), "Documents", "VisionClaw add-ons")
		path = plugin.helpers.export(names[index], folder)
		return (
			f"Saved the add-on {names[index]} as the file {path}. Open that file to install it in NVDA for good, or "
			"share it. After installing it, remove it from VisionClaw so that it does not run twice."
		)

	add("export_addon", "save an add-on VisionClaw wrote as an .nvda-addon file, to install for good or to share",
		exportAddon, {"name": text("the add-on's name, from list_helpers", maxLength=60)},
		before="list_helpers", title="Saving the add-on as a file", tell=VERBATIM)

	# What NVDA has and uses.
	add("nvda_info",
		"report what NVDA has and uses: the speech synthesizer, its voices and settings, the braille display and "
		"tables, the installed drivers, the add-ons, NVDA's version",
		lambda task, topic: "\n".join(
			[onMain(nvdainfo.about, topic)]
			+ (plugin.driverNotes.problems(drivers.SYNTH) if topic == nvdainfo.SPEECH else [])
			+ (plugin.driverNotes.problems(drivers.DISPLAY) if topic == nvdainfo.BRAILLE else [])),
		{"topic": text("what to report on", enum=nvdainfo.TOPICS, auto=nvdainfo.topicOf)},
		looks=True, title="Asking NVDA")

	def switchDriver(task, kind, name):
		state = onMain(_driverState)
		installed = state["installed"][kind]
		if not installed:
			raise ToolError(f"NVDA did not say which {kind} drivers are installed.")
		index = match.best(name, [shown for _name, shown in installed])
		if index is None:
			index = match.best(name, [driver for driver, _shown in installed], least=0.8)
		if index is None:
			raise ToolError(
				f"There is no {kind} called \"{name}\". Installed: {', '.join(shown for _n, shown in installed[:20])}.")
		target, targetShown = installed[index]
		current, currentShown = state[kind]
		if target == current:
			return f"{targetShown} is already the {kind} in use."
		verdict, why = drivers.judge(
			kind, target, state[drivers.SYNTH][0], state[drivers.DISPLAY][0], plugin.driverNotes, targetShown)
		if verdict == drivers.REFUSE:
			raise Refused(why)
		# Translators: Asked before the speech synthesizer or braille display is switched.
		mustAgree((f"{why} " if why else "") + _(
			"Switch the {kind} from {old} to {new}? If {new} does not work, do nothing: "
			"VisionClaw switches back to {old} after {seconds} seconds."
		).format(kind=kind, old=currentShown, new=targetShown, seconds=KEEP_SECONDS))
		if not onMain(_setDriver, kind, target, timeout=60):
			onMain(_setDriver, kind, current, timeout=60)
			plugin.driverNotes.record(kind, target, drivers.FAILED)
			plugin.memory.add(f"On this computer the {kind} {targetShown} could not be started.", topic=kind)
			return f"{targetShown} could not be started, so {currentShown} is still the {kind} in use."
		# Translators: Asked right after switching. Not answering switches back.
		kept = plugin.clawKeep(_(
			"This is {new}. Does it work? Choose Keep it within {seconds} seconds, or VisionClaw switches back to {old}."
		).format(new=targetShown, old=currentShown, seconds=KEEP_SECONDS), KEEP_SECONDS)
		if not kept:
			onMain(_setDriver, kind, current, timeout=60)
			plugin.driverNotes.record(kind, target, drivers.REVERTED)
			plugin.memory.add(
				f"On this computer the {kind} {targetShown} was switched back because it was not confirmed to work.",
				topic=kind)
			return f"Switched back to {currentShown}, because {targetShown} was not confirmed to work."
		plugin.driverNotes.record(kind, target, drivers.WORKED)
		return f"The {kind} is now {targetShown}. Before, it was {currentShown}."

	add("switch_driver",
		"switch NVDA to another speech synthesizer or braille display; refuses a switch that would leave the user "
		"with neither speech nor braille, and switches back if the new one is not confirmed to work",
		switchDriver, {
			"kind": text("which kind of driver", enum=drivers.KINDS, auto=drivers.kindOf),
			"name": text("the name of the synthesizer or braille display to switch to, from nvda_info", maxLength=80),
		}, changes=True, before="nvda_info", title="Switching the driver")

	# The web, through the user's own browser and NVDA's browse mode.
	def pageNow():
		document = webtools.page()
		return (webtools.address(document), webtools.title(document)) if document is not None else None

	def openPage(task, url):
		before = onMain(pageNow)
		onMain(webtools.openAddress, url)
		time.sleep(WEB_SETTLE_SECONDS)
		deadline = time.monotonic() + WEB_WAIT_SECONDS
		while time.monotonic() < deadline:
			task.check()
			now = onMain(pageNow)
			if now is not None and now[1] and (before is None or now[0] != before[0]):
				return now[1]
			time.sleep(0.5)
		now = onMain(pageNow)
		return now[1] if now is not None else ""

	def webOpen(task, address):
		pageTitle = openPage(task, web.normalizeAddress(address))
		if not pageTitle:
			return "The address was given to the browser, but the page was not ready in time."
		return f"Opened the web page {pageTitle}."

	add("web_open", "open a web address in the user's browser", webOpen,
		{"address": text("the web address, like example.com", maxLength=300, auto=web.addressIn)},
		title="Opening the web page", tell=VERBATIM)

	def webSearch(task, words):
		words = " ".join(str(words).split())
		if not words:
			raise ToolError("Say what to search for.")
		pageTitle = openPage(task, web.searchUrl(config.conf["visionClaw"]["searchEngine"], words))
		if not pageTitle:
			raise ToolError("The search page was not ready in time. Try again.")
		return f"Searched the web for {words}."

	add("web_search", "search the web for something, in the user's browser", webSearch,
		{"words": text("what to search for, as a few words", maxLength=200, auto=web.searchWords)},
		title="Searching the web", tell=VERBATIM)

	def readPage(task, about):
		found = onMain(webtools.pageText)
		if found is None:
			raise ToolError("The user is not in a web page. Open one first; for other windows use look or read_text.")
		pageTitle, pageBody = found
		body = web.passages(pageBody, about)
		if not body:
			return f"The web page {pageTitle} has no text."
		return f"From the web page {pageTitle or 'without a title'}:\n{body}"

	add("read_page", "read the web page the user is in: the parts of its text that matter for the question", readPage,
		{"about": text("the question, or what to look for on the page", maxLength=200, auto=True)},
		looks=True, title="Reading the web page")

	def pageOutline(task):
		found = onMain(webtools.headings)
		if found is None:
			raise ToolError("The user is not in a web page. Open one first.")
		items = onMain(webtools.pageItems)
		kinds = [item["kind"] for item in items.items] if items is not None else []
		fields = sum(kind not in ("link", "button", "heading") for kind in kinds)
		lines = [
			f"The web page {items.title if items is not None else ''} has {len(found)} headings, "
			f"{kinds.count('link')} links, {kinds.count('button')} buttons and {fields} form fields."
		]
		lines += [f"Heading level {level}: {label}" if level else f"Heading: {label}" for level, label, _node in found[:35]]
		if len(found) > 35:
			lines.append(f"... and {len(found) - 35} more headings.")
		return "\n".join(lines)

	add("page_outline",
		"say how the web page is laid out: its headings in order, and how many links, buttons and fields it has",
		pageOutline, looks=True, title="Looking at how the page is laid out", tell=VERBATIM)

	def goToItem(task, item):
		result = getattr(task, "items", None)
		if result is None or not getattr(result, "web", False):
			raise ToolError("Use list_items first, in a web page.")
		index = pickItem(item, result.items, ("heading",))
		if index is None:
			raise ToolError(f"There is no item called \"{item}\" on the page. Use a number or a name from list_items.")
		found = result.items[index]
		onMain(webtools.moveTo, found)
		return f"NVDA is now at {found['text']}. Use NVDA's say all command to read on from there."

	add("go_to_item",
		"move NVDA's reading position to one item from list_items on the web page: a heading, a link or a field",
		goToItem, {"item": text("the number or the name of the item, from list_items", maxLength=80)},
		before="list_items", title="Moving there", tell=VERBATIM)

	def pageNavigate(task, direction):
		from keyboardHandler import KeyboardInputGesture
		before = onMain(pageNow)
		if before is None:
			raise ToolError("The user is not in a web page.")
		onMain(KeyboardInputGesture.fromName(_PAGE_KEYS[direction]).send)
		time.sleep(WEB_SETTLE_SECONDS)
		deadline = time.monotonic() + WEB_WAIT_SECONDS / 2
		now = onMain(pageNow)
		while direction != "reload" and time.monotonic() < deadline and (now is None or now[0] == before[0]):
			task.check()
			time.sleep(0.5)
			now = onMain(pageNow)
		if direction != "reload" and now is not None and now[0] == before[0]:
			return f"The browser did not go {direction}. It is still on {now[1] or 'the same page'}."
		return _PAGE_DONE[direction] + (f". The page is now {now[1]}." if now is not None and now[1] else ".")

	add("page_navigate", "go back or forward one page in the browser, or reload the page", pageNavigate,
		{"direction": text("which way", enum=list(_PAGE_KEYS), auto=directionOf)},
		title="Moving between pages", tell=VERBATIM)

	def fillField(task, field, typed, enter):
		import brailleInput
		from keyboardHandler import KeyboardInputGesture
		result = getattr(task, "items", None) or screen.items()
		if getattr(result, "web", False):
			index = webtools.fieldIndex(field, result.items)
		else:
			index = match.itemIndex(field, Screen.names(result))
		if index is None:
			raise ToolError(f"There is no field called \"{field}\". Use a number or a name from list_items.")
		found = result.items[index]
		# Translators: Asked before VisionClaw types into a field. {text} is the text, {field} the field.
		confirm(_("Type \"{text}\" into {field}?").format(text=clip(typed, 80), field=found["text"]))
		onMain(Screen.click, result, found)  # in a web page this goes into the field, as Enter does
		time.sleep(0.5)
		onMain(brailleInput.handler.sendChars, typed)
		if enter == "yes":
			time.sleep(0.2)
			onMain(KeyboardInputGesture.fromName("enter").send)
			time.sleep(CLICK_SETTLE_SECONDS)
		task.items = None
		return f"Typed \"{clip(typed, 80)}\" into {found['text']}" + (" and pressed Enter." if enter == "yes" else ".")

	registry.add(Tool(
		"fill_field", "type text into one field from list_items, such as a search box or a field of a form",
		guarded(lambda task, field, text, enter: fillField(task, field, text, enter)), {
			"field": text("the number or the name of the field, from list_items", maxLength=80),
			"text": text("the text to type into it", maxLength=400),
			"enter": text("yes to press Enter afterwards, to search or send", enum=["yes", "no"],
				auto=lambda part: "yes" if _SUBMITS.search(part) else "no"),
		}, changes=True, before="list_items", title="Typing into the field"))

	registry.add(Tool(ANSWER, "tell the user the result in plain words; always the last step", lambda task: ""))
	return registry
