# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The plain logic behind the ten things of docs/PLAN-ten-scenarios.md that the main parts share: colours
measured from pixels, places found in a picture, a form that is only a picture, a picture on a page and what is
asked about it, a drawn knob set to a number, an installer gone through page after page, and a form's fields
outlined in red.

Plain Python: no NVDA, no model, no mouse. The pictures are drawn by tests/drawn.py and the knobs and installers
are made up here; none is a real program or website. What passes here says that the rules do what they are meant
to do on these, not that they do it on a real scanned form, plug-in or installer.

  python tests/test_ten.py
"""
import harness  # noqa: F401
import drawn
from PIL import Image, ImageDraw
from visionClaw.claw import colours, guide, images, pageview, paper, pictures, spots, target, wizard

# --- Colours named from their red, green and blue ---

for rgb, name in (
	((0, 0, 0), "black"), ((15, 15, 15), "black"), ((255, 255, 255), "white"), ((245, 245, 245), "white"),
	((128, 128, 128), "grey"), ((60, 60, 60), "dark grey"), ((200, 200, 200), "light grey"), ((54, 69, 79), "dark grey"),
	((20, 25, 60), "dark blue"), ((0, 0, 128), "dark blue"), ((0, 0, 255), "blue"), ((135, 206, 235), "light blue"),
	((255, 0, 0), "red"), ((128, 0, 0), "dark red"), ((217, 48, 37), "red"), ((139, 69, 19), "brown"),
	((255, 165, 0), "orange"), ((245, 222, 179), "beige"), ((255, 253, 208), "cream"), ((255, 255, 0), "yellow"),
	((128, 128, 0), "olive"), ((0, 128, 0), "green"), ((0, 100, 0), "dark green"), ((144, 238, 144), "light green"),
	((64, 224, 208), "turquoise"), ((128, 0, 128), "purple"), ((230, 190, 255), "light purple"), ((255, 192, 203), "light pink"),
	((255, 105, 180), "pink"), ((192, 192, 192), "light grey"),
):
	assert colours.name(rgb) == name, (rgb, colours.name(rgb), name)
	assert colours.name(rgb) in colours.NAMES, colours.name(rgb)
# Every name a colour can get is a name a person would say, and every asked word leads to one of them.
assert all(value in colours.NAMES for value in colours.ASKED.values()), [v for v in colours.ASKED.values() if v not in colours.NAMES]

# What the user's words name.
assert colours.wanted("select the dark blue color option") == ["dark blue"]
assert colours.wanted("is this jacket navy blue or solid black") == ["dark blue", "black"]
assert colours.wanted("the light gray one or the maroon one") == ["light grey", "dark red"]
assert colours.wanted("Click the Medium size swatch") == [] and colours.wanted("") == []
assert colours.wanted("the teal one, not the blue one") == ["dark turquoise", "blue"]
# Which measured colour is the one asked for.
assert colours.closest("dark blue", ["black", "dark blue", "red"]) == (1, True)
assert colours.closest("blue", ["dark blue", "light blue"]) == (None, [0, 1])
assert colours.closest("blue", ["dark blue", "red"]) == (0, True)
assert colours.closest("green", ["red", "white"]) == (None, [])
assert colours.fit("dark blue", "dark blue") == 2 and colours.fit("blue", "dark blue") == 1 and colours.fit("blue", "red") == 0
assert colours.distance((0, 0, 0), (0, 0, 0)) == 0 and colours.distance((255, 0, 0), (0, 0, 255)) > 300

# --- A form of a web page whose only sign of trouble is a red outline ---

page, fields = drawn.webForm(wrong=(1, 3))
assert colours.marked(page.image, fields) == [1, 3], [round(colours.redShare(page.image, box), 2) for box in fields]
assert colours.redLines(page.image, page.lines) == ["Please check this field", "Please check this field"], colours.redLines(page.image, page.lines)
clean, fields = drawn.webForm(wrong=())
assert colours.marked(clean.image, fields) == [] and colours.redLines(clean.image, clean.lines) == []
# A field that is only partly on the picture, or no box at all, is no fault.
assert colours.marked(page.image, [None, (500, 400, 900, 700), (-50, -50, -10, -10)]) == []
assert colours.redShare(page.image, (10, 10, 12, 12)) == 0.0

# --- The colours of a photo: what it shows, without the plain background it stands on ---

photo = Image.new("RGB", (300, 300), (250, 250, 250))
ImageDraw.Draw(photo).rectangle((60, 40, 240, 280), fill=(22, 28, 62))
assert colours.ground(photo) == "white"
back, shares = colours.subject(photo)
assert back == "white" and shares[0][0] == "dark blue" and shares[0][1] > 0.9, (back, shares)
assert colours.main(photo)[0][0] in ("white", "dark blue") and len(colours.main(photo)) == 2
assert colours.name(colours.middle(photo, (60, 40, 240, 280))) == "dark blue"
assert colours.said([("dark blue", 0.62), ("white", 0.2)]) == "mostly dark blue (62 percent), then white (20 percent)"
assert colours.said([("black", 0.95)]) == "almost all black (95 percent)" and colours.said([]) == ""
said = images.measured(photo, ["dark blue", "black"])
assert said.startswith("Measured from the picture's pixels: leaving out the white background, almost all dark blue"), said
assert "dark blue is there; black is hardly there" in said and "light in a photo" in said, said
black = Image.new("RGB", (300, 300), (250, 250, 250))
ImageDraw.Draw(black).rectangle((60, 40, 240, 280), fill=(14, 14, 16))
assert "dark blue is hardly there; black is there" in images.measured(black, ["dark blue", "black"]), images.measured(black, ["dark blue", "black"])
assert "blue as such is not, but a darker or lighter blue is" in images.measured(photo, ["blue"]), images.measured(photo, ["blue"])
assert images.measured(Image.new("RGB", (50, 50), (255, 255, 255)), ["red"]) == ""

# --- A printed form that is only a picture: lines, boxes, labels ---

form, where = drawn.paperForm()
rules = spots.rules(form.image)


def has(box, found, slack=4):
	return any(all(abs(a - b) <= slack for a, b in zip(box, rule["box"])) for rule in found)


for key in ("nameRule", "birthRule", "addressRule", "signRule", "dateRule"):
	assert has(where[key], rules), (key, where[key], [rule["box"] for rule in rules])
# Dotted lines are told from solid ones; no line of the paragraph's text is taken for a line to write on.
assert [rule["dotted"] for rule in rules if has(where["birthRule"], [rule]) or has(where["signRule"], [rule])] == [True, True]
assert not [rule for rule in rules if 55 < rule["box"][1] < 100], [rule["box"] for rule in rules]
assert len(rules) <= 7, [rule["box"] for rule in rules]
boxes = spots.squares(form.image)
assert [(square["box"], square["ticked"]) for square in boxes] == [(where["agreeBox"], False), (where["newsBox"], True)], boxes

# A label is found where it stands, also when the reading joined two words or got a letter wrong.
for label in ("Applicant Full Name", "applicant full name", "ApplicantFull Name", "Aplicant Full Name", "Applicant Full Name:"):
	assert len(spots.phrase(form.lines, label)) == 1, label
assert spots.phrase(form.lines, "Nothing here") == [] and spots.phrase(form.lines, "") == [] and spots.phrase(None, "Name") == []
# "Address" is in the paragraph too; both are found, the paragraph's first.
assert len(spots.phrase(form.lines, "Address")) == 2

# Which line belongs to a label: to its right; under it; above it, as a line to sign has its word under it.
for label, key, how in (
	("Applicant Full Name", "nameRule", spots.NEXT), ("Date of Birth", "birthRule", spots.NEXT),
	("Authorized Signature", "signRule", spots.ABOVE),
):
	place = spots.phrase(form.lines, label)[0]
	rule, relation = spots.blankFor(place, rules)
	assert has(where[key], [rule]) and relation == how, (label, rule, relation)
	x, y = spots.writePoint(rule, place[3] - place[1])
	assert rule["box"][0] < x < rule["box"][0] + 20 and rule["box"][1] - 10 < y < rule["box"][1], (label, x, y)
address = spots.phrase(form.lines, "Address")
assert spots.blankFor(address[0], rules) is None  # the word in the paragraph has no line
rule, relation = spots.blankFor(address[1], rules)
assert has(where["addressRule"], [rule]) and relation == spots.UNDER
# The side the user's words name is the only side looked at.
sign = spots.phrase(form.lines, "Authorized Signature")[0]
assert spots.blankFor(sign, rules, spots.UNDER) is None and spots.blankFor(sign, rules, spots.ABOVE)[1] == spots.ABOVE
# "Date" stands twice: in "Date of Birth" and under the line at the bottom.
dates = spots.phrase(form.lines, "Date")
assert len(dates) == 2 and has(where["dateRule"], [spots.blankFor(dates[1], rules)[0]])
# A line that is written on already says so; a blank one does not.
email = spots.phrase(form.lines, "Email")[0]
written, _how = spots.blankFor(email, rules)
assert spots.written(form.image, written, 14) is True
name = spots.phrase(form.lines, "Applicant Full Name")[0]
assert spots.written(form.image, spots.blankFor(name, rules)[0], 14) is False
# The label right above its own line is not taken for writing on it.
assert spots.written(form.image, spots.blankFor(address[1], rules)[0], 14, address[1]) is False
# The check box that belongs to a label.
agree = spots.phrase(form.lines, "I agree to the rules of the library")[0]
assert spots.squareFor(agree, boxes) == {"box": where["agreeBox"], "ticked": False}
news = spots.phrase(form.lines, "Send me news")[0]
assert spots.squareFor(news, boxes)["ticked"] is True and spots.squareFor(name, boxes) is None
assert spots.whereText((40, 20, 100, 40), (800, 620)) == "near the top, on the left"
assert spots.whereText((300, 300, 500, 320), (800, 620)) == "in the middle"
assert spots.whereText((600, 560, 700, 580), (800, 620)) == "near the bottom, on the right"
assert [word["text"] for _distance, word in spots.near(form.lines, where["nameRule"], 60)][:3]
# A larger screen: the same form at 240 percent is read with the same rules.
big = form.image.resize((1920, 1488))
assert len(spots.rules(big, 2.4)) == len(rules) and len(spots.squares(big, 2.4)) == 2

# A grid of tiles, as a puzzle of pictures has; a form is no grid.
for rows, columns, side, gap in ((3, 3, 100, 6), (4, 4, 80, 3), (2, 3, 120, 8)):
	image, tiles = drawn.tiles(rows, columns, side, gap)
	found = spots.grid(image)
	assert found is not None and found[:2] == (rows, columns) and len(found[2]) == rows * columns, (rows, columns, found and found[:2])
	assert all(abs(a - b) <= 2 for tile, box in zip(found[2], tiles) for a, b in zip(tile, box)), (found[2][:2], tiles[:2])
image, tiles = drawn.tiles(3, 3)
wide = Image.new("RGB", (600, 500), (255, 255, 255))
wide.paste(image, (120, 90))
found = spots.grid(wide, (120, 90, 120 + image.size[0], 90 + image.size[1]))
assert found[:2] == (3, 3) and abs(found[2][0][0] - (120 + tiles[0][0])) <= 2
assert spots.grid(form.image) is None and spots.grid(image, (0, 0, 4, 4)) is None

# --- What the user's words ask on such a form ---

for said, expected in (
	("click directly on the blank line next to 'Applicant Full Name,' and type my name",
		{"label": "Applicant Full Name", "kind": paper.LINE, "side": spots.NEXT, "which": None, "typed": None, "own": paper.NAME, "signs": False}),
	("Find the dotted line labeled 'Authorized Signature' at the bottom of the page and click there so I can place my digital signature.",
		{"label": "Authorized Signature", "kind": paper.LINE, "side": spots.ANY, "which": paper.LAST, "typed": None, "own": None, "signs": True}),
	("Click the line next to Date of Birth and type 3 March 1990",
		{"label": "Date of Birth", "kind": paper.LINE, "side": spots.NEXT, "which": None, "typed": "3 March 1990", "own": None, "signs": False}),
	("Type Josh Kennedy on the line under Address",
		{"label": "Address", "kind": paper.LINE, "side": spots.UNDER, "which": None, "typed": "Josh Kennedy", "own": None, "signs": False}),
	("Put my email on the Email line",
		{"label": "Email", "kind": paper.LINE, "side": spots.ANY, "which": None, "typed": None, "own": paper.EMAIL, "signs": False}),
	("Type \"N/A\" on the dotted line next to \"Middle name\"",
		{"label": "Middle name", "kind": paper.LINE, "side": spots.NEXT, "which": None, "typed": "N/A", "own": None, "signs": False}),
	("click the line labelled Date at the bottom and type today's date",
		{"label": "Date", "kind": paper.LINE, "side": spots.ANY, "which": paper.LAST, "typed": None, "own": paper.DATE, "signs": False}),
	("write my phone number in the blank after Phone",
		{"label": "Phone", "kind": paper.LINE, "side": spots.NEXT, "which": None, "typed": None, "own": paper.PHONE, "signs": False}),
	("check the box next to I agree to the rules in this scanned PDF",
		{"label": "I agree to the rules", "kind": paper.BOX, "side": spots.NEXT, "which": None, "typed": None, "own": None, "signs": False}),
	("tick the box beside Send me news on this printed form",
		{"label": "Send me news", "kind": paper.BOX, "side": spots.NEXT, "which": None, "typed": None, "own": None, "signs": False}),
):
	assert paper.wish(said) == expected, (said, paper.wish(said))
assert paper.wish("click the signature line")["label"] == "signature" and paper.wish("click the signature line")["signs"]
# What is no line or box of a paper form: a real check box is worked by its name, a button is clicked, a question is answered.
for said in (
	"check the box next to I agree to the rules", "how do I type on the line next to Name", "Click the Next button",
	"type hello in the search box", "read this line", "go to line 40", "draw a line from the top to the bottom",
	"Select the Fill and Sign tool", "type my name", "Make NVDA talk faster", "click the dotted line", "",
):
	assert paper.wish(said) is None, (said, paper.wish(said))

# The user's own facts come from what they asked VisionClaw to remember, word for word, and are never made up.
assert paper.remembered(paper.NAME, ["You like to be called Sam.", "Your name is Josh Kennedy."]) == "Josh Kennedy"
assert paper.remembered(paper.NAME, ["You like to be called Sam."]) is None  # what someone is called is no name for a form
assert paper.remembered(paper.EMAIL, ["Your email address is josh@example.org."]) == "josh@example.org"
assert paper.remembered(paper.PHONE, ["Your phone number is 555 010 0199."]) == "555 010 0199"
assert paper.remembered(paper.ADDRESS, ["Your address is 12 Oak Street, Reading, PA 19601."]) == "12 Oak Street, Reading, PA 19601"
assert paper.remembered(paper.NAME, []) is None and paper.remembered(paper.DATE, ["Your name is A B."]) is None
# The newest memory wins.
assert paper.remembered(paper.NAME, ["Your name is Old Name.", "Your name is New Name."]) == "New Name"
assert paper.today(2026, 11, 19) == "November 19, 2026" and paper.today(2027, 3, 4) == "March 4, 2027"
assert paper.ownOf("my full name") == paper.NAME and paper.ownOf("today's date") == paper.DATE and paper.ownOf("Josh") is None
assert "remember that my name is" in paper.ownQuestion(paper.NAME)

# Which of several places is meant, and the sentences.
assert paper.choose([1], None) == 0 and paper.choose([1, 2, 3], paper.LAST) == 2 and paper.choose([1, 2], paper.FIRST) == 0
assert paper.choose([1, 2], None) is None
assert paper.placeChoices(dates, (800, 620)) == ["Number 1, near the top, on the left", "Number 2, near the bottom"]
wished = paper.wish("click the blank line next to 'Applicant Full Name' and type my name")
assert paper.question(wished, spots.NEXT, "Josh Kennedy") == (
	"Click the line to the right of \"Applicant Full Name\" with the mouse and type \"Josh Kennedy\"?")
assert "written on that line already" in paper.question(wished, spots.NEXT, "Josh Kennedy", written=True)
assert paper.done(wished, spots.NEXT, "Josh Kennedy", shows=True) == (
	"Clicked the line to the right of \"Applicant Full Name\" and typed \"Josh Kennedy\". The text is now read there in the picture.")
assert "could not read the text back" in paper.done(wished, spots.NEXT, "Josh Kennedy", shows=False)
signs = paper.wish("click the dotted line labelled Authorized Signature so I can sign")
assert paper.done(signs, spots.ABOVE, None, dotted=True).startswith("Clicked the dotted line above \"Authorized Signature\". VisionClaw does not sign for you")
ticks = paper.wish("check the box next to I agree in this scanned form")
assert paper.question(ticks, spots.NEXT, None, ticked=False) == "Click the check box at \"I agree\" with the mouse? It looks empty."
assert paper.done(ticks, spots.NEXT, None, changed=True).endswith("so the click was taken.")
assert paper.notFound(wished, True).startswith("Nothing was clicked: the words \"Applicant Full Name\" were not found")
assert paper.notFound(wished, False).startswith("Nothing was clicked: no text could be read")
assert paper.noBlank(wished).startswith("Nothing was clicked: \"Applicant Full Name\" was found, but no line to write on")

# --- A picture on a page or in a window: which one is meant, and what is asked about it ---

for said, which, asks in (
	("Read the text inside the latest image posted in this WhatsApp chat and explain the visual joke.", images.LATEST,
		[(pictures.TEXT, "Read the text inside the latest image posted in this WhatsApp chat"), (images.JOKE, "explain the visual joke")]),
	("Look at the screenshot my coworker just shared, what error code is highlighted in the dialog box?", images.LATEST,
		[(pictures.FOCUS, "what error code is highlighted in the dialog box?")]),
	("Look at the product photo, is this jacket navy blue or solid black, and does it have any printed logos?", images.PRODUCT,
		[(pictures.COLOUR, "is this jacket navy blue or solid black"), (pictures.FIND, "does it have any printed logos?")]),
	("Look at the room gallery photos and tell me whether the balcony overlooks the ocean or the mountains.", images.GALLERY,
		[(pictures.DESCRIBE, "tell me whether the balcony overlooks the ocean or the mountains")]),
	("what does the meme say", images.LARGEST, [(pictures.TEXT, "what does the meme say")]),
	("describe this picture", images.FOCUSED, [(pictures.DESCRIBE, "describe this picture")]),
	("look at the last picture", images.LATEST, [(pictures.DESCRIBE, "What does this picture show?")]),
	("What's in the first photo on this page?", images.FIRST, [(pictures.DESCRIBE, "What's in the first photo on this page?")]),
	("explain the joke in the picture my friend sent", images.LATEST, [(images.JOKE, "explain the joke in the picture my friend sent")]),
):
	wished = images.wish(said)
	assert wished is not None and wished["which"] == which, (said, wished)
	assert images.asks(said) == asks, (said, images.asks(said))
for said in ("Make NVDA talk faster", "what is on my screen", "click the Next button", "open my downloads folder", ""):
	assert images.wish(said) is None, said
assert images.rule(images.JOKE) == images.JOKE_RULE and images.rule(pictures.TEXT) == pictures.RULES[pictures.TEXT]
# The rule for a joke has no example in it: a small model copies an example as if it were the answer.
assert "for example" not in images.JOKE_RULE.lower() and "such as" not in images.JOKE_RULE.lower()

# Which of the pictures found is meant: the little faces and emoji of a chat are never it.
window = (0, 0, 1200, 800)
found = [
	{"box": (10, 10, 42, 42), "name": "Sam", "order": 1},
	{"box": (100, 100, 400, 300), "name": "IMG_2231.jpg", "order": 2},
	{"box": (10, 320, 42, 352), "name": "Alex", "order": 3},
	{"box": (100, 420, 500, 700), "name": "A cat sitting in a box", "order": 4, "focused": False},
	{"box": (520, 690, 540, 710), "name": "thumbs up", "order": 5},
]
for which, orders in ((images.LATEST, [4]), (images.FIRST, [2]), (images.LARGEST, [4]), (images.PRODUCT, [4]), (images.GALLERY, [2, 4]), (images.FOCUSED, [4])):
	chosen, more = images.choose({"which": which}, found, window)
	assert [picture["order"] for picture in chosen] == orders and more == 0, (which, chosen)
found[1]["focused"] = True
assert [picture["order"] for picture in images.choose({"which": images.FOCUSED}, found, window)[0]] == [2]
assert images.choose({"which": images.LATEST}, found[:1] + found[2:3], window) == ([], 0)
# A gallery of many photos: the first few are looked at, and the user is told how many were not.
many = [{"box": (10 + 210 * index, 100, 200 + 210 * index, 300), "name": f"Room {index}", "order": index} for index in range(7)]
chosen, more = images.choose({"which": images.GALLERY}, many, (0, 0, 1600, 900))
assert len(chosen) == images.MAX_GALLERY and more == 3 and "3 more pictures were not looked at" in images.leftOut(more)
assert images.leftOut(0) == ""
# On a large screen at 200 percent, a picture must be larger to be meant.
assert images.bigEnough((0, 0, 100, 100), window) and not images.bigEnough((0, 0, 100, 100), window, 2.0)
assert images.visible((100, 100, 300, 300), window) == 1.0 and images.visible((1100, 100, 1300, 300), window) == 0.5
assert images.visible((2000, 100, 2200, 300), window) == 0.0
# What the page calls a picture is said when it says something: a file's name says nothing.
assert images.calls({"name": "IMG_2231.jpg"}) == "" and images.calls({"name": "image"}) == "" and images.calls({"name": ""}) == ""
assert images.calls({"name": "A cat sitting in a box"}) == "A cat sitting in a box"
assert images.lead({"which": images.LATEST}, found[3]) == "The last picture on this page, which the page calls \"A cat sitting in a box\""
assert images.lead({"which": images.GALLERY}, many[0], 1, 4, "window") == "Picture 1 of 4 in this window, which the program calls \"Room 0\""
assert images.lead({"which": images.LATEST}, {"name": ""}, where="picture") == "The picture found in the lower part of this window"

# --- A drawn knob set to a number ---


class Knob:
	"""A made-up drawn knob: a value, how far each size of step moves it, and the text shown around it."""

	def __init__(self, value, gains=None, low=0, high=100, sense=1, shows="{value:g}%", others=("Gain 12 dB", "Freq 440 Hz"),
			onlyAfterMove=False, twin=False):
		self.value, self.low, self.high, self.sense = value, low, high, sense
		self.gains = gains or {target.FINE: 1, target.STEP: 4, target.FAR: 16}
		self.shows, self.others, self.twin = shows, others, twin
		self.moved = not onlyAfterMove
		self.strokes = []

	def read(self):
		lines = list(self.others)
		if self.shows and self.moved:
			lines.append("Mix " + self.shows.format(value=self.value))
		if self.twin:
			lines.append("Wet " + self.shows.format(value=100 - self.value))
		return lines

	def stroke(self, direction, size):
		self.strokes.append((direction, size))
		before = self.value
		self.value = max(self.low, min(self.high, self.value + direction * self.sense * self.gains[size]))
		self.moved = True
		return self.value != before


for label, knob, wanted, percent, why, value, called in (
	("down to 35 from 80", Knob(80), 35, True, target.REACHED, 35, "Mix"),
	("up to 90 from 10", Knob(10), 90, True, target.REACHED, 90, "Mix"),
	("a knob that turns the other way", Knob(50, sense=-1), 35, True, target.REACHED, 35, "Mix"),
	("already there", Knob(35), 35, True, target.REACHED, 35, "Mix"),
	("steps of 5, asked for 37", Knob(50, gains={target.FINE: 5, target.STEP: 10, target.FAR: 20}), 37, True, target.NEAREST, 35, "Mix"),
	("no number shown", Knob(50, shows=""), 35, True, target.NO_NUMBER, 50, "Mix"),
	("a number only after it moves", Knob(60, onlyAfterMove=True), 35, True, target.REACHED, 35, "Mix"),
	("shown in dB, asked in percent", Knob(-6, shows="{value:g} dB", low=-60, high=6, others=()), 35, True, target.OTHER_UNIT, -6, "Mix"),
	("a plain number", Knob(3, shows="{value:g}", low=0, high=10, gains={target.FINE: 0.5, target.STEP: 1, target.FAR: 2}, others=()), 7, False, target.REACHED, 7, "Mix"),
	("at its end before the number", Knob(20, high=30), 80, True, target.STUCK, 30, "Mix"),
	# Two numbers change with every step: the one in the line that names the control is its own.
	("two numbers change, one is named", Knob(50, onlyAfterMove=True, twin=True, others=()), 35, True, target.REACHED, 35, "Mix"),
	("two numbers change, one is named, both shown", Knob(50, twin=True), 35, True, target.REACHED, 35, "Mix"),
	# Neither line names the control: which number is its own cannot be told, and it is left where it was.
	("two numbers change, none is named", Knob(50, onlyAfterMove=True, twin=True, others=()), 35, True, target.SEVERAL, 50, "Blend"),
):
	outcome = target.seek(wanted, percent, knob.read, knob.stroke, name=called)
	assert outcome["why"] == why and abs(knob.value - value) < 0.001, (label, outcome, knob.value)
	assert len(knob.strokes) <= target.MAX_STROKES and outcome["strokes"] <= target.MAX_STROKES, label
	said = target.text("Mix", wanted, percent, outcome)
	assert said.startswith("Mix") or said.startswith("No number") or said.startswith("Several numbers"), said
# What cannot be set is left where it was, and the user is told so.
knob = Knob(50, shows="")
assert "moved a little and back again" in target.text("Mix", 35, True, target.seek(35, True, knob.read, knob.stroke, name="Mix")) and knob.value == 50
knob = Knob(80)
said = target.text("Mix", 35, True, target.seek(35, True, knob.read, knob.stroke, name="Mix"))
assert said.startswith("Mix now shows 35 percent, which is what was asked for. It showed 80 percent before."), said
assert "read from the picture next to the control after every step" in said
knob = Knob(50, gains={target.FINE: 5, target.STEP: 10, target.FAR: 20})
assert "as near as it goes" in target.text("Mix", 37, True, target.seek(37, True, knob.read, knob.stroke))
# Stopping is honoured between steps.


def stopped():
	raise KeyboardInterrupt()


knob = Knob(80)
try:
	target.seek(35, True, knob.read, knob.stroke, check=stopped)
	raise AssertionError("the search went on after it was stopped")
except KeyboardInterrupt:
	assert knob.strokes == []
assert [item[:2] for item in target.numbers(["Mix 35%", "Gain -12.5 dB  Freq 440 Hz", "Ratio 4:1"])] == [
	(35.0, "%"), (-12.5, "dB"), (440.0, "Hz"), (4.0, ""), (1.0, "")]
assert target.numbers(["Mix 35%"])[0][2] == "mix #" and target.numbers(["Mix 36%"])[0][2] == "mix #"
assert target.question("Mix", 35, True).startswith("Set Mix to 35 percent with the mouse?")

# --- Going through an installer page after page ---

for said, expected in (
	("Uncheck any bundled promotional toolbars in this installer and click Next until the installation starts.",
		{"press": "Next", "until": "the installation starts", "uncheck": "bundled promotional toolbars", "offers": True}),
	("click Next until the installation starts", {"press": "Next", "until": "the installation starts", "uncheck": "", "offers": False}),
	("keep pressing Continue until it asks for my name", {"press": "Continue", "until": "it asks for my name", "uncheck": "", "offers": False}),
	("go through this installer for me", {"press": "Next", "until": "", "uncheck": "", "offers": False}),
	("step through this setup wizard and decline any offers", {"press": "Next", "until": "", "uncheck": "offers", "offers": True}),
):
	assert wizard.wish(said) == expected, (said, wizard.wish(said))
for said in ("click the Next button", "how do I click Next until it installs", "install Firefox", "open the installer", "Make NVDA talk faster", ""):
	assert wizard.wish(said) is None, (said, wizard.wish(said))
for name in ("Install the Ask Toolbar", "Also install McAfee WebAdvisor", "Set Yahoo as my default search engine", "Yes, install the free security scan",
		"Add the Shopping Assistant browser extension"):
	assert wizard.isOffer(name), name
for name in ("Create a desktop shortcut", "Launch the program when setup ends", "I accept the agreement", "Install for all users"):
	assert not wizard.isOffer(name), name
assert wizard.isOffer("Install the Bing Bar", {"uncheck": "the Bing bar"}) and not wizard.isOffer("Create a desktop shortcut", {"uncheck": "the Bing bar"})
assert wizard.isTerms("I accept the agreement") and wizard.isTerms("I Agree") and not wizard.isTerms("I do not accept the agreement")
assert wizard.isStart("Install") and wizard.isStart("&Install") and not wizard.isStart("Next >") and wizard.isEnd("Finish")
T = guide.Thing
assert wizard.named(T("Next >", "button"), "Next") and wizard.named(T("&Next", "button"), "next") and not wizard.named(T("Next steps", "link"), "Next")


class Installer:
	"""A made-up installer: pages of things; pressing a check box or radio button sets it, the page's button goes on."""

	def __init__(self, pages, program="setup"):
		self.pages, self.at, self.program, self.pressed = pages, 0, program, []

	def look(self):
		title, things = self.pages[self.at]
		return list(things), title, self.program

	def press(self, thing):
		self.pressed.append(thing.name)
		if thing.kind == "check box":
			thing.checked = not thing.checked
		elif thing.kind == "radio button":
			for other in self.pages[self.at][1]:
				if other.kind == "radio button":
					other.checked = other is thing
		elif thing.name.strip("&<> ").lower() in ("next", "i agree", "install", "continue") and self.at < len(self.pages) - 1:
			self.at += 1


def pages():
	return [
		("Setup - Welcome", [T("Next >", "button"), T("Cancel", "button")]),
		("Setup - License Agreement", [
			T("I accept the agreement", "radio button", checked=False), T("I do not accept the agreement", "radio button", checked=True),
			T("< Back", "button"), T("Next >", "button", usable=True), T("Cancel", "button")]),
		("Setup - Additional Tasks", [
			T("Create a desktop shortcut", "check box", checked=True), T("Install the Ask Toolbar", "check box", checked=True),
			T("Set Yahoo as my default search engine", "check box", checked=True), T("< Back", "button"), T("Next >", "button"), T("Cancel", "button")]),
		("Setup - Ready to Install", [T("< Back", "button"), T("Install", "button"), T("Cancel", "button")]),
		("Setup - Installing", [T("Cancel", "button")]),
	]


asked = []


def yes(question, choices):
	asked.append((question, list(choices)))
	return 0


wished = wizard.wish("Uncheck any bundled promotional toolbars in this installer and click Next until the installation starts.")
setup = Installer(pages())
said, pressed = wizard.walk(wished, setup.look, setup.press, yes)
# The offers were unchecked, the shortcut was left alone, the terms and the installation were asked about.
assert setup.pressed == ["Next >", "I accept the agreement", "Next >", "Install the Ask Toolbar", "Set Yahoo as my default search engine", "Next >", "Install"], setup.pressed
assert pressed == setup.pressed and setup.at == 4
assert len(asked) == 2 and "asks you to accept terms: \"I accept the agreement\"" in asked[0][0] and asked[0][1] == ["Yes, accept and go on", "No, stop here"], asked
assert "There is no Next button here; the button is Install." in asked[1][0] and "may not be possible to take back" in asked[1][0], asked[1]
assert "Page 3, Setup - Additional Tasks. Check boxes: Create a desktop shortcut (checked), Install the Ask Toolbar (checked)" in said, said
assert "unchecked Install the Ask Toolbar; unchecked Set Yahoo as my default search engine; pressed Next >." in said, said
assert "pressed Install, as you said. The window now says that it is under way. VisionClaw stops here." in said, said
assert wizard.startQuestion(wished, "Setup - Welcome").startswith("Press Next on page after page of this window, Setup - Welcome, until the installation starts?")
assert "never accepts licence terms without asking you" in wizard.startQuestion(wished, "")

# The user does not accept the terms: nothing more is pressed.
setup = Installer(pages())
said, pressed = wizard.walk(wished, setup.look, setup.press, lambda question, choices: 1 if "accept terms" in question else 0)
assert setup.pressed == ["Next >"] and "you did not, so VisionClaw stopped here" in said, (setup.pressed, said)
# The user says no to the installation: it stops before the button.
setup = Installer(pages())
said, pressed = wizard.walk(wished, setup.look, setup.press, lambda question, choices: 1 if "Press Install?" in question else 0)
assert setup.pressed[-1] == "Next >" and "Install" not in setup.pressed and "you said no, so VisionClaw stopped before it" in said, (setup.pressed, said)
# Without being asked to, no box is unchecked.
setup = Installer(pages())
plain = wizard.wish("click Next until the installation starts")
said, pressed = wizard.walk(plain, setup.look, setup.press, yes)
assert "Install the Ask Toolbar" not in setup.pressed and "unchecked" not in said, setup.pressed
# An installer whose licence page has a button "I Agree" in place of Next.
setup = Installer([
	("Welcome", [T("Next >", "button")]), ("License Agreement", [T("< Back", "button"), T("I Agree", "button"), T("Cancel", "button")]),
	("Completing Setup", [T("Finish", "button")])])
del asked[:]
said, pressed = wizard.walk(plain, setup.look, setup.press, yes)
assert setup.pressed == ["Next >", "I Agree"] and "accept terms: \"I Agree\"" in asked[0][0], (setup.pressed, asked)
assert "There is no Next button any more; the page has Finish, which VisionClaw did not press." in said, said
# A box that does not take the press is said to be still checked.


class Stubborn(Installer):
	def press(self, thing):
		if thing.kind == "check box":
			self.pressed.append(thing.name)
			return
		Installer.press(self, thing)


setup = Stubborn(pages()[2:])
said, pressed = wizard.walk(wished, setup.look, setup.press, yes)
assert "pressed Install the Ask Toolbar to uncheck it, but it does not show as unchecked: check it yourself" in said, said
# A press that changes nothing, twice: it stops and says the page may want something first.
setup = Installer([("Your details", [T("Next >", "button"), T("Name", "edit field")])])
said, pressed = wizard.walk(plain, setup.look, setup.press, yes)
assert setup.pressed == ["Next >", "Next >"] and "changed nothing, so VisionClaw stopped" in said, (setup.pressed, said)
# Another program comes to the front: it stops there.


class Elsewhere(Installer):
	def press(self, thing):
		Installer.press(self, thing)
		self.program = "consent"


setup = Elsewhere(pages())
said, pressed = wizard.walk(plain, setup.look, setup.press, yes)
assert setup.pressed == ["Next >"] and "Another program is in front now, consent." in said and "only you can answer" in said, said
# What the user waits for shows: it stops before pressing.
setup = Installer([("Step 1", [T("Continue", "button")]), ("Step 2", [T("Continue", "button")]), ("Your name", [T("Name", "edit field"), T("Continue", "button")])])
said, pressed = wizard.walk(wizard.wish("keep pressing Continue until it asks for my name"), setup.look, setup.press, yes)
assert setup.pressed == ["Continue", "Continue"] and "This is what you were waiting for" in said, (setup.pressed, said)
# A long row of pages: a check-in on the way, and never more than the most pages.
long = Installer([(f"Page {index}", [T("Next", "button")]) for index in range(40)])
del asked[:]
said, pressed = wizard.walk(plain, long.look, long.press, yes)
assert len(long.pressed) == wizard.MAX_PAGES and [question for question, _c in asked if "Go on pressing Next?" in question], (len(long.pressed), asked)
long = Installer([(f"Page {index}", [T("Next", "button")]) for index in range(40)])
said, pressed = wizard.walk(plain, long.look, long.press, lambda question, choices: 1)
assert len(long.pressed) == wizard.CHECK_AFTER and "Stopped there, as you said." in said
# A page that offers something with a button to decline: said, not pressed.
setup = Installer([("Special offer: try WebCompanion free", [T("Accept", "button"), T("Decline", "button")])])
said, pressed = wizard.walk(wished, setup.look, setup.press, yes)
assert setup.pressed == [] and "To refuse, say: click Decline." in said, said

# --- A form's fields outlined in red, said with the rest of form_trouble ---

nodes = [{"role": "EDITABLETEXT", "name": "Email address", "states": [], "start": 10}, {"role": "EDITABLETEXT", "name": "Postcode", "states": [], "start": 20}]
found = pageview.trouble(nodes)
said = pageview.troubleText(found, moved=True, red=nodes[:1], written=["Please check this field"], looked=2)
assert "In the picture of the page, 1 field is outlined in red, which is how a page usually marks what is wrong: " in said, said
assert "Written in red in the picture: Please check this field." in said and "NVDA's reading position is now on the first of them, Email address." in said, said
assert "measured from the colours of the 2 fields that are on the screen now" in said, said
said = pageview.troubleText(found, red=nodes, looked=2)
assert "2 fields are outlined in red" in said and "reading position" not in said, said
# Nothing red: the user is told that, and what else it may be.
said = pageview.troubleText(found, looked=2)
assert "No field on the screen is outlined in red and nothing is written in red there." in said, said
# The picture could not be looked at: what was said before this work.
assert "The reason may be shown only as a picture or by a colour" in pageview.troubleText(found), pageview.troubleText(found)
assert pageview.redText([], [], 0) == []

# --- Which job each of the article's own sentences goes to, by plain code alone ---

import json  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402

from visionClaw.claw import docformat, humancheck, lookup, planner, seats, shopping, understand  # noqa: E402


def routed(said):
	"""The parts a request is split into by plain rules, and the job the first pattern names for each."""
	whole = planner.hint(said)
	if whole in planner._WHOLE or guide.asks(said):
		return [whole]
	parts = planner.plainSplit(said) or [said]
	jobs, before = [], None
	for part in parts:
		before = planner.hint(part, before)
		jobs.append(before)
	return jobs


for said, jobs in (
	("Make NVDA only speak words when I type.", ["change_setting"]),
	("Stop reading every punctuation mark while I review this article.", ["change_setting"]),
	("Make NVDA talk faster.", ["change_setting"]),
	("Navigate this Logitech Options+ window and remap my top function keys to standard F1 through F12 keys.", ["work_through"]),
	("Uncheck any bundled promotional toolbars in this installer and click Next until the installation starts.", ["step_through"]),
	# Inside a launcher: the Settings menu is a thing of that program, and both options are controls of it.
	("Click the Play button in this launcher, open the Settings menu, and turn on UI narration and subtitles.", ["click", "click", "set_control"]),
	("Read my current character stats, equipped items, and available skill points from the inventory grid on screen.", ["describe"]),
	("Put my focus in the first required field that I still need to complete.", ["form_trouble"]),
	("Check why this form did not submit, tell me the error message, and jump my cursor straight to the field with the red error outline.", ["form_trouble"]),
	# The name of the tool has an "and" in it, and the label a comma: neither splits the request.
	("Select the Fill and Sign tool, click directly on the blank line next to 'Applicant Full Name,' and type my name.", ["click", "fill_blank"]),
	("Find the dotted line labeled 'Authorized Signature' at the bottom of the page and click there so I can place my digital signature.", ["fill_blank"]),
	("Open the preset browser inside this VST plugin and select the 'Warm Vocal Reverb' preset.", ["click", "click"]),
	# A knob that is to show a number is set to it; it is not only taken hold of for the arrow keys.
	("Turn the graphical Mix knob down to 35 percent and click the Bypass toggle.", ["set_control", "click"]),
	("Read the text inside the latest image posted in this WhatsApp chat and explain the visual joke.", ["look_picture"]),
	("Look at the screenshot my coworker just shared, what error code is highlighted in the dialog box?", ["look_picture"]),
	("Format this entire Word document in APA 7th edition style: set the font to 12-point Times New Roman, double-space all paragraphs, "
		"and apply a 0.5-inch hanging indent to the References section.", ["format_document"]),
	("Check the visual layout of my resume and tell me if everything fits cleanly onto a single page without any overlapping text boxes.", ["check_layout"]),
	("Locate and click the 'Verify you are human' Cloudflare Turnstile checkbox on screen.", ["human_check"]),
	("Select all squares with traffic lights.", ["human_check"]),
	("Look at the product photo, is this jacket navy blue or solid black, and does it have any printed logos?", ["look_picture"]),
	("Click the Medium size swatch, select the dark blue color option, and confirm the storage capacity is set to 256GB.", ["pick_option", "pick_option", "pick_option"]),
	("Find an available window seat ahead of the wing on this aircraft map and click it to reserve my seat.", ["pick_seat"]),
	("Look at the room gallery photos and tell me whether the balcony overlooks the ocean or the mountains.", ["look_picture"]),
	("Pick March 14 2027 as my check-in date in this calendar.", ["pick_date"]),
):
	assert routed(said) == jobs, (said, routed(said))
	# The words are understood before anything is planned (claw/understand.py): the job is the same afterwards.
	if said.startswith(("Make NVDA only", "Stop reading", "Make NVDA talk")):
		continue
	understood = understand.Grammar(None).read(said).text
	assert routed(understood) == jobs, (said, understood, routed(understood))
# The two parts of the request about the form that is only a picture, in the user's own words.
assert planner.plainSplit("Select the Fill and Sign tool, click directly on the blank line next to 'Applicant Full Name,' and type my name.") == [
	"Select the Fill and Sign tool", "Click directly on the blank line next to 'Applicant Full Name,' and type my name"]

# "Only speak words when I type" is two settings of NVDA: typed words on, typed characters off. The words are
# understood that way by plain code (claw/understanding.md), the user is told so, and each setting is its own part.
from visionClaw.claw import understand  # noqa: E402

reading = understand.Grammar(None).read("Make NVDA only speak words when I type.")
assert reading.text == "Make NVDA turn on speak typed words and turn off speak typed characters." and reading.said, reading.text
assert planner.plainSplit(reading.text) == ["Make NVDA turn on speak typed words", "Turn off speak typed characters"]
assert [planner.hint(part) for part in planner.plainSplit(reading.text)] == ["change_setting", "change_setting"]

# What the new jobs must leave alone: each of these keeps the job it had before.
for said, job in (
	("which model should I use for describing pictures", "model_advice"), ("should I switch to a smaller model", "model_advice"),
	("Right-click the Options button.", "click"), ("choose the second option", "click"), ("describe this picture", "describe"),
	("Coach me on reading the current line.", "coach"), ("turn the volume up to 60 percent", "change_setting"),
	("open my pictures folder", "open_thing"), ("how do I double space in Word", "explain_keys"),
):
	assert planner.hint(said) == job, (said, planner.hint(said))
for said in ("check the box next to I agree", "press verify", "select all", "turn the slider up", "describe the picture", "open cloudflare.com"):
	assert not humancheck.about(said), said
for said in ("change the font size to 12", "what colour is this", "set the window size", "one of the boxes on this form has a red border, take me to it",
		"navigate this scanner app and set it to scan in colour", "Right-click the Options button."):
	assert shopping.optionWish(said) is None, said
for said in ("open the window", "how do I pick a seat", "click the Next button"):
	assert seats.seatWish(said) is None, said
for said in ("what font is this", "how do I double-space in Word", "how is this page laid out"):
	assert docformat.wish(said) is None and docformat.layoutWish(said) is None, said

# Every new job is one whose words are sure, is offered only where its own function finds it in the words, and has
# its tool kept away from VisionClaw's own windows where it works the window in front.
NEW_JOBS = ("look_picture", "fill_blank", "step_through", "format_document", "check_layout", "human_check", "pick_option", "pick_seat")
for job in NEW_JOBS:
	assert job in planner.RECIPES and planner.RECIPES[job][2] == (job,), job
	assert job in planner._SURE and job in planner._NEEDS, job
	assert planner._NEEDS[job]("Make NVDA speak a little faster") is None, job
for tool in ("fill_blank", "step_through", "format_document", "human_check", "pick_option", "pick_seat"):
	assert tool in guide.OFF_LIMITS, tool

# The two evaluation sets written for these jobs, each before it was run: how many requests plain code alone names
# rightly. The first set stood at 41 of 49 when it was first run; three rules were corrected against it, and the
# second set, written after that and before it was run, stood at 28 of 30; two more rules were corrected against
# it. Lower numbers than these mean a rule got worse.
LEAST = {"requests-ten": 43, "requests-ten2": 30}
here = os.path.dirname(os.path.abspath(__file__))
for name, least in LEAST.items():
	with open(os.path.join(here, "eval", name + ".json"), encoding="utf-8") as f:
		data = json.load(f)["requests"]
	right = 0
	for item in data:
		assert all(job in planner.RECIPES for part in item["expect"] for job in part), item
		got = routed(item["request"])
		right += len(got) == len(item["expect"]) and all(job in wanted for job, wanted in zip(got, item["expect"]))
	assert right >= least, f"{name}: {right} named rightly, before {least}"

# --- The notes looked things up in: one answer a section, about working the computer by keyboard and speech ---

with open(os.path.join(here, "..", "addon", "globalPlugins", "visionClaw", "claw", "knowledge", "visionclaw-sighted-help.md"), encoding="utf-8") as f:
	note = f.read()
sections = re.split(r"\n## ", note.split("\n# ", 1)[1])[1:]
assert len(sections) == 11, len(sections)
for section in sections:
	heading, _sep, body = section.partition("\n")
	assert len(body) <= 400, (heading, len(body))
	assert not re.search(r"\b(click the (blue|red|green)|look at the screen|as you can see|hover over)\b", body, re.IGNORECASE), heading
	assert "e.g." not in body and "for example" not in body.lower(), heading
gate = lookup.NOTES["visionclaw-sighted-help"][2]
for question in ("how do I fill in a scanned form", "can you get me through an installer", "can VisionClaw format my paper in APA",
		"how do I get past a captcha", "can you pick a window seat for me", "can you type my card number"):
	assert gate.search(question), question
for question in ("How do I read the title of this window?", "What is browse mode?", "How do I copy text?", "how do I change the speech rate"):
	assert not gate.search(question), question

print("OK")
