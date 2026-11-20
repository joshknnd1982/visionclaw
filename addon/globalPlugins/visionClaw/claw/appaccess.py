# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a whole program made accessible, one window after another. The owner asked on 2026-11-19 for "a skill
# that makes visionclaw learn all about the current window of a program, makes a plan to fix all accessibility issues,
# and then fixes those issues. The skill must use memory, scratchpads, logs, system prompts, rag. And when the user
# moves onto another window of the program, visionclaw can learn about it too, and visionclaw must understand that these
# two or three or four of twenty windows or 100 or more of these windows and all kinds of objects belong to this
# program. then visionclaw must implement all accessibility fixes."
# What follows from it, all of it plain code:
#   - wish(): what the user's words ask: learn the window in front, make the plan, carry it out, say which windows are
#     known or how far the plan is, learn each new window by itself or stop that, forget what was learned.
#   - Which window it is (windowId): its window class, and its title with what changes in it left out, a document's
#     name and numbers, so that "Untitled - Notepad" and "notes.txt - Notepad" are one window of the program. A page of
#     a website is told by its address's path with numbers and codes left out (pageId).
#   - The program's map: every window and page learned, and the plan for all of them, as two sections of the program's
#     own Markdown file of what VisionClaw found (claw/accessnotes.py). However many windows there are, they belong to
#     the program the file is named for, and so do their controls: a fix of the program's add-on works in every one.
#   - The plan: every fix the inspections found, each once for the whole program, with the windows it was found in; the
#     simplest remedy first (a name, being told of a change, a key that presses, reads or moves); then what can only be
#     done while a window is open, and what no add-on can fix, with what to do instead. Steps about what the user asked
#     VisionClaw to remember about the program come first among those still to make (favoured).
#   - What is made is read from the program's fixes add-on itself each time, never assumed (refreshed).
# No model writes or decides anything here. No NVDA dependencies.

import json
import re
import time

from . import fixes
from .fixmatch import plainText
from .memory import words

# What the user's words ask.
LEARN, PLAN, FIX, ALL, WINDOWS_SAID, PLAN_SAID, FOLLOW, UNFOLLOW, FORGET = (
	"learn", "plan", "fix", "all", "windows", "show plan", "follow", "unfollow", "forget")
# What only finds out or says, and what makes the fixes.
LOOKS_ONLY = (LEARN, PLAN, WINDOWS_SAID, PLAN_SAID, FOLLOW, UNFOLLOW, FORGET)
MAKES = (FIX, ALL)
# The kinds of step of a plan.
FIX_STEP, LOOK, HOTKEY, ADVICE = "fix", "look", "hotkey", "advice"
# What has become of a step that is a fix.
PLANNED, MADE = "planned", "made"
# How a window was learned.
ASKED, BY_ITSELF = "when you asked", "by itself when you moved there"
# What VisionClaw does when the user moves to a window of a program it is making accessible (the setting programFollow).
FOLLOW_TELL, FOLLOW_QUIET, FOLLOW_OFF = "tell", "quiet", "off"
FOLLOW_CHOICES = (FOLLOW_TELL, FOLLOW_QUIET, FOLLOW_OFF)
# The map has room for this many windows and steps; beyond that the oldest go, but never a step that is made.
MAX_WINDOWS = 1000
MAX_STEPS = 400
# How long VisionClaw waits after a window came to the front before it learns it by itself: the user may only be
# passing through.
SETTLE_SECONDS = 1.5
# Under this many windows the answer names them all; with more it says how many and how to hear them all.
NAMED_WINDOWS = 6

# --- What the user's words ask ---

_PROG = r"(?:program|app|application|game|software|site|website|web ?site)"
_WIN = r"(?:windows?|dialogs?|dialog box(?:es)?|screens?|pages?)"
_THIS_PROG = rf"(?:this|the|my|that|current)\s+{_PROG}"
_HERE_WIN = rf"(?:this|the current|current|the|this new|that|the active)\s+(?:new\s+)?{_WIN}(?:\s+(?:in front|i'?m in|i am in))?"
# The whole program: every window of it, all its dialogs, its windows, the whole app.
_WHOLE = re.compile(
	rf"\b(?:whole|entire|complete)\s+{_PROG}\b"
	rf"|\b(?:every|each|all(?:\s+of)?(?:\s+the)?|all its|all of its|any)\s+(?:other\s+|new\s+|of\s+(?:its|the|this)\s+)?{_WIN}\b"
	rf"|\b{_PROG}'?s\s+{_WIN}\b|\bits\s+{_WIN}\b"
	rf"|\b{_WIN}\s+(?:of|in|for)\s+{_THIS_PROG}\b", re.IGNORECASE)
# "Explore this page" is the page explored (explore_page), and "go through" is being led through a task (work_through).
_LEARN = r"(?:learn\w*|study|studies|get to know|map|memori[sz]e)"
_LOOK = r"(?:inspect\w*|check\w*|audit\w*|scan\w*|examin\w*|analy[sz]\w*|look (?:at|into|through))"
_FIX = r"(?:fix\w*|repair\w*|correct\w*|implement\w*|apply|applied|carry out|carried out|execute|resolv\w*|solv\w*)"
_ACCESS = r"(?:accessib\w*|usab\w*|issues?|problems?|unlabell?ed|unnamed|fix\w*)"
_NOT = re.compile(
	r"\bscratch ?pads?\b|\b(?:fix|repair|correct|debug|write|make)\s+(?:the |my |that |this |an |a )?add-?ons?\b"
	r"|\bnotes?\b|\b(?:your own|yourself|your (?:own )?(?:code|bugs?|errors?))\b|\bprofiles?\b|\bsettings?\b",
	re.IGNORECASE)
_FORGET = re.compile(
	r"\b(?:forget|delete|erase|clear|wipe|throw away|get rid of|remove)\b.{0,50}"
	rf"(?:\b(?:plan|map)\b.{{0,40}}\b(?:{_PROG}|fix\w*|accessib\w*|{_WIN})\b|\b{_WIN}\b.{{0,30}}\b(?:you|visionclaw)\s+(?:learn\w*|know|found)"
	rf"|\bwhat (?:you|visionclaw) (?:learned|learnt|know|found)\b.{{0,30}}\b{_WIN}\b|\b{_WIN}\s+(?:of|in)\s+{_THIS_PROG}\b)",
	re.IGNORECASE)
_UNFOLLOW = re.compile(
	r"\b(?:stop|don'?t|do not|no longer|quit|never)\b.{0,16}\b(?:learn\w*|follow\w*|mapp\w*|watch\w*|study\w*)\b.{0,40}"
	rf"\b(?:{_WIN}|{_PROG})\b", re.IGNORECASE)
_FOLLOW = re.compile(
	r"\b(?:keep|start|go on|continue|begin)\b.{0,12}\b(?:learn\w*|follow\w*|mapping|watching|studying)\b.{0,40}"
	rf"\b(?:{_WIN}|{_PROG})\b"
	rf"|\blearn\b.{{0,20}}\b(?:each|every|any|all|other|new)\b.{{0,14}}{_WIN}\b.{{0,30}}\b(?:as|when|whenever|that|once)\b.{{0,24}}"
	r"\b(?:move|moves|go|goes|open|opens|switch|get|gets|come|comes|reach|appear|appears)\b"
	rf"|\bfollow me\b.{{0,40}}\b{_WIN}\b", re.IGNORECASE)
_WINDOWS_SAID = re.compile(
	rf"\b(?:which|what|how many|list|tell me|say|name)\b.{{0,30}}\b(?:windows|dialogs|screens|pages)\b.{{0,40}}"
	r"\b(?:learn\w*|know|known|found|seen|mapped|inspected|checked|studied)\b"
	rf"|\b(?:what|which)\b.{{0,30}}\b(?:you|visionclaw)\b.{{0,20}}\b(?:learn\w*|know|found)\b.{{0,30}}\b{_WIN}\s+(?:of|in)\s+{_THIS_PROG}\b",
	re.IGNORECASE)
_PLAN_WORD = re.compile(r"\bplan\b", re.IGNORECASE)
_PLAN_ABOUT = re.compile(rf"\b(?:{_PROG}|{_WIN}|accessib\w*|fix\w*|issues?|problems?)\b|\b(?:your|the accessibility) plan\b", re.IGNORECASE)
_PLAN_MADE = re.compile(r"\b(?:make|making|made|create|draw up|work out|come up with|build|write|prepare|put together|plan)\b"
	r".{0,40}\b(?:plan|fix\w*)\b|^\W*(?:please\s+)?plan\b", re.IGNORECASE)
_PLAN_ASKED = re.compile(
	r"\b(?:what|what's|whats|show|read|tell|say|list|how far|how much|where|go over|repeat)\b.{0,30}\bplan\b"
	r"|\bplan\b.{0,20}\b(?:so far|look like|say|have)\b", re.IGNORECASE)
_LEFT = re.compile(
	r"\b(?:what(?:'s| is)?|how much(?: is)?|how many)\b.{0,12}\b(?:left|still|remaining)\b.{0,20}\b(?:to (?:fix|do|make)|fix\w*)\b"
	r"|\bhow far\b.{0,30}\b(?:fix\w*|accessib\w*|plan)\b", re.IGNORECASE)
_CARRY_OUT = re.compile(
	r"\b(?:carry out|do|follow|implement|apply|execute|finish|complete|go ahead with|run|act on)\b.{0,20}\b(?:the|your|this|that|my)\s+"
	r"(?:accessibility\s+)?plan\b"
	r"|\b(?:make|do|apply|implement|finish|add)\b.{0,12}\b(?:the|all the|all|rest of the|remaining|other)\s+(?:planned|remaining|other|rest of the)?\s*"
	r"(?:accessibility\s+)?fix(?:es)?\b.{0,40}\b(?:planned|you planned|left|remaining|for (?:this|the) (?:program|app|game|site|website))\b"
	r"|\b(?:make|do|apply|implement)\b.{0,10}\b(?:the )?(?:planned|remaining) (?:accessibility )?fix(?:es)?\b"
	r"|\bimplement\w*\b.{0,20}\b(?:all|every)\b.{0,20}\b(?:accessibility )?fix(?:es)?\b", re.IGNORECASE)
_ACCESSIBLE_WHOLE = re.compile(
	rf"\bmake\b.{{0,40}}\b(?:whole|entire|every|each|all(?: of)?(?: its| the)?)\s+(?:{_PROG}|{_WIN})\b.{{0,30}}\b(?:accessible|usable|easier to use)\b"
	rf"|\bmake\b.{{0,30}}\b{_PROG}'?s?\s+{_WIN}\b.{{0,20}}\b(?:accessible|usable)\b", re.IGNORECASE)
# The fixes asked for after the learning: "..., then fix those issues", "and fix them all".
_THEN_FIX = re.compile(
	r"\b(?:then|and then|and|after that|afterwards|next)\s*,?\s+(?:also\s+)?(?:please\s+)?(?:go ahead and\s+)?"
	r"(?:fix\w*|repair\w*|implement\w*|apply|correct|resolve|solve|carry (?:it|them|that|the plan) out|carry out"
	r"|make (?:the |all the |all |those |these )?(?:fix|changes))\b", re.IGNORECASE)
_THIS_TOO = re.compile(
	rf"\b(?:this|that|the current)\s+(?:new\s+)?(?:one|{_WIN})\s+(?:too|as well|also)\b|\b(?:add|include)\b.{{0,10}}\b(?:this|that)\s+{_WIN}\b"
	rf"|\banother\s+{_WIN}\s+of\b", re.IGNORECASE)
_LEARN_HERE = re.compile(
	rf"\b{_LEARN}\b.{{0,24}}\b(?:about\s+|all about\s+|everything about\s+)?{_HERE_WIN}\b"
	rf"|\b{_LEARN}\b.{{0,40}}\b(?:{_WIN}\s+(?:of|in)\s+{_THIS_PROG}|{_PROG}'?s\s+{_WIN})\b"
	rf"|\b{_LEARN}\b.{{0,30}}\b(?:the )?accessib\w*\s+of\s+{_THIS_PROG}\b", re.IGNORECASE)


def wish(text):
	"""What the user's words ask of the work on a whole program, as {"do": ...}, or None where they ask something else.
	Kept narrow: "fix this window", "inspect this window" and "make this program accessible" stay with the inspection of
	one window (fix_access, check_access); "learn about this program" stays the notes from the internet (learn_app)."""
	said = " ".join(str(text or "").split())
	if not said or _NOT.search(said):
		return None
	low = said.lower()
	whole = bool(_WHOLE.search(said))
	if _FORGET.search(said):
		return {"do": FORGET}
	if _UNFOLLOW.search(said):
		return {"do": UNFOLLOW}
	if _FOLLOW.search(said):
		return {"do": FOLLOW}
	if _WINDOWS_SAID.search(said) and not re.search(rf"\b{_FIX}\b", said, re.IGNORECASE):
		return {"do": WINDOWS_SAID}
	planned = bool(_PLAN_WORD.search(said) and _PLAN_ABOUT.search(said))
	if planned and _PLAN_ASKED.search(said) and not _PLAN_MADE.search(said):
		return {"do": PLAN_SAID}
	if _LEFT.search(said) and (whole or re.search(rf"\b{_PROG}\b", said, re.IGNORECASE)):
		return {"do": PLAN_SAID}
	learns = bool(_LEARN_HERE.search(said) or _THIS_TOO.search(said)
		or (whole and re.search(rf"\b(?:{_LEARN}|{_LOOK})\b", said, re.IGNORECASE)))
	fixes_ = bool(re.search(rf"\b{_FIX}\b", said, re.IGNORECASE) or re.search(r"\bmake (?:the |all )?(?:the )?fix", low))
	thenFix = bool(_THEN_FIX.search(said))
	if _CARRY_OUT.search(said):
		return {"do": ALL if learns else FIX}
	# "Make a plan to fix ..." asks for the plan, and nothing is made until the user says so; "... then fix them" asks
	# for the fixes too.
	planOnly = planned and _PLAN_MADE.search(said) and not thenFix
	if planOnly and (learns or whole or re.search(rf"\b(?:{_ACCESS}|{_WIN}|{_PROG})\b", said, re.IGNORECASE)):
		return {"do": PLAN}
	if _ACCESSIBLE_WHOLE.search(said) or (whole and fixes_ and not _onlyOne(said)):
		return {"do": ALL}
	if learns:
		if thenFix:
			return {"do": ALL}
		if planned or re.search(r"\bplan\b", low):
			return {"do": PLAN}
		return {"do": LEARN}
	if planned and _PLAN_MADE.search(said) and re.search(rf"\b(?:{_ACCESS}|{_WIN}|{_PROG})\b", said, re.IGNORECASE):
		return {"do": PLAN}
	return None


# A clause that belongs to the work on a whole program: "make a plan to fix all accessibility issues", "then fix those".
_BELONGS = re.compile(
	rf"\b(?:{_LEARN}|{_LOOK}|plan\w*|{_FIX}|{_ACCESS}|accessible|{_WIN}|{_PROG})\b|^\W*(?:and |then |and then )?"
	r"(?:do|make) (?:it|them|that|those|these|all of (?:it|them))\b", re.IGNORECASE)


def belongs(part):
	"""Whether a clause of a request is part of the work on a whole program, so that the request is kept whole: "learn
	this window, make a plan, then fix the issues" is one job, "learn this window and then open Notepad" is two."""
	return bool(_BELONGS.search(" ".join(str(part or "").split())))


def _onlyOne(text):
	"""Whether the words point at one window only: "fix this window", where "every" is about something else."""
	return bool(re.search(rf"\b(?:fix|repair)\w*\s+{_HERE_WIN}\b", text, re.IGNORECASE)) and not _WHOLE.search(
		re.sub(rf"\b(?:fix|repair)\w*\s+{_HERE_WIN}\b", " ", text, flags=re.IGNORECASE))


def makes(asked):
	"""Whether the words ask for the fixes to be made, not only learned or planned."""
	found = wish(asked)
	return bool(found) and found["do"] in MAKES


def targetOf(asked):
	"""What to learn where the words say: a web page, a program's window, or whichever the user is in (auto)."""
	text = str(asked or "").lower()
	if re.search(r"\b(web ?pages?|web ?sites?|sites?|pages?)\b", text) and not re.search(r"\b(windows?|dialogs?|programs?|apps?|applications?|games?)\b", text):
		return "page"
	if re.search(r"\b(windows?|dialogs?|programs?|apps?|applications?|games?|screens?)\b", text):
		return "window"
	return "auto"


# --- Which window or page it is ---

_SEPARATORS = re.compile(r"\s+[-–—|]\s+")
_FILE = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.[A-Za-z][A-Za-z0-9]{0,4}\b")
_QUOTED = re.compile("[\"“‘][^\"”’]{1,80}[\"”’]")
_NUMBER = re.compile(r"\d+")
CHANGING = "*"


def titleShape(title, names=()):
	"""A window's title with what changes in it left out, so that the same window of a program is known again with
	another document in it: the parts of a title that do not name the program become *, and so do file names and quoted
	names; numbers become #. "Untitled - Notepad" and "notes.txt - Notepad" are both "* - notepad". names: what the
	program is called (its file's name, the name its maker gave it)."""
	text = " ".join(str(title or "").split())
	if not text:
		return ""
	called = {word for name in names for word in plainText(name).split() if len(word) >= 3}
	parts = _SEPARATORS.split(text)
	if len(parts) > 1:
		kept = [part if set(plainText(part).split()) & called else CHANGING for part in parts]
		if all(part == CHANGING for part in kept):
			# Nothing names the program: its name is mostly last ("Report - Writer"), and the rest is the document.
			kept = [CHANGING] * (len(parts) - 1) + [parts[-1]]
		joined = []
		for part in kept:
			if not (part == CHANGING and joined and joined[-1] == CHANGING):
				joined.append(part)
		text = " - ".join(joined)
	text = _QUOTED.sub(CHANGING, text)
	text = _FILE.sub(CHANGING, text)
	text = _NUMBER.sub("#", text)
	return " ".join(text.lower().split())[:120]


def windowId(windowClass, title, names=()):
	"""What tells a window of a program apart from its other windows, and finds it again."""
	return {"cls": " ".join(str(windowClass or "").split())[:80], "title": titleShape(title, names)}


_CODE = re.compile(r"^(?=.*\d)[A-Za-z0-9_-]{8,}$|^[0-9a-f]{6,}$|^\d+$", re.IGNORECASE)


def pageId(address):
	"""What tells a page of a website apart from its other pages: the path of its address, with numbers and codes left
	out. "https://shop.example/orders/12345?x=1" is "/orders/*"."""
	text = str(address or "").strip()
	if "://" in text:
		text = text.split("://", 1)[1]
	for mark in "?#":
		text = text.split(mark, 1)[0]
	path = text.split("/", 1)[1] if "/" in text else ""
	shaped = [CHANGING if _CODE.match(part) else _NUMBER.sub("#", part.lower()) for part in path.split("/") if part]
	return {"page": ("/" + "/".join(shaped))[:120]}


def ref(ident):
	"""A window or page as a short text, to say which steps of the plan belong to it."""
	if not ident:
		return ""
	if "page" in ident:
		return "page " + ident["page"]
	return f"{ident.get('cls', '')} | {ident.get('title', '')}"


def kindOf(role="", windowClass="", page=False):
	"""What kind of place it is, in a word: a page, a dialog, or a window."""
	if page:
		return "page"
	if "DIALOG" in str(role or "").upper() or str(windowClass or "") == "#32770":
		return "dialog"
	return "window"


# --- The windows learned ---

# A problem of the inspection (claw/audit.py, accesstools._worked) in a few words, for the line of its window.
PROBLEM_WORDS = {
	"unnamed": "controls without a name", "clickable": "things that can be clicked but are no buttons or links",
	"feed": "an endless feed with no key from post to post", "blocks": "similar blocks with no key from one to the next",
	"media": "a player whose buttons are hard to reach", "changing": "parts that change without telling NVDA",
	"drawn": "text that is only shown as a picture", "structure": "no headings and no landmarks",
	"generic": "names that say nothing", "state": "states that may be missing", "frames": "frames without a name",
	"images": "images without a description", "picture": "nothing NVDA can read, the window is one picture",
	"turned": "controls that are dragged or turned with the mouse", "unreached": "controls the Tab key does not reach",
	"pointed": "controls worked with the mouse in a way the keyboard does not do",
	"gestured": "controls worked with the mouse in a way the keyboard does not do",
}


class Place:
	"""One window of a program or page of a website, as it was learned."""

	__slots__ = ("ident", "name", "kind", "controls", "usable", "named", "problems", "times", "how", "day")

	def __init__(self, ident, name, kind="window", controls=0, usable=0, named=0, problems=(), times=1, how=ASKED, day=""):
		self.ident = dict(ident or {})
		self.name = " ".join(str(name or "").split()) or "a window without a title"
		self.kind = kind
		self.controls, self.usable, self.named = int(controls or 0), int(usable or 0), int(named or 0)
		self.problems = list(problems)
		self.times = int(times or 1)
		self.how = how
		self.day = day or time.strftime("%Y-%m-%d")

	def key(self):
		return ref(self.ident)

	def problemText(self):
		if not self.problems:
			return "No problems were found."
		listed = _joined(self.problems)
		return f"{_count(len(self.problems), 'problem')}: {listed}."

	def line(self):
		"""The line of the map, as the user reads it."""
		what = "a page" if self.kind == "page" else "a dialog" if self.kind == "dialog" else "a window"
		known = (f"NVDA knows {_count(self.controls, 'control')} in it, {self.usable} that can be used and {self.named} with a "
			"name.") if self.kind != "page" else f"NVDA knows {_count(self.controls, 'control')} on it."
		learned = f"Learned {_count(self.times, 'time')}, the last time {self.how}."
		return f"{self.name}, {what}. {known} {self.problemText()} {learned}"

	def data(self):
		data = dict(self.ident)
		data.update(name=self.name, kind=self.kind, controls=self.controls, usable=self.usable, named=self.named,
			problems=self.problems, times=self.times, how=self.how)
		return data

	@classmethod
	def fromLine(cls, day, text, key):
		"""A window from its line in the file, or None when its brackets say nothing about which window it is."""
		if not isinstance(key, dict) or not (key.get("page") or "cls" in key or "title" in key):
			return None
		ident = {"page": key["page"]} if key.get("page") else {"cls": str(key.get("cls") or ""), "title": str(key.get("title") or "")}
		name = key.get("name") or str(text or "").split(", a ", 1)[0]
		problems = key.get("problems") if isinstance(key.get("problems"), list) else []
		return cls(ident, name, key.get("kind") or "window", key.get("controls"), key.get("usable"), key.get("named"),
			[str(p) for p in problems], key.get("times") or 1, key.get("how") or ASKED, day)


def placeFrom(report, ident, name, kind, how=ASKED, before=None):
	"""A window as an inspection (audit.Report) found it. before: the same window as it was learned before, whose count
	of times goes on."""
	nodes = getattr(report, "nodes", None)
	summary = str(getattr(report, "summary", "") or "")
	controls = usable = named = 0
	found = re.search(r"NVDA knows (\d+) controls? in it, (\d+) that can be used and (\d+) with a name", summary)
	if found:
		controls, usable, named = (int(n) for n in found.groups())
	elif nodes is not None:
		controls = len(nodes)
	problems = []
	for finding in getattr(report, "findings", ()) or ():
		said = PROBLEM_WORDS.get(finding.id, finding.id)
		if said not in problems:
			problems.append(said)
	return Place(ident, name, kind, controls, usable, named, problems, (before.times + 1) if before else 1, how)


# --- The plan ---

# The simplest remedy first (the owner: a name, a key that presses or reads, a lasting fix, then the rest).
_RANKS = {(fixes.NAME, False): 0, (fixes.NAME, True): 1, (fixes.WATCH, False): 2, (fixes.PRESS, False): 3,
	(fixes.READ, False): 4, (fixes.JUMP, False): 5}
_KIND_RANKS = {HOTKEY: 6, LOOK: 7, ADVICE: 8}


def ruleKey(rule):
	return json.dumps(rule or {}, sort_keys=True)


def fixData(fix):
	"""Only what a planned fix may hold: its kind, its rule cleaned as an add-on's rule is, what it is called, and whether
	the name is a guess from a picture. None when it cannot be a fix."""
	try:
		kind = fix.get("kind")
		if kind not in fixes.KINDS:
			return None
		label = " ".join(str(fix.get("label") or "").split())[:60]
		if not label:
			return None
		data = {"kind": kind, "rule": fixes.cleanRule(fix.get("rule")), "label": label}
		if fix.get("guess"):
			data["guess"] = True
		return data
	except (ValueError, AttributeError, TypeError):
		return None


class Step:
	"""One step of the plan. kind: FIX_STEP (a fix of the program's add-on), LOOK (controls to be named from their
	pictures, while their window is open), HOTKEY (controls that need a hotkey of VisionClaw's own, made while their
	window is open), ADVICE (what no add-on can fix, and what to do instead). fix: the fix's data, or for LOOK
	{"rule", "kind", "count"}. windows: the windows it was found in (ref). status: PLANNED or MADE, for a fix."""

	__slots__ = ("kind", "fix", "text", "finding", "windows", "status", "day", "made")

	def __init__(self, kind, fix=None, text="", finding="", windows=(), status=PLANNED, day=""):
		self.kind = kind
		self.fix = dict(fix) if fix else None
		self.text = " ".join(str(text or "").split())
		self.finding = finding
		self.windows = list(windows)
		self.status = status if kind == FIX_STEP else ""
		self.day = day or time.strftime("%Y-%m-%d")
		# The fix as the add-on has it, with its keys, once it is made (refreshed).
		self.made = None

	def key(self):
		if self.kind == FIX_STEP:
			return (FIX_STEP, self.fix["kind"], ruleKey(self.fix["rule"]))
		if self.kind == LOOK:
			return (LOOK, ruleKey(self.fix.get("rule")))
		return (self.kind, self.finding, self.windows[0] if self.windows else "")

	def rank(self):
		if self.kind == FIX_STEP:
			return _RANKS.get((self.fix["kind"], bool(self.fix.get("guess")) and self.fix["kind"] == fixes.NAME), 5)
		return _KIND_RANKS[self.kind]

	def sentence(self):
		"""What the step does, in a plain sentence from its data."""
		if self.kind == FIX_STEP:
			if self.made is not None:
				return fixes.describeFix(self.made).rstrip(".")
			return planned(self.fix)
		if self.kind == LOOK:
			count = int(self.fix.get("count") or 1)
			kind = str(self.fix.get("kind") or "control")
			return (f"{_count(count, kind)} without a name, to be named from {'its picture' if count == 1 else 'their pictures'} "
				"while the window is open")
		return self.text.rstrip(".")

	def words(self):
		"""What the step is about, for finding the steps a memory of the user's is about."""
		return words(" ".join([self.sentence()] + [w.split("|")[-1] for w in self.windows]))

	def data(self):
		data = {"step": self.kind, "in": self.windows}
		if self.fix:
			data["fix"] = self.fix
		if self.finding:
			data["finding"] = self.finding
		if self.kind in (HOTKEY, ADVICE):
			data["say"] = self.text
		if self.kind == FIX_STEP:
			data["status"] = self.status
		return data

	@classmethod
	def fromLine(cls, day, key):
		"""A step from its line in the file, or None when its brackets do not say what it is."""
		if not isinstance(key, dict) or key.get("step") not in (FIX_STEP, LOOK, HOTKEY, ADVICE):
			return None
		kind = key["step"]
		windows = [str(w) for w in key.get("in") or () if str(w).strip()]
		if kind == FIX_STEP:
			fix = fixData(key.get("fix") or {})
			if fix is None:
				return None
			return cls(kind, fix, finding=str(key.get("finding") or ""), windows=windows,
				status=MADE if key.get("status") == MADE else PLANNED, day=day)
		if kind == LOOK:
			fix = key.get("fix") if isinstance(key.get("fix"), dict) else {}
			try:
				rule = fixes.cleanRule(fix.get("rule"))
			except (ValueError, AttributeError):
				return None
			return cls(kind, {"rule": rule, "kind": str(fix.get("kind") or "control"), "count": int(fix.get("count") or 1)},
				finding=str(key.get("finding") or ""), windows=windows, day=day)
		text = str(key.get("say") or "")
		return cls(kind, text=text, finding=str(key.get("finding") or ""), windows=windows, day=day) if text else None


def planned(fix):
	"""A fix that is not made yet, in a plain sentence: it has no keys yet, which are chosen when it is made."""
	kind, label = fix["kind"], fix["label"]
	if kind == fixes.NAME:
		guess = ", a guess from a picture that can be wrong" if fix.get("guess") else ""
		return f"{fixes._kindName(fix['rule']).capitalize()} without a name are called {label}{guess}"
	if kind == fixes.PRESS:
		return f"A key that presses {label}, wherever you are in it"
	if kind == fixes.READ:
		return f"A key that reads {label}"
	if kind == fixes.JUMP:
		return f"Two keys that move to the next and the previous {label}"
	return f"Being told when {label} changes"


def stepsFrom(report, where, named=None):
	"""The steps for what one inspection of a window found. where: the window (ref). named: {ruleKey: name} for controls
	without a name that were named from their pictures, or from the program's notes, while the window was open."""
	named = named or {}
	steps = []
	for finding in getattr(report, "findings", ()) or ():
		made = False
		for fix in finding.fixes:
			data = fixData(fix)
			if data is not None:
				steps.append(Step(FIX_STEP, data, finding=finding.id, windows=[where]))
				made = True
		for group in finding.look:
			name = named.get(ruleKey(group.get("rule")))
			if name:
				data = fixData({"kind": fixes.NAME, "rule": group.get("rule"), "label": name, "guess": True})
				if data is not None:
					steps.append(Step(FIX_STEP, data, finding=finding.id, windows=[where]))
					made = True
					continue
			try:
				rule = fixes.cleanRule(group.get("rule"))
			except ValueError:
				continue
			steps.append(Step(LOOK, {"rule": rule, "kind": str(group.get("kind") or "control"), "count": len(group.get("nodes") or ())},
				finding=finding.id, windows=[where]))
			made = True
		if finding.controls:
			steps.append(Step(HOTKEY, text=" ".join(part for part in (finding.text, finding.advice) if part), finding=finding.id,
				windows=[where]))
			made = True
		if not made:
			steps.append(Step(ADVICE, text=" ".join(part for part in (finding.text, finding.advice) if part), finding=finding.id,
				windows=[where]))
	return steps


def merged(plan, new, where):
	"""The plan after a window (where) was learned: a step found again keeps its place and gets this window too; a step
	that was found only in this window and is gone now is dropped, unless it is made, since its fix is in the add-on and
	may be why it is gone; a name found for controls that waited to be looked at takes the place of the look. A name from
	the program's code takes the place of a guess from a picture."""
	fresh = {}
	for step in new:
		fresh.setdefault(step.key(), step)
	out = []
	for step in plan:
		key = step.key()
		if key in fresh:
			found = fresh.pop(key)
			if where not in step.windows:
				step.windows.append(where)
			if step.kind == FIX_STEP and step.fix.get("guess") and not found.fix.get("guess"):
				step.fix = found.fix
			if step.kind in (LOOK, HOTKEY, ADVICE):
				step.fix, step.text = found.fix, found.text
			out.append(step)
		elif where in step.windows and step.status != MADE:
			rest = [w for w in step.windows if w != where]
			if rest:
				step.windows = rest
				out.append(step)
		else:
			out.append(step)
	out += [step for step in new if step.key() in fresh and fresh.pop(step.key()) is step]
	names = {ruleKey(step.fix["rule"]) for step in out if step.kind == FIX_STEP and step.fix["kind"] == fixes.NAME}
	out = [step for step in out if not (step.kind == LOOK and ruleKey(step.fix.get("rule")) in names)]
	return trimmed(out)


def trimmed(plan):
	"""At most MAX_STEPS steps; the oldest that are not made go first."""
	while len(plan) > MAX_STEPS:
		at = next((i for i, step in enumerate(plan) if step.status != MADE), 0)
		del plan[at]
	return plan


def refreshed(plan, installed):
	"""Each fix of the plan marked made where the program's add-on has it now, and planned where it does not. installed:
	the fixes of the add-on (fixes.parse), with their keys."""
	have = {}
	for fix in installed or ():
		try:
			have[(fix["kind"], ruleKey(fixes.cleanRule(fix["rule"])))] = fix
		except (ValueError, KeyError, TypeError, AttributeError):
			continue
	for step in plan:
		if step.kind == FIX_STEP:
			step.made = have.get((step.fix["kind"], ruleKey(step.fix["rule"])))
			step.status = MADE if step.made is not None else PLANNED
	return plan


def favoured(plan, memories):
	"""The steps of the plan in the order they are made and said: those still to make whose words a memory of the user's
	about this program shares come first, then by the simplest remedy. memories: the lines the user asked VisionClaw to
	remember about this program. Returns (the steps in order, how many a memory moved forward)."""
	wanted = set()
	for line in memories or ():
		wanted |= words(line)
	wanted -= _PLAIN
	moved = 0

	def order(pair):
		at, step = pair
		# The more of a memory's words a step shares (the window and the control it names), the sooner it comes.
		shared = len(step.words() & wanted) if wanted and step.kind == FIX_STEP and step.status == PLANNED else 0
		return (-shared, step.rank(), at)

	ranked = sorted(enumerate(plan), key=order)
	if wanted:
		moved = sum(1 for _at, step in ranked if step.kind == FIX_STEP and step.status == PLANNED and step.words() & wanted)
	return [step for _at, step in ranked], moved


_PLAIN = words("program window windows dialog button buttons control controls key keys name names called use used want like "
	"always never often mostly")


def toMake(plan):
	"""The fixes the add-on can be given now, from every window: those still planned."""
	return [step for step in plan if step.kind == FIX_STEP and step.status == PLANNED]


def counts(plan):
	"""How many steps there are of each sort: (to make, made, need their window, no add-on can fix)."""
	make = sum(1 for step in plan if step.kind == FIX_STEP and step.status == PLANNED)
	made = sum(1 for step in plan if step.kind == FIX_STEP and step.status == MADE)
	window = sum(1 for step in plan if step.kind in (LOOK, HOTKEY))
	advice = sum(1 for step in plan if step.kind == ADVICE)
	return make, made, window, advice


# --- What is said ---

def _count(number, word):
	number = int(number or 0)
	if number == 1:
		return f"1 {word}"
	if word.endswith("y") and not word.endswith(("ey", "ay", "oy")):
		return f"{number} {word[:-1]}ies"
	if word.endswith(("s", "x", "ch", "sh")):
		return f"{number} {word}es"
	return f"{number} {word}s"


def _joined(items):
	items = [str(item) for item in items if str(item).strip()]
	if not items:
		return ""
	if len(items) == 1:
		return items[0]
	return ", ".join(items[:-1]) + " and " + items[-1]


def where(scope):
	return f"the website {scope['site']}" if scope.get("site") else f"the program {scope.get('app', '')}"


def placesWord(scope, count=2):
	word = "page" if scope.get("site") else "window"
	return word if count == 1 else word + "s"


def namesOf(places):
	"""{ref: the name the user knows the window by}."""
	return {place.key(): place.name for place in places}


def inText(step, names, scope):
	"""Which windows a step belongs to, in words; every one of them."""
	called = [names.get(w) or w.split("|")[-1].strip() or "a window without a title" for w in step.windows]
	called = list(dict.fromkeys(called))
	if not called:
		return ""
	word = placesWord(scope, len(called))
	the = "In the" if not scope.get("site") else "On the"
	return f"{the} {word} {_joined(called)}."


def stepLine(step, names, scope):
	"""One step, as its line in the file and as it is said: what has become of it, what it is, and where."""
	if step.kind == FIX_STEP:
		head = "Made" if step.status == MADE else "To make"
	elif step.kind == LOOK:
		head = "Needs its window open"
	elif step.kind == HOTKEY:
		head = "Needs its window open, for a hotkey"
	else:
		head = "No add-on can fix this"
	return f"{head}: {step.sentence()}. {inText(step, names, scope)}".strip()


def countText(plan, scope, places):
	"""The plan in one or two sentences: how many steps, and of which sort."""
	make, made, window, advice = counts(plan)
	total = len(plan)
	if not total:
		return f"The plan for {where(scope)} has no steps: nothing that VisionClaw checks for was found in its {placesWord(scope)}."
	parts = []
	if make:
		parts.append(f"{make} to make")
	if made:
		parts.append(f"{made} made")
	if window:
		parts.append(f"{window} that {'needs its' if window == 1 else 'need their'} {placesWord(scope, 1)} open")
	if advice:
		parts.append(f"{advice} that no add-on can fix")
	known = len(places)
	return (f"The plan for {where(scope)}, from the {_count(known, placesWord(scope, 1))} VisionClaw has learned, has "
		f"{_count(total, 'step')}: {_joined(parts)}.")


def planText(plan, scope, places, memoryMoved=0):
	"""The whole plan, every step numbered, as it is said when the user asks for it."""
	names = namesOf(places)
	lines = [countText(plan, scope, places)]
	if memoryMoved:
		lines.append(f"{_count(memoryMoved, 'step')} that what you asked VisionClaw to remember is about "
			f"{'comes' if memoryMoved == 1 else 'come'} first.")
	for number, step in enumerate(plan, 1):
		lines.append(f"{number}. {stepLine(step, names, scope)}")
	make = counts(plan)[0]
	if make:
		lines.append(nextText(make))
	return "\n".join(lines)


def nextText(make):
	"""What to say to have the planned fixes made."""
	return (f"To make the {_count(make, 'fix')} still to make, say: make the planned fixes for this program. VisionClaw "
		"asks before it turns them on.")


def windowsText(places, scope):
	"""Every window learned, by name, with what was found in it: the whole list, as the user asked for it."""
	if not places:
		return f"VisionClaw has learned no {placesWord(scope)} of {where(scope)} yet. Say: learn this window, while one is in front."
	word = placesWord(scope, len(places))
	lines = [f"VisionClaw has learned {_count(len(places), placesWord(scope, 1))} of {where(scope)}, and all of "
		f"{'it belongs' if len(places) == 1 else 'them belong'} to it:"]
	for number, place in enumerate(places, 1):
		lines.append(f"{number}. {place.line()}")
	if len(places) > 1:
		lines.append(f"A fix made for {where(scope)} works in every one of these {word}.")
	return "\n".join(lines)


def knownText(places, scope, place):
	"""How many windows of the program VisionClaw knows, after one was learned: names them where there are few, and
	says how many and how to hear them all where there are more. A summary by design; nothing is cut in a name."""
	count = len(places)
	if count <= 1:
		return f"It is the first {placesWord(scope, 1)} of {where(scope)} that VisionClaw has learned."
	if count <= NAMED_WINDOWS:
		return (f"VisionClaw now knows {_count(count, placesWord(scope, 1))} of {where(scope)}, all of them part of it: "
			f"{_joined(p.name for p in places)}.")
	return (f"VisionClaw now knows {_count(count, placesWord(scope, 1))} of {where(scope)}, all of them part of it. To hear "
		f"every one, say: which windows of this program have you learned.")


def learnedText(place, scope, findings, mine, plan, places, logLines=(), memoryMoved=0, followed=FOLLOW_TELL, counted=True,
		nextStep=True):
	"""What is said after a window was learned: what it is, every problem found in it, its steps in the plan, how many
	windows the program has that VisionClaw knows, the plan in numbers (counted), what NVDA's log said, and what to say
	to have the fixes made (nextStep). findings: the inspection's findings (their sentences are said whole). mine: the
	steps of the plan that belong to this window."""
	what = "page" if place.kind == "page" else "dialog" if place.kind == "dialog" else "window"
	lines = [f"Learned the {what} {place.name} of {where(scope)}." if not scope.get("site")
		else f"Learned the page {place.name} of {where(scope)}."]
	if findings:
		lines.append(f"Found {_count(len(findings), 'problem')} in it:")
		for number, finding in enumerate(findings, 1):
			lines.append(f"{number}. " + " ".join(part for part in (finding.text, finding.advice) if part))
	else:
		lines.append("None of the problems VisionClaw checks for were found in it. That does not prove everything in it is "
			"easy to use.")
	names = namesOf(places)
	if mine:
		lines.append(f"Its {_count(len(mine), 'step')} in the plan for the whole {'website' if scope.get('site') else 'program'}:")
		for step in mine:
			lines.append(f"- {stepLine(step, names, scope)}")
	lines.append(knownText(places, scope, place))
	if counted:
		lines.append(countText(plan, scope, places))
		if memoryMoved:
			lines.append("Steps that what you asked VisionClaw to remember is about come first.")
	lines += list(logLines)
	make = counts(plan)[0]
	if make and nextStep:
		lines.append(nextText(make))
	if followed == FOLLOW_TELL:
		lines.append(f"When you move to another {placesWord(scope, 1)} of it, VisionClaw learns that one too, and tells you.")
	elif followed == FOLLOW_QUIET:
		lines.append(f"When you move to another {placesWord(scope, 1)} of it, VisionClaw learns that one too, quietly.")
	elif not scope.get("site"):
		lines.append("To learn another window, move to it and say: learn this window too.")
	return "\n".join(lines)


def followedText(place, scope, findings, mine, make):
	"""One sentence after a window was learned by itself, when the user moved there."""
	found = (f"{_count(len(findings), 'problem')}" if findings else "no problems")
	more = f", {_count(len(mine), 'step')} for it in the plan" if mine else ""
	tail = " Say: make the planned fixes for this program." if make and mine else ""
	return f"VisionClaw learned this {place.kind} of {scope.get('app') or scope.get('site')}: {found}{more}.{tail}"


def leftText(plan, names, scope):
	"""After the fixes were made: what is still left, step by step, so that nothing is hidden."""
	left = [step for step in plan if step.kind != FIX_STEP or step.status != MADE]
	if not left:
		return f"Every step of the plan for {where(scope)} is made."
	lines = [f"Still left in the plan: {_count(len(left), 'step')}."]
	for step in left:
		lines.append(f"- {stepLine(step, names, scope)}")
	if any(step.kind in (LOOK, HOTKEY) for step in left):
		lines.append(f"For a step that needs its {placesWord(scope, 1)} open, move to that {placesWord(scope, 1)} and say: "
			"learn this window and make its fixes.")
	return "\n".join(lines)


def contextText(places, plan, scope):
	"""For the model that chooses how to handle a request: that the user is in a program VisionClaw is making accessible,
	how many of its windows are known, and how much of the plan is left. "" when no window of it is known."""
	if not places:
		return ""
	make, made, window, advice = counts(plan)
	return (f"VisionClaw is making {where(scope)} accessible window after window: it has learned "
		f"{_count(len(places), placesWord(scope, 1))} of it, and its plan has {make} fixes still to make and {made} made.")


def scratchLine(place, scope, findings, new):
	"""The line written on the program's learning scratchpad after a window was learned, for the models that work there
	later. Plain code writes it."""
	problems = _joined(place.problems) if place.problems else "no problems"
	planned = f"; {_count(len(new), 'step')} for it in the accessibility plan" if new else ""
	return (f"VisionClaw inspected the {place.kind} {place.name} of {scope.get('app') or scope.get('site')}: "
		f"{problems}{planned}.")


# --- The map in the program's file ---

def placesFrom(lines):
	"""The windows of the map, from the lines of its section (accessnotes.WINDOWS)."""
	found = []
	for day, text, key in lines:
		place = Place.fromLine(day, text, key)
		if place is not None:
			found.append(place)
	return found


def placeLines(places):
	return [(place.day, place.line(), place.data()) for place in places[-MAX_WINDOWS:]]


def withPlace(places, place):
	"""The windows with one learned (again): it takes the place of the same window learned before, and goes last."""
	return [old for old in places if old.key() != place.key()] + [place]


def planFrom(lines):
	"""The steps of the plan, from the lines of its section (accessnotes.PLAN)."""
	found = []
	for day, _text, key in lines:
		step = Step.fromLine(day, key)
		if step is not None:
			found.append(step)
	return found


def planLines(plan, places, scope):
	names = namesOf(places)
	return [(step.day, stepLine(step, names, scope), step.data()) for step in plan]


# --- Following the user from window to window ---

def follows(setting, stopped, scope, known, here):
	"""Whether a window the user moved to is learned by itself: following is not off, the user did not say to stop for
	this program, VisionClaw is making the program accessible (it knows a window of it), and this window is not known."""
	if setting not in (FOLLOW_TELL, FOLLOW_QUIET) or not scope or not here:
		return False
	name = scope.get("app") or scope.get("site") or ""
	if not name or name in (stopped or ()):
		return False
	return bool(known) and here not in known
