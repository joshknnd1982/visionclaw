# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - VisionClaw's own logs read, what went wrong said, and its own code corrected, as tools, only when the
# user asks for exactly that (claw/diagnose.py). The owner said on 2026-11-19: "give visionclaw access to its own logs,
# so through the coding and vision model, a user can have visionclaw diagnose and fix its own bugs" and "visionclaw must
# only read its own logs and fix its own bugs upon user request". So every tool here reads what the user asked from the
# user's own words (diagnose.wish) and does nothing without them; the model that writes code says what went wrong and
# writes the correction, the model that sees reads the correction, plain code checks it, and the user is always asked
# before it is used (mustAgree). VisionClaw's own files are never changed: a correction is data, put in place while
# NVDA runs, kept with its report in the folder "ownfixes" of VisionClaw's data, and undone with "undo that". Nothing
# here goes online.

import os
import time

import addonHandler

from .claw import debuglog, diagnose, policy, prompts
from .claw.catalog import CODER, VISION
from .claw.llm import LLM, LLMError, plainSpeech
from .claw.tools import VERBATIM
from .nvdatools import _safe

addonHandler.initTranslation()

# The folder of VisionClaw's own code in the running add-on.
ROOT = os.path.dirname(os.path.abspath(__file__))
# Where a correction comes from in the list of changes (claw/changes.py), for undo_change.
CHANGE = "ownfix:"


def logsFolder(plugin):
	return os.path.join(plugin.dataDir, "logs")


def startUp(plugin):
	"""The corrections the user said yes to, put in place again when VisionClaw starts. Never a fault."""
	from . import versiontools
	plugin.ownFixes = diagnose.Fixes(
		os.path.join(plugin.dataDir, diagnose.FOLDER), ROOT, _safe(versiontools.ownVersion, "") or "")
	try:
		placed, aside = plugin.ownFixes.startUp()
		if placed or aside:
			debuglog.log("ownfix", f"Corrections of VisionClaw's own code: {placed} in place, {aside} put aside.")
	except Exception as e:
		debuglog.error("ownfix", "The corrections of VisionClaw's own code could not be put in place", e)


def _reasoning(task):
	return getattr(getattr(task, "params", None), "reasoning", "off") or "off"


def diagnosis(plugin, task, error, asked):
	"""What the model that writes code says went wrong, in plain words, said to be its own and possibly wrong; "" where
	the error has no place in VisionClaw's code or the model cannot answer."""
	frame = diagnose.ownFrame(error, ROOT)
	if frame is None:
		return ""
	fixes = plugin.ownFixes
	source = fixes.source(frame[0])
	place = diagnose.functionAt(source, frame[1]) if source else None
	if place is None:
		return ""
	one = policy.isOneModel(plugin.runtime)
	coder = policy.roleName(CODER, one)
	task.emit("talk", f"The {coder} is reading the error and the code where it happened.")
	try:
		said = LLM(plugin.runtime, task).text(
			CODER, prompts.speaking(diagnose.DIAGNOSE_TASK),
			diagnose.facts(error, ROOT, source, place) + f"\nThe user asked: \"{asked}\"\nWhat went wrong?",
			maxTokens=320, reasoning=_reasoning(task), temperature=0.2)
	except LLMError:
		return ""
	said = plainSpeech(" ".join(str(said or "").split()))
	return f"What the {coder} says went wrong, which may be wrong: {said}" if said else ""


def register(add, plugin, text, onMain, confirm, mustAgree):
	"""The tools for VisionClaw's own logs and code. The first three are the helpers of nvdatools.build."""

	def ownErrors(task, asked):
		# The part's own words decide, never the rest of the request: only what the user asked for is done.
		want = diagnose.wish(asked)
		if want is None or want["do"] not in (diagnose.ERRORS, diagnose.WHY):
			return "VisionClaw reads its own log only when you ask for exactly that, so nothing was read."
		folder = logsFolder(plugin)
		if not debuglog.on():
			lead = ("VisionClaw's log is switched off in its settings, under VisionClaw's log, so what happened since then "
				"was not written down. ")
		else:
			lead = ""
		logged = diagnose.readLogs(folder)
		found = diagnose.errors(logged)
		if want["do"] == diagnose.ERRORS:
			return lead + diagnose.listText(found, ROOT, diagnose.engineTrouble(folder))
		story = diagnose.lastRequest(logged) if want.get("request") and not want.get("which") else None
		if story is not None:
			said = [lead + diagnose.storyText(story)]
			ofIt = [error for error in found if error.request == story["request"]]
			if ofIt:
				said.append(diagnose.errorText(ofIt[0], ROOT))
				said.append(diagnosis(plugin, task, ofIt[0], asked))
			return " ".join(part for part in said if part)
		error = diagnose.chosen(found, want, ROOT)
		if error is None:
			return lead + "VisionClaw's log has no errors, so there is nothing to find out."
		return " ".join(part for part in (lead + diagnose.errorText(error, ROOT), diagnosis(plugin, task, error, asked)) if part)

	add("own_errors",
		"read VisionClaw's own log, only when the user asks: say which errors it has, or find out why VisionClaw or the "
		"user's last request went wrong",
		ownErrors, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Reading VisionClaw's own log", tell=VERBATIM)

	def fixSelf(task, asked):
		want = diagnose.wish(asked)
		if want is None or want["do"] != diagnose.FIX:
			return "VisionClaw corrects its own code only when you ask for exactly that, so nothing was changed."
		fixes = plugin.ownFixes
		found = diagnose.errors(diagnose.readLogs(logsFolder(plugin)))
		error = diagnose.chosen(found, want, ROOT)
		if error is None:
			return "VisionClaw's log has no error to correct, so nothing was changed."
		told = diagnose.errorText(error, ROOT)
		frame = diagnose.ownFrame(error, ROOT)
		if frame is None:
			return f"{told} It did not happen in VisionClaw's own code, so VisionClaw cannot correct it. Nothing was changed."
		relative, line, function = frame
		source = fixes.source(relative)
		place = diagnose.functionAt(source, line) if source else None
		if place is not None and place["name"] != function:
			return (f"{told} VisionClaw's code has changed since this error happened, so the line no longer fits it. "
				"Nothing was changed.")
		why = diagnose.refusal(relative, place)
		if why:
			return f"{told} {why} Nothing was changed."
		facts = diagnose.facts(error, ROOT, source, place)
		llm = LLM(plugin.runtime, task)
		one = policy.isOneModel(plugin.runtime)
		coder, checker = policy.roleName(CODER, one), policy.roleName(VISION, one)
		task.emit("talk", f"The {coder} is writing a correction of {place['qualname']}.")
		user = f"{facts}\nThe user asked: \"{asked}\"\nWrite the whole corrected function."
		newText, problems, review, reviewed = None, [], "", False
		for _attempt in range(diagnose.TRIES):
			task.check()
			asking = user + (f"\nThe correction you wrote before had problems: {' '.join(problems[:3])}" if problems else "")
			try:
				answer = llm.text(CODER, prompts.coding(diagnose.FIX_TASK, asked), asking, maxTokens=1600,
					reasoning=_reasoning(task), temperature=0, code=True)
			except LLMError as e:
				return f"{told} The {coder} could not be asked: {e} Nothing was changed."
			candidate = diagnose.bodyAligned(diagnose.tidy(diagnose.extractFunction(answer), place))
			problems = diagnose.checkFix(source, place, candidate) if candidate else [
				"Write the whole corrected function, its def line included."]
			if problems:
				task.emit("detail", f"Plain code found a problem in the correction: {problems[0]}")
				continue
			# The other model reads it; its doubt is told to the coder once, and then to the user.
			try:
				verdict = llm.json(VISION, diagnose.REVIEW_SYSTEM,
					f"{facts}\nThe corrected function:\n```python\n{candidate}```\nDoes it stop the error and change nothing else?",
					diagnose.REVIEW_SCHEMA, maxTokens=160)
			except LLMError:
				verdict = {}
			problem = " ".join(str(verdict.get("problem") or "").split())
			newText = candidate
			if verdict.get("fixes") is False and problem:
				review = f"The {checker} found a problem: {problem}"
				if not reviewed:
					reviewed = True
					task.emit("talk", review)
					problems = [problem]
					continue
			else:
				review = f"The {checker} read it and found no problem." if verdict.get("fixes") else f"The {checker} could not say."
			break
		if newText is None:
			return (f"{told} The {coder} could not write a correction that passes VisionClaw's checks: "
				f"{problems[0] if problems else 'it wrote none'} Nothing was changed.")
		change = diagnose.changeText(place["text"], newText)
		# Translators: Asked before VisionClaw uses a correction of its own code. {error} is the error, {where} the function,
		# {change} what the correction changes, {coder} and {review} which model wrote it and what the other said.
		mustAgree(_(
			"VisionClaw found this error: {error} The {coder} wrote a correction of {where}. {change} {review} Plain code "
			"checked that it is written correctly, changes only that function, and adds nothing that reaches the internet, "
			"starts programs or deletes files. That is a check, not a guarantee. If you say yes, the correction is used at "
			"once and whenever VisionClaw starts; VisionClaw's own files stay as they are, and if the correction itself "
			"fails, it turns itself off. You can undo it by saying undo that. Use the correction?").format(
				error=told, coder=coder, where=place["qualname"], change=change, review=review))
		version = fixes.version
		fix = diagnose.Fix(
			id=time.strftime("fix-%Y%m%d-%H%M%S") + f"-{place['name']}", file=relative, qualname=place["qualname"],
			version=version, oldDigest=diagnose.digest(place["text"]), old=place["text"], new=newText,
			error=f"{error.message} ({error.exception})" if error.exception else error.message,
			made=time.strftime("%Y-%m-%d %H:%M:%S"))
		worked, why = fixes.add(fix, diagnose.report(fix, facts, "", change, review))
		if not worked:
			fixes.remove(fix.id)
			return f"The correction was written, but it could not be put in place: {why} Nothing was changed."
		plugin.changes.add(f"{CHANGE}{fix.id}", f"VisionClaw's correction of its function {place['qualname']}", "", fix.id,
			"as it was written", "corrected", asked)
		return (f"VisionClaw's function {place['qualname']} is corrected, and the correction is used from now on, also when "
			f"VisionClaw starts again. {change} A report of it is in the folder ownfixes of VisionClaw's data. If the "
			"correction itself fails, it turns itself off and the function works as before. To undo it, say undo that.")

	add("fix_self",
		"correct a bug in VisionClaw's own code, only when the user asks for exactly that: the model that writes code "
		"corrects the function where an error from VisionClaw's log happened, and the user is asked before it is used",
		fixSelf, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Correcting VisionClaw's own code", tell=VERBATIM)

	def ownFixes(task, asked):
		want = diagnose.wish(asked)
		fixes = plugin.ownFixes
		if want is None or want["do"] != diagnose.REMOVE:
			return fixes.text()
		standing = [fix for fix in fixes.all() if fix.state == "on"]
		if not standing:
			return "No correction of VisionClaw's own code is in use, so there is nothing to undo."
		which = want.get("which")
		fix = standing[-which] if which and 0 < which <= len(standing) else standing[-1]
		return undoOne(plugin, fix.id, confirm, asked)

	add("own_fixes",
		"say which corrections VisionClaw made of its own code, or undo one, only when the user asks",
		ownFixes, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="VisionClaw's corrections of its own code", tell=VERBATIM)


def undoOne(plugin, ident, confirm, asked=""):
	"""A correction undone after a question: the function as it was is used again. The sentence for the user."""
	fix = next((found for found in plugin.ownFixes.all() if found.id == ident), None)
	if fix is None or fix.state == "undone":
		return "That correction is undone already."
	# Translators: Asked before VisionClaw undoes a correction of its own code. {where} is the function.
	confirm(_("Undo VisionClaw's correction of its function {where}, so that it works as it was written again?").format(
		where=fix.qualname))
	plugin.ownFixes.remove(ident)
	for change in plugin.changes.pending():
		if change.get("setting") == f"{CHANGE}{ident}":
			plugin.changes.markUndone(change)
	return f"VisionClaw's correction of {fix.qualname} is undone; the function works as it was written again."


def undoFix(plugin, change, confirm):
	"""undo_change for a correction of VisionClaw's own code."""
	return undoOne(plugin, change["new"], confirm)
