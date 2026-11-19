# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The answer to a request said a sentence at a time with the real model in the bundled engine: how soon the first
sentence would be spoken, against when the whole answer is ready, with the stand-in tools of
tests/live_orchestrator.py. Each request is run once with the setting on; nothing is spoken, the pieces are written
down with the time they came. Also checks that the pieces together are the answer, and that they say no key with
"plus" and nothing of the model's question.

	python -u tests/live_stream.py MODELS_FOLDER VISIONID CODERID [stepwise]

VC_BACKEND=cpu runs the model on the processor alone, as on a slow computer. VC_ONLY="part one|part two" runs only the requests of tests/eval/answers.json that contain one of those parts; by
default those whose answer a model words. VC_ASK="request one|request two" runs those requests instead."""
import json
import os
import re
import sys
import time

import harness
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_answers  # noqa: E402
import live_orchestrator as live  # noqa: E402
from visionClaw.claw import orchestrator, partners, router, runtime  # noqa: E402
from visionClaw.claw import task as taskModule  # noqa: E402
from visionClaw.claw.catalog import VISION  # noqa: E402

DEFAULT = ("what key tells me the window title|whats the shortcut to start a new game in here|how do i save in space "
	"trader|how do i turn the screen curtain on|what happens when I press nvda f12|tell me what the clock and calendar "
	"addon does")


def words(text):
	return " ".join(str(text).split())


def runItem(rt, item, stepwise):
	asked, state = [], {}
	orch = orchestrator.Orchestrator(rt, live.makeRegistry(rt, state),
		lambda question, choices: asked.append(question) or 0, lambda: eval_answers.GAME, live.Memory("nul"))
	orch.stepwise = lambda: stepwise
	orch.memories = live.KEPT
	orch.program = lambda: "spacetrader"
	orch.skills = live.SKILLS
	orch.facts = lambda: {router.WEB: False, router.CONTROLLER: False, router.DIRECT: False}
	orch.streaming = lambda: True
	if live.understand is not None:
		orch.understanding = live.understand.Grammar(None)
		orch.workFolder = live.WORK
	heard = []
	started = time.time()
	task = taskModule.Task(item["request"], onEvent=lambda task, kind, text: heard.append((time.time() - started, kind, text)))
	orch.run(task)
	return task, heard


def main():
	sys.stdout.reconfigure(errors="replace")
	folder, vision, coder = sys.argv[1:4]
	stepwise = sys.argv[4] if len(sys.argv) > 4 else "auto"
	chosen = {"backend": os.environ.get("VC_BACKEND", "auto"), "visionModel": vision, "coderModel": coder}
	cat = live.OneModelCatalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found.")
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	partners.setInstalled([partners.JAWS, partners.CLASSIC])
	data = json.load(open(os.path.join(eval_answers.EVAL, "answers.json"), encoding="utf-8"))["requests"]
	only = [part.lower() for part in os.environ.get("VC_ONLY", DEFAULT).split("|") if part]
	# VC_ASK="request one|request two": these requests instead, in the live test's game window.
	if os.environ.get("VC_ASK"):
		data = [{"request": request} for request in os.environ["VC_ASK"].split("|") if request]
		only = [""]
	rows = []
	try:
		for item in data:
			if not any(part in item["request"].lower() for part in only):
				continue
			task, heard = runItem(rt, item, stepwise)
			pieces = [(at, text) for at, kind, text in heard if kind == taskModule.SAY]
			answerAt = next((at for at, kind, _text in heard if kind == taskModule.ANSWER), None)
			# When the model began to word the answer: the last step announced is the answer's.
			answerStep = next((at for at, kind, _text in reversed(heard) if kind == taskModule.STEP), None)
			same = words(" ".join(text for _at, text in pieces)) == words(task.answer)
			bad = [text for _at, text in pieces if re.search(r"\bplus\b", text, re.I) or "information found" in text.lower()]
			row = {"request": item["request"], "streamed": task.streamed, "pieces": len(pieces),
				"answerStep": answerStep, "first": pieces[0][0] if pieces else None, "whole": answerAt, "same": same,
				"bad": bad, "answer": task.answer}
			rows.append(row)
			print(f"{item['request']}: streamed {task.streamed}, {len(pieces)} pieces", flush=True)
			if pieces and answerStep is not None and answerAt is not None:
				print(f"   answer step at {answerStep:.1f}s, first piece at {pieces[0][0]:.1f}s "
					f"({pieces[0][0] - answerStep:.1f}s after), whole answer at {answerAt:.1f}s "
					f"({answerAt - answerStep:.1f}s after)")
			print(f"   pieces together are the answer: {same}; pieces with 'plus' or the question's words: {bad}")
			for at, text in pieces:
				print(f"   {at:6.1f}s  {text}")
			print(f"   ANSWER: {task.answer}")
	finally:
		rt.stop()
	streamed = [row for row in rows if row["streamed"] and row["answerStep"] is not None]
	if streamed:
		ahead = [row["whole"] - row["first"] for row in streamed]
		print(f"\n{len(streamed)} of {len(rows)} answers said in pieces; the first piece came on average "
			f"{sum(row['first'] - row['answerStep'] for row in streamed) / len(streamed):.1f}s after the answer step, "
			f"{sum(ahead) / len(ahead):.1f}s before the whole answer was ready "
			f"(at most {max(ahead):.1f}s). Pieces equal the answer in {sum(row['same'] for row in rows)} of {len(rows)}.")


if __name__ == "__main__":
	main()
