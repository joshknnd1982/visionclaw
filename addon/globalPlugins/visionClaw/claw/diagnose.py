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
# The checks prevent accidents; they are not a sandbox. Never describe them as one. No NVDA dependencies.

import ast
import difflib
import functools
import hashlib
import importlib
import json
import os
import re
import sys
import textwrap
import threading
import time

from . import debuglog
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
	dictionary with do (ERRORS, WHY, FIX, FIXES, REMOVE), which (a number, 1 the newest, -1 the oldest, or None) and
	about (the words that say which error is meant). Kept narrow: the words must name VisionClaw or "you" with its log,
	its errors or its code, or ask why the last request went wrong. "Open your log" is the log opened, not read here."""
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
	if found is None:
		return None
	return {"do": found, "which": whichNumber(low), "about": " ".join(sorted(words(said) - _ASKING_WORDS)),
		"request": bool(re.search(r"\b(request|task|command|answer|description)\b", low))}


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
				working[thread] = started.group(2)
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
	[message]}, or None."""
	story = None
	current = {}
	for when, thread, area, first, rest in entries(text):
		if area == "task":
			started = _NEW_REQUEST.match(first)
			if started:
				current[thread] = {"request": started.group(2), "when": when, "problems": [], "errors": [], "ended": "", "seconds": ""}
				continue
			ended = _ENDED.match(first)
			if ended and thread in current:
				done = current.pop(thread)
				done["ended"], done["seconds"] = ended.group(1), ended.group(2)
				story = done
				continue
		if thread not in current:
			continue
		failed = _TOOL_FAILED.match(first) if area == "tool" else None
		if failed:
			current[thread]["problems"].append((failed.group(1), failed.group(2)))
		elif first.startswith("ERROR: "):
			current[thread]["errors"].append(first[len("ERROR: "):].strip())
	return story


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


def checkFix(source, place, newText):
	"""Problems with a correction, as sentences the model can act on; empty when it may be offered. newText: the
	function as the model wrote it, its def line first."""
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
	if changed == 0:
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
	as it was (its digest, to know the code is still the same) and as it is now."""

	FIELDS = ("id", "file", "qualname", "version", "oldDigest", "old", "new", "error", "made", "state", "why")

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
			lines.append(f"{number}. {fix.qualname} in {fileWords(fix.file)}, made {ago(fix.made)} for VisionClaw {fix.version}, for the "
				f"error: {fix.error}. It is {said.get(fix.state, fix.state)}" + (f": {fix.why}" if fix.why and fix.state != "on" else "") + ".")
		return "\n".join(lines)


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
	return "\n".join([
		f"# VisionClaw's correction of {fix.qualname}", "",
		f"Made {time.strftime('%Y-%m-%d %H:%M', time.localtime(time.time()))} for VisionClaw {fix.version}, after you asked for it.",
		"VisionClaw's own files were not changed: the correction is put in place of the function while NVDA runs, and again "
		"when VisionClaw starts, for this version only. To undo it, say undo that, or remove the correction of your code.", "",
		"## The error", "", fix.error, "", "## What the model said went wrong", "", diagnosis or "Not asked.", "",
		"## What the correction changes", "", change, "", "## What the other model said", "", review or "Not asked.", "",
		"## What the models were given", "", facts_, "",
		"## The function as it was", "", "```python", textwrap.dedent(fix.old).rstrip(), "```", "",
		"## The function as it is now", "", "```python", fix.new.rstrip(), "```", ""])
