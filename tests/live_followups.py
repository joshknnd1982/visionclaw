# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A real model writes requests that follow the one before them out in full (claw/followups.py), and plain code
checks what it wrote. Prints, for each case, what the model wrote, whether plain code stands behind it, and what
was hoped for. Read every line: a rewrite that passes the check can still be wrong.

  python tests/live_followups.py [modelsFolder] [visionModelId] [coderModelId]
"""
import sys
import time

import harness
from visionClaw.claw import catalog, followups, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import VISION
from visionClaw.claw.llm import LLM, LLMError

# (the request before, its answer, what the user says now, a word the full request must have)
CASES = (
	("How do I read the title of this window?", "From NVDA: Reports the title of the current application or foreground window. Keys: NVDA+t.",
		"And the status bar?", "status bar"),
	("What is the speech rate?", "The speech rate is 50.", "and the pitch?", "pitch"),
	("Look through my downloads folder.", "2 items in Downloads. The newest first: 1. setup.exe, 5 MB, in Downloads, changed November 18, "
		"2026, 2. report.pdf, 120 KB, in Downloads, changed November 2, 2026.", "Open the second one.", "report.pdf"),
	("Look through my downloads folder.", "2 items in Downloads. The newest first: 1. setup.exe, 5 MB, in Downloads, changed November 18, "
		"2026, 2. report.pdf, 120 KB, in Downloads, changed November 2, 2026.", "delete the first one", "setup.exe"),
	("Which windows are open?", "3 windows are open: 1. Inbox - Gmail - Google Chrome. 2. Settings. 3. notes.txt - Notepad.",
		"close the last one", "notepad"),
	("Make NVDA speak a little faster.", "Speech rate was 50 and is now 60.", "louder", "louder"),
	("Turn off the typing echo.", "Keyboard speak typed characters was on and is now off.", "what about typed words?", "words"),
	("Find files called budget.", "2 files: budget 2026.xlsx in Documents, budget old.xlsx in Downloads.", "open it", "budget"),
	("Open notepad.", "Opened Notepad.", "and maximize it", "notepad"),
	("What is on my screen?", "The window shows the main menu of Space Trader, with the buttons New Game, Load Game, Options and Quit.",
		"click the third one", "options"),
	("What does NVDA+T do?", "It reports the title of the window.", "and NVDA+F12?", "f12"),
	# These stand alone, though they look as if they leaned on something: the model should copy them unchanged.
	("Make NVDA speak a little faster.", "Speech rate was 50 and is now 60.", "and open notepad", ""),
	("What is on my screen?", "The window shows a calendar.", "read it", ""),
)


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	cat = catalog.Catalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found.")
	chosen = {"backend": "auto", "visionModel": sys.argv[2] if len(sys.argv) > 2 else "", "coderModel": sys.argv[3] if len(sys.argv) > 3 else ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	print("model:", rt.entry(VISION)["name"])
	good = used = 0
	try:
		for before, answer, now, wanted in CASES:
			last = followups.Last(before, answer, 0.0)
			kind = followups.kind(now, last, 10)
			llm = LLM(rt, taskModule.Task(now))
			started = time.time()
			# What plain code makes of it comes first, as in VisionClaw itself; the model is asked only for the rest.
			_kind, plain, _tell = followups.resolve(now, last, 10)
			if kind is None:
				# It stands alone: VisionClaw asks no model, and takes it as it was said.
				written, full = "(not asked: it stands alone)", now
			elif plain:
				written, full = "(not asked: plain code wrote it out)", plain
			else:
				system, question = followups.ask(now, last, kind)
				try:
					written = llm.json(VISION, system, question, followups.SCHEMA, maxTokens=120).get("request")
				except LLMError as e:
					written = f"(no answer: {e})"
				full = followups.checked(written, now, last, mustChange=followups.strong(now))
			changed = bool(full) and full.lower().rstrip(" .?!") != now.lower().rstrip(" .?!")
			fits = (changed and wanted in full.lower()) if wanted else not changed
			used += bool(full)
			good += fits
			print(f"\n{before!r} then {now!r} ({kind}), {time.time() - started:.1f} s")
			print(f"   the model wrote: {written!r}")
			print(f"   taken as: {full!r}; {'as hoped' if fits else 'NOT as hoped (wanted: ' + (wanted or 'the request as it was said') + ')'}")
	finally:
		rt.stop()
	print(f"\n{used} of {len(CASES)} were used by plain code; {good} were as hoped.")


if __name__ == "__main__":
	main()
