# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Calendars made up for the tests, which answer to presses as real ones do: one made of controls with names,
as NVDA knows a web page's or a window's, and the same one as a picture, with words at their places and arrows
that are shapes without names. Used by tests/test_dates.py and tests/test_nvda_stub.py."""
import calendar
import datetime

import harness  # noqa: F401
from visionClaw.claw import dates


class Made:
	"""A calendar that shows one month and answers to presses. style: how its days are named ("number" for a bare
	number, "full" for the whole date); lead: whether the last days of the month before and the first days of
	the month after are shown too, as most calendars do; named: whether its buttons have names."""

	def __init__(self, year, month, style="number", lead=True, named=True, greyed=(), backwards=False, dead=False,
			heading="{month} {year}", closes=False, split=False):
		self.year, self.month, self.style, self.lead, self.named = year, month, style, lead, named
		self.greyed, self.backwards, self.dead, self.heading = set(greyed), backwards, dead, heading
		self.closes, self.split = closes, split
		self.chosen, self.pressed, self.open = None, [], True

	def _days(self):
		"""[(year, month, day)] of every cell, in reading order."""
		first = datetime.date(self.year, self.month, 1)
		count = calendar.monthrange(self.year, self.month)[1]
		cells = []
		if self.lead:
			before = first.weekday()  # the week begins on Monday
			for back in range(before, 0, -1):
				day = first - datetime.timedelta(days=back)
				cells.append((day.year, day.month, day.day))
		cells += [(self.year, self.month, day) for day in range(1, count + 1)]
		if self.lead:
			after = datetime.date(self.year, self.month, count)
			while len(cells) % 7:
				after += datetime.timedelta(days=1)
				cells.append((after.year, after.month, after.day))
		return cells

	def _label(self, date):
		if self.style == "full":
			return dates.said(date)
		return str(date[2])

	def step(self, by):
		if self.dead:
			return
		month = self.month - 1 + (-by if self.backwards else by)
		self.year, self.month = self.year + month // 12, month % 12 + 1

	def controls(self):
		"""The calendar as the controls of a page: a heading, two buttons, and a table of days, each day a cell
		with a button of the same name inside it."""
		if not self.open:
			return [{"label": "Departure date", "ref": ("field",), "inside": None}]
		name = dates.MONTHS[self.month - 1].capitalize()
		found = [{"label": "Book a flight", "ref": ("title",), "inside": None}]
		if self.split:
			found += [{"label": name, "ref": ("month",), "inside": None}, {"label": str(self.year), "ref": ("year",), "inside": None}]
		else:
			found.append({"label": self.heading.format(month=name, year=self.year), "ref": ("heading",), "inside": None})
		found += [
			{"label": "Previous month" if self.named else "", "ref": ("previous",), "inside": None},
			{"label": "Next month" if self.named else "", "ref": ("next",), "inside": None}]
		found += [{"label": day, "ref": ("weekday", day), "inside": None} for day in ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")]
		for date in self._days():
			cell = ("cell",) + date
			label = self._label(date)
			found.append({"label": label, "ref": cell, "inside": None})
			found.append({
				"label": label, "ref": ("day",) + date, "inside": cell, "usable": date not in self.greyed,
				"marked": date == self.chosen})
		found.append({"label": "Results 1 to 10 of 31", "ref": ("other",), "inside": None})
		return found

	def press(self, ref):
		self.pressed.append(ref)
		if ref[0] == "next":
			self.step(1)
		elif ref[0] == "previous":
			self.step(-1)
		elif ref[0] == "day":
			self.chosen = ref[1:]
			if ref[1:3] != (self.year, self.month) and not self.dead:
				self.year, self.month = ref[1], ref[2]  # a day of another month takes the calendar there
			if self.closes:
				self.open = False

	def read(self):
		# Controls are found anew at every reading; the same control keeps its ref.
		return dates.fromControls(self.controls())


class Drawn(Made):
	"""The same calendar as a picture: words with their places, and two arrows that are shapes without names.
	arrows: where the arrows are; "split" has one on each side of the heading, "right" has both at the right, the
	first of them going back; "left" has both at the left."""

	CELL, TOP, LEFT = 40, 60, 20

	def __init__(self, *args, arrows="split", flipped=False, glyphs=False, **kwargs):
		super().__init__(*args, **kwargs)
		self.arrows, self.flipped, self.glyphs = arrows, flipped, glyphs

	def _arrowPlaces(self):
		"""(the place of the arrow that goes back, the place of the arrow that goes forward)."""
		y = 30
		if self.arrows == "split":
			places = ((self.LEFT + 10, y), (self.LEFT + 7 * self.CELL - 10, y))
		elif self.arrows == "right":
			places = ((self.LEFT + 6 * self.CELL - 20, y), (self.LEFT + 7 * self.CELL - 10, y))
		else:
			places = ((self.LEFT + 10, y), (self.LEFT + 40, y))
		return (places[1], places[0]) if self.flipped else places

	def picture(self):
		"""(the lines of text, the shapes that are no text)."""
		name = dates.MONTHS[self.month - 1].capitalize()
		lines = [[
			{"text": name, "x": 110, "y": 22, "width": 50, "height": 14},
			{"text": str(self.year), "x": 166, "y": 22, "width": 34, "height": 14}]]
		lines.append([
			{"text": day, "x": self.LEFT + column * self.CELL + 10, "y": 44, "width": 18, "height": 12}
			for column, day in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"))])
		days = self._days()
		# The text recognition gives the columns in an order of its own: here, each column from top to bottom.
		for column in range(7):
			line = []
			for index in range(column, len(days), 7):
				row = index // 7
				line.append({
					"text": str(days[index][2]), "x": self.LEFT + column * self.CELL + 12, "y": self.TOP + row * 30 + (column % 2),
					"width": 16, "height": 12})
			lines.append(line)
		lines.append([{"text": "Cancel", "x": 30, "y": 260, "width": 44, "height": 14}, {"text": "OK", "x": 200, "y": 260, "width": 20, "height": 14}])
		back, forward = self._arrowPlaces()
		icons = [] if self.glyphs else [(x - 8, y - 8, x + 8, y + 8) for x, y in sorted((back, forward))]
		icons.append((250, 255, 266, 271))  # a shape that is not beside the heading
		if self.glyphs:
			lines[0] = [{"text": "<", "x": back[0] - 4, "y": 22, "width": 8, "height": 14}] + lines[0] + [
				{"text": ">", "x": forward[0] - 4, "y": 22, "width": 8, "height": 14}]
		return lines, icons

	def read(self):
		return dates.fromWords(*self.picture())

	def press(self, ref):
		self.pressed.append(ref)
		x, y = ref
		back, forward = self._arrowPlaces()
		if abs(x - back[0]) <= 8 and abs(y - back[1]) <= 8:
			self.step(-1)
		elif abs(x - forward[0]) <= 8 and abs(y - forward[1]) <= 8:
			self.step(1)
		elif y >= self.TOP:
			column, row = int((x - self.LEFT) // self.CELL), int((y - self.TOP) // 30)
			days = self._days()
			if 0 <= row * 7 + column < len(days):
				self.chosen = days[row * 7 + column]
