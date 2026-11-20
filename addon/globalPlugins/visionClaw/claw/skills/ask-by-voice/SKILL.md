---
name: Ask by voice
description: For questions about speaking a request to VisionClaw instead of typing it, and about the speech model that listens.
when: by voice, with my voice, voice input, speech model, dictate, dictation, microphone, speech recognition, speak my requests
uses: voice_info, get_voice, remove_voice
log: errors, audio
---

Say whether asking by voice is ready, in the words of the result. NVDA+alt+v opens the Ask VisionClaw window and listens at once; alt+v listens in that window. The user speaks after the high beep, listening ends when they stop speaking, and what was heard is put into the box and read out before anything is done, so a wrong word can be corrected. The words are worked out on this computer and sent nowhere.
