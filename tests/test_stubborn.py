# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Stubborn programs, controls and web pages, with plain Python (2026-11-19): what VisionClaw keeps about a place as a
Markdown file (claw/accessnotes.py), when a case is hard and how the model for hard cases settles it
(claw/hardcase.py), the controls whose state may be missing (audit._stateless), the notes looked things up in
(knowledge/visionclaw-stubborn.md), and the names the speech model is told (voice.namesHere). No NVDA, no model.

  python tests/test_stubborn.py
"""
import os
import re
import tempfile

import harness  # noqa: F401
from visionClaw.claw import accessnotes, audit, catalog, fixes, hardcase, voice, working

# --- The access notes: one Markdown file a place, written by plain code, read as the user left it ---

folder = tempfile.mkdtemp(prefix="vcaccess-")
notes = accessnotes.AccessNotes(os.path.join(folder, accessnotes.FOLDER))
app = fixes.scopeOf(app="reaper")
site = fixes.scopeOf(site="example.com")
assert notes.forModels(app) == "" and notes.known(app, {"role": "SLIDER"}) is None  # nothing yet, and no file
volume = accessnotes.keyOf({"role": "SLIDER", "autoId": "vol"})
gain = accessnotes.keyOf(None, "SLIDER", "Gain")
assert gain == {"name": "Gain", "role": "SLIDER"} and accessnotes.keyOf(None, "BUTTON", "") is None
assert notes.keepWay(app, volume, "Volume", working.SIDEWAYS, accessnotes.AGREED, today="2026-11-19")
assert notes.keepWay(app, gain, "Gain", working.AROUND, accessnotes.ONE, today="2026-11-19")
assert not notes.keepWay(app, None, "a button without a name", working.CLICK, accessnotes.AGREED)  # nothing finds it again
# Only what was agreed or settled is used again; one model's answer is only told.
assert notes.known(app, volume) == working.SIDEWAYS and notes.known(app, gain) is None
# A later answer about the same control: an agreed one takes the place of the old line, an unsure one does not.
assert notes.keepWay(app, gain, "Gain", working.UPDOWN, accessnotes.SETTLED, today="2026-11-20")
assert notes.known(app, gain) == working.UPDOWN
assert not notes.keepWay(app, gain, "Gain", working.CLICK, accessnotes.ONE)
assert notes.known(app, gain) == working.UPDOWN
assert notes.keepName(app, {"role": "BUTTON", "autoId": "play"}, "button", "Play", today="2026-11-19")
assert notes.keepKind(app, "Its window has the class REAPERwnd.", today="2026-11-19")
assert notes.keepFound(app, "3 controls without a name; 2 never take the focus.", today="2026-11-19")
text = notes.text(app)
assert text.startswith("# What VisionClaw found in the program reaper\n"), text
assert "You may change or delete any line" in text and "## How controls are worked" in text, text
assert "- 2026-11-19: Volume: drag sideways. agreed. [" in text and "- 2026-11-20: Gain: drag up and down. settled" in text, text
assert "a button without a name is called Play, from its picture" in text
# Another place has a file of its own.
assert notes.keepWay(site, volume, "Volume", working.CLICK, accessnotes.AGREED)
assert notes.known(site, volume) == working.CLICK and notes.known(app, volume) == working.SIDEWAYS
assert os.path.basename(notes.path(site)) == "example.com.md" and os.path.basename(notes.path(app)) == "reaper.md"
# For the models: the lines that share words with the request first, without the rules in brackets.
told = notes.forModels(app, "the gain knob")
assert told.startswith("Found in this place before, on this computer:\n- Gain: drag up and down") and "[" not in told, told
# The writer of an add-on gets only lines that share a telling word with what the add-on is for, or nothing.
assert notes.forModels(app, "beep when a link gets the focus", strict=True) == ""
assert "Play" in notes.forModels(app, "a key that presses play", strict=True)
# The user's own changes count: a deleted line is gone, a changed way is the one used.
path = notes.path(app)
with open(path, encoding="utf-8") as f:
	lines = f.read().splitlines()
lines = [line.replace("Volume: drag sideways", "Volume: turn in a circle") for line in lines if "Gain" not in line]
with open(path, "w", encoding="utf-8") as f:
	f.write("\n".join(lines))
assert notes.known(app, gain) is None and notes.known(app, volume) == working.AROUND
# A file that grows: the oldest summaries go first, never what was found about a control.
for at in range(accessnotes.MAX_LINES + 5):
	notes.keepFound(app, f"Inspection number {at}.")
text = notes.text(app)
assert "Inspection number 0." not in text and f"Inspection number {accessnotes.MAX_LINES + 4}." in text
assert notes.known(app, volume) == working.AROUND and "Play" in text
assert sum(1 for line in text.splitlines() if line.startswith("- ")) <= accessnotes.MAX_LINES
# Forgotten, the file is gone; a place that cannot be written is no fault.
assert notes.forget(app) and not os.path.exists(path) and not notes.forget(app)
broken = accessnotes.AccessNotes(os.path.join(path, "nowhere", "\0"))
assert not broken.keepWay(app, volume, "Volume", working.CLICK, accessnotes.AGREED) and broken.known(app, volume) is None
assert accessnotes.fileName({"app": ""}) == "" and notes.forModels({"app": ""}) == ""

# --- Hard cases ---

entries = catalog.CATALOG
four, six = (e for e in entries if catalog.isEdge(e))
assert hardcase.candidates(entries) == [four, six]
has = lambda wanted: (lambda entry: entry["id"] in wanted)  # noqa: E731
# "" uses any model for hard cases on the disk, Q4_K_M first; "none" never; an id only that one, when it is there.
assert hardcase.chosen(entries, "", has(set())) is None
assert hardcase.chosen(entries, "", has({six["id"]})) is six
assert hardcase.chosen(entries, "", has({four["id"], six["id"]})) is four
assert hardcase.chosen(entries, "none", has({four["id"]})) is None
assert hardcase.chosen(entries, six["id"], has({four["id"], six["id"]})) is six
assert hardcase.chosen(entries, six["id"], has({four["id"]})) is None
# What the user is asked names the model, says it is slower and text only, and asks.
question = hardcase.question(four, hardcase.ADDON)
assert question.startswith("The add-on could not be written so that it passes VisionClaw's checks. VisionClaw has a larger model")
assert "Qwen3 14B Q4_K_M" in question and "slower" in question and "text only" in question and question.endswith("?")
assert "NVDA+Alt+X" in hardcase.startText(four)
assert "NVDA+Alt+M" in hardcase.missingText(entries) and "Qwen3 14B" in hardcase.missingText(entries)
assert hardcase.missingText([e for e in entries if not catalog.isEdge(e)]) == ""
# The user's own words can ask for it.
for words in ("fix it with the model for hard cases", "use the 14b", "try the larger model", "write it with qwen3 14b"):
	assert hardcase.asked(words), words
for words in ("this is hard to use", "which model is best", "a larger font"):
	assert not hardcase.asked(words), words
# A judgement is a hard case only where the two answers did not settle it and the facts tell something.
assert hardcase.isHardJudgement({"sure": False, "telling": True})
assert not hardcase.isHardJudgement({"sure": True, "telling": True}) and not hardcase.isHardJudgement({"sure": False, "telling": False})
# Settled: agreeing with one answer makes it sure; alone where neither could tell, not sure; a third answer changes nothing.
assert hardcase.settles(working.CLICK, working.SIDEWAYS, working.SIDEWAYS) == (working.SIDEWAYS, True)
assert hardcase.settles(working.CLICK, working.SIDEWAYS, working.CLICK) == (working.CLICK, True)
assert hardcase.settles(None, working.UNSURE, working.UPDOWN) == (working.UPDOWN, False)
assert hardcase.settles(working.CLICK, working.SIDEWAYS, working.AROUND) == (None, False)
assert hardcase.settles(working.CLICK, working.SIDEWAYS, working.UNSURE) == (None, False)
assert hardcase.settles(working.CLICK, None, "something made up") == (None, False)

# --- Controls whose state may be missing ---

def node(role, name, states=()):
	return {"role": role, "name": name, "states": list(states)}


found = audit._stateless([node("TAB", "General"), node("TAB", "Advanced"), node("BUTTON", "Show more"),
	node("BUTTON", "Options", ["HASPOPUP"]), node("BUTTON", "Save"), node("LINK", "Expand all")])
assert found is not None and found.id == "state" and not found.fixable, found
assert found.text == (
	"A state may be missing: 2 tabs here, and none of them says that it is the one selected; 2 buttons that open or show "
	"something do not say whether what they open is open: Show more, Expand all."), found.text
assert "picture" in found.advice
assert audit._stateless([node("TAB", "General", ["SELECTED"]), node("TAB", "Advanced"), node("BUTTON", "Show more", ["COLLAPSED"])]) is None
assert audit._stateless([node("TAB", "Only one"), node("BUTTON", "More options", ["EXPANDED"])]) is None
assert audit._stateless([]) is None
# Buttons and links that open or close something but have no state of their own are no finding.
assert audit._stateless([node("BUTTON", "Close"), node("BUTTON", "Open"), node("LINK", "Order details"),
	node("LINK", "More info"), node("BUTTON", "Shipping options")]) is None
assert audit._stateless([node("BUTTON", "Main menu"), node("BUTTON", "More")]).text.endswith("Main menu, More.")
report = audit.auditWindow([node("TAB", "General"), node("TAB", "Sound"), node("BUTTON", "OK", ["FOCUSABLE"])], title="Options", app="game")
assert any(finding.id == "state" for finding in report.findings)

# --- Naming: a model that is not small is told where the control is; a copied name is asked again, then dropped ---

big, little = {"small": False}, {"small": True}
assert working.tellAround(big) and not working.tellAround(little) and not working.tellAround(None)
heard = []


def answering(*names):
	names = iter(names)
	return lambda around: heard.append(around) or next(names)


near = [("button", "Previous"), ("button", "Next")]
assert working.named(answering("Play"), big, "Just before it: button Previous.", near) == "Play" and heard == ["Just before it: button Previous."]
heard.clear()
assert working.named(answering("Next", "Play"), big, "around", near) == "Play" and heard == ["around", ""]
heard.clear()
assert working.named(answering("Next", "Next"), big, "around", near) == ""
heard.clear()
assert working.named(answering("Play"), little, "around", near) == "Play" and heard == [""]  # a small model is not told
heard.clear()
assert working.named(answering("Spotify Premium"), little, "around", near, ["Spotify", "Spotify Premium"]) == ""
assert working.copies("next", near) and not working.copies("Next track", near) and not working.copies("", near)
assert audit.cleanName("Play button") == "Play" and audit.cleanName("Close Button.") == "Close" and audit.cleanName("Button") == ""
assert audit.cleanName("Notification bell") == "Notification bell"

# --- The question that names a control without a name: where it is, in words, no example ---

around = working.aroundText("vlc", False, "song.mp3 - VLC media player", [("button", "Previous")], [("button", "Next"), ("slider", "Volume")])
assert around == ("It is in the program vlc, in the window titled song.mp3 - VLC media player. Just before it: button "
	"Previous. Just after it: button Next, slider Volume."), around
assert working.nameQuestion("button", around).startswith("The picture shows one button that has no name. It is in the program vlc")
assert working.nameQuestion("graphic") == "The picture shows one graphic that has no name. What is a good name for it?"
assert working.aroundText("example.com", True).startswith("It is in the website example.com.") and working.aroundText() == ""
assert "example" not in working.NAME_SYSTEM.lower() and "colour" in working.NAME_SYSTEM and "unknown" in working.NAME_SYSTEM

# --- The notes looked things up in: one answer a section, about working the computer by keyboard and speech ---

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "..", "addon", "globalPlugins", "visionClaw", "claw", "knowledge", "visionclaw-stubborn.md"),
		encoding="utf-8") as f:
	note = f.read()
sections = re.split(r"\n## ", note.split("\n# ", 1)[1])[1:]
assert len(sections) >= 8, len(sections)
for section in sections:
	heading, _sep, body = section.partition("\n")
	assert len(body) <= 400, (heading, len(body))
	assert not re.search(r"\b(click the (blue|red|green)|look at|as you can see|hover over)\b", body, re.IGNORECASE), heading
	assert "e.g." not in body and "for example" not in body.lower(), heading

# --- What the speech model is told: names of where the user is, likeliest first, nothing it knows anyway ---

names = voice.namesHere("REAPER", "song.rpp - REAPER v7.2", "Arpeggiator",
	["OK", "Cancel", "Quantize", "Sidechain Send", "File", "Track 1 volume fader knob control", "Ozone 11 Maximizer", "Notepad"],
	["shh"])
assert names[:3] == ["REAPER", "shh", "Arpeggiator"], names
assert "OK" not in names and "File" not in names and "Notepad" not in names, names  # known, or told already
assert "Track 1 volume fader knob control" not in names  # too long to be a name the user says
assert len(names) <= voice.MAX_HERE and len(voice.NAMES) + len(names) <= voice.MAX_NAMES
assert all(name in voice.context(names) for name in names)
assert voice.namesHere() == [] and voice.namesHere("", "", "", ["", None, "12"]) == []
# A name the speech model heard split into words is joined again, only where the letters are the very same.
assert voice.fitted("Click wave table in Vital.", ["Wavetable"]) == "Click Wavetable in Vital."
assert voice.fitted("Open the foobar 2000 equalizer.", ["foobar2000"]) == "Open the foobar2000 equalizer."
assert voice.fitted("Open the side chain tab", ["Sidechain"]) == "Open the Sidechain tab"
assert voice.fitted("Click the contact button.", ["Kontakt"]) == "Click the contact button."  # sounds alike, is not
assert voice.fitted("Turn on auto play.", ["AutoTune"]) == "Turn on auto play."
assert voice.heard("language English<asr_text>Open the note pad.") == "Open the Notepad."
# --- What the model for hard cases got wrong, corrected by plain code ---

from visionClaw.claw import microaddons  # noqa: E402

made = (
	"import globalPluginHandler\nimport eventHandler\nimport tones\n\n\n"
	"class GlobalPlugin(globalPluginHandler.GlobalPlugin):\n"
	"\t@eventHandler.registerEvent(\"event_valueChange\")\n"
	"\tdef event_valueChange(self, obj, nextHandler):\n\t\ttones.beep(880, 100)\n\t\tnextHandler()\n")
tidied = microaddons.tidy(made, "beep whenever a progress bar's value changes")
assert "registerEvent" not in tidied and "def event_valueChange(self, obj, nextHandler):" in tidied, tidied
assert not microaddons.check(tidied), microaddons.check(tidied)
# A script keeps its decorator: that one NVDA needs.
keyed = (
	"import globalPluginHandler\nimport ui\nfrom scriptHandler import script\n\n\n"
	"class GlobalPlugin(globalPluginHandler.GlobalPlugin):\n"
	"\t@script(gesture=\"kb:NVDA+shift+h\")\n\tdef script_hello(self, gesture):\n\t\tui.message(\"hello\")\n")
assert "@script(" in microaddons.tidy(keyed, "say hello when I press NVDA+shift+H")
print("OK")
