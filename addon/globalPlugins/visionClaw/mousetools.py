# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the mouse, from the keyboard. Sighted people click, right-click, double-click and drag on
# controls that give a screen reader nothing to hold on to. Here are those actions as functions; the tools
# that let the models use them on an item found in a window's picture; and pointer mode, in which the arrow
# keys move the pointer inside the window, so that any control at all can be worked without a mouse.
# The mouse is moved through Windows itself, so nothing here depends on a part of NVDA that may change.

import ctypes
import threading
import time
from ctypes import wintypes

import addonHandler
import api
import tones
import ui
import wx
from logHandler import log

from . import ocr
from .claw import pointer, scrolling
from .claw.tools import VERBATIM, ToolError
from .engine import EngineError, prepareImage

addonHandler.initTranslation()

_LEFTDOWN, _LEFTUP, _RIGHTDOWN, _RIGHTUP = 0x0002, 0x0004, 0x0008, 0x0010
_WHEEL, _HWHEEL = 0x0800, 0x1000
# Pauses that give a program time to notice each part of a mouse action.
_SETTLE, _DRAG_STEP, _HOLD = 0.04, 0.012, 0.08
# Between the notches of the wheel, and before looking at what a scroll did.
_WHEEL_STEP, _SCROLL_SETTLE = 0.012, 0.35
# The size of the area around the pointer that is read or described, on a plain screen at 100 percent.
_READ_AREA, _LOOK_AREA = (320, 70), (420, 260)
# Kinds of control whose value the wheel changes when the pointer is over them. Never scrolled by accident.
_WHEEL_CHANGES = ("SLIDER", "COMBOBOX", "SPINBUTTON", "TAB", "TABCONTROL", "DROPDOWNBUTTON")


def position():
	point = wintypes.POINT()
	ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
	return point.x, point.y


def moveTo(x, y):
	ctypes.windll.user32.SetCursorPos(int(x), int(y))


def _button(flag):
	ctypes.windll.user32.mouse_event(flag, 0, 0, 0, 0)


def press():
	_button(_LEFTDOWN)


def release():
	_button(_LEFTUP)


def _wheel(flag, amount):
	ctypes.windll.user32.mouse_event(flag, 0, 0, amount, 0)


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


def wheel(x, y, direction, notches):
	"""Turn the mouse wheel with the pointer at a point of the screen, one notch at a time as a hand does:
	some programs take no notice of one large turn. Leaves the pointer there."""
	moveTo(x, y)
	time.sleep(_SETTLE)
	flag = _WHEEL if direction in (scrolling.UP, scrolling.DOWN) else _HWHEEL
	amount = scrolling.wheelAmount(direction, 1)
	for _ in range(max(1, min(scrolling.MAX_NOTCHES, notches))):
		_wheel(flag, amount)
		time.sleep(_WHEEL_STEP)


def scrollView(grab, box, point, direction, notches, toEnd=False, cancel=None):
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
		wheel(point[0], point[1], direction, notches)
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


def click(x, y, action=pointer.CLICK):
	"""Do one mouse action at a point of the screen. Leaves the pointer there."""
	moveTo(x, y)
	time.sleep(_SETTLE)
	if action == pointer.HOVER:
		return
	if action == pointer.RIGHT:
		_button(_RIGHTDOWN)
		_button(_RIGHTUP)
		return
	for _ in range(2 if action == pointer.DOUBLE else 1):
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


class PointerMode:
	"""While it is on, the arrow keys move the mouse pointer inside the window in front, and other keys click,
	right-click, double-click, hold and let go for dragging, and say what is under the pointer."""

	def __init__(self, plugin):
		self._plugin = plugin
		self.active = False
		self.holding = False
		self.x = self.y = 0
		self.scale = 1.0
		self._bar = -1

	def _box(self):
		loc = self._plugin.windowBox(api.getForegroundObject())
		return (loc.left, loc.top, loc.left + loc.width, loc.top + loc.height)

	def start(self):
		"""Turn pointer mode on. Returns what was said, so a tool can pass it on. Main thread."""
		box = self._box()
		self.x, self.y = pointer.centre(box)
		try:
			# Start on the focused control, where it has a place inside the window.
			loc = api.getFocusObject().location
			if loc and loc.width > 0 and loc.height > 0:
				self.x, self.y = pointer.clamp(loc.left + loc.width // 2, loc.top + loc.height // 2, box)
		except Exception:
			pass
		moveTo(self.x, self.y)
		self.active, self.holding = True, False
		# Steps and areas follow the scaling of the monitor the window is on.
		self.scale = scaleAt(self.x, self.y)
		# Translators: Spoken when pointer mode is turned on.
		text = _(
			"Pointer mode is on. The arrow keys move the mouse pointer in this window; with Shift in small steps, "
			"with Control in large ones. Enter clicks, Shift+Enter double-clicks, the Applications key right-clicks. "
			"G holds the mouse button down, and G again lets go, for dragging. Page Down and Page Up turn the mouse "
			"wheel about a page; with Shift one notch, with Control sideways. S finds the scrollbars and puts the "
			"pointer on one. D tries what is under the pointer as a dial or slider: it turns the wheel on it and drags "
			"it a little, and then the arrow keys work it. W says what is at the pointer, R reads the text there, "
			"P says where the pointer is, H repeats this help. Escape turns pointer mode off."
		)
		ui.message(text)
		return text

	def stop(self, say=True):
		if self.holding:
			release()
		wasOn, self.active, self.holding = self.active, False, False
		if say and wasOn:
			# Translators: Spoken when pointer mode is turned off.
			ui.message(_("Pointer mode is off."))

	def toggle(self):
		self.stop() if self.active else self.start()

	def scriptFor(self, gesture):
		"""The pointer mode command for a pressed key, as a script, or None."""
		if not self.active:
			return None
		for identifier in gesture.normalizedIdentifiers:
			command = pointer.KEYS.get(identifier)
			if command is not None:
				def script_pointerMode(gesture, command=command):
					self._run(command)
				return script_pointerMode
		return None

	def _run(self, command):
		try:
			box = self._box()
		except Exception:
			self.stop()
			return
		name = command[0]
		if name == "move":
			x, y = pointer.move(self.x, self.y, command[1], pointer.stepFor(command[2], box, self.scale), box)
			atEdge = (x, y) == (self.x, self.y)
			self.x, self.y = x, y
			moveTo(x, y)
			# A short tone says how high the pointer is; a low one that it is at the edge.
			tones.beep(180 if atEdge else pointer.pitch(y, box), 25)
		elif name == "centre":
			self.x, self.y = pointer.centre(box)
			moveTo(self.x, self.y)
			ui.message(pointer.where(self.x, self.y, box))
		elif name in ("click", "double", "right"):
			if self.holding:
				release()
				self.holding = False
			action = {"click": pointer.CLICK, "double": pointer.DOUBLE, "right": pointer.RIGHT}[name]
			threading.Thread(target=click, args=(self.x, self.y, action), daemon=True).start()
			# Translators: Spoken in pointer mode after a mouse action. One of: click, double click, right click.
			ui.message({"click": _("click"), "double": _("double click"), "right": _("right click")}[name])
		elif name == "grab":
			if self.holding:
				release()
				self.holding = False
				# Translators: Spoken in pointer mode when the mouse button is let go after dragging.
				ui.message(_("Let go."))
			else:
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
			threading.Thread(
				target=self._scroll, args=(box, command[1], pointer.notchesFor(command[2])), daemon=True).start()
		elif name == "take":
			self._plugin.controlKeys.takeAtPointer()
		elif name == "bars":
			threading.Thread(target=self._bars, args=(box,), daemon=True).start()
		elif name == "help":
			self.start()
		elif name == "exit":
			self.stop()

	def _scroll(self, box, direction, notches):
		"""Turn the wheel at the pointer, and say where the view now stands, or that it did not move."""
		try:
			moved, _done, picture = scrollView(self._plugin._grab, box, (self.x, self.y), direction, notches)
		except Exception:
			log.debugWarning("VisionClaw: could not scroll at the pointer", exc_info=True)
			# Translators: Spoken in pointer mode when scrolling was not possible.
			wx.CallAfter(ui.message, _("Scrolling did not work here."))
			return
		if not moved:
			# Translators: Spoken in pointer mode when turning the wheel moved nothing.
			wx.CallAfter(ui.message, _("Nothing moved. This is the end, or nothing scrolls under the pointer."))
			return
		bar = _barFor(picture, self.scale, direction)
		# Translators: Spoken in pointer mode after scrolling when no scrollbar shows how far. {direction} is up, down, left or right.
		wx.CallAfter(ui.message, scrolling.positionText(bar) if bar else _("Scrolled {direction}.").format(direction=direction))

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
				"No scrollbar was found in this window's picture. Page Down and Page Up still turn the wheel."))
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
		"to the end; says whether anything moved and how far along the view now stands",
		scrollTool, {
			"direction": text("which way to scroll", enum=scrolling.DIRECTIONS, auto=scrolling.directionOf),
			"asked": text("what the user asked for, in their own words, with how far to scroll", maxLength=300, auto=True),
		}, changes=True, title="Scrolling")

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
