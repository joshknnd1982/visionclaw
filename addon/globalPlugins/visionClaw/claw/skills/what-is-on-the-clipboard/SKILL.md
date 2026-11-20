---
name: What is on the clipboard
description: Reads the text on the clipboard with NVDA's own command.
when: what did i copy, what's on my clipboard, what is on my clipboard, read my clipboard, read the clipboard
uses: do_command
steps:
- do_command: report the text on the clipboard
log: errors
lands: stay
---

Say the text exactly as NVDA reports it. Where the clipboard holds no text, say so, and that a picture on the clipboard can be described with NVDA+Alt+D.
