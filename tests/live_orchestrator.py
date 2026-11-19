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
from visionClaw.claw import computer, controls, dates, partners, places, planner, profiles, prompts, router, skills
from visionClaw.claw import guide as walking
try:
	# Understanding the user's words and the work sheets came with 1.11.0; an older copy scored with VC_PLUGIN has none.
	from visionClaw.claw import understand
except ImportError:
	understand = None
WORK = tempfile.mkdtemp(prefix="visionclaw-work-")
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

	def setSetting(task, setting, value, asked):
		if setting not in settings:
			# Like the real tool: the setting's name instead of its id is understood too.
			named = [k for k, v in settings.items() if match.plain(v[0]) == match.plain(setting)]
			if not named:
				raise tools.ToolError(f"There is no setting with the id {setting}. Copy an id exactly from find_setting.")
			setting = named[0]
		old = settings[setting][1]
		if setting == "speech.rate":
			value = match.toNumber(value, int(old), 0, 100)
		# Like the real tool: "only in this program" is read from the user's own words, and the words that say so
		# are no part of what the setting is compared with.
		scope = profiles.scopeOf(asked, {"app": "spacetrader", "product": "Space Trader", "title": "Space Trader - Main Menu"})
		if profiles.everywhere(asked):
			settings[setting][1] = value
			state["everywhere"] = (setting, value)
			return profiles.everywhereDone(settings[setting][0].capitalize(), old, value)
		if scope is not None:
			state.setdefault("only in", []).append((scope["program"] or "the program in front", setting, value))
			return profiles.done(settings[setting][0].capitalize(), old, value, scope["program"] or "Space Trader", "spacetrader", True)
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
		# What the words put in a place of Windows is listed from there, as nvdatools' list_items does.
		place = places.within(about)
		if place in (places.TRAY, places.TASKBAR):
			task.listed = [item["name"] for item in places.usable(taskbarItems)
				if not item.get("hidden") and places.isTray(item) == (place == places.TRAY)]
			return f"{len(task.listed)} items in {places.nameOf(place)} of Windows:\n" + "\n".join(
				f"{i}. {n}" for i, n in enumerate(task.listed, 1))
		task.listed = items
		return f"{len(items)} items in the window:\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(items, 1))

	def clickItem(task, item, action):
		for i, name in enumerate(getattr(task, "listed", None) or items, 1):
			if item.strip().rstrip(".") == str(i) or item.lower().replace(" button", "") in name.lower():
				state["clicked"] = name if action == "click" else (name, action)
				done = {"click": "Clicked", "double click": "Double-clicked", "right click": "Right-clicked",
					"middle click": "Clicked with the middle mouse button:", "triple click": "Triple-clicked"}.get(action)
				if action == pointer.HOLD:
					return f"Held the mouse button down on {name} for {pointer.secondsText(pointer.holdSeconds(task.request))}."
				return f"{done} {name}." if done else f"The mouse pointer rests on {name}. This appeared: Opens the settings."
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
		"click, double-click, triple-click, right-click, click with the middle button, hover over, or press and hold "
		"one item from list_items: a link, a button, an item in a window; also with Control, Shift or Alt held down, "
		"or at a place on the item; hovering says what appeared",
		clickItem,
		{"item": text("the number or the name of the item, from list_items", maxLength=80),
			"action": text("what to do with the mouse", enum=pointer.ACTIONS, auto=pointer.actionOf)},
		changes=True, before="list_items", title="Clicking the item"))
	reg.add(tools.Tool("find_setting", "find NVDA settings by describing them; gives each setting's id, value now and allowed values",
		findSetting, {"words": text("2 to 4 keywords for the setting, like: speech rate", maxLength=80,
			auto=lambda part: profiles.without(part)[:80])},
		looks=True, title="Finding the setting"))
	reg.add(tools.Tool("set_setting", "change one NVDA setting", setSetting, {
		"setting": text("the id of the setting, copied from find_setting", maxLength=80),
		"value": text("the new value: on, off, a number, +10 or -10 to change a number, or one of the allowed values",
			maxLength=60),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
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
		# With VC_WITHOUT set, the stand-ins named in it (separated by |) are left out, and with them the jobs
		# that need them: to see whether a choice went wrong because of a job that was added.
		if name in os.environ.get("VC_WITHOUT", "").split("|"):
			return

		def run(task, **form):
			state[name] = form or True
			return result.format(**form) if form else result
		reg.add(tools.Tool(name, description, run, fields, title=title, **options))

	if understand is not None:
		# The user's own words, as in wordtools.py: the stand-in keeps nothing.
		simple("my_words",
			"teach VisionClaw a word or phrase of the user's own that is to mean something else from now on, list the "
			"words taught, or forget one or all of them",
			"From now on, the word is understood as the user said. To undo it, say forget the word.", "Your own words", {
				"action": text("teach a new word, list the words taught, forget one word, or forget all of them",
					enum=list(understand.ACTIONS), auto=understand.actionOf),
				"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
			}, changes=True, tell=tools.VERBATIM)
	simple("page_outline",
		"say how the web page is laid out: its headings in order, and how many links, buttons and fields it has",
		"The web page Example Shop has 2 headings, 3 links, 1 buttons and 1 form fields.\n"
		"Heading level 1: Example Shop\nHeading level 2: Refund policy", "Looking at how the page is laid out",
		looks=True, tell=V)
	# The page as a whole, and what stops a form (pagetools.py): what the real tools say of a stand-in page.
	simple("explore_page",
		"say how the web page the user is in is laid out and how to move on it: landmarks, where the main part "
		"begins, headings, the navigation's links, form fields, and the NVDA keys that fit this page",
		"The web page Example Shop on example-shop.com has 2 headings, 3 landmarks, 3 links, 1 button and 1 form field.\n"
		"Landmarks in order: banner; navigation, with 3 links; main.\n"
		"The main landmark begins with the heading at level 1, Example Shop.\n"
		"How to move on this page:\n"
		"The quickest way to the main part: press 1, which moves to the heading at level 1.\n"
		"H moves to the next heading, Shift+H to the one before.", "Exploring the page", looks=True, tell=V)
	simple("form_trouble",
		"find out why a form on the web page will not send or submit: fields marked as not valid, required fields "
		"that are empty, and the page's error messages; then move NVDA's reading position to the first of them",
		"2 fields may be stopping this form.\n"
		"1. Email, edit field, required: is marked as not valid. The page says: Enter an email address with an @ sign.\n"
		"2. Password, password field, required: must be filled in and is empty.\n"
		"NVDA's reading position is now on the first of them, Email. Press Enter to go into it, and Escape to come "
		"back to reading.", "Looking for what stops the form", looks=True, tell=V)
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
	simple("guides_info",
		"say which NVDA developer guides VisionClaw has downloaded to this computer, from which day and where they "
		"are kept, or open their folder; not for what the guides say about something",
		"The NVDA Developer Guide by NV Access, downloaded on 2026-11-17, 1 day ago.", "Looking at the developer guides",
		{"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)}, looks=True, tell=V)
	simple("remove_guides", "delete the downloaded NVDA developer guides from this computer",
		"Deleted from this computer: the NVDA Developer Guide and the NVDA Add-on Development Guide.",
		"Deleting the developer guides", changes=True, tell=V)
	simple("downloads_info",
		"say what VisionClaw can download for the user on request, guides, lessons and notes, whether each is on this "
		"computer already, and what to say to get it; when the user asks what it can download, get or learn from",
		"VisionClaw can get these for you from the internet. Each is downloaded only when you ask for it.",
		"Looking at what can be downloaded", looks=True, tell=V)
	simple("update_training",
		"download free material that teaches NVDA from the internet, the NVDA wiki, the lessons of the American "
		"Foundation for the Blind and the workshops of Hadley, and keep it for looking things up; only when the "
		"user asks for exactly this",
		"Downloaded 6 pages of the NVDA wiki and kept them as Markdown.", "Getting the free training material",
		changes=True, tell=V)
	simple("training_info",
		"say which training material about NVDA VisionClaw has downloaded to this computer, from which day and "
		"where it is kept, and where NVDA's own help is kept as Markdown files, or open the folder; not for what "
		"the material says about something",
		"6 pages of the NVDA wiki, by NVDA's community, on GitHub, downloaded today.", "Looking at the training material",
		{"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)}, looks=True, tell=V)
	simple("remove_training", "delete the downloaded NVDA training material from this computer",
		"Deleted from this computer: the NVDA wiki.", "Deleting the training material", changes=True, tell=V)
	simple("coach",
		"coach the user with the lessons of the add-on NVDA Coach when they ask to be coached, taught or trained, "
		"or ask for a lesson or a hint: opens NVDA Coach, or gives a hint, one step or a whole lesson from it, says "
		"which lessons it has, or how far the user is",
		"From NVDA Coach, the lesson \"About Browse Mode\" in Browse Mode and Web Navigation, a hint: Arrow keys move "
		"through it just like a regular document.", "Asking NVDA Coach",
		{"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)}, looks=True, tell=V)
	simple("scroll_view",
		"scroll what the window in front shows with the mouse wheel, up, down, left or right, a little, a page or "
		"to the end; says whether anything moved and how far along the view now stands",
		"Scrolled {direction} in the window Space Trader. It now stands 40 percent down. The user said: {asked}",
		"Scrolling", {
			"direction": text("which way to scroll", enum=scrolling.DIRECTIONS, auto=scrolling.directionOf),
			"asked": text("what the user asked for, in their own words, with how far to scroll", maxLength=300, auto=True),
		}, changes=True)
	simple("draw_gesture",
		"swipe, flick or draw a line or a shape with the mouse button held down, on an item the user names, at the "
		"mouse pointer or in the middle of the window, for a program that is worked by gestures; says whether "
		"anything changed",
		"Drew the gesture with the mouse button held down. What the window shows changed. The user said: {asked}",
		"Drawing the gesture", {
			"asked": text("what the user asked for, in their own words, with the direction or the shape", maxLength=300, auto=True),
		}, changes=True)
	simple("timed_click",
		"click something at the right moment: as soon as it changes or appears, or many times in a steady rhythm; "
		"for games and controls that react to timing",
		"Clicked at the right moment. The user said: {asked}", "Clicking at the right moment", {
			"asked": text("what the user asked for, in their own words, with when or how often to click", maxLength=300, auto=True),
		}, changes=True)
	# A hotkey of the program in front. It was missing here until 2026-11-18, so the models could not choose it.
	simple("create_helper",
		"give the program in front its own hotkey, a key or a button of a game controller, that clicks an item, "
		"hovers over it, holds it down, or reads the text at it, found by name each time",
		"In spacetrader, pressing {key} now does this: {action} \"{item}\". The user said: {asked}", "Making the hotkey", {
			"key": text("the hotkey, like NVDA+alt+1, or the button of the game controller", maxLength=40),
			"action": text("click the item, hover over it, hold it down, or read it", enum=pointer.ACTIONS + ["read"],
				auto=lambda part: "read" if " read" in part.lower() else pointer.actionOf(part)),
			"item": text("the name of the item, from list_items", maxLength=80),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="list_items")
	simple("touch_gesture",
		"touch the screen as fingers would, on an item the user names, at the mouse pointer or in the middle of the "
		"window: pinch or spread with two fingers, swipe with one to five fingers, turn with two fingers, tap, double "
		"tap, or touch and hold; where a program takes no touch the mouse wheel is used instead; says whether "
		"anything changed",
		"Touched the screen as fingers would. What the window shows changed. The user said: {asked}",
		"Touching the screen", {
			"asked": text("what the user asked for, in their own words, with the gesture and the number of fingers",
				maxLength=300, auto=True),
		}, changes=True)
	simple("pen_stroke",
		"press on the screen as a pen or a finger would, with a pressure the user names: lightly, firmly, a number "
		"of percent, rising or falling; in one place for a time, or along a line or a shape; for drawing programs "
		"and controls that feel how hard they are pressed",
		"Pressed as a pen would. What the window shows changed. The user said: {asked}", "Pressing with pressure", {
			"asked": text("what the user asked for, in their own words, with how hard to press", maxLength=300, auto=True),
		}, changes=True)
	simple("turn_view",
		"turn the view, look or aim in a game that reads the mouse directly, by moving the mouse itself left, right, "
		"up or down, a little, a lot or around; says whether the view changed",
		"Moved the mouse itself. What the window shows changed. The user said: {asked}", "Moving the mouse itself", {
			"asked": text("what the user asked for, in their own words, with the direction", maxLength=300, auto=True),
		}, changes=True)
	simple("mouse_way",
		"say or keep how the mouse is moved in the program in front: Windows' own pointer, a pointer the game draws "
		"itself, or a view that the mouse turns; also make direct mouse movement faster or slower there, or measure "
		"the game's own pointer",
		"Kept for spacetrader how its mouse is moved. The user said: {asked}", "How the mouse is moved here", {
			"asked": text("what the user said about how this program uses the mouse, in their own words", maxLength=300, auto=True),
		}, changes=True)
	simple("controller_info",
		"say whether a game controller, gamepad or joystick is connected, whether controller mode is on, and what "
		"its sticks, buttons and triggers do in controller mode",
		"A game controller is connected: an Xbox controller, or one that Windows reads the same way. Controller mode "
		"is off. Hold the controller's View and Menu buttons together for a second, or press NVDA+Alt+J, to work the "
		"mouse pointer with it.", "Checking the game controller", looks=True, tell=V)
	simple("controller_mode",
		"turn controller mode on or off: with it on, a connected game controller works the mouse pointer in any "
		"window, with its sticks, buttons and triggers",
		"Controller mode is {turn}.", "Controller mode", {
			"turn": text("on or off", enum=["on", "off"], auto=lambda part: "off" if " off" in part.lower() else "on"),
		}, tell=V)
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
	# The computer itself (claw/computer.py): the real tools need Windows, so these stand in for them with the
	# same forms. Nothing on this computer is opened, emptied, closed or shut down.
	things = computer.places() + [
		computer.thing("desktop", "Firefox", computer.ON_DESKTOP, "x"), computer.thing("desktop", "Steam", computer.ON_DESKTOP, "x"),
		computer.thing("program", "Google Chrome", computer.PROGRAM, "x"), computer.thing("program", "Space Trader", computer.PROGRAM, "x"),
		computer.thing("program", "Space Trader Editor", computer.PROGRAM, "x")]
	windows = [
		{"hwnd": 1, "title": "Space Trader - Main Menu", "app": "spacetrader", "front": True, "minimized": False},
		{"hwnd": 2, "title": "Settings", "app": "ApplicationFrameHost", "front": False, "minimized": False},
		{"hwnd": 3, "title": "Mozilla Firefox", "app": "firefox", "front": False, "minimized": False},
		{"hwnd": 4, "title": "notes.txt - Notepad", "app": "notepad", "front": False, "minimized": True}]

	def findThing(task, words):
		found, _sure = computer.find(computer.wanted(words), things)
		if not found:
			raise tools.ToolError(computer.nothingFound(computer.wanted(words)))
		task.things = found
		return computer.foundText(found)

	def openThing(task, thing, asked):
		item = next((one for one in getattr(task, "things", ()) if one["id"] == thing), None)
		if item is None:
			raise tools.ToolError(f"There is no thing with the id {thing}. Copy an id exactly from find_thing.")
		state.setdefault("opened", []).append(item["id"])
		return f"Opened {item['name']}."

	def systemVolume(task, asked):
		wish = computer.volumeOf(asked)
		if wish is None:
			raise tools.ToolError("The request does not say what to do with the computer's volume.")
		state["system volume"] = wish
		new, _held = computer.volumeNew(40, wish) if wish[0] in (computer.UP, computer.DOWN, computer.SET) else (40, False)
		return f"The computer's volume was 40 percent and is now {new} percent."

	def listWindows(task, about):
		task.windows = windows
		return computer.windowsText(windows)

	def windowAction(task, window, action, asked):
		meant = computer.windowsMeant(asked, task.windows) or computer.windowsMeant(window, task.windows)
		if len(meant) != 1:
			raise tools.ToolError(f"No open window is called \"{window}\". Use a number or a name from list_windows.")
		state.setdefault("window", []).append((action, meant[0]["title"]))
		return f"{action.capitalize()}: the window {meant[0]['title']}."

	def checkSeen(task, what, asked):
		state["checked"] = what
		return f"{computer.YES} {what} is on the screen: its name is in the text that is shown."

	def setControl(task, asked):
		wish = controls.wish(asked)
		if wish is None:
			raise tools.ToolError("The request does not say which control of this program to set and how.")
		state.setdefault("control", []).append((wish["name"], wish["what"]))
		return f"{wish['name'].capitalize()} was set: {wish['what']}."

	def powerTool(task, asked):
		what = computer.powerOf(asked)
		if what is None:
			raise tools.ToolError("The request does not say whether to lock, sleep, restart or shut down.")
		state["power"] = what
		return f"Would {what} the computer now; the test does not."

	askedField = {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)}
	reg.add(tools.Tool("find_thing",
		"find what the user wants opened by its name: a program, an app, a thing on the desktop, a folder, a file of "
		"theirs, the Recycle Bin, Control Panel, or a page of Windows Settings; gives each thing's id",
		findThing, {"words": text("the name of what is to be opened, as the user said it", maxLength=120, auto=computer.wanted)},
		looks=True, title="Finding what to open"))
	reg.add(tools.Tool("open_thing", "open one thing found by find_thing, as a double click on it would", openThing, {
		"thing": text("the id of the thing to open, from find_thing", maxLength=120),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
	}, changes=True, before="find_thing", title="Opening it", tell=V))
	simple("windows_part", "open a part of Windows itself with its own key: the Start menu (the Start button), Windows "
		"search, the taskbar, the notification area (system tray), quick settings, the notification center, Task View, the "
		"Run dialog, the Quick Link menu, clipboard history or the emoji panel; says where NVDA is and the key",
		"Opened the Start menu with the Windows key, or Control+Escape. NVDA is now on: Search box, edit.",
		"Opening a part of Windows", dict(askedField), tell=V)
	# What is in a part of Windows itself (placetools.py): the taskbar as Windows 11 reported it on the owner's
	# computer on 2026-11-18, with two made-up hidden icons and desktop icons.
	bar = lambda x: (x, 1198, x + 40, 1258)  # noqa: E731
	taskbarItems = [
		{"name": "Start", "kind": 50000, "cls": "ToggleButton", "aid": "StartButton", "box": bar(708)},
		{"name": "Search", "kind": 50000, "cls": "ToggleButton", "aid": "SearchButton", "box": bar(764)},
		{"name": "Microsoft Edge pinned", "kind": 50000, "cls": "Taskbar.TaskListButtonAutomationPeer", "box": bar(819)},
		{"name": "Claude - 1 running window", "kind": 50000, "cls": "Taskbar.TaskListButtonAutomationPeer", "box": bar(874)},
		{"name": "Show Hidden Icons", "kind": 50000, "cls": "SystemTray.NormalButton", "aid": "SystemTrayIcon", "box": bar(1663)},
		{"name": "Network JoshKennedy\nInternet access", "kind": 50000, "cls": "SystemTray.AccentButton", "aid": "SystemTrayIcon", "box": bar(1708)},
		{"name": "Volume Speakers (Realtek(R) Audio): 20%", "kind": 50000, "cls": "SystemTray.OmniButtonCenter", "aid": "SystemTrayIcon", "box": bar(1743)},
		{"name": "Power Battery status: fully charged 100%", "kind": 50000, "cls": "SystemTray.AccentButton", "aid": "SystemTrayIcon", "box": bar(1778)},
		{"name": "Clock 10:29 PM\n11/18/2026", "kind": 50000, "cls": "SystemTray.OmniButton", "aid": "SystemTrayIcon", "box": bar(1823)},
		{"name": "NVDA", "kind": 50000, "cls": "SystemTray.NormalButton", "box": None, "hidden": True},
		{"name": "Dropbox\nUp to date", "kind": 50000, "cls": "SystemTray.NormalButton", "box": None, "hidden": True}]

	def readPlace(task, asked):
		wish = places.wish(asked) or places.wish(task.request)
		if wish is None:
			raise tools.ToolError("The request does not name a part of Windows that can be read.")
		said = []
		for ident in wish["places"]:
			if ident == places.TRAY:
				said.append(places.trayText(places.tray(taskbarItems), wish["how"], wish["thing"]))
			elif ident == places.TASKBAR:
				said.append(places.taskbarText(places.taskbar(taskbarItems), wish["how"], wish["thing"]))
			elif ident == places.DESKTOP:
				said.append(places.listText(ident, ["This PC", "Recycle Bin", "Steam", "Space Trader"], wish["how"], wish["thing"]))
			else:
				said.append(places.listText(ident, ["Message from Steam: your download finished"], wish["how"], wish["thing"], left=True))
		state["read_place"] = wish
		return " ".join(said)

	if "read_place" not in os.environ.get("VC_WITHOUT", "").split("|"):
		reg.add(tools.Tool("read_place", "say what is in a part of Windows itself, read from what Windows tells screen readers",
			readPlace, dict(askedField), looks=True, title="Reading a part of Windows", tell=V))
	simple("recycle_bin", "say how many things the Recycle Bin holds, how much room they take, and whether it is worth emptying",
		computer.binText(12, 5 << 20, 200 << 30, 500 << 30), "Checking the Recycle Bin", looks=True, tell=V)
	simple("empty_recycle_bin", "empty the Recycle Bin, which deletes what is in it for good; always asks first",
		"Emptied the Recycle Bin: 12 items, 5 MB, deleted for good.", "Emptying the Recycle Bin", dict(askedField), changes=True, tell=V)
	reg.add(tools.Tool("system_volume",
		"turn the volume of the computer itself up or down, set it to a number of percent, mute or unmute it, or say how loud it is",
		systemVolume, dict(askedField), changes=True, title="Working the computer's volume", tell=V))
	reg.add(tools.Tool("list_windows", "list the windows that are open, with the program each belongs to", listWindows,
		{"about": text("what the user asked for, in their own words", maxLength=200, auto=True)}, looks=True,
		title="Listing the open windows"))
	reg.add(tools.Tool("window_action",
		"switch to, close, minimize, maximize or restore one of the windows from list_windows; or minimize every window",
		windowAction, {
			"window": text("the number or the name of the window, from list_windows", maxLength=120),
			"action": text("what to do with the window", enum=computer.WINDOW_ACTIONS, auto=computer.windowActionOf),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="list_windows", title="Working the window", tell=V))
	simple("find_files",
		"say what is in the user's Desktop, Documents, Downloads, Pictures, Music or Videos folder, newest first, or "
		"find their files by a word of the name or by kind",
		"2 items in Downloads. The newest first:\n1. setup.exe, 5 MB, in Downloads, changed November 18, 2026\n"
		"2. report.pdf, 120 KB, in Downloads, changed November 2, 2026", "Looking through your folders", dict(askedField),
		looks=True, tell=V)
	simple("computer_info", "say a fact about the computer itself: free room on its drives, its memory, its processor",
		"Drive C: (System) has 200 GB free of 500 GB, 40 percent. Asked about: {topic}.", "Asking the computer",
		{"topic": text("which fact", enum=computer.TOPICS, auto=computer.topicOf)}, looks=True, tell=V)
	def changeFile(task, asked):
		job = computer.fileTask(asked)
		if job is None:
			raise tools.ToolError("The request does not say what to do with which file or folder.")
		state.setdefault("file", []).append((job["what"], job["new"] or " ".join((job["src"] or {}).get("words", []))))
		return f"Would {job['what']} now: {job['new'] or ' '.join(job['src']['words'])}; the test changes no file."

	reg.add(tools.Tool("change_file",
		"make a new folder or text file, rename, move or copy a file or folder of the user's, or move one to the Recycle Bin",
		changeFile, dict(askedField), changes=True, title="Working on your file", tell=V))
	reg.add(tools.Tool("power", "lock the computer, put it to sleep, restart it, shut it down, sign out of Windows",
		powerTool, dict(askedField), changes=True, title="Locking or shutting down", tell=V))
	reg.add(tools.Tool("check_seen", "check whether something the user names is on the screen; answers yes or no", checkSeen, {
		"what": text("the thing to look for, as the user named it", maxLength=80, auto=computer.seenWhat),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
	}, looks=True, title="Checking whether it is on the screen", tell=V))
	reg.add(tools.Tool("set_control",
		"turn a named option, check box or switch of the program in front on or off, or turn a named slider or value "
		"up or down or to a number", setControl, dict(askedField), changes=True, title="Setting the control", tell=V))
	# A setting for one program, a date in a calendar, and asking by voice (2026-11-18).
	simple("program_settings", "say which programs have NVDA settings of their own, kept in NVDA's configuration profiles",
		profiles.listText([("spacetrader", "spacetrader", True, ["speech rate from 50 to 60."])]),
		"Looking up which programs have their own settings", dict(askedField), looks=True, tell=V)
	simple("remove_program_settings",
		"delete the NVDA settings one program has for itself, so that NVDA behaves there as it does everywhere else",
		profiles.removed("Space Trader", "spacetrader"), "Removing the program's own settings", dict(askedField), changes=True, tell=V)

	def pickDate(task, asked):
		wish = dates.wish(asked, __import__("datetime").date(2026, 11, 18))
		if wish is None:
			raise tools.ToolError("The request names no date.")
		state["date"] = wish["dates"]
		return f"Chose {dates.said(wish['dates'][0])} in the calendar; the test presses nothing."

	reg.add(tools.Tool("pick_date",
		"choose a date in a calendar or date picker that is showing in the web page or window in front, by pressing its "
		"buttons for the month and the day; for a calendar that cannot be worked with the keyboard",
		pickDate, dict(askedField), changes=True, title="Choosing the date in the calendar", tell=V))
	simple("voice_info", "say whether asking VisionClaw by voice is set up, which speech model it listens with, and how to speak a request",
		"Asking by voice is ready. VisionClaw listens with the speech model Qwen3-ASR 0.6B, which runs on this computer's "
		"processor. To ask by voice, press NVDA+Alt+V.", "Looking up asking by voice", dict(askedField), looks=True, tell=V)
	simple("get_voice", "download the speech model for asking VisionClaw by voice, after a question",
		"The speech model Qwen3-ASR 0.6B is on this computer now; the test downloads nothing.", "Getting the speech model",
		dict(askedField), tell=V)
	simple("remove_voice", "delete the speech model for asking by voice from this computer",
		"Deleted the speech model Qwen3-ASR 0.6B; the test deletes nothing.", "Deleting the speech model", dict(askedField),
		changes=True, tell=V)
	# Working through a task, VisionClaw's own voice, and the two add-ons it works together with (2026-11-18).
	def workThrough(task, asked):
		goal = walking.goalOf(asked)
		if len(goal.split()) < 2:
			return walking.NO_GOAL
		state["worked through"] = goal
		return f"Step 1: pressed Insert tab. New here: Attach File button. The test presses nothing; it was asked to: {goal}."

	reg.add(tools.Tool("work_through",
		"work through a task with the user in the program or web page in front when they are stuck or the usual way "
		"does not work: finds the thing that leads to what they want, says its key, presses it if they say yes, and "
		"goes on step by step", workThrough, dict(askedField), changes=True, title="Working through it with you", tell=V))
	simple("own_voice",
		"give VisionClaw a voice of its own by opening NVDA's Speech settings for it, turn that voice on or off, remove "
		"it, or say whether it has one",
		"NVDA's Speech settings are open, for VisionClaw's voice; the test opens nothing.", "Looking at VisionClaw's own voice",
		dict(askedField), tell=V)

	def classicSpeech(task, asked):
		wish = partners.classicWish(asked) or {"what": partners.INFO}
		state["classic"] = wish
		return f"ClassicSpeech: {wish['what']}; the test changes nothing."

	reg.add(tools.Tool("classic_speech",
		"with the add-on ClassicSpeech: change how much NVDA says about each control (Beginner, Intermediate, "
		"Advanced), list or switch its speech and sound schemes or turn them on or off, open its windows, or say how "
		"it is set", classicSpeech, dict(askedField), title="Working ClassicSpeech", tell=V))

	def jawsHelp(task, asked):
		wish = partners.jawsWish(asked) or {"what": partners.INFO}
		state["jaws"] = wish
		return "In JAWS, Insert+F7 is: Displays a list of links on the page. In NVDA that is: Open the Elements List, with NVDA+f7."

	reg.add(tools.Tool("jaws_help",
		"with the add-on JAWS Migration Assistant: say what a JAWS keystroke or a JAWS command is in NVDA, what was "
		"brought over from JAWS, or which commands that add-on has", jawsHelp, dict(askedField), looks=True,
		title="Asking the JAWS Migration Assistant", tell=V))
	# The jobs that had no stand-in until 2026-11-18, so that a model could not choose them here and its choice of
	# another looked like its mistake (tests/eval_routing.py found eleven). Each takes what the real tool takes.
	simple("read_text", "read the exact text shown in the window, on the screen or in the focused control",
		"Text in the window: Space Trader - Main Menu. New Game. Load Game. Options. Quit.", "Reading the text",
		{"target": text("where to read", enum=["window", "screen", "control"], auto=lambda part: "window")}, looks=True, tell=V)
	simple("type_text", "type text into the program in front", "Typed: {text}", "Typing the text",
		{"text": text("the text to type", maxLength=400)}, changes=True, tell=V)
	simple("press_keys", "press keyboard keys in the program in front", "Pressed {keys}.", "Pressing keys",
		{"keys": text("the keys, like control+s or alt+f4", maxLength=80)}, changes=True, tell=V)
	simple("name_control", "give the focused button, which has no useful name, a name", "The focused button is now called {name}.",
		"Naming the button", {"name": text("the name to give it", maxLength=60)}, changes=True, tell=V)
	simple("create_addon", "write a small NVDA add-on for what the user asked, check it, and turn it on after asking",
		"Wrote the add-on and turned it on after you said yes.", "Writing the add-on", dict(askedField), changes=True, tell=V)
	simple("remove_helper", "remove a helper or add-on VisionClaw made", "Removed {name}.", "Removing it",
		{"name": text("the name, from list_helpers", maxLength=80)}, changes=True, before="list_helpers", tell=V)
	simple("export_addon", "save an add-on VisionClaw wrote as a file", "Saved {name} as a file on your desktop.", "Saving the add-on",
		{"name": text("the name, from list_helpers", maxLength=80)}, before="list_helpers", tell=V)
	simple("learn_app", "go online after a question and learn about the program in front or one named, and keep notes",
		"Learned about Space Trader and kept notes.", "Learning about the program", dict(askedField), changes=True, tell=V)
	simple("note_page", "add what the web page in the browser says to the notes on a program", "Added the page to the notes.",
		"Adding the page to the notes", dict(askedField), changes=True, tell=V)
	simple("app_notes", "say which programs VisionClaw has notes on, or open them", "VisionClaw has notes on: Space Trader.",
		"Listing the notes", dict(askedField), looks=True, tell=V)
	simple("forget_notes", "delete notes on a program after a question", "Deleted the notes on Space Trader.",
		"Deleting the notes", dict(askedField), changes=True, tell=V)

	def modelAdvice(task, asked):
		from visionClaw.claw import advice
		state["model_advice"] = asked
		return advice.advise(asked or task.request, catalog.CATALOG, {VISION: "qwen3.5-9b", CODER: "qwen3.5-9b-coder"},
			{"qwen3.5-9b", "qwen3.5-9b-coder"}, 8151, 31, {"qwen3.5-9b": (31, 4)}, (), True)

	reg.add(tools.Tool("model_advice", "suggest which of VisionClaw's models fits what the user wants to do; changes nothing",
		modelAdvice, dict(askedField), looks=True, title="Suggesting a model", tell=V))
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
	# The user's own words and casual words understood (claw/understand.py, 1.11.0). None is from an evaluation set.
	"When I say shh, I mean stop talking. >> Which words have I taught you?",
	"Kill the typing echo please.",
	"Give the screen a once-over.",
	# A setting for one program only, a date in a calendar, asking by voice, and requests that follow the one
	# before them (2026-11-18). Requests joined by " >> " are asked one after the other of the same VisionClaw.
	"Make NVDA speak a little faster, only in this program.",
	"Turn off the typing echo just in this app.",
	"When I'm in Space Trader, set punctuation to all.",
	"Turn off the typing echo in this program.",
	"Which programs have their own settings?",
	"Remove the settings for this program.",
	"Pick the fourteenth of March twenty twenty-seven in this calendar.",
	"Choose next Friday in the date picker.",
	"Can I ask you by voice?",
	"Download the speech model.",
	"Delete the speech model.",
	"Turn the computer's volume up a bit. >> Do that again. >> The other way. >> Say that again.",
	"Make NVDA speak a little faster. >> A bit more. >> Too fast.",
	"Look through my downloads folder. >> Open the second one.",
	"How do I read the title of this window? >> And the status bar?",
	"Turn off the typing echo. >> The same in Word.",
	# Everywhere or only here in JAWS's own words, working through a task, a voice of its own, and the two add-ons,
	# which the test takes to be running (2026-11-18).
	"Speak words as I type in every application.",
	"Stop announcing capital letters in Space Trader.",
	"Make NVDA speak a little faster everywhere.",
	"I'm stuck, I want to attach a file to this email.",
	"Walk me through exporting this as a PDF.",
	"I can't find how to change the font here.",
	"Customise your voice.",
	"Turn off your own voice.",
	"What is JAWS's Insert+F7 in NVDA?",
	"What is the JAWS say line command in NVDA?",
	"Set ClassicSpeech to advanced.",
	"Which speech schemes do I have?",
	"Switch to the scheme Classic.",
	"Open voice profiles.",
	# Working the computer itself, several things in one request, things that depend on something, and a named
	# control of the program in front (2026-11-18). The first five are the owner's own words.
	"first, look at my screen. If you see recycle bin, open it.",
	"check and see if my recycle bin needs to be emptied or not.",
	"Go into my windows settings, turn down my system volume, close windows settings, then go to gmail.com in my google "
	"chrome and tell me how many emails I have.",
	"find the settings button in this inaccessible app, then adjust the volume and turn it up a bit and turn the equalizer "
	"down, then close settings.",
	"find the settings button, and then in this multipage dialog, turn on my nvidia gpu for this program, and turn off the "
	"media keys on my keyboard.",
	"Open Notepad.",
	# The parts of Windows itself (2026-11-18). The first four are the owner's own words, which all failed in 1.7.1.
	"click the start button.",
	"click the windows start button using the mouse.",
	"look at the current screen, then click the windows start button with the mouse.",
	"open the windows start menu.",
	"Go to the system tray.",
	"Open quick settings.",
	# What is in a part of Windows itself (2026-11-18). The first is the owner's own words, which were answered from a
	# picture of the desktop: "I cannot see the system tray in this image".
	"tell me all objects that are currently in the system tray.",
	"What icons are in my notification area?",
	"Is NVDA running in the system tray?",
	"How many icons are in the system tray?",
	"Which programs are on my taskbar?",
	"What icons are on my desktop?",
	"Read my notifications.",
	"Right-click the volume icon in the system tray.",
	"What is the system tray?",
	"Describe the system tray for me.",
	"look at my screen, then tell me what is in the system tray.",
	"Launch Steam.",
	"Open my downloads folder.",
	"Open the Recycle Bin.",
	"Start Space Trader.",
	"Is my recycle bin full?",
	"Empty the recycle bin.",
	"Switch to Firefox.",
	"Close this window.",
	"Minimize all windows.",
	"What is in my downloads folder?",
	"How much disk space do I have left?",
	"Which programs are running?",
	"Restart my computer.",
	"Turn the computer's volume up a lot.",
	"If notepad is open, close it.",
	"If my recycle bin is not empty, empty it.",
	"Turn on dark mode in this program.",
	"Can you empty my recycle bin?",
	# The user's own files: made, renamed, moved, copied, and moved to the Recycle Bin (2026-11-18).
	"Create a folder called Taxes in my documents.",
	"Rename the file budget to Budget 2026.",
	"Move the file report.pdf from my downloads to my documents.",
	"Copy the file budget to my desktop.",
	"Delete the file old notes.",
	"Delete notes.txt.",
	"Create a folder called Receipts on my desktop, then move the file report.pdf to my desktop.",
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
	# The page as a whole and what stops a form (2026-11-18): plain code answers, a model only chooses the job.
	"Explore this page for me.",
	"What is the best way to get around this page?",
	"How is this page laid out?",
	"Why won't this form submit?",
	"Which fields did I miss in this form?",
	"Summarize this page.",
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
	# What is worked by neither a click nor a drag: held down, hovered over, swiped, clicked at the right moment.
	"Press and hold the New Game button for 2 seconds.",
	"Hover over the Options button.",
	"Middle-click the Options button.",
	"Swipe left on the Options button.",
	"Draw a circle in this window.",
	"Click the Quit button as soon as it changes.",
	"Click the New Game button 5 times.",
	"Zoom in.",
	# What no mouse pointer does: fingers, pressure, a game that reads the mouse directly; and a game controller.
	"Pinch the Options button with two fingers.",
	"Swipe left with three fingers.",
	"Press hard on the New Game button for 2 seconds.",
	"Draw a line to the right with the pressure rising.",
	"Turn left.",
	"Look up a little.",
	"This game has its own mouse pointer.",
	"The mouse turns the view in this game.",
	"Is a game controller connected?",
	"What do the buttons on my controller do?",
	"Turn on controller mode.",
	"Make the X button on my controller click the New Game button.",
	"Give this program a hotkey, NVDA+alt+1, that clicks the Options button.",
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
	# The guides themselves, the add-ons by what is wanted, and NVDA Coach (2026-11-18).
	"Which developer guides do I have?",
	"Delete the developer guides.",
	"Give me a hint about browse mode.",
	"Coach me on reading the current line.",
	"Open NVDA Coach.",
	"Is there an add-on that tells me the date?",
	# Free training material, another screen reader, and a hand on the mouse (2026-11-18).
	"What can you download for me?",
	"Get the free NVDA training material.",
	"Which training material do I have?",
	"Delete the training material.",
	"I'm coming from JAWS. What is the JAWS cursor called in NVDA?",
	"I am using my real mouse. How do I hear what is under the pointer?",
	"Do a deep query of this control and tell me how a sighted person works it.",
	"What model is installed?",
	"Which AI model are you using?",
	# Which model fits what the user wants to do (2026-11-19): suggested by plain code, nothing changed.
	"Which model should I use for describing pictures?",
	"Should I switch to a smaller model? The 9B feels slow.",
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
	# The two add-ons VisionClaw works together with are taken to be running, unless VC_NO_PARTNERS is set.
	partners.setInstalled([] if os.environ.get("VC_NO_PARTNERS") else [partners.JAWS, partners.CLASSIC])
	print("vision:", rt.entry(VISION)["name"], "| coder:", rt.entry(CODER)["name"])
	asked = []

	def askUser(question, choices):
		asked.append(question)
		print("   ASKED:", question, choices)
		return 0

	try:
		# With VC_ONLY set, only the requests that contain one of its parts (separated by |) are run.
		only = [part.lower() for part in os.environ.get("VC_ONLY", "").split("|") if part]
		for session in REQUESTS:
			if only and not any(part in session.lower() for part in only):
				continue
			state = {}
			orch = orchestrator.Orchestrator(rt, makeRegistry(rt, state), askUser, lambda: "Program: spacetrader. Window title: Space Trader - Main Menu. Focused control: button, New Game.", Memory("nul"))
			following = session.split(" >> ")
			for request in following:
				runOne(orch, request, reasoning, state, len(following) > 1)
	finally:
		rt.stop()


def runOne(orch, request, reasoning, state, follows):
	"""One request of a session. The requests of a session are asked of the same VisionClaw, one after the other,
	so that one can follow the one before it."""
	# A fifth argument says whether the model is asked one small question at a time: auto, always or never.
	orch.stepwise = lambda: sys.argv[5] if len(sys.argv) > 5 else "auto"
	orch.memories = KEPT
	orch.program = lambda: "spacetrader"
	orch.skills = SKILLS
	# Where the user is, for the router: a game in front, no web page, no controller.
	orch.facts = lambda: {router.WEB: False, router.CONTROLLER: False, router.DIRECT: False}
	if understand is not None:
		orch.understanding = understand.Grammar(None)
		orch.workFolder = WORK
	task = taskModule.Task(request, reasoning=reasoning)
	start = time.time()
	orch.run(task)
	print(f"\n=== {request}  -> {task.state} in {time.time() - start:.1f}s, changed: {state}")
	for _seconds, kind, text in task.log:
		if kind in (taskModule.TALK, taskModule.DETAIL, taskModule.ERROR, taskModule.THINK):
			print(f"   [{kind}] {text}")
	if follows and task.request != request:
		print(f"   TAKEN AS: {task.request}")
	print("   ANSWER:", task.answer)


if __name__ == "__main__":
	main()
