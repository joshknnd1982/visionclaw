# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools for fingers and pressure. "Pinch the map", "swipe left with three fingers", "turn the
# photo a quarter with two fingers", "press hard on the pad", "draw a line with the pressure rising": the
# user's own words say which gesture, plain code works out where every finger goes (claw/touch.py), Windows
# is asked to touch or press (touchinput.py), and the window is looked at before and after, so that the user
# is told what happened and not what was tried. Where a program takes no touch, the mouse wheel stands in for
# a pinch, a spread and a swipe with two fingers, and what worked is kept for the program.

import contextlib
import time

import addonHandler

from . import mousetools, touchinput
from .claw import pointer, scrolling, touch
from .claw.tools import ToolError
from .vclog import log

addonHandler.initTranslation()

# What worked for a gesture in a program, as it is kept and said.
FINGERS, WHEEL = "fingers on the screen", "the mouse wheel"
_SETTLE = 0.35


def nvdaTouchOn():
	"""Whether NVDA itself is handling a touch screen just now."""
	try:
		import touchHandler
		return getattr(touchHandler, "handler", None) is not None
	except Exception:
		return False


def register(add, plugin, text, confirm, mustAgree, shared):
	"""Add the tools for fingers and pressure. shared: what the mouse tools found out to be needed by both
	(where a request is meant, a picture of the window, whether it changed)."""

	def changed(before, after):
		"""Whether the window shows something else now; None when it could not be looked at."""
		if before is None or after is None:
			return None
		return pointer.appeared(before, after) is not None or scrolling.moved(before, after) >= scrolling.MOVED_SHARE

	def ask(question, pausesNvda):
		if pausesNvda:
			# Putting NVDA's own touch handling aside is always asked about, whatever the settings say.
			# Translators: Added to a question when NVDA's own touch screen gestures are paused for a moment.
			mustAgree(question + " " + _(
				"NVDA's own touch gestures are put aside for that moment and put back right after."))
		else:
			confirm(question)

	def wheelInstead(task, stand, box, point):
		"""Do with the mouse wheel what stands in for a touch gesture. Returns whether anything moved."""
		old = mousetools.position()
		try:
			if stand[0] == "zoom":
				direction = scrolling.UP if stand[1] == "in" else scrolling.DOWN
				moved, _done, _picture = mousetools.scrollView(plugin._grab, box, point, direction, 2, False, task.cancel, ("control",))
			else:
				moved, _done, _picture = mousetools.scrollView(
					plugin._grab, box, point, stand[1], scrolling.PAGE_NOTCHES, False, task.cancel)
		finally:
			mousetools.moveTo(*old)
		return moved

	def touchGesture(task, asked):
		words = asked or task.request
		gesture = touch.touchOf(words)
		if gesture is None:
			raise ToolError(
				"The request does not say which touch gesture to do. It can be a pinch or a spread, a swipe in a "
				"direction, a turn clockwise or anticlockwise, a tap, or a touch that is held, each with a number of "
				"fingers from one to five.")
		point, name, box = shared.placeFor(task, words)
		scale = mousetools._onMain(lambda: mousetools.scaleAt(*point))
		app = mousetools._onMain(mousetools.appNow)
		stand = touch.instead(gesture)
		kept = dict(plugin.appWays.get(app, "touch") or {})
		# Translators: Asked before VisionClaw touches the screen as fingers would. {gesture} is what, {name} where.
		ask(_("Touch the screen for you: {gesture}, on {name}?").format(gesture=gesture["text"], name=name), nvdaTouchOn())
		before = shared.look(box)
		refused = ""
		if kept.get(gesture["kind"]) == WHEEL and stand is not None:
			# Touch did nothing in this program before and the wheel did: the wheel at once.
			if wheelInstead(task, stand, box, point):
				task.items = None
				return (
					f"Used {touch.insteadText(stand)}, in place of {gesture['text']}, on {name}: this program took no "
					"touch before, and the wheel worked there. What the window shows changed.")
			kept.pop(gesture["kind"], None)
			before = shared.look(box)
		try:
			with touchinput.nvdaTouchPaused(mousetools._onMain):
				touchinput.fingers(touch.strokes(gesture, point, box, scale), gesture["pressure"], task.cancel)
		except touchinput.Refused as e:
			refused = str(e)
			log.debugWarning(f"VisionClaw: the touch was refused: {refused}")
		task.check()
		time.sleep(_SETTLE)
		after = shared.look(box) if before is not None else None
		task.items = None  # the window has probably changed
		did = f"Touched the screen as fingers would: {gesture['text']}, on {name}."
		if not refused:
			result = changed(before, after)
			if result is None:
				return did + " The window could not be looked at, so whether anything changed is not known."
			if result:
				kept[gesture["kind"]] = FINGERS
				plugin.appWays.set(app, "touch", kept)
				return did + " What the window shows changed."
		if stand is not None:
			# The least that works: the wheel does the same for most programs that take no touch.
			if wheelInstead(task, stand, box, point):
				kept[gesture["kind"]] = WHEEL
				plugin.appWays.set(app, "touch", kept)
				why = f"Windows did not take the touch. {refused}" if refused else (
					f"{did} Nothing VisionClaw can see changed, so the program seems to take no touch.")
				return (
					f"{why} VisionClaw then used {touch.insteadText(stand)}, and what the window shows changed. That is "
					"kept for this program, and used at once the next time.")
		if refused:
			raise ToolError(f"The screen could not be touched for you. {refused}")
		return (
			did + " Nothing VisionClaw can see changed in the window. The program may take no touch, or the gesture "
			"was not on the thing that takes it."
			+ (f" {touch.insteadText(stand).capitalize()} changed nothing either." if stand is not None else ""))

	add("touch_gesture",
		"touch the screen as fingers would, on an item the user names, at the mouse pointer or in the middle of the "
		"window: pinch or spread with two fingers, swipe with one to five fingers, turn with two fingers, tap, double "
		"tap, or touch and hold; where a program takes no touch the mouse wheel is used instead; says whether "
		"anything changed",
		touchGesture, {
			"asked": text("what the user asked for, in their own words, with the gesture and the number of fingers",
				maxLength=300, auto=True),
		}, changes=True, title="Touching the screen")

	def penStroke(task, asked):
		words = asked or task.request
		pen = touch.penOf(words)
		if pen is None:
			raise ToolError(
				"The request does not say how hard to press. Say it in a word, such as lightly, firmly or as hard as "
				"it goes, or as a number of percent of full pressure, or as rising or falling; with a line or a shape "
				"to draw, or with a time to keep pressing.")
		point, name, box = shared.placeFor(task, words)
		finger = pen["tool"] == touch.FINGER
		note = ""
		if not finger and not touchinput.penSupported():
			finger = True
			note = " This version of Windows gives a program no pen, so one finger pressed instead, which also says how hard."
		# Translators: Asked before VisionClaw presses on the screen as a pen or a finger would, with pressure. {what} is what.
		ask(_("Press on {name} for you: {what}?").format(name=name, what=pen["text"]), finger and nvdaTouchOn())
		before = shared.look(box)
		pace = pen["gesture"]["pace"] if pen["gesture"] else touch.REST_EVERY
		try:
			with touchinput.nvdaTouchPaused(mousetools._onMain) if finger else contextlib.nullcontext():
				touchinput.strokesWithPen(touch.penStrokes(pen, point, box), pen["eraser"], pace, task.cancel, finger)
		except touchinput.Refused as e:
			raise ToolError(f"The screen could not be pressed for you. {e}")
		task.check()
		time.sleep(_SETTLE)
		after = shared.look(box) if before is not None else None
		task.items = None
		result = changed(before, after)
		said = f"Pressed as a {'finger' if finger else 'pen'} would: {pen['text']}, on {name}.{note}"
		if result is None:
			return said + " The window could not be looked at, so whether anything changed is not known."
		if result:
			return said + " What the window shows changed. Whether the program felt how hard it was pressed, VisionClaw cannot see."
		return (
			said + " Nothing VisionClaw can see changed in the window. A program that reads a drawing tablet through "
			"the tablet's own driver, and not through Windows, takes no notice of this.")

	add("pen_stroke",
		"press on the screen as a pen or a finger would, with a pressure the user names: lightly, firmly, a number "
		"of percent, rising or falling; in one place for a time, or along a line or a shape; for drawing programs "
		"and controls that feel how hard they are pressed",
		penStroke, {
			"asked": text("what the user asked for, in their own words, with how hard to press", maxLength=300, auto=True),
		}, changes=True, title="Pressing with pressure")
