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
	"The two models plan small steps, agree on them, and carry them out one at a time.\n"
	"NVDA+Alt+P: hear how far the task is. NVDA+Alt+X: stop the task.\n"
	"NVDA+Alt+M: choose or download models.\n"
	"VisionClaw uses AI, and AI can make mistakes, so please double-check anything important.\n"
	"Everything runs on your computer. Images are never sent to the internet."
)


def _mb(n):
	return round(n / 1048576)


class ModelsDialog(wx.Dialog):
	"""Lets the user choose a vision model and a coder model, and downloads what is missing.
	Enter starts, Space reads the progress while working. Every model is always offered: the computer only
	decides which one is suggested."""

	def __init__(self, parent, models, conf, suggested, onInstalled, notes=()):
		"""models: the catalog. conf: the add-on's settings. suggested: {role: model id}.
		notes: sentences about this computer, shown under the welcome text."""
		# Translators: Title of the window for choosing and downloading the models.
		super().__init__(parent, title=_("VisionClaw models"))
		self._models = models
		self._conf = conf
		self._onInstalled = onInstalled
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
		# Translators: Button that closes the window without downloading.
		self.closeBtn = wx.Button(self, wx.ID_CANCEL, label=_("&Later"))
		buttons.Add(self.startBtn)
		buttons.Add(self.closeBtn, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self._updateButton()
		self.SetSizerAndFit(main)
		self.CentreOnScreen()
		self.startBtn.SetDefault()
		self.startBtn.Bind(wx.EVT_BUTTON, lambda e: self._start())
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
				and self.FindFocus() is not self.closeBtn and not isinstance(self.FindFocus(), wx.Choice):
			self._start()
			return
		evt.Skip()

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
		for choice in self._choices.values():
			choice.Disable()
		self.closeBtn.SetLabel(_("&Close"))
		# Translators: Shown when the models are ready, followed by the usage guide.
		self._setText(_("VisionClaw is ready to use.") + "\n\n" + USAGE)
		self.Layout()
		self._onInstalled()

	def _failed(self, error):
		self._working = False
		self.gauge.Hide()
		for choice in self._choices.values():
			choice.Enable()
		# Translators: Button to retry a failed download.
		self.startBtn.SetLabel(_("&Try again"))
		self.startBtn.Show()
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
