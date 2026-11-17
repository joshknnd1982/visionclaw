# VisionClaw test plan inside NVDA

Tick an item only after doing it in a running NVDA. Write the NVDA version and the models used at the top of
`docs/STATUS.md` when done. If something fails, copy the lines from NVDA's log (NVDA+F1) that start with
"VisionClaw".

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

## Settings
- [ ] NVDA menu, Preferences, Settings, VisionClaw opens and reads every control.
- [ ] "Graphics found" names the graphics chips of this computer.
- [ ] Each graphics choice works after OK: Automatic, Dedicated graphics card, Vulkan, Processor only
      (describe a window after each; with debug logging on, `engine.log` shows the device).

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

## Settings stay the user's
- [ ] Installing or updating VisionClaw changes no NVDA setting (compare the speech rate before and after).
- [ ] "Speak a bit faster": the question reads "You asked: speak a bit faster. Change speech rate from X to Y?".
- [ ] "What did you change?" names that change.
- [ ] "Undo that" asks, then puts the rate back to X, and says so.
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
- [ ] "What are the headings on this page?" lists them with their levels.
- [ ] "Take me to the heading ...": NVDA says the heading, and say all reads on from there.
- [ ] "Go back" and "reload this page".
- [ ] The same in Firefox, Chrome and Edge.

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

## The mouse from the keyboard
- [ ] On the desktop or in File Explorer: "right-click the ... icon" opens its context menu.
- [ ] "Double-click the ... icon" opens it.
- [ ] In a program with a slider NVDA cannot move: "drag the ... slider to the right a little" moves it.
- [ ] In the overlay (NVDA+Alt+O): G on an item says "Picked up"; G on another says "Dropped ... on ..." and the
      program shows the result (try moving a file onto a folder).
- [ ] NVDA+Alt+K turns pointer mode on and says the keys. The arrow keys move the pointer with a tone; at the
      edge the tone is low.
- [ ] In pointer mode: Enter clicks what is under the pointer; the Applications key opens a context menu.
- [ ] In pointer mode: G, arrow keys, G drags (try a slider or a window's title bar).
- [ ] In pointer mode: W says what is at the pointer; R reads the text there; P says the position.
- [ ] Escape turns pointer mode off, and the arrow keys work as usual again. Letters other than G, W, R, P, H
      were typed into the program as usual while it was on.
- [ ] "Make this control keyboard navigable" turns pointer mode on.

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

## Stopping NVDA
- [ ] NVDA exits without an error, and no `vcengine.exe` is left running (Task Manager).
