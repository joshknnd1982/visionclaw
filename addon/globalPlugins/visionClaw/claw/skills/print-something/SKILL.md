---
name: Print a document or page
description: For printing what is in front: opens the program's own print window and says its choices; nothing is printed before the user says yes.
when: print this, print the page, print the document, print it, my printer, the printer, print preview, print settings
uses: press_keys, where_am_i, click, set_control, explain_keys, describe, open_thing
steps:
- press_keys: press control+p
- where_am_i
log: errors, objects
lands: told
---

Open the program's own print window with its key, then say the printer, the pages, the number of copies and the button that prints, in the words of the window. Change a choice only when the user's words ask for it. The button that prints is pressed only after the user says yes, since paper and ink are used. When no printer is found, offer the Printers and scanners page of Windows Settings.
