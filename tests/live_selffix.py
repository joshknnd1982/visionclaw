# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A real model corrects VisionClaw's own code from a complaint, with no error in VisionClaw's log (claw/diagnose.py):
plain code reads the complaint, finds the functions the request's tool used and ranks them by the complaint's words; the
model that writes code chooses one by its number and corrects it; plain code checks the correction, the other model reads
it, and the corrected function is run against stand-ins made by this test, to see whether it does what the user wanted.
Nothing of VisionClaw's own code is changed and nothing is put in place: a corrected function runs only in modules this
test makes, against stand-ins. Never the real NVDA, the real mouse or the real keyboard.

The five cases were written on 2026-11-19 before anything was run on them. The first is the bug the owner found in
1.18.0: the function openPanel of nvdalogtools.py as it was in commit bf61849, with the rest of that file and the real
claw/nvdalog.py around it, run against stand-ins for NVDA's settings window in which the focus goes to the page's first
control, Make screen black, unless the function puts it on the Logging level combo box. The names of NVDA the stand-ins
share with NVDA (_logLevelCombo, currentCategory, categoryClasses, catListCtrl, container, setPostInitFocus) are those
focustools.py was written from; the other names are the stand-in's own. The other four cases are made up: each a small
file of VisionClaw-like code with one bug and functions that are not the bug. Where the model chooses a function that is
not the bug, the bug itself is also given to it, to measure the correction apart from the choice. Read every correction:
one that does what was intended here may still be wrong in NVDA.

Measured on 2026-11-19 with Qwen3.5 4B for both jobs: 5 of 5 read as complaints, the function with the bug offered 5 of 5
(first 4 of 5), chosen 5 of 5; corrections that did what was intended 3 of 5. The focus bug was not corrected: the model
called gui.mainFrame.getFocus(), which does not exist. After that run, diagnose.unknownNames was added, so the first case
is spent for measuring it: with it, the same made-up name was refused three times and no correction was offered. With
Qwen3 14B writing code (the model for hard cases): the same 5 of 5 chosen and 3 of 5 that did what was intended; the
focus bug was not corrected either (it asked the class of the settings page for its combo box).

  python -u tests/live_selffix.py MODELS VISIONID CODERID [--dry] [--no-names]
	--dry        plain code only: what is found and offered to the model; no model is asked
	--no-names   without the check of names the running program does not have (diagnose.unknownNames)
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import types

import harness
from visionClaw.claw import catalog, diagnose, prompts, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.llm import LLM, LLMError

# --- The cases, written before anything was run on them ---

FOCUS_RESULT = ("NVDA's settings are open at Privacy and Security. Press Tab until you reach the Logging level combo box, "
	"choose with the arrow keys, Info is enough, then press Enter. VisionClaw changed nothing itself.")
FOCUS_ASKED = ("NVDA's log is switched off: NVDA's logging level is Disabled, so NVDA writes nothing to its log. Open NVDA's "
	"Privacy and Security settings now, at the Logging level combo box?")

VOLUME = '''\
# A stand-in made by tests/live_selffix.py: VisionClaw-like code with one bug.

_endpoint = {"level": 0.5, "muted": False}


def readVolume():
	"""The computer's volume as Windows gives it: from 0.0 to 1.0."""
	return float(_endpoint["level"])


def isMuted():
	"""Whether the computer's sound is muted."""
	return bool(_endpoint["muted"])


def clampLevel(value):
	"""A volume from 0.0 to 1.0, whatever was asked."""
	return min(1.0, max(0.0, float(value)))


def volumeText(level):
	"""The computer's volume in words, for the user."""
	return f"The computer's volume is {round(level, 2)} percent."


def muteText(muted):
	"""Whether the sound is muted, in words."""
	return "The sound is muted." if muted else "The sound is on."


def register(add, plugin):
	def systemVolume(task, asked):
		level = clampLevel(readVolume())
		said = volumeText(level)
		if isMuted():
			said += " " + muteText(True)
		return said

	add("system_volume", systemVolume)
'''

LISTS = '''\
# A stand-in made by tests/live_selffix.py: VisionClaw-like code with one bug.


def itemsOf(listBox):
	"""The names of a list's items, in order."""
	return [str(item) for item in listBox.items]


def indexOf(items, name):
	"""Which item of a list a name means: its number from 0."""
	found = 0
	wanted = name.lower()[:2]
	for index, item in enumerate(items):
		if item.lower().startswith(wanted):
			found = index
	return found


def selectAt(listBox, index):
	"""Select the item at a number, as a press of the arrow keys would."""
	listBox.selected = index
	return listBox.items[index]


def spokenItem(item, index, count):
	"""What the user hears about the chosen item."""
	return f"Selected {item}, {index + 1} of {count}."


def register(add, plugin):
	def chooseItem(task, asked):
		listBox = plugin.listBox
		items = itemsOf(listBox)
		name = asked.split(" ", 1)[-1]
		index = indexOf(items, name)
		item = selectAt(listBox, index)
		return spokenItem(item, index, len(items))

	add("choose_item", chooseItem)
'''

KEYS = '''\
# A stand-in made by tests/live_selffix.py: VisionClaw-like code with one bug.

COMMANDS = {
	"nvda menu": {"description": "Shows the NVDA menu", "gestures": ["kb:NVDA+n", "kb(laptop):NVDA+control+n"]},
	"say all": {"description": "Reads from the caret to the end", "gestures": ["kb(desktop):NVDA+downArrow", "kb(laptop):NVDA+a"]},
	"time": {"description": "Says the time", "gestures": ["kb:NVDA+f12"]},
}


def commandOf(asked):
	"""The command the user's words name."""
	low = asked.lower()
	for name in COMMANDS:
		if name in low:
			return name
	return ""


def gestureOf(command):
	"""The key of a command that the user is told: the one for a desktop keyboard."""
	return COMMANDS[command]["gestures"][-1]


def keyWords(gesture):
	"""A key as NVDA writes it, without the part that says which keyboard it is for."""
	return gesture.split(":", 1)[-1]


def register(add, plugin):
	def tellKey(task, asked):
		command = commandOf(asked)
		if not command:
			return "No command was found."
		return f"The key for {command} is {keyWords(gestureOf(command))}."

	add("explain_keys", tellKey)
'''

LINES = '''\
# A stand-in made by tests/live_selffix.py: VisionClaw-like code with one bug.


def caretInfo(obj):
	"""The text at the caret of a control."""
	return obj.makeTextInfo("caret")


def lineAt(info):
	"""The line a text range is on."""
	line = info.copy()
	line.move("line", -1)
	line.expand("line")
	return line.text


def spoken(text):
	"""A line as the user hears it; an empty one is said as blank."""
	return text.strip() or "blank"


def register(add, plugin):
	def readLine(task, asked):
		info = caretInfo(plugin.focus)
		return spoken(lineAt(info))

	add("read_line", readLine)
'''


class Lines:
	"""A stand-in for NVDA's text range over a few lines, with the caret on one."""

	def __init__(self, lines, at):
		self.lines, self.at, self.text = lines, at, ""

	def copy(self):
		return Lines(self.lines, self.at)

	def move(self, unit, count, endPoint=None):
		new = min(max(0, self.at + count), len(self.lines) - 1)
		moved, self.at = new - self.at, new
		return moved

	def expand(self, unit):
		self.text = self.lines[self.at]

	def collapse(self, end=False):
		pass


def checkVolume(module):
	said = [module.volumeText(level) for level in (0.5, 0.07, 1.0)]
	return all(f"{number} percent" in text for number, text in zip((50, 7, 100), said)), " / ".join(said)


def checkLists(module):
	items = ["Desktop", "Documents", "Downloads", "Music"]
	got = [module.indexOf(items, name) for name in ("Documents", "downloads", "Music", "Desktop")]
	return got == [1, 2, 3, 0], f"indexOf gives {got} for Documents, downloads, Music, Desktop; [1, 2, 3, 0] is right"


def checkKeys(module):
	got = [module.gestureOf(name) for name in ("nvda menu", "say all", "time")]
	return got == ["kb:NVDA+n", "kb(desktop):NVDA+downArrow", "kb:NVDA+f12"], f"gestureOf gives {got}"


def checkLines(module):
	lines = ["first line", "second line", "third line"]
	got = [module.lineAt(Lines(lines, at)) for at in (1, 0, 2)]
	return got == ["second line", "first line", "third line"], f"lineAt gives {got} for the caret on lines 2, 1 and 3"


# (name, file, source or None for the old nvdalogtools.py, the tool, the complaint, what VisionClaw did, the function
# with the bug, the check of the corrected module)
CASES = (
	("the focus put on Make screen black", "nvdalogtools.py", None, "nvda_log",
		"I said yes to opening NVDA's settings at the Logging level combo box, but the focus landed on Make screen black "
		"(immediate effect) instead, fix that",
		{"request": "check NVDA's log", "steps": [{"tool": "nvda_log", "title": "Reading NVDA's own log", "status": "done",
			"result": FOCUS_RESULT}], "asked": [(FOCUS_ASKED, "Yes, open them")], "answer": FOCUS_RESULT},
		"openPanel", None),
	("the volume said as 0.5 percent", "systemtools.py", VOLUME, "system_volume",
		"you said the computer's volume is 0.5 percent, but it is at half, it should have said 50 percent",
		{"request": "what is the computer's volume", "steps": [{"tool": "system_volume", "title": "Reading the volume",
			"status": "done", "result": "The computer's volume is 0.5 percent."}], "asked": [],
			"answer": "The computer's volume is 0.5 percent."},
		"volumeText", checkVolume),
	("Downloads selected for Documents", "listtools.py", LISTS, "choose_item",
		"you selected Downloads instead of Documents",
		{"request": "choose Documents", "steps": [{"tool": "choose_item", "title": "Choosing in the list", "status": "done",
			"result": "Selected Downloads, 3 of 4."}], "asked": [], "answer": "Selected Downloads, 3 of 4."},
		"indexOf", checkLists),
	("the laptop key told for the NVDA menu", "keytools.py", KEYS, "explain_keys",
		"you told me the key for the NVDA menu is NVDA+control+n, but that is the laptop key, it should have been NVDA+n",
		{"request": "what is the key for the nvda menu", "steps": [{"tool": "explain_keys", "title": "Finding the key",
			"status": "done", "result": "The key for nvda menu is NVDA+control+n."}], "asked": [],
			"answer": "The key for nvda menu is NVDA+control+n."},
		"gestureOf", checkKeys),
	("the line above read", "readtools.py", LINES, "read_line",
		"you read the line above instead of the line I am on",
		{"request": "read the current line", "steps": [{"tool": "read_line", "title": "Reading the line", "status": "done",
			"result": "first line"}], "asked": [], "answer": "first line"},
		"lineAt", checkLines),
)

# --- Stand-ins for NVDA's settings window and wx, for the first case ---

SETTINGS = '''\
class Control:
	def __init__(self, label):
		self.label = label

	def SetFocus(self):
		state["focus"] = self

	def SetFocusFromKbd(self):
		self.SetFocus()

	def IsShown(self):
		return True

	def IsEnabled(self):
		return True

	def GetLabel(self):
		return self.label


class SettingsPanel:
	def __init__(self, parent):
		self.parent = parent
		self.controls = []
		self.makeSettings()

	def makeSettings(self):
		pass

	def onSave(self):
		pass


class GeneralSettingsPanel(SettingsPanel):
	title = "General"

	def makeSettings(self):
		self.languageList = Control("Language")
		self.controls = [self.languageList]


class PrivacyAndSecuritySettingsPanel(SettingsPanel):
	title = "Privacy and Security"

	def makeSettings(self):
		self.screenCurtainCheckBox = Control("Make screen black (immediate effect)")
		self.screenCurtainSoundCheckBox = Control("Play sound when toggling screen curtain")
		self._logLevelCombo = Control("Logging level")
		self.controls = [self.screenCurtainCheckBox, self.screenCurtainSoundCheckBox, self._logLevelCombo]


class CategoryList:
	def __init__(self, dialog):
		self.dialog = dialog
		self.selected = 0

	def Select(self, index, on=True):
		self.selected = index

	def Focus(self, index):
		self.dialog._showCategory(index)

	def GetFirstSelected(self):
		return self.selected

	def SetFocus(self):
		state["focus"] = self


class Container:
	def __init__(self, dialog):
		self.dialog = dialog

	def SetFocus(self):
		# As a panel does in wx: the focus goes to its first control.
		self.dialog.currentCategory.controls[0].SetFocus()


class MultiCategorySettingsDialog:
	categoryClasses = []

	def __init__(self, parent, initialCategory=None):
		self.categoryClasses = list(type(self).categoryClasses)
		self.catListCtrl = CategoryList(self)
		self.container = Container(self)
		self.currentCategory = (initialCategory or self.categoryClasses[0])(self)
		self.catListCtrl.Select(self.categoryClasses.index(type(self.currentCategory)))
		# As NVDA's settings window does: once it is shown, the focus goes to the first control of its page.
		self.setPostInitFocus = self.container.SetFocus
		wx.CallAfter(self._postInit)

	def _postInit(self):
		self.setPostInitFocus()

	def _showCategory(self, index):
		self.currentCategory = self.categoryClasses[index](self)

	def IsShown(self):
		return True

	def Raise(self):
		pass

	def SetFocus(self):
		self.catListCtrl.SetFocus()


class NVDASettingsDialog(MultiCategorySettingsDialog):
	title = "NVDA Settings"
	categoryClasses = [GeneralSettingsPanel, PrivacyAndSecuritySettingsPanel]
'''


class Events:
	"""wx's queue of things to do, in the stand-in's own time, in milliseconds."""

	def __init__(self):
		self.now, self.queue, self.number = 0, [], 0

	def add(self, ms, function, args, kwargs):
		self.number += 1
		self.queue.append((self.now + int(ms), self.number, function, args, kwargs))

	def run(self, until=10000):
		while self.queue:
			self.queue.sort(key=lambda event: (event[0], event[1]))
			when, _number, function, args, kwargs = self.queue.pop(0)
			if when > until:
				break
			self.now = max(self.now, when)
			function(*args, **kwargs)


def standIns():
	"""Stand-ins for wx, gui and gui.settingsDialogs, put into sys.modules; (events, state)."""
	events, state = Events(), {"focus": None, "windows": []}
	wx = types.ModuleType("wx")
	wx.CallAfter = lambda function, *args, **kwargs: events.add(0, function, args, kwargs)

	class CallLater:
		def __init__(self, ms, function, *args, **kwargs):
			events.add(ms, function, args, kwargs)

		def Start(self, *args):
			pass

		def Stop(self):
			pass

		def IsRunning(self):
			return False

	wx.CallLater = wx.FutureCall = CallLater
	wx.GetTopLevelWindows = lambda: list(state["windows"])
	wx.Window = types.SimpleNamespace(FindFocus=lambda: state["focus"])
	wx.Yield = wx.SafeYield = lambda *args, **kwargs: True
	settings = types.ModuleType("gui.settingsDialogs")
	settings.__dict__.update(state=state, wx=wx, __name__="gui.settingsDialogs")
	exec(compile(SETTINGS, "gui/settingsDialogs.py", "exec"), settings.__dict__)
	gui = types.ModuleType("gui")

	class MainFrame:
		def popupSettingsDialog(self, dialog, *args, **kwargs):
			state["windows"].append(dialog(self, *args, **kwargs))

	gui.mainFrame, gui.settingsDialogs = MainFrame(), settings
	sys.modules.update({"wx": wx, "gui": gui, "gui.settingsDialogs": settings})
	return events, state


def checkFocus(module):
	events, state = standIns()
	module.openPanel()
	events.run()
	focus = state["focus"]
	label = getattr(focus, "label", None) or type(focus).__name__
	return label == "Logging level", f"the focus is on {label}"


# --- Loading the cases as VisionClaw's code, in a folder of the test's own ---

def stubs():
	"""What the old nvdalogtools.py needs that only NVDA has: addonHandler, and nvdatools' _safe."""
	addonHandler = types.ModuleType("addonHandler")
	addonHandler.initTranslation = lambda: None
	addonHandler.getAvailableAddons = lambda: []
	nvdatools = types.ModuleType("visionClaw.nvdatools")

	def _safe(function, default=None):
		try:
			return function()
		except Exception:
			return default

	nvdatools._safe = _safe
	sys.modules.update({"addonHandler": addonHandler, "visionClaw.nvdatools": nvdatools})


def oldLogTools():
	return subprocess.run(["git", "show", "bf61849:addon/globalPlugins/visionClaw/nvdalogtools.py"], cwd=harness.ROOT,
		capture_output=True, text=True, encoding="utf-8", check=True).stdout


def loadModule(root, relative, source, suffix=""):
	path = os.path.join(root, *relative.split("/"))
	module = types.ModuleType(f"visionClaw.{relative[:-3]}{suffix}")
	module.__package__ = "visionClaw"
	module.__dict__["_"] = lambda text: text
	exec(compile(source, path, "exec"), module.__dict__)
	return module


def toolOf(module, name):
	added = {}
	plugin = types.SimpleNamespace(clawAsk=lambda question, choices: 0, listBox=None, focus=None,
		orchestrator=types.SimpleNamespace(last=None))
	if "onMain" in module.register.__code__.co_varnames:
		module.register(lambda tool, *args, **kwargs: added.setdefault(tool, args[1] if len(args) > 1 else None),
			plugin, lambda *a, **k: {}, lambda function: function(), lambda question: None, lambda question: None)
	else:
		module.register(lambda tool, function: added.setdefault(tool, function), plugin)
	return added[name]


# --- The model's part, as diagnosetools.py does it ---

def choose(rt, complaint, done, offered):
	small = (rt.entry(CODER) or {}).get("suggest") is False
	none = not small
	if len(offered) == 1 and small:
		return 0, "plain code (one fits)"
	llm = LLM(rt, taskModule.Task(complaint))
	try:
		chosen = int(llm.json(CODER, diagnose.CHOOSE_SYSTEM + (diagnose.CHOOSE_NONE if none else ""),
			diagnose.chooseQuestion(complaint, done, offered), diagnose.chooseSchema(len(offered), none), maxTokens=20).get("number"))
	except (LLMError, TypeError, ValueError, AttributeError) as e:
		return None, f"no answer: {e}"
	return (chosen - 1 if 1 <= chosen <= len(offered) else None), f"the model said {chosen}"


def correct(rt, complaint, entry, done):
	"""The correction loop of diagnosetools.writeCorrection: (the function or None, problems, review, tries)."""
	place, source = entry["place"], entry["source"]
	nvda = diagnose.namesFacts(entry["function"], place, sys.modules, complaint)
	facts = diagnose.complaintFacts(complaint, done, entry, nvda)
	if nvda:
		print("  NVDA facts given:\n    " + "\n    ".join(nvda))
	llm = LLM(rt, taskModule.Task(complaint))
	user = f"{facts}\nThe user asked: \"{complaint}\"\nWrite the whole corrected function."
	newText, problems, review, reviewed, tries = None, [], "", False, 0
	for _attempt in range(diagnose.TRIES):
		tries += 1
		started = time.time()
		asking = user + (f"\nThe correction you wrote before had problems: {' '.join(problems[:3])}" if problems else "")
		answer = llm.text(CODER, prompts.coding(diagnose.COMPLAINT_FIX_TASK, complaint), asking, maxTokens=1600,
			temperature=0, code=True)
		candidate = diagnose.bodyAligned(diagnose.tidy(diagnose.extractFunction(answer), place))
		problems = diagnose.checkFix(source, place, candidate, True) if candidate else ["no function"]
		if not problems and "--no-names" not in sys.argv:
			problems = diagnose.unknownNames(candidate, entry["function"], sys.modules)
		print(f"  try {tries} ({time.time() - started:.1f} s): " + ("passes plain code's checks" if not problems
			else "problems: " + " ".join(problems)))
		if problems:
			print(textwrap.indent(candidate or answer, "    | "))
			continue
		verdict = llm.json(VISION, diagnose.COMPLAINT_REVIEW_SYSTEM,
			f"{facts}\nThe corrected function:\n```python\n{candidate}```\nDoes it do what the user expected and change nothing else?",
			diagnose.REVIEW_SCHEMA, maxTokens=160)
		problem = " ".join(str(verdict.get("problem") or "").split())
		newText = candidate
		print(f"  the other model: {verdict}")
		if verdict.get("fixes") is False and problem and not reviewed:
			reviewed, problems = True, [problem]
			continue
		review = problem
		break
	return newText, problems, review, tries


def run(case, root, check, newText, entry):
	"""The corrected function run against the stand-ins: (did what was intended, what was seen)."""
	source = diagnose.replaced(entry["source"], entry["place"], newText)
	try:
		module = loadModule(root, entry["file"], source, "_fixed")
		return check(module)
	except Exception as e:
		return False, f"it failed when run: {type(e).__name__}: {e}"


def main():
	sys.stdout.reconfigure(errors="replace")
	dry = "--dry" in sys.argv
	args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
	rt = None
	if not dry:
		folder = args[0] if args else "no-models-folder"
		cat = catalog.Catalog(folder, harness.visionMateData())
		chosen = {"backend": "auto", "visionModel": args[1] if len(args) > 1 else "", "coderModel": args[2] if len(args) > 2 else ""}
		rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
		if not rt.hasModel(CODER):
			sys.exit("No model found.")
		print("models:", rt.entry(VISION)["name"], "and", rt.entry(CODER)["name"])
	stubs()
	temporary = tempfile.mkdtemp(prefix="vcselffix-")
	root = os.path.join(temporary, "globalPlugins", "visionClaw")
	os.makedirs(root)

	def read(relative):
		mine = os.path.join(root, *relative.split("/"))
		path = mine if os.path.isfile(mine) else os.path.join(harness.PLUGIN_DIR, *relative.split("/"))
		try:
			with open(path, encoding="utf-8") as f:
				return f.read()
		except OSError:
			return ""

	score = {"read": 0, "offered": 0, "first": 0, "chose": 0, "passed": 0, "intended": 0, "givenPassed": 0, "givenIntended": 0}
	try:
		for name, relative, source, tool, complaint, did, buggy, check in CASES:
			print(f"\n=== {name}\nThe user: {complaint}")
			source = source if source is not None else oldLogTools()
			with open(os.path.join(root, relative), "w", encoding="utf-8") as f:
				f.write(source)
			if check is None:
				check = checkFocus
				standIns()
			module = loadModule(root, relative, source)
			want = diagnose.wish(complaint)
			print(f"plain code reads it as: {want and want['do']}, complaint: {bool(want and want['complaint'])}")
			score["read"] += bool(want and want["do"] == diagnose.FIX and want["complaint"])
			item = dict(did, said=did["request"], when=time.time(), state="done")
			found = diagnose.usedFunctions(toolOf(module, tool), read, root, sys.modules)
			offered = diagnose.fitting(found, complaint, item["answer"])
			usable = [entry for entry in found if not entry["refusal"]]
			print(f"plain code found {len(found)} functions, {len(usable)} that can be corrected; offered: "
				+ ", ".join(f"{entry['qualname']} ({entry['file']})" for entry in offered))
			names = [entry["place"]["name"] for entry in offered]
			score["offered"] += buggy in names
			score["first"] += bool(names) and names[0] == buggy
			# The function with the bug as it is, run against the stand-ins: it must not do what was intended.
			bugEntry = next((entry for entry in found if entry["place"]["name"] == buggy), None)
			if bugEntry is not None:
				print("before the correction: " + run(name, root, check, textwrap.dedent(bugEntry["place"]["text"]), bugEntry)[1])
			if dry or not offered:
				continue
			done = diagnose.doneText(item)
			started = time.time()
			index, how = choose(rt, complaint, done, offered)
			chosenEntry = offered[index] if index is not None else None
			print(f"the model chose: {chosenEntry['qualname'] if chosenEntry else 'none'} ({how}, {time.time() - started:.1f} s)")
			rightChoice = chosenEntry is not None and chosenEntry["place"]["name"] == buggy
			score["chose"] += rightChoice
			for given, entry in (("chosen", chosenEntry), ("given", None if rightChoice or bugEntry is None else bugEntry)):
				if entry is None:
					continue
				print(f"-- the correction of {entry['qualname']} ({given})")
				newText, problems, review, tries = correct(rt, complaint, entry, done)
				if newText is None:
					print(f"  no correction passed plain code's checks after {tries} tries")
					continue
				print("  what it changes: " + diagnose.changeText(entry["place"]["text"], newText))
				print(textwrap.indent(newText, "    | "))
				ok, seen = run(name, root, check, newText, entry)
				print(f"  run against the stand-ins: {seen}" + (", as intended." if ok else ", NOT what was intended."))
				if given == "chosen":
					score["passed"] += 1
					score["intended"] += ok and rightChoice
				else:
					score["givenPassed"] += 1
					score["givenIntended"] += ok
	finally:
		if rt is not None:
			rt.stop()
		shutil.rmtree(temporary, ignore_errors=True)
	count = len(CASES)
	print(f"\nRead as a complaint: {score['read']} of {count}. The function with the bug offered: {score['offered']} of "
		f"{count}, first: {score['first']} of {count}.")
	if not dry:
		print(f"The model chose the function with the bug: {score['chose']} of {count}. Its correction passed the checks: "
			f"{score['passed']}; did what was intended, of the right function: {score['intended']} of {count}. Given the function "
			f"with the bug where it chose another: passed {score['givenPassed']}, did what was intended {score['givenIntended']}.")


if __name__ == "__main__":
	main()
