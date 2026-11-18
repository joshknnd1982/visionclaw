# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the window that shows what VisionClaw remembers, worked with the keyboard alone: a list of every
# memory with a check box each, the whole of the memory that is selected in a box that can be read line by
# line, and buttons that delete the checked memories, delete all of them to start over, open a memory to
# change it, and open the folder. Nothing is deleted without a question. The memories are the Markdown files
# of claw/memories.py; this window only shows and deletes them.

import os

import addonHandler
import gui
import ui
import wx

from .claw import debuglog, memories

addonHandler.initTranslation()


class MemoriesDialog(wx.Dialog):
	"""What VisionClaw remembers, and deleting some or all of it."""

	def __init__(self, parent, kept):
		# Translators: Title of the window that shows what VisionClaw remembers.
		super().__init__(parent, title=_("VisionClaw: what it remembers"))
		self._kept = kept
		self._entries = []
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the list of memories.
		main.Add(wx.StaticText(self, label=_("&Memories. Check the ones you want VisionClaw to forget:")),
			flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		try:
			from gui import nvdaControls
			self.list = nvdaControls.CustomCheckListBox(self, choices=[])
		except Exception:
			self.list = wx.CheckListBox(self, choices=[])
		main.Add(self.list, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		# Translators: Label of the box that shows the whole of the selected memory.
		main.Add(wx.StaticText(self, label=_("The selected memory, &whole:")), flag=wx.LEFT | wx.RIGHT, border=10)
		self.detail = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(560, 120))
		main.Add(self.detail, flag=wx.ALL | wx.EXPAND, border=10)
		self.total = wx.StaticText(self, label="")
		main.Add(self.total, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that deletes the checked memories.
		self.forgetBtn = wx.Button(self, label=_("&Forget checked memories"))
		# Translators: Button that deletes every memory, so that VisionClaw starts over.
		self.forgetAllBtn = wx.Button(self, label=_("Forget &all and start over"))
		# Translators: Button that opens the selected memory in a text editor, to read or change it.
		self.openBtn = wx.Button(self, label=_("&Open the selected memory to change it"))
		# Translators: Button that opens the folder where the memories are kept.
		self.folderBtn = wx.Button(self, label=_("Open the f&older"))
		# Translators: Button that closes the window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("C&lose"))
		for button in (self.forgetBtn, self.forgetAllBtn, self.openBtn, self.folderBtn, closeBtn):
			buttons.Add(button, flag=wx.RIGHT, border=10)
		main.Add(buttons, flag=wx.ALL, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.CentreOnScreen()
		self.list.Bind(wx.EVT_LISTBOX, lambda e: self._showDetail())
		self.forgetBtn.Bind(wx.EVT_BUTTON, lambda e: self._forget(checkedOnly=True))
		self.forgetAllBtn.Bind(wx.EVT_BUTTON, lambda e: self._forget(checkedOnly=False))
		self.openBtn.Bind(wx.EVT_BUTTON, lambda e: self._open(selected=True))
		self.folderBtn.Bind(wx.EVT_BUTTON, lambda e: self._open(selected=False))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())
		# The files may have been changed or deleted by hand while the window was in the background.
		self.Bind(wx.EVT_ACTIVATE, lambda e: (self.refresh() if e.GetActive() else None, e.Skip()))
		self.refresh()
		self.list.SetFocus()

	def refresh(self):
		"""Read the memories again from the disk, keeping the selection and the check marks where they can."""
		selected = self._selected()
		checked = {self._entries[i].name for i in self.list.GetCheckedItems() if i < len(self._entries)}
		self._entries = list(reversed(self._kept.all()))  # the newest first
		self.list.Set([
			f"{entry.text()} ({memories.KIND_NAMES.get(entry.kind, entry.kind)}"
			+ (f", kept {entry.saved})" if entry.saved else ")") for entry in self._entries])
		for at, entry in enumerate(self._entries):
			if entry.name in checked:
				self.list.Check(at)
		if self._entries:
			names = [entry.name for entry in self._entries]
			self.list.SetSelection(names.index(selected.name) if selected and selected.name in names else 0)
			# Translators: How many memories there are. {count} is the number.
			self.total.SetLabel(_("VisionClaw remembers {count} things.").format(count=len(self._entries))
				if len(self._entries) != 1 else _("VisionClaw remembers one thing."))
		else:
			# Translators: Shown when VisionClaw remembers nothing.
			self.total.SetLabel(_("VisionClaw remembers nothing. Ask it to remember something, and it will."))
		for button in (self.forgetBtn, self.forgetAllBtn, self.openBtn):
			button.Enable(bool(self._entries))
		self._showDetail()

	def _selected(self):
		at = self.list.GetSelection()
		return self._entries[at] if 0 <= at < len(self._entries) else None

	def _showDetail(self):
		entry = self._selected()
		if entry is None:
			self.detail.SetValue("")
			return
		lines = [entry.body or entry.title]
		if entry.asked:
			# Translators: In the whole of a memory: the user's own words when they asked for it.
			lines.append(_("In your words: {words}").format(words=entry.asked))
		if entry.program:
			# Translators: In the whole of a memory: the program it is about.
			lines.append(_("About the program: {program}").format(program=entry.program))
		# Translators: In the whole of a memory: the file it is kept in.
		lines.append(_("Kept in the file: {path}").format(path=self._kept.path(entry.name)))
		self.detail.SetValue("\n".join(lines))

	def _forget(self, checkedOnly):
		if checkedOnly:
			chosen = [self._entries[i] for i in self.list.GetCheckedItems() if i < len(self._entries)]
			if not chosen:
				# Translators: Reported when Forget is pressed and no memory is checked.
				ui.message(_("No memory is checked. Press Space on a memory to check it."))
				return
			# Translators: Asked before the checked memories are deleted. {count} is how many.
			question = _("Forget the {count} checked memories? Their files are deleted from this computer.").format(
				count=len(chosen))
		else:
			chosen = list(self._entries)
			# Translators: Asked before every memory is deleted.
			question = _(
				"Forget everything VisionClaw remembers, {count} memories, and start over? Their files are deleted from "
				"this computer.").format(count=len(chosen))
		gui.mainFrame.prePopup()
		try:
			# Translators: Title of the question asked before memories are deleted.
			answer = gui.messageBox(question, _("Forget memories"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
		finally:
			gui.mainFrame.postPopup()
		if answer != wx.YES:
			return
		gone = [entry for entry in chosen if self._kept.remove(entry.name)]
		self._kept.writeIndex()
		debuglog.log("memories", f"The user deleted {len(gone)} of {len(chosen)} memories in the memories window")
		self.refresh()
		self.list.SetFocus()
		if len(gone) < len(chosen):
			# Translators: Reported when some memories could not be deleted.
			ui.message(_("{count} memories could not be deleted. They are in the folder {folder}.").format(
				count=len(chosen) - len(gone), folder=self._kept.folder))
		elif not self._entries:
			# Translators: Reported when every memory was deleted.
			ui.message(_("Forgotten. VisionClaw remembers nothing now and starts over."))
		else:
			# Translators: Reported after some memories were deleted. {count} is how many.
			ui.message(_("Forgotten: {count}.").format(count=len(gone)))

	def _open(self, selected):
		try:
			if selected:
				entry = self._selected()
				if entry is not None:
					os.startfile(self._kept.path(entry.name))
			else:
				self._kept.writeIndex()
				os.startfile(self._kept.folder)
		except OSError as e:
			debuglog.error("memories", "A memory or the folder could not be opened", e)
			# Translators: Reported when a memory or its folder could not be opened. {error} is the reason.
			ui.message(_("It could not be opened: {error}").format(error=e))


def show(plugin):
	"""Shows the window, or brings it to the front if it is open. Main thread."""
	dialog = getattr(plugin, "_memoriesDialog", None)
	try:
		if dialog:
			dialog.refresh()
			dialog.Raise()
			return
	except RuntimeError:
		pass  # the window was closed: wx says so this way
	plugin._memoriesDialog = MemoriesDialog(gui.mainFrame, plugin.memories)
	gui.mainFrame.prePopup()
	plugin._memoriesDialog.Show()
	plugin._memoriesDialog.Raise()
	gui.mainFrame.postPopup()
