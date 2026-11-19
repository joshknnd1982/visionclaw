# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Asking by voice (claw/voice.py, voiceinput.py): when a person has begun and finished speaking, from sound made
up by the test; a recording as a WAVE file; what is made of the speech model's answer; the speech models that
are offered and that nothing else can be; keeping them on the disk, with a stand-in for the download; a whole
spoken request with a stand-in for the microphone and for the engine; and where requests about it are sent.
Plain Python: no microphone is opened and no model is run. tests/live_voice.py does that.

  python tests/test_voice.py
"""
import array
import builtins
import importlib
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import threading
import types

import harness  # noqa: F401
from visionClaw.claw import catalog, offers, planner, router, voice

# --- Sound made up by the test ---


def sound(seconds, loudness, pitch=220.0):
	"""A tone of this loudness as 16-bit samples; loudness 0 is silence."""
	count = int(voice.RATE * seconds)
	samples = array.array("h", (
		int(loudness * 1.4142 * math.sin(2 * math.pi * pitch * index / voice.RATE)) for index in range(count)))
	return samples.tobytes()


def pieces(*parts):
	"""Sounds one after the other, cut into tenths of a second as the microphone gives them."""
	whole = b"".join(parts)
	return [whole[at:at + voice.CHUNK_BYTES] for at in range(0, len(whole), voice.CHUNK_BYTES)]


def hear(chunks, **options):
	listener = voice.Listener(**options)
	for number, chunk in enumerate(chunks):
		ended = listener.feed(chunk)
		if ended is not None:
			return listener, ended, number + 1
	return listener, None, len(chunks)


assert voice.CHUNK_BYTES == 3200 and voice.level(b"") == 0.0 and voice.level(sound(0.1, 0)) == 0.0
assert 990 < voice.level(sound(0.1, 1000)) < 1010, voice.level(sound(0.1, 1000))
# A quiet room, two seconds of speech, then quiet: listening ends a pause after the last word.
ROOM, VOICE = 40, 3000
listener, ended, used = hear(pieces(sound(0.5, ROOM), sound(2.0, VOICE), sound(4.0, ROOM)))
assert ended == voice.HEARD and listener.spoke(), ended
assert abs(used * voice.CHUNK_SECONDS - (0.5 + 2.0 + voice.PAUSE_SECONDS)) <= 0.2, used
# What is kept is the speech with a little before and after it, and none of the long quiet.
kept = len(listener.audio()) / (voice.RATE * voice.SAMPLE_BYTES)
assert 2.0 <= kept <= 2.0 + 2 * voice.MARGIN_SECONDS + 0.2, kept
# Nobody speaks: after a while listening ends, and nothing is kept.
listener, ended, used = hear(pieces(sound(20, ROOM)))
assert ended == voice.NOTHING and abs(used * voice.CHUNK_SECONDS - voice.START_SECONDS) <= 0.11 and listener.audio() == b""
# A pause in the middle of a sentence that is shorter than the pause that ends it: one request.
listener, ended, used = hear(pieces(sound(0.3, ROOM), sound(1.0, VOICE), sound(0.8, ROOM), sound(1.0, VOICE), sound(3.0, ROOM)))
assert ended == voice.HEARD and len(listener.audio()) / 32000 >= 2.8, len(listener.audio()) / 32000
# Someone who never stops: ended at the longest request, and what was said is kept.
listener, ended, used = hear(pieces(sound(60, VOICE)))
assert ended == voice.TOO_LONG and abs(used * voice.CHUNK_SECONDS - voice.MAX_SECONDS) <= 0.11
assert len(listener.audio()) / 32000 >= voice.MAX_SECONDS - 0.2
# A long sentence does not raise the bar until the speaker no longer counts: thirty seconds of speech are one.
listener, ended, used = hear(pieces(sound(0.5, ROOM), sound(30, VOICE), sound(3, ROOM)))
assert ended == voice.HEARD and len(listener.audio()) / 32000 >= 30, len(listener.audio()) / 32000
# A click or a key is too short to be speech.
listener, ended, used = hear(pieces(sound(1, ROOM), sound(0.1, 20000), sound(10, ROOM)))
assert ended == voice.NOTHING and not listener.spoke()
# A noisy room is not speech, and a voice over it is.
NOISY = 700
listener, ended, used = hear(pieces(sound(12, NOISY)))
assert ended == voice.NOTHING, ended
listener, ended, used = hear(pieces(sound(3, NOISY), sound(1.5, 6000), sound(4, NOISY)))
assert ended == voice.HEARD and listener.spoke()
# A quiet voice in a quiet room counts, and one that is already speaking when listening begins is not taken
# for the room.
listener, ended, used = hear(pieces(sound(0.5, 15), sound(1.5, 400), sound(3, 15)))
assert ended == voice.HEARD
listener, ended, used = hear(pieces(sound(2.0, VOICE), sound(3, ROOM)))
assert ended == voice.HEARD and listener.first == 0
# While it goes on, nothing is said to have ended.
assert hear(pieces(sound(0.5, ROOM), sound(1.0, VOICE)))[1] is None

# --- A recording as a WAVE file ---

pcm = sound(1.0, VOICE)
data = voice.wav(pcm)
assert data[:4] == b"RIFF" and data[8:16] == b"WAVEfmt " and data[36:40] == b"data" and data[44:] == pcm
size, kind, channels, rate, perSecond, align, bits = struct.unpack("<IHHIIHH", data[16:36])
assert (size, kind, channels, rate, perSecond, align, bits) == (16, 1, 1, 16000, 32000, 2, 16)
assert struct.unpack("<I", data[4:8])[0] == len(data) - 8 and struct.unpack("<I", data[40:44])[0] == len(pcm)

# --- What the model is told, and what is made of its answer ---

assert voice.heard("language English<asr_text>Make NVDA speak a little faster only in this program.") == (
	"Make NVDA speak a little faster only in this program.")
assert voice.heard("language Chinese<asr_text>你好。") == "你好。"
assert voice.heard("<asr_text>Open my downloads folder.") == "Open my downloads folder."
assert voice.heard("  Open   my downloads folder.  ") == "Open my downloads folder."
for nothing in ("", None, "language None<asr_text>", "language English<asr_text>", "<asr_text>", "language English<asr_text> . ", "<|endoftext|>"):
	assert voice.heard(nothing) == "", nothing
told = voice.context(["Notepad", "notepad", "Space Trader", ""])
assert "NVDA" in told and "VisionClaw" in told and "Space Trader" in told and told.count("otepad") == 1, told
assert len(voice.context([f"Program {number}" for number in range(40)])) < 400
assert voice.saidText("Open notepad.") == "You said: Open notepad. Press Enter to send it, or change it first."
assert voice.saidText("Open notepad") == "You said: Open notepad. Press Enter to send it, or change it first."
for sentence in (voice.NOTHING_HEARD, voice.NO_MICROPHONE, voice.NOT_UNDERSTOOD):
	assert not any(mark in sentence for mark in "*`_#"), sentence

# --- The speech models that are offered, and that nothing else can be ---

PINNED = re.compile(r"^https://huggingface\.co/ggml-org/Qwen3-ASR-[0-9.]+B-GGUF/resolve/[0-9a-f]{40}/[A-Za-z0-9._-]+\.gguf$")
assert [entry["id"] for entry in voice.MODELS] == ["qwen3-asr-0.6b", "qwen3-asr-1.7b"] and voice.SUGGESTED == "qwen3-asr-0.6b"
for entry in voice.MODELS:
	assert entry["licence"] == "Apache 2.0" and entry["source"].split("/")[0] == voice.PUBLISHER == "ggml-org"
	assert entry["madeFrom"].startswith("Qwen/Qwen3-ASR-") and "Qwen3-ASR" in entry["name"]
	assert [f["kind"] for f in entry["files"]] == ["model", "mmproj"]
	for f in entry["files"]:
		assert PINNED.match(f["url"]) and f["url"].endswith("/" + f["name"]), f["url"]
		assert f["url"].startswith(f"https://huggingface.co/{entry['source']}/resolve/")
		assert re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) and f["size"] > 100 * 2 ** 20
		assert entry["quant"] in f["name"]
assert voice.size(voice.MODELS[0]) == 804749248 + 214392480
assert voice.model("qwen3-asr-1.7b") is voice.MODELS[1] and voice.model("nothing") is None
assert "suggested" in voice.label(voice.MODELS[0]) and "suggested" not in voice.label(voice.MODELS[1])
assert voice.label(voice.MODELS[0]).startswith("Qwen3-ASR 0.6B, 972 MB to download"), voice.label(voice.MODELS[0])
# The speech models are no part of the catalog of vision and coder models: nothing about those changes, the list
# that is published stays as it was, and a list that is fetched can add neither a speech model nor ggml-org.
assert not any("asr" in entry["id"] for entry in catalog.CATALOG) and "ggml-org" not in catalog.PUBLISHERS
assert not any("asr" in str(entry.get("id")) for entry in catalog.publishedList()["models"])
fetched = dict(voice.MODELS[0], role="speech", files=[dict(f) for f in voice.MODELS[0]["files"]], maxContext=4096)
for attempt in (fetched, dict(fetched, role=catalog.VISION), dict(fetched, role=catalog.CODER, files=fetched["files"][:1])):
	try:
		catalog.checkEntry(attempt)
		raise AssertionError("a fetched list could add a speech model")
	except ValueError:
		pass
question = voice.downloadQuestion(voice.MODELS[0], voice.size(voice.MODELS[0]))
assert "972 MB" in question and "huggingface.co/ggml-org/Qwen3-ASR-0.6B-GGUF" in question and "Apache 2.0" in question
assert question.endswith("Download it now?") and "sent nowhere" in question

# --- Keeping them on the disk ---

folder = tempfile.mkdtemp()
try:
	store = voice.Store(os.path.join(folder, "speech"))
	small, large = voice.MODELS
	assert store.chosen() is None and store.wanted() is small and store.wanted("qwen3-asr-1.7b") is large and store.stored() == []
	assert store.missingBytes(small) == voice.size(small)
	text = store.text()
	assert text.startswith("Asking by voice is not set up yet") and "asks before it downloads Qwen3-ASR 0.6B, 972 MB" in text, text
	# The download is stood in for: each file is made with the size it must have. The real one checks the SHA-256.
	asked, progress = [], []

	def fakeDownload(url, dest, size=None, sha256=None, onProgress=None, cancel=None):
		asked.append((url, size, sha256))
		with open(dest, "wb") as f:
			f.truncate(size)
		if os.path.exists(dest + ".part"):
			os.remove(dest + ".part")  # the real download makes the file out of its unfinished part
		if onProgress:
			onProgress(size, size)

	realDownload = voice.net.download
	voice.net.download = fakeDownload
	store.download(small, lambda done, total: progress.append((done, total)))
	assert [url for url, _size, _sha in asked] == [f["url"] for f in small["files"]]
	assert all(sha == f["sha256"] and size == f["size"] for (_url, size, sha), f in zip(asked, small["files"]))
	assert progress[-1] == (voice.size(small), voice.size(small)) and store.installed(small) and store.missingBytes(small) == 0
	assert store.chosen() is small and store.chosen("qwen3-asr-1.7b") is small  # the one that is here is used
	model, audio = store.paths(small)
	assert model.endswith("Qwen3-ASR-0.6B-Q8_0.gguf") and audio.endswith("mmproj-Qwen3-ASR-0.6B-Q8_0.gguf")
	assert os.path.dirname(model) == os.path.join(folder, "speech", "qwen3-asr-0.6b")
	# What is here already is not downloaded again.
	del asked[:]
	store.download(small)
	assert asked == []
	text = store.text()
	assert text.startswith("Asking by voice is ready. VisionClaw listens with the speech model Qwen3-ASR 0.6B") and "972 MB" in text
	assert "sent nowhere" in text and "NVDA+Alt+V" in text
	# An unfinished download of the other one is said to be one.
	os.makedirs(os.path.join(folder, "speech", large["dir"]))
	with open(os.path.join(folder, "speech", large["dir"], large["files"][0]["name"] + ".part"), "wb") as f:
		f.truncate(300 * 2 ** 20)
	assert not store.installed(large) and store.missingBytes(large) == voice.size(large) - 300 * 2 ** 20
	assert "A download of Qwen3-ASR 1.7B was not finished: 300 MB of 2.3 GB are here." in store.text(), store.text()
	# Both chosen: the user's choice is used once it is here.
	store.download(large)
	assert store.chosen("qwen3-asr-1.7b") is large and store.chosen("") is small
	freed = store.remove(small) + store.remove(large)
	assert freed == voice.size(small) + voice.size(large) and store.stored() == [] and store.chosen() is None
	assert not os.path.exists(os.path.join(folder, "speech", small["dir"]))
	voice.net.download = realDownload
finally:
	shutil.rmtree(folder, ignore_errors=True)

# --- A whole spoken request, with a stand-in for the microphone and for the engine ---

logged = []
logHandler = types.ModuleType("logHandler")
logHandler.log = types.SimpleNamespace(
	debug=lambda *a, **k: None, debugWarning=lambda *a, **k: None, info=lambda *a, **k: None,
	warning=lambda *a, **k: None, error=lambda *a, **k: logged.append(a[0]))
sys.modules["logHandler"] = logHandler
builtins._ = lambda text: text
voiceinput = importlib.import_module("visionClaw.voiceinput")
# Windows' structures, as Microsoft's pages give them: their sizes on this computer's Python.
import ctypes  # noqa: E402
pointer = ctypes.sizeof(ctypes.c_void_p)
assert ctypes.sizeof(voiceinput.WAVEFORMATEX) == 18
assert ctypes.sizeof(voiceinput.WAVEHDR) == (48 if pointer == 8 else 32), ctypes.sizeof(voiceinput.WAVEHDR)
assert voiceinput.WAVEHDR.dwFlags.offset == (24 if pointer == 8 else 16)
assert voiceinput.WAVE_MAPPER == 0xFFFFFFFF and voiceinput.WHDR_DONE == 1


class FakeEars:
	def __init__(self, answer):
		self.answer, self.got = answer, []

	def text(self, pcm, names=(), cancel=None):
		self.got.append((len(pcm), tuple(names)))
		if isinstance(self.answer, Exception):
			raise self.answer
		return voice.heard(self.answer)


def microphone(*parts):
	return lambda stop: iter(pieces(*parts))


states = []
ears = FakeEars("language English<asr_text>Open my downloads folder.")
text, problem = voiceinput.listen(
	ears, threading.Event(), states.append, ["Notepad"], microphone(sound(0.4, ROOM), sound(1.5, VOICE), sound(3, ROOM)))
assert (text, problem) == ("Open my downloads folder.", ""), (text, problem)
assert states == ["listening", "speaking", "thinking"], states
assert ears.got[0][1] == ("Notepad",) and 1.5 <= ears.got[0][0] / 32000 <= 2.6, ears.got
# Nobody speaks: the model is never asked.
ears, states = FakeEars("x"), []
text, problem = voiceinput.listen(ears, threading.Event(), states.append, (), microphone(sound(12, ROOM)))
assert (text, problem) == ("", voice.NOTHING_HEARD) and ears.got == [] and states == ["listening"]
# The user stops listening before saying anything: nothing is said about it.
stop = threading.Event()
stop.set()
text, problem = voiceinput.listen(FakeEars("x"), stop, lambda state: None, (), lambda stop: iter(()))
assert (text, problem) == ("", "")
# The user stops while speaking: what was said so far is used.


def cutOff(stop):
	for number, chunk in enumerate(pieces(sound(0.3, ROOM), sound(5, VOICE))):
		if number == 12:
			return
		yield chunk


ears = FakeEars("language English<asr_text>Turn the volume")
text, problem = voiceinput.listen(ears, threading.Event(), lambda state: None, (), cutOff)
assert text == "Turn the volume" and ears.got, (text, problem)
# The model makes no words of it, the microphone is missing, and the engine fails: each is said plainly.
text, problem = voiceinput.listen(
	FakeEars("language None<asr_text>"), threading.Event(), lambda state: None, (), microphone(sound(1, VOICE), sound(3, ROOM)))
assert (text, problem) == ("", voice.NOT_UNDERSTOOD)


def noMicrophone(stop):
	raise voiceinput.NoMicrophone("waveInOpen answered 2")
	yield b""


text, problem = voiceinput.listen(FakeEars("x"), threading.Event(), lambda state: None, (), noMicrophone)
assert (text, problem) == ("", voice.NO_MICROPHONE)
text, problem = voiceinput.listen(
	FakeEars(voiceinput.EngineError("it stopped")), threading.Event(), lambda state: None, (), microphone(sound(1, VOICE), sound(3, ROOM)))
assert text == "" and problem == "The speech model could not be used: it stopped", problem
# With no speech model on the computer, the engine is never started.
empty = tempfile.mkdtemp()
try:
	try:
		voiceinput.Ears(harness.ENGINE_DIR, voice.Store(empty), lambda: "").text(sound(1, VOICE))
		raise AssertionError("listening went on without a speech model")
	except voiceinput.EngineError as e:
		assert "No speech model" in str(e)
finally:
	shutil.rmtree(empty, ignore_errors=True)

# --- Where requests about it are sent ---

HINTS = {
	"can I ask you by voice": "voice_info", "Can I just speak my requests instead of typing?": "voice_info",
	"how do I talk to VisionClaw with my voice": "voice_info", "is voice input set up": "voice_info",
	"which speech model do you use": "voice_info", "does dictation work here": "voice_info",
	"download the speech model": "get_voice", "set up asking by voice": "get_voice", "get the speech recognition model": "get_voice",
	"delete the speech model": "remove_voice", "remove the speech recognition model from this computer": "remove_voice",
	# NVDA's own voice is a setting, and which voices there are is asked of NVDA.
	"change the voice": "change_setting", "make the voice slower": "change_setting", "which voices do I have": "nvda_info",
	"turn the voice volume down": "change_setting", "which models are installed": "visionclaw_models",
	"what can you download for me": "downloads_info",
}
for said, recipe in HINTS.items():
	assert planner.hint(said) == recipe, (said, planner.hint(said))


class _Registry:
	def has(self, names):
		return True

	def get(self, name):
		return object()


for said, recipe in HINTS.items():
	assert recipe in planner.offered(said, _Registry(), {router.WEB: False}), (said, recipe)
for said in ("what is on my screen", "open notepad", "set punctuation to all"):
	offered = planner.offered(said, _Registry(), {})
	assert not {"voice_info", "get_voice", "remove_voice"} & set(offered), (said, offered)
# The overview of what can be downloaded names the speech model, and the words it tells the user to say get it.
for here in (False, True):
	overview = offers.overview({"speech": here})
	assert f"Say: {offers.ASK_VOICE}." in overview and ("NVDA+Alt+V" in overview) is here, overview
assert planner.hint(offers.ASK_VOICE) == "get_voice"
assert {"voice_info", "get_voice", "remove_voice"} <= offers.ABOUT_DOWNLOADS

print("OK")
