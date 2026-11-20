# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - NVDA's own log, read for the user only when the user asks for exactly that (claw/nvdalog.py holds the plain
# logic and the rules). The owner said on 2026-11-19: "I also want visionclaw to have access to the various logs of nvda
# itself, info, debug, etcetera", "if nvda logging is disabled, then such skills can't be used until user turns on some
# sort of nvda logging in nvda settings currently under privacy", and "visionclaw can query the various nvda logs to get all
# kinds of realtime info". What this file does on NVDA's side:
#   - reads NVDA's logging level and whether it is forced (logHandler.log.getEffectiveLevel, logHandler.isLogLevelForced,
#     globalVars.appArgs.secure and logFileName, config.conf["general"]["loggingLevel"]), read from NVDA's logHandler.py;
#   - reads nvda.log of this run and nvda-old.log of the run before, from the folder NVDA writes to, only the end of a very
#     large file, and only what is new since VisionClaw last read it when that is asked. Entries of the levels IO, DEBUG and
#     DEBUG_UNREDACTED are dropped while the lines are parsed (nvdalog.parse): never read out, never given to a model,
#     never written to VisionClaw's own log, which gets counts only;
#   - names the add-ons from the running NVDA (addonHandler.getAvailableAddons) and the modules in their folders, so that
#     an error is told by the add-on it comes from;
#   - opens NVDA's settings at the category Privacy and Security, as NVDA's own menu does (gui/__init__.py,
#     MainFrame.onPrivacyAndSecuritySettingsCommand), on NVDA's main thread, after the user said yes to the offer. That
#     changes nothing. VisionClaw never changes NVDA's logging level (nvdatools._SKIP_KEYS has "loggingLevel").
#   - says a key tried in input help by what its command does, from NVDA's own list of commands (scriptWords).
# Nothing here goes online, and nothing runs by itself: not at start-up, not after an error. For other parts of VisionClaw:
#   mark()                 a position at the end of this run's log, or None; reads no line
#   since(position)        the readable entries written after it, each with its time; never raises, any thread
#   readCurrent(check)     this run's entries, with their times
#   factsSince(since, until)   what NVDA reported in a stretch of time, one plain dict each (nvdalog.factOf)
# They are likewise used only for a request of the user.

import os
import tempfile
import time

import addonHandler

from .claw import debuglog, nvdalog, policy, prompts
from .claw.catalog import CODER
from .claw.llm import LLM, LLMError, clip, plainSpeech
from .claw.tools import VERBATIM
from .nvdatools import _safe

addonHandler.initTranslation()

# Where VisionClaw last stopped reading NVDA's log in this run of NVDA, so that "anything new in NVDA's log" reads only what
# is new: {"path", "offset", "when"}. Kept only while NVDA runs, never written to the disk.
_lastRead = {}
# The folders of an add-on whose modules NVDA names in a codepath of code outside itself ("external:globalPlugins.clock...").
_KINDS = ("globalPlugins", "appModules", "synthDrivers", "brailleDisplayDrivers", "visionEnhancementProviders")


def logState():
	"""NVDA's logging now, read from the running NVDA: {configured, effective, forced, secure, file, writing}. Never a fault:
	what cannot be read is left unknown."""
	import config
	import globalVars
	import logHandler
	args = getattr(globalVars, "appArgs", None)
	effective = _safe(lambda: logHandler.log.getEffectiveLevel())
	handler = getattr(logHandler, "logHandler", None)
	fileHandler = getattr(logHandler, "FileHandler", None)
	writing = None
	if isinstance(fileHandler, type) and handler is not None:
		writing = isinstance(handler, fileHandler)
	forced = _safe(logHandler.isLogLevelForced, False) if callable(getattr(logHandler, "isLogLevelForced", None)) else False
	return {
		"configured": str(_safe(lambda: config.conf["general"]["loggingLevel"], "") or ""),
		"effective": effective if isinstance(effective, int) and not isinstance(effective, bool) else None,
		"forced": forced is True,
		"secure": getattr(args, "secure", False) is True,
		"file": str(getattr(args, "logFileName", "") or ""),
		"writing": writing,
	}


def _defaultFolder():
	"""Where NVDA keeps its log when the running NVDA names no file: the folder for temporary files, as logHandler's
	_getDefaultLogFilePath does for an installed or portable NVDA."""
	import logHandler
	found = _safe(lambda: logHandler._getDefaultLogFilePath(), "")
	return os.path.dirname(found) if isinstance(found, str) and found else tempfile.gettempdir()


def addonsKnown():
	"""({add-on id: its name}, {"globalPlugins.clock": add-on id, ...}) of every add-on installed in the running NVDA.
	Main thread. Never a fault."""
	names, modules = {}, {}
	for addon in list(_safe(lambda: list(addonHandler.getAvailableAddons()), []) or []):
		ident = str(getattr(addon, "name", "") or "")
		if not ident:
			continue
		names[ident] = str(_safe(lambda a=addon: a.manifest["summary"], "") or ident)
		path = str(getattr(addon, "path", "") or "")
		for kind in _KINDS:
			for entry in _safe(lambda folder=os.path.join(path, kind): os.listdir(folder), []) or []:
				module = entry[:-3] if entry.endswith(".py") else entry
				if module and not module.startswith(("_", ".")) and "." not in module:
					modules[f"{kind}.{module}"] = ident
	return names, modules


def readFile(path, start=None, limit=nvdalog.MAX_READ):
	"""The lines of a log file: (lines, cut, size). start: a byte offset to read from, for what is new since then; else the
	end of the file, at most limit bytes of it (cut says that the beginning was left out). An entry cut in two at the start
	is left out by nvdalog.parse. Nothing is kept: the lines are parsed at once, and private entries keep nothing."""
	size = os.path.getsize(path)
	begin = max(0, size - limit)
	if start is not None and 0 <= start <= size:
		begin = max(start, begin)
	with open(path, "rb") as f:
		f.seek(begin)
		data = f.read(size - begin)
	cut = begin > 0 and (start is None or begin > start)
	return data.decode("utf-8", errors="replace").splitlines(), cut, size


def readCurrent(check=None, start=None):
	"""The entries of this run's log, each with its time worked out: (entries, cut, size, path), or None where NVDA keeps no
	log file. For a request of the user only."""
	state = logState()
	path = state.get("file") or ""
	if not path or not os.path.isfile(path):
		return None
	lines, cut, size = readFile(path, start)
	entries = nvdalog.parse(lines, check)
	# This run's log is being written now: its last entry is not later than now.
	nvdalog.stamp(entries, time.time())
	return entries, cut, size, path


def factsSince(since=None, until=None, check=None):
	"""What NVDA reported in this run's log from since to until (seconds since the epoch), one plain dict each
	(nvdalog.factOf). Private entries are never in it. For later features and skills, for a request of the user only."""
	read = readCurrent(check)
	if read is None:
		return []
	_names, modules = addonsKnown()
	return nvdalog.facts(nvdalog.entriesSince(read[0], since, until), modules)


def mark():
	"""A position at the end of this run's log, to read later what NVDA wrote after it (since): {"path", "offset", "when"},
	or None where NVDA keeps no log file. Reads no line of the log. Works from any thread; never raises."""
	try:
		import globalVars
		path = str(getattr(getattr(globalVars, "appArgs", None), "logFileName", "") or "")
		if not path or not os.path.isfile(path):
			return None
		return {"path": path, "offset": os.path.getsize(path), "when": time.time()}
	except Exception:
		return None


def since(position, check=None):
	"""The readable entries NVDA wrote to this run's log after a position from mark(), in order, each with its time worked
	out; [] where there is no position, no log, or another log than the one marked. Entries of the levels IO, DEBUG and
	DEBUG_UNREDACTED are never in it. Only the end of a very large stretch is read (nvdalog.MAX_READ). Works from any thread;
	never raises. For a request of the user only: nothing reads the log by itself."""
	try:
		if not position or not position.get("path"):
			return []
		now = mark()
		if now is None or now["path"] != position["path"] or now["offset"] < position.get("offset", 0):
			return []
		if now["offset"] == position.get("offset", 0):
			return []
		lines, _cut, _size = readFile(position["path"], position.get("offset", 0))
		entries = nvdalog.parse(lines, check)
		nvdalog.stamp(entries, time.time())
		return [entry for entry in entries if not entry.private]
	except Exception:
		return []


def scriptWords():
	"""{(class name, script name): what the command does, and script name: the same} for NVDA's commands where the user is,
	so that a key tried in input help is said by what its command does. Main thread. Never a fault."""
	from . import nvdatools
	found = {}
	for command in _safe(nvdatools._commands, []) or []:
		description = getattr(command, "description", "")
		if not description:
			continue
		cls = getattr(command, "cls", None)
		name = getattr(cls, "__name__", "") if not isinstance(cls, str) else cls
		found.setdefault((name, command.scriptName), description)
		found.setdefault(command.scriptName, description)
	return found


def _readOld(path, check=None):
	if not path or not os.path.isfile(path):
		return []
	lines, _cut, _size = readFile(path)
	entries = nvdalog.parse(lines, check)
	# A closed file: when it was last written is when its last entry was.
	nvdalog.stamp(entries, min(time.time(), _safe(lambda: os.path.getmtime(path), time.time())))
	return entries


def openPanel():
	"""NVDA's settings at the category Privacy and Security, as NVDA's own menu opens it, on NVDA's main thread. Changes
	nothing."""
	import gui
	import wx
	from gui.settingsDialogs import NVDASettingsDialog, PrivacyAndSecuritySettingsPanel
	wx.CallAfter(gui.mainFrame.popupSettingsDialog, NVDASettingsDialog, PrivacyAndSecuritySettingsPanel)


def _reasoning(task):
	return getattr(getattr(task, "params", None), "reasoning", "off") or "off"


def _begun(task):
	"""When the request was made, as seconds since the epoch."""
	started = getattr(task, "started", None)
	if isinstance(started, (int, float)):
		return time.time() - (time.monotonic() - started)
	return time.time()


def _previousEnd(plugin):
	"""When the request before this one ended, as seconds since the epoch, or None."""
	last = _safe(lambda: plugin.orchestrator.last)
	when = getattr(last, "when", None)
	if isinstance(when, (int, float)) and when > 0:
		return time.time() - (time.monotonic() - when)
	return None


def explanation(plugin, task, problem, names, asked):
	"""What the model that writes code says one error means, said to be its own and possibly wrong; "" where it cannot
	answer. Only the error is given, which is of a level that is read."""
	one = policy.isOneModel(plugin.runtime)
	coder = policy.roleName(CODER, one)
	task.emit("talk", f"The {coder} is reading the error from NVDA's log.")
	try:
		said = LLM(plugin.runtime, task).text(
			CODER, prompts.speaking(nvdalog.EXPLAIN_TASK),
			nvdalog.modelFacts(problem, names, clip) + f"\nThe user asked: \"{asked}\"\nWhat does this error mean?",
			maxTokens=320, reasoning=_reasoning(task), temperature=0.2)
	except LLMError:
		return ""
	said = plainSpeech(" ".join(str(said or "").split()))
	return f"What the {coder} says this error means, which may be wrong: {said}" if said else ""


def register(add, plugin, text, onMain, confirm, mustAgree):
	"""The tool for NVDA's own log."""

	def offer(said, state):
		"""Where NVDA's log is off or the user asks to change its level: what is so, and the offer to open NVDA's
		Privacy and Security settings, which changes nothing. Asked directly: an offer is always the user's to take."""
		if not nvdalog.canOffer(state):
			return said
		# Translators: Asked when NVDA's log is off or the user asks to change NVDA's logging level. Before it, VisionClaw
		# says why. Opening the settings changes nothing.
		question = said + " " + _("Open NVDA's Privacy and Security settings now, at the Logging level combo box?")
		# Translators: The two choices of the question above.
		if plugin.clawAsk(question, [_("Yes, open them"), _("No, leave them")]) != 0:
			# Translators: Said when the user did not want NVDA's settings opened.
			return _("NVDA's settings were not opened, and nothing was changed.")
		openPanel()
		debuglog.log("nvdalog", "NVDA's Privacy and Security settings were opened at the user's yes.")
		# Translators: Said after VisionClaw opened NVDA's Privacy and Security settings for the user.
		return _(
			"NVDA's settings are open at Privacy and Security. Press Tab until you reach the Logging level combo box, choose "
			"with the arrow keys, Info is enough, then press Enter. VisionClaw changed nothing itself.")

	def nvdaLog(task, asked):
		# The part's own words decide, never the rest of the request: only what the user asked for is read.
		want = nvdalog.wish(asked)
		if want is None:
			# Translators: Said when the tool for NVDA's log was used for words that do not ask for NVDA's log.
			return _("VisionClaw reads NVDA's log only when you ask for exactly that, so nothing was read.")
		state = _safe(logState, {}) or {}
		do = want["do"]
		debuglog.log("nvdalog", f"Asked of NVDA's log: {do}. Level {nvdalog.levelName(state)}, forced {state.get('forced')}, "
			f"secure {state.get('secure')}, a file {'is' if state.get('file') else 'is not'} named.")
		if do == nvdalog.LEVEL:
			return offer(nvdalog.levelText(state), state) if nvdalog.isOff(state) else nvdalog.levelText(state)
		if do == nvdalog.SETTINGS:
			return offer(nvdalog.settingsText(state), state)
		if do == nvdalog.WHERE:
			return nvdalog.locationText(state)
		names, modules = _safe(lambda: onMain(addonsKnown), ({}, {})) or ({}, {})
		current = state.get("file") or ""
		folder = os.path.dirname(current) if current else _defaultFolder()
		oldPath = os.path.join(folder, nvdalog.OLD_FILE)
		if do == nvdalog.LAST_RUN:
			old = _readOld(oldPath, task.check)
			said = nvdalog.lastRunText(old, names, modules)
			_logged(old, "the run before")
			if nvdalog.isOff(state):
				return offer(said + "\n" + nvdalog.offText(state), state)
			return said
		if nvdalog.isOff(state) or not os.path.isfile(current):
			return offer(nvdalog.offText(state), state)
		stretch = ""
		if do == nvdalog.RECENT and want.get("since") == nvdalog.SINCE_READ and _lastRead.get("path") == current:
			start = _lastRead.get("offset")
			stretch = f"since VisionClaw last read it, at {time.strftime('%H:%M:%S', time.localtime(_lastRead.get('when')))}"
		else:
			start = None
		lines, cut, size = readFile(current, start)
		entries = nvdalog.parse(lines, task.check)
		nvdalog.stamp(entries, time.time())
		_lastRead.update(path=current, offset=size, when=time.time())
		_logged(entries, "this run")
		lead = ""
		if cut:
			lead = (f"NVDA's log is very large, so VisionClaw read its last {nvdalog.MAX_READ >> 20} megabytes"
				+ (f", from {entries[0].clock[:8]} on" if entries else "") + ". ")
		level = nvdalog.levelName(state)
		private = nvdalog.privateText(entries)
		if do == nvdalog.RECENT:
			if not stretch:
				fromWhen, until, stretch = nvdalog.window(want.get("since"), _begun(task), _previousEnd(plugin))
				entries = nvdalog.entriesSince(entries, fromWhen, until)
			return lead + nvdalog.recentText(entries, stretch, modules, names)
		if do == nvdalog.SESSION:
			hasOld = os.path.isfile(oldPath)
			return lead + nvdalog.sessionText(entries, _readOld(oldPath, task.check) if hasOld else None, time.time(), modules, names)
		if do == nvdalog.OBJECT:
			infos = nvdalog.devInfos(entries)
			if want.get("compare"):
				return lead + nvdalog.compareText(*(infos[-2:] if len(infos) >= 2 else (None, None)))
			return lead + nvdalog.objectText(infos[-1] if infos else None, want.get("field"), modules, names)
		if do == nvdalog.INPUT_HELP:
			describe = _safe(lambda: onMain(scriptWords), {}) or {}
			return lead + nvdalog.inputHelpText(nvdalog.inputHelp(entries, modules), names, want.get("last"), describe)
		if do == nvdalog.SAVED:
			return lead + nvdalog.savedText(entries, modules)
		if do == nvdalog.PARTS:
			return lead + nvdalog.partsText(entries, asked, modules)
		problems = nvdalog.errors(entries, modules)
		if do == nvdalog.EXPLAIN:
			problem = nvdalog.chosen(problems, want, names)
			if problem is None:
				return lead + "NVDA's log of this run has no errors, so there is nothing to explain."
			# One error asked about is told with Python's own words and the file and line: what a bug report needs.
			told = nvdalog.problemText(problem, names, detail=True)
			return " ".join(part for part in (lead + told, explanation(plugin, task, problem, names, asked)) if part)
		if do == nvdalog.FREEZES:
			said = nvdalog.freezesText(nvdalog.freezes(entries, modules), names)
			oldEnd = nvdalog.ending(_readOld(oldPath, task.check), modules, names) if os.path.isfile(oldPath) else None
			if oldEnd and oldEnd["how"] == nvdalog.FROZE:
				said += "\nThe run before ended while NVDA was frozen: " + oldEnd["said"]
			return lead + said + (f"\n{private}" if private else "")
		if do == nvdalog.DRIVERS:
			groups = nvdalog.groupsAsked(asked)
			found = nvdalog.driverFacts(entries, groups, modules)
			return lead + nvdalog.driversText(found, level, "this run", groups)
		if do == nvdalog.ADDONS:
			said = nvdalog.addonsText(problems, nvdalog.freezes(entries, modules), names, "this run", want.get("about", ""))
			old = _readOld(oldPath, task.check)
			oldEnd = nvdalog.ending(old, modules, names) if old else None
			if oldEnd and oldEnd["how"] == nvdalog.CRASHED and "add-on" in oldEnd["said"]:
				said += "\nIn the run before: " + oldEnd["said"]
			elif old:
				summary = nvdalog.addonsSummary(nvdalog.errors(old, modules), names)
				if summary and nvdalog.byAddon(nvdalog.errors(old, modules)):
					said += "\nIn the run before: " + summary
			return lead + said + (f"\n{private}" if private else "")
		# ERRORS
		named = nvdalog.addonNamed(want.get("about", ""), names)
		if named:
			return lead + nvdalog.addonsText(problems, [], names, "this run", want.get("about", "")) + (f"\n{private}" if private else "")
		return lead + nvdalog.errorsText(problems, names) + (f"\n{private}" if private else "")

	add("nvda_log",
		"read NVDA's own log, only when the user asks: its errors and which add-on they come from, freezes, trouble with the "
		"speech synthesizer, the sound or the braille display, how NVDA ended last time, what NVDA wrote just now, when NVDA "
		"started, the developer info of an object (NVDA+f1), keys tried in input help, settings saved or put back, NVDA "
		"Remote, Java and UI Automation, and NVDA's logging level",
		nvdaLog, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Reading NVDA's own log", tell=VERBATIM)


def _logged(entries, which):
	"""What VisionClaw's own log is told of a read: counts only, never what NVDA's log says."""
	counts = {}
	for entry in entries:
		counts[entry.level] = counts.get(entry.level, 0) + 1
	debuglog.log("nvdalog", f"Read NVDA's log of {which}: {len(entries)} entries, by level {sorted(counts.items())}.")
