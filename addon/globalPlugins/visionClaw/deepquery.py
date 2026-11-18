# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a deep query of one control: everything that can be found out about it without touching it.
# What NVDA says it is; what Windows UI Automation and the older accessibility interfaces offer for it; what
# its window is and which toolkit or game engine draws it; the text NVDA's off-screen model caught being
# drawn in it; and what Windows itself finds at its middle. The result is plain data (claw/working.py turns it
# into sentences), so the models and the code that chooses a fix can use it.
# Also the one thing here that changes something: setting a control's value through UI Automation, which is
# how a slider or dial is worked without the mouse where the program allows it.
# Everything here must be called on NVDA's main thread, and nothing here may raise.

import api
from .vclog import log

from .claw import dragcontrol

# Windows' own numbers for what UI Automation can do with a control, and for two of its properties.
_PATTERNS = (
	(30031, "invoke"), (30041, "toggle"), (30033, "a value in a range"), (30043, "a value as text"),
	(30028, "expand and collapse"), (30036, "select"), (30034, "scroll"), (30042, "move and resize"),
	(30137, "drag"), (30141, "be dropped on"),
)
_RANGE_PATTERN, _FRAMEWORK = 10003, 30024
_WEB_KEPT = ("tag", "xml-roles", "id", "class", "draggable", "haspopup", "valuetext", "text-input-type")
_SILENT_KINDS = ("UNKNOWN", "PANE", "WINDOW", "CANVAS", "GRAPHIC", "CLIENT")


def _safe(fn, default=None):
	try:
		value = fn()
	except Exception:
		return default
	return default if value is None else value


def _words(value, limit=120):
	return " ".join(str(value or "").split())[:limit]


def _element(obj):
	return _safe(lambda: obj.UIAElement)


def _interface(name):
	import UIAHandler
	found = getattr(UIAHandler, name, None)
	return found if found is not None else getattr(UIAHandler.UIA, name)


def _rangePattern(obj):
	element = _element(obj)
	if element is None:
		return None
	try:
		unknown = element.GetCurrentPattern(_RANGE_PATTERN)
		if not unknown:
			return None
		return unknown.QueryInterface(_interface("IUIAutomationRangeValuePattern"))
	except Exception:
		return None


def rangeOf(obj):
	"""The range of a control's value as Windows reports it: {"now", "low", "high", "small", "readOnly"},
	or None when the program offers none."""
	pattern = _rangePattern(obj)
	if pattern is None:
		return None
	try:
		low, high = float(pattern.CurrentMinimum), float(pattern.CurrentMaximum)
		found = {
			"now": float(pattern.CurrentValue), "low": low, "high": high,
			"small": float(_safe(lambda: pattern.CurrentSmallChange, 0.0) or 0.0),
			"readOnly": bool(_safe(lambda: pattern.CurrentIsReadOnly, False)),
		}
	except Exception:
		return None
	return found if high > low else None


def turn(obj, direction, size):
	"""Change a control's value by one step through Windows itself. Returns (whether it changed, what it now
	shows in words). Never raises."""
	span = rangeOf(obj)
	if span is None or span["readOnly"]:
		return False, ""
	wanted = dragcontrol.nextValue(span["now"], span["low"], span["high"], direction, size, span["small"])
	if wanted != span["now"]:
		try:
			_rangePattern(obj).SetValue(wanted)
		except Exception:
			log.debugWarning("VisionClaw: a value could not be set through UI Automation", exc_info=True)
			return False, ""
	after = rangeOf(obj) or span
	shown = _words(_safe(lambda: obj.value), 60) or dragcontrol.valueText(after["now"], after["low"], after["high"])
	return after["now"] != span["now"], shown


def canTurn(obj):
	span = rangeOf(obj) if obj is not None else None
	return span is not None and not span["readOnly"]


def boxOf(obj):
	place = _safe(lambda: obj.location)
	if not place or place.width < 4 or place.height < 4:
		return None
	return (place.left, place.top, place.left + place.width, place.top + place.height)


def _interfaceName(obj):
	if _element(obj) is not None:
		return "Windows UI Automation"
	names = " ".join(cls.__module__ + "." + cls.__name__ for cls in type(obj).__mro__)
	if "JAB" in names:
		return "the Java Access Bridge"
	if _safe(lambda: obj.IAccessibleObject) is not None:
		return "IAccessible2, as browsers use" if _safe(lambda: obj.IA2Attributes) else "Microsoft Active Accessibility"
	return "its window alone, which reports no accessibility interface" if _safe(lambda: obj.windowHandle) else ""


def _drawn(obj):
	"""Text that NVDA's off-screen model caught the program drawing inside this control."""
	try:
		import displayModel
		import textInfos
		return _words(displayModel.DisplayModelTextInfo(obj, textInfos.POSITION_ALL).text, 200)
	except Exception:
		return ""


def under(x, y):
	"""What Windows itself finds at a point of the screen, as (kind, name), or None."""
	found = _safe(lambda: api.getDesktopObject().objectFromPoint(int(x), int(y)))
	if found is None:
		return None
	return (_safe(lambda: found.role.name, "") or "", _words(_safe(lambda: found.name), 60))


def facts(obj):
	"""Everything found out about one control, as plain data."""
	role = _safe(lambda: obj.role.name, "") or "UNKNOWN"
	states = [_safe(lambda s=state: s.name, "") for state in (_safe(lambda: obj.states) or ())]
	found = {
		"role": role,
		"roleText": _safe(lambda: obj.role.displayString, "") or role.lower(),
		"name": _words(_safe(lambda: obj.name)),
		"value": _words(_safe(lambda: obj.value), 80),
		"description": _words(_safe(lambda: obj.description)),
		"states": sorted(state for state in states if state),
		"focusable": "FOCUSABLE" in states,
		"shortcut": _words(_safe(lambda: obj.keyboardShortcut), 40),
		"box": boxOf(obj),
		"api": _interfaceName(obj),
		"windowClass": _words(_safe(lambda: obj.windowClassName), 80),
		"controlId": _safe(lambda: obj.windowControlID, 0) or 0,
		"children": _safe(lambda: obj.childCount, 0) or 0,
		"app": _words(_safe(lambda: obj.appModule.appName), 60),
	}
	count = min(5, _safe(lambda: obj.actionCount, 0) or 0)
	found["actions"] = [name for name in (_words(_safe(lambda i=i: obj.getActionName(i)), 30) for i in range(count)) if name]
	if not found["actions"]:
		# Many controls report no count of actions and still have one that is done by default.
		found["actions"] = [name for name in (_words(_safe(lambda: obj.getActionName()), 30),) if name]
	element = _element(obj)
	if element is not None:
		found["patterns"] = [name for ident, name in _PATTERNS if _safe(lambda i=ident: element.GetCurrentPropertyValue(i)) is True]
		found["framework"] = _words(_safe(lambda: element.GetCurrentPropertyValue(_FRAMEWORK)), 30)
	span = rangeOf(obj)
	if span is not None:
		found["range"] = span
	web = _safe(lambda: obj.IA2Attributes)
	if hasattr(web, "get"):
		found["web"] = {key: _words(web.get(key), 60) for key in _WEB_KEPT if web.get(key)}
	if role in _SILENT_KINDS:
		found["drawn"] = _drawn(obj)
	box = found["box"]
	if box is not None:
		found["under"] = under((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
	return found
