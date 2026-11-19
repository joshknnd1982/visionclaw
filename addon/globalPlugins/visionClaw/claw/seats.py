# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a seat map, as plain logic. An airline's seat map is a grid of small squares that a sighted person
# takes in at a glance: which seats are free, which are at a window, where the exits are. A screen reader user
# gets, at best, a hundred buttons called "12A", and at worst one picture. Here:
#   - what the user's own words ask is read by plain code (seatWish): a window, aisle or middle seat; at the front
#     or the back; ahead of, over or behind the wing; in an exit row; in or near a row; or one seat by its number;
#   - the map is read from the names of its seats where the page gives any (fromNames): row, letter, free or
#     taken, a price, and whatever else the name says, such as window, exit row or over wing;
#   - or, as a fallback, from the picture (fromPicture): the seat numbers or the row numbers and column letters
#     read in it, the colour of every seat measured from its pixels, and the legend that says which colour is free;
#   - the seats that fit are put in order by plain rules (choose), each with its reason in words.
# Nothing is guessed in silence. Where the page does not say which seats are at a window or an aisle, that is
# worked out from the seat letters as most aircraft are lettered, and the answer says so. Where the map does not
# show the wing, the answer says that, and offers the front rows instead of rows that might be ahead of it. Where
# a picture has no legend that can be read, the answer says that which seats are free could not be told.
# A seat is only ever pressed after a question, because choosing a seat may cost money (shoptools.py).
# Every sentence the user is told about this is here. No NVDA dependencies.

import re

from . import colours, spots
from .shopping import MONEY

WINDOW, AISLE, MIDDLE = "window", "aisle", "middle"
FRONT, BACK, AHEAD_OF_WING, BEHIND_WING, OVER_WING, EXIT = "front", "back", "ahead of the wing", "behind the wing", "over the wing", "exit row"
# Where what is known of a map comes from.
NAMES, PICTURE = "names", "picture"
FROM_PAGE, FROM_LETTERS, FROM_GAPS = "page", "letters", "gaps"
LETTERS = "ABCDEFGHIJKL"
# Fewer seats than this are no seat map.
MIN_SEATS = 6
COUNT, MAX_COUNT = 3, 8
# Two colours measured in a picture are one colour when they differ by less than this (colours.distance).
SAME_COLOUR = 70
# How seats are lettered across a row on most aircraft, and which letters are then at an aisle. From the letters
# alone this is not certain, so an answer that rests on it says so.
LAYOUTS = {
	"ABCDEF": "CD", "ACDF": "CD", "ABCD": "BC", "ACDEF": "CD", "ABCDEFGHJK": "CDGH", "ABCDEFGHJ": "CDFG",
	"ABCDEGHJK": "CDGH", "ACDEFGHK": "CDGH", "ABDEFGJK": "BDGJ", "ADGK": "DG",
}
_SEAT_WORD = re.compile(r"\bseats?\b|\bseat ?maps?\b|\bseating\b", re.IGNORECASE)
_PROGRAM_WINDOW = re.compile(r"\b(?:in|on|of|from)\s+(?:this|the|that|my)\s+(?:browser\s+)?window\b(?!\s+seat)", re.IGNORECASE)
_KINDS = ((WINDOW, r"\bwindows?\b"), (AISLE, r"\baisles?\b"), (MIDDLE, r"\b(?:middle|centre|center)\s+seats?\b|\bseats?\s+in\s+the\s+middle\b"))
# The wing is looked for first: "in front of the wing" is no wish for the front of the aircraft.
_ZONES = (
	(AHEAD_OF_WING, r"\b(?:ahead of|in front of|forward of|before|front of)\s+(?:the\s+)?wings?\b"),
	(BEHIND_WING, r"\b(?:behind|aft of|back of|after|past)\s+(?:the\s+)?wings?\b"),
	(OVER_WING, r"\b(?:over|on|above|at|by|near|beside)\s+(?:the\s+)?wings?\b|\bover ?wing\b"),
	(EXIT, r"\b(?:emergency\s+)?exit(?:\s+rows?)?\b"),
	(FRONT, r"\b(?:front|forward|nose)\b|\bas far forward\b"),
	(BACK, r"\b(?:back|rear|tail)\b"),
)
_ROW = re.compile(r"\brow\s+(\d{1,2})\b", re.IGNORECASE)
_NEAR_ROW = re.compile(r"\b(?:near|around|close to|by|next to|about)\s+row\s+\d{1,2}\b", re.IGNORECASE)
_ASKED_SEAT = re.compile(r"\b(\d{1,2})\s?([A-La-l])\b(?!\w)")
_ACTS = re.compile(r"\b(click|select|choose|pick|reserve|book|take|grab|press|get me|give me|put me)\b", re.IGNORECASE)
_TOGETHER = re.compile(r"\b(together|next to each other|side by side|adjacent|beside each other)\b", re.IGNORECASE)
_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
_COUNT = re.compile(
	r"\b(?:best|top|first|show me|tell me|give me|list)\s+(\d|one|two|three|four|five|six|seven|eight)\b"
	r"|\b(\d|two|three|four|five|six|seven|eight)\s+(?:choices|options|candidates|suggestions)\b", re.IGNORECASE)
# A seat's number in the name of a control, as pages write it.
_ID_ROW_SEAT = re.compile(r"\brow\s+(\d{1,2})\b.{0,24}?\bseat\s+([A-L])\b", re.IGNORECASE)
_ID_SEAT_ROW = re.compile(r"\bseat\s+([A-L])\b.{0,24}?\brow\s+(\d{1,2})\b", re.IGNORECASE)
_ID = re.compile(r"(?<![\w$.,])(\d{1,2})\s?-?\s?([A-L])(?!\w)")
_ID_SMALL = re.compile(r"(?<![\w$.,])(\d{1,2})([a-l])(?!\w)")
_TAKEN = re.compile(
	r"\b(occupied|unavailable|not available|taken|reserved|blocked|sold|booked|not selectable|cannot be selected|not for sale)\b", re.IGNORECASE)
_FREE = re.compile(r"\b(available|open|free|vacant|selectable|can be selected)\b", re.IGNORECASE)
_CHOSEN = re.compile(r"\b(selected|your seat|chosen|current seat|my seat|your selection)\b", re.IGNORECASE)
_NO_CHARGE = re.compile(r"\b(free of charge|no (?:extra |additional )?(?:charge|fee|cost)|included|complimentary)\b", re.IGNORECASE)
_EXIT_WORD = re.compile(r"\bexit\b", re.IGNORECASE)
_WING_WORD = re.compile(r"\bover ?wing\b|\bwings?\b", re.IGNORECASE)
_ROWS_RANGE = re.compile(r"\brows?\s+(\d{1,2})\s*(?:-|to|through|thru|–|and|&|,)\s*(\d{1,2})\b|\brows?\s+(\d{1,2})\b", re.IGNORECASE)
_NOTES = (
	("extra legroom", r"\b(?:extra|more|additional)\s+leg ?room\b"), ("bulkhead", r"\bbulkhead\b"),
	("limited recline", r"\b(?:limited|no|restricted)\s+recline\b"), ("near a lavatory", r"\b(?:lavatory|lavatories|toilets?|restrooms?)\b"),
	("near the galley", r"\bgalley\b"), ("no window", r"\b(?:no|without|missing)\s+window\b"),
)
# Words of a legend in a picture, by what they say of a seat.
_LEGEND = (("free", r"^(?:available|open|free|vacant)$"), ("taken", r"^(?:occupied|unavailable|taken|reserved|blocked)$"),
	("chosen", r"^(?:selected|chosen)$"))


class Seat:
	"""One seat of a map, with what is known of it."""

	def __init__(self, row, letter, ref=None, label=""):
		self.row, self.letter, self.ref, self.label = row, letter, ref, label
		# True, False, or None where it could not be told.
		self.free = None
		# Whether the map says it in words or by its legend; otherwise it is only that the seat can be pressed.
		self.stated = False
		self.chosen = False
		self.price = ""
		self.kind = None
		self.exit = False
		self.wing = False
		self.notes = []

	@property
	def id(self):
		return f"{self.row}{self.letter}"


class SeatMap:
	"""A seat map: its seats by number, and where what is known of them comes from."""

	def __init__(self, source):
		self.source = source
		self.seats = {}
		self.wingRows = set()
		# Whether the rows at the wing are named by the map itself, or only marked by a word in a picture, which
		# shows one place and not how far the wing reaches.
		self.wingByWord = False
		self.exitRows = set()
		self.kindsFrom = None
		self.legend = {}

	def isMap(self):
		return len(self.seats) >= MIN_SEATS

	def rows(self):
		return sorted({seat.row for seat in self.seats.values()})

	def freeKnown(self):
		return any(seat.free is not None for seat in self.seats.values())

	def inOrder(self):
		return sorted(self.seats.values(), key=lambda seat: (seat.row, seat.letter))


def seatWish(part):
	"""What the user's own words ask of a seat map, or None when they speak of no seat: {"kind": WINDOW, AISLE,
	MIDDLE or None; "zone": FRONT, BACK, AHEAD_OF_WING, BEHIND_WING, OVER_WING, EXIT or None; "row": a row number
	or None; "nearRow": whether rows near it will do; "seat": one seat by its number ("12A") or None; "count": how
	many seats to tell; "act": whether a seat is to be chosen, or only found and told; "together": whether the
	words ask for seats next to each other, which is not done}."""
	text = " ".join(str(part or "").split())
	if not _SEAT_WORD.search(text):
		return None
	if re.search(r"\bhow (?:do|can|would|should|could) (?:i|we|you|one)\b|\bhow to\b", text, re.IGNORECASE):
		return None
	words = _PROGRAM_WINDOW.sub(" ", text)
	kind = next((value for value, pattern in _KINDS if re.search(pattern, words, re.IGNORECASE)), None)
	zone = next((value for value, pattern in _ZONES if re.search(pattern, words, re.IGNORECASE)), None)
	row = _ROW.search(words)
	seat = None
	for found in _ASKED_SEAT.finditer(words):
		# "Row 12 a window seat" names no seat 12A: a small letter must stand right at its number.
		if found.group(2).isupper() or " " not in found.group(0):
			seat = f"{int(found.group(1))}{found.group(2).upper()}"
			break
	count = COUNT
	counted = _COUNT.search(words)
	if counted:
		said = (counted.group(1) or counted.group(2)).lower()
		count = max(1, min(MAX_COUNT, _NUMBERS.get(said) or int(said)))
	return {
		"kind": kind, "zone": zone, "row": int(row.group(1)) if row and seat is None else None,
		"nearRow": bool(_NEAR_ROW.search(words)), "seat": seat, "count": count, "act": bool(_ACTS.search(words)),
		"together": bool(_TOGETHER.search(words))}


def _idOf(label):
	"""The seat a control's name is about: (row, letter), or None."""
	found = _ID_ROW_SEAT.search(label)
	if found:
		return int(found.group(1)), found.group(2).upper()
	found = _ID_SEAT_ROW.search(label)
	if found:
		return int(found.group(2)), found.group(1).upper()
	found = _ID.search(label)
	if found:
		return int(found.group(1)), found.group(2)
	# A small letter only where the name says it is a seat: "3d" alone may be anything.
	if _SEAT_WORD.search(label):
		found = _ID_SMALL.search(label)
		if found:
			return int(found.group(1)), found.group(2).upper()
	return None


def _rowsNamed(label):
	"""The rows a name speaks of: "rows 10 to 20" is every row from 10 to 20, "row 14" is 14."""
	rows = set()
	for found in _ROWS_RANGE.finditer(label):
		if found.group(1):
			first, last = int(found.group(1)), int(found.group(2))
			joiner = label[found.start():found.end()].lower()
			if re.search(r"-|to|through|thru|–", joiner):
				rows.update(range(min(first, last), max(first, last) + 1))
			else:
				rows.update((first, last))
		else:
			rows.add(int(found.group(3)))
	return rows


def _kindsFromLetters(seatMap):
	"""Which seats are at a window or an aisle, worked out from the seat letters where the map does not say: the
	first and the last letter are at the windows; the aisle letters are taken from how most aircraft are lettered,
	and left unknown where the letters fit no usual way."""
	seats = [seat for seat in seatMap.seats.values() if seat.kind is None]
	if not seats:
		return
	letters = sorted({seat.letter for seat in seatMap.seats.values()})
	if len(letters) < 2:
		return
	windows = {letters[0], letters[-1]}
	whole = LAYOUTS.get("".join(letters))
	byRow = {}
	for seat in seatMap.seats.values():
		byRow.setdefault(seat.row, set()).add(seat.letter)
	changed = False
	for seat in seats:
		aisles = LAYOUTS.get("".join(sorted(byRow[seat.row]))) or whole
		if seat.letter in windows:
			seat.kind = WINDOW
		elif aisles is None:
			continue
		else:
			seat.kind = AISLE if seat.letter in aisles else MIDDLE
		changed = True
	if changed and seatMap.kindsFrom is None:
		seatMap.kindsFrom = FROM_LETTERS


def fromNames(controls):
	"""A seat map from the controls of a web page or window, in reading order. controls: [{"label": its name or
	text, "ref": what presses it, "usable": False when it is greyed out, "marked": True when it is selected}]. A
	seat is a control whose name has a row number and a seat letter. What the name says besides is kept: free or
	taken, a price, window or aisle, exit row, over wing. A control that only says "aisle" between two seats of a
	row marks them as aisle seats; one that names the rows of the wing or of an exit marks those rows."""
	seatMap = SeatMap(NAMES)
	aisleLetters = set()
	last, pending = None, None
	for control in controls:
		label = " ".join(str(control.get("label") or "").split())
		if not label:
			continue
		found = _idOf(label)
		if found is None:
			low = label.lower()
			if re.fullmatch(r"aisle\W*", low) and last is not None:
				pending = last
			elif _WING_WORD.search(label):
				seatMap.wingRows.update(_rowsNamed(label))
			elif _EXIT_WORD.search(label):
				seatMap.exitRows.update(_rowsNamed(label))
			continue
		row, letter = found
		ident = f"{row}{letter}"
		if ident in seatMap.seats and seatMap.seats[ident].stated:
			# The same seat twice, as a cell and the button inside it: the first that says something counts.
			continue
		seat = Seat(row, letter, control.get("ref"), label)
		# What the name says of the seat, without its own number: "12A" has no word in it.
		words = _ID.sub(" ", label)
		# "Not selected" says nothing about whether the seat is free.
		words = re.sub(r"\b(?:not|un)[- ]?selected\b", " ", words, flags=re.IGNORECASE)
		usable = control.get("usable", True)
		if control.get("marked") or _CHOSEN.search(words):
			seat.chosen, seat.free, seat.stated = True, False, True
		elif _TAKEN.search(words):
			seat.free, seat.stated = False, True
		elif not usable:
			seat.free = False
		elif _FREE.search(words):
			seat.free, seat.stated = True, True
		else:
			seat.free = True
		money = MONEY.search(label)
		if money:
			seat.price = money.group(0).strip()
		elif _NO_CHARGE.search(words):
			seat.price = "no charge"
		for kind, pattern in _KINDS[:2] + ((MIDDLE, r"\b(?:middle|centre|center)\b"),):
			if re.search(pattern, words, re.IGNORECASE) and not re.search(r"\b(?:no|without|missing)\s+window\b", words, re.IGNORECASE):
				seat.kind = kind
				seatMap.kindsFrom = FROM_PAGE
				break
		seat.exit = bool(_EXIT_WORD.search(words))
		seat.wing = bool(_WING_WORD.search(words))
		seat.notes = [note for note, pattern in _NOTES if re.search(pattern, words, re.IGNORECASE)]
		if seat.wing:
			seatMap.wingRows.add(row)
		if seat.exit:
			seatMap.exitRows.add(row)
		if pending is not None and pending.row == row:
			aisleLetters.update((pending.letter, letter))
		pending = None
		seatMap.seats[ident] = seat
		last = seat
	if aisleLetters:
		seatMap.kindsFrom = FROM_PAGE
		letters = sorted({seat.letter for seat in seatMap.seats.values()})
		for seat in seatMap.seats.values():
			if seat.kind is None:
				seat.kind = AISLE if seat.letter in aisleLetters else WINDOW if seat.letter in (letters[0], letters[-1]) else MIDDLE
	for seat in seatMap.seats.values():
		if seat.row in seatMap.exitRows:
			seat.exit = True
		if seat.row in seatMap.wingRows:
			seat.wing = True
	_kindsFromLetters(seatMap)
	return seatMap


def _box(word):
	return spots.wordBox(word)


def _aligned(words, upright):
	"""The largest group of words that stand in one line: in one column (upright) or in one row."""
	best = []
	for word in words:
		middle = word["x"] + word["width"] / 2.0 if upright else word["y"] + word["height"] / 2.0
		reach = max(4, word["height"] * 0.6)
		group = [other for other in words if abs(
			(other["x"] + other["width"] / 2.0 if upright else other["y"] + other["height"] / 2.0) - middle) <= reach]
		if len(group) > len(best):
			best = group
	return best


def legendOf(lines, colourAt):
	"""The legend of a drawn seat map: for "free", "taken" and "chosen", the colour (red, green, blue) of the small
	block that stands next to the legend's word. A legend's word stands alone; the same word inside a sentence is
	none. colourAt(box) gives the colour of an area of the picture, or None."""
	found = {}
	for line in lines or ():
		for word in line:
			text = re.sub(r"[^a-z]", "", word.get("text", "").lower())
			meaning = next((name for name, pattern in _LEGEND if re.match(pattern, text)), None)
			if meaning is None or meaning in found:
				continue
			box = _box(word)
			tall = max(6, word["height"])
			# Other words close by on the same line make it a sentence, unless they belong to the legend too
			# ("Not available" is read as the word after "Not").
			beside = [other for _distance, other in spots.near([line], box, tall * 0.9) if other is not word]
			if any(not re.match(r"^(?:seats?|not|-|:)?$", re.sub(r"[^a-z:-]", "", other.get("text", "").lower())) for other in beside):
				continue
			ground = colourAt((box[0], box[1] - tall, box[2], box[1] - tall * 0.3)) or colourAt((box[0], box[3] + tall * 0.3, box[2], box[3] + tall))
			for sample in ((box[0] - tall * 1.7, box[1], box[0] - tall * 0.4, box[3]), (box[2] + tall * 0.4, box[1], box[2] + tall * 1.7, box[3])):
				colour = colourAt(sample)
				if colour is not None and (ground is None or colours.distance(colour, ground) > 40):
					found[meaning] = colour
					break
	return found


def _across(seatMap, places, upright):
	"""Windows and aisles from where the columns of seats stand in a picture: the outermost columns are at the
	windows, and the columns on either side of a gap wider than the usual space are at an aisle."""
	byLetter = {}
	for ident, (x, y) in places.items():
		byLetter.setdefault(seatMap.seats[ident].letter, []).append(x if upright else y)
	if len(byLetter) < 2:
		return
	columns = sorted((sorted(values)[len(values) // 2], letter) for letter, values in byLetter.items())
	gaps = [columns[index + 1][0] - columns[index][0] for index in range(len(columns) - 1)]
	usual = sorted(gaps)[0] if gaps else 0
	aisles = set()
	for index, gap in enumerate(gaps):
		if usual and gap > usual * 1.5:
			aisles.update((columns[index][1], columns[index + 1][1]))
	windows = {columns[0][1], columns[-1][1]}
	for seat in seatMap.seats.values():
		seat.kind = WINDOW if seat.letter in windows else AISLE if seat.letter in aisles else MIDDLE
	seatMap.kindsFrom = FROM_GAPS


def fromPicture(lines, colourAt, legend=None):
	"""A seat map from a picture with no names, as a fallback: from the words read in it and the colour of each
	seat. lines: the text read in the picture (ocr.py's lines of words). colourAt(box): the colour (red, green,
	blue) of an area of the picture, or None; the caller builds it from colours.middle. legend: what legendOf
	found, or None to look for it here. Seats are found by their numbers written in them ("12A"), or by the row
	numbers and column letters around the grid. A seat is free where its colour is the legend's colour for free;
	where the picture has no legend that can be read, free stays unknown for every seat. A seat's ref is the
	middle of its place in the picture, (x, y), for the mouse."""
	seatMap = SeatMap(PICTURE)
	words = [word for line in lines or () for word in line if word.get("text", "").strip()]
	places, sizes = {}, {}
	for word in words:
		found = re.fullmatch(r"(\d{1,2})([A-L])", word["text"].strip())
		if found:
			ident = f"{int(found.group(1))}{found.group(2)}"
			box = _box(word)
			tall = max(4, box[3] - box[1])
			places[ident] = spots.middleOf(box)
			# The seat's own colour is measured just above its number, where no letter is drawn.
			sizes[ident] = (box[0], box[1] - tall * 0.6, box[2], box[1] - tall * 0.1)
			seatMap.seats[ident] = Seat(int(found.group(1)), found.group(2), places[ident], word["text"].strip())
	upright = True
	if len(seatMap.seats) < MIN_SEATS:
		# Row numbers down one side and column letters along another.
		seatMap.seats, places, sizes = {}, {}, {}
		letters = [word for word in words if re.fullmatch(r"[A-L]", word["text"].strip())]
		numbers = [word for word in words if re.fullmatch(r"\d{1,2}", word["text"].strip())]
		for upright in (True, False):
			columns = _aligned(letters, not upright)
			rows = _aligned(numbers, upright)
			if len(columns) >= 2 and len(rows) >= 3:
				break
		else:
			return seatMap
		middles = lambda word: (word["x"] + word["width"] / 2.0, word["y"] + word["height"] / 2.0)
		spans = sorted(middles(word)[0 if upright else 1] for word in columns)
		pitch = min((spans[index + 1] - spans[index] for index in range(len(spans) - 1)), default=20)
		half = max(4, pitch * 0.3)
		for number in rows:
			for letter in columns:
				x = middles(letter)[0] if upright else middles(number)[0]
				y = middles(number)[1] if upright else middles(letter)[1]
				ident = f"{int(number['text'])}{letter['text'].strip()}"
				places[ident] = (round(x), round(y))
				sizes[ident] = (x - half, y - half, x + half, y + half)
				seatMap.seats[ident] = Seat(int(number["text"]), letter["text"].strip(), places[ident], ident)
	else:
		# Which way the rows run: the seats of one row stand side by side, or one above the other.
		byRow = {}
		for ident, (x, y) in places.items():
			byRow.setdefault(seatMap.seats[ident].row, []).append((x, y))
		wide = sum(max(x for x, _y in row) - min(x for x, _y in row) for row in byRow.values())
		high = sum(max(y for _x, y in row) - min(y for _x, y in row) for row in byRow.values())
		upright = wide >= high
	if not seatMap.isMap():
		return seatMap
	seatMap.legend = legend if legend is not None else legendOf(lines, colourAt)
	known = {name: colour for name, colour in seatMap.legend.items() if colour is not None}
	for ident, seat in seatMap.seats.items():
		colour = colourAt(sizes[ident])
		if colour is None or "free" not in known:
			continue
		nearest = min(known, key=lambda name: colours.distance(colour, known[name]))
		if colours.distance(colour, known[nearest]) > SAME_COLOUR:
			# A colour the legend does not explain: taken for not free, since only the legend's colour is free.
			seat.free = False
			continue
		seat.free, seat.stated = nearest == "free", True
		seat.chosen = nearest == "chosen"
	_across(seatMap, places, upright)
	# The words Wing and Exit in the picture mark the rows they stand beside, no more.
	along = {}
	for ident, (x, y) in places.items():
		along.setdefault(seatMap.seats[ident].row, []).append(y if upright else x)
	rowAt = {row: sorted(values)[len(values) // 2] for row, values in along.items()}
	spread = sorted(rowAt.values())
	pitch = min((spread[index + 1] - spread[index] for index in range(len(spread) - 1)), default=0) or 20
	for word in words:
		text = re.sub(r"[^a-z]", "", word["text"].lower())
		if text not in ("wing", "wings", "exit", "exits"):
			continue
		start, end = (word["y"], word["y"] + word["height"]) if upright else (word["x"], word["x"] + word["width"])
		beside = {row for row, at in rowAt.items() if start - pitch * 0.5 <= at <= end + pitch * 0.5}
		if text.startswith("wing"):
			seatMap.wingRows.update(beside)
			seatMap.wingByWord = True
		else:
			seatMap.exitRows.update(beside)
	for seat in seatMap.seats.values():
		seat.exit = seat.row in seatMap.exitRows
		seat.wing = seat.row in seatMap.wingRows
	return seatMap


def reason(seat):
	"""A seat with what is known of it, in words: "12A: window, row 12, free, $15"."""
	parts = []
	if seat.kind:
		parts.append(seat.kind)
	parts.append(f"row {seat.row}")
	if seat.chosen:
		parts.append("chosen now")
	elif seat.free is True:
		parts.append("free" if seat.stated else "can be chosen")
	elif seat.free is False:
		parts.append("taken")
	if seat.exit:
		parts.append("exit row")
	if seat.wing:
		parts.append("at the wing")
	parts.extend(seat.notes)
	if seat.price:
		parts.append(seat.price)
	return f"{seat.id}: " + ", ".join(parts)


def choose(seatMap, wish):
	"""The seats that fit what was asked, the best first: ([seats], [sentences that say what could not be done as
	asked]). Only free seats are offered. "Ahead of the wing" is only answered where the map itself says where the
	wing is; where it does not, the sentence says so and the front rows are offered instead."""
	notes = []
	everything = seatMap.inOrder()
	if wish.get("together"):
		notes.append("VisionClaw looks for one seat at a time; it does not look for seats next to each other yet.")
	if wish.get("seat"):
		seat = seatMap.seats.get(wish["seat"])
		if seat is None:
			return [], notes + [f"This map has no seat {wish['seat']}."]
		if seat.chosen:
			return [], notes + [f"Seat {seat.id} is the seat that is chosen now."]
		if seat.free is False:
			return [], notes + [f"Seat {seat.id} is taken."]
		if seat.free is None:
			notes.append(f"Whether seat {seat.id} is free could not be told from this map.")
		return [seat], notes
	if not seatMap.freeKnown():
		return [], notes + [
			"Which seats are free could not be told: the picture has no legend that VisionClaw could read, and the "
			"seats have no names. Ask what the picture of the seat map shows, and the model that sees pictures looks "
			"at it; a model can be wrong."]
	pool = [seat for seat in everything if seat.free is True and not seat.chosen]
	kind = wish.get("kind")
	if kind:
		if not any(seat.kind == kind for seat in everything):
			if kind == WINDOW or not any(seat.kind for seat in everything):
				notes.append(f"This map does not say which seats are {_kindWords(kind)}, and it could not be worked out, so every free seat is offered.")
			else:
				notes.append(
					f"Which seats are {_kindWords(kind)} could not be told from this map: its seat letters fit no usual way "
					"of lettering. Every free seat is offered.")
		else:
			pool = [seat for seat in pool if seat.kind == kind]
	zone = wish.get("zone")
	order = lambda seat: (seat.row, seat.letter)
	if zone in (AHEAD_OF_WING, BEHIND_WING, OVER_WING):
		if not seatMap.wingRows:
			if zone == AHEAD_OF_WING:
				notes.append(
					"This map does not show where the wing is, so VisionClaw cannot say which rows are ahead of it. "
					"These are the nearest to the front instead.")
			elif zone == BEHIND_WING:
				notes.append(
					"This map does not show where the wing is, so VisionClaw cannot say which rows are behind it. "
					"These are the nearest to the back instead.")
				order = lambda seat: (-seat.row, seat.letter)
			else:
				return [], notes + [
					"This map does not show where the wing is, so VisionClaw cannot say which rows are over it. Name a "
					"row instead, such as: a window seat near row 14."]
		else:
			first, last = min(seatMap.wingRows), max(seatMap.wingRows)
			if seatMap.wingByWord:
				notes.append(
					f"The picture has the word wing beside {_rowsText(seatMap.wingRows)}; how far the wing reaches is not "
					"shown, so a row close to it may still be at the wing.")
			if zone == AHEAD_OF_WING:
				pool = [seat for seat in pool if seat.row < first]
			elif zone == BEHIND_WING:
				pool = [seat for seat in pool if seat.row > last]
			else:
				pool = [seat for seat in pool if seat.row in seatMap.wingRows]
	elif zone == EXIT:
		if not seatMap.exitRows:
			return [], notes + ["This map does not say which rows are exit rows. Name a row instead."]
		pool = [seat for seat in pool if seat.exit]
	elif zone == BACK:
		order = lambda seat: (-seat.row, seat.letter)
	row = wish.get("row")
	if row is not None:
		inRow = [seat for seat in pool if seat.row == row]
		if inRow and not wish.get("nearRow"):
			pool = inRow
		else:
			if not inRow and not wish.get("nearRow"):
				notes.append(f"No free seat of that kind is in row {row}. These are the nearest rows.")
			order = lambda seat: (abs(seat.row - row), seat.row, seat.letter)
	pool.sort(key=order)
	return pool[:max(1, min(MAX_COUNT, wish.get("count") or COUNT))], notes


def _kindWords(kind):
	return {WINDOW: "at a window", AISLE: "at an aisle", MIDDLE: "in the middle"}[kind]


def _rowsText(rows):
	rows = sorted(rows)
	if len(rows) == 1:
		return f"row {rows[0]}"
	if rows == list(range(rows[0], rows[-1] + 1)):
		return f"rows {rows[0]} to {rows[-1]}"
	return "rows " + ", ".join(str(row) for row in rows[:-1]) + f" and {rows[-1]}"


def mapText(seatMap):
	"""What the map has, in one or two sentences, and where what is said of it comes from."""
	rows = seatMap.rows()
	seats = seatMap.seats.values()
	free = sum(1 for seat in seats if seat.free is True and not seat.chosen)
	where = ("read from the names of its seats" if seatMap.source == NAMES else "read from the picture of the window")
	said = f"The seat map, {where}, has {_rowsText(rows)} with {len(seatMap.seats)} seats"
	if seatMap.freeKnown():
		stated = any(seat.stated for seat in seats if seat.free is True)
		said += f"; {free} of them are free." if stated else f"; {free} of them can be chosen, which usually means they are free."
	else:
		said += "; which of them are free could not be told."
	chosen = [seat.id for seat in seatMap.inOrder() if seat.chosen]
	if chosen:
		said += f" Chosen now: {', '.join(chosen)}."
	if seatMap.kindsFrom == FROM_LETTERS:
		said += (
			" Which seats are at a window or an aisle was worked out from the seat letters, as most aircraft are "
			"lettered; the map itself does not say.")
	elif seatMap.kindsFrom == FROM_GAPS:
		said += " Which seats are at a window or an aisle was worked out from the gaps between the columns in the picture."
	if seatMap.wingRows and not seatMap.wingByWord:
		said += f" The map says the wing is at {_rowsText(seatMap.wingRows)}."
	if seatMap.exitRows:
		said += f" The map marks an exit at {_rowsText(seatMap.exitRows)}."
	return said


def told(seatMap, wish, seats, notes):
	"""The answer when seats are only told: the map, what could not be done as asked, and the seats that fit."""
	parts = [mapText(seatMap)] + list(notes)
	if seats:
		parts.append(("The best fit: " if len(seats) == 1 else f"The best {len(seats)}: ") + "; ".join(reason(seat) for seat in seats) + ".")
		if not wish.get("act"):
			parts.append("To choose one, say: choose seat " + seats[0].id + ".")
	elif not notes:
		parts.append("No free seat fits what you asked for.")
	return " ".join(parts)


def question(seats):
	"""Asked before a seat is pressed, always: (the question, the choices, the last of which is to choose none)."""
	prices = [seat for seat in seats if seat.price]
	cost = ("The map gives a price for some of them. " if prices and len(seats) > 1 else
		f"The map says {seats[0].price} for it. " if prices else "")
	if len(seats) == 1:
		text = f"Choose seat {reason(seats[0])}? {cost}Choosing a seat may cost money."
		return text, ["Yes, choose it", "No, only tell me"]
	text = f"Which seat should VisionClaw choose? {cost}Choosing a seat may cost money."
	return text, [reason(seat) for seat in seats] + ["None, only tell me"]


def done(seat, after):
	"""What was done, and what the map says of the seat afterwards. after: the seat as the map shows it when read
	again, or None when it could not be read again."""
	said = f"Pressed seat {seat.id}."
	if after is None:
		return said + " The seat map could not be read again, so VisionClaw cannot say whether the seat is yours. Check before you go on."
	if after.chosen:
		return said + f" The map now marks {seat.id} as chosen."
	if after.free is False:
		return said + f" The map now shows {seat.id} as not free, which usually means it is held for you; it does not say chosen, so check before you go on."
	return said + f" The map does not mark {seat.id} as chosen, so the press may not have been taken, or the page may ask something first. Check before you go on."


NO_WISH = (
	"The request does not say what kind of seat is wanted. Say it in words, such as: find a free window seat near the "
	"front, or: choose seat 12A.")
NO_MAP = (
	"No seat map was found on this page or in this window: no seats with a row number and a letter, by their names "
	"or in the picture. If the map opens with a button, such as Choose seats, press that first and ask again.")
