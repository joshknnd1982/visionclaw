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
assert len(registry.names()) == 41, registry.names()
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
worked, result = registry.call(task, "remember", {"note": "In Space Trader the Play button is called Start."})
assert worked and instance.memory.search("Space Trader Play button")
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
# Pointing at something asks nothing, presses nothing, and leaves the pointer there.
fresh()
asked = len(questions)
worked, result = registry.call(task, "click_item", {"item": "Trash", "action": "hover", "asked": ""})
assert worked and result == "The mouse pointer is on Trash icon." and buttons == [] and moves == [(500, 400)]
assert len(questions) == asked
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
instance.pointerMode.stop()
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

# What looking for newer models found is said in plain sentences.
from visionClaw import dialogs  # noqa: E402

assert dialogs.lookResult({"new": ["Qwen9 1B", "Qwen9 Coder 1B"], "tooNew": 1, "refused": 2, "updated": "2027-03-01"}) == (
	"2 models were added to the lists: Qwen9 1B, Qwen9 Coder 1B. The list was last brought up to date on 2027-03-01. "
	"1 newer models need a newer version of VisionClaw and are not offered here. "
	"2 entries of the list were left out, because they did not pass VisionClaw's checks.")
assert dialogs.lookResult({"new": [], "tooNew": 0, "refused": 0, "updated": ""}) == (
	"There are no newer models. The lists here already offer every model on VisionClaw's list.")

instance.terminate()
print("OK")
