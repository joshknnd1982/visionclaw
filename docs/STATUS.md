# VisionClaw status

Updated 2026-11-17, version 0.1.0.

## What exists

Everything in phases 1 to 3.4 and 4.1 of `CLAUDE.md`: the fork, the model catalog and models window, the
graphics choice with fallback, the two-model runtime, the planner with recipes, agreement between the models,
the step runner, 21 NVDA tools, the Ask VisionClaw window, app helpers, generated add-ons, the knowledge base
and the lessons memory.

## What was tested, and how

| Test | What it shows | Result |
|---|---|---|
| `tests/test_core.py` | Whole requests through the orchestrator with scripted models: splitting into parts, recipes, agreement, a corrected choice, disagreement decided by the user, a wrong form fixed from the tool's error, a hint from the other model, an honest answer when a part fails, a plan the model writes itself, stopping | passes |
| `tests/test_parts.py` | Catalog entries, a resumable download from a local server that is cut off half way, a damaged file refused, cancelling, shared model files, forgiving matching, the code check, the write-check-repair-review loop for add-ons, storing and packaging an add-on, the knowledge base | passes |
| `tests/test_nvda_stub.py` | The real plugin and all its files load against stand-ins for NVDA; all 21 tools and 15 recipes are in place; settings are found by plain words and changed through the configuration; the user is asked before a change; an app helper is saved and removed; a generated add-on is checked, loaded into the running plugins and removed | passes |
| `tests/live_orchestrator.py` | Seven real requests with a real model in the bundled engine, on a GeForce RTX 5060 Laptop GPU, with stand-in tools | 7 of 7 did the right thing, 0.4 to 3.5 seconds each |
| Engine backends | The engine started and answered on the dedicated card, on the built-in chip through Vulkan, and on the processor; the context grew from 4096 to 8192; a running answer was cancelled in 0.7 seconds | worked |
| Catalog addresses | Sizes and SHA-256 values were read from Hugging Face's own file listings on 2026-11-17 | recorded |

## What was not tested

- **Nothing has been run inside NVDA.** The stand-ins accept any call, so mistakes in how NVDA's own API is
  used (commands, gestures, speech capture, dialogs, the settings panel, the overlay reuse) are not caught.
  This is phase 3.5 and comes first.
- **The suggested models have not been downloaded or run.** The live test used VisionMate's Qwen3-VL 2B for
  both jobs. So: Qwen3.5 has not been loaded by this engine build, the thinking switch has not been seen
  working, Qwen2.5-Coder has not written an add-on here, and two different models have not disagreed with each
  other in a real run. With one model in both roles, agreement is nearly certain; expect more "the models do
  not agree" questions with two different models.
- **No real download from Hugging Face** was made by the add-on's own code; the download code was tested
  against a local server only.
- **Generated add-ons** have only been written by a scripted stand-in for the coder model.
- Speed on the processor alone and on low-memory computers.

## Known limits

- The models window, settings and tool results are in English; translations are phase 6.4.
- A generated add-on can be exported as an `.nvda-addon` file only from code (`Helpers.export`); there is no
  command for it yet.
- `run_command` runs NVDA's script directly; a few scripts that depend on how they were triggered may behave
  differently than when pressed.
- App helpers find their item by text, so an item that is only an unnamed icon cannot be a helper's target yet.
- The check on generated code is not a sandbox.

## Next session

Phase 3.5: install the build in NVDA (ask the owner first), walk through `docs/TESTPLAN.md`, fix what breaks.
Then download the two suggested models and repeat `tests/live_orchestrator.py` with them.
