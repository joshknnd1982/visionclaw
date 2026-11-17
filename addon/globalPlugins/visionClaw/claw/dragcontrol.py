# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the plain reasoning behind working a dial, a knob, a custom slider or another control that a
# sighted person drags, with the arrow keys instead. A control is worked in one of five ways: through Windows
# itself where the program offers its value, with the mouse wheel, or by dragging up and down, sideways or
# around in a circle. Which way works is found out by trying each and looking whether the picture changed.
# What the control then shows is the text near it that changed.
# No NVDA dependencies, and nothing here touches the mouse. Pictures are PIL images. Sizes are for a plain
# screen at 100 percent and are turned into pixels with scrolling.pixels.

import math
import re

from . import scrolling

VALUE, WHEEL, UPDOWN, SIDEWAYS, AROUND = "value", "wheel", "up and down", "sideways", "around"
METHODS = [VALUE, WHEEL, UPDOWN, SIDEWAYS, AROUND]
STEP, FINE, FAR = "step", "fine", "far"
# How far one key press drags, how many notches it turns the wheel, and what share of a value's range it moves.
_DRAG = {STEP: 8, FINE: 2, FAR: 32}
_NOTCHES = {STEP: 1, FINE: 1, FAR: 4}
_SHARE = {STEP: 0.05, FINE: 0.01, FAR: 0.2}
# A dial whose size is not known is taken to be this far from its middle to its rim.
RADIUS = 16
# The square around the control that is compared before and after, and the area whose text is read.
SPOT, AREA = 96, (320, 220)
# The control changed if at least this much of the square did.
CHANGED = 0.004
# "To the end" stops when nothing moves any more, and never goes on longer than this.
MAX_END_STROKES = 40
ACTION = "work"

# The keys while a control is held, as NVDA spells them.
KEYS = {
	"kb:uparrow": ("turn", 1, STEP), "kb:rightarrow": ("turn", 1, STEP),
	"kb:downarrow": ("turn", -1, STEP), "kb:leftarrow": ("turn", -1, STEP),
	"kb:shift+uparrow": ("turn", 1, FINE), "kb:shift+rightarrow": ("turn", 1, FINE),
	"kb:shift+downarrow": ("turn", -1, FINE), "kb:shift+leftarrow": ("turn", -1, FINE),
	"kb:control+uparrow": ("turn", 1, FAR), "kb:control+rightarrow": ("turn", 1, FAR),
	"kb:control+downarrow": ("turn", -1, FAR), "kb:control+leftarrow": ("turn", -1, FAR),
	"kb:pageup": ("turn", 1, FAR), "kb:pagedown": ("turn", -1, FAR),
	"kb:home": ("end", -1), "kb:end": ("end", 1),
	"kb:r": ("read",), "kb:w": ("look",), "kb:m": ("method",), "kb:k": ("keep",), "kb:h": ("help",),
	"kb:escape": ("exit",),
}
_AT_POINTER = re.compile(
	r"\b(at|under|below|beneath) (the |my )?(mouse|pointer|cursor)\b|\bwhere (the |my )?(mouse|pointer|cursor) is\b", re.IGNORECASE)
_KEEP = re.compile(
	r"\bhot ?keys?\b|\bshortcuts?\b|\b(keep|save|remember)\b|\bfor good\b|\balways\b|\bevery time\b|\bfrom now on\b|\bpermanent", re.IGNORECASE)


def methodOf(words):
	"""The way a control is worked, where the user's own words say it, else None."""
	text = (words or "").lower()
	if re.search(r"\b(mouse )?wheel\b|\bscroll(ing)? (on|over)\b", text):
		return WHEEL
	if re.search(r"\b(in a |a )?circle\b|\bcircular\b|\bround and round\b|\bclockwise\b|\brotat\w+\b|\baround\b", text):
		return AROUND
	if re.search(r"\bup (and|or) down\b|\bupwards?\b|\bvertical(ly)?\b|\bup-down\b", text):
		return UPDOWN
	if re.search(r"\bsideways\b|\bleft (and|or|to) right\b|\bhorizontal(ly)?\b|\bacross\b", text):
		return SIDEWAYS
	return None


def kindWord(words):
	"""What to call the control, from the user's words."""
	text = (words or "").lower()
	for pattern, word in ((r"\b(dial|knob)s?\b", "dial"), (r"\b(slider|fader|scrubber|seek ?bar)s?\b", "slider"),
			(r"\b(joystick|stick|lever)s?\b", "lever"), (r"\bwheels?\b", "wheel")):
		if re.search(pattern, text):
			return word
	return "control"


def atPointer(words):
	return bool(_AT_POINTER.search(words or ""))


def wantsKept(words):
	return bool(_KEEP.search(words or ""))


def order(way=None, hasValue=False):
	"""The ways to try, in order. The wheel comes first: it presses nothing, so it can do no harm. Dragging
	around comes late: on some dials a press on the rim sets the value at once. way: how the control is
	thought to be worked (a word of working.WAYS), which moves that way forward."""
	first = {"drag sideways": SIDEWAYS, "drag up and down": UPDOWN}.get(way)
	tried = [WHEEL] + ([first] if first else []) + [UPDOWN, SIDEWAYS, AROUND]
	found = ([VALUE] if hasValue else [])
	for method in tried:
		if method not in found:
			found.append(method)
	return found


def stroke(method, direction, size, scale=1.0, radius=None):
	"""One drag as the points the mouse passes through, each given from the place of the control: the first
	is where the button goes down, the last where it is let go. direction: 1 turns up, -1 down."""
	distance = scrolling.pixels(_DRAG.get(size, _DRAG[STEP]), scale)
	if method == AROUND:
		reach = max(4, int(radius or scrolling.pixels(RADIUS, scale)))
		angle = direction * distance / reach
		count = max(3, math.ceil(abs(angle) / 0.12))
		return [(round(reach * math.sin(angle * i / count)), round(-reach * math.cos(angle * i / count))) for i in range(count + 1)]
	count = max(2, math.ceil(distance / 3))
	across, down = (direction, 0) if method == SIDEWAYS else (0, -direction)
	return [(round(across * distance * i / count), round(down * distance * i / count)) for i in range(count + 1)]


def notches(size):
	return _NOTCHES.get(size, 1)


def nextValue(now, low, high, direction, size, small=0.0):
	"""The value one key press further, kept inside the range. small: the control's own smallest step."""
	span = high - low
	if span <= 0:
		return now
	step = span * _SHARE.get(size, _SHARE[STEP])
	if small and small > 0:
		step = small if size == FINE else max(small, round(step / small) * small)
	return max(low, min(high, now + direction * step))


def valueText(now, low, high):
	"""A value as a share of its range, for a control that has no words of its own for it."""
	span = high - low
	return f"{round(100 * (now - low) / span)} percent" if span > 0 else f"{now:g}"


def changed(before, after):
	"""How much of the picture of a control changed between two looks, from 0.0 to 1.0."""
	if before is None or after is None or before.size != after.size:
		return 1.0
	a, b = before.convert("L").resize((64, 64)).tobytes(), after.convert("L").resize((64, 64)).tobytes()
	return sum(1 for x, y in zip(a, b) if abs(x - y) > 24) / len(a)


def newText(before, after):
	"""The text that is there now and was not before: after a turn, most likely the value. Lists of lines."""
	old = {" ".join(line.split()) for line in before or ()}
	fresh = [" ".join(line.split()) for line in after or () if " ".join(line.split()) not in old]
	return " ".join(line for line in fresh if line)[:100]


def shareOf(point, box):
	"""A place on the screen as a share of a window (left, top, right, bottom), so that it can be kept."""
	left, top, right, bottom = box
	return (round((point[0] - left) / max(1, right - left), 4), round((point[1] - top) / max(1, bottom - top), 4))


def pointOf(share, box):
	left, top, right, bottom = box
	x, y = left + share[0] * (right - left), top + share[1] * (bottom - top)
	return max(left + 1, min(right - 2, round(x))), max(top + 1, min(bottom - 2, round(y)))


def around(point, size, box):
	"""A rectangle of a size (one number for a square, or width and height) around a point, kept inside a box."""
	width, height = (size, size) if isinstance(size, (int, float)) else size
	left, top, right, bottom = box
	width, height = min(int(width), right - left), min(int(height), bottom - top)
	x = max(left, min(right - width, point[0] - width // 2))
	y = max(top, min(bottom - height, point[1] - height // 2))
	return (x, y, x + width, y + height)


def handleOf(items, index):
	"""Where to take hold of a thing named in a window's picture, as (x, y, radius) in the picture.
	The name is often the text beside or under a dial, not the dial: if an icon was joined to the text, or
	stands right beside it, that is the thing to hold. Otherwise the middle of the item itself."""
	item = items[index]
	left, top, right, bottom = item["box"]
	if item.get("kind") == "icon":
		return (left + right) // 2, (top + bottom) // 2, max(4, min(right - left, bottom - top) * 7 // 20)
	textBox = item.get("textBox") or item["box"]
	if tuple(textBox) != tuple(item["box"]):
		# The part of the item that is not its text.
		tl, tt, tr, tb = textBox
		parts = [(left, top, tl, bottom), (tr, top, right, bottom), (left, top, right, tt), (left, tb, right, bottom)]
		l, t, r, b = max(parts, key=lambda p: max(0, p[2] - p[0]) * max(0, p[3] - p[1]))
		if r - l >= 6 and b - t >= 6:
			return (l + r) // 2, (t + b) // 2, max(4, min(r - l, b - t) * 7 // 20)
	height = max(8, textBox[3] - textBox[1])
	best = None
	for other in items:
		if other is item or other.get("kind") != "icon":
			continue
		ol, ot, orr, ob = other["box"]
		gap = max(max(ol - right, left - orr, 0), max(ot - bottom, top - ob, 0))
		if gap <= 2.5 * height and (best is None or gap < best[0]):
			best = (gap, other)
	if best is not None:
		ol, ot, orr, ob = best[1]["box"]
		return (ol + orr) // 2, (ot + ob) // 2, max(4, min(orr - ol, ob - ot) * 7 // 20)
	return (left + right) // 2, (top + bottom) // 2, 0


def methodText(method):
	return {
		VALUE: "through Windows itself, without the mouse", WHEEL: "with the mouse wheel",
		UPDOWN: "by dragging it up and down", SIDEWAYS: "by dragging it sideways",
		AROUND: "by dragging around it in a circle",
	}.get(method, "in a way not found out yet")


def helpText(name, kind, method):
	"""What is said when a control is taken hold of."""
	what = f"{name}, a {kind}" if name and kind != "control" and kind not in name.lower() else (name or f"this {kind}")
	return (
		f"The arrow keys now work {what}, {methodText(method)}. Up and Right turn it up, Down and Left turn it "
		"down; with Shift a small step, with Control a large one. Home and End go to its ends. R reads what is "
		"shown at it, W asks the vision model what it shows, M tries another way of working it, K keeps it under "
		"a hotkey for this program, H repeats this. Escape gives the arrow keys back."
	)


def describe(binding):
	"""A kept control in one sentence, for the list of what VisionClaw has made."""
	return (
		f"{binding.get('key', '')} takes hold of {binding.get('name') or 'a ' + binding.get('kind', 'control')}, "
		f"so the arrow keys work it {methodText(binding.get('method'))}")
