# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""How well the real models say how a control is worked. Needs the engine and models on this computer:

    python tests/live_working.py <models folder> <vision model id> <coder model id>

The vision model is shown drawings of controls; the coder model is given the facts of a deep query. Each
answer is printed beside what a sighted person would say. Read every line: drawings are not real programs,
and a small model can be right here and wrong there.
"""
import sys

from PIL import Image, ImageDraw

import harness
from live_orchestrator import OneModelCatalog
from visionClaw.claw import runtime, working
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.llm import LLM
from visionClaw.engine import prepareImage


def canvas():
	image = Image.new("RGB", (220, 160), (236, 236, 236))
	return image, ImageDraw.Draw(image)


def dial():
	image, draw = canvas()
	draw.ellipse((70, 30, 150, 110), fill=(70, 70, 80), outline=(20, 20, 20), width=3)
	draw.line((110, 70, 136, 44), fill=(255, 200, 40), width=6)
	for x, y in ((62, 96), (58, 62), (76, 30), (110, 18), (144, 30), (162, 62), (158, 96)):
		draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(40, 40, 40))
	draw.text((88, 122), "VOLUME", fill=(20, 20, 20))
	return image


def flatSlider():
	image, draw = canvas()
	draw.rectangle((20, 76, 200, 84), fill=(150, 150, 150))
	draw.rectangle((20, 76, 120, 84), fill=(40, 110, 220))
	draw.ellipse((108, 66, 132, 94), fill=(250, 250, 250), outline=(60, 60, 60), width=2)
	draw.text((20, 40), "Brightness", fill=(20, 20, 20))
	return image


def fader():
	image, draw = canvas()
	draw.rectangle((104, 14, 116, 146), fill=(60, 60, 60))
	draw.rectangle((88, 56, 132, 76), fill=(210, 210, 215), outline=(30, 30, 30), width=2)
	draw.line((88, 66, 132, 66), fill=(30, 30, 30), width=2)
	return image


def button():
	image, draw = canvas()
	draw.rounded_rectangle((50, 55, 170, 105), radius=8, fill=(40, 110, 220), outline=(20, 60, 140), width=2)
	draw.text((92, 74), "Start", fill=(255, 255, 255))
	return image


def field():
	image, draw = canvas()
	draw.text((20, 40), "Your name:", fill=(20, 20, 20))
	draw.rectangle((20, 62, 200, 92), fill=(255, 255, 255), outline=(90, 90, 90), width=2)
	draw.line((28, 68, 28, 86), fill=(0, 0, 0), width=1)
	return image


def label():
	image, draw = canvas()
	draw.text((30, 70), "Score: 1250   Lives: 3", fill=(20, 20, 20))
	return image


def holdButton():
	image, draw = canvas()
	draw.ellipse((80, 30, 140, 90), fill=(200, 40, 40), outline=(90, 10, 10), width=3)
	draw.text((58, 104), "Hold to record", fill=(20, 20, 20))
	return image


def infoIcon():
	image, draw = canvas()
	draw.text((20, 70), "Shipping cost", fill=(20, 20, 20))
	draw.ellipse((112, 64, 132, 84), outline=(40, 90, 200), width=2)
	draw.text((120, 68), "i", fill=(40, 90, 200))
	draw.text((20, 110), "Hover for details", fill=(110, 110, 110))
	return image


def swipeBar():
	image, draw = canvas()
	draw.rounded_rectangle((20, 60, 200, 100), radius=20, fill=(210, 210, 215), outline=(120, 120, 120), width=2)
	draw.ellipse((24, 64, 56, 96), fill=(250, 250, 250), outline=(60, 60, 60), width=2)
	draw.text((72, 74), "Swipe to unlock  >>", fill=(60, 60, 60))
	return image


def signature():
	image, draw = canvas()
	draw.rectangle((20, 30, 200, 120), fill=(255, 255, 255), outline=(90, 90, 90), width=2)
	draw.line((30, 100, 190, 100), fill=(150, 150, 150), width=1)
	draw.text((30, 104), "x  Sign here", fill=(120, 120, 120))
	draw.line((40, 90, 60, 60, 75, 92, 95, 55, 110, 90, 150, 70), fill=(20, 20, 120), width=2)
	return image


def timingBar():
	image, draw = canvas()
	draw.text((20, 30), "Click when the marker is in the green!", fill=(20, 20, 20))
	draw.rectangle((20, 70, 200, 94), fill=(200, 60, 60), outline=(40, 40, 40), width=2)
	draw.rectangle((120, 70, 150, 94), fill=(40, 180, 70))
	draw.polygon(((76, 60), (88, 60), (82, 70)), fill=(0, 0, 0))
	draw.line((82, 70, 82, 98), fill=(0, 0, 0), width=3)
	return image


def pad():
	image, draw = canvas()
	draw.rectangle((50, 20, 170, 140), fill=(30, 30, 40), outline=(200, 200, 200), width=2)
	draw.line((110, 20, 110, 140), fill=(70, 70, 90), width=1)
	draw.line((50, 80, 170, 80), fill=(70, 70, 90), width=1)
	draw.ellipse((126, 46, 142, 62), fill=(255, 200, 40), outline=(255, 255, 255), width=2)
	draw.text((52, 144), "X", fill=(20, 20, 20))
	draw.text((36, 24), "Y", fill=(20, 20, 20))
	return image


PICTURES = (
	("a round dial", dial, (working.AROUND, working.UPDOWN)),
	("a slider lying flat", flatSlider, (working.SIDEWAYS,)),
	("an upright fader", fader, (working.UPDOWN,)),
	("a button", button, (working.CLICK,)),
	("a text field", field, (working.TYPE,)),
	("a line of text", label, (working.SHOWS,)),
	# What is worked by neither a click nor a drag along a line.
	("a button that says it is held down", holdButton, (working.HOLD,)),
	("an information icon that says to hover", infoIcon, (working.HOVER,)),
	("a bar that says to swipe", swipeBar, (working.GESTURE, working.SIDEWAYS)),
	("a box to sign in", signature, (working.GESTURE,)),
	("a bar with a moving marker and a green part", timingBar, (working.TIMED,)),
	("a square pad with a point in it", pad, (working.PAD,)),
)
FACTS = (
	("a slider that offers its value", {
		"role": "SLIDER", "roleText": "slider", "name": "Volume", "value": "40", "states": [], "focusable": False,
		"patterns": ["a value in a range"], "range": {"now": 40.0, "low": 0.0, "high": 100.0, "readOnly": False},
		"api": "Windows UI Automation", "windowClass": "HwndWrapper[Mixer]"}, (working.SIDEWAYS, working.UPDOWN)),
	("a pane with an invoke action", {
		"role": "PANE", "roleText": "pane", "name": "Play", "states": [], "focusable": False, "actions": ["invoke"],
		"patterns": ["invoke"], "api": "Windows UI Automation", "windowClass": "Qt5QWindowIcon"}, (working.CLICK,)),
	("a web div with the role slider", {
		"role": "SECTION", "roleText": "section", "name": "", "states": ["CLICKABLE"], "focusable": False,
		"api": "IAccessible2, as browsers use", "web": {"tag": "div", "class": "range-knob", "xml-roles": "slider"},
		"windowClass": "Chrome_RenderWidgetHostHWND"}, (working.SIDEWAYS, working.UPDOWN, working.AROUND)),
	("an editable text", {
		"role": "PANE", "roleText": "pane", "name": "Search", "states": ["FOCUSABLE"], "focusable": True,
		"patterns": ["a value as text"], "api": "Windows UI Automation", "windowClass": "TkChild"}, (working.TYPE,)),
	("a bare window of a game", {
		"role": "PANE", "roleText": "pane", "name": "", "states": [], "focusable": False,
		"api": "its window alone, which reports no accessibility interface", "windowClass": "UnityWndClass"}, (working.UNSURE,)),
	("a static text", {
		"role": "PANE", "roleText": "pane", "name": "Ready", "states": ["READONLY"], "focusable": False,
		"api": "Microsoft Active Accessibility", "windowClass": "Static"}, (working.SHOWS,)),
	# Decided by plain code from the control's own words, from Windows, or from NVDA's states.
	("a button whose name says to hold it", {
		"role": "BUTTON", "roleText": "button", "name": "Hold to talk", "states": ["FOCUSABLE"], "focusable": True,
		"patterns": ["invoke"], "api": "Windows UI Automation", "windowClass": "Chrome_WidgetWin_1"}, (working.HOLD,)),
	("a thing Windows says can be dragged", {
		"role": "PANE", "roleText": "pane", "name": "Card 4", "states": [], "focusable": False, "patterns": ["drag"],
		"api": "Windows UI Automation", "windowClass": "HwndWrapper[Board]"}, (working.DRAG_TO,)),
	("a part of a page that opens a menu", {
		"role": "SECTION", "roleText": "section", "name": "Account", "states": ["CLICKABLE"], "focusable": False,
		"api": "IAccessible2, as browsers use", "web": {"tag": "div", "haspopup": "menu"},
		"windowClass": "Chrome_RenderWidgetHostHWND"}, (working.CHOOSE,)),
	# These two were left to the coder model at first. Qwen2.5 Coder 1.5B got neither and Qwen3.5 9B one of them
	# (2026-11-18), so plain code now knows their words too (working._SAID).
	("a pane described as kept down while speaking", {
		"role": "PANE", "roleText": "pane", "name": "Microphone", "states": ["CLICKABLE"], "focusable": False,
		"description": "Keep the mouse button down on this while you speak, and let go when you are done",
		"api": "IAccessible2, as browsers use", "web": {"tag": "div", "class": "ptt"},
		"windowClass": "Chrome_RenderWidgetHostHWND"}, (working.HOLD,)),
	("a canvas described as for sketching", {
		"role": "CANVAS", "roleText": "canvas", "name": "Sketch", "states": ["CLICKABLE"], "focusable": False,
		"description": "Sketch with the mouse; your strokes are sent when you finish",
		"api": "IAccessible2, as browsers use", "web": {"tag": "canvas", "id": "sketch"},
		"windowClass": "Chrome_RenderWidgetHostHWND"}, (working.GESTURE,)),
)


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	cat = OneModelCatalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found.")
	chosen = {"backend": "auto", "visionModel": sys.argv[2] if len(sys.argv) > 2 else "",
		"coderModel": sys.argv[3] if len(sys.argv) > 3 else ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	print("vision:", rt.entry(VISION)["name"], "| coder:", rt.entry(CODER)["name"])
	llm = LLM(rt, taskModule.Task("how controls are worked"))
	right = 0
	try:
		for what, draw, wanted in PICTURES:
			answer = working.wayFrom(llm.json(
				VISION, working.VISION_SYSTEM, "How does a person work the control in the middle of this picture with a mouse?",
				working.JUDGE_SCHEMA, maxTokens=30, image=prepareImage(draw(), 448)))
			right += answer in wanted
			print(f"{'ok  ' if answer in wanted else 'MISS'} vision, {what}: {answer}   (a sighted person: {' or '.join(wanted)})")
		for what, facts, wanted in FACTS:
			known = working.byFacts(facts)
			if known is not None or not working.telling(facts):
				# Decided without a model: by what the facts say outright, or not asked because they say nothing.
				answer = known or working.UNSURE
				right += answer in wanted
				print(f"{'ok  ' if answer in wanted else 'MISS'} plain code, {what}: {answer}   (a sighted person: {' or '.join(wanted)})")
				continue
			answer = working.wayFrom(llm.json(
				CODER, working.CODER_SYSTEM, "What is reported about the control:\n" + working.factsText(facts),
				working.JUDGE_SCHEMA, maxTokens=30))
			right += answer in wanted
			print(f"{'ok  ' if answer in wanted else 'MISS'} coder, {what}: {answer}   (a sighted person: {' or '.join(wanted)})")
	finally:
		rt.stop()
	print(f"{right} of {len(PICTURES) + len(FACTS)} as a sighted person would say.")


if __name__ == "__main__":
	main()
