# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - working through a task with the user when the usual path is not clear (claw/guide.py). The tool
# work_through looks at what the program in front offers, in three places, the surest first: the web page as
# NVDA keeps it in browse mode, the window's controls as NVDA knows them, and, where NVDA knows next to nothing,
# the texts and icons in the window's picture. It presses a thing the way NVDA does, or with the mouse for a
# thing that is only in the picture, and only after the user said yes to that step.
# It stays in the program it began in, and never works VisionClaw's own windows or NVDA's.

import time

import addonHandler
import api
import config

from . import fixruntime
from .claw import guide, policy, prompts
from .claw.fixmatch import labelOf
from .claw.llm import LLM, LLMError, clip
from .claw.tools import ToolError
from .vclog import log

addonHandler.initTranslation()

SETTLE_SECONDS = 0.8
# Fewer named things than this in what NVDA knows of a window, and its picture is read as well.
FEW = 3
MAX_NODES = 1500
# NVDA's own windows, and with them VisionClaw's: never worked.
OWN_APPS = ("nvda", "nvda_slave", "nvda_dmp")
CHOOSE_SYSTEM = (
	prompts.IDENTITY + " The user wants to get something done in the program they are in. You are given what they "
	"want and numbered things of its window that can be pressed. Choose the one thing to press next to get there, by "
	"its number. A thing that only shares a word with what they want does not lead there. If none of them leads "
	"there, choose 0.")


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def inFront():
	"""(the program in front by the name of its file, its window's title). Main thread."""
	fg = _safe(api.getForegroundObject)
	focus = _safe(api.getFocusObject)
	module = _safe(lambda: focus.appModule) or _safe(lambda: fg.appModule)
	return str(_safe(lambda: module.appName) or ""), " ".join(str(_safe(lambda: fg.name) or "").split())


def ownWindow():
	"""Whether one of VisionClaw's own windows is in front: the Ask window, a question it asks, its models,
	skills or memories window. They are windows of NVDA whose title names VisionClaw. Main thread."""
	program, title = inFront()
	return program.lower() in OWN_APPS and "visionclaw" in title.lower()


def _fromNodes(nodes, make):
	things = []
	for node in nodes[:MAX_NODES]:
		kind = guide.KINDS.get(node.get("role") or "")
		states = node.get("states") or ()
		if kind is None or node.get("hidden") or "INVISIBLE" in states:
			continue
		name = labelOf(node)
		if not name:
			continue
		obj = node.get("obj")
		key = _safe(lambda: obj.keyboardShortcut) if obj is not None else ""
		things.append(guide.Thing(name, kind, make(node), key or "", "UNAVAILABLE" not in states))
	return things


def _windowThings():
	"""The things of the window in front that NVDA knows. Main thread."""
	nodes = list(fixruntime.windowNodes(api.getForegroundObject()))
	return _fromNodes(nodes, lambda node: ("window", node["obj"]))


def _pressObject(obj):
	fixruntime.pressObject(obj)


def _pressOnPage(document, node):
	fixruntime.locate(document, node)
	fixruntime.activateOnPage(document, node)


def register(add, plugin, text, onMain, screen):
	"""Add the tool. add and text are nvdatools' own; onMain runs a function on NVDA's main thread."""

	def look(task):
		"""(the things in front, the window's title, the program)."""
		from . import pagetools
		task.check()
		program, title = onMain(inFront)
		found = onMain(pagetools._where)
		if found:
			document = found[0]
			things = _fromNodes(pagetools.pageNodes(task, document, onMain), lambda node: ("page", document, node))
			if things:
				return things, title, program
		things = onMain(_windowThings)
		if len([thing for thing in things if thing.usable]) < FEW and config.conf["visionClaw"]["useOcr"]:
			# NVDA knows next to nothing of this window: its picture is read for texts and icons.
			try:
				result = screen.items()
				for item in getattr(result, "items", ()) or ():
					if item.get("web") is None:
						name = item.get("plain") or item.get("name") or item.get("text") or ""
						things.append(guide.Thing(name, "in the window's picture", ("picture", result, item)))
			except ToolError:
				pass
			except Exception:
				log.debugWarning("VisionClaw: the window's picture could not be read for things to press", exc_info=True)
		return things, title, program

	def press(task, thing):
		task.check()
		ref = thing.ref
		if ref[0] == "window":
			onMain(_pressObject, ref[1])
		elif ref[0] == "page":
			onMain(_pressOnPage, ref[1], ref[2])
		else:
			from . import nvdatools
			onMain(nvdatools.Screen.click, ref[1], ref[2])

	def choose(task, goal, things):
		"""A model's choice among a few things, or None. A very small model is not given "none of these": it takes
		that at random; for it plain code's best is taken."""
		entry = _safe(lambda: plugin.runtime.entry(policy.LEAD)) or {}
		if entry.get("suggest") is False:
			return 0
		numbered = "\n".join(f"{number}. {clip(thing.said(), 80)}" for number, thing in enumerate(things, 1))
		user = f"The user wants to: \"{clip(goal, 300)}\"\nThings in the window:\n{numbered}\nWhich one is pressed next? Give its number, or 0 if none leads there."
		schema = {
			"type": "object", "properties": {"thing": {"type": "integer", "enum": list(range(0, len(things) + 1))}},
			"required": ["thing"]}
		try:
			chosen = int(LLM(plugin.runtime, task).json(policy.LEAD, CHOOSE_SYSTEM, user, schema, maxTokens=20).get("thing"))
		except (LLMError, TypeError, ValueError):
			return None
		return chosen - 1 if chosen >= 1 else None

	def workThrough(task, asked):
		goal = guide.goalOf(asked or task.request)
		if len(goal.split()) < 2:
			return guide.NO_GOAL
		if onMain(ownWindow):
			return guide.NOT_OWN
		said, pressed = guide.walk(
			goal, lambda: look(task), lambda thing: press(task, thing), lambda goal, things: choose(task, goal, things),
			plugin.clawAsk, task.check, lambda: time.sleep(SETTLE_SECONDS))
		return said or f"VisionClaw found nothing to do for this: {goal}."

	add("work_through",
		"work through a task with the user in the program or web page in front when they are stuck or the usual way "
		"does not work: finds the thing that leads to what they want, says its key, presses it if they say yes, and "
		"goes on step by step",
		workThrough, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Working through it with you")
