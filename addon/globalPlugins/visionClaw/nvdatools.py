# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools the models can use inside NVDA. Each tool is a small form and a function.
# The functions run on the task's worker thread; everything that touches NVDA is passed to NVDA's main thread.

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

from . import ocr
from .claw import match, microaddons
from .claw.catalog import CODER, VISION
from .claw.llm import LLM, clip
from .claw.memory import score
from .claw.tools import ANSWER, VERBATIM, Registry, Tool, ToolError
from .engine import prepareImage

addonHandler.initTranslation()

MAX_ITEMS_SHOWN = 45
MAX_FOUND = 6
CLICK_SETTLE_SECONDS = 0.7
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
	"speech.speakTypedCharacters": "echo",
}
_NAMED_VALUES = {"speech.symbolLevel": {"none": 0, "some": 100, "most": 200, "all": 300}}
_SYNTH_NUMBERS = ("rate", "pitch", "volume")
_TARGETS = ["window", "screen", "control"]


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


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


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


def _synthSettings():
	synth = synthDriverHandler.getSynth()
	found = []
	if synth is None:
		return found

	def save(name, value):
		setattr(synth, name, value)
		try:
			config.conf["speech"][synth.name][name] = value
		except Exception:
			log.debugWarning("VisionClaw: could not save the synthesizer setting", exc_info=True)

	for name in _SYNTH_NUMBERS:
		if _safe(lambda n=name: synth.isSupported(n)):
			found.append(_Setting(
				f"speech.{name}", f"speech {name}", "number",
				lambda n=name: int(getattr(synth, n)), lambda v, n=name: save(n, v), 0, 100,
			))
	voices = _safe(lambda: synth.availableVoices) or {}
	if len(voices) > 1:
		names = {info.displayName: ident for ident, info in voices.items()}
		found.append(_Setting(
			"speech.voice", "speech voice", "option",
			lambda: next((n for n, i in names.items() if i == synth.voice), synth.voice),
			lambda v: save("voice", names.get(v, v)), options=list(names)[:40],
		))
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
		"""The texts and icons in the window in front, read from its picture. Returns the overlay's result."""
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
		"""Click the middle of an item, and put the mouse back. Main thread."""
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

	def guarded(fn):
		"""A tool function where the user saying no ends the step quietly instead of as an error."""
		def run(task, **form):
			try:
				return fn(task, **form)
			except UserSaidNo:
				return "You said no, so nothing was changed."
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

	def listItems(task):
		result = screen.items()
		task.items = result
		names = [item["text"] for item in result.items]
		if not names:
			return "Nothing was found in this window."
		shown = "\n".join(f"{i}. {name}" for i, name in enumerate(names[:MAX_ITEMS_SHOWN], 1))
		more = f"\n... and {len(names) - MAX_ITEMS_SHOWN} more." if len(names) > MAX_ITEMS_SHOWN else ""
		return f"{len(names)} items in the window:\n{shown}{more}"

	add("list_items", "list the buttons, texts and icons in the window in front, even when NVDA cannot read it",
		listItems, looks=True, title="Listing what is in the window")

	def clickItem(task, item):
		result = getattr(task, "items", None)
		if result is None or not result.items:
			raise ToolError("Use list_items first.")
		index = match.itemIndex(item, Screen.names(result))
		if index is None:
			index = match.itemIndex(item, [it["text"] for it in result.items])
		if index is None:
			raise ToolError(f"There is no item called \"{item}\". Use a number or a name from list_items.")
		found = result.items[index]
		# Translators: Asked before VisionClaw clicks something. {item} is what will be clicked.
		confirm(_("Click {item}?").format(item=found["text"]))
		onMain(Screen.click, result, found)
		time.sleep(CLICK_SETTLE_SECONDS)
		task.items = None  # the window has probably changed
		return f"Clicked {found['text']}."

	add("click_item", "click one item from list_items in the real window", clickItem,
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
			# Translators: Asked before VisionClaw changes an NVDA setting.
			return found, new, old, _("Change {setting} from {old} to {new}?").format(
				setting=found.label, old=old, new=found.shown(new))
		found, new, old, question = onMain(work)
		confirm(question)
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
		facts = onMain(screen.situation)
		notes = plugin.knowledge.text(purpose, limit=3, chars=700, sources=("addon-development", "objects-and-events"))
		source = microaddons.write(llm, task, purpose, facts, notes, params, CODER, VISION)
		keys = microaddons.gestures(source)
		keyText = " Keys: " + "; ".join(f"{k} ({d})" if d else k for k, d in keys) + "." if keys else ""
		# Translators: Asked before a newly written add-on is turned on.
		question = _("VisionClaw wrote an add-on called {name}. It should: {purpose}.{keys} Turn it on?").format(
			name=name, purpose=purpose, keys=keyText)
		# Translators: Choices when a newly written add-on is ready.
		choices = [_("Turn it on"), _("Let me read the code first"), _("Do not use it")]
		choice = plugin.clawAsk(question, choices)
		if choice == 1:
			wx.CallAfter(ui.browseableMessage, source, name)
			choice = plugin.clawAsk(_("Turn the add-on {name} on?").format(name=name), [choices[0], choices[2]])
			choice = 0 if choice == 0 else 2
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

	registry.add(Tool(ANSWER, "tell the user the result in plain words; always the last step", lambda task: ""))
	return registry
