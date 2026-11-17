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
from visionClaw.claw import catalog, match, orchestrator, runtime, tools, web
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

	items = ["Space Trader - Main Menu heading", "New Game button", "Load Game button", "Options button", "Quit button",
		"Search edit field", "Refund policy heading"]

	def listItems(task, about):
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
		listItems, {"about": text("what is being looked for, in a few words", maxLength=120, auto=True)},
		looks=True, title="Listing what is there"))
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
	page = (
		"Example Shop\nWelcome to our shop. We sell garden tools.\n"
		"Refund policy\nYou can return any product within 30 days for a full refund.\n"
		"Opening hours\nWe are open Monday to Friday from nine to five."
	)

	def webOpen(task, address):
		state["opened"] = web.normalizeAddress(address)
		return "Opened the web page BBC Home."

	def webSearch(task, words):
		state["searched"] = words
		return f"Searched the web for {words}."

	def readPage(task, about):
		state["read"] = about
		return "From the web page Example Shop:\n" + web.passages(page, about)

	def fillField(task, field, typed, enter):
		state["filled"] = (field, typed, enter)
		return f"Typed \"{typed}\" into Search edit field" + (" and pressed Enter." if enter == "yes" else ".")

	def nvdaInfo(task, topic):
		state["info"] = topic
		return {
			"speech": "Speech synthesizer in use: eSpeak NG (driver name espeak).\nVoice in use: English (America).\n"
				"Rate: 60.\nSynthesizers installed (3): eSpeak NG, Windows OneCore voices, Microsoft Speech API version 5.",
			"braille": "Braille display in use: Freedom Scientific Focus (driver name freedomScientific).\n"
				"It has 40 cells.\nOutput table: English (U.S.) 8 dot computer braille.",
		}.get(topic, "NVDA version: 2026.2.")

	def switchDriver(task, kind, name):
		installed = ["eSpeak NG", "Windows OneCore voices", "Microsoft Speech API version 5"]
		index = match.best(name, installed)
		if index is None:
			raise tools.ToolError(f"There is no {kind} called \"{name}\". Installed: {', '.join(installed)}.")
		state["switched"] = installed[index]
		return f"The {kind} is now {installed[index]}. Before, it was eSpeak NG."

	reg.add(tools.Tool("switch_driver",
		"switch NVDA to another speech synthesizer or braille display; refuses a switch that would leave the user "
		"with neither speech nor braille, and switches back if the new one is not confirmed to work",
		switchDriver, {
			"kind": text("which kind of driver", enum=["synthesizer", "braille display"],
				auto=lambda part: "braille display" if "braille" in part.lower() else "synthesizer"),
			"name": text("the name of the synthesizer or braille display to switch to, from nvda_info", maxLength=80),
		}, changes=True, before="nvda_info", title="Switching the driver"))
	def simple(name, description, result, title, fields=None, **options):
		def run(task, **form):
			state[name] = form or True
			return result.format(**form) if form else result
		reg.add(tools.Tool(name, description, run, fields, title=title, **options))

	simple("page_outline",
		"say how the web page is laid out: its headings in order, and how many links, buttons and fields it has",
		"The web page Example Shop has 2 headings, 3 links, 1 buttons and 1 form fields.\n"
		"Heading level 1: Example Shop\nHeading level 2: Refund policy", "Looking at how the page is laid out",
		looks=True, tell=V)
	simple("go_to_item",
		"move NVDA's reading position to one item from list_items on the web page: a heading, a link or a field",
		"NVDA is now at {item}.", "Moving there",
		{"item": text("the number or the name of the item, from list_items", maxLength=80)}, before="list_items", tell=V)
	simple("page_navigate", "go back or forward one page in the browser, or reload the page",
		"Went {direction}. The page is now Example Shop.", "Moving between pages",
		{"direction": text("which way", enum=["back", "forward", "reload"],
			auto=lambda part: "reload" if "reload" in part.lower() else "forward" if "forward" in part.lower() else "back")},
		tell=V)
	simple("list_helpers", "list the app helpers and add-ons VisionClaw has made on this computer",
		"Add-on hello_key (on): say hello on NVDA+shift+h. Keys: NVDA+shift+h.", "Listing what VisionClaw made",
		looks=True, tell=V)
	simple("repair_addon",
		"have the models debug and correct an add-on VisionClaw wrote that fails or does the wrong thing",
		"The add-on {name} was corrected and is on again.", "Debugging the add-on", {
			"name": text("the add-on's name, from list_helpers", maxLength=60),
			"problem": text("what the add-on does wrong, or should do instead", maxLength=400, auto=True),
		}, before="list_helpers", tell=V)
	reg.add(tools.Tool("web_open", "open a web address in the user's browser", webOpen,
		{"address": text("the web address, like example.com", maxLength=300, auto=web.addressIn)},
		title="Opening the web page", tell=V))
	reg.add(tools.Tool("web_search", "search the web for something, in the user's browser", webSearch,
		{"words": text("what to search for, as a few words", maxLength=200, auto=web.searchWords)},
		title="Searching the web", tell=V))
	reg.add(tools.Tool("read_page", "read the web page the user is in: the parts of its text that matter for the question",
		readPage, {"about": text("the question, or what to look for on the page", maxLength=200, auto=True)},
		looks=True, title="Reading the web page"))
	reg.add(tools.Tool("fill_field", "type text into one field from list_items, such as a search box or a field of a form",
		lambda task, field, text, enter: fillField(task, field, text, enter), {
			"field": text("the number or the name of the field, from list_items", maxLength=80),
			"text": text("the text to type into it", maxLength=400),
			"enter": text("yes to press Enter afterwards, to search or send", enum=["yes", "no"],
				auto=lambda part: "yes" if "search" in part.lower() else "no"),
		}, changes=True, before="list_items", title="Typing into the field"))
	reg.add(tools.Tool("nvda_info",
		"report what NVDA has and uses: the speech synthesizer, its voices and settings, the braille display and "
		"tables, the installed drivers, the add-ons, NVDA's version", nvdaInfo,
		{"topic": text("what to report on", enum=["speech", "braille", "addons", "general"],
			auto=lambda part: "braille" if "braille" in part.lower() else "speech")},
		looks=True, title="Asking NVDA"))
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
	"Open bbc.co.uk",
	"Search the web for the weather in Boston.",
	"What does this page say about refunds?",
	"Type garden gloves into the search box and search.",
	"Which speech synthesizer am I using?",
	"What braille display do I have, and how many cells does it have?",
	"Switch my speech synthesizer to the Windows OneCore voices.",
	"What are the headings on this page?",
	"Take me to the heading Refund policy.",
	"Go back to the previous page.",
	"The add-on hello key does not work, it says nothing. Fix it.",
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
