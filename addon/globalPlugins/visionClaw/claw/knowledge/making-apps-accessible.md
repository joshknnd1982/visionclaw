# Making programs and games usable

## How to choose a way to make a program accessible
Try the simplest way first. 1. If NVDA already reads the control, only a command or setting is needed.
2. If the window is a picture to NVDA (a game, a custom drawn program), list its items from the picture
with list_items and click one with click_item. 3. If a button has no name, give it one with name_control.
4. If the user will use the program often, make an app helper: hotkeys that click or read named items.
5. Write an add-on only when the program needs behaviour none of these can give, such as speaking when
something changes.

## Programs and games NVDA cannot read at all, custom drawn windows
Some programs draw their own buttons, so NVDA sees one empty window. VisionClaw reads the picture of the
window instead: text is read with Windows OCR and icons are named by the vision model. list_items gives a
numbered list of what is there; click_item clicks one. The overlay (NVDA+Alt+O) shows the same list for
the user to move through with the arrow keys and press Enter on.

## Scrolling a window the keyboard does not scroll
scroll_view turns the mouse wheel in the window in front: up, down, left or right, a little, a page, or to
the end. It compares the window's picture before and after, so it says truthfully whether anything moved,
and where the window shows a scrollbar it says how far along the view stands. To scroll what is under a
certain place, use pointer mode (NVDA+Alt+K): I and K turn the wheel up and down at the pointer, and S puts
the pointer on a scrollbar so that it can be dragged with G and the arrow keys. NVDA also has its own
commands for the mouse wheel, without keys assigned; find_command finds them by the words mouse scroll.

## Screens of different sizes and scalings
Nothing in VisionClaw is a fixed number of pixels. Items are found in the picture of the window as it is
on this screen, clicks go to the middle of the item found, steps in pointer mode follow the screen's
scaling, and distances given in words, like a little, are a share of the window.

## Dials, knobs and custom sliders that are only dragged with the mouse
work_control lets the arrow keys work a control that a sighted person drags or turns: a dial, a knob, a fader,
a custom slider. It finds out how the control is worked by trying: through Windows itself, the mouse wheel,
dragging up and down, sideways, or around. After each key press the user hears what changed. K keeps it under
a hotkey. For a control with nothing to name, the user turns on pointer mode (NVDA+Alt+K), moves the pointer
onto it and presses D. Use drag_item only for one single drag, such as dropping one thing on another.

## Finding out how a control is worked: a deep query
check_access with the target control asks everything about the focused control: what NVDA reports, what
Windows UI Automation offers (an action to press it, a value that can be set), its window and the toolkit or
game engine that draws it, and the text NVDA's off-screen model caught. It says how a sighted person works
the control and what to ask for. A deep inspection of a window or page does this for every control whose
kind NVDA cannot tell, and offers a key that presses, or arrow keys, for those the keyboard does not reach.

## App helpers: hotkeys for a program that has none
An app helper belongs to one program. It maps a key to an item in the window, found by its text each
time the key is pressed, so it still works when the window moves or is resized. Action click presses the
item. Action read speaks the text next to or under a label, like a score or a status line. Helpers are
plain data, not code, so they are safer and more reliable than an add-on. Use keys like NVDA+alt+1.

## Unlabelled buttons and icons
A button without a name is announced only as "button". name_control saves a name for the focused control
or for an icon in the overlay; NVDA uses it from then on in that program. Find out what the button does
first with look, by asking what the icon shows.

## Things in a window that change: status lines, scores, timers, chat
To hear a value on request, use an app helper with the read action. To hear it automatically when it
changes, an add-on is needed, with event_valueChange or event_nameChange when NVDA can see the control.
When NVDA cannot see it, the add-on would have to look at the picture repeatedly, which is slow; prefer
a hotkey that reads it on request.

## Games
Many games have no controls NVDA can see. Menus can usually be worked from the picture with list_items
and click_item, or with the game's own keys sent by press_keys. Ask the user which keys the game uses
if they know. Fast action on screen cannot be described quickly enough; say so honestly.

## New to NVDA: the NVDA key and basic commands
The NVDA key is Insert, or Caps Lock if the user chose that. NVDA+N opens the NVDA menu. NVDA+T reads
the window title. NVDA+Tab says what has the focus. NVDA+Down arrow reads from here on (say all).
Control stops speech. NVDA+1 turns input help on and off, where every key says what it does.
NVDA+Control+G opens general settings. NVDA+Q quits NVDA. The numpad keys or NVDA+arrow keys explore the
screen by object. find_command finds the exact keys for any command on this computer; always use it
before telling the user a shortcut, because keys differ between desktop and laptop keyboard layouts.
