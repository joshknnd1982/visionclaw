# Plan: what VisionClaw learns from NVDA's own log

Written on 2026-11-19 for VisionClaw 1.18.0. The owner said: "I also want visionclaw to have access to the various logs of
nvda itself, info, debug, etcetera", "if nvda logging is disabled, then such skills can't be used until user turns on
some sort of nvda logging in nvda settings currently under privacy", "visionclaw can query the various nvda logs to get
all kinds of realtime info. this is for new visionclaw skills, system prompts, future features", and "info logs can give
you much more info than that. make plans for info about objects and other logged items", then "implement the plan as
features".

Everything below was read from NVDA 2026.3.1's own source (tag release-2026.3.1), never written from memory. When a newer
NVDA is out, read its source again and correct the message texts in `claw/nvdalog.py`.

## The rules for every part

- VisionClaw reads NVDA's log on this computer and sends nothing anywhere.
- Only entries of the levels Info, Debug warning, Warning, Error and Critical are read. Entries of the levels Input/output,
  Debug and Debug unredacted hold the keys you typed and the words NVDA spoke: they are counted, never read out, never
  given to a model, and never copied into VisionClaw's own log.
- When NVDA's logging is off, VisionClaw says so and where to turn it on: NVDA's settings, the category Privacy and
  Security, the combo box Logging level. Info is enough for everything in this plan except the debug warnings, which
  need Debug warning or lower. VisionClaw offers to open that page; it never changes the logging level itself.
- Plain code reads the log and says what it found. A model only explains one error in plain words when you ask what it
  means, and that sentence says it is the model's.

## What NVDA writes at the Info level, and what VisionClaw makes of it

### 1. Your NVDA session
NVDA writes when it starts ("Starting NVDA version ..."), the Windows version, the Python version, its configuration
folder, "NVDA initialized" when it is ready, "Add-ons are disabled" when it was started without them, and "Exiting" when
it closes normally. The log of the run before is kept as nvda-old.log.
Feature: "when did NVDA start", "how long has NVDA been running", "did NVDA close properly last time", "was NVDA started
with add-ons off". A log of the run before that has no "Exiting" means NVDA did not close normally: it crashed, froze or
was ended, and VisionClaw says what the last entries were about.

### 2. Speech and braille drivers
NVDA writes "Loaded synthDriver ...", "Falling back to previous synthDriver ...", "Searching for next synthDriver" and
"Falling back to next synthDriver ...", and "Loaded braille display driver '...', current display has N cells."
Feature: "why did my voice change", "which braille display did NVDA load and how many cells", "did my synthesizer fail".
VisionClaw tells the story in order: which driver was asked for, that it failed and why, and which one NVDA fell back
to.

### 3. Objects: NVDA's developer info
When you press NVDA+F1, NVDA writes "Developer info for navigator object" with everything it knows about the object:
name, role, states, value, description, location, process, whether it can take the focus, its Python class, the program
(app module, product name, version, architecture), the window (handle, class name, control ID, styles, text), and, by
the interface the program uses, IAccessible (accName, accRole, accState, accValue, accDescription, the child ID,
IAccessible2's unique ID) or UI Automation (automation ID, class name, framework ID, the patterns it offers, provider
description, runtime ID). NVDA also opens its log viewer; Escape closes it.
Features:
- "what did the developer info say", "what is its window class", "which framework is this button made with", "does it
  have an automation ID": the newest object of the log, one field at a time, in plain words.
- "compare the last two objects I checked": what differs between the two newest developer infos, field by field.
- What tells the object apart (its automation ID, window class, framework, role and name) is written on the learning
  scratchpad of the program, by plain code, when you ask about it, so that fixes, names and add-ons for this program
  can use it later.

### 4. Input help: which command a key runs, and whose it is
With input help on (NVDA+1), NVDA writes "Input help: gesture ..., bound to script ... on ..." for every key you press.
That says the key, the command and where the command lives: NVDA itself, an app module or an add-on.
Feature: "which keys did I try in input help", "what was the last key I tried in input help", "which add-on does that
key belong to". The place of the command is matched to an installed add-on by plain code.

### 5. Freezes
NVDA writes "Core frozen in stack!" as an error, then "Starting freeze recovery after N seconds" and "Recovered from
freeze after N seconds". Feature: "did NVDA freeze", "how long did NVDA hang", with the program that was in front when it
froze where the log says so.

### 6. Settings and profiles
NVDA writes "Loading config: ...", the configuration it uses when it starts (secrets taken out by NVDA itself), "Base
configuration saved", "Saved configuration profile ...", "Profile triggers saved" and "Reverted to saved configuration".
Feature: "when were my settings last saved", "did NVDA save my profile", "were my settings reverted".

### 7. Other parts of NVDA
UI Automation's version, whether Java Access Bridge was started, NVDA Remote's connections ("Successfully connected as
leader", "Client connected", "Leader session disconnected", and more), MathCAT, update checks, and the crash handler.
Feature: "is NVDA Remote connected", "did Java support start", answered from the newest entries.

## Realtime: the log as it is written

- **What just happened**: "what did NVDA log just now", "what happened when I pressed that": only what is new since your
  last request, through NVDA's own fragment marks or a position kept in the file.
- **A failed step explained**: when a step of VisionClaw fails, the errors NVDA wrote during that step are added to what
  the step reports, by plain code, in plain words with the add-on's name, so that the model's next try and the answer
  you hear know why.
- **A change checked**: after VisionClaw switches a speech or braille driver or changes a setting, the errors NVDA wrote
  meanwhile are said; a driver that fell back is said to have fallen back.
- **Recent trouble goes with a question about it**: a question such as "why did speech stop" or "why is NVDA slow" is
  given the newest errors, freezes and driver fallbacks as what is known, for the model that chooses.
- **A watch for errors, if you want it**: a setting, off until you turn it on, says one sentence when NVDA logs an
  error, naming the add-on or part of NVDA it came from, at most once a minute for each.

## For later

- Debug warnings (need the level Debug warning): count, for a stubborn program, how often NVDA could not read a
  property of its controls, as one more fact for the inspection of a program.
- A bug report for NV Access or an add-on's author: a Markdown file with NVDA's version, Windows, the add-ons and the
  errors, without anything typed or spoken, written for you to attach yourself; nothing is sent.

## Skills and instructions

- An instruction for answers made from NVDA's log: name the add-on or the part of NVDA a line is from, say an error in
  plain words, never read out code, file paths or the numbers of threads, and say when it happened.
- Skills: NVDA went silent, an add-on causing trouble, NVDA froze or is slow, what NVDA's developer info says, which add-on
  a key belongs to, did NVDA close properly, NVDA's logging level.
