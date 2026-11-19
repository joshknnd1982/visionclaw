# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a picture on a web page or in a program's window: which one the user means, and what to ask
# about it. "Read the text in the latest image in this chat and explain the joke", "look at the screenshot my
# coworker just shared, what error code is highlighted", "look at the product photo, is this jacket navy blue or
# black", "look at the photos of the room, does the balcony face the sea". A screen reader says "graphic", or the
# name of a file; reading the whole window's text mixes the picture with everything around it.
# Plain code reads from the user's own words which picture is meant (the latest, the first, the product's, the
# photos of a gallery, the one with the focus, the largest), chooses it among the pictures the page or the
# program itself tells NVDA about, by their order and size, and leaves out what is too small to be meant: emoji,
# little faces next to names, icons. Only then is a model asked, about that picture alone, one small question at
# a time (claw/pictures.py). A question about a colour is answered with what was measured from the pixels first
# (claw/colours.py), because a small model is not sure of navy against black.
# How this differs from claw/pictures.py: pictures.py takes a question about a picture that is already chosen
# (the screen, the window, the focused control) and splits it into its parts, each with the rule of its kind.
# This file decides WHICH picture of a page or a chat is meant, and uses pictures.py for the parts of the
# question; it adds only what a picture someone sent needs on top: why it is meant to be funny, and a colour
# that is measured.
# No NVDA dependencies. Boxes are (left, top, right, bottom) in screen pixels.

import re

from . import colours, pictures
from .scrolling import pixels

LATEST, FIRST, PRODUCT, GALLERY, FOCUSED, LARGEST = "latest", "first", "product", "gallery", "focused", "largest"
# At most this many photos of a gallery are looked at for one request; each is a question to a model.
MAX_GALLERY = 4
# A picture that is meant is at least this big on a plain screen at 100 percent, and at least this share of the
# window's shorter side. Emoji and the little faces next to names are smaller.
MIN_SIDE, MIN_SHARE = 72, 0.09
_IMAGE = (
	r"(?:images?|pictures?|photos?|photographs?|pics?|memes?|screen ?shots?|graphics?|comics?|comic strips?|gifs?|stickers?|"
	r"drawings?|cartoons?|thumbnails?|snaps?|selfies?|attachments?)")
_IMAGE_RE = re.compile(rf"\b{_IMAGE}\b", re.IGNORECASE)
_PLURAL = re.compile(r"\b(images|pictures|photos|photographs|pics|memes|screenshots|screen shots|thumbnails|comics)\b", re.IGNORECASE)
_LATEST = re.compile(
	r"\b(latest|last|newest|most recent|recent|just (?:now )?(?:shared|sent|posted|received|got|came in|arrived|dropped)|"
	r"(?:shared|sent|posted) just now|bottom)\b", re.IGNORECASE)
_FIRST = re.compile(r"\b(first|top|earliest|oldest)\b", re.IGNORECASE)
_PRODUCT = re.compile(
	r"\b(product|item|listing|main|hero|cover|profile)\b(?:'s)?\s+" + _IMAGE + r"\b|\b" + _IMAGE + r" of (?:the|this) (?:product|item|listing)\b",
	re.IGNORECASE)
_GALLERY = re.compile(
	r"\b(gallery|galleries|carousel|slideshow|slide show|album)\b|\b(all|each|every|these|those|the room|room|the hotel|hotel) "
	r"(?:of the |the )?" + _IMAGE + r"\b", re.IGNORECASE)
_FOCUSED = re.compile(
	r"\b(?:this|focused|current|selected|highlighted)\s+" + _IMAGE + r"\b|\b" + _IMAGE + r" (?:i am|i'm|that i'm|that i am) on\b"
	r"|\b" + _IMAGE + r" (?:under|at|with) (?:the |my )?(?:focus|cursor)\b", re.IGNORECASE)
_CHAT = re.compile(
	r"\b(chat|chats|conversation|thread|channel|message|messages|whatsapp|telegram|signal|discord|slack|teams|messenger|"
	r"imessage|dm|dms|group|coworker|co-worker|colleague|friend|shared|sent|posted)\b", re.IGNORECASE)
# A part of a question that only says which picture to look at, and asks nothing about it.
_POINTS = re.compile(
	r"^\s*(?:please\s+)?(?:look at|have a look at|take a look at|check out|check|see|view|open|find|go to|examine|inspect)\s+"
	r"(?:the|this|that|my|a|an|each|every|all)\b[^?]*$", re.IGNORECASE)
_ASKS_MORE = re.compile(
	r"\b(what|which|who|where|why|how|is|are|does|do|did|can|could|read|describe|tell|explain|count|list|say)\b", re.IGNORECASE)
JOKE = "joke"
_JOKE = re.compile(r"\b(jokes?|funny|humou?r|punch ?line|memes?|comic|comics|cartoons?|gag|pun)\b", re.IGNORECASE)
# What a model is told for a question that asks why a picture is meant to be funny. No example: a small model
# copies an example as if it were the answer.
JOKE_RULE = (
	"First say what the picture shows and what any text in it says. Then say in one or two plain sentences why "
	"people find it funny: what is unexpected, or which two things are set against each other. If you do not "
	"understand the joke, say so.")


def about(part):
	"""Whether a request's words name a picture at all."""
	return bool(_IMAGE_RE.search(part or "") or _GALLERY.search(part or ""))


def wish(part):
	"""Which picture the user's words mean, or None when they name no picture: {"which": LATEST, FIRST, PRODUCT,
	GALLERY, FOCUSED or LARGEST; "many": whether several pictures are meant; "chat": whether the words speak of a
	chat or of something sent}."""
	text = " ".join(str(part or "").split())
	if not about(text):
		return None
	chat = bool(_CHAT.search(text))
	loose = False
	if _GALLERY.search(text):
		which = GALLERY
	elif _PRODUCT.search(text):
		which = PRODUCT
	elif _LATEST.search(text):
		which = LATEST
	elif _FOCUSED.search(text):
		which = FOCUSED
	elif _FIRST.search(text):
		which = FIRST
	elif _PLURAL.search(text) and not chat:
		# "Pictures" alone: several are meant, but the words pick none of them (see meant).
		which, loose = GALLERY, True
	else:
		# In a chat the picture that is meant is the newest one; anywhere else, the one that fills most of the window.
		which = LATEST if chat else LARGEST
	return {"which": which, "many": which == GALLERY, "chat": chat, "loose": loose}


# Words for a picture that is always one thing inside a page or a chat, never the whole screen.
_ONE_PICTURE = re.compile(
	r"\b(memes?|screen ?shots?|comics?|comic strips?|cartoons?|stickers?|gifs?|attachments?|thumbnails?|selfies?)\b", re.IGNORECASE)
# Words that say something else is to be done with a picture than looking at it: that is another job.
_NOT_LOOKING = re.compile(
	r"\b(open|delete|remove|move|copy|rename|save|download|upload|send|attach|print|share|forward|post|folders?|files?|"
	r"take a|take an|make a|create|draw|generate|wallpaper|background|click|press|select|choose|search|look for|google|"
	r"show me|get me|find (?:me )?(?:some |a |an |more )?" + _IMAGE + r"|how many (?:[\w-]+ )?" + _IMAGE + r")\b", re.IGNORECASE)


# A request about VisionClaw's models, or about describing pictures in general, is about no picture in front.
_ABOUT_MODELS = re.compile(
	r"\b(models?|qwen|quants?|q4_k_m|q6_k|llms?|vision model|coder model|visionclaw|settings?|add-?ons?|skills?)\b", re.IGNORECASE)


def meant(part):
	"""The wish (see wish), where the words pick one picture among those of a page, a window or a chat and ask to
	look at it; None for anything else. "Describe this picture" and "what is on my screen" are not that: they look
	at what has the focus or at the whole window, as before. Neither is "open my newest photo", which is about a
	file."""
	wished = wish(part)
	if wished is None or _NOT_LOOKING.search(part or "") or _ABOUT_MODELS.search(part or ""):
		return None
	if _ONE_PICTURE.search(part or "") or wished["chat"]:
		return wished
	# The plural alone picks no picture: "which model is best for describing pictures" is about models.
	if wished["which"] in (LATEST, FIRST, PRODUCT, GALLERY) and not wished["loose"]:
		return wished
	return None


def asks(part):
	"""The separate questions a request asks about a picture: [(kind, the user's words)], with the kind's rule
	found by rule(). A part that only says which picture to look at asks nothing and is left out; when nothing is
	asked at all, the picture is described."""
	found = pictures.pieces(part)
	kept = [(kind, text) for kind, text in found if not (_POINTS.match(text) and len(found) > 1)]
	if not kept:
		kept = found
	result = []
	for kind, text in kept:
		# Reading the text and explaining the joke are two questions, also where the words join them with "and".
		split = re.split(r",?\s+and\s+(?=(?:then\s+)?(?:explain|tell me why|say why)\b)", text, maxsplit=1, flags=re.IGNORECASE)
		for piece in split:
			piece = piece.strip(" ,.;")
			if not piece:
				continue
			if _JOKE.search(piece) and re.search(r"\b(explain|why|what'?s funny|what is funny|get it|joke)\b", piece, re.IGNORECASE):
				result.append((JOKE, piece))
			elif colours.wanted(piece) and pictures.kindOf(piece) in (pictures.DESCRIBE, pictures.FIND):
				result.append((pictures.COLOUR, piece))
			else:
				result.append((pictures.kindOf(piece), piece))
	if len(result) == 1 and _POINTS.match(result[0][1]) and not _ASKS_MORE.search(result[0][1]):
		return [(pictures.DESCRIBE, "What does this picture show?")]
	return result[:pictures.MAX_PIECES]


def rule(kind):
	"""The one rule a model is given for a question of a kind."""
	return JOKE_RULE if kind == JOKE else pictures.rule(kind)


def bigEnough(box, window, scale=1.0):
	"""Whether a picture is big enough to be one a person means, and no emoji, little face or icon."""
	left, top, right, bottom = box
	side = min(right - left, bottom - top)
	if side < pixels(MIN_SIDE, scale):
		return False
	if window is None:
		return True
	return side >= MIN_SHARE * min(window[2] - window[0], window[3] - window[1])


def visible(box, window):
	"""How much of a picture is inside the window, from 0.0 to 1.0."""
	left, top, right, bottom = box
	area = max(1, (right - left) * (bottom - top))
	if window is None:
		return 1.0
	width = min(right, window[2]) - max(left, window[0])
	height = min(bottom, window[3]) - max(top, window[1])
	return max(0, width) * max(0, height) / area


def _area(picture):
	left, top, right, bottom = picture["box"]
	return (right - left) * (bottom - top)


def choose(wished, found, window=None, scale=1.0):
	"""The pictures that are meant, among those that were found: found is a list of {"box", "name", "order", and
	"focused": whether the focus or NVDA's reading position is on it}, in the order of the page or window. Returns
	(the chosen pictures, how many more pictures of a gallery were left out)."""
	usable = [picture for picture in found if picture.get("box") and bigEnough(picture["box"], window, scale)]
	if not usable:
		return [], 0
	usable.sort(key=lambda picture: picture.get("order", 0))
	which = wished["which"]
	if which == FOCUSED:
		focused = [picture for picture in usable if picture.get("focused")]
		if focused:
			return focused[:1], 0
		which = LARGEST
	if which == LATEST:
		return usable[-1:], 0
	if which == FIRST:
		return usable[:1], 0
	largest = max(usable, key=_area)
	if which == GALLERY:
		# The photos of a gallery are of one size, or nearly; a logo beside them is not one of them.
		alike = [picture for picture in usable if _area(picture) >= 0.3 * _area(largest)]
		return alike[:MAX_GALLERY], max(0, len(alike) - MAX_GALLERY)
	# The product's own photo, or simply the picture: the largest one.
	return [largest], 0


def calls(picture):
	"""What the page or the program itself calls a picture, when that says something: not a file's name alone."""
	name = " ".join(str(picture.get("name") or "").split())
	if len(name) < 3 or re.fullmatch(r"[\w.-]+\.(?:png|jpe?g|gif|webp|bmp|svg)", name, re.IGNORECASE):
		return ""
	if name.lower() in ("image", "graphic", "photo", "picture", "img", "thumbnail"):
		return ""
	return name


def lead(wished, picture, number=None, total=None, where="page"):
	"""How an answer about a picture begins: which picture was looked at, and what the page calls it."""
	which = wished["which"]
	place = "on this page" if where == "page" else "in this window"
	if number is not None and total and total > 1:
		said = f"Picture {number} of {total} {place}"
	elif which == LATEST:
		said = f"The last picture {place}" if where != "picture" else "The picture found in the lower part of this window"
	elif which == FIRST:
		said = f"The first picture {place}"
	elif which == FOCUSED and picture.get("focused"):
		said = "The picture that has the focus"
	else:
		said = f"The largest picture {place}" if where != "picture" else "The picture found in this window"
	named = calls(picture)
	return said + (f", which the {'page' if where == 'page' else 'program'} calls \"{named}\"" if named else "")


def measured(image, asked):
	"""What plain code measured of a picture's colours, for a question that names colours: a sentence, or "".
	asked: the colours the user's words name (colours.wanted)."""
	ground, shares = colours.subject(image)
	if not shares:
		return ""
	said = "Measured from the picture's pixels: " + (f"leaving out the {ground} background, " if ground else "") + colours.said(shares) + "."
	fits = []
	for colour in asked or ():
		share = sum(part for name, part in shares if name == colour)
		# The same colour darker or lighter: "blue" was asked for and dark blue was measured.
		near = sum(part for name, part in shares if name != colour and colours.family(name) == colours.family(colour))
		if share >= 0.15:
			fits.append(f"{colour} is there")
		elif near >= 0.15:
			fits.append(f"{colour} as such is not, but a darker or lighter {colours.family(colour)} is")
		else:
			fits.append(f"{colour} is hardly there")
	if fits:
		said += " Of the colours you named: " + "; ".join(fits) + "."
	return said + " The light in a photo can make a colour look darker or lighter than the thing is."


NOT_FOUND = (
	"No picture large enough to be meant was found: neither among the pictures the page or the program tells NVDA "
	"about, nor in the picture of the window. If it is further up or down, scroll to it and ask again; or ask what "
	"is on the screen, and the whole window is looked at.")
NO_WISH = "The request names no picture. Say which picture is meant, such as: the latest picture in this chat."


def leftOut(count):
	return f" {count} more {'picture was' if count == 1 else 'pictures were'} not looked at: ask again for the next ones after moving on in the gallery." if count else ""
