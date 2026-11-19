# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - smarter planning, by plain code. Before a model chooses how a request is done, it is given a short
# brief made of what fits this request and nothing else:
#   - where the user is, in plain words: the Windows desktop, the taskbar, a dialog, a web browser, a folder
#     window, a game (place);
#   - one or two planning notes that the user's own words call up (NOTES): facts about how a blind person's
#     request is best done with the keyboard and NVDA, such as that the Start menu is in no program's window;
#   - what worked before for a request in nearly the same words, kept on this computer (Plans);
#   - which jobs the skills that fit the request are for, so that the model is surely offered them (skillJobs).
# Asked for by the owner on 2026-11-18: "combine smart planning python module or modules, plus skills, rag,
# system prompts, memory to greatly enhance the planning of visionclaw and its AI models", after "click the start
# button" and "open the windows start menu" failed. Everything here only helps: a model still chooses, plain code
# still checks, and nothing here may end a request. No NVDA dependencies.
#
# The arithmetic, all in Python's own standard library because NVDA's Python has nothing else:
#   - BM25 (Robertson and Sparck Jones' ranking, as search engines use it) puts the notes the words call up in
#     order: a rare word of the request that a note has counts for more than a common one (bm25);
#   - how alike two requests are is the Jaccard index of their telling words (alike);
#   - how surely a plan works is Laplace's rule of succession, (good + 1) / (good + bad + 2), so that one success
#     says little and a failure counts against it; and a plan's weight halves every HALF_LIFE_DAYS, so that what
#     worked lately wins (Plans.rate).

import json
import math
import os
import re
import threading
import time

from . import debuglog
from .memory import wordList, words as tellingWords

# --- Where the user is ---

_BROWSERS = ("chrome", "firefox", "msedge", "brave", "opera", "vivaldi", "iexplore", "waterfox", "librewolf", "thorium")
_GAME_WORDS = re.compile(r"\b(game|steam|unity|unreal|godot|minecraft|launcher)\b", re.IGNORECASE)


def place(app, title="", windowClass=""):
	"""Where the user is, in a few plain words, or "" when nothing more can be said than the program's name.
	From the program's name, the window's title and the window's class, as NVDA reports them."""
	app = (app or "").lower()
	title = title or ""
	windowClass = windowClass or ""
	if windowClass in ("Progman", "WorkerW") or (app == "explorer" and title == "Program Manager"):
		return ("the Windows desktop, which holds only the desktop icons; the Start button, the taskbar and the "
			"notification area are not in it")
	if windowClass in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
		return "the taskbar of Windows"
	if app == "startmenuexperiencehost":
		return "the Start menu of Windows"
	if app in ("searchhost", "searchapp", "searchui"):
		return "Windows search"
	if app == "shellexperiencehost":
		return "a panel of Windows itself, such as quick settings or the notification center"
	if app == "explorer" and windowClass == "CabinetWClass":
		return "a folder window of File Explorer"
	if app in _BROWSERS:
		return "a web browser"
	if app == "nvda":
		return "a window of NVDA itself"
	if windowClass == "#32770":
		return "a dialog box"
	if _GAME_WORDS.search(f"{app} {title}"):
		return "what may be a game"
	return ""


# The places that are Windows' own shell: nothing in them has a Start button, a taskbar or a notification area of
# its own, so words that name one mean that of Windows.
SHELL_PLACES = ("the Windows desktop", "the taskbar of Windows", "the Start menu of Windows", "Windows search",
	"a panel of Windows itself", "a folder window of File Explorer")


def isShell(app, title="", windowClass=""):
	"""Whether Windows' own shell is in front: the desktop, the taskbar, the Start menu, search, a panel of
	Windows or a folder window."""
	return place(app, title, windowClass).startswith(SHELL_PLACES)


def placeText(app, title="", windowClass=""):
	"""The sentence about where the user is that goes with a request, or ""."""
	where = place(app, title, windowClass)
	return f"This is {where}." if where else ""


# --- Planning notes, called up by the user's own words ---

# (what the words must name, the recipes the note is about, the note). Each note is a fact about doing a request
# for a blind person with the keyboard and NVDA, says which job fits, and has no example in it: a small model
# copies an example. A note is given only when its words are in the request, and at most MAX_NOTES of them.
NOTES = (
	(r"\b(start (button|menu|screen)|task ?bar|system ?tray|notification (area|cent(er|re))|quick settings|"
		r"action cent(er|re)|task view|run dialog|clipboard history|emoji panel|hidden icons)\b",
		("windows_part",),
		"The Start button, the Start menu, the taskbar, the notification area, quick settings and the notification "
		"center are parts of Windows itself and in no program's window. They are opened with Windows' own keys: "
		"windows_part."),
	(r"\b(open|launch|start|run)\b.*\b(program|app|application|folder|file|game|settings)\b"
		r"|\b(open|launch)\b(?!.*\b(button|link|tab|menu|item|icon)\b)",
		("open_thing",),
		"A program, folder, file or settings page of Windows is opened by its name from anywhere: open_thing. A "
		"button or item inside the window in front is clicked instead: click."),
	(r"\b(click|press|push|activate|select)\b.*\b(button|link|tab|icon|item|check ?box|menu)\b",
		("click",),
		"A button, link, tab or icon is clicked only when it is in the window in front or on the web page in front. "
		"Something of Windows itself, or of another program, is reached another way."),
	(r"\b(press|hit|type)\b.*\b(key|keys|enter|escape|tab|control|ctrl|alt|shift|f\d+)\b|\bkeyboard shortcut\b",
		("press_keys", "do_command"),
		"Keys that are pressed go to the program in front. A command of NVDA itself is done with do_command, not by "
		"pressing its keys."),
	(r"\b(speak|speech|voice|rate|pitch|volume|punctuation|echo|braille|verbosity)\b",
		("change_setting", "system_volume"),
		"How NVDA speaks or shows braille is an NVDA setting: change_setting. The loudness of the whole computer is "
		"system_volume."),
	(r"\b(how (do|can|to|would)|what (key|keys|shortcut|command)|which (key|keys|command))\b",
		("explain_keys", "nvda_question"),
		"A question about how something is done is answered with the keys for it, and nothing is done: "
		"explain_keys."),
	(r"\b(every time|whenever|each time|always|automatically|from now on)\b",
		("write_addon", "make_hotkey", "add_fix", "remember"),
		"Something that is to happen every time on its own needs an add-on: write_addon. Something done once is "
		"done now with another job. A wish about how answers are given is remembered: remember."),
	(r"\b(add-?on|plug-?in|script|code)\b",
		("write_addon", "fix_addon", "addon_question", "save_addon"),
		"A new add-on is written with write_addon; one VisionClaw made that fails is repaired with fix_addon; a "
		"question about an installed add-on is addon_question."),
	(r"\b(switch to|go to|bring up|close|minimi[sz]e|maximi[sz]e)\b.*\b(window|program|app)\b",
		("window",),
		"Another open window or program is switched to, closed, minimized or maximized with window."),
	(r"\b(web ?site|web ?page|page|link|browser|url|www|\.com)\b",
		("open_website", "web_page", "click", "go_to"),
		"A website is opened with open_website. On a web page that is in front, its links and buttons are clicked "
		"with click, and questions about it are web_page."),
	(r"\b(read|tell me|say|what (is|does)|describe)\b.*\b(screen|window|picture|image|photo|this)\b",
		("describe", "read_text", "where_am_i"),
		"What the screen or a picture shows is describe; its exact words are read_text; which program and control "
		"the user is in is where_am_i."),
)
MAX_NOTES = 2
# BM25's two numbers, as they are usually chosen: how fast a word that comes again stops counting more (K1), and
# how much a long text is held against it (B).
K1, B = 1.2, 0.75


def bm25(query, texts):
	"""BM25 scores of texts for a query, one for each text, from their telling words without endings. A word
	that few texts have counts for more than one that many have."""
	docs = [wordList(text) for text in texts]
	if not docs:
		return []
	count = len(docs)
	average = sum(len(doc) for doc in docs) / count or 1.0
	having = {}
	for doc in docs:
		for word in set(doc):
			having[word] = having.get(word, 0) + 1
	scores = []
	for doc in docs:
		score = 0.0
		for word in set(wordList(query)):
			times = doc.count(word)
			if not times:
				continue
			idf = math.log(1 + (count - having[word] + 0.5) / (having[word] + 0.5))
			score += idf * times * (K1 + 1) / (times + K1 * (1 - B + B * len(doc) / average))
		scores.append(score)
	return scores


def notesFor(request, available=None):
	"""The planning notes the user's own words call up, at most MAX_NOTES, the best first. A note is called up
	only by the words its pattern names; among those, BM25 puts first the one that shares the rarest words with
	the request. available: the recipes that can be used here; a note about none of them is left out."""
	text = " ".join((request or "").lower().split())
	called = [index for index, (pattern, recipes, _note) in enumerate(NOTES)
		if (available is None or any(recipe in available for recipe in recipes)) and re.search(pattern, text)]
	if not called:
		return []
	scores = bm25(text, [NOTES[index][2] for index in range(len(NOTES))])
	# Ties keep the order of NOTES, which goes from the surest to the most general.
	called.sort(key=lambda index: (-round(scores[index], 6), index))
	return [NOTES[index][2] for index in called[:MAX_NOTES]]


# --- What worked before ---

MAX_PLANS = 200
# How alike two requests must be, as the share of their telling words they have in common.
ALIKE = 0.75
# Fewer telling words than this say too little to be compared.
LEAST_WORDS = 2
# How surely a plan must have worked to be named, by Laplace's rule: one success and no failure is 2/3.
SURE_ENOUGH = 0.6
# A plan's weight halves in this many days, so that what worked lately wins over what worked long ago.
HALF_LIFE_DAYS = 90


def alike(first, second):
	"""How alike two requests are, from 0 to 1: the telling words they share, of all they have."""
	a, b = tellingWords(first), tellingWords(second)
	if len(a) < LEAST_WORDS or len(b) < LEAST_WORDS:
		return 0.0
	return len(a & b) / len(a | b)


def rate(good, bad):
	"""How surely a plan works, by Laplace's rule of succession: (good + 1) / (good + bad + 2)."""
	return (max(0, good) + 1) / (max(0, good) + max(0, bad) + 2)


class Plans:
	"""How requests of one part were done on this computer: for each request and recipe, how often it went well
	(done to the end, nothing the user said no to) and how often not. Kept as data in plans.json in VisionClaw's
	data folder, never code. Used only as what a model is told and as a job it is surely offered; a model and the
	user's own words still decide. path None: kept only while NVDA runs."""

	def __init__(self, path=None, clock=time.time):
		self._path = path
		self._lock = threading.Lock()
		self._plans = None
		self._clock = clock

	def _load(self):
		if self._plans is not None:
			return self._plans
		self._plans = []
		if self._path and os.path.isfile(self._path):
			try:
				with open(self._path, encoding="utf-8") as f:
					data = json.load(f)
				self._plans = [plan for plan in data if isinstance(plan, dict) and plan.get("request") and plan.get("recipe")]
			except (OSError, ValueError) as e:
				debuglog.error("planning", "The plans that worked before could not be read", e)
		return self._plans

	def _save(self):
		if not self._path:
			return
		try:
			os.makedirs(os.path.dirname(self._path), exist_ok=True)
			temporary = self._path + ".tmp"
			with open(temporary, "w", encoding="utf-8") as f:
				json.dump(self._plans, f, ensure_ascii=False, indent=1)
			os.replace(temporary, self._path)
		except OSError as e:
			debuglog.error("planning", "The plans that worked before could not be saved", e)

	def keep(self, request, recipe, good=True):
		"""Count how a request was done: well (good) or not. The plan of a request in nearly the same words with
		the same recipe is counted on; its words become the newest."""
		request = " ".join(str(request or "").split())[:200]
		if not request or not recipe or len(tellingWords(request)) < LEAST_WORDS:
			return
		with self._lock:
			plans = self._load()
			plan = next((one for one in plans if one["recipe"] == recipe and alike(one["request"], request) >= ALIKE), None)
			if plan is None:
				plan = {"request": request, "recipe": recipe, "good": 0, "bad": 0}
			else:
				plans.remove(plan)
			plan["request"] = request
			plan.setdefault("good", 0)
			plan.setdefault("bad", 0)
			key = "good" if good else "bad"
			plan[key] = int(plan[key]) + 1
			plan["at"] = round(self._clock())
			plans.append(plan)
			self._plans = plans[-MAX_PLANS:]
			self._save()
		debuglog.log("planning", f"Kept: {request!r} as {recipe} went {'well' if good else 'not well'} "
			f"({plan['good']} well, {plan['bad']} not).")

	def weight(self, plan, request):
		"""How much a kept plan says about a request: how alike the requests are, how surely the plan worked, and
		how lately, multiplied."""
		age = max(0.0, self._clock() - float(plan.get("at", 0))) / 86400
		fresh = 0.5 ** (age / HALF_LIFE_DAYS)
		return alike(plan["request"], request) * rate(int(plan.get("good", 0)), int(plan.get("bad", 0))) * fresh

	def recall(self, request, available=None):
		"""The plan of an alike request that has proved itself, as (its request, its recipe), or None. Where
		plans of alike requests have different recipes, the one with the most weight wins."""
		with self._lock:
			plans = list(self._load())
		best, most = None, 0.0
		for plan in plans:
			if available is not None and plan["recipe"] not in available:
				continue
			if alike(plan["request"], request) < ALIKE or rate(int(plan.get("good", 0)), int(plan.get("bad", 0))) < SURE_ENOUGH:
				continue
			now = self.weight(plan, request)
			if now > most:
				best, most = plan, now
		return (best["request"], best["recipe"]) if best else None

	def forget(self):
		"""Forget every plan."""
		with self._lock:
			self._plans = []
			self._save()

	def count(self):
		with self._lock:
			return len(self._load())


# What a step's result begins with when nothing was done, though the step ended.
_NOTHING_DONE = ("You said no", "VisionClaw did not do this", "Nothing was")


def outcome(task):
	"""How a request went, for counting its plan: True when every step was done and nothing says that nothing
	was done; False when a step failed or nothing was done; None when the user said no, which says nothing
	about the plan."""
	steps = list(getattr(task, "steps", None) or [])
	if not steps:
		return None
	results = [str(getattr(step, "result", "") or "") for step in steps]
	if any(result.startswith("You said no") for result in results):
		return None
	for step, result in zip(steps, results):
		if getattr(step, "status", "") != "done" or result.startswith(_NOTHING_DONE):
			return False
	return True


def wentWell(task):
	"""Whether a request went well: every step done, nothing the user said no to, and nothing that says nothing
	was done."""
	return outcome(task) is True


# --- Skills ---

def skillJobs(skills, available):
	"""The jobs that the skills which fit the request are for, among those that can be used here. They are
	offered to the model that chooses, so that a job a skill speaks about is never left out; the skills' own
	sentences still go only to the steps and the answer."""
	jobs = []
	for skill in skills or ():
		for job in getattr(skill, "uses", ()) or ():
			if job in available and job not in jobs:
				jobs.append(job)
	return jobs


# --- The brief ---

def brief(request, available, plans=None, label=None):
	"""What the model that chooses is told besides the request: the planning notes the words call up and what
	worked before. Returns (text, the recipe that worked before or None)."""
	lines = []
	notes = notesFor(request, available)
	if notes:
		lines.append("Good to know: " + " ".join(notes))
	before = None
	if plans is not None:
		try:
			found = plans.recall(request, available)
		except Exception as e:
			debuglog.error("planning", "The plans that worked before could not be looked at", e)
			found = None
		if found is not None:
			said, before = found
			named = label(before) if label else before
			lines.append(f"Earlier, \"{said}\" was done well this way: {before} ({named}).")
	return "\n".join(lines), before
