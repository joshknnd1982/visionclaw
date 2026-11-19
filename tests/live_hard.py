# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""How a control of a stubborn program is worked, judged from what NVDA and Windows report about it, by an everyday
model and by the model for hard cases, the way VisionClaw asks each (accesstools.judge and _hardJudge). The facts are
of controls whose kind NVDA cannot tell and that plain code cannot decide (working.byFacts says nothing), written on
2026-11-19 before anything was run on them, with the ways a sighted person would say. Nothing is clicked.

  python -u tests/live_hard.py EVERYDAYFOLDER everydayCoderId HARDFOLDER hardId
"""
import sys
import time

import harness
from live_orchestrator import OneModelCatalog
from visionClaw.claw import runtime, working
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER
from visionClaw.claw.llm import LLM, MEDIUM

W = working
# (what it is, the facts, the ways that count as right)
FACTS = (
	("a knob of an audio plug-in drawn by JUCE", {"role": "PANE", "name": "Cutoff", "windowClass": "JUCE_1f2a3b4c",
		"states": ["FOCUSABLE"]}, (W.AROUND, W.UPDOWN)),
	("a level control of a VST plug-in", {"role": "GRAPHIC", "name": "Output gain", "windowClass": "VSTGUI",
		"states": ["FOCUSABLE"]}, (W.AROUND, W.UPDOWN, W.SIDEWAYS)),
	("a waveform where a region is chosen", {"role": "UNKNOWN", "name": "Waveform",
		"description": "Click and drag to select a region"}, (W.SIDEWAYS, W.DRAG_TO, W.PAD)),
	("a colour field", {"role": "PANE", "name": "Saturation and brightness"}, (W.PAD,)),
	("a game's minimap", {"role": "CANVAS", "name": "Minimap", "description": "Click to move the camera there"},
		(W.CLICK,)),
	("a list of tracks drawn by the program", {"role": "PANE", "name": "Track list", "children": 40,
		"windowClass": "TListPanel"}, (W.WHEEL, W.CLICK)),
	("a pan control in a Qt mixer", {"role": "UNKNOWN", "name": "Pan", "windowClass": "Qt5QWindowIcon",
		"states": ["FOCUSABLE"]}, (W.SIDEWAYS, W.AROUND, W.UPDOWN)),
	("a timeline with a playhead", {"role": "PANE", "name": "Timeline", "description": "Drag the playhead to move in the song"},
		(W.SIDEWAYS, W.DRAG_TO)),
	("a settings icon with no action reported", {"role": "GRAPHIC", "name": "Settings", "states": ["FOCUSABLE"]}, (W.CLICK,)),
	("a score shown in a game", {"role": "PANE", "name": "Score: 1200"}, (W.SHOWS,)),
	("a game window with a name only", {"role": "EMBEDDEDOBJECT", "name": "Game", "windowClass": "UnityWndClass"},
		(W.UNSURE, W.AIM, W.CLICK)),
	("a tempo field drawn by the program", {"role": "PANE", "name": "Tempo 120 BPM", "states": ["FOCUSABLE"],
		"description": "Double-click to type a tempo, or drag up and down"}, (W.UPDOWN, W.TYPE, W.DOUBLE)),
)


def ask(rt, reasoning, label):
	llm = LLM(rt, taskModule.Task("how controls are worked"))
	right = 0
	started = time.monotonic()
	for what, facts, wanted in FACTS:
		assert working.byFacts(facts) is None and working.telling(facts), what
		begun = time.monotonic()
		answer = working.wayFrom(llm.json(
			CODER, working.CODER_SYSTEM, "What is reported about the control:\n" + working.factsText(facts),
			working.JUDGE_SCHEMA, maxTokens=30, reasoning=reasoning))
		right += answer in wanted
		print(f"{label} {'ok  ' if answer in wanted else 'MISS'} {what}: {answer}   ({time.monotonic() - begun:.1f} s; "
			f"a sighted person: {' or '.join(wanted)})", flush=True)
	print(f"{label}: {right} of {len(FACTS)} as a sighted person would say, {time.monotonic() - started:.0f} s in all.",
		flush=True)


def main():
	sys.stdout.reconfigure(errors="replace")
	if len(sys.argv) < 5:
		sys.exit(__doc__)
	everydayFolder, everydayId, hardFolder, hardId = sys.argv[1:5]
	# The everyday model, asked as accesstools.judge asks it: the coder's question, no reasoning.
	models = OneModelCatalog(everydayFolder, harness.visionMateData())
	chosen = {"backend": "auto", "visionModel": everydayId.replace("-coder", ""), "coderModel": everydayId}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, models, lambda: chosen)
	print("everyday:", rt.entry(CODER)["name"], flush=True)
	try:
		ask(rt, "off", "everyday")
	finally:
		rt.stop()
	# The model for hard cases, asked as accesstools._hardJudge asks it: in a hard case, reasoning medium.
	models = OneModelCatalog(hardFolder, harness.visionMateData())
	entry = next(e for e in models.entries(CODER) if e["id"] == hardId)
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, models, lambda: {"backend": "auto"})
	try:
		with rt.hardCase(entry):
			print("hard:", rt.entry(CODER)["name"], flush=True)
			ask(rt, MEDIUM, "hard")
			print(rt.whereText(), flush=True)
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
