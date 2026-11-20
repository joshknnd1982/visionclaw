---
name: Play a game the screen reader cannot read
description: Reads a game's menus and text from its picture and says where things are.
when: game, games, playing, menu of the game, level, inventory, character, score, health, game screen
uses: read_text, describe, click, keyboard_mouse, learn_app, gesture, timed_click, turn_view, touch, controller_mode, set_control
log: errors, objects, freezes, input help
lands: told
---

Read the text the game shows first, exactly. For a menu, say the choices in order and which one is selected. Say where things are on the screen in plain words such as top left or middle. Say numbers such as score, health, money or time exactly. Suggest pointer mode only when nothing can be listed or read. Where the scratchpad of this game says what a key does or where a menu leads, use it, and say that it was written down before.
