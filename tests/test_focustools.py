# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The focus put where the user needs it, and checked (focustools.py): a page of NVDA's settings opened at the control the
user needs, also when the window is open at another page; a control that cannot take the focus said to be so; the focus
on a program's control checked before it is said or before a key is pressed. Plain Python, with stand-ins for NVDA's
settings window, its objects and its main thread.

  python tests/test_focustools.py
"""
import sys
import types

import harness  # noqa: F401

api = types.ModuleType("api")
sys.modules.setdefault("api", api)
api = sys.modules["api"]
from visionClaw import focustools  # noqa: E402


class Control:
	def __init__(self, shown=True, enabled=True):
		self.shown, self.enabled, self.focused = shown, enabled, 0

	def IsShown(self):
		return self.shown

	def IsEnabled(self):
		return self.enabled

	def SetFocus(self):
		self.focused += 1


class PrivacyPage:
	def __init__(self):
		self.curtain, self._logLevelCombo = Control(), Control()


class SpeechPage:
	def __init__(self):
		self.voicePanel = types.SimpleNamespace(voiceList=Control(), rateSlider=Control())


class CategoryList:
	"""Stands in for catListCtrl: selecting and focusing an item changes the page, as in NVDA."""

	def __init__(self, window):
		self.window = window

	def Select(self, index):
		self.selected = index

	def Focus(self, index):
		self.window.currentCategory = self.window.categoryClasses[index]()


class SettingsWindow:
	def __init__(self, page, shown=True):
		self.categoryClasses = [SpeechPage, PrivacyPage]
		self.currentCategory = page()
		self.catListCtrl = CategoryList(self)
		self.shown = shown

	def IsShown(self):
		return self.shown


class OtherWindow:
	def IsShown(self):
		return True


combo = lambda page: getattr(page, "_logLevelCombo", None)  # noqa: E731
# Nothing open yet: wait.
assert focustools.settingsStep([OtherWindow()], SettingsWindow, PrivacyPage, combo) == focustools.WAIT
assert focustools.settingsStep([SettingsWindow(PrivacyPage, shown=False)], SettingsWindow, PrivacyPage, combo) == focustools.WAIT
# Open at the page: the Logging level combo box, not the page's first control.
window = SettingsWindow(PrivacyPage)
found = focustools.settingsStep([OtherWindow(), window], SettingsWindow, PrivacyPage, combo)
assert found is window.currentCategory._logLevelCombo
# Already open at another page (NVDA only brings it to the front): the page is changed, then the control is found.
window = SettingsWindow(SpeechPage)
assert focustools.settingsStep([window], SettingsWindow, PrivacyPage, combo) == focustools.WAIT
assert isinstance(window.currentCategory, PrivacyPage) and window.catListCtrl.selected == 1
assert focustools.settingsStep([window], SettingsWindow, PrivacyPage, combo) is window.currentCategory._logLevelCombo
# A control that is not there, or cannot take the focus (a level forced by NVDA's command line): gone, nothing focused.
window = SettingsWindow(PrivacyPage)
window.currentCategory._logLevelCombo.enabled = False
assert focustools.settingsStep([window], SettingsWindow, PrivacyPage, combo) == focustools.GONE
assert focustools.settingsStep([SettingsWindow(SpeechPage)], SettingsWindow, PrivacyPage, lambda page: None) == focustools.WAIT
assert focustools.settingsStep([SettingsWindow(PrivacyPage)], SettingsWindow, PrivacyPage, lambda page: None) == focustools.GONE


class OddPage:
	pass


assert focustools.settingsStep([SettingsWindow(PrivacyPage)], SettingsWindow, OddPage, combo) == focustools.GONE

# The look that runs after NVDA opened the window: the control gets the focus once, and done is told.
wx = types.ModuleType("wx")
windows = []
wx.GetTopLevelWindows = lambda: list(windows)
wx.CallLater = lambda ms, fn, *args: fn(*args)
sys.modules["wx"] = wx
told = []
window = SettingsWindow(PrivacyPage)
windows.append(window)
focustools._look(SettingsWindow, PrivacyPage, combo, told.append, 3)
assert told == [True] and window.currentCategory._logLevelCombo.focused == 1 and window.currentCategory.curtain.focused == 0
windows.clear()
focustools._look(SettingsWindow, PrivacyPage, combo, told.append, 3)
assert told == [True, False], "no window within the tries: told it could not"
# --- The focus on a program's control is checked, never assumed ---


class Obj:
	def __init__(self, name, parent=None, takes=True):
		self.name, self.parent, self.takes = name, parent, takes

	def setFocus(self):
		if self.takes:
			state["focus"] = self


state = {"focus": None}
api.getFocusObject = lambda: state["focus"]
onMain = lambda fn, *args: fn(*args)  # noqa: E731
combo = Obj("Quality")
inner = Obj("Quality edit", parent=combo)
assert focustools.isFocus(combo, combo) and focustools.isFocus(combo, inner) and not focustools.isFocus(combo, Obj("Other"))
assert focustools.focusOn(combo, onMain)
stubborn = Obj("Drawn knob", takes=False)
state["focus"] = Obj("Play button")
assert not focustools.focusOn(stubborn, onMain, seconds=0.1)
assert state["focus"].name == "Play button", "the focus stays where it was, and nothing claims otherwise"

print("test_focustools: OK")
