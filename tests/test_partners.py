# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Working together with the JAWS Migration Assistant and ClassicSpeech (claw/partners.py, partnertools.py): what
the user's words ask of each, that neither job is offered when its add-on is not running, and the two tools
against stand-ins for the add-ons. The stand-ins have the names, the shapes and the behaviour that the add-ons'
own source has (jawsMigrator 1.63 and ClassicSpeech 1.16, read on 2026-11-18); neither add-on is installed on the
computer these tests were written on, so the real ones were never called. Plain Python.

  python tests/test_partners.py
"""
import builtins
import importlib
import sys
import types

import harness  # noqa: F401
from visionClaw.claw import partners, planner, router

P = partners

# --- What the words ask ---

for said, wish in {
		"What is JAWS's Insert+F7 in NVDA?": {"what": P.KEY, "key": "insert+f7"},
		"what does the jaws key insert f7 do in nvda": {"what": P.KEY, "key": "insert+f7"},
		"what is jaws key caps lock+t": {"what": P.KEY, "key": "capslock+t"},
		"what does jaws control+insert+b do": {"what": P.KEY, "key": "control+insert+b"},
		"In JAWS I press Insert+Up Arrow. What is that here?": {"what": P.KEY, "key": "insert+uparrow"},
		"What is the JAWS say line command in NVDA?": {"what": P.COMMAND, "words": "say line"},
		"what did the JAWS migration bring over": {"what": P.INFO},
		"which commands does the JAWS layer have": {"what": P.INFO}}.items():
	assert P.jawsWish(said) == wish, (said, P.jawsWish(said))
for said in ("what is insert+f7", "make the voice slower", "open notepad"):
	assert P.jawsWish(said) is None, said
# A question about an idea of JAWS's, or from someone who says they come from JAWS, is no question about a
# keystroke or a command: it is looked up as before.
for said in (
		"I'm coming from JAWS. What is the JAWS cursor called in NVDA?", "I come from JAWS. How do I read the title of this window?",
		"Is NVDA like JAWS?", "What did JAWS call browse mode?"):
	assert P.jawsWish(said) is None, (said, P.jawsWish(said))
for said, wish in {
		"set ClassicSpeech to advanced": {"what": P.LEVEL, "level": "Advanced"},
		"set the verbosity to beginner": {"what": P.LEVEL, "level": "Beginner"},
		"say less about each control with ClassicSpeech": {"what": P.LEVEL, "step": 1},
		"ClassicSpeech should say more": {"what": P.LEVEL, "step": -1},
		"which speech schemes do I have": {"what": P.SCHEMES},
		"turn sound schemes off": {"what": P.SCHEMES_ON, "on": False},
		"switch the speech and sound schemes on": {"what": P.SCHEMES_ON, "on": True},
		"next scheme": {"what": P.NEXT},
		"switch to the scheme JAWS Sounds (from JAWS)": {"what": P.SCHEME, "name": "JAWS Sounds (from JAWS)"},
		"what can ClassicSpeech do": {"what": P.INFO}}.items():
	assert P.classicWish(said) == wish, (said, P.classicWish(said))
assert P.classicWish("open voice profiles") == {
	"what": P.OPEN, "script": "script_openClassicSpeechVoiceProfiles", "said": "ClassicSpeech's Voice Profiles"}
assert P.classicWish("open the speech and sound schemes")["script"] == "script_openClassicSpeechSchemes"
assert P.classicWish("open ClassicSpeech settings")["script"] == "script_openClassicSpeechSettings"
for said in ("make the voice slower", "change the voice", "what is on my screen", "which voices do I have"):
	assert P.classicWish(said) is None, said
SCHEMES = ["Default", "JAWS Sounds (from JAWS)", "Classic", "Quiet web"]
assert P.pickName("JAWS Sounds (from JAWS)", SCHEMES) == "JAWS Sounds (from JAWS)" and P.pickName("the quiet web one", SCHEMES) == "Quiet web"
assert P.pickName("classic", SCHEMES) == "Classic" and P.pickName("something else", SCHEMES) is None
assert P.nextLevel("Beginner", 1) == "Intermediate" and P.nextLevel("Advanced", 1) is None and P.nextLevel("Beginner", -1) is None
NAMES = {"sayline": "Report the current line", "saywindowtitle": "Report the title of the window", "movetonextheading": "Move to the next heading"}
assert P.matchCommand("say line", NAMES) == ["sayline"] and P.matchCommand("next heading", NAMES) == ["movetonextheading"]
assert P.matchCommand("window title", NAMES) == ["saywindowtitle"] and P.matchCommand("fly to the moon", NAMES) == []

# --- Offered only while the add-on is running ---


class _Registry:
	def has(self, names):
		return True

	def get(self, name):
		return object()


JAWS_ASKED, CLASSIC_ASKED = "What is JAWS's Insert+F7 in NVDA?", "which speech schemes do I have"
P.setInstalled([])
assert not P.has(P.JAWS) and not P.has(P.CLASSIC)
assert planner.hint(JAWS_ASKED) != "jaws_help" and planner.hint(CLASSIC_ASKED) != "classic_speech"
for said in (JAWS_ASKED, CLASSIC_ASKED, "set ClassicSpeech to advanced"):
	offered = planner.offered(said, _Registry(), {router.WEB: False})
	assert "jaws_help" not in offered and "classic_speech" not in offered, (said, offered)
assert planner.fitted("classic_speech", CLASSIC_ASKED, "nvda_question") == "nvda_question"
P.setInstalled([P.JAWS, P.CLASSIC, "somethingElse"])
assert P.has(P.JAWS) and P.has(P.CLASSIC) and not P.has("somethingElse")
assert planner.hint(JAWS_ASKED) == "jaws_help" and planner.hint(CLASSIC_ASKED) == "classic_speech"
assert "jaws_help" in planner.offered(JAWS_ASKED, _Registry(), {}) and "classic_speech" in planner.offered(CLASSIC_ASKED, _Registry(), {})
assert planner.hint("I'm coming from JAWS. What is the JAWS cursor called in NVDA?") != "jaws_help"
# VisionClaw's notes on the two add-ons are asked about a JAWS keystroke or command, not about JAWS as such.
from visionClaw.claw import lookup
for said, wanted in (
		("I'm coming from JAWS. What is the JAWS cursor called in NVDA?", False),
		("Is NVDA like JAWS?", False),
		("What is JAWS's Insert+F7 in NVDA?", True),
		("What is the JAWS say line command in NVDA?", True),
		("What does the JAWS Migration Assistant do?", True),
		("How do I change a setting only in this program?", True),
		("What is ClassicSpeech?", True)):
	assert bool(lookup._ASKING_NOTES.search(said)) == wanted, said
# NVDA's own voice stays a setting of NVDA, with both add-ons running.
assert planner.hint("make the voice slower") == "change_setting" and planner.hint("open notepad") == "open_thing"
for said in ("make the voice slower", "what is on my screen"):
	offered = planner.offered(said, _Registry(), {})
	assert "jaws_help" not in offered and "classic_speech" not in offered, (said, offered)

# --- The tools, against stand-ins for the two add-ons ---

logged = []
logHandler = types.ModuleType("logHandler")
logHandler.log = types.SimpleNamespace(**{name: (lambda *a, **k: logged.append(a[0])) for name in ("debug", "debugWarning", "info", "warning", "error")})
conf = {"classicSpeech": {"defaultProfile": "Beginner"}}
called = []
sys.modules.update({
	"logHandler": logHandler, "addonHandler": types.SimpleNamespace(initTranslation=lambda: None),
	"config": types.SimpleNamespace(conf=conf), "wx": types.SimpleNamespace(CallAfter=lambda fn, *args: fn(*args)),
	"inputCore": types.SimpleNamespace(normalizeGestureIdentifier=lambda ident: ident.lower()),
	"globalPluginHandler": types.SimpleNamespace(runningPlugins=set())})
builtins._ = lambda text: text
partnertools = importlib.import_module("visionClaw.partnertools")
running = sys.modules["globalPluginHandler"].runningPlugins


def pluginClass(module, **members):
	cls = type("GlobalPlugin", (), members)
	cls.__module__ = module
	return cls


# ClassicSpeech, as its source has it.
schemeState = {"enabled": True, "activeScheme": "Default"}


class SchemeStore:
	def set_active_scheme(self, name):
		if name not in SCHEMES:
			raise KeyError(name)
		self._name = name

	def apply(self):
		schemeState["activeScheme"] = self._name


store = types.ModuleType(partnertools.STORE_MODULE)
store.schemes_root = lambda: "root"
store.load_scheme_folders = lambda root: ({name: {} for name in SCHEMES}, {})
store.runtime_data = lambda: types.SimpleNamespace(data=dict(schemeState))
store.set_schemes_enabled = lambda on: schemeState.__setitem__("enabled", bool(on))
store.SchemeStore = SchemeStore
sys.modules[partnertools.STORE_MODULE] = store
classic = pluginClass(
	partnertools.CLASSIC_MODULE,
	script_openClassicSpeechVoiceProfiles=lambda self, gesture: called.append("voice profiles"),
	script_openClassicSpeechSchemes=lambda self, gesture: called.append("schemes"))()
classic.processor = types.SimpleNamespace(set_profile=lambda name: conf["classicSpeech"].__setitem__("defaultProfile", name))

# The JAWS Migration Assistant, as its source has it.
keyMap = types.ModuleType(partnertools.JAWS_MODULE + ".jawsKeyMap")
keyMap.SCRIPT_MAP = {
	"sayline": ("globalCommands", "GlobalCommands", "reportCurrentLine", "Report the current line; twice spells it"),
	"selectalink": ("browseMode", "BrowseModeDocumentTreeInterceptor", "elementsList", "Open the Elements List")}
keyMap.QUICK_NAV_MAP = {"movetonextheading": ("browseMode", "BrowseModeTreeInterceptor", "nextHeading", "Move to the next heading")}
keyMap.getNvdaTargets = lambda script, jawsKey=None: tuple(
	target for target in [keyMap.SCRIPT_MAP.get(script.lower()) or keyMap.QUICK_NAV_MAP.get(script.lower())] if target)
keyMap.jawsKeyToNvdaGesture = lambda key, layout: None if "bogus" in key else (
	("kb(%s):" % layout if layout in ("desktop", "laptop") else "kb:") + "+".join("NVDA" if part in ("insert", "jawskey", "capslock") else part for part in key.split("+")))
docs = types.ModuleType(partnertools.JAWS_MODULE + ".jawsDocs")
docs.describe = lambda found, script: found.get(script.lower(), script)
state = types.ModuleType(partnertools.JAWS_MODULE + ".state")
last = {"when": "2026-11-07T03:52:53", "jaws": "JAWS 2027", "target": "normal configuration"}
state.get = lambda key: last if key == "lastMigration" else None
migratorModule = types.ModuleType(partnertools.JAWS_MODULE)
migratorModule.LAYER_COMMANDS = (
	(("kb:m",), "openAssistant", "M", "open the migration assistant."),
	(("kb:h",), "showSpeechHistory", "H", "what NVDA said, the most recent last, as JAWS's speech history."))
sys.modules.update({
	partnertools.JAWS_MODULE: migratorModule, partnertools.JAWS_MODULE + ".jawsKeyMap": keyMap,
	partnertools.JAWS_MODULE + ".jawsDocs": docs, partnertools.JAWS_MODULE + ".state": state})
reverse = {"kb(desktop):nvda+f7": [("Insert+F7", "SelectALink", "Desktop Keys")], "kb:nvda+uparrow": [("JAWSKey+UpArrow", "SayLine", "Common Keys")]}
keymap = {"value": ("jaws", reverse, {"selectalink": "Displays a list of links on the page", "sayline": "Says the current line"}, "desktop", {})}
migrator = pluginClass(partnertools.JAWS_MODULE, _jawsKeymap=lambda self: keymap["value"])()

# VisionClaw's side: its tools, its record of changes, NVDA's commands with their keys.
toolsMade, changes, questions = {}, [], []
answer = {"yes": True}


class No(Exception):
	pass


def confirm(question):
	questions.append(question)
	if not answer["yes"]:
		raise No()


vc = types.SimpleNamespace(changes=types.SimpleNamespace(
	add=lambda *args, **kwargs: changes.append(args), markUndone=lambda change: changes.append(("undone", change["setting"]))))
command = lambda script, keys, source="globalCommands": types.SimpleNamespace(  # noqa: E731
	scriptName=script, keys=keys, source=source, line=lambda: f"{script}: Keys: {' or '.join(keys)}.")
COMMANDS = [
	command("reportCurrentLine", ["NVDA+upArrow", "NVDA+l"]), command("elementsList", ["NVDA+f7"]),
	command("pageSummary", ["NVDA+shift+u"], partnertools.CLASSIC_MODULE)]
partnertools.register(
	lambda name, description, fn, fields=None, **options: toolsMade.__setitem__(name, (fn, options)), vc,
	lambda description, **extra: dict({"type": "string"}, **extra), lambda fn, *args: fn(*args), confirm, lambda: COMMANDS)
task = types.SimpleNamespace(request="")
classicSpeech, jawsHelp = toolsMade["classic_speech"][0], toolsMade["jaws_help"][0]
assert toolsMade["jaws_help"][1].get("looks") and not toolsMade["classic_speech"][1].get("looks")

# Neither is running: said, with where it is from, and nothing else happens.
assert partnertools.refresh() == [] and not P.has(P.JAWS)
assert classicSpeech(task, "set ClassicSpeech to advanced") == P.CLASSIC_MISSING and jawsHelp(task, JAWS_ASKED) == P.JAWS_MISSING
running.update({classic, migrator})
assert sorted(partnertools.refresh()) == ["ClassicSpeech", "jawsMigrator"] and P.has(P.JAWS) and P.has(P.CLASSIC)

# ClassicSpeech: the verbosity level, asked about, done with its own call, and written down so it can be put back.
said = classicSpeech(task, "set ClassicSpeech to advanced")
assert said == "ClassicSpeech's verbosity level was Beginner and is now Advanced. " + P.LEVEL_SAYS["Advanced"], said
assert conf["classicSpeech"]["defaultProfile"] == "Advanced" and questions[-1].startswith("Change ClassicSpeech's verbosity level from Beginner to Advanced?")
assert changes[-1][:6] == ("classicspeech:level", "ClassicSpeech's verbosity level", "Beginner", "Advanced", "Beginner", "Advanced")
assert classicSpeech(task, "say less with ClassicSpeech").startswith("ClassicSpeech's verbosity level is Advanced already, and there is none beyond it.")
said = classicSpeech(task, "ClassicSpeech should say more")
assert "was Advanced and is now Intermediate" in said and conf["classicSpeech"]["defaultProfile"] == "Intermediate", said
# A no changes nothing.
answer["yes"] = False
try:
	classicSpeech(task, "set ClassicSpeech to beginner")
	raise AssertionError("the level was changed after a no")
except No:
	assert conf["classicSpeech"]["defaultProfile"] == "Intermediate"
answer["yes"] = True
# Schemes: listed, switched by name, the next one, turned off; a name that is none of them changes nothing.
said = classicSpeech(task, "which speech schemes do I have")
assert said.startswith("Speech and sound schemes are on. The scheme in use is Default. ClassicSpeech has 4: Default, JAWS Sounds (from JAWS), Classic, Quiet web."), said
said = classicSpeech(task, "switch to the scheme JAWS Sounds (from JAWS)")
assert said == "ClassicSpeech's speech and sound scheme was Default and is now JAWS Sounds (from JAWS).", said
assert schemeState["activeScheme"] == "JAWS Sounds (from JAWS)" and changes[-1][0] == "classicspeech:scheme"
assert classicSpeech(task, "next scheme").endswith("is now Classic.") and schemeState["activeScheme"] == "Classic"
said = classicSpeech(task, "switch to the scheme Loud")
assert said.startswith("VisionClaw could not tell which scheme you mean. ClassicSpeech has: Default,") and schemeState["activeScheme"] == "Classic"
said = classicSpeech(task, "turn sound schemes off")
assert said == "ClassicSpeech's speech and sound schemes are now off." and schemeState["enabled"] is False
assert classicSpeech(task, "turn sound schemes off") == "Speech and sound schemes are off already."
# Its windows are opened with its own commands.
assert classicSpeech(task, "open voice profiles") == "Opened ClassicSpeech's Voice Profiles." and called == ["voice profiles"]
# How it is set, with its commands that have keys.
said = classicSpeech(task, "what can ClassicSpeech do")
assert "Its verbosity level is Intermediate" in said and "Speech and sound schemes are off, and the scheme in use is Classic." in said
assert "pageSummary: Keys: NVDA+shift+u." in said, said
# Put back, each with ClassicSpeech's own call.
undo = lambda kind, old, shown: partnertools.undoClassic(vc, {  # noqa: E731
	"setting": "classicspeech:" + kind, "label": "ClassicSpeech's " + kind, "old": old, "oldShown": shown}, confirm)
assert undo("level", "Beginner", "Beginner").endswith("is back to Beginner, as it was before.") and conf["classicSpeech"]["defaultProfile"] == "Beginner"
assert undo("scheme", "Default", "Default") and schemeState["activeScheme"] == "Default"
assert undo("schemes", True, "on") and schemeState["enabled"] is True
# A newer ClassicSpeech that keeps the level another way: nothing is changed, and that is said.
classic.processor = types.SimpleNamespace()
assert classicSpeech(task, "set ClassicSpeech to advanced") == P.CLASSIC_CHANGED and conf["classicSpeech"]["defaultProfile"] == "Beginner"

# The JAWS Migration Assistant: a JAWS keystroke, from JAWS's own key map through to NVDA's command and its keys.
said = jawsHelp(task, "What is JAWS's Insert+F7 in NVDA?")
assert said == "In JAWS, Insert+F7 is: Displays a list of links on the page. In NVDA that is: Open the Elements List, with NVDA+f7.", said
said = jawsHelp(task, "In JAWS I press Insert+Up Arrow. What is that here?")
assert said == "In JAWS, Insert+Uparrow is: Says the current line. In NVDA that is: Report the current line; twice spells it, with NVDA+upArrow or NVDA+l.", said
# A key JAWS's map has nothing for, and one the assistant does not know.
assert jawsHelp(task, "what does jaws insert+f2 do").startswith("JAWS's own key map on this computer has nothing for Insert+F2")
# A JAWS command by its name: needs no JAWS on the computer.
said = jawsHelp(task, "What is the JAWS say line command in NVDA?")
assert said == "JAWS's command sayline: in NVDA that is: Report the current line; twice spells it, with NVDA+upArrow or NVDA+l.", said
assert jawsHelp(task, "what is the jaws next heading command").startswith("JAWS's command movetonextheading: in NVDA that is: Move to the next heading, which has no key of its own in NVDA.")
assert jawsHelp(task, "what is the jaws frobnicate command").startswith("The JAWS Migration Assistant knows no JAWS command that fits these words")
# What was brought over, and the keys of its layer.
said = jawsHelp(task, "what did the JAWS migration bring over")
assert "Its last migration was on 2026-11-07, from JAWS 2027, into normal configuration." in said, said
assert "After NVDA+Shift+J, these keys: M: open the migration assistant. H: what NVDA said, the most recent last, as JAWS's speech history." in said
# No JAWS on this computer: said, with the assistant's own helper named.
keymap["value"] = None
assert jawsHelp(task, JAWS_ASKED) == P.NO_KEYMAP
# A newer assistant that keeps its key map another way: said, and nothing breaks.
del type(migrator)._jawsKeymap
assert jawsHelp(task, JAWS_ASKED).startswith("This version of the JAWS Migration Assistant keeps that in another way")
running.clear()
assert partnertools.refresh() == []

print("OK")
