# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what the user told VisionClaw to remember, kept as Markdown files the user can read, change
# and delete, the way Claude keeps its memories: one file for each memory, with a few lines at its top that
# say what it is, and one index, MEMORY.md, with a line for each. A memory is kept only when it is needed:
# when the user asks for it, or, if the user allows it, when they say something lasting about themselves or
# about how they like things done and nothing else in the request keeps it. What is kept is the user's own
# words, turned from "I" to "you" by plain code; no model writes a memory. Memories are found again by their
# words, and those about the program in front when the user is in it.
# This is not claw/memory.py: that one keeps short lessons about what failed, for the models; these are the
# user's. No NVDA dependencies.

import os
import re
import threading
import time

from . import debuglog, ranking
from .llm import clip
from .memory import _COMMON, _WORD, stem

INDEX = "MEMORY.md"
# What a memory is about. The words are those the user hears.
YOU, LIKES, PROGRAM, WHERE = "you", "preference", "program", "reference"
KINDS = (YOU, LIKES, PROGRAM, WHERE)
KIND_NAMES = {
	YOU: "about you", LIKES: "how you like things done", PROGRAM: "about a program", WHERE: "where to find something"}
# When memories are kept: when the user asks or says something lasting, only when they ask, or never.
AUTO, ASKED, OFF = "auto", "asked", "off"
WHEN = (AUTO, ASKED, OFF)
MAX_MEMORIES = 200
MAX_CHARS = 500
# How many memories are given to the model with a request, at most, and how long all of them may be.
RECALLED = 4
RECALL_CHARS = 420
# A memory is given with a request only when it has at least this share of what the request names.
RECALL_COVER = 0.34
# A new memory replaces an old one that shares this much of its words.
SAME = 0.7

# The user asks for something to be kept.
_ASKS = re.compile(
	r"\b(remember|memori[sz]e|don'?t forget|do not forget|keep in mind|bear in mind|make a note|take a note|"
	r"note (down )?that|write (it )?down that|save (it )?as a memory|add (it |this |that )?to (your )?memor(y|ies))\b",
	re.IGNORECASE)
# The user asks what is kept.
_ASKS_WHAT = re.compile(
	r"\b(what|which|do|did|have|anything)\b.{0,20}\byou (remember|remembered|know about me|memori[sz]ed)\b"
	r"|\b(list|show|open|read)\b.{0,30}\bmemor(y|ies)\b", re.IGNORECASE)
# The user asks what is kept, or for it to go. Then nothing new is kept from the request.
_ABOUT_MEMORIES = re.compile(
	r"\b(forget|memories|memory|what do you (remember|know about me)|what have you remembered)\b", re.IGNORECASE)
# What the user says about themselves.
_ABOUT_SELF = re.compile(
	r"\b(my name is|my name's|call me|i am (blind|deaf|deafblind|deaf-blind|partially sighted|low vision|visually "
	r"impaired|new to|a beginner|left[- ]handed|right[- ]handed|learning)|i'm (blind|deaf|deafblind|deaf-blind|"
	r"partially sighted|low vision|visually impaired|new to|a beginner|left[- ]handed|right[- ]handed|learning)|"
	r"i (use|have|own) (a|an|the|my) [\w -]{0,30}(braille display|braille|keyboard|laptop|headphones|speakers|"
	r"screen|monitor|mouse|computer|phone|synthesi[sz]er|voice)|my (braille display|keyboard|laptop|computer|"
	r"synthesi[sz]er|first language|language|screen reader|voice) is|i speak\b)",
	re.IGNORECASE)
# How the user likes things done.
_LIKES = re.compile(
	r"\b(i prefer|i'd prefer|i would prefer|i like it when|i like it if|i don'?t like|i do not like|i hate|"
	r"i'd rather|i would rather|i want you to always|i want you to never|please always|please never|"
	r"always (ask|tell|say|speak|read|use|give|let|answer|show|explain)|never (ask|tell|say|speak|read|use|give|"
	r"let|answer|show|explain|change|touch)|from now on|in (the )?future|next time)\b",
	re.IGNORECASE)
# What a memory kept without being asked must be about: how this blind user works the computer. The owner asked
# on 2026-11-17 that prompts, memories and skills always be about how blind people use computers: speech and
# braille, keys and commands, NVDA and its settings and add-ons, programs and games and how to get through
# them, and how answers are to be worded. Whatever the user explicitly asks to be remembered is kept.
_COMPUTER = re.compile(
	r"\b(nvda|screen ?reader|narrator|jaws|speech|speak\w*|spoken|voice|voices|synth\w*|rate|pitch|volume|"
	r"punctuation|verbos\w*|beep\w*|sound\w*|braille|display|keys?|keyboard|shortcuts?|hot ?keys?|commands?|"
	r"press\w*|type|typing|mouse|click\w*|focus|read\w*|say|said|tell|announc\w*|answers?|describ\w*|"
	r"controllers?|game ?pads?|joysticks?|touch ?screens?|touch|pen|stylus|triggers?|"
	r"descriptions?|colou?rs?|picture\w*|screen|window|programs?|apps?|applications?|games?|browser|web|page|"
	r"site|email|mail|document|file|folder|add-?ons?|settings?|ask\w*|confirm\w*|delet\w*|chang\w*|"
	r"blind|deaf\w*|sight\w*|vision|low vision|magnif\w*|new to|beginner|learning|left[- ]handed|"
	r"right[- ]handed|language|english|short|long|detail\w*|slow\w*|fast\w*|step|steps)\b", re.IGNORECASE)
# Where something is: a folder, a file or an address.
_WHERE = re.compile(r"[a-z]:\\|\\\\|https?://|www\.|\b(folder|file|website|address|is at|are at|is in the|are in the)\b",
	re.IGNORECASE)
# About the program the user is in, or a game.
_THIS_PROGRAM = re.compile(
	r"\b(in |for )?(this|the current) (program|app|application|game|window|site|web ?site)\b|\b(in|for) here\b",
	re.IGNORECASE)
# Words at the start of a request that only ask for the memory to be kept.
_LEAD = re.compile(
	r"^\s*(?:(?:hey |ok |okay )?visionclaw[,:]?\s+)?(?:please\s+)?(?:can you\s+|could you\s+|would you\s+)?"
	r"(?:(?:remember|memori[sz]e|don'?t forget|do not forget|keep in mind|bear in mind|note(?: down)?|write down|"
	r"make a note|take a note|save (?:it )?as a memory)(?:\s+(?:of|this|that|for (?:me|later|next time)))*"
	r"\s*[:,]?\s*)+", re.IGNORECASE)
_TRAIL = re.compile(r"\s*[,;]?\s*(?:please|thanks|thank you|for (?:me|later|next time)|ok)\s*[.!?]*\s*$", re.IGNORECASE)
# "I" to "you", for saying a memory back. Longest first.
_PERSON = (
	("i am", "you are"), ("i'm", "you're"), ("i was", "you were"), ("i've", "you've"), ("i'd", "you'd"),
	("i'll", "you'll"), ("myself", "yourself"), ("mine", "yours"), ("my", "your"), ("me", "you"), ("i", "you"))
_PERSON_RE = re.compile(r"\b(" + "|".join(re.escape(first) for first, _second in _PERSON) + r")\b", re.IGNORECASE)
_SECOND = dict(_PERSON)
# "Forget that": the memory kept last.
_LAST = re.compile(r"\b(that|it|the last( one)?|what i (just )?said|the latest)\b", re.IGNORECASE)
_ALL = re.compile(r"\b(all|every ?thing|every memory|all (of )?(your|the|my) memories|everything you remember)\b",
	re.IGNORECASE)


def asksToRemember(text):
	"""Whether the user asks for something to be remembered."""
	return bool(_ASKS.search(text or "")) and not _ASKS_WHAT.search(text or "") and not re.search(r"\bforget\b(?! to)", re.sub(
		r"\b(don'?t|do not) forget\b", "", text or "", flags=re.IGNORECASE), re.IGNORECASE)


def lasting(text):
	"""The kind of a lasting thing the user says about themselves or how they like things done, or "" when they
	say none. "Speak faster from now on" is lasting too; whether it needs a memory is decided by what else the
	request did (`worthKeeping`)."""
	text = text or ""
	if _ABOUT_MEMORIES.search(text):
		return ""
	if _ABOUT_SELF.search(text):
		return YOU
	if _LIKES.search(text):
		return LIKES
	return ""


def factOf(said):
	"""What is to be remembered, in the user's own words: "remember that my display is a Focus 40, please"
	becomes "my display is a Focus 40"."""
	text = " ".join(str(said or "").split())
	text = _LEAD.sub("", text)
	text = re.sub(r"^(that|to)\s+", "", text, flags=re.IGNORECASE)
	text = _TRAIL.sub("", text).strip(" ,;:")
	# A question is asked, not remembered: of "I'm new to NVDA. How do I read the title?" the first is kept.
	sentences = [part for part in re.split(r"(?<=[.!?])\s+", text) if part]
	kept = [part for part in sentences if not part.rstrip().endswith("?")]
	if kept and len(kept) < len(sentences):
		text = " ".join(kept).strip(" .")
	return text[:MAX_CHARS]


# A fact that tells VisionClaw what to do, and is not about anything: it is said back as the user's request.
_TELLS = re.compile(
	r"\s*(always|never|please|do|don'?t|do not|ask|tell|say|speak|read|use|give|let|answer|show|explain|be|keep|"
	r"stop|start|when|whenever|if|from now on|next time|in (the )?future)\b", re.IGNORECASE)


def yours(fact):
	"""A fact said back to the user: "my display is a Focus 40" becomes "Your display is a Focus 40.", "call
	me Sam" becomes "You like to be called Sam.", and something VisionClaw is told to do is said as what the
	user asked."""
	fact = " ".join(str(fact or "").split()).strip(" ,;:")
	if not fact:
		return ""
	called = re.match(r"(?:please\s+)?call me\s+(.+?)[.!]?$", fact, re.IGNORECASE)
	if called:
		return f"You like to be called {called.group(1)}."
	if _TELLS.match(fact):
		return f"You asked: \"{fact.rstrip('.!')}\"."

	def turn(hit):
		word = hit.group(0)
		new = _SECOND[word.lower()]
		return new[0].upper() + new[1:] if word[0].isupper() and word.lower() != "i" else new
	text = _PERSON_RE.sub(turn, fact)
	text = re.sub(r"\byou am\b", "you are", text, flags=re.IGNORECASE)
	text = text[0].upper() + text[1:]
	return text if text[-1] in ".!?" else text + "."


def clause(request, kind):
	"""The part of a request that says the lasting thing: "I'm new to NVDA" of "I'm new to NVDA, how do I read
	the title?", and the whole sentence for how the user likes things done."""
	pattern = _ABOUT_SELF if kind == YOU else _LIKES
	for sentence in re.split(r"(?<=[.!?;])\s+", " ".join(str(request or "").split())):
		if not pattern.search(sentence):
			continue
		if kind == YOU:
			for piece in re.split(r",\s*|\s+(?:and|but|so)\s+(?=(?:how|what|which|where|why|can|could|would|will|"
					r"please|tell|read|say|open|turn|set|make)\b)", sentence):
				if pattern.search(piece):
					return piece.strip(" .!?")
		return sentence.strip(" .!?")
	return ""


def kindOf(fact, program=""):
	"""What a memory is about, from its words: a program, where to find something, the user, or how they like
	things done."""
	if program or _THIS_PROGRAM.search(fact or ""):
		return PROGRAM
	if _WHERE.search(fact or ""):
		return WHERE
	if _ABOUT_SELF.search(fact or "") or re.match(r"\s*(i am|i'm|my|i use|i have)\b", fact or "", re.IGNORECASE):
		return YOU
	return LIKES


def slug(text):
	words = re.findall(r"[a-z0-9]+", (text or "").lower())
	return "-".join(words[:7])[:60] or "memory"


def words(text):
	return {stem(word) for word in _WORD.findall((text or "").lower()) if word not in _COMMON}


def _subject(fact):
	"""What a fact is about, where it says "X is": "my braille display" in "my braille display is a Focus 40"."""
	hit = re.match(r"\s*(.{3,60}?)\s+(is|are|was|were)\b", (fact or "").lower())
	if not hit:
		return ""
	subject = " ".join(hit.group(1).split())
	return subject if len(words(subject)) >= 1 and subject not in ("it", "this", "that", "there") else ""


class Entry:
	"""One memory. name: its file name without .md. title: one line that says it. kind: one of KINDS.
	program: the program it is about, or "". saved: the day it was kept. body: what it says. asked: the user's
	own words."""

	__slots__ = ("name", "title", "kind", "program", "saved", "body", "asked", "time")

	def __init__(self, name, title, kind, program="", saved="", body="", asked="", time=0.0):
		self.name, self.title, self.kind, self.program = name, title, kind, program
		self.saved, self.body, self.asked, self.time = saved, body, asked, time

	def text(self):
		"""What the memory says, as one line."""
		said = self.title or clip(" ".join(self.body.split()), 200)
		return f"In {self.program}: {said}" if self.program and self.program.lower() not in said.lower() else said

	def markdown(self):
		lines = [
			"---", f"name: {self.name}", f"description: {self.title}", f"type: {self.kind}",
			f"program: {self.program}", f"saved: {self.saved}", "---", "", self.body.strip()]
		if self.asked:
			lines += ["", f"In your words: \"{self.asked}\""]
		return "\n".join(lines) + "\n"


def parse(name, text, modified=0.0):
	"""A memory from its file. A file the user wrote without the lines at the top is still a memory: its first
	line is its title."""
	text = (text or "").replace("\r\n", "\n")
	head, body = {}, text
	hit = re.match(r"\s*---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
	if hit:
		for line in hit.group(1).splitlines():
			key, _sep, value = line.partition(":")
			head[key.strip().lower()] = value.strip()
		body = hit.group(2)
	asked = ""
	said = re.search(r'^In your words: "(.*)"\s*$', body, re.MULTILINE)
	if said:
		asked = said.group(1)
		body = body[:said.start()] + body[said.end():]
	body = body.strip()
	title = head.get("description") or next((line.strip("# ").strip() for line in body.splitlines() if line.strip()), "")
	kind = head.get("type") if head.get("type") in KINDS else kindOf(body)
	return Entry(name, clip(title, 200), kind, head.get("program", ""), head.get("saved", ""), body, asked, modified)


class Memories:
	"""The memories in one folder."""

	def __init__(self, folder):
		self.folder = folder
		self._lock = threading.Lock()
		self._seen = None  # (names and times of the files when last read, entries)

	def path(self, name):
		return os.path.join(self.folder, name + ".md")

	def all(self):
		"""Every memory, the newest last. Read again whenever a file was added, changed or deleted, because the
		user may change them by hand."""
		try:
			names = sorted(name for name in os.listdir(self.folder) if name.endswith(".md") and name != INDEX)
			stamp = tuple((name, os.path.getmtime(os.path.join(self.folder, name))) for name in names)
		except OSError:
			return []
		with self._lock:
			if self._seen and self._seen[0] == stamp:
				return list(self._seen[1])
			found = []
			for name, modified in stamp:
				try:
					with open(os.path.join(self.folder, name), encoding="utf-8", errors="replace") as f:
						found.append(parse(name[:-3], f.read(), modified))
				except OSError as e:
					debuglog.error("memories", f"The memory {name} could not be read", e)
			found = [entry for entry in found if entry.title or entry.body]
			found.sort(key=lambda entry: entry.time)
			self._seen = (stamp, found)
			return list(found)

	def _write(self, entry):
		os.makedirs(self.folder, exist_ok=True)
		tmp = self.path(entry.name) + ".tmp"
		with open(tmp, "w", encoding="utf-8", newline="\n") as f:
			f.write(entry.markdown())
		os.replace(tmp, self.path(entry.name))

	def writeIndex(self):
		"""MEMORY.md: one line for each memory, for the user to read. It is made from the files, so it never
		says something the files do not."""
		kept = self.all()
		lines = [
			"# What VisionClaw remembers", "",
			"One line for each memory. Each memory is a file in this folder; open it to read or change it, or delete "
			"the file to make VisionClaw forget it. VisionClaw also deletes them when you ask it to forget.", ""]
		for kind in KINDS:
			mine = [entry for entry in kept if entry.kind == kind]
			if mine:
				lines += [f"## {KIND_NAMES[kind][0].upper()}{KIND_NAMES[kind][1:]}", ""]
				lines += [f"- [{entry.text()}]({entry.name}.md) (kept {entry.saved or 'earlier'})" for entry in mine]
				lines.append("")
		if not kept:
			lines.append("Nothing yet.")
		try:
			os.makedirs(self.folder, exist_ok=True)
			with open(os.path.join(self.folder, INDEX), "w", encoding="utf-8", newline="\n") as f:
				f.write("\n".join(lines).rstrip() + "\n")
		except OSError as e:
			debuglog.error("memories", "The index of memories could not be written", e)

	def add(self, fact, asked="", kind="", program="", today=None):
		"""Keep a memory. A memory about the same thing replaces the old one: "my braille display is a Focus 40"
		replaces "my braille display is a Brailliant". Returns (the entry, the entry it replaced or None)."""
		fact = " ".join(str(fact or "").split())[:MAX_CHARS]
		if len(words(fact)) < 1 or len(fact) < 4:
			raise ValueError("There is nothing to remember in those words.")
		kind = kind if kind in KINDS else kindOf(fact, program)
		if kind != PROGRAM:
			program = ""
		said = yours(fact)
		# Compared as they are said back, so that "remember that my display ..." and "my display ..." are alike.
		mine, subject = words(said), _subject(said)
		replaced = None
		for old in self.all():
			if (old.program or "").lower() != (program or "").lower():
				continue
			theirs = words(old.body)
			similar = mine and theirs and len(mine & theirs) / len(mine | theirs) >= SAME
			if similar or (subject and subject == _subject(old.body)):
				replaced = old
				break
		name = replaced.name if replaced else slug(said)
		if not replaced:
			taken = {entry.name for entry in self.all()}
			base, number = name, 2
			while name in taken or name.lower() == INDEX[:-3].lower():
				name, number = f"{base}-{number}", number + 1
		entry = Entry(
			name, clip(said, 200), kind, program, time.strftime("%Y-%m-%d", time.localtime(today)), said,
			" ".join(str(asked or "").split())[:MAX_CHARS], time.time())
		self._write(entry)
		kept = self.all()
		if len(kept) > MAX_MEMORIES:
			# The oldest go first; they are files the user can still find in the log of what was deleted.
			for old in kept[:len(kept) - MAX_MEMORIES]:
				self.remove(old.name)
		self.writeIndex()
		debuglog.log("memories", f"Kept the memory {name}: {said!r} ({kind}{', ' + program if program else ''})"
			+ (f", replacing {replaced.title!r}" if replaced else ""))
		return entry, replaced

	def remove(self, name):
		try:
			os.remove(self.path(name))
		except OSError as e:
			debuglog.error("memories", f"The memory {name} could not be deleted", e)
			return False
		debuglog.log("memories", f"Deleted the memory {name}")
		return True

	def find(self, said, limit=3, cover=0.0):
		"""The memories the user's words are about, best first."""
		kept = self.all()
		asked = words(said)
		if not kept or not asked:
			return []
		entries = [(words(entry.title + " " + entry.program), words(entry.body + " " + entry.asked)) for entry in kept]
		return [kept[index] for index in ranking.rank(asked, entries, limit, cover=cover)]

	def chosen(self, which):
		"""The memories a request to forget means: all of them, the last one kept, or those its words name."""
		kept = self.all()
		if not kept:
			return []
		rest = re.sub(r"\b(forget|delete|remove|erase|clear|memor(y|ies)|about|what|you|remember|please|the|"
			r"visionclaw|i (told|said|asked)|said|told)\b", " ", which or "", flags=re.IGNORECASE)
		if _ALL.search(which or ""):
			return kept
		named = self.find(rest)
		if named:
			return named[:1] if len(named) > 1 and _LAST.search(which or "") else named
		if _LAST.search(which or "") or not words(rest):
			return kept[-1:]
		return []

	def recall(self, request, program="", limit=RECALLED, chars=RECALL_CHARS):
		"""The memories that belong with a request, as lines for the model: those about the program the user is
		in, and those the request's words are about. Short, because small models are shown it."""
		kept = self.all()
		if not kept:
			return []
		chosen = []
		low = (program or "").lower()
		if low:
			chosen += [entry for entry in reversed(kept) if entry.program and entry.program.lower() == low][:2]
		chosen += [entry for entry in self.find(request, limit, cover=RECALL_COVER) if entry not in chosen]
		lines, used = [], 0
		for entry in chosen[:limit]:
			line = clip(entry.text(), 160)
			if used + len(line) > chars:
				break
			lines.append(line)
			used += len(line)
		return lines

	def listText(self):
		kept = self.all()
		if not kept:
			return "VisionClaw remembers nothing yet. Say remember, and what to remember, and it will."
		lines = [f"VisionClaw remembers {len(kept)} {'thing' if len(kept) == 1 else 'things'}:"]
		lines += [f"{entry.text()}" for entry in kept]
		return " ".join(lines[:1]) + "\n" + "\n".join(lines[1:])


def worthKeeping(request, when, steps, changes):
	"""What to keep from a request without being asked, or "": only when the user allows it, when they said
	something lasting about themselves or how they like things done, and when nothing else in the request
	keeps it already: a setting that was changed is kept by NVDA, and a memory the user asked for by the
	remember tool. steps: (tool, worked) of each step. changes(tool) says whether a tool changes something."""
	if when != AUTO or asksToRemember(request) or not lasting(request):
		return ""
	if any(tool == "remember" for tool, _worked in steps):
		return ""
	kind = lasting(request)
	if kind == LIKES and any(worked and changes(tool) for tool, worked in steps):
		return ""
	said = clause(request, kind)
	# Kept without being asked only when it is about how the user works the computer.
	return said if _COMPUTER.search(said) else ""


def asksWhat(text):
	"""Whether the user asks what VisionClaw remembers."""
	return bool(_ASKS_WHAT.search(text or ""))


__all__ = ["Memories", "Entry", "asksToRemember", "asksWhat", "lasting", "factOf", "yours", "clause", "kindOf", "worthKeeping"]
