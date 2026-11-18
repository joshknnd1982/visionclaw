# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A game controller as a way to work the computer, with plain Python.

What Windows reports of a controller as one plain state; what changed from one look to the next, with a
pulled trigger counted as a button and both middle buttons held as a chord; which button does what; how far
a pushed stick moves the pointer; which button a request in words names. Also the skills, the notes and the
words that belong to controllers, fingers, pressure and games.
No controller is read here: the states are numbers made by this test.

  python tests/test_gamepad.py
"""
import tempfile

import harness  # noqa: F401
from visionClaw.claw import gamepad, lookup, memories, planner, pointer, prompts, skills
from visionClaw.claw.knowledge import Knowledge

# --- What Windows reports, as one plain state ---

state = gamepad.fromXInput(0x1000 | 0x0100 | 0x0001, 255, 0, 32767, 32767, -32768, 0)
assert state.buttons == frozenset({gamepad.A, gamepad.LB, gamepad.UP}), state.buttons
# XInput counts a stick pushed away from the user as positive; on a screen that is up, which is less.
assert round(state.lx, 3) == 1.0 and round(state.ly, 3) == -1.0 and round(state.rx, 3) == -1.0 and abs(state.ry) < 0.001
assert state.lt == 1.0 and state.rt == 0.0
assert gamepad.fromXInput(0, 0, 0, 0, 0, 0, 0).buttons == frozenset()
assert set(gamepad.XINPUT_BITS.values()) == set(gamepad.BUTTONS) - {gamepad.LT, gamepad.RT}  # the triggers are not bits
# A controller of another make: its buttons by where they lie on most, its direction pad as an angle.
other = gamepad.fromJoystick(0b10 | (1 << 6), {"x": -1.0, "y": 0.5, "z": 0.25, "r": 0.0}, 4500)
assert other.buttons == frozenset({gamepad.A, gamepad.LT, gamepad.UP, gamepad.RIGHT}), other.buttons
assert (other.lx, other.ly, other.rx, other.ry) == (-1.0, 0.5, 0.25, 0.0) and other.lt == 1.0 and other.rt == 0.0
assert gamepad.fromJoystick(0, {}, 18000).buttons == frozenset({gamepad.DOWN})
assert gamepad.fromJoystick(0, {}, 27000).buttons == frozenset({gamepad.LEFT})
assert gamepad.fromJoystick(0, {}, None).buttons == frozenset() and gamepad.fromJoystick(0, {}, 65535).buttons == frozenset()

# --- A stick: at rest in its middle, gentle at first, strong at the rim ---

assert gamepad.stick(0.1, 0.1) == (0.0, 0.0) and gamepad.stick(0.0, gamepad.DEAD) == (0.0, 0.0)
little, half, full = gamepad.stick(0.4, 0.0)[0], gamepad.stick(0.62, 0.0)[0], gamepad.stick(1.0, 0.0)[0]
assert 0 < little < 0.06 and 0.2 < half < 0.3 and full == 1.0, (little, half, full)
across, down = gamepad.stick(-0.7, 0.7)
assert across < 0 < down and abs(abs(across) - down) < 1e-9  # a slanted push stays slanted
assert gamepad.stick(1.0, 1.0)[0] < 1.0 and abs(sum(v * v for v in gamepad.stick(1.0, 1.0)) - 1.0) < 1e-9
# How far in a length of time: more on a screen that draws things larger, less with the slow button.
assert gamepad.glide(1.0, 0.0, 1.0) == (gamepad.SPEED, 0.0)
assert gamepad.glide(0.0, 1.0, 0.5, scale=2.0) == (0.0, gamepad.SPEED)
assert gamepad.pace({gamepad.LB}) == gamepad.SLOW and gamepad.pace({gamepad.RB}) == gamepad.FAST and gamepad.pace(set()) == 1.0
# A slow push is not lost: its small pieces are added up until they make a pixel.
carry = gamepad.Carry()
moved = [carry.add(0.3, -0.3) for _ in range(10)]
assert sum(x for x, _y in moved) == 3 and sum(y for _x, y in moved) == -3 and (1, -1) in moved and (0, 0) in moved
carry.clear()
assert carry.add(0.9, 0.0) == (0, 0)

# --- From one look to the next ---


def look(buttons=(), lt=0.0, rt=0.0):
	return gamepad.State(frozenset(buttons), 0.0, 0.0, 0.0, 0.0, lt, rt)


follower = gamepad.Follower()
assert follower.update(look([gamepad.A]), 0.0) == [("down", gamepad.A)]
assert follower.update(look([gamepad.A]), 0.1) == []  # held: nothing new
assert follower.update(look([gamepad.B]), 0.2) == [("down", gamepad.B), ("up", gamepad.A)]
assert follower.update(look(), 0.3) == [("up", gamepad.B)]
# A trigger counts as a button once it is pulled far enough, and until it is nearly let go: it does not flutter.
assert follower.update(look(rt=0.3), 1.0) == [] and follower.update(look(rt=0.45), 1.1) == [("down", gamepad.RT)]
assert follower.update(look(rt=0.3), 1.2) == [] and gamepad.RT in follower.held
assert follower.update(look(rt=0.2), 1.3) == [("up", gamepad.RT)]
# Both middle buttons held for a second, once; again only after both were let go.
both = [gamepad.BACK, gamepad.START]
assert follower.update(look(both), 5.0) == [("down", gamepad.BACK), ("down", gamepad.START)]
assert follower.update(look(both), 5.5) == [] and follower.update(look(both), 6.0) == [("chord",)]
assert follower.update(look(both), 8.0) == []
follower.update(look([gamepad.START]), 8.1)
follower.update(look(both), 8.2)
assert follower.update(look(both), 9.5) == []  # one of them was never let go
follower.update(look(), 9.6)
follower.update(look(both), 10.0)
assert follower.update(look(both), 11.0) == [("chord",)]
# After the mode was changed by a button, the chord waits until both are up.
follower.update(look(), 12.0)
follower.disarm()
follower.update(look(both), 13.0)
assert follower.update(look(both), 14.5) == []
follower.update(look(), 15.0)
follower.update(look(both), 16.0)
assert follower.update(look(both), 17.0) == [("chord",)]

# --- Which button does what ---

assert gamepad.commandFor(gamepad.A, set()) == ("click",) and gamepad.commandFor(gamepad.B, set()) == ("right",)
assert gamepad.commandFor(gamepad.X, set()) == ("double",) and gamepad.commandFor(gamepad.Y, set()) == ("what",)
assert gamepad.commandFor(gamepad.UP, set()) == ("move", "up", pointer.STEP)
assert gamepad.commandFor(gamepad.UP, {gamepad.LB}) == ("move", "up", pointer.FINE)
assert gamepad.commandFor(gamepad.A, {gamepad.LB}) == ("when", True) and gamepad.commandFor(gamepad.B, {gamepad.LB}) == ("rest",)
assert gamepad.commandFor(gamepad.RIGHT, {gamepad.RB}) == ("item", 1) and gamepad.commandFor(gamepad.LEFT, {gamepad.RB}) == ("item", -1)
assert gamepad.commandFor(gamepad.A, {gamepad.RB}) == ("grab",) and gamepad.commandFor(gamepad.X, {gamepad.RB}) == ("way",)
assert gamepad.commandFor(gamepad.BACK, set()) == ("exit",) and gamepad.commandFor(gamepad.START, set()) == ("help",)
# The shoulder buttons and the triggers do nothing by being pressed; and a button with no meaning beside a
# held shoulder button does nothing, instead of something the user did not mean.
for button in (gamepad.LB, gamepad.RB, gamepad.LT, gamepad.RT):
	assert gamepad.commandFor(button, set()) is None
assert gamepad.commandFor(gamepad.START, {gamepad.LB}) is None and gamepad.commandFor(gamepad.LS, {gamepad.RB}) is None
# Every command a button gives is one pointer mode knows, or one of the controller's own.
known = {command[0] for command in pointer.KEYS.values()} | {"what", "stick", "item", "items", "middle"}
for table in (gamepad.ALONE, gamepad.WITH_LEFT, gamepad.WITH_RIGHT):
	for button, command in table.items():
		assert button in gamepad.BUTTONS and command[0] in known, (button, command)
# The help names every button that does something, by the name it has on the controller.
for word in ("left stick", "direction pad", "A clicks", "B right-clicks", "X double-clicks", "Y says", "right trigger",
		"left trigger", "right stick", "left shoulder button", "right shoulder button", "Menu button", "View button"):
	assert word in gamepad.HELP, word
assert "{kind}" in gamepad.CONNECTED and "NVDA+Alt+J" in gamepad.CONNECTED
assert "may not fit this one" in gamepad.kindText(gamepad.OTHER)  # what is not known is said

# --- A button named in words ---

for words, button in (
	("Make the X button on my controller click Play", gamepad.X),
	("the left bumper of my gamepad", gamepad.LB), ("right shoulder button on the controller", gamepad.RB),
	("the left trigger of the controller", gamepad.LT), ("RT on the xbox controller", gamepad.RT),
	("d-pad up on the controller", gamepad.UP), ("left on the d-pad", gamepad.LEFT),
	("click the left stick on my controller", gamepad.LS), ("R3 on my gamepad", gamepad.RS),
	("the menu button of my controller", gamepad.START), ("the view button on the gamepad", gamepad.BACK),
	("the cross button on my playstation controller", gamepad.A), ("triangle on the dualsense", gamepad.Y),
	# Only where the words speak of a controller at all: a browser has a back button too.
	("press the back button", None), ("click the X button to close", None), ("NVDA+alt+1", None),
	("my controller", None),
):
	assert gamepad.buttonOf(words) == button, (words, gamepad.buttonOf(words))
assert gamepad.identifier(gamepad.X) == "pad:x" and gamepad.buttonText(gamepad.X) == "the X button"
assert all(gamepad.buttonText(name) != name for name in gamepad.BUTTONS)
assert gamepad.about("is my joystick connected") and not gamepad.about("click the Start button")

# --- The words point to the right job ---

HINTS = {
	"Is a controller connected?": "controller_info", "What do the buttons on my gamepad do?": "controller_info",
	"How do I use my controller with VisionClaw?": "controller_info", "Do I have a joystick plugged in?": "controller_info",
	"Turn on controller mode": "controller_mode", "Turn off controller mode": "controller_mode",
	"Use the mouse pointer with my Xbox controller": "controller_mode",
	"Let me work this window with my controller": "controller_mode", "Stop using the controller": "controller_mode",
	"Make the X button on my controller click Play": "make_hotkey",
	"Let the left bumper of my gamepad read the score": "make_hotkey",
	# A joystick drawn in a window is dragged; no controller is meant.
	"Drag the joystick left": "drag",
}
for words, recipe in HINTS.items():
	assert planner.hint(words) == recipe, (words, planner.hint(words))
assert planner.RECIPES["controller_info"][2] == ("controller_info",) and planner.RECIPES["controller_mode"][2] == ("controller_mode",)
# A model that takes "make the X button on my controller click ..." for a click now is corrected: the button
# must never be clicked instead. A click that names no button of a controller stays a click.
assert planner.fitted("click", "Make the X button on my controller click the New Game button", "make_hotkey") == "make_hotkey"
assert planner.fitted("click", "Click the New Game button", "click") == "click"
assert planner.fitted("click", "Give this program a hotkey for the Play button", "make_hotkey") == "click"

# --- Skills: chosen by the request's words, and only then ---

lib = skills.Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
CHOSEN = {
	"Pinch the map with two fingers": "fingers-and-pressure",
	"Press harder on the drum pad": "fingers-and-pressure",
	"Is my game controller connected?": "game-controller",
	"What does the left trigger do in controller mode?": "game-controller",
	"Turn around, this game has mouse look": "game-direct-mouse",
	"This game draws its own pointer": "game-direct-mouse",
}
for request, slug in CHOSEN.items():
	chosen = [skill.slug for skill in lib.choose(request)]
	assert slug in chosen, (request, chosen)
for request in ("what time is it", "turn up the volume", "look up the weather", "press Enter", "open the control panel"):
	chosen = [skill.slug for skill in lib.choose(request)]
	assert not {"fingers-and-pressure", "game-controller", "game-direct-mouse"} & set(chosen), (request, chosen)
# Their sentences reach the steps of their jobs, and no others.
pad = lib.get("game-controller")
assert skills.guide([pad], "controller_mode").startswith('Follow the skill "Work the computer with a game controller": ')
assert skills.guide([pad], "change_setting") == ""
assert "View and Menu" in pad.instructions and "NVDA+alt+j" in pad.instructions

# --- The notes answer questions, and only questions about these things ---

knowledge = Knowledge()
POOL = lookup.fromSections(knowledge.everything())


def answer(question):
	return lookup.resultText(lookup.about(question, POOL))


first = answer("How do I turn on controller mode?")
assert first.startswith("From VisionClaw's notes on game controllers, touch, pressure and games: Game controller: turning controller mode on and off."), first
assert "NVDA+Alt+J" in first and "View and Menu" in first
assert "A clicks, B right-clicks, X double-clicks" in answer("What do the buttons A and B do on the game controller?")
assert "right trigger is the mouse button" in answer("How do I drag with the trigger of the controller?")
assert "pinch or spread" in answer("How can I pinch without a touch screen?")
assert "presses as a pen" in answer("How do I press with pressure without a pen or stylus?")
assert "own pointer" in answer("The game has its own mouse pointer, how do I click things?")
# A question that names none of these is not answered from them.
for question in ("How do I press a button?", "How do I open the Start menu?", "What is browse mode?"):
	assert "game controllers, touch, pressure and games" not in answer(question), (question, answer(question))
# One section is one answer, short enough to be given word for word.
for title, body, source in knowledge.everything():
	if source == "visionclaw-inputs":
		assert len(body) <= 360, (title, len(body))
		assert ":" in title, title

# --- What is worth keeping about the user, and what every answer is told ---

changes = lambda tool: False  # noqa: E731
# How the user works the computer includes a controller, a joystick, a pen and a touch screen.
assert memories.worthKeeping("I prefer my joystick", memories.AUTO, [], changes) == "I prefer my joystick"
assert memories.worthKeeping("I am blind and use a game controller, how do I click?", memories.AUTO, [("look_up", True)], changes) == (
	"I am blind and use a game controller")
assert memories.worthKeeping("I prefer my coffee black", memories.AUTO, [], changes) == ""
assert "controller" in prompts.SPEAKING and len(prompts.SPEAKING) < 700
print("OK")
