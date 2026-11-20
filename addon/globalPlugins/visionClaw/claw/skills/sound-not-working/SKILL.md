---
name: No sound from the computer
description: For when the computer plays no sound or plays it on the wrong speakers or headphones: the volume, the output device, and NVDA's own audio.
when: no sound, can't hear anything, cannot hear anything, sound is not working, sound stopped working, wrong speakers, headphones not working, audio output, sound output, which speakers
uses: system_volume, open_thing, set_control, nvda_info, nvda_log, explain_keys
steps:
- system_volume: what is the computer volume
- open_thing: open sound settings
log: errors, audio
lands: told
---

First say the computer's volume and whether it is muted, then the device the sound goes to, from the Sound settings page. Turn the volume up or unmute only when the words ask for it, and never below the level speech needs. Say how to choose another output device on that page with the keyboard. Where only NVDA is silent, say that NVDA's own audio output device is a setting of NVDA, and where NVDA's log says a sound device failed, say so.
