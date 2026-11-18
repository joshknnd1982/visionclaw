# VisionClaw test plan inside NVDA

Tick an item only after doing it in a running NVDA. Write the NVDA version and the models used at the top of
`docs/STATUS.md` when done. If something fails, VisionClaw's own log has what happened: ask "open the
VisionClaw log", or open `%APPDATA%\nvda\visionClaw\logs\visionclaw.log`. It is written whatever NVDA's own
logging level is.

Before you start: disable VisionMate in the Add-on Store, install the VisionClaw build, restart NVDA.

## Starting up
- [ ] NVDA starts without an error sound, and the VisionClaw models window opens after a few seconds.
- [ ] The window reads: welcome text, vision model list, coder model list, Download button.
- [ ] Both lists offer every model; the suggested ones say "suggested"; VisionMate's data, if present, says
      "on this computer".
- [ ] Changing a list changes the size on the Download button.
- [ ] Download starts with Enter; Space says the progress; Cancel keeps the partial file; starting again resumes.
- [ ] After the download the window shows the usage guide, and NVDA+Alt+W describes the window.

## VisionMate's features still work
- [ ] NVDA+Alt+A, W, F, D once (spoken) and twice (window with a question box).
- [ ] NVDA+Alt+O opens the overlay; arrows move; Enter clicks; Escape closes.
- [ ] NVDA+Alt+G, NVDA+Alt+B and NVDA+Alt+N.

## Commands, the time and the date (0.9.0)
- [ ] "Ask NVDA to give me the current time and then the date": the time is spoken, then the date, and the
      answer says to press NVDA+F12 once for the time and twice for the date. No error.
- [ ] "What time is it?" says the time only. "What is the date today?" says the date only.
- [ ] "Read the status bar" in a program that has one: it is read, with no error. (This is the command whose
      key could not be made before.)
- [ ] "Copy the window title to the clipboard", then paste somewhere: the title is there.
- [ ] A request for which NVDA has no command, such as "say the version of NVDA", says that no command
      matches and runs nothing.
- [ ] With an add-on installed that has a command without a description: asking for it by its name runs it.

## VisionClaw's own log (0.9.0)
- [ ] VisionClaw's settings have "VisionClaw's own log" with Detailed, Brief and Off, and a button that opens it.
- [ ] "Open the VisionClaw log" opens `visionclaw.log` in a text window. Its first lines name the versions of
      VisionClaw, NVDA and Windows.
- [ ] After a request, the log holds the request, every step, each question to the model with its answer, each
      tool with its result, and the answer you heard.
- [ ] With NVDA's own logging level Off, the log is still written.
- [ ] Set to Off: nothing more is written. Set to Brief: no whole questions to the model are written.

## Everything inside NVDA (0.9.0)
- [ ] "Tell me everything NVDA knows about this control" on a button: name, kind, states, position and size,
      program, window class and more are said, and they are right.
- [ ] "What is the window class of this control?" says only the window class.
- [ ] The same for "the navigator object" after moving it, and for "what is under the mouse".
- [ ] "What does the function api.getFocusObject do?" says that it is a function, how it is called, its help
      text, and the control it gives back now. Note how long the first such request takes.
- [ ] "Do a full audit of NVDA": totals are said, and `nvda-audit.md` in VisionClaw's data folder lists every
      command with its keys, the synthesizer and braille display in use and how they are driven, and
      everything by name. With "and show me the list" it opens. NVDA keeps working during and after it.
- [ ] "How does NVDA talk to a braille display?" is answered from VisionClaw's notes.

## Questions about a picture (0.9.0)
- [ ] NVDA+Alt+F twice on the desktop, then "what is the currently highlighted item?": it is answered. The
      reply "I can only answer questions about this image" never comes.
- [ ] A question about something the picture does not show: the answer says that it is not in the picture.
- [ ] "What is this program for?" in the window of NVDA+Alt+W twice: it is answered.

## Settings
- [ ] NVDA menu, Preferences, Settings, VisionClaw opens and reads every control.
- [ ] "Graphics found" names the graphics chips of this computer.
- [ ] Each graphics choice works after OK: Automatic, Dedicated graphics card, Vulkan, Processor only
      (describe a window after each; with debug logging on, `engine.log` shows the device).

## A newer version of VisionClaw
- [x] NVDA+Alt+U says "Looking for a newer version of VisionClaw", then a window says that this is the newest
      version. (Owner, 0.8.0, 2026-11-17.)
- [ ] With an older version installed than the newest release: NVDA+Alt+U says which version is available, its
      size and what is new, and asks whether to download.
- [ ] No: nothing is downloaded. Yes: "Downloading VisionClaw ..." is spoken, then NVDA's own install question
      appears; after yes NVDA restarts, and NVDA+Alt+U then says this is the newest version.
- [x] VisionClaw's settings: "Look for a newer version of VisionClaw" starts on "Only when I ask". (Owner,
      0.8.0, 2026-11-17.)
- [ ] The button "Look for a newer version now" in the settings does the same as NVDA+Alt+U.
- [ ] Set to "When NVDA starts, at most once a day": after restarting NVDA with an older version installed,
      one sentence is spoken within about a minute, no window opens, and nothing is downloaded. Restarting NVDA
      again the same day says nothing.
- [ ] "Check for a new version of VisionClaw" in the Ask window asks before going online, then answers.
- [ ] With no internet connection, NVDA+Alt+U says that it could not look, and that nothing was changed.

## Managing models
- [ ] VisionClaw's settings show a "Models on this computer" box with each model, its size and what it is in use
      for, and the total.
- [ ] NVDA+Alt+M opens the list. Space checks a model, and NVDA says it is checked.
- [ ] "Remove checked models" asks first, names the models and the space, and No removes nothing.
- [ ] Yes removes them; the list and the total change; "Removed. N GB freed." is spoken.
- [ ] Removing the model in use for coding: asking something afterwards uses another stored coder, or opens the
      models window if there is none.
- [ ] "Choose or download other models", picking a smaller pair: after the download, the question "You no longer
      use ..." appears; Yes removes the old ones.
- [ ] "Remove all models", then NVDA+Alt+W: the models window opens.

## Newer models
- [ ] The models window lists Qwen3.5 0.8B first among the vision models and Qwen2.5 Coder 0.5B first among
      the coder models; neither is marked as suggested, and each says "very small: fast, less accurate".
- [ ] "Look for newer models" asks first and says what goes online. No: nothing happens, and nothing went
      online.
- [ ] Yes: after a moment the text says there are no newer models, with the list's date, or names the models
      that were added; these are then in the lists, and the model that was selected is still selected.
- [ ] With no internet connection: the text says the list could not be read and that nothing was changed.
- [ ] Choose Qwen3.5 0.8B and Qwen2.5 Coder 0.5B: they download, pass the check, and the engine starts with
      them. "What is on my screen" gives an answer. (Both were downloaded and run in the engine outside NVDA
      on 2026-11-17; they are fast and often wrong. Not yet chosen inside NVDA.)
- [ ] After closing and reopening NVDA, models added by the button are still in the lists.

## Settings stay the user's
- [ ] Installing or updating VisionClaw changes no NVDA setting (compare the speech rate before and after).
- [ ] "Speak a bit faster": the question reads "You asked: speak a bit faster. Change speech rate from X to Y?".
- [ ] "What did you change?" names that change.
- [x] "Undo that" asks, then puts the rate back to X, and says so. (Owner, 0.4.0, 2026-11-17.)
- [ ] "Restore the voice pitch to what it was before you changed it", with the pitch never changed by
      VisionClaw: it says it has not changed that, and nothing changes.
- [ ] After restarting NVDA, "what did you change?" still knows the changes.

## Two large models
- [ ] With Qwen3.5 9B and Qwen2.5 Coder 7B chosen on a computer whose graphics card cannot hold both: ask
      something, then open NVDA+Alt+C. The Last task box says the two models ran in two different places.
- [ ] A second request starts at once, without a long pause for loading.
- [ ] With the side by side setting off, the same request still works, more slowly.

## Asking
- [ ] NVDA+Alt+C opens the Ask window; Enter on a request closes it and "Understanding your request" is spoken.
- [ ] "Make NVDA speak a little faster": asks "Change speech rate from X to Y?"; Yes changes the rate; the
      answer says the old and new value.
- [ ] The same, answering No: nothing changes and the answer says so.
- [ ] "Turn off the typing echo and set punctuation to all": two changes, both reported.
- [ ] "How do I read the title of this window?": the answer names the keys.
- [ ] "How can I use the keyboard to navigate my desktop?": the answer is about the desktop (Windows+D, the
  arrow keys, Enter), and not about the keyboard layout. The Last task box shows three lines that begin
  "Asked NVDA", "Asked the program" and "Asked Windows".
- [ ] "How do I switch between open windows?": Alt+Tab. "How do I rename a file?": F2.
- [ ] "What is browse mode?": an explanation from NVDA's user guide, not a command.
- [ ] "What does NVDA+T do?" and "What does Windows+D do?": each says what that key does.
- [ ] "What can I do here?", in a dialog with a button in focus: the program, the window and the focused
  control are named, with the control's own key if it has one.
- [ ] "Which windows are open?": the titles of the open windows.
- [ ] "How do I bake a cake?": one sentence that nothing was found, and what was asked.
- [ ] In a well-known program such as Notepad++ or Audacity, "Learn about this program": the Last task box says
  which program it took it to be; a question says what is sent and that no search engine is used; No makes
  nothing go online. Yes: the answer names the websites read, how many notes were kept, and the file.
- [ ] "Open the notes on this program": the Markdown file opens; every note has a Source line.
- [ ] In that program, a question the notes can answer, such as "how do I close a tab": the answer begins
  "From the notes on". A question nothing answers: "Nothing that was found answers that", or that nothing was found.
- [ ] "What does this do?" with the focus on a named button: the Last task box says what the model took
  "this" to be, and the answer is about that button.
- [ ] In a browser, on a page about a program: "Add this page to the notes on" and the program's name. The
  answer says how many notes were added and that nothing was fetched.
- [ ] "Which notes do you have?", then "Delete the notes on this program": asked first, then gone.
- [ ] In a game, "Learn about this game": it is taken to be a game.
- [ ] NVDA+Alt+U with a newer version on GitHub: a window opens with the focus in a read-only edit box; the
  arrow keys read what is new line by line; Tab reaches "Download and install" and "Not now"; Escape closes it
  and nothing is downloaded.
- [ ] "Read the window title": the title is spoken and the keys are named.
- [ ] "What is on my screen?": a description is spoken.
- [ ] "Read the text in this window": the text is read.
- [ ] In a program with buttons, "Click the ... button": asks, then clicks the right place.
- [ ] "Give this program a hotkey that clicks ...": the hotkey then works in that program and nowhere else.
- [ ] "List what you have made", then "Remove the hotkey ...".
- [ ] NVDA+Alt+P during a task says the step; NVDA+Alt+X stops it within a second or two.
- [ ] NVDA+Alt+C afterwards shows the whole last task in the Last task box.
- [ ] With "Say each step" off, only the answer is spoken.
- [ ] With the coder model missing, asking opens the models window.

## The web
- [ ] "Open nvaccess.org": the browser opens it and the answer names the page.
- [ ] "Search the web for NVDA user guide": a results page opens and the answer says something about the results.
- [ ] On an article: "What does this page say about ...?" answers from the page.
- [ ] "Click the ... link" follows it without a question; "Press the ... button" asks first.
- [ ] "Type ... into the search box and search": the text goes into the field and Enter is pressed.
- [x] "What are the headings on this page?" lists them with their levels. (Owner, 0.4.0, 2026-11-17.)
- [ ] "Take me to the heading ...": NVDA says the heading, and say all reads on from there.
- [ ] "Go back" and "reload this page".
- [ ] The same in Firefox, Chrome and Edge.

## Making a website or a program accessible
Do each of these once in Firefox and once in a Chromium browser (Chrome, Edge or Brave).
- [ ] On a page with posts (a social feed, a forum): "do a deep inspection of this website". The answer names
  the page and the site, counts headings, links, buttons and fields, and lists numbered problems. NVDA keeps
  responding while it works, and NVDA+Alt+X stops it.
- [ ] The counts in the report agree with NVDA's own elements list (NVDA+F7) for links, headings and buttons.
- [ ] "Fix all of it": the question says in plain sentences what will be made, with the keys. Say no: nothing
  is made. Ask again and say yes: the answer names the add-on.
- [ ] The next-post and previous-post keys move NVDA's reading position post by post and say each post's first
  line. At the last loaded post the key says no more are loaded; a moment later it finds the new ones.
- [ ] On a video site: the key for play or pause works from anywhere on the page, both while playing and while
  paused. The key that reads the time reads it.
- [ ] A button that had no name is now read with its name in browse mode (arrow keys, B, the elements list)
  and when tabbing to it in focus mode. Buttons that had names sound as before. Braille shows the name.
- [ ] On another website, and in another program, each of the add-on's keys does what it did before.
- [ ] "Make NVDA+alt+P press the ... button on this page": the key is made and works. Asking for a key NVDA
  already uses gives another key, and says so.
- [ ] "Tell me when the ... changes" on a part that changes (a clock, a counter): the new text is spoken once
  per change, only while that site is in front, and NVDA stays responsive.
- [ ] With an unnamed button focused: "name the focused button Share on this website" names it, or says why it cannot.
- [ ] After restarting NVDA the fixes still work. "List what you have made" shows the add-on. "Save the add-on
  ... as a file" writes a file that installs in NVDA; "remove the add-on ..." ends the fixes and takes the
  names off the page.
- [ ] "Fix the add-on fixes ..." is refused with the reason, and nothing is rewritten.
- [ ] In a program whose controls NVDA can see (for example a settings window): "inspect this window for
  accessibility problems" counts its controls; a key made with "make a key that presses the ... button" works.
- [ ] In a game or program NVDA cannot read: the inspection says it is a picture to NVDA and what to use instead.
- [ ] A very long page (a feed scrolled far down): the inspection finishes, and NVDA does not freeze.

## Installed add-ons
- [x] "Which add-ons do I have" (owner, 0.4.0, 2026-11-17): the list matches NVDA's add-on store, with versions and enabled or disabled.
- [ ] "What does the ... add-on do": answered from its description and help. "Which keys does the ... add-on
  have": the keys match NVDA's Input gestures dialog.
- [ ] A command of an installed add-on can be found and run by describing it.

## Speech, braille and drivers
Do these with someone sighted nearby, or with a second way to get speech back, until they have passed once.
- [ ] "Which speech synthesizer am I using?" and "What braille display do I have?" answer correctly.
- [ ] "Change the voice to ...": the voice changes after the question.
- [ ] "Switch my speech synthesizer to eSpeak": asks; switches; the "does it work?" window is spoken by the
      new synthesizer; Keep it keeps it.
- [ ] The same, but do nothing for 20 seconds: the old synthesizer comes back and says so.
- [ ] Asking again warns that it was switched back before.
- [ ] "Switch to no speech", with no braille display: refused, with the reason, and nothing changes.
- [ ] "Set the volume to 0", with no braille display: refused.
- [ ] "Turn speech mode off" (an NVDA command): asks first and says how to undo it.

## Scrolling and screen scaling
Try these at the scaling the computer normally uses and, if possible, once more at another one (Windows
Settings, Display, Scale).
- [ ] In a window with a long list or text: "scroll down" asks first, then the view moves, and the answer says
      how far it stands if the window shows a scrollbar.
- [ ] "Scroll this window to the bottom" stops by itself at the end. Asking to scroll down again says that
      nothing moved.
- [ ] "Scroll up a little" moves less than "scroll up a page".
- [ ] With the focus on a slider or a combo box: "scroll down" does not change its value.
- [ ] Pointer mode (NVDA+Alt+K): Page Down and Page Up scroll what is under the pointer; Shift+Page Down
      scrolls one notch; at the end "Nothing moved" is spoken.
- [ ] Pointer mode: S says where a scrollbar is and how far along it stands, and the pointer is on its thumb:
      G, Down arrow a few times, G moves the view.
- [ ] Pointer mode: an arrow key moves the pointer about the same distance on the screen at 100 percent and
      at 150 or 200 percent scaling, and less in a very small window.
- [ ] On a second monitor with another scaling, the same holds, and clicks land where the pointer is.
- [ ] "Inspect this window for accessibility problems" in a program with a scrollbar says that its picture
      shows a scrollbar, and what the vision model sees that is worked with the mouse.

## The mouse from the keyboard
- [ ] On the desktop or in File Explorer: "right-click the ... icon" opens its context menu.
- [ ] "Double-click the ... icon" opens it.
- [ ] In a program with a slider NVDA cannot move: "drag the ... slider to the right a little" moves it.
- [ ] In the overlay (NVDA+Alt+O): G on an item says "Picked up"; G on another says "Dropped ... on ..." and the
      program shows the result (try moving a file onto a folder).
- [x] (Owner, 0.4.0, 2026-11-17, in Notepad.) NVDA+Alt+K turns pointer mode on and says the keys. The arrow keys move the pointer with a tone; at the
      edge the tone is low.
- [ ] In pointer mode: Enter clicks what is under the pointer; the Applications key opens a context menu.
- [ ] In pointer mode: G, arrow keys, G drags (try a slider or a window's title bar).
- [ ] In pointer mode: W says what is at the pointer; R reads the text there; P says the position.
- [x] (Owner, 0.4.0, 2026-11-17.) Escape turns pointer mode off, and the arrow keys work as usual again. Letters other than G, W, R, P, H
      were typed into the program as usual while it was on.
- [ ] "Make this control keyboard navigable" turns pointer mode on.

## Dials and sliders that are dragged (0.6.0)
- [x] In a program with a dial or knob NVDA cannot move (a music program, a plug-in, a game's settings): "let
      the arrow keys work the ... dial" asks first, then says how it is worked. The control is where it was.
      (Owner's report, 0.8.0, 2026-11-17, without detail.)
- [ ] Up, Down, Shift+Up and Control+Up change it, and what is said matches what the program shows.
- [ ] End runs to the end and says so; another Up says that nothing moved.
- [ ] R reads the text at the control; W gives the vision model's guess; M changes the way and says it.
- [ ] K keeps it and says the hotkey; Escape gives the arrow keys back and the mouse pointer goes back.
      (Not ticked: on 2026-11-17 no kept hotkey was in the data folder after the owner's run.)
- [ ] After restarting NVDA the hotkey takes hold of the control at once, without trying anything.
- [ ] In another program the hotkey does what it did before.
- [x] NVDA+Alt+K, pointer on a slider's thumb, D: the arrow keys move the thumb, also after several presses.
      (Owner's report, 0.8.0, 2026-11-17, without detail.)
- [ ] On a standard Windows slider that does not take the focus: it is worked through Windows itself, and the
      mouse pointer does not move.
- [ ] On something that is not dragged (a plain picture): VisionClaw says that nothing changed, and nothing is kept.
- [ ] In a game window: D on a slider of the settings screen works it, or says honestly that nothing changed.

## How controls are worked, and the deep query (0.6.0)
- [x] "Do a deep inspection of this window" in a program with custom controls: the report says how many
      controls are clicked, typed into and dragged, and what both models say about those NVDA cannot tell.
      (Owner's report, 0.8.0, 2026-11-17, without detail.)
- [ ] "Fix number ..." for controls that are dragged makes hotkeys after a question; each hotkey works.
- [ ] "Fix number ..." for controls the Tab key never reaches makes keys that press them.
- [x] With a control focused: "do a deep query of this control" names its kind, states, actions, what UI
      Automation offers, its window's class and toolkit, and how a sighted person works it.
      (Owner's report, 0.8.0, 2026-11-17, without detail.)
- [ ] The inspection of an ordinary, accessible program (Notepad, a settings window) reports no false problems
      of these kinds.

## The developer guides (0.6.0)
- [ ] "Get the latest NVDA developer guides" asks first, also with "ask before changes" turned off. No downloads nothing.
- [x] Yes downloads both and says how many sections each has. The files are in VisionClaw's data folder under guides.
      (Seen on the disk, 0.8.0, 2026-11-17: 79 and 119 sections.)
- [x] Afterwards a question about writing add-ons ("how does an add-on bind a gesture to a script?") is answered
      with words from the guides. (Owner's report, 0.8.0, 2026-11-17, without detail.)
- [ ] Without an internet connection it says that the guides could not be downloaded, and earlier copies stay.

## The very small models, one question at a time (after 0.6.0)
- [ ] VisionClaw's settings have "Ask the models one small question at a time" with Automatic, Always, Never,
      and the choice is kept after OK.
- [ ] With Qwen3.5 0.8B and Qwen2.5 Coder 0.5B chosen: "make NVDA speak a little faster" asks about the speech
      rate with a number, and changes it. "Turn off the typing echo" turns it off.
- [ ] With them: on a web page, a question about something the page does not say is answered with "What was
      looked up does not mention ...", not with a made-up answer.
- [ ] With the usual models and the setting on Always: the same requests still work, only slower.

## Add-ons
- [ ] "Write an add-on that says hello when I press NVDA+shift+H": asks to turn it on; "Let me read the code
      first" shows the code; after "Turn it on" the key works at once.
- [ ] After restarting NVDA the key still works.
- [ ] The question before turning an add-on on says in plain words what the code does (keys, what it reacts
      to, which programs, whether it speaks or beeps).
- [ ] A failing add-on: put an add-on that fails into `%APPDATA%\nvda\visionClaw\addons` (for example, change
      `ui.message` to `ui.mesage` in one VisionClaw wrote) and restart NVDA. Pressing its key gives no NVDA error
      sound; "had a problem ... is correcting" is spoken; after a while "was corrected and is on again", and the
      key works.
- [ ] While it is being corrected, NVDA reads normally and focus changes are announced.
- [ ] "Fix the add-on ..., it should say ... instead": it is changed and loaded again.
- [ ] With automatic correction off in settings, a failing add-on is turned off and that is spoken.
- [ ] "Save the add-on ... as a file": the file is in Documents, VisionClaw add-ons, and installs as a normal
      add-on.
- [ ] "Remove the add-on ...": the key stops working.
- [ ] With an unlabelled button focused: "Write an add-on that calls this button Play". The Last task box shows
      what the vision model saw and the control's details, and the button is then announced as Play.
- [ ] "Write an add-on that beeps when a link gets the focus": works in a browser, and NVDA still reads links.

## Agreement
- [ ] With two different models, note how often "The two models do not agree" appears for the requests above,
      and whether the choices offered make sense.
- [ ] With one model chosen for both jobs (for example Qwen3.5 9B and "Qwen3.5 9B, used for coding"): ask
      "Make NVDA speak a little faster", then press NVDA+Alt+C again and read the Last task box. It says "The
      model is choosing what to do" and "The plan is ready", and nowhere "two models", "both models" or "agree".
      It also says "One model does both jobs".
- [x] "What model is installed?": the answer names the model, says that it does both jobs (or names the two),
      gives its size on the disk, says where it runs, and ends with NVDA+Alt+M. No list of add-ons.
      (Owner's report, 0.8.2, 2026-11-17, without detail.)
- [x] "Which add-ons do I have?" right after it: NVDA's add-ons, not the ones VisionClaw wrote.
      (Owner's report, 0.8.2, 2026-11-17, without detail.)
- [ ] With one model for both jobs, the first request after NVDA starts: note how many seconds pass before the
      first step is announced, and for the same request again right after.
      (Owner, 0.8.2, 2026-11-17: asked a request twice in a row and reports that answering is faster. No
      seconds were given, and it was not said whether the first one came right after NVDA started. Not ticked.)

## Skills (after 0.11.0)
- [ ] NVDA+Alt+I opens the skills window. The list says each skill's name, and "yours" or "off" where that is so;
      arrowing through it fills the box below with everything about the chosen skill, which can be read line by
      line. The count under the list is right.
- [ ] New skill: the name, the line about what it is for, the starting words, the jobs it is for (a checkable
      list), what it tells VisionClaw, and steps (Add a step: a list of jobs, then the words) can all be reached
      with Tab and filled in by keyboard. Leaving out the starting words is refused with a message that says why.
- [ ] Change on a built-in skill keeps your copy, marked yours; "Delete your copy" brings VisionClaw's own back.
- [ ] Turn off, then Turn on: the button's name follows, and NVDA says the new state.
- [ ] Delete is only offered for your own skills, and asks first.
- [ ] Import a skill file: a SKILL.md from another computer is shown in full before it is kept.
- [ ] "Open the skills folder" (in the window and in VisionClaw's settings) opens File Explorer on the folder,
      with README.md in it.
- [ ] In the Ask window: "Make a new skill: when I ask about recipes, read the ingredients first" asks before
      saving, and the skill then shows in the window; "Which skills do you have?", "What does the chart skill
      do?", "Turn off the game skill", "Delete my recipes skill" each do what they say.
- [ ] "Quick status" says the time, the date and the battery, without the models choosing a plan.
- [ ] "Describe this photo" on a picture: the description starts with what kind of picture it is and its main
      subject (the skill "Describe a photo or picture").

## How VisionClaw answers: instructions for blind users
- [ ] NVDA menu, Preferences, Settings, VisionClaw: the button "How VisionClaw answers, and your own
      instructions" opens a window with a list of seven instructions and an edit box. Moving in the list puts
      the chosen instruction's words in the box, and the box can be read line by line.
- [ ] Write "Call me Sam." into your own instructions, press OK, ask "What time is it?" or a question such as
      "How do I read the title of this window?": the answer follows your instruction.
- [ ] Change "How answers are worded", press OK, open the window again: the entry says "(changed)". Press
      "Restore the original of this instruction" and OK: the entry no longer says "(changed)" and answers are
      as before.
- [ ] Change two instructions, press "Restore all originals" and OK: every entry is back to the original and
      your own instructions are empty. Cancel instead of OK keeps everything as it was.
- [ ] With your own instructions set, switch to another configuration profile and back (or reload the
      configuration with NVDA+Control+R): the instructions still apply.
- [ ] With your own instructions set, choose other models in the models window: the instructions still apply.
- [ ] NVDA+Alt+D on a dialog: the description starts with what is shown, says which button has the focus,
      and has no stars, hashes or list marks.

## Stopping NVDA
- [ ] NVDA exits without an error, and no `vcengine.exe` is left running (Task Manager).
