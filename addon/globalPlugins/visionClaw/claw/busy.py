# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what VisionClaw is busy with, and a status update when it has been quiet too long.
#
# A large model, or a model that thinks a lot first, can take a minute or more for one answer, and while it does
# the user hears nothing. Everything VisionClaw does for the user that can take long is a job on one board: a
# request (NVDA+Alt+C, NVDA+Alt+V), a description (NVDA+Alt+F, A, W, D), an answer about a picture, the icons of
# the overlay (NVDA+Alt+O), the words of a spoken request, an add-on being corrected. When the user has heard
# nothing of a job for as long as the setting says, the board says where it is: what it is doing, for how long,
# and, the first time, that NVDA+Alt+P says it at any time. Nothing is said while VisionClaw waits for the user
# (a question is open), once the answer is being spoken or shown, or when the setting is off.
# No NVDA dependencies.

import contextlib
import threading
import time

from . import debuglog

# The setting: how many seconds of quiet before a status update, and between two of them; or never.
CHOICES = ("10", "15", "30", "60", "off")
SUGGESTED = "15"
# How often the board looks whether an update is due, in seconds.
TICK = 1.0

PROGRESS_KEY, STOP_KEY = "NVDA+Alt+P", "NVDA+Alt+X"

# What a job is doing, as the user is told: "Still {doing}". The words after "describing" say what is described.
REQUEST = "working on your request"
DESCRIBING = "describing {what}"
QUESTION = "answering your question about the picture"
ICONS = "naming the icons in the overlay"
VOICE = "working out what you said"
REPAIR = "correcting the add-on {what}"


def seconds(choice):
	"""The setting's choice as seconds of quiet, or 0 for never."""
	try:
		return 0 if str(choice) == "off" else max(1, int(choice))
	except (TypeError, ValueError):
		return int(SUGGESTED)


def duration(total):
	"""A number of seconds in words: "1 second", "45 seconds", "1 minute", "2 minutes and 5 seconds"."""
	total = max(0, int(total))
	minutes, rest = divmod(total, 60)
	secondsText = f"{rest} second" + ("" if rest == 1 else "s")
	if not minutes:
		return secondsText
	minutesText = f"{minutes} minute" + ("" if minutes == 1 else "s")
	return minutesText + (f" and {secondsText}" if rest else "")


def _sentence(text):
	text = " ".join(str(text or "").split())
	if text and text[-1] not in ".!?":
		text += "."
	return text


class Job:
	"""One thing VisionClaw is busy with. Made by Board.begin."""

	def __init__(self, board, doing, activity="", cancel=None, doneText=""):
		self._board = board
		# What it is doing, to follow "Still": "describing the screen".
		self.doing = doing
		# What it is doing right now, a sentence, or a function that gives one when it is asked for.
		self._activity = activity
		# The switch that stops it with NVDA+Alt+X, or None where it cannot be stopped.
		self.cancel = cancel
		# Said when the job is over, only if the user was given an update about it: the end of something whose
		# end would otherwise go unnoticed.
		self.doneText = doneText
		self.started = self.heard = board.clock()
		self.updates = 0
		# The user is hearing or reading what it brought: no more updates.
		self.quiet = False
		# The job waits for something else, not for a model: no updates until it goes on.
		self.paused = False
		self.done = threading.Event()

	def activity(self):
		activity = self._activity
		try:
			return _sentence(activity() if callable(activity) else activity)
		except Exception as e:
			debuglog.error("busy", "What a job is doing could not be put into words", e)
			return ""

	def setActivity(self, activity):
		self._activity = activity

	def heardNow(self):
		"""The user just heard something of this job, such as a step: the quiet starts again."""
		self.heard = self._board.clock()

	def hush(self):
		"""The result is being spoken or shown: nothing more is said about the job."""
		self.quiet = True

	def pause(self):
		self.paused = True

	def resume(self):
		if self.paused:
			self.paused = False
			self.heardNow()

	@property
	def stoppable(self):
		return self.cancel is not None

	def seconds(self, now=None):
		return int((self._board.clock() if now is None else now) - self.started)

	def update(self, now=None, first=False):
		"""The status update, as it is said after a stretch of quiet."""
		parts = [f"Still {self.doing}, {duration(self.seconds(now))} so far.", self.activity()]
		if first:
			parts.append(
				f"Press {PROGRESS_KEY} at any time to hear how far it is, or {STOP_KEY} to stop it." if self.stoppable
				else f"Press {PROGRESS_KEY} at any time to hear how far it is.")
		return " ".join(part for part in parts if part)

	def progress(self, now=None):
		"""Where it is, as NVDA+Alt+P says it."""
		doing = self.doing[:1].upper() + self.doing[1:]
		return " ".join(part for part in (f"{doing}, {duration(self.seconds(now))} so far.", self.activity()) if part)


class Board:
	"""Everything VisionClaw is busy with. speak(text) says an update; it is called from the board's own thread.
	every() gives the seconds of quiet before an update, 0 for never; it is asked each time, so that a changed
	setting counts at once. clock is time.monotonic, or a stand-in in the tests."""

	def __init__(self, speak=None, every=lambda: int(SUGGESTED), clock=time.monotonic, tick=TICK):
		self._speak = speak
		self._every = every
		self.clock = clock
		self._tick = tick
		self._jobs = []
		self._lock = threading.Lock()
		self._thread = None
		self._closed = threading.Event()
		# How many questions to the user are open: while one is, VisionClaw waits for the user, not for a model.
		self._asking = 0

	# --- Jobs ---

	def begin(self, doing, activity="", cancel=None, doneText=""):
		"""A job begins. Returns it; end it with end(job), also when it failed or was stopped."""
		job = Job(self, doing, activity, cancel, doneText)
		with self._lock:
			self._jobs.append(job)
			start = self._speak is not None and self._thread is None and not self._closed.is_set()
			if start:
				self._thread = threading.Thread(target=self._watch, name="visionClaw-status", daemon=True)
		if start:
			self._thread.start()
		return job

	def end(self, job, said=True):
		"""A job is over. Its doneText is said where the user was given an update about it, unless said is False
		or it was stopped."""
		if job is None:
			return
		with self._lock:
			if job in self._jobs:
				self._jobs.remove(job)
			else:
				return
		job.done.set()
		stopped = job.cancel is not None and job.cancel.is_set()
		if said and job.updates and job.doneText and not stopped and self._speak is not None:
			self._say(job.doneText)

	@contextlib.contextmanager
	def job(self, doing, activity="", cancel=None, doneText=""):
		job = self.begin(doing, activity, cancel, doneText)
		try:
			yield job
		finally:
			self.end(job)

	def running(self):
		with self._lock:
			return list(self._jobs)

	# --- The user ---

	@contextlib.contextmanager
	def asking(self):
		"""While a question to the user is open: no updates, since VisionClaw waits for the user. Afterwards the
		quiet starts again, since the user has just done something."""
		with self._lock:
			self._asking += 1
		try:
			yield
		finally:
			with self._lock:
				self._asking = max(0, self._asking - 1)
			self.heard()

	@property
	def isAsking(self):
		return self._asking > 0

	def heard(self):
		"""The user has just heard where everything is, as after NVDA+Alt+P."""
		for job in self.running():
			job.heardNow()

	def progressText(self, now=None):
		"""Where every job is, in sentences, or "" when VisionClaw is busy with nothing. The quiet starts again."""
		jobs = self.running()
		if not jobs:
			return ""
		now = self.clock() if now is None else now
		text = " ".join(job.progress(now) for job in jobs)
		if self.isAsking:
			text += " VisionClaw is waiting for your answer to its question."
		self.heard()
		return text

	def stop(self):
		"""Stop every job that can be stopped. Returns how many were."""
		stopped = 0
		for job in self.running():
			if job.cancel is not None and not job.cancel.is_set():
				job.cancel.set()
				stopped += 1
		return stopped

	# --- Updates ---

	def every(self):
		try:
			return max(0, int(self._every()))
		except Exception:
			return int(SUGGESTED)

	def due(self, now=None):
		"""The updates that are due now, each as it is to be said; the jobs count as heard. Called by the board's
		own thread, and by the tests with a time of their own."""
		every = self.every()
		if not every or self.isAsking:
			return []
		now = self.clock() if now is None else now
		texts = []
		for job in self.running():
			if job.quiet or job.paused or job.done.is_set() or (job.cancel is not None and job.cancel.is_set()):
				continue
			if now - job.heard < every:
				continue
			texts.append(job.update(now, first=not job.updates))
			job.updates += 1
			job.heard = now
		return texts

	def _say(self, text):
		debuglog.log("status", text)
		try:
			self._speak(text)
		except Exception as e:
			debuglog.error("busy", "A status update could not be said", e)

	def _watch(self):
		while not self._closed.wait(self._tick):
			with self._lock:
				if not self._jobs:
					self._thread = None
					return
			for text in self.due():
				self._say(text)
		with self._lock:
			self._thread = None

	def close(self):
		"""NVDA is closing: no more updates."""
		self._closed.set()
		for job in self.running():
			job.done.set()
