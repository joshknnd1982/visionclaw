---
name: Change which key does something
description: Gives a command another key, or a program a key it lacks, in the simplest way.
when: remap, different key, another key, change the key, reassign, assign a key, key for this, rebind
uses: nvda_question, explain_keys, make_hotkey, add_fix, write_addon
log: errors, input help, add-ons
lands: moved
---

An NVDA command gets a new key in NVDA's Input gestures dialog: open the NVDA menu with NVDA+n, then Preferences, then Input gestures. Say that first when the command belongs to NVDA. A key that clicks or reads something in a program is a hotkey helper or a fix. Write an add-on only when nothing else can do it, and never take a key that NVDA or the program already uses.
