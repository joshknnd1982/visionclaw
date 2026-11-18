# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what the user asked VisionClaw to remember, and the user's library of documents, as tools.
# Memories are Markdown files in the folder "memories" of VisionClaw's data, with an index, MEMORY.md
# (claw/memories.py). What is kept is the user's own words; no model writes a memory, and none is needed:
# plain code takes out "remember that" and turns "my" into "your". The library is the folder "library", whose
# documents are looked things up in with everything else (claw/library.py, asktools.py). Nothing here goes
# online.

import os
import re

import addonHandler
import config

from . import asktools
from .claw import debuglog, library, memories
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()

_OPEN = re.compile(r"\b(open|show me the (file|folder)|edit|change them|see the (file|folder))\b", re.IGNORECASE)
# The user wants to go through the memories and delete some.
_MANAGE = re.compile(r"\b(manage|go through|clean up|tidy|choose|pick|some of)\b", re.IGNORECASE)


def kept_words(which):
	"""The words of a request to forget, without those that only ask."""
	return re.sub(r"\b(forget|delete|remove|erase|clear|memor(y|ies)|my|your|of|the|please|visionclaw)\b", " ", which or "",
		flags=re.IGNORECASE)


def when():
	"""When memories may be kept: memories.AUTO, ASKED or OFF, as the user chose in the settings."""
	try:
		chosen = config.conf["visionClaw"]["remember"]
	except Exception:
		chosen = memories.AUTO
	return chosen if chosen in memories.WHEN else memories.AUTO


def forCoder(plugin, purpose):
	"""For the model that writes or repairs an add-on: the memories, the library and the notes on accessibility
	interfaces that belong with its purpose, short (claw/library.forCoder). Never raises."""
	try:
		who = _mainThread["run"](asktools.programNow) if _mainThread["run"] else {}
	except Exception:
		who = {}
	names = [name for name in (who.get("app"), who.get("product")) if name and name != "unknown"]
	try:
		text = library.forCoder(plugin.memories, plugin.library, plugin.knowledge, purpose, names)
	except Exception as e:
		debuglog.error("memories", "What the add-on writer is told could not be put together", e)
		return ""
	if text:
		debuglog.log("memories", f"Given to the add-on writer: {text.strip()!r}")
	return text


# How the tools run something on NVDA's main thread; set when the tools are registered.
_mainThread = {"run": None}


def register(plugin, add, text, onMain, confirm):
	"""The tools for memories and the library. add and text are the helpers of nvdatools.build."""
	kept = plugin.memories
	shelf = plugin.library
	_mainThread["run"] = onMain

	def remember(task, fact, asked):
		if when() == memories.OFF:
			return (
				"Keeping memories is switched off in VisionClaw's settings, so nothing was kept. It can be switched "
				"on there, under Remember things.")
		fact = memories.factOf(fact or asked)
		if not memories.words(fact):
			return "Nothing to remember was said. Say remember, followed by what VisionClaw should remember."
		program = ""
		if memories.kindOf(fact) == memories.PROGRAM:
			program = onMain(asktools.programNow)["app"]
			if program == "unknown":
				program = ""
		try:
			entry, replaced = kept.add(fact, asked=asked, program=program)
		except ValueError as e:
			raise ToolError(str(e))
		except OSError as e:
			raise ToolError(f"The memory could not be saved: {e}")
		told = f"VisionClaw will remember this: {entry.text()}"
		if replaced:
			told += f" It replaces what it remembered before: {replaced.text()}"
		return told + " To make it forget, say forget that."

	add("remember",
		"keep something the user asks VisionClaw to remember for later: something about them, how they like things "
		"done, a program, or where to find something; kept in their own words as a file they can read",
		remember, {
			"fact": text("what is to be remembered, in the user's own words", maxLength=500, auto=memories.factOf),
			"asked": text("what the user asked for, in their own words", maxLength=500, auto=True),
		}, title="Remembering", tell=VERBATIM)

	def listMemories(task, asked):
		if _OPEN.search(asked or "") or _MANAGE.search(asked or ""):
			from . import memoriesui
			onMain(memoriesui.show, plugin)
			return (
				"The window of memories is open. Each memory is in the list, with a check box. Check the ones to "
				"forget and press Forget checked memories, or press Forget all and start over. "
				f"They are kept as files in the folder {kept.folder}.")
		return kept.listText() + (
			f"\nThey are kept as files in the folder {kept.folder}. To forget some or all of them, ask to open your "
			"memories, or say forget and what to forget.")

	add("memories",
		"say what VisionClaw remembers that the user asked it to remember, or open the list so the user can read it",
		listMemories, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking at what VisionClaw remembers", tell=VERBATIM)

	def forgetMemory(task, which):
		if not kept.all():
			return "VisionClaw remembers nothing, so there is nothing to forget."
		if _MANAGE.search(which or "") and not memories.words(_MANAGE.sub(" ", kept_words(which))):
			# "Delete some of my memories": the user chooses them in the window.
			from . import memoriesui
			onMain(memoriesui.show, plugin)
			return (
				"The window of memories is open. Check the ones to forget and press Forget checked memories, or press "
				"Forget all and start over.")
		chosen = kept.chosen(which)
		if not chosen:
			return "None of the memories is about that. " + kept.listText()
		said = "; ".join(entry.text() for entry in chosen[:5]) + ("" if len(chosen) <= 5 else f"; and {len(chosen) - 5} more")
		if len(chosen) > 1 and len(chosen) == len(kept.all()):
			# Everything at once is always asked about, whatever the settings say.
			# Translators: Asked before every memory is deleted. {count} is how many.
			question = _("Forget everything VisionClaw remembers, {count} memories, and start over? The files are deleted "
				"from this computer.").format(count=len(chosen))
			# Translators: The two choices before every memory is deleted.
			if plugin.clawAsk(question, [_("Yes, forget everything"), _("No, keep them")]) != 0:
				return "You said no, so VisionClaw still remembers everything."
		else:
			# Translators: Asked before memories are deleted. {memories} is what is remembered.
			confirm(_("Forget this? {memories} The files are deleted from this computer.").format(memories=said))
		gone = [entry for entry in chosen if kept.remove(entry.name)]
		kept.writeIndex()
		if not gone:
			raise ToolError("The memories could not be deleted. They are in the folder " + kept.folder + ".")
		debuglog.log("memories", f"Forgot {len(gone)} memories after the request {which!r}")
		left = len(kept.all())
		return f"Forgotten: {'; '.join(entry.text() for entry in gone[:5])}." + (
			" VisionClaw remembers nothing now." if not left else f" VisionClaw still remembers {left} other things.")

	add("forget_memory",
		"delete something VisionClaw remembers: what the user names, the last thing it remembered, or everything",
		forgetMemory, {"which": text("what to forget, in the user's own words", maxLength=300, auto=True)},
		changes=True, title="Forgetting", tell=VERBATIM)

	def library(task, asked):
		shelf.prepare()
		if _OPEN.search(asked or "") or re.search(r"\b(add|put)\b", asked or "", re.IGNORECASE):
			try:
				os.startfile(shelf.folder)
			except OSError as e:
				raise ToolError(f"The library could not be opened ({e}). It is the folder {shelf.folder}.")
			return (
				f"The library folder is open in a window: {shelf.folder}. Copy documents into it, such as the manual of "
				"a program or a game, as Markdown, text, saved web pages or Word documents. VisionClaw reads them the next "
				"time you ask a question. " + shelf.listText().split(" The library is the folder")[0])
		return shelf.listText()

	add("library",
		"say which documents are in VisionClaw's library, that it looks things up in, or open the library's folder so "
		"the user can add documents",
		library, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking at your library", tell=VERBATIM)
