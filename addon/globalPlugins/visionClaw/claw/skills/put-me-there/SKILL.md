---
name: Put me on a control, a page or a window
description: Puts the user exactly where they ask to be, and checks at every step that NVDA's focus really got there.
when: move the focus to, put the focus on, put the cursor in, put me in the field, put me on the page, page of the dialog, tab of the dialog, edit field, most useful control, most useful item
uses: go_to_control, go_to, window
log: errors, objects
lands: told
---

Go one step at a time: first the window or dialog, then its page, then the control, and go on only where NVDA says the last step landed. Say where the user is at the end: the control's kind and label, its page and window, what it shows, and the key that works it. Where the place is not there, say what there is instead and that nothing else was moved. Never press a button to get there without asking, and never say the focus is somewhere unless NVDA reports it there.
