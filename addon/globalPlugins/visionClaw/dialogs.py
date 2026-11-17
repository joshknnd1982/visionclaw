# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the models window (welcome, choosing and downloading models) and the description window.

import re
import threading

import addonHandler
import api
import gui
import ui
import wx
from logHandler import log

from . import net, sounds
from .claw import catalog

addonHandler.initTranslation()

# Translators: Usage guide shown after the vision data is installed.
USAGE = _(
	"How to use VisionClaw:\n"
	"NVDA+Alt+A: describe the current element.\n"
	"NVDA+Alt+W: describe the current window.\n"
	"NVDA+Alt+F: describe the whole screen.\n"
	"NVDA+Alt+D: describe the image or image file on the clipboard.\n"
	"Press a command once to hear a quick description. "
	"Press it twice quickly to get a detailed description in a window you can read, copy and close, "
	"and where you can ask questions about the image.\n"
	"NVDA+Alt+O: open the overlay, which makes a window NVDA cannot read into a list of its texts and icons. "
	"Press Enter on an item to click it, and Escape to close.\n"
	"NVDA+Alt+G: turn automatic descriptions on or off. When on, images that have no label "
	"are described as you read web pages and documents.\n"
	"NVDA+Alt+B: turn button names on or off. When on, buttons that have no name are named from their icon.\n"
	"NVDA+Alt+N: give your own name to the current button, or to the current item in the overlay.\n"
	"Press Control to stop speaking.\n"
	"NVDA+Alt+C: ask VisionClaw to do something, in plain language. For example: make NVDA speak faster, "
	"what is on my screen, how do I read the window title, press the Play button in this window, "
	"or write an add-on that beeps when a link gets the focus. "
	"Your request is planned in small steps and carried out one at a time. With two different models, the two "
	"must agree on the steps first; with one model for both jobs, that model chooses and checks its own work.\n"
	"NVDA+Alt+P: hear how far the task is. NVDA+Alt+X: stop the task.\n"
	"NVDA+Alt+K: pointer mode, to work a control NVDA cannot reach: the arrow keys move the mouse pointer, "
	"Enter clicks, the Applications key right-clicks, G holds and lets go for dragging, Escape leaves.\n"
	"In the overlay, G on an item picks it up and G on another item drops it there.\n"
	"NVDA+Alt+M: choose or download models.\n"
	"VisionClaw uses AI, and AI can make mistakes, so please double-check anything important.\n"
	"Everything runs on your computer. Images are never sent to the internet."
)


def _mb(n):
	return round(n / 1048576)


def lookResult(found):
	"""What looking for newer models found, in sentences. found is what catalog.Catalog.look returns."""
	lines = []
	if found["new"]:
		# Translators: Shown after looking for newer models. {count} is how many, {names} their names.
		lines.append(_("{count} models were added to the lists: {names}.").format(
			count=len(found["new"]), names=", ".join(found["new"])))
	else:
		# Translators: Shown after looking for newer models when there are none.
		lines.append(_("There are no newer models. The lists here already offer every model on VisionClaw's list."))
	if found.get("updated"):
		# Translators: Says how old the list of models is. {date} is a date like 2026-11-17.
		lines.append(_("The list was last brought up to date on {date}.").format(date=found["updated"]))
	if found.get("tooNew"):
		# Translators: Shown when some newer models cannot be used by this version of the add-on.
		lines.append(_(
			"{count} newer models need a newer version of VisionClaw and are not offered here."
		).format(count=found["tooNew"]))
	if found.get("refused"):
		# Translators: Shown when entries of the list were not accepted.
		lines.append(_(
			"{count} entries of the list were left out, because they did not pass VisionClaw's checks."
		).format(count=found["refused"]))
	return " ".join(lines)


class ModelsDialog(wx.Dialog):
	"""Lets the user choose a vision model and a coder model, and downloads what is missing.
	Enter starts, Space reads the progress while working. Every model is always offered: the computer only
	decides which one is suggested."""

	def __init__(self, parent, models, conf, suggested, onInstalled, notes=(), onChosen=None):
		"""models: the catalog. conf: the add-on's settings. suggested: {role: model id}.
		notes: sentences about this computer, shown under the welcome text.
		onChosen(keys) is called with the stored models the new choice uses, once they are ready."""
		self._suggested = suggested
		self._looking = False
		# Translators: Title of the window for choosing and downloading the models.
		super().__init__(parent, title=_("VisionClaw models"))
		self._models = models
		self._conf = conf
		self._onInstalled = onInstalled
		self._onChosen = onChosen
		self._cancel = threading.Event()
		self._working = False
		self._progress = ""
		self._entries = {
			catalog.VISION: models.entries(catalog.VISION),
			catalog.CODER: models.entries(catalog.CODER) + [None],
		}
		# Translators: Welcome text of the models window.
		intro = _(
			"VisionClaw works with two AI models that run on your own computer: a vision model that looks at the "
			"screen, and a coder model that checks plans and writes add-ons. Together they carry out what you ask "
			"in plain language. Nothing you do is sent to the internet.\n\n"
			"Choose the models below. Larger models are more accurate and slower, and need more memory. "
			"All of them are offered whatever your computer is; the suggested ones are the safe choice. "
			"The very small ones are for a computer that can run nothing larger: they make more mistakes, so "
			"VisionClaw asks them one small question at a time. "
			"A model is downloaded only once, and you can change your choice here at any time."
		)
		if notes:
			intro += "\n\n" + "\n".join(notes)
		main = wx.BoxSizer(wx.VERTICAL)
		self.text = wx.TextCtrl(self, value=intro, size=(560, 170), style=wx.TE_MULTILINE | wx.TE_READONLY)
		main.Add(self.text, flag=wx.ALL | wx.EXPAND, border=10)
		self._choices = {}
		for role, label in (
			# Translators: Label of the list of vision models.
			(catalog.VISION, _("&Vision model:")),
			# Translators: Label of the list of coder models.
			(catalog.CODER, _("C&oder model:")),
		):
			main.Add(wx.StaticText(self, label=label), flag=wx.LEFT | wx.RIGHT, border=10)
			choice = wx.Choice(self, choices=[self._label(e, suggested.get(role)) for e in self._entries[role]])
			choice.SetSelection(self._firstSelection(role, suggested.get(role)))
			choice.Bind(wx.EVT_CHOICE, lambda e: self._updateButton())
			main.Add(choice, flag=wx.ALL | wx.EXPAND, border=10)
			self._choices[role] = choice
		self.gauge = wx.Gauge(self, range=100)
		self.gauge.Hide()
		main.Add(self.gauge, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		self.startBtn = wx.Button(self, label="")
		# Translators: Button that asks, and then looks on VisionClaw's page for models that are not offered yet.
		self.lookBtn = wx.Button(self, label=_("Look for &newer models..."))
		# Translators: Button that closes the window without downloading.
		self.closeBtn = wx.Button(self, wx.ID_CANCEL, label=_("&Later"))
		buttons.Add(self.startBtn)
		buttons.Add(self.lookBtn, flag=wx.LEFT, border=10)
		buttons.Add(self.closeBtn, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self._updateButton()
		self.SetSizerAndFit(main)
		self.CentreOnScreen()
		self.startBtn.SetDefault()
		self.startBtn.Bind(wx.EVT_BUTTON, lambda e: self._start())
		self.lookBtn.Bind(wx.EVT_BUTTON, lambda e: self._look())
		self.closeBtn.Bind(wx.EVT_BUTTON, self._onClose)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self.Bind(wx.EVT_CHAR_HOOK, self._onKey)
		self.text.SetFocus()

	def _label(self, entry, suggestedId):
		if entry is None:
			# Translators: A choice in the list of coder models.
			return _("No coder model now: image descriptions and the overlay only")
		if self._models.isInstalled(entry):
			# Translators: A model in the list that needs no download. {name} is the model.
			label = _("{name}, on this computer").format(name=entry["name"])
		else:
			# Translators: A model in the list. {name} is the model, {size} its download size in megabytes.
			label = _("{name}, {size} MB to download").format(
				name=entry["name"], size=_mb(self._models.missingBytes(entry)))
		if entry["id"] == suggestedId:
			# Translators: Added to the model that is suggested for this computer.
			label += _(", suggested")
		if entry.get("suggest") is False:
			# Translators: Added to the very smallest models in the list, which are offered but never suggested.
			label += _(", very small: fast, less accurate")
		return label

	def _firstSelection(self, role, suggestedId):
		"""The user's earlier choice if there is one, else the suggested model."""
		entries = self._entries[role]
		chosen = self._conf["visionModel" if role == catalog.VISION else "coderModel"]
		for wanted in (chosen, suggestedId):
			for i, entry in enumerate(entries):
				if entry is not None and entry["id"] == wanted:
					return i
		return 0

	def _selected(self):
		return {role: self._entries[role][max(0, choice.GetSelection())] for role, choice in self._choices.items()}

	def _toDownload(self):
		"""The chosen models that are not here yet."""
		return [e for e in self._selected().values() if e is not None and not self._models.isInstalled(e)]

	def _missingBytes(self, entries):
		"""Bytes still to download for these models, counting a file two of them share only once."""
		seen, size = set(), 0
		for entry in entries:
			for f in entry["files"]:
				key = (entry["dir"], f["name"])
				if key not in seen:
					seen.add(key)
					only = dict(entry, files=[f])
					size += self._models.missingBytes(only)
		return size

	def _updateButton(self):
		size = self._missingBytes(self._toDownload())
		if size:
			# Translators: Button that starts the download. {size} is in megabytes.
			self.startBtn.SetLabel(_("&Download ({size} MB)").format(size=_mb(size)))
		else:
			# Translators: Button that saves the choice of models when nothing needs downloading.
			self.startBtn.SetLabel(_("&Use these models"))

	def _after(self, fn, *args):
		# The window may be closed while the worker thread is still reporting progress.
		wx.CallAfter(lambda: fn(*args) if self else None)

	def _onKey(self, evt):
		key = evt.GetKeyCode()
		if self._working and key == wx.WXK_SPACE:
			ui.message(self._progress)
			return
		if not self._working and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and self.startBtn.IsShown() \
				and self.FindFocus() not in (self.closeBtn, self.lookBtn) and not isinstance(self.FindFocus(), wx.Choice):
			self._start()
			return
		evt.Skip()

	def _look(self):
		"""Look for newer models, but only after the user has said yes: this is the one time VisionClaw goes
		online other than to download a model."""
		if self._working or self._looking:
			return
		# Translators: Asked before VisionClaw goes online to read the list of models.
		question = _(
			"VisionClaw will go online once, to its own page on GitHub, and read the list of Qwen models it can "
			"offer. Nothing about you, your computer or what you do is sent; GitHub sees your internet address, as "
			"any website does. Nothing is downloaded or changed except the lists in this window.\n\nLook now?"
		)
		# Translators: Title of the question asked before VisionClaw goes online to read the list of models.
		if gui.messageBox(question, _("Look for newer models"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
			return
		self._looking = True
		self.lookBtn.Disable()
		# Translators: Shown while the list of models is being read from the internet.
		self._setText(_("Looking for newer models."))
		version = ""
		try:
			version = str(addonHandler.getCodeAddon().manifest["version"])
		except Exception:
			log.debugWarning("VisionClaw: the add-on's own version could not be read", exc_info=True)
		threading.Thread(target=self._lookWork, args=(version,), name="visionClaw-look", daemon=True).start()

	def _lookWork(self, version):
		try:
			found = self._models.look(version)
		except Exception as e:
			log.warning("VisionClaw: the list of models could not be read", exc_info=True)
			self._after(self._looked, None, str(e))
			return
		self._after(self._looked, found, "")

	def _looked(self, found, error):
		self._looking = False
		self.lookBtn.Enable()
		if found is None:
			# Translators: Shown when the list of models could not be read. {error} is the reason.
			self._setText(_(
				"The list of models could not be read: {error}\n\nNothing was changed. Check your internet "
				"connection and try again later."
			).format(error=error))
			return
		if found["new"]:
			# The new models join the lists; what was selected stays selected.
			for role, choice in self._choices.items():
				chosen = self._selected()[role]
				entries = self._models.entries(role) + ([None] if role == catalog.CODER else [])
				self._entries[role] = entries
				choice.Set([self._label(e, self._suggested.get(role)) for e in entries])
				choice.SetSelection(next((i for i, e in enumerate(entries) if e is chosen or (
					e is not None and chosen is not None and e["id"] == chosen["id"])), 0))
			self._updateButton()
		self._setText(lookResult(found))

	def _setText(self, text, focus=True):
		self.text.SetValue(text)
		if focus:
			self.text.SetFocus()
			self.text.SetInsertionPoint(0)

	def _start(self):
		if self._working:
			return
		wanted = self._toDownload()
		if not wanted:
			self._finished()
			return
		self._working = True
		self._cancel.clear()
		self.startBtn.Hide()
		self.lookBtn.Hide()
		for choice in self._choices.values():
			choice.Disable()
		# Translators: Button that cancels the download.
		self.closeBtn.SetLabel(_("&Cancel"))
		self.gauge.SetValue(0)
		self.gauge.Show()
		# Translators: Reported when the download begins.
		self._progress = _("Starting download.")
		# Translators: Shown while downloading.
		self._setText(_("Downloading the models. Press Space to hear the progress."))
		self.Layout()
		self.Fit()
		threading.Thread(target=self._work, args=(wanted,), name="visionClaw-models", daemon=True).start()

	def _work(self, wanted):
		total = self._missingBytes(wanted) or 1
		state = {"before": 0}
		try:
			for entry in wanted:
				start = self._models.missingBytes(entry)
				offset = catalog.entrySize(entry) - start

				def downloaded(done, _total, entry=entry, offset=offset):
					got = state["before"] + max(0, done - offset)
					pct = min(100, got * 100 // total)
					# Translators: Download progress. {name} is the model, {pct} percent, {done} of {total} megabytes.
					self._progress = _("Downloading {name}, {pct} percent, {done} of {total} MB.").format(
						name=entry["name"], pct=pct, done=_mb(got), total=_mb(total))
					self._after(lambda v: self.gauge.SetValue(v), pct)

				self._models.download(entry, downloaded, self._cancel)
				state["before"] += start
		except net.Cancelled:
			return
		except (OSError, ValueError) as e:
			log.error("VisionClaw: model download failed", exc_info=True)
			self._after(self._failed, str(e))
			return
		self._after(self._finished)

	def _finished(self):
		self._working = False
		chosen = self._selected()
		self._conf["visionModel"] = chosen[catalog.VISION]["id"] if chosen[catalog.VISION] else ""
		self._conf["coderModel"] = chosen[catalog.CODER]["id"] if chosen[catalog.CODER] else "none"
		self.gauge.Hide()
		self.startBtn.Hide()
		self.lookBtn.Hide()
		for choice in self._choices.values():
			choice.Disable()
		self.closeBtn.SetLabel(_("&Close"))
		# Translators: Shown when the models are ready, followed by the usage guide.
		self._setText(_("VisionClaw is ready to use.") + "\n\n" + USAGE)
		self.Layout()
		self._onInstalled()
		if self._onChosen is not None:
			keep = [entry["dir"] or entry["id"] for entry in chosen.values() if entry is not None]
			wx.CallAfter(self._onChosen, keep)

	def _failed(self, error):
		self._working = False
		self.gauge.Hide()
		for choice in self._choices.values():
			choice.Enable()
		# Translators: Button to retry a failed download.
		self.startBtn.SetLabel(_("&Try again"))
		self.startBtn.Show()
		self.lookBtn.Show()
		self.closeBtn.SetLabel(_("&Close"))
		if "CERTIFICATE_VERIFY_FAILED" in error:
			# Translators: Shown when the download fails because the secure connection can't be checked.
			self._setText(_(
				"The download did not finish because Windows could not confirm the secure connection "
				"to the download server.\n\n"
				"This usually happens when the PC's date and time are wrong, when Windows Update hasn't run "
				"for a while, or when antivirus or a company network checks secure connections. "
				"Fix the date and time or run Windows Update, then press Enter to try again. "
				"The download continues from where it stopped."
			))
		else:
			# Translators: Shown when the download fails. {error} is the reason.
			self._setText(_(
				"The download did not finish: {error}\n\n"
				"Check your internet connection and press Enter to try again. "
				"The download continues from where it stopped."
			).format(error=error))
		self.Layout()

	def _onClose(self, evt):
		if self._working:
			# Keep the partial download so the next attempt resumes.
			self._cancel.set()
			# Translators: Reported when the download is cancelled.
			ui.message(_("Download cancelled."))
		self.Destroy()


def _gb(n):
	return f"{n / 1073741824:.1f}"


def modelLine(model, inUse):
	"""One stored model in words: its name, its size, and what it is used for."""
	uses = []
	if model["partial"] and not model["roles"]:
		# Translators: Said of a model whose download was not finished.
		uses.append(_("unfinished download"))
	for role, text in (
		# Translators: Said of a stored model that is the one in use for looking at the screen.
		(catalog.VISION, _("in use for vision")),
		# Translators: Said of a stored model that is the one in use for coding.
		(catalog.CODER, _("in use for coding")),
	):
		if inUse.get(role) == model["key"]:
			uses.append(text)
	if not uses:
		# Translators: Said of a stored model that VisionClaw is not using at the moment.
		uses.append(_("not in use"))
	# Translators: A model on this computer. {name} is the model, {size} its size in gigabytes, {uses} what it is used for.
	return _("{name}, {size} GB, {uses}").format(name=model["name"], size=_gb(model["bytes"]), uses=" and ".join(uses))


def modelsSummary(models, inUse):
	"""All stored models in a few lines, for the settings panel and the top of the models window."""
	if not models:
		# Translators: Shown when no model is on the computer.
		return _("No models are on this computer yet.")
	lines = [modelLine(m, inUse) for m in models]
	# Translators: The total of the models on this computer. {count} models, {size} gigabytes.
	lines.append(_("{count} models, {size} GB on disk in all.").format(
		count=len(models), size=_gb(sum(m["bytes"] for m in models))))
	return "\n".join(lines)


class ManageModelsDialog(wx.Dialog):
	"""Shows the models on this computer, and lets the user remove some or all of them and choose others."""

	def __init__(self, parent, plugin):
		# Translators: Title of the window that shows the models on this computer.
		super().__init__(parent, title=_("VisionClaw: models on this computer"))
		self._plugin = plugin
		self._models = []
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the list of models on this computer.
		main.Add(wx.StaticText(self, label=_("&Models on this computer. Check the ones you want to remove:")),
			flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		try:
			from gui import nvdaControls
			self.list = nvdaControls.CustomCheckListBox(self, choices=[])
		except Exception:
			self.list = wx.CheckListBox(self, choices=[])
		main.Add(self.list, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		self.total = wx.StaticText(self, label="")
		main.Add(self.total, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that removes the checked models from the computer.
		self.removeBtn = wx.Button(self, label=_("&Remove checked models"))
		# Translators: Button that removes every model from the computer.
		self.removeAllBtn = wx.Button(self, label=_("Remove &all models"))
		# Translators: Button that opens the window for choosing and downloading models.
		self.chooseBtn = wx.Button(self, label=_("&Choose or download other models..."))
		# Translators: Button that closes the window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("C&lose"))
		for button in (self.removeBtn, self.removeAllBtn, self.chooseBtn, closeBtn):
			buttons.Add(button, flag=wx.RIGHT, border=10)
		main.Add(buttons, flag=wx.ALL, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.CentreOnScreen()
		self.removeBtn.Bind(wx.EVT_BUTTON, lambda e: self._remove(checkedOnly=True))
		self.removeAllBtn.Bind(wx.EVT_BUTTON, lambda e: self._remove(checkedOnly=False))
		self.chooseBtn.Bind(wx.EVT_BUTTON, self._choose)
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())
		self.Bind(wx.EVT_ACTIVATE, lambda e: (self.refresh() if e.GetActive() else None, e.Skip()))
		self.refresh()
		self.list.SetFocus()

	def refresh(self):
		"""Read again what is on the disk; it changes when models are removed or downloaded."""
		self._models, inUse = self._plugin.modelsOnDisk()
		self.list.Set([modelLine(m, inUse) for m in self._models])
		if self._models:
			self.list.SetSelection(0)
			# Translators: The total of the models on this computer. {count} models, {size} gigabytes.
			self.total.SetLabel(_("{count} models, {size} GB on disk in all.").format(
				count=len(self._models), size=_gb(sum(m["bytes"] for m in self._models))))
		else:
			# Translators: Shown when no model is on the computer.
			self.total.SetLabel(_("No models are on this computer yet."))
		self.removeBtn.Enable(bool(self._models))
		self.removeAllBtn.Enable(bool(self._models))

	def _remove(self, checkedOnly):
		if checkedOnly:
			chosen = [self._models[i] for i in self.list.GetCheckedItems() if i < len(self._models)]
			if not chosen:
				# Translators: Reported when Remove is pressed and no model is checked.
				ui.message(_("No model is checked. Press Space on a model to check it."))
				return
		else:
			chosen = list(self._models)
		names = ", ".join(m["name"] for m in chosen)
		size = _gb(sum(m["bytes"] for m in chosen))
		# Translators: Asked before models are removed from the computer.
		question = _(
			"Remove {names}? This frees {size} GB. A removed model can be downloaded again at any time."
		).format(names=names, size=size)
		left = len(self._models) - len(chosen)
		if not any(catalog.VISION in m["roles"] for m in self._models if m not in chosen):
			# Translators: Added to the question when no vision model would be left.
			question += " " + _("No vision model will be left, so VisionClaw cannot describe anything until you download one.")
		elif not left:
			question += ""
		gui.mainFrame.prePopup()
		try:
			# Translators: Title of the question asked before models are removed.
			answer = gui.messageBox(question, _("Remove models"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
		finally:
			gui.mainFrame.postPopup()
		if answer != wx.YES:
			return
		try:
			freed = self._plugin.removeModels([m["key"] for m in chosen])
		except (OSError, RuntimeError) as e:
			log.error("VisionClaw: could not remove models", exc_info=True)
			# Translators: Reported when models could not be removed. {error} is the reason.
			ui.message(_("The models could not be removed: {error}").format(error=e))
			self.refresh()
			return
		self.refresh()
		# Translators: Reported after models were removed. {size} is the space freed in gigabytes.
		ui.message(_("Removed. {size} GB freed.").format(size=_gb(freed)))

	def _choose(self, evt):
		self._plugin.showDataDialog()


class ResultDialog(wx.Dialog):
	"""Shows a description so it can be read line by line, copied and closed.
	With onAsk, it also has a box for questions about the image: onAsk(question, dialog)."""

	def __init__(self, parent, text, onAsk=None):
		# Translators: Title of the window showing a detailed description.
		super().__init__(parent, title=_("VisionClaw description"))
		self._text = text
		self._onAsk = onAsk
		self.asking = False
		main = wx.BoxSizer(wx.VERTICAL)
		self.textCtrl = wx.TextCtrl(self, value=text, size=(600, 320), style=wx.TE_MULTILINE | wx.TE_READONLY)
		main.Add(self.textCtrl, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		self.question = None
		if onAsk is not None:
			ask = wx.BoxSizer(wx.HORIZONTAL)
			# Translators: Label of the box for questions about the described image.
			ask.Add(wx.StaticText(self, label=_("&Question about this image:")), flag=wx.ALIGN_CENTER_VERTICAL)
			self.question = wx.TextCtrl(self, size=(380, -1), style=wx.TE_PROCESS_ENTER)
			ask.Add(self.question, proportion=1, flag=wx.LEFT, border=8)
			# Translators: Button that asks the typed question about the image.
			askBtn = wx.Button(self, label=_("As&k"))
			ask.Add(askBtn, flag=wx.LEFT, border=8)
			main.Add(ask, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)
			self.question.Bind(wx.EVT_TEXT_ENTER, lambda e: self.ask())
			askBtn.Bind(wx.EVT_BUTTON, lambda e: self.ask())
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that copies the description to the clipboard.
		copyBtn = wx.Button(self, label=_("&Copy"))
		# Translators: Button that closes the description window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("C&lose"))
		buttons.Add(copyBtn)
		buttons.Add(closeBtn, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.CentreOnScreen()
		copyBtn.Bind(wx.EVT_BUTTON, lambda e: api.copyToClip(self.textCtrl.GetValue(), notify=True))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())
		self.textCtrl.SetFocus()
		self.textCtrl.SetInsertionPoint(0)

	def ask(self):
		question = self.question.GetValue().strip() if self.question else ""
		if not question or self.asking or self._onAsk is None:
			return
		self.question.Clear()
		self.asking = True
		self._onAsk(question, self)

	def addAnswer(self, question, answer):
		"""Called on the GUI thread when an answer is complete."""
		self.asking = False
		if answer:
			# Translators: A question and its answer, added to the description window.
			self.appendText(_("\n\nQuestion: {question}\nAnswer: {answer}").format(question=question, answer=answer))

	def appendText(self, text):
		"""Add streamed text without moving the reading position."""
		pos = self.textCtrl.GetInsertionPoint()
		self.textCtrl.AppendText(text)
		self.textCtrl.SetInsertionPoint(pos)

	def setFinalText(self, text):
		pos = self.textCtrl.GetInsertionPoint()
		self.textCtrl.SetValue(text)
		self.textCtrl.SetInsertionPoint(min(pos, self.textCtrl.GetLastPosition()))


class StreamingResult:
	"""Opens a ResultDialog as soon as the first sentence arrives and keeps adding the rest.
	feed() and finish() are called from the worker thread."""

	_FIRST = re.compile(r"[.!?。！？]\s")

	def __init__(self, onOpened, onAsk=None):
		self._text = ""
		self._shown = 0
		self._requested = False
		self._dialog = None
		self._onOpened = onOpened
		self._onAsk = onAsk

	def feed(self, delta):
		self._text += delta
		if not self._requested:
			if self._FIRST.search(self._text) or len(self._text) > 160:
				self._requested = True
				wx.CallAfter(self._open)
		else:
			wx.CallAfter(self._sync)

	def finish(self, finalText):
		wx.CallAfter(self._finish, finalText)

	def _open(self):
		self._dialog = ResultDialog(gui.mainFrame, _streamClean(self._text), self._onAsk)
		self._shown = len(self._text)
		show(self._dialog)
		self._onOpened()

	def _sync(self):
		if self._dialog and self._shown < len(self._text):
			self._dialog.appendText(_streamClean(self._text[self._shown:]))
			self._shown = len(self._text)

	def _finish(self, finalText):
		if self._dialog is None:
			self._open()
		if self._dialog:
			self._dialog.setFinalText(finalText)
			sounds.play("done")


def _streamClean(text):
	return text.replace("**", "").replace("`", "").replace("##", "")


def show(dialog):
	"""Show a modeless dialog in front, the way NVDA's own windows appear."""
	gui.mainFrame.prePopup()
	dialog.Show()
	dialog.Raise()
	gui.mainFrame.postPopup()
