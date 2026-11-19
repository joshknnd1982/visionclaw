# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools the models can use inside NVDA. Each tool is a small form and a function.
# The functions run on the task's worker thread; everything that touches NVDA is passed to NVDA's main thread.

import ctypes
import difflib
import html
import importlib
import inspect
import os
import re
import sys
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
from .vclog import log

from . import computertools, mousetools, net, nvdainfo, ocr, profiletools, webtools
from .claw import changes, commands, computer, debuglog, drivers, fixes, gamepad, guides, helpfiles, inside, lookup, match, microaddons, offers, pointer, policy, profiles, prompts, training, web
from .claw import guide, planning
from .claw.catalog import CODER, VISION
from .claw.llm import LLM, clip
from .claw.memory import score, wordList, words as wordsOf
from .claw.knowledge import Knowledge
from .claw.tools import ANSWER, VERBATIM, Registry, Tool, ToolError
from .claw.skills import addonGuide, stepGuide
from .engine import EngineError, prepareImage

addonHandler.initTranslation()

MAX_ITEMS_SHOWN = 45
MAX_FOUND = 6
CLICK_SETTLE_SECONDS = 0.7
# Some commands speak a moment after they were run; what they say is waited for this long.
COMMAND_SETTLE_SECONDS = 0.6
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


class _MOUSEINPUT(ctypes.Structure):
	_fields_ = [
		("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
		("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t),
	]


class _KEYBDINPUT(ctypes.Structure):
	_fields_ = [
		("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
		("dwExtraInfo", ctypes.c_size_t),
	]


class _INPUTUNION(ctypes.Union):
	_fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
	_fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]


_INPUT_KEYBOARD, _KEYEVENTF_KEYUP, _KEYEVENTF_UNICODE = 1, 0x0002, 0x0004


def unicodeInputs(text):
	"""The key events that type a text as characters, whatever the keyboard layout: for each character a key
	down and a key up carrying the character itself."""
	units = text.replace("\r\n", "\r").replace("\n", "\r").encode("utf-16-le")
	events = []
	for i in range(0, len(units), 2):
		code = units[i] | (units[i + 1] << 8)
		for flags in (_KEYEVENTF_UNICODE, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
			event = _INPUT(type=_INPUT_KEYBOARD)
			event.u.ki = _KEYBDINPUT(wVk=0, wScan=code, dwFlags=flags, time=0, dwExtraInfo=0)
			events.append(event)
	return events


def typeUnicode(text):
	"""Type a text into the program in front, through Windows itself. This does not rely on any part of NVDA,
	which has moved its own typing function between versions."""
	events = unicodeInputs(text)
	if not events:
		return
	block = (_INPUT * len(events))(*events)
	sent = ctypes.windll.user32.SendInput(len(events), block, ctypes.sizeof(_INPUT))
	if sent != len(events):
		raise ToolError("Windows did not accept the typing. The program in front may not allow it.")


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


def mentioned(asked, items):
	"""The names of the items that the user's own words mention, in the order they are said.
	"Drag the New Game button onto the Quit button" mentions New Game, then Quit. Where two names overlap,
	the longer is meant. A name shared by several items is given once."""
	said = f" {match.plain(asked)} "
	spans = []
	for item in items:
		name = match.plain(item.get("plain") or item.get("name") or item["text"])
		if len(name) < 2:
			continue
		at = said.find(f" {name} ")
		if at >= 0 and (at, at + len(name), name) not in spans:
			spans.append((at, at + len(name), name))
	spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
	names, end = [], -1
	for start, stop, name in spans:
		if start >= end:
			names.append(name)
			end = stop
	return names


def helperAction(part):
	"""What a program's hotkey is to do with its item, from the user's own words: hover over it, hold it down,
	read it, or click it in one of the three ways."""
	action = pointer.actionOf(part)
	if action == pointer.CLICK and re.search(r"\b(reads?|says?|speaks?|tells?|announces?)\b", (part or "").lower()):
		return "read"
	return action


def meant(asked, items, reference):
	"""What to look an item up by: the one item the user's own words name, if they name exactly one; otherwise
	what the model wrote. A person's words are more reliable than a small model's copy of them."""
	names = mentioned(asked, items) if asked else []
	return names[0] if len(names) == 1 else reference


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
		# Where the setting is in NVDA's configuration, as its sections and its key; None where that is not known.
		self.path = None
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
	setting = _confSettingOf(path, spec)
	if setting is not None:
		setting.path = tuple(path)
	return setting


def _confSettingOf(path, spec):
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
	for setting in found:
		setting.path = (section, _safe(lambda: driver.name) or "", setting.id.split(".", 1)[1])
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


def settingWords(ident, label):
	"""The words a setting is known by: (those of its name, those people also use for it)."""
	return wordsOf(f"{label} {ident.replace('.', ' ')}"), wordsOf(_ALIASES.get(ident, ""))


def _findSettings(query):
	"""The settings a request is about, best first. A setting counts by how many of the request's words name
	it, not by what share of the request they are: a long sentence that says "pitch" once is about the pitch."""
	inOrder = wordList(query)
	asked = set(inOrder)
	scored = []
	for setting in allSettings():
		named, also = settingWords(setting.id, setting.label)
		matched = asked & (named | also)
		if matched:
			# Among equals, the setting named last wins: in "the voice pitch", the pitch is what is meant.
			last = max(i for i, word in enumerate(inOrder) if word in matched)
			scored.append((len(matched), len(asked & named), last, setting))
	scored.sort(key=lambda x: (-x[0], -x[1], -x[2]))
	return [
		f"{s.id}: {s.label}. Now: {s.shown()}. Allowed: {s.allowed()}." for _count, _named, _last, s in scored[:MAX_FOUND]
	]


def related(asked, ident, label):
	"""Whether a request says anything about a setting. Used to refuse changing a setting nobody asked about."""
	named, also = settingWords(ident, label)
	return bool(wordsOf(asked) & (named | also))


def _resolveSetting(ident):
	settings = allSettings()
	for setting in settings:
		if setting.id == ident:
			return setting
	index = match.best(str(ident).replace(".", " "), [s.id.replace(".", " ") for s in settings], least=0.85)
	if index is None:
		# A model sometimes copies the setting's name instead of its id: "speech: rate" for speech.rate.
		wanted = match.plain(str(ident))
		index = next((i for i, s in enumerate(settings) if match.plain(s.label) == wanted), None)
	return settings[index] if index is not None else None


# --- NVDA commands ---

class _Command:
	"""One NVDA command, as plain facts: its id, the script behind it and the class that has it, what NVDA
	says it does, its keys as shown to the user, and its keys as NVDA writes them."""

	def __init__(self, ident, scriptName, cls, description, category, keys, gestures, documented=True):
		self.id = ident
		self.scriptName = scriptName
		self.cls = cls
		self.description = " ".join(str(description or "").split())
		self.category = str(category or "")
		self.keys = keys
		self.gestures = gestures
		self.documented = documented

	@property
	def source(self):
		"""Where the command comes from, like globalCommands or an add-on's module."""
		return getattr(self.cls, "__module__", "") or ""

	def line(self):
		"""The command as shown to a model and to the user: its id, what it does, its keys."""
		what = self.description or f"A command without a description, in {self.source or 'NVDA'}"
		keys = " or ".join(self.keys) if self.keys else "no key assigned"
		return f"{self.id}: {clip(what, 220).rstrip('.')}. Keys: {keys}."


def _shownKeys(gestures, layout):
	"""The keyboard keys among a command's gestures: (as shown to the user, as NVDA writes them)."""
	shown, raw = [], []
	for gesture in gestures:
		if not (gesture.startswith("kb:") or gesture.startswith(f"kb({layout}):")):
			continue
		text = _safe(lambda g=gesture: inputCore.getDisplayTextForGestureIdentifier(g)[1])
		if text and text not in shown:
			shown.append(text)
			raw.append(gesture)
	return shown, raw


def _scriptObjects():
	"""The live objects that have commands where the user is now, in the order NVDA asks them."""
	import globalCommands
	import globalPluginHandler
	focus = api.getFocusObject()
	found = list(globalPluginHandler.runningPlugins)
	found += [_safe(lambda: focus.appModule), _safe(lambda: focus.treeInterceptor), focus]
	found += list(reversed(_safe(api.getFocusAncestors, []) or []))
	found = [obj for obj in found if obj is not None]
	# NVDA's own commands are always the last, whatever else is there.
	return found + [globalCommands.commands]


def _undocumented(known, layout):
	"""Commands that NVDA does not list anywhere, because they were given no description: every script of the
	objects in use that is not known yet. They can be found and run like the others."""
	found = []
	above = {id(ancestor) for ancestor in (_safe(api.getFocusAncestors, []) or [])}
	for obj in _scriptObjects():
		byScript = {}
		for gesture, script in (_safe(lambda o=obj: dict(o._gestureMap), {}) or {}).items():
			byScript.setdefault(getattr(script, "__func__", script), []).append(gesture)
		for cls in type(obj).__mro__:
			for name, script in list(vars(cls).items()):
				if not name.startswith("script_") or not callable(script) or name[7:] in known:
					continue
				if id(obj) in above and not getattr(script, "canPropagate", False):
					continue  # as in NVDA: what contains the focus only lends the commands made for that
				known.add(name[7:])
				keys, raw = _shownKeys(byScript.get(script, []), layout)
				found.append(_Command(
					name[7:], name[7:], cls, getattr(script, "__doc__", "") or "", "", keys, raw, documented=False))
	return found


def _commands():
	"""Every command NVDA has where the user is now, with its keys: those NVDA lists, then those it does not
	list because they have no description. Must be called on the main thread."""
	focus = api.getFocusObject()
	mappings = inputCore.manager.getAllGestureMappings(obj=focus, ancestors=api.getFocusAncestors())
	layout = _safe(lambda: config.conf["keyboard"]["keyboardLayout"], "desktop")
	found, used = [], {}
	for category, scripts in mappings.items():
		for _name, info in scripts.items():
			keys, raw = _shownKeys(info.gestures, layout)
			ident = info.scriptName
			used[ident] = used.get(ident, 0) + 1
			if used[ident] > 1:
				ident = f"{ident}{used[ident]}"
			found.append(_Command(ident, info.scriptName, info.cls, info.displayName, category, keys, raw))
	try:
		found += _undocumented(set(used), layout)
	except Exception:
		log.debugWarning("VisionClaw: the commands without a description could not be listed", exc_info=True)
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
	"""The live object a command belongs to: NVDA's own commands first, then the add-ons, the program, the
	page, the focused control, and what contains it."""
	objects = _scriptObjects()
	for candidate in objects[-1:] + objects[:-1]:
		if isinstance(candidate, cls):
			return candidate
	return None


_MODIFIER_KEYS = frozenset((
	"nvda", "control", "shift", "alt", "windows", "leftcontrol", "rightcontrol", "leftshift", "rightshift",
	"leftalt", "rightalt", "leftwindows", "rightwindows",
))


def keyGesture(identifier):
	"""A key press made from the way NVDA writes a key: kb:NVDA+control+downArrow, or kb(laptop):NVDA+shift+s.
	NVDA keeps the parts of a key in the order of the alphabet, so the keys that are held are put first again
	and the key that is pressed last. Raises LookupError or ValueError when NVDA does not know a key."""
	from keyboardHandler import KeyboardInputGesture
	parts = identifier.split(":", 1)[1].split("+")
	held = [part for part in parts if part.lower() in _MODIFIER_KEYS]
	pressed = [part for part in parts if part.lower() not in _MODIFIER_KEYS]
	return KeyboardInputGesture.fromName("+".join(held + pressed if pressed else parts))


def noKeyGesture(name, script):
	"""What stands in for a key press when a command is run that has no key, or whose key NVDA cannot make.
	NVDA asks every command's key press a few things before it runs the command; without one it fails."""
	base = getattr(inputCore, "InputGesture", object)

	class NoKeys(base):
		wasInSayAll = False
		isModifier = False
		bypassInputHelp = True
		reportInInputHelp = False

		def _get_identifiers(self):
			return ()

		def _get_normalizedIdentifiers(self):
			return ()

		def _get_displayName(self):
			return name

		def _get_script(self):
			return script

		def send(self):
			pass

	gesture = NoKeys()
	if "displayName" not in vars(NoKeys):
		# NVDA makes properties of the _get_ methods above. Where that did not happen, they are set by hand.
		gesture.identifiers, gesture.normalizedIdentifiers, gesture.displayName, gesture.script = (), (), name, script
	return gesture


def _commandParts(command):
	"""What is needed to run a command: (the script, the key press handed to it). The script is None for a
	command that is nothing but another key."""
	gesture = None
	for identifier in command.gestures:
		try:
			gesture = keyGesture(identifier)
			break
		except Exception:
			debuglog.detail("command", f"NVDA made no key press from {identifier} for {command.id}")
	if command.scriptName.startswith("kb:"):
		# A command that only presses another key: that key is pressed.
		try:
			return None, keyGesture(command.scriptName)
		except Exception:
			raise ToolError(f"The command {command.id} presses a key that NVDA does not know.")
	target = _commandTarget(command.cls)
	script = getattr(target, "script_" + command.scriptName, None) if target is not None else None
	if script is None:
		raise ToolError(f"The command {command.id} cannot be used where the user is now.")
	if gesture is None:
		gesture = noKeyGesture(command.description or command.id, script)
	return script, gesture


def _runCommand(command, wanted, heard):
	"""Run a command as if its key were pressed: once, or as often as wanted asks for, quickly, the way a
	person presses twice. wanted: the press counts whose result is wanted, lowest first. Returns the place in
	heard.texts from which what was said belongs to the answer. Must be called on the main thread."""
	script, gesture = _commandParts(command)
	debuglog.log("command", (
		f"Running {command.id} (script_{command.scriptName} of {command.source}), pressed {wanted[-1]} time(s), "
		f"wanted presses {wanted}, key press: {type(gesture).__name__} {_safe(lambda: gesture.displayName, '')!r}"))
	if script is None:
		gesture.send()
		return 0
	# So that the first press counts as a first press, whatever was pressed just before.
	clear = getattr(scriptHandler, "clearLastScript", None)
	if clear is not None:
		_safe(clear)
	first, start = wanted[0], 0
	for press in range(1, wanted[-1] + 1):
		if 1 < press <= first:
			# What the presses before said was not asked for: it is cut short, as when a person presses on.
			_safe(_cancelSpeech)
		if press == first:
			start = len(heard.texts)
		scriptHandler.executeScript(script, gesture)
		debuglog.detail("command", f"Press {press} of {command.id} done; NVDA has said so far: {heard.texts[start:]}")
	return start


def _cancelSpeech():
	import speech
	speech.cancelSpeech()


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
		app, title, fg, focus = self.where()
		role = _safe(lambda: focus.role.displayString) or ""
		name = _safe(lambda: focus.name) or "no name"
		# Where that is, in plain words, by plain code (claw/planning.py): the desktop, the taskbar, a dialog.
		where = planning.placeText(app, title, _safe(lambda: fg.windowClassName) or "")
		return f"Program: {app}. Window title: {title or 'none'}. Focused control: {role}, {name}." + (f" {where}" if where else "")

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
	def click(result, item, action=pointer.CLICK, spot=None, keys=()):
		"""Click, double-click, right-click or point at an item. In a window this is done with the mouse in the
		middle of the item, and the mouse is put back. A web page item is worked the way NVDA does it: activated,
		or moved to, and for a right-click its context menu is opened with the Applications key. Main thread.
		What only the real mouse does is done with it on a web page too: a click with the middle button, three
		clicks, a click at a place on the item (spot, shares of its width and height) and a click with keys held
		down. Returns False when that was wanted and the item's place on the screen is not known."""
		real = spot is not None or bool(keys) or action in (pointer.MIDDLE, pointer.TRIPLE)
		if real:
			point = Screen.pointOf(result, item, spot)
			if point is None:
				return False
			old = mousetools.position()
			with mousetools.keysDown(keys):
				mousetools.click(point[0], point[1], action)
			wx.CallLater(250, mousetools.moveTo, *old)
			return True
		if item.get("web") is not None:
			if action in (pointer.RIGHT, pointer.HOVER):
				webtools.moveTo(item)
				if action == pointer.RIGHT:
					from keyboardHandler import KeyboardInputGesture
					KeyboardInputGesture.fromName("applications").send()
			else:
				webtools.activate(item)
			return
		x, y = result.screenPoint(item)
		old = mousetools.position()
		mousetools.click(x, y, action)
		if action != pointer.HOVER:  # pointing at something means leaving the pointer there
			wx.CallLater(250, mousetools.moveTo, *old)

	@staticmethod
	def pointOf(result, item, spot=None):
		"""The middle of an item on the screen, for the mouse, or the place on it that spot gives as shares of
		its width and height; None when its place is not known. An item of a web page is brought into view
		first, and NVDA's reading position is put on it. Main thread."""
		if item.get("web") is None:
			box = item.get("box")
			if spot is None or not box:
				return result.screenPoint(item)
			info = result.imageInfo
			left, top = info.convertXToScreen(box[0]), info.convertYToScreen(box[1])
			right, bottom = info.convertXToScreen(box[2]), info.convertYToScreen(box[3])
		else:
			webtools.moveTo(item)
			obj = _safe(lambda: item["web"].obj)
			if obj is None:
				return None
			_safe(obj.scrollIntoView)
			loc = _safe(lambda: obj.location)
			if not loc or loc.width <= 0 or loc.height <= 0:
				return None
			left, top, right, bottom = loc.left, loc.top, loc.left + loc.width, loc.top + loc.height
		across, down = spot or (0.5, 0.5)
		return round(left + across * max(0, right - left - 1)), round(top + down * max(0, bottom - top - 1))


# --- Knowledge ---

def userGuideSections():
	"""NVDA's own user guide, as sections, so the models can read how NVDA works."""
	import documentationUtils
	path = documentationUtils.getDocFilePath("userGuide.html")
	if not path or not os.path.isfile(path):
		return []
	with open(path, encoding="utf-8", errors="replace") as f:
		page = f.read()
	# Each row of a table as a sentence, and no heading rows: see lookup.htmlSections.
	return [(title, body[:1500], "userGuide") for title, body in lookup.htmlSections(page)]


def _kindOf(thing):
	if inspect.ismodule(thing):
		return "a module"
	if inspect.isclass(thing):
		return "a class"
	if inspect.ismethod(thing):
		return "a method"
	if inspect.isroutine(thing):
		return "a function"
	return f"a value of the kind {type(thing).__name__}"


def _inspect(name):
	"""What a module, class, function or value of NVDA is: its kind, how it is called, its help text, what it
	has, and what it holds now. A function that only reports something and needs nothing (getFocusObject,
	isRunning) is called, so that what it gives back now can be said; nothing else is ever called.
	Must be called on the main thread."""
	parts = [p for p in re.split(r"[.\s]+", str(name).replace("()", "").strip()) if p]
	if not parts or not all(p.isidentifier() for p in parts):
		raise ToolError("Give a dotted name like api.getFocusObject or controlTypes.Role.")
	if parts[0] in microaddons.FORBIDDEN_MODULES:
		raise ToolError(f"{parts[0]} is not an NVDA module that add-ons may use.")
	found, rest = None, []
	for cut in range(len(parts), 0, -1):
		module = sys.modules.get(".".join(parts[:cut]))
		if module is None:
			try:
				module = importlib.import_module(".".join(parts[:cut]))
			except Exception:
				continue
		found, rest, path = module, parts[cut:], ".".join(parts[:cut])
		break
	if found is None:
		raise ToolError(f"NVDA has no module called {parts[0]}.")
	for attr in rest:
		if not hasattr(found, attr) and inside.reports(path.split(".")[-1], found):
			# "api.getFocusObject.name": what the function gives back now is looked into.
			found, path = found(), path + "()"
		if not hasattr(found, attr):
			raise ToolError(f"{path} has nothing called {attr}. It has: {_members(found)}")
		found, path = getattr(found, attr), f"{path}.{attr}"
	lines = [f"{path} is {_kindOf(found)}."]
	if callable(found):
		signature = inside.signature(found)
		if signature:
			lines.append(f"Call it as {path.split('.')[-1]}{signature}.")
	doc = inspect.getdoc(found) if (callable(found) or inspect.ismodule(found)) else None
	if doc:
		lines.append(clip(doc, 500))
	if inspect.ismodule(found) or inspect.isclass(found):
		lines.append("It has: " + _members(found))
	elif inside.reports(path.split(".")[-1], found):
		try:
			lines.append(f"Called now, it gives back: {inside.describe(found())}.")
		except Exception as e:
			lines.append(f"Calling it now did not work: {type(e).__name__}: {clip(str(e), 160)}.")
	elif not callable(found):
		lines.append(f"Now it holds: {inside.describe(found)}.")
	return "\n".join(lines)


_insideCache = {"count": -1, "entries": []}


def insideIndex():
	"""The list of everything inside the running NVDA and its add-ons. Made when first asked for, and again
	when modules were loaded since, as when an add-on or a program's module arrived."""
	loaded = dict(sys.modules)
	if _insideCache["count"] != len(loaded):
		started = time.monotonic()
		_insideCache["entries"] = inside.index(loaded)
		_insideCache["count"] = len(loaded)
		debuglog.log("inside", (
			f"Listed {len(_insideCache['entries'])} things in {len(loaded)} loaded modules "
			f"in {time.monotonic() - started:.1f} seconds"))
	return _insideCache["entries"]


# --- What NVDA knows about one object ---

FOCUS, NAVIGATOR, WINDOW, MOUSE, DESKTOP, PARENT = "focus", "navigator", "window", "mouse", "desktop", "parent"
OBJECTS = [FOCUS, NAVIGATOR, WINDOW, MOUSE, DESKTOP, PARENT]
_OBJECT_NAMES = {
	FOCUS: "The focused control", NAVIGATOR: "The navigator object", WINDOW: "The window in front",
	MOUSE: "What is under the mouse pointer", DESKTOP: "The desktop", PARENT: "What the focused control is inside of",
}
# Words of a request about an object that name no fact about it.
_OBJECT_WORDS = wordsOf(
	"everything all tell about control object focus focused navigator window this that info information fact facts "
	"detail details property properties nvda know knows have has what give show say report mouse pointer desktop "
	"parent current under item element button thing")


def objectOf(part):
	"""Which object a request is about, from its words."""
	said = (part or "").lower()
	if re.search(r"\bnavigator\b|\breview (cursor|position)\b", said):
		return NAVIGATOR
	if re.search(r"\b(mouse|pointer)\b", said):
		return MOUSE
	if re.search(r"\bdesktop\b", said):
		return DESKTOP
	if re.search(r"\b(parent|container|inside of|contains (it|this))\b", said):
		return PARENT
	if re.search(r"\b(window|foreground|dialog)\b", said) and not re.search(r"\bwindow (class|handle|control id)\b", said):
		return WINDOW
	return FOCUS


def _theObject(which):
	if which == NAVIGATOR:
		return api.getNavigatorObject()
	if which == WINDOW:
		return api.getForegroundObject()
	if which == MOUSE:
		return api.getMouseObject()
	if which == DESKTOP:
		return api.getDesktopObject()
	focus = api.getFocusObject()
	return _safe(lambda: focus.parent) if which == PARENT else focus


def objectFacts(obj):
	"""Everything NVDA knows about one object, as (what it is called, other words people use for it, the
	fact). Must be called on the main thread; never raises."""
	from . import deepquery
	known = deepquery.facts(obj)
	found = []

	def fact(label, also, value):
		value = " ".join(str(value or "").split())
		if value:
			found.append((label, also, value))

	fact("Name", "called label", known["name"] or "it has no name")
	fact("Kind", "role type", f"{known['roleText']} (controlTypes.Role.{known['role']})")
	fact("Value", "content shows", known["value"])
	fact("Description", "help", known["description"])
	fact("States", "state checked selected pressed expanded unavailable", ", ".join(
		state.lower().replace("_", " ") for state in known["states"]))
	fact("Keyboard shortcut", "key accelerator hotkey", known["shortcut"])
	box = known["box"]
	if box:
		fact("Position and size", "where location place coordinates big wide high width height pixels", (
			f"left {box[0]}, top {box[1]}, {box[2] - box[0]} wide, {box[3] - box[1]} high, in pixels"))
	place = _safe(lambda: obj.positionInfo) or {}
	if place.get("indexInGroup"):
		fact("Place among its neighbours", "index group level position number", (
			f"{place['indexInGroup']} of {place.get('similarItemsInGroup', 'an unknown number')}"
			+ (f", level {place['level']}" if place.get("level") else "")))
	fact("Program", "app application process", (
		f"{known['app']}, process id {_safe(lambda: obj.processID, 'unknown')}"))
	fact("Window class", "classname", known["windowClass"])
	fact("Window control id", "identifier", known["controlId"] or "")
	fact("Window handle", "hwnd", _safe(lambda: obj.windowHandle) or "")
	fact("Accessibility interface", "api automation uia iaccessible msaa", known["api"])
	fact("UI Automation id", "automationid identifier", _safe(lambda: obj.UIAAutomationId) or "")
	fact("UI Automation class", "classname", _safe(lambda: obj.UIAElement.cachedClassName) or "")
	fact("Toolkit", "framework", known.get("framework", ""))
	fact("What it can do through UI Automation", "patterns do", ", ".join(known.get("patterns", [])))
	fact("Actions", "do action press activate", ", ".join(known["actions"]))
	fact("On a web page it is", "web html tag attributes", ", ".join(f"{k} {v}" for k, v in known.get("web", {}).items()))
	fact("Text drawn in it", "drawn text shown", known.get("drawn", ""))
	children = []
	child = _safe(lambda: obj.firstChild)
	while child is not None and len(children) < 5:
		children.append(inside.describe(child, 60).replace("an object NVDA reads: ", "").split(" (")[0])
		child = _safe(lambda c=child: c.next)
	if known["children"]:
		fact("Children", "child contains inside items", (
			f"{known['children']}" + (f": {'; '.join(children)}" if children else "")
			+ (" and more" if known["children"] > len(children) and children else "")))
	parent = _safe(lambda: obj.parent)
	if parent is not None:
		fact("It is inside", "parent container", inside.describe(parent, 60).replace("an object NVDA reads: ", "").split(" (")[0])
	classes = [f"{cls.__module__}.{cls.__qualname__}" for cls in type(obj).__mro__[:4] if cls is not object]
	if classes:
		fact("NVDA's class for it", "python class code", classes[0] + (
			", built on " + ", ".join(classes[1:]) if classes[1:] else ""))
	fact("Everything else it has", "attributes members list", inside.publicNames(obj, 45))
	return found


def objectAnswer(obj, which, asked):
	"""What is said about an object: every fact, or, when the request names some, only those. A property the
	request names that is not among the facts is read from the object itself. Main thread."""
	facts = objectFacts(obj)
	said = wordsOf(asked) - _OBJECT_WORDS
	low = (asked or "").lower()
	# A fact that is asked for by its full name is the one that is meant: "window class" is not the Python class.
	chosen = [(label, value) for label, _also, value in facts if label.lower() in low]
	if not chosen and said:
		chosen = [(label, value) for label, also, value in facts if said & (wordsOf(label) | wordsOf(also))]
	# Anything else the object has can be asked for by its name, known to VisionClaw or not.
	labels = {label.lower() for label, _also, _value in facts}
	for name in dir(obj):
		shown = name[5:] if name.startswith("_get_") else name
		if shown.startswith("_") or len(shown) < 4 or match.label(shown) in labels:
			continue
		if re.search(rf"(?<![a-z0-9]){re.escape(shown.lower())}(?![a-z0-9])", low) or (
				len(shown) > 5 and re.search(rf"(?<![a-z0-9]){re.escape(match.label(shown))}(?![a-z0-9])", low)):
			try:
				value = getattr(obj, shown)
			except Exception as e:
				value = f"could not be read ({type(e).__name__})"
			line = (shown, value if isinstance(value, str) and value.startswith("could not") else inside.describe(value, 200))
			if line not in chosen and not callable(value):
				chosen.append(line)
	lines = chosen or [(label, value) for label, _also, value in facts]
	return f"{_OBJECT_NAMES[which]}. " + " ".join(f"{label}: {value.rstrip('.')}." for label, value in lines)


def failingLine(trace):
	"""Where in the add-on's own code an error happened, from NVDA's traceback."""
	found = re.findall(r'File "[^"]*plugin\.py", line (\d+), in (\w+)\n\s*(.+)', trace or "")
	if not found:
		return ""
	number, function, code = found[-1]
	return f"The failing line is line {number}, in {function}: {code.strip()}"


def nvdaHas(name):
	"""Whether the running NVDA has a dotted name, like api.getFocusObject: True, False, or None when that
	cannot be told. Looking never changes anything: only modules that are loaded already are asked, nothing is
	imported and nothing is called. A part of a package that is not loaded yet cannot be told."""
	parts = str(name or "").split(".")
	thing = sys.modules.get(parts[0])
	if thing is None or not inspect.ismodule(thing):
		return None
	for part in parts[1:]:
		if not (inspect.ismodule(thing) or inspect.isclass(thing)):
			# What an object has is not asked: reading it could run code.
			return None
		try:
			known = part in vars(thing) or (inspect.isclass(thing) and any(part in vars(base) for base in thing.__mro__))
		except Exception:
			return None
		if not known:
			loaded = sys.modules.get(f"{thing.__name__}.{part}") if inspect.ismodule(thing) else None
			if loaded is not None:
				thing = loaded
				continue
			# A package has parts that are loaded only when they are needed, and a module can make a name when
			# it is asked for one.
			return None if hasattr(thing, "__path__") or hasattr(thing, "__getattr__") else False
		thing = vars(thing).get(part) if part in vars(thing) else getattr(thing, part, None)
	return True


def guideLines(plugin, purpose, known=""):
	"""For the model that writes or repairs an add-on: the few single lines of the downloaded developer guides
	that fit what the add-on is for (claw/guides.py), without those whose names this NVDA no longer has, and
	without those about a name the model is told anyway (known: VisionClaw's own notes for this request; its
	instructions are added here); "" when no guides are on the computer or none is left. Never raises: the
	guides only help."""
	kept = getattr(plugin, "devGuides", None)
	if kept is None:
		return ""
	try:
		text = kept.forCoder(purpose, exists=nvdaHas, known=f"{microaddons._SYSTEM}\n{known}")
	except Exception as e:
		debuglog.error("guides", "The developer guides could not be read for the add-on", e)
		return ""
	if text:
		debuglog.log("guides", f"Given to the add-on writer from the developer guides: {text!r}")
	return text


def coderNotes(plugin, task, purpose, notes):
	"""All that the model that writes or repairs an add-on is given to read, in the order in which it counts,
	because it is cut off at its end: what a chosen skill says, what the user asked VisionClaw to remember with
	their library, the lines of the developer guides that fit, and then VisionClaw's own notes. Each is chosen
	by plain code from what the add-on is for, and left out when nothing fits."""
	from . import memorytools
	parts = [
		# When VisionClaw corrects an add-on by itself there is no request, so the skills are chosen by what the
		# add-on is for.
		stepGuide(task) or addonGuide(getattr(plugin, "skills", None), purpose),
		memorytools.forCoder(plugin, purpose).strip(),
		guideLines(plugin, purpose, notes),
		notes,
	]
	return "\n".join(part for part in parts if part)


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
	if fixes.isFixes(source):
		# Accessibility fixes are put together from fixed parts and plain data. A model must never rewrite them.
		raise ToolError(
			f"The add-on {ident} holds accessibility fixes that VisionClaw put together from tested parts, so it "
			"has no code for the models to correct. Say which of its fixes is wrong and what it should do "
			"instead, or have the add-on removed.")
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
	# What a skill says, what the user asked VisionClaw to remember, their library, the notes on accessibility
	# interfaces and the lines of the developer guides that belong with the add-on come before the notes.
	notes = coderNotes(plugin, task, purpose, notes)
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

	def guarded(fn, pointing=False):
		"""A tool function where the user saying no ends the step quietly instead of as an error.
		pointing: the tool puts the mouse on a place; while it works, the mouse is moved the way the program in
		front is known to need, as for a game that reads the mouse directly."""
		def run(task, **form):
			try:
				if pointing:
					with mousetools.directScope(plugin):
						return fn(task, **form)
				return fn(task, **form)
			except UserSaidNo:
				return "You said no, so nothing was changed."
			except Refused as e:
				return f"VisionClaw did not do this. {e}"
			except ValueError as e:
				raise ToolError(str(e))
		return run

	def notOwn(fn):
		"""A tool that works the window in front, kept away from VisionClaw's own windows: their controls always
		belong to the user."""
		def run(task, **form):
			from . import guidetools
			if _safe(lambda: onMain(guidetools.ownWindow), False) is True:
				return guide.NOT_OWN
			return fn(task, **form)
		return run

	def add(name, description, fn, fields=None, **options):
		if name in guide.OFF_LIMITS:
			fn = notOwn(fn)
		registry.add(Tool(name, description, guarded(fn, name in mousetools.DIRECT_TOOLS), fields, **options))

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
		# What a chosen skill says about looking, such as how a photo or a chart is best described.
		guide = stepGuide(task)
		if guide:
			prompt += f"\n{guide}"
		seer = policy.roleName(VISION, policy.isOneModel(plugin.runtime))
		task.emit("talk", f"Asked the {seer}: {question}")
		answer = plugin.runtime.describe(prepareImage(image, config.conf["visionClaw"]["detailSize"]), prompt, 350,
			cancel=task.cancel, system=prompts.seeing())
		task.check()
		task.emit("talk", f"The {seer} answered: {clip(answer, 400)}")
		return answer or f"The {seer} gave no answer."

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

	def elsewhere(task, words, chosen=None):
		"""Where the thing the user named is not in the window in front: a part of Windows itself, or a program,
		folder or place of Windows that is opened by its name. Each is asked about, except a part of Windows the
		words are sure of. Returns the result, or None when nothing else fits."""
		from . import computertools
		part = computer.windowsPart(words) or computer.windowsPart(words, loose=True)
		if part is not None:
			if computer.windowsPart(words) is None:
				name = computer.windowsPartOf(part)[0]
				named = " ".join(match.telling(words)) or "that"
				# Translators: Asked when what the user named is not in the window in front, and is perhaps a part of Windows. {named} is what the user said, {part} the part of Windows.
				if plugin.clawAsk(_("Nothing in this window is called {named}. Open {part} of Windows instead?").format(
						named=named, part=name), [_("Yes, do it"), _("No, leave it")]) != 0:
					raise UserSaidNo()
			task.items = None
			return computertools.openWindowsPart(part, onMain, notInWindow=True)
		named = " ".join(match.telling(words))
		if len(named) < 3:
			return None
		found, sure = computer.find(named, computer.places())
		if not found:
			found, sure = computer.find(named, _safe(computertools.gather, []) or [])
		if not (sure or len(found) == 1):
			return None
		thing = found[0]
		# Translators: Asked when what the user named is not in the window in front, and a program or place of that name was found. {named} is what the user said, {name} and {kind} what was found.
		if plugin.clawAsk(_("Nothing in this window is called {named}. Open {name}, {kind}, instead?").format(
				named=named, name=thing["name"], kind=thing["kind"]), [_("Yes, do it"), _("No, leave it")]) != 0:
			raise UserSaidNo()
		try:
			computertools.shellOpen(thing["target"])
		except OSError as e:
			raise ToolError(f"{thing['name']} could not be opened. {e}")
		task.items = None
		return f"Nothing in the window in front was called {named}, so VisionClaw opened {thing['name']}, {thing['kind']}."

	def clickItem(task, item, action, asked):
		result = getattr(task, "items", None)
		if result is None or not result.items:
			raise ToolError("Use list_items first.")
		# The part of the request this step is for, in the user's own words; a model that left it empty is not
		# checked against the whole request, which may be about other things too.
		words = asked or ""
		reference = meant(asked, result.items, item)
		# A model that writes that the item is not there names no item, whatever its sentence shares with one.
		none = match.saysNone(reference)
		index = None if none else pickItem(reference, result.items, ("link", "button"))
		# What the user's own words name decides: an item that has none of its words is not taken for it.
		if index is None or not match.fits(words, result.items[index]["text"]):
			other = elsewhere(task, words)
			if other is not None:
				return other
			named = " ".join(match.telling(words))
			where = f"on the web page {result.title}" if getattr(result, "web", False) else "in the window in front"
			if index is None and (none or named):
				return (
					f"Nothing was clicked: nothing {where} is called {named or item}, and it is not a part of Windows "
					"or a program that VisionClaw can open by its name.")
			if index is None:
				raise ToolError(f"There is no item called \"{item}\". Use a number or a name from list_items.")
			# Translators: Asked when the item a model chose does not have the name the user said. {named} is what the user said, {item} the item that was chosen.
			if plugin.clawAsk(_("Nothing in this window is called {named}. The closest found is {item}. Use it anyway?").format(
					named=named, item=result.items[index]["text"]), [_("Yes, do it"), _("No, leave it")]) != 0:
				return f"Nothing was clicked: nothing {where} is called {named}, and you did not want {result.items[index]['text']}."
		found = result.items[index]
		if action not in pointer.ACTIONS:
			action = pointer.CLICK
		if action in (pointer.HOVER, pointer.HOLD):
			# Both need the real mouse on the item, also on a web page: a menu that opens when the pointer rests
			# on it, or a button that works only while it is held down, takes no notice of NVDA's own ways.
			point = onMain(Screen.pointOf, result, found)
			if point is None:
				if action == pointer.HOVER:
					return (
						f"NVDA's reading position is on {found['text']}. Where it is on the screen is not known, so the "
						"mouse pointer could not be rested on it.")
				raise ToolError(
					f"Where {found['text']} is on the screen is not known, so it could not be held down. Pointer mode "
					"lets the user put the mouse pointer on it: G holds the mouse button and G lets go.")
			# The window as it was listed; for a web page, the window in front.
			box = mousetools._windowBox(result) if found.get("web") is None else onMain(screen.box, "window")
			read = config.conf["visionClaw"]["useOcr"]
			if action == pointer.HOVER:
				# Pointing changes nothing, so nothing is asked; the pointer stays there.
				before, after = mousetools.rest(plugin._grab, box, point, task.cancel)
				task.check()
				return mousetools.restText(*mousetools.appearedText(before, after, read), found["text"])
			seconds = pointer.holdSeconds(asked or task.request)
			# Translators: Asked before VisionClaw presses the mouse button on something and keeps it down. {time} is how long.
			confirm(_("Press and hold {item} for {time}?").format(item=found["text"], time=pointer.secondsText(seconds)))
			old = mousetools.position()
			before = _safe(lambda: plugin._grab(box))
			try:
				mousetools.hold(point[0], point[1], seconds, task.cancel)
				time.sleep(CLICK_SETTLE_SECONDS)
				after = _safe(lambda: plugin._grab(box)) if before is not None else None
			finally:
				mousetools.moveTo(*old)
			task.check()
			task.items = None  # the window has probably changed
			said = f"Held the mouse button down on {found['text']} for {pointer.secondsText(seconds)}."
			if before is None or after is None:
				return said
			changed, shown = mousetools.appearedText(before, after, read)
			return said + (f" This appeared: {shown}" if shown else " What the window shows changed." if changed
				else " Nothing VisionClaw can see changed in the window.")
		# What only the user's own words can say: keys held down during the click, and where on the item it lands.
		words = asked or task.request
		keys = pointer.modifiersOf(words)
		spot = pointer.spotOf(words)
		what = found["text"]
		if spot is not None:
			what += f", {pointer.spotText(spot)}"
		if keys:
			what += " with " + " and ".join(key.capitalize() for key in keys) + " held down"
		# Following a link only goes to another page; everything else is asked about.
		if keys or spot is not None or not (found.get("kind") == "link" and action == pointer.CLICK):
			confirm({
				# Translators: Asked before VisionClaw clicks something. {item} is what will be clicked.
				pointer.CLICK: _("Click {item}?"),
				# Translators: Asked before VisionClaw double-clicks something.
				pointer.DOUBLE: _("Double-click {item}?"),
				# Translators: Asked before VisionClaw right-clicks something.
				pointer.RIGHT: _("Right-click {item}?"),
				# Translators: Asked before VisionClaw clicks something with the middle mouse button.
				pointer.MIDDLE: _("Click {item} with the middle mouse button?"),
				# Translators: Asked before VisionClaw clicks something three times in a row.
				pointer.TRIPLE: _("Triple-click {item}?"),
			}[action].format(item=what))
		if onMain(Screen.click, result, found, action, spot, keys) is False:
			raise ToolError(
				f"Where {found['text']} is on the screen is not known, so the mouse could not be used on it. Pointer "
				"mode lets the user put the mouse pointer on it.")
		time.sleep(CLICK_SETTLE_SECONDS)
		task.items = None  # the window has probably changed
		done = {
			pointer.CLICK: "Clicked", pointer.DOUBLE: "Double-clicked", pointer.RIGHT: "Right-clicked",
			pointer.MIDDLE: "Clicked with the middle mouse button:", pointer.TRIPLE: "Triple-clicked"}[action]
		return f"{done} {what}."

	add("click_item",
		"click, double-click, triple-click, right-click, click with the middle button, hover over, or press and hold "
		"one item from list_items: a link, a button, an item in a window; also with Control, Shift or Alt held down, "
		"or at a place on the item; hovering says what appeared",
		clickItem, {
			"item": text("the number or the name of the item, from list_items", maxLength=80),
			"action": text("what to do with the mouse", enum=pointer.ACTIONS, auto=pointer.actionOf),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="list_items", title="Clicking the item")

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
		# Translators: Asked before VisionClaw types text for the user. {text} is the text.
		confirm(_("Type \"{text}\" into the program?").format(text=clip(textToType, 80)))
		onMain(typeUnicode, textToType)
		return f"Typed: {clip(textToType, 80)}"

	registry.add(Tool("type_text", "type text into the program in front", guarded(notOwn(lambda task, text: typeText(task, text))),
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
			# No examples here: a small model copies an example as if it were the answer.
			raise ToolError("No setting matches those words. Use the words of the request that say what the setting does.")
		return "\n".join(found)

	add("find_setting", "find NVDA settings by describing them; gives each setting's id, value now and allowed values",
		findSetting, {"words": text("2 to 4 keywords for the setting, like: speech rate", maxLength=80,
			auto=lambda part: clip(profiles.without(part), 80).replace(" ...[cut]", ""))},
		looks=True, title="Finding the setting")

	def setSetting(task, setting, value, asked):
		# "Only in this program": read from the user's own words by plain code (claw/profiles.py). The words
		# that say so name no setting, and are left out when the setting is compared with the request.
		words = computer.own(asked or task.request)
		# The program in front, so that "in" and its name alone says for which program: "in Space Trader".
		here = _safe(lambda: onMain(profiletools.front)[1]) or {}
		scope = profiles.scopeOf(words, here)
		everywhere = profiles.everywhere(words)
		about = profiles.without(computer.own(asked), here) if asked else ""

		def work():
			found = _resolveSetting(setting)
			if found is None:
				raise ToolError(f"There is no setting with the id {setting}. Copy an id exactly from find_setting.")
			# Only the setting the user asked about may be changed, whatever a model decided.
			if about and not related(about, found.id, found.label):
				raise ToolError(
					f"The user asked: \"{clip(asked, 200)}\". That says nothing about {found.label}. "
					"Choose the setting from find_setting that the request is about. If none is, this cannot be done.")
			new = found.parse(value)
			old = found.shown()
			if found.id == "speech.volume":
				verdict, why = drivers.judgeVolume(new, _driverState()[drivers.DISPLAY][0])
				if verdict == drivers.REFUSE:
					raise Refused(why)
				if verdict == drivers.WARN:
					return found, new, old, found.read(), f"{why} " + _("Change {setting} from {old} to {new}?").format(
						setting=found.label, old=old, new=found.shown(new)), True
			# Translators: Asked before VisionClaw changes an NVDA setting.
			return found, new, old, found.read(), _("Change {setting} from {old} to {new}?").format(
				setting=found.label, old=old, new=found.shown(new)), False
		found, new, old, before, question, risky = onMain(work)
		if scope is not None:
			return setForProgram(task, scope, found, new, question, risky, words)
		# Everywhere, or only in the program in front? NVDA writes a change to the profile that is on. So where the
		# program in front has settings of its own, the user's words decide, and where they do not say, the user is
		# asked: the difference between everywhere and here is never left to chance.
		own, byHand, module, facts = _safe(lambda: onMain(profiletools.onTop)) or ("", "", None, {})
		if byHand and everywhere:
			return profiles.manualOn(byHand)
		if own:
			program = profiles.shown(facts)
			if not everywhere:
				# Translators: Put before the question about a change, so the user can tell if it is what they asked for.
				said = (_("You asked: {request}").format(request=clip(asked, 160)).rstrip(".") + ". ") if asked else ""
				chosen = plugin.clawAsk(
					said + profiles.whichQuestion(found.label, old, found.shown(new), program), profiles.whichChoices(program))
				if chosen == 0:
					return setForProgram(task, {"program": "", "words": ""}, found, new, question, risky, words, agreed=True)
				if chosen != 1:
					raise UserSaidNo()
			else:
				whole = question.rstrip("?") + ", everywhere?"
				if asked:
					whole = _("You asked: {request}").format(request=clip(asked, 160)).rstrip(".") + ". " + whole
				mustAgree(whole) if risky else confirm(whole)
			app = (facts.get("app") or "").lower()
			profiletools.settle(lambda: onMain(profiletools.front)[1]["app"].lower() == app, task.check)

			def everywhereWork():
				_own, _byHand, module, _facts = profiletools.onTop()
				return profiletools.writeBase(module, found, raw=value)
			try:
				was, beforeBase, newBase, nowBase, kept = onMain(everywhereWork)
			except profiletools.NotPossible as e:
				return str(e)
			plugin.changes.add(found.id, found.label, beforeBase, newBase, was, nowBase, asked or task.request)
			return profiles.everywhereDone(found.label.capitalize(), was, nowBase, program, kept) + profiles.othersKeep(
				[name for name in _safe(lambda: onMain(profiletools.holders, found.path, own), []) or [] if name != program])
		if byHand:
			question += " " + profiles.manualTakes(byHand)
			risky = True
		if profiles.NARROWS.search(words):
			# The words narrow the request down, and no program could be read from them. The user is told what
			# will happen, whatever the settings say, before anything is changed everywhere.
			# Translators: Added to the question about a change when the user's words seem to narrow it down.
			question += " " + _("This will apply in every program.")
			risky = True
		if asked:
			# Translators: Put before the question about a change, so the user can tell if it is what they asked for.
			question = _("You asked: {request}").format(request=clip(asked, 160)).rstrip(".") + ". " + question
		mustAgree(question) if risky else confirm(question)
		onMain(found.write, new)
		now = onMain(found.shown)
		# Every change is written down, so that it can be put back.
		plugin.changes.add(found.id, found.label, before, new, old, now, asked or task.request)
		said = f"{found.label.capitalize()} was {old} and is now {now}."
		if byHand:
			return f"{said} {profiles.manualTakes(byHand)}"
		# Programs that have a value of their own for this keep it: said, so that "it did not change in Word" is
		# no surprise.
		return said + profiles.othersKeep(_safe(lambda: onMain(profiletools.holders, found.path), []) or [])

	def setForProgram(task, scope, found, new, question, risky, words, agreed=False):
		"""Change a setting for the program in front only, in NVDA's configuration profile for it."""
		try:
			_module, facts, profile = onMain(profiletools.check, scope["program"], found.id)
		except profiletools.NotPossible as e:
			return str(e)
		program = profiles.shown(facts)
		question = (
			# Translators: Put before the question about a change, so the user can tell if it is what they asked for.
			_("You asked: {request}").format(request=clip(words, 160)).rstrip(".") + ". "
			+ profiles.question(program, profile is None) + " " + question)
		# A new profile changes how NVDA behaves in a program from now on: always asked about. Where the user has
		# just chosen "only in this program" in a question, that was the asking.
		if not agreed:
			mustAgree(question) if (risky or profile is None) else confirm(question)
		# The question was a window of NVDA. NVDA needs a moment to see that the program is in front again.
		app = facts["app"].lower()
		profiletools.settle(lambda: onMain(profiletools.front)[1]["app"].lower() == app, task.check)

		def work():
			# The question was a window of NVDA; the program is in front again now. Everything from here to the
			# write happens in one go on NVDA's main thread, so that nothing can come in between.
			module, facts, _profile = profiletools.check(scope["program"], found.id)
			name, created = profiletools.activate(module)
			try:
				old, before = found.shown(), found.read()
				profiletools.write(name, found, new)
			except Exception:
				if created:
					profiletools.forget(name)
				raise
			return name, created, old, before, found.shown(), profiles.shown(facts)
		try:
			name, created, old, before, now, program = onMain(work)
		except profiletools.NotPossible as e:
			return str(e)
		plugin.changes.add(found.id, found.label, before, new, old, now, words, profile=name, program=program)
		return profiles.done(found.label.capitalize(), old, now, program, name, created)

	add("set_setting", "change one NVDA setting", setSetting, {
		"setting": text("the id of the setting, copied from find_setting", maxLength=80),
		"value": text("the new value: on, off, a number, +10 or -10 to change a number, or one of the allowed values",
			maxLength=60),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
	}, changes=True, before="find_setting", title="Changing the setting")

	def undoChange(task, what):
		def known(change):
			named, also = settingWords(change["setting"], change["label"])
			return named | also
		change, reason = changes.choose(what, plugin.changes.pending(), known)
		if reason == "nothing":
			return "VisionClaw has not changed any setting, so there is nothing to put back."
		if reason == "other":
			return (
				"VisionClaw has not changed that, so it cannot put it back. What it has changed, and can put back:\n"
				+ plugin.changes.text())

		if str(change["setting"]).startswith("classicspeech:"):
			# What VisionClaw changed in the add-on ClassicSpeech: put back with that add-on's own calls.
			from . import partnertools
			return partnertools.undoClassic(plugin, change, confirm)
		if str(change["setting"]).startswith("file:"):
			# What VisionClaw did to a file of the user's: turned round by the tool that did it.
			try:
				return computertools.undoFile(plugin, change, confirm)
			except OSError as e:
				raise ToolError(f"It could not be put back. {e}")

		profile = change.get("profile") or ""

		def work():
			found = _resolveSetting(change["setting"])
			if found is None:
				raise ToolError(f"The setting {change['label']} is not there any more, so it cannot be put back.")
			# A setting that was changed for one program is put back while that program's profile is the one
			# NVDA writes to, and never anywhere else.
			if profile and profiletools.top() != profile:
				return found, None, None
			return found, found.shown(), found.shown(change["old"])
		found, now, back = onMain(work)
		program = change.get("program") or profile
		if profile and now is None:
			return profiles.undoElsewhere(found.label, program)
		where = f" in {program}" if profile else ""
		if now == back:
			plugin.changes.markUndone(change)
			return f"{found.label.capitalize()}{where} is already {back}, as it was before VisionClaw changed it."
		# Translators: Asked before VisionClaw puts a setting back to what it was. {where} is empty, or says in which program.
		confirm(_("Put {setting}{where} back from {now} to {old}, as it was before VisionClaw changed it?").format(
			setting=found.label, where=where, now=now, old=back))
		if profile:
			# While the question was open NVDA had the program's profile turned off; it is on again a moment
			# after the program is in front.
			profiletools.settle(lambda: onMain(profiletools.top) == profile, task.check)

		def putBack():
			if profile:
				profiletools.write(profile, found, change["old"])
				return found.shown()
			# A change that was made everywhere is put back in NVDA's normal configuration, also while the program
			# in front has a profile of its own that is on.
			own, byHand, module, _facts = profiletools.onTop()
			if byHand:
				raise profiletools.NotPossible(profiles.manualOn(byHand))
			if own:
				return profiletools.writeBase(module, found, value=change["old"])[3]
			found.write(change["old"])
			return found.shown()
		try:
			after = onMain(putBack)
		except profiletools.NotPossible as e:
			return profiles.undoElsewhere(found.label, program) if profile else str(e)
		plugin.changes.markUndone(change)
		return f"{found.label.capitalize()}{where} was {now} and is back to {after}, as it was before."

	add("undo_change", "put a setting back to what it was before VisionClaw changed it", undoChange,
		{"what": text("which change to undo, in the user's words", maxLength=300, auto=True)},
		changes=True, title="Putting it back")

	add("list_changes", "say which settings VisionClaw has changed, and from what to what",
		lambda task: plugin.changes.text() or "VisionClaw has not changed any setting.",
		looks=True, title="Looking up what was changed", tell=VERBATIM)

	# Settings that one program has for itself, in NVDA's configuration profiles (claw/profiles.py).
	def programSettings(task, asked):
		return profiles.listText(onMain(profiletools.listed, plugin.changes.pending()))

	add("program_settings", "say which programs have NVDA settings of their own, kept in NVDA's configuration profiles",
		programSettings, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking up which programs have their own settings", tell=VERBATIM)

	def removeProgramSettings(task, asked):
		program, profile = onMain(profiletools.profileFor, profiles.namedIn(asked or task.request))
		if profile is None:
			return profiles.noProfile(program)
		# It cannot be undone, so it is always asked about, whatever the settings say.
		mustAgree(profiles.removeQuestion(program, profile))
		try:
			onMain(profiletools.remove, profile)
		except profiletools.NotPossible as e:
			return str(e)
		plugin.changes.markProfileGone(profile)
		return profiles.removed(program, profile)

	add("remove_program_settings",
		"delete the NVDA settings one program has for itself, so that NVDA behaves there as it does everywhere else",
		removeProgramSettings, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Removing the program's own settings")

	# Commands.
	def findCommand(task, words):
		known = onMain(_commands)
		task.commands = known
		# The commands NVDA lists come first; those without a description are looked at only when none of
		# the listed ones fits, so that an unnamed script never pushes a described command aside.
		found = []
		for documented in (True, False):
			pool = [c for c in known if c.documented == documented]
			found = [pool[i] for i in commands.find(words, [(c.scriptName, c.description, c.category) for c in pool], MAX_FOUND)]
			if found:
				break
		debuglog.log("command", f"Looked among {len(known)} commands for \"{words}\": found {[c.id for c in found]}")
		if not found:
			raise ToolError("No NVDA command matches those words. Use the words of the request that say what the command does.")
		return "\n".join(c.line() for c in found)

	add("find_command", "find NVDA commands by describing what they do; gives each command's id and its keys",
		findCommand, {"words": text("2 to 4 keywords for what the command does, like: window title", maxLength=80,
			auto=True)}, looks=True, title="Finding the command")

	def runCommand(task, command, asked):
		known = getattr(task, "commands", None) or onMain(_commands)
		index = match.best(command, [c.id for c in known], least=0.85)
		if index is None:
			raise ToolError(f"There is no command with the id {command}. Copy an id exactly from find_command.")
		chosen = known[index]
		risk = _RISKY_COMMANDS.get(chosen.scriptName)
		if risk:
			# Translators: Asked before an NVDA command that can silence or close NVDA. {command} is the command.
			mustAgree(f"{risk} " + _("Run the command: {command}?").format(command=chosen.description or chosen.id))
		# Many commands do something else on a second or third press: the time once, the date twice. What the
		# user asked for decides how often, read from the command's own description by plain code.
		wanted = commands.presses(asked or task.request, chosen.scriptName, chosen.description)
		with _SpeechCapture() as heard:
			start = onMain(_runCommand, chosen, wanted, heard)
			task.cancel.wait(COMMAND_SETTLE_SECONDS)
		said = " ".join(heard.texts[start:]).strip()
		debuglog.log("command", f"{chosen.id} ran. NVDA said: {said!r}")
		often = "" if wanted[-1] == 1 else f" {commands.pressText(wanted[-1])}"
		keys = f" Next time you can press {' or '.join(chosen.keys)}{often} for this." if chosen.keys else ""
		done = f"NVDA said: {clip(said, 500)}" if said else f"Done: {chosen.description or chosen.id}"
		return f"{done.rstrip('.')}.{keys}"

	add("run_command", "run one NVDA command for the user", runCommand, {
		"command": text("the id of the command, copied from find_command", maxLength=60),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
	}, changes=True, before="find_command", title="Running the command")

	# Learning about NVDA.
	def searchHelp(task, words):
		found = plugin.knowledge.text(words, limit=3, chars=600)
		lessons = plugin.memory.search(words, limit=2)
		if lessons:
			found += "\n\nLearned earlier on this computer:\n" + "\n".join(f"- {t}" for t in lessons)
		# The user's own library, searched the same way.
		shelf = Knowledge(folder="")
		shelf.addSource("library", plugin.library.sections)
		inLibrary = shelf.text(words, limit=2, chars=600)
		if inLibrary:
			found = f"{found}\n\nFrom your library:\n{inLibrary}".strip()
		if not found.strip():
			raise ToolError("Nothing was found for those words. Try other words.")
		return found

	def updateGuides(task):
		# Going online is always asked about, whatever the settings say.
		# Translators: Asked before the developer guides are downloaded from the internet.
		mustAgree(_(
			"Download the latest NVDA Developer Guide from NV Access, and the NVDA Add-on Development Guide from the "
			"NVDA add-ons community on GitHub? Only these two requests are sent, with nothing about you or this "
			"computer. The guides are kept on this computer as text for the models to read."))
		result = guides.update(
			plugin.guidesDir, lambda url: net.fetchText(url, limit=guides.MAX_BYTES, hosts=guides.HOSTS), task.cancel)
		plugin.knowledge.replaceSource(guides.SOURCE, lambda: guides.load(plugin.guidesDir))
		plugin.devGuides.reload()
		return guides.summary(result)

	add("update_guides",
		"download the latest NVDA developer guide and NVDA add-on development guide from the internet and keep them "
		"for the models to read; only when the user asks for exactly this",
		updateGuides, changes=True, title="Getting the latest developer guides", tell=VERBATIM)

	def guidesInfo(task, asked):
		# What VisionClaw knows, plain code says: which guides are here, from which day, and where.
		told = guides.storedText(plugin.guidesDir)
		if plugin.devGuides.here() and re.search(r"\b(open|show me the (files?|folder)|see the (files?|folder))\b", asked or "", re.IGNORECASE):
			try:
				onMain(os.startfile, plugin.guidesDir)
			except OSError as e:
				raise ToolError(f"The folder could not be opened ({e}). It is {plugin.guidesDir}.")
			told = "The folder with the developer guides is open in a window. " + told
		return told

	add("guides_info",
		"say which NVDA developer guides VisionClaw has downloaded to this computer, from which day and where they "
		"are kept, or open their folder; not for what the guides say about something",
		guidesInfo, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking at the developer guides", tell=VERBATIM)

	def removeGuides(task):
		if not plugin.devGuides.downloaded():
			return (
				"No developer guides were downloaded, so there is nothing to delete. "
				+ ("The copy that came with VisionClaw stays; it is part of the add-on." if plugin.devGuides.here() else "")).strip()
		# Translators: Asked before the downloaded developer guides are deleted.
		confirm(_(
			"Delete the NVDA developer guides from this computer? VisionClaw then no longer looks things up in them. "
			"They can be downloaded again at any time."))
		gone = guides.remove(plugin.guidesDir)
		plugin.knowledge.replaceSource(guides.SOURCE, lambda: guides.load(plugin.guidesDir))
		plugin.devGuides.reload()
		if not gone:
			raise ToolError("The developer guides could not be deleted. Their files are in the folder " + plugin.guidesDir + ".")
		return (
			f"Deleted from this computer: the {' and the '.join(gone)}. To have them again, ask VisionClaw to get the "
			"latest NVDA developer guides." + (
				" The copy that came with VisionClaw is used again." if plugin.devGuides.here() else ""))

	add("remove_guides", "delete the downloaded NVDA developer guides from this computer",
		removeGuides, changes=True, title="Deleting the developer guides", tell=VERBATIM)

	# What VisionClaw can download for the user, whether it is here already, and the words that get it.
	add("downloads_info",
		"say what VisionClaw can download for the user on request, guides, lessons and notes, whether each is on this "
		"computer already, and what to say to get it; when the user asks what it can download, get or learn from",
		lambda task: offers.overview(plugin.downloadState()), looks=True,
		title="Looking at what can be downloaded", tell=VERBATIM)

	# Free material that teaches NVDA: the NVDA wiki, AFB's lessons and Hadley's workshops (claw/training.py).
	# The owner said yes to these three sources on 2026-11-18.
	def updateTraining(task):
		# Going online is always asked about, whatever the settings say. The question names every site.
		mustAgree(training.question())
		result = training.update(
			plugin.trainingDir, lambda url: net.fetchText(url, limit=training.MAX_BYTES, hosts=training.HOSTS), task.cancel)
		plugin.knowledge.replaceSource(training.SOURCE, lambda: training.load(plugin.trainingDir))
		return training.summary(result)

	add("update_training",
		"download free material that teaches NVDA from the internet, the NVDA wiki, the lessons of the American "
		"Foundation for the Blind and the workshops of Hadley, and keep it for looking things up; only when the "
		"user asks for exactly this",
		updateTraining, changes=True, title="Getting the free training material", tell=VERBATIM)

	def trainingInfo(task, asked):
		# What VisionClaw has to read, said by plain code: the training material, and NVDA's own help as Markdown.
		told = training.storedText(plugin.trainingDir) + " " + helpfiles.listText(plugin.helpDir)
		if re.search(r"\b(open|show me the (files?|folder)|see the (files?|folder))\b", asked or "", re.IGNORECASE):
			folder = plugin.trainingDir if training.here(plugin.trainingDir) else plugin.helpDir
			if os.path.isdir(folder):
				try:
					onMain(os.startfile, folder)
				except OSError as e:
					raise ToolError(f"The folder could not be opened ({e}). It is {folder}.")
				told = f"The folder {folder} is open in a window. " + told
		return told

	add("training_info",
		"say which training material about NVDA VisionClaw has downloaded to this computer, from which day and "
		"where it is kept, and where NVDA's own help is kept as Markdown files, or open the folder; not for what "
		"the material says about something",
		trainingInfo, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking at the training material", tell=VERBATIM)

	def removeTraining(task):
		if not training.here(plugin.trainingDir):
			return "No training material is on this computer, so there is nothing to delete."
		# Translators: Asked before the downloaded training material is deleted.
		confirm(_(
			"Delete the downloaded NVDA training material from this computer? VisionClaw then no longer looks things "
			"up in it. It can be downloaded again at any time."))
		gone = training.remove(plugin.trainingDir)
		plugin.knowledge.replaceSource(training.SOURCE, lambda: training.load(plugin.trainingDir))
		if not gone:
			raise ToolError("The training material could not be deleted. Its files are in the folder " + plugin.trainingDir + ".")
		return (
			f"Deleted from this computer: {', '.join(gone)}. To have it again, ask VisionClaw to get the free NVDA "
			"training material.")

	add("remove_training", "delete the downloaded NVDA training material from this computer",
		removeTraining, changes=True, title="Deleting the training material", tell=VERBATIM)

	add("search_help", "read NVDA's user guide, the developer guides and VisionClaw's notes on NVDA and its add-on system", searchHelp,
		{"words": text("2 to 4 keywords for what you need to know", maxLength=80, auto=True)}, looks=True,
		title="Reading up on it")

	def findNvda(task, words):
		found = inside.search(insideIndex(), words, MAX_FOUND)
		debuglog.log("inside", f"Looked inside NVDA for \"{words}\": found {[entry.name for entry in found]}")
		if not found:
			raise ToolError("Nothing inside NVDA matches those words. Use the words of the request that say what the thing does.")
		return "\n".join(clip(entry.line(), 230) for entry in found)

	add("find_nvda",
		"find functions, classes, modules, objects and values inside NVDA's own code and its add-ons' code by "
		"describing them; gives each one's dotted name and what it is",
		findNvda, {"words": text("2 to 4 keywords for what the thing does, or its name", maxLength=120, auto=True)},
		looks=True, title="Searching inside NVDA")

	add("inspect_nvda",
		"look closely at one thing inside NVDA's code: what a module, class, function or value is, how to call it, "
		"and what it holds or gives back now",
		lambda task, name: onMain(_inspect, name),
		{"name": text("its dotted name, copied from find_nvda", maxLength=120)}, looks=True, before="find_nvda",
		title="Looking inside NVDA", tell=VERBATIM)

	def objectInfo(task, object, asked):
		which = object if object in OBJECTS else objectOf(asked)

		def work():
			found = _theObject(which)
			if found is None:
				raise ToolError(f"NVDA has no such object now: {_OBJECT_NAMES[which].lower()}.")
			return objectAnswer(found, which, asked)
		result = onMain(work)
		debuglog.detail("object", result)
		return result

	add("object_info",
		"say what NVDA knows about one object: the focused control, the navigator object, the window in front, what "
		"is under the mouse, the desktop, or what the focused control is inside of; every fact, or the ones asked for",
		objectInfo, {
			"object": text("which object", enum=OBJECTS, auto=objectOf),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, looks=True, title="Asking NVDA about the object", tell=VERBATIM)

	def auditNvda(task, asked):
		# Everything this NVDA has, counted and listed: the commands where the user is, everything inside the
		# loaded modules, and how the synthesizer and the braille display are driven. Read only.
		known = onMain(_commands)
		task.check()
		entries = insideIndex()
		task.check()
		count = inside.counts(entries)
		described = [c for c in known if c.documented]
		withKeys = [c for c in known if c.keys]
		speechLines = onMain(lambda: nvdainfo.speech().splitlines() + nvdainfo.speechInside())
		brailleLines = onMain(lambda: nvdainfo.brailleInfo().splitlines() + nvdainfo.brailleInside())
		general = onMain(nvdainfo.general).splitlines()
		totals = [
			f"Commands that can be used where you are now: {len(known)}. {len(described)} have a description, "
			f"{len(known) - len(described)} have none, and {len(withKeys)} have a key.",
			f"Modules loaded: {count[inside.MODULE] - count['notLoaded']}. Modules that belong to NVDA and are not "
			f"loaded, such as drivers that are not in use: {count['notLoaded']}.",
			f"Classes: {count[inside.CLASS]}. Functions: {count[inside.FUNCTION]}. Methods: {count[inside.METHOD]}, "
			f"of which {count['commands']} are commands. Properties: {count[inside.PROPERTY]}. Values: {count[inside.VALUE]}.",
		]
		sections = [
			("What this is", [
				"A list of everything in the NVDA that is running on this computer, made by VisionClaw from the "
				"running program itself. Nothing was changed, and nothing was sent anywhere.",
				f"Made on {time.strftime('%Y-%m-%d at %H:%M')}."] + general),
			("Totals", totals),
			("Speech: how NVDA talks to the synthesizer", speechLines),
			("Braille: how NVDA talks to the braille display", brailleLines),
			("Commands with a description, usable where you are now", [c.line() for c in described]),
			("Commands without a description, usable where you are now", [
				f"{c.line()} From {c.source}." for c in known if not c.documented]),
		]
		path = os.path.join(os.path.dirname(plugin.guidesDir), "nvda-audit.md")
		try:
			with open(path, "w", encoding="utf-8", newline="\n") as f:
				f.write(inside.auditText("Audit of this NVDA by VisionClaw", sections, entries))
		except OSError as e:
			raise ToolError(f"The audit could not be saved: {e}")
		debuglog.log("audit", f"Audit written to {path}: {totals}")
		opened = ""
		if re.search(r"\b(open|show|read|see|view)\b", (asked or "").lower()):
			onMain(os.startfile, path)
			opened = " It is open in a window now."
		first = lambda lines: lines[0] if lines else ""  # noqa: E731
		return (
			f"VisionClaw went through all of this NVDA. {' '.join(totals)} {first(speechLines)} {first(brailleLines)} "
			f"The whole list, with every command, module, class, function and value by name, and how speech and "
			f"braille are driven, is saved as the file {path}.{opened} You can ask about any of it by describing it.")

	add("audit_nvda",
		"go through all of the running NVDA and count and list everything in it: every command, module, class, "
		"function, object and value, and how it drives the speech synthesizer and the braille display; saves the "
		"list as a file",
		auditNvda, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Going through all of NVDA", tell=VERBATIM)

	def showLog(task):
		path = debuglog.path()
		if not path or not debuglog.on():
			return "VisionClaw's log is switched off. It is switched on in VisionClaw's settings, under Debug log."
		if not os.path.isfile(path):
			return f"VisionClaw's log is still empty. It will be the file {path}."
		onMain(os.startfile, path)
		return (
			f"VisionClaw's log is open in a window. It is the file {path}. It stays on this computer and holds "
			"what VisionClaw was asked, what it did and every error.")

	add("show_log", "open VisionClaw's own debug log, the file that records what VisionClaw did and every error",
		showLog, looks=True, title="Opening VisionClaw's log", tell=VERBATIM)

	def askUserTool(task, question):
		answer = plugin.clawAskText(question)
		task.check()
		return f"The user answered: {answer}" if answer else "The user gave no answer."

	add("ask_user", "ask the user a question when something needed is not known", askUserTool,
		{"question": text("the question, in plain words", maxLength=200)}, looks=True, title="Asking you")

	# App helpers and add-ons.
	def createHelper(task, key, action, item, asked=""):
		result = getattr(task, "items", None) or screen.items()
		index = match.itemIndex(item, Screen.names(result))
		if index is None:
			raise ToolError(f"There is no item called \"{item}\" in the window. Use a name from list_items.")
		name = Screen.names(result)[index]
		app = onMain(screen.where)[0]
		# A button of a game controller can be the hotkey: the user's own words say which.
		button = gamepad.buttonOf(asked or task.request) or gamepad.buttonOf(key)
		if button is not None:
			key = f"{gamepad.buttonText(button)} of the game controller"
			keyId = gamepad.identifier(button)
		else:
			keyId = onMain(plugin.helpers.keyId, key)
		if keyId is None:
			raise ToolError(
				f"\"{key}\" is not a key. Use something like NVDA+alt+1 or NVDA+shift+p, or name a button of the game "
				"controller, such as the X button or the left shoulder button.")
		# Translators: Asked before VisionClaw saves a hotkey for a program.
		confirm(_("In {app}, make {key} {action} \"{item}\"?").format(app=app, key=key, action=action, item=name))
		plugin.helpers.add(app, key, keyId, action, name)
		more = {
			pointer.HOVER: " It rests the mouse pointer on it and says what appears.",
			pointer.HOLD: " The mouse button stays down on it until you press the hotkey again, or Escape.",
		}.get(action, "")
		if button is not None:
			more += (
				" It works whenever the controller is connected, in this program only, in controller mode or out of it."
				if onMain(lambda: plugin.controller.device) is not None else
				" No game controller is connected just now; it works as soon as one is.")
		return f"In {app}, pressing {key} now does this: {action} \"{name}\".{more}"

	add("create_helper",
		"give the program in front its own hotkey, a key or a button of a game controller, that clicks an item, "
		"hovers over it, holds it down, or reads the text at it, found by name each time",
		createHelper, {
			"key": text("the hotkey, like NVDA+alt+1, or the button of the game controller", maxLength=40),
			"action": text(
				"click, double click, triple click, right click or middle click the item; hover rests the mouse pointer "
				"on it and says what appears; press and hold keeps the mouse button down on it until the hotkey is "
				"pressed again; read speaks the item and the text after it",
				enum=pointer.ACTIONS + ["read"], auto=helperAction),
			"item": text("the name of the item, from list_items", maxLength=80),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
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
		# What a skill says, what the user asked VisionClaw to remember, their library, the notes on accessibility
		# interfaces and the lines of the developer guides that belong with the add-on come before the notes.
		notes = coderNotes(plugin, task, purpose, notes)
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
			if policy.isOneModel(plugin.runtime):
				# Translators: Added to the question when the one model, reading its own code again, is not sure about it.
				question = _("Reading its code again, the model has a doubt about it: {doubt} ").format(doubt=task.codeDoubt) + question
			else:
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
		lambda task: "\n".join(part for part in (plugin.helpers.listText(), "\n".join(plugin.appWays.lines())) if part)
		or "VisionClaw has not made any helpers or add-ons yet.", looks=True,
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

	# Which models VisionClaw itself has and uses. Plain code reads the settings and the disk: a model does not
	# know its own name, and would make one up.
	def modelInfo(task):
		# Translators: Added to the answer about VisionClaw's models. The key is the default one.
		return plugin.runtime.aboutText() + " " + _("To see, remove or choose other models, press NVDA+Alt+M.")

	add("model_info",
		"say which AI models VisionClaw itself has stored on this computer and uses, how big they are, and where "
		"they run",
		modelInfo, looks=True, title="Checking VisionClaw's models", tell=VERBATIM)

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
		return waitForPage(task, before)

	def waitForPage(task, before):
		"""The title of the page that is there once the browser has loaded it; "" when it was not in time."""
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

	def webOpen(task, address, asked=""):
		url = web.normalizeAddress(address)
		# A browser the user names, as in "go to example.com in Chrome", is used where it is installed.
		named = computer.browserOf(asked or task.request)
		path = computertools.browserPath(named[0]) if named else None
		said = ""
		if named and path is None:
			said = f" {named[1]} was not found on this computer, so your usual browser was used."
		if path is not None:
			before = onMain(pageNow)
			try:
				computertools.shellOpen(path, url)
			except OSError as e:
				raise ToolError(f"{named[1]} could not be started. {e}")
			pageTitle = waitForPage(task, before)
			said = f" It was opened in {named[1]}."
		else:
			pageTitle = openPage(task, url)
		if not pageTitle:
			return "The address was given to the browser, but the page was not ready in time." + said
		return f"Opened the web page {pageTitle}." + said

	add("web_open", "open a web address in the user's browser, or in a browser they name", webOpen, {
		"address": text("the web address, like example.com", maxLength=300, auto=web.addressIn),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
	}, title="Opening the web page", tell=VERBATIM)

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

	def goToItem(task, item, asked):
		result = getattr(task, "items", None)
		if result is None or not getattr(result, "web", False):
			raise ToolError("Use list_items first, in a web page.")
		index = pickItem(meant(asked, result.items, item), result.items, ("heading",))
		if index is None:
			raise ToolError(f"There is no item called \"{item}\" on the page. Use a number or a name from list_items.")
		found = result.items[index]
		onMain(webtools.moveTo, found)
		return f"NVDA is now at {found['text']}. Use NVDA's say all command to read on from there."

	add("go_to_item",
		"move NVDA's reading position to one item from list_items on the web page: a heading, a link or a field",
		goToItem, {
			"item": text("the number or the name of the item, from list_items", maxLength=80),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, before="list_items", title="Moving there", tell=VERBATIM)

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

	def fillField(task, field, typed, enter, asked):
		from keyboardHandler import KeyboardInputGesture
		result = getattr(task, "items", None) or screen.items()
		if getattr(result, "web", False):
			fields = [item for item in result.items if item.get("kind") in webtools.FIELD_KINDS]
			index = webtools.fieldIndex(meant(asked, fields, field), result.items)
		else:
			index = match.itemIndex(meant(asked, result.items, field), Screen.names(result))
		if index is None:
			raise ToolError(f"There is no field called \"{field}\". Use a number or a name from list_items.")
		found = result.items[index]
		# Translators: Asked before VisionClaw types into a field. {text} is the text, {field} the field.
		confirm(_("Type \"{text}\" into {field}?").format(text=clip(typed, 80), field=found["text"]))
		onMain(Screen.click, result, found)  # in a web page this goes into the field, as Enter does
		time.sleep(0.5)
		onMain(typeUnicode, typed)
		if enter == "yes":
			time.sleep(0.2)
			onMain(KeyboardInputGesture.fromName("enter").send)
			time.sleep(CLICK_SETTLE_SECONDS)
		task.items = None
		return f"Typed \"{clip(typed, 80)}\" into {found['text']}" + (" and pressed Enter." if enter == "yes" else ".")

	registry.add(Tool(
		"fill_field", "type text into one field from list_items, such as a search box or a field of a form",
		guarded(lambda task, field, text, enter, asked: fillField(task, field, text, enter, asked), True), {
			"field": text("the number or the name of the field, from list_items", maxLength=80),
			"text": text("the text to type into it", maxLength=400),
			"enter": text("yes to press Enter afterwards, to search or send", enum=["yes", "no"],
				auto=lambda part: "yes" if _SUBMITS.search(part) else "no"),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="list_items", title="Typing into the field"))

	# The mouse from the keyboard: dragging, and pointer mode.
	shared = mousetools.register(add, plugin, text, confirm, screen, pickItem, mentioned)
	# Fingers and pressure: touching the screen as a hand would, and pressing as a pen would.
	from . import touchtools
	touchtools.register(add, plugin, text, confirm, mustAgree, shared)
	# A game controller: whether one is connected, and controller mode.
	from . import padtools
	padtools.register(add, plugin, text)
	from . import controlkeys
	controlkeys.register(add, plugin, text, confirm, screen, pickItem, mentioned)
	# Deep inspection, lasting fixes for a website or program, and questions about installed add-ons.
	from . import accesstools
	accesstools.register(plugin, add, text, registry)
	# A newer version of VisionClaw itself, when the user asks for it in words.
	from . import updater
	updater.register(plugin, add, text)
	# Skills: making, listing, reading, turning off and deleting them, in words.
	from . import skilltools
	skilltools.register(plugin, add, text, onMain, confirm)
	# A question: NVDA is asked, then the program, then its window, then Windows.
	from . import asktools
	asktools.register(plugin, add, text, onMain, _commands)
	# Learning about the program in front from the internet, after a question, and the notes kept of it.
	from . import learntools
	learntools.register(plugin, add, text, onMain, confirm)
	# What the user asked VisionClaw to remember, as Markdown files, and the user's library of documents.
	from . import memorytools
	memorytools.register(plugin, add, text, onMain, confirm)
	# The computer itself: things opened by name, the Recycle Bin, the volume, windows, files, facts, power.
	computertools.register(add, plugin, text, onMain, confirm, mustAgree, Refused, screen)
	# A named control of the program in front: on or off, up or down, also on another page of its dialog.
	from . import controltools
	controltools.register(add, plugin, text, onMain, confirm, screen)
	# A web page as a whole, and what stops a form on it (pagetools.py). Imported here for the same reason.
	from . import pagetools
	pagetools.register(add, plugin, text, onMain)
	# A date chosen in a calendar that cannot be worked with the keyboard (datetools.py).
	from . import datetools
	datetools.register(add, plugin, text, onMain, confirm, screen)
	# Asking by voice: whether it is set up, getting the speech model, deleting it (voiceui.py).
	from . import voiceui
	voiceui.register(add, plugin, text, mustAgree)
	# The JAWS Migration Assistant and ClassicSpeech, where they are running in this NVDA (partnertools.py).
	from . import partnertools
	partnertools.register(add, plugin, text, onMain, confirm, lambda: onMain(_commands))
	# Working through a task with the user when the usual path is not clear (guidetools.py).
	from . import guidetools
	guidetools.register(add, plugin, text, onMain, screen)

	# VisionClaw's own voice, which the user sets in NVDA's own Speech settings (ownvoice.py).
	def ownVoice(task, asked):
		from . import ownvoice
		wanted = ownvoice.wish(asked or task.request)
		now = bool(config.conf["visionClaw"]["ownVoice"])
		if wanted == ownvoice.CUSTOMISE:
			problem = onMain(ownvoice.check)
			if problem:
				return problem
			# A profile is made and NVDA's settings are opened: always asked about.
			mustAgree(ownvoice.QUESTION.format(name=onMain(ownvoice.profileName) or ownvoice.PROFILE))
			config.conf["visionClaw"]["ownVoice"] = True
			return onMain(ownvoice.customise)
		if wanted == ownvoice.REMOVE:
			name = onMain(ownvoice.profileName)
			if not name:
				return "VisionClaw has no voice of its own, so there is nothing to remove. It speaks as NVDA does."
			mustAgree(
				f"Delete the configuration profile {name}, which holds VisionClaw's own voice? VisionClaw then speaks as "
				"NVDA does. This cannot be undone.")
			onMain(ownvoice.remove)
			return f"The configuration profile {name} was deleted. VisionClaw speaks with NVDA's own voice again."
		if wanted is None or wanted == now:
			return onMain(ownvoice.stateText, now)
		config.conf["visionClaw"]["ownVoice"] = wanted
		return onMain(ownvoice.stateText, wanted)

	add("own_voice",
		"give VisionClaw a voice of its own by opening NVDA's Speech settings for it, turn that voice on or off, remove "
		"it, or say whether it has one",
		ownVoice, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		title="Looking at VisionClaw's own voice", tell=VERBATIM)

	registry.add(Tool(ANSWER, "tell the user the result in plain words; always the last step", lambda task: ""))
	return registry
