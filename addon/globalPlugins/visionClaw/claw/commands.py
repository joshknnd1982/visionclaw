# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - NVDA's commands as plain data: which command a request is about, and how often its key has to
# be pressed for what was asked. Many NVDA commands do something else on a second or third press: one press
# of NVDA+F12 says the time, two say the date. NVDA says so in the command's own description, so plain code
# reads it there and compares it with the user's own words; no model is asked. No NVDA dependencies.

import re

from . import match, ranking
from .memory import stem, words

MAX_FOUND = 6
# How often to press, as descriptions and people say it. The position in this list is the number of presses.
_TIMES = (
	None,
	re.compile(r"\bonce\b", re.IGNORECASE),
	re.compile(r"\b(twice|two times|a second time|double[- ]?press\w*)\b", re.IGNORECASE),
	re.compile(r"\b(three times|thrice|a third time|triple[- ]?press\w*)\b", re.IGNORECASE),
	re.compile(r"\b(four times|a fourth time)\b", re.IGNORECASE),
)
MAX_PRESSES = len(_TIMES) - 1
_SENTENCE = re.compile(r"(?<=[.!?;])\s+")
# Two things are asked for at once: "the time and the date".
_BOTH = re.compile(r"\b(and|then|plus|also|both)\b|[,;&]", re.IGNORECASE)
# Words that say nothing about which command is meant: they are in most descriptions, or only say to press.
_SAY_NOTHING = frozenset(stem(word) for word in (
	"press pressed pressing presses key keys command will would when information instead again also same").split())
# Words of a request that ask, and are not what is asked for. They count for less than what is asked for.
_ASKING = frozenset(stem(word) for word in "say tell read report speak give show ask announce hear".split())
# Words people use for a command that are not in its name or description, by the number of presses they
# belong to. Kept short: only where the real words of a request were seen to miss.
ALIASES = {
	"dateTime": {1: "clock hour", 2: "day today weekday month year calendar"},
	"say_battery_status": {1: "power charge charging charged charger"},
	"sayAll": {1: "start reading continuous continuously aloud"},
	"showGui": {1: "open menu"},
}


def pressCount(text):
	"""The highest number of presses a text speaks of, or 0 when it speaks of none."""
	return max((count for count in range(1, len(_TIMES)) if _TIMES[count].search(text or "")), default=0)


def _withoutTimes(text):
	"""A text without its "twice" and "three times": the "times" must not make a command look as if it told
	the time."""
	text = str(text or "")
	for pattern in _TIMES[1:]:
		text = pattern.sub(" ", text)
	return text


def byPress(description):
	"""What a command does on the first, second and third press, from its description:
	{1: "reports the current time", 2: "reports the current date"}. A command that does one thing has only 1."""
	found = {}
	for sentence in _SENTENCE.split(" ".join(str(description or "").split())):
		if not sentence:
			continue
		count = max(1, pressCount(sentence))
		found[count] = f"{found[count]} {sentence}" if count in found else sentence
	return found or {1: ""}


def telling(text):
	"""The words of a text that tell one command from another."""
	return words(_withoutTimes(text)) - _SAY_NOTHING


def _ownWords(scriptName, description):
	"""For each number of presses, the words that belong to it."""
	aliases = ALIASES.get(scriptName, {})
	return {count: telling(text) | words(aliases.get(count, "")) for count, text in byPress(description).items()}


def presses(asked, scriptName, description):
	"""How often a command's key must be pressed for what the user asked, as the list of press counts whose
	result is wanted: [1] for the time, [2] for the date, [1, 2] for "the time and the date".
	The user's own words decide: a count is wanted when they use a word that the description only uses for
	that count, and not for a lower one."""
	asked = str(asked or "")
	said = pressCount(_TIMES[1].sub(" ", asked))
	if said > 1:
		return [said]
	own = _ownWords(scriptName, description)
	if len(own) < 2:
		return [1]
	said = telling(asked)
	wanted, lower = [], set()
	for count in sorted(own):
		if count > 1 and said & (own[count] - lower):
			wanted.append(count)
		lower |= own[count]
	if not wanted:
		return [1]
	# The first press is wanted as well when two things are asked for and one is what only it does.
	later = set().union(*(own[count] for count in own if count > 1))
	if _BOTH.search(asked) and said & (own.get(1, set()) - later):
		wanted.insert(0, 1)
	return wanted


def pressText(count):
	return {1: "once", 2: "twice", 3: "three times", 4: "four times"}.get(count, f"{count} times")


def entryWords(scriptName, description, category=""):
	"""(the words of a command's name, the words of its description), for ranking."""
	aliases = " ".join(ALIASES.get(scriptName, {}).values())
	return words(f"{match.label(scriptName)} {aliases}"), telling(f"{description} {category}")


def find(asked, commands, limit=MAX_FOUND):
	"""The commands a request is about, best first. commands: (scriptName, description, category) each.
	Returns their indexes."""
	said = telling(asked)
	return ranking.rank(said, [entryWords(*command) for command in commands], limit, light=_ASKING)
