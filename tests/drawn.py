# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Pictures drawn by the tests, with the words a reading of them would give: a printed form that is only a
picture, a form of a web page with a field outlined in red, a product photo, swatches, a puzzle of tiles. Nothing
here is a real program or website; what plain code finds in these pictures says nothing about how well it finds
things in a real one, and the tests that use this file say so.

Words are given as ocr.py gives them: lines of words, each {"x", "y", "width", "height", "text"} in picture pixels.
"""
from PIL import Image, ImageDraw, ImageFont

WHITE, INK, GREY, RED = (255, 255, 255), (20, 20, 20), (118, 118, 118), (217, 48, 37)


def font(size=14):
	"""A font every Windows has, or PIL's own when it is not there."""
	for name in ("arial.ttf", "segoeui.ttf", "tahoma.ttf"):
		try:
			return ImageFont.truetype(name, size)
		except OSError:
			continue
	return ImageFont.load_default()


class Page:
	"""A picture that is drawn on, and the lines of words a reading of it would give."""

	def __init__(self, width=800, height=600, colour=WHITE, size=14):
		self.image = Image.new("RGB", (width, height), colour)
		self.draw = ImageDraw.Draw(self.image)
		self.font = font(size)
		self.lines = []

	def text(self, x, y, words, fill=INK, read=True):
		"""Write words at a place; returns the box of all of them. Each word is a word of the reading."""
		line = []
		at = x
		space = self.draw.textlength(" ", font=self.font)
		for word in words.split():
			left, top, right, bottom = self.draw.textbbox((at, y), word, font=self.font)
			self.draw.text((at, y), word, fill=fill, font=self.font)
			line.append({"x": int(left), "y": int(top), "width": int(right - left), "height": int(bottom - top), "text": word})
			at = right + space
		if read and line:
			self.lines.append(line)
		first, last = line[0], line[-1]
		return (first["x"], min(word["y"] for word in line), last["x"] + last["width"],
			max(word["y"] + word["height"] for word in line))

	def rule(self, x0, x1, y, dotted=False, thick=1, fill=INK):
		"""A line to write on: solid, or dotted."""
		if not dotted:
			self.draw.line((x0, y, x1, y), fill=fill, width=thick)
			return
		for x in range(x0, x1, 5):
			self.draw.line((x, y, min(x1, x + 1), y), fill=fill, width=thick)

	def square(self, x, y, side=14, ticked=False, fill=INK):
		"""A printed check box, empty or with a cross in it."""
		self.draw.rectangle((x, y, x + side, y + side), outline=fill, width=1)
		if ticked:
			self.draw.line((x + 3, y + 3, x + side - 3, y + side - 3), fill=fill, width=2)
			self.draw.line((x + 3, y + side - 3, x + side - 3, y + 3), fill=fill, width=2)
		return (x, y, x + side + 1, y + side + 1)

	def field(self, box, outline=GREY, width=1):
		"""An edit field of a web page, as its outline."""
		self.draw.rectangle(box, outline=outline, width=width)
		return box

	def block(self, box, fill):
		self.draw.rectangle(box, fill=fill)
		return box


def paperForm():
	"""A printed form that is only a picture: labels, lines to write on, a line to sign, check boxes, a paragraph,
	and a line that is already written on. Returns (the page, the boxes of what was drawn, by name)."""
	page = Page(800, 620)
	where = {}
	page.text(40, 20, "Application for a Library Card")
	page.rule(40, 250, 40)  # an underline right under the heading: no blank
	page.text(40, 60, "Please fill in every line. A form that is not signed cannot be accepted, and the card is")
	page.text(40, 80, "sent to the address you give below within ten days of the day we get this form.")
	where["name"] = page.text(40, 130, "Applicant Full Name")
	page.rule(200, 560, 146)
	where["nameRule"] = (200, 146, 560, 147)
	where["birth"] = page.text(40, 170, "Date of Birth:")
	page.rule(150, 400, 186, dotted=True)
	where["birthRule"] = (150, 186, 400, 187)
	where["email"] = page.text(40, 210, "Email:")
	page.rule(100, 400, 226)
	page.text(110, 208, "sam@example.org")  # written on its line
	where["address"] = page.text(40, 260, "Address")
	page.rule(40, 500, 300)
	where["addressRule"] = (40, 300, 500, 301)
	where["agree"] = page.text(64, 340, "I agree to the rules of the library")
	where["agreeBox"] = page.square(40, 340)
	where["news"] = page.text(64, 370, "Send me news")
	where["newsBox"] = page.square(40, 370, ticked=True)
	page.rule(40, 320, 540, dotted=True)
	where["signRule"] = (40, 540, 320, 541)
	where["sign"] = page.text(40, 548, "Authorized Signature")
	page.rule(420, 620, 540)
	where["dateRule"] = (420, 540, 620, 541)
	where["date"] = page.text(420, 548, "Date")
	return page, where


def webForm(wrong=(1,), redText=True):
	"""A form of a web page in which the fields named in `wrong` (by number from 0) are outlined in red and nothing
	else says so. Returns (the page, the boxes of its fields in order)."""
	page = Page(520, 420)
	boxes = []
	for index, label in enumerate(("First name", "Email address", "Phone number", "Postcode")):
		top = 30 + index * 90
		page.text(40, top, label)
		boxes.append(page.field((40, top + 22, 400, top + 52), RED if index in wrong else GREY, 2 if index in wrong else 1))
		if index in wrong and redText:
			page.text(40, top + 58, "Please check this field", fill=(200, 30, 30))
	return page, boxes


def tiles(rows=3, columns=3, side=100, gap=6, colours=None):
	"""A puzzle of pictures: tiles of grainy colour separated by plain gaps. Returns (the picture, the boxes of the
	tiles row by row)."""
	width, height = gap + columns * (side + gap), gap + rows * (side + gap)
	image = Image.new("RGB", (width, height), WHITE)
	draw = ImageDraw.Draw(image)
	boxes = []
	for row in range(rows):
		for column in range(columns):
			left, top = gap + column * (side + gap), gap + row * (side + gap)
			base = (colours or {}).get(row * columns + column, (60 + 20 * row, 110 + 15 * column, 90))
			for y in range(top, top + side, 4):
				# Grain, so that a tile is no plain block.
				shade = tuple(max(0, min(255, part + ((y * 7 + column * 13) % 23) - 11)) for part in base)
				draw.rectangle((left, y, left + side - 1, y + 3), fill=shade)
			draw.line((left, top, left + side - 1, top + side - 1), fill=(30, 30, 30), width=3)
			boxes.append((left, top, left + side, top + side))
	return image, boxes
