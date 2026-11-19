# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Checks that ask whether the visitor is a person, drawn by the test: a window with a puzzle of pictures inside a
frame that has a heading and buttons, a box with words next to it, a track with a handle; and the same checks as
a web page would give them to NVDA, as plain controls. None of this is a real check of any provider: the pictures
only have the parts that plain code looks for (a grid of tiles with plain gaps, a printed box, words), and the
controls only have the kinds, names and states that tests/test_humancheck.py needs. What is found here says
nothing about a real check on a real website.

Words are given as ocr.py gives them: lines of words, each {"x", "y", "width", "height", "text"} in picture pixels.
"""
import drawn

BLUE, PAPER = (66, 133, 244), (255, 255, 255)


def puzzle(rows=3, columns=3, side=96, gap=6, asks=("Select all squares with", "traffic lights", "Click verify once there are none left.")):
	"""A window of a browser with a puzzle of pictures in a frame: a blue heading that says what is asked, the tiles,
	and a row of buttons under them. Returns {"page": the drawn page, "frame": the frame's box, "tiles": the boxes of
	the tiles row by row, "verify": the box of the word VERIFY}."""
	page = drawn.Page(900, 700)
	page.text(40, 20, "Create your account")
	page.text(40, 50, "One more step before we can go on.")
	grid, boxes = drawn.tiles(rows, columns, side, gap)
	left, top = 240, 110
	head = 22 * len(asks) + 16
	width, height = grid.size
	frame = (left, top, left + width, top + head + height + 46)
	page.block((left, top, left + width - 1, top + head - 1), BLUE)
	for index, line in enumerate(asks):
		page.text(left + 12, top + 8 + 22 * index, line, fill=PAPER)
	page.image.paste(grid, (left, top + head))
	tiles = [(left + box[0], top + head + box[1], left + box[2], top + head + box[3]) for box in boxes]
	foot = top + head + height + 12
	page.block((left + width - 110, foot, left + width - 10, foot + 26), BLUE)
	verify = page.text(left + width - 92, foot + 5, "VERIFY", fill=PAPER)
	page.text(left + 12, foot + 5, "SKIP")
	return {"page": page, "frame": frame, "tiles": tiles, "verify": verify}


def markTile(page, tile):
	"""What a puzzle draws on a tile that was clicked: a mark in its corner, so that its picture changes."""
	page.draw.rectangle((tile[0] + 4, tile[1] + 4, tile[0] + 30, tile[1] + 30), fill=BLUE)


def boxCheck(words="Verify you are human", square=True):
	"""A window with a check that shows only its box and the words next to it. Returns {"page", "frame", "box": the
	printed box or None, "label": the box of the words}."""
	page = drawn.Page(900, 500)
	page.text(40, 20, "Checking that the connection is safe")
	frame = (300, 160, 600, 230)
	page.draw.rectangle(frame, outline=drawn.GREY, width=1)
	box = page.square(320, 185, side=20) if square else None
	label = page.text(352, 188, words)
	return {"page": page, "frame": frame, "box": box, "label": label}


def tickBox(page, box):
	page.draw.line((box[0] + 4, box[1] + 10, box[0] + 9, box[1] + 16), fill=(20, 140, 60), width=3)
	page.draw.line((box[0] + 9, box[1] + 16, box[0] + 17, box[1] + 4), fill=(20, 140, 60), width=3)


def slider():
	"""A window with a check whose handle must be dragged along a track. Returns {"page", "frame", "handle"}."""
	page = drawn.Page(900, 500)
	page.text(40, 20, "Sign in")
	frame = (280, 200, 620, 250)
	page.draw.rectangle(frame, outline=drawn.GREY, width=1)
	handle = page.block((284, 204, 326, 246), BLUE)
	page.text(380, 216, "Slide to verify")
	return {"page": page, "frame": frame, "handle": handle}


def plain():
	"""A window with no check in it."""
	page = drawn.Page(900, 500)
	page.text(40, 20, "Winter boots")
	page.text(40, 50, "Warm, lined, and made to last. Add to cart to order a pair.")
	return {"page": page, "frame": None}


class Node(dict):
	"""A control of a web page as VisionClaw's page reading gives it: a plain dict, kept apart by what it is."""
	__hash__ = object.__hash__

	def __eq__(self, other):
		return self is other


_keys = [0]


def node(role, name="", up=None, states=(), text="", hidden=False):
	_keys[0] += 1
	return Node(role=role, name=name, text=text, states=list(states), key=(1, _keys[0]), up=up, hidden=hidden)


def recaptchaPage(open_=False, asks=("Select all squares with", "traffic lights", "Click verify once there are none left.")):
	"""A web page with a check in a frame, as plain controls: the frame with its box and status; and, when its puzzle
	is open, a second frame with what is asked and its buttons. Returns (every control, the controls by name)."""
	root = node("DOCUMENT", "Create your account")
	heading = node("HEADING", "Create your account", root)
	name = node("EDITABLETEXT", "Email address", root)
	frame = node("INTERNALFRAME", "reCAPTCHA", root)
	box = node("CHECKBOX", "I'm not a robot", frame)
	status = node("STATICTEXT", "Recaptcha requires verification", frame)
	found = {"root": root, "frame": frame, "box": box, "status": status}
	nodes = [root, heading, name, frame, box, status]
	if open_:
		challenge = node("INTERNALFRAME", "recaptcha challenge expires in two minutes", root)
		nodes.append(challenge)
		for line in asks:
			nodes.append(node("STATICTEXT", line, challenge))
		for key, label in (("new", "Get a new challenge"), ("audio", "Get an audio challenge"), ("help", "Help"), ("verify", "Verify")):
			found[key] = node("BUTTON", label, challenge)
			nodes.append(found[key])
		found["challenge"] = challenge
	nodes.append(node("BUTTON", "Sign up", root))
	return nodes, found


def turnstilePage():
	"""A web page that shows nothing but a check, with its box in a frame."""
	root = node("DOCUMENT", "Just a moment")
	frame = node("INTERNALFRAME", "Widget containing a Cloudflare security challenge", root)
	box = node("CHECKBOX", "Verify you are human", frame)
	return [root, node("HEADING", "example.org", root), frame, box], {"root": root, "frame": frame, "box": box}


def storePage():
	"""A web page with no check on it."""
	root = node("DOCUMENT", "Winter boots")
	return [root, node("HEADING", "Winter boots", root), node("BUTTON", "Add to cart", root),
		node("CHECKBOX", "Gift wrap", root)], {"root": root}
