---
name: Help VisionClaw offered for a place that tells NVDA little
description: The help the user took with NVDA+Alt+Y after VisionClaw noticed a window, dialog or control that tells NVDA little.
when: tells nvda almost nothing, nothing in this dialog has the focus, nvda logged errors in this program
uses: go_to_control, nvda_log, check_access, describe
log: errors, objects, freezes
lands: told
instead of: stubborn-program
---

The user took this help; still ask before anything is changed. First make the place workable from the keyboard, then put the user on what is most likely to help, and say why it was chosen in words a sighted helper would use: highlighted, the default button, larger, its colour, an empty field. Say what was read from a picture and that it can be wrong. End with the keys that work it and the way back. Where a scratchpad line says how this window was worked before, use it first.
