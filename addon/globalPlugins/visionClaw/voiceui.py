# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - asking by voice, as the user meets it: the speech model offered and downloaded after a question,
# listening started and stopped, and beeps that say what is going on while NVDA must stay silent, because what
# NVDA says would be heard by the microphone. The microphone and the model are in voiceinput.py; what needs no
# NVDA is in claw/voice.py.

import os
import threading
import time

import addonHandler
import gui
import tones
import ui
import wx

from . import net, voiceinput
from .claw import debuglog, voice
from .vclog import log

addonHandler.initTranslation()

# The beeps: listening begins (high), speech is being worked out (lower). Short, so that they are over before
# anyone speaks.
BEEP_LISTEN, BEEP_THINK, BEEP_MS = 880, 440, 70
# After the beep the microphone is opened this much later, so that the beep is not recorded.
AFTER_BEEP_SECONDS = 0.25
PERCENT_STEP = 10


class Voice:
	"""Asking by voice for one running VisionClaw. chosenId() gives the speech model the user chose, or ""."""

	def __init__(self, plugin, engineDir, dataDir, chosenId):
		self.plugin = plugin
		self.store = voice.Store(os.path.join(dataDir, "speech"))
		self._chosenId = chosenId
		logPath = os.path.join(dataDir, "logs", "speech.log") if debuglog.detailed() else None
		self.ears = voiceinput.Ears(engineDir, self.store, chosenId, logPath)
		self._stop = threading.Event()
		self._thread = None
		self._downloadCancel = None

	# --- The speech model ---

	def ready(self):
		return self.store.chosen(self._chosenId()) is not None

	def infoText(self):
		return self.store.text(self._chosenId())

	def wanted(self):
		return self.store.wanted(self._chosenId())

	def downloading(self):
		return self._downloadCancel is not None

	def stopDownload(self):
		if self._downloadCancel is not None:
			self._downloadCancel.set()

	def download(self, entry, say=None, cancel=None):
		"""Download a speech model, saying how far it is every ten percent. Only after the user said yes.
		Raises net.Cancelled, OSError or ValueError."""
		said = {"percent": -PERCENT_STEP}

		def progress(done, total):
			percent = int(done * 100 / total) if total else 0
			if say is not None and percent >= said["percent"] + PERCENT_STEP and percent < 100:
				said["percent"] = percent - percent % PERCENT_STEP
				say(said["percent"])
		debuglog.log("voice", f"Downloading the speech model {entry['name']} from {entry['source']}.")
		self.store.download(entry, progress, cancel)
		debuglog.log("voice", f"The speech model {entry['name']} is on this computer.")

	def offer(self, parent, then=None):
		"""Ask whether to download the speech model, and download it if the user says yes. then() is called on
		the main thread when it is here. Main thread."""
		if self.downloading():
			# Translators: Reported when the speech model is asked for while it is being downloaded.
			ui.message(_("The speech model is still being downloaded."))
			return
		entry = self.wanted()
		left = self.store.missingBytes(entry)
		# Translators: Title of the question before the speech model for asking by voice is downloaded.
		if gui.messageBox(voice.downloadQuestion(entry, left), _("Ask VisionClaw by voice"), wx.YES_NO | wx.ICON_QUESTION, parent) != wx.YES:
			return
		cancel = self._downloadCancel = threading.Event()

		def say(percent):
			# Translators: Spoken while the speech model is downloaded. {percent} is how far it is.
			wx.CallAfter(ui.message, _("Speech model: {percent} percent").format(percent=percent))

		def run():
			problem = None
			try:
				self.download(entry, say, cancel)
			except net.Cancelled:
				# Translators: Reported when the download of the speech model was stopped.
				problem = _("The download was stopped. What arrived is kept, so asking again goes on from there.")
			except (OSError, ValueError) as e:
				log.error("VisionClaw: the speech model could not be downloaded", exc_info=True)
				# Translators: Reported when the speech model could not be downloaded. {error} is why.
				problem = _("The speech model could not be downloaded: {error}").format(error=e)
			finally:
				self._downloadCancel = None

			def done():
				if problem:
					ui.message(problem)
					return
				# Translators: Reported when the speech model has been downloaded.
				ui.message(_("The speech model is on this computer. You can ask by voice now."))
				if then is not None:
					then()
			wx.CallAfter(done)

		# Translators: Reported when the download of the speech model begins.
		ui.message(_("Downloading the speech model. VisionClaw says how far it is."))
		threading.Thread(target=run, name="visionClaw-speech-download", daemon=True).start()

	def remove(self):
		"""Delete every speech model from this computer. Returns the bytes freed."""
		self.stop()
		freed = 0
		for entry, _size, _whole in self.store.stored():
			freed += self.store.remove(entry)
		return freed

	# --- Listening ---

	def listening(self):
		return self._thread is not None and self._thread.is_alive()

	def stop(self):
		"""Stop listening. What was said so far is still turned into text."""
		self._stop.set()

	def start(self, onState, onDone, names=()):
		"""Listen for one spoken request. onState(state) and onDone(text, problem) are called on the main thread.
		While the microphone is open nothing is spoken: a high beep says that listening has begun, a lower one
		that it is over and the words are being worked out."""
		if self.listening():
			return
		self._stop.clear()
		board = getattr(self.plugin, "board", None)
		working = {"job": None}

		def state(now):
			# The beeps are played from NVDA's main thread, like everything of NVDA's.
			if now == "listening":
				wx.CallAfter(tones.beep, BEEP_LISTEN, BEEP_MS)
				time.sleep(AFTER_BEEP_SECONDS)
			elif now == "thinking":
				wx.CallAfter(tones.beep, BEEP_THINK, BEEP_MS)
				# The microphone is closed now, so a status update may be said if working out the words takes long.
				# Never before: what NVDA says while the microphone is open would be recorded.
				if board is not None:
					working["job"] = board.begin(
						# Translators: What VisionClaw is doing, as a status update says it: "Still working out what you said".
						_("working out what you said"),
						# Translators: What the speech model is doing while it turns a spoken request into text.
						_("The speech model is turning your words into text."))
			wx.CallAfter(onState, now)

		def run():
			try:
				text, problem = voiceinput.listen(self.ears, self._stop, state, names)
			except Exception as e:
				log.error("VisionClaw: listening failed", exc_info=True)
				text, problem = "", f"Listening did not work: {type(e).__name__}: {e}"
			finally:
				if board is not None:
					board.end(working["job"])
			wx.CallAfter(onDone, text, problem)

		try:
			import speech
			speech.cancelSpeech()
		except Exception:
			pass
		self._thread = threading.Thread(target=run, name="visionClaw-listen", daemon=True)
		self._thread.start()

	def terminate(self):
		self.stop()
		self.stopDownload()


# How many controls of the window in front are read, and for how long at most, for the names told to the speech model.
NAMES_LIMIT = 60
NAMES_SECONDS = 0.15


def namesHere(plugin=None):
	"""The names the user may say about where they are, for the speech model to hear right (voice.namesHere): the program
	in front, the words the user taught VisionClaw, the focused control, the window's title, and the names of a few of
	its controls, read quickly. Main thread. Never raises: names only help, and listening must not wait for them."""
	import api
	from . import fixruntime
	program, title, focus, controls, taught = "", "", "", [], []
	try:
		window, current = api.getForegroundObject(), api.getFocusObject()
		module = getattr(window, "appModule", None)
		program = (getattr(module, "productName", "") or getattr(module, "appName", "") or "").strip()
		title, focus = window.name or "", current.name or ""
		for node in fixruntime.windowNodes(window, limit=NAMES_LIMIT, seconds=NAMES_SECONDS):
			if node.get("name") and "INVISIBLE" not in (node.get("states") or ()):
				controls.append(node["name"])
	except Exception:
		log.debugWarning("VisionClaw: the names of the window in front could not be read for the speech model", exc_info=True)
	try:
		taught = [said for said, _meant in plugin.understanding.own()] if plugin is not None else []
	except Exception:
		taught = []
	return voice.namesHere(program, title, focus, controls, taught)


def register(add, plugin, text, mustAgree):
	"""Add the tools about asking by voice. add and text are nvdatools' own."""
	from .claw.tools import VERBATIM, ToolError
	asked = {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)}

	add("voice_info", "say whether asking VisionClaw by voice is set up, which speech model it listens with, and how to speak a request",
		lambda task, asked: plugin.voice.infoText(), asked, looks=True, title="Looking up asking by voice", tell=VERBATIM)

	def getVoice(task, asked):
		speech = plugin.voice
		if speech.ready():
			return speech.infoText()
		entry = speech.wanted()
		# A download is always asked about, whatever the settings say.
		mustAgree(voice.downloadQuestion(entry, speech.store.missingBytes(entry)))

		def say(percent):
			task.setState(task.state, f"Downloading the speech model: {percent} percent.")
		try:
			speech.download(entry, say, task.cancel)
		except net.Cancelled:
			task.check()
			return "The download was stopped. What arrived is kept, so asking again goes on from there."
		except (OSError, ValueError) as e:
			raise ToolError(f"The speech model could not be downloaded: {e}")
		return (
			f"The speech model {entry['name']} is on this computer now. To ask by voice, press NVDA+Alt+V and speak "
			"after the high beep.")

	add("get_voice", "download the speech model for asking VisionClaw by voice, after a question", getVoice, asked,
		title="Getting the speech model", tell=VERBATIM)

	def removeVoice(task, asked):
		speech = plugin.voice
		stored = speech.store.stored()
		if not stored:
			return "No speech model is on this computer, so there is nothing to delete."
		names = " and ".join(entry["name"] for entry, _size, _whole in stored)
		total = sum(size for _entry, size, _whole in stored)
		mustAgree(
			f"Delete the speech model {names} from this computer, {voice.sizeText(total)}? Asking by voice then needs it "
			"downloaded again.")
		try:
			freed = speech.remove()
		except OSError as e:
			raise ToolError(f"It could not be deleted: {e}")
		return f"Deleted the speech model {names}. That freed {voice.sizeText(freed)}."

	add("remove_voice", "delete the speech model for asking by voice from this computer", removeVoice, asked,
		changes=True, title="Deleting the speech model")
