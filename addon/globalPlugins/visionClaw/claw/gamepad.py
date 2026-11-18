# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a game controller as a way to work the computer. A stick moves the mouse pointer, slowly when
# pushed a little and fast when pushed far; buttons click; a trigger is the mouse button for as long as it is
# pulled, and the other one presses as hard as it is pulled; the second stick turns the wheel or moves the
# mouse itself, for games. Here is the plain reasoning: what Windows reports of a controller as one plain
# state, what changed from one look to the next, which button does what, how far a stick moves the pointer,
# and which button a request in words names.
# No NVDA dependencies, and nothing here reads a controller or moves anything.

import collections
import math
import re

from . import pointer

A, B, X, Y = "a", "b", "x", "y"
LB, RB, LT, RT = "lb", "rb", "lt", "rt"
BACK, START, LS, RS = "back", "start", "ls", "rs"
UP, DOWN, LEFT, RIGHT = "up", "down", "left", "right"
BUTTONS = [A, B, X, Y, LB, RB, LT, RT, BACK, START, LS, RS, UP, DOWN, LEFT, RIGHT]
# How a button is written where it is kept as a hotkey, beside NVDA's "kb:" for keys.
PREFIX = "pad:"
# The bits of the buttons as Windows' XInput reports them (XINPUT_GAMEPAD, read from Microsoft's page on
# 2026-11-18).
XINPUT_BITS = {
	0x0001: UP, 0x0002: DOWN, 0x0004: LEFT, 0x0008: RIGHT, 0x0010: START, 0x0020: BACK, 0x0040: LS, 0x0080: RS,
	0x0100: LB, 0x0200: RB, 0x1000: A, 0x2000: B, 0x4000: X, 0x8000: Y,
}
# Where the buttons lie on most controllers that Windows reads through its older joystick interface, counted
# from 1: the left, lower, right and upper of the four, the shoulders, the triggers, the two in the middle,
# the sticks pressed in. Not every make follows this.
JOYSTICK_BUTTONS = {1: X, 2: A, 3: B, 4: Y, 5: LB, 6: RB, 7: LT, 8: RT, 9: BACK, 10: START, 11: LS, 12: RS}
XBOX, OTHER = "xinput", "joystick"

# Sticks from -1 to 1, to the right and down; triggers from 0 to 1.
State = collections.namedtuple("State", "buttons lx ly rx ry lt rt")
NOTHING = State(frozenset(), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

# A stick that is let go does not come back to exactly the middle: inside this share of its way it is at rest.
DEAD = 0.24
# A trigger counts as pulled above the first and as let go below the second, so that it does not flutter.
TRIGGER_ON, TRIGGER_OFF = 0.4, 0.25
# How fast a stick pushed all the way moves the pointer, on a plain screen at 100 percent, in pixels a second;
# with the left shoulder button slow, with the right one fast.
SPEED, SLOW, FAST = 700.0, 0.25, 2.5
# How fast the other stick turns the wheel, in notches a second, and moves the mouse itself, in steps a second.
WHEEL_RATE, LOOK_RATE = 10.0, 900.0
# Both middle buttons held this long turn controller mode on or off.
CHORD_SECONDS = 1.0
# How often a connected controller is looked at, and how often Windows is asked whether one has come.
LOOK_EVERY, SEARCH_EVERY = 1 / 60, 2.5
# Short buzzes: at the window's edge, and when what is under the pointer becomes something else.
# (left motor, right motor, seconds)
BUZZ_EDGE, BUZZ_OTHER = (0.55, 0.0, 0.07), (0.0, 0.4, 0.04)


def _axis(value, low=-32768, high=32767):
	middle = (low + high) / 2
	return max(-1.0, min(1.0, (value - middle) / ((high - low) / 2)))


def fromXInput(buttons, leftTrigger, rightTrigger, lx, ly, rx, ry):
	"""One state from what XInput reports. Its sticks count upwards as positive; here down is."""
	names = frozenset(name for bit, name in XINPUT_BITS.items() if buttons & bit)
	return State(names, _axis(lx), -_axis(ly), _axis(rx), -_axis(ry), leftTrigger / 255, rightTrigger / 255)


def fromJoystick(buttons, axes, pov=None):
	"""One state from what Windows' older joystick interface reports of a controller that is not read through
	XInput. buttons: the pressed ones as bits, the first button the lowest. axes: {"x", "y", "z", "r"} each
	from -1 to 1, the first two the left stick and the others the right one. pov: where the direction pad
	points, in hundredths of a degree, or None."""
	names = {name for number, name in JOYSTICK_BUTTONS.items() if buttons & (1 << (number - 1))}
	if pov is not None and 0 <= pov < 36000:
		angle = pov / 100
		if angle >= 292.5 or angle <= 67.5:
			names.add(UP)
		if 22.5 <= angle <= 157.5:
			names.add(RIGHT)
		if 112.5 <= angle <= 247.5:
			names.add(DOWN)
		if 202.5 <= angle <= 337.5:
			names.add(LEFT)
	return State(
		frozenset(names), axes.get("x", 0.0), axes.get("y", 0.0), axes.get("z", 0.0), axes.get("r", 0.0),
		1.0 if LT in names else 0.0, 1.0 if RT in names else 0.0)


def stick(x, y, dead=DEAD):
	"""How far a stick is pushed, as (across, down) from -1 to 1: nothing inside its resting place, then
	gently at first and strongly near the rim, so that a small push makes a small, exact movement."""
	size = math.hypot(x, y)
	if size <= dead:
		return 0.0, 0.0
	push = min(1.0, (size - dead) / (1 - dead)) ** 2
	return x / size * push, y / size * push


class Follower:
	"""Follows a controller from one look to the next and says what happened: buttons that went down or came
	up, with a pulled trigger counted as a button, and both middle buttons held long enough."""

	def __init__(self):
		self.held = frozenset()
		self._both = None
		self._armed = True

	def update(self, state, now):
		"""The events since the last look: ("down", button), ("up", button), ("chord",)."""
		held = set(state.buttons) - {LT, RT}
		for name, value in ((LT, state.lt), (RT, state.rt)):
			if value >= TRIGGER_ON or (name in self.held and value > TRIGGER_OFF):
				held.add(name)
		held = frozenset(held)
		events = [("down", name) for name in BUTTONS if name in held and name not in self.held]
		events += [("up", name) for name in BUTTONS if name in self.held and name not in held]
		self.held = held
		if BACK in held and START in held:
			if self._both is None:
				self._both = now
			elif self._armed and now - self._both >= CHORD_SECONDS:
				self._armed = False
				events.append(("chord",))
		else:
			self._both = None
			if BACK not in held and START not in held:
				self._armed = True
		return events

	def disarm(self):
		"""After the mode was turned on or off, the middle buttons do nothing more until both were let go."""
		self._armed = False


# What each button does in controller mode: alone, with the left shoulder button held, with the right one.
# The words are those of pointer mode (claw/pointer.py) where the two do the same.
ALONE = {
	A: ("click",), B: ("right",), X: ("double",), Y: ("what",), LS: ("where",), RS: ("stick",),
	START: ("help",), BACK: ("exit",),
	UP: ("move", "up", pointer.STEP), DOWN: ("move", "down", pointer.STEP),
	LEFT: ("move", "left", pointer.STEP), RIGHT: ("move", "right", pointer.STEP),
}
WITH_LEFT = {
	A: ("when", True), B: ("rest",), X: ("take",), Y: ("read",),
	UP: ("move", "up", pointer.FINE), DOWN: ("move", "down", pointer.FINE),
	LEFT: ("move", "left", pointer.FINE), RIGHT: ("move", "right", pointer.FINE),
}
WITH_RIGHT = {
	A: ("grab",), B: ("middle",), X: ("way",), Y: ("look",),
	RIGHT: ("item", 1), LEFT: ("item", -1), UP: ("items",), DOWN: ("bars",),
}


def commandFor(button, held):
	"""What a button that went down does, given which others are held, or None."""
	if button in (LB, RB, LT, RT):
		return None
	if RB in held and button in WITH_RIGHT:
		return WITH_RIGHT[button]
	if LB in held and button in WITH_LEFT:
		return WITH_LEFT[button]
	if RB in held or LB in held:
		return None
	return ALONE.get(button)


def pace(held):
	"""How fast the stick moves the pointer, given which shoulder button is held."""
	return SLOW if LB in held else FAST if RB in held else 1.0


def glide(sx, sy, seconds, scale=1.0, factor=1.0, rate=SPEED):
	"""How far a pushed stick moves in a length of time, in pixels, as (across, down), not yet rounded."""
	return sx * rate * scale * factor * seconds, sy * rate * scale * factor * seconds


class Carry:
	"""Adds up small movements and gives them out in whole numbers, so that a slow push is not lost."""

	def __init__(self):
		self.x = self.y = 0.0

	def add(self, dx, dy):
		self.x, self.y = self.x + dx, self.y + dy
		# A hair is added before cutting off, so that ten tenths make a whole one.
		wholeX, wholeY = int(self.x + math.copysign(1e-9, self.x)), int(self.y + math.copysign(1e-9, self.y))
		self.x, self.y = self.x - wholeX, self.y - wholeY
		return wholeX, wholeY

	def clear(self):
		self.x = self.y = 0.0


# --- A button named in words ---

_ABOUT = re.compile(
	r"\b(controllers?|game ?pads?|joy ?pads?|joysticks?|xbox|playstation|dualshock|dualsense|d-?pad|bumpers?"
	r"|thumb ?sticks?)\b|\b(left|right) (trigger|shoulder|stick)\b")
_SIDE = {"left": 0, "l": 0, "right": 1, "r": 1}
_NAMED = (
	(re.compile(r"\b(left|right) (bumper|shoulder)( button)?\b"), lambda m: (LB, RB)[_SIDE[m.group(1)]]),
	(re.compile(r"\b(l|r)(b|1)\b"), lambda m: (LB, RB)[_SIDE[m.group(1)]]),
	(re.compile(r"\b(left|right) trigger\b"), lambda m: (LT, RT)[_SIDE[m.group(1)]]),
	(re.compile(r"\b(l|r)(t|2)\b"), lambda m: (LT, RT)[_SIDE[m.group(1)]]),
	(re.compile(r"\b(left|right) (thumb ?)?stick (button|click|pressed( in)?)\b|\b(?:click(?:ing)?|press(?:ing)?)(?: in)? the (left|right) (?:thumb ?)?stick\b"),
		lambda m: (LS, RS)[_SIDE[m.group(1) or m.group(5)]]),
	(re.compile(r"\b(l|r)3\b"), lambda m: (LS, RS)[_SIDE[m.group(1)]]),
	(re.compile(r"\bd-?pad (up|down|left|right)\b|\b(up|down|left|right) on the d-?pad\b"), lambda m: m.group(1) or m.group(2)),
	(re.compile(r"\b(start|menu|options) button\b"), lambda m: START),
	(re.compile(r"\b(back|view|select|share) button\b"), lambda m: BACK),
	(re.compile(r"\b([abxy]) button\b|\bbutton ([abxy])\b"), lambda m: m.group(1) or m.group(2)),
	(re.compile(r"\b(cross|circle|square|triangle)( button)?\b"),
		lambda m: {"cross": A, "circle": B, "square": X, "triangle": Y}[m.group(1)]),
)


def about(words):
	"""Whether the user's words speak of a game controller."""
	return bool(_ABOUT.search((words or "").lower()))


def buttonOf(words):
	"""The controller button the user's words name, or None: only where they speak of a controller at all,
	since "the back button" is a browser's too."""
	text = (words or "").lower()
	if not _ABOUT.search(text):
		return None
	for pattern, name in _NAMED:
		found = pattern.search(text)
		if found:
			return name(found)
	return None


_TEXTS = {
	A: "the A button", B: "the B button", X: "the X button", Y: "the Y button", LB: "the left shoulder button",
	RB: "the right shoulder button", LT: "the left trigger", RT: "the right trigger", BACK: "the View button",
	START: "the Menu button", LS: "the left stick pressed in", RS: "the right stick pressed in",
	UP: "up on the direction pad", DOWN: "down on the direction pad", LEFT: "left on the direction pad",
	RIGHT: "right on the direction pad",
}


def buttonText(name):
	"""A button in words, as on an Xbox controller."""
	return _TEXTS.get(name, name)


def identifier(name):
	"""A button as it is kept for a hotkey."""
	return PREFIX + name


def kindText(kind, name=""):
	if kind == XBOX:
		return "an Xbox controller, or one that Windows reads the same way"
	return (
		"a game controller of another make" + (f" ({name})" if name else "") + ", read through Windows' older joystick "
		"interface; its buttons are taken to lie as on most such controllers, which may not fit this one")


HELP = (
	"Controller mode is on. The left stick moves the mouse pointer in this window, slowly for a small push and fast "
	"for a full one; the left shoulder button makes it slow and exact, the right shoulder button fast. The "
	"direction pad moves it one step. "
	"A clicks, B right-clicks, X double-clicks, Y says what is under the pointer. "
	"The right trigger is the mouse button for as long as you pull it, for dragging and holding. The left trigger "
	"presses like a pen, as hard as you pull it. "
	"The right stick turns the mouse wheel; pressed in, it moves the mouse itself instead, for games that read the "
	"mouse directly. Pressing the left stick in says where the pointer is. "
	"With the left shoulder button held: A clicks when what is here changes, B rests the pointer and says what "
	"appears, X takes a dial or slider for the direction pad, Y reads the text here. "
	"With the right shoulder button held: right and left on the direction pad jump between the things found in the "
	"window, up looks again, down finds scrollbars, A holds the mouse button until pressed again, B clicks with "
	"the middle button, X changes how the mouse is moved, Y describes what is here. "
	"The Menu button repeats this. The View button turns controller mode off; View and Menu held together for a "
	"second turn it on.")
CONNECTED = (
	"A game controller is connected: {kind}. To work the mouse pointer with it, hold its View and Menu buttons "
	"together for a second, or press NVDA+Alt+J.")
