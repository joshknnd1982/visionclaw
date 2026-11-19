# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The real speech model hears requests that name things in the window in front, once told only VisionClaw's own names
and once also told the names of where the user is (voice.namesHere). Windows' own voices speak the requests into WAVE
files first (System.Speech, through PowerShell), so nothing is recorded from a microphone and no person is needed.

  python -u tests/live_voice_names.py SPEECHFOLDER [--second]

SPEECHFOLDER is where VisionClaw keeps its speech models: the folder "speech" of its data. The requests and what counts
as heard rightly were written on 2026-11-19, before anything was run on them. Two of them name nothing of the window,
to see that the names told do not make the model hear them where they were not said. Runs on the processor only.
"""
import os
import subprocess
import sys
import tempfile
import time

import harness
import live_voice
from visionClaw import voiceinput
from visionClaw.claw import voice

# (what is said, the program, the window's title, the focused control, controls of the window, names that must be heard)
CASES = (
	("Click the Arpeggiator button.", "Vital", "Vital", "", ["Arpeggiator", "Oscillator 1", "Filter 1"], ["Arpeggiator"]),
	("Turn on Quantize.", "REAPER", "song.rpp - REAPER v7.2", "", ["Quantize", "Grid", "Snap"], ["Quantize"]),
	("Press the Kontakt library button.", "Kontakt", "Kontakt 8", "", ["Library", "Browse"], ["Kontakt"]),
	("Open the Sidechain tab.", "FabFilter Pro-C 2", "FabFilter Pro-C 2", "", ["Sidechain", "Knee", "Ratio"], ["Sidechain"]),
	("Read the Thunderbird inbox.", "Thunderbird", "Inbox - Mozilla Thunderbird", "Inbox", [], ["Thunderbird"]),
	("Click the Nexus Mods button.", "Vortex", "Vortex", "", ["Nexus Mods", "Dashboard"], ["Nexus Mods"]),
	("Switch to Audacity.", "Audacity", "Audacity", "", [], ["Audacity"]),
	("Turn up the Ozone limiter.", "iZotope Ozone 11", "Ozone 11", "", ["Ozone", "Maximizer"], ["Ozone"]),
	("Click Wavetable in Vital.", "Vital", "Vital", "", ["Wavetable", "Sample"], ["Wavetable", "Vital"]),
	("Press the Bitwig play button.", "Bitwig Studio", "Bitwig Studio", "", ["Play", "Record"], ["Bitwig"]),
	("Open the foobar2000 equalizer.", "foobar2000", "Equalizer | foobar2000", "", ["Preamp"], ["foobar2000"]),
	("Click the Steam friends list.", "Steam", "Steam", "", ["Friends List", "Library"], ["Steam"]),
	# Named nowhere in what is said: the names told must not be heard instead.
	("Click the contact button.", "Kontakt", "Kontakt 8", "", ["Kontakt"], []),
	("Open the settings.", "iZotope Ozone 11", "Ozone 11", "", ["Ozone"], []),
)
# Written on 2026-11-19 after the first set was run and voice.fitted was made from its misses, before anything was run
# on these: the honest measure of both.
CASES2 = (
	("Open the SoundCloud upload page.", "Firefox", "Upload - SoundCloud - Mozilla Firefox", "", ["Upload"], ["SoundCloud"]),
	("Click the TeamTalk connect button.", "TeamTalk", "TeamTalk 5", "", ["Connect", "Channels"], ["TeamTalk"]),
	("Turn on AutoTune.", "Pro Tools", "Session - Pro Tools", "", ["AutoTune", "Bypass"], ["AutoTune"]),
	("Open the PowerPoint ribbon.", "PowerPoint", "Slides - PowerPoint", "", ["Ribbon"], ["PowerPoint"]),
	("Click the OneDrive icon.", "explorer", "Taskbar", "", ["OneDrive", "Volume"], ["OneDrive"]),
	("Press the Melodyne button.", "Cubase", "Cubase Pro Project", "", ["Melodyne", "Mixer"], ["Melodyne"]),
	("Switch to GoldWave.", "GoldWave", "GoldWave", "", [], ["GoldWave"]),
	("Click the Serato deck.", "Serato DJ Pro", "Serato DJ Pro", "", ["Deck 1", "Library"], ["Serato"]),
	("Read the Discord channel list.", "Discord", "general - Discord", "", ["Channels"], ["Discord"]),
	("Turn the Valhalla reverb up.", "Reaper", "ValhallaRoom", "", ["Valhalla", "Decay"], ["Valhalla"]),
	("Click the Zoom mute button.", "Zoom", "Zoom Meeting", "", ["Mute", "Participants"], ["Zoom"]),
	("Turn on auto play.", "Pro Tools", "Session - Pro Tools", "", ["AutoTune"], []),
	("Read the cloud status.", "Firefox", "SoundCloud - Mozilla Firefox", "", ["SoundCloud"], []),
)
VOICES = ("Microsoft David Desktop", "Microsoft Zira Desktop")
_SPEAK = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice($args[0])
$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s.SetOutputToWaveFile($args[1], $f)
$s.Speak($args[2])
$s.SetOutputToNull()
"""


def plain(text):
	return " ".join("".join(c if c.isalnum() else " " for c in str(text).lower()).split())


def speak(folder, voiceName, text, index):
	path = os.path.join(folder, f"{index:02d}-{voiceName.split()[1]}.wav")
	script = os.path.join(folder, "speak.ps1")
	with open(script, "w", encoding="utf-8") as f:
		f.write(_SPEAK)
	subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, voiceName, path, text],
		check=True, capture_output=True)
	return path


def rightly(heard, said, wanted):
	if wanted:
		return all(plain(name) in plain(heard) for name in wanted)
	return plain(heard) == plain(said)


def main():
	if len(sys.argv) < 2:
		sys.exit(__doc__)
	store = voice.Store(sys.argv[1])
	entry = store.chosen()
	if entry is None:
		sys.exit(f"No speech model is in {sys.argv[1]}.")
	ears = voiceinput.Ears(harness.ENGINE_DIR, store, lambda: "")
	folder = tempfile.mkdtemp(prefix="vcvoice-")
	print(f"Speech model: {entry['name']}, on the processor alone. Recordings in {folder}.")
	cases = CASES2 if "--second" in sys.argv else CASES
	scores = {"before": 0, "now": 0}
	total = 0
	for index, (said, program, title, focus, controls, wanted) in enumerate(cases):
		names = voice.namesHere(program, title, focus, controls)
		for voiceName in VOICES:
			pcm = live_voice.samples(speak(folder, voiceName, said, index))
			total += 1
			for label, told in (("before", ["Notepad"]), ("now", names)):
				started = time.monotonic()
				heard = ears.text(pcm, told)
				ok = rightly(heard, said, wanted)
				scores[label] += ok
				print(f"{label:6} {voiceName.split()[1]:5} {'right' if ok else 'WRONG'} {time.monotonic() - started:.1f} s "
					f"said {said!r} heard {heard!r}" + (f" told {names}" if label == "now" else ""), flush=True)
	print(f"Heard rightly: told only VisionClaw's names {scores['before']} of {total}; told the names of the window too "
		f"{scores['now']} of {total}.")


if __name__ == "__main__":
	main()
