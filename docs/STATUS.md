# VisionClaw status

Updated 2026-11-17, version 0.6.0.

## What exists

Everything in phases 1 to 3.4 and 4.1 of `CLAUDE.md`: the fork, the model catalog and models window, the
graphics choice with fallback, the two-model runtime, the planner with recipes, agreement between the models,
the step runner, 43 NVDA tools and 37 recipes, the Ask VisionClaw window, app helpers, generated add-ons, the
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

## Five tests inside NVDA (2026-11-17, NVDA 2026.3.1, version 0.4.0)

The owner installed 0.4.0, restarted NVDA and ran five tests given to him in chat, with Qwen3.5 4B for vision
and Qwen3.5 9B for coding. He reported that all five pass. NVDA's logging level was Off, and nothing beyond
"all pass" was written down, so what exactly was spoken is not recorded.

1. Pointer mode in Notepad: NVDA+Alt+K turns it on, the arrow keys move the pointer, Escape turns it off.
2. "Which add-ons are installed?" and a question about one of them.
3. "What are the headings on this page?" on a web page.
4. "Inspect this page for accessibility problems" on a web page.
5. "Speak a little faster", then "Undo that".

The matching lines in `docs/TESTPLAN.md` are ticked. Not covered by these five: making fixes and the fixes
add-on, dragging, right-click, typing into web fields, switching drivers, generated add-ons and their
correction, scrolling, and the two smallest models.

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

## The mouse from the keyboard (0.4.0)

Right-click, double-click, pointing and dragging on items found in a window's picture; G to pick up and drop in
the overlay; pointer mode (NVDA+Alt+K); right-click and double-click for app helpers. Tested with stand-ins
that write down every mouse move and button instead of making them: right-click, double-click and pointing at
an item; a drag from one item onto another in small steps with the button released at the end; a drag by
direction and distance; pointer mode's keys through the plugin's own key handling, including hold, move, let
go, and letting go when the mode is left. With the owner's two real models, "right-click the Options button",
"drag the New Game button onto the Quit button" and "make this control keyboard navigable" were each handled
the right way. That run also showed Qwen3.5 4B writing ", " where an item's name belongs in a form with two
fields; since then the user's own words decide which items are meant (`nvdatools.mentioned`).
**None of it has moved a real mouse**: whether programs accept the clicks and drags, and how pointer mode feels
in use, must be found out in NVDA.

## Websites and programs made accessible for good; installed add-ons (0.4.0)

Four tools and four recipes, which makes 40 tools and 34 recipes. `check_access` inspects the web page, the
window or the focused control; `fix_access` makes the fixes for what was found; `add_fix` makes one fix asked
for in words; `addon_info` answers questions about an add-on installed in NVDA. A fix is one of five kinds: two
keys that move between items, a key that presses a control, a key that reads one, a name for controls without
one, and being told when a part changes. The fixes of one website or program are data in one add-on, put
together by code from `fixruntime.py` and `claw/fixmatch.py`; no model writes or repairs it.

Tested, and how:

- **NVDA's own source, read for this.** The source of NVDA 2026.3.1 (the version on this computer) was read
  for everything the new code relies on: Chromium browsers and Firefox share one page builder and one set of
  facts per control (tag, class, id, kind, states); a control's name is only spoken from those facts when
  `alwaysReportName` is set; how NVDA moves its reading position, presses a control and finds a control's
  place; the names of every kind and state used; and the add-on handler's functions. This found one mistake
  that no stand-in would have shown: NVDA asks an add-on to name a control only if the add-on's own class has
  the method, not a class it inherits from, so the method is now written into each add-on that gives names.
  Reading source shows what NVDA should do; it is not a run inside NVDA.
- **`tests/test_access.py`, plain code.** Rules; a page read whole and read in stretches of 37 characters gives
  the same controls with the same texts; class names a person wrote are told from names a tool made up; a
  stand-in feed page gives exactly the findings it holds (12 nameless buttons of which 7 can be named and 5
  cannot be told apart, 2 clickable things that are no controls, a feed of 5 posts whose inner comments are not
  counted, a player whose button is found under either of its names); what changed between two looks; text
  that is only in the picture; a window NVDA cannot read; choosing by number or words; words from a page that
  try to become code stay data; the add-on passes the same check as model-written add-ons and its data reads
  back from it.
- **`tests/test_access.py`, the generated add-on at work** against a stand-in page that behaves as NVDA's source
  says: the next-post key goes post by post, also in small stretches, and finds posts that arrive later;
  previous goes back; a key presses the player's button under whichever name it has; a key reads the time;
  names reach what NVDA reads from the page and the control itself; on another site every key is passed on and
  nothing is named; turning the add-on off takes the names out; a fix that fails says so and raises nothing;
  a change is announced once, and not while the user is elsewhere; in a stand-in window, keys press, read and
  move, and a button is named by its control id.
- **`tests/test_nvda_stub.py`**, the tools through the real registry against stand-ins: the report in the
  tool's own words; nothing made when the user says no; the add-on stored, loaded, listed and working; one
  more fix joining it; a key in use replaced by a free one; refusals that say why; `repair_addon` refusing to
  hand fixes to a model; a name from a picture marked as a guess; "fix number 3" meaning the problem that had
  that number in the report the user heard; removal; an installed add-on's facts, keys and help.
- **`tests/live_orchestrator.py` with the owner's two models** (Qwen3.5 4B and Qwen3.5 9B, on the GeForce RTX
  5060 and the Radeon 780M), stand-in tools, 35 requests of which 11 are new: a deep inspection, "fix the
  accessibility problems on this page", "make this website accessible", "inspect this window for
  accessibility problems, then fix number 2", "give this site keys to move between posts", "make NVDA+alt+P
  press the Play button on this page", "tell me when the inbox count changes", "name the focused button Share
  on this website", "fix number 2", and two questions about an add-on. Both models chose the same, fitting
  recipe for all 35, in 2 to 17 seconds each, and the forms were filled in usably. What the first run showed
  and what was changed for it: (1) "call the focused button Share" was taken as a click by both models, so
  the documented wording is now "name the focused button"; (2) a model wrote "F1" where the add-on's key was
  F12 when it retold the add-on's facts, so those facts are now said in the tool's own words; (3) the model
  wrote "all" as the add-on's name though the request named the Clock add-on, and wrote the new name where
  the control belongs, so in both tools the user's own words now decide what is meant; (4) "the inbox count"
  is not the text of the part it means, so a part is also found by what the page's code calls it; (5) a
  number in "fix number 2" now means the problem that had that number in the report the user heard.

- **An independent review** of this work, arranged by the other session, found six faults by reading the
  code. All are fixed, each with a test: two fixes add-ons for a site and one of its sub-sites wrapped each
  other again on every focus move; the hint words for the new recipes also took ordinary requests such as
  "what key reloads the page" or "fix the problem with my speech"; two websites whose names become the same
  folder name ("my-site.com", "my.site.com") shared one add-on; "fix all" on a page with a running video would
  have announced the time every few seconds; a picture that cannot be taken (screen curtain) ended the whole
  task; and a website's name was written into the add-on without limiting its characters. Looking again for a
  watched control that has gone is now done every 30 seconds with smaller limits.

## The latest small models (0.4.0)

Read from Hugging Face's own listing on 2026-11-17: the newest Qwen family that comes in small sizes is still
Qwen3.5 (0.8B, 2B, 4B, 9B); Qwen3.6 and Qwen3.8 start at 27B. The newest small coder models are still
Qwen2.5 Coder (0.5B, 1.5B, 3B, 7B); Qwen3 Coder starts at 30B. Added to the catalog: Qwen3.5 0.8B for vision and
Qwen2.5 Coder 0.5B, offered first in their lists and never suggested. Qwen2.5 Coder 3B was left out because its
licence is not Apache 2.0. New: `models.json` in the repository, written from the catalog, and the button
"Look for newer models" in the models window, which asks first and then reads that one file.

- Revision, size and SHA-256 of the three new files were read from Hugging Face's API, and each download
  address was asked for its headers: all three answer with the catalogued size and checksum. When 0.4.0 was
  released neither model had been downloaded or run; that was done afterwards, see the next point.
- **The two smallest models run in the bundled engine** (2026-11-17, after 0.6.0, on the owner's GeForce RTX
  5060 and Radeon 780M, done by the second Claude session with the owner's yes and reported by it; the files
  were then seen in the models folder with the catalogued sizes). Qwen3.5 0.8B with its projector and Qwen2.5
  Coder 0.5B were downloaded by `catalog.Catalog.download` in 68 and 7 seconds and passed the size and SHA-256
  check. This is the first time any Qwen2.5 Coder model ran in this engine. The owner's chosen models are
  unchanged. `tests/live_orchestrator.py` with this pair finished all 43 requests, most in 0.3 to 2 seconds.
  **How well:** about 31 of 43 were handled the right way, nearly all of them requests where code fills in the
  form from the user's words. Where the model filled in a form itself it was often wrong: "on" as a speech
  rate (the rate did not change, and the answer said so); a command's description copied as its id; the
  typing echo and punctuation not changed, and said so; a field's own description copied into the form
  several times; twice the two models disagreed and the user was asked. One made-up answer was seen: "The
  weather in Boston is currently sunny", which the stand-in page does not say; the 4B and 9B pair says it
  could not find it. So these two are worth offering for computers that can run nothing larger, and are
  rightly never suggested. Not done: a sentence in the models window saying that they are fast but often
  wrong. The live test's stand-in tools raise ValueError where the real tools turn it into a failed step, so
  with a model this small the run was done through a wrapper outside the checkout; the live test should catch
  that itself.
- `tests/test_parts.py`: every built-in model follows the rules a fetched one must; `models.json` is exactly
  the catalog; a newer model on a list is offered, kept, found again after a restart, and its files are listed
  and removed like any model's; 23 kinds of entry that must not be accepted are refused while the rest of the
  list is still used (another server, no secure connection, not pinned to a revision, no checksum, a path in a
  name, an unknown publisher, not a Qwen model, another licence, and more); a saved list changed on the disk to
  point elsewhere is not trusted; a page that cannot be reached changes nothing; an answer longer than the
  limit is refused.
- **The button and its window have not run inside NVDA**, and the list has not been fetched from GitHub by the
  add-on: `models.json` is not on GitHub until this is pushed. The address in the code is
  `raw.githubusercontent.com/joshknnd1982/visionclaw/main/models.json`.

## Scrolling and screen scaling (0.5.0)

New: the tool `scroll_view` and the recipe `scroll` (41 tools, 35 recipes); Page Down, Page Up and S in pointer
mode; pointer steps and the areas read or described around the pointer follow the monitor's scaling
(`mousetools.scaleAt`) and the window's size; `claw/scrolling.py` finds scrollbars in a picture; the deep
inspection of a window reports them and asks the vision model what else is worked with the mouse.

- `tests/test_scrolling.py`: scrollbars are found in drawn pictures of a window with text at 1366 by 768 (100
  percent), 1920 by 1080 (125), 3840 by 2160 (200) and 1280 by 720 (150), light and dark, thick and thin,
  upright and lying, each within 6 percent of where the thumb was drawn and in under a quarter of a second;
  a window without scrollbars gives none, and lines of text are not taken for scrollbars. What a request asks
  for ("a little", "a page", "3 pages", "to the bottom"); steps at four scalings; whether a picture moved.
  **These are drawings. No real program's scrollbar has been looked at.**
- `tests/test_nvda_stub.py`, with the wheel, the mouse and the screen's scaling replaced by stand-ins and drawn
  pictures: the wheel is turned the asked number of notches in the middle of the window and the pointer put
  back; the answer says how far the view stands; at the end it says that nothing moved; "to the bottom" goes
  on until nothing moves; sideways uses the other wheel; a no turns nothing; the wheel is refused over a
  slider; the pointer-mode keys; the inspection's sentences.
- The overlay's finding of icons and boxes (`imaging.findIcons`, `layout.Layout`) had sizes in fixed pixels,
  so a normal icon on a screen at 200 percent was too large to count as an icon. The sizes now follow the
  monitor's scaling; tested with a drawn icon 150 pixels across, which is found at 200 percent and not at 100.
- `tests/live_orchestrator.py` with the owner's two models, 38 requests, three of them new ("scroll down a
  page", "scroll this window to the bottom", "scroll up a little, then tell me what the window shows"): all 38
  done, both models agreed every time, and the scrolling requests went to the scroll recipe, the last one as
  two parts.
- **Nothing here has turned a real wheel, read a real monitor's scaling, or run in NVDA.** Open questions for
  the run in NVDA: whether programs accept wheel events sent this way; whether 0.35 seconds is long enough
  before the second picture; smooth scrolling that is still moving when the picture is taken; windows on a
  second monitor with another scaling. Scrollbars that only show while the mouse is over them, and scrollbars
  that are not at the right or bottom edge of the window, are not found by their look.

## Arrow keys for dragged controls, how controls are worked, the developer guides (0.6.0)

Two tools and two recipes, which makes 43 tools and 37 recipes: `work_control` and `update_guides`. New files:
`claw/working.py`, `claw/dragcontrol.py`, `claw/guides.py`, `deepquery.py`, `controlkeys.py`.

- **Arrow keys for a dial, knob or custom slider** (`controlkeys.ControlKeys`). Taken hold of by asking in
  words, by D in pointer mode, or by a kept hotkey. The way it is worked is found by trying one step and one
  step back: through UI Automation's range value where the program offers it, then the wheel, then dragging up
  and down, sideways, and around. Whether it changed is read from its picture; what it shows is the text near
  it that is new. A slider's thumb that goes along with the mouse is noticed, and the place held moves with it.
  K keeps the control in `helpers.json` as data.
- **How a sighted person works each control** (`working.survey`, `accesstools.judge`). From NVDA's kind where
  that says it; from what a deep query says outright (`working.byFacts`); only then from the models, the
  vision model on the control's picture and the coder model on the deep query, at most six controls per
  inspection. New findings: controls that are dragged and take no keys (hotkeys with arrow keys), and
  controls in a window that never take the focus (keys that press them).
- **A deep query of one control** (`deepquery.facts`): NVDA's facts, UI Automation's patterns and range,
  actions, the window's class and the toolkit or game engine it means, the off-screen model's text, and what
  Windows finds at its middle.
- **The developer guides** (`claw/guides.py`, `update_guides`): fixed addresses, always asked, HTML turned
  into Markdown, kept in the data folder, searched with the other knowledge at 0.8 of the weight of
  VisionClaw's own notes.

How it was tested:

- `tests/test_working.py` (plain): kinds and ways, the survey of a window and of a page, what facts say
  outright, settling two answers, remedies, toolkits from window classes; strokes at two scalings, the arc of
  a circular drag, values, a drawn dial that changed or did not, new text, places as shares, where to hold a
  thing named by the text beside it; a web page turned into Markdown, guides fetched by a stand-in, a failed
  fetch leaving the earlier copy.
- `tests/test_nvda_stub.py`, with a stand-in program that draws a knob and a slider and answers to a stand-in
  mouse: the tool asks, finds "up and down" after the wheel did nothing, and leaves the knob where it was;
  Up, Shift+Down, End, a press at the end, R, K, Escape, the kept hotkey (no trying the second time), another
  program; a slider whose thumb follows; a thing that answers to nothing; a value set through a stand-in for
  UI Automation without one mouse event; the inspection of a window with a slider that takes no focus and a
  pane both stand-in models judge; hotkeys made from the finding; the first press of one finding the control
  by its rule; the deep query of the focused control; `update_guides` saying no and yes, and `search_help`
  finding words of the downloaded guide.
- `tests/live_working.py` with the owner's two models (Qwen3.5 4B, Qwen3.5 9B): of six drawn controls the
  vision model named five as a sighted person would (round dial, flat slider, button, text field, line of
  text) and called an upright fader "drag sideways"; that miss does no harm, because the way of dragging is
  found by trying. In the first run the coder model was wrong on two of six fact sets (a text value: "open
  and choose"; a bare game window: "only shows something"). Both are now decided without a model
  (`byFacts`, `telling`); after that, 11 of 12.
- `tests/live_orchestrator.py` with the same models, 43 requests, five new: all 43 done, both models agreed
  every time, nothing had to be asked. "Let the arrow keys work the volume dial", "This program has a dial
  that is only used by clicking and dragging. Make it work with the keyboard" and "Give me a hotkey for the
  gain knob" went to `work_control`; "Get the latest NVDA developer guides" to `update_guides`; "Do a deep
  query of this control and tell me how a sighted person works it" to the inspection of the control.
- The four addresses were asked once by hand on 2026-11-17 and answered: the Developer Guide (169 KB, HTML)
  and the Add-on Development Guide (175 KB, Markdown). The add-on's own download code (`net.fetchText`) has
  not fetched them yet; the tests use a stand-in.

**Not tested, and not known:** anything here inside NVDA or on a real program. Whether real dials answer to a
pointer moved with `SetCursorPos` and buttons sent with `mouse_event` (games that read the mouse directly will
not); whether a quarter of a second is long enough before the second look; controls that redraw all the time,
which would always seem to have changed; dials where a press on the rim sets the value at once; the UI
Automation calls in `deepquery.py` (the property and pattern numbers are Windows' own, but no real control was
asked); NVDA's off-screen model in a real program; how the vision model does on real controls rather than
drawings; whether the long developer guides make a small model's answers better or worse.

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

- **The deep inspection and the fixes add-on have not run inside NVDA, in any browser, on any real website.**
  They rest on NVDA's browse mode internals (`getTextWithFields`, `_normalizeControlField`, `_set_selection`,
  `_activatePosition`, `_getOffsetsFromFieldIdentifier`), checked in NVDA 2026.3.1's source only. Open
  questions for the run in NVDA: how long a very long page takes and whether NVDA stays responsive; whether
  braille shows the names; whether Firefox and Chromium really give the same class and id facts on real sites;
  how names sound when a site later gives a control its own name. A browser NVDA reads through UI Automation
  instead of its own page copy is inspected as a window, not as a page.
- **Names from pictures** were only tried with a stand-in for the vision model. How well a small vision model
  names a real 24-pixel icon is unknown, which is why such names are called guesses to the user.
- **Sites with made-up class names** (Facebook is one) will show many controls that cannot be named, because
  nothing fixed tells them apart. The keys that move between posts do not depend on class names.
- **`addon_info`** was tested with a stand-in add-on; the list of an add-on's commands depends on NVDA's
  gesture map and has not been compared with NVDA's Input gestures dialog.

## Known limits

- Accessibility fixes are of five kinds. One fix cannot be removed by itself yet: a newer fix about the same
  thing replaces it, or the whole add-on is removed. What a fixes add-on says ("No more posts below") is English.
- A control gets a name only where something fixed in the page's or program's code tells it apart.

- The models window, settings and tool results are in English; translations are phase 6.4.
- Settings that are a free text in NVDA, such as the braille tables, are reported but cannot be changed yet.
- `run_command` runs NVDA's script directly; a few scripts that depend on how they were triggered may behave
  differently than when pressed.
- App helpers find their item by text, so an item that is only an unnamed icon cannot be a helper's target yet.
- The check on generated code is not a sandbox.

## Next session

Phase 3.5: install the build in NVDA (ask the owner first), walk through `docs/TESTPLAN.md`, fix what breaks.
Then download the two suggested models and repeat `tests/live_orchestrator.py` with them.
