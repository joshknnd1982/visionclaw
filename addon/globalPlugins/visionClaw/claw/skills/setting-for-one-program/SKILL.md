---
name: A setting for one program only
description: For changing an NVDA setting so that it applies only in the program in front, kept in an NVDA configuration profile, and for saying which programs have settings of their own.
when: only in this program, only in this app, just in this program, just in this app, only for this program, only here, configuration profile, configuration profiles, own settings, settings for this program
uses: change_setting, program_settings, remove_program_settings, undo_change
log: errors, settings
---

Say in which program the setting now applies, what it was and what it is, in the words of the result, and that other programs are as they were. NVDA keeps this in a configuration profile that it turns on by itself when that program is in front; NVDA+control+p opens NVDA's window for profiles. To put it back, the user says undo that while in that program. Never say a setting was changed for one program unless the result says so.
