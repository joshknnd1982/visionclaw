# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A real model writes the same add-ons two ways: as one piece (microaddons.write, as before 1.11.0) and piece by piece
(claw/codeplan.py). Every add-on that passes the checks is then run against stand-ins for NVDA (tests/addonstandin.py),
to see whether it does what was asked: what it says, whether it beeps, whether it keeps out of other programs. Nothing
is loaded into NVDA. Read every add-on it prints.

The requests and what each must do were written on 2026-11-19, before either way was run on them.

  python -u tests/live_codeplan.py MODELS [visionId] [coderId]
  VC_HARD=qwen3-14b python -u tests/live_codeplan.py MODELS   the model for hard cases writes and reviews, as in a hard case
"""
import contextlib
import os
import re
import sys
import time

import addonstandin as standin
import harness
from live_orchestrator import OneModelCatalog
from visionClaw.claw import codeplan, microaddons, policy, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import LLM
from visionClaw.claw.tools import ToolError

FACTS = "Program: notepad. Window title: notes.txt - Notepad."


def said(fake, *words):
	text = " ".join(fake.said + fake.spoken).lower()
	return all(word.lower() in text for word in words)


def hello(source):
	fake = standin.Fake()
	plugin = standin.load(source, fake)
	return [] if standin.press(plugin, source, "NVDA+shift+h", fake) and said(fake, "hello") else ["NVDA+shift+H does not say hello"]


def linkBeep(source):
	fake = standin.Fake()
	plugin = standin.load(source, fake)
	wrong = []
	if standin.event(plugin, "gainFocus", standin.control("Home", "LINK"), fake) != 1:
		wrong.append("a link's focus is not passed on to NVDA once")
	if not fake.beeps:
		wrong.append("no beep for a link")
	fake.beeps.clear()
	standin.event(plugin, "gainFocus", standin.control("OK", "BUTTON"), fake)
	if fake.beeps:
		wrong.append("it beeps for a button too")
	return wrong


def notepadName(source):
	wrong = []
	fake = standin.Fake(focus=standin.control("Save", "BUTTON", "notepad"))
	plugin = standin.load(source, fake)
	if not standin.press(plugin, source, "NVDA+shift+n", fake) or not said(fake, "save"):
		wrong.append("in Notepad, NVDA+shift+N does not say the name")
	fake = standin.Fake(focus=standin.control("Save", "BUTTON", "chrome"))
	plugin = standin.load(source, fake)
	standin.press(plugin, source, "NVDA+shift+n", fake)
	if said(fake, "save"):
		wrong.append("it says the name in another program too")
	return wrong


def time_(source):
	fake = standin.Fake()
	plugin = standin.load(source, fake)
	ok = standin.press(plugin, source, "NVDA+alt+t", fake) and re.search(r"\d", " ".join(fake.said))
	return [] if ok else ["NVDA+alt+T does not say the time"]


def three(source):
	wrong = []
	fake = standin.Fake()
	plugin = standin.load(source, fake)
	standin.event(plugin, "gainFocus", standin.control("OK", "BUTTON"), fake)
	if not fake.beeps:
		wrong.append("no beep for a button")
	if not standin.press(plugin, source, "NVDA+shift+w", fake) or not said(fake, "inbox"):
		wrong.append("NVDA+shift+W does not say the window's title")
	fake.said.clear()
	standin.event(plugin, "gainFocus", standin.control("Home", "LINK"), fake)
	if not said(fake, "link ahead"):
		wrong.append("a link does not say link ahead")
	return wrong


def firefox(source):
	wrong = []
	fake = standin.Fake(focus=standin.control("Search", "EDITABLETEXT", "firefox"))
	plugin = standin.load(source, fake)
	standin.event(plugin, "gainFocus", standin.control("News", "HEADING", "firefox"), fake)
	if not said(fake, "heading"):
		wrong.append("a heading in Firefox does not say heading")
	fake.said.clear()
	if not standin.press(plugin, source, "NVDA+alt+n", fake) or not said(fake, "search"):
		wrong.append("NVDA+alt+N in Firefox does not say the name")
	fake = standin.Fake(focus=standin.control("Search", "EDITABLETEXT", "chrome"))
	plugin = standin.load(source, fake)
	standin.event(plugin, "gainFocus", standin.control("News", "HEADING", "chrome"), fake)
	standin.press(plugin, source, "NVDA+alt+n", fake)
	if fake.said:
		wrong.append(f"it speaks in Chrome too: {fake.said}")
	return wrong


def checked(source):
	wrong = []
	fake = standin.Fake(focus=standin.control("Hello", "EDITABLETEXT"))
	plugin = standin.load(source, fake)
	standin.event(plugin, "stateChange", standin.control("Bold", "CHECKBOX", states=["CHECKED"]), fake)
	if not said(fake, "checked"):
		wrong.append("a checkbox that gets checked does not say checked")
	fake.said.clear()
	standin.event(plugin, "stateChange", standin.control("Bold", "CHECKBOX"), fake)
	if said(fake, "checked") and not said(fake, "unchecked"):
		wrong.append("it says checked when the checkbox is unchecked")
	fake.said.clear()
	if not standin.press(plugin, source, "NVDA+shift+c", fake) or not said(fake, "5"):
		wrong.append("NVDA+shift+C does not say how many characters the name has")
	return wrong


def typing(source):
	fake = standin.Fake()
	plugin = standin.load(source, fake)
	standin.event(plugin, "typedCharacter", standin.control("Text", "EDITABLETEXT"), fake, ch="a")
	return [] if fake.beeps else ["typing a character does not beep"]


def value(source):
	wrong = []
	fake = standin.Fake(focus=standin.control("Volume", "SLIDER", value="42 percent"))
	plugin = standin.load(source, fake)
	if not standin.press(plugin, source, "NVDA+shift+v", fake) or not said(fake, "42"):
		wrong.append("NVDA+shift+V does not say the value")
	standin.event(plugin, "valueChange", standin.control("Copying", "PROGRESSBAR", value="10 percent"), fake)
	if not fake.beeps:
		wrong.append("a progress bar's change does not beep")
	return wrong


CASES = (
	("Say hello when I press NVDA+shift+H.", hello),
	("Beep when a link gets the focus.", linkBeep),
	("In notepad, say the name of the focused control when I press NVDA+shift+N.", notepadName),
	("Say the time when I press NVDA+alt+T.", time_),
	("Write an add-on that beeps when a button gets the focus, says the title of the window when I press NVDA+shift+W, "
		"and says link ahead whenever a link gets the focus.", three),
	("Make an add-on that only works in firefox: say heading whenever a heading gets the focus, and say the name of the "
		"focused control when I press NVDA+alt+N.", firefox),
	("When a checkbox gets checked, say checked. When I press NVDA+shift+C, say how many characters the name of the "
		"focused control has.", checked),
	("Each time I type a character, beep.", typing),
	("Say the value of the focused control when I press NVDA+shift+V, and beep whenever a progress bar's value changes.", value),
)


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	chosen = {"backend": "auto"}
	if len(sys.argv) > 2:
		chosen["visionModel"] = sys.argv[2]
	if len(sys.argv) > 3:
		chosen["coderModel"] = sys.argv[3]
	models = OneModelCatalog(folder, harness.visionMateData())
	if not models.installed(VISION):
		sys.exit("No model found.")
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, models, lambda: chosen)
	# VC_HARD: the id of a model for hard cases (claw/hardcase.py); it writes and reviews every add-on, as in a hard case.
	hard = os.environ.get("VC_HARD", "")
	hardEntry = next((entry for entry in models.entries(CODER) if entry["id"] == hard), None) if hard else None
	if hard and (hardEntry is None or not models.isInstalled(hardEntry)):
		sys.exit(f"The model for hard cases {hard} is not in {folder}.")
	case = rt.hardCase(hardEntry) if hardEntry else contextlib.nullcontext()
	case.__enter__()
	print("coder:", rt.entry(CODER)["name"], "| reviewer:", rt.entry(VISION)["name"], "| a hard case" if hardEntry else "")
	knowledge = Knowledge()
	params = policy.select({"complexity": policy.COMPLEX, "needs_code": True})._replace(oneModel=policy.isOneModel(rt))
	if hardEntry:
		params = params._replace(oneModel=True, oneByOne=False)
	score = {"one piece": [0, 0, 0.0], "in pieces": [0, 0, 0.0]}
	try:
		# VC_ONLY: only the cases whose request has one of these parts (separated by |); VC_WAYS: only these ways.
		only = [part.lower() for part in os.environ.get("VC_ONLY", "").split("|") if part]
		ways = [way for way in ("one piece", "in pieces") if way in os.environ.get("VC_WAYS", "one piece|in pieces")]
		for purpose, check in CASES:
			if only and not any(part in purpose.lower() for part in only):
				continue
			notes = knowledge.text(purpose, limit=3, chars=700, sources=("addon-development", "objects-and-events"))
			for way in ways:
				task = taskModule.Task(purpose)
				start = time.time()
				try:
					if way == "one piece":
						source = microaddons.write(LLM(rt, task), task, purpose, FACTS, notes, params, CODER, VISION)
					else:
						source = codeplan.write(LLM(rt, task), task, purpose, FACTS, notes, params, CODER, VISION,
							notesFor=lambda words: knowledge.text(words, limit=2, chars=500, sources=("addon-development", "objects-and-events")))
				except ToolError as e:
					print(f"\n=== [{way}] {purpose}\n   -> FAILED the checks in {time.time() - start:.1f}s: {e}")
					score[way][2] += time.time() - start
					continue
				seconds = time.time() - start
				score[way][2] += seconds
				score[way][0] += 1
				if hardEntry and rt.whereText():
					print("   " + rt.whereText())
				try:
					wrong = check(source)
				except Exception as e:
					wrong = [f"it raised {type(e).__name__}: {e}"]
				if not wrong:
					score[way][1] += 1
				print(f"\n=== [{way}] {purpose}\n   -> passed the checks in {seconds:.1f}s; "
					+ ("does what was asked" if not wrong else "WRONG: " + "; ".join(wrong)))
				for _s, kind, text in task.log:
					if kind in (taskModule.TALK, taskModule.DETAIL) and ("piece" in text.lower() or "fault" in text):
						print(f"   [{kind}] {text[:200]}")
				print("   " + source.replace("\n", "\n   "))
		print()
		for way, (passed, right, seconds) in score.items():
			print(f"{way}: {passed} of {len(CASES)} passed the checks, {right} of {len(CASES)} did what was asked, "
				f"{seconds:.0f} seconds in all")
	finally:
		case.__exit__(None, None, None)
		rt.stop()


if __name__ == "__main__":
	main()
