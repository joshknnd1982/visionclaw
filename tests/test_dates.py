# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Choosing a date in a calendar (claw/dates.py): which date the user's words mean, typed or spoken; what a
calendar shows, from the names of its controls and from the text in a picture; and the steps to the right month
and day, on calendars made up by the test that answer to presses as real ones do. Plain Python.

The tool itself is driven in tests/test_nvda_stub.py, on a calendar of controls and on one that is only drawn.

  python tests/test_dates.py
"""
import datetime

import harness  # noqa: F401
from calendarstandin import Drawn, Made
from visionClaw.claw import dates, planner, router

TODAY = datetime.date(2026, 11, 18)  # a Wednesday
MARCH_14 = (2027, 3, 14)

# --- Which date the words mean ---

SAID = {
	"Pick the fourteenth of March twenty twenty-seven in this calendar.": [MARCH_14],
	"choose 14 March 2027 in the date picker": [MARCH_14],
	"select March 14th, 2027 in the calendar": [MARCH_14],
	"choose 2027-03-14 in the calendar": [MARCH_14],
	"pick two thousand twenty seven march fourteen in the calendar": [MARCH_14],
	"Pick March the fourteenth in this calendar": [MARCH_14],  # no year: the next 14 March
	"pick march twenty one in this calendar": [(2027, 3, 21)],
	"pick the twenty first of december in the calendar": [(2026, 12, 21)],
	"pick march nineteen twenty twenty seven in the calendar": [(2027, 3, 19)],
	"choose 25/12/2026 in the calendar": [(2026, 12, 25)],
	"set the date to 3/4/2027": [(2027, 3, 4), (2027, 4, 3)],  # both readings: the user is asked
	"pick tomorrow in this date picker": [(2026, 11, 19)],
	"choose today in the calendar": [(2026, 11, 18)],
	"choose the day after tomorrow in the calendar": [(2026, 11, 20)],
	"pick friday in the calendar": [(2026, 11, 20)],
	"pick this friday in the calendar": [(2026, 11, 20)],
	"pick next friday in the calendar": [(2026, 11, 20), (2026, 11, 27)],  # two meanings: the user is asked
	"pick wednesday in the calendar": [(2026, 11, 25)],  # said on a Wednesday: the one a week from now
	"choose the 30th in the calendar": [(2026, 11, 30)],
	"choose the 5th in the calendar": [(2026, 12, 5)],  # the 5th of this month is over
	"in two weeks, in the calendar, pick": [(2026, 12, 2)],
	"choose a week from today in the calendar": [(2026, 11, 25)],
	"select the departure date January 5": [(2027, 1, 5)],
	"Set the check-in date to 29 Feb 2028": [(2028, 2, 29)],
	"pick Dec. 31, 2026 in the calendar": [(2026, 12, 31)],
	"select november 18 in the calendar": [(2026, 11, 18)],  # today counts as coming
}
for words, expected in SAID.items():
	found = dates.wish(words, TODAY)
	assert found is not None and found["dates"] == expected, (words, found)
# No calendar named, no date said, a date that does not exist, or only a question.
for words in (
		"what is the date", "say the date", "tell me the time and date", "how do I pick a date in this calendar on March 14",
		"set punctuation to all", "open the calendar", "pick a date in the calendar", "choose 30 February 2027 in the calendar",
		"click the March button", "set the speech rate to 14", "read the 14th line", "what day is March 14 2027",
		"remember that my birthday is March 14", "make a folder called March 2027", "go to the next heading",
		"pick 14 March 2027", "set the date format to day first", "which date is selected in the calendar"):
	assert dates.wish(words, TODAY) is None, (words, dates.wish(words, TODAY))
assert dates.said(MARCH_14) == "Sunday, 14 March 2027" and dates.monthSaid((2027, 3)) == "March 2027"
assert dates.parse("the fourteenth of March twenty twenty-seven", TODAY) == [MARCH_14]
assert dates.numbersFromWords("the thirty first of January nineteen ninety nine") == "the 31st of january 1999"
assert dates.numbersFromWords("two thousand and five") == "2005" and dates.numbersFromWords("twenty oh seven") == "2007"
assert dates.numbersFromWords("twenty one") == "twenty one"  # no year, and a day only next to a month
assert dates.numbersFromWords("give me one moment") == "give me one moment"

# --- What a calendar's heading, days and buttons say ---

for label, shown in {
		"March 2027": (2027, 3), "Mar 2027": (2027, 3), "MARCH, 2027": (2027, 3), "2027 March": (2027, 3), "03/2027": (2027, 3),
		"2027-03": (2027, 3), "Sept. 2026": (2026, 9), "March": None, "Monday": None, "14": None, "March 14, 2027": None,
		"Meeting in March 2027 with the whole team": None, "13/2027": None}.items():
	assert dates.monthOf(label) == shown, (label, dates.monthOf(label))
assert dates.monthAlone("March") == 3 and dates.monthAlone("March 2027") is None and dates.yearAlone("2027") == 2027
for label, day in {"14": 14, "14.": 14, "14th": 14, " 1 ": 1, "31": 31, "32": None, "0": None, "14 March": None, "": None, "Mo": None}.items():
	assert dates.dayNumber(label) == day, label
for label, date in {
		"Sunday, March 14, 2027": MARCH_14, "14 March 2027": MARCH_14, "Choose Sunday, March 14th, 2027": MARCH_14,
		"2027-03-14": MARCH_14, "Sunday 14 March": MARCH_14, "March 14": MARCH_14, "14": None, "March 2027": None,
		"Next month": None}.items():
	assert dates.labelDate(label, (2027, 3)) == date, (label, dates.labelDate(label, (2027, 3)))
# A day of December shown in a January calendar belongs to the year before.
assert dates.labelDate("December 31", (2027, 1)) == (2026, 12, 31) and dates.labelDate("January 1", (2026, 12)) == (2027, 1, 1)
for label in ("Next month", "Next", ">", "›", "»", "Go to next month", "Forward", "next"):
	assert dates.isNext(label) and not dates.isPrevious(label), label
for label in ("Previous month", "Prev", "<", "‹", "«", "Go to previous month", "Back", "previous"):
	assert dates.isPrevious(label) and not dates.isNext(label), label
for label in ("Next year", "Previous year", "Today", "Clear", "14", "March 2027", "Next page of results is here"):
	assert not dates.isNext(label) and not dates.isPrevious(label), label
assert dates.monthsApart((2026, 11), MARCH_14) == 4 and dates.monthsApart((2027, 5), MARCH_14) == -2
assert dates.monthsApart((2027, 3), MARCH_14) == 0

# --- Calendars made up by the test ---


def choose(made, date):
	return dates.choose(made.read, made.press, date)


# A calendar of named controls, four months before the date: four presses of Next month, then the day.
made = Made(2026, 11)
view = made.read()
assert view.isCalendar() and view.shown == (2026, 11) and view.next == ("next",) and view.previous == ("previous",)
# A button inside a cell of the same name counts once, as the button.
assert len(view.cells) == len(made._days()) and all(cell.ref[0] == "day" for cell in view.cells), view.cells[:3]
done, said, moved = choose(made, MARCH_14)
assert done and moved == 4 and made.chosen == MARCH_14, (said, made.pressed)
assert made.pressed == [("next",)] * 4 + [("day",) + MARCH_14]
assert said == "Chose Sunday, 14 March 2027 in the calendar, after going 4 months to March 2027.", said
# Backwards, and across a year.
made = Made(2027, 5)
done, said, moved = choose(made, (2026, 12, 31))
assert done and moved == 5 and made.chosen == (2026, 12, 31) and made.pressed[:5] == [("previous",)] * 5, made.pressed
# The month is showing already: the day is pressed and nothing else.
made = Made(2027, 3)
done, said, moved = choose(made, MARCH_14)
assert done and moved == 0 and made.pressed == [("day",) + MARCH_14] and said == "Chose Sunday, 14 March 2027 in the calendar."
# The 30th of November: the calendar also shows the 30th of the month before; the right one is taken. And the
# 1st: there are two, and the one of this month is the first.
made = Made(2026, 12)  # December 2026 begins on a Tuesday, so 30 November is shown before it
assert (2026, 11, 30) in made._days() and (2027, 1, 1) in made._days()
done, _said, _moved = choose(made, (2026, 12, 30))
assert done and made.chosen == (2026, 12, 30), made.chosen
made = Made(2026, 12)
done, _said, _moved = choose(made, (2026, 12, 1))
assert done and made.chosen == (2026, 12, 1)
# The 30th of November asked for while December is showing: the calendar is taken back a month first; the grey
# 30 at the top of December is not pressed.
made = Made(2026, 12)
done, said, moved = choose(made, (2026, 11, 30))
assert done and made.chosen == (2026, 11, 30) and made.pressed[0] == ("previous",) and moved == 1, made.pressed
# Days that say their whole date: the day is pressed wherever it shows, without counting months where it can.
made = Made(2026, 11, style="full")  # November 2026 ends on a Monday, so the first days of December show
done, said, moved = choose(made, (2026, 12, 3))
assert done and made.chosen == (2026, 12, 3) and moved == 0, (made.pressed, said)
made = Made(2026, 11, style="full", lead=False)
done, said, moved = choose(made, MARCH_14)
assert done and moved == 4 and made.chosen == MARCH_14
# A heading in another form, and the month and the year in two places.
for options in ({"heading": "{year} {month}"}, {"heading": "{month}, {year}"}, {"split": True}):
	made = Made(2026, 11, **options)
	assert made.read().shown == (2026, 11), options
	done, _said, moved = choose(made, MARCH_14)
	assert done and moved == 4 and made.chosen == MARCH_14, options
# A day that is greyed out is not pressed, and that is said.
made = Made(2027, 3, greyed=[MARCH_14])
done, said, moved = choose(made, MARCH_14)
assert not done and made.chosen is None and "greyed out" in said and made.pressed == [], said
# A calendar whose button does nothing: after two presses VisionClaw stops and says what it still shows.
made = Made(2026, 11, dead=True)
done, said, moved = choose(made, MARCH_14)
assert not done and made.pressed == [("next",)] * 2 and "still shows November 2026" in said, said
# A calendar whose named button goes the other way: stopped after one press.
made = Made(2026, 11, backwards=True)
done, said, moved = choose(made, MARCH_14)
assert not done and len(made.pressed) == 1 and "went the other way, to October 2026" in said, said
# Too far to press there.
made = Made(2026, 11)
done, said, moved = choose(made, (2040, 1, 1))
assert not done and made.pressed == [] and "158 months away" in said, said
# No buttons with names, and nothing beside the heading: said, and nothing is pressed.
made = Made(2026, 11, named=False)
done, said, moved = choose(made, MARCH_14)
assert not done and made.pressed == [] and "found no button in it for the next month" in said, said
# No heading that says the month: nothing is pressed.
made = Made(2026, 11, heading="Departure")
done, said, moved = choose(made, MARCH_14)
assert not done and said == dates.NO_HEADING and made.pressed == []
# No calendar at all.
assert dates.choose(lambda: None, lambda ref: 1 / 0, MARCH_14)[:2] == (False, dates.NO_CALENDAR)
other = dates.fromControls([{"label": str(number), "ref": number, "inside": None} for number in (1, 2, 3, 10, 20, 30)])
assert not other.isCalendar()
assert dates.choose(lambda: other, lambda ref: 1 / 0, MARCH_14)[:2] == (False, dates.NO_CALENDAR)
# A page of numbered results is no calendar either.
pages = dates.fromControls([{"label": str(number), "ref": number, "inside": None} for number in range(1, 26)])
assert not pages.isCalendar()
# The request is stopped: nothing more is pressed.


class Stopped(Exception):
	pass


def stop():
	raise Stopped()


made = Made(2026, 11)
try:
	dates.choose(made.read, made.press, MARCH_14, check=stop)
	raise AssertionError("a stopped request went on")
except Stopped:
	assert made.pressed == []

# --- A calendar that is only a picture ---


drawn = Drawn(2026, 11)
view = drawn.read()
assert view is not None and view.isCalendar() and view.shown == (2026, 11) and view.source == "picture"
assert view.next is None and view.previous is None and len(view.arrows) == 2, view.arrows
# The days are in reading order, though the text recognition gave them column by column.
assert [dates.dayNumber(cell.label) for cell in view.cells] == [day for _y, _m, day in drawn._days()]
# Which arrow goes forward is not known: the last one is tried, and it is the right one here.
done, said, moved = choose(drawn, MARCH_14)
assert done and drawn.chosen == MARCH_14 and moved == 4, (said, drawn.pressed)
assert said == (
	"Chose Sunday, 14 March 2027 in the calendar, after going 4 months to March 2027. The calendar was read from the "
	"window's picture, so check that the date field now says this date: which arrow goes forward was found by trying."), said
# Both arrows at the right, the usual way round; and a calendar whose arrows are the other way round: the first
# press goes the wrong way, that is seen, and the other arrow takes it back and on.
for options, presses in (({"arrows": "right"}, 4), ({"arrows": "left"}, 4), ({"flipped": True}, 6), ({"arrows": "right", "flipped": True}, 6)):
	drawn = Drawn(2026, 11, **options)
	done, said, moved = choose(drawn, MARCH_14)
	assert done and drawn.chosen == MARCH_14 and moved == presses, (options, moved, said)
# Backwards with arrows found by trying.
drawn = Drawn(2027, 3)
done, said, moved = choose(drawn, (2026, 12, 24))
assert done and drawn.chosen == (2026, 12, 24) and moved == 3, (moved, said)
# Arrows that are text: no trying is needed, and none is spoken of.
drawn = Drawn(2026, 11, glyphs=True)
view = drawn.read()
assert view.next is not None and view.previous is not None
done, said, moved = choose(drawn, MARCH_14)
assert done and moved == 4 and "found by trying" not in said and said.endswith("check that the date field now says this date."), said
# The month showing: one click on the day, at its place in the picture.
drawn = Drawn(2027, 3)
done, said, moved = choose(drawn, MARCH_14)
assert done and moved == 0 and len(drawn.pressed) == 1 and drawn.chosen == MARCH_14
# A picture with text and no calendar, and an empty one.
assert dates.fromWords([[{"text": "Hello", "x": 1, "y": 1, "width": 30, "height": 12}, {"text": "14", "x": 40, "y": 1, "width": 12, "height": 12}]]) is None
assert dates.fromWords([]) is None and dates.fromWords(None) is None

# --- Where the request is sent ---

for words in SAID:
	assert planner.hint(words) == "pick_date", (words, planner.hint(words))


class _Registry:
	def has(self, names):
		return True

	def get(self, name):
		return object()


for words in ("Pick the fourteenth of March twenty twenty-seven in this calendar.", "choose 14 March 2027 in the date picker"):
	assert planner.decided(words, _Registry()) == "pick_date"
	assert "pick_date" in planner.offered(words, _Registry(), {router.WEB: False})
# Requests that have a date or a calendar in them and are something else.
for words, recipe in {
		"what is the date": "do_command", "say the date": "do_command", "open the calendar": "open_thing",
		"click the next month button": "click", "remember that my birthday is March 14": "remember",
		"create a folder called March 2027 in my documents": "file_task"}.items():
	assert planner.hint(words) == recipe, (words, planner.hint(words))
	assert "pick_date" not in planner.offered(words, _Registry(), {}), words
assert planner.fitted("pick_date", "click the next month button", "click") == "click"

print("OK")
