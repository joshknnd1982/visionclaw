# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A real vision model names objects without a name the way object names (nametools.py) ask it: buttons whose text is
drawn into their picture, which with Windows OCR agreeing would be said without "probably" (the drawn text stands in
for what Windows OCR reads, which plain Python cannot reach); and fields, shown with what is before and above them
(naming.pictureBox). Every answer goes through naming.decide, as in nametools. Icon buttons are measured by
tests/live_naming.py, which asks them the same way.

The pictures, the places and the names that count as right were written on 2026-11-19 before anything was run on
them. On the first run a sentence for fields was compared too (10 of 11 with it and without; it was dropped), and the
field with nothing around it was named "Edit field", after which naming.decide drops a name that is itself vague: the
set is spent for that rule. A name that copies an object around it counts as wrong; a field with nothing that says
what it is must get no name. How long each answer took is printed too.

  python -u tests/live_object_names.py MODELS [visionId]
"""
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont

import harness
from live_orchestrator import OneModelCatalog
from live_naming import rightly
from visionClaw.claw import audit, naming, prompts, runtime, working
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import VISION
from visionClaw.claw.llm import LLM
from visionClaw.engine import prepareImage

FONTS = r"C:\Windows\Fonts"
INK, PAPER, LINE = (32, 32, 40), (255, 255, 255), (150, 150, 160)
# The add-on's own default for the picture the model is shown (settings: detailSize).
SIZE = 768


def font(name="segoeui.ttf", size=16):
	try:
		return ImageFont.truetype(os.path.join(FONTS, name), size)
	except OSError:
		return ImageFont.load_default()


# --- Buttons with their text drawn in them ---
# (text on it, font, size, background, ink, an icon before the text, program or website, is it a website, title,
# before it, after it, the words of which one makes a right name)
TEXT_BUTTONS = (
	("Save", "segoeui.ttf", 15, (240, 240, 240), INK, None, "notepad++", False, "new 1 - Notepad++",
		[("button", "Open")], [("button", "Close")], ("save",)),
	("Sign in", "segoeuib.ttf", 16, (26, 115, 232), (255, 255, 255), None, "accounts.example.com", True, "Sign in - Example",
		[("link", "Forgot password")], [("link", "Create account")], ("sign", "signin", "login", "log")),
	("Next", "arial.ttf", 14, (230, 230, 230), INK, None, "setup", False, "Setup - Space Trader",
		[("button", "Back")], [("button", "Cancel")], ("next", "continue")),
	("Add to cart", "segoeuib.ttf", 15, (255, 216, 20), INK, None, "shop.example.com", True, "Headphones - Example Shop",
		[("combo box", "Quantity")], [("button", "Buy now")], ("cart", "add")),
	("Cancel", "tahoma.ttf", 13, (236, 236, 236), INK, None, "setup", False, "Setup - Space Trader",
		[("button", "Next")], [], ("cancel",)),
	("Send", "calibri.ttf", 16, (0, 120, 212), (255, 255, 255), None, "OUTLOOK", False, "Untitled - Message",
		[("edit field", "To")], [("button", "Attach file")], ("send",)),
	("Log out", "segoeui.ttf", 14, (250, 250, 250), (180, 30, 30), None, "mail.example.com", True, "Inbox - Example Mail",
		[("link", "Settings")], [], ("log", "logout", "sign", "signout")),
	("Play", "segoeuib.ttf", 15, (30, 30, 30), (255, 255, 255), "play", "Spotify", False, "Spotify Premium",
		[("button", "Previous")], [("button", "Next")], ("play",)),
)


def textButton(text, fontName, size, back, ink, icon):
	face = font(fontName, size)
	width = int(face.getlength(text)) + (34 if icon else 22)
	height = size * 2 + 6
	image = Image.new("RGB", (width + 8, height + 8), PAPER)
	draw = ImageDraw.Draw(image)
	draw.rounded_rectangle((4, 4, width + 3, height + 3), radius=5, fill=back, outline=LINE)
	x = 15
	if icon == "play":
		draw.polygon(((x, 4 + height // 2 - 6), (x, 4 + height // 2 + 6), (x + 10, 4 + height // 2)), fill=ink)
		x += 16
	draw.text((x, 4 + height // 2), text, font=face, fill=ink, anchor="lm")
	return image


# --- Fields, with what is around them ---
# (what is drawn, the role, program or website, is it a website, title, before it, after it, the words of which one
# makes a right name; none where nothing in the picture says what the field is for)
def form(draw, labels):
	"""A page of a form: labels as (text, x, y), and fields as (x0, y0, x1, y1, inside)."""
	face = font("segoeui.ttf", 15)
	for text, x, y in labels.get("text", ()):
		draw.text((x, y), text, font=face, fill=INK, anchor="lm")
	for x0, y0, x1, y1, inside in labels.get("fields", ()):
		draw.rectangle((x0, y0, x1, y1), fill=PAPER, outline=LINE, width=1)
		if inside == "dots":
			for i in range(6):
				draw.ellipse((x0 + 10 + i * 12, (y0 + y1) // 2 - 3, x0 + 16 + i * 12, (y0 + y1) // 2 + 3), fill=INK)
		elif inside == "magnifier":
			draw.ellipse((x0 + 8, y0 + 7, x0 + 20, y0 + 19), outline=(110, 110, 120), width=2)
			draw.line((x0 + 18, y0 + 17, x0 + 24, y0 + 23), fill=(110, 110, 120), width=2)
		elif inside == "arrow":
			draw.polygon(((x1 - 20, y0 + 12), (x1 - 8, y0 + 12), (x1 - 14, y0 + 19)), fill=INK)
		elif inside == "spin":
			draw.text((x0 + 8, (y0 + y1) // 2), "1", font=face, fill=INK, anchor="lm")
			draw.polygon(((x1 - 16, y0 + 10), (x1 - 6, y0 + 10), (x1 - 11, y0 + 4)), fill=INK)
			draw.polygon(((x1 - 16, y1 - 10), (x1 - 6, y1 - 10), (x1 - 11, y1 - 4)), fill=INK)
		elif inside:
			draw.text((x0 + 8, (y0 + y1) // 2), inside, font=face, fill=(140, 140, 150), anchor="lm")


# Each: the picture's parts, the field to name (its box), its role, and as for buttons.
FIELDS = (
	("label left", {"text": [("First name:", 40, 60)], "fields": [(160, 46, 400, 74, "")]}, (160, 46, 400, 74),
		"EDITABLETEXT", "shop.example.com", True, "Checkout - Example Shop", [], [("edit field", "Last name")], ("first",)),
	("label above", {"text": [("Email address", 40, 40)], "fields": [(40, 56, 340, 84, "")]}, (40, 56, 340, 84),
		"EDITABLETEXT", "shop.example.com", True, "Create account - Example Shop", [("edit field", "Full name")],
		[("edit field", "Password")], ("email", "e-mail", "mail")),
	("password with dots", {"text": [("Password", 40, 60)], "fields": [(160, 46, 400, 74, "dots")]}, (160, 46, 400, 74),
		"PASSWORDEDIT", "accounts.example.com", True, "Sign in - Example", [("edit field", "Email")], [("button", "Sign in")],
		("password",)),
	("search with a magnifier", {"fields": [(40, 40, 360, 70, "magnifier")]}, (40, 40, 360, 70),
		"EDITABLETEXT", "Spotify", False, "Spotify Premium", [("button", "Home")], [("button", "Your library")],
		("search", "find")),
	("phone, label left", {"text": [("Phone number", 40, 60)], "fields": [(170, 46, 400, 74, "")]}, (170, 46, 400, 74),
		"EDITABLETEXT", "OUTLOOK", False, "New contact - Outlook", [("edit field", "Email")], [("edit field", "Address")],
		("phone", "telephone", "number", "mobile")),
	("postcode above", {"text": [("Postcode", 40, 40)], "fields": [(40, 56, 200, 84, "")]}, (40, 56, 200, 84),
		"EDITABLETEXT", "shop.example.com", True, "Checkout - Example Shop", [("edit field", "City")], [("combo box", "Country")],
		("postcode", "post code", "zip", "postal")),
	("placeholder only", {"fields": [(40, 40, 340, 70, "Enter your city")]}, (40, 40, 340, 70),
		"EDITABLETEXT", "weather.example.com", True, "Weather - Example", [("link", "Home")], [("button", "Go")], ("city",)),
	("quantity spin box", {"text": [("Quantity", 40, 60)], "fields": [(140, 46, 220, 74, "spin")]}, (140, 46, 220, 74),
		"SPINBUTTON", "shop.example.com", True, "Headphones - Example Shop", [("combo box", "Colour")],
		[("button", "Add to cart")], ("quantity", "qty", "amount", "number")),
	("country combo box", {"text": [("Country", 40, 60)], "fields": [(140, 46, 380, 74, "arrow")]}, (140, 46, 380, 74),
		"COMBOBOX", "shop.example.com", True, "Checkout - Example Shop", [("edit field", "Postcode")], [("button", "Continue")],
		("country", "region")),
	("second of two in a row", {"text": [("From", 40, 60), ("To", 300, 60)],
		"fields": [(90, 46, 270, 74, ""), (330, 46, 510, 74, "")]}, (330, 46, 510, 74),
		"EDITABLETEXT", "travel.example.com", True, "Flights - Example Travel", [("edit field", "From")],
		[("button", "Search flights")], ("to", "destination", "arrival", "arrive")),
	("nothing says what it is", {"fields": [(40, 40, 340, 70, "")]}, (40, 40, 340, 70),
		"EDITABLETEXT", "game", False, "Space Trader", [("button", "New Game")], [("button", "Quit")], ()),
)


def fieldPicture(parts, box, role):
	"""The page drawn, and the part of it object names show the model: the field with what is before and above it."""
	image = Image.new("RGB", (560, 140), PAPER)
	form(ImageDraw.Draw(image), parts)
	return image.crop(naming.pictureBox(role, box, (0, 0, image.width, image.height)))


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	cat = OneModelCatalog(folder, harness.visionMateData())
	chosen = {"backend": "auto", "visionModel": sys.argv[2] if len(sys.argv) > 2 else "", "coderModel": ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	if rt.entry(VISION) is None:
		sys.exit("No model found.")
	entry = rt.entry(VISION)
	print("vision:", entry["name"], "told where an object is:", working.tellAround(entry), flush=True)
	llm = LLM(rt, taskModule.Task("naming objects"))
	times = []

	def ask(image, question):
		started = time.monotonic()
		answer = llm.json(VISION, prompts.seeing(working.NAME_SYSTEM), question, working.NAME_SCHEMA, maxTokens=24,
			image=image)
		times.append(time.monotonic() - started)
		return audit.cleanName(answer.get("name") if isinstance(answer, dict) else answer)

	try:
		# Warm the engine up, so that its start is not counted as the first answer's time.
		ask(prepareImage(Image.new("RGB", (32, 32), PAPER), SIZE), "Say unknown.")
		times.clear()
		right = sure = 0
		print("Buttons with their text drawn in them:", flush=True)
		for text, fontName, size, back, ink, icon, place, isSite, title, before, after, wanted in TEXT_BUTTONS:
			image = prepareImage(textButton(text, fontName, size, back, ink, icon), SIZE)
			told = working.aroundText(place, isSite, title, before, after)
			name = working.named(lambda around, image=image: ask(image, naming.question("BUTTON", around)), entry, told,
				before + after, [place, title])
			# In NVDA, Windows OCR reads the text exactly; where it agrees with the model the name has no "probably".
			name, isSure = naming.decide(name, text, "", "BUTTON")
			ok = rightly(name, wanted, before + after)
			right += ok
			sure += isSure
			print(f"  {text}: {'ok' if ok else 'MISS'} {name!r}{' (sure)' if isSure else ''}", flush=True)
		print(f"Text buttons named rightly: {right} of {len(TEXT_BUTTONS)}; said without probably: {sure}.", flush=True)

		right = 0
		print("Fields, with what is before and above them:", flush=True)
		for what, parts, box, role, place, isSite, title, before, after, wanted in FIELDS:
			image = prepareImage(fieldPicture(parts, box, role), SIZE)
			told = working.aroundText(place, isSite, title, before, after)
			name = working.named(lambda around, image=image: ask(image, naming.question(role, around)), entry, told,
				before + after, [place, title])
			raw = name
			name = naming.decide(name, "", "", role)[0]
			ok = rightly(name, wanted, before + after)
			right += ok
			print(f"  {what}: {'ok' if ok else 'MISS'} {name!r}" + (f" (the model said {raw!r})" if raw != name else ""),
				flush=True)
		print(f"Fields named rightly: {right} of {len(FIELDS)}.", flush=True)
	finally:
		rt.stop()
	if times:
		times.sort()
		print(f"Seconds an answer took: shortest {times[0]:.1f}, middle {times[len(times) // 2]:.1f}, longest "
			f"{times[-1]:.1f}, over {len(times)} answers.")


if __name__ == "__main__":
	main()
