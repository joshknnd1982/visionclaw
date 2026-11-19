<!-- Written on 2026-11-18 from VisionClaw's own code: claw/profiles.py and profiletools.py (an NVDA setting for
one program only), claw/followups.py (a request that follows the one before it), claw/dates.py and datetools.py
(a date chosen in a calendar), claw/voice.py, voiceinput.py and voiceui.py (asking by voice), claw/advice.py (which
model fits what you want to do). When the code
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
