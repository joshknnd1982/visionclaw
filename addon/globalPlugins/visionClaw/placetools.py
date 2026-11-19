# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the places of Windows itself, read from what Windows tells screen readers about them: the icons of
# the notification area (the system tray), also those hidden behind Show hidden icons; the programs on the
# taskbar; the icons on the desktop; and the Start menu, quick settings, the notification center and clipboard
# history, which are opened with their own key first. Which place is meant and what is wanted there is read from
# the user's own words by plain code (claw/places.py), which also sorts and words what is found here. No model is
# asked: what Windows reports is said word for word.
# Asked for by the owner on 2026-11-18, after "tell me all objects that are currently in the system tray." was
# answered from a picture of the desktop: "I cannot see the system tray in this image".
#
# What was read to write this, on 2026-11-18: Microsoft's pages on UI Automation ("UI Automation Tree Overview",
# "Control Type Identifiers", IUIAutomation::ElementFromHandle, IUIAutomationTreeWalker, IUIAutomationElement's
# Current properties, IUIAutomationInvokePattern::Invoke, IUIAutomationTogglePattern::CurrentToggleState); and the
# taskbar of the owner's Windows 11 (build 26300), read with UI Automation from plain Python the same day. There the
# taskbar is the window Shell_TrayWnd, whose own tree holds only empty panes of the old taskbar; the buttons are in
# its child window Windows.UI.Composition.DesktopWindowContentBridge, which Windows reports as not visible. The
# icons of the notification area have the automation id SystemTrayIcon and classes that begin with SystemTray.,
# the first being the button "Show Hidden Icons"; the programs are Taskbar.TaskListButtonAutomationPeer, named
# "Claude - 1 running window" or "Microsoft Edge pinned". The hidden icons are in a window of their own,
# TopLevelWindowForOverflowXamlIsland, that exists only while they are shown. On Windows 10 the icons are toolbar
# buttons inside TrayNotifyWnd, and the hidden ones in NotifyIconOverflowWindow, which is there while hidden too.
# The desktop's icons are the list items of the SysListView32 inside SHELLDLL_DefView, under Progman or a WorkerW.
# When Windows changes its taskbar, read it again in the same way; do not guess a class or an id.
#
# Everything that asks Windows here runs on NVDA's main thread (onMain), as NVDA's own UI Automation does; waiting
# is done outside it. Nothing here may raise: a place Windows says nothing about is an empty list.
# What tests must never do for real is in functions of their own, which tests/test_nvda_stub.py replaces:
# trayItems, hiddenItems, desktopItems, frontItems, frontApp; and computertools.pressShortcut.

import ctypes
import time
from ctypes import wintypes

import addonHandler
import api

from . import computertools
from .claw import computer, debuglog, places
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()

_user32 = ctypes.windll.user32
# Windows' own numbers for what UI Automation can do with an element.
_INVOKE, _TOGGLE, _RANGE = 10000, 10015, 10003
MAX_DEPTH = 14
MAX_ITEMS = 400
MAX_VISITS = 1500
# How long the hidden icons are given to show, and a part of Windows that is opened to be read.
HIDDEN_WAIT = 1.5
OPEN_WAIT = 1.2
_POLL = 0.1
_BRIDGE = "Windows.UI.Composition.DesktopWindowContentBridge"
_TASKBARS = ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")
_OVERFLOW_NEW, _OVERFLOW_OLD = "TopLevelWindowForOverflowXamlIsland", "NotifyIconOverflowWindow"
# The programs that show a part of Windows itself once it is open: the Start menu; quick settings and the
# notification center; clipboard history. A part whose program is in front already is read without its key, which
# would close it again.
_OPEN_APPS = {
	"start": ("startmenuexperiencehost",),
	"quick-settings": ("shellexperiencehost", "shellhost"),
	"notifications": ("shellexperiencehost", "shellhost"),
	"clipboard": ("textinputhost",),
}


def _safe(fn, default=None):
	try:
		value = fn()
	except Exception:
		return default
	return default if value is None else value


def _client():
	"""NVDA's own UI Automation client, or None where NVDA does not use UI Automation."""
	try:
		import UIAHandler
		handler = getattr(UIAHandler, "handler", None)
		return getattr(handler, "clientObject", None) if handler is not None else None
	except Exception:
		return None


def _interface(name):
	import UIAHandler
	found = getattr(UIAHandler, name, None)
	return found if found is not None else getattr(UIAHandler.UIA, name)


# --- Windows' windows ---

_user32.FindWindowW.restype = wintypes.HWND
_user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
_user32.FindWindowExW.restype = wintypes.HWND
_user32.FindWindowExW.argtypes = (wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)
_ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _className(hwnd):
	buffer = ctypes.create_unicode_buffer(256)
	_user32.GetClassNameW(hwnd, buffer, 256)
	return buffer.value


def _children(hwnd):
	"""Every window inside a window, at any depth, as (handle, class)."""
	found = []

	def each(child, _extra):
		found.append((child, _className(child)))
		return True

	_user32.EnumChildWindows(hwnd, _ENUM(each), 0)
	return found


def _topWindows(cls):
	"""Every top-level window of a class."""
	found = []
	hwnd = _user32.FindWindowExW(None, None, cls, None)
	while hwnd and len(found) < 16:
		found.append(hwnd)
		hwnd = _user32.FindWindowExW(None, hwnd, cls, None)
	return found


def _visible(hwnd):
	return bool(hwnd) and bool(_user32.IsWindowVisible(hwnd))


# --- What UI Automation reports ---

def _state(element):
	"""An element's state in a word or a number, where it has one: on or off, a value in a range."""
	toggle = _safe(lambda: element.GetCurrentPattern(_TOGGLE))
	if toggle:
		state = _safe(lambda: toggle.QueryInterface(_interface("IUIAutomationTogglePattern")).CurrentToggleState)
		if state is not None:
			return {0: "off", 1: "on", 2: "partly on"}.get(int(state), "")
	span = _safe(lambda: element.GetCurrentPattern(_RANGE))
	if span:
		value = _safe(lambda: span.QueryInterface(_interface("IUIAutomationRangeValuePattern")).CurrentValue)
		if value is not None:
			return f"{float(value):g}"
	return ""


def _facts(element, path, hidden):
	rect = element.CurrentBoundingRectangle
	box = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)) if rect.right > rect.left and rect.bottom > rect.top else None
	kind = int(element.CurrentControlType)
	return {
		"name": element.CurrentName or "", "kind": kind, "cls": element.CurrentClassName or "",
		"aid": element.CurrentAutomationId or "", "box": box, "path": tuple(path), "hidden": hidden,
		"offscreen": bool(_safe(lambda: element.CurrentIsOffscreen, False)),
		"state": _state(element) if kind in (50002, 50000, 50015, 50013) else "",
		"element": element,
	}


def walk(hwnd, hidden=False):
	"""Everything UI Automation reports inside a window, depth first, as plain facts (claw/places.py). Main
	thread. An element that cannot be read is left out."""
	client = _client()
	if client is None or not hwnd:
		return []
	root = _safe(lambda: client.ElementFromHandle(hwnd))
	walker = _safe(lambda: client.ControlViewWalker)
	if not root or walker is None:
		return []
	items = []

	# Every element is counted, also one that cannot be read, so that a tree that never ends ends here.
	visited = [0]

	def visit(parent, path, depth):
		if depth > MAX_DEPTH or visited[0] >= MAX_VISITS:
			return
		child = _safe(lambda: walker.GetFirstChildElement(parent))
		while child and len(items) < MAX_ITEMS and visited[0] < MAX_VISITS:
			visited[0] += 1
			facts = _safe(lambda: _facts(child, path, hidden))
			if facts is not None:
				items.append(facts)
			visit(child, path + ((facts or {}).get("cls", ""),), depth + 1)
			current = child
			child = _safe(lambda: walker.GetNextSiblingElement(current))

	visit(root, (_className(hwnd),), 0)
	return items


def _windowsOf(hwnd):
	"""A window and the windows inside it that hold content of their own: Windows 11's taskbar draws its buttons in
	a child window that Windows reports as not visible."""
	return [hwnd] + [child for child, cls in _children(hwnd) if cls == _BRIDGE]


def _readAll(hwnds, hidden=False):
	items = []
	for hwnd in hwnds:
		for window in _windowsOf(hwnd):
			items += walk(window, hidden)
	return items


def trayItems():
	"""Everything on the taskbars of Windows, the notification area with them. Main thread."""
	return _readAll([hwnd for cls in _TASKBARS for hwnd in _topWindows(cls)])


def _overflow():
	"""The window of the hidden icons as (handle, whether it is there while hidden)."""
	old = _user32.FindWindowW(_OVERFLOW_OLD, None)
	if old:
		return old, True
	return _user32.FindWindowW(_OVERFLOW_NEW, None), False


def _overflowShown():
	hwnd, _always = _overflow()
	return _visible(hwnd)


def _invoke(element):
	"""Do an element's own action, as a click on it would. Main thread. Returns whether Windows took it."""
	pattern = _safe(lambda: element.GetCurrentPattern(_INVOKE))
	if not pattern:
		return False
	try:
		pattern.QueryInterface(_interface("IUIAutomationInvokePattern")).Invoke()
		return True
	except Exception as e:
		debuglog.error("places", "An element of Windows could not be invoked", e)
		return False


def hiddenItems(shown, onMain):
	"""The icons hidden behind Show hidden icons, as (their facts, whether they could be read). On Windows 10 they
	are read where they are; on Windows 11 they exist only while shown, so the button is pressed through Windows
	itself, they are read, and the button is pressed again to hide them, as they were. shown: what trayItems gave."""
	hwnd, always = onMain(_overflow)
	if hwnd and always:
		return onMain(_readAll, [hwnd], True), True
	if hwnd and onMain(_visible, hwnd):
		return onMain(_readAll, [hwnd], True), True
	chevron = next((item for item in shown if places.isTray(item) and places._CHEVRON.search(places.clean(item.get("name")))), None)
	if chevron is None or chevron.get("element") is None:
		return [], False
	debuglog.log("places", "Showing the hidden icons for a moment, to read them.")
	if not onMain(_invoke, chevron["element"]):
		return [], False
	found, read = [], False
	try:
		waited = 0.0
		while waited < HIDDEN_WAIT and not onMain(_overflowShown):
			time.sleep(_POLL)
			waited += _POLL
		hwnd, _always = onMain(_overflow)
		if hwnd and onMain(_visible, hwnd):
			found, read = onMain(_readAll, [hwnd], True), True
	finally:
		# Hidden again as they were: the button is pressed again only while they are still shown.
		if onMain(_overflowShown):
			onMain(_invoke, chevron["element"])
	return found, read


def _desktopList():
	"""The list of the desktop's icons, or 0."""
	for cls in ("Progman", "WorkerW"):
		for top in _topWindows(cls):
			for child, childClass in _children(top):
				if childClass == "SysListView32" and _className(_user32.GetParent(child)) == "SHELLDLL_DefView":
					return child
	return 0


def desktopItems():
	"""The icons on the desktop. Main thread."""
	return walk(_desktopList())


def frontApp():
	"""The program of the window in front, in lower case. Main thread."""
	return (_safe(lambda: api.getForegroundObject().appModule.appName, "") or "").lower()


def frontClass():
	"""The class of the window in front. Main thread."""
	return _safe(lambda: api.getForegroundObject().windowClassName, "") or ""


def frontItems():
	"""Everything in the window in front, for a part of Windows that was just opened. Main thread."""
	hwnd = _safe(lambda: api.getForegroundObject().windowHandle, 0)
	return _readAll([hwnd]) if hwnd else []


def boxOf(ident):
	"""Where a place that is always on the screen is, as (left, top, right, bottom), or None. Main thread."""
	items = trayItems() if ident in (places.TRAY, places.TASKBAR) else []
	if ident == places.TRAY:
		boxes = [item["box"] for item in items if item.get("box") and places.isTray(item) and not item.get("hidden")]
	elif ident == places.TASKBAR:
		boxes = [item["box"] for item in items if item.get("box")]
	else:
		return None
	if not boxes:
		return None
	return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


# --- Reading a place ---

def read(ident, wish, onMain, pressShortcut=None):
	"""What a place of Windows holds, in sentences, by plain code. wish: what places.wish gave."""
	how, thing = wish.get("how", places.LIST), wish.get("thing", "")
	if ident == places.TRAY:
		shown = onMain(trayItems) or []
		hidden, read_ = hiddenItems(shown, onMain)
		said = places.trayText(places.tray(shown + hidden), how, thing, hiddenRead=read_)
		debuglog.log("places", f"The notification area: {len(shown)} things read, {len(hidden)} hidden ones (read: {read_}).")
		return said or places.nothingText(ident)
	if ident == places.TASKBAR:
		said = places.taskbarText(places.taskbar(onMain(trayItems) or []), how, thing)
		return said or places.nothingText(ident)
	if ident == places.DESKTOP:
		names = [item["name"] for item in places.usable(onMain(desktopItems) or [])]
		return places.listText(ident, names, how, thing) or places.nothingText(ident)
	# A part that exists only while it is open: opened with its own key, read, and left open.
	apps = _OPEN_APPS.get(ident, ())
	app = onMain(frontApp) or ""
	if app not in apps:
		_name, keys, _said, _there = computer.windowsPartOf(places.placeOf(ident)[2])
		debuglog.log("places", f"Opening {ident} with {keys} to read it.")
		onMain(pressShortcut or computertools.pressShortcut, keys)
		waited = 0.0
		while waited < OPEN_WAIT:
			time.sleep(_POLL)
			waited += _POLL
			app = onMain(frontApp) or ""
			if app in apps and waited >= 0.4:
				break
		if app not in apps:
			return places.notOpenedText(ident)
	items = onMain(frontItems) or []
	if ident == "notifications":
		items = [item for item in items if item.get("kind") == 50007]
	said = places.listText(ident, places.opened(items), how, thing, left=True)
	return said or places.nothingText(ident, opened_=True)


class PlaceItems:
	"""The things of a place of Windows as list_items gives them, so that click_item clicks one with the mouse in
	its middle, as on any window."""

	web = False

	def __init__(self, ident, items):
		self.place = ident
		self.title = places.nameOf(ident)
		self.items = [{"text": item["name"], "plain": item["name"], "kind": places.KINDS.get(item.get("kind"), "item"),
			"box": item["box"], "place": ident} for item in items if item.get("box")]
		boxes = [item["box"] for item in self.items] or [(0, 0, 1, 1)]
		left, top = min(b[0] for b in boxes), min(b[1] for b in boxes)
		right, bottom = max(b[2] for b in boxes), max(b[3] for b in boxes)
		self.imageInfo = _Frame(left, top, right - left, bottom - top)

	def screenPoint(self, item):
		left, top, right, bottom = item["box"]
		return (left + right) // 2, (top + bottom) // 2


class _Frame:
	"""Where a place is on the screen, in the shape click_item knows from a window's picture: places are given in
	the screen's own pixels, so nothing is converted."""

	def __init__(self, left, top, width, height):
		self.screenLeft, self.screenTop, self.screenWidth, self.screenHeight = left, top, max(1, width), max(1, height)

	def convertXToScreen(self, x):
		return x

	def convertYToScreen(self, y):
		return y


def itemsIn(ident, onMain):
	"""The things of a place that is always on the screen, for clicking, as PlaceItems; None when none were read
	there or the place is not on the screen now (a taskbar that hides itself)."""
	if ident in (places.TRAY, places.TASKBAR):
		shown = onMain(trayItems) or []
		kept = [item for item in places.usable(shown) if (places.isTray(item) if ident == places.TRAY else not places.isTray(item))]
	elif ident == places.DESKTOP:
		# Only while the desktop is in front: a click on a covered desktop would land on the window above it.
		if onMain(frontClass) not in ("Progman", "WorkerW"):
			return None
		kept = places.usable(onMain(desktopItems) or [])
	else:
		return None
	kept = [item for item in kept if item.get("box") and not item.get("offscreen")]
	return PlaceItems(ident, kept) if kept else None


def register(add, plugin, text, onMain):
	"""Add the tool that reads a place of Windows itself. Called from nvdatools.build."""

	def readPlace(task, asked):
		wish = places.wish(asked) or places.wish(task.request)
		if wish is None:
			named = places.named(asked) or places.named(task.request)
			if not named:
				raise ToolError(
					"The request does not name a part of Windows that can be read, such as the system tray, the taskbar, "
					"the desktop, the notifications, quick settings or the Start menu.")
			wish = {"places": named, "how": places.LIST, "thing": ""}
		said = []
		for ident in wish["places"]:
			task.check()
			said.append(read(ident, wish, onMain))
		return " ".join(said)

	add("read_place",
		"say what is in a part of Windows itself, read from what Windows tells screen readers: the icons of the "
		"system tray (notification area), also the hidden ones; the programs on the taskbar; the icons on the "
		"desktop; or the notifications, quick settings, the Start menu or clipboard history, which are opened first",
		readPlace, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Reading a part of Windows", tell=VERBATIM)
