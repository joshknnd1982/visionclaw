---
name: Find and press a button NVDA cannot reach
description: Finds a button or icon by its picture when NVDA cannot reach it, and presses it after asking.
when: cannot find the button, can't find the button, unlabelled, unlabeled, no label, button without a name, icon, cannot reach, can't reach, cannot tab to, can't tab to
uses: click, name_button, describe
log: errors, objects
lands: told
---

Look for the item by what it does as well as by its text: an icon has no text, so its picture tells what it is. When several items could be meant, choose the one whose name or picture fits the user's words best. Never press anything that sends, buys, pays, deletes or closes unless the user's words ask for exactly that.
