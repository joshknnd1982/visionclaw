---
name: Get my bearings
description: Says where the user is and what the window shows, in one go.
when: get my bearings, i am lost, i'm lost, where am i and what is here, orient me, what is in front of me
uses: where_am_i, describe
steps:
- where_am_i
- describe: Say what this window shows, from top to bottom: its title, its main parts, and its buttons and fields.
log: errors, objects, session
lands: told
---

Be brief: the program, the window and the focused control first, then the main parts of the window.
