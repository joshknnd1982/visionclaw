<!-- Written on 2026-11-18 from VisionClaw's own code: claw/gamepad.py (what each button of a game controller does),
claw/touch.py (touch gestures and pressure), claw/direct.py (games that read the mouse directly) and the keys
of pointer mode in claw/pointer.py. When the code changes, read it again and bring these up to date; do not
write them from memory. Each section is short on purpose: one section is one answer, and it is given to the
user word for word by the smallest models.
Nothing may stand between this comment and the first heading but the title, or it becomes a section. -->
# VisionClaw with a game controller, fingers, pressure and games

## Game controller: turning controller mode on and off
With a game controller connected, press NVDA+Alt+J, or hold the controller's View and Menu buttons together
for a second. Controller mode then works the mouse pointer in the window in front. The View button turns it
off. VisionClaw says when a controller is connected; that can be changed in its settings, under Game
controller.

## Game controller: what the left stick and the direction pad do
In controller mode the left stick moves the mouse pointer: a small push moves it slowly, a full push fast.
Hold the left shoulder button for slow and exact, the right shoulder button for fast. The direction pad moves
the pointer one step at a time. When the stick comes to rest, VisionClaw says what is under the pointer.

## Game controller: what the buttons A, B, X and Y do
In controller mode A clicks, B right-clicks, X double-clicks, and Y says what is under the mouse pointer.
The Menu button says everything the controller does. Pressing the left stick in says where the pointer is in
the window.

## Game controller: the triggers, holding the mouse button, dragging and pressure
In controller mode the right trigger is the mouse button for as long as you pull it: pull it, move the left
stick and let go to drag, or keep it pulled to hold a button down. The left trigger presses like a pen, as
hard as you pull it, for drawing and for controls that feel pressure.

## Game controller: the right stick, scrolling and looking around in a game
In controller mode the right stick turns the mouse wheel up, down and sideways. Press the right stick in, and
it moves the mouse itself instead, for a game that reads the mouse directly and turns its view with it. Press
it in again for the wheel.

## Game controller: the shoulder buttons held with another button
With the left shoulder button held: A clicks the moment what is under the pointer changes, B rests the
pointer and says what appears, X tries what is there as a dial or slider, Y reads the text there. With the
right shoulder button held: right and left on the direction pad jump between the things found in the window,
and Y has the picture there described.

## Game controller: making a button a hotkey of a program
Ask VisionClaw, with the program in front, to make a button of the controller click, read, hover over or
hold something by its name: for instance the X button, the left shoulder button or up on the direction pad.
The button then does that in this program whenever the controller is connected. Remove it by asking.

## Touch gestures without a touch screen: pinch, spread, swipe, turn, double tap
Ask VisionClaw to pinch or spread something with two fingers, to swipe it with one to five fingers, to turn
it with two fingers, to double tap it, or to touch and hold it. It touches the screen as fingers would and
says whether anything changed. Where a program takes no touch, it uses the mouse wheel for a pinch, a spread
and a two-finger swipe.

## Pressure without a pen: pressing lightly or firmly, drawing a line with pressure
Ask VisionClaw to press something lightly, firmly, as hard as it goes, or at a number of percent of full
pressure, for a time; or to draw a line or a shape with the pressure rising or falling. It presses as a pen
would. A program that reads a drawing tablet through the tablet's own driver takes no notice.

## A game where the mouse turns the view: turning, looking and aiming
Tell VisionClaw once that the mouse turns the view in this game. Then ask it to turn left or right, to look
up or down, or to turn around: it moves the mouse itself and says whether the view changed. If it turns too
far or not far enough, say that direct mouse movement is too fast or too slow; that is kept for the game.

## A game that draws its own mouse pointer: clicking things by name
Tell VisionClaw once that this game has its own pointer. Clicking, holding and dragging things by name then
work again: VisionClaw pushes the game's pointer into the corner of the window, measures how fast it moves,
and brings it to the thing. If clicks land beside what you name, say that it is too fast or too slow.

## Pointer mode: the key M changes how the mouse is moved, for games
In pointer mode, NVDA+Alt+K, the key M changes how the mouse is moved: Windows' own pointer, the game's own
pointer, or a view that the mouse turns. For a view the arrow keys move the mouse itself and Enter clicks
where the game aims. What you choose is kept for the program.
