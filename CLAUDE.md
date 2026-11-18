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
  on or put into the add-on, and an answer made from it says where it is from. A site that answers a program
  with a challenge is not to be worked around; the earlier copy stays. Never add a source without the owner's
  yes; `tests/test_training.py` fails when the sources or servers change.
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
- **Measure with the real model.** After any change to a prompt, a recipe or a form, run
  `python tests/live_orchestrator.py` and read every answer. A change that passes the scripted tests can still
  make a small model worse.
- **Patch files with a script file, not a shell heredoc.** In this environment Bash heredocs that contain
  triple-quoted Python with apostrophes fail to parse, and a heredoc turns two backslashes into one, so that
  a regular expression's `\b` arrives as a backspace character. Write the patch script with the Write tool
  and run it.
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
    mousetools.py            the mouse from the keyboard: click, right-click, double-click, drag, the wheel,
                             the screen's scaling, pointer mode; holding the button, resting the pointer and
                             what appeared, gestures, a click when something changes or in a rhythm, keys held
                             down during a click or a turn of the wheel; the mouse's own movement for a game
                             that reads the mouse directly, Windows' facts about its pointer, and how the
                             mouse is moved while a tool works in such a game
    touchinput.py            fingers and a pen through Windows itself: a gesture as the places every finger
                             passes through, a pen stroke with a pressure at each place, a pen held down
    touchtools.py            the tools for fingers and pressure: touch, compare, the wheel instead, what worked
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
      drivers.py             rules that keep speech and braille alive; what happened with each driver
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
  and optional fixed steps), 49 built in for what blind people do at a computer, seven of them for the add-ons
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
- [ ] **6.2 Voice input** for requests, with a local Qwen ASR model.
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
python tests/live_touch.py               says what it would do; with --yes really touches and presses, inside
                                         its own window only; never run it without asking the owner
python tests/live_learn.py               a real model and the real internet learn about a program; read every note
python tests/live_orchestrator.py        needs the engine and a model on this computer
python tests/live_side_by_side.py        two real engines on two backends; needs VisionMate's vision data
python tests/live_addon.py               a real model writes four add-ons and debugs one; read every result
python tests/live_addon_memories.py      a real model writes add-ons with a memory, the library and the notes on
                                         accessibility interfaces put first; read every result
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

1. Bump `version` and `changelog` in `addon/manifest.ini`.
2. `python tools/update_shipped_guides.py`, so that the build carries the guides as they are now; then
   `python tests/run_all.py`, then `python build.py`.
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
