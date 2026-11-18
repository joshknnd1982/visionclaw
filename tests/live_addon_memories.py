# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Has a real model write NVDA add-ons with what the user asked VisionClaw to remember, the user's library and
the notes on accessibility interfaces put before its notes (claw/library.forCoder), as nvdatools does, and
prints each result with what the model was told. Nothing is loaded into NVDA. Read every result: does the
add-on follow the memory (the key the user said, the program it is for), and is it still only what was asked?

  python tests/live_addon_memories.py [modelsFolder]
"""
import os
import sys
import tempfile
import time

import harness
from live_orchestrator import OneModelCatalog
from visionClaw.claw import library, memories, microaddons, policy, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import LLM
from visionClaw.claw.tools import ToolError

# (what the add-on is for, the program in front)
PURPOSES = (
	("In this game, say the amount of money when I press my money key.", ["spacetrader", "Space Trader"]),
	("Announce it when a program sends a UI Automation notification event.", []),
)


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	models = OneModelCatalog(folder, harness.visionMateData())
	if not models.installed(VISION):
		sys.exit("No model found. Download models with VisionClaw, or install VisionMate's vision data.")
	chosen = {"backend": "auto", "visionModel": sys.argv[2] if len(sys.argv) > 2 else "",
		"coderModel": sys.argv[3] if len(sys.argv) > 3 else ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, models, lambda: chosen)
	print("coder:", rt.entry(CODER)["name"])
	base = tempfile.mkdtemp()
	kept = memories.Memories(os.path.join(base, "memories"))
	kept.add("in this game my money key is NVDA+shift+M", program="spacetrader")
	kept.add("I prefer short answers")
	shelf = library.Library(os.path.join(base, "library"))
	shelf.prepare()
	with open(os.path.join(shelf.folder, "Space Trader manual.txt"), "w", encoding="utf-8") as f:
		f.write("MONEY\nYour money is shown in the status bar of the main window, as Credits: followed by the amount.\n")
	knowledge = Knowledge()
	params = policy.select({"complexity": policy.COMPLEX, "needs_code": True})
	try:
		for purpose, program in PURPOSES:
			task = taskModule.Task(purpose)
			notes = knowledge.text(purpose, limit=3, chars=700, sources=("addon-development", "objects-and-events"))
			mine = library.forCoder(kept, shelf, knowledge, purpose, program).strip()
			if mine:
				notes = f"{mine}\n{notes}"
			print(f"\n=== {purpose}\n   TOLD FIRST:\n   " + mine.replace("\n", "\n   "))
			start = time.time()
			try:
				source = microaddons.write(LLM(rt, task), task, purpose, f"Program: {program[0] if program else 'notepad'}.",
					notes, params, CODER, VISION)
				print(f"   -> passed the check in {time.time() - start:.1f}s")
				print("   " + " ".join(microaddons.describe(source)))
				print("   " + source.replace("\n", "\n   "))
			except ToolError as e:
				print(f"   -> FAILED in {time.time() - start:.1f}s: {e}")
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
