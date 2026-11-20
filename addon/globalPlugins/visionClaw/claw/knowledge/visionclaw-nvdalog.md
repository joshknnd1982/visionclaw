<!-- Written on 2026-11-19 from VisionClaw's own code: claw/nvdalog.py and nvdalogtools.py, which read NVDA's own log; what
NVDA writes there was read from NVDA's source, branch release-2026.3.1, as named at the top of claw/nvdalog.py. When the code
changes, read it again and bring these up to date; do not write them from memory. Each section is short on purpose: one
section is one answer, and it is given to the user word for word by the smallest models. Nothing may stand between this
comment and the first heading but the title, or it becomes a section. -->
# VisionClaw and NVDA's own log

## Reading NVDA's log: its errors, and which add-on they come from
Say: check NVDA's log, or what errors has NVDA had. VisionClaw says each error once, the newest first, with how often and
when, and which add-on it came from. Say: which add-on is causing errors, to hear the add-ons first. Say: explain NVDA's
error 2, to hear what one means; that is a model's guess and may be wrong.

## When NVDA froze, crashed or closed by itself
Say: did NVDA freeze, or why does NVDA keep freezing, to hear how often and how long, and which add-on NVDA was working in.
Say: why did NVDA crash, or how did NVDA close last time, to hear how the run before ended, from the file nvda-old.log. NVDA
keeps only the log of the run before.

## The speech synthesizer, the sound and the braille display in NVDA's log
Say: did my synthesizer fail, or why did my braille display disconnect. VisionClaw says what NVDA wrote about the speech
synthesizer, the sound output and the braille display, in the order it happened, and which ones NVDA loaded last.

## What NVDA wrote just now
Say: what just happened in NVDA, to hear what NVDA wrote in the two minutes before you asked, or since your last request.
Say: anything new in NVDA's log, to hear only what was written since VisionClaw last read it. What VisionClaw itself wrote
there is left out.

## NVDA's developer info of an object, from NVDA+f1
NVDA+f1 writes everything NVDA knows of the navigator object to its log. Say: what did the developer info say, or what is
its window class in the developer info, or compare the last two objects I checked. Handles and what is typed into a
password field are never said.

## Which command a key ran in input help, and whose it is
NVDA+1 turns input help on and off; while it is on, NVDA writes each key and its command to its log. Say: which keys did I
try in input help, or which add-on does that key belong to. VisionClaw says whether the command is NVDA's or an add-on's.

## When NVDA started, its settings, NVDA Remote, Java and UI Automation
Say: when did NVDA start, or how long has NVDA been running. Say: when were my settings last saved. Say: is NVDA Remote
connected, did Java support start, or which UI Automation version does NVDA use.

## NVDA's logging level, and when NVDA's log is off
Say: what is NVDA's logging level. VisionClaw never changes it. It is in NVDA's settings, which NVDA+control+g opens, under
Privacy and Security, in the combo box Logging level. Info is enough for errors. When the log is off, VisionClaw offers to
open those settings, which changes nothing.

## What VisionClaw never reads from NVDA's log
At the levels Input/output and Debug, NVDA's log holds every key you type and everything NVDA says. VisionClaw only counts
those lines: it never reads them out, never gives them to a model and never writes them to its own log. Nothing is sent
anywhere, and the log is read only when you ask.

## Where NVDA's log is, for a bug report
Say: where is NVDA's log file. NVDA+f1 opens NVDA's log viewer. NVDA+control+shift+f1 pressed once marks a starting point,
and pressed again copies what NVDA logged since then to the clipboard.
