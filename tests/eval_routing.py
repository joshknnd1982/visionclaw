# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Scores how well VisionClaw chooses the job for requests it was never tuned on (phase 5.1).

Each request of tests/eval/requests.json goes through VisionClaw's real planning, with the real model in the
bundled engine: splitting, the router, plain code's decisions, the brief, the model's choice, its check against the
words. The steps are not carried out, so it is fast and changes nothing. A request is right when it has as many parts
as expected and each part got one of the jobs that count as right for it. A question to the user is counted apart:
it is never wrong, and never right either, because the user had to decide.

  python -u tests/eval_routing.py MODELS [reasoning] [visionId] [coderId] [stepwise] [label]

The owner's own settings: MODELS = %APPDATA%/nvda/addons/visionClaw/data/models, auto, qwen3.5-9b,
qwen3.5-9b-coder, always. Results go to tests/eval/results-<label>.json; compare two labels with
  python tests/eval_routing.py --compare LABEL1 LABEL2
"""
import json
import os
import sys
import time

import harness

# VC_PLUGIN: another copy of the add-on to score, as the code of the last release unpacked from git, so that the
# same set is scored before and after a change.
if os.environ.get("VC_PLUGIN"):
	sys.modules["visionClaw"].__path__ = [os.environ["VC_PLUGIN"]]
import live_orchestrator as live  # noqa: E402
from visionClaw.claw import orchestrator, partners, router, runtime, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import VISION

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, "eval")
NOTEPAD = "Program: notepad. Window title: notes.txt - Notepad. Focused control: edit, Text editor."
BROWSER = "Program: chrome. Window title: Weekly News - Google Chrome. Focused control: document, Weekly News. This is a web browser."


class Planner(orchestrator.Orchestrator):
	"""The orchestrator up to its plan: nothing is carried out."""

	def _runSteps(self, llm, task, request, params, start=0, stop=None):
		for step in task.steps:
			if step.tool != tools.ANSWER:
				step.status, step.result = taskModule.STEP_DONE, "(not run)"

	def _nextWays(self, llm, task, request, params):
		return

	def _answer(self, llm, task, request, params, spoken=None, taken=None):
		return ""


def partsOf(task):
	"""The jobs of a plan, one for each part, in order."""
	found, seen = [], []
	for step in task.steps:
		if step.tool == tools.ANSWER:
			continue
		if step.part not in seen:
			seen.append(step.part)
			found.append(step.recipe or "other")
	return found


def judge(got, expect):
	return len(got) == len(expect) and all(recipe in allowed for recipe, allowed in zip(got, expect))


def compare(first, second):
	a = {row["request"]: row for row in json.load(open(os.path.join(EVAL, f"results-{first}.json"), encoding="utf-8"))["rows"]}
	b = {row["request"]: row for row in json.load(open(os.path.join(EVAL, f"results-{second}.json"), encoding="utf-8"))["rows"]}
	for label, rows in ((first, a), (second, b)):
		right = sum(row["verdict"] == "right" for row in rows.values())
		asked = sum(row["verdict"] == "asked" for row in rows.values())
		print(f"{label}: {right} of {len(rows)} right, {asked} asked the user")
	for request in a:
		if request in b and a[request]["verdict"] != b[request]["verdict"]:
			print(f"  {a[request]['verdict']:>5} -> {b[request]['verdict']:<5} {request}  ({a[request]['got']} -> {b[request]['got']})")


def main():
	if sys.argv[1:2] == ["--compare"]:
		compare(sys.argv[2], sys.argv[3])
		return
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	reasoning = sys.argv[2] if len(sys.argv) > 2 else "auto"
	chosen = {"backend": "auto", "visionModel": sys.argv[3] if len(sys.argv) > 3 else "",
		"coderModel": sys.argv[4] if len(sys.argv) > 4 else ""}
	stepwise = sys.argv[5] if len(sys.argv) > 5 else "auto"
	label = sys.argv[6] if len(sys.argv) > 6 else time.strftime("%H%M")
	cat = live.OneModelCatalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found.")
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	partners.setInstalled([partners.JAWS, partners.CLASSIC])
	# VC_SET: which set of tests/eval to score; requests (the first) unless it names another, as requests2.
	data = json.load(open(os.path.join(EVAL, os.environ.get("VC_SET", "requests") + ".json"), encoding="utf-8"))["requests"]
	only = [part.lower() for part in os.environ.get("VC_ONLY", "").split("|") if part]
	rows = []
	started = time.time()
	try:
		for item in data:
			request = item["request"]
			if only and not any(part in request.lower() for part in only):
				continue
			web = bool((item.get("facts") or {}).get("web"))
			asked = []
			orch = Planner(rt, live.makeRegistry(rt, {}), lambda question, choices: asked.append(question) or 0,
				lambda: BROWSER if web else NOTEPAD, None)
			orch.stepwise = lambda: stepwise
			orch.memories = live.KEPT
			orch.program = lambda: "chrome" if web else "notepad"
			orch.skills = live.SKILLS
			orch.facts = lambda: {router.WEB: web, router.CONTROLLER: False, router.DIRECT: False}
			if live.understand is not None:
				orch.understanding = live.understand.Grammar(None)
			task = taskModule.Task(request, reasoning=reasoning)
			start = time.time()
			orch.run(task)
			got = partsOf(task)
			verdict = "right" if judge(got, item["expect"]) and not asked else "asked" if asked else "wrong"
			rows.append({"request": request, "expect": item["expect"], "got": got, "verdict": verdict,
				"asked": asked, "seconds": round(time.time() - start, 1), "state": task.state})
			print(f"{verdict:>5}  {request}  got {got}" + ("" if verdict == "right" else f"  expected {item['expect']}"), flush=True)
			if verdict != "right" and os.environ.get("VC_LOG"):
				for _seconds, kind, text in task.log:
					if kind in (taskModule.TALK, taskModule.DETAIL):
						print(f"        [{kind}] {text[:300]}")
	finally:
		rt.stop()
	right = sum(row["verdict"] == "right" for row in rows)
	askedCount = sum(row["verdict"] == "asked" for row in rows)
	print(f"\n{label}: {right} of {len(rows)} right ({100 * right / max(1, len(rows)):.0f}%), "
		f"{askedCount} asked the user, {len(rows) - right - askedCount} wrong, in {time.time() - started:.0f} seconds.")
	with open(os.path.join(EVAL, f"results-{label}.json"), "w", encoding="utf-8") as f:
		json.dump({"label": label, "models": chosen, "stepwise": stepwise, "rows": rows}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
	main()
