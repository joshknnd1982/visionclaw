---
name: Speech or braille trouble in NVDA's log
description: For a voice that changed by itself, a synthesizer that failed or a braille display that disconnected: what NVDA wrote about it, in the order it happened.
when: voice changed, voice change, synthesizer failed, synth failed, synthesizer error, braille display disconnected, braille display failed
uses: nvda_log, nvda_info
log: speech, audio, braille, errors
lands: stay
---

Tell what happened in order, with its time: which synthesizer or braille display NVDA tried, that it failed and the reason NVDA wrote, and which one NVDA went back to. Say which ones NVDA loaded last. NVDA+control+s opens the synthesizer selection, and NVDA+control+a the braille display selection. Never switch a driver unless the user asks; guess no cause the log does not give.
