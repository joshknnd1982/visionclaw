# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the focus put where the user needs it, and checked, never assumed.
# The owner found on 2026-11-19, testing 1.18.0: asked "check NVDA's log" with NVDA's logging off, he said yes to having
# NVDA's settings opened at the Logging level combo box, and the focus was on "Make screen black (immediate effect)"
# instead; then: "fix this bug. and fix any other similar focus task bugs too." What follows from it:
#   - A page of NVDA's settings is opened as NVDA's own menu opens it, and then the focus is put on the control the user
#     needs (openSettingsAt). Read from NVDA 2026.3.1's gui/settingsDialogs.py: MultiCategorySettingsDialog, opened with an
#     initialCategory, sets setPostInitFocus = self.container.SetFocus, so the focus goes to the first control of the page;
#     the page shown is dialog.currentCategory, the pages are dialog.categoryClasses, and selecting and focusing an item of
#     dialog.catListCtrl changes the page (as its onCharHook does for Control+Tab). gui/__init__.py popupSettingsDialog:
#     when the window is already open (MultiInstanceErrorWithDialog) it is only brought to the front, on whatever page it
#     shows, so the page is changed here. The control is found by the name NVDA gives it in its source: a page's attribute
#     (PrivacyAndSecuritySettingsPanel._logLevelCombo), or AutoSettingsMixin's f"{setting.id}List" for a voice setting
#     (SpeechSettingsPanel.voicePanel.voiceList). Read the source again for a newer NVDA.
#   - Where VisionClaw puts NVDA's focus on a control of a program (focusOn), it then checks that the focus is there before
#     it says so, and before any key is pressed for that control: a key pressed while the focus is elsewhere would change
#     something else.
# Never a fault: what cannot be done is said, and nothing is pressed.

import threading
import time

# How long a page of NVDA's settings is waited for, and how often it is looked at.
SETTINGS_SECONDS = 3.0
STEP_MS = 100
# How long the focus is waited for after it was put on a control of a program.
FOCUS_SECONDS = 0.8
FOCUS_STEP = 0.05
WAIT, GONE = "wait", "gone"


def settingsStep(windows, dialogClass, panelClass, find):
	"""One look at the open windows, by plain logic: the control to focus; WAIT while the settings window or its page is
	not there yet (the page is changed here when the window shows another one); GONE when the control does not exist or
	cannot take the focus. windows: the top-level windows."""
	dialog = next((window for window in windows if isinstance(window, dialogClass) and _shown(window)), None)
	if dialog is None:
		return WAIT
	panel = getattr(dialog, "currentCategory", None)
	if not isinstance(panel, panelClass):
		classes = list(getattr(dialog, "categoryClasses", ()) or ())
		if panelClass not in classes:
			return GONE
		index = classes.index(panelClass)
		try:
			dialog.catListCtrl.Select(index)
			dialog.catListCtrl.Focus(index)
		except Exception:
			return GONE
		return WAIT
	try:
		control = find(panel)
	except Exception:
		control = None
	if control is None or not _shown(control) or not _enabled(control):
		return GONE
	return control


def _shown(window):
	try:
		return bool(window.IsShown())
	except Exception:
		return False


def _enabled(window):
	try:
		return bool(window.IsEnabled())
	except Exception:
		return False


def openAt(dialogClass, panelClass, find, done=None, tries=None):
	"""Open NVDA's settings at panelClass, as NVDA's menu does, and put the focus on find(page). done(True) once the focus is
	on it, done(False) where it could not be. Main thread."""
	import gui
	gui.mainFrame.popupSettingsDialog(dialogClass, panelClass)
	_later(dialogClass, panelClass, find, done, int(SETTINGS_SECONDS * 1000 / STEP_MS) if tries is None else tries)


def _later(dialogClass, panelClass, find, done, tries):
	import wx
	wx.CallLater(STEP_MS, _look, dialogClass, panelClass, find, done, tries)


def _look(dialogClass, panelClass, find, done, tries):
	import wx
	try:
		found = settingsStep(wx.GetTopLevelWindows(), dialogClass, panelClass, find)
	except Exception:
		found = GONE
	if found == WAIT and tries > 0:
		_later(dialogClass, panelClass, find, done, tries - 1)
		return
	ok = False
	if found not in (WAIT, GONE):
		try:
			found.SetFocus()
			ok = True
		except Exception:
			ok = False
	if done is not None:
		try:
			done(ok)
		except Exception:
			pass


def openSettingsAt(dialogClass, panelClass, find, cancel=None):
	"""openAt from a worker thread: waits until the focus is on the control, or could not be put there, at most a few
	seconds. Returns whether it is there."""
	import wx
	finished = threading.Event()
	result = {"ok": False}

	def done(ok):
		result["ok"] = ok
		finished.set()

	wx.CallAfter(openAt, dialogClass, panelClass, find, done)
	end = time.monotonic() + SETTINGS_SECONDS + 1.0
	while not finished.wait(0.05):
		if time.monotonic() > end or (cancel is not None and cancel.is_set()):
			break
	return result["ok"]


def isFocus(obj, focus):
	"""Whether NVDA's focus is the object, or inside it (a combo box's own edit field, a list's item). Plain logic."""
	try:
		current, depth = focus, 0
		while current is not None and depth < 4:
			if current == obj:
				return True
			current, depth = current.parent, depth + 1
	except Exception:
		return False
	return False


def focusOn(obj, onMain, cancel=None, seconds=FOCUS_SECONDS):
	"""Put NVDA's focus on an object of a program and check that it is there. Returns True when it is; False when the
	program did not move the focus there. Worker thread; onMain runs a function on NVDA's main thread."""
	import api
	try:
		onMain(lambda: obj.setFocus())
	except Exception:
		return False
	end = time.monotonic() + seconds
	while True:
		try:
			if onMain(lambda: isFocus(obj, api.getFocusObject())):
				return True
		except Exception:
			return False
		if time.monotonic() > end or (cancel is not None and cancel.is_set()):
			return False
		time.sleep(FOCUS_STEP)


def focusName(onMain):
	"""What has NVDA's focus now, in a few words: its name and kind. "" when it cannot be told."""
	import api
	try:
		def name():
			focus = api.getFocusObject()
			role = getattr(getattr(focus, "role", None), "displayString", "") or ""
			return " ".join(f"{focus.name or ''} {role}".split())
		return onMain(name) or ""
	except Exception:
		return ""
