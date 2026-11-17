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
from visionClaw.claw import catalog, match, microaddons, policy
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


broken = "```python\n" + HEAD + "\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message('link')\n```"
fixed = "```python\n" + HEAD + "\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message('link')\n\t\tnextHandler()\n```"
params = policy.select({"complexity": "complex", "needs_code": True})
task = taskModule.Task("write an add-on")
llm = FakeLLM([broken, fixed], [{"ok": True, "problem": ""}])
source = microaddons.write(llm, task, "say link when a link gets the focus", "Program: firefox", "", params, CODER, VISION)
assert microaddons.check(source) == [] and "nextHandler()" in source
assert [role for role, _u in llm.calls] == [CODER, CODER, VISION]
assert "must call nextHandler()" in llm.calls[1][1]
# The reviewing model finds a fault: the coder is sent back once more.
llm = FakeLLM([fixed, fixed], [{"ok": False, "problem": "It speaks for every control, not only links."}, {"ok": True, "problem": ""}])
microaddons.write(llm, task, "say link when a link gets the focus", "", "", params, CODER, VISION)
assert "not only links" in llm.calls[2][1]
# Code that never passes is refused, not run.
llm = FakeLLM([broken] * 10, [])
try:
	microaddons.write(llm, task, "x", "", "", params, CODER, VISION)
	raise AssertionError("code that fails the check must be refused")
except ToolError as e:
	assert "nextHandler" in str(e)

# --- Keeping and packaging add-ons ---

store = microaddons.Store(tempfile.mkdtemp())
store.save("Link Beeper", source, "say link when a link gets the focus")
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
