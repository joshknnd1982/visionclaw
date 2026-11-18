# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Questions in the description window with a real vision model: each is asked as before, with the picture
alone, and as now, with the one command of NVDA the question names, found by plain code (followup.known).
The commands are every command of NVDA 2026.3.1 (tests/nvda_commands.json). Needs the engine and a model:

    python tests/live_followup.py <models folder> [--dry]

With --dry no model is asked: only what would be given with each question is printed.

Nothing is scored: read every answer. A question about how something is done should now name the key of
NVDA's command, exactly, or say that it is not sure; a question about what the picture shows, or about
writing add-ons, must get nothing and be answered as before.
"""
import json
import os
import sys
import time

import harness
from live_orchestrator import OneModelCatalog
from live_prompts import saveDialog, settingsPage
from visionClaw import followup
from visionClaw.claw import lookup, prompts, runtime
from visionClaw.claw.catalog import VISION
from visionClaw.engine import imageMessages, prepareImage

QUESTIONS = (
	("save dialog", saveDialog, "Which button has the focus?"),
	("save dialog", saveDialog, "How do I read the title of this window with the keyboard?"),
	("save dialog", saveDialog, "Which key reads the status bar?"),
	("settings page", settingsPage, "How can I hear which control has the focus?"),
	("settings page", settingsPage, "Which options are turned on?"),
	("settings page", settingsPage, "How would an add-on speak a message when I press a key?"),
	# Here the command plain code finds is not the answer: the model should say that it is not sure of the key.
	("settings page", settingsPage, "How do I move the mouse to this button?"),
	("save dialog", saveDialog, "How do I copy this text to the clipboard?"),
	("save dialog", saveDialog, "Which key opens the NVDA menu?"),
)


# Asked only with --dry, to see what plain code finds.
MORE = (
	("", None, "What colour is the car?"),
	("", None, "How do I get to that button?"),
	("", None, "What do I press to hear the time?"),
	("", None, "How do I move to the next heading?"),
	("", None, "How do I hear the battery status?"),
	("", None, "Which key opens the NVDA menu?"),
	("", None, "How do I turn the screen curtain on?"),
)


def ask(rt, messages, maxTokens):
	start = time.monotonic()
	answer = rt.chat(VISION, messages, maxTokens)
	return " ".join(str(answer or "").split()), time.monotonic() - start


def main():
	sys.stdout.reconfigure(errors="replace")
	if len(sys.argv) < 2:
		sys.exit(__doc__)
	cat = OneModelCatalog(sys.argv[1], harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found.")
	passages = []
	# NVDA's commands, every one of NVDA 2026.3.1, as VisionClaw reads them from the running NVDA.
	with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nvda_commands.json"), encoding="utf-8") as f:
		for command in json.load(f):
			keys = [g.split(":", 1)[1] for g in command["gestures"] if g.startswith(("kb:", "kb(desktop):"))]
			line = f"{command['name']}: {command['description'].rstrip('.')}. Keys: {' or '.join(keys) if keys else 'no key assigned'}."
			passages.append(lookup.fromCommand(command["name"], command["description"], command["category"], line))
	if "--dry" in sys.argv:
		for _name, _draw, question in QUESTIONS + MORE:
			print(f"Q: {question}\n   {followup.known(question, passages).strip() or '(nothing)'}")
		return
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: {"backend": "auto", "visionModel": "", "coderModel": ""})
	print("vision:", rt.entry(VISION)["name"], "| passages:", len(passages))
	prompts.configure()
	described = {}
	try:
		for name, draw, question in QUESTIONS:
			if name not in described:
				start = imageMessages(prepareImage(draw(), 768), prompts.DETAILED, prompts.seeing())
				answer, _took = ask(rt, start, 300)
				described[name] = start + [{"role": "assistant", "content": answer}]
			found = followup.known(question, passages)
			print(f"\n=== {name}: {question}\n   given: {found.strip() or '(nothing: the question is about the picture, or nothing was found)'}")
			for how, extra in (("before", ""), ("now", found)):
				if how == "now" and not found:
					continue
				answer, took = ask(rt, described[name] + [{"role": "user", "content": question + extra + followup.ANSWER}],
					followup.MAX_TOKENS)
				print(f"   {how} ({took:.1f}s): {answer}")
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
