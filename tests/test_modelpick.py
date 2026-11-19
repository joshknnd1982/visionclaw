# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Which model does each job when the user lets VisionClaw pick (claw/modelpick.py), on made-up computers. Plain
Python: no NVDA, no model, no graphics card.

  python tests/test_modelpick.py
"""
import harness  # noqa: F401
from visionClaw.claw import catalog, modelpick, planner
from visionClaw.claw.catalog import CODER, VISION

ALL = catalog.CATALOG


def picked(request, installed, card, ram=16, **more):
	return modelpick.pick(request, ALL, installed, card, ram, planner.quickTriage(request), **more)


def ids(found):
	return found.ids()[VISION], found.ids()[CODER]


# The owner's computer: the 9B for both jobs on an 8 GB card. It does everything, and nothing more is loaded.
owner = {"qwen3.5-9b", "qwen3.5-9b-coder"}
for request in ("speak faster", "describe the screen", "write an add-on that beeps when a link gets the focus"):
	found = picked(request, owner, 8151, 31)
	assert ids(found) == ("qwen3.5-9b", "qwen3.5-9b-coder"), (request, found)
	assert modelpick.sameFile(found.vision, found.coder)
text = modelpick.pickedText(picked("speak faster", owner, 8151, 31))
assert text.startswith("For planning what to do, VisionClaw picked Qwen3.5 9B: the largest model here that fits your "
	"graphics card"), text
assert "For checking the plan, the same model: the model that plans checks its own plan" in text, text
# One model is never called two, and no model's role is named in what the user is told.
for request in ("describe the screen", "write an add-on", "speak faster"):
	said = modelpick.pickedText(picked(request, owner, 8151, 31)).lower()
	for wrong in ("both models", "the two models", "the other model", "the vision model", "the coder model", "agree"):
		assert wrong not in said, (request, wrong, said)

# Several models here, an 8 GB card: the largest that fits plans; the 9B does not fit beside it with a coder.
several = {"qwen3.5-2b", "qwen3.5-4b", "qwen3.5-4b-coder", "qwen2.5-coder-1.5b", "qwen3.5-0.8b"}
found = picked("turn off the typing echo", several, 8151)
assert ids(found) == ("qwen3.5-4b", "qwen3.5-4b-coder"), found
# Writing code: a model for code beside the 4B on the card (4.4 + 1.8 + 0.2 <= 7.96) is smaller than the 4B's own
# twin (3.8), so the twin writes the code and nothing more is loaded.
found = picked("write an add-on that says the time with NVDA+Alt+T", several, 8151)
assert ids(found) == ("qwen3.5-4b", "qwen3.5-4b-coder"), found
assert found.why[CODER].startswith("the model that plans, which writes code too"), found.why
# With a larger model for code on the disk and a card of 12 GB, it writes the code beside the model that plans.
withCoder = several | {"qwen2.5-coder-7b"}
found = picked("write an add-on that says the time with NVDA+Alt+T", withCoder, 12288)
assert ids(found) == ("qwen3.5-4b", "qwen2.5-coder-7b"), found
assert "beside the model that plans" in found.why[CODER]
assert "For writing code, Qwen2.5 Coder 7B" in modelpick.pickedText(found), modelpick.pickedText(found)
# Not a request for code: the model that plans checks its own plan, and the 7B is not loaded for it.
assert ids(picked("what time is it", withCoder, 12288)) == ("qwen3.5-4b", "qwen3.5-4b-coder")
# On a card too small for the 7B beside the 4B (8 GB), the twin writes the code.
assert ids(picked("write an add-on that says the time", withCoder, 8151)) == ("qwen3.5-4b", "qwen3.5-4b-coder")

# No graphics card: the largest that fits the memory, and said to be slower.
found = picked("describe the screen", several, 0, 16)
assert ids(found)[0] == "qwen3.5-4b", found
assert "runs slower" in found.why[VISION]
found = picked("describe the screen", several, 0, 6)
assert ids(found)[0] == "qwen3.5-2b", found  # 4.4 GB is more than 45 percent of 6 GB; 2.6 GB is not
# Only a coder model for the second job that is not the planner's twin: the smallest suggested, loaded already wins.
small = {"qwen3.5-2b", "qwen2.5-coder-1.5b", "qwen2.5-coder-0.5b"}
assert ids(picked("what time is it", small, 4096)) == ("qwen3.5-2b", "qwen2.5-coder-1.5b")
assert ids(picked("what time is it", small, 4096, loaded={"qwen2.5-coder-0.5b"})) == ("qwen3.5-2b", "qwen2.5-coder-0.5b")

# The user asked for speed: a simple request is planned by the fastest suggested model; a picture, code or a hard
# request still gets the largest. The 0.8B is never suggested, so the 2B is the fastest suggested.
fast = ("the 9B is too slow for me",)
big = several | {"qwen3.5-9b", "qwen3.5-9b-coder"}
assert ids(picked("speak faster", big, 12288, remembered=fast))[0] == "qwen3.5-2b"
assert "you asked for faster answers" in picked("speak faster", big, 12288, remembered=fast).why[VISION]
assert ids(picked("describe the screen", big, 12288, remembered=fast))[0] == "qwen3.5-9b"
assert ids(picked("write an add-on that beeps", big, 12288, remembered=fast))[0] == "qwen3.5-9b"
assert ids(picked("speak faster", big, 12288))[0] == "qwen3.5-9b"
assert not modelpick.wantsSpeed(("my braille display is a Focus 40", "I like short answers"))

# The user's own review: a model with which requests went badly here is passed over while another can plan.
went = {"qwen3.5-4b": (2, 8)}
assert ids(picked("speak faster", several, 8151, outcomes=went))[0] == "qwen3.5-2b"
assert ids(picked("speak faster", several, 8151, outcomes={"qwen3.5-4b": (2, 2)}))[0] == "qwen3.5-4b"  # too few to count
assert ids(picked("speak faster", {"qwen3.5-4b", "qwen3.5-4b-coder"}, 8151, outcomes=went))[0] == "qwen3.5-4b"  # nothing else

# Two quants of one model: the one the user chose wins, else the one loaded, else Q4_K_M.
quants = {"qwen3.5-4b", "qwen3.5-4b-q6k"}
assert ids(picked("speak faster", quants, 8151))[0] == "qwen3.5-4b"
assert ids(picked("speak faster", quants, 8151, chosen={"qwen3.5-4b-q6k"}))[0] == "qwen3.5-4b-q6k"
assert ids(picked("speak faster", quants, 8151, loaded={"qwen3.5-4b-q6k"}))[0] == "qwen3.5-4b-q6k"

# A model only for hard cases ("edge") is never picked here, whatever its size.
edge = dict(next(entry for entry in ALL if entry["id"] == "qwen2.5-coder-7b"), id="hard-case-coder", edge=True, memoryGb=6.5)
found = modelpick.pick("write an add-on that beeps", ALL + [edge], {"qwen3.5-2b", "hard-case-coder", "qwen2.5-coder-1.5b"},
	12288, 16, planner.quickTriage("write an add-on that beeps"))
assert ids(found) == ("qwen3.5-2b", "qwen2.5-coder-1.5b"), found
# Nothing to plan with on the disk: nothing is picked, and the user's own choice stays.
assert not picked("speak faster", {"qwen2.5-coder-1.5b"}, 8151)
assert modelpick.pickedText(picked("speak faster", set(), 8151)) == ""
# A model that is not on the disk is never picked.
assert all(ident in big for ident in ids(picked("describe the screen", big, 99999)))

# The jobs, from the words and plain code's first sorting.
assert modelpick.jobsOf("describe the screen", planner.quickTriage("describe the screen")) == ["plan", "see", "check"]
assert modelpick.jobsOf("write an add-on that beeps", planner.quickTriage("write an add-on that beeps")) == ["plan", "code"]
assert modelpick.jobsOf("speak faster", planner.quickTriage("speak faster")) == ["plan", "check"]
assert modelpick.settingText(modelpick.AUTO).startswith("VisionClaw picks the model for each job itself")
assert modelpick.settingText(modelpick.MINE) == ""

# The user chose the models: asked which models VisionClaw uses, it says which it would pick, only where they differ.
same = modelpick.suggestionText(picked("", owner, 8151, 31), picked("write an add-on", owner, 8151, 31),
	{VISION: "qwen3.5-9b", CODER: "qwen3.5-9b-coder"})
assert same == "", same
said = modelpick.suggestionText(picked("", withCoder, 12288), picked("write an add-on", withCoder, 12288),
	{VISION: "qwen3.5-2b", CODER: "qwen2.5-coder-1.5b"})
assert said.startswith("Of the models on this computer, VisionClaw would choose differently. For planning and pictures it "
	"would pick Qwen3.5 4B: the largest model here that fits your graphics card"), said
assert "For writing code it would pick Qwen2.5 Coder 7B" in said and said.endswith("nothing changes until you do."), said
said = modelpick.suggestionText(picked("", several, 8151), picked("write an add-on", several, 8151),
	{VISION: "qwen3.5-2b", CODER: "qwen2.5-coder-1.5b"})
assert "For writing code it would use Qwen3.5 4B too" in said, said
assert modelpick.suggestionText(modelpick.Pick(), modelpick.Pick(), {}) == ""
print("OK")
