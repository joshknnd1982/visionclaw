# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Runs real requests through the orchestrator with a real model in the bundled engine.

Needs addon/engine (see BUILD.md) and a model on this computer: either models downloaded by VisionClaw
(pass their folder as the first argument) or VisionMate's vision data, which is then used for both roles.
The NVDA tools are replaced by stand-ins, so nothing on the computer is changed.

  python tests/live_orchestrator.py [modelsFolder] [reasoning]
"""
import io
import sys
import time

import harness
from visionClaw.claw import catalog, match, orchestrator, runtime, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.memory import Memory, score


class OneModelCatalog(catalog.Catalog):
	"""Uses VisionMate's vision data for both roles when no coder model is installed."""

	def entries(self, role=None):
		found = super().entries(role)
		if role == CODER and not any(self.isInstalled(e) for e in found):
			return [e for e in super().entries(VISION) if e["id"] == catalog.VISIONMATE_ID]
		return found


def screenshot():
	from PIL import Image, ImageDraw
	image = Image.new("RGB", (640, 360), "white")
	draw = ImageDraw.Draw(image)
	draw.rectangle((0, 0, 640, 40), fill="navy")
	draw.text((12, 12), "Space Trader - Main Menu", fill="white")
	for i, label in enumerate(("New Game", "Load Game", "Options", "Quit")):
		draw.rectangle((220, 80 + i * 60, 420, 120 + i * 60), outline="black", width=2)
		draw.text((280, 94 + i * 60), label, fill="black")
	buf = io.BytesIO()
	image.save(buf, "JPEG", quality=90)
	return buf.getvalue()


def makeRegistry(rt, state):
	reg = tools.Registry()
	settings = {
		"speech.rate": ["speech: rate", 50, "a number from 0 to 100"],
		"speech.symbolLevel": ["speech: symbol level", "some", "one of: none, some, most, all"],
		"keyboard.speakTypedCharacters": ["keyboard: speak typed characters", "on", "on or off"],
	}

	def findSetting(task, words):
		aliases = {
			"speech.rate": "speed fast faster slow slower quick talk talking speak speaking",
			"speech.symbolLevel": "punctuation symbols level",
			"keyboard.speakTypedCharacters": "echo typing letters keys characters typed",
		}
		scored = sorted(((score(words, f"{v[0]} {aliases[k]}"), k, v) for k, v in settings.items()), key=lambda x: -x[0])
		found = [f"{k}: {v[0]}. Now: {v[1]}. Allowed: {v[2]}." for s, k, v in scored if s >= 0.25]
		if not found:
			raise tools.ToolError("No setting matches those words. Try other words, like speech rate.")
		return "\n".join(found)

	def setSetting(task, setting, value):
		if setting not in settings:
			raise tools.ToolError(f"There is no setting with the id {setting}. Copy an id exactly from find_setting.")
		old = settings[setting][1]
		if setting == "speech.rate":
			value = match.toNumber(value, int(old), 0, 100)
		settings[setting][1] = value
		state[setting] = value
		return f"{settings[setting][0]} was {old} and is now {value}."

	def look(task, target, question):
		return rt.describe(screenshot(), f"Look at this picture of the user's {target} and answer: {question}", 250,
			cancel=task.cancel)

	items = ["Space Trader - Main Menu heading", "New Game button", "Load Game button", "Options button", "Quit button"]

	def listItems(task):
		return f"{len(items)} items in the window:\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(items, 1))

	def clickItem(task, item):
		for i, name in enumerate(items, 1):
			if item.strip().rstrip(".") == str(i) or item.lower().replace(" button", "") in name.lower():
				state["clicked"] = name
				return f"Clicked {name}."
		raise tools.ToolError(f"There is no item called \"{item}\". Use a number or a name from list_items.")

	def findCommand(task, words):
		return (
			"title: Reports the title of the current application or foreground window. Keys: NVDA+t.\n"
			"dateTime: Reports the current time. Keys: NVDA+f12.")

	def runCommand(task, command):
		if command not in ("title", "dateTime"):
			raise tools.ToolError(f"There is no command with the id {command}. Copy an id exactly from find_command.")
		state["ran"] = command
		return "Ran the command Reports the title. Its keys are NVDA+t. NVDA said: Space Trader - Main Menu."

	def text(description, **extra):
		return dict({"type": "string", "description": description}, **extra)

	V = tools.VERBATIM
	reg.add(tools.Tool("focus_info", "say which program, window and control the user is in",
		lambda task: "Program: spacetrader. Window title: Space Trader. Focused control: pane, no name.",
		looks=True, title="Checking where you are", tell=V))
	reg.add(tools.Tool("look", "look at the screen with the vision model and answer a question about what is shown",
		look, {"target": text("what to look at", enum=["window", "screen", "control"], auto=lambda part: "window"),
			"question": text("what to find out, as a full question", maxLength=200, auto=True)},
		looks=True, title="Looking at the screen", tell=V))
	reg.add(tools.Tool("list_items", "list the buttons, texts and icons in the window in front, even when NVDA cannot read it",
		listItems, looks=True, title="Listing what is in the window"))
	reg.add(tools.Tool("click_item", "click one item from list_items in the real window", clickItem,
		{"item": text("the number or the name of the item, from list_items", maxLength=80)},
		changes=True, before="list_items", title="Clicking the item"))
	reg.add(tools.Tool("find_setting", "find NVDA settings by describing them; gives each setting's id, value now and allowed values",
		findSetting, {"words": text("2 to 4 keywords for the setting, like: speech rate", maxLength=80, auto=True)},
		looks=True, title="Finding the setting"))
	reg.add(tools.Tool("set_setting", "change one NVDA setting", setSetting, {
		"setting": text("the id of the setting, copied from find_setting", maxLength=80),
		"value": text("the new value: on, off, a number, +10 or -10 to change a number, or one of the allowed values",
			maxLength=60),
	}, changes=True, before="find_setting", title="Changing the setting"))
	reg.add(tools.Tool("find_command", "find NVDA commands by describing what they do; gives each command's id and its keys",
		findCommand, {"words": text("2 to 4 keywords for what the command does", maxLength=80, auto=True)},
		looks=True, title="Finding the command"))
	reg.add(tools.Tool("run_command", "run one NVDA command for the user", runCommand,
		{"command": text("the id of the command, copied from find_command", maxLength=60)},
		changes=True, before="find_command", title="Running the command"))
	reg.add(tools.Tool(tools.ANSWER, "tell the user the result in plain words; always the last step", lambda task: ""))
	return reg


REQUESTS = (
	"Make NVDA speak a little faster.",
	"What is on my screen?",
	"Click the New Game button.",
	"How do I read the title of this window?",
	"Read the window title.",
	"Turn off the typing echo and set punctuation to all.",
	"Click Options, then tell me what the window shows.",
)


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	reasoning = sys.argv[2] if len(sys.argv) > 2 else "auto"
	cat = OneModelCatalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found. Download models with VisionClaw, or install VisionMate's vision data.")
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: {"backend": "auto"})
	print("vision:", rt.entry(VISION)["name"], "| coder:", rt.entry(CODER)["name"])
	asked = []

	def askUser(question, choices):
		asked.append(question)
		print("   ASKED:", question, choices)
		return 0

	try:
		for request in REQUESTS:
			state = {}
			orch = orchestrator.Orchestrator(rt, makeRegistry(rt, state), askUser, lambda: "Program: spacetrader.", Memory("nul"))
			task = taskModule.Task(request, reasoning=reasoning)
			start = time.time()
			orch.run(task)
			print(f"\n=== {request}  -> {task.state} in {time.time() - start:.1f}s, changed: {state}")
			for _seconds, kind, text in task.log:
				if kind in (taskModule.TALK, taskModule.DETAIL, taskModule.ERROR, taskModule.THINK):
					print(f"   [{kind}] {text}")
			print("   ANSWER:", task.answer)
	finally:
		rt.stop()


if __name__ == "__main__":
	main()
