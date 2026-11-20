---
name: What NVDA's developer info says about an object
description: For the developer info NVDA writes to its log with NVDA+f1: one fact of the object, all of it in plain words, or what differs between the last two objects.
when: developer info, dev info, compare objects, objects i checked
uses: nvda_log
log: errors, objects
lands: stay
---

Say the facts of the developer info in the words of the result, one to a sentence, with the time it was written. Never read out handles, process numbers or what was typed into a protected field. When there is no developer info, say that NVDA+f1 on the object writes it and opens NVDA's log viewer, which Escape closes. Say that the automation ID and the window class are what tell a control apart when a fix or a name is made for it.
