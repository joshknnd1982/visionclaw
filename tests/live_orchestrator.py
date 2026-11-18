# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Runs real requests through the orchestrator with a real model in the bundled engine.

Needs addon/engine (see BUILD.md) and a model on this computer: either models downloaded by VisionClaw
(pass their folder as the first argument) or VisionMate's vision data, which is then used for both roles.
The NVDA tools are replaced by stand-ins, so nothing on the computer is changed.

  python tests/live_orchestrator.py [modelsFolder] [reasoning] [visionModelId] [coderModelId]
"""
import io
import json
import os
import sys
import tempfile
import time

import harness
from visionClaw.claw import audit, catalog, commands, fixes, library, lookup, match, memories, orchestrator, pointer, runtime, scrolling, tools, web
from visionClaw.claw import planner, prompts, skills
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.memory import Memory, score


class LiveRegistry(tools.Registry):
	"""A stand-in tool that is handed a value it cannot use, such as the word "on" where a number belongs,
	raises ValueError. In VisionClaw itself that comes back to the model as a failed step to correct
	(nvdatools' guarded does it), so it must do the same here. Without this, one badly filled form from a very
	small model ended the whole run."""

	def call(self, task, name, form):
		try:
			return super().call(task, name, form)
		except ValueError as e:
			return False, tools.clip(str(e), tools.RESULT_CHARS)


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
	reg = LiveRegistry()
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
			# Like the real tool: the setting's name instead of its id is understood too.
			named = [k for k, v in settings.items() if match.plain(v[0]) == match.plain(setting)]
			if not named:
				raise tools.ToolError(f"There is no setting with the id {setting}. Copy an id exactly from find_setting.")
			setting = named[0]
		old = settings[setting][1]
		if setting == "speech.rate":
			value = match.toNumber(value, int(old), 0, 100)
		settings[setting][1] = value
		state[setting] = value
		return f"{settings[setting][0]} was {old} and is now {value}."

	def look(task, target, question):
		# As the real tool: the instructions for blind users, and what a chosen skill says about looking.
		prompt = f"Look at this picture of the user's {target} and answer: {question}"
		guide = skills.stepGuide(task)
		if guide:
			prompt += f"\n{guide}"
		return rt.describe(screenshot(), prompt, 350, cancel=task.cancel, system=prompts.seeing())

	items = ["Space Trader - Main Menu heading", "New Game button", "Load Game button", "Options button", "Quit button",
		"Search edit field", "Refund policy heading"]

	def listItems(task, about):
		return f"{len(items)} items in the window:\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(items, 1))

	def clickItem(task, item, action):
		for i, name in enumerate(items, 1):
			if item.strip().rstrip(".") == str(i) or item.lower().replace(" button", "") in name.lower():
				state["clicked"] = name if action == "click" else (name, action)
				done = {"click": "Clicked", "double click": "Double-clicked", "right click": "Right-clicked"}.get(action)
				return f"{done} {name}." if done else f"The mouse pointer is on {name}."
		raise tools.ToolError(f"There is no item called \"{item}\". Use a number or a name from list_items.")

	# Every command of NVDA 2026.3.1's globalCommands.py, found the way VisionClaw itself finds them.
	with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nvda_commands.json"), encoding="utf-8") as f:
		known = json.load(f)

	def keysOf(command):
		keys = [g.split(":", 1)[1] for g in command["gestures"] if g.startswith(("kb:", "kb(desktop):"))]
		return " or ".join(keys) if keys else "no key assigned"

	def findCommand(task, words):
		found = commands.find(words, [(c["name"], c["description"], c["category"]) for c in known])
		if not found:
			raise tools.ToolError("No NVDA command matches those words. Use the words of the request that say what the command does.")
		return "\n".join(
			f"{known[i]['name']}: {known[i]['description'].strip().rstrip('.')}. Keys: {keysOf(known[i])}." for i in found)

	def runCommand(task, command, asked):
		chosen = next((c for c in known if c["name"] == command), None)
		if chosen is None:
			raise tools.ToolError(f"There is no command with the id {command}. Copy an id exactly from find_command.")
		wanted = commands.presses(asked, chosen["name"], chosen["description"])
		state.setdefault("ran", []).append((command, wanted))
		said = {
			("dateTime", 1): "4:05 PM", ("dateTime", 2): "Tuesday, November 17, 2026", ("title", 1): "Space Trader - Main Menu",
		}
		heard = " ".join(said[(command, count)] for count in wanted if (command, count) in said)
		often = "" if wanted[-1] == 1 else f" {commands.pressText(wanted[-1])}"
		done = f"NVDA said: {heard}" if heard else f"Done: {chosen['description'].strip().rstrip('.')}"
		return f"{done}. Next time you can press {keysOf(chosen)}{often} for this."

	def text(description, **extra):
		return dict({"type": "string", "description": description}, **extra)

	# A question: every command of NVDA, VisionClaw's notes with the keys of Windows, NVDA's own user guide where
	# NVDA is installed on this computer, and a stand-in program and window, ranked by the real code.
	notes = Knowledge()
	guide = os.path.join(os.environ.get("ProgramFiles", ""), "NVDA", "documentation", "en", "userGuide.html")
	if os.path.isfile(guide):
		with open(guide, encoding="utf-8", errors="replace") as f:
			page = f.read()
		notes.addSource("userGuide", lambda: [(title, body, "userGuide") for title, body in lookup.htmlSections(page)])
	pool = [lookup.fromCommand(
		c["name"], c["description"], c["category"],
		f"{c['name']}: {c['description'].strip().rstrip('.')}. Keys: {keysOf(c)}.") for c in known]
	pool += lookup.fromSections(notes.everything())
	pool += [
		lookup.Passage(lookup.APP, "The program in front", "The program in front is spacetrader, which is Space Trader, version 2.1.",
			"the program spacetrader", here=True),
		lookup.Passage(lookup.WINDOW, "The window in front", "The window in front is called Space Trader - Main Menu.",
			"this window", here=True),
		lookup.Passage(lookup.WINDOW, "The control that has the focus",
			"The focus is on: button \"New Game\". It is 1 of 4. Its own key is Alt+N.", "this window", here=True),
		lookup.Passage(lookup.WINDOW, "Keys of the controls in this window",
			"New Game (button): Alt+N; Load Game (button): Alt+L; Options (button): Alt+O; Quit (button): Alt+Q.", "this window"),
		lookup.Passage(lookup.SYSTEM, "The version of Windows on this computer", "This computer runs Windows 11 24H2, build 26100."),
		lookup.Passage(lookup.SYSTEM, "The windows that are open now",
			"3 windows are open now: Space Trader - Main Menu; Inbox - Mail; Untitled - Notepad."),
	]

	def lookUp(task, question):
		state["asked"] = question
		mine = lookup.fromMemories(KEPT.all()) + SHELF.passages(["spacetrader", "Space Trader"])
		return lookup.resultText(lookup.about(question, pool + mine, program=["spacetrader"])) or lookup.nothingText(
			question, "spacetrader", "Space Trader - Main Menu", library=True, memories=bool(KEPT.all()))

	# Memories and the library, as in memorytools.py, in a folder of their own.
	def remember(task, fact, asked):
		entry, replaced = KEPT.add(memories.factOf(fact or asked), asked=asked)
		return f"VisionClaw will remember this: {entry.text()}" + (" It replaces an older memory." if replaced else "")

	def listMemories(task, asked):
		return KEPT.listText()

	def forgetMemory(task, which):
		chosen = KEPT.chosen(which)
		if not chosen:
			return "None of the memories is about that. " + KEPT.listText()
		gone = [entry.text() for entry in chosen if KEPT.remove(entry.name)]
		return "Forgotten: " + "; ".join(gone)

	reg.add(tools.Tool("remember",
		"keep something the user asks VisionClaw to remember for later: something about them, how they like things "
		"done, a program, or where to find something; kept in their own words as a file they can read",
		remember, {
			"fact": {"type": "string", "description": "what is to be remembered, in the user's own words", "maxLength": 500,
				"auto": memories.factOf},
			"asked": {"type": "string", "description": "what the user asked for, in their own words", "maxLength": 500, "auto": True},
		}, tell=tools.VERBATIM))
	reg.add(tools.Tool("memories",
		"say what VisionClaw remembers that the user asked it to remember, or open the list so the user can read it",
		listMemories, {"asked": {"type": "string", "description": "what the user asked for", "maxLength": 300, "auto": True}},
		looks=True, tell=tools.VERBATIM))
	reg.add(tools.Tool("forget_memory",
		"delete something VisionClaw remembers: what the user names, the last thing it remembered, or everything",
		forgetMemory, {"which": {"type": "string", "description": "what to forget, in the user's own words", "maxLength": 300,
			"auto": True}}, changes=True, tell=tools.VERBATIM))
	reg.add(tools.Tool("library",
		"say which documents are in VisionClaw's library, that it looks things up in, or open the library's folder so "
		"the user can add documents",
		lambda task, asked: SHELF.listText(), {"asked": {"type": "string", "description": "what the user asked for",
			"maxLength": 300, "auto": True}}, looks=True, tell=tools.VERBATIM))

	V = tools.VERBATIM
	reg.add(tools.Tool(lookup.TOOL,
		"answer a question about how to do something with the keyboard or what something is: asks NVDA (its "
		"commands and user guide), then the program in front, then its window, then Windows, and gives what they "
		"say that is about the question",
		lookUp, {"question": text("the user's question, in their own words", maxLength=300, auto=True)},
		looks=True, title="Asking NVDA, the program, the window and Windows"))
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
	reg.add(tools.Tool("click_item",
		"click, double-click, right-click or point at one item from list_items: a link, a button, an item in a window",
		clickItem,
		{"item": text("the number or the name of the item, from list_items", maxLength=80),
			"action": text("what to do with the mouse", enum=pointer.ACTIONS, auto=pointer.actionOf)},
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
	reg.add(tools.Tool("run_command", "run one NVDA command for the user", runCommand, {
		"command": text("the id of the command, copied from find_command", maxLength=60),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
	}, changes=True, before="find_command", title="Running the command"))
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
			"addons": "Add-ons installed (3): Clock and calendar 2.1 (enabled); VisionClaw 0.8.2 (enabled); "
				"NVDA Remote 2.6 (disabled).",
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
	simple("undo_change", "put a setting back to what it was before VisionClaw changed it",
		"Speech rate was 45 and is back to 50, as it was before.", "Putting it back",
		{"what": text("which change to undo, in the user's words", maxLength=300, auto=True)}, changes=True)
	simple("list_changes", "say which settings VisionClaw has changed, and from what to what",
		"Speech rate: from 50 to 45, on 17 November at 12:57.", "Looking up what was changed", looks=True, tell=V)
	simple("drag_item",
		"drag one item from list_items with the mouse: onto another item, or in a direction, as for a slider",
		"Dragged {item} to {to}. The user said: {asked}", "Dragging the item", {
			"item": text("the number or the name of the item to drag, from list_items", maxLength=80),
			"to": text("the item to drag it onto, or a direction and distance in the user's words, such as: right a little",
				maxLength=80),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="list_items")
	simple("work_control",
		"let the arrow keys work a dial, knob, custom slider or other control that is only worked by dragging it "
		"with the mouse, and say what it shows after each press; can keep it under a hotkey",
		"The arrow keys now work {item}, by dragging it up and down. The user said: {asked}",
		"Taking hold of the control", {
			"item": text("the name of the dial, slider or control, as the user said it", maxLength=80),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, tell=V)
	simple("update_guides",
		"download the latest NVDA developer guide and NVDA add-on development guide from the internet and keep them "
		"for the models to read; only when the user asks for exactly this",
		"Downloaded the NVDA Developer Guide and kept it as Markdown, 120 sections.", "Getting the latest developer guides",
		changes=True, tell=V)
	simple("scroll_view",
		"scroll what the window in front shows with the mouse wheel, up, down, left or right, a little, a page or "
		"to the end; says whether anything moved and how far along the view now stands",
		"Scrolled {direction} in the window Space Trader. It now stands 40 percent down. The user said: {asked}",
		"Scrolling", {
			"direction": text("which way to scroll", enum=scrolling.DIRECTIONS, auto=scrolling.directionOf),
			"asked": text("what the user asked for, in their own words, with how far to scroll", maxLength=300, auto=True),
		}, changes=True)
	simple("check_update",
		"look on VisionClaw's own page on GitHub for a newer version of VisionClaw itself, and get it if the "
		"user wants it",
		"You have the newest version of VisionClaw, 0.8.2.", "Looking for a newer version of VisionClaw", tell=V)
	simple("model_info",
		"say which AI models VisionClaw itself has stored on this computer and uses, how big they are, and where "
		"they run",
		"VisionClaw uses one model, Qwen3.5 9B, for both jobs: looking at the screen and planning, and checking and "
		"writing code. One model is stored on this computer: Qwen3.5 9B, 6.1 GB.", "Checking VisionClaw's models",
		looks=True, tell=V)
	simple("pointer_mode",
		"turn on pointer mode, so the user can work any control with the keyboard: the arrow keys move the mouse "
		"pointer, and keys click, right-click, double-click and drag",
		"Pointer mode is on. The arrow keys move the mouse pointer in this window.", "Turning on pointer mode", tell=V)
	simple("list_helpers", "list the app helpers and add-ons VisionClaw has made on this computer",
		"Add-on hello_key (on): say hello on NVDA+shift+h. Keys: NVDA+shift+h.", "Listing what VisionClaw made",
		looks=True, tell=V)
	simple("repair_addon",
		"have the models debug and correct an add-on VisionClaw wrote that fails or does the wrong thing",
		"The add-on {name} was corrected and is on again.", "Debugging the add-on", {
			"name": text("the add-on's name, from list_helpers", maxLength=60),
			"problem": text("what the add-on does wrong, or should do instead", maxLength=400, auto=True),
		}, before="list_helpers", tell=V)
	simple("check_access",
		"inspect the web page, the program's window or the focused control in depth for what stands in the way "
		"of a screen reader user, and say what an add-on can fix",
		"Checked the web page My feed on example-feed.com, in firefox. It has 5 headings, 2 links, 19 buttons and 0 form "
		"fields. Found 3 problems. 1. 12 buttons have no name, so NVDA only says what kind of control it is. 7 of them "
		"can be given a name; 5 cannot be told apart by anything fixed in the page's code. 2. The page is a feed of 5 "
		"posts so far. More are loaded as you move down, so it has no end, and NVDA has no key that goes from post to "
		"post. 3. The page has a video player. Its buttons are found only by moving to them. VisionClaw can fix all of "
		"them with an add-on for the website example-feed.com, which stays until you have it removed. Ask for all of it "
		"to be fixed, or for one number.", "Inspecting for accessibility problems", {
			"target": text("what to inspect; auto is the web page if the user is in one, else the window",
				enum=audit.TARGETS, auto=audit.targetOf),
			"depth": text("deep also watches for changes and reads the picture; quick only reads the controls",
				enum=audit.DEPTHS, auto=audit.depthOf),
		}, looks=True, tell=V)
	simple("fix_access",
		"fix the accessibility problems that check_access found, with an add-on for this website or program that "
		"stays until the user has it removed",
		"Made 6 fixes for the website example-feed.com. The user said: {which}", "Making the accessibility fixes",
		{"which": text("which problems to fix, in the user's words: all of them, or the number of one", maxLength=200,
			auto=True)}, changes=True, before="check_access")
	simple("add_fix",
		"make one lasting fix for this website or program: a key that presses a control, a key that reads one, "
		"keys that move between posts or other items, a name for a control, or being told when something changes",
		"Made 1 fix for the website example-feed.com: kind {kind}, item {item}, key {key}, name {name}.", "Making the fix", {
			"kind": text("the kind of fix", enum=audit.FIX_KINDS, auto=audit.kindOf),
			"item": text("what the fix is about: the control's name as the user said it, the focused control, or for "
				"move the kind of item, in a few words", maxLength=80),
			"key": text("the hotkey the user named, or empty to have a free one chosen", maxLength=30, auto=fixes.keyIn),
			"name": text("for the kind name: the new name. Otherwise empty", maxLength=60),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="check_access")
	simple("addon_info",
		"say what an add-on installed in this NVDA does, whether it is on, what its commands and keys are, and what "
		"its help says",
		"The add-on Clock and calendar, version 2.1, by Someone, is on.\n"
		"It says about itself: Speaks the time and date in many ways, and has alarms.\n"
		"Its commands where you are now: Say the time (NVDA+F12); Open the alarm settings (no key assigned).\n"
		"From its help: Press NVDA+F12 twice to hear the date.", "Looking at the add-on", {
			"addon": text("the name of the add-on, or all for the list of add-ons", maxLength=60),
			"about": text("what the user wants to know about it", maxLength=200, auto=True),
		}, looks=True, tell=V)
	simple("find_nvda",
		"find functions, classes, modules, objects and values inside NVDA's own code and its add-ons' code by "
		"describing them; gives each one's dotted name and what it is",
		"api.getFocusObject: function. getFocusObject(). Gets the object with focus.\n"
		"api.setFocusObject: function. setFocusObject(obj). Stores an object as the current focus object.\n"
		"api.getNavigatorObject: function. getNavigatorObject(). Gets the current navigator object.",
		"Searching inside NVDA",
		{"words": text("2 to 4 keywords for what the thing does, or its name", maxLength=120, auto=True)}, looks=True)
	simple("inspect_nvda",
		"look closely at one thing inside NVDA's code: what a module, class, function or value is, how to call it, "
		"and what it holds or gives back now",
		"{name} is a function.\nCall it as getFocusObject().\nGets the object with focus.\n"
		"Called now, it gives back: an object NVDA reads: button called \"New Game\".", "Looking inside NVDA",
		{"name": text("its dotted name, copied from find_nvda", maxLength=120)}, looks=True, before="find_nvda", tell=V)
	simple("object_info",
		"say what NVDA knows about one object: the focused control, the navigator object, the window in front, what "
		"is under the mouse, the desktop, or what the focused control is inside of; every fact, or the ones asked for",
		"Facts about the object: {object}. Name: New Game. Kind: button. Window class: Button. The user said: {asked}",
		"Asking NVDA about the object", {
			"object": text("which object", enum=["focus", "navigator", "window", "mouse", "desktop", "parent"],
				auto=lambda part: "navigator" if "navigator" in part.lower() else "mouse" if "mouse" in part.lower() else "focus"),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, looks=True, tell=V)
	simple("audit_nvda",
		"go through all of the running NVDA and count and list everything in it: every command, module, class, "
		"function, object and value, and how it drives the speech synthesizer and the braille display; saves the "
		"list as a file",
		"VisionClaw went through all of this NVDA. Commands that can be used where you are now: 330. The user said: {asked}",
		"Going through all of NVDA",
		{"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)}, looks=True, tell=V)
	simple("show_log", "open VisionClaw's own debug log, the file that records what VisionClaw did and every error",
		"VisionClaw's log is open in a window.", "Opening VisionClaw's log", looks=True, tell=V)
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
			auto=lambda part: "braille" if "braille" in part.lower() else "addons" if "add" in part.lower() else "speech")},
		looks=True, title="Asking NVDA"))
	# Skills: the real tools need NVDA, so these stand in for them with the same forms.
	simple("add_skill",
		"make a new skill: what the user says VisionClaw should do, kept and used whenever later requests have "
		"its starting words", "Saved the skill {name}. It is used when your request says: {when}.", "Making the skill", {
			"name": text("a short name for the new skill, in two to five words", maxLength=60),
			"when": text("the words of the user's request that should start the skill, separated by commas", maxLength=200),
			"asked": text("what the user asked for, in their own words", maxLength=1000, auto=True),
		}, changes=True, tell=V)
	simple("list_skills", "say which skills VisionClaw has, or open the skills window or the folder of the user's skills",
		"VisionClaw has 31 skills, 0 of them yours:\n1. Describe a photo or picture\n2. Understand a chart, graph or diagram\n"
		"3. Play a game the screen reader cannot read", "Looking at the skills",
		{"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)}, looks=True, tell=V)
	simple("show_skill", "say what one skill does, when it is used and what it tells VisionClaw",
		"{skill}: everything about it.", "Reading the skill", {
			"skill": text("the name of the skill, from list_skills", maxLength=80),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, looks=True, before="list_skills", tell=V)
	simple("manage_skill", "delete one of the user's skills, or turn a skill off or on",
		"The skill {skill}: {action}.", "Changing the skill", {
			"skill": text("the name of the skill, from list_skills", maxLength=80),
			"action": text("what to do with it", enum=["delete", "turn off", "turn on"],
				auto=lambda part: "turn off" if "off" in part.lower() else "delete"),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="list_skills", tell=V)
	reg.add(tools.Tool(tools.ANSWER, "tell the user the result in plain words; always the last step", lambda task: ""))
	return reg


# What the user asks VisionClaw to remember, and the user's library, for the requests below.
_FOLDER = tempfile.mkdtemp()
KEPT = memories.Memories(os.path.join(_FOLDER, "memories"))
SHELF = library.Library(os.path.join(_FOLDER, "library"))
SHELF.prepare()
# VisionClaw's own skills, and a folder for the user's that starts empty.
SKILLS = skills.Skills(os.path.join(_FOLDER, "skills"), recipes=set(planner.RECIPES))
with open(os.path.join(SHELF.folder, "Space Trader manual.txt"), "w", encoding="utf-8") as _f:
	_f.write("TRADING\nPress T to open the market. Buy low and sell high.\n\nSAVING\nSaving is done with Control+S.\n")

REQUESTS = (
	"Remember that my braille display is a Focus 40.",
	"What do you remember about me?",
	"Which braille display do I have?",
	"I'm new to NVDA. How do I read the title of this window?",
	"Forget that.",
	"What is in my library?",
	"How do I open the market in Space Trader?",
	"What is UI Automation?",
	"What does aria-label do?",
	"How do I reopen a closed tab in Chrome?",
	"How do I turn on Sticky Keys?",
	"ask nvda to give me the current time and then the date.",
	"What time is it?",
	"What is the date today?",
	"Tell me the time and the date.",
	"How much battery is left?",
	"Copy the window title to the clipboard.",
	"What is the window class of the focused control?",
	"Tell me everything NVDA knows about this control.",
	"What does the function api.getFocusObject do?",
	"Do a full audit of NVDA.",
	"Open the VisionClaw log.",
	"Make NVDA speak a little faster.",
	"What is on my screen?",
	"Click the New Game button.",
	"How do I read the title of this window?",
	"How can I use the keyboard to navigate my desktop?",
	"How do I switch between open windows?",
	"How do I copy text?",
	"What is browse mode?",
	"What does NVDA+T do?",
	"How do I close this program?",
	"What can I do here?",
	"Which key starts a new game?",
	"How do I rename a file?",
	"How do I bake a cake?",
	"Which windows are open?",
	"How do I get to the system tray?",
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
	"Restore the voice pitch to what it was before you changed it.",
	"What did you change?",
	"Undo that.",
	"Right-click the Options button.",
	"Drag the New Game button onto the Quit button.",
	"Make this control keyboard navigable.",
	"Check for a new version of VisionClaw.",
	"Is VisionClaw up to date?",
	"Scroll down a page.",
	"Scroll this window to the bottom.",
	"Scroll up a little, then tell me what the window shows.",
	"Do a deep inspection of this website.",
	"Fix the accessibility problems on this page.",
	"Make this website accessible.",
	"Inspect this window for accessibility problems, then fix number 2.",
	"Give this site keys to move between posts.",
	"Make NVDA+alt+P press the Play button on this page.",
	"Tell me when the inbox count changes.",
	"Name the focused button Share on this website.",
	"Fix number 2.",
	"What does the Clock add-on do?",
	"Which keys does the Clock add-on have?",
	"Let the arrow keys work the volume dial.",
	"This program has a dial that is only used by clicking and dragging. Make it work with the keyboard.",
	"Give me a hotkey for the gain knob.",
	"Get the latest NVDA developer guides.",
	"Do a deep query of this control and tell me how a sighted person works it.",
	"What model is installed?",
	"Which AI model are you using?",
	"Which add-ons do I have?",
	"List the add-ons you have made.",
	# Skills (claw/skills.py): one with steps runs them as they are; one without gives its sentences to the
	# models; the rest are about skills themselves.
	"Quick status",
	"Describe this picture for me.",
	"Make a new skill: when I ask about recipes, read the ingredients first, with their amounts exactly.",
	"Which skills do you have?",
	"Turn off the game skill.",
)


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	reasoning = sys.argv[2] if len(sys.argv) > 2 else "auto"
	cat = OneModelCatalog(folder, harness.visionMateData())
	if not cat.installed(VISION):
		sys.exit("No model found. Download models with VisionClaw, or install VisionMate's vision data.")
	# The third and fourth arguments choose the models by their catalog ids, like qwen3.5-4b and qwen3.5-9b-coder.
	chosen = {"backend": "auto", "visionModel": sys.argv[3] if len(sys.argv) > 3 else "",
		"coderModel": sys.argv[4] if len(sys.argv) > 4 else ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	print("vision:", rt.entry(VISION)["name"], "| coder:", rt.entry(CODER)["name"])
	asked = []

	def askUser(question, choices):
		asked.append(question)
		print("   ASKED:", question, choices)
		return 0

	try:
		# With VC_ONLY set, only the requests that contain one of its parts (separated by |) are run.
		only = [part.lower() for part in os.environ.get("VC_ONLY", "").split("|") if part]
		for request in REQUESTS:
			if only and not any(part in request.lower() for part in only):
				continue
			state = {}
			orch = orchestrator.Orchestrator(rt, makeRegistry(rt, state), askUser, lambda: "Program: spacetrader. Window title: Space Trader - Main Menu. Focused control: button, New Game.", Memory("nul"))
			# A fifth argument says whether the model is asked one small question at a time: auto, always or never.
			orch.stepwise = lambda: sys.argv[5] if len(sys.argv) > 5 else "auto"
			orch.memories = KEPT
			orch.program = lambda: "spacetrader"
			orch.skills = SKILLS
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
