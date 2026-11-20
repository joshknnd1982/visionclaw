---
name: Quick status: time, date and battery
description: Says the time, the date and how much battery is left, in one go.
when: quick status, status check, time date and battery, time and battery
uses: do_command
steps:
- do_command: what time is it
- do_command: what is the date today
- do_command: how much battery is left
log: errors, session
lands: moved
---

Say each one in a few words.
