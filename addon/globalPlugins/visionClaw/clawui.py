# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the Ask VisionClaw window, the questions VisionClaw asks the user, and how a task's progress
# is put into words.

import threading

import addonHandler
import gui
import ui
import wx

from .claw import policy
from .claw import voice as voiceWords
from .claw import task as taskModule

addonHandler.initTranslation()


# When the Ask window is opened to listen at once, how long NVDA is given to begin saying that it has opened.
LISTEN_AFTER_MS = 900


def reasoningLabels():
	return [
		# Translators: Choices for how much the models think before they act.
		_("Automatic: decided for each request"),
		_("Off: fastest"),
		_("Low"),
		_("Medium"),
		_("High: slowest, most careful"),
	]


def stepwiseLabels():
	return [
		# Translators: Choices for whether the models are asked one small question at a time.
		_("Automatic: only for the very small models"),
		_("Always: slower, for any model that makes mistakes"),
		_("Never"),
	]


def _popup(dialog):
	"""Show a modal dialog the way NVDA's own windows appear, and return its result."""
	gui.mainFrame.prePopup()
	try:
		return dialog.ShowModal()
	finally:
		gui.mainFrame.postPopup()


def _fromWorker(show, cancel=None):
	"""Run show() on the main thread and wait for its result on a worker thread. None if the task is stopped."""
	if wx.IsMainThread():
		return show()
	done = threading.Event()
	box = {}

	def run():
		try:
			box["value"] = show()
		finally:
			done.set()

	wx.CallAfter(run)
	while not done.wait(0.2):
		if cancel is not None and cancel.is_set():
			return None
	return box.get("value")


def choose(question, choices, cancel=None):
	"""Ask the user to pick one of several choices. Returns its index, or None if they cancelled."""
	def show():
		# Translators: Title of the window in which VisionClaw asks the user to choose.
		dialog = wx.SingleChoiceDialog(gui.mainFrame, question, _("VisionClaw asks"), list(choices))
		dialog.SetSelection(0)
		try:
			return dialog.GetSelection() if _popup(dialog) == wx.ID_OK else None
		finally:
			dialog.Destroy()
	return _fromWorker(show, cancel)


def askText(question, cancel=None):
	"""Ask the user to type an answer. Returns the text, or "" if they cancelled."""
	def show():
		# Translators: Title of the window in which VisionClaw asks the user a question.
		dialog = wx.TextEntryDialog(gui.mainFrame, question, _("VisionClaw asks"))
		try:
			return dialog.GetValue().strip() if _popup(dialog) == wx.ID_OK else ""
		finally:
			dialog.Destroy()
	return _fromWorker(show, cancel) or ""


class _KeepDialog(wx.Dialog):
	"""Asks whether to keep a change, and closes by itself, with the answer no, after some seconds.
	Used after switching the speech synthesizer or braille display: if the new one gives no output, the user
	cannot answer, and not answering switches back."""

	def __init__(self, parent, question, keepLabel, backLabel, seconds):
		# Translators: Title of the window that asks whether a new synthesizer or braille display works.
		super().__init__(parent, title=_("VisionClaw: does it work?"))
		main = wx.BoxSizer(wx.VERTICAL)
		main.Add(wx.StaticText(self, label=question), flag=wx.ALL, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		keep = wx.Button(self, wx.ID_YES, label=keepLabel)
		back = wx.Button(self, wx.ID_NO, label=backLabel)
		buttons.Add(keep)
		buttons.Add(back, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(main)
		self.CentreOnScreen()
		keep.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_YES))
		back.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_NO))
		self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_NO))
		self._timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, lambda e: self.EndModal(wx.ID_NO) if self.IsModal() else None, self._timer)
		self._timer.StartOnce(int(seconds * 1000))
		keep.SetFocus()


def confirmKeep(question, seconds, cancel=None):
	"""Ask whether to keep a change. True only if the user says yes within the time; silence means no."""
	def show():
		dialog = _KeepDialog(
			gui.mainFrame, question,
			# Translators: Buttons of the window that asks whether a new synthesizer or braille display works.
			_("&Keep it"), _("&Switch back"), seconds)
		try:
			return _popup(dialog) == wx.ID_YES
		finally:
			dialog.Destroy()
	return bool(_fromWorker(show, cancel))


def progressText(task):
	"""Where a task is, in a sentence."""
	state, step, steps, activity, seconds = task.progress()
	if state == taskModule.DONE:
		# Translators: Progress of a finished task.
		return _("Finished. {answer}").format(answer=task.answer)
	if state == taskModule.CANCELLED:
		# Translators: Progress of a task the user stopped.
		return _("The task was stopped.")
	if state == taskModule.FAILED:
		# Translators: Progress of a task that failed.
		return _("The task failed.")
	if steps and state in (taskModule.WORKING, taskModule.CHECKING, taskModule.WAITING):
		# Translators: Progress of a running task. {activity} is what it is doing.
		return _("{activity} {seconds} seconds so far.").format(activity=activity, seconds=seconds)
	# Translators: Progress of a task that has not started its steps yet.
	return _("{activity} {seconds} seconds so far.").format(activity=activity or _("Starting."), seconds=seconds)


def logText(task):
	"""Everything a task did, for reading afterwards."""
	lines = [_("Request: {request}").format(request=task.request), ""]
	for _seconds, kind, text in task.log:
		if kind == taskModule.ANSWER:
			lines += ["", _("Answer: {answer}").format(answer=text), ""]
		elif kind == taskModule.THINK:
			lines.append(_("Thinking, {text}").format(text=text))
		else:
			lines.append(text)
	return "\n".join(lines)


class AskDialog(wx.Dialog):
	"""Where the user types a request. Enter sends it and closes the window, so the program the request is
	about has the focus again while VisionClaw works. onSend(request, reasoning) starts the task."""

	def __init__(self, parent, onSend, lastTask=None, reasoning=policy.AUTO, voice=None, listenNow=False, names=()):
		"""voice: asking by voice (voiceui.Voice), or None for a window without it. listenNow: begin to listen as
		soon as the window is there. names: names that may be said, such as the program in front."""
		# Translators: Title of the window for asking VisionClaw to do something.
		super().__init__(parent, title=_("Ask VisionClaw"))
		self._onSend = onSend
		self._voice, self._names = voice, tuple(names or ())
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the box where the user types a request.
		main.Add(wx.StaticText(self, label=_("&What do you want VisionClaw to do?")), flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.request = wx.TextCtrl(self, size=(560, -1), style=wx.TE_PROCESS_ENTER)
		main.Add(self.request, flag=wx.ALL | wx.EXPAND, border=10)
		row = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Label of the choice of how much the models think.
		row.Add(wx.StaticText(self, label=_("&Reasoning:")), flag=wx.ALIGN_CENTER_VERTICAL)
		self.reasoning = wx.Choice(self, choices=reasoningLabels())
		self.reasoning.SetSelection(policy.REASONING_CHOICES.index(reasoning) if reasoning in policy.REASONING_CHOICES else 0)
		row.Add(self.reasoning, flag=wx.LEFT, border=8)
		main.Add(row, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		# Translators: Label of the box that shows what VisionClaw did last time.
		main.Add(wx.StaticText(self, label=_("&Last task:")), flag=wx.LEFT | wx.RIGHT, border=10)
		last = logText(lastTask) if lastTask is not None else _(
			# Translators: Shown in the Ask VisionClaw window before any request was made.
			"Nothing yet. Examples of what you can ask:\n"
			"Make NVDA speak a little faster.\n"
			"What is on my screen?\n"
			"How do I read the title of this window?\n"
			"Press the Play button in this window.\n"
			"Give this program a hotkey that clicks Send.\n"
			"Write an add-on that beeps when a link gets the focus.\n"
			"Make NVDA speak faster, only in this program.\n"
			"Pick 14 March 2027 in this calendar.\n"
			"After a request you can also say: do that again, a bit more, the other way, say that again.\n\n"
			"To speak your request, press Alt+V here, or NVDA+Alt+V from anywhere.\n"
			"While VisionClaw works: NVDA+Alt+P says the progress, NVDA+Alt+X stops the task."
		)
		self.log = wx.TextCtrl(self, value=last, size=(560, 220), style=wx.TE_MULTILINE | wx.TE_READONLY)
		main.Add(self.log, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		self.voiceBtn = None
		if voice is not None:
			# Translators: Button in the Ask VisionClaw window that listens to a request the user speaks.
			self._speakLabel = _("Speak your request (&V)")
			self.voiceBtn = wx.Button(self, label=self._speakLabel)
			self.voiceBtn.Bind(wx.EVT_BUTTON, lambda e: self.speak())
			buttons.Add(self.voiceBtn, flag=wx.RIGHT, border=10)
		# Translators: Button that sends the request to VisionClaw.
		sendBtn = wx.Button(self, label=_("&Send"))
		# Translators: Button that closes the Ask VisionClaw window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("&Close"))
		buttons.Add(sendBtn)
		buttons.Add(closeBtn, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.CentreOnScreen()
		self.request.Bind(wx.EVT_TEXT_ENTER, lambda e: self._send())
		sendBtn.Bind(wx.EVT_BUTTON, lambda e: self._send())
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self._close())
		self.Bind(wx.EVT_CLOSE, lambda e: self._close())
		self.request.SetFocus()
		if listenNow and voice is not None:
			# NVDA first says that this window has opened. Listening begins a moment later and cuts that short, so
			# that NVDA's own voice is not what the microphone hears.
			wx.CallLater(LISTEN_AFTER_MS, lambda: self.speak() if self else None)

	def _close(self):
		if self._voice is not None:
			self._voice.stop()
		self.Destroy()

	def _send(self):
		request = self.request.GetValue().strip()
		if not request:
			return
		reasoning = policy.REASONING_CHOICES[max(0, self.reasoning.GetSelection())]
		self._close()
		self._onSend(request, reasoning)

	# --- Asking by voice ---

	def speak(self):
		"""The voice button: begin to listen; while listening, stop and use what was said; while the speech model
		is being downloaded, stop the download. With no speech model yet, the user is asked whether to get one."""
		voice = self._voice
		if voice is None:
			return
		if voice.downloading():
			voice.stopDownload()
			return
		if voice.listening():
			voice.stop()
			return
		if not voice.ready():
			voice.offer(self, then=lambda: self.speak() if self else None)
			return
		# While the microphone is open NVDA must say nothing. A button that has the focus is read out when its
		# name changes, so the name is changed only when the focus is somewhere else.
		if not self.voiceBtn.HasFocus():
			# Translators: The voice button of the Ask VisionClaw window while VisionClaw listens.
			self.voiceBtn.SetLabel(_("Stop listening (&V)"))
		voice.start(self._voiceState, self._voiceDone, self._names)

	def _voiceState(self, state):
		if not self or self.voiceBtn is None:
			return
		if state == "thinking":
			# Translators: The voice button of the Ask VisionClaw window while the spoken words are worked out.
			self.voiceBtn.SetLabel(_("Working out what you said"))

	def _voiceDone(self, text, problem):
		"""What was heard is put into the box, where it can be read and changed, and is read out. Nothing is sent
		until the user presses Enter."""
		if not self:
			return  # the window was closed meanwhile
		self.voiceBtn.SetLabel(self._speakLabel)
		if text:
			before = self.request.GetValue().strip()
			self.request.SetValue(f"{before} {text}" if before else text)
			self.request.SetInsertionPointEnd()
			self.request.SetFocus()
			ui.message(voiceWords.saidText(text))
		elif problem:
			ui.message(problem)
