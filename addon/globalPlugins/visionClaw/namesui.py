# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the window of saved object names (NVDA+Alt+N pressed twice, or the button in VisionClaw's settings),
# worked with the keyboard alone: the programs and websites that have names, the names of the one selected with who
# gave each and how sure it is, and buttons that change a name, forget names, save names to a file to share with other
# VisionClaw users, and add names from such a file. A shared file is plain data that names programs and websites; it
# is checked before anything in it is used (claw/naming.py readShared), and it never replaces the user's own names.

import os

import addonHandler
import gui
import ui
import wx

from . import checklist
from .claw import debuglog, naming

addonHandler.initTranslation()

# The file name offered when names are shared.
SHARE_FILE = "VisionClaw object names.json"


class NamesDialog(wx.Dialog):
	"""Saved object names: read, change, forget, share, and add shared ones."""

	def __init__(self, parent, plugin):
		# Translators: Title of the window of saved object names.
		super().__init__(parent, title=_("VisionClaw: saved object names"))
		self._plugin = plugin
		self._store = plugin.labels
		self._places = []
		self._names = []
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the list of programs and websites that have saved object names.
		main.Add(wx.StaticText(self, label=_("&Programs and websites with saved names:")),
			flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.placeList = wx.ListBox(self, size=(560, 140))
		main.Add(self.placeList, flag=wx.ALL | wx.EXPAND, border=10)
		# Translators: Label of the list of saved names of the selected program or website.
		main.Add(wx.StaticText(self, label=_("&Names there. Check the ones to forget:")),
			flag=wx.LEFT | wx.RIGHT, border=10)
		self.nameList = checklist.checkList(self, size=(560, 200))
		main.Add(self.nameList, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		self.total = wx.StaticText(self, label="")
		main.Add(self.total, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that changes the selected saved name.
		self.changeBtn = wx.Button(self, label=_("&Change the selected name..."))
		# Translators: Button that forgets the checked saved names.
		self.forgetBtn = wx.Button(self, label=_("&Forget checked names"))
		# Translators: Button that forgets every saved name of the selected program or website.
		self.forgetPlaceBtn = wx.Button(self, label=_("Forget &all names of this place"))
		# Translators: Button that saves names to a file, to give to other VisionClaw users.
		self.shareBtn = wx.Button(self, label=_("&Share names..."))
		# Translators: Button that adds names from a file another VisionClaw user shared.
		self.addBtn = wx.Button(self, label=_("A&dd shared names..."))
		# Translators: Button that closes the window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("C&lose"))
		for button in (self.changeBtn, self.forgetBtn, self.forgetPlaceBtn, self.shareBtn, self.addBtn, closeBtn):
			buttons.Add(button, flag=wx.RIGHT, border=8)
		main.Add(buttons, flag=wx.ALL, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.CentreOnScreen()
		self.placeList.Bind(wx.EVT_LISTBOX, lambda e: self._showNames())
		self.changeBtn.Bind(wx.EVT_BUTTON, lambda e: self._change())
		self.forgetBtn.Bind(wx.EVT_BUTTON, lambda e: self._forget(checkedOnly=True))
		self.forgetPlaceBtn.Bind(wx.EVT_BUTTON, lambda e: self._forget(checkedOnly=False))
		self.shareBtn.Bind(wx.EVT_BUTTON, lambda e: self._share())
		self.addBtn.Bind(wx.EVT_BUTTON, lambda e: self._add())
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())
		self.refresh()
		self.placeList.SetFocus()

	# --- What is shown ---

	@staticmethod
	def placeText(scope, count):
		scope = str(scope or "")
		if scope.startswith("site:"):
			# Translators: A website in the list of saved object names. {site} is its address, {count} how many names.
			return _("website {site}, {count} names").format(site=scope[5:], count=count)
		# Translators: A program in the list of saved object names. {program} is its name, {count} how many names.
		return _("program {program}, {count} names").format(program=scope, count=count)

	@staticmethod
	def nameText(entry):
		kind = naming.kindWord(entry.get("role") or "")
		if entry["by"] == naming.YOU:
			# Translators: Who gave a saved name: the user.
			who = _("your name")
		elif entry["by"] == naming.PERSON:
			# Translators: Who gave a saved name: a person, in a file someone shared.
			who = _("shared by a person")
		elif entry.get("sure"):
			# Translators: Who gave a saved name: the model, and what is written in the picture agrees.
			who = _("by the model, checked against its picture or its code")
		else:
			# Translators: Who gave a saved name: the model, which is not sure, so NVDA says "probably" before it.
			who = _("guessed by the model, said with probably")
		return f"{entry['name']}, {kind}, {who}"

	def refresh(self):
		selected = self._selectedPlace()
		self._places = self._store.places()
		self.placeList.Set([self.placeText(scope, count) for scope, count in self._places])
		if self._places:
			scopes = [scope for scope, _count in self._places]
			self.placeList.SetSelection(scopes.index(selected) if selected in scopes else 0)
			total = sum(count for _scope, count in self._places)
			# Translators: How many names are saved. {names} and {places} are numbers.
			self.total.SetLabel(_("{names} names saved for {places} programs and websites.").format(
				names=total, places=len(self._places)))
		else:
			# Translators: Shown when no object names are saved.
			self.total.SetLabel(_(
				"No names are saved yet. Turn object names on with NVDA+Alt+B, or give an object your own name with "
				"NVDA+Alt+N."))
		for button in (self.changeBtn, self.forgetBtn, self.forgetPlaceBtn, self.shareBtn):
			button.Enable(bool(self._places))
		self._showNames()

	def _selectedPlace(self):
		at = self.placeList.GetSelection()
		return self._places[at][0] if 0 <= at < len(self._places) else None

	def _showNames(self):
		scope = self._selectedPlace()
		self._names = self._store.entries(scope) if scope else []
		self.nameList.Set([self.nameText(entry) for _key, entry in self._names])
		if self._names:
			self.nameList.SetSelection(0)

	# --- Changing and forgetting ---

	def _change(self):
		scope = self._selectedPlace()
		at = self.nameList.GetSelection()
		if scope is None or not 0 <= at < len(self._names):
			# Translators: Reported when Change is pressed and no name is selected.
			ui.message(_("Select a name in the list of names first."))
			return
		key, entry = self._names[at]
		# Translators: Title and prompt of the window that changes a saved name.
		dialog = wx.TextEntryDialog(self, _("Name (leave empty to remove your name):"), _("VisionClaw name"),
			value=entry["name"])
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			name = dialog.GetValue().strip()
		finally:
			dialog.Destroy()
		self._store.setUser(scope, key, name, entry.get("role") or "")
		debuglog.log("names", f"The user changed a saved name in {scope} to {name!r}")
		self.refresh()
		self.nameList.SetFocus()
		# Translators: Reported after a name was saved or removed.
		ui.message(_("Name saved") if name else _("Name removed"))

	def _forget(self, checkedOnly):
		scope = self._selectedPlace()
		if scope is None:
			return
		if checkedOnly:
			chosen = [self._names[i][0] for i in self.nameList.GetCheckedItems() if i < len(self._names)]
			if not chosen:
				# Translators: Reported when Forget is pressed and no name is checked.
				ui.message(_("No name is checked. Press Space on a name to check it."))
				return
			# Translators: Asked before the checked names are forgotten. {count} is how many.
			question = _("Forget the {count} checked names? Where an object has no other name, it is named again when "
				"you reach it while object names are on.").format(count=len(chosen))
		else:
			chosen = None
			# Translators: Asked before every name of a program or website is forgotten. {place} is its name.
			question = _("Forget every saved name of {place}?").format(place=self.placeText(scope, len(self._names)))
		# Translators: Title of the question asked before names are forgotten.
		if gui.messageBox(question, _("Forget names"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
			return
		if chosen is None:
			self._store.forgetPlace(scope)
			count = len(self._names)
		else:
			count = sum(1 for key in chosen if self._store.forget(scope, key))
		debuglog.log("names", f"The user forgot {count} saved names of {scope}")
		self.refresh()
		self.placeList.SetFocus()
		# Translators: Reported after names were forgotten. {count} is how many.
		ui.message(_("Forgotten: {count}.").format(count=count))

	# --- Sharing ---

	def _share(self):
		if not self._places:
			return
		selected = self.placeList.GetSelection()
		dialog = checklist.ChecksDialog(
			self,
			# Translators: The question before names are saved to a file to share. The file names the programs and
			# websites, so the user chooses which.
			_("Check the programs and websites whose names to share. The file names them, and nothing else about you."),
			# Translators: Title of the window that chooses which names to share.
			_("Share names"),
			[self.placeText(scope, count) for scope, count in self._places], checked=[selected] if selected >= 0 else [])
		try:
			if dialog.ShowModal() != wx.ID_OK:
				return
			chosen = [self._places[at][0] for at in dialog.checked()]
		finally:
			dialog.Destroy()
		if not chosen:
			# Translators: Reported when nothing was checked to share.
			ui.message(_("Nothing was checked, so nothing was shared."))
			return
		files = wx.FileDialog(
			# Translators: Title of the window that saves names to a file.
			self, _("Save the names to a file"), defaultFile=SHARE_FILE,
			# Translators: The kind of file names are shared in.
			wildcard=_("VisionClaw names") + " (*.json)|*.json", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
		try:
			if files.ShowModal() != wx.ID_OK:
				return
			path = files.GetPath()
		finally:
			files.Destroy()
		import json
		data = self._store.shared(chosen, maker=_version())
		try:
			with open(path, "w", encoding="utf-8") as f:
				json.dump(data, f, ensure_ascii=False, indent="\t")
		except OSError as e:
			debuglog.error("names", "The names could not be saved to a file", e)
			# Translators: Reported when the names could not be saved. {error} is the reason.
			ui.message(_("The names could not be saved: {error}").format(error=e))
			return
		debuglog.log("names", f"The user shared {len(data['names'])} names of {len(chosen)} places to {path}")
		# Translators: Reported after names were saved to a file. {count} and {places} are numbers, {file} its name.
		ui.message(_(
			"Saved {count} names of {places} programs and websites to {file}. Give the file to another VisionClaw user, "
			"who adds it with Add shared names. A name read from a picture fits only where the object looks exactly "
			"the same.").format(count=len(data["names"]), places=len(chosen), file=os.path.basename(path)))

	def _add(self):
		files = wx.FileDialog(
			# Translators: Title of the window that opens a file of shared names.
			self, _("Open a file of names another VisionClaw user shared"),
			wildcard=_("VisionClaw names") + " (*.json)|*.json", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		try:
			if files.ShowModal() != wx.ID_OK:
				return
			path = files.GetPath()
		finally:
			files.Destroy()
		try:
			if os.path.getsize(path) > naming.MAX_SHARED_BYTES:
				raise ValueError(_("This file is too big to be a file of names."))
			with open(path, "rb") as f:
				data = f.read()
			added, replaced, kept = self._store.addShared(data)
		except (OSError, ValueError) as e:
			debuglog.error("names", f"Shared names could not be added from {path}", e)
			# Translators: Reported when a file of shared names could not be used. {error} is the reason.
			ui.message(_("Nothing was added: {error}").format(error=e))
			return
		self._plugin.namer.refresh()
		debuglog.log("names", f"Added shared names from {path}: {added} new, {replaced} replaced, {kept} kept")
		self.refresh()
		self.placeList.SetFocus()
		# Translators: Reported after shared names were added. {added}, {replaced} and {kept} are numbers.
		ui.message(_(
			"Added {added} names. {replaced} guesses were replaced with better names. {kept} names you already had were "
			"kept as they are.").format(added=added, replaced=replaced, kept=kept))


def _version():
	try:
		return "VisionClaw " + addonHandler.getCodeAddon().manifest["version"]
	except Exception:
		return "VisionClaw"


def show(plugin, parent=None):
	"""Shows the window, or brings it to the front if it is open. Main thread."""
	dialog = getattr(plugin, "_namesDialog", None)
	try:
		if dialog:
			dialog.refresh()
			dialog.Raise()
			return
	except RuntimeError:
		pass  # the window was closed: wx says so this way
	plugin._namesDialog = NamesDialog(parent or gui.mainFrame, plugin)
	gui.mainFrame.prePopup()
	plugin._namesDialog.Show()
	plugin._namesDialog.Raise()
	gui.mainFrame.postPopup()
