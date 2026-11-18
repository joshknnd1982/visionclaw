# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - answering a question from everything that can be asked on this computer, in this order: NVDA
# (its commands and its user guide), the program in front, its window, and Windows itself. A question like
# "how can I use the keyboard to navigate my desktop" used to be put to NVDA's commands alone, and the command
# that shares the words "keyboard" and "desktop" was given as the answer. Here every source gives what it has
# as small passages, plain code ranks all of them together by what the question is about, and what is not
# about it is left out; when nothing is, plain code says so, because a small model cannot. No NVDA dependencies.

import html
import re

from . import commands, match, ranking
from .llm import clip
from .memory import _COMMON, _WORD, stem

NVDA, APP, WINDOW, SYSTEM = "nvda", "app", "window", "system"
# The order in which the sources are asked, and in which equally good answers are given.
ORDER = (NVDA, APP, WINDOW, SYSTEM)
ORIGINS = {NVDA: "NVDA", APP: "this program", WINDOW: "this window", SYSTEM: "Windows"}
TOOL = "look_up"
# Where each knowledge file belongs, and what it is called when an answer is taken from it. A file that is
# not listed is NVDA's.
NOTES = {
	"windows-keyboard": (SYSTEM, "Windows"),
	"userGuide": (NVDA, "NVDA's user guide"),
	"addons": (NVDA, "an add-on's help"),
	"making-apps-accessible": (NVDA, "VisionClaw's notes"),
	"making-websites-accessible": (NVDA, "VisionClaw's notes"),
	"guides": (NVDA, "NVDA's developer guides"),
}
# Written for people who write add-ons. Left out unless the question is about that.
DEVELOPER_NOTES = frozenset(("addon-development", "objects-and-events", "nvda-inside", "guides"))
_DEVELOPER = re.compile(
	r"\b(add-?ons?|plug-?ins?|code|coding|script(s|ing)?|python|function|method|class|module|api|develop\w*|"
	r"program(ming|mer)|source|event|nvdaobject)\b", re.IGNORECASE)
# How a result begins when nothing that was found is about the question. It is then said as it is.
NOTHING = "Nothing was found about"
# What is said when a model read what was found and says that none of it answers the question.
NO_ANSWER = "Nothing that was found answers that. The nearest thing found, which may not be what you want:"
# A passage is about this long, so that every source is weighed in pieces of the same size.
PASSAGE_CHARS = 340
MAX_FOUND = 3
# How many are looked at before the few that are given are chosen.
WIDE = 40
# All that is given back fits in what the model that answers is shown.
BUDGET = 1150
# What is kept must cover at least this share of what the question names, by the weight of its words, and
# score at least this share of the best.
COVER = 0.45
SHARE = 0.75
# A word that only asks breaks a tie here and no more: "shortcut" must not outweigh what the shortcut is for.
LIGHT = 0.05
# Words of a question that say how something is to be done or asked, and not what: every answer is a way to
# do something with the keyboard.
_MEANS_WORDS = (
	"keyboard shortcut shortcuts hotkey hotkeys way ways computer explain help work works working able "
	"possible easy easily quick quickly best find know learn check see mean means called much many")
# The few words that say nothing in any question. Used when a question has no other words: "what is the NVDA
# key" is about the NVDA key.
_EMPTY = frozenset((
	"the and for with that this from have has was were are not but you your can will what how why which into "
	"out does did please want need just some any all now here there its it's about tell").split())
# Words that point at where the user is. Then the program, the window and the focused control are part of
# the answer, whatever else is found.
_HERE = re.compile(
	r"\bhere\b|\bfocused\b|\bin front\b|\bwhere am i\b|\bam i (in|on)\b|\bwhat can i do\b"
	r"|\bth(is|e current) (program|app|application|window|dialog|control|button|field|list|menu|screen|game|page"
	r"|site|website|thing|one|box|item|tab)\b", re.IGNORECASE)
# A question that asks what something is, and not which key does it.
_WHAT_IS = re.compile(
	r"^\s*(what('s| is| are| does| do)|explain|tell me about|describe|who is|why)\b"
	r"|^\s*how (do|can|would|should) (i|you|we) use (?!(the|my|a) (keyboard|keys)\b)|^\s*how do(es)? .*\bwork\b",
	re.IGNORECASE)
_ASKS_KEY = re.compile(
	r"\b(what|which) (key|shortcut|command|hot ?key|gesture)s?\b|\bpress\b"
	r"|\b(key|shortcut|command|hot ?key|gesture)s? (for|to|that|do i|does|is used|are used)\b", re.IGNORECASE)
# A key written out, like NVDA+T or control+alt+n.
_MODIFIER = r"(?:nvda|control|ctrl|alt|shift|windows|win|insert|caps ?lock)"
_KEY = re.compile(rf"\b(?:{_MODIFIER}\s*\+\s*)+[a-z0-9]+\b", re.IGNORECASE)
_SENTENCE = re.compile(r"(?<=[.!?;])\s+")


# Different words people use for one thing. Kept short: only what real questions were seen to miss.
_SAME = {
	"talk": "speak", "speech": "speak", "spoken": "speak", "app": "program", "applic": "program", "exit": "quit",
	"pc": "comput", "laptop": "comput", "tray": "notific", "erase": "delet", "remov": "delet",
}


def root(word):
	"""A word cut down further than memory.stem does, so that navigate, navigating, navigation and navigator
	are one word, as are close and closing, move and moving, stop and stopping. Used on both sides of every
	comparison here, so it only has to be the same for both."""
	cut = word
	for suffix in ("ation", "ator", "ate", "at"):
		if word.endswith(suffix) and len(word) - len(suffix) >= 5:
			cut = word[:-len(suffix)]
			break
	else:
		if len(word) >= 4 and word.endswith("e"):
			cut = word[:-1]
		elif len(word) >= 4 and word[-1] == word[-2] and word[-1] not in "aeioulsf":
			cut = word[:-1]
	return _SAME.get(cut, cut)


def roots(found):
	return {root(word) for word in found}


def textWords(text):
	"""The telling words of a text, as they are compared here. "NVDA" is kept, which it is not elsewhere: in
	"what is the NVDA key" it is what is asked about."""
	return roots(stem(word) for word in _WORD.findall((text or "").lower()) if word not in _COMMON or word == "nvda")


_MEANS = roots(stem(word) for word in _MEANS_WORDS.split())
_ASKING = roots(commands._ASKING)


class Passage:
	"""One small piece of what a source knows. source: one of ORDER. title: what it is about, in a few words.
	text: what it says. origin: what the source is called when the user is told where an answer is from.
	here: it says where the user is, so it belongs to any question about "this" or "here".
	command: it is a command with its keys. developer: it is written for people who write add-ons."""

	__slots__ = ("source", "title", "text", "origin", "here", "command", "developer", "lead", "_named", "_other")

	def __init__(self, source, title, text, origin="", here=False, command=False, developer=False, lead=False,
			named=None, other=None):
		self.source = source
		self.title = " ".join(str(title or "").split())
		self.text = " ".join(str(text or "").split())
		self.origin = origin or ORIGINS[source]
		self.here = here
		self.command = command
		self.developer = developer
		# The first piece under a heading: where a thing is said to be what it is.
		self.lead = lead
		self._named = None if named is None else roots(named)
		self._other = None if other is None else roots(other)

	def words(self):
		"""(the words of its title, the words of its text), worked out once."""
		if self._named is None:
			self._named = textWords(self.title)
		if self._other is None:
			self._other = textWords(self.text)
		return self._named, self._other

	def line(self, chars=PASSAGE_CHARS):
		"""The passage as one line that says where it is from."""
		text = self.text
		if self.title and not match.plain(text).startswith(match.plain(self.title)):
			text = f"{self.title.rstrip('.:')}. {text}"
		return f"From {self.origin}: {shorten(text, chars)}"


def shorten(text, chars):
	"""A text cut to a length at the end of a sentence, where that keeps most of it."""
	text = " ".join(str(text or "").split())
	if len(text) <= chars:
		return text
	kept = ""
	for sentence in _SENTENCE.split(text):
		if len(kept) + len(sentence) + 1 > chars:
			break
		kept = f"{kept} {sentence}".strip()
	return kept if len(kept) >= chars // 2 else clip(text, chars)


def chunks(body, chars=PASSAGE_CHARS):
	"""A long text as pieces of whole sentences, each about chars long."""
	found, piece = [], ""
	for sentence in _SENTENCE.split(" ".join(str(body or "").split())):
		if not sentence:
			continue
		if piece and len(piece) + len(sentence) + 1 > chars:
			found.append(piece)
			piece = ""
		piece = f"{piece} {sentence}".strip()
		while len(piece) > chars * 2:  # one endless sentence
			found.append(piece[:chars * 2])
			piece = piece[chars * 2:].strip()
	if piece:
		found.append(piece)
	return found


def htmlSections(page):
	"""A web page of help, such as NVDA's user guide, as (title, text) at its headings. A table's heading row
	is left out, because "Name, Desktop key, Laptop key" says nothing and would make every table look as if it
	were about the desktop; each other row becomes a sentence, so that a command stays with its keys."""
	page = re.sub(r"<(script|style)\b.*?</\1>", " ", page or "", flags=re.DOTALL | re.IGNORECASE)
	found = []
	parts = re.split(r"<h[1-4][^>]*>(.*?)</h[1-4]>", page, flags=re.DOTALL | re.IGNORECASE)
	for at in range(1, len(parts) - 1, 2):
		title = " ".join(html.unescape(re.sub(r"<[^>]+>", "", parts[at])).split())
		body = re.sub(r"<th\b[^>]*>.*?</th>", " ", parts[at + 1], flags=re.DOTALL | re.IGNORECASE)
		body = re.sub(r"</td>\s*<td\b[^>]*>", ", ", body, flags=re.IGNORECASE)
		body = re.sub(r"</(tr|li|p|dd|dt)>", "; ", body, flags=re.IGNORECASE)
		body = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", body)).split())
		# Tidy what the joining left behind: "text. ;" and "; ;".
		body = re.sub(r"\s+([;,.])", r"\1", body)
		body = re.sub(r"([.!?:;,])[;,]+", r"\1", body).strip(" ;,")
		# The page's own title and its table of contents name everything and say nothing.
		if title and len(body) > 40 and at > 1 and not re.search(r"table of contents", title, re.IGNORECASE):
			found.append((title, body))
	return found


def fromSections(sections):
	"""Passages from the sections of the knowledge files and the user guide: (title, body, source name) each."""
	found = []
	for title, body, name in sections:
		source, origin = NOTES.get(name, (NVDA, "VisionClaw's notes on NVDA"))
		for at, piece in enumerate(chunks(body)):
			found.append(Passage(source, title, piece, origin, developer=name in DEVELOPER_NOTES, lead=at == 0))
	return found


def fromCommand(scriptName, description, category, line, source=NVDA, origin=""):
	"""A passage for one NVDA command, known by the same words by which commands are found."""
	named, other = commands.entryWords(scriptName, description, category)
	return Passage(source, "", line, origin, command=True, named=named, other=other)


def asked(question, extra=""):
	"""(the telling words of a question, those among them that only ask or only say "with the keyboard").
	extra: the name of what the question's "this" or "it" means, where a model said which thing that is. Where
	the question names something itself, the extra words only break ties; where it names nothing, they are
	what is asked about."""
	said = roots(commands.telling(question))
	light = said & (_MEANS | _ASKING)
	if not said - light:
		# Nothing is left to name: then even "NVDA" and "key" tell, as in "what is the NVDA key".
		every = roots(stem(word) for word in _WORD.findall(commands._withoutTimes(question).lower()) if word not in _EMPTY)
		if every - light:
			said, light = every, every & light
	more = textWords(extra) - said if extra else set()
	if more:
		if said - light:
			light = light | more
		said = said | more
	return said, light


def isHere(question):
	"""Whether a question is about where the user is: this program, this window, the focused control."""
	return bool(_HERE.search(question or ""))


def isDeveloper(question):
	return bool(_DEVELOPER.search(question or ""))


def isWhatIs(question):
	"""Whether a question asks what something is. An explanation answers it, not a command."""
	return bool(_WHAT_IS.search(question or "")) and not _ASKS_KEY.search(question or "") and not keysIn(question)


def _key(text):
	text = re.sub(r"\s*\+\s*", "+", text.lower())
	return text.replace("ctrl+", "control+").replace("win+", "windows+").replace("insert+", "nvda+")


def keysIn(question):
	"""The keys a question writes out, like NVDA+T, as NVDA and Windows write them."""
	return [_key(hit.group(0)) for hit in _KEY.finditer(question or "")]


def hasKey(text, key):
	"""Whether a text names a key: "nvda+t" is in "Keys: NVDA+t." and not in "NVDA+tab"."""
	return bool(re.search(rf"(?<![a-z0-9+]){re.escape(key)}(?![a-z0-9+])", _key(text).replace("caps lock+", "nvda+")))


def _ranked(question, passages, limit, cover, share, inOrder=False, extra=""):
	"""The passages a question is about, best first, and not all of one kind where there are others: the best
	from NVDA does not push out the best from Windows, and three commands do not push out the explanation."""
	said, light = asked(question, extra)
	naming = said - light
	found = [passages[index] for index in ranking.rank(
		said, [passage.words() for passage in passages], WIDE, share=share, light=light, cover=cover,
		lightWeight=LIGHT)]
	# Among those, a heading that is exactly what was asked about comes first: "Browse Mode" for browse mode.
	# inOrder: and of two such headings the one that comes first in the guide, where a thing is introduced
	# before its settings are listed.
	place = {id(passage): at for at, passage in enumerate(passages)}
	found.sort(key=lambda passage: (passage.words()[0] != naming, place[id(passage)] if inOrder else 0))
	chosen = []
	# First the best of each source, then the best under each heading, then whatever is left.
	for kindOf in (lambda p: (p.origin, p.command), lambda p: (p.origin, p.command, p.title)):
		kinds = {kindOf(passage) for passage in chosen}
		for passage in found:
			if passage not in chosen and kindOf(passage) not in kinds:
				kinds.add(kindOf(passage))
				chosen.append(passage)
	chosen += [passage for passage in found if passage not in chosen]
	chosen = chosen[:limit]
	return [passage for passage in found if passage in chosen]


def about(question, passages, limit=MAX_FOUND, cover=COVER, share=SHARE, extra=""):
	"""The passages that are about a question, best first; among equals, in the order the sources are asked.
	A key that is written out finds what that key does. A question that asks what something is gets
	explanations before commands. Passages that say where the user is are added when the question is about
	"this" or "here", and are all there is when nothing else is found for such a question."""
	# Among equals: in the order the sources are asked, and a command with a key before one without.
	passages = sorted(passages, key=lambda passage: (
		ORDER.index(passage.source), passage.command and "no key assigned" in passage.text))
	if not isDeveloper(question):
		passages = [passage for passage in passages if not passage.developer]
	# A question that only points, "what does this do", is about where the user is, like one that says "here".
	own, ownLight = asked(_HERE.sub(" ", question))
	pointing = isHere(question) or (pointsAt(question) and not own - ownLight)
	here = [passage for passage in passages if passage.here] if pointing else []
	keys = keysIn(question)
	if here and not keys:
		# "What does this program do" names nothing but the program: then where the user is, is the answer.
		said, light = asked(_HERE.sub(" ", question), extra)
		if not said - light:
			return here
	found = []
	for key in keys:
		# A key of Windows is looked for in what is known about Windows first, any other in NVDA's commands.
		first = SYSTEM if key.startswith("windows+") else NVDA
		found += sorted(
			(passage for passage in passages if hasKey(passage.text, key) and passage not in found),
			key=lambda passage: (passage.source != first, not passage.command))
	found = found[:limit]
	if not found and isWhatIs(question):
		# What a thing is, is said where the section about it begins; then anywhere in an explanation; a
		# command last.
		said, light = asked(question, extra)
		found = _ranked(question, [
			passage for passage in passages if passage.lead and said - light <= passage.words()[0]], limit, cover, share,
			inOrder=True, extra=extra)
		found = found or _ranked(
			question, [passage for passage in passages if not passage.command], limit, cover, share, extra=extra)
	if not found:
		found = _ranked(question, passages, limit, cover, share, extra=extra)
	return found + [passage for passage in here if passage not in found]


def resultText(found, budget=BUDGET):
	"""What was found, one passage to a line, each saying where it is from, within what a model is shown."""
	if not found:
		return ""
	each = max(200, budget // len(found) - 12)
	lines = []
	for passage in found:
		line = passage.line(each)
		if line not in lines:
			lines.append(line)
	return "\n".join(lines)


def saidWords(question, limit=4):
	"""What a question names, in the user's own words, for saying what was not found."""
	said, light = asked(question)
	found = []
	for word in _WORD.findall(commands._withoutTimes(question).lower()):
		if root(stem(word)) in said - light and word not in found:
			found.append(word)
	return found[:limit]


def nothingText(question, program="", window="", notes=None):
	"""The honest answer when none of the sources says anything about what was asked. notes: whether VisionClaw
	has notes on the program, where that is known; without them it says how to get some."""
	named = saidWords(question)
	what = " or ".join(named) if named else "that"
	where = "NVDA's commands and user guide"
	where += f", the program {program}" if program else ", the program in front"
	where += f", its window {window}" if window else ", its window"
	where += ", VisionClaw's notes on the program" if notes else ""
	text = f"{NOTHING} {what}. Asked were: {where}, and what VisionClaw knows about Windows."
	if notes is False:
		text += (
			" VisionClaw has no notes on this program yet. Ask it to learn about this program, and it reads up on "
			"it on the internet after asking you.")
	return text


def isNothing(result):
	return str(result or "").startswith(NOTHING)


# How the lines begin that say where the user is.
_HERE_LINES = ("From the program ", f"From {ORIGINS[APP]}:", f"From {ORIGINS[WINDOW]}:")


def numbered(result):
	"""A result with its pieces numbered, when it has several that say where they are from, so that a model
	takes each as a thing of its own. Any other text is left as it is."""
	lines = [line.strip() for line in str(result or "").splitlines() if line.strip()]
	if len(lines) < 2 or not all(line.startswith("From ") for line in lines):
		return result
	return "\n".join(f"{number}. {line}" for number, line in enumerate(lines, 1))


# What a question says when it points at something instead of naming it.
_POINTS = re.compile(r"\b(this|that|it|its|here|these|those)\b", re.IGNORECASE)
_REFERENT_SYSTEM = (
	"A blind person using a screen reader asked a question that points at something with a word like this, it "
	"or here, without naming it. You are told where they are. Choose what the question is about."
)


# What a question says it means, when it says "this program" or "this button" and not only "this".
_SAYS_PROGRAM = re.compile(r"\bth(is|at|e current) (program|app|application|game|utility|tool|software)\b", re.IGNORECASE)
_SAYS_WINDOW = re.compile(r"\bth(is|at|e current) (window|dialog|screen|page|site|website|tab)\b", re.IGNORECASE)
_SAYS_CONTROL = re.compile(
	r"\bth(is|at|e current|e focused) (control|button|field|box|check ?box|list|item|menu|slider|link|option|thing|one)\b"
	r"|\bfocused\b", re.IGNORECASE)
PROGRAM_MEANT, WINDOW_MEANT, CONTROL_MEANT = "the program", "the window", "the control that has the focus"


def saysWhich(question):
	"""What a question says it is about, where it says so itself: PROGRAM_MEANT, WINDOW_MEANT, CONTROL_MEANT,
	or "" when it only points. What the user's own words decide is not asked of a model."""
	for pattern, meant in ((_SAYS_PROGRAM, PROGRAM_MEANT), (_SAYS_WINDOW, WINDOW_MEANT), (_SAYS_CONTROL, CONTROL_MEANT)):
		if pattern.search(question or ""):
			return meant
	return ""


def pointsAt(question):
	"""Whether a question points at something without naming it: "what does this do", "how do I close it"."""
	return bool(_POINTS.search(question or ""))


def referent(llm, role, question, choices):
	"""Which of the things where the user is a question means by "this" or "it". choices: (what it is, its
	name) each, such as ("the program", "notepad"). A model chooses by number; plain code offers the things.
	Returns the index, or None when the model cannot be asked."""
	choices = [choice for choice in choices if choice[1]]
	if len(choices) < 2:
		return 0 if choices else None
	numbered = "\n".join(f"{number}. {what}: {clip(name, 120)}" for number, (what, name) in enumerate(choices, 1))
	schema = {
		"type": "object",
		"properties": {"about": {"type": "integer", "enum": list(range(1, len(choices) + 1))}},
		"required": ["about"],
	}
	try:
		chosen = int(llm.json(
			role, _REFERENT_SYSTEM, f"The question: \"{clip(question, 300)}\"\nWhere they are:\n{numbered}\n"
			"Which one is the question about? Give its number.", schema, maxTokens=20).get("about") or 0)
	except Exception as e:
		# Knowing what "this" means is a help, not a need: only stopping the request is passed on. Without a
		# model's answer the question is looked up by its own words.
		if type(e).__name__ == "Cancelled":
			raise
		return None
	return chosen - 1 if 1 <= chosen <= len(choices) else None


def pickable(result):
	"""The lines of a result that a model may choose among for the answer, or reject: none when the result says
	where the user is, which is said whole, or that nothing was found."""
	lines = [line.strip() for line in str(result or "").splitlines() if line.strip()]
	if not lines or isNothing(result) or lines[0].startswith(_HERE_LINES):
		return []
	return [line for line in lines if not line.startswith(_HERE_LINES)][:4]


def quoted(result, pick=""):
	"""The answer when a model is not to put anything in its own words: the best line of a result, and with it
	the best that Windows says when the best is from somewhere else, because a question like "how do I copy
	text" has an answer in NVDA and a more usual one in Windows. pick: the line a capable model chose as the
	one that answers the question; then that line is the answer."""
	lines = [line.strip() for line in str(result or "").splitlines() if line.strip()]
	if not lines:
		return ""
	if pick and pick in lines:
		return pick
	if lines[0].startswith(_HERE_LINES):
		# Where the user is: the program, the window and the control with the focus belong together.
		return " ".join(line for line in lines[:4] if line.startswith(_HERE_LINES))
	windows = f"From {ORIGINS[SYSTEM]}:"
	second = next((line for line in lines[1:] if line.startswith(windows)), "")
	return lines[0] if lines[0].startswith(windows) or not second else f"{lines[0]} {second}"
