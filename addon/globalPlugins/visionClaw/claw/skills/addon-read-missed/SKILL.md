---
name: An add-on that reads what NVDA misses
description: How an add-on that reads one part of a window NVDA does not read keeps to that part.
when: nvda does not read, nvda doesn't read, nvda misses, not read by nvda, read the status, read the counter, read the score, read the timer, read that part
uses: write_addon, fix_addon
log: errors, objects, add-ons
---

Read only the one control or part of the window that was asked about, and nothing around it. When it cannot be found, say so in one sentence instead of reading something else. Say numbers, times and names exactly as shown, and leave out the kind of control unless it was asked for.
