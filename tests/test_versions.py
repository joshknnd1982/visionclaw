# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Which version is installed: what the words ask the version of, the job they go to, and the answer. Plain Python.
The owner asked on 2026-11-19 "tell me the version of visionclaw I have installed?" and was read all 25 add-ons. The
tool itself, against stand-ins for NVDA, is in test_nvda_stub.py."""

import harness  # noqa: F401
from visionClaw.claw import planner, tools, understand, versions

V, N, NAMED, P = versions.VISIONCLAW, versions.NVDA, versions.NAMED, versions.PROGRAM

# What the words ask the version of. The first two are the owner's own.
ASKS = {
	"tell me the version of visionclaw I have installed?": [(V, "VisionClaw")],
	"What visionclaw addon version is installed?": [(V, "VisionClaw")],
	"Which version of VisionClaw do I have": [(V, "VisionClaw")],
	"visionclaw version?": [(V, "VisionClaw")],
	"what version of vision claw is this": [(V, "VisionClaw")],
	"what version are you": [(V, "VisionClaw")],
	"what's your version number": [(V, "VisionClaw")],
	"VisionClaw, what version of NVDA am I running?": [(N, "NVDA")],
	"can you tell me what version of nvda I have": [(N, "NVDA")],
	"what version of the screen reader am I using": [(N, "NVDA")],
	"Which build of NVDA is this": [(N, "NVDA")],
	"what version of NVDA did I install": [(N, "NVDA")],
	"Which version of Access8Math do I have?": [(NAMED, "Access8Math")],
	"what version is the NVDA Coach add-on": [(NAMED, "NVDA Coach")],
	"what version of this program is it": [(P, "")],
	"what version of Firefox is this": [(NAMED, "Firefox")],
	"what version of NVDA and VisionClaw do I have": [(N, "NVDA"), (V, "VisionClaw")],
	"which version of NVDA as well as VisionClaw is this": [(N, "NVDA"), (V, "VisionClaw")],
	"what version of Microsoft Access do I have": [(NAMED, "Microsoft Access")],
	"what version of Access is this": [(NAMED, "Access")],
	"what versions of nvda, visionclaw and access8math are installed?": [(N, "NVDA"), (V, "VisionClaw"), (NAMED, "access8math")],
	"I'm a beginner screen reader user, what version of visionclaw do I have": [(V, "VisionClaw")],
}
for said, things in ASKS.items():
	found = versions.wish(said)
	assert found is not None and found["things"] == things, (said, found)
	assert planner.hint(said) == "version_info", (said, planner.hint(said))

# Words that ask something else: a newer version, what is new, what something needs, an add-on to be written, a model,
# Windows, Python, the guides, a version of a file, or nothing named.
for said in (
		"Is there a newer version of VisionClaw?", "check for a new version of visionclaw", "check for updates",
		"is visionclaw up to date", "install the latest version of visionclaw", "what's new in this version of NVDA",
		"what changed in the new version", "what version of windows do I have", "which version of python does nvda use",
		"which model version is visionclaw using", "what version of NVDA does VisionClaw need",
		"which NVDA versions does this add-on support", "write an add-on that says the NVDA version when I press NVDA+Shift+V",
		"which version of the developer guide do I have", "tell me about version control",
		"restore the previous version of this document", "what version is installed", "how are you", "read the title"):
	assert versions.wish(said) is None, (said, versions.wish(said))
	assert planner.hint(said) != "version_info", said
assert planner.hint("check for a new version of visionclaw") == "update_visionclaw"
assert planner.hint("Is there a newer version of VisionClaw?") == "update_visionclaw"
# A question of how is answered with keys, as before.
assert planner.hint("how do I find out which version of NVDA I have") == "explain_keys"

# The job is sure: no model is asked, and no other job stands in for it.
reg = tools.Registry()
reg.add(tools.Tool("version_info", "say which version is installed", lambda task, asked: f"Version: {asked}",
	{"asked": {"type": "string", "description": "what the user asked", "auto": True}}, looks=True))
for said in ASKS:
	assert planner.decided(said, reg) == "version_info", said
assert planner.fitted("nvda_info", "tell me the version of visionclaw I have installed?", "version_info") == "version_info"
assert planner.fitted("addon_question", "what version of the clock add-on do I have", "version_info") == "version_info"
# Understood words still go to it.
grammar = understand.Grammar(None)
for said in ("tell me the version of visionclaw I have installed?", "What visionclaw addon version is installed?",
		"hey visionclaw, which version of nvda have I got"):
	assert planner.hint(grammar.read(said).text) == "version_info", (said, grammar.read(said).text)

# Being new to this: said in the request, or in what the user asked VisionClaw to remember about themselves.
for said in ("I'm a beginner", "I am new to NVDA", "as a beginner screen reader user", "I'm new.", "I've never used a screen reader",
		"I just started using NVDA", "I'm still learning NVDA", "You are new to screen readers."):
	assert versions.beginner(said), said
for said in ("what is new in NVDA", "is there a new version", "You are learning Spanish.", "I'm new to this job at work",
		"Your braille display is a Focus 40.", "a new document"):
	assert not versions.beginner(said), said
assert versions.wish("I am new to NVDA. Which NVDA version is this?")["beginner"]
assert not versions.wish("which version of nvda do I have")["beginner"]

# The answer: one sentence for each thing asked about, and nothing more.
assert versions.answer([{"kind": V, "version": "1.15.1"}]) == "VisionClaw is version 1.15.1."
assert versions.answer([{"kind": N, "version": "2026.3.1"}]) == "NVDA is version 2026.3.1."
assert versions.answer([{"kind": NAMED, "name": "Clock", "version": "2.1", "state": "on", "found": True}]) == "Clock is version 2.1."
assert versions.answer([{"kind": NAMED, "name": "Clock", "version": "2.1", "state": "turned off", "found": True}]) == (
	"Clock is version 2.1. It is turned off.")
assert versions.answer([{"kind": NAMED, "name": "Clock", "version": "", "found": True}]) == "Clock does not say which version it is."
assert versions.answer([{"kind": P, "name": "Notepad", "version": "", "found": True, "program": True}]) == (
	"Notepad does not tell NVDA which version it is.")
assert versions.answer([{"kind": NAMED, "name": "zebra", "found": False, "front": "Notepad"}]).startswith(
	"No add-on called \"zebra\" is installed in NVDA, and the program in front is Notepad.")
both = versions.answer([{"kind": N, "version": "2026.3.1"}, {"kind": V, "version": "1.15.1"}])
assert both == "NVDA is version 2026.3.1.\nVisionClaw is version 1.15.1.", both
# For someone new to this, one sentence each on where to find it next time, with keys every keyboard has.
said = versions.answer([{"kind": V, "version": "1.15.1"}, {"kind": NAMED, "name": "Clock", "version": "2.1", "found": True}], True)
lines = said.split("\n")
assert lines[:2] == ["VisionClaw is version 1.15.1.", "Clock is version 2.1."] and len(lines) == 4, said
assert "NVDA+Alt+U" in lines[2] and "Add-on Store" in lines[3], said
for line in versions._NEXT_TIME.values():
	assert not any(word in line.lower() for word in ("click", "look at", "see the", "blue", "icon")), line
print("OK")
