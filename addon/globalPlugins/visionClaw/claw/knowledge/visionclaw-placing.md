<!-- Written on 2026-11-19 from VisionClaw's own code: claw/placing.py and gototools.py (being put on a window, a page
and a control, and the most useful item), claw/landing.py and orchestrator._landed (where the user is at the end of a
request), claw/troubles.py and helpoffer.py (help offered where a place tells NVDA little). When the code changes, read
it again and bring these up to date; do not write them from memory. Each section is short on purpose: one section is
one answer, and it is given to the user word for word by the smallest models.
Nothing may stand between this comment and the first heading but the title, or it becomes a section. -->
# VisionClaw putting you where you want to be

## How do I get VisionClaw to put me on a control, a field, a page or a tab of a dialog
Ask with NVDA+Alt+C, for example: put me on page two of the Advanced dialog, in the Proxy edit field. Or: move the
focus to the Save button, take me to the Connection tab, put the cursor in the search box. VisionClaw finds the
window, then the page, then the control, and says where you are when NVDA reports the focus there.

## What if the dialog or window is not open yet
Name it: put me in the Name field of the Options dialog. VisionClaw brings an open window of that name to the front.
Where none is open and the window in front has a button for it, such as Options..., it asks before it presses it.
Where there is neither, it says so, and nothing is changed.

## What if VisionClaw cannot put me there
It says what there is instead, such as the edit fields of that page, and that nothing else was moved. Where a program
does not let the focus move to a control, VisionClaw puts NVDA's navigator object on it and says where the focus is.
It never says you are somewhere unless NVDA reports it.

## Put me on the most useful control, somewhere useful, where to start
Say: put me on the most useful control in this dialog. VisionClaw chooses as a sighted person's eye would: the default
or highlighted item, the usual way on such as OK or Continue, the start of a game, an empty field to type in, what is
larger or a colour that stands out. It says why it chose that item.

## Put on an item of a window that tells NVDA almost nothing, through the overlay
Where a window tells NVDA almost nothing, VisionClaw reads its picture and opens the overlay, NVDA+Alt+O, with its
cursor on the item you asked for or the most useful one. The arrow keys move between items, Enter clicks one, Escape
closes the overlay. What is read from a picture can be wrong.

## A field or button on a web page, browse mode and focus mode
On a web page, a field you want to type in gets the focus in focus mode, as Enter does: type, and press Escape to go
back to browse mode. A button or link gets NVDA's reading position in browse mode, so nothing is pressed: Enter uses it.

## Where am I after VisionClaw has done something
At the end of a request VisionClaw says where you are when the focus moved: the program, window, control and whether a
web page is in browse mode or focus mode. When a dialog came up, it says its message and its default button. Where the
place tells NVDA almost nothing, it says how to get on, and Alt+Tab goes back.

## Help offered by itself, NVDA+Alt+Y, and how to refuse it or stop it
Where VisionClaw notices a window that tells NVDA almost nothing, a dialog with nothing focused, a control without a
name or errors NVDA logged, it offers help in one sentence. Press NVDA+Alt+Y to take it; do nothing to say no. Press it
twice for no more offers in that program, once there to have them again, or turn off Offer help in VisionClaw settings.
