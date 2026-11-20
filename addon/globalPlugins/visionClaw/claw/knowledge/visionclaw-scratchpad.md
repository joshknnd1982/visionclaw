<!-- Written on 2026-11-19 from VisionClaw's own code: claw/scratchpad.py and scratchtools.py (scratchpads), claw/worksheet.py
and claw/orchestrator.py (what the models write down while they work), claw/diagnose.py and diagnosetools.py (VisionClaw's
own logs and code). When the code changes, read it again and bring these up to date; do not write them from memory.
Each section is short on purpose: one section is one answer, and it is given to the user word for word by the smallest
models. Nothing may stand between this comment and the first heading but the title, or it becomes a section. -->
# VisionClaw's scratchpads, and its own logs and code

## What a scratchpad is, and how to start one for a task
A scratchpad is a Markdown file where VisionClaw and its models write down what they find while they work. Say: start a
scratchpad for, then the task, and after a colon the things to do, joined with commas or then. While it is open,
VisionClaw reads it with every request and writes down what was done.

## Writing on the scratchpad, checking things off, and what is next
Say: write on the scratchpad that, then what to write. Say: add, then a thing to do, to the scratchpad. Say: check off
step 2, or mark the first one as done. Say: what's next, or where was I. Say: read my scratchpad, to hear all of it.

## Finishing, opening, listing and deleting scratchpads
Say: close the scratchpad when the task is done; it is kept. Say: open my scratchpad, to read the file in your program
for text. Say: which scratchpads do I have. Say: delete the scratchpad, or delete all scratchpads; VisionClaw asks first.

## What the models learn on the fly, in each program and website
While they work, the models write down the one fact a long result holds that the next step needs, and plain code keeps
it only when its names, numbers and keys are in what was found. Those lines are kept on a scratchpad for each program or
website, with the topics they are about, and used again there the next time.

## The descriptions scratchpad, and asking about something described before
The last descriptions of the screen and of pictures, and the questions answered about them, are kept on the
descriptions scratchpad. Ask about one later by pointing back at it: what was the phone number in the picture you
described. Say: delete the descriptions scratchpad, to clear it.

## Where the scratchpads are, and turning them off
They are Markdown files in the folder scratchpads of VisionClaw's data, inside the add-on, so a portable copy carries
them, as it carries the logs. In VisionClaw's settings, Let the models keep scratchpads turns off what the models write
down, what they learn and the descriptions; a task scratchpad you start is kept either way.

## Reading VisionClaw's own log for errors, only when you ask
Say: what errors are in your log, or why did my last request fail, or diagnose your last error. VisionClaw reads its log
only then. It says each error, when and how often it happened, and where in its code, and the model that writes code
says in plain words what went wrong, which may be wrong. To open the log file itself, say: open your log.

## Having VisionClaw correct a bug in its own code, only when you ask
Say: fix that bug in your code. The model that writes code corrects the one function where the error happened, plain
code checks it, the model that sees reads it, and VisionClaw always asks you first. Its own files are not changed: the
correction is used while NVDA runs and whenever VisionClaw starts.

## Undoing a correction, and which corrections there are
Say: undo that, right after a correction, or remove the corrections to your own code. Say: which fixes did you make to
your own code. A correction that fails by itself turns itself off. An update of VisionClaw puts it aside, and a report of
each is in the folder ownfixes of VisionClaw's data.
