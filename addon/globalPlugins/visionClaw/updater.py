# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - getting a newer version of VisionClaw itself from its page on GitHub.
# The user chooses in the settings when the list of releases is read: only when they ask (NVDA+Alt+U, the
# button in the settings, or a request in words), or also when NVDA starts, at most once a day. Whatever
# they chose, nothing is downloaded before they say yes, the downloaded file is checked against the size
# and SHA-256 GitHub reports, and the installing is left to NVDA itself, which asks its own question and
# restarts. What may be downloaded is decided in claw/updates.py.

import os
import threading
import time

import addonHandler
import globalVars
import gui
import ui
import wx
from .vclog import log

from . import net
from .claw import updates
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()

# After NVDA has started, how long to wait before looking by itself, so that start-up is not slowed.
START_DELAY_MS = 45000


def currentVersion():
	"""The version of VisionClaw that is running."""
	try:
		return str(addonHandler.getCodeAddon().manifest["version"])
	except Exception:
		log.debugWarning("VisionClaw: its own version could not be read", exc_info=True)
		return ""


class UpdateDialog(wx.Dialog):
	"""Says that a newer version is there and what is new in it, in a read-only edit box, so that it can be
	read line by line, word by word and again, and copied; and asks whether to download it. A message box
	can only be listened to once, from start to end."""

	def __init__(self, parent, text):
		# Translators: Title of the window about a newer version of VisionClaw.
		super().__init__(parent, title=_("VisionClaw update"))
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the read-only box that says what is new in a newer version of VisionClaw.
		main.Add(wx.StaticText(self, label=_("&What is new:")), flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.textCtrl = wx.TextCtrl(self, value=text, size=(620, 320), style=wx.TE_MULTILINE | wx.TE_READONLY)
		main.Add(self.textCtrl, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that downloads a newer version of VisionClaw and hands it to NVDA to install.
		yes = wx.Button(self, wx.ID_YES, label=_("&Download and install"))
		# Translators: Button that closes the window about a newer version without downloading anything.
		no = wx.Button(self, wx.ID_NO, label=_("&Not now"))
		buttons.Add(yes)
		buttons.Add(no, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_NO)
		self.CentreOnScreen()
		yes.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_YES))
		no.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_NO))
		self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_NO))
		# The box has the focus, at its start, so that reading begins with what is new and nothing is
		# downloaded by a stray Enter.
		self.textCtrl.SetFocus()
		self.textCtrl.SetInsertionPoint(0)


def askDownload(found, current):
	"""Show what is new in a newer version and ask whether to download it. True for yes. Main thread."""
	dialog = UpdateDialog(gui.mainFrame, updates.offerText(found, current))
	gui.mainFrame.prePopup()
	try:
		return dialog.ShowModal() == wx.ID_YES
	finally:
		gui.mainFrame.postPopup()
		dialog.Destroy()


def _openInstaller(path):
	"""Hand the downloaded add-on file to Windows, which gives it to NVDA: NVDA then asks its own question
	about installing it and restarts. Raises OSError if Windows has no program for such files."""
	os.startfile(path)


class Updater:
	def __init__(self, plugin, folder, conf):
		self._plugin = plugin
		self._folder = os.path.join(folder, "updates")
		self._conf = conf
		self._busy = False
		self._cancel = threading.Event()
		self._timer = None

	# --- Looking ---

	def look(self):
		"""Read the list of releases and say whether a newer version exists. Returns the newer version as
		claw/updates.py describes it, or None. Raises OSError or ValueError if the list cannot be read.
		May be called from any thread; it goes online, so never call it without the user's say."""
		found = updates.newest(net.fetchJson(updates.RELEASES_URL, limit=updates.LIST_BYTES), currentVersion())
		self._conf()["updateLastCheck"] = str(time.time())
		return found

	def download(self, found, onProgress=None):
		"""Download a newer version's file and check it. Returns the file's path."""
		os.makedirs(self._folder, exist_ok=True)
		for name in os.listdir(self._folder):  # earlier downloads are not kept
			if name != found["name"] and name != found["name"] + ".part":
				try:
					os.remove(os.path.join(self._folder, name))
				except OSError:
					pass
		path = os.path.join(self._folder, found["name"])
		net.download(found["url"], path, found["size"], found["sha256"], onProgress, self._cancel)
		return path

	# --- When NVDA starts ---

	def startLater(self):
		"""With the automatic choice, look once after NVDA has started, if a day has passed since the last time."""
		if globalVars.appArgs.secure or not updates.due(self._conf()["updateCheck"], self._conf()["updateLastCheck"], time.time()):
			return
		self._timer = wx.CallLater(START_DELAY_MS, self.check, False)

	def stop(self):
		self._cancel.set()
		if self._timer is not None:
			self._timer.Stop()
			self._timer = None

	# --- From the key and the button ---

	def check(self, asked=True):
		"""Look for a newer version in the background, then tell the user and offer it. asked: the user asked
		for this now; if not, nothing is said unless there is a newer version. Main thread."""
		if self._busy or globalVars.appArgs.secure:
			return
		self._busy = True
		if asked:
			# Translators: Spoken when the user asks to look for a newer version of VisionClaw.
			ui.message(_("Looking for a newer version of VisionClaw."))
		threading.Thread(target=self._lookWork, args=(asked,), name="visionClaw-update", daemon=True).start()

	def _lookWork(self, asked):
		try:
			found, error = self.look(), ""
		except Exception as e:
			log.warning("VisionClaw: could not look for a newer version", exc_info=True)
			found, error = None, str(e)
		wx.CallAfter(self._looked, found, error, asked)

	def _looked(self, found, error, asked):
		self._busy = False
		current = currentVersion()
		if found is None:
			if not asked:
				return
			if error:
				# Translators: Shown when the list of versions could not be read. {error} is the reason.
				text = _("VisionClaw could not look for a newer version: {error}\n\nNothing was changed.").format(error=error)
			else:
				text = updates.newestText(current)
			# Translators: Title of the window about a newer version of VisionClaw.
			gui.messageBox(text, _("VisionClaw update"), wx.OK | wx.ICON_INFORMATION)
			return
		if not asked:
			# Found by itself after NVDA started: one sentence and no window, which would get in the way while
			# NVDA is still starting. Nothing is downloaded until the user asks for it.
			# Translators: Spoken when a newer version was found by itself. {version} is the new version.
			ui.message(_(
				"VisionClaw {version} is available. Press NVDA+Alt+U to get it."
			).format(version=found["version"]))
			return
		# What is new is shown in a box that can be read line by line, with the two choices as buttons.
		if not askDownload(found, current):
			return
		self._busy = True
		# Translators: Spoken when the download of a newer version begins.
		ui.message(_("Downloading VisionClaw {version}.").format(version=found["version"]))
		threading.Thread(target=self._downloadWork, args=(found,), name="visionClaw-update", daemon=True).start()

	def _downloadWork(self, found):
		try:
			path, error = self.download(found), ""
		except net.Cancelled:
			wx.CallAfter(self._downloaded, None, "", found)
			return
		except Exception as e:
			log.warning("VisionClaw: the newer version could not be downloaded", exc_info=True)
			path, error = None, str(e)
		wx.CallAfter(self._downloaded, path, error, found)

	def _downloaded(self, path, error, found):
		self._busy = False
		if path is None:
			if error:
				# Translators: Shown when the newer version could not be downloaded. {error} is the reason.
				gui.messageBox(_(
					"The new version could not be downloaded: {error}\n\nNothing was changed. You can try again later."
				).format(error=error), _("VisionClaw update"), wx.OK | wx.ICON_WARNING)
			return
		ui.message(self.install(path, found))

	def install(self, path, found):
		"""Give the checked file to NVDA to install. Returns the sentence that says what happens next."""
		try:
			_openInstaller(path)
		except OSError:
			log.warning("VisionClaw: the downloaded add-on file could not be opened", exc_info=True)
			# Translators: Said when the downloaded new version could not be handed to NVDA. {path} is the file.
			return _(
				"VisionClaw {version} was downloaded and checked, but Windows could not open it. The file is {path}. "
				"Open it from NVDA's add-on store, Install from external source."
			).format(version=found["version"], path=path)
		# Translators: Said when the new version was downloaded and NVDA's own install question is opening.
		return _(
			"VisionClaw {version} was downloaded and checked. NVDA now asks whether to install it; answer yes, and "
			"NVDA restarts with the new version."
		).format(version=found["version"])


def register(plugin, add, text):
	"""The tool for asking in words. add and text are the helpers of nvdatools.build."""

	def checkUpdate(task):
		# Translators: Asked before VisionClaw goes online to look for a newer version of itself.
		question = _(
			"VisionClaw will go online once, to its own page on GitHub, and read the list of its versions. Nothing "
			"about you or your computer is sent; GitHub sees your internet address, as any website does. Look now?")
		# Translators: The choices before VisionClaw goes online to look for a newer version of itself.
		if plugin.clawAsk(question, [_("Yes, look"), _("No")]) != 0:
			return "You said no, so VisionClaw did not go online."
		try:
			found = plugin.updater.look()
		except (OSError, ValueError) as e:
			raise ToolError(f"The list of versions could not be read: {e}")
		current = currentVersion()
		if found is None:
			return updates.newestText(current)
		task.check()
		available = updates.availableText(found, current)
		# The same window as with the key: what is new in a box that can be read line by line.
		from . import clawui
		if not clawui._fromWorker(lambda: askDownload(found, current), task.cancel):
			task.check()
			return f"{available} You said not now, so nothing was downloaded. Press NVDA+Alt+U whenever you want it."
		try:
			path = plugin.updater.download(found)
		except (OSError, ValueError) as e:
			raise ToolError(f"The new version could not be downloaded: {e}")
		task.check()
		done = threading.Event()
		said = []

		def install():
			try:
				said.append(plugin.updater.install(path, found))
			finally:
				done.set()

		wx.CallAfter(install)
		done.wait(15)
		return said[0] if said else f"VisionClaw {found['version']} was downloaded and checked. The file is {path}."

	add("check_update",
		"look on VisionClaw's own page on GitHub for a newer version of VisionClaw itself, and get it if the "
		"user wants it",
		checkUpdate, title="Looking for a newer version of VisionClaw", tell=VERBATIM)
