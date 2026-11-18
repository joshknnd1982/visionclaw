# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the plain reasoning behind scrolling with the mouse wheel from the keyboard, on any screen:
# how far a request wants to scroll, how big a step is on this screen, whether a scroll moved anything (so the
# end of a list is noticed), and where the scrollbars are in a window's picture and how far down they stand.
# Sizes are never fixed numbers of pixels: they follow the screen's scaling and the size of the window, so the
# same request does the same thing on a small laptop screen and on a large 4K one.
# No NVDA dependencies, and nothing here touches the mouse. Pictures are PIL images.

import re

UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"
DIRECTIONS = [UP, DOWN, LEFT, RIGHT]
# One notch of the wheel, as Windows counts it.
WHEEL_DELTA = 120
# A notch scrolls about three lines in most programs; this many notches are about one page of a window.
NOTCHES, PAGE_NOTCHES, MAX_NOTCHES = 3, 8, 400
# "To the end": scroll a page at a time until nothing moves any more, but never more often than this.
MAX_PAGES = 60
# Windows' own measure: 96 dots per inch is a scaling of 100 percent.
BASE_DPI = 96
_END = re.compile(r"\b(all the way|to the (very )?(end|bottom|top|start|beginning|left|right|edge)|as far as)\b")
_PAGE = re.compile(r"\b(a |one |by a |by one )?(page|screen|screenful)\b")
_HALF = re.compile(r"\bhalf (a |of a |the )?(page|screen)\b")
_LITTLE = re.compile(r"\b(a little|a bit|slightly|a tiny bit|one (line|notch|click|step))\b")
_LOT = re.compile(r"\b(a lot|far|much further|a long way)\b")
_NUMBER = re.compile(r"\b(\d{1,3})\s*(pages?|screens?|lines?|notch(es)?|clicks?|steps?|times)?\b")


def scaleOf(dpi):
	"""How much larger than plain everything is drawn on a screen: 1.0 at 100 percent, 2.0 at 200 percent."""
	try:
		value = float(dpi) / BASE_DPI
	except (TypeError, ValueError):
		return 1.0
	return max(0.75, min(5.0, value)) if value > 0 else 1.0


def pixels(size, scale):
	"""A size meant for a plain screen, in the pixels of this screen."""
	return max(1, round(size * scale))


def steps(box, scale):
	"""How far the pointer moves for one key press in pointer mode, as (plain, fine, far), on this screen and
	in this window: a step looks the same size to the eye whatever the resolution, and a far step is never
	more than a tenth of a small window."""
	left, top, right, bottom = box
	smaller = max(40, min(right - left, bottom - top))
	plain = max(4, min(pixels(20, scale), smaller // 12))
	return plain, max(1, min(pixels(4, scale), plain // 2)), max(plain * 2, min(pixels(100, scale), smaller // 4))


def directionOf(words):
	"""Which way a request wants to scroll, from its words. "To the top" is up, "to the end" is down."""
	text = (words or "").lower()
	if re.search(r"\b(left|leftwards?)\b", text):
		return LEFT
	if re.search(r"\b(right|rightwards?)\b", text):
		return RIGHT
	if re.search(r"\b(up|upwards?|back|top|start|beginning|previous|earlier)\b", text):
		return UP
	return DOWN


def zoomOf(words):
	"""Whether a request wants what is shown made larger ("in") or smaller ("out"), which a sighted person does
	with the Control key and the mouse wheel, or with two fingers; None when it asks for neither."""
	text = (words or "").lower()
	if re.search(r"\bzoom(s|ed|ing)?\s+(back\s+)?out\b|\bunzoom\b", text):
		return "out"
	if re.search(r"\bzoom(s|ed|ing)?\b", text):
		return "in"
	return None


def amountOf(words):
	"""How far a request wants to scroll, as (notches of the wheel, whether to go on until the end)."""
	text = (words or "").lower()
	if _END.search(text):
		return PAGE_NOTCHES, True
	if _HALF.search(text):
		return PAGE_NOTCHES // 2, False
	found = _NUMBER.search(text)
	if found and found.group(2):
		count = max(1, int(found.group(1)))
		per = PAGE_NOTCHES if found.group(2).startswith(("page", "screen")) else 1
		return min(MAX_NOTCHES, count * per), False
	if _PAGE.search(text):
		return PAGE_NOTCHES, False
	if _LITTLE.search(text):
		return 1, False
	if _LOT.search(text):
		return PAGE_NOTCHES * 2, False
	return NOTCHES, False


def wheelAmount(direction, notches):
	"""The number Windows wants for a turn of the wheel: positive is away from the user (up, or right)."""
	sign = 1 if direction in (UP, RIGHT) else -1
	return sign * WHEEL_DELTA * max(1, min(MAX_NOTCHES, int(notches)))


def _grey(image, size):
	return image.convert("L").resize(size).tobytes()


def moved(before, after):
	"""How much of a picture changed between two looks, from 0.0 (nothing) to 1.0 (everything). After a scroll
	this says whether anything moved: at the end of a list, nothing does. Both pictures are made small first,
	so that a blinking cursor or a clock does not count as movement."""
	if before is None or after is None or before.size != after.size:
		return 1.0
	a, b = _grey(before, (96, 96)), _grey(after, (96, 96))
	return sum(1 for x, y in zip(a, b) if abs(x - y) > 18) / len(a)


# A scroll moved something if at least this much of the picture changed.
MOVED_SHARE = 0.004


def _runs(values, tolerance):
	"""A row of grey values as runs of nearly the same value: [(start, end, value)]."""
	found = []
	start = 0
	for i in range(1, len(values) + 1):
		if i == len(values) or abs(values[i] - values[start]) > tolerance:
			found.append((start, i, values[start]))
			start = i
	return found


TOLERANCE = 14


def _thumb(line, tolerance=TOLERANCE):
	"""If a line of grey values along a strip looks like a scrollbar's track with its thumb on it:
	(where the thumb starts, where it ends, where the track starts, where the track ends, the thumb's tone),
	all along the line; else None. A track is one tone for most of its length; the thumb is the one long
	stretch of another tone on it."""
	length = len(line)
	if length < 24:
		return None
	runs = [run for run in _runs(line, tolerance) if run[1] - run[0] >= 2]
	if not runs:
		return None
	tones = {}
	for start, end, value in runs:
		key = value // (tolerance + 1)
		tones[key] = tones.get(key, 0) + end - start
	track = max(tones, key=tones.get)
	if tones[track] < 0.3 * length:
		return None
	trackValue = max((run for run in runs if run[2] // (tolerance + 1) == track), key=lambda run: run[1] - run[0])[2]

	def reach(position, step):
		"""How far the track goes on from one end of a thumb. A bin or two of mixed tone at an edge is passed."""
		edge, gap = position, 0
		i = position - 1 if step < 0 else position
		while 0 <= i < length and gap <= 2:
			if abs(line[i] - trackValue) <= tolerance:
				edge, gap = (i if step < 0 else i + 1), 0
			else:
				gap += 1
			i += step
		return edge

	best = None
	for start, end, value in runs:
		if value // (tolerance + 1) == track or end - start < 3:
			continue
		trackStart, trackEnd = reach(start, -1), reach(end, 1)
		span = trackEnd - trackStart
		if (span >= 0.3 * length and span - (end - start) >= 3 and 0.03 * span <= end - start <= 0.97 * span
				and (best is None or span > best[3] - best[2])):
			best = (start, end, trackStart, trackEnd, value)
	return best


def _apart(small, width, bins, column, thumb):
	"""Whether a column next to a strip is free of the thumb's tone where the thumb is. A scrollbar's thumb
	stands alone; a piece of a wide thing, such as a word or a picture, goes on into the next column."""
	if column < 0 or column >= width:
		return True  # the edge of the picture
	start, end, tone = thumb[0], thumb[1], thumb[4]
	same = sum(1 for row in range(start, end) if abs(small[row * width + column] - tone) <= TOLERANCE)
	return same <= 0.15 * (end - start)


def _bars(image, scale, vertical):
	"""The scrollbars of one direction in a picture, as dictionaries with their place in the picture."""
	width, height = image.size
	if not vertical:
		image = image.transpose(2)  # a quarter turn to the left, so one piece of code serves both directions
		width, height = image.size
	if width < 40 or height < 60:
		return []
	bins = min(height, 200)
	small = image.convert("L").resize((width, bins)).tobytes()
	thinnest, thickest = max(2, pixels(3, scale)), pixels(26, scale)
	found = []
	x = 0
	while x < width:
		thumb = _thumb([small[row * width + x] for row in range(bins)])
		if thumb is None:
			x += 1
			continue
		end = x + 1
		while end < width:
			other = _thumb([small[row * width + end] for row in range(bins)])
			if other is None or abs(other[0] - thumb[0]) > 1 or abs(other[1] - thumb[1]) > 1:
				break
			end += 1
		unit = height / bins
		top, bottom = round(thumb[0] * unit), round(thumb[1] * unit)
		trackTop, trackBottom = round(thumb[2] * unit), round(thumb[3] * unit)
		# As thick as a scrollbar, a thumb that is longer than it is thick, and standing alone.
		if (thinnest <= end - x <= thickest and bottom - top >= max(pixels(14, scale), 1.2 * (end - x))
				and _apart(small, width, bins, x - 1, thumb) and _apart(small, width, bins, end, thumb)):
			travel = (trackBottom - trackTop) - (bottom - top)
			found.append({
				"at": (x, end), "thumb": (top, bottom), "track": (trackTop, trackBottom),
				"percent": max(0, min(100, round(100 * (top - trackTop) / travel))) if travel > 0 else 0,
				"shown": max(1, min(100, round(100 * (bottom - top) / max(1, trackBottom - trackTop)))),
			})
		x = end
	return found


def scrollbars(image, scale=1.0):
	"""The scrollbars in a picture of a window, found by their look: a thin strip of one tone with one stretch
	of another tone standing alone on it. Each is a dictionary: vertical, box (left, top, right, bottom of its
	track in the picture), grip (the middle of its thumb, where to take hold of it), percent (how far along it
	stands), and shown (how much of the whole it shows at once, in percent). A look, not a certainty: something
	that happens to look like a scrollbar is found too, and a scrollbar that only shows while the mouse is over
	it is not."""
	width, height = image.size
	# A scrollbar stands at the right or the bottom edge of what it scrolls. Anywhere else, a strip with one
	# stretch of another tone is far more often a line of text with one word on it, so it is not counted.
	# To find the scrollbar of a part of a window, give the picture of that part.
	nearRight, nearBottom = max(pixels(40, scale), 0.03 * width), max(pixels(64, scale), 0.07 * height)
	found = []
	for bar in _bars(image, scale, True):
		(left, right), (top, bottom) = bar["at"], bar["thumb"]
		if width - right > nearRight:
			continue
		found.append({
			"vertical": True, "box": (left, bar["track"][0], right, bar["track"][1]),
			"grip": ((left + right) // 2, (top + bottom) // 2), "percent": bar["percent"], "shown": bar["shown"],
		})
	for bar in _bars(image, scale, False):
		# The picture was turned a quarter turn to the left: its columns are the rows of the real picture,
		# and going down in it is going left in the real one.
		(first, last), (start, end) = bar["at"], bar["thumb"]
		if height - last > nearBottom:
			continue
		left, right = width - end, width - start
		found.append({
			"vertical": False, "box": (width - bar["track"][1], first, width - bar["track"][0], last),
			"grip": ((left + right) // 2, (first + last) // 2), "percent": 100 - bar["percent"], "shown": bar["shown"],
		})
	return found


def barText(bar):
	"""A scrollbar in words a person can picture."""
	edge = "at the right" if bar["vertical"] else "at the bottom"
	way = "down" if bar["vertical"] else "across"
	return f"a scrollbar {edge}, {bar['percent']} percent {way}, showing {bar['shown']} percent of the whole at a time"


def positionText(bar):
	"""Where a view stands after a scroll, from its scrollbar."""
	if bar["percent"] <= 4:
		return "at the top" if bar["vertical"] else "at the left end"
	if bar["percent"] >= 96:
		return "at the bottom" if bar["vertical"] else "at the right end"
	return f"{bar['percent']} percent {'down' if bar['vertical'] else 'across'}"
