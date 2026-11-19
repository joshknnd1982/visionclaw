# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a web page in words, for someone who hears it or reads it in braille, and what is stopping a
# form. Two things, both plain code over the controls NVDA keeps of a page (claw/fixmatch.py's plain nodes):
#   1. Exploring a page: its landmarks in order, where the main part begins, how many headings, links, buttons,
#      fields, tables and lists it has, the links of its navigation, its form fields, and which of NVDA's own
#      keys move best on this page. Only keys for what the page really has are named.
#   2. Form trouble: the fields the page marks as not valid, the fields that must be filled in and are empty,
#      and the error messages the page shows, each put with the field it stands next to.
# Nothing is guessed and no model is asked: what is said is what the page itself tells NVDA. The keys were read
# from the user guide of NVDA 2026.3.1 on 2026-11-18 (Browse Mode, Single Letter Navigation, The Elements
# List, table navigation); NVDA's names for landmarks from its aria module, its names for states from
# controlTypes.State, and its kinds of control from controlTypes.Role. When they are brought up to date, read
# them again; do not write them from memory. No NVDA dependencies.

import re

from . import fixmatch

plainText, labelOf = fixmatch.plainText, fixmatch.labelOf

# How NVDA says each landmark.
LANDMARKS = {
	"banner": "banner", "complementary": "complementary", "contentinfo": "content info", "main": "main",
	"navigation": "navigation", "search": "search", "form": "form", "region": "region"}
# The kinds of control a form is filled in with, and what each is called in a list.
FIELDS = {
	"EDITABLETEXT": "edit field", "PASSWORDEDIT": "password field", "COMBOBOX": "combo box", "CHECKBOX": "checkbox",
	"RADIOBUTTON": "radio button", "SWITCH": "switch", "SPINBUTTON": "spin button", "SLIDER": "slider",
	"DATEEDITOR": "date field"}
TYPED = ("EDITABLETEXT", "PASSWORDEDIT", "SPINBUTTON", "DATEEDITOR")
CHECKED = ("CHECKBOX", "SWITCH")
BUTTONS = ("BUTTON", "TOGGLEBUTTON", "MENUBUTTON", "SPLITBUTTON", "DROPDOWNBUTTON")
SHOWN_LANDMARKS, SHOWN_TROUBLE = 8, 8
LABEL_CHARS, SAID_CHARS = 60, 160
# A tool's answer is cut at tools.RESULT_CHARS. What is said here is shortened by plain code until it fits, the
# lists first, so that the keys at the end are never the part that is lost.
FITS = 1400
# How many headings, links of the navigation and form fields are named, from the fullest to the shortest.
_SHORTER = ((6, 8, 8), (4, 6, 5), (3, 4, 3), (2, 3, 0), (1, 0, 0), (0, 0, 0))
# A message this near after a field, or this near before one, in characters of the page, belongs to the field.
AFTER_FIELD, BEFORE_FIELD = 200, 80
# Parts of a class name, as the page's own code writes it, that say something is wrong.
_WRONG = frozenset(("error", "errors", "invalid", "danger"))
# What a combo box shows while nothing is chosen.
_NOT_CHOSEN = ("select", "choose", "please", "pick")
# Words in a line read from a picture that may say why a form was not taken.
_ERROR_WORDS = (
	"error", "required", "invalid", "not valid", "incorrect", "must be", "must contain", "must match", "please enter",
	"please fill", "please select", "please choose", "missing", "too short", "too long", "do not match", "does not match",
	"cannot be empty", "can't be empty", "is not a valid", "try again", "failed")


def many(count, one, more=None):
	return f"{count} {one if count == 1 else (more or one + 's')}"


def _listed(words):
	"""Words as they are said in a row: a, b and c."""
	words = [word for word in words if word]
	if len(words) < 2:
		return "".join(words)
	return ", ".join(words[:-1]) + " and " + words[-1]


def _states(node):
	return node.get("states") or ()


def shown(node):
	"""Whether a control is there for the user: not hidden by the page."""
	return not node.get("hidden") and "INVISIBLE" not in _states(node)


def _label(node, chars=LABEL_CHARS):
	text = " ".join(str(labelOf(node) or "").split())
	return text if len(text) <= chars else text[:chars].rsplit(" ", 1)[0] + " ..."


def headingLevel(node):
	"""The level of a heading, 0 where NVDA does not say it, or None for what is no heading."""
	role = str(node.get("role") or "")
	if not role.startswith("HEADING"):
		return None
	digits = role[7:] or str(node.get("level") or "")
	return int(digits) if digits.isdigit() else 0


def _inside(node, outer):
	up = node.get("up")
	while up is not None:
		if up is outer:
			return True
		up = up.get("up")
	return False


def _landmarkOf(node):
	"""The landmark a control is in, the nearest one, or None."""
	up = node.get("up")
	while up is not None:
		if up.get("landmark") in LANDMARKS:
			return up
		up = up.get("up")
	return None


def isField(node):
	"""Whether a control is one a form is filled in with, and can be filled in now."""
	role = node.get("role")
	if role not in FIELDS or not shown(node) or "UNAVAILABLE" in _states(node):
		return False
	return not (role in TYPED and "READONLY" in _states(node))


def fieldText(node):
	"""A field as it is said in a list: its label, its kind, and that it must be filled in."""
	label = _label(node) if node.get("name") else ""
	kind = FIELDS.get(node.get("role"), "field")
	text = f"{label}, {kind}" if label else f"{kind} without a label"
	return text + (", required" if "REQUIRED" in _states(node) else "")


# --- Exploring a page ---

class View:
	"""What a page has, as plain lists of its controls in reading order."""

	def __init__(self, nodes):
		seen = [node for node in nodes if shown(node)]
		self.landmarks = [
			node for node in seen
			if node.get("landmark") in LANDMARKS and (node.get("landmark") != "region" or node.get("name"))]
		self.headings = [(headingLevel(node), node) for node in seen if headingLevel(node) is not None and _label(node)]
		self.links = [node for node in seen if node.get("role") == "LINK" and _label(node)]
		self.buttons = [node for node in seen if node.get("role") in BUTTONS]
		self.fields = [node for node in seen if isField(node)]
		self.tables = [node for node in seen if node.get("role") == "TABLE"]
		self.lists = [node for node in seen if node.get("role") == "LIST"]
		self.graphics = [node for node in seen if node.get("role") == "GRAPHIC"]
		self.main = next((node for node in self.landmarks if node.get("landmark") == "main"), None)

	def levels(self):
		"""How many headings each level has, as {level: count}."""
		counts = {}
		for level, _node in self.headings:
			counts[level] = counts.get(level, 0) + 1
		return counts

	def firstAt(self, level):
		return next((node for found, node in self.headings if found == level), None)


def landmarkText(node, links=0):
	"""A landmark as NVDA says it, with its name and how many links it has."""
	text = LANDMARKS[node["landmark"]]
	if node.get("name"):
		text += f", {_label(node, 40)}"
	if links:
		text += f", with {many(links, 'link')}"
	return text


def _counts(view):
	parts = [
		(len(view.headings), "heading", None), (len(view.landmarks), "landmark", None), (len(view.links), "link", None),
		(len(view.buttons), "button", None), (len(view.fields), "form field", None), (len(view.tables), "table", None),
		(len(view.lists), "list", None), (len(view.graphics), "picture", None)]
	return _listed([many(count, one, more) for count, one, more in parts if count])


def _mainText(view):
	"""Where the main part of the page begins, in one sentence."""
	top = view.firstAt(1)
	if view.main is not None:
		first = next(((level, node) for level, node in view.headings if _inside(node, view.main)), None)
		if first is not None:
			level, node = first
			at = f"at level {level}" if level else "without a level"
			return f"The main landmark begins with the heading {at}, {_label(node)}."
		return "The page has a main landmark, which has no heading."
	if top is not None:
		return f"The page marks no main landmark. Its heading at level 1 is {_label(top)}."
	if view.headings:
		level, node = view.headings[0]
		at = f", at level {level}" if level else ""
		return f"The page marks no main landmark and has no heading at level 1. Its first heading is {_label(node)}{at}."
	return "The page marks no main landmark and has no headings."


def tips(view):
	"""Which of NVDA's keys move best on this page, the best first. Only keys for what the page has."""
	lines, levels = [], view.levels()
	top = view.firstAt(1)
	if top is not None and (view.main is None or _inside(top, view.main)):
		lines.append("The quickest way to the main part: press 1, which moves to the heading at level 1.")
	elif view.main is not None:
		lines.append("The quickest way to the main part: press D until NVDA says main landmark.")
	elif not view.headings and len(view.fields) >= 3:
		lines.append("This page is mostly a form: press F to move to its first field.")
	if view.headings:
		lines.append("H moves to the next heading, Shift+H to the one before.")
		level, count = max(levels.items(), key=lambda item: (item[1], -item[0]))
		if level > 1 and count >= 3 and count < len(view.headings):
			lines.append(f"Most headings, {count} of them, are at level {level}: {level} moves between just these.")
	if len(view.landmarks) >= 2 or (view.landmarks and view.main is None):
		lines.append("D moves to the next landmark, Shift+D to the one before.")
	if view.fields:
		lines.append(
			"F moves to the next form field. Press Enter on a field to type in it, and Escape to go back to reading.")
	if view.tables:
		lines.append("T moves to the next table. Inside a table, Control+Alt+Arrow keys move by row and column.")
	if view.lists:
		lines.append("L moves to the next list, I to the next list item.")
	if not view.headings and not view.landmarks:
		lines.append("P moves to the next paragraph of text, which helps to find where the reading starts.")
	lines.append(
		"NVDA+F7 lists the links, headings, form fields, buttons and landmarks of the page; type there to filter the list.")
	return lines


def explore(nodes, title="", site=""):
	"""A page in words: what it has, how it is laid out, and how to move on it with NVDA's own keys."""
	view = View(nodes)
	text = ""
	for shownHeadings, shownLinks, shownFields in _SHORTER:
		text = _explore(view, title, site, shownHeadings, shownLinks, shownFields)
		if len(text) <= FITS:
			break
	return text


def _explore(view, title, site, shownHeadings, shownLinks, shownFields):
	name = f"The web page {title}" if title else "This web page"
	if site:
		name += f" on {site}"
	counts = _counts(view)
	if not counts:
		return (
			f"{name} has no headings, landmarks, links, buttons or form fields that NVDA can move by. "
			"Read it with the arrow keys, or press P to move from paragraph to paragraph. If it sounds empty, "
			"NVDA+F5 reads the page in again; if it stays empty, ask VisionClaw to describe the window.")
	lines = [f"{name} has {counts}."]
	if view.landmarks:
		said = []
		for node in view.landmarks[:SHOWN_LANDMARKS]:
			said.append(landmarkText(node, sum(1 for link in view.links if _landmarkOf(link) is node)))
		more = len(view.landmarks) - len(said)
		lines.append("Landmarks in order: " + "; ".join(said) + (f"; and {more} more." if more > 0 else "."))
	lines.append(_mainText(view))
	levels = view.levels()
	if len(view.headings) > 1:
		byLevel = _listed([f"{count} at level {level}" if level else f"{count} without a level" for level, count in sorted(levels.items())])
		lines.append(f"Headings: {byLevel}.")
	if view.headings and shownHeadings:
		inMain = [node for _level, node in view.headings if view.main is None or _inside(node, view.main)]
		first = [_label(node) for node in (inMain or [node for _level, node in view.headings])[:shownHeadings]]
		lines.append(("The first headings: " if len(first) > 1 else "The heading: ") + "; ".join(first) + ".")
	for node in view.landmarks:
		if node.get("landmark") != "navigation" or not shownLinks:
			continue
		links = [_label(link, 30) for link in view.links if _landmarkOf(link) is node]
		if links:
			more = len(links) - shownLinks
			called = f" {_label(node, 40)}" if node.get("name") else ""
			lines.append(
				f"The navigation landmark{called} has these links: " + ", ".join(links[:shownLinks])
				+ (f", and {more} more." if more > 0 else "."))
			break  # the first navigation is the site's own; the others are named among the landmarks
	if view.fields and shownFields:
		more = len(view.fields) - shownFields
		lines.append(
			"Form fields: " + "; ".join(fieldText(node) for node in view.fields[:shownFields])
			+ (f"; and {more} more." if more > 0 else "."))
	lines.append("How to move on this page:")
	lines += tips(view)
	return "\n".join(lines)


# --- What is stopping a form ---

def _saysWrong(node):
	"""Whether the page's own code marks this as something that went wrong."""
	if node.get("role") == "ALERT" or "alert" in str(node.get("xml") or "").split():
		return True
	if str(node.get("live") or "") == "assertive":
		return True
	for name in node.get("cls") or ():
		for part in plainText(name).split():
			if part in _WRONG:
				return True
	return False


def _classWrong(node):
	return _saysWrong({"cls": node.get("cls")})


def _markedWrong(field, holds):
	"""Whether the page's code marks a field as wrong: by the field's own class, or by the class of a box close
	around it that holds no other field."""
	if _classWrong(field):
		return True
	up, steps = field.get("up"), 0
	while up is not None and steps < 3:
		if holds.get(id(up)) == 1 and _classWrong(up):
			return True
		up, steps = up.get("up"), steps + 1
	return False


def _empty(node):
	"""Whether a field that must be filled in has nothing in it. None where that cannot be told."""
	role, states = node.get("role"), _states(node)
	if role in TYPED:
		return not plainText(node.get("text"))
	if role in CHECKED:
		return "CHECKED" not in states
	if role == "COMBOBOX":
		chosen = plainText(node.get("text"))
		return not chosen or chosen.startswith(_NOT_CHOSEN)
	return None


def _group(node):
	"""What holds the radio buttons a radio button belongs with."""
	up = node.get("up")
	while up is not None:
		if up.get("role") == "GROUPING" or "radiogroup" in str(up.get("xml") or "").split():
			return up
		up = up.get("up")
	return node.get("up")


def messages(nodes, fields):
	"""The error messages a page shows: what its code marks as an alert or as wrong, has text, and is no field
	and no box around a field. Of a message inside a message, the inner one."""
	holding = set()
	for field in fields:
		up = field
		while up is not None:
			holding.add(id(up))
			up = up.get("up")
	found = [node for node in nodes if shown(node) and id(node) not in holding and _saysWrong(node) and plainText(node.get("text") or node.get("name"))]
	outer = set()
	for node in found:
		up = node.get("up")
		while up is not None:
			outer.add(id(up))
			up = up.get("up")
	kept, said = [], set()
	for node in found:
		text = plainText(node.get("text") or node.get("name"))
		if id(node) in outer or text in said:
			continue
		said.add(text)
		kept.append(node)
	return kept


def _nearest(message, fields):
	"""The field a message stands next to: the one just before it, else the one just after it, else None."""
	at, end = message.get("start"), message.get("end")
	if at is None or end is None:
		return None
	before = [field for field in fields if field.get("end") is not None and field["end"] <= at]
	if before:
		field = max(before, key=lambda field: field["end"])
		if at - field["end"] <= AFTER_FIELD:
			return field
		return None  # a message far below the last field is about the whole form
	after = [field for field in fields if field.get("start") is not None and field["start"] >= end]
	if after and message.get("role") != "ALERT" and "alert" not in str(message.get("xml") or "").split():
		field = min(after, key=lambda field: field["start"])
		if field["start"] - end <= BEFORE_FIELD:
			return field
	return None


class Trouble:
	"""What may be stopping a form. items: one for each field, in page order, as {"node", "text", "why": [...],
	"says": [...]}. notes: messages of the page that belong to no field. fields: how many fields were looked at."""

	def __init__(self, items, notes, fields):
		self.items, self.notes, self.fields = items, notes, fields

	@property
	def first(self):
		return self.items[0]["node"] if self.items else None


def trouble(nodes):
	"""Find what may be stopping the form of a page, from what the page itself tells NVDA."""
	fields = [node for node in nodes if isField(node)]
	why, order = {}, {}

	def note(node, reason):
		order.setdefault(id(node), node)
		reasons = why.setdefault(id(node), [])
		if reason not in reasons:
			reasons.append(reason)

	# How many fields each box of the page holds: a box marked as wrong that holds one field is about that field.
	holds = {}
	for field in fields:
		up = field.get("up")
		while up is not None:
			holds[id(up)] = holds.get(id(up), 0) + 1
			up = up.get("up")
	groups = {}
	for field in fields:
		states, role = _states(field), field.get("role")
		if "INVALID_ENTRY" in states:
			note(field, "is marked as not valid")
		elif _markedWrong(field, holds):
			note(field, "is marked by the page as wrong")
		if role == "RADIOBUTTON":
			group = groups.setdefault(id(_group(field)), {"first": field, "required": False, "checked": False})
			group["required"] = group["required"] or "REQUIRED" in states
			group["checked"] = group["checked"] or "CHECKED" in states
			continue
		if "REQUIRED" in states:
			empty = _empty(field)
			if empty and role in TYPED:
				note(field, "must be filled in and is empty")
			elif empty and role in CHECKED:
				note(field, "must be checked and is not")
			elif empty:
				note(field, "must have a choice and none seems to be made")
	for group in groups.values():
		if group["required"] and not group["checked"]:
			note(group["first"], "one of these radio buttons must be chosen and none is")
	says, notes = {}, []
	for message in messages(nodes, fields):
		text = " ".join(str(message.get("text") or message.get("name") or "").split())[:SAID_CHARS]
		field = _nearest(message, fields)
		if field is None:
			notes.append(text)
			continue
		order.setdefault(id(field), field)
		says.setdefault(id(field), []).append(text)
	items = []
	for key, node in sorted(order.items(), key=lambda item: (item[1].get("start") is None, item[1].get("start") or 0)):
		items.append({"node": node, "text": fieldText(node), "why": why.get(key, []), "says": says.get(key, [])})
	return Trouble(items, notes, len(fields))


def errorLines(lines, limit=4):
	"""Of the lines of text read from a picture of the page, those that may say why a form was not taken."""
	found = []
	for line in lines or ():
		text = " ".join(str(line).split())
		low = f" {plainText(text)} "
		if 3 < len(text) <= SAID_CHARS and any(f" {plainText(word)} " in low for word in _ERROR_WORDS) and text not in found:
			found.append(text)
	return found[:limit]


def _howToFix(node):
	role = node.get("role")
	if role in TYPED or role == "COMBOBOX":
		return "Press Enter to go into it, and Escape to come back to reading."
	if role in CHECKED:
		return "Press Space to check it."
	return ""


def redText(red, written, looked, moved=False):
	"""What the picture of the page shows where the page itself tells NVDA nothing: the fields that are outlined in
	red, and the lines written in red. red: the fields, as the page's controls, in page order. written: the lines
	of red text. looked: how many fields were on the screen to be looked at. Measured from the pixels by plain
	code (claw/colours.py); no model looked."""
	lines = []
	if red:
		count = len(red)
		lines.append(
			f"In the picture of the page, {many(count, 'field is', 'fields are')} outlined in red, which is how a page "
			f"usually marks what is wrong: {_listed([fieldText(node) for node in red[:SHOWN_TROUBLE]])}"
			+ (f", and {count - SHOWN_TROUBLE} more" if count > SHOWN_TROUBLE else "") + ".")
	if written:
		lines.append("Written in red in the picture: " + " ".join(line if line[-1:] in ".!?" else line + "." for line in written[:4]))
	if red and moved:
		name = _label(red[0]) or FIELDS.get(red[0].get("role"), "field")
		lines.append(f"NVDA's reading position is now on the first of them, {name}. {_howToFix(red[0])}".strip())
	if lines:
		lines.append(
			f"This was measured from the colours of the {many(looked, 'field')} that are on the screen now; fields further "
			"up or down were not looked at. Scroll and ask again to check those.")
	return lines


def troubleText(found, moved=False, drawn=(), red=(), written=(), looked=0):
	"""What may be stopping the form, said one field to a line, the first field first.
	moved: NVDA's reading position was put on the first of them. drawn: lines read from the page's picture.
	red, written, looked: what the picture of the page shows in red, where the page itself says nothing (redText)."""
	if not found.items and not found.notes:
		if not found.fields:
			lines = ["This page has no form fields that NVDA can read, so nothing can be said about a form here."]
		else:
			lines = [
				f"Looked at the {many(found.fields, 'form field')} of this page. None is marked as not valid or as "
				"required and empty, and the page shows no error message that NVDA can read."]
		marks = redText(red, written, looked, moved)
		if marks:
			lines.extend(marks)
			if drawn:
				lines.append("These lines of the picture may say why: " + " ".join(f"{line}." if line[-1:] not in ".!?" else line for line in drawn))
			return "\n".join(lines)
		if drawn:
			lines.append("In the picture of the page, these lines may say why: " + " ".join(f"{line}." if line[-1:] not in ".!?" else line for line in drawn))
		else:
			lines.append(
				"No field on the screen is outlined in red and nothing is written in red there. The page may check only "
				"when its button is pressed, or the fields in trouble are further up or down: scroll and ask again. Or ask "
				"VisionClaw to describe the window, and the model that sees pictures looks at it."
				if looked else
				"The reason may be shown only as a picture or by a colour, or the page may check only when its button "
				"is pressed. Ask VisionClaw to describe the window, and the model that sees pictures looks at it.")
		return "\n".join(lines)
	text = ""
	for most in range(SHOWN_TROUBLE, 0, -1):
		text = _troubleText(found, moved, most)
		if len(text) <= FITS:
			break
	return text


def _troubleText(found, moved, most):
	lines = []
	if found.items:
		count = len(found.items)
		lines.append(f"{many(count, 'field')} may be stopping this form." if count > 1 else "1 field may be stopping this form.")
		for number, item in enumerate(found.items[:most], 1):
			line = f"{number}. {item['text']}"
			if item["why"]:
				line += ": " + _listed(item["why"]) + "."
			else:
				line += "."
			if item["says"]:
				line += " The page says: " + " ".join(item["says"])
				line += "" if line[-1:] in ".!?" else "."
			lines.append(line)
		if count > most:
			lines.append(f"And {count - most} more; press F to move from field to field.")
	if found.notes:
		lead = "The page also says: " if found.items else "The page says: "
		said = " ".join(note if note[-1:] in ".!?" else note + "." for note in found.notes[:3])
		lines.append(lead + said)
	if moved and found.first is not None:
		name = _label(found.first) or FIELDS.get(found.first.get("role"), "field")
		lines.append(f"NVDA's reading position is now on the first of them, {name}. {_howToFix(found.first)}".strip())
	elif found.items:
		lines.append("Press F to move from field to field, Shift+F to move back.")
	return "\n".join(lines)


# --- The gist of a page, word for word ---

# Words that ask for a page as a whole in a few sentences, not for one thing on it.
_GIST = re.compile(
	r"\b(summar\w+|overview|gist|tl;?dr|in short|in brief|main points?|key points?"
	r"|what(?: is|'s) (?:this|the) (?:web ?page|page|article|site|web ?site|story|post) (?:all )?about)\b", re.IGNORECASE)
GIST_CHARS, GIST_LEAD = 700, "The page in its own words, the beginning of each part:"
_HEADING_CHARS = 70


def asksGist(part):
	"""Whether the user's words ask what a page is about as a whole."""
	return bool(_GIST.search(str(part or "")))


def _firstSentence(text, chars=220):
	match = re.search(r"(.+?[.!?])(\s|$)", text)
	sentence = match.group(1) if match else text
	return sentence if len(sentence) <= chars else sentence[:chars].rsplit(" ", 1)[0] + " ..."


def gist(text, chars=GIST_CHARS):
	"""The beginning of each part of a page's text, word for word: each heading with the first sentence under
	it. For a model that is asked one small question at a time and must not put a page into its own words, this
	is what "summarize this page" gets: nothing is rephrased, so nothing is made up. "" where the text has no
	sentences. A row of short lines without a sentence between them is a menu, and is left out."""
	lines = [" ".join(line.split()) for line in str(text or "").splitlines()]
	lines = [line for line in lines if line and line != "..."]
	if lines and lines[0].lower().startswith("from the web page"):
		lines = lines[1:]

	def isHeading(line):
		return len(line) <= _HEADING_CHARS and line[-1:] not in ".!?:;,"

	pieces, heading, afterText = [], "", False
	for line in lines:
		if isHeading(line):
			heading, afterText = line, False
			continue
		if afterText:
			continue  # only the beginning of each part
		sentence = _firstSentence(line)
		pieces.append(f"{heading}: {sentence}" if heading else sentence)
		heading, afterText = "", True
	out = []
	for piece in pieces:
		if out and len(" ".join(out)) + len(piece) + 1 > chars:
			break
		out.append(piece if piece[-1:] in ".!?" else piece + ".")
	return f"{GIST_LEAD} " + " ".join(out) if out else ""
