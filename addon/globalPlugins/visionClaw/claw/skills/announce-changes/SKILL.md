---
name: Be told when something changes
description: Makes NVDA say a status, a counter or a message when it changes, without being asked.
when: tell me when, let me know when, announce when, say when, notify me, keep me informed, status changes, progress, new message arrives
uses: add_fix, write_addon
log: errors, objects
---

Prefer a watch fix on the one control that shows the change over a written add-on. Say only the new text, never the whole window. Do not speak the same text twice in a row, and do not speak more than about once a second. An add-on must stop watching when its window closes.
