# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a question about a picture, put to the model that sees in bite-size pieces.
# The owner said on 2026-11-19: "make an orchestrator to understand similar prompts for pictures". People ask about
# a picture in many ways: "what's in the pic", "is there a cat anywhere in this", "how many people are in it",
# "what does the sign say", "what colour is the dress", often several at once. A small model that sees answers one
# plain question better than three run together, and answers it better when it is told what kind of answer is
# wanted. So plain code:
#   1. splits a question into its separate questions ("what is in this photo, and is there any text in it" is two),
#      at most MAX_PIECES, each asked of the model on its own with the same picture;
#   2. tells each question's kind from its words (KINDS: describe, read text, count, is it there, where, colour,
#      people, chart, what is focused), and adds the one short rule of that kind right after the question, where a
#      small model heeds it most. The rules are plain sentences without examples, and never say anything that only
#      sight could follow: the user hears them read back as answers.
#   3. puts the answers together in order, each after its own question, so the user hears which answer is which.
# The user's own words are always the question; nothing is rephrased. No NVDA dependencies.

import re

DESCRIBE, TEXT, COUNT, FIND, WHERE, COLOUR, PEOPLE, CHART, FOCUS = (
	"describe", "text", "count", "find", "where", "colour", "people", "chart", "focus")
MAX_PIECES = 4
# The kinds, in the order they are told apart: the narrowest first. "How many people" is a count; "is there any
# text" is reading the text, which answers whether there is any.
_KINDS = (
	(COUNT, r"\bhow many\b|\bcount\b|\bnumber of\b"),
	(TEXT, r"\bread\b|\btext\b|\bwritten\b|\bwriting\b|\bwords?\b|\bwhat does (?:it|this|that|the [\w ]{1,30}) say\b|\bsays?\b"
		r"|\bcaption\b|\bspell(?:ed|t)?\b"),
	(CHART, r"\b(?:chart|graph|diagram|plot|axis|axes|trend|histogram)s?\b"),
	(COLOUR, r"\bcolou?rs?\b|\bwhat shade\b"),
	(WHERE, r"^\s*where\b|\bwhere (?:is|are|was|were|'s)\b"),
	(FIND, r"^\s*(?:is|are) there\b|\b(?:can you|do you) (?:see|find|spot)\b"
		r"|\bdoes (?:it|this|that|the)(?: [\w'-]+){0,3} (?:have|show|contain|include)\b"
		r"|\bdo (?:they|these|those) (?:have|show)\b|\banywhere\b|^\s*(?:is|are) (?:it|this|that|the [\w ]{1,30}) (?:in|on|shown|visible)\b"),
	(PEOPLE, r"\b(?:who|people|person|persons|man|woman|men|women|child|children|kids?|baby|faces?|anyone|anybody|someone|crowd)\b"),
	(FOCUS, r"\b(?:focused|selected|highlighted|checked|ticked|greyed|grayed|disabled|active|current)\b"),
)
_KIND_PATTERNS = tuple((kind, re.compile(words, re.IGNORECASE)) for kind, words in _KINDS)
# The one rule of each kind, said right after the question.
RULES = {
	DESCRIBE: "Start with what the picture is, in one sentence. Then name the most important things in it, then the "
		"details that matter.",
	TEXT: "Read the text exactly as it is written, in the order it is read. Say which words cannot be read for certain.",
	COUNT: "Count them, and give the number first. If they cannot be counted for certain, say about how many, and that "
		"it is not certain.",
	FIND: "Answer yes or no first. Then say where it is, in words such as top, bottom, left, right or middle.",
	WHERE: "Say where it is in words such as top, bottom, left, right or middle, and what is next to it.",
	COLOUR: "Name the colour in plain words, and say which thing it is the colour of.",
	PEOPLE: "Describe the people: how many there are, what they wear and what they are doing. Never say who someone is.",
	CHART: "Say what kind of chart it is, its title, what each axis or part shows, the main trend, and the numbers that "
		"are written on it.",
	FOCUS: "Say which item is focused, selected, checked, highlighted or greyed out, by its text.",
}
# Where one question ends and the next begins: a question mark with more after it; "and", "also" or a semicolon
# before a word that begins a question or asks for something about the picture.
_ASKS = (r"(?:what|what's|whats|which|who|who's|where|where's|how|is|are|does|do|did|can|could|read|describe|tell me|"
	r"count|any|list|name|say)\b")
_SPLIT = re.compile(rf"\?\s+(?=\S)|\s*;\s*|,?\s+(?:and also|and|also|plus)\s+(?={_ASKS})|,\s+(?={_ASKS})", re.IGNORECASE)


def kindOf(question):
	"""The kind of answer a question about a picture wants, from its words."""
	for kind, pattern in _KIND_PATTERNS:
		if pattern.search(question or ""):
			return kind
	return DESCRIBE


def pieces(question):
	"""A question about a picture as its separate questions, in order, each as (kind, the user's words). One
	question stays one. A piece of fewer than two words belongs to the one before it."""
	text = " ".join(str(question or "").split())
	if not text:
		return []
	parts = []
	for part in _SPLIT.split(text):
		part = part.strip(" ,.;")
		if not part:
			continue
		if parts and len(part.split()) < 2:
			parts[-1] = f"{parts[-1]} {part}"
			continue
		parts.append(part)
	if len(parts) > MAX_PIECES:
		parts = parts[:MAX_PIECES - 1] + [" and ".join(parts[MAX_PIECES - 1:])]
	return [(kindOf(part), part) for part in parts] or [(kindOf(text), text)]


def rule(kind):
	"""The one rule of a kind of question, said right after it."""
	return RULES.get(kind, RULES[DESCRIBE])


def asked(text):
	"""A question as it is said back to the user before its answer."""
	text = text.strip(" ,.;")
	text = text[:1].upper() + text[1:]
	return text if text.endswith("?") else text + "?"


def together(answers):
	"""The answers to the pieces of a question, each after its own question, as one text for the user. answers:
	[(the user's words, the answer)]. One answer is said as it is."""
	if len(answers) == 1:
		return answers[0][1]
	return "\n".join(f"{asked(text)} {answer.strip()}" for text, answer in answers)
