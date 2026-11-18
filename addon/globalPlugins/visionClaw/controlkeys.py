# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - arrow keys for a control that a sighted person drags: a dial, a knob, a custom slider, a lever
# in a game. VisionClaw takes hold of the control, and from then on the arrow keys work it until Escape.
# It is worked through Windows itself where the program offers its value, else with the mouse wheel, else by
# dragging up and down, sideways or around in a circle; which of these works is found out by trying each and
# comparing the control's picture before and after. After every key press the user is told what happened:
# the text near the control that changed, or that it moved, or that nothing moved.
# A control can be kept under a hotkey for its program. What is kept is data: a name or a place as a share of
# the window, and the way it is worked. No code is written for it.

import re
import threading
import time

import addonHandler
import api
import config
import tones
import ui
import wx
from .vclog import log

from . import deepquery, fixruntime, mousetools, ocr
from .claw import audit, dragcontrol, fixes, match, pointer, scrolling, working
from .claw.fixmatch import hostOf, matches
from .claw.tools import VERBATIM, ToolError
from .engine import prepareImage

addonHandler.initTranslation()

# After the mouse did something, before the control is looked at again.
_LOOK_SETTLE = 0.25
_KIND_WORDS = re.compile(r"\b(the|this|that|a|an|my|dial|knob|slider|fader|control|lever|wheel|custom|inaccessible)\b", re.IGNORECASE)
_FOCUSED = re.compile(r"\b(focused|this|current|that)\s+(control|slider|dial|knob|fader|one|thing|item)\b", re.IGNORECASE)


def _strokeAlong(path):
	"""Press the mouse button at the first point, move through the others, and let go."""
	mousetools.moveTo(*path[0])
	time.sleep(mousetools._SETTLE)
	mousetools.press()
	try:
		time.sleep(mousetools._HOLD)
		for point in path[1:]:
			mousetools.moveTo(*point)
			time.sleep(mousetools._DRAG_STEP)
		time.sleep(mousetools._HOLD)
	finally:
		mousetools.release()  # the button must never stay down


def newControl(name, kind, point, box, radius=None, obj=None, find=None, method=None, site=""):
	"""A control to take hold of, as plain data. Its place is kept as a share of the window."""
	return {
		"name": " ".join(str(name or "").split())[:60], "kind": kind or "control", "method": method,
		"share": dragcontrol.shareOf(point, box), "radius": radius, "follows": None, "obj": obj, "find": find,
		"site": site,
	}


class ControlKeys:
	"""While a control is held, the arrow keys work it."""

	def __init__(self, plugin):
		self._plugin = plugin
		self.active = False
		self.control = None
		self.scale = 1.0
		self._lock = threading.Lock()
		self._halt = threading.Event()
		self._old = self._leaving = None
		self._seen = None
		self._lines = None
		self._valueText = ""

	def _box(self):
		loc = self._plugin.windowBox(api.getForegroundObject())
		return (loc.left, loc.top, loc.left + loc.width, loc.top + loc.height)

	@staticmethod
	def _say(text):
		wx.CallAfter(ui.message, text)

	# --- Taking hold and letting go ---

	def take(self, control, say=True, old=None):
		"""Take hold of a control whose way of working is known. Main thread. Returns what is said."""
		self.stop(say=False)
		box = self._box()
		self.control = control
		self._halt.clear()
		self._seen = self._lines = None
		point = dragcontrol.pointOf(control["share"], box)
		self.scale = mousetools.scaleAt(*point)
		self._old = old or mousetools.position()
		if control.get("method") != dragcontrol.VALUE:
			mousetools.moveTo(*point)
		self.active = True
		text = dragcontrol.helpText(control.get("name"), control.get("kind"), control.get("method"))
		if say:
			ui.message(text)
		# The text near the control as it is now, so that the first key press can say what changed.
		if self._lock.acquire(False):
			threading.Thread(target=self._work, args=(self._prime, box), daemon=True).start()
		return text

	def stop(self, say=True):
		wasOn, self.active = self.active, False
		self._halt.set()
		old, self._old = self._old, None
		if wasOn:
			self._remember()
			if old is not None and (self.control or {}).get("method") != dragcontrol.VALUE:
				# The pointer goes back where it was; if the mouse is still at work, when that is finished.
				if self._lock.acquire(False):
					mousetools.moveTo(*old)
					self._lock.release()
				else:
					self._leaving = old
			if say:
				# Translators: Spoken when the arrow keys stop working a dial or slider.
				ui.message(_("The arrow keys are yours again."))

	def _remember(self):
		"""A kept control remembers how it is worked and, if it moves when dragged, where it now is."""
		control = self.control or {}
		saved = control.get("saved")
		if saved:
			self._plugin.helpers.patch(saved[0], saved[1], {
				"method": control.get("method"), "follows": control.get("follows"), "share": list(control["share"])})

	def scriptFor(self, gesture):
		"""The command for a pressed key while a control is held, as a script, or None."""
		if not self.active:
			return None
		for identifier in gesture.normalizedIdentifiers:
			command = dragcontrol.KEYS.get(identifier)
			if command is not None:
				def script_controlKeys(gesture, command=command):
					self._run(command)
				return script_controlKeys
		return None

	def _run(self, command):
		name = command[0]
		if name == "exit":
			self.stop()
			return
		control = self.control or {}
		if name == "help":
			ui.message(dragcontrol.helpText(control.get("name"), control.get("kind"), control.get("method")))
			return
		if name == "keep":
			ui.message(self.keep())
			return
		try:
			box = self._box()
		except Exception:
			self.stop()
			return
		target = {"turn": self._turn, "end": self._toEnd, "read": self._read, "look": self._look, "method": self._nextMethod}[name]
		if not self._lock.acquire(False):
			self._halt.set()  # a key pressed during a long run stops the run
			return
		self._halt.clear()
		threading.Thread(target=self._work, args=(target, box) + tuple(command[1:]), daemon=True).start()

	def _work(self, target, box, *args):
		try:
			target(box, *args)
		except Exception:
			log.error("VisionClaw: working a control failed", exc_info=True)
			# Translators: Spoken when a key that works a dial or slider failed.
			self._say(_("That did not work here."))
		finally:
			leaving, self._leaving = self._leaving, None
			if leaving is not None:
				mousetools.moveTo(*leaving)
			self._lock.release()

	def busy(self):
		return self._lock.locked()

	# --- The work itself. These run on a worker thread. ---

	def _stroke(self, box, direction, size):
		"""Work the control one step and look whether it changed. Says nothing. Returns whether it changed."""
		control = self.control
		method = control.get("method")
		if method == dragcontrol.VALUE:
			moved, self._valueText = mousetools._onMain(lambda: deepquery.turn(control.get("obj"), direction, size))
			return moved
		grab = self._plugin._grab
		point = dragcontrol.pointOf(control["share"], box)
		side = scrolling.pixels(dragcontrol.SPOT, self.scale)
		spot = dragcontrol.around(point, side, box)
		if self._seen is not None and self._seen[0] == spot:
			before = self._seen[1]
		else:
			mousetools.moveTo(*point)
			time.sleep(_LOOK_SETTLE)  # anything that lights up under the pointer has done so before the first look
			before = grab(spot)
		last = point
		if method == dragcontrol.WHEEL:
			mousetools.wheel(point[0], point[1], scrolling.UP if direction > 0 else scrolling.DOWN, dragcontrol.notches(size))
		else:
			offsets = dragcontrol.stroke(method, direction, size, self.scale, control.get("radius"))
			path = [pointer.clamp(point[0] + dx, point[1] + dy, box) for dx, dy in offsets]
			_strokeAlong(path)
			last = path[-1]
			mousetools.moveTo(*point)
		time.sleep(_LOOK_SETTLE)
		after = grab(spot)
		moved = dragcontrol.changed(before, after) >= dragcontrol.CHANGED
		if moved and method in (dragcontrol.UPDOWN, dragcontrol.SIDEWAYS) and last != point:
			if control.get("follows") is None and size != dragcontrol.FINE:
				# Did the thing that was pressed go along with the mouse, as a slider's thumb does? Then it looks
				# at its new place as it looked at the old one, and the next press must be there.
				there = dragcontrol.around(last, side, box)
				control["follows"] = dragcontrol.changed(before, grab(there)) < dragcontrol.CHANGED
			if control.get("follows"):
				control["share"] = dragcontrol.shareOf(last, box)
				mousetools.moveTo(*last)
				self._seen = None
				return True
		self._seen = (spot, after)
		return moved

	def _readLines(self, box):
		"""The lines of text shown around the control."""
		if not config.conf["visionClaw"]["useOcr"]:
			return []
		point = dragcontrol.pointOf(self.control["share"], box)
		area = dragcontrol.around(point, tuple(scrolling.pixels(size, self.scale) for size in dragcontrol.AREA), box)
		try:
			return [line for line in ocr.rowsText(ocr.recognize(self._plugin._grab(area))).splitlines() if line.strip()]
		except Exception:
			log.debugWarning("VisionClaw: the text at a control could not be read", exc_info=True)
			return []

	def _prime(self, box):
		if self.control.get("method") != dragcontrol.VALUE:
			self._lines = self._readLines(box)

	def _shown(self, box):
		"""What the control shows now that it did not show before."""
		if self.control.get("method") == dragcontrol.VALUE:
			return self._valueText
		lines = self._readLines(box)
		fresh = dragcontrol.newText(self._lines, lines) if self._lines is not None else ""
		self._lines = lines
		return fresh

	def _turn(self, box, direction, size):
		if not self._stroke(box, direction, size):
			tones.beep(180, 40)
			# Translators: Spoken when an arrow key did not change a dial or slider.
			self._say(_("Nothing moved. It may be at its end, or it is not worked this way: M tries another way."))
			return
		tones.beep(900 if direction > 0 else 500, 25)
		# Translators: Spoken after an arrow key turned a dial or slider when no new text is shown at it.
		self._say(self._shown(box) or (_("Up.") if direction > 0 else _("Down.")))

	def _toEnd(self, box, direction):
		count = 0
		while count < dragcontrol.MAX_END_STROKES and self.active and not self._halt.is_set():
			if not self._stroke(box, direction, dragcontrol.FAR):
				break
			count += 1
		if not count:
			tones.beep(180, 40)
			# Translators: Spoken when Home or End did not move a dial or slider.
			self._say(_("Nothing moved. It is at that end already, or it is not worked this way."))
			return
		shown = self._shown(box)
		if self._halt.is_set():
			# Translators: Spoken when going to the end of a dial or slider was stopped by a key.
			self._say(_("Stopped. {shown}").format(shown=shown).strip())
		else:
			# Translators: Spoken when a dial or slider was moved until it moved no more.
			self._say(_("At the end. {shown}").format(shown=shown).strip())

	def _read(self, box):
		control = self.control
		if control.get("method") == dragcontrol.VALUE:
			text = mousetools._onMain(lambda: deepquery.turn(control.get("obj"), 0, dragcontrol.FINE))[1]
		else:
			lines = self._readLines(box)
			self._lines = lines
			text = " ".join(lines)[:300]
		# Translators: Spoken when no text is shown at a dial or slider.
		self._say(text or _("No text is shown at it. W asks the vision model what it shows."))

	def _look(self, box):
		point = dragcontrol.pointOf(self.control["share"], box)
		area = dragcontrol.around(point, tuple(scrolling.pixels(size, self.scale) for size in dragcontrol.AREA), box)
		answer = ""
		try:
			answer = self._plugin.runtime.describe(
				prepareImage(self._plugin._grab(area), 448),
				f"This picture shows a {self.control.get('kind') or 'control'} in a program, at its centre. What value or "
				"position does it show? Answer in one short sentence. If the picture does not show it, say that you "
				"cannot tell.", 60)
		except Exception:
			log.debugWarning("VisionClaw: the vision model could not look at a control", exc_info=True)
		answer = " ".join(str(answer or "").split())
		if answer:
			# Translators: Spoken before what the vision model thinks a dial or slider shows. It can be wrong.
			self._say(_("The vision model's guess: {answer}").format(answer=answer))
		else:
			# Translators: Spoken when the vision model could not say what a dial or slider shows.
			self._say(_("VisionClaw could not tell what it shows."))

	def _methods(self):
		control = self.control
		hasValue = control.get("obj") is not None and mousetools._onMain(lambda: deepquery.canTurn(control["obj"]))
		return dragcontrol.order(hasValue=hasValue)

	def _nextMethod(self, box):
		control = self.control
		methods = self._methods()
		now = control.get("method")
		control["method"] = methods[(methods.index(now) + 1) % len(methods)] if now in methods else methods[0]
		control["follows"] = None
		self._seen = None
		if control["method"] != dragcontrol.VALUE:
			mousetools.moveTo(*dragcontrol.pointOf(control["share"], box))
		# Translators: Spoken when the way a dial or slider is worked was changed. {how} is: by dragging it up and down, and so on.
		self._say(_("It is now worked {how}. Try the arrow keys.").format(how=dragcontrol.methodText(control["method"])))

	def probe(self, control, box, way=None):
		"""Find out how a control is worked, by trying each way one step up and, when something changed, one
		step back. Returns the way, or None when nothing VisionClaw can see changed."""
		self.control = control
		point = dragcontrol.pointOf(control["share"], box)
		self.scale = mousetools._onMain(lambda: mousetools.scaleAt(*point))
		hasValue = control.get("obj") is not None and mousetools._onMain(lambda: deepquery.canTurn(control["obj"]))
		if hasValue:
			control["method"] = dragcontrol.VALUE
			return dragcontrol.VALUE
		for method in dragcontrol.order(way):
			control["method"], control["follows"] = method, None
			self._seen = None
			if self._stroke(box, 1, dragcontrol.STEP):
				self._stroke(box, -1, dragcontrol.STEP)  # put it back, as well as can be
				return method
		control["method"] = None
		return None

	def start(self, control, way=None):
		"""Find out how a control is worked if that is not known, and take hold of it. Worker thread.
		Returns (whether it was taken, what to tell the user)."""
		box = mousetools._onMain(self._box)
		old = mousetools.position()
		if control.get("method") is None:
			mousetools._onMain(lambda: self.stop(say=False))
			with self._lock:
				found = self.probe(control, box, way)
			if found is None:
				mousetools.moveTo(*old)
				what = control.get("name") or "what is there"
				return False, (
					f"Nothing VisionClaw can see changed at {what} when it turned the mouse wheel on it and dragged it "
					"up, sideways and around. It may not be worked by dragging, it may show its change somewhere else, "
					"or the program may not take a mouse that is moved this way. Pointer mode (NVDA+Alt+K) lets you "
					"put the pointer on it yourself: G holds the mouse button, the arrow keys drag, G lets go.")
		return True, mousetools._onMain(lambda: self.take(control, say=False, old=old))

	def begin(self, control, resolve=None):
		"""Take hold of a control from a key press, and say what happened. Worker thread."""
		try:
			if resolve is not None:
				control = resolve()
			_ok, text = self.start(control)
		except LookupError as e:
			text = str(e)
		except Exception:
			log.error("VisionClaw: a control could not be taken hold of", exc_info=True)
			# Translators: Spoken when a dial or slider could not be taken hold of.
			text = _("VisionClaw could not take hold of it.")
		self._say(text)

	def takeAtPointer(self):
		"""From pointer mode: what is under the pointer is tried as a dial or slider. Main thread."""
		mode = self._plugin.pointerMode
		box = self._box()
		control = newControl("", "control", (mode.x, mode.y), box)
		mode.stop(say=False)
		# Translators: Spoken in pointer mode when D was pressed to try what is under the pointer as a dial or slider.
		ui.message(_("Finding out how this is worked: turning the mouse wheel on it and dragging it a little."))
		threading.Thread(target=self.begin, args=(control,), daemon=True).start()

	def takeSaved(self, app, keyId, binding):
		"""From a kept control's hotkey. Main thread."""
		threading.Thread(
			target=self.begin, args=(None, lambda: resolve(self._plugin, app, keyId, binding)), daemon=True).start()

	# --- Keeping ---

	def keep(self, key=None, app=None):
		"""Keep the held control under a hotkey for its program. Main thread. Returns the sentence that says so."""
		control = self.control
		if not self.active or control is None:
			return "No control is held."
		helpers = self._plugin.helpers
		app = app or deepquery._safe(lambda: api.getForegroundObject().appModule.appName, "") or ""
		if not app:
			return "VisionClaw could not tell which program this is, so nothing was kept."
		if control.get("saved"):
			return f"It is kept already, under {helpers.binding(*control['saved']).get('key', 'its hotkey')}."
		from . import accesstools
		used = accesstools.usedKeys(self._plugin)
		note = ""
		if key and fixes.normKey(key) in used:
			note = f" {key} already does something else in NVDA here, so another key was chosen."
			key = None
		if not key:
			free = fixes.freeKeys(1, used)
			if not free:
				return "No hotkey is free for this, so it was not kept."
			key = free[0]
		keyId = helpers.keyId(key)
		if keyId is None:
			return f"\"{key}\" is not a key, so it was not kept."
		helpers.addBinding(app, keyId, bindingOf(control, key))
		control["saved"] = (app, keyId)
		return (
			f"Kept. In {app}, {key} now takes hold of {control.get('name') or 'this ' + control.get('kind', 'control')}."
			f"{note} Ask VisionClaw to remove the hotkey {key} to undo this.")


def bindingOf(control, key):
	"""What is kept of a control: data only."""
	name = control.get("name") or ""
	return {
		"key": key, "action": dragcontrol.ACTION, "item": name or control.get("kind") or "control", "name": name,
		"kind": control.get("kind") or "control", "method": control.get("method"), "share": list(control["share"]),
		"radius": control.get("radius"), "follows": control.get("follows"), "find": control.get("find"),
		"site": control.get("site") or "",
	}


def _document():
	focus = api.getFocusObject()
	document = getattr(focus, "treeInterceptor", None)
	if document is not None and deepquery._safe(lambda: fixruntime.isPage(document), False):
		return document
	return None


def siteNow():
	"""The website the user is in, or "". Main thread."""
	document = _document()
	return hostOf(deepquery._safe(lambda: fixruntime.pageAddress(document), "")) if document is not None else ""


def _byRule(rule, site):
	"""NVDA's own object for the first control that fits a rule, in the page or the window in front."""
	if site:
		document = _document()
		if document is None or hostOf(fixruntime.pageAddress(document)) != site:
			return None
		node = fixruntime.findOnPage(document, rule)
		key = node.get("key") if node else None
		return document.getNVDAObjectFromIdentifier(int(key[0]), int(key[1])) if key else None
	for node in fixruntime.windowNodes(api.getForegroundObject()):
		if matches(rule, node):
			return node["obj"]
	return None


def resolve(plugin, app, keyId, binding):
	"""A kept control as it is in the window now. Worker thread. Raises LookupError with what to tell the user."""
	keys = plugin.controlKeys
	box = mousetools._onMain(keys._box)
	name, kind = binding.get("name") or "", binding.get("kind") or "control"
	find = binding.get("find") or {}
	# Translators: Spoken when a kept dial or slider is not in the window. {name} is its name.
	missing = _("{name} is not in this window right now.").format(name=name or binding.get("item") or kind)
	control = None
	if find.get("rule"):
		def located():
			obj = _byRule(find["rule"], binding.get("site") or "")
			return obj, (deepquery.boxOf(obj) if obj is not None else None)
		obj, place = mousetools._onMain(located)
		if place is None:
			raise LookupError(missing)
		point = ((place[0] + place[2]) // 2, (place[1] + place[3]) // 2)
		control = newControl(name, kind, point, box, binding.get("radius"), obj=obj, find=find)
	elif find.get("item"):
		result = plugin.clawScreen.items()
		index = match.best(find["item"], plugin.clawScreen.names(result)) if not getattr(result, "web", False) else None
		if index is None:
			raise LookupError(missing)
		x, y, radius = dragcontrol.handleOf(result.items, index)
		info = result.imageInfo
		control = newControl(name, kind, (info.convertXToScreen(x), info.convertYToScreen(y)), box, radius or None, find=find)
	else:
		control = dict(newControl(name, kind, (0, 0), box), share=tuple(binding["share"]), radius=binding.get("radius"))
	control["method"] = binding.get("method")
	control["follows"] = binding.get("follows")
	control["site"] = binding.get("site") or ""
	control["saved"] = (app, keyId)
	if control["method"] == dragcontrol.VALUE and control.get("obj") is None:
		control["method"] = None
	return control


def register(add, plugin, text, confirm, screen, pickItem, mentioned):
	"""Add the tool that takes hold of a control. Called from nvdatools.build."""
	keys = plugin.controlKeys

	def known(item, words):
		"""A slider or dial NVDA itself knows, by its name, or the focused control when the words mean it.
		Main thread. Returns (object, node) or None."""
		window = api.getForegroundObject()
		if _FOCUSED.search(words):
			focus = api.getFocusObject()
			if focus is not None and focus != window and deepquery.boxOf(focus) is not None:
				return focus, None
		wanted = " ".join(_KIND_WORDS.sub(" ", item or "").split())
		if not wanted:
			return None
		nodes = [node for node in fixruntime.windowNodes(window) if working.byRole(node) in working.TURNED]
		node = audit.findByName(wanted, nodes)
		if node is not None and deepquery.boxOf(node["obj"]) is not None:
			return node["obj"], node
		return None

	def workControl(task, item, asked):
		words = asked or task.request
		kind, method = dragcontrol.kindWord(words), dragcontrol.methodOf(words)
		box = mousetools._onMain(keys._box)
		site = mousetools._onMain(siteNow)
		control = None
		if plugin.pointerMode.active or dragcontrol.atPointer(words):
			mode = plugin.pointerMode
			point = (mode.x, mode.y) if mode.active else mousetools.position()
			if not (box[0] <= point[0] < box[2] and box[1] <= point[1] < box[3]):
				raise ToolError("The mouse pointer is not inside the window in front. Put it on the control with pointer mode first.")
			control = newControl(item if item and not dragcontrol.atPointer(item) else "", kind, point, box)
			mousetools._onMain(lambda: mode.stop(say=False))
		if control is None:
			found = mousetools._onMain(lambda: known(item, words))
			if found is not None:
				obj, node = found
				place = mousetools._onMain(lambda: deepquery.boxOf(obj))
				rule = audit.signature(node) if node is not None else None
				name = (node or {}).get("name") or mousetools._onMain(lambda: deepquery._safe(lambda: obj.name, "")) or item
				control = newControl(
					name, kind, ((place[0] + place[2]) // 2, (place[1] + place[3]) // 2), box,
					max(4, min(place[2] - place[0], place[3] - place[1]) * 7 // 20), obj=obj,
					find={"rule": rule} if rule else None, site=site)
		if control is None:
			result = getattr(task, "items", None) or screen.items()
			if getattr(result, "web", False):
				raise ToolError(
					"NVDA knows no slider or dial of that name on this page. Put the mouse pointer on it with pointer "
					"mode (NVDA+Alt+K) and press D there.")
			names = mentioned(words, result.items)
			index = pickItem(names[0] if len(names) == 1 else item, result.items)
			if index is None:
				raise ToolError(
					f"Nothing called \"{item}\" was found in this window's picture. Put the mouse pointer on the control "
					"with pointer mode (NVDA+Alt+K) and press D there.")
			x, y, radius = dragcontrol.handleOf(result.items, index)
			info = result.imageInfo
			shown = result.items[index].get("plain") or result.items[index].get("name") or result.items[index]["text"]
			control = newControl(
				shown, kind, (info.convertXToScreen(x), info.convertYToScreen(y)), box, radius or None,
				find={"item": shown})
		control["method"] = method
		what = control["name"] or "what is at the mouse pointer"
		# Translators: Asked before VisionClaw works a dial or slider with the mouse. {name} is the control.
		confirm(_(
			"Let the arrow keys work {name}? To find out how it is worked, VisionClaw turns the mouse wheel on it and "
			"drags it a little, then puts it back as well as it can."
		).format(name=what) if method is None else _("Let the arrow keys work {name}?").format(name=what))
		taken, said = keys.start(control)
		task.items = None
		if not taken:
			raise ToolError(said)
		wanted = fixes.keyIn(words)
		if wanted or dragcontrol.wantsKept(words):
			said += " " + mousetools._onMain(lambda: keys.keep(fixes.cleanKey(wanted) if wanted else None))
		else:
			said += " To keep this for next time, press K now."
		return said

	add("work_control",
		"let the arrow keys work a dial, knob, custom slider or other control that is only worked by dragging it "
		"with the mouse, and say what it shows after each press; can keep it under a hotkey",
		workControl, {
			"item": text("the name of the dial, slider or control, as the user said it", maxLength=80),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, title="Taking hold of the control", tell=VERBATIM)
