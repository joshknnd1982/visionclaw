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

> **Status: version 1.0.0, the first full release.** The orchestration core has been tested with scripted models and with
> real models through the bundled engine. Inside NVDA 2026.3.1 the owner has run the models window, a first
> set of requests, five tests of version 0.4.0 and three of 0.8.2; **most of the test plan has not been run inside NVDA
> yet**, and what 0.9.0 to 0.11.0 add (the command fix, the log, the audit, the questions about pictures, questions
> answered from NVDA, the program, the window and Windows, the window that says what is new, learning about a
> program from the internet), scrolling and
> the arrow keys for dials not at all. Expect rough edges and please report them. See
> [docs/STATUS.md](docs/STATUS.md) for exactly what was tested.

## What you can ask

Press **NVDA+Alt+C**, type a request, and press Enter. For example:

- *Make NVDA speak a little faster.*
- *Turn off the typing echo and set punctuation to all.*
- *How do I read the title of this window?* (You are told the keys, for next time.)
- *How can I use the keyboard to navigate my desktop?* *How do I switch between open windows?* *How do I rename a file?*
- *What is browse mode?* *What does NVDA+T do?* *What does Windows+D do?*
- *What can I do here?* *Which key is for the Save button?* *Which windows are open?*
- *Learn about this program.* *Learn about this game.* Then: *How do I duplicate a line?* *Delete the notes on this program.*
- *What is on my screen?*
- *Press the Play button in this window.* (Works in windows and games NVDA cannot read.)
- *Give this program a hotkey that clicks Send.*
- *Write an add-on that beeps when a link gets the focus.*
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
   **you are asked** and pick from the choices.
   **With one model for both jobs** there are not two to agree, and VisionClaw does not say that there are:
   the model chooses once, checks a plan it wrote itself, and you are asked when it is not sure of that plan.
   Its choice is also checked against your own words by plain program code. If your words point to something
   else, the model looks again; if it still chooses differently, **you are asked** which of the two you meant.
3. **One step at a time.** For each step a model fills in one small form, and plain program code does the rest.
   When a step fails, the model sees the error and corrects itself; if it stays stuck, the other model gives it
   a hint; if that does not help, you choose whether to skip, retry or stop.
4. **You hear the progress.** Every step is announced. **NVDA+Alt+P** says where the task is at any time.
5. **You can always stop.** **NVDA+Alt+X** stops the task at once, even in the middle of a model's answer.
6. **Honest answers.** What VisionClaw says it did is taken from what the tools actually reported, and it tells
   you plainly when a part could not be done.
7. **It learns.** When a step first fails and then works, the lesson is kept on your computer and used for
   similar requests later. The models can also read NVDA's own user guide and notes about NVDA's add-on system.

## Install

1. Download **[VisionClaw-0.11.0.nvda-addon](https://github.com/joshknnd1982/visionclaw/releases/download/v0.11.0/VisionClaw-0.11.0.nvda-addon)**
   (or pick a version on the [releases page](https://github.com/joshknnd1982/visionclaw/releases)), open the
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

The models come from Hugging Face. Each file is pinned to one version and checked against its SHA-256 after
the download. You can also use VisionClaw with a vision model only; then it describes images and runs the
overlay like VisionMate, and Ask VisionClaw waits until you add a coder model.

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
- **Hear how the page is laid out**: its headings in order with their levels, and how many links, buttons and
  fields it has.
- **Move to a place on the page**: "take me to the heading Refund policy" puts NVDA's reading position there,
  so you can read on with NVDA's own commands.
- **Go back, forward, or reload.**

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

What it cannot do: a control that nothing in the page's or program's code tells apart from others cannot be
named reliably, and the report says how many those are. A window NVDA cannot read at all cannot be fixed
this way; use the picture instead (*list what is in the window*, an app helper hotkey, or pointer mode).
Sites change, and a fix that no longer finds its control says so instead of doing something else.

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
   (`%APPDATA%\nvda\visionClaw\notes`). It says at the top that it is from the internet and may be wrong,
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

**In the overlay** (NVDA+Alt+O), on any item: Enter or Space clicks, Shift+Enter double-clicks, the Applications
key right-clicks, and **G picks the item up; G on another item drops it there.**

**Pointer mode** (NVDA+Alt+K, or ask "make this control keyboard navigable") is for a control, canvas or game
where nothing can be listed at all. The arrow keys move the mouse pointer inside the window:
- Arrow keys move one step; with Shift a fine step; with Control a far one. On a plain screen these are 20, 4
  and 100 pixels. They follow your screen: at 200 percent scaling they are twice as many pixels, so a step is
  the same to the eye on a small laptop screen and on a large 4K one, and in a small window they are made
  smaller so the pointer does not leap across it. A short tone tells you how high the pointer is, and a low
  tone that it has reached the edge.
- **Page Down and Page Up turn the mouse wheel about a page** where the pointer is; with Shift one notch; with
  Control sideways. You hear how far along the view stands, or that nothing moved.
- **S finds the scrollbars** in the window's picture, tells you where one is and how far along it stands, and
  puts the pointer on it. G then holds it, the arrow keys move it, and G lets go.
- Enter or Space clicks, Shift+Enter double-clicks, the Applications key right-clicks.
- **G holds the mouse button down; move; G again lets go.** That is a drag done by hand.
- W has the vision model say what is at the pointer. R reads the text there. P says where the pointer is in the
  window. Home goes to the middle. H repeats the keys. Escape turns pointer mode off.
All other keys keep working as usual.

**App helpers** can right-click or double-click their item as well as click it: "give this program a hotkey
that right-clicks the canvas".

**Scrollbars and other things made only for the mouse.** A deep inspection of a window ("inspect this window")
now also looks at its picture: plain code finds the scrollbars by their look, on a screen of any size and
scaling, and the vision model is asked what else is worked with the mouse, such as sliders, switches or a
drawing area. You are told what was found and how to work it from the keyboard. What the vision model names
is marked as its view, because it can be wrong. Scrollbars that only appear while the mouse is over them,
and scrollbars in the middle of a window rather than at its right or bottom edge, are not found by their
look; the wheel still scrolls there.

When you name the things yourself, as in "drag the New Game button onto the Quit button", your own words decide
which items are meant, not the model's copy of them.

## Dials, knobs and sliders that are only worked by dragging

Some programs, music tools and games have a dial, a knob or a slider of their own that a sighted person drags
with the mouse, and that takes no keys at all. Say what you want: "let the arrow keys work the volume dial",
"make the gain knob work with the keyboard", "give me a hotkey for the pan slider". VisionClaw asks first, then
finds out by itself how the control is worked: through Windows itself where the program offers its value, else
with the mouse wheel, else by dragging it up and down, sideways, or around in a circle. It tries each one step
and puts it back, and compares the control's picture before and after to see what worked.

From then on, until you press Escape:

- Up and Right turn it up, Down and Left turn it down; with Shift a small step, with Control a large one.
- Home and End go to its ends.
- After every press you hear what changed: the text at the control that is new, such as "58 percent", or "Up",
  or that nothing moved.
- R reads the text at it, W asks the vision model what it shows (a guess), M tries another way of working it.
- K keeps it under a hotkey for this program. The next time, that hotkey takes hold of it at once.

Where nothing can be named, as in many games, press NVDA+Alt+K for pointer mode, move the pointer onto the
control with the arrow keys (W says what is under it), and press D. The same then happens for what is there.

What is kept is data, not code: the control's name or its place as a share of the window, and how it is
worked. Limits, stated plainly: this has been tested with a stand-in program, not with real programs yet.
A game that reads the mouse directly, as most 3D action games do, will not follow a pointer moved this way.
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

Ask "get the latest NVDA developer guides". VisionClaw asks first, then downloads the NVDA Developer Guide
from NV Access and the NVDA Add-on Development Guide from the NVDA add-ons community, turns them into plain
Markdown text and keeps them on your computer. From then on the models read up in them, together with NVDA's
user guide and VisionClaw's own notes, when they plan a settings change, answer a question about NVDA, or
write and correct an add-on. Ask again whenever you want newer copies. It never happens by itself, only the
two requests are sent, and what is downloaded is text to read, never a program.

## Add-ons written by VisionClaw

**You never have to read, write or debug code.** You say what you need; the coder model writes a small add-on.

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
add-on. Small models make mistakes; read the code or ask someone you trust if an add-on matters to you.

## Commands

| Keys | What it does |
|---|---|
| NVDA+Alt+C | Ask VisionClaw |
| NVDA+Alt+P | Say the progress of the current request |
| NVDA+Alt+X | Stop the current request |
| NVDA+Alt+M | See, remove or swap the models on this computer |
| NVDA+Alt+U | Look for a newer version of VisionClaw, and get it if you want it |
| NVDA+Alt+K | Pointer mode: work the mouse pointer with the arrow keys |
| NVDA+Alt+A | Describe the current element |
| NVDA+Alt+W | Describe the current window |
| NVDA+Alt+F | Describe the whole screen |
| NVDA+Alt+D | Describe the image, or copied image file, on the clipboard |
| NVDA+Alt+O | Open or close the overlay for the current window |
| NVDA+Alt+G | Turn automatic descriptions of unlabeled images and photos on or off |
| NVDA+Alt+B | Turn names for buttons that have no name on or off |
| NVDA+Alt+N | Give your own name to the current button or overlay item |

Press a describe command once for a quick spoken description, twice for a detailed one in a window where you
can ask questions. Every question is answered there: what is highlighted or selected, where something is,
what a thing is for, what a word or symbol means, what could be done next. Earlier versions replied "I can
only answer questions about this image" to much of that; that reply is gone. What the picture does not show,
the model is told to say is not shown, and never to invent. Press Control to stop speaking. All commands can be changed in NVDA's Input
Gestures dialog, under VisionClaw.

By default VisionClaw asks before it changes a setting, clicks, presses keys or types. You can turn that off in
settings. Anything that could take speech or braille away is always asked about, whatever the setting.

## VisionClaw's own log

VisionClaw keeps a log of its own, so that when something goes wrong it can be found out why. NVDA's own log
is often switched off; this one does not depend on it.

- It is the file `visionclaw.log` in the folder `logs` of VisionClaw's data folder
  (`%APPDATA%\nvda\visionClaw\logs`). Ask *open the VisionClaw log*, or use the button in VisionClaw's settings.
- **Detailed** (the default) records every request, every step, every question put to a model with its
  answer, every tool with what it was given and what it found, every question you were asked and what you
  chose, how the engine started, and every error with the place in the code where it happened. **Brief**
  leaves out the whole questions and answers. **Off** writes nothing. Choose in VisionClaw's settings.
- The file is kept small: at 2 MB it is put aside and a new one begun, and three old ones are kept.
- **It stays on your computer.** VisionClaw sends it nowhere. It holds what you asked and what was read from
  your screen, so look through it before you give it to someone.
- A fault inside VisionClaw no longer ends the whole request: the step that failed says so, the rest of your
  request is still done, and where it happened is in the log.

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

VisionClaw does not collect any information. Its own code connects to the internet only to download the
models you choose, from Hugging Face; when you press Look for newer models and say yes, to read the list
of models from its own page on GitHub; and when you ask for the latest developer guides and say yes, to
download those two guides from NV Access and GitHub; and when you ask it to learn about a program and say yes,
to read about that program on Wikipedia, Wikidata and the program's own website, sending the program's name
and nothing about you. None of these happens by itself. It also reads the list
of its own versions from GitHub when you ask it to look for a newer version; only if you turn that on in the
settings does it do so by itself, when NVDA starts and at most once a day. Screens, photos, requests and
generated code never leave your computer. VisionClaw's own log, the audit of NVDA and the notes on programs
are files on your computer and are sent nowhere.
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
- Qwen models by the Qwen team, Alibaba Cloud: Apache 2.0. GGUF conversions of Qwen3.5 by Unsloth.
- [NVDA](https://github.com/nvaccess/nvda) by NV Access and contributors, GPL v2 or later: VisionClaw's notes on
  how NVDA is built inside were written from its source, and the tests use the descriptions of its commands
  (`tests/nvda_commands.json`).

VisionClaw's code is licensed under the GNU General Public License, version 2 or later. See [LICENSE](LICENSE).
