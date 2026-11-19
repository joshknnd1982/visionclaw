# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Which model fits what the user wants to do, suggested by plain code (claw/advice.py), and how requests went with
each model on this computer (planning.Outcomes). Plain Python: no NVDA, no model.

  python tests/test_advice.py
"""
import json
import os
import re
import tempfile

import harness  # noqa: F401
from visionClaw.claw import advice, catalog, planner, planning
from visionClaw.claw.catalog import CODER, VISION

OWNER = {VISION: "qwen3.5-9b", CODER: "qwen3.5-9b-coder"}
STORED = {"qwen3.5-9b", "qwen3.5-9b-coder"}
CARD, RAM = 8151, 31  # the owner's GeForce RTX 5060 Laptop GPU and memory, 2026-11-19

# What is wanted, from the words.
assert advice.purposesOf("which model should I use for describing pictures") == [advice.SEE]
assert advice.purposesOf("which model is best for writing add-ons") == [advice.CODE]
assert advice.purposesOf("which model plans and carries out tasks best") == [advice.PLAN]
assert advice.purposesOf("the 9b is too slow, should I switch") == [advice.FAST]
assert advice.purposesOf("suggest a model for me") == [advice.PLAN, advice.SEE, advice.CODE]
# The jobs: asked for in words, and not where VisionClaw's installed models or a braille display are meant.
for said in ("which model should I use for describing pictures", "should I switch to a smaller model", "which model is best for writing add-ons",
		"recommend a model for planning", "is a different qwen better for coding", "which quant should I use"):
	assert planner.hint(said) == "model_advice", (said, planner.hint(said))
for said, job in (("Which AI model are you using?", "visionclaw_models"), ("What model is installed?", "visionclaw_models"),
		("what model of braille display do I have", "nvda_info")):
	assert planner.hint(said) == job, (said, planner.hint(said))

# On the owner's computer, with one model for both jobs: keep it, say why, what was measured, and how it went here.
said = advice.advise("which model should I use for planning and doing tasks", catalog.CATALOG, OWNER, STORED, CARD, RAM,
	{"qwen3.5-9b": (31, 4)}, (), True)
assert said.startswith("This computer has 8 GB of graphics memory and 31 GB of memory. For planning and carrying out what you ask: "
	"keep Qwen3.5 9B, which you use now"), said
assert "58 of 65 requests in words it had never seen" in said and "went well 31 of 35 times" in said, said
assert said.endswith("VisionClaw only suggests and has changed nothing: to choose, press NVDA+Alt+M, the models window."), said
# Faster: a smaller one in place of what is used, said to be less exact and not measured, and not on the disk.
said = advice.advise("should I switch to a smaller model", catalog.CATALOG, OWNER, STORED, CARD, RAM)
assert "VisionClaw suggests Qwen3.5 4B in place of Qwen3.5 9B" in said and "less exact" in said, said
assert "It is not on your disk yet" in said and "has not been measured" in said, said
# What the user asked to be remembered about a model is their review: a model they said is too slow brings speed in.
said = advice.advise("which model for pictures", catalog.CATALOG, OWNER, STORED, CARD, RAM, {}, ["The 9B model is too slow for me"], True)
assert "For answering faster" in said and "You asked VisionClaw to remember: The 9B model is too slow for me." in said, said
assert advice.remembers(["The 9B model is too slow", "My display is a Focus 40", "I prefer Qwen"]) == ["The 9B model is too slow", "I prefer Qwen"]
# Coding with one model for both jobs: it is kept, as it is loaded once; with two models, a coder that fits.
said = advice.advise("which model is best for writing add-ons", catalog.CATALOG, OWNER, STORED, CARD, RAM, {}, (), True)
assert "For writing and fixing add-ons: keep Qwen3.5 9B" in said, said
said = advice.advise("which model is best for writing add-ons", catalog.CATALOG, {VISION: "qwen3.5-4b", CODER: "qwen2.5-coder-1.5b"},
	{"qwen3.5-4b", "qwen2.5-coder-1.5b"}, CARD, RAM)
assert "VisionClaw suggests Qwen2.5 Coder 7B in place of Qwen2.5 Coder 1.5B" in said, said
# No graphics card: the largest that fits the memory, said to run slower; the very smallest are never suggested.
said = advice.advise("which model for pictures", catalog.CATALOG, {VISION: "qwen3.5-2b", CODER: "qwen2.5-coder-1.5b"}, set(), 0, 8)
assert said.startswith("This computer has no dedicated graphics card, and 8 GB of memory.") and "runs slower" in said, said
assert "0.8B" not in said and "0.5B" not in said
# Every suggestion only says what was measured, word for word from MEASURED, and is short enough to be a tool's answer.
for words in ("suggest a model", "which model for pictures", "smaller model please", "which model for code"):
	for card, ram in ((CARD, RAM), (0, 8), (24000, 64), (4096, 16)):
		said = advice.advise(words, catalog.CATALOG, OWNER, STORED, card, ram, {"qwen3.5-9b": (3, 1)}, (), True)
		assert len(said) <= 1400 and "NVDA+Alt+M" in said and "changed nothing" in said, said
		assert "went well" not in said  # fewer than LEAST_SEEN requests say nothing
		for claim in re.findall(r"Measured: (.*?)\.", said):
			assert any(claim == sentence for _ident, _purpose, sentence in advice.MEASURED), claim
		assert not re.search(r"\b(colou?r|look at|see the|as you can see)\b", said, re.IGNORECASE), said
# The suggested model is always one of the catalog's, in the suggested quant.
for purpose in (advice.PLAN, advice.SEE, advice.CODE, advice.FAST):
	for card, ram in ((CARD, RAM), (0, 8), (24000, 64)):
		entry, _why = advice.pick(purpose, catalog.CATALOG, card, ram, OWNER, True)
		assert entry is not None and catalog.quantOf(entry) == catalog.DEFAULT_QUANT, (purpose, card)
		assert entry.get("suggest", True) is not False or purpose == advice.FAST, entry["id"]

# How requests went with each model on this computer: counted, kept in a file, read back.
folder = tempfile.mkdtemp()
path = os.path.join(folder, "models-went.json")
outcomes = planning.Outcomes(path)
for good in (True, True, False):
	outcomes.keep("qwen3.5-9b", good)
outcomes.keep("", True)  # no model, nothing kept
assert outcomes.counts() == {"qwen3.5-9b": (2, 1)}
assert planning.Outcomes(path).counts() == {"qwen3.5-9b": (2, 1)}
assert json.load(open(path, encoding="utf-8")) == {"qwen3.5-9b": [2, 1]}
open(path, "w", encoding="utf-8").write("not json")
assert planning.Outcomes(path).counts() == {}  # a file that cannot be read is no fault
print("OK")
