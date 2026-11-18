# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""What the user asks VisionClaw to remember, kept as Markdown files with an index, and the user's library of
documents, looked things up in with everything else. Plain Python: no NVDA, no model.

  python tests/test_memories.py
"""
import os
import tempfile
import types
import zipfile

import harness  # noqa: F401
from visionClaw.claw import library, lookup, memories, orchestrator
from visionClaw.claw import task as taskModule
from visionClaw.claw.knowledge import Knowledge

# --- What is to be remembered, from the user's words ---

assert memories.factOf("remember that my braille display is a Focus 40, please") == "my braille display is a Focus 40"
assert memories.factOf("VisionClaw, please remember: call me Sam") == "call me Sam"
assert memories.factOf("remember to ask me before deleting") == "ask me before deleting"
assert memories.factOf("I'm new to NVDA. How do I read the title of this window?") == "I'm new to NVDA"
assert memories.yours("my braille display is a Focus 40") == "Your braille display is a Focus 40."
assert memories.yours("I am new to NVDA") == "You are new to NVDA."
assert memories.yours("call me Sam") == "You like to be called Sam."
assert memories.yours("always ask me before deleting") == 'You asked: "always ask me before deleting".'
assert memories.yours("the saves are in D:\\Games") == "The saves are in D:\\Games."
assert memories.asksToRemember("please remember that I use a Focus 40")
assert memories.asksToRemember("don't forget that my laptop has no numpad")
assert not memories.asksToRemember("what do you remember about me")
assert not memories.asksToRemember("forget that")
assert memories.asksWhat("what do you remember about me") and memories.asksWhat("open my memories")
assert memories.kindOf("my braille display is a Focus 40") == memories.YOU
assert memories.kindOf("the saves are in D:\\Games") == memories.WHERE
assert memories.kindOf("in this game the map key is M") == memories.PROGRAM
assert memories.kindOf("short answers are best") == memories.LIKES

# --- What is kept without being asked: only what is lasting, and only what nothing else kept ---

assert memories.lasting("I'm new to NVDA, how do I read the title?") == memories.YOU
assert memories.clause("I'm new to NVDA, how do I read the title?", memories.YOU) == "I'm new to NVDA"
assert memories.lasting("from now on, always ask me before deleting anything") == memories.LIKES
assert memories.lasting("how do I read the title?") == ""
assert memories.lasting("forget that I prefer short answers") == ""  # about memories: never kept again
changes = lambda tool: tool == "set_setting"  # noqa: E731
assert memories.worthKeeping("I'm new to NVDA, how do I read the title?", memories.AUTO, [("look_up", True)], changes) == (
	"I'm new to NVDA")
# A setting that was changed is kept by NVDA; a memory would only repeat it.
assert memories.worthKeeping("speak faster from now on", memories.AUTO, [("set_setting", True)], changes) == ""
# The same request, when the change failed, is worth a memory: it says how the user likes things.
assert memories.worthKeeping("speak faster from now on", memories.AUTO, [("set_setting", False)], changes) == (
	"speak faster from now on")
assert memories.worthKeeping("I'm new to NVDA", memories.ASKED, [], changes) == ""
assert memories.worthKeeping("I'm new to NVDA", memories.OFF, [], changes) == ""
assert memories.worthKeeping("remember that I'm new to NVDA", memories.AUTO, [("remember", True)], changes) == ""
assert memories.worthKeeping("what is the time", memories.AUTO, [], changes) == ""
# Kept without being asked only when it is about how this blind user works the computer.
assert memories.worthKeeping("I prefer short answers", memories.AUTO, [], changes) == "I prefer short answers"
assert memories.worthKeeping("never tell me the colour of a button", memories.AUTO, [], changes) == (
	"never tell me the colour of a button")
assert memories.worthKeeping("I use a Focus 40 braille display", memories.AUTO, [], changes) == "I use a Focus 40 braille display"
assert memories.worthKeeping("I prefer tea to coffee", memories.AUTO, [], changes) == ""
assert memories.worthKeeping("from now on I will go to bed early", memories.AUTO, [], changes) == ""

# --- The files: one Markdown file for each memory, and the index ---

folder = os.path.join(tempfile.mkdtemp(), "memories")
kept = memories.Memories(folder)
assert kept.all() == [] and "remembers nothing" in kept.listText()
entry, replaced = kept.add("my braille display is a Focus 40", asked="remember that my braille display is a Focus 40")
assert replaced is None and entry.text() == "Your braille display is a Focus 40." and entry.kind == memories.YOU
text = open(kept.path(entry.name), encoding="utf-8").read()
assert text.startswith("---\nname: your-braille-display-is-a-focus-40\ndescription: Your braille display is a Focus 40.\n"
	"type: you\n"), text
assert 'In your words: "remember that my braille display is a Focus 40"' in text
index = open(os.path.join(folder, memories.INDEX), encoding="utf-8").read()
assert "# What VisionClaw remembers" in index and "- [Your braille display is a Focus 40.](your-braille-display-is-a-focus-40.md)" in index
# The same thing said again replaces the old memory instead of keeping two.
entry2, replaced = kept.add("my braille display is a Brailliant BI 20")
assert replaced is not None and replaced.name == entry.name and len(kept.all()) == 1
assert kept.all()[0].text() == "Your braille display is a Brailliant BI 20."
kept.add("I prefer short answers")
kept.add("in this game the map key is M", program="spacetrader")
assert kept.all()[-1].kind == memories.PROGRAM and kept.all()[-1].text() == "In spacetrader: In this game the map key is M."
assert len(kept.all()) == 3

# A file the user wrote by hand, without the lines at the top, is a memory too; a file changed by hand is read again.
with open(os.path.join(folder, "my-own.md"), "w", encoding="utf-8") as f:
	f.write("My dog is called Rex.\n")
assert any(entry.title == "My dog is called Rex." for entry in kept.all())
os.remove(os.path.join(folder, "my-own.md"))
assert not any(entry.title == "My dog is called Rex." for entry in kept.all())

# --- Found again: with the request whose words are about it, and in the program it is about ---

assert kept.recall("which braille display do I have") == ["Your braille display is a Brailliant BI 20."]
assert kept.recall("open the map", program="spacetrader")[0] == "In spacetrader: In this game the map key is M."
assert kept.recall("what time is it") == []
assert kept.recall("what time is it", program="notepad") == []

# --- Forgetting: by the words, the last one, or all ---

assert [entry.text() for entry in kept.chosen("forget what I said about my braille display")] == [
	"Your braille display is a Brailliant BI 20."]
assert [entry.name for entry in kept.chosen("forget that")] == [kept.all()[-1].name]
assert len(kept.chosen("forget everything")) == 3
assert kept.chosen("forget my favourite colour") == []
assert kept.remove(kept.chosen("forget that")[0].name)
kept.writeIndex()
assert len(kept.all()) == 2 and "map key" not in open(os.path.join(folder, memories.INDEX), encoding="utf-8").read()

# --- The orchestrator: memories given with a request, and kept after it ---

runner = orchestrator.Orchestrator(types.SimpleNamespace(), types.SimpleNamespace(
	get=lambda name: types.SimpleNamespace(changes=name == "set_setting")), lambda q, c: 0)
runner.memories = kept
context = runner._context("which braille display do I have")
assert "The user asked VisionClaw to remember:\n- Your braille display is a Brailliant BI 20." in context, context
task = taskModule.Task("I'm new to NVDA, how do I read the title?")
step = types.SimpleNamespace(tool="look_up", status=taskModule.STEP_DONE)
task.steps = [step]
told = runner._keep(task)
assert told == "VisionClaw will remember this: You're new to NVDA. To make it forget, say forget that.", told
runner.remembering = lambda: memories.ASKED
task = taskModule.Task("I am left-handed")
task.steps = [step]
assert runner._keep(task) == "" and not any("left" in entry.text() for entry in kept.all())
# A memory that cannot be kept never ends a request.
runner.remembering = lambda: memories.AUTO
runner.memories = types.SimpleNamespace(add=lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
task = taskModule.Task("I prefer short answers")
task.steps = [step]
assert runner._keep(task) == ""

# --- The library: the user's own documents, cut into passages ---

shelf = library.Library(os.path.join(tempfile.mkdtemp(), "library"))
shelf.prepare()
assert os.path.isfile(os.path.join(shelf.folder, library.README)) and shelf.documents() == []
assert "library is empty" in shelf.listText()
with open(os.path.join(shelf.folder, "Space Trader manual.txt"), "w", encoding="utf-8") as f:
	f.write("GETTING STARTED\nThe Play button is called Start. Press Alt+S to start a new game.\n\n"
		"TRADING\nPress T to open the market. Buy low and sell high.\n\nSAVING\nSaving is done with Control+S.\n")
with open(os.path.join(shelf.folder, "notes.md"), "w", encoding="utf-8") as f:
	f.write("# My notes\n\n## Mail\nMy mail program is Thunderbird.\n")
os.makedirs(os.path.join(shelf.folder, "web"))
with open(os.path.join(shelf.folder, "web", "help.html"), "w", encoding="utf-8") as f:
	f.write("<html><body><h1>Help</h1><p>Intro</p><h2>Zooming in on the map</h2><p>Press Z to zoom in on the map, and X "
		"to zoom out again.</p></body></html>")
# A Word document, made the way Word writes one, with a heading.
w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
with zipfile.ZipFile(os.path.join(shelf.folder, "Reaper guide.docx"), "w") as archive:
	archive.writestr("word/document.xml", (
		f'<w:document xmlns:w="{w}"><w:body>'
		'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Recording a track</w:t></w:r></w:p>'
		'<w:p><w:r><w:t>Press Control+R to start recording, and Control+R again to stop.</w:t></w:r></w:p>'
		'</w:body></w:document>'))
with open(os.path.join(shelf.folder, "broken.docx"), "w") as f:
	f.write("not a zip file")
documents = {library.nameOf(path): (sections, why) for path, sections, why in shelf.documents()}
assert documents["Space Trader manual"][0][0] == ("GETTING STARTED", "The Play button is called Start. Press Alt+S to start a new game.")
assert len(documents["Space Trader manual"][0]) == 3
assert documents["notes"][0] == [("Mail", "My mail program is Thunderbird.")]
assert documents["help"][0] == [("Zooming in on the map", "Press Z to zoom in on the map, and X to zoom out again.")]
assert documents["Reaper guide"][0] == [("Recording a track", "Press Control+R to start recording, and Control+R again to stop.")]
assert documents["broken"][0] == [] and documents["broken"][1]
listed = shelf.listText()
assert "4 documents" in listed and "Could not be read: broken" in listed, listed

# A plain text without headings is cut at blank lines.
assert library.textSections("One.\n\nTwo.", "x") == [("x", "One. Two.")]
assert library.mentions("Space Trader manual", ["spacetrader", "Space Trader"])
assert not library.mentions("Reaper guide", ["notepad"])

# --- Questions: the library and the memories are asked with everything else ---

pool = shelf.passages(["notepad"]) + lookup.fromMemories(kept.all())
found = lookup.resultText(lookup.about("how do I start a new game in Space Trader", pool))
assert found.startswith("From your library, Space Trader manual: GETTING STARTED. The Play button is called Start."), found
found = lookup.resultText(lookup.about("how do I record a track", pool))
assert "From your library, Reaper guide: Recording a track. Press Control+R" in found, found
found = lookup.resultText(lookup.about("which braille display do I have", pool))
assert found.startswith("From what you asked VisionClaw to remember: Your braille display is a Brailliant BI 20."), found
# A document whose name names the program in front counts as that program's.
mine = shelf.passages(["spacetrader", "Space Trader"])
assert {passage.source for passage in mine if passage.origin.endswith("Space Trader manual")} == {lookup.APP}
assert {passage.source for passage in mine if passage.origin.endswith("Reaper guide")} == {lookup.LIBRARY}
# A changed document is read again, and a deleted one is gone.
os.remove(os.path.join(shelf.folder, "Reaper guide.docx"))
assert "Reaper guide" not in {library.nameOf(path) for path, _s, _w in shelf.documents()}

# --- The notes on accessibility interfaces and on programs are asked only when the question is about them ---

notes = lookup.fromSections(Knowledge().everything())
gatedApi = [passage for passage in notes if passage.gate is not None]
for question in ("how do I press a button", "how do I open a link", "what does this checkbox do"):
	assert not any(passage in lookup.gated(gatedApi, question) for passage in gatedApi if "ARIA" in passage.origin)
apiQuestions = ("what is UI Automation", "what does aria-label do", "how do I turn on the Java Access Bridge")
for question in apiQuestions:
	opened = lookup.gated(gatedApi, question)
	assert opened, question
# The notes on browsers are asked when the user is in a browser, though the question does not say so.
browsers = [passage for passage in notes if passage.origin == "VisionClaw's notes on web browsers"]
if browsers:
	assert lookup.gated(browsers, "how do I reopen a closed tab") == browsers
	assert lookup.gated(browsers, "how do I go back", ["msedge"]) == browsers
	assert lookup.gated(browsers, "how do I go back", ["notepad"]) == []
assert "and what you asked VisionClaw to remember." in lookup.nothingText("how do I bake a cake", memories=True)
assert ", the documents in your library," in lookup.nothingText("how do I bake a cake", library=True, memories=True)

# --- The model that writes an add-on is told the memories, the library and the notes that belong with it ---

coderKept = memories.Memories(os.path.join(tempfile.mkdtemp(), "memories"))
coderKept.add("my NVDA key is Caps Lock")
coderKept.add("in this game the map key is M", program="spacetrader")
coderKept.add("I prefer short answers")
told = library.forCoder(coderKept, shelf, Knowledge(), "a key that reads the map in the game", ["spacetrader", "Space Trader"])
assert told.startswith("\nWhat the user asked VisionClaw to remember:\n- In spacetrader: In this game the map key is M."), told
assert "short answers" not in told
told = library.forCoder(coderKept, shelf, Knowledge(), "announce the UI Automation notification event", [])
assert "About the accessibility interface:\n[UI Automation notification event" in told, told
assert len(told) <= library.CODER_CHARS + 1
# NVDA's own name for the event comes first in that section, so it is inside what the writer is told.
assert "event_UIA_notification(self, obj, nextHandler, displayString=None" in told, told
told = library.forCoder(coderKept, shelf, Knowledge(), "a key that says how much money I have in Space Trader", [])
assert "From the user's library:\nFrom your library, Space Trader manual:" in told, told
# What the library says leads to NVDA's note on it, but only when the passage is about what the heading names.
assert library.nvdaNote(Knowledge(), "MONEY Your money is shown in the status bar of the main window.").startswith(
	"[Reading the status bar of the window in front]\napi.getStatusBar()")
assert library.nvdaNote(Knowledge(), "SAVING Press F5 to save the game.") == ""
assert library.nvdaNote(Knowledge(), "HEALTH Your health is spoken when you press H.") == ""
# Nothing that fits: nothing is added; and a part that cannot be read never stops the add-on.
assert library.forCoder(coderKept, shelf, Knowledge(), "read the clock", []) == ""
assert library.forCoder(types.SimpleNamespace(), None, None, "read the clock") == ""

# --- Which recipe the words suggest ---

from visionClaw.claw import planner  # noqa: E402
for said, recipe in (
		("remember that my braille display is a Focus 40", "remember"), ("don't forget the saves are in D:\\Games", "remember"),
		("call me Sam", "remember"), ("what do you remember about me", "memories"), ("open my memories", "memories"),
		("I'm new to NVDA.", "remember"), ("I'm new to NVDA. How do I read the title of this window?", "explain_keys"),
		("forget that", "forget_memory"), ("forget everything you remember", "forget_memory"),
		("delete some of my memories", "forget_memory"), ("forget the notes on notepad", "forget_notes"),
		("what is in my library", "library"), ("open the library folder", "library"), ("make notes on this program", "learn_app")):
	assert planner.hint(said) == recipe, (said, planner.hint(said))

print("OK")
