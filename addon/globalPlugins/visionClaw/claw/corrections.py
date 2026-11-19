# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - learning from the user's corrections. The owner said on 2026-11-19: "all visionclaw orchestrators must
# follow suit and also be flexible and adaptable and understand the meaning of the various ways a user may make
# various requests", and asked for "clever memory save and memory recall". When a request was understood wrongly, the
# user says what they meant: "no, I meant turn off the typing echo", "not that, the volume", "that's not what I asked,
# I wanted the system tray". Plain code reads such a correction (correctionOf): what was meant is done instead, and
# when it went well the user is asked once whether VisionClaw should understand their first words that way from then
# on (offer, question). With a yes, the pair is kept as the user's own words (claw/understand.py, understanding.md in
# VisionClaw's data folder), which the user can read, change and forget, so that the next time the same words are
# understood rightly at once. Nothing is kept without a yes, no model writes or rephrases what is kept, and nothing
# goes online. No NVDA dependencies.

import re

# How long after a request a correction may still be about it, in seconds.
SOON_SECONDS = 600
# The words that are kept must be short enough to be the user's way of saying one thing.
MAX_SAID = 60
MIN_WORDS = 2

_I_MEANT = r"(?:i\s+(?:meant|mean|wanted|want|asked\s+for|was\s+asking\s+for|said)\s+(?:you\s+to\s+|to\s+|for\s+you\s+to\s+)?)"
_CORRECTION = re.compile(
	r"^\s*(?:"
	# no, I meant X / nope, I wanted X / no no, I meant X
	r"(?:no|nope|nah|no\s+no)[\s,.!-]+" + _I_MEANT + r"|"
	# I meant X (not "I want X", which is a request of its own)
	r"i\s+(?:meant|was\s+asking\s+for)\s+(?:you\s+to\s+|to\s+|for\s+you\s+to\s+)?|"
	# not that, X / not that one, I meant X
	r"not\s+(?:that\s+one|this\s+one|that|this|what\s+i\s+(?:meant|wanted|asked(?:\s+for)?))[\s,.!-]+" + _I_MEANT + r"?|"
	# that's not what I meant, I wanted X / that is not what I asked for, X
	r"(?:that'?s|that\s+is|this\s+is|that\s+was)\s+(?:not|wrong|the\s+wrong\s+(?:one|thing))(?:\s+what\s+i\s+(?:meant|wanted|asked(?:\s+for)?|said))?"
	r"[\s,.!-]+" + _I_MEANT + r"?|"
	# wrong, I meant X / wrong one, X
	r"(?:wrong\s+one|wrong\s+thing|wrong)[\s,.!-]+" + _I_MEANT + r"?"
	r")(?P<meant>.+?)\s*$",
	re.IGNORECASE)
# A plain "no, X" is a correction only when X begins with something to do: "no, turn it off" but not "no, that's fine".
_NO_THEN = re.compile(r"^\s*(?:no|nope|nah)[\s,.!-]+(?P<meant>.+?)\s*$", re.IGNORECASE)
_TO_DO = re.compile(
	r"^(?:turn|switch|open|close|read|say|tell|show|go|move|click|press|type|find|search|start|stop|make|set|change|"
	r"put|use|describe|look|list|check|mute|unmute|play|pause|lock|empty|minimize|maximize|maximise|minimise|focus|"
	r"select|copy|paste|save|undo|speak|announce|give|take|bring|switch|launch|run)\b", re.IGNORECASE)
# Words at the end that only say "instead of the last one".
_INSTEAD = re.compile(r"[\s,]*(?:instead|not\s+that(?:\s+one)?|please|thanks|thank\s+you)\s*[.!?]*$", re.IGNORECASE)


def correctionOf(request):
	"""What the user meant, when the request corrects the one before it ("no, I meant X"), or None."""
	text = " ".join(str(request or "").replace("’", "'").split())
	found = _CORRECTION.match(text)
	if not found:
		plain = _NO_THEN.match(text)
		if not plain or not _TO_DO.match(plain.group("meant")):
			return None
		found = plain
	meant = found.group("meant").strip(" ,.!?;:-\"'")
	for _again in range(2):
		meant = _INSTEAD.sub("", meant).strip(" ,.!?;:-\"'")
	return meant if len(meant.split()) >= 1 and len(meant) >= 3 else None


def offer(said, meant, refusal=None):
	"""(said, meant) to offer to keep as the user's own words, or None. said: the request that was understood wrongly, as
	the user said it; meant: what they meant. refusal(said, meant): the user's own words' own check (understand.refusal),
	a sentence when the pair cannot be kept."""
	said = " ".join(str(said or "").strip(" .!?,;:\"'").split())
	meant = " ".join(str(meant or "").strip(" .!?,;:\"'").split())
	if not said or not meant or said.lower() == meant.lower():
		return None
	if len(said) > MAX_SAID or len(said.split()) < MIN_WORDS:
		return None
	# A request that was itself a correction, a request to remember or to teach a word keeps its words as they are.
	if correctionOf(said) or re.search(r'\b(remember|when i say|i mean|means?)\b|"', said, re.IGNORECASE):
		return None
	if refusal is not None:
		try:
			if refusal(said, meant):
				return None
		except Exception:
			return None
	return said, meant


def question(said, meant):
	"""The question that asks whether to keep a correction as the user's own words."""
	return (f"Should VisionClaw understand \"{said}\" as \"{meant}\" from now on? It is kept with your own words in "
		f"VisionClaw's data folder; say \"forget the word {said}\" to undo it.")


YES = "Yes, understand it that way from now on"
NO = "No"
CHOICES = (YES, NO)


__all__ = ["correctionOf", "offer", "question", "CHOICES", "YES", "NO", "SOON_SECONDS"]
