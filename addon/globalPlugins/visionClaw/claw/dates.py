# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - choosing a date in a calendar that cannot be worked with the keyboard: "pick 14 March 2027 in this
# calendar", "choose next Friday in the date picker". Everything here is plain logic:
#   - which date the user's own words mean, also when they were spoken and the numbers came as words;
#   - what a calendar shows: its month and year, its days, and its buttons for the next and the previous month,
#     from the names NVDA has for a web page's or a window's controls, or from the text in the window's picture;
#   - the steps that get to the right month and press the right day, each one checked against what the calendar
#     shows afterwards, so that the user is told what happened and not what was attempted.
# A model writes nothing here. What reads the calendar and presses its buttons is in datetools.py.
# No NVDA dependencies.

import datetime
import re

MONTHS = (
	"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
	"december")
_SHORT = {name[:3]: number for number, name in enumerate(MONTHS, 1)}
_SHORT["sept"] = 9
_MONTH_NUMBER = dict({name: number for number, name in enumerate(MONTHS, 1)}, **_SHORT)
_MONTH = "(?:" + "|".join(sorted(_MONTH_NUMBER, key=len, reverse=True)) + r")\.?"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WEEKDAY = "(?:" + "|".join(WEEKDAYS) + ")"
# Numbers as words, as a spoken request has them.
_UNITS = {
	"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
	"eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
	"eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30}
_ORDINALS = {
	"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
	"tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
	"seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "thirtieth": 30}
_TENS_YEAR = {
	"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
FIRST_YEAR, LAST_YEAR = 1900, 2199
# How far a calendar is taken by pressing its button for the next or previous month.
MAX_MONTHS = 60
# Kinds of step.
PRESS_DAY, NEXT, PREVIOUS = "day", "next", "previous"


def _clean(text):
	return " ".join(str(text or "").split())


def numbersFromWords(text):
	"""A text with its numbers written as words turned into digits, where they are parts of a date: "the
	fourteenth of March twenty twenty-seven" becomes "the 14th of March 2027"."""
	# "Twenty-seven" is two words; the hyphens of 2027-03-14 stay.
	low = " " + re.sub(r"(?<=[a-z])-(?=[a-z])", " ", _clean(text).lower()) + " "
	# Years first: "twenty twenty seven", "two thousand twenty seven", "two thousand and five", "nineteen ninety nine".
	def year(hit):
		words = hit.group(0).split()
		words = [word for word in words if word != "and"]
		if words[:2] == ["two", "thousand"]:
			rest = words[2:]
			value = 2000 + _small(rest) if rest else 2000
		else:
			century = {"twenty": 20, "nineteen": 19}[words[0]]
			rest = words[1:]
			if rest[:1] == ["hundred"]:
				rest = rest[1:]
			if rest[:1] in (["oh"], ["o"]):
				rest = rest[1:]
			value = century * 100 + _small(rest)
		return f" {value} "
	tens = "|".join(_TENS_YEAR)
	units = "one|two|three|four|five|six|seven|eight|nine"
	teens = "ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
	# "Twenty one" is the day 21 and no year; the year 2001 is said "twenty oh one" or "two thousand one".
	small = rf"(?:(?:{tens})(?: (?:{units}))?|{teens}|(?:oh|o) (?:{units}))"
	low = re.sub(rf" two thousand(?: and)?(?: (?:{small}|{units}))? ", year, low)
	# "Twenty twenty seven" before "nineteen ...": in "March nineteen twenty twenty seven" the nineteen is the day.
	low = re.sub(rf" twenty (?:hundred(?: and)? )?{small} ", year, low)
	low = re.sub(rf" nineteen (?:hundred(?: and)? )?{small} ", year, low)
	# Days: "twenty first", "thirty first", "fourteenth", "twenty one", "fourteen".
	def day(hit):
		words = hit.group(0).split()
		value = 0
		ordinal = False
		for word in words:
			if word in _ORDINALS:
				value += _ORDINALS[word]
				ordinal = True
			else:
				value += _UNITS[word]
		return f" {value}{_suffix(value) if ordinal else ''} "
	ordinals = "|".join(sorted(_ORDINALS, key=len, reverse=True))
	low = re.sub(rf" (?:(?:twenty|thirty) )?(?:{ordinals}) ", day, low)
	names = "|".join(sorted(_UNITS, key=len, reverse=True))
	# A bare number word only next to a month: "March fourteen", "fourteen March". "One" elsewhere stays a word.
	low = re.sub(rf"(?<= )(?:(?:twenty|thirty) )?(?:{names}) (?={_MONTH} )", lambda hit: day(hit).lstrip(), low)
	low = re.sub(rf"({_MONTH}) ((?:(?:twenty|thirty) )?(?:{names})) ", lambda hit: hit.group(1) + day(_Fake(hit.group(2))), low)
	return _clean(low)


class _Fake:
	"""A match that holds one text, for a function that takes matches."""

	def __init__(self, text):
		self._text = text

	def group(self, index=0):
		return self._text


def _small(words):
	"""A number below a hundred from its words; 0 for none."""
	value = 0
	for word in words:
		value += _TENS_YEAR.get(word, 0) or _UNITS.get(word, 0)
	return value


def _suffix(number):
	if 10 <= number % 100 <= 20:
		return "th"
	return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def valid(year, month, day):
	try:
		datetime.date(year, month, day)
	except (ValueError, TypeError):
		return False
	return FIRST_YEAR <= year <= LAST_YEAR


def _year(text):
	year = int(text)
	if year < 100:
		year += 2000 if year < 70 else 1900
	return year


def _coming(month, day, today):
	"""The year of the next day that has this month and day, counting today."""
	for year in (today.year, today.year + 1, today.year + 2, today.year + 3, today.year + 4):
		if valid(year, month, day) and datetime.date(year, month, day) >= today:
			return year
	return None


_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(\d{4})"
_PATTERNS = (
	# 14 March 2027, the 14th of March 2027, 14 Mar, 2027
	("dmy", re.compile(rf"\b{_DAY}(?: of)? ({_MONTH})(?:,? {_YEAR})?\b")),
	# March 14, 2027; March 14th; March the 14th 2027
	("mdy", re.compile(rf"\b({_MONTH})(?: the)? {_DAY}(?!\d)(?:,? {_YEAR})?\b")),
)
_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_NUMERIC = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4}|\d{2})\b")
_RELATIVE = re.compile(
	rf"\b(?P<today>today)\b|\b(?P<after>the day after tomorrow)\b|\b(?P<tomorrow>tomorrow)\b|\b(?P<yesterday>yesterday)\b"
	rf"|\bin (?P<count>\d{{1,3}}|a|an|one|two|three|four|five|six|seven|eight|nine|ten) (?P<unit>days?|weeks?|months?)\b"
	rf"|\b(?P<count2>\d{{1,3}}|a|an|one|two|three|four|five|six|seven|eight|nine|ten) (?P<unit2>days?|weeks?) from (?:today|now)\b"
	rf"|\b(?P<which>next|this|this coming|coming|on)? ?(?P<weekday>{_WEEKDAY})(?P<after2> after next| next week)?\b")
# A day alone, "the 30th", is a date only where nothing follows that it could count: "the first link" is none.
_DAY_ONLY = re.compile(r"\bthe (\d{1,2})(?:st|nd|rd|th)(?= (?:in|on|of|at|from|please|as|for)\b|\s*$|\s*[.,;!?])")


def parse(text, today=None):
	"""The dates a text may mean, as [(year, month, day)]: one where the words are clear, two where a date in
	numbers can be read both ways (3/4/2027), none where no date is said. A date without a year is the next
	day that has that month and day."""
	today = today or datetime.date.today()
	low = numbersFromWords(text)
	hit = _ISO.search(low)
	if hit and valid(int(hit.group(1)), int(hit.group(2)), int(hit.group(3))):
		return [(int(hit.group(1)), int(hit.group(2)), int(hit.group(3)))]
	for order, pattern in _PATTERNS:
		for hit in pattern.finditer(low):
			if order == "dmy":
				day, month, year = int(hit.group(1)), _MONTH_NUMBER[hit.group(2).rstrip(".")], hit.group(3)
			else:
				month, day, year = _MONTH_NUMBER[hit.group(1).rstrip(".")], int(hit.group(2)), hit.group(3)
			year = int(year) if year else _coming(month, day, today)
			if year and valid(year, month, day):
				return [(year, month, day)]
	hit = _NUMERIC.search(low)
	if hit:
		first, second, year = int(hit.group(1)), int(hit.group(2)), _year(hit.group(3))
		found = []
		for month, day in ((first, second), (second, first)):
			if valid(year, month, day) and (year, month, day) not in found:
				found.append((year, month, day))
		if found:
			return found
	hit = _RELATIVE.search(low)
	if hit:
		found = _relative(hit, today)
		if found is not None:
			dates = [(found.year, found.month, found.day)]
			# "Next Friday" is the coming Friday to some people and the Friday of next week to others.
			if hit.groupdict().get("weekday") and (hit.group("which") or "") == "next" and not hit.group("after2"):
				later = found + datetime.timedelta(days=7)
				dates.append((later.year, later.month, later.day))
			return dates
	hit = _DAY_ONLY.search(low)
	if hit:
		day = int(hit.group(1))
		# The next day of that number, this month or the next.
		for add in range(0, 3):
			month = (today.month - 1 + add) % 12 + 1
			year = today.year + (today.month - 1 + add) // 12
			if valid(year, month, day) and datetime.date(year, month, day) >= today:
				return [(year, month, day)]
	return []


def _count(text):
	return 1 if text in ("a", "an") else _UNITS.get(text) or int(text)


def _relative(hit, today):
	groups = hit.groupdict()
	if groups.get("today"):
		return today
	if groups.get("after"):
		return today + datetime.timedelta(days=2)
	if groups.get("tomorrow"):
		return today + datetime.timedelta(days=1)
	if groups.get("yesterday"):
		return today - datetime.timedelta(days=1)
	count, unit = groups.get("count") or groups.get("count2"), groups.get("unit") or groups.get("unit2")
	if count and unit:
		number = _count(count)
		if unit.startswith("day"):
			return today + datetime.timedelta(days=number)
		if unit.startswith("week"):
			return today + datetime.timedelta(weeks=number)
		month = today.month - 1 + number
		year, month = today.year + month // 12, month % 12 + 1
		day = today.day
		while day > 28 and not valid(year, month, day):
			day -= 1
		return datetime.date(year, month, day)
	if groups.get("weekday"):
		wanted = WEEKDAYS.index(groups["weekday"])
		ahead = (wanted - today.weekday()) % 7
		# "Friday" said on a Friday is the Friday a week from now; "this Friday" too, as people mean it.
		ahead = ahead or 7
		if groups.get("after2"):
			ahead += 7
		return today + datetime.timedelta(days=ahead)
	return None


# Words that say a calendar is to be worked, and a date chosen in it.
_PICKS = re.compile(
	r"\b(pick|choose|select|set|click|press|go to|jump to|move to|put in|enter|change|take|mark|book|use)\b", re.IGNORECASE)
_CALENDAR = re.compile(
	r"\b(calendars?|date ?pickers?|date ?choosers?|date (field|box|control|selector)|month view|(the|this|that|a|as the|"
	r"start|end|departure|arrival|return|check[- ]?in|check[- ]?out|due|birth|delivery|appointment|travel|pick[- ]?up) date)\b"
	r"|\bdate of (birth|departure|arrival|travel)\b", re.IGNORECASE)
_HOW = re.compile(r"\bhow (do|can|would|should|could) (i|we|you|one)\b|\bhow to\b|\bwhat (is|was|day)\b|\bwhich (day|date)\b", re.IGNORECASE)


def wish(part, today=None):
	"""What the user's own words ask of a calendar: {"dates": the dates they may mean, "said": their words}; None
	when they name no calendar, no date, or only ask how something is done or what the date is."""
	text = _clean(re.sub(r"\(this follows:.*?\)\s*$", "", str(part or "")))
	if not text or _HOW.search(text) or not _PICKS.search(text) or not _CALENDAR.search(numbersFromWords(text)):
		return None
	found = parse(text, today)
	if not found:
		return None
	return {"dates": found, "said": text}


def said(date):
	"""A date as it is said: Sunday, 14 March 2027."""
	year, month, day = date
	weekday = WEEKDAYS[datetime.date(year, month, day).weekday()].capitalize()
	return f"{weekday}, {day} {MONTHS[month - 1].capitalize()} {year}"


def monthSaid(shown):
	return f"{MONTHS[shown[1] - 1].capitalize()} {shown[0]}"


# --- What a calendar shows ---

_MONTH_YEAR = (
	re.compile(rf"^\W*({_MONTH}),? (\d{{4}})\W*$"),
	re.compile(rf"^\W*(\d{{4}}),? ({_MONTH})\W*$"),
	re.compile(rf"^\W*(\d{{1,2}})[/.-](\d{{4}})\W*$"),
	re.compile(rf"^\W*(\d{{4}})[/.-](\d{{1,2}})\W*$"),
)
_MONTH_ALONE = re.compile(rf"^\W*({_MONTH})\W*$")


def monthOf(label):
	"""The month and year a calendar's heading says, as (year, month); None when the text is no such heading.
	"March 2027", "Mar 2027", "2027 March", "03/2027", "2027-03"."""
	low = _clean(label).lower()
	if not low or len(low) > 24:
		return None
	for number, pattern in enumerate(_MONTH_YEAR):
		hit = pattern.match(low)
		if not hit:
			continue
		one, two = hit.group(1), hit.group(2)
		if number == 0:
			year, month = int(two), _MONTH_NUMBER[one.rstrip(".")]
		elif number == 1:
			year, month = int(one), _MONTH_NUMBER[two.rstrip(".")]
		elif number == 2:
			year, month = int(two), int(one)
		else:
			year, month = int(one), int(two)
		if 1 <= month <= 12 and FIRST_YEAR <= year <= LAST_YEAR:
			return year, month
	return None


def monthAlone(label):
	"""The month a text names when it names nothing else: for a calendar that has its month and its year in two
	places."""
	hit = _MONTH_ALONE.match(_clean(label).lower())
	return _MONTH_NUMBER[hit.group(1).rstrip(".")] if hit else None


def yearAlone(label):
	hit = re.match(r"^\W*(\d{4})\W*$", _clean(label))
	return int(hit.group(1)) if hit and FIRST_YEAR <= int(hit.group(1)) <= LAST_YEAR else None


def dayNumber(label):
	"""The day a cell of a calendar shows when its name is a number and nothing else: "14", "14.", "14th"."""
	hit = re.match(r"^\W*(\d{1,2})(?:st|nd|rd|th)?\W*$", _clean(label).lower())
	if not hit:
		return None
	day = int(hit.group(1))
	return day if 1 <= day <= 31 else None


def labelDate(label, shown=None):
	"""The whole date a cell's name says, as (year, month, day): "Sunday, March 14, 2027", "14 March 2027",
	"2027-03-14". A name with a month and a day and no year ("March 14", "Sunday 14 March") is read with the year
	the calendar shows. None for a bare number and for anything that is no date."""
	low = numbersFromWords(label)
	if not low or len(low) > 60 or dayNumber(low) is not None:
		return None
	hit = _ISO.search(low)
	if hit and valid(int(hit.group(1)), int(hit.group(2)), int(hit.group(3))):
		return int(hit.group(1)), int(hit.group(2)), int(hit.group(3))
	for order, pattern in _PATTERNS:
		hit = pattern.search(low)
		if not hit:
			continue
		if order == "dmy":
			day, month, year = int(hit.group(1)), _MONTH_NUMBER[hit.group(2).rstrip(".")], hit.group(3)
		else:
			month, day, year = _MONTH_NUMBER[hit.group(1).rstrip(".")], int(hit.group(2)), hit.group(3)
		if year is None and shown is not None:
			# December's days shown in a January calendar belong to the year before, and the other way round.
			year = shown[0] + (1 if shown[1] == 12 and month == 1 else -1 if shown[1] == 1 and month == 12 else 0)
		if year is not None and valid(int(year), month, day):
			return int(year), month, day
	return None


_NEXT = re.compile(
	r"^\W*(next|forward|following|later|go to next|show next|move to next)( month)?\W*$|\bnext month\b|\bmonth forward\b"
	r"|^\s*(>|›|»|→|▶|►|❯|⮞|▸)\s*$", re.IGNORECASE)
_PREVIOUS = re.compile(
	r"^\W*(prev|previous|back|backward|earlier|go to previous|show previous|move to previous)( month)?\W*$"
	r"|\b(previous|prev|last) month\b|\bmonth back\b"
	r"|^\s*(<|‹|«|←|◀|◄|❮|⮜|◂)\s*$", re.IGNORECASE)
_YEAR_BUTTON = re.compile(r"\byear\b", re.IGNORECASE)


def isNext(label):
	label = _clean(label)
	return bool(_NEXT.search(label)) and not _YEAR_BUTTON.search(label)


def isPrevious(label):
	label = _clean(label)
	return bool(_PREVIOUS.search(label)) and not _YEAR_BUTTON.search(label)


class Cell:
	"""One day of a calendar: its name, what presses it, whether it can be chosen, and whether it is marked."""

	def __init__(self, label, ref, usable=True, marked=False):
		self.label, self.ref, self.usable, self.marked = _clean(label), ref, usable, marked


class View:
	"""A calendar as it shows now. shown: (year, month), or None when its heading could not be read. next and
	previous: what presses the button for the next and the previous month, or None. arrows: buttons beside the
	heading whose names say nothing, in the order they stand; which is which is found by trying."""

	def __init__(self, shown, cells, next=None, previous=None, arrows=(), source=""):
		self.shown, self.cells, self.next, self.previous = shown, list(cells), next, previous
		self.arrows, self.source = list(arrows), source

	def isCalendar(self):
		"""Whether this is a calendar at all: a run of days, or days that say their whole date."""
		numbers = [dayNumber(cell.label) for cell in self.cells]
		plain = [number for number in numbers if number is not None]
		whole = sum(1 for cell in self.cells if labelDate(cell.label, self.shown) is not None)
		return whole >= 7 or (len(plain) >= 20 and _hasRun(plain))


def _hasRun(numbers):
	"""Whether numbers hold the days of a month in order: 1, 2, 3 ... up to at least 28."""
	try:
		at = numbers.index(1)
	except ValueError:
		return False
	run = 0
	for expected, number in enumerate(numbers[at:], 1):
		if number != expected:
			break
		run += 1
	return run >= 28


def dayCell(view, date):
	"""The cell of a calendar that is a day, or None. A cell that says its whole date wins. Among bare numbers,
	the days of the month shown are the run that begins at the first 1: the 29, 30 and 31 before it belong to
	the month before, and a second 1 begins the month after. Bare numbers count only when the calendar shows the
	date's month."""
	for cell in view.cells:
		if labelDate(cell.label, view.shown) == date:
			return cell
	if view.shown != (date[0], date[1]):
		return None
	numbered = [(dayNumber(cell.label), cell) for cell in view.cells]
	numbered = [(number, cell) for number, cell in numbered if number is not None]
	start = next((index for index, (number, _cell) in enumerate(numbered) if number == 1), None)
	if start is None:
		return None
	for expected, (number, cell) in enumerate(numbered[start:], 1):
		if number != expected:
			# A day that could not be read breaks the run; the day is then looked for after it, before the next 1.
			break
		if number == date[2]:
			return cell
	for number, cell in numbered[start + 1:]:
		if number == 1:
			break
		if number == date[2]:
			return cell
	return None


def monthsApart(shown, date):
	"""How many months after the month shown a date's month is; negative when it is before."""
	return (date[0] - shown[0]) * 12 + (date[1] - shown[1])


def fromControls(controls):
	"""A calendar from the controls of a web page or window, in reading order. controls: [{"label": its name or
	text, "ref": what presses it, "usable": False when it is greyed out, "marked": True when it is selected,
	"inside": the ref of the control it is inside, or None}]. A control inside another with the same name (a
	button in a cell) counts once, as the inner one."""
	labels = {id(control["ref"]): _clean(control["label"]) for control in controls}
	parents = set()
	for control in controls:
		inside = control.get("inside")
		if inside is not None and labels.get(id(inside)) == _clean(control["label"]):
			parents.add(id(inside))
	shown, month, year = None, None, None
	cells, nextRef, previousRef = [], None, None
	for control in controls:
		if id(control["ref"]) in parents:
			continue
		label = _clean(control["label"])
		if not label:
			continue
		if dayNumber(label) is not None or labelDate(label) is not None or (
				shown is not None and labelDate(label, shown) is not None):
			cells.append(Cell(label, control["ref"], control.get("usable", True), control.get("marked", False)))
			continue
		heading = monthOf(label)
		if heading is not None:
			# The first heading counts: a calendar that shows two months is worked by its first.
			shown = shown or heading
			continue
		if monthAlone(label) is not None and month is None:
			month = monthAlone(label)
			continue
		if yearAlone(label) is not None and year is None:
			year = yearAlone(label)
			continue
		if isNext(label):
			nextRef = nextRef if nextRef is not None else control["ref"]
		elif isPrevious(label):
			previousRef = previousRef if previousRef is not None else control["ref"]
	if shown is None and month is not None and year is not None:
		shown = (year, month)
	return View(shown, cells, nextRef, previousRef, source="controls")


def fromWords(lines, icons=()):
	"""A calendar from the text in a window's picture. lines: the lines the text recognition found, each a list
	of words {"text", "x", "y", "width", "height"} in the picture's pixels. icons: boxes (left, top, right, bottom)
	of small shapes that are no text, such as arrows. A ref is the middle of a word or shape, (x, y), in the
	picture's pixels. Returns None when the picture shows no calendar."""
	words = [word for line in lines or () for word in line if _clean(word.get("text"))]
	if not words:
		return None

	def middle(word):
		return (word["x"] + word["width"] / 2.0, word["y"] + word["height"] / 2.0)

	# The heading: a line, or two words next to each other, that says a month and a year.
	shown, heading = None, None
	for line in lines or ():
		line = [word for word in line if _clean(word.get("text"))]
		# The fewest words that say it: an arrow written as "<" next to the heading is no part of it.
		for count in (1, 2, 3):
			for start in range(len(line) - count + 1):
				piece = line[start:start + count]
				found = monthOf(" ".join(word["text"] for word in piece))
				if found is not None:
					shown, heading = found, piece
					break
			if shown:
				break
		if shown:
			break
	cells = []
	height = sorted(word["height"] for word in words)[len(words) // 2]
	# Days are below the heading, where there is one. They are put into rows, top to bottom, and each row is
	# read from left to right: the text recognition gives the columns in an order of its own.
	top = max(word["y"] + word["height"] for word in heading) if heading else None
	days = [
		word for word in words
		if dayNumber(word["text"]) is not None and not (top is not None and word["y"] < top - height * 0.3)]
	rows = []
	for word in sorted(days, key=lambda word: middle(word)[1]):
		if rows and abs(middle(word)[1] - rows[-1][0]) <= max(3.0, height * 0.6):
			rows[-1][1].append(word)
		else:
			rows.append((middle(word)[1], [word]))
	for _centre, row in rows:
		for word in sorted(row, key=lambda word: word["x"]):
			cells.append(Cell(word["text"], middle(word)))
	view = View(shown, cells, source="picture")
	if not view.isCalendar():
		return None
	if heading:
		left = min(word["x"] for word in heading)
		right = max(word["x"] + word["width"] for word in heading)
		centre = sum(middle(word)[1] for word in heading) / len(heading)
		band = max(height * 1.6, 12)
		beside = []
		for word in words:
			if word in heading or abs(middle(word)[1] - centre) > band:
				continue
			label = _clean(word["text"])
			if isNext(label):
				view.next = view.next or middle(word)
			elif isPrevious(label):
				view.previous = view.previous or middle(word)
		for box in icons or ():
			x, y = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
			if abs(y - centre) <= band and not (left <= x <= right):
				beside.append((x, y))
		# Shapes beside the heading, left to right. Which one goes forward is found by trying.
		view.arrows = sorted(beside)
	return view


# --- Getting to the date ---

NO_CALENDAR = (
	"No calendar was found here. Open the calendar first, so that its days are showing: on many date fields Alt+Down "
	"Arrow opens it, or the button next to the field does. Then ask again.")
NO_HEADING = (
	"A calendar is showing, but VisionClaw could not tell which month it shows, so it pressed nothing. If the calendar "
	"has boxes for the month and the year, set them first and ask again for the day.")


def choose(read, press, date, pause=None, check=None):
	"""Get a calendar to a date and press its day. read() gives the calendar as it shows now (a View) or None;
	press(ref) presses one of its buttons; pause() waits for the calendar to change; check() ends everything when
	the request is stopped. Returns (whether the day was pressed, the sentence that says what happened, how many
	times the month was changed). After every press the calendar is read again, and what it shows decides the
	next step: nothing is counted blind."""
	pause = pause or (lambda: None)
	check = check or (lambda: None)
	moved, stuck, swapped, guessed = 0, 0, False, False
	wanted = said(date)
	target = (date[0], date[1])
	view = read()
	while True:
		check()
		if view is None or not view.isCalendar():
			return False, (NO_CALENDAR if not moved else (
				f"After {moved} presses the calendar was no longer found, so {wanted} was not chosen.")), moved
		cell = dayCell(view, date)
		if cell is not None:
			if not cell.usable:
				return False, (
					f"The calendar shows {wanted}, but that day is greyed out there: it cannot be chosen. Nothing was pressed"
					+ (" for the day." if moved else ".")), moved
			press(cell.ref)
			return True, _doneText(wanted, view, moved, guessed), moved
		if view.shown is None:
			return False, NO_HEADING, moved
		apart = monthsApart(view.shown, date)
		if apart == 0:
			return False, (
				f"The calendar shows {monthSaid(view.shown)}, but day {date[2]} was not found in it, so nothing was pressed "
				"for the day."), moved
		if abs(apart) > MAX_MONTHS:
			return False, (
				f"The calendar shows {monthSaid(view.shown)}, and {wanted} is {abs(apart)} months away. VisionClaw goes at "
				f"most {MAX_MONTHS} months by pressing the button for the next or previous month. If the calendar has a "
				"box for the year, set that first and ask again."), moved
		forward = apart > 0
		ref = view.next if forward else view.previous
		byGuess = False
		if ref is None:
			if not view.arrows:
				return False, (
					f"The calendar shows {monthSaid(view.shown)}. VisionClaw found no button in it for the "
					f"{'next' if forward else 'previous'} month, so it could not get to {monthSaid(target)}."), moved
			# Which unnamed button goes forward is not known: the last one is tried for forward first.
			last = forward != swapped
			ref = view.arrows[-1] if last else view.arrows[0]
			byGuess = guessed = True
		before = view.shown
		press(ref)
		moved += 1
		pause()
		check()
		view = read()
		after = view.shown if view is not None else None
		if after is None or after == before:
			stuck += 1
			if stuck >= 2:
				return False, (
					f"The calendar still shows {monthSaid(before)} after its button was pressed twice, so VisionClaw stopped. "
					f"{wanted} was not chosen."), moved
			continue
		stuck = 0
		went = monthsApart(before, (after[0], after[1], 1))
		if (went > 0) != forward:
			if not byGuess:
				return False, (
					f"The calendar's button for the {'next' if forward else 'previous'} month went the other way, to "
					f"{monthSaid(after)}, so VisionClaw stopped. {wanted} was not chosen."), moved
			# The guess was the wrong way round: from now on the other button is used, and it also takes this back.
			swapped = not swapped


def _doneText(wanted, view, moved, guessed):
	text = f"Chose {wanted} in the calendar"
	if moved:
		text += f", after going {moved} month{'s' if moved != 1 else ''} to {monthSaid(view.shown)}" if view.shown else ""
	text += "."
	if view.source == "picture":
		text += (
			" The calendar was read from the window's picture, so check that the date field now says this date"
			+ (": which arrow goes forward was found by trying." if guessed else "."))
	return text


def ambiguous(dates):
	"""The question to the user when a date in numbers can be read two ways."""
	return "That date can be read two ways. Which do you mean?", [said(date) for date in dates]
