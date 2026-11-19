# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Nothing the user reads or hears is cut, and the user's own words are never cut (llm.uncut). Plain Python.

The owner said on 2026-11-19: "very long prompts are being cut off with ' ...[cut] ' and other similar cutoffs. You
must ensure the whole prompt is always displayed no matter how long." The answer before it, the add-ons installed,
had ended in "Pr ...[cut]." So: a tool's result is kept whole, every answer, question, step said and line of the log
is whole, and the request reaches every model and every tool whole. Only what a model reads of results, notes and
pages is trimmed for it (llm.clip), where the prompt is made.

  python tests/test_whole.py
"""
import os
import re
import tempfile

import harness  # noqa: F401
from test_core import FakeRuntime, makeRegistry, script
from visionClaw.claw import debuglog, llm, orchestrator, tools
from visionClaw.claw import task as taskModule

ADDON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "addon", "globalPlugins", "visionClaw")

# --- The code: llm.clip is never given the user's words, nor text the user is told ---

# What holds the user's own words in VisionClaw's code.
USER_WORDS = re.compile(
	r"\bclip\(\s*(request|part|asked|goal|purpose|clause|question|textToType|typed|piece\.action|step\.part|"
	r"task\.request|last\.request|_asked\(|bare\(|newThing\(|_clean\()")
# Where text is said or shown to the user, or asked of them.
TOLD = re.compile(r"\.emit\(|\bconfirm\(|\bmustAgree\(|\bclawAsk\(|\baskUser\(|\bToolError\(|\bquestion = |ui\.message\(")
# The user's words shortened by a slice.
SLICED = re.compile(r"\b(request|asked)\b[\w.()\" ]*\)?\[:\d+\]")
found = []
for folder, _dirs, names in os.walk(ADDON):
	if os.sep + "skills" in folder or os.sep + "knowledge" in folder or os.sep + "shipped" in folder:
		continue
	for name in names:
		if not name.endswith(".py"):
			continue
		path = os.path.join(folder, name)
		with open(path, encoding="utf-8") as f:
			for number, line in enumerate(f, 1):
				where = f"{os.path.relpath(path, ADDON)}:{number}: {line.strip()[:120]}"
				if USER_WORDS.search(line):
					found.append("the user's words clipped: " + where)
				if "clip(" in line and TOLD.search(line):
					found.append("clipped where the user is told: " + where)
				if SLICED.search(line):
					found.append("the user's words sliced: " + where)
				if "left out]" in line or ("[cut]" in line and name not in ("llm.py", "shapes.py")):
					found.append("a cut marker: " + where)
assert not found, "\n".join(found)

# --- llm.uncut and llm.clip ---
LONG = " ".join(f"word{number:04d}" for number in range(1200))
assert llm.uncut(LONG) == LONG and llm.uncut(None) == "" and llm.uncut("  a  ") == "a"
assert llm.clip(LONG, 100).endswith(llm.CUT) and llm.clip("short", 100) == "short"

# --- A tool: the user's words reach it whole, and what it gives back is kept whole ---
said = []
tool = tools.Tool("echo", "say it back", lambda task, asked: said.append(asked) or "Heard: " + asked,
	{"asked": {"type": "string", "description": "what the user asked, in their own words", "maxLength": 300, "auto": True}})
assert tool.autoForm(LONG) == {"asked": LONG}
registry = tools.Registry()
registry.add(tool)


def tooLong(task):
	raise tools.ToolError("No such thing. " + LONG)


registry.add(tools.Tool("fails", "fails with a long message", tooLong))
worked, result = registry.call(None, "echo", {"asked": LONG})
assert worked and result == "Heard: " + LONG and llm.CUT not in result, result[-80:]
worked, result = registry.call(None, "fails", {})
assert not worked and result.endswith(LONG), result[-80:]

# --- The log keeps every entry whole ---
folder = tempfile.mkdtemp(prefix="vc-whole-")
debuglog.start(folder, debuglog.DETAILED)
debuglog.log("test", "A prompt: " + LONG * 4)
assert ("A prompt: " + LONG * 4) in debuglog.tail(2) and "left out" not in debuglog.tail(2)
debuglog.stop()

# --- A whole request: a very long request and a very long result ---
# One long sentence with nothing that splits it, as a person might dictate it.
REQUEST = "describe what the screen shows around the names " + " ".join(f"name{number:03d}" for number in range(300))
SEEN = "The screen shows " + "; ".join(f"item {number:03d} with a long description of its own" for number in range(120)) + "."
asked = []


def askUser(question, options):
	asked.append((question, options))
	return None


heard = []
registry = makeRegistry({})
registry.add(tools.Tool("look", "look at the screen with the vision model", lambda task, target, question: heard.append(question) or SEEN, {
	"target": {"type": "string", "description": "what to look at", "enum": ["window", "screen"], "auto": lambda part: "screen"},
	"question": {"type": "string", "description": "what to find out", "maxLength": 200, "auto": True},
}, looks=True, title="Looking at the screen", tell=tools.VERBATIM))
runtime = FakeRuntime(script(choices=["describe"]))
task = taskModule.Task(REQUEST)
orchestrator.Orchestrator(runtime, registry, askUser, lambda: "Program: notepad.", None).run(task)
assert task.state == taskModule.DONE, (task.state, task.log[-3:])
# The tool was given the user's words whole.
assert heard and REQUEST in heard[0], heard
# The model that chose the job read the request whole.
assert any(REQUEST in user for _role, _system, user in runtime.calls), [user[:200] for _r, _s, user in runtime.calls]
# The answer holds all that was found, and nothing the user could read or hear is cut.
assert SEEN in task.answer and llm.CUT.strip() not in task.answer, task.answer[-120:]
for _seconds, kind, text in task.log:
	assert llm.CUT.strip() not in text and "left out" not in text, (kind, text[-120:])
assert any(kind == taskModule.DETAIL and text == "Result: " + SEEN for _seconds, kind, text in task.log), "the step's result was cut"
assert not asked, asked

print("test_whole: OK")
