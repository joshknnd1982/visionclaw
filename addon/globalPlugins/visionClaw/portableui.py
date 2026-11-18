# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the window that makes a portable copy of VisionClaw with everything in it: the add-on, its
# engine, every model, guide, lesson, note, memory, skill and log in its data folder, nothing left out, and
# its settings. Two ways, chosen by the user:
#   one .nvda-addon file, to install on any computer: opened there, NVDA asks before it installs it;
#   straight into a portable NVDA, as on a flash drive: VisionClaw then starts with that NVDA.
# A portable NVDA itself is made with NVDA's own window (Tools, Create portable copy); a button opens it. With
# "Copy current user configuration" checked there, VisionClaw comes along with everything, because its data
# is inside its add-on folder.
# Everything is said in words and worked from the keyboard; the copy runs in the background with a progress
# bar NVDA reports, and can be stopped. The work itself is claw/portable.py.

import ctypes
import os
import shutil
import threading

import addonHandler
import gui
import ui
import wx

from .claw import debuglog, guides, portable

addonHandler.initTranslation()

FILE, INTO_NVDA = 0, 1
STEPS = 1000


def partName(name):
	"""What a folder or file of the data folder holds, in words."""
	names = {
		# Translators: What a part of VisionClaw's data folder holds, in the window that makes a portable copy.
		"models": _("the models"),
		# Translators: What a part of VisionClaw's data folder holds.
		"guides": _("the developer guides"),
		# Translators: What a part of VisionClaw's data folder holds.
		"training": _("the training material"),
		# Translators: What a part of VisionClaw's data folder holds.
		"notes": _("notes on programs"),
		# Translators: What a part of VisionClaw's data folder holds.
		"memories": _("what you asked VisionClaw to remember"),
		# Translators: What a part of VisionClaw's data folder holds.
		"library": _("your library of documents"),
		# Translators: What a part of VisionClaw's data folder holds.
		"skills": _("your own skills"),
		# Translators: What a part of VisionClaw's data folder holds.
		"help": _("NVDA's help as Markdown"),
		# Translators: What a part of VisionClaw's data folder holds.
		"logs": _("VisionClaw's logs"),
		# Translators: What a part of VisionClaw's data folder holds.
		"updates": _("downloaded versions of VisionClaw"),
	}
	return names.get(name, name)


def fileSystemOf(folder):
	"""The name of the file system a folder is on, such as NTFS, exFAT or FAT32, or "" when Windows does not say."""
	root = os.path.splitdrive(os.path.abspath(folder))[0] + "\\"
	name = ctypes.create_unicode_buffer(64)
	try:
		if ctypes.windll.kernel32.GetVolumeInformationW(root, None, 0, None, None, None, name, len(name)):
			return name.value
	except Exception:
		pass
	return ""


def _ask(question, title, parent):
	gui.mainFrame.prePopup()
	try:
		return gui.messageBox(question, title, wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, parent) == wx.YES
	finally:
		gui.mainFrame.postPopup()


def _tell(text, title, parent, icon=wx.ICON_INFORMATION):
	gui.mainFrame.prePopup()
	try:
		gui.messageBox(text, title, wx.OK | icon, parent)
	finally:
		gui.mainFrame.postPopup()


class PortableDialog(wx.Dialog):
	"""Make a portable copy of VisionClaw with everything in it."""

	def __init__(self, parent, plugin):
		# Translators: Title of the window that makes a portable copy of VisionClaw.
		super().__init__(parent, title=_("VisionClaw: make a portable copy"))
		self.plugin = plugin
		self._stop = None
		self._progress = None
		self._lastStep = -1
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the box that says what goes into a portable copy of VisionClaw.
		main.Add(wx.StaticText(self, label=_("&What goes into the copy, and how:")), flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.summary = wx.TextCtrl(self, value=self.summaryText(), style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
			size=(600, 220))
		main.Add(self.summary, flag=wx.ALL | wx.EXPAND, border=10)
		# Translators: Label of the choice of what kind of portable copy to make.
		self.kind = wx.RadioBox(self, label=_("Make"), choices=[
			# Translators: A kind of portable copy of VisionClaw.
			_("One file that installs VisionClaw with everything on any computer (.nvda-addon)"),
			# Translators: A kind of portable copy of VisionClaw.
			_("VisionClaw with everything, straight into a portable NVDA, as on a flash drive"),
		], majorDimension=1, style=wx.RA_SPECIFY_COLS)
		main.Add(self.kind, flag=wx.ALL | wx.EXPAND, border=10)
		row = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Label of the folder a portable copy is put into.
		row.Add(wx.StaticText(self, label=_("&Folder or drive to put it in:")), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)
		self.folder = wx.TextCtrl(self, size=(360, -1))
		row.Add(self.folder, proportion=1, flag=wx.RIGHT, border=10)
		# Translators: Button that opens Windows' window for choosing a folder.
		self.browseBtn = wx.Button(self, label=_("&Browse..."))
		row.Add(self.browseBtn)
		main.Add(row, flag=wx.ALL | wx.EXPAND, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that makes the portable copy.
		self.makeBtn = wx.Button(self, label=_("&Make the copy"))
		# Translators: Button that opens NVDA's own window for making a portable NVDA.
		self.nvdaBtn = wx.Button(self, label=_("Make a portable &NVDA with NVDA's own window..."))
		# Translators: Button that closes the window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("C&lose"))
		for button in (self.makeBtn, self.nvdaBtn, closeBtn):
			buttons.Add(button, flag=wx.RIGHT, border=10)
		main.Add(buttons, flag=wx.ALL, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.makeBtn.SetDefault()
		self.CentreOnScreen()
		self.browseBtn.Bind(wx.EVT_BUTTON, lambda e: self._browse())
		self.makeBtn.Bind(wx.EVT_BUTTON, lambda e: self._make())
		self.nvdaBtn.Bind(wx.EVT_BUTTON, lambda e: self._openNvdaWindow())
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self.summary.SetFocus()

	def version(self):
		try:
			return addonHandler.getCodeAddon().manifest["version"]
		except Exception:
			return "unknown"

	def summaryText(self):
		dataDir = self.plugin.dataDir
		found = portable.files(self.plugin.addonDir)
		total = sum(size for _full, _arc, size in found)
		inData = [f for f in found if f[1].startswith(portable.DATA + "/")]
		lines = [
			# Translators: In the window that makes a portable copy. {version} is VisionClaw's version, {count} a
			# number of files, {size} a size such as 8.6 GB.
			_("Everything VisionClaw has here, nothing left out: VisionClaw {version} with its engine, and its whole "
				"data folder, {count} files. {size} in all.").format(
				version=self.version(), count=len(inData), size=portable.sizeText(total)),
		]
		for name, size, count in portable.parts(dataDir):
			# Translators: One part of VisionClaw's data folder. {what} says what it holds, {size} its size.
			lines.append(_("{what}: {size}").format(what=partName(name), size=portable.sizeText(size)))
		lines += [
			# Translators: In the window that makes a portable copy.
			_("Your VisionClaw settings come with it. Another NVDA takes them over when its VisionClaw has no models "
				"chosen yet; one that was used already keeps its own."),
			# Translators: In the window that makes a portable copy: the first way.
			_("One file that installs: put it on a flash drive or send it, and open it on the other computer while "
				"NVDA is running. NVDA asks before it installs it. Where VisionClaw is there already, what that "
				"computer has is kept and the rest is added."),
			# Translators: In the window that makes a portable copy: the second way.
			_("Straight into a portable NVDA: choose the folder of a portable NVDA, or the drive it is on. VisionClaw "
				"then starts with that NVDA. To make a portable NVDA first, use the button for NVDA's own window and "
				"check Copy current user configuration there: VisionClaw then comes along with everything, and "
				"nothing more is needed here."),
			# Translators: In the window that makes a portable copy.
			_("Writing many gigabytes to a flash drive takes a while, and the copy can be stopped. A drive formatted "
				"as FAT32 cannot hold a file of 4 GB or more; exFAT and NTFS can."),
		]
		try:
			kept = os.listdir(os.path.join(dataDir, "guides"))
		except OSError:
			kept = []
		downloaded = os.path.isdir(os.path.join(dataDir, "training")) or any(
			name.endswith(".md") and name[:-3] not in guides.MAY_SHIP for name in kept)
		if downloaded:
			# Translators: In the window that makes a portable copy, when it holds downloaded lessons or guides.
			lines.append(_("The copy holds lessons and guides that VisionClaw downloaded for your own reading. Their "
				"owners keep their copyright, so give a copy to someone else only where they allow it."))
		return "\n".join(lines)

	def _browse(self):
		# Translators: Title of Windows' window for choosing where a portable copy goes.
		with wx.DirDialog(self, _("Where should the portable copy go?"), defaultPath=self.folder.GetValue()) as d:
			if d.ShowModal() == wx.ID_OK:
				self.folder.SetValue(d.GetPath())
		self.folder.SetFocus()

	def _openNvdaWindow(self):
		self.Close()
		wx.CallAfter(gui.mainFrame.onCreatePortableCopyCommand, None)

	def _make(self):
		# Translators: Title of the messages of the window that makes a portable copy.
		title = _("Portable copy")
		folder = self.folder.GetValue().strip().strip('"')
		if not folder or not os.path.isdir(folder):
			# Translators: Reported when no folder, or one that does not exist, was given for a portable copy.
			_tell(_("Choose a folder or drive that exists, with Browse or by typing its path."), title, self)
			self.folder.SetFocus()
			return
		if portable.inside(folder, self.plugin.addonDir):
			# Translators: Reported when the folder for a portable copy is inside VisionClaw's own folder.
			_tell(_("That folder is inside VisionClaw itself. Choose another one, such as a flash drive."), title, self)
			return
		kind = self.kind.GetSelection()
		if kind == INTO_NVDA:
			nvdaDir, what = portable.findNvda(folder)
			if nvdaDir is None:
				# Translators: Asked when no portable NVDA was found in the folder chosen for a portable copy.
				if _ask(_("There is no NVDA in this folder or in the folders just inside it. Open NVDA's own window "
					"for making a portable NVDA now? Check Copy current user configuration there, and VisionClaw comes "
					"along with everything."), title, self):
					self._openNvdaWindow()
				return
			if what == portable.INSTALLED:
				# Translators: Reported when the folder chosen holds an NVDA that is installed, not a portable one.
				_tell(_("The NVDA in {folder} is installed on this computer, not a portable one. Choose the folder "
					"of a portable NVDA.").format(folder=nvdaDir), title, self)
				return
			target = portable.addonFolderOf(nvdaDir)
			if portable.inside(target, self.plugin.addonDir) or portable.inside(self.plugin.addonDir, target):
				# Translators: Reported when the portable NVDA chosen is the one running now.
				_tell(_("That is the NVDA running now, which has VisionClaw already."), title, self)
				return
			if os.path.isdir(target) and not _ask(
				# Translators: Asked when the portable NVDA has VisionClaw already.
				_("The portable NVDA in {folder} has VisionClaw already. Bring it up to this computer's copy? Its "
					"files of the same name are replaced by this computer's, and what only it has is kept.").format(
					folder=nvdaDir), title, self):
				return
			place = target
		else:
			place = os.path.join(folder, portable.BUNDLE_NAME.format(version=self.version()))
			if os.path.exists(place) and not _ask(
				# Translators: Asked when the file of a portable copy is there already.
				_("{path} is there already. Replace it?").format(path=place), title, self):
				return
		found = portable.files(self.plugin.addonDir)
		extras = {
			f"{portable.DATA}/{portable.SETTINGS_FILE}": portable.settingsText(self.plugin.portableSettings()).encode("utf-8")}
		try:
			free = shutil.disk_usage(folder).free
		except OSError:
			free = None
		sizes = [size for _full, _arc, size in found] + [len(b) for b in extras.values()]
		trouble = portable.check(kind == FILE, sizes, free, fileSystemOf(folder))
		if trouble and trouble[0] == portable.TOO_BIG_FOR_FAT:
			# Translators: Reported when the drive chosen for a portable copy is formatted as FAT32. {size} is the
			# size of the biggest file.
			_tell(_("This drive is formatted as FAT32, which cannot hold a file of 4 GB or more, and the copy needs "
				"one of {size}. Choose another drive, or format this one as exFAT or NTFS: formatting erases "
				"everything on it.").format(size=portable.sizeText(trouble[1])), title, self, wx.ICON_WARNING)
			return
		if trouble and trouble[0] == portable.NO_SPACE:
			# Translators: Reported when the drive chosen has too little room. {need} and {free} are sizes.
			_tell(_("There is not enough room there: the copy needs {need}, and {free} is free.").format(
				need=portable.sizeText(trouble[1]), free=portable.sizeText(free or 0)), title, self, wx.ICON_WARNING)
			return
		self._start(kind, place, found, extras, sum(sizes))

	def _start(self, kind, place, found, extras, total):
		self._stop = threading.Event()
		self._lastStep = -1
		# Translators: Title of the progress bar while a portable copy is made.
		self._progress = wx.ProgressDialog(_("Making the portable copy"),
			# Translators: Shown while a portable copy is made. {size} is its size.
			_("Copying {size}. This can take several minutes.").format(size=portable.sizeText(total)),
			maximum=STEPS, parent=self,
			style=wx.PD_CAN_ABORT | wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)
		debuglog.log("portable", f"Making a portable copy ({'file' if kind == FILE else 'into a portable NVDA'}) at {place}: "
			f"{len(found)} files, {total} bytes")

		def work():
			result = error = None
			try:
				if kind == FILE:
					result = portable.writeBundle(found, place, extras, self._stop, self._onProgress)
				else:
					result = portable.copyTo(found, place, extras, self._stop, self._onProgress)
			except portable.Stopped as e:
				error = e
			except Exception as e:
				error = e
				debuglog.error("portable", f"The portable copy at {place} could not be made", e)
			wx.CallAfter(self._finished, kind, place, result, error)

		threading.Thread(target=work, name="visionClaw-portable", daemon=True).start()

	def _onProgress(self, done, total, name):
		step = int(STEPS * done / total) if total else STEPS
		if step != self._lastStep:
			self._lastStep = step
			wx.CallAfter(self._showProgress, min(step, STEPS - 1), done, total)

	def _showProgress(self, step, done, total):
		if self._progress is None:
			return
		# Translators: Shown while a portable copy is made. {done} and {total} are sizes.
		keepGoing, _skip = self._progress.Update(step, _("{done} of {total} copied.").format(
			done=portable.sizeText(done), total=portable.sizeText(total)))
		if not keepGoing and self._stop is not None:
			self._stop.set()

	def _finished(self, kind, place, result, error):
		if self._progress is not None:
			self._progress.Destroy()
			self._progress = None
		self._stop = None
		# Translators: Title of the messages of the window that makes a portable copy.
		title = _("Portable copy")
		if isinstance(error, portable.Stopped):
			if kind == FILE:
				# Translators: Reported when the user stopped making the file of a portable copy.
				text = _("Stopped. Nothing was left behind.")
			else:
				# Translators: Reported when the user stopped copying VisionClaw into a portable NVDA.
				text = _("Stopped partway. VisionClaw in the portable NVDA may not be whole yet. Make the copy again to "
					"finish it: what was copied already is skipped.")
			debuglog.log("portable", "The portable copy was stopped by the user")
		elif error is not None:
			# Translators: Reported when a portable copy could not be made. {error} is what Windows said.
			text = _("The copy could not be made: {error}. Nothing that was there before was harmed.").format(error=error) \
				if kind == FILE else _("The copy could not be made: {error}. Make it again to finish it; what was "
				"copied already is skipped.").format(error=error)
		elif kind == FILE:
			# Translators: Reported when the file of a portable copy is made. {path} is the file, {size} its size.
			text = _("Done. {path} holds VisionClaw with everything, {size}. On another computer, open this file "
				"while NVDA is running, and NVDA asks before it installs it.").format(
				path=place, size=portable.sizeText(result))
			debuglog.log("portable", f"The portable copy {place} was made, {result} bytes")
		else:
			copied, skipped = result
			# Translators: Reported when VisionClaw was copied into a portable NVDA. {folder} is where.
			text = _("Done. VisionClaw is in the portable NVDA with everything, at {folder}. Start that NVDA with "
				"nvda.exe in its folder, and VisionClaw starts with it. If it is running now, restart it.").format(
				folder=place)
			if skipped:
				# Translators: Added when files that were there already were skipped. {count} is how many.
				text += " " + _("{count} files were there already and were skipped.").format(count=skipped)
			debuglog.log("portable", f"VisionClaw was copied into {place}: {copied} files copied, {skipped} skipped")
		_tell(text, title, self)

	def _onClose(self, event):
		if self._stop is not None:
			# Translators: Reported when the window is closed while a copy is being made.
			ui.message(_("The copy is still being made. Press Cancel on the progress bar to stop it."))
			event.Veto()
			return
		self.Destroy()


def show(plugin, parent=None):
	gui.mainFrame.prePopup()
	try:
		dialog = PortableDialog(parent or gui.mainFrame, plugin)
		dialog.Show()
	finally:
		gui.mainFrame.postPopup()
