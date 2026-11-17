# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Scrolling with the mouse wheel, on any screen: what a request asks for, steps that follow the screen's
scaling and the window's size, noticing whether a scroll moved anything, and finding scrollbars by their look.

The scrollbars are looked for in drawn pictures of a window with text, at four screen sizes and scalings, light
and dark, with thick and thin bars, upright and lying. These are drawings, not real programs: how well real
scrollbars are found is only shown by trying them.
"""
import random
import time

from PIL import Image, ImageDraw

import harness  # noqa: F401
from visionClaw.claw import scrolling


def window(width, height, scale, vertical=None, horizontal=None, dark=False, thin=False):
	"""A picture of a window with text, and scrollbars standing at the given shares (0.0 to 1.0)."""
	random.seed(width * 7 + height)
	back, ink, track, thumb = ((32, 220, 46, 110) if dark else (255, 20, 240, 150))
	image = Image.new("L", (width, height), back)
	draw = ImageDraw.Draw(image)
	bar = round((6 if thin else 17) * scale)
	line = round(18 * scale)
	for y in range(round(40 * scale), height - 2 * bar, line):
		x = round(12 * scale)
		while x < width - 3 * bar:
			word = random.randint(round(10 * scale), round(70 * scale))
			if random.random() < 0.8:
				draw.rectangle((x, y, x + word, y + round(9 * scale)), fill=ink)
			x += word + round(8 * scale)
	draw.rectangle((0, 0, width, round(30 * scale)), fill=90)  # a title bar
	if vertical is not None:
		top, bottom = round(30 * scale), height - (bar if horizontal is not None else 0)
		draw.rectangle((width - bar, top, width - 1, bottom - 1), fill=track)
		arrows = 0 if thin else bar
		length = bottom - top - 2 * arrows
		size = round(length * 0.25)
		start = top + arrows + round((length - size) * vertical)
		draw.rectangle((width - bar + 1, start, width - 2, start + size), fill=thumb)
	if horizontal is not None:
		right = width - (bar if vertical is not None else 0)
		draw.rectangle((0, height - bar, right - 1, height - 1), fill=track)
		arrows = 0 if thin else bar
		length = right - 2 * arrows
		size = round(length * 0.4)
		start = arrows + round((length - size) * horizontal)
		draw.rectangle((start, height - bar + 1, start + size, height - 2), fill=thumb)
	return image


for width, height, dpi in ((1366, 768, 96), (1920, 1080, 120), (3840, 2160, 192), (1280, 720, 144)):
	scale = scrolling.scaleOf(dpi)
	for vertical, horizontal, dark, thin in ((0.0, None, False, False), (0.5, None, False, False), (1.0, None, True, False),
			(0.3, 0.7, False, False), (0.6, None, False, True), (None, None, False, False), (None, 0.2, True, False)):
		image = window(width, height, scale, vertical, horizontal, dark, thin)
		started = time.time()
		found = scrolling.scrollbars(image, scale)
		took = time.time() - started
		ups = [bar for bar in found if bar["vertical"]]
		acrosses = [bar for bar in found if not bar["vertical"]]
		assert took < 3, took
		assert len(ups) == (vertical is not None), (found, vertical)
		assert len(acrosses) == (horizontal is not None), (found, horizontal)
		if vertical is not None:
			assert abs(ups[0]["percent"] - 100 * vertical) <= 6, ups
			x, y = ups[0]["grip"]
			assert x > width * 0.95 and image.getpixel((x, y)) in (150, 110), (x, y, image.getpixel((x, y)))
		if horizontal is not None:
			assert abs(acrosses[0]["percent"] - 100 * horizontal) <= 6, acrosses
			x, y = acrosses[0]["grip"]
			assert y > height * 0.93 and image.getpixel((x, y)) in (150, 110), (x, y, image.getpixel((x, y)))

# Whether a scroll moved anything.
first = window(1366, 768, 1.0, 0.2)
assert scrolling.moved(first, first) == 0.0
assert scrolling.moved(first, window(1366, 768, 1.0, 0.6)) > 0 and scrolling.moved(first, None) == 1.0
shifted = Image.new("L", first.size, 255)
shifted.paste(first, (0, -60))
assert scrolling.moved(first, shifted) > scrolling.MOVED_SHARE
# Steps follow the screen: the same to the eye, never huge in a small window.
assert scrolling.steps((0, 0, 1366, 768), 1.0) == (20, 4, 100) and scrolling.steps((0, 0, 3840, 2160), 2.0) == (40, 8, 200)
assert scrolling.steps((0, 0, 200, 120), 2.0) == (10, 5, 30)
# What a request asks for.
for words, direction, amount in (
	("scroll down", "down", (3, False)), ("scroll up a little", "up", (1, False)), ("scroll down a page", "down", (8, False)),
	("scroll to the bottom", "down", (8, True)), ("scroll back to the top", "up", (8, True)), ("scroll right", "right", (3, False)),
	("scroll down 3 pages", "down", (24, False)), ("scroll up 5 lines", "up", (5, False)), ("scroll down half a page", "down", (4, False)),
	("scroll all the way to the left", "left", (8, True)), ("scroll the list down a lot", "down", (16, False)),
):
	assert scrolling.directionOf(words) == direction and scrolling.amountOf(words) == amount, (words, scrolling.directionOf(words), scrolling.amountOf(words))
assert scrolling.wheelAmount("down", 3) == -360 and scrolling.wheelAmount("up", 1) == 120 and scrolling.wheelAmount("right", 2) == 240
# The scrollbar in words, and where the view stands.
bar = scrolling.scrollbars(window(1366, 768, 1.0, 0.5), 1.0)[0]
assert scrolling.barText(bar) == "a scrollbar at the right, 50 percent down, showing 24 percent of the whole at a time", scrolling.barText(bar)
assert scrolling.positionText(bar) == "50 percent down"
assert scrolling.positionText(dict(bar, percent=2)) == "at the top" and scrolling.positionText(dict(bar, percent=98)) == "at the bottom"
assert scrolling.positionText({"vertical": False, "percent": 100}) == "at the right end"
# The overlay's icon finder follows the scaling too: an icon 150 pixels across is too large to be an icon on
# a plain screen, and is one on a screen at 200 percent, where a normal icon has that many pixels.
from visionClaw import imaging, layout  # noqa: E402

drawing = Image.new("RGB", (900, 500), "white")
pen = ImageDraw.Draw(drawing)
pen.ellipse((100, 100, 250, 250), fill="navy")
pen.rectangle((650, 180, 700, 230), outline="black", width=6)
sizes = {scale: sorted(box[2] - box[0] for box in imaging.findIcons(drawing, (), scale)) for scale in (1.0, 2.0)}
assert sizes == {1.0: [56], 2.0: [56, 156]}, sizes
# The layout of a window takes the scaling as well, and still works without it.
assert layout.Layout(drawing, [], 2.0).scale == 2.0 and layout.Layout(drawing, []).scale == 1.0
# A screen's scaling, from what Windows reports; nonsense counts as a plain screen.
assert scrolling.scaleOf(96) == 1.0 and scrolling.scaleOf(144) == 1.5 and scrolling.scaleOf(192) == 2.0
assert scrolling.scaleOf(0) == 1.0 and scrolling.scaleOf(None) == 1.0 and scrolling.scaleOf("x") == 1.0
print("OK")
