# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The Ask VisionClaw window (clawui.AskDialog) with the real wxPython and stand-ins for NVDA's gui and ui, and a
stand-in for asking by voice: the voice button offers the speech model when there is none, begins to listen when
there is one, stops when pressed again, puts what was heard into the box without sending it, adds it to what is
there already, and says a problem as it is; and the window without asking by voice has no such button.
No microphone is opened and no model is run. Skipped when wxPython is not installed. Nothing is shown on the
screen.

  python tests/test_ask_window.py
"""
import sys
import types

import harness  # noqa: F401

try:
	import wx
except ImportError:
	print("wxPython is not installed; skipped.\nOK")
	sys.exit(0)

said = []
gui = types.ModuleType("gui")
gui.mainFrame = None
sys.modules["gui"] = gui
sys.modules["ui"] = types.SimpleNamespace(message=lambda text: said.append(text))
import builtins  # noqa: E402
builtins._ = getattr(builtins, "_", None) or (lambda text: text)
sys.modules.setdefault("addonHandler", types.SimpleNamespace(initTranslation=lambda: None))

from visionClaw import clawui  # noqa: E402
from visionClaw.claw import voice as voiceWords  # noqa: E402


class FakeVoice:
	"""Asking by voice as the window sees it."""

	def __init__(self, ready):
		self.isReady, self.isListening, self.isDownloading = ready, False, False
		self.did, self.then, self.heard = [], None, None

	def ready(self):
		return self.isReady

	def listening(self):
		return self.isListening

	def downloading(self):
		return self.isDownloading

	def stopDownload(self):
		self.did.append("stop download")
		self.isDownloading = False

	def stop(self):
		self.did.append("stop")
		self.isListening = False

	def offer(self, parent, then=None):
		self.did.append("offer")
		self.then = then

	def start(self, onState, onDone, names=()):
		self.did.append(("start", tuple(names)))
		self.isListening = True
		self.heard = (onState, onDone)


app = wx.App(False)
sent = []

# A window without asking by voice has no such button, and works as before.
plain = clawui.AskDialog(None, lambda request, reasoning: sent.append((request, reasoning)))
assert plain.voiceBtn is None
plain.speak()  # nothing happens, and nothing breaks
plain.request.SetValue("  what is on my screen  ")
plain._send()
assert sent == [("what is on my screen", "auto")], sent

# With asking by voice: a button with a key of its own, before Send.
voice = FakeVoice(ready=False)
dialog = clawui.AskDialog(None, lambda request, reasoning: sent.append((request, reasoning)), voice=voice, names=["Notepad"])
assert dialog.voiceBtn.GetLabel() == "Speak your request (&V)"
assert "Alt+V" in dialog.log.GetValue() and "NVDA+Alt+V" in dialog.log.GetValue()
# No speech model yet: the user is asked whether to get one, and nothing listens.
dialog.speak()
assert voice.did == ["offer"] and not voice.isListening
# Once it is here, what was begun goes on by itself.
voice.isReady = True
voice.then()
assert voice.did[-1] == ("start", ("Notepad",)) and voice.isListening
assert dialog.voiceBtn.GetLabel() == "Stop listening (&V)"  # the focus is in the box, so NVDA does not read this out
# Pressed again while listening: listening stops, and what was said so far is still worked out.
dialog.speak()
assert voice.did[-1] == "stop"
onState, onDone = voice.heard
onState("thinking")
assert dialog.voiceBtn.GetLabel() == "Working out what you said"
# What was heard is put into the box and read out. Nothing is sent.
del sent[:]
onDone("Make NVDA speak a little faster, only in this program.", "")
assert dialog.request.GetValue() == "Make NVDA speak a little faster, only in this program."
assert said[-1] == "You said: Make NVDA speak a little faster, only in this program. Press Enter to send it, or change it first."
assert sent == [] and dialog.voiceBtn.GetLabel() == "Speak your request (&V)"
assert dialog.request.GetInsertionPoint() == len(dialog.request.GetValue())
# Said in two goes: the second is added to the first.
dialog.speak()
voice.heard[1]("Then tell me the time.", "")
assert dialog.request.GetValue() == "Make NVDA speak a little faster, only in this program. Then tell me the time."
# A problem is said as it is, and the box stays as it was.
voice.isListening = False
dialog.speak()
voice.heard[1]("", voiceWords.NOTHING_HEARD)
assert said[-1] == voiceWords.NOTHING_HEARD and dialog.request.GetValue().endswith("Then tell me the time.")
# Listening that the user stopped before saying anything: nothing is said about it.
before = len(said)
voice.heard[1]("", "")
assert len(said) == before
# While the speech model is being downloaded, the button stops the download.
voice.isListening, voice.isDownloading = False, True
dialog.speak()
assert voice.did[-1] == "stop download"
# Enter sends what is in the box, and listening is stopped with the window.
voice.isListening = True
dialog._send()
assert sent == [("Make NVDA speak a little faster, only in this program. Then tell me the time.", "auto")], sent
assert voice.did[-1] == "stop"
# What comes back after the window is gone is dropped without an error.
wx.Yield()
onDone("too late", "")
print("OK")
