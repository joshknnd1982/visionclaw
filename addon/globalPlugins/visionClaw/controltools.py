# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tool that sets a named control of the program in front: turns a check box, switch or option
# on or off, and turns a slider or value up or down or to a number. "Turn on my NVIDIA GPU for this program",
# "turn the equalizer down", "turn the volume up a bit". The user's own words say which control and what to do
# (claw/controls.py). The control is looked for by its name:
#   1. in what NVDA knows of the window in front;
#   2. on the other pages of a dialog that has tabs, one after another, and the user is told which page;
#   3. in the window's picture, for a window NVDA cannot read: then VisionClaw works with the mouse, compares
#      the picture before and after, and says what it saw, and what it could only guess. A drawn knob or slider
#      is set to a number by moving it a step at a time and reading the number shown at it (claw/target.py).
# The least risky way that works is used: the control's own action through NVDA or Windows itself first, the
# keyboard next, the mouse last. The user is asked before anything is changed, and told what the control was
# and what it is now, never only what was tried.

import time

import addonHandler
import api
import config

from . import deepquery, fixruntime, mousetools
from .claw import computer, controls, dragcontrol, policy, prompts, target
from .claw.catalog import VISION
from .claw.llm import clip
from .claw.tools import VERBATIM, ToolError
from .controlkeys import newControl
from .engine import prepareImage

addonHandler.initTranslation()

_SETTLE = 0.45


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def _nodes():
	"""The controls of the window in front as NVDA knows them, without those that are not shown. Main thread."""
	found = []
	for node in fixruntime.windowNodes(api.getForegroundObject()):
		if node.get("obj") is None or set(node.get("states") or ()) & {"INVISIBLE", "OFFSCREEN"}:
			continue
		found.append(node)
	return found


def _label(node):
	return node.get("name") or node.get("text") or ""


def findKnown(wish):
	"""The controls NVDA knows in the window in front that the wish names. Main thread."""
	nodes = [node for node in _nodes() if _label(node) and node.get("role") not in controls.PAGES]
	kinds = controls.CHECKABLE if wish["what"] in (controls.ON, controls.OFF) else controls.TURNED
	prefer = [index for index, node in enumerate(nodes) if node.get("role") in kinds]
	return [nodes[index] for index in controls.pick(wish["name"], [_label(node) for node in nodes], prefer)]


def pagesOf():
	"""The pages of the dialog in front, as its tabs: [(name, object, whether it is the page shown)]. Main thread."""
	return [(_label(node), node["obj"], "SELECTED" in (node.get("states") or ())) for node in _nodes()
		if node.get("role") in controls.PAGES and _label(node)][:controls.MAX_PAGES]


def statesOf(obj):
	"""The states of a control as NVDA gives them now. Main thread."""
	return [getattr(state, "name", str(state)) for state in (_safe(lambda: obj.states, ()) or ())]


def valueOf(obj):
	"""What a control shows as its value now, in words. Main thread."""
	span = deepquery.rangeOf(obj)
	shown = " ".join(str(_safe(lambda: obj.value, "") or "").split())[:60]
	if shown:
		return shown
	return dragcontrol.valueText(span["now"], span["low"], span["high"]) if span else ""


def setShare(obj, value, percent):
	"""Set a control's value through Windows itself: to a number, or to a share of its range. Main thread.
	Returns whether Windows took it."""
	span = deepquery.rangeOf(obj)
	if span is None or span["readOnly"]:
		return False
	wanted = span["low"] + (span["high"] - span["low"]) * value / 100.0 if percent else float(value)
	wanted = max(span["low"], min(span["high"], wanted))
	try:
		deepquery._rangePattern(obj).SetValue(wanted)
	except Exception:
		return False
	return True


def pressKey(name, times=1):
	"""Press a key in the program in front, as often as said. Main thread."""
	from keyboardHandler import KeyboardInputGesture
	for _press in range(times):
		KeyboardInputGesture.fromName(name).send()


def register(add, plugin, text, onMain, confirm, screen):
	"""Add the tool that sets a named control. The first five arguments are the helpers of nvdatools.build."""

	def onPages(task, wish):
		"""Look for the control on the other pages of the dialog. Returns (the controls found, the page's name,
		how many pages were looked at). Where it is on no page, the page that was shown is shown again."""
		pages = onMain(pagesOf)
		start = next((page for page in pages if page[2]), None)
		looked = 0
		for name, obj, shown in pages:
			if shown:
				continue
			task.check()
			onMain(fixruntime.pressObject, obj)
			time.sleep(_SETTLE)
			looked += 1
			found = onMain(findKnown, wish)
			if found:
				return found, name, looked
		if looked and start is not None:
			onMain(fixruntime.pressObject, start[1])
			time.sleep(_SETTLE)
		return [], "", looked

	def setKnown(task, wish, node, where):
		"""Set a control NVDA knows. Returns the sentence for the user."""
		obj, role, name = node["obj"], node.get("role") or "", _label(node)
		what = wish["what"]
		if role in controls.CHECKABLE:
			if what not in (controls.ON, controls.OFF):
				raise ToolError(f"{name} is a control that is on or off, not one that is turned up or down. Say whether to turn it on or off.")
			now = controls.checked(onMain(statesOf, obj))
			if now is not None and controls.onOff(now) == what:
				return f"{name}{where} is already {what}. Nothing was changed."
			# Translators: Asked before VisionClaw turns an option of a program on or off. {name} is the option.
			confirm((_("Turn {name} on?") if what == controls.ON else _("Turn {name} off?")).format(name=name))
			onMain(fixruntime.pressObject, obj)
			time.sleep(_SETTLE)
			after = controls.checked(onMain(statesOf, obj))
			if after is not None and controls.onOff(after) == what:
				return f"{name}{where} was {controls.onOff(not after)} and is now {what}."
			return (
				f"{name}{where} was pressed, but NVDA still reports it as {controls.onOff(bool(after))}. The program may "
				"need a moment, or it may ask something first.")
		if role in controls.TURNED or onMain(deepquery.canTurn, obj):
			if what in (controls.ON, controls.OFF):
				raise ToolError(f"{name} is a control that is turned up or down, not one that is on or off. Say up, down, or a number.")
			before = onMain(valueOf, obj)
			direction = 1 if what == controls.UP else -1
			if what == controls.SET:
				# Translators: Asked before VisionClaw sets a slider of a program. {name} is the slider, {value} the new value.
				confirm(_("Set {name} to {value}?").format(name=name, value=f"{wish['value']}{' percent' if wish['percent'] else ''}"))
				if not onMain(setShare, obj, wish["value"], wish["percent"]):
					raise ToolError(
						f"{name}{where} does not let its value be set to a number from outside. Ask to turn it up or down "
						"instead; it shows " + (before or "no value") + ".")
			else:
				# Translators: Asked before VisionClaw turns a slider of a program up or down. {name} is the slider.
				confirm((_("Turn {name} up, {steps}?") if direction > 0 else _("Turn {name} down, {steps}?")).format(
					name=name, steps=controls.stepsText(wish["steps"])))
				steps = dragcontrol.MAX_END_STROKES if wish["steps"] >= controls.TO_END else wish["steps"]
				if onMain(deepquery.canTurn, obj):
					for _step in range(steps):
						task.check()
						if not onMain(deepquery.turn, obj, direction, dragcontrol.STEP)[0]:
							break
				else:
					# The keyboard: the control takes the focus, and the arrow keys turn it as they do for any slider.
					onMain(lambda: obj.setFocus())
					time.sleep(0.2)
					key = "end" if steps >= dragcontrol.MAX_END_STROKES and direction > 0 else (
						"home" if steps >= dragcontrol.MAX_END_STROKES else "upArrow" if direction > 0 else "downArrow")
					onMain(pressKey, key, 1 if key in ("home", "end") else steps)
			time.sleep(_SETTLE)
			after = onMain(valueOf, obj)
			if before and after and before != after:
				return f"{name}{where} was {before} and is now {after}."
			if after:
				return f"{name}{where} did not change. It shows {after}. It may be at its end, or the program did not take it."
			return f"{name}{where} was turned, but it shows no value VisionClaw can read, so whether it changed is not known."
		# Anything else NVDA knows: a list to choose from, a field. The focus is put on it, which is as far as plain
		# code can go without guessing, and the user is told the keys.
		onMain(lambda: obj.setFocus())
		shown = onMain(valueOf, obj)
		return (
			f"{name}{where} is not a control that is simply on or off or turned up or down"
			+ (f"; it shows {shown}" if shown else "") + ". The focus is on it now: the arrow keys change it, and NVDA says each choice.")

	def setSeen(task, wish):
		"""Set a control that is only in the window's picture. Returns the sentence for the user."""
		result = getattr(task, "items", None) or screen.items()
		if getattr(result, "web", False) or not result.items:
			return None
		names = [item.get("plain") or item.get("name") or item["text"] for item in result.items]
		found = controls.pick(wish["name"], names)
		if not found:
			return None
		if len(found) > 1:
			raise ToolError("Several things in this window's picture fit that name: " + "; ".join(names[i] for i in found[:5]) + ". Say which one.")
		item, shown = result.items[found[0]], names[found[0]]
		box = onMain(lambda: plugin.controlKeys._box())
		info = result.imageInfo
		what = wish["what"]
		if what in (controls.UP, controls.DOWN):
			x, y, radius = dragcontrol.handleOf(result.items, found[0])
			control = newControl(shown, "control", (info.convertXToScreen(x), info.convertYToScreen(y)), box, radius or None,
				find={"item": shown})
			# Translators: Asked before VisionClaw works a slider it only sees in a window's picture. {name} is the slider.
			confirm(_(
				"Turn {name} {way} with the mouse? NVDA cannot read this control, so VisionClaw first finds out how it is "
				"worked by turning the mouse wheel on it and dragging it a little.").format(name=shown, way=what))
			keys = plugin.controlKeys
			taken, said = keys.start(control)
			if not taken:
				raise ToolError(said)
			moved = 0
			steps = dragcontrol.MAX_END_STROKES if wish["steps"] >= controls.TO_END else wish["steps"]
			try:
				with keys._lock:
					for _step in range(steps):
						task.check()
						if not keys._stroke(box, 1 if what == controls.UP else -1, dragcontrol.STEP):
							break
						moved += 1
					now = keys._shown(box)
			finally:
				mousetools._onMain(lambda: keys.stop(say=False))
			task.items = None
			if not moved:
				return f"{shown} did not move when it was turned {what}. It may be at its end."
			return f"Turned {shown} {what}, {computer.many(moved, 'step')}, with the mouse." + (
				f" It now shows: {clip(now, 80)}" if now else " The picture changed there; it shows no value VisionClaw can read.")
		if what == controls.SET:
			# A drawn knob or slider is set to a number the way a sighted person does it: moved a step at a time,
			# with the number shown at it read after every step (claw/target.py). Plain code; no model.
			if not config.conf["visionClaw"]["useOcr"]:
				raise ToolError(
					f"{shown} is only in the window's picture, and reading text in pictures is turned off in VisionClaw's "
					"settings, so the number it shows cannot be read. Ask to turn it up or down instead.")
			x, y, radius = dragcontrol.handleOf(result.items, found[0])
			control = newControl(shown, "control", (info.convertXToScreen(x), info.convertYToScreen(y)), box, radius or None,
				find={"item": shown})
			confirm(target.question(shown, wish["value"], wish["percent"]))
			keys = plugin.controlKeys
			taken, said = keys.start(control)
			if not taken:
				raise ToolError(said)
			try:
				with keys._lock:
					outcome = target.seek(
						wish["value"], wish["percent"], lambda: keys._readLines(box),
						lambda direction, size: keys._stroke(box, direction, size), task.check, name=shown)
			finally:
				mousetools._onMain(lambda: keys.stop(say=False))
			task.items = None
			return target.text(shown, wish["value"], wish["percent"], outcome)
		# On or off, seen only in the picture: what it is now can only be read by the model that sees.
		point = result.screenPoint(item)
		area = dragcontrol.around(point, dragcontrol.AREA, box)
		seer = policy.roleName(VISION, policy.isOneModel(plugin.runtime))

		def reading():
			answer = _safe(lambda: plugin.runtime.describe(
				prepareImage(plugin._grab(area), 448),
				f"This picture shows part of a program's window. Find the label \"{shown}\" and the check box or switch that "
				"belongs to it. Is it on or off? Answer with one word: on, off, or unknown.", 12, cancel=task.cancel,
				system=prompts.seeing()), "")
			word = " ".join(str(answer or "").lower().split()).strip(" .")
			return word if word in ("on", "off") else ""

		before = reading()
		task.check()
		if before == what:
			return (
				f"{shown} looks {what} already, by the {seer}'s reading of the picture, which can be wrong. Nothing was "
				f"clicked. To click it anyway, say: click {shown}.")
		# Translators: Asked before VisionClaw clicks an option it only sees in a window's picture. {name} is the option.
		confirm((_("Click {name} to turn it on?") if what == controls.ON else _("Click {name} to turn it off?")).format(name=shown))
		picture = _safe(lambda: plugin._grab(area))
		old = mousetools.position()
		mousetools._onMain(lambda: mousetools.click(point[0], point[1]))
		time.sleep(_SETTLE)
		mousetools.moveTo(*old)
		changed = picture is not None and dragcontrol.changed(picture, _safe(lambda: plugin._grab(area))) >= dragcontrol.CHANGED
		after = reading()
		task.items = None
		if not changed:
			return f"Clicked {shown}, but nothing VisionClaw can see changed there. It may need a click on the box beside its name."
		return f"Clicked {shown}, and the picture changed there." + (
			f" The {seer} reads it as {after} now, which can be wrong." if after else f" Whether it is {what} now cannot be read from the picture.")

	def setControl(task, asked):
		wish = controls.wish(asked or task.request)
		if wish is None:
			raise ToolError(
				"The request does not say which control of this program to set and how. Name the control, and say on or "
				"off, up or down, or a number.")
		names = wish.get("names") or [wish["name"]]
		if len(names) < 2:
			return setOne(task, wish)
		# Several controls named in one breath: "turn on UI narration and subtitles". The whole name is tried first,
		# because one control may be called so; then each on its own, and each is asked about and said.
		try:
			return setOne(task, wish)
		except ToolError:
			pass
		said, failed = [], []
		for name in names:
			task.check()
			try:
				said.append(setOne(task, dict(wish, name=name, names=[name])))
			except ToolError as e:
				failed.append(str(e))
		if not said:
			raise ToolError(" ".join(failed))
		return " ".join(said + failed)

	def setOne(task, wish):
		found = onMain(findKnown, wish)
		where, looked = "", 0
		if not found:
			found, page, looked = onPages(task, wish)
			if found:
				where = f", on the page {page},"
		task.check()
		if len(found) > 1:
			raise ToolError("Several controls fit that name: " + "; ".join(_label(node) for node in found[:5]) + ". Say which one.")
		if found:
			said = setKnown(task, wish, found[0], where)
			task.items = None
			return said
		said = setSeen(task, wish)
		if said is not None:
			return said
		raise ToolError(
			f"No control called \"{wish['name']}\" was found in the window in front: not in what NVDA knows of it"
			+ (f", not on its {computer.many(looked, 'other page')}" if looked else "")
			+ ", and not in its picture. It may have another name there; ask what the window shows.")

	add("set_control",
		"turn a named option, check box or switch of the program in front on or off, or turn a named slider or value "
		"up or down or to a number; looks for it in the window, on the other pages of its dialog and in its picture, "
		"and says what it was and what it is now",
		setControl, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Setting the control", tell=VERBATIM)
