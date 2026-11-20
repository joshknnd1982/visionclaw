# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the work sheet of one request: a temporary Markdown file that holds the plan, and from which every
# small model is fed its own small piece of the work, deleted when the request is done.
# The owner said on 2026-11-19: "no matter what model the user chooses, visionclaw must force these small models
# to be as accurate as possible, this means using temporary markdown files to plan and feed small bite-size pieces
# into tiny models, which get deleted when a job is done."
# A file does not make a model more exact by itself; what it is fed does. So the sheet is the one place a step's
# question is made from: a step is given what the steps of its own part found, not everything found so far, and
# a piece of an add-on is given its own section and nothing else (claw/codeplan.py). The file shows the user, or
# anyone reading VisionClaw's data folder, the plan and what each step was given and found, while the request runs.
# It is written to the folder work of VisionClaw's data, one file for each request, and deleted when the request
# ends, whether it was done, failed or stopped; what is left there after NVDA closed in the middle of a request is
# deleted when VisionClaw starts. Without a folder the sheet is kept in memory only. Writing it never ends a
# request.
# The sheet is also the request's scratchpad (claw/scratchpad.py): a long result is given to a step by its parts that
# are about the step, not cut off after its beginning; a line a model wrote down from what a step found, checked by
# plain code, is given to the steps after it; and so are the lines of the lasting scratchpads (the open task, what was
# learned in this program) that are about the step. No NVDA dependencies.

import os
import re
import time

from . import debuglog, scratchpad
from . import task as taskModule
from .llm import clip, uncut

FOLDER = "work"
PREFIX = "request-"
# How much of a step's result is given to the step after it, as before (agent.RESULT_CHARS).
RESULT_CHARS = 500
# A part that speaks of "it" or "there" leans on what came before: it is given everything found so far.
_LEANS = re.compile(r"\b(it|its|they|them|their|that one|this one|there|those|these)\b|\(this follows:", re.IGNORECASE)
_MARK = {
	taskModule.STEP_DONE: "x", taskModule.STEP_FAILED: "!", taskModule.SKIPPED: "-", taskModule.NOT_NEEDED: "-",
	taskModule.RUNNING: ">",
}
_SAID = {
	taskModule.STEP_DONE: "done", taskModule.STEP_FAILED: "did not work", taskModule.SKIPPED: "left out",
	taskModule.NOT_NEEDED: "not needed", taskModule.RUNNING: "running now", taskModule.PENDING: "to do",
}


def clean(folder):
	"""Delete the work sheets left over from a request that NVDA closed in the middle of. Returns how many."""
	gone = 0
	try:
		names = os.listdir(folder)
	except OSError:
		return 0
	for name in names:
		if name.startswith(PREFIX) and name.endswith(".md"):
			try:
				os.remove(os.path.join(folder, name))
				gone += 1
			except OSError as e:
				debuglog.error("worksheet", f"A work sheet left over could not be deleted: {name}", e)
	return gone


def relevant(steps, index):
	"""The earlier steps whose results step index is given: those of its own part, and the check it depends on.
	A step a model planned itself, one that leans on what came before ("it", "there"), and one added to finish what
	was missing are given every earlier step, as before."""
	step = steps[index]
	wide = step.recipe is None or getattr(step, "wide", False) or bool(_LEANS.search(step.part or ""))
	chosen = []
	for i, earlier in enumerate(steps[:index]):
		if wide or earlier.part == step.part or earlier is step.onlyIf:
			chosen.append(i)
	return chosen


def stepQuery(step):
	"""What a step is about, for finding the parts of a result and the lines of a scratchpad that fit it."""
	return f"{step.part or ''} {step.title or ''} {step.detail or ''}".strip()


def feed(steps, index, notes=()):
	"""What step index is given of what was found so far, in the form the models know. A result longer than
	RESULT_CHARS is given by its parts about this step (scratchpad.relevantText). notes: lines written on a scratchpad
	that are about this step, given after the results; nothing is added when there are none."""
	lines = []
	query = stepQuery(steps[index])
	for i in relevant(steps, index):
		step = steps[i]
		if step.status == taskModule.STEP_DONE:
			lines.append(f"{i + 1}. {step.title}: {scratchpad.relevantText(step.result, query, RESULT_CHARS)}")
		elif step.status in (taskModule.STEP_FAILED, taskModule.SKIPPED):
			lines.append(f"{i + 1}. {step.title}: was not done.")
	given = "\n".join(lines) or "Nothing yet."
	written = [note for note in notes if note]
	if written:
		given += "\nWritten on the scratchpad:\n" + "\n".join(f"- {text}" for text in written)
	return given


class Sheet:
	"""The work sheet of one request. folder: where it is written, or None to keep it in memory only."""

	_count = 0

	def __init__(self, folder, request, clock=time.time):
		self.folder = folder
		self.request = request
		self.understood = ""
		self.started = clock()
		self.recipes = []
		self.steps = []
		# Sections added by the work itself, as an add-on written piece by piece: {heading: text}, in order.
		self.sections = {}
		# The request's own scratchpad: what the models wrote down while they worked (claw/scratchpad.py), and which
		# step each line came from. lasting(query) gives the lines of the lasting scratchpads about a step, or None.
		self.pad = scratchpad.Pad(scratchpad.REQUEST, clock=clock)
		self.noteFrom = {}
		self.lasting = None
		self.given = []
		self.closed = False
		self.path = None
		if folder:
			Sheet._count += 1
			stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(self.started))
			self.path = os.path.join(folder, f"{PREFIX}{stamp}-{os.getpid()}-{Sheet._count}.md")
		self.write()

	def plan(self, steps, recipes=(), understood=""):
		"""The plan, once it is known."""
		self.steps = steps
		self.recipes = list(recipes or ())
		if understood:
			self.understood = understood
		self.write()

	def section(self, heading, text):
		"""A section of the work's own, written at once. The same heading replaces what was there."""
		self.sections[heading] = text
		self.write()

	def note(self, index, note):
		"""A line written down from what step index found (scratchpad.Note), for the steps that are given that step."""
		self.pad.add(note)
		self.noteFrom[note.text] = index
		self.write()

	def notesFor(self, steps, index):
		"""The lines of the scratchpads given to step index: those written from the steps it is given, then those of the
		lasting scratchpads that are about it, at most scratchpad.FED_NOTES. A fault in the lasting ones is no fault."""
		chosen = set(relevant(steps, index))
		found = [note.text for note in self.pad.notes if self.noteFrom.get(note.text) in chosen]
		lasting = []
		if self.lasting is not None and len(found) < scratchpad.FED_NOTES:
			try:
				for note in self.lasting(stepQuery(steps[index])) or ():
					if note.text not in found and len(found) < scratchpad.FED_NOTES:
						found.append(note.text)
						lasting.append(note)
			except Exception as e:
				debuglog.error("scratchpad", "The scratchpads could not be read for a step", e)
		# The lasting lines a step was given: how the request went is counted on them (scratchpad.Pads.judge).
		self.given += [note for note in lasting if note not in self.given]
		return found[:scratchpad.FED_NOTES]

	def feed(self, steps, index):
		"""What step index is given of what was found so far; written into the sheet with the step."""
		self.steps = steps
		notes = self.notesFor(steps, index)
		given = feed(steps, index, notes)
		chosen = relevant(steps, index)
		steps[index].given = chosen
		steps[index].notes = notes
		self.write()
		return given

	def text(self):
		"""The sheet as Markdown."""
		lines = [
			"# VisionClaw work sheet", "",
			"This is VisionClaw's plan for one request, and what each small step is given and finds. It is deleted",
			"when the request is done.", "",
			f"Request: \"{self.request}\"",
		]
		if self.understood and self.understood != self.request:
			lines.append(f"Understood as: \"{self.understood}\"")
		lines.append(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.started))}")
		if self.recipes:
			lines += ["", "Parts: " + "; ".join(self.recipes) + "."]
		if self.steps:
			lines += ["", "## Plan", ""]
			for number, step in enumerate(self.steps, 1):
				mark = _MARK.get(step.status, " ")
				part = f" For: \"{uncut(step.part)}\"." if step.part and step.tool != "answer" else ""
				lines.append(f"{number}. [{mark}] {step.title} ({step.tool}): {_SAID.get(step.status, step.status)}.{part}")
			found = [(number, step) for number, step in enumerate(self.steps, 1)
				if step.status in (taskModule.STEP_DONE, taskModule.STEP_FAILED) and step.tool != "answer"]
			if found:
				lines += ["", "## Found so far", ""]
				for number, step in found:
					given = getattr(step, "given", None)
					if given is not None:
						lines.append(f"Step {number} was given: " + (
							", ".join(f"step {i + 1}" for i in given) if given else "nothing found before it") + ".")
					lines.append(f"Step {number} found: {clip(step.result, RESULT_CHARS)}")
					lines.append("")
		if self.pad.notes:
			lines += ["", "## Scratchpad", ""] + [note.line() for note in self.pad.notes]
		for heading, text in self.sections.items():
			lines += ["", f"## {heading}", "", text.rstrip()]
		return "\n".join(lines).rstrip() + "\n"

	def write(self):
		"""Write the sheet to its file. A fault is written to the log and never ends the request."""
		if not self.path or self.closed:
			return
		try:
			os.makedirs(self.folder, exist_ok=True)
			temporary = self.path + ".new"
			with open(temporary, "w", encoding="utf-8") as f:
				f.write(self.text())
			os.replace(temporary, self.path)
		except Exception as e:
			debuglog.error("worksheet", "The work sheet could not be written", e)

	def close(self):
		"""The request is done: the sheet is deleted. What it held is in VisionClaw's log when the log is on."""
		if self.closed:
			return
		self.closed = True
		if not self.path:
			return
		for path in (self.path, self.path + ".new"):
			try:
				if os.path.exists(path):
					os.remove(path)
			except OSError as e:
				debuglog.error("worksheet", "The work sheet could not be deleted", e)
