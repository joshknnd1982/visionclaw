# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - local image description for NVDA.
# Runs the bundled engine (llama.cpp server) and streams answers from it: image descriptions, JSON and code.
# This module has no NVDA dependencies so it can be tested on its own.

import base64
import ctypes
import http.client
import io
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from ctypes import wintypes

from .claw import debuglog

try:
	from logHandler import log
except ImportError:
	import logging
	log = logging.getLogger("visionClaw")
	log.debugWarning = log.warning

CREATE_NO_WINDOW = 0x08000000


def _shown(messages):
	"""A conversation as written to VisionClaw's log: the text whole, a picture as its size only."""
	lines = []
	for message in messages:
		content = message.get("content")
		if isinstance(content, list):
			parts = []
			for part in content:
				if part.get("type") == "text":
					parts.append(part.get("text", ""))
				else:
					parts.append(f"[a picture, {len(str(part.get('image_url', {}).get('url', ''))) * 3 // 4} bytes]")
			content = " ".join(parts)
		lines.append(f"{message.get('role')}: {content}")
	return "\n".join(lines)


def _logTail(path, lines=25):
	"""The last lines the engine wrote about itself, for the log entry of a failed start."""
	try:
		with open(path, encoding="utf-8", errors="replace") as f:
			return "".join(f.readlines()[-lines:]).rstrip()
	except (OSError, TypeError):
		return ""


class EngineError(Exception):
	pass


# --- Job object: makes Windows kill llama-server if NVDA exits or crashes. ---

class _IoCounters(ctypes.Structure):
	_fields_ = [(n, ctypes.c_ulonglong) for n in (
		"ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
		"ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BasicLimits(ctypes.Structure):
	_fields_ = [
		("PerProcessUserTimeLimit", ctypes.c_longlong),
		("PerJobUserTimeLimit", ctypes.c_longlong),
		("LimitFlags", wintypes.DWORD),
		("MinimumWorkingSetSize", ctypes.c_size_t),
		("MaximumWorkingSetSize", ctypes.c_size_t),
		("ActiveProcessLimit", wintypes.DWORD),
		("Affinity", ctypes.c_size_t),
		("PriorityClass", wintypes.DWORD),
		("SchedulingClass", wintypes.DWORD),
	]


class _ExtendedLimits(ctypes.Structure):
	_fields_ = [
		("BasicLimitInformation", _BasicLimits),
		("IoInfo", _IoCounters),
		("ProcessMemoryLimit", ctypes.c_size_t),
		("JobMemoryLimit", ctypes.c_size_t),
		("PeakProcessMemoryUsed", ctypes.c_size_t),
		("PeakJobMemoryUsed", ctypes.c_size_t),
	]


_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JobObjectExtendedLimitInformation = 9


def _createKillOnCloseJob():
	k32 = ctypes.WinDLL("kernel32", use_last_error=True)
	k32.CreateJobObjectW.restype = wintypes.HANDLE
	k32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
	k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
	k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
	job = k32.CreateJobObjectW(None, None)
	if not job:
		return None, k32
	info = _ExtendedLimits()
	info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
	k32.SetInformationJobObject(job, _JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info))
	return job, k32


def prepareImage(image, maxSide):
	"""Shrink a PIL image so its longest side is at most maxSide and return JPEG bytes.
	Smaller images are the biggest speed win: fewer image tokens for the model to read."""
	image = image.convert("RGB")
	if max(image.size) > maxSide:
		image = image.copy()
		image.thumbnail((maxSide, maxSide), _lanczos())
	buf = io.BytesIO()
	image.save(buf, "JPEG", quality=90)
	return buf.getvalue()


def imageMessages(jpegBytes, prompt):
	"""The start of a conversation about one image."""
	b64 = base64.b64encode(jpegBytes).decode("ascii")
	return [{"role": "user", "content": [
		{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
		{"type": "text", "text": prompt},
	]}]


def _lanczos():
	from PIL import Image
	return getattr(Image, "Resampling", Image).LANCZOS


def _freePort():
	with socket.socket() as s:
		s.bind(("127.0.0.1", 0))
		return s.getsockname()[1]


# The engine always picks the likeliest next word, which is fastest and most exact. A small model can then get
# stuck saying one sentence again and again. The DRY setting makes it avoid repeating what it already said; reading
# a receipt was as exact with it as without.
ANTI_LOOP = {"dry_multiplier": 0.8, "dry_base": 1.75, "dry_allowed_length": 2, "dry_penalty_last_n": 512}


class RepeatGuard:
	"""Passes streamed text on, but leaves out sentences said before, and stops after a few: the model is stuck.
	Text goes on at once unless it is the start of a sentence said before, so speech does not start later."""

	_END = re.compile(r"[.!?。！？](?=\s)|\n")
	# Short pieces like "- Price:" may rightly come again.
	MIN_CHARS = 12
	MAX_REPEATS = 3

	def __init__(self, onText=None):
		self._onText = onText
		self._seen = set()
		self._current = ""  # the sentence being written
		self._sent = 0  # how much of it was passed on
		self._repeats = 0
		self._out = []

	@staticmethod
	def _key(text):
		return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())

	def _pass(self, text):
		if text:
			self._out.append(text)
			if self._onText is not None:
				self._onText(text)

	def feed(self, delta):
		"""Returns False once the model is repeating itself, so it should be stopped."""
		self._current += delta
		while True:
			end = self._END.search(self._current)
			if end is None:
				break
			sentence, self._current = self._current[:end.end()], self._current[end.end():]
			sent, self._sent = self._sent, 0
			key = self._key(sentence)
			if not sent and len(key) >= self.MIN_CHARS and key in self._seen:
				self._repeats += 1
				if self._repeats >= self.MAX_REPEATS:
					self._current, self._sent = "", 0  # what follows is more of the same
					return False
				continue
			self._seen.add(key)
			self._pass(sentence[sent:])
		if len(self._current) > self._sent:
			key = self._key(self._current)
			# Held back only while it could still turn out to be a repeat.
			if self._sent or not any(s.startswith(key) for s in self._seen if len(s) >= self.MIN_CHARS):
				self._pass(self._current[self._sent:])
				self._sent = len(self._current)
		return True

	def finish(self):
		"""Everything passed on, with what is left of the last sentence unless it is a repeat."""
		rest = self._current[self._sent:]
		if rest and (self._sent or self._key(self._current) not in self._seen):
			self._pass(rest)
		self._current, self._sent = "", 0
		return "".join(self._out)


class _PassThrough:
	"""Passes streamed text on unchanged; used where RepeatGuard would damage the answer, like JSON and code."""

	def __init__(self, onText=None):
		self._onText = onText
		self._out = []

	def feed(self, delta):
		self._out.append(delta)
		if self._onText is not None:
			self._onText(delta)
		return True

	def finish(self):
		return "".join(self._out)


class CodeGuard(_PassThrough):
	"""Passes program code on unchanged, but stops a model that writes the same line again and again, which
	small models sometimes do with comments until they run out of room."""

	MAX_SAME = 5
	WINDOW = 12
	# No small add-on is this long; a model that gets here has lost its way and would only waste the user's time.
	MAX_LINES = 90

	def __init__(self, onText=None):
		super().__init__(onText)
		self._line = ""
		self._recent = []
		self._lines = 0

	def feed(self, delta):
		super().feed(delta)
		self._line += delta
		while "\n" in self._line:
			line, self._line = self._line.split("\n", 1)
			line = line.strip()
			self._lines += 1
			if self._lines > self.MAX_LINES:
				return False
			if not line:
				continue
			self._recent = (self._recent + [line])[-self.WINDOW:]
			if self._recent.count(line) >= self.MAX_SAME:
				return False
		return True

	def finish(self):
		"""The code, without the repeated lines it ended in."""
		text = "".join(self._out)
		if self._recent and self._recent.count(self._recent[-1]) >= self.MAX_SAME:
			lines = text.rstrip().split("\n")
			while len(lines) > 1 and lines[-1].strip() == lines[-2].strip():
				lines.pop()
			text = "\n".join(lines[:-1]) + "\n"
		return text


class Engine:
	"""Owns one llama-server process. Thread safe; all methods may block."""

	def __init__(self, engineDir, logPath=None):
		self._exe = os.path.join(engineDir, "vcengine.exe")
		self._logPath = logPath
		self._lock = threading.RLock()
		self._proc = None
		self._port = None
		self._config = None
		self._job, self._k32 = _createKillOnCloseJob()

	@property
	def exe(self):
		return self._exe

	@property
	def running(self):
		return self._proc is not None and self._proc.poll() is None

	@property
	def usingGpu(self):
		return bool(self.running and self._config and "--device" in self._config[2] and "none" not in self._config[2])

	@property
	def context(self):
		"""The context size the engine was started with, or 0 if it is not running."""
		return self._config[3] if self.running and self._config else 0

	@property
	def modelPath(self):
		return self._config[0] if self.running and self._config else None

	def ensure(self, modelPath, mmprojPath, backendArgs, context=4096):
		"""Start the server with this configuration unless it is already running with it.
		backendArgs are the engine arguments that choose the graphics device or the processor."""
		config = (modelPath, mmprojPath, tuple(backendArgs), int(context))
		with self._lock:
			if self.running and self._config == config:
				return
			self.stop()
			self._start(config)

	def _start(self, config):
		modelPath, mmprojPath, backendArgs, context = config
		self._port = _freePort()
		args = [
			self._exe, "-m", modelPath, "--host", "127.0.0.1", "--port", str(self._port),
			"-c", str(context), "-np", "1", "--no-webui",
		]
		if mmprojPath:
			args += ["--mmproj", mmprojPath]
		args += list(backendArgs)
		log.debug(f"VisionClaw: starting {args}")
		debuglog.log("engine", f"Starting the engine: {args}")
		started = time.monotonic()
		logFile = open(self._logPath, "w", encoding="utf-8", errors="replace") if self._logPath else subprocess.DEVNULL
		try:
			self._proc = subprocess.Popen(
				args, cwd=os.path.dirname(self._exe), stdin=subprocess.DEVNULL,
				stdout=subprocess.DEVNULL, stderr=logFile, creationflags=CREATE_NO_WINDOW,
			)
		finally:
			if logFile is not subprocess.DEVNULL:
				logFile.close()
		if self._job:
			self._k32.AssignProcessToJobObject(self._job, int(self._proc._handle))
		self._config = config
		try:
			self._waitHealthy(timeout=180)
		except EngineError as e:
			debuglog.error("engine", (
				f"The engine did not get ready after {time.monotonic() - started:.1f} s: {e}\n"
				f"What the engine wrote last:\n{_logTail(self._logPath)}"), e)
			raise
		debuglog.log("engine", f"The engine is ready on port {self._port} after {time.monotonic() - started:.1f} s.")
		self._warmUp(bool(mmprojPath))
		debuglog.log("engine", f"The engine is warmed up after {time.monotonic() - started:.1f} s.")

	def _waitHealthy(self, timeout):
		deadline = time.monotonic() + timeout
		while time.monotonic() < deadline:
			if self._proc.poll() is not None:
				self._proc = None
				raise EngineError("The description engine stopped while loading the model.")
			try:
				with urllib.request.urlopen(self._url("/health"), timeout=2) as r:
					if json.load(r).get("status") == "ok":
						return
			except (urllib.error.URLError, OSError, ValueError):
				pass
			time.sleep(0.2)
		self.stop()
		raise EngineError("The description engine took too long to load the model.")

	def _warmUp(self, hasProjector):
		# The first request compiles GPU shaders; do it now instead of on the user's first press.
		try:
			if hasProjector:
				from PIL import Image
				self.describe(prepareImage(Image.new("RGB", (64, 64), "gray"), 64), "Hi", 1)
			else:
				self.chat([{"role": "user", "content": "Hi"}], 1, raw=True)
		except (EngineError, ImportError):
			log.debugWarning("VisionClaw: warm-up failed", exc_info=True)

	def stop(self):
		with self._lock:
			if self._proc is not None:
				debuglog.log("engine", f"Stopping the engine on port {self._port}.")
				try:
					self._proc.kill()
					self._proc.wait(timeout=5)
				except Exception:
					log.debugWarning("VisionClaw: could not stop engine", exc_info=True)
			self._proc = None
			self._config = None

	def _url(self, path):
		return f"http://127.0.0.1:{self._port}{path}"

	def describe(self, jpegBytes, prompt, maxTokens, onText=None, cancel=None):
		"""Send one image and prompt. Calls onText(delta) as text streams in.
		Returns the full text, or None if cancelled."""
		return self.chat(imageMessages(jpegBytes, prompt), maxTokens, onText, cancel)

	def chat(self, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None):
		"""Like describe, but continues a conversation. Asking again with the same start
		reuses the engine's work on the image, so follow-up questions answer quickly.
		options are extra request fields, like temperature or response_format; they win over the defaults.
		raw is for JSON and code: nothing is left out of the answer and the anti-repeat setting is off, because
		code rightly repeats itself. raw="code" also stops a model that writes one line over and over. info, a dict, receives "finish" (why the model stopped) and "thinking"."""
		if not self.running:
			raise EngineError("The description engine is not running.")
		body = {
			"messages": messages,
			"max_tokens": maxTokens,
			"temperature": 0,
			"stream": True,
			# Keep the engine's work on the image, so a follow-up question does not read it again.
			"cache_prompt": True,
			# Models that can think only do so when asked to; a description should start at once.
			"chat_template_kwargs": {"enable_thinking": False},
		}
		if not raw:
			body.update(ANTI_LOOP)
		if options:
			body.update(options)
		guard = CodeGuard(onText) if raw == "code" else _PassThrough(onText) if raw else RepeatGuard(onText)
		thinking = []
		asked = time.monotonic()
		if debuglog.detailed():
			debuglog.detail("engine", (
				f"Question to the model on port {self._port} (at most {maxTokens} tokens, options {options}):\n"
				f"{_shown(messages)}"))
		conn = http.client.HTTPConnection("127.0.0.1", self._port, timeout=600)
		finished = threading.Event()
		if cancel is not None:
			threading.Thread(target=self._abortOnCancel, args=(conn, cancel, finished), daemon=True).start()
		try:
			conn.request(
				"POST", "/v1/chat/completions", body=json.dumps(body).encode("utf-8"),
				headers={"Content-Type": "application/json"},
			)
			resp = conn.getresponse()
			if resp.status != 200:
				raise EngineError(f"The description engine returned an error: {resp.read()[:300]!r}")
			for rawLine in resp:
				if cancel is not None and cancel.is_set():
					return None
				line = rawLine.decode("utf-8", "replace").strip()
				if not line.startswith("data:") or line.endswith("[DONE]"):
					continue
				msg = json.loads(line[5:])
				if "error" in msg:
					raise EngineError(str(msg["error"].get("message", msg["error"])))
				if not msg.get("choices"):
					continue
				choice = msg["choices"][0]
				if info is not None and choice.get("finish_reason"):
					info["finish"] = choice["finish_reason"]
				delta = choice.get("delta") or {}
				if delta.get("reasoning_content"):
					thinking.append(delta["reasoning_content"])
				text = delta.get("content")
				if text and not guard.feed(text):
					log.debug("VisionClaw: the description repeated itself; stopped")
					break  # closing the connection below stops the engine
		except (http.client.HTTPException, OSError) as e:
			if cancel is not None and cancel.is_set():
				debuglog.log("engine", f"The question was stopped after {time.monotonic() - asked:.2f} s.")
				return None
			debuglog.error("engine", f"The connection to the engine was lost after {time.monotonic() - asked:.2f} s", e)
			raise EngineError(f"Lost connection to the description engine: {e}")
		except EngineError as e:
			debuglog.error("engine", f"The engine reported an error after {time.monotonic() - asked:.2f} s", e)
			raise
		finally:
			finished.set()
			conn.close()
			if info is not None:
				info["thinking"] = "".join(thinking)
		if cancel is not None and cancel.is_set():
			debuglog.log("engine", f"The question was stopped after {time.monotonic() - asked:.2f} s.")
			return None
		answer = guard.finish().strip()
		if debuglog.detailed():
			debuglog.detail("engine", (
				f"Answer after {time.monotonic() - asked:.2f} s"
				+ (f" (stopped because: {info.get('finish')})" if info and info.get("finish") else "") + f":\n{answer}"
				+ (f"\nIts thinking:\n{''.join(thinking)}" if thinking else "")))
		return answer

	@staticmethod
	def _abortOnCancel(conn, cancel, finished):
		# Closing the socket makes llama-server drop the request at once, so the next one is not queued behind it.
		while not finished.is_set():
			if cancel.wait(0.05):
				if conn.sock is not None:
					try:
						conn.sock.shutdown(socket.SHUT_RDWR)
					except OSError:
						pass
				return
