# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the plain reasoning behind fingers and pressure. A sighted person pinches a map with two
# fingers, turns a photo, swipes with three, taps, and presses harder with a pen for a thicker line. Here is
# what a request in words means of that: which gesture, with how many fingers, how far, how hard; and the
# places each finger or the pen passes through, one small step after another, kept inside the window.
# What stands in for a gesture when a program takes no touch (the wheel for a pinch or a swipe) is said here too.
# No NVDA dependencies, and nothing here touches the screen: the frames are lists of numbers.

import math
import re

from . import pointer, scrolling

PINCH, SPREAD, SWIPE, ROTATE, TAP, HOLD = "pinch", "spread", "swipe", "rotate", "tap", "touch and hold"
KINDS = [PINCH, SPREAD, SWIPE, ROTATE, TAP, HOLD]
MAX_FINGERS = 5
# Windows counts pressure from 0 to this.
FULL = 1024
# How hard a finger or the pen presses when the words do not say, as a share of full.
PRESSURE_DEFAULT = 0.5
# How far the fingers travel, as a share of the window's shorter side, when the words do not say.
SHARE_DEFAULT = 0.25
# How far apart fingers lie side by side, and how close two pinching fingers come, on a plain screen at
# 100 percent (turned into pixels with scrolling.pixels).
FINGER_GAP, PINCH_NEAR = 44, 14
# How many small steps a movement is made of, the time from one to the next, and how often a resting finger
# is reported: Windows gives up a touch that says nothing for a while.
STEPS, PACE, REST_EVERY = 24, 0.012, 0.05
TAP_SECONDS, TAP_GAP = 0.06, 0.12
HOLD_DEFAULT, HOLD_MAX = 1.2, 30.0
PEN, FINGER = "pen", "finger"

_NUMBERS = {"a": 1, "one": 1, "single": 1, "1": 1, "two": 2, "both": 2, "2": 2, "three": 3, "3": 3, "four": 4, "4": 4,
	"five": 5, "5": 5}
_FINGERS = re.compile(
	r"\b(a|one|single|two|both|three|four|five|[1-5])[- ]finger(s|ed)?\b"
	r"|\b(?:with|using|use) (?:my |your |the )?(a|one|two|both|three|four|five|[1-5]) fingers?\b")
# Words that say the screen is touched, and not the mouse used.
_TOUCH_WORDS = re.compile(
	r"\bfingers?\b|\b[1-5a-z]+-finger(ed)?\b|\btouch(es|ed|ing)?\b|\btouch ?screens?\b|\bmulti-?touch\b|\btouch gestures?\b"
	# A tap alone is a click with the mouse too; a double or triple tap is said of a touch screen.
	r"|\b(double|triple)[- ]tap(s|ped|ping)?\b")
_SPREAD = re.compile(
	r"\b(spread|stretch)(s|es|ed|ing)?\b|\bpinch(es|ed|ing)? (it |them )?(out|open|apart)\b|\bunpinch\w*\b|\breverse pinch\b")
_PINCH = re.compile(r"\bpinch(es|ed|ing)?\b|\bsqueez(e|es|ed|ing)\b")
_ROTATE = re.compile(r"\b(rotat(e|es|ed|ing)|twist(s|ed|ing)?)\b|\bturn(s|ed|ing)?\b.*\bfingers?\b|\bfingers?\b.*\bturn(s|ed|ing)?\b")
_SWIPE = re.compile(r"\b(swip(e|es|ed|ing)|flick(s|ed|ing)?|slid(e|es|ing)|scroll(s|ed|ing)?|pan(s|ned|ning)?|drag(s|ged|ging)?)\b")
_HOLD = re.compile(
	r"\b(touch|tap|press)(es)? and holds?\b|\blong[- ](press|tap|touch)\b|\bhold(s|ing)? (a|one|two|three|my|your|the)? ?fingers?\b"
	r"|\bkeep (a|one|two|my|your|the)? ?fingers? (on|down)\b")
_TAP = re.compile(r"\btap(s|ped|ping)?\b|\btouch(es)?\b")
_ZOOM = re.compile(r"\bzoom(s|ed|ing)? (in|out)\b|\b(enlarge|magnify|make\b.*\b(bigger|larger))\b|\b(shrink|make\b.*\bsmaller)\b")
_AMOUNTS = (
	(r"\b(all the way|fully|as far as (it|they) (goes?|go))\b", 0.45), (r"\b(tiny|slightly|a (tiny|wee) bit)\b", 0.06),
	(r"\b(a little|a bit|little|bit|small|short)\b", 0.12), (r"\b(a lot|far|much|large|big|long|wide)\b", 0.4),
)
_ANTICLOCKWISE = re.compile(r"\b(anti|counter)-?clockwise\b|\bto the left\b|\bleftwards?\b")
_DEGREES = re.compile(r"(\d{1,3})\s*(degrees?|°)")


def fingersOf(words):
	"""How many fingers the user's words name, or None when they name no number."""
	found = _FINGERS.search((words or "").lower())
	if not found:
		return None
	return max(1, min(MAX_FINGERS, _NUMBERS[found.group(1) or found.group(3)]))


def _fingersText(count):
	return "one finger" if count == 1 else f"{('two', 'three', 'four', 'five')[count - 2]} fingers"


def _share(text):
	percent = re.search(r"(\d{1,3})\s*(%|percent)(?! pressure)", text)
	if percent and not re.search(r"pressure\D{0,12}" + percent.group(1), text):
		return max(0.03, min(0.9, int(percent.group(1)) / 100))
	return next((share for pattern, share in _AMOUNTS if re.search(pattern, text)), SHARE_DEFAULT)


def touchOf(words):
	"""The touch gesture the user's words ask for, or None when they ask for none:
	{"kind", "fingers", "text": what it is in words, "size": share of the window's shorter side,
	"direction": for a swipe, "degrees": for a turn, clockwise positive, "taps", "seconds": for a hold,
	"pressure": share of full, "pace": seconds from one small step to the next}.
	A pinch, a spread and a turn are always meant for fingers; a swipe, a tap and a hold only where the words
	speak of fingers or of touching, since the mouse swipes and holds too."""
	text = (words or "").lower()
	named = fingersOf(text)
	touching = named is not None or bool(_TOUCH_WORDS.search(text))
	zoom = _ZOOM.search(text)
	gesture = {"size": _share(text), "pressure": (pressureOf(text) or (PRESSURE_DEFAULT,))[0], "pace": PACE}
	if re.search(r"\b(flick|fast|quick(ly)?)\b", text):
		gesture["pace"] = PACE / 3
	elif re.search(r"\bslow(ly)?\b", text):
		gesture["pace"] = PACE * 2.5
	if _SPREAD.search(text) or (touching and zoom and re.search(r"\bzoom(s|ed|ing)? in\b|enlarge|magnify|bigger|larger", text)):
		fingers = max(2, named or 2)
		return dict(gesture, kind=SPREAD, fingers=fingers, text=f"a spread with {_fingersText(fingers)}, as for zooming in")
	if _PINCH.search(text) or (touching and zoom):
		fingers = max(2, named or 2)
		return dict(gesture, kind=PINCH, fingers=fingers, text=f"a pinch with {_fingersText(fingers)}, as for zooming out")
	if _HOLD.search(text) and touching:
		fingers = named or 1
		seconds = pointer.secondsIn(text)
		seconds = max(0.3, min(HOLD_MAX, seconds)) if seconds else HOLD_DEFAULT
		return dict(gesture, kind=HOLD, fingers=fingers, seconds=seconds,
			text=f"a touch with {_fingersText(fingers)}, held for {pointer.secondsText(seconds)}")
	if _ROTATE.search(text) and (touching or re.search(r"\b(rotat|twist)", text)) and (touching or _DEGREES.search(text) or "clockwise" in text):
		fingers = max(2, named or 2)
		degrees = _DEGREES.search(text)
		amount = int(degrees.group(1)) if degrees else 180 if "half" in text else 45 if re.search(r"\b(a little|a bit|slightly)\b", text) else 90
		amount = max(5, min(360, amount))
		clockwise = not _ANTICLOCKWISE.search(text)
		return dict(gesture, kind=ROTATE, fingers=fingers, degrees=amount if clockwise else -amount,
			text=f"a turn of {amount} degrees {'clockwise' if clockwise else 'anticlockwise'} with {_fingersText(fingers)}")
	if not touching:
		return None
	direction = re.search(r"\b(left|right|up|down)(wards?)?\b", _FINGERS.sub(" ", text))
	if _SWIPE.search(text) and direction:
		fingers = named or 1
		way = direction.group(1)
		return dict(gesture, kind=SWIPE, fingers=fingers, direction=way,
			text=f"a swipe {way if way in ('up', 'down') else 'to the ' + way} with {_fingersText(fingers)}")
	if _TAP.search(text):
		fingers = named or 1
		taps = 3 if re.search(r"\btriple[- ]tap\b|\bthree times\b", text) else 2 if re.search(r"\bdouble[- ]tap\b|\btwice\b|\btwo times\b", text) else 1
		return dict(gesture, kind=TAP, fingers=fingers, taps=taps,
			text=f"{('a tap', 'a double tap', 'a triple tap')[taps - 1]} with {_fingersText(fingers)}")
	return None


def instead(gesture):
	"""What the mouse wheel does that stands in for a touch gesture, where a program takes no touch:
	("zoom", "in" or "out") for a spread or a pinch, ("scroll", direction) for a swipe with two fingers, which
	moves what is shown the way the fingers go. None where nothing stands in: a turn, a tap, more fingers."""
	kind = gesture["kind"]
	if kind == SPREAD:
		return ("zoom", "in")
	if kind == PINCH:
		return ("zoom", "out")
	if kind == SWIPE and gesture["fingers"] == 2:
		# Fingers that go up push what is shown up, which is scrolling down.
		return ("scroll", {"up": scrolling.DOWN, "down": scrolling.UP, "left": scrolling.RIGHT, "right": scrolling.LEFT}[gesture["direction"]])
	return None


def insteadText(stand):
	"""What stands in for a touch gesture, in words."""
	if stand is None:
		return ""
	if stand[0] == "zoom":
		return f"the Control key and the mouse wheel, which make most views {'larger' if stand[1] == 'in' else 'smaller'}"
	return f"the mouse wheel, turned {stand[1]}"


def _ring(count, radius, angle=0.0):
	"""Places for fingers around a middle, evenly spaced: two lie on a line, three make a triangle."""
	return [(radius * math.cos(angle + 2 * math.pi * i / count), radius * math.sin(angle + 2 * math.pi * i / count))
		for i in range(count)]


def _row(count, gap, direction):
	"""Places for fingers side by side, across the way they will move."""
	dx, dy = pointer.DIRECTIONS[direction]
	return [((i - (count - 1) / 2) * gap * abs(dy), (i - (count - 1) / 2) * gap * abs(dx)) for i in range(count)]


def strokes(gesture, place, box, scale=1.0):
	"""What the fingers do for a gesture at a place in a window: a list of strokes, between which every finger
	is lifted. A stroke is {"frames": [[(x, y) for each finger], ...], "pace": seconds between frames}. The
	fingers go down at the first frame and are lifted where the last one leaves them. Every place is kept
	inside the window."""
	left, top, right, bottom = box
	unit = gesture["size"] * min(right - left, bottom - top)
	count, kind = gesture["fingers"], gesture["kind"]
	near = scrolling.pixels(PINCH_NEAR, scale)
	gap = scrolling.pixels(FINGER_GAP, scale)

	def at(offsets):
		return [pointer.clamp(round(place[0] + x), round(place[1] + y), box) for x, y in offsets]

	if kind in (PINCH, SPREAD):
		far = max(unit, near * 2.5)
		radii = [far + (near - far) * i / STEPS for i in range(STEPS + 1)]
		if kind == SPREAD:
			radii.reverse()
		return [{"frames": [at(_ring(count, radius)) for radius in radii], "pace": gesture["pace"]}]
	if kind == ROTATE:
		radius = max(unit, near * 2.5)
		turn = math.radians(gesture["degrees"])
		steps = max(STEPS, round(abs(gesture["degrees"]) / 3))
		return [{"frames": [at(_ring(count, radius, turn * i / steps)) for i in range(steps + 1)], "pace": gesture["pace"]}]
	if kind == SWIPE:
		dx, dy = pointer.DIRECTIONS[gesture["direction"]]
		span = gesture["size"] * ((right - left) if dx else (bottom - top))
		row = _row(count, gap, gesture["direction"])
		# The swipe is drawn with the place in its middle, so that it stays on the thing it is meant for.
		return [{"frames": [at([(x + dx * span * (i / STEPS - 0.5), y + dy * span * (i / STEPS - 0.5)) for x, y in row])
			for i in range(STEPS + 1)], "pace": gesture["pace"]}]
	row = at(_row(count, gap, "up"))
	if kind == HOLD:
		return [{"frames": [row] * max(3, round(gesture["seconds"] / REST_EVERY)), "pace": REST_EVERY}]
	tap = {"frames": [row] * 3, "pace": TAP_SECONDS / 2}
	return [dict(tap) for _ in range(gesture.get("taps", 1))]


# --- Pressure ---

_LEVELS = (
	(r"\b(as hard as (it|you|i) can|full(y| pressure| force)?|maximum|max|all the way down|hardest)\b", 1.0),
	(r"\b(very|really|extra) (hard|firm(ly)?|heavy|heavily|strong(ly)?)\b", 0.92),
	(r"\b(very|really|extra) (light(ly)?|soft(ly)?|gentl[ey]|faint(ly)?)\b", 0.1),
	(r"\b(hard(er)?|firm(ly|er)?|heav(y|ily|ier)|strong(ly|er)?|thick(er)?|bold(er)?)\b", 0.8),
	(r"\b(light(ly|er)?|soft(ly|er)?|gentl[ey]|gentler|faint(ly|er)?|thin(ner)?)\b", 0.25),
	(r"\b(medium|normal|moderate|half)\b", 0.5),
)
_PRESSURE_PERCENT = re.compile(
	r"\b(\d{1,3})\s*(?:%|percent)(?: of)?(?: full)? (?:pressure|force)\b|\b(?:pressure|force)(?: of| at| to)? (\d{1,3})\s*(?:%|percent)?")
_FROM_TO = re.compile(r"\bfrom (.{1,24}?) to (.{1,24}?)(?: pressure| force|[.,;]|$)")
_RISING = re.compile(r"\b(get(s|ting)?|grow(s|ing)?|press(ing)?) (harder|firmer|heavier|stronger|thicker)\b|\b(increas|ris)(e|es|ing)\b|\bharder and harder\b")
_FALLING = re.compile(r"\b(get(s|ting)?|grow(s|ing)?|press(ing)?) (lighter|softer|fainter|thinner)\b|\b(decreas|fad|eas)(e|es|ing)\b|\blighter and lighter\b")
_PRESSURE_WORDS = re.compile(
	r"\bpressures?\b|\bforce\b|\b(pen|stylus|pencil|brush|eraser)\b|\bpress(es|ed|ing)? (down )?(\w+ )?(hard(er)?|firmly|lightly|softly|gently|harder)\b"
	r"|\b(hard|firm|light|soft|gentle) (press|touch|tap|stroke|line)\b|\bpress(es|ing)? (\w+ ){0,4}(hard|firmly|lightly|softly|gently)\b")


def _level(text):
	percent = re.search(r"(\d{1,3})\s*(%|percent)?", text)
	if percent and (percent.group(2) or text.strip() == percent.group(0).strip()):
		return max(0.01, min(1.0, int(percent.group(1)) / 100))
	return next((share for pattern, share in _LEVELS if re.search(pattern, text)), None)


def pressureOf(words):
	"""How hard the user's words ask to press, as (share of full at the start, share at the end), or None when
	they say nothing of it. "From light to hard" and "getting harder" give a rise."""
	text = (words or "").lower()
	span = _FROM_TO.search(text)
	if span:
		start, end = _level(span.group(1)), _level(span.group(2))
		if start is not None and end is not None:
			return (start, end)
	if _RISING.search(text):
		return (0.15, 1.0)
	if _FALLING.search(text):
		return (1.0, 0.15)
	percent = _PRESSURE_PERCENT.search(text)
	if percent:
		share = max(0.01, min(1.0, int(percent.group(1) or percent.group(2)) / 100))
		return (share, share)
	if not _PRESSURE_WORDS.search(text):
		return None
	share = next((share for pattern, share in _LEVELS if re.search(pattern, text)), PRESSURE_DEFAULT)
	return (share, share)


def pressureText(span):
	"""How hard, in words: "80 percent of full pressure", "pressure rising from 15 to 100 percent"."""
	start, end = round(span[0] * 100), round(span[1] * 100)
	if start == end:
		return f"{start} percent of full pressure"
	return f"pressure {'rising' if end > start else 'falling'} from {start} to {end} percent"


def penOf(words):
	"""What the user's words ask to do with pressure, or None when they say nothing of pressure, a pen or how
	hard: {"text", "tool": PEN or FINGER, "pressure": (start, end), "gesture": a line or shape as
	pointer.gestureOf gives it, or None for a press in one place, "seconds": how long a press lasts,
	"eraser": the other end of the pen}."""
	text = (words or "").lower()
	span = pressureOf(text)
	if span is None:
		return None
	eraser = bool(re.search(r"\b(eras(e|es|er|ing)|rub(s|bing)? out)\b", text))
	tool = FINGER if re.search(r"\bfingers?\b|\btouch(es|ing)?\b", text) and not re.search(r"\b(pen|stylus|pencil|brush)\b", text) else PEN
	# The words that say how hard would otherwise be read as a size or a direction of the line.
	bare = _PRESSURE_PERCENT.sub(" ", text)
	gesture = pointer.gestureOf(bare) if re.search(
		r"\b(draw|line|stroke|swipe|circle|tick|check ?mark|zig-?zag|square|triangle|cross|letter|sign|scribble|eras\w+|rub\w*)\b", bare) else None
	seconds = pointer.secondsIn(text)
	seconds = max(0.1, min(HOLD_MAX, seconds)) if seconds else 0.6
	with_ = "the eraser end of the pen" if eraser else "the pen" if tool == PEN else "a finger"
	what = gesture["text"] if gesture else f"a press for {pointer.secondsText(seconds)}"
	return {
		"text": f"{what} with {with_}, at {pressureText(span)}", "tool": tool, "pressure": span, "gesture": gesture,
		"seconds": seconds, "eraser": eraser}


def penStrokes(pen, place, box):
	"""The places the pen or finger passes through, with how hard it presses at each: a list of strokes, each a
	list of (x, y, share of full pressure). The pressure changes evenly from the start of the first stroke to
	the end of the last."""
	start, end = pen["pressure"]
	if pen["gesture"] is None:
		count = max(3, round(pen["seconds"] / REST_EVERY))
		return [[(place[0], place[1], start + (end - start) * i / (count - 1)) for i in range(count)]]
	paths = pointer.gesturePaths(pen["gesture"], place, box)
	total = max(1, sum(len(points) for points in paths) - 1)
	found, done = [], 0
	for points in paths:
		found.append([(x, y, start + (end - start) * (done + i) / total) for i, (x, y) in enumerate(points)])
		done += len(points)
	return found


def units(share):
	"""A share of full pressure in Windows' own numbers. A pen or finger that touches never reports nothing."""
	return max(1, min(FULL, round(share * FULL)))
