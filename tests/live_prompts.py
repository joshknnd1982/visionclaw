# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The instructions for blind users (claw/prompts.py) with a real vision model. Each drawn picture is
described as VisionClaw did before they existed (the request alone, with its honesty sentence) and as it does
now (the same request, with prompts.seeing() as the first message), quickly and in one sentence, and a
follow-up question is asked of both. Needs the engine and a model on this computer:

    python tests/live_prompts.py <models folder> <vision model id>

Nothing is scored: read every answer. Look for answers that start with what is shown, read the text exactly,
say what is focused, checked or greyed out, and use no Markdown.
"""
import sys
import time

from PIL import Image, ImageDraw, ImageFilter

import harness
from live_orchestrator import OneModelCatalog
from visionClaw import followup
from visionClaw.claw import prompts, runtime
from visionClaw.claw.catalog import VISION
from visionClaw.engine import imageMessages, prepareImage

# What every request ended with before claw/prompts.py.
OLD_HONESTY = (
	" If text is too small or blurry to read, say so instead of guessing it. "
	"Do not guess who a person is or how old they are."
)


def saveDialog():
	image = Image.new("RGB", (520, 220), (240, 240, 240))
	draw = ImageDraw.Draw(image)
	draw.rectangle((0, 0, 520, 30), fill=(255, 255, 255))
	draw.text((10, 9), "Notepad", fill=(0, 0, 0))
	draw.text((30, 60), "Do you want to save changes to Shopping list.txt?", fill=(0, 40, 140))
	for i, (label, focused) in enumerate((("Save", True), ("Don't Save", False), ("Cancel", False))):
		x = 170 + i * 115
		draw.rectangle((x, 160, x + 100, 190), fill=(225, 238, 252) if focused else (253, 253, 253),
			outline=(0, 120, 215) if focused else (170, 170, 170), width=3 if focused else 1)
		draw.text((x + 20, 170), label, fill=(0, 0, 0))
	return image


def settingsPage():
	image = Image.new("RGB", (480, 260), (255, 255, 255))
	draw = ImageDraw.Draw(image)
	draw.text((20, 15), "Sound settings", fill=(0, 0, 0))
	for i, (label, checked) in enumerate((("Play sounds", True), ("Start with Windows", False), ("Mute when locked", True))):
		y = 60 + i * 40
		draw.rectangle((20, y, 36, y + 16), outline=(60, 60, 60), width=2, fill=(0, 120, 215) if checked else (255, 255, 255))
		if checked:
			draw.line((23, y + 8, 28, y + 13, 34, y + 3), fill=(255, 255, 255), width=2)
		draw.text((46, y + 3), label, fill=(0, 0, 0))
	draw.rectangle((20, 200, 140, 230), outline=(200, 200, 200), fill=(245, 245, 245))
	draw.text((40, 210), "Advanced...", fill=(180, 180, 180))
	draw.rectangle((340, 200, 460, 230), outline=(0, 120, 215), fill=(0, 120, 215))
	draw.text((385, 210), "Apply", fill=(255, 255, 255))
	return image


def scene():
	image = Image.new("RGB", (400, 260), (135, 200, 250))
	draw = ImageDraw.Draw(image)
	draw.rectangle((0, 190, 400, 260), fill=(70, 160, 70))
	draw.ellipse((320, 20, 370, 70), fill=(255, 220, 40))
	draw.rectangle((90, 120, 210, 200), fill=(200, 80, 60))
	draw.polygon(((80, 120), (150, 70), (220, 120)), fill=(120, 60, 40))
	draw.rectangle((140, 160, 165, 200), fill=(90, 50, 30))
	draw.rectangle((280, 130, 295, 200), fill=(100, 70, 40))
	draw.ellipse((255, 80, 320, 145), fill=(40, 130, 50))
	return image


def blurred():
	image = Image.new("RGB", (420, 140), (255, 255, 255))
	draw = ImageDraw.Draw(image)
	draw.text((20, 20), "Error 0x80070057", fill=(180, 0, 0))
	draw.text((20, 60), "The parameter is incorrect. Contact your administrator.", fill=(0, 0, 0))
	return image.resize((105, 35)).resize((420, 140)).filter(ImageFilter.GaussianBlur(1.5))


PICTURES = (
	("save dialog", saveDialog, "Which button has the focus?"),
	("settings page", settingsPage, "Which options are turned on, and can I press Advanced?"),
	("drawn scene", scene, "Is there a person in it?"),
	("blurred error", blurred, "What is the error number?"),
)


def ask(rt, messages, maxTokens):
	start = time.monotonic()
	answer = rt.chat(VISION, messages, maxTokens)
	return " ".join(str(answer or "").split()), time.monotonic() - start


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	cat = OneModelCatalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found.")
	chosen = {"backend": "auto", "visionModel": sys.argv[2] if len(sys.argv) > 2 else "", "coderModel": ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	print("vision:", rt.entry(VISION)["name"])
	prompts.configure()
	try:
		for name, draw, question in PICTURES:
			jpeg = prepareImage(draw(), 768)
			print(f"\n=== {name}")
			for how, system, honesty in (("before", None, ""), ("now", prompts.seeing(), "")):
				for mode, request, tokens in (("quick", prompts.QUICK, 200), ("one sentence", prompts.BRIEF, 80)):
					start = imageMessages(jpeg, request + honesty, system)
					answer, took = ask(rt, start, tokens)
					print(f"  {how}, {mode} ({took:.1f}s): {answer}")
					if mode == "quick":
						follow = start + [{"role": "assistant", "content": answer},
							{"role": "user", "content": question + followup.ANSWER}]
						answer, took = ask(rt, follow, followup.MAX_TOKENS)
						print(f"  {how}, asked \"{question}\" ({took:.1f}s): {answer}")
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
