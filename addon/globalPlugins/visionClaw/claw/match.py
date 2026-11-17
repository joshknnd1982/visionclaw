# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - forgiving matching of what a small model writes against what really exists: item names on the
# screen, setting values, key names. Small models write "/80" for 80 and "play button" for "Play"; accuracy
# comes from correcting that here, in plain code. No NVDA dependencies.

import difflib
import re

_NOT_WORD = re.compile(r"[^a-z0-9]+")
_KIND_WORDS = (
	" button", " edit field", " checkbox", " radio button", " link", " heading", " icon", " item", " menu", " tab",
)
_ON = frozenset(("on", "true", "yes", "1", "enable", "enabled", "checked", "always"))
_OFF = frozenset(("off", "false", "no", "0", "disable", "disabled", "unchecked", "never", "none"))


def plain(text):
	"""Lower case, with punctuation and what kind of item it is taken off."""
	text = (text or "").lower().strip()
	for word in _KIND_WORDS:
		if text.endswith(word):
			text = text[:-len(word)]
	return " ".join(_NOT_WORD.sub(" ", text).split())


def best(name, texts, least=0.6):
	"""The index of the text that best matches name, or None if nothing is close enough.
	An exact match wins, then a text that contains the name, then the closest spelling."""
	wanted = plain(name)
	if not wanted:
		return None
	candidates = [plain(t) for t in texts]
	for i, text in enumerate(candidates):
		if text == wanted:
			return i
	containing = [i for i, text in enumerate(candidates) if text and (wanted in text or text in wanted)]
	if containing:
		# The shortest containing text is the closest to what was asked for.
		return min(containing, key=lambda i: abs(len(candidates[i]) - len(wanted)))
	scored = [(difflib.SequenceMatcher(None, wanted, text).ratio(), i) for i, text in enumerate(candidates) if text]
	if not scored:
		return None
	ratio, index = max(scored)
	return index if ratio >= least else None


def itemIndex(reference, texts):
	"""Which item a model means: a number from the list ("3", "item 3", "3."), or else its name."""
	m = re.fullmatch(r"\s*(?:item|number|no\.?|#)?\s*(\d+)\s*[.)]?\s*", str(reference or ""), re.IGNORECASE)
	if m:
		index = int(m.group(1)) - 1
		return index if 0 <= index < len(texts) else None
	return best(reference, texts)


def toBool(raw):
	"""True, False, or None if the text is neither."""
	word = plain(str(raw))
	if word in _ON:
		return True
	if word in _OFF:
		return False
	return None


def toNumber(raw, current=None, low=None, high=None):
	"""A whole number from what a model wrote. "+10" and "-10" change the current value; "80%" and "/80" are 80.
	Raises ValueError with a sentence the model can act on."""
	text = str(raw).strip()
	m = re.search(r"([+-]?)\s*(\d+)", text)
	if not m:
		raise ValueError(f"\"{raw}\" is not a number. Give a whole number.")
	number = int(m.group(2))
	if m.group(1) and current is not None and text.startswith(("+", "-")):
		number = current + number if m.group(1) == "+" else current - number
		if low is not None:
			number = max(low, number)
		if high is not None:
			number = min(high, number)
	if (low is not None and number < low) or (high is not None and number > high):
		raise ValueError(f"{number} is outside the allowed range, {low} to {high}.")
	return number


def toOption(raw, options):
	"""The option a model means, from a list of allowed ones. Raises ValueError naming the allowed ones."""
	index = best(str(raw), [str(o) for o in options], least=0.7)
	if index is None:
		raise ValueError(f"\"{raw}\" is not allowed. Allowed: {', '.join(str(o) for o in options)}.")
	return options[index]


def label(identifier):
	"""A readable name from a setting's identifier: "speakTypedWords" becomes "speak typed words"."""
	text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(identifier)).replace("_", " ")
	return " ".join(text.split()).lower()
