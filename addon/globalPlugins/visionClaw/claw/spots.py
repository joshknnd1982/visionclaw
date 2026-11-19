# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - places in a picture, found by plain code. A scanned form is only a picture: NVDA finds nothing in
# it to move to, and a sighted person works it by seeing the printed line next to "Applicant Full Name" and
# clicking there. Here the same is done from the pixels and from the text read in the picture (ocr.py's lines of
# words, each with x, y, width, height and text):
#   - where a label stands in that text (phrase), forgiving what the reading got slightly wrong;
#   - the printed lines to write on: solid, dotted or dashed (rules), and which of them belongs to a label
#     (blankFor): to its right, under it, or above it, as on a line to sign;
#   - small empty or ticked squares, the check boxes of a printed form (squares), and the one next to a label
#     (squareFor);
#   - a grid of equal tiles separated by plain gaps, as a puzzle of pictures has (grid).
# Nothing here asks a model, and nothing here touches the mouse: the callers click. Sizes follow the screen's
# scaling (scrolling.pixels), never a fixed number of pixels.
# No NVDA dependencies. Pictures are PIL images; boxes are (left, top, right, bottom) in picture pixels.

import difflib
import re

from .scrolling import pixels

# How different from the page's background a pixel must be to count as ink.
INK = 60
# A line to write on is at least this long, at most this thick, and its dots or dashes at most this far apart;
# all for a plain screen at 100 percent.
MIN_RULE, MAX_THICK, MAX_GAP = 36, 4, 7
# The side of a printed check box, from and to, at 100 percent.
MIN_SQUARE, MAX_SQUARE = 9, 28
# Where a label's blank is looked for, and how the user is told where it was found.
NEXT, UNDER, ABOVE, ANY = "next", "under", "above", "any"
HOW = {NEXT: "to the right of", UNDER: "under", ABOVE: "above"}
# A grid has at least two tiles each way and at most this many.
MAX_TILES = 8


def _plain(text):
	return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _alike(got, want):
	"""Whether a word as it was read is the word that was asked for: the same, or nearly, for a longer word."""
	if got == want:
		return 1.0
	if len(want) < 5 or abs(len(got) - len(want)) > 2:
		return 0.0
	ratio = difflib.SequenceMatcher(None, got, want).ratio()
	return ratio if ratio >= 0.84 else 0.0


def wordBox(word):
	return (word["x"], word["y"], word["x"] + word["width"], word["y"] + word["height"])


def _union(boxes):
	return (min(box[0] for box in boxes), min(box[1] for box in boxes), max(box[2] for box in boxes), max(box[3] for box in boxes))


def phrase(lines, label):
	"""Where a label stands in the text read from a picture: [(left, top, right, bottom)], from the top down. The
	reading may have joined two words, split one, or got a letter wrong; a label of several words must still be
	there as a whole, in one line."""
	want = [_plain(word) for word in (label or "").split()]
	want = [word for word in want if word]
	if not want:
		return []
	joined = "".join(want)
	found = []
	for line in lines or ():
		words = [(_plain(word.get("text", "")), word) for word in line]
		words = [(text, word) for text, word in words if text]
		best = None
		for start in range(len(words)):
			# The same number of words, or one fewer or one more where the reading joined or split them.
			for count in (len(want), len(want) - 1, len(want) + 1):
				if count < 1 or start + count > len(words):
					continue
				got = "".join(text for text, _word in words[start:start + count])
				score = _alike(got, joined)
				if score and (best is None or score > best[0]):
					best = (score, start, count)
		if best is not None:
			_score, start, count = best
			found.append(_union([wordBox(word) for _text, word in words[start:start + count]]))
	return sorted(found, key=lambda box: (box[1], box[0]))


def _rows(image):
	"""A picture as rows of bytes, 1 where there is ink and 0 where the page's own background is: (width, height,
	rows). The background is the tone most of the picture has."""
	grey = image.convert("L")
	width, height = grey.size
	histogram = grey.histogram()
	back = max(range(256), key=histogram.__getitem__)
	data = grey.point([1 if abs(value - back) > INK else 0 for value in range(256)]).tobytes()
	return width, height, [data[y * width:(y + 1) * width] for y in range(height)]


def _regular(segment):
	"""Whether a run of ink with gaps is a dotted or dashed line: its pieces all of nearly one length, and its gaps
	too. A row of letters has pieces and gaps of every length."""
	pieces = [len(piece) for piece in re.findall(rb"\x01+", segment)]
	gaps = [len(gap) for gap in re.findall(rb"\x00+", segment)]
	if len(pieces) < 4:
		return False
	# The first and the last piece may be cut short.
	inner = sorted(pieces[1:-1]) or sorted(pieces)
	middle = inner[len(inner) // 2]
	if any(abs(piece - middle) > max(2, middle // 2) for piece in inner):
		return False
	gaps.sort()
	return not gaps or gaps[-1] - gaps[0] <= max(2, gaps[len(gaps) // 2] // 2)


def _inkShare(rows, top, bottom, left, right):
	total = ink = 0
	for y in range(max(0, top), min(len(rows), bottom)):
		ink += rows[y].count(b"\x01", left, right)
		total += right - left
	return ink / total if total else 0.0


def rules(image, scale=1.0):
	"""The lines to write on in a picture: thin, long, with nothing on them. Each is {"box": (left, top, right,
	bottom), "dotted": whether it is made of dots or dashes}, from the top down. A line with writing on it is not
	blank, and is left out; so is a line of text, which is thick and uneven."""
	width, height, rows = _rows(image)
	least, thick, gap = pixels(MIN_RULE, scale), pixels(MAX_THICK, scale), pixels(MAX_GAP, scale)
	clear = pixels(3, scale)
	runs = re.compile(rb"\x01+(?:\x00{1,%d}\x01+)*" % gap)
	open_, done = [], []
	for y in range(height + 1):
		row = rows[y] if y < height else b""
		here = []
		for found in runs.finditer(row):
			start, end = found.span()
			if end - start < least:
				continue
			segment = found.group(0)
			solid = segment.count(b"\x01") >= 0.94 * len(segment)
			if solid or _regular(segment):
				here.append([start, end, not solid])
		still = []
		for group in open_:
			# A line goes on in the next row where most of it is there again.
			match = next((run for run in here if min(run[1], group["right"]) - max(run[0], group["left"])
				>= 0.8 * min(run[1] - run[0], group["right"] - group["left"])), None)
			if match is None:
				done.append(group)
				continue
			here.remove(match)
			group.update(left=min(group["left"], match[0]), right=max(group["right"], match[1]), bottom=y + 1,
				dotted=group["dotted"] or match[2])
			still.append(group)
		open_ = still + [{"left": run[0], "right": run[1], "top": y, "bottom": y + 1, "dotted": run[2]} for run in here]
	found = []
	for group in done:
		if group["bottom"] - group["top"] > thick:
			continue
		left, right = group["left"], group["right"]
		# Nothing may stand on the line or hang from it: then it is blank, and no underline of a word.
		above = _inkShare(rows, group["top"] - clear - 1, group["top"] - 1, left, right)
		below = _inkShare(rows, group["bottom"] + 1, group["bottom"] + clear + 1, left, right)
		if above > 0.06 or below > 0.06:
			continue
		found.append({"box": (left, group["top"], right, group["bottom"]), "dotted": group["dotted"]})
	return sorted(found, key=lambda rule: (rule["box"][1], rule["box"][0]))


def written(image, rule, tall, skip=None):
	"""Whether something is already written on a line: ink in the band of one letter's height above it. skip is
	the box of the label when the label itself stands right above its line; its columns are not counted."""
	_width, _height, rows = _rows(image)
	left, top, right, _bottom = rule["box"]
	spans = [(left, right)]
	if skip is not None and skip[2] > left and skip[0] < right:
		spans = [(start, end) for start, end in ((left, max(left, skip[0] - 2)), (min(right, skip[2] + 2), right)) if end > start]
	total = ink = 0
	for y in range(max(0, top - tall), max(0, top - 1)):
		for start, end in spans:
			ink += rows[y].count(b"\x01", start, end)
			total += end - start
	return total > 0 and ink / total > 0.015


def squares(image, scale=1.0):
	"""The small printed squares in a picture, as a check box is: {"box": (left, top, right, bottom), "ticked":
	whether something is drawn inside}, from the top down."""
	width, height, rows = _rows(image)
	low, high = pixels(MIN_SQUARE, scale), pixels(MAX_SQUARE, scale)
	edge = re.compile(rb"\x01{%d,%d}" % (low, high))
	found = []
	for y in range(height - low):
		for hit in edge.finditer(rows[y]):
			left, right = hit.span()
			# The whole edge, not a piece of a longer line.
			if (left > 0 and rows[y][left - 1]) or (right < width and rows[y][right]):
				continue
			side = right - left
			if any(abs(left - box[0]) <= 2 and abs(y - box[1]) <= 3 for box, _ticked in found):
				continue
			for bottom in range(y + side - max(2, side // 4), min(height, y + side + max(2, side // 4) + 1)):
				under = rows[bottom]
				if under.count(b"\x01", left, right) < 0.9 * side:
					continue
				between = range(y + 1, bottom)
				if not between:
					continue
				leftEdge = sum(1 for row in between if rows[row][left] or rows[row][min(width - 1, left + 1)])
				rightEdge = sum(1 for row in between if rows[row][right - 1] or rows[row][max(0, right - 2)])
				if leftEdge < 0.85 * len(between) or rightEdge < 0.85 * len(between):
					continue
				inner = _inkShare(rows, y + 3, bottom - 2, left + 3, right - 3) if side > 8 else 0.0
				# A filled block is no box; a box may hold a tick or a cross.
				if inner > 0.7:
					continue
				found.append(((left, y, right, bottom + 1), inner > 0.08))
				break
	return [{"box": box, "ticked": ticked} for box, ticked in sorted(found, key=lambda item: (item[0][1], item[0][0]))]


def blankFor(label, found, side=ANY):
	"""The line to write on that belongs to a label: (the rule, how it lies to the label: NEXT, UNDER or ABOVE), or
	None. label is the label's box; found is what rules() gave. To the right on the same line first; else the
	nearer of the line just under the label and the line just above it, as a line to sign has its word under it."""
	left, top, right, bottom = label
	tall = max(4, bottom - top)

	def beside():
		near = [rule for rule in found if rule["box"][0] >= right - tall // 2
			and top - 0.4 * tall <= rule["box"][3] <= bottom + 0.9 * tall]
		return min(near, key=lambda rule: rule["box"][0], default=None)

	def overlaps(rule):
		return min(rule["box"][2], right + 3 * tall) - max(rule["box"][0], left - 3 * tall) > 0 and (
			rule["box"][0] <= right and rule["box"][2] >= left or abs(rule["box"][0] - left) <= 3 * tall)

	def under():
		near = [rule for rule in found if bottom - 0.2 * tall < rule["box"][1] <= bottom + 3 * tall and overlaps(rule)]
		return min(near, key=lambda rule: rule["box"][1], default=None)

	def above():
		near = [rule for rule in found if top - 2.5 * tall <= rule["box"][3] < top + 0.2 * tall and overlaps(rule)]
		return max(near, key=lambda rule: rule["box"][3], default=None)

	if side in (NEXT, ANY):
		rule = beside()
		if rule is not None:
			return rule, NEXT
	if side == UNDER:
		rule = under()
		return (rule, UNDER) if rule is not None else None
	if side == ABOVE:
		rule = above()
		return (rule, ABOVE) if rule is not None else None
	low, high = under(), above()
	if low is not None and high is not None:
		return (low, UNDER) if low["box"][1] - bottom <= top - high["box"][3] else (high, ABOVE)
	if low is not None:
		return low, UNDER
	if high is not None:
		return high, ABOVE
	return None


def writePoint(rule, tall):
	"""Where to click to write on a line: a little in from its left end and a little above it, so that the writing
	sits on the line. tall is the height of the label's letters."""
	left, top, _right, _bottom = rule["box"]
	return left + max(4, round(tall * 0.6)), top - max(3, round(tall * 0.4))


def middleOf(box):
	return (box[0] + box[2]) // 2, (box[1] + box[3]) // 2


def squareFor(label, found):
	"""The check box that belongs to a label: the nearest square on the label's own line, before it or after it,
	or None. label is the label's box; found is what squares() gave."""
	left, top, right, bottom = label
	tall = max(4, bottom - top)
	near = []
	for square in found:
		box = square["box"]
		middle = (box[1] + box[3]) / 2.0
		if not top - 0.6 * tall <= middle <= bottom + 0.6 * tall:
			continue
		gap = left - box[2] if box[2] <= left + 2 else box[0] - right if box[0] >= right - 2 else None
		if gap is not None and gap <= 4 * tall:
			# A box before its label is the usual way; one after it is a little less likely to be the label's own.
			near.append((gap + (0 if box[2] <= left + 2 else tall), square))
	return min(near, key=lambda item: item[0])[1] if near else None


def _plainLines(image, upright):
	"""For each column (upright) or each row of a picture, whether it is one plain tone from end to end."""
	grey = image.convert("L")
	width, height = grey.size
	data = grey.tobytes()
	if upright:
		return [max(data[x::width]) - min(data[x::width]) <= 14 for x in range(width)]
	return [max(data[y * width:(y + 1) * width]) - min(data[y * width:(y + 1) * width]) <= 14 for y in range(height)]


def _spans(plain):
	"""The stretches between plain lines: [(start, end)]."""
	found, start = [], None
	for index, value in enumerate(list(plain) + [True]):
		if not value and start is None:
			start = index
		elif value and start is not None:
			found.append((start, index))
			start = None
	return found


def _even(spans):
	"""The spans that are tiles: at least two, all of nearly one size. A thin strip at the edge is dropped."""
	if len(spans) < 2:
		return []
	sizes = sorted(end - start for start, end in spans)
	middle = sizes[len(sizes) // 2]
	tiles = [(start, end) for start, end in spans if abs((end - start) - middle) <= max(3, middle * 0.15)]
	return tiles if 2 <= len(tiles) <= MAX_TILES else []


def grid(image, box=None):
	"""A grid of equal tiles in a picture or in an area of it, separated by gaps of one plain tone: (rows, columns,
	[the box of every tile, row by row]) or None. The tiles are numbered from 1 by the caller, left to right and
	top to bottom, the way a person reads them out."""
	area = image.convert("RGB")
	offsetX = offsetY = 0
	if box is not None:
		left, top, right, bottom = (int(round(value)) for value in box)
		left, top = max(0, left), max(0, top)
		right, bottom = min(area.size[0], right), min(area.size[1], bottom)
		if right - left < 8 or bottom - top < 8:
			return None
		area = area.crop((left, top, right, bottom))
		offsetX, offsetY = left, top
	across = _even(_spans(_plainLines(area, True)))
	down = _even(_spans(_plainLines(area, False)))
	if not across or not down:
		return None
	tiles = [(offsetX + x0, offsetY + y0, offsetX + x1, offsetY + y1) for y0, y1 in down for x0, x1 in across]
	return len(down), len(across), tiles


def near(lines, box, reach):
	"""The words read in a picture that stand within `reach` pixels of a box, nearest first: [(distance, word)]."""
	left, top, right, bottom = box
	found = []
	for line in lines or ():
		for word in line:
			l, t, r, b = wordBox(word)
			dx = max(left - r, l - right, 0)
			dy = max(top - b, t - bottom, 0)
			distance = (dx * dx + dy * dy) ** 0.5
			if distance <= reach:
				found.append((distance, word))
	return sorted(found, key=lambda item: item[0])


def whereText(box, size):
	"""Where a place is in a picture, in words a blind person can use: "near the top, on the left"."""
	width, height = size
	x, y = middleOf(box)
	down = "near the top" if y < height / 3.0 else "near the bottom" if y > height * 2 / 3.0 else "in the middle"
	across = "on the left" if x < width / 3.0 else "on the right" if x > width * 2 / 3.0 else ""
	return f"{down}, {across}" if across else down
