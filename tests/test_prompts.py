# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The instructions every answer and every description of a picture is given about the blind user
(claw/prompts.py): what they say, that the user's own wording and instructions are used, and that forms never
get the user's instructions. The scripted models of test_core.py run again when it is imported here."""
import re

import harness  # noqa: F401
from test_core import run
from visionClaw.claw import agent, orchestrator, prompts
from visionClaw.claw import task as taskModule
from visionClaw.engine import imageMessages

# --- What the parts say ---

for name in prompts.PARTS:
	text = prompts.DEFAULTS[name]
	# A small model copies an example as if it were the answer, so there is none.
	assert not re.search(r"\b(like|such as|for example|e\.g\.)\b", text, re.IGNORECASE), name
	# Nothing in them names a model's role: one model is never called two.
	assert not re.search(r"\b(both|two|other|vision|coder) models?\b|\bagree", text, re.IGNORECASE), name
	assert len(text) < 700, name
assert "blind" in prompts.USER and "braille" in prompts.USER
assert "Start with the answer" in prompts.SPEAKING and "Markdown" in prompts.SPEAKING
assert "exactly" in prompts.SEEING and "cannot be read" in prompts.SEEING and prompts.HONESTY in prompts.QUICK

# --- Putting them together ---

prompts.configure()
spoken = prompts.speaking("Do the task.")
assert spoken.startswith("Do the task.\n") and prompts.USER in spoken and prompts.SPEAKING in spoken
assert prompts.SEEING not in spoken
seen = prompts.seeing()
assert seen.startswith(prompts.IDENTITY) and prompts.SEEING in seen and prompts.SPEAKING in seen
assert "keep to this" not in seen and "Answer in" not in seen

prompts.configure({"speaking": "Answer in one sentence.\nBe kind"}, own="Call me Sam\nKeep it short", language="German")
assert prompts.isCustom("speaking") and not prompts.isCustom("user")
assert prompts.part("speaking") == "Answer in one sentence. Be kind."
spoken = prompts.speaking("Do the task.")
assert "Answer in one sentence. Be kind." in spoken and prompts.SPEAKING not in spoken
assert spoken.endswith("The user asks you to keep to this: Call me Sam. Keep it short.\nAnswer in German.")
assert "Call me Sam" in prompts.summary() and "German" in prompts.summary()

# VisionClaw's own wording given back is not a rewriting, so a newer VisionClaw's wording is used later.
prompts.configure({"user": prompts.USER, "seeing": "  "})
assert not prompts.isCustom("user") and not prompts.isCustom("seeing")
assert prompts.oneLine("a " * 400, prompts.OWN_CHARS).__len__() <= prompts.OWN_CHARS

# --- Pictures get them as the first message ---

assert imageMessages(b"x", "Describe.")[0]["role"] == "user"
started = imageMessages(b"x", "Describe.", "Rules.")
assert started[0] == {"role": "system", "content": "Rules."} and started[1]["role"] == "user"

# --- A whole request: the answer gets the user's instructions, a form never does ---

prompts.configure(own="Call me Sam")
assert agent._FORM_SYSTEM.startswith(prompts.IDENTITY) and orchestrator._JUDGE_SYSTEM.startswith(prompts.IDENTITY)
task, state, asked, rt = run("Make NVDA talk faster", forms=[{"setting": "speech.rate", "value": "70"}])
assert state.get("rate") == 70, task.log
assert rt.calls and not any("Call me Sam" in system for _role, system, _user in rt.calls)

task, state, asked, rt = run("What is the key for the window title?", choices=("explain_keys",))
answers = [system for _role, system, _user in rt.calls if "Answer the user from the information given" in system]
assert answers, [system[:60] for _role, system, _user in rt.calls]
assert all("Call me Sam" in system and prompts.USER in system and prompts.SPEAKING in system for system in answers)
assert not any("Call me Sam" in system for _role, system, _user in rt.calls if system not in answers)
prompts.configure()

# --- Add-ons written on the fly get them too ---

from visionClaw.claw import microaddons  # noqa: E402

prompts.configure(own="Call me Sam", language="German")
coded = prompts.coding(microaddons._SYSTEM)
assert coded.startswith("You write small add-ons") and prompts.USER in coded and prompts.ADDON in coded
assert prompts.SPEAKING not in coded and "Call me Sam" in coded
assert coded.endswith("Write what the add-on says to the user in German.")
# Every writing, repair and review of an add-on is sent with them.
systems = []


class RecordingLLM:
	def text(self, role, system, user, **kwargs):
		systems.append(system)
		return "```python\nimport globalPluginHandler\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\tpass\n```"

	def json(self, role, system, user, schema, **kwargs):
		systems.append(system)
		return {"ok": True, "problem": ""}


params = type("Params", (), {"codeTokens": 600, "reasoning": "off", "codeReviews": 1, "codeRepairs": 1})()
task = taskModule.Task("beep")
try:
	# The stand-in code does nothing, so the checks refuse it after its repair; what matters is what was sent.
	microaddons.write(RecordingLLM(), task, "beep when I press NVDA+shift+b", "", "", params, "coder", "vision")
except microaddons.ToolError:
	pass
microaddons.repair(RecordingLLM(), "coder", "beep", "x = 1\n", ["It does nothing."], params)
assert len(systems) >= 3
assert systems and all("Call me Sam" in s and prompts.ADDON in s for s in systems), systems
prompts.configure()

print("OK")
