---
name: Which command a key runs, and whose it is
description: For keys tried in input help: the last key or all of them, the command each runs, and whether it is NVDA's own or an installed add-on's.
when: input help, which add-on does that key, whose key, whose command, key belong, keys i tried
uses: nvda_log, addon_question, explain_keys
log: errors, input help, add-ons
---

Say each key as NVDA writes it, the command it runs in the words of the result, and whose it is: NVDA itself, NVDA's support for a program, or an add-on by its name. Say when a key runs no command. When no key was tried, say that NVDA+1 turns input help on and off, and that while it is on every key is said instead of being carried out. Never guess whose a command is.
