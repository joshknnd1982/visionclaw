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
# A complaint about what VisionClaw just did, with no error in the log (the owner, 2026-11-19: "visionclaw must be able to
# fix such focus and other bugs by itself using its AI models and skills, when I complain about a problem like this"):
# the request it is about is taken from what the orchestrator keeps in memory, or from the log; the functions that
# request's tools used are found in the running add-on without running anything, and ranked by the complaint's words;
# the model that writes code chooses one by its number and corrects it; the running NVDA is read, never changed, for what
# the names the function uses have (diagnose.namesFacts). The same checks, review and question follow. When VisionClaw
# cannot, it says so, names the function it would need, and writes a report for its developer. A correction is never
# said to work: the user is asked to try again, and to say undo that if it is worse.

import os
import sys
import time

import addonHandler

from .claw import debuglog, diagnose, policy, prompts
from .claw.catalog import CODER, VISION
from .claw.llm import LLM, LLMError, plainSpeech, uncut
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


def writeCorrection(plugin, task, place, source, facts, asked, complaint=False, function=None):
	"""The function as the model that writes code corrects it, passed by plain code's checks and read by the other model:
	(the function or None, the problems plain code found last, what the other model said, why no model could be asked or
	""). complaint: it corrects what the user said was wrong, not an error of the log. function: the running function,
	whose module tells which names exist (diagnose.unknownNames)."""
	llm = LLM(plugin.runtime, task)
	one = policy.isOneModel(plugin.runtime)
	coder, checker = policy.roleName(CODER, one), policy.roleName(VISION, one)
	system = diagnose.COMPLAINT_FIX_TASK if complaint else diagnose.FIX_TASK
	reviewSystem = diagnose.COMPLAINT_REVIEW_SYSTEM if complaint else diagnose.REVIEW_SYSTEM
	question = ("Does it do what the user expected and change nothing else?" if complaint
		else "Does it stop the error and change nothing else?")
	task.emit("talk", f"The {coder} is writing a correction of {place['qualname']}.")
	user = f"{facts}\nThe user asked: \"{asked}\"\nWrite the whole corrected function."
	newText, problems, review, reviewed = None, [], "", False
	for _attempt in range(diagnose.TRIES):
		task.check()
		asking = user + (f"\nThe correction you wrote before had problems: {' '.join(problems[:3])}" if problems else "")
		try:
			answer = llm.text(CODER, prompts.coding(system, asked), asking, maxTokens=1600,
				reasoning=_reasoning(task), temperature=0, code=True)
		except LLMError as e:
			return None, problems, review, f"The {coder} could not be asked: {e}"
		candidate = diagnose.bodyAligned(diagnose.tidy(diagnose.extractFunction(answer), place))
		problems = diagnose.checkFix(source, place, candidate, complaint) if candidate else [
			"Write the whole corrected function, its def line included."]
		# A name the running NVDA does not have is said to the model, which writes it again: plain code can tell it.
		if not problems and function is not None:
			problems = _safe(lambda: diagnose.unknownNames(candidate, function, sys.modules), []) or []
		if problems:
			task.emit("detail", f"Plain code found a problem in the correction: {problems[0]}")
			continue
		# The other model reads it; its doubt is told to the coder once, and then to the user.
		try:
			verdict = llm.json(VISION, reviewSystem,
				f"{facts}\nThe corrected function:\n```python\n{candidate}```\n{question}",
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
	return newText, problems, review, ""


def fixError(plugin, task, asked, error, mustAgree):
	"""An error of VisionClaw's log corrected in the function where it happened, after a question. The sentence for
	the user."""
	fixes = plugin.ownFixes
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
	one = policy.isOneModel(plugin.runtime)
	coder = policy.roleName(CODER, one)
	newText, problems, review, failure = writeCorrection(plugin, task, place, source, facts, asked)
	if failure:
		return f"{told} {failure} Nothing was changed."
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
	fix = diagnose.Fix(
		id=time.strftime("fix-%Y%m%d-%H%M%S") + f"-{place['name']}", file=relative, qualname=place["qualname"],
		version=fixes.version, oldDigest=diagnose.digest(place["text"]), old=place["text"], new=newText,
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


# --- A complaint about what VisionClaw just did ---

def recentRequests(plugin):
	"""What the last requests did, the newest first, each with its age in seconds: from what the orchestrator keeps in
	memory, else from VisionClaw's log. Reads only."""
	orchestrator = getattr(plugin, "orchestrator", None)
	kept = list(getattr(orchestrator, "recent", None) or [])
	found = []
	if kept:
		now = _safe(lambda: orchestrator.clock(), None)
		for item in reversed(kept):
			when = item.get("when")
			age = now - when if isinstance(now, (int, float)) and isinstance(when, (int, float)) else 0.0
			found.append(dict(item, age=max(0.0, age)))
		return found
	for item in reversed(diagnose.requests(diagnose.readLogs(logsFolder(plugin)))):
		try:
			age = time.time() - time.mktime(time.strptime(item["when"], "%Y-%m-%d %H:%M:%S"))
		except (ValueError, OverflowError, TypeError, KeyError):
			age = 0.0
		found.append(dict(item, age=max(0.0, age)))
	return found


def toolFunction(fn):
	"""A tool's own function, inside the wrappers nvdatools.build puts around every tool (guarded, notOwn), each made
	inside build and keeping the tool's function as fn. Read from the closures; nothing runs."""
	for _round in range(4):
		if not str(getattr(fn, "__qualname__", "")).startswith("build.<locals>."):
			break
		cells = dict(zip(getattr(getattr(fn, "__code__", None), "co_freevars", ()), getattr(fn, "__closure__", None) or ()))
		try:
			inner = cells["fn"].cell_contents
		except (KeyError, ValueError):
			break
		if not callable(inner):
			break
		fn = inner
	return fn


def findCode(plugin, item, check=None):
	"""The functions of VisionClaw's own code that the tools of a request used: (the tools, the functions, the tool's own
	first). Found in the running add-on without running anything."""
	registry = getattr(getattr(plugin, "orchestrator", None), "registry", None)
	tools = list(dict.fromkeys(step.get("tool") for step in item.get("steps") or () if step.get("tool")))
	found, seen = [], set()
	for name in tools:
		tool = registry.get(name) if registry is not None else None
		if tool is None:
			continue
		for entry in diagnose.usedFunctions(toolFunction(tool.fn), plugin.ownFixes.source, ROOT, sys.modules, check=check):
			key = (entry["file"], entry["qualname"])
			if key not in seen:
				seen.add(key)
				found.append(entry)
	return tools, found


def chooseFunction(plugin, task, complaint, done, offered):
	"""Which of the functions plain code offered the complaint is about: (its index or None, a sentence that says how it
	was chosen). Only a model that is not one of the very smallest may say none of them; for the very smallest, plain
	code decides whether anything fits, and where one fits it is taken."""
	one = policy.isOneModel(plugin.runtime)
	coder = policy.roleName(CODER, one)
	small = (_safe(lambda: plugin.runtime.entry(CODER), {}) or {}).get("suggest") is False
	if len(offered) == 1 and small:
		return 0, (f"Plain code found one function of VisionClaw's code that fits your words, {offered[0]['qualname']} in "
			f"{diagnose.fileWords(offered[0]['file'])}, which may be wrong.")
	none = not small
	task.emit("talk", f"The {coder} is choosing which of {len(offered)} functions of VisionClaw's code did it.")
	try:
		chosen = int(LLM(plugin.runtime, task).json(
			CODER, diagnose.CHOOSE_SYSTEM + (diagnose.CHOOSE_NONE if none else ""),
			diagnose.chooseQuestion(complaint, done, offered), diagnose.chooseSchema(len(offered), none), maxTokens=20).get("number"))
	except (LLMError, TypeError, ValueError, AttributeError) as e:
		debuglog.log("ownfix", f"The choice of a function could not be had: {e}")
		return None, f"The {coder} could not be asked which function did it"
	if chosen == 0:
		return None, f"The {coder} found that none of the {len(offered)} functions that fit your words best does it"
	if not 1 <= chosen <= len(offered):
		return None, f"The {coder} gave no function of the list"
	entry = offered[chosen - 1]
	return chosen - 1, (f"Plain code found {len(offered)} functions of VisionClaw's code that fit your words, and the {coder} "
		f"chose {entry['qualname']} in {diagnose.fileWords(entry['file'])} as the one that did it, which may be wrong.")


def cannot(plugin, told, complaint, done, offered, why, tools=(), need=None):
	"""What VisionClaw could not correct by itself: said in plain words, with the function it would need, and written as a
	report for its developer. Nothing is changed."""
	reason = why[:1].upper() + why[1:]
	report = diagnose.complaintReport(complaint, done, offered, reason + ".", plugin.ownFixes.version, tools)
	name = plugin.ownFixes.note(time.strftime("report-%Y%m%d-%H%M%S"), report)
	needed = (f" The function it would need to correct is {need['qualname']} in {diagnose.fileWords(need['file'])}."
		if need else "")
	where = (f" A report for VisionClaw's developer is in the folder ownfixes of VisionClaw's data, in the file {name}."
		if name else "")
	debuglog.log("ownfix", f"Not corrected: {reason}. Report: {name or 'not written'}.")
	return f"{told} VisionClaw could not correct this by itself: {why}.{needed}{where} Nothing was changed."


def fixComplaint(plugin, task, asked, complaint, target, mustAgree):
	"""What the user said VisionClaw did wrong, corrected in the function of its own code that did it, after a question;
	or said why not, with a report. The sentence for the user."""
	if target is None:
		return ("VisionClaw found no request of yours before this one that it could look at, so it cannot tell what went "
			"wrong. Ask for the same thing again, then say what went wrong. Nothing was changed.")
	said = uncut(target.get("said") or target.get("request"))
	if target.get("age", 0) > diagnose.COMPLAINT_SECONDS:
		return (f"Your last request, \"{said}\", was more than {diagnose.COMPLAINT_SECONDS // 60} minutes ago, so VisionClaw "
			"cannot be sure that is what you mean. Ask for it again, then say what went wrong. Nothing was changed.")
	told = diagnose.aboutText(complaint, target)
	# An error from that request in VisionClaw's log says where it went wrong more surely than words do.
	ofIt = [error for error in diagnose.errors(diagnose.readLogs(logsFolder(plugin)))
		if error.request and error.request in (target.get("said"), target.get("request")) and diagnose.ownFrame(error, ROOT)]
	if ofIt:
		task.emit("talk", "VisionClaw's log has an error from that request, so the function where it happened is corrected.")
		return fixError(plugin, task, asked, ofIt[0], mustAgree)
	task.emit("talk", f"{told} VisionClaw is looking for the part of its own code that did it.")
	tools, found = findCode(plugin, target, task.check)
	done = diagnose.doneText(target)
	offered = diagnose.fitting(found, complaint, target.get("answer", ""))
	debuglog.log("ownfix", f"A complaint about {target.get('request')!r}: the tools {tools}, {len(found)} functions found, "
		f"offered {[entry['qualname'] for entry in offered]}.")
	if not offered:
		usable = [entry for entry in found if not entry["refusal"]]
		if usable:
			why = f"plain code found no function of VisionClaw's code that fits your words among the {len(usable)} that request used"
		elif found:
			why = "the code that request used is made inside other functions, which VisionClaw cannot correct while it runs"
		elif tools:
			why = f"the code of the tools that request used, {', '.join(tools)}, could not be found"
		else:
			why = "that request used none of VisionClaw's tools, so there is no code of it to look at"
		return cannot(plugin, told, complaint, done, [], why, tools, found[0] if found else None)
	index, how = chooseFunction(plugin, task, complaint, done, offered)
	if index is None:
		return cannot(plugin, told, complaint, done, offered, how, tools, offered[0])
	entry = offered[index]
	place, source = entry["place"], entry["source"]
	task.emit("talk", how)
	nvda = _safe(lambda: diagnose.namesFacts(entry["function"], place, sys.modules, complaint), []) or []
	facts = diagnose.complaintFacts(complaint, done, entry, nvda)
	one = policy.isOneModel(plugin.runtime)
	coder = policy.roleName(CODER, one)
	newText, problems, review, failure = writeCorrection(plugin, task, place, source, facts, asked, complaint=True,
		function=entry["function"])
	if failure:
		return f"{told} {failure} Nothing was changed."
	if newText is None:
		return cannot(plugin, told, complaint, done, offered,
			f"the {coder} could not write a correction of {entry['qualname']} that passes VisionClaw's checks: "
			f"{(problems[0] if problems else 'it wrote none').rstrip('.')}", tools, entry)
	change = diagnose.changeText(place["text"], newText)
	# Translators: Asked before VisionClaw uses a correction of its own code that it wrote because the user said what it
	# did was wrong. {told} is what the user said and the request it is about, {how} how the function was chosen, {coder}
	# the model that wrote it, {change} what the correction changes, {review} what the other model said.
	mustAgree(_(
		"{told} {how} The {coder} wrote a correction of it. {change} {review} Plain code checked that it is written "
		"correctly, changes only that function, and adds nothing that reaches the internet, starts programs or deletes "
		"files. That is a check, not a guarantee: nobody knows yet whether it does what you wanted. If you say yes, the "
		"correction is used at once and whenever VisionClaw starts; VisionClaw's own files stay as they are, and if the "
		"correction itself fails, it turns itself off. You can undo it by saying undo that. Use the correction?").format(
			told=told, how=how, coder=coder, change=change, review=review))
	fixes = plugin.ownFixes
	fix = diagnose.Fix(
		id=time.strftime("fix-%Y%m%d-%H%M%S") + f"-{place['name']}", file=entry["file"], qualname=entry["qualname"],
		version=fixes.version, oldDigest=diagnose.digest(place["text"]), old=place["text"], new=newText,
		error=f"What you said was wrong: {complaint}", made=time.strftime("%Y-%m-%d %H:%M:%S"), complaint=complaint)
	worked, why = fixes.add(fix, diagnose.report(fix, facts, how, change, review))
	if not worked:
		fixes.remove(fix.id)
		return f"The correction was written, but it could not be put in place: {why} Nothing was changed."
	plugin.changes.add(f"{CHANGE}{fix.id}", f"VisionClaw's correction of its function {entry['qualname']}", "", fix.id,
		"as it was written", "corrected", asked)
	return (f"VisionClaw put a correction of its function {entry['qualname']} in place. {change} Nobody knows yet whether "
		f"it does what you wanted: ask for the same thing again, \"{said}\", and listen to what happens. If it is worse, or "
		"no better, say undo that. A report of it is in the folder ownfixes of VisionClaw's data.")


def whyComplaint(plugin, task, complaint, asked, lead=""):
	"""Why VisionClaw did what the user says was wrong, as far as plain code can tell: the request it is about, an error
	of the log from it with what the model that writes code says of it, or else the functions that fit the words, and
	how to have it corrected. No correction is made."""
	complaint, target = diagnose.complaintTarget(recentRequests(plugin), complaint)
	if target is None:
		return lead + "VisionClaw found no request of yours before this one that it could look at, so it cannot tell why."
	said = [lead + diagnose.aboutText(complaint, target)]
	steps = [f"{step.get('title') or step.get('tool')}, {step.get('status') or 'unknown'}" for step in target.get("steps") or ()]
	if steps:
		said.append("What VisionClaw did for it: " + "; ".join(steps) + ".")
	ofIt = [error for error in diagnose.errors(diagnose.readLogs(logsFolder(plugin)))
		if error.request and error.request in (target.get("said"), target.get("request"))]
	if ofIt:
		said.append(diagnose.errorText(ofIt[0], ROOT))
		said.append(diagnosis(plugin, task, ofIt[0], asked))
	else:
		said.append("VisionClaw's log has no error from that request, so plain code cannot tell for certain why it happened.")
		_tools, found = findCode(plugin, target, task.check)
		offered = diagnose.fitting(found, complaint, target.get("answer", ""))
		if offered:
			said.append("The parts of VisionClaw's code that fit your words best: " + "; ".join(
				f"{entry['qualname']} in {diagnose.fileWords(entry['file'])}" for entry in offered) + ".")
	said.append("To have VisionClaw try to correct it, say: fix that bug.")
	return " ".join(part for part in said if part)


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
		# Why VisionClaw did what the user says was wrong: about the request it did it in.
		if want.get("complaint"):
			return whyComplaint(plugin, task, want["complaint"], asked, lead)
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
		# A complaint about what VisionClaw just did, in these words or in the request just before ("fix that bug" after "why
		# did the focus go to the wrong control"): the code that request used is corrected.
		complaint, target = diagnose.complaintTarget(recentRequests(plugin), want.get("complaint", ""))
		if complaint:
			return fixComplaint(plugin, task, asked, complaint, target, mustAgree)
		found = diagnose.errors(diagnose.readLogs(logsFolder(plugin)))
		error = diagnose.chosen(found, want, ROOT)
		if error is None:
			return "VisionClaw's log has no error to correct, so nothing was changed."
		return fixError(plugin, task, asked, error, mustAgree)

	add("fix_self",
		"correct a bug in VisionClaw's own code, only when the user asks for exactly that or says that what VisionClaw just "
		"did was wrong: the model that writes code corrects the function where an error from VisionClaw's log happened, or "
		"the one that did what the user says was wrong, and the user is asked before it is used",
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
