# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - one request from the user: its steps, its progress, and the switch that stops it.
# No NVDA dependencies.

import threading
import time

from . import debuglog

# States of a task.
UNDERSTANDING, PLANNING, AGREEING, WAITING, WORKING, CHECKING = (
	"understanding", "planning", "agreeing", "waiting", "working", "checking")
DONE, FAILED, CANCELLED = "done", "failed", "cancelled"
FINISHED = (DONE, FAILED, CANCELLED)

# Kinds of progress event. STATE and STEP are worth speaking; the rest go to the task window's log.
STATE, STEP, DETAIL, TALK, THINK, ANSWER, ERROR = "state", "step", "detail", "talk", "think", "answer", "error"

PENDING, RUNNING, STEP_DONE, STEP_FAILED, SKIPPED = "pending", "running", "done", "failed", "skipped"
# A step that was not done because what it depends on did not hold: "if you see the Recycle Bin, open it", and
# the Recycle Bin is not there. That is no failure.
NOT_NEEDED = "not needed"


class Cancelled(Exception):
	"""The user stopped the task."""


class Step:
	def __init__(self, title, tool, detail="", part="", recipe=None):
		self.title = title
		self.tool = tool
		self.detail = detail
		# The part of the user's request this step is for, in their own words.
		self.part = part
		# The recipe the step comes from, or None if a model wrote the step itself.
		self.recipe = recipe
		# What the chosen skills say about this kind of step (claw/skills.py), for the models that work on it.
		self.guide = ""
		self.status = PENDING
		self.result = ""
		# What was learned if the step first failed and then worked; kept in memory after the task.
		self.lesson = ""
		# A step that checks what others depend on has `test`, which says from its result whether that holds, and
		# `said`, which makes the sentence the user is told; `holds` is what the test said once the step is done.
		# A step that depends on one has it as `onlyIf` (planner.conditional).
		self.test = None
		self.said = None
		self.holds = None
		self.onlyIf = None

	def asDict(self):
		return {"title": self.title, "tool": self.tool, "detail": self.detail}

	def __repr__(self):
		return f"Step({self.tool}: {self.title!r}, {self.status})"


class Task:
	"""onEvent(task, kind, text) is called for every progress event, from the task's worker thread."""

	def __init__(self, request, onEvent=None, reasoning="auto"):
		self.request = request
		self.reasoning = reasoning
		self.cancel = threading.Event()
		self.state = UNDERSTANDING
		self.steps = []
		self.current = -1
		self.answer = ""
		self.log = []
		self.started = time.monotonic()
		self._onEvent = onEvent
		# What the task is doing right now, in a few words, for "where are we?".
		self.activity = ""
		# What it waits for at this moment, such as a model that is starting or answering: a sentence, or a function
		# that gives one as it is when it is asked for (claw/llm.py sets it for every question to a model). None
		# when it waits for nothing.
		self.now = None
		# Set when the task could not start because a model has not been downloaded: "vision" or "coder".
		self.missing = None
		self.params = None

	def emit(self, kind, text):
		self.log.append((time.monotonic() - self.started, kind, text))
		# Everything the user could have heard or read of a request is in VisionClaw's log too, whole.
		debuglog.log(f"task {kind}", text)
		if kind in (STATE, STEP):
			self.activity = text
		if self._onEvent is not None:
			try:
				self._onEvent(self, kind, text)
			except Exception:  # a broken listener must not stop the task
				pass

	def setState(self, state, text):
		self.state = state
		self.emit(STATE, text)

	def check(self):
		"""Call often. Leaves the task at once if the user stopped it."""
		if self.cancel.is_set():
			raise Cancelled()

	def stop(self):
		self.cancel.set()

	@property
	def finished(self):
		return self.state in FINISHED

	def seconds(self):
		return int(time.monotonic() - self.started)

	def progress(self):
		"""Where the task is, as (state, step number or 0, number of steps, activity, seconds)."""
		return (self.state, self.current + 1 if self.steps else 0, len(self.steps), self.activity, self.seconds())

	def nowText(self):
		"""What the task waits for at this moment, in a sentence, or ""."""
		now = self.now
		try:
			return str((now() if callable(now) else now) or "")
		except Exception:
			return ""

	def statusText(self):
		"""What it is doing and what it waits for, for a status update."""
		return " ".join(part for part in (self.activity, self.nowText()) if part)
