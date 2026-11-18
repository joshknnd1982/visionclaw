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
  `mousetools.moveTo`, `mousetools._button` and `nvdatools.typeUnicode` with functions that write down what
  would have happened.
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
- **Measure with the real model.** After any change to a prompt, a recipe or a form, run
  `python tests/live_orchestrator.py` and read every answer. A change that passes the scripted tests can still
  make a small model worse.
- **Patch files with a script file, not a shell heredoc.** In this environment Bash heredocs that contain
  triple-quoted Python with apostrophes fail to parse. Write the patch script with the Write tool and run it.
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
                             the screen's scaling, pointer mode
    accesstools.py           deep inspection, lasting fixes for a website or program, installed add-ons;
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
    followup.py              questions in the description window: all are answered
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
      pointer.py             which mouse action is meant, where a drag ends, how pointer mode moves
      scrolling.py           how far to scroll, steps that follow the screen, whether a scroll moved anything,
                             scrollbars found in a picture
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
      guides.py              the downloaded developer guides: fixed addresses, web page to Markdown, sections
      working.py             how a control is worked, from NVDA's facts or from both models; which remedy fits;
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
  and optional fixed steps), 38 built in for what blind people do at a computer, six of them for the add-ons
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
python tests/live_learn.py               a real model and the real internet learn about a program; read every note
python tests/live_orchestrator.py        needs the engine and a model on this computer
python tests/live_side_by_side.py        two real engines on two backends; needs VisionMate's vision data
python tests/live_addon.py               a real model writes four add-ons and debugs one; read every result
python tests/live_addon_memories.py      a real model writes add-ons with a memory, the library and the notes on
                                         accessibility interfaces put first; read every result
python tests/live_working.py             both real models say how drawn and described controls are worked
python tests/live_prompts.py             a real vision model describes drawn pictures with and without the
                                         instructions for blind users; read every answer
python tools/write_models_list.py        writes models.json from the catalog; run after every change to CATALOG
python tools/write_command_fixture.py    writes tests/nvda_commands.json from NVDA's globalCommands.py
python tools/audit_nvda_source.py        counts NVDA's modules, commands, drivers and extension points from its source
python build.py                          writes dist/VisionClaw-<version>.nvda-addon
```

Run `python tests/run_all.py` before every commit. Compile every add-on file with Python 3.11 syntax in mind
(no `match`-only features newer than 3.11, no PEP 695 generics).

## Releasing

1. Bump `version` and `changelog` in `addon/manifest.ini`.
2. `python tests/run_all.py`, then `python build.py`.
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
