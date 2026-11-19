# VisionClaw

Ask the [NVDA screen reader](https://www.nvaccess.org/) for anything in plain language, fully offline.

VisionClaw is an NVDA add-on that joins three things on your own computer:

- a small **Qwen vision model** that looks at the screen,
- a small **Qwen coder model** that checks plans and writes code,
- an **agent core** modelled on [SmallClaw](https://github.com/XposeMarket/SmallClaw), which breaks a request
  into small steps and carries them out with tools inside NVDA.

You type what you want. The two models agree on how to do it, then do it one small step at a time, telling you
the progress as they go. Nothing you do is sent to the internet. No accounts, no API keys, no usage limits.

VisionClaw is a fork of [VisionMate](https://github.com/athee06/VisionMate) by Athiban Vijay and keeps
everything VisionMate does: image descriptions, the overlay for windows NVDA cannot read, photo descriptions in
chat apps, and names for unlabelled buttons.

> **Status.** Everything is tested with plain Python, with stand-ins for NVDA, Windows, the mouse and the
> internet, and with the real models through the bundled engine. Inside NVDA 2026.3.1 the owner has run the
> models window, a first set of requests, five tests of version 0.4.0 and three of 0.8.2; **most of the test plan
> has not been run inside NVDA yet**. Expect rough edges and please report them. See
> [docs/STATUS.md](docs/STATUS.md) for exactly what was tested.

<!-- news: written by tools/write_help.py from manifest.ini; do not change it by hand -->
This README is for VisionClaw 1.15.1.

## What is new in 1.15.1

- Ask which version of something is installed, and VisionClaw says that version and nothing more. Press NVDA+Alt+C and say "which version of VisionClaw do I have", "what version of NVDA am I running", "what version of Access8Math is installed" with any add-on's name, or "what version of this program is it". Before, "tell me the version of visionclaw I have installed" read out the whole list of add-ons.
- Ask about several at once, "what versions of NVDA and VisionClaw do I have", and you hear one line for each. An add-on that is turned off is said to be, and one you name that is not installed is said not to be.
- Only when you say you are new to this, as in "I'm a beginner screen reader user, what version of NVDA do I have", or asked VisionClaw to remember that you are new to NVDA, does one sentence follow on where to find the version yourself next time, such as NVDA+N, then H for Help, then About.
- The version is read from NVDA itself, the add-on's own manifest and the program, by plain code: no model is asked and nothing goes online. To look for a newer VisionClaw, press NVDA+Alt+U or say "check for a new version of visionclaw", as before. Tested with plain Python and stand-ins for NVDA; not yet run inside NVDA.

## What was new in 1.15.0

- Ask about the control you are on in your own words, and VisionClaw answers at once from what NVDA knows, without asking you what you meant. Press NVDA+Alt+C and say "what is the focused control", "what does this button do", "what happens if I press Enter here", "is this checkbox checked", "is this button greyed out", "does this have a shortcut key", "what is the navigator object on" or "what's under my mouse". In browse mode it is the link, button or field at your reading position.
- The answer starts with what you asked: yes or no for a state, then the control's kind and name, the window and program, its state, its value or selected text, its place in its list, what it is inside of, its description and shortcut key, how to use it from the keyboard, and NVDA's own key for next time, such as NVDA+Tab for the focus. A control without a name gets the name you saved for it, or one read from its picture, said with probably where it is not sure. Asked what a button does where nothing says it, the model guesses from its name and picture, and the answer says it is a guess. Nothing is pressed or changed.
- VisionClaw no longer asks you to choose between two ways that only look and change nothing, such as looking at the screen and looking it up in NVDA. It tries one, what NVDA says before a picture, then the other if the first finds nothing, and tells you so. It still asks first when one of the ways would change something. A step that only looks and fails is followed by the other way instead of a question.
- A question VisionClaw finds no job for, such as "tell me a joke" or "what's 15 times 12", is looked up in NVDA, the program, the window and Windows, and you are told plainly when nothing is found, instead of being asked to choose a plan. "Switch to focus mode" and "go into focus mode" run NVDA's own command, and "is the remember me box ticked" is no longer taken as something to remember.
- Measured with the real Qwen3.5 4B for both jobs on two new sets of requests in casual words: on the set written to tune it, 34 of 64 right with 4 questions to you before, 61 of 64 with none after; on the held-out set, 35 of 60 with 2 questions before, 55 of 60 when first run, and 59 of 60 with none after three small rules made from its misses. Not yet run inside NVDA.

How to use each of these is explained in its own part of this README, further down.
<!-- /news -->

## What you can ask

Press **NVDA+Alt+C**, type a request, and press Enter. For example:

- *Make NVDA speak a little faster.*
- *Check and see if my recycle bin needs to be emptied.* *Empty the recycle bin.* *Open the Recycle Bin.*
- *Open Notepad.* *Open my Downloads folder.* *Open Bluetooth settings.* *Switch to Firefox.* *Close this window.*
- *Turn down my system volume.* *How much disk space do I have left?* *What is in my downloads folder?*
- *Create a folder called Taxes in my documents.* *Rename the file budget to Budget 2026.* *Delete the file old notes.*
- *Go into my Windows settings, turn down my system volume, close Windows settings, then go to gmail.com in my
  Google Chrome and tell me how many emails I have.* (Several things in one request, done in order.)
- *If you see the Recycle Bin, open it.* *If Notepad is open, close it.*
- *Find the settings button in this app, then turn the volume up a bit and turn the equalizer down.*
- *In this dialog, turn on my NVIDIA GPU for this program.*
- *Turn off the typing echo and set punctuation to all.*
- *How do I read the title of this window?* (You are told the keys, for next time.)
- *How can I use the keyboard to navigate my desktop?* *How do I switch between open windows?* *How do I rename a file?*
- *What is browse mode?* *What does NVDA+T do?* *What does Windows+D do?*
- *What can I do here?* *Which key is for the Save button?* *Which windows are open?*
- *Learn about this program.* *Learn about this game.* Then: *How do I duplicate a line?* *Delete the notes on this program.*
- *What is on my screen?* *Read the text in this window.*
- *What is the focused control?* *What does this button do?* *Is this checkbox checked?* *What's under my mouse?*
- *Press the Play button in this window.* (Works in windows and games NVDA cannot read.) *Press Control+S.*
- *Remember that I use a braille display with 40 cells.* *What do you remember?* *Which skills do you have?*
- *Give this program a hotkey that clicks Send.*
- *Pinch the map with two fingers.* *Swipe left with three fingers.* *Press hard on the drum pad.*
- *Turn left.* *Look up a little.* *This game has its own mouse pointer.* (For games that read the mouse directly.)
- *Is a controller connected?* *Turn on controller mode.* *Make the X button on my controller click Play.*
- *Write an add-on that beeps when a link gets the focus.*
- *Write an add-on that beeps when a link gets the focus, says the time with NVDA+Alt+T, and only works in Firefox.*
  (Written piece by piece.)
- *Take a peek at the screen.* *Kill the typing echo.* *Give the Save button a click.* (Casual words are understood.)
- *When I say shh, I mean stop talking.* *Which words have I taught you?* *Forget the word shh.*
- *What is in this photo, and is there any text in it?* (Asked one part at a time.)
- *Open bbc.co.uk*, *Search the web for the weather in Boston*, *What does this page say about refunds?*
- *Type garden gloves into the search box and search.*
- *Which speech synthesizer am I using? What braille display do I have, and how many cells does it have?*
- *Switch my speech synthesizer to eSpeak.*
- *Save the add-on hello key as a file.*
- *Do a deep inspection of this website.* Then: *Fix all of it*, or *Fix number 2.*
- *Give this site keys to move between posts.* *Make NVDA+Alt+P press the Play button on this page.*
- *What does the Clock add-on do? Which keys does it have?*
- *What time is it?* *What is the date today?* *Tell me the time and the date.*
- *Tell me everything NVDA knows about this control.* *What is the window class of the focused control?*
- *What does the function api.getFocusObject do?* *Do a full audit of NVDA.*
- *Open the VisionClaw log.*

You do not need to know NVDA. VisionClaw finds the right NVDA setting or command from your description.

## How it works

1. **Bite-size steps.** Your request is split into its separate parts. Each part is matched to a short, fixed
   list of steps, one tool each, such as "find the setting" then "change the setting". Small models are good
   at choosing between a few named options and poor at inventing plans, so that is all they are asked to do.
2. **The models must agree.** Each model decides, on its own, how to handle each part. If they choose the
   same, the work starts. If not, each is told the other's choice and decides again. If they still differ,
   **you are asked** and pick from the choices, but only when one of the two ways would change something: when both
   only look, VisionClaw tries one, what NVDA says before a picture, and the other if the first finds nothing.
   **With one model for both jobs** there are not two to agree, and VisionClaw does not say that there are:
   the model chooses once, checks a plan it wrote itself, and you are asked when it is not sure of that plan.
   Its choice is also checked against your own words by plain program code. If your words point to something
   else, the model looks again; if it still chooses differently, **you are asked** which of the two you meant,
   again only when one of them would change something.
3. **One step at a time.** For each step a model fills in one small form, and plain program code does the rest.
   When a step fails, the model sees the error and corrects itself; if it stays stuck, the other model gives it
   a hint; if that does not help, you choose whether to skip, retry or stop. A way that only looks and has another
   way waiting is followed by that way instead, without a question.
4. **You hear the progress.** Every step is announced. **NVDA+Alt+P** says where the task is at any time, and
   when a large model or high thinking keeps you waiting, VisionClaw says how far it is by itself (see "While
   VisionClaw works: status updates").
5. **You can always stop.** **NVDA+Alt+X** stops the task at once, even in the middle of a model's answer.
6. **Honest answers.** What VisionClaw says it did is taken from what the tools actually reported, and it tells
   you plainly when a part could not be done.
7. **It learns.** When a step first fails and then works, the lesson is kept on your computer and used for
   similar requests later. The models can also read NVDA's own user guide and notes about NVDA's add-on system.

## How VisionClaw understands your words

VisionClaw reads what you say the way a text adventure reads its player: some words are understood as other words
that mean the same, before anything is decided. "Take a peek at the screen" is understood as "look at the screen",
"kill the typing echo" as "turn off the typing echo", "give the Save button a click" as "click the Save button",
"punch in control c" as "press control c", "google how to bake bread" as "search the web for how to bake bread",
"dump the bin" as "empty the recycle bin", and "hey VisionClaw, ... for me please" loses its greeting. This is done
by plain program code, from lines written in a Markdown file that comes with VisionClaw (`understanding.md` in its
`claw` folder); no model decides it, and nothing goes online. Small models read plain words much better than slang.

- **You are told.** When the meaning of a word was changed, the answer begins "Understood as", with your request as
  it was understood. A spelling or a greeting that was left out is not said.
- **Your own words stay yours.** Words in quotes, text you ask to have typed, a name you give, what is to be
  searched for, web addresses, file names, keys, and every request to remember something, to make a skill or to
  teach a word are never changed.
- **A way of saying what to do counts only where something to do begins.** "Fire up Notepad" opens Notepad, but
  "why does the fan fire up" is left as it is.

### Your own words

Teach VisionClaw a word or phrase of your own. Say *when I say shh, I mean stop talking*, *understand zap as turn
off*, or *by brb I mean lock the computer*. VisionClaw asks you first (unless you turned questions off), and from
then on that word is understood that way, before everything else, anywhere in a request, also when it is all you
say. The answer then begins "Understood as".

- *Which words have I taught you?* lists them.
- *Forget the word shh.* forgets one. *Forget all the words I taught you.* forgets all of them, always after a
  question.
- They are kept in the file `understanding.md` in VisionClaw's data folder, one line each, which you can read and
  change in any editor; a line you write there counts at once.
- A word of fewer than two letters, an everyday word like "it" or "the", and a word that means itself cannot be
  taught: they would change nearly every request. You are told why.

### Questions about a picture, one at a time

A question about what is on the screen is put to the model that sees in its separate parts. "What is in this photo,
and is there any text in it?" is two questions, asked one after the other with the same picture. Each gets the one
rule of its kind right after it, where a small model heeds it most: text is read exactly as it is written; a count
gives the number first; "is there" is answered yes or no first, then where; a colour is named in plain words; people
are described without saying who they are; a chart is told by its title, its axes and its trend. You hear each
answer after its own question. Your own words are always the question.

### Add-ons and questions about a picture understand your words too

The whole request is understood first, as above. Then the part of VisionClaw that writes an add-on reads your words
again with words of its own: "make an add-on that chimes whenever focus hits a link" is read as "beeps whenever focus
lands on a link", and "yells 'new mail' when a dialog pops up" as "says 'new mail'". The part that asks about a picture
does the same to know what kind of answer you want: "what's scribbled on the whiteboard" asks for what is written,
"tally up the icons" for a count, "what's lit up" for what is highlighted; the model is still asked in your own words.
Words in quotes, the words an add-on is to say, and keys are never changed. These words are in understanding.md, under
headings that end ", in add-ons" and ", in questions about a picture"; your own words count there too. The description
window answers your questions as before.

### When VisionClaw got it wrong: say what you meant

Say "no, I meant turn off the typing echo", "not that, the notification area" or "that's not what I asked, I wanted
the Start menu". VisionClaw does what you meant instead, and tells you which request it takes as corrected. When that
went well, it asks once: "Should VisionClaw understand ... as ... from now on?". Say yes, and your first words are kept
with your own words, so that the next time they are understood rightly at once. Say no, and nothing is kept. It asks
only when "Remember things" is on its first choice. To undo it, say "forget the word" and the words.

## The work sheet: every request in small pieces

Every request has a work sheet: a Markdown file with the plan, what each small step is given, and what it found. It
is the one place each question to a model is made from, so that a small model gets only its own small piece of the
work: a step is given what the steps of its own part found, not everything found so far, and a piece of an add-on is
given its own section and nothing of the others. A step that speaks of "it" or "there", and a step a model planned
itself, are given everything found before it, as before.

The work sheet is in the folder `work` of VisionClaw's data folder while the request runs, so you can open it in
any editor to follow along. **It is deleted when the request is done**, also when it failed or you stopped it; one
left over because NVDA closed in the middle of a request is deleted when VisionClaw starts. What happened is still in
VisionClaw's own log, when the log is on.

## Install

1. Download **[VisionClaw.nvda-addon](https://github.com/joshknnd1982/visionclaw/releases/latest/download/VisionClaw.nvda-addon)**,
   which is always the newest version (or pick a version on the [releases page](https://github.com/joshknnd1982/visionclaw/releases)), open the
   file, confirm the installation, and restart NVDA.
2. If VisionMate is installed, disable it in the Add-on Store: VisionClaw includes it and uses the same keys.
3. A welcome window opens where you **choose your models**. Press Enter to download them. While they download,
   press Space to hear the progress. An interrupted download continues from where it stopped.

## Your settings stay yours

VisionClaw changes an NVDA setting only when you ask it to, and only the setting you asked about.

- **Only what you asked about.** Before a setting is changed, plain code checks that your request says
  something about that setting. If it does not, the change is refused, whatever a model decided.
- **You see what you asked next to what will change.** The question reads, for example: "You asked: speak a bit
  faster. Change speech rate from 50 to 60?"
- **Every change is written down**: what it was, what it became, when, and which request asked for it.
- **"What did you change?"** lists the changes that still stand.
- **"Undo that"**, or "put the speech rate back", puts a setting back to what it was. If you ask to restore
  something VisionClaw never changed, it says so and changes nothing.

Installing or updating VisionClaw changes no NVDA setting.

### A setting only for one program

*"Make NVDA speak a little faster, only in this program."* *"Turn off the typing echo just in Notepad."* *"When
I'm in Word, set punctuation to all."* Say what you want and add where: only in this program, just in this app,
only here, or the program's name while you are in it. Plain code reads that from your own words; no model
decides it.

NVDA does this with a configuration profile, which it turns on by itself whenever that program is in front.
Where the program has none yet, VisionClaw tells you so and always asks before it makes one, whatever your
settings say. The profile is named after the program, as NVDA itself would name it. The answer says what the
setting was and what it is now in that program, and that other programs are as they were.

- **Only while that program is in front.** If you name a program that is not the one in front, nothing is
  changed and you are told to switch to it first. That way a setting is never changed in the wrong place.
- **"Undo that"** puts the setting back, while you are in that program. From elsewhere VisionClaw changes
  nothing and tells you where to say it.
- **"Which programs have their own settings?"** names each program, its profile, and what VisionClaw changed
  there. **"Remove the settings for this program"** deletes the program's profile after a question, because NVDA
  cannot bring a deleted profile back.
- **When it cannot be done, nothing is changed, and you are told why**: a setting NVDA keeps the same for every
  program, a profile you turned on by hand (it counts before every program's profile, and takes every change),
  profile triggers switched off, or an NVDA that keeps nothing on this computer.
- If your words narrow a request down and no program can be read from them, as in "only in my browser", the
  question says "This will apply in every program" before anything changes.

NVDA's own window for profiles is NVDA+Control+P.

**Everywhere, or only here.** NVDA writes a change to whichever profile is on. So once a program has settings
of its own, a plain "make NVDA speak faster", said in that program, would quietly land in that program alone.
VisionClaw does not leave that to chance:

- *"Speak words as I type in every application"*, *"make NVDA speak faster everywhere"*: NVDA's normal
  configuration is changed, also while the program in front has a profile of its own. If that program keeps a
  value of its own for the setting, you are told so, and how to change that too.
- *"Stop announcing capital letters in Word"*: a program named with "in" alone is enough, where it is a program
  everybody knows or the one in front.
- You say neither, and the program in front has settings of its own: VisionClaw asks, "only in Word, or
  everywhere?"
- After any change, it names the programs that have a value of their own for that setting and keep it.
- "Undo that" puts each change back where it was made.

### Requests that follow the one before

After a request you can lean on it, in the same session of NVDA:

| You say | What happens |
|---|---|
| do that again, again, try again | The request before is done again, also one that failed or was stopped. |
| a bit more, more, keep going | The same once more. |
| the other way, too much, too fast, slower | The request before with its direction turned round, or set to the one you name. |
| say that again, what did you say | The last answer is said again; nothing is done. |
| the same in Word, do that again in Notepad | A question is asked about that program; anything else is done after switching to it. |
| and the pitch? open the second one, delete the last one | Written out in full first, from the request before and its answer. |

Plain code writes the first five out by itself. The last kind a model writes out, and plain code checks that
every word it wrote was said by you or by VisionClaw; if not, the model's words are not used. You are always
told how you were understood: the answer begins "Understood as: ...". Everything that changes something still
asks first. "Open it" may mean what has the focus, so it leans on the request before for three minutes only;
the others for ten. Nothing of this is written to the disk.

## Models

Every model is always offered, whatever your computer is. Your computer only decides which one is suggested.
Larger models are more accurate and slower. You can change your choice at any time with **NVDA+Alt+M**.
Ask **"what model is installed"** or "which model are you using" to hear which model does which job, what is
stored on your computer and how big it is, and where a loaded model runs. That answer is read from your
settings and your disk by plain program code; a model does not know its own name and is not asked.

| Use | Model | Download |
|---|---|---|
| Vision | Qwen3.5 0.8B, the smallest and least accurate | 0.7 GB |
| Vision | Qwen3.5 2B (suggested) | 1.8 GB |
| Vision | Qwen3.5 4B | 3.2 GB |
| Vision | Qwen3.5 9B | 6.2 GB |
| Vision | Qwen3-VL 2B from VisionMate, if it is already on your computer | none |
| Coder | Qwen2.5 Coder 0.5B, the smallest and least accurate | 0.5 GB |
| Coder | Qwen2.5 Coder 1.5B (suggested) | 1.0 GB |
| Coder | Qwen3.5 4B, used for coding | 2.6 GB, or none if you chose it for vision |
| Coder | Qwen2.5 Coder 7B | 4.4 GB |
| Coder | Qwen3.5 9B, used for coding | 5.3 GB, or none if you chose it for vision |
| Coder, for hard cases only | Qwen3 14B, larger and slower, used only when the others could not, after you say yes | 8.4 GB |

The models come from Hugging Face. Each file is pinned to one version and checked against its SHA-256 after
the download. You can also use VisionClaw with a vision model only; then it describes images and runs the
overlay like VisionMate, and Ask VisionClaw waits until you add a coder model.

### Which model for what you want to do

Ask: *which model should I use for describing pictures*, *should I switch to a smaller model*, *which model is best
for writing add-ons*, *suggest a model*. VisionClaw suggests one model for each thing you want to do: planning and
carrying out what you ask, describing pictures and the screen, writing and fixing add-ons, or answering faster. The
suggestion stands on your graphics card and memory, the models on your disk, what was measured with each model in
VisionClaw's own tests and on which day (a model that was not measured is said to be not measured), and your own
review: how your requests went with each model on this computer, counted in models-went.json in VisionClaw's data
folder, and anything you asked VisionClaw to remember about a model, such as *remember that the 9B is too slow for
me*. No model is asked, and nothing goes online. Nothing is changed either: you choose in the models window,
NVDA+Alt+M.

You can also ask about *stubborn programs*, *the model for hard cases* and *which speech model should I use*. The
answer says whether your graphics card has room for the Q6_K of the suggested model, whether the model for hard cases
runs on your computer and how (on the card, shared with the processor, or not at all), and that the speech models come
only as Q8_0. In the models window, the button **Suggest models for what I want to do** asks the same with check boxes:
check what you want VisionClaw for with Space and press Enter. NVDA says each choice as a check box, checked or not
checked, and says it again when Space changes it. The reasons are put into the box at the top and the
suggested models into the lists; nothing is downloaded until you press the first button, and you can still choose
others.

### Letting VisionClaw pick the model for each job

In VisionClaw's settings, **Which model does each job** has two choices. The first, where it starts, is "The models I
chose in the models window; VisionClaw only suggests": your own choice does every job, as always. The second is
"VisionClaw picks from the models on this computer for each request, without asking". Then, before each request,
VisionClaw picks among the models you have downloaded, by plain code and without a question:

- For planning and for pictures, the largest model that fits your graphics card with room to spare, because that is the
  most exact one that still runs fast; with no graphics card that holds one, the largest that fits your memory.
- For writing an add-on, the largest model for code that fits on the graphics card beside it, or the same model when it
  writes code too, so that nothing more is loaded.
- For checking a plan, the same model when it can, so that nothing more is loaded.
- A faster model only when you said you want speed, such as "the 9B is too slow for me", and only for a request that is
  not a hard one and has no picture and no code in it.
- A model with which your requests went badly on this computer is passed over while another can do the job.

It never downloads anything, never picks a model you have not downloaded, and never picks the model for hard cases.
Nothing is said while it picks: press NVDA+Alt+P to hear what it picked, or ask "which model are you using". To go
back, choose the first choice again.

Keep your own choice and still hear VisionClaw's view: ask "which model are you using", and VisionClaw also says which
models on this computer it would pick for planning and for code, but only where they differ from yours. It never says
this by itself, and nothing changes until you choose.

### The model for hard cases

VisionClaw's everyday models are 9B or smaller. One larger model, **Qwen3 14B**, in Q4_K_M or Q6_K, is kept for what
they could not do:

- an add-on that does not pass VisionClaw's checks, will not start, or fails again after it was corrected;
- a control of a stubborn program where its picture and what is reported about it say different things about how it
  is worked, or neither can tell.

Then VisionClaw asks: "... VisionClaw has a larger model for hard cases on this computer ... Try once more with it?"
It is slower: loading it and its answer may take a few minutes, and the everyday models are unloaded meanwhile and
come back with the next request. NVDA+Alt+X stops it. Its work goes through every check, like any other. It reads and
writes text only: no Qwen model of that size sees pictures.

Choose it in the models window, NVDA+Alt+M, in the list **Model for hard cases** under the coder lists: None, Qwen3
14B Q4_K_M (suggested) or Qwen3 14B Q6_K. None is chosen until you choose otherwise, so nothing of 9 GB is downloaded
unasked. The check box **Ask me before the model for hard cases is used** is checked at first. Say *fix my add-on
Beeper with the model for hard cases* to use it at once. When it is not on your computer, the answer to a hard case
says where to get it; nothing is downloaded by itself.

Measured on 2026-11-19, in Q4_K_M on a graphics card of 8 GB shared with the processor: of nine add-ons written piece
by piece, all nine did what was asked, where those of Qwen3.5 9B did eight, in about the same time; written as one
piece, six where the 9B's did four. Of twelve controls a program draws itself, it told six rightly, as the 9B did, but
made fewer wrong guesses, at about 17 seconds a control where the 9B took one or two.

### The very smallest models: one small question at a time

The two smallest models, Qwen3.5 0.8B and Qwen2.5 Coder 0.5B, are for computers that can run nothing larger.
They are fast and often wrong when they have to fill in a whole form at once. So VisionClaw treats them
differently, by itself:

- It asks for one thing at a time: first which setting, then which value, each in a call of its own.
- Wherever the step before found the possible answers, the model can only pick one of them: an id that was
  found, a name that was listed, on or off, one of a setting's options, or a number. It cannot write anything
  else. This narrowing is used for the larger models too.
- An answer that only repeats the question is asked for again.
- When you ask about something that was looked up, such as a web page, the answer is a line of what was
  found, word for word. If nothing found mentions what you asked about, VisionClaw says so. The small model is
  not asked to put it in its own words, because that is where it made things up.

In VisionClaw's settings, "Ask the models one small question at a time" is Automatic (only for the very small
models), Always, or Never. Always is slower and may help any model that makes mistakes.

### Small models are asked a choice more than once

When a small model, such as Qwen3.5 2B, Qwen3.5 0.8B or Qwen2.5 Coder 1.5B, chooses among a few fixed answers (what
kind of request this is, which item is meant, on or off), it is asked three times, and the answer most of its answers
gave is taken. The first answer is its most likely one; the others are written with a little chance in them, and asking
stops as soon as two agree. Larger models are asked once. Measured with the real Qwen3.5 2B and 0.8B choosing the job:
on 202 requests with the 2B, one more was right and one question to you fewer, none was worse, and choosing took a third
longer; with the 0.8B nothing changed. Most of choosing the job is done by plain code, so this changes little there;
forms filled in by a small model were not measured.

### Newer models

These are the newest Qwen models that come in small sizes, as of 17 November 2026. The Qwen team's newer
families (Qwen3.6, Qwen3.8, Qwen3 Coder) only exist in sizes of 27 billion parameters and more, which is too
large for most computers.

When newer small Qwen models appear, they are added to a list on VisionClaw's page on GitHub. To get them
without waiting for a new version of the add-on, press **Look for newer models** in the models window
(NVDA+Alt+M, then Choose or download other models). VisionClaw asks first, then reads that one list, and adds
what is new to the two lists of models. It never does this by itself. Nothing about you or your computer is
sent; GitHub sees your internet address, as any website does. Every model on the list is checked before it
is offered: only Qwen models, only from Hugging Face, each file pinned to one version with its size and
SHA-256, which the download verifies. A model that needs a newer VisionClaw is not offered, and you are told.

### Seeing, removing and swapping models

- **NVDA's settings, under VisionClaw,** list the models on your computer: each one's name, its size, and
  whether it is in use for vision, for coding, or not at all, with the total disk space they take.
- **NVDA+Alt+M** (or "See, remove or swap models" in settings) opens a window with the same list. Press Space
  on the models you want to remove and choose "Remove checked models", or choose "Remove all models". You are
  asked before anything is deleted, and told how much space it frees. A removed model can be downloaded again
  at any time.
- **"Choose or download other models"** in that window lets you pick smaller or bigger ones. When the new ones
  are ready, VisionClaw offers to remove the ones you no longer use; you decide.
- If you remove the model that is in use, VisionClaw uses another one that is still on the computer for that
  job, if there is one. With no vision model left, it asks you to choose one the next time you need it.

## Where the models run

In NVDA's settings, under VisionClaw, choose:

- **Automatic** (default): a dedicated graphics card if one is found, else another graphics chip through
  Vulkan, else the processor.
- **Dedicated graphics card.**
- **Vulkan**: a built-in graphics chip if there is one, which leaves a dedicated card free.
- **Processor only.**

If the chosen place fails to start, VisionClaw moves down the list by itself and keeps working.

**A model larger than the card** (the model for hard cases on a card of 8 GB, or a Q6_K that does not fit) is shared
between the graphics card and the processor: as much of it as fits goes on the card. A model that should fit but does
not start whole is tried that way too before the card is given up. "What model is installed" says when a model is
shared with the processor.

**Two large models.** When both models do not fit on one graphics chip together, such as Qwen3.5 9B and
Qwen2.5 Coder 7B on an 8 GB card, the second one is put on another graphics chip or on the processor, so both
stay loaded and neither has to be loaded again. Only when there is no room anywhere do the two take turns.
You can turn this off in settings; then they always take turns on the best chip. The Last task box in the Ask
window says where each model ran.

## What each model does

- **The vision model** looks at the screen, plans, and fills in the small forms that drive each step.
- **The coder model** is the second opinion: it decides on its own how each part of a request should be
  handled, and work starts only when the two agree. It gives a hint when the vision model is stuck on a step,
  checks the result of freely planned work, and writes, debugs and corrects add-ons.
- **The vision model reviews the coder's add-ons**, and describes the window when a fix is about something on
  screen.
- **One model for both.** You can choose one model for vision and for code, such as Qwen3.5 9B and "Qwen3.5 9B,
  used for coding": it is stored once and loaded once. It then does all of the above itself, and VisionClaw
  calls it "the model". A second look by the same model may catch less than a second model would.

## Reasoning level

In the Ask VisionClaw window and in settings: **Automatic, Off, Low, Medium, High**. Automatic decides for
each request: simple requests think less and answer sooner, new code gets the most care. Higher levels let the
models write out their reasoning before deciding, retry more, review generated code more often, and turn on the
thinking mode of models that have one (Qwen3.5). The context size given to a model is chosen for every single
call from how long that call is.

## Working the computer for you

VisionClaw does things on the computer itself, not only inside NVDA. Each of these is one small tool; which
thing you mean is read from your own words by plain code, and a model at most chooses among the few things that
were found. You are asked before anything is opened, closed or changed, unless you turned that off in the
settings; what cannot be undone is always asked about.

| You say | What happens |
|---|---|
| *Open Notepad. Open my Downloads folder. Open the Recycle Bin. Go into my Windows settings. Open Bluetooth settings.* | The thing is found by its name among the programs of the Start menu, what is on your desktop, the folders, tools and settings pages of Windows, and your own files, and opened as a double click would. When several things have the name, you are asked which. |
| *What is in my system tray? Tell me all objects that are currently in the system tray. Is NVDA running in the system tray? How many icons are in the system tray? Which programs are on my taskbar? What icons are on my desktop? Read my notifications. What is in quick settings?* | What is there is read from what Windows tells screen readers, word for word, with no model and no picture, and you are told the key that goes there. The hidden tray icons are read too: VisionClaw shows them for a moment through Windows itself and hides them again, and the window you were in comes back to the front. The notifications, quick settings, the Start menu and clipboard history exist only while they are open, so they are opened with their own key, read, and left open; Escape closes them. |
| *Right-click the volume icon in the system tray. Click the Firefox button on the taskbar. Click Dropbox.* | Something inside the system tray or on the taskbar is clicked there, with the mouse in its middle, after a question. A thing you name that is in no window is looked for in the notification area and on the taskbar, and you are asked before it is used there. |
| *Open the Start menu. Click the Start button. Go to the system tray. Open quick settings. Go to the taskbar. Open the notification center. Open Task View. Open the Run dialog. Open clipboard history. Open the emoji panel.* | The part of Windows itself is opened with Windows' own key, and you are told that key for next time and how to move inside it. These are in no program's window, so they are never among a window's items. Where a program could have a Start button of its own and nothing in its window is called Start, you are asked whether the Start menu of Windows is meant. |
| *Click the recycle bin* (while another program is in front) | When nothing in the window has the name you said, and it is a program, folder or place of Windows, VisionClaw offers to open it by its name instead. When the item a model picked has none of your words, you are asked before anything is clicked. |
| *Check my recycle bin. Is my recycle bin full?* | How many items it holds, how much room they take, and whether emptying is worth it for the room left on your drive. Answered at once; no model is asked. |
| *Empty the recycle bin.* | Always asks first, with the number of items and their size: what is emptied is deleted for good. |
| *Turn down my system volume. Set the computer's volume to 40 percent. What is the volume of my computer?* | The volume of the whole computer, not of NVDA's voice. Turning it down stops at 10 percent so that NVDA can still be heard. Muting, or a number below 10, is refused when no braille display is in use, and asked about when one is. |
| *Switch to Firefox. Close Notepad. Minimize all windows. Maximize this window.* | The window your words name is worked, and named in the answer. A window that stays open after it was asked to close is said to be still open. Where no window has that name, as for a settings panel inside a program, Escape is offered. |
| *What is in my downloads folder? Find the file named budget. How many PDFs are in my documents?* | Your Desktop, Documents, Downloads, Pictures, Music and Videos folders are looked through, the newest first, with size and date. Nothing is changed. |
| *Create a folder called Taxes in my documents. Rename the file budget to Budget 2026. Move the file report.pdf to my documents. Copy the file budget to my desktop. Delete the file old notes.* | The file or folder is found by its name in your own folders; when several fit, you are asked which. You are told what will be done and asked first. Nothing is ever overwritten. Deleting moves it to the Recycle Bin and is always asked about. *Undo that* puts a rename or a move back. |
| *How much disk space do I have left? How much memory does my computer have? How long has my computer been on? Am I connected to the internet? Which programs are running?* | Answered from Windows itself. Nothing is sent anywhere to find out. |
| *Lock my computer. Restart my computer. Shut down the computer. Cancel the shutdown.* | Always asks first. A restart or shutdown waits 30 seconds and can be called off in that time. |

### Several things in one request

Join up to eight things with commas, *and* or *then*. Plain rules split the request where they can tell for
certain, so a long request is not left to a small model to cut up. Each thing gets its own small steps, each
step is announced as it starts ("Step 3 of 8: Closing the window"), and the answer says in order what was
really done, and what was not.

*"Go into my Windows settings, turn down my system volume, close Windows settings, then go to gmail.com in my
Google Chrome and tell me how many emails I have."* becomes: open Windows Settings; turn the computer's volume
down; close the window Settings; open gmail.com in Chrome; read the page and answer.

A web address is opened in the browser you name, where it is installed. What a web page shows of your mail
depends on the page: you must be signed in there, and VisionClaw reads only what the page says.

### Things that depend on something

*"If you see the Recycle Bin, open it."* *"If Notepad is open, close it."* *"If my recycle bin is not empty,
empty it."* VisionClaw checks first and tells you what it found. For "if you see", it looks at the names NVDA
has where you are, then at the text on the screen, and only then asks the model that sees; a yes that rests on
the model alone is said to be the model's, which can be wrong. When the condition does not hold, the rest is
not done, and the answer says so. Other kinds of "if" are planned as before.

### Options inside a program

*"Find the settings button in this app, then turn the volume up a bit and turn the equalizer down, then close
settings."* *"In this dialog, turn on my NVIDIA GPU for this program, and turn off the media keys."* The control
is looked for by its name: first in what NVDA knows of the window, then on the other pages of a dialog that
has tabs, then in the window's picture. A check box or switch is turned on or off, a slider up or down or to a
number, through the control's own action where the program offers one, with the keyboard next, and with the
mouse last. You are asked first and told what it was and what it is now. Where the control is only in the
picture, VisionClaw says that its reading is from the picture and can be wrong.

### A date in a calendar that takes no keys

*"Pick 14 March 2027 in this calendar."* *"Choose next Friday in the date picker."* *"Set the departure date to
January 5."* Have the calendar showing. The date is read from your own words by plain code, also when it was
spoken and its numbers came as words ("the fourteenth of March twenty twenty-seven"). A date in numbers that
can be read two ways (3/4/2027), and "next Friday", are asked about. A date without a year is the next one.

VisionClaw looks for the calendar in the web page, then in the window as NVDA knows it, then in the window's
picture, for a calendar that is only drawn. It asks, presses the calendar's own button for the next or previous
month until the right month shows, then presses the day. After every press the calendar is read again; nothing
is counted blind. You are told the date with its weekday, how many months it went, and what the calendar shows
afterwards. A day that is greyed out is not pressed. Where the arrows have no names, which one goes forward is
found by trying one press, and that is said. For a calendar read from a picture you are told to check the date
field. At most 60 months are gone by pressing.

### The router: fewer choices for the model

A small model chooses well among a dozen things and badly among eighty. So before a model is asked what to do,
plain code leaves out what cannot be meant: what works a web page when no browser is in front and the words
name no page, what needs a game controller when none is connected, and what reads everything from your words
when your words do not say it. What your own words point to is always offered. Where the words can hardly mean
anything else, as with the Recycle Bin or a shutdown, no model is asked at all. And when a model finds nothing
that fits among what it was offered, it is offered everything, once.

### How VisionClaw plans, checks and learns

Where a request is about is read from your words: the window in front, a web page, or a part of Windows itself
such as the system tray, the taskbar or the desktop, and each place is read in the way that can really reach it.
What was found is then checked by plain code. When a way of looking did not find what you asked, as when a picture
of the desktop "cannot see the system tray", VisionClaw tries the next way that only looks, once, tells you so, and
says what that way found. The way that found nothing is counted as not working for that request and the way that
answered as working, in plans.json on this computer. Words that mean the same thing count as one, so what was
learned for one wording is used for another: "tell me all objects in the system tray" and "which icons are in my
notification area" are the same request to VisionClaw. A model still chooses, and plain code still checks.

A question about how to do something is answered with the keys, and nothing is done; a question that begins with why
is answered. When the model's choice also fits your words, VisionClaw goes with it instead of asking you; it asks you
only when your words clearly point elsewhere and one of the two ways would change something. Between two ways that
only look it does not ask: it tries one, then the other if the first finds nothing. How well VisionClaw chooses is measured on sets of requests in words it
was never tuned on, with the real model, and a change is kept only when it measures better.

## Working through a task when the usual path isn't clear

*"I'm stuck, I want to attach a file to this email."* *"Walk me through exporting this as a PDF."* *"I can't find
how to change the font here."* *"The usual way doesn't work, I want to print this."* Say what you want and that
you are stuck. VisionClaw looks at what the program in front offers: the web page as NVDA keeps it, the
window's controls as NVDA knows them, and, where NVDA knows next to nothing, the texts and icons in the window's
picture. It finds the thing that leads to what you want, tells you what it is and its key, and asks:

- **Yes, press it**: it is pressed, VisionClaw looks again, tells you what that brought up, and goes on from there.
- **No, only tell me where it is**: nothing is pressed; you get the thing and its key, to do it yourself.
- **Stop here**.

The rules it keeps, which are the ones JAWS's Companion names for itself:

- **Every step is asked about**, and a step that may not be possible to take back (Send, Delete, Pay) says so.
- **It checks in on a longer task**: after three steps it asks whether to go on. At most eight steps in one go.
- **It stays in one program.** When a step brings another program to the front, it stops and tells you that the
  next step is there.
- **Its own windows are off limits.** VisionClaw never clicks, types or presses keys in its own windows; their
  controls are yours. This holds for every tool that works the window in front, not only for this one.
- **It tells you what it did**, step by step, and what is in front at the end.

Plain code ranks the things in the window by your own words, with the words menus use for the same thing
(attach and insert, save and export, settings and options). A model is asked only to choose among the few that
were found, and only where plain code is not sure.

## A voice of its own

*"Customise VisionClaw's voice."* NVDA's own Speech settings open, and whatever you choose there, the
synthesizer, the voice, its rate, pitch and volume, is used for what VisionClaw says and for nothing else. While
that window is open NVDA itself speaks with that voice, so that you hear what you choose; when you close it, your
own voice is back. *"Turn off your own voice"* makes VisionClaw speak like NVDA again and keeps the voice for
later; *"remove VisionClaw's voice"* deletes it after a question. There is also a command without a key, under
VisionClaw in NVDA's Input Gestures.

It is done the way NVDA gives "say all" a voice of its own: one configuration profile, called VisionClaw voice,
that NVDA applies only to VisionClaw's words. None of your own settings is changed. Braille is the same either way.

## With the JAWS Migration Assistant and ClassicSpeech

Two other add-ons by the same author make VisionClaw do more when they are running in the same NVDA. Without
them, these jobs are simply not offered.

**[JAWS Migration Assistant](https://github.com/joshknnd1982/jawsMigrator).** *"What is JAWS's Insert+F7 in
NVDA?"* VisionClaw looks the keystroke up in JAWS's own key map on your computer, through the assistant, and
tells you what it does in JAWS and which NVDA command, with which key, does the same. *"What is the JAWS say line
command in NVDA?"* works by the command's name and needs no JAWS on the computer. *"What did the JAWS migration
bring over?"* says when the last migration was, from which JAWS, and lists the keys of the assistant's layer
(NVDA+Shift+J). And whoever has it installed is taken to come from JAWS, so the page for people from JAWS, if you
downloaded the training material, is asked with every question. Nothing of the assistant's is ever written.

**[ClassicSpeech](https://github.com/joshknnd1982/classicspeech-nvda).** *"Set ClassicSpeech to Advanced."* *"Say
less about each control."* *"Which speech schemes do I have?"* *"Switch to the scheme JAWS Sounds."* *"Turn sound
schemes off."* *"Open voice profiles."* VisionClaw asks first, uses ClassicSpeech's own calls, tells you what it
was and what it is now, and "undo that" puts it back. JAWS's own Companion says of its Speech and Sound Schemes
and Voice Profiles that it cannot change them yet.

Neither add-on has an interface for other add-ons; VisionClaw uses names read from their source (JAWS Migration
Assistant 1.63, ClassicSpeech 1.16). Where a newer version keeps something differently, VisionClaw says so and
changes nothing. Neither was installed on the computer this was written on, so both were tested only against
stand-ins built from their source.

## While VisionClaw works: status updates

A large model, or a model set to think a lot first, can take a minute or more for one answer. So that you are
never left wondering, VisionClaw tells you by itself how far it is when you have heard nothing from it for a
while: *"Still describing the screen, 30 seconds so far. The vision model is looking at the picture."* The first
update also tells you to press **NVDA+Alt+P** at any time to hear how far it is, and **NVDA+Alt+X** to stop it.
This works for a request (NVDA+Alt+C or NVDA+Alt+V), a description (NVDA+Alt+A, W, F or D, and photos in chats),
an answer to a question in the description window, the speech model working out what you said, the icons of the
overlay being named (NVDA+Alt+O), and an add-on VisionClaw wrote being corrected.

- **What an update says**: what VisionClaw is doing and what it waits for: which step of your request it is on;
  whether a model is still starting, which a large model takes a while to do; whether it is thinking before it
  answers, and at which level of thinking; or how many of the overlay's icons are done. When the icons took long
  enough for an update, you also hear when they are all done.
- **When nothing is said**: while VisionClaw waits for your answer to a question, once the answer or description
  is being spoken or shown, and while the microphone is open.
- **Every step you already hear counts**: the quiet starts again after each one, and after you press NVDA+Alt+P.
- **Your choice**: in VisionClaw's settings, **Status updates while VisionClaw takes long, as with a large model
  or high thinking**: after 10, 15, 30 or 60 seconds of quiet, and as often while it lasts; or never. The
  suggested choice is 15 seconds. With the updates off, NVDA+Alt+P still says how far it is whenever you press it.
- **Reading on while you wait**: while VisionClaw waits for a description or an answer about a picture, other
  keys no longer stop it: you can read on, or press NVDA+Alt+P, and the description still comes. Press
  NVDA+Alt+X to stop it. Once it is being spoken, Control stops it, as before.

## Asking by voice

Press **NVDA+Alt+V**, or Alt+V in the Ask VisionClaw window, and speak after the high beep. VisionClaw stops
listening by itself when you stop speaking (or press the button again); a lower beep means it is working out
your words. What it heard is put into the request box and read to you: "You said: ... Press Enter to send it, or
change it first." Nothing is ever done before you send it. While the microphone is open NVDA says nothing,
because the microphone would hear it; the beeps tell you what is going on.

The words are turned into text on this computer, by the speech model **Qwen3-ASR** from the Qwen team (Apache
2.0), in the same bundled engine, on the processor alone. What you say is not kept and is sent nowhere. The
model is not part of the add-on: the first time you ask by voice, VisionClaw asks whether to download it,
about 1 GB, from Hugging Face, where the llama.cpp project (ggml-org) publishes it in the engine's format; it
comes only as Q8_0. In the settings you can choose the larger Qwen3-ASR 1.7B (2.3 GB) instead. "Can I ask you by
voice?" says whether it is set up, "download the speech model" gets it after a question, and "delete the speech
model" removes it after a question.

Measured on the developer's computer on 2026-11-18 with Qwen3-ASR 0.6B: 24 of 24 requests spoken by Windows'
two built-in voices were heard word for word, each about 1.7 seconds from start to text. It writes "NVDA" as
"Nvidia" unless it is told the name beforehand, so VisionClaw tells it a few names, among them the program in
front. A person speaking into a real microphone has not been tried yet.

**The names where you are.** VisionClaw tells the speech model the names you are likely to say: the program in front,
the words you taught VisionClaw, the focused control, the window's title and a few of its controls. And where it heard
a name it was told split in two, such as "wave table" for Wavetable or "side chain" for Sidechain, plain code joins it
again. Measured on 2026-11-19 with Windows' own voices and requests that name things in programs such as REAPER,
Kontakt, TeamTalk and GoldWave: 53 of 54 heard rightly, where 36 before; a name that was told but not said was not
heard instead ("click the contact button" stayed contact).

## Programs and games NVDA cannot read

VisionClaw tries the simplest way first:

- **The overlay** (NVDA+Alt+O) turns a window into a list you can move through and click.
- **"Press the Start button"**: VisionClaw lists what is in the window from its picture and clicks the item.
- **App helpers**: "give this program a hotkey that clicks Send" saves a hotkey for that program. The item is
  found by its name each time, so the hotkey still works when the window moves. Helpers are plain data, not
  code.
- **Names**: "call this button Play" names an unlabelled button from then on.
- **Add-ons**: for behaviour nothing else can give, the coder model writes a small NVDA add-on. See below.

## The web

VisionClaw uses your own browser, through NVDA's browse mode. NVDA already knows a page as links, headings,
buttons and form fields, so nothing has to be guessed from a picture.

- **Open** a web address, or **search the web** with the search engine you choose in settings (DuckDuckGo,
  Google or Bing).
- **Ask about the page** you are on. For a long page, VisionClaw picks the passages that match your question
  and has the model answer from those.
- **Follow a link or press a button** by name. Following a link needs no question; pressing a button asks
  first, because a button can send or buy something.
- **Type into a field**, and press Enter if you asked to search or send.
- **Explore a page**: "explore this page" or "what is the best way to get around this page" names its
  landmarks in order, where the main part begins, what the page has, the links of its navigation and its form
  fields, and then the NVDA keys that fit this page, the best first. Keys for things the page does not have
  are not named.
- **Find out why a form will not send**: "why won't this form submit" or "which fields did I miss" names the
  fields the page marks as not valid, the required fields that are empty, and the page's own error messages,
  each with its field, and puts NVDA's reading position on the first of them. Nothing on the page is changed.
- **Hear the headings of the page** in order with their levels, and how many links, buttons and fields it has.
  "Summarize this page" gives the beginning of each part of the page, in the page's own words.
- **Move to a place on the page**: "take me to the heading Refund policy" puts NVDA's reading position there,
  so you can read on from there with NVDA's own commands.
- **Go back, forward or reload.**

The models still run only on your computer. The browser goes online, as it does when you use it yourself.

## Making a website or a program accessible, for good

Some websites and programs fight the screen reader: buttons with no name, feeds that load more as you scroll
and never end, video players whose buttons hide, things you can click that are not buttons. VisionClaw can
inspect the place you are in, tell you what is in the way, and make fixes that stay.

**Inspect.** Ask *do a deep inspection of this website*, *inspect this window for accessibility problems*, or
*what is wrong with this button*. VisionClaw reads every control NVDA knows there, watches for a moment to
see what changes by itself, and compares the picture of the page with its text. It then tells you, in plain
numbered sentences, what it found and which of it an add-on can fix. Nothing is changed by inspecting.

**Fix.** Ask *fix all of it* or *fix number 2*, or say what you want in your own words:

- *Give this site keys to move between posts.* Two keys go to the next and the previous post, result, video
  or other repeated item. On a page that loads more as you go, the same key finds the new ones.
- *Make NVDA+Alt+P press the Play button on this page.* One key presses a control by its name, wherever you
  are on the page, under whichever name it has at the moment (Play or Pause).
- *Make a key that reads the time.* One key reads a part of the page or window.
- *Name the focused button Share on this website.* Controls without a name get one. Where the page's own code says what a
  button is, that is used; where it does not, the vision model looks at the button's picture, and you are
  told that the name is a guess.
- *Tell me when the inbox count changes.* You hear a part's new text whenever it changes.

Before anything is turned on you are told exactly what will be made, and asked. The fixes for one website
(in any browser) or one program are kept together in one add-on, named fixes and then the site or program.
It starts with NVDA from then on and stays until you say *remove the add-on* and its name. *Save the add-on
... as a file* gives you a normal add-on file to install for good or to share with someone who uses the
same site. Outside that website or program its keys do what they always do.

It is built to work the same in Chrome, Edge, Brave and other Chromium browsers and in Firefox, because NVDA
builds the pages of all of them the same way, and VisionClaw reads what NVDA has built. This part is new: it
has been tested against stand-ins for a web page and against NVDA's own source, but not yet on real websites
inside NVDA. `docs/STATUS.md` says exactly what was and was not tested.

No model writes this add-on's code. It is put together by plain code from fixed, tested parts and the list
of your fixes, so what it does can be told to you exactly and a small model cannot break it. The models
choose what you mean and name icons from their pictures. For behaviour these five kinds of fix cannot give,
the coder model can still write an add-on, as described further down.

**Names from pictures.** A control without a name is named by the model that sees, from its picture, in one to three
words that say what it does, never its colour or shape, in a short form it cannot ramble in. A larger model is also
told the program, the window and the named controls around the control; a small one is not, because it copied those
names. A name that only copies one of them is not used, and "Play button" becomes Play, since NVDA says the kind
itself. Measured on 34 drawn icon buttons: Qwen3.5 9B named 33 rightly where 29 before, Qwen3.5 2B 31 where 29, and
Qwen3.5 0.8B 23 where 24.

**A state that may be missing.** The report says when tabs report none of them as selected, and when buttons that
open or show something do not say whether it is open. Then ask *which tab is selected* or *what is open here*: the
model that sees reads it from the picture and says that it was read from the picture.

**What VisionClaw remembers about the place.** After a deep check, how each control is worked, names read from
pictures, what drew the window (its class, which tells the toolkit or game engine) and what each check found are kept
in a Markdown file for that program or website, in the folder access of VisionClaw's data folder, such as
access\reaper.md. A control the models agreed on before is not put to them again: the next check gives the same answer
at once. When VisionClaw writes an add-on for that program, the lines that fit the request go with it. The file is
yours: read it, change any line or delete it; VisionClaw only adds lines and reads it as you left it.

**When the models do not agree.** Where the picture and what is reported say different things about how a control
is worked, VisionClaw offers the model for hard cases, if it is on your computer (see Models).

What it cannot do: a control that nothing in the page's or program's code tells apart from others cannot be
named reliably, and the report says how many those are. A window NVDA cannot read at all cannot be fixed
this way; use the picture instead (*list what is in the window*, an app helper hotkey, or pointer mode).
Sites change, and a fix that no longer finds its control says so instead of doing something else.

## The control you are on

Ask about the control you are on in your own words, and VisionClaw answers at once from what NVDA knows, without
asking you what you meant: *what is the focused control*, *what does this button do*, *what happens if I press Enter
here*, *is this checkbox checked*, *is this button greyed out*, *does this have a shortcut key*, *what is the
navigator object on*, *what's under my mouse*. In browse mode it is the link, button or field at your reading
position.

The answer starts with what you asked: yes or no for a state, then its kind and name, the window and the program,
its state (checked, pressed, expanded, unavailable), its value or selected text, its place in its list, what it is
inside of, its own description and shortcut key, how it is used from the keyboard, and NVDA's own key that says it,
for next time (**NVDA+Tab** for the focus). A control without a name is given the name you or VisionClaw saved for
it; if there is none, the model that sees reads one from its picture, said with "probably" where it is not sure.
Asked what a button does where nothing says it, the model guesses from its name and picture, and the answer says it
is a guess. Nothing is pressed or changed. *Tell me everything NVDA knows about this control* still gives every
technical fact.

## Questions: NVDA is asked, then the program, then its window, then Windows

A question such as *how do I ...*, *what key ...*, *what is ...* or *what does this key do* is never put to
one place alone. Every time, VisionClaw asks four, in this order:

1. **NVDA**: every command that works where you are, with its keys; the whole of NVDA's own user guide on
   your computer; and the help of the add-ons you have installed.
2. **The program in front**: which program it is and its version, the commands NVDA has for that program, and
   the hotkeys VisionClaw made for it.
3. **Its window**: the window's title, the control that has the focus (its kind, name, value, state, its place
   in its list, its own key, and what it is inside of), the status bar, and the controls in the window that
   have keys of their own.
4. **Windows itself**: which Windows this is, which windows are open, and VisionClaw's notes on the keys of
   Windows: the desktop, the Start menu, the taskbar, the notification area, switching and closing windows,
   File Explorer, menus, dialogs, text, copy and paste, locking and shutting down. These notes were written
   from Microsoft's own page on Windows keyboard shortcuts and are part of the add-on; nothing is looked up
   online.

Each of them gives what it has in small pieces. Plain code, not a model, then decides which pieces are about
your question: a piece must be about what your question names, and words that only say "with the keyboard"
or "how do I" count for almost nothing. That is why *How can I use the keyboard to navigate my desktop?* is
answered with the keys for the desktop, and not with the NVDA command that switches the keyboard layout,
which only shares the words keyboard and desktop.

The answer says where it is from: "From NVDA", "From NVDA's user guide", "From this window", "From Windows".
Where NVDA and Windows both have an answer, as for copying text, you get both, NVDA's first. A larger model
puts the pieces into its own words; a model that is asked one small question at a time gives you the best
piece word for word. When nothing is about your question, VisionClaw says so in one sentence and names what
it asked. It does not give you the nearest thing.

In the Last task box you can read what was asked: three lines that begin "Asked NVDA", "Asked the program"
and "Asked Windows".

## Learning about the program or game you are in

Ask **learn about this program** or **learn about this game** while you are in it. You can also name one:
*learn about Audacity*.

1. **VisionClaw finds out which program it is.** It reads what Windows reports: the name of the program's
   file, what its maker called it, its version and its window's title. A model then says which of these
   names the program is known by and whether it is a game, a program or a utility. A game that runs in Java
   reports "Java" as its maker's name; the model takes the window's title instead.
2. **You are asked before anything goes online**, whatever your settings. The question says what is sent.
3. **It reads three places.** Wikipedia, for what the program is and what its article says about using it.
   Wikidata, for the address of the program's own website and of its manual. Then that website: its first
   page and up to five of its pages that are about keys, getting started, the interface or accessibility.
4. **It writes notes.** From each useful section of a page the model writes short points: what a key does,
   how something is done. Plain code then checks every point against the page: a point that names a key the
   page does not have, or whose words are mostly not in the page, is dropped. Where nothing stands, the
   page's own words are kept. The very smallest models do not write notes; their notes are the page's words.
5. **The notes are a file.** One Markdown file for each program, in the folder `notes` of VisionClaw's data
   (`%APPDATA%\nvda\addons\visionClaw\data\notes`). It says at the top that it is from the internet and may be wrong,
   and under every note which page it is from.

After that, ask your questions in the program: *how do I duplicate a line*, *which key closes a tab*, *what
is this program*. The notes are asked together with NVDA, the program, its window and Windows, and an answer
from them begins "From the notes on", with the website.

- *Which notes do you have?* lists the programs. *Open the notes on this program* opens the file, to read or
  change. *Delete the notes on this program*, or *delete all notes*, removes them after a question.
- **A page from your own browser.** Open any page about the program, and ask *add this page to the notes on
  Notepad++*. The page is read through NVDA as your browser shows it. Nothing is fetched for this, so it
  works for pages behind a search, a login or a cookie question you have answered yourself.

What this cannot do, and why: **VisionClaw itself asks no search engine.** Search engines serve people and
turn programs away; when this was built, DuckDuckGo answered with its challenge for automated traffic after
a few requests, and VisionClaw does not work around that. So a program that Wikipedia has no article about
is not found, and a program whose website is not on Wikidata gets only what Wikipedia says. For those,
search in your own browser (*search the web for ... keyboard shortcuts*), open a result, and add that page.

What is sent: the program's name, to Wikipedia; one request to Wikidata; and requests for pages to the
program's own website, as a browser would make them. Each of these sees your internet address. Every
request calls itself "VisionClaw" with its version and "NVDA screen reader add-on", and carries nothing
about you or your computer. VisionClaw's log lists every address a request went to.

## The models: what they decide, and what plain code checks

The models do more than choose a plan and put answers into words:

- For a question that only points, *what does this do*, a model is told where you are and says whether you
  mean the program, the window or the control that has the focus. Where your own words say it, as in *this
  program* or *this button*, nobody is asked.
- A model that is not one of the very smallest reads what was looked up and says which line answers your
  question, or that none does. Then you hear "Nothing that was found answers that", and the nearest thing is
  given as only the nearest. A very small model is never given that choice, because it takes it at random.
- A model names the program you are in and its kind, and writes the notes, as described above.

In each case the model chooses among things plain code found, or writes something plain code can check.

## Asking NVDA about itself: speech, braille, drivers

- Ask which speech synthesizer, voice, braille display, braille tables, drivers and add-ons NVDA has and uses,
  and how they are set.
- Every setting the synthesizer in use offers can be changed by describing it: voice, variant, rate, pitch,
  volume, and whatever else that synthesizer has. The same goes for the braille display's own settings.
- **Switching the speech synthesizer or braille display** is done with care, because a wrong switch could
  leave you without speech:
  - VisionClaw asks NVDA what is installed and in use first.
  - It **refuses** a switch that would leave you with neither speech nor braille, such as "No speech" with no
    braille display connected, and says why. It also refuses a speech volume too quiet to hear when there is
    no braille.
  - It always asks before switching, whatever your settings.
  - After the switch you confirm that the new one works. If you do not answer within 20 seconds, for example
    because nothing can be heard, **it switches back by itself**.
  - It remembers which drivers could not be started or had to be switched back on this computer, and warns you
    before trying one of those again.
- NVDA commands that can silence or close NVDA (speech mode, sleep mode, quit, restart) are also always asked
  about first, with a word on how to undo them.

### Every NVDA command, also the ones NVDA lists nowhere

VisionClaw finds an NVDA command from your description among all the commands that can be used where you
are: NVDA's own, those of your add-ons, of the program in front and of the web page. NVDA 2026.3.1 has 509
commands; 191 of them have no description and are in no list, and VisionClaw finds those too, by their names.

- A command is found by the word that tells it apart. Asked for *the current time*, a dozen commands share
  the word "current" and one is about the time; that one is found.
- **Commands that do something else on a second or third press.** One press of NVDA+F12 says the time, two
  say the date; one press reads the window title, three copy it. NVDA says so in the command's own
  description. VisionClaw reads it there and presses as often as your words ask for: *what is the date* is
  two presses, *the time and the date* gives both. Afterwards it tells you the keys and how often to press.
- *What does NVDA+F12 do?* and *which keys read the status bar?* are answered from the same list.
- When no command fits, VisionClaw says so. It does not run the nearest thing.

### Everything inside NVDA: functions, classes, objects

For people who write add-ons, and for the models when they write one, VisionClaw can look into the running
NVDA itself. Nothing is taken from a list written in advance, so it also covers your add-ons and whatever a
newer NVDA brings.

- *What does the function api.getFocusObject do?* or *which functions does NVDA have for braille?* searches
  every loaded module of NVDA and your add-ons, by name or by description, and says what the thing is, how it
  is called, what its own help text says, and what it holds or gives back right now.
- Only functions that merely report something and need nothing, like getFocusObject, are called to say what
  they give back. Nothing that changes anything is ever called this way.
- *Tell me everything NVDA knows about this control* reads every fact of the focused control: name, kind,
  value, states, shortcut key, position and size, place among its neighbours, program and process, window
  class, control id and handle, the accessibility interface, what can be done with it, what it is inside of,
  and NVDA's own class for it. The same for *the navigator object*, *the window*, *what is under the mouse*.
  Ask for one fact (*what is the window class of this control?*) and only that is said. Any other property
  can be asked for by its name.
- *Do a full audit of NVDA* counts and lists everything in the NVDA that is running: every command with its
  keys, every module, class, function, method, property and value by name, the drivers that are installed but
  not in use, and how NVDA drives your speech synthesizer and your braille display (the driver's class, its
  settings, which speech commands it understands, how many cells, how its keys are tied to commands). The list
  is saved as `nvda-audit.md` in VisionClaw's data folder; say *and show me the list* to have it opened.
  Nothing is changed by an audit, and nothing is sent anywhere.
- VisionClaw's notes on how NVDA is built inside (commands, objects, the path from text to the synthesizer,
  the path from focus to the braille cells, the places where add-ons can listen in) were written from the
  source of NVDA 2026.3.1 and are read by the models like the user guide. Ask *how does NVDA talk to a braille
  display?*

### The add-ons you have installed

VisionClaw knows the add-ons in your NVDA. *Which add-ons do I have?* lists them with their versions and
whether they are on. *What does the Clock add-on do?*, *Which keys does it have?* or *How do I set an alarm
with the Clock add-on?* are answered from what the add-on says about itself, its commands and keys where you
are now, and its own help. An add-on's commands are NVDA commands, so VisionClaw can also find and run them
for you (*say the date with the Clock add-on*), and it can change an add-on's settings when the add-on keeps
them in NVDA's configuration. The help texts of the add-ons that are on are read up on like NVDA's own user
guide.

## Ten things that used to need sighted help

These are ten things a sighted helper was needed for. VisionClaw does them on your own computer; nothing is sent
anywhere. Plain code measures and finds wherever it can: a colour from the pixels, a blank line in the picture of a
form, a seat from its name, a document through Word's own interface. A model is asked one small question at a
time, and only where sight is needed. Everything that changes something asks first. What buys, books, installs
or accepts terms is always asked about, whatever your settings say. None of this has run inside NVDA yet, in a
real browser, in Word or on a real shop's website: it was tested on pictures and programs made up by the tests.

### 10. NVDA's settings in plain words

*"Make NVDA only speak words when I type."* *"Stop reading every punctuation mark."* *"Make NVDA talk faster."*
VisionClaw finds the setting among all of NVDA's, asks, changes it and says what it was and what it is now.
"Undo that" puts it back. See "Your settings stay yours".

### 9. A program NVDA cannot read, and an installer

*"Navigate this window and remap my function keys."* VisionClaw works through it with you: it finds the next
thing to press, says its key, and asks before every step.

*"Uncheck any bundled toolbars in this installer and click Next until the installation starts."* VisionClaw asks
once, then goes page after page: it says each page with its check boxes, unchecks and names a checked box that
offers extra software or a changed home page or search, never accepts licence terms without asking you, and asks
before the button that starts the installation. It stops when the button is gone, when a press changes nothing,
when Windows asks whether the program may change the computer, and after twelve pages. It cannot judge an offer
that is worded as a choice between two kinds of installation; it reads the page and you decide.

### 8. A game's launcher, and what a game shows

*"Click the Play button in this launcher, open the Settings menu, and turn on UI narration and subtitles."* Four
steps in that program: two clicks, then each of the two options is found by its name, asked about and set, and
you are told what it was and what it is now. *"Read my character stats and skill points from the inventory on
screen"* looks at the window's picture and reads it, each part of the question on its own.

### 7. A form that will not send

*"Why won't this form submit?"* *"Put my focus in the first required field I still need to complete."* VisionClaw
names the fields the page marks as wrong or required and empty, and the page's error messages. New: where the
page tells NVDA nothing, the picture of the page is measured. A field that is outlined in red, and a line
written in red, is named, and NVDA's reading position is put on the first. This is measured from the pixels;
no model looks. Only the fields on the screen at that moment are measured: scroll and ask again for the rest.

### 6. A scanned PDF that is only a picture

*"Click the line next to Full Name and type my name."* *"Click the dotted line labelled Authorized Signature at
the bottom so I can sign."* *"Check the box next to Yes in this scanned form."* The label is found in the text
read from the window's picture, and the printed line or box that belongs to it in the pixels: to its right,
under it, or above it. VisionClaw asks, clicks there with the mouse, types, reads the place again and tells you
whether the text shows. "My name", "my email" and "my phone number" are taken word for word from what you asked
VisionClaw to remember ("remember that my name is ..."), or you are asked; they are never made up. VisionClaw
never signs for you. The program must be ready to take the click: in Adobe Acrobat, choose the Fill and Sign
tool first. A line that already has writing on it is said to have some.

### 5. A drawn knob set to a number

*"Turn the Mix knob down to 35 percent."* Where the program offers the knob's value to Windows, it is simply
set. A knob that is only drawn, as in many audio plug-ins, is moved a step at a time, and the number shown next
to it is read from the picture after every step, until it is the number you asked for, or as near as the knob's
own steps allow. Where no number shows, or it is in another unit such as dB, that is said and the knob is left
where it was; the arrow keys for a dial stay for that ("work the Mix knob with the arrow keys").

### 4. A picture in a chat

*"What does the latest picture in this chat say?"* *"Read the text in the latest image in this chat and explain
the joke."* *"Look at the screenshot my coworker just shared, what error code is highlighted?"* VisionClaw finds
that picture among the pictures the page or the program tells NVDA about, by their order and size, and leaves
out emoji and the little faces next to names. It brings the picture into view, cuts it out, reads its text and
asks the model that sees each of your questions about that picture alone. A model's answer about a joke can be
wrong, and it says when it does not understand one.

### 3. A Word document formatted, and its layout checked

*"Format this document in APA style."* *"Set the font to 12-point Times New Roman, double-space all paragraphs,
and give the References a half inch hanging indent."* In Microsoft Word, through Word's own interface. The
question names every change; one Control+Z in Word takes all of it back. The answer says what was changed and
what the style also asks that VisionClaw did not do: the title page, page numbers, heading levels. In Google
Docs VisionClaw changes nothing; it tells you the keys Google lists and how to use its tool finder, Alt+/.

*"Does my resume fit on one page?"* *"Are any text boxes overlapping?"* VisionClaw says how many pages there
are, how much is on the last one, which tables are wider than the page and which text boxes or pictures overlap
or reach beyond it. These are Word's own numbers, not a picture.

### 2. A check that asks whether you are a person

These checks are made to stop programs, and they shut blind people out when the audio way is missing or broken.
VisionClaw makes a check readable and workable; you answer it. *"What kind of check is this?"* names the kind
and the ways through it that need no sight, the surest first. *"Click the verify you are human box"* presses the
box after asking. *"What do the squares show?"* reads what the puzzle asks and says what each square shows,
numbered left to right and top to bottom. Then you say which: *"select squares 1, 4 and 7, then verify"*. *"Get
an audio challenge"* presses that button. *"Take hold of the slider"* puts the pointer on the piece, and you
drag it with pointer mode: G holds, the arrow keys move, G lets go. VisionClaw never chooses the squares for
you, never answers a check by itself, never tries again by itself, and does nothing to hide that a program is
pressing for you. These checks are hard for programs on purpose, so this will not always get through; the
site's own audio challenge or accessibility option is the surer way where it works.

### 1. Shopping and booking

*"Look at the product photo, is this jacket navy blue or black?"* The main colours are measured from the photo's
pixels and said first, then the model's answer. *"Select the dark blue colour option."* An option is chosen by
its name, or, for a swatch with no name, by its measured colour; afterwards VisionClaw says what the page marks
as chosen. *"Is the 256GB option selected?"* answers from the page's own state. *"Find a free window seat near
the front."* The seat map is read from the names of its seats, or from its picture and legend; VisionClaw says
the best few with the reason for each and clicks one after asking. Where the map does not say where the wing is,
VisionClaw says so. Before a button that buys, books or pays is pressed, by a click or while working through a
task, VisionClaw reads you what the page says is to be paid, word for word, and always asks. VisionClaw does not
type card numbers, security codes or passwords: put the focus in the field and type them yourself.

## Working the mouse from the keyboard

Sighted people click, right-click, double-click and drag on controls that give a screen reader nothing to hold
on to. VisionClaw lets you do all of that without a mouse, in three ways.

**Ask for it.** VisionClaw finds the item in the window's picture and does it:
- "Right-click the file icon", "double-click the folder", "point at the Help button".
- "Drag the file onto the Trash", "drag the volume slider to the right a little", "drag the handle down 50
  pixels".
- "Scroll down", "scroll up a little", "scroll down a page", "scroll this window to the bottom", "scroll
  right". VisionClaw turns the mouse wheel in the middle of the window, or over the control you are on, and
  then compares the window's picture before and after. So it can tell you honestly whether anything moved:
  at the end of a list it says that nothing moved, and "to the bottom" stops when nothing moves any more.
  Where the window shows a scrollbar, you also hear how far along the view now stands, in percent.
You are asked first, except for pointing, which changes nothing. The wheel is never turned over a slider, a
combo box or a similar control, where it would change a value instead of scrolling.

**In the overlay** (NVDA+Alt+O), on any item: Enter or Space clicks, Shift+Enter double-clicks, **A
right-clicks**, and **G picks the item up; G on another item drops it there.**

**Every key of pointer mode and of the overlay is one that every keyboard has**: letters, the arrow keys,
Enter, Space, Escape, Shift and Control. Small and laptop keyboards often have no Applications key, no Page Up
and Page Down, no Home and End and no function keys, so nothing depends on those. Where your keyboard has
them they still work as before: the Applications key or Shift+F10 right-clicks, Page Down and Page Up turn the
wheel, Home goes to the middle.

**Pointer mode** (NVDA+Alt+K, or ask "make this control keyboard navigable") is for a control, canvas or game
where nothing can be listed at all. The arrow keys move the mouse pointer inside the window:
- Arrow keys move one step; with Shift a fine step; with Control a far one. On a plain screen these are 20, 4
  and 100 pixels. They follow your screen: at 200 percent scaling they are twice as many pixels, so a step is
  the same to the eye on a small laptop screen and on a large 4K one, and in a small window they are made
  smaller so the pointer does not leap across it. A short tone tells you how high the pointer is, and a low
  tone that it has reached the edge.
- **I, K, J and L turn the mouse wheel about a page** where the pointer is: I up, K down, J left, L right.
  They lie under the right hand like the arrow keys. With Shift one notch. You hear how far along the view
  stands, or that nothing moved.
- **S finds the scrollbars** in the window's picture, tells you where one is and how far along it stands, and
  puts the pointer on it. G then holds it, the arrow keys move it, and G lets go.
- Enter or Space clicks, Shift+Enter double-clicks, **A right-clicks**. A click or a turn of the wheel waits
  until you have let go of Shift, Control and Alt, because held down they change what the mouse does in most
  programs; if they stay down, nothing is done and you are told.
- **G holds the mouse button down; move; G again lets go.** That is a drag done by hand.
- **T rests the pointer where it is and says what appears**: a tip, a menu that opens by itself, a preview.
- **C clicks the moment what is under the pointer changes.** Shift+C only sounds a tone then, so that you press
  Enter yourself. Any key stops the watch.
- W has the vision model say what is at the pointer. R reads the text there. P says where the pointer is in the
  window. B brings it back to the middle. H repeats the keys. Escape turns pointer mode off.
All other keys keep working as usual.

**App helpers** can right-click or double-click their item as well as click it: "give this program a hotkey
that right-clicks the canvas". They can also hover over it and say what appears, or hold the mouse button
down on it until the hotkey is pressed again.

**Scrollbars and other things made only for the mouse.** A deep inspection of a window ("inspect this window")
now also looks at its picture: plain code finds the scrollbars by their look, on a screen of any size and
scaling, and the vision model is asked what else is worked with the mouse, such as sliders, switches or a
drawing area. You are told what was found and how to work it from the keyboard. What the vision model names
is marked as its view, because it can be wrong. Scrollbars that only appear while the mouse is over them,
and scrollbars in the middle of a window rather than at its right or bottom edge, are not found by their
look; the wheel still scrolls there.

When you name the things yourself, as in "drag the New Game button onto the Quit button", your own words decide
which items are meant, not the model's copy of them.

## Controls that need more than a click

Some controls are worked by neither a click nor a drag from one thing to another. VisionClaw does each of
these from the keyboard, and tells you afterwards what happened.

- **Hovering.** "Hover over the Help icon." The mouse pointer rests on it, on a web page too, and the window is
  compared before and after: you hear the text that appeared, such as a tip or a menu that opens by itself, or
  that nothing appeared. Nothing is asked first, because pointing changes nothing. The pointer stays there, so
  you can list what is in the window again and click what opened.
- **Holding the button down.** "Press and hold the Record button for 3 seconds", "long-press the app icon".
  The button is never left down: it comes up when the time is over, when you stop the request, and at most
  after a minute. For a button you hold as long as you need it, such as push to talk, ask for a hotkey:
  "make NVDA+Alt+3 hold down the Talk button". The first press holds the button, the second press, or Escape,
  lets go, and after two minutes it lets go by itself and says so.
- **Gestures.** "Swipe left on the card", "flick up", "draw a circle on the canvas", "draw a line down then
  right with the right button held down". A swipe or line needs its direction, a shape its name: a circle
  (clockwise or anticlockwise), a tick, a zigzag, a square, a triangle, a cross, or one of the letters L, V,
  Z, N, M and W. Say small, large or a percentage for its size, slowly or flick for its speed. For any other
  shape, in pointer mode G holds the mouse button, the arrow keys draw, and G lets go.
- **Timing.** "Click the Go button as soon as it changes", "click Catch when it appears, wait up to 2
  minutes": VisionClaw watches the place and clicks at once when it changes. "Click the cookie 20 times",
  "click the drum 8 times, twice a second": clicks in a steady rhythm. Stated plainly: VisionClaw looks about
  25 times a second, so the click comes a moment after the change, and what must be hit more exactly than that
  can be missed. Something that moves all the time has no single moment VisionClaw can tell; it says so and
  clicks nothing.
- **Other buttons and keys.** "Middle-click the link", "triple-click the paragraph", "control-click the second
  file", "click Photo 3 with the Shift key held down". The key goes down before the click and always comes up
  after it.
- **A place on a thing.** "Click the seek bar 30 percent across", "click the right end of the timeline", "click
  the top left corner of the map": for a bar that is clicked where the value should be, a picture or a board.
- **Larger and smaller.** "Zoom in", "zoom out": the mouse wheel with the Control key held down, which is what a
  sighted person does with a mouse where two fingers would be used on a touch screen. You hear whether anything
  changed.
- **A pad, a colour field or a joystick**, which is dragged in any direction: in pointer mode, G holds the
  button, the arrow keys move it both ways, and G lets go.

**The inspection finds them.** "Inspect this window" or "inspect this page" now also tells you which controls
are worked in one of these ways. Plain code knows it where the control's own name or description says so
("Hold to record", "Swipe to unlock", "Sign here", "Hover for details"); for a control whose kind NVDA cannot
tell, the models look at its picture and at what is reported about it. For a control that is hovered over or
held down, "fix it" makes a hotkey: one that rests the pointer on it and says what appears, or one that holds
the button down until you press it again. For the others the report says what to ask for. A model can be
wrong, and the report says who said what.

**Every kind of control.** NVDA has 156 kinds of control. VisionClaw now knows for each of them how it is
worked, that it only holds or shows something, or that it must be looked at. It also reads what Windows
reports about a control (that it can be dragged, moved freely, scrolled or selected), what a web page's code
says (its role, that it can be dragged, that it opens a menu), and NVDA's states (checkable, editable,
draggable, has a pop-up).

What VisionClaw cannot do here, stated plainly: dragging between two different windows. Fingers, pressure
and games that read the mouse directly have their own sections below. None of this has been tried in real
programs yet, only with stand-ins for the mouse and drawn pictures.

## Fingers and pressure, without a touch screen and without a pen

Some programs are made for a touch screen or a pen: a map that is pinched, a photo that is turned with two
fingers, a list that is swiped with three, a drawing program where pressing harder gives a thicker line.
Windows lets a program touch the screen as fingers would and press as a pen would, and VisionClaw uses that
for you. No touch screen and no pen is needed.

- **Fingers.** "Pinch the map", "spread two fingers on the photo", "zoom in with two fingers", "swipe left with
  three fingers", "turn the picture 90 degrees clockwise with two fingers", "double tap the Start icon", "touch
  and hold the Record button for 2 seconds". One to five fingers. Say a little, a lot or a percentage for how
  far, slowly or flick for how fast. You name the thing; without a name it is done at the mouse pointer or in
  the middle of the window.
- **More than one way.** VisionClaw looks at the window before and after. If the touch changed nothing, the
  program probably takes no touch, and then the mouse wheel is used instead: with Control for a pinch or a
  spread, plain for a swipe with two fingers. You are told which of the two worked, and that is kept for the
  program, so the next time the working way is used at once. Nothing stands in for a turn with two fingers;
  if that changes nothing, you are told so.
- **Pressure.** "Press hard on the drum pad", "press the pad at 70 percent pressure for 2 seconds", "draw a
  line to the right with the pressure rising", "draw a circle with the pen, lightly", "erase a zigzag with
  the pen, firmly". The words lightly, firmly, hard, as hard as it goes, a number of percent, rising, falling,
  or "from light to hard" say how hard. VisionClaw presses as a pen would; with "with a finger" it presses as
  a finger, which also reports how hard.
- **You are asked first**, and whatever is put down is lifted again: when the gesture is done, when you stop
  the request, and when something fails.
- **On a computer with a touch screen**, NVDA takes every touch for itself, to read what is under your finger.
  For the moment of a gesture VisionClaw puts NVDA's own touch gestures aside, with NVDA's own function, and
  puts them back right after. It always asks before it does that, and it does not change NVDA's setting.

Limits, stated plainly. Pressing as a pen needs Windows 10, version 1809, or later; on an older Windows one
finger presses instead. A program that reads a drawing tablet through the tablet's own driver, and not through
Windows, takes no notice. VisionClaw can see whether the window changed, not whether the program felt how hard
it was pressed. A program that runs with more rights than NVDA, such as one started as administrator, cannot
be touched. None of this has been tried against a real program yet: it was tested with a stand-in for
Windows, and `python tests/live_touch.py --yes` shows on your own computer whether Windows takes the fingers
and the pen.

## Games that read the mouse directly

Many games take no notice of where Windows' mouse pointer is. They listen to how far the mouse itself moves.
Some turn the view with it and show no pointer at all; others draw a pointer of their own. Putting Windows'
pointer on a thing does nothing in either. VisionClaw can move the mouse itself, by a number of its own steps,
which such a game sees as it sees a hand moving the mouse.

- **Tell VisionClaw which it is**, once: "the mouse turns the view in this game", or "this game has its own
  mouse pointer". It asks, keeps that for the program, and uses it whenever the game hides Windows' pointer.
  When Windows' own pointer shows again, as in many menus, the usual way is used. "How does this game use the
  mouse?" says what is kept and what Windows reports: that the pointer is hidden, and kept inside the window.
  "Use the normal mouse pointer again" forgets it.
- **A view the mouse turns.** "Turn left", "turn right a lot", "look up a little", "turn around", "turn right
  500 steps". VisionClaw moves the mouse itself and tells you whether the view changed. How far a game turns
  for one step differs from game to game: "direct mouse movement is too fast" or "too slow" changes it, and
  that is kept for the game.
- **A pointer the game draws itself.** Clicking, holding, dragging and gestures on things you name work again:
  VisionClaw pushes the game's pointer into the corner of the window, where it must be whatever its speed,
  and counts from there. The first time it also measures how fast the game moves its pointer, by moving it
  three times and comparing the pictures. If clicks land beside what you name, say that it is too fast or too
  slow, or "measure the game's pointer".
- **Pointer mode** (NVDA+Alt+K): **M changes how the mouse is moved**, between Windows' pointer, the game's
  own pointer, and a view that the mouse turns, and keeps your choice for the program. For a view, the arrow
  keys move the mouse itself and Enter clicks where the game aims.
- **The inspection says so.** "Inspect this window" reports when a program hides Windows' pointer and keeps it
  inside its window, and what to tell VisionClaw then.

Limits, stated plainly. A game that refuses movements made by a program, as some games with cheat protection
do, cannot be worked this way. VisionClaw does not know how far a game turns for a step until you tell it
that it is too fast or too slow. Measuring a game's pointer needs the pointer to be the only small thing that
moves in the picture. All of this was tested with a game drawn by the test, which has a pointer of its own
with a speed of its own; it has not been tried in a real game.

## A game controller

When a game controller is connected, VisionClaw notices it and says so in one sentence. An Xbox controller,
and any controller Windows reads the same way, is fully known. A controller of another make is read through
Windows' older joystick interface, with its buttons taken to lie where they lie on most controllers; that may
not fit yours, and VisionClaw says so.

**Controller mode** makes the controller a way to work any window, whatever its controls are: standard, drawn,
moving or entirely custom. Turn it on by holding the controller's View and Menu buttons together for a second,
or with NVDA+Alt+J, or by asking "turn on controller mode". The View button turns it off. Out of controller
mode VisionClaw leaves the sticks and buttons alone, so you can play with the controller as always.

| On the controller | What it does |
|---|---|
| Left stick | Moves the mouse pointer in the window: a small push slowly, a full push fast. When it comes to rest you hear what NVDA finds under the pointer, and feel a short buzz when that is something else than before. At the window's edge the pointer stops, with a buzz and a low tone |
| Direction pad | Moves the pointer one step |
| A, B, X | Click, right-click, double-click |
| Y | Says what is under the pointer |
| Right trigger | The mouse button, for as long as you pull it: pull, move the stick and let go to drag, or keep it pulled to hold something down |
| Left trigger | Presses like a pen, as hard as you pull it, for drawing and for controls that feel pressure |
| Right stick | Turns the mouse wheel, up, down and sideways. Pressed in, it moves the mouse itself instead, for a game that reads the mouse directly; pressed in again, the wheel |
| Left stick pressed in | Says where the pointer is in the window |
| Left shoulder button, held | Makes the stick slow and exact. With it: A clicks the moment what is under the pointer changes, B rests the pointer and says what appears, X tries what is there as a dial or slider (the direction pad then works it), Y reads the text there |
| Right shoulder button, held | Makes the stick fast. With it: right and left on the direction pad jump to the next and the previous thing found in the window's picture and say its name, up looks at the window again, down finds the scrollbars, A holds the mouse button until you press it again, B clicks with the middle button, X changes how the mouse is moved, Y has the picture at the pointer described |
| Menu | Says all of this |
| View | Turns controller mode off |

**A button as a hotkey.** "Make the X button on my controller click Play", "let the left shoulder button of my
controller read the score", "make up on the d-pad of my gamepad hold down the Talk button". The button then
does that in this program, in controller mode or out of it, whenever the controller is connected, and finds
its thing by name each time. "Remove the X button on my controller" removes it.

**Asking.** "Is a controller connected?", "What do the buttons on my controller do?", "How do I drag with the
controller?" are answered by plain code and from VisionClaw's own notes, never made up by a model.

**Your choice.** In NVDA's settings, under VisionClaw, Game controller: tell me when one is connected and
listen for View and Menu held together (the default); listen, but say nothing when one is connected; or do
not look for a game controller at all.

Limits, stated plainly. VisionClaw cannot press a controller's buttons for you: a game that is only worked
with a controller needs your hands on it, and VisionClaw then describes the screen. The buzz may not come at
all, because Windows gives a controller's motors to the program in front; nothing depends on it, and every
buzz has a sound or a spoken word beside it. Whatever the triggers hold, the mouse button or the pen, comes up
when you let go, when the mode is turned off, when the controller is unplugged, and when NVDA closes.
Controller mode was tested with made-up controller states, not with a real controller in a real hand.

## Dials, knobs and sliders that are only worked by dragging

Some programs, music tools and games have a dial, a knob or a slider of their own that a sighted person drags
with the mouse, and that takes no keys at all. Say what you want: "let the arrow keys work the volume dial",
"make the gain knob work with the keyboard", "give me a hotkey for the pan slider". VisionClaw asks first, then
finds out by itself how the control is worked: through Windows itself where the program offers its value, else
with the mouse wheel, else by dragging it up and down, sideways, or around in a circle. It tries each one step
and puts it back, and compares the control's picture before and after to see what worked.

From then on, until you press Escape:

- Up and Right turn it up, Down and Left turn it down; with Shift a small step, with Control a large one.
- T goes to its top end and B to its bottom end. (Home and End do the same, on a keyboard that has them.)
- After every press you hear what changed: the text at the control that is new, such as "58 percent", or "Up",
  or that nothing moved.
- R reads the text at it, W asks the vision model what it shows (a guess), M tries another way of working it.
- K keeps it under a hotkey for this program. The next time, that hotkey takes hold of it at once.

Where nothing can be named, as in many games, press NVDA+Alt+K for pointer mode, move the pointer onto the
control with the arrow keys (W says what is under it), and press D. The same then happens for what is there.

What is kept is data, not code: the control's name or its place as a share of the window, and how it is
worked. Limits, stated plainly: this has been tested with a stand-in program, not with real programs yet.
A game that reads the mouse directly, as most 3D action games do, will not follow a pointer moved this way
unless you tell VisionClaw so: see "Games that read the mouse directly".
A control whose change shows nowhere near it cannot be told to have moved.

## How a sighted person works each control, and a deep query

When VisionClaw inspects a window, a page or one control, it now also works out how a sighted person works
what is there. For controls whose kind NVDA can tell, that is known: a button is clicked, a field is typed
into, a slider is dragged. Controls whose kind NVDA cannot tell are put to both models, one small question
each: the vision model looks at the control's picture, and the coder model reads what a deep query found.
Their answers are compared, and the report says who said what, and that a model can be wrong.

A deep query asks everything that can be asked without touching the control: what NVDA reports; what Windows
UI Automation and the older accessibility interfaces offer for it, such as an action to press it or a value
that can be set; its window, and which toolkit or game engine draws it; the text NVDA's off-screen model
caught being drawn; and what Windows itself finds at that spot. Ask "do a deep query of this control" or
"how would a sighted person use this" with the control focused.

From that, plain code chooses the fix: a key that presses a control the Tab key never reaches; arrow keys for
a control that is dragged or turned; a name for one that has none; or advice where no fix is known.

## The latest developer guides, for the models to read

The NVDA Developer Guide from NV Access comes with VisionClaw, as Markdown text, as it was when your version
was built: you have it without a download. It is under the same licence as VisionClaw. The NVDA Add-on
Development Guide does not come with it, because its authors have not said that it may be passed on.

Ask "get the latest NVDA developer guides". VisionClaw asks first, then downloads the NVDA Developer Guide
from NV Access and the NVDA Add-on Development Guide from the NVDA add-ons community, turns them into plain
Markdown text and keeps them on your computer. Ask again whenever you want newer copies. It never happens by
itself, only the two requests are sent, and what is downloaded is text to read, never a program.

What VisionClaw does with them once they are there:

- **Questions about writing for NVDA** ("what does the developer guide say about events") are answered from
  them, in plain words and without code read out; the answer says which guide it is from.
- **When it writes or corrects an add-on for you**, the model is given the single lines of the guides that fit
  your request and that VisionClaw's own notes do not already cover: one line for one function, never a whole
  code example. A line whose function your NVDA no longer has is left out.
- **In the description window**, a question about how something is done is given what NVDA's own help says.
- **"Which developer guides do I have"** tells you which guides are on the computer, from which day and in
  which folder; "open the developer guides folder" opens it; "delete the developer guides" removes them after
  asking.

Guides downloaded with VisionClaw 1.1.0 or older lost the indentation of some code examples. Ask for the
latest guides once more to have them kept as they were written; VisionClaw tells you so when you ask which
guides you have.

## The add-ons you have installed, and NVDA Coach

VisionClaw reads from the running NVDA which add-ons are installed, what each says about itself, its help and
its commands. Nothing is kept in a list, so a new add-on is known the next time you ask.

- "Is there an add-on that reads math?", "which of my add-ons can tell me the date?": it names the add-on
  that says it does this, with its key written as the add-on writes it, and says when that add-on is turned off.
- "What does the Clock add-on do?", "which keys does it have?": as before.
- VisionClaw never installs, removes, turns on or turns off an add-on.

**NVDA Coach** is a free add-on by Tony Gebhard, in NVDA's Add-on Store, that teaches NVDA in lessons of single
steps. VisionClaw works with it only when you ask to be coached or taught, and gives as much help as you ask for:

- "give me a hint about browse mode": one hint from the lesson, and no more;
- "coach me on reading the current line": the one step that is about it;
- "teach me object navigation step by step" or "give me a lesson on the NVDA menu": the lesson's steps in order;
- "which lessons does NVDA Coach have", "how far am I in NVDA Coach": the chapters, and what you have finished;
- "open NVDA Coach" or "coach me": NVDA Coach's own window, opened with its own command.

Without NVDA Coach, "teach me how to ..." is answered from NVDA's own user guide, and VisionClaw says once
that the add-on exists. You can also tell VisionClaw how much help you want in general ("from now on, give me
only a hint", "always explain things step by step"); it remembers that and keeps to it in its answers.

NVDA's own list of what is new in its newest three versions, which comes with NVDA, is asked when you ask
what is new, what changed or what was fixed.

## Which version is installed

Ask **"which version of VisionClaw do I have"**, "what version of NVDA am I running", "what version of Access8Math is
installed" with any add-on's name, or "what version of this program is it". VisionClaw says that version and nothing
more: "VisionClaw is version 1.15.1." Ask about several at once, "what versions of NVDA and VisionClaw do I have", and
you hear one line for each. An add-on that is turned off is said to be; an add-on you name that is not installed is
said not to be, with the name of the program in front.

Only when you say you are new to this ("I'm a beginner screen reader user, ...", "I'm new to NVDA"), or asked
VisionClaw to remember that you are, does the answer add where to find the version yourself next time: for NVDA,
NVDA+N, then H for Help, and About; for an add-on, NVDA+N, then T for Tools, then A for the Add-on Store, whose
Installed add-ons tab lists every add-on with its version; for VisionClaw, NVDA+Alt+U to look for a newer one.

The version is read from NVDA itself, from the add-on's own manifest and from what the program tells NVDA, by plain
code: no model is asked and nothing goes online. "Is there a newer version of VisionClaw" still looks on GitHub, after
a question (see "Getting a newer version of VisionClaw").

## Free training material, and everything as Markdown files

Ask "get the free NVDA training material". VisionClaw says which sites it is from and how many requests it
sends, asks, and then downloads 18 pages and keeps them as Markdown text on your computer:

- from the **NVDA wiki**, written by NVDA's community: coming to NVDA from JAWS, coming from Window-Eyes,
  the ribbon of Office, which programs work with NVDA, more voices, and NVDA's log;
- the eight lessons of the **American Foundation for the Blind's "Learn NVDA"**, from 2016, as their transcripts;
- the four workshops of **Hadley's "NVDA Screen Reader Series"**, as their transcripts.

AFB and Hadley keep their copyright, and the wiki states no licence: the pages are kept for your own reading,
each file says where it is from, and nothing is passed on. It never happens by itself.

VisionClaw then uses them where they belong, after NVDA's own user guide: the lessons when you ask to learn
or be taught something, or say you are new; the page for people from JAWS when you name JAWS. Say once "I come
from JAWS" and VisionClaw remembers it, and looks in that page for every question. An answer made from a lesson
says where it is from. "Which training material do I have" tells you what is on the computer; "delete the
training material" removes it after asking.

Everything VisionClaw reads up in is a Markdown file you can open, in VisionClaw's data folder: `guides`,
`training`, `notes`, `memories`, `skills`, and `help`, where NVDA's own user guide, its list of what is new
and the help of each of your add-ons are kept as Markdown and made again when NVDA or an add-on is updated.

## Finding out what VisionClaw can download for you

Ask "what can you download for me", or press the button "What VisionClaw can download for you" in VisionClaw's
settings. VisionClaw names everything it can get from the internet for you, the developer guides, the free
lessons, notes on the program you are in, newer models and a newer version, says which of it is on your
computer already, and gives the words that get each. It also tells you by itself, in one sentence after a
fitting answer: after you ask for an add-on, that the guide for writing add-ons can be downloaded; after you
ask to be taught something, that lessons can be. Each of these sentences is said once and never again, and
nothing is downloaded until you ask and say yes.

## When you have a hand on a mouse

VisionClaw works from the keyboard first. At the times you work a real mouse, a trackpad or a game controller
yourself, say so ("I am using my real mouse"), and it helps with that instead of leading you back to the
keyboard: with NVDA's own mouse tracking (NVDA+M), with directions in words, and by saying what is under the
pointer before you click.

## Add-ons written by VisionClaw

**You never have to read, write or debug code.** You say what you need; the coder model writes a small add-on.

### Written piece by piece

A request for an add-on is broken into bite-size pieces by plain program code, the way a text adventure reads a
command: each piece is one key command or one thing that happens by itself. *Write an add-on that beeps when a link
gets the focus, says the time with NVDA+Alt+T, and only works in Firefox* is two pieces and one program.

- **Plain code writes everything around the pieces:** the imports, the key you named, the event (a control getting
  the focus, a window coming to the front, a name, value or state that changes, a character you type, the cursor
  moving, an alert, a notification, something appearing), the kind of control ("a link", "a heading", "a
  checkbox"), the state ("gets checked" speaks only when the box is now checked, not when it is unchecked), and the
  program. A piece whose work is a beep or a fixed sentence, such as *say heading*, is written by plain code too.
- **The model writes only the few lines inside one piece**, fed from that piece's section of the work sheet: what it
  must do, when it runs, the method with the place for its lines, and the notes, skills and memories that fit that
  piece's own words. It never sees the other pieces.
- **Each piece is checked, corrected and reviewed on its own**, then plain code puts them together and checks the
  whole add-on once more.
- **A key command whose key you did not name** gets a key nothing else uses, and you are told which.
- **You are told what it cannot do**: an add-on for headings that get the focus works in a program and in focus
  mode, but in browse mode on a web page moving to a heading does not move the focus.
- **What cannot be read into pieces** for certain, such as something every hour, at NVDA's start, or a settings
  panel, is written as one piece as before, and you are told why.
- **When an add-on fails in one place**, only the method where it failed is sent to the model to correct, and put
  back; when it failed in several places, or you say in words what is wrong, the whole add-on is corrected as before.

Before it can run:
- The code must pass a check: it must be valid, must not start programs, use the network, or delete or write
  files, and must follow NVDA's rules for events and key commands.
- The code is compared with what you asked for. An event or a key nobody asked for is taken out, and a limit to
  a program you did not name is removed. Mistakes that plain code can correct, it corrects without asking the
  model: a forgotten import, an event that forgot to hand the event on to NVDA, a control's kind written the
  wrong way, a file the model let run on too long.
- The other model reviews it (unless reasoning is set to Off). The checks decide; if the reviewer still has a
  doubt, you are told the doubt.
- **You are always asked** whether to turn it on, and told in plain words what checking the code shows: the
  keys it adds, what it reacts to, which programs it works in, and whether it speaks, beeps, presses keys or
  clicks. Showing the code is offered too, for those who want it.

**When an add-on fails, the models debug it.** Every add-on VisionClaw wrote runs behind a guard:
- An error in it never reaches NVDA. NVDA keeps working, and events are still handed on.
- The add-on is paused, and you hear that it had a problem and is being corrected.
- The coder model is given the exact error, the failing line, and what NVDA really offers where the code used
  something that does not exist. It corrects the add-on, the result is checked and reviewed like a new one, and
  it is loaded again. You hear when it is on again.
- An add-on that stops starting after an NVDA update is debugged the same way.
- After three corrections that did not hold, it is turned off and you are told. "Fix the add-on ..." lets you
  say in words what it does wrong, and the models try again with that.
- The mistake is remembered, so the coder is warned about it next time. You can turn automatic correction off
  in settings; then a failing add-on is turned off and you are told.

Generated add-ons load without restarting NVDA and come back after a restart. "List what you have made" and
"remove the add-on ..." manage them.

**The two models work together on a fix.** When the add-on is about something on screen, the vision model
first says what the window shows, NVDA supplies the exact details of the focused control (program, kind, window
class, control number), and the coder model writes the fix for that control.

**Fixes are permanent.** A generated add-on is kept and starts again with NVDA. "Save the add-on ... as a file"
writes it as a normal `.nvda-addon` file in your Documents folder, under "VisionClaw add-ons", which you can
install like any other add-on or share with someone who has the same problem.

The check prevents accidents. It is not a sandbox: once you say yes, the code runs inside NVDA like any other
add-on. Small models make mistakes; if an add-on matters to you, listen to what VisionClaw says the code does
before you say yes.

## Skills

A skill tells VisionClaw how a kind of job is done well for a blind person: describing a photo, web forms,
email, braille, games, NVDA for a beginner, stubborn controls, and many more; 66 come with VisionClaw. VisionClaw chooses skills from
the words of your request, by plain code, at most two at a time; an everyday word alone does not start one. A
skill never holds code, and every change is still asked about.

- **Make your own in words**: "make a new skill: when I ask about recipes, read the ingredients first". What the
  skill says is your own words.
- "Which skills do you have", "what does the email skill say", "turn off the game skill", "delete my recipes
  skill".
- **The skills window**, NVDA+Alt+I, or the button "Skills: read, make, change, turn off or delete them" in the
  settings: every skill and what it says, with New skill, Change, Turn off or on, Delete, Import a skill file,
  Open the skills folder, and Read the skills again. A skill that comes with VisionClaw is never deleted, only
  turned off; a changed one is kept as your copy, and deleting your copy brings back the original.

## Memories

Say "remember that I use a braille display with 40 cells". VisionClaw keeps your own words as a small Markdown
file, one for each memory, in the folder `memories` of its data, and uses them with later requests. It also keeps
something lasting you say about how you work the computer when nothing else kept it, and then says so and how to
undo it; the setting "Remember things" decides this. A new memory about the same thing replaces the old one.

- "What do you remember", "forget that", "forget all" (always asked about first).
- **The memories window**, from the button "What VisionClaw remembers, to forget some or all" in the settings: a
  check box for each memory, the whole memory to read, Forget checked, and Forget all and start over.
- How much help you want is a memory too: "from now on, give me only a hint".
- How fast you like answers is kept without being asked: "the 9B is too slow for me", "I like quick answers",
  "accuracy matters most to me". The model VisionClaw picks or suggests follows it.
- Memories are found by what they mean: a memory about the system tray is found when you ask about the notification
  area, and one about how fast your voice talks when you ask to make the speech quicker.

## Your library

Put Markdown, text, saved web pages or Word documents into VisionClaw's library folder, and questions are
answered from them too, after NVDA, the program, its window and Windows. A document whose name names a program
counts for that program. Ask "what is in my library", or press "Open your library of documents" in the settings
to open the folder.

## How VisionClaw answers, and your own instructions

Every answer, every description of a picture and every add-on written on the fly is told who you are: blind,
listening to speech or reading braille. Answers start with the answer, use no Markdown, copy names, numbers and
keys exactly, say places in words, and say what cannot be read instead of guessing. In the settings, the button
"How VisionClaw answers, and your own instructions" lets you read and rewrite every instruction, add your own,
and restore the original of one or all of them. They apply to whatever model you use.

## Object names

Many programs, games and web pages have buttons, pictures and other controls without a name, or with a name that
says nothing: NVDA then says only "button", "graphic", a file name such as icon_close.svg, or the sign of an icon
font. Press NVDA+Alt+B and VisionClaw says "Object names on". From then on every object that is truly unlabelled,
with no label from Windows, the browser or the program, is named by the local model that sees, the moment you reach
it, and the name is saved. Press NVDA+Alt+B again and it says "Object names off". These are accessibility fixes made
on the fly, for the times you just want a control to say what it is: nothing is written, installed or asked. When
an object is not named and you want a name for it anyway, press NVDA+Shift+Alt+B.

- **However you move**: Tab, Shift+Tab, Control+Tab and the arrow keys in lists and menus; in browse mode the arrow
  keys, the quick navigation keys such as B for the next button and G for the next graphic, and NVDA+F7's elements
  list, without leaving browse mode; object navigation, such as NVDA+Numpad 6 or NVDA+Shift+Right Arrow on a laptop;
  the review cursor; and the mouse. NVDA asks the object for its name, and VisionClaw answers with the saved one.
- **Only what is truly unlabelled is named**: whatever Windows, the browser or the program gives NVDA is a label,
  however short or odd, and is left as it is: one letter or number, such as a page number or X; a sign such as + or an
  emoji; a file name in a list of files; a name from the program's code, such as btnClose. The label the program gives
  in another way counts too: a description or tooltip, the hint written in an empty field, the words inside a button,
  and the text the program says labels a field. Where NVDA would not say such a label by itself, VisionClaw says it, as
  it is, without the model: the label next to a field that the program links to it, and the words inside a button.
  Truly unlabelled is: no name at all; only the signs of an icon font or characters that are never printed; only the
  word for its kind, such as button on a button; a word a program gives by a mistake, such as undefined; and on a
  picture, its file name, a web address or a word that only says it is a picture. An empty table cell, an empty list
  and a pane that holds other objects are not named, and nor is a picture inside a button or link: the button or link
  is named instead, where it needs a name.
- **Ask for a name yourself**: NVDA+Shift+Alt+B asks the model for a name for the object where you are, in browse mode
  for the control or picture at the cursor: where object names left it alone because it has a label you do not
  understand, such as X, where the model could not name it before, and also while object names are off. The beep says
  the name is on its way, then you hear it, with probably where the model is not sure, or that the model could not
  tell. It is saved, and said there from then on, over the program's own label, while object names are on; forget it
  in the window of saved names.
- **A beep**: when a name for the object you are on is on its way, you hear a short, soft, high beep, then the name.
  On a slower computer this tells you to wait a moment. The beep goes with the setting "Play a soft tick while
  waiting for a description": turn that off and this beep is off too.
- **Probably**: a name the model is not sure of is said with probably before it: "probably Settings button". A name
  is sure when the text written on the object, read exactly with Windows OCR, or what the program's own code calls
  it, agrees with the model. Your own names, and names a person shared, are said as they are.
- **Saved**: names are kept for each program and each website, in the file labels.json of VisionClaw's data folder,
  and NVDA says them from then on, in speech and braille. VisionClaw's tools and its models see them too, and a name
  found in a program's code is added to VisionClaw's notes on that program or website. On a web page the controls a
  little further down, and in a program the objects next to the one you reach, are named in the background, so that
  their names are ready when you get there.
- **Your own name**: NVDA+Alt+N gives your own name to the object where you are: in browse mode the control or
  picture at the cursor, elsewhere the object at the review position, or the current item of the overlay. Leave the
  name empty to take your name away. Your own name always wins, also over the program's own label. You can also ask:
  "call this button play".
- **The window of saved names**: press NVDA+Alt+N twice, or the button "Saved object names: change, forget or share
  them" in VisionClaw's settings: the programs and websites with names, the names of the one you choose with who gave
  each and how sure it is, and the buttons Change the selected name, Forget checked names, Forget all names of this
  place, Share names and Add shared names.
- **Sharing**: Share names saves the names of the programs and websites you check to a file. Give it to another
  VisionClaw user, who adds it with Add shared names. The file is plain data and names those programs and websites,
  nothing else about you. Every line is checked before it is used, and a shared name never replaces your own; it
  replaces only a guess of the model. A name kept by what the object's code calls it fits on every computer; one kept
  by its picture fits only where the object looks exactly the same.
- **A small model is best**: the first time you turn object names on, VisionClaw says once that, because these are
  fixes made on the fly, a small model, 7B or smaller, is best for them: it names an object quickly. If the model you
  use is larger, it is named. You choose the model in the models window, NVDA+Alt+M; nothing is changed for you.

What object names cannot do: an object that is not on the screen, or while the screen curtain is on, has no picture
and is not named. A page that NVDA reads through UI Automation, such as a Word document, does not get names in its
text yet. The model can be wrong, which is why a name it is not sure of has probably. Text and headings are read
from their own words and are never named.

Which objects are named was decided for every kind of object NVDA has. The full list, read from the source of NVDA
2026.3.1, with every role, every state, every class of object, the browse mode documents, the programs NVDA supports
and every way of moving with its keys, is [docs/NVDA-OBJECTS.md](docs/NVDA-OBJECTS.md).

## Commands

| Keys | What it does |
|---|---|
| NVDA+Alt+C | Ask VisionClaw |
| NVDA+Alt+V | Ask VisionClaw by voice: opens the same window and listens |
| NVDA+Alt+P | Say how far VisionClaw is with a request, a description, an answer about a picture, the words you spoke or the overlay's icons |
| NVDA+Alt+X | Stop the current request, or a description or answer about a picture that is still on its way |
| NVDA+Alt+M | See, remove or swap the models on this computer |
| NVDA+Alt+I | The skills window: read, make, change, turn off or delete skills |
| NVDA+Alt+U | Look for a newer version of VisionClaw, and get it if you want it |
| NVDA+Alt+K | Pointer mode: work the mouse pointer with the arrow keys |
| NVDA+Alt+J | Controller mode: work the mouse pointer with a connected game controller |
| NVDA+Alt+A | Describe the current element |
| NVDA+Alt+W | Describe the current window |
| NVDA+Alt+F | Describe the whole screen |
| NVDA+Alt+D | Describe the image, or copied image file, on the clipboard |
| NVDA+Alt+O | Open or close the overlay for the current window |
| NVDA+Alt+G | Turn automatic descriptions of unlabeled images and photos on or off |
| NVDA+Alt+B | Turn object names on or off: every object that is truly unlabelled named by the local model wherever you move, in browse mode too |
| NVDA+Shift+Alt+B | Ask the local model to name the object where you are, also where object names left it alone |
| NVDA+Alt+N | Give your own name to the object where you are, or to an overlay item; press twice for the window of saved object names |

Press a describe command once for a quick spoken description, twice for a detailed one in a window where you
can ask questions. Every question is answered there: what is highlighted or selected, where something is,
what a thing is for, what a word or symbol means, what could be done next. Earlier versions replied "I can
only answer questions about this image" to much of that; that reply is gone. What the picture does not show,
the model is told to say is not shown, and never to invent. Press Control to stop speaking. All commands can be changed in NVDA's Input
Gestures dialog, under VisionClaw.

By default VisionClaw asks before it changes a setting, clicks, presses keys or types. You can turn that off in
settings. Anything that could take speech or braille away is always asked about, whatever the setting.

## Taking VisionClaw along: a portable copy

Everything VisionClaw keeps is inside its own add-on folder, in the folder `data`
(`%APPDATA%\nvda\addons\visionClaw\data` in an installed NVDA): the models, the guides, the training material,
notes, memories, skills, your library, the logs, and whatever else you have it download or keep. Its size is
whatever you have put there. When VisionClaw is updated, this folder moves into the newer version by itself; when
VisionClaw is removed, it is kept in `%APPDATA%\nvda\visionClaw`, and a later install takes it in again. A
VisionClaw older than 1.4.0 kept it in `%APPDATA%\nvda\visionClaw`; it is moved in the first time 1.4.0 starts.

In VisionClaw's settings, press *Make a portable copy of VisionClaw with everything in it* (Alt+X). The window
says what goes in, part by part with its size, and offers two ways:

- **One file that installs VisionClaw with everything on any computer**, `VisionClaw-<version>-portable.nvda-addon`.
  Put it on a flash drive or send it, and open it on the other computer while NVDA is running; NVDA asks
  before it installs it. Where VisionClaw is there already, what that computer has is kept and the rest is added.
- **VisionClaw with everything, straight into a portable NVDA**, as on a flash drive. Choose the folder of a
  portable NVDA, or the drive it is on; VisionClaw then starts with that NVDA. Copying again finishes a copy that
  was stopped and skips what is there already.

Nothing is left out of the data folder. Your VisionClaw settings come along too, and are taken over by a
VisionClaw that has no models chosen yet; one that was used already keeps its own. To make a portable NVDA
itself, the window has a button for NVDA's own window (NVDA menu, Tools, Create portable copy): check *Copy
current user configuration* there, and VisionClaw comes along with everything.

Writing many gigabytes to a flash drive takes a while; a progress bar shows how far it is, and Cancel stops it.
A drive formatted as FAT32 cannot hold a file of 4 GB or more, so VisionClaw says so before it starts; exFAT and
NTFS can. The copy holds the lessons and guides VisionClaw downloaded for your own reading; their owners keep
their copyright, so give a copy to someone else only where they allow it.

## VisionClaw's own log

VisionClaw keeps a log of its own, so that when something goes wrong it can be found out why. NVDA's own log
is often switched off; this one does not depend on it.

- It is the file `visionclaw.log` in the folder `logs` of VisionClaw's data folder
  (`%APPDATA%\nvda\addons\visionClaw\data\logs`). Ask *open the VisionClaw log*, or use the button in VisionClaw's settings.
- **Detailed** (the default) records every request, every step, every question put to a model with its
  answer, every tool with what it was given and what it found, every question you were asked and what you
  chose, how the engine started, and every error with the place in the code where it happened. **Brief**
  leaves out the whole questions and answers. **Off** writes nothing. Choose in VisionClaw's settings.
- The file is kept small: at 2 MB it is put aside and a new one begun, and three old ones are kept.
- **It stays on your computer.** VisionClaw sends it nowhere. It holds what you asked and what was read from
  your screen, so look through it before you give it to someone.
- A fault inside VisionClaw no longer ends the whole request: the step that failed says so, the rest of your
  request is still done, and where it happened is in the log.

## Settings

NVDA menu, Preferences, Settings, VisionClaw. In the order you meet them:

- **Run the models on (graphics)**: Automatic, Dedicated graphics card, Vulkan, or Processor only.
- **When both models do not fit on one graphics chip, run the second one on another chip or the processor,
  instead of the two taking turns.**
- **How much the models think before acting**: Automatic, Off, Low, Medium, High.
- **Ask the models one small question at a time**: Automatic, Always or Never. Automatic does this for the two
  very small models only.
- **Which model does each job**: the models you chose in the models window, and VisionClaw only suggests; or
  VisionClaw picks from the models on this computer for each request, without asking.
- **Remember things**: when you ask, and when you say something lasting about yourself or how you like things;
  only when you ask it to remember; or never.
- **What VisionClaw remembers, to forget some or all**: opens the memories window.
- **What VisionClaw can download for you.**
- **Open your library of documents.**
- **Search the web with**: the search engine used when you ask to search the web.
- **Game controller**: tell me when one is connected and listen for its View and Menu buttons held together;
  listen, but say nothing when one is connected; or do not look for a game controller.
- **Speech model for asking by voice**: the small one, about 1 GB, or a larger one. It is downloaded when you
  first use it, after a question.
- **When an add-on VisionClaw wrote fails, have the models debug and correct it by themselves.**
- **Ask me before VisionClaw changes a setting, clicks, presses keys or types.**
- **Say each step while VisionClaw works on a request.**
- **Status updates while VisionClaw takes long, as with a large model or high thinking**: after 10, 15, 30 or 60
  seconds of quiet, and as often while it lasts; or never, and you press NVDA+Alt+P when you want to know. The
  suggested choice is 15 seconds.
- **Speak with VisionClaw's own voice, once you have set one.**
- **Models on this computer**: the models, their sizes and what each is in use for.
- **Look for a newer version of VisionClaw**: only when I ask, or when NVDA starts, at most once a day.
- **Look for a newer version now.**
- **VisionClaw's own log, for finding out why something went wrong**: Detailed, Brief or Off.
- **Open VisionClaw's log.**
- **Skills: read, make, change, turn off or delete them**: opens the skills window.
- **Open the skills folder.**
- **How VisionClaw answers, and your own instructions.**
- **See, remove or swap models.**
- **Choose or download models.**
- **Make a portable copy of VisionClaw with everything in it, for a flash drive or another computer.**
- VisionMate's settings: **Automatically describe images without a label, photos in chats and photos in image
  viewers**; **Describe images further down the page in the background, so they are ready sooner**; **Object names: name every object without a name or with a vague one, wherever you move**; **Saved object names: change, forget or share them**; **Use Windows OCR to read screen text exactly**; **Keep the
  overlay up to date as the window changes**; **Get ready when NVDA starts**; **Answer in NVDA's language**;
  **Play a soft tick while waiting for a description**.

## Requirements

- Windows 10 or 11, 64-bit
- NVDA 2024.1 or later
- 4 GB of free disk space for the two suggested models, more for larger ones
- 8 GB of RAM or more; 16 GB is comfortable with both models loaded
- A graphics chip that supports Vulkan makes it much faster. Without one, the processor is used.

## What to expect

Measured on one laptop with a dedicated graphics card (GeForce RTX 5060 Laptop, 8 GB), with the stand-in tools
of the live test and Qwen3-VL 2B doing both jobs: a request took between half a second and four seconds. On the
processor alone it will be several times slower. With the suggested models these numbers have not been measured
yet.

These are small models. They are right most of the time on simple requests and less often on complicated ones.
Double-check anything important.

## Getting a newer version of VisionClaw

VisionClaw can look on its own page on GitHub for a newer version of itself and get it for you.

- **When you ask:** press **NVDA+Alt+U**, or use the button "Look for a newer version now" in VisionClaw's
  settings, or ask in words: *check for a new version of VisionClaw*. If there is one, a window opens with
  the focus in a **read-only edit box** that holds its version, its size and what is new, one point to a line.
  Read it with the arrow keys, line by line or word by word, as often as you like, and copy from it. Tab
  reaches two buttons: **Download and install**, and **Not now**. Escape means not now. If there is no newer
  version, you are told that you have the newest.
- **By itself, if you choose that:** in VisionClaw's settings, "Look for a newer version of VisionClaw" can be
  set to "When NVDA starts, at most once a day, and tell me". Then, a little after NVDA has started, you hear
  one sentence if a newer version exists: "VisionClaw 0.10.0 is available. Press NVDA+Alt+U to get it." No
  window opens and nothing is downloaded until you ask. The setting starts on "Only when I ask".
- **Getting it:** after your yes, the add-on file of that release is downloaded and checked against the size
  and SHA-256 that GitHub reports for it. Then it is handed to NVDA, which asks its own question about
  installing it and restarts. Nothing is ever installed without that question.

What the check can and cannot show: the SHA-256 comes from GitHub, like the file itself. It shows that the
file arrived whole and was not changed on the way; it does not show who made it. Only files of the releases
of `joshknnd1982/visionclaw` on github.com are ever taken, and a release whose file has no size or SHA-256 is
passed over.

Nothing about you or your computer is sent. GitHub sees your internet address, as any website does.

## Privacy

VisionClaw does not collect any information. What you say when you ask by voice is recorded into memory, turned
into text on your own computer, and thrown away: no recording is written to the disk and nothing of it is sent
anywhere. Its own code connects to the internet only to download the
models you choose, from Hugging Face, and the speech model after a question; when you press Look for newer models and say yes, to read the list
of models from its own page on GitHub; and when you ask for the latest developer guides and say yes, to
download those two guides from NV Access and GitHub; and when you ask it to learn about a program and say yes,
to read about that program on Wikipedia, Wikidata and the program's own website, sending the program's name
and nothing about you. None of these happens by itself. It also reads the list
of its own versions from GitHub when you ask it to look for a newer version; only if you turn that on in the
settings does it do so by itself, when NVDA starts and at most once a day. Screens, photos, requests and
generated code never leave your computer. VisionClaw's own log, the audit of NVDA and the notes on programs
are files on your computer and are sent nowhere. A game controller is read on your computer; nothing about
it is sent anywhere.
When you ask it to open or search the web, it hands the address to your own browser, which goes online as
usual; a web search sends your search words to the search engine you chose.

## How this relates to SmallClaw

SmallClaw is a Node.js program for the Ollama model server. An NVDA add-on runs inside NVDA's own Python, so
SmallClaw itself cannot be put inside one. VisionClaw therefore carries a Python agent core that follows
SmallClaw's design: small steps, a secondary model that advises and checks, loop and failure handling,
keyword-chosen knowledge, lessons kept between sessions. SmallClaw's code is not included.

## Building and contributing

See [BUILD.md](BUILD.md). [CLAUDE.md](CLAUDE.md) holds the project's rules and its plan in phases and sessions;
[docs/STATUS.md](docs/STATUS.md) says what is done and tested, and [docs/TESTPLAN.md](docs/TESTPLAN.md) is the
checklist for testing inside NVDA.

## Credits and licence

- [VisionMate](https://github.com/athee06/VisionMate) by Athiban Vijay: the describing, overlay, OCR and
  chat-photo features. GPL v2 or later.
- [SmallClaw](https://github.com/XposeMarket/SmallClaw) by XposeMarket: the agent design. MIT.
- [llama.cpp](https://github.com/ggml-org/llama.cpp): the engine. MIT.
- The NVDA Developer Guide by NV Access and contributors comes with VisionClaw as Markdown text. GNU General
  Public License, version 2 or later.
- Qwen models by the Qwen team, Alibaba Cloud: Apache 2.0. GGUF conversions of Qwen3.5 by Unsloth.
- [NVDA](https://github.com/nvaccess/nvda) by NV Access and contributors, GPL v2 or later: VisionClaw's notes on
  how NVDA is built inside were written from its source, and the tests use the descriptions of its commands
  (`tests/nvda_commands.json`).

VisionClaw's code is licensed under the GNU General Public License, version 2 or later. See [LICENSE](LICENSE).
