# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The skills for everyday tasks (1.20.0 and later), with plain Python.

The owner asked on 2026-11-19, after the skill that makes a whole program accessible: "make more complex skills for
other common end-user tasks", and to add to VisionClaw's parser and orchestrator where needed. Fifteen skills came of it:
chat apps, the calendar, writing and proofreading, music and videos, printing, a download, no sound, starting the day,
social media, Windows updates, banking safely, reading a book, remote help, copy and paste, and what is on the
clipboard. This checks, without NVDA and without a model:
- each is chosen first for the words people use for its task, and for nothing else that is asked every day;
- the six with steps of their own run them only for their own words, and every step's words are understood by plain
  code: the NVDA command is found among NVDA's real commands, the folder and the part of Windows are read from the words;
- not one of the 312 known requests and none of the evaluation sets runs these steps instead of its own job;
- one of them carried out from start to end with a scripted model, no model choosing the job.
Every skill is also checked with the others in tests/test_skills.py.

  python tests/test_everyday_skills.py
"""
import glob
import json
import os
import tempfile

import harness  # noqa: F401
from test_core import FakeRuntime
from visionClaw.claw import commands, computer, orchestrator, places, planner, skills, tools
from visionClaw.claw import task as taskModule

HERE = os.path.dirname(os.path.abspath(__file__))
lib = skills.Skills(tempfile.mkdtemp(prefix="vceveryday-"), recipes=set(planner.RECIPES))
NEW = {
	"chat-and-messages": ("Read my unread messages in WhatsApp", "Reply to the last message in this group chat"),
	"calendar-and-appointments": ("What's on my calendar today?", "Add an appointment with the dentist on Friday"),
	"write-and-proofread": ("Proofread what I wrote", "Are there spelling mistakes in this email?"),
	"music-and-videos": ("Pause the video", "Skip to the next song in Spotify"),
	"print-something": ("print this", "My printer is not printing anything"),
	"find-a-download": ("where did my download go", "What did I just download?"),
	"sound-not-working": ("no sound", "My headphones not working with this computer"),
	"start-my-day": ("start my day", "Give me my morning briefing"),
	"social-media-feed": ("Read the next post on Facebook", "What are the comments on this post?"),
	"windows-updates": ("windows update", "Are there pending updates for Windows?"),
	"online-banking-safely": ("What's my account balance?", "Help me pay a bill on my bank's website"),
	"reading-a-book": ("Read this book from the start", "Go to the next chapter of my ebook"),
	"remote-help": ("How do I get remote help with NVDA?", "Set up NVDA remote so my friend can help"),
	"copy-and-paste": ("copy this text", "Copy the link of this page"),
	"what-is-on-the-clipboard": ("what did I copy", "What's on my clipboard?"),
}
for slug, said in NEW.items():
	skill = lib.get(slug)
	assert skill is not None and skill.source == skills.OURS, slug
	assert "errors" in skill.log and not skills.check(skill, set(planner.RECIPES)), slug
	for request in said:
		chosen = [found.slug for found in lib.choose(request)]
		assert chosen and chosen[0] == slug, (request, chosen)
# Everyday requests that are about something else choose none of them.
for request in ("what time is it", "turn off the typing echo", "open example.com", "Undo that", "fix this window",
		"read the window title", "describe the screen", "write Jordan Lee on the dotted line under Print Name",
		"Open my downloads folder.", "what is in my downloads folder", "make NVDA speak faster", "close this window"):
	assert not set(found.slug for found in lib.choose(request)) & set(NEW), (request, [s.slug for s in lib.choose(request)])

# The skills with steps of their own: run only for their own words, and each step's words understood by plain code.
STEPS = {
	"print-something": [("press_keys", "press control+p"), ("where_am_i", "")],
	"find-a-download": [("files", "what is the newest file in my downloads folder")],
	"sound-not-working": [("system_volume", "what is the computer volume"), ("open_thing", "open sound settings")],
	"start-my-day": [("do_command", "what time is it"), ("do_command", "what is the date today"),
		("do_command", "how much battery is left"), ("read_place", "what notifications do I have")],
	"windows-updates": [("open_thing", "open windows update"), ("describe",
		"Say what the Windows Update page says: whether updates are waiting, being installed or need a restart.")],
	"what-is-on-the-clipboard": [("do_command", "report the text on the clipboard")],
}
for slug, steps in STEPS.items():
	assert list(lib.get(slug).steps) == steps, (slug, lib.get(slug).steps)
with open(os.path.join(HERE, "nvda_commands.json"), encoding="utf-8") as f:
	NVDA = [(c["name"], c["description"], c["category"]) for c in json.load(f)]
WANTED = {"what time is it": "dateTime", "what is the date today": "dateTime", "how much battery is left": "say_battery_status",
	"report the text on the clipboard": "reportClipboardText"}
for slug, steps in STEPS.items():
	for recipe, words in steps:
		if recipe == "do_command":
			assert NVDA[commands.find(words, NVDA)[0]][0] == WANTED[words], (words, [NVDA[i][0] for i in commands.find(words, NVDA)])
		elif recipe == "files":
			wish = computer.fileWish(words)
			assert wish["folders"] == ["downloads"] and wish["order"] == "newest", wish
		elif recipe == "read_place":
			assert places.wish(words)["places"] == ["notifications"], places.wish(words)
		elif recipe == "system_volume":
			assert computer.volumeOf(words) is not None, words
		elif recipe == "open_thing":
			assert computer.opensPlace(words), words
		elif recipe == "press_keys":
			assert "control+p" in words
for request, slug in (("print this", "print-something"), ("Print it, please", "print-something"), ("no sound", "sound-not-working"),
		("start my day", "start-my-day"), ("windows update", "windows-updates"), ("what did I copy", "what-is-on-the-clipboard"),
		("where did my download go", "find-a-download")):
	run = skills.planned(lib.choose(request), request)
	assert run is not None and run.slug == slug, (request, run)
for request in ("my printer is not working, how do I fix it", "no sound, what should I check first", "Open the file I downloaded",
		"open my latest download", "copy this text"):
	run = skills.planned(lib.choose(request), request)
	assert run is None or run.slug not in STEPS, (request, run.slug)

# A how-question or a why-question is answered, and nothing is done, also where a skill's own words are in it: the
# orchestrator does not run the steps that skills.planned would give it (claw/orchestrator.py, planner.asksHowOrWhy).
for request in ("How do I print this?", "how can I start my day with VisionClaw", "Why is there no sound"):
	assert planner.asksHowOrWhy(request), request
assert skills.planned(lib.choose("How do I print this?"), "How do I print this?") is not None
for request in ("print this", "start my day", "no sound", "what did I copy"):
	assert not planner.asksHowOrWhy(request), request
source = open(orchestrator.__file__, encoding="utf-8").read()
assert "ownPlan is not None and planner.asksHowOrWhy(request)" in source

# Not one known request, and none of the evaluation sets, runs these steps in place of its own job.
texts = []
known = json.load(open(os.path.join(HERE, "eval", "known.json"), encoding="utf-8"))["jobs"]
texts += [text for found in known.values() for text in found]
for name in glob.glob(os.path.join(HERE, "eval", "requests*.json")):
	data = json.load(open(name, encoding="utf-8"))
	for item in (data if isinstance(data, list) else data.get("requests") or []):
		if isinstance(item, dict):
			texts.append(item.get("request") or item.get("text") or "")
assert len(texts) > 800, len(texts)
ran = [text for text in texts if (skills.planned(lib.choose(text), text) or lib.get("bearings")).slug in NEW]
assert not ran, ran

# Start my day, from start to end: three NVDA commands and the notifications, each with the skill's own words, and no
# model asked how to handle the request.
state = {}


def text(description, **extra):
	spec = {"type": "string", "description": description}
	spec.update(extra)
	return spec


reg = tools.Registry()
COMMANDS = {"time": "Reports the current time", "date": "Reports the date", "battery": "Reports the battery"}
reg.add(tools.Tool("find_command", "find an NVDA command", lambda task, words: state.setdefault("found", []).append(words) or "\n".join(
	f"{ident}: {description}." for ident, description in COMMANDS.items()), {"words": text("keywords", auto=True)}, looks=True))
reg.add(tools.Tool("run_command", "run an NVDA command", lambda task, command, asked: state.setdefault("ran", []).append(command)
	or f"Ran the command {command}.", {"command": text("the id from find_command"), "asked": text("the user's words", auto=True)},
	changes=True, before="find_command"))
reg.add(tools.Tool("read_place", "read a part of Windows", lambda task, asked: state.setdefault("read", []).append(asked)
	or "The notification center has 2 notifications: Mail, 3 new messages; Calendar, Dentist at 3.", {
	"asked": text("the user's words", auto=True)}, looks=True, tell=tools.VERBATIM))
reg.add(tools.Tool(tools.ANSWER, "tell the user the result", lambda task: ""))


def script(role, system, user):
	if system.startswith("You choose how VisionClaw"):
		raise AssertionError("no model chooses the job of a skill with steps")
	if "You fill in one small tool form" in system:
		asked = user.split("The user asked:")[1].split("\n")[0]
		for ident, words in (("time", "time"), ("date", "date"), ("battery", "battery")):
			if words in asked:
				return {"command": ident}
		return {"command": "time"}
	if "Answer the user from the information given" in system:
		return "Done."
	raise AssertionError("unexpected prompt: " + system[:80])


runtime = FakeRuntime(script)
orch = orchestrator.Orchestrator(runtime, reg, lambda q, o: 0, lambda: "", None)
orch.skills = lib
task = taskModule.Task("Start my day, please")
orch.run(task)
assert task.state == taskModule.DONE, task.log
assert [s.tool for s in task.steps] == ["find_command", "run_command"] * 3 + ["read_place", "answer"], task.steps
assert state["found"] == ["what time is it", "what is the date today", "how much battery is left"], state
assert state["ran"] == ["time", "date", "battery"] and state["read"] == ["what notifications do I have"], state
assert any("following the skill Start my day" in logged for _t, _k, logged in task.log), task.log
assert "The notification center has 2 notifications" in task.answer, task.answer

print("test_everyday_skills: OK")
