# Plan: the ten things from the article, in VisionClaw

Written on 2026-11-19, before anything was built. The owner gave an article that lists ten things JAWS's AI agent
is said to do, and said: "adapt this article so all of these features work with visionclaw. I want the user to be
able to do all of these. coordinate with other sessions so it works as good as it possibly can. first: plan this
out. make a markdown file with a plan, then follow the plan."

This file is that plan. It was kept up to date while the work went on: the order of work near the end says what
was done, and the last two parts say what turned out differently and what is not claimed.

## How VisionClaw does these things, and why not the way the article describes

The article's agent sends the screen to a large model in the cloud, which decides and clicks. VisionClaw runs small
models on the user's own computer, and nothing leaves it. So every scenario is built the way everything in
VisionClaw is built:

- **Plain code finds, measures and decides wherever it can.** A colour is measured from the pixels, a blank line is
  found in the pixels, a seat is read from its name, a document is formatted through Word's own interface. A small
  model is far less sure of any of these than plain code is.
- **A model gets one small question at a time**, and only where sight or wording is needed: what a picture shows,
  what a joke is, what a square of a puzzle holds.
- **Facts first.** What the web page or the program itself tells NVDA is used before any picture.
- **The user stays in charge.** Everything that changes something is asked about; what cannot be taken back
  (buying, booking, installing, accepting terms) is always asked about, whatever the settings say.
- **Say what happened**, in words, and say when a reading comes from a picture or from a model, which can be wrong.

## Where VisionClaw stood before this work

The article's own example sentences were put to VisionClaw's plain code (no model) on 2026-11-19:

- Already right: all three settings requests (10), both form requests (7), the date in a calendar (1).
- Half right: the launcher request (8) was split well, but "open the Settings menu" and "turn on UI narration and
  subtitles" were taken for NVDA's own settings; the knob (5) went to arrow keys for the knob, not to a number.
- Wrong or not understood: the installer (9), the scanned form (6), the picture in a chat (4), the document (3),
  the human checks (2), swatches, seats and room photos (1).

## The ten scenarios

### 10. NVDA's settings in plain words

Already there (`change_setting`, also only for one program, and undone with "undo that").

- To do: check the three sentences end to end against the real list of NVDA's settings: "only speak words when I
  type" is two settings (typed words on, typed characters off); "stop reading every punctuation mark" is the
  punctuation level; "talk faster" is the rate.
- To do: where one request means two settings, both are changed and both are said.

### 9. Programs NVDA cannot read, and installers

Already there: things clicked by name from the window's picture, working through a task step by step.

- New, `step_through` (`claw/wizard.py`, `wizardtools.py`): a button pressed page after page until something is
  reached. "Uncheck any bundled toolbars in this installer and click Next until the installation starts."
  On every page: the page is said in one line; a checked box that offers something extra is unchecked and named;
  a box that accepts licence terms is never ticked without a question; the button that starts the installation is
  asked about. It stops when the button is gone, when the words it waits for show, or after a fixed number of pages.
- Routing: "navigate this window and remap my function keys" goes to working through a task.

### 8. Game launchers, and reading what a game shows

Already there: clicking by name in a picture, a named control turned on, questions about a picture in parts.

- Routing: inside a launcher or game, "open the Settings menu" is a click there, not Windows' settings; "turn on UI
  narration and subtitles" is two controls of the program, both set.
- New kind of question about a picture: a grid or table is read row by row, each value with its heading.

### 7. A form that will not send

Already there (`form_trouble`): fields the page marks as wrong or required and empty, the page's error messages,
the reading position put on the first.

- New: where the page tells NVDA nothing, plain code looks at the picture of every field: a field whose outline is
  red while the others are not is named, and the reading position is put on the first (`claw/colours.py`).
  This is measured from pixels; no model is asked.
- "Put my focus in the first required field" also moves the focus into the field, not only the reading position.

### 6. A scanned PDF that is only a picture

- New, `fill_blank` (`claw/spots.py`, `claw/paper.py`, `papertools.py`): the label is read from the user's words,
  found in the text of the picture; the blank line or box that belongs to it is found in the pixels; it is
  clicked, and the text is typed. "My name" is taken from what the user asked VisionClaw to remember, or asked
  for; it is never made up. Afterwards the place is read again and the user is told whether the text is there.
- "Click the dotted line labelled Authorized Signature at the bottom of the page" is the same without typing.
- A check box next to a label is clicked the same way.

### 5. A drawn knob set to a number

Already there: `set_control` sets a number where the program offers its value; arrow keys for any knob.

- New (`claw/target.py`, a hook in `controltools.py`): a knob that exists only in the picture is set to a number.
  It is moved one step, the number shown near it is read from the picture before and after, and the steps go on
  until the number is the one asked for, or as near as the knob's own steps allow. Where no number is shown,
  that is said, and the arrow keys stay.
- "Open the preset browser and select Warm Vocal Reverb", "click the Bypass toggle": clicks by name, as before.

### 4. A picture in a chat

Already there: the picture under the focus described; a photo found inside a chat message.

- New, `look_picture` (`claw/images.py`, `picturetools.py`): which picture is meant is read from the words (the
  latest in the chat, the one my coworker just shared, the product photo, the photos of the gallery); it is found
  from what the page or program tells NVDA, or in the window's picture; cut out; and asked about in parts: its
  text word for word, what it shows, and, when asked, why it is meant to be funny.
- New kinds of question in `claw/pictures.py`: a joke, a colour.

### 3. A Word or Google Docs document formatted, and its layout checked

- New, `format_document` (`claw/docformat.py`, `doctools.py`): in Microsoft Word, through Word's own interface,
  the one NVDA itself uses. What the words ask is read by plain code: a style (APA 7, MLA 9) from a table, and any
  of font, size, line spacing, margins, first-line indent, hanging indent for the references. The question names
  every change; all of it is one step for Word's own undo. The answer says what was changed and what the style
  also asks that VisionClaw did not do.
- New, `check_layout`: how many pages, how much is on the last page, a table wider than the page, text boxes and
  pictures that overlap or reach outside the page; from Word's own numbers, not from a picture.
- Google Docs has no such interface. There, VisionClaw works Google's own menu search, one command at a time, and
  types only after NVDA confirms that the search box has the focus. What Google's own page of keyboard shortcuts
  does not offer is said to be not possible there.
- Word is not installed on the computer this is built on: tested against a stand-in written from Microsoft's
  documentation.

### 2. Checks that ask whether you are a person

These checks exist to stop programs, and they shut out blind people when the audio way is missing or broken.
VisionClaw makes a check **perceivable and workable for the person in front of the computer**, as a screen reader
should; the person answers it.

- New, `human_check` (`claw/humancheck.py`, `checktools.py`):
  - says which kind of check the page has, and names the ways through it that need no sight first (the check box
    by keyboard, the audio challenge, the site's accessibility option);
  - presses the "Verify you are human" or "I'm not a robot" box where the keyboard cannot reach it;
  - for a puzzle of pictures: reads what is asked, and says what each square shows, one square at a time; the
    user then says which squares to select, and VisionClaw clicks those and the Verify button;
  - for a slider or a piece to be dragged: takes hold of it for the arrow keys and says where the gap is.
- What it will never do: answer a check by itself or in the background, try again by itself, hide that a program
  is pressing for the person, or imitate a hand's movement to get past a check. The rule that a challenge put to
  VisionClaw's own downloads is never worked around stays as it is.
- Said plainly to the user: these checks are made to be hard for programs, so this will not always get through.

### 1. Shopping and booking

Already there: clicking by name, fields filled in, a date chosen in a calendar, working through a task.

- New, measured colours (`claw/colours.py`): the main colours of a product photo are measured from its pixels and
  said with the model's answer, so "navy or black" does not rest on a small model alone.
- New, `pick_option` (`claw/shopping.py`, `shoptools.py`): a size, colour or storage option chosen by its name or,
  for a swatch with no name, by its measured colour; and "confirm the storage is set to 256GB" answered from the
  option's own state.
- New, `pick_seat` (`claw/seats.py`): the seat map read from the names of its seats (row, letter, free or taken),
  or from its picture and legend; window, aisle, front, back, near a row; the best few are said, and one is
  clicked after a question. Where the map does not show the wing, that is said.
- New, a question before anything is bought: before a button that buys, books or pays is pressed, by any tool, the
  total is read from the page word for word and the user is always asked.
- Room photos: `look_picture` with "the photos of the gallery", each photo asked the user's question.
- VisionClaw never types a card number, a password or a security code; the user types those.

## What is shared

- `claw/colours.py`: a colour named in plain words from its pixels; the main colours of an area; the colour of an
  outline; which of several colours is nearest to the one asked for.
- `claw/spots.py`: places in a picture found by plain code: words of a label, lines, boxes, a grid of tiles.
- `claw/images.py`, `picturetools.py`: the pictures on a page or in a window, and which one is meant.
- Skills, one for each scenario, so the models word their part well for a blind user.
- A note, `visionclaw-sighted-help.md`, with the words that ask for each of these, for questions about VisionClaw itself.
- Planning notes and patterns, so each sentence goes to the right job; every new job gets its line in the help.

## With the other sessions

Three other sessions are working in this same folder:

- "Visionclaw prompt orchestrator" is releasing 1.11.0 (understanding casual words, work sheets, add-ons written
  piece by piece, questions about a picture in parts). Used here: the work sheet feeds my steps; my questions
  about pictures go through its parts and kinds; casual wordings of the ten scenarios become lines of
  understanding.
- "Visionclaw accessibility optimization" (a larger model for hard cases, notes on stubborn programs, names for
  unlabelled controls). Used here: what was found out about a stubborn program is kept in its notes; a step that
  fails after the usual rounds may be offered to the larger model.
- "Smallclaw/visionclaw optimization" (VisionClaw picking the model for each job, votes for small models'
  choices, recall by concepts). Used here: my jobs say what they need so the right model is picked; a small
  model's choice among found things gets its votes.

Rules between us: I work only in new files of my own until 1.11.0 is pushed; shared files get small additions, said
before and after; only my own files are staged by name; the graphics card is used by one session at a time.

## Order of work

Every step was done on 2026-11-19; what was tested and how is in `docs/STATUS.md` under "Ten things that used to
need sighted help".

1. Built and tested: the shared parts: `colours.py`, `spots.py`.
2. Built and tested: scenarios 7, 6, 5 and 4: red marks in `form_trouble`, `fill_blank`, a knob to a number in
   `set_control`, `look_picture`.
3. Built and tested: scenarios 3, 2 and 1, each in files of its own, by three helpers working at the same time:
   `format_document` and `check_layout`; `human_check`; `pick_option`, `pick_seat` and the question before a
   purchase.
4. Built and tested: scenario 9, `step_through`; scenarios 10 and 8, by rules in the planner and two lines of
   understanding.
5. Done after 1.11.0 was pushed: the eight jobs in the planner, each offered only where its own function finds it
   in the words; the tools registered (113 in all); the question before a purchase in the click and in the walk;
   card numbers and passwords never typed.
6. Done: three new skills and nine older ones that are now also for the new jobs; the note
   `visionclaw-sighted-help.md` with its gate.
7. Done: `tests/test_ten.py`, `test_ten_tools.py`, `test_docformat.py`, `test_shopping.py`, `test_humancheck.py`;
   `python tests/run_all.py` passes with the other sessions' work in the folder.
8. Done: two evaluation sets, each written before it was run. With Qwen3.5 9B: 42 of 49 and 27 of 30 on the first
   run; 47 of 49 and 30 of 30 after a rule was added against them, which is no blind measure any more.
9. Done: both help files, the changelog, `docs/STATUS.md`, `docs/TESTPLAN.md`, `CLAUDE.md`.

## What turned out differently from the plan

- **A slider in a check** is dragged by the user in pointer mode, not with the arrow keys for a dial: those let go
  of the mouse button after every step, and a check takes each letting go as an answer.
- **Google Docs**: VisionClaw changes nothing there. It tells the keys Google lists and how to use Google's tool
  finder. Typing into the tool finder by itself waits until it can be tried in a real browser.
- **The note** is called `visionclaw-sighted-help.md`.
- **APA's own website** answers a program with a challenge; it was not worked around, and Purdue OWL's pages were
  read for what APA and MLA ask. No first-line indent is set for APA by itself, because no page that could be read
  states it; the answer says so.
- **No planning notes** were added: every new job is decided by its own function, so the model that chooses is not
  asked about them.
- **Not used yet**: the accessibility session's access notes and its larger model for a step that fails.
- **Not committed and not built**: the work is in the shared folder with the other sessions' work for 1.12.0;
  committing and building wait for the owner's word.

## What will not be claimed

None of this has run inside NVDA, in a real browser, in Word, in a real installer, a real plug-in, against a real
check or on a real shop's website. It was tested with pictures drawn by the tests, with stand-ins for NVDA and for
Word, and with the real model choosing the job. `docs/TESTPLAN.md` lists the runs to make inside NVDA, Word first.
