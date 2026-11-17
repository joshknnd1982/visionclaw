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

- **Local only.** The add-on's own code connects to the internet only to download models, and only after the
  user says yes. Never add telemetry, cloud APIs, or update checks. The web tools hand an address to the user's
  own browser when the user asks; the models never go online.
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
- **What plain code can correct, plain code corrects.** A small model keeps what it once wrote however often
  it is told. Before sending code back to the coder, `microaddons.tidy` takes out what was not asked for, adds
  forgotten imports and `nextHandler()`, fixes role comparisons, adds a program limit, and salvages a file that
  was cut off. Add to `tidy` whenever the real model shows a new mistake of this kind, and never show the coder
  an example that does two things: it copies all of it.
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
    nvdainfo.py              what NVDA has and uses: synthesizer, voices, braille display, drivers, add-ons
    helpers.py               app helpers and generated add-ons: loading them live, their hotkeys
    (the rest)               VisionMate features: overlay, OCR, chat photos, labels ...
    claw/                    SmallClaw-style core. NO NVDA imports.
      catalog.py             model catalog, what is installed, downloads
      backend.py             dedicated GPU -> Vulkan -> CPU choice and fallback
      runtime.py             both engines; loads, swaps, resizes context
      policy.py              picks context size, token limits, temperature, reasoning per task
      llm.py                 JSON-constrained calls, reasoning levels, prompt trimming
      match.py               forgiving matching of what a model writes against what exists
      web.py                 web addresses, search addresses, the passages of a page that matter
      drivers.py             rules that keep speech and braille alive; what happened with each driver
      planner.py             splits a request into parts; recipes; free plans and their repair
      consensus.py           the two models agree, or the user decides
      agent.py               the tool loop for one step
      tools.py               tool registry
      memory.py              lessons learned, kept between sessions
      knowledge.py           searchable NVDA add-on knowledge (claw/knowledge/*.md)
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
- [ ] **3.5 Test inside NVDA.** Install the build in NVDA (ask the user first) and walk through
  `docs/TESTPLAN.md`. Fix what breaks. *Done when:* every item in the test plan is ticked by a real run.

### Phase 4 — Learning
- [x] **4.1 Knowledge base** for NVDA add-on development, and lessons memory.
- [ ] **4.2 Learn from this NVDA.** Index NVDA's shipped user guide and the source of installed add-ons as
  examples; add a `learn` command that studies a topic and stores notes. *Done when:* a question about an NVDA
  feature is answered with a quote from the user guide.
- [ ] **4.3 Skills.** SmallClaw-style `SKILL.md` files (trigger words + instructions) for common jobs: relabel a
  control, remap a key, announce changes in a window region, fix an unlabelled app. Chosen by keyword, injected
  into the step prompt.

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
python tests/live_orchestrator.py        needs the engine and a model on this computer
python tests/live_side_by_side.py        two real engines on two backends; needs VisionMate's vision data
python tests/live_addon.py               a real model writes four add-ons and debugs one; read every result
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
4. Until phase 3.5 is done, releases are marked **pre-release** and the notes say what has not been run in NVDA.

## Credits that must stay

- VisionMate by Athiban Vijay — the describe, overlay, OCR and chat-photo features (GPL v2 or later).
- SmallClaw by XposeMarket (MIT) — the agent design the `claw/` package follows.
- llama.cpp (MIT) — the engine. Qwen models by the Qwen team, Alibaba Cloud (Apache 2.0).
