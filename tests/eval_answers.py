# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Scores the words of VisionClaw's final answer, with the real model, on requests it was never tuned on (phase 5.1).

tests/eval_routing.py scores only which job is chosen and carries nothing out. Here every request goes through the
whole of VisionClaw, from the words to the answer: every step is carried out with the stand-in tools of
tests/live_orchestrator.py, which change nothing on the computer, and the answer the user would hear is judged by
plain code (tests/answercheck.py):
- the rules for every answer: nothing cut, no Markdown, nothing only a sighted person can follow, no key that exists
  nowhere, no "two models" when one model does both jobs, nothing of the question the model was given, no opening
  words before the answer;
- what the item wants: "says", groups of words of which the answer must have one each, and "never", words it must
  not have. They are facts of the stand-ins: the speech rate is 50, the time NVDA says is 4:05 PM, the focus is on the
  button New Game of Space Trader, the web page is Example Shop.
The job chosen is scored as well where the item has "expect", as in eval_routing.py.

  python -u tests/eval_answers.py MODELS [reasoning] [visionId] [coderId] [stepwise] [label]

VC_SET chooses the set of tests/eval: answers (the development set, the default) or answers-held (the held-out set,
written at the same time, before anything was run on either). Any other set, such as requests6, is scored by the rules
for every answer alone. VC_ONLY="part|part" runs only the requests that contain one of the parts. Results go to
tests/eval/results-answers-<label>.json; compare two with
  python tests/eval_answers.py --compare LABEL1 LABEL2
"""
import json
import os
import sys
import time

import harness

# VC_PLUGIN: another copy of the add-on to score, as the code of the last release unpacked from git.
if os.environ.get("VC_PLUGIN"):
	sys.modules["visionClaw"].__path__ = [os.environ["VC_PLUGIN"]]
import answercheck  # noqa: E402
import live_orchestrator as live  # noqa: E402
from visionClaw.claw import orchestrator, partners, policy, router, runtime, tools  # noqa: E402
from visionClaw.claw import task as taskModule  # noqa: E402
from visionClaw.claw.catalog import VISION  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, "eval")
# Where the user is: the world of the stand-ins. The game Space Trader, or the web page Example Shop.
GAME = "Program: spacetrader. Window title: Space Trader - Main Menu. Focused control: button, New Game."
BROWSER = "Program: chrome. Window title: Example Shop - Google Chrome. Focused control: document, Example Shop. This is a web browser."
# The stand-in tools whose result a model writes: what they say is checked like the answer, and grounds nothing.
BY_MODEL = frozenset(("look",))
RIGHT, WRONG, ASKED = "right", "wrong", "asked"


def jobsOf(task):
	"""The jobs of a plan, one for each part, in order."""
	found, seen = [], []
	for step in task.steps:
		if step.tool == tools.ANSWER:
			continue
		if step.part not in seen:
			seen.append(step.part)
			found.append(step.recipe or "other")
	return found


def sourcesOf(task, request):
	"""What the answer may take its words from: the user's own words and what the tools found, written by plain
	code. A result a model wrote is no source."""
	found = [request, task.request, getattr(task, "original", ""), getattr(task, "said", "")]
	for step in task.steps:
		if step.tool != tools.ANSWER and step.tool not in BY_MODEL and step.result:
			found.append(str(step.result))
	return [text for text in found if text]


def runItem(rt, item, stepwise="auto", reasoning="auto"):
	"""One request of a set from its words to its answer, with a fresh VisionClaw and fresh stand-ins.
	Gives (task, questions put to the user, what the stand-ins were asked to change)."""
	web = bool((item.get("facts") or {}).get("web"))
	asked, state = [], {}
	orch = orchestrator.Orchestrator(rt, live.makeRegistry(rt, state),
		lambda question, choices: asked.append(question) or 0, lambda: BROWSER if web else GAME, live.Memory("nul"))
	orch.stepwise = lambda: stepwise
	orch.memories = live.KEPT
	orch.program = lambda: "chrome" if web else "spacetrader"
	orch.skills = live.SKILLS
	orch.facts = lambda: {router.WEB: web, router.CONTROLLER: False, router.DIRECT: False}
	if live.understand is not None:
		orch.understanding = live.understand.Grammar(None)
		orch.workFolder = live.WORK
	task = taskModule.Task(item["request"], reasoning=reasoning)
	orch.run(task)
	return task, asked, state


def score(task, item, asked, oneModel):
	"""The row of results for one request: its jobs, its answer and what is wrong with the answer."""
	request = item["request"]
	answer = task.answer or ""
	wrong = answercheck.judge(answer, sourcesOf(task, request), item, oneModel)
	jobs = jobsOf(task)
	row = {"request": request, "answer": answer, "state": task.state, "jobs": jobs, "asked": asked,
		"problems": [list(problem) for problem in wrong], "verdict": WRONG if wrong else RIGHT}
	if item.get("expect"):
		fits = len(jobs) == len(item["expect"]) and all(job in allowed for job, allowed in zip(jobs, item["expect"]))
		row["job"] = ASKED if asked and not fits else RIGHT if fits else WRONG
	return row


def summary(rows, label):
	right = sum(row["verdict"] == RIGHT for row in rows)
	text = f"{label}: {right} of {len(rows)} answers right ({100 * right / max(1, len(rows)):.0f}%)"
	jobs = [row for row in rows if "job" in row]
	if jobs:
		text += f"; the job right for {sum(row['job'] == RIGHT for row in jobs)} of {len(jobs)}"
	counts = {}
	for row in rows:
		for rule in {problem[0] for problem in row["problems"]}:
			counts[rule] = counts.get(rule, 0) + 1
	if counts:
		text += ". Answers with each fault: " + ", ".join(
			f"{rule} {counts[rule]}" for rule in answercheck.RULES + (answercheck.MISSING, answercheck.NEVER) if rule in counts)
	return text + "."


def compare(first, second):
	load = lambda label: {row["request"]: row for row in json.load(  # noqa: E731
		open(os.path.join(EVAL, f"results-answers-{label}.json"), encoding="utf-8"))["rows"]}
	a, b = load(first), load(second)
	print(summary(list(a.values()), first))
	print(summary(list(b.values()), second))
	for request in a:
		if request in b and a[request]["verdict"] != b[request]["verdict"]:
			print(f"  {a[request]['verdict']:>5} -> {b[request]['verdict']:<5} {request}")
			for row in (a[request], b[request]):
				print(f"        {row['problems']}  {row['answer']}")


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
	name = os.environ.get("VC_SET", "answers")
	data = json.load(open(os.path.join(EVAL, name + ".json"), encoding="utf-8"))["requests"]
	only = [part.lower() for part in os.environ.get("VC_ONLY", "").split("|") if part]
	answercheck.knownKeys()
	rows = []
	started = time.time()
	try:
		for item in data:
			if only and not any(part in item["request"].lower() for part in only):
				continue
			start = time.time()
			task, asked, state = runItem(rt, item, stepwise, reasoning)
			row = score(task, item, asked, policy.isOneModel(rt))
			row["seconds"], row["changed"] = round(time.time() - start, 1), repr(state)
			rows.append(row)
			job = f" job {row['job']} {row['jobs']}" if "job" in row else f" {row['jobs']}"
			print(f"{row['verdict']:>5}  {item['request']}  ({row['seconds']}s,{job})", flush=True)
			print(f"       ANSWER: {row['answer']}")
			for rule, what in row["problems"]:
				print(f"       {rule}: {what}")
			for question in asked:
				print(f"       ASKED: {question}")
	finally:
		rt.stop()
	print(f"\n{summary(rows, label)} In {time.time() - started:.0f} seconds.")
	with open(os.path.join(EVAL, f"results-answers-{label}.json"), "w", encoding="utf-8") as f:
		json.dump({"label": label, "set": name, "models": chosen, "stepwise": stepwise, "rows": rows}, f,
			ensure_ascii=False, indent=1)


if __name__ == "__main__":
	main()
