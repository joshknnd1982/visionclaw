# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Checks the reasoning behind working the mouse from the keyboard: which mouse action a request means,
how the pointer moves and stays inside a window, where a drag ends, and the keys of pointer mode.
Nothing here touches the mouse."""
import harness  # noqa: F401
from visionClaw.claw import pointer

BOX = (100, 100, 900, 700)  # a window 800 wide and 600 high

# Which mouse action a request means.
for words, action in (
	("click the Play button", pointer.CLICK),
	("right-click the file icon", pointer.RIGHT),
	("open the context menu of the document", pointer.RIGHT),
	("double click the folder", pointer.DOUBLE),
	("click twice on the picture", pointer.DOUBLE),
	("hover over the Help button", pointer.HOVER),
	("move the mouse to the toolbar", pointer.HOVER),
	("press Start", pointer.CLICK),
	# What is neither a click nor a drag: the button kept down, the middle button, three clicks.
	("press and hold the Record button for 3 seconds", pointer.HOLD),
	("hold down the Talk button", pointer.HOLD),
	("long-press the app icon", pointer.HOLD),
	("keep the Charge button pressed", pointer.HOLD),
	("a hotkey that holds down the Push to talk button", pointer.HOLD),
	("click the Hold button", pointer.CLICK),  # a button called Hold is clicked
	("middle-click the link", pointer.MIDDLE),
	("click the tab with the mouse wheel", pointer.MIDDLE),
	("triple-click the paragraph", pointer.TRIPLE),
	("a hotkey that hovers over the Help icon", pointer.HOVER),
	("rest the pointer on the chart", pointer.HOVER),
):
	assert pointer.actionOf(words) == action, (words, pointer.actionOf(words))

# How long the button is kept down: what the words say, else a second and a half, never longer than a minute.
assert pointer.holdSeconds("hold the Record button for 3 seconds") == 3 and pointer.holdSeconds("hold it for half a second") == 0.5
assert pointer.holdSeconds("press and hold Delete") == pointer.HOLD_DEFAULT and pointer.holdSeconds("hold it for 10 minutes") == pointer.HOLD_MAX
assert pointer.secondsIn("wait 200 ms") == 0.2 and pointer.secondsIn("for a second") == 1 and pointer.secondsIn("for 2 minutes") == 120
assert pointer.secondsIn("as soon as it is ready") is None  # "as" is not "a s"
assert pointer.secondsText(0.5) == "half a second" and pointer.secondsText(1) == "1 second" and pointer.secondsText(2.5) == "2.5 seconds"
assert pointer.secondsText(0.08) == "80 milliseconds" and pointer.secondsText(120) == "2 minutes"

# Keys held down during a click. A key must be said to be a key or to be held.
assert pointer.modifiersOf("control-click the second file") == ["control"]
assert pointer.modifiersOf("ctrl+shift+click the last row") == ["control", "shift"]
assert pointer.modifiersOf("click Photo 3 with the Shift key held down") == ["shift"]
assert pointer.modifiersOf("click the layer while holding alt") == ["alt"]
assert pointer.modifiersOf("click the icon with the control panel label") == [] and pointer.modifiersOf("click Play") == []
assert pointer.modifiersOf("right-click the shift button") == []

# A click at a place on a thing: a bar that is clicked where the value should be, a picture, a board.
assert pointer.spotOf("click the seek bar 30 percent across") == (0.3, 0.5)
assert pointer.spotOf("click the picture 80% down") == (0.5, 0.8)
assert pointer.spotOf("click the right end of the timeline") == (0.95, 0.5)
assert pointer.spotOf("click the top left corner of the map") == (0.05, 0.05)
assert pointer.spotOf("click the bottom of the list") == (0.5, 0.95)
assert pointer.spotOf("click the Play button") is None and pointer.spotOf("set the volume to 30 percent") is None
assert pointer.spotText((0.3, 0.5)) == "30 percent across" and pointer.spotText((0.05, 0.95)) == "5 percent across and 95 percent down"

# A click at the right moment, or many in a rhythm; neither when the words ask for neither.
assert pointer.timingOf("click the Go button when it turns green") == {"mode": pointer.WHEN, "wait": pointer.WAIT_DEFAULT}
assert pointer.timingOf("click Catch as soon as it appears, wait up to 2 minutes") == {"mode": pointer.WHEN, "wait": 120}
assert pointer.timingOf("click the cookie 20 times") == {"mode": pointer.RHYTHM, "times": 20, "every": pointer.EVERY_DEFAULT}
assert pointer.timingOf("click Fire rapidly") == {"mode": pointer.RHYTHM, "times": pointer.TIMES_DEFAULT, "every": pointer.EVERY_FAST}
assert pointer.timingOf("click the drum five times, every half a second") == {"mode": pointer.RHYTHM, "times": 5, "every": 0.5}
assert pointer.timingOf("click the pedal 8 times, twice a second") == {"mode": pointer.RHYTHM, "times": 8, "every": 0.5}
assert pointer.timingOf("click it 5000 times every 1 ms")["times"] == pointer.TIMES_MAX
assert pointer.timingOf("click it 5000 times every 1 ms")["every"] == pointer.EVERY_LEAST
assert pointer.timingOf("click the Play button") is None
# A place that changes by itself a little needs a larger change; one that moves all the time has no moment.
assert pointer.trigger(0.0) == 0.01 and pointer.trigger(0.02) == 0.06 and pointer.trigger(0.5) is None

# Gestures: a line by its directions, a shape by its name; the button, the size and the speed from the words.
swipe = pointer.gestureOf("swipe left on the card")
assert swipe["text"] == "a swipe to the left" and swipe["strokes"] == [[(0.0, 0.0), (-1.0, 0.0)]] and swipe["button"] == pointer.LEFT_BUTTON
line = pointer.gestureOf("draw a line down then right with the right button held down")
assert line["text"] == "a line down, then to the right" and line["strokes"] == [[(0.0, 0.0), (0.0, 1.0), (1.0, 1.0)]]
assert line["button"] == pointer.RIGHT_BUTTON  # and "right button" was not taken for a direction
circle = pointer.gestureOf("draw a small circle on the canvas")
assert circle["text"] == "a circle, clockwise" and circle["size"] == 0.1 and len(circle["strokes"][0]) == 25
assert circle["strokes"][0][0] == (0.0, -0.5) and circle["strokes"][0][6][0] == 0.5  # from the top, to the right first
assert pointer.gestureOf("draw a circle anticlockwise")["strokes"][0][6][0] == -0.5
assert pointer.gestureOf("draw a tick")["text"] == "a tick" and pointer.gestureOf("draw the letter Z")["text"] == "the letter Z"
assert len(pointer.gestureOf("draw a cross on the box")["strokes"]) == 2  # two strokes: the button is let go in between
assert pointer.gestureOf("flick up")["pace"] < pointer.gestureOf("swipe up")["pace"] < pointer.gestureOf("swipe up slowly")["pace"]
assert pointer.gestureOf("click the Play button") is None and pointer.gestureOf("draw something") is None
# The points of a gesture: in small steps, a share of the window's shorter side, and never outside the window.
paths = pointer.gesturePaths(swipe, (500, 400), BOX)
assert paths[0][0] == (500, 400) and paths[0][-1] == (350, 400) and len(paths[0]) > 10, paths
assert all(abs(a[0] - b[0]) <= 8 for a, b in zip(paths[0], paths[0][1:]))
far = pointer.gesturePaths(pointer.gestureOf("swipe right all the way"), (850, 400), BOX)
assert far[0][-1] == (898, 400)  # stopped at the edge
round_ = pointer.gesturePaths(circle, (500, 400), BOX)[0]
assert round_[0] == (500, 370) and all(abs(((x - 500) ** 2 + (y - 400) ** 2) ** 0.5 - 30) <= 2 for x, y in round_)

# What appeared between two looks at a window: where the picture changed, or None when nothing a person
# would notice did.
from PIL import Image, ImageDraw  # noqa: E402

plain = Image.new("RGB", (400, 300), "white")
tipped = plain.copy()
ImageDraw.Draw(tipped).rectangle((200, 120, 320, 150), fill="black")
assert pointer.appeared(plain, plain.copy()) is None and pointer.appeared(plain, tipped) == (200, 120, 321, 151)
speck = plain.copy()
speck.putpixel((5, 5), (0, 0, 0))
assert pointer.appeared(plain, speck) is None and pointer.appeared(None, plain) is None

# The pointer moves by steps and never leaves the window.
assert pointer.centre(BOX) == (500, 400)
assert pointer.move(500, 400, "right", pointer.STEP, BOX) == (520, 400)
assert pointer.move(500, 400, "up", pointer.FINE, BOX) == (500, 396)
assert pointer.move(500, 400, "left", pointer.FAR, BOX) == (400, 400)
assert pointer.move(890, 400, "right", pointer.FAR, BOX) == (898, 400)  # stopped at the edge
assert pointer.move(105, 105, "up", pointer.FAR, BOX) == (105, 101)
assert pointer.clamp(-50, 5000, BOX) == (101, 698)

# Where the pointer is, in words, and as a tone: high at the top, low at the bottom.
assert pointer.where(100, 100, BOX) == "0 percent across, 0 percent down"
assert pointer.where(500, 400, BOX) == "50 percent across, 50 percent down"
assert pointer.where(899, 699, BOX) == "100 percent across, 100 percent down"
assert pointer.pitch(101, BOX) > pointer.pitch(400, BOX) > pointer.pitch(698, BOX) >= 300

# A drag passes through many points and ends exactly where it should.
points = pointer.path((200, 200), (500, 350))
assert len(points) >= 10 and points[-1] == (500, 350) and points[0] != (200, 200)
assert all(a[0] <= b[0] and a[1] <= b[1] for a, b in zip(points, points[1:]))

# A drag given as a direction, with or without a distance.
assert pointer.dragOffset("right 100 pixels", BOX) == (100, 0)
assert pointer.dragOffset("down 50", BOX) == (0, 50)
assert pointer.dragOffset("left 25 percent", BOX) == (-200, 0)
assert pointer.dragOffset("up a little", BOX) == (0, -48)
assert pointer.dragOffset("to the right a lot", BOX) == (280, 0)
assert pointer.dragOffset("right", BOX) == (120, 0)
assert pointer.dragOffset("all the way down", BOX) == (0, 600)
# A drag onto a thing is not a direction.
assert pointer.dragOffset("the Trash icon", BOX) is None and pointer.dragOffset("onto Quit", BOX) is None

# Every key of pointer mode does something known, and the keys a user needs are all there.
commands = {command[0] for command in pointer.KEYS.values()}
assert commands == {
	"move", "click", "double", "right", "grab", "look", "read", "where", "help", "centre", "exit", "scroll", "bars", "take",
	"rest", "when", "way"}
# M changes how the mouse is moved, for a game that reads the mouse directly (claw/direct.py).
assert pointer.KEYS["kb:m"] == ("way",)
# T rests the pointer and says what appears; C clicks the moment what is there changes, Shift+C only sounds a tone.
assert pointer.KEYS["kb:t"] == ("rest",) and pointer.KEYS["kb:c"] == ("when", True) and pointer.KEYS["kb:shift+c"] == ("when", False)
assert pointer.KEYS["kb:pagedown"] == ("scroll", "down", pointer.PAGE) and pointer.KEYS["kb:shift+pageup"] == ("scroll", "up", pointer.NOTCH)
assert pointer.KEYS["kb:control+pagedown"] == ("scroll", "right", pointer.PAGE) and pointer.KEYS["kb:s"] == ("bars",)
assert pointer.notchesFor(pointer.PAGE) == 8 and pointer.notchesFor(pointer.NOTCH) == 1
# Every job has a key that every keyboard has. The owner said on 2026-11-18: "some keyboards don't have an
# application key ... assume some don't have pageup, pagedown, home, end, either." So a key that may be missing
# is only ever a second way to something that letters, the arrow keys, Enter, Space, Escape, Shift and Control do.
EVERYWHERE = set("abcdefghijklmnopqrstuvwxyz") | {"enter", "space", "escape", "leftarrow", "rightarrow", "uparrow", "downarrow"}


def onEveryKeyboard(key):
	*held, main = key[len("kb:"):].split("+")
	return main in EVERYWHERE and set(held) <= {"shift", "control"}


def checkKeys(keys, extra):
	plain = {key: command for key, command in keys.items() if onEveryKeyboard(key)}
	for key, command in keys.items():
		if key in plain:
			continue
		# Enter on the number block is the one key left that is neither: it is Enter.
		assert key in extra or key == "kb:numpadenter", key
		assert command in plain.values(), (key, command)
	assert set(extra) <= set(keys) and not any(onEveryKeyboard(key) for key in extra)


checkKeys(pointer.KEYS, pointer.EXTRA_KEYS)
assert pointer.KEYS["kb:a"] == ("right",) == pointer.KEYS["kb:applications"]
assert pointer.KEYS["kb:b"] == ("centre",) == pointer.KEYS["kb:home"]
assert pointer.KEYS["kb:i"] == ("scroll", "up", pointer.PAGE) and pointer.KEYS["kb:k"] == ("scroll", "down", pointer.PAGE)
assert pointer.KEYS["kb:j"] == ("scroll", "left", pointer.PAGE) and pointer.KEYS["kb:l"] == ("scroll", "right", pointer.PAGE)
assert pointer.KEYS["kb:shift+k"] == ("scroll", "down", pointer.NOTCH) and pointer.KEYS["kb:shift+j"] == ("scroll", "left", pointer.NOTCH)
# The same holds while a dial or slider is held: T and B go to its ends.
from visionClaw.claw import dragcontrol  # noqa: E402
checkKeys(dragcontrol.KEYS, dragcontrol.EXTRA_KEYS)
assert dragcontrol.KEYS["kb:t"] == ("end", 1) == dragcontrol.KEYS["kb:end"] and dragcontrol.KEYS["kb:b"] == ("end", -1) == dragcontrol.KEYS["kb:home"]
said = dragcontrol.helpText("Volume", "dial", dragcontrol.UPDOWN)
assert "T goes to its top end and B to its bottom end." in said and "Home" not in said and "Page" not in said, said
# A step is the same to the eye on every screen: twice the pixels at twice the scaling, and smaller in a
# small window so that the pointer does not leap across it.
assert [pointer.stepFor(size, (0, 0, 1366, 768), 1.0) for size in (pointer.STEP, pointer.FINE, pointer.FAR)] == [20, 4, 100]
assert [pointer.stepFor(size, (0, 0, 3840, 2160), 2.0) for size in (pointer.STEP, pointer.FINE, pointer.FAR)] == [40, 8, 200]
assert [pointer.stepFor(size, (0, 0, 2560, 1440), 1.25) for size in (pointer.STEP, pointer.FINE, pointer.FAR)] == [25, 5, 125]
assert [pointer.stepFor(size, (0, 0, 200, 120), 2.0) for size in (pointer.STEP, pointer.FINE, pointer.FAR)] == [10, 5, 30]
assert pointer.KEYS["kb:shift+leftarrow"] == ("move", "left", pointer.FINE)
assert pointer.KEYS["kb:control+downarrow"] == ("move", "down", pointer.FAR)
assert all(key == key.lower() and key.startswith("kb:") for key in pointer.KEYS)
print("OK")
