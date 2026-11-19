<!-- Written on 2026-11-18 from VisionClaw's own code: claw/profiles.py and profiletools.py (an NVDA setting for
one program only), claw/followups.py (a request that follows the one before it), claw/dates.py and datetools.py
(a date chosen in a calendar), claw/voice.py, voiceinput.py and voiceui.py (asking by voice), claw/advice.py (which
model fits what you want to do); and on 2026-11-19 from claw/understand.py, wordtools.py, claw/worksheet.py,
claw/codeplan.py and claw/pictures.py (how words are understood, your own words, the work sheet, an add-on written
piece by piece, questions about a picture) and claw/busy.py (status updates while VisionClaw takes long), and claw/modelpick.py,
claw/corrections.py and claw/llm.py (picking the model for each job, a correction kept, votes). When the code
changes, read it again and bring these up to date; do not write them from memory. Each section is short on
purpose: one section is one answer, and it is given to the user word for word by the smallest models.
Nothing may stand between this comment and the first heading but the title, or it becomes a section. -->
# VisionClaw: settings for one program, follow-up requests, calendars, and asking by voice

## Changing an NVDA setting only in one program, only in this program, with a configuration profile
Say what you want and add: only in this program. For a program you name, be in it first. VisionClaw asks, then
keeps the setting in an NVDA configuration profile that NVDA turns on by itself whenever that program is in
front. Other programs stay as they were. To put it back, say undo that while you are in that program.

## Changing a setting everywhere, in every program, or only here when a program has its own settings
Say everywhere, or in every application, to change NVDA's normal setting for all programs. Where the program in
front already has settings of its own and you do not say which you mean, VisionClaw asks: only in this program,
or everywhere. After a change everywhere it tells you which programs keep a value of their own.

## Which programs have NVDA settings of their own, and removing a program's own settings
Ask: which programs have their own settings. VisionClaw names each program, its configuration profile, and what
it changed there. To take them away, be in the program and say: remove the settings for this program. It always
asks first, because a deleted profile cannot be brought back. NVDA's own window for profiles is NVDA+Control+P.

## Follow-up requests: do that again, a bit more, the other way, too fast, say that again, the second one
After a request you can lean on it. Do that again repeats it. A bit more does the same once more; the other
way, too much, or too fast turns it round. Say that again repeats the last answer. The same in Word does it
there. And the pitch, or open the second one, is written out in full first, and VisionClaw tells you how it
understood you.

## Working through a task when you are stuck or the usual way does not work, step by step
Say what you want and that you are stuck: I'm stuck, I want to attach a file to this email. VisionClaw looks at
what the program offers, finds the thing that leads there, tells you its key, and presses it if you say yes. It
asks before every step, checks in after three, stays in this one program, and tells you what it did.

## VisionClaw's own voice, a different voice for VisionClaw, customising it in NVDA's Speech settings
Say: customise VisionClaw's voice. NVDA's Speech settings open, and the synthesizer, voice, rate, pitch and volume
you choose there are for VisionClaw alone. While that window is open NVDA speaks with that voice too; when you
close it your own voice is back. To stop using it, say: turn off your own voice.

## Choosing a date in a calendar or date picker that takes no keys, picking a date
Have the calendar showing, then say: pick 14 March 2027 in this calendar. VisionClaw asks, presses the
calendar's own button for the next or previous month until the right month shows, then presses the day, and
says what it did. A calendar that is only drawn is read from the window's picture; then check the date field.

## Asking VisionClaw by voice, speaking a request instead of typing it, dictating
Press NVDA+Alt+V, or Alt+V in the Ask VisionClaw window, and speak after the high beep. VisionClaw stops
listening when you stop speaking; a lower beep means it is working out your words. What it heard is put into
the box and read to you. Press Enter to send it, or correct it first. Nothing is done before you send it.

## The speech model for asking by voice: downloading it, choosing another, deleting it, privacy
The first time you ask by voice, VisionClaw asks whether to download the speech model Qwen3-ASR, about 1 GB.
Your words are then turned into text on this computer and are sent nowhere; nothing of them is kept. A larger
model can be chosen in VisionClaw's settings. To delete it, say: delete the speech model.

## Which model to use for what, and whether to switch to a smaller, larger or different model
Ask: which model should I use for describing pictures, should I switch to a smaller model, which model is best for
writing add-ons. VisionClaw suggests one from your graphics card and memory, what was measured and how requests went
with each model on this computer. It changes nothing: you choose in the models window, NVDA+Alt+M.

## The JAWS Migration Assistant: what a JAWS keystroke or JAWS command is in NVDA
With the add-on JAWS Migration Assistant running, ask: what is JAWS's Insert+F7 in NVDA. VisionClaw looks the
keystroke up in JAWS's own key map and tells you what it does in JAWS and which NVDA command and key does the
same. That add-on's own helper is NVDA+Shift+J, then K, then the JAWS keystroke.

## ClassicSpeech: how much NVDA says, verbosity levels, speech and sound schemes, voice profiles
With the add-on ClassicSpeech running, ask: set ClassicSpeech to Advanced, say less about each control, which
speech schemes do I have, switch to the scheme and its name, turn schemes off, open voice profiles. VisionClaw
asks first, uses ClassicSpeech's own commands, and undo that puts a change back.

## Understood as: how VisionClaw understands casual words, slang and other ways of saying something
Before it decides what to do, VisionClaw reads casual words as the plain words it knows: take a peek at the
screen is look at the screen, kill the typing echo is turn off the typing echo. When the meaning was changed,
the answer begins Understood as. Text in quotes, text to type, names and searches are never changed.

## Teaching VisionClaw a word of your own, your own words, forgetting a word you taught
Say: when I say shh, I mean stop talking. From then on that word is understood that way. Which words have I
taught you lists them. Forget the word shh forgets one; forget all the words I taught you forgets all. They are
in the file understanding.md in VisionClaw's data folder.

## The work sheet of a request: the plan in small pieces, where it is and when it is deleted
Every request has a work sheet, a Markdown file with the plan and what each step is given and found, in the
folder work of VisionClaw's data folder. Each model is fed only its own piece of the work from it. It is deleted
when the request is done, failed or was stopped.

## An add-on written piece by piece, and why one was written as one piece
VisionClaw reads a request for an add-on into pieces: one key or one thing that happens by itself each. Plain
code writes the key, the event and the program; the model writes only the lines inside one piece. Something
every hour, at NVDA's start or a settings panel is written as one piece, and you are told why.

## Asking about a picture in several parts, one question at a time
A question about the screen with several parts, such as what is in this photo and is there any text in it, is
asked of the model that sees one part at a time, each with the rule of its kind. You hear each answer after its
own question.

## Status updates while VisionClaw takes long, how far it is, and turning them off
When a large model or high thinking keeps you waiting, VisionClaw says how far it is after 15 seconds of quiet,
and again every 15 seconds. NVDA+Alt+P says it at any time; NVDA+Alt+X stops it. In VisionClaw's settings, Status
updates while VisionClaw takes long sets 10, 15, 30 or 60 seconds, or never.

## Letting VisionClaw pick the model for each job, which model it picked, picking models by itself
In VisionClaw's settings, Which model does each job: your own choice, or VisionClaw picks from the models on this
computer for each request, without asking. It picks the largest that fits your graphics card, a model for code when
it writes an add-on, and a faster one only if you said you want speed. Ask which model are you using to hear it.

## No, I meant: correcting VisionClaw when it got your request wrong, and keeping the correction
Say no, I meant, and what you wanted, or not that, and what you meant. VisionClaw does that instead. When it went
well, it asks once whether to understand your first words that way from now on; with a yes they are kept as your
own words. To undo it, say forget the word, and the words.

## Small models asked more than once, votes, why a small model answers the same question several times
A small model that chooses among a few fixed answers is asked three times, and the answer most of them gave is
taken. It makes small models a little steadier and costs a little time. Larger models are asked once.
