# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Status updates while VisionClaw takes long (claw/busy.py): when one is due, what it says, what counts as heard,
when nothing is said, the setting, NVDA+Alt+P and NVDA+Alt+X; what a request waits for while a model is asked
(claw/llm.py, task.py), with one model and with two; and whether a model is in memory (claw/runtime.py). Plain
Python, with a clock of the test's own."""
import re
import threading
import time

import harness  # noqa: F401
from visionClaw.claw import busy, llm, runtime
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION


class Clock:
	def __init__(self):
		self.now = 1000.0

	def __call__(self):
		return self.now


# --- The setting and the words ---

assert busy.CHOICES == ("10", "15", "30", "60", "off") and busy.SUGGESTED in busy.CHOICES
assert [busy.seconds(choice) for choice in busy.CHOICES] == [10, 15, 30, 60, 0]
assert busy.seconds("nonsense") == 15 and busy.seconds(None) == 15
assert busy.duration(0) == "0 seconds" and busy.duration(1) == "1 second" and busy.duration(45) == "45 seconds"
assert busy.duration(60) == "1 minute" and busy.duration(61) == "1 minute and 1 second"
assert busy.duration(125) == "2 minutes and 5 seconds" and busy.duration(180) == "3 minutes"

# --- When an update is due, and what it says ---

clock, every = Clock(), [15]
board = busy.Board(speak=None, every=lambda: every[0], clock=clock)
cancel = threading.Event()
step = ["Step 1 of 2: Finding the setting."]
job = board.begin("working on your request", lambda: step[0] + " The coder model is answering.", cancel=cancel)
assert board.running() == [job] and board.due() == []
clock.now += 14
assert board.due() == [], "nothing before the quiet has lasted"
clock.now += 1
first = board.due()
assert first == [
	"Still working on your request, 15 seconds so far. Step 1 of 2: Finding the setting. The coder model is answering. "
	"Press NVDA+Alt+P at any time to hear how far it is, or NVDA+Alt+X to stop it."], first
assert board.due() == [], "said once, then the quiet starts again"
# Later updates do not repeat the reminder, and say what it is doing now.
step[0] = "Step 2 of 2: Changing the setting."
clock.now += 15
again = board.due()
assert again == ["Still working on your request, 30 seconds so far. Step 2 of 2: Changing the setting. The coder model is answering."], again
assert "NVDA+Alt+P" not in again[0]
# A step the user heard counts: the quiet starts again.
clock.now += 10
job.heardNow()
clock.now += 10
assert board.due() == []
clock.now += 5
assert board.due()[0].startswith("Still working on your request, 55 seconds so far.")
# Above a minute the time is said in minutes and seconds.
clock.now += 25
assert board.due()[0].startswith("Still working on your request, 1 minute and 20 seconds so far.")

# NVDA+Alt+P says where everything is, and the quiet starts again.
clock.now += 14
text = board.progressText()
assert text == "Working on your request, 1 minute and 34 seconds so far. Step 2 of 2: Changing the setting. The coder model is answering.", text
clock.now += 14
assert board.due() == []

# While a question to the user is open, nothing is said: VisionClaw waits for the user, not for a model.
clock.now += 60
with board.asking():
	assert board.isAsking and board.due() == []
	assert board.progressText().endswith("VisionClaw is waiting for your answer to its question.")
	clock.now += 60
	assert board.due() == []
assert not board.isAsking
# After the answer the quiet starts again.
assert board.due() == []
clock.now += 15
assert len(board.due()) == 1

# A setting changed while a job runs counts at once; off says nothing; NVDA+Alt+P still works.
every[0] = 0
clock.now += 600
assert board.due() == [] and board.progressText().startswith("Working on your request, ")
every[0] = 60
clock.now += 59
assert board.due() == []
clock.now += 1
assert len(board.due()) == 1
every[0] = 15

# A job that was stopped says nothing more; NVDA+Alt+X stops what can be stopped.
quiet = board.begin("naming the icons in the overlay", "0 of 4 icons done so far.")
assert board.stop() == 1 and cancel.is_set(), "only the request had a switch"
assert board.stop() == 0
clock.now += 100
said = board.due()
assert said == ["Still naming the icons in the overlay, 1 minute and 40 seconds so far. 0 of 4 icons done so far. "
	"Press NVDA+Alt+P at any time to hear how far it is."], said
board.end(job)
board.end(job)  # ending twice does nothing
assert board.running() == [quiet]

# Once the answer is spoken or shown, nothing more is said; a paused job says nothing until it goes on.
seen = board.begin("describing the screen", "The vision model is looking at the picture.", cancel=threading.Event())
clock.now += 15
assert [text for text in board.due() if "describing" in text] and seen.updates == 1
seen.hush()
clock.now += 100
assert not [text for text in board.due() if "describing" in text]
quiet.pause()
clock.now += 100
assert board.due() == []
quiet.resume()
assert board.due() == [], "going on counts as heard"
clock.now += 15
assert len(board.due()) == 1
board.end(seen)

# What a job is doing that cannot be put into words is left out, and logged; nothing raises.
broken = board.begin("working out what you said", lambda: 1 / 0)
clock.now += 15
assert "Still working out what you said, 15 seconds so far. Press NVDA+Alt+P" in " ".join(board.due())
board.end(broken)
board.end(quiet, said=False)
assert board.running() == [] and board.progressText() == ""

# --- A job's end, said only after an update, and only when not stopped ---

spoken = []
board = busy.Board(speak=spoken.append, every=lambda: 15, clock=clock, tick=0.01)
icons = board.begin("naming the icons in the overlay", "1 of 2 icons done so far.", doneText="Finished naming the icons in the overlay.")
board.end(icons)
assert spoken == [], "over before any update: nothing to close"
icons = board.begin("naming the icons in the overlay", "1 of 2 icons done so far.", doneText="Finished naming the icons in the overlay.")
clock.now += 15
for _wait in range(500):
	if spoken:
		break
	time.sleep(0.01)
assert spoken and spoken[0].startswith("Still naming the icons in the overlay, 15 seconds so far."), spoken
board.end(icons)
assert spoken[-1] == "Finished naming the icons in the overlay.", spoken
# The board's own thread ends when nothing is left, and a new job starts it again.
for _wait in range(500):
	if board._thread is None:
		break
	time.sleep(0.01)
assert board._thread is None
del spoken[:]
stopped = threading.Event()
icons = board.begin("describing the screen", "x", cancel=stopped, doneText="Done.")
clock.now += 15
for _wait in range(500):
	if spoken:
		break
	time.sleep(0.01)
stopped.set()
board.end(icons)
assert spoken and spoken[-1] != "Done.", spoken
with board.job("working on your request", "y") as inside:
	assert board.running() == [inside]
assert board.running() == []
board.close()
for _wait in range(500):
	if board._thread is None:
		break
	time.sleep(0.01)
assert board._thread is None, "closing ends the board's thread"
assert board.begin("after closing", "z") is not None and board._thread is None, "a closed board starts no thread"

# --- What a request waits for while a model is asked ---


class Runtime:
	def __init__(self, one=False, loaded=True):
		self.one, self.isLoaded, self.during = one, loaded, []
		self.task = None

	def oneModel(self):
		return self.one

	def loaded(self, role):
		return self.isLoaded

	def entry(self, role):
		return {"thinking": True}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		self.during.append(self.task.nowText())
		return '{"reasoning": "", "answer": "yes"}' if "response_format" in (options or {}) else "Fine."


TWO = re.compile(r"\bmodels\b|agree|\b(vision|coder|other|another|second) model", re.IGNORECASE)
for one in (False, True):
	name = "model" if one else "coder model"
	rt = Runtime(one)
	task = rt.task = taskModule.Task("Make NVDA speak faster")
	asker = llm.LLM(rt, task)
	assert asker.waiting(CODER) == f"The {name} is answering."
	assert asker.waiting(CODER, llm.HIGH) == f"The {name} is thinking before it answers; thinking is set to high."
	rt.isLoaded = False
	assert asker.waiting(CODER, llm.HIGH) == f"Starting the {name}."
	rt.isLoaded = True
	# Set while the model is asked, as it is at that moment; cleared after.
	assert task.nowText() == ""
	asker.json(CODER, "system", "user", {"type": "object", "properties": {"answer": {"type": "string"}}}, reasoning=llm.MEDIUM)
	asker.text(CODER, "system", "user", reasoning=llm.OFF)
	asker.text(CODER, "system", "user", reasoning=llm.HIGH)
	assert rt.during == [
		f"The {name} is thinking before it answers; thinking is set to medium.", f"The {name} is answering.",
		f"The {name} is thinking before it answers; thinking is set to high."], rt.during
	assert task.now is None and task.nowText() == ""
	task.activity = "Step 1 of 2: Finding the setting."
	task.now = lambda: asker.waiting(CODER)
	assert task.statusText() == f"Step 1 of 2: Finding the setting. The {name} is answering."
	if one:
		# One model is never called two.
		for text in rt.during + [asker.waiting(VISION), asker.waiting(CODER, llm.LOW)]:
			assert not TWO.search(text), text
# A runtime that cannot say whether a model is loaded counts it as loaded; a failing one too.
assert llm.LLM(object(), task)._loaded(CODER) is True
broken = Runtime()
broken.loaded = lambda role: 1 / 0
assert llm.LLM(broken, task)._loaded(CODER) is True
# A model call that fails clears what the task waited for.
failing = Runtime()
failing.task = task


def failingChat(*args, **kwargs):
	raise RuntimeError("the engine went away")


failing.chat = failingChat
try:
	llm.LLM(failing, task).text(CODER, "s", "u")
except RuntimeError:
	pass
assert task.now is None
# What the task waits for that cannot be put into words is left out.
task.now = lambda: 1 / 0
assert task.nowText() == ""

# --- Whether a model is in memory ---


class Engine:
	def __init__(self):
		self.running, self.modelPath = False, None


entries = {VISION: {"id": "v"}, CODER: {"id": "c"}}
paths = {"v": ("vision.gguf", "mmproj.gguf"), "c": ("coder.gguf", None), "same": ("vision.gguf", None)}
stand = type("Catalog", (), {
	"selected": lambda self, role, preferred=None: entries[role],
	"paths": lambda self, entry: paths[entry["id"]],
})()
rt = runtime.ModelRuntime("engine", stand, lambda: {})
rt.engines = {VISION: Engine(), CODER: Engine()}
assert not rt.loaded(VISION) and not rt.loaded(CODER)
rt.engines[CODER].running, rt.engines[CODER].modelPath = True, "coder.gguf"
assert rt.loaded(CODER) and not rt.loaded(VISION)
# Running with another model is not loaded.
rt.engines[CODER].modelPath = "old.gguf"
assert not rt.loaded(CODER)
# One model for both jobs: the vision engine serves the coder role.
entries[CODER] = {"id": "same"}
rt.engines[VISION].running, rt.engines[VISION].modelPath = True, "vision.gguf"
assert rt.oneModel() and rt.loaded(CODER) and rt.loaded(VISION)
entries[CODER] = None
assert not rt.loaded(CODER)

print("OK")
