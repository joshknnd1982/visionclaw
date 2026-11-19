# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The real speech model in the bundled engine, through VisionClaw's own code (voiceinput.Ears), on recordings
that are files; and, only when asked for, the real microphone.

  python tests/live_voice.py FOLDER one.wav two.wav ...
  python tests/live_voice.py FOLDER --mic

FOLDER is where VisionClaw keeps its speech models: the folder "speech" of its data, with "qwen3-asr-0.6b" in it.
Each recording must be a WAVE file with one channel of 16-bit samples at 16 kHz; what the model hears is printed
with the time it took. A file named like "what was said.wav" is compared with its name.

--mic opens the default microphone for three seconds through voiceinput.chunks, the code VisionClaw listens
with, and prints how loud each tenth of a second was. It never prints, keeps or turns into text what was said:
it only shows that Windows gives VisionClaw sound. Do not run it for the owner without asking.
"""
import builtins
import os
import struct
import sys
import threading
import time
import types

import harness

logHandler = types.ModuleType("logHandler")
logHandler.log = types.SimpleNamespace(**{name: (lambda *a, **k: None) for name in ("debug", "debugWarning", "info", "warning", "error")})
sys.modules["logHandler"] = logHandler
builtins._ = lambda text: text
from visionClaw import voiceinput  # noqa: E402
from visionClaw.claw import voice  # noqa: E402


def samples(path):
	"""The samples of a WAVE file, which must be one channel of 16 bits at 16 kHz."""
	with open(path, "rb") as f:
		data = f.read()
	assert data[:4] == b"RIFF" and data[8:12] == b"WAVE", "not a WAVE file"
	at = 12
	form = None
	while at + 8 <= len(data):
		name, size = data[at:at + 4], struct.unpack("<I", data[at + 4:at + 8])[0]
		if name == b"fmt ":
			form = struct.unpack("<HHIIHH", data[at + 8:at + 24])
		elif name == b"data":
			assert form is not None and form[:3] == (1, 1, voice.RATE) and form[5] == 16, f"not 16 kHz, one channel, 16 bits: {form}"
			return data[at + 8:at + 8 + size]
		at += 8 + size + (size & 1)
	raise AssertionError("no sound in the file")


def main():
	arguments = sys.argv[1:]
	if not arguments:
		sys.exit(__doc__)
	folder = arguments[0]
	if "--mic" in arguments:
		print(f"Windows has {voiceinput.microphones()} microphones. Listening for three seconds; only loudness is shown.")
		stop = threading.Event()
		levels = []
		started = time.monotonic()
		for chunk in voiceinput.chunks(stop, seconds=10):
			levels.append(round(voice.level(chunk)))
			if time.monotonic() - started >= 3:
				stop.set()
		print(f"{len(levels)} pieces of a tenth of a second each. Loudness: {levels}")
		return
	store = voice.Store(folder)
	entry = store.chosen()
	if entry is None:
		sys.exit(f"No speech model is in {folder}.")
	ears = voiceinput.Ears(harness.ENGINE_DIR, store, lambda: "")
	print(f"Speech model: {entry['name']}, {voice.sizeText(store.bytesOnDisk(entry))}, on the processor alone.")
	right = total = 0
	for path in arguments[1:]:
		pcm = samples(path)
		started = time.monotonic()
		heard = ears.text(pcm, ["Notepad"])
		took = time.monotonic() - started
		wanted = os.path.splitext(os.path.basename(path))[0]
		plain = lambda text: " ".join("".join(c if c.isalnum() else " " for c in text.lower()).split())  # noqa: E731
		same = plain(heard) == plain(wanted)
		total += 1
		right += same
		print(f"{len(pcm) / 32000:.1f} s of sound, {took:.1f} s from start to text ({'as said' if same else 'DIFFERENT'}): {heard!r}")
	if total:
		print(f"{right} of {total} recordings were heard as their file names say.")


if __name__ == "__main__":
	main()
