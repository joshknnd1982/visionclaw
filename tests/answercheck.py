# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The words of a final answer, checked by plain code: what every answer must be, and what one answer must say.

Another session said on 2026-11-19 that the evaluation sets checked only which job was chosen, never the words of the
final answer, and the owner asked for it at once. tests/eval_answers.py carries every step out with the stand-ins of
tests/live_orchestrator.py and the real model, and judges the answer with this file; tests/test_answers.py checks the
rules themselves without a model.

Rules for every answer (`problems`). Each is a rule of CLAUDE.md for what the user hears:
- not empty;
- nothing cut (`llm.CUT` and the markers tests/test_whole.py forbids);
- no Markdown, which a screen reader reads out mark by mark;
- nothing only a sighted person can follow ("as you can see", "hover over", "click the blue ...");
- no key that exists nowhere: every key written in the answer is in the request, in what a tool found, among NVDA's
  commands, in VisionClaw's notes on Windows' keys, among VisionClaw's own keys, or in NVDA's user guide where NVDA is
  installed. A key a model made up sends a blind user to press the wrong thing;
- every key written as NVDA writes it, "NVDA+t", never spelled out as "NVDA plus t": a braille display shows the
  words as they are, and keys are copied exactly;
- with one model for both jobs, never "both models", "the other model", "the vision model" or an agreement;
- nothing of the question the model was given ("the information found", "line 2 says", "the user asked"), which
  means nothing to the user;
- no opening words before the answer ("Sure", "Certainly", "Here is"): every answer starts with the answer.
A phrase that a tool's own result or the user's own words contain is not held against the answer: it was not made up
in the answer. Results written by a model (`look`) are no such source, so they are checked like the answer.

What one answer must say (`expected`): an item of an evaluation set may have "says", a list of groups of which every
group must have one phrase in the answer, and "never", phrases that must not be in it. A phrase is found whatever its
case and spacing; a key is found however it is written ("Ctrl+S" is "Control+S"); "re:" begins a regular expression.
"""
import glob
import html
import json
import os
import re

import harness  # noqa: F401
from visionClaw.claw import llm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLUGIN = os.path.join(ROOT, "addon", "globalPlugins", "visionClaw")

EMPTY, CUT, MARKDOWN, SIGHTED, MADE_UP_KEY, SPELLED, TWO_MODELS, SCAFFOLD, PREAMBLE = (
	"empty", "cut", "markdown", "sighted", "made-up key", "key spelled out", "two models", "scaffold", "preamble")
MISSING, NEVER = "missing", "never"
RULES = (EMPTY, CUT, MARKDOWN, SIGHTED, MADE_UP_KEY, SPELLED, TWO_MODELS, SCAFFOLD, PREAMBLE)

# The markers of a cut that tests/test_whole.py forbids.
CUT_MARKS = (llm.CUT.strip(), "left out]")
_MARKDOWN = re.compile(r"\*\*|__|```|`[^`\n]+`|^\s*#{1,6}\s|^\s*[-*•]\s+\S", re.MULTILINE)
# Words that only a sighted person can follow. Places said in words ("at the top of the window") are fine, and the
# mouse is not sighted-only; a colour as the only way to tell a thing is not.
_SIGHTED = re.compile(
	r"\b(as you can see|you can see|you('ll| will) (now )?see|as shown|shown (above|below)|see (above|below)|"
	r"hover over|look at the|look for the|"
	r"click (on )?the (blue|red|green|yellow|orange|purple|grey|gray|white|black)\b|"
	r"(blue|red|green|yellow|orange|purple) (button|icon|link|arrow)s?)\b", re.IGNORECASE)
_TWO_MODELS = re.compile(
	r"\b((both|the two|two) models|the (other|vision|coder|second|reviewing) model|models? (agree|agreed|disagree)\w*)\b",
	re.IGNORECASE)
_SCAFFOLD = re.compile(
	r"\b(information (found|provided|given|above)|the (passages?|lines?) (found|given|above|provided)|"
	r"lines? \d+ (says|said|states|shows)|according to (the )?(information|passages?|lines?|context|text provided)|"
	r"based on the (information|passages?|lines?|context|text provided|results?)|the context (given|provided)|"
	r"the user (asked|wants|said))\b", re.IGNORECASE)
_PREAMBLE = re.compile(
	r"^(sure|certainly|of course|absolutely|great question|good question|i'?d be (happy|glad)|here is|here's|here are|"
	r"okay|ok)\b", re.IGNORECASE)
# How VisionClaw tells the user how their words were understood (understand.taken, followups.taken); the answer
# itself begins after it.
_TAKEN = re.compile(r"^Understood as: .*?[.!?](\s+|$)")

# A key as NVDA and Windows write it: a modifier, then one or more keys joined by +. A model also spells the + out,
# "NVDA plus t": that is the same key, and is found too, so that a made-up key cannot hide behind the word.
_MODIFIERS = r"nvda|control|ctrl|alt|shift|windows|win|insert|caps ?lock"
_JOIN = r"(?:\s?\+\s?|\s+plus\s+)"
KEY = re.compile(
	rf"(?<![\w+])(?:{_MODIFIERS})(?:{_JOIN}(?:(?:up|down|left|right) arrow|page (?:up|down)|caps lock|[a-z0-9]+(?:arrow)?))+",
	re.IGNORECASE)
_SPELLED = re.compile(r"\s+plus\s+", re.IGNORECASE)
_ALIASES = {
	"ctrl": "control", "win": "windows", "esc": "escape", "del": "delete", "ins": "insert", "caps lock": "capslock",
	"pgup": "pageup", "pgdn": "pagedown", "page up": "pageup", "page down": "pagedown", "return": "enter",
	"up": "uparrow", "down": "downarrow", "left": "leftarrow", "right": "rightarrow",
	"up arrow": "uparrow", "down arrow": "downarrow", "left arrow": "leftarrow", "right arrow": "rightarrow",
}


def keyOf(written):
	"""A key as a set of its parts, whatever their order, case and spelling: "Ctrl+S" and "s+control" are one key."""
	parts = [" ".join(part.lower().split()) for part in _SPELLED.sub("+", written).split("+")]
	return frozenset(_ALIASES.get(part, part) for part in parts if part)


def keysIn(text):
	"""Every key written in a text, as sets of parts."""
	return {keyOf(match.group(0)) for match in KEY.finditer(str(text or ""))}


def _plain(text):
	text = str(text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
	return " ".join(text.lower().split())


_known = None


def knownKeys():
	"""Every key that exists for VisionClaw's user: NVDA's commands, VisionClaw's notes on Windows' keys, VisionClaw's
	own keys, and NVDA's user guide where NVDA is installed on this computer."""
	global _known
	if _known is not None:
		return _known
	found = set()
	with open(os.path.join(HERE, "nvda_commands.json"), encoding="utf-8") as f:
		for command in json.load(f):
			for gesture in command["gestures"]:
				if gesture.startswith("kb"):
					found.add(keyOf(gesture.split(":", 1)[1]))
	sources = glob.glob(os.path.join(PLUGIN, "claw", "knowledge", "*.md")) + [os.path.join(PLUGIN, "__init__.py")]
	guide = os.path.join(os.environ.get("ProgramFiles", ""), "NVDA", "documentation", "en", "userGuide.html")
	if os.path.isfile(guide):
		sources.append(guide)
	for path in sources:
		with open(path, encoding="utf-8", errors="replace") as f:
			text = f.read()
		found |= keysIn(html.unescape(re.sub(r"<[^>]+>", " ", text)) if path.endswith(".html") else text.replace("kb:", " "))
	_known = frozenset(found)
	return _known


def _unsourced(pattern, answer, sources):
	"""The phrases of a pattern in the answer that no source has: those were written in the answer itself."""
	return [match.group(0) for match in pattern.finditer(answer) if _plain(match.group(0)) not in sources]


def problems(answer, sources=(), oneModel=False, known=None):
	"""What is wrong with an answer by the rules every answer must keep, as (rule, what) pairs. sources: the user's own
	words and what the tools found, written by plain code; never what a model wrote."""
	answer = str(answer or "")
	plainSources = " \n ".join(_plain(source) for source in sources)
	found = []
	if not answer.strip():
		return [(EMPTY, "the answer is empty")]
	for mark in CUT_MARKS:
		if mark in answer:
			found.append((CUT, mark))
	for match in _MARKDOWN.finditer(answer):
		found.append((MARKDOWN, match.group(0).strip()))
	for phrase in _unsourced(_SIGHTED, answer, plainSources):
		found.append((SIGHTED, phrase))
	if oneModel:
		for phrase in _unsourced(_TWO_MODELS, answer, plainSources):
			found.append((TWO_MODELS, phrase))
	for phrase in _unsourced(_SCAFFOLD, answer, plainSources):
		found.append((SCAFFOLD, phrase))
	start = _TAKEN.sub("", answer.strip(), count=1)
	opening = _PREAMBLE.match(start)
	if opening and _plain(start[:60]) not in plainSources:
		found.append((PREAMBLE, opening.group(0)))
	grounded = set(known if known is not None else knownKeys())
	for source in sources:
		grounded |= keysIn(source)
	for match in KEY.finditer(answer):
		if keyOf(match.group(0)) not in grounded:
			found.append((MADE_UP_KEY, match.group(0)))
		if _SPELLED.search(match.group(0)) and _plain(match.group(0)) not in plainSources:
			found.append((SPELLED, match.group(0)))
	return found


def has(answer, phrase):
	"""Whether the answer has a phrase of an evaluation set: whatever its case and spacing, a key however it is
	written, and a phrase that begins with "re:" as a regular expression."""
	if phrase.startswith("re:"):
		return re.search(phrase[3:], str(answer or ""), re.IGNORECASE) is not None
	if KEY.fullmatch(phrase.strip()):
		return keyOf(phrase) in keysIn(answer)
	return _plain(phrase) in _plain(answer)


def expected(answer, item):
	"""What an item of an evaluation set wants of its answer and did not get, as (rule, what) pairs: a group of
	"says" of which no phrase is there, and a phrase of "never" that is there."""
	found = [(MISSING, " or ".join(group)) for group in item.get("says", ()) if not any(has(answer, p) for p in group)]
	found += [(NEVER, phrase) for phrase in item.get("never", ()) if has(answer, phrase)]
	return found


def judge(answer, sources, item=None, oneModel=False, known=None):
	"""Everything wrong with an answer: the rules for every answer, then what its item wants."""
	return problems(answer, sources, oneModel, known) + (expected(answer, item) if item else [])
