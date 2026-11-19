# VisionClaw — instructions for Claude

VisionClaw is an NVDA add-on, forked from VisionMate (athee06/VisionMate, GPL v2 or later). It joins three things
on the user's own computer, with nothing sent to the internet:

1. a small local **Qwen vision model** (default Qwen3.5-2B),
2. a small local **Qwen coder model** (default Qwen2.5-Coder-1.5B),
3. a **SmallClaw-style agent core** (planner, tool loop, skills, memory, verifier, self-repair), ported to Python
   so it can run inside NVDA.

The user types or dictates any request. The two models plan it, agree on the plan, and carry it out with NVDA
tools: changing NVDA settings, looking at the screen, and writing small NVDA add-ons on the fly.

The owner, Josh Kennedy (GitHub `joshknnd1982`), is blind and uses NVDA. Everything you build must be usable by
keyboard and speech alone.

## What the owner cares about most

1. **Accuracy and ease of use for the end user**, ahead of features and speed.
2. **Bite-size steps, always.** These are small models. Every request, simple or complex, becomes a short list
   of small steps. One step is one tool, and the model only fills in that tool's small form. Python does the
   rest. Never hand a small model a big open-ended job.
3. **Making stubborn, inaccessible Windows apps, games and custom controls usable**: reading the window from its
   picture, clicking items by name, naming unlabelled controls, app helpers with their own hotkeys, and
   generated add-ons when nothing simpler will do. Prefer the simplest of these that works.
4. **A person who has never used NVDA** must be able to work the screen reader in plain language: find and run
   any NVDA command or setting by describing it, and be told the keyboard shortcut for next time.

5. **Always give the user a choice.** Never hide a model or an option because of the computer it runs on.
   Every model in the catalog, including the 7B and 9B ones, is offered with every graphics option (they are
   still fast through Vulkan on modest PCs). Hardware only decides what is suggested first.
   The owner said on 2026-11-18: "user should be able to choose between q4_k_m and q6_k for everything.
   **user choice** visionclaw suggests, user can take the suggestion or make his own model and quant choices."
   Every model is offered as Q4_K_M and as Q6_K (`catalog.QUANTS`). Each quant is an entry of its own in the
   same folder, so the vision projector is shared and downloaded once, and an older VisionClaw can still read
   `models.json`. The Q4_K_M entries keep their old ids, so an older setting without a quant still means
   Q4_K_M. The models window has a second list under each model for its quant, with sizes and plain words
   (`dialogs.modelLabel`, `quantLabel`). The suggested model and quant are marked, never forced. Q4_K_M is
   suggested unless measuring shows Q6_K clearly better for a model (`catalog.SUGGESTED_QUANTS`, measured
   with `tests/live_quants.py`). A stored model is one folder and quant (`catalog.storeKey`), so the quant no
   longer used can be offered for removal. A new model in the catalog comes in both quants, from the same
   publisher and revision, or the owner is told which quant is missing.

6. **The user cannot read, write or debug code.** Never make the user's safety or success depend on looking at
   code. Say what code does in plain words taken from the code itself (`microaddons.describe`). When generated
   code fails, the models debug it (`helpers._guard`, `nvdatools.fixAddon`); the user at most says in words
   what is wrong.

## Rules that always apply

- **Everything is about how blind people use computers.** The owner said on 2026-11-17: "prompts and
  memories and skills **must** always be relevant to how *blind* people use computers." Every prompt, every
  memory VisionClaw keeps or offers, every skill (built in or written by the user), every recipe and every
  answer is about working the computer with the keyboard, speech and braille through NVDA: keys and commands
  written exactly as NVDA names them, places said in words, nothing that only a sighted person can follow
  ("click the blue button", "look at", "as you can see", "hover over it"), and the user told what changed.
  The mouse is not sighted-only: blind people work it with NVDA's keyboard commands when they need it (the
  owner, 2026-11-17), so never drop or down-rank something for naming the mouse; leave out only what needs
  sight or a hand on the mouse, and give a plain key first, NVDA's keys that work the mouse next. Model calls that
  word something for the user take their system prompt from `prompts.speaking(task)` or `prompts.seeing()`
  (`claw/prompts.py`), whatever model is chosen, so these instructions always apply.
- **Add-ons written on the fly get the same instructions, skills, memories and notes.** The owner said on
  2026-11-17: "system prompts and memories and rag and skills must also apply when the local AI models are
  generating nvda addons on the fly for the nvda user." Every model call that writes, reviews, repairs or
  debugs a generated add-on (`claw/microaddons.py`, `nvdatools.fixAddon`, `helpers._guard`) has the
  instructions for blind users in its system prompt (`prompts.coding(task)`), and its user message carries
  what is relevant to the request: the knowledge notes (RAG), the skills that match, and what the user asked
  VisionClaw to remember. Keep each short, one small step at a time; the add-on itself speaks through
  `ui.message` in plain words and is worked from the keyboard. Measure with `python tests/live_addon.py`.
- **Code-writing skills, instructions, notes and memories are chosen by the request.** The owner said on
  2026-11-17: "there must be special code-writing skills, system prompts, rag, memories... they must trigger
  when visionclaw deems each skill is appropriate according to user prompt." Plain code decides from the
  user's own words which of them fit: the code-writing instructions added to the system prompt
  (`prompts.coding(task, purpose)`, `prompts.CODE_KINDS`), the skills (`claw/skills.py`, `stepGuide`,
  `addonGuide`), the knowledge passages and what the user asked VisionClaw to remember
  (`memorytools.forCoder`). Only what fits is sent, never all of it, and nothing when nothing fits; a small
  model reads a few short, relevant lines better than many.
- **Local only.** The add-on's own code connects to the internet only to download models, and only after the
  user says yes. Never add telemetry, cloud APIs, or update checks. The web tools hand an address to the user's
  own browser when the user asks; the models never go online.
  One exception, which the owner approved on 2026-11-17 as "button only": the models window has a button,
  "Look for newer models", that asks first and then reads one file, `models.json`, from VisionClaw's own
  GitHub repository (`catalog.LIST_URL`). It must never run by itself, on a timer, or at start-up, and it must
  never send anything but the request.
  A second exception, which the owner asked for on 2026-11-17: the tool `update_guides` downloads the NVDA
  Developer Guide (NV Access) and the NVDA Add-on Development Guide (the NVDA add-ons community) and keeps
  them as Markdown for the models to read (`claw/guides.py`). Only when the user asks for exactly this, always
  after a question (`mustAgree`, whatever the settings say), only from the addresses and servers fixed in
  `guides.SOURCES` and `guides.HOSTS`, and nothing is sent but the two requests. What comes back is text to
  read, never run. Never add a source without the owner's yes.
  A third exception, which the owner asked for on 2026-11-17 ("add a feature which checks for visionclaw addon
  updates and gets the latest version for the user, either automatically or manually from my github"):
  VisionClaw reads the list of releases of its own repository from GitHub's API (`updates.RELEASES_URL`) to
  see whether a newer version exists (`claw/updates.py`, `updater.py`). When: only when the user asks
  (NVDA+Alt+U, the button in the settings, the tool `check_update`, which asks first), unless the user sets
  "Look for a newer version" to the automatic choice; then also when NVDA starts, at most once a day. The
  default is "only when I ask", and must stay so. Found by itself, a newer version is only announced, in one
  sentence, with no window. Nothing is downloaded without a yes, only the release's own
  `VisionClaw-<version>.nvda-addon` at github.com under this repository may be downloaded, a file without a
  size and SHA-256 from GitHub is refused, and the installing is left to NVDA, which asks its own question.
  Nothing is sent but the request. The SHA-256 comes from GitHub like the file: it shows the file arrived
  whole, not who made it; say it that way.
  A fourth exception, which the owner asked for on 2026-11-17 ("identify the application or game I am in,
  search the internet, learn about the current app or game, make quick notes in markdown about it which the
  user can always delete later, then let me ask questions about it"): the tool `learn_app` goes online to
  learn about a program (`claw/learn.py`, `learntools.py`). Only when the user asks for exactly this, always
  after a question (asked directly, whatever the settings say) that says what is sent: the program's name to
  Wikipedia (`learn.WIKI_HOSTS`), a request to Wikidata (`learn.WIKIDATA_HOSTS`) for the address of the
  program's own website and manual, and requests to that website for at most `learn.MAX_PAGES` pages, over
  https only, on the same server as the address Wikidata gave. Nothing is sent but these requests; they call
  themselves "VisionClaw/<version> (NVDA screen reader add-on)" and carry nothing about the user. What comes
  back is text to read, never run, and is kept as Markdown in the folder `notes` of VisionClaw's data.
  A fifth exception, which the owner asked for on 2026-11-18 ("search and apply info from all nvda user
  guides, help documentation and free training material that it can find and download, converting it to
  markdown") and said yes to source by source the same day ("Yes, the wiki", "Also AFB and Hadley", "you may
  download them, and user must be able to request them through visionclaw"): the tool `update_training`
  downloads free material that teaches NVDA (`claw/training.py`): six pages of the NVDA wiki on GitHub, the
  eight lessons of the American Foundation for the Blind's "Learn NVDA" and the four workshops of Hadley's
  "NVDA Screen Reader Series", the last two as the transcripts on their pages. Only when the user asks for
  exactly this, always after a question (`mustAgree`, whatever the settings say) that names every site and the
  number of requests (`training.question`), only from the addresses and servers fixed in `training.SETS` and
  `training.HOSTS`, over https, and nothing is sent but the requests. What comes back is text to read, never
  run. AFB and Hadley keep their copyright and the wiki states no licence: every file says at its top where
  it is from and whose it is, it is kept for the user's own reading on this computer, nothing of it is passed
  on or put into the add-on, and an answer made from it says where it is from. The one exception is the
  portable copy the user makes of their own VisionClaw (see "The data folder is inside the add-on"): the owner
  said it carries everything, and the window says that the owners keep their copyright. A site that answers a program
  with a challenge is not to be worked around; the earlier copy stays. Never add a source without the owner's
  yes; `tests/test_training.py` fails when the sources or servers change.
  A sixth exception, which the owner said yes to on 2026-11-18, asked "may VisionClaw offer it from ggml-org, and
  may I download the small one (about 1 GB) to this computer to test it?": "Yes to both". The speech model for
  asking by voice, Qwen3-ASR by the Qwen team (Apache 2.0), is downloaded from `ggml-org`, the llama.cpp
  project's own page on Hugging Face, because neither Qwen nor Unsloth publishes it in the engine's format
  (`claw/voice.py`: `MODELS`, `PUBLISHER`). Only when the user asks to speak a request or for the speech model,
  always after a question that names the model, its size and where it is from (`voice.downloadQuestion`;
  `mustAgree` in the tool), every file pinned to one revision with its size and SHA-256. **ggml-org is allowed
  for the speech model only**: `catalog.PUBLISHERS` is unchanged, the speech models are no part of `CATALOG` or
  `models.json`, and `catalog.checkEntry` knows no such role, so a fetched list can add neither a speech model
  nor ggml-org (`tests/test_voice.py` checks all of it). It exists only as Q8_0 (and bf16): there is no Q4_K_M
  and no Q6_K, and the owner was told so. Never add another speech model or publisher without the owner's yes.
  **No search engine is asked by the add-on's own code.** It was tried on 2026-11-17: DuckDuckGo's page for
  people answered with its challenge for automated traffic after a handful of requests. That is the site
  saying no to programs, and it is not to be worked around: no browser-like headers, no other endpoint of a
  search engine, no retries against a challenge. A general web search goes through the user's own browser
  (`web_search`), and a page the user has open there can be added to the notes (`note_page`), which reads it
  through NVDA and fetches nothing. Never add a source to `learn.py` without the owner's yes.
- **The latest small Qwen models are always offered.** The owner wants every small size of the newest Qwen
  vision and coder models in the lists. When asked to bring them up to date, do not answer from memory: read
  Hugging Face's own listing (`https://huggingface.co/api/models?author=Qwen&sort=createdAt&direction=-1`, and
  the same with `author=unsloth&search=Qwen` for the GGUF files), take revision, size and SHA-256 of each file
  from `https://huggingface.co/api/models/<repo>?blobs=true`, add the entries to `CATALOG`, set
  `catalog.LIST_UPDATED`, run `python tools/write_models_list.py`, and push `models.json`: every installed copy
  then gets the new models from the button, without a new release. Only Qwen models under Apache 2.0 from the
  publishers in `catalog.PUBLISHERS`; anything else needs the owner's yes. A model of a new family may need a
  newer engine: give it `minVersion` in the list, and say so. A fetched list can never widen what may be
  downloaded (`catalog.checkEntry`); keep it that way.
- **Never cut off speech and braille.** Anything that could leave a screen reader user with neither goes
  through `claw/drivers.py`: refuse what is certain to, always ask first, switch back unless the user confirms
  that it works, and remember what failed. New tools that touch speech, braille, audio or NVDA's own running
  must use `mustAgree`, never the optional `confirm`.
- **Never break the screen reader.** Do not install, enable, disable or reload add-ons in the user's running
  NVDA, and do not restart NVDA, without asking first in chat. Test with plain Python and the stub harness.
- **Small models first.** Every prompt must work on a 1.5B to 4B model. That means: constrained JSON
  (`response_format` json_schema) for every decision, one small step at a time, short prompts, trimmed
  observations, and deterministic Python doing everything that does not need a model.
- **The `claw/` package has no NVDA imports.** Anything that touches `api`, `config`, `ui`, `wx`, `gui` lives
  outside it (`nvdatools.py`, `clawui.py`, `__init__.py`). This keeps `claw/` testable with plain Python.
- **Every task is interruptible.** Every loop and every model call takes the task's cancel event. Never add a
  blocking wait that ignores it.
- **The user stays in charge.** Models must agree before a task starts; when they do not, the user chooses.
  Settings changes and new add-ons are confirmed with the user unless they turned confirmations off.
- **Generated code is checked before it runs** (`claw/microaddons.py`): it must parse, pass the safety check,
  and be approved by the user. The safety check prevents accidents; it is not a sandbox. Never describe it as one.
- **Code style:** tabs, camelCase, `# Translators:` comments on every user-visible string, `_()` for
  translation, the GPL header on every file. Files changed from VisionMate keep Athiban Vijay's copyright line
  and carry a "Modified for VisionClaw" line. Python must run on NVDA 2024.1 (Python 3.11) and later.
- **Honest reporting.** Say what was tested and how. "Compiles" and "unit tests pass" are not "works in NVDA".
- **One model is never called two.** The user may choose one model for both jobs. Then nothing the user hears
  or reads may say "both models", "the two models", "the other model", "the vision model", "the coder model"
  or "agree": it is "the model" (`policy.roleName`, `policy.isOneModel`), and the same question is not put to
  it twice. A new sentence that names a model's role needs both forms, and `tests/test_one_model.py` fails on
  one that does not.
- **What plain code can correct, plain code corrects.** A small model keeps what it once wrote however often
  it is told. Before sending code back to the coder, `microaddons.tidy` takes out what was not asked for, adds
  forgotten imports and `nextHandler()`, fixes role comparisons, adds a program limit, and salvages a file that
  was cut off. Add to `tidy` whenever the real model shows a new mistake of this kind, and never show the coder
  an example that does two things: it copies all of it.
- **Never put an example in a message a model reads after a failure.** It copies the example as if it were the
  answer: "try other words, like speech rate" made the model change the speech rate. Say what is needed in
  general words.
- **Only what the user asked about is changed, and every change can be undone.** A tool that changes something
  takes the user's own words (`asked`, an `auto` field), refuses when they say nothing about its target
  (`nvdatools.related`), records the old value (`claw/changes.py`), and shows the request in its question.
  Never learn a lesson from a search tool: finding something is not finding the right thing.
- **What VisionClaw knows, plain code says.** A model does not know its own name, its size or where it runs,
  and makes something up when asked. Questions about VisionClaw itself (its models: `model_info`,
  `runtime.aboutText`; its version: `check_update`) are answered from the settings and the disk, word for
  word. When a question about VisionClaw gets a wrong answer, look first for a missing recipe.
- **The user's own words decide which thing is meant.** When the request names exactly one item of the list
  (two for a drag), that is used, whatever the model wrote in the form (`nvdatools.mentioned`, `meant`). Give a
  tool that picks an item the `asked` auto field.
- **Tests never move the real mouse or type into the real computer.** `tests/test_nvda_stub.py` replaces
  `mousetools.moveTo`, `mousetools._button`, `mousetools._key` and `nvdatools.typeUnicode` with functions that
  write down what would have happened. The same holds for fingers, the pen, the mouse's own movement and a
  game controller: `touchinput._touchFrame`, `touchinput._penFrame`, `mousetools._relative`,
  `mousetools.pointerState`, `padtools._find`, `padtools._read` and `padtools._vibrate` are stood in for, so
  that no test depends on what is plugged into the computer. One file does touch the real computer,
  `tests/live_touch.py`, only with `--yes`, only inside a small window of its own that never takes the
  focus; never run it for the owner without asking, and never add it to `run_all.py`.
- **Every way a sighted person works a control has a keyboard way, and every kind of control is known.** The
  owner said on 2026-11-18, of controls worked by hovering, holding the button down, gestures and timing: "I
  want those to be on the list of visionclaw controls which visionclaw must be able to make accessible too",
  then "if you can think of any other controls to add ... add those", and "both controls and control types".
  The list is `working.WAYS`: click, double click, right click, type, open and choose, drag up and down,
  sideways, in a circle, in any direction, to another place, the mouse wheel, hover, press and hold, swipe or
  draw, click at the right moment, touch with fingers, press with pressure, move the mouse to look. Each has a
  means that really does it (`claw/pointer.py`, `mousetools.py`; for the last three see the next rule):
  `click_item` (also the middle button, three clicks, a key held down, a place on the item, hovering with what
  appeared read out, holding for a time), `draw_gesture`, `timed_click`, `scroll_view` (also zoom), a hotkey
  that holds or hovers (`helpers._pointed`), and the keys of pointer mode. A new way needs all of: a line in
  both questions to the models, a remedy (`working.remedy`, `adviceFor`), a means, a case in
  `tests/live_working.py`, and what it cannot do said in plain words. Every kind NVDA has is sorted
  (`working.knownRole`; the list in `tests/test_working.py` was read from the installed NVDA's
  `controlTypes.Role`; read it again for a newer NVDA, do not write it from memory). What a control's own name
  says ("Hold to record") is decided by plain code (`working.bySaid`), kept narrow. A mouse button or a key
  that VisionClaw presses down always comes up again: in a `finally`, when the request is stopped, and after
  `pointer.HOLD_LIMIT` for a hotkey; never add a way to leave one down.
- **Every key VisionClaw gives a job is one that every keyboard has.** The owner said on 2026-11-18, of pointer
  mode: "it says the applications key right-clicks. some keyboards don't have an application key. this must be
  changed to a more standard keyboard key. assume some don't have pageup, pagedown, home, end, either." So a
  mode of VisionClaw's own (pointer mode, the overlay, a held dial or slider, anything added later) does every
  job with letters, the arrow keys, Enter, Space, Escape, Shift and Control. The Applications key, Page Up, Page
  Down, Home, End, Insert, Delete, the function keys and the number block may be missing: such a key is only
  ever a second way (`pointer.EXTRA_KEYS`, `dragcontrol.EXTRA_KEYS`), and no spoken help, description or note
  of VisionClaw names it. In pointer mode A right-clicks, I, K, J and L turn the wheel, B goes to the middle;
  for a held control T and B go to its ends; in the overlay A right-clicks. `tests/test_pointer.py` fails when
  a job has no such key. Keys of Windows and of NVDA itself are said as they are. A click or a turn of the wheel
  that a key of pointer mode starts waits until the user's Shift, Control and Alt are up (`mousetools.keysUp`):
  held down they change what the mouse does, so nothing is done and that is said when they stay down.
- **Fingers, pressure, a game that reads the mouse directly, and a game controller.** The owner said on
  2026-11-18, of what 1.1.0 had named as not covered: "visionclaw must be able to make these controls
  accessible as well. Find a way or multiple ways to do this, using visionclaw and its offline local models,
  skills, memory, rag, and system prompts"; and of a controller: "support the detection of this, if detected,
  visionclaw must add accessibility for various movement and button presses and clicks and pressure across all
  possible windows, app and game controls". What follows from it:
  - **Fingers and pressure** (`claw/touch.py`, `touchinput.py`, `touchtools.py`): `touch_gesture` touches the
    screen as one to five fingers would, `pen_stroke` presses as a pen would. Which gesture, how many fingers
    and how hard is read from the user's own words by plain code. A pinch, a spread and a turn always mean
    fingers; a swipe, a tap and a hold only where the words speak of fingers or touching, since the mouse does
    them too.
  - **More than one way, and the least that works.** A touch is tried, the window is compared before and
    after, and where nothing changed the mouse wheel stands in (`touch.instead`): for a pinch, a spread and a
    swipe with two fingers. The user is told which worked, and that is kept for the program
    (`direct.AppWays`, the file `appways.json`), so the working way comes first the next time. It is data,
    never code. Where nothing stands in, as for a turn with two fingers, that is said.
  - **What is put down is lifted.** Fingers and the pen come up in a `finally`, when the request is stopped,
    and when Windows refuses a report. In controller mode what a trigger holds comes up when the trigger is
    let go, when the mode is turned off, when the controller goes away and when NVDA closes
    (`padtools.Controller._release`).
  - **NVDA's own touch handling** is put aside only with NVDA's own `touchHandler.setTouchSupport`, only for
    the moment of a gesture, always after a question (`mustAgree`), and always put back in a `finally`.
    NVDA's setting is not changed. Read `touchHandler.py` in NVDA's source again before changing this.
  - **A game that reads the mouse directly** (`claw/direct.py`): the mouse itself is moved by a number of its
    own steps (`mousetools._relative`, `nudge`). Which kind a program is, a view the mouse turns or a pointer
    of its own, is told by the user in words (`mouse_way`) or with M in pointer mode, kept as data, and used
    only while Windows' own pointer is hidden there (`mousetools.pointerState`, `directScope`). For a view,
    `turn_view` moves the mouse and says whether the picture changed, and a tool that points at a place
    refuses with a sentence that says what to ask for. For a pointer of the game's own, `direct.Tracker`
    pushes it into the corner of the window and counts from there; its speed is measured from three pictures
    and never guessed in silence. How far a game turns is a guess until the user says too fast or too slow;
    say that it is a guess.
  - **A game controller** (`claw/gamepad.py`, `padtools.py`) is only ever read. Out of controller mode its
    sticks and buttons are the user's: only View and Menu held together, and buttons the user made hotkeys,
    do anything. Never add a virtual controller or a driver, and never press a controller's buttons for a
    game. Whether a connected controller is announced is the user's choice (announce, quiet, off); the
    announcement is one sentence. Everything controller mode does is spoken; the buzz is never the only
    sign, because Windows may not give the motors to a program that is not in front. A button as a hotkey is
    a helper like any other (`helpers.runPad`, kept as `pad:` and the button's name).
  - **Windows' own structures** for touch, the pen and controllers were read from Microsoft's pages on
    2026-11-18, named at the top of `touchinput.py` and `padtools.py`. When they are changed, read the pages
    again; do not write a structure from memory.
  - **The notes** that answer questions about all this (`claw/knowledge/visionclaw-inputs.md`) were written
    from VisionClaw's own code and are asked only when a question names a controller, fingers, pressure or a
    game's mouse (`lookup._INPUTS`). When a button's meaning changes in `gamepad.py`, change the notes, the
    skill, the README's table and the help page with it.
  - **A tool's answer is cut at `tools.RESULT_CHARS`.** A help text that a tool gives back word for word
    (`gamepad.HELP`, the help of pointer mode) must fit with what is said before it.
- **A recipe that reads everything from the user's words is checked against them.** When a model chooses
  `timed_click` or `gesture` and the words name no moment and no count, or no direction and no shape, plain
  code takes what the words point to instead (`planner.fitted`). Both real models sent "press and hold ... for
  2 seconds" to the timed click twice, hint or no hint.
- **In a question to a model, the order of the choices matters.** With the click listed first, Qwen3.5 9B
  called an upright fader a click; with the ways of dragging first, it named all twelve drawn controls
  rightly (`working.VISION_SYSTEM`, 2026-11-18). Measure before moving a line.
- **Accessibility fixes are data, not model code.** A fixes add-on is `fixes.build(scope, fixes)`: the text of
  `claw/fixmatch.py` and `fixruntime.py` below their marker lines, plus the fixes as a literal. Never let a
  model write or repair it (`nvdatools.fixAddon` refuses), and never hang a fix on something that is not fixed
  in the page's code: class names made by a tool are shared by unrelated controls (`audit.telling`). A new kind
  of fix goes into `fixruntime.py` and `fixes.py` together, with a case in `tests/test_access.py` that runs the
  generated add-on against the stand-in page. Whatever `fixruntime.py` uses must pass `microaddons.check`
  (no ctypes, setattr or files) and must never let an error reach NVDA.
- **No fixed pixel sizes.** Screens differ in size and scaling, and NVDA works in real pixels on each
  monitor. A size that should look the same to the eye is written for a plain screen at 100 percent and
  turned into pixels with `scrolling.pixels(size, scale)`, where the scale comes from `mousetools.scaleAt`;
  a distance inside a window is a share of the window. A place that is kept, as in a fix or a helper, is kept
  as a name or a share, never as pixels.
- **Say whether it moved.** After the wheel is turned, the picture before and after is compared
  (`scrolling.moved`), and the user is told what happened, not what was attempted.
- **A dragged control is worked the least risky way that works.** Through Windows itself where the program
  offers its value, then the wheel, then dragging up and down, sideways, and around last (a press on the rim
  of some dials sets the value at once). The way is found by trying one step and one step back
  (`ControlKeys.probe`), after the user said yes, and the user is told whether anything changed. A kept control
  is data in `helpers.json`; never generate code for it.
- **How a control is worked is decided by facts first.** A model is asked only about controls whose kind NVDA
  cannot tell, one small form each (`working.JUDGE_SCHEMA`), at most `working.MAX_JUDGED` per inspection, and
  the report says that a model can be wrong.
- **A model writes only what the results allow.** Where the step before found the possible answers (the ids
  of settings or commands, the names of listed items, on or off, a setting's options, a number), plain code
  turns them into the form's only allowed answers (`claw/shapes.py`, `Tool.schema(skip, shapes)`), for every
  model. A new tool whose field takes something an earlier tool found gets a line in `shapes.SOURCES`.
- **The very smallest models get one small question at a time.** When the model that fills in forms is one
  that is never suggested (`policy.stepwise`; the user can also choose Always or Never), a form is filled in
  one field per call (`agent.fillOneByOne`), each answer narrowing the next; an answer that repeats the
  question is asked for again; and looked-up information is answered with a line of it, word for word, chosen
  by plain code and at most picked among by the model (`orchestrator._quoted`), never rephrased. A very small
  model cannot say "none of these", so never give it that as a choice: let plain code decide whether anything
  fits.
- **An NVDA command is run with a key press, as often as the user's words ask.** NVDA asks every command's
  key press a few things before it runs the command, so `scriptHandler.executeScript` is never given None:
  the key press is made from the way NVDA writes the key (`nvdatools.keyGesture`; NVDA shows "ctrl" and knows
  "control"), and a command without a key gets a stand-in (`nvdatools.noKeyGesture`). What a second or third
  press does is read from the command's own description (`commands.byPress`, `commands.presses`), never asked
  of a model. Commands are ranked by the word that tells them apart (`claw/ranking.py`), and when nothing
  fits, plain code says so. Check a change against `tests/nvda_commands.json`, every real command of NVDA.
- **A fault inside a tool ends its step, not the request.** `Registry.call` turns an unexpected error into a
  failed step with a sentence for the user, and writes where it happened to VisionClaw's log. Stopping, a
  no from the user and a lost engine are passed on (`tools.PASSED_ON`).
- **What happened is written to VisionClaw's own log** (`claw/debuglog.py`; from NVDA-side files through
  `vclog.log`, which also writes to NVDA's log). The owner asked for detailed logs on 2026-11-17, and NVDA's
  logging level is often Off. Every request, step, form, question to a model with its answer, tool result,
  question to the user, engine start and error goes there. New code that can fail logs the failure with
  `debuglog.error`. The log is a file on this computer: nothing may ever send it, the user chooses Detailed,
  Brief or Off, and Detailed must stay the default. Nothing in `debuglog` may raise.
- **What is inside NVDA is read from the running NVDA.** `claw/inside.py` lists every loaded module of NVDA
  and the add-ons with what it has; nothing is taken from a list written in advance, so a newer NVDA and
  unknown add-ons are covered. Looking never changes anything: only a function that merely reports and needs
  nothing (`inside.reports`: get, is, has) is called to say what it gives back. The notes in
  `claw/knowledge/nvda-inside.md` were written from NVDA's source with `tools/audit_nvda_source.py`; when
  they are brought up to date, read the source again, do not write from memory.
- **A question is asked of NVDA, then the program, then its window, then Windows, every time.** The owner
  asked for this on 2026-11-17, after "How can I use the keyboard to navigate my desktop?" was put to NVDA's
  commands alone and answered with the command that switches the keyboard layout. The tool `look_up`
  (`asktools.py`) asks all four, always, in that order: NVDA's commands where the user is, its whole user
  guide and its add-ons' help; the program in front; its window, the focused control and the controls that
  have keys of their own; Windows' version, the open windows, and the notes in
  `claw/knowledge/windows-keyboard.md`. Every one gives small passages, and plain code ranks all of them
  together by what the question names (`claw/lookup.py`): a passage must cover enough of it
  (`ranking.rank(cover=)`), words that only say "with the keyboard" count for almost nothing, a written-out
  key finds what that key does, and "what is" gets an explanation before a command. When nothing is about
  the question, plain code says so (`lookup.nothingText`) and no model is asked. Never send a question to
  one source alone again, and never let a recipe for questions end in `find_command`.
- **The notes on Windows are one answer to a section.** `windows-keyboard.md` was written from Microsoft's
  page "Keyboard shortcuts in Windows", read on 2026-11-17; the smallest models give a section to the user
  word for word. When it is brought up to date, read Microsoft's page again, keep each section under about
  340 characters, and put the words people ask with into its heading.
- **What is new in a version is read in an edit box.** The owner asked for this on 2026-11-17. A newer
  version is offered in `updater.UpdateDialog`: a read-only, multi-line edit box with what is new, one point
  to a line (`updates.offerText`), and two buttons. Never put it back into a message box, which can only be
  listened to once.
- **The models are used where they are good, and plain code checks what they write.** The owner asked on
  2026-11-17 that VisionClaw use its models to be more intelligent and more aware of where the user is. A
  model chooses among things plain code found, or writes something plain code can check: which of a
  program's names it is known by and whether it is a game, a program or a utility (`learn.identify`); short
  notes from one section of a page at a time, of which only those are kept whose keys and most of whose
  words are in that section (`learn.writeNotes`, `learn.checked`); what "this", "it" or "here" in a question
  means, among the program, the window and the focused control (`lookup.referent`), unless the user's own
  words say it (`lookup.saysWhich`); and, for a model that is not one of the very smallest, which line of
  what was looked up answers the question, or that none does (`orchestrator._pick`, `lookup.NO_ANSWER`).
  A very small model (`suggest` is False) is never asked to write notes or given "none of these". A model
  step that only helps, such as what "this" means, must never end the request when the model cannot answer.
- **Notes on programs are the user's files.** One Markdown file for each program in `notes`, which says at
  its top where it is from and that it may be wrong. `forget_notes` deletes one or all after a question;
  adding to notes never rewrites what is there (`learn.merged`), because the user may have written into it.
  Notes answer questions as passages of the program (`learn.passages`), each saying which website it is from.
- **Memories are the user's files too, and kept only when needed.** The owner asked on 2026-11-17 that
  VisionClaw save memories in Markdown the way Claude does, only when necessary, and that the user can delete
  some or all of them and start over. One file for each memory in the folder `memories` of VisionClaw's data,
  with a few lines at its top (name, description, type, program, saved) and an index, `MEMORY.md`, made from
  the files (`claw/memories.py`). What is kept is the user's own words, turned from "I" to "you" by plain
  code; no model writes or rephrases a memory. A memory is kept when the user asks (`remember`), or, if the
  setting "Remember things" allows it (the default), when the user says something lasting about themselves or
  how they like things done, nothing else in the request kept it (a changed setting is kept by NVDA), and it is
  about how they work the computer (`memories.worthKeeping`); the answer then says so and how to undo it. A
  new memory about the same thing replaces the old one. Memories go with a request to the planner
  (`orchestrator._context`) and answer questions through `look_up`. The user forgets one, the last, or all in
  words (`forget_memory`; all is always asked about) or in the memories window (`memoriesui.py`: a list with
  check boxes, the whole memory, Forget checked, Forget all and start over), from the settings or a command
  without a key. `claw/memory.py` is something else: lessons about failed forms, for the models.
- **The library is retrieval, done by plain code.** Every source `look_up` asks is cut into small passages;
  plain code finds those about the question, and only they reach the model (`claw/lookup.py`). After NVDA, the
  program, its window and Windows come the user's library (`claw/library.py`: Markdown, text, saved web pages
  and Word documents in the folder `library`; a document whose name names the program in front counts as that
  program's) and the memories. Notes on accessibility interfaces (`api-*.md`) and on common programs
  (`app-*.md`) carry a gate in `lookup.NOTES`: they are asked only when the question, or the program in front,
  names what they are about, so that "how do I press a button" is not answered with the ARIA role. These notes
  were written on 2026-11-17 from the pages named at the top of each file; when they are brought up to date,
  read those pages again, keep each section to one answer with the asking words in its heading.
- **No question about a described picture is refused.** VisionMate asked the model first whether a question
  was "about the image", and a small model said no to what a blind person most needs to ask. The description
  window answers everything (`followup.ANSWER`); the one rule is that what is not shown is said to be not
  shown. Do not bring a gate back.
- **Every answer and description is told who the user is.** The owner asked on 2026-11-17 for global
  instructions made for blind people, after VisionAssistantPro's. `claw/prompts.py` holds them in three parts:
  who the user is (blind, speech or braille), how an answer is worded to be heard (start with the answer, no
  Markdown, names, numbers and keys copied exactly, places in words, nothing only by its colour, say what is
  not known), and what matters in a picture (text exactly, focused, selected, checked, greyed out, no guessing
  who someone is). `prompts.speaking(task)` is the system prompt of every answer a model writes for the user,
  `prompts.seeing()` of every description and question about a picture, then the user's own instructions and
  language. The user reads and rewrites all of it in "How VisionClaw answers" (settings); VisionClaw's own
  wording is kept as "" so a newer one reaches them. Forms, code, notes and judgements get only
  `prompts.IDENTITY`: the user's words could change ids a form must copy. No examples in these parts, and no
  model's role named in them (`tests/test_prompts.py`).
- **Skills are text, chosen by plain code.** A skill (`claw/skills.py`) only tells the models how a kind of job is
  done well for a blind person; it never holds code, and every tool still asks before it changes anything. Plain
  code chooses it from the request's words: a phrase of several words must be there word for word unless two or
  more of its words tell what it is about, so an everyday word alone ("read", "key") never starts a skill. Its
  sentences go only to the steps of the jobs in its `uses`, and to the answer; never to the very smallest
  models' one-field questions, and never to the model that chooses the recipe. A skill with steps runs them as
  they are only when the request has a starting phrase word for word. What a skill made in words tells
  VisionClaw is the user's own words, and only starting words the user said are kept. A built-in skill is
  never deleted, only turned off; the user's copy of one takes its place. Built-in skills have no examples, no
  Markdown in their sentences, and stay under `skills.GUIDE_CHARS`; `tests/test_skills.py` checks every one.
  Every skill is about how a blind person works the computer: keyboard, speech and braille. Where a program needs
  the mouse, a skill leads to the keyboard way first and then to NVDA's keys that work the mouse, taken from
  `tests/nvda_commands.json`, never to "click the icon at the top right". A one-word starting phrase matches
  by its stem, so check that the stem is not an everyday word ("news" became "new").
- **The developer guides are put to use a line at a time, and only where they add something.** The owner
  said on 2026-11-18: "if the user asks to download the nvda development guides in markdown ... then we must
  also have appropriate skills, rag, memory, and system prompts to optimise the visionclaw addon and its AI
  models and smallclaw abilities along with the original visionmate features". What follows from it
  (`claw/guides.py`):
  - **Kept as they were written.** A code example keeps its indentation: one written indented is put between
    fences (`guides.tidy`), and a line that begins with # inside an example is a comment, not a heading
    (`guides.cut`). VisionClaw 1.1.0 and older lost both; such copies have no `format` in `guides.json`, are
    still read (`cut(old=True)`, `prose(old=True)`), and the user is told to ask for the guides again. Bump
    `guides.FORMAT` when the way they are kept changes.
  - **Read in three ways, each by plain code.** As sections of plain sentences without code, for questions and
    for speech (`guides.load`, `prose`); as single facts, one line about one name of NVDA's code
    (`guides.facts`: an item of a list that begins with a name, a row of a table that says what is wanted and
    how it is written; never a line of an example or a sentence of the running text); and as what is on the
    computer, from which day (`guides.storedText`, the tools `guides_info` and `remove_guides`).
  - **The writer of an add-on gets facts, never examples, and only new ones.** `nvdatools.coderNotes` puts in
    order what the coder reads: skill, memories and library, the lines of the guides, VisionClaw's own notes.
    A fact is given when the request names it (`guides.fits`), when the running NVDA still has its name
    (`nvdatools.nvdaHas`: loaded modules only, nothing imported or called), when it is not about Python's own
    modules or something a small add-on must not use (`guides.NOT_FOR_ADDONS`), and when the model is not told
    its name anyway (`known`: the coder's instructions and the notes sent). The last rule was measured with
    Qwen2.5 Coder 1.5B on 2026-11-18 (`tests/live_addon_guides.py`): a line that repeated the notes made the
    model write a key command where an event was asked for. With the rule, 2 of 9 requests got a line and
    both passed with and without it: no harm, and no gain measured either. Do not loosen it without measuring
    on the whole evaluation set.
  - **Instructions chosen by where the lines are from.** `prompts.CODE_GUIDE` goes to the coder only when its
    message has lines of the guides (`guides.CODER_HEAD`); `prompts.DEV_GUIDE` and `prompts.ADDON_HELP` go to
    an answer only when what was looked up is from the guides or from an add-on (`prompts.aboutFound`). The
    user can rewrite all three in "How VisionClaw answers".
  - **Skills**: `developer-guides` for answers, `addon-by-the-guides` for the coder; both start only when the
    request names the guides.
  - **Never a new source without the owner's yes**, as before: `guides.SOURCES` and `HOSTS` are unchanged, and
    `tests/test_guides.py` fails when they change.
- **NVDA's own help comes first, and is already on the computer.** The owner asked on 2026-11-18 that VisionClaw
  "search and apply info from all nvda user guides, help documentation and free training material that it can
  find and download, converting it to markdown". NVDA's user guide and its list of what is new come with NVDA,
  in the user's language and for the installed version, and are read from there: the user guide always, the
  list of what is new for its newest three versions and only when the question asks what is new, changed or
  fixed (`lookup.newsSections`, `lookup._NEWS`, `asktools.newsSections`). The key commands reference is made
  from the user guide and says nothing more. Free training material from the internet was researched on
  2026-11-18 by fetching every address (the list is in `docs/STATUS.md`): only NVDA's own documentation is
  clearly licensed; NV Access's Basic Training is paid. The owner said yes to the NVDA wiki, AFB and Hadley
  (the fifth exception under "Local only"). VisionClaw's own code still asks no search engine, so "find"
  means a fixed list; anything else the user finds can be added with `note_page` from a page open in their
  browser, or put into the library as a file.
- **Downloaded training material is asked after NVDA's own help, and each page only about what it is about.**
  It was written by others than NV Access, AFB's lessons in 2016. Its passages have a source of their own
  (`lookup.TRAINING`), which among equals comes after NVDA, the program, the window and Windows, and every
  page has a gate (`training.SETS`): the page for people from JAWS when JAWS is named, the ribbon page for the
  ribbon, the lessons when the user asks to learn, be taught or coached, or says they are new. What the user
  asked VisionClaw to remember about themselves opens a gate too (`training.comesFrom`): someone who said once
  that they come from JAWS gets that page without naming JAWS again. `prompts.TRAINING_HELP` goes with an
  answer made from it: say where it is from, and NVDA's own guide is right where they differ. Skills:
  `training-material`, `coming-from-another-screen-reader`. A lesson's web page is kept without the site
  around it (`training.lessonText`): the main part of the page, up to the first heading after which only the
  site's own offers follow (`stop`). When a site is rebuilt and that no longer fits, the page comes back too
  short, is refused, and the earlier copy stays; then read the page again and correct `stop`, do not guess.
  The wiki's own FAQ was left out because it says of itself that it is out of date.
- **Everything VisionClaw reads up in is a Markdown file the user can open.** The owner said on 2026-11-18:
  "all guides, wikis, and other materials should be converted to markdown (md) files to make it as easy as
  possible for visionclaw and its local AI models to work and interact with and learn from". In VisionClaw's
  data folder: `guides` (the developer guides), `training` (one folder for each source), `notes` (programs
  learned about), `memories`, `skills`, and `help`: NVDA's own user guide, its list of what is new, and one
  file for each add-on's help (`claw/helpfiles.py`). A file in `help` is made from the page that came with
  NVDA or the add-on, and made again when that page is newer or another one, as after an update or a change
  of NVDA's language; VisionClaw then reads the Markdown file, so what it looks things up in and what the
  user can open are the same text. A file that cannot be written is no fault: the page is read as it is. The
  user's own library is the one place that takes other kinds of file. New material is kept as Markdown, with
  a line at its top that says what it was made from.
- **Add-ons installed in NVDA are asked what they do; nothing is kept in a list.** The owner said on
  2026-11-18: "make skills, rag, memories and system prompts to detect addons, learn what they do, and help
  the user work with various addons depending on what the user wishes to do with the screen reader."
  `accesstools.installedAddons` reads every add-on from the running NVDA each time: its name, what it says
  about itself, whether it is on, its commands where the user is, its help. `claw/addons.py` turns that into
  passages that say which add-on they are from, and plain code finds the add-ons that say they do what the
  user wants (`addons.forWish`, `wishText`), or says that none does. `addon_info` does this when no add-on is
  named and the words say what is wanted (`addons.wishOf`). A command that an add-on adds says which add-on
  it is from when a question is answered with it (`accesstools.addonOwners`, `asktools.commandPassages`).
  **VisionClaw never installs, removes, turns on or turns off an add-on**, and says so of one that is turned
  off. The skill `work-with-add-ons` and
  `prompts.ADDON_HELP` word answers about add-ons.
- **NVDA Coach only when the user asks, and as much help as they ask for.** The owner said on 2026-11-18 that
  VisionClaw "should detect if it is installed if user makes a certain request, and interact with that addon
  giving the user lots of help, but only if user requests, while respecting the level of help the user is
  asking for". NVDA Coach (Tony Gebhard, GPL v2, id `nvdaCoach`) was read from its source at version 1.6.0:
  one command (`toggleCoach`), lessons as plain steps with hints in files of its own, a file of what is
  finished, no setting for how much help, nothing online. So the level is read from the user's own words
  (`addons.wants`): the Coach's window, the list of lessons, how far the user is, a hint and no more, one
  step, a whole lesson. The tool `coach` reads the lessons and the progress, never writes them, runs the
  Coach's one command only when its window is asked for, and says its text word for word. "Press Enter to
  continue" is taken out of a step, because said outside the Coach's window it would have the user press
  Enter in another program. Not installed: asked for by name, that is said; asked to be taught something,
  NVDA itself answers through `look_up` and the Coach is named once. When a newer NVDA Coach keeps its lessons
  differently they are not found and VisionClaw says so: read its source again, do not guess.
- **How much help an answer gives is the user's choice, and is remembered.** The skill `as-much-help-as-asked`
  goes with an answer when the request says how much. What the user asked VisionClaw to remember about it
  ("from now on, give me only a hint") goes with every answer a model words (`memories.helpWanted`,
  `orchestrator._helpWanted`), whatever the question is about.
- **In the description window, a question about a key is given the one NVDA command it is about, and nothing
  else.** A model that only sees a picture makes keys up: asked how to read the window's title, Qwen3.5 9B
  said "press Alt and then S". `followup.known` adds one line to a question that asks how something is done or
  which key does it: the command of NVDA, among those that work where the user is (`asktools.forPicture`),
  that has a key, is the best found, has a word of its own name in the question, and has nearly every word the
  question names; what it does on one press, and its key (`followup._once`). A question about what the picture
  shows is asked exactly as before. Measured on 2026-11-18 with Qwen3.5 9B (`tests/live_followup.py`): the
  title, the status bar and the NVDA menu went from a made-up key to the right one; a command that was not
  the answer was ignored once and repeated once (NVDA's review copy for "copy this text"). **Do not widen
  it without measuring**: lines of the user guide were tried and a line that was not about the question was
  repeated as the answer with its key; a passage of the developer guides made the model invent a key where
  before it had said, rightly, that the picture does not show this. So the developer guides do not go to the
  description window. The suggested small vision model was not on the computer and was not measured.
- **VisionClaw adapts to the user, and the keyboard is the first way, not the only one.** The owner said
  on 2026-11-18: "visionclaw must be able to adapt and learn, using its models for the best experience for
  the blind keyboard-only user. and sometimes for those times a blind user may need to use a game controller
  or a physical mouse." What adapts today, each kept as data the user can read and delete: what the user said
  about themselves and how they like things done (memories, and with them how much help an answer gives and
  which screen reader they come from); what worked in a program (`direct.AppWays`, helpers, fixes); what a
  program is, learned on request (notes); what failed in a form (`claw/memory.py`); skills the user makes. A
  model chooses or words; plain code checks and keeps. **When the user says they have a hand on a mouse,
  trackpad or controller, that is their choice: help with it** (the skills `hand-on-the-mouse` and
  `game-controller`), with NVDA's own mouse tracking, read from `tests/nvda_commands.json`, and directions in
  words. VisionClaw still never makes an answer depend on the mouse when the user did not bring it up.
- **A skill can take the place of another.** `instead of:` in a SKILL.md names skills, by folder name, that
  are not used when this one fits (`skills.Skills.choose`): two skills that say opposite things for the same
  words must not both reach a model. `hand-on-the-mouse` takes the place of `mouse-from-keyboard`.
- **Every build carries the guides and the training material that may be passed on.** The owner said on
  2026-11-18: "since everything is in markdown, all guides and all training material, just include it with
  every build of the addon. put this as a rule in claude.md ... then every visionclaw user gets it, even if
  the guides get a little out of date they are still useful for the end-user." So what is kept as Markdown and
  may be passed on is part of the add-on, in `addon/globalPlugins/visionClaw/claw/shipped`, and every user has
  it without a download; a copy the user downloads later is newer and is used in its place.
  - **A text put into the add-on is published to every user, so only what its owner allows to be passed on
    goes in.** `guides.MAY_SHIP` names each shipped source and by what right. Checked on 2026-11-18 by reading
    each source: the **NVDA Developer Guide** is under the GNU General Public License, version 2 or later,
    like VisionClaw, and is shipped. The **NVDA Add-on Development Guide** and the **NVDA wiki** state no
    licence (the guide's own page asks to respect its authors' copyright); **AFB** keeps its copyright;
    **Hadley** says "All rights reserved". These four are **not** shipped: each is downloaded when the user
    asks, as before. NVDA's own user guide and list of what is new come with NVDA itself.
  - **A source is added the day its owner says yes**, in writing: put its id and the words "by permission of
    ..., on ..." into `MAY_SHIP` (for the training material, give `claw/training.py` a `MAY_SHIP` and a
    `shipped` folder read the same way as `guides.shipped`), keep who said yes, when and in which words in
    `docs/STATUS.md`, and say in the file's first line whose it is. Never ship a text on a guess about its
    licence, and never because it is free to read: free to read is not free to pass on.
  - **Before every build** run `python tools/update_shipped_guides.py`, which fetches what `MAY_SHIP` names
    from the addresses fixed in `guides.SOURCES`, turns it into Markdown with the add-on's own code, writes
    whose it is and its licence in its first line, and takes out of the folder anything that may not be
    shipped. `build.py` refuses to build when the folder holds anything else than what `MAY_SHIP` names, and
    `tests/test_guides.py` fails then too.
  - **A little out of date is fine, and said.** The user is told that a guide came with VisionClaw and as it
    was on which day (`guides.storedText`), and can always ask for the latest.
- **The user is told what can be downloaded for them.** The owner said on 2026-11-18, of what does not come
  with the add-on: "visionclaw must provide a way for the user to know that these are downloadable on
  request. otherwise the user may never know what help and guides visionclaw can get for the user". Three
  ways, all plain code (`claw/offers.py`): the overview, asked for in words ("what can you download for me",
  the tool `downloads_info`) or with the button "What VisionClaw can download for you" in the settings, which
  names everything that can be downloaded, whether it is here already, and the words that get it; one
  sentence after an answer where it fits (the guide for add-ons after a request about writing one, the lessons
  after a request to learn or one that names another screen reader, the overview after any other question);
  and the answers that already say so (`guides.storedText`, `training.storedText`, `lookup.nothingText`,
  `addons.coachMissing`). **Each sentence is said once and then never again** (`offered.json` in VisionClaw's
  data), begins with "This is said once", is not said after a request that failed or that was itself about
  downloading, and offers only what is not here. Nothing is ever downloaded because of it: the user asks, and
  is asked first. Whatever VisionClaw learns to download later gets a line in `offers.overview`, and a
  sentence of its own only if the user could not find out otherwise; `tests/test_training.py` checks that
  every sentence the user is told to say is sent to the recipe it names.
- **The help files explain every feature, and what is new in the latest version and how to use it.** The owner
  said on 2026-11-18: "all help files should always reflect all visionclaw features, explain them, including
  what is new in the very latest addon and how to use the new features." The help files are the page NVDA opens
  for the add-on (`addon/doc/en/readme.html`, which `look_up` also reads as an add-on's help) and the README.
  What follows from it:
  - **What is new is written by plain code from the changelog**: `python tools/write_help.py` puts the newest
    two "New in" parts of `manifest.ini`, point by point, between the `news` markers of both files, with the
    version the help is for. Never write that part by hand; `build.py` refuses to build while it is out of date.
    So the changelog's points must themselves say how to use what is new: the words to say or the keys to press.
  - **Every feature is explained in its own part**, in the same change that adds or changes it: what it does,
    the words that ask for it, its keys, what it asks first, and what it cannot do. Both files, every time.
  - **`tests/test_help.py` fails** when a key of VisionClaw, of pointer mode, of a held dial or of the overlay,
    a label of the settings panel, or a kind of request (`planner.RECIPES`) is missing from either file. A new
    recipe needs a line in its `HELP` with words a user would say, and those words written into both files.
  - The help is for blind users like everything else: keys as NVDA names them, places in words, nothing that
    needs sight, and only keys that every keyboard has for VisionClaw's own modes.
  - VisionClaw's own notes (`claw/knowledge/visionclaw-*.md`) and skills change with the help when a feature
    they describe changes.
- **VisionClaw must do more than JAWS's AI tools, and what JAWS does is read, not remembered.** The owner
  said on 2026-11-18: "My goal is for visionclaw to be even more powerful and far more useful than Freedom
  Scientific Jaws fsCompanion could ever be", then "more powerful than fscompanion and other jaws AI tools in
  jaws2027. It must outdo jaws in capabilities", and "jaws2027 is on my local pc, feel free to examine its
  help and docs". JAWS 2027 is installed on the owner's computer; its help is
  `C:\ProgramData\Freedom Scientific\JAWS\2027\Locale\enu\Help\JFW.chm` (unpack a copy with
  `hh.exe -decompile`; the pages are `whats_new/Whats_New.htm`, `using_jaws/Getting_Help/Vispero_Companion.htm`,
  `customizing_jaws_for_windows/Picture_Smart/Picture_Smart.htm`, `using_jaws/Voice_Assistant.htm`,
  `using_jaws/Face_in_View.htm`). What it can do, what VisionClaw does against each point, and what is still
  missing is in `docs/STATUS.md` under "Compared with JAWS 2027"; when a newer JAWS is installed, read its
  help again and bring that list up to date, do not write it from memory. JAWS's help is Freedom Scientific's:
  it is read to learn what JAWS does, and nothing of it is copied into VisionClaw, its notes or its answers.
  Never say VisionClaw does more than JAWS in something that has not been run in NVDA: say what was tested.
- **A web page as a whole, and what stops a form, are said by plain code from what NVDA keeps of the page.**
  `explore_page` and `form_trouble` (`claw/pageview.py`, `pagetools.py`) ask no model and send nothing
  anywhere. Exploring names the landmarks in order, where the main part begins, what the page has, and only
  those of NVDA's keys that fit this page; the keys were read from NVDA's user guide, and
  `tests/test_pageview.py` asks the user guide of the installed NVDA for each of them. Form trouble says only
  what the page itself tells NVDA: fields marked as not valid, fields that must be filled in and are empty,
  and messages the page's own code marks as an alert or an error, each with the field it stands next to; then
  NVDA's reading position is put on the first of them, and that is said. Where the page tells NVDA nothing,
  the text in its picture is read for lines that say what is wrong, and after that the user is pointed to
  the model that sees pictures; plain code never guesses a reason. Both answers shorten themselves to fit
  `tools.RESULT_CHARS`, the lists first, so that the keys are never the part that is cut.
- **Measure with the real model.** After any change to a prompt, a recipe or a form, run
  `python tests/live_orchestrator.py` and read every answer. A change that passes the scripted tests can still
  make a small model worse.
- **Patch files with a script file, not a shell heredoc.** In this environment Bash heredocs that contain
  triple-quoted Python with apostrophes fail to parse, and a heredoc turns two backslashes into one, so that
  a regular expression's `\b` arrives as a backspace character. Write the patch script with the Write tool
  and run it.
- **The data folder is inside the add-on, and the whole of it can be carried away.** The owner said on
  2026-11-18: "everything in the data folder, **no exceptions.** must be moved, copied, made portable. and on
  subsequent installs of the addon onto local machines, non-portable, the data folder must go inside the addon
  folder itself", and: "the data folder may not be a fixed size depending on what the user has downloaded and
  stored in that folder". What follows from it (`claw/portable.py`, `portableui.py`, `installTasks.py`):
  - **Where.** Everything VisionClaw keeps is in `data` inside the add-on's folder (`DATA_DIR`). Never keep
    anything in NVDA's configuration folder again. The first start of 1.4.0 or later moves in what an older
    VisionClaw kept in `nvda\visionClaw` (`portable.moveIn`); on one drive that is a rename, however big.
  - **Never lost.** NVDA deletes an add-on's folder at the next start after an update or a removal, after
    calling the old copy's `onUninstall` (read from NVDA's `addonHandler` on 2026-11-18; read it again before
    changing this). `onUninstall` moves `data` into `visionClaw.pendingInstall` for an update, or back to
    `nvda\visionClaw` for a removal, where a later install takes it in (`portable.carryOver`). Where both
    have a file, this computer's own wins. Nothing is ever deleted. `installTasks.py` loads `portable.py` by
    its path, so `portable.py` must import nothing of NVDA and nothing of the package.
  - **No exceptions, any size.** A portable copy is the whole add-on folder and every file of `data`, whatever
    is there when the copy is made (`portable.files`): models of any size, guides, training material, notes,
    memories, skills, the library, logs, unfinished downloads. Never add a list of what to leave out, and never
    assume a size: measure the folder each time. Only `__pycache__` outside `data` is left out.
  - **Two ways, the user chooses.** One `.nvda-addon` file that NVDA installs on any computer, asking first
    (`portable.writeBundle`; models stored as they are, zip64 for big files), or a copy straight into a
    portable NVDA's `userConfig\addons\visionClaw` (`portable.copyTo`, which skips what is there already). An
    installed NVDA and the running one are refused. The settings go along as `data\carried-settings.json` and
    are taken over once, only by a VisionClaw with no models chosen (`portable.takeSettings`). A button opens
    NVDA's own window for a portable NVDA, which now carries VisionClaw with everything too.
  - **Said before, not after.** Room on the drive and FAT32's limit of 4 GB for one file are checked before the
    copy starts (`portable.check`); the copy shows a progress bar, can be stopped, and leaves no half file. A
    build never carries anyone's data (`build.py` leaves out `addon/data`).
- **VisionClaw works the computer itself, in many small steps, and says what is going on.** The owner said on
  2026-11-18, after "first, look at my screen. If you see recycle bin, open it" ended in a description and
  "check and see if my recycle bin needs to be emptied" in a look-up: "claude must expand visionclaw
  capabilities to do many more things by controlling my computer on my behalf", "multistep things", and
  "visionclaw must be able to execute multistep agentic tasks whether in regards to accessibility, NVDA,
  writing addons, or general agentic computer use while still letting the blind user know what is going on."
  What follows from it (`claw/computer.py`, `computertools.py`, `claw/controls.py`, `controltools.py`):
  - **A model never writes what is opened or changed.** Which program, folder, settings page, window, file,
    volume or control is meant is read from the user's own words by plain code; a model at most chooses among
    the ids or names of what was found. What may be opened is fixed in `computer.PLACES` or found on this
    computer (Start menu, desktop, Windows' Apps folder, the user's own folders); a text that was fetched or
    generated never names something to open.
  - **What cannot be undone is always asked about** (`mustAgree`, whatever the settings say): emptying the
    Recycle Bin, locking, sleeping, restarting, shutting down, signing out. A restart or shutdown waits
    `computer.POWER_WAIT` seconds and can be called off. Everything else that changes something uses `confirm`.
  - **The computer's volume is speech.** Turning it down stops at `computer.QUIET`; muting or a number below it
    is refused when no braille display is in use and always asked about when one is. Never add a way around
    this. NVDA's own volume stays a setting of NVDA: a bare "volume" means that, as before.
  - **Say what happened.** A window asked to close that is still open is said to be open; after a volume
    change the level is read back; the Recycle Bin is counted again after emptying.
  - **Windows' own structures** were read on 2026-11-18 from Microsoft's pages and from the header files of the
    Windows SDK on the owner's computer, named at the top of `computertools.py`; the pages of Windows Settings
    are from Microsoft's page "Launch Windows Settings". Read them again before changing one; do not write a
    structure, a function's place in an interface, or a settings address from memory.
  - **Tests never open, empty, close, change the volume of, lock or shut down the real computer.**
    `tests/test_nvda_stub.py` replaces `computertools.shellOpen`, `emptyBin`, `setVolume`, `setMute`,
    `focusWindow`, `closeWindow`, `showWindow`, `minimizeAll`, `pressEscape`, `power` and `recycle`, and makes up what
    would be read. Reading alone (the Recycle Bin's count, the volume, drives, windows, programs) may be run on
    the real computer. Never run the changing ones for the owner without asking.
  - **A long request is split by plain rules where they can tell for certain** (`planner.plainSplit`): an end
    of a sentence, "then", a comma or "and" before a word that begins a thing to do (`computer.ACTS`). Up to
    `planner.MAX_PARTS` things. Where a part needs the part before it to be understood and plain code cannot
    say which thing "it" is, or the first part is no thing to do, the request is left to the model as before.
    "Adjust the volume and turn it up" is one thing; a button that is found before more is done is found to
    be clicked (`_FIND_IT`), and the parts shown to the user say so. Add a case to `tests/test_computer.py`
    for every request of the owner's that was split wrongly.
  - **A request that depends on something is checked by plain code first** (`computer.condition`,
    `planner.conditional`): whether something is on the screen (`check_seen`: NVDA's names where the user is,
    then the text that is shown, then the model that sees, whose lone yes is said to be a model's), whether a
    window is open, and what the Recycle Bin holds. The check is a step of its own; the steps that depend on
    it carry it as `onlyIf`, are left out as `NOT_NEEDED` when it does not hold, and the answer says "So this
    was not done". Not done because of a condition is no failure. Only these three kinds are understood; any
    other "if" is planned as before. Do not hand a condition to a model to judge in prose.
  - **A named control of the program in front** (`set_control`): looked for by its name in what NVDA knows of
    the window, then on the other pages of a dialog with tabs (and the page that was shown is shown again
    when it is on none), then in the window's picture. The least risky way that works: the control's own
    action, the keyboard, the mouse last. The answer says what it was and what it is now; a reading from a
    picture is said to be one. It is meant where the words say "this program" or right after a click or
    another control there (`planner._INSIDE`); alone, "turn off the typing echo" is NVDA's own setting.
  - **The notes and skills** that go with this: `claw/knowledge/visionclaw-computer.md`, asked only when a
    question names one of these things (`lookup._COMPUTER`), and the skills `work-the-computer` and
    `control-in-a-program`. When a tool's behaviour changes, change the notes, the README and the help with it.
  - **The user's own files** (`computer.fileTask`, the tool `change_file`): a folder or a text file made, a file
    or folder renamed, moved or copied, or moved to the Recycle Bin. Only inside the user's own folders
    (`computertools.insideOwn`), found there by its name by the search, never by a path a model wrote; where
    several fit, the user chooses in a question of the tool's own. **Nothing is ever overwritten**, and
    **nothing is ever deleted for good**: deleting is `computertools.recycle`, always asked about (`mustAgree`),
    and where Windows cannot use the Recycle Bin it is Windows that asks, never VisionClaw that decides. A
    rename, a move and a thing that was made are written to the list of changes (`file:` entries) and put
    back by `undo_change` (`computertools.undoFile`). The words must speak of a file, a folder or a document,
    or write a name with its ending: "delete the notes on this program" is not about a file. Tests change
    files only in folders of their own, and `recycle` is always stood in for.
  - **Still to do, and said so to the user**: choosing from a
    combo box by the option's name; a dialog whose pages are a list or a tree and not tabs; a volume for one
    program; Wi-Fi and Bluetooth turned on and off without the Settings page.
- **An NVDA setting for one program only is NVDA's own configuration profile, and is changed only while that
  program is in front.** Built on 2026-11-18 against what JAWS's Companion does ("only for the application in
  use"); `claw/profiles.py`, `profiletools.py`. What follows from it:
  - **Plain code reads "only in this program" from the user's own words** (`profiles.scopeOf`); a model never
    decides it. The recipe stays `change_setting`: the scope is no recipe of its own, and no control of the
    program (`planner._FOR_ONE_PROGRAM`). The words that say for which program are left out when the setting is
    looked up and compared with the request (`profiles.without`): "Word" is in the name of another setting.
  - **Those words are never split off.** Measured with Qwen3.5 9B on 2026-11-18: "Make NVDA speak a little
    faster, only in this program." was split at its comma, the second half was taken for a request to describe
    the screen, and the setting was changed in every program. `planner.split` puts the words aside before it
    splits and gives them back to every part that changes a setting.
  - **What NVDA does was read from its source** (branch release-2026.3, on 2026-11-18: `config/__init__.py`,
    `appModuleHandler.py`, `gui/configProfiles.py`; what was read is at the top of `profiletools.py`). Read it
    again before changing anything there; do not write from memory. VisionClaw does what NVDA's own New Profile
    window does (`createProfile`, `triggersToProfiles["app:" + name]`, `saveProfileTriggers`), and then enters the
    program's trigger the way `appModuleHandler.handleAppSwitch` does, because a profile that was only just
    made does not apply until its program gets the focus again.
  - **Nothing is written unless the program's profile is the one NVDA writes to at that moment**
    (`profiletools.write`, checked in the same call on NVDA's main thread). A program that is named and is not
    in front, a setting of `BASE_ONLY_SECTIONS`, a profile turned on by hand, triggers switched off, an NVDA
    that keeps nothing: each ends with nothing changed and a sentence that says why (`profiles.py`). A profile
    that was made and could not be turned on is taken away again.
  - **A new profile is always asked about** (`mustAgree`): it changes how NVDA behaves in a program from then
    on. Deleting one too (`remove_program_settings`), because NVDA cannot bring it back.
  - **Undo only in that program.** A change is recorded with its profile (`ChangeLog.add(profile=, program=)`);
    `undo_change` puts it back only while that profile is on top, and otherwise says where to say it. It writes
    the old value into the profile, as NVDA's own settings window would; it does not take the key out.
  - Where the words narrow a request down and no program can be read from them (`profiles.NARROWS`), the
    question says "This will apply in every program", whatever the settings say.
  - **Everywhere or only here is never left to chance.** The owner said on 2026-11-18: "It also must understand
    the difference between changing a setting everywhere and changing it only for the application you're using".
    NVDA writes a change to the profile that is on, so once a program has a profile, a change said there without
    a place would land in that program alone. So: "everywhere", "in every application" (`profiles.everywhere`)
    writes NVDA's normal configuration, also while the program's profile is on (`profiletools.writeBase`: its
    trigger is left, the write is made only if the normal configuration is then the one NVDA writes to, and the
    trigger is entered again in a `finally`); a relative value ("+10") is read against the value everywhere; a
    program named with "in" alone counts where it is a known program written as a name or the program in front
    (`profiles._plainIn`, JAWS's own example "Stop announcing capital letters in Word"); and where the program in
    front has a profile and the words say neither, **the user is asked** (`profiles.whichQuestion`), whatever the
    settings say. After a change the programs that keep a value of their own for it are named
    (`profiletools.holders`). Undo puts each change back where it was made.
  - `tests/profilestandin.py` stands in for NVDA's configuration and was written from the same source. When
    NVDA's profiles change, change it with `profiletools.py`. **None of this has run inside NVDA**: whether the
    entered trigger makes the profile apply at once is the first thing to try there.
- **A request that follows the one before it is written out in full, by plain code where it can, and the user is
  told how it was understood** (`claw/followups.py`, `orchestrator._follow`). Built on 2026-11-18.
  - **Plain code first**: the same again, a bit more, the other way or "too fast" (`opposite`, `toward`), the
    last answer said again, the same in another program, "the second one" from the numbered list in the last
    answer (`listed`, `nth`), and "and maximize it" by the planner's own rules for "it" (`_joined`).
  - **A model only for the rest, with the smallest question that fits** (`followups.ask`): the same about a new
    thing (`ABOUT_SYSTEM`), or a thing the answer names (`THING_SYSTEM`). Plain code checks every word of what it
    wrote against what the user and VisionClaw said (`checked`), and refuses a copy of a follow-up that leans on
    the request before in clear words (`mustChange`). Measured with Qwen3.5 9B on 2026-11-18: given one question
    for every kind and leave to copy the request unchanged, it copied 8 of 11; with these it wrote all of them
    out. **Never give it "copy it unchanged" for a follow-up that cannot stand alone.** Measure with
    `python tests/live_followups.py`, and read every line.
  - **The very smallest models are never asked** (`suggest` is False); the request then stays as it was said
    and the one before is given as what is known (`followups.background`).
  - **Always said**: the answer begins "Understood as: ...". Everything that changes something still asks.
  - **"It" may mean what has the focus**: "open it" leans on the request before for `SOON_SECONDS` only, and
    the model may leave it as it is. "Read it" and "say this" never mean "say the last answer again": that
    needs "again". "The first button" leans on nothing; only "the first one" does.
  - **Kept only while NVDA runs** (`orchestrator.last`); nothing of it is written to the disk.
  - Add a case to `tests/test_followups.py` for every follow-up of the owner's that was understood wrongly.
- **A date in a calendar is read from the user's words, and every press is checked against what the calendar
  then shows** (`claw/dates.py`, `datetools.py`). Built on 2026-11-18 against JAWS's example of a date picker.
  - **The date is plain code's**: typed or spoken ("the fourteenth of March twenty twenty-seven"). Two readings
    (3/4/2027, "next Friday") are put to the user; a date without a year is the next one; a model writes nothing.
  - **Three places, the surest first** (`datetools.Reader`): the web page from NVDA's browse mode, the window as
    NVDA knows it, the window's picture. One calendar logic for all three (`dates.View`, `fromControls`,
    `fromWords`, `choose`).
  - **Nothing is counted blind.** After every press the calendar is read again; a month that did not change
    twice, or a named button that went the wrong way, ends it with a sentence. Which unnamed arrow goes forward
    is found by trying one press, and said. A greyed-out day is not pressed. At most `dates.MAX_MONTHS`.
  - **The days of the month shown begin at the first 1**: the 29, 30, 31 before it are the month before.
  - **Say what happened**: the date with its weekday, how many months it went, and whether the calendar marks
    the day or is gone; for a picture, that the date field must be checked.
  - `tests/calendarstandin.py` has calendars that answer to presses. Not run in a real browser or program.
- **Asking by voice never does anything by itself, and nothing that is said leaves the computer**
  (`claw/voice.py`, `voiceinput.py`, `voiceui.py`). Built on 2026-11-18; phase 6.2.
  - **What was heard is put into the request box and read out; only Enter sends it.** Never send a spoken
    request directly: a mis-heard word must be correctable before anything is done.
  - **Nothing is spoken while the microphone is open**: NVDA would be recorded. A high beep says listening has
    begun, a lower one that the words are being worked out. Keep it that way for anything added.
  - **Recorded into memory, never to a file, never sent.** Only how long the sound was and how many words were
    heard go to the log; the words themselves only when the log is detailed.
  - **The speech model runs in an engine of its own, on the processor, started for one recording and stopped
    again** (`voiceinput.Ears`): it is ready in about a second and leaves the graphics card to the other models.
  - **It is told the names it would otherwise mishear** (`voice.context`): it wrote "NVDA" as "Nvidia" until
    told the name. Add a name there when the real model shows a new one; measure with `tests/live_voice.py`.
  - **When the person has finished is plain code's** (`voice.Listener`): louder than the room for long enough
    is speech, a pause after speech ends it. The room is learned only from what is not speech, so that a long
    sentence does not raise the bar.
  - **Windows' structures for the microphone** were read from Microsoft's pages and the SDK's headers on
    2026-11-18, named at the top of `voiceinput.py`. No callback is used. What is opened is closed in a finally.
  - **Tests never open the microphone.** `tests/live_voice.py --mic` does, shows loudness only, and is never
    run for the owner without asking; never add it to `run_all.py`.
  - The speech models are kept in `speech` of VisionClaw's data, apart from the vision and coder models, so that
    nothing about those changes; the user chooses between them in the settings (`speechModel`).
- **Working through a task is one step at a time, asked about, in one program, and never in VisionClaw's own
  windows** (`claw/guide.py`, `guidetools.py`). The owner said on 2026-11-18: "visionclaw must help the user work
  through a task when the usual path isn't clear. just like how fsCompanion does in jaws2027", and gave JAWS's own
  rules for it, read from JAWS 2027's What's New page the same day: it only works when asked, approves important
  steps, checks in on longer tasks, stays in one application, and its own window is off limits.
  - **Plain code finds, a model at most chooses.** What the user wants is their own words without the words that
    say they are stuck (`guide.goalOf`); the things of the window are ranked by those words and by the words menus
    use for the same thing (`guide.rank`, `_ALIKE`); where one is clearly about it and well ahead, it is taken
    (`guide.sure`); else a model chooses among at most `guide.MAX_OFFERED` by number, with "none of these", and a
    very small model is not asked (`guidetools` `choose`).
  - **Every step is asked about** (`plugin.clawAsk`, whatever the settings say), with "only tell me where it is"
    and "stop" as choices; a thing whose press may not be possible to take back says so (`guide.isFinal`).
  - **A check-in after `guide.CHECK_AFTER` steps, at most `guide.MAX_STEPS`.** After every press the window is
    looked at again and the user is told what it brought up (`guide.changed`); two presses that bring up nothing
    end it.
  - **It stays in one program**: when a step brings another program to the front, it stops and says so. Never make
    it follow into another program.
  - **VisionClaw's own windows are off limits to every tool that works the window in front** (`guide.OFF_LIMITS`,
    `nvdatools` `notOwn`, `guidetools.ownWindow`: a window of NVDA whose title names VisionClaw). A new tool that
    clicks, types or presses keys in the window in front gets a line in `OFF_LIMITS`.
  - **A request that says the user is stuck is never split, and no model is asked what to do with it**
    (`planner.split`, `_SURE`). Measured with Qwen3.5 9B on 2026-11-18: "I'm stuck, I want to attach a file to this
    email." was split at its comma, "I'm stuck" was answered as a question, the rest was planned freely, and a
    button was clicked that nobody had asked for.
  - Tested on a program made up by the test; not run in a real program.
- **VisionClaw's own voice is the user's to set in NVDA's own Speech settings.** The owner said on 2026-11-18:
  "instead of changing the voice pitch while visionclaw is speaking, drop me into nvda speech settings so I can
  fully customise visionclaw's voice." (`ownvoice.py`.) It is one NVDA configuration profile, tied to a trigger of
  VisionClaw's own (`ownvoice.SPEC`), and every sentence VisionClaw speaks carries
  `ConfigProfileTriggerCommand(trigger, True)`, as NVDA does for say all: NVDA's speech manager applies the profile
  to those words alone and leaves it by itself. To set it, the profile is turned on by hand and NVDA's Speech
  settings are opened; a timer turns it off again when that window is closed (`ownvoice._watch`). What was read
  from NVDA's source is at the top of `ownvoice.py`; read it again before changing it. **Never change the user's
  own voice, rate or pitch for this, and never put the pitch trick back.** Always asked before the profile is
  made; not begun while NVDA's settings window is open or another profile is on by hand. `_speak` in `__init__.py`
  is the one place VisionClaw's speech goes through. Not run in NVDA.
- **The JAWS Migration Assistant and ClassicSpeech are used when they are running, and only then**
  (`claw/partners.py`, `partnertools.py`). The owner said on 2026-11-18: "if the jaws migrator addon and
  classicSpeech addon are installed, visionclaw will be even more powerful! let it take advantage of both".
  - **Neither has an interface for other add-ons.** The names VisionClaw uses were read from their source
    (jawsMigrator 1.63, ClassicSpeech 1.16) and are listed at the top of `partnertools.py`. When either changes,
    read its source again (`github.com/joshknnd1982/jawsMigrator`, `.../classicspeech-nvda`); do not guess a name.
    Every reach into them is wrapped: a name that is gone ends in a sentence, and nothing is changed.
  - **The JAWS Migration Assistant is only read**, never written: its key data, its key map of the JAWS on the
    computer, its state. **ClassicSpeech is changed only with the calls its own commands and windows make**
    (`processor.set_profile`, `SchemeStore().set_active_scheme().apply()`, `set_schemes_enabled`), after a
    question, recorded in the list of changes (`classicspeech:` entries) and put back by `undo_change`. Its
    windows are opened with its own scripts through `wx.CallAfter`, as its AGENTS.md asks.
  - **Not offered without the add-on.** `partnertools.refresh` tells `claw/partners.py` before each request which
    are running; the hints and the router's needs ask `partners.has`. Nothing of either add-on is copied in.
  - Neither was installed where this was written: both tools were tested only against stand-ins that have the
    names and shapes their source has (`tests/test_partners.py`). Say so until they were run for real.
- **The router: a model is offered only what fits** (`claw/router.py`). The owner asked on 2026-11-18 for "a
  lightweight routing layer in Python that exposes only the tools relevant to the current app or window
  context (for example, showing browser tools only when a browser is focused)", and for it to be used wherever
  else it helps. A small model chooses well among a dozen things and badly among eighty.
  - **What is offered**: the everyday core always; what works a web page when a web page or a browser is in
    front (`router.WEB`), when the part before opened one, or when the words speak of a page; what needs a
    game controller when one is connected or named; what reads everything from the user's words only when the
    words say it (`planner.needsFor`); what is about one subject (skills, notes, downloads, the log) when the
    words name it (`router.GATES`). The facts come from the add-on (`plugin._clawFacts`).
  - **It narrows, it never forbids.** Every recipe a pattern of the planner finds in the words is offered
    (`planner.hinted`). A fact that could not be found out hides nothing. When a model finds nothing that fits
    among what it was offered, it is offered everything, once (`planner.classify`). The user's own choice is
    never narrowed: this is about what a model is shown, not about what the user may ask for.
  - **Where the words can hardly mean anything else, no model is asked** (`planner.decided`, `_SURE`): the
    Recycle Bin, locking and shutting down, the computer's own volume, a place of Windows opened by its name,
    a question right after a web page was opened, a named control right after a click. Each was either sure by
    its words or measured: the real 9B model chose wrongly twice in a row for the last two.
  - **A plan a model writes itself** gets only the tools of what was offered (`router.tools`).
  - **A new recipe** is offered always unless it gets a line in `router.GATES` or `planner._NEEDS`; give it one
    when it can only be meant in a place or by words of its own, and add the request to `tests/test_computer.py`,
    where every request listed must be offered the recipe its words point to. Measure with the whole of
    `tests/live_orchestrator.py` after changing a gate.
- **Never commit** model files (`*.gguf`, `*.bin`), `dist/`, tokens, or the `SmallClaw/` reference clone.

## Layout

```
addon/
  manifest.ini
  installTasks.py
  engine/                    llama.cpp server (vcengine.exe + DLLs); binaries are not in git, see BUILD.md
  globalPlugins/visionClaw/
    __init__.py              the global plugin: VisionMate's describe/overlay features + VisionClaw commands
    engine.py                one llama-server process: start, health, streaming chat, cancel
    hardware.py              memory and graphics adapters
    settings.py              settings panel
    dialogs.py               models window, description window
    clawui.py                Ask VisionClaw window, choice prompts, progress speech
    nvdatools.py             the tools the models can call, written against the NVDA API
    webtools.py              the web through NVDA's browse mode: a page's links, buttons, fields and text
    pagetools.py             a web page as a whole with the NVDA keys that fit it, and what stops a form: the
                             page read a stretch at a time, the reading position put on the first field in trouble
    mousetools.py            the mouse from the keyboard: click, right-click, double-click, drag, the wheel,
                             the screen's scaling, pointer mode; holding the button, resting the pointer and
                             what appeared, gestures, a click when something changes or in a rhythm, keys held
                             down during a click or a turn of the wheel; the mouse's own movement for a game
                             that reads the mouse directly, Windows' facts about its pointer, and how the
                             mouse is moved while a tool works in such a game
    touchinput.py            fingers and a pen through Windows itself: a gesture as the places every finger
                             passes through, a pen stroke with a pressure at each place, a pen held down
    touchtools.py            the tools for fingers and pressure: touch, compare, the wheel instead, what worked
    computertools.py         the computer itself, through Windows: things opened by name, the Recycle Bin, the
                             computer's volume, open windows, the user's files, facts about the computer,
                             locking and shutting down, and whether something is on the screen
    controltools.py          a named control of the program in front: found in the window, on the other pages
                             of its dialog or in its picture, and turned on, off, up or down
    padtools.py              a game controller: noticing it, reading it, controller mode, its buzz, the tools
    accesstools.py           deep inspection, lasting fixes for a website or program, installed add-ons, which
                             add-on does what the user wants, NVDA Coach;
                             both models judging how a control is worked
    deepquery.py             a deep query of one control: NVDA, UI Automation, the window, the off-screen model
    controlkeys.py           arrow keys for a control that is dragged: taking hold, trying how it is worked,
                             telling what changed, keeping it under a hotkey
    fixruntime.py            the working part of every fixes add-on; copied into the add-on as text
    updater.py               a newer version of VisionClaw: looking, the window that says what is new,
                             downloading, handing it to NVDA
    asktools.py              a question: what NVDA, the program in front, its window and Windows each say,
                             the notes on the program, and what "this" means, by the user's words or a model
    memorytools.py           remembering, listing and forgetting what the user asked VisionClaw to remember;
                             the user's library of documents
    memoriesui.py            the memories window: forget the checked ones, or all of them and start over
    skilltools.py            skills in words: making one from the user's own words, listing, reading, turning
                             off or on, deleting
    skillsui.py              the skills window (NVDA+Alt+I): every skill, what the chosen one says, new, change,
                             turn off, delete, import a file, open the skills folder
    learntools.py            learning about the program in front from the internet after a question, adding a
                             page from the user's browser to the notes, listing, opening and deleting notes
    nvdainfo.py              what NVDA has and uses: synthesizer, voices, braille display, drivers, add-ons;
                             how NVDA drives the synthesizer and the display in use, for the audit
    vclog.py                 one "log" for the NVDA-side files: NVDA's log and VisionClaw's own
    followup.py              questions in the description window: all are answered; a question about a key is
                             given the one NVDA command it is about
    helpers.py               app helpers and generated add-ons: loading them live, their hotkeys
    profiletools.py          an NVDA setting for the program in front only: NVDA's configuration profile for it
                             made, turned on, written to only while it is the one NVDA writes to, listed, deleted
    guidetools.py            working through a task: what the program in front offers, read from the web page, the
                             window or its picture; a thing pressed after a yes; VisionClaw's own windows told
    ownvoice.py              VisionClaw's own voice: one NVDA configuration profile applied to its words alone,
                             set by the user in NVDA's own Speech settings
    partnertools.py          the JAWS Migration Assistant and ClassicSpeech, where they are running: a JAWS
                             keystroke or command in NVDA; ClassicSpeech's level and schemes changed by asking
    datetools.py             a date chosen in a calendar: found in the web page, the window or its picture,
                             its buttons pressed, read again after every press
    voiceinput.py            asking by voice: the microphone through Windows' waveform functions, and the
                             speech model in an engine of its own on the processor
    voiceui.py               asking by voice as the user meets it: the speech model offered and downloaded
                             after a question, listening started and stopped, the beeps, the tools
    portableui.py            the window that makes a portable copy: one .nvda-addon file with everything, or
                             VisionClaw with everything straight into a portable NVDA; progress, stopping
    (the rest)               VisionMate features: overlay, OCR, chat photos, labels ...
    claw/                    SmallClaw-style core. NO NVDA imports.
      catalog.py             model catalog, the fetched list of newer models and its checks, what is
                             installed, downloads
      backend.py             dedicated GPU -> Vulkan -> CPU choice and fallback
      runtime.py             both engines; loads, swaps, resizes context
      policy.py              picks context size, token limits, temperature, reasoning per task
      llm.py                 JSON-constrained calls, reasoning levels, prompt trimming
      match.py               forgiving matching of what a model writes against what exists
      ranking.py             which of many things a request is about: rare words tell, names tell more
      commands.py            NVDA's commands as data: finding one, and how often its key is pressed
      lookup.py              a question answered from NVDA, the program, the window and Windows: passages,
                             which of them are about the question, a help page as text, what to say when none is
      memories.py            the user's memories as Markdown files with an index; what to keep, recall, forget
      library.py             the user's documents read as sections and passages for lookup
      learn.py               what a program is called and what to ask about it; Wikipedia, Wikidata and the
                             program's own website read as text; the useful sections of a page; notes a model
                             writes and plain code checks; the notes as Markdown files and as passages
      inside.py              everything inside the running NVDA, listed from its loaded modules; the audit
      debuglog.py            VisionClaw's own log file: levels, rotation, errors with their place in the code
      web.py                 web addresses, search addresses, the passages of a page that matter
      pageview.py            a web page in words: landmarks, where the main part begins, what it has, NVDA's own
                             keys for it; the fields and messages that may be stopping a form
      drivers.py             rules that keep speech and braille alive; what happened with each driver
      computer.py            working the computer itself, as plain logic: what is to be opened and which found
                             thing is meant, what the Recycle Bin holds and whether it is worth emptying, the
                             computer's volume, which window, which files, facts in words, locking and
                             shutting down, and what a request depends on
      controls.py            what the user's words ask of a named control, and which control a name means
      profiles.py            "only in this program" read from the user's words, which program is meant, the name
                             of its profile, and every sentence the user is told about it
      followups.py           a request that follows the one before it: which kind, what plain code writes out,
                             the questions to a model for the rest, and the check of what it wrote
      guide.py               working through a task: what the user wants, which things of a window are about it,
                             what a step brought up, and the walk with its rules
      partners.py            what the user's words ask of the JAWS Migration Assistant and of ClassicSpeech, and
                             which of the two are running
      dates.py               a date from typed or spoken words; a calendar from the names of controls or from
                             the text in a picture; the steps to the right month and day
      voice.py               the speech models and their files; when a person has begun and finished speaking;
                             a recording as a WAVE file; what the model is told and what is made of its answer
      router.py              which kinds of request and which tools a model is offered: by where the user is,
                             by the part before, and by what the words name
      pointer.py             which mouse action is meant, where a drag ends, how pointer mode moves; how long
                             to hold, which keys are held, a place on a thing, gestures as strokes, when and
                             how often to click, where a picture changed
      scrolling.py           how far to scroll, steps that follow the screen, whether a scroll moved anything,
                             scrollbars found in a picture
      touch.py               which touch gesture the words mean, with how many fingers; where each finger
                             goes; how hard to press and along which line; what the wheel does instead
      direct.py              a game that reads the mouse directly: what a turn means in the mouse's own
                             steps, a program's own pointer brought to a place from the window's corner and
                             measured from pictures, what Windows' facts say, what is kept about a program
      gamepad.py             a game controller as one plain state, what changed since the last look, which
                             button does what, how far a stick moves the pointer, a button named in words
      changes.py             every setting VisionClaw changed, so that it can be listed and put back
      prompts.py             what every answer and description is told about the blind user, the user's own
                             instructions and wording
      fixmatch.py            controls as plain data and the rules that find them; copied into fixes add-ons
      audit.py               the inspection's findings for a page or window, and the fixes each can have
      fixes.py               fixes as data; the add-on put together from them; what it does, in sentences
      updates.py             which release is newer, and which one file may be downloaded for it
      planner.py             splits a request into parts; recipes; free plans and their repair
      consensus.py           the two models agree, or the user decides
      agent.py               the tool loop for one step
      tools.py               tool registry
      shapes.py              what a model may write in a field, from the results so far; an answer that only
                             repeats the question; answers quoted from what was looked up
      memory.py              lessons learned, kept between sessions
      skills.py              skills: SKILL.md read and written, checked, chosen by their words, their sentences
                             for a step, a skill's own steps as the plan; VisionClaw's own and the user's
      skills/                VisionClaw's own skills, one folder with a SKILL.md each
      knowledge.py           searchable NVDA add-on knowledge (claw/knowledge/*.md)
      guides.py              the downloaded developer guides: fixed addresses, web page to Markdown with its
                             code examples kept whole, sections as plain sentences, single facts for the writer
                             of an add-on, which guides are here and from when
      training.py            free material that teaches NVDA: the fixed sources the owner said yes to, a
                             lesson's web page without the site around it, each page with what must be named
                             for it to be asked, which material is here
      shipped/               what comes with every build as Markdown: the guides that may be passed on
      offers.py              what can be downloaded for the user: the overview, and one sentence said once
                             after an answer that it fits
      helpfiles.py           NVDA's own help and the add-ons' help kept as Markdown files, made again when the
                             page they were made from changes
      addons.py              the add-ons installed in NVDA as plain data: which of them does what the user
                             wants; NVDA Coach's lessons and progress read from its files, and how much help
                             the user's words ask for
      working.py             how a control is worked, from NVDA's facts, its own name or both models, for
                             every kind of control NVDA has; which remedy fits;
                             what a window's class says about the toolkit or game engine
      dragcontrol.py         the drags, wheel turns and values behind the arrow keys; whether a control changed
      microaddons.py         check, store, package generated add-ons
      portable.py            the data folder inside the add-on: moved in at start, carried over when NVDA
                             deletes the add-on's folder; a portable copy as one file or into a portable NVDA;
                             the settings that go with it. Loaded by installTasks.py by its path
      task.py                task state, progress events, cancel
      orchestrator.py        runs a whole request from start to finish
tests/                       plain-Python tests; tests/live_*.py need the engine and a model
docs/STATUS.md               what is done and what was tested, and how
docs/TESTPLAN.md             the checklist for testing inside NVDA
tools/                       build helpers
```

## How a request flows

1. **Split** (`planner.split`): the request is split into its separate parts, in the user's own words. A
   request that is clearly one thing is not sent to a model at all.
2. **Recipes** (`planner.RECIPES`): each part is matched to a recipe, a fixed list of steps with one tool each
   (`change_setting` is `find_setting` then `set_setting`). Only a part that fits no recipe is planned freely
   by the model, and that plan is repaired by rules (`planner.normalize`).
3. **Agreement** (`consensus.agree`): both models choose the recipe for each part, each on its own. Same choice:
   agreed. Different: each is told the other's choice and chooses again. Still different: the user picks.
   A freely written plan is reviewed in words by the other model, corrected once, then put to the user.
   Never go back to asking a small model to judge a recipe plan in prose: it objects at random.
   When one model is chosen for both jobs (`runtime.oneModel`, carried in `params.oneModel`) there is no
   agreement: the recipe is chosen once and checked against the user's own words (`planner.hint`); where
   the words point elsewhere the model is told so and chooses again, and if it still differs the user picks.
   Do not let the model's second answer stand alone: measured with the 9B model, it kept a wrong choice both
   times. A freely written plan is checked by the same model with the reviewer's question, and the user is
   asked when it stays unsure.
4. **Policy** (`policy.select`): token limits, retries, reviews and the reasoning level, from how demanding the
   recipes are. The user's reasoning setting (Automatic, Off, Low, Medium, High) overrides the automatic
   choice. The context size is chosen per model call from its length (`llm.py`).
5. **Run** (`agent.runStep`): one step at a time. Code fills in every form field it can from the user's own
   words (fields marked `auto`); the model fills in the rest; on an error it sees the error and tries again,
   then gets a hint from the other model, then the user is asked. Progress is reported at every state change.
6. **Answer** (`orchestrator._answer`): what tools did is said in the tools' own words, never rephrased by a
   model, so nothing is claimed that did not happen. Only looked-up information is put into words by a model.
   Failed parts are named. A freely written plan is also checked by the other model, with one repair round.
7. **Learn** (`memory`): what failed and what fixed it is saved and recalled for similar requests.

## Phases and sessions

A session is one sitting with Claude. Do the sessions in order. At the start of a session read this file and
`docs/STATUS.md`; at the end update the checkboxes here and write what was tested in `docs/STATUS.md`.
A session is done only when its "Done when" line is true.

### Phase 1 — Fork and foundation
- [x] **1.1 Fork.** Rename the package to `visionClaw`, keep upstream credit and licence, new manifest, new
  config section and data folder. *Done when:* every file compiles and no user-visible "VisionMate" is left
  except credits.
- [x] **1.2 Models.** `claw/catalog.py`: catalog with pinned URLs, sizes and SHA-256; resumable verified
  downloads; reuse VisionMate's vision data if it is already on the computer. Models window that asks before
  downloading. *Done when:* catalog URLs answer with the catalogued sizes and the download test passes.
- [x] **1.4 Side by side.** Two models that do not fit on one chip: the second goes to another chip or the
  processor and both stay loaded (`runtime._placeBeside`); they take turns only when there is no room anywhere.
- [x] **1.3 Graphics choice.** `claw/backend.py` + `runtime.py`: Automatic, Dedicated graphics card, Vulkan,
  Processor only; fallback dedicated -> Vulkan -> CPU when a start fails. *Done when:* the device list is parsed
  on a real machine and each backend starts the engine, or falls back.

### Phase 2 — Orchestration core
- [x] **2.1 Engine and runtime.** Two engines, context resizing, JSON-schema calls, reasoning control.
- [x] **2.2 Policy, planner, consensus.** *Done when:* tests cover agree, revise-then-agree, and disagree ->
  user choice.
- [x] **2.3 Agent loop, tools, task state, cancel.** *Done when:* a scripted fake model drives a multi-step
  task to the end, and cancelling stops it within one model call.
- [x] **2.4 Live test** against a real model through the bundled engine (`tests/live_orchestrator.py`).

### Phase 3 — NVDA integration
- [x] **3.1 NVDA tools.** Settings (find, set with validation), NVDA commands (find, run, tell the shortcut),
  focus and window information, look at the screen, OCR, list and click the items in a window, press keys,
  introspection of NVDA modules, knowledge search, ask the user.
- [x] **3.2 Ask VisionClaw window**, progress speech, stop command, reasoning choice, settings panel.
- [x] **3.3 Micro add-ons.** Generate, check, review, confirm, load live, repair on error, list, remove.
  Export as `.nvda-addon`: see 3.8.
- [x] **3.4 App helpers.** A saved, declarative helper for one app: hotkeys that click or read named items found
  in the window's picture. No generated code, so small models get it right more often.
- [x] **3.6 The web.** Open, search, ask about the page, follow links, press buttons, fill fields, through the
  user's browser and NVDA's browse mode. In a web page `list_items` and `click_item` use the page's own
  elements instead of the picture.
- [x] **3.7 Speech and braille.** `nvda_info` reports synthesizer, voices, braille display, tables, drivers and
  add-ons; every setting of the driver in use can be changed; `switch_driver` switches safely.
- [x] **3.8 Permanent fixes.** A generated add-on can be saved as an `.nvda-addon` file; the vision model and
  NVDA's facts about the focused control inform the coder.
- [x] **3.9 Add-ons for people who cannot read code.** Plain facts about the code before it is turned on;
  code compared with the request; a guard around every generated add-on; automatic debugging and correction;
  `repair_addon` for a fix described in words.
- [x] **3.10 More of the web.** Page outline with heading levels, moving NVDA's reading position to an item,
  back, forward and reload.
- [x] **3.11 Managing models.** Settings list the stored models; a window removes some or all and leads to
  choosing others; after a new choice the unused ones are offered for removal (`catalog.stored`,
  `dialogs.ManageModelsDialog`, `plugin.removeModels`). Stop the engines before deleting model files.
- [x] **3.12 Settings stay the user's.** Changes only to what was asked about; a record of every change;
  `undo_change` and `list_changes`.
- [x] **3.13 The mouse from the keyboard.** Right-click, double-click, pointing and dragging on listed items;
  G to pick up and drop in the overlay; pointer mode (NVDA+Alt+K) for controls with nothing to list.
- [x] **3.14 Websites and programs made accessible for good.** `check_access` inspects a web page (Chromium
  browsers and Firefox alike, through NVDA's virtual buffer), a window or the focused control; `fix_access`
  and `add_fix` make lasting fixes of five kinds (jump, press, read, name, watch), kept as data in one add-on
  per website or program that is put together from fixed parts, never written by a model.
- [x] **3.15 Installed add-ons.** `addon_info` answers questions about any installed add-on; the help texts
  of running add-ons are a knowledge source.
- [x] **3.16 The latest small models.** Qwen3.5 0.8B and Qwen2.5 Coder 0.5B built in; `models.json`, written
  from the catalog by `tools/write_models_list.py`; "Look for newer models" in the models window, which asks
  first; every fetched entry checked by `catalog.checkEntry`.
- [x] **3.17 Scrolling on any screen.** `scroll_view` turns the wheel and says whether anything moved; Page
  Down, Page Up and S in pointer mode; pointer steps and areas follow the monitor's scaling and the window's
  size; scrollbars found in a window's picture by plain code, and the vision model asked for other things
  worked with the mouse, in the deep inspection of a window.
- [x] **3.18 Arrow keys for controls that are dragged.** `work_control` and D in pointer mode take hold of a
  dial, knob or custom slider; the way it is worked (through UI Automation, the wheel, dragging up and down,
  sideways or around) is found by trying and comparing its picture; every press says what changed; K keeps
  it under a hotkey as data.
- [x] **3.19 How a sighted person works each control.** The inspection sorts controls by how they are worked
  from NVDA's facts; what the facts do not say is put to both models (the vision model sees the picture, the
  coder model reads a deep query of NVDA, UI Automation, the window and the off-screen model); the remedy is
  chosen by plain code (`working.remedy`).
- [x] **3.20 The latest developer guides.** `update_guides` downloads them after a question and keeps them as
  Markdown; they are searched with VisionClaw's own notes, which win where both fit equally.
- [x] **3.21 One small question at a time.** Forms narrowed to what the results allow, for every model; for
  the very smallest models one field per call and quoted answers; a setting with Automatic, Always, Never.
- [x] **3.22 One model for both jobs.** Never called two; its choice checked against the user's words, and
  the user asked when they differ; loaded once; "what model is installed" answered by plain code.
- [x] **3.21 A newer version of VisionClaw.** Looking on GitHub when asked or, by the user's choice, when NVDA
  starts; always a question before a download; the file checked; NVDA does the installing.
- [x] **3.23 NVDA's commands, all of them.** Found by the telling word among every command, also those
  without a description; run with a real key press or a stand-in; pressed as often as the words ask (the time
  once, the date twice). The request that failed in real use is replayed in `tests/test_nvda_stub.py`.
- [x] **3.24 VisionClaw's own log.** Detailed, Brief or Off; a button and a request that open it; a fault
  inside a tool ends its step only.
- [x] **3.25 Everything inside NVDA.** `find_nvda` and `inspect_nvda` for any function, class, module or
  value; `object_info` for every fact of a control; `audit_nvda` for the whole of it, with how speech and
  braille are driven; notes on NVDA's inside written from its source.
- [x] **3.26 Every question about a picture is answered.**
- [x] **3.27 Questions answered from NVDA, the program, the window and Windows.** `look_up` asks all four in
  that order; plain code keeps what is about the question and says so when nothing is; the keys of Windows
  as notes written from Microsoft's own page.
- [x] **3.28 What is new, in a box that can be read line by line**, when a newer version is offered.
- [x] **3.29 Learning about the program or game in front.** `learn_app` identifies it, asks, reads Wikipedia,
  Wikidata and the program's own website, and keeps notes as Markdown; `note_page` adds a page from the user's
  browser; `app_notes` and `forget_notes`; questions are answered from the notes by `look_up`.
- [x] **3.30 The models used for more.** A model names the program and its kind, writes the notes, says what
  "this" means, and judges whether what was looked up answers the question; plain code checks each.
- [x] **3.31 Controls that need more than a click, and every kind of control.** Hover with what appeared read
  out, press and hold, gestures, a click at the right moment or in a rhythm, the middle button, a key held
  down, a place on a thing, zoom; found by the inspection from a control's own name or by the models; hotkeys
  that hold or hover; all 156 kinds of control NVDA has sorted.
- [x] **3.32 Fingers and pressure.** `touch_gesture`: a pinch, a spread, a swipe with one to five fingers, a
  turn with two, a tap, a double tap, a touch that is held; the wheel instead where a program takes no touch,
  and what worked kept for the program. `pen_stroke`: a press or a line with a pressure in words, in percent,
  rising or falling. Tested with a stand-in for Windows; see `tests/live_touch.py`.
- [x] **3.33 Games that read the mouse directly.** `turn_view` and `mouse_way`; the mouse's own movement; a
  game's own pointer brought to a place from the corner of its window and measured; M in pointer mode; the
  inspection saying what Windows reports of its pointer. Tested with a game drawn by the test.
- [x] **3.34 A game controller.** Noticed when it is connected; controller mode (NVDA+Alt+J, or View and Menu
  held together) with sticks, buttons, triggers, the buzz and jumping between the things in a window; a button
  as a hotkey of a program; a setting with three choices. Tested with made-up controller states.
- [x] **3.35 The developer guides put to use.** Code examples kept whole; the guides as plain sentences for
  questions and as single facts for the writer of an add-on, given only where they add a name the notes do
  not have; `guides_info` and `remove_guides`; instructions and skills chosen by where lines are from.
  Measured with the real coder model: no harm, no gain on nine everyday add-ons.
- [x] **3.36 Add-ons by what the user wants, and NVDA Coach.** `addon_info` finds the installed add-on that
  says it does something; `coach` gives a hint, a step, a lesson, the list or the progress from NVDA Coach's
  own files, or opens it; how much help the user wants is read from their words and remembered. Tested with
  stand-ins and with NVDA Coach's real English lessons read from its repository; not run inside NVDA.
- [x] **3.37 NVDA's own list of what is new, and keys in the description window.** Both measured or tried on
  the real files of NVDA 2026.3.1 on this computer.
- [x] **3.38 Free training material from the internet.** `update_training` downloads the NVDA wiki's pages
  and the transcripts of AFB's and Hadley's lessons after a question that names every site; `training_info`,
  `remove_training`; each page asked only about what it is about and after NVDA's own help. Tried on the real
  pages, fetched once by hand; the add-on's own download code has not fetched them yet.
- [x] **3.39 Everything as Markdown files.** NVDA's user guide, its list of what is new and each add-on's help
  are kept as Markdown in `help` and read from there.
- [x] **3.41 Guides that come with every build.** The NVDA Developer Guide, which is under the GPL, is part of
  the add-on as Markdown; the others wait for their owners' yes.
- [x] **3.42 Telling the user what can be downloaded.** `downloads_info`, a button in the settings, and one
  sentence said once after a fitting answer.
- [x] **3.40 A hand on the mouse.** A skill for the times a blind user works a real mouse or trackpad, in place
  of the skill that leads back to the keyboard. Not measured with a model.
- [x] **3.43 The data folder inside the add-on, and a portable copy.** Moved in at start, carried over on
  update and removal; one file or a portable NVDA with everything in it, made from the settings. Tested with
  plain Python, the real wxPython and a real file of 1.1 GB; not run inside NVDA.
- [x] **3.44 The computer itself.** Things opened by their name; the Recycle Bin checked and emptied; the
  computer's volume; windows switched to, closed, minimized and maximized; the user's folders and files; facts
  about the computer; locking, restarting and shutting down. Reading was run on the owner's real Windows 11;
  everything that changes something only against stand-ins.
- [x] **3.45 Several things in one request, and things that depend on something.** Up to eight things, split by
  plain rules; "if you see", "if it is open", "if the Recycle Bin is not empty" checked by a step of its own.
  Measured with the real Qwen3.5 9B on the owner's own five requests.
- [x] **3.46 A named control of the program in front.** On or off, up or down, also on another page of a dialog
  with tabs and in the window's picture. Tested with stand-in controls; not run in a real program.
- [x] **3.48 The user's own files.** A folder or text file made; a file or folder renamed, moved, copied, or
  moved to the Recycle Bin; undone with "undo that". Run for real on files in a folder of the test's own, with
  the Recycle Bin stood in for; not run inside NVDA.
- [x] **3.47 The router.** A model is offered what fits where the user is and what they said, and is not asked
  at all where the words are sure. Measured with the real model on the whole of `tests/live_orchestrator.py`.
- [x] **3.49 A web page explored, and what stops a form.** `explore_page` and `form_trouble`, the first two
  things built against what JAWS 2027's Vispero Companion does (its Page Explorer, and its help with a form
  that will not send). Tested with a stand-in web page and with the real model choosing the job; not run in a
  browser inside NVDA. What is still missing against JAWS is listed in `docs/STATUS.md`.
- [x] **3.50 A setting only for one program.** NVDA's configuration profile for the program in front, made after
  a question, written to only while it is the one NVDA writes to; undone in that program; listed and deleted.
  Tested against a stand-in written from NVDA's source, and with the real model choosing the job; not run in NVDA.
- [x] **3.51 Requests that follow the one before.** The same again, more, the other way, the answer again, the
  same elsewhere, the second one, and the same about another thing. Measured with the real Qwen3.5 9B.
- [x] **3.52 A date in a calendar that takes no keys.** From the web page, the window, or its picture. Tested on
  calendars made up by the test; not run in a real browser or program.
- [x] **3.53 Everywhere, or only here.** A setting changed in NVDA's normal configuration while a program's own
  profile is on; the user asked where the words do not say. Tested against the stand-in; not run in NVDA.
- [x] **3.54 Working through a task when the usual path is not clear**, and VisionClaw's own windows off limits.
  Tested on a program made up by the test, and with the real model choosing the job; not run in a real program.
- [x] **3.55 A voice of its own**, set in NVDA's Speech settings. Tested against the stand-in; not run in NVDA.
- [x] **3.56 The JAWS Migration Assistant and ClassicSpeech.** Tested against stand-ins built from their source;
  neither was installed where this was written.
- [ ] **3.5 Test inside NVDA.** Install the build in NVDA (ask the user first) and walk through
  `docs/TESTPLAN.md`. Fix what breaks. *Done when:* every item in the test plan is ticked by a real run.

### Phase 4 — Learning
- [x] **4.1 Knowledge base** for NVDA add-on development, and lessons memory.
- [x] **4.4 Memories and the library.** Memories in Markdown, kept when asked or when needed, forgotten in
  words or in a window; the user's library and notes on accessibility interfaces, Windows and common programs
  looked things up in with everything else.
- [ ] **4.2 Learn from this NVDA.** Index NVDA's shipped user guide and the source of installed add-ons as
  examples; add a `learn` command that studies a topic and stores notes. *Done when:* a question about an NVDA
  feature is answered with a quote from the user guide.
- [x] **4.3 Skills.** SmallClaw-style `SKILL.md` files (starting words, the jobs they are for, plain sentences,
  and optional fixed steps), 56 built in for what blind people do at a computer, seven of them for the add-ons
  the models write (`claw/skills/`), chosen by
  plain code from the request's words, their sentences given to the forms, the vision model, the coder and the
  answer of their jobs; a skill with steps runs them as its plan. The user makes, changes, turns off, deletes and
  imports skills in the skills window (NVDA+Alt+I) or in words, and opens the skills folder with a button.

### Phase 5 — Quality with real models
- [ ] **5.1 Evaluation set.** 40 requests with expected outcomes (settings, vision, add-ons, multi-step) in
  `tests/eval/`; a runner that scores them against the real models. *Done when:* the score is recorded in
  `docs/STATUS.md`.
- [ ] **5.2 Prompt tuning** against the evaluation set for Qwen3.5-2B and Qwen2.5-Coder-1.5B, then the larger
  pair. Do not tune on fewer than the whole set.
- [ ] **5.3 Add-on templates.** Deterministic templates the coder fills in, for the request kinds where free
  code generation scores worst.

### Phase 6 — Reach
- [ ] **6.1 Optional CUDA engine** download for NVIDIA cards (Vulkan already uses them; CUDA is faster).
- [x] **6.2 Voice input** for requests, with a local Qwen ASR model: Qwen3-ASR 0.6B or 1.7B in the bundled engine,
  NVDA+Alt+V. The real model heard 24 of 24 requests spoken by Windows' own two voices; the microphone code got
  sound from Windows on the owner's computer. A person speaking into a microphone, and all of it inside NVDA, are
  still to be tried.
- [ ] **6.3 Bridge to a real SmallClaw gateway** for users who also run SmallClaw: expose the two models as an
  OpenAI-compatible endpoint SmallClaw can use, and accept SmallClaw tasks.
- [ ] **6.4 Translations** and submission to the NVDA Add-on Store.

## Testing

```
python tests/run_all.py                  every plain-Python test (no model needed)
python tests/test_lookup.py              questions against every NVDA command and the notes; plain Python
python tests/test_skills.py              every built-in skill checked; choosing, the user's skills, a skill's plan
python tests/test_skills_window.py       the skills window with the real wxPython and stand-ins for NVDA's gui
python tests/test_learn.py               learning about a program against a stand-in internet; every request listed
python tests/test_memories.py            memories as files, kept, recalled, forgotten; the library; gated notes
python tests/test_guides.py              the developer guides as sentences and as facts, which facts a request gets,
                                         add-ons by what the user wants, NVDA Coach's lessons from made-up files,
                                         NVDA's list of what is new, keys in the description window
python tests/test_touch.py               fingers, pressure, a turn in the mouse's own steps, a drawn game with a
                                         pointer of its own brought to a place and measured; plain Python
python tests/test_gamepad.py             a game controller's states, buttons and sticks; its skills and notes
python tests/test_computer.py            working the computer itself, requests that depend on something, long requests
                                         split by plain rules, a named control, the router; whole requests with
                                         stand-in tools and a scripted model
python tests/test_profiles.py            an NVDA setting for one program: what the words ask, and NVDA's profiles
                                         against a stand-in written from NVDA's source
python tests/test_followups.py           requests that follow the one before: kinds, what plain code writes out, the
                                         check of what a model wrote, whole requests in a row
python tests/test_dates.py               dates from typed and spoken words, and calendars made up by the test that
                                         answer to presses: of controls, and only drawn
python tests/test_voice.py               asking by voice without a microphone: when speech begins and ends, the
                                         speech models and what cannot be added to them, a whole spoken request
python tests/test_ask_window.py          the Ask window's voice button with the real wxPython and a stand-in voice
python tests/test_guide.py               working through a task on a program made up by the test: every step asked
                                         about, a check-in, staying in one program, stopping, what was done
python tests/test_partners.py            the JAWS Migration Assistant and ClassicSpeech against stand-ins built from
                                         their source; neither job offered without its add-on
python tests/live_followups.py MODELS    a real model writes follow-up requests out in full; read every line
python tests/live_voice.py FOLDER a.wav  the real speech model on recordings that are files; with --mic the real
                                         microphone, loudness only; never run --mic without asking the owner
python tests/live_touch.py               says what it would do; with --yes really touches and presses, inside
                                         its own window only; never run it without asking the owner
python tests/live_learn.py               a real model and the real internet learn about a program; read every note
python tests/live_orchestrator.py        needs the engine and a model on this computer
python tests/live_side_by_side.py        two real engines on two backends; needs VisionMate's vision data
python tests/live_addon.py               a real model writes four add-ons and debugs one; read every result
python tests/live_addon_memories.py      a real model writes add-ons with a memory, the library and the notes on
                                         accessibility interfaces put first; read every result
python tests/test_portable.py            the data folder moved in, carried over when NVDA deletes the add-on's folder,
                                         a portable copy as one file and into a portable NVDA, the settings it carries
python tests/test_portable_window.py     the portable copy's window with the real wxPython: what it says, each refusal
python tests/test_pageview.py            a web page explored and a form's trouble found, on a stand-in page; the keys
                                         compared with the user guide of the NVDA installed on this computer
python tests/test_training.py            the training material against a stand-in internet: the fixed sources, a
                                         lesson without the site around it, gates, the Markdown help files
python tests/live_addon_guides.py MODELS GUIDES   a real model writes the same add-ons with and without lines of
                                         the developer guides; read every add-on
python tests/live_followup.py MODELS     a real vision model answers questions in the description window before
                                         and now; add --dry to see only what plain code would give
python tests/live_quants.py FOLDER 1 ID1 ID2   two quants of one coder write the same add-ons; counts passes
                                         and repair rounds; read every add-on it writes to a file
python tests/live_working.py             both real models say how drawn and described controls are worked
python tests/live_prompts.py             a real vision model describes drawn pictures with and without the
                                         instructions for blind users; read every answer
python tests/test_help.py                the help files name every key, setting and kind of request, and say what
                                         is new in the manifest's version
python tools/write_help.py               writes what is new into readme.html and README.md from the changelog;
                                         run after every change to the changelog
python tools/write_models_list.py        writes models.json from the catalog; run after every change to CATALOG
python tools/write_command_fixture.py    writes tests/nvda_commands.json from NVDA's globalCommands.py
python tools/update_shipped_guides.py    fetches the guides that may be passed on and puts them into the add-on;
                                         run before every build
python tools/audit_nvda_source.py        counts NVDA's modules, commands, drivers and extension points from its source
python build.py                          writes dist/VisionClaw-<version>.nvda-addon
```

Run `python tests/run_all.py` before every commit. Compile every add-on file with Python 3.11 syntax in mind
(no `match`-only features newer than 3.11, no PEP 695 generics).

## Releasing

1. Bump `version` and `changelog` in `addon/manifest.ini`. Each point of the changelog says how to use what is
   new: the words to say or the keys to press.
2. `python tools/write_help.py`, so that both help files say what is new in this version; check that every new
   feature has its own part in both. `python tools/update_shipped_guides.py`, so that the build carries the
   guides as they are now; then `python tests/run_all.py`, then `python build.py`.
3. Commit, tag `v<version>`, push, and create a GitHub release with `dist/VisionClaw-<version>.nvda-addon` and
   the fixed-name copy `VisionClaw.nvda-addon`.
   VisionMate's own version tags were renamed locally to `visionmate-v...` so that they do not collide with
   VisionClaw's `v...` tags. Never push the `visionmate-` tags.
4. The owner made 0.12.0 the full release 1.0.0 on 2026-11-18, before phase 3.5 was done. From 1.0.0 on, releases
   are full releases, not pre-releases; the notes still say what has not been run in NVDA.
5. Installed copies find a release through `claw/updates.py`. For that the tag must be `v` and the version in
   numbers, the release must not be a draft, and it must carry `VisionClaw-<version>.nvda-addon`. Put what is
   new under a heading that begins "New in": that part is read out to users who are offered the version.

## Credits that must stay

- VisionMate by Athiban Vijay — the describe, overlay, OCR and chat-photo features (GPL v2 or later).
- SmallClaw by XposeMarket (MIT) — the agent design the `claw/` package follows.
- llama.cpp (MIT) — the engine. Qwen models by the Qwen team, Alibaba Cloud (Apache 2.0).
- The NVDA Developer Guide by NV Access and contributors (GPL v2 or later) — comes with every build as Markdown.
