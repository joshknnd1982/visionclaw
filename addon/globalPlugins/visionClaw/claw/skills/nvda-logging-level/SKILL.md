---
name: NVDA's logging level and a log for a bug report
description: For NVDA's logging level, turning NVDA's log on, and getting NVDA's log ready for a bug report, without VisionClaw changing anything.
when: logging level, log level, turn on logging, nvda logging, debug logging, bug report, log viewer
uses: nvda_log, do_command, explain_keys
log: errors, settings
---

Say NVDA's logging level as NVDA's settings name it, and that VisionClaw never changes it. NVDA+control+g opens NVDA's settings; the category Privacy and Security has the combo box Logging level. Info is enough for errors. A higher level makes NVDA ask first, as it may write what is typed and spoken: set it back to Info after. NVDA+f1 opens the log viewer; NVDA+control+shift+f1 pressed twice copies part of the log for a bug report.
