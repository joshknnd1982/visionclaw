# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Skills, with plain Python: every skill that comes with VisionClaw is read and checked; skills are chosen
for requests by their words and not for others; the user's own skills are kept, take the place of a built-in
one, are turned off and on, deleted and taken in from a shared file; a skill's sentences reach the form, the
answer and the vision model's question; and a skill with steps runs them as its plan, with no model choosing."""
import json
import os
import re
import shutil
import tempfile

import harness  # noqa: F401
from visionClaw.claw import orchestrator, planner, skills, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.memory import wordList

RECIPES = set(planner.RECIPES)

# 1. Every built-in skill is read, has nothing wrong with it, and is short enough for a small model.
lib = skills.Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=RECIPES)
every = lib.all()
assert len(every) >= 30, len(every)
for skill in every:
	assert skill.source == skills.OURS and skill.on, skill
	assert not skills.check(skill, RECIPES), (skill.slug, skills.check(skill, RECIPES))
	assert skill.description and skill.uses and skill.when, skill.slug
	# A skill is read with a step's form; a long one would crowd out the step.
	assert len(skill.instructions) <= skills.GUIDE_CHARS, (skill.slug, len(skill.instructions))
	# A small model copies an example as if it were the answer, and Markdown is read out as noise.
	low = skill.instructions.lower()
	assert "for example" not in low and "e.g." not in low and "for instance" not in low, skill.slug
	assert not re.search(r"[*#`_]|^\s*-", skill.instructions, re.M), skill.slug
	# For a blind person: keys and words, never a colour or a look to find something by.
	assert not re.search(r"\b(blue|red|green) (button|link|icon)\b", low), skill.slug
	# Written and read back, a skill is the same skill.
	again = skills.parse(skills.toText(skill))
	assert (again.name, again.when, again.uses, again.steps, again.instructions) == (
		skill.name, skill.when, skill.uses, skill.steps, skill.instructions), skill.slug
assert len({skill.name for skill in every}) == len(every), "two skills have the same name"

# 2. Skills are chosen by their words, the best first; requests about something else get none.
CHOSEN = {
	"Describe this photo my friend sent": "describe-photo",
	"What does this chart show?": "chart",
	"Help me fill in this form": "web-form",
	"NVDA stopped talking in Word": "nvda-silent",
	"I'm new to NVDA, how do I read the window title?": "nvda-beginner",
	"There's a cookie banner I can't get past": "popups-and-banners",
	"Read the error message": "error-message",
	"Am I muted in this meeting?": "video-call",
	"Is there anything personal visible before I share my screen?": "screen-privacy",
	"What colour is this shirt?": "colours",
	"Read this scanned letter": "read-unreadable-text",
	"How does my document look? Is the heading bold?": "document-look",
	"Let the arrow keys work this knob in the synth plugin": "music-software",
	"Help me through this setup wizard": "installer",
	"Read this table row by row": "table",
	"quick status": "quick-status",
	"get my bearings": "bearings",
	"How do I right-click here without a mouse?": "mouse-from-keyboard",
	"Write an add-on that beeps whenever a link gets the focus": "addon-for-blind-user",
}
for request, slug in CHOSEN.items():
	chosen = lib.choose(request)
	assert chosen and chosen[0].slug == slug, (request, [s.slug for s in chosen])
for request in ("what time is it", "turn off the typing echo", "open example.com", "Undo that"):
	assert not lib.choose(request), (request, [s.slug for s in lib.choose(request)])

# 3. Only a skill with steps, whose starting words are in the request word for word, is a plan.
assert skills.planned(lib.choose("quick status"), "quick status").slug == "quick-status"
assert skills.planned(lib.choose("Get my bearings, please"), "Get my bearings, please").slug == "bearings"
assert skills.planned(lib.choose("Describe this photo"), "Describe this photo") is None
assert skills.planned(lib.choose("bearings"), "bearings") is None

# 4. A skill's sentences go only to the steps of the jobs it is for, and to the answer.
photo = lib.get("describe-photo")
assert skills.guide([photo], "describe").startswith('Follow the skill "Describe a photo or picture": ')
assert skills.guide([photo], "change_setting") == ""
assert skills.guide([photo], None)  # a plan a model wrote itself is told every chosen skill
assert skills.guide([photo], anyRecipe={"describe", "answer"}) and not skills.guide([photo], anyRecipe={"click"})
two = skills.guide([photo, lib.get("chart")], "describe")
assert two.count("Follow the skill") == 2 and len(two) <= skills.GUIDE_CHARS + 20, len(two)

# The add-on writer gets the add-on skills, also with no request, by what the add-on is for.
assert 'Follow the skill "An add-on that speaks by itself"' in skills.addonGuide(
	lib, "speak the title every time a window opens")
# The code-writing skills, each chosen by what the add-on is for.
for purpose, slug in (
		("Make an add-on with a key that reads the status bar", "addon-key-command"),
		("in this game, write an add-on that reads the score", "addon-one-program"),
		("NVDA does not read the timer, make an add-on that reads it", "addon-read-missed"),
		("Write an add-on that shows the battery on my braille display", "addon-braille")):
	assert slug in [s.slug for s in lib.choose(purpose)], (purpose, [s.slug for s in lib.choose(purpose)])
assert [s.slug for s in lib.choose("Which braille display do I have?")] == ["braille-setup"]
assert skills.addonGuide(lib, "colour of the sky") == "" and skills.addonGuide(None, "anything") == ""

# 5. The user's own skills: kept, found, chosen before a built-in one, turned off and on, deleted.
folder = tempfile.mkdtemp(prefix="vcskills-user-")
lib = skills.Skills(folder, recipes=RECIPES)
mine = lib.save(skills.Skill(
	"Cooking recipes", "Reading recipes from cooking websites", "recipe, ingredients, cooking", ("web_page",), (),
	"Read the ingredients first, with their amounts exactly, then the steps in order, one at a time."))
assert mine.source == skills.YOURS and os.path.isfile(os.path.join(folder, "cooking-recipes", skills.FILE))
assert lib.find("cooking recipes").slug == "cooking-recipes" and lib.find("the cooking skill").slug == "cooking-recipes"
assert lib.choose("read the ingredients of this recipe")[0].slug == "cooking-recipes"
lib.setOn("cooking-recipes", False)
assert not lib.choose("read the ingredients of this recipe")
assert json.load(open(os.path.join(folder, skills.STATE), encoding="utf-8")) == {"off": ["cooking-recipes"]}
assert not skills.Skills(folder, recipes=RECIPES).get("cooking-recipes").on  # remembered
lib.setOn("cooking-recipes", True)
assert lib.choose("read the ingredients of this recipe")
# A second skill of the same name gets a folder of its own.
again = lib.save(skills.Skill("Cooking recipes", "", "baking", (), (), "Say oven temperatures exactly."))
assert again.slug == "cooking-recipes-2"
assert "was deleted" in lib.remove("cooking-recipes-2") and lib.get("cooking-recipes-2") is None
assert not os.path.exists(os.path.join(folder, "cooking-recipes-2"))

# A built-in skill cannot be deleted, only turned off; changing one keeps the user's copy in its place, and
# deleting that copy brings VisionClaw's own back.
try:
	lib.remove("chart")
	raise AssertionError("a built-in skill was deleted")
except skills.SkillError as e:
	assert "turned off" in str(e)
assert os.path.isfile(os.path.join(skills.BUILT_IN, "chart", skills.FILE))
copy = lib.save(skills.Skill("Understand a chart, graph or diagram", "", "chart, graph", ("describe",), (),
	"Say the title, then the highest value first."), replace="chart")
assert copy.slug == "chart" and copy.source == skills.YOURS and copy.replaces
assert lib.get("chart").instructions.startswith("Say the title")
assert "used again" in lib.remove("chart")
assert lib.get("chart").source == skills.OURS

# A skill with something wrong is not kept, and says why in words.
for bad, why in (
		(skills.Skill("Nothing", "", "", (), (), "Do this."), "no words that start it"),
		(skills.Skill("Common", "", "how do i, what is", (), (), "Do this."), "too common"),
		(skills.Skill("Wrong", "", "wrong", ("fly_to_moon",), (), "Do this."), "not something VisionClaw can do"),
		(skills.Skill("Empty", "", "empty", (), (), ""), "says nothing")):
	try:
		lib.save(bad)
		raise AssertionError(f"kept {bad.name}")
	except skills.SkillError as e:
		assert why in str(e), (why, str(e))

# A skill shared as a file: with the lines at the top, in SmallClaw's own words, or only a heading.
shared = lib.importText(
	"---\nname: Banking\ndescription: online banking\ntriggers: [bank, balance, statement]\nrecipes: web_page\n---\n"
	"Read amounts exactly, with their currency. Never press a button that pays or moves money.\n", "SKILL.md")
assert shared.when == ("bank", "balance", "statement") and shared.uses == ("web_page",), shared
plain = skills.parse("# Podcasts\n\nSay the length of an episode first.\n")
assert plain.name == "Podcasts" and plain.instructions == "Say the length of an episode first." and not plain.when
assert skills.check(plain, RECIPES) == ["It has no words that start it."]
listed = skills.parse("---\nname: Morning\nwhen: good morning\nsteps:\n  1. do_command: what time is it\n"
	"  2. where_am_i\n---\n")
assert listed.steps == (("do_command", "what time is it"), ("where_am_i", "")), listed.steps
try:
	skills.parse("---\nname: Broken\n")
	raise AssertionError("a skill without the closing dashes was read")
except skills.SkillError:
	pass
# The folder the user opens says how a skill is written.
assert os.path.isfile(os.path.join(lib.prepare(), skills.README))
assert lib.reload() and all(s.slug != "README" for s in lib.all())


# 6. Through the orchestrator, with a scripted model.
class FakeRuntime:
	def __init__(self, script):
		self.script = script
		self.calls = []

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None,
			context=None):
		system, user = messages[0]["content"], messages[1]["content"]
		self.calls.append((role, system, user))
		answer = self.script(role, system, user)
		return answer if isinstance(answer, str) else json.dumps(answer)


def text(description, **extra):
	return dict({"type": "string", "description": description}, **extra)


def registry(state):
	reg = tools.Registry()
	commands = {"time": "Reports the current time", "date": "Reports the date", "battery": "Reports the battery"}

	def find(task, words):
		state.setdefault("found", []).append(words)
		return "\n".join(f"{ident}: {description}." for ident, description in commands.items())

	def runIt(task, command, asked):
		state.setdefault("ran", []).append(command)
		return f"Ran the command {command}."

	def look(task, target, question):
		from visionClaw.claw.skills import stepGuide
		state["guide"] = stepGuide(task)
		return "A photo of two people on a beach."

	reg.add(tools.Tool("find_command", "find an NVDA command", find, {"words": text("keywords", auto=True)}, looks=True))
	reg.add(tools.Tool("run_command", "run an NVDA command", runIt, {
		"command": text("the id from find_command"), "asked": text("the user's words", auto=True)},
		changes=True, before="find_command"))
	reg.add(tools.Tool("look", "look at the screen", look, {
		"target": text("what", enum=["window", "screen"], auto=lambda part: "screen"),
		"question": text("what to find out", auto=True)}, looks=True, tell=tools.VERBATIM))
	reg.add(tools.Tool(tools.ANSWER, "tell the user the result", lambda task: ""))
	return reg


def script(role, system, user):
	if system.startswith("You choose how VisionClaw"):
		return {"choice": "describe"}
	if "You fill in one small tool form" in system:
		for ident in ("time", "date", "battery"):
			if ident in user.split("The user asked:")[1].split("\n")[0]:
				return {"command": ident}
		return {"command": "time"}
	if "Answer the user from the information given" in system:
		return "Done."
	raise AssertionError("unexpected prompt: " + system[:80])


userFolder = tempfile.mkdtemp(prefix="vcskills-run-")
lib = skills.Skills(userFolder, recipes=RECIPES)
state = {}
rt = FakeRuntime(script)
orch = orchestrator.Orchestrator(rt, registry(state), lambda q, o: 0, lambda: "", None)
orch.skills = lib

# A skill with steps runs them as they are: three commands, each found with the skill's own words, and no
# model is asked how to handle the request. Only the recipes this computer has are planned.
task = taskModule.Task("Quick status, please")
orch.run(task)
assert task.state == taskModule.DONE, task.log
assert [s.tool for s in task.steps] == ["find_command", "run_command"] * 3 + ["answer"], task.steps
assert state["found"] == ["what time is it", "what is the date today", "how much battery is left"], state
assert state["ran"] == ["time", "date", "battery"], state
assert not any(system.startswith("You choose how") for _r, system, _u in rt.calls)
assert any("following the skill Quick status" in logged for _t, _k, logged in task.log), task.log
assert any("Following the skill Quick status" in logged for _t, _k, logged in task.log)
# Its sentences reach the form of each step of its job.
forms = [user for _r, system, user in rt.calls if "You fill in one small tool form" in system]
assert forms and all('Follow the skill "Quick status' in user for user in forms), forms

# A skill without steps does not plan, but its sentences reach the vision model's question.
state.clear()
task = taskModule.Task("Describe this photo")
orch.run(task)
assert task.state == taskModule.DONE, task.log
assert [s.tool for s in task.steps] == ["look", "answer"], task.steps
assert state["guide"].startswith('Follow the skill "Describe a photo or picture"'), state
assert any("Skills used: Describe a photo or picture" in logged for _t, _k, logged in task.log)

# A skill turned off is not used; a fault in the skills never ends the request.
lib.setOn("describe-photo", False)
state.clear()
orch.run(taskModule.Task("Describe this photo"))
assert state["guide"] == "", state

# A skill whose words are in the request but whose jobs are not in the plan is neither used nor named.
other = lib.save(skills.Skill("Photo settings", "", "photo", ("change_setting",), (), "Say the old value too."))
state.clear()
task = taskModule.Task("Describe this photo")
orch.run(task)
assert task.state == taskModule.DONE and state["guide"] == "", state
assert not any("Skills used" in logged for _t, _k, logged in task.log), task.log
lib.remove(other.slug)


class Broken:
	def choose(self, request):
		raise RuntimeError("broken")


orch.skills = Broken()
task = taskModule.Task("Describe this photo")
orch.run(task)
assert task.state == taskModule.DONE, task.log

# 7. Requests about skills go to the skill recipes.
for request, recipe in (
		("make a new skill: when I ask about recipes, read the ingredients first", "add_skill"),
		("which skills do you have", "list_skills"),
		("open the skills window", "list_skills"),
		("delete the shopping skill", "manage_skill"),
		("turn off the game skill", "manage_skill"),
		("what does the chart skill do", "show_skill")):
	assert planner.hint(request) == recipe, (request, planner.hint(request))

for path in (folder, userFolder):
	shutil.rmtree(path, ignore_errors=True)
print("OK")
