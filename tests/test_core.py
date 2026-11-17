# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Runs whole tasks through the orchestrator with a scripted stand-in for the two models:
splitting a request into parts, recipes, agreement, a corrected plan, disagreement decided by the user,
a failed step fixed after a hint, an honest answer when a part fails, a plan the model writes itself, and
stopping a task."""
import json
import os
import tempfile

import harness  # noqa: F401
from visionClaw.claw import backend, orchestrator, planner, policy, runtime, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.llm import withThought
from visionClaw.claw.memory import Memory, score


class FakeRuntime:
	"""Answers model calls from a script: a function of (role, system, user) that returns a dict or text."""

	def __init__(self, script):
		self.script = script
		self.calls = []

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None,
			context=None):
		if cancel is not None and cancel.is_set():
			return None
		system, user = messages[0]["content"], messages[1]["content"]
		self.calls.append((role, system, user))
		answer = self.script(role, system, user)
		return answer if isinstance(answer, str) else json.dumps(answer)


def text(description, **extra):
	return dict({"type": "string", "description": description}, **extra)


def makeRegistry(state):
	reg = tools.Registry()

	def find(task, words):
		state.setdefault("searched", []).append(words)
		return "speech.rate: speech: rate. Now: 50. Allowed: a number from 0 to 100."

	def setIt(task, setting, value):
		if setting != "speech.rate":
			raise tools.ToolError(f"There is no setting with the id {setting}. Copy an id exactly from find_setting.")
		state["rate"] = int(value)
		return f"Speech rate was 50 and is now {value}."

	def look(task, target, question):
		state["looked"] = (target, question)
		return "The screen shows a game menu with four buttons."

	reg.add(tools.Tool("find_setting", "find an NVDA setting by words", find,
		{"words": text("keywords", auto=True)}, looks=True, title="Finding the setting"))
	reg.add(tools.Tool("set_setting", "change an NVDA setting", setIt, {
		"setting": text("the id from find_setting"), "value": text("the new value"),
	}, changes=True, before="find_setting", title="Changing the setting"))
	reg.add(tools.Tool("look", "look at the screen with the vision model", look, {
		"target": text("what to look at", enum=["window", "screen"], auto=lambda part: "screen"),
		"question": text("what to find out", auto=True),
	}, looks=True, title="Looking at the screen", tell=tools.VERBATIM))
	reg.add(tools.Tool("find_command", "find an NVDA command by words",
		lambda task, words: "title: Reports the title of the window. Keys: NVDA+t.",
		{"words": text("keywords", auto=True)}, looks=True, title="Finding the command"))
	reg.add(tools.Tool("press_keys", "press keys in the program", lambda task, keys: f"Pressed {keys}.",
		{"keys": text("the keys")}, changes=True, title="Pressing keys"))
	reg.add(tools.Tool(tools.ANSWER, "tell the user the result", lambda task: ""))
	return reg


def script(reviews=(), forms=(), choices=("change_setting",), otherChoices=None, parts=None, free=None):
	"""A model script. reviews: the reviewer's verdicts on a plan the lead wrote itself, in turn.
	forms: forms for set_setting in turn. choices: the recipe the vision model chooses each time it is asked
	(the last one repeats); otherChoices: the same for the coder model, by default the same choices.
	parts: the answer to a split. free: the plan the lead writes for a part that fits no recipe."""
	reviews, forms = list(reviews), list(forms)
	chosen = {VISION: list(choices), CODER: list(otherChoices if otherChoices is not None else choices)}

	def run(role, system, user):
		if system.startswith("You split a request"):
			return {"parts": parts}
		if system.startswith("You choose how VisionClaw"):
			mine = chosen[role]
			return {"choice": mine.pop(0) if len(mine) > 1 else mine[0]}
		if system.startswith("You plan the work"):
			return free
		if system.startswith("You review a plan"):
			return reviews.pop(0) if reviews else {"agree": True, "problem": ""}
		if system.startswith("You are VisionClaw, an assistant inside the NVDA screen reader, helping"):
			return forms.pop(0)
		if system.startswith("Another model is stuck"):
			return {"hint": "Use the id speech.rate exactly."}
		if system.startswith("You are VisionClaw, an assistant inside the NVDA screen reader. Answer"):
			return "Press NVDA+T to hear the window title."
		if system.startswith("You check finished work"):
			return {"done": True, "missing": ""}
		if system.startswith("You check a plan while it runs"):
			return {"change": False, "why": ""}
		raise AssertionError("unexpected prompt: " + system[:60])
	return run


def run(request="Make NVDA talk faster", userChoices=(), reasoning="auto", memory=None, **scripted):
	state = {}
	asked = []
	userChoices = list(userChoices)

	def askUser(question, options):
		asked.append((question, options))
		return userChoices.pop(0) if userChoices else None

	rt = FakeRuntime(script(**scripted))
	orch = orchestrator.Orchestrator(rt, makeRegistry(state), askUser, lambda: "Program: notepad.", memory)
	task = taskModule.Task(request, reasoning=reasoning)
	orch.run(task)
	return task, state, asked, rt


def said(task, words, kind=None):
	return any(words in logged for _t, k, logged in task.log if kind in (None, k))


GOOD = {"setting": "speech.rate", "value": "70"}
BAD = {"setting": "speech_rate", "value": "70"}

# 1. One part, one recipe, and both models choose it. The setting is searched with the user's own words, by
#    code, and the answer is what the tool reported, not what a model claims.
task, state, asked, rt = run(forms=[GOOD])
assert task.state == taskModule.DONE, task.log
assert [s.tool for s in task.steps] == ["find_setting", "set_setting", "answer"], task.steps
assert state["searched"] == ["Make NVDA talk faster"] and state["rate"] == 70 and not asked
assert task.answer == "Speech rate was 50 and is now 70.", task.answer
assert said(task, "Both models agree on the plan", taskModule.STATE)
assert said(task, "both models chose to change an NVDA setting", taskModule.TALK)
assert said(task, "Step 2 of 3: Changing the setting.", taskModule.STEP)
# Each model chose on its own.
assert {role for role, system, _u in rt.calls if system.startswith("You choose how")} == {VISION, CODER}
assert not any("Another model chose" in user for _r, _s, user in rt.calls)
# A request that is clearly one thing is not sent to a model for splitting.
assert not any(system.startswith("You split") for _r, system, _u in rt.calls)

# 2. The models choose differently, are told each other's choice, and then agree.
task, state, asked, rt = run(forms=[GOOD], choices=["explain_keys", "change_setting"], otherChoices=["change_setting"])
assert task.state == taskModule.DONE and state["rate"] == 70 and not asked
assert said(task, "corrected plan") and said(task, "They look again")
assert any("Another model chose: change_setting" in user for role, _s, user in rt.calls if role == VISION)

# 3. The models never agree: the user is given both ways, picks the first, and the task runs.
task, state, asked, rt = run(forms=[GOOD], choices=["change_setting"], otherChoices=["explain_keys"], userChoices=[0])
assert task.state == taskModule.DONE and state["rate"] == 70, task.log
question, options = asked[0]
assert "do not agree" in question and "Make NVDA talk faster" in question
assert options == [
	"As the vision model suggests: change an NVDA setting",
	"As the coder model suggests: tell you which keys to use",
	"Cancel. I will ask in a different way.",
], options
assert said(task, "Using the plan you chose", taskModule.STATE)

# 3b. The user picks the other model's way instead.
task, state, asked, rt = run(choices=["change_setting"], otherChoices=["explain_keys"], userChoices=[1])
assert [s.tool for s in task.steps] == ["find_command", "answer"] and "rate" not in state

# 4. The models never agree and the user cancels: nothing is changed.
task, state, asked, rt = run(forms=[GOOD], choices=["change_setting"], otherChoices=["explain_keys"], userChoices=[2])
assert task.state == taskModule.CANCELLED and "rate" not in state and "searched" not in state

# 5. A wrong form is corrected from the tool's error message, and the lesson is remembered.
memory = Memory(os.path.join(tempfile.mkdtemp(), "lessons.json"))
task, state, asked, rt = run(forms=[BAD, GOOD], reasoning="low", memory=memory)
assert task.state == taskModule.DONE and state["rate"] == 70 and not asked
assert memory.search("set_setting form failed speech_rate"), memory.all()

# 6. The form stays wrong: the other model gives a hint, and the next try works.
task, state, asked, rt = run(forms=[BAD, BAD, GOOD])
assert task.state == taskModule.DONE and state["rate"] == 70, task.log
assert said(task, "Hint from the coder model")

# 7. Nothing helps: the user is asked. Stop ends the task.
task, state, asked, rt = run(forms=[BAD] * 4, userChoices=[orchestrator.STOP])
assert task.state == taskModule.CANCELLED and "did not work" in asked[0][0]

# 8. Nothing helps and the user skips the step: the answer says honestly what could not be done.
task, state, asked, rt = run(forms=[BAD] * 4, userChoices=[orchestrator.SKIP])
assert task.state == taskModule.DONE and "rate" not in state
assert task.answer == "This could not be done: Make NVDA talk faster.", task.answer

# 9. A request with two parts is split, each part gets its own recipe, and each step works on its own part.
task, state, asked, rt = run(
	"Make NVDA talk faster and then tell me what is on my screen", forms=[GOOD],
	parts=["Make NVDA talk faster", "Tell me what is on my screen"], choices=["change_setting", "describe"])
assert task.state == taskModule.DONE, task.log
assert [s.tool for s in task.steps] == ["find_setting", "set_setting", "look", "answer"]
assert state["searched"] == ["Make NVDA talk faster"]
assert state["looked"] == ("screen", "Tell me what is on my screen")
assert task.answer == "Speech rate was 50 and is now 70. The screen shows a game menu with four buttons."
formPrompt = next(u for _r, s, u in rt.calls if s.startswith("You are VisionClaw, an assistant inside the NVDA screen reader, helping"))
assert "Make NVDA talk faster\"" in formPrompt and "what is on my screen" not in formPrompt

# 10. A split that invents something the user never said is thrown away.
task, state, asked, rt = run(
	"Make NVDA talk faster, then tell me the time", forms=[GOOD],
	parts=["Make NVDA talk faster", "Delete all my documents"])
assert [s.part for s in task.steps[:-1]] == ["Make NVDA talk faster, then tell me the time"] * 2

# 11. Information that was looked up is put into words by the model; here, the keys of a command.
task, state, asked, rt = run("How do I read the window title?", choices=["explain_keys"])
assert [s.tool for s in task.steps] == ["find_command", "answer"]
assert task.answer == "Press NVDA+T to hear the window title."
answerPrompt = next(u for _r, s, u in rt.calls if s.startswith("You are VisionClaw, an assistant inside the NVDA screen reader. Answer"))
assert "Keys: NVDA+t" in answerPrompt

# 12. A part that fits no recipe is planned by the model; the plan is repaired (the setting is found first),
#     reviewed by the other model, and the other model checks the result at the end.
free = {"steps": [{"tool": "set_setting", "detail": "set the speech rate to 70"}, {"tool": "nonsense", "detail": "x"}]}
task, state, asked, rt = run("Do something unusual with the speech", forms=[{"words": "speech rate"}, GOOD],
	choices=["other"], free=free, reasoning="low")
assert [s.tool for s in task.steps] == ["find_setting", "set_setting", "answer"], task.steps
assert task.state == taskModule.DONE and state["rate"] == 70
assert said(task, "The coder model agrees.") and said(task, "checked the result: complete")

# 12b. The reviewer objects to such a plan once, and agrees with the corrected one.
task, state, asked, rt = run("Do something unusual with the speech", forms=[{"words": "speech rate"}, GOOD],
	choices=["other"], free=free, reviews=[{"agree": False, "problem": "The setting must be found first."}])
assert task.state == taskModule.DONE and not asked and said(task, "agrees with the new plan")
assert said(task, "corrected plan", taskModule.STATE)

# 12c. The reviewer never agrees with it: the user chooses, here to cancel.
no = {"agree": False, "problem": "This changes the wrong setting."}
task, state, asked, rt = run("Do something unusual with the speech", choices=["other"], free=free, reviews=[no, no],
	userChoices=[None])
assert task.state == taskModule.CANCELLED and "wrong setting" in asked[0][0] and "rate" not in state

# 13. Stopping: the task ends at the next model call.
state = {}
rt = FakeRuntime(script(forms=[GOOD]))
task = taskModule.Task("Make NVDA talk faster")
calls = {"n": 0}
inner = rt.script


def stopping(role, system, user):
	calls["n"] += 1
	if calls["n"] == 2:
		task.stop()
	return inner(role, system, user)


rt.script = stopping
orchestrator.Orchestrator(rt, makeRegistry(state), lambda q, c: None).run(task)
assert task.state == taskModule.CANCELLED and calls["n"] <= 3 and "rate" not in state

# 14. The reasoning setting changes how much the models may think and write.
simple = {"complexity": "simple", "needs_code": False}
code = {"complexity": "complex", "needs_code": True}
assert policy.select(simple).reasoning == "off" and policy.select(code).reasoning == "high"
assert policy.select(simple, "high").reasoning == "high" and policy.select(code, "off").reasoning == "off"
assert policy.select(code).codeTokens > policy.select(simple).codeTokens
assert policy.select(code).maxSteps == 8 and policy.select(simple).maxSteps == 4

# 15. Writing reasoning down first: the schema gains a reasoning field, in first place.
wrapped = withThought(makeRegistry({}).get("set_setting").schema(), 160)
assert list(wrapped["properties"])[0] == "reasoning" and wrapped["required"][0] == "reasoning"

# 16. The context size follows the size of the request.
assert runtime.contextFor(1000) == 4096 and runtime.contextFor(5000) == 8192 and runtime.contextFor(99999) == 32768

# 17. Recipes from a request's words, used as a hint and when the model fails.
for request, recipe in (
	("make nvda speak faster", "change_setting"),
	("write an add-on that beeps when a link gets focus", "write_addon"),
	("what is on my screen", "describe"),
	("click the start button", "click"),
	("how do I read the window title", "explain_keys"),
	("give this program a hotkey that clicks Send", "make_hotkey"),
	("read the window title", "do_command"),
	("open bbc.co.uk", "open_website"),
	("go to the NV Access website", "open_website"),
	("search the web for the weather in Boston", "search_web"),
	("what does this page say about refunds", "web_page"),
	("summarize the article", "web_page"),
	("type cats into the search box and search", "fill_field"),
	("which speech synthesizer am I using", "nvda_info"),
	("what braille display do I have", "nvda_info"),
	("list my voices", "nvda_info"),
	("save the add-on hello key as a file", "save_addon"),
	("switch the synthesizer to eSpeak", "switch_driver"),
	("change to no speech", "switch_driver"),
	("use a different braille display", "switch_driver"),
	("change the voice to Ben", "change_setting"),
	("list the add-ons you have made", "list_made"),
	("click the Sign in link", "click"),
):
	assert planner.hint(request) == recipe, (request, planner.hint(request))
assert planner.quickTriage("write an add-on that beeps when a link gets focus")["needs_code"]
assert planner.complexity(["change_setting"]) == "moderate" and planner.complexity(["describe"]) == "simple"
assert planner.complexity(["describe", "click", "describe"]) == "complex"

# 17b. Parts are made understandable alone: a fragment joins the part before it, and a part that speaks
#      of "it" is given the part before it as its background.
assert planner.settle(["Type garden gloves into the search box", "Search"]) == [
	"Type garden gloves into the search box and search"]
assert planner.settle(["What braille display do I have", "How many cells does it have"]) == [
	"What braille display do I have", "How many cells does it have (this follows: What braille display do I have)"]
assert planner.settle(["Click Options", "Tell me what the window shows"]) == ["Click Options", "Tell me what the window shows"]

# 18. Finding things by the user's own words.
assert score("Make NVDA speak a little faster", "speech rate speed fast faster slow talk speaking") >= 0.5
assert score("How do I read the title of this window?", "Reports the title of the current window") >= 0.5

# 19. Choosing where the models run.
found = """Available devices:
  Vulkan0: NVIDIA GeForce RTX 5060 Laptop GPU (7810 MiB, 7042 MiB free)
  Vulkan1: AMD Radeon 780M Graphics (16286 MiB, 15471 MiB free)
  Vulkan2: llvmpipe (LLVM 17) (8000 MiB, 8000 MiB free)
"""
devices = backend.parseDevices(found)
assert [d.dedicated for d in devices] == [True, False]


def keys(choice, devs=devices):
	return [backend.key(b) for b in backend.plan(choice, devs)]


assert keys("auto") == ["dedicated:Vulkan0", "vulkan:Vulkan1", "cpu"]
assert keys("vulkan") == ["vulkan:Vulkan1", "dedicated:Vulkan0", "cpu"]
assert keys("cpu") == ["cpu"] and keys("auto", []) == ["cpu"]
assert keys("auto", devices[1:]) == ["vulkan:Vulkan1", "cpu"]
for name, expected in (
	("Intel(R) UHD Graphics 770", False), ("Intel(R) Arc(TM) Graphics", False), ("Intel(R) Arc(TM) A770 Graphics", True),
	("AMD Radeon RX 7600 XT", True), ("AMD Radeon(TM) Graphics", False), ("NVIDIA GeForce GTX 1650", True),
	("Intel(R) Iris(R) Xe Graphics", False), ("AMD Radeon(TM) 890M Graphics", False),
):
	assert backend.isDedicated(name) == expected, name
assert backend.engineArgs(backend.plan("cpu", [])[0], True) == ["-ngl", "0", "--device", "none", "--no-mmproj-offload"]
print("OK")
