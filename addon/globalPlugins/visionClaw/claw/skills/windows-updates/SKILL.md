---
name: Windows updates
description: For checking whether Windows has updates waiting or needs a restart, and installing them after a question.
when: windows update, windows updates, update windows, check for windows updates, install windows updates, restart to update, pending updates
uses: open_thing, describe, set_control, click, read_text, step_through, power
steps:
- open_thing: open windows update
- describe: Say what the Windows Update page says: whether updates are waiting, being installed or need a restart.
log: errors, session
lands: told
---

Say what the Windows Update page says: whether updates are waiting, being installed, or need a restart, and how long they may take where the page says it. Press its buttons only after the user says yes. A restart is always asked about first, and the user is told to save their work. Say that NVDA starts again after a restart where it is set to start after signing in.
