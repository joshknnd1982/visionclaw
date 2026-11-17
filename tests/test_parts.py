# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Checks the building blocks: the model catalog and resumable verified downloads, forgiving matching,
the check that generated add-ons must pass, writing and repairing an add-on, storing and packaging one,
and the knowledge base."""
import hashlib
import os
import tempfile
import threading
import zipfile

import harness  # noqa: F401
import rangeserver
from visionClaw import net
from visionClaw.claw import catalog, drivers, match, microaddons, policy, web
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import plainSpeech
from visionClaw.claw.tools import ToolError

# --- The catalog ---

ids = [e["id"] for e in catalog.CATALOG]
assert len(ids) == len(set(ids))
for entry in catalog.CATALOG:
	assert entry["role"] in (VISION, CODER) and entry["files"]
	kinds = [f["kind"] for f in entry["files"]]
	assert kinds.count("model") == 1 and (entry["role"] == CODER or kinds.count("mmproj") == 1), entry["id"]
	for f in entry["files"]:
		assert f["url"].startswith("https://huggingface.co/") and "/resolve/" in f["url"] and "/main/" not in f["url"]
		assert len(f["sha256"]) == 64 and f["size"] > 100 * 2 ** 20
# Every model is offered, whatever the computer: the computer only changes which one is suggested.
assert catalog.recommend(VISION, 8, 0) == "qwen3.5-2b" and catalog.recommend(CODER, 8, 0) == "qwen2.5-coder-1.5b"
assert catalog.recommend(VISION, 64, 0) == "qwen3.5-4b" and catalog.recommend(CODER, 16, 12000) == "qwen3.5-4b-coder"
assert {"qwen2.5-coder-7b", "qwen3.5-9b"} <= set(ids)

# Downloading: a model of two files from a local server, the first download cut off half way.
served = tempfile.mkdtemp()
blobs = {"model.gguf": os.urandom(3 * 2 ** 20 + 123), "mmproj.gguf": os.urandom(2 ** 20)}
for name, data in blobs.items():
	with open(os.path.join(served, name), "wb") as f:
		f.write(data)
base, server = rangeserver.serve(served, failAfterBytes=2 ** 20 + 5)
entry = {
	"id": "test", "dir": "test", "role": VISION, "name": "Test", "small": True, "thinking": False,
	"memoryGb": 1, "maxContext": 4096,
	"files": [
		{"kind": kind, "name": name, "size": len(blobs[name]), "sha256": hashlib.sha256(blobs[name]).hexdigest(),
			"url": f"{base}/{name}"}
		for kind, name in (("model", "model.gguf"), ("mmproj", "mmproj.gguf"))
	],
}
models = catalog.Catalog(tempfile.mkdtemp())
total = catalog.entrySize(entry)
assert not models.isInstalled(entry) and models.missingBytes(entry) == total
try:
	models.download(entry)
	raise AssertionError("the cut-off download should have failed")
except OSError:
	pass
assert 0 < models.missingBytes(entry) < total  # what arrived is kept
progress = []
models.download(entry, lambda done, size: progress.append((done, size)))
assert models.isInstalled(entry) and models.missingBytes(entry) == 0
assert progress[-1] == (total, total) and all(a[0] <= b[0] for a, b in zip(progress, progress[1:]))
model, projector = models.paths(entry)
assert open(model, "rb").read() == blobs["model.gguf"] and open(projector, "rb").read() == blobs["mmproj.gguf"]
# A damaged file is refused.
bad = dict(entry, id="bad", dir="bad", files=[dict(entry["files"][1], sha256="0" * 64)])
try:
	models.download(bad)
	raise AssertionError("a damaged download should have been refused")
except ValueError:
	pass
assert not models.isInstalled(bad)
# Cancelling stops a download.
stop = threading.Event()
stop.set()
other = dict(entry, id="other", dir="other")
try:
	models.download(other, cancel=stop)
	raise AssertionError("a cancelled download should have stopped")
except net.Cancelled:
	pass
# A model that shares its file with another is not downloaded twice, and removing one keeps the shared file.
coder = dict(entry, id="test-coder", role=CODER, files=entry["files"][:1])
assert models.isInstalled(coder) and models.missingBytes(coder) == 0
server.shutdown()
# VisionMate's vision data, where it exists, is offered without a download.
folder = tempfile.mkdtemp()
assert catalog.VISIONMATE_ID not in [e["id"] for e in catalog.Catalog(folder, folder).entries(VISION)]
for name in ("core.bin", "vision.bin"):
	open(os.path.join(folder, name), "wb").close()
reuse = catalog.Catalog(folder, folder)
assert reuse.selected(VISION)["id"] == catalog.VISIONMATE_ID and reuse.paths(reuse.selected(VISION))[0].endswith("core.bin")

# --- Forgiving matching ---

items = ["Space Trader - Main Menu heading", "New Game button", "Load Game button", "Options button", "Quit button"]
assert match.itemIndex("2", items) == 1 and match.itemIndex("item 4.", items) == 3 and match.itemIndex("9", items) is None
assert match.itemIndex("new game", items) == 1 and match.itemIndex("the Quit button", items) == 4
assert match.itemIndex("Optoins", items) == 3 and match.itemIndex("Save", items) is None
assert match.toNumber("80") == 80 and match.toNumber("/80") == 80 and match.toNumber("80%", 50, 0, 100) == 80
assert match.toNumber("+10", 50, 0, 100) == 60 and match.toNumber("-10", 5, 0, 100) == 0
for wrong in ("fast", "250"):
	try:
		match.toNumber(wrong, 50, 0, 100)
		raise AssertionError(wrong)
	except ValueError:
		pass
assert match.toBool("On") is True and match.toBool("disabled") is False and match.toBool("maybe") is None
assert match.toOption("ALL", ["none", "some", "most", "all"]) == "all"
assert match.label("speakTypedWords") == "speak typed words"
assert plainSpeech("Seen:\n- A **game** menu\n- Four buttons") == "Seen: A game menu, Four buttons."

# --- The web: addresses, searches, and the passages of a page that matter ---

assert web.addressIn("please open bbc.co.uk for me") == "bbc.co.uk"
assert web.addressIn("go to https://example.com/a?b=1.") == "https://example.com/a?b=1"
assert web.addressIn("open the BBC website") == ""
assert web.normalizeAddress("bbc.co.uk") == "https://bbc.co.uk" and web.normalizeAddress("http://a.org/x") == "http://a.org/x"
assert web.normalizeAddress("localhost.example:8080/x") == "https://localhost.example:8080/x"
for bad in ("javascript:alert(1)", "file:///c:/windows/system32", "ftp://a.org", "the bbc", "", "data:text/html,x"):
	try:
		web.normalizeAddress(bad)
		raise AssertionError(bad)
	except ValueError:
		pass
assert web.searchWords("Search the web for cheap flights to Rome online.") == "cheap flights to Rome"
assert web.searchWords("look up the weather in Boston") == "the weather in Boston"
assert web.searchWords("google NVDA add-on development") == "NVDA add-on development"
assert web.searchUrl("google", "a b&c") == "https://www.google.com/search?q=a+b%26c"
assert web.searchUrl("nothing", "x").startswith("https://duckduckgo.com/")
assert web.passages("Short page.\n\nTwo lines.", "anything") == "Short page.\nTwo lines."
long = "\n".join(["News today"] + [f"Paragraph {i} talks about football results." for i in range(80)]
	+ ["The library opens at nine and closes at five on weekdays."] + [f"Advert {i} for shoes." for i in range(80)])
found = web.passages(long, "When does the library open?")
assert found.startswith("News today") and "library opens at nine" in found and "..." in found and len(found) <= 1500
assert web.passages(long, "zzzz").startswith("News today") and len(web.passages(long, "zzzz")) <= 1410

# --- Keeping speech and braille alive ---

S, D = drivers.SYNTH, drivers.DISPLAY
assert drivers.judge(S, "espeak", "oneCore", None) == (drivers.FINE, "")
assert drivers.judge(S, "silence", "espeak", None)[0] == drivers.REFUSE
assert drivers.judge(S, "silence", "espeak", "noBraille")[0] == drivers.REFUSE
assert drivers.judge(S, "silence", "espeak", "freedomScientific")[0] == drivers.WARN
assert drivers.judge(D, "noBraille", "espeak", "freedomScientific")[0] == drivers.WARN
assert drivers.judge(D, "noBraille", "silence", "freedomScientific")[0] == drivers.REFUSE
assert drivers.judge(D, "noBraille", None, "freedomScientific")[0] == drivers.REFUSE
assert drivers.judge(D, "freedomScientific", "espeak", "noBraille") == (drivers.FINE, "")
notes = drivers.DriverNotes(os.path.join(tempfile.mkdtemp(), "drivers.json"))
assert notes.warning(S, "sapi5") == "" and drivers.judge(S, "sapi5", "espeak", None, notes)[0] == drivers.FINE
notes.record(S, "sapi5", drivers.FAILED)
notes.record(S, "sapi5", drivers.FAILED)
notes.record(S, "sapi5", drivers.REVERTED)
verdict, why = drivers.judge(S, "sapi5", "espeak", None, notes, "Microsoft Speech API")
assert verdict == drivers.WARN, why
assert why == ("Earlier on this computer, Microsoft Speech API could not be started 2 times and was switched back "
	"once because it was not confirmed to work."), why
notes.record(S, "sapi5", drivers.WORKED)
assert notes.warning(S, "sapi5").endswith("The last time it worked.")
again = drivers.DriverNotes(notes._path)  # kept between sessions
assert again.get(S, "sapi5")["failed"] == 2 and again.problems(S) and not again.problems(D)
assert drivers.judgeVolume(50, None)[0] == drivers.FINE and drivers.judgeVolume(3, None)[0] == drivers.REFUSE
assert drivers.judgeVolume(3, "freedomScientific")[0] == drivers.WARN
assert drivers.kindOf("switch my braille display to Focus") == D and drivers.kindOf("use eSpeak") == S

# --- The check generated add-ons must pass ---

assert microaddons.check(microaddons.TEMPLATE) == []
assert microaddons.gestures(microaddons.TEMPLATE) == [("NVDA+shift+f9", "Says the name of the focused control")]
HEAD = "import globalPluginHandler\nimport ui\n\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n"
for source, expected in (
	("def x(:\n", "Syntax error"),
	("import ui\n", "must define class GlobalPlugin"),
	("import subprocess\n" + HEAD + "\tpass\n", "subprocess is not allowed"),
	("from urllib import request\n" + HEAD + "\tpass\n", "urllib is not allowed"),
	(HEAD + "\tdef script_a(self, gesture):\n\t\topen('x', 'w')\n", "open() is not allowed"),
	(HEAD + "\tdef script_a(self, gesture):\n\t\texec('x')\n", "exec() is not allowed"),
	("import os\n" + HEAD + "\tdef script_a(self, gesture):\n\t\tos.remove('x')\n", "os.remove() is not allowed"),
	(HEAD + "\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message('x')\n", "must call nextHandler()"),
	(HEAD + "\tdef event_gainFocus(self, obj):\n\t\tpass\n", "must take (self, obj, nextHandler)"),
	(HEAD + "\tdef script_a(self):\n\t\tpass\n", "must take exactly (self, gesture)"),
	(HEAD + "\tdef script_a(self, gesture):\n\t\ttones.beep(440, 50)\n", "tones is used but not imported"),
	(HEAD + "\t@script(description='x', gesture='NVDA+k')\n\tdef script_a(self, gesture):\n\t\tpass\n", "must start with kb:"),
):
	problems = microaddons.check(source)
	assert any(expected in p for p in problems), (expected, problems)
assert microaddons.slug("Beep on Links!") == "beep_on_links" and microaddons.slug("9 lives") == "helper_9_lives"
fenced = "Here it is:\n```python\nimport ui\n```\nDone."
assert microaddons.extractCode(fenced) == "import ui\n" and microaddons.extractCode("```python\nimport ui\n") == "import ui\n"


# --- Writing an add-on: the coder writes, the check finds a fault, the coder repairs, the other model reviews ---

class FakeLLM:
	def __init__(self, texts, verdicts):
		self.texts, self.verdicts, self.calls = list(texts), list(verdicts), []

	def text(self, role, system, user, **options):
		self.calls.append((role, user))
		return self.texts.pop(0)

	def json(self, role, system, user, schema, **options):
		self.calls.append((role, user))
		return self.verdicts.pop(0)


# A fault that plain code cannot correct, so the coder model has to: something that is not allowed.
broken = ("```python\n" + HEAD
	+ "\tdef event_gainFocus(self, obj, nextHandler):\n\t\texec('x')\n\t\tui.message('link')\n\t\tnextHandler()\n```")
fixed = "```python\n" + HEAD + "\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message('link')\n\t\tnextHandler()\n```"
params = policy.select({"complexity": "complex", "needs_code": True})
task = taskModule.Task("write an add-on")
llm = FakeLLM([broken, fixed], [{"ok": True, "problem": ""}])
source = microaddons.write(llm, task, "say link when a link gets the focus, anywhere", "Program: firefox", "", params, CODER, VISION)
assert microaddons.check(source) == [] and "nextHandler()" in source
assert [role for role, _u in llm.calls] == [CODER, CODER, VISION]
assert "exec() is not allowed" in llm.calls[1][1]
# The reviewing model finds a fault: the coder is sent back once more.
llm = FakeLLM([fixed, fixed], [{"ok": False, "problem": "It speaks for every control, not only links."}, {"ok": True, "problem": ""}])
microaddons.write(llm, task, "say link when a link gets the focus, anywhere", "", "", params, CODER, VISION)
assert "not only links" in llm.calls[2][1]
# The checks decide; the reviewing model only advises. Code that passes every check is kept even if the
# reviewer still doubts it when the tries are used up, and the doubt is kept for the user.
no = {"ok": False, "problem": "It might be too loud."}
llm = FakeLLM([fixed] * 10, [no, no])
kept = microaddons.write(llm, task, "say link when a link gets the focus, anywhere", "", "", params, CODER, VISION)
assert microaddons.check(kept) == [] and task.codeDoubt == "It might be too loud."
# Code that never passes is refused, not run.
llm = FakeLLM([broken] * 10, [])
try:
	microaddons.write(llm, task, "x", "", "", params, CODER, VISION)
	raise AssertionError("code that fails the check must be refused")
except ToolError as e:
	assert "exec() is not allowed" in str(e)

# --- Does the code do what was asked, and only that? ---

KEY_ONLY = microaddons.EXAMPLE_KEY
EVENT_ONLY = microaddons.EXAMPLE_EVENT
assert microaddons.check(KEY_ONLY) == [] and microaddons.check(EVENT_ONLY) == []
assert microaddons.checkAgainst(KEY_ONLY, "Say the name of the focused control when I press NVDA+shift+F9") == []
assert microaddons.checkAgainst(EVENT_ONLY, "Beep when a button gets the focus") == []
# Something that happens by itself, though only a key was asked for.
found = microaddons.checkAgainst(microaddons.TEMPLATE, "Say hello when I press NVDA+shift+H")
assert any("does not ask for anything to happen by itself. Remove event_gainFocus" in p for p in found), found
assert any("only for the program notepad" in p for p in found), found
# A key nobody asked for.
found = microaddons.checkAgainst(microaddons.TEMPLATE, "Beep whenever a link gets the focus")
assert any("does not ask for a key command. Remove script_sayName" in p for p in found), found
# A program limit is fine when the request names the program, or says "this program" and the facts name it.
assert not any("only for the program" in p for p in microaddons.checkAgainst(
	microaddons.TEMPLATE, "In Notepad, say text area when the focus moves, and the name on NVDA+shift+F9"))
assert not any("only for the program" in p for p in microaddons.checkAgainst(
	microaddons.TEMPLATE, "In this program, announce text area when the focus moves; key NVDA+shift+F9",
	"Program: notepad. Window title: Untitled."))
# A control's kind compared with a text never matches.
wrongRole = EVENT_ONLY.replace("obj.role == controlTypes.Role.BUTTON", "obj.role == \"link\"")
found = microaddons.checkAgainst(wrongRole, "Beep when a link gets the focus")
assert any("controlTypes.Role.LINK" in p for p in found), found
assert any("does nothing" in p for p in microaddons.checkAgainst(HEAD + "\tpass\n", "Say hello on NVDA+shift+H"))

# --- What plain code corrects, without asking a model ---

# An event nobody asked for is taken out; the key command stays, and the result passes every check.
tidied = microaddons.tidy(microaddons.TEMPLATE, "Say the name of the focused control when I press NVDA+shift+F9")
assert "event_gainFocus" not in tidied and "script_sayName" in tidied and microaddons.check(tidied) == []
assert microaddons.checkAgainst(tidied, "Say the name of the focused control when I press NVDA+shift+F9") == []
# A key nobody asked for is taken out, with its decorator; the event stays.
tidied = microaddons.tidy(microaddons.TEMPLATE, "Say text area whenever the focus moves in Notepad")
assert "script_sayName" not in tidied and "@script" not in tidied and "event_gainFocus" in tidied
assert microaddons.check(tidied) == []
# "when I press" asks for a key, not for something that happens by itself.
assert not microaddons._wantsEvent("Say hello when I press NVDA+shift+H")
assert microaddons._wantsEvent("Say hello when a window opens") and microaddons._wantsEvent("Beep whenever a link gets the focus")
# A control's kind written as a text is rewritten the way NVDA needs it, and the import is added.
noImport = EVENT_ONLY.replace("import controlTypes\n", "").replace("obj.role == controlTypes.Role.BUTTON", "obj.role == 'link'")
tidied = microaddons.tidy(noImport, "Beep when a link gets the focus")
assert "obj.role == controlTypes.Role.LINK" in tidied and tidied.startswith("import controlTypes\n"), tidied
assert microaddons.check(tidied) == [] and microaddons.checkAgainst(tidied, "Beep when a link gets the focus") == []
# Code that would be left with nothing is not touched, so that the coder is told what is wrong instead.
assert microaddons.tidy(KEY_ONLY, "Beep when a link gets the focus") == KEY_ONLY
# A request for one program, and code that works everywhere: the limit is asked for.
found = microaddons.checkAgainst(KEY_ONLY, "In notepad, say the name on NVDA+shift+F9", "Program: notepad. Window title: x.")
assert any("only for the program notepad" in p and "appName" in p for p in found), found

# ... and plain code puts the limit in: in another program the key is passed on, the event goes to NVDA.
tidied = microaddons.tidy(KEY_ONLY, "In notepad, say the name on NVDA+shift+F9", "Program: notepad. Window title: x.")
assert 'if api.getFocusObject().appModule.appName != "notepad":' in tidied and "gesture.send()" in tidied
assert microaddons.check(tidied) == []
assert microaddons.checkAgainst(tidied, "In notepad, say the name on NVDA+shift+F9", "Program: notepad.") == []
spaces = EVENT_ONLY.replace("\t", "    ")
tidied = microaddons.tidy(spaces, "Beep when a button gets the focus in notepad", "Program: notepad.")
assert '        if getattr(getattr(obj, "appModule", None), "appName", None) != "notepad":\n            nextHandler()' in tidied
assert tidied.startswith("import api\n") and microaddons.check(tidied) == []
# A request that names no program gets no limit.
assert microaddons.tidy(KEY_ONLY, "Say the name on NVDA+shift+F9", "Program: notepad.") == KEY_ONLY

# A forgotten import is added, and an event that forgot to pass the event on is made to.
forgetful = (
	"import globalPluginHandler\n\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\n"
	"\tdef event_gainFocus(self, obj, nextHandler):\n\t\tif obj.role == controlTypes.Role.LINK:\n\t\t\ttones.beep(880, 80)\n")
assert len(microaddons.check(forgetful)) == 3
tidied = microaddons.tidy(forgetful, "Beep when a link gets the focus")
assert microaddons.check(tidied) == [] and tidied.rstrip().endswith("\t\tnextHandler()"), tidied
assert tidied.startswith("import tones\nimport controlTypes\n"), tidied
assert microaddons.tidy(EVENT_ONLY, "Beep when a button gets the focus") == EVENT_ONLY  # nothing to correct

# A file cut off in the middle, because the model went on too long, is cut back to a complete program.
cutOff = KEY_ONLY + "\t\tif obj.role == 1:\n\t\t\tui.message(\"one\")\n\t\tif obj.role == 2:\n"
assert any("Syntax error" in p for p in microaddons.check(cutOff))
saved = microaddons.salvage(cutOff)
assert microaddons.check(saved) == [] and "ui.message(\"one\")" in saved and "obj.role == 2" not in saved
assert microaddons.salvage(KEY_ONLY) == KEY_ONLY and microaddons.salvage("def x(:") == "def x(:"
assert microaddons.check(microaddons.tidy(cutOff, "Say the name on NVDA+shift+F9")) == []

# A model that writes one line over and over is stopped, and the repeated lines are dropped.
from visionClaw.engine import CodeGuard  # noqa: E402
guard = CodeGuard()
assert guard.feed("import ui\n\n\ndef a():\n\tpass\n") and guard.feed("\n\ndef b():\n\tpass\n")
stopped = [guard.feed("\t# Say the time\n") for _ in range(6)]
assert stopped[:4] == [True] * 4 and stopped[4] is False
assert guard.finish().count("# Say the time") == 0 and guard.finish().startswith("import ui")
guard = CodeGuard()
assert all(guard.feed(f"x{i} = {i}\n") for i in range(CodeGuard.MAX_LINES)) and not guard.feed("one = 1\n")

# --- What an add-on does, in plain words, found by checking its code ---

facts = microaddons.describe(microaddons.TEMPLATE)
assert "It adds the key NVDA+shift+f9: Says the name of the focused control." in facts, facts
assert "It acts by itself when the focus moves to another control." in facts
assert "It works only in: notepad." in facts and "It can say: text area." in facts, facts
plain = microaddons.describe(HEAD + "\tdef script_a(self, gesture):\n\t\ttones.beep(440, 50)\n")
assert "It is not limited to one program." in plain and "It beeps." in plain, plain
assert microaddons.describe("def x(:") == []

# --- Debugging an add-on: the error goes to the coder, and the result is checked and reviewed again ---

llm = FakeLLM([broken, fixed], [{"ok": True, "problem": ""}])
problems = ["When it ran in NVDA, event_gainFocus failed with AttributeError: 'NoneType' object has no attribute 'name'."]
corrected = microaddons.fix(llm, task, "say link when a link gets the focus, anywhere", source, problems, "Check for None.", params, CODER, VISION)
assert microaddons.check(corrected) == [] and [role for role, _u in llm.calls] == [CODER, CODER, VISION]
assert "AttributeError" in llm.calls[0][1] and "Check for None." in llm.calls[0][1] and "Find the cause" in llm.calls[0][1]
assert "exec() is not allowed" in llm.calls[1][1]  # the corrected file is checked like a new one

# --- Keeping and packaging add-ons ---

store = microaddons.Store(tempfile.mkdtemp())
store.save("Link Beeper", source, "say link when a link gets the focus, anywhere")
assert [m["name"] for m in store.list()] == ["link_beeper"] and store.source("Link Beeper") == source
assert store.setEnabled("link_beeper", False) and store.meta("link_beeper")["enabled"] is False
package = store.package("link_beeper", tempfile.mkdtemp())
with zipfile.ZipFile(package) as z:
	assert sorted(z.namelist()) == ["globalPlugins/visionClaw_link_beeper.py", "manifest.ini"]
	manifest = z.read("manifest.ini").decode()
	assert "name = visionClaw_link_beeper" in manifest and "minimumNVDAVersion = 2024.1" in manifest
assert store.remove("link_beeper") and store.list() == [] and not store.remove("link_beeper")

# --- The knowledge base ---

knowledge = Knowledge()
assert knowledge.count() >= 25
for query, expected in (
	("hotkey key command script gesture", "Key commands"),
	("react when the focus moves to a control", "Events, reacting when focus moves"),
	("button without a name", "Unlabelled buttons and icons"),
	("game that NVDA cannot read", "Games"),
	("click the mouse at a position", "Clicking the mouse"),
):
	titles = [title for title, _body, _source in knowledge.search(query, limit=3)]
	assert any(expected in title for title in titles), (query, titles)
assert knowledge.text("zzzz qqqq") == ""
knowledge.addSource("guide", lambda: [("Screen curtain", "The screen curtain makes the screen black for privacy.", "guide")])
assert "privacy" in knowledge.text("screen curtain black")
print("OK")
