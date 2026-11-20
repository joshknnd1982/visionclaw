---
name: A control NVDA calls the wrong kind
description: For a control that NVDA reads as a pane, a group, plain text, unknown or clickable, though it is a button, slider, list or something else.
when: reads as pane, says pane, reads as unknown, says unknown, reads as text, reads as a group, says clickable, wrong role, wrong kind of control, custom drawn, owner drawn, window class, which toolkit
uses: check_access, object_facts, fix_access, add_fix, write_addon
log: errors, objects
---

What NVDA calls a control comes from the program: its role, its states, and the class of its window, which tells which toolkit or game engine drew it. Read these first. Work a control by what it does, found by the inspection, which asks the models only where the facts do not say and keeps what was found for this program. Prefer a name or a key as a lasting fix; an add-on that gives it the right kind only when nothing simpler works. Say what it is reported as and what it does.
