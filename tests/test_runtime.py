# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Checks where the two models are put, with stand-ins for the engines and the graphics chips:
both on the dedicated card when they fit, the second on another chip or the processor when they do not,
taking turns only when there is no room anywhere, and falling back when a backend does not start."""
import harness  # noqa: F401
from visionClaw.claw import backend, runtime
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.engine import EngineError

DEDICATED = backend.Device("Vulkan0", "NVIDIA GeForce RTX 5060 Laptop GPU", 7810, 7000, True)
BUILT_IN = backend.Device("Vulkan1", "AMD Radeon 780M Graphics", 16286, 15000, False)
LARGE_VISION = {"id": "v", "name": "Vision 9B", "memoryGb": 7.6, "maxContext": 16384}
LARGE_CODER = {"id": "c", "name": "Coder 7B", "memoryGb": 5.8, "maxContext": 32768}
SMALL_VISION = dict(LARGE_VISION, name="Vision 2B", memoryGb=2.6)
SMALL_CODER = dict(LARGE_CODER, name="Coder 1.5B", memoryGb=1.8)


class FakeEngine:
	exe = "vcengine.exe"

	def __init__(self, world):
		self._world = world
		self.running = False
		self.modelPath = None
		self.context = 0
		self.device = None
		self.starts = []
		self.args = []

	def ensure(self, modelPath, mmprojPath, backendArgs, context=4096):
		self.stop()
		device = backendArgs[backendArgs.index("--device") + 1]
		self.starts.append(device)
		self.args.append(list(backendArgs))
		if device in self._world.broken:
			raise EngineError(f"could not start on {device}")
		self.running, self.modelPath, self.context, self.device = True, modelPath, context, device
		self._world.loaded[id(self)] = (device, self._world.sizes[modelPath])

	def stop(self):
		self.running, self.context = False, 0
		self._world.loaded.pop(id(self), None)


class World:
	"""A computer: its graphics chips, its free memory, and what is loaded where."""

	def __init__(self, devices, vision, coder, ramGb=32.0, sideBySide=True, choice="auto", broken=(), hard=None):
		self.devices, self.ramGb, self.broken = devices, ramGb, set(broken)
		self.loaded = {}
		self.sizes = {"vision.gguf": vision["memoryGb"], "coder.gguf": coder["memoryGb"]}
		entries = {VISION: vision, CODER: coder}
		paths = {vision["id"]: ("vision.gguf", "mmproj.gguf"), coder["id"]: ("coder.gguf", None)}
		if hard is not None:
			# The model for hard cases: text only, no projector.
			paths[hard["id"]] = ("hard.gguf", None)
			self.sizes["hard.gguf"] = hard["memoryGb"]
		catalog = type("Catalog", (), {
			"selected": lambda self, role, preferred=None: entries[role],
			"paths": lambda self, entry: paths[entry["id"]],
		})()
		settings = {"backend": choice, "sideBySide": sideBySide}
		self.runtime = runtime.ModelRuntime("engine", catalog, lambda: settings, self.freeRam)
		self.runtime.engines = {VISION: FakeEngine(self), CODER: FakeEngine(self)}
		self.runtime.devices = self.listDevices

	def used(self, device):
		return sum(size for where, size in self.loaded.values() if where == device)

	def freeRam(self):
		# A built-in chip and the processor both use the computer's main memory.
		return self.ramGb - self.used("none") - sum(self.used(d.id) for d in self.devices if not d.dedicated)

	def listDevices(self, refresh=False):
		return [d._replace(freeMb=int(d.freeMb - self.used(d.id) * 1024)) for d in self.devices]

	def where(self):
		rt = self.runtime
		return {role: rt.engines[role].device if rt.engines[role].running else None for role in (VISION, CODER)}


# 1. Two small models fit on the dedicated card together.
world = World([DEDICATED, BUILT_IN], SMALL_VISION, SMALL_CODER)
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: "Vulkan0", CODER: "Vulkan0"}

# 2. Two large models do not fit on an 8 GB card together: the second goes to the built-in chip, and both stay.
world = World([DEDICATED, BUILT_IN], LARGE_VISION, LARGE_CODER)
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: "Vulkan0", CODER: "Vulkan1"}, world.where()
assert world.runtime.engines[VISION].starts == ["Vulkan0"]  # the first model was never unloaded
text = world.runtime.whereText()
assert "The vision model runs on NVIDIA GeForce RTX 5060 Laptop GPU (dedicated graphics card)." in text
assert "The coder model runs on AMD Radeon 780M Graphics (built-in graphics chip, through Vulkan)." in text
# Going back and forth between them starts nothing again.
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.runtime.engines[VISION].starts == ["Vulkan0"] and world.runtime.engines[CODER].starts == ["Vulkan1"]
# A model that needs a larger context is restarted where it is, not moved.
world.runtime.ensure(VISION, 16384)
assert world.where()[VISION] == "Vulkan0" and world.runtime.engines[VISION].context == 16384

# 2b. One model for both jobs is loaded once. Its engine starts with the larger of the two usual context
#     sizes, so that the other job does not make it load a second time.
same = dict(LARGE_VISION, id="v")
world = World([DEDICATED, BUILT_IN], same, same)
assert world.runtime.oneModel()
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
world.runtime.ensure(VISION)
assert world.runtime.engines[VISION].starts == ["Vulkan0"] and world.runtime.engines[CODER].starts == [], world.where()
assert world.runtime.engines[VISION].context == 8192
assert world.runtime.whereText() == "One model does both jobs and runs on NVIDIA GeForce RTX 5060 Laptop GPU (dedicated graphics card)."
# Two different models keep their own usual sizes.
world = World([DEDICATED, BUILT_IN], SMALL_VISION, SMALL_CODER)
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert not world.runtime.oneModel()
assert world.runtime.engines[VISION].context == 4096 and world.runtime.engines[CODER].context == 8192

# 3. With only a dedicated card, the second large model goes to the processor.
world = World([DEDICATED], LARGE_VISION, LARGE_CODER)
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: "Vulkan0", CODER: "none"}
assert "The coder model runs on the processor." in world.runtime.whereText()

# 4. No room anywhere: only then do the two take turns on the dedicated card.
world = World([DEDICATED], LARGE_VISION, LARGE_CODER, ramGb=4.0)
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: None, CODER: "Vulkan0"}
world.runtime.ensure(VISION)
assert world.where() == {VISION: "Vulkan0", CODER: None}

# 5. The user turned side by side off: the two take turns on the best chip, as before.
world = World([DEDICATED, BUILT_IN], LARGE_VISION, LARGE_CODER, sideBySide=False)
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: None, CODER: "Vulkan0"}
# ... but two small models still share it.
world = World([DEDICATED, BUILT_IN], SMALL_VISION, SMALL_CODER, sideBySide=False)
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: "Vulkan0", CODER: "Vulkan0"}

# 6. The other chip does not start: the second model goes on to the processor, and the first one stays.
world = World([DEDICATED, BUILT_IN], LARGE_VISION, LARGE_CODER, broken=["Vulkan1"])
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: "Vulkan0", CODER: "none"}
assert world.runtime.engines[CODER].starts == ["Vulkan1", "none"]
# A failed try beside the other model does not mark the chip as broken for good.
assert [backend.key(b) for b in world.runtime.chain()] == ["dedicated:Vulkan0", "vulkan:Vulkan1", "cpu"]

# 7. Starting a model alone: a chip that does not start is skipped and remembered until the settings change.
world = World([DEDICATED, BUILT_IN], SMALL_VISION, SMALL_CODER, broken=["Vulkan0"])
world.runtime.ensure(VISION)
assert world.where()[VISION] == "Vulkan1"
assert [backend.key(b) for b in world.runtime.chain()] == ["vulkan:Vulkan1", "cpu"]
world.runtime.resetFailures()
assert [backend.key(b) for b in world.runtime.chain()][0] == "dedicated:Vulkan0"

# 8. The user chose Vulkan: the built-in chip first, and a second large model beside it on the dedicated card.
smallBuiltIn = BUILT_IN._replace(totalMb=9000, freeMb=9000)
world = World([DEDICATED, smallBuiltIn], LARGE_VISION, LARGE_CODER, choice="vulkan")
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: "Vulkan1", CODER: "Vulkan0"}, world.where()

# 9. The user chose the processor: nothing is ever put on a graphics chip.
world = World([DEDICATED, BUILT_IN], SMALL_VISION, SMALL_CODER, choice="cpu")
world.runtime.ensure(VISION)
world.runtime.ensure(CODER)
assert world.where() == {VISION: "none", CODER: "none"}

# 10. A model larger than the card is split between the card and the processor by the engine itself ("-ngl auto",
#     "--fit on"), where before it was put on the card whole and failed. A model that fits is put on the card whole.
assert backend.splits(10.4, backend.Backend(backend.DEDICATED, DEDICATED))
assert not backend.splits(7.0, backend.Backend(backend.DEDICATED, DEDICATED))
assert not backend.splits(99, backend.Backend(backend.CPU, None))
assert backend.engineArgs(backend.Backend(backend.DEDICATED, DEDICATED), False, True) == [
	"-ngl", "auto", "--fit", "on", "--device", "Vulkan0"]
assert backend.engineArgs(backend.Backend(backend.DEDICATED, DEDICATED), True) == ["-ngl", "99", "--device", "Vulkan0"]
HARD = {"id": "h", "name": "Hard 14B", "memoryGb": 10.4, "maxContext": 32768, "edge": True}
NINE = dict(LARGE_VISION, id="v")

# 11. A hard case: the model for hard cases does both jobs for this thread only, gets the card to itself, split, and is
#     unloaded again afterwards; the everyday model comes back with the next request.
import threading  # noqa: E402
world = World([DEDICATED], NINE, NINE, hard=HARD)
rt = world.runtime
rt.ensure(VISION)
assert world.where() == {VISION: "Vulkan0", CODER: None} and not rt.inHardCase()
elsewhere = {}
with rt.hardCase(HARD):
	assert world.where() == {VISION: None, CODER: None}  # the everyday model made room
	assert rt.inHardCase() and rt.entry(VISION) is HARD and rt.entry(CODER) is HARD and rt.oneModel()
	rt.ensure(CODER)
	assert world.where()[VISION] == "Vulkan0" and rt.engines[VISION].modelPath == "hard.gguf"
	assert rt.engines[VISION].args[-1][:2] == ["-ngl", "auto"]
	# Another thread, such as a description asked for meanwhile, still has the everyday model.
	other = threading.Thread(target=lambda: elsewhere.update(entry=rt.entry(VISION), hard=rt.inHardCase()))
	other.start()
	other.join()
assert elsewhere == {"entry": NINE, "hard": False}
assert world.where() == {VISION: None, CODER: None} and rt.entry(CODER) is NINE and not rt.inHardCase()
rt.ensure(VISION)
assert rt.engines[VISION].modelPath != "hard.gguf" and rt.engines[VISION].args[-1][:2] == ["-ngl", "99"]
# An error inside the hard case still ends it.
try:
	with rt.hardCase(HARD):
		rt.ensure(CODER)
		raise EngineError("lost")
except EngineError:
	pass
assert not rt.inHardCase() and rt.engines[VISION].modelPath != "hard.gguf" or not rt.engines[VISION].running

# 12. A split model that does not start on the card goes to the processor, and the card is not marked as broken: the
#     everyday models still use it.
world = World([DEDICATED], NINE, NINE, hard=HARD, broken=["Vulkan0"])
world.broken = {"Vulkan0"}
with world.runtime.hardCase(HARD):
	world.runtime.ensure(CODER)
	assert world.where()[VISION] == "none"
assert [backend.key(b) for b in world.runtime.chain()] == ["dedicated:Vulkan0", "cpu"]
print("OK")
