# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Has a real model write the same small NVDA add-ons twice: once with VisionClaw's own notes alone, and once
with the single lines of the downloaded developer guides that fit the request put before them, as
nvdatools.coderNotes does. Shows whether the guides help a small model or lead it astray.

Needs addon/engine (see BUILD.md), models downloaded by VisionClaw, and the developer guides on this computer:
the folder VisionClaw keeps them in, which is "guides" in VisionClaw's data folder. Nothing is loaded into
NVDA and nothing goes online: each result is put through the check a generated add-on must pass, the names of
NVDA it uses are counted, and it is printed. Read every add-on; a check that passes says little.

  python tests/live_addon_guides.py modelsFolder guidesFolder
"""
import re
import sys
import time

import harness
from live_orchestrator import OneModelCatalog
from visionClaw.claw import guides, microaddons, policy, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import LLM
from visionClaw.claw.tools import ToolError

# What each add-on is for, and the names of NVDA that code doing it has to use.
PURPOSES = (
	("Say hello when I press NVDA+shift+H.", ("ui.message",)),
	("Beep when a link gets the focus.", ("tones.beep", "event_gainFocus")),
	("Copy the name of the focused control to the clipboard when I press NVDA+alt+C.", ("api.getFocusObject", "api.copyToClip")),
	("Say the title of the window in front when I press NVDA+alt+W.", ("api.getForegroundObject", ".name")),
	("Say the text of the navigator object when I press NVDA+alt+N.", ("api.getNavigatorObject",)),
	("Tell me when the name of the focused control changes.", ("event_nameChange",)),
	("Tell me when a part of the page that updates itself changes.", ("event_liveRegionChange",)),
	("Say the window class name of the focused control when I press NVDA+alt+K.", ("windowClassName",)),
	("Say where the focused control is on the screen when I press NVDA+alt+L.", (".location",)),
)


def main():
	sys.stdout.reconfigure(errors="replace")
	if len(sys.argv) < 3:
		sys.exit(__doc__)
	models = OneModelCatalog(sys.argv[1], harness.visionMateData())
	if not models.installed(VISION):
		sys.exit("No model found. Download models with VisionClaw, or install VisionMate's vision data.")
	kept = guides.Guides(sys.argv[2])
	if not kept.here():
		sys.exit("No developer guides in that folder. Ask VisionClaw to get the latest NVDA developer guides first.")
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, models, lambda: {"backend": "auto"})
	print("coder:", rt.entry(CODER)["name"], "| reviewer:", rt.entry(VISION)["name"], "| facts in the guides:", len(kept.facts()))
	knowledge = Knowledge()
	params = policy.select({"complexity": policy.COMPLEX, "needs_code": True})
	score = {False: [0, 0, 0], True: [0, 0, 0]}
	try:
		for purpose, needed in PURPOSES:
			own = knowledge.text(purpose, limit=3, chars=700, sources=("addon-development", "objects-and-events"))
			lines = kept.forCoder(purpose, known=f"{microaddons._SYSTEM}\n{own}")
			print(f"\n##### {purpose}\n   given from the guides: {lines or '(nothing fits, so both runs are the same)'}")
			for withGuides in (False, True):
				if withGuides and not lines:
					continue
				notes = f"{lines}\n{own}" if withGuides else own
				task = taskModule.Task(purpose)
				start = time.time()
				label = "with the guides" if withGuides else "own notes only"
				try:
					source = microaddons.write(LLM(rt, task), task, purpose, "Program: notepad.", notes, params, CODER, VISION)
				except ToolError as e:
					print(f"\n=== {label} -> FAILED in {time.time() - start:.1f}s: {e}")
					score[withGuides][2] += 1
					continue
				used = [name for name in needed if name in source]
				repairs = sum(1 for _s, kind, text in task.log if kind == "detail" and text.startswith("Fixing the code"))
				score[withGuides][0] += 1
				score[withGuides][1] += len(used) == len(needed)
				print(f"\n=== {label} -> passed the check in {time.time() - start:.1f}s, {repairs} repair rounds; "
					f"uses {used} of {list(needed)}; lines: {source.count(chr(10))}")
				print("   " + " ".join(microaddons.describe(source)))
				print("   " + re.sub(r"\n", "\n   ", source))
		for withGuides in (False, True):
			passed, right, failed = score[withGuides]
			print(f"\n{'With the guides' if withGuides else 'Own notes only'}: {passed} passed the check, "
				f"{right} of them use every name the job needs, {failed} failed.")
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
