# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - scratchpads as tools (claw/scratchpad.py): a task scratchpad started, written on, checked off, read,
# finished and deleted in the user's own words; a question answered from what is written on the scratchpads; which
# program or website the user is in, whose learning scratchpad is used; and the lines of the scratchpads given to
# look_up as passages. Every scratchpad is a Markdown file in the folder "scratchpads" of VisionClaw's data, inside
# the add-on's folder, so it goes with the user into a portable copy. What the user asks of a scratchpad is read from
# their words by plain code; no model writes on a scratchpad here. Nothing here goes online.

import os
import re
from urllib.parse import urlparse

import addonHandler
import api

from .claw import lookup, match, scratchpad
from .claw.tools import SUMMARIZE, VERBATIM, ToolError
from .nvdatools import _safe, onMain

addonHandler.initTranslation()

# Words that mean the last answer, when the user asks for it to be written down: "write that on the scratchpad".
_LAST_ANSWER = re.compile(
	r"^\W*(that|this|it|what you (found|said|told me|just said|found out)|the (answer|last answer|result))\W*$", re.IGNORECASE)


def openFile(path):
	"""Hand a scratchpad's file or folder to Windows, which opens it in the user's own program. Stood in for in tests."""
	os.startfile(path)


def subjectNow():
	"""The program or website the user is in, as its learning scratchpad is named: the web site's own name where the
	user is on a web page (its address without www), else the name the program's maker gave it, else its file's name.
	Main thread."""
	document = _safe(lambda: api.getFocusObject().treeInterceptor)
	address = str(_safe(lambda: document.documentConstantIdentifier, "") or "") if document is not None else ""
	if address.startswith(("http://", "https://")):
		host = _safe(lambda: urlparse(address).hostname, "") or ""
		if host:
			return host[4:] if host.startswith("www.") else host
	module = _safe(lambda: api.getFocusObject().appModule) or _safe(lambda: api.getForegroundObject().appModule)
	product = " ".join(str(_safe(lambda: module.productName, "") or "").split())
	app = str(_safe(lambda: module.appName, "") or "").strip()
	if app in ("nvda", "") and not product:
		return ""
	return product or app


def passages(plugin, question, program=""):
	"""The lines of the scratchpads that may answer a question, as look_up's passages: the open task's, what was learned
	in this program or website, lines learned elsewhere that share a topic with the question, and, only where the
	question points back at a description ("the picture you described"), the descriptions. Never a fault."""
	pads = getattr(plugin, "pads", None)
	if pads is None:
		return []
	try:
		kinds = (scratchpad.TASK, scratchpad.LEARNING) + ((scratchpad.DESCRIBED,) if scratchpad.pointsBack(question) else ())
		notes = pads.notesFor(question, program, 6, kinds)
	except Exception:
		return []
	return [lookup.Passage(lookup.PAD, "", note.text, scratchpad.noteSource(None, note), lead=True) for note in notes]


def _keeping():
	try:
		import config
		return bool(config.conf["visionClaw"]["scratchpads"])
	except Exception:
		return False


def describeOn(plugin, what, text, question=""):
	"""A description written on the descriptions scratchpad, where the user lets VisionClaw keep scratchpads. Never a
	fault: a description is said whether or not it is kept."""
	pads = getattr(plugin, "pads", None)
	if pads is None or not _keeping() or not str(text or "").strip():
		return
	program = _safe(lambda: onMain(subjectNow, timeout=2), "") or ""
	try:
		pads.describe(what, f"{text} (Asked: {question})" if question else text, program)
	except Exception:
		pass


def answeredOn(plugin, question, answer):
	"""A question answered about the last description, written under it on the descriptions scratchpad."""
	pads = getattr(plugin, "pads", None)
	if pads is None or not _keeping():
		return
	try:
		pads.answered(question, answer)
	except Exception:
		pass


def register(add, plugin, text, onMain, confirm, mustAgree):
	"""The tools for scratchpads. The first three are the helpers of nvdatools.build."""

	def where():
		return _safe(lambda: onMain(subjectNow), "") or ""

	def lastAnswer():
		last = _safe(lambda: plugin.orchestrator.last)
		return " ".join(str(getattr(last, "answer", "") or "").split())

	def chosenPad(kind):
		"""The scratchpad the words mean: the open task (or the one finished last), the learning scratchpad of the
		program or website the user is in, or the descriptions."""
		pads = plugin.pads
		if kind == scratchpad.LEARNING:
			return pads.learning(where())
		if kind == scratchpad.DESCRIBED:
			return pads.descriptions()
		pad = pads.active()
		if pad is None:
			finished = [found for kind_, found in pads.everything() if kind_ == scratchpad.TASK]
			pad = max(finished, key=lambda found: found.changed) if finished else None
		return pad

	def scratchpadTool(task, asked):
		# The part's own words decide, never the rest of the request.
		want = scratchpad.wish(asked)
		if want is None or want["do"] == scratchpad.SEARCH:
			raise ToolError("The words ask nothing to be done with a scratchpad. Name the scratchpad and what to do with it.")
		pads = plugin.pads
		do = want["do"]
		if do == scratchpad.START:
			pad, before = pads.start(want.get("title") or "", todo=want.get("items") or ())
			said = [f"Started the task scratchpad {pad.title}."]
			if pad.todo:
				said.append(f"{len(pad.todo)} things to do: " + "; ".join(f"{n}, {t}" for n, (t, _d) in enumerate(pad.todo, 1)) + ".")
			said.append("VisionClaw reads it with every request while it is open, and writes down what was done. "
				"Say what's next, check off and a number, or close the scratchpad when the task is finished.")
			if before is not None:
				said.append(f"The scratchpad {before.title} was open; it is finished now, and kept.")
			return " ".join(said)
		if do == scratchpad.NEXT:
			return scratchpad.nextText(pads.active())
		if do == scratchpad.LIST:
			return scratchpad.listText(pads.everything())
		if do == scratchpad.NOTE:
			words = want.get("text") or ""
			if _LAST_ANSWER.match(words):
				words = lastAnswer()
				if not words:
					return "There is no answer before this one to write down. Say what to write after the word that."
			active = pads.active()
			program = where()
			if want.get("pad") == scratchpad.LEARNING or active is None:
				if not program:
					return ("No task scratchpad is open, and the program you are in could not be told, so nothing was written. "
						"To start a task scratchpad, say start a scratchpad for, then the task.")
				pads.learn(program, words, scratchpad.BY_YOU)
				return f"Written on the scratchpad for {program}: {words}"
			active.add(scratchpad.Note(words, scratchpad.BY_YOU, program))
			pads.save(active)
			return f"Written on your task scratchpad {active.title}: {words}"
		if do == scratchpad.ADD:
			active = pads.active()
			if active is None:
				return "No task scratchpad is open, so nothing was added. To start one, say start a scratchpad for, then the task."
			added = [item for item in want.get("items") or () if item]
			active.todo += [[item, False] for item in added]
			pads.save(active)
			number, nextOne = active.nextItem()
			return (f"Added to {active.title}: " + "; ".join(added) + f". {len(active.todo)} things are on its list."
				+ (f" Next: {number}, {nextOne}." if nextOne else ""))
		if do == scratchpad.CHECK:
			active = pads.active()
			if active is None:
				return "No task scratchpad is open, so there is nothing to check off."
			if not active.todo:
				return f"Nothing is on the list of {active.title}, so nothing was checked off."
			number = want.get("number")
			at = None
			if number == -1:
				at = len(active.todo) - 1
			elif number:
				at = number - 1 if 1 <= number <= len(active.todo) else None
				if at is None:
					return f"{active.title} has {len(active.todo)} things on its list, so there is no number {number}."
			elif want.get("text"):
				at = match.best(want["text"], [item for item, _done in active.todo])
			if at is None:
				nextNumber, _text = active.nextItem()
				at = None if nextNumber is None else nextNumber - 1
			if at is None:
				return f"Everything on {active.title} is checked off already."
			active.todo[at][1] = True
			pads.save(active)
			number, nextOne = active.nextItem()
			return (f"Checked off {at + 1}, {active.todo[at][0]}. "
				+ (f"Next: {number}, {nextOne}." if nextOne else "Everything on the list is done. Say close the scratchpad when the task is finished."))
		if do == scratchpad.FINISH:
			pad = pads.finish()
			if pad is None:
				return "No task scratchpad is open, so there is nothing to finish."
			return (f"The task scratchpad {pad.title} is finished. It is kept in the folder scratchpads of VisionClaw's data, "
				"and VisionClaw no longer reads it with every request.")
		if do == scratchpad.OPEN_FILE:
			pad = chosenPad(want.get("pad"))
			target = pad.path if pad is not None and pad.path and os.path.isfile(pad.path) else pads.folder
			os.makedirs(pads.folder, exist_ok=True)
			try:
				openFile(target)
			except OSError as e:
				raise ToolError(f"Windows could not open it: {e}")
			return ("Opened the scratchpad in your program for text files." if target != pads.folder
				else "There is no such scratchpad yet, so the folder of scratchpads was opened.")
		if do == scratchpad.DELETE:
			kind = want.get("pad")
			if kind in ("all", scratchpad.FINISHED):
				chosen = [pad for found, pad in pads.everything()
					if kind == "all" or (found == scratchpad.TASK and pad.status == scratchpad.FINISHED)]
				if not chosen:
					return "There is no such scratchpad, so nothing was deleted."
				# Translators: Asked before VisionClaw deletes several scratchpads. {count} is how many.
				mustAgree(_("Delete {count} scratchpads for good? They cannot be brought back.").format(count=len(chosen)))
				gone = sum(1 for pad in chosen if pads.delete(pad))
				return f"Deleted {gone} scratchpads."
			pad = chosenPad(kind)
			if pad is None or not pad.path or not os.path.isfile(pad.path):
				return "There is no such scratchpad, so nothing was deleted."
			name = {scratchpad.LEARNING: f"what was learned in {pad.title}",
				scratchpad.DESCRIBED: "the descriptions scratchpad"}.get(kind, f"the task scratchpad {pad.title}")
			# Translators: Asked before VisionClaw deletes one scratchpad. {name} is which.
			confirm(_("Delete {name} for good? It cannot be brought back.").format(name=name))
			return f"Deleted {name}." if pads.delete(pad) else f"{name[:1].upper()}{name[1:]} could not be deleted."
		pad = chosenPad(want.get("pad"))
		if pad is None:
			return "There is no task scratchpad yet. To start one, say start a scratchpad for, then the task."
		return scratchpad.padText(pad)

	add("scratchpad",
		"start a scratchpad for a task the user works on over several requests, write on it, add things to do, check them "
		"off, say what is next, read it, list, open, finish or delete scratchpads",
		scratchpadTool, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Working on the scratchpad", tell=VERBATIM)

	def scratchpadSearch(task, asked):
		want = scratchpad.wish(asked) or {"pad": scratchpad.TASK, "query": asked}
		query = want.get("query") or asked
		found = plugin.pads.search(query, where(), want.get("pad") or scratchpad.TASK)
		if not found:
			return f"{lookup.NOTHING} that on your scratchpads."
		return scratchpad.foundText(found)

	add("scratchpad_search",
		"answer a question from what is written on the scratchpads: the open task, what was learned in programs and "
		"websites, and the descriptions of pictures and of the screen",
		scratchpadSearch, {"asked": text("what the user asked, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking on the scratchpads", tell=SUMMARIZE)
