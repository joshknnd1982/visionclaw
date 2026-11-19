# VisionClaw status

Updated 2026-11-19, version 1.11.1.

## What exists

Everything in phases 1 to 3.4 and 4.1 of `CLAUDE.md`: the fork, the model catalog and models window, the
graphics choice with fallback, the two-model runtime, the planner with recipes, agreement between the models,
the step runner, 53 NVDA tools and 47 recipes, the Ask VisionClaw window, app helpers, generated add-ons, the
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
  rightly never suggested. That run was done through a wrapper outside the checkout, because the live test's
  stand-in tools raised ValueError where the real tools turn it into a failed step.
- What was done about it is under "One small question at a time" below (0.7.0).
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

## One small question at a time; forms narrowed to what was found (0.7.0)

The owner asked that the very smallest models be fed and asked in very small steps. New: `claw/shapes.py`,
`agent.fillOneByOne`, `orchestrator._quoted`, `policy.stepwise`, the setting `oneAtATime` (Automatic, Always,
Never) with its choice in the settings panel.

- **For every model:** where the step before found the possible answers, the form allows nothing else: the
  ids of found settings and commands, the names of listed items, on or off, a setting's options, a number
  (`shapes.shapes`, `Tool.schema(skip, shapes)`). A list that is not whole narrows nothing.
- **What the user's own words say is filled in by code** (`shapes.said`): "to all", "turn off", "a little
  faster" (+10), "much slower" (-25), "to 70", an item named in full, both ends of a drag.
- **For a lead model that is never suggested** (Qwen3.5 0.8B): one field per call, each answer narrowing the
  next; an answer that repeats the question is asked for once more and then replaced by the user's words;
  looked-up information is answered with a line of it, word for word, found by plain code and at most chosen
  among by the model; if nothing found mentions what was asked, that is said.

How it was tested:

- `tests/test_shapes.py` (plain, scripted stand-in for the model): what results allow; lists that are cut or
  not whole; the form given to the engine; one field per call with the second narrowed by the first; code
  filling in what the words say; an answer that repeats the question; quoted answers; when the mode is used.
- A first try with the real 0.8B model: asked one question with a fixed list or a number pattern, it gave the
  right value, command id and on or off, twice each. Asked which of three lines answers a question that none
  answers, with 0 allowed for "none", it chose line 1 both times, and so did the 0.5B coder model. **A very
  small model cannot say "none of these."** So plain code decides whether anything fits.
- `tests/live_orchestrator.py` with **Qwen3.5 0.8B and Qwen2.5 Coder 0.5B**, 43 requests, every answer read.
  Before any of this, the second session counted about 31 of 43 handled the right way. With narrowing only
  (the setting on Never), by my count 34: wrong were the speech rate (set to 100), the made-up weather
  answer, the add-on's name, the item of four fixes, and the item of two dial requests. With the finished
  mode, 41: the rate went from 50 to 60, punctuation to all, the weather answer is "What was looked up does
  not mention weather or boston", the add-on and the dials are named rightly, a drag has both its ends.
  Still wrong: "tell me when the inbox count changes" names "5 posts" as the thing to watch, and "make
  NVDA+alt+P press the Play button" gives the whole sentence as the item, which the real tool would answer
  with "nothing of that name". Twice the two models disagreed on the recipe and the user was asked, as before.
  It took 39 seconds for all 43, against 38.
- The same with the owner's **Qwen3.5 4B and Qwen3.5 9B** (the mode is off for them; narrowing and the code
  filling are on): all 43 done, nothing asked, no failed form at all where the 0.6.0 run had four, both items
  that were written as ", " in 0.6.0 are now right ("Search edit field", "New Game button"), the three
  answers I compared are the same or shorter, and it took 160 seconds against 173.
- In the models window the two smallest models now end with "very small: fast, less accurate", and the
  welcome text says they are asked one small question at a time (`dialogs.ModelsDialog._label`; checked
  against the stand-ins, the window not opened in NVDA). The live test turns a stand-in's ValueError into a
  failed step itself (`LiveRegistry`). Both by the second session.

**Not tested:** any of it inside NVDA. The real tools give the same result lines as the stand-ins
(`_findSettings`, `findCommand`, `listItems`), but no real list of settings, commands or window items has
gone through the narrowing; the new choice in the settings panel has not been opened; the Qwen3.5 2B and
Qwen2.5 Coder 1.5B pair, which is the suggested one, was not run because it is not on this computer; the
setting on Always with larger models was not measured. Quoted answers are only as good as the lines that
were looked up: a question asked in other words than the page uses gets "does not mention".

## A newer version of VisionClaw (0.8.0)

The owner asked for it on 2026-11-17: VisionClaw looks for a newer version of itself on GitHub and gets it,
when asked (NVDA+Alt+U, a button in the settings, the tool `check_update` with the recipe `update_visionclaw`)
or, if the user turns it on, when NVDA starts, at most once a day. `claw/updates.py` decides from GitHub's list
of releases whether a newer version exists and which one file may be downloaded; `updater.py` asks, downloads
with `net.download`, and opens the file so that NVDA installs it.

- `tests/test_updates.py`: the highest version wins, compared as numbers (0.10.0 over 0.9.0); pre-releases
  count; the version in use or a lower one is never offered; 17 kinds of release that must be passed over are
  (a draft, a tag that is not a version, the fixed-name copy alone, a file of another version, another server,
  another repository, another release, no secure connection, no checksum, no size, and more); when the list
  is read by itself; what is said.
- `tests/test_nvda_stub.py`, with GitHub, the download and the installer replaced by stand-ins: a request in
  words asks before going online, and a no reads nothing; the newest version is said to be the newest; a
  newer one is offered with what is new, "not now" downloads nothing, yes downloads the release's own file
  with its size and checksum and hands it to NVDA; a file Windows cannot open is named with its place; a page
  that cannot be reached fails with the reason. The key: a window, a question, a download after yes. By
  itself: nothing is scheduled with "only when I ask"; with the automatic choice one sentence is spoken, no
  window opens, nothing is downloaded, and the list is not read twice in a day.
- **Against the real GitHub, read-only, with plain Python:** the list of this repository's 11 releases was
  read with `net.fetchJson`; for version 0.6.0 the code found 0.7.0 with the right file, size and SHA-256, and
  for 0.7.0 nothing newer. All releases so far are pre-releases, so GitHub's "latest release" address answers
  404; that is why the whole list is read.
- `tests/live_orchestrator.py` with the owner's Qwen3.5 4B and 9B, 45 requests: all done, both models agreed
  every time. "Check for a new version of VisionClaw" and "Is VisionClaw up to date?" went to the new recipe,
  and "Get the latest NVDA developer guides" still went to the guides.
- **After 0.8.0 was published, against the real release, with plain Python:** seen from version 0.7.0 the
  code found 0.8.0, and `net.download` fetched `VisionClaw-0.8.0.nvda-addon` through GitHub's redirect in about
  a second and verified its size and SHA-256; the file is byte for byte the one built here. Seen from 0.8.0,
  nothing newer is offered. What is read out as new is the part under the release's "New in" heading.
- **Inside NVDA 2026.3.1, by the owner, on 2026-11-17, with 0.8.0 installed** (the built file was opened
  for him from this computer, NVDA asked to install it, and he installed it): he was given two things to try
  and reported "all two tests pass. nothing went wrong." They were: NVDA+Alt+U, which should say that it is
  looking and then show a window saying that 0.8.0 is the newest version; and the setting "Look for a newer
  version of VisionClaw", which should stand on "Only when I ask". He gave no more detail, and NVDA's logging
  is off, so there is no log. That 0.8.0 loads in NVDA, with the new settings choice in the panel, follows
  from it. The other case, a newer version being offered, downloaded and installed from inside NVDA, cannot
  be tried until a release after 0.8.0 exists.
- **Not tested inside NVDA:** a newer version being offered; whether opening the downloaded file makes NVDA ask to install it
  (it relies on Windows knowing `.nvda-addon` files, which an installed NVDA sets up and a portable one does
  not), the window and the spoken sentence, and the settings panel's new choice and button.
- What the SHA-256 shows: it comes from GitHub like the file, so it shows the file arrived whole, not who
  made it. Anyone who can publish a release in the repository decides what users are offered.

## Five tests of what 0.6.0 added, inside NVDA (2026-11-17, NVDA 2026.3.1, with 0.8.0 installed)

The owner was given five things to try: (1) "let the arrow keys work the ... dial" in a program with a dial or
custom slider, then Up, Down, End, R, K, Escape; (2) pointer mode, the pointer on a slider, D; (3) "do a deep
inspection of this window" in a program with custom controls; (4) "do a deep query of this control"; (5) "get
the latest NVDA developer guides", then a question about binding a gesture to a script.

- **His report:** "yes they are there. so all five of your questions now pass." He said this after asking
  where the guides are kept and finding them. He named no program and did not say what was spoken, and NVDA's
  logging is off, so tests 1 to 4 rest on his word alone. An earlier "all five pass", about a minute after
  NVDA had restarted with 0.6.0 and before anything a run leaves behind was on the disk, was not recorded.
- **Confirmed by what is on the disk:** the download of test 5. `guides` in VisionClaw's data folder was
  written at 16:47, a minute after 0.8.0 was installed: the NVDA Developer Guide, 109,742 bytes of Markdown in
  79 sections, and the NVDA Add-on Development Guide, 173,781 bytes in 119 sections. This is the first time
  `net.fetchText`, `guides.update` and the turning of NV Access's real page into Markdown ran for real.
- **Not confirmed, and the disk speaks against it:** K in test 1. There is no `helpers.json` in the data
  folder, so no control has been kept under a hotkey: K was not pressed, or it kept nothing. Not ticked.
- **Not known:** which way a real dial turned out to be worked; whether what was said after a key press
  matched the program; what the models said about a real control; whether the answer to the question about
  gestures used words from the guides.

## One model for both jobs is no longer called two (0.8.1)

The owner reported that VisionClaw said two models were agreeing when only one model was installed. Seen on
his computer on 2026-11-17: one model is stored, Qwen3.5 9B with its projector (6.15 GB), and the settings
choose it for vision (`qwen3.5-9b`) and for code (`qwen3.5-9b-coder`). Both entries are the same file, and one
engine serves both jobs (`runtime._slot`). The agreement step still asked "both" for a choice, which was the
same model answering the same question twice at temperature 0, and reported "The two models are agreeing on
what to do" and "Both models agree on the plan".

What changed: `runtime.oneModel()` says whether one model file serves both jobs, and the orchestrator carries
that in `params.oneModel`. Then the recipe for a part is chosen once; a plan the model wrote itself is still
checked with the reviewer's question, by the same model, and said so ("The model checked its plan"); when it
keeps finding a problem the user chooses between its plans. The hint for a stuck step, the check of the result,
the second reading of generated code, the question about a doubt, and the inspection's judgement of controls
all say "the model". With two different models every sentence and every call is as before.

- **With plain Python:** `tests/test_one_model.py` (new; twelve test files pass). With the real catalog's
  entries the runtime reports one model for 9B with 9B, and two for 9B with another coder or with a model
  missing. Whole requests with a scripted model: the choice is asked once, and no sentence that is logged or
  put to the user contains "models", "agree", or "vision", "coder", "other" or "reviewing model"; a plan with a
  problem is corrected; a plan that stays doubtful is put to the user. With two models the old sentences are
  still there. `tests/test_nvda_stub.py` runs the inspection with one model and finds "says the model, from
  the picture and from what is reported".
- **Against the owner's real models folder, read-only:** the real catalog lists one stored model serving both
  roles, and the real runtime with his two settings reports one model for both jobs.
- **Not done:** no run with the real model. No prompt, recipe or form was changed, only which calls are made
  and what is said, and NVDA was running with the 9B model loaded, so a second copy was not started beside it.
  **Not tried inside NVDA.**

## A wrong answer about the installed model, and what was done about it (0.8.2)

The owner asked VisionClaw "what model is installed" and got a list of add-ons. Reproduced on his computer
with his model, Qwen3.5 9B for both jobs, in the bundled engine with the live test's stand-in tools: the model
chose the recipe `nvda_info` three times out of three for "what model is installed" and "which model are you
using". There was no recipe for VisionClaw's own models, so it took the nearest. In NVDA the answer is then
quoted from what `nvda_info` found, and the line "Add-ons installed" has the word "installed" in it.

What changed:
1. **A recipe and a tool for it**: `visionclaw_models` and `model_info`. The answer is written by plain code
   (`runtime.aboutText`) from the settings and the disk: which model does which job, what is stored and how
   big, a download that was not finished, and where a loaded model runs. It is said as it is, never rephrased.
2. **A check of the one model's choice** (`consensus._onRecipe`): where the user's own words point to another
   recipe (`planner.hint`), the model is told so and chooses again; if it still differs, the user is asked
   which of the two is meant. Measured first: in 55 parts of 48 requests the 9B model went against the words
   twice, was wrong both times, and kept its choice both times when only asked to look again. So its second
   answer does not stand alone.
3. **Add-ons**: "Which add-ons do I have?" was one of those two; the model took it for the add-ons VisionClaw
   wrote. The two recipes' descriptions now say which is which, the words "what add-ons did VisionClaw write"
   point to the right one, and add-on, add on and addon are one word when a looked-up line is matched.
4. **One model is loaded once** (`runtime.ensure`): its engine was started with the vision job's context size
   and started again, model and all, when the coder job first came up. The owner had reported an answer that
   took 40 seconds or more. Whether this was the cause there is not known: NVDA's log is off, the model had
   been unloaded, and the tests described here were using his graphics card at about that time.
5. Two parts of a request that get the same answer say it once.

- **With plain Python:** twelve test files pass. New cases in `tests/test_one_model.py` (the second look, the
  question to the user and its three answers, the answer said once, `aboutText` for one model, two, none, a
  loaded one and an unfinished download), in `tests/test_runtime.py` (one start for both jobs),
  `tests/test_core.py` (which words point to the new recipe and which must not), `tests/test_shapes.py` and
  `tests/test_nvda_stub.py` (45 tools; the real tool with no model stored).
- **With the real model, Qwen3.5 9B for both jobs, one question at a time, on the GeForce RTX 5060:**
  `tests/live_orchestrator.py`, now 49 requests. All 49 were carried out, every answer was read. Against the
  run before these changes every choice is the same except the two that were wrong. "What model is
  installed?" and "Which AI model are you using?" give the answer about the model in half a second; "Which
  add-ons do I have?" and "what addons do i have" give NVDA's add-ons. The user was asked once in the 49: for
  the second half of "Do a deep query of this control and tell me how a sighted person works it", where the
  first choice offered is the right one. The whole run took 91 seconds, the slowest request 10; before the
  change to loading it was 246 seconds for 48 requests, the slowest 38. That is not a clean comparison: at
  about the time of the earlier run the owner was using VisionClaw in NVDA with the same model, so two
  copies may have shared the computer. That one start now serves both jobs is shown by `test_runtime.py`.
  This is also the first run of the one-model wording of 0.8.1 with the real model: "The model is choosing
  what to do", "The plan is ready".
- **Not tested:** two different models with the new recipe (only one model is stored on this computer). The
  very small models. **Nothing inside NVDA**: the real `model_info` there, with its sentence about where the
  model runs, and how long the first request now takes.

## Three tests inside NVDA with 0.8.2 (2026-11-17, NVDA 2026.3.1)

The owner was given three things to try after installing 0.8.2: (1) "What model is installed?", which should
name Qwen3.5 9B, say that it does both jobs, give 6.1 GB and mention NVDA+Alt+M, with no list of add-ons;
(2) "Which add-ons do I have?", which should list NVDA's add-ons; (3) any request twice in a row, and roughly
how long each took.

- **His report:** "all three tests now pass. It is faster when answering too." He did not say what was spoken,
  gave no seconds, and NVDA's logging is off, so this rests on his word. He uses one model, Qwen3.5 9B, for
  both jobs, with "one small question at a time" set to Always.
- **Confirmed by what is on the disk:** 0.8.2 is the version installed in NVDA; its manifest there was written
  at 18:32.
- **What this shows:** the real `model_info` and `nvda_info` tools run in NVDA and answer the two questions
  that had gone wrong, and 0.8.2 loads. Since 0.8.2 includes 0.8.1, the one-model path ran in NVDA too.
- **Not known:** whether "faster" comes from the model being loaded once, or from his earlier slow request
  having shared the computer with the tests here. Whether the Last task box now says "The model is choosing
  what to do" and nothing of two models was not asked and not reported. The question that is put when the
  model and the words differ has not come up in NVDA.

## A command that failed in real use, and what 0.9.0 does about it (2026-11-17)

In NVDA the owner asked "ask nvda to give me the current time and then the date", with Qwen3.5 9B for both
jobs and "one small question at a time" set to Always. He pasted what the Last task box showed. It ended with
"VisionClaw ran into a problem: AttributeError: 'NoneType' object has no attribute 'wasInSayAll'".

**The cause, found by reading the pasted run and NVDA 2026.3.1's source** (`scriptHandler.py`,
`keyboardHandler.py`, `inputCore.py`, `globalCommands.py`, downloaded from NV Access's repository at the tag
`release-2026.3.1`):

1. The search for the command counted shared words. "Current" is in dozens of command descriptions, and
   "pressed three times" was read as the word "time". So the status bar command scored as high as the clock,
   came first, and the model took it.
2. VisionClaw made the key press for a command from the key as NVDA shows it to the user. NVDA shows
   "NVDA+ctrl+down arrow" and only knows the key by the name "control", so no key press could be made.
3. It then called `scriptHandler.executeScript(script, None)`. NVDA's first line there asks the key press
   whether it came during say all (`willSayAllResume`), and None cannot answer.
4. The error was not a tool's "could not do it" but a fault, and a fault ended the whole request. The date was
   never tried. Nothing was written anywhere, because NVDA's log was off.

**What was changed:**

- Commands are ranked by the word that tells them apart (`claw/ranking.py`, `claw/commands.py`): a word counts
  for more the fewer commands have it, and more again in a command's own name; words that only say how often
  to press are taken out first; what is far from the best is not offered. When nothing fits, plain code says so.
- The key press is made from the way NVDA writes the key; a command without a key, or whose key cannot be
  made, gets a stand-in built on NVDA's own `InputGesture` (`nvdatools.keyGesture`, `noKeyGesture`).
- A second or third press: what it does is read from the command's own description, and the user's words
  decide how often the key is pressed (`commands.presses`). The date is two presses of NVDA+F12.
- Commands without a description, which NVDA lists nowhere, are found and run after the described ones.
- A fault inside a tool ends its step with a sentence and the rest of the request goes on (`Registry.call`).
- VisionClaw has its own log, `%APPDATA%\nvda\visionClaw\logs\visionclaw.log`, written whatever NVDA's logging
  level is, with a setting (Detailed, Brief, Off; Detailed by default), a button and the request "open the
  VisionClaw log". It is kept under 2 MB, with three older files beside it, and is sent nowhere.

**Also in 0.9.0, asked for by the owner in the same sitting:**

- *"VisionClaw must be able to query and give info from every single NVDA command, function and object, known
  or unknown."* `find_nvda` and `inspect_nvda` search and look at everything in the loaded modules of the
  running NVDA and its add-ons (`claw/inside.py`); a function that only reports and needs nothing is called
  to say what it gives back now, nothing else is called. `object_info` reads every fact of the focused
  control, the navigator object, the window, what is under the mouse, the desktop or the focus's parent, and
  any other property by its name.
- *"Do a full audit of all NVDA commands, objects, functions, including how it interacts with TTS engines and
  braille displays."* Done twice over. (1) NVDA 2026.3.1's source was audited without running it
  (`tools/audit_nvda_source.py`): 609 modules, 1,815 classes, 1,573 functions outside classes, 6,907 methods,
  509 commands of which 318 have a description (267 in globalCommands, 242 elsewhere), 6 speech synthesizer
  drivers, 24 braille display drivers, 38 extension points. From that and from reading `synthDriverHandler`,
  `speech`, `braille`, `driverHandler`, `bdDetect` and `brailleTables`, the notes
  `claw/knowledge/nvda-inside.md` were written, 15 short sections the models search like the user guide.
  (2) The tool `audit_nvda` does the same on the user's running NVDA, with their add-ons and drivers, and
  saves `nvda-audit.md`.
- *"Remove this restriction if possible"*, about the reply "I can only answer questions about this image" in
  the description window. Removed: every question goes to the vision model with the picture
  (`followup.ANSWER`), and one model call is made instead of two.

**Tested, and how:**

- `tests/test_commands.py`, plain Python, against `tests/nvda_commands.json`, the 265 described commands of
  NVDA 2026.3.1's `globalCommands.py` taken from its source: both parts of the failed request find the clock
  and nothing else; the time is one press, the date two, both together one and two; 16 other requests find
  their command first or among the first three; a request with no command finds nothing; the log's levels,
  rotation, errors with the place in the code, and that it never raises; the list of what is inside, from
  stand-in modules; a fault inside a tool.
- `tests/test_nvda_stub.py`: **the failed request replayed whole**, through the real orchestrator and the
  real tools, against stand-ins that behave like NVDA 2026.3.1 in the three places that mattered (the command
  list, a key press that cannot be made from "ctrl", and `executeScript` asking the key press first). The
  answer is "NVDA said: 10:42. Next time you can press NVDA+f12 for this. NVDA said: Tuesday, November 17,
  2026. Next time you can press NVDA+f12 twice for this." Also: the status bar command now runs; a command
  without a key runs; a command without a description is found and run; a fault becomes a failed step and is
  in the log with the file and line; `inspect_nvda` never calls a function that changes something;
  `object_info` with all facts, one fact, and a property it has no name for; the audit file; the log opened
  only when asked; three questions about a picture, each answered with one model call.
- `tests/live_orchestrator.py` with the owner's own setup: Qwen3.5 9B for both jobs on the GeForce RTX 5060,
  one small question at a time set to Always, 60 requests of which 11 are new, run twice, every answer read.
  All 60 were carried out, in 0.4 to 11.5 seconds, 112 seconds in all. The failed request took 11.4 seconds
  and gave the time and the date. The first run showed two things, both fixed before the second: the wording
  of the new "facts about a control" choice drew "how many cells does it have" away from the braille report,
  so the user was asked; and "how do I read the title" lost its keys when only one command was found. In the
  second run the user was asked once, for "do a deep query of this control and tell me how a sighted person
  works it", the same request as in 0.8.2. The command stand-ins of the live test now search the same 265
  real commands.

**Not tested, and what that means:**

- **None of 0.9.0 has run inside NVDA.** The stand-ins were written from NVDA's source, which shows what NVDA
  should do. Open: whether the two quick presses are counted as a double press on a slow computer (NVDA's
  limit is the keyboard setting "multi press timeout", 500 ms by default, and the presses follow each other
  at once); whether the first press's speech is cut cleanly before the date is spoken; whether the stand-in
  for a key press is accepted by every command (it is built the way NVDA's own classes are, and has not been
  made by a real NVDA yet).
- **Commands without a description** are often plain key handlers of the focused control (the arrow keys in
  an edit field). They are only offered when no described command fits, but running one has not been tried.
- **`find_nvda` in a real NVDA**: how long the first listing takes (several hundred modules), how much memory
  it holds, and whether every module can be gone through from a background thread without trouble, are
  unknown. It is made once and again only when modules were loaded since.
- **`inspect_nvda` calls reporting functions on NVDA's main thread.** A function named get..., is... or has...
  that is slow would hold NVDA up for that long; none is known.
- **Questions about pictures** were tested with a stand-in for the engine. How well a small vision model keeps
  to "say that it is not in the picture" is not measured; the owner's 9B model is the one to try it with.
- **The notes on speech and braille** describe NVDA's own code. Synthesizers and displays that add-ons bring
  follow the same base classes; nothing was tried with a real braille display.

## A question answered off the point in real use, and what 0.10.0 does about it (2026-11-17)

In NVDA the owner asked "How can I use the keyboard to navigate my desktop?", with Qwen3.5 9B for both jobs
and one small question at a time. The answer was "toggleKeyboardLayout: Toggles between desktop and laptop
keyboard layout. Keys: no key assigned." The owner asked that VisionClaw always query NVDA, then the program,
the window and Windows itself before it answers, that an answer always be about the question, and that
VisionClaw be more intelligent and more aware of where the user is.

What was wrong, read from the transcript and reproduced against all 265 commands of NVDA 2026.3.1:
1. A "how do I" question was planned as `find_command` alone. Nothing but NVDA's commands was ever asked, so
   a question about Windows or about the program in front could not be answered at all.
2. Among the commands, the one that shares "keyboard" and "desktop" with the question was the best match.
   "Keyboard" says how, not what; it counted as much as "desktop".
3. Nothing checked that what was found was about the question, and with one small question at a time the
   found line is the answer.

What 0.10.0 does:
- **One step, `look_up`, asks four places, always, in this order** (`asktools.py`): NVDA (the commands that
  work where the user is, the whole user guide as it is on the computer, the help of the installed add-ons,
  VisionClaw's notes); the program in front (name, product, version, NVDA's commands for it, the hotkeys
  VisionClaw made for it); its window (title, the control with the focus with value, states, place in its
  group, own key, description and what it is inside of, the status bar, and up to 40 controls that have a key
  of their own, found in at most 0.4 seconds); Windows (version, the titles of the open windows, and 34 short
  notes on the keys of Windows). Three lines in the Last task box say what was asked.
- **Plain code decides what is about the question** (`claw/lookup.py`): every source gives passages of about
  340 characters; all are ranked together by the words the question names, a rare word counting for more and a
  word in a heading for more again; words that only ask or only say "with the keyboard" count for a twentieth;
  a passage must cover 45 percent of what is named and score 75 percent of the best; the best of each source
  is kept before a second from the same. Among equals the order is NVDA, program, window, Windows.
- A written-out key ("what does NVDA+T do") finds what that key does. "What is" and "how do I use" get the
  start of the section that explains the thing, before any command. "This program", "here" and "focused" bring
  in where the user is; a question that names nothing else is answered with that alone.
- **Nothing found is said by plain code**, as a sentence that names what was asked, and is given to the user as
  it is. No model is asked to put nothing into words, and the step does not count as failed.
- The recipes `explain_keys` and `nvda_question` are now `look_up`. A question that fits no other hint is
  hinted as a question, so it is looked up and not planned freely.
- The model that answers is shown the pieces numbered, each saying where it is from, and is told to use the
  ones about the question and never to join steps from two pieces.
- NVDA's user guide is read with its tables: heading rows ("Name, Desktop key, Laptop key") are left out, which
  alone made half the guide look as if it were about the desktop, and each other row is a sentence, so a
  command stays with its keys. The title page and table of contents are left out.
- **The notes on Windows** (`claw/knowledge/windows-keyboard.md`) were written from Microsoft's page "Keyboard
  shortcuts in Windows" (support.microsoft.com), read on 2026-11-17 through Microsoft's own documentation
  service, for Windows 11 and 10; Control+S and Control+O from Microsoft Learn, "Moving from Mac to Windows".
  Not on those pages, and written from common knowledge: that the arrow keys move between icons, that typing
  first letters jumps, that Enter opens, that Space presses a button, and the Applications key.
- **What is new in a newer version** is shown in a read-only edit box, one point to a line, with the buttons
  Download and install, and Not now (`updater.UpdateDialog`, `updates.offerText`), from the key, the button
  and the request in words alike. The owner asked for this on the same day.

Tested, and how:
- **`tests/test_lookup.py`, plain code**, against every NVDA command, VisionClaw's real notes and a stand-in
  page of help: the question that went wrong gives the desktop section of the Windows notes and not the
  layout command; NVDA answers what is NVDA's (the title, the current line, the time, say all, the NVDA menu);
  Windows answers eleven everyday questions (switching windows, the Start menu, renaming, the system tray,
  locking, the taskbar, minimizing, saving, selecting text, closing, shutting down); copying text gives NVDA's
  and Windows' answers, NVDA's first; three "what is" questions give explanations; written-out keys; "here"
  and "this program"; a window's own controls with their keys; the order among equals; nothing found for
  three questions; developer notes kept out of a user's question; word endings; the coverage rule; the hints;
  and the whole request through the orchestrator with a scripted model, for the quoted answer, the answer in
  the model's words, and nothing found.
- **`tests/test_nvda_stub.py`**, the real tool through the real registry against stand-ins for NVDA: a replay
  of the owner's question with the layout command among NVDA's commands, the three "Asked" lines, a command
  with its key, the user guide read from a file with a table, where the user is on a stand-in desktop
  (program, version, window, focused icon, 1 of 12, what it is inside of), a control's own key, the open
  windows, nothing found, and the whole request as in the real run. The window that says what is new: what it
  shows, yes and no, from the request in words and from the key.
- **Names in NVDA's own code**: the compiled modules of the NVDA 2026.3.1 on this computer were searched for
  every NVDA name the new code uses (api.getStatusBar, getStatusBarText, getFocusAncestors,
  winVersion.getWinVer with releaseName and build, documentationUtils.getDocFilePath, the app module's
  productName and productVersion, keyboardShortcut, positionInfo, displayString). All were found. Finding a
  name does not prove it behaves as expected.
- **The listing of open windows** was run by itself on this computer, outside NVDA: it ran and found one
  window. Windows that Windows keeps hidden for sleeping apps are left out.
- **A trial against the real user guide of NVDA 2026.3.1** on this computer, 1643 passages with the commands
  and notes, 35 questions, each ranked in under 5 thousandths of a second. This is how the rules above were
  found: the first trial gave the mouse chapter for the desktop question, because of the table heading
  "Desktop key". Known weak answers that remain: "what is focus mode" has no section of its own and gets
  passages that mention it; "how do I save a file" and the like are answered from the Windows notes only where
  a note exists.
- **`tests/live_orchestrator.py` with the owner's real model**, Qwen3.5 9B for both jobs, stand-in tools but
  the real ranking over the real commands, notes and user guide. With one small question at a time, as the
  owner uses it: all 72 requests of the list were carried out, 12 of them new questions, each question in
  about half a second. The desktop question now gives: "From Windows: The desktop: going to it and navigating
  its icons with the keyboard. Press Windows+D to go to the desktop; press it again to bring the windows back.
  On the desktop the arrow keys move from icon to icon, typing the first letters of a name jumps to that icon,
  and Enter opens it." With the model putting answers into its own words (20 requests read): "Press Windows
  and D together to go to the desktop. ... Use the arrow keys to move from one icon to another. ... Press
  Enter to open an icon."; "Press the NVDA key plus T to read the window title. The current window title is
  Space Trader - Main Menu."; "Press Alt+N to start a new game."
  What the runs showed and what was changed for it: (1) for "how do I copy text" the model joined NVDA's
  review-cursor command and Control+C into one way; since the pieces are numbered it says them as two.
  (2) "What is browse mode" was answered from the settings chapter of the same name; of two sections with the
  asked-for heading the first in the guide is now taken. (3) "Which windows are open" was taken as "where am
  I"; the hint was narrowed. (4) "How much battery is left" found nothing, because "much" and "left" counted
  as what is asked about, and it had lost its way to the battery command; "much" and "many" now only ask, and
  the words point to the command again. (5) "What can I do here", quoted, gave the program alone; the window
  and the focused control are now said with it. One request still ends in a question to the user: "How do I
  bake a cake?", where the model wants to work out steps itself; after the user's choice it says that nothing
  was found.

Not tested: **none of this has run inside NVDA.** Walking a real window for controls with keys, the status
bar, the real focus and its ancestors, the open windows as seen from inside NVDA, how long the first question
takes while the user guide is read, and the window with the edit box are all untried there. How well the
smaller models choose `look_up` was not measured; only Qwen3.5 9B was run.

## Learning about the program in front, and the models used for more (0.11.0, 2026-11-17)

The owner asked that VisionClaw identify the application or game he is in, search the internet, learn about
it, make quick notes in Markdown that he can delete later, and let him ask questions about it; and that
VisionClaw use its models to be more intelligent and more aware of where the user is.

What was built:
- **`learn_app`** (`learntools.py`, `claw/learn.py`). The program in front is read from Windows (file name,
  product name, version, window title, focused control). Plain code makes the list of names it could be known
  by, leaving out product names that only name what runs it (Java, Python, the Windows shell); a model
  chooses one and says game, program or utility. The user is asked, always, with what is sent. Then:
  Wikipedia is searched for the name and the article with that name is read, if its opening is about
  something run on a computer; Wikidata is asked for the official website (P856) and the user manual (P2078);
  those pages are read, and up to four links on each that lead to help on the same server. At most 6 pages.
  From each page the sections that name keys, or whose heading is about keys, getting started, the interface
  or accessibility, are kept, at most 6 a page and 20 in all, 1500 characters each.
- **Notes.** A model that is not one of the very smallest writes short points from each section; plain code
  keeps a point only if every key it names is in the section and at least 60 percent of its words are. Where
  no point stands, the section's own text is kept. One Markdown file per program, with a Source line under
  every note. `app_notes` lists or opens them, `forget_notes` deletes one or all after a question, `note_page`
  adds the page open in the user's browser, read through NVDA, with nothing fetched.
- **Questions from the notes.** `look_up` adds the notes of the program in front to what NVDA, the program,
  the window and Windows say. An answer from them begins "From the notes on <program>, from <website>".
  Where nothing is found and there are no notes, the answer says how to get some.
- **What "this" means.** A question that points ("what does this do", "how do I close it") is put to a model
  with the program, the window and the focused control as the three choices, unless the user's words say it
  ("this program", "this button"). The name of what is meant is looked up with the question.
- **Whether what was found answers the question.** With one small question at a time, a model that is not
  one of the very smallest is shown the lines that were found and where the user is, and chooses the one that
  answers, or 0 for none. On 0 the user hears "Nothing that was found answers that. The nearest thing found,
  which may not be what you want:" and the line. The very smallest models are not asked.
- **A word nothing has.** In the ranking, a word of the question that no source has now counts as half the
  rarest word, instead of not at all. "How do I duplicate the current line" no longer gets whatever has
  "current".

**No search engine, and why.** The first version searched DuckDuckGo's page for people. After about ten
requests in a few minutes, from this computer, it answered every request with its challenge for automated
traffic (HTTP 202, "anomaly"). That is the site saying no to programs. It was not worked around; the
search was taken out, and Wikipedia and Wikidata, which keep a door open for programs, are asked instead.
What this costs: a program without a Wikipedia article is not found, and one without a website on Wikidata
gets only Wikipedia. Wikipedia answered "too many requests" (HTTP 429) during the trials, after bursts of
requests in a few seconds; one learning makes 2 requests to Wikipedia and 2 to Wikidata, a server that asks
for a pause gets 4 seconds and one more try, and what fails is named in the answer.

Tested, and how:
- **`tests/test_learn.py`, plain code against a stand-in internet** that writes down every request: the
  exact list of nine addresses asked for Notepad++, in order, with the servers each answer may come from, and
  no search engine among them; Notepad++ told from Notepad; the links of a manual that are worth reading and
  those that are not (download, licence, another website); a cookie notice with keys in it left out; a
  script's text never read; the notes file word for word; listing, finding, adding to and deleting notes
  while keeping what the user wrote into them; questions answered from the notes with the website; a program
  Wikipedia does not know; an article of the right name about a river; "too many requests" retried once; a
  page that times out; stopping; the model's choice of name and kind among the names offered; a made-up key
  and a made-up fact dropped from the model's notes; what "this" means; the model's pick of a line and its
  "none"; the hints for the four new recipes.
- **`tests/test_nvda_stub.py`**, the real tools through the real registry: no means no request at all; the
  question's wording; the six requests after yes, each calling itself "VisionClaw/<version> (NVDA screen reader
  add-on)" and taking text only; the notes file; the model's made-up key not in it; a question answered from
  the notes; "What does this do?" put to the model and answered about the focused button; the browser page
  added with no request; deletion; the hint when there are no notes.
- **The real internet, plain code** (`learn.study` with the add-on's own fetching): Notepad++, 10 requests,
  5.6 seconds, Wikipedia and npp-user-manual.org, 12 sections; Audacity, 9 requests, 3 seconds, Wikipedia and
  audacityteam.org, 8 sections; Stardew Valley, Wikipedia's Gameplay section only, because Wikidata answered
  "too many requests" at that moment; a made-up program, nothing kept.
- **`tests/live_learn.py`, the real Qwen3.5 9B and the real internet**: the model named five programs and
  their kind from what Windows reports, all rightly (Notepad++ a program; a Java game by its window's title,
  a game; Visual Studio Code a program; 7-Zip a utility; Calculator, behind Windows' frame host, a program).
  Learning about Notepad++ took about 45 seconds, 10 requests; the model wrote points for 10 of 12 sections,
  each checked against the page, in 1 to 6 seconds a section. After the limits were raised to 6 sections a
  page, a second run kept 16 notes, 13 of them written by the model, in 57 seconds. Seven questions were then
  asked from the notes in both ways of answering. Read, with one small question at a time: "How do I go to
  the next tab?" gave the manual's note on Ctrl+Tab; "What is this program?" gave Wikipedia's opening, and no
  model was asked what "this" is; "What does this do?", with the focus on a check box, was taken by the model
  to be about that check box and answered with it and its key; "How do I copy text?" gave the manual's note on
  Ctrl+C; "How do I duplicate the current line?", which the notes kept do not cover, gave "Nothing that was
  found answers that" with the nearest note marked as only the nearest, where the first run had given that
  note as the answer. In its own words the model said for that one "I could not find information on how to
  duplicate the current line in Notepad++." One answer is weaker than it should be: in its own words, "How do
  I go to the next tab?" was answered from Windows' note on File Explorer's tabs and not from the program's
  note.
- **`tests/live_orchestrator.py` again, the whole list of 72 requests**, with the real Qwen3.5 9B asked one
  small question at a time and now judging the lines: all 72 carried out, every question answered as before
  or better, and the model said "nothing answers" for none of them, so it does not turn right answers away
  on this list. "How do I copy text?" now gives Windows' Control+C, which the model chose over NVDA's
  review-cursor command. Each question takes about 1.2 seconds, where it took 0.5 before the model judged.
- The models' new steps cost time: about a second for what "this" means, and about half a second for judging
  the lines, on a GeForce RTX 5060.

Not tested: **none of this has run inside NVDA.** The program's product name and version as NVDA reports
them for real programs and games, the question window, how the notes file opens, reading a browser page
through NVDA for `note_page`, and how long a learning takes while NVDA speaks are all untried there. Only
Qwen3.5 9B was run; how the 2B and 4B models write notes is not measured. Three programs were learned from
the real internet; games are the weakest: Wikipedia says what a game is and how it plays, seldom its keys.

## Memories in Markdown, the library, and notes on accessibility interfaces (2026-11-17)

The owner asked that VisionClaw save memories in Markdown the way Claude does, only when necessary; that the
user can delete some or all of them and start over; and that VisionClaw look things up in information about
accessibility APIs, NVDA, Windows and programs.

- **Memories** (`claw/memories.py`, `memorytools.py`, `memoriesui.py`): one Markdown file for each memory in
  the folder `memories` of VisionClaw's data, with an index, `MEMORY.md`. Kept when the user asks
  ("remember that ...", "call me ..."), or, under the default setting "Remember things", when the user says
  something lasting about how they work the computer and nothing else in the request kept it; the answer says
  so and how to undo it. The user's own words are kept, "my" turned to "your" by plain code; no model writes
  a memory. Tools `remember`, `memories`, `forget_memory` (one, the last, or all; all is always asked about);
  the memories window from the settings or from an NVDA command without a key, with check boxes, the whole
  memory, Forget checked, and Forget all and start over. The old `remember` tool, which wrote a lesson, is gone.
- **The library** (`claw/library.py`): Markdown, text, saved web pages and Word documents in the folder
  `library`, asked by `look_up` after Windows, with the memories; `search_help` reads it too; the tool
  `library` lists it or opens its folder.
- **New notes**, each written from the pages named at its top, read on 2026-11-17: `api-uia.md` (37 sections),
  `api-msaa-ia2.md` (22), `api-aria.md` (26), `api-java-access-bridge.md` (11), `windows-accessibility.md` (24),
  `app-browsers.md` (23), `app-office.md` (25), `app-explorer.md` (6). The API and program notes are asked only
  when the question or the program in front names what they are about (`lookup.gated`).
- **Lookup**: "UI Automation" counts as one word (a two-letter word is not a word there); within one source, a
  heading that names more of the question comes first; a last piece of a section shorter than a third of a
  passage stays with the piece before it.

| Test | What it shows | Result |
|---|---|---|
| `tests/test_memories.py` | What is kept from the user's words; what is kept without being asked and what is not (a changed setting, a statement not about using the computer, the setting at "only when I ask" or "never"); the files and the index; a memory about the same thing replacing the old one; a file written by hand; recall with a request and in a program; forgetting by words, the last, all; the orchestrator giving memories to the planner and keeping one after a request, and a memory that cannot be saved not ending the request; the library reading text with headings, Markdown, a web page in a subfolder and a Word document, and saying which could not be read; the library and memories answering questions; gated notes; the hints | passes |
| `tests/test_memories_window.py` | The memories window with the real wxPython (not shown on the screen) and stand-ins for NVDA's gui and ui: the list, the whole memory, nothing checked, a no, forgetting the checked one, forgetting all and starting over | passes |
| `tests/test_nvda_stub.py` | The real tools against stand-ins for NVDA: remembering, a memory replaced, listing, recall, an empty library, a document added, `search_help` and `look_up` reading the library and the memories | passes |
| `tests/live_orchestrator.py`, 15 requests, Qwen3.5 9B for both jobs, on this computer | Remember, what do you remember, which braille display, "I'm new to NVDA. How do I read the title of this window?", forget that, the library, a question answered from a manual in the library, UI Automation, aria-label, reopening a tab in Chrome, Sticky Keys, and four earlier requests | First run: 14 of 15 right. "I'm new to NVDA. How do I ..." made the hint say remember, the user was asked, and the whole question was kept. Fixed (the hint now takes only a statement alone, and a question is never kept); run again, the question was answered and only "You're new to NVDA" was kept, and "forget that" removed it. "Which braille display do I have?" was answered by `nvda_info` from the display in use, not from the memory, which is right. |
| `tests/test_core.py` | A model with its own thinking mode that thinks until no tokens are left is asked again without thinking | passes |
| `tests/live_addon_memories.py`, Qwen3.5 9B, on this computer, sharing the graphics card with other sessions' engines | A real model writes two add-ons with what the user asked VisionClaw to remember, the user's library and the notes on accessibility interfaces put first (`library.forCoder`): a money key for a game, from a memory ("your money key is NVDA+shift+M") and a manual in the library ("shown in the status bar ... as Credits:"); and announcing UI Automation notifications | First run: both failed with "The file must define class GlobalPlugin". The cause was not the notes: at reasoning High the model thought until all its tokens were used and wrote nothing, every round. Fixed in `llm.text` (an empty answer after thinking is asked for again without thinking). Second run: both passed the checks, but the money key read the focused control, and the other used `event_notification`, which NVDA does not have. The notes had neither: NVDA's source was read and `event_UIA_notification` (the text is `displayString`) and `api.getStatusBar`/`api.getStatusBarText` were added; a library passage now brings NVDA's note on what it names (`library.nvdaNote`). Third run: both right. The money key uses NVDA+shift+M, reads the status bar and says "Credits:"'s amount, or that there is none; the other says `displayString` and calls `nextHandler()`. Still: the money key works in every program, not only the game, and the notification add-on may say a notification twice in the program in front, because NVDA already does there. Each add-on took 10 to 50 minutes, with other engines on the same card. |

Not tested: none of this has run inside NVDA. The memories window has not been used with NVDA speaking it; the
command that opens it has no key until the user gives it one in Input gestures. The library has been tried with
small documents only.

## Instructions for blind users in every answer, description and add-on (2026-11-17)

The owner asked for global system prompts made for blind people, after VisionAssistantPro's; that they can be
changed and the originals always put back; that they apply whatever model is used; and that they, skills,
memories and notes also reach the add-ons written on the fly, each chosen by the request.

- `claw/prompts.py`: who the user is (blind, speech or braille), how an answer is worded to be heard (start
  with the answer, no Markdown, names, numbers and keys copied exactly, places in words, nothing only by its
  colour, no looking or hand on the mouse, say what is not known), what matters in a picture (text exactly,
  focused, selected, checked, greyed out, never fill in what cannot be read), what an add-on must be for this
  user, the three description requests (with their honesty sentence), and three code-writing rules added only
  when the request asks for that kind of add-on (a key, by itself, one program; `prompts.codeKinds`).
- Every answer a model words for the user (`prompts.speaking`), every description and question about a picture,
  in the description window, read-ahead, chat photos and the `look` tool (`prompts.seeing`), and every writing,
  review and repair of an add-on (`prompts.coding`) has them as its system prompt, followed by the user's own
  instructions and language. Forms and judgements get only `prompts.IDENTITY`, so the user's words cannot
  change the ids they copy. The instructions are kept in the settings, not with a model, and are sent with
  every request, so they apply to any model, one or two, after models are removed, added or swapped, and
  again after NVDA switches or reloads its configuration profile.
- "How VisionClaw answers, and your own instructions" in VisionClaw's settings: a list of every instruction and
  an edit box; an entry says "(changed)"; "Restore the original of this instruction", "Restore all originals";
  an empty box is the original. VisionClaw's own wording lives only in the code, so it can always come back,
  and a newer version's wording reaches a user who changed nothing.
- Skills (skills session) and memories and notes (memories session) reach the add-on writer in its user message.

| Test | What it shows | Result |
|---|---|---|
| `tests/test_prompts.py` | No example and no model role in any part; how the parts are put together; the user's wording and own instructions used, an original given back not kept as a change; a picture's first message; in a scripted request the answer gets the instructions and no form does; add-on writing, repair and review get them | passes |
| `tests/test_nvda_stub.py` | The window lists every part with "(changed)"; OK keeps the user's words and turns the original into ""; the `look` tool sends them; settings saved again keep them; restoring all gives back every original | passes |
| `tests/live_orchestrator.py`, 72 requests, Qwen3.5 9B for both jobs, the model wording the answers, before and after | 56 answers word for word the same. Better: "VisionClaw version 0.8.2 is enabled. NVDA Remote version 2.6" (before: "0.8", "2"), window names kept whole, keys written NVDA+T. Worse at first: "How do I read the title" was answered "press NVDA+T twice" | found, then measured six times each: old wording 0 of 6 wrong, first new order 2 of 6 wrong, the order now used (the task's own rules before the wording rules) 0 of 6 wrong |
| `tests/live_prompts.py`, Qwen3.5 9B, four drawn pictures, quick, one sentence and a question | With the instructions: the answers start with what is shown, say which button has the focus, which boxes are checked and that Advanced is greyed out, and are shorter. Two faults seen: "Shopping list dot txt" for a file name, and a blurred error number read as a made-up one where the request alone said it was unreadable | the honesty sentence was put back next to the request and "dot" taken out of the rule; see the next line |
| `tests/live_prompts.py` again, after those changes | The blurred error is now said to be unreadable; the states and the focus are still named. Unasked advice seen ("try pressing F1"): "Give no advice that was not asked for" was added to the wording rules. "Shopping list dot txt" is still said: the model writes the file name that way whatever the rule says | blurred error fixed; "dot txt" is a known limitation |
| The title question, six times, Qwen3.5 9B, with the wording as it is now (after the advice rule was added) | All six say NVDA plus T reads the title; one also says what the second and third presses do, correctly | 0 of 6 wrong. The keys are written "NVDA plus T", not "NVDA+T" |
| `tests/live_addon.py`, Qwen3.5 9B writing and reviewing, with the instructions and without, 40 minutes each | With them: "Say hello when I press NVDA+shift+H" and "Beep when a link gets the focus" written right and passed the check and the review (the hello script has a description saying what it does; the beep lets every focus change pass on). Without them: the hello add-on, the same code. Neither run reached the third and fourth add-on in its 40 minutes: the memories session's 9B test shared the card the whole time (one add-on took 30 minutes), and an earlier run of three hours wrote nothing because the 9B thought until its tokens ran out (fixed in `llm.text` by the memories session) | 3 add-ons written, all right; nothing worse with the instructions; the comparison is too small to say they make add-ons better |

Not tested: none of this has run inside NVDA. The window, the profile switch and how the instructions sound
with a real synthesizer and display are untried. The engine was shared with other sessions' live tests during
these runs, so the times measured then are not the add-on's.

## Skills: built in, the user's own, chosen by plain code (2026-11-18)

The owner asked that the user can add skills of their own, SmallClaw's SKILL.md files, and that VisionClaw
comes with a full set of skills that matter to a blind user; then for a button that opens the skills folder,
and a way to add and remove the chosen skills; and that skills also reach the add-ons written on the fly.

- **What a skill is** (`claw/skills.py`): a folder with a SKILL.md, a few lines at its top (name, description,
  the words that start it, the jobs it is for, optional fixed steps) and plain sentences on how that kind of job
  is done well for a blind person. It never holds code, and every tool still asks before it changes anything.
- **38 built in** (`claw/skills/`): describing a photo, text NVDA cannot read, a window's layout, unlabelled
  buttons, web forms, shopping, pop-ups and banners, error messages, NVDA for a beginner, comfortable speech,
  braille, a silent NVDA, games, stubborn programs, naming a control, announcing changes, keys, long web pages,
  web searches, video calls, email, how a document looks, charts, colours, screen privacy, installers, PDF,
  tables, music software, the mouse from the keyboard (NVDA's own mouse keys, taken from
  `tests/nvda_commands.json`), two with fixed steps ("where am I": the window and what it shows; "quick
  status": the time, the date and the battery), and six for the add-ons the models write (one key, speaking by
  itself, one program or game, reading what NVDA misses, braille, and the blind user in general).
- **Chosen by plain code** from the request's words, at most two: a phrase of several words must be there word
  for word unless two or more of its words tell what it is about, so an everyday word alone does not start a
  skill. Their sentences go to the forms of the jobs they are for, the `look` tool, the add-on writer and
  repairer (before the memories and notes) and the answer; never to the one-field questions of the very
  smallest models, and never to the model that chooses the recipe. A skill with steps runs them as its plan
  only when the request has one of its starting phrases word for word ("Following the skill ...").
- **The user's own**: in words ("make a new skill: when I ask about recipes, ...", "which skills do you have",
  "what does the email skill say", "turn off the game skill", "delete my recipes skill") through the tools
  `add_skill`, `list_skills`, `show_skill`, `manage_skill`; what the skill tells VisionClaw is the user's own
  words, and only starting words the user said are kept. Or in the skills window (NVDA+Alt+I, or the button in
  the settings): every skill, what the chosen one says, New skill, Change, Turn off or on, Delete, Import a skill
  file (what it says is shown before it is kept), Open the skills folder (also a button in the settings), Read
  the skills again. A built-in skill is never deleted, only turned off; the user's copy of one takes its place,
  and deleting that copy brings the original back.

| Test | What it shows | Result |
|---|---|---|
| `tests/test_skills.py` | Every built-in skill passes the check (starting words not too common, known jobs, under the length limit, no Markdown or examples); which skill 19 requests start and which code-writing skill 4 add-on requests start, and that requests about something else start none ("what time is it", "turn off the typing echo", "Undo that"); the plan of a skill with steps; the sentences for a job, for an add-on, for the answer; the user's skills, a copy replacing a built-in one, turning off, deleting, a broken file reported and skipped, importing; in a scripted request the skill's plan, its sentences in the form and the answer, a turned-off skill not used | passes |
| `tests/test_skills_window.py` | The skills window and the window for one skill with the real wxPython (not shown on the screen) and stand-ins for NVDA's gui and ui: the list and the whole of the chosen skill, a built-in one not deleted, turning off and on, the window that makes a skill with its steps chosen from a list of jobs, a skill without starting words refused with the reason, a changed built-in skill kept as the user's copy and the original back when the copy is deleted, a no keeping a skill, the folder made with a note on writing skills | passes |
| `tests/test_nvda_stub.py` | The real tools against stand-ins for NVDA: making a skill with the question, listing, reading one, turning the game skill off (not the add-on skill for games, a fault found by the prompts session and fixed: a skill whose short name the user says wins), deleting a built-in one turns it off after a question | passes |
| `tests/live_orchestrator.py`, Qwen3.5 9B for both jobs, the first 20 of the requests | Earlier requests with skills in place | 19 of 20 right; the 20th was cut off when the run was stopped to free the graphics card for the other sessions. "I'm new to NVDA" got the beginner skill and a better answer. One request picked the long web page skill because of the word "news"; its starting words were made longer |
| `tests/live_orchestrator.py`, Qwen3.5 9B for both jobs, 8 requests about skills, after the other sessions' work | "I'm new to NVDA. How do I read the title", "Make NVDA speak a little faster", "Right-click the Options button" (the mouse skill), "Quick status" (the skill's three steps: the time, the date, the battery), "Describe this picture", making a skill in words, "Which skills do you have", "Turn off the game skill" | All 8 right in the end. Two faults found and fixed. The live test's stand-in for looking at the screen did not give the model the instructions for blind users or the skill's sentences, as the real tool does, and its description came back in Markdown and was cut off; with the stand-in made like the real tool, the description starts with what is shown, quotes the text exactly and says there are no people in the picture, as the photo skill asks. "Turn off the game skill" named the game skill as used, because of the word game, although it says nothing about turning a skill off; now only skills that speak about a step of the plan are kept and named (`tests/test_skills.py` has the case) |

Not tested: none of this has run inside NVDA. The skills window has not been used with NVDA speaking it, and
NVDA+Alt+I has not been pressed in a real NVDA.

## Q4_K_M or Q6_K for every model: the user's choice (2026-11-18)

The owner's words: "user should be able to choose between q4_k_m and q6_k for everything. **user choice**
visionclaw suggests, user can take the suggestion or make his own model and quant choices."

What was done:
- Every model in the catalog can now be had as Q4_K_M and as Q6_K: the four Qwen3.5 vision models, the three
  Qwen2.5 Coder models, and Qwen3.5 4B and 9B used for coding. That is 18 entries, 9 of them new. The Q6_K
  files were read from Hugging Face's API (`/api/models/<repo>/revision/<rev>?blobs=true`) at the revisions
  the catalog already pins, from the same publishers (unsloth and Qwen). Every model has a single Q6_K file
  there, so no quant is missing.
- Each quant is an entry of its own (`qwen3.5-2b-q6k` beside `qwen3.5-2b`), in the same folder. The vision
  projector is the same file for both quants, so it is downloaded once. The Q4_K_M entries keep their old
  ids, so a setting from before there were quants still means Q4_K_M, and nothing changes for a user who has
  a model. `models.json` was regenerated (`LIST_UPDATED` 2026-11-18). An older VisionClaw that presses "Look
  for newer models" reads the Q6_K entries as extra models and can use them; `checkEntry` there drops the new
  "quant" field.
- The models window has a second list under each model, "Vision model quant" (Alt+Q) and "Coder model
  quant" (Alt+A). The list of models says, for each model, which quant is on this computer and how much each
  other quant would download. The list of quants says, for each: "Q4_K_M, smaller and faster" or "Q6_K, larger
  and more exact, best for writing add-ons", the model file's size, and whether it is on this computer or how
  much is left to download. The suggested model and the suggested quant are marked "suggested" and chosen
  first, never forced. Every model and quant is offered on every computer. Choosing another model keeps the
  quant chosen before. The Download button counts a shared file once.
- A stored model is now one folder and quant (`catalog.storeKey`: `qwen3.5-2b`, `qwen3.5-2b@Q6_K`). After a
  switch to the other quant, the one no longer used is offered for removal, as before. The projector stays
  until the last quant of the model is removed. The size in the question is what removing really frees
  (`Catalog.freedBy`). "Which model do you use" now names the quant (`catalog.displayName`).
- `catalog.SUGGESTED_QUANTS` holds the models for which measuring showed Q6_K clearly better. It is empty:
  see below.

| Test | What it covers | Result |
| --- | --- | --- |
| `tests/test_parts.py` | Every model in both quants, same publisher, revision, folder and projector; the names with and without the quant; Q6_K_XL not taken for Q6_K; the suggestion Q4_K_M on every computer, and Q6_K when `SUGGESTED_QUANTS` says so; a list whose quant is not its file's is refused; the setting kept as the entry's id, an old setting meaning Q4_K_M, a Q6_K setting used; the same model in two quants is two models, not one doing both jobs; on the disk, both quants as two stored models, the projector downloaded once, counted once, and removed with the last quant; `models.json` equals the catalog | passes |
| `tests/test_models_window.py` (new) | The models window with the real wxPython (not shown on the screen): every model listed once with what each quant would download; an old setting chooses Qwen3.5 2B in Q4_K_M; the quant list's words and sizes and the suggested mark; a projector on the disk not counted again in the Download button; another model keeps the quant chosen; every coder in both quants; no coder model; the choice written to the settings and the keys of the files in use handed on for the removal offer; the window opened again shows the choice; each list has its own label and key | passes |
| `tests/test_nvda_stub.py`, `tests/test_one_model.py` | The labels of the model list; the names said by "which model" with the quant | passes |
| `python tests/run_all.py` | All 21 plain-Python tests | passes |
| `tests/live_quants.py` (new), Qwen2.5 Coder 1.5B in Q4_K_M and in Q6_K, each its own reviewer, three rounds of the four add-ons of `live_addon.py` and the debugging of `api.getFocus` | Q4_K_M: 12 of 12 passed the checks, 3 with no repair round, 18 repair rounds in all, 2.7 s each; the debugging gave `getFocusObject` 3 of 3. Q6_K: 9 of 12 passed, none with no repair round, 30 repair rounds, 3.2 s each; the debugging gave `getFocusObject` 3 of 3, after 2 repair rounds each time | Q6_K not better |

What the measurement shows, and what it does not. The three rounds gave the same results each time, so this is
really one run of five jobs per quant. Q6_K failed "Beep when a link gets the focus" every time: it kept a
key command the request did not ask for, through four repair rounds. It also needed repair rounds where
Q4_K_M needed none ("Say hello" picked up an unused `import keyboardHandler`). Both quants debugged the
failing add-on to `api.getFocusObject`. The add-ons that passed were read and are alike, all usable. On this
small set, Q6_K is not better for the 1.5B coder, so Q4_K_M stays the suggestion for every model. The Q6_K
files were downloaded with the owner's yes (2.4 GB for the pair).

Not measured: the vision models in Q6_K, the 0.5B and 7B coders and the Qwen3.5 models used for coding in
Q6_K, and `tests/live_addon_memories.py` and `tests/live_orchestrator.py` with any Q6_K model. A larger set of
requests (phase 5.1) may still find a model that Q6_K helps. Not run inside NVDA: the models window with its
new lists has not been used with NVDA speaking it, and no Q6_K model has been downloaded from the window
itself (the download in the test went through the same `Catalog.download`, with its SHA-256 check).

## Controls that need more than a click, and every kind of control (1.1.0, 2026-11-18)

The owner's words, after another session had said that controls worked by hovering, holding the button down,
gestures or reacting to timing were not on VisionClaw's list: "I want those to be on the list of visionclaw
controls which visionclaw must be able to make accessible too." Then: "if necessary, make skills and system
prompts appropriate for such controls", "if you can think of any other controls to add to the list ... add
those", and "both controls and control types for accessibility".

What was done:
- **Five new ways of working a control** in `working.WAYS`: hover, press and hold, swipe or draw, click at the
  right moment, drag in any direction. Both questions to the models name them. A control's own name or
  description decides by plain code where it says so (`working.bySaid`: "Hold to record", "Swipe to unlock",
  "Sign here", "Hover for details", "Click when the bar is green"), kept narrow: a button called Hold is
  clicked. Such a control is found whether or not it takes the focus, on a web page too, because Enter clicks
  a button and does not keep it down.
- **A means for each**, in `claw/pointer.py` (plain reasoning) and `mousetools.py` (the mouse):
  hovering with the window compared before and after and the new text read out (`click_item`, also on a web
  page, through the item's own place on the screen); holding for a time from the words (`pointer.holdSeconds`,
  at most a minute); gestures as strokes from the words (`pointer.gestureOf`, `draw_gesture`): a swipe or a
  line in up to six directions, a circle either way, a tick, a zigzag, a square, a triangle, a cross in two
  strokes, six letters, with the left or the right button, a size and a speed; a click when a watched place
  changes, or a number of clicks in a steady rhythm (`pointer.timingOf`, `timed_click`).
- **More clicks**: the middle button, three clicks, Control, Shift or Alt held down
  (`pointer.modifiersOf`, `mousetools.keysDown`), and a click at a place on a thing (`pointer.spotOf`).
  `scroll_view` zooms in and out with Control and the wheel.
- **Pointer mode**: T rests the pointer and says what appears, C clicks when what is under the pointer
  changes, Shift+C only sounds a tone; any key ends a watch.
- **Hotkeys**: an app helper can hover over its item and say what appears, or hold the button down on it until
  the hotkey or Escape is pressed again (`helpers._pointed`, `PointerMode.keepDown`, `letGo`). A held button
  lets go by itself after two minutes, and when VisionClaw stops.
- **The inspection** reports such controls (`accesstools._specialFindings`): for hover and hold it offers
  hotkeys, kept as data like the hotkeys for dials; for the others it says what to ask for.
- **Every kind of control**: the 156 kinds in `controlTypes.Role` of the NVDA installed on this computer were
  read from its `library.zip` (the names only, nothing run), and each is now sorted: worked in a known way,
  only holding or showing something, or left for the models to look at (`working.knownRole`). `byFacts` also
  uses UI Automation's drag, move and resize, scroll and select, the page's `draggable` and `haspopup`, more
  web roles, and NVDA's states. The web roles were written from what is commonly used, not checked against
  the standard's own list.
- **A model's choice of recipe is checked** where plain code can tell it cannot be meant (`planner.fitted`).
- A 39th built-in skill, "Work a control that needs more than a click".

| Test | What it covers | Result |
| --- | --- | --- |
| `tests/test_pointer.py` | Which action the words mean (hold, middle, triple, hover; a button called Hold is clicked); how long to hold; a time in words ("as" is not "a s"); keys held down, and "with the control panel" naming none; a place on a thing; when and how often to click, with the limits; the threshold of a watched place; gestures by direction, shape, button, size and speed, their points in small steps inside the window; where a picture changed, and a speck not counting | passes |
| `tests/test_working.py` | What a control's own name says, 19 names; its words before a click Windows offers; the survey finding such controls with and without the focus, also on a page; the remedy and the advice for each way, with what the timed click cannot do; every way named in both questions to the models; all 156 kinds of NVDA sorted, each in one place only; thumbs, grips, videos and embedded objects; what Windows, the page and NVDA's states say | passes |
| `tests/test_nvda_stub.py` (the mouse, the keys and the wheel only written down) | Hovering says what appeared, that nothing did, or that the window could not be looked at; holding for half a second with a question first, and a stopped request letting go at once; the middle button; Control down before the click and up after; three clicks; a click 25 percent across; a swipe from the named item with the pointer put back; a circle with the right button; words that name no gesture; three clicks in a rhythm; a click when the place changes; nothing clicked when it never changes or changes all the time; zoom in and out with Control up again; T, C and Shift+C in pointer mode and a key ending a watch; a hotkey that hovers; an inspection that finds "Hold to record" and "Swipe to unlock" by their names, makes a hotkey for the first, which holds at the first press and lets go at the second, at Escape and when VisionClaw stops; the deep query of that button | passes |
| `tests/test_core.py` | The words that point to the two new recipes and to a click that holds; "tell me when the score changes" still a fix; a model's impossible choice corrected | passes |
| `python tests/run_all.py` | All 22 plain-Python tests | passes |
| `tests/live_working.py`, Qwen3.5 9B looking, Qwen2.5 Coder 1.5B reading the facts | 12 drawn controls, 6 of them new (a button that says to hold it, an information icon, a bar to swipe, a box to sign in, a bar with a moving marker, a square pad), and 11 fact sets | First run 19 of 23: the vision model called an upright fader a click, which it had called a drag before the new lines were added. With the ways of dragging listed first it named all 12 drawn controls rightly, so that order is kept. The coder model called a plain text "mouse wheel", and got neither of two free wordings ("keep the mouse button down on this while you speak": "click at the right moment"; "sketch with the mouse": "mouse wheel"). It had not been given the description at all; that was a fault and is fixed. Qwen3.5 9B as the coder got one of the two. Both wordings and the plain text are now decided by plain code. After that 23 of 23, of which 12 by the vision model and 11 by plain code |
| `tests/live_orchestrator.py`, Qwen3.5 9B and Qwen2.5 Coder 1.5B, stand-in tools, 96 requests of which 8 are new ("Press and hold the New Game button for 2 seconds", "Hover over the Options button", "Middle-click the Options button", "Swipe left on the Options button", "Draw a circle in this window", "Click the Quit button as soon as it changes", "Click the New Game button 5 times", "Zoom in") | Which job both models choose, and the forms | 94 of 96 got the fitting job from both models; all 8 new ones did, and all the older mouse requests (click, right-click, drag, scroll, pointer mode, the dials). One fault was found and fixed first: both models sent "Press and hold ... for 2 seconds" to the click at the right moment, also after a rewording and although the words pointed to a click; plain code now corrects a choice the words cannot mean (`planner.fitted`). The two that did not get a fitting job at once: "Name the focused button Share on this website" (the vision model chose to work out the steps itself, the coder model the lasting fix; in VisionClaw the user is then asked, the stand-in took the vision model's choice, and its free plan ran for eight minutes and named nothing), and the second half of "Do a deep query of this control and tell me how a sighted person works it" (the user is asked). Both went the same way with the two new recipes taken out, so they come from this pair of models, not from this change; with Qwen3.5 4B and 9B on 2026-11-17 both had chosen rightly. The first full run stopped after nine requests with the engines idle, for a reason not found; the second ran through |

What the measurement shows, and what it does not. The drawings are simple and say in words what to do with
them; a real program's control that is held down or hovered over often says nothing, and then a model can
only guess from its look. The small coder model cannot be relied on for a free wording, which is why plain
code decides wherever words allow. Nothing here was run inside NVDA or against a real program: no real tip
was read, no real button was held, no real gesture was drawn, and no real key was held down during a click.
`keyboardHandler.ignoreInjection` is used so that NVDA takes no notice of the held key; that it exists in
every NVDA from 2024.1 on was not checked, and without it the key is pressed all the same.

## Fingers, pressure, games that read the mouse directly, and a game controller (1.2.0, 2026-11-18)

The owner's words, of what 1.1.0 had named as not covered ("Gestures with two fingers, pressure, and games
that read the mouse directly are not covered"): "visionclaw must be able to make these controls accessible as
well. Find a way or multiple ways to do this, using visionclaw and its offline local models, skills, memory,
rag, and system prompts." And: "when the user has a gamepad or controller such as an xbox controller
connected, support the detection of this, if detected, visionclaw must add accessibility for various movement
and button presses and clicks and pressure across all possible windows, app and game controls which can be
made to work with accessibility fixes. whether the controls are standard, nonstandard, drawn, moving,
floating, extremely custom, etcetera."

What was done:
- **Fingers** (`claw/touch.py`, `touchinput.py`, `touchtools.py`, the tool `touch_gesture`). Windows lets a
  program touch the screen as fingers would (`InjectTouchInput`). A pinch, a spread, a swipe with one to five
  fingers, a turn with two fingers, a tap, a double tap and a touch that is held are read from the user's own
  words by plain code; where every finger goes, in small steps and inside the window, is worked out by plain
  code too. The user is asked first, and the fingers are lifted in a `finally`.
- **More than one way.** The window is compared before and after. Where a touch changed nothing, the mouse
  wheel stands in: with Control for a pinch or a spread, plain for a swipe with two fingers. The user is told
  which of the two worked, and that is kept for the program (`direct.AppWays`, `appways.json`), so the working
  way is used at once the next time. Nothing stands in for a turn with two fingers, and that is said.
- **Pressure** (the tool `pen_stroke`). Windows gives a program a pen to hold
  (`CreateSyntheticPointerDevice`, Windows 10 version 1809 and later). "Lightly", "firmly", "as hard as it
  goes", a number of percent, "rising", "falling" and "from light to hard" say how hard; a press lasts a time,
  a line or a shape is drawn with the pressure changing evenly along it. On a Windows without a pen for
  programs one finger presses instead, and that is said.
- **NVDA's own touch handling.** On a computer with a touch screen NVDA takes every touch for itself. NVDA's
  source (`touchHandler.py`, read from NV Access's repository on 2026-11-18) shows that it registers as the
  target of all touch input and offers `setTouchSupport` to turn that off and on, which its own command
  NVDA+Control+Alt+T uses. VisionClaw calls that function for the moment of a gesture, always after a
  question, and puts it back in a `finally`. NVDA's setting is not changed.
- **Games that read the mouse directly** (`claw/direct.py`, the tools `turn_view` and `mouse_way`). The mouse
  itself is moved by a number of its own steps (`mouse_event` with a relative movement), which such a game
  sees as it sees a hand. The user tells VisionClaw once which kind the game is; that is kept as data and used
  only while Windows' own pointer is hidden there, which plain code reads from Windows (`GetCursorInfo`,
  `GetClipCursor`). For a view the mouse turns, "turn left", "look up a little" and "turn around" move the
  mouse and say whether the picture changed; how far is a guess that the user corrects in words ("too fast",
  "too slow"), kept for the program. For a game that draws its own pointer, the pointer is pushed into the
  corner of the window, where it must be whatever its speed, and counted from there (`direct.Tracker`); its
  speed and place are measured from three pictures, by where the picture changed. Clicking, holding, dragging,
  gestures and timed clicks by name then go there (`mousetools.directScope`). Pointer mode has the key M for
  the three ways.
- **A game controller** (`claw/gamepad.py`, `padtools.py`). A thread of its own asks Windows every two and a
  half seconds whether a controller is there (XInput; the older joystick interface every fourth time, for
  controllers of another make) and, once one is, looks at it sixty times a second. Out of controller mode only
  View and Menu held together for a second, and buttons the user made hotkeys, do anything. In controller mode
  the left stick moves the pointer by how far it is pushed, what NVDA finds under the pointer is said when the
  stick comes to rest, A, B and X click, Y says what is there, the right trigger is the mouse button while it
  is pulled, the left trigger presses like a pen as hard as it is pulled, the right stick turns the wheel or
  moves the mouse itself, and with the right shoulder button the direction pad jumps between the things found
  in the window's picture. The other commands are those of pointer mode, so nothing was written twice. A
  button can be a hotkey of a program (`create_helper`, kept as `pad:` and the button). A setting with three
  choices, and NVDA+Alt+J.
- **Three more ways of working a control** in `working.WAYS`: touch with fingers, press with pressure, move
  the mouse to look; each with a line in both questions to the models, a remedy, a means, a case in
  `tests/live_working.py` and what it cannot do. A control's own words decide by plain code ("Pinch to zoom",
  "Pressure-sensitive pad", "Move the mouse to look around"). The inspection of a window says what Windows
  reports of its pointer, and that a controller is connected.
- **Skills, notes, memories, instructions.** Three built-in skills (42 now). Notes written from VisionClaw's
  own code (`claw/knowledge/visionclaw-inputs.md`), asked only when a question names a controller, fingers,
  pressure or a game's mouse. A section in the notes for the coder: an add-on cannot read a controller or
  touch the screen, so such a thing is a hotkey and not an add-on. What the user says about a controller, a
  joystick, a pen or a touch screen counts as how they work the computer and may be kept as a memory. Every
  answer is told to name a controller's buttons as the controller names them.
- **Six new tools (69 now) and six new recipes**, with the words that point to them, and a model's choice
  corrected where the words cannot mean it (`planner.fitted`): no touch without a touch in the words, no turn
  for "turn up the volume", and never a click for "make the X button on my controller click ...".

| Test | What it covers | Result |
| --- | --- | --- |
| `tests/test_touch.py` (new) | Which touch gesture the words mean and with how many fingers, with what stays the mouse's; where the fingers go for a pinch, a spread, a swipe, a turn, a tap and a hold, in small steps, inside the window, twice as far apart on a screen scaled to twice; what stands in; pressure in words, percent, rising and falling, and that no pressure is made up; a pen's line with the pressure changing evenly over two strokes; a turn as steps of the mouse, with "turn up the volume" not meant; what the words say about a program's mouse; a game drawn by the test with a pointer of its own at four speeds, brought to places from the corner within three pixels, landing beside the place with the wrong speed, and measured to within 0.06 from three pictures; a picture that measures nothing; what is kept as data, with a broken file; 29 requests whose words point to the right job; the new ways in the survey, the remedy and both questions | passes |
| `tests/test_gamepad.py` (new) | What XInput and the older joystick interface report as one state; a stick at rest, gentle at first, strong at the rim; a slow push not lost; buttons down and up, a trigger that does not flutter, the chord once and again only after both were let go; which button does what, alone and with each shoulder button; the help naming every button; 17 ways of naming a button in words, and none where no controller is spoken of; the words that point to the controller's jobs; the three skills chosen by their words and not by others; the notes answering six questions and not answering three others; a section of the notes being one short answer; what is kept as a memory | passes |
| `tests/test_nvda_stub.py` (fingers, the pen, the mouse's own movement, Windows' facts about its pointer and the controller only written down or made up) | A pinch around the named thing, asked first, lifted where the fingers last were; the wheel with Control used where the touch changed nothing, said and kept, and used at once the next time; a swipe with two fingers as scrolling; a turn that changed nothing with nothing else tried; three fingers; a double tap; Windows refusing, with and without something that stands in; no gesture named; a stopped request lifting the fingers; NVDA's touch handling put aside and put back, also when the touch fails, and asked about with confirmations off; a press at 80 percent, a line with the pressure rising, the eraser, a finger where there is no pen, nothing pressed without words for how hard, a stopped request lifting the pen; a turn of 300 steps in small pieces, a turn that changed nothing, no direction; what is said and kept about a program's mouse; a click, a gesture and pointer mode moving a game's own pointer and never Windows'; the usual way when Windows' pointer shows; too fast kept; pointing refused where the mouse turns the view; pointer mode's arrow keys and Enter there, and M through the three ways; a controller noticed and announced once, left alone out of controller mode, the chord, the stick fast, slow and gentle, what is under the pointer said once with a buzz, the edge, A, B, X, Y, the direction pad, a drag with the right trigger, the pen with the left trigger, the wheel and the mouse itself with the right stick, jumping between things by name, a button as a hotkey in its program only, Menu and View, the tool in words, the controller going away while both triggers hold something, quiet and off, a controller of another make, and the inspection naming the hidden pointer and the controller | passes |
| `python tests/run_all.py` | All 24 plain-Python tests | passes |
| `tests/live_working.py`, Qwen3.5 9B looking, Qwen2.5 Coder 1.5B reading the facts | 16 drawn controls, 4 of them new (a map that says to pinch with two fingers, a photo that says to turn it with two fingers, a pad that says to press harder, a game's view with a mark in its middle that says to move the mouse to look), and 14 fact sets, 3 of them new | First run, with 15 drawings: 28 of 29. The 12 older drawings were all still named rightly with the three new lines in the question, so the order of the lines was kept. The pad was called "press with pressure" and the game's view "move the mouse to look". The map that says to pinch was called "drag in any direction", which is also how a sighted person works a map, and the line for that way names a map; so both answers are now counted for the map, the word "map" was taken out of the new line, and a photo that is turned with two fingers was added, which the model called "touch with fingers". Second run: 30 of 30, of which 16 by the vision model and 14 by plain code |
| `tests/live_orchestrator.py`, Qwen3.5 9B and Qwen2.5 Coder 1.5B, stand-in tools, 109 requests of which 13 are new ("Pinch the Options button with two fingers", "Swipe left with three fingers", "Press hard on the New Game button for 2 seconds", "Draw a line to the right with the pressure rising", "Turn left", "Look up a little", "This game has its own mouse pointer", "The mouse turns the view in this game", "Is a game controller connected?", "What do the buttons on my controller do?", "Turn on controller mode", "Make the X button on my controller click the New Game button", "Give this program a hotkey, NVDA+alt+1, that clicks the Options button") | Which job both models choose, and the forms | 106 of 109 got the fitting job from both models, four of them after looking again; all 13 new ones did, and every older mouse request (click, hold, hover, the gestures, the timed clicks, scroll, zoom, drag, pointer mode, the dials). For "Swipe left with three fingers" the coder model first chose the mouse's gesture and took the touch on looking again. One fault of the test itself was found first: it had no stand-in for making a hotkey, so the models could not choose that job at all and both clicked the button; with the stand-in added both chose the hotkey, also for a key. The three that did not get a fitting job: "Name the focused button Share on this website" and the second half of "Do a deep query of this control and tell me how a sighted person works it", as in 1.1.0; and "How do I bake a cake?", which both models chose to plan themselves, so that it took 79 seconds and one question to the user before the right answer came, that nothing was found. That request was run again without the new jobs and went the same way, so it does not come from this change |

What the measurement shows, and what it does not. The models send requests in words to the right job, and
tell a drawn control that says how it is worked. For the release itself nothing touched a real screen. After
it, on 2026-11-18 and with the owner's yes, `python tests/live_touch.py --yes` was run once on the owner's
computer (Windows 11, 64-bit Python; NVDA had no part in it, and whether the computer has a touch screen was
not looked at). Inside its own small window
that never takes the focus it made one pinch and one pen stroke, and printed what Windows told that window:
48 touches by 2 fingers, which began 160 pixels apart and ended 28 apart, pressing at 512 of 1024; and 15 pen
reports whose pressure went from 154 to 1024 of 1024. So Windows takes the fingers and the pen as
`touchinput.py` makes them, and a window is told the pressure that was asked for. That is one window of the
test's own: no real program was touched, and it says nothing of what a program does with a touch. The
structures have the sizes of Microsoft's own on this computer (96, 144, 120 and 152 bytes in a 64-bit
Python). No game was run: that a game sees a movement made
by `mouse_event` as it sees a hand is how Windows is documented to hand on such input, and it is not tried
here. No controller was plugged in: `XInputGetState` and the joystick interface were never read with one
there, the buzz was never felt, and how the pointer feels under a real stick is not known. In NVDA 2024.1 to
2025, which are 32-bit, the structures are smaller by Windows' own rules; that was not run.

## The developer guides put to use, add-ons by what the user wants, NVDA Coach (1.3.0, 2026-11-18)

The owner asked for four things in one sitting: that the downloaded developer guides be used with fitting
skills, retrieval, memory and system prompts, for VisionClaw's own abilities and the features that came from
VisionMate; that VisionClaw search and apply NVDA's user guides, help and free training material; that it
work with the add-on NVDA Coach, only when asked and with as much help as asked; and that it notice the
installed add-ons, learn what they do and bring them in for what the user wants. Three tools and three
recipes more, which makes 71 tools and 66 recipes: `guides_info`, `remove_guides`, `coach`. Four skills more,
46 in all, seven of them for the add-ons the models write. New files: `claw/addons.py`, `tests/test_guides.py`,
`tests/live_addon_guides.py`, `tests/live_followup.py`. Released as 1.3.0 with the four sections that follow.

What was found in the guides as VisionClaw had kept them, on the owner's computer:

- **Code examples were cut up.** `knowledge.sections` took every line that begins with # for a heading, also
  a comment inside an example, so that "Developer guide example 2" was a section whose body was bare code.
  And `guides.tidy` took the indentation off every line outside a fence, which is how the add-on guide writes
  most of its examples: their Python was no longer Python. Both are corrected (`guides.cut`, `guides.tidy`).
  Copies kept by 1.1.0 and older are still read, and the user is told to ask for the guides once more.
- **The writer of an add-on never saw the guides**, although the message after the download said so: its notes
  came from two of VisionClaw's own files only. The message now says what is true.
- **Nothing could say which guides are on the computer.** `guides.storedText` existed and was called nowhere.

What exists now:

- **The guides read three ways** (`claw/guides.py`): sections of plain sentences without code, for questions
  and speech; single facts, one line for one name of NVDA's code (98 in the two real guides: items of lists
  such as "api.getFocusObject(): Retrieves the focused control", and rows of the table of the add-on guide
  that says what is wanted and how it is written); and which guides are here, from which day.
- **For the writer of an add-on** (`nvdatools.coderNotes`, `guideLines`): the facts the request names, whose
  names this NVDA still has (`nvdatools.nvdaHas`), that are NVDA's own and allowed in a small add-on, and that
  name something the model is not told anyway. `prompts.CODE_GUIDE` goes with them and only with them.
- **For answers**: `prompts.DEV_GUIDE` when what was looked up is from the guides, `prompts.ADDON_HELP` when it
  is from an add-on; the skills `developer-guides`, `addon-by-the-guides`, `work-with-add-ons`,
  `as-much-help-as-asked`; what the user asked to be remembered about how much help they want
  (`memories.helpWanted`) with every answer a model words. A question about writing for NVDA that finds
  nothing says how to get the guides when they are not on the computer.
- **Add-ons** (`claw/addons.py`, `accesstools.installedAddons`): every installed add-on read from the running
  NVDA as plain data; `addon_info` without a name finds the add-ons that say they do what the user wants.
- **NVDA Coach** (`coach`): read from its source at 1.6.0. A hint, one step, a whole lesson, the list, the
  progress, or its own window, by the user's own words. Without it, "teach me how to" is answered by `look_up`.
- **NVDA's list of what is new** for its newest three versions, read from the file that comes with NVDA, asked
  only about what is new, changed or fixed.
- **The description window**: a question about a key is given the one NVDA command it is about.

How it was tested:

- `tests/test_guides.py` (plain, new): an indented example kept whole and its comment no heading; the list of
  contents left out; sentences without code; facts from items and rows and never from an example; which facts
  seven requests get, and that five get none; a name NVDA no longer has left out; guides kept by 1.1.0 read;
  the record, its age, deleting; the instructions chosen by where lines are from; three made-up add-ons asked
  what they do, one of them turned off; NVDA Coach's lessons from made-up files, ten requests sorted by how
  much help they ask for, a hint that does not give the step, the progress; the list of what is new with what
  is for developers left out; five commands and nine questions of the description window; where sixteen
  requests are sent; the skills chosen.
- `tests/test_nvda_stub.py`: `nvdaHas` on a made-up module; `update_guides` with a guide that has a fact;
  `guideLines` and `coderNotes`; `guides_info` and `remove_guides` saying no and yes; `addon_info` with a wish;
  `coach` without the add-on (by name, and "teach me", which goes on to `look_up`), with a stand-in for it
  (hint, step, list, its command run once), and with it turned off.
- `python tests/run_all.py`: all 24 files pass.
- **The real guides.** The two guides were fetched once by hand on 2026-11-18 from the two addresses in
  `guides.SOURCES` and kept with the new code: 96 and 120 sections, 98 facts. The copy VisionClaw 0.8.0 had
  downloaded on the owner's computer on 2026-11-17 was read with the new code as well: 213 sections, 98 facts.
- **NVDA Coach's real lessons.** Its six English lesson files were read from its repository: 45 lessons in six
  chapters, as its own description says. Eleven requests found the right lesson ("the speech rate" finds
  "The Synth Settings Ring", "the NVDA menu" finds "Meet Your NVDA Key").
- **NVDA's real list of what is new** on this computer (2026.3.1): 22 sections, 117 passages from three versions.
- `tests/live_addon_guides.py` with Qwen2.5 Coder 1.5B writing and Qwen3.5 9B reviewing. First run, six
  add-ons, every fitting fact given: with the guides 4 of 5 passed, without them 4 of 5. "Beep when a link gets
  the focus" passed without and failed with (the line about api.getFocusObject led to a key command); "tell me
  when the name of the focused control changes" failed without and passed with (the line named the event).
  Second run, nine add-ons, after facts the model is told anyway were left out: two requests got a line, and
  both passed with and without it. **So: no harm any more, and no gain measured.** VisionClaw's own notes
  already name what everyday add-ons need. Two failures have nothing to do with the guides and are left for
  phase 5: the name-change add-on is written as a key command, and the live-region add-on does not use
  event_liveRegionChange.
- `tests/live_followup.py` with Qwen3.5 9B, three runs. First, with lines of the user guide and the developer
  guides: the title right where it had been made up; the status bar wrong (the text was cut so that another
  row's key was left); a line that was not about the question repeated as the answer; and for a question about
  add-ons an invented key where the model had said before that the picture does not show this. After the
  narrowing to one named command with a key: the title, the status bar and the NVDA menu went from a made-up
  key ("Alt and then S", "Control plus F10", "Control plus Alt plus M") to the right one; a command that was
  not the answer was ignored once ("move the mouse to this button") and repeated once ("copy this text" got
  NVDA's review copy, NVDA+F10, where Control+C is meant); questions about the picture were asked as before.

Free help and training material, researched on 2026-11-18 by fetching every address; nothing was added:

- Clearly licensed (GPL v2 or later): only NVDA's own documentation. It is on the computer already, in the
  user's language. `download.nvaccess.org/documentation/` also has it in 52 languages and for older versions.
- Free to read, for blind users, no licence stated: the NVDA wiki on GitHub, among it "Switching from JAWS to
  NVDA", "Switching from Window-Eyes to NVDA", a FAQ that calls itself out of date, and working the Office
  ribbon. The host is one VisionClaw may already ask (`raw.githubusercontent.com`).
- Free to read, all rights reserved: the American Foundation for the Blind's "Learn NVDA" lessons as
  transcripts (2016; the page says "we encourage you to share them"), Hadley's NVDA Screen Reader Series as
  transcripts, the California School for the Blind's practice lessons, NV Access's Get Help page.
- For testers and developers, clearly licensed: WebAIM's NVDA article and list of keys (free with credit),
  the Accessibility Developer Guide (MIT).
- Not to be used: NV Access's Basic Training (paid; its free sample forbids reuse), Deque University (forbids
  copying), and sites that answer programs with a challenge (OpenLearn, Pressbooks, Mozilla Support).

**Not tested, and not known:** anything of this inside NVDA. `nvdaHas` on NVDA's real modules, where a module
that makes names when asked cannot be told. The `coach` tool with the real NVDA Coach installed: finding it
among the add-ons, its lessons' folder in the installed add-on, its progress file, and running its command,
which in Excel is left to NVDA. Lessons of NVDA Coach in other languages, where "Press Enter to continue" is
worded differently and stays in a step. `installedAddons` with the owner's 20 add-ons: how long reading every
help page takes on each request. Whether the suggested small vision model keeps to the command it is given in
the description window: only the 9B model was on the computer. Whether a larger coder model gains from the
lines of the guides. Skills and the memory of how much help is wanted were not measured with a model.

## Free training material, everything as Markdown, a hand on the mouse (1.3.0, 2026-11-18)

The owner said yes to three sources of free training material by name, the NVDA wiki, AFB and Hadley, and
asked that the user can request them through VisionClaw and that skills, retrieval, memory and system prompts
make use of them; that all guides, wikis and other material be kept as Markdown files; and that VisionClaw
adapt, also to the times a blind user works a game controller or a real mouse. Three tools and three recipes
more, which makes 74 tools and 69 recipes: `update_training`, `training_info`, `remove_training`. Three
skills more, 49 in all. New files: `claw/training.py`, `claw/helpfiles.py`, `tests/test_training.py`.

- **Training material** (`claw/training.py`): 18 pages. Six of the NVDA wiki (coming from JAWS, coming from
  Window-Eyes, the ribbon of Office, which programs work with NVDA, more voices, the log), kept as the
  Markdown they are; the eight lessons of AFB's "Learn NVDA" from 2016 and Hadley's four workshops, as the
  transcripts on their pages, without the sites' menus, players and offers. The wiki's FAQ was left out: it
  says of itself that it is out of date. Every file says at its top where it is from and whose it is.
- **Asked for in words**: "get the free NVDA training material" asks first, naming every site and the 18
  requests, whatever the settings say. "Which training material do I have", "open the training material
  folder", "delete the training material".
- **Retrieval**: a source of its own after NVDA, the program, the window and Windows; every page asked only
  about what it is about. What VisionClaw remembers about the user opens a page too: "I come from JAWS", said
  once, is kept without being asked for, and the page for people from JAWS is then asked for every question.
- **System prompt**: `prompts.TRAINING_HELP`, chosen when an answer is made from the material.
- **Skills**: `training-material`, `coming-from-another-screen-reader`, `hand-on-the-mouse`.
- **Everything as Markdown** (`claw/helpfiles.py`): NVDA's user guide, its list of what is new and each
  add-on's help are turned into Markdown files in the folder `help` of VisionClaw's data the first time they
  are asked, made again when the page they came from is newer or another one, and read from there. This also
  ends the reading of every add-on's page of help on each request about add-ons.
- **A skill can take the place of another** (`instead of:`): `hand-on-the-mouse` instead of
  `mouse-from-keyboard`, so that a user with a hand on the mouse is not told to use the keyboard.

How it was tested:

- `tests/test_training.py` (plain, new): only the three sources, 18 addresses over https from the servers
  named; the question; a made-up lesson page kept without menus, form, player, offers and speaker marks, and
  a teaser left out; files with where they are from; a page that is not the page, and a site that cannot be
  reached, leaving the earlier copy; passages with their gates, asked with and without the word JAWS, with and
  without a memory that names it, with and without "teach me"; the instruction chosen for every source; five
  things a user says about themselves kept; eleven requests sent to the right recipe; the skills chosen and
  the one that takes another's place; a page of help kept as Markdown, read again without being made again,
  made again when the page changes or is another one, and read as it is when the file cannot be written.
- `tests/test_nvda_stub.py`: `update_training` saying no and yes with a stand-in for the internet, the servers
  and the size limit handed to the download; `training_info`; `look_up` giving a lesson only to "teach me",
  and the page for people from JAWS only once VisionClaw remembers it; the user guide and the stand-in
  add-on's help written as Markdown files; `remove_training`.
- `python tests/run_all.py`: all 25 files pass.
- **The real pages.** All 18 were fetched once by hand on 2026-11-18 and kept with the new code: 4 to 30
  kilobytes each, 539 passages. Seventeen questions were asked of them together with NVDA's real user guide
  and every real command: questions that name JAWS, Window-Eyes, the ribbon, voices or the log were answered
  from the wiki; "teach me how to move around a web page" from AFB's lesson on the internet; ordinary
  questions from NVDA's own help as before. Which passage of a spoken lesson is picked is rough: a transcript
  is talk, and the piece found is sometimes beside the point.
- `tests/live_orchestrator.py` with Qwen3.5 9B and Qwen2.5 Coder 1.5B, before the three training recipes were
  added: 115 requests, all done, none failed. "Which developer guides do I have", "Delete the developer
  guides", "Give me a hint about browse mode", "Coach me on reading the current line", "Open NVDA Coach" and
  "Is there an add-on that tells me the date" each went to the right recipe, both models agreeing.
- The same run again after the three training recipes were added: 120 requests, all done, none failed. "Get
  the free NVDA training material", "Which training material do I have" and "Delete the training material"
  each went to the right recipe, both models agreeing. "I am using my real mouse. How do I hear what is under
  the pointer?" was answered with NVDA+M for mouse tracking and NVDA+control+M for the mouse settings, and was
  not sent back to the keyboard: the skill `hand-on-the-mouse` reached the answer. "I'm coming from JAWS. What
  is the JAWS cursor called in NVDA?" was answered "The information provided does not state" this, which is
  right for this test: its stand-in for `look_up` has no page of the wiki, so the model said so instead of
  guessing. With the wiki downloaded, in NVDA, that question is not tested. `downloads_info` was added after
  this run had started and was not in it.

**Not tested, and not known:** anything of this inside NVDA. The add-on's own download code (`net.fetchText`)
has not fetched the 18 pages; afb.org and hadleyhelps.org may answer it differently than they answered a plain
request. How the answers read when a model words a passage of a transcript: only which passages are found was
looked at. The skills `hand-on-the-mouse`, `coming-from-another-screen-reader` and `training-material` were
not measured with a model. Whether a lesson from 2016 contradicts NVDA 2026 anywhere: the instruction says
NVDA's own guide is right, and that was not measured either. Turning the user guide into Markdown takes a
moment the first time a question is asked; how long inside NVDA is not known.

## Guides that come with every build (1.3.0, 2026-11-18)

The owner asked that all guides and all training material, being Markdown, be included with every build.
What each owner allows was read the same day. Shipped: the NVDA Developer Guide (NV Access; GNU General Public
License, version 2 or later; `copying.txt` in the folder it is downloaded from), 96 sections, 108 kilobytes,
in `claw/shipped/guides`, with its owner and licence in its first line. Not shipped, and why: the NVDA Add-on
Development Guide (the repository nvdaaddons/DevGuide has no licence file and GitHub reports none; its page
asks to respect its authors' copyright), the NVDA wiki's pages (no licence stated), AFB's lessons (copyright
AFB) and Hadley's workshops ("All rights reserved"). Those four are downloaded when the user asks, as before.
No owner has been asked for permission yet.

- `guides.MAY_SHIP`, `guides.shipped`, `tools/update_shipped_guides.py`, a check in `build.py`.
- A user who downloaded nothing has 95 sections of the Developer Guide for questions, and 2 single facts for
  the writing of add-ons: nearly all facts are in the Add-on Development Guide, which is not shipped.
- Tested: `tests/test_guides.py` part 10 (only what `MAY_SHIP` names is in the folder; the file's first line;
  read without a download; a downloaded copy used in its place and the shipped one back after deleting; a
  file that may not be shipped is never read from the folder), and in `tests/test_nvda_stub.py` `guides_info`,
  `remove_guides` and `search_help` with the shipped guide. `build.py` itself was not run, so as not to write
  over the 1.2.0 package in `dist`; that it packs every file under `addon` was read in its code.

## Telling the user what can be downloaded (1.3.0, 2026-11-18)

The owner asked that the user be able to find out what VisionClaw can download for them. New: `claw/offers.py`,
the tool and recipe `downloads_info` (75 tools, 70 recipes), the button "What VisionClaw can download for you"
in the settings, `orchestrator._offered`, the file `offered.json`.

- **Asked for**: "what can you download for me" gives the overview, said as it is: the developer guides, the
  training material, notes on a program, a newer version, newer models, which of it is here, the words for each.
- **Told once**: one sentence after an answer that it fits, each said once ever.
- Tested in `tests/test_training.py` part 7 (the overview; nine sentences the user is told to say, each sent
  to the recipe it names; each offer said once, also in another session; nothing offered that is here, after a
  request about downloading, or after a change of a setting; a file that cannot be written) and in
  `tests/test_nvda_stub.py` (the tool; the sentence after a request that was done, not a second time, not
  after one that failed).
- **Not tested:** the button in the settings and its window, which need NVDA; the sentence spoken at the end
  of a real answer; `downloads_info` among the recipes the real models choose from, which was added after the
  last run of `tests/live_orchestrator.py` had started.

## The data folder inside the add-on, and a portable copy (1.4.0, 2026-11-18)

The owner asked that everything VisionClaw keeps go inside the add-on's folder, and for a button in the settings
that makes a portable copy with all of it, "no exceptions", whatever its size.

- Where NVDA deletes an add-on's folder was read from NVDA's own source (`source/addonHandler/__init__.py` on
  GitHub, 2026-11-18): an update is unpacked into `visionClaw.pendingInstall`; at the next start the old folder
  is removed after the old copy's `onUninstall`, then the new one is renamed into place. NVDA's "Create portable
  copy" with the user's configuration copies the whole configuration folder (`installer.copyUserConfig`), add-ons
  included.
- `tests/test_portable.py`, plain Python: merging keeps this computer's file where both have one; moving in at
  start; an update carries the data into the pending folder, also when the new copy brings data of its own; a
  removal keeps it in the configuration folder; a pending install that is taken away keeps nothing;
  `installTasks.onUninstall` itself, loaded as NVDA loads it, with stand-ins for NVDA's modules; every file of
  the data folder in the copy, a new one added later included; FAT32 and room; finding a portable NVDA and
  refusing an installed one; the settings taken over once and only by a VisionClaw with no models; a whole
  `.nvda-addon` file read back and unpacked; stopping leaves nothing; copying into a portable NVDA and copying
  again skips what is there. Passes.
- `tests/test_portable_window.py`, the real wxPython 4 with stand-ins for NVDA's gui: what the window says goes
  in, with a folder it has no name for; every refusal and question; what is said when done or stopped. Passes.
- `tests/test_nvda_stub.py`: the real plugin moves what is in the old folder into its data folder at start,
  keeps its own file where both have one, and takes over carried settings. Passes.
- A real file of 1.1 GB, random bytes, put into a `.nvda-addon` file by `portable.writeBundle` (zip64) in about
  a second and unpacked again with Python's zipfile, as NVDA unpacks: the same SHA-256.
- **Not tested:** nothing of this has run inside NVDA. Not the move of the owner's 8.6 GB at the first start,
  not an update carrying the data, not the window in NVDA, not a copy of the real data folder, not installing
  such a file on another computer, not starting VisionClaw from a portable NVDA on a flash drive. The 4 GB check
  reads the drive's file system from Windows; it was not tried on a real FAT32 drive.

## The computer itself, several things in one request, a named control, and the router (1.5.0, 2026-11-18)

**What failed in real use.** The owner asked, with Qwen3.5 9B doing both jobs: "first, look at my screen. If you
see recycle bin, open it." Both parts were sent to describing the screen, and the answer ended "To open it,
press the Enter key": nothing was opened. Then: "check and see if my recycle bin needs to be emptied or not."
That was sent to the look-up, which answered with a memory, "See if it needs to be emptied or not (this
follows: Check your recycle bin)": an earlier request about the Recycle Bin had been kept as a memory instead
of being done. The cause was the same both times: VisionClaw had no tool that acts on the computer itself, so
the model chose the nearest thing it was offered. The owner then asked for many more such tasks, for several
things in one request, for work inside a program's own settings, and for a router.

**What exists now.** Twelve tools and nine recipes in `computertools.py` and `controltools.py`, with their
logic in `claw/computer.py` and `claw/controls.py`: `find_thing` and `open_thing`, `recycle_bin`,
`empty_recycle_bin`, `system_volume`, `list_windows` and `window_action`, `find_files`, `computer_info`,
`power`, `check_seen`, `set_control`. `web_open` takes a browser the user names. `planner.plainSplit` splits a
request of up to eight things by plain rules; `planner.conditional` puts a check before the steps that depend
on it; `claw/router.py` decides what a model is offered, and `planner.decided` what no model is asked about.
Two skills, `work-the-computer` and `control-in-a-program`, and the notes `visionclaw-computer.md`.

| Test | What it shows | Result |
|---|---|---|
| `tests/test_computer.py`, plain Python | What is to be opened and which found thing is meant; that a place of Windows is only ever opened by what is fixed in the code; the Recycle Bin's sentences and when emptying is called worth it; the computer's volume and its floor of 10 percent; locking and shutting down, and that nothing of NVDA's, a program's or a website's is meant; which window the words name; files by folder, kind and name; eleven requests that depend on something and four that are left alone; 14 requests split by plain rules and 12 left to the model; 62 requests and the recipe their words point to, among them every older one whose words could have been taken by a new recipe; the router with and without a browser, a controller and a part before; whole requests with stand-in tools and a scripted model, among them the owner's five | passes |
| `tests/test_nvda_stub.py`, new part | The real tools against a made-up Windows: a place, a program and a file found and opened; a no from the user; Windows refusing; the Recycle Bin checked, and emptied only after a question that is asked whatever the settings say; the volume turned down, held at 10 percent, refused to mute without braille and asked about with braille; a window closed by the user's words whatever the model wrote, one that stays open said to be open, Escape offered for a panel that is no window; files, facts, and a restart that is always asked about; whether something is on the screen by NVDA's names, by the text shown and by the model; a check box on another page of a dialog with tabs turned on, with the page named; a slider turned up and to its end; a control that is nowhere, with the page that was shown shown again; the owner's first request through the real tools with one model for both jobs: one question to the model in all | passes |
| Reading from the real computer (Windows 11, build 26300), with plain Python and stand-ins for NVDA's modules only | The Recycle Bin (it was empty: 0 items), the volume (20 percent, not muted), the drives, the memory, the time the computer has been on, the open windows, the user's folders from the registry, 166 programs of the Start menu and Windows' Apps folder and 41 things on the desktop, and which browsers are installed. `SHQUERYRBINFO` is 24 bytes in a 64-bit program, as the header says | worked; nothing was opened or changed |
| `tests/live_orchestrator.py`, Qwen3.5 9B for both jobs as the owner has it, one small question at a time, stand-in tools, the 24 new requests | The owner's five requests and 19 more: opening by name, the Recycle Bin, the volume, windows, files, facts, a restart, three things that depend on something, a named control | 24 of 24 handled the right way. "Check and see if my recycle bin needs to be emptied or not" now answers in 0.0 seconds with no model asked; "first, look at my screen. If you see recycle bin, open it" in 14.9 seconds, of which the look takes nearly all. In the first run the model had to ask the user twice: after "go to gmail.com" it sent "tell me how many emails I have" to describing the screen, twice, and after a click it sent "turn the volume up a bit" to NVDA's settings, twice. Both are now decided by plain code (`planner.decided`) |
| The same, all 145 requests of `tests/live_orchestrator.py`, the same model and settings | Whether the router, the plain splitting and the new recipes made any older request worse | All 145 were carried out and every answer was read. Each of the 121 older requests went to the kind of request it should, and every one of the 68 kinds was still reached by the requests that are for it: no kind was shut out by the router. No run of the older requests without the router was made on this day to set beside it, so "no worse" rests on reading the answers, not on a comparison. A model was offered 12 kinds of request on average, of the 68 the stand-ins make possible, and 19 parts were decided by the words alone. Four times the model's choice differed from what the words point to after a second look, and the user was asked: "How do I bake a cake?", "Name the focused button Share on this website", "Give me a hotkey for the gain knob", and the second half of "Do a deep query of this control and tell me how a sighted person works it". The first two were known before; none of the four is about the computer. Weak answers that are the stand-ins' or the look-up's, not the router's: "I'm coming from JAWS. What is the JAWS cursor called in NVDA?" found nothing that answers, because the live test has no training material, and "Tell me when the inbox count changes" made a fix with a muddled name. The whole run took 213 seconds of work |
| `python tests/run_all.py` | Every plain-Python test, 28 files | passes |

**What the router changes, measured.** For "Make NVDA speak a little faster" a model is offered 9 kinds of
request of the 68 the live test's stand-ins make possible; for the parts of the owner's long request 10, 18
and 14. Seven of the 24 new requests are decided by the words alone and take no model call to plan.

**Not tested, and said in the release notes.** Nothing of this has run inside NVDA. Opening a thing, emptying
the Recycle Bin, changing the volume and muting, switching to, closing, minimizing and maximizing a window,
Escape for a panel, locking, sleeping, restarting, shutting down and signing out have only met stand-ins: the
calls to Windows are written from Microsoft's pages and the SDK's headers, and only those that read were run.
`set_control` has only met stand-in controls: a real dialog with tabs, a real slider through UI Automation,
the keyboard way for a slider without it, and the whole of the way through a window's picture are untried.
What a web page such as Gmail gives NVDA to read, and so whether "how many emails do I have" is answered, was
not tried; the stand-in page has no mail. `check_seen` was not tried on a real desktop: whether Windows' text
recognition reads the names under desktop icons, and whether NVDA gives the icons' names when another window
is in front (then only the text and the model are left).

## The user's own files (1.6.0, 2026-11-18)

Asked for by the owner right after 1.5.0: creating, renaming, moving and deleting files. One tool, `change_file`,
and one recipe, `file_task`; the logic is `computer.fileTask`, `cleanName`, `renamed` and `bestFiles`. Which file
is meant is found by the search that `find_files` uses, by the words of its name; a model writes nothing, and
where several files fit, the tool itself asks the user which. The recipe is decided by the words alone.

| Test | What it shows | Result |
|---|---|---|
| `tests/test_computer.py`, new part | Twelve requests and what each asks for; fifteen that delete, move, copy or rename something else and are left alone ("delete the notes on this program", "copy the window title to the clipboard", "move to the next heading"); names Windows does not take; the ending kept on a rename; the file that is named exactly shutting out those that only have the word | passes |
| `tests/test_nvda_stub.py`, new part | The real tool and the real search on real files in a folder of the test's own that stands for the user's folders: a folder and a text file made; a second one of the same name refused; a rename with the ending kept; a rename onto an existing name refused; a move to a folder of the user's and to a folder inside it by its name; a copy; a folder not copied; deleting asked about whatever the settings say, a no leaving the file, a folder's question saying how much is in it; no such file, no name, and several that fit with "None of these"; the list of changes; three renames and moves and one made file put back by "undo that" | passes; the Recycle Bin was stood in for |
| `tests/live_orchestrator.py`, Qwen3.5 9B for both jobs, one small question at a time, stand-in tools | Seven file requests, one of them two things in a row, and six older requests with words that could be taken for a file's ("Delete the developer guides", "Delete the training material", "Forget that", "Copy the window title to the clipboard", "What did you change", "Undo that") | 13 of 13 handled the right way; the seven file requests took no model call |

**Not tested.** `computertools.recycle` calls Windows' `SHFileOperationW` with a structure read from the SDK's
header; it has never been called for real, so whether a file really lands in the Recycle Bin is untried. A file
that is open in a program, a file on another drive, a very large folder, and a name in another script than
Latin were not tried. Nothing of this has run inside NVDA.

## Compared with JAWS 2027's AI tools; a web page explored, and what stops a form (1.6.0, 2026-11-18)

The owner's goal, said on 2026-11-18: VisionClaw is to be more powerful and more useful than Vispero Companion
(formerly FSCompanion) and the other AI tools of JAWS 2027. What JAWS does was read, not remembered: from the help
of the JAWS 2027 installed on this computer (`JFW.chm`, its What's New page last updated on October 19, 2026; the
pages are named in `CLAUDE.md`), from Vispero's own post "Download JAWS, ZoomText, and Fusion 2027", and from
Double Tap's article of October 27, 2026. Nothing of JAWS's help was copied into VisionClaw.

**What JAWS 2027 has, by its own help, and where VisionClaw stands.** "Not run in NVDA" is said where that is so;
see "What was not tested".

| JAWS 2027 | VisionClaw |
|---|---|
| Vispero Companion answers questions about JAWS, Windows, web browsing, Microsoft Office and Google Workspace, with keystrokes. Through Vispero's cloud. | `look_up` answers from NVDA's own user guide and commands, the program in front, its window, Windows' keys, notes on common programs, free training material, the user's library and memories. On this computer. Thinner than JAWS on Office and Google Workspace: `app-office.md` and `app-browsers.md` are short notes, where Vispero has years of training material. |
| The new Companion (Early Adopter Program, United States only, needs a Vispero account and the internet): one conversation; no list of earlier conversations. | No account, no country, no internet. Memories are kept between sessions as files the user can read and delete. A request that follows another in one sentence is understood, and since 1.7.0 a request that follows the one before it as a new request too: "do that again", "the other way", "and the pitch?", "open the second one" (`claw/followups.py`); the user is told how it was understood. Kept while NVDA runs, not between sessions. |
| Page Explorer: a summary of a web page, its important links, and tips for moving on it. | New: `explore_page` (below), with only those NVDA keys that fit the page; `read_page` answers and summarizes; `page_outline`, `go_to`. No model is needed for the layout. |
| Picture Smart: describes a picture file, a control, the window, the screen, a slide or a video frame; two services to compare; follow-up questions; a scanner or camera. | Describing the focus, window, screen, pictures in File Explorer and chat photos, with follow-up questions, from VisionMate. One local model, so no second opinion from another service. No scanner or camera. |
| Companion Actions: finds an unlabelled button, makes sense of an error message, explains a cluttered screen, works through a task. Stays in one application. | Clicking by name from the window's picture, naming controls for good, the deep inspection, lasting fixes, add-ons written on request, the mouse, touch, pen and controller from the keyboard, and since 1.5.0 the computer itself across programs. New: `form_trouble` (below). |
| Changes JAWS settings by asking, everywhere or only for the application in use. Not yet: advanced braille settings, Speech and Sound Schemes, Voice Profiles. | Changes any NVDA setting by asking, the settings of the synthesizer and braille display in use, switches drivers safely, and undoes every change. Since 1.7.0 also only for the program in front, kept in NVDA's own configuration profile for it, which VisionClaw makes after a question; listed, undone and removed in words. Not run in NVDA. |
| Asks before important steps; Escape stops; checks in on long tasks. | Asks before every change unless the user turned that off, always before what could silence NVDA; the stop command; progress spoken at every step. |
| A voice of its own for the Companion. | Since 1.7.0: "customise VisionClaw's voice" opens NVDA's own Speech settings for it; any synthesizer, voice, rate, pitch and volume, used for VisionClaw's words alone. Not heard in NVDA yet. |
| Dictation in the Companion; the voice assistant "Hey Sharky" (Microsoft's cloud). | Since 1.7.0: NVDA+Alt+V, with the speech model Qwen3-ASR on this computer; nothing that is said leaves it. What was heard is read back before anything is done. No wake word: a key starts it. Tested with synthetic voices only. |
| Face in View: whether the face is in the camera's picture and well lit. | Missing. |
| Auto Graphics Labeler: names graphics from their tooltips. | Names from the page's or program's own code, or from the picture, kept for good as data. |

**What VisionClaw has that JAWS's help does not describe at all:** everything on the user's own computer with
nothing sent anywhere; add-ons written, checked and repaired on request; fixes for a website or program that
stay; arrow keys for dragged controls; fingers, pressure, games that read the mouse directly and a game
controller; learning about a program and keeping notes; skills the user makes in words; a portable copy.

**Built on 2026-11-18 for 1.7.0**, the first four points of the list below as it stood for 1.6.0: a setting for
one program, follow-up requests, a date in a calendar, and asking by voice; and, asked for the same day,
everywhere or only here, working through a task, a voice of its own, and two add-ons used. See the section "A setting for one
program, follow-up requests, a date in a calendar, asking by voice". Vispero's example of an action was
"selecting a date in an inaccessible calendar date picker"; `pick_date` is VisionClaw's answer to it.

**Still to build to be ahead on every point**, in the order of how much each matters against JAWS:
- Everything of 1.7.0 run inside NVDA, the setting for one program first (`docs/TESTPLAN.md`).
- Deeper notes on Word, Excel, Outlook, PowerPoint and Google's programs, from sources that may be used.
- A camera's picture described before a call.
- The JAWS Migration Assistant and ClassicSpeech installed, and VisionClaw's tools for them run for real.
- A wake word, as JAWS's "Hey Sharky" has; today a key starts listening.
- Follow-ups that know more than the one request before, and that are kept between sessions if the user wants.
- A date control that opens no calendar, and a calendar whose month is chosen in a combo box.

The list as it stood for 1.6.0, kept for what was read from NVDA's source then:
1. A setting changed only in the program in front, through NVDA's configuration profiles. Read from
   `config/__init__.py` of NVDA's release-2026.3 branch on 2026-11-18, and to be read again before building:
   a change (`config.conf[...][...] = value`) is written to the profile activated last (`self.profiles[-1]`,
   `AggregatedSection._getUpdateSection`); `createProfile(name)` makes an empty profile and raises ValueError
   when the name is taken; a program's trigger is kept in `config.conf.triggersToProfiles` and saved with
   `saveProfileTriggers()`; `manualActivateProfile(name)` puts a profile on top, and with None takes the
   manual one off again; the sections in `BASE_ONLY_SECTIONS` (general, update, development, addonStore, remote,
   math, screenCurtain) cannot be in a profile at all. Not read yet: `appModuleHandler` (how a program's
   trigger is written, thought to be "app:" and the program's name, and when it is entered), and
   `gui/configProfiles.py` (what NVDA itself does after a trigger was added while the program is in front).
   Open questions that need a run in NVDA: whether a new profile takes effect at once or only when the user
   comes back to the program; how undoing such a change finds the profile again when the user is elsewhere
   (`claw/changes.py` would have to keep the profile's name). Not built today, because a mistake here changes
   how NVDA speaks in a program without the user knowing why.
2. A follow-up request that knows the request before it ("and the second one?", "do that again in Word").
3. Dates in calendars that cannot be worked with the keyboard, which Vispero names as an example of an action.
4. Speech in: asking by voice with a local model (phase 6.2).
5. Deeper notes on Word, Excel, Outlook, PowerPoint and Google's programs, from sources that may be used.
6. A voice or pitch of its own for VisionClaw's answers; a camera's picture described before a call.

**Built on 2026-11-18** (`claw/pageview.py`, `pagetools.py`, `tests/test_pageview.py`):

- `explore_page`: a web page as a whole, from what NVDA keeps of it in browse mode. What it has, its landmarks
  in order with their names and links, where the main part begins, how its headings are spread over the levels,
  the first headings, the links of its navigation, its form fields, and then which of NVDA's keys move best on
  this page, the best first, and only keys for what the page has. Plain code; no model; nothing sent.
- `form_trouble`: why a form will not send. Fields the page marks as not valid, fields that must be filled in
  and are empty, a group of radio buttons of which one must be chosen and none is, and the page's own error
  messages, each with the field it stands next to; then NVDA's reading position is on the first of them.
  Where the page tells NVDA nothing, the text in the page's picture is read for lines that say what is wrong.
- "Summarize this page" with a model that is asked one small question at a time (the owner's own setting): the
  answer was "What was looked up does not mention summarize". Now plain code gives the beginning of each part of
  the page in the page's own words (`pageview.gist`, `orchestrator._quoted`).
- `page_outline` now means the headings alone; "how is this page laid out" goes to `explore_page`. "Layout" and
  "structure" no longer point at a page where the words name the keyboard, a window, a document or a table:
  before, "change the keyboard layout to laptop" pointed at the page's headings.

Tested, and how:

- `tests/test_pageview.py` (plain Python, the stand-in web page of the inspection, widened with NVDA's own names
  for kinds of control and states): a well-built page, a bare one, links only, a main landmark with and without a
  heading at level 1, a form alone, a very long page shortened to fit; a form with twelve kinds of field in and
  out of trouble; messages put with the right field or with the whole form; a message inside a message; nothing
  found; lines from the picture; the two tools through stand-ins for NVDA, read a stretch at a time, with the
  reading position moved and a page in focus mode put back into browse mode; a picture that cannot be read and
  a position that cannot be moved. Every key named was found in the user guide of the NVDA 2026.3.1 installed
  on this computer, which the test asks again every time it runs here.
- `tests/test_nvda_stub.py`: both tools through VisionClaw's real registry on the stand-in feed page.
- `tests/test_core.py`: sixteen sentences sent to the right job by their words, five that must not be.
- With the real model, Qwen3.5 9B for both jobs, asked one small question at a time (the owner's settings), in
  the bundled engine on the GeForce RTX 5060, with stand-in tools (`VC_ONLY`, 12 requests of
  `tests/live_orchestrator.py`): "Explore this page for me", "What is the best way to get around this page?",
  "How is this page laid out?" went to `explore_page`; "Why won't this form submit?" and "Which fields did I
  miss in this form?" to `form_trouble`; the headings, a question about the page, typing into the search box,
  moving to a heading and the two lasting fixes went where they went before. No question to the user, 0.5 to
  6.6 seconds each.
- The whole of `tests/live_orchestrator.py`, 158 requests, the same model and settings, with the file tasks and
  the pages and forms both in place, run once on 2026-11-18 before the release: all 158 were carried out and
  every answer was read. The six requests for pages and forms and the seven for files went to their own jobs.
  The user was asked four times, the same four as in the run for 1.5.0 ("How do I bake a cake?", "Name the
  focused button Share on this website", "Give me a hotkey for the gain knob", and the second half of "Do a
  deep query of this control and tell me how a sighted person works it"), and the two weak answers named there
  are unchanged (the JAWS cursor, the inbox count). No run without today's changes was made to set beside it,
  so "no older request got worse" rests on reading the answers and on the notes of the earlier run.

## A setting for one program, follow-up requests, a date in a calendar, asking by voice (1.7.0, 2026-11-18)

The owner asked for the four things that were listed as still missing against JAWS 2027 ("add all that stuff into
visionclaw as well. I want it to be better than jaws2027"). What was built, what it rests on, and what was tested.

**An NVDA setting only for one program** (`claw/profiles.py`, `profiletools.py`; phase 3.50).

- The two parts of NVDA's source that had not been read were read on 2026-11-18, branch release-2026.3:
  `appModuleHandler.py` (a program's trigger is `AppProfileTrigger(appName)`, whose spec is "app:" and the name of
  the program's file; `handleAppSwitch` makes one and calls `enter()` when the program gets the focus, keeps it on
  the program's module as `_configProfileTrigger`, and calls `exit()` on it when the program loses the focus) and
  `gui/configProfiles.py` (NVDA's own New Profile window calls `createProfile`, sets `triggersToProfiles[spec]`,
  calls `saveProfileTriggers` and `enableProfileTriggers`, and then relies on the program getting the focus
  again). With `config/__init__.py`, read again: a triggered profile does not apply while triggers are disabled
  or suspended; a profile turned on by hand always stays on top.
- So the two open questions have these answers from the source: a profile that was only just made does not apply
  until its program gets the focus again, and VisionClaw therefore enters the program's trigger itself, as
  `handleAppSwitch` does; and undoing is done only while the program's profile is the one NVDA writes to, with the
  profile's name kept in `changes.json`.
- "Only in this program", "just in this app", "only here", "when I'm in Word", "in Notepad only" are read from the
  user's own words by plain code; the recipe stays `change_setting`. Two new jobs: `program_settings` (which
  programs have settings of their own) and `remove_program_settings` (always asked about).
- Before a profile is made the user is told and always asked. Nothing is written unless the program's profile is
  the one NVDA writes to at that moment. Refused with a reason, and nothing changed: a named program that is not
  in front, a setting NVDA keeps the same everywhere, a profile turned on by hand, triggers switched off, an NVDA
  that keeps nothing on the computer, NVDA's own window in front.

**Requests that follow the one before** (`claw/followups.py`, `orchestrator._follow`; phase 3.51). Plain code
writes out: the same again, a bit more, the other way and "too fast", the last answer said again, the same in
another program, "the second one" from the numbered list of the last answer, and "and maximize it". A model
writes out the rest ("and the pitch?", "click the third one", "open it"), with a question of its own for each kind,
and plain code checks every word against what was said. The answer begins "Understood as: ...". Kept only while
NVDA runs.

**A date in a calendar that takes no keys** (`claw/dates.py`, `datetools.py`; phase 3.52). `pick_date` reads the
date from the user's words, typed or spoken; finds the calendar in the web page, the window, or the window's
picture; presses its button for the next or previous month until the right month shows, reading the calendar again
after every press; presses the day; and says what happened.

**Asking by voice** (`claw/voice.py`, `voiceinput.py`, `voiceui.py`; phase 6.2). NVDA+Alt+V, or Alt+V in the Ask
window. The microphone is read through Windows' waveform-audio functions into memory; plain code tells when the
person has finished; the speech model Qwen3-ASR turns the recording into text in an engine of its own on the
processor, which is started for the recording and stopped again; the text is put into the request box and read
out, and only Enter sends it.

- The speech model. Read from Hugging Face's own listing on 2026-11-18: `Qwen/Qwen3-ASR-0.6B` and
  `Qwen/Qwen3-ASR-1.7B` are under Apache 2.0. Neither Qwen nor Unsloth publishes them as GGUF; `ggml-org`, the
  llama.cpp project, does (`ggml-org/Qwen3-ASR-0.6B-GGUF` at revision 928ab958, `ggml-org/Qwen3-ASR-1.7B-GGUF` at
  36a67868), as Q8_0 and bf16 only: **there is no Q4_K_M and no Q6_K**. The owner was asked "May VisionClaw offer it
  from ggml-org, and may I download the small one (about 1 GB) to this computer to test it?" and chose "Yes to
  both". ggml-org is allowed for the speech model only; `catalog.PUBLISHERS` is unchanged.
- The engine that is bundled (VisionMate 5.0.1's build of llama.cpp) took the model as it is: no newer engine is
  needed. Its own log says "audio input is in experimental stage and may have reduced quality".

The owner then asked for more, the same day, and it is in the same version:

**Everywhere, or only here** (phase 3.53). JAWS's help says its Companion "understands the difference between
changing a setting everywhere and changing it only for the application you're using", with the examples "Speak
words as I type in every application" and "Stop announcing capital letters in Word". Reading NVDA's source showed
what that means for NVDA: a change is written to the profile that is on, so once a program has settings of its
own, a change said there without a place lands in that program alone. Now "everywhere" writes NVDA's normal
configuration also while a program's profile is on, a program named with "in" alone is understood, the user is
asked where the words say neither, and the programs that keep a value of their own are named.

**Working through a task when the usual path is not clear** (`claw/guide.py`, `guidetools.py`; phase 3.54). JAWS's
What's New page, read again on 2026-11-18: the Companion can "work through a task when the usual path isn't
clear", only works when asked, asks before important steps, checks in on longer tasks, stays in one application,
and cannot operate its own window. `work_through` does this for NVDA: it reads what the program in front offers
(web page, window, or picture), ranks it by the user's own words, asks before every step with "only tell me" and
"stop" as choices, checks in after three steps, stops when another program comes to the front, and says what it
did. VisionClaw's own windows are off limits to every tool that works the window in front.

**A voice of its own** (`ownvoice.py`; phase 3.55). First built as a lower pitch; the owner asked instead to be
dropped into NVDA's Speech settings. Read from NVDA's source: `ConfigProfileTriggerCommand` applies a
configuration profile to a stretch of speech, as say all's own profile is applied. VisionClaw's voice is one
profile tied to a trigger of its own; "customise VisionClaw's voice" turns it on by hand, opens NVDA's Speech
settings, and turns it off again when they are closed.

**The JAWS Migration Assistant and ClassicSpeech** (`claw/partners.py`, `partnertools.py`; phase 3.56). Their
source was read on 2026-11-18 (jawsMigrator 1.63, MIT; ClassicSpeech 1.16, GPL v2). With the first, VisionClaw
says what a JAWS keystroke or command is in NVDA; with the second, it changes the verbosity level and the speech
and sound schemes by asking, which JAWS's help says its own Companion cannot do yet for JAWS's schemes and voice
profiles. Neither add-on has an interface for other add-ons, and neither was installed on this computer.

Tested, and how:

| Test | What it shows | Result |
|---|---|---|
| `tests/test_profiles.py` | 16 sentences that ask for one program and what is left of each without those words; 18 that narrow down something else and must not be taken for a program ("speak typed characters only in edit fields", "beep when I use caps lock"); whether a named program is the one in front; the profile's name; which requests remove or list; where 18 requests are sent and that each is offered; six requests kept whole or split with the scope words on every part that changes a setting; then `profiletools.py` against a stand-in that keeps profiles as NVDA's source says (`tests/profilestandin.py`): no program in front, a profile made and on top at once, the normal configuration untouched, the setting as it was in another program and the program's own on coming back, nothing written while another program is in front, a profile turned on by hand, triggers off, an NVDA that keeps nothing, a profile that NVDA does not turn on taken away again, a name that is taken, listing and removing | passes |
| `tests/test_nvda_stub.py`, new part | The real `set_setting`, `undo_change`, `list_changes`, `program_settings` and `remove_program_settings` through VisionClaw's registry on the same stand-in: the question before a new profile, asked with confirmations off; a second setting without a new profile; "only in Word" with Notepad in front; "only in my browser" ending in "This will apply in every program"; undo refused from another program and done in the right one; removing asked about | passes |
| `tests/test_followups.py` | 18 follow-ups plain code writes out and 11 it leaves to a model; 23 requests with "that", "it" or "and" that stand alone; the three time limits; turning a request round and towards a direction; things by their place in a numbered list, and a place the list does not have; what a model wrote, accepted and refused; six sessions of whole requests through the orchestrator with stand-in tools and a scripted model, one with a model that makes a file name up, one with a very small model that is never asked, one that does a stopped request again | passes |
| `tests/test_dates.py` | 26 ways of saying a date, typed and spoken, with "today" fixed, and 18 requests that name no date or no calendar; headings, days and buttons by their names; then calendars made up by the test that answer to presses (`tests/calendarstandin.py`): forward and backward and across a year, the right 30 where two are shown, days that say their whole date, a heading in three forms and in two places, a greyed-out day, a button that does nothing, a button that goes the wrong way, too far, no buttons, no heading, no calendar, a stopped request; the same calendar as a picture with the days given column by column, arrows on both sides, both at the right, both at the left, the wrong way round, and arrows that are text | passes |
| `tests/test_nvda_stub.py`, new part | The real `pick_date` through the registry: on a calendar of controls as NVDA would know a window's, and on one that is only drawn, read from stand-in text recognition and clicked with a stand-in mouse; the question; a no; a calendar that closes; a date that can be read two ways put to the user; a greyed-out day; no date; text recognition switched off; a window with no calendar; the mouse put back | passes |
| `tests/test_voice.py` | When speech begins and ends, on sound made up by the test: a pause that ends a request and one that does not, nobody speaking, someone who never stops, thirty seconds of speech in one piece, a click, a noisy room, a quiet voice, someone already speaking; the WAVE file; what is made of the model's answer; the two speech models with their pinned files, and that a fetched list can add neither a speech model nor ggml-org; keeping, choosing and removing them with a stand-in download; Windows' structures by their sizes; a whole spoken request with a stand-in microphone and engine, with nobody speaking, stopped early, not understood, no microphone, a failed engine; where 17 requests are sent | passes |
| `tests/test_nvda_stub.py`, new part | The real `voice_info`, `get_voice` and `remove_voice`: the question before a download, asked with confirmations off; progress said every ten percent; nothing downloaded twice; the model that is here used when the other was chosen; deleting asked about | passes; nothing was downloaded |
| `tests/test_ask_window.py`, with the real wxPython | The Ask window's voice button with a stand-in for asking by voice: the speech model offered when there is none, listening begun and stopped, what was heard put into the box and read out without being sent, a second go added to the first, a problem said as it is, a download stopped, and the window without asking by voice | passes; no microphone, no model, nothing shown on the screen |
| `tests/test_profiles.py` and `tests/test_nvda_stub.py`, for everywhere or only here | Seven ways of naming a program with "in" alone or not; six ways of saying every program; the write into the normal configuration while a program's profile is on, with "+10" read against the value everywhere and the program keeping its own; nothing written under a profile turned on by hand; which programs hold a value of their own; then the real tools: the question "only in Notepad, or everywhere?", each of its three answers, "in every application" without a question, three changes undone where each was made, and the sentence that Notepad keeps its own value | passes |
| `tests/test_guide.py` | Eight requests and what the user wants in each; five that are something else; ranking with the words menus use; then a mail program made up by the test: a model choosing between two ways and plain code sure of the next, "only tell me", "stop", a model saying none leads there, another program coming to the front, nothing about it, presses that bring up nothing, a check-in after three steps, the most steps, a stopped request | passes |
| `tests/test_nvda_stub.py`, new part | The real `work_through` on stand-in things of a window; five tools refused while VisionClaw's Ask window is in front, and NVDA's own settings window not taken for VisionClaw's; `own_voice`: no voice yet, the question, a no, the profile made and turned on by hand with NVDA's Speech settings opened, a setting written into that profile alone, the profile turned off when the window closes, VisionClaw's words carrying the trigger, turned off and on in words, removed after a question | passes |
| `tests/test_partners.py` | What the words ask of each add-on; neither job hinted at or offered without its add-on; then both tools against stand-ins with the names and shapes the add-ons' source has: the verbosity level changed, refused beyond the last level, a no; schemes listed, switched by name, the next one, turned off, a name that is none; a window opened; each change put back; a newer ClassicSpeech that keeps the level differently; a JAWS keystroke through to NVDA's command and keys; a key the map does not have; a command by name; what was brought over; no JAWS on the computer; a newer assistant | passes; the real add-ons were never called |
| `tests/live_voice.py`, Qwen3-ASR 0.6B Q8_0 in the bundled engine, on the processor alone, through `voiceinput.Ears` | 24 recordings: twelve requests, each spoken by Windows' own voices David and Zira at 16 kHz | 24 of 24 heard word for word, 1.4 to 1.9 seconds each from starting the engine to the text. Before it was told the name, it wrote "NVDA" as "Nvidia" |
| `tests/live_voice.py --mic`, on the owner's computer | `voiceinput.chunks` opened the default microphone for three seconds | Windows gave 29 pieces of a tenth of a second; all were silent (loudness 0 or 1). Nothing was kept or turned into text |
| `tests/live_followups.py`, Qwen3.5 9B | 13 follow-ups after a request and its answer | Four were written out by plain code (three by their place in a numbered list, "and maximize it" by the planner's rules) and one was taken to stand alone ("and open notepad"), so no model was asked for those five. Of the eight put to the model, seven were written out as wanted: "How do I read the status bar of this window?", "What is the pitch?", "Make NVDA speak a little louder.", "Turn off the typed words echo.", "click the Options", "What does NVDA+F12 do?", and "open budget old.xlsx" for "open it", which was a guess between two files. "read it" after a description of the window was written as "read The window". Before the questions were made smaller, the same model had copied 8 of 11 follow-ups back unchanged |
| `tests/live_orchestrator.py`, Qwen3.5 9B for both jobs, one small question at a time (the owner's settings), GeForce RTX 5060, stand-in tools | All 196 requests of the list, run once on 2026-11-18: the 38 new ones (a setting for one program, everywhere, a date, voice, working through a task, a voice of its own, the two add-ons taken to be running, and five sessions of requests that follow one another) and the 158 older ones. The jobs of the 180 requests that were also in a run before the two add-ons were added were compared with that run by a script | 196 of 196 were carried out, 0.0 to 29.1 seconds each. Every new request went to the job its words point to; the three that say the user is stuck, the dates and the computer's volume took no model call. The user was asked 5 times: what was meant by "How do I bake a cake?", "Name the focused button Share on this website.", "Give me a hotkey for the gain knob." and the second half of the deep-query request, the same four as in the runs for 1.5.0 and 1.6.0; and once about a step of a stand-in tool that could not find a file the test has no stand-in for ("Open report.pdf.", written out from "open the second one"). One older request went elsewhere than before: "I'm coming from JAWS. What is the JAWS cursor called in NVDA?" was sent to the JAWS Migration Assistant's job, which answers with keystrokes. Corrected after the run (`partners.jawsWish` wants a keystroke, the word command or the migration; the gate of VisionClaw's notes no longer opens for JAWS alone) and measured again with the three requests that name JAWS only: it is looked up as before, and the two about a JAWS keystroke and a JAWS command still go to the add-on's job. The whole list was not run again after that correction |

What measuring with the real model changed, the same day:

- "Make NVDA speak a little faster, only in this program." was split at its comma; "only in this program" was
  taken for a request to describe the screen, and the stand-in setting was changed for every program. Now the
  words that say for which program are put aside before a request is split (`planner.split`).
- Given one question for every kind of follow-up, with leave to copy a request that stands alone, the model
  copied 8 of 11 follow-ups unchanged ("And the status bar?" stayed "And the status bar?"). Now ordinals are
  plain code's, and the model gets a question of its own for "the same about another thing" and for "a thing the
  answer names", and a copy is refused where the follow-up cannot stand alone.
- "Open report.pdf.", written out from "open the second one", ended in a question whether to open a website.
  A name with a file's ending is a file now (`computer.namesFile`); "open notes.txt" no longer points at
  VisionClaw's notes on a program.
- "Read it" was taken for "say the last answer again". That needs "again" now.

**Not tested.**

- **The JAWS Migration Assistant and ClassicSpeech were not installed on this computer.** Everything VisionClaw
  does with them rests on names read from their source and on stand-ins made to match. One wrong name and the tool
  says that this version keeps it differently; that it works with the real add-ons is not known.
- **A voice of its own has not been heard.** Whether NVDA applies the profile to VisionClaw's words as it does for
  say all, how a profile with another synthesizer behaves between VisionClaw's words and NVDA's own, and whether
  the profile is turned off when the settings window is closed with Escape, are known only from NVDA's source.
- **Working through a task in a real program.** Which controls NVDA reports for a ribbon, a menu bar or a web
  application, whether pressing them through NVDA opens what a click would, and how long a program needs before it
  can be looked at again (0.8 seconds is waited) were not tried.

- **Nothing of this has run inside NVDA.** For a setting for one program that matters most: the stand-in was
  written from NVDA's source, but whether entering the trigger makes a new profile apply at once, how NVDA's
  speech reloads its settings at that moment, and what happens when NVDA's own Settings window is open (it
  suspends triggers) are only known from reading. `docs/TESTPLAN.md` has the steps, the first of them first.
- **No person has spoken into a real microphone.** The 24 recordings were Windows' synthetic voices, clean and
  at an even loudness; the microphone on this computer gave only silence in the check, so whether it is muted or
  the room was silent is not known. When speech begins and ends was tested on tones, not voices. Accents, a noisy
  room, a headset, another language than English, and Qwen3-ASR 1.7B were not tried.
- **NVDA+Alt+V, the beeps, the download question and its progress, and the choice in the settings** were not run;
  the Ask window's voice button was, with a stand-in for the voice. Whether NVDA's own speech, coming from
  loudspeakers, gets into a recording is not known: VisionClaw cuts NVDA's speech short, beeps, and opens the
  microphone a quarter of a second later, and when the window was opened to listen at once it waits 0.9 seconds
  first; none of that has been heard by anyone.
- **A calendar in a real browser or program.** How Chrome, Edge and Firefox name the days and buttons of real date
  pickers, a calendar inside a frame, one that shows two months, one whose month is a combo box, and a native
  Windows date control were not tried. From a picture, days are found as text; a calendar whose numbers the text
  recognition misreads is not found or is found short.
- **A follow-up after an answer that names several things**: "open it" after two files were found was written out
  with the second file's name by the real model. That is a guess. The user is told what it was taken as and the
  tool asks before it opens anything, but nothing checks that the right one was meant.

## What was not tested

- **Exploring a page and form trouble (2026-11-18) have not run in a browser inside NVDA.** They read the same
  facts as the deep inspection (`getTextWithFields`), which has not run there either. Open questions for the
  run in NVDA: whether Chrome, Edge and Firefox mark a required and an invalid field the way the stand-in does;
  what an empty edit field holds in NVDA's copy of the page where the site shows a placeholder; whether moving
  the reading position (`_set_selection`) lands on the field after the Ask window has closed; how a page built
  without landmarks or headings sounds. Sites that mark a wrong field only by a red border are found only
  through the text in the picture, or not at all.

- **Fingers, pressure, games that read the mouse directly and a game controller (1.2.0)** were tested with
  stand-ins for Windows, the mouse and the controller, with a game drawn by the test, and with the real models
  on drawn pictures and on requests in words. A real pinch and a real pen stroke were taken by Windows once,
  inside the own window of `python tests/live_touch.py --yes` (2026-11-18, see above). Not tried at all: a
  real program that takes touch, and one that does not; a drawing program that follows a pen's pressure; NVDA's own touch handling put aside on
  a computer with a touch screen; a real game whose view the mouse turns, and one that draws its own pointer,
  with its pointer measured; a real controller, of Xbox's kind and of another make, in a real hand, with its
  buzz; and all of it in a 32-bit NVDA.

- **Controls that need more than a click (1.1.0)** were tested with a stand-in for the mouse, the keyboard
  and the screen, and with the real models on drawn pictures. In a real program: hovering and reading a tip,
  holding a button, a hotkey that holds, gestures, a click when something changes, the middle button, a key
  held down during a click, a click at a place on a thing, and zoom have not been tried. A web page item's
  place on the screen comes from NVDA's own object for it (`obj.location` after `scrollIntoView`), which the
  stand-ins do not check.

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

- Files: only in your Desktop, Documents, Downloads, Pictures, Music and Videos folders. Whole folders are
  moved but not copied. A file selected in File Explorer is not known to VisionClaw: say its name. A deleted
  file is brought back from the Recycle Bin by hand, not by "undo that".
- Working the computer itself: a
  list to choose from inside a program (a combo box) is not set by the option's name; the focus is put on it
  and the keys are said. The pages of a dialog are found only where they are tabs, not where they are a list or
  a tree. The computer's volume is that of the device Windows plays through, not of one program. Wi-Fi and
  Bluetooth are not switched; their Settings pages are opened. A program that runs with more rights than NVDA
  cannot be closed or brought to the front. The words for all of this are understood in English only.
- "If you see" something: where its name is in no text and NVDA gives no name, only the model's yes or no is
  left, and a yes of its alone is said to be the model's. Three kinds of condition are understood: something on
  the screen, a window that is open, and what the Recycle Bin holds.
- A request of more than eight things is cut off at eight.

- Accessibility fixes are of five kinds. One fix cannot be removed by itself yet: a newer fix about the same
  thing replaces it, or the whole add-on is removed. What a fixes add-on says ("No more posts below") is English.
- A control gets a name only where something fixed in the page's or program's code tells it apart.

- The models window, settings and tool results are in English; translations are phase 6.4.
- Settings that are a free text in NVDA, such as the braille tables, are reported but cannot be changed yet.
- `run_command` runs NVDA's script directly, with a key press made for it; a few scripts that depend on how
  they were triggered may behave differently than when pressed. How often to press is only read from English
  descriptions ("twice", "three times"); with NVDA in another language a command is pressed once.
- VisionClaw's log holds what was asked and what was read from the screen, in plain text, until it is
  overwritten. It can be switched off.
- App helpers find their item by text, so an item that is only an unnamed icon cannot be a helper's target yet.
- Questions are matched by words. A question in words that neither NVDA, the window nor the notes on Windows
  use finds nothing, and says so. The notes on Windows are in English and cover Windows' own keys, not the
  keys of each program; a program answers only through the keys its own controls report.
- Menus that are closed are not in a window's controls, so their keys are not found until the menu is open.
- Learning about a program finds only what Wikipedia, Wikidata and the program's own website have. VisionClaw
  asks no search engine itself. Notes are in the language of the pages, which is English.
- A model's notes are checked for keys and words, not for meaning: a point can still say something the page
  does not mean. Every note names its page, and the file says it may be wrong.
- The check on generated code is not a sandbox.
- A click at the right moment follows a change VisionClaw sees, about 25 looks a second; it cannot hit a moving
  mark at a place, and something that changes all the time has no moment it can tell. A drag between two
  windows is not covered.
- A touch or a press with pressure is seen to have changed the window or not; whether a program felt how hard
  it was pressed cannot be seen. A program that reads a drawing tablet through the tablet's own driver takes
  no notice. Pressing as a pen needs Windows 10, version 1809, or later. A program that runs with more rights
  than NVDA cannot be touched.
- A game that refuses movements made by a program cannot be worked. How far a game turns for a step of the
  mouse is a guess until the user says too fast or too slow. A game's own pointer is measured only where it is
  the one small thing that moves in the picture; where the game's menu lights up under it, measuring fails and
  says so.
- VisionClaw cannot press a controller's buttons: a game that is only worked with a controller needs the
  user's hands. A controller of another make than Xbox's is read with its buttons taken to lie as on most; the
  triggers of such a controller are on or off, not pressed harder or lighter. The buzz may not come.
- The words for all of this are understood in English only.
- What appeared after hovering is the text that is new where the window's picture changed; a tip drawn outside
  the window, or one that shows no text, is not read.
- A control's own name is understood in English only ("Hold to record"); in another language the models are
  asked instead.

## Keys that every keyboard has (1.7.1, 2026-11-18)

The owner, with pointer mode on: "it says the applications key right-clicks. some keyboards don't have an
application key. this must be changed to a more standard keyboard key. assume some don't have pageup, pagedown,
home, end, either."

What was changed:
- Pointer mode (`pointer.KEYS`): A right-clicks; I, K, J and L turn the wheel up, down, left and right about a
  page, with Shift one notch; B brings the pointer back to the middle. The overlay: A right-clicks. A dial or
  slider that is held (`dragcontrol.KEYS`): T and B go to its top and bottom end.
- The keys that may be missing still work, as a second way only (`pointer.EXTRA_KEYS`, `dragcontrol.EXTRA_KEYS`).
  No spoken help, command description or note names them any more.
- Found while doing this, in the code as it was: Shift+Page Down turned the wheel while the user's Shift was
  still down, and with Shift most programs scroll sideways; Shift+Enter double-clicked with Shift down, which
  selects a range in a list. A click or a turn of the wheel in pointer mode now waits up to 1.5 seconds for
  Shift, Control and Alt to come up (`mousetools.keysUp`), and does nothing and says so when they stay down. One
  turn of the wheel at a time: a key that repeats meanwhile is left out.

What was tested, and how: `tests/test_pointer.py` fails when a job of pointer mode or of a held control has no
key made of letters, arrow keys, Enter, Space, Escape, Shift and Control. `tests/test_nvda_stub.py` presses every
new key and every old one against stand-ins for the mouse, the wheel and the keyboard, holds Shift and Control
down as a person would, and checks that the spoken help names no key that may be missing. `python
tests/run_all.py` passes. **Not run inside NVDA**: whether Windows reports the user's Shift as up as soon as it
is let go, and whether Shift+K then scrolls down and not sideways in a browser, are in `docs/TESTPLAN.md`.

Not changed: the keys of the arrow keys' own held dial that work with the wheel or a drag while Shift or
Control is down (a small or a large step). There a wait would make a held key lag. Whether Control held down
makes a wheel-worked dial zoom instead is to be tried inside NVDA.

## Help files that explain every feature and what is new (2026-11-18, after 1.7.1)

The owner asked that all help files always reflect every feature, explain it, and say what is new in the latest
version and how to use it. Before this, the help page NVDA opens still said "This is version 1.0" and had no part
on what is new; it said nothing of the computer itself (1.5.0), your own files, exploring a page and form trouble
(1.6.0), skills, memories, the library, the log, everything inside NVDA, the choice of quant, "How VisionClaw
answers", NVDA+Alt+I, or the overlay's letters H, B, E, X, K and D. The README said "Status: version 1.3.0",
its download link was for 0.11.0, and it had no part for skills, memories, the library or the settings.

- `addon/doc/en/readme.html` was written again: a part for every feature, the keys, every setting by its own
  label, what was tested, and privacy with every time VisionClaw goes online (the training material was missing).
- The README got the parts it lacked, NVDA+Alt+I, a list of the settings, and a download link that always gives
  the newest version (`releases/latest/download/VisionClaw.nvda-addon`, the fixed-name copy every release has).
- `tools/write_help.py` writes what is new in the newest two versions, from the changelog, into both files.
  `build.py` refuses to build while that part is out of date.
- `tests/test_help.py` (in `run_all.py`) fails when either file lacks a key, a setting's label, the words for
  any of the 93 kinds of request, or the part on what is new for the manifest's version. It found at once a kind
  of request being built in another session, `windows_part` (opening the Start menu and other parts of Windows),
  which was then given its lines in both files from the words `computer.WINDOWS_PARTS` knows.

Tested: `python tests/test_help.py` and `python tests/run_all.py`. The page has not been opened from NVDA's
Add-on Store yet; that it reads well with NVDA's browse mode is to be checked there.

## The Start menu, parts of Windows, the click that must fit, and smarter planning (1.8.0, 2026-11-18)

The owner: "I asked visionclaw to open the start menu, click the start button in windows. I asked several different
ways and visionclaw fails to do this. Fix this problem. You must make visionclaw much smarter, more context aware,
more adaptable, more flexible." Then, while it was being done: "make planning smarter across all aspects",
"combine smart planning python module or modules, plus skills, rag, system prompts, memory", and "if there are
extra python modules, math formulas, etcetera that will make planning smarter too, use them".

What VisionClaw's own log showed (the owner's NVDA, Qwen3.5 9B for both jobs, one question at a time, the desktop
in front):
- "click the start button." was a click; `list_items` listed the desktop's 41 icons; the Start button is on the
  taskbar, so it was not among them; the model chose "Settings button", the user said yes, and it was clicked.
- "click the windows start button using the mouse." went the same way; after two refused names the model chose
  "10", the Brave icon, and the user said no.
- "open the windows start menu." The model chose to press keys, rightly; the plain hint said click ("open ...
  menu"), the model kept its choice, the user had to choose; with click, the model wrote "None of the items in the
  list is the Windows Start menu.", and `match.best` found the item "te" inside that sentence. "Clicked te."
- The README and the help page already described "open the Start menu", but no code did it.

What was changed:
- **The parts of Windows itself** (`computer.WINDOWS_PARTS`, tool and recipe `windows_part`): the Start menu
  (Control+Escape), search, the taskbar, the notification area, quick settings, the notification center, Task
  View, the Run dialog, the Quick Link menu (also "right-click the start button"), clipboard history, the emoji
  panel. Keys from `windows-keyboard.md`. Sure words are decided without a model; "the start button" alone stays a
  click, and the click opens the Start menu after a question, or without one where Windows' own shell is in front
  (`router.SHELL`). A new skill, `parts-of-windows`, and a section in `visionclaw-computer.md`.
- **The click must fit the words** (`match.fits`, `telling`, `saysNone`, `nvdatools.clickItem`/`elsewhere`): see
  CLAUDE.md. `match.best` no longer finds a short name inside a long sentence.
- **`claw/planning.py`**: where the user is in plain words (added to every `situation()`), planning notes called
  up by the words and ranked by BM25, plans counted as they went well or not with Laplace's rule and a half-life
  of 90 days (`plans.json`), and the jobs of the skills that fit always offered. Only the standard library.

What was tested, and how:
- `tests/test_planning.py` (new, in `run_all.py`): every one of the owner's requests and 25 more, which part of
  Windows they mean and which job; that the keys are those of Microsoft's page; the click checks; BM25 against
  hand-worked cases; Laplace's rule, ageing and the most weight winning, read back from the file; that a fault in
  the brief never ends a request; that with the shell in front no model is asked.
- `tests/test_nvda_stub.py`: the real `click_item` and `windows_part` against stand-ins for NVDA and the keyboard:
  the owner's two failing forms open the Start menu (the stand-in records Control+Escape and that no mouse button
  was pressed); "click the start button" asks first and does nothing on no; an item that has none of the words is
  asked about and not clicked on no; "not found" clicks nothing; "click the recycle bin" offers the Recycle Bin.
- `python tests/run_all.py`: all pass.
- **The real model**: `tests/live_orchestrator.py` with Qwen3.5 9B for both jobs, one question at a time (the
  owner's own settings), now 202 requests with six new ones; every request is carried out (202 of 202 done) in at
  most 8.9 seconds. "click the windows start button using the mouse.", "open the windows start menu.", the split
  "look at the current screen, then click the windows start button with the mouse.", "Go to the system tray." and
  "Open quick settings." go to the part of Windows by plain code. "click the start button." with the test's game
  in front: the model chose the part of Windows (with the brief), the plain hint said click, and the user is asked;
  that is meant, since a game can have a Start button. "How do I bake a cake?", which ended in a question to the
  user in every earlier run, now goes to explain_keys and is answered that nothing is about it. The questions that
  were there before are still there ("Name the focused button Share on this website", "Give me a hotkey for the
  gain knob", the second half of the deep query). 89 of the 202 got a brief.
- **Not run inside NVDA.** First to try: does Control+Escape sent by VisionClaw open the Start menu, and is NVDA's
  focus there when the answer is said; then "click the start button" with the desktop in front (no question).

## What is in a part of Windows, the next way, and learning that generalizes (1.9.0, 2026-11-18)

The owner pasted VisionClaw's progress for "tell me all objects that are currently in the system tray." (Qwen3.5 9B
for both jobs, one question at a time, the desktop in front): the planning note said the tray is "opened with
windows_part", the model chose to describe the screen, the picture of the desktop answered "I cannot see the system
tray in this image ... is not visible", and the request ended as "Finished". Then: "visionclaw must be even smarter
and plan a lot smarter ... learn to generalize either through a skill, system prompt, memory, new python code, some
sort of advanced math formulas, or a combination of all of those."

What was wrong, in general terms, not only for the tray:
1. VisionClaw had no way to read a place that is in no window. It could only open the tray.
2. Where a request is about was not a thing plain code read: every way of looking looked at the window in front.
3. An answer that says "I cannot see it" counted as done, so nothing tried another way, and `planning.outcome`
   would have counted the wrong plan as one that went well and offered it again next time.
4. What was learned was compared by exact words, so it could not carry over to another wording.

What was changed:
- **`claw/places.py`, `placetools.py`, the job `read_place`**: the system tray (with the hidden icons and the
  clock), the taskbar, the desktop, and the notifications, quick settings, the Start menu and clipboard history
  (opened with their key first and left open) are read from what Windows tells screen readers through UI
  Automation, word for word, no model. Plain code reads the place and what is wanted (list, count, or whether a
  named thing is there) from the words, and decides the job without a model (`planner._SURE`).
- **A thing inside a place is clicked there**: "right-click the volume icon in the system tray" lists the tray and
  clicks in the icon's middle after the usual question; "click Dropbox" from any window is looked for in the tray and
  on the taskbar, and asked about. `look` takes the picture of the tray or taskbar where the words name it.
- **The next way** (`planning.unanswered`, `NEXT_WAYS`, `nextWay`, `orchestrator._nextWays`): a way of looking
  that found nothing is followed by the next way that only looks, by rules in a table, once per way; the user is
  told. After a picture that cannot see a part of Windows: `read_place`. After Windows said nothing about the tray or
  the taskbar: their picture.
- **Learning from what really happened**: such a request is counted as not well; after a next way, the first way as
  not well and the next as it went.
- **`claw/concepts.py`**: words that mean the same thing are one concept, and plans are recalled and planning notes
  ranked by concepts too. "Tell me all objects ... in the system tray" and "which icons are in my notification area"
  are now 1.0 alike (before: 0.0).
- The planning note for the parts of Windows names both jobs; the skill `parts-of-windows` uses `read_place`; a
  section in `visionclaw-computer.md`; both help files; the test plan.

What was tested, and how:
- **The real taskbar of the owner's Windows 11 (build 26300), read only**, with UI Automation from plain Python the
  same way `placetools.py` walks it, and put through `places.py`: the three tray icons shown (network, volume,
  battery), the clock, Show hidden icons, the programs Microsoft Edge (pinned) and Claude (1 running window), Start
  and Search, and all 44 icons of the desktop, said correctly. The taskbar's buttons are only in its child window
  `Windows.UI.Composition.DesktopWindowContentBridge`; the tree of `Shell_TrayWnd` itself has only empty panes.
  **The hidden icons were not shown**: that would have opened the flyout on the owner's screen without asking. How
  Windows 11 keeps them while shown is therefore not checked on a real computer; the code reads any named buttons of
  that window, and says when it could not read them.
- `tests/test_places.py` (new, in `run_all.py`): 33 wordings and which place and wish they mean; which job; the
  facts read from the owner's taskbar and a Windows 10 taskbar sorted and said; concepts; what is no answer; the next
  way; and whole requests with a scripted model: the owner's request answered from Windows with no model asked; the
  model sent to the picture anyway, then the next way, the user told, the picture's "cannot see" not said, the plan
  learned and recalled for other words; Windows saying nothing, then the picture; both finding nothing; the next way
  failing outright, then what the first found said as it was; a picture that answers left alone.
- `tests/test_nvda_stub.py`: the real `read_place`, `list_items` and `click_item` against stand-ins for the taskbar:
  the owner's request, NVDA hidden in the tray, the taskbar, the desktop, quick settings opened with Windows+A and
  read, already open and not closed, not opening; the volume icon right-clicked in its middle; "click claude" found on
  the taskbar, asked about, and clicked there; the desktop not used while covered.
- `python tests/run_all.py`: all pass (run again after the last change, before the build).
- **The real model**: `tests/live_orchestrator.py` with Qwen3.5 9B for both jobs, one question at a time (the
  owner's own settings), now 213 requests with eleven new ones; all 213 carried out, in at most 8.6 seconds. The
  owner's request and "What icons are in my notification area?", "Is NVDA running in the system tray?", "How many
  icons are in the system tray?", "Which programs are on my taskbar?", "What icons are on my desktop?", "Read my
  notifications.", "Describe the system tray for me." are decided by plain code and answered from what Windows
  reported, with no model asked; "Right-click the volume icon in the system tray." right-clicks that icon; "What is
  the system tray?" and "How do I get to the system tray?" are still answered as questions; in "look at my screen,
  then tell me what is in the system tray." the screen is described and the tray read. The questions to the user are
  the four of 1.8.0 ("click the start button." with the game in front, "Name the focused button Share on this
  website", "Give me a hotkey for the gain knob", the second half of the deep query) and one in the session "Look
  through my downloads folder. >> Open the second one.", where the stand-in that finds things to open has no
  report.pdf; run again on the code of 1.8.0, that session asks the same. No next way was needed in the live run: the
  requests that need one are now decided before. 90 of the 213 got a brief.
- **The hidden icons on the owner's real taskbar, with his yes** (after the release, the same evening), from plain
  Python, the way `placetools.hiddenItems` does it: Show Hidden Icons was found and invoked; the window
  `TopLevelWindowForOverflowXamlIsland` ("System tray overflow window.") was shown within 0.1 seconds; its four
  icons were read (Claude, NVDA, Copilot, NVIDIA Settings; buttons of class `SystemTray.NormalButton`, automation id
  `NotifyItemIcon`, each reported twice, once from the window and once from its content window, and said once); it
  was hidden again by invoking the button a second time. **What it found wrong**: the window shown took the focus,
  and after it was hidden the focus was on the taskbar, not on the window that was in front before. Fixed: the
  window in front before is remembered and brought back (`computertools.focusWindow`), tested in
  `tests/test_nvda_stub.py` with stand-ins for Windows, and tried once more on the owner's taskbar with his yes:
  the four icons were read, the window was hidden again, the focus was on the taskbar right after, and the window
  that was in front (Claude) came back to the front. Released as 1.9.1. The window that keeps the hidden icons
  stays after the first time, not shown; it is then not read where it is, but shown first, as on the first time.
  From NVDA's own process, bringing the window back is still to be tried.
- **Not run inside NVDA.** First to try: the owner's request from the desktop, then from Notepad, and whether the
  hidden icons are read and the focus comes back to where it was (the new section of `docs/TESTPLAN.md`).

## Smarter across the board, measured; which model for what (1.10.0, 2026-11-19)

The owner: "find a way to make it a lot smarter across the board, too", and while it was being done: "if I should
switch to smaller or different qwen variants according to user reviews and my available listed visionclaw qwen model
choices ... visionclaw should suggest what kind of switch I should make, then let the final decision up to me", and
"if we need more clever skills, more clever system prompts, memory and rag, claude must implement this".

**Measuring first (phase 5.1).** The full live test cannot show this: its 213 requests were tuned against for weeks,
and it counts what was carried out, not whether the job was the right one. So:
- `tests/eval/requests.json`, 137 requests in a blind person's casual words, each with the jobs that count as right,
  none of them in the live test; `requests2.json` (88) and `requests3.json` (65), each written after the changes
  before it and before anything was run on it. `tests/eval/known.json`: the 312 requests whose job is known (the
  live test's parts as handled rightly, reviewed by hand, and the help files' words).
- `tests/eval_routing.py` runs a set through VisionClaw's real planning with the real model and carries nothing
  out: right, wrong, or the user had to be asked. `VC_PLUGIN` scores another copy of the add-on, so the last release,
  unpacked from git, was scored on the same sets.
- **Found first, a fault of the test itself**: eleven jobs had no stand-in in `tests/live_orchestrator.py` (pressing
  keys, typing, reading text, writing an add-on, naming a button, the notes and three about what VisionClaw made), so
  the model could not choose them and its choice of another looked like its mistake. With them added, the first set
  went from 113 to 121 of 137 with no change to VisionClaw.

**What the misses showed, and what was changed**, each a rule, none for one sentence:
- Of the 9 questions to the user on the first set, the model had chosen rightly in 6: a word had set off a pattern for
  an action ("shortcut", "headings", "menu"). Now the user is asked only where the words point clearly elsewhere
  (`planner.challenger`): the model's choice stands where a pattern that is not only about questions points to it too,
  or where only such a weak pattern points elsewhere.
- A how-question is answered with keys and a why-question is answered, whatever job a word in it names (`_HOW`, `_WHY`).
- A model that finds nothing that fits gets the job the words fully name (`planner.fitted`).
- Plain code reads more: a key combination of the program ("send control s"), the computer's volume said as "too
  loud", "what did I download", NVDA's own menu and windows, "what's on the clipboard", "focused", a rhythm said as
  "every second", "go back to" a program, "what does this dialog say", "I want to hear", "every letter I type", "your
  log", "what control am I on", "describe" as its first word.
- A skill's own steps run only when nothing more is asked; one job told in clauses, or a complaint and "make it stop",
  is not split.
- Tried and dropped: a nearest-neighbour vote over the known requests by BM25 and the concepts (`claw/intents.py`,
  written and removed the same day). Left out of one by one, it named the right job for 81 percent of the known
  requests it was sure of, but was sure of only a third; on the first set it was sure of 34 and wrong in 11 ("look up
  the price online" was taken for looking around in a game), while the patterns alone were right for 107 of 133. A
  hint that wrong would have misled the model, so it was not used.

**Scores**, Qwen3.5 9B for both jobs, one question at a time, the owner's settings:

| Set | 1.9.1 | 1.10.0 |
|---|---|---|
| First (137; the changes were made while reading its misses) | 121 right, 9 asked, 7 wrong | 135 right, 0 asked, 2 wrong |
| Second (88; written after the first round, before running; the second round was made from it) | 77 right, 4 asked, 7 wrong | 81 right, 2 asked, 5 wrong (after the first round) |
| Third (65; written blind after both rounds) | **55 right (85%), 5 asked, 5 wrong** | **58 right (89%), 1 asked, 6 wrong** |

The third set is the honest measure. One request there went from a question to the user to a wrong job: "open nvda
settings" is now taken as opening a thing by its name, since that pattern supports the model's choice. Left open, with
the six other misses of the third set, for a fourth set to measure any change made from them.

**Which model for what (`claw/advice.py`, the job `model_advice`).** See CLAUDE.md. Its suggestions were checked in
`tests/test_advice.py` against the owner's computer (8 GB graphics card, 31 GB of memory, Qwen3.5 9B for both jobs):
keep the 9B for planning, pictures and add-ons; Qwen3.5 4B when the user wants speed, said to be less exact and not
measured; with no graphics card, the largest that fits the memory, said to be slower. Every "Measured:" sentence is
checked to be one of `advice.MEASURED`. "According to user reviews" was taken as the user's own reviews on this
computer: how requests went with each model (`planning.Outcomes`, `models-went.json`, counted from now on) and what
the user asked VisionClaw to remember about a model. Reviews from the internet were not added: VisionClaw's own code
goes online only for the sources the owner said yes to.

**Skills, prompts, memory and retrieval**: what the measurements called for. A skill, Choosing a model; a section in
`visionclaw-asking.md`, looked up when a question names models or quants; the memory of how each model did. The
gains in choosing came from plain-code rules, not from longer prompts: the model was right where plain code let it be.

What was tested, and how: `python tests/run_all.py` (with `test_eval_patterns.py` and `test_advice.py`, new) passes;
`tests/test_nvda_stub.py` runs the real `model_advice` against a stand-in graphics card. **The real model**: the full
`tests/live_orchestrator.py`, now 215 requests with the eleven new stand-ins and two requests for a model suggestion:
all 215 carried out, in at most 9.4 seconds. Compared part by part with the run of 1.9.0, two choices changed and
nothing else: "Name the focused button Share on this website" now names the button (its stand-in was one of the
eleven missing), where before the user was asked; "Give me a hotkey for the gain knob" now goes to the arrow keys for
the dial, which is what the user had chosen when asked. Questions to the user: 3, where there were 5 ("click the start
button." with the game in front, the second half of the deep query, and the "report pdf" session, which asks the same
on the code of 1.8.0). Both requests for a model suggestion went to `model_advice`. **Not run inside NVDA.**

## Understanding your words, the work sheet, add-ons in pieces, questions in parts (1.11.0, 2026-11-19)

The owner asked, in one request: "build an orchestrator in python that takes a big prompt and breaks it down into
bite-size pieces a small 1b to 9b model can understand. visionclaw must have skills and system prompts, memory and rag
to understand the different ways a user may request something, like how inform text adventures understand different
things in different ways"; then the same "for pictures and all other functions"; and "no matter what model the user
chooses, visionclaw must force these small models to be as accurate as possible, this means using temporary markdown
files to plan and feed small bite-size pieces into tiny models, which get deleted when a job is done". Asked whether
this is the best way, Claude agreed, with one caveat said to the owner: a file does not make a model more exact by
itself; what each call is fed does. So the work sheet was made the one place each step's question comes from.

**What was built** (the rules are in CLAUDE.md):
- `claw/understand.py` and `claw/understanding.md`: the user's words understood by plain code, the way Inform's
  "Understand" lines work. Four sections by where a line may change something; tokens [x], [keys], [thing], [window];
  what is never changed (quotes, text to be typed, names, searches, addresses, keys, and requests to remember, make a
  skill or teach a word); "Understood as" at the start of the answer when a meaning was changed.
- The user's own words: the job `teach_words`, the tool `my_words` (`wordtools.py`), the file `understanding.md` in
  the data folder, read again when it changes.
- `claw/worksheet.py`: the work sheet of every request, in `work` of the data folder, deleted in `Orchestrator.run`'s
  `finally` and at start. Each step is fed from it what its own part found (`agent.found`); a step a model planned
  itself, one that leans on "it", and one added for what was missing are given everything, as before.
- `claw/codeplan.py`: an add-on read into pieces by plain code (keys, events, kinds of control, states, programs), its
  frame and the beeps and fixed sentences written by plain code, the lines of each piece written by the model from
  that piece's section of the work sheet, checked, corrected and reviewed one piece at a time; the old writer for what
  cannot be framed; a failing add-on corrected one method at a time where everything that went wrong is in one method.
- `claw/pictures.py`: a question about the screen asked in its parts, each with the one rule of its kind.
- Skills, prompts, memory and retrieval: every piece of an add-on gets the skills, memories, library and notes chosen
  for its own words (`nvdatools.coderNotes` per piece); the piece writer and each kind of picture question have
  instructions of their own, without examples; the user's own words are kept as Markdown; VisionClaw's notes
  (`visionclaw-asking.md`) answer questions about all of it, asked only when a question names it.

**What was tested, and how.**
- Plain Python: `tests/test_codeplan.py` (requests read into pieces; the frame; every assembled add-on run against
  stand-ins for NVDA's modules, `tests/addonstandin.py`: a beep only for links, nothing in another program, a key
  passed on there, a failing piece that does not stop NVDA; scripted models: a piece is given nothing of the others,
  a failing piece is sent back alone, a review's fault, the old writer for a timer, one method corrected; the work
  sheet written, fed from, and deleted) and `tests/test_understand.py` (the grammar, what is never changed, the user's
  own words as a file, picture questions, and whole requests through the orchestrator: "Understood as", the work sheet
  a file while the request runs and gone after it, also after a failure, and a second part not given what the first
  found). `python tests/run_all.py` passes.
- **Choosing the job, with the real Qwen3.5 9B** for both jobs, one question at a time, the owner's settings
  (`tests/eval_routing.py`). A fourth set, `tests/eval/requests4.json`, 62 requests in casual, roundabout and slangy
  words, was written before the grammar and before anything was run on it, and 1.10.0 was scored on it first:

  | Set | 1.10.0 | 1.11.0 |
  |---|---|---|
  | First (137) | 135 right, 0 asked | 135 right, 0 asked: the same, request for request |
  | Second (88) | 87 right, 1 asked | 87 right, 1 asked: the same |
  | Third (65) | 58 right, 1 asked | 58 right, 1 asked: the same |
  | **Fourth (62, casual words)** | **40 right (65%), 2 asked** | **52 right (84%), 1 asked**: 12 better, none worse |
  | Fourth, with Qwen3.5 2B choosing (stepwise Automatic) | 41 right (66%), 5 asked | **55 right (89%), 0 asked** |

  Plain code alone, the planner's first pattern: on the fourth set 29 of 60 from the raw words, 54 of 60 after the
  words are understood; on the 593 known and earlier requests none worse, two better. **Said plainly**: the fourth set
  and the grammar were written by the same hand on the same day, so the gain on it is what the grammar can do on
  words like its own; a set in the owner's own words is the honest measure of what comes next. Left open on the fourth
  set, not tuned on, for a fifth set to measure: a complaint and its remedy said in one breath is split in two ("the pc
  is blaring, turn it down", "nvda is mumbling, crank up the voice volume", "my beeping add-on is broken, sort it
  out", "check out this chart and give me the gist"); "how many people are in this photo" and "what's this thing I'm
  sitting on" go to a question; "how's my battery doing" and "anything new for visionclaw" too; "read everything from
  here down" reads the window's text instead of starting say all; "what's this page going on about" asks the user.
- **Writing add-ons, with the real Qwen3.5 9B** (`tests/live_codeplan.py`): nine add-ons, written down with what each must do before either way was run, each written as one piece
  (`microaddons.write`, as before) and piece by piece (`codeplan.write`), at the owner's settings (reasoning
  Automatic, which is High for an add-on). Every add-on that passed the checks was run against stand-ins for NVDA's
  modules (`tests/addonstandin.py`) to see whether it does what was asked:

  | Request | One piece | Piece by piece |
  |---|---|---|
  | Say hello with NVDA+shift+H | right, 97 s | right, 0 s (plain code) |
  | Beep when a link gets the focus | right, 94 s | right, 0 s (plain code) |
  | In Notepad, the focused control's name with NVDA+shift+N | right, 97 s | right, 58 s |
  | The time with NVDA+alt+T | right, 138 s | right, 58 s |
  | Beep for a button, the window's title with NVDA+shift+W, "link ahead" for a link | wrong (`window.appName`), 288 s | right, 110 s |
  | Only in Firefox: "heading" for a heading, the focused control's name with NVDA+alt+N | wrong (`Role.HEADLINE`, which NVDA does not have, and the key works in every program), 95 s | wrong (says the control's kind instead of its name, after the review named a fault that was not there), 110 s |
  | "Checked" when a checkbox gets checked, a count of the name's characters with NVDA+shift+C | wrong (silent when checked), 286 s | right, 55 s |
  | Beep each time a character is typed | refused by its own check, 422 s | right, 0 s (plain code) |
  | The focused control's value with NVDA+shift+V, a beep when a progress bar changes | wrong (no beep), 290 s | right, 56 s |
  | **All nine** | **8 passed the checks, 4 did what was asked, 1806 s** | **9 passed the checks, 8 did what was asked, 446 s** |

  Found and corrected while measuring, each with a test: the piece writer took the first line of an answer without
  its indentation, so every answer of the 9B, which writes a piece's lines indented, was a syntax error the model could
  not correct, and the piece fell back to one piece after many minutes (`codeplan._block`); a check of the same program
  the frame checks was refused (now left, `codeplan.problems`); both writers wrote a window's title as
  `obj.appModule.windowTitle` or `.title`, which NVDA does not have, and plain code now writes it as the name
  (`microaddons.fixNames`, and a line in `objects-and-events.md`); the one-piece writer's own check took "each time I
  type a character" for a key and refused the event (`microaddons._ON_KEY`). The one-piece column was measured before
  that last fix. The first run, before these fixes, is not counted: it was stopped.
  With the smallest suggested pair, Qwen2.5 Coder 1.5B writing and Qwen3.5 2B reviewing, on the GeForce, after the
  fixes above and two more this pair showed (`controlTypes.Role.PROGRESS_BAR`, and `datetime.now()` on the module
  datetime, both corrected in `microaddons.fixNames`), with the stand-in made fuller (all 156 kinds of control NVDA
  has, read in `tests/test_working.py`, and the attributes NVDA's controls have, after it had wrongly failed an add-on
  that used `Role.LABEL` and `windowControlID`): **one piece 9 passed the checks and 3 did what was asked, in 27
  seconds; piece by piece 9 passed and 9 did what was asked, in 13 seconds.** The session working on 1.12.0 ran the
  same nine on the Radeon 780M the same morning, before the datetime fix: one piece 2 of 9, piece by piece 8 of 9.
- **The live test, in part**, with Qwen3.5 9B for both jobs at the owner's settings: the 12 requests of
  `tests/live_orchestrator.py` that have several parts, where what a step is fed changed (each part now gets only
  what its own part found), and four new ones for this version. All 16 were carried out, each part by the job it was
  before, with no question to the user: the Recycle Bin opened after it was seen, the volume, gmail.com and the
  closed Settings window in one request, the controls of a dialog with tabs, the folder made and the file moved,
  and the rest. "Kill the typing echo please" and "Give the screen a once-over" were answered "Understood as: turn
  off the typing echo." and "Understood as: look at the screen.". **The whole live test (210 sessions, about 40
  minutes) was not run** for this version: three other sessions were waiting for the graphics card.
- **Not run inside NVDA.** The new tool `my_words`, the work sheets in the real data folder, the piece writer's add-ons
  loaded into NVDA, and the look tool's questions in parts have run only against stand-ins. `docs/TESTPLAN.md` has a
  new section for them.

## 1.11.1: a correction, and the whole live test (2026-11-19)

**What went wrong.** Several Claude sessions worked in the same checkout. 1.11.0 was built from a clean copy, but
its `manifest.ini` was made from the shared one with one line of another session taken out, not from 1.10.0 with
this session's own edits: two key lines of the description and one point of what is new, about status updates
for descriptions (NVDA+Alt+P, NVDA+Alt+X), came along, and `tools/write_help.py` wrote that point into both help
files. None of that feature's code was in 1.11.0. Found by the session that is writing it. **What was done**: the
GitHub release notes of 1.11.0 were corrected, with a line that says so; 1.11.1 was made from the tag v1.11.0 on
the branch `release-1.11`, with the description's two lines as in 1.10.0, the point taken out, and nothing else
changed; `main` was left alone, since it holds that session's own work for 1.12.0. **Lesson**: rebuild every
shared file from HEAD plus your own edits, never from the shared copy (see the memory on releasing from a
shared checkout).

**The whole live test of 1.11.0**, `tests/live_orchestrator.py`, run from a clean copy of the tag v1.11.0 with
Qwen3.5 9B for both jobs at the owner's settings, after the release, at the owner's request: all **219** requests
(the 215 of 1.10.0 and four new ones) were carried out, in at most 8.5 seconds each, with no fault. VisionClaw
asked the user three times, the same three as 1.10.0: "click the start button." with the game in front, the second
half of the deep query ("Tell me how a sighted person works it"), and the "report pdf" session, a gap of the
`find_thing` stand-in. No output of 1.10.0's whole run was kept, so the answers were not compared one by one;
the totals are those of 1.10.0's run in this file.

## Next session

1.11.0 understands casual words and the user's own words, feeds every step from a work sheet, and writes add-ons
piece by piece. First, with the owner's yes: the new section of `docs/TESTPLAN.md`, "Understanding your words, the
work sheet, add-ons in pieces", in NVDA. Then a fifth evaluation set in the owner's own casual words, to measure the
grammar on words its writer did not choose; the misses of the fourth set listed above are for that set to measure.
With the owner's yes, download Qwen3.5 2B or 0.8B and run `tests/live_codeplan.py` and `tests/eval_routing.py` with
it: the piece writer was made for the smallest models and was measured only with the 9B.

1.7.0 added four things, and none of them has run inside NVDA. With the owner's yes, in this order: the first
item of "A setting only for one program" in `docs/TESTPLAN.md` (does a profile that was only just made apply at
once?), because everything about that feature rests on it; then "Asking by voice" with a person speaking into a
real microphone, since only Windows' synthetic voices were tried and the microphone gave silence in the check; then
a date picker on a real booking site. If the profile does not apply at once, read `appModuleHandler.py` and
`config/__init__.py` of the installed NVDA's version again before changing `profiletools._enter`.

1.5.0 added twelve tools that act on the computer and none of them has run inside NVDA. First of all, with the
owner's yes: the new section "Working the computer itself" of `docs/TESTPLAN.md`, starting with the two
requests that failed. Then the owner's examples inside a real program with a settings dialog.

`python tests/live_touch.py --yes` was run on 2026-11-18 with the owner's yes: Windows took the fingers and
the pen, and `touchinput.py` needed no change. Run it again, after asking, when `touchinput.py` changes.
Phase 3.5: install the build in NVDA (ask the owner first), walk through `docs/TESTPLAN.md`, fix what breaks.
Then download the two suggested models and repeat `tests/live_orchestrator.py` with them.

Found on 2026-11-18 and left open: with Qwen3.5 9B and Qwen2.5 Coder 1.5B, "Name the focused button Share on
this website" is not sent to the lasting fix, although its words point there. When one model does both jobs
its choice is checked against the words (`consensus._onRecipe`); when two models are used and they disagree,
it is not. Check both against the words in the same way, and measure with the whole of
`tests/live_orchestrator.py`.
