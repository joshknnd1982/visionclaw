---
name: Write an add-on a blind person can use
description: How an NVDA add-on that VisionClaw writes or corrects must behave for someone who listens to speech or reads braille.
when: write an add-on, make an add-on, create an add-on, an add-on that, add-on which, fix the add-on, every time, whenever, speak when, beep when
uses: write_addon, fix_addon
---

The user hears the add-on and cannot see the screen. Say what it does with ui.message in one short plain sentence; a beep alone is not enough unless a beep is what was asked for. Give every script a description that says what it does, because NVDA names the key by it in the Input gestures dialog. Use only a key that was asked for. Never move the mouse, the focus or the navigator object, and never stop speech or braille, unless that is what was asked.
