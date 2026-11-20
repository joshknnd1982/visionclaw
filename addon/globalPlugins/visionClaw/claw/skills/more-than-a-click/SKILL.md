---
name: Work a control that needs more than a click
description: For a control that is hovered over, held down, swiped, drawn on, or clicked at the right moment.
when: tooltip, hover menu, press and hold, hold down, long press, swipe, mouse gesture, right moment, timing, middle click, control click, shift click, joystick
uses: click, gesture, timed_click, scroll, keyboard_mouse, make_hotkey, check_access, explain_keys, nvda_question
log: errors, objects
lands: told
---

VisionClaw does each of these from the keyboard. Resting the pointer on a thing shows its tip or menu, and what appeared is read out. The mouse button is held down for a number of seconds, or by a hotkey until the hotkey is pressed again. A swipe needs its direction and a shape its name. A click at the right moment waits until the thing changes. In pointer mode, NVDA+alt+k, t rests the pointer, g holds the button, c clicks when what is there changes. Say what changed afterwards.
