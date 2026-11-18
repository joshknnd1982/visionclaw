# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - games and programs that read the mouse directly. Such a program takes no notice of where
# Windows' own pointer is put: it listens to how far the mouse itself moves. Some turn the view with it and
# show no pointer at all; others draw a pointer of their own. Here is the plain reasoning for both: what a
# request to turn or look means as movements of the mouse; how a program's own pointer is brought to a place
# by pushing it into the window's corner first and counting from there; how its speed and place are measured
# from pictures; and what Windows' facts about the pointer say. Also what VisionClaw has found out about how
# one program is worked, kept as data between sessions.
# No NVDA dependencies. Nothing here moves the mouse: movements are handed to a function given from outside.

import json
import os
import re
import threading
import time

from . import pointer

# How the mouse is moved in a program: Windows' own pointer is put somewhere, as everywhere else; the program
# draws a pointer of its own that follows the mouse's movement; or the mouse turns the view and nothing points.
PLAIN, POINTER, VIEW = "windows", "own pointer", "view"
WAYS = [PLAIN, POINTER, VIEW]
# One movement handed to Windows is never larger than this: programs drop or clip a mouse that jumps.
CHUNK = 24
# Into the corner it may go in larger pieces: where it ends is known whatever is dropped on the way.
HOME_CHUNK = 60
# How far the mouse is moved for a turn when the words give no number, in the mouse's own steps.
LITTLE, SOME, LOT = 80, 300, 900
# A turn "around" or "behind" is taken to be this many steps, which is a guess that differs from game to game.
AROUND = 1200
MAX_STEPS = 20000
# The speed a program gives the mouse may be changed in words; kept between these.
SPEED_LEAST, SPEED_MOST = 0.1, 10.0
FASTER, SLOWER = 1.4, 0.7
# Measuring a program's own pointer: how far it is moved for each look, and what speeds are believed.
MEASURE_STEP = 40
MEASURED_LEAST, MEASURED_MOST = 0.2, 6.0

_DIRECTIONS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
_TURN = re.compile(
	r"\b(turn(s|ing)?|look(s|ing)?|aim(s|ing)?|face|facing|steer(s|ing)?|pan(s|ning)?|spin(s|ning)?|rotat(e|es|ing)"
	r"|tilt(s|ing)?)\b|\bmove (the |my )?(mouse|view|camera|crosshairs?|aim)\b|\b(mouse|camera|view)\b.*\bdirectly\b")
# What is also turned up, down or around, and has nothing to do with a view.
_OTHER_TURNS = re.compile(r"\b(volume|speed|rate|pitch|sound|music|voice|brightness|heating|lights?|page|pages)\b")
_AROUND = re.compile(r"\b(turn|spin|look) (right |all the way )?(around|round)\b|\bbehind (me|you)\b|\babout[- ]face\b")
_NUMBER = re.compile(r"(\d{1,5})\s*(steps?|counts?|units?|pixels?|px|mickeys?|degrees?|°)?")


def turnOf(words, speed=1.0):
	"""The movement of the mouse a request to turn, look or aim means, or None when the words name no
	direction: {"dx", "dy": the mouse's own steps, to the right and down, "text": what is done, in words,
	"guess": whether how far is VisionClaw's own guess}."""
	text = (words or "").lower()
	if not _TURN.search(text) or _OTHER_TURNS.search(text):
		return None
	around = _AROUND.search(text)
	found = re.search(r"\b(left|right|up|down)(wards?)?\b", text)
	if not found and not around:
		return None
	way = found.group(1) if found else "right"
	number = _NUMBER.search(text)
	guess = True
	if number and number.group(2) and number.group(2).startswith(("degree", "°")):
		# A game turns as far for a movement as its own settings say; a full turn is taken to be twice AROUND.
		steps = int(number.group(1)) / 360 * 2 * AROUND * speed
	elif number and number.group(2):
		steps, guess = int(number.group(1)), False
	elif around:
		steps = AROUND * speed
	elif re.search(r"\b(a lot|far|much|sharply|hard|all the way)\b", text):
		steps = LOT * speed
	elif re.search(r"\b(a little|a bit|slightly|little|bit|a touch|gently|tiny)\b", text):
		steps = LITTLE * speed
	else:
		steps = SOME * speed
	steps = max(1, min(MAX_STEPS, round(steps)))
	dx, dy = _DIRECTIONS[way]
	return {
		"dx": dx * steps, "dy": dy * steps, "guess": guess,
		"text": f"{steps} steps {way if way in ('up', 'down') else 'to the ' + way}"}


def chunks(dx, dy, chunk=CHUNK):
	"""A movement of the mouse as many small ones, which together make exactly the whole."""
	count = max(1, -(-max(abs(dx), abs(dy)) // chunk))
	moves, doneX, doneY = [], 0, 0
	for i in range(1, count + 1):
		x, y = round(dx * i / count), round(dy * i / count)
		if (x - doneX, y - doneY) != (0, 0):
			moves.append((x - doneX, y - doneY))
		doneX, doneY = x, y
	return moves


_OWN = re.compile(
	r"\b(its|it's|their|the game'?s?|the program'?s?) own (mouse )?(pointer|cursor)\b|\bown (mouse )?(pointer|cursor)\b"
	r"|\b(draws?|shows?|has) (its|a|an) (own )?(mouse )?(pointer|cursor)( of its own)?\b|\bsoftware (pointer|cursor)\b")
_VIEW = re.compile(
	r"\b(mouse|it)\b.{0,30}\b(turns?|moves?|rotates?|steers?|controls?) the (view|camera|character|player|aim|crosshairs?)\b"
	r"|\bmouse ?look\b|\bfirst[- ]person\b|\b(no|without a) (mouse )?(pointer|cursor)\b|\bcaptures? the mouse\b|\bmouse is captured\b")
_DIRECT = re.compile(
	r"\breads? the mouse (directly|itself)\b|\bdirect(ly)? (mouse|input|movement)\b|\braw (mouse|input)\b|\bdirect mouse\b"
	r"|\bmoves? the mouse directly\b|\brelative (mouse|movement)\b")
_OFF = re.compile(
	r"\b(stop|no more|turn off|switch off|disable|don'?t use|do not use|without)\b.{0,30}\b(direct|raw|relative)\b"
	r"|\b(normal|usual|ordinary|plain|windows'?s?|standard|regular) (mouse )?(pointer|cursor|mouse|way)\b|\bback to (the )?(normal|windows)\b"
	r"|\bforget\b.{0,40}\b(mouse|pointer|cursor)\b")
_TOO_FAST = re.compile(r"\btoo (fast|far|much|quick(ly)?|sensitive)\b|\b(slower|less far|less sensitive|slow (it )?down)\b|\bovershoot\w*\b")
_TOO_SLOW = re.compile(r"\btoo (slow(ly)?|short|little)\b|\bnot\b.{0,14}\bfar enough\b|\b(faster|further|farther|more sensitive|speed (it )?up)\b|\bundershoot\w*\b")
_MEASURE = re.compile(r"\b(measure|calibrate|re-?measure|recalibrate|find)\b.{0,40}\b(pointer|cursor|mouse|speed)\b")


def wayOf(words):
	"""What the user's words say about how the mouse is to be moved in the program in front:
	("way", PLAIN, POINTER or VIEW), ("speed", a factor), ("measure", None), or None when they only ask."""
	text = (words or "").lower()
	if _MEASURE.search(text):
		return ("measure", None)
	if _TOO_FAST.search(text):
		return ("speed", SLOWER)
	if _TOO_SLOW.search(text):
		return ("speed", FASTER)
	if _OFF.search(text):
		return ("way", PLAIN)
	if _VIEW.search(text):
		return ("way", VIEW)
	if _OWN.search(text) or _DIRECT.search(text):
		return ("way", POINTER)
	return None


def wayText(way):
	"""How the mouse is moved in a program, in a sentence for the user."""
	return {
		PLAIN: "Windows' own mouse pointer is put where it is wanted, as in other programs",
		POINTER: "the program draws a pointer of its own, which VisionClaw moves by moving the mouse itself: into the "
			"corner of the window first, then counted from there",
		VIEW: "the mouse turns the view and nothing points at anything, so VisionClaw moves the mouse itself by a "
			"number of steps",
	}[way]


def stateText(state):
	"""What Windows' facts about its own pointer say, as sentences, or "". state: {"showing": whether Windows'
	pointer is drawn, "confined": whether a program keeps it inside a part of the screen, "inside": whether
	that part lies inside the window in front}."""
	if not state:
		return ""
	if not state.get("showing") and state.get("confined") and state.get("inside"):
		return (
			"This program hides Windows' mouse pointer and keeps it inside its own window, as games do that read the "
			"mouse directly: putting the pointer on a thing does nothing there.")
	if not state.get("showing"):
		return (
			"Windows' mouse pointer is hidden here. A program that hides it often draws a pointer of its own or turns "
			"the view with the mouse, and then takes no notice of where Windows' pointer is put.")
	if state.get("confined") and state.get("inside"):
		return "This program keeps the mouse pointer inside its own window."
	return ""


def reads(state):
	"""Whether Windows' facts say that the program in front most likely reads the mouse directly."""
	return bool(state) and not state.get("showing")


ADVICE = (
	"Tell VisionClaw which it is: \"this game has its own pointer\", and clicks by name work again; or \"the mouse "
	"turns the view here\", and then \"turn left\", \"look up a little\" or \"turn around\" move the mouse itself. "
	"Pointer mode (NVDA+Alt+K) and controller mode (NVDA+Alt+J) move it the same way; M in pointer mode changes "
	"between the three ways. A game that refuses movements made by a program cannot be worked this way.")


class Tracker:
	"""Brings a program's own pointer to a place, when the program only follows how far the mouse moves.
	send(dx, dy) moves the mouse itself; grab(box) gives a picture of the window, or is None; box is the
	window (left, top, right, bottom). Where the pointer is believed to be is kept in x and y."""

	def __init__(self, send, box, speed=1.0, grab=None, pause=time.sleep, measure=False):
		self._send, self._grab, self._pause = send, grab, pause
		# Whether the pointer is measured by itself the first time it is brought somewhere.
		self._measureFirst = measure
		self.box = tuple(box)
		# How many pixels the program moves its pointer for one step of the mouse.
		self.speed = max(SPEED_LEAST, min(SPEED_MOST, float(speed or 1.0)))
		self.x, self.y = self.box[0], self.box[1]
		self.homed = self.measured = False

	def _move(self, dx, dy, chunk=CHUNK):
		for stepX, stepY in chunks(dx, dy, chunk):
			self._send(stepX, stepY)
			self._pause(0.001)

	def home(self):
		"""Push the pointer into the window's top left corner, further than the window is large, so that it is
		there whatever its speed, and count from there."""
		left, top, right, bottom = self.box
		far = round(max(right - left, bottom - top) / MEASURED_LEAST) + 200
		self._move(-far, -far, HOME_CHUNK)
		self._pause(0.05)
		self.x, self.y, self.homed = left, top, True

	def measure(self):
		"""Find out from pictures how fast the program moves its pointer and where it is: the pointer is moved
		three equal times, and where the picture changed tells where it was each time. Returns whether that
		gave a believable answer; if not, the speed stays as it was. Needs home() first."""
		if self._grab is None:
			return False
		step = MEASURE_STEP
		shots = []
		try:
			for _ in range(3):
				self._move(step, step)
				self._pause(0.09)
				shots.append(self._grab(self.box))
		except Exception:
			return False
		first, second = pointer.appeared(shots[0], shots[1]), pointer.appeared(shots[1], shots[2])
		# What the program believes after three moves, until the pictures say better.
		self.x, self.y = self.box[0] + round(3 * step * self.speed), self.box[1] + round(3 * step * self.speed)
		if first is None or second is None:
			return False
		width, height = self.box[2] - self.box[0], self.box[3] - self.box[1]
		for found in (first, second):
			if found[2] - found[0] > width / 3 or found[3] - found[1] > height / 3:
				return False  # more than a pointer changed
		across, down = (second[0] - first[0]) / step, (second[1] - first[1]) / step
		if not (MEASURED_LEAST <= across <= MEASURED_MOST and MEASURED_LEAST <= down <= MEASURED_MOST):
			return False
		if abs(across - down) > 0.3 * max(across, down):
			return False
		self.speed = (across + down) / 2
		# The change between the second and third picture begins where the pointer was at the second.
		self.x = self.box[0] + second[0] + round(step * self.speed)
		self.y = self.box[1] + second[1] + round(step * self.speed)
		self.measured = True
		return True

	def goTo(self, x, y):
		"""Bring the pointer to a place on the screen, from where it is believed to be."""
		if not self.homed:
			self.home()
			if self._measureFirst:
				self.measure()
		x, y = pointer.clamp(round(x), round(y), self.box)
		dx, dy = round((x - self.x) / self.speed), round((y - self.y) / self.speed)
		self._move(dx, dy)
		# What was really sent is counted, so that rounding does not add up.
		self.x += round(dx * self.speed)
		self.y += round(dy * self.speed)


class AppWays:
	"""What VisionClaw has found out about how one program is worked, kept as data between sessions:
	{program: {"mouse": POINTER or VIEW, "speed": number, "touch": what worked for a gesture, ...}}.
	Nothing here is code, and all of it is forgotten with forget()."""

	def __init__(self, path):
		self._path = path
		self._lock = threading.Lock()
		self._data = {}
		try:
			with open(path, encoding="utf-8") as f:
				data = json.load(f)
			if isinstance(data, dict):
				self._data = {str(app): dict(values) for app, values in data.items() if isinstance(values, dict)}
		except (OSError, ValueError):
			pass

	def _save(self):
		try:
			tmp = self._path + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				json.dump(self._data, f, indent=1)
			os.replace(tmp, self._path)
		except OSError:
			pass

	def get(self, app, key, default=None):
		return self._data.get(app or "", {}).get(key, default)

	def set(self, app, key, value):
		if not app:
			return
		with self._lock:
			if value is None:
				self._data.get(app, {}).pop(key, None)
				if not self._data.get(app):
					self._data.pop(app, None)
			else:
				self._data.setdefault(app, {})[key] = value
			self._save()

	def mouse(self, app):
		way = self.get(app, "mouse", PLAIN)
		return way if way in WAYS else PLAIN

	def speed(self, app):
		try:
			return max(SPEED_LEAST, min(SPEED_MOST, float(self.get(app, "speed", 1.0))))
		except (TypeError, ValueError):
			return 1.0

	def forget(self, app):
		with self._lock:
			found = self._data.pop(app or "", None) is not None
			if found:
				self._save()
		return found

	def lines(self):
		"""What is kept, as sentences."""
		found = []
		for app, values in sorted(self._data.items()):
			if values.get("mouse") in (POINTER, VIEW):
				found.append(f"In {app}, {wayText(values['mouse'])}.")
			for gesture, way in sorted((values.get("touch") or {}).items()):
				found.append(f"In {app}, {gesture} is done with {way}.")
		return found
