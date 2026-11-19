# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""What tests/test_shopping.py works on: pictures drawn by the test (a row of colour swatches with no names, a seat
map with a legend) with the words a reading of them would give, and controls made up by the test with the names
web pages give their options and seats. Nothing here is a real shop or a real airline; what plain code finds here
says nothing about how well it does on a real website, and the test that uses this file says so.
"""
import drawn

# The colours a seat is drawn in: free, taken, chosen.
FREE, TAKEN, CHOSEN = (120, 190, 120), (165, 165, 165), (60, 110, 220)
NAVY, BLACK, RED, CREAM, GREEN = (22, 28, 62), (12, 12, 12), (200, 30, 40), (245, 238, 215), (30, 140, 60)


def swatches(shades, side=30, gap=12, left=40, top=70, ring=None):
	"""A product's colours as a row of plain blocks with no names, under the word Colour, with a line of text
	about the product above and a large Add to cart button below. ring: the number of the swatch that has a ring
	around it, as a chosen one has. Returns (the page, the boxes of the swatches from left to right)."""
	page = drawn.Page(520, 260)
	page.text(40, 16, "Rain jacket, light and warm")
	page.text(left, top - 26, "Colour")
	boxes = []
	for index, shade in enumerate(shades):
		x = left + index * (side + gap)
		boxes.append(page.block((x, top, x + side, top + side), shade))
		if ring == index:
			page.draw.rectangle((x - 4, top - 4, x + side + 4, top + side + 4), outline=drawn.INK, width=2)
	page.block((40, 170, 220, 210), (30, 90, 200))
	page.text(70, 182, "Add to cart", fill=drawn.WHITE)
	return page, boxes


def optionControls():
	"""The options of a product as a web page gives them to NVDA: sizes as radio buttons in a group called Size,
	one of them sold out; storage as toggle buttons; colours as buttons, two with a shop's own names and two with
	no name at all; and other controls of the page that are no options."""
	def control(label, role, states=(), group="", ref=None):
		return {"label": label, "role": role, "states": list(states), "group": group, "colour": None, "ref": ref or f"ref:{group}:{label}"}
	return [
		control("Search", "EDITABLETEXT"), control("Medium articles", "LINK", group="Blog"),
		control("Small", "RADIOBUTTON", ("CHECKED",), "Size"), control("Medium", "RADIOBUTTON", (), "Size"),
		control("Medium Tall", "RADIOBUTTON", (), "Size"), control("Large", "RADIOBUTTON", ("UNAVAILABLE",), "Size"),
		control("XL - sold out", "RADIOBUTTON", (), "Size"),
		control("128GB", "TOGGLEBUTTON", ("PRESSED",), "Storage"), control("256 GB", "TOGGLEBUTTON", (), "Storage"),
		control("512GB", "TOGGLEBUTTON", (), "Storage"),
		control("Midnight", "BUTTON", (), "Colour"), control("Sahara", "BUTTON", (), "Colour"),
		control("", "BUTTON", (), "Colour", ref="ref:swatch:0"), control("", "BUTTON", (), "Colour", ref="ref:swatch:1"),
		control("Add to cart", "BUTTON"), control("Quantity", "COMBOBOX"),
	]


def seatControls(style, rows, letters, taken=(), chosen=(), prices=None, wing=(), exits=(), aisleAfter=None):
	"""The seats of a map as a web page names them, in reading order, in one of several airlines' ways:
	"bare" is "12A", greyed out when taken; "seat" is "Seat 12A available" or "Seat 12A occupied"; "full" is "12A,
	window, available, $15", with exit row and over wing where they are; "rowseat" is "Row 12 Seat A, Available".
	aisleAfter: a letter after which the page has a control that only says "aisle"."""
	prices = prices or {}
	found = []
	for row in rows:
		for letter in letters:
			ident = f"{row}{letter}"
			isTaken, isChosen = ident in taken, ident in chosen
			usable, marked = True, False
			if style == "bare":
				label, usable, marked = ident, not isTaken, isChosen
			elif style == "seat":
				label = f"Seat {ident} " + ("selected" if isChosen else "occupied" if isTaken else "available")
			elif style == "rowseat":
				label = f"Row {row} Seat {letter}, " + ("Your seat" if isChosen else "Unavailable" if isTaken else "Available")
			else:
				kind = "window" if letter in (letters[0], letters[-1]) else "aisle" if letter in "CD" else "middle"
				parts = [ident, kind, "selected" if isChosen else "not available" if isTaken else "available"]
				if row in exits:
					parts.append("exit row")
				if row in wing:
					parts.append("over wing")
				if ident in prices:
					parts.append(prices[ident])
				label = ", ".join(parts)
			found.append({"label": label, "ref": f"ref:{ident}", "usable": usable, "marked": marked})
			if aisleAfter == letter:
				found.append({"label": "aisle", "ref": f"ref:aisle:{row}", "usable": False, "marked": False})
	return found


def seatPicture(rows, letters, aisleAfter="C", taken=(), chosen=(), ids=True, legend=True, wing=None, sideways=False):
	"""A seat map that is only drawn: every seat a small block in the colour of free, taken or chosen, with its
	number written in it (ids) or with the column letters and row numbers around the grid; a wider gap for the
	aisle; under it a legend of three small blocks with the words Available, Occupied and Selected. wing: a row
	beside which the word Wing is written. sideways: the rows run from left to right, as on a map that shows the
	aircraft lying on its side. Returns (the page, the middle of every seat by its number)."""
	page = drawn.Page(760, 560, size=11)
	side, pitch, aisle = 34, 44, 30
	left, top = 90, 60
	places = {}

	def across(index):
		gap = aisle if aisleAfter and letters.index(aisleAfter) < index else 0
		return index * pitch + gap

	for rowIndex, row in enumerate(rows):
		for letterIndex, letter in enumerate(letters):
			ident = f"{row}{letter}"
			x = left + (rowIndex * pitch if sideways else across(letterIndex))
			y = top + (across(letterIndex) if sideways else rowIndex * pitch)
			shade = CHOSEN if ident in chosen else TAKEN if ident in taken else FREE
			page.block((x, y, x + side, y + side), shade)
			places[ident] = (x + side // 2, y + side // 2)
			if ids:
				page.text(x + 5, y + 17, ident)
	if not ids:
		for letterIndex, letter in enumerate(letters):
			if sideways:
				page.text(left - 30, top + across(letterIndex) + 10, letter)
			else:
				page.text(left + across(letterIndex) + 12, top - 24, letter)
		for rowIndex, row in enumerate(rows):
			if sideways:
				page.text(left + rowIndex * pitch + 10, top - 24, str(row))
			else:
				page.text(left - 34, top + rowIndex * pitch + 10, str(row))
	if wing is not None:
		rowIndex = list(rows).index(wing)
		if sideways:
			page.text(left + rowIndex * pitch, top + across(len(letters) - 1) + side + 14, "Wing")
		else:
			page.text(left + across(len(letters) - 1) + side + 24, top + rowIndex * pitch + 10, "Wing")
	if legend:
		y = 510
		for index, (shade, word) in enumerate(((FREE, "Available"), (TAKEN, "Occupied"), (CHOSEN, "Selected"))):
			x = 90 + index * 170
			page.block((x, y, x + 14, y + 14), shade)
			page.text(x + 22, y + 1, word)
	return page, places
