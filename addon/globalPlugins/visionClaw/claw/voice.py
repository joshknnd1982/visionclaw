# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - asking by voice, with a speech model that runs on this computer. Nothing that is said leaves it:
# the microphone is recorded into memory, turned into text by the bundled engine, and thrown away.
# Here is everything that needs no NVDA and no microphone:
#   - the speech models that are offered, where their files are from, and keeping them on the disk;
#   - when a person has begun to speak and when they have finished, from how loud each tenth of a second is;
#   - a recording as a WAVE file in memory, which is what the engine takes;
#   - what the model is told before it listens, and what is made of its answer.
# The recording itself and the engine are in voiceinput.py. No NVDA dependencies.
#
# The model is Qwen3-ASR, by the Qwen team, under the Apache 2.0 licence (read from Hugging Face's listing on
# 2026-11-18). Neither the Qwen team nor Unsloth publishes it in the engine's own format; ggml-org, the page of
# the llama.cpp project, whose engine VisionClaw uses, does. The owner said yes to ggml-org for the speech model on
# 2026-11-18, and was told that it comes only as Q8_0: there is no Q4_K_M and no Q6_K of it. It is offered from
# nowhere else, a list that is fetched can never add a speech model (catalog.checkEntry knows no such role), and
# every file is pinned to one revision with its size and SHA-256, which the download checks.

import array
import math
import os
import re
import struct

from .. import net

PUBLISHER = "ggml-org"
LICENCE = "Apache 2.0"
_HF = "https://huggingface.co/{repo}/resolve/{rev}/{name}"


def _file(repo, rev, name, size, sha256, kind="model"):
	return {"kind": kind, "name": name, "size": size, "sha256": sha256, "url": _HF.format(repo=repo, rev=rev, name=name)}


_SMALL = ("ggml-org/Qwen3-ASR-0.6B-GGUF", "928ab958557df9aa2ef1c93e0e83c7ad0933fae2")
_LARGE = ("ggml-org/Qwen3-ASR-1.7B-GGUF", "36a678687ba7d07a74ca70ccb0e36902e005fb80")
# Revisions, sizes and SHA-256 read from https://huggingface.co/api/models/<repo>?blobs=true on 2026-11-18.
# The smaller one is suggested: on the owner's computer it was ready in about a second and turned a sentence
# into text in half a second, on the processor alone. The user chooses either.
MODELS = (
	{
		"id": "qwen3-asr-0.6b", "dir": "qwen3-asr-0.6b", "name": "Qwen3-ASR 0.6B", "quant": "Q8_0", "memoryGb": 1.3,
		"licence": LICENCE, "source": _SMALL[0], "madeFrom": "Qwen/Qwen3-ASR-0.6B",
		"files": (
			_file(*_SMALL, "Qwen3-ASR-0.6B-Q8_0.gguf", 804749248,
				"bca259818b50ca7c4c05e9bdb35a5dc04fa039653a6d6f3f0f331f96f6aa1971"),
			_file(*_SMALL, "mmproj-Qwen3-ASR-0.6B-Q8_0.gguf", 214392480,
				"41a342b5e4c514e968cb756de6cd1b7be39eff43c44c57a2ef5fc6522e36603d", "mmproj"),
		),
	},
	{
		"id": "qwen3-asr-1.7b", "dir": "qwen3-asr-1.7b", "name": "Qwen3-ASR 1.7B", "quant": "Q8_0", "memoryGb": 3.0,
		"licence": LICENCE, "source": _LARGE[0], "madeFrom": "Qwen/Qwen3-ASR-1.7B",
		"files": (
			_file(*_LARGE, "Qwen3-ASR-1.7B-Q8_0.gguf", 2165034944,
				"58e22d0532d4eacaf034cfac17a6fed159f37c41390c710186783be439d1fc57"),
			_file(*_LARGE, "mmproj-Qwen3-ASR-1.7B-Q8_0.gguf", 355709344,
				"46c1d533af3f354ceb37ce855dbceff7da7fa7cf1e6a523df3b13440bd164c0d", "mmproj"),
		),
	},
)
SUGGESTED = MODELS[0]["id"]


def model(modelId):
	return next((entry for entry in MODELS if entry["id"] == modelId), None)


def size(entry):
	return sum(f["size"] for f in entry["files"])


def sizeText(count):
	return f"{count / 2 ** 30:.1f} GB" if count >= 2 ** 30 else f"{round(count / 2 ** 20)} MB"


def label(entry):
	"""A speech model as the user chooses it: its name, its size, and which one is suggested."""
	text = f"{entry['name']}, {sizeText(size(entry))} to download"
	if entry["id"] == SUGGESTED:
		text += ", suggested: fast, and enough for requests"
	else:
		text += ", larger and slower, for when the smaller one mishears you"
	return text


class Store:
	"""The speech models on this computer, in a folder of their own inside VisionClaw's data."""

	def __init__(self, folder):
		self.folder = folder

	def _path(self, entry, f):
		return os.path.join(self.folder, entry["dir"], f["name"])

	def _has(self, entry, f):
		try:
			return os.path.getsize(self._path(entry, f)) == f["size"]
		except OSError:
			return False

	def installed(self, entry):
		return all(self._has(entry, f) for f in entry["files"])

	def chosen(self, preferredId=""):
		"""The model to listen with: the user's choice if it is on this computer, else one that is; None if none."""
		here = [entry for entry in MODELS if self.installed(entry)]
		for entry in here:
			if entry["id"] == preferredId:
				return entry
		return here[0] if here else None

	def wanted(self, preferredId=""):
		"""The model to offer for download: the user's choice, else the suggested one."""
		return model(preferredId) or model(SUGGESTED)

	def paths(self, entry):
		"""(the model's file, its audio part's file)."""
		found = {f["kind"]: self._path(entry, f) for f in entry["files"]}
		return found["model"], found["mmproj"]

	def missingBytes(self, entry):
		left = 0
		for f in entry["files"]:
			if self._has(entry, f):
				continue
			try:
				left += max(0, f["size"] - os.path.getsize(self._path(entry, f) + ".part"))
			except OSError:
				left += f["size"]
		return left

	def download(self, entry, onProgress=None, cancel=None):
		"""Download what is missing of a speech model. Calls onProgress(doneBytes, totalBytes). Only ever called
		after the user said yes. Raises net.Cancelled, OSError, or ValueError if a file arrives damaged."""
		os.makedirs(os.path.join(self.folder, entry["dir"]), exist_ok=True)
		total, before = size(entry), 0
		for f in entry["files"]:
			if not self._has(entry, f):
				def progress(done, _total, before=before):
					if onProgress is not None:
						onProgress(before + done, total)
				net.download(f["url"], self._path(entry, f), f["size"], f["sha256"], progress, cancel)
			before += f["size"]
			if onProgress is not None:
				onProgress(before, total)

	def bytesOnDisk(self, entry):
		found = 0
		for f in entry["files"]:
			for path in (self._path(entry, f), self._path(entry, f) + ".part"):
				try:
					found += os.path.getsize(path)
				except OSError:
					pass
		return found

	def remove(self, entry):
		"""Delete a speech model from the disk. Returns the bytes freed."""
		freed = 0
		for f in entry["files"]:
			for path in (self._path(entry, f), self._path(entry, f) + ".part"):
				try:
					got = os.path.getsize(path)
				except OSError:
					continue
				os.remove(path)
				freed += got
		try:
			os.rmdir(os.path.join(self.folder, entry["dir"]))
		except OSError:
			pass
		return freed

	def stored(self):
		"""[(entry, bytes on the disk, whether it is complete)] of every speech model that has files here."""
		return [(entry, self.bytesOnDisk(entry), self.installed(entry)) for entry in MODELS if self.bytesOnDisk(entry)]

	def text(self, preferredId=""):
		"""Whether asking by voice is ready, in sentences, read from the disk by plain code."""
		lines = []
		use = self.chosen(preferredId)
		if use is None:
			offer = self.wanted(preferredId)
			lines.append(
				"Asking by voice is not set up yet: no speech model is on this computer. To get one, press the button "
				f"Speak your request in the Ask VisionClaw window, or NVDA+Alt+V; VisionClaw then asks before it downloads "
				f"{offer['name']}, {sizeText(size(offer))}, from Hugging Face.")
		else:
			lines.append(
				f"Asking by voice is ready. VisionClaw listens with the speech model {use['name']}, which runs on this "
				"computer's processor. What you say is not kept and is sent nowhere.")
		for entry, got, whole in self.stored():
			lines.append(
				f"{entry['name']} is on this computer, {sizeText(got)}." if whole
				else f"A download of {entry['name']} was not finished: {sizeText(got)} of {sizeText(size(entry))} are here.")
		lines.append(
			"To ask by voice, press NVDA+Alt+V, or the button Speak your request in the Ask VisionClaw window. Speak after "
			"the high beep; VisionClaw stops listening when you stop speaking, puts what it heard into the box, and reads "
			"it to you before anything is done.")
		return " ".join(lines)


def downloadQuestion(entry, left):
	"""What the user is asked before a speech model is downloaded."""
	return (
		f"Asking by voice needs a speech model on this computer. VisionClaw can download {entry['name']} by the Qwen "
		f"team, {sizeText(left)}, from Hugging Face, where the llama.cpp project publishes it in the engine's format "
		f"(huggingface.co/{entry['source']}). It is free, under the {entry['licence']} licence. After that, what you "
		"say is turned into text on this computer and is sent nowhere. Download it now?")


# --- A recording ---

RATE = 16000  # samples a second, one channel, 16 bits each: what the speech model takes
SAMPLE_BYTES = 2
CHUNK_SECONDS = 0.1
CHUNK_BYTES = int(RATE * CHUNK_SECONDS) * SAMPLE_BYTES
# Why listening ended.
HEARD, NOTHING, TOO_LONG, STOPPED = "heard", "nothing", "too long", "stopped"
# How long VisionClaw waits for the first word, how long a pause ends the request, and the longest request.
START_SECONDS = 8.0
PAUSE_SECONDS = 1.5
MAX_SECONDS = 45.0
# A sound counts as speech when it is this many times louder than the room, and never below LEAST.
TIMES_LOUDER = 3.0
LEAST = 260.0
# Speech must last this long to count: a click or a key is shorter.
SPEECH_SECONDS = 0.2
# What is kept before the first word and after the last, so that no word is cut.
MARGIN_SECONDS = 0.4


def level(chunk):
	"""How loud a piece of a recording is: the root of the mean of its samples' squares; 0 for none."""
	usable = len(chunk) - len(chunk) % SAMPLE_BYTES
	if usable <= 0:
		return 0.0
	samples = array.array("h")
	samples.frombytes(bytes(chunk[:usable]))
	return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


class Listener:
	"""Follows a recording a tenth of a second at a time and says when the person has finished. feed(chunk)
	gives None while listening goes on, and then why it ended: HEARD (they spoke and then paused), NOTHING (they
	never began) or TOO_LONG. How loud the room is, is learned from the quietest pieces heard so far, so a noisy
	room does not count as speech and a quiet voice does."""

	def __init__(self, start=START_SECONDS, pause=PAUSE_SECONDS, longest=MAX_SECONDS):
		self._start, self._pause, self._longest = start, pause, longest
		self._chunks = []
		self._levels = []
		self._floor = None
		self._run = 0
		self.first = None  # the piece in which speech began
		self.last = None  # the last piece with speech in it

	def seconds(self):
		return len(self._chunks) * CHUNK_SECONDS

	def spoke(self):
		return self.first is not None

	def feed(self, chunk):
		loud = level(chunk)
		at = len(self._chunks)
		self._chunks.append(bytes(chunk))
		self._levels.append(loud)
		# The room: the quietest piece so far. A person who is already speaking when listening begins must not be
		# taken for the room, so the first piece counts for no more than a quiet room does.
		if self._floor is None:
			self._floor = min(loud, LEAST)
		elif loud < self._floor:
			self._floor = loud
		speech = loud >= max(LEAST, self._floor * TIMES_LOUDER)
		if not speech:
			# A room that got louder is followed slowly, and only by what is not speech: a long sentence must
			# not raise the bar until the speaker no longer counts.
			self._floor = min(loud, self._floor * 1.02 + 0.5)
		if speech:
			self._run += 1
			if self._run * CHUNK_SECONDS >= SPEECH_SECONDS:
				if self.first is None:
					self.first = at - self._run + 1
				self.last = at
		else:
			self._run = 0
		now = self.seconds()
		if self.first is None:
			return NOTHING if now >= self._start else None
		if (at - self.last) * CHUNK_SECONDS >= self._pause:
			return HEARD
		if now >= self._longest:
			return TOO_LONG
		return None

	def audio(self):
		"""What was said, with a little before the first word and after the last; b"" when nothing was."""
		if self.first is None:
			return b""
		margin = int(round(MARGIN_SECONDS / CHUNK_SECONDS))
		return b"".join(self._chunks[max(0, self.first - margin):self.last + 1 + margin])


def wav(pcm, rate=RATE):
	"""A recording as a WAVE file in memory: one channel, 16 bits."""
	pcm = bytes(pcm)
	return b"".join((
		b"RIFF", struct.pack("<I", 36 + len(pcm)), b"WAVE", b"fmt ",
		struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * SAMPLE_BYTES, SAMPLE_BYTES, 8 * SAMPLE_BYTES),
		b"data", struct.pack("<I", len(pcm)), pcm))


# --- What the model is told, and what is made of its answer ---

# Names the model would otherwise write as words it knows better: it heard "NVDA" as "Nvidia". Told before it
# listens, they are written right. Measured with Qwen3-ASR 0.6B on 2026-11-18.
NAMES = ("NVDA", "VisionClaw", "braille", "Notepad", "Recycle Bin")
MAX_NAMES = 12
TOKENS = 220


# Words that are no names worth telling: the speech model knows them already.
_EVERYDAY = frozenset((
	"ok", "cancel", "yes", "no", "close", "open", "save", "file", "edit", "view", "help", "new", "next", "back", "button",
	"menu", "window", "tab", "home", "search", "settings", "options", "tools", "more", "minimize", "maximize", "restore",
	"apply", "exit", "start", "stop", "play", "pause", "the", "and", "of", "to", "a", "an", "in", "on", "for", "untitled"))
# How many names of the window in front go to the model besides NAMES. The owner's words and the program come first.
MAX_HERE = MAX_NAMES - len(NAMES)


def _worthTelling(name):
	"""Whether a name of the window in front is worth telling the speech model: short, with a letter, and not made of
	words it knows anyway."""
	name = " ".join(str(name or "").split())
	if not name or len(name) > 30 or len(name.split()) > 3 or not re.search(r"[A-Za-z]", name):
		return False
	return any(word not in _EVERYDAY for word in re.findall(r"[a-z0-9+#]+", name.lower()))


def namesHere(program="", title="", focus="", controls=(), taught=()):
	"""The names the user may say about where they are, for the speech model to hear right, the likeliest first: the
	program, the words the user taught VisionClaw, the focused control, the parts of the window's title, and the names
	of the window's controls. At most MAX_HERE, each once. Plain code; nothing of it is kept."""
	found = []
	titleParts = [part.strip() for part in re.split(r"\s+[-|:\u2013\u2014]\s+", str(title or "")) if part.strip()]
	for name in [program] + list(taught or ()) + [focus] + titleParts + list(controls or ()):
		name = " ".join(str(name or "").split())
		if _worthTelling(name) and name.lower() not in (known.lower() for known in found + list(NAMES)):
			found.append(name)
		if len(found) >= MAX_HERE:
			break
	return found


def context(names=()):
	"""What the speech model is told before it listens: the names that may be said. names: more of them, such as
	the program in front."""
	every = []
	for name in tuple(NAMES) + tuple(names):
		name = " ".join(str(name or "").split())[:40]
		if name and name.lower() not in (known.lower() for known in every):
			every.append(name)
	return (
		"The user speaks a request to VisionClaw, an assistant in the NVDA screen reader. Names that may be said: "
		+ ", ".join(every[:MAX_NAMES]) + ".")


_TAG = re.compile(r"<[^<>]{1,40}>")
_HEAD = re.compile(r"^\s*language\s+[A-Za-z]{2,24}(?:\s+[A-Za-z]{2,24})?\s*<asr_text>", re.IGNORECASE)
_NO_SPEECH = re.compile(r"^\s*language\s+none\b", re.IGNORECASE)


def _joined(text):
	return re.sub(r"[^a-z0-9]+", "", text.lower())


def fitted(text, names):
	"""What was heard, with a name it was told written as the name is written where it heard the same letters split
	otherwise: "wave table" is Wavetable and "foobar 2000" is foobar2000 when those names were told. Only where the
	letters and digits are the very same; a word that only sounds like a name is left as it was heard."""
	words = str(text or "").split()
	for name in sorted({" ".join(str(n or "").split()) for n in names or ()}, key=len, reverse=True):
		target = _joined(name)
		if len(target) < 4 or " " in name:
			continue
		at = 0
		while at < len(words):
			for size in (3, 2):
				piece = words[at:at + size]
				if len(piece) == size and _joined(" ".join(piece)) == target:
					tail = re.search(r"[^A-Za-z0-9]*$", piece[-1]).group(0)
					head = re.match(r"^[^A-Za-z0-9]*", piece[0]).group(0)
					words[at:at + size] = [head + name + tail]
					break
			at += 1
	return " ".join(words)


def heard(answer, names=()):
	"""The words of the model's answer, without the marks it puts around them; "" when it heard no speech.
	The model answers as: language English<asr_text>Make NVDA speak faster. names: what it was told; a name it heard
	split into words is joined again (fitted)."""
	text = str(answer or "")
	if _NO_SPEECH.match(text):
		return ""
	text = _HEAD.sub("", text, count=1)
	if "<asr_text>" in text:
		text = text.split("<asr_text>", 1)[1]
	text = " ".join(_TAG.sub(" ", text).split())
	# A recording of a room with nobody speaking comes back as a mark or a lone word of noise.
	return fitted(text, tuple(NAMES) + tuple(names or ())) if re.search(r"[A-Za-z0-9À-￿]{2,}", text) else ""


def saidText(text):
	"""What the user is told once their words are in the box."""
	return f"You said: {text} Press Enter to send it, or change it first." if text[-1:] in ".!?" else (
		f"You said: {text}. Press Enter to send it, or change it first.")


NOTHING_HEARD = "Nothing was heard. Press the button again and speak after the high beep."
NO_MICROPHONE = (
	"Windows gave VisionClaw no microphone. Check that one is plugged in and chosen in Windows Settings, System, "
	"Sound, and that Settings, Privacy and security, Microphone lets desktop apps use it.")
NOT_UNDERSTOOD = "The speech model made no words of that. Press the button again, a little closer to the microphone."
