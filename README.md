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

> **Status: pre-release (0.3.1).** The orchestration core has been tested with scripted models and with a
> real model through the bundled engine, and the whole add-on has been loaded against stand-ins for NVDA.
> It has **not yet been run inside NVDA**. Expect rough edges and please report them. See
> [docs/STATUS.md](docs/STATUS.md) for exactly what was tested.

## What you can ask

Press **NVDA+Alt+C**, type a request, and press Enter. For example:

- *Make NVDA speak a little faster.*
- *Turn off the typing echo and set punctuation to all.*
- *How do I read the title of this window?* (You are told the keys, for next time.)
- *What is on my screen?*
- *Press the Play button in this window.* (Works in windows and games NVDA cannot read.)
- *Give this program a hotkey that clicks Send.*
- *Write an add-on that beeps when a link gets the focus.*
- *Open bbc.co.uk*, *Search the web for the weather in Boston*, *What does this page say about refunds?*
- *Type garden gloves into the search box and search.*
- *Which speech synthesizer am I using? What braille display do I have, and how many cells does it have?*
- *Switch my speech synthesizer to eSpeak.*
- *Save the add-on hello key as a file.*

You do not need to know NVDA. VisionClaw finds the right NVDA setting or command from your description.

## How it works

1. **Bite-size steps.** Your request is split into its separate parts. Each part is matched to a short, fixed
   list of steps, one tool each, such as "find the setting" then "change the setting". Small models are good
   at choosing between a few named options and poor at inventing plans, so that is all they are asked to do.
2. **The models must agree.** Each model decides, on its own, how to handle each part. If they choose the
   same, the work starts. If not, each is told the other's choice and decides again. If they still differ,
   **you are asked** and pick from the choices.
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

1. Download **[VisionClaw-0.3.1.nvda-addon](https://github.com/joshknnd1982/visionclaw/releases/download/v0.3.1/VisionClaw-0.3.1.nvda-addon)**
   (or pick a version on the [releases page](https://github.com/joshknnd1982/visionclaw/releases)), open the
   file, confirm the installation, and restart NVDA.
2. If VisionMate is installed, disable it in the Add-on Store: VisionClaw includes it and uses the same keys.
3. A welcome window opens where you **choose your models**. Press Enter to download them. While they download,
   press Space to hear the progress. An interrupted download continues from where it stopped.

## Models

Every model is always offered, whatever your computer is. Your computer only decides which one is suggested.
Larger models are more accurate and slower. You can change your choice at any time with **NVDA+Alt+M**.

| Use | Model | Download |
|---|---|---|
| Vision | Qwen3.5 2B (suggested) | 1.8 GB |
| Vision | Qwen3.5 4B | 3.2 GB |
| Vision | Qwen3.5 9B | 6.2 GB |
| Vision | Qwen3-VL 2B from VisionMate, if it is already on your computer | none |
| Coder | Qwen2.5 Coder 1.5B (suggested) | 1.0 GB |
| Coder | Qwen3.5 4B, used for coding | 2.6 GB, or none if you chose it for vision |
| Coder | Qwen2.5 Coder 7B | 4.4 GB |
| Coder | Qwen3.5 9B, used for coding | 5.3 GB, or none if you chose it for vision |

The models come from Hugging Face. Each file is pinned to one version and checked against its SHA-256 after
the download. You can also use VisionClaw with a vision model only; then it describes images and runs the
overlay like VisionMate, and Ask VisionClaw waits until you add a coder model.

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
| NVDA+Alt+M | Choose or download models |
| NVDA+Alt+A | Describe the current element |
| NVDA+Alt+W | Describe the current window |
| NVDA+Alt+F | Describe the whole screen |
| NVDA+Alt+D | Describe the image, or copied image file, on the clipboard |
| NVDA+Alt+O | Open or close the overlay for the current window |
| NVDA+Alt+G | Turn automatic descriptions of unlabeled images and photos on or off |
| NVDA+Alt+B | Turn names for buttons that have no name on or off |
| NVDA+Alt+N | Give your own name to the current button or overlay item |

Press a describe command once for a quick spoken description, twice for a detailed one in a window where you
can ask questions about the image. Press Control to stop speaking. All commands can be changed in NVDA's Input
Gestures dialog, under VisionClaw.

By default VisionClaw asks before it changes a setting, clicks, presses keys or types. You can turn that off in
settings. Anything that could take speech or braille away is always asked about, whatever the setting.

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

## Privacy

VisionClaw does not collect any information. Its own code connects to the internet only to download the
models you choose, from Hugging Face. Screens, photos, requests and generated code never leave your computer.
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

VisionClaw's code is licensed under the GNU General Public License, version 2 or later. See [LICENSE](LICENSE).
