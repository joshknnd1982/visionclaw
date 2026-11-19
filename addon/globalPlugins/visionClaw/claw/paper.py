# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a form that is only a picture: a scanned or flattened PDF, a fax, a photo of a paper form. NVDA finds
# no fields in it; a sighted person sees the printed line next to "Applicant Full Name", clicks on it and types.
# Here the user's own words are read by plain code: which label is meant, whether its line or its check box,
# where the blank lies to the label when the words say so, which of several is meant ("at the bottom"), and what
# is to be typed. A model writes nothing: a label that is copied wrongly clicks in the wrong place.
# What is typed is the user's own text. "My name", "my email", "my phone number" and "my address" are taken from
# what the user asked VisionClaw to remember, word for word, or asked for; they are never made up. Today's date is
# worked out by plain code. VisionClaw never signs for the user: it clicks the line to sign, and the user signs.
# The places themselves are found in the picture by claw/spots.py; the clicking and typing is papertools.py.
# Every sentence the user is told about this is here.
# No NVDA dependencies.

import re

from . import spots

LINE, BOX = "line", "box"
FIRST, LAST = "first", "last"
# What of the user's own can be typed, and how memories word it (claw/memories.py turns "my" into "your").
NAME, EMAIL, PHONE, ADDRESS, DATE, INITIALS = "name", "email address", "phone number", "address", "date", "initials"
_QUOTED = re.compile(r"[\"“”]([^\"“”]{1,80})[\"“”]|(?<![\w])['‘]([^'‘’]{1,80}?)['’](?![\w])")
# A line to write on, as the words say it: a blank, a dotted line, a line next to or under something, the line to
# sign. A line of text that is read, a line number and a command that says a line are something else.
_LINE_WORDS = re.compile(
	r"\b(blank|blanks|dotted|dashed|underscores?|signature line|sign here|empty space|space next to|space beside|space after)\b"
	r"|\bline\s+(?:next to|beside|after|before|to the right of|right of|under|underneath|below|beneath|above|over|labell?ed|"
	r"marked|called|named|titled|that says|that reads|for)\b", re.IGNORECASE)
# "Put my email on the Email line", "click the signature line": a line named by its label, with a word that writes
# or clicks.
_WRITES_ON = re.compile(r"\b(click|type|write|put|sign|enter|fill|print|place|tap)\b", re.IGNORECASE)
_READS = re.compile(
	r"\b(read (?:me|this|that|the|out|it)|reading|current line|next line|previous line|first line|last line|line by line|"
	r"line numbers?|line \d+|commands?|hot ?keys?|shortcuts?|a key|key that|coach|command line)\b", re.IGNORECASE)
_BOX_WORDS = re.compile(r"\b(check ?box|tick ?box|box|square)\b", re.IGNORECASE)
_NOT_BOX = re.compile(r"\b(text|edit|search|combo|list|dialog|message|in) ?box\b", re.IGNORECASE)
# A printed check box is only meant where the words say that this is a paper form or a picture of one; a check
# box of a program or a web page is worked by its own name (claw/controls.py).
_PAPER = re.compile(
	r"\b(pdfs?|scan\w*|printed|paper|flattened|untagged|fax\w*|photo of|picture of|image of|document'?s? picture)\b", re.IGNORECASE)
_TYPES = re.compile(r"\b(type|write|enter|put|print|fill in|fill out|add)\b\s+", re.IGNORECASE)
_TYPED_END = re.compile(
	r"\s+(?:on|in|into|onto|at|to|next to|beside|under|below|above|after|there)\b(?:\s+(?:the|that|this|it)\b)?|[.;!?]\s*$|$", re.IGNORECASE)
_RELATION = re.compile(
	r"\b(next to|beside|after|before|to the right of|right of|under|underneath|below|beneath|above|over|"
	r"labell?ed|marked|called|named|titled|that says|that reads|saying|reading|for|by)\b\s+(?:the\s+)?(?:words?\s+|label\s+|text\s+)?",
	re.IGNORECASE)
_LABEL_END = re.compile(
	r"\s+(?:and|then|so|at the (?:very )?(?:top|bottom|end|start|beginning)|on the (?:page|form|first|last|next)|"
	r"(?:in|on|of|from) (?:this|the|my|that) (?:scanned |printed |flattened |untagged |paper )?(?:pdf|form|document|page|picture|"
	r"image|scan|fax|window)|line|box|blank|field)\b|[,.;!?]|$", re.IGNORECASE)
_NAMED_KIND = re.compile(r"\bthe\s+([\w' -]{2,40}?)\s+(?:line|blank|box|check ?box)\b", re.IGNORECASE)
_SIDES = (
	(spots.UNDER, r"\b(under|underneath|below|beneath)\b"), (spots.ABOVE, r"\b(above|over)\b"),
	(spots.NEXT, r"\b(next to|beside|after|to the right of|right of)\b"))
_LAST = re.compile(r"\b(at the (very )?(bottom|end)|last|lowest|bottom of)\b", re.IGNORECASE)
_FIRST = re.compile(r"\b(at the (very )?(top|start|beginning)|first|topmost|top of)\b", re.IGNORECASE)
_OWN = (
	(INITIALS, r"\b(?:my|our) initials\b"),
	(NAME, r"\b(?:my|our) (?:own |full |whole |legal |first and last )?name\b"),
	(EMAIL, r"\b(?:my|our) e-?mail(?: address)?\b"),
	(PHONE, r"\b(?:my|our) (?:tele)?(?:phone|mobile|cell)(?: number)?\b"),
	(ADDRESS, r"\b(?:my|our) (?:home |postal |mailing |street )?address\b"),
	(DATE, r"\b(?:today'?s date|the date today|the date of today|the current date|the date)\b"),
)
_NOT_LABEL = frozenset(("the", "a", "an", "my", "your", "this", "that", "blank", "dotted", "dashed", "empty", "line", "box"))
# How a memory says each of the user's own facts. A name the user only likes to be called is no name for a form.
_REMEMBERED = {
	NAME: r"\byour (?:own |full |whole |legal )?name is\s+([^.;!?\n]{2,60})",
	EMAIL: r"\byour e-?mail(?: address)? is\s+([^\s;!?\n]+@[^\s;!?\n]+?)[.]?(?:\s|$)",
	PHONE: r"\byour (?:tele)?(?:phone|mobile|cell)(?: number)? is\s+([+(]?\d[\d ()./-]{5,24}\d)",
	ADDRESS: r"\byour (?:home |postal |mailing |street )?address is\s+([^;!?\n]{6,160}?)[.]?\s*$",
	INITIALS: r"\byour initials are\s+([A-Za-z. ]{1,12}?)[.]?\s*$",
}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def _unquote(text):
	text = (text or "").strip()
	found = _QUOTED.fullmatch(text)
	if found:
		return (found.group(1) or found.group(2) or "").strip()
	return text


def _tidyLabel(text):
	words = (text or "").strip(" ,.;:!?'\"‘’“”").split()
	while words and words[0].lower() in _NOT_LABEL:
		words.pop(0)
	while words and words[-1].lower() in ("line", "box", "blank", "field"):
		words.pop()
	return " ".join(words)


def ownOf(text):
	"""Which of the user's own facts some words name ("my full name" is NAME), or None."""
	for what, pattern in _OWN:
		if re.fullmatch(r"\s*(?:in\s+)?" + pattern[2:-2] + r"\s*", text or "", re.IGNORECASE):
			return what
	return None


def wish(part):
	"""What the user's own words ask on a form that is only a picture, or None when they name no line or box of
	such a form: {"label": the printed words the blank belongs to; "kind": LINE or BOX; "side": where the blank
	lies to the label when the words say so (spots.NEXT, UNDER, ABOVE) or spots.ANY; "which": FIRST, LAST or None
	when the label stands there more than once; "typed": the text to type, or None; "own": which of the user's own
	facts is to be typed (NAME, EMAIL, ...), or None; "signs": whether the line is one to sign}."""
	text = " ".join(str(part or "").split())
	low = text.lower()
	if re.search(r"\bhow (do|can|would|should|could) (i|we|you|one)\b|\bhow to\b", low):
		return None
	line = bool(_LINE_WORDS.search(text)) or bool(_NAMED_KIND.search(text) and _WRITES_ON.search(text) and re.search(r"\bline\b", low))
	box = bool(_BOX_WORDS.search(text)) and not _NOT_BOX.search(text) and not line
	if box and not _PAPER.search(text):
		return None
	if not box and (not line or _READS.search(text)):
		return None
	# What is to be typed is taken out first, so that it is never taken for the label.
	typed, own, rest = None, None, text
	types = _TYPES.search(text)
	if types and not box:
		after = text[types.end():]
		quoted = _QUOTED.match(after)
		if quoted:
			typed = (quoted.group(1) or quoted.group(2)).strip()
			rest = text[:types.start()] + " " + after[quoted.end():]
		else:
			end = _TYPED_END.search(after)
			said = after[:end.start()].strip(" ,")
			# "Type on the line next to ..." names no text: the words after it are where, not what.
			if said and not re.match(r"(?:the|a|that|this|it|there|here)\b", said, re.IGNORECASE):
				typed = said
				rest = text[:types.start()] + " " + after[end.start():]
		if typed is not None:
			own = ownOf(typed)
			if own:
				typed = None
	label = None
	quoted = _QUOTED.search(rest)
	if quoted:
		label = _tidyLabel(quoted.group(1) or quoted.group(2))
	if not label:
		for found in _RELATION.finditer(rest):
			tail = rest[found.end():]
			label = _tidyLabel(tail[:_LABEL_END.search(tail).start()])
			if label and not re.fullmatch(r"(?:it|there|here|that|this|me|you)", label, re.IGNORECASE):
				break
			label = None
	if not label:
		named = _NAMED_KIND.search(rest)
		if named:
			label = _tidyLabel(named.group(1))
	if not label or len(label) < 2:
		return None
	side = next((value for value, pattern in _SIDES if re.search(pattern, rest, re.IGNORECASE)), spots.ANY)
	which = LAST if _LAST.search(rest) else FIRST if _FIRST.search(rest) else None
	signs = bool(re.search(r"\b(sign|signature|initial)\w*\b", low))
	return {"label": label, "kind": BOX if box else LINE, "side": side, "which": which, "typed": typed, "own": own,
		"signs": signs and typed is None and own is None}


def remembered(what, bodies):
	"""One of the user's own facts, word for word, from what they asked VisionClaw to remember: bodies are the
	texts of the memories, the newest last. None when no memory says it."""
	pattern = _REMEMBERED.get(what)
	if pattern is None:
		return None
	for body in reversed(list(bodies or ())):
		for line in str(body or "").splitlines():
			found = re.search(pattern, line.strip(), re.IGNORECASE)
			if found:
				return found.group(1).strip(" ,")
	return None


def today(year, month, day):
	"""Today's date written out, so that it cannot be read as another day: November 19, 2026."""
	return f"{MONTHS[month - 1]} {day}, {year}"


def ownQuestion(what):
	"""Asked when VisionClaw does not know one of the user's own facts."""
	return (
		f"What should be typed as your {what}? VisionClaw does not know it. To be asked only once, say afterwards: "
		f"remember that my {what} is, and then your {what}.")


def choose(places, which):
	"""Which of several places a label was found at is meant: its index, or None when the words do not say."""
	if len(places) == 1:
		return 0
	if which == FIRST:
		return 0
	if which == LAST:
		return len(places) - 1
	return None


def whichQuestion(label, count):
	return f"The words \"{label}\" stand in this picture {count} times. Which one do you mean?"


def placeChoices(places, size):
	"""The places a label was found at, each in words, for the user to choose from."""
	return [f"Number {index}, {spots.whereText(box, size)}" for index, box in enumerate(places, 1)]


def thing(wished, how, dotted=False):
	"""The blank in words: "the dotted line above Authorized Signature"."""
	if wished["kind"] == BOX:
		return f"the check box at \"{wished['label']}\""
	line = "dotted line" if dotted else "line"
	return f"the {line} {spots.HOW.get(how, 'at')} \"{wished['label']}\""


def question(wished, how, typed, dotted=False, written=False, ticked=None):
	"""Asked before VisionClaw clicks on the form, and types."""
	what = thing(wished, how, dotted)
	if wished["kind"] == BOX:
		state = " It looks ticked already." if ticked else " It looks empty." if ticked is not None else ""
		return f"Click {what} with the mouse?{state}"
	already = " Something seems to be written on that line already." if written else ""
	if typed:
		return f"Click {what} with the mouse and type \"{typed}\"?{already}"
	return f"Click {what} with the mouse?{already}"


def notFound(wished, seen):
	"""Said when the label is not in the text read from the picture. seen: whether any text was read at all."""
	if not seen:
		return (
			"Nothing was clicked: no text could be read in the picture of this window, so the form's labels could "
			"not be found. If the form is small on the screen, zoom in and ask again.")
	return (
		f"Nothing was clicked: the words \"{wished['label']}\" were not found in the text of this window's picture. "
		"They may be on another page or further down: scroll or go to that page and ask again, or say the label as "
		"it is printed.")


def noBlank(wished):
	what = "check box" if wished["kind"] == BOX else "line to write on"
	return (
		f"Nothing was clicked: \"{wished['label']}\" was found, but no {what} next to it, under it or above it. "
		"The form may use a box or a shaded area there: pointer mode, NVDA+Alt+K, lets you put the mouse pointer "
		"there yourself.")


def done(wished, how, typed, dotted=False, shows=None, changed=None):
	"""What was done, and what was seen afterwards. shows: whether the typed text was read back at the place
	(None when it could not be checked). changed: whether the picture changed at the place after a click alone."""
	what = thing(wished, how, dotted)
	if wished["kind"] == BOX:
		said = f"Clicked {what}."
		if changed is True:
			return said + " The picture of the box changed, so the click was taken."
		if changed is False:
			return said + " Nothing VisionClaw can see changed there, so the box may not have taken the click."
		return said
	if typed:
		said = f"Clicked {what} and typed \"{typed}\"."
		if shows is True:
			return said + " The text is now read there in the picture."
		if shows is False:
			return (
				said + " VisionClaw could not read the text back at that place. The form may need its fill tool chosen "
				"first, or the text may be too small to read: ask to read the text of the window to check.")
		return said
	said = f"Clicked {what}."
	if wished["signs"]:
		said += " VisionClaw does not sign for you: place your signature now, with the program's own way of signing."
	elif changed is False:
		said += " Nothing VisionClaw can see changed there."
	return said


NO_WISH = (
	"The request does not say which line or box of the form is meant. Say the printed words it belongs to, such as: "
	"click the line next to Full Name and type my name.")
NOT_TYPED = "Nothing was typed, because nothing was given to type."
