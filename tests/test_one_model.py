# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""One model chosen for both jobs, vision and code. There are then not two models that could agree, and the
user must never be told that there are: the model chooses once, checks a plan it wrote itself, and every
sentence says "the model". With two different models nothing changes.

The scripted models, the tools and the forms are those of test_core.py, which runs again when it is imported
here."""
import re
import tempfile

import harness  # noqa: F401
from test_core import BAD, GOOD, FakeRuntime, makeRegistry, script
from visionClaw.claw import catalog, microaddons, orchestrator, policy, runtime, working
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION

# --- Whether one model does both jobs, from the real catalog's entries ---

real = catalog.Catalog(tempfile.mkdtemp())
nine, nineForCode = real.get("qwen3.5-9b"), real.get("qwen3.5-9b-coder")
assert nine["role"] == VISION and nineForCode["role"] == CODER
# The same model file, so one engine serves both.
assert real.paths(nine)[0] == real.paths(nineForCode)[0]
anotherCoder = next(entry for entry in real.entries(CODER) if entry["dir"] != nine["dir"])


def runtimeWith(vision, coder):
	chosen = {VISION: vision, CODER: coder}
	stand = type("Catalog", (), {
		"selected": lambda self, role, preferred=None: chosen[role],
		"paths": lambda self, entry: real.paths(entry),
	})()
	return runtime.ModelRuntime("engine", stand, lambda: {})


assert runtimeWith(nine, nineForCode).oneModel() and policy.isOneModel(runtimeWith(nine, nineForCode))
assert not runtimeWith(nine, anotherCoder).oneModel()
# A model that is missing is not "one model for both".
assert not runtimeWith(nine, None).oneModel() and not runtimeWith(None, nineForCode).oneModel()
# A runtime that cannot say has two models, as before.
assert not policy.isOneModel(object())
assert policy.roleName(CODER) == "coder model" and policy.roleName(VISION) == "vision model"
assert policy.roleName(CODER, True) == "model" and policy.roleName(VISION, True) == "model"
assert policy.select({"complexity": "simple"}).oneModel is False

# --- Whole requests with one model ---


class OneRuntime(FakeRuntime):
	def oneModel(self):
		return True


# Words that would tell the user of two models, or of an agreement between them.
TWO = re.compile(r"\bmodels\b|agree|\b(vision|coder|other|another|reviewing|second) model", re.IGNORECASE)


def run(request="Make NVDA talk faster", userChoices=(), reasoning="auto", **scripted):
	state, asked = {}, []
	userChoices = list(userChoices)

	def askUser(question, options):
		asked.append((question, options))
		return userChoices.pop(0) if userChoices else None

	rt = OneRuntime(script(**scripted))
	task = taskModule.Task(request, reasoning=reasoning)
	orchestrator.Orchestrator(rt, makeRegistry(state), askUser, lambda: "Program: notepad.").run(task)
	# Nothing the user hears or is asked speaks of two models.
	for _time, kind, text in task.log:
		assert not TWO.search(text), (kind, text)
	for question, options in asked:
		for text in [question] + list(options):
			assert not TWO.search(text), text
	return task, state, asked, rt


def said(task, words, kind=None):
	return any(words in logged for _t, k, logged in task.log if kind in (None, k))


def choosing(rt):
	return [role for role, system, _u in rt.calls if system.startswith("You choose how")]


# 1. A request that fits a recipe: the model chooses once. Asked again it would say the same, so the second
#    question is not put, and nothing is called an agreement. What the coder role would have chosen does not
#    matter: it is the same model.
task, state, asked, rt = run(forms=[GOOD], otherChoices=["explain_keys"])
assert task.state == taskModule.DONE and state["rate"] == 70 and not asked, task.log
assert task.answer == "Speech rate was 50 and is now 70."
assert choosing(rt) == [VISION], choosing(rt)
assert said(task, "The model is choosing what to do.", taskModule.STATE)
assert said(task, "\"Make NVDA talk faster\": the model chose to change an NVDA setting.", taskModule.TALK)
assert said(task, "The steps:\n", taskModule.TALK)
assert said(task, "The plan is ready: 3 steps.", taskModule.STATE)
assert said(task, "One model does both jobs", taskModule.DETAIL)
assert task.params.oneModel is True

# 2. Two parts: one choice for each part.
task, state, asked, rt = run(
	"Make NVDA talk faster and then tell me what is on my screen", forms=[GOOD],
	parts=["Make NVDA talk faster", "Tell me what is on my screen"], choices=["change_setting", "describe"])
assert task.state == taskModule.DONE and [s.tool for s in task.steps] == ["find_setting", "set_setting", "look", "answer"]
assert choosing(rt) == [VISION, VISION]

# 3. A step that stays stuck: the model looks at it in another way. That is not called another model's hint.
task, state, asked, rt = run(forms=[BAD, BAD, GOOD])
assert task.state == taskModule.DONE and state["rate"] == 70, task.log
assert said(task, "The model is stuck and looks at the step in another way.")
assert said(task, "What the model came up with: Use the id speech.rate exactly.")

# 4. A part that fits no recipe: the model writes a plan and checks it itself, and checks the result.
free = {"steps": [{"tool": "set_setting", "detail": "set the speech rate to 70"}, {"tool": "nonsense", "detail": "x"}]}
task, state, asked, rt = run("Do something unusual with the speech", forms=[{"words": "speech rate"}, GOOD],
	choices=["other"], free=free, reasoning="low")
assert task.state == taskModule.DONE and state["rate"] == 70 and not asked, task.log
assert said(task, "Plan for \"Do something unusual with the speech\":")
assert said(task, "The model checked its plan and found no problem.")
assert said(task, "The model checked the result: complete.")
assert said(task, "The plan is ready", taskModule.STATE)

# 4b. It finds a problem in its plan once, and none in the new one.
task, state, asked, rt = run("Do something unusual with the speech", forms=[{"words": "speech rate"}, GOOD],
	choices=["other"], free=free, reviews=[{"agree": False, "problem": "The setting must be found first."}])
assert task.state == taskModule.DONE and not asked, task.log
assert said(task, "The model checked its plan and found a problem: The setting must be found first.")
assert said(task, "The model checked the new plan and found no problem.")
assert said(task, "The model corrected its plan", taskModule.STATE)

# 4c. It keeps finding a problem: the user decides, and is told that the model is not sure, not that two
#     models differ. Here the user cancels, and nothing is changed.
no = {"agree": False, "problem": "This changes the wrong setting."}
task, state, asked, rt = run("Do something unusual with the speech", choices=["other"], free=free, reviews=[no, no],
	userChoices=[None])
assert task.state == taskModule.CANCELLED and "rate" not in state, task.log
question, options = asked[0]
assert question.startswith("The model is not sure how to do this: \"Do something unusual with the speech\".")
assert "wrong setting" in question and options[0].startswith("Use the new plan: ") and options[-1].startswith("Cancel.")
assert said(task, "The model is not sure of its plan. Waiting for your choice.", taskModule.STATE)

# 4d. The user chooses the plan, and it runs.
task, state, asked, rt = run("Do something unusual with the speech", forms=[{"words": "speech rate"}, GOOD],
	choices=["other"], free=free, reviews=[no, no], userChoices=[0])
assert task.state == taskModule.DONE and state["rate"] == 70, task.log
assert said(task, "Using the plan you chose", taskModule.STATE)

# --- The one model's choice is checked against the user's own words ---

# 5. The words point to another choice than the model made: it is told which, looks again, and takes it.
task, state, asked, rt = run("How do I read the window title?", choices=["describe", "explain_keys"])
assert task.state == taskModule.DONE and not asked, task.log
assert [s.tool for s in task.steps] == ["find_command", "answer"] and "looked" not in state
assert choosing(rt) == [VISION, VISION]
assert any("The user's words point to: explain_keys (tell you which keys to use). You chose describe." in user
	for _r, system, user in rt.calls if system.startswith("You choose how"))
assert said(task, "After checking against your words, the model chose to tell you which keys to use.")
assert said(task, "The model corrected its plan", taskModule.STATE)

# 5b. It keeps its own choice: then the user decides, as when two models differ. The words' reading comes
#     first, and nothing is said of two models.
task, state, asked, rt = run("How do I read the window title?", choices=["describe"], userChoices=[0])
assert task.state == taskModule.DONE and [s.tool for s in task.steps] == ["find_command", "answer"], task.log
question, options = asked[0]
assert question == "VisionClaw is not sure what you mean by \"How do I read the window title?\". What should it do?"
assert options == ["Tell you which keys to use.", "Look at the screen and describe it.", "Cancel. I will ask in a different way."]
assert said(task, "Your words could also mean: tell you which keys to use. The model looked again and still chose to "
	"look at the screen and describe it.")
assert said(task, "Not sure what you mean. Waiting for your choice.", taskModule.STATE)
assert said(task, "Using the plan you chose", taskModule.STATE)

# 5c. The user takes the model's choice instead.
task, state, asked, rt = run("How do I read the window title?", choices=["describe"], userChoices=[1])
assert task.state == taskModule.DONE and [s.tool for s in task.steps] == ["look", "answer"] and "looked" in state

# 5d. The user cancels: nothing is done.
task, state, asked, rt = run("How do I read the window title?", choices=["describe"], userChoices=[2])
assert task.state == taskModule.CANCELLED and "looked" not in state and len(asked) == 1

# 5e. Words that point nowhere, or to what the model chose, cost no second question.
task, state, asked, rt = run("How do I read the window title?", choices=["explain_keys"])
assert task.state == taskModule.DONE and choosing(rt) == [VISION] and not asked

# 6. Two parts answered by the same look are said once, not twice.
task, state, asked, rt = run(
	"Tell me what is on my screen and describe the screen",
	parts=["Tell me what is on my screen", "Describe the screen"], choices=["describe"])
assert task.state == taskModule.DONE and [s.tool for s in task.steps] == ["look", "look", "answer"], task.log
assert task.answer == "The screen shows a game menu with four buttons.", task.answer

# --- Which models VisionClaw has and uses: plain code answers, from the settings and the disk ---


def about(vision, coder, stored, loaded=False):
	chosen = {VISION: vision, CODER: coder}
	stand = type("Catalog", (), {
		"selected": lambda self, role, preferred=None: chosen[role],
		"paths": lambda self, entry: real.paths(entry),
		"stored": lambda self: stored,
	})()
	rt = runtime.ModelRuntime("engine", stand, lambda: {})
	if loaded:
		rt.engines[VISION] = type("Engine", (), {"running": True})()
		rt.backends[VISION] = runtime.backend.Backend(runtime.backend.CPU, None)
	return rt.aboutText()


nineStored = {"key": "qwen3.5-9b", "name": "Qwen3.5 9B", "bytes": 6598688544, "roles": ["vision", "coder"],
	"ids": ["qwen3.5-9b", "qwen3.5-9b-coder"], "partial": False}
text = about(nine, nineForCode, [nineStored])
assert text == (
	"VisionClaw uses one model, Qwen3.5 9B, for both jobs: looking at the screen and planning, and checking and "
	"writing code. One model is stored on this computer: Qwen3.5 9B, 6.1 GB. No model is loaded at the moment. "
	"A model is loaded when it is needed."), text
assert not TWO.search(text.replace("No model is", "")), text
assert "One model does both jobs and runs on the processor." in about(nine, nineForCode, [nineStored], loaded=True)
otherStored = {"key": anotherCoder["dir"], "name": anotherCoder["name"], "bytes": 2 ** 30, "roles": ["coder"],
	"ids": [anotherCoder["id"]], "partial": False}
half = dict(otherStored, name="Half a model", partial=True)
text = about(nine, anotherCoder, [nineStored, otherStored, half])
assert text.startswith(
	"For looking at the screen and planning, VisionClaw uses the model Qwen3.5 9B. For checking and writing code, "
	f"it uses the model {anotherCoder['name']}. 2 models are stored on this computer: Qwen3.5 9B, 6.1 GB; "
	f"{anotherCoder['name']}, 1.0 GB. A download was not finished: Half a model."), text
text = about(None, None, [])
assert text == (
	"No model is chosen yet for looking at the screen and planning. No model is chosen yet for checking and "
	"writing code. No model is stored on this computer yet."), text

# --- With two different models nothing changes ---

rt = FakeRuntime(script(forms=[GOOD]))
task = taskModule.Task("Make NVDA talk faster")
orchestrator.Orchestrator(rt, makeRegistry({}), lambda q, c: None).run(task)
assert task.state == taskModule.DONE and task.params.oneModel is False
assert said(task, "The two models are agreeing on what to do.", taskModule.STATE)
assert said(task, "Both models agree on the plan", taskModule.STATE) and said(task, "The agreed steps:")
assert sorted(choosing(rt)) == sorted([VISION, CODER])
assert not said(task, "One model does both jobs")

# --- How a control is worked: one model asked about the picture and about what is reported ---

assert working.settle(working.CLICK, working.CLICK, True) == (
	working.CLICK, True, "the model, from the picture and from what is reported")
assert working.settle(working.AROUND, working.UPDOWN, True) == (
	working.AROUND, True, "the model, from the picture and from what is reported")
assert working.settle(working.AROUND, working.CLICK, True) == (
	working.AROUND, False, "the model, from the picture; from what is reported it says click")
assert working.settle(working.AROUND, None, True) == (working.AROUND, False, "the model, from the picture")
assert working.settle(None, working.TYPE, True) == (working.TYPE, False, "the model, from what is reported")
assert working.settle(working.UNSURE, None, True) == (working.UNSURE, False, "the model")

# --- Writing an add-on: the model reads its own code again; that is not called a reviewing model ---


class FakeLLM:
	def __init__(self, texts, verdicts):
		self.texts, self.verdicts = list(texts), list(verdicts)

	def text(self, role, system, user, **options):
		return self.texts.pop(0)

	def json(self, role, system, user, schema, **options):
		return self.verdicts.pop(0)


code = ("```python\nimport globalPluginHandler\nimport ui\n\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n"
	"\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message('link')\n\t\tnextHandler()\n```")
purpose = "say link when a link gets the focus, anywhere"
two = policy.select({"complexity": "complex", "needs_code": True})
one = two._replace(oneModel=True)

task = taskModule.Task("write an add-on")
microaddons.write(FakeLLM([code], [{"ok": True, "problem": ""}]), task, purpose, "", "", one, CODER, VISION)
assert said(task, "The model is writing the add-on.") and said(task, "The model read its own code again: no fault found.")
task = taskModule.Task("write an add-on")
doubt = {"ok": False, "problem": "It might be too loud."}
microaddons.write(FakeLLM([code] * 10, [doubt, doubt]), task, purpose, "", "", one, CODER, VISION)
assert said(task, "The model read its own code again and found a fault: It might be too loud.")
assert task.codeDoubt == "It might be too loud."
assert not any(TWO.search(text) for _t, _k, text in task.log), task.log
# Two models: as before.
task = taskModule.Task("write an add-on")
microaddons.write(FakeLLM([code], [{"ok": True, "problem": ""}]), task, purpose, "", "", two, CODER, VISION)
assert said(task, "The coder model is writing the add-on.") and said(task, "The reviewing model checked the code: no fault found.")
print("OK")
