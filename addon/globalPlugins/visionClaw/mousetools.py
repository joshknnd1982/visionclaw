# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the mouse, from the keyboard. Sighted people click, right-click, double-click and drag on
# controls that give a screen reader nothing to hold on to. Here are those actions as functions; the tools
# that let the models use them on an item found in a window's picture; and pointer mode, in which the arrow
# keys move the pointer inside the window, so that any control at all can be worked without a mouse.
# The mouse is moved through Windows itself, so nothing here depends on a part of NVDA that may change.
# A game that reads the mouse directly takes no notice of where Windows' pointer is put. For such a program
# the mouse itself is moved, by a number of its own steps (claw/direct.py): to turn the view, or to bring the
# program's own pointer to a place by counting from the corner of its window.

import contextlib
import ctypes
import threading
import time
from ctypes import wintypes

import addonHandler
import api
import tones
import ui
import wx
from .vclog import log

from . import ocr
from .claw import direct, dragcontrol, pointer, scrolling
from .claw.tools import VERBATIM, ToolError
from .engine import EngineError, prepareImage

addonHandler.initTranslation()

_LEFTDOWN, _LEFTUP, _RIGHTDOWN, _RIGHTUP = 0x0002, 0x0004, 0x0008, 0x0010
_MIDDLEDOWN, _MIDDLEUP = 0x0020, 0x0040
# Moving the mouse itself by a number of its own steps, as a hand moves it; and the pause between the pieces.
_MOVE, _NUDGE_STEP = 0x0001, 0.002
# Windows' numbers for the keys that can be held down during a click or a turn of the wheel.
_KEY_CODES = {"control": 0x11, "shift": 0x10, "alt": 0x12}
_WHEEL, _HWHEEL = 0x0800, 0x1000
# Pauses that give a program time to notice each part of a mouse action.
_SETTLE, _DRAG_STEP, _HOLD = 0.04, 0.012, 0.08
# Between the notches of the wheel, and before looking at what a scroll did.
_WHEEL_STEP, _SCROLL_SETTLE = 0.012, 0.35
# How long a click or a turn of the wheel in pointer mode waits for the user to let go of Shift, Control and Alt.
_KEYS_UP = 1.5
# The size of the area around the pointer that is read or described, on a plain screen at 100 percent.
_READ_AREA, _LOOK_AREA = (320, 70), (420, 260)
# The tools that point at a place: while one of them works, the mouse is moved the way the program in front
# is known to need (directScope).
DIRECT_TOOLS = frozenset(("click_item", "drag_item", "draw_gesture", "timed_click", "fill_field"))
# Kinds of control whose value the wheel changes when the pointer is over them. Never scrolled by accident.
_WHEEL_CHANGES = ("SLIDER", "COMBOBOX", "SPINBUTTON", "TAB", "TABCONTROL", "DROPDOWNBUTTON")


class _Direct:
	"""How the mouse is moved just now: Windows' pointer is put somewhere, as almost everywhere; or, while a
	tool or pointer mode works in a program that reads the mouse directly, the program's own pointer is
	brought there by a tracker; or nothing can be pointed at, because the mouse turns the view."""

	def __init__(self):
		self.way, self.tracker = direct.PLAIN, None


_direct = _Direct()
_VIEW_REFUSAL = (
	"In this program the mouse turns the view, so nothing can be pointed at or clicked by its place. Ask to turn "
	"left or right or to look up or down; or use pointer mode (NVDA+Alt+K) or controller mode (NVDA+Alt+J), where "
	"Enter or the A button clicks where the game aims. If the program does show a pointer of its own, say: this "
	"game has its own pointer.")


def _cursorPosition():
	point = wintypes.POINT()
	ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
	return point.x, point.y


def _setCursor(x, y):
	ctypes.windll.user32.SetCursorPos(int(x), int(y))


def _relative(dx, dy):
	"""Move the mouse itself by a number of its own steps, to the right and down. A program that reads the
	mouse directly sees this as it sees a hand moving the mouse."""
	ctypes.windll.user32.mouse_event(_MOVE, int(dx), int(dy), 0, 0)


def position():
	if _direct.way == direct.POINTER and _direct.tracker is not None:
		return _direct.tracker.x, _direct.tracker.y
	return _cursorPosition()


def moveTo(x, y):
	if _direct.way == direct.POINTER and _direct.tracker is not None:
		_direct.tracker.goTo(x, y)
		return
	if _direct.way == direct.VIEW:
		raise ToolError(_VIEW_REFUSAL)
	_setCursor(x, y)


def nudge(dx, dy, cancel=None):
	"""Move the mouse itself by a number of steps, in small pieces as a hand does. Returns False when stopped."""
	for stepX, stepY in direct.chunks(dx, dy):
		if cancel is not None and cancel.is_set():
			return False
		_relative(stepX, stepY)
		time.sleep(_NUDGE_STEP)
	return True


class _CURSORINFO(ctypes.Structure):
	_fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hCursor", wintypes.HANDLE), ("ptScreenPos", wintypes.POINT)]


def pointerState(box=None):
	"""What Windows says about its own mouse pointer: whether it is drawn, whether a program keeps it inside
	a part of the screen, and whether that part lies inside the window (left, top, right, bottom). A game
	that reads the mouse directly hides it and keeps it in. After a touch Windows itself puts the pointer
	away for a while; that is not counted as hidden."""
	state = {"showing": True, "confined": False, "inside": False}
	try:
		user32 = ctypes.windll.user32
		info = _CURSORINFO()
		info.cbSize = ctypes.sizeof(_CURSORINFO)
		if user32.GetCursorInfo(ctypes.byref(info)):
			state["showing"] = info.flags != 0
		clip = wintypes.RECT()
		if user32.GetClipCursor(ctypes.byref(clip)):
			width, height = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
			state["confined"] = clip.right - clip.left < width - 2 or clip.bottom - clip.top < height - 2
			if state["confined"] and box is not None:
				state["inside"] = (
					clip.left >= box[0] - 2 and clip.top >= box[1] - 2 and clip.right <= box[2] + 2 and clip.bottom <= box[3] + 2)
	except Exception:
		log.debugWarning("VisionClaw: Windows' facts about the mouse pointer could not be read", exc_info=True)
	return state


def appNow():
	"""The name of the program in front, or "". Main thread."""
	try:
		return api.getForegroundObject().appModule.appName or ""
	except Exception:
		return ""


@contextlib.contextmanager
def directScope(plugin):
	"""While a tool works the mouse: move it the way the program in front is known to need. Where the user
	said that the program draws a pointer of its own, and Windows' pointer is hidden there, the program's
	pointer is brought to each place by counting from the window's corner; where the mouse turns the view,
	pointing at a place is refused with a sentence that says what to ask for instead. Everywhere else, and
	whenever Windows' own pointer shows, nothing is different."""
	way, app, box = direct.PLAIN, "", None
	try:
		app, box = _onMain(lambda: (appNow(), plugin.pointerMode._box()))
		way = plugin.appWays.mouse(app)
		if way != direct.PLAIN and pointerState(box)["showing"]:
			way = direct.PLAIN
	except Exception:
		way = direct.PLAIN
	if way == direct.PLAIN:
		yield
		return
	old = (_direct.way, _direct.tracker)
	tracker = None
	if way == direct.POINTER:
		tracker = direct.Tracker(
			_relative, box, plugin.appWays.speed(app), plugin._grab, measure=plugin.appWays.get(app, "speed") is None)
	_direct.way, _direct.tracker = way, tracker
	try:
		yield
	finally:
		_direct.way, _direct.tracker = old
		if tracker is not None and tracker.measured:
			plugin.appWays.set(app, "speed", round(tracker.speed, 3))


def _button(flag):
	ctypes.windll.user32.mouse_event(flag, 0, 0, 0, 0)


def press():
	_button(_LEFTDOWN)


def release():
	_button(_LEFTUP)


def _wheel(flag, amount):
	ctypes.windll.user32.mouse_event(flag, 0, 0, amount, 0)


def _key(code, up):
	"""Press or let go of one key of the keyboard, through Windows itself."""
	ctypes.windll.user32.keybd_event(code, 0, 2 if up else 0, 0)


def _keyDown(code):
	"""Whether a key of the keyboard is down right now, as Windows says. Only read."""
	return bool(ctypes.windll.user32.GetAsyncKeyState(code) & 0x8000)


def keysUp(wait=None):
	"""Wait until the user has let go of Shift, Control and Alt, and say whether they are up. A key of pointer
	mode that is pressed with Shift leaves Shift down for a moment, and held down these keys change what the
	mouse does in most programs: Shift makes the wheel scroll sideways and a click select everything in
	between, Control makes the wheel zoom."""
	until = time.monotonic() + (_KEYS_UP if wait is None else wait)
	while True:
		try:
			if not any(_keyDown(code) for code in _KEY_CODES.values()):
				return True
		except Exception:
			return True  # Windows did not say: go on, as before this check existed
		if time.monotonic() >= until:
			return False
		time.sleep(0.01)


@contextlib.contextmanager
def keysDown(names):
	"""Keep Control, Shift or Alt down while something is done with the mouse, as for a click that adds to a
	selection or a wheel that zooms. The keys always come up again. NVDA is told to take no notice of them."""
	codes = [_KEY_CODES[name] for name in names or () if name in _KEY_CODES]
	if not codes:
		yield
		return
	try:
		from keyboardHandler import ignoreInjection
		quiet = ignoreInjection()
		if not hasattr(quiet, "__enter__"):
			raise TypeError("not a context manager")
	except Exception:
		# An NVDA without it: the keys are pressed all the same, and NVDA at most stops speaking for them.
		quiet = contextlib.nullcontext()
	with quiet:
		done = []
		try:
			for code in codes:
				_key(code, False)
				done.append(code)
			time.sleep(_SETTLE)
			yield
		finally:
			for code in reversed(done):
				_key(code, True)  # a key must never stay down
			time.sleep(_SETTLE)


def _dpi(x, y):
	"""The dots per inch of the monitor a point is on; 96 is a scaling of 100 percent. NVDA works in real
	pixels on every monitor, so this is only needed for sizes that should look the same to the eye."""
	try:
		user32, shcore = ctypes.windll.user32, ctypes.windll.shcore
		user32.MonitorFromPoint.restype = ctypes.c_void_p
		user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
		shcore.GetDpiForMonitor.argtypes = [
			ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
		monitor = user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)  # the nearest monitor
		across, down = ctypes.c_uint(), ctypes.c_uint()
		if shcore.GetDpiForMonitor(monitor, 0, ctypes.byref(across), ctypes.byref(down)) == 0 and across.value:
			return across.value
	except Exception:
		log.debugWarning("VisionClaw: the screen's scaling could not be read", exc_info=True)
	return scrolling.BASE_DPI


def scaleAt(x, y):
	"""How much larger than plain things are drawn on the monitor a point is on: 1.0, 1.25, 2.0 and so on."""
	return scrolling.scaleOf(_dpi(x, y))


def wheel(x, y, direction, notches, keys=()):
	"""Turn the mouse wheel with the pointer at a point of the screen, one notch at a time as a hand does:
	some programs take no notice of one large turn. Leaves the pointer there.
	keys: keys held down meanwhile; with Control the wheel makes most views larger or smaller."""
	moveTo(x, y)
	time.sleep(_SETTLE)
	flag = _WHEEL if direction in (scrolling.UP, scrolling.DOWN) else _HWHEEL
	amount = scrolling.wheelAmount(direction, 1)
	with keysDown(keys):
		for _ in range(max(1, min(scrolling.MAX_NOTCHES, notches))):
			_wheel(flag, amount)
			time.sleep(_WHEEL_STEP)


def scrollView(grab, box, point, direction, notches, toEnd=False, cancel=None, keys=()):
	"""Scroll with the pointer at a point and look whether anything moved, by comparing the picture of the box
	before and after. toEnd: go on, a page at a time, until nothing moves any more.
	grab(box) gives a picture. Returns (whether anything moved, how many notches were scrolled, the last picture)."""
	moveTo(*point)
	time.sleep(_SCROLL_SETTLE)  # anything that lights up under the pointer has done so before the first look
	before = grab(box)
	done, picture = 0, before
	for _round in range(scrolling.MAX_PAGES if toEnd else 1):
		if cancel is not None and cancel.is_set():
			break
		wheel(point[0], point[1], direction, notches, keys)
		time.sleep(_SCROLL_SETTLE)
		picture = grab(box)
		if scrolling.moved(before, picture) < scrolling.MOVED_SHARE:
			break
		done += notches
		before = picture
	return done > 0, done, picture


def _barFor(picture, scale, direction):
	"""The scrollbar in a picture that belongs to a direction of scrolling, or None."""
	wanted = direction in (scrolling.UP, scrolling.DOWN)
	try:
		return next((bar for bar in scrolling.scrollbars(picture, scale) if bar["vertical"] == wanted), None)
	except Exception:
		log.debugWarning("VisionClaw: the picture could not be searched for scrollbars", exc_info=True)
		return None


def click(x, y, action=pointer.CLICK, move=True):
	"""Do one mouse action at a point of the screen. Leaves the pointer there.
	move: False where the mouse turns the view; then the buttons are pressed where the game aims."""
	if move:
		moveTo(x, y)
		time.sleep(_SETTLE)
	if action == pointer.HOVER:
		return
	if action == pointer.RIGHT:
		_button(_RIGHTDOWN)
		_button(_RIGHTUP)
		return
	if action == pointer.MIDDLE:
		_button(_MIDDLEDOWN)
		_button(_MIDDLEUP)
		return
	for _ in range({pointer.DOUBLE: 2, pointer.TRIPLE: 3}.get(action, 1)):
		press()
		release()
		time.sleep(_SETTLE)


def drag(start, end):
	"""Press the mouse button at start, move to end in small steps, and let go. Blocks for about half a second."""
	moveTo(*start)
	time.sleep(_SETTLE)
	press()
	try:
		time.sleep(_HOLD)
		for point in pointer.path(start, end):
			moveTo(*point)
			time.sleep(_DRAG_STEP)
		time.sleep(_HOLD)
	finally:
		release()  # the button must never stay down


def _pause(seconds, cancel=None):
	"""Wait, in short pieces, so that stopping is noticed at once. Returns False when it was stopped."""
	until = time.monotonic() + seconds
	while True:
		if cancel is not None and cancel.is_set():
			return False
		left = until - time.monotonic()
		if left <= 0:
			return True
		time.sleep(min(0.03, left))


def hold(x, y, seconds, cancel=None):
	"""Press the mouse button at a point, keep it down for a time, and let go. Leaves the pointer there.
	Returns how long it was down."""
	moveTo(x, y)
	time.sleep(_SETTLE)
	press()
	started = time.monotonic()
	try:
		_pause(seconds, cancel)
	finally:
		release()  # the button must never stay down
	return time.monotonic() - started


def draw(paths, right=False, pace=_DRAG_STEP, cancel=None):
	"""Draw a gesture: for each list of points, press the button at the first, pass through the others in
	small steps, and let go. right: with the right mouse button, as mouse gestures in some programs want."""
	down, up = (_RIGHTDOWN, _RIGHTUP) if right else (_LEFTDOWN, _LEFTUP)
	for points in paths:
		if cancel is not None and cancel.is_set():
			return
		moveTo(*points[0])
		time.sleep(_SETTLE)
		_button(down)
		try:
			time.sleep(_HOLD)
			for point in points[1:]:
				if cancel is not None and cancel.is_set():
					break
				moveTo(*point)
				time.sleep(pace)
			time.sleep(_HOLD)
		finally:
			_button(up)  # the button must never stay down
		time.sleep(_SETTLE)


def clicks(point, times, every, cancel=None):
	"""Click at a point a number of times, in a steady rhythm. Returns how many clicks were made."""
	moveTo(*point)
	time.sleep(_SETTLE)
	started, done = time.monotonic(), 0
	for index in range(times):
		# Each click at its own moment, counted from the first, so that the rhythm does not drift.
		if not _pause(started + index * every - time.monotonic(), cancel):
			break
		press()
		release()
		done += 1
	return done


# How long the pointer rests on something before what appeared is looked at. A value of this module, so that
# the tests need not wait.
_REST = pointer.REST_SECONDS
MOVING, STOPPED, NOTHING = "moving", "stopped", "nothing"


def rest(grab, box, point, cancel=None):
	"""Rest the pointer on a point, as a hand does to see a tip or a menu that opens by itself, and look at the
	window before and after. Leaves the pointer there. Returns (the picture before, the picture after); both
	are None when the window could not be looked at."""
	x, y = point
	try:
		at = position()
		if abs(at[0] - x) < 4 and abs(at[1] - y) < 4:
			# The pointer is there already, and what it shows may be showing: away first, to the window's corner.
			moveTo(box[0] + 1, box[1] + 1)
			time.sleep(_SCROLL_SETTLE)
		before = grab(box)
	except Exception:
		log.debugWarning("VisionClaw: the window could not be looked at before resting the pointer", exc_info=True)
		before = None
	# Many programs only notice a pointer that moves, so it arrives from just beside the point.
	moveTo(x - 2, y)
	time.sleep(_SETTLE)
	moveTo(x, y)
	_pause(_REST, cancel)
	try:
		after = grab(box) if before is not None else None
	except Exception:
		log.debugWarning("VisionClaw: the window could not be looked at after resting the pointer", exc_info=True)
		before = after = None
	return before, after


def appearedText(before, after, read=True):
	"""What appeared between two pictures of a window: (whether anything did, the text that is new).
	Whether anything did is None when the window could not be looked at.
	read: whether text recognition may be used."""
	if before is None or after is None:
		return None, ""
	area = pointer.appeared(before, after)
	if area is None:
		return False, ""
	if not read:
		return True, ""
	try:
		old = ocr.rowsText(ocr.recognize(before.crop(area))).splitlines()
		new = ocr.rowsText(ocr.recognize(after.crop(area))).splitlines()
		return True, dragcontrol.newText(old, new)
	except Exception:
		log.debugWarning("VisionClaw: what appeared could not be read", exc_info=True)
		return True, ""


def restText(found, text, name):
	"""The sentence that says what resting the pointer on something showed."""
	if text:
		return f"The mouse pointer rests on {name}. This appeared: {text}"
	if found is None:
		return f"The mouse pointer rests on {name}. The window could not be looked at, so what appeared is not known."
	if found:
		return (
			f"The mouse pointer rests on {name}. Something appeared or changed in the window, but no new text could "
			"be read there. Ask what the window shows now.")
	return f"The mouse pointer rests on {name}. Nothing VisionClaw can see appeared."


def watch(grab, spot, wait, cancel=None):
	"""Look at a place again and again until it changes. Returns (how many seconds that took, ""), or
	(None, why not): MOVING when it changes all the time by itself, STOPPED, or NOTHING when the time ran out."""
	first = grab(spot)
	noise = 0.0
	for _look in range(3):
		time.sleep(pointer.LOOK_EVERY)
		noise = max(noise, dragcontrol.changed(first, grab(spot)))
	needed = pointer.trigger(noise)
	if needed is None:
		return None, MOVING
	started = time.monotonic()
	while time.monotonic() - started < wait:
		if cancel is not None and cancel.is_set():
			return None, STOPPED
		time.sleep(pointer.LOOK_EVERY)
		if dragcontrol.changed(first, grab(spot)) >= needed:
			return time.monotonic() - started, ""
	return None, NOTHING


class PointerMode:
	"""While it is on, the arrow keys move the mouse pointer inside the window in front, and other keys click,
	right-click, double-click, hold and let go for dragging, and say what is under the pointer.
	It also keeps the one mouse button that a hotkey holds down, in or out of pointer mode, so that there is
	one place that knows whether the button is down, and one that lets it go."""

	def __init__(self, plugin):
		self._plugin = plugin
		self.active = False
		self.holding = False
		self.x = self.y = 0
		self.scale = 1.0
		self._bar = -1
		# What a hotkey holds the mouse button down on, or None; and what stops a watch for a change.
		self.kept = None
		self._keptOld = self._keptTimer = None
		self._watching = None
		# One turn of the wheel at a time: the picture before and after it is compared.
		self._wheeling = threading.Lock()
		# How the mouse is moved here: Windows' pointer, the program's own pointer, or the view (claw/direct.py).
		self.direct = direct.PLAIN
		# Called with a short word when the pointer comes to the window's edge; controller mode buzzes then.
		self.onEdge = None

	# --- A button a hotkey keeps down ---

	def keepDown(self, point, name):
		"""Press the mouse button on a place and keep it down until letGo. Main thread."""
		self.letGo(say=False)
		if self.holding:
			release()
			self.holding = False
		self._keptOld = position()
		moveTo(*point)
		time.sleep(_SETTLE)
		press()
		self.kept = name or ""
		# It lets go by itself in the end: a button that stays down makes every later click a drag.
		self._keptTimer = wx.CallLater(int(pointer.HOLD_LIMIT * 1000), self.letGo, True, True)
		# Translators: Spoken when a hotkey presses the mouse button on something and keeps it down. {name} is the thing.
		ui.message(_("Holding the mouse button down on {name}. Press the hotkey again, or Escape, to let go.").format(
			name=self.kept or _("it")))

	def letGo(self, say=True, late=False):
		"""Let go of the button a hotkey keeps down. Returns whether one was down. Main thread."""
		if self.kept is None:
			return False
		release()
		name, self.kept = self.kept, None
		timer, self._keptTimer = self._keptTimer, None
		if timer is not None and not late:
			timer.Stop()
		old, self._keptOld = self._keptOld, None
		if old is not None:
			moveTo(*old)
		if say and late:
			# Translators: Spoken when a held mouse button was let go because it had been down for very long.
			ui.message(_("Let go of {name}: it had been held for two minutes.").format(name=name or _("it")))
		elif say:
			# Translators: Spoken when a hotkey lets go of the mouse button it kept down. {name} is the thing.
			ui.message(_("Let go of {name}.").format(name=name or _("it")))
		return True

	def _box(self):
		loc = self._plugin.windowBox(api.getForegroundObject())
		return (loc.left, loc.top, loc.left + loc.width, loc.top + loc.height)

	# --- A program that reads the mouse directly ---

	def wayHere(self, box):
		"""How the mouse is moved in the program in front: as it was kept for the program, where Windows' own
		pointer is hidden there; else as everywhere. Main thread."""
		way = self._plugin.appWays.mouse(appNow())
		return way if way != direct.PLAIN and not pointerState(box)["showing"] else direct.PLAIN

	def useWay(self, way, box):
		"""Move the mouse this way from now on. For a program's own pointer, the pointer is pushed into the
		window's corner, measured where that has not been done, and brought to the middle. Main thread."""
		self.leaveWay()
		self.direct = way
		if way != direct.POINTER:
			return
		app = appNow()
		tracker = direct.Tracker(
			_relative, box, self._plugin.appWays.speed(app), self._plugin._grab,
			measure=self._plugin.appWays.get(app, "speed") is None)
		_direct.way, _direct.tracker = direct.POINTER, tracker
		try:
			tracker.goTo(*pointer.centre(box))
		except Exception:
			log.debugWarning("VisionClaw: the program's own pointer could not be brought to the middle", exc_info=True)
		if tracker.measured:
			self._plugin.appWays.set(app, "speed", round(tracker.speed, 3))
		self.x, self.y = tracker.x, tracker.y

	def leaveWay(self):
		if self.direct == direct.POINTER:
			_direct.way, _direct.tracker = direct.PLAIN, None
		self.direct = direct.PLAIN

	def nextWay(self, box):
		"""Change to the next of the three ways the mouse can be moved, keep it for the program in front, and
		say which it is. Main thread."""
		way = direct.WAYS[(direct.WAYS.index(self.direct) + 1) % len(direct.WAYS)]
		self.useWay(way, box)
		app = appNow()
		self._plugin.appWays.set(app, "mouse", None if way == direct.PLAIN else way)
		text = {
			# Translators: Spoken in pointer mode when the mouse is moved as in every other program again.
			direct.PLAIN: _("Windows' own mouse pointer is moved, as in other programs."),
			# Translators: Spoken in pointer mode when a game's own pointer is moved by moving the mouse itself.
			direct.POINTER: _(
				"The program's own pointer is moved: VisionClaw pushed it into the corner of the window, counted from "
				"there and brought it to the middle. Kept for this program."),
			# Translators: Spoken in pointer mode when the arrow keys turn a game's view by moving the mouse itself.
			direct.VIEW: _(
				"The mouse turns the view: the arrow keys move the mouse itself, and Enter clicks where the game aims. "
				"Kept for this program."),
		}[way]
		ui.message(text)
		return text

	def start(self):
		"""Turn pointer mode on. Returns what was said, so a tool can pass it on. Main thread."""
		self.place()
		self.active, self.holding = True, False
		return self.help()

	def place(self):
		"""Put the pointer where pointer mode begins, in the window in front, and move the mouse the way this
		program needs. Without the keys of pointer mode: controller mode uses this too. Main thread."""
		box = self._box()
		self.x, self.y = pointer.centre(box)
		try:
			# Start on the focused control, where it has a place inside the window.
			loc = api.getFocusObject().location
			if loc and loc.width > 0 and loc.height > 0:
				self.x, self.y = pointer.clamp(loc.left + loc.width // 2, loc.top + loc.height // 2, box)
		except Exception:
			pass
		way = self.wayHere(box)
		if way == direct.PLAIN:
			self.leaveWay()
			moveTo(self.x, self.y)
		else:
			self.x, self.y = pointer.centre(box)
			self.useWay(way, box)
		# Steps and areas follow the scaling of the monitor the window is on.
		self.scale = scaleAt(self.x, self.y)

	def help(self):
		"""Say what the keys of pointer mode do. Returns what was said."""
		# Translators: Spoken when pointer mode is turned on.
		text = _(
			"Pointer mode is on. The arrow keys move the mouse pointer in this window; with Shift in small steps, "
			"with Control in large ones. Enter clicks, Shift+Enter double-clicks, A right-clicks. "
			"G holds the mouse button down, and G again lets go, for dragging. I turns the mouse wheel up and K "
			"down, J left and L right, about a page; with Shift one notch. S finds the scrollbars and puts the "
			"pointer on one. D tries what is under the pointer as a dial or slider: it turns the wheel on it and drags "
			"it a little, and then the arrow keys work it. T rests the pointer here and says what appears, as for a "
			"tip or a menu that opens by itself. C clicks here the moment what is here changes, and Shift+C only "
			"sounds a tone then. W says what is at the pointer, R reads the text there, P says where the pointer "
			"is, B brings it back to the middle, H repeats this help. M changes how the mouse is moved, for a game that reads "
			"the mouse directly: Windows' pointer, the game's own pointer, or the view that the mouse turns. "
			"Escape turns pointer mode off."
		)
		if self.direct == direct.POINTER:
			# Translators: Added to the help of pointer mode in a program that draws its own mouse pointer.
			text += " " + _("In this program its own pointer is moved, as you told VisionClaw.")
		elif self.direct == direct.VIEW:
			# Translators: Added to the help of pointer mode in a program where the mouse turns the view.
			text += " " + _("In this program the mouse turns the view: the arrow keys move the mouse itself, as you told VisionClaw.")
		ui.message(text)
		return text

	def stop(self, say=True):
		if self.holding:
			release()
		self.letGo(say=False)
		self._stopWatching()
		self.leaveWay()
		wasOn, self.active, self.holding = self.active, False, False
		if say and wasOn:
			# Translators: Spoken when pointer mode is turned off.
			ui.message(_("Pointer mode is off."))

	def toggle(self):
		self.stop() if self.active else self.start()

	def scriptFor(self, gesture):
		"""The pointer mode command for a pressed key, as a script, or None."""
		if self.kept is not None and "kb:escape" in gesture.normalizedIdentifiers:
			# Escape lets go of a button that a hotkey keeps down, in pointer mode or out of it.
			def script_letGo(gesture):
				self.letGo()
			return script_letGo
		if not self.active:
			return None
		for identifier in gesture.normalizedIdentifiers:
			command = pointer.KEYS.get(identifier)
			if command is not None:
				def script_pointerMode(gesture, command=command):
					self._run(command)
				return script_pointerMode
		return None

	def _stopWatching(self):
		"""Stop a watch for a change, if one is running. Returns whether one was."""
		watching, self._watching = self._watching, None
		if watching is None or watching.is_set():
			return False
		watching.set()
		return True

	def _run(self, command):
		if self._stopWatching():
			return  # a key pressed during a watch only ends the watch; the watch says that it stopped
		try:
			box = self._box()
		except Exception:
			self.stop()
			return
		name = command[0]
		view = self.direct == direct.VIEW
		if name == "way":
			self.nextWay(box)
		elif name == "move" and view:
			# The mouse itself is moved; there is no place, so the tone only says that it moved.
			dx, dy = pointer.DIRECTIONS[command[1]]
			steps = round(pointer.stepFor(command[2], box, self.scale) * self._plugin.appWays.speed(appNow()))
			nudge(dx * steps, dy * steps)
			tones.beep(660, 20)
		elif name in ("centre", "where") and view:
			# Translators: Spoken in pointer mode when the user asks where the pointer is in a game whose view the mouse turns.
			ui.message(_("The mouse turns the view here, so there is no pointer with a place."))
		elif name == "move":
			x, y = pointer.move(self.x, self.y, command[1], pointer.stepFor(command[2], box, self.scale), box)
			atEdge = (x, y) == (self.x, self.y)
			self.x, self.y = x, y
			moveTo(x, y)
			# A short tone says how high the pointer is; a low one that it is at the edge.
			tones.beep(180 if atEdge else pointer.pitch(y, box), 25)
			if atEdge and self.onEdge is not None:
				self.onEdge()
		elif name == "centre":
			self.x, self.y = pointer.centre(box)
			moveTo(self.x, self.y)
			ui.message(pointer.where(self.x, self.y, box))
		elif name in ("click", "double", "right", "middle"):
			if self.holding:
				release()
				self.holding = False
			action = {"click": pointer.CLICK, "double": pointer.DOUBLE, "right": pointer.RIGHT, "middle": pointer.MIDDLE}[name]
			threading.Thread(target=self._click, args=(action, not view), daemon=True).start()
			# Translators: Spoken in pointer mode after a mouse action. One of: click, double click, right click, middle click.
			ui.message({"click": _("click"), "double": _("double click"), "right": _("right click"), "middle": _("middle click")}[name])
		elif name == "grab":
			if self.holding:
				release()
				self.holding = False
				# Translators: Spoken in pointer mode when the mouse button is let go after dragging.
				ui.message(_("Let go."))
			else:
				if not view:
					moveTo(self.x, self.y)
				press()
				self.holding = True
				# Translators: Spoken in pointer mode when the mouse button is held down for dragging.
				ui.message(_("Holding. Move with the arrow keys, then press G to let go."))
		elif name == "where":
			ui.message(pointer.where(self.x, self.y, box))
		elif name == "read":
			threading.Thread(target=self._read, args=(box,), daemon=True).start()
		elif name == "look":
			threading.Thread(target=self._look, args=(box,), daemon=True).start()
		elif name == "scroll":
			# A key that repeats while the wheel is still being turned is left out, so that what is said is true.
			if self._wheeling.acquire(False):
				threading.Thread(
					target=self._scroll, args=(box, command[1], pointer.notchesFor(command[2])), daemon=True).start()
		elif name == "rest":
			threading.Thread(target=self._restHere, args=(box,), daemon=True).start()
		elif name == "when":
			self._watching = threading.Event()
			# Translators: Spoken in pointer mode when VisionClaw starts to watch what is under the pointer for a change.
			ui.message(_("Watching what is here. Any key of pointer mode stops it."))
			threading.Thread(target=self._when, args=(box, command[1], self._watching), daemon=True).start()
		elif name == "take":
			self._plugin.controlKeys.takeAtPointer()
		elif name == "bars":
			threading.Thread(target=self._bars, args=(box,), daemon=True).start()
		elif name == "help":
			self.help()
		elif name == "exit":
			self.stop()

	def _restHere(self, box):
		"""Rest the pointer where it is and say what appeared: a tip, a menu that opens by itself, a preview."""
		before, after = rest(self._plugin._grab, box, (self.x, self.y))
		found, text = appearedText(before, after)
		if text:
			wx.CallAfter(ui.message, text)
		elif found is None:
			# Translators: Spoken in pointer mode when the window could not be looked at after resting the pointer.
			wx.CallAfter(ui.message, _("The window could not be looked at."))
		elif found:
			# Translators: Spoken in pointer mode when resting the pointer changed the window but no new text was read.
			wx.CallAfter(ui.message, _("Something appeared or changed, but no new text could be read. W says what is here."))
		else:
			# Translators: Spoken in pointer mode when resting the pointer on something showed nothing new.
			wx.CallAfter(ui.message, _("Nothing appeared."))

	def _when(self, box, press_, stopped):
		"""Watch what is under the pointer and, the moment it changes, click it or only sound a tone."""
		side = scrolling.pixels(dragcontrol.SPOT, self.scale)
		spot = dragcontrol.around((self.x, self.y), side, box)
		try:
			moveTo(self.x, self.y)
			time.sleep(_SCROLL_SETTLE)  # anything that lights up under the pointer has done so before the first look
			took, why = watch(self._plugin._grab, spot, pointer.WAIT_DEFAULT, stopped)
			if took is not None and press_:
				press()
				release()
		except Exception:
			log.debugWarning("VisionClaw: could not watch at the pointer", exc_info=True)
			took, why = None, NOTHING
		if self._watching is stopped:
			self._watching = None
		if took is not None:
			tones.beep(1200, 40)
			# Translators: Spoken in pointer mode when what was watched changed. The first also clicked it.
			wx.CallAfter(ui.message, _("It changed, and was clicked.") if press_ else _("It changed."))
		elif why == MOVING:
			# Translators: Spoken in pointer mode when what is under the pointer changes all the time.
			wx.CallAfter(ui.message, _(
				"What is here moves all the time, so VisionClaw cannot tell one moment from another."))
		elif why == STOPPED:
			# Translators: Spoken in pointer mode when watching for a change was stopped by a key.
			wx.CallAfter(ui.message, _("Stopped watching."))
		else:
			# Translators: Spoken in pointer mode when what was watched did not change in time.
			wx.CallAfter(ui.message, _("Nothing changed here in half a minute."))

	def _letGo(self):
		# Translators: Spoken in pointer mode when Shift, Control or Alt was kept down after a key of pointer mode.
		return _("Let go of Shift, Control and Alt first: held down, they change what the mouse does. Nothing was done.")

	def _click(self, action, move):
		"""Click where the pointer is, once the user's own Shift, Control and Alt are up: Shift+Enter leaves Shift
		down for a moment, and with it a double click would select everything in between."""
		if not keysUp():
			wx.CallAfter(ui.message, self._letGo())
			return
		click(self.x, self.y, action, move)

	def _scroll(self, box, direction, notches):
		"""Turn the wheel at the pointer, once the user's own Shift, Control and Alt are up, and say where the
		view now stands, or that it did not move."""
		try:
			text = self._scrolled(box, direction, notches) if keysUp() else self._letGo()
		except Exception:
			log.debugWarning("VisionClaw: could not scroll at the pointer", exc_info=True)
			# Translators: Spoken in pointer mode when scrolling was not possible.
			text = _("Scrolling did not work here.")
		finally:
			self._wheeling.release()
		wx.CallAfter(ui.message, text)

	def _scrolled(self, box, direction, notches):
		moved, _done, picture = scrollView(self._plugin._grab, box, (self.x, self.y), direction, notches)
		if not moved:
			# Translators: Spoken in pointer mode when turning the wheel moved nothing.
			return _("Nothing moved. This is the end, or nothing scrolls under the pointer.")
		bar = _barFor(picture, self.scale, direction)
		# Translators: Spoken in pointer mode after scrolling when no scrollbar shows how far. {direction} is up, down, left or right.
		return scrolling.positionText(bar) if bar else _("Scrolled {direction}.").format(direction=direction)

	def _bars(self, box):
		"""Find the scrollbars in the window's picture and put the pointer on the next one's thumb."""
		try:
			found = scrolling.scrollbars(self._plugin._grab(box), self.scale)
		except Exception:
			log.debugWarning("VisionClaw: could not look for scrollbars", exc_info=True)
			found = []
		if not found:
			# Translators: Spoken in pointer mode when no scrollbar was found in the window's picture.
			wx.CallAfter(ui.message, _(
				"No scrollbar was found in this window's picture. I and K still turn the wheel up and down."))
			return
		self._bar = (self._bar + 1) % len(found)
		bar = found[self._bar]
		self.x, self.y = pointer.clamp(box[0] + bar["grip"][0], box[1] + bar["grip"][1], box)
		moveTo(self.x, self.y)
		# Translators: Spoken in pointer mode when the pointer was put on a scrollbar. {bar} describes it.
		wx.CallAfter(ui.message, _(
			"{bar}. The pointer is on it: G holds it, the arrow keys move it, G lets go."
		).format(bar=scrolling.barText(bar).capitalize()))

	def _area(self, box, size):
		"""A picture of the area around the pointer, kept inside the window. size is for a plain screen."""
		size = (scrolling.pixels(size[0], self.scale), scrolling.pixels(size[1], self.scale))
		left, top = pointer.clamp(self.x - size[0] // 2, self.y - size[1] // 2, box)
		right, bottom = pointer.clamp(self.x + size[0] // 2, self.y + size[1] // 2, box)
		return self._plugin._grab((left, top, max(left + 16, right), max(top + 16, bottom)))

	def _read(self, box):
		try:
			text = ocr.rowsText(ocr.recognize(self._area(box, _READ_AREA))).strip()
		except Exception:
			log.debugWarning("VisionClaw: could not read at the pointer", exc_info=True)
			text = ""
		# Translators: Spoken in pointer mode when there is no text at the pointer.
		wx.CallAfter(ui.message, text or _("No text here."))

	def _look(self, box):
		try:
			image = self._area(box, _LOOK_AREA)
			answer = self._plugin.runtime.describe(
				prepareImage(image, 448),
				"This is the part of a window around the mouse pointer, which is at the centre of the picture. "
				"In one short sentence, say what is at the centre: what kind of control or thing it is, and any "
				"text on it. If nothing is there, say that it is empty.", 70)
		except EngineError:
			answer = ""
		except Exception:
			log.debugWarning("VisionClaw: could not look at the pointer", exc_info=True)
			answer = ""
		# Translators: Spoken in pointer mode when the vision model could not say what is at the pointer.
		wx.CallAfter(ui.message, answer or _("VisionClaw could not tell what is here."))


def _onMain(fn, timeout=10):
	"""Run fn on NVDA's main thread and return its result."""
	if wx.IsMainThread():
		return fn()
	done = threading.Event()
	box = {}

	def run():
		try:
			box["value"] = fn()
		except Exception as e:
			box["error"] = e
		done.set()

	wx.CallAfter(run)
	if not done.wait(timeout):
		raise ToolError("NVDA did not answer in time.")
	if "error" in box:
		raise box["error"]
	return box.get("value")


def _windowBox(result):
	info = result.imageInfo
	return (info.screenLeft, info.screenTop, info.screenLeft + info.screenWidth, info.screenTop + info.screenHeight)


def register(add, plugin, text, confirm, screen, pickItem, mentioned):
	"""Add the mouse tools to the tools the models can use. Called from nvdatools.build."""

	def dragItem(task, item, to, asked):
		result = getattr(task, "items", None) or screen.items()
		if getattr(result, "web", False):
			raise ToolError(
				"Dragging works on windows read from their picture, not on the parts of a web page that NVDA already "
				"reads. For a web page, use pointer mode.")
		box = _windowBox(result)
		# The user's own words decide where they can: "drag A onto B" names both ends, in that order, and
		# "drag the slider right a little" names the thing and the direction.
		names = mentioned(asked, result.items) if asked else []
		if len(names) == 2:
			item, to = names
		elif len(names) == 1 and pointer.dragOffset(asked, box) is not None:
			item, to = names[0], asked
		index = pickItem(item, result.items)
		if index is None:
			raise ToolError(f"There is no item called \"{item}\". Use a number or a name from list_items.")
		source = result.items[index]
		start = result.screenPoint(source)
		offset = pointer.dragOffset(to, box)
		if offset is not None:
			end = pointer.clamp(start[0] + offset[0], start[1] + offset[1], box)
			across, down = end[0] - start[0], end[1] - start[1]
			where = (f"{abs(across)} pixels to the {'right' if across > 0 else 'left'}" if across
				else f"{abs(down)} pixels {'down' if down > 0 else 'up'}")
		else:
			target = pickItem(to, result.items)
			if target is None or target == index:
				raise ToolError(
					f"\"{to}\" is neither another item from list_items nor a direction. Give an item to drag onto, "
					"or a direction with a distance.")
			end = result.screenPoint(result.items[target])
			where = "onto " + result.items[target]["text"]
		# Translators: Asked before VisionClaw drags something with the mouse. {item} is what, {where} where to.
		confirm(_("Drag {item} {where}?").format(item=source["text"], where=where))
		old = position()
		drag(start, end)
		time.sleep(0.3)
		moveTo(*old)
		task.items = None  # the window has probably changed
		return f"Dragged {source['text']} {where}."

	add("drag_item",
		"drag one item from list_items with the mouse: onto another item, or in a direction, as for a slider",
		dragItem, {
			"item": text("the number or the name of the item to drag, from list_items", maxLength=80),
			"to": text("the item to drag it onto, or a direction and distance in the user's words, such as: right a little",
				maxLength=80),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="list_items", title="Dragging the item")

	def scrollTool(task, direction, asked):
		words = asked or task.request
		notches, toEnd = scrolling.amountOf(words)

		def place():
			"""Where to scroll: over the focused control if it is a sizeable part of the window, else the
			middle of the window. Never over a control whose value the wheel would change. Main thread."""
			fg = api.getForegroundObject()
			loc = plugin.windowBox(fg)
			box = (loc.left, loc.top, loc.left + loc.width, loc.top + loc.height)
			point = pointer.centre(box)
			scale = scaleAt(*point)
			spot = None
			try:
				spot = api.getFocusObject().location
			except Exception:
				pass
			if spot and spot.width >= scrolling.pixels(80, scale) and spot.height >= scrolling.pixels(60, scale):
				point = pointer.clamp(spot.left + spot.width // 2, spot.top + spot.height // 2, box)
			for candidate in (point, pointer.centre(box)):
				try:
					under = api.getDesktopObject().objectFromPoint(*candidate)
					kind = getattr(getattr(under, "role", None), "name", "")
				except Exception:
					kind = ""
				if kind not in _WHEEL_CHANGES:
					return box, candidate, scale, " ".join(str(getattr(fg, "name", "") or "").split())
			return box, None, scale, ""

		box, point, scale, title = _onMain(place)
		if point is None:
			raise ToolError(
				"The mouse pointer would be over a control whose value the wheel changes, so nothing was scrolled. "
				"Pointer mode lets the user choose the place.")
		where = f"the window {title}" if title else "the window in front"
		zoom = scrolling.zoomOf(words)
		if zoom:
			# Larger or smaller: the wheel with Control held down, as a sighted person does it. A little at a time.
			direction = scrolling.UP if zoom == "in" else scrolling.DOWN
			counted = scrolling._NUMBER.search(words.lower())
			notches = min(notches, scrolling.PAGE_NOTCHES) if counted and counted.group(2) else 2
			size = "larger" if zoom == "in" else "smaller"
			# Translators: Asked before VisionClaw zooms with the mouse wheel. {size} is larger or smaller.
			confirm(_("Make what {where} shows {size}, with the Control key and the mouse wheel?").format(where=where, size=size))
			old = position()
			try:
				moved, _done, _picture = scrollView(plugin._grab, box, point, direction, notches, False, task.cancel, ("control",))
			finally:
				moveTo(*old)
			task.items = None
			if not moved:
				return (
					f"Nothing VisionClaw can see changed in {where}. It may not be made {size} with the Control key and "
					f"the mouse wheel, or it is as {'large' if zoom == 'in' else 'small'} as it goes.")
			return f"Made what {where} shows {size}, with the Control key and {notches} notches of the mouse wheel."
		far = "to the end" if toEnd else ("about a page" if notches == scrolling.PAGE_NOTCHES else f"{notches} notches of the wheel")
		# Translators: Asked before VisionClaw scrolls with the mouse wheel. {direction} is up, down, left or right.
		confirm(_("Scroll {direction} {far} in {where}?").format(direction=direction, far=far, where=where))
		old = position()
		try:
			moved, done, picture = scrollView(plugin._grab, box, point, direction, notches, toEnd, task.cancel)
		finally:
			moveTo(*old)
		task.items = None  # what the window shows has changed
		if not moved:
			return (
				f"Nothing moved in {where}. It is already as far {direction} as it goes, or nothing scrolls where "
				"the mouse pointer was put.")
		bar = _barFor(picture, scale, direction)
		stands = f" It now stands {scrolling.positionText(bar)}." if bar else ""
		if toEnd:
			return f"Scrolled {direction} in {where} until nothing moved any more.{stands}"
		return f"Scrolled {direction} {far} in {where}.{stands}"

	add("scroll_view",
		"scroll what the window in front shows with the mouse wheel, up, down, left or right, a little, a page or "
		"to the end, or zoom in or out with the Control key and the wheel; says whether anything moved and how far "
		"along the view now stands",
		scrollTool, {
			"direction": text("which way to scroll", enum=scrolling.DIRECTIONS, auto=scrolling.directionOf),
			"asked": text("what the user asked for, in their own words, with how far to scroll", maxLength=300, auto=True),
		}, changes=True, title="Scrolling")

	def placeFor(task, words):
		"""Where a gesture or a timed click is meant, as (point on the screen, what to call it, the window's box):
		the pointer in pointer mode or when the words say so; else the one item the words name; else the control
		NVDA is on, if it is a part of the window; else the middle of the window."""
		mode = plugin.pointerMode
		if mode.active or dragcontrol.atPointer(words):
			box = _onMain(mode._box)
			point = (mode.x, mode.y) if mode.active else position()
			if not (box[0] <= point[0] < box[2] and box[1] <= point[1] < box[3]):
				raise ToolError("The mouse pointer is not inside the window in front. Put it there with pointer mode first.")
			return point, "what is under the mouse pointer", box
		result = getattr(task, "items", None) or screen.items()
		if not getattr(result, "web", False):
			names = mentioned(words, result.items)
			index = pickItem(names[0], result.items) if names else None
			if index is not None:
				return result.screenPoint(result.items[index]), result.items[index]["text"], _windowBox(result)
		box = _onMain(mode._box)

		def current():
			"""The navigator object or the focused control, where it is a part of the window. Main thread."""
			whole = max(1, (box[2] - box[0]) * (box[3] - box[1]))
			for get in (api.getNavigatorObject, api.getFocusObject):
				try:
					obj = get()
					loc = obj.location
					name = " ".join(str(obj.name or "").split())[:60]
				except Exception:
					continue
				if (loc and loc.width > 0 and loc.height > 0 and loc.width * loc.height < 0.6 * whole
						and box[0] <= loc.left + loc.width // 2 < box[2] and box[1] <= loc.top + loc.height // 2 < box[3]):
					return (loc.left + loc.width // 2, loc.top + loc.height // 2), name or "the control you are on"
			return None
		found = _onMain(current)
		if found is not None:
			return found[0], found[1], box
		return pointer.centre(box), "the middle of the window", box

	def changedText(before, after):
		"""Whether what the window shows changed, in a sentence."""
		if before is None or after is None:
			return ""
		if pointer.appeared(before, after) is not None:
			return " What the window shows changed."
		return " Nothing VisionClaw can see changed in the window."

	def look(box):
		try:
			return plugin._grab(box)
		except Exception:
			log.debugWarning("VisionClaw: the window could not be looked at", exc_info=True)
			return None

	def gestureTool(task, asked):
		words = asked or task.request
		gesture = pointer.gestureOf(words)
		if gesture is None:
			raise ToolError(
				"The request does not say which gesture to draw. A swipe or a line needs its direction: left, right, "
				"up or down, also several one after another. A shape needs its name: a circle, a tick, a zigzag, a "
				"square, a triangle, a cross, or one of the letters L, V, Z, N, M and W.")
		point, name, box = placeFor(task, words)
		paths = pointer.gesturePaths(gesture, point, box)
		right = gesture["button"] == pointer.RIGHT_BUTTON
		how = "the right mouse button" if right else "the mouse button"
		# Translators: Asked before VisionClaw draws a gesture with the mouse. {gesture} is what, such as: a swipe to the left.
		confirm(_("Draw {gesture} on {name}, with {button} held down?").format(gesture=gesture["text"], name=name, button=how))
		old = position()
		before = look(box)
		try:
			draw(paths, right, gesture["pace"], task.cancel)
		finally:
			time.sleep(_SCROLL_SETTLE)
			moveTo(*old)
		task.check()
		after = look(box) if before is not None else None
		task.items = None  # the window has probably changed
		return f"Drew {gesture['text']} on {name}, with {how} held down.{changedText(before, after)}"

	add("draw_gesture",
		"swipe, flick or draw a line or a shape with the mouse button held down, on an item the user names, at the "
		"mouse pointer or in the middle of the window, for a program that is worked by gestures; says whether "
		"anything changed",
		gestureTool, {
			"asked": text("what the user asked for, in their own words, with the direction or the shape", maxLength=300, auto=True),
		}, changes=True, title="Drawing the gesture")

	def timedTool(task, asked):
		words = asked or task.request
		timing = pointer.timingOf(words)
		if timing is None:
			raise ToolError(
				"The request does not say when to click: as soon as the thing changes or appears, or a number of "
				"times in a row.")
		point, name, box = placeFor(task, words)
		old = position()
		if timing["mode"] == pointer.RHYTHM:
			times, every = timing["times"], pointer.secondsText(timing["every"])
			# Translators: Asked before VisionClaw clicks something many times. {every} is a time, such as: half a second.
			confirm(_("Click {name} {times} times, one every {every}?").format(name=name, times=times, every=every))
			before = look(box)
			try:
				done = clicks(point, times, timing["every"], task.cancel)
			finally:
				moveTo(*old)
			task.check()
			time.sleep(_SCROLL_SETTLE)
			task.items = None
			return f"Clicked {name} {done} times, one every {every}.{changedText(before, look(box) if before is not None else None)}"
		wait = pointer.secondsText(timing["wait"])
		# Translators: Asked before VisionClaw watches something and clicks it when it changes. {wait} is a time.
		confirm(_("Click {name} as soon as it changes? VisionClaw watches it for up to {wait}.").format(name=name, wait=wait))
		scale = _onMain(lambda: scaleAt(*point))
		spot = dragcontrol.around(point, scrolling.pixels(dragcontrol.SPOT, scale), box)
		try:
			moveTo(*point)
			time.sleep(_SCROLL_SETTLE)  # anything that lights up under the pointer has done so before the first look
			took, why = watch(plugin._grab, spot, timing["wait"], task.cancel)
			if took is not None:
				press()
				release()
				time.sleep(_SETTLE)
		finally:
			moveTo(*old)
		task.check()
		if took is not None:
			task.items = None
			return (
				f"{name[:1].upper() + name[1:]} changed after {pointer.secondsText(round(took, 1) or 0.1)} and was clicked "
				"at once. VisionClaw looks about 25 times a second, so the click came a moment after the change.")
		if why == MOVING:
			raise ToolError(
				f"{name[:1].upper() + name[1:]} moves or changes all the time, so VisionClaw cannot tell one moment from "
				"another there, and nothing was clicked. In pointer mode, Shift+C sounds a tone at a change and Enter clicks.")
		raise ToolError(f"Nothing changed at {name} in {wait}, so nothing was clicked.")

	add("timed_click",
		"click something at the right moment: as soon as it changes or appears, or many times in a steady rhythm; "
		"for games and controls that react to timing",
		timedTool, {
			"asked": text("what the user asked for, in their own words, with when or how often to click", maxLength=300, auto=True),
		}, changes=True, title="Clicking at the right moment")

	def turnView(task, asked):
		words = asked or task.request
		app, box = _onMain(lambda: (appNow(), plugin.pointerMode._box()))
		turn = direct.turnOf(words, plugin.appWays.speed(app))
		if turn is None:
			raise ToolError(
				"The request does not say which way to turn or look: left, right, up or down, or around. How far may "
				"be said as a little, a lot, or a number of steps.")
		# Translators: Asked before VisionClaw moves the mouse itself to turn a game's view. {how} is how far and which way.
		confirm(_("Move the mouse itself {how}, to turn or look in {app}?").format(
			# Translators: Stands for a program's name where the name is not known.
			how=turn["text"], app=app or _("this program")))
		before = look(box)
		whole = nudge(turn["dx"], turn["dy"], task.cancel)
		task.check()
		time.sleep(_SCROLL_SETTLE)
		after = look(box) if before is not None else None
		task.items = None
		said = f"Moved the mouse itself {turn['text']}."
		if not whole:
			said = "Stopped while moving the mouse itself."
		if before is None or after is None:
			changed = " The window could not be looked at, so whether the view changed is not known."
		elif scrolling.moved(before, after) >= scrolling.MOVED_SHARE or pointer.appeared(before, after) is not None:
			changed = " What the window shows changed."
		else:
			changed = (
				" Nothing VisionClaw can see changed in the window. The program may not turn with the mouse just now, or "
				"it refuses movements made by a program.")
		guess = (
			" How far a program turns for one step of the mouse differs from program to program: if that was too far "
			"or not far enough, say that direct mouse movement is too fast or too slow here, and VisionClaw keeps it "
			"for this program.") if turn["guess"] else ""
		return said + changed + guess

	add("turn_view",
		"turn the view, look or aim in a game that reads the mouse directly, by moving the mouse itself left, right, "
		"up or down, a little, a lot or around; says whether the view changed",
		turnView, {
			"asked": text("what the user asked for, in their own words, with the direction", maxLength=300, auto=True),
		}, changes=True, title="Moving the mouse itself")

	def mouseWay(task, asked):
		words = asked or task.request
		app, box = _onMain(lambda: (appNow(), plugin.pointerMode._box()))
		ways = plugin.appWays
		state = pointerState(box)
		wanted = direct.wayOf(words)
		if not app:
			raise ToolError("Which program is in front could not be found out.")
		if wanted is None:
			# Only asked about: what is kept and what Windows says, in plain code's own words.
			kept = ways.mouse(app)
			lines = [f"In {app}, {direct.wayText(kept)}."]
			if kept != direct.PLAIN:
				lines.append(f"One step of the mouse counts as {ways.speed(app):g} there.")
			facts = direct.stateText(state)
			if facts:
				lines.append(facts)
				if kept == direct.PLAIN:
					lines.append(direct.ADVICE)
			elif kept == direct.PLAIN:
				lines.append("Windows' own mouse pointer shows here, so the usual way should work.")
			return " ".join(lines)
		kind, value = wanted
		if kind == "speed":
			speed = max(direct.SPEED_LEAST, min(direct.SPEED_MOST, ways.speed(app) * value))
			# Translators: Asked before VisionClaw keeps a different speed of the mouse for one program.
			confirm(_("Make direct mouse movement in {app} {how}, and keep that for this program?").format(
				# Translators: How direct mouse movement is changed for a program: slower, or faster.
				app=app, how=_("slower") if value < 1 else _("faster")))
			ways.set(app, "speed", round(speed, 3))
			return (
				f"Direct mouse movement in {app} is now {'slower' if value < 1 else 'faster'}: one step counts as "
				f"{speed:g}. This is kept for the program.")
		if kind == "measure":
			if ways.mouse(app) != direct.POINTER:
				raise ToolError(
					f"Measuring is for a program that draws a pointer of its own, and {app} is not kept as one. Say "
					"first that the program has its own pointer.")
			# Translators: Asked before VisionClaw measures how fast a game moves its own mouse pointer.
			confirm(_("Push the pointer of {app} into the corner of its window and move it three times, to measure it?").format(app=app))
			tracker = direct.Tracker(_relative, box, ways.speed(app), plugin._grab)
			tracker.home()
			if not tracker.measure():
				return (
					f"The pointer of {app} could not be measured: its picture did not show one small thing moving. "
					f"One step of the mouse still counts as {ways.speed(app):g} there. If clicks land beside what you "
					"name, say that it is too fast or too slow.")
			ways.set(app, "speed", round(tracker.speed, 3))
			return f"Measured: {app} moves its pointer {tracker.speed:.2f} pixels for one step of the mouse. Kept for the program."
		if value == ways.mouse(app):
			return f"That is how it is already kept: in {app}, {direct.wayText(value)}."
		# Translators: Asked before VisionClaw keeps how the mouse is moved in one program. {way} says how.
		confirm(_("Keep this for {app}: {way}?").format(app=app, way=direct.wayText(value)))
		ways.set(app, "mouse", None if value == direct.PLAIN else value)
		if value == direct.PLAIN:
			ways.set(app, "speed", None)
			return f"In {app}, {direct.wayText(value)} again. What was kept about its mouse is forgotten."
		more = (
			" Clicking, holding, dragging and gestures on things you name now move the program's own pointer. Its "
			"speed is measured the first time; if clicks land beside what you name, say that it is too fast or too slow."
			if value == direct.POINTER else
			" Ask to turn left or right, to look up or down, or to turn around. In pointer mode the arrow keys now "
			"move the mouse itself.")
		hidden = "" if not state["showing"] else (
			" Windows' own pointer shows here just now; this way is used whenever the program hides it.")
		return f"Kept for {app}: {direct.wayText(value)}.{more}{hidden}"

	add("mouse_way",
		"say or keep how the mouse is moved in the program in front: Windows' own pointer, a pointer the game draws "
		"itself, or a view that the mouse turns; also make direct mouse movement faster or slower there, or measure "
		"the game's own pointer",
		mouseWay, {
			"asked": text("what the user said about how this program uses the mouse, in their own words", maxLength=300, auto=True),
		}, changes=True, title="How the mouse is moved here")

	def pointerMode(task):
		done = threading.Event()
		box = {}

		def start():
			try:
				box["text"] = plugin.pointerMode.start()
			finally:
				done.set()
		wx.CallAfter(start)
		done.wait(10)
		return box.get("text") or "Pointer mode could not be turned on."

	add("pointer_mode",
		"turn on pointer mode, so the user can work any control with the keyboard: the arrow keys move the mouse "
		"pointer, and keys click, right-click, double-click and drag",
		pointerMode, title="Turning on pointer mode", tell=VERBATIM)
	# What the tools for fingers and pressure share with these: where a request is meant, and whether it changed.
	import types
	return types.SimpleNamespace(placeFor=placeFor, changedText=changedText, look=look)
