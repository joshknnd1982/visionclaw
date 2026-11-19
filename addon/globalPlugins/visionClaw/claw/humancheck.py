# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - checks on web pages that ask whether the visitor is a person ("I'm not a robot", "Verify you are
# human", a puzzle of pictures, a piece to drag). They are made to stop programs, and they shut out blind people
# wherever the way without sight is missing or broken. A screen reader's job is to make what is on the screen
# perceivable and workable for the person in front of it, and that is all VisionClaw does here:
#   - it says which kind of check the page has, and names the ways through it that need no sight first;
#   - it presses the check's box for the person where the keyboard cannot reach it;
#   - it reads out what a puzzle asks, word for word, and says what each square shows, one square at a time;
#   - it clicks the squares THE PERSON names by their numbers, and a button of the check the person names;
#   - it turns on pointer mode on a handle that must be dragged, so that the person drags it with the arrow keys.
# THE PERSON ANSWERS THE CHECK. The line that must hold, here, in checktools.py and in every sentence:
#   - VisionClaw never decides which squares are selected. Nothing in this file takes what a puzzle asks for and
#     gives back squares. A model is asked what ONE square shows, in a few words, and is never told what the puzzle
#     asks for; it is never asked whether a square fits. The numbers come from the user's own words only (numbers).
#   - Nothing is done in the background, nothing without the user asking in that very request, and nothing is
#     tried again by VisionClaw itself. Every press is asked about first, always, whatever the settings say.
#   - Nothing imitates a hand: no made-up paths, pauses or timing, no change to how the browser shows itself, and
#     no service outside this computer. A click is a plain click, and the check may well notice that.
#   - The rule that a challenge put to VisionClaw's own downloads is not worked around is untouched by all this.
# The user is told plainly that these checks are built to be hard for programs, so this will not always get
# through, and that the check's own audio challenge or accessibility option, where it works, is the surer way.
#
# What the ways without sight are was read from each provider's own pages on 2026-11-19, not remembered:
#   - Google, "reCAPTCHA accessibility", support.google.com/recaptcha/answer/6175971: works with screen readers;
#     status messages under "recaptcha status" ("Recaptcha requires verification", "Opening verification challenge",
#     "You are verified", "Verification expired, check the checkbox again for a new challenge"); the buttons "Get an
#     audio challenge", PLAY, "Verify", "Get a new challenge"; R replays the sound in its text box; the link
#     "Alternatively, download audio as MP3"; force forms mode if the screen reader does not enter it; the
#     verification expires, so do it last.
#   - hCaptcha, hcaptcha.com/accessibility: an "Accessibility Challenge" in the widget's menu where the site turned
#     it on, which is text only; an accessibility sign-up that gives an encrypted cookie through an email login link,
#     usable several times a day, which needs cross-site cookies for hcaptcha.com; no audio challenge is described.
#   - Cloudflare, developers.cloudflare.com/turnstile/concepts/widget and .../frequently-asked-questions: in managed
#     mode "the visitor will be prompted to select a box", "There will be no images or text to decipher"; when the
#     interaction times out the page or the widget must be loaded again; "Turnstile is WCAG 2.2 AA compliant". The
#     pages do not give the words written next to the box, so none are quoted as Cloudflare's.
#   - Arkose Labs, arkoselabs.com/accessibility: says nothing about how its puzzles are done without sight, so no
#     way is named for it here.
# NVDA's keys named here (X the next check box, B the next button, E the next edit field, NVDA+Space for focus
# mode) are in the user guide of NVDA 2026.3.1; tests/test_humancheck.py asks the installed guide for them.
# Which check a page has is told from the provider's name in the titles of its frames and in its text; the exact
# titles were not read anywhere and are not relied on.
# No NVDA dependencies. Pictures are PIL images; boxes are (left, top, right, bottom) in picture pixels.

import re

from . import spots
from .tools import RESULT_CHARS

RECAPTCHA, HCAPTCHA, TURNSTILE, ARKOSE, SLIDER, TEXT, UNKNOWN = (
	"recaptcha", "hcaptcha", "turnstile", "arkose", "slider", "text", "unknown")
# What the check shows at the moment: its box, or a puzzle.
BOX, PUZZLE = "box", "puzzle"
# What the user's words ask of VisionClaw.
TELL, PRESS_BOX, DESCRIBE, SELECT, VERIFY, HOLD = "tell", "press box", "describe", "select", "verify", "hold"
# The buttons of a check that the user can name.
B_VERIFY, B_SKIP, B_NEXT, B_AUDIO, B_NEW = "verify", "skip", "next", "audio", "new"
# A puzzle of more squares than this is not described: no check VisionClaw knows of has more.
MAX_SQUARES = 16
# How much of a square's description is kept.
SQUARE_CHARS = 70

NAMES = {
	RECAPTCHA: "Google's reCAPTCHA", HCAPTCHA: "hCaptcha", TURNSTILE: "Cloudflare's Turnstile",
	ARKOSE: "an Arkose Labs puzzle", SLIDER: "a check with a piece or a handle to drag",
	TEXT: "a check that shows letters to type", UNKNOWN: "a check that asks whether you are a person",
}
_KINDS = (
	(TURNSTILE, r"\bcloudflare\b|\bturnstile\b"),
	(RECAPTCHA, r"\bre ?captcha\b"),
	(HCAPTCHA, r"\bh ?captcha\b"),
	(ARKOSE, r"\barkose\b|\bfun ?captcha\b"),
	(SLIDER, r"\bslide to (verify|unlock|complete|continue)\b|\bdrag the (slider|piece|puzzle)\b|\bslider (puzzle|captcha|verification)\b"
		r"|\bpuzzle piece\b|\bgeetest\b|\bslide the\b|\bdrag to (verify|complete)\b"),
	(TEXT, r"\b(type|enter) the (characters|letters|text|code|words?) (you see|shown|in the (image|picture)|above|below)\b"),
	(UNKNOWN, r"\bcaptcha\b|\bverify (that )?you are (a )?human\b|\b(i'?m|i am) not a robot\b|\bi am human\b|\bare you a robot\b"
		r"|\bprove (that )?you('re| are) (a )?human\b|\bhuman verification\b|\bnot a bot\b|\bverif\w+ (that )?you('re| are) not a (robot|bot)\b"
		# What a puzzle of pictures asks names a check too, where nothing else does.
		r"|\bselect (all|each|every) (squares?|images?|pictures?|tiles?) (with|containing|that)\b|\bclick verify once\b"
		r"|\bclick (on )?(each|every) (image|picture|square) (containing|with)\b"),
)
_KIND_PATTERNS = tuple((kind, re.compile(words, re.IGNORECASE)) for kind, words in _KINDS)
# What a puzzle asks begins with one of these.
_ASKS = re.compile(
	r"\b(select all|select each|select every|click (on )?(each|every|all)|pick (the|all|each)|choose (the|all|each)|tap (on )?(each|every|all)|"
	r"please (select|click|pick|choose|solve)|use the arrows|rotate the|drag the|slide the|move the|slide to|match the)\b", re.IGNORECASE)
_DANGLING = re.compile(r"\b(with|containing|of|the|a|an|to|that)\s*$", re.IGNORECASE)
_MORE = re.compile(r"\b(click|press|select|tap) (on )?(verify|skip|next)\b|\bif there are none\b|\bonce there are none\b", re.IGNORECASE)
_STATUS = re.compile(
	r"\b(you are verified|verification expired|verification challenge expired|requires verification|opening verification challenge|"
	r"please try again|try again|incorrect|expired|verified|success|failed|error)\b", re.IGNORECASE)
# The words written next to the box of a check, as people know them; used only to find the box in a picture.
BOX_WORDS = ("Verify you are human", "I'm not a robot", "I am human", "I am not a robot")

_NUMBER_WORDS = {
	"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
	"eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
	"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
	"tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
}
_NUMBER = re.compile(
	r"\b(\d{1,2})(?:st|nd|rd|th)?\b|\b(" + "|".join(_NUMBER_WORDS) + r"|last)\b", re.IGNORECASE)
# A number that counts something else than a square.
_NOT_A_SQUARE_AFTER = re.compile(
	r"\s*(?:by|x|\u00d7)\s*\d|\s*(?:seconds?|minutes?|times?|percent|%|pixels?|steps?|more|rows?|columns?|at a time|of them)\b", re.IGNORECASE)
# "One" is a number only where numbers are being said: at the start, in a list, or after the word for a square or
# for selecting. In "this one", "the last one" and "the larger one" it stands for a thing.
_ONE_BEFORE = re.compile(
	r"(?:^|[,;]|\b(?:squares?|tiles?|images?|pictures?|photos?|boxes|cells?|numbers?|select|click|pick|choose|tap|press|tick|mark|"
	r"check|hit|take|and|or|plus|then))\s*$", re.IGNORECASE)
_SQUARE_NOUN = r"(?:squares?|tiles?|images?|pictures?|photos?|boxes|cells?|numbers?|ones?)"
_SELECTS = re.compile(r"\b(select|click|pick|choose|tap|press|tick|mark|check|hit|take|deselect|unselect|untick)\b", re.IGNORECASE)
# The words that ask VisionClaw to choose the squares by what they show. It never does; the user is told so.
_BY_CONTENT = re.compile(
	rf"\b{_SQUARE_NOUN}\s+(?:with|containing|showing|of|that (?:show|have|contain|include|match|fit)\w*|which (?:show|have|contain|match)\w*)\b"
	rf"|\bwhich (?:of the )?{_SQUARE_NOUN}\b|\b(?:everything|anything|all|those|the ones) (?:with|containing|showing|that (?:show|have|contain|match)\w*)\b"
	r"|\bthe (?:right|correct|matching) (?:squares?|tiles?|images?|pictures?|ones?)\b", re.IGNORECASE)
# The words that ask VisionClaw to get through the whole check by itself. It never does; the user is told what it does.
_WHOLE = re.compile(
	r"\b(solve|bypass|crack|beat|defeat|get (?:me |us )?(?:past|through|around|by)|get rid of|pass (?:this|the|that|it)|"
	r"complete (?:this|the|that|it)|finish (?:this|the|that|it)|do (?:this|the|that|my) (?:captcha|check|puzzle|verification|challenge)|"
	r"answer (?:this|the|that|it)|take care of|deal with|"
	r"handle (?:this|that|it|my|the (?:captcha|check|puzzle|verification|challenge)))\b", re.IGNORECASE)
_TELLS = re.compile(
	r"\bwhat (?:kind|type|sort) of\b|\bwhich (?:kind|type|sort) of\b|\bmy options\b|\bwhat can (?:i|you|we) do\b|\bwhat are the ways\b"
	r"|\bhow (?:do|can|could|would|should) (?:i|we|you)\b|\bis there an? (?:audio|accessible|other|another)\b|\bwhat ways\b"
	r"|\bis (?:this|that|there) a (?:captcha|check)\b", re.IGNORECASE)
_DESCRIBES = re.compile(
	r"\b(describe|what(?:'s| is| are| does| do)|tell me (?:what|about)|read (?:out |me )?(?:the|what)|say what|explain|"
	r"what (?:it|the puzzle|the check|the captcha|the challenge) (?:asks|wants|says|shows))\b", re.IGNORECASE)
_HOLDS = re.compile(r"\b(sliders?|slide|drag\w*|puzzle piece|jigsaw|piece|handle)\b", re.IGNORECASE)
_BOX_LABEL = re.compile(
	r"\bverify (?:that )?(?:you are|i am|i'm|you're) (?:a )?human\b|\b(?:i'?m|i am) not a robot\b|\bi am human\b|\bnot a robot\b", re.IGNORECASE)
_BOX_NOUN = re.compile(r"\b(check ?box|tick ?box|box)\b", re.IGNORECASE)
_PRESSES = re.compile(r"\b(click|press|check|tick|select|activate|hit|push|tap|mark)\b", re.IGNORECASE)
_BUTTONS = (
	(B_AUDIO, r"\baudio\b|\bsound\b|\blisten\b"),
	(B_NEW, r"\b(?:new|another|different) (?:challenge|puzzle|one|pictures?|images?|set)\b|\breload\b|\brefresh\b"),
	(B_SKIP, r"\bskip\b"),
	(B_VERIFY, r"\bverify\b|\bsubmit\b|\bdone\b|\bconfirm\b"),
	(B_NEXT, r"\bnext\b|\bcontinue\b"),
)
_THEN = re.compile(r"\b(?:then|and|afterwards|after that)\s+(?:press |click |hit |push |tap )?(?:the |on )?(verify|skip|next|submit|done|confirm|continue)\b", re.IGNORECASE)
# How each button a user can name is found among a check's own buttons, by its name.
BUTTON_WORDS = {
	B_VERIFY: r"\b(verify|submit|done|confirm|check)\b", B_SKIP: r"\bskip\b", B_NEXT: r"\b(next|continue)\b",
	B_AUDIO: r"\baudio\b", B_NEW: r"\bnew challenge\b|\breload\b|\brefresh\b|\bnew\b",
}

# Said with everything this tool does. The user must never think that getting through is promised.
NOTICE = (
	"These checks are built to be hard for programs, so this will not always get through, and the site may ask again. "
	"Where it works, the check's own audio challenge or accessibility option is the surer way.")
SHORT_NOTICE = "If the site asks again: its own audio challenge or accessibility option, where it works, is the surer way."
OFFERS = (
	"VisionClaw can press the check's box for you, say what a puzzle asks and what each square shows, click the "
	"squares you name by their numbers, press a button of the check you name, and turn on pointer mode on a handle "
	"that must be dragged. It does not choose an answer: you answer the check.")
NOT_CHOSEN = (
	"VisionClaw does not choose the squares: the check is asking you. It says what each square shows, and you then "
	"say which numbers to select.")
NO_NUMBERS = (
	"Nothing was clicked: the request names no squares by their numbers. Ask what the squares show, then say which "
	"numbers to select.")
NO_CHECK = (
	"VisionClaw finds no check here that asks whether you are a person: nothing on the web page as NVDA has it, and "
	"nothing in the text of the window's picture, names one. If one is on the screen, move NVDA to it and ask again.")
NO_SQUARES = (
	"No grid of squares was found in the picture of this window. The check may show its box only and no puzzle yet, "
	"its puzzle may be of another kind, or it may be partly off the screen: scroll so that all of it shows, and ask again.")
STILL = "The check is still there."
NO_BOX = (
	"Nothing was pressed: VisionClaw found no check box of the check, neither on the web page as NVDA has it nor "
	"next to its words in the picture of the window.")
# What the model that sees is asked about one square. It is never told what the puzzle asks for.
SQUARE_PROMPT = (
	"This picture is one square of a grid of pictures on a web page. Say what the square shows, in at most eight "
	"words. Name the things in it. If you cannot tell what it shows, say that it is unclear.")
ONE_SQUARE_PROMPT = (
	"This picture is one square of a grid of pictures on a web page. Say what it shows in two short sentences: the "
	"main thing first, then what else is in it, also at its edges. If you cannot tell what it shows, say that it is unclear.")
GAP_PROMPT = (
	"This picture shows part of a web page where a piece or a handle must be dragged along a track, often into an "
	"empty cut-out of its shape. Say in two short sentences where the piece or handle is now and where the empty "
	"cut-out is: left, middle or right, and about how many tenths of the way across the picture each one is. If you "
	"cannot see a piece or a cut-out, say so.")


def isCheck(text):
	"""Whether a frame's title or a line of text names a check that asks whether the visitor is a person."""
	return any(pattern.search(text or "") for _kind, pattern in _KIND_PATTERNS)


# The words of a request that is about such a check, for the planner. "Check the box next to I agree", "press
# verify", "select all" and "turn the slider up" are not: they are an ordinary click or control.
_ABOUT = re.compile(
	r"\b(re ?captchas?|h ?captchas?|captchas?|turnstile|fun ?captcha)\b"
	r"|\bverify (that )?(you are|i am|i'm|you're) (a )?human\b|\b(i'?m|i am) not a robot\b|\bnot a robot\b|\bi am human\b"
	r"|\bprove (that )?(i'?m|i am|you are|you're) (a )?(human|person|not a (robot|bot))\b"
	r"|\b(human|robot|bot) (check|verification|test)\b|\b(security|verification) (challenge|puzzle)\b"
	r"|\bselect (all|each|every) (the )?(squares?|images?|pictures?|tiles?) (with|containing|that|showing)\b"
	r"|\b(select|click|pick|choose|tap|tick|mark) (the )?(squares?|tiles?) (number )?(\d{1,2}|one|two|three|four|five|six|seven|eight|nine)\b"
	r"|\b(select|click|pick|choose|tap) \d{1,2}\b.{0,40}\b(then|and) (press |click |hit )?(the )?(verify|skip)\b"
	r"|\b(describe|what (is|are|do|does|'s)|tell me what)\b.{0,30}\b(squares?|tiles?) ?(\d{1,2}|show|have|hold|of the (puzzle|check))\b"
	r"|\bdescribe (the |each |every )?(squares?|tiles?)\b"
	r"|\baudio challenge\b|\bpuzzle piece\b|\bslider (puzzle|captcha|check)\b|\bslide to verify\b"
	r"|\bcloudflare\b.{0,40}\b(check ?box|box|verif\w+|challenge)\b", re.IGNORECASE)


def about(part):
	"""Whether a request's own words are about a check that asks whether the visitor is a person."""
	return bool(_ABOUT.search(str(part or "")))


def kindOf(frames, texts):
	"""Which check a page has: from the titles of its frames first, then from the text NVDA or the picture gives.
	None when nothing names a check. A provider's name tells more than words every check uses."""
	for source in (frames, texts):
		joined = " \n ".join(str(item or "") for item in source or ())
		for kind, pattern in _KIND_PATTERNS:
			if kind != UNKNOWN and pattern.search(joined):
				return kind
	joined = " \n ".join(str(item or "") for item in list(frames or ()) + list(texts or ()))
	return UNKNOWN if _KIND_PATTERNS[-1][1].search(joined) else None


def asksOf(texts):
	"""What a puzzle asks, word for word, from the lines of text of the check; "" when no line asks anything. A
	line that breaks off is joined with the next, and the line that says when to press Verify or Skip is added."""
	lines = [" ".join(str(line or "").split()) for line in texts or ()]
	lines = [line for line in lines if line]
	for index, line in enumerate(lines):
		if not _ASKS.search(line):
			continue
		said = [line]
		at = index + 1
		if _DANGLING.search(line) and at < len(lines):
			said.append(lines[at])
			at += 1
		text = " ".join(said)
		for more in lines[at:at + 3]:
			if _MORE.search(more) and more not in said:
				said.append(more)
				text += ("" if text[-1:] in ".!?" else ".") + " " + more
		return text if len(text) <= 220 else text[:220].rsplit(" ", 1)[0] + " ..."
	return ""


def statusOf(texts):
	"""What the check itself says of its state, word for word: at most two short lines of its own text."""
	found = []
	for line in texts or ():
		line = " ".join(str(line or "").split())
		if line and len(line) <= 120 and _STATUS.search(line) and not _ASKS.search(line) and line not in found:
			found.append(line)
	return " ".join(found[:2])


def stageOf(texts, squares=0):
	"""Whether the check shows a puzzle (it asks something, or squares were found) or only its box."""
	return PUZZLE if asksOf(texts) or squares else BOX


def numbers(part, count):
	"""The numbers of the squares that the user's own words name, each from 1 to count, in the order they are
	said and each once: "squares 1, 4 and 7", "the second and the last". A number that counts something else ("3 by
	3", "2 times") is none. Words that name no number give []."""
	text = " ".join(str(part or "").split())
	found = []
	for hit in _NUMBER.finditer(text):
		if _NOT_A_SQUARE_AFTER.match(text[hit.end():]):
			continue
		word = (hit.group(2) or "").lower()
		if word == "one" and not _ONE_BEFORE.search(text[:hit.start()]):
			continue
		if hit.group(1) and re.search(r"(?:\bby|\bx|\u00d7)\s*$", text[:hit.start()], re.IGNORECASE):
			continue
		value = int(hit.group(1)) if hit.group(1) else count if word == "last" else _NUMBER_WORDS[word]
		if 1 <= value <= count and value not in found:
			found.append(value)
	return found


def wish(part):
	"""What the user's own words ask about a check: {"what": TELL, PRESS_BOX, DESCRIBE, SELECT, VERIFY or HOLD;
	"button": which button for VERIFY (B_VERIFY, B_SKIP, B_NEXT, B_AUDIO, B_NEW); "then": a button to press after
	the squares, or None; "squares": whether single squares are named for DESCRIBE or SELECT; "byContent": the words
	want the squares chosen for the user by what they show; "wholeCheck": the words want the whole check done for
	the user}. The last two are never done; they turn the request into telling and describing."""
	text = " ".join(str(part or "").split())
	found = {"what": TELL, "button": None, "then": None, "squares": False, "byContent": False, "wholeCheck": False}
	if _BY_CONTENT.search(text):
		found.update(what=DESCRIBE, byContent=True)
		return found
	if _WHOLE.search(text):
		found.update(wholeCheck=True)
		return found
	if _TELLS.search(text):
		return found
	named = bool(numbers(text, 99))
	if _DESCRIBES.search(text):
		found.update(what=DESCRIBE, squares=named and bool(re.search(rf"\b{_SQUARE_NOUN}\b", text, re.IGNORECASE)))
		return found
	if _BOX_LABEL.search(text) and _PRESSES.search(text):
		found.update(what=PRESS_BOX)
		return found
	if named and (_SELECTS.search(text) or re.search(rf"\b{_SQUARE_NOUN}\b", text, re.IGNORECASE)):
		then = _THEN.search(text)
		found.update(what=SELECT, squares=True, then=buttonOf(then.group(1)) if then else None)
		return found
	if _SELECTS.search(text) and re.search(rf"\b(all|every|each|everything)\b.{{0,20}}\b{_SQUARE_NOUN}\b|\ball of them\b", text, re.IGNORECASE):
		found.update(what=SELECT, squares=True)
		return found
	if _HOLDS.search(text):
		found.update(what=HOLD)
		return found
	if _BOX_NOUN.search(text) and _PRESSES.search(text):
		found.update(what=PRESS_BOX)
		return found
	button = buttonOf(text)
	if button is not None and (_PRESSES.search(text) or re.search(r"\b(get|use|switch to|give me|open|play|now|go)\b", text, re.IGNORECASE)
			or re.match(r"\s*(?:(?:please|now|then|and|just)\s+)*(?:skip|verify|next|submit|continue|reload|refresh|confirm)\b", text, re.IGNORECASE)):
		found.update(what=VERIFY, button=button)
		return found
	return found


def buttonOf(text):
	"""Which button of a check some words name, or None."""
	for button, pattern in _BUTTONS:
		if re.search(pattern, text or "", re.IGNORECASE):
			return button
	return None


def buttonIn(button, names):
	"""Which of a check's own buttons, by their names, is the one the user named: its index, or None."""
	pattern = re.compile(BUTTON_WORDS[button], re.IGNORECASE)
	return next((index for index, name in enumerate(names) if pattern.search(name or "")), None)


def _plainRows(area):
	"""For each row of a picture, whether it is one plain tone from end to end."""
	grey = area.convert("L")
	width, height = grey.size
	data = grey.tobytes()
	return [max(data[y * width:(y + 1) * width]) - min(data[y * width:(y + 1) * width]) <= 14 for y in range(height)]


def _clip(box, size):
	left, top, right, bottom = (int(round(value)) for value in box)
	left, top = max(0, left), max(0, top)
	right, bottom = min(size[0], right), min(size[1], bottom)
	return (left, top, right, bottom) if right - left >= 16 and bottom - top >= 16 else None


def squaresIn(image, areas=(None,)):
	"""The squares of a puzzle of pictures in a picture: (rows, columns, [the box of every square, row by row]),
	or None. areas: where to look, the likeliest first; each a box, or None for the whole picture. An area may
	hold more than the grid, as a check's frame holds its heading and its buttons: then the rows of squares are
	told from the bands of equal height between plain rows, and the grid is looked for in them alone. Squares are
	numbered from 1, left to right and from the top down, the way a person reads them out."""
	for area in areas:
		box = _clip(area, image.size) if area is not None else (0, 0, image.size[0], image.size[1])
		if box is None:
			continue
		found = spots.grid(image, box)
		if found is None:
			# The bands between plain rows: a heading, the rows of squares, the buttons.
			plain = _plainRows(image.crop(box))
			bands, start = [], None
			for index, value in enumerate(plain + [True]):
				if not value and start is None:
					start = index
				elif value and start is not None:
					bands.append((start, index))
					start = None
			best = None
			for first in range(len(bands)):
				tall = bands[first][1] - bands[first][0]
				last = first
				while last + 1 < len(bands) and abs((bands[last + 1][1] - bands[last + 1][0]) - tall) <= max(3, tall * 0.15):
					last += 1
				if last > first and tall >= 24 and (best is None or last - first > best[1] - best[0]):
					best = (first, last)
			if best is not None:
				found = spots.grid(image, (box[0], box[1] + bands[best[0]][0], box[2], box[1] + bands[best[1]][1]))
		if found is not None and 4 <= len(found[2]) <= MAX_SQUARES:
			return found
	return None


def areasFor(size, frames=(), asks=None):
	"""Where a puzzle's squares are looked for in a picture, the likeliest first: the boxes of the check's frames,
	the largest first; then what lies under the words that say what the puzzle asks; then the whole picture."""
	found = sorted((box for box in frames if box is not None), key=lambda box: -(box[2] - box[0]) * (box[3] - box[1]))
	if asks is not None:
		width, height = size
		tall = max(8, asks[3] - asks[1])
		for share in (0.6, 0.45, 0.3):
			found.append((max(0, asks[0] - 3 * tall), asks[3], min(width, asks[0] + share * width), height))
	return found + [None]


def describeSome(part, count):
	"""Which squares a request to describe names, or all of them: [numbers from 1]."""
	named = numbers(part, count) if wish(part)["squares"] else []
	return named or list(range(1, count + 1))


def kindText(kind, stage=None, asks="", status=""):
	"""Which check this is and what it shows now, for the user."""
	said = f"This is {NAMES.get(kind, NAMES[UNKNOWN])}."
	if asks:
		said += f" It shows a puzzle that asks: {asks}"
		if said[-1] not in ".!?":
			said += "."
	elif stage == BOX:
		said += " It shows its box and no puzzle."
	if status:
		said += f" The check itself says: {status}"
		if said[-1] not in ".!?":
			said += "."
	return said


def waysText(kind):
	"""The ways through a check that need no sight, the surest first, with NVDA's own keys. Only what the provider's
	own pages say (see the top of this file); where they say nothing, that is said."""
	if kind == RECAPTCHA:
		return (
			"Google describes a way that needs no sight. In browse mode, X moves to the check's box and Space checks it; "
			"NVDA is told its status, such as: You are verified. If a puzzle of pictures opens, B moves to the button Get "
			"an audio challenge: press it, press the button PLAY, type the numbers you hear into the edit field after "
			"it, and press Enter. In that field R plays the sound again, and the button Get a new challenge gives "
			"another. If NVDA does not let you type there, NVDA+Space turns focus mode on. The check expires after a "
			"time, so do it last on the page.")
	if kind == HCAPTCHA:
		return (
			"hCaptcha's own page names two ways that need no sight, and no audio challenge. First, its accessibility "
			"sign-up at hcaptcha.com/accessibility: you sign up with your email address and get a login link; opening "
			"it in this browser sets a cookie that lets you pass, or gives you a challenge in text, several times a "
			"day. The browser must allow cookies from other sites for hcaptcha.com. Second, where the site has turned "
			"it on, the check's menu has an Accessibility Challenge, which is text only.")
	if kind == TURNSTILE:
		return (
			"Cloudflare says there are no pictures or text to make out here, at most a box to select. In browse mode, X "
			"moves to the check box and Space checks it; then wait a few seconds. If the box does not take the "
			"keyboard, VisionClaw can press it for you. If the check runs out of time, Cloudflare says the page must "
			"be loaded again.")
	if kind == ARKOSE:
		return (
			"Arkose Labs' own accessibility page says nothing about how its puzzles are done without sight, so "
			"VisionClaw names no way of its own. In browse mode, B moves to the next button of the check; a button for "
			"another kind of challenge, if there is one, says so by its name.")
	if kind == SLIDER:
		return (
			"VisionClaw knows of no way through this kind of check that needs no sight, unless the check has a button "
			"of its own for one: in browse mode, B moves to the next button. VisionClaw can turn on pointer mode with "
			"the mouse pointer on the handle, so that you drag it with the arrow keys.")
	if kind == TEXT:
		return (
			"Look for the check's own audio version: in browse mode, B moves to the next button, and its name says "
			"so; E moves to the edit field to type into. Reading the letters from the picture is what this kind of "
			"check is built to stop, and VisionClaw's reading of them would most likely be wrong.")
	return (
		"In browse mode, X moves to the next check box and Space checks it; B moves to the next button, and a button "
		"for an audio or text version, if there is one, says so by its name.")


def reachText(boxes, buttons, limit=6):
	"""The check boxes and buttons of the check that NVDA can reach, by their names."""
	parts = []
	if boxes:
		parts.append("check box: " + "; ".join(name or "no name" for name in boxes[:2]))
	if buttons:
		named = [name for name in buttons if name][:limit]
		if named:
			parts.append("buttons: " + "; ".join(named))
	return ("NVDA can reach these in the check: " + ". ".join(parts) + ".") if parts else ""


def tellText(kind, stage=None, asks="", status="", boxes=(), buttons=(), wholeCheck=False):
	"""Everything the user is told about the check on the page, short enough to be said whole."""
	lead = "VisionClaw does not get through a check for you; here is what is there and what it can do. " if wholeCheck else ""
	parts = [lead + kindText(kind, stage, asks, status), waysText(kind), reachText(list(boxes), list(buttons)), OFFERS, NOTICE]
	text = " ".join(part for part in parts if part)
	if len(text) > RESULT_CHARS:
		# What NVDA can reach is found with B and X anyway; it goes first.
		parts[2] = ""
		text = " ".join(part for part in parts if part)
	if len(text) > RESULT_CHARS:
		parts[3] = "VisionClaw can press the box, describe the squares, click the squares you name, and press a button you name. You answer the check."
		text = " ".join(part for part in parts if part)
	return text


def squareText(said):
	"""One square's description, tidied to a few words."""
	text = " ".join(str(said or "").split()).strip(" .")
	if not text:
		return "no description"
	return text if len(text) <= SQUARE_CHARS else text[:SQUARE_CHARS].rsplit(" ", 1)[0] + " ..."


def puzzleText(asks, rows, columns, said, seer="model that sees", byContent=False, room=RESULT_CHARS):
	"""What a puzzle of pictures asks and what its squares show. said: [(the square's number, its description)].
	The descriptions are shortened alike until everything fits in what a tool may say."""
	count = rows * columns
	lead = NOT_CHOSEN + " " if byContent else ""
	if asks:
		head = lead + f"The check asks: {asks}" + ("" if asks[-1:] in ".!?" else ".")
	else:
		head = lead + "What the check asks could not be read as text."
	head += f" It has {count} squares, {rows} rows of {columns}, numbered from left to right and from the top down."
	tail = (
		f" These are the {seer}'s words for each square, and a model can be wrong. Say which squares to select by their "
		"numbers, and whether to press Verify afterwards. VisionClaw selects only the squares you name. " + SHORT_NOTICE)
	keep = SQUARE_CHARS
	while True:
		body = " ".join(
			f"Square {number}: {text if len(text) <= keep else text[:keep].rsplit(' ', 1)[0] + ' ...'}."
			for number, text in ((number, squareText(text)) for number, text in said))
		if len(head) + 1 + len(body) + len(tail) <= room or keep <= 20:
			break
		keep -= 8
	return f"{head} {body}{tail}"


def numbersText(found):
	"""Numbers said as a person says them: "1, 4 and 7"."""
	words = [str(number) for number in found]
	return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def selectQuestion(found, then=None):
	"""Asked before the squares the user named are clicked. Always asked."""
	what = "square" if len(found) == 1 else "squares"
	after = f", and then press its button {then.capitalize()}" if then else ""
	return (
		f"Click {what} {numbersText(found)} of the check with the mouse, as you said{after}? These checks are built to be "
		"hard for programs, so this may not get through.")


def boxQuestion(kind, name=""):
	"""Asked before the check's box is pressed. Always asked."""
	named = f", {name}," if name else ""
	return (
		f"Press the check box of {NAMES.get(kind, NAMES[UNKNOWN])}{named} for you? NVDA's own way is tried first, and "
		"the mouse on the box if that does nothing. These checks are built to be hard for programs, so this may not get through.")


def buttonQuestion(name):
	"""Asked before a button of the check is pressed. Always asked."""
	return f"Press the check's button {name} for you?"


def afterText(before, after, changed=None):
	"""What the check shows after a press, set beside what it showed before. before and after: {"kind", "stage",
	"asks", "status", "checked"} or None when no check is found any more. changed: whether the picture of the check
	changed, when that was compared. Never says that the check was passed: only the page can say that."""
	if after is None or after.get("kind") is None:
		return (
			"No check is found here any more, neither on the page as NVDA has it nor in the window's picture. Whether "
			"the site took it is for the page to say: read on from where you are.")
	if after.get("status") and after.get("status") != (before or {}).get("status"):
		said = f"The check itself now says: {after['status']}"
		return said if said[-1] in ".!?" else said + "."
	if after.get("checked") and not (before or {}).get("checked"):
		return "The check's box is now checked, as NVDA has it."
	if after.get("asks") and after.get("asks") != (before or {}).get("asks"):
		opened = (before or {}).get("stage") != PUZZLE
		return (
			("The check has opened a puzzle. It asks: " if opened else "The check now shows another puzzle. It asks: ") + after["asks"]
			+ ("" if after["asks"][-1:] in ".!?" else ".") + " Ask what the squares show, or use the check's own audio challenge.")
	if after.get("stage") == PUZZLE and (before or {}).get("stage") != PUZZLE:
		return "The check has opened a puzzle. Ask what it asks and what the squares show, or use the check's own audio challenge."
	if changed is True:
		return "The picture of the check changed. Ask what it shows now before you go on."
	if changed is False:
		return "The check looks the same as before: nothing VisionClaw can see changed."
	return STILL


def selectedText(found, taken, then=None, pressed=None, after=""):
	"""What was done with the squares the user named. taken: for each, whether its picture changed after the click
	(None when that could not be compared). pressed: whether the button was found and pressed."""
	what = "square" if len(found) == 1 else "squares"
	said = f"Clicked {what} {numbersText(found)}, as you said."
	same = [number for number, changed in zip(found, taken) if changed is False]
	if same:
		said += f" Nothing VisionClaw can see changed at {numbersText(same)}, so the click may not have been taken there."
	if then:
		said += (f" Pressed the button {then.capitalize()}." if pressed else f" The button {then.capitalize()} was not found, so it was not pressed.")
	return " ".join(part for part in (said, after, SHORT_NOTICE) if part)


def boxText(how, after):
	"""What was done with the check's box. how: "nvda", "mouse" (on the box as NVDA or the picture places it) or
	"beside" (no box was found in the picture, so the click went just before its words)."""
	said = {
		"nvda": "Pressed the check's box with NVDA's own action.",
		"mouse": "Pressed the check's box with a mouse click on it.",
		"beside": "No box was found in the picture next to the check's words, so VisionClaw clicked just before the words, where such a box usually is.",
	}[how]
	return " ".join(part for part in (said, after, SHORT_NOTICE) if part)


def buttonText(name, after):
	return " ".join(part for part in (f"Pressed the check's button {name}.", after, SHORT_NOTICE) if part)


def noButton(button, names):
	"""Said when the button the user named is not among the check's buttons."""
	have = "; ".join(name for name in names if name)
	return (
		f"Nothing was pressed: the check has no button for {button} that VisionClaw can find." +
		(f" NVDA can reach these buttons in it: {have}." if have else ""))


def holdText(where, gap="", seer="model that sees", steps=None):
	"""Said when pointer mode was turned on for a handle or a piece that must be dragged. where: how the place was
	found ("page": from the page as NVDA has it; "words": at the start of the line of the check's words in the
	picture; "middle": nothing was found, so the pointer is in the middle of the window). gap: the model's words
	for where the piece and the cut-out are. steps: (how many presses of Right Arrow cross the check, and of
	Shift+Right Arrow), when the check's width is known."""
	place = {
		"page": "with the mouse pointer on the handle, where NVDA has it",
		"words": "with the mouse pointer at the start of the line that holds the check's words, where such a check usually has its handle; this is a guess",
		"middle": "but VisionClaw could not find the handle, so the mouse pointer is in the middle of the window; move it onto the handle with the arrow keys",
	}[where]
	said = (
		f"Pointer mode is on, {place}. W says what is at the pointer. G holds the mouse button down; then Right Arrow "
		"drags to the right and Left Arrow back, with Shift in small steps; G again lets go, and letting go is your "
		"answer to the check. Escape turns pointer mode off.")
	if steps:
		said += f" The check is about {steps[0]} presses of Right Arrow wide, or {steps[1]} with Shift."
	if gap:
		said += f" The {seer} says of the picture, and a model can be wrong: {' '.join(gap.split())}"
		if said[-1] not in ".!?":
			said += "."
	return f"{said} You drag it; VisionClaw does not. {SHORT_NOTICE}"
