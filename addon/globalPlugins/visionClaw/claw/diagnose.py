# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - VisionClaw reads its own logs, says what went wrong, and corrects its own code, only when the user asks.
# The owner said on 2026-11-19: "give visionclaw access to its own logs, so through the coding and vision model, a user
# can have visionclaw diagnose and fix its own bugs", and: "visionclaw must only read its own logs and fix its own bugs
# upon user request." What follows from it:
#   - Plain code reads the user's words (wish). Nothing here runs by itself: not after an error, not at start-up, not
#     as a step a model planned. The one thing done at start-up is to use again a correction the user said yes to.
#   - Plain code reads the logs (errors, lastRequest): every error with the place in the code where it happened, how
#     often, and the request it happened in. Nothing is sent anywhere.
#   - The model that writes code reads the error and the lines of VisionClaw's own code where it happened, and says in
#     plain words what went wrong (DIAGNOSE_TASK), said to be the model's and possibly wrong.
#   - A correction is one function, written again by the model that writes code, checked by plain code (checkFix:
#     it parses, keeps its name and arguments, changes few lines, adds no import and nothing that reaches the internet,
#     starts programs or deletes files, and the whole file still compiles), read by the other model (REVIEW_SYSTEM),
#     and used only after the user says yes, always asked (mustAgree in the tool).
#   - VisionClaw's own files are never changed. A correction is data in the folder "ownfixes" of VisionClaw's data:
#     the function as it was and as it is now, which is put in place of the old one while NVDA runs (Fixes.apply) and
#     again whenever VisionClaw starts, for the version it was made for only. The function that takes its place runs
#     the correction and, when the correction itself fails, turns it off and runs the old function from then on
#     (guarded). An update of VisionClaw puts its code back as released; a correction for another version is put aside.
#   - Undone with "undo that" (the list of changes) or in words. A report in Markdown says what was found and changed,
#     for the user to keep or to give to VisionClaw's developer.
#   - A complaint about what VisionClaw just did, with no error in the log (the section at the end of this file). The
#     owner said on 2026-11-19, after NVDA's settings were opened with the focus on "Make screen black" instead of the
#     Logging level combo box and nothing was written to the log: "visionclaw must be able to fix such focus and other
#     bugs by itself using its AI models and skills, when I complain about a problem like this." Plain code reads the
#     complaint, finds the request it is about and the functions of VisionClaw's own code that request used, and ranks
#     them by the complaint's words; the model that writes code chooses one by its number and corrects it; then the same
#     checks, review and question as for an error. It is never said to be fixed: the user is asked to try again.
# The checks prevent accidents; they are not a sandbox. Never describe them as one. No NVDA dependencies.

import ast
import difflib
import dis
import functools
import hashlib
import importlib
import inspect
import json
import os
import re
import sys
import textwrap
import threading
import time
import types

from . import corrections, debuglog, inside, match, ranking
from .llm import clip, uncut
from .memory import words
from .prompts import IDENTITY

FOLDER = "ownfixes"
FIXES_FILE = "fixes.json"
# The logs VisionClaw keeps in the folder "logs" of its data, and what each is.
LOGS = ("visionclaw.log", "engine.log", "coder.log", "speech.log")
# How many errors are said at most when the user asks for them; the rest are counted.
MAX_LISTED = 8
# A correction changes at most this many lines of the function: a larger one is a rewrite, and is refused.
MAX_CHANGED = 16
# How many times the model that writes code may try again after plain code found a problem in its correction.
TRIES = 3
# Where VisionClaw's own code is, inside the add-on's folder, and the package it is as Python knows it while it runs:
# globalPlugins.visionClaw inside NVDA.
OWN_PACKAGE = ("globalPlugins", "visionClaw")
PACKAGE = __name__.rsplit(".claw.", 1)[0] if ".claw." in __name__ else ".".join(OWN_PACKAGE)
# Files whose functions are never corrected: what installs and carries the data, and what corrects and checks itself.
NEVER = frozenset(("installTasks.py", "claw/portable.py", "claw/diagnose.py", "diagnosetools.py", "claw/debuglog.py", "vclog.py"))
# Functions that run once while VisionClaw starts or closes: a correction would never be used.
_ONCE = frozenset(("__init__", "terminate", "onInstall", "onUninstall", "register", "build"))
# What a correction may not add where the function did not have it already: reaching the internet, starting programs,
# deleting files, running text as code, changing what other code finds.
FORBIDDEN = frozenset((
	"eval", "exec", "compile", "__import__", "globals", "setattr", "delattr", "system", "popen", "Popen", "spawn",
	"remove", "unlink", "rmdir", "rmtree", "removedirs", "startfile", "ShellExecuteW", "urlopen", "Request", "socket",
	"subprocess", "shutil", "requests", "http", "urllib", "ftplib", "smtplib", "webbrowser", "connect", "send", "sendall"))
# What a function raises in the ordinary course of VisionClaw's work: the user stopped or said no, a tool refused, a
# model or the engine is missing. Such an exception from a correction is no failure of the correction.
PASSED_ON = frozenset((
	"Cancelled", "Declined", "EngineError", "LLMError", "ModelMissing", "ToolError", "UserSaidNo", "Refused",
	"NotPossible", "StopIteration", "GeneratorExit"))

ERRORS, WHY, FIX, FIXES, REMOVE = "errors", "why", "fix", "fixes", "remove"

# --- What the user asks ---

_ME = r"(?:you|your|yourself|your own|visionclaw'?s?|vision claw'?s?)"
_FAULT = r"(?:bugs?|errors?|crash(?:es|ed)?|faults?|exceptions?|problems?|mistakes?|glitch(?:es)?|tracebacks?)"
_FIX = re.compile(
	rf"\b(fix|repair|correct|patch|debug and fix|debug)\b.{{0,40}}\b{_ME}\b.{{0,30}}\b({_FAULT}|code|source|self)\b"
	rf"|\b(fix|repair|correct|patch)\b\s+(yourself|your own code|your code|visionclaw)\b"
	rf"|\b(fix|repair|correct|patch)\b\s+(that|this|the|the last|your last)\s+{_FAULT}\b"
	rf"(?!.*\b(add-?on|setting|page|form|file|document|website|program|app)\b)"
	rf"|\b(heal|mend)\b\s+(yourself|your code)\b"
	rf"|\b(fix|repair|correct|patch)\b.{{0,30}}\b{_FAULT}\b.{{0,20}}\b(in|from|of) {_ME} (own )?(log|logs|code)\b", re.IGNORECASE)
_REMOVE = re.compile(
	rf"\b(remove|undo|take back|turn off|delete|forget|drop|stop using)\b.{{0,40}}\b(corrections?|fix(es)?|patch(es)?)\b"
	rf".{{0,30}}\b({_ME}|own code|your code|yourself)\b"
	rf"|\b(remove|undo|take back|delete|drop)\b.{{0,12}}\b(the |your )?(corrections?|fix(es)?|patch(es)?) (you made|to yourself|you wrote)\b",
	re.IGNORECASE)
_FIXES = re.compile(
	rf"\b(which|what|list|show|tell me|how many|any)\b.{{0,30}}\b(corrections?|fix(es)?|patch(es)?)\b.{{0,40}}"
	rf"\b(you (made|did|wrote|applied)|to (yourself|your (own )?code)|of your (own )?code|in your (own )?code|you have made)\b",
	re.IGNORECASE)
_WHY = re.compile(
	rf"\b(diagnose|why did|why does|why do|why is|why isn't|why won't|why didn't|why can't|what went wrong|"
	rf"what('s| is) wrong|what happened|figure out|find out|explain|work out|investigate|look into)\b.{{0,60}}"
	rf"(\b{_ME}\b.{{0,30}}\b({_FAULT}|log|logs|fail\w*|crash\w*|break\w*|broke|wrong|not work\w*|stop\w*)\b"
	rf"|\b(my|the|your) (last |previous |latest )?(request|task|command|answer|description)\b.{{0,30}}\b(fail\w*|go wrong|went wrong|"
	rf"not work\w*|didn't work|stop\w*|break|broke|crash\w*|error\w*)\b|\b(that|this|the|your last) {_FAULT}\b)"
	rf"|\bdiagnose\b\s+(yourself|your (own )?(errors?|bugs?|log|problems?))\b"
	rf"|\b(what went wrong|what happened|what was wrong) (with|in|during) (my|the|your) (last |previous |latest )?"
	rf"(request|task|command)\b", re.IGNORECASE)
_ERRORS = re.compile(
	rf"\b(read|check|look (at|in|through|into)|show|list|go through|search|scan|what('s| is| are)?|any|tell me|are there|"
	rf"have there been|how many)\b.{{0,40}}\b({_ME} (own )?(log|logs|errors?|bugs?|crash(es)?|faults?|problems?|exceptions?)"
	rf"|(errors?|bugs?|crash(es)?|faults?|exceptions?) (in|of) {_ME} (own )?(logs?|code))\b"
	rf"|\b(errors?|problems?|faults?) (in|from) (the |visionclaw'?s? |your )?(engine|speech|coder) log\b", re.IGNORECASE)
# The log itself asked for, to be read by the user: the job that opens it (planner "visionclaw_log").
_OPEN_LOG = re.compile(r"\b(open|show( me)?|bring up|let me (see|read)|where is)\b.{0,20}\b(the |your |visionclaw'?s? )?(own )?(debug )?"
	r"logs?( file| folder)?\b", re.IGNORECASE)
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": 1, "latest": 1, "newest": 1,
	"previous": 2, "oldest": -1}
_WHICH_NUMBER = re.compile(r"\b(?:error|bug|crash|fault|number)\s+(\d{1,2})\b|\bthe (first|second|third|fourth|fifth|last|latest|"
	r"newest|previous|oldest) (?:error|bug|crash|fault|one|problem)\b", re.IGNORECASE)
_ASKING_WORDS = words(
	"fix repair correct patch debug diagnose why what went wrong error errors bug bugs crash crashes fault faults problem "
	"problems mistake mistakes exception your yourself own visionclaw vision claw log logs code source last latest newest "
	"first second third request task please can could would you tell explain find figure out look into happened fail "
	"failed failing break broke broken stop stopped work works working check show list undo remove take back "
	"fixes correction corrections patch patches made make did wrote turn drop")


def wish(text):
	"""What the user's own words ask of VisionClaw's own logs and code, or None where they ask nothing of them: a
	dictionary with do (ERRORS, WHY, FIX, FIXES, REMOVE), which (a number, 1 the newest, -1 the oldest, or None),
	about (the words that say which error is meant) and complaint (the user's words where they say that what VisionClaw
	just did was wrong, else ""). Kept narrow: the words must name VisionClaw or "you" with its log, its errors or its
	code, ask why the last request went wrong, or say that what VisionClaw, "you" or "it" just did was wrong
	(complaintOf). A complaint asks for a correction, or, asked with why, for what happened. "Open your log" is the log
	opened, not read here."""
	said = " ".join(str(text or "").split())
	low = said.lower()
	if not said:
		return None
	found = None
	if _REMOVE.search(low):
		found = REMOVE
	elif _FIXES.search(low):
		found = FIXES
	elif _FIX.search(low):
		found = FIX
	elif _WHY.search(low):
		found = WHY
	elif _ERRORS.search(low) and not (_OPEN_LOG.search(low) and not re.search(rf"\b{_FAULT}", low)):
		found = ERRORS
	complaint = complaintOf(said) if found in (None, FIX, WHY) else None
	if found is None and complaint:
		found = WHY if _ASKS_WHY.search(low) else FIX
	if found is None:
		return None
	return {"do": found, "which": whichNumber(low), "about": " ".join(sorted(words(said) - _ASKING_WORDS)),
		"request": bool(re.search(r"\b(request|task|command|answer|description)\b", low)), "complaint": complaint or ""}


def whichNumber(text):
	found = _WHICH_NUMBER.search(text or "")
	if not found:
		return None
	return int(found.group(1)) if found.group(1) else _ORDINALS.get(found.group(2).lower())


# --- Reading the logs ---

_ENTRY = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.\d{3})? \[([^\]]*)\] ([\w.-]+): ?(.*)$")
_FRAME = re.compile(r'^\s*File "([^"]+)", line (\d+), in (\S+)')
_EXCEPTION = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning|Cancelled|Declined|Missing|Refused)"
	r"|[A-Z]\w+)(?::\s?(.*))?$")
_NEW_REQUEST = re.compile(r"^New request: (['\"])(.*)\1\. Reasoning setting")
_ENDED = re.compile(r"^Request ended as (\w+) after ([\d.]+) seconds\.")
_TOOL_FAILED = re.compile(r"^(\w+) could not do it after [\d.]+ s: (.*)$")


class Error:
	"""An error in VisionClaw's log, with the place in the code where it happened. trace: [(file, line, function)],
	from the outermost to where it happened; exception: the last line of the trace ("OSError: ..."); request: the
	request that was being carried out on that thread, or ""."""

	def __init__(self, when, thread, area, message, trace, exception, request):
		self.when = when
		self.thread = thread
		self.area = area
		self.message = message
		self.trace = trace
		self.exception = exception
		self.request = request
		self.count = 1
		self.first = when

	def key(self):
		place = self.trace[-1] if self.trace else ("", 0, "")
		return (self.message, self.exception.split(":", 1)[0], place[0], place[2])

	def kind(self):
		return self.exception.split(":", 1)[0].strip() if self.exception else ""


def _requestOf(started):
	"""The request as the user said it, from the line that says it began: the log writes it as Python writes a string."""
	quoted = started.group(1) + started.group(2) + started.group(1)
	try:
		return str(ast.literal_eval(quoted))
	except (ValueError, SyntaxError):
		return started.group(2)


def entries(text):
	"""The entries of a log: (time, thread, area, first line, [the lines after it])."""
	found = []
	for raw in str(text or "").splitlines():
		head = _ENTRY.match(raw)
		if head:
			found.append([head.group(1), head.group(2), head.group(3), head.group(4), []])
		elif found:
			found[-1][4].append(raw[1:] if raw.startswith("\t") else raw)
	return found


def errors(text):
	"""The errors of a log, the newest first, each once with how often it happened and when first and last."""
	working = {}
	grouped = {}
	for when, thread, area, first, rest in entries(text):
		if area == "task":
			started = _NEW_REQUEST.match(first)
			if started:
				working[thread] = _requestOf(started)
				continue
			if _ENDED.match(first):
				working.pop(thread, None)
				continue
		if not first.startswith("ERROR: "):
			continue
		trace = [(m.group(1), int(m.group(2)), m.group(3)) for m in map(_FRAME.match, rest) if m]
		exception = next((line.strip() for line in reversed(rest) if line.strip() and not line.startswith(" ")
			and _EXCEPTION.match(line.strip()) and not line.strip().startswith(("Traceback", "File "))), "")
		error = Error(when, thread, area, first[len("ERROR: "):].strip(), trace, exception, working.get(thread, ""))
		key = error.key()
		if key in grouped:
			old = grouped[key]
			old.count += 1
			# The newest is told: its line fits the code that runs now, and the request is the last one it happened in.
			old.when, old.request = error.when, error.request or old.request
			old.trace, old.exception = error.trace or old.trace, error.exception or old.exception
		else:
			grouped[key] = error
	return sorted(grouped.values(), key=lambda error: error.when, reverse=True)


def lastRequest(text):
	"""What the log says of the last request that ended: {request, ended, seconds, problems [(tool, reason)], errors
	[message]} and what requests() adds, or None."""
	found = requests(text)
	return found[-1] if found else None


def requests(text):
	"""Every request of a log that ended, the oldest first: {request, said, when, ended, seconds, problems [(tool,
	reason)], errors [message], steps [{tool, status, result}], asked [(question, what the user chose)], answer}. The
	request is as the user said it; a step's result is there only where the log was detailed."""
	stories = []
	current = {}
	for when, thread, area, first, rest in entries(text):
		if area == "task":
			started = _NEW_REQUEST.match(first)
			if started:
				current[thread] = {"request": _requestOf(started), "said": _requestOf(started), "when": when, "problems": [],
					"errors": [], "ended": "", "seconds": "", "steps": [], "asked": [], "answer": "", "results": {}}
				continue
			ended = _ENDED.match(first)
			if ended and thread in current:
				done = current.pop(thread)
				done["ended"], done["seconds"] = ended.group(1), ended.group(2)
				steps, answer = _endedParts(first)
				results = done.pop("results")
				done["steps"] = [{"tool": tool, "status": status, "result": results.get(tool, "")} for tool, status in steps]
				done["answer"] = answer
				stories.append(done)
				continue
		if thread not in current:
			continue
		story = current[thread]
		failed = _TOOL_FAILED.match(first) if area == "tool" else None
		if failed:
			story["problems"].append((failed.group(1), failed.group(2)))
		elif first.startswith("ERROR: "):
			story["errors"].append(first[len("ERROR: "):].strip())
		elif area == "tool" and first.endswith(" result:") and rest:
			story["results"][first[:-len(" result:")].strip()] = "\n".join(rest).strip()
		elif area == "ask" and first.startswith("Asking the user: "):
			question = first[len("Asking the user: "):]
			story["asked"].append([question.split(" Choices: ", 1)[0], ""])
		elif area == "ask" and first.startswith("The user chose: ") and story["asked"]:
			story["asked"][-1][1] = first[len("The user chose: "):]
	return stories


def _endedParts(line):
	"""The steps and the answer from the line that says a request ended: ([(tool, status)], answer)."""
	steps, answer = [], ""
	try:
		middle = line.split(" Steps: ", 1)[1]
		listed, said = middle.rsplit(". Answer: ", 1)
		steps = [(str(tool), str(status)) for tool, status in ast.literal_eval(listed)]
		answer = str(ast.literal_eval(said.strip()))
	except (IndexError, ValueError, SyntaxError, TypeError):
		pass
	return steps, answer


def readLogs(folder, names=LOGS[:1], older=1):
	"""The text of VisionClaw's logs in folder, the older ones put aside first, so that the newest is last."""
	parts = []
	for name in names:
		path = os.path.join(folder, name)
		for number in range(older, 0, -1):
			parts.append(_readFile(f"{path}.{number}"))
		parts.append(_readFile(path))
	return "\n".join(part for part in parts if part)


def engineTrouble(folder, limit=6):
	"""The last lines in which the engines wrote that something failed, as they wrote them."""
	found = []
	for name in LOGS[1:]:
		text = _readFile(os.path.join(folder, name))
		for line in text.splitlines():
			if re.search(r"\b(error|failed|failure|out of memory|unable|cannot|could not|abort\w*)\b", line, re.IGNORECASE):
				found.append(f"{name}: {' '.join(line.split())}")
	return found[-limit:]


def _readFile(path):
	try:
		with open(path, encoding="utf-8", errors="replace") as f:
			return f.read()
	except OSError:
		return ""


def own(path, root):
	"""The place of a file in VisionClaw's own code, as "claw/llm.py", or "" where it is not VisionClaw's: NVDA's own code,
	Python's, or another add-on's. root: the folder globalPlugins/visionClaw of the add-on that is running."""
	normal = str(path or "").replace("\\", "/")
	marker = "/".join(OWN_PACKAGE) + "/"
	at = normal.lower().rfind(marker.lower())
	if at < 0:
		base = str(root or "").replace("\\", "/").rstrip("/") + "/"
		if root and normal.lower().startswith(base.lower()):
			return normal[len(base):]
		return ""
	return normal[at + len(marker):]


def ownFrame(error, root):
	"""Where in VisionClaw's own code an error happened: the last place of the trace that is VisionClaw's, as (file,
	line, function), or None when all of it is NVDA's or Python's."""
	for path, line, function in reversed(error.trace):
		place = own(path, root)
		if place and place.endswith(".py"):
			return place, line, function
	return None


def otherCode(error, root):
	"""The places past VisionClaw's own code where the error went on, as words: "NVDA's virtualBuffers"."""
	frame = ownFrame(error, root)
	if frame is None:
		return []
	after = False
	found = []
	for path, line, function in error.trace:
		if after and not own(path, root):
			name = os.path.splitext(os.path.basename(str(path).replace("\\", "/")))[0]
			module = str(path).replace("\\", "/").split("/")[0].split(".")[0] if "/" in str(path).replace("\\", "/") else name
			found.append(f"{module}" if module == name else f"{module} ({name})")
		if own(path, root) and (own(path, root), line, function) == frame:
			after = True
	return list(dict.fromkeys(found))


def chosen(found, wish_, root=None):
	"""The error a request is about: by its number (1 the newest), by the words that name it, else the newest; where the
	user asks for a correction, the newest one that happened in VisionClaw's own code."""
	if not found:
		return None
	pool = found
	if wish_ and wish_.get("do") == FIX and root is not None:
		pool = [error for error in found if ownFrame(error, root) is not None] or found
	which = (wish_ or {}).get("which")
	if which:
		return pool[which - 1] if 0 < which <= len(pool) else pool[-1] if which == -1 else None
	about = words((wish_ or {}).get("about", ""))
	if about:
		scored = []
		for at, error in enumerate(pool):
			said = words(f"{error.message} {error.exception} {' '.join(f for _p, _l, f in error.trace)} {error.request}")
			shared = len(about & said)
			if shared:
				scored.append((-shared, at))
		if scored:
			return pool[min(scored)[1]]
	return pool[0]


def ago(when, now=None):
	"""When something happened, in words: "today at 12:02", "yesterday at 22:17", "on 18 November at 22:17"."""
	try:
		stamp = time.mktime(time.strptime(when, "%Y-%m-%d %H:%M:%S"))
	except (ValueError, OverflowError, TypeError):
		return str(when or "")
	now = now if now is not None else time.time()
	day = time.strftime("%Y-%m-%d", time.localtime(stamp))
	clock = time.strftime("%H:%M", time.localtime(stamp))
	if day == time.strftime("%Y-%m-%d", time.localtime(now)):
		return f"today at {clock}"
	if day == time.strftime("%Y-%m-%d", time.localtime(now - 86400)):
		return f"yesterday at {clock}"
	return f"on {time.strftime('%d %B', time.localtime(stamp)).lstrip('0')} at {clock}"


def fileWords(relative):
	"""A file of VisionClaw's code as the user hears it. A name with two underscores on each side is said in words: the
	clean-up of what is spoken takes underscores away, and "__init__.py" was heard as "init.py" (measured 2026-11-19)."""
	relative = str(relative or "")
	if relative == "__init__.py":
		return "VisionClaw's main file"
	if relative.endswith("/__init__.py"):
		return f"the main file of its folder {relative[:-len('/__init__.py')]}"
	return f"the file {relative}"


def errorText(error, root, now=None):
	"""One error in plain sentences: what, when and how often, where in VisionClaw's code, what NVDA's or Python's code
	was doing, and in which request."""
	said = [f"{error.message.rstrip('.')}."]
	times = "once" if error.count == 1 else f"{error.count} times, the first {ago(error.first, now)}"
	said.append(f"It happened {ago(error.when, now)}" + ("." if error.count == 1 else f", {times}."))
	frame = ownFrame(error, root)
	if frame:
		said.append(f"In VisionClaw's code: the function {frame[2]} in {fileWords(frame[0])}, line {frame[1]}.")
		others = otherCode(error, root)
		if others:
			said.append(f"From there it went into {', '.join(others)}, which is not VisionClaw's code.")
	elif error.trace:
		said.append("It happened inside NVDA's or Python's own code, not in VisionClaw's.")
	if error.exception:
		said.append(f"The error Python gave: {error.exception}")
	if error.request:
		said.append(f"It happened while VisionClaw worked on the request \"{error.request}\".")
	return " ".join(said)


def listText(found, root, trouble=(), now=None):
	"""The errors of the log, the newest first, for the user."""
	if not found and not trouble:
		return "VisionClaw's log has no errors."
	lines = []
	if found:
		lines.append(f"VisionClaw's log has {len(found)} different errors, the newest first." if len(found) > 1
			else "VisionClaw's log has one error.")
		for number, error in enumerate(found[:MAX_LISTED], 1):
			lines.append(f"{number}. {errorText(error, root, now)}")
		if len(found) > MAX_LISTED:
			lines.append(f"{len(found) - MAX_LISTED} older errors are in the log too; say which one by its number to hear it.")
	if trouble:
		lines.append("What the engines wrote about failures, the last first: " + " ".join(reversed(list(trouble))))
	return "\n".join(lines)


def storyText(story):
	"""The last request as the log tells it."""
	if story is None:
		return "VisionClaw's log has no request that ended."
	said = [f"Your last request, \"{story['request']}\", ended as {story['ended']} after {story['seconds']} seconds."]
	for tool, reason in story["problems"]:
		said.append(f"The tool {tool} could not do it: {reason}")
	for message in story["errors"]:
		said.append(f"An error happened: {message}")
	if not story["problems"] and not story["errors"]:
		said.append("No step of it failed and no error was written to the log.")
	return " ".join(said)


# --- VisionClaw's own code ---

def functionAt(source, line):
	"""The innermost function around a line of a file: {name, qualname, start (its def line), end, decorated (the first
	line of its decorators), indent, nested (inside another function), owner (its class or None), node}, or None."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return None
	best = None

	def visit(node, owners, inFunction):
		nonlocal best
		for child in ast.iter_child_nodes(node):
			if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
				if child.lineno <= line <= (child.end_lineno or child.lineno):
					first = min([child.lineno] + [d.lineno for d in child.decorator_list])
					best = {
						"name": child.name, "qualname": ".".join(owners + [child.name]), "start": child.lineno,
						"end": child.end_lineno or child.lineno, "decorated": first, "nested": inFunction,
						"owner": owners[-1] if owners else None, "node": child, "async": isinstance(child, ast.AsyncFunctionDef),
						"ownerDepth": len(owners)}
				visit(child, owners + [child.name], True)
			elif isinstance(child, ast.ClassDef):
				visit(child, owners + [child.name], inFunction)
			else:
				visit(child, owners, inFunction)

	visit(tree, [], False)
	if best is not None:
		lines = source.splitlines()
		best["indent"] = re.match(r"^\s*", lines[best["start"] - 1]).group(0)
		best["text"] = "\n".join(lines[best["start"] - 1:best["end"]])
	return best


def functionText(source, place):
	"""A function's own lines, without its decorators, from its def line to its last line."""
	return place["text"]


def digest(text):
	return hashlib.sha256(textwrap.dedent(str(text or "")).strip().encode("utf-8")).hexdigest()


def moduleName(relative):
	"""The module a file of VisionClaw is, as Python knows it: "claw/llm.py" is globalPlugins.visionClaw.claw.llm."""
	parts = [part for part in str(relative).replace("\\", "/").split("/") if part]
	if not parts or not parts[-1].endswith(".py"):
		return ""
	parts[-1] = parts[-1][:-3]
	if parts[-1] == "__init__":
		parts.pop()
	return ".".join([PACKAGE] + parts)


def refusal(relative, place):
	"""Why a function cannot be corrected while VisionClaw runs, in a sentence, or "" where it can."""
	if relative in NEVER:
		return ("It happened in the part of VisionClaw that installs it, carries its data or corrects its own code, "
			"which VisionClaw never changes itself.")
	if place is None:
		return "No function of VisionClaw's code could be found at that line."
	if place["nested"]:
		return (f"It happened in {place['name']}, a function made inside another one while VisionClaw starts, which "
			"VisionClaw cannot put a correction in place of while it runs.")
	if place["ownerDepth"] > 1:
		return f"It happened in {place['qualname']}, inside a class inside another, which VisionClaw cannot correct while it runs."
	if place["name"] in _ONCE:
		return f"It happened in {place['qualname']}, which runs only while VisionClaw starts or closes, so a correction would never be used."
	if place["async"]:
		return f"{place['qualname']} is written in a way VisionClaw cannot correct while it runs."
	return ""


# --- The model's diagnosis and correction ---

DIAGNOSE_TASK = (
	"You are VisionClaw, an assistant inside the NVDA screen reader. You read an error from VisionClaw's own log and the "
	"function of VisionClaw's own code where it happened, and tell the user in a few plain sentences what went wrong.\n"
	"Rules: Say what VisionClaw was doing, what went wrong and why, and whether it is harmless or stopped something the "
	"user wanted. Use only the error and the code given. Name the function. Do not write code. If the cause cannot be "
	"told from them, say so.")
FIX_TASK = (
	"You correct one function of VisionClaw, an add-on for the NVDA screen reader written in Python, so that the error "
	"from its log no longer happens.\n"
	"Rules: Write the whole corrected function, from its def line to its end, and nothing else. Keep its name and its "
	"arguments. Change as few lines as you can. Do not add imports. Indent with tabs, as the code is. Where the error "
	"comes from code that is not VisionClaw's, such as NVDA's own, catch that error where this function calls it, and "
	"end that piece of work quietly when nothing the user asked for depends on it.")
REVIEW_SCHEMA = {
	"type": "object",
	"properties": {"fixes": {"type": "boolean"}, "problem": {"type": "string", "maxLength": 240}},
	"required": ["fixes", "problem"],
}
REVIEW_SYSTEM = (
	IDENTITY + " You check a correction of one function of VisionClaw's own code. Say fixes=true if the corrected "
	"function stops the error given and changes nothing else the function did. Say fixes=false only for a clear problem, "
	"and name it in problem. Judge only from what is given.")


def facts(error, root, source, place):
	"""What the models are told of an error: the error, the trace through VisionClaw's code, and the function."""
	frame = ownFrame(error, root)
	lines = [f"Error in VisionClaw's log: {error.message}", f"Python's error: {error.exception or 'not written'}"]
	if error.request:
		lines.append(f"It happened while VisionClaw worked on the request: \"{uncut(error.request)}\"")
	if error.count > 1:
		lines.append(f"It happened {error.count} times.")
	if error.trace:
		lines.append("Where it went, the last place last: " + "; ".join(
			f"{own(path, root) or os.path.basename(str(path).replace(chr(92), '/'))} line {line} in {function}"
			for path, line, function in error.trace[-6:]))
	if frame and place:
		failing = source.splitlines()[frame[1] - 1].strip() if 0 < frame[1] <= len(source.splitlines()) else ""
		# Shown from the left edge, as the model is to write it back.
		lines.append(f"The function {place['qualname']} of {frame[0]}:\n```python\n{clip(textwrap.dedent(place['text']), 3000)}\n```")
		if failing:
			lines.append(f"The error happened on this line of it: {failing}")
	return "\n".join(lines)


def extractFunction(answer):
	"""The function from a model's answer: the longest Python block, else the answer from its first def line."""
	blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", answer or "", re.DOTALL)
	# Without fences the answer keeps the indentation of its first line, so that the function can be dedented whole.
	text = max(blocks, key=len) if blocks else re.sub(r"^\s*```(?:python|py)?[ \t]*\n", "", str(answer or "")).rstrip()
	lines = text.splitlines()
	start = next((at for at, line in enumerate(lines) if re.match(r"^\s*(async\s+)?def\s", line)), None)
	if start is None:
		return ""
	# Decorators written just above the def line are the function's own; they are kept from the code as it was.
	return textwrap.dedent("\n".join(lines[start:])).rstrip() + "\n"


def tidy(newText, place):
	"""A correction as the file writes its code: where the function is indented with tabs and the model indented with
	spaces, every run of the model's own step of spaces at the start of a line becomes a tab. Measured with Qwen3.5 4B on
	2026-11-19: it indented with four spaces, and every line of its correction differed from the function's."""
	text = str(newText or "")
	if not place or "\t" not in place["text"][:200] or not re.search(r"^ +\S", text, re.M):
		return text
	steps = [len(found) for found in re.findall(r"^( +)\S", text, re.M)]
	unit = min(steps) if steps else 4
	unit = unit if unit in (2, 3, 4, 8) else 4

	def tabbed(found):
		spaces = len(found.group(1))
		return "\t" * (spaces // unit) + " " * (spaces % unit)

	return re.sub(r"^( +)", tabbed, text, flags=re.M)


def bodyAligned(newText):
	"""A function whose def line is at the left edge and whose body is indented deeper than one step, as when a model
	copies a method's body as it stood in its class: the body is put one step in. Measured with Qwen3.5 4B on 2026-11-19."""
	lines = str(newText or "").rstrip().splitlines()
	if len(lines) < 2 or lines[0][:1].isspace():
		return newText
	body = textwrap.dedent("\n".join(lines[1:]))
	unit = "\t" if "\t" in newText else "    "
	return "\n".join([lines[0]] + [unit + line if line.strip() else "" for line in body.splitlines()]) + "\n"


def _names(node):
	found = set()
	for child in ast.walk(node):
		if isinstance(child, ast.Name):
			found.add(child.id)
		elif isinstance(child, ast.Attribute):
			found.add(child.attr)
		elif isinstance(child, ast.alias):
			found.add(child.name.split(".")[0])
	return found


def _superFixed(text, owner):
	"""super() without arguments needs the class it is written in; a function put in place later has none, so plain code
	writes super(TheClass, self)."""
	if not owner:
		return text
	return re.sub(r"\bsuper\(\s*\)", f"super({owner}, self)", text)


def checkFix(source, place, newText, complaint=False):
	"""Problems with a correction, as sentences the model can act on; empty when it may be offered. newText: the
	function as the model wrote it, its def line first. complaint: it corrects what the user said was wrong, not an
	error of the log."""
	problems = []
	try:
		tree = ast.parse(newText)
	except SyntaxError as e:
		return [f"Syntax error on line {e.lineno} of the function: {e.msg}."]
	defs = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
	if len(tree.body) != 1 or len(defs) != 1:
		return ["Write only the one function, from its def line to its end, and nothing else."]
	new = defs[0]
	old = place["node"]
	if new.name != old.name:
		problems.append(f"The function must keep its name, {old.name}.")
	if ast.dump(new.args) != ast.dump(old.args):
		problems.append(f"The function must keep its arguments as they were: {ast.unparse(old.args)}.")
	if new.decorator_list:
		problems.append("Leave out the lines above the def line; the function keeps its own.")
	if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(new)) and not any(
			isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(old)):
		problems.append("Do not add imports.")
	added = (_names(new) - _names(old)) & FORBIDDEN
	if added:
		problems.append(f"Do not add {', '.join(sorted(added))}: a correction may not reach the internet, start programs, "
			"delete files or run text as code.")
	if any(isinstance(node, ast.Attribute) and node.attr.startswith("__") and not node.attr.endswith("__")
			for node in ast.walk(new)) and place["owner"]:
		problems.append("Do not use names that begin with two underscores.")
	oldLines = [line.rstrip() for line in textwrap.dedent(place["text"]).strip().splitlines()]
	newLines = [line.rstrip() for line in newText.strip().splitlines()]
	changed = sum(1 for line in difflib.ndiff(oldLines, newLines) if line[:1] in "+-")
	if changed == 0 and complaint:
		problems.append("That is the function as it was, and it would do the same again. Change what it does, so that it "
			"does what the user expected.")
	elif changed == 0:
		problems.append("That is the function as it was, and the error would happen again. Change the line where it "
			"happens, or catch the error there.")
	elif changed > MAX_CHANGED * 2:
		problems.append(f"That changes too much. Change only the lines needed for this error, at most {MAX_CHANGED}.")
	if not problems:
		whole = replaced(source, place, newText)
		try:
			compile(whole, "fixed.py", "exec")
		except SyntaxError as e:
			problems.append(f"With it the file does not compile: {e.msg}, line {e.lineno}.")
	return problems


def replaced(source, place, newText):
	"""The file with the function's own lines, from its def line to its end, put in place of the old ones."""
	lines = source.splitlines()
	indented = "\n".join(place["indent"] + line if line.strip() else "" for line in newText.rstrip().splitlines())
	return "\n".join(lines[:place["start"] - 1] + [indented] + lines[place["end"]:]) + "\n"


def changeText(oldText, newText):
	"""What a correction changes, in plain words taken from the code: how many lines, which errors it now catches and
	what it then does, which functions it calls now or no longer calls, and whether it stops early in a new case."""
	oldLines = textwrap.dedent(oldText).strip().splitlines()
	newLines = textwrap.dedent(newText).strip().splitlines()
	diff = list(difflib.ndiff(oldLines, newLines))
	plus = sum(1 for line in diff if line.startswith("+ "))
	minus = sum(1 for line in diff if line.startswith("- "))
	said = [f"It adds {plus} lines and takes out {minus}." if minus else f"It adds {plus} lines and takes none out."]
	try:
		old, new = ast.parse(textwrap.dedent(oldText)), ast.parse(textwrap.dedent(newText))
	except SyntaxError:
		return " ".join(said)

	def caught(tree):
		found = set()
		for node in ast.walk(tree):
			if isinstance(node, ast.ExceptHandler):
				names = ([node.type] if node.type is not None and not isinstance(node.type, ast.Tuple)
					else list(getattr(node.type, "elts", [])))
				what = ", ".join(ast.unparse(n) for n in names) if names else "any error"
				# Only a return or a break stops; a pass or a continue catches the error and goes on.
				quiet = all(isinstance(s, (ast.Return, ast.Break)) for s in node.body)
				found.add((what, quiet))
		return found

	for what, quiet in sorted(caught(new) - caught(old)):
		said.append(f"When the error {what} happens there, it now " + ("stops that piece of work quietly." if quiet
			else "catches it and goes on."))

	def calls(tree):
		return {getattr(n.func, "attr", getattr(n.func, "id", "")) for n in ast.walk(tree) if isinstance(n, ast.Call)} - {""}

	more, fewer = calls(new) - calls(old), calls(old) - calls(new)
	if more:
		said.append(f"It now also calls {', '.join(sorted(more))}.")
	if fewer:
		said.append(f"It no longer calls {', '.join(sorted(fewer))}.")
	returns = sum(isinstance(n, ast.Return) for n in ast.walk(new)) - sum(isinstance(n, ast.Return) for n in ast.walk(old))
	checks = sum(isinstance(n, ast.If) for n in ast.walk(new)) - sum(isinstance(n, ast.If) for n in ast.walk(old))
	if checks > 0:
		said.append(f"It checks {checks} more {'thing' if checks == 1 else 'things'} before it goes on.")
	if returns > 0 and not any(quiet for _w, quiet in caught(new) - caught(old)):
		said.append("It can now stop early.")
	return " ".join(said)


# --- Corrections kept as data, and put in place ---

class Fix:
	"""A correction the user said yes to: which function of which file, for which version of VisionClaw, the function
	as it was (its digest, to know the code is still the same) and as it is now. complaint: what the user said was
	wrong, for a correction made from a complaint and not from an error of the log."""

	FIELDS = ("id", "file", "qualname", "version", "oldDigest", "old", "new", "error", "made", "state", "why", "complaint")

	def __init__(self, **values):
		for name in self.FIELDS:
			setattr(self, name, values.get(name, ""))
		self.state = self.state or "on"

	def asDict(self):
		return {name: getattr(self, name) for name in self.FIELDS}


class Fixes:
	"""The corrections of VisionClaw's own code, in the folder "ownfixes" of VisionClaw's data, and the functions they
	replace while NVDA runs. root: the folder globalPlugins/visionClaw of the running add-on; version: its version."""

	def __init__(self, folder, root, version, clock=time.time, modules=None, load=None):
		self.folder = folder
		self.root = root
		self.version = version
		self._clock = clock
		self._lock = threading.RLock()
		self._modules = modules if modules is not None else sys.modules
		# How a part of VisionClaw that is not loaded yet is loaded: it is VisionClaw's own code.
		self._load = load if load is not None else importlib.import_module
		# What each correction put aside while it is in place: id -> (owner, name, original, wrapper).
		self._placed = {}

	def _path(self):
		return os.path.join(self.folder, FIXES_FILE)

	def all(self):
		try:
			with open(self._path(), encoding="utf-8") as f:
				data = json.load(f)
			return [Fix(**entry) for entry in data if isinstance(entry, dict)]
		except (OSError, ValueError):
			return []

	def _save(self, fixes):
		try:
			os.makedirs(self.folder, exist_ok=True)
			temporary = self._path() + ".new"
			with open(temporary, "w", encoding="utf-8", newline="\n") as f:
				json.dump([fix.asDict() for fix in fixes], f, indent=1)
			os.replace(temporary, self._path())
		except OSError as e:
			debuglog.error("ownfix", "The list of corrections could not be written", e)

	def _set(self, ident, **values):
		with self._lock:
			fixes = self.all()
			for fix in fixes:
				if fix.id == ident:
					for name, value in values.items():
						setattr(fix, name, value)
			self._save(fixes)

	def source(self, relative):
		return _readFile(os.path.join(self.root, *relative.split("/")))

	def add(self, fix, report):
		"""Keep a correction and its report, and put it in place. Returns (worked, sentence)."""
		with self._lock:
			fixes = [old for old in self.all() if not (old.file == fix.file and old.qualname == fix.qualname)]
			for old in self.all():
				if old.file == fix.file and old.qualname == fix.qualname:
					self.takeAway(old.id)
			fixes.append(fix)
			self._save(fixes)
			try:
				with open(os.path.join(self.folder, f"{fix.id}.md"), "w", encoding="utf-8", newline="\n") as f:
					f.write(report)
			except OSError as e:
				debuglog.error("ownfix", "The report of the correction could not be written", e)
		return self.apply(fix)

	def _owner(self, fix):
		name = moduleName(fix.file)
		module = self._modules.get(name)
		if module is None:
			try:
				module = self._load(name)
			except Exception as e:
				debuglog.error("ownfix", f"{name} could not be loaded for a correction", e)
				return None, None
		owner = module
		parts = fix.qualname.split(".")
		for part in parts[:-1]:
			owner = getattr(owner, part, None)
			if owner is None:
				return None, None
		return module, owner

	def apply(self, fix, onFail=None):
		"""Put a correction in place of its function while NVDA runs. Returns (worked, sentence). Only for the version it
		was made for, and only while the function is still as it was."""
		if fix.version and self.version and fix.version != self.version:
			return False, f"It was made for VisionClaw {fix.version}, and this is {self.version}."
		place = None
		source = self.source(fix.file)
		for node in ast.walk(ast.parse(source)) if source else ():
			if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fix.qualname.split(".")[-1]:
				candidate = functionAt(source, node.lineno)
				if candidate is not None and candidate["qualname"] == fix.qualname:
					place = candidate
					break
		if place is None or digest(place["text"]) != fix.oldDigest:
			return False, "VisionClaw's code of that function is no longer what the correction was made for."
		module, owner = self._owner(fix)
		if owner is None:
			return False, f"The part of VisionClaw that has {fix.qualname} is not loaded."
		name = fix.qualname.split(".")[-1]
		original = (owner.__dict__ if hasattr(owner, "__dict__") else {}).get(name)
		if original is None or isinstance(original, (staticmethod, classmethod, property)) or not callable(original):
			return False, f"{fix.qualname} is not a plain function, which VisionClaw cannot put a correction in place of."
		original = getattr(original, "__wrapped__", None) if getattr(original, "__visionclawFix__", None) else original
		namespace = {}
		try:
			code = compile(_superFixed(fix.new, place["owner"]), f"<VisionClaw's correction of {fix.qualname}>", "exec")
			exec(code, module.__dict__, namespace)
		except Exception as e:
			return False, f"The correction could not be made ready: {type(e).__name__}: {e}"
		fixed = namespace.get(name)
		if not callable(fixed):
			return False, "The correction has no function of that name."
		wrapper = guarded(fix, original, fixed, onFail or self._failed)
		with self._lock:
			setattr(owner, name, wrapper)
			# A function others took in by its name ("from .llm import clip") is given to them too.
			if owner is module:
				for other in list(self._modules.values()):
					spaced = getattr(other, "__dict__", None)
					if spaced is not None and other is not module and str(getattr(other, "__name__", "")).startswith(
							PACKAGE) and spaced.get(name) is original:
						spaced[name] = wrapper
			self._placed[fix.id] = (owner, name, original, wrapper)
		debuglog.log("ownfix", f"The correction {fix.id} of {fix.file} {fix.qualname} is in place.")
		return True, ""

	def _failed(self, fix, error):
		debuglog.error("ownfix", f"The correction {fix.id} of {fix.qualname} failed itself, so it is turned off", error)
		self._set(fix.id, state="failed", why=f"{type(error).__name__}: {error}")

	def takeAway(self, ident):
		"""The function as it was put back, while NVDA runs. Returns whether a correction was in place."""
		with self._lock:
			placed = self._placed.pop(ident, None)
			if placed is None:
				return False
			owner, name, original, wrapper = placed
			if getattr(owner, name, None) is wrapper:
				setattr(owner, name, original)
			for other in list(self._modules.values()):
				spaced = getattr(other, "__dict__", None)
				if spaced is not None and spaced.get(name) is wrapper:
					spaced[name] = original
			return True

	def remove(self, ident):
		"""A correction undone: the function as it was is used again, and the correction is kept as undone, with its
		report. Returns the Fix, or None."""
		with self._lock:
			fixes = self.all()
			found = next((fix for fix in fixes if fix.id == ident), None)
			if found is None:
				return None
			self.takeAway(ident)
			found.state = "undone"
			self._save(fixes)
			return found

	def startUp(self):
		"""Put in place every correction the user said yes to, where it still fits; one that does not is put aside and
		written to the log. Run once when VisionClaw starts. Returns (placed, put aside)."""
		placed, aside = 0, 0
		for fix in self.all():
			if fix.state != "on":
				continue
			try:
				worked, why = self.apply(fix)
			except Exception as e:
				worked, why = False, f"{type(e).__name__}: {e}"
			if worked:
				placed += 1
			else:
				aside += 1
				self._set(fix.id, state="aside", why=why)
				debuglog.log("ownfix", f"The correction {fix.id} of {fix.qualname} was put aside: {why}")
		return placed, aside

	def text(self):
		"""The corrections, in sentences."""
		fixes = self.all()
		if not fixes:
			return "VisionClaw has made no corrections of its own code."
		said = {"on": "in use", "failed": "turned off, because it failed itself", "aside": "put aside",
			"undone": "undone"}
		lines = [f"{len(fixes)} corrections of VisionClaw's own code:"]
		for number, fix in enumerate(fixes, 1):
			what = (f"for what you said was wrong: {fix.complaint.rstrip('.')}" if fix.complaint
				else f"for the error: {fix.error}")
			lines.append(f"{number}. {fix.qualname} in {fileWords(fix.file)}, made {ago(fix.made)} for VisionClaw {fix.version}, {what}. "
				f"It is {said.get(fix.state, fix.state)}" + (f": {fix.why}" if fix.why and fix.state != "on" else "") + ".")
		return "\n".join(lines)

	def note(self, name, text):
		"""A report of what VisionClaw could not correct, written as a Markdown file in the folder; its file name, or ""
		where it could not be written."""
		file = re.sub(r"[^\w.-]+", "-", str(name)).strip("-") + ".md"
		try:
			os.makedirs(self.folder, exist_ok=True)
			with open(os.path.join(self.folder, file), "w", encoding="utf-8", newline="\n") as f:
				f.write(text)
		except OSError as e:
			debuglog.error("ownfix", "A report for VisionClaw's developer could not be written", e)
			return ""
		return file


def guarded(fix, original, fixed, onFail):
	"""What is put in place of a function: the correction, and where the correction itself fails in a way the function's
	work does not explain, the correction is turned off and the old function used from then on. The error is still
	passed on, as the old function's would have been, so that nothing runs twice."""
	state = {"failed": False}

	@functools.wraps(original)
	def run(*args, **kwargs):
		if state["failed"]:
			return original(*args, **kwargs)
		try:
			return fixed(*args, **kwargs)
		except (KeyboardInterrupt, SystemExit):
			raise
		except BaseException as e:
			if type(e).__name__ not in PASSED_ON:
				state["failed"] = True
				try:
					onFail(fix, e)
				except Exception:
					pass
			raise

	run.__visionclawFix__ = fix.id
	run.__wrapped__ = original
	return run


def report(fix, facts_, diagnosis, change, review):
	"""The correction as a Markdown file, for the user to keep or to give to VisionClaw's developer."""
	complained = bool(getattr(fix, "complaint", ""))
	return "\n".join([
		f"# VisionClaw's correction of {fix.qualname}", "",
		f"Made {time.strftime('%Y-%m-%d %H:%M', time.localtime(time.time()))} for VisionClaw {fix.version}, after you asked for it.",
		"VisionClaw's own files were not changed: the correction is put in place of the function while NVDA runs, and again "
		"when VisionClaw starts, for this version only. To undo it, say undo that, or remove the correction of your code.", "",
		"## What you said was wrong" if complained else "## The error", "", fix.complaint if complained else fix.error, "",
		"## How this function was chosen" if complained else "## What the model said went wrong", "", diagnosis or "Not asked.", "",
		"## What the correction changes", "", change, "", "## What the other model said", "", review or "Not asked.", "",
		"## What the models were given", "", facts_, "",
		"## The function as it was", "", "```python", textwrap.dedent(fix.old).rstrip(), "```", "",
		"## The function as it is now", "", "```python", fix.new.rstrip(), "```", ""])


# --- A complaint about what VisionClaw just did, with no error in its log ---
# The owner said on 2026-11-19, testing 1.18.0: after "check NVDA's log" with NVDA's logging off he said yes to having
# NVDA's settings opened at the Logging level combo box, the focus landed on "Make screen black (immediate effect)"
# instead, and nothing was written to the log. Then: "visionclaw must be able to fix such focus and other bugs by itself
# using its AI models and skills, when I complain about a problem like this. Add a feature so visionclaw can fix itself."
#   - Plain code reads the complaint (complaintOf): the user says that what VisionClaw, "you" or "it" just did was wrong,
#     with words such as "instead of", "should have", "didn't work", "the focus went to". Kept narrow: a request to do
#     something ("move the focus to the OK button", "the focus is on the wrong control, press Tab"), a question other than
#     why, a correction ("no, I meant ..."), and something the user's own key press did are no complaint.
#   - Plain code finds what it is about (complaintTarget): the newest request before it that was not itself about
#     VisionClaw's own code, from what the orchestrator keeps in memory (record) or from VisionClaw's log (requests).
#   - Plain code finds the code (usedFunctions): each tool's function, and the functions of VisionClaw's own code it uses,
#     read from its code and resolved through the running objects without running anything: its closure, its module, the
#     imports inside it, what it assigns from those, and "self". A function made inside the tool (most tools are made
#     inside register) does not count as a level; what it uses does. DEPTH levels deep, at most MAX_FUNCTIONS.
#   - Plain code ranks them (fitting): the complaint's telling words against each function's name and first line of
#     help, its code and the lines where it is used, rare words counting most (claw/ranking.py); at most MAX_OFFERED, and
#     none that cannot be corrected (refusal). The model that writes code chooses one by its number (CHOOSE_SYSTEM); only
#     a model that is not one of the very smallest may say none of them.
#   - The model is told what the running NVDA has for the names the function uses (namesFacts): for each class of NVDA it
#     uses, what its own code sets on each object and its methods, read from the loaded modules' bytecode; nothing is
#     imported or called.
#   - The correction is written, checked, read by the other model and asked about as for an error. When VisionClaw
#     cannot, it says why, names the function it would need, and writes a report for its developer (complaintReport).

# How many requests the orchestrator keeps in memory for a complaint about one of them, and how long after a request a
# complaint may be about it, in seconds.
RECENT = 4
COMPLAINT_SECONDS = 1800
# How deep the functions a tool uses are followed, how many are looked at, how many the model chooses among, and how
# close to the best a function must be to be offered.
DEPTH = 2
MAX_FUNCTIONS = 120
MAX_OFFERED = 4
OFFER_SHARE = 0.5
# How many lines before and after the place where a function is used are read with it.
AROUND = 5
# The jobs that are about VisionClaw's own code: a complaint is never about one of them.
DIAGNOSE_TOOLS = frozenset(("own_errors", "fix_self", "own_fixes"))

_NOT_DONE = (r"(?:didn'?t|doesn'?t|don'?t|isn'?t|wasn'?t|won'?t|can'?t|cannot|couldn'?t|wouldn'?t|hasn'?t|haven'?t|never|"
	r"did not|does not|do not|is not|was not|will not|can not|could not|would not|has not|have not)")
# Words that say something went wrong. "Wrong" in "what went wrong" and "what's wrong" asks, and says nothing.
_COMPLAINS = re.compile(
	r"\binstead of\b|(?<!went )(?<!what's )(?<!what is )(?<!whats )\bwrong\b|\bnot what i (?:asked|wanted|meant|said)\b"
	r"|\bshould(?:n't| not)?\s+(?:have|'ve)\s+(?!a\b|an\b|the\b|my\b|your\b|to\b|any\b|some\b|this\b|that\b|it\b)\w+"
	r"|\b(?:was|were|is|are|you're)\s+(?:supposed|meant)\s+to\b"
	rf"|\b{_NOT_DONE}\s+(?:work|happen|do (?:it|that|anything|what)|go|open|close|move|land|read|say|speak|stop|find|press|"
	r"click|focus|get|show|put|start|change|turn|save|select|choose|type|switch|let)\w*\b"
	r"|\bnot (?:working|work)\b|\bfailed to\b|\bbroke\b|\bmessed (?:it |that |this )?up\b"
	r"|\byou\s+(?:said|told me|wrote|read out|typed|reported|announced)\b[^;!?]{0,120}?\bbut\b"
	r"|\b(?:there'?s|there is|that'?s|that is|it'?s|it is|this is|found)\s+a\s+bug\b|\b(?:is|are|you're|it's|that's)\s+(?:buggy|broken)\b"
	r"|\bfocus\s+(?:went|goes|go|landed|lands|ended up|ends up|was put|got put|jumped|jumps|moved|moves|stayed|stays|"
	r"is stuck|was stuck|is now|is on|was on|got)\b", re.IGNORECASE)
# Words that say it is what VisionClaw did: you, VisionClaw, "it" or "that" doing something at the start, the focus.
_BY_YOU = re.compile(
	r"\b(?:you|you've|you're|you'd|your|yourself|visionclaw'?s?|vision claw'?s?)\b"
	r"|^\W*(?:(?:no|hey|ok|okay|well|so|um|uh|oh|hmm|sorry|but|and)\b[,.!\s]*)*(?:it|that|this)(?:'s|\s+(?:is|was|did|does|"
	r"didn'?t|doesn'?t|isn'?t|wasn'?t|went|opened|put|moved|clicked|pressed|said|read|took|landed|only|just|still|never|"
	r"keeps|kept|ended|failed|gave|selected|chose|typed|set|turned|changed|made|should|has|had|broke))\b"
	r"|\b(?:the|my|nvda'?s|its)\s+focus\b", re.IGNORECASE)
# A question; one that asks why is answered as one (WHY), and "can you fix it" asks for a correction.
_ASKS = re.compile(
	r"^\W*(?:(?:hey|ok|okay|so|well|and|but)[,\s]+)*(?:what|which|who|where|when|how(?!\s+come)|can|could|would|will|do|"
	r"does|did|is|are|was|were|should|shall|may|have|has|am)\b", re.IGNORECASE)
_ASKS_WHY = re.compile(r"\bwhy\b|\bhow come\b|\bwhat went wrong\b|\bwhat happened\b", re.IGNORECASE)
_POLITE_START = (r"(?:(?:please|now|ok|okay|so|just|and|then|can you|could you|would you|will you|you need to|you must|"
	r"i want you to|go ahead and)\s+)*")
_FIXING = re.compile(
	rf"^\W*{_POLITE_START}(?:fix|repair|correct|patch|debug|mend|heal|sort (?:it|that|this) out|sort out|look into|"
	r"find out|figure out|make (?:it|that|this) (?:work|right)|work out|investigate|diagnose|tell me why|explain why|"
	r"learn from)\b", re.IGNORECASE)
# A clause that asks for something else to be done: then the words are a request, not a complaint.
_ACTION = re.compile(
	rf"^\W*{_POLITE_START}(?:open|close|click|press|type|turn|set|go|switch|start|find|read|tell|show|move|put|take|"
	r"select|choose|focus|try|do|make|undo|change|say|speak|stop|run|launch|search|scroll|drag|check|describe|list|look|"
	r"give|bring|use|mute|unmute|play|pause|save|copy|paste|delete|remove|empty|lock|minimi[sz]e|maximi[sz]e|restore|"
	r"enable|disable|navigate|jump|activate|write|repeat|retry|redo|help|lower|raise|increase|decrease|speed|slow|skip|"
	r"cancel|let)\b", re.IGNORECASE)
_CLAUSES = re.compile(r"[,;:.!?]+|\s+(?:and then|then|and|but|so)\s+", re.IGNORECASE)
# What the user's own key press did is no doing of VisionClaw's.
_OWN_PRESS = re.compile(r"\bwhen i (?:press|pressed|hit|tab|tabbed|type|typed|arrow|arrowed|use|used)\b", re.IGNORECASE)
# An add-on, an app helper or a hotkey VisionClaw made is corrected by its own job (fix_addon), not as VisionClaw's code.
_MADE_THINGS = re.compile(r"\badd-?ons?\b|\bhelpers?\b|\bhot ?keys?\b|\bscripts?\b|\bkeyboard shortcuts? you\b", re.IGNORECASE)
# Words of a complaint that say only that something went wrong, not what: they find no code.
_NOT_TELLING = words(
	"instead wrong should supposed meant work worked working works didn't doesn't bug bugs buggy broken broke fix fixed "
	"visionclaw vision claw went goes gone landed lands ended ends never again yourself own code said told kept keeps time "
	"happened happen failed fail messed please thank thanks")


def complaintOf(text):
	"""The user's words, where they say that what VisionClaw, "you" or "it" just did was wrong; else None. A why-question
	is a complaint too (wish makes it WHY). Kept narrow: the words must say that something went wrong (_COMPLAINS) and
	that VisionClaw did it (_BY_YOU), and must not ask for anything else to be done, ask another question, correct the
	request before ("no, I meant ..."), or speak of what the user's own key press did."""
	said = " ".join(str(text or "").replace("’", "'").split())
	low = said.lower()
	if not said or not _COMPLAINS.search(low) or not _BY_YOU.search(low) or _OWN_PRESS.search(low) or _MADE_THINGS.search(low):
		return None
	if _ASKS.match(low) and not _ASKS_WHY.search(low) and not re.match(
			r"^\W*(?:can|could|would|will)\s+you\s+(?:please\s+)?(?:fix|repair|correct|look into|find out)\b", low):
		return None
	for clause in _CLAUSES.split(low):
		clause = clause.strip()
		if clause and _ACTION.match(clause) and not _FIXING.match(clause) and not re.match(
				r"^\W*(?:tell|explain)\s+(?:me\s+)?(?:why|how come|what went wrong|what happened)\b", clause):
			return None
	if corrections.correctionOf(said):
		return None
	return said


def record(task, when):
	"""What a request did, as the orchestrator keeps it in memory for a complaint about it: never written anywhere.
	when: the time it ended on the orchestrator's clock."""
	steps = []
	for step in list(getattr(task, "steps", None) or []):
		steps.append({"tool": str(getattr(step, "tool", "") or ""), "title": str(getattr(step, "title", "") or ""),
			"status": str(getattr(step, "status", "") or ""), "result": str(getattr(step, "result", "") or "")})
	request = " ".join(str(getattr(task, "request", "") or "").split())
	return {"request": request, "said": " ".join(str(getattr(task, "original", "") or request).split()),
		"answer": " ".join(str(getattr(task, "plainAnswer", "") or getattr(task, "answer", "") or "").split()),
		"state": str(getattr(task, "state", "") or ""), "when": when, "steps": steps, "asked": []}


def _diagnosing(item):
	"""Whether a request was itself about VisionClaw's own log or code."""
	if any(step.get("tool") in DIAGNOSE_TOOLS for step in item.get("steps") or ()):
		return True
	return wish(item.get("said") or item.get("request") or "") is not None


def complaintTarget(items, complaint=""):
	"""(the complaint, the request it is about) from the last requests, the newest first, or ("", None) where there is
	no complaint. Where the words of this request have none, "fix that bug" right after a complaint VisionClaw was asked
	why about carries that complaint. The request is the newest that was not itself about VisionClaw's own code, or None."""
	items = list(items or [])
	if not complaint and items and _diagnosing(items[0]):
		complaint = (wish(items[0].get("said") or items[0].get("request") or "") or {}).get("complaint") or ""
	if not complaint:
		return "", None
	for item in items:
		if not _diagnosing(item):
			return complaint, item
	return complaint, None


def doneText(item, limit=600):
	"""What a request did, for a model: the request, each step with its result, what the user was asked, the answer."""
	said = [f"The request \"{uncut(item.get('said') or item.get('request'))}\"."]
	for step in item.get("steps") or ():
		title = f" ({step['title']})" if step.get("title") else ""
		result = f": {clip(' '.join(str(step.get('result') or '').split()), limit)}" if step.get("result") else ""
		said.append(f"The step {step.get('tool')}{title} ended as {step.get('status') or 'unknown'}{result}")
	for question, chosen in item.get("asked") or ():
		said.append(f"VisionClaw asked the user: \"{uncut(question)}\"" + (f" The user chose: {chosen}." if chosen else ""))
	results = {" ".join(str(step.get("result") or "").split()) for step in item.get("steps") or ()}
	if item.get("answer") and " ".join(str(item["answer"]).split()) not in results:
		said.append(f"VisionClaw answered: \"{clip(item['answer'], limit)}\"")
	return " ".join(said)


def aboutText(complaint, item):
	"""What the user is told the complaint is about, whole."""
	when = f", {ago(item['when'])}" if isinstance(item.get("when"), str) else ""
	return f"You said: \"{uncut(complaint)}\" That is about your request \"{uncut(item.get('said') or item.get('request'))}\"{when}."


# --- The functions a tool uses, found without running anything ---

_MISSING = object()


def allPlaces(source):
	"""Every function of a file, as functionAt gives one, from one reading of the file."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return []
	lines = source.splitlines()
	found = []

	def visit(node, owners, inFunction):
		for child in ast.iter_child_nodes(node):
			if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
				first = min([child.lineno] + [d.lineno for d in child.decorator_list])
				end = child.end_lineno or child.lineno
				found.append({
					"name": child.name, "qualname": ".".join(owners + [child.name]), "start": child.lineno, "end": end,
					"decorated": first, "nested": inFunction, "owner": owners[-1] if owners else None, "node": child,
					"async": isinstance(child, ast.AsyncFunctionDef), "ownerDepth": len(owners),
					"indent": re.match(r"^\s*", lines[child.lineno - 1]).group(0), "text": "\n".join(lines[child.lineno - 1:end])})
				visit(child, owners + [child.name], True)
			elif isinstance(child, ast.ClassDef):
				visit(child, owners + [child.name], inFunction)
			else:
				visit(child, owners, inFunction)

	visit(tree, [], False)
	return found


def _plainFunction(thing):
	"""The Python function behind something that can be called: a method's, a decorated one's, a correction's own
	original; None for anything else."""
	try:
		if isinstance(thing, (staticmethod, classmethod)):
			thing = thing.__func__
		if inspect.ismethod(thing):
			thing = thing.__func__
		thing = inspect.unwrap(thing)
	except Exception:
		return None
	return thing if isinstance(thing, types.FunctionType) else None


def _static(value, name):
	"""What something has under a name, read without running anything: never a property, never __getattr__."""
	try:
		found = inspect.getattr_static(value, name)
	except Exception:
		return _MISSING
	if isinstance(found, (staticmethod, classmethod)):
		return found.__func__
	if isinstance(found, property) or type(found).__name__ in ("getset_descriptor", "member_descriptor"):
		return _MISSING
	return found


def _importsIn(node, package, modules):
	"""What the imports inside a function bring in, from the modules that are loaded already: name -> what. Nothing is
	imported."""
	found = {}
	for sub in ast.walk(node):
		if isinstance(sub, ast.Import):
			for alias in sub.names:
				name = alias.asname or alias.name.split(".")[0]
				value = modules.get(alias.name if alias.asname else alias.name.split(".")[0])
				if value is not None:
					found[name] = value
		elif isinstance(sub, ast.ImportFrom):
			base = sub.module or ""
			if sub.level:
				parts = [part for part in str(package or "").split(".") if part]
				parts = parts[:len(parts) - (sub.level - 1)] if sub.level > 1 else parts
				base = ".".join(parts + ([sub.module] if sub.module else []))
			module = modules.get(base)
			for alias in sub.names:
				value = _static(module, alias.name) if module is not None else _MISSING
				if value is _MISSING:
					value = modules.get(f"{base}.{alias.name}", _MISSING)
				if value is not _MISSING:
					found[alias.asname or alias.name] = value
	return found


def _assignedIn(node):
	"""The plain names a function gives something it reads from a name: "pads = plugin.pads". name -> the expression."""
	found = {}
	for sub in ast.walk(node):
		if isinstance(sub, ast.Assign) and len(sub.targets) == 1 and isinstance(sub.targets[0], ast.Name) and isinstance(
				sub.value, (ast.Name, ast.Attribute)):
			found[sub.targets[0].id] = sub.value
	return found


def _usesIn(function, selfObject, place, modules):
	"""What a function uses of other functions: (the function, what it was found on, first line, last line) for each,
	once, read from its code and resolved through the running objects without running anything."""
	code = function.__code__
	closure = {}
	for name, cell in zip(code.co_freevars, function.__closure__ or ()):
		try:
			closure[name] = cell.cell_contents
		except ValueError:
			pass
	space = function.__globals__
	imported = _importsIn(place["node"], space.get("__package__") or "", modules)
	assigned = _assignedIn(place["node"])

	def named(name, depth):
		if name in imported:
			return imported[name]
		if name == "self" and selfObject is not None:
			return selfObject
		if name in closure:
			return closure[name]
		if name in assigned and depth < 3:
			found = resolved(assigned[name], depth + 1)
			return found[0] if found else _MISSING
		return space.get(name, _MISSING)

	def resolved(expr, depth=0):
		attrs = []
		while isinstance(expr, ast.Attribute):
			attrs.append(expr.attr)
			expr = expr.value
		if not isinstance(expr, ast.Name):
			return None
		value, holder = named(expr.id, depth), None
		if value is _MISSING:
			return None
		for attr in reversed(attrs):
			holder, value = value, _static(value, attr)
			if value is _MISSING:
				return None
		return value, holder

	seen = set()
	for sub in ast.walk(place["node"]):
		if not isinstance(sub, (ast.Name, ast.Attribute)) or not isinstance(sub.ctx, ast.Load):
			continue
		found = resolved(sub)
		if found is None:
			continue
		value, holder = found
		plain = _plainFunction(value)
		if plain is None or plain is function or id(plain) in seen:
			continue
		seen.add(id(plain))
		owner = holder if holder is not None and not isinstance(holder, types.ModuleType) else None
		yield value, owner, sub.lineno, getattr(sub, "end_lineno", None) or sub.lineno


def _around(lines, place, first, last):
	start = max(place["start"], first - AROUND)
	end = min(place["end"], last + AROUND)
	return textwrap.dedent("\n".join(lines[start - 1:end]))


def usedFunctions(start, read, root, modules=None, depth=DEPTH, limit=MAX_FUNCTIONS, check=None):
	"""The functions of VisionClaw's own code that start uses, and those they use, depth levels deep; start first. A
	function made inside another (as a tool inside register) does not count as a level. read(relative) gives the text
	of a file of VisionClaw's code; modules: the loaded modules (sys.modules). Each is a dict: file, qualname, place (as
	functionAt), function, depth, uses [(the qualname of what uses it, the lines around that place)], refusal (why it
	cannot be corrected, or ""). Nothing is imported or called."""
	modules = modules if modules is not None else sys.modules
	files = {}
	found, order = {}, []
	queue = [(start, None, 0, None, "")]
	while queue:
		if check is not None:
			check()
		# The nearest first: a function reached in fewer levels by one way counts at that level.
		thing, selfObject, level, caller, around = queue.pop(min(range(len(queue)), key=lambda at: (queue[at][2], at)))
		function = _plainFunction(thing)
		if function is None:
			continue
		relative = own(function.__code__.co_filename, root)
		if not relative.endswith(".py"):
			continue
		key = (relative, function.__code__.co_firstlineno, function.__name__)
		if key in found:
			if caller and len(found[key]["uses"]) < 6:
				found[key]["uses"].append((caller, around))
			continue
		if len(order) >= limit:
			continue
		if relative not in files:
			text = read(relative) or ""
			files[relative] = (text, text.splitlines(), allPlaces(text) if text else [])
		source, lines, places = files[relative]
		first = function.__code__.co_firstlineno
		place = next((p for p in places if p["name"] == function.__name__ and first in (p["decorated"], p["start"])), None)
		if place is None:
			continue
		entry = {"file": relative, "qualname": place["qualname"], "place": place, "source": source, "function": function,
			"depth": level, "uses": [(caller, around)] if caller else [], "refusal": refusal(relative, place)}
		found[key] = entry
		order.append(key)
		if level >= depth:
			continue
		try:
			used = list(_usesIn(function, selfObject, place, modules))
		except Exception as e:
			debuglog.error("ownfix", f"What {place['qualname']} uses could not be read", e)
			used = []
		for value, owner, firstLine, lastLine in used:
			inner = "<locals>" in str(getattr(_plainFunction(value), "__qualname__", ""))
			queue.append((value, owner, level if inner else level + 1, place["qualname"], _around(lines, place, firstLine, lastLine)))
	return [found[key] for key in order]


def _telling(text):
	"""The telling words of names and code as well as of sentences: openPanel is open and panel."""
	return words(match.label(str(text or "")))


def complaintWords(complaint):
	"""The words of a complaint that can find code: what it names, without the words that only say it went wrong."""
	return _telling(complaint) - _NOT_TELLING


def fitting(found, complaint, fallback=""):
	"""The functions a complaint is most likely about, the best first, at most MAX_OFFERED: only those that can be
	corrected, ranked by the complaint's telling words against each function's name and first line of help (counted
	more) and its code with the lines where it is used. fallback: words to rank by where the complaint names nothing,
	as what VisionClaw answered. Empty where nothing shares a word."""
	usable = [entry for entry in found if not entry["refusal"]]
	asked = complaintWords(complaint) or _telling(fallback)
	if not usable or not asked:
		return []
	entries = []
	for entry in usable:
		place = entry["place"]
		helpText = (ast.get_docstring(place["node"]) or "").split(". ")[0]
		named = _telling(place["name"]) | _telling(helpText)
		other = _telling(place["text"]) | _telling(" ".join(around for _caller, around in entry["uses"]))
		entries.append((named, other))
	return [usable[index] for index in ranking.rank(asked, entries, limit=MAX_OFFERED, share=OFFER_SHARE)]


CHOOSE_SYSTEM = (
	IDENTITY + " The user says VisionClaw did something wrong. You are given what the user said, what VisionClaw did, and "
	"a few functions of VisionClaw's own code that it used, each with a number. Give the number of the function whose "
	"work the user's words are about: the one that does what went wrong.")
CHOOSE_NONE = " Give 0 if none of them does it."


def chooseQuestion(complaint, done, offered):
	"""What the model that writes code is asked to choose from."""
	lines = [f"The user said: \"{uncut(complaint)}\"", f"What VisionClaw did: {done}", "The functions:"]
	for number, entry in enumerate(offered, 1):
		users = sorted({caller.split(".")[-1] for caller, _around in entry["uses"] if caller})
		lines.append(f"{number}. {entry['qualname']} in {entry['file']}" + (f", used by {', '.join(users)}" if users else "")
			+ f":\n```python\n{clip(textwrap.dedent(entry['place']['text']), 700)}\n```")
	lines.append("Which number?")
	return "\n".join(lines)


def chooseSchema(count, none):
	"""The form for the choice: a number of the list, and 0 only where the model may say none of them."""
	return {"type": "object", "properties": {"number": {"type": "integer", "enum": list(range(0 if none else 1, count + 1))}},
		"required": ["number"]}


COMPLAINT_FIX_TASK = (
	"You correct what one function of VisionClaw does wrong. VisionClaw is an add-on for the NVDA screen reader written "
	"in Python. The user said what went wrong; change the function so that it does what the user expected.\n"
	"Rules: Write the whole corrected function, from its def line to its end, and nothing else. Keep its name and its "
	"arguments. Change as few lines as you can, and keep everything else it does. Use only names the function already "
	"uses or that the facts given say exist. Add no import the function does not have. Indent with tabs, as the code is.")
COMPLAINT_REVIEW_SYSTEM = (
	IDENTITY + " You check a correction of one function of VisionClaw's own code, made because the user said that what it "
	"did was wrong. Say fixes=true if the corrected function would do what the user expected and changes nothing else "
	"the function did. Say fixes=false only for a clear problem, and name it in problem. Judge only from what is given.")


def complaintFacts(complaint, done, entry, nvda=()):
	"""What the models are told for a correction made from a complaint: what the user said, what VisionClaw did, the
	function, where it is used, and what the running NVDA has for the names it uses."""
	lines = [f"What the user says went wrong: \"{uncut(complaint)}\"", f"What VisionClaw did: {done}",
		f"The function {entry['qualname']} of {entry['file']}:\n```python\n{clip(textwrap.dedent(entry['place']['text']), 3000)}\n```"]
	for caller, around in entry["uses"][:2]:
		lines.append(f"Where {caller} uses it:\n```python\n{clip(around, 900)}\n```")
	if nvda:
		lines.append("What the running NVDA has, for names this function uses:\n" + "\n".join(f"- {fact}" for fact in nvda))
	return "\n".join(lines)


# --- What the running NVDA has, for the names a function uses ---

_LOADS_SELF = ("LOAD_FAST", "LOAD_FAST_CHECK", "LOAD_DEREF", "LOAD_FAST_BORROW", "LOAD_CLOSURE")
_LOADS_TWO = ("LOAD_FAST_LOAD_FAST", "LOAD_FAST_BORROW_LOAD_FAST_BORROW")


def _storedOnSelf(code, depth=0):
	"""The attributes a piece of code sets on self, read from its bytecode."""
	found = []
	try:
		instructions = list(dis.get_instructions(code))
	except Exception:
		return found
	before = None
	for instruction in instructions:
		if instruction.opname == "STORE_ATTR" and before is not None and (
				(before.opname in _LOADS_SELF and before.argval == "self")
				or (before.opname in _LOADS_TWO and isinstance(before.argval, tuple) and before.argval[-1] == "self")):
			found.append(str(instruction.argval))
		before = instruction
	if depth < 3:
		for const in code.co_consts:
			if isinstance(const, types.CodeType):
				found += _storedOnSelf(const, depth + 1)
	return found


def _family(cls):
	"""The classes of a class that are its program's own: those of the same top module, not wx's or Python's."""
	top = str(getattr(cls, "__module__", "")).split(".")[0]
	return [klass for klass in getattr(cls, "__mro__", (cls,)) if str(getattr(klass, "__module__", "")).split(".")[0] == top]


def storedAttributes(cls):
	"""What the code of a class and of its program's own base classes sets on each object, in the order it is first
	written: PrivacyAndSecuritySettingsPanel's makeSettings sets _logLevelCombo. Read from the bytecode; nothing runs."""
	names = []
	for klass in _family(cls):
		for value in list(vars(klass).values()):
			function = value.__func__ if isinstance(value, (staticmethod, classmethod)) else value
			code = getattr(function, "__code__", None)
			if isinstance(code, types.CodeType):
				for name in _storedOnSelf(code):
					if name not in names:
						names.append(name)
	return names


def _methods(cls):
	names = []
	for klass in _family(cls):
		for name, value in list(vars(klass).items()):
			if name.startswith("__") or name in names:
				continue
			if isinstance(value, (staticmethod, classmethod, types.FunctionType)):
				names.append(name)
	return names


def _first(names, wanted, limit):
	"""Names, those that share a telling word with what is wanted first, at most limit."""
	scored = sorted(names, key=lambda name: -len(_telling(name) & wanted))
	return scored[:limit]


def namesFacts(function, place, modules=None, complaint="", limit=4, perClass=24):
	"""What the running program has for the classes of NVDA (or of another program, never VisionClaw's own) a function
	uses, in sentences for the model: for each, what its code sets on each object and its methods, those the complaint
	names first. Only modules that are loaded are read: nothing is imported or called."""
	modules = modules if modules is not None else sys.modules
	space = getattr(function, "__globals__", {}) or {}
	imported = _importsIn(place["node"], space.get("__package__") or "", modules)
	wanted = complaintWords(complaint)
	facts, seen = [], []
	for sub in ast.walk(place["node"]):
		if not isinstance(sub, ast.Name) or sub.id in seen:
			continue
		seen.append(sub.id)
		value = imported.get(sub.id, space.get(sub.id, _MISSING))
		if not isinstance(value, type):
			continue
		module = str(getattr(value, "__module__", ""))
		if module.startswith(PACKAGE) or not inside.isNvda(module):
			continue
		stored = _first(storedAttributes(value), wanted, perClass)
		methods = _first(_methods(value), wanted, perClass)
		said = f"{sub.id}, a class of {module}."
		if stored:
			said += f" Its code sets on each object: {', '.join(stored)}."
		if methods:
			said += f" Its methods: {', '.join(methods)}."
		facts.append(said)
		if len(facts) >= limit:
			break
	return facts


def _namesOf(thing):
	"""The names something has, read from its own dictionary and its class's, without running anything."""
	names = set()
	for holder in [thing] + list(getattr(thing if isinstance(thing, type) else type(thing), "__mro__", ())):
		try:
			names.update(vars(holder))
		except TypeError:
			pass
	return names


def _dynamic(thing):
	"""Whether something may make names when they are asked for, by Python code of its own (__getattr__, or a
	__getattribute__ written in Python): then a name not found may still exist."""
	if isinstance(thing, types.ModuleType):
		return "__getattr__" in vars(thing)
	kind = thing if isinstance(thing, type) else type(thing)
	for klass in getattr(kind, "__mro__", ()):
		own = vars(klass)
		if "__getattr__" in own or isinstance(own.get("__getattribute__"), types.FunctionType):
			return True
	return False


def _exists(value, name):
	"""Whether something has a name: in its own dictionary or its class's, or as its class gives it when asked (wx's
	classes load their methods when they are first asked for). Nothing of the object itself runs."""
	try:
		inspect.getattr_static(value, name)
		return True
	except AttributeError:
		pass
	except Exception:
		return True
	if isinstance(value, types.ModuleType):
		return False
	try:
		getattr(value if isinstance(value, type) else type(value), name)
		return True
	except AttributeError:
		return False
	except Exception:
		return True


def unknownNames(newText, function, modules=None):
	"""Names a corrected function uses that do not exist in the running program, as sentences for the model that wrote
	it: a name never imported or defined, and a name asked of a module, a class or an object of the program that it does
	not have, with the names it has that are close. Read from the loaded modules and the function's own module without
	running anything; what cannot be told for certain is never said. Measured with Qwen3.5 4B on 2026-11-19: asked to
	put the focus on a control of NVDA's settings, it called gui.mainFrame.getFocus(), which NVDA does not have."""
	modules = modules if modules is not None else sys.modules
	try:
		tree = ast.parse(textwrap.dedent(str(newText or "")))
	except SyntaxError:
		return []
	node = next((child for child in tree.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
	if node is None:
		return []
	space = getattr(function, "__globals__", {}) or {}
	imported = _importsIn(node, space.get("__package__") or "", modules)
	defined = set(imported)
	for sub in ast.walk(node):
		if isinstance(sub, ast.Name) and not isinstance(sub.ctx, ast.Load):
			defined.add(sub.id)
		elif isinstance(sub, ast.arg):
			defined.add(sub.arg)
		elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
			defined.add(sub.name)
		elif isinstance(sub, (ast.Import, ast.ImportFrom)):
			defined.update((alias.asname or alias.name).split(".")[0] for alias in sub.names)
		elif isinstance(sub, ast.ExceptHandler) and sub.name:
			defined.add(sub.name)
		elif isinstance(sub, (ast.Global, ast.Nonlocal)):
			defined.update(sub.names)
	builtins = set(dir(__builtins__)) if isinstance(__builtins__, types.ModuleType) else set(__builtins__)
	problems = []
	for sub in ast.walk(node):
		if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) and sub.id not in defined and sub.id not in space \
				and sub.id not in builtins and sub.id != "__class__":
			said = f"{sub.id} is used but never imported or defined."
			if said not in problems:
				problems.append(said)
		if not isinstance(sub, ast.Attribute) or not isinstance(sub.ctx, ast.Load):
			continue
		attrs, expr = [], sub
		while isinstance(expr, ast.Attribute):
			attrs.append(expr.attr)
			expr = expr.value
		# A name the function gives a value itself cannot be told without running it: only imports and the module's names.
		if not isinstance(expr, ast.Name) or (expr.id not in imported and (expr.id in defined or expr.id not in space)):
			continue
		value = imported.get(expr.id, space.get(expr.id))
		dotted = expr.id
		for attr in reversed(attrs):
			if value is None or _dynamic(value) or isinstance(value, (int, float, str, bytes, bool, list, dict, tuple, set)):
				break
			if not _exists(value, attr):
				close = difflib.get_close_matches(attr, sorted(name for name in _namesOf(value) if not name.startswith("__")), 4, 0.6)
				said = (f"{dotted}.{attr} does not exist in the running NVDA: {dotted} has nothing called {attr}."
					+ (f" Names it has that are close: {', '.join(close)}." if close else ""))
				# Measured with Qwen3 14B on 2026-11-19: it asked the class of NVDA's settings page for the combo box that
				# the page's code sets on each page it makes.
				if isinstance(value, type) and attr in storedAttributes(value):
					said = (f"{dotted}.{attr} is not on the class {dotted}: its code sets {attr} on each object of it that is "
						"made, so it is found on such an object, not on the class.")
				if said not in problems:
					problems.append(said)
				break
			try:
				found = inspect.getattr_static(value, attr)
			except Exception:
				break
			if isinstance(found, (property, staticmethod, classmethod, types.FunctionType, types.BuiltinFunctionType,
					types.MethodType)) or not (isinstance(found, (types.ModuleType, type)) or hasattr(found, "__dict__")):
				break
			value, dotted = found, f"{dotted}.{attr}"
	return problems


def complaintReport(complaint, done, offered, why, version="", tools=()):
	"""What VisionClaw could not correct, as a Markdown file for the user to keep or to give to VisionClaw's developer."""
	lines = [
		"# What VisionClaw could not correct by itself", "",
		f"Written {time.strftime('%Y-%m-%d %H:%M', time.localtime(time.time()))} by VisionClaw {version}, after you said what "
		"went wrong. Nothing was changed.", "",
		"## What you said was wrong", "", complaint, "",
		"## What VisionClaw did", "", done, "",
		"## Why VisionClaw could not correct it", "", why, ""]
	if tools:
		lines += ["## The tools that request used", "", ", ".join(tools), ""]
	if offered:
		lines += ["## The functions of VisionClaw's code that fit your words best", ""]
		for entry in offered:
			lines += [f"### {entry['qualname']} in {entry['file']}", "", "```python",
				textwrap.dedent(entry["place"]["text"]).rstrip(), "```", ""]
	return "\n".join(lines)
