# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the plain reasoning behind working the mouse from the keyboard: which mouse action a request
# means, where a drag should end, how the pointer moves inside a window, and how to say where it is.
# Sighted people click, right-click, double-click and drag on controls a screen reader cannot reach; this is
# what lets a blind user do the same. No NVDA dependencies, and nothing here touches the mouse.

import re

from . import scrolling

CLICK, DOUBLE, RIGHT, HOVER = "click", "double click", "right click", "hover"
ACTIONS = [CLICK, DOUBLE, RIGHT, HOVER]
# How far one press of an arrow key moves the pointer: plain, with Shift (fine), with Control (far). These are
# sizes on a plain screen at 100 percent; stepFor turns them into the pixels of the user's screen and window.
STEP, FINE, FAR = 20, 4, 100
# How far the wheel is turned by the scroll keys of pointer mode: about a page, or one notch.
PAGE, NOTCH = "page", "notch"
DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
# How far "a little" and "a lot" are, as a share of the window, when a drag is asked for in words.
_AMOUNTS = (
	(r"\b(all the way|fully|to the end|to the (very )?(top|bottom|edge))\b", 1.0),
	(r"\b(tiny|slightly|a (tiny|wee) bit)\b", 0.03), (r"\b(a little|a bit|little|bit)\b", 0.08),
	(r"\b(a lot|far|much)\b", 0.35),
)
DEFAULT_SHARE = 0.15
# The keys of pointer mode, as NVDA spells them, and what each does.
KEYS = {
	"kb:leftarrow": ("move", "left", STEP), "kb:rightarrow": ("move", "right", STEP),
	"kb:uparrow": ("move", "up", STEP), "kb:downarrow": ("move", "down", STEP),
	"kb:shift+leftarrow": ("move", "left", FINE), "kb:shift+rightarrow": ("move", "right", FINE),
	"kb:shift+uparrow": ("move", "up", FINE), "kb:shift+downarrow": ("move", "down", FINE),
	"kb:control+leftarrow": ("move", "left", FAR), "kb:control+rightarrow": ("move", "right", FAR),
	"kb:control+uparrow": ("move", "up", FAR), "kb:control+downarrow": ("move", "down", FAR),
	"kb:enter": ("click",), "kb:numpadenter": ("click",), "kb:space": ("click",),
	"kb:shift+enter": ("double",), "kb:applications": ("right",), "kb:shift+f10": ("right",),
	"kb:g": ("grab",), "kb:w": ("look",), "kb:r": ("read",), "kb:p": ("where",), "kb:h": ("help",),
	"kb:home": ("centre",), "kb:escape": ("exit",),
	"kb:pagedown": ("scroll", "down", PAGE), "kb:pageup": ("scroll", "up", PAGE),
	"kb:shift+pagedown": ("scroll", "down", NOTCH), "kb:shift+pageup": ("scroll", "up", NOTCH),
	"kb:control+pagedown": ("scroll", "right", PAGE), "kb:control+pageup": ("scroll", "left", PAGE),
	"kb:s": ("bars",),
}


def stepFor(amount, box, scale):
	"""One key press's move in the pixels of this screen: STEP, FINE or FAR, made to fit the screen's scaling
	and the window's size, so a step looks the same on a small laptop screen and on a large 4K one."""
	plain, fine, far = scrolling.steps(box, scale)
	return {STEP: plain, FINE: fine, FAR: far}.get(amount, amount)


def notchesFor(amount):
	return scrolling.PAGE_NOTCHES if amount == PAGE else 1


def actionOf(part):
	"""Which mouse action a request means, from its words."""
	text = (part or "").lower()
	if re.search(r"right[- ]click|context menu|secondary click|right mouse", text):
		return RIGHT
	if re.search(r"double[- ]click|click twice|click two times", text):
		return DOUBLE
	if re.search(r"\b(hover|point at|point to|move the (mouse|pointer) (to|over|onto))\b", text):
		return HOVER
	return CLICK


def clamp(x, y, box):
	"""The point kept inside a box (left, top, right, bottom), one pixel in from its edges."""
	left, top, right, bottom = box
	return max(left + 1, min(right - 2, x)), max(top + 1, min(bottom - 2, y))


def move(x, y, direction, amount, box):
	dx, dy = DIRECTIONS[direction]
	return clamp(x + dx * amount, y + dy * amount, box)


def centre(box):
	left, top, right, bottom = box
	return (left + right) // 2, (top + bottom) // 2


def where(x, y, box):
	"""Where the pointer is in a window, in words a person can picture."""
	left, top, right, bottom = box
	across = round(100 * (x - left) / max(1, right - left - 1))
	down = round(100 * (y - top) / max(1, bottom - top - 1))
	return f"{max(0, min(100, across))} percent across, {max(0, min(100, down))} percent down"


def pitch(y, box):
	"""A tone for the pointer's height in the window: high at the top, low at the bottom."""
	_left, top, _right, bottom = box
	share = (y - top) / max(1, bottom - top - 1)
	return int(1500 - 1200 * max(0.0, min(1.0, share)))


def path(start, end, steps=14):
	"""The points a drag passes through. Many programs only follow a drag that moves in small steps."""
	(x0, y0), (x1, y1) = start, end
	steps = max(2, steps)
	return [(round(x0 + (x1 - x0) * i / steps), round(y0 + (y1 - y0) * i / steps)) for i in range(1, steps + 1)]


def dragOffset(words, box):
	"""If a drag's destination is given as a direction ("right a little", "down 50 pixels", "left 20 percent"),
	the distance to drag as (dx, dy) in pixels. None if the words name a thing to drag onto instead."""
	text = (words or "").lower()
	found = re.search(r"\b(left|right|up|down)(wards?)?\b", text)
	if not found:
		return None
	dx, dy = DIRECTIONS[found.group(1)]
	left, top, right, bottom = box
	span = (right - left) if dx else (bottom - top)
	number = re.search(r"(\d+)\s*(%|percent|px|pixels?)?", text)
	if number:
		amount = int(number.group(1))
		distance = span * amount / 100 if number.group(2) in ("%", "percent") else amount
	else:
		share = next((s for pattern, s in _AMOUNTS if re.search(pattern, text)), DEFAULT_SHARE)
		distance = span * share
	return round(dx * distance), round(dy * distance)
