# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - scratchpads: Markdown files in which VisionClaw and its models write down what they find while they
# work, and look it up again, the way cloud AI models keep notes in files while they carry out a long task.
# The owner said on 2026-11-19: "if no such scratchpad functionality exists so models have a place to write stuff
# down and do rag internally so they can better query, learn, act, query, learn, act, etcetera ... it should be a
# scratchpad similar to those used by cloud AI models ... scratchpads for agentic tasks, descriptions, file-based
# scratchpads", then: "the AI models must be able to use their various scratchpads to adapt and learn on-the-fly
# about everything from objects, various apis, controls, windows, apps, games, websites, browse mode and focus mode,
# photos, charts, maps, drawing apps, math equations, various office apps, music and audio programs", and "all
# scratchpads and logs must follow the user, even into portable copies of the addon".
# Four kinds, each a Markdown file the user can open, change and delete:
#   - the scratchpad of one request: a section of the request's work sheet (claw/worksheet.py), deleted with it;
#   - a task scratchpad: a task the user works on over several requests, with a list of things to do, notes and
#     what was done so far; one is open at a time, and it goes with every request while it is open;
#   - a learning scratchpad for each program and website: what the models found out while working there, each line
#     with the topics it is about (charts, maps, browse mode, audio programs ...), found again by plain code;
#   - the descriptions scratchpad: the last descriptions of the screen and of pictures, and the questions answered
#     about them.
# All of them are kept in the folder "scratchpads" of VisionClaw's data, inside the add-on's folder, so that they
# go with the user into a portable copy and through an update (claw/portable.py). A model never decides what is
# kept: it writes one short line, and plain code keeps it only when its keys and most of its words stand in what
# it was made from (learn.checked). Plain code finds again what fits a question or a step, by BM25 over words and
# concepts, the topics, and the program the user is in; a small model is given at most a few short lines.
# No NVDA dependencies.

import os
import re
import threading
import time

from . import concepts, debuglog
from .learn import _keysIn
from .llm import clip, uncut
from .memory import words
from .planning import alike, bm25
from .prompts import IDENTITY

FOLDER = "scratchpads"
TASKS = "tasks"
LEARNED = "learned"
DESCRIPTIONS_FILE = "descriptions.md"
INDEX = "SCRATCHPADS.md"
# The kinds of scratchpad.
TASK, LEARNING, DESCRIBED, REQUEST = "task", "learning", "descriptions", "request"
OPEN, FINISHED = "open", "finished"
# Who wrote a line.
BY_YOU, BY_MODEL, BY_VISIONCLAW = "you", "the model", "VisionClaw"
# How many lines a scratchpad keeps at most; the oldest go first. A Markdown file the user reads stays short.
MAX_NOTES = 80
MAX_DONE = 40
MAX_TODO = 30
MAX_DESCRIPTIONS = 12
# A line the models write is one short sentence.
NOTE_CHARS = 240
# How long a passage of a result is, when a long result is split to find the parts a step needs.
PASSAGE_CHARS = 320
# How many lines of the scratchpads go to one step, to the model that chooses, and to an answer.
FED_NOTES = 3
CONTEXT_NOTES = 2
# Two lines this alike (planning.alike) are about the same thing: the newer one takes the place of the older.
SAME = 0.75
# A line that shares no topic with the question must cover this much of its telling words.
COVER = 0.34
# How much a shared topic and the same program count, besides the words.
TOPIC_WEIGHT = 1.0
PROGRAM_WEIGHT = 0.8
_ASKS = words("about write wrote written note noted notes anything something say said tell know remember find found "
	"look there scratchpad scratchpads anyth")
# A line that scores less than this share of the best one is left out: a small model reads a few lines that fit better
# than many that only share a word.
RELATIVE = 0.5

# The topics a line is about, read by plain code from its words, and from the program it was written in. The owner's
# list of 2026-11-19, as a blind person says them: what a line is about is told by the words that name it.
TOPICS = (
	("objects and controls", r"\b(objects?|controls?|buttons?|check ?box(es)?|combo ?box(es)?|edit (fields?|box(es)?)|"
		r"fields?|sliders?|list items?|tree ?views?|tabs?|menus?|menu items?|tool ?bars?|dials?|knobs?|faders?|labels?|"
		r"unlabell?ed|focused|focus)\b"),
	("windows and dialogs", r"\b(windows?|dialogs?|dialog box(es)?|title bar|panes?|panels?|status bar)\b"),
	("programs", r"\b(programs?|apps?|applications?|software|utilit(y|ies))\b"),
	("games", r"\b(games?|gaming|player|levels?|inventory|quests?|steam|controller)\b"),
	("websites", r"\b(web ?sites?|web ?pages?|links?|browsers?|chrome|edge|firefox|headings?|landmarks?|urls?|sites?)\b"),
	("browse mode", r"\bbrowse mode\b|\bvirtual buffer\b|\breading position\b"),
	("focus mode", r"\bfocus mode\b|\bforms? mode\b"),
	("photos and pictures", r"\b(photos?|pictures?|images?|screenshots?|selfies?|faces?|camera)\b"),
	("charts and graphs", r"\b(charts?|graphs?|plots?|axis|axes|legends?|bar charts?|pie|trends?|diagrams?)\b"),
	("maps", r"\b(maps?|directions|routes?|streets?|north|south|east|west|latitude|longitude|locations?)\b"),
	("drawing", r"\b(draw\w*|paint\w*|canvas|brush(es)?|sketch\w*|pen tool|layers?|shapes?)\b"),
	("maths", r"\b(maths?|mathematic\w*|equations?|formulas?|fractions?|algebra|calculus|integrals?|derivatives?|"
		r"mathml|latex|calculator|square roots?|exponents?)\b"),
	("office documents", r"\b(word|excel|powerpoint|outlook|onenote|documents?|spreadsheets?|workbooks?|cells?|rows?|"
		r"columns?|slides?|e-?mails?|inbox|ribbon|libreoffice|google docs)\b"),
	("music and audio", r"\b(music|audio|sounds?|songs?|tracks?|mixers?|daws?|reaper|audacity|plug-?ins?|vsts?|midi|"
		r"tempo|volume|equali[sz]ers?|record\w*|playback|synth\w*)\b"),
	("accessibility interfaces", r"\b(apis?|ui ?automation|uia|iaccessible2?|ia2|msaa|aria|java access bridge|"
		r"automation ids?|accessibility (apis?|interfaces?)|com objects?|window class(es)?|roles?|states?)\b"),
	("keys", r"\b(keys?|shortcuts?|hot ?keys?|key commands?|keyboard)\b|\b(nvda|control|ctrl|alt|shift|windows)\s*\+"),
)
_TOPICS = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in TOPICS)
# Topics nearly every line has: they do not make a line of another program fit a question.
BROAD = frozenset(("objects and controls", "windows and dialogs", "programs", "keys"))

# --- The user's words: what is asked of a scratchpad ---

_PAD = r"scratch[ -]?pads?"
_PAD_WORDS = re.compile(rf"\b{_PAD}\b", re.IGNORECASE)
_POLITE = r"^\W*(?:(?:hey |ok |okay )?visionclaw[,:]?\s+)?(?:please\s+)?(?:(?:can|could|would|will) you\s+)?(?:please\s+)?"
START, NOTE, ADD, SHOW, SEARCH, CHECK, NEXT, FINISH, DELETE, LIST, OPEN_FILE = (
	"start", "note", "add", "show", "search", "check", "next", "finish", "delete", "list", "open")
_START = re.compile(rf"\b(start|begin|make|create|set up|new|open a new|open a)\b.{{0,30}}\b{_PAD}\b", re.IGNORECASE)
_TITLE = re.compile(rf"\b{_PAD}\b\s*(?:for|about|called|named|on|to)\s+(.+)$", re.IGNORECASE)
_NOTE = re.compile(
	rf"\b(note|write|jot|put|save|keep|record|add)\b(?:\s+(?:this|that|it))?(?:\s+down)?\b.{{0,24}}\b(on|in|into|to)\b.{{0,12}}\b{_PAD}\b"
	rf"|\b{_PAD}\b.{{0,6}}\b(note|write down|jot down)\b", re.IGNORECASE)
_ADD = re.compile(
	rf"\badd\b.{{1,80}}\b(to|on)\b\s+(?:the |my )?(?:to-?do|list|steps?)\b.{{0,30}}\b{_PAD}\b"
	rf"|\badd (?:a |an |another )?(?:step|thing to do|to-?do( item)?)\b", re.IGNORECASE)
_SHOW = re.compile(
	rf"\b(read|show|tell me|say|what('s| is| are)?( on| in)?|go through|look at|list)\b.{{0,24}}\b{_PAD}\b", re.IGNORECASE)
_LIST = re.compile(rf"\b(which|what|list|how many|all)\b.{{0,24}}\b{_PAD.replace('s?', 's')}\b|\bscratch ?pads (do|have)\b",
	re.IGNORECASE)
_SEARCH = re.compile(
	rf"\b(what|which|where|when|who|how|is there|are there|did you|do you|have you|anything)\b.{{0,60}}\b(on|in|from)\b"
	rf".{{0,12}}\b{_PAD}\b.{{0,8}}\b(about|for|on)\b|\b(according to|from|on|in)\b (?:the |my |your )?{_PAD}\b.{{0,8}},"
	rf"|\b(search|look (up|for|through)|find)\b.{{0,40}}\b{_PAD}\b", re.IGNORECASE)
_CHECK = re.compile(
	r"\b(check|tick|cross|mark)\b(.{0,60})\b(off|done|finished|complete|completed)\b|\b(i('ve| have)|that's|that is|i am|i'm)"
	r" (done|finished)( with)?\b|\bmark\b.{0,40}\bas (done|finished|complete)\b", re.IGNORECASE)
_NEXT = re.compile(
	r"\bwhat('s| is) next\b|\bwhere was i\b|\bwhere (did|do) (i|we) (leave|stop|get to)\b|\bwhat (do|should) i do next\b"
	r"|\b(the |my )?next (step|thing to do)\b|\bwhat('s| is) left\b|\bwhat (have i|is still) (left|to do)\b",
	re.IGNORECASE)
_FINISH = re.compile(
	rf"\b(finish|close|end|complete|stop)\b.{{0,30}}\b{_PAD}\b|\b(the|my|this) task is (done|finished|complete)\b"
	rf"|\b(i'm|i am|we're|we are) done with (the|this|my) task\b", re.IGNORECASE)
_DELETE = re.compile(rf"\b(delete|remove|erase|clear|forget|empty|wipe|throw away|get rid of)\b.{{0,50}}\b{_PAD}\b",
	re.IGNORECASE)
_OPEN = re.compile(rf"\bopen\b.{{0,12}}\b(my |the |this |your )?{_PAD}\b(?!\s*(for|about|called|named))"
	rf"|\b{_PAD} (file|folder)\b", re.IGNORECASE)
# Which scratchpad the words mean: the one for the program in front, the descriptions, all, the finished tasks.
_ABOUT_HERE = re.compile(rf"\b{_PAD}\b.{{0,30}}\b(for|of|about) (this|the current) (program|app|application|game|"
	r"web ?site|site|page)\b|\b(this|the current) (program|app|application|game|web ?site|site)'?s? " + _PAD, re.IGNORECASE)
_ABOUT_DESCRIPTIONS = re.compile(rf"\b(descriptions?|pictures?|photos?|images?)\b.{{0,20}}\b{_PAD}\b|\b{_PAD}\b.{{0,20}}"
	r"\b(of|for|with) (the )?(descriptions?|pictures?|photos?)\b", re.IGNORECASE)
_ABOUT_ALL = re.compile(rf"\ball\b.{{0,20}}\b{_PAD}\b|\b{_PAD}\b.{{0,12}}\ball\b|\bevery {_PAD}\b", re.IGNORECASE)
_ABOUT_FINISHED = re.compile(r"\b(finished|old|closed|done)\b.{0,20}\b(tasks?|" + _PAD + r")\b", re.IGNORECASE)
# A question about scratchpads themselves, answered from VisionClaw's own notes (claw/knowledge/visionclaw-scratchpad.md).
_ABOUT_FEATURE = re.compile(
	rf"^\W*(how (do|can|could|should|would|does) (i|you|we|visionclaw)\b|what (is|are) (a |an )?{_PAD}\b"
	rf"|what does (a |the )?{_PAD} do\b|(explain|tell me about) (the |a |your )?{_PAD}s?\b|why\b)", re.IGNORECASE)
# A question that points back at what VisionClaw described, saw or said before: asked of the descriptions scratchpad.
POINTS_BACK = re.compile(
	r"\b(you|visionclaw) (just )?(described|saw|looked at)\b"
	r"|\b(the|that|your|last|earlier|previous|first|second) (description|screenshot)\b"
	r"|\b(picture|photo|image|chart|graph|map|screen|drawing|equation|diagram) (you|visionclaw) (just )?(described|saw|"
	r"looked at|read out|showed me)\b|\bin the description\b", re.IGNORECASE)
_QUESTION = re.compile(r"^\W*(what|which|who|whose|where|when|why|how|is|are|was|were|did|does|do|can|could|tell me)\b",
	re.IGNORECASE)
_NUMBERS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
	"ninth": 9, "tenth": 10, "last": -1}
_NUMBER = re.compile(r"\b(?:step|item|number|thing|line)\s+(\d{1,2})\b|\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:step|item|one|thing)\b"
	r"|\bthe (first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last)\b", re.IGNORECASE)
_ITEMS_SPLIT = re.compile(r"\s*(?:;|,\s*(?:and\s+)?(?:then\s+)?|\bthen\b|\band then\b|\bafter that\b|\bnext\b)\s*", re.IGNORECASE)
# State the planner may ask, like partners.has: whether a task scratchpad is open, and whether descriptions are kept.
_state = {"task": False, "descriptions": False}


def setState(task=None, descriptions=None):
	if task is not None:
		_state["task"] = bool(task)
	if descriptions is not None:
		_state["descriptions"] = bool(descriptions)


def hasTask():
	return _state["task"]


def hasDescriptions():
	return _state["descriptions"]


def _clean(text):
	return " ".join(str(text or "").split()).strip(" .:;,-\"'")


def _after(pattern, text):
	"""What the user said after the words that only ask, or ""."""
	found = re.search(pattern, text, re.IGNORECASE)
	return _clean(text[found.end():]) if found else ""


def numberOf(text):
	"""Which item the words name by its number or place: 1 and up, -1 for the last, or None."""
	found = _NUMBER.search(text or "")
	if not found:
		return None
	if found.group(1) or found.group(2):
		return int(found.group(1) or found.group(2))
	return _NUMBERS.get(found.group(3).lower())


def items(text):
	"""Things to do, as the user listed them: "install it, set the volume, then learn the keys"."""
	parts = [_clean(part) for part in _ITEMS_SPLIT.split(text or "")]
	return [part for part in parts if len(part) >= 3][:MAX_TODO]


def _which(text):
	if _ABOUT_DESCRIPTIONS.search(text):
		return DESCRIBED
	if _ABOUT_HERE.search(text):
		return LEARNING
	if _ABOUT_ALL.search(text):
		return "all"
	if _ABOUT_FINISHED.search(text):
		return FINISHED
	return TASK


def wish(text):
	"""What the user's own words ask of a scratchpad, or None where they ask nothing of one. A dictionary: do (START,
	NOTE, ADD, SHOW, SEARCH, CHECK, NEXT, FINISH, DELETE, LIST, OPEN_FILE), pad (TASK, LEARNING, DESCRIBED, "all" or
	FINISHED), and what goes with it: title, items, text, number, query. Kept narrow: without the word scratchpad only
	"what's next", "where was I" and checking off, and only while a task scratchpad is open; and a question that points
	back at a description, only while descriptions are kept."""
	said = " ".join(str(text or "").split())
	low = said.lower()
	if not said:
		return None
	named = bool(_PAD_WORDS.search(low))
	if named and _ABOUT_FEATURE.search(low):
		# "How do I start a scratchpad", "what is a scratchpad": a question about VisionClaw, looked up in its own notes.
		return None
	if named:
		pad = _which(low)
		if _DELETE.search(low):
			return {"do": DELETE, "pad": pad}
		if _QUESTION.search(low) and _SEARCH.search(low):
			return {"do": SEARCH, "pad": pad, "query": _query(said)}
		if _START.search(low) and not _QUESTION.search(low):
			found = _TITLE.search(said)
			title, _colon, listed = (found.group(1) if found else "").partition(":")
			found = items(listed)
			return {"do": START, "pad": TASK, "title": _clean(title)[:80], "items": found}
		if _FINISH.search(low):
			return {"do": FINISH, "pad": TASK}
		if _ADD.search(low):
			thing = re.sub(rf"^\W*(?:please\s+)?add\s+|\s+(?:to|on)\s+(?:the |my )?(?:to-?do|list|steps?).*$", "", said,
				flags=re.IGNORECASE)
			return {"do": ADD, "pad": TASK, "items": items(thing) or [_clean(thing)]}
		if _NOTE.search(low):
			what = _after(r"\b(that|saying|:)\s*", said[_NOTE.search(low).end():]) or _clean(
				re.sub(_NOTE.pattern, "", said, flags=re.IGNORECASE))
			what = re.sub(rf"^\W*(?:that|this|it)\b\s*", "", what, flags=re.IGNORECASE)
			return {"do": NOTE, "pad": pad if pad in (LEARNING,) else TASK, "text": _clean(what)} if what else None
		if _CHECK.search(low) and hasTask():
			return {"do": CHECK, "pad": TASK, "number": numberOf(low), "text": _checkWords(said)}
		if _LIST.search(low):
			return {"do": LIST, "pad": "all"}
		if _SEARCH.search(low):
			return {"do": SEARCH, "pad": pad, "query": _query(said)}
		if _OPEN.search(low):
			return {"do": OPEN_FILE, "pad": pad}
		if _SHOW.search(low) or _NEXT.search(low):
			return {"do": NEXT if _NEXT.search(low) else SHOW, "pad": pad}
		if _QUESTION.search(low):
			return {"do": SEARCH, "pad": pad, "query": _query(said)}
		return {"do": SHOW, "pad": pad}
	if hasTask():
		if _NEXT.search(low):
			return {"do": NEXT, "pad": TASK}
		if _FINISH.search(low):
			return {"do": FINISH, "pad": TASK}
		if _CHECK.search(low) and re.search(r"\b(step|item|thing|to-?do|that|it|one|first|second|third|last)\b", low):
			return {"do": CHECK, "pad": TASK, "number": numberOf(low), "text": _checkWords(said)}
	if hasDescriptions() and POINTS_BACK.search(low) and _QUESTION.search(low):
		return {"do": SEARCH, "pad": DESCRIBED, "query": _query(said)}
	return None


def _checkWords(said):
	"""The words of a request to check something off that say which thing it is."""
	return _clean(re.sub(
		r"\b(please|check|tick|cross|mark|off|as|done|finished|complete|completed|on|the|my|scratch[ -]?pads?|i've|i have|"
		r"that's|that is|i am|i'm|with|step|item|thing|number|to-?do|list|first|second|third|last|\d+)\b",
		" ", said, flags=re.IGNORECASE))


def _query(said):
	"""What a question asks the scratchpads, without the words that name them."""
	text = re.sub(rf"\b(on|in|from|of|according to)\s+(the |my |your )?{_PAD}\b|\b{_PAD}\b", " ", said, flags=re.IGNORECASE)
	return _clean(text)


def pointsBack(text):
	return bool(POINTS_BACK.search(str(text or "")))


def asks(part):
	"""For the planner: whether the words ask something of a scratchpad that is not a question to answer from it."""
	found = wish(part)
	return found is not None and found["do"] != SEARCH


def asksFrom(part):
	"""For the planner: whether the words ask a question to be answered from the scratchpads."""
	found = wish(part)
	return found is not None and found["do"] == SEARCH


# --- Lines and passages ---

def topicsOf(text, program=""):
	"""The topics a text is about, by its words and by the program it is from."""
	both = f"{text or ''} {program or ''}"
	return {name for name, pattern in _TOPICS if pattern.search(both)}


class Note:
	"""One line of a scratchpad. by: who wrote it; program: where it was written; source: what it was made from."""

	__slots__ = ("text", "by", "program", "source", "topics", "when", "pad")

	def __init__(self, text, by=BY_YOU, program="", source="", topics=None, when=None):
		# The line keeps its own full stop; only spaces and a list mark are taken off.
		self.text = " ".join(str(text or "").split()).strip(" -*")
		self.by = by
		self.program = _clean(program)
		self.source = _clean(source)
		self.topics = set(topics) if topics is not None else topicsOf(self.text, self.program)
		self.when = when if when is not None else time.time()
		# Which scratchpad it is on, as (kind, title), once it is found there (Pad.lines).
		self.pad = ("", "")

	def line(self):
		"""The line as it is written in the file: the note, then who wrote it, where, about what and when."""
		said = [f"by {self.by}"]
		if self.program:
			said.append(f"in {self.program}")
		if self.source:
			said.append(f"from {self.source}")
		if self.topics:
			said.append("about " + ", ".join(sorted(self.topics)))
		said.append(time.strftime("%Y-%m-%d %H:%M", time.localtime(self.when)))
		return f"- {self.text} ({'; '.join(said)})"


_LINE = re.compile(r"^\s*[-*]\s+(.*?)\s*(?:\((by [^()]*)\))?\s*$")
_TODO = re.compile(r"^\s*(?:\d+[.)]|[-*])\s*\[( |x|X)\]\s*(.+?)\s*$")
_WHEN = re.compile(r"\b(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\b")


def parseNote(raw):
	"""A line of a file back into a Note. A line the user wrote by hand, without what follows it, is the user's."""
	found = _LINE.match(raw or "")
	if not found or not found.group(1).strip():
		return None
	text, said = found.group(1), found.group(2) or ""
	if not said:
		return Note(text, BY_YOU)
	by, program, source, topics, when = BY_YOU, "", "", set(), None
	for piece in said.split(";"):
		piece = piece.strip()
		if piece.startswith("by "):
			by = piece[3:]
		elif piece.startswith("in "):
			program = piece[3:]
		elif piece.startswith("from "):
			source = piece[5:]
		elif piece.startswith("about "):
			topics = {t.strip() for t in piece[6:].split(",") if t.strip()}
		elif _WHEN.search(piece):
			try:
				when = time.mktime(time.strptime(_WHEN.search(piece).group(1), "%Y-%m-%d %H:%M"))
			except (ValueError, OverflowError):
				when = None
	return Note(text, by, program, source, topics or None, when)


def passages(text, size=PASSAGE_CHARS):
	"""A result split into passages of about size characters, each whole: lines are joined, and a long line is split
	at the ends of its sentences. Nothing is lost: the passages together are the text."""
	found, now = [], ""
	for line in str(text or "").splitlines():
		line = " ".join(line.split())
		if not line:
			if now:
				found.append(now)
				now = ""
			continue
		pieces = [line] if len(line) <= size else re.split(r"(?<=[.!?;])\s+", line)
		for piece in pieces:
			if now and len(now) + len(piece) + 1 > size:
				found.append(now)
				now = ""
			now = f"{now} {piece}".strip()
	if now:
		found.append(now)
	return found


def rank(query, notes, program="", limit=FED_NOTES):
	"""The notes about a question or a step, the best first, at most limit. A note must share a telling word with the
	question; one from another program, or one that shares no topic with the question, must cover enough of it. BM25
	over words, half again over concepts (claw/concepts.py), and the topics and the program besides."""
	notes = [note for note in notes if note.text]
	# Words that only ask ("what did you write about") say nothing of what is meant.
	asked = (words(query) - _ASKS) or words(query)
	if not notes or not asked:
		return []
	texts = [note.text for note in notes]
	plain = bm25(query, texts)
	wide = bm25(concepts.text(concepts.tokens(query)), [concepts.text(concepts.tokens(t)) for t in texts])
	wanted = topicsOf(query)
	here = _clean(program).lower()
	scored = []
	for at, note in enumerate(notes):
		shared = asked & words(note.text)
		if not shared:
			continue
		sameProgram = bool(here) and note.program.lower() == here
		sameTopic = bool((wanted & note.topics) - BROAD)
		cover = len(shared) / len(asked)
		# A line learned in another program fits only by a topic of its own that the question shares, and its words.
		if here and note.program and not sameProgram and not (sameTopic and cover >= COVER):
			continue
		if not sameTopic and cover < COVER:
			continue
		score = plain[at] + 0.5 * wide[at] + TOPIC_WEIGHT * len(wanted & note.topics) + (PROGRAM_WEIGHT if sameProgram else 0)
		scored.append((score, note.when, at))
	scored.sort(key=lambda entry: (-round(entry[0], 6), -entry[1]))
	best = scored[0][0] if scored else 0
	return [notes[at] for score, _when, at in scored[:limit] if score >= RELATIVE * best]


def relevantText(result, query, chars):
	"""What a step is given of a long result: the whole of it where it fits; else its first passage, which says what it
	is, and then the passages that are about the step, in their own order, as many as fit. For what a model reads."""
	result = str(result or "").strip()
	if len(result) <= chars:
		return result
	pieces = passages(result)
	if len(pieces) < 3:
		return clip(result, chars)
	scores = bm25(query, pieces[1:])
	order = sorted(range(len(scores)), key=lambda at: (-scores[at], at))
	chosen, used = {0}, len(pieces[0])
	for at in order:
		if scores[at] <= 0:
			break
		if used + len(pieces[at + 1]) + 1 > chars:
			continue
		chosen.add(at + 1)
		used += len(pieces[at + 1]) + 1
	if len(chosen) == 1:
		return clip(result, chars)
	shown = " ".join(pieces[at] for at in sorted(chosen))
	left = len(pieces) - len(chosen)
	return f"{shown} (The parts about this step; {left} other parts of this result are on the scratchpad.)"


# --- What a model writes down, and what plain code keeps ---

KEEP_SYSTEM = (
	IDENTITY + " You keep a scratchpad while a task is carried out in small steps. From what one step found, you write "
	"down the one fact the next step needs, in one short sentence.\n"
	"Rules: Copy names, numbers and keys exactly as they are written in what was found. Write only what it says. "
	"If nothing in it is needed, write none.")
KEEP_SCHEMA = {
	"type": "object",
	"properties": {"note": {"type": "string", "maxLength": NOTE_CHARS}},
	"required": ["note"],
}
KEEP_TOKENS = 90
_NONE = re.compile(r"^\W*(none|nothing|no fact|n/?a|no note|not needed)\W*$", re.IGNORECASE)


def keepQuestion(request, step, nextTitle, result):
	"""The question to the model that writes down what a step found, for the step after it."""
	return (
		f"The user asked: \"{uncut(request)}\"\n"
		f"This step was: {step}.\n"
		f"What it found:\n{relevantText(result, f'{request} {nextTitle}', 1400)}\n"
		f"The next step is: {nextTitle}.\n"
		"Write down the one fact the next step needs.")


# Words that only frame a fact ("item 80 of the list"): they need not be in what the line was made from.
_FRAME = words("item items list listed step steps called named name number found result results next shown says said "
	"there here which first last line lines place places")
_NUMBER_IN = re.compile(r"\d+(?:[.,:]\d+)*")
_QUOTED = re.compile("[\"\u201c]([^\"\u201d]{2,60})[\"\u201d]")


def checkedNote(note, *sources):
	"""A line a model wrote, if it stands in what it was made from: every key, number and quoted name it has is there,
	and most of its other telling words. None otherwise. A line that only says there is nothing is no line."""
	text = " ".join(str(note or "").split()).strip(" -*")
	if not text or _NONE.match(text) or len(text) > NOTE_CHARS + 20 or len(text) < 8:
		return None
	body = "\n".join(str(source or "") for source in sources)
	low = body.lower()
	# A line copied word for word from what was found stands in it.
	if " ".join(text.lower().split()) in " ".join(low.split()):
		return text
	if not _keysIn(text) <= _keysIn(body):
		return None
	if not set(_NUMBER_IN.findall(text)) <= set(_NUMBER_IN.findall(body)):
		return None
	if any(quoted.lower() not in low for quoted in _QUOTED.findall(text)):
		return None
	mine = words(text) - _FRAME
	if not mine or len(mine & words(body)) / len(mine) < 0.6:
		return None
	return text


# --- A scratchpad as a Markdown file ---

class Pad:
	"""One scratchpad. kind: TASK, LEARNING, DESCRIBED or REQUEST. todo: [[text, done]]; notes: [Note]; done: [Note] of
	what was done (task scratchpads); descriptions: [(when, what, text, program, [(question, answer)])]."""

	def __init__(self, kind, title="", goal="", path=None, clock=time.time):
		self.kind = kind
		self.title = _clean(title)
		self.goal = _clean(goal)
		self.path = path
		self.status = OPEN
		self.created = self.changed = clock()
		self.todo = []
		self.notes = []
		self.done = []
		self.descriptions = []
		self._clock = clock

	# What is on it.

	def nextItem(self):
		"""The number and text of the first thing still to do, or (None, "")."""
		for number, (text, done) in enumerate(self.todo, 1):
			if not done:
				return number, text
		return None, ""

	def add(self, note, limit=MAX_NOTES):
		"""A line written on the scratchpad. A line about the same thing takes the place of the older one. Returns
		whether one was replaced."""
		replaced = False
		for at, old in enumerate(self.notes):
			if old.text.lower() == note.text.lower() or (alike(old.text, note.text) >= SAME and old.program == note.program):
				del self.notes[at]
				replaced = True
				break
		self.notes.append(note)
		del self.notes[:-limit]
		self.changed = self._clock()
		return replaced

	def lines(self):
		"""Everything on the scratchpad that a question may be answered from, as notes that know which scratchpad they
		are on."""
		found = list(self.notes)
		for text, done in self.todo:
			found.append(Note(f"{'Done' if done else 'To do'}: {text}", BY_YOU, topics=topicsOf(text)))
		found += self.done
		for when, what, text, program, asked in self.descriptions:
			found.append(Note(f"Described {what}: {text}", BY_MODEL, program, when=when))
			for question, answer in asked:
				found.append(Note(f"Asked about {what}: {question} Answer: {answer}", BY_MODEL, program, when=when))
		for note in found:
			note.pad = (self.kind, self.title)
		return found

	def text(self):
		"""The scratchpad as Markdown, for the user to read and for the models to read again."""
		head = {
			TASK: f"# Task scratchpad: {self.title or 'a task'}",
			LEARNING: f"# What VisionClaw learned in {self.title}",
			DESCRIBED: "# Descriptions scratchpad",
			REQUEST: "# Scratchpad of this request",
		}[self.kind]
		about = {
			TASK: "VisionClaw's scratchpad for a task you work on over several requests. While it is open, VisionClaw and "
				"its models read it with every request, and write down what was done. You may change or delete anything in it.",
			LEARNING: "What VisionClaw and its models found out while working here, written down so that they can use it "
				"the next time. Each line says who wrote it, what it is about and when. You may change or delete any line.",
			DESCRIBED: "The last descriptions of the screen and of pictures, and the questions answered about them, newest "
				"first. A question about something described before is answered from here. You may delete it at any time.",
			REQUEST: "What the models wrote down while working on this request.",
		}[self.kind]
		lines = [head, "", about, ""]
		if self.kind == TASK:
			lines.append(f"Status: {self.status}.")
			lines.append(f"Started: {time.strftime('%Y-%m-%d %H:%M', time.localtime(self.created))}.")
			if self.goal:
				lines.append(f"Goal: {self.goal}")
			lines += ["", "## To do", ""]
			lines += [f"{number}. [{'x' if done else ' '}] {text}" for number, (text, done) in enumerate(self.todo, 1)] or [
				"Nothing yet. Say: add, then what to do, to the scratchpad."]
		if self.kind != DESCRIBED:
			lines += ["", "## Notes", ""]
			lines += [note.line() for note in self.notes] or ["Nothing yet."]
		if self.kind == TASK:
			lines += ["", "## Done so far", ""]
			lines += [note.line() for note in self.done] or ["Nothing yet."]
		if self.kind == DESCRIBED:
			for when, what, text, program, asked in self.descriptions:
				stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(when))
				lines += ["", f"## {what[:1].upper()}{what[1:]}, {stamp}" + (f", in {program}" if program else ""), "", text]
				for question, answer in asked:
					lines += ["", f"Question: {question}", f"Answer: {answer}"]
		return "\n".join(lines).rstrip() + "\n"

	@classmethod
	def parse(cls, text, kind, path=None, clock=time.time):
		"""A scratchpad read back from its file, with whatever the user changed in it."""
		pad = cls(kind, path=path, clock=clock)
		section = ""
		description = None
		for raw in str(text or "").splitlines():
			line = raw.rstrip()
			if line.startswith("# "):
				title = line[2:]
				if kind == TASK and ":" in title:
					pad.title = _clean(title.split(":", 1)[1])
				elif kind == LEARNING and title.startswith("What VisionClaw learned in "):
					pad.title = _clean(title[len("What VisionClaw learned in "):])
				continue
			if line.startswith("## "):
				section = line[3:].strip().lower()
				if kind == DESCRIBED:
					head = line[3:]
					found = re.match(r"(.*?), (\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?:, in (.*))?$", head)
					when = clock()
					if found:
						try:
							when = time.mktime(time.strptime(found.group(2), "%Y-%m-%d %H:%M"))
						except (ValueError, OverflowError):
							pass
					description = [when, _clean(found.group(1) if found else head).lower(), "", _clean(found.group(3) if found else ""), []]
					pad.descriptions.append(description)
				continue
			if kind == TASK and not section:
				if line.lower().startswith("status:"):
					pad.status = FINISHED if "finish" in line.lower() else OPEN
				elif line.lower().startswith("goal:"):
					pad.goal = _clean(line[5:])
				elif line.lower().startswith("started:"):
					found = _WHEN.search(line)
					if found:
						try:
							pad.created = time.mktime(time.strptime(found.group(1), "%Y-%m-%d %H:%M"))
						except (ValueError, OverflowError):
							pass
				continue
			if kind == DESCRIBED and description is not None:
				if line.startswith("Question: "):
					description[4].append([line[len("Question: "):].strip(), ""])
				elif line.startswith("Answer: ") and description[4]:
					description[4][-1][1] = line[len("Answer: "):].strip()
				elif line.strip():
					description[2] = f"{description[2]} {line.strip()}".strip()
				continue
			if section == "to do":
				found = _TODO.match(line)
				if found:
					pad.todo.append([_clean(found.group(2)), found.group(1).lower() == "x"])
			elif section in ("notes", "done so far"):
				if line.strip().lower() in ("nothing yet.", ""):
					continue
				note = parseNote(line)
				if note is not None:
					(pad.notes if section == "notes" else pad.done).append(note)
		pad.descriptions = [tuple([d[0], d[1], d[2], d[3], [tuple(pair) for pair in d[4]]]) for d in pad.descriptions]
		return pad


def slug(name):
	"""A file name made of a program's or a task's name."""
	made = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
	return (made or "scratchpad")[:60]


class Pads:
	"""Every lasting scratchpad, in folder (the folder "scratchpads" of VisionClaw's data): task scratchpads, the
	learning scratchpads of programs and websites, and the descriptions. Each is read again from its file when the
	file changed, so what the user wrote into it counts. Nothing here raises to its caller for a file that cannot be
	written: the work goes on, and the log says why."""

	def __init__(self, folder, clock=time.time):
		self.folder = folder
		self._clock = clock
		self._lock = threading.RLock()
		self._cache = {}
		self.refresh()

	# Files.

	def _path(self, kind, name=""):
		if kind == DESCRIBED:
			return os.path.join(self.folder, DESCRIPTIONS_FILE)
		return os.path.join(self.folder, TASKS if kind == TASK else LEARNED, f"{slug(name)}.md")

	def _read(self, path, kind):
		try:
			stamp = os.path.getmtime(path)
		except OSError:
			self._cache.pop(path, None)
			return None
		cached = self._cache.get(path)
		if cached is not None and cached[0] == stamp:
			return cached[1]
		try:
			with open(path, encoding="utf-8") as f:
				pad = Pad.parse(f.read(), kind, path, self._clock)
		except (OSError, UnicodeDecodeError) as e:
			debuglog.error("scratchpad", f"A scratchpad could not be read: {path}", e)
			return None
		# When it was changed last is when its file was: the user may have written into it.
		pad.changed = stamp
		self._cache[path] = (stamp, pad)
		return pad

	def _write(self, pad):
		if not pad.path:
			return
		try:
			os.makedirs(os.path.dirname(pad.path), exist_ok=True)
			temporary = pad.path + ".new"
			with open(temporary, "w", encoding="utf-8", newline="\n") as f:
				f.write(pad.text())
			os.replace(temporary, pad.path)
			self._cache[pad.path] = (os.path.getmtime(pad.path), pad)
		except OSError as e:
			debuglog.error("scratchpad", f"A scratchpad could not be written: {pad.path}", e)
		self._index()

	def _all(self, kind):
		folder = os.path.join(self.folder, TASKS if kind == TASK else LEARNED)
		try:
			names = sorted(name for name in os.listdir(folder) if name.endswith(".md"))
		except OSError:
			return []
		return [pad for pad in (self._read(os.path.join(folder, name), kind) for name in names) if pad is not None]

	def refresh(self):
		"""Tell the planner whether a task scratchpad is open and whether descriptions are kept (setState)."""
		with self._lock:
			setState(task=self.active() is not None, descriptions=bool(self.descriptions().descriptions))

	def _index(self):
		"""SCRATCHPADS.md: one line for each scratchpad, made from the files, for the user to find them."""
		try:
			lines = ["# VisionClaw's scratchpads", "",
				"Every scratchpad is a Markdown file in this folder. You may open, change or delete any of them.", ""]
			for pad in self._all(TASK):
				lines.append(f"- Task: {pad.title} ({pad.status}), {os.path.join(TASKS, os.path.basename(pad.path))}")
			for pad in self._all(LEARNING):
				lines.append(f"- What was learned in {pad.title}: {len(pad.notes)} lines, {os.path.join(LEARNED, os.path.basename(pad.path))}")
			if os.path.isfile(self._path(DESCRIBED)):
				lines.append(f"- Descriptions: {DESCRIPTIONS_FILE}")
			os.makedirs(self.folder, exist_ok=True)
			with open(os.path.join(self.folder, INDEX), "w", encoding="utf-8", newline="\n") as f:
				f.write("\n".join(lines) + "\n")
		except OSError as e:
			debuglog.error("scratchpad", "The list of scratchpads could not be written", e)

	# Task scratchpads.

	def active(self):
		"""The open task scratchpad, the one changed last, or None."""
		with self._lock:
			open_ = [pad for pad in self._all(TASK) if pad.status == OPEN]
			return max(open_, key=lambda pad: pad.changed) if open_ else None

	def start(self, title, goal="", todo=()):
		"""A new task scratchpad. One that was open is finished first. Returns (the new one, the one finished or None)."""
		with self._lock:
			before = self.active()
			if before is not None:
				before.status = FINISHED
				self._write(before)
			title = _clean(title) or time.strftime("task of %d %B %H:%M", time.localtime(self._clock()))
			path = self._path(TASK, title)
			number = 2
			while os.path.exists(path):
				path = self._path(TASK, f"{title} {number}")
				number += 1
			pad = Pad(TASK, title, goal, path, self._clock)
			pad.todo = [[text, False] for text in list(todo)[:MAX_TODO]]
			self._write(pad)
			self.refresh()
			return pad, before

	def save(self, pad):
		with self._lock:
			pad.changed = self._clock()
			self._write(pad)
			self.refresh()

	def finish(self):
		with self._lock:
			pad = self.active()
			if pad is not None:
				pad.status = FINISHED
				self.save(pad)
			return pad

	def record(self, request, outcome, program=""):
		"""What was done with a request while a task scratchpad is open: written into its "Done so far" by plain code."""
		with self._lock:
			pad = self.active()
			if pad is None:
				return None
			pad.done.append(Note(f"\"{uncut(request)}\": {outcome}", BY_VISIONCLAW, program))
			del pad.done[:-MAX_DONE]
			self.save(pad)
			return pad

	# Learning scratchpads.

	def learning(self, program):
		"""The learning scratchpad of a program or website, read from its file, or a new one that is not written yet."""
		program = _clean(program)
		if not program:
			return None
		with self._lock:
			path = self._path(LEARNING, program)
			return self._read(path, LEARNING) or Pad(LEARNING, program, path=path, clock=self._clock)

	def learn(self, program, text, by, source=""):
		"""A line written on a program's learning scratchpad. Returns the Note, or None without a program."""
		pad = self.learning(program)
		if pad is None:
			return None
		with self._lock:
			note = Note(text, by, program, source)
			pad.add(note)
			self._write(pad)
			return note

	# Descriptions.

	def descriptions(self):
		with self._lock:
			return self._read(self._path(DESCRIBED), DESCRIBED) or Pad(DESCRIBED, path=self._path(DESCRIBED), clock=self._clock)

	def describe(self, what, text, program=""):
		"""A description, written first; the oldest go when there are more than MAX_DESCRIPTIONS."""
		text = " ".join(str(text or "").split())
		if not text:
			return
		with self._lock:
			pad = self.descriptions()
			pad.descriptions.insert(0, (self._clock(), _clean(what) or "the picture", text, _clean(program), []))
			del pad.descriptions[MAX_DESCRIPTIONS:]
			pad.changed = self._clock()
			self._write(pad)
			self.refresh()

	def answered(self, question, answer):
		"""A question answered about the last description."""
		with self._lock:
			pad = self.descriptions()
			if not pad.descriptions or not str(answer or "").strip():
				return
			when, what, text, program, asked = pad.descriptions[0]
			pad.descriptions[0] = (when, what, text, program, list(asked) + [(_clean(question), " ".join(str(answer).split()))])
			self._write(pad)

	# Finding again.

	def notesFor(self, query, program="", limit=FED_NOTES, kinds=(TASK, LEARNING)):
		"""The lines of the lasting scratchpads about a question or a step, the best first: the open task's, the program's
		own, and lines learned elsewhere that share a topic with the question."""
		with self._lock:
			found = []
			if TASK in kinds:
				pad = self.active()
				if pad is not None:
					found += pad.lines()
			if LEARNING in kinds:
				for pad in self._all(LEARNING):
					found += pad.lines()
			if DESCRIBED in kinds:
				found += self.descriptions().lines()
			return rank(query, found, program, limit)

	def contextText(self, request, program=""):
		"""What the model that chooses is told of the scratchpads: the open task, what is next on it, and the few lines
		that are about the request. "" when nothing is."""
		parts = []
		pad = self.active()
		if pad is not None:
			number, text = pad.nextItem()
			parts.append(f"The user is working on a task with a scratchpad: \"{pad.title}\"."
				+ (f" Next on it: {text}." if text else ""))
		lines = self.notesFor(request, program, CONTEXT_NOTES)
		if lines:
			parts.append("Written on VisionClaw's scratchpads before, which may help:\n" + "\n".join(f"- {note.text}" for note in lines))
		return "\n".join(parts)

	def search(self, query, program="", which=TASK, limit=6):
		"""The lines of the scratchpads that answer a question, with where each is from."""
		kinds = {TASK: (TASK, LEARNING, DESCRIBED), LEARNING: (LEARNING,), DESCRIBED: (DESCRIBED,)}.get(which, (TASK, LEARNING, DESCRIBED))
		return self.notesFor(query, program, limit, kinds)

	def everything(self):
		"""Every scratchpad there is: (kind, Pad)."""
		with self._lock:
			found = [(TASK, pad) for pad in self._all(TASK)] + [(LEARNING, pad) for pad in self._all(LEARNING)]
			described = self.descriptions()
			if described.descriptions:
				found.append((DESCRIBED, described))
			return found

	def delete(self, pad):
		"""A scratchpad's file removed. Returns whether it was there."""
		with self._lock:
			if not pad or not pad.path or not os.path.isfile(pad.path):
				return False
			try:
				os.remove(pad.path)
			except OSError as e:
				debuglog.error("scratchpad", f"A scratchpad could not be deleted: {pad.path}", e)
				return False
			self._cache.pop(pad.path, None)
			self._index()
			self.refresh()
			return True


# --- What the user is told ---

def noteSource(pad, note):
	"""Where a line is from, as the user is told it: by the scratchpad it is on."""
	kind, title = getattr(note, "pad", ("", "")) or ("", "")
	kind = pad or kind
	if kind == DESCRIBED:
		return "the descriptions scratchpad"
	if kind == LEARNING:
		return f"the scratchpad of what was learned in {title or note.program}"
	if kind == TASK:
		return f"your task scratchpad {title}".rstrip() if title else "your task scratchpad"
	return f"the scratchpad of what was learned in {note.program}" if note.program else "your task scratchpad"


def foundText(notes):
	"""Lines found on the scratchpads, each saying where it is from, for a model to answer from or to be said."""
	return "\n".join(f"From {noteSource(None, note)}: {note.text}" for note in notes)


def padText(pad):
	"""A scratchpad said in plain sentences: its title, what is next, what is on it."""
	if pad.kind == TASK:
		lines = [f"Your task scratchpad: {pad.title}." + (" It is finished." if pad.status == FINISHED else "")]
		if pad.goal:
			lines.append(f"Goal: {pad.goal}.")
		if pad.todo:
			lines.append("To do: " + "; ".join(
				f"{number}, {text}, {'done' if done else 'not done yet'}" for number, (text, done) in enumerate(pad.todo, 1)) + ".")
		else:
			lines.append("Nothing is on its list of things to do.")
		if pad.notes:
			lines.append("Notes: " + " ".join(f"{note.text.rstrip('.')}." for note in pad.notes))
		if pad.done:
			lines.append(f"Requests done for it: {len(pad.done)}. The last: {pad.done[-1].text}")
		return "\n".join(lines)
	if pad.kind == LEARNING:
		if not pad.notes:
			return f"Nothing has been learned in {pad.title} yet."
		return f"What was learned in {pad.title}, {len(pad.notes)} lines, the newest last:\n" + "\n".join(
			f"{note.text} (written by {note.by})" for note in pad.notes)
	if not pad.descriptions:
		return "The descriptions scratchpad is empty."
	return f"The last {len(pad.descriptions)} descriptions, the newest first:\n" + "\n".join(
		f"{what[:1].upper()}{what[1:]}, at {time.strftime('%H:%M', time.localtime(when))}: {text}"
		for when, what, text, _program, _asked in pad.descriptions)


def listText(found):
	"""Every scratchpad, one sentence each."""
	if not found:
		return "There are no scratchpads yet. To start one for a task, say: start a scratchpad for, then the task."
	lines = []
	for kind, pad in found:
		if kind == TASK:
			number, text = pad.nextItem()
			lines.append(f"Task scratchpad {pad.title}, {pad.status}" + (f", next: {text}" if text and pad.status == OPEN else "") + ".")
		elif kind == LEARNING:
			lines.append(f"What was learned in {pad.title}: {len(pad.notes)} lines.")
		else:
			lines.append(f"The descriptions scratchpad: {len(pad.descriptions)} descriptions.")
	return f"{len(found)} scratchpads:\n" + "\n".join(lines)


def nextText(pad):
	"""What is next on the open task, in a sentence."""
	if pad is None:
		return "No task scratchpad is open. To start one, say: start a scratchpad for, then the task."
	number, text = pad.nextItem()
	if number is None:
		return (f"Everything on the scratchpad {pad.title} is done." if pad.todo
			else f"Nothing is on the list of the scratchpad {pad.title}. To add something, say: add, then what to do, to the scratchpad.")
	left = sum(1 for _text, done in pad.todo if not done)
	return f"Next on {pad.title}: {number}, {text}. {left} of {len(pad.todo)} things are still to do."
