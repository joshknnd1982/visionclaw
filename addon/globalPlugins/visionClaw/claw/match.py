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
	# A text contains the name, or the name contains the text, as whole words. A short text inside a long
	# sentence is no match: a model that wrote "None of the items is the Start menu" once had "te" clicked.
	wantedWords = wanted.split()
	containing = [i for i, text in enumerate(candidates) if text and (
		f" {wanted} " in f" {text} " or (f" {text} " in f" {wanted} " and len(wantedWords) <= len(text.split()) + 2))]
	if containing:
		# The shortest containing text is the closest to what was asked for.
		return min(containing, key=lambda i: abs(len(candidates[i]) - len(wanted)))
	scored = [(difflib.SequenceMatcher(None, wanted, text).ratio(), i) for i, text in enumerate(candidates) if text]
	if not scored:
		return None
	ratio, index = max(scored)
	return index if ratio >= least else None


# What a model writes when the item is not in the list. Such an answer names no item, whatever it shares.
_SAYS_NONE = re.compile(
	r"^\s*(none|nothing|no item|no such|no match|not found|not (in|on) (the|this) list|n/?a|unknown|no matching)\b"
	r"|\b(none of (the|these|them)|is not (in|on|there|listed)|isn'?t (in|on|there|listed)|are not (in|on|there|listed)"
	r"|does not (contain|have|include|exist|appear)|doesn'?t (contain|have|include|exist|appear)|not (found|present|available|listed)"
	r"|cannot (find|be found|see)|can'?t (find|see)|could not (find|be found)|no (item|button|link|icon) (called|named))\b",
	re.IGNORECASE)


def saysNone(reference):
	"""Whether what a model wrote for an item says that there is none, rather than naming one."""
	text = str(reference or "")
	return bool(_SAYS_NONE.search(text)) or len(text.split()) > 12


# Words of a request to click something that say what to do or how, not which thing: they never tell items
# apart. The kind words (button, link, icon) are among them, because a name is compared without its kind.
_NOT_TELLING = frozenset((
	"click", "clicks", "clicking", "double", "right", "left", "middle", "triple", "press", "push", "tap", "hit",
	"activate", "select", "choose", "pick", "open", "find", "locate", "go", "to", "on", "onto", "at", "in", "into",
	"with", "using", "use", "by", "the", "a", "an", "my", "this", "that", "these", "those", "please", "can", "could",
	"would", "will", "you", "me", "i", "want", "need", "like", "let", "for", "it", "its", "of", "and", "then", "now",
	"just", "again", "once", "twice", "mouse", "pointer", "cursor", "button", "buttons", "link", "links", "icon",
	"icons", "tab", "tabs", "item", "items", "menu", "control", "field", "box", "check", "checkbox", "window",
	"screen", "program", "app", "here", "there", "hold", "down", "hover", "over", "point", "rest", "key", "keys",
	"held", "shift", "ctrl", "alt", "place", "part", "top", "bottom", "corner", "edge", "side", "center", "centre",
	"seconds", "second", "visionclaw", "hey", "ok", "okay", "do", "is", "be", "called", "named", "labelled",
	"labeled", "that", "which", "says", "say", "page", "web", "website", "site", "list", "one", "thing"))
# Words that pick an item by its place in a list or on the screen: then the words cannot be compared with names.
_BY_PLACE = re.compile(
	r"\b(first|second|third|fourth|fifth|last|next|previous|number|\d+(st|nd|rd|th)?|other|another|same|"
	r"it|this|that|them|selected|focused|current|highlighted|unlabell?ed|unnamed|nameless|empty)\b", re.IGNORECASE)


def telling(asked):
	"""The words of a request to click something that name the thing, or [] when they cannot be compared with
	names: none are left, or the thing is picked by its place ("the second button", "click it")."""
	text = (asked or "").lower()
	if _BY_PLACE.search(text):
		return []
	return [word for word in _NOT_WORD.sub(" ", text).split() if word not in _NOT_TELLING and len(word) > 1]


def _alike(word, other):
	if word == other:
		return True
	if min(len(word), len(other)) >= 4 and (word.startswith(other[:4]) and other.startswith(word[:4])):
		return True
	# What the text in a picture reads can be a letter off: "Googe hrom" for "Google Chrome".
	return min(len(word), len(other)) >= 4 and difflib.SequenceMatcher(None, word, other).ratio() >= 0.8


def fits(asked, text):
	"""Whether an item's text fits what the user's own words name: at least one word of the name in it, or
	nearly. True when the words cannot be compared with names."""
	named = telling(asked)
	if not named:
		return True
	words = _NOT_WORD.sub(" ", (text or "").lower()).split()
	return any(_alike(word, other) for word in named for other in words)


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
