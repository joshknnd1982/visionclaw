<!-- Written on 2026-11-18 from VisionClaw's own code: claw/places.py and placetools.py (what is in the system
tray, on the taskbar, on the desktop and in the parts of Windows that are opened first), claw/computer.py and computertools.py (opening things by
name, the Recycle Bin, the computer's volume, windows, files, facts about the computer, locking and shutting
down, requests that depend on something), claw/controls.py and controltools.py (a named control of the program
in front), claw/planner.py (long requests split by plain rules) and claw/router.py. When the code changes, read
it again and bring these up to date; do not write them from memory. Each section is short on purpose: one
section is one answer, and it is given to the user word for word by the smallest models.
Nothing may stand between this comment and the first heading but the title, or it becomes a section. -->
# VisionClaw working the computer for you

## What VisionClaw can do on the computer for you, and several things in one request
Ask in your own words, with NVDA+Alt+C. VisionClaw opens programs, folders and settings by name, checks and
empties the Recycle Bin, changes the computer's volume, works windows, looks through your folders, and sets
options inside a program. Several things can be asked at once, joined with commas or then; each is done in
order and announced as a step.

## The Start menu, the Start button, the taskbar, the system tray and quick settings
Say: open the Start menu, click the Start button, go to the system tray, open quick settings. These are parts of
Windows itself, in no program's window. VisionClaw opens each with Windows' own key, such as Control+Escape for
the Start menu or Windows+B for the system tray, and tells you that key for next time.

## What is in the system tray, on the taskbar, on the desktop, and in the notifications
Say: what is in the system tray, is NVDA running in the system tray, which programs are on my taskbar, what icons
are on my desktop, read my notifications. VisionClaw reads it from what Windows tells screen readers, word for
word, also the hidden tray icons, and says the key that goes there. Right-click the volume icon in the system tray
clicks it there.

## Opening a program, a folder, the Recycle Bin, Control Panel or Windows Settings by name
Say open, and the name: open Notepad, open my Downloads folder, open the Recycle Bin, open Bluetooth settings.
VisionClaw finds it among the programs of the Start menu, the things on your desktop, the places and settings
pages of Windows, and your own files, asks before it opens it, and says which window is in front afterwards.

## Checking the Recycle Bin, whether it needs emptying, and emptying it
Ask: check my recycle bin. VisionClaw says how many items it holds, how much room they take, and whether
emptying is worth it for the room on your drive. To empty it, say: empty the recycle bin. VisionClaw always
asks first, because what is emptied is deleted for good and cannot be brought back.

## The volume of the computer, and muting it
Say: turn down my system volume, or set the computer's volume to 40 percent. This is the volume of the whole
computer, not of NVDA's voice. Turning it down stops at 10 percent, so that NVDA can still be heard. Muting is
refused when no braille display is in use, because NVDA would be silent too.

## Switching to a window, closing, minimizing and maximizing windows
Say: switch to Firefox, close Notepad, minimize all windows, maximize this window. VisionClaw names the window
it worked. A window that stays open after it was asked to close may be asking whether to save. The keys of
Windows for this are Alt+Tab to switch, Alt+F4 to close, and Windows+D to show the desktop.

## What is in your Downloads, Documents or Desktop folder, and finding a file by name
Ask: what is in my downloads folder, find the file named budget, how many PDFs are in my documents. VisionClaw
looks in your Desktop, Documents, Downloads, Pictures, Music and Videos folders, lists the newest first with
size and date, and changes nothing. To open one of them, say open and its name.

## Making a folder, and renaming, moving, copying or deleting a file or folder of yours
Say: create a folder called Taxes in my documents, rename the file budget to Budget 2026, move the file
report.pdf to my documents, delete the file old notes. VisionClaw asks first and overwrites nothing. Deleting
moves the file to the Recycle Bin, from where it can be brought back. A rename or a move is undone with: undo that.

## Free disk space, memory, processor, how long the computer has been on, and whether it is online
Ask: how much disk space do I have left, how much memory does my computer have, how long has my computer been
on, am I connected to the internet, which programs are running. The answers come from Windows itself. Nothing
is sent to the internet to find out.

## Locking, restarting, shutting down the computer, and calling a shutdown off
Say: lock my computer, restart my computer, shut down the computer, put the computer to sleep. VisionClaw
always asks first. A restart or shutdown waits 30 seconds; in that time, say: cancel the shutdown. Save your
work before you say yes, because work that is not saved is lost.

## Doing something only if something else is so: if you see, if it is open, if the Recycle Bin is not empty
Say: if you see the Recycle Bin, open it; if Notepad is open, close it; if my recycle bin is not empty, empty
it. VisionClaw checks first: the names NVDA has where you are, the text on the screen, then the picture. It
tells you what it found, and when the condition does not hold it says that the rest was not done.

## Turning an option, check box, switch or slider inside a program on, off, up or down
Say: turn on dark mode in this program, turn the equalizer down, turn the volume up a bit in this app.
VisionClaw looks for the control by its name in the window, on the other pages of its dialog, and in the
window's picture where NVDA cannot read it. It asks first, and says what the control was and what it is now.
