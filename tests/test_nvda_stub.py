# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Loads the whole add-on against stand-ins for NVDA's modules, without NVDA.

This catches mistakes that only show when the code runs: a missing import, a misspelt name, a tool whose form
does not fit its function. It then drives the real tools: finding and changing settings through NVDA's
configuration, the hotkeys of app helpers, and loading a generated add-on.
It is not a test inside NVDA: the stand-ins accept anything, so what NVDA itself does is not checked here.
"""
import builtins
import importlib
import json
import os
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG_DIR = tempfile.mkdtemp()


class _Meta(type):
	def __getattr__(cls, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return type(name, (Anything,), {})


class Anything(metaclass=_Meta):
	"""A class that has every attribute, can be called and subclassed, and never complains."""

	def __init__(self, *args, **kwargs):
		pass

	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return Anything()

	def __call__(self, *args, **kwargs):
		return Anything()

	def __iter__(self):
		return iter(())

	def __getitem__(self, key):
		return Anything()

	def __or__(self, other):
		return self


class Stub(types.ModuleType):
	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		found = type(name, (Anything,), {})
		setattr(self, name, found)
		return found


def stub(name, **attributes):
	module = Stub(name)
	module.__dict__.update(attributes)
	sys.modules[name] = module
	return module


def defaults(spec):
	"""Values for a configuration section from its specification."""
	import re
	values = {}
	for key, text in spec.items():
		if isinstance(text, dict):
			values[key] = defaults(text)
			continue
		default = re.search(r"default\s*=\s*(\"[^\"]*\"|'[^']*'|[^,)]+)", text)
		raw = default.group(1).strip().strip("\"'") if default else ""
		if text.startswith("boolean"):
			values[key] = raw == "True"
		elif text.startswith("integer"):
			values[key] = int(raw or 0)
		else:
			values[key] = raw
	return values


class Conf(dict):
	"""NVDA's configuration: sections of values, with their specification in .spec."""

	def __init__(self):
		super().__init__()
		self.spec = {
			"speech": {
				"symbolLevel": "integer(default=100)",
				"autoLanguageSwitching": "boolean(default=True)",
				"synth": "string(default=auto)",
				"fake": {"rate": "integer(default=50,min=0,max=100)"},
			},
			"keyboard": {
				"speakTypedCharacters": "boolean(default=True)",
				"speakTypedWords": "boolean(default=False)",
				"keyboardLayout": "string(default=\"desktop\")",
			},
			"mouse": {"enableMouseTracking": "boolean(default=True)"},
			"presentation": {
				"progressBarUpdates": {"progressBarOutputMode": "option(\"off\", \"speak\", \"beep\", \"both\", default=\"beep\")"},
			},
			"update": {"autoCheck": "boolean(default=True)"},
		}

	def __missing__(self, section):
		self[section] = defaults(self.spec[section])
		return self[section]


class DriverSetting:
	def __init__(self, id, displayName, minVal=0, maxVal=100):
		self.id, self.displayName, self.minVal, self.maxVal = id, displayName, minVal, maxVal


class NumericDriverSetting(DriverSetting):
	pass


class BooleanDriverSetting(DriverSetting):
	pass


class Synth:
	name = "fake"
	description = "Fake synthesizer"
	rate, pitch, volume = 50, 40, 100
	rateBoost = False
	voice = "v1"
	availableVoices = {"v1": types.SimpleNamespace(displayName="Anna"), "v2": types.SimpleNamespace(displayName="Ben")}
	supportedSettings = [
		DriverSetting("voice", "Voice"), NumericDriverSetting("rate", "Rate"), BooleanDriverSetting("rateBoost", "Rate boost"),
		NumericDriverSetting("pitch", "Pitch"), NumericDriverSetting("volume", "Volume"),
	]


class GlobalPlugin:
	def __init__(self):
		pass

	def terminate(self):
		pass

	def getScript(self, gesture):
		return None


def script(**kwargs):
	return lambda fn: fn


builtins._ = lambda text: text
log = Anything()
log.isEnabledFor = lambda level: False
stub("addonHandler", initTranslation=lambda: None, getAvailableAddons=lambda: [])
stub("logHandler", log=log)
conf = Conf()
stub("config", conf=conf)
stub("globalVars", appArgs=types.SimpleNamespace(configPath=CONFIG_DIR, secure=False))
running = set()
stub("globalPluginHandler", GlobalPlugin=GlobalPlugin, runningPlugins=running)
stub("scriptHandler", script=script)
synth = Synth()
SYNTHS = [("fake", "Fake synthesizer"), ("espeak", "eSpeak NG"), ("silence", "No speech"), ("broken", "Broken voice")]


def setSynth(name):
	if name == "broken":
		return False  # this one never starts; NVDA keeps the synthesizer it had
	synth.name, synth.description = name, dict(SYNTHS)[name]
	return True


stub("synthDriverHandler", getSynth=lambda: synth, getSynthList=lambda: SYNTHS, setSynth=setSynth)
stub("braille", handler=types.SimpleNamespace(display=types.SimpleNamespace(name="noBraille"), displaySize=0),
	getDisplayList=lambda: [("noBraille", "No braille"), ("freedomScientific", "Freedom Scientific Focus")])
typed = []
os.environ["USERPROFILE"] = CONFIG_DIR  # so that nothing is written to the real Documents folder
stub("wx", IsMainThread=lambda: True, CallAfter=lambda fn, *args: fn(*args), CallLater=lambda ms, fn, *args: None)
stub("inputCore", normalizeGestureIdentifier=lambda ident: ident.lower())
stub("keyboardHandler", KeyboardInputGesture=types.SimpleNamespace(
	fromName=lambda name: (_ for _ in ()).throw(LookupError(name)) if "bogus" in name else Anything()))
for name in (
	"api", "controlTypes", "gui", "gui.guiHelper", "gui.settingsDialogs", "languageHandler", "queueHandler", "speech",
	"speech.extensions", "textInfos", "ui", "contentRecog", "contentRecog.recogUi", "contentRecog.uwpOcr",
	"documentationUtils", "globalCommands", "mouseHandler", "winUser", "NVDAObjects", "core",
	"screenCurtain", "vision", "locationHelper", "winVersion", "tones", "nvwave", "appModuleHandler", "eventHandler",
	"NVDAObjects.UIA", "NVDAObjects.IAccessible", "UIAHandler", "winKernel", "browseMode", "cursorManager",
	"buildVersion", "brailleTables", "textInfos.offsets", "virtualBuffers",
):
	if name not in sys.modules:
		stub(name)
sys.modules["gui"].guiHelper = sys.modules["gui.guiHelper"]
sys.modules["gui"].settingsDialogs = sys.modules["gui.settingsDialogs"]
sys.modules["gui.settingsDialogs"].NVDASettingsDialog = types.SimpleNamespace(categoryClasses=[])
sys.modules["speech"].extensions = sys.modules["speech.extensions"]
sys.modules["contentRecog"].recogUi = sys.modules["contentRecog.recogUi"]

# The real add-on package this time, with its own __init__.
sys.path.insert(0, os.path.join(ROOT, "addon", "globalPlugins"))
plugin = importlib.import_module("visionClaw")
from visionClaw import mousetools, nvdatools, webtools  # noqa: E402
# Nothing really moves the mouse during the tests: every move and button is only written down.
moves, buttons = [], []
mousetools.moveTo = lambda x, y: moves.append((x, y))
mousetools._button = buttons.append
mousetools.position = lambda: (7, 7)
mousetools._SETTLE = mousetools._DRAG_STEP = mousetools._HOLD = 0
# The wheel is not really turned either, and the screen's scaling is a plain 100 percent.
wheels = []
mousetools._wheel = lambda flag, amount: wheels.append((flag, amount))
mousetools._dpi = lambda x, y: 96
mousetools._WHEEL_STEP = mousetools._SCROLL_SETTLE = 0
# No key of the keyboard is really pressed either, and the pointer does not really rest anywhere.
keysPressed = []
mousetools._key = lambda code, up: keysPressed.append((code, up))
mousetools._REST = 0
nvdatools.typeUnicode = typed.append  # nothing is really typed into the computer during the tests
from visionClaw.claw import orchestrator, planner  # noqa: E402
from visionClaw.claw import task as taskModule  # noqa: E402
from visionClaw.claw.catalog import CODER, VISION  # noqa: E402

# --- The plugin starts, and every tool and recipe is in place ---

os.makedirs(os.path.join(CONFIG_DIR, "visionClaw"), exist_ok=True)
with open(os.path.join(CONFIG_DIR, "visionClaw", "lessons.json"), "w", encoding="utf-8") as f:
	json.dump([
		{"text": "Tool find_setting: this form failed: {\"words\": \"restore the voice pitch\"} (No setting matches). "
			"This form worked: {\"words\": \"speech rate\"}.", "topic": "restore the voice pitch", "time": 1.0},
		{"text": "Tool set_setting: this form failed: {} (x). This form worked: {}.", "topic": "x", "time": 2.0},
	], f)
instance = plugin.GlobalPlugin()
registry = instance.orchestrator.registry
assert len(registry.names()) == 63, registry.names()
# Lessons from searches that happened to find something misled; they are dropped when VisionClaw starts.
assert instance.memory.all() == ["Tool set_setting: this form failed: {} (x). This form worked: {}."], instance.memory.all()
assert set(planner.available(registry)) == set(planner.RECIPES), set(planner.RECIPES) - set(planner.available(registry))
for name in registry.names():
	tool = registry.get(name)
	assert tool.before is None or registry.get(tool.before), name
	assert tool.title and tool.description, name
	json.dumps(tool.schema())  # every form is a JSON schema the engine can be given
assert conf["visionClaw"]["backend"] == "auto" and conf["visionClaw"]["confirmChanges"] is True
assert not instance.runtime.hasModel(VISION) and not instance.runtime.hasModel(CODER)
# Which models VisionClaw has and uses is answered by plain code, in its own words, and no model is asked. Here
# none is stored yet.
worked, result = registry.call(taskModule.Task("what model is installed"), "model_info", {})
assert worked and result == (
	"No model is chosen yet for looking at the screen and planning. No model is chosen yet for checking and "
	"writing code. No model is stored on this computer yet. To see, remove or choose other models, press "
	"NVDA+Alt+M."), result
assert registry.get("model_info").tell == "verbatim" and not registry.get("model_info").fields
assert planner.RECIPES["visionclaw_models"][2] == ("model_info",)
assert "the processor" in instance.devicesText() or "(" in instance.devicesText()

# --- Settings: found by plain words, changed with forgiving values, guarded ---

task = taskModule.Task("test")
found = [s.id for s in nvdatools.allSettings()]
assert "speech.rate" in found and "keyboard.speakTypedCharacters" in found and "speech.symbolLevel" in found
assert "presentation.progressBarUpdates.progressBarOutputMode" in found
# Left out on purpose: sections and keys that are not for a model to change.
assert "update.autoCheck" not in found and "speech.synth" not in found and "keyboard.keyboardLayout" not in found
worked, result = registry.call(task, "find_setting", {"words": "Make NVDA speak a little faster"})
assert worked and result.startswith("speech.rate: speech rate. Now: 50. Allowed: a number from 0 to 100."), result
worked, result = registry.call(task, "find_setting", {"words": "turn off the typing echo"})
assert worked and result.startswith("keyboard.speakTypedCharacters"), result
worked, result = registry.call(task, "find_setting", {"words": "set punctuation to all"})
assert worked and "speech.symbolLevel" in result and "one of: none, some, most, all" in result, result
worked, result = registry.call(task, "find_setting", {"words": "zebra unicorn"})
assert not worked and "No setting matches" in result

conf["visionClaw"]["confirmChanges"] = False
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "+10", "asked": ""})
assert worked and synth.rate == 60 and result == "Speech rate was 50 and is now 60.", result
assert conf["speech"]["fake"]["rate"] == 60
worked, result = registry.call(task, "set_setting", {"setting": "speech_rate", "value": "/80", "asked": ""})
assert worked and synth.rate == 80, result  # a near miss of the id and a stray character are forgiven
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "500", "asked": ""})
assert not worked and "outside the allowed range" in result and synth.rate == 80
worked, result = registry.call(task, "set_setting", {"setting": "keyboard.speakTypedCharacters", "value": "off", "asked": ""})
assert worked and conf["keyboard"]["speakTypedCharacters"] is False
worked, result = registry.call(task, "set_setting", {"setting": "speech.symbolLevel", "value": "all", "asked": ""})
assert worked and conf["speech"]["symbolLevel"] == 300 and result.endswith("is now all."), result
# The setting's name instead of its id is understood too.
worked, result = registry.call(task, "set_setting", {"setting": "Keyboard: speak typed characters", "value": "on", "asked": ""})
assert worked and conf["keyboard"]["speakTypedCharacters"] is True, result
registry.call(task, "set_setting", {"setting": "keyboard.speakTypedCharacters", "value": "off", "asked": ""})
worked, result = registry.call(task, "set_setting", {"setting": "nothing.here", "value": "on", "asked": ""})
assert not worked and "Copy an id exactly from find_setting" in result

# Every setting the synthesizer itself offers can be changed, not only rate, pitch and volume.
worked, result = registry.call(task, "find_setting", {"words": "change the voice"})
assert worked and "speech.voice: speech voice. Now: Anna. Allowed: one of: Anna, Ben." in result, result
worked, result = registry.call(task, "set_setting", {"setting": "speech.voice", "value": "ben", "asked": ""})
assert worked and synth.voice == "v2" and conf["speech"]["fake"]["voice"] == "v2", result
worked, result = registry.call(task, "set_setting", {"setting": "speech.rateBoost", "value": "on", "asked": ""})
assert worked and synth.rateBoost is True, result

# What NVDA has and uses: the synthesizer, its voices, the braille display, the drivers.
worked, result = registry.call(task, "nvda_info", {"topic": "speech"})
assert worked and "Speech synthesizer in use: Fake synthesizer (driver name fake)." in result, result
assert "Voice in use: Ben." in result and "Voices of this synthesizer (2): Anna, Ben." in result
assert "Rate: 80." in result and "Synthesizers installed (4): Fake synthesizer, eSpeak NG, No speech, Broken voice." in result
worked, result = registry.call(task, "nvda_info", {"topic": "braille"})
assert worked and "No braille display is in use." in result, result
assert "Braille display drivers installed (2): No braille, Freedom Scientific Focus." in result
worked, result = registry.call(task, "nvda_info", {"topic": "general"})
assert worked and "Keyboard layout: desktop." in result and "Speech synthesizer in use" in result, result
from visionClaw import nvdainfo  # noqa: E402
assert nvdainfo.topicOf("what braille display do I have") == "braille"
assert nvdainfo.topicOf("which voices does my synthesizer have") == "speech"
assert nvdainfo.topicOf("which add-ons are installed") == "addons" and nvdainfo.topicOf("what version is this") == "general"

# --- Only what was asked about is changed, every change is written down, and any change can be put back ---

PITCH = "restore the voice pitch to what it was before you changed it."
# A long sentence that says "pitch" once is about the pitch. It used to match nothing, and the model then
# searched for something else and changed the speech rate.
worked, result = registry.call(task, "find_setting", {"words": PITCH})
assert worked and result.startswith("speech.pitch: speech pitch.") and "speech.rate" not in result, result
# A setting the request says nothing about is not changed, whatever a model decides.
rateBefore = synth.rate
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "45", "asked": PITCH})
assert not worked and "says nothing about speech rate" in result and synth.rate == rateBefore, result
assert "like speech rate" not in registry.call(task, "find_setting", {"words": "zebra unicorn"})[1]  # no examples to copy
# A change that was asked for is written down with what it was before.
instance.changes.pending()
instance.changes._changes = []  # the tests above changed settings too; start this part with an empty record
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "+10", "asked": "speak a bit faster"})
assert worked and synth.rate == rateBefore + 10, result
worked, result = registry.call(task, "set_setting", {"setting": "speech.pitch", "value": "70", "asked": "make the pitch higher"})
assert worked and synth.pitch == 70
newest = instance.changes.pending()[0]
assert newest["setting"] == "speech.pitch" and newest["old"] == 40 and newest["new"] == 70 and newest["request"] == "make the pitch higher"
worked, result = registry.call(task, "list_changes", {})
assert worked and "Speech pitch: from 40 to 70" in result and f"Speech rate: from {rateBefore} to {rateBefore + 10}" in result, result
# "Restore the pitch" puts the pitch back, and leaves the rate alone.
worked, result = registry.call(task, "undo_change", {"what": PITCH})
assert worked and synth.pitch == 40 and synth.rate == rateBefore + 10, result
assert result == "Speech pitch was 70 and is back to 40, as it was before.", result
# Asked again: VisionClaw has not changed the pitch any more, says so, and changes nothing.
worked, result = registry.call(task, "undo_change", {"what": PITCH})
assert worked and result.startswith("VisionClaw has not changed that") and "Speech rate: from" in result
assert synth.rate == rateBefore + 10
# "Undo that" puts back the newest change that still stands.
worked, result = registry.call(task, "undo_change", {"what": "undo that"})
assert worked and synth.rate == rateBefore and instance.changes.pending() == [], result
worked, result = registry.call(task, "undo_change", {"what": "undo that"})
assert worked and result == "VisionClaw has not changed any setting, so there is nothing to put back."

# The user is asked before a change, and saying no changes nothing.
conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "20", "asked": "speak slower"})
assert worked and result == "You said no, so nothing was changed." and synth.rate == 80
assert questions == ["You asked: speak slower. Change speech rate from 80 to 20?"], questions
instance.clawAsk = lambda question, choices: 0
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "20", "asked": ""})
assert worked and synth.rate == 20
conf["visionClaw"]["confirmChanges"] = False

# --- Switching the speech synthesizer: never leave the user without speech and braille ---

from visionClaw.claw import drivers  # noqa: E402
SYNTH = drivers.SYNTH
questions, keeps = [], []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
instance.clawKeep = lambda question, seconds: keeps.append(question) or True
# The user is always asked first, even with questions turned off, and confirms afterwards that it works.
assert conf["visionClaw"]["confirmChanges"] is False
worked, result = registry.call(task, "switch_driver", {"kind": SYNTH, "name": "espeak ng"})
assert worked and synth.name == "espeak" and result == "The synthesizer is now eSpeak NG. Before, it was Fake synthesizer.", result
assert "Switch the synthesizer from Fake synthesizer to eSpeak NG?" in questions[-1] and "switches back" in questions[-1]
assert "This is eSpeak NG. Does it work?" in keeps[-1] and instance.driverNotes.get(SYNTH, "espeak")["worked"] == 1
# Not confirmed in time: switched back, and remembered.
instance.clawKeep = lambda question, seconds: False
worked, result = registry.call(task, "switch_driver", {"kind": SYNTH, "name": "Fake synthesizer"})
assert worked and synth.name == "espeak", result
assert result == "Switched back to eSpeak NG, because Fake synthesizer was not confirmed to work."
# The next time, the user is warned before it is tried again.
instance.clawKeep = lambda question, seconds: True
worked, result = registry.call(task, "switch_driver", {"kind": SYNTH, "name": "Fake synthesizer"})
assert worked and synth.name == "fake", result
assert questions[-1].startswith(
	"Earlier on this computer, Fake synthesizer was switched back once because it was not confirmed to work."), questions[-1]
# A synthesizer that does not start: the old one stays, and that is remembered too.
worked, result = registry.call(task, "switch_driver", {"kind": SYNTH, "name": "Broken voice"})
assert worked and synth.name == "fake", result
assert result == "Broken voice could not be started, so Fake synthesizer is still the synthesizer in use."
assert instance.driverNotes.get(SYNTH, "broken")["failed"] == 1 and instance.memory.search("Broken voice could not be started")
worked, result = registry.call(task, "nvda_info", {"topic": "speech"})
assert "Earlier on this computer, broken could not be started once." in result, result
# "No speech" with no braille display would leave nothing: refused, without even asking.
asked = len(questions)
worked, result = registry.call(task, "switch_driver", {"kind": SYNTH, "name": "No speech"})
assert worked and synth.name == "fake" and len(questions) == asked, result
assert result.startswith("VisionClaw did not do this. That would leave you with no speech and no braille"), result
# With a braille display it is allowed, after a warning.
sys.modules["braille"].handler.display = types.SimpleNamespace(name="freedomScientific", description="Focus 40")
worked, result = registry.call(task, "switch_driver", {"kind": SYNTH, "name": "No speech"})
assert worked and synth.name == "silence" and questions[-1].startswith("This turns speech off completely. You will have braille only.")
# ... and then braille cannot be switched off, because nothing would be left.
sys.modules["braille"].handler.setDisplayByName = lambda name: setattr(sys.modules["braille"].handler.display, "name", name)
worked, result = registry.call(task, "switch_driver", {"kind": drivers.DISPLAY, "name": "No braille"})
assert worked and result.startswith("VisionClaw did not do this. That would leave you with no braille and no speech"), result
assert sys.modules["braille"].handler.display.name == "freedomScientific"
sys.modules["braille"].handler.display = types.SimpleNamespace(name="noBraille")
setSynth("fake")
# The user says no: nothing changes. An unknown name: the installed ones are named.
instance.clawAsk = lambda question, choices: 1
worked, result = registry.call(task, "switch_driver", {"kind": SYNTH, "name": "eSpeak NG"})
assert worked and result == "You said no, so nothing was changed." and synth.name == "fake"
worked, result = registry.call(task, "switch_driver", {"kind": SYNTH, "name": "Zebra Talk"})
assert not worked and "Installed: Fake synthesizer, eSpeak NG" in result
# A volume too quiet to hear, without braille, is refused as well.
worked, result = registry.call(task, "set_setting", {"setting": "speech.volume", "value": "0", "asked": ""})
assert worked and synth.volume == 100 and "too quiet to hear, and there is no braille display" in result, result
instance.clawAsk = lambda question, choices: 0
worked, result = registry.call(task, "set_setting", {"setting": "speech.volume", "value": "40", "asked": ""})
assert worked and synth.volume == 40

# Typing goes through Windows itself: one key down and one key up per character, with the right layout
# of the structure Windows expects (40 bytes on 64-bit Windows, 28 on 32-bit).
import ctypes  # noqa: E402
events = nvdatools.unicodeInputs("a\u00e9\nb")
assert len(events) == 8 and [e.u.ki.wScan for e in events[::2]] == [ord("a"), 0xE9, 13, ord("b")]
assert events[0].u.ki.dwFlags == 0x0004 and events[1].u.ki.dwFlags == 0x0006 and events[0].type == 1
assert ctypes.sizeof(nvdatools._INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
assert len(nvdatools.unicodeInputs("\U0001F600")) == 4  # a character outside the basic plane is two units

# --- Other tools that need no screen ---

worked, result = registry.call(task, "inspect_nvda", {"name": "json.dumps"})
assert worked and "Call it as dumps(" in result, result
worked, result = registry.call(task, "inspect_nvda", {"name": "subprocess.run"})
assert not worked and "not an NVDA module" in result
worked, result = registry.call(task, "inspect_nvda", {"name": "json.nothing"})
assert not worked and "has nothing called nothing" in result
worked, result = registry.call(task, "search_help", {"words": "hotkey for a program that has none"})
assert worked and "App helpers" in result, result
# Memories: the user's own words, kept as a Markdown file with an index, said back with "your", found again.
worked, result = registry.call(task, "remember", {
	"fact": "remember that my braille display is a Focus 40, please", "asked": "remember that my braille display is a Focus 40, please"})
assert worked and result.startswith("VisionClaw will remember this: Your braille display is a Focus 40."), result
assert os.path.isfile(os.path.join(instance.memories.folder, "MEMORY.md"))
assert "Your braille display is a Focus 40." in open(os.path.join(instance.memories.folder, "MEMORY.md"), encoding="utf-8").read()
worked, result = registry.call(task, "remember", {"fact": "my braille display is a Brailliant BI 20", "asked": "x"})
assert "It replaces what it remembered before: Your braille display is a Focus 40." in result, result
assert len(instance.memories.all()) == 1
worked, result = registry.call(task, "memories", {"asked": "what do you remember about me"})
assert worked and "Brailliant" in result, result
assert instance.orchestrator.memories.recall("which braille display do I have") == ["Your braille display is a Brailliant BI 20."]
worked, result = registry.call(task, "library", {"asked": "what is in my library"})
assert worked and "library is empty" in result and os.path.isfile(os.path.join(instance.library.folder, "README.txt")), result
with open(os.path.join(instance.library.folder, "Space Trader manual.txt"), "w", encoding="utf-8") as f:
	f.write("The Play button is called Start. Press Alt+S to start a new game.\n\nSaving is done with Control+S.")
worked, result = registry.call(task, "library", {"asked": "what is in my library"})
assert worked and "1 document: Space Trader manual." in result, result
worked, result = registry.call(task, "search_help", {"words": "start new game"})
assert worked and "From your library" in result and "Alt+S" in result, result
worked, result = registry.call(task, "press_keys", {"keys": "bogusKey"})
assert not worked and "is not a key" in result
worked, result = registry.call(task, "list_helpers", {})
assert worked and "has not made any" in result
assert nvdatools.targetOf("What is on my screen?") == "screen" and nvdatools.targetOf("describe this button") == "control"
assert nvdatools.targetOf("what does this program show") == "window"

# --- A whole request through the real tools, with scripted models ---


class FakeRuntime:
	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False}

	def chat(self, role, messages, maxTokens, **options):
		system = messages[0]["content"]
		if system.startswith("You choose how VisionClaw"):
			return json.dumps({"choice": "change_setting"})
		if system.startswith("You are VisionClaw, an assistant inside the NVDA screen reader, helping"):
			return json.dumps({"setting": "speech.rate", "value": "+10"})
		raise AssertionError(system[:60])


spoken = []
orch = orchestrator.Orchestrator(FakeRuntime(), registry, lambda q, c: 0, lambda: "Program: notepad.", instance.memory)
task = taskModule.Task("Make NVDA speak a little faster", lambda t, kind, text: spoken.append((kind, text)))
orch.run(task)
assert task.state == taskModule.DONE and synth.rate == 30, task.log
assert task.answer == "Speech rate was 20 and is now 30."
assert ("step", "Step 1 of 3: Finding the setting.") in spoken and ("answer", task.answer) in spoken

# --- App helpers: a hotkey that belongs to one program ---

helpers = instance.helpers
assert helpers.keyId("NVDA+alt+1") == "kb:nvda+alt+1" and helpers.keyId("bogus") is None
helpers.add("spacetrader", "NVDA+alt+1", "kb:nvda+alt+1", "click", "New Game")
assert "App helper in spacetrader: NVDA+alt+1 does click \"New Game\"." in helpers.listText()
assert json.load(open(os.path.join(CONFIG_DIR, "visionClaw", "helpers.json")))["spacetrader"]
assert helpers.remove("NVDA+alt+1") and "New Game" not in helpers.listText() and not helpers.remove("NVDA+alt+1")

# --- A generated add-on: checked, loaded into NVDA's running plugins, removed ---

source = (
	"import globalPluginHandler\nimport ui\nfrom scriptHandler import script\n\n\n"
	"class GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\n"
	"\t@script(description=\"Says hello\", gesture=\"kb:NVDA+shift+h\")\n"
	"\tdef script_hello(self, gesture):\n\t\tui.message(\"Hello\")\n"
)
helpers.store.save("Hello Key", source, "say hello on NVDA+shift+h")
loaded = helpers.loadAddon("Hello Key")
assert loaded in running and type(loaded).__name__ == "GlobalPlugin" and hasattr(loaded, "script_hello")
assert "Add-on hello_key (on): say hello on NVDA+shift+h. Keys: NVDA+shift+h." in helpers.listText()
assert helpers.remove("hello_key") and loaded not in running and helpers.store.list() == []
# Code that fails the check is never run.
helpers.store.save("Bad One", "import subprocess\n" + source, "x")
try:
	helpers.loadAddon("Bad One")
	raise AssertionError("code that fails the check must not be loaded")
except ValueError as e:
	assert "subprocess is not allowed" in str(e)
assert not running

# --- An add-on that fails is caught, debugged by the models and corrected, without the user ---

HEADER = (
	"import globalPluginHandler\nimport ui\nfrom scriptHandler import script\n\n\n"
	"class GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\n"
	"\t@script(description=\"Says the focus\", gesture=\"kb:NVDA+shift+j\")\n"
	"\tdef script_sayFocus(self, gesture):\n"
)
FAILING = (
	HEADER + "\t\tui.message(missingName)\n\n"
	"\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message(obj.nme)\n\t\tnextHandler()\n"
)
CORRECTED = (
	HEADER + "\t\tui.message(\"focus\")\n\n"
	"\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message(obj.name)\n\t\tnextHandler()\n"
)
failures = []
instance.onAddonFailed = failures.append
helpers.store.save("Focus Key", FAILING, "say the focus on NVDA+shift+j, and say the name when the focus moves")
loaded = helpers.loadAddon("Focus Key")
# The error does not reach NVDA; it is kept, with the failing line, and the add-on is paused.
assert loaded.script_sayFocus(None) is None and failures == ["focus_key"]
entry = helpers.errors["focus_key"][0]
assert entry["where"] == "script_sayFocus" and entry["error"].startswith("NameError: name 'missingName'"), entry
assert "ui.message(missingName)" in nvdatools.failingLine(entry["trace"]), nvdatools.failingLine(entry["trace"])
# While it is paused, events still reach NVDA and nothing fails again.
passed = []
loaded.event_gainFocus(types.SimpleNamespace(name="OK button"), lambda: passed.append(1))
assert passed == [1] and failures == ["focus_key"] and len(helpers.errors["focus_key"]) == 1
# An event that fails before passing the event on: the guard passes it on, exactly once.
loaded = helpers.loadAddon("Focus Key")
loaded.event_gainFocus(types.SimpleNamespace(name="OK button"), lambda: passed.append(2))
assert passed == [1, 2] and failures == ["focus_key", "focus_key"]
assert helpers.errors["focus_key"][-1]["error"].startswith("AttributeError")
# What NVDA really offers, where the code used something that does not exist.
facts = nvdatools.debugFacts("AttributeError: module 'json' has no attribute 'dump_s'")
assert "json has nothing called dump_s" in facts[0] and "dumps" in facts[0], facts
assert "never imported or defined" in nvdatools.debugFacts("NameError: name 'missingName' is not defined")[0]


class CoderRuntime(FakeRuntime):
	"""A coder model that corrects the add-on, and a reviewer that finds no fault."""
	prompts = []

	def chat(self, role, messages, maxTokens, **options):
		system, user = messages[0]["content"], messages[1]["content"]
		if system.startswith("You write small add-ons"):
			self.prompts.append(user)
			return "```python\n" + CORRECTED + "```"
		if system.startswith("You review a small NVDA"):
			return json.dumps({"ok": True, "problem": ""})
		return super().chat(role, messages, maxTokens, **options)


realRuntime = instance.runtime
instance.runtime = CoderRuntime()
instance._debugAddon("focus_key")
prompt = CoderRuntime.prompts[-1]
assert "script_sayFocus failed with NameError" in prompt and "The failing line is line" in prompt, prompt
assert "event_gainFocus failed with AttributeError" in prompt and "never imported or defined" in prompt
assert helpers.store.source("focus_key") == CORRECTED and helpers.store.meta("focus_key")["repairs"] == 1
loaded = helpers._loaded["focus_key"]
assert loaded in running and "focus_key" not in helpers.errors
loaded.script_sayFocus(None)
loaded.event_gainFocus(types.SimpleNamespace(name="OK button"), lambda: passed.append(3))
assert passed == [1, 2, 3] and failures == ["focus_key", "focus_key"]  # it no longer fails
assert instance.memory.search("NVDA add-on code mistake NameError missingName")
# The user can also ask for a fix in words; what they say goes to the coder.
worked, result = registry.call(taskModule.Task("fix"), "repair_addon", {"name": "focus key", "problem": "It should say the name too."})
assert worked and result == "The add-on focus_key was corrected and is on again.", result
assert "The user says: It should say the name too." in CoderRuntime.prompts[-1]
# After several corrections that did not hold, it is turned off instead of being corrected for ever.
helpers.store.save("Focus Key", FAILING, "say the focus on NVDA+shift+j, and say the name when the focus moves", repairs=3)
loaded = helpers.loadAddon("Focus Key")
loaded.script_sayFocus(None)
instance._debugAddon("focus_key")
assert helpers.store.meta("focus_key")["enabled"] is False and not running, helpers.store.meta("focus_key")
helpers.store.remove("focus_key")
helpers.errors.clear()
instance.runtime = realRuntime

# A generated add-on is saved as a normal add-on file, to install for good or to share.
helpers.store.save("Hello Key", source, "say hello on NVDA+shift+h")
worked, result = registry.call(task, "export_addon", {"name": "hello key"})
saved = os.path.join(CONFIG_DIR, "Documents", "VisionClaw add-ons", "visionClaw_hello_key.nvda-addon")
assert worked and os.path.isfile(saved) and saved in result, result
worked, result = registry.call(task, "export_addon", {"name": "nothing like it"})
assert not worked and "Use a name from list_helpers" in result
helpers.store.remove("hello_key")

# --- The web, through the browser and NVDA's browse mode ---

activated = []


moved = []


def node(label):
	return types.SimpleNamespace(
		label=label, activate=lambda: activated.append(label), moveTo=lambda: moved.append(label),
		report=lambda: moved.append("said " + label))


PAGE = "\n".join(
	["Example Shop", "Welcome to our shop."]
	+ [f"Product number {i} is a fine product that many people like to buy." for i in range(60)]
	+ ["Refund policy", "You can return any product within 30 days for a full refund."]
	+ [f"More about delivery, part {i}, with many words about parcels and vans." for i in range(40)]
)


class Page(sys.modules["browseMode"].BrowseModeDocumentTreeInterceptor):
	isReady = True
	documentConstantIdentifier = "https://example.com/"
	nodes = {
		"link": [node("Home"), node("Sign in"), node("Refund policy")],
		"button": [node("Buy now")],
		"edit": [node("Search the shop")],
		"heading": [node("Example Shop"), node("Refund policy")],
		"heading1": [node("Example Shop")],
		"heading2": [node("Refund policy")],
	}

	def __init__(self):
		self.rootNVDAObject = types.SimpleNamespace(name="Example Shop")

	def _iterNodesByType(self, kind):
		return iter(self.nodes.get(kind, []))

	def makeTextInfo(self, position):
		return types.SimpleNamespace(text=PAGE)


document = Page()
focus = Anything()
focus.treeInterceptor = document
sys.modules["api"].getFocusObject = lambda: focus
nvdatools.CLICK_SETTLE_SECONDS = nvdatools.WEB_SETTLE_SECONDS = 0
nvdatools.WEB_WAIT_SECONDS = 2
task = taskModule.Task("test")

# The page's own links, buttons and fields are listed, what is looked for first.
worked, result = registry.call(task, "list_items", {"about": "sign in to my account"})
assert worked and result.startswith("7 items on the web page Example Shop:\n1. Sign in link"), result
assert "Buy now button" in result and "Search the shop edit field" in result
# Following a link needs no question; pressing a button does.
conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(task, "click_item", {"item": "Sign in", "action": "click", "asked": ""})
assert worked and activated == ["Sign in"] and not questions and result == "Clicked Sign in link.", result
registry.call(task, "list_items", {"about": "buy"})
worked, result = registry.call(task, "click_item", {"item": "the Buy now button", "action": "click", "asked": ""})
assert worked and activated[-1] == "Buy now" and questions == ["Click Buy now button?"], (result, questions)
# A right-click on a web page item goes there and opens its context menu; nothing is followed or pressed.
registry.call(task, "list_items", {"about": "home"})
before = list(activated)
worked, result = registry.call(task, "click_item", {"item": "Home", "action": "right click", "asked": ""})
assert worked and result == "Right-clicked Home link." and activated == before and moved[-2:] == ["Home", "said Home"], result
assert questions[-1] == "Right-click Home link?"
del moved[:]
# Typing into a field: "the search box" finds the page's one field; Enter is pressed when asked.
registry.call(task, "list_items", {"about": "search box"})
worked, result = registry.call(task, "fill_field", {"field": "the search box", "text": "cats", "enter": "yes", "asked": ""})
assert worked and activated[-1] == "Search the shop" and typed == ["cats"], result
assert result == "Typed \"cats\" into Search the shop edit field and pressed Enter.", result
assert questions[-1] == "Type \"cats\" into Search the shop edit field?"
conf["visionClaw"]["confirmChanges"] = False
# How the page is laid out: its headings with their levels, in page order.
worked, result = registry.call(task, "page_outline", {})
assert worked and result.startswith(
	"The web page Example Shop has 2 headings, 3 links, 1 buttons and 1 form fields.\n"
	"Heading level 1: Example Shop\nHeading level 2: Refund policy"), result
# Moving NVDA's reading position to a heading, so the user can read on from there.
registry.call(task, "list_items", {"about": "go to the refund policy section"})
worked, result = registry.call(task, "go_to_item", {"item": "Refund policy heading", "asked": ""})
assert worked and moved == ["Refund policy", "said Refund policy"], (result, moved)
assert result.startswith("NVDA is now at Refund policy heading."), result
assert activated[-1] == "Search the shop"  # moving there follows no link and presses nothing
# Back, forward and reload use the browser's own keys.
sent = []
sys.modules["keyboardHandler"].KeyboardInputGesture = types.SimpleNamespace(
	fromName=lambda name: types.SimpleNamespace(send=lambda: (
		sent.append(name), setattr(document, "documentConstantIdentifier", "https://example.com/" + name))))
worked, result = registry.call(task, "page_navigate", {"direction": "back"})
assert worked and sent == ["alt+leftArrow"] and result == "Went back. The page is now Example Shop.", result
worked, result = registry.call(task, "page_navigate", {"direction": "reload"})
assert worked and sent[-1] == "f5" and result.startswith("Reloaded the page"), result
assert nvdatools.directionOf("go back") == "back" and nvdatools.directionOf("go forward a page") == "forward"
assert nvdatools.directionOf("refresh this page") == "reload"
document.documentConstantIdentifier = "https://example.com/"

# Reading a long page: the beginning and the passage that answers the question, not the whole page.
worked, result = registry.call(task, "read_page", {"about": "What is the refund policy?"})
assert worked and result.startswith("From the web page Example Shop:") and "within 30 days for a full refund" in result
assert len(result) < 1600 and "part 39" not in result
# Opening an address and searching the web go to the user's own browser.
opened = []


def startfile(url):
	opened.append(url)
	document.documentConstantIdentifier = url
	document.rootNVDAObject.name = "BBC Home" if "bbc" in url else "weather in Boston at DuckDuckGo"


webtools.os = types.SimpleNamespace(startfile=startfile)
worked, result = registry.call(task, "web_open", {"address": "bbc.co.uk"})
assert worked and opened == ["https://bbc.co.uk"] and result == "Opened the web page BBC Home.", result
for bad, why in (("javascript:alert(1)", "Only web addresses"), ("the bbc", "is not a web address"), ("", "is not a web address")):
	worked, result = registry.call(task, "web_open", {"address": bad})
	assert not worked and why in result and len(opened) == 1, (bad, result)
worked, result = registry.call(task, "web_search", {"words": "weather in Boston"})
assert worked and opened[-1] == "https://duckduckgo.com/?q=weather+in+Boston" and result == "Searched the web for weather in Boston."
conf["visionClaw"]["searchEngine"] = "bing"
registry.call(task, "web_search", {"words": "weather in Boston"})
assert opened[-1] == "https://www.bing.com/search?q=weather+in+Boston"
# Outside a web page, read_page says so.
sys.modules["api"].getFocusObject = lambda: Anything()
worked, result = registry.call(task, "read_page", {"about": "anything"})
assert not worked and "not in a web page" in result

# --- The models on this computer: listed, removed, swapped ---

from visionClaw import dialogs  # noqa: E402
from visionClaw.claw import catalog  # noqa: E402
real = list(catalog.CATALOG)
try:
	def small(ident, folder, role, name, files):
		return {"id": ident, "dir": folder, "role": role, "name": name, "small": True, "thinking": False,
			"memoryGb": 1, "maxContext": 4096,
			"files": [{"kind": kind, "name": fileName, "size": size, "sha256": "0" * 64, "url": ""} for kind, fileName, size in files]}
	catalog.CATALOG[:] = [
		small("four", "four", VISION, "Qwen3.5 4B", [("model", "four.gguf", 3 * 2 ** 20), ("mmproj", "eyes.gguf", 2 ** 20)]),
		small("coder", "coder", CODER, "Qwen2.5 Coder 1.5B", [("model", "coder.gguf", 2 ** 20)]),
		small("nine-coder", "nine", CODER, "Qwen3.5 9B", [("model", "nine.gguf", 5 * 2 ** 20)]),
	]
	modelsDir = instance.models.modelsDir
	for path, size in (("four/four.gguf", 3), ("four/eyes.gguf", 1), ("coder/coder.gguf", 1), ("nine/nine.gguf", 5)):
		os.makedirs(os.path.dirname(os.path.join(modelsDir, path)), exist_ok=True)
		with open(os.path.join(modelsDir, path), "wb") as f:
			f.write(b"x" * (size * 2 ** 20))
	conf["visionClaw"]["visionModel"], conf["visionClaw"]["coderModel"] = "four", "nine-coder"
	stored, inUse = instance.modelsOnDisk()
	assert [m["key"] for m in stored] == ["four", "coder", "nine"] and inUse == {VISION: "four", CODER: "nine"}
	summary = instance.modelsSummary()
	assert "Qwen3.5 4B, 0.0 GB, in use for vision" in summary and "Qwen3.5 9B, 0.0 GB, in use for coding" in summary, summary
	assert "Qwen2.5 Coder 1.5B, 0.0 GB, not in use" in summary and "3 models," in summary
	assert dialogs.modelsSummary([], {}) == "No models are on this computer yet."
	# The window for managing models can be built and filled.
	manage = dialogs.ManageModelsDialog(None, instance)
	manage.refresh()
	assert [m["key"] for m in manage._models] == ["four", "coder", "nine"]
	# Removing the coder in use: its file is gone, the choice falls back to the coder that is left.
	assert instance.removeModels(["nine"]) == 5 * 2 ** 20
	assert not os.path.exists(os.path.join(modelsDir, "nine")) and conf["visionClaw"]["coderModel"] == ""
	assert instance.modelsOnDisk()[1] == {VISION: "four", CODER: "coder"}
	# After other models were chosen, the user is offered to remove the ones no longer used, and decides.
	asked = []
	sys.modules["gui"].messageBox = lambda question, *args, **kwargs: asked.append(question) or sys.modules["wx"].NO
	instance._offerCleanup(["four"])
	assert "You no longer use: Qwen2.5 Coder 1.5B." in asked[0] and len(instance.modelsOnDisk()[0]) == 2
	sys.modules["gui"].messageBox = lambda question, *args, **kwargs: sys.modules["wx"].YES
	instance._offerCleanup(["four"])
	assert [m["key"] for m in instance.modelsOnDisk()[0]] == ["four"]
	instance._offerCleanup(["four"])  # nothing unused: no question
	# Removing everything: no vision model is left, and VisionClaw knows it.
	assert instance.removeModels(["four"]) == 4 * 2 ** 20
	assert instance.modelsOnDisk() == ([], {}) and not instance._dataReady() and conf["visionClaw"]["visionModel"] == ""
	# Not while a request is being worked on.
	instance.clawTask = taskModule.Task("busy")
	try:
		instance.removeModels(["four"])
		raise AssertionError("models must not be removed while a request runs")
	except RuntimeError as e:
		assert "Stop it first" in str(e)
	instance.clawTask = None
finally:
	catalog.CATALOG[:] = real

# --- The mouse from the keyboard: right-click, double-click, drag, and pointer mode ---

window = types.SimpleNamespace(
	web=False,
	items=[{"text": "File icon", "plain": "File"}, {"text": "Trash icon", "plain": "Trash"}, {"text": "Volume slider", "plain": "Volume"}],
	imageInfo=types.SimpleNamespace(screenLeft=100, screenTop=100, screenWidth=800, screenHeight=600),
)
places = {"File icon": (200, 200), "Trash icon": (500, 400), "Volume slider": (300, 600)}
window.screenPoint = lambda item: places[item["text"]]
conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
task = taskModule.Task("test")
LEFT_DOWN, LEFT_UP, RIGHT_DOWN, RIGHT_UP = 2, 4, 8, 16


def fresh():
	del moves[:], buttons[:]
	task.items = window


fresh()
worked, result = registry.call(task, "click_item", {"item": "the file icon", "action": "right click", "asked": ""})
assert worked and result == "Right-clicked File icon." and questions[-1] == "Right-click File icon?", result
assert moves[0] == (200, 200) and buttons == [RIGHT_DOWN, RIGHT_UP], (moves, buttons)
fresh()
worked, result = registry.call(task, "click_item", {"item": "File", "action": "double click", "asked": ""})
assert worked and result == "Double-clicked File icon." and buttons == [LEFT_DOWN, LEFT_UP, LEFT_DOWN, LEFT_UP]
# Resting the pointer on something asks nothing, presses nothing, and leaves the pointer there. The window is
# looked at before and after, and what appeared is read out: a tip, a menu that opens by itself.
from PIL import Image, ImageDraw  # noqa: E402

plainShot = Image.new("RGB", (800, 600), "white")
tipShot = plainShot.copy()
ImageDraw.Draw(tipShot).rectangle((400, 320, 560, 350), fill="black")
realOcr, mousetools.ocr = mousetools.ocr, types.SimpleNamespace(
	recognize=lambda image: image, rowsText=lambda image: "Empties the trash" if image.convert("L").getextrema()[0] < 50 else "")
conf["visionClaw"]["useOcr"] = True
shots = [plainShot, tipShot]
realGrab, instance._grab = instance._grab, lambda box: shots.pop(0)
fresh()
asked = len(questions)
worked, result = registry.call(task, "click_item", {"item": "Trash", "action": "hover", "asked": ""})
assert worked and result == "The mouse pointer rests on Trash icon. This appeared: Empties the trash", result
assert buttons == [] and moves == [(498, 400), (500, 400)] and len(questions) == asked, moves
# Nothing appeared: that is what is said.
shots = [plainShot, plainShot.copy()]
fresh()
worked, result = registry.call(task, "click_item", {"item": "Trash", "action": "hover", "asked": ""})
assert worked and result == "The mouse pointer rests on Trash icon. Nothing VisionClaw can see appeared.", result
# The window cannot be looked at: nothing is claimed about what appeared.
shots = []
fresh()
worked, result = registry.call(task, "click_item", {"item": "Trash", "action": "hover", "asked": ""})
assert worked and result.endswith("The window could not be looked at, so what appeared is not known."), result

# Press and hold: the button goes down, stays down for as long as the words say, and comes up; the user is
# asked first and told what the window then showed.
shots = [plainShot, tipShot]
fresh()
began = time.time()
worked, result = registry.call(task, "click_item", {
	"item": "?", "action": "press and hold", "asked": "press and hold the File icon for half a second"})
assert worked and result == "Held the mouse button down on File icon for half a second. This appeared: Empties the trash", result
assert time.time() - began >= 0.45 and questions[-1] == "Press and hold File icon for half a second?", questions[-1]
assert buttons == [LEFT_DOWN, LEFT_UP] and moves[0] == (200, 200) and moves[-1] == (7, 7), (buttons, moves)
# Stopped while the button is down: it comes up at once, and never stays down.
shots = [plainShot, plainShot]
fresh()
stopping = taskModule.Task("test")
stopping.items = window
threading.Timer(0.1, stopping.stop).start()
began = time.time()
try:
	registry.call(stopping, "click_item", {"item": "File", "action": "press and hold", "asked": "hold down the File icon for 30 seconds"})
	raise AssertionError("a stopped request must not go on")
except taskModule.Cancelled:
	pass
assert time.time() - began < 5 and buttons == [LEFT_DOWN, LEFT_UP], buttons

# The middle button, and a click with a key held down: the key goes down before the click and comes up after.
fresh()
worked, result = registry.call(task, "click_item", {"item": "File", "action": "middle click", "asked": ""})
assert worked and result == "Clicked with the middle mouse button: File icon." and buttons == [32, 64], (result, buttons)
fresh()
del keysPressed[:]
worked, result = registry.call(task, "click_item", {"item": "?", "action": "click", "asked": "control-click the Trash icon"})
assert worked and result == "Clicked Trash icon with Control held down.", result
assert questions[-1] == "Click Trash icon with Control held down?" and keysPressed == [(0x11, False), (0x11, True)], keysPressed
assert buttons == [LEFT_DOWN, LEFT_UP] and moves[0] == (500, 400)
fresh()
worked, result = registry.call(task, "click_item", {"item": "File", "action": "triple click", "asked": ""})
assert worked and result == "Triple-clicked File icon." and buttons == [LEFT_DOWN, LEFT_UP] * 3, (result, buttons)
# A click at a place on a thing, as on a bar that is clicked where the value should be.
window.items[2]["box"] = (100, 490, 300, 510)
window.imageInfo.convertXToScreen, window.imageInfo.convertYToScreen = (lambda x: x + 100), (lambda y: y + 100)
fresh()
worked, result = registry.call(task, "click_item", {"item": "?", "action": "click", "asked": "click the Volume slider 25 percent across"})
assert worked and result == "Clicked Volume slider, 25 percent across." and moves[0] == (250, 600), (result, moves)
del window.items[2]["box"]

# A gesture: a swipe from the item the words name, a share of the window long, with the button down all the
# way; the user is asked, the pointer is put back, and whether the window changed is said.
shots = [plainShot, tipShot]
fresh()
worked, result = registry.call(task, "draw_gesture", {"asked": "swipe left on the Trash icon"})
assert worked and result == (
	"Drew a swipe to the left on Trash icon, with the mouse button held down. What the window shows changed."), result
assert questions[-1] == "Draw a swipe to the left on Trash icon, with the mouse button held down?", questions[-1]
assert buttons == [LEFT_DOWN, LEFT_UP] and moves[0] == (500, 400) and moves[-2] == (350, 400) and moves[-1] == (7, 7), moves
# With the right button, as mouse gestures in some programs want; nothing changed is said too.
shots = [plainShot, plainShot.copy()]
fresh()
worked, result = registry.call(task, "draw_gesture", {"asked": "draw a circle on the File icon with the right button held down"})
assert worked and result == (
	"Drew a circle, clockwise on File icon, with the right mouse button held down. Nothing VisionClaw can see "
	"changed in the window."), result
assert buttons == [RIGHT_DOWN, RIGHT_UP] and len(moves) > 20
# Words that name no gesture: nothing is drawn.
fresh()
worked, result = registry.call(task, "draw_gesture", {"asked": "do the thing on the Trash icon"})
assert not worked and "does not say which gesture" in result and buttons == [], result

# A click in a rhythm, and a click the moment the thing changes.
instance._grab = lambda box: plainShot
fresh()
worked, result = registry.call(task, "timed_click", {"asked": "click the Trash icon 3 times, every 100 milliseconds"})
assert worked and result.startswith("Clicked Trash icon 3 times, one every 100 milliseconds."), result
assert questions[-1] == "Click Trash icon 3 times, one every 100 milliseconds?" and buttons == [LEFT_DOWN, LEFT_UP] * 3
light, dark = Image.new("L", (96, 96), 255), Image.new("L", (96, 96), 0)
frames = [light] * 8 + [dark]
instance._grab = lambda box: frames.pop(0) if len(frames) > 1 else frames[0]
fresh()
worked, result = registry.call(task, "timed_click", {"asked": "click the Trash icon when it changes"})
assert worked and result.startswith("Trash icon changed after ") and "was clicked at once" in result, result
assert questions[-1] == "Click Trash icon as soon as it changes? VisionClaw watches it for up to 30 seconds."
assert buttons == [LEFT_DOWN, LEFT_UP] and moves[0] == (500, 400) and moves[-1] == (7, 7), (buttons, moves)
# It never changes: nothing is clicked, and that is said.
frames = [light]
fresh()
worked, result = registry.call(task, "timed_click", {"asked": "click the Trash icon when it changes, wait 1 second"})
assert not worked and "Nothing changed at Trash icon in 1 second, so nothing was clicked." in result and buttons == [], result
# It changes all the time: no moment can be told from another, so nothing is clicked.
flicker = [light, dark] * 40
instance._grab = lambda box: flicker.pop(0)
fresh()
worked, result = registry.call(task, "timed_click", {"asked": "click the Trash icon as soon as it lights up"})
assert not worked and "moves or changes all the time" in result and buttons == [], result
# Words that say neither when nor how often: nothing is clicked.
worked, result = registry.call(task, "timed_click", {"asked": "the Trash icon"})
assert not worked and "does not say when to click" in result, result
instance._grab, mousetools.ocr = realGrab, realOcr
# Dragging one item onto another: the button goes down on the first, travels in small steps, and comes up on
# the second. The button never stays down.
fresh()
worked, result = registry.call(task, "drag_item", {"item": "File", "to": "the Trash icon", "asked": ""})
assert worked and result == "Dragged File icon onto Trash icon." and questions[-1] == "Drag File icon onto Trash icon?", result
assert buttons == [LEFT_DOWN, LEFT_UP] and moves[0] == (200, 200) and (500, 400) in moves and len(moves) > 10
assert moves[-1] == (7, 7)  # the pointer is put back afterwards
# Dragging in a direction, as for a slider, stays inside the window.
fresh()
worked, result = registry.call(task, "drag_item", {"item": "Volume slider", "to": "right 100 pixels", "asked": ""})
assert worked and (400, 600) in moves and result == "Dragged Volume slider 100 pixels to the right.", (result, moves[:3])
# The user's own words decide which things are meant, whatever a model wrote in the form.
fresh()
worked, result = registry.call(task, "drag_item", {"item": ", ", "to": "?", "asked": "Drag the file icon onto the trash icon."})
assert worked and result == "Dragged File icon onto Trash icon.", result
fresh()
worked, result = registry.call(task, "drag_item", {"item": "?", "to": "?", "asked": "Drag the volume slider to the left a little"})
assert worked and result == "Dragged Volume slider 64 pixels to the left.", result
fresh()
worked, result = registry.call(task, "click_item", {"item": ", ", "action": "click", "asked": "Click the trash icon"})
assert worked and result == "Clicked Trash icon.", result
assert nvdatools.mentioned("Drag the file icon onto the trash icon", window.items) == ["file", "trash"]
assert nvdatools.mentioned("press the big red button", window.items) == []
assert nvdatools.meant("click something", window.items, "Trash") == "Trash"
fresh()
worked, result = registry.call(task, "drag_item", {"item": "Volume", "to": "the Moon", "asked": ""})
assert not worked and "neither another item" in result and buttons == []
# Saying no drags nothing.
fresh()
instance.clawAsk = lambda question, choices: 1
worked, result = registry.call(task, "drag_item", {"item": "File", "to": "Trash", "asked": ""})
assert worked and result == "You said no, so nothing was changed." and buttons == [] and moves == []
instance.clawAsk = lambda question, choices: 0

# Pointer mode: the arrow keys move the pointer inside the window, and keys click, hold and let go.
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	location=types.SimpleNamespace(left=100, top=100, width=600, height=400), windowHandle=0, name="Game")


def key(name):
	return types.SimpleNamespace(normalizedIdentifiers=[f"kb(desktop):{name}", f"kb:{name}"])


def press(name):
	found = instance.getScript(key(name))
	assert found is not None, name
	found(key(name))


assert instance.getScript(key("rightarrow")) is None  # off: the arrow keys are NVDA's own
del moves[:], buttons[:]
instance.pointerMode.start()
box = instance.pointerMode._box()
cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
assert instance.pointerMode.active and moves == [(cx, cy)], (moves, box)
press("rightarrow")
press("shift+downarrow")
press("control+leftarrow")
assert moves[-3:] == [(cx + 20, cy), (cx + 20, cy + 4), (cx - 80, cy + 4)], moves
# Holding, moving and letting go is a drag done by hand.
press("g")
assert buttons == [LEFT_DOWN] and instance.pointerMode.holding
press("uparrow")
press("g")
assert buttons == [LEFT_DOWN, LEFT_UP] and not instance.pointerMode.holding
# Other keys are left to NVDA; Escape leaves the mode, and lets go of the button if it was held.
assert instance.getScript(key("a")) is None and instance.getScript(key("tab")) is None
press("g")
press("escape")
assert not instance.pointerMode.active and buttons[-1] == LEFT_UP and instance.getScript(key("uparrow")) is None
# Asked for in words, pointer mode is turned on and its keys are told.
worked, result = registry.call(task, "pointer_mode", {})
assert worked and instance.pointerMode.active and "The arrow keys move the mouse pointer" in result, result
instance.pointerMode.stop()

# An app helper can right-click or double-click its item, not only click it.
clicked = []
instance.clawScreen.click = lambda result, item, action="click": clicked.append((item["text"], action))
instance.clawScreen.items = lambda: window
helpers._run({"key": "NVDA+alt+2", "action": "right click", "item": "Trash"})
assert clicked == [("Trash icon", "right click")], clicked

# --- Deep inspection, lasting fixes, and the add-ons installed in NVDA ---

from pagestandin import documentClass, feedPage  # noqa: E402
from visionClaw import accesstools  # noqa: E402
from visionClaw.claw import fixes  # noqa: E402

textInfos = sys.modules["textInfos"]
textInfos.POSITION_ALL, textInfos.POSITION_FIRST, textInfos.POSITION_CARET, textInfos.UNIT_LINE = "all", "first", "caret", "line"
textInfos.offsets = sys.modules["textInfos.offsets"]
textInfos.offsets.Offsets = lambda start, end: types.SimpleNamespace(start=start, end=end)
feed = documentClass(sys.modules["virtualBuffers"].VirtualBuffer)(feedPage(), "https://www.example-feed.com/home", "My feed")
focus = Anything()
focus.treeInterceptor = feed
sys.modules["api"].getFocusObject = lambda: focus
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="My feed - Firefox", appModule=types.SimpleNamespace(appName="firefox"))
accesstools.CHANGE_WAIT_SECONDS = 0
accesstools._drawn = lambda plugin, box: []  # the screen is not read during the tests
task = taskModule.Task("test")

# The inspection reads the page and reports, in the tool's own words, what is in the way and what can be fixed.
assert accesstools.targetOf("inspect this website deeply") == "page" and accesstools.targetOf("check this game") == "window"
assert accesstools.targetOf("what is wrong with this button") == "control" and accesstools.targetOf("fix all of it") == "auto"
assert accesstools.depthOf("do a deep inspection") == "deep" and accesstools.depthOf("make a key that presses Play") == "quick"
worked, result = registry.call(task, "check_access", {"target": "auto", "depth": "deep"})
assert worked and result.startswith("Checked the web page My feed on example-feed.com, in firefox."), result
assert "Found 4 problems." in result and "12 buttons have no name" in result and "feed of 5 posts" in result, result
assert "VisionClaw can fix all of them with an add-on for the website example-feed.com" in result and "[cut]" not in result
assert registry.get("check_access").tell == "verbatim" and registry.get("check_access").looks

# Fixing all of it: the vision model is asked about the nameless buttons that code cannot name, the user is
# told in plain sentences what will be made, and only after a yes is the add-on stored and turned on.
looks = []


class Looker:
	def describe(self, image, prompt, maxTokens, cancel=None):
		looks.append(prompt)
		return "Unknown"


realRuntime, instance.runtime = instance.runtime, Looker()
instance._grab = lambda box: "picture"
accesstools.prepareImage = lambda image, size: b"jpeg"
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(task, "fix_access", {"which": "fix all of it"})
assert worked and result == "You said no, so nothing was changed." and instance.helpers.store.source("fixes_example_feed_com") is None, result
assert questions[0].startswith(
	"VisionClaw can make these fixes for the website example-feed.com, as an add-on that stays until you have it "
	"removed. It works only on the website example-feed.com, in any browser NVDA reads in browse mode."), questions[0]
assert "NVDA+alt+pageDown moves to the next post" in questions[0] and questions[0].endswith("Turn them on?")
instance.clawAsk = lambda question, choices: 0
instance.helpers.add("firefox", "NVDA+alt+1", "kb:nvda+alt+1", "click", "Reload")
worked, result = registry.call(task, "fix_access", {"which": "fix all of it"})
assert worked and result.startswith("Made 8 fixes for the website example-feed.com."), result
assert result.endswith("They are in the add-on fixes_example_feed_com and stay until you ask VisionClaw to remove that add-on.")
stored = instance.helpers.store.source("fixes_example_feed_com")
scope, made = fixes.parse(stored)
assert scope == {"site": "example-feed.com"} and len(made) == 8 and fixes.isFixes(stored)
# NVDA+alt+1 belongs to an app helper already, so the fixes start at NVDA+alt+2.
assert [fix["keys"] for fix in made if fix["kind"] == "press"] == [["NVDA+alt+2"], ["NVDA+alt+3"]], made
loaded = instance.helpers._loaded["fixes_example_feed_com"]
assert loaded in running
assert "Add-on fixes_example_feed_com (on): Accessibility fixes for the website example-feed.com" in instance.helpers.listText()

# The loaded add-on works: the next-post key moves NVDA's reading position to the first post.
feed.caret = 0
getattr(loaded, "script_fix%dnext" % [fix["label"] for fix in made].index("post"))(Anything())
firstPost = next(el for el in feed.root.walk() if el.role.name == "ARTICLE")
assert feed.caret == firstPost.start, (feed.caret, firstPost.start)

# One more fix asked for in words joins the same add-on. The key the user names is used when it is free.
worked, result = registry.call(task, "check_access", {"target": "auto", "depth": "quick"})
assert worked
worked, result = registry.call(task, "add_fix", {"kind": "press", "item": "the Like button", "key": "NVDA+alt+L", "name": "", "asked": ""})
assert worked and "NVDA+alt+L presses Like, wherever you are." in result, result
scope, made = fixes.parse(instance.helpers.store.source("fixes_example_feed_com"))
assert len(made) == 9 and made[-1] == {"kind": "press", "rule": {"role": "BUTTON", "names": ["like"]}, "label": "Like", "keys": ["NVDA+alt+L"]}
# Keys to move between the clickable things; a name for a control by its name on the page; being told of a change.
worked, result = registry.call(task, "add_fix", {"kind": "move", "item": "clickable things", "key": "", "name": "", "asked": ""})
assert worked and "moves to the next clickable item" in result, result
worked, result = registry.call(task, "add_fix", {"kind": "announce", "item": "the inbox count", "key": "", "name": "", "asked": ""})
assert worked and "You are told when inbox count changes." in result, result
worked, result = registry.call(task, "add_fix", {"kind": "read", "item": "the time", "key": "", "name": "", "asked": ""})
assert worked and "reads player time." in result, result
# What cannot be done is refused in words that say why.
worked, result = registry.call(task, "add_fix", {"kind": "press", "item": "the Teleport button", "key": "", "name": "", "asked": ""})
assert not worked and "Nothing called \"the Teleport button\" was found here." in result and "Like" in result, result
worked, result = registry.call(task, "add_fix", {"kind": "read", "item": "Open the menu", "key": "", "name": "", "asked": ""})
assert not worked and "Nothing fixed in the code of the page tells this control apart" in result, result
worked, result = registry.call(task, "add_fix", {"kind": "name", "item": "Mute", "key": "", "name": "", "asked": ""})
assert not worked and "The new name is missing" in result, result
# "Name the focused button Share": the user's words say the focused control is meant, even when the model
# wrote the new name where the control belongs.
closeButton = next(el for el in feed.root.walk() if el.attrs["class"] == "btn btn-close")
closeButton.treeInterceptor = feed
sys.modules["api"].getFocusObject = lambda: closeButton
worked, result = registry.call(task, "add_fix", {
	"kind": "name", "item": "Share", "key": "", "name": "Share", "asked": "Name the focused button Share on this website."})
assert worked and "Buttons without a name are called Share." in result, result
assert {"kind": "name", "rule": {"role": "BUTTON", "cls": ["btn-close"], "tag": ""}, "label": "Share", "keys": []} in [
	dict(fix, rule=dict(fix["rule"], tag=fix["rule"].get("tag", ""))) for fix in fixes.parse(instance.helpers.store.source("fixes_example_feed_com"))[1]]
sys.modules["api"].getFocusObject = lambda: focus
worked, result = registry.call(taskModule.Task("test"), "fix_access", {"which": "all"})
assert not worked and result == "Use check_access first.", result
assert accesstools.kindOf("tell me when the inbox count changes") == "announce" and accesstools.kindOf("call this button Share") == "name"
assert accesstools.kindOf("give this site keys to move between posts") == "move" and accesstools.kindOf("make a key that reads the time") == "read"
assert accesstools.kindOf("make NVDA+alt+P press the Play button") == "press"

# The coder model is never asked to rewrite accessibility fixes: they are data and tested parts, not its code.
worked, result = registry.call(task, "repair_addon", {"name": "fixes_example_feed_com", "problem": "the key does nothing"})
assert not worked and "has no code for the models to correct" in result, result
assert fixes.parse(instance.helpers.store.source("fixes_example_feed_com"))[1][-1]["label"] == "Share"

# "Fix number 3" means the problem that had number 3 in the report the user heard, even when a later look at
# the page counts differently. One inspection serves a whole request.
heardTask = taskModule.Task("test")
registry.call(heardTask, "check_access", {"target": "auto", "depth": "deep"})
first = heardTask.access
registry.call(heardTask, "check_access", {"target": "auto", "depth": "quick"})
assert heardTask.access is first
assert instance.accessHeard[1] == {1: "unnamed", 2: "clickable", 3: "feed", 4: "media"}, instance.accessHeard
laterTask = taskModule.Task("test")
laterTask.steps = [taskModule.Step("Inspecting", "check_access", recipe="fix_access")]
laterTask.current = 0
registry.call(laterTask, "check_access", {"target": "auto", "depth": "deep"})
del laterTask.access.report.findings[0]  # as if the first problem had gone since
for number, finding in enumerate(laterTask.access.report.findings, 1):
	finding.number = number
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 1
registry.call(laterTask, "fix_access", {"which": "fix number 3"})
assert "moves to the next post" in questions[0] and "Play or pause" not in questions[0], questions
instance.clawAsk = lambda question, choices: 0

# A nameless button the code cannot name is named from its picture, and the user is told it is a guess.
instance.runtime = types.SimpleNamespace(describe=lambda image, prompt, maxTokens, cancel=None: "Settings")
lonely = documentClass(sys.modules["virtualBuffers"].VirtualBuffer)(
	__import__("pagestandin").El("DOCUMENT", __import__("pagestandin").El("BUTTON", ident="btn-primary")), "https://lonely.example/", "Lonely")
focus.treeInterceptor = lonely
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
registry.call(task, "check_access", {"target": "page", "depth": "deep"})
worked, result = registry.call(task, "fix_access", {"which": "fix the button without a name"})
assert worked and "Buttons without a name are called Settings. This name is a guess from its picture and can be wrong." in questions[0], (result, questions)
assert fixes.parse(instance.helpers.store.source("fixes_lonely_example"))[1] == [
	{"kind": "name", "rule": {"role": "BUTTON", "ident": "btn-primary"}, "label": "Settings", "keys": [], "guess": True}]
# When no picture can be taken, for example while the screen curtain is on, the task does not break: the
# control stays without a name, and that is said.
def noPicture(box):
	raise RuntimeError("the screen curtain is on")


instance._grab = noPicture
registry.call(task, "remove_helper", {"name": "fixes_lonely_example"})
worked, result = registry.call(task, "fix_access", {"which": "fix the button without a name"})
assert not worked and result.startswith("Nothing could be fixed for this: 1 controls without a name were left as they are"), result
instance._grab = lambda box: "picture"
instance.runtime = realRuntime

# Two websites whose names would become the same folder name each keep their own add-on.
aFix = [{"kind": "press", "rule": {"role": "BUTTON", "names": ["go"]}, "label": "Go", "keys": []}]
for site in ("my-site.com", "my.site.com"):
	place = accesstools.Inspection("page", fixes.scopeOf(site=site), [], None, None, "", None)
	accesstools.install(instance, task, place, [dict(fix) for fix in aFix])
kept = {meta["name"]: fixes.parse(instance.helpers.store.source(meta["name"]))[0] for meta in instance.helpers.store.list()
	if meta["name"].startswith("fixes_my")}
assert sorted(scope["site"] for scope in kept.values()) == ["my-site.com", "my.site.com"] and "fixes_my_site_com" in kept, kept
assert kept["fixes_my_site_com"] == {"site": "my-site.com"}
for name in kept:
	registry.call(task, "remove_helper", {"name": name})

# Removing the add-on removes the fixes; nothing of them is left running.
conf["visionClaw"]["confirmChanges"] = False
worked, result = registry.call(task, "remove_helper", {"name": "fixes_example_feed_com"})
assert worked and loaded not in running and instance.helpers.store.source("fixes_example_feed_com") is None, result
assert instance.helpers.remove("NVDA+alt+1")

# The add-ons installed in NVDA: which there are, and what one of them is, has and says about itself.
addonDir = tempfile.mkdtemp()
os.makedirs(os.path.join(addonDir, "doc", "en"))
os.makedirs(os.path.join(addonDir, "globalPlugins"))
with open(os.path.join(addonDir, "doc", "en", "readme.html"), "w", encoding="utf-8") as f:
	f.write("<html><h1>Clock</h1><p>Press NVDA+F12 twice to hear the date.</p><h2>Alarms</h2><p>Alarms ring at the time you set.</p></html>")
clock = types.SimpleNamespace(
	name="clock", path=addonDir, isDisabled=False, isRunning=True,
	manifest={"summary": "Clock and calendar", "version": "2.1", "author": "Someone", "description": "Speaks the time in many ways."},
	getDocFilePath=lambda: os.path.join(addonDir, "doc", "en", "readme.html"))
sys.modules["addonHandler"].getAvailableAddons = lambda: [clock]
sys.modules["addonHandler"].getRunningAddons = lambda: [clock]
worked, result = registry.call(task, "addon_info", {"addon": "clock", "about": "how do I hear the date"})
assert worked and result.startswith("The add-on Clock and calendar, version 2.1, by Someone, is on."), result
assert "Press NVDA+F12 twice to hear the date." in result and "Speaks the time in many ways." not in result, result
# The user's own words decide which add-on is meant, whatever a model wrote as its name.
worked, result = registry.call(task, "addon_info", {"addon": "all", "about": "What does the Clock add-on do?"})
assert worked and "It says about itself: Speaks the time in many ways." in result, result
assert "It has commands that work everywhere." in result and registry.get("addon_info").tell == "verbatim", result
worked, result = registry.call(task, "addon_info", {"addon": "all", "about": "which add-ons do I have"})
assert worked and result == "Add-ons installed (1): Clock and calendar 2.1 (enabled).", result
worked, result = registry.call(task, "addon_info", {"addon": "teleporter", "about": "what does it do"})
assert not worked and "No installed add-on is called \"teleporter\"" in result, result
# The help texts of the add-ons that are on can be read up on like NVDA's own user guide.
assert any("Alarms ring at the time you set." in body for _title, body, source in accesstools.addonSections() if source == "addons")

# --- Scrolling with the mouse wheel ---

from PIL import Image, ImageDraw  # noqa: E402


def shot(offset, bar=None):
	"""A picture of a window whose lines stand at an offset, with a scrollbar at a share of its way down."""
	image = Image.new("L", (800, 600), 255)
	draw = ImageDraw.Draw(image)
	for row in range(40):
		y = 20 + row * 30 - offset
		if 0 <= y < 580:
			draw.rectangle((20, y, 200 + (row * 37) % 400, y + 10), fill=20)
	if bar is not None:
		draw.rectangle((783, 0, 799, 599), fill=240)
		top = round((600 - 150) * bar)
		draw.rectangle((784, top, 798, top + 150), fill=150)
	return image


WHEEL, HWHEEL = 0x0800, 0x1000
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="Notes", appModule=types.SimpleNamespace(appName="notes"),
	location=types.SimpleNamespace(left=0, top=0, width=800, height=600))
sys.modules["api"].getFocusObject = lambda: types.SimpleNamespace(location=None)
under = types.SimpleNamespace(role=types.SimpleNamespace(name="PANE"))
sys.modules["api"].getDesktopObject = lambda: types.SimpleNamespace(objectFromPoint=lambda x, y: under)
conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
task = taskModule.Task("test")
# Three notches down, in the middle of the window; the picture moved, and the scrollbar says how far it stands.
pictures = [shot(0, 0.0), shot(90, 0.3)]
instance._grab = lambda box: pictures.pop(0)
del wheels[:], moves[:]
worked, result = registry.call(task, "scroll_view", {"direction": "down", "asked": "scroll down"})
assert worked and result == "Scrolled down 3 notches of the wheel in the window Notes. It now stands 30 percent down.", result
assert wheels == [(WHEEL, -120)] * 3 and moves[0] == (400, 300) and moves[-1] == (7, 7), (wheels, moves)
assert questions == ["Scroll down 3 notches of the wheel in the window Notes?"], questions
# At the end nothing moves, and that is what is said. Nothing is claimed that did not happen.
pictures = [shot(300, 1.0), shot(300, 1.0)]
worked, result = registry.call(task, "scroll_view", {"direction": "down", "asked": "scroll down a page"})
assert worked and result.startswith("Nothing moved in the window Notes. It is already as far down as it goes"), result
# To the end: a page at a time until nothing moves any more.
pictures = [shot(0, 0.0), shot(240, 0.4), shot(480, 0.8), shot(600, 1.0), shot(600, 1.0)]
del wheels[:]
worked, result = registry.call(task, "scroll_view", {"direction": "down", "asked": "scroll to the bottom"})
assert worked and result == "Scrolled down in the window Notes until nothing moved any more. It now stands at the bottom.", result
assert len(wheels) == 4 * 8 and not pictures
# Sideways uses the other wheel; up turns it the other way.
pictures = [shot(0), shot(60)]
del wheels[:]
worked, result = registry.call(task, "scroll_view", {"direction": "right", "asked": "scroll right a little"})
assert worked and wheels == [(HWHEEL, 120)] and result == "Scrolled right 1 notches of the wheel in the window Notes.", (result, wheels)
# Larger and smaller: the wheel with the Control key held down, which comes up again; a little at a time.
pictures = [shot(0), shot(60)]
del wheels[:], keysPressed[:]
worked, result = registry.call(task, "scroll_view", {"direction": "down", "asked": "zoom in"})
assert worked and result == "Made what the window Notes shows larger, with the Control key and 2 notches of the mouse wheel.", result
assert wheels == [(WHEEL, 120)] * 2 and keysPressed == [(0x11, False), (0x11, True)], (wheels, keysPressed)
assert questions[-1] == "Make what the window Notes shows larger, with the Control key and the mouse wheel?", questions[-1]
pictures = [shot(0), shot(0)]
del wheels[:], keysPressed[:]
worked, result = registry.call(task, "scroll_view", {"direction": "down", "asked": "zoom out"})
assert worked and result.startswith("Nothing VisionClaw can see changed in the window Notes."), result
assert wheels == [(WHEEL, -120)] * 2 and keysPressed == [(0x11, False), (0x11, True)], (wheels, keysPressed)
# The user says no: the wheel is not turned.
instance.clawAsk = lambda question, choices: 1
pictures = [shot(0), shot(60)]
del wheels[:]
worked, result = registry.call(task, "scroll_view", {"direction": "down", "asked": "scroll down"})
assert worked and result == "You said no, so nothing was changed." and wheels == [], result
instance.clawAsk = lambda question, choices: 0
# Over a slider or a combo box the wheel would change a value, so nothing is scrolled there.
under.role.name = "SLIDER"
worked, result = registry.call(task, "scroll_view", {"direction": "down", "asked": "scroll down"})
assert not worked and "whose value the wheel changes" in result and wheels == [], result
under.role.name = "PANE"
conf["visionClaw"]["confirmChanges"] = False

# In pointer mode Page Down turns the wheel where the pointer is and says where the view then stands; at the
# end it says so; S puts the pointer on the scrollbar.
said = []
sys.modules["ui"].message = said.append


def settle(count):
	for _ in range(200):
		if len(said) >= count:
			return
		time.sleep(0.01)
	raise AssertionError(said)


instance.pointerMode.start()
del said[:], wheels[:]
pictures = [shot(0, 0.0), shot(240, 0.5)]
press("pagedown")
settle(1)
assert said == ["50 percent down"] and wheels == [(WHEEL, -120)] * 8, (said, wheels)
pictures = [shot(600, 1.0), shot(600, 1.0)]
press("shift+pagedown")
settle(2)
assert said[-1] == "Nothing moved. This is the end, or nothing scrolls under the pointer." and len(wheels) == 9
pictures = [shot(0, 0.5)]
press("s")
settle(3)
assert said[-1].startswith("A scrollbar at the right, 50 percent down, showing 25 percent of the whole at a time. The pointer is on it"), said[-1]
assert (instance.pointerMode.x, instance.pointerMode.y) == (791, 300), (instance.pointerMode.x, instance.pointerMode.y)
pictures = [shot(0)]
press("s")
settle(4)
assert said[-1].startswith("No scrollbar was found in this window's picture.")
# T rests the pointer where it is and says what appeared.
realOcr, mousetools.ocr = mousetools.ocr, types.SimpleNamespace(
	recognize=lambda image: image, rowsText=lambda image: "Empties the trash" if image.convert("L").getextrema()[0] < 50 else "")
pictures = [plainShot, tipShot]
press("t")
settle(5)
assert said[-1] == "Empties the trash", said[-1]
pictures = [plainShot, plainShot.copy()]
press("t")
settle(6)
assert said[-1] == "Nothing appeared.", said[-1]
# C watches what is under the pointer and clicks the moment it changes; Shift+C only says so, with a tone.
frames = [light] * 8 + [dark]
instance._grab = lambda box: frames.pop(0) if len(frames) > 1 else frames[0]
del buttons[:]
press("c")
settle(8)
assert said[-2] == "Watching what is here. Any key of pointer mode stops it." and said[-1] == "It changed, and was clicked.", said[-2:]
assert buttons == [LEFT_DOWN, LEFT_UP], buttons
frames = [light] * 8 + [dark]
del buttons[:]
press("shift+c")
settle(10)
assert said[-1] == "It changed." and buttons == [], (said[-1], buttons)
# Any key ends a watch, and does nothing else.
frames = [light]
press("c")
time.sleep(0.3)
at = (instance.pointerMode.x, instance.pointerMode.y)
press("rightarrow")
settle(12)
assert said[-1] == "Stopped watching." and buttons == [] and (instance.pointerMode.x, instance.pointerMode.y) == at, said[-1]
instance.pointerMode.stop()
# A hotkey that rests the pointer on its item and says what appeared, found by name each time.
instance.clawScreen.items = lambda: window
pictures = [plainShot, tipShot]
instance._grab = lambda box: pictures.pop(0)
del moves[:], buttons[:]
helpers._run({"key": "NVDA+alt+4", "action": "hover", "item": "Trash"}, "notes", "kb:nvda+alt+4")
assert said[-1] == "Empties the trash" and moves[-1] == (500, 400) and buttons == [], (said[-1], moves)
helpers._run({"key": "NVDA+alt+4", "action": "hover", "item": "Moon"}, "notes", "kb:nvda+alt+4")
assert said[-1] == "Moon is not in this window right now.", said[-1]
mousetools.ocr = realOcr
sys.modules["ui"].message = lambda text: None

# The inspection of a window says what its picture shows of scrollbars, and what the vision model sees.
pictures = [shot(0, 0.5)] * 3
instance._grab = lambda box: pictures[0]
realRuntime, instance.runtime = instance.runtime, types.SimpleNamespace(
	describe=lambda image, prompt, maxTokens, cancel=None: "A volume slider at the top right.")
worked, result = registry.call(taskModule.Task("test"), "check_access", {"target": "window", "depth": "deep"})
assert worked and "Its picture shows a scrollbar at the right, 50 percent down" in result, result
assert "The vision model, which can be wrong, sees these things that are worked with the mouse: A volume slider at the top right." in result
assert "Page Down and Page Up turn the mouse wheel" in result, result
instance.runtime = realRuntime

# --- A newer version of VisionClaw itself ---

from visionClaw import net, updater  # noqa: E402

BASE = "https://github.com/joshknnd1982/visionclaw/releases/download"


def published(version):
	name = f"VisionClaw-{version}.nvda-addon"
	return {"tag_name": f"v{version}", "prerelease": True, "draft": False, "body": "* Scrolling is smoother.", "assets": [
		{"name": name, "size": 3000000, "digest": "sha256:" + "5" * 64, "browser_download_url": f"{BASE}/v{version}/{name}"}]}


fetched, downloaded, opened, boxes, said = [], [], [], [], []
onGitHub = [published("0.8.0")]
net.fetchJson = lambda url, timeout=20, limit=None: fetched.append(url) or list(onGitHub)


def fakeDownload(url, dest, size=None, sha256=None, onProgress=None, cancel=None):
	downloaded.append((url, size, sha256))
	with open(dest, "wb") as f:
		f.write(b"add-on")
	return dest


net.download = fakeDownload
updater._openInstaller = opened.append
updater.currentVersion = lambda: "0.8.0"
sys.modules["ui"].message = said.append
updater.gui.messageBox = lambda text, *args, **kwargs: boxes.append(text) or sys.modules["wx"].YES
# The window that says what is new and asks whether to download: what it would show is written down.
offers, wanted = [], [True]
updater.askDownload = lambda found, current: offers.append(updater.updates.offerText(found, current)) or wanted[0]
task = taskModule.Task("test")
assert conf["visionClaw"]["updateCheck"] == "manual" and conf["visionClaw"]["updateLastCheck"] == ""
# Asked in words: the user is asked before anything goes online. No means nothing goes online.
instance.clawAsk = lambda question, choices: questions.append(question) or 1
questions = []
worked, result = registry.call(task, "check_update", {})
assert worked and result == "You said no, so VisionClaw did not go online." and fetched == [], result
assert questions[0].startswith("VisionClaw will go online once, to its own page on GitHub"), questions
# Yes, and the version in use is the newest: that is said, and nothing is downloaded.
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(task, "check_update", {})
assert worked and result == "You have the newest version of VisionClaw, 0.8.0." and downloaded == [], result
assert fetched == ["https://api.github.com/repos/joshknnd1982/visionclaw/releases?per_page=20"]
assert float(conf["visionClaw"]["updateLastCheck"]) > 0
# A newer one is there: it is offered with what is new, and "not now" downloads nothing.
onGitHub.append(published("0.9.0"))
wanted[0] = False
worked, result = registry.call(task, "check_update", {})
# What is new is shown in a box of its own, one point to a line, with the choice as buttons.
assert offers[-1].splitlines()[:6] == [
	"VisionClaw 0.9.0 is available. You have 0.8.0.", "It is a download of 3 MB.", "",
	"What is new in VisionClaw 0.9.0:", "Scrolling is smoother.", ""], offers
assert len(questions) == 3 and "Download it now" not in questions[-1], questions  # only asked before going online
assert worked and result.startswith("VisionClaw 0.9.0 is available. You have 0.8.0. It is a download of 3 MB. What is new: "
	"Scrolling is smoother. You said not now, so nothing was downloaded."), result
assert downloaded == [] and opened == []
# Yes: the release's own file is downloaded with its size and checksum, and handed to NVDA to install.
instance.clawAsk = lambda question, choices: 0
wanted[0] = True
worked, result = registry.call(task, "check_update", {})
assert worked and result.startswith("VisionClaw 0.9.0 was downloaded and checked. NVDA now asks whether to install it"), result
assert downloaded == [(f"{BASE}/v0.9.0/VisionClaw-0.9.0.nvda-addon", 3000000, "5" * 64)], downloaded
assert len(opened) == 1 and opened[0].endswith(os.path.join("updates", "VisionClaw-0.9.0.nvda-addon")) and os.path.isfile(opened[0])
# Windows cannot open the file: the user is told where it is.
updater._openInstaller = lambda path: (_ for _ in ()).throw(OSError("no program"))
worked, result = registry.call(task, "check_update", {})
assert worked and "but Windows could not open it. The file is " in result, result
updater._openInstaller = opened.append
# The page cannot be reached: the step fails with the reason, and nothing is changed.
net.fetchJson = lambda url, timeout=20, limit=None: (_ for _ in ()).throw(OSError("no connection"))
worked, result = registry.call(task, "check_update", {})
assert not worked and result == "The list of versions could not be read: no connection", result
net.fetchJson = lambda url, timeout=20, limit=None: fetched.append(url) or list(onGitHub)


def idle():
	for _ in range(300):
		if not instance.updater._busy:
			return
		time.sleep(0.01)
	raise AssertionError("the updater did not finish")


# With the key (NVDA+Alt+U) or the button: a window says that a newer version is there and asks before the
# download; yes downloads it and hands it to NVDA.
del downloaded[:], opened[:], boxes[:], said[:], offers[:]
instance.updater.check()
idle()
time.sleep(0.05)
idle()
assert said[0] == "Looking for a newer version of VisionClaw." and "Downloading VisionClaw 0.9.0." in said, said
assert boxes == [] and offers[0].startswith("VisionClaw 0.9.0 is available. You have 0.8.0.\nIt is a download of 3 MB."), (boxes, offers)
assert "\nWhat is new in VisionClaw 0.9.0:\nScrolling is smoother.\n" in offers[0], offers
# The window itself: a read-only box that holds all of it, and the two choices as buttons.
shown = updater.UpdateDialog(None, offers[0])
assert isinstance(shown, updater.wx.Dialog) and shown.textCtrl is not None
assert len(downloaded) == 1 and len(opened) == 1 and said[-1].startswith("VisionClaw 0.9.0 was downloaded and checked."), said
# No: nothing is downloaded.
wanted[0] = False
del downloaded[:], opened[:]
instance.updater.check()
idle()
assert downloaded == [] and opened == []
# With the newest version in use, the window says so.
updater.currentVersion = lambda: "0.9.0"
del boxes[:]
instance.updater.check()
idle()
assert boxes == ["You have the newest version of VisionClaw, 0.9.0."], boxes
# By itself after NVDA has started: only with the automatic choice, and then one spoken sentence, no window,
# and no download. With "only when I ask" nothing is even scheduled.
timers = []
sys.modules["wx"].CallLater = lambda ms, fn, *args: timers.append((ms, fn, args))
conf["visionClaw"]["updateLastCheck"] = ""
instance.updater.startLater()
assert timers == []
conf["visionClaw"]["updateCheck"] = "auto"
instance.updater.startLater()
assert len(timers) == 1 and timers[0][0] == updater.START_DELAY_MS and timers[0][2] == (False,)
instance.updater.startLater()  # the list was not read yet, so it is still due
assert len(timers) == 2
updater.currentVersion = lambda: "0.8.0"
del boxes[:], said[:], downloaded[:], fetched[:]
timers[0][1](*timers[0][2])
idle()
assert said == ["VisionClaw 0.9.0 is available. Press NVDA+Alt+U to get it."] and boxes == [] and downloaded == [], (said, boxes)
assert len(fetched) == 1
del timers[:]
instance.updater.startLater()  # read a moment ago: not again today
assert timers == []
# Nothing newer, found by itself: nothing is said at all.
updater.currentVersion = lambda: "0.9.0"
del said[:]
instance.updater.check(False)
idle()
assert said == [] and boxes == []
conf["visionClaw"]["updateCheck"] = "manual"
sys.modules["ui"].message = lambda text: None
sys.modules["wx"].CallLater = lambda ms, fn, *args: None

# What looking for newer models found is said in plain sentences.
from visionClaw import dialogs  # noqa: E402

assert dialogs.lookResult({"new": ["Qwen9 1B", "Qwen9 Coder 1B"], "tooNew": 1, "refused": 2, "updated": "2027-03-01"}) == (
	"2 models were added to the lists: Qwen9 1B, Qwen9 Coder 1B. The list was last brought up to date on 2027-03-01. "
	"1 newer models need a newer version of VisionClaw and are not offered here. "
	"2 entries of the list were left out, because they did not pass VisionClaw's checks.")
assert dialogs.lookResult({"new": [], "tooNew": 0, "refused": 0, "updated": ""}) == (
	"There are no newer models. The lists here already offer every model on VisionClaw's list.")
# In the lists of the models window, the very smallest models say what they are, so that it is heard while
# moving through the list; the others, and the suggested one, are worded as before.
# Each model is said with what each of its quants would download.
shelf = types.SimpleNamespace(entries=catalog.Catalog("nowhere").entries, isInstalled=lambda entry: False,
	missingBytes=lambda entry: 703 * 2 ** 20)
labelOf = lambda ident, suggested=None: dialogs.modelLabel(shelf, catalog.Catalog("nowhere").get(ident), suggested)  # noqa: E731
assert labelOf("qwen3.5-0.8b") == (
	"Qwen3.5 0.8B, Q4_K_M 703 MB to download, Q6_K 703 MB to download, very small: fast, less accurate"), labelOf("qwen3.5-0.8b")
assert labelOf("qwen2.5-coder-0.5b").endswith(", very small: fast, less accurate")
assert labelOf("qwen3.5-2b", "qwen3.5-2b") == "Qwen3.5 2B, Q4_K_M 703 MB to download, Q6_K 703 MB to download, suggested"
assert labelOf("qwen3.5-9b") == "Qwen3.5 9B, Q4_K_M 703 MB to download, Q6_K 703 MB to download"
assert labelOf("qwen3.5-9b-q6k", "qwen3.5-9b-q6k").endswith(", suggested")

# --- Arrow keys for a control that is dragged: a dial, a slider, a value Windows offers ---

import math  # noqa: E402

from visionClaw import controlkeys, deepquery  # noqa: E402
from visionClaw.claw import dragcontrol  # noqa: E402

# A stand-in program: a window 800 by 600 with one control at a place. A knob takes drags up and down; a
# slider's thumb goes along with the mouse sideways. Neither takes the wheel. Nothing real is moved.
world = types.SimpleNamespace(kind="knob", handle=(400, 300), level=50, thumb=200, down=False, at=(7, 7))


def worldMove(x, y):
	if world.down:
		if world.kind == "knob":
			world.level = max(0, min(100, world.level + world.at[1] - y))
		else:
			world.thumb = max(100, min(700, world.thumb + x - world.at[0]))
	world.at = (x, y)
	moves.append((x, y))


def worldButton(flag):
	buttons.append(flag)
	if flag != LEFT_DOWN:
		world.down = False
	elif world.kind == "knob":
		world.down = math.hypot(world.at[0] - world.handle[0], world.at[1] - world.handle[1]) <= 24
	else:
		world.down = abs(world.at[0] - world.thumb) <= 10 and abs(world.at[1] - world.handle[1]) <= 10


def scene(box):
	image = Image.new("L", (800, 600), 230)
	draw = ImageDraw.Draw(image)
	x, y = world.handle
	if world.kind == "knob":
		draw.ellipse((x - 24, y - 24, x + 24, y + 24), fill=90)
		angle = world.level / 100 * 4 - 2
		draw.line((x, y, x + 20 * math.sin(angle), y - 20 * math.cos(angle)), fill=250, width=5)
	else:
		draw.rectangle((100, y - 2, 700, y + 2), fill=120)
		draw.rectangle((world.thumb - 8, y - 10, world.thumb + 8, y + 10), fill=40)
	return image.crop(box)


def idle():
	for _ in range(600):
		if not instance.controlKeys.busy():
			return
		time.sleep(0.01)
	raise AssertionError("still at work")


mousetools.moveTo, mousetools._button, mousetools.position = worldMove, worldButton, lambda: world.at
controlkeys._LOOK_SETTLE = 0
controlkeys.ocr = types.SimpleNamespace(recognize=lambda image: None, rowsText=lambda lines: f"Gain\n{world.level} dB")
instance._grab = scene
said = []
sys.modules["ui"].message = said.append
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="Mixer", appModule=types.SimpleNamespace(appName="mixer"),
	location=types.SimpleNamespace(left=0, top=0, width=800, height=600), windowHandle=0)
sys.modules["api"].getFocusObject = lambda: types.SimpleNamespace(location=None, treeInterceptor=None)
conf["visionClaw"]["confirmChanges"] = True
conf["visionClaw"]["useOcr"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
task = taskModule.Task("test")
keys = instance.controlKeys
assert instance.getScript(key("uparrow")) is None and "work_control" in planner.RECIPES["work_control"][2]

# Asked for in words, with the pointer put on the dial in pointer mode: VisionClaw asks, finds out by trying
# that the dial is dragged up and down (the wheel did nothing), puts it back, and the arrow keys take over.
instance.pointerMode.start()
instance.pointerMode.x, instance.pointerMode.y = 400, 300
del wheels[:]
worked, result = registry.call(task, "work_control", {"item": "", "asked": "let the arrow keys work the dial under the mouse pointer"})
assert worked and result.startswith("The arrow keys now work this dial, by dragging it up and down."), result
assert result.endswith("To keep this for next time, press K now."), result
assert questions[-1].startswith("Let the arrow keys work what is at the mouse pointer? To find out how it is worked"), questions
assert world.level == 50 and len(wheels) == 1 and not world.down and buttons[-1] == LEFT_UP, (world, wheels)
assert keys.active and not instance.pointerMode.active and keys.control["method"] == dragcontrol.UPDOWN
assert keys.control["follows"] is False and keys.control["share"] == (0.5, 0.5), keys.control
idle()
# Up turns it up, and what is said is the text at the dial that changed.
press("uparrow")
idle()
assert world.level == 58 and said[-1] == "58 dB", (world.level, said[-3:])
press("shift+downarrow")
idle()
assert world.level == 56 and said[-1] == "56 dB", (world.level, said[-3:])
# End goes on until nothing moves any more, and then the next press says that nothing moved.
press("end")
idle()
assert world.level == 100 and said[-1] == "At the end. 100 dB", (world.level, said[-3:])
press("uparrow")
idle()
assert said[-1].startswith("Nothing moved. It may be at its end"), said[-1]
press("r")
idle()
assert said[-1] == "Gain 100 dB", said[-1]
# K keeps it under a hotkey for this program, as data: a place as a share of the window, and the way.
press("k")
assert said[-1].startswith("Kept. In mixer, NVDA+alt+") and "takes hold of this dial" in said[-1], said[-1]
kept = list(instance.helpers._bindings["mixer"].values())[0]
assert kept["action"] == "work" and kept["method"] == dragcontrol.UPDOWN and kept["share"] == [0.5, 0.5] and kept["find"] is None, kept
assert "takes hold of a dial, so the arrow keys work it by dragging it up and down" in instance.helpers.listText()
# Escape gives the arrow keys back.
press("escape")
assert not keys.active and said[-1] == "The arrow keys are yours again." and instance.getScript(key("uparrow")) is None
# The hotkey takes hold of it again, without trying anything: how it is worked is remembered.
world.level = 20
del wheels[:], buttons[:]
press(kept["key"].lower())
for _ in range(300):
	if keys.active:
		break
	time.sleep(0.01)
idle()
assert keys.active and wheels == [] and buttons == [] and said[-1].startswith("The arrow keys now work this dial"), said[-1]
press("control+uparrow")
idle()
assert world.level == 52 and said[-1] == "52 dB", (world.level, said[-2:])
# In another program the hotkey is not VisionClaw's.
press("escape")
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="Other", appModule=types.SimpleNamespace(appName="other"),
	location=types.SimpleNamespace(left=0, top=0, width=800, height=600), windowHandle=0)
assert instance.getScript(key(kept["key"].lower())) is None
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="Mixer", appModule=types.SimpleNamespace(appName="mixer"),
	location=types.SimpleNamespace(left=0, top=0, width=800, height=600), windowHandle=0)
assert instance.helpers.remove(kept["key"])

# A slider whose thumb goes along with the mouse: dragging sideways is found, and the place that is held
# moves with the thumb, so the next press takes hold of it where it now is.
world.kind, world.thumb = "slider", 200
controlkeys.ocr = types.SimpleNamespace(recognize=lambda image: None, rowsText=lambda lines: "Balance")
box = keys._box()
taken, text = keys.start(controlkeys.newControl("Balance", "slider", (200, 300), box))
assert taken and text.startswith("The arrow keys now work Balance, a slider, by dragging it sideways."), text
assert world.thumb == 200 and keys.control["follows"] is True and keys.control["share"] == (0.25, 0.5), (world.thumb, keys.control)
idle()
press("rightarrow")
idle()
assert world.thumb == 208 and keys.control["share"] == (0.26, 0.5) and said[-1] == "Up.", (world.thumb, keys.control["share"], said[-1])
press("leftarrow")
press("escape")
idle()
# Something that does not answer to the wheel or to any drag is not taken, and that is said.
world.kind, world.handle = "knob", (50, 50)
taken, text = keys.start(controlkeys.newControl("Nothing", "control", (400, 300), box))
assert not taken and text.startswith("Nothing VisionClaw can see changed at Nothing when it turned the mouse wheel"), text
assert not keys.active and buttons[-1] == LEFT_UP

# Where Windows offers the control's value, it is set through Windows itself: the mouse is not touched.
pattern = types.SimpleNamespace(CurrentMinimum=0, CurrentMaximum=10, CurrentValue=5, CurrentSmallChange=1, CurrentIsReadOnly=False)
pattern.SetValue = lambda value: setattr(pattern, "CurrentValue", value)
speed = types.SimpleNamespace(value=None)
realPattern, deepquery._rangePattern = deepquery._rangePattern, lambda obj: pattern if obj is speed else None
del moves[:], buttons[:]
taken, text = keys.start(controlkeys.newControl("Speed", "slider", (400, 300), box, obj=speed))
assert taken and "through Windows itself, without the mouse" in text and keys.control["method"] == dragcontrol.VALUE, text
idle()
press("uparrow")
idle()
assert pattern.CurrentValue == 6 and said[-1] == "60 percent" and buttons == [], (pattern.CurrentValue, said[-1], buttons)
press("escape")

# --- The inspection works out how a sighted person works each control, and chooses the fix ---


def thing(role, name, states=(), box=(0, 0, 10, 10), children=(), autoId=""):
	return types.SimpleNamespace(
		role=types.SimpleNamespace(name=role, displayString=role.lower()), name=name, value="",
		states=[types.SimpleNamespace(name=state, displayString=state.lower()) for state in states],
		location=types.SimpleNamespace(left=box[0], top=box[1], width=box[2] - box[0], height=box[3] - box[1]),
		children=list(children), windowControlID=0, UIAAutomationId=autoId, windowClassName="JUCE_1a",
		hasIrrelevantLocation=False, windowHandle=0, appModule=types.SimpleNamespace(appName="mixer"))


volumeSlider = thing("SLIDER", "Volume", box=(100, 100, 300, 120), autoId="volumeSlider")
drive = thing("PANE", "", ["CLICKABLE"], box=(376, 276, 424, 324))
okButton = thing("BUTTON", "OK", ["FOCUSABLE"], box=(600, 500, 700, 540))
mixer = thing("WINDOW", "Mixer", box=(0, 0, 800, 600), children=[volumeSlider, drive, okButton])
sys.modules["api"].getForegroundObject = lambda: mixer
sys.modules["api"].getFocusObject = lambda: drive


class JudgeRuntime(FakeRuntime):
	asked = []

	def chat(self, role, messages, maxTokens, **options):
		system = messages[0]["content"]
		self.asked.append(system[:24])
		if system.startswith("You look at a picture of one control"):
			return json.dumps({"way": "turn in a circle"})
		if system.startswith("You know how programs and web pages are built"):
			return json.dumps({"way": "drag up and down"})
		raise AssertionError(system[:60])

	def describe(self, image, prompt, maxTokens, cancel=None):
		return "none"


realRuntime, instance.runtime = instance.runtime, JudgeRuntime()
world.kind, world.handle, world.level = "knob", (200, 110), 50
task = taskModule.Task("test")
worked, result = registry.call(task, "check_access", {"target": "window", "depth": "deep"})
assert worked and "with a mouse 1 is clicked, 1 is dragged sideways." in result, result
# The pane NVDA cannot tell the kind of was shown to both models: the vision model saw its picture, the
# coder model read the deep query, and both mean a thing that is turned.
assert "a pane without a name: turn in a circle, says both models." in result and "a model can be wrong" in result, result
assert len(JudgeRuntime.asked) == 2, JudgeRuntime.asked
assert ("2 controls here are worked by dragging or turning with the mouse and do not take the keyboard: Volume, "
	"a dial without a name.") in result, result
assert "with an add-on or with hotkeys of its own" in result, result
# Fixing them makes a hotkey for each, after a question. Nothing is tried yet, and no code is written.
del questions[:], buttons[:]
worked, result = registry.call(task, "fix_access", {"which": "fix the dials and sliders"})
assert worked and result.startswith("Made 2 hotkeys in mixer: NVDA+alt+"), result
assert questions[-1].startswith("Make these hotkeys in mixer?") and "for Volume" in questions[-1] and buttons == [], questions
made = {binding["name"]: binding for binding in instance.helpers._bindings["mixer"].values()}
assert made["Volume"]["find"] == {"rule": {"role": "SLIDER", "autoId": "volumeSlider"}} and made["Volume"]["method"] is None, made
assert made[""]["kind"] == "dial" and made[""]["find"] is None and made[""]["share"] == [0.5, 0.5], made
# The first press of a hotkey finds the control by what tells it apart, finds out how it is worked, and
# remembers that.
press(made["Volume"]["key"].lower())
for _ in range(300):
	if keys.active:
		break
	time.sleep(0.01)
idle()
assert keys.active and keys.control["method"] == dragcontrol.UPDOWN and keys.control["share"] == (0.25, 0.1833), keys.control
press("escape")
assert [b for b in instance.helpers._bindings["mixer"].values() if b["name"] == "Volume"][0]["method"] == dragcontrol.UPDOWN
# One control queried in depth: what is reported, how it is worked, and what to ask for.
del JudgeRuntime.asked[:]
worked, result = registry.call(taskModule.Task("test"), "check_access", {"target": "control", "depth": "deep"})
assert worked and "The deep query found this. It is reported as: pane, with no name." in result, result
assert "Its window has the class JUCE_1a, which is JUCE, used by music programs and plug-ins." in result, result
assert "A sighted person works it like this: turn in a circle. That comes from both models." in result, result
assert "Ask VisionClaw to let the arrow keys work this control" in result, result
# One model chosen for both jobs: it is asked about the picture and about what is reported, and the report
# says so. It never speaks of both models, because there are not two.
JudgeRuntime.oneModel = lambda self: True
del JudgeRuntime.asked[:]
oneTask = taskModule.Task("test")
worked, result = registry.call(oneTask, "check_access", {"target": "control", "depth": "deep"})
assert worked and ("A sighted person works it like this: turn in a circle. That comes from the model, from the "
	"picture and from what is reported.") in result, result
assert "both models" not in result, (JudgeRuntime.asked, result)
assert any("from its picture the model says turn in a circle, from what is reported about it the model says "
	"drag up and down." in text for _t, _k, text in oneTask.log), oneTask.log
assert not any("vision model" in text or "coder model" in text for _t, _k, text in oneTask.log), oneTask.log
worked, result = registry.call(taskModule.Task("test"), "check_access", {"target": "window", "depth": "deep"})
assert worked and "turn in a circle, says the model, from the picture and from what is reported." in result, result
assert "with the model, shown the picture and told what is reported, and a model can be wrong" in result, result
assert "both models" not in result, result
del JudgeRuntime.oneModel
for binding in list(made.values()):
	assert instance.helpers.remove(binding["key"])
instance.runtime = realRuntime
deepquery._rangePattern = realPattern

# Controls that are worked by neither a click nor a drag. Their own names say how: one is held down, one is
# swiped. No model is asked. The one that is held down gets a hotkey although it takes the focus, because
# Enter clicks a button and does not keep it down; for the other the report says what to ask for.
recordButton = thing("BUTTON", "Hold to record", ["FOCUSABLE"], box=(100, 400, 300, 440), autoId="recordButton")
unlock = thing("PANE", "Swipe to unlock", ["CLICKABLE"], box=(400, 400, 700, 440))
recorder = thing("WINDOW", "Recorder", box=(0, 0, 800, 600), children=[recordButton, unlock, okButton])
sys.modules["api"].getForegroundObject = lambda: recorder
sys.modules["api"].getFocusObject = lambda: okButton
task = taskModule.Task("test")
worked, result = registry.call(task, "check_access", {"target": "window", "depth": "quick"})
assert worked and "with a mouse 1 is clicked, 1 is pressed and held down, 1 is swiped or drawn on." in result, result
assert ("1 control here is worked with the mouse in a way the keyboard does not do: Hold to record is worked by "
	"holding the mouse button down on it.") in result, result
assert "Swipe to unlock is worked by swiping across it or drawing on it." in result, result
assert "Ask VisionClaw to swipe it left, right, up or down" in result and "with hotkeys of its own" in result, result
del questions[:], buttons[:], moves[:]
worked, result = registry.call(task, "fix_access", {"which": "fix the control that is held down"})
assert worked and result.startswith("Made 1 hotkey in mixer: NVDA+alt+") and result.endswith(
	"holds the mouse button down on Hold to record until you press it again. Ask VisionClaw to remove a hotkey to undo one."), result
assert questions[-1].startswith("Make these hotkeys in mixer? NVDA+alt+") and "arrow keys" not in questions[-1], questions
held = [b for b in instance.helpers._bindings["mixer"].values() if b["name"] == "Hold to record"][0]
assert held["action"] == "press and hold" and held["find"] == {"rule": {"role": "BUTTON", "autoId": "recordButton"}}, held
assert buttons == []  # nothing is pressed until the hotkey is
# The hotkey finds the button again, presses the mouse button on its middle and keeps it down; the same
# hotkey lets go, and so does Escape.
press(held["key"].lower())
for _ in range(300):
	if instance.pointerMode.kept is not None:
		break
	time.sleep(0.01)
assert instance.pointerMode.kept == "Hold to record" and buttons == [LEFT_DOWN] and moves[-1] == (200, 420), (buttons, moves)
assert said[-1] == "Holding the mouse button down on Hold to record. Press the hotkey again, or Escape, to let go.", said[-1]
press(held["key"].lower())
assert instance.pointerMode.kept is None and buttons == [LEFT_DOWN, LEFT_UP] and said[-1] == "Let go of Hold to record.", said[-1]
press(held["key"].lower())
for _ in range(300):
	if instance.pointerMode.kept is not None:
		break
	time.sleep(0.01)
press("escape")
assert instance.pointerMode.kept is None and buttons == [LEFT_DOWN, LEFT_UP] * 2, buttons
assert instance.getScript(key("escape")) is None  # nothing is held: Escape is the program's own again
# VisionClaw going away lets go of a button that is still down.
press(held["key"].lower())
for _ in range(300):
	if instance.pointerMode.kept is not None:
		break
	time.sleep(0.01)
instance.pointerMode.stop(say=False)
assert instance.pointerMode.kept is None and buttons[-1] == LEFT_UP
assert "holds" not in instance.helpers.listText() and "does press and hold \"Hold to record\"" in instance.helpers.listText()
assert instance.helpers.remove(held["key"])
# The focused control, queried in depth: its own name comes before its kind.
sys.modules["api"].getFocusObject = lambda: recordButton
worked, result = registry.call(taskModule.Task("test"), "check_access", {"target": "control", "depth": "deep"})
assert worked and "A sighted person works it like this: press and hold. That comes from its own name." in result, result
assert "Ask VisionClaw to press and hold it by name" in result, result

# --- The developer guides: downloaded only after a yes, kept as Markdown, and read by the models ---

GUIDE = "<html><body><h1>NVDA Developer Guide</h1>" + "".join(
	f"<h2>Chapter {n}</h2><p>{'A quokkabinding ties a gesture to a script in chapter %d. ' % n * 30}</p>" for n in range(8)) + "</body></html>"
WIKI = "".join(f"## Lesson {n}\n\n{'An add-on is a package, says lesson %d. ' % n * 40}\n\n" for n in range(8))
fetched = []


def fakeFetch(url, limit=None, hosts=None):
	fetched.append((url, hosts))
	return GUIDE if url.endswith(".html") else WIKI


nvdatools.net.fetchText = fakeFetch
conf["visionClaw"]["confirmChanges"] = False
# It is asked about even when the user turned confirmations off, and a no downloads nothing.
del questions[:]
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(taskModule.Task("test"), "update_guides", {})
assert worked and result == "You said no, so nothing was changed." and fetched == [], (result, fetched)
assert questions[0].startswith("Download the latest NVDA Developer Guide from NV Access") and "Only these two requests are sent" in questions[0]
instance.clawAsk = lambda question, choices: 0
worked, result = registry.call(taskModule.Task("test"), "update_guides", {})
assert worked and result.startswith("Downloaded the NVDA Developer Guide and kept it as Markdown, 8 sections."), result
assert [url.split("/")[2] for url, _hosts in fetched] == ["download.nvaccess.org", "raw.githubusercontent.com"], fetched
assert all(hosts and "download.nvaccess.org" in hosts for _url, hosts in fetched)
assert os.path.isfile(os.path.join(instance.guidesDir, "nvda-developer-guide.md"))
# What the models read up in now includes the guide.
worked, result = registry.call(taskModule.Task("test"), "search_help", {"words": "quokkabinding gesture script"})
assert worked and "A quokkabinding ties a gesture to a script" in result, result
assert registry.get("update_guides").tell == "verbatim" and "update_guides" in planner.RECIPES

# --- NVDA's commands: the request that failed in real use, replayed ---
# "ask nvda to give me the current time and then the date" ended with
# "AttributeError: 'NoneType' object has no attribute 'wasInSayAll'". VisionClaw had chosen the status bar
# command, could not make a key press for its key (NVDA shows it as "ctrl", and knows it as "control"), and ran
# the command with no key press at all, which NVDA cannot do. The stand-ins below behave like NVDA 2026.3.1 in
# all three places.
from visionClaw.claw import debuglog  # noqa: E402

nvdatools.COMMAND_SETTLE_SECONDS = 0
spoken, ran = [], []
listeners = []
sys.modules["speech.extensions"].filter_speechSequence = types.SimpleNamespace(
	register=listeners.append, unregister=listeners.remove)


def say(text):
	spoken.append(text)
	for listener in list(listeners):
		listener([text])


presses = {"script": None, "count": 0}


class Commands:
	"""NVDA's global commands."""

	def script_dateTime(self, gesture):
		say("10:42" if presses["count"] == 0 else "Tuesday, November 17, 2026")

	def script_reportStatusLine(self, gesture):
		say("Line 1, column 1")

	def script_noKey(self, gesture):
		say("done without a key")

	def script_hidden(self, gesture):
		say("a command NVDA lists nowhere")

	_gestureMap = {}


Commands._gestureMap = {"kb:alt+f12+nvda": Commands.script_hidden}
theCommands = Commands()
sys.modules["globalCommands"].commands = theCommands


def executeScript(script, gesture):
	# As in NVDA's scriptHandler: the key press is asked before anything else, and a quick second press counts.
	gesture.wasInSayAll
	function = getattr(script, "__func__", script)
	presses["count"] = presses["count"] + 1 if presses["script"] is function else 0
	presses["script"] = function
	ran.append((function.__name__, type(gesture).__name__))
	script(gesture)


def clearLastScript():
	presses["script"], presses["count"] = None, 0


sys.modules["scriptHandler"].executeScript = executeScript
sys.modules["scriptHandler"].clearLastScript = clearLastScript
made = []


class KeyPress:
	wasInSayAll = False

	def __init__(self, name):
		self.displayName = name

	@classmethod
	def fromName(cls, name):
		# NVDA knows "control", not "ctrl", and no key called "bogus".
		if any(part in ("ctrl", "bogus") or " " in part for part in name.split("+")):
			raise LookupError(name)
		made.append(name)
		return cls(name)


sys.modules["keyboardHandler"].KeyboardInputGesture = KeyPress


def info(scriptName, description, gestures):
	return types.SimpleNamespace(cls=Commands, scriptName=scriptName, displayName=description, gestures=gestures)


MAPPINGS = {"System status": {
	"time": info("dateTime", "If pressed once, reports the current time. If pressed twice, reports the current date", ["kb:f12+nvda"]),
	"status": info("reportStatusLine", (
		"Reads the current application status bar. If pressed twice, spells the information. If pressed three "
		"times, copies the status bar to the clipboard"), ["kb:control+downarrow+nvda"]),
	"focus": info("reportCurrentFocus", (
		"Reports the object with focus. If pressed twice, spells the information. Pressing three times spells it "
		"using character descriptions."), ["kb:nvda+tab"]),
	"nokey": info("noKey", "Announces the quokka without any key", []),
	"badkey": info("noKey", "Announces the wombat with a key NVDA cannot make", ["kb:bogus+nvda"]),
}}
SHOWN = {"kb:f12+nvda": "NVDA+f12", "kb:control+downarrow+nvda": "NVDA+ctrl+down arrow", "kb:nvda+tab": "NVDA+tab",
	"kb:bogus+nvda": "NVDA+bogus", "kb:alt+f12+nvda": "NVDA+alt+f12"}
sys.modules["inputCore"].manager = types.SimpleNamespace(getAllGestureMappings=lambda obj=None, ancestors=None: MAPPINGS)
sys.modules["inputCore"].getDisplayTextForGestureIdentifier = lambda gesture: ("keyboard", SHOWN[gesture])
sys.modules["api"].getFocusObject = lambda: types.SimpleNamespace(appModule=None, treeInterceptor=None)
sys.modules["api"].getFocusAncestors = lambda: []
running.clear()
conf["visionClaw"]["confirmChanges"] = False

# The whole request, through the orchestrator, with a model that chooses what the model in real use chose.
from visionClaw.claw import policy  # noqa: E402


class OneModel:
	"""One model for both jobs, as in the real run. It answers each question the way it was seen to."""
	oneModel = True

	def __init__(self):
		self.asked = []

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"id": "tiny", "name": "Qwen3.5 0.8B", "small": True, "thinking": False, "tiny": True}

	def whereText(self):
		return ""

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		user = messages[-1]["content"]
		self.asked.append(user)
		schema = options["response_format"]["json_schema"]["schema"]["properties"]
		if "parts" in schema:
			return json.dumps({"parts": ["ask nvda to give me the current time", "ask nvda to give me the date"]})
		if "choice" in schema:
			return json.dumps({"choice": "do_command"})
		if "command" in schema:
			# A small model takes the first id it is offered.
			return json.dumps({"command": schema["command"]["enum"][0]})
		raise AssertionError(f"an unexpected question to the model: {user}")


model = OneModel()
runner = orchestrator.Orchestrator(model, registry, lambda question, choices: 0)
runner.stepwise = lambda: policy.NEVER
del spoken[:], ran[:], made[:]
task = runner.run(taskModule.Task("ask nvda to give me the current time and then the date"))
assert task.state == taskModule.DONE, (task.state, task.log[-4:])
assert [step.tool for step in task.steps] == ["find_command", "run_command", "find_command", "run_command", "answer"]
assert all(step.status == taskModule.STEP_DONE for step in task.steps), task.steps
# The clock was found for both parts, and nothing else was offered to the model.
assert task.steps[0].result == (
	"dateTime: If pressed once, reports the current time. If pressed twice, reports the current date. Keys: NVDA+f12."
), task.steps[0].result
assert task.steps[2].result == task.steps[0].result
# The time is one press; the date is two quick presses, as NVDA's own description of the command says.
assert ran == [("script_dateTime", "KeyPress")] * 3, ran
assert made == ["nvda+f12", "nvda+f12"], made  # the keys that are held come first again, the key that is pressed last
assert task.answer == (
	"NVDA said: 10:42. Next time you can press NVDA+f12 for this. NVDA said: Tuesday, November 17, 2026. "
	"Next time you can press NVDA+f12 twice for this."), task.answer
assert spoken == ["10:42", "10:42", "Tuesday, November 17, 2026"], spoken
# The same in one part: both are said, in order.
del spoken[:], ran[:]
worked, result = registry.call(taskModule.Task("t"), "run_command", {"command": "dateTime", "asked": "the time and the date"})
assert worked and result == "NVDA said: 10:42 Tuesday, November 17, 2026. Next time you can press NVDA+f12 twice for this.", result

# The command that failed: its key is shown as "NVDA+ctrl+down arrow". The key press is made from the way NVDA
# writes the key, not from how it is shown, so the command runs.
del spoken[:], ran[:], made[:]
worked, result = registry.call(taskModule.Task("t"), "find_command", {"words": "read the status bar"})
assert worked and result.startswith("reportStatusLine: Reads the current application status bar"), result
assert "Keys: NVDA+ctrl+down arrow." in result
worked, result = registry.call(taskModule.Task("t"), "run_command", {"command": "reportStatusLine", "asked": "read the status bar"})
assert worked and result == "NVDA said: Line 1, column 1. Next time you can press NVDA+ctrl+down arrow for this.", result
assert made == ["control+nvda+downarrow"] and ran == [("script_reportStatusLine", "KeyPress")], (made, ran)
# A command without a key, and one whose key NVDA cannot make, are given a stand-in for the key press: NVDA
# asks the key press whether it came during say all, and "nothing" cannot answer that.
for words, expected in (("announce the quokka", "done without a key"), ("announce the wombat", "done without a key")):
	del ran[:]
	task = taskModule.Task(words)
	worked, result = registry.call(task, "find_command", {"words": words})
	ident = result.split(":")[0]
	assert worked and ident.startswith("noKey"), result
	worked, result = registry.call(task, "run_command", {"command": ident, "asked": words})
	assert worked and result.startswith(f"NVDA said: {expected}."), result
	assert ran == [("script_noKey", "NoKeys")], ran
gesture = nvdatools.noKeyGesture("Announces the quokka", theCommands.script_noKey)
assert gesture.wasInSayAll is False and gesture.send() is None and gesture.displayName == "Announces the quokka"
assert nvdatools.keyGesture("kb(laptop):shift+nvda+s").displayName == "shift+nvda+s"
# A command NVDA lists nowhere, because it has no description, is found by its name and run all the same.
del ran[:]
task = taskModule.Task("run the hidden command")
worked, result = registry.call(task, "find_command", {"words": "run the hidden command"})
assert worked and result == "hidden: A command without a description, in __main__. Keys: NVDA+alt+f12.", result
worked, result = registry.call(task, "run_command", {"command": "hidden", "asked": "run the hidden command"})
assert worked and result.startswith("NVDA said: a command NVDA lists nowhere."), result
# A described command is never pushed aside by one without a description.
worked, result = registry.call(taskModule.Task("t"), "find_command", {"words": "report the focus"})
assert worked and result.startswith("reportCurrentFocus: ") and "hidden" not in result, result
# What has no command says so, instead of offering whatever shares a word.
worked, result = registry.call(taskModule.Task("t"), "find_command", {"words": "say the version of the zebra"})
assert not worked and result.startswith("No NVDA command matches those words."), result
# A fault inside a tool ends the step with a sentence, and the whole of it is in VisionClaw's log.
sys.modules["scriptHandler"].executeScript = lambda script, gesture: None.wasInSayAll
task = taskModule.Task("the time")
registry.call(task, "find_command", {"words": "the current time"})
worked, result = registry.call(task, "run_command", {"command": "dateTime", "asked": "the current time"})
assert not worked and "a fault inside VisionClaw (AttributeError" in result, result
sys.modules["scriptHandler"].executeScript = executeScript
written = debuglog.tail(200)
assert debuglog.path() == os.path.join(CONFIG_DIR, "visionClaw", "logs", "visionclaw.log") and debuglog.detailed()
assert "tool: ERROR: run_command failed" in written and "wasInSayAll" in written and "nvdatools.py" in written
assert "command: Running dateTime (script_dateTime of __main__), pressed 1 time(s)" in written
with open(debuglog.path(), encoding="utf-8") as f:
	everything = f.read()
assert "start: VisionClaw" in everything and "This log stays on this computer" in everything
assert "task: New request: 'ask nvda to give me the current time and then the date'" in everything
assert "task answer: NVDA said: 10:42." in everything and "tool: find_command starts." in everything
assert "command: dateTime ran. NVDA said: 'Tuesday, November 17, 2026'" in everything

# --- Everything inside NVDA: found by describing it, looked at closely, and what it holds now ---
fakeApi = sys.modules["quokkaApi"] = types.ModuleType("quokkaApi")  # a real module: a stand-in has every name
fakeApi.__doc__ = "Functions about quokkas."


def getQuokkaObject():
	"""Gets the quokka that has the focus."""
	return types.SimpleNamespace(name="Quokka OK", role=types.SimpleNamespace(displayString="button", name="BUTTON"))


def setQuokka(value):
	"""Changes the quokka."""
	raise AssertionError("a function that changes something must never be called by looking at it")


getQuokkaObject.__module__ = setQuokka.__module__ = "quokkaApi"
fakeApi.getQuokkaObject, fakeApi.setQuokka, fakeApi.quokkaCount = getQuokkaObject, setQuokka, 3
task = taskModule.Task("what does getQuokkaObject give back")
worked, result = registry.call(task, "find_nvda", {"words": "the quokka that has the focus"})
assert worked and result.splitlines()[0] == (
	"quokkaApi.getQuokkaObject: function. getQuokkaObject(). Gets the quokka that has the focus."), result
worked, result = registry.call(task, "inspect_nvda", {"name": "quokkaApi.getQuokkaObject"})
assert worked and result == (
	"quokkaApi.getQuokkaObject is a function.\nCall it as getQuokkaObject().\nGets the quokka that has the focus.\n"
	"Called now, it gives back: an object NVDA reads: button called \"Quokka OK\" (types.SimpleNamespace)."), result
# What a function gives back can be looked into; a value says what it holds; nothing that changes is called.
worked, result = registry.call(task, "inspect_nvda", {"name": "quokkaApi.getQuokkaObject.name"})
assert worked and result == "quokkaApi.getQuokkaObject().name is a value of the kind str.\nNow it holds: 'Quokka OK'.", result
worked, result = registry.call(task, "inspect_nvda", {"name": "quokkaApi.quokkaCount"})
assert worked and result.endswith("Now it holds: 3."), result
worked, result = registry.call(task, "inspect_nvda", {"name": "quokkaApi.setQuokka"})
assert worked and "Call it as setQuokka(value)." in result and "Called now" not in result, result
worked, result = registry.call(task, "inspect_nvda", {"name": "quokkaApi.nothingHere"})
assert not worked and "has nothing called nothingHere" in result, result
worked, result = registry.call(task, "inspect_nvda", {"name": "subprocess.Popen"})
assert not worked and "not an NVDA module" in result, result
worked, result = registry.call(task, "find_nvda", {"words": "zzyzx plugh xyzzy"})
assert not worked and result.startswith("Nothing inside NVDA matches those words."), result
assert registry.get("inspect_nvda").before == "find_nvda" and registry.get("inspect_nvda").tell == "verbatim"

# --- What NVDA knows about one object ---
Role = types.SimpleNamespace
button = types.SimpleNamespace(
	name="Send", role=Role(name="BUTTON", displayString="button"), value=None, description="Sends the message",
	states=[Role(name="FOCUSABLE"), Role(name="FOCUSED")], keyboardShortcut="alt+s",
	location=types.SimpleNamespace(left=100, top=200, width=80, height=30), windowClassName="Button",
	windowControlID=1001, windowHandle=3344, childCount=0, processID=4242, quokkaLevel=7,
	appModule=types.SimpleNamespace(appName="mailer"), positionInfo={"indexInGroup": 2, "similarItemsInGroup": 5},
	parent=types.SimpleNamespace(name="Compose", role=Role(name="DIALOG", displayString="dialog")),
	firstChild=None, UIAElement=None, IAccessibleObject=None, IA2Attributes=None, actionCount=0,
	getActionName=lambda index=0: "press",
)
sys.modules["api"].getFocusObject = lambda: button
sys.modules["api"].getNavigatorObject = lambda: button.parent
sys.modules["api"].getDesktopObject = lambda: types.SimpleNamespace(objectFromPoint=lambda x, y: None)
worked, result = registry.call(taskModule.Task("t"), "object_info", {"object": "focus", "asked": "tell me everything about this control"})
assert worked and result.startswith("The focused control. Name: Send. Kind: button (controlTypes.Role.BUTTON)."), result
for fact in (
	"Description: Sends the message.", "States: focusable, focused.", "Keyboard shortcut: alt+s.",
	"Position and size: left 100, top 200, 80 wide, 30 high, in pixels.", "Place among its neighbours: 2 of 5.",
	"Program: mailer, process id 4242.", "Window class: Button.", "Window control id: 1001.", "Window handle: 3344.",
	"Actions: press.", "It is inside: dialog called \"Compose\".", "Everything else it has:",
):
	assert fact in result, (fact, result)
# Asked for one fact, only that is said; and a property VisionClaw has no name for is read from the object.
worked, result = registry.call(taskModule.Task("t"), "object_info", {"object": "focus", "asked": "what is the window class of this control"})
assert worked and result == "The focused control. Window class: Button.", result
worked, result = registry.call(taskModule.Task("t"), "object_info", {"object": "focus", "asked": "where is this button on the screen"})
assert worked and result == "The focused control. Position and size: left 100, top 200, 80 wide, 30 high, in pixels.", result
worked, result = registry.call(taskModule.Task("t"), "object_info", {"object": "focus", "asked": "what is the quokkaLevel of this control"})
assert worked and result == "The focused control. quokkaLevel: 7.", result
worked, result = registry.call(taskModule.Task("t"), "object_info", {"object": "navigator", "asked": "the name of the navigator object"})
assert worked and result == "The navigator object. Name: Compose.", result
assert nvdatools.objectOf("what is under the mouse") == "mouse" and nvdatools.objectOf("this button") == "focus"
assert nvdatools.objectOf("the window class of this control") == "focus" and nvdatools.objectOf("facts about this window") == "window"
assert registry.get("object_info").autoForm("the role of the navigator object")["object"] == "navigator"

# --- The audit of the whole NVDA, and VisionClaw's log, opened only when asked ---
started = []
realStartfile = getattr(os, "startfile", None)
os.startfile = started.append
try:
	sys.modules["api"].getFocusObject = lambda: types.SimpleNamespace(appModule=None, treeInterceptor=None)
	worked, result = registry.call(taskModule.Task("t"), "audit_nvda", {"asked": "do a full audit of nvda"})
	auditPath = os.path.join(CONFIG_DIR, "visionClaw", "nvda-audit.md")
	assert worked and result.startswith("VisionClaw went through all of this NVDA. Commands that can be used where you are now: 6. "
		"5 have a description, 1 have none, and 5 have a key."), result
	assert f"is saved as the file {auditPath}." in result and started == [], (result, started)
	with open(auditPath, encoding="utf-8") as f:
		audit = f.read()
	for part in (
		"# Audit of this NVDA by VisionClaw", "## Totals", "## Speech: how NVDA talks to the synthesizer",
		"## Braille: how NVDA talks to the braille display", "The driver in use is the class",
		"reached as synthDriverHandler.getSynth().", "reached as braille.handler.",
		"## Commands with a description, usable where you are now", "dateTime: If pressed once, reports the current time",
		"## Commands without a description, usable where you are now", "hidden: A command without a description",
		"## Everything inside, by name", "quokkaApi.getQuokkaObject: function.",
	):
		assert part in audit, part
	worked, result = registry.call(taskModule.Task("t"), "audit_nvda", {"asked": "audit nvda and show me the list"})
	assert worked and "It is open in a window now." in result and started == [auditPath], (result, started)
	worked, result = registry.call(taskModule.Task("t"), "show_log", {})
	assert worked and result.startswith("VisionClaw's log is open in a window.") and started[-1] == debuglog.path(), result
	debuglog.setLevel(debuglog.OFF)
	worked, result = registry.call(taskModule.Task("t"), "show_log", {})
	assert worked and result.startswith("VisionClaw's log is switched off.") and len(started) == 2, result
	debuglog.setLevel(debuglog.DETAILED)
	# The setting is one of three, and what the user chose is what is used.
	assert conf["visionClaw"]["debugLog"] == "detailed"
	conf["visionClaw"]["debugLog"] = "brief"
	instance.onSettingsSaved()
	assert debuglog.level() == "brief" and not debuglog.detailed()
	conf["visionClaw"]["debugLog"] = "detailed"
	instance.onSettingsSaved()
finally:
	if realStartfile is not None:
		os.startfile = realStartfile

# --- Questions in the description window: none is turned away any more ---
# VisionMate asked the model first whether a question was "about the image", and a small model said no to
# "what is highlighted on my desktop". Now every question goes to the vision model with the picture.
from visionClaw import followup  # noqa: E402

assert not hasattr(followup, "CHECK") and not hasattr(followup, "NOT_IMAGE") and not hasattr(followup, "clearlyOffTopic")
assert not hasattr(instance, "_declineQuestion")
for phrase in ("blind person", "highlighted or selected", "not in the picture", "Never make up"):
	assert phrase in followup.ANSWER, phrase
chats, answers = [], []


def fakeChat(messages, maxTokens, onText=None, cancel=None, *args, **kwargs):
	chats.append((messages, maxTokens))
	if onText is not None:
		onText("The Recycle Bin icon is highlighted.")
	return "The Recycle Bin icon is highlighted."


instance._engine = types.SimpleNamespace(chat=fakeChat, usingGpu=False)
instance._ensureEngine = lambda: None
dialog = types.SimpleNamespace(addAnswer=lambda question, answer: answers.append((question, answer)))
for question in ("what is the currently highlighted item on my desktop?", "what is a recycle bin for?", "hello"):
	conversation = {"start": [{"role": "user", "content": "describe"}, {"role": "assistant", "content": "A desktop."}], "history": []}
	del chats[:], answers[:]
	instance._answer(conversation, question, dialog, threading.Event())
	assert len(chats) == 1, chats  # asked once: no question about the question comes first
	assert chats[0][0][-1]["content"].startswith(question) and followup.ANSWER in chats[0][0][-1]["content"]
	assert answers == [(question, "The Recycle Bin icon is highlighted.")], answers
	assert conversation["history"] == [(question, "The Recycle Bin icon is highlighted.")]
assert "Question about the picture: 'hello'" in debuglog.tail(30)

# --- A question is put to NVDA, then the program, then its window, then Windows ---
# The request that went wrong in real use: "How can I use the keyboard to navigate my desktop?" was put to
# NVDA's commands alone, and answered with the command that switches the keyboard layout.
from visionClaw import asktools  # noqa: E402
from visionClaw.claw import lookup  # noqa: E402

guidePath = os.path.join(CONFIG_DIR, "userGuide.html")
with open(guidePath, "w", encoding="utf-8") as f:
	f.write(
		"<h1>NVDA User Guide</h1><p>Contents: Browse Mode, the desktop keyboard layout, and more of the same kind.</p>"
		"<h2>Browse Mode</h2><p>Complex read-only documents such as web pages are browsed in NVDA using browse mode.</p>"
		"<table><tr><th>Name</th><th>Desktop key</th><th>Laptop key</th></tr>"
		"<tr><td>Toggle browse and focus modes</td><td>NVDA+space</td><td>NVDA+space</td></tr></table>")
sys.modules["documentationUtils"].getDocFilePath = lambda name: guidePath
sys.modules["winVersion"].getWinVer = lambda: types.SimpleNamespace(releaseName="Windows 11 24H2", build=26100)
asktools.openWindows = lambda: ["Inbox - Mail", "Untitled - Notepad"]  # the real windows of this computer are not read
asktools._kept.update(count=None, passages=[], guide=None)
MAPPINGS["Input"] = {
	"layout": info("toggleKeyboardLayout", "Toggles between desktop and laptop keyboard layout", []),
	"title": info("title", "Reports the title of the current application or foreground window. If pressed twice, spells the title", ["kb:nvda+t"]),
}
SHOWN["kb:nvda+t"] = "NVDA+t"
explorer = types.SimpleNamespace(appName="explorer", productName="Microsoft Windows Operating System", productVersion="10.0.26100")
viewButton = types.SimpleNamespace(
	name="View", role=Role(name="BUTTON", displayString="button"), keyboardShortcut="Alt+V", firstChild=None, next=None)
programManager = types.SimpleNamespace(
	name="Program Manager", role=Role(name="PANE", displayString="pane"), appModule=explorer, firstChild=viewButton)
desktopList = types.SimpleNamespace(name="Desktop", role=Role(name="LIST", displayString="list"))
recycleBin = types.SimpleNamespace(
	name="Recycle Bin", role=Role(name="LISTITEM", displayString="list item"), value=None, description="",
	states=[Role(name="SELECTED", displayString="selected"), Role(name="FOCUSED", displayString="focused")],
	keyboardShortcut=None, positionInfo={"indexInGroup": 1, "similarItemsInGroup": 12}, appModule=explorer,
	treeInterceptor=None, firstChild=None, next=None)
sys.modules["api"].getForegroundObject = lambda: programManager
sys.modules["api"].getFocusObject = lambda: recycleBin
sys.modules["api"].getFocusAncestors = lambda: [types.SimpleNamespace(name="Desktop", role=Role(displayString="window")), programManager, desktopList]
sys.modules["api"].getStatusBar = lambda: None
question = "How can I use the keyboard to navigate my desktop?"
task = taskModule.Task(question)
worked, result = registry.call(task, "look_up", {"question": question})
assert worked and result.startswith(
	"From Windows: The desktop: going to it and navigating its icons with the keyboard. Press Windows+D to go to the "
	"desktop; press it again to bring the windows back. On the desktop the arrow keys move from icon to icon"), result
assert "toggleKeyboardLayout" not in result and "layout" not in result, result
# All four were asked, in order, and the user is told so.
told = [text for _seconds, kind, text in task.log if kind == taskModule.DETAIL]
assert told[0] == "Asked NVDA: 7 commands that work where you are, its user guide, and the help of its add-ons.", told
assert told[1] == "Asked the program explorer, and its window Program Manager. Controls in it with a key of their own: 1.", told
assert told[2] == "Asked Windows: Windows 11 24H2, build 26100, 2 open windows, and the keys of Windows.", told
assert "lookup: Asked " in debuglog.tail(20) and "Telling words: ['desktop', 'keyboard', 'navig']" in debuglog.tail(20)
# NVDA answers what is NVDA's: a command with its key, and what something is from its user guide, whose
# table headings ("Desktop key") are not taken for content.
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "How do I read the window title?"})
assert worked and result.splitlines()[0] == (
	"From NVDA: title: Reports the title of the current application or foreground window. If pressed twice, spells "
	"the title. Keys: NVDA+t."), result
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "What is browse mode?"})
assert worked and result.splitlines()[0] == (
	"From NVDA's user guide: Browse Mode. Complex read-only documents such as web pages are browsed in NVDA using "
	"browse mode. Toggle browse and focus modes, NVDA+space, NVDA+space"), result
# The program and its window answer for where the user is.
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "What can I do here?"})
assert worked and result.splitlines() == [
	"From the program explorer: The program in front is explorer, which is Microsoft Windows Operating System, version 10.0.26100.",
	"From this window: The window in front is called Program Manager.",
	"From this window: The control that has the focus. The focus is on: list item \"Recycle Bin\". It is selected. It is 1 of 12. "
	"It is inside: pane \"Program Manager\", then list \"Desktop\".",
], result
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "which key is for the View button"})
assert worked and "From this window: Keys of the controls in this window. View (button): Alt+V." in result, result
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "which windows are open"})
assert worked and result.startswith("From Windows: The windows that are open now. 2 windows are open now: Inbox - Mail; Untitled - Notepad."), result
# Nothing fits: that is a sentence for the user, not a failed step to be tried again with other words.
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "How do I bake a walnut cake?"})
assert worked and result.startswith(
	"Nothing was found about bake or walnut or cake. Asked were: NVDA's commands and user guide, the program explorer, "
	"its window Program Manager, what VisionClaw knows about Windows, the documents in your library, and what you "
	"asked VisionClaw to remember."), result
# The library and the memories are asked too, after Windows.
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "what is the Play button called in Space Trader"})
assert worked and "From your library, Space Trader manual: The Play button is called Start." in result, result
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "which braille display do I have"})
assert worked and "From what you asked VisionClaw to remember: Your braille display is a Brailliant BI 20." in result, result
# Looking things up changes nothing, and the recipes for questions use it.
assert registry.get("look_up").looks and not registry.get("look_up").changes and registry.get("look_up").tell == "summarize"
assert planner.RECIPES["explain_keys"][2] == ("look_up",) and planner.hint(question) == "explain_keys"


class AsInTheRun:
	"""One model for both jobs, asked one small question at a time, as in the run that went wrong."""
	oneModel = True

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"id": "one", "name": "Qwen3.5 9B"}

	def whereText(self):
		return ""

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		schema = options["response_format"]["json_schema"]["schema"]["properties"]
		if "choice" in schema:
			return json.dumps({"choice": "explain_keys"})
		if "line" in schema:
			# A model of this size reads what was found and says whether it answers the question.
			assert "1. From Windows: The desktop: going to it" in messages[-1]["content"]
			return json.dumps({"line": 1})
		raise AssertionError(f"an unexpected question to the model: {messages[-1]['content']}")


runner = orchestrator.Orchestrator(AsInTheRun(), registry, lambda question, choices: 0)
runner.stepwise = lambda: "always"
task = runner.run(taskModule.Task(question))
assert task.state == taskModule.DONE and [step.tool for step in task.steps] == ["look_up", "answer"], (task.state, task.log[-4:])
assert task.answer.startswith(
	"From Windows: The desktop: going to it and navigating its icons with the keyboard. Press Windows+D to go to the desktop;"), task.answer
assert "layout" not in task.answer

# --- Learning about the program in front from the internet, the notes, and questions answered from them ---
from visionClaw import learntools  # noqa: E402
from visionClaw.claw import learn  # noqa: E402

trader = types.SimpleNamespace(appName="spacetrader", productName="", productVersion="2.1")
newGame = types.SimpleNamespace(
	name="New Game", role=Role(name="BUTTON", displayString="button"), value=None, description="", states=[],
	keyboardShortcut="Alt+N", positionInfo={}, appModule=trader, treeInterceptor=None, firstChild=None, next=None)
menuWindow = types.SimpleNamespace(
	name="Space Trader - Main Menu", role=Role(name="WINDOW", displayString="window"), appModule=trader, firstChild=None)
sys.modules["api"].getForegroundObject = lambda: menuWindow
sys.modules["api"].getFocusObject = lambda: newGame
sys.modules["api"].getFocusAncestors = lambda: [types.SimpleNamespace(name="Desktop", role=Role(displayString="window")), menuWindow]
WEB = {
	"https://en.wikipedia.org/w/api.php?action=query&list=search": json.dumps({"query": {"search": [
		{"title": "Space Trader (video game)"}, {"title": "Trader"}]}}),
	"https://en.wikipedia.org/w/api.php?action=query&prop=pageprops": json.dumps({"query": {"pages": {"7": {
		"title": "Space Trader (video game)", "pageprops": {"wikibase_item": "Q7"},
		"extract": "Space Trader is a strategy video game about trading between planets.\n\n== Gameplay ==\n"
			"The player buys and sells goods. Press Ctrl+N to start a new game and F5 to save the game."}}}}),
	"https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity=Q7&property=P2078": json.dumps({"claims": {}}),
	"https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity=Q7&property=P856": json.dumps(
		{"claims": {"P856": [{"mainsnak": {"datavalue": {"value": "https://spacetrader.example.org/"}}}]}}),
	"https://spacetrader.example.org/help/keyboard-shortcuts/": "<html><head><title>Keys</title></head><body><h2>Keyboard shortcuts</h2>"
		"<table><tr><td>Ctrl+S</td><td>Save the game</td></tr><tr><td>Ctrl+L</td><td>Load a game</td></tr></table></body></html>",
	"https://spacetrader.example.org/": "<html><head><title>Space Trader</title></head><body><h2>Controls</h2>"
		"<p>Use the arrow keys to move between planets. Press Enter to land on a planet.</p>"
		"<a href='/help/keyboard-shortcuts/'>Keyboard shortcuts</a> <a href=\"/help/keyboard-shortcuts/\">Keyboard shortcuts</a>"
		"<a href=\"/buy/\">Buy the game</a></body></html>",
}
requests = []


def fakeFetchText(url, timeout=30, limit=None, hosts=None, agent=None, textOnly=False):
	requests.append((url, hosts, agent, textOnly))
	if hosts is not None and url.split("/")[2] not in hosts:
		raise ValueError("The answer came from a place it may not come from.")
	for start, body in WEB.items():
		if url.startswith(start):
			return body
	raise OSError("no such page")


learntools.net.fetchText = fakeFetchText


class LearningModel:
	"""The model's part in learning: it names the program and its kind, writes notes, and says what "this" means."""
	asked = []

	def oneModel(self):
		return True

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"id": "one", "name": "Qwen3.5 9B"}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		user = messages[-1]["content"]
		self.asked.append(user)
		schema = options["response_format"]["json_schema"]["schema"]["properties"]
		if "kind" in schema:
			return json.dumps({"name": next(name for name in schema["name"]["enum"] if "Trader" in name), "kind": "game"})
		if "notes" in schema:
			if "Ctrl+N" in user:
				# One note that stands in the text, and one with a key the text does not have.
				return json.dumps({"notes": ["Ctrl+N starts a new game.", "Press F9 to win the game."]})
			return json.dumps({"notes": []})
		if "about" in schema:
			return json.dumps({"about": len(schema["about"]["enum"])})  # the last thing offered: the focused control
		raise AssertionError(f"an unexpected question to the model: {user}")


realRuntime, instance.runtime = instance.runtime, LearningModel()
notesFile = os.path.join(CONFIG_DIR, "visionClaw", "notes", "spacetrader.md")
questions = []
# The user is asked before anything goes online, whatever the settings say. No: nothing is requested.
instance.clawAsk = lambda question, choices: questions.append((question, choices)) or 1
task = taskModule.Task("Learn about this game")
worked, result = registry.call(task, "learn_app", registry.get("learn_app").autoForm("Learn about this game"))
assert worked and result == "You said no, so VisionClaw did not go online and no notes were made.", result
assert requests == [] and not os.path.exists(notesFile)
question, choices = questions[0]
assert question.startswith(
	"VisionClaw will go online to learn about Space Trader. It sends the name Space Trader to Wikipedia, asks Wikidata "
	"for the address of its website and its manual, and then reads up to 6 help pages straight from that website. "
	"No search engine is used. Nothing else about you or your computer is sent;"), question
assert question.endswith("Go online now?") and choices == ["Yes, go online", "No"]
# The model was asked which name the program is known by, among those plain code found, and what kind it is.
assert any("The possible names: Main Menu; Space Trader; spacetrader" in user for user in LearningModel.asked), LearningModel.asked
assert any(text == (
	"The program in front is spacetrader, with the window Space Trader - Main Menu. The model takes it to be the game "
	"Space Trader.") for _seconds, kind, text in task.log if kind == taskModule.TALK), task.log
# Yes: Wikipedia, Wikidata and the game's own website are read, and nothing else.
instance.clawAsk = lambda question, choices: 0
task = taskModule.Task("Learn about this game")
worked, result = registry.call(task, "learn_app", {"name": "", "asked": "Learn about this game"})
assert worked and result.startswith(
	"VisionClaw learned about the game Space Trader. It read 2 websites (en.wikipedia.org, spacetrader.example.org) and "
	f"kept 4 notes, in the file {notesFile}. 1 of them were put into short points by the model and checked against the page."), result
assert [url.split("?")[0] if "wikipedia" in url else url for url, _h, _a, _t in requests] == [
	"https://en.wikipedia.org/w/api.php", "https://en.wikipedia.org/w/api.php",
	"https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity=Q7&property=P2078",
	"https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity=Q7&property=P856",
	"https://spacetrader.example.org/", "https://spacetrader.example.org/help/keyboard-shortcuts/"], requests
assert "srsearch=Space+Trader+video+game" in requests[0][0]
# Every request says what it is and nothing about the user, and only text is taken.
assert all(agent == "VisionClaw/0.9.0 (NVDA screen reader add-on)" and textOnly for _url, _hosts, agent, textOnly in requests), requests
with open(notesFile, encoding="utf-8") as f:
	kept = f.read()
assert kept.startswith("# Notes on Space Trader (program spacetrader)\n") and "\n## What Space Trader is\n" in kept
# The model's note that stands in the page is kept; the one with a made-up key is not.
assert "\n## Gameplay\n\n- Ctrl+N starts a new game.\n\nSource: https://en.wikipedia.org/wiki/Space_Trader_%28video_game%29\n" in kept, kept
assert "F9" not in kept and "| Ctrl+S | Save the game" in kept
steps = [text for _seconds, kind, text in task.log if kind == taskModule.DETAIL]
assert "Asking Wikipedia about Space Trader." in steps and "Reading Keyboard shortcuts on spacetrader.example.org." in steps
assert "Writing notes on: Gameplay." in steps, steps
assert "learn: Learned about Space Trader (game). Requests went to:" in debuglog.tail(40)

# Questions about the game are now answered from the notes, each saying which website it is from.
task = taskModule.Task("t")
worked, result = registry.call(task, "look_up", {"question": "How do I save my game?"})
assert worked and result.splitlines()[0].startswith("From the notes on Space Trader, from "), result
assert "Save the game" in result.splitlines()[0] or "F5 to save" in result, result
assert any(text.startswith("Asked VisionClaw's notes on Space Trader: ") for _s, kind, text in task.log if kind == taskModule.DETAIL)
# A question that only points is put to the model with where the user is; it says the focused button is meant.
task = taskModule.Task("t")
worked, result = registry.call(task, "look_up", {"question": "What does this do?"})
assert worked and "The focus is on: button \"New Game\". Its own key is Alt+N." in result, result
assert "Ctrl+N starts a new game" in result, result
assert ("The model takes the question to be about the control that has the focus: button \"New Game\"."
	in [text for _s, kind, text in task.log if kind == taskModule.DETAIL]), task.log
assert any("3. the control that has the focus: button \"New Game\"" in user for user in LearningModel.asked)
# Which notes there are.
worked, result = registry.call(taskModule.Task("t"), "app_notes", {"asked": "Which notes do you have?"})
assert worked and result.startswith("VisionClaw has notes on 1 program: Space Trader, 4 notes from "), result
assert result.endswith("There are notes on the program you are in, spacetrader."), result
# A page the user has open in their own browser is added to the notes; nothing is fetched for it.
del requests[:]
learntools.webtools.pageText = lambda: (
	"Space Trader tips", "Tips\nTrading\nPress T to trade and B to buy. Press Ctrl+T to open the trade screen.\nAbout\nWe like games.")
learntools.webtools.page = lambda: "document"
learntools.webtools.address = lambda document: "https://tips.example.net/space-trader"
learntools.webtools.headings = lambda: [(2, "Trading", None), (2, "About", None)]
form = registry.get("note_page").autoForm("Add this page to the notes on Space Trader")
assert form["name"] == "Space Trader"
worked, result = registry.call(taskModule.Task("t"), "note_page", form)
assert worked and result.startswith(
	f"Added 1 note from the page Space Trader tips to the notes on Space Trader, in the file {notesFile}. Nothing was "
	"fetched from the internet for this"), result
assert requests == []
with open(notesFile, encoding="utf-8") as f:
	kept = f.read()
assert "\n## Trading\n\nPress T to trade and B to buy." in kept and kept.rstrip().endswith("Source: https://tips.example.net/space-trader")
worked, result = registry.call(taskModule.Task("t"), "note_page", {"name": "", "asked": "add this page to my notes"})
assert not worked and "does not say which program the page is about" in result, result
# The notes are deleted when the user asks, and then a question says how to get some.
worked, result = registry.call(taskModule.Task("t"), "forget_notes", {"which": "Delete the notes on this program"})
assert worked and result == "Deleted the notes on Space Trader. VisionClaw has no notes left.", result
assert not os.path.exists(notesFile)
worked, result = registry.call(taskModule.Task("t"), "forget_notes", {"which": "delete all notes"})
assert worked and result == "VisionClaw has no notes on any program, so there is nothing to delete.", result
worked, result = registry.call(taskModule.Task("t"), "look_up", {"question": "How do I bake a walnut cake?"})
assert worked and result.endswith(
	"VisionClaw has no notes on this program yet. Ask it to learn about this program, and it reads up on it on the "
	"internet after asking you."), result
for name in ("learn_app", "note_page", "forget_notes"):
	assert registry.get(name).changes and registry.get(name).tell == "verbatim"
assert planner.hint("Learn about this game") == "learn_app" and planner.RECIPES["learn_app"][2] == ("learn_app",)
instance.runtime = realRuntime

# --- How VisionClaw answers: the user's own instructions and wording (claw/prompts.py) ---
from visionClaw.claw import prompts  # noqa: E402

vc = conf["visionClaw"]
assert vc["ownInstructions"] == "" and not any(prompts.isCustom(p) for p in prompts.PARTS)
instance.showAnswers()
answersDialog = instance._answersDialog
# Every part the user may rewrite is listed, the user's own instructions first, and each says if it was changed.
assert [key for key, _name in answersDialog._names] == ["own"] + list(prompts.PARTS)
assert all(value == "" for value in answersDialog._values.values())
assert answersDialog._label("speaking") == "How answers are worded" and answersDialog._label("own").endswith("(none)")
answersDialog._values["speaking"] = prompts.SPEAKING
assert not answersDialog._changed("speaking")
answersDialog._values["speaking"] = "Shout."
assert answersDialog._label("speaking") == "How answers are worded (changed)"
# The user writes instructions of their own and rewrites two parts; a part given back as it was stays "".
answersDialog._onSave({"own": "Call me Sam\nKeep it short", "user": prompts.USER, "speaking": prompts.SPEAKING,
	"seeing": "Say the colours of everything.", "brief": "Say only what the picture is."})
assert vc["ownInstructions"] == "Call me Sam. Keep it short." and vc["promptUser"] == "" and vc["promptSpeaking"] == ""
assert vc["promptSeeing"] == "Say the colours of everything." and prompts.customized() == ["seeing", "brief"]
assert prompts.part("brief") == "Say only what the picture is." and prompts.part("quick") == prompts.QUICK
# Opened again, the window shows what the user wrote, and the original where they wrote nothing.
instance._answersDialog = None
instance.showAnswers()
assert instance._answersDialog._values["seeing"] == "Say the colours of everything."
assert instance._answersDialog._values["user"] == "" and instance._answersDialog._defaults["user"] == prompts.USER
# Every description gets them, as the first message to the model.
systems = []
instance.runtime = types.SimpleNamespace(
	describe=lambda image, prompt, maxTokens, cancel=None, system=None: systems.append(system) or "A menu.")
instance._grab = lambda box: Image.new("RGB", (64, 64), "white")
worked, result = registry.call(taskModule.Task("t"), "look", {"target": "screen", "question": "What is shown?"})
assert worked and result == "A menu." and "Call me Sam" in systems[0] and "Say the colours of everything." in systems[0]
assert prompts.SEEING not in systems[0] and prompts.USER in systems[0]
# Settings saved again keep them; VisionClaw's own wording comes back when the user empties the box.
instance.runtime = realRuntime
instance.onSettingsSaved()
assert prompts.own() == "Call me Sam. Keep it short."
instance._answersDialog = None
instance.showAnswers()
# Restoring every original: the window empties every box, and OK keeps VisionClaw's own wording.
instance._answersDialog._onSave({key: "" for key, _name in instance._answersDialog._names})
assert vc["promptSeeing"] == "" and vc["promptBrief"] == "" and prompts.own() == "" and prompts.customized() == []
assert prompts.part("seeing") == prompts.SEEING and prompts.part("brief") == prompts.BRIEF
instance.runtime = realRuntime

# Skills (skilltools.py): made in the user's own words, listed, read, turned off and on, deleted. The words
# that start a new skill are kept only where the user said them; what it tells VisionClaw is the user's words.
skillQuestions = []
conf["visionClaw"]["confirmChanges"] = True
instance.clawAsk = lambda question, choices: skillQuestions.append(question) or 0
assert instance.orchestrator.skills is instance.skills and len(instance.skills.all()) >= 30
asked = "Make a new skill: when I ask about recipes, read the ingredients first, with their amounts exactly."
worked, result = registry.call(taskModule.Task(asked), "add_skill", {
	"name": "Recipes", "when": "recipes, cooking, ingredients, kitchen", "asked": asked})
assert worked and result.startswith("Saved the skill Recipes. It is used when your request says: recipes; ingredients."), result
assert "NVDA+alt+i" in result and "Save a new skill called Recipes?" in skillQuestions[-1]
made = instance.skills.get("recipes")
assert made.source == "yours" and made.instructions == (
	"When I ask about recipes, read the ingredients first, with their amounts exactly."), made.instructions
assert os.path.isfile(os.path.join(instance.skills.folder, "recipes", "SKILL.md"))
assert instance.skills.choose("read the ingredients of this recipe")[0].slug == "recipes"
# Words the user never said cannot start it.
worked, result = registry.call(taskModule.Task("t"), "add_skill", {
	"name": "Banking", "when": "bank, money", "asked": "make a skill to read amounts exactly"})
assert not worked and "Say in the request which words" in result, result
worked, result = registry.call(taskModule.Task("t"), "list_skills", {"asked": "which skills do you have"})
assert worked and result.startswith("VisionClaw has ") and "Recipes (yours)" in result, result
worked, result = registry.call(taskModule.Task("t"), "list_skills", {"asked": "which skills are about charts"})
assert worked and "Understand a chart, graph or diagram" in result and "Recipes" not in result, result
worked, result = registry.call(taskModule.Task("t"), "show_skill", {"skill": "x", "asked": "what does the chart skill do"})
assert worked and result.startswith("Understand a chart, graph or diagram:") and "Used when your request says:" in result, result
# The user's own words decide which skill is meant, whatever the model wrote.
worked, result = registry.call(taskModule.Task("t"), "manage_skill", {
	"skill": "Shop online safely", "action": "turn off", "asked": "turn off the game skill"})
assert worked and result == "The skill Play a game the screen reader cannot read is off. It can be turned on again.", result
assert not instance.skills.get("game").on
worked, result = registry.call(taskModule.Task("t"), "manage_skill", {
	"skill": "game", "action": "turn on", "asked": "turn on the game skill"})
assert worked and instance.skills.get("game").on
# A built-in skill is turned off, after a question, instead of being deleted.
worked, result = registry.call(taskModule.Task("t"), "manage_skill", {
	"skill": "chart", "action": "delete", "asked": "delete the chart skill"})
assert worked and "comes with VisionClaw, so it was turned off" in result and not instance.skills.get("chart").on, result
assert "cannot be deleted. Turn it off instead?" in skillQuestions[-1]
instance.skills.setOn("chart", True)
# Saying no keeps the user's skill.
instance.clawAsk = lambda question, choices: skillQuestions.append(question) or 1
worked, result = registry.call(taskModule.Task("t"), "manage_skill", {
	"skill": "Recipes", "action": "delete", "asked": "delete my recipes skill"})
assert worked and "nothing was changed" in result and instance.skills.get("recipes") is not None, result
instance.clawAsk = lambda question, choices: skillQuestions.append(question) or 0
worked, result = registry.call(taskModule.Task("t"), "manage_skill", {
	"skill": "Recipes", "action": "delete", "asked": "delete my recipes skill"})
assert worked and result == "Your skill Recipes was deleted." and instance.skills.get("recipes") is None, result
assert "Delete your skill Recipes?" in skillQuestions[-1]
# The skills window (skillsui.py) needs real wx lists, which the stand-in does not have; it is tested in NVDA.

instance.terminate()
print("OK")
