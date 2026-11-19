# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The user's words understood the way a text adventure understands them (claw/understand.py), the user's own
words taught, listed and forgotten, a question about a picture asked in its pieces (claw/pictures.py), and whole
requests through the orchestrator with its work sheet. Plain Python, with scripted models.

  python tests/test_understand.py
"""
import os
import shutil
import tempfile

import harness  # noqa: F401
from test_core import FakeRuntime, makeRegistry, script
from visionClaw.claw import orchestrator, pictures, planner, understand
from visionClaw.claw import task as taskModule

grammar = understand.Grammar(None)
assert len(grammar.rules()) > 50, "VisionClaw's own lines must be read"


def read(text):
	return grammar.read(text).text


# --- VisionClaw's own lines ---

# Said for nothing, at the start or the end only.
assert read("Hey VisionClaw, could you please fire up notepad for me") == "could you please open notepad"
assert read("please describe this, thanks!") == "describe this!"
assert read("is the speech working well") == "is the speech working well"  # "well" is said for nothing only at the start
assert read("right click the file") == "right click the file"
# Ways of saying what to do, only where something to do begins.
assert read("kill the typing echo") == "turn off the typing echo"
assert read("give the Save button a click") == "click the Save button"
assert read("hit the button that says Next") == "click the Next button"
assert read("punch in control c") == "press control c" and read("hit enter") == "press enter"
assert read("key in hello there") == "type hello there"
assert read("google best pizza near me") == "search the web for best pizza near me"
assert read("take back that last change") == "undo that last change"
assert read("remind me what nvda+t does") == "what does nvda+t do"
assert read("close the dialog and then bring up the start menu") == "close the dialog and then open the start menu"
assert read("take a peek at the screen") == "look at the screen"
assert read("get rid of this window") == "close this window"
# Not where something to do begins: "fire up" in the middle of a sentence is not changed.
assert read("why does the fan fire up when I open nvda") == "why does the fan fire up when I open nvda"
# Words that mean the same, anywhere.
assert read("ugh, the voice is way too squeaky") == "the voice is pitched too high"
assert read("how full is the bin") == "how full is the recycle bin"
assert read("make the speech a bit quicker") == "make the speech a bit faster"
assert read("what's on screen") == "what's on the screen"
assert read("where'd my holiday pics go") == "find my holiday pictures"
# What must stay the user's own is never changed: text to type, quotes, names, searches, addresses, keys.
assert read("type I wanna go home") == "type I wanna go home"
assert read('say "gimme five"') == 'say "gimme five"'
assert read("name it kill switch") == "name it kill switch"
assert read("search the web for ur mom jokes") == "search the web for ur mom jokes"
assert read("go to u.com") == "go to u.com"
assert read("press control u") == "press control u"
# What is remembered, a skill, and a word taught keep the user's own words; only a greeting is taken away.
assert read("remember that I wanna short answers") == "remember that I wanna short answers"
assert read("hey visionclaw, remember that I wanna short answers") == "remember that I wanna short answers"
assert read("make a skill for when I wanna read recipes") == "make a skill for when I wanna read recipes"
# The user is told when the meaning of a word was changed, and not for a spelling or a greeting.
assert grammar.read("kill the typing echo").said and not grammar.read("gimme the time").said
assert not grammar.read("hey visionclaw, what time is it").said
assert understand.taken("turn off the typing echo") == "Understood as: turn off the typing echo."
assert "\"kill the typing echo\" as \"turn off the typing echo\"" in understand.changesText(grammar.read("kill the typing echo"))
# At least two words are always left, and a fault leaves the request as it was said.
assert read("please") == "please" and read("thanks so much") == "thanks so much"
assert grammar.read(None).text == ""

# What the planner's patterns make of it: casual words reach the job their plain words name.
for said, job in (("kill the typing echo", "change_setting"), ("give the save button a click", "click"),
		("punch in control c", "press_keys"), ("google how to bake bread", "search_web"), ("dump the bin", "empty_bin"),
		("take back that last change", "undo_change"), ("lock up the pc", "power")):
	assert planner.hint(read(said)) == job, (said, read(said), planner.hint(read(said)))

# --- A file of words ---

rules = understand.parse('## Ways to say what to do\n- "zap [x]" means "turn off [x]"\n## Not a section\n- "a" means "b"\n'
	'## Spellings\n- "a line without a meaning"\n- "thx" means "thanks"\n')
assert [(rule.phrases, rule.meant, rule.kind) for rule in rules] == [
	(["zap [x]"], "turn off [x]", understand.TO_DO), (["thx"], "thanks", understand.SPELLING)], rules

# --- The user's own words ---

folder = tempfile.mkdtemp()
try:
	mine = understand.Grammar(folder)
	assert mine.own() == []
	assert mine.teach("shh", "stop talking") is False
	assert mine.teach("tunes", "my music folder") is False
	assert mine.teach("Shh", "stop speech") is True  # the same word again replaces it
	assert mine.own() == [("tunes", "my music folder"), ("Shh", "stop speech")]
	text = open(os.path.join(folder, understand.OWN_NAME), encoding="utf-8").read()
	assert text.startswith("# Your own words") and '- "Shh" means "stop speech"' in text, text
	# They come first, and are understood anywhere, but never inside what is to be typed.
	assert mine.read("shh please").text == "stop speech" and mine.read("shh please").said
	assert mine.read("open tunes").text == "open my music folder"
	assert mine.read("type tunes").text == "type tunes"
	# A line the user writes into the file counts at once.
	with open(os.path.join(folder, understand.OWN_NAME), "a", encoding="utf-8") as f:
		f.write('- "brb" means "lock the computer"\n')
	os.utime(os.path.join(folder, understand.OWN_NAME), (1, 1))
	assert mine.read("brb").text == "lock the computer" and mine.read("brb now").text == "lock the computer now"
	# Forgetting one, and all.
	assert mine.forget("tunes") == [("tunes", "my music folder")] and mine.forget("nothing") == []
	assert mine.read("open tunes").text == "open tunes"
	assert len(mine.forget(None)) == 2 and mine.own() == []
	# What cannot be taught, said in a sentence.
	for said, meant in (("a", "b"), ("the", "stop"), ("x" * 70, "y"), ("same", "same"), ("word", "")):
		assert understand.refusal(understand.cleanSaid(said), understand.cleanMeant(meant)), (said, meant)
	try:
		mine.teach("it", "the window")
		raise AssertionError("an everyday word must not be taught")
	except ValueError as e:
		assert "nearly every request" in str(e)
	# Without a data folder nothing can be kept.
	try:
		understand.Grammar(None).teach("shh", "stop")
		raise AssertionError("no folder, nothing kept")
	except ValueError:
		pass
finally:
	shutil.rmtree(folder, ignore_errors=True)

# What the user's words ask of their own words.
assert understand.wishOf("when I say shh, I mean stop talking") == {"what": "teach", "said": "shh", "meant": "stop talking"}
assert understand.wishOf('understand "zap" as turn off') == {"what": "teach", "said": "zap", "meant": "turn off"}
assert understand.wishOf("by brb I mean lock the computer")["said"] == "brb"
assert understand.wishOf("from now on, tunes means my music folder")["meant"] == "my music folder"
assert understand.wishOf("forget the word shh") == {"what": "forget", "said": "shh"}
assert understand.wishOf("forget all the words I taught you") == {"what": "forget all"}
assert understand.wishOf("which words have I taught you") == {"what": "list"}
for said in ("forget everything you know about me", "what does this word mean", "I mean it", "remember that I mean well",
		"tell me what the word ubiquitous means"):
	assert understand.wishOf(said) is None, said
assert understand.actionOf("which words have I taught you") == "list" and understand.actionOf("x") == "teach"
# The planner sends them to their job by plain code, before memories, and never splits them at their comma.
assert planner.hint("when I say shh, I mean stop talking") == "teach_words"
assert planner.hint("forget the word shh") == "teach_words"
assert planner.hint("forget everything you know about me") == "forget_memory"
assert "teach_words" in planner._SURE and planner.plainSplit("when I say shh, I mean stop talking") in (None, ["when I say shh, I mean stop talking"])

# --- A question about a picture, in its pieces ---

assert pictures.pieces("what is in this photo, and is there any text in it") == [
	("describe", "what is in this photo"), ("text", "is there any text in it")]
assert pictures.pieces("how many buttons are there? which one is focused") == [
	("count", "how many buttons are there"), ("focus", "which one is focused")]
assert pictures.pieces("what colour is the car and who is driving it") == [("colour", "what colour is the car"), ("people", "who is driving it")]
for said, kind in (("is there a dog anywhere in this picture", "find"), ("what does the sign say", "text"),
		("describe this chart", "chart"), ("where is the OK button", "where"), ("what am I looking at", "describe"),
		("read the error message", "text"), ("does this photo have any people in it", "find")):
	assert pictures.pieces(said) == [(kind, said)], (said, pictures.pieces(said))
assert len(pictures.pieces("what is this? what is that? who is here? what colour is it? how many are there")) == pictures.MAX_PIECES
for kind, rule in pictures.RULES.items():
	# A rule is heard by the user as part of an answer: nothing in it may need sight, and it gives no example.
	assert not any(word in rule.lower() for word in ("look at", "as you can see", "for example", "such as the")), (kind, rule)
assert pictures.together([("what is it", "A dog.")]) == "A dog."
assert pictures.together([("what is it", "A dog."), ("is there text", "No.")]) == "What is it? A dog.\nIs there text? No."

# --- Whole requests through the orchestrator ---

GOOD = {"setting": "speech.rate", "value": "70"}


def run(request, folder=None, own=None, **scripted):
	state = {}
	rt = FakeRuntime(script(**scripted))
	orch = orchestrator.Orchestrator(rt, makeRegistry(state), lambda question, options: None, lambda: "Program: notepad.")
	orch.understanding = understand.Grammar(own)
	orch.workFolder = folder
	task = taskModule.Task(request)
	seen = {}

	original = orch._runSteps

	def watched(llm, task, request, params, start=0, stop=None):
		# The work sheet is a file while the request runs.
		seen["files"] = os.listdir(folder) if folder else []
		seen["sheet"] = task.sheet.text()
		return original(llm, task, request, params, start, stop)
	orch._runSteps = watched
	orch.run(task)
	return task, state, rt, seen


folder = tempfile.mkdtemp()
own = tempfile.mkdtemp()
try:
	# Casual words are understood as plain words; the user is told, and the setting's search gets the plain words.
	task, state, rt, seen = run("ugh, nvda talks way too slow, crank up the speed", folder, forms=[GOOD])
	assert task.state == taskModule.DONE, task.log
	assert task.answer.startswith("Understood as: nvda talks too slow, turn up the speed."), task.answer
	assert state["searched"] == ["nvda talks too slow, turn up the speed"], state
	# The work sheet was a file in the folder while the request ran, and is deleted now.
	assert len(seen["files"]) == 1 and seen["files"][0].startswith("request-"), seen
	assert "Understood as: \"nvda talks too slow, turn up the speed\"" in seen["sheet"], seen["sheet"]
	assert os.listdir(folder) == []
	# A greeting and a spelling are not said in the answer.
	task, state, rt, seen = run("hey visionclaw, make nvda talk faster please", folder, forms=[GOOD])
	assert not task.answer.startswith("Understood as") and state["searched"] == ["make nvda talk faster"], (task.answer, state)
	# The user's own words come first.
	understand.Grammar(own).teach("zippy", "speak faster")
	task, state, rt, seen = run("go zippy", folder, own=own, forms=[GOOD])
	assert task.answer.startswith("Understood as: go speak faster."), task.answer
	# A request that fails still has its work sheet deleted.
	task, state, rt, seen = run("make nvda talk faster", folder, forms=[{"setting": "nope", "value": "1"}] * 20)
	assert os.listdir(folder) == []
	# A step of the second part is not given what the first part found.
	task, state, rt, seen = run("make nvda talk faster. look at the screen", folder, forms=[GOOD],
		choices=["change_setting", "describe"])
	assert task.state == taskModule.DONE and [s.tool for s in task.steps] == ["find_setting", "set_setting", "look", "answer"], task.steps
	assert task.steps[2].given == [] and task.steps[1].given == [0], [getattr(s, "given", None) for s in task.steps]
finally:
	shutil.rmtree(folder, ignore_errors=True)
	shutil.rmtree(own, ignore_errors=True)
print("OK")
