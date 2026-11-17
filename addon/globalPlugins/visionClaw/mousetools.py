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
from .claw import pointer
from .claw.tools import VERBATIM, ToolError
from .engine import EngineError, prepareImage

addonHandler.initTranslation()

_LEFTDOWN, _LEFTUP, _RIGHTDOWN, _RIGHTUP = 0x0002, 0x0004, 0x0008, 0x0010
# Pauses that give a program time to notice each part of a mouse action.
_SETTLE, _DRAG_STEP, _HOLD = 0.04, 0.012, 0.08
# The size of the area around the pointer that is read or described, in pixels.
_READ_AREA, _LOOK_AREA = (320, 70), (420, 260)


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
		# Translators: Spoken when pointer mode is turned on.
		text = _(
			"Pointer mode is on. The arrow keys move the mouse pointer in this window; with Shift in small steps, "
			"with Control in large ones. Enter clicks, Shift+Enter double-clicks, the Applications key right-clicks. "
			"G holds the mouse button down, and G again lets go, for dragging. W says what is at the pointer, "
			"R reads the text there, P says where the pointer is, H repeats this help. Escape turns pointer mode off."
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
			x, y = pointer.move(self.x, self.y, command[1], command[2], box)
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
		elif name == "help":
			self.start()
		elif name == "exit":
			self.stop()

	def _area(self, box, size):
		"""A picture of the area around the pointer, kept inside the window."""
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
