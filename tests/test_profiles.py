# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""An NVDA setting changed only for one program: what the user's words ask for (claw/profiles.py), and what is
done with NVDA's configuration profiles (profiletools.py) against a stand-in that behaves as NVDA's own source
says its profiles do (tests/profilestandin.py). Plain Python; nothing of the real NVDA is touched.

The tools themselves (set_setting with "only in this program", undo_change, program_settings,
remove_program_settings) are driven in tests/test_nvda_stub.py.
"""
import importlib
import sys
import types

import harness  # noqa: F401
import profilestandin
from visionClaw.claw import changes as changesModule
from visionClaw.claw import planner, profiles, router

# ---------------------------------------------------------------------------------------------------------
# What the words ask for.
# ---------------------------------------------------------------------------------------------------------

FRONT = ""
SCOPED = {
	"Make NVDA speak a little faster, only in this program.": (FRONT, "Make NVDA speak a little faster."),
	"make nvda speak faster only in this app": (FRONT, "make nvda speak faster"),
	"turn off the typing echo just in Notepad": ("Notepad", "turn off the typing echo"),
	"When I'm in Word, set punctuation to all": ("Word", "set punctuation to all"),
	"when i am in word set punctuation to all": ("word", "set punctuation to all"),
	"set the speech rate to 70 for this program": (FRONT, "set the speech rate to 70"),
	"in notepad only, turn off typing echo": ("notepad", "turn off typing echo"),
	"turn the pitch up only here": (FRONT, "turn the pitch up"),
	"say punctuation only when I am in Visual Studio Code and nowhere else": ("Visual Studio Code", "say punctuation"),
	"turn off typing echo only in the command prompt": ("command prompt", "turn off typing echo"),
	"set punctuation to all only in excel, not everywhere": ("excel", "set punctuation to all"),
	"Speak typed words only in Word": ("Word", "Speak typed words"),
	"just for this game, turn off speech": (FRONT, "turn off speech"),
	"turn the voice volume down while I'm using Spotify": ("Spotify", "turn the voice volume down"),
	"Turn off the typing echo in this program": (FRONT, "Turn off the typing echo"),
	"only while I am in this program, raise the pitch": (FRONT, "raise the pitch"),
}
for said, (program, rest) in SCOPED.items():
	found = profiles.scopeOf(said)
	assert found is not None and found["program"] == program, (said, found)
	assert profiles.without(said) == rest, (said, profiles.without(said))

# A program named with "in" alone, as in JAWS's own example "Stop announcing capital letters in Word": taken for a
# program where the name is one everybody knows and is written as a name, or is the program in front.
TRADER = {"app": "spacetrader", "product": "Space Trader", "title": "Space Trader - Main Menu"}
for said, alone, here in (
		("Stop announcing capital letters in Word.", "Word", "Word"),
		("In Word, stop announcing capital letters", "Word", "Word"),
		("stop announcing capitals in Space Trader", None, "Space Trader"),
		("speak typed characters in edit fields", None, None),
		("set punctuation to all in general", None, None),
		("read the title in braille", None, None),
		("turn on speech in notepad", None, None)):  # not written as a name, and not the program in front
	found, front = profiles.scopeOf(said), profiles.scopeOf(said, TRADER)
	assert (found or {}).get("program") == alone and (front or {}).get("program") == here, (said, found, front)
assert profiles.without("Stop announcing capital letters in Word.") == "Stop announcing capital letters"
assert profiles.without("stop announcing capitals in Space Trader", TRADER) == "stop announcing capitals"
# Every program: JAWS's other example, and other ways of saying it. Then no one program is meant, and the words
# that say so are no part of the setting's name.
for said, rest in {
		"Speak words as I type in every application": "Speak words as I type",
		"make speech faster everywhere": "make speech faster",
		"turn off the typing echo in all programs": "turn off the typing echo",
		"turn off typing echo, not only in this program": "turn off typing echo",
		"set punctuation to all for every app": "set punctuation to all",
		"Make NVDA louder globally.": "Make NVDA louder."}.items():
	assert profiles.everywhere(said) and profiles.scopeOf(said) is None and profiles.scopeOf(said, TRADER) is None, said
	assert profiles.without(said) == rest, (said, profiles.without(said))
for said in ("make speech faster", "turn off typing echo only in this program", "set punctuation to all only in excel, not everywhere",
		"say all", "turn the volume up in this program and nowhere else"):
	assert not profiles.everywhere(said), said
for said in ("Speak words as I type in every application", "Stop announcing capital letters in Word.",
		"turn off typing echo, not only in this program", "make speech faster everywhere"):
	assert planner.hint(said) == "change_setting", (said, planner.hint(said))
assert "only in Notepad, or everywhere?" in profiles.whichQuestion("speech rate", "50", "60", "Notepad")
assert profiles.whichChoices("Notepad")[:2] == ["Only in Notepad", "Everywhere"]
assert profiles.everywhereDone("Speech rate", "50", "60") == "Everywhere: Speech rate was 50 and is now 60."
assert "Notepad has a value of its own for this, 70, and keeps it." in profiles.everywhereDone("Speech rate", "50", "60", "Notepad", "70")
assert profiles.othersKeep([]) == "" and profiles.othersKeep(["Word"]) == " Word has a value of its own for this and keeps it."
assert profiles.othersKeep(["Word", "Notepad", "Excel"]) == " Word, Notepad and Excel have values of their own for this and keep them."

# Words that narrow down something else than the program: a value of a setting, a moment, a place in a text.
NOT_SCOPED = (
	"make speech faster", "speak typed characters only in edit fields", "beep when I use caps lock",
	"make it only speak words when in edit fields", "say punctuation only in documents", "turn off typing echo",
	"read only the links on this page", "announce capitals only with a beep", "only say the time",
	"turn up the volume just a little", "tell me a hint when I use the arrow keys", "only in my browser make the voice slower",
	"turn on speech when I am in a hurry", "say all only in browse mode", "set the rate to 60 in general",
	"when I use the mouse, report what is under it", "just in case, turn the volume up", "open the settings of this program",
)
for said in NOT_SCOPED:
	assert profiles.scopeOf(said) is None, (said, profiles.scopeOf(said))
	assert profiles.without(said) == " ".join(said.split()), said

# Where the words narrow something down and no program could be read, the user is told that it is for every
# program before anything changes.
assert profiles.NARROWS.search("only in my browser make the voice slower")
assert profiles.NARROWS.search("speak typed characters only in edit fields")
assert not profiles.NARROWS.search("make speech faster")
assert not profiles.NARROWS.search("turn the volume up just a little")

# "Only", "just" and "when I am in" narrow a request down; "in this program" alone does not.
assert profiles.restricts("turn the volume up only in this program")
assert profiles.restricts("When I'm in Word, set punctuation to all")
assert not profiles.restricts("turn on the Use GPU option in this program")
assert not profiles.restricts("make speech faster")

# Whether a program the user named is the one in front.
NOTEPAD = {"app": "notepad", "product": "Microsoft Windows Operating System", "title": "Untitled - Notepad"}
WORD = {"app": "winword", "product": "Microsoft Office", "title": "Letter.docx - Word"}
CODE = {"app": "code", "product": "Visual Studio Code", "title": "main.py - project - Visual Studio Code"}
EDGE = {"app": "msedge", "product": "Microsoft Edge", "title": "News - Personal - Microsoft Edge"}
for name, facts, expected in (
		("Notepad", NOTEPAD, True), ("notepad", NOTEPAD, True), ("Word", WORD, True), ("word", WORD, True),
		("Microsoft Word", WORD, True), ("Visual Studio Code", CODE, True), ("vs code", CODE, True), ("Edge", EDGE, True),
		("Word", NOTEPAD, False), ("Notepad", WORD, False), ("Excel", WORD, False), ("Chrome", EDGE, False),
		("Spotify", NOTEPAD, False), ("", NOTEPAD, True), ("Letter", NOTEPAD, False)):
	assert profiles.fits(name, facts) is expected, (name, facts["app"], profiles.fits(name, facts))
# A program is called what its maker calls it, unless that says nothing about it.
assert profiles.shown(NOTEPAD) == "Notepad" and profiles.shown(WORD) == "Word", (profiles.shown(NOTEPAD), profiles.shown(WORD))
assert profiles.shown(CODE) == "Visual Studio Code" and profiles.shown(EDGE) == "Microsoft Edge"
assert profiles.shown({"app": "spacetrader", "product": "Space Trader"}) == "Space Trader"
assert profiles.shown({"app": "oddgame", "product": "Microsoft Windows Operating System"}) == "oddgame"
assert profiles.shown({"app": "", "product": ""}) == "this program"

# The profile is called what NVDA itself would call it, the program's own name; another name when that is taken.
assert profiles.profileName("notepad", []) == "notepad"
assert profiles.profileName("notepad", ["Notepad"]) == "notepad (VisionClaw)"
assert profiles.profileName("notepad", ["notepad", "notepad (visionclaw)"]) == "notepad (VisionClaw 2)"
assert profiles.appOf("app:notepad") == "notepad" and profiles.appOf("sayAll") == "" and profiles.appOf("app:") == ""

# Which request takes a program's settings away again, and which asks which programs have some.
REMOVES = {
	"remove the settings for this program": "", "make Notepad behave like everywhere else again": "Notepad",
	"delete the configuration profile for Word": "Word", "Delete the NVDA profile of this program": "",
	"get rid of the settings for Excel": "Excel", "reset the settings for this app": "",
	"make this program sound like all other programs again": "",
}
for said, named in REMOVES.items():
	assert profiles.removes(said), said
	assert not profiles.asks(said), said
	assert profiles.namedIn(said) == named, (said, profiles.namedIn(said))
ASKS = (
	"which programs have their own settings", "does this program have its own NVDA settings", "list my configuration profiles",
	"what programs have different settings", "is a configuration profile active", "Which apps have special NVDA settings?",
)
for said in ASKS:
	assert profiles.asks(said) and not profiles.removes(said), said
for said in (
		"delete the file settings.txt", "how do I delete a configuration profile", "remove the notes for this program",
		"reset the speech rate", "delete my chrome profile", "what did you change", "undo that", "open the settings",
		"remove the hotkey for this program", "turn off typing echo", "which settings did you change"):
	assert not profiles.removes(said) and not profiles.asks(said), said

# Where each request is sent. A setting for one program stays a setting of NVDA, and is never taken for a control
# of the program; a control of the program stays one.
HINTS = {
	"Make NVDA speak a little faster, only in this program.": "change_setting",
	"turn off the typing echo just in Notepad": "change_setting",
	"When I'm in Word, set punctuation to all": "change_setting",
	"turn off the typing echo in this program": "change_setting",
	"turn the volume up only in this program": "change_setting",
	"only here, make the voice slower": "change_setting",
	"turn the volume up a bit in this program": "set_control",
	"turn on the Use GPU option in this program": "set_control",
	"In this dialog, turn on dark mode": "set_control",
	"turn off typing echo": "change_setting",
	"remove the settings for this program": "remove_program_settings",
	"make Notepad behave like everywhere else again": "remove_program_settings",
	"delete the configuration profile for Word": "remove_program_settings",
	"which programs have their own settings": "program_settings",
	"does this program have its own NVDA settings": "program_settings",
	"what did you change": "list_changes",
	"undo that": "undo_change",
	"delete the file settings.txt": "file_task",
}
for said, recipe in HINTS.items():
	assert planner.hint(said) == recipe, (said, planner.hint(said))


class _Registry:
	def has(self, names):
		return True

	def get(self, name):
		return types.SimpleNamespace(title=name, before=None)


for said, recipe in HINTS.items():
	offered = planner.offered(said, _Registry(), {router.WEB: False, router.CONTROLLER: False, router.DIRECT: False})
	assert recipe in offered, (said, recipe, offered)
# Taking a program's settings away is offered only when the words ask for it.
for said in ("turn off typing echo", "make speech faster", "what is on my screen", "delete the file notes.txt"):
	offered = planner.offered(said, _Registry(), {})
	assert "remove_program_settings" not in offered and "program_settings" not in offered, (said, offered)
# A model that chose it for words that do not ask for it is corrected by plain code.
assert planner.fitted("remove_program_settings", "turn off typing echo", "change_setting") == "change_setting"

# The words that say for which program are no thing to do of their own. Measured with Qwen3.5 9B on 2026-11-18:
# "Make NVDA speak a little faster, only in this program." was split at its comma, "only in this program" was taken
# for a request to describe the screen, and the setting was changed in every program. So the words are put aside
# before a request is split, and given back to every part that changes a setting. No model is needed for these.
SPLITS = {
	"Make NVDA speak a little faster, only in this program.": ["Make NVDA speak a little faster, only in this program."],
	"When I'm in Word, set punctuation to all": ["When I'm in Word, set punctuation to all"],
	"Turn off the typing echo just in this app.": ["Turn off the typing echo just in this app."],
	"Turn off the typing echo and set punctuation to all, only in this program": [
		"Turn off the typing echo only in this program", "Set punctuation to all only in this program"],
	"Only in Notepad, turn off the typing echo, then open my downloads folder": [
		"Turn off the typing echo only in Notepad", "Open my downloads folder"],
	"Make NVDA speak faster only in this program, then tell me what is on my screen": [
		"Make NVDA speak faster only in this program", "Tell me what is on my screen"],
}
for said, parts in SPLITS.items():
	found = planner.split(None, None, said)
	assert found == parts, (said, found)
	# Every part that changes a setting still says for which program, and no other part does.
	for part in found:
		assert (profiles.scopeOf(part) is not None) == (planner.hint(part) == "change_setting"), (said, part)

# What the user is told.
said = profiles.done("Speech rate", "50", "70", "Notepad", "notepad", True)
assert said.startswith("Only in Notepad: Speech rate was 50 and is now 70.") and "new configuration profile called notepad" in said, said
assert "undo that" in said
said = profiles.done("Speech rate", "50", "70", "Notepad", "notepad", False)
assert "new configuration profile" not in said and "configuration profile notepad" in said, said
assert "Word" in profiles.notHere("Word", "Notepad") and "Notepad" in profiles.notHere("Word", "Notepad")
assert "NVDA+Control+P" in profiles.manualOn("quiet") and "quiet" in profiles.manualOn("quiet")
assert "There is none for Notepad yet" in profiles.question("Notepad", True)
assert "already has" in profiles.question("Notepad", False)
assert profiles.listText([]).startswith("No program has NVDA settings of its own")
text = profiles.listText([("notepad", "notepad", True, ["speech rate from 50 to 70."]), ("winword", "winword", False, [])])
assert text.startswith("2 programs have NVDA settings of their own.") and "which is on now" in text, text
assert "VisionClaw changed there: speech rate from 50 to 70." in text, text
# Every sentence the user hears is plain: no Markdown, no code.
for sentence in (profiles.BASE_ONLY, profiles.READ_ONLY, profiles.TRIGGERS_OFF, profiles.NO_PROGRAM, profiles.manualOn("x"),
		profiles.notActive("x"), profiles.undoElsewhere("speech rate", "x"), profiles.removeQuestion("x", "x"), profiles.removed("x", "x")):
	assert not any(mark in sentence for mark in "*`_#"), sentence

# ---------------------------------------------------------------------------------------------------------
# What is done with NVDA's profiles, against the stand-in.
# ---------------------------------------------------------------------------------------------------------

base = {
	"speech": {"symbolLevel": 100, "fake": {"rate": 50}},
	"keyboard": {"speakTypedCharacters": True, "speakTypedWords": False},
	"general": {"language": "en"},
}
conf = profilestandin.Manager(base, spec={})
state = {"front": None, "window": "Untitled - Notepad"}
logged = []
api = types.ModuleType("api")
api.getFocusObject = lambda: types.SimpleNamespace(appModule=state["front"])
api.getForegroundObject = lambda: types.SimpleNamespace(appModule=state["front"], name=state["window"])
config = types.ModuleType("config")
config.conf = conf
appModuleHandler = types.ModuleType("appModuleHandler")
appModuleHandler.AppProfileTrigger = profilestandin.triggerClass(lambda: config.conf)
nvdaState = types.ModuleType("NVDAState")
nvdaState.shouldWriteToDisk = lambda: config.conf.canWrite
logHandler = types.ModuleType("logHandler")
logHandler.log = types.SimpleNamespace(
	debug=lambda *a, **k: None, debugWarning=lambda *a, **k: None, info=lambda *a, **k: logged.append(a[0]),
	warning=lambda *a, **k: logged.append(a[0]), error=lambda *a, **k: logged.append("ERROR " + str(a[0])))
sys.modules.update({
	"api": api, "config": config, "appModuleHandler": appModuleHandler, "NVDAState": nvdaState, "logHandler": logHandler})
profiletools = importlib.import_module("visionClaw.profiletools")
Trigger = appModuleHandler.AppProfileTrigger


class Setting:
	"""A setting as nvdatools knows one: it reads and writes through NVDA's configuration."""

	def __init__(self, ident):
		self.id = ident
		self._path = ident.split(".")

	def _node(self):
		node = config.conf
		for part in self._path[:-1]:
			node = node[part]
		return node

	def read(self):
		return self._node()[self._path[-1]]

	def write(self, value):
		self._node()[self._path[-1]] = value


def front(module, window=""):
	"""Another program comes to the front, as NVDA sees it."""
	profilestandin.switch(Trigger, state["front"], module)
	state["front"], state["window"] = module, window or module.appName


notepad = profilestandin.Module("notepad", "Microsoft Windows Operating System")
word = profilestandin.Module("winword", "Microsoft Office")
nvda = profilestandin.Module("nvda", "NVDA")
echo = Setting("keyboard.speakTypedCharacters")
rate = Setting("speech.fake.rate")

# No program in front, and NVDA's own window in front: no setting for a program.
for module in (None, nvda):
	state["front"] = module
	try:
		profiletools.check("", echo.id)
		raise AssertionError("a setting was allowed with no program in front")
	except profiletools.NotPossible as e:
		assert str(e) == profiles.NO_PROGRAM, e
state["front"] = None

# Notepad in front. It has no profile yet: checking makes none.
front(notepad, "Untitled - Notepad")
module, facts, profile = profiletools.check("", echo.id)
assert module is notepad and facts["app"] == "notepad" and profile is None
assert list(conf.listProfiles()) == [] and conf.triggersToProfiles == {}
# The program the user named must be the one in front.
profiletools.check("Notepad", echo.id)
try:
	profiletools.check("Word", echo.id)
	raise AssertionError("a setting for Word was allowed while Notepad is in front")
except profiletools.NotPossible as e:
	assert str(e) == profiles.notHere("Word", "Notepad"), e
# A setting NVDA keeps the same for every program.
try:
	profiletools.check("", "general.language")
	raise AssertionError("a setting that cannot be in a profile was allowed")
except profiletools.NotPossible as e:
	assert str(e) == profiles.BASE_ONLY

# The profile is made, its trigger is saved, and it is on top at once, though Notepad got the focus before it
# was there.
assert profiletools.top() is None
name, created = profiletools.activate(notepad)
assert (name, created) == ("notepad", True)
assert conf.triggersToProfiles == {"app:notepad": "notepad"} and conf.saved == 1
assert profiletools.top() == "notepad" and conf.profiles[-1].triggered
profiletools.write(name, echo, False)
assert echo.read() is False
assert conf.writes[-1] == ("notepad", "keyboard.speakTypedCharacters", False), conf.writes
# The normal configuration was not touched.
assert base["keyboard"]["speakTypedCharacters"] is True

# In another program the setting is as it was; back in Notepad it is the program's own again.
front(word, "Letter.docx - Word")
assert profiletools.top() is None and echo.read() is True
front(notepad, "Untitled - Notepad")
assert profiletools.top() == "notepad" and echo.read() is False
# A second setting for the same program goes into the same profile; none is made.
name, created = profiletools.activate(notepad)
assert (name, created) == ("notepad", False) and conf.saved == 1
profiletools.write(name, rate, 70)
assert rate.read() == 70 and base["speech"]["fake"]["rate"] == 50
front(word, "Letter.docx - Word")
assert rate.read() == 50

# Nothing is ever written when the program's profile is not the one NVDA writes to.
before = list(conf.writes)
try:
	profiletools.write("notepad", rate, 90)
	raise AssertionError("a program's setting was written while another program is in front")
except profiletools.NotPossible:
	pass
assert conf.writes == before and rate.read() == 50

# A profile the user turned on by hand counts before every program's profile, and takes every change. Then
# nothing is changed, and the user is told how to turn it off.
conf.createProfile("quiet")
conf.manualActivateProfile("quiet")
assert profiletools.manual() == "quiet"
try:
	profiletools.check("", echo.id)
	raise AssertionError("a setting for a program was allowed under a profile turned on by hand")
except profiletools.NotPossible as e:
	assert "quiet" in str(e) and "Manual deactivate" in str(e), e
conf.manualActivateProfile(None)
assert profiletools.manual() == ""

# Triggers switched off in NVDA: said, and nothing is made.
conf.disableProfileTriggers()
try:
	profiletools.check("", echo.id)
	raise AssertionError("a setting for a program was allowed with triggers switched off")
except profiletools.NotPossible as e:
	assert str(e) == profiles.TRIGGERS_OFF
conf.enableProfileTriggers()
front(word, "Letter.docx - Word")

# An NVDA that keeps nothing on this computer.
conf.canWrite = False
try:
	profiletools.check("", echo.id)
	raise AssertionError("a setting for a program was allowed in an NVDA that cannot keep it")
except profiletools.NotPossible as e:
	assert str(e) == profiles.READ_ONLY
conf.canWrite = True

# NVDA does not turn the new profile on: nothing is left behind, neither the profile nor its trigger.
realEnter = profiletools._enter
profiletools._enter = lambda module: None
try:
	profiletools.activate(word)
	raise AssertionError("a profile that is not on was taken to be on")
except profiletools.NotPossible:
	pass
assert "winword" not in list(conf.listProfiles()) and "app:winword" not in conf.triggersToProfiles
profiletools._enter = realEnter

# A profile of that name is there already and belongs to nothing: another name is taken, and the user's own
# profile is left alone.
conf.createProfile("winword")
conf._files["winword"]["speech"] = {"symbolLevel": 300}
name, created = profiletools.activate(word)
assert (name, created) == ("winword (VisionClaw)", True), name
assert conf.triggersToProfiles["app:winword"] == "winword (VisionClaw)"
assert conf._files["winword"] == {"speech": {"symbolLevel": 300}}

# A trigger whose profile is gone counts as none.
conf.triggersToProfiles["app:ghost"] = "ghost"
assert profiletools.mapped("ghost") is None

# Everywhere, while the program in front has a profile of its own that is on: the write goes into NVDA's normal
# configuration, the program's profile is on again afterwards, and where the program has a value of its own for
# the setting, it keeps it and that is told.
front(notepad, "Untitled - Notepad")
name, created = profiletools.activate(notepad)
profiletools.write(name, rate, 70)
own, byHand, module, facts = profiletools.onTop()
assert (own, byHand) == ("notepad", "") and module is notepad


class Shown(Setting):
	def shown(self, value=None):
		return str(self.read() if value is None else value)

	def parse(self, raw):
		return self.read() + int(raw) if str(raw).startswith("+") else int(raw)


rateShown, levelShown = Shown("speech.fake.rate"), Shown("speech.symbolLevel")
was, before, new, now, kept = profiletools.writeBase(notepad, levelShown, raw="300")
assert (was, before, new, now, kept) == ("100", 100, 300, "300", ""), (was, before, new, now, kept)
assert base["speech"]["symbolLevel"] == 300 and profiletools.top() == "notepad" and levelShown.read() == 300
assert conf.writes[-1] == (None, "speech.symbolLevel", 300)
# "+10" is read against the value everywhere, which is 50, not against Notepad's own 70; and Notepad keeps its 70.
was, before, new, now, kept = profiletools.writeBase(notepad, rateShown, raw="+10")
assert (was, before, new, now, kept) == ("50", 50, 60, "60", "70"), (was, before, new, now, kept)
assert base["speech"]["fake"]["rate"] == 60 and rateShown.read() == 70 and profiletools.top() == "notepad"
# Which programs hold a value of their own for a setting.
profiletools._profileData = lambda name: conf._files[name]
assert profiletools.holders(("speech", "fake", "rate")) == ["Notepad"], profiletools.holders(("speech", "fake", "rate"))
assert profiletools.holders(("speech", "symbolLevel")) == [] and profiletools.holders(("speech", "fake", "rate"), "notepad") == []
assert profiletools.holders(None) == [] and profiletools.holders(("nothing", "here")) == []
# With a profile turned on by hand besides the program's own, the normal configuration cannot be reached: nothing
# is written, and the program's profile is on again.
conf.manualActivateProfile("quiet")
writes = list(conf.writes)
try:
	profiletools.writeBase(notepad, rateShown, raw="20")
	raise AssertionError("the normal configuration was written to under a profile turned on by hand")
except profiletools.NotPossible as e:
	assert str(e) == profiles.OTHER_PROFILE
assert conf.writes == writes and base["speech"]["fake"]["rate"] == 60
conf.manualActivateProfile(None)
assert profiletools.onTop()[0] == "notepad"
base["speech"]["fake"]["rate"], base["speech"]["symbolLevel"] = 50, 100
front(word, "Letter.docx - Word")
conf.deleteProfile("notepad")
front(notepad, "Untitled - Notepad")
profiletools.activate(notepad)
profiletools.write("notepad", echo, False)
profiletools.write("notepad", rate, 70)
front(word, "Letter.docx - Word")

# Waiting for the program to be in front again after a question: at once when it is, given up after a while when
# it never is, and ended when the request is stopped.
assert profiletools.settle(lambda: True) is True
assert profiletools.settle(lambda: False, seconds=0.2) is False
looks = []
assert profiletools.settle(lambda: looks.append(1) or len(looks) >= 3, seconds=2) is True and len(looks) == 3


def stopped():
	raise KeyboardInterrupt()


try:
	profiletools.settle(lambda: False, stopped, seconds=2)
	raise AssertionError("a stopped request went on waiting")
except KeyboardInterrupt:
	pass

# Which programs have settings of their own, with what VisionClaw changed there.
log = changesModule.ChangeLog(harness.os.path.join(harness.ROOT, "tests", "__pycache__", "no-such-folder", "changes.json"))
log._save = lambda: None
log.add("keyboard.speakTypedCharacters", "keyboard speak typed characters", True, False, "on", "off", "x", profile="notepad", program="Notepad")
log.add("speech.symbolLevel", "speech symbol level", 100, 300, "some", "all", "y")
found = profiletools.listed(log.pending())
assert [(app, name) for app, name, _on, _mine in found] == [("notepad", "notepad"), ("winword", "winword (VisionClaw)")], found
assert found[0][3] == ["keyboard speak typed characters from on to off."] and found[1][2] is True, found
assert "only in Notepad" in log.text() and log.text().count("only in") == 1, log.text()

# Removing: for the program in front, for a named one, and for one that has none.
assert profiletools.profileFor("") == ("Word", "winword (VisionClaw)")
assert profiletools.profileFor("Notepad") == ("Notepad", "notepad")
assert profiletools.profileFor("Excel") == ("Excel", None)
profiletools.remove("notepad")
assert "notepad" not in list(conf.listProfiles()) and "app:notepad" not in conf.triggersToProfiles
log.markProfileGone("notepad")
assert [change["setting"] for change in log.pending()] == ["speech.symbolLevel"]
front(notepad, "Untitled - Notepad")
assert profiletools.top() is None and echo.read() is True
assert profiletools.profileFor("") == ("Notepad", None)

print("OK")
