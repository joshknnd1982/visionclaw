---
name: Start my day
description: Says the time, the date, the battery and the notifications waiting, one after the other.
when: start my day, morning briefing, daily briefing, what did i miss, catch me up
uses: do_command, read_place
steps:
- do_command: what time is it
- do_command: what is the date today
- do_command: how much battery is left
- read_place: what notifications do I have
log: errors, session
lands: told
---

Say each part in a few words, in this order: the time, the date, the battery where there is one, and the notifications, each with its program and its text. Say when there are none. Say that Escape closes the notification center when it was opened for this.
