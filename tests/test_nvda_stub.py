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
stub("brailleInput", handler=types.SimpleNamespace(sendChars=typed.append))
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
	"buildVersion", "brailleTables",
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
from visionClaw import nvdatools, webtools  # noqa: E402
from visionClaw.claw import orchestrator, planner  # noqa: E402
from visionClaw.claw import task as taskModule  # noqa: E402
from visionClaw.claw.catalog import CODER, VISION  # noqa: E402

# --- The plugin starts, and every tool and recipe is in place ---

instance = plugin.GlobalPlugin()
registry = instance.orchestrator.registry
assert len(registry.names()) == 28, registry.names()
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

# Every setting the synthesizer itself offers can be changed, not only rate, pitch and volume.
worked, result = registry.call(task, "find_setting", {"words": "change the voice"})
assert worked and "speech.voice: speech voice. Now: Anna. Allowed: one of: Anna, Ben." in result, result
worked, result = registry.call(task, "set_setting", {"setting": "speech.voice", "value": "ben"})
assert worked and synth.voice == "v2" and conf["speech"]["fake"]["voice"] == "v2", result
worked, result = registry.call(task, "set_setting", {"setting": "speech.rateBoost", "value": "on"})
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
worked, result = registry.call(task, "set_setting", {"setting": "speech.volume", "value": "0"})
assert worked and synth.volume == 100 and "too quiet to hear, and there is no braille display" in result, result
instance.clawAsk = lambda question, choices: 0
worked, result = registry.call(task, "set_setting", {"setting": "speech.volume", "value": "40"})
assert worked and synth.volume == 40

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


def node(label):
	return types.SimpleNamespace(label=label, activate=lambda: activated.append(label))


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
assert worked and result.startswith("5 items on the web page Example Shop:\n1. Sign in link"), result
assert "Buy now button" in result and "Search the shop edit field" in result
# Following a link needs no question; pressing a button does.
conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(task, "click_item", {"item": "Sign in"})
assert worked and activated == ["Sign in"] and not questions and result == "Clicked Sign in link.", result
registry.call(task, "list_items", {"about": "buy"})
worked, result = registry.call(task, "click_item", {"item": "the Buy now button"})
assert worked and activated[-1] == "Buy now" and questions == ["Click Buy now button?"], (result, questions)
# Typing into a field: "the search box" finds the page's one field; Enter is pressed when asked.
registry.call(task, "list_items", {"about": "search box"})
worked, result = registry.call(task, "fill_field", {"field": "the search box", "text": "cats", "enter": "yes"})
assert worked and activated[-1] == "Search the shop" and typed == ["cats"], result
assert result == "Typed \"cats\" into Search the shop edit field and pressed Enter.", result
assert questions[-1] == "Type \"cats\" into Search the shop edit field?"
conf["visionClaw"]["confirmChanges"] = False
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

instance.terminate()
print("OK")
