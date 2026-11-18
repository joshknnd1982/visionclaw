---
name: Play a game that reads the mouse directly
description: For a game that takes no notice of where the mouse pointer is put: the mouse turns its view, or it draws a pointer of its own.
when: turn left, turn right, turn around, look around, own pointer, own cursor, mouse look, first person, crosshair, reads the mouse directly, direct mouse
uses: turn_view, mouse_way, keyboard_mouse, controller_mode, click, describe, explain_keys, nvda_question
---

Such a game follows how far the mouse itself moves. Where the mouse turns the view, VisionClaw moves the mouse itself to turn or look and says whether the view changed; too fast or too slow can be said and is kept for the game. Where the game draws its own pointer, saying so once makes clicks by name work again. In pointer mode, NVDA+alt+k, m changes between the ways, and the arrow keys then move the mouse itself. A game that refuses movements made by a program cannot be worked this way.
