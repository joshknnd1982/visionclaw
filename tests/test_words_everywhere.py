# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Every orchestrator reads the user's words through one grammar, with lines of its own where it needs them
(claw/understand.py: use, current, Grammar.read(where=...); claw/codeplan.py read; claw/pictures.py pieces). Plain
Python: no NVDA, no model. The requests here are from tests/eval/words-addons.json and words-pictures.json, the sets the
lines were written from; never take one from the held-out sets.

  python tests/test_words_everywhere.py
"""
import os
import shutil
import tempfile

import harness  # noqa: F401
from visionClaw.claw import codeplan, pictures, understand

grammar = understand.Grammar(None)
rules = grammar.rules()
# The sections of understanding.md for one orchestrator are read with their place, and every other line has none.
assert any(rule.scope == understand.ADDON for rule in rules) and any(rule.scope == understand.PICTURE for rule in rules)
assert all(rule.scope in (None, understand.ADDON, understand.PICTURE) for rule in rules)
assert any(rule.scope == understand.ADDON and rule.kind == understand.TO_DO for rule in rules)
# A line for add-ons never changes a whole request, and one for pictures never changes an add-on.
assert grammar.read("make it chime when the battery is low").text == "make it chime when the battery is low"
assert grammar.read("make it chime when the battery is low", where=understand.ADDON).text == "make it beep when the battery is low"
assert grammar.read("tally up the icons", where=understand.ADDON).text == "tally up the icons"
assert grammar.read("tally up the icons", where=understand.PICTURE).text == "count the icons"
# The lines every request gets apply there too.
assert grammar.read("hey visionclaw, what's scribbled on the whiteboard", where=understand.PICTURE).text == \
	"what's written on the whiteboard"
# In an add-on, "that says" is what it does: the words after it are read; quotes and keys never change.
assert grammar.read("whip up an add-on that yells 'new mail' when a dialog pops up", where=understand.ADDON).text == \
	"make an add-on that says 'new mail' when a dialog pops up"
assert grammar.read("make an add-on where hitting nvda+shift+t blurts out the time", where=understand.ADDON).text == \
	"make an add-on where hitting nvda+shift+t says the time"
assert grammar.read("rename the file that says chime", where=None).text == "rename the file that says chime"

# The add-on writer reads casual words into the right pieces.
for said, event, role, state, body in (
		("make an add-on that dings whenever I land on a link", "gainFocus", "LINK", None, "tones.beep"),
		("build me a script that chimes when a checkbox gets ticked", "stateChange", "CHECKBOX", ("CHECKED", True), "tones.beep"),
		("an addon that beeps whenever focus hits a radio button", "gainFocus", "RADIOBUTTON", None, "tones.beep"),
		("make an addon that says 'done' once a button becomes greyed out", "stateChange", "BUTTON", ("UNAVAILABLE", True),
			"ui.message('done')"),
		("make an add-on that pings me when a notification comes in", "UIA_notification", "", None, "tones.beep"),
		("build an add-on: when I focus an edit box, play a beep", "gainFocus", "EDITABLETEXT", None, "tones.beep"),
		("an addon that clicks softly whenever a check box is unticked", "stateChange", "CHECKBOX", ("CHECKED", False), "tones.beep")):
	found, why = codeplan.read(said)
	assert len(found) == 1, (said, why)
	piece = found[0]
	assert (piece.event, piece.role or "", piece.state) == (event, role, state), (said, piece.event, piece.role, piece.state)
	assert codeplan.plainBody(piece.action)[0].startswith(body), (said, piece.action)
# A key with something to say that a model writes stays so.
found, _why = codeplan.read("rig up an add-on so control+alt+n reads out the focused object's name")
assert found[0].kind == codeplan.KEY and codeplan.plainBody(found[0].action)[0] == ""

# A question about a picture: the kind of each part, from casual words.
for said, kinds in (("can you make out the lettering on the button", ["text"]), ("what hue is the background", ["colour"]),
		("what's the trendline doing", ["chart"]), ("what's lit up on the screen right now", ["focus"]),
		("what's in this photo, and what's the fine print say", ["describe", "text"])):
	assert [kind for kind, _words in pictures.pieces(said)] == kinds, (said, pictures.pieces(said))
# The kind is told from the plain words; the model is still asked in the user's own words, part for part.
assert pictures.pieces("what's scribbled on the whiteboard") == [("text", "what's scribbled on the whiteboard")]
assert pictures.pieces("what's scribbled on the whiteboard? what hue is the sky") == [
	("text", "what's scribbled on the whiteboard"), ("colour", "what hue is the sky")]
# Where only the plain words split into parts ("count" begins a question, "tally up" does not), they are asked.
assert pictures.pieces("what's scribbled on the whiteboard, and tally up the icons") == [
	("text", "what's written on the whiteboard"), ("count", "count the icons")]

# One grammar for every orchestrator: the add-on's own, with the user's own words, once it is set.
own = tempfile.mkdtemp()
try:
	mine = understand.Grammar(own)
	mine.teach("bonk", "beep")
	understand.use(mine)
	assert understand.current() is mine
	found, _why = codeplan.read("make an add-on that bonks when a link gets the focus")
	assert found and found[0].event == "gainFocus" and "bonk" in found[0].action  # "bonks" is another word than "bonk"
	found, _why = codeplan.read("make an add-on that says bonk when a link gets the focus")
	assert found and found[0].action == "say beep", found[0].action
finally:
	understand.use(None)
	shutil.rmtree(own, ignore_errors=True)
assert isinstance(understand.current(), understand.Grammar) and understand.current().folder is None
print("OK")
