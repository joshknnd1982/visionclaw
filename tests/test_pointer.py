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
):
	assert pointer.actionOf(words) == action, (words, pointer.actionOf(words))

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
	"move", "click", "double", "right", "grab", "look", "read", "where", "help", "centre", "exit", "scroll", "bars"}
assert pointer.KEYS["kb:pagedown"] == ("scroll", "down", pointer.PAGE) and pointer.KEYS["kb:shift+pageup"] == ("scroll", "up", pointer.NOTCH)
assert pointer.KEYS["kb:control+pagedown"] == ("scroll", "right", pointer.PAGE) and pointer.KEYS["kb:s"] == ("bars",)
assert pointer.notchesFor(pointer.PAGE) == 8 and pointer.notchesFor(pointer.NOTCH) == 1
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
