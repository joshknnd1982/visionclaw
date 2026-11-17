# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Has a real model write small NVDA add-ons and debug a failing one, through the bundled engine.

Needs addon/engine (see BUILD.md) and a model on this computer: models downloaded by VisionClaw (pass their
folder as the first argument) or VisionMate's vision data, which then does both jobs. Nothing is loaded into
NVDA: each result is only put through the same check a generated add-on must pass, and printed.

  python tests/live_addon.py [modelsFolder]
"""
import sys
import time

import harness
from live_orchestrator import OneModelCatalog
from visionClaw.claw import microaddons, policy, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import LLM
from visionClaw.claw.tools import ToolError

PURPOSES = (
	"Say hello when I press NVDA+shift+H.",
	"Beep when a link gets the focus.",
	"In notepad, say the name of the focused control when I press NVDA+shift+N.",
	"Say the time when I press NVDA+alt+T.",
)
FAILING = '''import globalPluginHandler
import ui
import api
from scriptHandler import script


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	@script(description="Says the name of the focused control", gesture="kb:NVDA+shift+j")
	def script_sayFocus(self, gesture):
		obj = api.getFocus()
		ui.message(obj.name)
'''
PROBLEMS = [
	"When it ran in NVDA, script_sayFocus failed with AttributeError: module 'api' has no attribute 'getFocus'. "
	"The failing line is line 11, in script_sayFocus: obj = api.getFocus()",
	"api has nothing called getFocus. Names it does have that are close: getFocusObject, getFocusAncestors, "
	"getFocusDifferenceLevel.",
]


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	models = OneModelCatalog(folder, harness.visionMateData())
	if not models.installed(VISION):
		sys.exit("No model found. Download models with VisionClaw, or install VisionMate's vision data.")
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, models, lambda: {"backend": "auto"})
	print("coder:", rt.entry(CODER)["name"], "| reviewer:", rt.entry(VISION)["name"])
	knowledge = Knowledge()
	params = policy.select({"complexity": policy.COMPLEX, "needs_code": True})
	passed = 0
	try:
		for purpose in PURPOSES:
			task = taskModule.Task(purpose)
			notes = knowledge.text(purpose, limit=3, chars=700, sources=("addon-development", "objects-and-events"))
			start = time.time()
			try:
				source = microaddons.write(LLM(rt, task), task, purpose, "Program: notepad.", notes, params, CODER, VISION)
				passed += 1
				print(f"\n=== {purpose}  -> passed the check in {time.time() - start:.1f}s")
				print("   " + " ".join(microaddons.describe(source)))
				print("   " + source.replace("\n", "\n   "))
			except ToolError as e:
				print(f"\n=== {purpose}  -> FAILED in {time.time() - start:.1f}s: {e}")
			for _seconds, kind, text in task.log:
				if kind == taskModule.TALK:
					print(f"   [{kind}] {text}")
		print(f"\n{passed} of {len(PURPOSES)} add-ons passed the check.")
		task = taskModule.Task("fix")
		start = time.time()
		try:
			fixed = microaddons.fix(
				LLM(rt, task), task, "Say the name of the focused control when I press NVDA+shift+J.", FAILING, PROBLEMS,
				"", params, CODER, VISION)
			print(f"\n=== Debugging a failing add-on -> passed the check in {time.time() - start:.1f}s")
			print("   uses getFocusObject:", "getFocusObject" in fixed, "| still uses getFocus():", "getFocus()" in fixed)
			print("   " + fixed.replace("\n", "\n   "))
		except ToolError as e:
			print(f"\n=== Debugging a failing add-on -> FAILED: {e}")
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
