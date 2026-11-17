# VisionClaw status

Updated 2026-11-17, version 0.3.3.

## What exists

Everything in phases 1 to 3.4 and 4.1 of `CLAUDE.md`: the fork, the model catalog and models window, the
graphics choice with fallback, the two-model runtime, the planner with recipes, agreement between the models,
the step runner, 32 NVDA tools and 26 recipes, the Ask VisionClaw window, app helpers, generated add-ons, the
knowledge base and the lessons memory. New in 0.2.0: the web through NVDA's browse mode, reporting on speech,
braille, drivers and add-ons, safe switching of the synthesizer and braille display, and saving a generated
add-on as a file. New in 0.3.0: a guard around generated add-ons with automatic debugging and correction,
plain-language facts about generated code, checks of code against the request, corrections by plain code,
page outline, moving to a place on a page, and back, forward and reload.

## What was tested, and how

| Test | What it shows | Result |
|---|---|---|
| `tests/test_core.py` | Whole requests through the orchestrator with scripted models: splitting into parts, recipes, agreement, a corrected choice, disagreement decided by the user, a wrong form fixed from the tool's error, a hint from the other model, an honest answer when a part fails, a plan the model writes itself, stopping | passes |
| `tests/test_parts.py` | Catalog entries, a resumable download from a local server that is cut off half way, a damaged file refused, cancelling, shared model files, forgiving matching, the code check, the write-check-repair-review loop for add-ons, storing and packaging an add-on, the knowledge base | passes |
| `tests/test_nvda_stub.py` | The real plugin and all its files load against stand-ins for NVDA; all 32 tools and 26 recipes are in place; settings are found by plain words and changed through the configuration; the user is asked before a change; an app helper is saved and removed; a generated add-on is checked, loaded into the running plugins, saved as a file and removed; a stand-in web page is listed, a link followed, a button pressed after a question, a field filled, a long page read by passage, an address opened and a search made; the synthesizer is reported, switched, switched back when not confirmed, warned about the next time, and refused when it would leave no speech and no braille | passes |
| `tests/live_orchestrator.py` | Eighteen real requests with a real model in the bundled engine, on a GeForce RTX 5060 Laptop GPU, with stand-in tools: settings, commands, looking, clicking, the web, a search box, speech and braille questions, switching the synthesizer, page headings, moving to a heading, going back, fixing an add-on | 18 of 18 were handled the right way, 0.2 to 3.9 seconds each. The answer to the web search was "could not find", because the stand-in page was not a search result. |
| `tests/live_addon.py` | A real model (Qwen3-VL 2B, which is not a coder model) writes four small add-ons and debugs a failing one, through the bundled engine. Nothing is loaded into NVDA; each result goes through the checks. | 4 of 4 passed the checks in 2 to 12 seconds, each doing only what was asked; the failing add-on was corrected in about 1 second (`api.getFocus` became `api.getFocusObject`). Getting there took five rounds of fixes to the instructions and checks, which is why `tidy`, `checkAgainst`, `salvage` and `CodeGuard` exist. |
| Names in NVDA's own code | Without running NVDA, the compiled modules of the NVDA 2026.3.1 on this computer were searched for every NVDA function and attribute the new code uses | All found except NVDA's braille-input typing function, which has moved; typing was rewritten to go through Windows itself (0.3.1). Finding a name does not prove it behaves as expected. |
| Engine backends | The engine started and answered on the dedicated card, on the built-in chip through Vulkan, and on the processor; the context grew from 4096 to 8192; a running answer was cancelled in 0.7 seconds | worked |
| `tests/test_runtime.py` | Where the two models are put, with stand-ins for the engines and chips: together when they fit, the second on another chip or the processor when they do not, taking turns only when there is no room anywhere, falling back when a chip does not start, never moving a model that is only restarted for a larger context | passes |
| `tests/live_side_by_side.py` | Two real engines on this computer, the first chip reported as full: one model on the GeForce RTX 5060, the other on the Radeon 780M through Vulkan, both loaded, six alternating answers in 0.4 seconds | worked |
| Catalog addresses | Sizes and SHA-256 values were read from Hugging Face's own file listings on 2026-11-17 | recorded |

## First run inside NVDA (2026-11-17, NVDA 2026.3.1, version 0.3.1)

Seen from outside NVDA, after the owner installed the add-on and restarted. NVDA's logging level was Off, so
errors inside NVDA could not be read; what the owner heard is not recorded here yet.

- The add-on loaded: its data folder was created and the models window ran.
- The owner chose Qwen3.5 4B for vision and Qwen3.5 9B for coding. Both were downloaded from Hugging Face by the
  add-on's own code, about 9 GB, and passed the size and SHA-256 check (the files have their final names, which
  they only get after the check).
- The engine was started by the add-on with Qwen3.5 4B and its projector on the GeForce RTX 5060
  (`--device Vulkan0`), and reported healthy.
- Asked directly, that engine answered at once with thinking switched off, kept to a JSON form, and with
  thinking switched on gave its thinking separately from its answer. So this engine build runs Qwen3.5, and the
  thinking switch works.

The owner then tried the add-on and reported that nothing went wrong. Which of the test requests were tried
was not written down, so the test plan is not ticked off from this.

After installing 0.3.2 the owner reported that the models window (NVDA+Alt+M) works in NVDA 2026.3.1. Which of
its buttons were used was not written down; removing a model for real is not confirmed.

## A wrong change in real use, and what was done about it (0.3.3)

In NVDA the owner asked "restore the voice pitch to what it was before you changed it". VisionClaw changed the
speech rate instead. The cause, read from VisionClaw's own lessons file:
1. The search for the setting compared what share of the request's words matched, so a long sentence that said
   "pitch" once matched nothing.
2. The error message gave examples ("like speech rate"), and the model copied the example as its next search.
3. Nothing checked that the setting to be changed was the one asked about, and nothing recorded the old value,
   so the change could not be undone. A lesson was even stored that would have repeated the mistake.

Fixed in 0.3.3: settings are found by how many of the request's words name them; error messages give no
examples; `set_setting` refuses a setting the request says nothing about and shows the request in its question;
every change is recorded (`claw/changes.py`) and can be listed and undone (`undo_change`, `list_changes`);
lessons are no longer learned from searches, and the misleading ones are dropped at start. The request that went
wrong is replayed in `tests/test_nvda_stub.py`. The old speech rate is not known; the owner has to set it again.

## Two different models in one run (2026-11-17)

`tests/live_orchestrator.py` was run with the owner's models: Qwen3.5 4B for vision on the GeForce RTX 5060 and
Qwen3.5 9B for coding, which did not fit beside it and ran on the Radeon 780M through Vulkan, both loaded.
20 of 21 requests were handled the right way, in 2.4 to 10 seconds each, and the two models chose the same way
every time, so the user was never asked to decide. The one failure: the model wrote a setting's name
("speech: rate") where its id was wanted, which the stand-in tool refused; the real tool accepted near misses
already and now accepts the name too.

## What was not tested

- **Model management (0.3.2)**, apart from the owner's report above, was tested against stand-ins only: listing what is stored, removing some or all
  models, falling back to another stored model, and the offer to remove models no longer used. The window
  itself, and deleting a model file right after its engine was stopped, have not run in NVDA. The listing was
  run read-only against the owner's real models folder and showed Qwen3.5 4B (3.2 GB) and Qwen3.5 9B (5.3 GB).

- **Inside NVDA, only loading, the models window, downloading and starting the engine have been seen to
  work** (see above). Asking, the tools, the settings panel, app helpers, the web tools, driver switching and
  add-ons have not been confirmed there. The stand-ins accept any call, so mistakes in how NVDA's own API is
  used are not caught. This is phase 3.5.
- **The live tests used VisionMate's Qwen3-VL 2B for both jobs.** Qwen3.5 4B has since been seen running in
  the engine (see above), but no request has been run through two different models, Qwen3.5 9B has not been
  loaded yet, Qwen2.5-Coder has not been tried at all, and two different models have not disagreed with each
  other in a real run. With one model in both roles, agreement is nearly certain; expect more "the models do
  not agree" questions with two different models.
- **Generated add-ons have not run inside NVDA.** A real model has written and corrected them, and they pass
  the checks, but whether they then do the right thing in NVDA is untested. Passing the checks is not the same
  as working: one of the four test add-ons says "no link focused" on every control that is not a link, which
  nobody asked for and no check catches.
- **The guard around add-ons** (errors caught, the event handed on, the add-on paused, automatic correction)
  has only run against stand-ins. It wraps the add-on's class before NVDA sees it; whether NVDA's own handling
  of key commands and events accepts the wrapped methods must be confirmed in NVDA.
- Only four requests for add-ons, all simple, have been tried with a real model. Harder ones will fail more
  often, and a real coder model has not been tried at all.
- **The web tools have only met a stand-in page.** They rely on NVDA's browse mode (`_iterNodesByType`, the
  document's text, activating an element), which differs between browsers and NVDA versions. Waiting for a page
  to load is a guess of up to 25 seconds.
- **Switching drivers has only met stand-in drivers.** NVDA's `setSynth` and `setDisplayByName`, and the window
  that asks "does it work?" and closes itself after 20 seconds, have not run in NVDA. Until they have, try a
  switch only with someone sighted nearby or a second way to get speech back. A braille display that needs a
  port to be chosen is not handled.
- Speed on the processor alone and on low-memory computers.
- Side by side was tested with the 2B model loaded twice. How fast a 7B or 9B model answers on a built-in chip
  or on the processor has not been measured, and the memory each model needs (`memoryGb` in the catalog) is an
  estimate that decides whether a model is thought to fit.

## Known limits

- The models window, settings and tool results are in English; translations are phase 6.4.
- Settings that are a free text in NVDA, such as the braille tables, are reported but cannot be changed yet.
- `run_command` runs NVDA's script directly; a few scripts that depend on how they were triggered may behave
  differently than when pressed.
- App helpers find their item by text, so an item that is only an unnamed icon cannot be a helper's target yet.
- The check on generated code is not a sandbox.

## Next session

Phase 3.5: install the build in NVDA (ask the owner first), walk through `docs/TESTPLAN.md`, fix what breaks.
Then download the two suggested models and repeat `tests/live_orchestrator.py` with them.
