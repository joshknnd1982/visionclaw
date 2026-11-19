# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""tests/eval_routing.py with a small model's choices voted on or not (claw/llm.py, policy.votes), to measure what the
votes do on the same set with the same model. Nothing is carried out.

  VC_VOTES=0 python -u tests/eval_votes.py MODELS [reasoning] [visionId] [coderId] [stepwise] [label]

VC_VOTES=0 turns the votes off; anything else, or nothing, leaves them on. VC_SET picks the set, as in eval_routing.py.
VC_CHIP=Vulkan1 runs the model only on that graphics chip (or the processor), never on another: so that a measurement
can run on a built-in chip while the dedicated card is busy with something else.
"""
import os
import runpy
import sys

import harness  # noqa: F401
from visionClaw.claw import backend, policy, runtime

policy.VOTING = os.environ.get("VC_VOTES", "1") != "0"
print(f"Votes for small models: {'on' if policy.VOTING else 'off'}", flush=True)
CHIP = os.environ.get("VC_CHIP")
if CHIP:
	def _onlyChip(self):
		devices = [device for device in self.devices() if device.id == CHIP]
		return [backend.Backend(backend.VULKAN, device) for device in devices] + [backend.Backend(backend.CPU, None)]
	runtime.ModelRuntime.chain = _onlyChip
	print(f"Only on the graphics chip {CHIP}, else the processor.", flush=True)
sys.argv = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_routing.py")] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
