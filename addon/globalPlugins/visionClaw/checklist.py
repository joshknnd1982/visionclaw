# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a list of check boxes that NVDA reads, and a question answered by checking some of them.
# wx.CheckListBox alone, which is also the list inside wx.MultiChoiceDialog, tells NVDA neither that an item is a
# check box nor whether it is checked: Space checks an item without a word, so the list seems not to work at all
# (the owner, 2026-11-19, of the question before models are suggested). NVDA's own
# gui.nvdaControls.CustomCheckListBox, read from NVDA's source (branch release-2026.3, gui/nvdaControls.py) on
# 2026-11-19, reports every item as a check box with its state, and tells NVDA when Space changes it. NVDA's
# gui.guiHelper makes a subclass of the class it is given, so checkListClass gives a class, never a function.
# Where NVDA's control cannot be had, as in the tests, the plain one is used.

import addonHandler
import wx

addonHandler.initTranslation()


def checkListClass():
	"""The class of a list of check boxes NVDA reads: NVDA's own where there is one, else wx's."""
	try:
		from gui import nvdaControls
		return nvdaControls.CustomCheckListBox
	except Exception:
		return wx.CheckListBox


def checkList(parent, choices=(), **kwargs):
	"""A list of check boxes NVDA reads: each item a check box, checked or not, and said when Space changes it."""
	cls = checkListClass()
	try:
		return cls(parent, choices=list(choices), **kwargs)
	except Exception:
		if cls is wx.CheckListBox:
			raise
		return wx.CheckListBox(parent, choices=list(choices), **kwargs)


class ChecksDialog(wx.Dialog):
	"""A question answered by checking one or more choices with Space and pressing Enter, worked with the keyboard
	alone. In place of wx.MultiChoiceDialog, whose list NVDA cannot read. The question is the list's label, so NVDA
	reads it when the list gets the focus; the first choice is selected, so NVDA says it and whether it is checked."""

	def __init__(self, parent, question, title, choices, checked=()):
		super().__init__(parent, title=title)
		main = wx.BoxSizer(wx.VERTICAL)
		main.Add(wx.StaticText(self, label=question), flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.list = checkList(self, choices)
		for at in checked:
			self.list.Check(at)
		main.Add(self.list, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		main.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(main)
		self.CentreOnScreen()
		if self.list.GetCount():
			self.list.SetSelection(0)
		self.list.SetFocus()

	def checked(self):
		"""The places of the checked choices, in the order of the list."""
		return sorted(self.list.GetCheckedItems())
