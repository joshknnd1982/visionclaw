# VisionClaw test plan inside NVDA

Tick an item only after doing it in a running NVDA. Write the NVDA version and the models used at the top of
`docs/STATUS.md` when done. If something fails, VisionClaw's own log has what happened: ask "open the
VisionClaw log", or open `%APPDATA%\nvda\addons\visionClaw\data\logs\visionclaw.log`. It is written whatever NVDA's own
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
- [ ] "Explore this page" on a news site: the landmarks are named in order, the main part's heading is right,
  and every key that is named does what the answer says (1, H, D, F, T, L, NVDA+F7).
- [ ] "Explore this page" on a page without headings or landmarks: P is named, H and D are not.
- [ ] On a sign-up form, leave a required field empty and write a wrong email address, press the form's button,
  then ask "Why won't this form submit?": both fields are named with the page's own message, and NVDA's reading
  position is on the first; Enter goes into it.
- [ ] The same on a form that only shows a red border: the answer says nothing is marked, and reads the lines
  of the picture that say what is wrong, or points to describing the window.
- [ ] "Summarize this page" with "one small question at a time" set to Always: the beginning of each part of
  the page, in the page's own words.
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
- [ ] Pointer mode (NVDA+Alt+K): K and I scroll what is under the pointer down and up, L and J right and left;
      Shift+K scrolls one notch down, and not sideways (try it in a browser); at the end "Nothing moved" is
      spoken. On a keyboard that has them, Page Down and Page Up still scroll.
- [ ] Pointer mode: Shift+K with Shift kept down for two seconds scrolls nothing and says to let go.
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
- [ ] In pointer mode: Enter clicks what is under the pointer; A opens a context menu; B brings the pointer
      back to the middle. In the overlay (NVDA+Alt+O), A on an item opens its context menu.
- [ ] In pointer mode: Shift+Enter on a file in a list opens that one file, and does not select a range.
- [ ] In pointer mode: G, arrow keys, G drags (try a slider or a window's title bar).
- [ ] In pointer mode: W says what is at the pointer; R reads the text there; P says the position.
- [x] (Owner, 0.4.0, 2026-11-17.) Escape turns pointer mode off, and the arrow keys work as usual again. Letters other than G, W, R, P, H
      were typed into the program as usual while it was on.
- [ ] "Make this control keyboard navigable" turns pointer mode on.

## Controls that need more than a click (1.1.0)
- [ ] "Hover over the ... icon" on something that shows a tip: the tip's text is said. On something that shows
      nothing: "Nothing VisionClaw can see appeared." No question is asked first.
- [ ] On a web page with a menu that opens when the mouse is over it: "hover over ..." opens it, and "list what
      is in the window" then lists its items.
- [ ] "Press and hold the ... button for 3 seconds" asks first, holds for three seconds, and says what the
      window then showed. Stopping the request (NVDA+Alt+X) while it holds lets go at once.
- [ ] "Make NVDA+Alt+3 hold down the ... button": the hotkey says "Holding the mouse button down on ...";
      pressing it again says "Let go of ..."; Escape lets go as well. Clicks work normally afterwards.
- [ ] "Middle-click the ... link" in a browser opens it in a new tab. "Control-click the second file" in File
      Explorer's picture adds it to the selection, and the Control key is not stuck afterwards (type a letter).
- [ ] "Click the seek bar 30 percent across" in a media player moves the position.
- [ ] "Swipe left on ..." in a program that takes swipes with the mouse; "draw a circle" in Paint draws a
      circle; "draw a line down then right with the right button held down" in a browser with mouse gestures.
      Each asks first and says whether the window changed.
- [ ] "Click the ... button as soon as it changes" on something that changes after a while: it is clicked
      then. On something that never changes with "wait 5 seconds": nothing is clicked, and that is said.
- [ ] "Click the ... 10 times" clicks ten times, evenly.
- [ ] "Zoom in" and "zoom out" in a browser or an image viewer: the view gets larger and smaller, and the
      Control key is not stuck afterwards.
- [ ] Pointer mode: T on a toolbar button says its tip. C on something that will change clicks it when it does;
      Shift+C only sounds the tone; any key stops the watch and says so.
- [ ] "Inspect this window" in a program with a button named like "Hold to record": the report says it is
      worked by holding the mouse button down, and "fix it" offers a hotkey for it.

## Dials and sliders that are dragged (0.6.0)
- [x] In a program with a dial or knob NVDA cannot move (a music program, a plug-in, a game's settings): "let
      the arrow keys work the ... dial" asks first, then says how it is worked. The control is where it was.
      (Owner's report, 0.8.0, 2026-11-17, without detail.)
- [ ] Up, Down, Shift+Up and Control+Up change it, and what is said matches what the program shows.
- [ ] T runs to the top end and says so; another Up says that nothing moved. B runs to the bottom end.
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

## The developer guides put to use, add-ons by what you want, NVDA Coach (after 1.1.0)
- [ ] "Which developer guides do I have" says both guides, the day, and the folder. With guides kept by 1.1.0 or
      older it also says they were kept by an older VisionClaw and how to get them again.
- [ ] After "get the latest NVDA developer guides" once more, the same question no longer says that.
- [ ] "What does the developer guide say about events" is answered in plain words, names the guide, and reads
      out no code.
- [ ] "Open the developer guides folder" opens the folder in File Explorer.
- [ ] "Delete the developer guides" asks, deletes on yes, and "which developer guides do I have" then says none.
- [ ] "Write an add-on that says the window class name of the focused control when I press NVDA+alt+K": VisionClaw's
      log shows the line "Given to the add-on writer from the developer guides", and the add-on works.
- [ ] "Write an add-on that beeps when a link gets the focus": the log shows no line from the guides, and the
      add-on works as before.
- [ ] "Is there an add-on that ..." with something one of your add-ons does: it names that add-on and its key.
- [ ] The same for something no add-on does: it says none does, and lists the add-ons.
- [ ] For an add-on that is turned off: it says so, and does not turn it on.
- [ ] Without NVDA Coach: "open NVDA Coach" says it is not installed and installs nothing; "teach me how to read
      the window title" answers from NVDA's user guide and names NVDA Coach once.
- [ ] With NVDA Coach installed: "give me a hint about browse mode" gives one hint; "coach me on reading the
      current line" gives one step; "teach me object navigation step by step" gives the steps; "which lessons
      does NVDA Coach have" and "how far am I in NVDA Coach" answer; "open NVDA Coach" opens its window.
- [ ] With NVDA Coach installed and Excel in front: "open NVDA Coach" says to leave Excel first.
- [ ] "From now on, give me only a hint." Then "how do I read the window title": the answer is a hint.
      "Forget that" puts it back.
- [ ] "What is new in the latest version of NVDA" is answered from NVDA's own list, and names the version.
- [ ] "Get the free NVDA training material" asks first, also with "ask before changes" turned off, and names
      the NVDA wiki, AFB and Hadley and 18 requests. No downloads nothing.
- [ ] Yes downloads 18 pages. VisionClaw's data folder has `training` with three folders of Markdown files, and
      each file says at its top where it is from.
- [ ] "Which training material do I have" says the three sources, the day and the folder.
- [ ] "Teach me how to move around a web page" is answered with a lesson, and says where it is from.
      "How do I move to the next heading" is answered from NVDA's own help as before.
- [ ] "I come from JAWS." Then "what is the review cursor": the answer uses the wiki's page for people from JAWS.
- [ ] "Delete the training material" asks, and deletes on yes.
- [ ] After the first question, VisionClaw's data folder has `help` with `nvda-user-guide.md`,
      `nvda-whats-new.md`, and after a question about add-ons a file for each add-on in `help\addons`.
- [ ] "What can you download for me" names the developer guides, the lessons, notes on a program, a newer
      version and newer models, says which are here, and gives the words for each.
- [ ] In VisionClaw's settings, the button "What VisionClaw can download for you" opens the same text in a
      window that can be read line by line.
- [ ] On a fresh installation, the first question ("how do I read the title") ends with one sentence that
      begins "This is said once" and names "what can you download for me". The next question does not.
- [ ] The first request for an add-on ends with one sentence about the NVDA Add-on Development Guide; the
      second does not. After "get the latest NVDA developer guides", it is never said.
- [ ] "I am using my real mouse. How do I hear what is under the pointer?" names NVDA+M and does not tell you
      to use the keyboard instead.
- [ ] In the description window (NVDA+Alt+W pressed twice on a window), "how do I read the title of this window with the
      keyboard" names NVDA+T; "which button has the focus" is answered from the picture as before.

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
- [ ] A failing add-on: put an add-on that fails into `%APPDATA%\nvda\addons\visionClaw\data\addons` (for example, change
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

## Fingers and pressure (after 1.2.0)
- [x] (Run on 2026-11-18 on the owner's computer, outside NVDA: it said all three.)
      First, outside the Ask window: `python tests/live_touch.py --yes`. It opens a small window of its own,
      touches and presses only inside it, and prints what Windows told that window. It must say that two
      fingers began further apart than they ended, that the pen's pressure rose, and "Windows took the
      fingers and the pen as VisionClaw makes them."
- [ ] In a program that takes touch (the Maps or Photos app, or a map on a web page in Edge): "pinch the map
      with two fingers" asks first, then says that what the window shows changed, and the map is smaller.
      "Spread two fingers" makes it larger. "Swipe left with two fingers" moves it.
- [ ] In a program that takes no touch but zooms with the wheel (a document in a browser): "zoom in with two
      fingers" says that the program seems to take no touch, that the Control key and the mouse wheel were
      used, and that this is kept. The same request again uses the wheel at once and says so.
- [ ] "Turn the picture 90 degrees clockwise with two fingers" in a program that cannot turn: says that nothing
      changed, and tries nothing else.
- [ ] "Double tap the Start icon", "touch and hold" an item for 2 seconds: what happens is what a finger does
      there. Stopping the request (NVDA+Alt+X) during a long hold lifts the finger at once.
- [ ] In a drawing program that uses Windows Ink (Paint, OneNote, Whiteboard), with a pen or brush chosen whose
      width follows pressure: "draw a line to the right with the pressure rising" draws a line that gets
      thicker. "Press hard" and "press lightly" leave a larger and a smaller dot. Have someone sighted look,
      or ask VisionClaw to describe the window.
- [ ] On a computer with a touch screen, with NVDA's touch interaction on: the question before a gesture says
      that NVDA's own touch gestures are put aside for that moment; after the gesture NVDA's touch gestures
      work again (a tap reads what is under the finger).
- [ ] In a program started as administrator: the answer says that Windows did not allow it, and why.

## Games that read the mouse directly (after 1.2.0)
- [ ] In a game whose view the mouse turns: "how does this game use the mouse?" says that the program hides
      Windows' mouse pointer and keeps it inside its window. "The mouse turns the view in this game" asks and
      keeps it. "Turn left" asks, then says that the view changed, and it did. "Turn around" turns much
      further. "Direct mouse movement is too fast" makes the next "turn left" shorter.
- [ ] In the same game, pointer mode (NVDA+Alt+K) says that the mouse turns the view here; the arrow keys turn
      and look, Enter fires or clicks where the game aims, P says that there is no pointer with a place.
- [ ] In a game that draws its own pointer in its menus: "this game has its own mouse pointer", then "click
      Options" (or another thing in the menu): the game's pointer goes to it and it is pressed. If it lands
      beside it: "measure the game's pointer", then again.
- [ ] In such a game, pointer mode: M says each of the three ways in turn; with the game's own pointer the
      arrow keys move that pointer.
- [ ] When the game shows Windows' own pointer again, as in a settings window, clicks by name work the usual way.
- [ ] "Use the normal mouse pointer again" forgets it; "list what you have made" no longer names the game.
- [ ] "Inspect this window" in such a game: the report says what Windows reports of its pointer, and what to
      tell VisionClaw.
- [ ] A game with cheat protection: note whether it takes the movements at all.

## A game controller (after 1.2.0)
- [ ] Plug in or switch on an Xbox controller: within a few seconds VisionClaw says once that a game controller
      is connected and how to turn controller mode on. Unplug it: it says that it is gone.
- [ ] "Is a controller connected?" and "what do the buttons on my controller do?" are answered at once, with
      no model's wording.
- [ ] Hold View and Menu together for a second: the help is spoken. NVDA+Alt+J turns the mode off and on.
- [ ] Left stick: a small push moves the pointer slowly, a full push fast; with the left shoulder button held,
      slowly and exactly. When the stick comes to rest, what is under the pointer is said, once. At the
      window's edge there is a low tone, and perhaps a buzz; note whether the buzz is felt.
- [ ] A clicks, B right-clicks, X double-clicks, Y says what is under the pointer; the direction pad moves one step.
- [ ] Right trigger: pull it on a window's title bar, move the stick, let go: the window moved. "Holding." and
      "Let go." are spoken.
- [ ] Left trigger in a drawing program that follows pressure: pulling it further draws a thicker line while
      the stick moves; "Pen down." and "Pen up." are spoken.
- [ ] Right stick scrolls a long page up, down and sideways. Pressed in, in a game whose view the mouse turns,
      it looks around; pressed in again, it scrolls.
- [ ] Right shoulder button with right and left on the direction pad: the pointer jumps from one thing found in
      the window to the next, and its name and number are said; A then clicks it.
- [ ] Left shoulder button with B on something that has a tip: the tip is read. With X on a dial: the direction
      pad then turns the dial, and the View button gives it back.
- [ ] "Make the X button on my controller click" something by name: it asks, and X then does that in this
      program, in controller mode and out of it, and not in other programs. "Remove the X button on my
      controller" removes it.
- [ ] With controller mode off, play a game with the controller for a few minutes: VisionClaw does nothing.
- [ ] Unplug the controller while the right trigger is pulled: the mouse button comes up, the mode is off, and
      that is said.
- [ ] Settings, Game controller: with "say nothing when one is connected" nothing is said on plugging in, and
      View and Menu still work; with "do not look for a game controller" neither works, and asking says why.
- [ ] A controller of another make (PlayStation, or a plain USB gamepad): it is announced as of another make;
      note which of its buttons do what the help says, and which do not.

## Working the computer itself (after 1.4.0)
- [ ] "Check and see if my recycle bin needs to be emptied": answers at once, with the number of items and their
      size as File Explorer shows them.
- [ ] Delete a test file, then "empty the recycle bin": a question names the number of items; No leaves them;
      Yes empties it, and the answer says how many were deleted.
- [ ] "Open the Recycle Bin", "open Notepad", "open my downloads folder", "go into my Windows settings", "open
      Bluetooth settings": each opens after a question, and the answer names the window in front.
- [ ] "Open" with a word that several programs have: the question lists them, and the chosen one opens.
- [ ] "First, look at my screen. If you see recycle bin, open it." with the desktop in front: the screen is
      described, the Recycle Bin is found by its name, and it opens. With a window covering the desktop: it
      says that it is not on the screen and that it was not opened.
- [ ] "Turn down my system volume": 10 points lower, and NVDA is still heard. Repeated near 10 percent: it stops
      at 10 and says why. "Mute my computer" without a braille display: refused, with the reason.
- [ ] "Switch to" a program that is open; "close Notepad" with unsaved text: it says the window is still open.
- [ ] "Minimize all windows": the desktop is in front. Windows+D brings the windows back.
- [ ] "What is in my downloads folder" and "find the file named" a word of a file you have.
- [ ] "How much disk space do I have left", "how long has my computer been on", "which programs are running".
- [ ] "Lock my computer": asked, then locked. "Restart my computer", then within 30 seconds "cancel the restart".
- [ ] "Go into my Windows settings, turn down my system volume, close Windows settings, then go to gmail.com in
      my Google Chrome and tell me how many emails I have": five things, each announced as a step, in order.
- [ ] In a program with a settings dialog that has tabs: "in this dialog, turn on" an option that is on another
      page: the page is named, and the option is on afterwards. Then a slider "up a bit".
- [ ] In a program NVDA cannot read: "find the settings button in this app, then turn the volume up a bit".
- [ ] In NVDA's log viewer or VisionClaw's log: "Offered for this: N of M kinds of request" appears, with N
      far smaller than M, and a request about a web page is still understood with no browser in front.

## Your own files (after 1.5.0)
Use test files you can afford to lose.
- [ ] "Create a folder called VisionClaw test in my documents": asked, made, and File Explorer shows it.
- [ ] Put two text files there by hand. "Rename the file" with a word of one name "to" a new name: the question
      names the file and the new name with its ending; afterwards File Explorer shows the new name.
- [ ] "Undo that": the old name is back.
- [ ] "Move the file" to "my desktop", then "undo that": it is back where it was.
- [ ] "Copy the file" to "my desktop": it is in both places.
- [ ] Rename one file to the name of the other: refused, and nothing is changed.
- [ ] "Delete the file" with the name of the copy on the desktop: the question says Recycle Bin; after Yes the
      file is in the Recycle Bin, and Restore there brings it back.
- [ ] A word that several files have: a question lists them; "None of these" changes nothing.
- [ ] "Delete this file" says to give the name, and names F2 and Delete for the file selected in File Explorer.

## A setting only for one program (1.7.0)
Do this in a program you do not mind NVDA behaving differently in, such as Notepad. Afterwards "remove the
settings for this program" takes it all away again.
- [ ] In Notepad: "make NVDA speak a little faster, only in this program". The question says that this is only
      for Notepad and that a configuration profile will be made, also with confirmations turned off. After Yes
      the answer says what the rate was and is, and names the profile. **NVDA speaks faster at once, in Notepad.**
      This is the first thing to find out: whether the profile applies without leaving the program.
- [ ] Alt+Tab to another program: the old rate. Back to Notepad: the faster one.
- [ ] NVDA+Control+P: the profile is in the list, named after the program, and marked as triggered while Notepad
      was in front. NVDA menu, Configuration profiles, Triggers: "Current application (notepad)" has it.
- [ ] In Notepad: "turn off the typing echo just in this app": no new profile is made, and the question says so.
- [ ] In Notepad: "undo that": the typing echo is back in Notepad. From another program: "undo that" changes
      nothing and says to switch to Notepad.
- [ ] From another program: "set punctuation to all only in Notepad": nothing changes, and it says to switch.
- [ ] "Which programs have their own settings?" names Notepad, its profile, and what VisionClaw changed.
- [ ] Turn a profile on by hand (NVDA+Control+P, Manual activate), then ask for a setting only in this program:
      refused, with how to turn the manual profile off. Turn it off again.
- [ ] "Make NVDA speak faster, only in my browser" in Notepad: the question ends "This will apply in every
      program". Answer No.
- [ ] Restart NVDA: Notepad still has its own rate. Then "remove the settings for this program": asked, and
      Notepad speaks like everything else again; the profile is gone from NVDA+Control+P.

## Requests that follow the one before (1.7.0)
- [ ] "Turn the computer's volume up a bit", then "do that again", then "the other way", then "say that again":
      each answer begins "Understood as" and says what was done; the last repeats the answer and changes nothing.
- [ ] "Make NVDA speak a little faster", then "a bit more", then "too fast".
- [ ] "What is in my downloads folder", then "open the second one": the question names the second file.
- [ ] "How do I read the title of this window?", then "and the status bar?": the answer is about the status bar,
      and begins with the question written out in full.
- [ ] "Open Notepad", then "and maximize it".
- [ ] After a pause of more than ten minutes, "a bit more" is taken as a request of its own.
- [ ] Restart NVDA, then "do that again": it says there is no earlier request.

## A date in a calendar (1.7.0)
- [ ] On a web page with a date picker whose calendar is open (a flight or hotel search): "pick" a date four
      months ahead "in this calendar". The question names the date with its weekday and the month showing. After
      Yes the calendar goes month by month and the day is chosen; check the date field.
- [ ] The same with a date in the month showing, and with a date last month.
- [ ] "Set the date to 3/4/2027": a question asks which of the two readings is meant.
- [ ] "Pick next Friday in the calendar": a question asks which Friday.
- [ ] With no calendar showing: it says so, and says how to open one.
- [ ] In a program whose calendar NVDA cannot read: the same request; the answer says the calendar was read from
      the picture and to check the date field.
- [ ] A day that is greyed out, such as a date in the past on a booking site: not pressed, and that is said.

## Asking by voice (1.7.0)
- [ ] NVDA+Alt+V with no speech model: a question names Qwen3-ASR 0.6B, its size and Hugging Face. No downloads
      nothing. Yes downloads it and says how far it is every ten percent; pressing the button again stops it,
      and asking again goes on from where it stopped.
- [ ] NVDA+Alt+V: a high beep, then say "what is on my screen". Stop speaking: a lower beep, then NVDA says "You
      said: ..." and the words are in the box. NVDA says nothing between the two beeps. Enter sends it.
- [ ] Say "make NVDA speak a little faster, only in this program": NVDA is written NVDA, not Nvidia.
- [ ] Say a date: "pick the fourteenth of March twenty twenty-seven in this calendar".
- [ ] NVDA+Alt+V and say nothing: after about eight seconds, "Nothing was heard".
- [ ] NVDA+Alt+V, start a long sentence and press Alt+V in the middle: what was said so far is in the box.
- [ ] In the Ask window, Alt+V does the same as the button. With text already in the box, what is said is added.
- [ ] With no microphone, or the microphone turned off in Windows' privacy settings: it says so plainly.
- [ ] "Can I ask you by voice?" says that it is ready and names the keys. "Delete the speech model": asked, then
      gone. VisionClaw's settings offer both speech models.
- [ ] After a spoken request, no `vcengine.exe` for the speech model is left running (Task Manager shows at most
      the engines of the other models).

## Everywhere, or only here (1.7.0)
Do this after "A setting only for one program", while Notepad still has settings of its own.
- [ ] In Notepad: "make NVDA speak a little faster". A question asks: only in Notepad, or everywhere? Choose
      Everywhere: the answer begins "Everywhere", and says that Notepad keeps its own value. In another program
      NVDA is faster; in Notepad it is as before.
- [ ] In Notepad: "speak words as I type in every application": no question about where, and other programs change.
- [ ] In Word: "stop announcing capital letters in Word": taken for Word alone, with no "only".
- [ ] In a program without settings of its own: "set punctuation to all": changed as always, and the answer names
      the programs that keep a value of their own, if any.
- [ ] "Undo that" after each: it is put back where it was made, also from inside Notepad.

## Working through a task (1.7.0)
- [ ] In a mail program or Word: "I'm stuck, I want to" and something its menus or ribbon can do. The question
      names a thing and its key. "No, only tell me where it is": nothing is pressed. Again, "Yes, press it": it is
      pressed, and the answer says what that brought up.
- [ ] A task that takes more than three steps: after the third, it asks whether to go on.
- [ ] A step that opens another program (a link that opens the browser): it stops and says so.
- [ ] A thing called Send or Delete as the next step: the question says it may not be possible to take back.
- [ ] In a program NVDA cannot read: the things are found in the window's picture and clicked with the mouse.
- [ ] With the Ask VisionClaw window left open in front: "click the Send button" is refused, with the reason.

## A voice of its own (1.7.0)
- [ ] "Customise VisionClaw's voice": a question explains what will happen. After Yes, NVDA's Speech settings open,
      and their title names the profile VisionClaw voice. Choose another voice or rate and press OK.
- [ ] Within a few seconds of closing the window NVDA says that VisionClaw's voice is set, in your own voice again.
- [ ] Ask VisionClaw anything: its progress and its answer are in the voice you chose; NVDA's own speech (keys,
      focus) is in yours. Braille shows the same as before.
- [ ] Choose another synthesizer for VisionClaw's voice: its words come from that one, and NVDA's own from yours,
      without NVDA getting stuck on the other synthesizer.
- [ ] "Turn off your own voice": VisionClaw speaks like NVDA. "Turn it on" again. "Remove VisionClaw's voice":
      asked, then the profile is gone from NVDA+Control+P.
- [ ] Press Escape in the Speech settings instead of OK: your own voice is back, and nothing was kept.

## The JAWS Migration Assistant and ClassicSpeech (1.7.0)
Only with these add-ons installed. Neither was installed where VisionClaw's code for them was written.
- [ ] With the JAWS Migration Assistant, on a computer that has JAWS: "what is JAWS's Insert+F7 in NVDA?" says
      what the key does in JAWS and names the NVDA command with its key. Compare with NVDA+Shift+J, K, Insert+F7.
- [ ] "What is the JAWS say line command in NVDA?" and "what did the JAWS migration bring over?".
- [ ] With ClassicSpeech: "set ClassicSpeech to Advanced": asked, changed, and NVDA says less about each control at
      once. "Undo that" brings Beginner back.
- [ ] "Which speech schemes do I have?", "switch to the scheme" and a name, "turn sound schemes off", "open voice
      profiles".
- [ ] Without either add-on: the same requests are answered as questions, and nothing claims the add-on is there.

## What is in a part of Windows (1.9.0)
The owner's request that failed in 1.8.0 first. Nothing here changes anything, except that the hidden icons are
shown for a moment and hidden again.
- [ ] "Tell me all objects that are currently in the system tray." from the desktop: every icon shown on the
      taskbar, the clock, and the key Windows+B. No "I cannot see". Compare with Windows+B and the arrow keys.
- [ ] The hidden icons are read too (NVDA's own icon is usually among them). Afterwards Show hidden icons is closed
      again, and NVDA's focus is back in the window you were in, not on the taskbar. If the hidden ones are said to be "could not be read", say so.
- [ ] The same from inside another program, such as Notepad: the tray is read, Notepad is not touched.
- [ ] "Is NVDA running in the system tray?", "how many icons are in the system tray?".
- [ ] "Which programs are on my taskbar?": pinned and running programs, Start and Search.
- [ ] "What icons are on my desktop?": the desktop's icons, also from another program.
- [ ] "Read my notifications" and "what is in quick settings": opened with Windows+N and Windows+A, read, and left
      open; Escape closes them. Asked again while open: read without closing.
- [ ] "Right-click the volume icon in the system tray": asked, then the volume icon's menu opens.
- [ ] "Click Dropbox" (or another program with a tray icon) from Notepad: VisionClaw says it is in the notification
      area and asks before it clicks it there.
- [ ] "What is the system tray?" and "how do I get to the system tray?" are still answered as questions.

## Understanding your words, the work sheet, add-ons in pieces (1.11.0)
- [ ] "Take a peek at the screen": the answer begins "Understood as: look at the screen." and describes it.
- [ ] "Kill the typing echo": understood as turn off the typing echo, asked, and turned off. "Undo that" puts it back.
- [ ] "Type I wanna go home" in Notepad types exactly "I wanna go home".
- [ ] "When I say shh, I mean stop talking": asked, then kept. The file understanding.md is in VisionClaw's data
      folder with that line. "Shh" is then understood as "stop talking". "Which words have I taught you" lists it;
      "forget the word shh" forgets it.
- [ ] While a long request runs (for example "write an add-on that beeps when a link gets the focus and says the
      time with NVDA+Alt+T"), the folder work in VisionClaw's data folder holds one request-....md file, which can be
      opened and read. When the request is done, the folder is empty. The same after NVDA+Alt+X stops a request.
- [ ] That add-on is announced as written in 2 pieces; the beep is written by plain code. Turned on, a link that gets
      the focus beeps, and NVDA+Alt+T says the time.
- [ ] "Write an add-on that says heading whenever a heading gets the focus, and only works in Firefox": before it is
      turned on, VisionClaw says that in browse mode moving to a heading does not move the focus.
- [ ] "Give me a key that reads the window title": VisionClaw says which free key it chose; the key works.
- [ ] On a photo or a window: "what is in this picture, and is there any text in it?": two answers, each after its
      own question.

## Status updates while VisionClaw takes long (1.12.0)
- [ ] With Qwen3.5 9B and "How much the models think before acting" set to High, NVDA+Alt+C: "write an add-on that
      beeps when a link gets the focus". After 15 seconds without a spoken step: "Still working on your request, 15
      seconds so far.", the step, and what the model is doing ("Starting the coder model." or "The coder model is
      thinking before it answers; thinking is set to high."). The first update ends "Press NVDA+Alt+P at any time to
      hear how far it is, or NVDA+Alt+X to stop it."; later ones do not.
- [ ] NVDA+Alt+P during that request says how far it is; the next update comes 15 seconds after it, not sooner.
- [ ] While VisionClaw asks a question (a setting change to confirm), no update is said until it is answered.
- [ ] Right after NVDA starts, with the 9B not yet loaded, NVDA+Alt+F: "Still describing the screen, 15 seconds so
      far. Starting the vision model." Press NVDA+Alt+P, then an arrow key, while waiting: the description still
      comes. Again, and press NVDA+Alt+X while waiting: "Stopping.", and no description comes.
- [ ] Once a quick description is being spoken, Control stops it, as before.
- [ ] NVDA+Alt+F pressed twice: updates until the description window opens, none after.
- [ ] In the description window, ask a question and arrow through the text while waiting: the answer still comes.
- [ ] NVDA+Alt+O in a window with many unnamed icons, with the 9B: "Still naming the icons in the overlay, ... 3 of 16
      icons done so far.", and at the end "Finished naming the icons in the overlay." Escape before the end: nothing
      more is said about the icons.
- [ ] NVDA+Alt+V: nothing is said while the microphone is open. With a long request spoken, if working out the words
      takes over 15 seconds: "Still working out what you said".
- [ ] Settings, "Status updates while VisionClaw takes long": Never, and no update is said, but NVDA+Alt+P still
      answers; 10 seconds, and updates come every 10 seconds.
- [ ] With a braille display: the updates are shown on it too.

## Ten things that used to need sighted help (1.12.0)
None of these has run inside NVDA. Each is one real run; say what you hear.
- [ ] Settings: "make NVDA only speak words when I type". The answer begins "Understood as", and two settings are
      asked about and changed: typed words on, typed characters off. "Undo that" twice puts both back.
- [ ] A scanned form (a PDF that is only a picture, open in Adobe Acrobat with Fill and Sign chosen, or any picture
      of a form in a viewer): "click the line next to Full Name and type my name". First say "remember that my name
      is" and your name. VisionClaw asks with the label and your name in the question, clicks, types, and says
      whether the text is read there. Check with NVDA+R or by asking to read the window that the name is on the line.
- [ ] The same form: "click the dotted line labelled Signature so I can sign": the line is clicked, nothing is typed,
      and the answer says that VisionClaw does not sign for you.
- [ ] The same form, a label that is printed twice: VisionClaw asks which one, by where each is on the page.
- [ ] An installer with a page that offers extra software (many free programs have one): "uncheck any bundled
      toolbars in this installer and click Next until the installation starts". One question first; then each page
      is said; the offer is unchecked and named; the licence page asks you; the Install button asks you. Say no
      at Install and check that nothing was installed.
- [ ] An installer drawn by its own code, where NVDA reads nothing: the same request. The pages are read from the
      window's picture; say whether the right button was pressed each time.
- [ ] A game's launcher or a program with its own settings window: "click the Play button in this launcher, open the
      Settings menu, and turn on subtitles and narration" (use names your program has). Four steps; each option is
      said with what it was and what it is now.
- [ ] A web form that marks a wrong field only by a red border (many sign-up pages; leave a required field empty and
      press the send button first): "why won't this form submit". The answer names the field outlined in red, and
      NVDA's reading position is on it: press NVDA+Tab or read the current line to check.
- [ ] An audio plug-in or program with a drawn knob that shows its value as a number: "turn the Mix knob down to 35
      percent" (use a knob your program has). VisionClaw asks, moves it step by step, and says what it shows now.
      Check the value with the program's own way. Then a knob that shows no number: it says so and leaves it.
- [ ] WhatsApp Web, Discord or another chat with a picture in it: "what does the latest picture in this chat say",
      then "explain the joke in the latest picture". The answer begins with which picture was looked at.
- [ ] A shop's page with a product photo: "look at the product photo, is it navy blue or black". The measured
      colours are said first, then the model's answer.
- [ ] Microsoft Word with a document of your own that you have a copy of: "format this document in APA style".
      The question names every change. Afterwards NVDA+F on a paragraph says the font and the spacing; one
      Control+Z in Word puts everything back. This is the first thing to try in Word: whether Word's own
      interface is reached at all.
- [ ] Word: "does my document fit on one page" and "how many pages is this document": the numbers match Word's own
      status bar (NVDA+End).
- [ ] Google Docs: "format this document in APA style": nothing is changed, and the answer gives Google's keys.
- [ ] A page with a check box that asks whether you are a person: "what kind of check is this", then "click the
      verify you are human box". VisionClaw asks before pressing, and says what the page shows afterwards. It never
      says the check was passed unless the page says so.
- [ ] A check with a puzzle of pictures: "what do the squares show". Each square is said by number. Then "select
      squares 1 and 4, then verify" (your own numbers): only those are clicked, after a question. "Select all
      squares with traffic lights" selects nothing and says that you choose.
- [ ] A shop's page with colour swatches: "select the dark blue colour option". The question names the option and
      its measured colour; afterwards VisionClaw says what the page marks as chosen.
- [ ] A shop's page at the last step, with a button that buys (do not go through with it): "click the Place Order
      button", with confirmations turned off in VisionClaw's settings. VisionClaw still asks, and reads the total
      from the page. Say no: nothing is pressed.
- [ ] A field for a card number or a password: "type 1234 into the card number field": VisionClaw refuses and says
      why.
- [ ] An airline's seat map: "find a free window seat near the front". The best few are said with reasons; say no
      to the question, and no seat is taken.

## Stopping NVDA
- [ ] NVDA exits without an error, and no `vcengine.exe` is left running (Task Manager).
