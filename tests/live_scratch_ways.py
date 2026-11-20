# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A real model answers questions from lines of VisionClaw's scratchpads, the way the orchestrator asks it
(orchestrator._ANSWER_TASK with prompts.speaking), once without the instructions for scratchpad lines (as in 1.17.0)
and once with them (prompts.PAD_HELP, 1.18.0). Plain code judges every answer: the names, numbers and keys it must
say, words it must never say, whether it says the line is from a scratchpad, and the rules every answer keeps
(tests/answercheck.py). The cases were written on 2026-11-19 before anything was run on them. Read every answer.

  python -u tests/live_scratch_ways.py MODELS VISIONID CODERID
"""
import sys
import time

import answercheck
import harness
from visionClaw.claw import catalog, lookup, orchestrator, prompts, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import VISION
from visionClaw.claw.llm import LLM, LLMError

# (question, lines found on the scratchpads, groups of words of which the answer must have one each, words it must not have)
CASES = (
	("what is the key to record in Reaper",
		"From the scratchpad of what was learned in REAPER: The Record button has the key Control+R.",
		(("control+r", "ctrl+r"),), ("control+s", "alt+r")),
	("where was the volume slider in Audacity",
		"From the scratchpad of what was learned in Audacity: The volume slider is the third control after the Play button.",
		(("third", "3rd"), ("play",)), ("first control", "second control")),
	("what was the phone number in the picture you described",
		"From the descriptions scratchpad: Described the picture: A flyer for a bake sale on Saturday at 10 in the morning. "
		"Call 555 0142 for tickets.",
		(("555 0142", "555-0142", "5550142"),), ("911",)),
	("what's next on my task",
		"From your task scratchpad: To do: set the speech rate to 60\nFrom your task scratchpad: Done: turn on track "
		"announcements",
		(("speech rate",), ("60", "sixty")), ()),
	("which item is the mixer button",
		"From the scratchpad of what was learned in REAPER: The Mixer button is item 80 of the list.",
		(("80", "eighty"),), ("item 8 ", "item 81")),
	("what key opens the inventory in this game",
		"From the scratchpad of what was learned in Minecraft: E opens the inventory.\nFrom the scratchpad of what was "
		"learned in Minecraft: The pause menu has Save and Quit as its last button.",
		(("e",),), ("control+e", "i opens", "tab opens")),
	("what did you write down about the export dialog",
		"From your task scratchpad: The export dialog asks for the file name first, then the format, MP3 or WAV.",
		(("file name",), ("mp3",), ("wav",)), ("flac",)),
	("did the vocals go on track 2",
		"From the scratchpad of what was learned in REAPER: The vocals were recorded on track 2, named Lead vocal.",
		(("yes", "track 2"),), ("track 3",)),
)


def ask(rt, question, found, withHelp):
	user = f"The user asked: \"{question}\"\nInformation found:\n{lookup.numbered(found)}\n\nAnswer the user."
	before = prompts._FOUND
	if not withHelp:
		prompts._FOUND = tuple(entry for entry in before if entry[0] != "padHelp")
	try:
		system = prompts.speaking(orchestrator._ANSWER_TASK, found=user)
	finally:
		prompts._FOUND = before
	llm = LLM(rt, taskModule.Task(question))
	try:
		return llm.text(orchestrator.policy.LEAD, system, user, maxTokens=200, exact=True).strip()
	except LLMError as e:
		return f"(no answer: {e})"


def judge(answer, question, found, must, never):
	low = " " + " ".join(answer.lower().split()) + " "
	missing = [group for group in must if not any(
		(f" {word} " in low or f" {word}." in low or f" {word}," in low) if len(word) == 1 else word in low for word in group)]
	wrong = [word for word in never if word in low]
	broken = answercheck.problems(answer, [question, found])
	return missing, wrong, broken, "scratchpad" in low or "written down" in low or "wrote down" in low


def main():
	sys.stdout.reconfigure(errors="replace")
	args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
	cat = catalog.Catalog(args[0] if args else "no-models-folder", harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found.")
	chosen = {"backend": "auto", "visionModel": args[1] if len(args) > 1 else "", "coderModel": args[2] if len(args) > 2 else ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	print("models:", rt.entry(VISION)["name"])
	score = {False: [0, 0], True: [0, 0]}
	try:
		for question, found, must, never in CASES:
			print(f"\n== {question}")
			for withHelp in (False, True):
				began = time.time()
				answer = ask(rt, question, found, withHelp)
				missing, wrong, broken, named = judge(answer, question, found, must, never)
				good = not missing and not wrong and not broken
				score[withHelp][0] += good
				score[withHelp][1] += named
				label = "now   " if withHelp else "before"
				print(f"{label} ({time.time() - began:.1f} s) {'PASS' if good else 'MISS'}"
					f"{' says scratchpad' if named else ''}: {answer}")
				if not good:
					print(f"       missing {missing}, never said {wrong}, rules {broken}")
	finally:
		rt.stop()
	count = len(CASES)
	print(f"\nbefore: {score[False][0]} of {count} right, {score[False][1]} say where it is from")
	print(f"now:    {score[True][0]} of {count} right, {score[True][1]} say where it is from")


if __name__ == "__main__":
	main()
