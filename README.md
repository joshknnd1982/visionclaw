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

> **Status: first pre-release (0.1.0).** The orchestration core has been tested with scripted models and with a
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

1. Download **[VisionClaw-0.1.0.nvda-addon](https://github.com/joshknnd1982/visionclaw/releases/download/v0.1.0/VisionClaw-0.1.0.nvda-addon)**
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
When there is not enough memory for both models at once, they take turns.

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

## Add-ons written by VisionClaw

The coder model writes the add-on. Before it can run, the code must pass a check (it must be valid, must not
start programs, use the network, or delete or write files, and must follow NVDA's rules for events and key
commands), the other model reviews it (unless reasoning is set to Off), and **you are always asked** whether to turn it on, with the option to
read the code first. If NVDA cannot start it, the error goes back to the coder model to fix. Generated add-ons
load without restarting NVDA and come back after a restart. "List what you have made" and "remove the add-on
..." manage them.

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
settings.

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

VisionClaw does not collect any information. It connects to the internet only to download the models you
choose, from Hugging Face. Screens, photos, requests and generated code never leave your computer.

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
