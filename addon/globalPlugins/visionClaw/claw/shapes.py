# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - narrowing what a model may write. A small model that is asked for the id of a setting writes
# the setting's description, or a word that only sounds like an id. Here plain code reads what the step before
# found and turns it into the only answers that are allowed: the ids that were found, the names that were
# listed, on or off, the options of a setting, or a number. The engine then lets the model write nothing else.
# Also for the very smallest models: noticing an answer that only repeats the question, and answering a
# question with a line of what was looked up instead of with a sentence of the model's own.
# No NVDA dependencies.

import re

from . import task as taskModule
from .memory import _COMMON, _WORD, stem, words

IDS, NAMES, VALUE = "ids", "names", "value"
# (tool, field): (the tool whose result holds the allowed answers, what to take from it, and for a value the
# field that says which line is meant).
SOURCES = {
	("set_setting", "setting"): ("find_setting", IDS),
	("set_setting", "value"): ("find_setting", VALUE, "setting"),
	("run_command", "command"): ("find_command", IDS),
	("inspect_nvda", "name"): ("find_nvda", IDS),
	("click_item", "item"): ("list_items", NAMES),
	("drag_item", "item"): ("list_items", NAMES),
	("go_to_item", "item"): ("list_items", NAMES),
	("fill_field", "field"): ("list_items", NAMES),
	("show_skill", "skill"): ("list_skills", NAMES),
	("manage_skill", "skill"): ("list_skills", NAMES),
	("open_thing", "thing"): ("find_thing", IDS),
	("window_action", "window"): ("list_windows", NAMES),
}
# Fields for which one found thing is taken without asking a model: what was found is what the user named.
ONLY_ONE = frozenset((("open_thing", "thing"),))
MAX_CHOICES = 30
NUMBER_PATTERN = "^[+-]?[0-9]{1,4}$"
_ID = re.compile(r"^(\S{1,120}): ")
_NUMBERED = re.compile(r"^\d{1,3}\. (.+)$")
# Words of a question that say nothing about what is asked.
_ASKING = frozenset((
	"page", "say", "says", "said", "about", "tell", "website", "site", "window", "screen", "show", "shows", "find",
	"know", "read", "text", "give", "much", "many", "where", "who", "whom", "there", "thing", "something",
	"web", "search", "look", "internet", "online", "google",
))
MAX_PICKED = 8
# Tools whose result is told as it is, because it already is the answer: what the vision model saw, or the
# text that was asked to be read.
AS_IS = ("look", "read_text")


def _lines(result):
	lines = [line.strip() for line in (result or "").splitlines() if line.strip()]
	# A result that was cut off ends in a line that is not whole.
	if lines and "[cut]" in lines[-1]:
		lines.pop()
	return lines


def idsIn(result):
	"""The ids a result lists, one at the start of each line: "speech.rate: Speech rate. Now: 50." """
	found = []
	for line in _lines(result):
		hit = _ID.match(line)
		if not hit:
			# A line that does not start with an id: this is not a list of ids, or not only one. Nothing is
			# narrowed then, because a list with one id missing would shut the right answer out.
			return []
		if hit.group(1) not in found:
			found.append(hit.group(1))
	return found if len(found) <= MAX_CHOICES else []


def namesIn(result):
	"""The names a result lists in numbered lines: "2. New Game button"."""
	found = []
	for line in _lines(result):
		hit = _NUMBERED.match(line)
		if hit and hit.group(1).strip() not in found:
			found.append(hit.group(1).strip())
	# A list too long to offer whole is not narrowed: the right name might be among those left out.
	return found if len(found) <= MAX_CHOICES else []


def lineOf(result, ident):
	return next((line for line in _lines(result) if line.startswith(f"{ident}: ")), None)


def valueShape(line):
	"""What a setting's new value may be, from the line that says what is allowed for it."""
	allowed = line.split("Allowed:", 1)[1] if "Allowed:" in line else line
	if re.search(r"\bon or off\b", allowed.lower()):
		return {"enum": ["on", "off"]}
	hit = re.search(r"one of: (.+)", allowed)
	if hit:
		options = [option.strip().rstrip(".").strip() for option in hit.group(1).split(",")]
		options = [option for option in options if option]
		return {"enum": options[:MAX_CHOICES]} if options else {}
	if "a number from" in allowed.lower():
		return {"pattern": NUMBER_PATTERN}
	return {}


def _source(steps, index, toolName):
	for step in reversed(steps[:index]):
		if step.tool == toolName and step.status == taskModule.STEP_DONE:
			return step.result
	return None


def shapes(toolName, fields, steps, index, form=None):
	"""For the fields of a tool that is about to be filled in: what each may be, where the results so far
	say it. {field: {"enum": [...]}} or {field: {"pattern": ...}}. A field that is not narrowed is left out."""
	form = form or {}
	found = {}
	for name in fields:
		source = SOURCES.get((toolName, name))
		result = _source(steps, index, source[0]) if source else None
		if not result:
			continue
		if source[1] == IDS:
			choices = idsIn(result)
			if choices:
				found[name] = {"enum": choices}
		elif source[1] == NAMES:
			choices = namesIn(result)
			if choices:
				found[name] = {"enum": choices}
		else:
			ids = idsIn(result)
			chosen = form.get(source[2]) or (ids[0] if len(ids) == 1 else None)
			line = lineOf(result, chosen) if chosen else None
			shape = valueShape(line) if line else {}
			if shape:
				found[name] = shape
	return found


def _plain(text):
	return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


# --- What the user's own words already say ---

_UP = re.compile(r"\b(faster|quicker|louder|higher|more|up|increase|raise|bigger)\b")
_DOWN = re.compile(r"\b(slower|quieter|softer|lower|less|down|decrease|reduce|smaller)\b")
_MUCH = re.compile(r"\b(much|a lot|lots|far|way)\b")
_TINY = re.compile(r"\b(slightly|a tiny bit|a touch|a hair)\b")
_OFF = re.compile(r"\b(off|disable[sd]?|stop|don'?t|do not|no longer|without|never|mute|silence)\b")
_ON = re.compile(
	r"\b(turn|switch)(s|ed|ing)? (it |this |that |(the |my )?\w+ ){0,3}on\b|\benable[sd]?\b|\bactivate[sd]?\b"
	r"|\bstart (speaking|saying|reading|announcing|echoing)\b")
_DIRECTION = re.compile(r"\b(left|right|up|down)(wards?)?\b")
# In a drag two things are named: the one that is dragged, then the one it is dropped on.
_SECOND = {("drag_item", "to"): "list_items"}


def numberSaid(text):
	"""The new value of a number, where the user's words give it: "to 70" is 70, "a little faster" is +10,
	"much quieter" is -25, "by 5" with a direction is that much. None where the words do not say."""
	text = (text or "").lower()
	exact = re.search(r"\b(?:to|at)\s+(\d{1,4})\b", text)
	if exact:
		return exact.group(1)
	up, down = bool(_UP.search(text)), bool(_DOWN.search(text))
	if up == down:
		share = re.search(r"\b(\d{1,4})\s*(percent|%)", text)
		return share.group(1) if share else None
	by = re.search(r"\bby\s+(\d{1,4})\b", text)
	amount = by.group(1) if by else "25" if _MUCH.search(text) else "5" if _TINY.search(text) else "10"
	return ("+" if up else "-") + amount


def onOffSaid(text):
	"""On or off, where the user's words say one of them and not the other. "On" alone is not enough:
	"the beep on capitals" does not ask for anything to be turned on."""
	text = (text or "").lower()
	off, on = bool(_OFF.search(text)), bool(_ON.search(text))
	if off != on:
		return "off" if off else "on"
	return None


def optionSaid(text, options):
	"""The one option the user's words set something to: "to all", "at most", or the last word."""
	text = " ".join((text or "").lower().split()).rstrip(" .!")
	hits = [option for option in options if re.search(rf"\b(to|at|as)\s+(the\s+)?{re.escape(str(option).lower())}\b", text)
		or text.endswith(" " + str(option).lower())]
	return hits[0] if len(hits) == 1 else None


def namesSaid(text, names):
	"""The listed names that the user's words say in full, in the order they are said. Where two overlap,
	the longer is meant."""
	said = f" {_plain(text)} "
	spans = []
	for name in names:
		plain = _plain(name)
		at = said.find(f" {plain} ") if len(plain) >= 2 else -1
		if at >= 0:
			spans.append((at, at + len(plain), name))
	spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
	found, end = [], -1
	for start, stop, name in spans:
		if start >= end:
			found.append(name)
			end = stop
	return found


def said(toolName, name, part, steps, index, form=None):
	"""A field's value where the user's own words give it and the results say what it may be. A person's
	words are more reliable than a small model's choice from a list. None where the words do not decide."""
	second = _SECOND.get((toolName, name))
	if second:
		names = namesSaid(part, namesIn(_source(steps, index, second) or ""))
		if len(names) == 2:
			return names[1]
		# One thing and a direction: the direction is in the user's words, which the tool reads itself.
		return " ".join(part.split())[:80] if len(names) == 1 and _DIRECTION.search(part.lower()) else None
	shape = shapes(toolName, [name], steps, index, form).get(name)
	if not shape:
		return None
	if shape.get("pattern"):
		return numberSaid(part)
	choices = shape.get("enum") or []
	source = SOURCES.get((toolName, name))
	if choices == ["on", "off"]:
		return onOffSaid(part)
	if source[1] == VALUE:
		return optionSaid(part, choices)
	if source[1] == NAMES:
		names = namesSaid(part, choices)
		wanted = 2 if (toolName, "to") in _SECOND else 1
		return names[0] if len(names) == wanted else None
	if source[1] == IDS:
		# One thing was found by its name: it is the only answer the form allows, so no model is asked for it.
		if len(choices) == 1 and (toolName, name) in ONLY_ONE:
			return choices[0]
		# A dotted name the user wrote out in full, like api.getFocusObject, is the one that is meant.
		low = (part or "").lower()
		written = [choice for choice in choices if "." in choice and re.search(
			rf"(?<![\w.]){re.escape(choice.lower())}(?![\w])", low)]
		return written[0] if len(written) == 1 else None
	return None


def echoes(value, toolName, name, description):
	"""Whether a model's answer only repeats the question: the field's own description, its name, or the
	tool's name, instead of a value."""
	said = _plain(value)
	if not said:
		return True
	described = _plain(description)
	if said in (_plain(toolName), _plain(name)) or said == described:
		return True
	# Four words in a row taken from the description are the description, wherever they were taken from.
	spoken = said.split()
	return any(" ".join(spoken[at:at + 4]) in described for at in range(len(spoken) - 3))


# --- Answering with what was looked up ---

def _oneWord(text):
	"""Add-on, add on and addon are one word, however the user or a text writes it."""
	return re.sub(r"\badd[- ]?on(s?)\b", r"addon\1", text or "", flags=re.IGNORECASE)


def _asked(question):
	return {word for word in words(_oneWord(question)) if word not in {stem(w) for w in _ASKING}}


def quote(question, text):
	"""The lines of a looked-up text that mention what a question asks about, best first, each with the line
	after a heading joined to it. Returns (lines, the words of the question that were looked for)."""
	lines = _lines(text)
	if len(lines) == 1 and not _ID.match(lines[0]):
		# One paragraph: its sentences. Several lines are kept whole, so that the keys at the end of a line
		# that names a command stay with it.
		lines = [part.strip() for part in re.split(r"(?<=[.!?])\s+", lines[0]) if part.strip()]
	asked = _asked(question)
	scored = []
	for at, line in enumerate(lines):
		count = len(asked & words(_oneWord(line)))
		if not count:
			continue
		# A short line without an end is a heading: what it heads is the line after it.
		if len(line) < 40 and line[-1] not in ".!?" and at + 1 < len(lines):
			line = f"{line}. {lines[at + 1]}"
		if line not in (kept for _c, _a, kept in scored) and not any(line in kept for _c, _a, kept in scored):
			scored.append((count, at, line))
	scored.sort(key=lambda found: (-found[0], found[1]))
	return [line for _count, _at, line in scored[:MAX_PICKED]], asked


def notMentioned(question):
	"""The honest answer when nothing that was looked up mentions what was asked."""
	said = [word for word in _WORD.findall(_oneWord(question).lower()) if word not in _COMMON and word not in _ASKING]
	said = list(dict.fromkeys(said))[:4]
	if not said:
		return "What was looked up does not answer that."
	return "What was looked up does not mention " + (" or ".join(said)) + "."
