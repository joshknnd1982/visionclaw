# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Runs two real engines side by side on two different backends of this computer.

Needs addon/engine (see BUILD.md) and VisionMate's vision data, which is loaded twice: once as the vision
model and once, under a second spelling of its path, as the coder model. The first graphics chip is reported
as full, so the second model has to find another place. Both must answer while both stay loaded.

  python tests/live_side_by_side.py
"""
import os
import sys
import time

import harness
from visionClaw.claw import backend, catalog, runtime
from visionClaw.claw.catalog import CODER, VISION


def main():
	folder = harness.visionMateData()
	if not folder:
		sys.exit("VisionMate's vision data is not on this computer.")
	core, vision = os.path.join(folder, "core.bin"), os.path.join(folder, "vision.bin")
	entries = {
		VISION: {"id": "v", "name": "vision", "memoryGb": 2.6, "maxContext": 16384},
		CODER: {"id": "c", "name": "coder", "memoryGb": 2.0, "maxContext": 32768},
	}
	# The same file under another spelling counts as another model, so it gets an engine of its own.
	paths = {"v": (core, vision), "c": (core.replace("\\", "/"), None)}
	models = type("Catalog", (), {
		"selected": lambda self, role, preferred=None: entries[role],
		"paths": lambda self, entry: paths[entry["id"]],
	})()
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, models, lambda: {"backend": "auto", "sideBySide": True})
	real = backend.listDevices(rt.engines[VISION].exe)
	print("graphics found:", [(d.id, d.name, d.dedicated) for d in real])
	chain = rt.chain()
	if len(chain) < 2:
		sys.exit("This computer has only one place to run a model.")
	first = chain[0]
	# Report the first place as full once a model is on it, as a large model would leave it.
	rt.devices = lambda refresh=False: [
		d._replace(freeMb=100) if first.device and d.id == first.device.id and rt.engines[VISION].running else d
		for d in real
	]
	ask = [{"role": "user", "content": "Reply with the single word: ready"}]
	try:
		start = time.time()
		print("vision:", repr(rt.chat(VISION, ask, 8)), "on", backend.describe(rt.backends[VISION]), f"{time.time() - start:.1f}s")
		start = time.time()
		print("coder: ", repr(rt.chat(CODER, ask, 8, raw=True)), "on", backend.describe(rt.backends[CODER]), f"{time.time() - start:.1f}s")
		assert rt.engines[VISION].running and rt.engines[CODER].running, "both models must stay loaded"
		assert backend.key(rt.backends[VISION]) != backend.key(rt.backends[CODER]), "they must be in different places"
		# Back and forth, as the agreement step does: nothing is loaded again, so every answer is quick.
		start = time.time()
		for _ in range(3):
			rt.chat(VISION, ask, 8)
			rt.chat(CODER, ask, 8, raw=True)
		print(f"six more answers, alternating: {time.time() - start:.1f}s")
		print(rt.whereText())
		print("OK")
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
