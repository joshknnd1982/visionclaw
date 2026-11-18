# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The downloaded developer guides put to use, the add-ons installed in NVDA, and NVDA Coach. Plain Python:
no NVDA, no model, nothing online.

What is checked: a code example of a guide keeps its indentation and its comments are no headings; a guide is
read as plain sentences without its code, and as single facts; which facts the model that writes an add-on is
given, and that none is given when none fits; a guide kept by an older VisionClaw is still read; which guides
are here, said by plain code; the instructions that go with guide lines and with answers from the guides or
from an add-on; which installed add-on does what the user wants; the lessons of NVDA Coach read from files
made up here, by how much help was asked for; NVDA's own list of what is new; what is remembered about how
much help an answer gives; and where the requests about all this are sent.

  python tests/test_guides.py
"""
import datetime
import json
import os
import re
import tempfile

import harness  # noqa: F401
from visionClaw.claw import addons, guides, lookup, memories, microaddons, planner, prompts, skills

# The guide that comes with every build is put aside for the parts below, which are about what the user
# downloaded; part 10 is about the one that comes with VisionClaw.
SHIPPED = guides.SHIPPED
guides.SHIPPED = ""

# --- 1. A guide as Markdown: code keeps its indentation, and a comment in code is no heading ---

WIKI = """# The Add-on Guide

- [Intro](#user-content-intro)
- [Events](#user-content-events)
- [Scripts](#user-content-scripts)
- [Objects](#user-content-objects)
- [Modules](#user-content-modules)
- [Tips](#user-content-tips)
- [More](#user-content-more)
- [End](#user-content-end)

## Useful modules

Here are the modules you will use most.

* Useful functions:
    - `api.getFocusObject()`: Retrieves the focused control (returns the object with focus).
    - `api.copyToClip(text to be copied)`: copies text to the clipboard.
    - `tones.beep(pitch in hertz, duration in milliseconds)`: Plays a tone of specified pitch.
    - `ui.message(message to be spoken)`: Speaks or brailles the message.
    - `controlTypes.ROLE_BUTTON`: the old way to name the role of a button.
    - `os.startfile(path)`: opens a file with its program.

## An example

The below example beeps:

	import tones
	# Other parts of the plugin.

	class GlobalPlugin(globalPluginHandler.GlobalPlugin):

		def script_beep(self, gesture):
			tones.beep(440, 100)

After the example, the text goes on. See [the guide](https://example.org/guide.html) for more.

## Notes and references

| What you want | How to write it | Remarks |
|---|---|---|
| Title of the active window | foreground.name | Only if present. |
| Play a tone | tones.beep(hertz, duration) | Duration in milliseconds. |
| Current time in seconds | time.time() | Seconds since 1970. |
| APPLY | ReturnCode.APPLY | A button. |
"""
kept = guides.tidy(WIKI)
assert "```\nimport tones\n# Other parts of the plugin.\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\n\tdef script_beep(self, gesture):\n\t\ttones.beep(440, 100)\n```" in kept, kept
# An item of a list inside a list is no code, although it is indented.
assert "- `api.getFocusObject()`: Retrieves" in kept and "```\n- `api" not in kept
assert guides.tidy("## Events {#events}\n\n\n\ntext  \n") == "## Events\n\ntext\n"
sections = guides.cut(kept)
titles = [title for title, _body in sections]
# The comment in the code is not a heading, and the list of contents is left out.
assert titles == ["Useful modules", "An example", "Notes and references"], titles
said = guides.prose(dict(sections)["An example"])
assert said == "The below example beeps: After the example, the text goes on. See the guide for more.", said
assert "tones.beep" not in said and "http" not in said
rows = guides.prose(dict(sections)["Notes and references"])
assert "Title of the active window: foreground.name. Only if present." in rows and "---" not in rows, rows

# --- 2. Single facts, and which of them fit a request ---

facts = [fact for title, body in sections for fact in guides.factsIn(body, "The Add-on Guide", title)]
texts = [fact.text for fact in facts]
assert "api.getFocusObject(): Retrieves the focused control (returns the object with focus)." in texts, texts
assert "Title of the active window: foreground.name. Only if present." in texts
# A line of the example is never a fact, and a row that begins with a single word says nothing on its own.
assert not any("script_beep" in text or "440" in text for text in texts) and not any(text.startswith("APPLY") for text in texts)
assert all(fact.names for fact in facts)


def given(purpose, exists=None):
	return [fact.names[0].split("(")[0] for fact in guides.fitting(facts, purpose, exists=exists)]


assert given("Copy the name of the focused control to the clipboard when I press NVDA+alt+C.") == ["api.getFocusObject", "api.copyToClip"]
assert given("Beep when a link gets the focus.") == ["api.getFocusObject", "tones.beep"]
assert given("Announce the title of the window in front when it changes.") == ["foreground.name"]
# Nothing fits: nothing is given. "The time" is not "the current time in seconds", and Python's own time
# module is not NVDA's.
assert given("Say hello when I press NVDA+shift+H.") == []
assert given("Say the time when I press NVDA+alt+T.") == []
assert given("Tell me when a progress bar changes in this program.") == []
# What a small add-on must not use is never given, whatever the request says.
assert given("Open a file with its program by its path") == []
# A name this NVDA no longer has is left out; one that cannot be told is kept.
assert given("say the role of the button when I press NVDA+alt+B") == ["controlTypes.ROLE_BUTTON"]
assert given("say the role of the button when I press NVDA+alt+B", exists=lambda name: False if "ROLE_" in name else None) == []
text = guides.coderText(facts, "Beep when a link gets the focus.")
assert text.startswith(guides.CODER_HEAD + "\n- ") and "\n- tones.beep(pitch in hertz, duration in milliseconds): Plays a tone" in text, text
assert guides.coderText(facts, "Say hello when I press NVDA+shift+H.") == ""
assert len(guides.coderText(facts, "copy the focused control's title to the clipboard and beep")) <= guides.CODER_CHARS + len(guides.CODER_HEAD) + 2

# --- 3. Kept on this computer: counted, read as sentences and as facts, said by plain code, deleted ---

folder = tempfile.mkdtemp()
PAGE = "<html><body><h1>NVDA Developer Guide</h1>" + "".join(
	f"<h2>Part {n}</h2><p>{'Words about part %d. ' % n * 40}</p><pre># A comment in code\nx = {n}</pre>" for n in range(12)) + "</body></html>"
LONG_WIKI = WIKI + "".join(f"\n## Topic {n}\n\n{'The wiki says things about topic %d. ' % n * 30}\n" for n in range(10))
result = guides.update(folder, lambda url: PAGE if url.endswith(".html") else LONG_WIKI, today="2026-11-18")
assert result == {"got": [("NVDA Developer Guide", 12), ("NVDA Add-on Development Guide", 13)], "failed": []}, result
assert guides.stored(folder)["NVDA Developer Guide"] == {"date": "2026-11-18", "sections": 12, "format": guides.FORMAT}
assert "the models" not in guides.summary(result).lower() and "add-on" in guides.summary(result)
loaded = guides.load(folder)
assert all(source == guides.SOURCE and "```" not in body and "A comment in code" not in body for _title, body, source in loaded)
assert loaded[0][0] == "NVDA Developer Guide: Part 0", loaded[0]
book = guides.Guides(folder)
assert book.here() and "tones.beep" in book.forCoder("Beep when a link gets the focus.")
today = datetime.date(2026, 11, 20)
told = guides.storedText(folder, today)
assert "The NVDA Developer Guide by NV Access, downloaded on 2026-11-18, 2 days ago." in told and folder in told, told
assert "older VisionClaw" not in told and "Newer ones may exist" not in told
assert "Newer ones may exist by now" in guides.storedText(folder, datetime.date(2027, 8, 1))
assert "never downloads them by itself" in guides.storedText(folder, datetime.date(2027, 8, 1))

# As VisionClaw 1.1.0 kept them: no fences, the indentation gone, no format in the record.
old = tempfile.mkdtemp()
with open(os.path.join(old, "nvda-addon-development-guide.md"), "w", encoding="utf-8") as f:
	f.write(
		"# The Add-on Guide\n\n## An example\n\nThe below example beeps:\n\nimport tones\n# Other parts of the plugin.\n\n"
		"class GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\ndef script_beep(self, gesture):\ntones.beep(440, 100)\n\n"
		"After the example, the text goes on.\n\n## Useful modules\n\n- `tones.beep(pitch in hertz, duration in milliseconds)`: Plays a tone.\n")
with open(os.path.join(old, guides.RECORD), "w", encoding="utf-8") as f:
	json.dump({"NVDA Add-on Development Guide": {"date": "2026-11-17", "sections": 119}}, f)
loaded = guides.load(old)
assert [title for title, _body, _source in loaded] == [
	"NVDA Add-on Development Guide: An example", "NVDA Add-on Development Guide: Useful modules"], loaded
assert loaded[0][1] == "The below example beeps: After the example, the text goes on.", loaded[0][1]
assert guides.Guides(old).forCoder("Beep when a link gets the focus.").endswith("Plays a tone.")
assert "kept by an older VisionClaw" in guides.storedText(old, today)

assert guides.remove(folder) == ["NVDA Developer Guide", "NVDA Add-on Development Guide"]
assert not guides.Guides(folder).here() and guides.load(folder) == [] and guides.stored(folder) == {}
assert guides.storedText(folder).startswith("No developer guides are on this computer yet.")
assert guides.remove(folder) == []
# Nothing was added to where a guide may come from.
assert [source["id"] for source in guides.SOURCES] == ["nvda-developer-guide", "nvda-addon-development-guide"]
assert guides.HOSTS == ("download.nvaccess.org", "www.nvaccess.org", "raw.githubusercontent.com")

# --- 4. The instructions that go with them ---

prompts.configure()
plain = prompts.coding(microaddons._SYSTEM, "Beep when a link gets the focus.")
guided = prompts.coding(microaddons._SYSTEM, "Beep when a link gets the focus.", guided=True)
assert prompts.CODE_GUIDE not in plain and guided.endswith(prompts.CODE_GUIDE)
assert prompts.aboutFound("From NVDA's developer guides: Events. NVDA fires events.") == ("devGuide",)
assert prompts.aboutFound("From the add-on Clock: Reports the time. Keys: NVDA+F12.") == ("addonHelp",)
assert prompts.aboutFound("From an add-on's help: The add-on Clock. Press NVDA+F12.") == ("addonHelp",)
assert prompts.aboutFound("From NVDA's user guide: Browse Mode.") == ()
assert prompts.DEV_GUIDE in prompts.speaking("Task.", found="1. From NVDA's developer guides: x") and prompts.DEV_GUIDE not in prompts.speaking("Task.")
# What the writer of an add-on is sent says so in the message, which is how the instruction is chosen.


class _Llm:
	def __init__(self):
		self.systems = []

	def text(self, role, system, user, **options):
		self.systems.append(system)
		return "```python\nimport globalPluginHandler\n\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\tpass\n```"


class _Params:
	codeTokens, reasoning = 100, "off"


llm = _Llm()
microaddons._generate(llm, "coder", "Write it.\n" + guides.coderText(facts, "Beep when a link gets the focus."), _Params(), "Beep.")
microaddons._generate(llm, "coder", "Write it.", _Params(), "Beep.")
assert prompts.CODE_GUIDE in llm.systems[0] and prompts.CODE_GUIDE not in llm.systems[1]

# A question about writing for NVDA that finds nothing says how to get the guides, when they are not here.
nothing = lookup.nothingText("how do I write an event for an add-on", "notepad", "Untitled", guides=False)
assert "The NVDA developer guides are not on this computer." in nothing and "after asking you" in nothing
assert "developer guides" not in lookup.nothingText("how do I write an event for an add-on", "notepad", guides=True)
assert "developer guides" not in lookup.nothingText("how do I juggle", "notepad", guides=False)

# --- 5. Which installed add-on does what the user wants ---

installed = [
	addons.Installed("clock", "Clock and calendar", "Speaks the time in many ways.", addons.ON,
		[("Reports the current time", "NVDA+F12")], ["Press NVDA+F12 twice to hear the date. The alarm is set in the Clock settings."]),
	addons.Installed("Access8Math", "Access8Math", "Reads mathematical content and lets you navigate equations.", addons.OFF, [],
		["Access8Math lets NVDA read math content in web pages and in Word, and move through an equation term by term."]),
	addons.Installed("vlc", "VLC", "Improves VLC media player.", addons.WAITING, [], []),
]
assert addons.wishOf("which add-ons are installed") == "" and addons.wishOf("is there an add-on that reads math equations") == "reads math equations"
found = addons.forWish("is there an add-on that reads math equations", installed)
assert [addon.ident for addon, _about in found] == ["Access8Math"], found
told = addons.wishText("is there an add-on that reads math equations", installed)
assert told.startswith("One add-on installed in NVDA says it does this.\nThe add-on Access8Math: "), told
# An add-on that is turned off is said to be, and VisionClaw does not turn it on.
assert "It is turned off, so its commands do not work now. VisionClaw does not turn add-ons on or off" in told
told = addons.wishText("which add-on can tell me the date", installed)
assert "The add-on Clock and calendar: Press NVDA+F12 twice to hear the date." in told and "turned off" not in told, told
told = addons.wishText("do I have an add-on for sudoku", installed)
assert told.startswith("None of the 3 add-ons installed in NVDA says anything about sudoku."), told
assert "Clock and calendar, Access8Math, VLC" in told
assert addons.wishText("anything", []) == "No add-ons are installed in NVDA."
# Every passage says which add-on it is from, which is how the answer is told to name the add-on.
assert all(passage.origin.startswith("the add-on ") for passage in addons.passages(installed))
assert prompts.aboutFound(addons.passages(installed)[0].line()) == ("addonHelp",)

# --- 6. NVDA Coach: its lessons read from files, as much help as was asked for ---

coach = tempfile.mkdtemp()
os.makedirs(os.path.join(coach, "en"))
CHAPTERS = {
	"reading.json": {"id": "reading", "title": "Reading Text", "order": 2, "lessons": [
		{"id": "line", "title": "Read the Current Line", "order": 1, "steps": [
			{"type": "info", "instruction": "NVDA+Up Arrow reads the current line. Press Enter to continue.",
				"hints": ["Hold the NVDA key and press Up Arrow."]},
			{"type": "gesture", "instruction": "Press NVDA+Up Arrow now to hear the line.", "hint": "The NVDA key is Insert."}]},
		{"id": "word", "title": "Jump Word by Word", "order": 2, "steps": [
			{"type": "info", "instruction": "Control+Right Arrow moves to the next word.", "hints": []}]}]},
	"start.json": {"id": "start", "title": "Getting Started", "order": 1, "lessons": [
		{"id": "key", "title": "Meet Your NVDA Key", "order": 1, "steps": [
			{"type": "info", "instruction": "The NVDA key is Insert. NVDA+N opens the NVDA menu. The menu has Preferences.",
				"hints": ["Press and hold Insert, then press N for the menu."]},
			{"type": "info", "instruction": "In the menu, the arrow keys move and Escape closes the menu."}]}]},
	"notes.json": ["not a chapter"],
}
for name, chapter in CHAPTERS.items():
	with open(os.path.join(coach, "en", name), "w", encoding="utf-8") as f:
		json.dump(chapter, f)
with open(os.path.join(coach, "en", "broken.json"), "w", encoding="utf-8") as f:
	f.write("{ not json")
lessons = addons.coachLessons(coach, ("de", "", "en"))
# In the Coach's own order, and without the sentence that belongs to the Coach's own window.
assert [lesson.title for lesson in lessons] == ["Meet Your NVDA Key", "Read the Current Line", "Jump Word by Word"]
assert lessons[1].steps[0] == ("NVDA+Up Arrow reads the current line.", ("Hold the NVDA key and press Up Arrow.",))
assert lessons[1].steps[1][1] == ("The NVDA key is Insert.",)
assert addons.coachLessons(os.path.join(coach, "nowhere")) == [] and addons.coachLessons(coach, ("fr",)) == []

for said, level in (
		("open NVDA Coach", addons.OPEN), ("coach me", addons.OPEN), ("start the next lesson", addons.OPEN),
		("which lessons does NVDA Coach have", addons.LIST), ("how far am I in NVDA Coach", addons.PROGRESS),
		("which lessons have I done", addons.PROGRESS), ("give me a hint about reading the current line", addons.HINT),
		("teach me the NVDA menu step by step", addons.STEPS), ("give me a lesson on the NVDA menu", addons.STEPS),
		("coach me on reading the current line", addons.ONE)):
	assert addons.wants(said) == level, (said, addons.wants(said))

key = "NVDA+shift+c"
progress = os.path.join(coach, "progress.json")
with open(progress, "w", encoding="utf-8") as f:
	json.dump({"start": {"key": {"completed": True}}, "reading": {"line": {"completed": False}}}, f)
done = addons.coachDone(progress)
assert done == {("start", "key")} and addons.coachDone(os.path.join(coach, "none.json")) == set()
hint = addons.coachText(lessons, done, "give me a hint about reading the current line", key)
assert hint.startswith('From NVDA Coach, the lesson "Read the Current Line" in Reading Text, a hint: Hold the NVDA key and press Up Arrow.'), hint
# A hint is a hint: the step itself, which names the key, is not given with it.
assert "reads the current line" not in hint
one = addons.coachText(lessons, done, "coach me on reading the current line", key)
assert "step 1 of 2: NVDA+Up Arrow reads the current line." in one and "press NVDA+shift+c" in one, one
steps = addons.coachText(lessons, done, "give me a lesson on the NVDA menu", key)
assert '"Meet Your NVDA Key" in Getting Started, step by step.\nStep 1: The NVDA key is Insert.' in steps and "\nStep 2: In the menu" in steps, steps
assert "Press Enter to continue" not in steps + one + hint
listed = addons.coachText(lessons, done, "which lessons does NVDA Coach have", key)
assert listed.startswith("NVDA Coach has 3 lessons in 2 chapters: Getting Started, 1 lesson; Reading Text, 2 lessons."), listed
far = addons.coachText(lessons, done, "how far am I in NVDA Coach", key)
assert far.startswith("You have finished 1 of the 3 lessons of NVDA Coach. Getting Started: 1 of 1; Reading Text: 0 of 2."), far
assert 'The first lesson you have not finished is "Read the Current Line"' in far
assert addons.coachText(lessons, done, "teach me to juggle", key).startswith("None of the 3 lessons of NVDA Coach is about juggl")
assert "its lessons were not found" in addons.coachText([], done, "teach me the menu", key)
# Not there, or not on: said plainly, and VisionClaw installs and turns on nothing.
assert "is not installed in NVDA" in addons.coachMissing(None) and "does not install add-ons" in addons.coachMissing(None)
assert "it is turned off" in addons.coachMissing(addons.OFF) and "does not turn add-ons on or off" in addons.coachMissing(addons.OFF)
assert addons.namesCoach("open the coach") and not addons.namesCoach("teach me the speech rate")
assert addons.plainQuestion("teach me how to change the speech rate") == "change the speech rate"
assert len(addons.coachText(lessons, done, "teach me the NVDA menu step by step", key)) < 1500

# --- 7. NVDA's own list of what is new ---

CHANGES = (
	"<html><body><h1>What's New in NVDA</h1><h2>2026.3.1</h2><p>This is a patch release that fixes a problem with the task "
	"switcher in Windows 10.</p><h3>Bug Fixes</h3><ul><li>Fixed the task switcher no longer announcing the selected task.</li>"
	"</ul><h3>Changes for Developers</h3><p>The function quokka was removed from the public interface.</p>"
	"<h2>2026.3</h2><h3>New Features</h3><ul><li>A new command reports the battery of a braille display.</li></ul>"
	"<h2>2026.2</h2><p>Highlights of this release are many, and are listed below in full.</p>"
	"<h2>2026.1</h2><p>An older release, which is not read any more by default here.</p>"
	"<h2>2025.3</h2><p>An even older release, which is certainly not read any more.</p></body></html>")
news = lookup.newsSections(CHANGES)
assert [title for title, _body in news] == [
	"What is new in NVDA 2026.3.1, the latest version", "New in NVDA 2026.3.1, the latest version: Bug Fixes",
	"New in NVDA 2026.3: New Features", "What is new in NVDA 2026.2"], news
assert not any("quokka" in body for _title, body in news)
passages = lookup.fromSections([(title, body, lookup.NEWS) for title, body in news])
found = lookup.about("what is new in the latest version of NVDA", passages)
assert found and found[0].origin == "NVDA's list of what is new" and "2026.3.1" in found[0].line(), found
# It is asked only about what is new or what changed, never about how something is done.
assert lookup.about("how do I report the battery of my braille display", passages) == []
assert lookup.about("what changed in NVDA for the braille display battery", passages)

# --- 7b. The description window: a question about how something is done is given the command it names ---

from visionClaw import followup  # noqa: E402


def command(name, description, keys):
	line = f"{name}: {description.rstrip('.')}. Keys: {keys or 'no key assigned'}."
	return lookup.fromCommand(name, description, "", line)


commandList = [
	command("title", "Reports the title of the current application or foreground window. If pressed twice, spells the title", "NVDA+t"),
	command("readStatusLine", "Reads the current application status bar", ""),
	command("reportStatusLine", "Reads the current application status bar. If pressed twice, spells the information", "NVDA+end"),
	command("toggleVirtualBufferPassThrough", (
		"Toggles between browse mode and focus mode. When in focus mode, keys will pass straight through to the "
		"application, allowing you to interact directly with a control"), "NVDA+space"),
	command("reportCurrentFocus", "Reports the object with focus", "NVDA+tab"),
]
found = followup.known("How do I read the title of this window with the keyboard?", commandList)
# What a second press does is left out: given it, the model said to press the key twice.
assert found == "\n\n" + followup.KNOWN_HEAD + "\n- From NVDA: title: Reports the title of the current application or foreground window. Keys: NVDA+t.", found
assert "never make one up" in followup.KNOWN_HEAD and "not from the picture" in followup.KNOWN_HEAD
# Of two commands for one thing, the one that has a key.
found = followup.known("Which key reads the status bar?", commandList)
assert "reportStatusLine" in found and "NVDA+end" in found and "no key assigned" not in found, found
# What the picture shows is asked exactly as before: nothing is added.
for question in ("Which button has the focus?", "What colour is the car?", "Which options are turned on?", "Is there a person in it?"):
	assert followup.known(question, commandList) == "", question
# A command that only shares words with the question is not given: measured, the model repeats its key.
assert followup.known("How can I hear which control has the focus?", commandList) == ""
# A question that names one thing is too wide, and one that nothing is about gets nothing.
assert followup.known("How do I get to that button?", commandList) == ""
assert followup.known("How do I bake sourdough bread at home?", commandList) == ""
# A question about writing add-ons is not for the model that looks at a picture: measured, it invents a key.
assert not followup.asksHow("How would an add-on speak a message when I press a key?")
assert followup.known("How would an add-on report the title of the window?", commandList) == ""

# --- 8. How much help an answer gives, remembered ---

assert memories.worthKeeping("From now on, give me only a hint.", memories.AUTO, [], lambda tool: False)
assert memories.worthKeeping("I prefer short answers. How do I read the title?", memories.AUTO, [], lambda tool: False)
kept = memories.Memories(tempfile.mkdtemp())
kept.add("always explain things step by step", kind=memories.LIKES)
kept.add("your braille display is a Focus 40", kind=memories.YOU)
kept.add("I prefer the Eloquence voice", kind=memories.LIKES)
# Only what is about how much help an answer gives: not the braille display, and not the voice.
wanted = kept.helpWanted()
assert len(wanted) == 1 and "explain things step by step" in wanted[0], wanted

# --- 9. Where the requests are sent, and the skills that are chosen ---

SENT = {
	"get the latest NVDA developer guides": "update_guides",
	"which developer guides do I have?": "guides_info",
	"how old are the developer guides": "guides_info",
	"open the developer guides folder": "guides_info",
	"delete the developer guides": "remove_guides",
	"what does the developer guide say about events": "nvda_question",
	"coach me": "coach",
	"open NVDA Coach": "coach",
	"give me a hint about browse mode": "coach",
	"teach me object navigation": "coach",
	"which lessons have I done": "coach",
	"is there an add-on that reads math": "addon_question",
	"which of my add-ons can download videos": "addon_question",
	"what does the clock add-on do": "addon_question",
	"how do I read the title": "explain_keys",
	"what is browse mode": "nvda_question",
}
for request, recipe in SENT.items():
	assert planner.hint(request) == recipe, (request, planner.hint(request))
for recipe in ("guides_info", "remove_guides", "coach"):
	assert recipe in planner.RECIPES and planner.label(recipe)

lib = skills.Skills(tempfile.mkdtemp(), recipes=set(planner.RECIPES))
for request, slug in {
		"what does the developer guide say about events": "developer-guides",
		"is there an add-on that reads math": "work-with-add-ons",
		"just a hint, how do I read the title": "as-much-help-as-asked"}.items():
	chosen = [skill.slug for skill in lib.choose(request)]
	assert slug in chosen, (request, chosen)
both = [skill.slug for skill in lib.choose("Write an add-on the way the developer guide says, which beeps when a link gets the focus")]
assert "addon-by-the-guides" in both or "addon-for-blind-user" in both, both
guide = skills.guide(lib.choose("write it according to the guide, an add-on that beeps"), "write_addon")
assert "never make up a name" in guide, guide
# The skill for answers from the guides says nothing to the writing of an add-on, and the other way round.
assert "never make up a name" not in skills.guide(lib.choose("what does the developer guide say about events"), "nvda_question")
for request in ("what time is it", "turn off the typing echo", "read the title"):
	assert not lib.choose(request), (request, lib.choose(request))
# Nothing a model reads here names a model's role, or gives an example.
for text in (prompts.CODE_GUIDE, prompts.DEV_GUIDE, prompts.ADDON_HELP, guides.CODER_HEAD, addons.COACH_ABSENT):
	assert not re.search(r"\b(both|two|other|vision|coder) models?\b|\bfor example\b|\bsuch as\b", text, re.IGNORECASE), text

# --- 10. What comes with every build: only what its owner allows to be passed on ---

guides.SHIPPED = SHIPPED
# Nothing is in the folder of what is shipped that is not named, with its licence, in MAY_SHIP.
assert guides.MAY_SHIP == {"nvda-developer-guide": "GNU General Public License, version 2 or later"}
files = sorted(name for name in os.listdir(SHIPPED) if name.endswith(".md"))
assert files == [ident + ".md" for ident in sorted(guides.MAY_SHIP)], files
came = guides.shippedRecord()
assert list(came) == ["NVDA Developer Guide"] and came["NVDA Developer Guide"]["licence"] == guides.MAY_SHIP["nvda-developer-guide"]
assert came["NVDA Developer Guide"]["format"] == guides.FORMAT and came["NVDA Developer Guide"]["sections"] > 50
with open(os.path.join(SHIPPED, "nvda-developer-guide.md"), encoding="utf-8") as f:
	top = f.read(400)
# The file says whose it is and under which licence, before anything else.
assert top.startswith("<!-- NVDA Developer Guide, by NV Access and contributors. GNU General Public License, version 2 or later. From https://download.nvaccess.org/"), top
# A user who downloaded nothing has it: as sentences for questions, with no code in them.
nothing = tempfile.mkdtemp()
kept = guides.Guides(nothing)
assert kept.here() and not kept.downloaded()
sections = guides.load(nothing)
assert len(sections) > 50 and all(title.startswith("NVDA Developer Guide: ") and "```" not in body for title, body, _source in sections)
assert not any("<!--" in body or "turned into Markdown by VisionClaw" in body for _title, body, _source in sections)
told = guides.storedText(nothing)
assert told.startswith("The NVDA Developer Guide by NV Access came with VisionClaw, as it was on "), told
assert "The NVDA Add-on Development Guide does not come with VisionClaw, because its authors have not said that it may be passed on." in told
assert "asks before it goes online" in told and "downloaded on" not in told
# What the user downloads is newer and is used in its place; deleted, the one that came with VisionClaw is back.
result = guides.update(nothing, lambda url: PAGE if url.endswith(".html") else LONG_WIKI, today="2026-12-01")
assert len(result["got"]) == 2 and kept.downloaded()
assert guides.load(nothing)[0][0] == "NVDA Developer Guide: Part 0"
assert "came with VisionClaw" not in guides.storedText(nothing) and "A downloaded guide is used in place" in guides.summary(result)
assert guides.remove(nothing) == ["NVDA Developer Guide", "NVDA Add-on Development Guide"]
assert kept.here() and not kept.downloaded() and len(guides.load(nothing)) == len(sections)
# A guide that may not be passed on is never read from the folder of what is shipped, even if a file is there.
other = tempfile.mkdtemp()
with open(os.path.join(other, "nvda-addon-development-guide.md"), "w", encoding="utf-8") as f:
	f.write("## Lesson\n\nA guide whose authors did not say that it may be passed on.\n")
guides.SHIPPED = other
assert guides.load(tempfile.mkdtemp()) == [] and not guides.Guides(tempfile.mkdtemp()).here()
guides.SHIPPED = SHIPPED

print("OK")
