---
name: An add-on causing trouble in NVDA
description: For an add-on that causes errors, freezes or crashes in NVDA: which one NVDA's log points to, and how to test it without VisionClaw changing anything.
when: add-on causing, addon causing, add-on breaking, addon breaking, add-on crashing, addon crashing, add-on freezing, add-on errors, addon errors
uses: nvda_log, addon_question, nvda_info
log: errors, add-ons, freezes, session
---

Name the add-on NVDA's log points to, with how many errors or freezes, and say that this is what the log shows, not proof. To test it, the user turns that add-on off in the Add-on Store, which NVDA+n, then t, then a opens, and restarts NVDA; or chooses restart with add-ons disabled and debug logging enabled in the dialog NVDA+q opens. Say that VisionClaw never turns an add-on off itself.
