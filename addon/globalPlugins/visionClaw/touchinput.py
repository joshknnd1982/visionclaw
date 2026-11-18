# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - fingers and a pen, without a touch screen and without a pen. Windows lets a program touch the
# screen as fingers would, several at once, and press as a pen would, with how hard it presses; programs
# that are worked by pinching, by turning with two fingers or by pressure then answer as they do to a hand.
# Here those are functions: a gesture given as the places every finger passes through, a pen stroke given
# as places with a pressure each, and a pen that is held down and moved for as long as someone wants.
# Whatever is put down here is lifted again, also when the request is stopped or something fails.
# The structures and numbers were read from Microsoft's own pages on 2026-11-18 (POINTER_INFO,
# POINTER_TOUCH_INFO, POINTER_PEN_INFO, POINTER_TYPE_INFO, InjectTouchInput, InjectSyntheticPointerInput).

import contextlib
import ctypes
import threading
import time
from ctypes import wintypes

from .claw import touch
from .vclog import log

_PT_TOUCH, _PT_PEN = 2, 3
_INRANGE, _INCONTACT, _DOWN, _UPDATE, _UP = 0x00000002, 0x00000004, 0x00010000, 0x00020000, 0x00040000
DOWN, MOVE, UP = _INRANGE | _INCONTACT | _DOWN, _INRANGE | _INCONTACT | _UPDATE, _UP
_TOUCH_MASK = 0x1 | 0x2 | 0x4  # the contact's area, its direction and its pressure are given
_PEN_MASK_PRESSURE = 0x1
_PEN_INVERTED, _PEN_ERASER = 0x2, 0x4
_FEEDBACK_DEFAULT = 1
_NOT_READY, _ACCESS_DENIED = 21, 5
# Windows' numbers for where the whole desktop begins, which may lie left of or above the main screen.
_VIRTUAL_LEFT, _VIRTUAL_TOP = 76, 77
# Half the width of a finger's contact, in pixels.
_FINGER = 3


class _POINTER_INFO(ctypes.Structure):
	_fields_ = [
		("pointerType", ctypes.c_uint32), ("pointerId", ctypes.c_uint32), ("frameId", ctypes.c_uint32),
		("pointerFlags", ctypes.c_uint32), ("sourceDevice", wintypes.HANDLE), ("hwndTarget", wintypes.HWND),
		("ptPixelLocation", wintypes.POINT), ("ptHimetricLocation", wintypes.POINT),
		("ptPixelLocationRaw", wintypes.POINT), ("ptHimetricLocationRaw", wintypes.POINT),
		("dwTime", wintypes.DWORD), ("historyCount", ctypes.c_uint32), ("InputData", ctypes.c_int32),
		("dwKeyStates", wintypes.DWORD), ("PerformanceCount", ctypes.c_uint64), ("ButtonChangeType", ctypes.c_int),
	]


class _POINTER_TOUCH_INFO(ctypes.Structure):
	_fields_ = [
		("pointerInfo", _POINTER_INFO), ("touchFlags", ctypes.c_uint32), ("touchMask", ctypes.c_uint32),
		("rcContact", wintypes.RECT), ("rcContactRaw", wintypes.RECT), ("orientation", ctypes.c_uint32),
		("pressure", ctypes.c_uint32),
	]


class _POINTER_PEN_INFO(ctypes.Structure):
	_fields_ = [
		("pointerInfo", _POINTER_INFO), ("penFlags", ctypes.c_uint32), ("penMask", ctypes.c_uint32),
		("pressure", ctypes.c_uint32), ("rotation", ctypes.c_uint32), ("tiltX", ctypes.c_int32), ("tiltY", ctypes.c_int32),
	]


class _TYPE_UNION(ctypes.Union):
	_fields_ = [("touchInfo", _POINTER_TOUCH_INFO), ("penInfo", _POINTER_PEN_INFO)]


class _POINTER_TYPE_INFO(ctypes.Structure):
	_anonymous_ = ("u",)
	_fields_ = [("type", ctypes.c_uint32), ("u", _TYPE_UNION)]


class Refused(Exception):
	"""Windows did not take the touch or the pen. The text says why, for the user."""


_lock = threading.Lock()
_touchReady = False
_penDevice = None
_penTried = False


def _user32():
	return ctypes.WinDLL("user32", use_last_error=True)


def _why(code):
	if code == _ACCESS_DENIED:
		return (
			"Windows did not allow it. The window in front may belong to a program that runs with more rights than "
			"NVDA, such as one started as administrator.")
	return f"Windows refused it (error {code})."


def _readyTouch():
	"""Tell Windows once that fingers will be simulated. Raises Refused where Windows cannot do it."""
	global _touchReady
	with _lock:
		if _touchReady:
			return
		try:
			user32 = _user32()
			done = user32.InitializeTouchInjection(touch.MAX_FINGERS, _FEEDBACK_DEFAULT)
		except (AttributeError, OSError):
			raise Refused("This version of Windows cannot touch the screen for a program. It needs Windows 8 or later.")
		if not done:
			raise Refused(_why(ctypes.get_last_error()))
		_touchReady = True


def _touchFrame(points, flags, pressure):
	"""Report every finger at once: where each is, and whether they go down, move or come up."""
	_readyTouch()
	user32 = _user32()
	contacts = (_POINTER_TOUCH_INFO * len(points))()
	for number, (x, y) in enumerate(points):
		contact = contacts[number]
		contact.pointerInfo.pointerType = _PT_TOUCH
		contact.pointerInfo.pointerId = number
		contact.pointerInfo.pointerFlags = flags
		contact.pointerInfo.ptPixelLocation.x, contact.pointerInfo.ptPixelLocation.y = int(x), int(y)
		contact.touchMask = _TOUCH_MASK
		contact.rcContact.left, contact.rcContact.right = int(x) - _FINGER, int(x) + _FINGER
		contact.rcContact.top, contact.rcContact.bottom = int(y) - _FINGER, int(y) + _FINGER
		contact.orientation = 90
		contact.pressure = touch.units(pressure)
	for _again in range(4):
		if user32.InjectTouchInput(len(points), contacts):
			return
		code = ctypes.get_last_error()
		if code != _NOT_READY:
			raise Refused(_why(code))
		time.sleep(0.001)  # two reports came too close together; the same one is given again
	raise Refused(_why(_NOT_READY))


def _pen():
	"""The pen Windows lets a program hold, made once; None where this Windows has none (before Windows 10,
	version 1809)."""
	global _penDevice, _penTried
	with _lock:
		if _penTried:
			return _penDevice
		_penTried = True
		try:
			user32 = _user32()
			user32.CreateSyntheticPointerDevice.restype = ctypes.c_void_p
			user32.CreateSyntheticPointerDevice.argtypes = [ctypes.c_uint32, ctypes.c_ulong, ctypes.c_uint32]
			_penDevice = user32.CreateSyntheticPointerDevice(_PT_PEN, 1, _FEEDBACK_DEFAULT) or None
		except (AttributeError, OSError):
			_penDevice = None
		if _penDevice is None:
			log.debugWarning("VisionClaw: this Windows gives a program no pen to hold")
		return _penDevice


def penSupported():
	return _pen() is not None


def _penFrame(x, y, flags, pressure, eraser=False):
	"""Report the pen: where it is, whether it goes down, moves or comes up, and how hard it presses."""
	device = _pen()
	if device is None:
		raise Refused("This version of Windows gives a program no pen. It needs Windows 10, version 1809, or later.")
	user32 = _user32()
	user32.InjectSyntheticPointerInput.argtypes = [ctypes.c_void_p, ctypes.POINTER(_POINTER_TYPE_INFO), ctypes.c_uint32]
	info = _POINTER_TYPE_INFO()
	info.type = _PT_PEN
	pen = info.penInfo
	pen.pointerInfo.pointerType = _PT_PEN
	pen.pointerInfo.pointerId = 0
	pen.pointerInfo.pointerFlags = flags
	# The pen's place is counted from the corner of the whole desktop, as Microsoft's page says.
	pen.pointerInfo.ptPixelLocation.x = int(x) - user32.GetSystemMetrics(_VIRTUAL_LEFT)
	pen.pointerInfo.ptPixelLocation.y = int(y) - user32.GetSystemMetrics(_VIRTUAL_TOP)
	pen.penMask = _PEN_MASK_PRESSURE
	pen.penFlags = (_PEN_INVERTED | _PEN_ERASER) if eraser else 0
	pen.pressure = 0 if flags == UP else touch.units(pressure)
	if not user32.InjectSyntheticPointerInput(device, ctypes.byref(info), 1):
		raise Refused(_why(ctypes.get_last_error()))


def close():
	"""Give the pen back to Windows. Called when VisionClaw stops."""
	global _penDevice, _penTried
	with _lock:
		device, _penDevice, _penTried = _penDevice, None, False
	if device is not None:
		try:
			_user32().DestroySyntheticPointerDevice(ctypes.c_void_p(device))
		except Exception:
			log.debugWarning("VisionClaw: the pen could not be given back", exc_info=True)


def _wait(seconds, cancel):
	"""Wait a moment. Returns False when the request was stopped."""
	if cancel is not None and cancel.is_set():
		return False
	time.sleep(seconds)
	return not (cancel is not None and cancel.is_set())


def fingers(strokes, pressure=touch.PRESSURE_DEFAULT, cancel=None):
	"""Do a touch gesture: for each stroke the fingers go down at its first frame, pass through the others and
	are lifted. strokes as touch.strokes gives them. Fingers that went down always come up again.
	Raises Refused when Windows does not take it. Returns whether it was done to the end."""
	for number, stroke in enumerate(strokes):
		frames = stroke["frames"]
		if number and not _wait(touch.TAP_GAP, cancel):
			return False
		if cancel is not None and cancel.is_set():
			return False
		last, whole = frames[0], True
		_touchFrame(last, DOWN, pressure)
		try:
			for frame in frames[1:]:
				if not _wait(stroke["pace"], cancel):
					whole = False
					break
				_touchFrame(frame, MOVE, pressure)
				last = frame
			time.sleep(0.02)
		finally:
			# Lifted where they last were, as Windows asks; a finger must never stay on the screen.
			try:
				_touchFrame(last, UP, pressure)
			except Refused:
				log.debugWarning("VisionClaw: the fingers could not be lifted; Windows lifts them by itself", exc_info=True)
		if not whole:
			return False
	return True


def strokesWithPen(strokes, eraser=False, pace=touch.PACE, cancel=None, finger=False):
	"""Draw or press with the pen: each stroke is a list of (x, y, share of full pressure). finger: with one
	finger instead, which also reports how hard it presses. What went down always comes up again.
	Raises Refused when Windows does not take it. Returns whether it was done to the end."""
	def report(x, y, flags, share):
		if finger:
			_touchFrame([(x, y)], flags, share)
		else:
			_penFrame(x, y, flags, share, eraser)

	for number, points in enumerate(strokes):
		if number and not _wait(touch.TAP_GAP, cancel):
			return False
		if cancel is not None and cancel.is_set():
			return False
		last, whole = points[0], True
		report(last[0], last[1], DOWN, last[2])
		try:
			for point in points[1:]:
				if not _wait(pace, cancel):
					whole = False
					break
				report(point[0], point[1], MOVE, point[2])
				last = point
			time.sleep(0.02)
		finally:
			try:
				report(last[0], last[1], UP, last[2])
			except Refused:
				log.debugWarning("VisionClaw: the pen could not be lifted; Windows lifts it by itself", exc_info=True)
		if not whole:
			return False
	return True


class LivePen:
	"""A pen that someone holds: it goes down, is moved and pressed harder or lighter for as long as they
	want, and comes up. With no pen in this Windows, one finger stands in. Used by controller mode, where a
	trigger says how hard."""

	def __init__(self):
		self.down = False
		self._at = (0, 0)
		self._finger = False

	def press(self, x, y, share):
		"""Put the pen down, or move it and change how hard it presses. Raises Refused."""
		if not self.down:
			self._finger = not penSupported()
		flags = MOVE if self.down else DOWN
		if self._finger:
			_touchFrame([(x, y)], flags, share)
		else:
			_penFrame(x, y, flags, share)
		self.down, self._at = True, (x, y)

	def lift(self):
		"""Lift the pen where it is. Returns whether it was down. Never raises: it must come up."""
		if not self.down:
			return False
		self.down = False
		try:
			if self._finger:
				_touchFrame([self._at], UP, touch.PRESSURE_DEFAULT)
			else:
				_penFrame(self._at[0], self._at[1], UP, 0)
		except Exception:
			log.debugWarning("VisionClaw: the pen could not be lifted; Windows lifts it by itself", exc_info=True)
		return True


@contextlib.contextmanager
def nvdaTouchPaused(onMain):
	"""On a computer with a touch screen NVDA takes every touch for itself, to read what is under a finger.
	While VisionClaw touches the screen for the user, NVDA's own touch handling is put aside, with NVDA's own
	function for it, and put back afterwards whatever happens. NVDA's setting is not changed."""
	paused = False
	try:
		import touchHandler
		if getattr(touchHandler, "handler", None) is not None:
			onMain(lambda: touchHandler.setTouchSupport(False))
			paused = True
	except Exception:
		log.debugWarning("VisionClaw: NVDA's own touch handling could not be put aside", exc_info=True)
	try:
		yield paused
	finally:
		if paused:
			try:
				onMain(lambda: touchHandler.setTouchSupport(True))
			except Exception:
				log.error("VisionClaw: NVDA's own touch handling could not be put back", exc_info=True)
