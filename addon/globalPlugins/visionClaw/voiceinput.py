# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - asking by voice: the microphone, and the speech model in the bundled engine (claw/voice.py).
# What is said is recorded into memory, turned into text on this computer, and thrown away: no file is written
# and nothing is sent anywhere. The text is put where the user can read and change it; nothing is ever done
# with a request before the user has heard what was understood and sent it.
#
# The microphone is read through Windows' waveform-audio functions in winmm.dll. Their structures and functions
# were read on 2026-11-18 from Microsoft's pages, and the values of the constants from the header files of the
# Windows SDK on the owner's computer (mmeapi.h and mmsyscom.h, version 10.0.26100.0); read them again before
# changing one, do not write a structure from memory:
#   WAVEFORMATEX    https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/ns-mmeapi-waveformatex
#   WAVEHDR         https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/ns-mmeapi-wavehdr
#   waveInOpen      https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveinopen
# No callback is used: the buffers are looked at a few times a second, so nothing of Windows ever calls into
# Python. Whatever is opened here is closed in a finally.

import base64
import ctypes
import os
import threading
import time
from ctypes import wintypes

from .claw import debuglog, voice
from .engine import Engine, EngineError
from .vclog import log

WAVE_MAPPER = 0xFFFFFFFF  # ((UINT)-1): Windows chooses the microphone that is set as the default
WAVE_FORMAT_PCM = 1
CALLBACK_NULL = 0
WHDR_DONE = 0x00000001
MMSYSERR_NOERROR = 0
BUFFERS = 4
POLL_SECONDS = 0.02
# The engine's own arguments for the processor alone, as claw/backend.py gives them for a model with a second file.
CPU_ARGS = ("-ngl", "0", "--device", "none", "--no-mmproj-offload")
CONTEXT = 4096


class WAVEFORMATEX(ctypes.Structure):
	_pack_ = 1
	_fields_ = [
		("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
		("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
		("cbSize", wintypes.WORD)]


class WAVEHDR(ctypes.Structure):
	pass


WAVEHDR._fields_ = [
	("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD), ("dwBytesRecorded", wintypes.DWORD),
	("dwUser", ctypes.c_size_t), ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
	("lpNext", ctypes.POINTER(WAVEHDR)), ("reserved", ctypes.c_size_t)]


class NoMicrophone(Exception):
	"""Windows gave no microphone, or it stopped giving sound."""


def _winmm():
	winmm = ctypes.WinDLL("winmm")
	handle = wintypes.HANDLE
	winmm.waveInGetNumDevs.restype = wintypes.UINT
	winmm.waveInOpen.argtypes = [
		ctypes.POINTER(handle), wintypes.UINT, ctypes.POINTER(WAVEFORMATEX), ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
	for name in ("waveInPrepareHeader", "waveInUnprepareHeader", "waveInAddBuffer"):
		getattr(winmm, name).argtypes = [handle, ctypes.POINTER(WAVEHDR), wintypes.UINT]
	for name in ("waveInStart", "waveInStop", "waveInReset", "waveInClose"):
		getattr(winmm, name).argtypes = [handle]
	for name in ("waveInOpen", "waveInPrepareHeader", "waveInUnprepareHeader", "waveInAddBuffer", "waveInStart", "waveInStop",
			"waveInReset", "waveInClose"):
		getattr(winmm, name).restype = wintypes.UINT
	return winmm


def microphones():
	"""How many microphones Windows has; 0 when none or when that cannot be found out."""
	try:
		return int(_winmm().waveInGetNumDevs())
	except Exception:
		return 0


def chunks(stop, seconds=voice.MAX_SECONDS + 5):
	"""The sound of the default microphone, a tenth of a second at a time, as 16-bit samples at 16 kHz, until
	stop is set or the time is over. Raises NoMicrophone when Windows gives none."""
	winmm = _winmm()
	wanted = WAVEFORMATEX(
		WAVE_FORMAT_PCM, 1, voice.RATE, voice.RATE * voice.SAMPLE_BYTES, voice.SAMPLE_BYTES, 8 * voice.SAMPLE_BYTES, 0)
	device = wintypes.HANDLE()
	result = winmm.waveInOpen(ctypes.byref(device), WAVE_MAPPER, ctypes.byref(wanted), 0, 0, CALLBACK_NULL)
	if result != MMSYSERR_NOERROR:
		raise NoMicrophone(f"waveInOpen answered {result}")
	headers, buffers, prepared = [], [], []
	try:
		for _number in range(BUFFERS):
			buffer = ctypes.create_string_buffer(voice.CHUNK_BYTES)
			header = WAVEHDR()
			header.lpData = ctypes.cast(buffer, ctypes.c_void_p)
			header.dwBufferLength = voice.CHUNK_BYTES
			header.dwFlags = 0
			buffers.append(buffer)
			headers.append(header)
			if winmm.waveInPrepareHeader(device, ctypes.byref(header), ctypes.sizeof(WAVEHDR)) != MMSYSERR_NOERROR:
				raise NoMicrophone("a buffer could not be prepared")
			prepared.append(header)
			if winmm.waveInAddBuffer(device, ctypes.byref(header), ctypes.sizeof(WAVEHDR)) != MMSYSERR_NOERROR:
				raise NoMicrophone("a buffer could not be given to the microphone")
		if winmm.waveInStart(device) != MMSYSERR_NOERROR:
			raise NoMicrophone("the microphone did not start")
		at = 0
		deadline = time.monotonic() + seconds
		waited = time.monotonic()
		while not stop.is_set() and time.monotonic() < deadline:
			header = headers[at]
			if not header.dwFlags & WHDR_DONE:
				if time.monotonic() - waited > 3:
					raise NoMicrophone("the microphone gave no sound for three seconds")
				time.sleep(POLL_SECONDS)
				continue
			waited = time.monotonic()
			data = ctypes.string_at(header.lpData, header.dwBytesRecorded)
			header.dwBytesRecorded = 0
			header.dwFlags &= ~WHDR_DONE
			if winmm.waveInAddBuffer(device, ctypes.byref(header), ctypes.sizeof(WAVEHDR)) != MMSYSERR_NOERROR:
				raise NoMicrophone("a buffer could not be given back to the microphone")
			at = (at + 1) % BUFFERS
			if data:
				yield data
	finally:
		# Reset gives every buffer back; only then may they be unprepared and the microphone closed.
		winmm.waveInReset(device)
		for header in prepared:
			winmm.waveInUnprepareHeader(device, ctypes.byref(header), ctypes.sizeof(WAVEHDR))
		winmm.waveInClose(device)


def record(stop, onHeard=None, source=None):
	"""Listen until the person has finished speaking, stop is set, or the time is over. Returns (the recording as
	16-bit samples, why listening ended: voice.HEARD, NOTHING, TOO_LONG or STOPPED). onHeard() is called once, when
	speech begins. source: for tests, what gives the sound in place of the microphone."""
	listener = voice.Listener()
	why = voice.STOPPED
	told = False
	for chunk in (source or chunks)(stop):
		ended = listener.feed(chunk)
		if listener.spoke() and not told:
			told = True
			if onHeard is not None:
				try:
					onHeard()
				except Exception:
					pass
		if ended is not None:
			why = ended
			break
	if why == voice.STOPPED and not listener.spoke():
		return b"", voice.STOPPED
	return listener.audio(), why


class Ears:
	"""The speech model in an engine of its own, on the processor. It is started for one recording and stopped
	again, so that it takes no memory while nobody speaks: it is ready in about a second."""

	def __init__(self, engineDir, store, chosenId, logPath=None):
		self._engineDir, self._store, self._chosenId, self._logPath = engineDir, store, chosenId, logPath
		self._lock = threading.Lock()

	def model(self):
		return self._store.chosen(self._chosenId())

	def text(self, pcm, names=(), cancel=None):
		"""What was said in a recording, as text; "" when the model heard no words. Raises EngineError."""
		entry = self.model()
		if entry is None:
			raise EngineError("No speech model is on this computer.")
		modelPath, audioPath = self._store.paths(entry)
		with self._lock:
			engine = Engine(self._engineDir, self._logPath)
			# The engine's own first question is a picture; a speech model takes none.
			engine._warmUp = lambda hasProjector: None
			started = time.monotonic()
			try:
				engine.ensure(modelPath, audioPath, CPU_ARGS, CONTEXT)
				ready = time.monotonic() - started
				audio = base64.b64encode(voice.wav(pcm)).decode("ascii")
				messages = [
					{"role": "system", "content": voice.context(names)},
					{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": audio, "format": "wav"}}]}]
				answer = engine.chat(messages, voice.TOKENS, cancel=cancel, raw=True)
			finally:
				engine.stop()
		found = voice.heard(answer)
		debuglog.log("voice", (
			f"{entry['name']} was ready after {ready:.1f} s and answered after {time.monotonic() - started:.1f} s in all, "
			f"for {len(pcm) / (voice.RATE * voice.SAMPLE_BYTES):.1f} s of sound. It heard {len(found.split())} words."))
		# What was said is the user's own; only its length is written to the log unless the log is detailed.
		debuglog.detail("voice", f"Heard: {found!r}")
		return found


def listen(ears, stop, onState, names=(), source=None):
	"""One spoken request from the microphone to text. onState(state) is called with "listening", "speaking" and
	"thinking" as it goes on. Returns (the text or "", the sentence to say when there is no text or "")."""
	try:
		onState("listening")
		pcm, why = record(stop, lambda: onState("speaking"), source)
	except NoMicrophone as e:
		debuglog.error("voice", "The microphone could not be read", e)
		return "", voice.NO_MICROPHONE
	except OSError as e:
		debuglog.error("voice", "Windows' sound functions could not be used", e)
		return "", voice.NO_MICROPHONE
	if not pcm:
		return "", ("" if why == voice.STOPPED else voice.NOTHING_HEARD)
	onState("thinking")
	try:
		text = ears.text(pcm, names)
	except EngineError as e:
		log.error("VisionClaw: the speech model could not turn the recording into text", exc_info=True)
		return "", f"The speech model could not be used: {e}"
	return (text, "") if text else ("", voice.NOT_UNDERSTOOD)
