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
import shutil
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
# VisionClaw keeps its data in its own add-on folder (claw/portable.py). Here that is a folder of the test's own,
# so that the test never writes into this repository.
DATA = os.path.join(CONFIG_DIR, "addons", "visionClaw", "data")
assert plugin.DATA_DIR == os.path.join(plugin.ADDON_DIR, "data"), plugin.DATA_DIR
assert plugin.OLD_DATA_DIR == os.path.join(CONFIG_DIR, "visionClaw"), plugin.OLD_DATA_DIR
plugin.DATA_DIR, plugin.MODELS_DIR = DATA, os.path.join(DATA, "models")
from visionClaw import mousetools, nvdatools, padtools, webtools  # noqa: E402
from visionClaw.claw import guides as shippedGuides  # noqa: E402

# The guide that comes with every build is put aside: the tests below are about what the user downloads.
# tests/test_guides.py checks the one that comes with VisionClaw.
SHIPPED_GUIDES = shippedGuides.SHIPPED
shippedGuides.SHIPPED = ""
# Nothing really moves the mouse during the tests: every move and button is only written down.
moves, buttons = [], []
# The real functions are kept: where the mouse itself is moved for a game, they are tested with what is below
# them stood in for.
realMoveTo, realPosition = mousetools.moveTo, mousetools.position
# No game controller is read during the tests, whatever is plugged into this computer, and Windows' facts
# about its mouse pointer are the usual ones.
padtools._find = lambda joysticks=True: None
padtools._vibrate = lambda device, left, right: None
mousetools.pointerState = lambda box=None: {"showing": True, "confined": False, "inside": False}
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
# Whether Shift, Control or Alt is down is not read from the real keyboard: these are the keys held down.
keysHeld = set()
mousetools._keyDown = lambda code: code in keysHeld
mousetools._REST = 0
nvdatools.typeUnicode = typed.append  # nothing is really typed into the computer during the tests
# Nothing on the real computer is opened, emptied, closed, made louder or quieter, locked or shut down during the
# tests, and nothing is read from it either: every function of computertools.py that does something only writes
# down what would have happened, and what the computer would be asked is made up here.
from visionClaw import computertools  # noqa: E402
from visionClaw.claw import computer  # noqa: E402

did = []
pc = {
	"bin": (3, 5 << 20), "volume": 40, "muted": False, "refuse": False,
	"windows": [
		{"hwnd": 11, "title": "Inbox (3) - sam@example.com - Gmail - Google Chrome", "app": "chrome", "front": True, "minimized": False},
		{"hwnd": 12, "title": "Settings", "app": "ApplicationFrameHost", "front": False, "minimized": False},
		{"hwnd": 13, "title": "notes.txt - Notepad", "app": "notepad", "front": False, "minimized": True},
	],
	"files": [
		("setup.exe", "Downloads", 5 << 20, 1795000000.0, False, r"C:\Users\sam\Downloads\setup.exe"),
		("budget 2026.xlsx", "Documents", 20000, 1790000000.0, False, r"C:\Users\sam\Documents\budget 2026.xlsx"),
	],
}


def fakeOpen(target, arguments=None):
	if pc["refuse"]:
		raise OSError("Windows did not open it (its answer was 2).")
	did.append(("open", target, arguments))


def fakeEmpty():
	did.append(("empty",))
	pc["bin"] = (0, 0)


def fakeSetVolume(level):
	did.append(("volume", level))
	pc["volume"] = level
	return level


def fakeSearch(wish, cancel=None):
	hits = [hit for hit in pc["files"] if hit[1].lower() in wish["folders"] and computer.fileFits(hit[0], wish)]
	shown = [(name, where, size, "November 18, 2026", isFolder) for name, where, size, _changed, isFolder, _path in hits]
	return shown, hits, [key.capitalize() for key in wish["folders"]], False


computertools.shellOpen = fakeOpen
computertools.emptyBin = fakeEmpty
computertools.binInfo = lambda: pc["bin"]
computertools.systemDrive = lambda: (200 << 30, 500 << 30)
computertools.volumeNow = lambda: (pc["volume"], pc["muted"])
computertools.setVolume = fakeSetVolume
computertools.setMute = lambda muted: (did.append(("mute", muted)), pc.__setitem__("muted", muted))[0]
computertools.openWindows = lambda: [dict(window) for window in pc["windows"]]
computertools.focusWindow = lambda hwnd: did.append(("focus", hwnd)) or True
computertools.closeWindow = lambda hwnd: did.append(("close", hwnd)) or hwnd != 13
computertools.showWindow = lambda hwnd, action: did.append((action, hwnd))
computertools.minimizeAll = lambda: did.append(("minimize all",))
computertools.pressEscape = lambda: did.append(("escape",))
computertools.pressShortcut = lambda keys: did.append(("keys", keys))
computertools.PART_SETTLE_SECONDS = 0
computertools.power = lambda what: did.append(("power", what))
computertools.drives = lambda: [("C:", "System", 200 << 30, 500 << 30)]
computertools.memory = lambda: (21 << 30, 31 << 30)
computertools.upSeconds = lambda: 86400 + 9 * 3600
computertools.processorText = lambda: "The processor is a Test Chip, with 16 threads."
computertools.networkText = lambda: "Windows says this computer is connected to a network."
computertools.systemText = lambda: "This computer is called TESTPC. You are signed in as sam. Windows is version 10.0, build 26300."
computertools.gather = lambda: computer.places() + [
	computer.thing("desktop", "Firefox", computer.ON_DESKTOP, r"C:\Users\sam\Desktop\Firefox.lnk"),
	computer.thing("program", "Space Trader", computer.PROGRAM, r"C:\Start\Space Trader.lnk"),
	computer.thing("program", "Space Trader Editor", computer.PROGRAM, r"C:\Start\Space Trader Editor.lnk")]
realSearchFiles, realUserFolders = computertools.searchFiles, computertools.userFolders
computertools.searchFiles = fakeSearch
# Nothing is really moved to the Recycle Bin: what would be is written down, and taken away as Windows would.
recycled = []


def fakeRecycle(path):
	recycled.append(path)
	import shutil as shutilForTest
	shutilForTest.rmtree(path) if os.path.isdir(path) else os.remove(path)


computertools.recycle = fakeRecycle
computertools.browserPath = lambda exe: r"C:\Chrome\chrome.exe" if exe == "chrome.exe" else None
# The places of Windows itself (placetools.py): nothing is read from this computer's real taskbar. The taskbar is
# what Windows 11 reported on the owner's computer on 2026-11-18, in the same shape; the hidden icons, the desktop
# and quick settings are made up.
from visionClaw import placetools  # noqa: E402

_bar = lambda x: (x, 1198, x + 40, 1258)  # noqa: E731
TASKBAR = [
	{"name": "Start", "kind": 50000, "cls": "ToggleButton", "aid": "StartButton", "box": _bar(708)},
	{"name": "Search", "kind": 50000, "cls": "ToggleButton", "aid": "SearchButton", "box": _bar(764)},
	{"name": "", "kind": 50006, "cls": "Microsoft.UI.Xaml.Controls.AnimatedVisualPlayer", "aid": "Icon", "box": _bar(777)},
	{"name": "Microsoft Edge pinned", "kind": 50000, "cls": "Taskbar.TaskListButtonAutomationPeer", "aid": "Appid: MSEdge", "box": _bar(819)},
	{"name": "Claude - 1 running window", "kind": 50000, "cls": "Taskbar.TaskListButtonAutomationPeer", "aid": "Window: 0x2a04f6", "box": _bar(874)},
	{"name": "Show Hidden Icons", "kind": 50000, "cls": "SystemTray.NormalButton", "aid": "SystemTrayIcon", "box": _bar(1663)},
	{"name": "Network JoshKennedy\nInternet access", "kind": 50000, "cls": "SystemTray.AccentButton", "aid": "SystemTrayIcon", "box": _bar(1708)},
	{"name": "Volume Speakers (Realtek(R) Audio): 20%", "kind": 50000, "cls": "SystemTray.OmniButtonCenter", "aid": "SystemTrayIcon", "box": _bar(1743)},
	{"name": "Power Battery status: fully charged 100%", "kind": 50000, "cls": "SystemTray.AccentButton", "aid": "SystemTrayIcon", "box": _bar(1778)},
	{"name": "Clock 10:29 PM\n\u200e11/\u200e18/\u200e2026", "kind": 50000, "cls": "SystemTray.OmniButton", "aid": "SystemTrayIcon", "box": _bar(1823)},
]
HIDDEN = [
	{"name": "NVDA", "kind": 50000, "cls": "SystemTray.NormalButton", "aid": "NotifyItemIcon", "box": None, "hidden": True},
	{"name": "Dropbox\nUp to date", "kind": 50000, "cls": "SystemTray.NormalButton", "aid": "NotifyItemIcon", "box": None, "hidden": True},
]
front = {"app": "explorer", "class": "Progman"}
# Showing the hidden icons, reading them and hiding them again, with stand-ins for Windows: Windows 11 moves the
# focus to them and leaves it on the taskbar after; the window that was in front is brought back (2026-11-18).
flyout = {"shown": False, "front": 5}


def fakeInvoke(element):
	did.append(("invoke", element))
	flyout["shown"] = not flyout["shown"]
	flyout["front"] = 77 if flyout["shown"] else 9
	return True


realLow = (placetools._overflow, placetools._visible, placetools._invoke, placetools._foreground, placetools._readAll)
placetools._overflow = lambda: (77 if flyout["shown"] else 0, False)
placetools._visible = lambda hwnd: hwnd == 77 and flyout["shown"]
placetools._invoke = fakeInvoke
placetools._foreground = lambda: flyout["front"]
placetools._readAll = lambda hwnds, hidden=False: [dict(item, hidden=True) for item in HIDDEN] if hwnds == [77] else []
placetools._POLL = 0.01
del did[:]
chevronItem = dict(TASKBAR[5], element="the chevron")
found, read = placetools.hiddenItems([chevronItem], lambda fn, *args: fn(*args))
assert read and [item["name"] for item in found] == ["NVDA", "Dropbox\nUp to date"], found
assert did == [("invoke", "the chevron"), ("invoke", "the chevron"), ("focus", 5)] and not flyout["shown"], did
# No button that shows them: nothing is pressed, and they are said not to have been read.
del did[:]
assert placetools.hiddenItems([TASKBAR[6]], lambda fn, *args: fn(*args)) == ([], False) and did == []
(placetools._overflow, placetools._visible, placetools._invoke, placetools._foreground, placetools._readAll) = realLow
placetools.trayItems = lambda: [dict(item) for item in TASKBAR]
placetools.hiddenItems = lambda shown, onMain: (did.append(("hidden icons",)) or [dict(item) for item in HIDDEN], True)
placetools.desktopItems = lambda: [
	{"name": name, "kind": 50007, "cls": "", "aid": "", "box": (0, 4 + 152 * i, 109, 122 + 152 * i)}
	for i, name in enumerate(("This PC", "Recycle Bin", "Firefox", "Steam"))]
placetools.frontApp = lambda: front["app"]
placetools.frontClass = lambda: front["class"]
placetools.frontItems = lambda: [
	{"name": "Wi-Fi", "kind": 50000, "state": "on"}, {"name": "Bluetooth", "kind": 50000, "state": "off"},
	{"name": "Volume", "kind": 50015, "state": "20"}, {"name": "", "kind": 50033}]
placetools.OPEN_WAIT, placetools._POLL = 0.6, 0.01
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
# What VisionClaw 1.3.0 kept in NVDA's configuration folder is moved into the add-on's data folder at start,
# and settings that came with a portable copy are taken over by a VisionClaw with no models chosen.
with open(os.path.join(CONFIG_DIR, "visionClaw", "labels.json"), "w", encoding="utf-8") as f:
	f.write("{}")
os.makedirs(DATA, exist_ok=True)
with open(os.path.join(DATA, "labels.json"), "w", encoding="utf-8") as f:
	f.write('{"from": "a portable copy"}')
with open(os.path.join(DATA, "carried-settings.json"), "w", encoding="utf-8") as f:
	json.dump({"searchEngine": "bing", "updateLastCheck": "123", "noSuchSetting": 1}, f)
instance = plugin.GlobalPlugin()
assert not os.path.exists(os.path.join(CONFIG_DIR, "visionClaw")), os.listdir(os.path.join(CONFIG_DIR, "visionClaw"))
assert os.path.isfile(os.path.join(DATA, "lessons.json"))
# Where both had a file, this computer's own is kept.
assert open(os.path.join(DATA, "labels.json"), encoding="utf-8").read() == "{}"
assert conf["visionClaw"]["searchEngine"] == "bing" and conf["visionClaw"]["updateLastCheck"] == ""
assert not os.path.exists(os.path.join(DATA, "carried-settings.json"))
conf["visionClaw"]["searchEngine"] = "duckduckgo"
assert instance.dataDir == DATA and instance.portableSettings()["searchEngine"] == "duckduckgo"
# The controller is looked for by a thread of its own; here every look is made by the test.
instance.controller._stopped.set()
instance.controller._thread.join(5)
registry = instance.orchestrator.registry
assert len(registry.names()) == 123, registry.names()
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
assert json.load(open(os.path.join(DATA, "helpers.json")))["spacetrader"]
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
# A button that buys is always asked about, with what the page says is to be paid, and not asked about a second time.
assert worked and activated[-1] == "Buy now" and len(questions) == 1 and questions[0].startswith("\"Buy now\" buys, books or pays."), (result, questions)
# The user says no to it: nothing is pressed, and the answer says that nothing was bought. With confirmations
# turned off it is asked about all the same.
registry.call(task, "list_items", {"about": "buy"})
pressedBefore = list(activated)
conf["visionClaw"]["confirmChanges"] = False
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(task, "click_item", {"item": "the Buy now button", "action": "click", "asked": ""})
assert worked and activated == pressedBefore and len(questions) == 2, (result, questions)
assert result == "Nothing was clicked: \"Buy now button\" was not pressed, so nothing was bought, booked or paid.", result
conf["visionClaw"]["confirmChanges"] = True
instance.clawAsk = lambda question, choices: questions.append(question) or 0
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
worked, result = registry.call(task, "web_open", {"address": "bbc.co.uk", "asked": "Open bbc.co.uk"})
assert worked and opened == ["https://bbc.co.uk"] and result == "Opened the web page BBC Home.", result
# A browser the user names is used where it is installed; where it is not, the usual one is, and that is said.
del did[:]
worked, result = registry.call(task, "web_open", {"address": "bbc.co.uk", "asked": "go to bbc.co.uk in my google chrome"})
assert worked and did == [("open", r"C:\Chrome\chrome.exe", "https://bbc.co.uk")], (result, did)
assert result.endswith("It was opened in Google Chrome.") and opened == ["https://bbc.co.uk"], result
worked, result = registry.call(task, "web_open", {"address": "bbc.co.uk", "asked": "open bbc.co.uk with opera"})
assert worked and result == (
	"Opened the web page BBC Home. Opera was not found on this computer, so your usual browser was used."), result
del opened[1:]
for bad, why in (("javascript:alert(1)", "Only web addresses"), ("the bbc", "is not a web address"), ("", "is not a web address")):
	worked, result = registry.call(task, "web_open", {"address": bad, "asked": "open " + bad})
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
	# Who picks the model for each job (claw/modelpick.py): the user, by default; with "VisionClaw picks", the models on
	# the disk for each request, handed to the runtime by _runtimeSettings, said with the progress and when asked. A
	# stand-in graphics card, so that the engine is never started to list the real ones.
	from visionClaw.claw import backend as pickBackend  # noqa: E402
	realPickDevices = instance.runtime.devices
	instance.runtime.devices = lambda refresh=False: [pickBackend.Device("0", "Test card", 8151, 8000, True)]
	assert conf["visionClaw"]["modelPick"] == "mine" and plugin._runtimeSettings()["coderModel"] == "nine-coder"
	instance._pickModels(taskModule.Task("write an add-on"))  # the user's own choice: nothing is picked
	assert not plugin._PICKED and plugin._runtimeSettings()["coderModel"] == "nine-coder"
	said = instance.modelPickText()
	assert said.startswith("Of the models on this computer, VisionClaw would choose differently. For writing code it would "
		"pick Qwen2.5 Coder 1.5B"), said
	conf["visionClaw"]["modelPick"] = "auto"
	pickTask = taskModule.Task("write an add-on that beeps when a link gets the focus")
	instance._pickModels(pickTask)
	assert plugin._runtimeSettings()["visionModel"] == "four" and plugin._runtimeSettings()["coderModel"] == "coder", plugin._PICKED
	assert instance.runtime.entry(CODER)["id"] == "coder"
	assert any("For writing code, Qwen2.5 Coder 1.5B" in str(entry) for entry in pickTask.log), pickTask.log
	said = instance.modelPickText()
	assert said.startswith("VisionClaw picks the model for each job itself") and "Last time: For planning what to do" in said, said
	conf["visionClaw"]["modelPick"] = "mine"
	assert plugin._runtimeSettings()["coderModel"] == "nine-coder" and instance.runtime.entry(CODER)["id"] == "nine-coder"
	plugin._PICKED.clear()
	instance.runtime.devices = realPickDevices
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
# The Start button is on the taskbar, not in the window in front. The owner's requests of 2026-11-18: the model
# chose an unrelated item, or wrote a sentence that "te" was found in. Now the Start menu is opened with its key.
del did[:]
for asked, reference in (("click the windows start button using the mouse.", "10"),
		("open the windows start menu.", "None of the items in the list is the Windows Start menu.")):
	fresh()
	before = len(questions)
	worked, result = registry.call(task, "click_item", {"item": reference, "action": "click", "asked": asked})
	assert worked and result.startswith("That is not in the window in front: it is part of Windows itself. VisionClaw "
		"opened the Start menu with the Windows key, or Control+Escape"), result
	assert did[-1] == ("keys", "control+escape") and buttons == [] and len(questions) == before, (did, questions)
# Where the words could also mean a Start button of the program in front, the user is asked first.
fresh()
worked, result = registry.call(task, "click_item", {"item": "Volume", "action": "click", "asked": "click the start button."})
assert questions[-1] == "Nothing in this window is called start. Open the Start menu of Windows instead?", questions[-1]
assert worked and did[-1] == ("keys", "control+escape") and buttons == [], result
instance.clawAsk = lambda question, choices: questions.append(question) or 1
fresh()
worked, result = registry.call(task, "click_item", {"item": "Volume", "action": "click", "asked": "click the start button."})
assert worked and result == "You said no, so nothing was changed." and buttons == [], result
# An item that has none of the words the user said is never clicked without a question that says so.
fresh()
worked, result = registry.call(task, "click_item", {"item": "Volume", "action": "click", "asked": "click the zebra button"})
assert questions[-1] == "Nothing in this window is called zebra. The closest found is Volume slider. Use it anyway?", questions[-1]
assert worked and result.startswith("Nothing was clicked: nothing in the window in front is called zebra") and buttons == [], result
instance.clawAsk = lambda question, choices: questions.append(question) or 0
fresh()
worked, result = registry.call(task, "click_item", {"item": "not found", "action": "click", "asked": "click the zebra button"})
assert worked and result.startswith("Nothing was clicked: nothing in the window in front is called zebra") and buttons == [], result
# A program or place of Windows that is named and is not in the window is offered to be opened by its name.
fresh()
worked, result = registry.call(task, "click_item", {"item": "File", "action": "click", "asked": "click the recycle bin"})
assert questions[-1] == "Nothing in this window is called recycle bin. Open Recycle Bin, a place of Windows, instead?", questions[-1]
assert worked and result.startswith("Nothing in the window in front was called recycle bin, so VisionClaw opened Recycle Bin"), result
assert buttons == []
# The part of Windows by its own tool.
worked, result = registry.call(task, "windows_part", {"asked": "go to the system tray"})
assert worked and did[-1] == ("keys", "windows+b") and result.startswith("Opened the notification area with Windows+B."), result
worked, result = registry.call(task, "windows_part", {"asked": "make nvda speak faster"})
assert not worked and "does not name a part of Windows" in result, result
# What is in the system tray, read from what Windows reports, by plain code: the owner's request of 2026-11-18,
# which a picture of the desktop answered with "I cannot see the system tray in this image". The hidden icons are
# read too; nothing is clicked and no key is pressed.
del did[:]
fresh()
worked, result = registry.call(task, "read_place", {"asked": "tell me all objects that are currently in the system tray."})
assert worked and result.startswith(
	"The notification area has 3 icons shown on the taskbar. They are: Network JoshKennedy, Internet access; Volume "
	"Speakers (Realtek(R) Audio): 20%; Power Battery status: fully charged 100%. Hidden behind Show hidden icons, 2 more "
	"icons: NVDA; Dropbox, Up to date. The clock says: 10:29 PM, 11/18/2026. To go to the notification area yourself, "
	"press Windows+B."), result
assert did == [("hidden icons",)] and buttons == [] and moves == [], (did, buttons)
worked, result = registry.call(task, "read_place", {"asked": "is NVDA running in the system tray?"})
assert worked and result.startswith("Yes. In the notification area, among the hidden icons: NVDA."), result
worked, result = registry.call(task, "read_place", {"asked": "which programs are on my taskbar"})
assert worked and result.startswith(
	"The taskbar has 2 programs: Microsoft Edge, pinned; Claude, 1 running window. Its own buttons: Start; Search. The "
	"notification area at its end has 3 icons"), result
worked, result = registry.call(task, "read_place", {"asked": "what icons are on my desktop"})
assert worked and result.startswith("The desktop has 4 icons: This PC; Recycle Bin; Firefox; Steam."), result
# A part of Windows that exists only while it is open is opened with its own key, read, and left open.
del did[:]
realShortcut = computertools.pressShortcut


def opening(keys):
	did.append(("keys", keys))
	front["app"] = "shellexperiencehost"


computertools.pressShortcut = opening
worked, result = registry.call(task, "read_place", {"asked": "tell me what is in quick settings"})
assert worked and did == [("keys", "windows+a")] and result.startswith(
	"Quick settings has 3 items: Wi-Fi, on; Bluetooth, off; Volume, 20. Quick settings is open now; Escape closes it."), (did, result)
# Already open: read without the key, which would close it again.
del did[:]
worked, result = registry.call(task, "read_place", {"asked": "what's in quick settings"})
assert worked and did == [] and result.startswith("Quick settings has 3 items"), result
# A part that does not open is said not to have opened, and nothing else is read.
front["app"] = "explorer"
computertools.pressShortcut = realShortcut
worked, result = registry.call(task, "read_place", {"asked": "tell me what is in quick settings"})
assert worked and result.startswith("Quick settings did not open, so it could not be read."), result
worked, result = registry.call(task, "read_place", {"asked": "make nvda speak faster"})
assert not worked and "does not name a part of Windows that can be read" in result, result
# Which model fits what the user wants to do: suggested by plain code, with a stand-in graphics card so that the
# engine is never started to list the real ones; nothing is changed.
from visionClaw.claw import backend as backendForTest  # noqa: E402
realDevices = instance.runtime.devices
instance.runtime.devices = lambda refresh=False: [backendForTest.Device("0", "Test card", 8151, 8000, True)]
worked, result = registry.call(task, "model_advice", {"asked": "which model should I use for describing pictures"})
assert worked and result.startswith("This computer has 8 GB of graphics memory") and result.endswith(
	"VisionClaw only suggests and has changed nothing: to choose, press NVDA+Alt+M, the models window."), result
assert "For describing pictures and the screen" in result, result
instance.runtime.devices = realDevices
# A thing inside the system tray is clicked there: listed from the tray, clicked with the mouse in its middle.
fresh()
worked, result = registry.call(task, "list_items", {"about": "right-click the volume icon in the system tray"})
assert worked and result.startswith("5 items in the notification area of Windows:\n") and "Volume Speakers" in result, result
worked, result = registry.call(task, "click_item", {"item": "Volume", "action": "right click", "asked": "right-click the volume icon in the system tray"})
assert worked and result == "Right-clicked Volume Speakers (Realtek(R) Audio): 20%." and questions[-1].startswith("Right-click Volume"), result
assert moves[0] == (1763, 1228) and buttons == [RIGHT_DOWN, RIGHT_UP], (moves, buttons)
# Named from any window and in no window: found on the taskbar, asked about, and clicked there.
fresh()
worked, result = registry.call(task, "click_item", {"item": "Claude", "action": "click", "asked": "click claude"})
assert questions[-1] == "Nothing in this window is called claude. Claude - 1 running window is in the taskbar of Windows. Use it there?", questions[-1]
assert worked and result == "Nothing in the window in front was called claude, so VisionClaw clicked Claude - 1 running window in the taskbar of Windows.", result
assert moves[0] == (894, 1228) and buttons == [LEFT_DOWN, LEFT_UP], (moves, buttons)
# The desktop's icons are clicked from the list only while the desktop is in front; a covered desktop is not.
fresh()
worked, result = registry.call(task, "list_items", {"about": "double-click the recycle bin on the desktop"})
assert worked and result.startswith("4 items in the desktop of Windows:\n1. Recycle Bin"), result
front["class"] = "CabinetWClass"
assert placetools.itemsIn(placetools.places.DESKTOP, lambda fn, *args: fn(*args)) is None
assert placetools.itemsIn(placetools.places.TRAY, lambda fn, *args: fn(*args)) is not None
front["class"] = "Progman"
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
assert instance.getScript(key("z")) is None and instance.getScript(key("tab")) is None
press("g")
press("escape")
assert not instance.pointerMode.active and buttons[-1] == LEFT_UP and instance.getScript(key("uparrow")) is None
# Every job of pointer mode has a key that every keyboard has: the owner said on 2026-11-18 that some keyboards
# have no Applications key, and no Page Up, Page Down, Home or End either. A right-clicks, as the Applications
# key does where there is one; B brings the pointer back to the middle, as Home does.
instance.pointerMode.start()


def clicksDone(count):
	for _ in range(200):
		if len(buttons) >= count:
			return
		time.sleep(0.01)
	raise AssertionError(buttons)


for rightKey in ("a", "applications", "shift+f10"):
	del buttons[:]
	press(rightKey)
	clicksDone(2)
	assert buttons == [mousetools._RIGHTDOWN, mousetools._RIGHTUP], (rightKey, buttons)
for middleKey in ("b", "home"):
	press("control+rightarrow")
	assert (instance.pointerMode.x, instance.pointerMode.y) != (cx, cy)
	press(middleKey)
	assert (instance.pointerMode.x, instance.pointerMode.y) == (cx, cy) == moves[-1], middleKey
# Shift+Enter leaves Shift down for a moment. With Shift down a double click would select everything in between,
# so the click waits until the user has let go, and is not done at all when the key stays down.
del buttons[:]
keysHeld.add(0x10)
press("shift+enter")
time.sleep(0.15)
assert buttons == [], buttons
keysHeld.clear()
clicksDone(4)
assert buttons == [LEFT_DOWN, LEFT_UP, LEFT_DOWN, LEFT_UP], buttons
del buttons[:]
heard = []
keptSaid, sys.modules["ui"].message = sys.modules["ui"].message, heard.append
keysHeld.add(0x10)
realWait, mousetools._KEYS_UP = mousetools._KEYS_UP, 0.1
press("shift+enter")
for _ in range(200):
	if len(heard) >= 2:
		break
	time.sleep(0.01)
assert heard == ["double click", "Let go of Shift, Control and Alt first: held down, they change what the mouse does. Nothing was done."], heard
assert buttons == [], buttons
keysHeld.clear()
mousetools._KEYS_UP = realWait
sys.modules["ui"].message = keptSaid
# The help that is spoken names only keys that every keyboard has.
spoken = instance.pointerMode.help()
for missing in ("Applications", "Page Down", "Page Up", "Home", "End ", "F10", "Insert", "Delete"):
	assert missing not in spoken, missing
assert "A right-clicks" in spoken and "I turns the mouse wheel up and K down, J left and L right" in spoken, spoken
assert "B brings it back to the middle" in spoken
instance.pointerMode.stop()
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
# The page as a whole, through the real tool: what it has and which of NVDA's keys fit it. This page has
# headings and no landmarks, so the heading key is named and the landmark key is not.
worked, result = registry.call(task, "explore_page", {})
assert worked and result.startswith("The web page My feed on example-feed.com has 5 headings, 2 links and 19 buttons."), result
assert "The page marks no main landmark and has no heading at level 1." in result and "How to move on this page:" in result
assert "H moves to the next heading" in result and "D moves" not in result and "[cut]" not in result, result
# What stops a form, on a page without a form: said plainly, nothing moved, no picture read.
worked, result = registry.call(task, "form_trouble", {})
assert worked and result.startswith("This page has no form fields that NVDA can read"), result
assert feed.caret == 0
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

# A nameless button the code cannot name is named from its picture, and the user is told it is a guess. The model
# that sees answers in a form of one short field (working.NAME_SCHEMA).
instance.runtime = types.SimpleNamespace(
	describe=lambda image, prompt, maxTokens, cancel=None: "Settings", unloadIdle=lambda *args: None,
	chat=lambda *args, **kwargs: '{"name": "Settings"}', oneModel=lambda: True)
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

# Which version is installed: that version alone, never the list of every add-on (versiontools.py, claw/versions.py).
# Asked by the owner on 2026-11-19: "tell me the version of visionclaw I have installed?" read out all 25 add-ons.
ownCopy = types.SimpleNamespace(name="visionClaw", path=addonDir, isDisabled=False, isRunning=True, isPendingInstall=False,
	manifest={"summary": "VisionClaw", "version": "1.15.1"})
offOne = types.SimpleNamespace(name="access8Math", path=addonDir, isDisabled=True, isRunning=False,
	manifest={"summary": "Access8Math", "version": "5.0"})
sys.modules["addonHandler"].getAvailableAddons = lambda: [clock, ownCopy, offOne]
sys.modules["buildVersion"].version = "2026.3.1"
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="Untitled - Notepad", appModule=types.SimpleNamespace(appName="notepad", productName="Microsoft Notepad", productVersion="11.2510.14.0"))
assert registry.get("version_info").tell == "verbatim" and registry.get("version_info").looks
for asked, expected in (
		("tell me the version of visionclaw I have installed?", "VisionClaw is version 1.15.1."),
		("What visionclaw addon version is installed?", "VisionClaw is version 1.15.1."),
		("which version of nvda am I running", "NVDA is version 2026.3.1."),
		("what version of the clock add-on do I have", "Clock and calendar is version 2.1."),
		("Which version of Access8Math is installed?", "Access8Math is version 5.0. It is turned off."),
		("what version of this program is it", "Microsoft Notepad is version 11.2510.14.0."),
		("what version of notepad is this", "Microsoft Notepad is version 11.2510.14.0."),
		("what versions of NVDA and VisionClaw do I have", "NVDA is version 2026.3.1.\nVisionClaw is version 1.15.1.")):
	worked, result = registry.call(task, "version_info", {"asked": asked})
	assert worked and result == expected, (asked, result)
worked, result = registry.call(task, "version_info", {"asked": "what version of teleporter do I have"})
assert worked and result.startswith("No add-on called \"teleporter\" is installed in NVDA, and the program in front is Microsoft Notepad."), result
# Only where the user says they are new to this does more follow: where to find it themselves next time.
worked, result = registry.call(task, "version_info", {"asked": "I'm a beginner screen reader user. What version of VisionClaw do I have?"})
assert worked and result.startswith("VisionClaw is version 1.15.1.\n") and "NVDA+Alt+U" in result, result
worked, result = registry.call(task, "version_info", {"asked": "I am new to NVDA, which version of it is this?"})
assert worked and result.startswith("NVDA is version 2026.3.1.\n") and "then H for Help, and choose About" in result, result
sys.modules["addonHandler"].getAvailableAddons = lambda: [clock]

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

# In pointer mode K turns the wheel down where the pointer is and says where the view then stands; at the
# end it says so; S puts the pointer on the scrollbar. Page Down does the same on a keyboard that has it.
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


def wheelFree():
	# The wheel is turned on a thread of its own; the next key counts only when that has finished.
	for _ in range(200):
		if not instance.pointerMode._wheeling.locked():
			return
		time.sleep(0.01)
	raise AssertionError("the wheel is still being turned")


# The letters every keyboard has: I up and K down, J left and L right, about a page; with Shift one notch.
HWHEEL = mousetools._HWHEEL
for letter, turned in (
		("k", [(WHEEL, -120)] * 8), ("i", [(WHEEL, 120)] * 8), ("l", [(HWHEEL, 120)] * 8), ("j", [(HWHEEL, -120)] * 8),
		("shift+k", [(WHEEL, -120)]), ("shift+i", [(WHEEL, 120)]), ("shift+l", [(HWHEEL, 120)]), ("shift+j", [(HWHEEL, -120)])):
	wheelFree()
	del said[:], wheels[:]
	pictures = [shot(0, 0.0), shot(240, 0.5)]
	press(letter)
	settle(1)
	assert wheels == turned, (letter, wheels)
# Shift+K leaves Shift down for a moment, and with Shift down most programs scroll sideways. So the wheel waits
# until the user has let go; a key that repeats meanwhile is left out; and it is not turned at all when Shift stays down.
wheelFree()
del said[:], wheels[:]
pictures = [shot(0, 0.0), shot(240, 0.5)]
keysHeld.add(0x10)
press("shift+k")
press("shift+k")
time.sleep(0.15)
assert wheels == [] and said == [], (wheels, said)
keysHeld.clear()
settle(1)
wheelFree()
assert wheels == [(WHEEL, -120)] and said == ["50 percent down"], (wheels, said)
del said[:], wheels[:]
keysHeld.add(0x11)
realWait, mousetools._KEYS_UP = mousetools._KEYS_UP, 0.1
press("k")
settle(1)
wheelFree()
assert wheels == [] and said == [
	"Let go of Shift, Control and Alt first: held down, they change what the mouse does. Nothing was done."], (wheels, said)
keysHeld.clear()
mousetools._KEYS_UP = realWait
del said[:]
said.extend(["", ""])  # as many things said as before these keys were tried
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
	describe=lambda image, prompt, maxTokens, cancel=None: "A volume slider at the top right.", unloadIdle=lambda *args: None)
worked, result = registry.call(taskModule.Task("test"), "check_access", {"target": "window", "depth": "deep"})
assert worked and "Its picture shows a scrollbar at the right, 50 percent down" in result, result
assert "The vision model, which can be wrong, sees these things that are worked with the mouse: A volume slider at the top right." in result
assert "where I and K turn the mouse wheel up and down" in result and "Page Down" not in result, result
instance.runtime = realRuntime

# --- Fingers and pressure, a game that reads the mouse directly, and a game controller ---

from visionClaw import touchinput, touchtools  # noqa: E402
from visionClaw.claw import direct, gamepad  # noqa: E402

# Nothing really touches the screen or presses on it during the tests, and the mouse itself is not moved:
# every report of a finger, of the pen and of a movement is only written down.
touches, pens, nudges = [], [], []


def writeTouch(points, flags, pressure):
	touches.append((list(points), flags, round(pressure, 2)))


touchinput._touchFrame = writeTouch
touchinput._penFrame = lambda x, y, flags, pressure, eraser=False: pens.append((x, y, flags, round(pressure, 2), eraser))
touchinput.penSupported = lambda: True
mousetools._relative = lambda dx, dy: nudges.append((dx, dy))
mousetools._NUDGE_STEP = 0
touchtools._SETTLE = 0
FINGERS_DOWN, FINGERS_MOVE, FINGERS_UP = touchinput.DOWN, touchinput.MOVE, touchinput.UP
conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="Star Map", appModule=types.SimpleNamespace(appName="starmap"),
	location=types.SimpleNamespace(left=100, top=100, width=800, height=600))
instance.clawScreen.items = lambda: window
# NVDA is on nothing that has a place in the window: a request that names no thing is meant for its middle.
sys.modules["api"].getNavigatorObject = lambda: types.SimpleNamespace(location=None, name="")
task = taskModule.Task("test")
plainShot = Image.new("RGB", (800, 600), "white")
tipShot = plainShot.copy()
ImageDraw.Draw(tipShot).rectangle((400, 320, 560, 350), fill="black")


def clear():
	del moves[:], buttons[:], wheels[:], keysPressed[:], touches[:], pens[:], nudges[:]
	task.items = window


# A pinch on a named thing: two fingers go down, come together in small steps and are lifted where they last
# were. The user is asked first, the mouse is not used, and what happened is said.
pictures = [plainShot, tipShot]
instance._grab = lambda box: pictures.pop(0)
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "pinch the Trash icon with two fingers"})
assert worked and result == (
	"Touched the screen as fingers would: a pinch with two fingers, as for zooming out, on Trash icon. What the "
	"window shows changed."), result
assert questions[-1] == "Touch the screen for you: a pinch with two fingers, as for zooming out, on Trash icon?", questions[-1]
assert touches[0][1] == FINGERS_DOWN and touches[-1][1] == FINGERS_UP and {flag for _p, flag, _s in touches[1:-1]} == {FINGERS_MOVE}
assert all(len(points) == 2 for points, _flag, _share in touches) and touches[-1][0] == touches[-2][0]
assert abs(touches[0][0][0][0] - touches[0][0][1][0]) > 3 * abs(touches[-1][0][0][0] - touches[-1][0][1][0]), touches[0]
assert (touches[0][0][0][0] + touches[0][0][1][0]) // 2 == 500 and touches[0][0][0][1] == 400  # around the thing that was named
assert buttons == [] and moves == [] and wheels == []
assert instance.appWays.get("starmap", "touch") == {"pinch": "fingers on the screen"}
# A program that takes no touch: nothing changed, so the wheel does it with Control held, the user is told
# which of the two worked, and that is kept for the program.
pictures = [plainShot, plainShot.copy(), shot(0), shot(90)]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "spread two fingers on the Trash icon"})
assert worked and result == (
	"Touched the screen as fingers would: a spread with two fingers, as for zooming in, on Trash icon. Nothing "
	"VisionClaw can see changed, so the program seems to take no touch. VisionClaw then used the Control key and "
	"the mouse wheel, which make most views larger, and what the window shows changed. That is kept for this "
	"program, and used at once the next time."), result
assert touches and wheels == [(WHEEL, 120)] * 2 and keysPressed == [(0x11, False), (0x11, True)], (wheels, keysPressed)
assert moves[0] == (500, 400) and moves[-1] == (7, 7), moves
assert instance.appWays.get("starmap", "touch") == {"pinch": "fingers on the screen", "spread": "the mouse wheel"}
# The next time the wheel is used at once, and nothing is touched.
pictures = [plainShot, shot(0), shot(90)]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "spread two fingers on the Trash icon"})
assert worked and result.startswith(
	"Used the Control key and the mouse wheel, which make most views larger, in place of a spread with two fingers"), result
assert touches == [] and wheels == [(WHEEL, 120)] * 2
# A swipe with two fingers upwards stands for scrolling down.
instance.appWays.set("starmap", "touch", None)
pictures = [plainShot, plainShot.copy(), shot(0), shot(240)]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "swipe up with two fingers on the File icon"})
assert worked and "VisionClaw then used the mouse wheel, turned down" in result and wheels == [(WHEEL, -120)] * 8, (result, wheels)
assert len(touches[0][0]) == 2 and touches[0][0][0][1] > touches[-1][0][0][1]  # the fingers went up
# A turn with two fingers has nothing that stands in for it: that nothing changed is said, and nothing else is tried.
pictures = [plainShot, plainShot.copy()]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "rotate the File icon 90 degrees clockwise with two fingers"})
assert worked and result == (
	"Touched the screen as fingers would: a turn of 90 degrees clockwise with two fingers, on File icon. Nothing "
	"VisionClaw can see changed in the window. The program may take no touch, or the gesture was not on the thing "
	"that takes it."), result
assert wheels == [] and len(touches) > 20
# Three fingers, and a double tap: two short touches.
pictures = [plainShot, tipShot]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "swipe left with three fingers"})
assert worked and all(len(points) == 3 for points, _flag, _share in touches) and "on the middle of the window" in questions[-1], questions[-1]
pictures = [plainShot, tipShot]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "double tap the File icon"})
assert worked and [flag for _p, flag, _s in touches].count(FINGERS_DOWN) == 2 and [flag for _p, flag, _s in touches].count(FINGERS_UP) == 2
assert touches[0][0] == [(200, 200)]
# Windows refuses the touch, and nothing stands in: that is said, with what Windows gave as the reason.


def refuse(points, flags, pressure):
	raise touchinput.Refused("Windows refused it (error 87).")


touchinput._touchFrame = refuse
pictures = [plainShot, plainShot]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "double tap the File icon"})
assert not worked and "The screen could not be touched for you. Windows refused it (error 87)." in result, result
# Refused, and the wheel stands in: the wheel is used, and why is said.
pictures = [plainShot, plainShot, shot(0), shot(90)]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "pinch the Trash icon"})
assert worked and result.startswith("Windows did not take the touch. Windows refused it (error 87). VisionClaw then used the Control key"), result
assert wheels == [(WHEEL, -120)] * 2
touchinput._touchFrame = writeTouch
instance.appWays.set("starmap", "touch", None)
# Words that name no touch: nothing is touched.
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "do the thing on the File icon"})
assert not worked and "does not say which touch gesture" in result and touches == [], result
# Stopped while the fingers are down: they are lifted at once, and never stay on the screen.
stopping = taskModule.Task("test")
stopping.items = window
pictures = [plainShot] * 4
clear()
threading.Timer(0.3, stopping.stop).start()
began = time.time()
try:
	registry.call(stopping, "touch_gesture", {"asked": "touch and hold the File icon for 20 seconds"})
	raise AssertionError("a stopped request must not go on")
except taskModule.Cancelled:
	pass
assert time.time() - began < 5 and touches[0][1] == FINGERS_DOWN and touches[-1][1] == FINGERS_UP, touches[-1]
# On a computer with a touch screen NVDA takes every touch for itself. Its own touch handling is put aside for
# the gesture with NVDA's own function and put back afterwards; this is always asked about, whatever the settings say.
paused = []
stub("touchHandler", handler=object(), setTouchSupport=paused.append)
conf["visionClaw"]["confirmChanges"] = False
pictures = [plainShot, tipShot]
clear()
worked, result = registry.call(task, "touch_gesture", {"asked": "pinch the Trash icon"})
assert worked and paused == [False, True] and questions[-1].endswith(
	"NVDA's own touch gestures are put aside for that moment and put back right after."), (paused, questions[-1])
# Also when the touch fails, NVDA's touch handling is put back.
touchinput._touchFrame = refuse
pictures = [plainShot, plainShot]
del paused[:]
worked, result = registry.call(task, "touch_gesture", {"asked": "double tap the File icon"})
assert not worked and paused == [False, True], paused
touchinput._touchFrame = writeTouch
sys.modules["touchHandler"].handler = None
conf["visionClaw"]["confirmChanges"] = True
instance.appWays.set("starmap", "touch", None)

# Pressure: the pen goes down on the named thing as hard as the words say, stays, and comes up.
pictures = [plainShot, tipShot]
clear()
worked, result = registry.call(task, "pen_stroke", {"asked": "press hard on the Trash icon for half a second"})
assert worked and result == (
	"Pressed as a pen would: a press for half a second with the pen, at 80 percent of full pressure, on Trash icon. "
	"What the window shows changed. Whether the program felt how hard it was pressed, VisionClaw cannot see."), result
assert questions[-1] == "Press on Trash icon for you: a press for half a second with the pen, at 80 percent of full pressure?"
assert pens[0] == (500, 400, FINGERS_DOWN, 0.8, False) and pens[-1][2] == FINGERS_UP and {pen[:2] for pen in pens} == {(500, 400)}
assert buttons == [] and moves == [] and touches == []
# A line with the pressure rising: it rises evenly from the first place to the last. Nothing changed: said so,
# with what cannot be reached this way.
pictures = [plainShot, plainShot.copy()]
clear()
worked, result = registry.call(task, "pen_stroke", {"asked": "draw a line to the right on the File icon with the pressure rising"})
assert worked and "at pressure rising from 15 to 100 percent, on File icon." in result, result
assert result.endswith("the tablet's own driver, and not through Windows, takes no notice of this."), result
shares = [pen[3] for pen in pens[:-1]]
assert shares[0] == 0.15 and shares[-1] == 1.0 and shares == sorted(shares) and len(set(shares)) > 10, shares
assert pens[0][:2] == (200, 200) and pens[-2][0] > 300 and pens[-2][1] == 200, pens[-2]
# The eraser end of the pen.
pictures = [plainShot, tipShot]
clear()
worked, result = registry.call(task, "pen_stroke", {"asked": "erase with the pen on the Trash icon, firmly, a zigzag"})
assert worked and all(pen[4] for pen in pens) and "the eraser end of the pen" in result, result
# A Windows without a pen for programs: one finger presses instead, which also says how hard; that is told.
touchinput.penSupported = lambda: False
pictures = [plainShot, tipShot]
clear()
worked, result = registry.call(task, "pen_stroke", {"asked": "press lightly on the File icon"})
assert worked and "gives a program no pen, so one finger pressed instead" in result and pens == [], result
assert touches[0] == ([(200, 200)], FINGERS_DOWN, 0.25) and touches[-1][1] == FINGERS_UP, touches[0]
touchinput.penSupported = lambda: True
# Words that say nothing of how hard: nothing is pressed.
clear()
worked, result = registry.call(task, "pen_stroke", {"asked": "press the File icon"})
assert not worked and "does not say how hard to press" in result and pens == [], result
# Stopped while the pen is down: it is lifted.
stopping = taskModule.Task("test")
stopping.items = window
pictures = [plainShot] * 4
clear()
threading.Timer(0.3, stopping.stop).start()
try:
	registry.call(stopping, "pen_stroke", {"asked": "press hard on the File icon for 20 seconds"})
	raise AssertionError("a stopped request must not go on")
except taskModule.Cancelled:
	pass
assert pens[0][2] == FINGERS_DOWN and pens[-1][2] == FINGERS_UP

# A game whose view the mouse turns: the mouse itself is moved by a number of steps, in small pieces, and
# whether the view changed is said. Windows' pointer is put nowhere, and no button is pressed.
pointerFacts = {"showing": True, "confined": False, "inside": False}
mousetools.pointerState = lambda box=None: dict(pointerFacts)
pictures = [shot(0), shot(90)]
clear()
worked, result = registry.call(task, "turn_view", {"asked": "turn left"})
assert worked and result.startswith("Moved the mouse itself 300 steps to the left. What the window shows changed."), result
assert "too fast or too slow" in result and questions[-1] == "Move the mouse itself 300 steps to the left, to turn or look in starmap?"
assert sum(dx for dx, _dy in nudges) == -300 and all(dy == 0 for _dx, dy in nudges) and max(abs(dx) for dx, _dy in nudges) <= direct.CHUNK
assert moves == [] and buttons == []
pictures = [shot(0), shot(0)]
clear()
worked, result = registry.call(task, "turn_view", {"asked": "look up 120 steps"})
assert worked and result == (
	"Moved the mouse itself 120 steps up. Nothing VisionClaw can see changed in the window. The program may not "
	"turn with the mouse just now, or it refuses movements made by a program."), result
assert sum(dy for _dx, dy in nudges) == -120
clear()
worked, result = registry.call(task, "turn_view", {"asked": "turn the thing"})
assert not worked and "does not say which way to turn or look" in result and nudges == [], result

# How the mouse is moved in a program is said from what is kept and from Windows' own facts, by plain code.
worked, result = registry.call(task, "mouse_way", {"asked": "how does this game use the mouse?"})
assert worked and result == (
	"In starmap, Windows' own mouse pointer is put where it is wanted, as in other programs. Windows' own mouse "
	"pointer shows here, so the usual way should work."), result
pointerFacts.update(showing=False, confined=True, inside=True)
worked, result = registry.call(task, "mouse_way", {"asked": "how does this game use the mouse?"})
assert worked and "This program hides Windows' mouse pointer and keeps it inside its own window" in result and direct.ADVICE in result, result
# Told once that the game draws its own pointer, VisionClaw keeps that; clicks by name then move the game's
# pointer: into the corner of the window, measured, and counted from there. Windows' pointer is put nowhere.
worked, result = registry.call(task, "mouse_way", {"asked": "this game has its own mouse pointer"})
assert worked and result.startswith("Kept for starmap: the program draws a pointer of its own"), result
assert questions[-1].startswith("Keep this for starmap: the program draws a pointer of its own") and instance.appWays.mouse("starmap") == direct.POINTER
stoodInMove, stoodInPosition = mousetools.moveTo, mousetools.position
mousetools.moveTo, mousetools.position = realMoveTo, realPosition
mousetools._setCursor = lambda x, y: moves.append((x, y))
mousetools._cursorPosition = lambda: (7, 7)
instance._grab = lambda box: plainShot  # no pointer to be seen: its speed cannot be measured and stays as it was
clear()
worked, result = registry.call(task, "click_item", {"item": "File", "action": "click", "asked": ""})
assert worked and result == "Clicked File icon." and buttons == [LEFT_DOWN, LEFT_UP], (result, buttons)
assert moves == [], moves  # Windows' own pointer was never put anywhere
# Into the corner (further than the window is large), three moves to measure, then from there to the icon.
home = round(800 / direct.MEASURED_LEAST) + 200
assert sum(dx for dx, _dy in nudges) == -home + 3 * direct.MEASURE_STEP + (200 - (100 + 3 * direct.MEASURE_STEP)), sum(dx for dx, _dy in nudges)
assert sum(dy for _dx, dy in nudges) == sum(dx for dx, _dy in nudges) and nudges[0] == (-direct.HOME_CHUNK, -direct.HOME_CHUNK)
assert mousetools._direct.way == direct.PLAIN and mousetools._direct.tracker is None  # only while the tool worked
# A hold and a gesture go the same way.
clear()
worked, result = registry.call(task, "draw_gesture", {"asked": "swipe left on the Trash icon"})
assert worked and moves == [] and buttons == [LEFT_DOWN, LEFT_UP] and sum(dx for dx, _dy in nudges) < -3000, (result, moves)
# When Windows' own pointer shows again, as in the game's menus, it is used as everywhere.
pointerFacts.update(showing=True)
clear()
worked, result = registry.call(task, "click_item", {"item": "File", "action": "click", "asked": ""})
assert worked and moves[0] == (200, 200) and nudges == [] and buttons == [LEFT_DOWN, LEFT_UP], (moves, nudges)
pointerFacts.update(showing=False)
# Too fast: kept for the program, and a turn is then that much shorter.
worked, result = registry.call(task, "mouse_way", {"asked": "direct mouse movement is too fast here"})
assert worked and result == (
	"Direct mouse movement in starmap is now slower: one step counts as 0.7. This is kept for the program."), result
pictures = [shot(0), shot(90)]
instance._grab = lambda box: pictures.pop(0)
clear()
worked, result = registry.call(task, "turn_view", {"asked": "turn right"})
assert worked and sum(dx for dx, _dy in nudges) == 210, nudges
# Told that the mouse turns the view: pointing at a thing by name is refused, with what to ask for instead.
worked, result = registry.call(task, "mouse_way", {"asked": "the mouse turns the view here"})
assert worked and instance.appWays.mouse("starmap") == direct.VIEW and "Ask to turn left or right" in result, result
clear()
worked, result = registry.call(task, "click_item", {"item": "File", "action": "click", "asked": ""})
assert not worked and "In this program the mouse turns the view" in result and buttons == [] and moves == [] and nudges == [], result
worked, result = registry.call(task, "mouse_way", {"asked": "how does this game use the mouse?"})
assert worked and result.startswith("In starmap, the mouse turns the view and nothing points at anything") and "counts as 0.7" in result, result
# What is kept about programs is listed with what VisionClaw has made.
worked, result = registry.call(task, "list_helpers", {})
assert worked and "In starmap, the mouse turns the view" in result, result

# Pointer mode in such a game: the arrow keys move the mouse itself, Enter clicks where the game aims, and M
# changes between the three ways and keeps the choice for the program.
said = []
sys.modules["ui"].message = said.append
clear()
text = instance.pointerMode.start()
assert instance.pointerMode.direct == direct.VIEW and "the mouse turns the view" in text and "M changes how the mouse is moved" in text, text
assert moves == [] and nudges == []
press("rightarrow")
press("shift+uparrow")
assert nudges == [(14, 0), (0, -3)] and moves == [], nudges  # a step of 20 and one of 4, at the speed kept for the game
press("enter")
for _wait in range(100):
	if buttons == [LEFT_DOWN, LEFT_UP]:
		break
	time.sleep(0.01)
assert buttons == [LEFT_DOWN, LEFT_UP] and moves == [], (buttons, moves)
press("p")
assert said[-1] == "The mouse turns the view here, so there is no pointer with a place.", said[-1]
press("m")
assert said[-1] == "Windows' own mouse pointer is moved, as in other programs." and instance.appWays.mouse("starmap") == direct.PLAIN
press("rightarrow")
assert moves[-1][0] == instance.pointerMode.x and len(nudges) == 2
instance._grab = lambda box: plainShot
clear()
press("m")
assert said[-1].startswith("The program's own pointer is moved") and instance.appWays.mouse("starmap") == direct.POINTER
assert nudges and moves == [] and mousetools._direct.way == direct.POINTER
was = (instance.pointerMode.x, instance.pointerMode.y)
assert abs(was[0] - 500) <= 1 and abs(was[1] - 400) <= 1, was  # brought to the middle of the window
del nudges[:]
press("rightarrow")
assert moves == [] and sum(dx for dx, _dy in nudges) == round(20 / 0.7) and instance.pointerMode.x == was[0] + 20, (nudges, instance.pointerMode.x)
press("escape")
assert not instance.pointerMode.active and mousetools._direct.way == direct.PLAIN and instance.pointerMode.direct == direct.PLAIN
# Back to the usual way: what was kept about the program's mouse is forgotten.
worked, result = registry.call(task, "mouse_way", {"asked": "use the normal mouse pointer again"})
assert worked and result == (
	"In starmap, Windows' own mouse pointer is put where it is wanted, as in other programs again. What was kept "
	"about its mouse is forgotten."), result
assert instance.appWays.lines() == []
pointerFacts.update(showing=True, confined=False, inside=False)
mousetools.moveTo, mousetools.position = stoodInMove, stoodInPosition

# A game controller. The states are made here; no controller is read.
controller = instance.controller
found = [None]
reported = [gamepad.NOTHING]
buzzes = []
padtools._find = lambda joysticks=True: found[0]
padtools._read = lambda device: reported[0]
padtools._vibrate = lambda device, left, right: buzzes.append((left, right))


def pad(held=(), lx=0.0, ly=0.0, rx=0.0, ry=0.0, lt=0.0, rt=0.0):
	return gamepad.State(frozenset(held), lx, ly, rx, ry, lt, rt)


def waitFor(test, what=""):
	for _wait in range(300):
		if test():
			return
		time.sleep(0.01)
	raise AssertionError(what or said[-3:])


del said[:]
# None is connected: nothing is said by itself; asked, plain code says so.
assert controller.look(0.0) == gamepad.SEARCH_EVERY and controller.device is None and said == []
worked, result = registry.call(taskModule.Task("is a controller connected"), "controller_info", {})
assert worked and result.startswith("No game controller is connected, as far as Windows reports."), result
instance.script_controllerMode(None)
assert said[-1] == "No game controller is connected, as far as Windows reports." and not controller.active
# One is connected: it is noticed and announced, once, with how to use it.
found[0] = (gamepad.XBOX, 0, "")
assert controller.look(1.0) == gamepad.LOOK_EVERY and controller.device == found[0]
assert said[-1].startswith("A game controller is connected: an Xbox controller, or one that Windows reads the same way.")
assert "hold its View and Menu buttons together for a second, or press NVDA+Alt+J" in said[-1] and len(said) == 2
worked, result = registry.call(taskModule.Task("is a controller connected"), "controller_info", {})
assert worked and "A game controller is connected" in result and "Controller mode is off." in result and result.endswith(
	"Ask what the buttons do, and VisionClaw says all of them."), result
worked, result = registry.call(taskModule.Task("what do the buttons of my controller do"), "controller_info", {})
assert worked and "In controller mode: The left stick moves the mouse pointer" in result and "A clicks, B right-clicks" in result, result
# Out of controller mode its sticks and buttons are left alone: the user may be playing with it.
clear()
reported[0] = pad([gamepad.A], lx=1.0, rt=1.0, lt=1.0)
controller.look(1.1)
controller.look(1.2)
reported[0] = gamepad.NOTHING
controller.look(1.3)
assert buttons == [] and moves == [] and pens == [] and wheels == [] and len(said) == 2
# View and Menu held together for a second turn controller mode on, and all it does is said.
reported[0] = pad([gamepad.BACK, gamepad.START])
controller.look(2.0)
controller.look(2.5)
assert not controller.active
controller.look(3.1)
assert controller.active and said[-1] == gamepad.HELP and moves[-1] == (500, 400), moves
assert not instance.pointerMode.active and instance.getScript(key("rightarrow")) is None  # the keyboard's keys stay the user's
reported[0] = gamepad.NOTHING
controller.look(3.2)
assert controller.active
# The left stick moves the pointer: a full push fast, with the left shoulder button slow, a small push slowly.
clear()
reported[0] = pad(lx=1.0)
controller.look(3.3)
assert moves[-1] == (570, 400), moves  # 700 pixels a second for a tenth of a second
reported[0] = pad([gamepad.LB], lx=1.0)
controller.look(3.4)
assert moves[-1] == (587, 400), moves
reported[0] = pad(lx=0.4, ly=-0.4)
controller.look(3.5)
x, y = moves[-1]
assert 587 < x <= 600 and 388 <= y < 400, moves[-1]  # about 13 pixels, where a full push made 70
# Inside its resting place the stick does nothing; when it comes to rest, what is under the pointer is said,
# once, and felt as a short buzz.
under.name, under.role.displayString = "Play", "button"
reported[0] = pad(lx=0.1, ly=0.1)
count = len(moves)
controller.look(3.6)
assert len(moves) == count
del buzzes[:]
controller.look(4.0)
assert said[-1] == "Play, button" and buzzes[-1] == gamepad.BUZZ_OTHER[:2], (said[-1], buzzes)
heard = len(said)
reported[0] = pad(lx=1.0)
controller.look(4.1)
reported[0] = gamepad.NOTHING
controller.look(4.2)
controller.look(4.6)
assert len(said) == heard  # still the same thing: not said again
controller.look(4.7)
assert buzzes[-1] == (0, 0)  # the buzz ends by itself
# At the window's edge the pointer stops, and that is felt and heard.
reported[0] = pad([gamepad.RB], lx=1.0)
for tick in range(8):
	controller.look(5.0 + tick / 10)
assert moves[-1][0] == 898 and gamepad.BUZZ_EDGE[:2] in buzzes, (moves[-1], buzzes)
reported[0] = gamepad.NOTHING
controller.look(6.0)
controller.look(6.5)
# The buttons: A clicks where the pointer is, B right-clicks, X double-clicks, Y says what is here.
at = (instance.pointerMode.x, instance.pointerMode.y)
for button, expected, word in ((gamepad.A, [LEFT_DOWN, LEFT_UP], "click"), (gamepad.B, [RIGHT_DOWN, RIGHT_UP], "right click"),
		(gamepad.X, [LEFT_DOWN, LEFT_UP] * 2, "double click")):
	clear()
	reported[0] = pad([button])
	controller.look(7.0)
	waitFor(lambda: buttons == expected, button)
	assert said[-1] == word and moves[0] == at, (said[-1], moves)
	reported[0] = gamepad.NOTHING
	controller.look(7.1)
reported[0] = pad([gamepad.Y])
controller.look(7.2)
assert said[-1] == "Play, button"
reported[0] = pad([gamepad.LS])
controller.look(7.3)
assert said[-1].endswith("percent down"), said[-1]
reported[0] = gamepad.NOTHING
controller.look(7.4)
# The direction pad moves one step, as an arrow key does in pointer mode.
instance.pointerMode.x = 500
reported[0] = pad([gamepad.LEFT])
controller.look(7.5)
assert instance.pointerMode.x == 480 and moves[-1] == (480, at[1]), moves[-1]
reported[0] = gamepad.NOTHING
controller.look(7.6)
# The right trigger is the mouse button for as long as it is pulled: pull, move, let go is a drag.
clear()
reported[0] = pad(rt=0.9)
controller.look(8.0)
assert buttons == [LEFT_DOWN] and said[-1] == "Holding." and instance.pointerMode.holding
reported[0] = pad(rt=0.9, lx=1.0)
controller.look(8.1)
assert moves[-1] == (550, at[1]) and buttons == [LEFT_DOWN]
reported[0] = pad(rt=0.1)
controller.look(8.2)
assert buttons == [LEFT_DOWN, LEFT_UP] and said[-1] == "Let go." and not instance.pointerMode.holding
# The left trigger presses like a pen, as hard as it is pulled, follows the pointer, and is lifted when let go.
clear()
reported[0] = pad(lt=1.0)
controller.look(8.5)
assert pens == [(550, at[1], FINGERS_DOWN, 1.0, False)] and said[-1] == "Pen down.", pens
reported[0] = pad(lt=0.625, lx=1.0)
controller.look(8.6)
assert pens[-1] == (620, at[1], FINGERS_MOVE, 0.5, False), pens[-1]
reported[0] = pad(lt=0.3)
controller.look(8.7)
assert pens[-1][2] == FINGERS_MOVE and pens[-1][3] < 0.1  # nearly let go: still down, pressing lightly
reported[0] = gamepad.NOTHING
controller.look(8.8)
assert pens[-1][2] == FINGERS_UP and said[-1] == "Pen up." and buttons == []
# The right stick turns the wheel; pressed in, it moves the mouse itself instead, for a game, and back.
clear()
reported[0] = pad(ry=1.0)
controller.look(9.0)
assert wheels == [(WHEEL, -120)], wheels  # ten notches a second for a tenth of a second
reported[0] = pad(rx=-1.0)
controller.look(9.1)
assert wheels[-1][0] == HWHEEL and len(wheels) == 2, wheels
reported[0] = pad([gamepad.RS])
controller.look(9.2)
assert said[-1] == "The right stick now moves the mouse itself, for a game that reads the mouse directly." and controller.looking
reported[0] = pad(ry=-1.0)
controller.look(9.3)
assert nudges == [(0, -90)] and len(wheels) == 2, nudges  # 900 steps a second
reported[0] = pad([gamepad.RS])
controller.look(9.4)
assert said[-1] == "The right stick now turns the mouse wheel." and not controller.looking
reported[0] = gamepad.NOTHING
controller.look(9.5)
# With the right shoulder button, the direction pad jumps from one thing found in the window to the next, by name.
clear()
reported[0] = pad([gamepad.RB, gamepad.RIGHT])
controller.look(10.0)
waitFor(lambda: said[-1] == "File icon, 1 of 3")
assert "Looking at the window." in said[-3:] and moves[-1] == (200, 200) and (instance.pointerMode.x, instance.pointerMode.y) == (200, 200)
reported[0] = pad([gamepad.RB])
controller.look(10.1)
reported[0] = pad([gamepad.RB, gamepad.RIGHT])
controller.look(10.2)
assert said[-1] == "Trash icon, 2 of 3" and moves[-1] == (500, 400)
reported[0] = pad([gamepad.RB])
controller.look(10.3)
reported[0] = pad([gamepad.RB, gamepad.LEFT])
controller.look(10.4)
assert said[-1] == "File icon, 1 of 3"
reported[0] = gamepad.NOTHING
controller.look(10.5)
# A button of the controller as a hotkey of the program in front: the user's own words say which button.
clicked = []
instance.clawScreen.click = lambda result, item, action="click": clicked.append((item["text"], action))
task.items = window
worked, result = registry.call(task, "create_helper", {
	"key": "?", "action": "click", "item": "Trash", "asked": "make the X button on my controller click the Trash icon"})
assert worked and result == (
	"In starmap, pressing the X button of the game controller now does this: click \"Trash\". It works whenever "
	"the controller is connected, in this program only, in controller mode or out of it."), result
assert questions[-1] == "In starmap, make the X button of the game controller click \"Trash\"?", questions[-1]
assert instance.helpers.binding("starmap", "pad:x")["item"] == "Trash"
clear()
reported[0] = pad([gamepad.X])
controller.look(11.0)
waitFor(lambda: clicked == [("Trash icon", "click")], "the button's hotkey")
assert buttons == []  # the button did what it was made for, and not its double click
reported[0] = gamepad.NOTHING
controller.look(11.1)
worked, result = registry.call(taskModule.Task("is my controller connected"), "controller_info", {})
assert worked and "Controller mode is on" in result and "Buttons that are hotkeys: App helper in starmap: the X button of the game controller does click" in result, result
# In another program the button is the controller mode's own again.
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="Notes", appModule=types.SimpleNamespace(appName="notes"),
	location=types.SimpleNamespace(left=100, top=100, width=800, height=600))
clear()
reported[0] = pad([gamepad.X])
controller.look(11.2)
waitFor(lambda: buttons == [LEFT_DOWN, LEFT_UP] * 2, "the double click")
assert len(clicked) == 1
reported[0] = gamepad.NOTHING
controller.look(11.3)
assert instance.helpers.remove("the X button on my controller") and instance.helpers.binding("starmap", "pad:x") == {}
# The Menu button repeats the help; the View button turns the mode off.
reported[0] = pad([gamepad.START])
controller.look(12.0)
assert said[-1] == gamepad.HELP
reported[0] = pad([gamepad.BACK])
controller.look(12.1)
assert not controller.active and said[-1] == "Controller mode is off."
reported[0] = gamepad.NOTHING
controller.look(12.2)
# Asked for in words, on and off.
worked, result = registry.call(task, "controller_mode", {"turn": "on"})
assert worked and controller.active and result == gamepad.HELP
worked, result = registry.call(task, "controller_mode", {"turn": "on"})
assert worked and result.startswith("Controller mode is already on.")
worked, result = registry.call(task, "controller_mode", {"turn": "off"})
assert worked and not controller.active and result == "Controller mode is off."
# The controller goes away while its trigger holds the mouse button and the pen is down: both come up at
# once, the mode is off, and the user is told.
instance.script_controllerMode(None)
assert controller.active
clear()
reported[0] = pad(rt=1.0, lt=1.0)
controller.look(13.0)
assert buttons == [LEFT_DOWN] and pens[-1][2] == FINGERS_DOWN
padtools._read = lambda device: None
assert controller.look(13.1) == gamepad.SEARCH_EVERY
assert buttons == [LEFT_DOWN, LEFT_UP] and pens[-1][2] == FINGERS_UP and not controller.active and controller.device is None
assert said[-1] == "The game controller is gone. Controller mode is off." and not instance.pointerMode.holding
padtools._read = lambda device: reported[0]
# Quiet: it is noticed without a word, and its buttons still work. Off: it is not looked for at all, and
# asking says why.
conf["visionClaw"]["controller"] = "quiet"
reported[0] = gamepad.NOTHING
heard = len(said)
controller.look(14.0)
assert controller.device is not None and len(said) == heard
conf["visionClaw"]["controller"] = "off"
assert controller.look(14.1) == gamepad.SEARCH_EVERY and controller.device is None and len(said) == heard
instance.script_controllerMode(None)
assert said[-1] == "Game controllers are switched off in VisionClaw's settings." and not controller.active
worked, result = registry.call(taskModule.Task("is a controller connected"), "controller_info", {})
assert worked and result.startswith("Game controllers are switched off in VisionClaw's settings"), result
conf["visionClaw"]["controller"] = "announce"
# A controller of another make is told apart, and what is not known about it is said.
found[0] = (gamepad.OTHER, 3, "")
controller.look(15.0)
assert "a game controller of another make" in said[-1] and "may not fit this one" in said[-1], said[-1]
# The inspection of a window says what Windows reports of its mouse pointer, and that a controller is there.
pointerFacts.update(showing=False, confined=True, inside=True)
pictures = [shot(0, 0.5)] * 3
instance._grab = lambda box: pictures[0]
realRuntime, instance.runtime = instance.runtime, types.SimpleNamespace(
	describe=lambda image, prompt, maxTokens, cancel=None: "Nothing that is worked with the mouse.", unloadIdle=lambda *args: None)
worked, result = registry.call(taskModule.Task("test"), "check_access", {"target": "window", "depth": "deep"})
assert worked and "This program hides Windows' mouse pointer and keeps it inside its own window" in result, result
assert "this game has its own pointer" in result and "A game controller is connected: in controller mode (NVDA+Alt+J)" in result, result
instance.runtime = realRuntime
pointerFacts.update(showing=True, confined=False, inside=False)
# When NVDA closes, everything is let go.
found[0] = None
padtools._read = lambda device: None
controller.look(16.0)
controller.stop()
assert controller.device is None and not controller.active
sys.modules["ui"].message = lambda text: None
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(
	name="Notes", appModule=types.SimpleNamespace(appName="notes"),
	location=types.SimpleNamespace(left=0, top=0, width=800, height=600))
under.name, under.role.displayString = "", ""
conf["visionClaw"]["confirmChanges"] = False

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
# T goes to the top end: on until nothing moves any more, and then the next press says that nothing moved.
# B goes to the bottom end. End and Home do the same on a keyboard that has them.
press("t")
idle()
assert world.level == 100 and said[-1] == "At the end. 100 dB", (world.level, said[-3:])
press("b")
idle()
assert world.level == 0 and said[-1].startswith("At the end."), (world.level, said[-3:])
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

# --- A whole program made accessible, window after window (appaccesstools.py, claw/appaccess.py) ---

from visionClaw import appaccesstools  # noqa: E402
from visionClaw.claw import accessnotes, appaccess, lookup  # noqa: E402

closeIcon = thing("BUTTON", "", ["FOCUSABLE"], box=(700, 10, 730, 40), autoId="closeBtn")
gearIcon = thing("BUTTON", "", ["FOCUSABLE"], box=(650, 10, 680, 40))
gearIcon.windowControlID = 1007
prefs = thing("DIALOG", "Preferences", box=(0, 0, 800, 600), children=[closeIcon, gearIcon, okButton])
effects = thing("DIALOG", "Effects", box=(0, 0, 800, 600), children=[
	thing("BUTTON", "", ["FOCUSABLE"], box=(700, 10, 730, 40), autoId="closeBtn"), thing("BUTTON", "Reverb", ["FOCUSABLE"]), okButton])
sys.modules["api"].getForegroundObject = lambda: prefs
sys.modules["api"].getFocusObject = lambda: okButton
instance.runtime = types.SimpleNamespace(
	describe=lambda image, prompt, maxTokens, cancel=None: "none", unloadIdle=lambda *args: None,
	chat=lambda *args, **kwargs: '{"name": "Gear"}', oneModel=lambda: True)
instance._grab = lambda box: "picture"
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
assert registry.get("learn_program").looks and registry.get("fix_program").changes
assert registry.get("learn_program").tell == registry.get("fix_program").tell == "verbatim"
# Learning the window in front: every problem, its steps in the plan, the program it belongs to, and nothing made yet.
worked, result = registry.call(taskModule.Task("test"), "learn_program", {"asked": "learn this window"})
assert worked and result.startswith("Learned the dialog Preferences of the program mixer.\nFound 1 problem in it:\n1. 2 buttons have "
	"no name"), result
assert "- To make: Buttons without a name are called close. In the window Preferences." in result, result
assert "- To make: Buttons without a name are called Gear, a guess from a picture that can be wrong. In the window Preferences." in result
assert "It is the first window of the program mixer that VisionClaw has learned." in result
assert "To make the 2 fixes still to make, say: make the planned fixes for this program." in result, result
assert result.endswith("When you move to another window of it, VisionClaw learns that one too, and tells you."), result
assert questions == [] and instance.helpers.store.source("fixes_mixer") is None
assert appaccesstools.isFollowed(instance, {"app": "mixer"})
mapFile = accesstools.accessNotes(instance).text({"app": "mixer"})
assert "## Windows and pages learned" in mapFile and "## The plan to fix it" in mapFile and "Preferences, a dialog." in mapFile, mapFile
# The name read from the gear's picture is kept, so that the same control is named again without a model.
assert accesstools.accessNotes(instance).knownName({"app": "mixer"}, accessnotes.keyOf(
	{"role": "BUTTON", "controlId": 1007, "windowClass": "JUCE_1a"})) == "Gear"
# A second window of the same program: it belongs to it, and the close button found in both is one step of the plan.
sys.modules["api"].getForegroundObject = lambda: effects
worked, result = registry.call(taskModule.Task("test"), "learn_program", {"asked": "learn this window too"})
assert worked and result.startswith("Learned the dialog Effects of the program mixer."), result
assert "- To make: Buttons without a name are called close. In the windows Preferences and Effects." in result, result
assert "VisionClaw now knows 2 windows of the program mixer, all of them part of it: Preferences and Effects." in result, result
worked, result = registry.call(taskModule.Task("test"), "learn_program", {"asked": "which windows of this program have you learned"})
assert worked and result.startswith("VisionClaw has learned 2 windows of the program mixer, and all of them belong to it:\n1. "
	"Preferences, a dialog."), result
worked, result = registry.call(taskModule.Task("test"), "learn_program", {"asked": "what's the plan for this program"})
assert worked and result.startswith("The plan for the program mixer, from the 2 windows VisionClaw has learned, has 2 steps: 2 to make."), result
# Making the plan: every fix of every window in the program's one add-on, after one question; then what is left.
del questions[:]
fixTask = taskModule.Task("test")
worked, result = registry.call(fixTask, "learn_program", {"asked": "make every window of this program accessible"})
assert worked and "make the planned fixes" not in result, result
worked, result = registry.call(fixTask, "fix_program", {"asked": "make every window of this program accessible"})
assert worked and result.startswith("Made 2 fixes for the program mixer."), result
assert result.endswith("Every step of the plan for the program mixer is made."), result
assert len(questions) == 1 and questions[0].startswith("VisionClaw can make these fixes for the program mixer"), questions
scope, made = fixes.parse(instance.helpers.store.source("fixes_mixer"))
assert sorted(fix["label"] for fix in made) == ["Gear", "close"], made
worked, result = registry.call(taskModule.Task("test"), "learn_program", {"asked": "what's the plan for this program"})
assert "2 made" in result and "1. Made: Buttons without a name are called close." in result, result
# Nothing left: said, and no question asked.
del questions[:]
worked, result = registry.call(taskModule.Task("test"), "fix_program", {"asked": "carry out the plan"})
assert worked and result.startswith("Nothing of the plan for the program mixer is left that an add-on can make now.") and not questions, result
# A deep inspection of another window of the program puts it on the map too, now that VisionClaw is making it accessible.
sys.modules["api"].getForegroundObject = lambda: recorder
registry.call(taskModule.Task("test"), "check_access", {"target": "window", "depth": "deep"})
assert [place.name for place in appaccesstools.mapOf(instance, {"app": "mixer"})[0]] == ["Preferences", "Effects", "Recorder"]
# Another window the user moves to is learned by itself, with NVDA's facts only, and one sentence says so.
heardFollow = []
follower = appaccesstools.Follower(instance, heardFollow.append, threading.Event())
routing = thing("DIALOG", "Routing", box=(0, 0, 800, 600), children=[
	thing("BUTTON", "", ["FOCUSABLE"], box=(700, 10, 730, 40), autoId="closeBtn"), thing("BUTTON", "Send", ["FOCUSABLE"]), okButton])
follower._learn(follower._generation, ({"app": "mixer"}, appaccess.windowId("JUCE_1a", "Routing", ["mixer"]), "Routing", "dialog", routing),
	threading.Event())
assert heardFollow == ["VisionClaw learned this dialog of mixer: 1 problem, 1 step for it in the plan."], heardFollow
assert "Routing" in [place.name for place in appaccesstools.mapOf(instance, {"app": "mixer"})[0]]
# A window known already is not learned again by itself, and nothing is said for a program the user stopped.
follower._learn(follower._generation, ({"app": "mixer"}, appaccess.windowId("JUCE_1a", "Routing", ["mixer"]), "Routing", "dialog", routing),
	threading.Event())
assert len(heardFollow) == 1
# The model that chooses is told that the user is in a program VisionClaw is making accessible, and how far it is.
told = instance.orchestrator.programMap()
assert told == ("VisionClaw is making the program mixer accessible window after window: it has learned 4 windows of it, and "
	"its plan has 0 fixes still to make and 2 made."), told
assert told in instance.orchestrator._context("now fix the rest of the windows")
worked, result = registry.call(taskModule.Task("test"), "learn_program", {"asked": "stop learning windows of this program"})
assert worked and result.startswith("VisionClaw no longer learns the windows of the program mixer") and not appaccesstools.isFollowed(
	instance, {"app": "mixer"}), result
assert instance.orchestrator.programMap() == ""
# look_up is given the map where the question is about windows, problems or the plan, each line saying where it is from.
sys.modules["api"].getForegroundObject = lambda: effects
found = appaccesstools.passages(instance, "which windows have problems")
assert found and all(p.origin == "what VisionClaw learned about the windows of the program mixer" for p in found), found
assert any("Routing, a dialog." in p.text for p in found) and lookup.gated(found, "what time is it") == []
# Forgetting asks first; the fixes made stay in the add-on.
worked, result = registry.call(taskModule.Task("test"), "learn_program", {"asked": "forget the windows of this program"})
assert worked and result.startswith("Forgot the 4 windows and the plan of the program mixer.") and questions[-1].startswith("Forget the 4 windows"), result
assert appaccesstools.mapOf(instance, {"app": "mixer"}) == ([], []) and instance.helpers.store.source("fixes_mixer") is not None
registry.call(taskModule.Task("test"), "remove_helper", {"name": "fixes_mixer"})
# The program's learning scratchpad has one line of what VisionClaw knows of it, for the models working there later.
mixerPad = instance.pads.learning("mixer")
assert [note.text for note in mixerPad.notes if "making mixer accessible window by window" in note.text], [n.text for n in mixerPad.notes]
os.remove(mixerPad.path)
instance.pads.refresh()
instance.runtime = realRuntime

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
assert debuglog.path() == os.path.join(DATA, "logs", "visionclaw.log") and debuglog.detailed()
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

# --- The control the user is on, in plain words (about_focus, claw/focus.py) ---
# No picture is taken in a test: without one, nothing is asked of a model.
savedGrab = instance._grab


def noPicture(box=None):
	raise RuntimeError("no picture in a test")


instance._grab = noPicture
sys.modules["api"].getForegroundObject = lambda: types.SimpleNamespace(name="New message", appModule=types.SimpleNamespace(appName="mailer"))
worked, result = registry.call(taskModule.Task("t"), "about_focus", {"asked": "what is the current focused control"})
assert worked and result.startswith("The focus is on the button \"Send\" in the window \"New message\" of the program mailer."), result
for said in ("It is 2 of 5.", "It is inside the dialog \"Compose\".", "It says of itself: Sends the message.",
		"Its own shortcut key is alt+s.", "Press Space or Enter to press it."):
	assert said in result, (said, result)
assert "focusable" not in result and "Window class" not in result, result
worked, result = registry.call(taskModule.Task("t"), "about_focus", {"asked": "what does this button do"})
assert worked and "Pressing Enter or Space presses the button \"Send\"." in result and "guess" not in result, result
worked, result = registry.call(taskModule.Task("t"), "about_focus", {"asked": "what is the navigator object on"})
assert worked and result.startswith("The navigator object is the dialog \"Compose\""), result
box = types.SimpleNamespace(
	name="Remember me", role=Role(name="CHECKBOX", displayString="check box"), value=None, description="",
	states=[Role(name="FOCUSABLE"), Role(name="FOCUSED")], keyboardShortcut="", location=None,
	appModule=types.SimpleNamespace(appName="mailer"), positionInfo={}, parent=None)
sys.modules["api"].getFocusObject = lambda: box
worked, result = registry.call(taskModule.Task("t"), "about_focus", {"asked": "is this checkbox checked"})
assert worked and result.startswith("No. The focus is on the check box \"Remember me\"") and "It is not checked." in result, result
box.states.append(Role(name="CHECKED"))
worked, result = registry.call(taskModule.Task("t"), "about_focus", {"asked": "is this box ticked?"})
assert worked and result.startswith("Yes.") and "It is checked." in result, result
# Without a name, and without a picture to read one from: said so, nothing made up.
bare = types.SimpleNamespace(
	name="", role=Role(name="BUTTON", displayString="button"), value=None, description="", states=[], keyboardShortcut="",
	location=types.SimpleNamespace(left=10, top=10, width=20, height=20), appModule=types.SimpleNamespace(appName="mailer"),
	positionInfo={}, parent=None)
sys.modules["api"].getFocusObject = lambda: bare
worked, result = registry.call(taskModule.Task("t"), "about_focus", {"asked": "what does this button do"})
assert worked and "It has no name of its own, and none could be found for it." in result, result
assert "Nothing tells what it does: it has no name and no description." in result, result
sys.modules["api"].getFocusObject = lambda: button
instance._grab = savedGrab
assert registry.get("about_focus").looks and not registry.get("about_focus").changes

# --- The audit of the whole NVDA, and VisionClaw's log, opened only when asked ---
started = []
realStartfile = getattr(os, "startfile", None)
os.startfile = started.append
try:
	sys.modules["api"].getFocusObject = lambda: types.SimpleNamespace(appModule=None, treeInterceptor=None)
	worked, result = registry.call(taskModule.Task("t"), "audit_nvda", {"asked": "do a full audit of nvda"})
	auditPath = os.path.join(DATA, "nvda-audit.md")
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
notesFile = os.path.join(DATA, "notes", "spacetrader.md")
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
	describe=lambda image, prompt, maxTokens, cancel=None, system=None: systems.append(system) or "A menu.",
	unloadIdle=lambda *args: None)
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

# --- The developer guides put to use, add-ons by what the user wants, and NVDA Coach ---
# tests/test_guides.py checks the plain parts; here the tools, in the stand-in NVDA.
from visionClaw.claw import addons as addonsModule  # noqa: E402
from visionClaw.claw import guides as guidesModule  # noqa: E402

# Whether the running NVDA has a name: asked of loaded modules only, and nothing is imported or called.
quokkas = types.ModuleType("quokkatones")
quokkas.beep = lambda *args: None
quokkas.Role = type("Role", (), {"BUTTON": 1})
sys.modules["quokkatones"] = quokkas
assert nvdatools.nvdaHas("quokkatones.beep") is True and nvdatools.nvdaHas("quokkatones.Role.BUTTON") is True
assert nvdatools.nvdaHas("quokkatones.gone") is False and nvdatools.nvdaHas("quokkatones.Role.LINK") is False
assert nvdatools.nvdaHas("nosuchmodule.thing") is None and nvdatools.nvdaHas("quokkatones.beep.deeper") is None

FACTS_WIKI = (
	"## Useful modules\n\n- `quokkatones.beep(pitch in hertz, duration in milliseconds)`: Plays a tone of specified pitch.\n"
	"- `quokkatones.gone(text)`: Retrieves the wombat that was removed long ago.\n\n"
	+ "".join(f"## Lesson {n}\n\n{'An add-on is a package, says lesson %d. ' % n * 40}\n\n" for n in range(8)))
nvdatools.net.fetchText = lambda url, limit=None, hosts=None: GUIDE if url.endswith(".html") else FACTS_WIKI
instance.clawAsk = lambda question, choices: 0
conf["visionClaw"]["confirmChanges"] = False
worked, result = registry.call(taskModule.Task("test"), "update_guides", {})
assert worked and "it is given the lines of them that fit" in result and "the models" not in result.lower(), result
# The writer of an add-on is given the line that fits, and never one whose name this NVDA no longer has.
lines = nvdatools.guideLines(instance, "Beep when a link gets the focus.")
assert lines == guidesModule.CODER_HEAD + "\n- quokkatones.beep(pitch in hertz, duration in milliseconds): Plays a tone of specified pitch.", lines
assert nvdatools.guideLines(instance, "Retrieve the wombat when I press NVDA+alt+W.") == ""
assert nvdatools.guideLines(instance, "Say hello when I press NVDA+shift+H.") == ""
# In what the writer reads, the lines of the guides come before VisionClaw's own notes, which are cut off last.
notes = nvdatools.coderNotes(instance, taskModule.Task("t"), "Beep when a link gets the focus.", "OWN NOTES")
assert notes.endswith("OWN NOTES") and guidesModule.CODER_HEAD in notes and notes.index(guidesModule.CODER_HEAD) < notes.index("OWN NOTES"), notes
notes = nvdatools.coderNotes(instance, taskModule.Task("t"), "Say hello when I press NVDA+shift+H.", "OWN NOTES")
assert notes.endswith("OWN NOTES") and guidesModule.CODER_HEAD not in notes, notes

# Which guides are here is said by plain code, word for word.
worked, result = registry.call(taskModule.Task("test"), "guides_info", {"asked": "which developer guides do I have"})
assert worked and result.startswith("The NVDA Developer Guide by NV Access, downloaded today."), result
assert instance.guidesDir in result and registry.get("guides_info").tell == "verbatim"
# Deleting them is asked about, and afterwards nothing of them is looked up or given.
conf["visionClaw"]["confirmChanges"] = True
del questions[:]
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(taskModule.Task("test"), "remove_guides", {})
assert worked and result == "You said no, so nothing was changed." and instance.devGuides.here(), result
assert questions[0].startswith("Delete the NVDA developer guides from this computer?"), questions
instance.clawAsk = lambda question, choices: 0
worked, result = registry.call(taskModule.Task("test"), "remove_guides", {})
assert worked and result.startswith("Deleted from this computer: the NVDA Developer Guide and the NVDA Add-on Development Guide."), result
assert not instance.devGuides.here() and nvdatools.guideLines(instance, "Beep when a link gets the focus.") == ""
worked, result = registry.call(taskModule.Task("test"), "guides_info", {"asked": "which developer guides do I have"})
assert worked and result.startswith("No developer guides are on this computer yet."), result
worked, result = registry.call(taskModule.Task("test"), "remove_guides", {})
assert worked and result == "No developer guides were downloaded, so there is nothing to delete.", result
# With the guide that comes with every build: it is there without a download, and it is not deleted.
shippedGuides.SHIPPED = SHIPPED_GUIDES
instance.knowledge.replaceSource(shippedGuides.SOURCE, lambda: shippedGuides.load(instance.guidesDir))
worked, result = registry.call(taskModule.Task("test"), "guides_info", {"asked": "which developer guides do I have"})
assert worked and result.startswith("The NVDA Developer Guide by NV Access came with VisionClaw, as it was on "), result
worked, result = registry.call(taskModule.Task("test"), "remove_guides", {})
assert worked and result == (
	"No developer guides were downloaded, so there is nothing to delete. The copy that came with VisionClaw stays; "
	"it is part of the add-on."), result
worked, result = registry.call(taskModule.Task("test"), "search_help", {"words": "extension points action decider"})
assert worked and "NVDA Developer Guide: " in result, result
shippedGuides.SHIPPED = ""
instance.knowledge.replaceSource(shippedGuides.SOURCE, lambda: shippedGuides.load(instance.guidesDir))
conf["visionClaw"]["confirmChanges"] = False

# An add-on that is not named, and something the user wants to do: the add-ons are asked which of them does it.
sys.modules["addonHandler"].getAvailableAddons = lambda: [clock]
sys.modules["addonHandler"].getRunningAddons = lambda: [clock]
worked, result = registry.call(taskModule.Task("t"), "addon_info", {"addon": "all", "about": "is there an add-on that rings alarms"})
assert worked and result.startswith("One add-on installed in NVDA says it does this.\nThe add-on Clock and calendar: "), result
assert "Alarms ring at the time you set." in result, result
worked, result = registry.call(taskModule.Task("t"), "addon_info", {"addon": "all", "about": "do I have an add-on for sudoku"})
assert worked and result.startswith("None of the 1 add-ons installed in NVDA says anything about sudoku."), result
# With nothing that is wanted, it is the list as before.
worked, result = registry.call(taskModule.Task("t"), "addon_info", {"addon": "all", "about": "which add-ons do I have"})
assert worked and result == "Add-ons installed (1): Clock and calendar 2.1 (enabled).", result
found = accesstools.installedAddons()
assert [(addon.ident, addon.name, addon.state) for addon in found] == [("clock", "Clock and calendar", addonsModule.ON)], found
# A command that an add-on adds says which add-on it is from, when a question is answered with it.
clockModule = types.ModuleType("globalPlugins.clockStandIn")
clockModule.__file__ = os.path.join(addonDir, "globalPlugins", "clockStandIn.py")
sys.modules["globalPlugins.clockStandIn"] = clockModule
assert accesstools.addonOwners().get("globalPlugins.clockStandIn") == "Clock and calendar", accesstools.addonOwners()
from visionClaw import asktools as askModule  # noqa: E402
ClockPlugin = type("ClockPlugin", (), {"__module__": "globalPlugins.clockStandIn"})
clockCommand = nvdatools._Command("sayAlarm", "sayAlarm", ClockPlugin, "Says when the next alarm rings", "Clock", ["NVDA+f11"], ["kb:nvda+f11"])
fromClock = askModule.commandPassages([clockCommand], "notepad", accesstools.addonOwners())
assert fromClock[0].line().startswith("From the add-on Clock and calendar: sayAlarm: Says when the next alarm rings. Keys: NVDA+f11."), fromClock[0].line()
assert askModule.commandPassages([clockCommand], "notepad")[0].origin == "NVDA"
del sys.modules["globalPlugins.clockStandIn"]

# NVDA Coach is not installed. Asked for by name: said so, and nothing is installed. Asked to be taught
# something: NVDA itself answers, and the Coach is named once.
worked, result = registry.call(taskModule.Task("t"), "coach", {"asked": "open NVDA Coach"})
assert worked and result == addonsModule.coachMissing(None) and "does not install add-ons" in result, result
worked, result = registry.call(taskModule.Task("t"), "coach", {"asked": "teach me how to hear the current date"})
assert worked and result.endswith(addonsModule.COACH_ABSENT) and "date" in result.lower() and "f12" in result.lower(), result

# NVDA Coach is installed: its lessons are read from its own files, and its own command opens it.
coachDir = tempfile.mkdtemp()
lessonDir = os.path.join(coachDir, "globalPlugins", "nvdaCoach", "lessons", "en")
os.makedirs(lessonDir)
with open(os.path.join(lessonDir, "start.json"), "w", encoding="utf-8") as f:
	json.dump({"id": "start", "title": "Getting Started", "order": 1, "lessons": [
		{"id": "title", "title": "Read the Title Bar", "order": 1, "steps": [
			{"type": "info", "instruction": "NVDA+T reads the title bar of the window. Press Enter to continue.",
				"hints": ["Hold the NVDA key and press T."]}]}]}, f)
coachAddon = types.SimpleNamespace(
	name="nvdaCoach", path=coachDir, isDisabled=False, isRunning=True,
	manifest={"summary": "NVDA Coach - Interactive Screen Reader Training", "version": "1.6.0", "author": "Someone",
		"description": "Interactive screen reader training."},
	getDocFilePath=lambda: None)
sys.modules["addonHandler"].getAvailableAddons = lambda: [clock, coachAddon]
opened = []
Commands.script_toggleCoach = lambda self, gesture: opened.append("coach")
MAPPINGS["NVDA Coach"] = {"coach": info("toggleCoach", "Show NVDA Coach window, or open the lesson picker", ["kb:nvda+shift+c"])}
SHOWN["kb:nvda+shift+c"] = "NVDA+shift+c"
worked, result = registry.call(taskModule.Task("t"), "coach", {"asked": "give me a hint about reading the title bar"})
assert worked and result.startswith('From NVDA Coach, the lesson "Read the Title Bar" in Getting Started, a hint: Hold the NVDA key and press T.'), result
assert not opened
worked, result = registry.call(taskModule.Task("t"), "coach", {"asked": "coach me on the title bar"})
assert worked and "step 1 of 1: NVDA+T reads the title bar of the window." in result and "press NVDA+shift+c" in result, result
assert "Press Enter to continue" not in result and not opened
worked, result = registry.call(taskModule.Task("t"), "coach", {"asked": "which lessons does NVDA Coach have"})
assert worked and result.startswith("NVDA Coach has 1 lesson in 1 chapter: Getting Started, 1 lesson."), result
# Only when its own window is asked for is its command run, once.
worked, result = registry.call(taskModule.Task("t"), "coach", {"asked": "open NVDA Coach"})
assert worked and result == addonsModule.COACH_OPENED and opened == ["coach"], (result, opened)
assert registry.get("coach").tell == "verbatim" and "coach" in planner.RECIPES
# Turned off: said so, nothing is run, and VisionClaw does not turn it on.
coachAddon.isDisabled = True
worked, result = registry.call(taskModule.Task("t"), "coach", {"asked": "open NVDA Coach"})
assert worked and result == addonsModule.coachMissing(addonsModule.OFF) and opened == ["coach"], result
sys.modules["addonHandler"].getAvailableAddons = lambda: [clock]
del MAPPINGS["NVDA Coach"]

# --- Free training material, downloaded only after a yes; NVDA's own help kept as Markdown files ---
# tests/test_training.py checks the plain parts; here the tools, in the stand-in NVDA.
from visionClaw.claw import helpfiles as helpModule  # noqa: E402
from visionClaw.claw import training as trainingModule  # noqa: E402

LESSON_PAGE = (
	"<html><body><header>Menu</header><main><h1>Lesson</h1><h2>Transcript</h2>"
	+ "".join(f"<p>[Ricky] In part {n} the quokkalesson shows how the Windows key opens the Start menu.</p>" for n in range(30))
	+ "<h2>Learn NVDA</h2><p>More lessons.</p></main></body></html>")
WIKI_LESSON = "## Cursors\n\nThe JAWS cursor is called object navigation with the review cursor in NVDA.\n\n" + "More for people from JAWS. " * 80
trainingFetched = []


def trainingFetch(url, limit=None, hosts=None):
	trainingFetched.append((url, hosts, limit))
	return WIKI_LESSON if url.startswith(trainingModule.WIKI) else LESSON_PAGE


nvdatools.net.fetchText = trainingFetch
conf["visionClaw"]["confirmChanges"] = False
# It is asked about even when the user turned confirmations off, the question names every site, and a no
# downloads nothing.
del questions[:]
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(taskModule.Task("test"), "update_training", {})
assert worked and result == "You said no, so nothing was changed." and trainingFetched == [], (result, trainingFetched)
assert questions[0] == trainingModule.question() and "afb.org" in questions[0] and "18 requests are sent" in questions[0]
instance.clawAsk = lambda question, choices: 0
worked, result = registry.call(taskModule.Task("test"), "update_training", {})
assert worked and result.startswith("Downloaded 6 pages of the NVDA wiki and kept them as Markdown."), result
assert len(trainingFetched) == 18 and all(hosts == trainingModule.HOSTS and limit == trainingModule.MAX_BYTES for _url, hosts, limit in trainingFetched)
assert {url.split("/")[2] for url, _hosts, _limit in trainingFetched} == {"raw.githubusercontent.com", "afb.org", "hadleyhelps.org"}
assert os.path.isfile(os.path.join(instance.trainingDir, "hadley-nvda", "useful-shortcuts.md"))
assert registry.get("update_training").tell == "verbatim" and "update_training" in planner.RECIPES
# What is here is said by plain code, with where NVDA's own help is kept as Markdown.
worked, result = registry.call(taskModule.Task("test"), "training_info", {"asked": "which training material do I have"})
assert worked and result.startswith("6 pages of the NVDA wiki, by NVDA's community, on GitHub, downloaded today."), result
assert instance.trainingDir in result and instance.helpDir in result, result
# A question that asks to be taught is given a lesson with what NVDA says itself; one that does not, is not.
worked, result = registry.call(taskModule.Task("test"), "look_up", {"question": "Teach me how the Windows key opens the Start menu"})
assert worked and "From AFB's Learn NVDA lessons, from 2016:" in result and "quokkalesson" in result, result
worked, result = registry.call(taskModule.Task("test"), "look_up", {"question": "How does the Windows key open the Start menu"})
assert "quokkalesson" not in result, result
# The page for people who come from JAWS: when JAWS is named, or when VisionClaw remembers that the user does.
worked, result = registry.call(taskModule.Task("test"), "look_up", {"question": "What is the review cursor in object navigation?"})
assert "From the NVDA wiki" not in result, result
instance.memories.add("I come from JAWS", kind="you")
worked, result = registry.call(taskModule.Task("test"), "look_up", {"question": "What is the review cursor in object navigation?"})
assert worked and "From the NVDA wiki: Switching from JAWS to NVDA: Cursors." in result, result
# NVDA's user guide was turned into a Markdown file by the question, and the add-ons' help with it.
assert os.path.isfile(os.path.join(instance.helpDir, "nvda-user-guide.md"))
with open(os.path.join(instance.helpDir, "nvda-user-guide.md"), encoding="utf-8") as f:
	assert helpModule.madeFrom(f.read()) == guidePath
accesstools.installedAddons()
with open(os.path.join(instance.helpDir, "addons", "clock.md"), encoding="utf-8") as f:
	clockHelp = f.read()
assert clockHelp.startswith("# The help of the add-on Clock and calendar\n") and "## Alarms\n\nAlarms ring at the time you set." in clockHelp, clockHelp
# Deleting is asked about, and afterwards nothing of it is looked up.
conf["visionClaw"]["confirmChanges"] = True
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(taskModule.Task("test"), "remove_training", {})
assert worked and result.startswith("Deleted from this computer: the NVDA wiki, AFB's Learn NVDA lessons, from 2016, Hadley's NVDA workshops."), result
assert questions[-1].startswith("Delete the downloaded NVDA training material from this computer?")
worked, result = registry.call(taskModule.Task("test"), "look_up", {"question": "Teach me how the Windows key opens the Start menu"})
assert "quokkalesson" not in result, result
worked, result = registry.call(taskModule.Task("test"), "remove_training", {})
assert worked and result == "No training material is on this computer, so there is nothing to delete.", result
conf["visionClaw"]["confirmChanges"] = False

# --- What can be downloaded: said when asked, and once after an answer that it fits ---
from visionClaw.claw import offers as offersModule  # noqa: E402

shippedGuides.SHIPPED = SHIPPED_GUIDES
worked, result = registry.call(taskModule.Task("test"), "downloads_info", {})
assert worked and result == offersModule.overview({"devGuide": True, "addonGuide": False, "training": False}), result
assert registry.get("downloads_info").tell == "verbatim" and "downloads_info" in planner.RECIPES
assert instance.downloadState() == {"devGuide": True, "addonGuide": False, "training": False, "speech": False}
# The orchestrator is given the sentences, and says each once after a request that was done.
assert instance.orchestrator.offer is not None
doneTask = taskModule.Task("Write an add-on that beeps when a link gets the focus")
doneTask.steps = [planner.Step("Writing", "create_addon", "x", "x", recipe="write_addon")]
doneTask.steps[0].status = taskModule.STEP_DONE
said = instance.orchestrator._offered(doneTask, doneTask.request, ["write_addon"])
assert said == offersModule.SENTENCES[offersModule.GUIDES], said
assert instance.orchestrator._offered(doneTask, doneTask.request, ["write_addon"]) == ""
assert os.path.isfile(os.path.join(os.path.dirname(instance.guidesDir), "offered.json"))
# After a request that failed, nothing is offered.
failedTask = taskModule.Task("Teach me how to read a web page")
failedTask.steps = [planner.Step("Asking", "look_up", "x", "x", recipe="nvda_question")]
failedTask.steps[0].status = taskModule.STEP_FAILED
assert instance.orchestrator._offered(failedTask, failedTask.request, ["nvda_question"]) == ""
shippedGuides.SHIPPED = ""

# --- The computer itself: things opened by name, the Recycle Bin, the volume, windows, files, facts, power ---
# The real tools, with Windows stood in for (see the top of this file).
from visionClaw.claw import router, shapes  # noqa: E402

conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
for name in ("open_thing", "recycle_bin", "empty_bin", "system_volume", "window", "files", "computer_info", "power", "set_control"):
	assert name in planner.RECIPES and registry.has(planner.RECIPES[name][2]), name
for name in ("empty_recycle_bin", "power"):
	assert registry.get(name).changes, name
# A place of Windows by its name: one thing is found, the user is asked, and Windows is handed what is fixed
# in the code for it, never something a model wrote.
task = taskModule.Task("open my recycle bin")
del did[:]
worked, result = registry.call(task, "find_thing", {"words": computer.wanted(task.request)})
assert worked and result == "place-recycle-bin: Recycle Bin, a place of Windows.", result
worked, result = registry.call(task, "open_thing", {"thing": "place-recycle-bin", "asked": task.request})
assert worked and result.startswith("Opened Recycle Bin."), result
assert did == [("open", "shell:RecycleBinFolder", None)] and questions == ["Open Recycle Bin, a place of Windows?"], (did, questions)
# A program of the Start menu by a word of its name: both that have it are offered, and the id decides.
task = taskModule.Task("open trader")
worked, result = registry.call(task, "find_thing", {"words": "trader"})
assert worked and result.splitlines() == [
	"program-space-trader: Space Trader, a program.", "program-space-trader-editor: Space Trader Editor, a program."], result
worked, result = registry.call(task, "open_thing", {"thing": "program-space-trader-editor", "asked": task.request})
assert worked and did[-1] == ("open", r"C:\Start\Space Trader Editor.lnk", None), did
worked, result = registry.call(task, "open_thing", {"thing": "program-doom", "asked": task.request})
assert not worked and "Copy an id exactly from find_thing" in result, result
# A file of the user's own, by a word of its name, when nothing else has that name.
task = taskModule.Task("open budget")
worked, result = registry.call(task, "find_thing", {"words": "budget"})
assert worked and result == "file-budget-2026-xlsx: budget 2026.xlsx in Documents, a file.", result
# Nothing by that name: said so, with what to ask for instead; and a no from the user opens nothing.
worked, result = registry.call(taskModule.Task("open my holiday plans"), "find_thing", {"words": "holiday plans"})
assert not worked and result.startswith('Nothing called "holiday plans" was found') and "ask to click it instead" in result, result
task = taskModule.Task("open notepad")
registry.call(task, "find_thing", {"words": "notepad"})
instance.clawAsk = lambda question, choices: 1
count = len(did)
worked, result = registry.call(task, "open_thing", {"thing": "notepad", "asked": task.request})
assert worked and result == "You said no, so nothing was changed." and len(did) == count, result
instance.clawAsk = lambda question, choices: questions.append(question) or 0
pc["refuse"] = True
worked, result = registry.call(task, "open_thing", {"thing": "notepad", "asked": task.request})
assert not worked and result.startswith("Notepad could not be opened."), result
pc["refuse"] = False

# The Recycle Bin: what it holds, in Windows' own numbers; and emptying it, which is always asked about.
worked, result = registry.call(taskModule.Task("check my recycle bin"), "recycle_bin", {})
assert worked and result.startswith("The Recycle Bin holds 3 items, 5 MB in all. It does not need emptying for room"), result
conf["visionClaw"]["confirmChanges"] = False
del questions[:], did[:]
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(taskModule.Task("empty the recycle bin"), "empty_recycle_bin", {"asked": "empty the recycle bin"})
assert worked and result == "You said no, so nothing was changed." and not did, (result, did)
assert questions == [
	"Empty the Recycle Bin? It holds 3 items, 5 MB in all. They are deleted for good and cannot be brought back."], questions
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(taskModule.Task("empty the recycle bin"), "empty_recycle_bin", {"asked": "empty the recycle bin"})
assert worked and result == "Emptied the Recycle Bin: 3 items, 5 MB, deleted for good." and did == [("empty",)], result
worked, result = registry.call(taskModule.Task("empty the recycle bin"), "empty_recycle_bin", {"asked": "empty the recycle bin"})
assert worked and result == "The Recycle Bin is already empty. Nothing was deleted." and did == [("empty",)], result
assert registry.call(taskModule.Task("x"), "recycle_bin", {})[1] == "The Recycle Bin is empty. There is nothing to empty."

# The computer's volume. Turning it down stops where NVDA's speech can still be heard.
del did[:]
worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": "turn down my system volume"})
assert worked and result == "The computer's volume was 40 percent and is now 30 percent." and did == [("volume", 30)], result
pc["volume"] = 14
worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": "turn the computer's volume down a lot"})
assert worked and pc["volume"] == 10 and result.endswith(
	"It was not turned lower than 10 percent, so that NVDA's speech can still be heard."), result
worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": "turn the computer's volume down"})
assert worked and pc["volume"] == 10 and result.startswith("The computer's volume stays at 10 percent"), result
# Muting, or a number too low to hear, would silence NVDA: refused when no braille display is in use, whatever
# the user answers; with a display in use it is asked about, always.
del did[:], questions[:]
for said in ("mute my computer", "set the system volume to 3 percent"):
	worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": said})
	assert worked and result.startswith("VisionClaw did not do this. Muting the computer's sound") and "no braille display is in use" in result, result
assert not did and not questions and not pc["muted"]
sys.modules["braille"].handler.display = types.SimpleNamespace(name="freedomScientific")
worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": "mute my computer"})
assert worked and result == "The computer's sound is muted. To get it back, say: unmute the computer." and did == [("mute", True)], result
assert questions and "too quiet to hear NVDA's speech: muted. Only braille would be left." in questions[0], questions
sys.modules["braille"].handler.display = types.SimpleNamespace(name="noBraille")
worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": "unmute the computer"})
assert worked and result == "The sound is on again. The computer's volume is at 10 percent." and not pc["muted"], result
worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": "what is the volume of my computer"})
assert worked and result == "The computer's volume is at 10 percent.", result
worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": "set the computer's volume to 60 percent"})
assert worked and result == "The computer's volume was 10 percent and is now 60 percent.", result
# NVDA's own volume is not this tool's: the words must be about the computer.
worked, result = registry.call(taskModule.Task("x"), "system_volume", {"asked": "make the voice louder"})
assert not worked and "does not say what to do with the computer's volume" in result, result

# Windows that are open: the user's own words say which one, whatever a model wrote in the form.
task = taskModule.Task("close windows settings")
worked, result = registry.call(task, "list_windows", {"about": task.request})
assert worked and result.splitlines() == [
	"3 windows open:", "1. Inbox (3) - sam@example.com - Gmail - Google Chrome, in front", "2. Settings",
	"3. notes.txt - Notepad, minimized"], result
assert shapes.namesIn(result) == [line.split(". ", 1)[1] for line in result.splitlines()[1:]]
del did[:]
conf["visionClaw"]["confirmChanges"] = True
del questions[:]
worked, result = registry.call(task, "window_action", {"window": "1", "action": "close", "asked": task.request})
assert worked and result == "Closed the window Settings." and did == [("close", 12)], (result, did)
assert questions == ["Close the window Settings?"], questions
conf["visionClaw"]["confirmChanges"] = False
task = taskModule.Task("switch to notepad")
registry.call(task, "list_windows", {"about": task.request})
worked, result = registry.call(task, "window_action", {"window": "Settings", "action": "switch to", "asked": task.request})
assert worked and result == "Switched to the window notes.txt - Notepad." and did[-1] == ("focus", 13), result
# A window that stays open after it was asked to close: that is said, not claimed as closed.
worked, result = registry.call(task, "window_action", {"window": "3", "action": "close", "asked": "close notepad"})
assert worked and result.startswith("The window notes.txt - Notepad was asked to close and is still open."), result
# Where the words name no window that is open, what the model chose from the list is used; a name that is not
# in the list is refused.
task = taskModule.Task("maximize the spreadsheet")
registry.call(task, "list_windows", {"about": task.request})
worked, result = registry.call(task, "window_action", {"window": "2. Settings", "action": "maximize", "asked": task.request})
assert worked and result == "Maximized the window Settings." and did[-1] == ("maximize", 12), result
worked, result = registry.call(task, "window_action", {"window": "Excel", "action": "maximize", "asked": task.request})
assert not worked and 'No open window is called "Excel"' in result, result
worked, result = registry.call(taskModule.Task("x"), "window_action", {"window": "", "action": "minimize", "asked": "minimize all windows"})
assert worked and did[-1] == ("minimize all",) and result.startswith("Every window was minimized."), result

# Files, facts and power.
worked, result = registry.call(taskModule.Task("x"), "find_files", {"asked": "what is in my downloads folder"})
assert worked and result == (
	"1 item in Downloads. The newest first:\n1. setup.exe, 5 MB, in Downloads, changed November 18, 2026"), result
worked, result = registry.call(taskModule.Task("x"), "find_files", {"asked": "find the file named budget"})
assert worked and result.startswith("1 thing with budget in the name, in your Desktop, Documents") and "budget 2026.xlsx" in result, result
worked, result = registry.call(taskModule.Task("x"), "computer_info", {"topic": "disk"})
assert worked and result == "Drive C: (System) has 200 GB free of 500 GB, 40 percent.", result
worked, result = registry.call(taskModule.Task("x"), "computer_info", {"topic": "uptime"})
assert worked and result == "The computer has been on for 1 day and 9 hours since it was last started.", result
worked, result = registry.call(taskModule.Task("x"), "computer_info", {"topic": "programs"})
assert worked and result == "Programs with a window open: google chrome, Settings, notepad.", result
worked, result = registry.call(taskModule.Task("x"), "computer_info", {"topic": "overview"})
assert worked and "TESTPC" in result and "31 GB of memory" in result and "Drive C:" in result, result
# Restarting is always asked about, whatever the settings say; a no does nothing; calling it off asks nothing.
del did[:], questions[:]
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(taskModule.Task("x"), "power", {"asked": "restart my computer"})
assert worked and result == "You said no, so nothing was changed." and not did, result
assert questions[0].startswith("Restart the computer in 30 seconds? Work that is not saved will be lost."), questions
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(taskModule.Task("x"), "power", {"asked": "shut down the computer"})
assert worked and did == [("power", "shut down")] and result == (
	"The computer shuts down in 30 seconds. To call it off, say: cancel the shutdown."), result
del questions[:]
worked, result = registry.call(taskModule.Task("x"), "power", {"asked": "cancel the shutdown"})
assert worked and did[-1] == ("power", "cancel") and not questions and result == "The restart or shutdown was called off.", result
worked, result = registry.call(taskModule.Task("x"), "power", {"asked": "restart nvda"})
assert not worked and "does not say whether to lock the computer" in result, result

# What the user wants closed is no window of its own, as the settings panel inside a program: Escape, after a
# question, and it is said that this is what was done.
task = taskModule.Task("close the equalizer panel")
registry.call(task, "list_windows", {"about": task.request})
conf["visionClaw"]["confirmChanges"] = True
del questions[:], did[:]
worked, result = registry.call(task, "window_action", {"window": "equalizer panel", "action": "close", "asked": task.request})
assert worked and did == [("escape",)] and result.startswith(
	"No window of that name is open, so Escape was pressed in the window in front."), (result, did)
assert questions and questions[0].startswith("No window of that name is open. It may be a panel inside the window in front."), questions
conf["visionClaw"]["confirmChanges"] = False

# --- A named control of the program in front: on or off, up or down, also on another page of its dialog ---
import api as apiStub  # noqa: E402
from visionClaw import controltools, deepquery as deep  # noqa: E402
from visionClaw.claw import controls  # noqa: E402

controltools._SETTLE = 0
focused = []


class Ctl:
	"""A control as NVDA would give it: a name, a kind, states, a value, and what pressing it does."""

	def __init__(self, name, role, states=(), value="", span=None):
		self.name, self.role, self.value, self.span = name, types.SimpleNamespace(name=role), value, span
		self.states = [types.SimpleNamespace(name=state) for state in states]
		self.location = types.SimpleNamespace(left=10, top=10, width=100, height=20)
		self.children = []
		self.pressed = 0

	def has(self, state):
		return any(one.name == state for one in self.states)

	def doAction(self):
		self.pressed += 1
		if self.role.name == "CHECKBOX":
			self.states = [] if self.has("CHECKED") else [types.SimpleNamespace(name="CHECKED")]
		if self.role.name == "TAB":
			dialog.show(self.name)

	def setFocus(self):
		focused.append(self.name)


class Dialog(Ctl):
	"""A dialog of three pages. Only the controls of the page that is shown are there."""

	def __init__(self):
		Ctl.__init__(self, "Sound Studio settings", "DIALOG")
		self.tabs = [Ctl("General", "TAB", ("SELECTED",)), Ctl("Graphics", "TAB"), Ctl("Keyboard", "TAB")]
		self.pages = {
			"General": [Ctl("Start with Windows", "CHECKBOX", ("CHECKED",)), Ctl("Volume", "SLIDER", value="40", span={"now": 40.0}),
				Ctl("Output device", "COMBOBOX", value="Speakers")],
			"Graphics": [Ctl("Use NVIDIA GPU (high performance)", "CHECKBOX")],
			"Keyboard": [Ctl("Enable media keys", "CHECKBOX", ("CHECKED",)), Ctl("Media key volume step", "SLIDER", value="5", span={"now": 5.0})],
		}
		self.shown = "General"

	def show(self, name):
		self.shown = name
		for tab in self.tabs:
			tab.states = [types.SimpleNamespace(name="SELECTED")] if tab.name == name else []

	@property
	def children(self):
		return self.tabs + self.pages[self.shown]

	@children.setter
	def children(self, value):
		pass


def fakeTurn(obj, direction, size):
	now = max(0.0, min(100.0, obj.span["now"] + 10 * direction))
	moved, obj.span["now"], obj.value = now != obj.span["now"], now, str(int(now))
	return moved, obj.value


dialog = Dialog()
realForeground, apiStub.getForegroundObject = apiStub.getForegroundObject, lambda: dialog
realRange, realTurn = deep.rangeOf, deep.turn
deep.rangeOf = lambda obj: dict(obj.span, low=0.0, high=100.0, small=1.0, readOnly=False) if getattr(obj, "span", None) else None
deep.turn = fakeTurn
instance.clawScreen.items = lambda: types.SimpleNamespace(items=[], web=False)
conf["visionClaw"]["confirmChanges"] = True
del questions[:]
# The control is on another page of the dialog: the pages are gone through, and the user is told which page.
worked, result = registry.call(taskModule.Task("x"), "set_control", {
	"asked": "In this multipage dialog, turn on my nvidia gpu for this program"})
assert worked and result == "Use NVIDIA GPU (high performance), on the page Graphics, was off and is now on.", result
assert questions == ["Turn Use NVIDIA GPU (high performance) on?"] and dialog.shown == "Graphics", (questions, dialog.shown)
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "Turn off the media keys on my keyboard"})
assert worked and result == "Enable media keys, on the page Keyboard, was on and is now off.", result
# What is as it should be already is left alone, and nothing is asked.
del questions[:]
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "turn on start with windows in this program"})
assert worked and result == "Start with Windows, on the page General, is already on. Nothing was changed." and not questions, result
# A slider on the page that is shown: turned through Windows itself, and what it was and is now is said.
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "Turn the volume up a bit"})
assert worked and result == "Volume was 40 and is now 50.", result
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "turn the volume all the way down"})
assert worked and result == "Volume was 50 and is now 0.", result
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "turn the volume down"})
assert worked and result == "Volume did not change. It shows 0. It may be at its end, or the program did not take it.", result
# A wish that does not fit the kind of control, and a kind plain code does not set: said, with a keyboard way.
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "turn the volume off in this program"})
assert not worked and "turned up or down, not one that is on or off" in result, result
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "turn the output device up in this program"})
assert worked and result.startswith("Output device is not a control that is simply on or off or turned up or down; it shows Speakers.") and (
	focused == ["Output device"]), result
# No such control anywhere: every other page was looked at, the page that was shown is shown again, and it is said.
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "Turn the equalizer down"})
assert not worked and result.startswith(
	'No control called "equalizer" was found in the window in front: not in what NVDA knows of it, not on its 2 other '
	"pages, and not in its picture."), result
assert dialog.shown == "General"
# A no from the user changes nothing.
instance.clawAsk = lambda question, choices: 1
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "turn off start with windows in this program"})
assert worked and result == "You said no, so nothing was changed." and dialog.pages["General"][0].has("CHECKED"), result
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(taskModule.Task("x"), "set_control", {"asked": "what is on my screen"})
assert not worked and "does not say which control of this program to set" in result, result
apiStub.getForegroundObject, deep.rangeOf, deep.turn = realForeground, realRange, realTurn
conf["visionClaw"]["confirmChanges"] = False

# --- The user's own files: made, renamed, moved, copied, and moved to the Recycle Bin ---
# The real tool and the real search, in folders of the test's own that stand for the user's folders. Files there
# are really renamed and moved; the Recycle Bin is stood in for.
own = tempfile.mkdtemp(prefix="vcfiles-")
ownFolders = {name: os.path.join(own, name.capitalize()) for name in computer.FOLDERS}
for folder in ownFolders.values():
	os.makedirs(folder)
for where, name in (("documents", "budget.xlsx"), ("documents", "Budget notes.txt"), ("downloads", "report.pdf"),
		("downloads", "old notes.txt"), ("documents", "letter.docx")):
	with open(os.path.join(ownFolders[where], name), "w", encoding="utf-8") as f:
		f.write("x")
os.makedirs(os.path.join(ownFolders["documents"], "Old stuff"))
with open(os.path.join(ownFolders["documents"], "Old stuff", "inside.txt"), "w", encoding="utf-8") as f:
	f.write("x")
computertools.userFolders = lambda: ownFolders
computertools.searchFiles = realSearchFiles
assert "file_task" in planner.RECIPES and registry.get("change_file").changes
conf["visionClaw"]["confirmChanges"] = True
del questions[:]
instance.clawAsk = lambda question, choices: questions.append(question) or 0


def fileJob(said):
	return registry.call(taskModule.Task(said), "change_file", {"asked": said})


def there(where, *parts):
	return os.path.exists(os.path.join(ownFolders[where], *parts))


# A new folder, where the user says; with no place said it goes into Documents, and the question says so.
worked, result = fileJob("create a folder called Taxes in my documents")
assert worked and result == "Made the folder Taxes in Documents." and os.path.isdir(os.path.join(ownFolders["documents"], "Taxes")), result
assert questions[-1] == "Make the folder Taxes in Documents?", questions
worked, result = fileJob("make a new folder named Holiday Photos")
assert worked and there("documents", "Holiday Photos") and questions[-1].endswith("You named no place, so it goes into Documents."), questions
worked, result = fileJob("create a folder called Taxes in my documents")
assert worked and result == "There is already something called Taxes in Documents. Nothing was changed.", result
worked, result = fileJob("create a text file called shopping list on my desktop")
assert worked and result == "Made the text file shopping list.txt in Desktop." and there("desktop", "shopping list.txt"), result
# A name Windows does not take, and no name at all, are refused in words.
worked, result = fileJob("create a folder called a/b in my documents")
assert not worked and "Windows does not take these characters" in result, result
worked, result = fileJob("create a new folder")
assert not worked and result == "The request does not say the new name.", result
# Renaming keeps the ending where the user gave none; one file is named exactly, though another has the word.
worked, result = fileJob("rename the file budget to Budget 2026")
assert worked and result == "Renamed the file budget.xlsx, in Documents, to Budget 2026.xlsx.", result
assert there("documents", "Budget 2026.xlsx") and not there("documents", "budget.xlsx") and there("documents", "Budget notes.txt")
assert questions[-1] == "Rename the file budget.xlsx, in Documents, to Budget 2026.xlsx?", questions
# Nothing is ever overwritten.
worked, result = fileJob("rename letter.docx to Budget 2026.xlsx")
assert worked and result == "There is already something called Budget 2026.xlsx in Documents, so letter.docx was not renamed.", result
assert there("documents", "letter.docx")
# Moving: to one of the user's folders, or to a folder inside them by its name.
worked, result = fileJob("move the file report.pdf from my downloads to my documents")
assert worked and result == "Moved the file report.pdf from Downloads to Documents." and there("documents", "report.pdf"), result
worked, result = fileJob("move report.pdf to the Taxes folder in my documents")
assert worked and result == "Moved the file report.pdf from Documents to Documents, in Taxes." and there("documents", "Taxes", "report.pdf"), result
worked, result = fileJob("move report.pdf to the Taxes folder")
assert worked and result == "The file report.pdf is already in Documents, in Taxes. Nothing was changed.", result
worked, result = fileJob("move the file letter to the Receipts folder")
assert not worked and 'No folder called "receipts" was found' in result and there("documents", "letter.docx"), result
# Copying leaves the file where it is; a whole folder is not copied.
worked, result = fileJob("copy the file letter to my desktop")
assert worked and result.startswith("Copied the file letter.docx from Documents to Desktop.") and there("desktop", "letter.docx") and there("documents", "letter.docx"), result
worked, result = fileJob("copy the folder Old stuff to my desktop")
assert not worked and "copies single files, not whole folders" in result, result
# Deleting is moving to the Recycle Bin, and is always asked about, whatever the settings say.
conf["visionClaw"]["confirmChanges"] = False
del questions[:], recycled[:]
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = fileJob("delete the file old notes")
assert worked and result == "You said no, so nothing was changed." and not recycled and there("downloads", "old notes.txt"), result
assert questions == ["Move the file old notes.txt, in Downloads, to the Recycle Bin? It can be brought back from there."], questions
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = fileJob("delete the file old notes")
assert worked and recycled == [os.path.join(ownFolders["downloads"], "old notes.txt")] and result.startswith(
	"Moved the file old notes.txt, from Downloads, to the Recycle Bin."), (result, recycled)
worked, result = fileJob("delete the folder Old stuff")
assert worked and "It is a folder with 1 things in it, and they all go with it." in questions[-1] and not there("documents", "Old stuff"), questions
# No such file; no name; and several that fit: the user chooses, or none of them.
worked, result = fileJob("delete the file holiday plans")
assert not worked and result.startswith('No file or folder with "holiday plans" in its name was found'), result
worked, result = fileJob("delete this file")
assert not worked and "F2 renames it and Delete moves it to the Recycle Bin" in result, result
with open(os.path.join(ownFolders["downloads"], "Budget draft.txt"), "w", encoding="utf-8") as f:
	f.write("x")
asked = []
instance.clawAsk = lambda question, choices: asked.append((question, choices)) or len(choices) - 1
worked, result = fileJob("rename the file budget to Plan")
assert worked and result == "You chose none of them, so nothing was changed.", result
assert asked[0][0] == "Several files fit that name. Which one do you mean?" and len(asked[0][1]) == 4, asked
assert "Budget draft.txt, in Downloads" in asked[0][1] and asked[0][1][-1] == "None of these"
# What VisionClaw did to a file is in the list of changes and can be put back: the newest first.
instance.clawAsk = lambda question, choices: 0
worked, result = registry.call(taskModule.Task("what did you change"), "list_changes", {})
assert worked and "The file report.pdf: from Documents to Documents, in Taxes" in result, result
assert "The file Budget 2026.xlsx: from budget.xlsx to Budget 2026.xlsx" in result, result
worked, result = registry.call(taskModule.Task("undo that"), "undo_change", {"what": "undo that"})
assert worked and result == "The file report.pdf is back in Documents." and there("documents", "report.pdf"), result
worked, result = registry.call(taskModule.Task("undo that"), "undo_change", {"what": "undo that"})
assert worked and result == "The file report.pdf is back in Downloads." and there("downloads", "report.pdf"), result
worked, result = registry.call(taskModule.Task("undo that"), "undo_change", {"what": "undo that"})
assert worked and result == "The file Budget 2026.xlsx is called budget.xlsx again.", result
assert there("documents", "budget.xlsx") and not there("documents", "Budget 2026.xlsx")
# Something that was made is removed again only while it is empty.
worked, result = registry.call(taskModule.Task("undo that"), "undo_change", {"what": "undo that"})
assert worked and result == "Removed the text file shopping list.txt again." and not there("desktop", "shopping list.txt"), result
computertools.userFolders, computertools.searchFiles = realUserFolders, fakeSearch
computertools.userFolders = lambda: ownFolders
instance.clawAsk = lambda question, choices: questions.append(question) or 0

# Whether something is on the screen: NVDA's own names first, then the text that is shown, then the picture.

realFocus = apiStub.getFocusObject
icons = [types.SimpleNamespace(name=name) for name in ("Firefox", "Recycle Bin", "Steam")]
apiStub.getFocusObject = lambda: types.SimpleNamespace(name="Firefox", parent=types.SimpleNamespace(children=icons))
worked, result = registry.call(taskModule.Task("x"), "check_seen", {"what": "recycle bin", "asked": "If you see recycle bin, open it"})
assert worked and result == 'Yes: recycle bin is there: NVDA finds "Recycle Bin" where you are.', result
apiStub.getFocusObject = realFocus
instance._grab = lambda box: "picture"
realRecognize = computertools.ocr.recognize
computertools.ocr.recognize = lambda image: [[{"text": "Recycle"}, {"text": "Bin"}], [{"text": "Steam"}]]
worked, result = registry.call(taskModule.Task("x"), "check_seen", {"what": "recycle bin", "asked": "If you see recycle bin, open it"})
assert worked and result == "Yes: recycle bin is on the screen: its name is in the text that is shown.", result
# Not in any text: the model that sees is asked for yes or no, and a yes of its alone is said to be a model's.
computertools.ocr.recognize = lambda image: [[{"text": "Steam"}]]
computertools.prepareImage = lambda image, size: b"jpeg"
asked = []
realRuntime, instance.runtime = instance.runtime, types.SimpleNamespace(
	describe=lambda image, prompt, maxTokens, cancel=None, system=None: asked.append(prompt) or "Yes, at the top left.",
	unloadIdle=lambda *args: None, oneModel=lambda: False)
worked, result = registry.call(taskModule.Task("x"), "check_seen", {"what": "recycle bin", "asked": "If you see recycle bin, open it"})
assert worked and computer.says(result) and "says it sees recycle bin on the screen: Yes, at the top left." in result, result
assert result.endswith("a model can be wrong.") and "Begin your answer with the one word yes or the one word no" in asked[0], result
instance.runtime.describe = lambda image, prompt, maxTokens, cancel=None, system=None: "No, I do not see it."
worked, result = registry.call(taskModule.Task("x"), "check_seen", {"what": "recycle bin", "asked": "If you see recycle bin, open it"})
assert worked and not computer.says(result) and result.startswith("No: recycle bin is not on the screen"), result
instance.runtime = realRuntime
computertools.ocr.recognize = realRecognize

# Where the user is, as facts for the router: nothing in front is a web page here, and no controller is there.
facts = instance._clawFacts()
assert facts.get(router.CONTROLLER) is False and router.WEB in facts and router.DIRECT in facts, facts

# The whole of the request that failed for the owner, through the real tools, with one model for both jobs.
apiStub.getFocusObject = lambda: types.SimpleNamespace(name="Firefox", parent=types.SimpleNamespace(children=icons))


class DeskModel(FakeRuntime):
	def __init__(self):
		self.asked = []

	def oneModel(self):
		return True

	def describe(self, image, prompt, maxTokens, cancel=None, system=None):
		return "The desktop shows a grid of icons."

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		self.asked.append(messages[-1]["content"])
		schema = options["response_format"]["json_schema"]["schema"]["properties"]
		if "choice" in schema:
			return json.dumps({"choice": "describe"})
		raise AssertionError("an unexpected question to the model: " + messages[-1]["content"])


desk = DeskModel()
realRuntime, instance.runtime = instance.runtime, desk
nvdatools.prepareImage = lambda image, size: b"jpeg"
computertools.ocr.recognize = lambda image: []
nvdatools.ocr.recognize = lambda image: []
runner = orchestrator.Orchestrator(desk, registry, lambda question, choices: 0)
runner.facts = instance._clawFacts
del did[:]
task = runner.run(taskModule.Task("first, look at my screen. If you see recycle bin, open it."))
assert task.state == taskModule.DONE, (task.state, task.log[-6:])
assert [(step.tool, step.status) for step in task.steps] == [
	("look", "done"), ("check_seen", "done"), ("find_thing", "done"), ("open_thing", "done"), ("answer", "done")], task.steps
assert did == [("open", "shell:RecycleBinFolder", None)], did
assert task.answer.startswith(
	'The desktop shows a grid of icons. Yes: recycle bin is there: NVDA finds "Recycle Bin" where you are. Opened Recycle Bin.'), task.answer
# One question to the model in all: what to do with "Look at my screen".
assert len(desk.asked) == 1 and "Look at my screen" in desk.asked[0], desk.asked
# And the other: no model is asked anything.
pc["bin"] = (0, 0)
del desk.asked[:]
task = runner.run(taskModule.Task("check and see if my recycle bin needs to be emptied or not."))
assert task.state == taskModule.DONE and not desk.asked, (task.log[-4:], desk.asked)
assert task.answer == "The Recycle Bin is empty. There is nothing to empty.", task.answer
instance.runtime = realRuntime
apiStub.getFocusObject = realFocus
computertools.ocr.recognize = nvdatools.ocr.recognize = realRecognize

# --- An NVDA setting only for the program in front (claw/profiles.py, profiletools.py) ---
# NVDA's configuration is stood in for by one that keeps profiles the way NVDA's own source says it does
# (tests/profilestandin.py). The normal configuration underneath is the one of all the tests above.

import profilestandin  # noqa: E402
from visionClaw import profiletools  # noqa: E402
from visionClaw.claw import profiles  # noqa: E402

configModule = sys.modules["config"]
profiletools.SETTLE_SECONDS = 0
profiled = profilestandin.Manager(conf)
configModule.conf = profiled
stub("NVDAState", shouldWriteToDisk=lambda: profiled.canWrite)
AppTrigger = profilestandin.triggerClass(lambda: configModule.conf)
sys.modules["appModuleHandler"].AppProfileTrigger = AppTrigger
inFront = {"module": None, "title": ""}
focusBefore, foregroundBefore = apiStub.getFocusObject, sys.modules["api"].getForegroundObject
apiStub.getFocusObject = lambda: types.SimpleNamespace(appModule=inFront["module"])
apiStub.getForegroundObject = lambda: types.SimpleNamespace(appModule=inFront["module"], name=inFront["title"])


def bringToFront(module, title):
	profilestandin.switch(AppTrigger, inFront["module"], module)
	inFront["module"], inFront["title"] = module, title


def settingNow(ident):
	return nvdatools._resolveSetting(ident).read()


notepadApp = profilestandin.Module("notepad", "Notepad")
wordApp = profilestandin.Module("winword", "Microsoft Office")
bringToFront(notepadApp, "Untitled - Notepad")
ECHO = "keyboard.speakTypedCharacters"
echoEverywhere = settingNow(ECHO)
other = "off" if echoEverywhere else "on"
instance.changes.pending()
instance.changes._changes = []
conf["visionClaw"]["confirmChanges"] = False
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 0
task = taskModule.Task("test")
# The words that say for which program are no part of what the setting is looked up with: "Word" is in the name
# of another setting.
assert registry.get("find_setting").autoForm("Turn off the typing echo only in Word.")["words"] == "Turn off the typing echo."
SAID = f"turn {other} the typing echo only in this program"
worked, result = registry.call(task, "set_setting", {"setting": ECHO, "value": other, "asked": SAID})
assert worked and result.startswith(
	f"Only in Notepad: Keyboard speak typed characters was {'on' if echoEverywhere else 'off'} and is now {other}. "
	"In other programs it is as it was. NVDA keeps this in a new configuration profile called notepad"), result
# A new profile is always asked about, whatever the settings say, and the question says what will be made.
assert len(questions) == 1 and questions[0].startswith(f"You asked: {SAID}. This is only for Notepad."), questions
assert "There is none for Notepad yet, so VisionClaw will make one." in questions[0], questions
assert profiled.triggersToProfiles == {"app:notepad": "notepad"} and list(profiled.listProfiles()) == ["notepad"]
assert settingNow(ECHO) is (not echoEverywhere)
assert conf["keyboard"]["speakTypedCharacters"] is echoEverywhere  # the normal configuration was not touched
assert profiled.writes[-1] == ("notepad", ECHO, not echoEverywhere), profiled.writes[-1]
# In another program the setting is as it was, and in Notepad it is Notepad's own.
bringToFront(wordApp, "Letter.docx - Word")
assert settingNow(ECHO) is echoEverywhere
bringToFront(notepadApp, "Untitled - Notepad")
assert settingNow(ECHO) is (not echoEverywhere)
# A second setting for the same program: no new profile, so with confirmations off nothing is asked.
levelBefore = settingNow("speech.symbolLevel")
worked, result = registry.call(task, "set_setting", {
	"setting": "speech.symbolLevel", "value": "all", "asked": "When I'm in Notepad, set punctuation to all"})
assert worked and result.startswith("Only in Notepad: Speech symbol level was") and "It is kept in the configuration profile notepad." in result, result
assert len(questions) == 1 and settingNow("speech.symbolLevel") == 300 and conf["speech"]["symbolLevel"] == levelBefore
worked, result = registry.call(task, "list_changes", {})
assert worked and "Speech symbol level, only in Notepad: from" in result and "Keyboard speak typed characters, only in Notepad" in result, result
# With confirmations on, the question says that it is only for this program.
conf["visionClaw"]["confirmChanges"] = True
worked, result = registry.call(task, "set_setting", {
	"setting": "speech.symbolLevel", "value": "none", "asked": "set punctuation to none just in this app"})
assert worked and settingNow("speech.symbolLevel") == 0 and conf["speech"]["symbolLevel"] == levelBefore, result
assert "This is only for Notepad, in the configuration profile NVDA already has for it." in questions[-1], questions[-1]
conf["visionClaw"]["confirmChanges"] = False

# A program that is named and is not the one in front: nothing is changed, nothing is asked, and the user is told.
asked = len(questions)
worked, result = registry.call(task, "set_setting", {
	"setting": "speech.symbolLevel", "value": "all", "asked": "set punctuation to all only in Word"})
assert worked and result == profiles.notHere("Word", "Notepad") and len(questions) == asked, result
assert settingNow("speech.symbolLevel") == 0
# A setting NVDA keeps the same everywhere is not changed for one program.
assert profiletools.baseOnly("general.language") and not profiletools.baseOnly(ECHO)
# Words that narrow the request down, from which no program can be read: the user is told that the change is for
# every program, whatever the settings say; a no changes nothing.
# Notepad has settings of its own by now, so a change that does not say where is asked about: only in Notepad,
# or everywhere? Leaving it changes nothing.
profiletools._profileData = lambda name: profiled._files[name]


def answering(wanted):
	"""A user who picks the choice that begins with these words; for a yes or no question, yes."""
	def ask(question, choices):
		questions.append(question)
		return next((at for at, choice in enumerate(choices) if choice.startswith(wanted)), 0)
	return ask


instance.clawAsk = answering("Nothing")
worked, result = registry.call(task, "set_setting", {
	"setting": "speech.symbolLevel", "value": "all", "asked": "set punctuation to all only in my browser"})
assert worked and result == "You said no, so nothing was changed.", result
assert questions[-1] == (
	"You asked: set punctuation to all only in my browser. Notepad has NVDA settings of its own. Change speech symbol "
	"level from none to all only in Notepad, or everywhere?"), questions[-1]
assert conf["speech"]["symbolLevel"] == levelBefore and settingNow("speech.symbolLevel") == 0
# "Everywhere" chosen: NVDA's normal configuration is changed, Notepad keeps its own value, and that is said.
instance.clawAsk = answering("Everywhere")
worked, result = registry.call(task, "set_setting", {"setting": "speech.symbolLevel", "value": "most", "asked": "set punctuation to most"})
assert worked and result == (
	"Everywhere: Speech symbol level was " + nvdatools._resolveSetting("speech.symbolLevel").shown(levelBefore) + " and is now most. "
	"Notepad has a value of its own for this, none, and keeps it. To change that too, say it again and add: only in "
	"this program."), result
assert conf["speech"]["symbolLevel"] == 200 and settingNow("speech.symbolLevel") == 0 and profiletools.top() == "notepad"
assert profiled.writes[-1] == (None, "speech.symbolLevel", 200), profiled.writes[-1]
# The words say "everywhere": nobody is asked which, and with confirmations off nothing is asked at all.
asked = len(questions)
worked, result = registry.call(task, "set_setting", {
	"setting": "speech.symbolLevel", "value": "some", "asked": "set punctuation to some in every application"})
assert worked and result.startswith("Everywhere: Speech symbol level was most and is now some."), result
assert len(questions) == asked and conf["speech"]["symbolLevel"] == 100 and settingNow("speech.symbolLevel") == 0
# "Only in Notepad" chosen: the same as saying it, without a second question.
instance.clawAsk = answering("Only in")
worked, result = registry.call(task, "set_setting", {"setting": "speech.symbolLevel", "value": "all", "asked": "set punctuation to all"})
assert worked and result.startswith("Only in Notepad: Speech symbol level was none and is now all."), result
assert len(questions) == asked + 1 and settingNow("speech.symbolLevel") == 300 and conf["speech"]["symbolLevel"] == 100
# Undone one after the other, in Notepad: Notepad's own value first, then the two changes made everywhere, each
# put back where it was made.
instance.clawAsk = answering("Yes")
worked, result = registry.call(task, "undo_change", {"what": "undo that"})
assert worked and result == "Speech symbol level in Notepad was all and is back to none, as it was before.", result
worked, result = registry.call(task, "undo_change", {"what": "undo that"})
assert worked and conf["speech"]["symbolLevel"] == 200 and settingNow("speech.symbolLevel") == 0, result
worked, result = registry.call(task, "undo_change", {"what": "undo that"})
assert worked and conf["speech"]["symbolLevel"] == levelBefore and profiletools.top() == "notepad", result
# From a program without settings of its own, a change is made as always, and the answer says that Notepad keeps
# its own value.
bringToFront(wordApp, "Letter.docx - Word")
worked, result = registry.call(task, "set_setting", {"setting": "speech.symbolLevel", "value": "most", "asked": "set punctuation to most"})
assert worked and result.endswith("is now most. Notepad has a value of its own for this and keeps it."), result
worked, result = registry.call(task, "undo_change", {"what": "undo that"})
assert worked and conf["speech"]["symbolLevel"] == levelBefore, result
bringToFront(notepadApp, "Untitled - Notepad")
instance.clawAsk = lambda question, choices: questions.append(question) or 0

# Putting it back. From another program nothing is changed, and the user is told where to say it.
bringToFront(wordApp, "Letter.docx - Word")
worked, result = registry.call(task, "undo_change", {"what": "undo that"})
assert worked and result == profiles.undoElsewhere("speech symbol level", "Notepad"), result
assert len(instance.changes.pending()) == 3
bringToFront(notepadApp, "Untitled - Notepad")
assert settingNow("speech.symbolLevel") == 0
worked, result = registry.call(task, "undo_change", {"what": "undo that"})
assert worked and result == "Speech symbol level in Notepad was none and is back to all, as it was before.", result
assert settingNow("speech.symbolLevel") == 300 and conf["speech"]["symbolLevel"] == levelBefore
worked, result = registry.call(task, "undo_change", {"what": "put the typing echo back"})
assert worked and result.startswith("Keyboard speak typed characters in Notepad was"), result
assert settingNow(ECHO) is echoEverywhere and conf["keyboard"]["speakTypedCharacters"] is echoEverywhere

# Which programs have settings of their own.
worked, result = registry.call(task, "program_settings", {"asked": "which programs have their own settings"})
assert worked and result.startswith("One program has NVDA settings of its own.\nnotepad: its own settings are in the "
	"configuration profile notepad, which is on now."), result
assert "VisionClaw changed there: speech symbol level from" in result, result
assert registry.get("program_settings").tell == "verbatim"
# Taking them away is always asked about; a no leaves everything.
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(task, "remove_program_settings", {"asked": "remove the settings for this program"})
assert worked and result == "You said no, so nothing was changed." and list(profiled.listProfiles()) == ["notepad"], result
assert questions[-1] == profiles.removeQuestion("Notepad", "notepad"), questions[-1]
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(task, "remove_program_settings", {"asked": "remove the settings for this program"})
assert worked and result == profiles.removed("Notepad", "notepad"), result
assert list(profiled.listProfiles()) == [] and profiled.triggersToProfiles == {} and profiletools.top() is None
assert settingNow("speech.symbolLevel") == levelBefore and instance.changes.pending() == []
worked, result = registry.call(task, "remove_program_settings", {"asked": "remove the settings for this program"})
assert worked and result == profiles.noProfile("Notepad"), result
worked, result = registry.call(task, "program_settings", {"asked": "which programs have their own settings"})
assert worked and result.startswith("No program has NVDA settings of its own"), result
# NVDA's own window in front: no program to keep a setting for.
bringToFront(profilestandin.Module("nvda", "NVDA"), "NVDA")
worked, result = registry.call(task, "set_setting", {"setting": ECHO, "value": other, "asked": "turn the typing echo " + other + " only here"})
assert worked and result == profiles.NO_PROGRAM and settingNow(ECHO) is echoEverywhere, result
configModule.conf = conf
apiStub.getFocusObject, apiStub.getForegroundObject = focusBefore, foregroundBefore

# --- A date chosen in a calendar that cannot be worked with the keyboard (claw/dates.py, datetools.py) ---
# The calendars are made up by the test and answer to presses as real ones do (tests/calendarstandin.py).

import datetime as datetimeForTest  # noqa: E402

from calendarstandin import Drawn, Made  # noqa: E402
from visionClaw import datetools, imaging as imagingForDates  # noqa: E402
from visionClaw.claw import dates  # noqa: E402

datetools.SETTLE_SECONDS = datetools.BACK_SECONDS = 0
# "Today" is fixed, so that a date without a year means the same whenever the test runs.


class FixedDate(datetimeForTest.date):
	@classmethod
	def today(cls):
		return cls(2026, 11, 18)


datetools.datetime = types.SimpleNamespace(date=FixedDate)
realPage, realWindowNodes = datetools._page, datetools._windowNodes
datetools._page = lambda: None
conf["visionClaw"]["confirmChanges"] = True
questions = []
instance.clawAsk = lambda question, choices: questions.append((question, list(choices))) or 0
task = taskModule.Task("test")


def calendarNodes(made):
	"""The made-up calendar as NVDA would know a window's controls: each with a name, states, and an action."""
	nodes, byRef = [], {}
	for control in made.controls():
		ref = control["ref"]
		node = {
			"role": "BUTTON", "name": control["label"], "text": "", "value": "", "hidden": False,
			"states": (["UNAVAILABLE"] if control.get("usable") is False else []) + (["SELECTED"] if control.get("marked") else []),
			"obj": types.SimpleNamespace(doAction=lambda ref=ref: made.press(ref)), "up": byRef.get(control.get("inside"))}
		byRef[ref] = node
		nodes.append(node)
	return nodes


# 1. A calendar of controls with names, four months before the date.
made = Made(2026, 11)
datetools._windowNodes = lambda: calendarNodes(made)
SAID_DATE = "Pick the fourteenth of March twenty twenty-seven in this calendar."
worked, result = registry.call(task, "pick_date", {"asked": SAID_DATE})
assert worked and made.chosen == (2027, 3, 14), result
assert result == (
	"Chose Sunday, 14 March 2027 in the calendar, after going 4 months to March 2027. The calendar marks that day as "
	"chosen."), result
assert questions == [(
	"Choose Sunday, 14 March 2027 in the calendar in this window? It shows November 2026. VisionClaw will press the "
	"calendar's own buttons.", ["Yes, do it", "No, leave it"])], questions
assert made.pressed == [("next",)] * 4 + [("day", 2027, 3, 14)], made.pressed
# The user says no: nothing is pressed.
made = Made(2026, 11)
instance.clawAsk = lambda question, choices: 1
worked, result = registry.call(task, "pick_date", {"asked": SAID_DATE})
assert worked and result == "You said no, so nothing was changed." and made.pressed == [], result
instance.clawAsk = lambda question, choices: questions.append((question, list(choices))) or 0
# A calendar that closes when a day is chosen: that is said.
made = Made(2027, 3, closes=True)
worked, result = registry.call(task, "pick_date", {"asked": "choose 14 March 2027 in the date picker"})
assert worked and result == (
	"Chose Sunday, 14 March 2027 in the calendar. The calendar is gone now, as most are once a day is chosen."), result
# A date in numbers that can be read two ways: the user is asked which, and the second is taken here.
made = Made(2027, 3)
del questions[:]
instance.clawAsk = lambda question, choices: questions.append((question, list(choices))) or (1 if "two ways" in question else 0)
worked, result = registry.call(task, "pick_date", {"asked": "set the date to 3/4/2027"})
assert questions[0] == ("That date can be read two ways. Which do you mean?", ["Thursday, 4 March 2027", "Saturday, 3 April 2027"]), questions
assert worked and made.chosen == (2027, 4, 3) and "Chose Saturday, 3 April 2027" in result, result
instance.clawAsk = lambda question, choices: questions.append((question, list(choices))) or 0
# A date without a year is the next one; "today" is the 18th of November 2026 here.
made = Made(2026, 11)
worked, result = registry.call(task, "pick_date", {"asked": "pick tomorrow in this date picker"})
assert worked and made.chosen == (2026, 11, 19), result
# A day that is greyed out, and no date in the words.
made = Made(2027, 3, greyed=[(2027, 3, 14)])
worked, result = registry.call(task, "pick_date", {"asked": SAID_DATE})
assert worked and "greyed out" in result and made.chosen is None, result
worked, result = registry.call(task, "pick_date", {"asked": "pick a date in the calendar"})
assert not worked and "names no date" in result, result

# 2. A calendar that is only drawn: read from the window's picture, and clicked with the mouse, which is put back.
drawn = Drawn(2026, 11, flipped=True)
datetools._windowNodes = lambda: []
BOX = (300, 200, 600, 500)
realPicture = instance.clawScreen.picture
instance.clawScreen.picture = lambda target: ("picture", BOX)
realDateRecognize, realFindIcons, realClick = datetools.ocr.recognize, imagingForDates.findIcons, mousetools.click
datetools.ocr.recognize = lambda image: drawn.picture()[0]
imagingForDates.findIcons = lambda image, textBoxes=(), scale=1.0: drawn.picture()[1]
clicked = []


def clickDrawn(x, y, action="click", move=True):
	clicked.append((x, y))
	drawn.press((x - BOX[0], y - BOX[1]))


mousetools.click = clickDrawn
del moves[:], questions[:]
worked, result = registry.call(task, "pick_date", {"asked": SAID_DATE})
assert worked and drawn.chosen == (2027, 3, 14), (result, drawn.pressed)
assert result == (
	"Chose Sunday, 14 March 2027 in the calendar, after going 6 months to March 2027. The calendar was read from the "
	"window's picture, so check that the date field now says this date: which arrow goes forward was found by trying."), result
assert "in this window, read from its picture" in questions[0][0], questions
# Every click was inside the window, and the mouse is back where it was.
assert all(BOX[0] <= x <= BOX[2] and BOX[1] <= y <= BOX[3] for x, y in clicked) and moves[-1] == mousetools.position(), (clicked, moves)
# With the text in pictures switched off, a drawn calendar is not looked for, and the user is told what to do.
conf["visionClaw"]["useOcr"] = False
worked, result = registry.call(task, "pick_date", {"asked": SAID_DATE})
assert worked and result == dates.NO_CALENDAR, result
conf["visionClaw"]["useOcr"] = True
# A window with text and no calendar.
datetools.ocr.recognize = lambda image: [[{"text": "Hello", "x": 5, "y": 5, "width": 40, "height": 12}]]
worked, result = registry.call(task, "pick_date", {"asked": SAID_DATE})
assert worked and result == dates.NO_CALENDAR, result
datetools.ocr.recognize, imagingForDates.findIcons, mousetools.click = realDateRecognize, realFindIcons, realClick
instance.clawScreen.picture = realPicture
datetools._page, datetools._windowNodes = realPage, realWindowNodes
conf["visionClaw"]["confirmChanges"] = False
assert registry.get("pick_date").changes and planner.RECIPES["pick_date"][2] == ("pick_date",)

# --- Asking by voice: whether it is set up, getting the speech model, deleting it (claw/voice.py, voiceui.py) ---
# No microphone is opened and nothing is downloaded: the download is stood in for.

from visionClaw.claw import voice as voiceWords  # noqa: E402

speech = instance.voice
assert speech.store.folder == os.path.join(DATA, "speech") and not speech.ready() and not speech.listening()
task = taskModule.Task("test")
worked, result = registry.call(task, "voice_info", {"asked": "can I ask you by voice"})
assert worked and result.startswith("Asking by voice is not set up yet: no speech model is on this computer."), result
assert registry.get("voice_info").tell == "verbatim"
assert instance.downloadState()["speech"] is False
worked, result = registry.call(task, "remove_voice", {"asked": "delete the speech model"})
assert worked and result == "No speech model is on this computer, so there is nothing to delete.", result
fetched = []


def fakeSpeechDownload(url, dest, size=None, sha256=None, onProgress=None, cancel=None):
	fetched.append(url)
	for part in range(1, 11):
		if onProgress:
			onProgress(size * part // 10, size)
	with open(dest, "wb") as f:
		f.truncate(size)


realSpeechDownload = voiceWords.net.download
voiceWords.net.download = fakeSpeechDownload
# A download is always asked about, whatever the settings say; a no downloads nothing.
conf["visionClaw"]["confirmChanges"] = False
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(task, "get_voice", {"asked": "download the speech model"})
assert worked and result == "You said no, so nothing was changed." and fetched == [] and not speech.ready(), result
assert questions[0].startswith("Asking by voice needs a speech model on this computer. VisionClaw can download Qwen3-ASR 0.6B")
assert "972 MB" in questions[0] and "huggingface.co/ggml-org/Qwen3-ASR-0.6B-GGUF" in questions[0], questions[0]
instance.clawAsk = lambda question, choices: questions.append(question) or 0
said = []
task = taskModule.Task("download the speech model", lambda task, kind, text: said.append(text) if kind == taskModule.STATE else None)
worked, result = registry.call(task, "get_voice", {"asked": "download the speech model"})
assert worked and result.startswith("The speech model Qwen3-ASR 0.6B is on this computer now. To ask by voice, press NVDA+Alt+V"), result
assert len(fetched) == 2 and all(url.startswith("https://huggingface.co/ggml-org/Qwen3-ASR-0.6B-GGUF/resolve/") for url in fetched)
# How far it is, is said every ten percent, and not more often.
assert said[0] == "Downloading the speech model: 0 percent." and 5 <= len(said) <= 11 and len(set(said)) == len(said), said
assert speech.ready() and instance.downloadState()["speech"] is True
worked, result = registry.call(task, "voice_info", {"asked": "is voice input set up"})
assert worked and result.startswith("Asking by voice is ready. VisionClaw listens with the speech model Qwen3-ASR 0.6B"), result
# Asked for again: nothing is downloaded twice.
del fetched[:]
worked, result = registry.call(task, "get_voice", {"asked": "download the speech model"})
assert worked and fetched == [] and result.startswith("Asking by voice is ready."), result
# The user chose the larger one, which is not here: the one that is here is listened with.
conf["visionClaw"]["speechModel"] = "qwen3-asr-1.7b"
assert speech.ears.model()["id"] == "qwen3-asr-0.6b" and speech.wanted()["id"] == "qwen3-asr-1.7b"
conf["visionClaw"]["speechModel"] = ""
# Deleting it is always asked about.
del questions[:]
worked, result = registry.call(task, "remove_voice", {"asked": "delete the speech model"})
assert worked and result == "Deleted the speech model Qwen3-ASR 0.6B. That freed 972 MB.", result
assert questions == [
	"Delete the speech model Qwen3-ASR 0.6B from this computer, 972 MB? Asking by voice then needs it downloaded again."], questions
assert not speech.ready() and not os.path.exists(os.path.join(DATA, "speech", "qwen3-asr-0.6b"))
voiceWords.net.download = realSpeechDownload
# The whole of VisionClaw's data is carried by a portable copy; the speech model's folder is inside it.
assert os.path.commonpath([speech.store.folder, DATA]) == DATA
assert "speechModel" in instance.portableSettings()

# --- Working through a task, VisionClaw's own windows off limits, and a voice of its own ---

from visionClaw import guidetools, ownvoice, pagetools as pagetoolsForGuide  # noqa: E402
from visionClaw.claw import guide  # noqa: E402

guidetools.SETTLE_SECONDS = 0
realWhere, realInFront, realThings, realPress = (
	pagetoolsForGuide._where, guidetools.inFront, guidetools._windowThings, guidetools._pressObject)
pagetoolsForGuide._where = lambda: None
front = {"program": "winword", "title": "Letter.docx - Word", "things": [
	guide.Thing("File", "menu item", ("window", "File"), "Alt+F"), guide.Thing("Home", "tab", ("window", "Home")),
	guide.Thing("Print", "button", ("window", "Print"), "Control+P"), guide.Thing("Bold", "button", ("window", "Bold"))]}
pressedThings = []


def pressThing(name):
	pressedThings.append(name)
	if name == "Print":
		front["title"] = "Print"
		front["things"] = [guide.Thing("Printer", "combo box", ("window", "Printer")), guide.Thing("Cancel", "button", ("window", "Cancel"))]


guidetools.inFront = lambda: (front["program"], front["title"])
guidetools._windowThings = lambda: list(front["things"])
guidetools._pressObject = pressThing
task = taskModule.Task("test")
asked = []
instance.clawAsk = lambda question, choices: asked.append((question, list(choices))) or 0
worked, result = registry.call(task, "work_through", {"asked": "I'm stuck, I want to print this letter"})
# Print is plain code's own choice; the window that opens has a Printer box, which is about printing too, and
# is offered next. Each was asked about before it was pressed.
assert worked and pressedThings == ["Print", "Printer"], (result, pressedThings)
assert len(asked) == 2 and asked[1][0].startswith("Step 2: Printer combo box looks like the way to print this letter."), asked
assert asked[0] == (
	"Step 1: Print button looks like the way to print this letter. Its key is Control+P. Press it for you?",
	["Yes, press it", "No, only tell me where it is", "Stop here"]), asked[0]
assert result.startswith("Step 1: pressed Print button. The window in front is now Print. New here: Printer combo box, Cancel button."), result
assert "VisionClaw finds nothing here that is about this: print this letter." in result, result
# Only told: nothing is pressed.
front["title"], front["things"] = "Letter.docx - Word", [guide.Thing("Print", "button", ("window", "Print"), "Control+P")]
del pressedThings[:]
instance.clawAsk = lambda question, choices: 1
worked, result = registry.call(task, "work_through", {"asked": "walk me through printing this"})
assert worked and pressedThings == [] and result == "The next step is Print button: its key is Control+P.", result
# No task named.
worked, result = registry.call(task, "work_through", {"asked": "I'm stuck"})
assert worked and result == guide.NO_GOAL
# VisionClaw's own windows are off limits: nothing that works the window in front is used on them.
front["program"], front["title"] = "nvda", "Ask VisionClaw"
for name, form in (
		("work_through", {"asked": "I'm stuck, I want to print this letter"}), ("type_text", {"text": "hello"}),
		("press_keys", {"keys": "enter"}), ("click_item", {"item": "Send", "action": "click", "asked": ""}),
		("pick_date", {"asked": "pick 14 March 2027 in this calendar"})):
	worked, result = registry.call(task, name, form)
	assert worked and result == guide.NOT_OWN, (name, result)
assert pressedThings == [] and "hello" not in typed
# NVDA's own windows, such as its settings, are not VisionClaw's.
front["title"] = "NVDA Settings: Speech (normal configuration)"
assert guidetools.ownWindow() is False
front["program"], front["title"] = "winword", "Letter.docx - Word"
assert guidetools.ownWindow() is False
pagetoolsForGuide._where, guidetools.inFront, guidetools._windowThings, guidetools._pressObject = (
	realWhere, realInFront, realThings, realPress)

# A voice of its own, set in NVDA's Speech settings: one configuration profile, used only for what VisionClaw says.
configModule.conf = profiled
spoken, uiSaid, openedSettings = [], [], []
realSpeak, realUiMessage, realMainFrame = sys.modules["speech"].speak, sys.modules["ui"].message, sys.modules["gui"].mainFrame
sys.modules["speech"].speak = spoken.append
sys.modules["ui"].message = uiSaid.append
stub("speech.commands", ConfigProfileTriggerCommand=lambda trigger, enter=True: ("voice of its own", trigger.spec, enter))
sys.modules["gui"].mainFrame = types.SimpleNamespace(
	popupSettingsDialog=lambda *panels: openedSettings.append(panels), prePopup=lambda: None, postPopup=lambda: None)
conf["visionClaw"]["ownVoice"] = True
assert ownvoice.profileName() == "" and ownvoice.check() == ""
# No voice set yet: VisionClaw speaks exactly as NVDA does.
ownvoice.say("Hello", True)
assert uiSaid == ["Hello"] and spoken == []
worked, result = registry.call(task, "own_voice", {"asked": "is your own voice on?"})
assert worked and result.startswith("VisionClaw speaks with NVDA's own voice now.") and "customise VisionClaw's voice" in result, result
# Customising is always asked about; a no makes nothing.
conf["visionClaw"]["confirmChanges"] = False
questions = []
instance.clawAsk = lambda question, choices: questions.append(question) or 1
worked, result = registry.call(task, "own_voice", {"asked": "customise VisionClaw's voice"})
assert worked and result == "You said no, so nothing was changed." and list(profiled.listProfiles()) == [] and openedSettings == []
assert "NVDA's Speech settings will open" in questions[0] and "VisionClaw voice" in questions[0], questions[0]
# A yes: the profile is made, tied to VisionClaw's own trigger, turned on by hand, and NVDA's Speech settings open.
instance.clawAsk = lambda question, choices: questions.append(question) or 0
worked, result = registry.call(task, "own_voice", {"asked": "customise VisionClaw's voice"})
assert worked and result == ownvoice.OPENED, result
assert list(profiled.listProfiles()) == ["VisionClaw voice"] and profiled.triggersToProfiles == {ownvoice.SPEC: "VisionClaw voice"}
assert ownvoice._byHand() == "VisionClaw voice" and len(openedSettings) == 1 and len(openedSettings[0]) == 2
# What is chosen in that window goes into that profile, and nowhere else: here, as the settings window would write it.
profiled["speech"]["symbolLevel"] = 0
assert profiled.writes[-1] == ("VisionClaw voice", "speech.symbolLevel", 0) and conf["speech"]["symbolLevel"] != 0
# The window is closed: the profile is turned off again, the user's own voice is back, and that is said.
ownvoice._watch("VisionClaw voice", uiSaid.append)
assert ownvoice._byHand() == "" and profiletools.top() is None and uiSaid[-1] == ownvoice.CLOSED
# From now on VisionClaw's words carry its own trigger, and NVDA applies the profile to them alone.
ownvoice.say("Finished.", True)
assert spoken[-1] == [("voice of its own", ownvoice.SPEC, True), "Finished."], spoken[-1]
# It is no program's own settings, and is not listed among them.
worked, result = registry.call(task, "program_settings", {"asked": "which programs have their own settings"})
assert worked and result.startswith("No program has NVDA settings of its own"), result
# Turned off in words: VisionClaw speaks as NVDA does, and the profile stays for later.
worked, result = registry.call(task, "own_voice", {"asked": "turn off your own voice"})
assert worked and "it is turned off" in result and conf["visionClaw"]["ownVoice"] is False, result
before = len(spoken)
ownvoice.say("Plain.", conf["visionClaw"]["ownVoice"])
assert len(spoken) == before and uiSaid[-1] == "Plain."
worked, result = registry.call(task, "own_voice", {"asked": "turn VisionClaw's own voice on"})
assert worked and conf["visionClaw"]["ownVoice"] is True and result.startswith("VisionClaw speaks with a voice of its own"), result
# While NVDA's settings window is open, or another profile is on by hand, it is not begun.
profiled.createProfile("quiet")
profiled.manualActivateProfile("quiet")
assert "The configuration profile quiet is turned on by hand." in ownvoice.check()
profiled.manualActivateProfile(None)
profiled.deleteProfile("quiet")
# Removed after a question.
worked, result = registry.call(task, "own_voice", {"asked": "remove VisionClaw's voice"})
assert worked and result == "The configuration profile VisionClaw voice was deleted. VisionClaw speaks with NVDA's own voice again.", result
assert list(profiled.listProfiles()) == [] and profiled.triggersToProfiles == {} and ownvoice.profileName() == ""
for said, wish in {
		"customise VisionClaw's voice": ownvoice.CUSTOMISE, "change your voice": ownvoice.CUSTOMISE, "give yourself a different voice": ownvoice.CUSTOMISE,
		"turn off your own voice": False, "turn VisionClaw's own voice on": True, "remove VisionClaw's voice": ownvoice.REMOVE,
		"is your own voice on?": None, "do you have a voice of your own": None}.items():
	assert ownvoice.wish(said) == wish, (said, ownvoice.wish(said))
sys.modules["speech"].speak, sys.modules["ui"].message, sys.modules["gui"].mainFrame = realSpeak, realUiMessage, realMainFrame
configModule.conf = conf

# --- Status updates while VisionClaw takes long (claw/busy.py), with the real plugin ---
from visionClaw import clawui  # noqa: E402
from visionClaw.claw import busy  # noqa: E402

assert plugin.conf()["statusUpdates"] == busy.SUGGESTED == "15" and instance.board.every() == 15
plugin.conf()["statusUpdates"] = "off"
assert instance.board.every() == 0
plugin.conf()["statusUpdates"] = "30"
assert instance.board.every() == 30
plugin.conf()["statusUpdates"] = busy.SUGGESTED
assert clawui.board is instance.board and len(clawui.statusLabels()) == len(busy.CHOICES)
statusSaid = []
sys.modules["ui"].message = statusSaid.append
# Nothing running: NVDA+Alt+P and NVDA+Alt+X say so, as before.
instance.clawTask = None
instance.script_clawProgress(None)
instance.script_clawStop(None)
assert statusSaid == [
	"VisionClaw is not working on anything. Press NVDA+Alt+C to ask for something.",
	"VisionClaw is not working on anything."], statusSaid
# A description on its way: NVDA+Alt+P says how far it is, and NVDA+Alt+X stops it.
stopDescribing = threading.Event()
describing = instance.board.begin(
	"describing the screen", instance._seeing("The {model} is looking at the picture."), cancel=stopDescribing)
instance.script_clawProgress(None)
assert statusSaid[-1].startswith("Describing the screen, 0 seconds so far.") and statusSaid[-1].endswith((
	"The vision model is looking at the picture.", "Starting the vision model.")), statusSaid[-1]
instance.script_clawStop(None)
assert stopDescribing.is_set() and statusSaid[-1] == "Stopping."
instance.board.end(describing)
# A question to the user: no update meanwhile.
assert clawui._fromWorker(lambda: instance.board.isAsking) is True and not instance.board.isAsking
# The icons of the overlay: counted as queued and done, ended when all are done or the overlay closes.
instance._iconsCounted(added=3)
instance.script_clawProgress(None)
assert statusSaid[-1] == "Naming the icons in the overlay, 0 seconds so far. 0 of 3 icons done so far.", statusSaid[-1]
instance._iconsCounted(done=2)
assert "2 of 3 icons done so far." in instance.board.progressText()
instance._iconsCounted(done=1)
assert instance._iconStatus is None and instance.board.running() == []
instance._iconsCounted(added=2)
instance._iconsCounted(dropped=True)
assert instance._iconStatus is None and instance.board.running() == []
instance._iconsCounted(done=1)  # a batch that ends after the overlay closed changes nothing
assert instance._iconStatus is None
sys.modules["ui"].message = realUiMessage

# Answers spoken a sentence at a time while the model writes them (claw/orchestrator.py), the setting streamAnswers:
# on by default and handed to the orchestrator; the first piece plays the sound of a finished request, ends the status
# updates and arms the stop on NVDA's speech being silenced; after Control nothing more is spoken; the whole answer
# that follows is not spoken again, and the Ask window's record has it once. Turned off, everything is said whole.
assert conf["visionClaw"]["streamAnswers"] is True
assert instance.orchestrator.streaming() is True and plugin._whole() is False
conf["visionClaw"]["streamAnswers"] = False
assert instance.orchestrator.streaming() is False and plugin._whole() is True
conf["visionClaw"]["streamAnswers"] = True
piecesSaid, soundsPlayed, hushed = [], [], []
realSpeak, realSound = plugin._speak, plugin._sound
plugin._speak, plugin._sound = piecesSaid.append, soundsPlayed.append
streamTask = taskModule.Task("how do I read the title of this window")
streamTask.statusJob = types.SimpleNamespace(hush=lambda: hushed.append(True), heardNow=lambda: None)
instance._onClawEvent(streamTask, taskModule.SAY, "The key is NVDA+t.")
assert piecesSaid == ["The key is NVDA+t."] and soundsPlayed == ["done"] and hushed == [True], (piecesSaid, soundsPlayed)
assert instance._speakingCancel is streamTask.quiet and not streamTask.quiet.is_set()
instance._onClawEvent(streamTask, taskModule.SAY, "Press it twice to have the title spelled.")
assert piecesSaid[-1] == "Press it twice to have the title spelled." and soundsPlayed == ["done"] and hushed == [True]
instance._onSpeechCanceled()  # Control, or anything else that silences NVDA
instance._onClawEvent(streamTask, taskModule.SAY, "A sentence after Control.")
assert len(piecesSaid) == 2, piecesSaid
streamTask.streamed = True
whole = "The key is NVDA+t. Press it twice to have the title spelled. A sentence after Control."
instance._onClawEvent(streamTask, taskModule.ANSWER, whole)
assert len(piecesSaid) == 2 and soundsPlayed == ["done"], (piecesSaid, soundsPlayed)
streamTask.log = [(0, taskModule.SAY, "The key is NVDA+t."), (1, taskModule.ANSWER, whole)]
assert clawui.logText(streamTask).count("The key is NVDA+t.") == 1, clawui.logText(streamTask)
streamTask.state, streamTask.answer = taskModule.DONE, whole
assert clawui.progressText(streamTask).endswith(whole)  # NVDA+Alt+P says the whole answer once it has finished
instance._speakingCancel = None
wholeTask = taskModule.Task("what is on the screen")
instance._onClawEvent(wholeTask, taskModule.ANSWER, "The screen shows a game menu.")
assert piecesSaid[-1] == "The screen shows a game menu." and soundsPlayed == ["done", "done"]
plugin._speak, plugin._sound = realSpeak, realSound

# --- Scratchpads (scratchtools.py, claw/scratchpad.py) ---

from visionClaw import diagnosetools, scratchtools  # noqa: E402
from visionClaw.claw import diagnose as diagModule, lookup as lookupModule, scratchpad as padModule  # noqa: E402

# In the data folder inside the add-on: a portable copy carries them, as it carries the logs.
assert instance.pads.folder == os.path.join(DATA, "scratchpads") and instance.orchestrator.pads is instance.pads
assert conf["visionClaw"]["scratchpads"] is True and instance.orchestrator.learning() is True
realFocusObject = sys.modules["api"].getFocusObject
reaper = types.SimpleNamespace(appName="reaper", productName="REAPER")
sys.modules["api"].getFocusObject = lambda: types.SimpleNamespace(
	treeInterceptor=types.SimpleNamespace(documentConstantIdentifier="https://www.bbc.co.uk/news"), appModule=reaper)
assert scratchtools.subjectNow() == "bbc.co.uk"
sys.modules["api"].getFocusObject = lambda: types.SimpleNamespace(treeInterceptor=None, appModule=reaper)
assert scratchtools.subjectNow() == "REAPER" and instance.orchestrator.subject() == "REAPER"
padQuestions = []
realClawAsk = instance.clawAsk
instance.clawAsk = lambda question, choices: padQuestions.append(question) or 0
padTask = taskModule.Task("a scratchpad")


def onPad(asked):
	worked, result = registry.call(padTask, "scratchpad", {"asked": asked})
	assert worked, result
	return result


said = onPad("start a scratchpad for mixing my song: record the vocals, set the levels, then export it")
assert said.startswith("Started the task scratchpad mixing my song. 3 things to do: 1, record the vocals; 2, set the levels; "
	"3, export it."), said
assert os.path.isfile(os.path.join(DATA, "scratchpads", "tasks", "mixing-my-song.md")) and padModule.hasTask()
assert onPad("write on the scratchpad that the vocals are on track 2") == (
	"Written on your task scratchpad mixing my song: the vocals are on track 2")
assert onPad("check off step 1") == "Checked off 1, record the vocals. Next: 2, set the levels."
assert onPad("what's next") == "Next on mixing my song: 2, set the levels. 2 of 3 things are still to do."
assert onPad("add normalise the track to the to-do list on my scratchpad").startswith("Added to mixing my song: normalise the track.")
assert onPad("read my scratchpad").startswith("Your task scratchpad: mixing my song.\nTo do: 1, record the vocals, done;")
worked, result = registry.call(padTask, "scratchpad_search", {"asked": "what did you write on the scratchpad about the vocals"})
assert worked and result.startswith("From your task scratchpad mixing my song: the vocals are on track 2"), result
assert registry.get("scratchpad_search").tell == "summarize" and registry.get("scratchpad").tell == "verbatim"
worked, result = registry.call(padTask, "scratchpad_search", {"asked": "is there anything on my scratchpad about the weather"})
assert worked and lookupModule.isNothing(result), result
# Words that ask nothing of a scratchpad are refused, with a sentence for the model in general words.
worked, result = registry.call(padTask, "scratchpad", {"asked": "turn off typing echo"})
assert not worked and "Name the scratchpad" in result and "for example" not in result
# A description is kept on the descriptions scratchpad, and a question that points back at it is answered from there.
scratchtools.describeOn(instance, "the screen", "A bar chart of sales by month; March is the highest.")
worked, result = registry.call(padTask, "scratchpad_search", {"asked": "which month was highest in the chart you described"})
assert worked and "Described the screen: A bar chart of sales by month; March is the highest." in result, result
conf["visionClaw"]["scratchpads"] = False
scratchtools.describeOn(instance, "the picture", "Not kept.")
assert all("Not kept" not in text for _w, _what, text, _p, _a in instance.pads.descriptions().descriptions)
assert instance.orchestrator.learning() is False
conf["visionClaw"]["scratchpads"] = True
# What was learned in the program in front: written by the user in words, and found by look_up as a passage.
assert onPad("write on the scratchpad for this program that the mixer opens with Control+M") == (
	"Written on the scratchpad for REAPER: the mixer opens with Control+M")
found = scratchtools.passages(instance, "how do I open the mixer", "REAPER")
assert found and found[0].source == lookupModule.PAD and found[0].text == "the mixer opens with Control+M", found
assert found[0].line().startswith("From the scratchpad of what was learned in REAPER: the mixer opens with Control+M")
# The descriptions only where the question points back at one.
assert all("Described" not in passage.text for passage in scratchtools.passages(instance, "which month was highest", "REAPER"))
opened = []
realOpenFile, scratchtools.openFile = scratchtools.openFile, opened.append
assert onPad("open my scratchpad") == "Opened the scratchpad in your program for text files."
assert opened[-1].endswith(os.path.join("tasks", "mixing-my-song.md")), opened
scratchtools.openFile = realOpenFile
assert onPad("close the scratchpad").startswith("The task scratchpad mixing my song is finished.") and not padModule.hasTask()
assert onPad("which scratchpads do I have").startswith("3 scratchpads:")
assert onPad("delete all scratchpads") == "Deleted 3 scratchpads."
assert padQuestions[-1] == "Delete 3 scratchpads for good? They cannot be brought back.", padQuestions

# --- VisionClaw's own logs and code, only when the user asks (diagnosetools.py, claw/diagnose.py) ---

logsDir = tempfile.mkdtemp()
realLogsFolder, diagnosetools.logsFolder = diagnosetools.logsFolder, lambda plugin: logsDir
slugLine = __import__("inspect").getsourcelines(padModule.slug)[1] + 2
slugPath = os.path.join(diagnosetools.ROOT, "claw", "scratchpad.py")
with open(os.path.join(logsDir, "visionclaw.log"), "w", encoding="utf-8") as f:
	f.write(
		"2026-11-19 12:00:00.000 [visionClaw-task] task: New request: 'start a scratchpad for my taxes'. Reasoning setting: auto.\n"
		"2026-11-19 12:00:01.000 [visionClaw-task] scratchpad: ERROR: A scratchpad's file name could not be made\n"
		f"\tTraceback (most recent call last):\n\t  File \"{slugPath}\", line {slugLine}, in slug\n\tTypeError: the name is too long\n"
		"2026-11-19 12:00:02.000 [visionClaw-task] task: Request ended as failed after 2.0 seconds. Steps: []. Answer: ''\n")
CORRECTED_SLUG = (
	'def slug(name):\n\t"""A file name made of a program\'s or a task\'s name."""\n'
	'\tmade = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")\n\treturn (made or "scratchpad")[:40]\n')
assert diagModule.checkFix(open(slugPath, encoding="utf-8").read(), diagModule.functionAt(open(slugPath, encoding="utf-8").read(), slugLine), CORRECTED_SLUG) == []


class SelfRuntime(FakeRuntime):
	"""The model that writes code says what went wrong and corrects the function; the model that sees reads it."""
	asked = []

	def oneModel(self):
		return False

	def chat(self, role, messages, maxTokens, **options):
		system, user = messages[0]["content"], messages[1]["content"]
		self.asked.append((role, system[:60], user))
		if system.startswith("You are VisionClaw, an assistant inside the NVDA screen reader. You read an error"):
			return "The function slug was given a name it could not turn into a file name, so the scratchpad was not made."
		if system.startswith("You correct one function of VisionClaw"):
			return "```python\n" + CORRECTED_SLUG + "```"
		if "You check a correction of one function" in system:
			return json.dumps({"fixes": True, "problem": ""})
		return super().chat(role, messages, maxTokens, **options)


realRuntime, instance.runtime = instance.runtime, SelfRuntime()
selfTask = taskModule.Task("a question about VisionClaw itself")
# Nothing is read and nothing is corrected without words that ask for it.
worked, result = registry.call(selfTask, "own_errors", {"asked": "what time is it"})
assert worked and result == "VisionClaw reads its own log only when you ask for exactly that, so nothing was read."
worked, result = registry.call(selfTask, "fix_self", {"asked": "what errors are in your log"})
assert worked and result == "VisionClaw corrects its own code only when you ask for exactly that, so nothing was changed."
assert SelfRuntime.asked == []
worked, result = registry.call(selfTask, "own_errors", {"asked": "what errors are in your log"})
assert worked and result.startswith("VisionClaw's log has one error.\n1. A scratchpad's file name could not be made.") and (
	"the function slug in the file claw/scratchpad.py" in result), result
assert SelfRuntime.asked == []  # listing them asks no model
worked, result = registry.call(selfTask, "own_errors", {"asked": "why did my last request fail"})
assert worked and result.startswith("Your last request, \"start a scratchpad for my taxes\", ended as failed after 2.0 seconds."), result
assert result.endswith("What the coder model says went wrong, which may be wrong: The function slug was given a name it could "
	"not turn into a file name, so the scratchpad was not made."), result
assert SelfRuntime.asked[-1][0] == CODER and "def slug(name):" in SelfRuntime.asked[-1][2]
# The correction: written by the model that writes code, read by the model that sees, always asked about, put in place at
# once, and VisionClaw's own file is not changed.
before = open(slugPath, encoding="utf-8").read()
padQuestions.clear()
worked, result = registry.call(selfTask, "fix_self", {"asked": "fix that bug in your code"})
assert worked and result.startswith("VisionClaw's function slug is corrected, and the correction is used from now on"), result
assert padQuestions and padQuestions[0].startswith("VisionClaw found this error: A scratchpad's file name could not be made."), padQuestions
assert "That is a check, not a guarantee." in padQuestions[0] and "The vision model read it and found no problem." in padQuestions[0]
assert [role for role, _s, _u in SelfRuntime.asked[-2:]] == [CODER, VISION]
assert padModule.slug("a" * 70) == "a" * 40 and open(slugPath, encoding="utf-8").read() == before
pending = instance.changes.pending()[0]
assert pending["setting"].startswith("ownfix:fix-") and pending["label"] == "VisionClaw's correction of its function slug"
assert os.path.isfile(os.path.join(DATA, "ownfixes", "fixes.json")) and any(
	name.endswith("-slug.md") for name in os.listdir(os.path.join(DATA, "ownfixes")))
worked, result = registry.call(selfTask, "own_fixes", {"asked": "which fixes did you make to your own code"})
assert worked and result.startswith("1 corrections of VisionClaw's own code:\n1. slug in the file claw/scratchpad.py") and "It is in use." in result, result
# The user said no: nothing is changed.
instance.clawAsk = lambda question, choices: 1
worked, result = registry.call(selfTask, "fix_self", {"asked": "fix that bug in your code"})
assert worked and result == "You said no, so nothing was changed." and padModule.slug("a" * 70) == "a" * 40
instance.clawAsk = lambda question, choices: padQuestions.append(question) or 0
# "Undo that" puts the function back as it was written.
worked, result = registry.call(selfTask, "undo_change", {"what": "undo that"})
assert worked and result == "VisionClaw's correction of slug is undone; the function works as it was written again.", result
assert padModule.slug("a" * 70) == "a" * 60 and all(c["setting"] != pending["setting"] for c in instance.changes.pending())
worked, result = registry.call(selfTask, "own_fixes", {"asked": "undo the fix you made to your code"})
assert worked and result == "No correction of VisionClaw's own code is in use, so there is nothing to undo.", result
instance.runtime = realRuntime
diagnosetools.logsFolder = realLogsFolder
shutil.rmtree(logsDir, ignore_errors=True)
sys.modules["api"].getFocusObject = realFocusObject
instance.clawAsk = realClawAsk

# --- NVDA's own log, only when the user asks (nvdalogtools.py, claw/nvdalog.py) ---
# A made-up nvda.log and nvda-old.log in a folder of the test's own: the real log of this computer is never read.

from visionClaw import nvdalogtools  # noqa: E402
from visionClaw.claw import nvdalog as logModule  # noqa: E402

nvdaLogDir = tempfile.mkdtemp()
nvdaLogPath = os.path.join(nvdaLogDir, "nvda.log")
ADDON_DIR_CLOCK = os.path.join(nvdaLogDir, "addons", "clock")
os.makedirs(os.path.join(ADDON_DIR_CLOCK, "globalPlugins", "clock"))
SECRET = ("hunter2", "kb(desktop):p", "Speaking")


def entryText(level, clock, message, codepath="core.main"):
	return f"{level} - {codepath} ({clock}) - MainThread (1000):\n{message}\n"


with open(nvdaLogPath, "w", encoding="utf-8") as f:
	f.write(entryText("INFO", "09:00:00.100", "Starting NVDA version 2026.3.1 AMD64", "__main__")
		+ entryText("INFO", "09:00:01.000", "Windows version: Windows 11 24H2")
		+ entryText("INFO", "09:00:03.000", "NVDA initialized")
		+ entryText("IO", "09:01:00.000", "Input: kb(desktop):p", "inputCore.InputManager.executeGesture")
		+ entryText("IO", "09:01:00.100", "Speaking ['hunter2']", "speech.speech.speak")
		+ entryText("ERROR", "09:02:00.000", "Error in script_sayTime\nTraceback (most recent call last):\n"
			f"  File \"{os.path.join(ADDON_DIR_CLOCK, 'globalPlugins', 'clock', '__init__.py')}\", line 60, in speakTime\n"
			"ValueError: invalid literal for int() with base 10: 'ten'", "external:globalPlugins.clock.GlobalPlugin.script_sayTime")
		+ entryText("INFO", "09:06:00.000", "Starting freeze recovery after 10.5 seconds.", "watchdog.waitForFreezeRecovery")
		+ entryText("INFO", "09:06:30.000", "Recovered from freeze after 40.2 seconds.", "watchdog.waitForFreezeRecovery")
		+ entryText("INFO", "09:07:00.000", "Developer info for navigator object:\nname: 'Save'\nrole: BUTTON\nstates: FOCUSABLE\n"
			"appModule: AppModule(appModules.notepad, appName='notepad', processID=4242)\nwindowClassName: 'Button'\n"
			"UIA automationID: SaveButton\nUIA frameworkID: Win32", "globalCommands.GlobalCommands.script_navigatorObject_devInfo")
		+ entryText("INFO", "09:08:00.000", "Input help: gesture kb(desktop):NVDA+shift+v, bound to script sayDate on "
			"globalPlugins.clock.GlobalPlugin", "inputCore.InputManager._handleInputHelp")
		+ entryText("INFO", "09:09:00.000", "Base configuration saved", "config.ConfigManager.save")
		+ entryText("INFO", "09:10:00.000", "Successfully connected as leader", "_remoteClient.client.RemoteClient.onConnectedAsLeader"))
with open(os.path.join(nvdaLogDir, "nvda-old.log"), "w", encoding="utf-8") as f:
	f.write(entryText("INFO", "22:00:00.000", "Starting NVDA version 2026.3.1 AMD64", "__main__")
		+ entryText("INFO", "22:00:01.000", "Windows version: Windows 11 24H2")
		+ entryText("INFO", "22:00:02.000", "NVDA initialized")
		+ entryText("CRITICAL", "23:59:59.500", "NVDA crashed! Minidump written to C:\\Temp\\nvda_crash.dmp", "watchdog._crashHandler")
		+ entryText("INFO", "23:59:59.600", "Restarting due to crash", "watchdog._crashHandler"))
logHandlerModule, globalVarsModule = sys.modules["logHandler"], sys.modules["globalVars"]


class FakeFileHandler:
	pass


nvdaLevel = {"level": 100, "forced": False}
realLogStandIn = logHandlerModule.log
logHandlerModule.log = types.SimpleNamespace(getEffectiveLevel=lambda: nvdaLevel["level"])
logHandlerModule.isLogLevelForced = lambda: nvdaLevel["forced"]
logHandlerModule.FileHandler = FakeFileHandler
logHandlerModule.logHandler = FakeFileHandler()
logHandlerModule._getDefaultLogFilePath = lambda: nvdaLogPath
globalVarsModule.appArgs.logFileName = nvdaLogPath
hadGeneral = "general" in conf
conf["general"] = {"loggingLevel": "OFF"}
realAvailable = sys.modules["addonHandler"].getAvailableAddons
sys.modules["addonHandler"].getAvailableAddons = lambda: [
	types.SimpleNamespace(name="clock", manifest={"summary": "Clock and Calendar"}, path=ADDON_DIR_CLOCK)]
panels, logQuestions = [], []
realMainFrame = sys.modules["gui"].mainFrame
sys.modules["gui"].mainFrame = types.SimpleNamespace(popupSettingsDialog=lambda *args: panels.append(args))
instance.clawAsk = lambda question, choices: logQuestions.append((question, choices)) or 0
realLast, instance.orchestrator.last = instance.orchestrator.last, None


class LogRuntime(FakeRuntime):
	"""The model that writes code says what one error means."""
	asked = []

	def oneModel(self):
		return False

	def chat(self, role, messages, maxTokens, **options):
		system, user = messages[0]["content"], messages[1]["content"]
		self.asked.append((role, system, user))
		if system.startswith("You are VisionClaw, an assistant inside the NVDA screen reader. You read one error from NVDA's own log"):
			return "The clock add-on could not turn the word ten into a number, so it could not say the time."
		return super().chat(role, messages, maxTokens, **options)


realRuntime, instance.runtime = instance.runtime, LogRuntime()
logTask = taskModule.Task("a question about NVDA's log")


def onLog(asked):
	worked, result = registry.call(taskModule.Task(asked), "nvda_log", {"asked": asked})
	assert worked, result
	for word in SECRET:
		assert word not in result, (word, result)
	return result


assert registry.get("nvda_log").looks and not registry.get("nvda_log").changes and registry.get("nvda_log").tell == "verbatim"
# Nothing is read without words that ask for it.
assert onLog("what time is it") == "VisionClaw reads NVDA's log only when you ask for exactly that, so nothing was read."
# The level is Disabled: said, where it is turned on, and the offer to open that page; a yes opens it and changes nothing.
said = onLog("check NVDA's log")
question, choices = logQuestions[-1]
assert question.startswith("NVDA's log is off: its logging level is Disabled") and question.endswith(
	"Open NVDA's Privacy and Security settings now, at the Logging level combo box?") and choices == ["Yes, open them", "No, leave them"]
assert said.startswith("NVDA's settings are open at Privacy and Security.") and len(panels) == 1
assert [getattr(part, "__name__", str(part)) for part in panels[0]][1] == "PrivacyAndSecuritySettingsPanel"
assert conf["general"]["loggingLevel"] == "OFF"  # VisionClaw never changes it
instance.clawAsk = lambda question, choices: logQuestions.append((question, choices)) or 1
assert onLog("why does nvda keep freezing") == "NVDA's settings were not opened, and nothing was changed." and len(panels) == 1
# Secure mode: said, and nothing offered.
globalVarsModule.appArgs.secure, asked = True, len(logQuestions)
assert onLog("check NVDA's log").startswith("NVDA runs in secure mode") and len(logQuestions) == asked
globalVarsModule.appArgs.secure = False
# The level is Info: the log is read, and the add-on is named from the running NVDA.
nvdaLevel["level"], conf["general"]["loggingLevel"] = 20, "INFO"
said = onLog("check NVDA's log")
assert said.startswith("NVDA's log of this run has one error.\nOf the 1 errors, 1 from Clock and Calendar (clock).\n1. Error in "
	"script_sayTime. Once, at 09:02:00. From the add-on Clock and Calendar (clock), in its function speakTime."), said
assert "2 entries of the levels that hold what you type" in said
said = onLog("which add-on is causing errors")
assert said.startswith("Errors in NVDA's log of this run that come from add-ons, the most first:\n1. Clock and Calendar (clock): 1 error.")
# The run before crashed in no add-on's code, so nothing of it is said here.
assert "In the run before" not in said, said
assert onLog("did nvda freeze").startswith("NVDA's log of this run shows one time that NVDA stopped responding.")
said = onLog("why did nvda crash")
assert said.startswith("The run before this one was NVDA 2026.3.1, started at 22:00:00.\nNVDA crashed, at 23:59:59. It then restarted itself.")
assert onLog("what is NVDA's logging level").startswith("NVDA's logging level is Info.")
assert onLog("where is nvda's log file").startswith(f"NVDA's log of this run is the file {nvdaLogPath}.")
said = onLog("when did nvda start")
assert said.startswith("This run of NVDA, version 2026.3.1, started at 09:00:00, and was ready at 09:00:03.") and (
	"The run before: NVDA crashed, at 23:59:59." in said), said
assert onLog("what did the developer info say").startswith("The developer info NVDA wrote at 09:07:00 is for the button \"Save\", in the "
	"program notepad.")
assert onLog("what is its automation id in the developer info") == ("In the developer info NVDA wrote at 09:07:00, its automation ID "
	"is SaveButton.")
assert onLog("which keys did I try in input help") == ("Keys you tried in input help in this run, in order: 1.\n1. At 09:08:00: "
	"NVDA+shift+v, which runs the command sayDate, of the add-on Clock and Calendar (clock).")
assert onLog("when were my settings last saved").endswith("The last time NVDA saved its settings was at 09:09:00.")
assert onLog("is nvda remote connected").startswith("NVDA Remote is connected, and this computer controls the other one.")
# Asking to turn it on: where it is, and the offer; nothing is changed.
instance.clawAsk = lambda question, choices: logQuestions.append((question, choices)) or 0
said = onLog("turn on NVDA's debug logging")
assert logQuestions[-1][0].startswith("VisionClaw never changes NVDA's logging level itself. It is Info now.") and len(panels) == 2
assert conf["general"]["loggingLevel"] == "INFO" and nvdaLevel["level"] == 20
# One error explained: the model that writes code is given that error alone, and its words are said to be its own.
said = onLog("explain NVDA error 1")
assert said.endswith("What the coder model says this error means, which may be wrong: The clock add-on could not turn the word ten "
	"into a number, so it could not say the time."), said
assert "in the main file of its folder globalPlugins/clock, line 60" in said
role, system, user = LogRuntime.asked[-1]
assert role == CODER and user.startswith("Error in NVDA's log: Error in script_sayTime") and not any(word in user for word in SECRET)
# What is new since VisionClaw last read the log: only that.
with open(nvdaLogPath, "a", encoding="utf-8") as f:
	f.write(entryText("WARNING", "09:20:00.000", "Couldn't open specified or default audio device. There may be no audio devices.",
		"nvwave.WavePlayer.open") + entryText("IO", "09:20:01.000", "Input: kb(desktop):p", "inputCore.InputManager.executeGesture"))
said = onLog("anything new in nvda's log")
assert said.startswith("What NVDA wrote to its log since VisionClaw last read it, at ") and "Error in script_sayTime" not in said
assert "At 09:20:00: NVDA could not open the sound output device" in said and "1 entry of the levels that hold" in said, said
# What NVDA wrote just now: the two minutes before the request.
justNow = time.strftime("%H:%M:%S", time.localtime(time.time() - 30)) + ".000"
with open(nvdaLogPath, "a", encoding="utf-8") as f:
	f.write(entryText("INFO", justNow, "Loaded synthDriver espeak", "synthDriverHandler.setSynth"))
said = onLog("what just happened in nvda")
assert said == ("What NVDA wrote to its log in the 2 minutes before you asked, in order:\nAt "
	f"{justNow[:8]}: NVDA loaded the speech synthesizer espeak."), said
# For other parts of VisionClaw: a mark at the end of the log, and the readable entries written after it.
position = nvdalogtools.mark()
assert position["path"] == nvdaLogPath and position["offset"] == os.path.getsize(nvdaLogPath)
assert nvdalogtools.since(position) == []
with open(nvdaLogPath, "a", encoding="utf-8") as f:
	f.write(entryText("IO", "09:30:00.000", "Speaking ['hunter2']", "speech.speech.speak")
		+ entryText("ERROR", "09:30:01.000", "setSynth failed for sapi5", "synthDriverHandler.setSynth"))
after = nvdalogtools.since(position)
assert [entry.message for entry in after] == ["setSynth failed for sapi5"] and all(not entry.private for entry in after)
assert logModule.troubleText(after) == "The speech synthesizer sapi5 could not be started."
assert nvdalogtools.since(None) == [] and nvdalogtools.since({"path": "elsewhere.log", "offset": 0}) == []
assert nvdalogtools.since({"path": nvdaLogPath, "offset": 10 ** 9}) == []
assert [fact["kind"] for fact in nvdalogtools.factsSince()][:3] == ["started", "windows", "initialized"]
# Nothing typed or spoken reached VisionClaw's own log or anything else it keeps.
for folder, _dirs, names in os.walk(DATA):
	for name in names:
		with open(os.path.join(folder, name), encoding="utf-8", errors="ignore") as f:
			kept = f.read()
		assert "hunter2" not in kept and "kb(desktop):p" not in kept, os.path.join(folder, name)
globalVarsModule.appArgs.logFileName = None
assert nvdalogtools.mark() is None
instance.runtime = realRuntime
instance.orchestrator.last = realLast
instance.clawAsk = realClawAsk
sys.modules["gui"].mainFrame = realMainFrame
sys.modules["addonHandler"].getAvailableAddons = realAvailable
logHandlerModule.log = realLogStandIn
if not hadGeneral:
	del conf["general"]
shutil.rmtree(nvdaLogDir, ignore_errors=True)

instance.terminate()
print("OK")
