# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the plain reasoning behind working the mouse from the keyboard: which mouse action a request
# means, where a drag should end, how the pointer moves inside a window, and how to say where it is.
# Sighted people click, right-click, double-click and drag on controls a screen reader cannot reach; this is
# what lets a blind user do the same. No NVDA dependencies, and nothing here touches the mouse.

import re

from . import scrolling

CLICK, DOUBLE, RIGHT, HOVER, HOLD = "click", "double click", "right click", "hover", "press and hold"
MIDDLE, TRIPLE = "middle click", "triple click"
ACTIONS = [CLICK, DOUBLE, RIGHT, MIDDLE, TRIPLE, HOVER, HOLD]
# Keys that can be held down during a click, as a request names them.
MODIFIERS = ("control", "shift", "alt")
# How long the button is kept down when the words give no time, and the longest a request may ask for.
HOLD_DEFAULT, HOLD_MAX = 1.5, 60.0
# A hotkey that keeps the button down lets go by itself after this long, so that it is never left down.
HOLD_LIMIT = 120.0
# How long the pointer rests on something before VisionClaw looks at what appeared.
REST_SECONDS = 1.2
# Watching a place for a change: how long by default and at most, and how often it is looked at.
WAIT_DEFAULT, WAIT_MAX, LOOK_EVERY = 30.0, 300.0, 0.04
# Clicking in a rhythm: how many clicks by default and at most, and the time from one to the next.
TIMES_DEFAULT, TIMES_MAX, EVERY_DEFAULT, EVERY_FAST, EVERY_LEAST = 10, 200, 0.25, 0.08, 0.03
WHEN, RHYTHM = "when it changes", "in a rhythm"
# How large a gesture is drawn, as a share of the window's shorter side.
GESTURE_SHARE = 0.25
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
	"kb:s": ("bars",), "kb:d": ("take",),
	# Rest on what is here and say what appears; click as soon as what is here changes; only a tone when it does.
	"kb:t": ("rest",), "kb:c": ("when", True), "kb:shift+c": ("when", False),
	# How the mouse is moved: Windows' pointer, a game's own pointer, or a view the mouse turns (claw/direct.py).
	"kb:m": ("way",),
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
	if re.search(r"middle[- ](click|button|mouse)|wheel[- ]click|\bclick\w*\b.*\bwith the (mouse )?wheel\b", text):
		return MIDDLE
	if re.search(r"triple[- ]click", text):
		return TRIPLE
	if _HOLD_WORDS.search(text):
		return HOLD
	if re.search(r"\b(hover(s|ing)?|point(s|ing)? (at|to)|mouse ?over|rest(s|ing)? the (mouse|pointer) on"
			r"|move the (mouse|pointer) (to|over|onto))\b", text):
		return HOVER
	# Something that is only to be found is pointed at, not clicked: the mouse rests on it, and what appears is
	# said. "Find and click" is a click.
	if re.search(r"^\s*(please )?(can you )?(find|locate|where is|where's)\b", text) and not re.search(
			r"\b(click|press|push|activate|open|select|choose)\b", text):
		return HOVER
	return CLICK


_HOLD_WORDS = re.compile(
	r"\b(press|click|tap|push)(es|s)? and holds?\b|\bhold(s|ing)? (down|the (left )?(mouse )?button)\b|\blong[- ](press|click)\b"
	r"|\bkeep\b.{0,40}\b(pressed|held)( down)?\b|\bhold\b.{0,60}\bfor (\d|an?\b|half|one|two|three|four|five|six|seven|eight|nine|ten)")
_COUNTS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
	"nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100}
_COUNT = r"(\d+(?:\.\d+)?|half an?|" + "|".join(sorted(_COUNTS, key=len, reverse=True)) + r")"
# A number may stand right before its unit ("3s", "200ms"); a word needs a space, or "as" would be "a s".
_TIME = re.compile(
	r"\b(?:(\d+(?:\.\d+)?)\s*(milliseconds?|ms|seconds?|secs?|s|minutes?|mins?)"
	r"|(half an?|" + "|".join(sorted(_COUNTS, key=len, reverse=True)) + r")\s+(milliseconds?|seconds?|secs?|minutes?|mins?))\b")


def _count(word):
	word = word.strip()
	if word.startswith("half"):
		return 0.5
	return float(_COUNTS[word]) if word in _COUNTS else float(word)


def secondsIn(words):
	"""A length of time given in words ("3 seconds", "half a second", "200 milliseconds"), in seconds, or None."""
	found = _TIME.search((words or "").lower())
	if not found:
		return None
	unit = found.group(2) or found.group(4)
	amount = _count(found.group(1) or found.group(3))
	return amount / 1000 if unit.startswith(("ms", "milli")) else amount * 60 if unit.startswith("min") else amount


def holdSeconds(words):
	"""How long the mouse button is kept down, from the user's words; never longer than HOLD_MAX."""
	asked = secondsIn(words)
	return max(0.1, min(HOLD_MAX, asked)) if asked else HOLD_DEFAULT


def secondsText(seconds):
	"""A length of time in words: "half a second", "1 second", "2.5 seconds", "2 minutes"."""
	if seconds >= 120 and seconds % 60 == 0:
		return f"{seconds / 60:g} minutes"
	if seconds < 1:
		return "half a second" if seconds == 0.5 else f"{round(seconds * 1000)} milliseconds"
	return f"{seconds:g} second" + ("" if seconds == 1 else "s")


_KEY_NAMES = {"ctrl": "control", "control": "control", "shift": "shift", "alt": "alt"}
_KEY = r"(ctrl|control|shift|alt)"
_TWO_KEYS = r"(?:the\s+)?" + _KEY + r"(?:\s+(?:and|\+)\s+(?:the\s+)?" + _KEY + r")?"
# "Control-click"; "with the Shift key held down"; "holding Alt". A key must be said to be a key or to be held:
# "with the control panel" names no key.
_HELD_KEYS = re.compile(
	r"\b" + _KEY + r"\s*[-+ ]\s*(?:" + _KEY + r"\s*[-+ ]\s*)?(?:left[- ]|right[- ]|double[- ]|middle[- ])?click"
	r"|\b(?:with|hold|keep|keeping)\s+(?:down\s+)?" + _TWO_KEYS + r"(?:\s+keys?|\s+held|\s+down|\s+pressed)+"
	r"|\bholding\s+(?:down\s+)?" + _TWO_KEYS + r"\b")


def modifiersOf(words):
	"""The keys a request wants held down during a click ("control-click", "with Shift held"), in the order of
	MODIFIERS, or []."""
	found = set()
	for match in _HELD_KEYS.finditer((words or "").lower()):
		found.update(_KEY_NAMES[name] for name in match.groups() if name)
	return [name for name in MODIFIERS if name in found]


_SPOT_ENDS = (
	(r"\b(left|start|beginning)\b", 0.05, None), (r"\bright\b|\b(far )?end\b", 0.95, None),
	(r"\b(top|upper)\b", None, 0.05), (r"\b(bottom|lower)\b", None, 0.95),
)
_SPOT_PART = re.compile(
	r"\b(?:at|on|near|in)? ?the ((?:(?:top|bottom|upper|lower|far)[- ])?(?:left|right|top|bottom|upper|lower|start|beginning|end))"
	r"(?:[- ]hand)? (?:end|edge|side|part|half|corner|of)\b")
_SPOT_SHARE = re.compile(r"(\d{1,3})\s*(?:%|percent)\s*(across|along|in|through|from the left|of the way|down|from the top)?")


def spotOf(words):
	"""Where on a thing a request wants the click, as shares of its width and height from its top left
	("30 percent across", "the right end", "the top left corner"), or None for its middle. This is how a bar
	that is clicked where the value should be, a picture or a board is worked."""
	text = (words or "").lower()
	share = _SPOT_SHARE.search(text)
	if share and share.group(2):
		amount = max(0, min(100, int(share.group(1)))) / 100
		return (0.5, amount) if share.group(2) in ("down", "from the top") else (amount, 0.5)
	part = _SPOT_PART.search(text)
	if not part:
		return None
	across = down = None
	for pattern, x, y in _SPOT_ENDS:
		if re.search(pattern, part.group(1)):
			across, down = (x if across is None else across), (y if down is None else down)
	return (0.5 if across is None else across, 0.5 if down is None else down)


def spotText(spot):
	"""A place on a thing in words: "30 percent across", "5 percent across and 95 percent down"."""
	across, down = round(spot[0] * 100), round(spot[1] * 100)
	if down == 50:
		return f"{across} percent across"
	if across == 50:
		return f"{down} percent down"
	return f"{across} percent across and {down} percent down"


# --- Clicking at the right moment ---

_RHYTHM_WORDS = re.compile(
	r"\btimes\b|\btwice\b|\bevery\b|\brepeatedly\b|\brapid(ly)?\b|\bmash\b|\bas fast as\b|\brhythm\b|\bkeep (on )?clicking\b"
	r"|\bover and over\b|\bagain and again\b|\bin time\b|\bon the beat\b")
_WHEN_WORDS = re.compile(
	r"\bwhen\b|\bas soon as\b|\bonce (it|the|that|this)\b|\bthe moment\b|\bat the right (moment|time)\b|\bwait (for|until|till)\b"
	r"|\buntil (it|the)\b")
_TIMES = re.compile(r"\b" + _COUNT + r"\s+times\b")
_PER_SECOND = re.compile(r"\b(?:" + _COUNT + r"\s+times|(twice)|(once))\s+(?:a|per|every)\s+second\b")


def timingOf(words):
	"""What clicking at the right moment the user's words ask for, or None when they ask for neither kind:
	{"mode": WHEN, "wait": seconds to watch at most}, or
	{"mode": RHYTHM, "times": how many clicks, "every": seconds from one click to the next}."""
	text = (words or "").lower()
	if _RHYTHM_WORDS.search(text):
		times = _TIMES.search(text)
		count = int(_count(times.group(1))) if times else 2 if re.search(r"\btwice\b", text) and not _PER_SECOND.search(text) else TIMES_DEFAULT
		every = EVERY_FAST if re.search(r"\b(fast|rapid(ly)?|quick(ly)?|mash)\b", text) else EVERY_DEFAULT
		rate = _PER_SECOND.search(text)
		gap = re.search(r"\bevery\s+" + _COUNT + r"?\s*(milliseconds?|ms|seconds?|secs?|minutes?|mins?)\b", text)
		if rate:
			every = 1.0 / (_count(rate.group(1)) if rate.group(1) else 2 if rate.group(2) else 1)
		elif gap:
			every = secondsIn((gap.group(1) or "one") + " " + gap.group(2))
		return {"mode": RHYTHM, "times": max(1, min(TIMES_MAX, count)), "every": max(EVERY_LEAST, min(60.0, every))}
	if _WHEN_WORDS.search(text):
		within = re.search(r"\b(within|for up to|up to|at most|for|wait)\s+" + _COUNT + r"\s*(seconds?|secs?|minutes?|mins?)\b", text)
		wait = secondsIn(within.group(2) + " " + within.group(3)) if within else WAIT_DEFAULT
		return {"mode": WHEN, "wait": max(1.0, min(WAIT_MAX, wait))}
	return None


def trigger(noise):
	"""How much of a watched place must change before it counts as the moment, given how much it changes by
	itself from one look to the next. None when it moves so much by itself that no moment can be told."""
	if noise > 0.25:
		return None
	return max(0.01, 3 * noise)


def appeared(before, after):
	"""Where a picture changed between two looks, as (left, top, right, bottom) inside it, or None when
	nothing a person would notice did. PIL images of the same size."""
	if before is None or after is None or before.size != after.size:
		return None
	from PIL import ImageChops
	differs = ImageChops.difference(before.convert("L"), after.convert("L")).point(lambda value: 255 if value > 24 else 0)
	box = differs.getbbox()
	if box is None or (box[2] - box[0]) * (box[3] - box[1]) < 36:
		return None
	return box


# --- Gestures: a line or a shape drawn with the mouse button held down ---

LEFT_BUTTON, RIGHT_BUTTON = "left", "right"
# Shapes as strokes, each a list of points around the place the gesture is drawn at: one unit is the size
# of the gesture, x to the right, y down. Two strokes mean the button is let go in between.
_SHAPES = (
	(r"\b(tick|check ?mark)\b", "a tick", [[(-0.5, 0.0), (-0.15, 0.4), (0.5, -0.4)]]),
	(r"\bzig-?zags?\b|\bscribble\b|\bscratch\b|\bwavy\b", "a zigzag", [[(-0.5, 0.2), (-0.25, -0.2), (0.0, 0.2), (0.25, -0.2), (0.5, 0.2)]]),
	(r"\b(square|rectangle)\b", "a square", [[(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5)]]),
	(r"\btriangle\b", "a triangle", [[(0.0, -0.5), (0.5, 0.5), (-0.5, 0.5), (0.0, -0.5)]]),
	(r"\b(a cross|an x|letter x|the x)\b", "a cross", [[(-0.5, -0.5), (0.5, 0.5)], [(0.5, -0.5), (-0.5, 0.5)]]),
	(r"\bletter l\b|\bl[- ]shape\b", "the letter L", [[(-0.3, -0.5), (-0.3, 0.5), (0.4, 0.5)]]),
	(r"\bletter v\b|\bv[- ]shape\b", "the letter V", [[(-0.5, -0.5), (0.0, 0.5), (0.5, -0.5)]]),
	(r"\bletter z\b|\bz[- ]shape\b", "the letter Z", [[(-0.5, -0.5), (0.5, -0.5), (-0.5, 0.5), (0.5, 0.5)]]),
	(r"\bletter n\b", "the letter N", [[(-0.4, 0.5), (-0.4, -0.5), (0.4, 0.5), (0.4, -0.5)]]),
	(r"\bletter m\b", "the letter M", [[(-0.5, 0.5), (-0.5, -0.5), (0.0, 0.2), (0.5, -0.5), (0.5, 0.5)]]),
	(r"\bletter w\b", "the letter W", [[(-0.5, -0.5), (-0.25, 0.5), (0.0, -0.2), (0.25, 0.5), (0.5, -0.5)]]),
)
_GESTURE_SIZES = (
	(r"\b(all the way|whole|full|entire)\b", 0.9), (r"\b(tiny|small|short|little)\b", 0.1),
	(r"\b(large|big|long|wide|far)\b", 0.5),
)
_RIGHT_BUTTON = re.compile(r"\b(with|using|holding|hold) (the |my )?right( mouse)? button( held)?( down)?\b|\bright[- ](button|drag)\b")


def _circle(clockwise):
	import math
	turn = 1 if clockwise else -1
	return [[(round(0.5 * math.sin(turn * 2 * math.pi * i / 24), 3), round(-0.5 * math.cos(2 * math.pi * i / 24), 3)) for i in range(25)]]


def gestureOf(words):
	"""The gesture the user's words ask for, or None when they name none:
	{"text": what it is, in words, "strokes": lists of points in units of its size, "button", "size": share of
	the window's shorter side, "pace": seconds from one small step to the next}."""
	text = (words or "").lower()
	button = RIGHT_BUTTON if _RIGHT_BUTTON.search(text) else LEFT_BUTTON
	text = _RIGHT_BUTTON.sub(" ", text)
	strokes = name = None
	if re.search(r"\b(circle|ring|loop|round and round)\b|\b(anti|counter)-?clockwise\b|\bclockwise\b", text):
		clockwise = not re.search(r"\b(anti|counter)-?clockwise\b", text)
		strokes, name = _circle(clockwise), "a circle, " + ("clockwise" if clockwise else "anticlockwise")
	for pattern, shape, points in _SHAPES if strokes is None else ():
		if re.search(pattern, text):
			strokes, name = [list(stroke) for stroke in points], shape
			break
	if strokes is None:
		# A line in one direction, or one direction after another: "swipe left", "down then right".
		ways = [found.group(1) for found in re.finditer(r"\b(left|right|up|down)(wards?)?\b", text)][:6]
		if not ways:
			return None
		x = y = 0.0
		line = [(0.0, 0.0)]
		for way in ways:
			dx, dy = DIRECTIONS[way]
			x, y = x + dx, y + dy
			line.append((x, y))
		strokes = [line]
		name = ("a swipe " if len(ways) == 1 else "a line ") + ", then ".join(
			way if way in ("up", "down") else f"to the {way}" for way in ways)
	percent = re.search(r"(\d+)\s*(%|percent)", text)
	size = int(percent.group(1)) / 100 if percent else next(
		(share for pattern, share in _GESTURE_SIZES if re.search(pattern, text)), GESTURE_SHARE)
	pace = 0.004 if re.search(r"\b(flick|fast|quick(ly)?)\b", text) else 0.03 if re.search(r"\bslow(ly)?\b", text) else 0.012
	return {"text": name, "strokes": strokes, "button": button, "size": max(0.02, min(1.0, size)), "pace": pace}


def gesturePaths(gesture, place, box):
	"""The points the mouse passes through for a gesture drawn at a place in a window, one list for each
	stroke, in small steps and kept inside the window."""
	left, top, right, bottom = box
	unit = gesture["size"] * min(right - left, bottom - top)
	paths = []
	for stroke in gesture["strokes"]:
		corners = [clamp(round(place[0] + x * unit), round(place[1] + y * unit), box) for x, y in stroke]
		points = [corners[0]]
		for start, end in zip(corners, corners[1:]):
			steps = max(2, round(max(abs(end[0] - start[0]), abs(end[1] - start[1])) / 6))
			points += path(start, end, steps)
		paths.append(points)
	return paths


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
