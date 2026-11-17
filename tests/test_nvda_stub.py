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


class Synth:
	name = "fake"
	rate, pitch, volume = 50, 40, 100
	voice = "v1"
	availableVoices = {"v1": Anything(), "v2": Anything()}

	def isSupported(self, setting):
		return setting in ("rate", "pitch", "volume")


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
stub("synthDriverHandler", getSynth=lambda: synth)
stub("wx", IsMainThread=lambda: True, CallAfter=lambda fn, *args: fn(*args), CallLater=lambda ms, fn, *args: None)
stub("inputCore", normalizeGestureIdentifier=lambda ident: ident.lower())
stub("keyboardHandler", KeyboardInputGesture=types.SimpleNamespace(
	fromName=lambda name: (_ for _ in ()).throw(LookupError(name)) if "bogus" in name else Anything()))
for name in (
	"api", "controlTypes", "gui", "gui.guiHelper", "gui.settingsDialogs", "languageHandler", "queueHandler", "speech",
	"speech.extensions", "textInfos", "ui", "contentRecog", "contentRecog.recogUi", "contentRecog.uwpOcr",
	"documentationUtils", "globalCommands", "mouseHandler", "winUser", "brailleInput", "NVDAObjects", "core",
	"screenCurtain", "vision", "locationHelper", "winVersion", "tones", "nvwave", "appModuleHandler", "eventHandler",
	"NVDAObjects.UIA", "NVDAObjects.IAccessible", "UIAHandler", "braille", "winKernel", "browseMode", "cursorManager",
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
from visionClaw import nvdatools  # noqa: E402
from visionClaw.claw import orchestrator, planner  # noqa: E402
from visionClaw.claw import task as taskModule  # noqa: E402
from visionClaw.claw.catalog import CODER, VISION  # noqa: E402

# --- The plugin starts, and every tool and recipe is in place ---

instance = plugin.GlobalPlugin()
registry = instance.orchestrator.registry
assert len(registry.names()) == 21, registry.names()
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
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "+10"})
assert worked and synth.rate == 60 and result == "Speech rate was 50 and is now 60.", result
assert conf["speech"]["fake"]["rate"] == 60
worked, result = registry.call(task, "set_setting", {"setting": "speech_rate", "value": "/80"})
assert worked and synth.rate == 80, result  # a near miss of the id and a stray character are forgiven
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "500"})
assert not worked and "outside the allowed range" in result and synth.rate == 80
worked, result = registry.call(task, "set_setting", {"setting": "keyboard.speakTypedCharacters", "value": "off"})
assert worked and conf["keyboard"]["speakTypedCharacters"] is False
worked, result = registry.call(task, "set_setting", {"setting": "speech.symbolLevel", "value": "all"})
assert worked and conf["speech"]["symbolLevel"] == 300 and result.endswith("is now all."), result
worked, result = registry.call(task, "set_setting", {"setting": "nothing.here", "value": "on"})
assert not worked and "Copy an id exactly from find_setting" in result

# The user is asked before a change, and saying no changes nothing.
conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "20"})
assert worked and result == "You said no, so nothing was changed." and synth.rate == 80
assert questions == ["Change speech rate from 80 to 20?"], questions
instance.clawAsk = lambda question, choices: 0
worked, result = registry.call(task, "set_setting", {"setting": "speech.rate", "value": "20"})
assert worked and synth.rate == 20
conf["visionClaw"]["confirmChanges"] = False

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

instance.terminate()
print("OK")
