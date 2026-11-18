# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a game controller as a way to work any window. When a controller is connected, VisionClaw
# notices it. In controller mode its left stick moves the mouse pointer, slowly or fast by how far it is
# pushed; its buttons click, right-click, say what is under the pointer and jump from one thing found in the
# window's picture to the next; its right trigger is the mouse button for as long as it is pulled; its left
# trigger presses like a pen, as hard as it is pulled; its right stick turns the wheel, or moves the mouse
# itself for a game that reads the mouse directly. A button can also be a hotkey of the program in front.
# Everything is said through NVDA, and nothing depends on seeing the screen.
# A controller is read through Windows' XInput, and one of another make through Windows' older joystick
# interface. The structures were read from Microsoft's own pages on 2026-11-18 (XINPUT_GAMEPAD, JOYINFOEX,
# JOYCAPSW). Reading a controller sends nothing anywhere.
# Whatever this holds down, the mouse button or the pen, comes up again: when the trigger is let go, when
# the mode is turned off, when the controller goes away, and when NVDA closes.

import ctypes
import re
import threading
import time
from ctypes import wintypes

import addonHandler
import api
import tones
import ui
import wx

from . import mousetools, touchinput
from .claw import direct, dragcontrol, gamepad, pointer, scrolling
from .claw.tools import VERBATIM
from .vclog import log

addonHandler.initTranslation()

ANNOUNCE, QUIET, OFF = "announce", "quiet", "off"
CHOICES = [ANNOUNCE, QUIET, OFF]
_NOT_CONNECTED = 1167
_JOY_RETURNALL = 0x000000FF
_JOY_HASPOV = 0x0010
_OFF_WORDS = re.compile(r"\b(off|stop|leave|exit|quit|end|disable|no more)\b", re.IGNORECASE)


class _XINPUT_GAMEPAD(ctypes.Structure):
	_fields_ = [
		("wButtons", wintypes.WORD), ("bLeftTrigger", ctypes.c_ubyte), ("bRightTrigger", ctypes.c_ubyte),
		("sThumbLX", ctypes.c_short), ("sThumbLY", ctypes.c_short), ("sThumbRX", ctypes.c_short), ("sThumbRY", ctypes.c_short),
	]


class _XINPUT_STATE(ctypes.Structure):
	_fields_ = [("dwPacketNumber", wintypes.DWORD), ("Gamepad", _XINPUT_GAMEPAD)]


class _XINPUT_VIBRATION(ctypes.Structure):
	_fields_ = [("wLeftMotorSpeed", wintypes.WORD), ("wRightMotorSpeed", wintypes.WORD)]


class _JOYINFOEX(ctypes.Structure):
	_fields_ = [(name, wintypes.DWORD) for name in (
		"dwSize", "dwFlags", "dwXpos", "dwYpos", "dwZpos", "dwRpos", "dwUpos", "dwVpos", "dwButtons", "dwButtonNumber",
		"dwPOV", "dwReserved1", "dwReserved2")]


class _JOYCAPSW(ctypes.Structure):
	_fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("szPname", ctypes.c_wchar * 32)] + [
		(name, wintypes.UINT) for name in (
			"wXmin", "wXmax", "wYmin", "wYmax", "wZmin", "wZmax", "wNumButtons", "wPeriodMin", "wPeriodMax", "wRmin",
			"wRmax", "wUmin", "wUmax", "wVmin", "wVmax", "wCaps", "wMaxAxes", "wNumAxes", "wMaxButtons")
	] + [("szRegKey", ctypes.c_wchar * 32), ("szOEMVxD", ctypes.c_wchar * 260)]


_xinputDll = None
_xinputTried = False
_joyCaps = {}


def _xinput():
	"""Windows' XInput, in whichever version this Windows has, or None."""
	global _xinputDll, _xinputTried
	if not _xinputTried:
		_xinputTried = True
		for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
			try:
				_xinputDll = ctypes.WinDLL(name)
				break
			except OSError:
				continue
	return _xinputDll


def _readXInput(index):
	"""The state of the controller in one of XInput's four places, or None when none is there."""
	dll = _xinput()
	if dll is None:
		return None
	state = _XINPUT_STATE()
	if dll.XInputGetState(index, ctypes.byref(state)) != 0:
		return None
	pad = state.Gamepad
	return gamepad.fromXInput(
		pad.wButtons, pad.bLeftTrigger, pad.bRightTrigger, pad.sThumbLX, pad.sThumbLY, pad.sThumbRX, pad.sThumbRY)


def _share(value, low, high):
	return 0.0 if high <= low else max(-1.0, min(1.0, (value - low) / (high - low) * 2 - 1))


def _readJoystick(index):
	"""The state of a controller Windows reads through its older joystick interface, or None."""
	try:
		winmm = ctypes.windll.winmm
		caps = _joyCaps.get(index)
		if caps is None:
			caps = _JOYCAPSW()
			if winmm.joyGetDevCapsW(index, ctypes.byref(caps), ctypes.sizeof(caps)) != 0:
				return None
			_joyCaps[index] = caps
		info = _JOYINFOEX()
		info.dwSize, info.dwFlags = ctypes.sizeof(_JOYINFOEX), _JOY_RETURNALL
		if winmm.joyGetPosEx(index, ctypes.byref(info)) != 0:
			_joyCaps.pop(index, None)
			return None
	except Exception:
		return None
	axes = {
		"x": _share(info.dwXpos, caps.wXmin, caps.wXmax), "y": _share(info.dwYpos, caps.wYmin, caps.wYmax),
		"z": _share(info.dwZpos, caps.wZmin, caps.wZmax), "r": _share(info.dwRpos, caps.wRmin, caps.wRmax),
	}
	pov = info.dwPOV if caps.wCaps & _JOY_HASPOV and info.dwPOV != 0xFFFF else None
	return gamepad.fromJoystick(info.dwButtons, axes, pov)


def _read(device):
	kind, index = device[0], device[1]
	return _readXInput(index) if kind == gamepad.XBOX else _readJoystick(index)


def _find(joysticks=True):
	"""The first connected controller as (kind, index, name), or None. XInput's four places first.
	joysticks: also ask Windows' older joystick interface, which takes longer to say that nothing is there."""
	for index in range(4):
		if _readXInput(index) is not None:
			return (gamepad.XBOX, index, "")
	if not joysticks:
		return None
	try:
		count = min(16, ctypes.windll.winmm.joyGetNumDevs())
	except Exception:
		count = 0
	for index in range(count):
		if _readJoystick(index) is not None:
			return (gamepad.OTHER, index, "")
	return None


def _vibrate(device, left, right):
	"""Turn a controller's two motors on, from 0 to 1 each, or off. Windows may leave them off for a program
	that is not in front; nothing depends on them."""
	if device is None or device[0] != gamepad.XBOX or _xinput() is None:
		return
	try:
		_xinput().XInputSetState(device[1], ctypes.byref(_XINPUT_VIBRATION(int(left * 65535), int(right * 65535))))
	except Exception:
		pass


class Controller:
	"""Notices a connected game controller and, in controller mode, works the mouse pointer with it."""

	def __init__(self, plugin, setting):
		self._plugin = plugin
		# How the user wants a controller treated: ANNOUNCE, QUIET or OFF. A function, read again at every look.
		self._setting = setting
		self.device = None
		self.active = False
		self._stopped = threading.Event()
		self._thread = None
		self._follower = gamepad.Follower()
		self._carry, self._wheel, self._look = gamepad.Carry(), gamepad.Carry(), gamepad.Carry()
		self._pen = touchinput.LivePen()
		self._penRefused = False
		self._trigger = False
		# Whether the right stick moves the mouse itself instead of turning the wheel.
		self.looking = False
		self._box, self._scale, self._app = None, 1.0, ""
		self._refreshed = 0.0
		self._moving = self._atEdge = False
		self._movedAt = 0.0
		self._under = ""
		self._buzzEnd = 0.0
		self._result, self._item = None, -1
		self._last = self._clock = 0.0
		self._searches = 0

	# --- Noticing a controller ---

	def start(self):
		self._thread = threading.Thread(target=self._loop, name="visionClaw-controller", daemon=True)
		self._thread.start()

	def stop(self):
		"""When NVDA closes: let go of everything and stop looking."""
		self._stopped.set()
		self._release()
		_vibrate(self.device, 0, 0)

	def _loop(self):
		while not self._stopped.is_set():
			try:
				wait = self.look()
			except Exception:
				# Nothing here may ever reach NVDA; a fault is written down and the look is tried again.
				log.error("VisionClaw: reading the game controller failed", exc_info=True)
				wait = 1.0
			self._stopped.wait(wait)

	def look(self, now=None):
		"""One look: whether a controller is there, and what it does. Returns how long to wait until the next."""
		now = time.monotonic() if now is None else now
		if self._setting() == OFF:
			if self.device is not None:
				self._gone(say=False)
			return gamepad.SEARCH_EVERY
		if self.device is None:
			# The older joystick interface is asked only every fourth time: it is slow to say that nothing is there.
			self._searches += 1
			found = _find(joysticks=self._searches % 4 == 1)
			if found is None:
				return gamepad.SEARCH_EVERY
			self._come(found)
			self._last = now
		state = _read(self.device)
		if state is None:
			self._gone()
			return gamepad.SEARCH_EVERY
		self._tick(state, now, max(0.0, min(0.1, now - self._last)))
		self._last = now
		return gamepad.LOOK_EVERY

	def _come(self, found):
		self.device = found
		self._follower = gamepad.Follower()
		log.info(f"VisionClaw: a game controller is connected ({found[0]}, place {found[1]}).")
		if self._setting() == ANNOUNCE:
			wx.CallAfter(ui.message, gamepad.CONNECTED.format(kind=gamepad.kindText(found[0], found[2])))

	def _gone(self, say=True):
		wasOn = self.active
		self.device = None
		self._release()
		self.active = False
		log.info("VisionClaw: the game controller is gone.")
		if say and wasOn:
			# Translators: Spoken when the game controller is unplugged or switched off while controller mode is on.
			wx.CallAfter(ui.message, _("The game controller is gone. Controller mode is off."))
		elif say and self._setting() == ANNOUNCE:
			# Translators: Spoken when the game controller is unplugged or switched off.
			wx.CallAfter(ui.message, _("The game controller is gone."))

	def _release(self):
		"""Let go of the mouse button and lift the pen, if this holds them. Safe from any thread."""
		if self._trigger:
			self._trigger = False
			mousetools.release()
			self._plugin.pointerMode.holding = False
		self._pen.lift()

	def describe(self):
		"""What is connected and whether controller mode is on, in sentences. Looks once if nothing is known."""
		if self._setting() == OFF:
			return (
				"Game controllers are switched off in VisionClaw's settings, so VisionClaw does not look for one. "
				"The setting is called Game controller.")
		device = self.device or _find()
		if device is None:
			return (
				"No game controller is connected, as far as Windows reports. An Xbox controller, or one that Windows reads "
				"the same way, is noticed a few seconds after it is plugged in or switched on.")
		lines = [f"A game controller is connected: {gamepad.kindText(device[0], device[2])}."]
		if self.active:
			lines.append("Controller mode is on.")
		else:
			lines.append(
				"Controller mode is off. Hold the controller's View and Menu buttons together for a second, or press "
				"NVDA+Alt+J, to work the mouse pointer with it.")
		keys = [line for line in self._plugin.helpers.listText().splitlines() if "game controller" in line]
		if keys:
			lines.append("Buttons that are hotkeys: " + " ".join(keys))
		return " ".join(lines)

	# --- Controller mode ---

	def toggle(self):
		"""Turn controller mode on or off. Main thread."""
		if self.active:
			self.turnOff()
		else:
			self.turnOn()

	def turnOn(self):
		"""Main thread. Returns what was said."""
		if self._setting() == OFF:
			# Translators: Spoken when controller mode is asked for and game controllers are switched off in the settings.
			text = _("Game controllers are switched off in VisionClaw's settings.")
			ui.message(text)
			return text
		if self.device is None:
			self.device = _find()
		if self.device is None:
			# Translators: Spoken when controller mode is asked for and no game controller is connected.
			text = _("No game controller is connected, as far as Windows reports.")
			ui.message(text)
			return text
		mode = self._plugin.pointerMode
		try:
			mode.place()
		except Exception:
			log.error("VisionClaw: controller mode could not start", exc_info=True)
			# Translators: Spoken when controller mode could not be turned on.
			text = _("Controller mode could not be turned on in this window.")
			ui.message(text)
			return text
		self._refresh()
		self._carry.clear(), self._wheel.clear(), self._look.clear()
		self.looking = mode.direct == direct.VIEW
		self._result, self._item, self._under = None, -1, ""
		self._follower.disarm()
		self.active = True
		ui.message(gamepad.HELP)
		return gamepad.HELP

	def turnOff(self, say=True):
		"""Main thread."""
		wasOn, self.active = self.active, False
		self._release()
		_vibrate(self.device, 0, 0)
		mode = self._plugin.pointerMode
		if not mode.active:
			mode.leaveWay()
		self._follower.disarm()
		if say and wasOn:
			# Translators: Spoken when controller mode is turned off.
			ui.message(_("Controller mode is off."))

	def _refresh(self):
		"""Which window is in front, how large it is and how its screen is scaled. Main thread."""
		try:
			mode = self._plugin.pointerMode
			self._box = mode._box()
			self._scale = mousetools.scaleAt(mode.x, mode.y)
			app = mousetools.appNow()
			if app != self._app:
				self._app, self._result, self._item = app, None, -1
		except Exception:
			self._box = None

	def _buzz(self, pattern):
		left, right, seconds = pattern
		_vibrate(self.device, left, right)
		self._buzzEnd = self._clock + seconds

	def _tick(self, state, now, passed):
		"""One look at the controller. The controller's own thread."""
		self._clock = now
		for event in self._follower.update(state, now):
			if event[0] == "chord":
				self._follower.disarm()
				wx.CallAfter(self.toggle)
			elif event[0] == "down":
				wx.CallAfter(self._pressed, event[1], self._follower.held)
			elif event[1] == gamepad.RT and self._trigger:
				self._trigger = False
				mousetools.release()
				self._plugin.pointerMode.holding = False
				# Translators: Spoken in controller mode when the right trigger is let go and the mouse button comes up.
				wx.CallAfter(ui.message, _("Let go."))
		if self._buzzEnd and now >= self._buzzEnd:
			self._buzzEnd = 0.0
			_vibrate(self.device, 0, 0)
		if not self.active:
			return
		if now - self._refreshed > 0.5:
			self._refreshed = now
			wx.CallAfter(self._refresh)
		box = self._box
		if box is None:
			return
		mode = self._plugin.pointerMode
		held = self._follower.held
		sx, sy = gamepad.stick(state.lx, state.ly)
		if sx or sy:
			factor = gamepad.pace(held)
			if mode.direct == direct.VIEW:
				# Nothing points anywhere: the stick moves the mouse itself.
				dx, dy = self._carry.add(*gamepad.glide(
					sx, sy, passed, 1.0, factor * self._plugin.appWays.speed(self._app), gamepad.LOOK_RATE))
				if dx or dy:
					mousetools._relative(dx, dy)
			else:
				dx, dy = self._carry.add(*gamepad.glide(sx, sy, passed, self._scale, factor))
				if dx or dy:
					x, y = pointer.clamp(mode.x + dx, mode.y + dy, box)
					edge = (x, y) != (mode.x + dx, mode.y + dy)
					mode.x, mode.y = x, y
					mousetools.moveTo(x, y)
					if edge and not self._atEdge:
						# The window's edge is felt and heard.
						self._buzz(gamepad.BUZZ_EDGE)
						tones.beep(180, 25)
					self._atEdge = edge
			self._moving, self._movedAt = True, now
		elif self._moving and now - self._movedAt > 0.3:
			self._moving = False
			self._carry.clear()
			if mode.direct != direct.VIEW:
				wx.CallAfter(self._sayUnder, False)
		# The left trigger presses like a pen, as hard as it is pulled.
		if state.lt >= gamepad.TRIGGER_ON or (self._pen.down and state.lt > gamepad.TRIGGER_OFF):
			share = max(0.02, min(1.0, (state.lt - gamepad.TRIGGER_OFF) / (1 - gamepad.TRIGGER_OFF)))
			if not self._penRefused:
				first = not self._pen.down
				try:
					self._pen.press(mode.x, mode.y, share)
					if first:
						# Translators: Spoken in controller mode when the left trigger puts the pen down.
						wx.CallAfter(ui.message, _("Pen down."))
				except touchinput.Refused as e:
					self._penRefused = True
					wx.CallAfter(ui.message, str(e))
		else:
			self._penRefused = False
			if self._pen.lift():
				# Translators: Spoken in controller mode when the left trigger is let go and the pen is lifted.
				wx.CallAfter(ui.message, _("Pen up."))
		# The right stick turns the wheel, or moves the mouse itself.
		rx, ry = gamepad.stick(state.rx, state.ry)
		if not (rx or ry):
			self._wheel.clear(), self._look.clear()
		elif self.looking:
			dx, dy = self._look.add(*gamepad.glide(
				rx, ry, passed, 1.0, gamepad.pace(held) * self._plugin.appWays.speed(self._app), gamepad.LOOK_RATE))
			if dx or dy:
				mousetools._relative(dx, dy)
		else:
			across, down = self._wheel.add(rx * gamepad.WHEEL_RATE * passed, ry * gamepad.WHEEL_RATE * passed)
			for count, direction in ((down, scrolling.DOWN if down > 0 else scrolling.UP), (across, scrolling.RIGHT if across > 0 else scrolling.LEFT)):
				for _notch in range(abs(count)):
					flag = mousetools._WHEEL if direction in (scrolling.UP, scrolling.DOWN) else mousetools._HWHEEL
					mousetools._wheel(flag, scrolling.wheelAmount(direction, 1))

	def _pressed(self, button, held):
		"""A button went down. Main thread."""
		try:
			# A button that is a hotkey of the program in front does that, in controller mode or out of it.
			if self._plugin.helpers.runPad(button):
				return
			if not self.active:
				return
			mode = self._plugin.pointerMode
			if button == gamepad.RT:
				if not self._trigger:
					if mode.direct != direct.VIEW:
						mousetools.moveTo(mode.x, mode.y)
					mousetools.press()
					self._trigger = mode.holding = True
					# Translators: Spoken in controller mode when the right trigger presses the mouse button down.
					ui.message(_("Holding."))
				return
			command = gamepad.commandFor(button, held)
			if command is not None:
				self._do(command)
		except Exception:
			log.error("VisionClaw: a button of the game controller failed", exc_info=True)

	def _do(self, command):
		"""Carry out what a button means. Main thread."""
		mode = self._plugin.pointerMode
		keys = self._plugin.controlKeys
		name = command[0]
		if name == "exit":
			if keys.active:
				keys.stop()  # the first press gives a held dial back; the second leaves the mode
				return
			self.turnOff()
		elif name == "help":
			ui.message(gamepad.HELP)
		elif name == "move" and keys.active:
			# A dial or slider is held: the direction pad works it, as the arrow keys do.
			size = dragcontrol.FINE if command[2] == pointer.FINE else dragcontrol.STEP
			keys._run(("turn", 1 if command[1] in ("up", "right") else -1, size))
		elif name == "what":
			self._sayUnder(True)
		elif name == "stick":
			self.looking = not self.looking
			# Translators: Spoken in controller mode when the right stick changes between the wheel and moving the mouse itself.
			ui.message(_(
				"The right stick now moves the mouse itself, for a game that reads the mouse directly."
			) if self.looking else _("The right stick now turns the mouse wheel."))
		elif name == "item":
			self._step(command[1])
		elif name == "items":
			self._result, self._item = None, -1
			self._step(0)
		else:
			mode.onEdge = lambda: self._buzz(gamepad.BUZZ_EDGE)
			mode._run(command)
			if name == "way":
				self.looking = mode.direct == direct.VIEW

	def _sayUnder(self, asked):
		"""Say what NVDA finds under the pointer: when the stick comes to rest, if it is something else than
		before, and whenever Y asks. Main thread."""
		mode = self._plugin.pointerMode
		text = ""
		try:
			obj = api.getDesktopObject().objectFromPoint(mode.x, mode.y)
			name = " ".join(str(getattr(obj, "name", "") or "").split())[:120]
			kind = str(getattr(getattr(obj, "role", None), "displayString", "") or "")
			text = ", ".join(part for part in (name, kind) if part)
		except Exception:
			log.debugWarning("VisionClaw: what is under the pointer could not be asked", exc_info=True)
		if asked:
			# Translators: Spoken in controller mode when NVDA can name nothing under the mouse pointer.
			ui.message(text or _(
				"NVDA can name nothing here. With the left shoulder button held, Y reads the text here; with the right "
				"one held, Y has the picture here described."))
			self._under = text
		elif text and text != self._under:
			self._under = text
			self._buzz(gamepad.BUZZ_OTHER)
			ui.message(text)

	def _step(self, step):
		"""Jump to the next or the previous thing found in the window, and say its name. Main thread."""
		if self._result is None:
			# Translators: Spoken in controller mode while the window is looked at for things to jump to.
			ui.message(_("Looking at the window."))
			threading.Thread(target=self._list, args=(step,), name="visionClaw-controller-items", daemon=True).start()
			return
		items = self._result.items
		if not items:
			# Translators: Spoken in controller mode when nothing was found in the window to jump to.
			ui.message(_("Nothing was found in this window."))
			return
		self._item = (self._item + (step or 1)) % len(items)
		item = items[self._item]
		try:
			point = self._plugin.clawScreen.pointOf(self._result, item)
		except Exception:
			point = None
		if point is None:
			# Translators: Spoken in controller mode when a thing's place on the screen is not known. {name} is the thing.
			ui.message(_("{name}. Where it is on the screen is not known.").format(name=item["text"]))
			return
		mode = self._plugin.pointerMode
		box = self._box or mode._box()
		mode.x, mode.y = pointer.clamp(point[0], point[1], box)
		if mode.direct != direct.VIEW:
			mousetools.moveTo(mode.x, mode.y)
		self._under = ""
		# Translators: Spoken in controller mode when the pointer jumped to a thing. {name} is the thing, {at} and {of} count them.
		ui.message(_("{name}, {at} of {of}").format(name=item["text"], at=self._item + 1, of=len(items)))

	def _list(self, step):
		try:
			result = self._plugin.clawScreen.items()
		except Exception:
			log.error("VisionClaw: the window could not be listed for the game controller", exc_info=True)
			# Translators: Spoken in controller mode when the window could not be looked at.
			wx.CallAfter(ui.message, _("VisionClaw could not read this window."))
			return
		self._result, self._item = result, -1 if step >= 0 else 0
		wx.CallAfter(self._step, step)


def register(add, plugin, text):
	"""Add the tools about a game controller. Called from nvdatools.build."""

	def info(task):
		words = task.request.lower()
		said = plugin.controller.describe()
		if any(word in words for word in ("button", "stick", "trigger", "help", "how", "what do", "what does", "use")):
			return said + " " + gamepad.HELP.replace("Controller mode is on. ", "In controller mode: ", 1)
		return said + " Ask what the buttons do, and VisionClaw says all of them."

	add("controller_info",
		"say whether a game controller, gamepad or joystick is connected, whether controller mode is on, and what "
		"its sticks, buttons and triggers do in controller mode",
		info, looks=True, title="Checking the game controller", tell=VERBATIM)

	def mode(task, turn):
		def work():
			if turn == "off":
				wasOn = plugin.controller.active
				plugin.controller.turnOff()
				return "Controller mode is off." if wasOn else "Controller mode was not on."
			if plugin.controller.active:
				return "Controller mode is already on. The controller's Menu button says what its buttons do."
			return plugin.controller.turnOn()
		return mousetools._onMain(work)

	add("controller_mode",
		"turn controller mode on or off: with it on, a connected game controller works the mouse pointer in any "
		"window, with its sticks, buttons and triggers",
		mode, {
			"turn": text("on or off", enum=["on", "off"], auto=lambda part: "off" if _OFF_WORDS.search(part or "") else "on"),
		}, title="Controller mode", tell=VERBATIM)

