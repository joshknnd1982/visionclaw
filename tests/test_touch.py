# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Fingers, pressure, and games that read the mouse directly, with plain Python.

What a request in words means as a touch gesture or as a press with pressure; the places every finger and
the pen pass through; what stands in for a gesture where a program takes no touch; what a request to turn
or look means as movements of the mouse itself; and a program's own pointer brought to a place by counting
from the corner of its window, with its speed measured from pictures.
The game is a drawing made by this test: it has a pointer of its own that follows the mouse's movement at a
speed of its own. Nothing here shows how a real program or a real game answers.

  python tests/test_touch.py
"""
import json
import math
import os
import tempfile

from PIL import Image, ImageDraw

import harness  # noqa: F401
from visionClaw.claw import direct, planner, pointer, scrolling, touch, working

BOX = (100, 100, 900, 700)
PLACE = (500, 400)

# --- Which touch gesture the words mean ---

pinch = touch.touchOf("Pinch the map")
assert pinch["kind"] == touch.PINCH and pinch["fingers"] == 2 and pinch["text"] == "a pinch with two fingers, as for zooming out"
spread = touch.touchOf("spread three fingers on the photo")
assert spread["kind"] == touch.SPREAD and spread["fingers"] == 3
assert touch.touchOf("pinch it out")["kind"] == touch.SPREAD and touch.touchOf("pinch open the picture")["kind"] == touch.SPREAD
# Zooming is a touch only where the words speak of fingers; else it is the wheel's.
assert touch.touchOf("zoom in with two fingers")["kind"] == touch.SPREAD and touch.touchOf("zoom out with two fingers")["kind"] == touch.PINCH
assert touch.touchOf("zoom in") is None
swipe = touch.touchOf("Swipe left with three fingers")
assert (swipe["kind"], swipe["fingers"], swipe["direction"]) == (touch.SWIPE, 3, "left"), swipe
assert swipe["text"] == "a swipe to the left with three fingers"
assert touch.touchOf("two-finger swipe up")["direction"] == "up" and touch.touchOf("scroll down with 2 fingers")["fingers"] == 2
# A swipe, a tap and a hold with no word of fingers or touching are the mouse's.
assert touch.touchOf("swipe left on the card") is None and touch.touchOf("tap the OK button") is None
assert touch.touchOf("press and hold the Record button") is None
turn = touch.touchOf("Rotate the photo 45 degrees anticlockwise with two fingers")
assert (turn["kind"], turn["degrees"], turn["fingers"]) == (touch.ROTATE, -45, 2), turn
assert touch.touchOf("turn the map with two fingers")["degrees"] == 90
assert touch.touchOf("twist it a half turn with two fingers")["degrees"] == 180
tap = touch.touchOf("Double tap the Start icon")
assert (tap["kind"], tap["taps"], tap["fingers"]) == (touch.TAP, 2, 1) and tap["text"] == "a double tap with one finger"
assert touch.touchOf("tap the picture with two fingers")["fingers"] == 2 and touch.touchOf("two-finger tap")["taps"] == 1
hold = touch.touchOf("Touch and hold the Record button for 2 seconds")
assert (hold["kind"], hold["seconds"]) == (touch.HOLD, 2.0) and hold["text"] == "a touch with one finger, held for 2 seconds"
assert touch.touchOf("long press with a finger")["seconds"] == touch.HOLD_DEFAULT
# How far, how fast and how many: within limits.
assert touch.touchOf("pinch a little")["size"] < touch.touchOf("pinch")["size"] < touch.touchOf("pinch a lot")["size"]
assert touch.touchOf("swipe left with nine fingers") is None or touch.touchOf("swipe left with nine fingers")["fingers"] <= touch.MAX_FINGERS
assert touch.touchOf("flick up with two fingers")["pace"] < touch.touchOf("swipe up with two fingers")["pace"]
assert touch.fingersOf("with both fingers") == 2 and touch.fingersOf("a 4-finger swipe") == 4 and touch.fingersOf("swipe") is None

# --- Where the fingers go ---


def spreadOf(frame):
	return math.dist(frame[0], frame[1])


frames = touch.strokes(pinch, PLACE, BOX)[0]["frames"]
assert all(len(frame) == 2 for frame in frames) and len(frames) == touch.STEPS + 1
# A pinch brings the fingers together around the place; a spread takes them apart.
assert spreadOf(frames[0]) > 3 * spreadOf(frames[-1]) > 0
middle = ((frames[0][0][0] + frames[0][1][0]) / 2, (frames[0][0][1] + frames[0][1][1]) / 2)
assert abs(middle[0] - PLACE[0]) <= 1 and abs(middle[1] - PLACE[1]) <= 1, middle
apart = touch.strokes(touch.touchOf("spread two fingers"), PLACE, BOX)[0]["frames"]
assert spreadOf(apart[-1]) > 3 * spreadOf(apart[0])
# Each step is small: a program follows fingers that move, not ones that jump.
assert max(math.dist(a[0], b[0]) for a, b in zip(frames, frames[1:])) < 12
# Three fingers stand in a triangle around the place.
three = touch.strokes(touch.touchOf("pinch with three fingers"), PLACE, BOX)[0]["frames"]
assert len(three[0]) == 3 and len(set(three[0])) == 3
# A swipe: the fingers lie side by side across the way they move, and all move the same.
moved = touch.strokes(swipe, PLACE, BOX)[0]["frames"]
assert len(moved[0]) == 3 and len({y for _x, y in moved[0]}) == 3 and len({x for x, _y in moved[0]}) == 1
assert all(last[0] < first[0] and last[1] == first[1] for first, last in zip(moved[0], moved[-1]))
assert moved[0][1][0] - moved[-1][1][0] == round(0.25 * 800)  # a quarter of the window's width
# A turn: both fingers keep their distance from the middle and go round it by the angle asked for.
around = touch.strokes(turn, PLACE, BOX)[0]["frames"]
radius = [math.dist(frame[0], PLACE) for frame in around]
assert max(radius) - min(radius) <= 2
angle = math.degrees(math.atan2(around[-1][0][1] - PLACE[1], around[-1][0][0] - PLACE[0]))
assert abs(angle - (-45)) < 3, angle  # anticlockwise is upwards on the screen
# A double tap is two short strokes in the same place; a hold repeats its place, so Windows does not give it up.
taps = touch.strokes(tap, PLACE, BOX)
assert len(taps) == 2 and taps[0]["frames"][0] == [PLACE] and len(taps[0]["frames"]) == 3
held = touch.strokes(hold, PLACE, BOX)[0]
assert len(held["frames"]) == round(2.0 / touch.REST_EVERY) and set(map(tuple, held["frames"])) == {(PLACE,)}
# Nothing leaves the window, even from its corner, and on a screen scaled to twice the fingers lie twice as far apart.
corner = touch.strokes(touch.touchOf("spread two fingers a lot"), (105, 105), BOX)[0]["frames"]
assert all(BOX[0] < x < BOX[2] and BOX[1] < y < BOX[3] for frame in corner for x, y in frame)
plain = touch.strokes(touch.touchOf("tap with two fingers"), PLACE, BOX, 1.0)[0]["frames"][0]
scaled = touch.strokes(touch.touchOf("tap with two fingers"), PLACE, BOX, 2.0)[0]["frames"][0]
assert spreadOf(scaled) == 2 * spreadOf(plain) == 2 * touch.FINGER_GAP

# --- What stands in where a program takes no touch ---

assert touch.instead(pinch) == ("zoom", "out") and touch.instead(spread) == ("zoom", "in")
# Two fingers that go up push what is shown up, which is scrolling down.
assert touch.instead(touch.touchOf("swipe up with two fingers")) == ("scroll", scrolling.DOWN)
assert touch.instead(touch.touchOf("swipe left with two fingers")) == ("scroll", scrolling.RIGHT)
# Nothing stands in for a turn, a tap, or a swipe with three fingers; that is said, not hidden.
assert touch.instead(turn) is None and touch.instead(tap) is None and touch.instead(swipe) is None
assert touch.insteadText(("zoom", "in")) == "the Control key and the mouse wheel, which make most views larger"
assert touch.insteadText(("scroll", "down")) == "the mouse wheel, turned down" and touch.insteadText(None) == ""

# --- Pressure ---

assert touch.pressureOf("press hard on the pad") == (0.8, 0.8) and touch.pressureOf("press lightly") == (0.25, 0.25)
assert touch.pressureOf("at 70 percent pressure") == (0.7, 0.7) and touch.pressureOf("pressure of 30") == (0.3, 0.3)
assert touch.pressureOf("press as hard as it can") == (1.0, 1.0) and touch.pressureOf("press very lightly on it") == (0.1, 0.1)
assert touch.pressureOf("a line from light to hard pressure") == (0.25, 0.8)
assert touch.pressureOf("from 20 to 90 percent pressure") == (0.2, 0.9)
assert touch.pressureOf("draw with the pressure rising") == (0.15, 1.0) and touch.pressureOf("pressure fading") == (1.0, 0.15)
# Words that say nothing of how hard: no pressure is made up.
assert touch.pressureOf("press the OK button") is None and touch.pressureOf("click the hard drive icon") is None
assert touch.pressureText((0.8, 0.8)) == "80 percent of full pressure"
assert touch.pressureText((0.15, 1.0)) == "pressure rising from 15 to 100 percent"
assert touch.units(1.0) == 1024 and touch.units(0.5) == 512 and touch.units(0.0) == 1  # a pen that touches never reports nothing
press = touch.penOf("Press the pad at 70 percent pressure for 2 seconds")
assert press["gesture"] is None and press["seconds"] == 2.0 and press["tool"] == touch.PEN
assert press["text"] == "a press for 2 seconds with the pen, at 70 percent of full pressure", press["text"]
line = touch.penOf("Draw a line to the right with the pressure rising")
assert line["gesture"]["strokes"] == [[(0.0, 0.0), (1.0, 0.0)]] and line["pressure"] == (0.15, 1.0)
assert touch.penOf("press firmly with a finger")["tool"] == touch.FINGER
assert touch.penOf("erase a zigzag with the pen, firmly")["eraser"] and not press["eraser"]
assert touch.penOf("press the button") is None and touch.penOf("draw a circle") is None
# The percent that says how hard is not taken for how long the line is.
assert touch.penOf("draw a line left at 90 percent pressure")["gesture"]["size"] == pointer.GESTURE_SHARE
# A press stays in its place; a line passes through small steps, and the pressure changes evenly along all of it.
points = touch.penStrokes(press, PLACE, BOX)[0]
assert {(x, y) for x, y, _p in points} == {PLACE} and {round(p, 2) for _x, _y, p in points} == {0.7}
path = touch.penStrokes(line, PLACE, BOX)[0]
assert path[0][:2] == PLACE and path[-1][0] > PLACE[0] and path[-1][1] == PLACE[1]
shares = [share for _x, _y, share in path]
assert shares[0] == 0.15 and abs(shares[-1] - 1.0) < 1e-9 and shares == sorted(shares)
cross = touch.penStrokes(touch.penOf("draw a cross, from light to hard pressure"), PLACE, BOX)
assert len(cross) == 2 and cross[0][-1][2] < cross[1][0][2] <= cross[1][-1][2]  # it goes on rising over both strokes

# --- A game whose view the mouse turns ---

assert direct.turnOf("Turn left") == {"dx": -direct.SOME, "dy": 0, "guess": True, "text": "300 steps to the left"}
assert direct.turnOf("look up a little")["dy"] == -direct.LITTLE and direct.turnOf("turn right a lot")["dx"] == direct.LOT
assert direct.turnOf("turn around")["dx"] == direct.AROUND and direct.turnOf("look behind you")["dx"] == direct.AROUND
exact = direct.turnOf("turn right 500 steps")
assert exact["dx"] == 500 and not exact["guess"]  # a number of steps is the user's own, and no guess
assert direct.turnOf("turn 90 degrees to the left")["dx"] == -600
# What is kept for the program makes every guess larger or smaller.
assert direct.turnOf("turn left", 0.5)["dx"] == -150 and direct.turnOf("turn right 500 steps", 0.5)["dx"] == 500
# Other things are turned up and looked up, and they are not meant.
for words in ("Turn up the volume", "turn down the speech rate", "look at this window", "turn the page", "click Start"):
	assert direct.turnOf(words) is None, words
# A movement is made of small pieces that add up to exactly the whole.
pieces = direct.chunks(-300, 80)
assert sum(x for x, _y in pieces) == -300 and sum(y for _x, y in pieces) == 80
assert max(abs(x) for x, _y in pieces) <= direct.CHUNK and len(pieces) == 13
assert direct.chunks(0, 0) == [] and direct.chunks(5, 0) == [(5, 0)]

# --- What the words say about how a program uses the mouse ---

assert direct.wayOf("This game has its own mouse pointer") == ("way", direct.POINTER)
assert direct.wayOf("this game reads the mouse directly") == ("way", direct.POINTER)
assert direct.wayOf("The mouse turns the view here") == ("way", direct.VIEW)
assert direct.wayOf("it is a first-person game") == ("way", direct.VIEW)
assert direct.wayOf("Use the normal mouse pointer again") == ("way", direct.PLAIN)
assert direct.wayOf("stop using direct mouse movement") == ("way", direct.PLAIN)
assert direct.wayOf("Direct mouse movement is too fast") == ("speed", direct.SLOWER)
assert direct.wayOf("it does not turn far enough") == ("speed", direct.FASTER)
assert direct.wayOf("measure the game's pointer") == ("measure", None)
assert direct.wayOf("how does this game use the mouse") is None  # only asked about
for way in direct.WAYS:
	assert direct.wayText(way)
# Windows' own facts: a hidden pointer kept inside the window is what a game does that reads the mouse itself.
assert direct.reads({"showing": False, "confined": True, "inside": True}) and not direct.reads({"showing": True})
assert "read the mouse directly" in direct.stateText({"showing": False, "confined": True, "inside": True})
assert direct.stateText({"showing": True, "confined": False, "inside": False}) == "" and direct.stateText(None) == ""
assert "cannot be worked this way" in direct.ADVICE  # what it cannot do is said

# --- A game that draws a pointer of its own ---


class Game:
	"""A window that takes no notice of Windows' pointer: it draws its own, which follows how far the mouse
	itself moves, at the game's own speed, and stops at the window's edges."""

	def __init__(self, speed, box=BOX, start=(450, 330)):
		self.speed, self.box = speed, box
		self.x, self.y = float(start[0]), float(start[1])
		self.sent = []

	def send(self, dx, dy):
		self.sent.append((dx, dy))
		left, top, right, bottom = self.box
		self.x = max(left, min(right - 1, self.x + dx * self.speed))
		self.y = max(top, min(bottom - 1, self.y + dy * self.speed))

	def grab(self, box):
		image = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (20, 30, 60))
		draw = ImageDraw.Draw(image)
		draw.rectangle((300, 200, 500, 260), fill=(90, 90, 110))  # a button that never changes
		x, y = round(self.x) - box[0], round(self.y) - box[1]
		draw.polygon(((x, y), (x + 11, y + 11), (x + 5, y + 12), (x, y + 17)), fill=(255, 255, 255))
		return image

	def at(self):
		return round(self.x), round(self.y)


def still(seconds):
	pass


# Pushed into the corner, it is there whatever its speed; from there every place is a count of steps.
for speed in (1.0, 0.5, 2.0):
	game = Game(speed)
	tracker = direct.Tracker(game.send, BOX, speed, pause=still)
	tracker.goTo(640, 480)
	assert abs(game.at()[0] - 640) <= 2 and abs(game.at()[1] - 480) <= 2, (speed, game.at())
	tracker.goTo(200, 150)
	tracker.goTo(820, 650)
	assert abs(game.at()[0] - 820) <= 3 and abs(game.at()[1] - 650) <= 3, (speed, game.at())
	assert (tracker.x, tracker.y) == game.at() or math.dist((tracker.x, tracker.y), game.at()) <= 3
	assert max(abs(dx) for dx, _dy in game.sent) <= direct.HOME_CHUNK
# With the wrong speed the pointer lands beside the place: that is why it is measured.
game = Game(1.6)
tracker = direct.Tracker(game.send, BOX, 1.0, pause=still)
tracker.goTo(640, 480)
assert abs(game.at()[0] - 640) > 100
# Measured from three pictures: where the picture changed tells where the pointer was, and so how fast it is.
for speed in (0.5, 1.0, 1.6, 2.5):
	game = Game(speed)
	tracker = direct.Tracker(game.send, BOX, 1.0, game.grab, pause=still, measure=True)
	tracker.goTo(640, 480)
	assert tracker.measured and abs(tracker.speed - speed) < 0.06, (speed, tracker.speed)
	assert abs(game.at()[0] - 640) <= 4 and abs(game.at()[1] - 480) <= 4, (speed, game.at())
# A picture in which more than a pointer changes, or nothing does, measures nothing; the speed stays as it was.
game = Game(1.0)
tracker = direct.Tracker(game.send, BOX, 1.3, lambda box: Image.new("RGB", (800, 600), "black"), pause=still)
tracker.home()
assert not tracker.measure() and tracker.speed == 1.3 and not tracker.measured
flip = [0]


def flashing(box):
	flip[0] += 1
	return Image.new("RGB", (800, 600), "white" if flip[0] % 2 else "black")


tracker = direct.Tracker(game.send, BOX, 1.3, flashing, pause=still)
tracker.home()
assert not tracker.measure() and tracker.speed == 1.3
assert direct.Tracker(game.send, BOX, 99).speed == direct.SPEED_MOST and direct.Tracker(game.send, BOX, None).speed == 1.0

# --- What is found out about a program is kept as data ---

folder = tempfile.mkdtemp(prefix="vcways-")
path = os.path.join(folder, "appways.json")
ways = direct.AppWays(path)
assert ways.mouse("doom") == direct.PLAIN and ways.speed("doom") == 1.0 and ways.lines() == []
ways.set("doom", "mouse", direct.VIEW)
ways.set("doom", "speed", 0.7)
ways.set("maps", "touch", {"pinch": "the mouse wheel"})
again = direct.AppWays(path)
assert again.mouse("doom") == direct.VIEW and again.speed("doom") == 0.7
assert again.lines() == [
	f"In doom, {direct.wayText(direct.VIEW)}.", "In maps, pinch is done with the mouse wheel."], again.lines()
assert json.load(open(path, encoding="utf-8")) == {"doom": {"mouse": "view", "speed": 0.7}, "maps": {"touch": {"pinch": "the mouse wheel"}}}
again.set("doom", "mouse", None)
again.set("doom", "speed", None)
assert again.mouse("doom") == direct.PLAIN and "doom" not in json.load(open(path, encoding="utf-8"))
assert again.forget("maps") and not again.forget("maps") and again.lines() == []
# A file that is broken, or holds something else, is nothing kept; and a made-up way is the usual one.
with open(path, "w", encoding="utf-8") as f:
	f.write("[1, 2")
assert direct.AppWays(path).lines() == []
broken = direct.AppWays(path)
broken.set("x", "mouse", "sideways")
broken.set("x", "speed", "fast")
assert broken.mouse("x") == direct.PLAIN and broken.speed("x") == 1.0

# --- The words point to the right job, and a model's impossible choice is corrected ---

HINTS = {
	"Pinch the map": "touch", "Spread two fingers on the photo": "touch", "Swipe left with three fingers": "touch",
	"Zoom in with two fingers": "touch", "Rotate the photo with two fingers": "touch",
	"Double tap the Start icon": "touch", "Touch and hold the Record button": "touch",
	"Press hard on the drum pad": "pressure", "Draw a line to the right with the pressure rising": "pressure",
	"Press the pad at 70 percent pressure for 2 seconds": "pressure", "Draw a circle with the pen, lightly": "pressure",
	"Turn left": "turn_view", "Look up a little": "turn_view", "Turn around": "turn_view", "Look down": "turn_view",
	"This game has its own mouse pointer": "mouse_way", "The mouse turns the view here": "mouse_way",
	"Direct mouse movement is too fast": "mouse_way", "Use the normal mouse pointer again": "mouse_way",
	# What was there before still goes where it went.
	"Turn up the volume": "change_setting", "Swipe left on the Options button": "gesture",
	"Press and hold the New Game button for 2 seconds": "click", "Zoom in": "scroll",
	"Click the New Game button 5 times": "timed_click", "Look at this window": "describe",
	"Turn off the typing echo": "change_setting", "look up a word for me on the web": "search_web",
	"Draw a circle in this window": "gesture", "Hover over the Options button": "click",
}
for words, recipe in HINTS.items():
	assert planner.hint(words) == recipe, (words, planner.hint(words))
for recipe in ("touch", "pressure", "turn_view", "mouse_way"):
	assert recipe in planner.RECIPES and len(planner.RECIPES[recipe][2]) == 1, recipe
# A model that sends "press and hold the button" to the touch, or "turn up the volume" to the view, is corrected:
# plain code can tell that the words name no touch and no turn.
assert planner.fitted("touch", "Press and hold the New Game button for 2 seconds", "click") == "click"
assert planner.fitted("pressure", "Click the Options button", "click") == "click"
assert planner.fitted("turn_view", "Turn up the volume", "change_setting") == "change_setting"
assert planner.fitted("touch", "Pinch the map", "touch") == "touch"
assert planner.fitted("turn_view", "Turn left", "turn_view") == "turn_view"

# --- How a control is worked: fingers, pressure, and a view that follows the mouse ---

for name, way in (
	("Pinch to zoom", working.TOUCH), ("Use two fingers to move the map", working.TOUCH),
	("Swipe with three fingers to switch", working.TOUCH), ("Pressure-sensitive pad", working.PRESSURE),
	("The harder you press, the louder", working.PRESSURE), ("Move the mouse to look around", working.AIM),
	("Mouse look", working.AIM),
	# What was known before is still known, and an everyday name says nothing.
	("Hold to record", working.HOLD), ("Swipe to unlock", working.GESTURE), ("Touch up paint", None), ("Pressure", None),
	("Look up", None),
):
	assert working.bySaid({"name": name}) == way, (name, working.bySaid({"name": name}))
for way, words in (
	(working.TOUCH, "touches the screen for you as fingers would"), (working.PRESSURE, "presses as a pen would"),
	(working.AIM, "moves the mouse itself"),
):
	assert working.remedy(way, True) == working.ADVICE and working.remedy(way, False) == working.ADVICE
	assert words in working.adviceFor(way), way
	assert way in working.SPECIAL and f"{way}:" in working.VISION_SYSTEM and way in working.CODER_SYSTEM, way
# What each cannot do is said in plain words.
assert "Nothing stands in for a turn with two fingers" in working.adviceFor(working.TOUCH)
assert "feels no pressure from this" in working.adviceFor(working.PRESSURE)
assert "refuses movements made by a program" in working.adviceFor(working.AIM)
# The ways of dragging still come first in the question to the vision model: with the click first it called an
# upright fader a click (2026-11-18).
assert working.VISION_SYSTEM.index("drag up and down:") < working.VISION_SYSTEM.index("click:") < working.VISION_SYSTEM.index("touch with fingers:")
assert working.waysText({working.TOUCH: 1, working.AIM: 2}) == (
	"Of the controls whose kind NVDA can tell, with a mouse 2 are worked by moving the mouse itself, with no pointer, "
	"1 is touched with two or more fingers.")
print("OK")
