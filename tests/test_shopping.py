# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Shopping and booking (claw/shopping.py, claw/seats.py, shoptools.py): which buttons buy and what the page says
is to be paid; what is never typed; the options of a product chosen by name or by measured colour, and whether one
is chosen; a seat map read from the names of its seats or from its picture, and the seats that fit what was asked.
Plain Python: no NVDA, no model, no browser.

Everything here is tried on pictures drawn by the test and on controls made up by the test (tests/shopdrawn.py),
named the way web pages name such things. None of it has run on a real shop's or airline's website, and what
passes here says nothing about how a real page behaves. The tools are driven through stand-ins for NVDA; the real
mouse is never moved, nothing is clicked, and nothing is bought.

  python tests/test_shopping.py
"""
import builtins
import os
import sys
import types

import harness  # noqa: F401
import shopdrawn
from visionClaw.claw import colours, seats, shopping
from visionClaw.claw import task as taskModule

# --- A purchase is always asked about ---

for name in (
		"Place your order", "Place Order", "Buy now", "Buy", "Buy with PayPal", "Pay now", "Pay $45.99", "Complete purchase",
		"Confirm booking", "Confirm and pay", "Reserve", "Reserve a table", "Book now", "Book", "Book this room", "Order now",
		"Submit order", "Review and place order", "Send payment", "Start free trial", "Purchase", "Donate", "Place bid",
		"Complete your booking", "Pay with card", "Buy now button", "PLACE ORDER", "Finalize order"):
	assert shopping.isPurchase(name), name
# "Checkout" only leads on to where the address and the payment are given; nothing is bought by it.
for name in (
		"Checkout", "Proceed to checkout", "Continue to payment", "Review order", "Add to cart", "Add to bag", "Add to basket",
		"Order history", "Order details", "Payment methods", "PayPal Checkout", "Bookmark", "Book details", "Booking details",
		"Subscribe", "Confirm", "Next", "Continue", "Cancel order", "Purchase history", "Reservations", "Pay later options",
		"Order", "View cart", "Apply", "Apply promo code", "Buy again", "Guest book", "Track order", "", None):
	assert not shopping.isPurchase(name), name

PAGE_TEXT = """Your basket
Blue jacket, Medium
Subtotal $40.00
Shipping $5.99
Total savings $5.00
Order total: $45.99
You have 3 items
How would you like to pay?
"""
# Word for word, the surest first; a subtotal, the savings and a count are not what is paid.
assert shopping.totals(PAGE_TEXT) == ["Order total: $45.99"], shopping.totals(PAGE_TEXT)
assert shopping.totals(PAGE_TEXT.splitlines()) == ["Order total: $45.99"]
# The word and the amount on two lines, as pages often lay them out, are given as one.
assert shopping.totals("Basket\nTotal\n$12.50\nThank you") == ["Total $12.50"]
found = shopping.totals(["Amount due today 45,99 €", "Total items 3", "Grand total EUR 45.99", "Total 45.99 EUR", "Estimated total $1,234.56"])
assert found == ["Amount due today 45,99 €", "Grand total EUR 45.99", "Estimated total $1,234.56"], found
assert len(shopping.totals(["Total: $1", "Order total: $2", "Grand total: $3", "Amount due: $4", "Total due: $5"])) == shopping.MAX_TOTALS
assert shopping.totals("Nothing here about money") == [] and shopping.totals("") == [] and shopping.totals(None) == []
assert shopping.totals("You saved a total of $5 today") == []
asked = shopping.purchaseQuestion("Place your order", shopping.totals(PAGE_TEXT))
assert asked == (
	"\"Place your order\" buys, books or pays. The page says: Order total: $45.99. Press it? This may not be possible "
	"to take back."), asked
asked = shopping.purchaseQuestion("Buy now", [])
assert "VisionClaw found no total on the page" in asked and asked.endswith("This may not be possible to take back."), asked
assert shopping.notPressed("Buy now") == "\"Buy now\" was not pressed, so nothing was bought, booked or paid."

# --- What VisionClaw never types ---

for name in (
		"Card number", "Credit card number", "Credit card", "Debit card", "Security code", "CVV", "CVC", "Expiration date",
		"Expiry (MM/YY)", "Valid thru", "Password", "Confirm password", "Passcode", "PIN", "Card PIN code",
		"Social Security Number", "SSN", "Account number", "Bank account number", "Routing number", "IBAN", "Sort code"):
	assert shopping.isSecret(name), name
# A promo code is no secret, and neither is the name on the card; "PIN code" alone is a postal code in India.
for name in (
		"Name on card", "Cardholder name", "PIN code", "Postcode", "Email", "Promo code", "Coupon code", "Discount code",
		"First name", "Phone", "Search", "Address", "City", "Quantity", "", None):
	assert not shopping.isSecret(name), name
assert "type it yourself" in shopping.SECRET_REFUSAL and "log" in shopping.SECRET_REFUSAL and "focus" in shopping.SECRET_REFUSAL

# --- What the user's words ask about an option ---

WISHES = {
	# The article's own sentences.
	"Click the Medium size swatch": (shopping.CHOOSE, "Medium", None, "size"),
	"select the dark blue color option": (shopping.CHOOSE, "dark blue", "dark blue", "colour"),
	"confirm the storage capacity is set to 256GB": (shopping.CHECK, "256GB", None, "storage"),
	"is the large size selected": (shopping.CHECK, "large", None, "size"),
	"choose the navy one": (shopping.CHOOSE, "navy", "dark blue", None),
	"pick the 512 GB storage option": (shopping.CHOOSE, "512 GB", None, "storage"),
	"select size 10": (shopping.CHOOSE, "10", None, "size"),
	"choose size XL": (shopping.CHOOSE, "XL", None, "size"),
	"which colour is selected": (shopping.CHECK, None, None, "colour"),
	"what size is chosen": (shopping.CHECK, None, None, "size"),
	"select the Midnight colour": (shopping.CHOOSE, "Midnight", None, "colour"),
	"click the red swatch": (shopping.CHOOSE, "red", "red", None),
	# Two colours in one name are a name, not a colour to measure.
	"select the Rose Gold option": (shopping.CHOOSE, "Rose Gold", None, None),
	"choose \"Space Grey\" as the colour": (shopping.CHOOSE, "Space Grey", "grey", "colour"),
	"go with the large size": (shopping.CHOOSE, "large", None, "size"),
}
for said, (what, name, colour, group) in WISHES.items():
	wish = shopping.optionWish(said)
	assert wish == {"what": what, "name": name, "colour": colour, "group": group}, (said, wish)
# No option of a product: another thing to click, how something is done, the size of a font, a question about a photo.
for said in (
		"Click the Next button", "select all", "change the font size to 12", "how do I choose a size", "is the checkbox selected",
		"Look at the product photo, is this jacket navy blue or solid black", "make the text size larger", "check the memory",
		"what colour is this", "set the window size", "", None):
	assert shopping.optionWish(said) is None, said

# --- Which option is meant ---

CONTROLS = shopdrawn.optionControls()
labels = lambda options: [option["label"] for option in options]

# By name: the same words win over a longer label, and a link that only has the word in it is no size.
wish = shopping.optionWish("Click the Medium size swatch")
options = shopping.asOptions(CONTROLS, wish)
assert labels(options) == ["Medium", "Medium Tall"], labels(options)
index, how = shopping.pickOption(wish, options)
assert options[index]["label"] == "Medium" and how == shopping.BY_NAME
assert options[index]["chosen"] is False and options[index]["usable"] and options[index]["group"] == "Size"
assert shopping.chooseQuestion(options[index]) == "Choose the option \"Medium\"?"
# Where the words say more, the longer one is meant.
wish = shopping.optionWish("choose the Medium Tall size")
options = shopping.asOptions(CONTROLS, wish)
assert labels(options) == ["Medium Tall"] and shopping.pickOption(wish, options) == (0, shopping.BY_NAME)
# Only longer labels: the user is asked which.
wish = shopping.optionWish("choose the Medium size")
only = [control for control in CONTROLS if control["label"] != "Medium"]
options = shopping.asOptions(only + [dict(CONTROLS[3], label="Medium Petite", ref="ref:petite")], wish)
assert shopping.pickOption(wish, options) == (None, [0, 1]), labels(options)
assert shopping.choices(options, [0, 1]) == ["The option \"Medium Tall\"", "The option \"Medium Petite\""]
assert shopping.whichQuestion(wish) == "More than one option fits \"Medium\". Which one do you mean?"
# A size said as a word finds its letter, and the other way round; "256GB" finds "256 GB".
for said, label in (("choose the extra large size", "XL - sold out"), ("choose size S", "Small"), ("pick the 256GB storage option", "256 GB"),
		("pick the 512 gb storage option", "512GB"), ("choose size L", "Large")):
	wish = shopping.optionWish(said)
	options = shopping.asOptions(CONTROLS, wish)
	index, how = shopping.pickOption(wish, options)
	assert index is not None and options[index]["label"] == label, (said, labels(options))
# Greyed out or said to be sold out: found, and not pressed.
for said in ("choose size L", "choose size XL"):
	wish = shopping.optionWish(said)
	options = shopping.asOptions(CONTROLS, wish)
	option = options[shopping.pickOption(wish, options)[0]]
	assert option["usable"] is False and shopping.unusableText(option).startswith("Nothing was pressed: the option"), option
# Nothing of that name.
wish = shopping.optionWish("choose the Purple Haze colour")
assert shopping.asOptions(CONTROLS, wish) == [] and shopping.pickOption(wish, []) == (None, [])
assert shopping.noFit(wish, []).startswith("Nothing was pressed: no option called \"Purple Haze\" was found")
assert shopping.noFit(wish, [], pressing=False).startswith("No option called \"Purple Haze\" was found")

# By colour. The swatches with no names are measured from a picture drawn here; the shop's own names say no colour.
page, boxes = shopdrawn.swatches([shopdrawn.NAVY, shopdrawn.BLACK, shopdrawn.RED, shopdrawn.CREAM, shopdrawn.GREEN], ring=1)
measured = [colours.name(colours.middle(page.image, box)) for box in boxes]
assert measured == ["dark blue", "black", "red", "cream", "green"], measured
withColour = [dict(control) for control in CONTROLS]
for control, colour in zip([c for c in withColour if c["group"] == "Colour"], ("dark blue", "beige", "red", "black")):
	assert shopping.needsColour(control)
	control["colour"] = colour
wish = shopping.optionWish("select the dark blue color option")
options = shopping.asOptions(withColour, wish)
assert labels(options) == ["Midnight", "Sahara", "", ""], labels(options)
index, how = shopping.pickOption(wish, options)
assert options[index]["label"] == "Midnight" and how == shopping.BY_MEASURED and options[index]["measured"]
assert shopping.optionSaid(options[index]) == "the option \"Midnight\", measured dark blue"
assert shopping.chooseQuestion(options[index]) == "Choose the option \"Midnight\", measured dark blue?"
wish = shopping.optionWish("click the red swatch")
options = shopping.asOptions(withColour, wish)
index, how = shopping.pickOption(wish, options)
assert options[index]["label"] == "" and options[index]["colour"] == "red" and how == shopping.BY_MEASURED
assert shopping.optionSaid(options[index], index + 1) == "an option with no name, number 3 of those found, measured red"
# "Navy" asked, and a swatch that is nearly black: navy is the dark blue one, not the black one.
wish = shopping.optionWish("choose the navy one")
options = shopping.asOptions(withColour, wish)
assert options[shopping.pickOption(wish, options)[0]]["label"] == "Midnight"
# A colour the option's own name says needs no measuring, and is not said to be measured.
named = [{"label": label, "role": "RADIOBUTTON", "states": [], "group": "Colour", "colour": None, "ref": label} for label in ("Navy", "Black", "Forest Green")]
wish = shopping.optionWish("select the dark blue color option")
options = shopping.asOptions(named, wish)
index, how = shopping.pickOption(wish, options)
assert options[index]["label"] == "Navy" and how == shopping.BY_LABEL_COLOUR and not options[index]["measured"], options
assert "measured" not in shopping.optionSaid(options[index])
wish = shopping.optionWish("choose the navy one")
options = shopping.asOptions(named, wish)
assert shopping.pickOption(wish, options) == (0, shopping.BY_NAME)
# "Blue" alone, with a dark and a light blue there: the user is asked, each with its measured colour.
two = [{"label": "", "role": "BUTTON", "states": [], "group": "Colour", "colour": colour, "ref": colour} for colour in ("dark blue", "light blue", "red")]
wish = shopping.optionWish("choose the blue one")
options = shopping.asOptions(two, wish)
assert shopping.pickOption(wish, options) == (None, [0, 1])
assert shopping.choices(options, [0, 1]) == [
	"An option with no name, number 1 of those found, measured dark blue", "An option with no name, number 2 of those found, measured light blue"]
# A link that merely has the word red in it is not the red one.
wish = shopping.optionWish("click the red swatch")
options = shopping.asOptions(two + [{"label": "Red hot deals", "role": "LINK", "states": [], "group": "", "colour": None, "ref": "deals"}], wish)
assert options[shopping.pickOption(wish, options)[0]]["colour"] == "red" and shopping.pickOption(wish, options)[1] == shopping.BY_MEASURED
# No colour that fits: nothing is chosen, and what was found is said with its measured colours.
wish = shopping.optionWish("choose the purple one")
options = shopping.asOptions(two, wish)
assert shopping.pickOption(wish, options) == (None, [])
said = shopping.noFit(wish, options)
assert said.startswith("Nothing was pressed: none of the options found is \"purple\". Found: An option with no name, number 1") and said.endswith(shopping.MEASURED_NOTE), said
# Where there are more controls than can be measured, those with no name and those in a colour group come first.
order = sorted(CONTROLS, key=shopping.measureFirst)
assert [control["label"] for control in order[:2]] == ["", ""] and {control["label"] for control in order[2:4]} == {"Midnight", "Sahara"}

# Whether an option is chosen is said only from what the page says.
assert shopping.chosenOf("RADIOBUTTON", ["CHECKED"]) is True and shopping.chosenOf("RADIOBUTTON", []) is False
assert shopping.chosenOf("TOGGLEBUTTON", ["PRESSED"]) is True and shopping.chosenOf("TOGGLEBUTTON", []) is False
assert shopping.chosenOf("BUTTON", []) is None and shopping.chosenOf("LINK", []) is None and shopping.chosenOf("GRAPHIC", []) is None
assert shopping.chosenOf("LISTITEM", ["SELECTABLE"]) is False and shopping.chosenOf("LISTITEM", ["SELECTABLE", "SELECTED"]) is True
assert shopping.chosenOf("BUTTON", [], "Midnight, selected") is True
wish = shopping.optionWish("confirm the storage capacity is set to 256GB")
options = shopping.asOptions(CONTROLS, wish)
# The other options of the same group come along, so that the one that is chosen can be said.
assert labels(options) == ["256 GB", "128GB", "512GB"], labels(options)
said = shopping.checkText(wish, options)
assert said == "No. The page does not mark the option \"256 GB\" as chosen. Marked as chosen now: 128GB.", said
wish = shopping.optionWish("is the small size selected")
assert shopping.checkText(wish, shopping.asOptions(CONTROLS, wish)) == "Yes. The page marks the option \"Small\" as chosen."
wish = shopping.optionWish("what size is chosen")
said = shopping.checkText(wish, shopping.asOptions(CONTROLS, wish))
assert said == "The page marks these as chosen: The option \"Small\".", said
# A plain button has no state: the answer says that the page does not say, and names no guess.
wish = shopping.optionWish("is the Midnight colour selected")
said = shopping.checkText(wish, shopping.asOptions(CONTROLS, wish))
assert said.startswith("The page does not say whether the option \"Midnight\" is chosen: it gives NVDA no state for it."), said
assert "a model can be wrong" in said
wish = shopping.optionWish("which colour is selected")
said = shopping.checkText(wish, shopping.asOptions(CONTROLS, wish))
assert said.startswith("The page marks none of these as chosen: The option \"Midnight\"; The option \"Sahara\"; An option with no name"), said
assert shopping.checkText(wish, []) == shopping.NO_OPTIONS
wish = shopping.optionWish("is the Purple Haze colour selected")
assert shopping.checkText(wish, []).startswith("No option called \"Purple Haze\" was found"), shopping.checkText(wish, [])
# After a press: chosen only when the page says so.
option = {"label": "Medium", "colour": None, "measured": False, "chosen": False, "usable": True}
assert shopping.doneText(option, True) == "Pressed the option \"Medium\". The page now marks it as chosen."
assert "does not mark it as chosen, so the press may not have been taken" in shopping.doneText(option, False)
assert "its picture changed after the press" in shopping.doneText(option, None, True)
assert "nothing VisionClaw can see changed" in shopping.doneText(option, None, False)
assert shopping.doneText(option, None).endswith("so VisionClaw cannot tell you that it is.")
swatch = {"label": "", "colour": "red", "measured": True, "chosen": None, "usable": True}
assert shopping.doneText(swatch, None, True, 3).startswith("Pressed an option with no name, number 3 of those found, measured red.")
assert shopping.doneText(swatch, None, True, 3).endswith(shopping.MEASURED_NOTE)
# A size chosen in a combo box: said, with what it shows, and how the user chooses there.
combo = [{"label": "Size", "role": "COMBOBOX", "states": [], "group": "", "colour": None, "value": "Medium", "ref": "combo"}]
wish = shopping.optionWish("choose the Large size")
said = shopping.comboText(wish, combo)
assert said.startswith("On this page that is chosen in the combo box \"Size\", which shows Medium now.") and "Up Arrow and Down Arrow" in said, said
assert shopping.comboText(shopping.optionWish("click the red swatch"), combo) == ""
assert shopping.namedExactly(shopping.optionWish("Click the Medium size swatch"), shopping.asOptions(CONTROLS, shopping.optionWish("Click the Medium size swatch")))
assert not shopping.namedExactly(wish, [{"label": "Large print books"}])

# Swatches that are only drawn: blocks of one colour in a row. The words, the big button and the ring are none.
blocks = shopping.blocks(page.image)
assert len(blocks) == 5, blocks
for found, drawn in zip(blocks, boxes):
	assert all(abs(a - b) <= 4 for a, b in zip(found, drawn)), (found, drawn)
assert shopping.swatchRows(blocks) == [[0, 1, 2, 3, 4]]
assert [colours.name(colours.middle(page.image, box)) for box in blocks] == ["dark blue", "black", "red", "cream", "green"]
# On a screen that draws everything larger, they are found as well.
large = page.image.resize((page.image.size[0] * 2, page.image.size[1] * 2))
assert len(shopping.blocks(large, 2.0)) == 5 and shopping.blocks(large, 1.0) == [b for b in shopping.blocks(large, 1.0) if b[2] - b[0] <= 72]
# Boxes that are no row: of different sizes, on different lines, or far apart.
assert shopping.swatchRows([(0, 0, 30, 30), (200, 300, 260, 360)]) == []
assert shopping.swatchRows([(0, 0, 30, 30), (40, 0, 70, 30), (400, 0, 430, 30)]) == [[0, 1]]
assert shopping.swatchRows([(0, 0, 30, 30), (40, 2, 70, 32), (0, 100, 30, 130), (40, 100, 70, 130), (80, 100, 110, 130)]) == [[2, 3, 4], [0, 1]]

# --- What the user's words ask of a seat map ---


def seatWish(said, **expected):
	wish = seats.seatWish(said)
	assert wish is not None, said
	plain = {"kind": None, "zone": None, "row": None, "nearRow": False, "seat": None, "count": seats.COUNT, "act": False, "together": False}
	plain.update(expected)
	assert wish == plain, (said, wish)
	return wish


ARTICLE = "Find an available window seat ahead of the wing on this aircraft map and click it to reserve my seat."
seatWish(ARTICLE, kind=seats.WINDOW, zone=seats.AHEAD_OF_WING, act=True)
seatWish("find me an aisle seat near the front", kind=seats.AISLE, zone=seats.FRONT)
seatWish("pick a window seat near row 12", kind=seats.WINDOW, row=12, nearRow=True, act=True)
seatWish("choose seat 12A", seat="12A", act=True)
seatWish("is seat 14c free", seat="14C")
seatWish("which seats are free in row 20", row=20)
seatWish("get me an exit row seat", zone=seats.EXIT, act=True)
seatWish("a middle seat at the back", kind=seats.MIDDLE, zone=seats.BACK)
seatWish("show me five window seats", kind=seats.WINDOW, count=5)
seatWish("find two seats together", together=True)
seatWish("a seat over the wing", zone=seats.OVER_WING)
seatWish("book a seat behind the wing", zone=seats.BEHIND_WING, act=True)
# "In front of the wing" is no wish for the front; "this window" is the program's window, not a window seat.
seatWish("a seat in front of the wing", zone=seats.AHEAD_OF_WING)
seatWish("select a seat in this window", act=True)
seatWish("find a window seat in this window", kind=seats.WINDOW)
# "Row 12 a window seat" names no seat 12A.
seatWish("row 12 a window seat", kind=seats.WINDOW, row=12)
for said in ("open the window", "how do I pick a seat", "click the Next button", "choose the Medium size", "", None):
	assert seats.seatWish(said) is None, said

# --- A seat map from the names of its seats ---

ROWS, LETTERS = range(10, 31), "ABCDEF"
TAKEN = {f"{row}{letter}" for row in range(10, 14) for letter in "AF"} | {"14B", "20C"}
PRICES = {"14A": "$15", "16F": "$9.50"}
for style in ("bare", "seat", "full", "rowseat"):
	seatMap = seats.fromNames(shopdrawn.seatControls(style, ROWS, LETTERS, taken=TAKEN, chosen={"15C"}, prices=PRICES, wing=range(16, 22), exits=(14, 15)))
	assert seatMap.isMap() and len(seatMap.seats) == 126 and seatMap.rows() == list(ROWS), style
	assert {seat.id for seat in seatMap.seats.values() if seat.free is False and not seat.chosen} == TAKEN, style
	assert [seat.id for seat in seatMap.seats.values() if seat.chosen] == ["15C"], style
	assert seatMap.seats["12B"].free is True and seatMap.seats["12B"].ref == "ref:12B", style
	# "Free" is only said where the page says it; a seat that can merely be pressed is said to be that.
	assert seatMap.seats["12B"].stated == (style != "bare"), style
	assert [seatMap.seats[f"12{letter}"].kind for letter in LETTERS] == ["window", "middle", "aisle", "aisle", "middle", "window"], style
	said = seats.mapText(seatMap)
	assert said.startswith("The seat map, read from the names of its seats, has rows 10 to 30 with 126 seats; 115 of them "), said
	assert ("can be chosen, which usually means they are free" in said) == (style == "bare"), said
	assert "Chosen now: 15C." in said
	if style == "full":
		# This page says window, aisle, exit row and over wing itself.
		assert seatMap.kindsFrom == seats.FROM_PAGE and "worked out" not in said
		assert seatMap.wingRows == set(range(16, 22)) and seatMap.exitRows == {14, 15}
		assert "The map says the wing is at rows 16 to 21." in said and "The map marks an exit at rows 14 to 15." in said
		assert seatMap.seats["14A"].price == "$15" and seatMap.seats["16F"].price == "$9.50" and seatMap.seats["14A"].exit
	else:
		# Here it was worked out from the letters, and the answer says so.
		assert seatMap.kindsFrom == seats.FROM_LETTERS and "worked out from the seat letters, as most aircraft are lettered" in said
		assert not seatMap.wingRows

# The article's request on a map that says where the wing is: window seats in the rows ahead of it, free ones only.
full = seats.fromNames(shopdrawn.seatControls("full", ROWS, LETTERS, taken=TAKEN, chosen={"15C"}, prices=PRICES, wing=range(16, 22), exits=(14, 15)))
wish = seats.seatWish(ARTICLE)
found, notes = seats.choose(full, wish)
assert [seat.id for seat in found] == ["14A", "14F", "15A"] and notes == [], ([seat.id for seat in found], notes)
assert seats.reason(found[0]) == "14A: window, row 14, free, exit row, $15"
question, choices = seats.question(found)
assert question == "Which seat should VisionClaw choose? The map gives a price for some of them. Choosing a seat may cost money."
assert choices == ["14A: window, row 14, free, exit row, $15", "14F: window, row 14, free, exit row", "15A: window, row 15, free, exit row", "None, only tell me"]
question, choices = seats.question(found[:1])
assert question == "Choose seat 14A: window, row 14, free, exit row, $15? The map says $15 for it. Choosing a seat may cost money."
assert choices == ["Yes, choose it", "No, only tell me"]
# The same request on a map that does not show the wing: no guess; that is said, and the front rows are offered.
bare = seats.fromNames(shopdrawn.seatControls("seat", ROWS, LETTERS, taken=TAKEN))
found, notes = seats.choose(bare, wish)
assert [seat.id for seat in found] == ["14A", "14F", "15A"], [seat.id for seat in found]
assert notes == [
	"This map does not show where the wing is, so VisionClaw cannot say which rows are ahead of it. These are the nearest "
	"to the front instead."], notes
said = seats.told(bare, wish, found, notes)
assert notes[0] in said and said.endswith("The best 3: 14A: window, row 14, free; 14F: window, row 14, free; 15A: window, row 15, free."), said
found, notes = seats.choose(bare, seats.seatWish("a seat over the wing"))
assert found == [] and notes[0].startswith("This map does not show where the wing is, so VisionClaw cannot say which rows are over it."), notes
found, notes = seats.choose(bare, seats.seatWish("book a seat behind the wing"))
assert [seat.id for seat in found] == ["30A", "30B", "30C"] and "nearest to the back instead" in notes[0]
# Behind and over the wing, where the map says where it is.
assert [seat.id for seat in seats.choose(full, seats.seatWish("a window seat behind the wing"))[0]] == ["22A", "22F", "23A"]
assert [seat.id for seat in seats.choose(full, seats.seatWish("a window seat over the wing"))[0]] == ["16A", "16F", "17A"]
# The wing's rows named by a control of their own.
ranged = seats.fromNames(shopdrawn.seatControls("seat", ROWS, LETTERS) + [{"label": "Wing: rows 15 to 22", "ref": "wing", "usable": False, "marked": False},
	{"label": "Emergency exit, row 14", "ref": "exit", "usable": False, "marked": False}])
assert ranged.wingRows == set(range(15, 23)) and ranged.exitRows == {14} and ranged.seats["14C"].exit and ranged.seats["15A"].wing
# Exit rows, the back, a row, near a row, a seat by its number, how many.
assert [seat.id for seat in seats.choose(full, seats.seatWish("get me an exit row seat"))[0]] == ["14A", "14C", "14D"]
found, notes = seats.choose(bare, seats.seatWish("get me an exit row seat"))
assert found == [] and notes == ["This map does not say which rows are exit rows. Name a row instead."]
assert [seat.id for seat in seats.choose(full, seats.seatWish("a middle seat at the back"))[0]] == ["30B", "30E", "29B"]
assert [seat.id for seat in seats.choose(full, seats.seatWish("which seats are free in row 20"))[0]] == ["20A", "20B", "20D"]
assert [seat.id for seat in seats.choose(full, seats.seatWish("pick a window seat near row 12"))[0]] == ["14A", "14F", "15A"]
found, notes = seats.choose(full, seats.seatWish("a window seat in row 12"))
assert [seat.id for seat in found] == ["14A", "14F", "15A"] and notes == ["No free seat of that kind is in row 12. These are the nearest rows."]
assert len(seats.choose(full, seats.seatWish("show me five window seats"))[0]) == 5
assert [seat.id for seat in seats.choose(full, seats.seatWish("choose seat 12B"))[0]] == ["12B"]
assert seats.choose(full, seats.seatWish("choose seat 10A")) == ([], ["Seat 10A is taken."])
assert seats.choose(full, seats.seatWish("choose seat 15C")) == ([], ["Seat 15C is the seat that is chosen now."])
assert seats.choose(full, seats.seatWish("choose seat 45K")) == ([], ["This map has no seat 45K."])
found, notes = seats.choose(full, seats.seatWish("find two seats together"))
assert found and notes == ["VisionClaw looks for one seat at a time; it does not look for seats next to each other yet."]
assert seats.told(full, seats.seatWish("find me a window seat at the front"), *seats.choose(full, seats.seatWish("find me a window seat at the front"))).endswith(
	"To choose one, say: choose seat 14A.")

# Letters with gaps for the missing middle seats (two and two): the aisle is between C and D.
small = seats.fromNames(shopdrawn.seatControls("bare", range(1, 9), "ACDF", taken={"1A"}))
assert [(seat.id, seat.kind) for seat in small.inOrder()[:4]] == [("1A", "window"), ("1C", "aisle"), ("1D", "aisle"), ("1F", "window")]
assert [seat.id for seat in seats.choose(small, seats.seatWish("find an aisle seat"))[0]] == ["1C", "1D", "2C"]
# The page marks the aisle itself, with a control that only says aisle: that counts, and nothing is worked out.
marked = seats.fromNames(shopdrawn.seatControls("bare", range(1, 9), "ABCDE", aisleAfter="B"))
assert [(seat.id, seat.kind) for seat in marked.inOrder()[:5]] == [("1A", "window"), ("1B", "aisle"), ("1C", "aisle"), ("1D", "middle"), ("1E", "window")]
assert marked.kindsFrom == seats.FROM_PAGE and "worked out" not in seats.mapText(marked)
# Letters that fit no usual way: the windows are still the outermost, the aisle is said to be unknown, and nothing is guessed.
odd = seats.fromNames(shopdrawn.seatControls("bare", range(1, 9), "ABCDE"))
assert [seat.kind for seat in odd.inOrder()[:5]] == ["window", None, None, None, "window"]
found, notes = seats.choose(odd, seats.seatWish("find an aisle seat"))
assert [seat.id for seat in found] == ["1A", "1B", "1C"] and notes == [
	"Which seats are at an aisle could not be told from this map: its seat letters fit no usual way of lettering. Every free seat is offered."]
assert seats.reason(found[1]) == "1B: row 1, can be chosen"
# Other ways pages name seats, and things that are no seats.
other = seats.fromNames([
	{"label": "Seat 3 A is available", "ref": 1}, {"label": "3B (Unavailable)", "ref": 2}, {"label": "3-C, Extra legroom, $24.00", "ref": 3},
	{"label": "Seat 3D not selected, available, free of charge", "ref": 4}, {"label": "seat 3e taken", "ref": 5},
	{"label": "3F Occupied", "ref": 6, "usable": False}, {"label": "2 Adults", "ref": 7}, {"label": "Flight 12 A320", "ref": 8},
	{"label": "Total $45.00", "ref": 9}, {"label": "3d secure payment", "ref": 10}, {"label": "Row 4", "ref": 11}])
assert sorted(other.seats) == ["3A", "3B", "3C", "3D", "3E", "3F"], sorted(other.seats)
assert [other.seats[ident].free for ident in sorted(other.seats)] == [True, False, True, True, False, False]
assert other.seats["3C"].price == "$24.00" and other.seats["3C"].notes == ["extra legroom"] and other.seats["3D"].price == "no charge"
assert not other.seats["3D"].chosen and seats.reason(other.seats["3C"]) == "3C: aisle, row 3, can be chosen, extra legroom, $24.00"
# Too few seats are no map.
assert not seats.fromNames([{"label": "12A", "ref": 1}, {"label": "Next", "ref": 2}]).isMap() and not seats.fromNames([]).isMap()
# What is said after a seat was pressed: chosen only when the map says so.
again = seats.fromNames(shopdrawn.seatControls("seat", ROWS, LETTERS, chosen={"14A"}))
assert seats.done(full.seats["14A"], again.seats["14A"]) == "Pressed seat 14A. The map now marks 14A as chosen."
assert "does not mark 14A as chosen" in seats.done(full.seats["14A"], bare.seats["14A"])
assert "could not be read again" in seats.done(full.seats["14A"], None)
taken = seats.fromNames(shopdrawn.seatControls("seat", ROWS, LETTERS, taken={"14A"}))
assert "it does not say chosen, so check before you go on" in seats.done(full.seats["14A"], taken.seats["14A"])

# --- A seat map that is only drawn ---

DRAWN_TAKEN, DRAWN_CHOSEN = {"10A", "11C", "12F"}, {"13D"}
for options in (dict(ids=True), dict(ids=False), dict(ids=True, sideways=True), dict(ids=False, sideways=True)):
	drawnPage, places = shopdrawn.seatPicture(range(10, 16), "ABCDEF", taken=DRAWN_TAKEN, chosen=DRAWN_CHOSEN, **options)
	seatMap = seats.fromPicture(drawnPage.lines, lambda box: colours.middle(drawnPage.image, box))
	assert seatMap.isMap() and len(seatMap.seats) == 36 and seatMap.source == seats.PICTURE, options
	assert {name: colours.name(colour) for name, colour in seatMap.legend.items()} == {"free": "green", "taken": "grey", "chosen": "blue"}, options
	assert {seat.id for seat in seatMap.seats.values() if seat.free is False} == DRAWN_TAKEN | DRAWN_CHOSEN, options
	assert [seat.id for seat in seatMap.seats.values() if seat.chosen] == ["13D"], options
	# Windows and aisles from the gaps between the columns, whichever way the map lies.
	assert [seatMap.seats[f"10{letter}"].kind for letter in "ABCDEF"] == ["window", "middle", "aisle", "aisle", "middle", "window"], options
	assert seatMap.kindsFrom == seats.FROM_GAPS and "worked out from the gaps between the columns in the picture" in seats.mapText(seatMap)
	# Each seat's place for the mouse is where it was drawn.
	for ident, (x, y) in places.items():
		assert abs(seatMap.seats[ident].ref[0] - x) <= 10 and abs(seatMap.seats[ident].ref[1] - y) <= 12, (options, ident, seatMap.seats[ident].ref, (x, y))
	found, notes = seats.choose(seatMap, seats.seatWish("find a window seat near the front"))
	assert [seat.id for seat in found] == ["10F", "11A", "11F"] and notes == [], options
	assert seats.mapText(seatMap).startswith("The seat map, read from the picture of the window, has rows 10 to 15 with 36 seats; 32 of them are free. Chosen now: 13D.")
# No legend that can be read: the seats are found, but which are free is not guessed, and the answer says so.
drawnPage, places = shopdrawn.seatPicture(range(10, 16), "ABCDEF", taken=DRAWN_TAKEN, legend=False)
seatMap = seats.fromPicture(drawnPage.lines, lambda box: colours.middle(drawnPage.image, box))
assert seatMap.isMap() and not seatMap.freeKnown() and all(seat.free is None for seat in seatMap.seats.values())
assert "which of them are free could not be told" in seats.mapText(seatMap)
found, notes = seats.choose(seatMap, seats.seatWish("find a window seat"))
assert found == [] and notes[0].startswith("Which seats are free could not be told: the picture has no legend that VisionClaw could read")
found, notes = seats.choose(seatMap, seats.seatWish("choose seat 11A"))
assert [seat.id for seat in found] == ["11A"] and notes == ["Whether seat 11A is free could not be told from this map."]
# The word Wing in the picture marks the row it stands beside and no more; the answer says that it is only that.
for sideways in (False, True):
	drawnPage, places = shopdrawn.seatPicture(range(10, 16), "ABCDEF", taken=DRAWN_TAKEN, wing=12, sideways=sideways)
	seatMap = seats.fromPicture(drawnPage.lines, lambda box: colours.middle(drawnPage.image, box))
	assert seatMap.wingRows == {12} and seatMap.wingByWord, (sideways, seatMap.wingRows)
	found, notes = seats.choose(seatMap, seats.seatWish("find a window seat ahead of the wing"))
	assert [seat.id for seat in found] == ["10F", "11A", "11F"], [seat.id for seat in found]
	assert notes == [
		"The picture has the word wing beside row 12; how far the wing reaches is not shown, so a row close to it may still be at "
		"the wing."], notes
	assert "The map says the wing" not in seats.mapText(seatMap)
# A legend's word inside a sentence is no legend.
sentence = [[{"x": 10, "y": 10, "width": 40, "height": 10, "text": "Free"}, {"x": 54, "y": 10, "width": 80, "height": 10, "text": "cancellation"}]]
assert seats.legendOf(sentence, lambda box: (10, 200, 10)) == {}
# A picture with no seats in it.
assert not seats.fromPicture([[{"x": 10, "y": 10, "width": 40, "height": 10, "text": "Welcome"}]], lambda box: None).isMap()
assert not seats.fromPicture([], lambda box: None).isMap()

# --- The tools, through stand-ins for NVDA. The real mouse is never moved. ---


class _Meta(type):
	def __getattr__(cls, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return type(name, (Anything,), {})


class Anything(metaclass=_Meta):
	"""A class that has every attribute, can be called and subclassed, and never complains (as in test_nvda_stub.py)."""

	def __init__(self, *args, **kwargs):
		pass

	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return Anything()

	def __call__(self, *args, **kwargs):
		return Anything()

	def __iter__(self):
		return iter(())

	def __getitem__(self, key):
		return Anything()

	def __or__(self, other):
		return self


class Stub(types.ModuleType):
	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		found = type(name, (Anything,), {})
		setattr(self, name, found)
		return found


def stub(name, **attributes):
	module = Stub(name)
	module.__dict__.update(attributes)
	sys.modules[name] = module
	return module


builtins._ = lambda text: text
conf = {"visionClaw": {"useOcr": True}}
stub("addonHandler", initTranslation=lambda: None)
stub("logHandler", log=Anything())
stub("config", conf=conf)
stub("wx", IsMainThread=lambda: True, CallAfter=lambda fn, *args: fn(*args), CallLater=lambda ms, fn, *args: None)
for name in (
		"api", "controlTypes", "textInfos", "textInfos.offsets", "ui", "winUser", "mouseHandler", "UIAHandler", "NVDAObjects",
		"NVDAObjects.UIA", "NVDAObjects.IAccessible", "contentRecog", "contentRecog.uwpOcr", "browseMode", "virtualBuffers",
		"keyboardHandler", "inputCore", "scriptHandler", "tones", "speech", "gui", "core", "queueHandler", "globalVars",
		"screenCurtain", "vision", "locationHelper", "winVersion", "nvwave", "appModuleHandler", "eventHandler", "winKernel",
		"cursorManager", "braille", "languageHandler", "globalPluginHandler", "documentationUtils", "globalCommands"):
	if name not in sys.modules:
		stub(name)
from visionClaw import shoptools  # noqa: E402
from visionClaw.claw.tools import ToolError  # noqa: E402

# The mouse, first of all: what would have been done is written down, and nothing is done.
mouse = []
shoptools.mousetools.click = lambda x, y, *args, **kwargs: mouse.append(("click", x, y))
shoptools.mousetools.position = lambda: (5, 5)
shoptools.mousetools.moveTo = lambda x, y: mouse.append(("move", x, y))
shoptools.mousetools.scaleAt = lambda x, y: 1.0
shoptools.SETTLE_SECONDS = 0

front = {"page": None, "window": None, "image": None, "lines": [], "frame": None}
pressed, questions, confirmed = [], [], []
answers = []


def node(name, role="BUTTON", states=(), up=None, box=None, **more):
	found = {"role": role, "name": name, "text": "", "states": list(states), "hidden": False, "key": (1, len(name) + 1), "up": up, "box": box}
	found.update(more)
	return found


def press(document, pressedNode):
	pressed.append(pressedNode["name"])
	react = front.get("react")
	if react:
		react(pressedNode)


def ask(question, choices):
	questions.append((question, list(choices)))
	return answers.pop(0) if answers else 0


shoptools._nodes = lambda task, onMain, place: (front[place], "document" if place == "page" else None) if front[place] else (None, None)
shoptools._boxesOf = lambda document, nodes: [found.get("box") for found in nodes]
shoptools._pressNode = press
shoptools._picture = lambda screen: (front["image"], front["frame"])
shoptools._read = lambda image: front["lines"] if conf["visionClaw"]["useOcr"] else []
plugin = types.SimpleNamespace(clawAsk=ask, _grab=lambda box: front["image"].crop(box), clawScreen=None)
tools = {}
shoptools.register(
	lambda name, description, fn, fields=None, **options: tools.__setitem__(name, (fn, fields, options)), plugin,
	lambda description, **extra: dict(extra, description=description), lambda fn, *args: fn(*args),
	lambda question: confirmed.append(question), lambda question: confirmed.append(question), None)
assert sorted(tools) == ["pick_option", "pick_seat"]
for name, (fn, fields, options) in tools.items():
	assert list(fields) == ["asked"] and fields["asked"]["auto"] is True and options["changes"] and options["tell"] == "verbatim", name


def run(tool, asked):
	del pressed[:], questions[:], confirmed[:], mouse[:]
	task = taskModule.Task("test")
	task.items = "the old list"
	return tools[tool][0](task, asked), task


def productPage():
	"""The options of shopdrawn.optionControls as the nodes of a page; a radio button that is pressed becomes the
	checked one of its group, as on a real page."""
	groups = {"Size": node("Size", "GROUPING"), "Storage": node("Storage", "GROUPING"), "Colour": node("Colour", "GROUPING"), "Blog": node("Blog", "GROUPING")}
	nodes = []
	swatches = iter(boxes[:4])
	for control in shopdrawn.optionControls():
		box = next(swatches) if control["group"] == "Colour" else None
		nodes.append(node(control["label"], control["role"], control["states"], groups.get(control["group"]), box))

	def react(pressedNode):
		for other in nodes:
			if other["up"] is pressedNode["up"] and other["role"] == "RADIOBUTTON":
				other["states"] = ["CHECKED"] if other is pressedNode else []
	return nodes, react


# By name, on a page: asked first, pressed the way NVDA presses it, read again, and said to be chosen because the page says so.
front["image"], front["frame"], front["lines"] = page.image, (0, 0) + page.image.size, page.lines
front["page"], front["react"] = productPage()
result, task = run("pick_option", "Click the Medium size swatch")
assert confirmed == ["Choose the option \"Medium\"?"] and pressed == ["Medium"] and mouse == [], (confirmed, pressed, mouse)
assert result == "Pressed the option \"Medium\". The page now marks it as chosen.", result
assert task.items is None
# A page that takes no notice of the press: said, not hidden.
front["page"], front["react"] = productPage()[0], None
result, task = run("pick_option", "Click the Medium size swatch")
assert pressed == ["Medium"] and "does not mark it as chosen, so the press may not have been taken" in result, result
# Only asked whether it is chosen: nothing is pressed and nothing is asked.
result, task = run("pick_option", "confirm the storage capacity is set to 256GB")
assert result == "No. The page does not mark the option \"256 GB\" as chosen. Marked as chosen now: 128GB." and pressed == [] and confirmed == [], result
assert task.items == "the old list"
# Sold out: found, said, not pressed.
result, task = run("pick_option", "choose size XL")
assert result.startswith("Nothing was pressed: the option \"XL - sold out\" is there, but the page shows it as not available") and pressed == [] and confirmed == []
# By colour: the swatches are measured from the picture; the shop's own name is said with the measured colour.
front["page"], front["react"] = productPage()
result, task = run("pick_option", "select the dark blue color option")
assert confirmed == ["Choose the option \"Midnight\", measured dark blue?"] and pressed == ["Midnight"], (confirmed, pressed)
# A plain button has no state, and its picture did not change: the answer says that it may not have been taken.
assert result == (
	"Pressed the option \"Midnight\", measured dark blue. The page does not say whether it is chosen, and nothing VisionClaw can see "
	"changed, so it may not have been taken. " + shopping.MEASURED_NOTE), result


def ring(pressedNode):
	"""A page that draws a ring around the swatch that was pressed, and says nothing to NVDA."""
	left, top, right, bottom = pressedNode["box"]
	page.draw.rectangle((left - 3, top - 3, right + 3, bottom + 3), outline=(0, 0, 0), width=2)


front["react"] = ring
result, task = run("pick_option", "click the red swatch")
assert confirmed == ["Choose an option with no name, number 3 of those found, measured red?"] and pressed == [""], (confirmed, pressed)
assert "its picture changed after the press, as it does when an option is taken" in result and result.endswith(shopping.MEASURED_NOTE), result
# Nothing of that colour: nothing is pressed, and what was measured is said.
result, task = run("pick_option", "choose the purple one")
assert result.startswith("Nothing was pressed: none of the options found is \"purple\". Found: The option \"Midnight\", measured dark blue;") and pressed == [], result
# Two that fit: the user is asked which, and "None of these" presses nothing.
page2, boxes2 = shopdrawn.swatches([shopdrawn.NAVY, (140, 190, 240), shopdrawn.RED])
colourGroup = node("Colour", "GROUPING")
front["image"], front["frame"], front["lines"] = page2.image, (0, 0) + page2.image.size, page2.lines
front["page"], front["react"] = [node("", "BUTTON", (), colourGroup, box) for box in boxes2], None
answers[:] = [1]
result, task = run("pick_option", "choose the blue one")
assert questions[0] == ("More than one option fits \"blue\". Which one do you mean?", [
	"An option with no name, number 1 of those found, measured dark blue", "An option with no name, number 2 of those found, measured light blue",
	"None of these"]), questions
assert confirmed == ["Choose an option with no name, number 2 of those found, measured light blue?"] and pressed == [""]
answers[:] = [2]
result, task = run("pick_option", "choose the blue one")
assert result == "You did not say which option, so nothing was pressed." and pressed == [] and confirmed == []
# A size that is chosen in a combo box: said, with what it shows; a link with the word in it is not taken for it.
front["page"] = [node("Size", "COMBOBOX", text="Medium"), node("Large print books", "LINK")]
result, task = run("pick_option", "choose the Large size")
assert result.startswith("On this page that is chosen in the combo box \"Size\", which shows Medium now.") and pressed == [] and confirmed == [], result
# No page and nothing in the window that NVDA knows: the swatches are found in the window's picture and clicked with
# the mouse, which is put back where it was.
front["page"], front["window"] = None, [node("Window", "PANE")]
front["image"], front["frame"], front["lines"] = page.image, (100, 50, 100 + page.image.size[0], 50 + page.image.size[1]), page.lines
page, boxes = shopdrawn.swatches([shopdrawn.NAVY, shopdrawn.BLACK, shopdrawn.RED, shopdrawn.CREAM, shopdrawn.GREEN])
front["image"] = page.image
plugin._grab = lambda box: page.image.crop((box[0] - 100, box[1] - 50, box[2] - 100, box[3] - 50))
result, task = run("pick_option", "click the red swatch")
assert confirmed == ["Choose an option with no name, number 3 of those found, measured red, found in the window's picture?"], confirmed
x, y = (boxes[2][0] + boxes[2][2]) // 2 + 100, (boxes[2][1] + boxes[2][3]) // 2 + 50
assert mouse[0][0] == "click" and abs(mouse[0][1] - x) <= 3 and abs(mouse[0][2] - y) <= 3 and mouse[-1] == ("move", 5, 5), (mouse, x, y)
assert pressed == [] and result.startswith("Pressed an option with no name, number 3 of those found, measured red, found in the window's picture."), result
# An option's name that is only read in the picture is clicked there too, in the middle of its words.
import drawn  # noqa: E402
sizes = drawn.Page(400, 120)
sizes.text(20, 20, "Size")
places = {word: sizes.text(20 + index * 110, 60, word) for index, word in enumerate(("Small", "Medium", "Large"))}
front["image"], front["lines"] = sizes.image, sizes.lines
front["frame"] = (100, 50, 100 + sizes.image.size[0], 50 + sizes.image.size[1])
plugin._grab = lambda box: sizes.image.crop((box[0] - 100, box[1] - 50, box[2] - 100, box[3] - 50))
result, task = run("pick_option", "Click the Medium size swatch")
assert confirmed == ["Choose the option \"Medium\", read in the window's picture?"], confirmed
x, y = (places["Medium"][0] + places["Medium"][2]) // 2 + 100, (places["Medium"][1] + places["Medium"][3]) // 2 + 50
assert mouse[0] == ("click", x, y) and mouse[-1] == ("move", 5, 5), (mouse, x, y)
assert result.startswith("Pressed the option \"Medium\", read in the window's picture. The page does not say whether it is chosen"), result
front["image"], front["lines"] = page.image, page.lines
front["frame"] = (100, 50, 100 + page.image.size[0], 50 + page.image.size[1])
plugin._grab = lambda box: page.image.crop((box[0] - 100, box[1] - 50, box[2] - 100, box[3] - 50))
# With reading of pictures turned off, the picture is not used.
conf["visionClaw"]["useOcr"] = False
result, task = run("pick_option", "click the red swatch")
assert result.startswith("Nothing was pressed: no option called \"red\" was found") and mouse == [], result
conf["visionClaw"]["useOcr"] = True
# Words that name no option are an error for the form, not a guess.
try:
	run("pick_option", "Click the Next button")
	raise AssertionError("no option was named")
except ToolError as e:
	assert str(e) == shopping.NO_WISH

# A seat map on a page: the seats that fit are told; a seat is pressed only after a question, which is always asked.
front["window"] = None


def seatPage(**options):
	nodes = [node(control["label"], "BUTTON", (() if control["usable"] else ("UNAVAILABLE",)) + (("SELECTED",) if control["marked"] else ()))
		for control in shopdrawn.seatControls("full", ROWS, LETTERS, taken=TAKEN, prices=PRICES, wing=range(16, 22), exits=(14, 15), **options)]

	def react(pressedNode):
		pressedNode["name"] = pressedNode["name"].replace("available", "selected")
	return nodes, react


front["page"], front["react"] = seatPage()
answers[:] = [1]
result, task = run("pick_seat", ARTICLE)
assert questions == [("Which seat should VisionClaw choose? The map gives a price for some of them. Choosing a seat may cost money.", [
	"14A: window, row 14, free, exit row, $15", "14F: window, row 14, free, exit row", "15A: window, row 15, free, exit row", "None, only tell me"])], questions
assert pressed == ["14F, window, available, exit row"] and mouse == [], pressed
assert result.startswith("The seat map, read from the names of its seats, has rows 10 to 30 with 126 seats; 116 of them are free.") and result.endswith(
	"Pressed seat 14F. The map now marks 14F as chosen."), result
assert task.items is None
# "None" presses nothing; the seats are still told.
front["page"], front["react"] = seatPage()
answers[:] = [3]
result, task = run("pick_seat", ARTICLE)
assert pressed == [] and result.endswith("15A: window, row 15, free, exit row. You did not choose one, so nothing was pressed."), result
# Only asked to find: nothing is asked and nothing is pressed.
result, task = run("pick_seat", "find me an aisle seat near the front")
assert questions == [] and pressed == [] and result.endswith("To choose one, say: choose seat 10C."), result
# A page that takes no notice of the press: said.
front["page"], front["react"] = seatPage()[0], None
answers[:] = [0]
result, task = run("pick_seat", "choose seat 12B")
assert questions[0][0] == "Choose seat 12B: middle, row 12, free? Choosing a seat may cost money." and pressed == ["12B, middle, available"]
assert "The map does not mark 12B as chosen, so the press may not have been taken" in result, result
# A taken seat is not pressed and not asked about.
result, task = run("pick_seat", "choose seat 10A")
assert questions == [] and pressed == [] and result.endswith("Seat 10A is taken."), result
# A map that is only drawn: read from the window's picture, and the seat is clicked with the mouse at its place.
drawnPage, places = shopdrawn.seatPicture(range(10, 16), "ABCDEF", taken=DRAWN_TAKEN, chosen=DRAWN_CHOSEN)
front["page"], front["window"], front["react"] = None, [node("Window", "PANE")], None
front["image"], front["frame"], front["lines"] = drawnPage.image, (200, 100, 200 + drawnPage.image.size[0], 100 + drawnPage.image.size[1]), drawnPage.lines
answers[:] = [0]
result, task = run("pick_seat", "choose seat 11A")
assert questions[0][0] == "Choose seat 11A: window, row 11, free? Choosing a seat may cost money.", questions
assert mouse[0][0] == "click" and abs(mouse[0][1] - (places["11A"][0] + 200)) <= 10 and abs(mouse[0][2] - (places["11A"][1] + 100)) <= 12, (mouse, places["11A"])
assert mouse[-1] == ("move", 5, 5) and pressed == []
# The picture did not change, so the map still shows the seat as free: the answer says the press may not have been taken.
assert result.startswith("The seat map, read from the picture of the window, has rows 10 to 15") and "does not mark 11A as chosen" in result, result
# Nothing that is a seat map.
front["image"], front["lines"] = page.image, page.lines
result, task = run("pick_seat", "find a window seat")
assert result == seats.NO_MAP
try:
	run("pick_seat", "Click the Next button")
	raise AssertionError("no seat was asked for")
except ToolError as e:
	assert str(e) == seats.NO_WISH

# Before a button that buys is pressed: the total is read from the page, and the user is always asked.
shoptools._pageLines = lambda plugin, onMain: PAGE_TEXT.splitlines()
del questions[:]
assert shoptools.guardPurchase(plugin, lambda fn, *args: fn(*args), "Add to cart") is True and questions == []
assert shoptools.guardPurchase(plugin, lambda fn, *args: fn(*args), "Proceed to checkout") is True and questions == []
answers[:] = [0]
assert shoptools.guardPurchase(plugin, lambda fn, *args: fn(*args), "Place your order") is True
assert questions == [(
	"\"Place your order\" buys, books or pays. The page says: Order total: $45.99. Press it? This may not be possible to take back.",
	["Yes, press it", "No, do not press it"])], questions
answers[:] = [1]
assert shoptools.guardPurchase(plugin, lambda fn, *args: fn(*args), "Buy now") is False
# The user closing the question without an answer is a no.
plugin.clawAsk = lambda question, choices: None
assert shoptools.guardPurchase(plugin, lambda fn, *args: fn(*args), "Pay now") is False
plugin.clawAsk = ask


# A page that cannot be read is no fault: the question says that no total was found.
def broken(plugin, onMain):
	raise RuntimeError("the page is gone")


shoptools._pageLines = broken
del questions[:]
answers[:] = [0]
assert shoptools.guardPurchase(plugin, lambda fn, *args: fn(*args), "Book now") is True
assert "VisionClaw found no total on the page" in questions[0][0], questions

print("OK")
