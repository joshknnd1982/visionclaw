# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - runs the two models. Each has its own engine process, started when first needed, on the best
# backend that works (dedicated graphics card, then Vulkan, then the processor). The context size grows when a
# request needs more. When both models do not fit on one graphics chip, the second goes to another chip or to
# the processor so both stay loaded; only when there is no room anywhere do they take turns. No NVDA dependencies.

import contextlib
import threading
import time

from . import backend
from .catalog import CODER, VISION, displayName
from . import debuglog
from ..engine import Engine, EngineError, imageMessages

try:
	from logHandler import log
except ImportError:
	import logging
	log = logging.getLogger("visionClaw")
	log.debugWarning = log.warning

DEFAULT_CONTEXT = {VISION: 4096, CODER: 8192}
CONTEXT_SIZES = (4096, 8192, 16384, 32768)
# Memory kept free for Windows and other programs when deciding whether both models fit.
SPARE_GB = 1.0
# Graphics memory kept free on a chip when deciding whether another model fits on it.
GPU_SPARE_GB = 0.3


class ModelMissing(EngineError):
	"""The model for a role has not been downloaded."""

	def __init__(self, role):
		super().__init__(f"The {role} model has not been downloaded.")
		self.role = role


def contextFor(tokens):
	"""The smallest context size that holds this many tokens."""
	for size in CONTEXT_SIZES:
		if tokens <= size:
			return size
	return CONTEXT_SIZES[-1]


class ModelRuntime:
	"""settings() returns the user's choices: {"backend", "visionModel", "coderModel"}.
	freeMemoryGb() returns the memory Windows still has free, or None."""

	def __init__(self, engineDir, catalog, settings, freeMemoryGb=None, logPaths=None):
		logPaths = logPaths or {}
		self.catalog = catalog
		self._settings = settings
		self._freeMemoryGb = freeMemoryGb or (lambda: None)
		self.engines = {VISION: Engine(engineDir, logPaths.get(VISION)), CODER: Engine(engineDir, logPaths.get(CODER))}
		self._lock = threading.RLock()
		self._idle = threading.Condition()
		self._busy = {VISION: 0, CODER: 0}
		self._lastUse = {VISION: time.monotonic(), CODER: time.monotonic()}
		self._failed = set()
		self._devices = None
		# The backend each engine is running on.
		self.backends = {VISION: None, CODER: None}

	# --- What is available ---

	def devices(self, refresh=False):
		if self._devices is None or refresh:
			self._devices = backend.listDevices(self.engines[VISION].exe)
		return self._devices

	def chain(self):
		"""Backends still worth trying, best first."""
		choice = self._settings().get("backend", backend.AUTO)
		chain = [b for b in backend.plan(choice, self.devices()) if backend.key(b) not in self._failed]
		return chain or [backend.Backend(backend.CPU, None)]

	def entry(self, role):
		preferred = self._settings().get("visionModel" if role == VISION else "coderModel")
		return self.catalog.selected(role, preferred)

	def hasModel(self, role):
		return self.entry(role) is not None

	def _slot(self, role):
		"""Which engine serves a role. When both roles use the same model file, the vision engine serves both."""
		if role == CODER:
			coder, vision = self.entry(CODER), self.entry(VISION)
			if coder and vision and self.catalog.paths(coder)[0] == self.catalog.paths(vision)[0]:
				return VISION
		return role

	def oneModel(self):
		"""Whether one model does both jobs: the same model file is chosen for vision and for code. Then there
		are not two models that could agree, and the user must never be told that there are."""
		return self._slot(CODER) == VISION

	def resetFailures(self):
		"""Try every backend again, for example after the user changed the graphics setting."""
		self._failed.clear()
		self._devices = None

	# --- Starting and stopping ---

	def ensure(self, role, context=None, cancel=None):
		"""Make the model for a role ready, with at least this context size. Returns its engine."""
		entry = self.entry(role)
		if entry is None:
			raise ModelMissing(role)
		slot = self._slot(role)
		if slot != role:
			entry = self.entry(VISION)
		model, mmproj = self.catalog.paths(entry)
		engine = self.engines[slot]
		usual = DEFAULT_CONTEXT[role]
		if slot == VISION and self.oneModel():
			# One model does both jobs. Started with the smaller of the two usual sizes, it had to be loaded a
			# second time as soon as the other job came up: several gigabytes read twice for the first request.
			usual = max(DEFAULT_CONTEXT.values())
		want = min(context or usual, entry["maxContext"])
		with self._lock:
			if engine.running and engine.modelPath == model:
				want = max(want, engine.context)  # the context only grows while the engine runs
				if engine.context == want:
					return engine
			# Restarting would cut off an answer that is being written.
			with self._idle:
				while self._busy[slot]:
					if cancel is not None and cancel.is_set():
						raise EngineError("Cancelled.")
					self._idle.wait(0.2)
			chain = self.chain()
			other = CODER if slot == VISION else VISION
			if self.engines[other].running:
				if self._placeBeside(engine, slot, entry, model, mmproj, want, chain, cancel):
					return engine
				# There is no room beside the other model anywhere, so the two take turns.
				if not self._busy[other]:
					log.debug(f"VisionClaw: unloading the {other} model to make room for the {slot} model")
					debuglog.log("runtime", f"Unloading the {other} model to make room for the {slot} model.")
					self.engines[other].stop()
					self.backends[other] = None
			last = None
			for choice in chain:
				if cancel is not None and cancel.is_set():
					raise EngineError("Cancelled.")
				try:
					engine.ensure(model, mmproj, backend.engineArgs(choice, bool(mmproj)), want)
				except EngineError as e:
					log.warning(f"VisionClaw: the {slot} model did not start on {backend.key(choice)}: {e}")
					debuglog.error("runtime", f"The {slot} model did not start on {backend.key(choice)}; trying the next choice", e)
					if choice.kind != backend.CPU:
						self._failed.add(backend.key(choice))
					last = e
					continue
				self.backends[slot] = choice
				return engine
			raise last or EngineError("The engine could not be started.")

	def _hasRoom(self, choice, entry, devices):
		"""Whether a model fits on a backend right now, next to whatever is already loaded there."""
		if choice.device is None:
			free = self._freeMemoryGb()
			return free is None or free >= entry["memoryGb"] + SPARE_GB
		device = devices.get(choice.device.id)
		return device is not None and device.freeMb / 1024 >= entry["memoryGb"] + GPU_SPARE_GB

	def _placeBeside(self, engine, slot, entry, model, mmproj, want, chain, cancel):
		"""Start a model while the other one stays loaded: on the best backend that still has room for it.
		With side by side on, that may be another graphics chip or the processor, so that two large models
		which do not fit on one graphics card together do not have to take turns. Returns True if it started."""
		devices = {d.id: d for d in self.devices(refresh=True)}
		candidates = chain if self._settings().get("sideBySide", True) else chain[:1]
		# A model that is only being restarted, for a larger context, already has its place.
		current = backend.key(self.backends[slot]) if engine.running and self.backends[slot] else None
		for choice in candidates:
			if cancel is not None and cancel.is_set():
				raise EngineError("Cancelled.")
			if backend.key(choice) != current and not self._hasRoom(choice, entry, devices):
				continue
			try:
				engine.ensure(model, mmproj, backend.engineArgs(choice, bool(mmproj)), want)
			except EngineError as e:
				# Most likely it did not fit after all. The backend itself is not marked as broken.
				log.warning(f"VisionClaw: the {slot} model did not start beside the other on {backend.key(choice)}: {e}")
				debuglog.error("runtime", f"The {slot} model did not start beside the other on {backend.key(choice)}", e)
				continue
			self.backends[slot] = choice
			return True
		return False

	def whereText(self):
		"""Where each loaded model is running, in a sentence, or ""."""
		found = []
		for slot in (VISION, CODER):
			choice = self.backends[slot]
			if self.engines[slot].running and choice is not None:
				found.append(f"The {slot} model runs on {backend.describe(choice)}.")
		if self.oneModel() and found:
			found = [found[0].replace("The vision model runs", "One model does both jobs and runs")]
		return " ".join(found)

	def aboutText(self):
		"""Which models VisionClaw has and uses, in sentences: what is chosen for each job, what is stored on the
		disk, and where a loaded model runs. Read from the settings and the disk by plain code; no model is
		asked, because a model does not know its own name."""
		def named(entry):
			return displayName(entry).split(", used for")[0]

		vision, coder = self.entry(VISION), self.entry(CODER)
		lines = []
		if self.oneModel():
			lines.append(
				f"VisionClaw uses one model, {named(vision)}, for both jobs: looking at the screen and planning, and "
				"checking and writing code.")
		else:
			lines.append(
				f"For looking at the screen and planning, VisionClaw uses the model {named(vision)}." if vision
				else "No model is chosen yet for looking at the screen and planning.")
			lines.append(
				f"For checking and writing code, it uses the model {named(coder)}." if coder
				else "No model is chosen yet for checking and writing code.")
		try:
			stored = list(self.catalog.stored())
		except Exception:
			stored = []
		whole = [model for model in stored if not model["partial"]]
		sizes = [f"{model['name']}, {model['bytes'] / 2 ** 30:.1f} GB" for model in whole]
		if len(sizes) == 1:
			lines.append(f"One model is stored on this computer: {sizes[0]}.")
		elif sizes:
			lines.append(f"{len(sizes)} models are stored on this computer: {'; '.join(sizes)}.")
		else:
			lines.append("No model is stored on this computer yet.")
		unfinished = [model["name"] for model in stored if model["partial"]]
		if unfinished:
			lines.append("A download was not finished: " + ", ".join(unfinished) + ".")
		where = self.whereText()
		if where:
			lines.append(where)
		elif vision or coder:
			lines.append("No model is loaded at the moment. A model is loaded when it is needed.")
		return " ".join(lines)

	def markFailed(self, role):
		"""The backend a role runs on stopped working mid-request. The next request uses the next one."""
		slot = self._slot(role)
		current = self.backends[slot]
		if current is not None and current.kind != backend.CPU:
			self._failed.add(backend.key(current))
		self.stop(slot)

	def stop(self, role=None):
		for slot in ((VISION, CODER) if role is None else (role,)):
			self.engines[slot].stop()
			self.backends[slot] = None

	def unloadIdle(self, role, seconds):
		"""Unload a model nobody has used for this long. Returns True if it was unloaded."""
		with self._idle:
			if self._busy[role] or not self.engines[role].running:
				return False
			if time.monotonic() - self._lastUse[role] < seconds:
				return False
		self.stop(role)
		return True

	# --- Using a model ---

	@contextlib.contextmanager
	def _use(self, slot):
		with self._idle:
			self._busy[slot] += 1
		try:
			yield
		finally:
			with self._idle:
				self._busy[slot] -= 1
				self._lastUse[slot] = time.monotonic()
				self._idle.notify_all()

	def isBusy(self, role=None):
		return bool(self._busy[role]) if role else any(self._busy.values())

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None,
			context=None):
		"""One request to the model of a role. Returns the answer, or None if cancelled."""
		engine = self.ensure(role, context, cancel)
		with self._use(self._slot(role)):
			return engine.chat(messages, maxTokens, onText, cancel, options, raw, info)

	def describe(self, jpegBytes, prompt, maxTokens, onText=None, cancel=None, options=None, system=None):
		"""One image and a prompt, to the vision model. system: what it is told first (claw/prompts.py), or None."""
		return self.chat(VISION, imageMessages(jpegBytes, prompt, system), maxTokens, onText, cancel, options)

	def status(self):
		"""What is loaded, for telling the user."""
		found = {}
		for role in (VISION, CODER):
			entry = self.entry(role)
			slot = self._slot(role)
			engine = self.engines[slot]
			found[role] = {
				"model": displayName(entry) if entry else None,
				"loaded": engine.running,
				"backend": self.backends[slot],
				"context": engine.context,
			}
		return found
