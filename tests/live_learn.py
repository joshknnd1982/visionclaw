# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Learns about a program with a real model in the bundled engine and the real internet, and then answers
questions from the notes. Needs addon/engine, a model on this computer, and a connection: it sends the
program's name to Wikipedia, asks Wikidata for its website, and reads a few pages of that website. Nothing is
written outside a temporary folder. Read every note and every answer.

  python tests/live_learn.py modelsFolder [visionModelId] [coderModelId] [program name] [file name] [window title]
"""
import os
import sys
import tempfile
import time

import harness
from visionClaw import net
from visionClaw.claw import catalog, learn, lookup, orchestrator, runtime, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import VISION
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import LLM

AGENT = "VisionClaw (NVDA screen reader add-on)"
QUESTIONS = (
	"How do I duplicate the current line?", "How do I go to the next tab?", "What is this program?",
	"How do I close this?", "What does this do?", "How do I copy text?", "How do I find text?",
)


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	chosen = {"backend": "auto", "visionModel": sys.argv[2] if len(sys.argv) > 2 else "",
		"coderModel": sys.argv[3] if len(sys.argv) > 3 else ""}
	product = sys.argv[4] if len(sys.argv) > 4 else "Notepad++"
	app = sys.argv[5] if len(sys.argv) > 5 else "notepad++"
	title = sys.argv[6] if len(sys.argv) > 6 else f"new 1 - {product}"
	cat = catalog.Catalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found. Download models with VisionClaw first.")
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	print("model:", rt.entry(VISION)["name"])
	try:
		task = taskModule.Task(f"Learn about this program ({product})")
		llm = LLM(rt, task)
		start = time.time()
		name, kind = learn.identify(llm, VISION, app, product, title, "editable text")
		print(f"The model takes {app} / {product!r} / {title!r} to be the {kind} {name}  ({time.time() - start:.1f} s)")
		for facts in (("javaw", "OpenJDK Platform binary", "Space Trader"), ("code", "Visual Studio Code", "main.py - project - Visual Studio Code"),
				("7zfm", "7-Zip", "7-Zip"), ("applicationframehost", "Microsoft Windows Operating System", "Calculator")):
			print("   also:", facts, "->", learn.identify(llm, VISION, *facts))
		written = []

		def write(heading, body):
			began = time.time()
			notes = learn.writeNotes(llm, VISION, name, heading, body)
			written.append((heading, notes, time.time() - began))
			print(f"\n--- {heading}  ({time.time() - began:.1f} s, {len(body)} characters of the page)")
			for note in notes or ["(the model gave nothing that stands in the text; the page's own words are kept)"]:
				print("   -", note)
			return notes

		start = time.time()
		result = learn.study(
			name, kind, lambda url, hosts=None: net.fetchText(url, timeout=15, limit=learn.PAGE_BYTES, hosts=hosts, agent=AGENT, textOnly=True),
			task.cancel, lambda sentence: print("..", sentence), write)
		print(f"\nLearning took {time.time() - start:.1f} s; {len(result['asked'])} requests; not used: {result['failed']}")
		with tempfile.TemporaryDirectory() as temp:
			store = learn.Notes(temp)
			path = store.save(app, learn.notesText(result, app))
			print(learn.summary(result, path))
			notes = learn.passages(store.read(app), name)
		# Questions, with the model choosing the line that answers and saying what "this" means.
		pool = notes + lookup.fromSections(Knowledge().everything()) + [
			lookup.Passage(lookup.APP, "The program in front", f"The program in front is {app}, which is {product}.", f"the program {app}", here=True),
			lookup.Passage(lookup.WINDOW, "The window in front", f"The window in front is called {title}.", "this window", here=True),
			lookup.Passage(lookup.WINDOW, "The control that has the focus", "The focus is on: check box \"Word wrap\". It is not checked.",
				"this window", here=True),
			lookup.Passage(lookup.WINDOW, "Keys of the controls in this window", "Word wrap (check box): Alt+W; Find next (button): F3.", "this window"),
		]

		def lookUp(task, question):
			extra = ""
			if lookup.pointsAt(question):
				choices = [(lookup.PROGRAM_MEANT, f"{app} {product}"), (lookup.WINDOW_MEANT, title), (lookup.CONTROL_MEANT, "check box \"Word wrap\"")]
				said = lookup.saysWhich(question)
				if said:
					meant = next(at for at, (what, _named) in enumerate(choices) if what == said)
					print(f"   the words of \"{question}\" say it is about: {choices[meant][0]}")
				else:
					meant = lookup.referent(LLM(rt, task), VISION, question, choices)
					print(f"   the model takes \"{question}\" to be about: {choices[meant] if meant is not None else None}")
				extra = "Word wrap" if meant == 2 else title if meant == 1 else ""
			return lookup.resultText(lookup.about(question, pool, extra=extra)) or lookup.nothingText(question, app, title, notes=True)

		registry = tools.Registry()
		registry.add(tools.Tool(lookup.TOOL, "answer a question about how to do something or what something is", lookUp,
			{"question": {"type": "string", "description": "the question", "maxLength": 300, "auto": True}},
			looks=True, title="Asking NVDA, the program, the window and Windows"))
		registry.add(tools.Tool(tools.ANSWER, "tell the user the result", lambda task: ""))
		for mode in ("always", "never"):
			print(f"\n##### answers, one small question at a time: {mode}")
			for question in QUESTIONS:
				runner = orchestrator.Orchestrator(
					rt, registry, lambda q, choices: 0,
					lambda: f"Program: {app}. Window title: {title}. Focused control: check box, Word wrap.")
				runner.stepwise = lambda: mode
				asked = taskModule.Task(question)
				start = time.time()
				runner.run(asked)
				print(f"=== {question}  ({time.time() - start:.1f} s)\n   ANSWER: {asked.answer}")
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
