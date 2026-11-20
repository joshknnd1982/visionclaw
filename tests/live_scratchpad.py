# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A real model writes down on the scratchpad the one fact a long result holds that the next step needs
(claw/scratchpad.py), and plain code keeps it or not; then, with --diagnose, the model that writes code says what went
wrong with the newest error of VisionClaw's log that has a place in VisionClaw's code, and writes a correction, which
plain code checks (claw/diagnose.py). Nothing is put in place and nothing is changed: this only measures. The cases
were written on 2026-11-19 before anything was run on them. Read every line: a line that passes the check can still be
the wrong fact.

  python -u tests/live_scratchpad.py MODELS VISIONID CODERID [--diagnose LOGFOLDER]
"""
import os
import sys
import time

import harness
from visionClaw.claw import catalog, diagnose, prompts, runtime, scratchpad
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.llm import LLM, LLMError

# (what the user asked, the step that found something, what it found, the next step, a word the kept line must have)
CASES = (
	("click the Mixer button in Reaper", "Listing the items",
		"\n".join(f"{n}. Button Track {n} arm" for n in range(1, 41)) + "\n41. Mixer (Control+M)\n42. Undo\n43. Redo",
		"Clicking the item", "mixer"),
	("open the Display settings of Windows and turn on night light", "Finding the settings page",
		"Windows Settings pages that fit: System > Display (ms-settings:display): brightness, night light, scale, resolution. "
		+ " ".join(f"Page {n}: something else entirely, about printers number {n}." for n in range(1, 25)),
		"Turning on night light", "display"),
	("read the chart's legend in this Excel workbook", "Looking at the screen",
		"The window shows an Excel workbook named Sales 2026. " + "Cells A1 to F20 hold numbers. " * 12
		+ "A bar chart is on the right; its legend at the bottom lists three series: North, South and West.",
		"Reading the legend", "north"),
	("which landmark is the search form in on this page", "Exploring the page",
		"The page has 6 landmarks: banner, navigation, main, complementary, search, contentinfo. "
		+ "Headings: " + ", ".join(f"Story {n}" for n in range(1, 50)) + ". The search landmark holds the field Search the news.",
		"Moving to the search field", "search"),
	("solve the equation on the screen", "Reading the text that is shown",
		"Homework, page 4. " + "Question text and instructions for the class. " * 15 + "Equation 3: 2x + 6 = 14. Show your work.",
		"Answering the question", "14"),
	("tell me the tempo of track 2 in the mixer", "Listing the items",
		"Track 1 Vocals, volume -3 dB, pan centre. Track 2 Drums, volume 0 dB, tempo 120 BPM. " + "Send and return slots, empty. " * 20,
		"Answering", "120"),
)


def keep(rt):
	kept = right = 0
	for request, step, found, nextTitle, wanted in CASES:
		llm = LLM(rt, taskModule.Task(request))
		started = time.time()
		try:
			wrote = llm.json(VISION, scratchpad.KEEP_SYSTEM, scratchpad.keepQuestion(request, step, nextTitle, found),
				scratchpad.KEEP_SCHEMA, maxTokens=scratchpad.KEEP_TOKENS).get("note")
		except LLMError as e:
			wrote = f"(no answer: {e})"
		checked = scratchpad.checkedNote(wrote, found)
		kept += bool(checked)
		hit = bool(checked) and wanted in checked.lower()
		right += hit
		print(f"\n{request}\n  wrote: {wrote!r} ({time.time() - started:.1f} s)\n  plain code: "
			+ ("kept" if checked else "not kept") + (f"; has \"{wanted}\"" if hit else ""))
	print(f"\nKept {kept} of {len(CASES)}; kept with the fact the next step needs: {right} of {len(CASES)}.")


def diagnoseNewest(rt, logs, root):
	found = diagnose.errors(diagnose.readLogs(logs))
	error = diagnose.chosen(found, {"do": diagnose.FIX}, "")
	frame = diagnose.ownFrame(error, "") if error else None
	if frame is None:
		print("No error of VisionClaw's own code in that log.")
		return
	relative, line, function = frame
	source = open(os.path.join(root, *relative.split("/")), encoding="utf-8").read()
	place = diagnose.functionAt(source, line)
	if place is None or place["name"] != function:
		# The log is from another version: the function is found by its name in the code that is here.
		at = next((n for n, text in enumerate(source.splitlines(), 1) if text.strip().startswith(f"def {function}(")), None)
		place = diagnose.functionAt(source, at + 1) if at else None
	if place is None:
		print(f"{function} is not in {relative} here.")
		return
	print(f"\nThe error: {diagnose.errorText(error, '')}\nThe function: {place['qualname']} in {relative}")
	why = diagnose.refusal(relative, place)
	if why:
		print(f"Not corrected: {why}")
		return
	facts = diagnose.facts(error, "", source, place)
	llm = LLM(rt, taskModule.Task("fix that bug in your code"))
	started = time.time()
	said = llm.text(CODER, prompts.speaking(diagnose.DIAGNOSE_TASK), facts + "\nWhat went wrong?", maxTokens=320, temperature=0.2)
	print(f"\nWhat the model says went wrong ({time.time() - started:.1f} s):\n{said}")
	user = f"{facts}\nThe user asked: \"fix that bug in your code\"\nWrite the whole corrected function."
	problems = []
	for attempt in range(diagnose.TRIES):
		started = time.time()
		asking = user + (f"\nThe correction you wrote before had problems: {' '.join(problems[:3])}" if problems else "")
		answer = llm.text(CODER, prompts.coding(diagnose.FIX_TASK, "fix that bug in your code"), asking, maxTokens=1600,
			temperature=0, code=True)
		candidate = diagnose.bodyAligned(diagnose.tidy(diagnose.extractFunction(answer), place))
		problems = diagnose.checkFix(source, place, candidate) if candidate else ["no function"]
		print(f"\nTry {attempt + 1} ({time.time() - started:.1f} s): " + ("passes plain code's checks" if not problems
			else "problems: " + " ".join(problems)))
		if problems:
			print(candidate)
		if not problems:
			print(diagnose.changeText(place["text"], candidate))
			print(candidate)
			verdict = llm.json(VISION, diagnose.REVIEW_SYSTEM,
				f"{facts}\nThe corrected function:\n```python\n{candidate}```\nDoes it stop the error and change nothing else?",
				diagnose.REVIEW_SCHEMA, maxTokens=160)
			print(f"The other model: {verdict}")
			return
	print("No correction passed the checks.")


# Functions with a real bug, and the call that shows it, written on 2026-11-19 before anything was run on them:
# (the module's text, the line of the error in it, the function, Python's error, the call, what the call must give).
SYNTHETIC = (
	("import textInfos\n\n\nclass Reader:\n\tdef readAhead(self, info):\n\t\tahead = info.copy()\n"
		"\t\tahead.move(textInfos.UNIT_LINE, 20, endPoint=\"end\")\n\t\treturn ahead.text\n",
		7, "readAhead", "OSError: [WinError 1775] A null context handle was passed from the client to the host",
		"Reader().readAhead(Gone())", ""),
	("class Meter:\n\tdef average(self, values):\n\t\ttotal = sum(values)\n\t\treturn total / len(values)\n",
		4, "average", "ZeroDivisionError: division by zero", "Meter().average([])", 0),
	("class Voices:\n\tdef voiceName(self, settings):\n\t\tname = settings[\"voice\"]\n\t\treturn name.title()\n",
		3, "voiceName", "KeyError: 'voice'", "Voices().voiceName({})", ""),
)


class Gone:
	"""A text range whose web page went away while it was read, as NVDA's virtual buffer does."""

	def copy(self):
		return self

	def move(self, *args, **kwargs):
		raise OSError("[WinError 1775] A null context handle was passed from the client to the host")

	text = "unreachable"


def synthetic(rt):
	"""The model that writes code corrects functions with a real bug; plain code checks each, and the corrected function
	is run with the call that failed, to see whether the error is gone."""
	import types
	passed = gone = right = 0
	for source, line, function, exception, call, wanted in SYNTHETIC:
		place = diagnose.functionAt(source, line)
		error = diagnose.Error("2026-11-19 12:00:00", "visionClaw-task", "addon", f"VisionClaw: {function} failed",
			[(f"C:\\x\\globalPlugins\\visionClaw\\reader.py", line, function)], exception, "")
		facts = diagnose.facts(error, "", source, place)
		llm = LLM(rt, taskModule.Task("fix that bug in your code"))
		user = f"{facts}\nThe user asked: \"fix that bug in your code\"\nWrite the whole corrected function."
		problems, candidate = [], ""
		for attempt in range(diagnose.TRIES):
			started = time.time()
			asking = user + (f"\nThe correction you wrote before had problems: {' '.join(problems[:3])}" if problems else "")
			answer = llm.text(CODER, prompts.coding(diagnose.FIX_TASK, "fix that bug in your code"), asking, maxTokens=900,
				temperature=0, code=True)
			candidate = diagnose.bodyAligned(diagnose.tidy(diagnose.extractFunction(answer), place))
			problems = diagnose.checkFix(source, place, candidate) if candidate else ["no function"]
			print(f"\n{function}, try {attempt + 1} ({time.time() - started:.1f} s): "
				+ ("passes plain code's checks" if not problems else "problems: " + " ".join(problems)))
			if not problems:
				break
		print(candidate)
		if problems:
			continue
		passed += 1
		print(diagnose.changeText(place["text"], candidate))
		module = types.ModuleType("reader")
		module.textInfos = types.SimpleNamespace(UNIT_LINE="line")
		exec(diagnose.replaced(source, place, candidate).replace("import textInfos\n", ""), module.__dict__)
		module.Gone = Gone
		try:
			result = eval(call, module.__dict__)
			ok = result == wanted
			gone += 1
			print(f"Run: {call} gives {result!r}" + (", as it should." if ok else f", where {wanted!r} was wanted."))
		except Exception as e:
			ok = False
			print(f"Run: {call} still fails: {type(e).__name__}: {e}")
		right += ok
	print(f"\nPassed plain code's checks: {passed} of {len(SYNTHETIC)}; the error gone when run: {gone} of {len(SYNTHETIC)}; "
		f"giving what was wanted: {right} of {len(SYNTHETIC)}.")


def main():
	sys.stdout.reconfigure(errors="replace")
	args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
	folder = args[0] if args else "no-models-folder"
	cat = catalog.Catalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found.")
	chosen = {"backend": "auto", "visionModel": args[1] if len(args) > 1 else "", "coderModel": args[2] if len(args) > 2 else ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	print("models:", rt.entry(VISION)["name"], "and", rt.entry(CODER)["name"])
	try:
		if "--only-diagnose" not in sys.argv:
			keep(rt)
		if "--synthetic" in sys.argv:
			synthetic(rt)
		if "--diagnose" in sys.argv:
			logs = sys.argv[sys.argv.index("--diagnose") + 1]
			diagnoseNewest(rt, logs, os.path.join(harness.ROOT, "addon", "globalPlugins", "visionClaw"))
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
