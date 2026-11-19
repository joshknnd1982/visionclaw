# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""One piece of an add-on written by a real model, with every answer and every problem printed: to see why a piece
does not pass its checks. Nothing is loaded into NVDA.

  python -u tests/live_piece.py MODELS visionId coderId "the request" [piece number]
"""
import sys
import time

import harness
from live_orchestrator import OneModelCatalog
from visionClaw.claw import codeplan, policy, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import LLM


class Shown(LLM):
	"""The model's calls, printed."""

	def text(self, role, system, user, **options):
		answer = super().text(role, system, user, **options)
		print(f"\n--- asked the {role} model:\n{user}\n--- it wrote:\n{answer}")
		return answer

	def json(self, role, system, user, schema, **options):
		answer = super().json(role, system, user, schema, **options)
		print(f"\n--- asked the {role} model for a form; it gave: {answer}")
		return answer


def main():
	sys.stdout.reconfigure(errors="replace")
	folder, vision, coder, purpose = sys.argv[1:5]
	number = int(sys.argv[5]) if len(sys.argv) > 5 else 1
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, OneModelCatalog(folder, harness.visionMateData()),
		lambda: {"backend": "auto", "visionModel": vision, "coderModel": coder})
	knowledge = Knowledge()
	params = policy.select({"complexity": policy.COMPLEX, "needs_code": True})._replace(oneModel=policy.isOneModel(rt))
	pieces, why = codeplan.read(purpose, "Program: notepad.")
	if not pieces:
		sys.exit(f"Not read into pieces: {why}")
	codeplan.chooseKeys(pieces)
	codeplan.name(pieces)
	piece = pieces[number - 1]
	task = taskModule.Task(purpose)
	start = time.time()
	try:
		codeplan.writePiece(Shown(rt, task), task, piece, number, params, CODER, VISION,
			notesFor=lambda words: knowledge.text(words, limit=2, chars=500, sources=("addon-development", "objects-and-events")))
		print(f"\n=== piece {number} passed in {time.time() - start:.1f}s:\n{piece.body}")
	except codeplan.Fallback as e:
		print(f"\n=== piece {number} did not pass in {time.time() - start:.1f}s: {e}")
	finally:
		rt.stop()
	for _s, kind, text in task.log:
		if kind in (taskModule.TALK, taskModule.DETAIL):
			print(f"   [{kind}] {text}")


if __name__ == "__main__":
	main()
