# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Compares two quants of one coder model writing NVDA add-ons, through the bundled engine.

The same requests as tests/live_addon.py, each written several times by each quant. The model is its own
reviewer, so that the only difference between the runs is the model's weights file. Counted for each quant: the
add-ons that pass the checks, those that pass with no repair round, the repair rounds, the time, and whether the
failing add-on is debugged to api.getFocusObject. Every add-on is written to a file to be read. Nothing is loaded
into NVDA.

  python tests/live_quants.py modelsFolder [times] [coder id ...]
  python tests/live_quants.py %APPDATA%/nvda/visionClaw/models 3 qwen2.5-coder-1.5b qwen2.5-coder-1.5b-q6k
"""
import os
import sys
import tempfile
import time

import harness
from live_addon import FAILING, PROBLEMS, PURPOSES
from visionClaw.claw import catalog, microaddons, policy, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import LLM
from visionClaw.claw.tools import ToolError


def repairs(task):
	return sum(1 for _s, _kind, text in task.log if str(text).startswith("Fixing the code"))


def measure(folder, coderId, times, out):
	models = catalog.Catalog(folder)
	entry = models.get(coderId)
	if entry is None or not models.isInstalled(entry):
		sys.exit(f"{coderId} is not on this computer.")
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, models, lambda: {"backend": "auto", "coderModel": coderId})
	knowledge = Knowledge()
	params = policy.select({"complexity": policy.COMPLEX, "needs_code": True})
	params = params._replace(oneModel=True)
	found = {"written": 0, "passed": 0, "first": 0, "repairs": 0, "seconds": 0.0, "fixed": 0, "fixRuns": 0}
	try:
		for round_ in range(times):
			for number, purpose in enumerate(PURPOSES, 1):
				task = taskModule.Task(purpose)
				notes = knowledge.text(purpose, limit=3, chars=700, sources=("addon-development", "objects-and-events"))
				start = time.time()
				try:
					source = microaddons.write(LLM(rt, task), task, purpose, "Program: notepad.", notes, params, CODER, CODER)
					result = "passed"
				except ToolError as e:
					source, result = "", f"FAILED: {e}"
				seconds = time.time() - start
				found["written"] += 1
				found["seconds"] += seconds
				found["repairs"] += repairs(task)
				if source:
					found["passed"] += 1
					found["first"] += repairs(task) == 0
				print(f"{coderId} round {round_ + 1} add-on {number}: {result}, {repairs(task)} repair rounds, {seconds:.1f}s",
					flush=True)
				out.write(f"\n=== {coderId}, round {round_ + 1}: {purpose}\n{result}, {repairs(task)} repair rounds\n{source}\n")
			task = taskModule.Task("fix")
			start = time.time()
			found["fixRuns"] += 1
			try:
				fixed = microaddons.fix(
					LLM(rt, task), task, "Say the name of the focused control when I press NVDA+shift+J.", FAILING,
					PROBLEMS, "", params, CODER, CODER)
				good = "getFocusObject" in fixed and "getFocus()" not in fixed
				found["fixed"] += good
				print(f"{coderId} round {round_ + 1} debugging: passed the check, getFocusObject {good}, "
					f"{repairs(task)} repair rounds, {time.time() - start:.1f}s", flush=True)
				out.write(f"\n=== {coderId}, round {round_ + 1}: debugging\n{fixed}\n")
			except ToolError as e:
				print(f"{coderId} round {round_ + 1} debugging: FAILED: {e}", flush=True)
	finally:
		rt.stop()
	return found


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1]
	times = int(sys.argv[2]) if len(sys.argv) > 2 else 3
	ids = sys.argv[3:] or ["qwen2.5-coder-1.5b", "qwen2.5-coder-1.5b-q6k"]
	path = os.path.join(tempfile.gettempdir(), "visionclaw-live-quants.txt")
	results = {}
	with open(path, "w", encoding="utf-8") as out:
		for ident in ids:
			results[ident] = measure(folder, ident, times, out)
	print(f"\nEvery add-on is in {path}.")
	for ident, r in results.items():
		print(f"{ident}: {r['passed']} of {r['written']} passed the checks, {r['first']} with no repair round, "
			f"{r['repairs']} repair rounds in all, {r['seconds'] / max(r['written'], 1):.1f}s each; "
			f"debugging to getFocusObject {r['fixed']} of {r['fixRuns']}.")


if __name__ == "__main__":
	main()
