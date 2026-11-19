# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - colours measured from the pixels of a picture and said in plain words. A blind user who asks
# whether a jacket is navy or black, which swatch is the dark blue one, or which field of a form is outlined in
# red, is asking for a fact that plain code can measure; a small model that looks at the picture is far less sure
# of it. So: a colour is named from its red, green and blue (name), the main colours of an area are counted
# (main), the colour of the middle of a small thing such as a swatch is taken (middle), the outline of a field is
# checked for the red that marks an error (redShare, marked), text written in red is found (redLines), and the
# colour a user's words name is matched against measured colours (wanted, fit, closest).
# What is said is always the colour's plain name and that it was measured from the picture: a photo's light
# changes colours, so the answer never claims more than what the pixels are.
# No NVDA dependencies. Pictures are PIL images; boxes are (left, top, right, bottom) in picture pixels.

import colorsys
import re

BLACK, WHITE, GREY = "black", "white", "grey"
# The plain names a colour can get. Every name is one a person would say; none needs a colour chart.
NAMES = (
	BLACK, WHITE, "dark grey", GREY, "light grey", "dark red", "red", "pink", "light pink", "brown", "orange",
	"light orange", "beige", "cream", "olive", "yellow", "light yellow", "dark green", "green", "light green",
	"dark turquoise", "turquoise", "light turquoise", "dark blue", "blue", "light blue", "dark purple", "purple",
	"light purple", "dark pink")
# Where each hue begins, in degrees around the colour circle, and its plain name.
_HUES = ((15, "red"), (42, "orange"), (68, "yellow"), (165, "green"), (195, "turquoise"), (258, "blue"), (285, "purple"),
	(320, "purple or pink"), (345, "pink"), (361, "red"))
# What a user may call a colour, and the plain name it is measured as. Longer wordings are looked for first.
ASKED = {
	"navy blue": "dark blue", "navy": "dark blue", "midnight blue": "dark blue", "royal blue": "blue", "sky blue": "light blue",
	"baby blue": "light blue", "pale blue": "light blue", "teal": "dark turquoise", "aqua": "turquoise", "cyan": "turquoise",
	"mint": "light green", "lime": "light green", "forest green": "dark green", "bottle green": "dark green",
	"maroon": "dark red", "burgundy": "dark red", "wine": "dark red", "crimson": "red", "scarlet": "red",
	"rose": "pink", "salmon": "light pink", "magenta": "dark pink", "fuchsia": "dark pink", "hot pink": "dark pink",
	"violet": "purple", "lilac": "light purple", "lavender": "light purple", "mauve": "light purple", "plum": "dark purple",
	"tan": "beige", "khaki": "beige", "sand": "beige", "ivory": "cream", "off white": "cream", "off-white": "cream",
	"gold": "yellow", "golden": "yellow", "mustard": "yellow", "silver": "light grey", "charcoal": "dark grey",
	"gray": GREY, "dark gray": "dark grey", "light gray": "light grey", "chocolate": "brown", "coffee": "brown",
}
_LIGHTNESS = r"(dark|deep|light|pale|bright)"
_PLAIN = r"(black|white|grey|gray|red|pink|brown|orange|beige|cream|olive|yellow|green|turquoise|blue|purple)"
_ASKED = re.compile(
	r"\b(" + "|".join(sorted((re.escape(word) for word in ASKED), key=len, reverse=True)) + r")\b"
	rf"|\b(?:{_LIGHTNESS}\s+)?{_PLAIN}\b", re.IGNORECASE)
# A picture is made this small before its colours are counted: a photo's grain is averaged away.
_SMALL = 48
# How strongly red a pixel must be to count as the red that marks an error.
_RED_SATURATION, _RED_VALUE = 0.5, 0.45
# A field counts as outlined in red when at least this share of its outline is red.
RED_OUTLINE = 0.3


def name(rgb):
	"""A colour in plain words, from its red, green and blue (0 to 255 each)."""
	red, green, blue = (max(0, min(255, int(part))) for part in rgb[:3])
	hue, saturation, value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
	hue *= 360
	# What has almost no colour is black, white or a grey.
	if value < 0.12 or (value < 0.22 and saturation < 0.35):
		return BLACK
	if saturation < 0.12 or (saturation < 0.2 and value < 0.5) or (saturation < 0.35 and value < 0.4):
		if value > 0.93:
			return WHITE
		return "light grey" if value > 0.7 else GREY if value > 0.4 else "dark grey"
	word = next(found for limit, found in _HUES if hue < limit)
	if word == "purple or pink":
		# Between purple and pink, a dark colour is called purple and a bright one pink.
		word = "purple" if value < 0.7 else "pink"
	pale = value > 0.8 and saturation < 0.45
	# Navy and maroon are still dark at half brightness; a green or a purple there is plainly green or purple.
	dark = value < (0.56 if word in ("red", "blue") else 0.45)
	if word == "orange":
		# A dark orange is brown; a pale one is beige, and a very pale one cream.
		if value < 0.62:
			return "brown"
		if saturation < 0.25:
			return "cream"
		return "beige" if saturation < 0.45 else "orange"
	if word == "yellow":
		if value < 0.6:
			return "olive"
		return "cream" if saturation < 0.25 else "light yellow" if pale else "yellow"
	if word == "red":
		if dark:
			return "dark red" if saturation > 0.45 else "brown"
		return "light pink" if saturation < 0.3 and value > 0.8 else "pink" if pale else "red"
	if word == "pink":
		return "dark pink" if saturation > 0.6 and value < 0.85 else "light pink" if pale else "pink"
	return f"dark {word}" if dark else f"light {word}" if pale else word


def family(colour):
	"""A colour's name without dark or light: what "blue" means when the user says no more."""
	return colour.split(" ", 1)[1] if colour.startswith(("dark ", "light ")) else colour


def wanted(words):
	"""The colours a user's words name, as plain names, in the order they are said. "Navy" is dark blue; "blue"
	alone is blue, and fits dark and light blue too (fit)."""
	found = []
	for hit in _ASKED.finditer(words or ""):
		if hit.group(1):
			colour = ASKED[hit.group(1).lower()]
		else:
			plain = "grey" if hit.group(3).lower() == "gray" else hit.group(3).lower()
			tone = (hit.group(2) or "").lower()
			tone = "dark" if tone in ("dark", "deep") else "light" if tone in ("light", "pale") else ""
			colour = f"{tone} {plain}".strip()
			if colour not in NAMES:
				colour = plain
		if colour not in found:
			found.append(colour)
	return found


def fit(asked, measured):
	"""How well a measured colour is the one asked for: 2 the same name, 1 the same colour darker or lighter (and
	what people call by a neighbour's name: a very dark blue and black, cream and white), 0 another colour."""
	if asked == measured:
		return 2
	if family(asked) == family(measured):
		return 1
	near = {("dark blue", BLACK), ("dark grey", BLACK), ("cream", WHITE), ("light grey", WHITE), ("beige", "cream"),
		("brown", "dark red"), ("dark turquoise", "dark green"), ("dark purple", "dark blue"), ("olive", "dark green"),
		("light pink", "pink"), ("dark pink", "purple")}
	return 1 if (asked, measured) in near or (measured, asked) in near else 0


def closest(asked, measured):
	"""Which of several measured colours is the one asked for: (its index, True) when exactly one fits best;
	(None, the indexes that fit equally well) when several do; (None, []) when none fits."""
	scores = [fit(asked, colour) for colour in measured]
	best = max(scores, default=0)
	if best == 0:
		return None, []
	indexes = [index for index, score in enumerate(scores) if score == best]
	return (indexes[0], True) if len(indexes) == 1 else (None, indexes)


def distance(first, second):
	"""How different two colours look, from 0 (the same) to about 765: the differences in red, green and blue,
	weighted by how strongly the eye sees each (the "redmean" formula)."""
	mean = (first[0] + second[0]) / 2.0
	red, green, blue = (first[i] - second[i] for i in range(3))
	return ((2 + mean / 256) * red * red + 4 * green * green + (2 + (255 - mean) / 256) * blue * blue) ** 0.5


def _crop(image, box):
	rgb = image.convert("RGB")
	if box is None:
		return rgb
	left, top, right, bottom = (int(round(value)) for value in box)
	left, top = max(0, left), max(0, top)
	right, bottom = min(rgb.size[0], right), min(rgb.size[1], bottom)
	if right - left < 1 or bottom - top < 1:
		return None
	return rgb.crop((left, top, right, bottom))


def _median(pixels):
	"""The middle colour of some pixels: the middle value of red, of green and of blue. One odd pixel changes nothing."""
	if not pixels:
		return None
	half = len(pixels) // 2
	return tuple(sorted(pixel[i] for pixel in pixels)[half] for i in range(3))


def main(image, box=None, most=3, least=0.06):
	"""The main colours of a picture or of an area of it: [(plain name, share from 0.0 to 1.0)], the most common
	first, at most `most`, and none that covers less than `least` of it."""
	area = _crop(image, box)
	if area is None:
		return []
	small = area.resize((min(_SMALL, area.size[0]), min(_SMALL, area.size[1])))
	counts = {}
	pixels = list(small.getdata())
	for pixel in pixels:
		colour = name(pixel)
		counts[colour] = counts.get(colour, 0) + 1
	found = sorted(counts.items(), key=lambda item: -item[1])
	return [(colour, count / len(pixels)) for colour, count in found if count / len(pixels) >= least][:most]


def ground(image, box=None, edge=0.04, least=0.7):
	"""The colour a picture stands on, as a plain name: what most of its outer edge is, as a product photo's white
	background. None when the edge is not mostly one colour."""
	area = _crop(image, box)
	if area is None:
		return None
	small = area.resize((min(_SMALL, area.size[0]), min(_SMALL, area.size[1])))
	width, height = small.size
	band = max(1, round(min(width, height) * edge))
	pixels = list(small.getdata())
	counts, total = {}, 0
	for y in range(height):
		for x in range(width):
			if x < band or y < band or x >= width - band or y >= height - band:
				colour = name(pixels[y * width + x])
				counts[colour] = counts.get(colour, 0) + 1
				total += 1
	if not total:
		return None
	colour = max(counts, key=counts.get)
	return colour if counts[colour] / total >= least else None


def subject(image, box=None, most=3, least=0.06):
	"""The main colours of what a picture shows, leaving out the plain background it stands on: (the background's
	name or None, [(plain name, share of what is left)])."""
	back = ground(image, box)
	if back is None:
		return None, main(image, box, most, least)
	area = _crop(image, box)
	small = area.resize((min(_SMALL, area.size[0]), min(_SMALL, area.size[1])))
	counts, total = {}, 0
	for pixel in small.getdata():
		colour = name(pixel)
		if colour == back:
			continue
		counts[colour] = counts.get(colour, 0) + 1
		total += 1
	# A picture that is nearly all background shows nothing to measure apart from it.
	if total < len(list(small.getdata())) * 0.03:
		return back, []
	found = sorted(counts.items(), key=lambda item: -item[1])
	return back, [(colour, count / total) for colour, count in found if count / total >= least][:most]


def middle(image, box, share=0.5):
	"""The colour in the middle of a small thing, such as a swatch or a seat on a map: the middle colour of the
	inner part of its box, so that its outline and what is around it do not count. (red, green, blue), or None."""
	left, top, right, bottom = box
	inX, inY = (right - left) * (1 - share) / 2.0, (bottom - top) * (1 - share) / 2.0
	area = _crop(image, (left + inX, top + inY, right - inX, bottom - inY))
	if area is None:
		return None
	return _median(list(area.getdata()))


def _isRed(pixel):
	hue, saturation, value = colorsys.rgb_to_hsv(pixel[0] / 255.0, pixel[1] / 255.0, pixel[2] / 255.0)
	hue *= 360
	return (hue < 18 or hue > 340) and saturation >= _RED_SATURATION and value >= _RED_VALUE


def redShare(image, box, thick=3):
	"""How much of the outline of a box is red, from 0.0 to 1.0: the pixels in a band `thick` wide on each side of
	the box's edge. A field that a web page marks as wrong only by a red border has a high share."""
	rgb = image.convert("RGB")
	width, height = rgb.size
	left, top, right, bottom = (int(round(value)) for value in box)
	if right - left < 4 or bottom - top < 4:
		return 0.0
	total = red = 0
	# The four sides, each as the rows or columns of the band around the edge.
	bands = (
		(left - thick, top - thick, right + thick, top + thick + 1), (left - thick, bottom - thick - 1, right + thick, bottom + thick),
		(left - thick, top + thick + 1, left + thick + 1, bottom - thick - 1), (right - thick - 1, top + thick + 1, right + thick, bottom - thick - 1))
	sides = []
	for x0, y0, x1, y1 in bands:
		x0, y0, x1, y1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
		if x1 <= x0 or y1 <= y0:
			continue
		horizontal = (x1 - x0) >= (y1 - y0)
		pixels = rgb.crop((x0, y0, x1, y1))
		data = list(pixels.getdata())
		w, h = pixels.size
		# A side is red when a line along it is red: the best row of a horizontal band, the best column of an upright one.
		lines = ([data[row * w:(row + 1) * w] for row in range(h)] if horizontal
			else [data[column::w] for column in range(w)])
		best = max((sum(1 for pixel in line if _isRed(pixel)) / len(line) for line in lines if line), default=0.0)
		sides.append((best, len(lines[0]) if lines else 0))
	for share, length in sides:
		total += length
		red += share * length
	return red / total if total else 0.0


def marked(image, boxes, thick=3, least=RED_OUTLINE):
	"""Which of several boxes are outlined in red: their indexes, in order. The boxes are the fields of a form in
	a picture of the page."""
	return [index for index, box in enumerate(boxes) if box is not None and redShare(image, box, thick) >= least]


def ink(image, box):
	"""The colour something is written or drawn in inside a box: the middle colour of the pixels that differ from
	the box's most common colour, which is its background. None when the box is one plain colour."""
	area = _crop(image, box)
	if area is None:
		return None
	pixels = list(area.getdata())
	counts = {}
	for pixel in pixels:
		key = (pixel[0] >> 3, pixel[1] >> 3, pixel[2] >> 3)
		counts[key] = counts.get(key, 0) + 1
	ground = max(counts, key=counts.get)
	back = tuple((part << 3) + 4 for part in ground)
	written = [pixel for pixel in pixels if distance(pixel, back) > 120]
	if len(written) < max(4, len(pixels) // 60):
		return None
	# The strongest half of them: the edges of letters are blended with the background.
	written.sort(key=lambda pixel: -distance(pixel, back))
	return _median(written[:max(1, len(written) // 2)])


def redLines(image, lines):
	"""The lines of text that are written in red, from the text read in a picture (ocr.py's lines of words with x,
	y, width, height and text): [the line's text]. A page that says what is wrong in red letters is found this way."""
	found = []
	for line in lines or ():
		words = [word for word in line if word.get("text", "").strip()]
		if not words:
			continue
		red = 0
		for word in words:
			colour = ink(image, (word["x"], word["y"], word["x"] + word["width"], word["y"] + word["height"]))
			if colour is not None and _isRed(colour):
				red += 1
		if red * 2 > len(words):
			found.append(" ".join(word["text"] for word in words))
	return found


def said(shares):
	"""The main colours of something as a sentence part: "mostly dark blue (62 percent), then white (20 percent)"."""
	if not shares:
		return ""
	parts = [f"{colour} ({round(share * 100)} percent)" for colour, share in shares]
	if len(parts) == 1:
		return f"almost all {parts[0]}" if shares[0][1] > 0.85 else f"mostly {parts[0]}"
	return f"mostly {parts[0]}, then " + " and ".join(parts[1:])


# Said with every measured colour, so that nobody takes it for more than it is.
MEASURED = "This was measured from the pixels of the picture; the light in a photo can make a colour look darker or lighter than the thing is."
