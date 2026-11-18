# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the add-ons installed in NVDA, as plain data: which of them does what the user wants, and what
# the add-on NVDA Coach teaches. The owner asked on 2026-11-18 that VisionClaw notice the add-ons that are
# installed, learn what they do, and help the user work with them "depending on what the user wishes to do with
# the screen reader", and that it work with NVDA Coach "only if user requests, while respecting the level of
# help the user is asking for".
#
# Nothing here is a list written in advance: what an add-on does is what the add-on itself says, in its
# description, its help and the names of its commands, read from the running NVDA each time (accesstools.py).
# Which add-on fits a wish is decided by plain code, the same way a question is answered (claw/lookup.py); when
# none fits, plain code says so.
#
# NVDA Coach (Tony Gebhard, GPL v2; read from its source at version 1.6.0 on 2026-11-18) teaches NVDA in
# lessons of single steps. Its lessons are plain sentences in files of its own, each step with an instruction
# and hints; what the user has finished is in a file of its own too. It has one command, which opens its
# window, and no setting for how much help it gives. So how much help the user gets here is read from the
# user's own words (wants): a hint, one step, a whole lesson, the list of lessons, how far they are, or the
# Coach's own window. Its files are only read. When a newer NVDA Coach keeps its lessons differently, they are
# simply not found, and VisionClaw says so. No NVDA dependencies.

import json
import os
import re

from . import lookup

ON, OFF, WAITING = "on", "turned off", "installed but not running"
MAX_ADDONS = 3
MAX_EACH = 2
HELP_BLOCKS = 40
BLOCK_CHARS = 1200
# All that is said about add-ons for a wish fits in what a tool gives back.
WISH_CHARS = 1300


class Installed:
	"""One add-on installed in NVDA. ident: its own name, which is also its folder. name: what it is called.
	description: what it says about itself. state: ON, OFF or WAITING. commands: (what the command does, its
	keys as NVDA writes them or "") for each command it has where the user is. help: its help, in blocks."""

	__slots__ = ("ident", "name", "description", "state", "commands", "help")

	def __init__(self, ident, name="", description="", state=ON, commands=(), help=()):
		self.ident = str(ident or "")
		self.name = " ".join(str(name or ident or "").split())
		self.description = " ".join(str(description or "").split())
		self.state = state
		self.commands = tuple((" ".join(str(what or "").split()), " ".join(str(keys or "").split())) for what, keys in commands)
		self.help = tuple(" ".join(str(block).split())[:BLOCK_CHARS] for block in list(help)[:HELP_BLOCKS] if str(block).strip())

	def __repr__(self):
		return f"Installed({self.ident}, {self.state})"


def origin(addon):
	"""What an add-on is called where the user is told that something is from it."""
	return f"the add-on {addon.name}"


def commandLine(what, keys):
	return f"{what.rstrip('.')}. " + (f"Keys: {keys}." if keys else "It has no key assigned.")


def passages(installed):
	"""What every add-on says about itself, as small passages that say which add-on they are from."""
	found = []
	for addon in installed:
		where = origin(addon)
		if addon.description:
			found.append(lookup.Passage(lookup.NVDA, addon.name, addon.description, where, lead=True))
		for block in addon.help:
			found += [lookup.Passage(lookup.NVDA, "", piece, where) for piece in lookup.chunks(block)]
		for what, keys in addon.commands:
			if what:
				found.append(lookup.Passage(lookup.NVDA, "", commandLine(what, keys), where, command=True))
	return found


# Words of a request about add-ons that only ask, and name nothing the user wants to do.
_ONLY_ASKS = re.compile(
	r"\b(add-?ons?|plug-?ins?|extensions?|installed|install|nvda|screen ?reader|list|show|tell|say|which|what|whats|"
	r"is|are|there|do|does|did|have|has|got|get|i|me|my|mine|you|your|an?|any|all|every|one|ones|of|the|that|for|to|can|"
	r"could|would|lets?|help|helps|with|use|using|on|in|it|them|they|please|know|about|many|how|running|turned|"
	r"enabled|disabled|off|names?|called)\b", re.IGNORECASE)


def wishOf(asked):
	"""What the user wants to do, without the words that only ask about add-ons: "" when nothing is left, as
	in "which add-ons are installed"."""
	left = " ".join(_ONLY_ASKS.sub(" ", str(asked or "")).split())
	return left if lookup.textWords(left) else ""


def forWish(wish, installed, limit=MAX_ADDONS, each=MAX_EACH):
	"""The add-ons that say they do what the user wants, best first, each with the passages that say so:
	[(add-on, [passages])]. Plain code; empty when none says so."""
	byOrigin = {origin(addon): addon for addon in installed}
	found = lookup.about(wishOf(wish) or wish, passages(installed), limit=limit * each * 2)
	chosen = []
	for passage in found:
		addon = byOrigin.get(passage.origin)
		if addon is None:
			continue
		mine = next((kept for who, kept in chosen if who is addon), None)
		if mine is None:
			if len(chosen) >= limit:
				continue
			chosen.append((addon, [passage]))
		elif len(mine) < each:
			mine.append(passage)
	return chosen


def stateText(addon):
	"""What is said of an add-on that is not on. VisionClaw never turns an add-on on or off by itself."""
	if addon.state == ON:
		return ""
	return (
		f" It is {addon.state}, so its commands do not work now. VisionClaw does not turn add-ons on or off; that is "
		"done in NVDA's Add-on Store.")


def wishText(wish, installed, chars=WISH_CHARS):
	"""Which installed add-ons do what the user wants, in sentences that are said as they are, so that a key is
	never retold wrongly; or that none does."""
	if not installed:
		return "No add-ons are installed in NVDA."
	found = forWish(wish, installed)
	count = len(installed)
	if not found:
		said = lookup.saidWords(wishOf(wish) or wish)
		what = " or ".join(said) if said else "that"
		return (
			f"None of the {count} add-ons installed in NVDA says anything about {what}. Asked were what each says "
			"about itself, its help and its commands. They are: " + ", ".join(addon.name for addon in installed[:30]) + ".")
	lines = []
	for addon, about in found:
		text = f"The add-on {addon.name}: " + " ".join(
			lookup.shorten(passage.text, 260 if len(found) > 1 else 420) for passage in about) + stateText(addon)
		if sum(len(line) + 1 for line in lines) + len(text) > chars and lines:
			break
		lines.append(text)
	head = (
		"One add-on installed in NVDA says it does this." if len(lines) == 1
		else f"{len(lines)} add-ons installed in NVDA say something about this.")
	return "\n".join([head] + lines)


# --- NVDA Coach ---

COACH = "nvdaCoach"
COACH_NAME = "NVDA Coach"
# The one command NVDA Coach has, by the name of its script: it opens the Coach's window or its list of lessons.
COACH_SCRIPT = "toggleCoach"
# Where its lessons and the user's progress are kept (NVDA Coach 1.6.0).
COACH_LESSONS = ("globalPlugins", "nvdaCoach", "lessons")
COACH_PROGRESS = "nvdaCoachProgress.json"
# How much help the user asks for, read from their own words.
OPEN, LIST, PROGRESS, HINT, ONE, STEPS = "open", "list", "progress", "hint", "one", "steps"
STEPS_CHARS = 1150
# The keys of the Coach's own window, read from its source at version 1.6.0.
COACH_OPENED = (
	"NVDA Coach is open. In its window, Enter or Space goes to the next step, F1 repeats the step, F2 gives a hint, "
	"F3 skips the step, and Escape stops the lesson.")
# Words that only ask for coaching and say nothing about what is to be learned.
_COACHING = re.compile(
	r"\b(nvda coach|coach(ing|es)?|lessons?|chapters?|tutorials?|training|trainer|teach(ing)?|train|learn(ing)?|"
	r"hints?|clues?|step by step|steps?|walk me through|show me how|help me( with)?|give me|tell me|can you|could you|"
	r"please|me|about|on|how to|the whole|a little|just|only|first|next|again|with|from|some|more|bit of|open|start|"
	r"show|launch|run|begin|continue|resume|bring up|go to|go back to|window|add-?on|whole|full|detail|every|each|all)\b",
	re.IGNORECASE)
_PROGRESS = re.compile(
	r"\b(progress|how far|certificate|(which|what|how many) (of the )?lessons? (have|did) i|have i (done|finished|completed)|"
	r"lessons? (i have|i've|i) (done|finished|completed)|done so far|left to do|still to do)\b", re.IGNORECASE)
_LIST = re.compile(
	r"\b(which|what|list|how many|all the|every)\b.{0,20}\b(lessons?|chapters?|topics?)\b"
	r"|\bwhat (does|can|will) (it|the coach|nvda coach) teach\b|\bwhat can i learn\b", re.IGNORECASE)
_HINT = re.compile(
	r"\b(hints?|clues?|nudge|pointers?)\b|\b(don'?t|do not) (tell|give) me the (answer|keys?)\b"
	r"|\bwithout (telling|giving) me\b", re.IGNORECASE)
_STEPS = re.compile(
	r"\b(step by step|every step|all (of )?the steps|each step|walk me through|talk me through|the whole lesson|"
	r"the full lesson|whole thing|in detail|in full|from the (start|beginning)|teach me|lesson (on|about|for))\b",
	re.IGNORECASE)

_NAMES_COACH = re.compile(r"\bcoach\b|\blessons?\b|\bchapters?\b", re.IGNORECASE)
# Said after an answer from NVDA itself, when the user asked to be taught and NVDA Coach is not there.
COACH_ABSENT = (
	"This is from NVDA itself. For lessons that go step by step there is the free add-on NVDA Coach, in NVDA's "
	"Add-on Store; it is not installed here.")


def namesCoach(asked):
	"""Whether the user's words ask for NVDA Coach itself or its lessons, and not only to be taught something."""
	return bool(_NAMES_COACH.search(str(asked or "")))


def plainQuestion(asked):
	"""What the user wants to learn, as a question without the words that only ask for coaching."""
	return " ".join(_COACHING.sub(" ", str(asked or "")).split())


class Lesson:
	"""One lesson of NVDA Coach. steps: (the instruction, its hints) for each step."""

	__slots__ = ("chapter", "chapterTitle", "ident", "title", "steps", "_words", "_often")

	def __init__(self, chapter, chapterTitle, ident, title, steps):
		self.chapter = chapter
		self.chapterTitle = chapterTitle
		self.ident = ident
		self.title = title
		self.steps = tuple(steps)
		self._words = None
		self._often = None

	def often(self):
		"""How often each telling word comes in the steps of the lesson."""
		if self._often is None:
			self._often = {}
			for said, hints in self.steps:
				for word in re.findall(r"[A-Za-z][A-Za-z0-9']+", f"{said} {' '.join(hints)}"):
					for told in lookup.textWords(word):
						self._often[told] = self._often.get(told, 0) + 1
		return self._often

	def words(self):
		if self._words is None:
			self._words = (
				lookup.textWords(self.title),
				lookup.textWords(" ".join(f"{said} {' '.join(hints)}" for said, hints in self.steps)))
		return self._words


# What a step says about the Coach's own window. Said by VisionClaw, outside that window, it would have the user
# press Enter in whatever program they are in. Only the English wording is known; in other languages it stays.
_IN_ITS_WINDOW = re.compile(r"\s*Press (Enter|Space)( or (Enter|Space))? to continue\.?", re.IGNORECASE)


def _oneLine(text):
	return " ".join(_IN_ITS_WINDOW.sub("", str(text or "")).split())


def coachLessons(folder, languages=("en",)):
	"""The lessons of NVDA Coach, in its own order, from the folder of lessons in the add-on: the first of the
	languages it has. A file that is not a chapter of lessons is passed over. Nothing is ever written."""
	chosen = next((os.path.join(folder, lang) for lang in languages if lang and os.path.isdir(os.path.join(folder, lang))), None)
	if chosen is None:
		return []
	chapters = []
	for name in sorted(os.listdir(chosen)):
		if not name.endswith(".json"):
			continue
		try:
			with open(os.path.join(chosen, name), encoding="utf-8") as f:
				chapter = json.load(f)
		except (OSError, ValueError, UnicodeDecodeError):
			continue
		if isinstance(chapter, dict) and isinstance(chapter.get("lessons"), list):
			chapters.append(chapter)

	def order(thing):
		at = thing.get("order")
		return at if isinstance(at, (int, float)) else 9999

	found = []
	for chapter in sorted(chapters, key=order):
		for lesson in sorted((entry for entry in chapter["lessons"] if isinstance(entry, dict)), key=order):
			steps = []
			for step in lesson.get("steps") or ():
				if not isinstance(step, dict) or not _oneLine(step.get("instruction")):
					continue
				hints = step.get("hints") if isinstance(step.get("hints"), list) else [step.get("hint")]
				steps.append((_oneLine(step["instruction"]), tuple(_oneLine(hint) for hint in hints if _oneLine(hint))))
			if steps:
				found.append(Lesson(
					str(chapter.get("id") or ""), _oneLine(chapter.get("title")), str(lesson.get("id") or ""),
					_oneLine(lesson.get("title")), steps))
	return found


def coachDone(path):
	"""The lessons the user has finished, as (chapter, lesson) pairs, from NVDA Coach's own file. Empty when
	there is none or it cannot be read."""
	try:
		with open(path, encoding="utf-8") as f:
			kept = json.load(f)
	except (OSError, ValueError, UnicodeDecodeError):
		return set()
	done = set()
	if isinstance(kept, dict):
		for chapter, lessons in kept.items():
			if isinstance(lessons, dict):
				done |= {(str(chapter), str(lesson)) for lesson, info in lessons.items() if isinstance(info, dict) and info.get("completed")}
	return done


def wants(asked):
	"""How much help the user asks for, by their own words: how far they are (PROGRESS), which lessons there
	are (LIST), the Coach's own window when the words name nothing to learn (OPEN), a hint and no more (HINT),
	a whole lesson (STEPS), or else a single step (ONE)."""
	asked = str(asked or "")
	if _PROGRESS.search(asked):
		return PROGRESS
	if _LIST.search(asked):
		return LIST
	if not topic(asked):
		return OPEN
	if _HINT.search(asked):
		return HINT
	return STEPS if _STEPS.search(asked) else ONE


def topic(asked):
	"""What the user wants to learn: the telling words that are left without those that only ask for coaching."""
	return lookup.textWords(_COACHING.sub(" ", lookup._KEY.sub(" ", str(asked or "")))) - {"nvda"}


def coachFind(lessons, asked):
	"""The lesson and the step in it that are about what the user wants to learn: (lesson, index of the step),
	or None. What counts is how much a lesson says about the thing, word for word asked, and whether its title
	names it: a lesson that mentions a word once is not about it, and neither is one whose title has one of two
	words while another lesson speaks of both throughout. The lesson must have at least half of the words that
	were asked."""
	said = topic(asked)
	if not said or not lessons:
		return None
	best, most = None, 0.0
	for lesson in lessons:
		title, body = lesson.words()
		if len(said & (title | body)) * 2 < len(said):
			continue
		often = lesson.often()
		inTitle = len(said & title) / len(said)
		score = 2.0 * sum(min(often.get(word, 0), 6) / 6 for word in said) / len(said) + 1.5 * inTitle + (inTitle == 1.0)
		if score > most:
			best, most = lesson, score
	if best is None:
		return None
	at, shared = 0, 0
	for index, (instruction, hints) in enumerate(best.steps):
		count = len(said & lookup.textWords(f"{instruction} {' '.join(hints)}"))
		if count > shared:
			at, shared = index, count
	return best, at


def _count(number, word):
	return f"{number} {word}" if number == 1 else f"{number} {word}s"


def coachList(lessons, done=()):
	"""The chapters of NVDA Coach with how many lessons each has, and how many of them are finished."""
	chapters = []
	for lesson in lessons:
		if not chapters or chapters[-1][0] != lesson.chapter:
			chapters.append([lesson.chapter, lesson.chapterTitle or lesson.chapter, 0, 0])
		chapters[-1][2] += 1
		chapters[-1][3] += (lesson.chapter, lesson.ident) in done
	return chapters


def coachText(lessons, done, asked, key=""):
	"""What VisionClaw says from NVDA Coach's lessons for what the user asked, as much as they asked for and
	in the Coach's own words, so that a key is never retold wrongly. key: the key that opens NVDA Coach, as
	NVDA writes it, or ""."""
	opens = f"press {key}" if key else "ask VisionClaw to open NVDA Coach"
	level = wants(asked)
	if not lessons:
		return (
			"NVDA Coach is installed, but its lessons were not found where NVDA Coach 1.6.0 keeps them, so VisionClaw "
			f"cannot read them. To use it, {opens}.")
	if level == PROGRESS:
		finished = sum(1 for lesson in lessons if (lesson.chapter, lesson.ident) in done)
		parts = [f"{title}: {have} of {total}" for _ident, title, total, have in coachList(lessons, done)]
		following = next((lesson for lesson in lessons if (lesson.chapter, lesson.ident) not in done), None)
		text = f"You have finished {finished} of the {_count(len(lessons), 'lesson')} of NVDA Coach. " + "; ".join(parts) + "."
		if following is not None:
			text += f" The first lesson you have not finished is \"{following.title}\", in {following.chapterTitle}."
		return text + f" To go on, {opens}."
	if level in (LIST, OPEN):
		parts = [f"{title}, {_count(total, 'lesson')}" for _ident, title, total, _have in coachList(lessons)]
		return (
			f"NVDA Coach has {_count(len(lessons), 'lesson')} in {_count(len(parts), 'chapter')}: " + "; ".join(parts)
			+ f". To choose one, {opens}. You can also ask VisionClaw for a hint, a step or a whole lesson about something.")
	found = coachFind(lessons, asked)
	if found is None:
		said = sorted(topic(asked))
		return (
			f"None of the {_count(len(lessons), 'lesson')} of NVDA Coach is about " + (" or ".join(said) if said else "that")
			+ f". To hear which lessons it has, ask which lessons NVDA Coach has; to open it, {opens}.")
	lesson, at = found
	where = f"From NVDA Coach, the lesson \"{lesson.title}\" in {lesson.chapterTitle}"
	instruction, hints = lesson.steps[at]
	if level == HINT:
		if hints:
			return f"{where}, a hint: {hints[0]} For the step itself, ask for the step; for all of it, ask for the whole lesson."
		return f"{where} has no hint for this step. The step itself says: {instruction}"
	if level == STEPS:
		lines, used = [], 0
		for number, (said, _hints) in enumerate(lesson.steps, 1):
			line = f"Step {number}: {said}"
			if used + len(line) > STEPS_CHARS and lines:
				break
			lines.append(line)
			used += len(line) + 1
		last = f"To do the lesson with the Coach, {opens}."
		if len(lines) < len(lesson.steps):
			last = f"The lesson has {len(lesson.steps)} steps; these are the first {len(lines)}. {last}"
		return "\n".join([f"{where}, step by step."] + lines + [last])
	return (
		f"{where}, step {at + 1} of {len(lesson.steps)}: {instruction} For a hint only, ask for a hint; for all of "
		f"it, ask for the whole lesson; to do it with the Coach, {opens}.")


def coachMissing(known):
	"""What is said when the user asks for NVDA Coach and it is not installed, or not on. known: its state, or
	None when it is not installed. VisionClaw never installs or turns on an add-on."""
	if known is None:
		return (
			"NVDA Coach is not installed in NVDA. It is a free add-on with lessons that teach NVDA step by step, and "
			"it is in NVDA's Add-on Store under the name NVDA Coach. VisionClaw does not install add-ons. Without it, "
			"you can still ask VisionClaw how to do anything in NVDA, and it answers from NVDA's own user guide.")
	return (
		f"NVDA Coach is installed, but it is {known}, so it cannot be opened. VisionClaw does not turn add-ons on or "
		"off; that is done in NVDA's Add-on Store. You can still ask VisionClaw how to do anything in NVDA.")
