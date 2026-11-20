# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a whole program made accessible, one window after another (claw/appaccess.py), as tools:
#   learn_program  learns the window or page the user is in with the deep inspection (accesstools.inspect), names the
#                  controls without a name from their pictures while they show, or with a name found for them in another
#                  window of the program before; puts the window on the program's map and its steps into the plan; says
#                  which windows of the program are known, the plan, or turns following on or off, or forgets the map
#   fix_program    makes every fix the plan holds for the whole program, from all of its windows, in the program's one
#                  fixes add-on, after one question; hotkeys for dragged controls of the window in front; and says what
#                  is left
# and the Follower: when the user moves to another window of a program they asked VisionClaw to make accessible, it is
# learned by itself with the quick inspection, which reads NVDA's facts and asks no model; one sentence says what was
# found, where the user lets it (the setting programFollow). Nothing is made without the user's yes.
# What it uses besides the inspection, each by plain code: the program's own Markdown file of what VisionClaw found
# (claw/accessnotes.py), which holds the map; the memories the user asked VisionClaw to keep about the program, whose
# steps come first; the learning scratchpad of the program, on which one line says what VisionClaw knows of it; and
# NVDA's own log, whose recent errors, freezes and developer info are said after a window is learned. Models are asked
# only what the inspection asks them, and to name a control from its picture; never to write a fix or decide the plan.

import json
import os
import re
import threading
import time
import types

import addonHandler
import api
import config
import wx

from . import accesstools, fixruntime, scratchtools
from .claw import accessnotes, appaccess, audit, debuglog, fixes, microaddons, scratchpad, skilllog
from .claw.fixmatch import hostOf
from .claw.tools import VERBATIM, ToolError
from .nvdatools import UserSaidNo, _safe, onMain

addonHandler.initTranslation()

# Which programs the user asked VisionClaw to make accessible, and for which they said to stop following: plain data in
# VisionClaw's data folder.
FOLLOW_FILE = "programs-followed.json"
# The kinds of fact of NVDA's log that are said after a window was learned (claw/skilllog.py).
LOG_KINDS = ("errors", "freezes", "objects")
# Fixes that tell of a change each look for their part every few seconds where it is not shown: a program keeps at most
# this many, however many windows it has.
MAX_WATCHES = 8
# How many groups of controls without a name are named from their pictures in one window.
MAX_LOOKED = accesstools.MAX_NAMES_BY_LOOKING
_lock = threading.RLock()


# --- The map, in the program's own file ---

def _notes(plugin):
	return accesstools.accessNotes(plugin)


def mapOf(plugin, scope):
	"""(the windows, the plan) of a program or website, as its file holds them now."""
	notes = _notes(plugin)
	return (appaccess.placesFrom(notes.entries(scope, accessnotes.WINDOWS)),
		appaccess.planFrom(notes.entries(scope, accessnotes.PLAN)))


def saveMap(plugin, scope, places, plan):
	notes = _notes(plugin)
	notes.setEntries(scope, accessnotes.WINDOWS, appaccess.placeLines(places))
	notes.setEntries(scope, accessnotes.PLAN, appaccess.planLines(plan, places, scope))


def installed(plugin, scope):
	"""The fixes the program's or website's add-on has now, with their keys; [] when it has none."""
	store = plugin.helpers.store
	wanted = fixes.scopeOf(scope.get("site", ""), scope.get("app", ""))
	for apart in (False, True):
		source = store.source(microaddons.slug(fixes.addonName(wanted, apart)))
		parsed = fixes.parse(source) if source else None
		if parsed is not None and parsed[0] == wanted:
			return parsed[1]
	return []


def _following(plugin):
	path = os.path.join(plugin.dataDir, FOLLOW_FILE)
	try:
		with open(path, encoding="utf-8") as f:
			data = json.load(f)
		return {"on": [str(n) for n in data.get("on") or ()], "off": [str(n) for n in data.get("off") or ()]}
	except (OSError, ValueError, AttributeError):
		return {"on": [], "off": []}


def _setFollowing(plugin, name, on):
	data = _following(plugin)
	data["on"] = [n for n in data["on"] if n != name] + ([name] if on else [])
	data["off"] = [n for n in data["off"] if n != name] + ([] if on else [name])
	try:
		os.makedirs(plugin.dataDir, exist_ok=True)
		with open(os.path.join(plugin.dataDir, FOLLOW_FILE), "w", encoding="utf-8") as f:
			json.dump(data, f, indent="\t")
	except OSError as e:
		debuglog.error("appaccess", "Which programs are followed could not be kept", e)


def isFollowed(plugin, scope):
	name = scope.get("app") or scope.get("site") or ""
	data = _following(plugin)
	return bool(name) and name in data["on"] and name not in data["off"]


def _setting():
	try:
		value = config.conf["visionClaw"]["programFollow"]
	except Exception:
		return appaccess.FOLLOW_TELL
	return value if value in appaccess.FOLLOW_CHOICES else appaccess.FOLLOW_TELL


# --- Where the user is ---

def _names(window):
	"""What the program is called: its file's name and the name its maker gave it. Main thread."""
	module = _safe(lambda: window.appModule)
	return [name for name in (_safe(lambda: module.appName, ""), _safe(lambda: module.productName, "")) if name]


def identOf(found):
	"""(what tells the inspected window or page apart, its name, its kind) for an inspection. Main thread."""
	if found.kind == "page":
		address = _safe(lambda: fixruntime.pageAddress(found.where), "") or ""
		return appaccess.pageId(address), found.title or address or "a page without a title", "page"
	window = found.where
	cls = _safe(lambda: window.windowClassName, "") or ""
	role = getattr(_safe(lambda: window.role), "name", "")
	return (appaccess.windowId(cls, found.title, _names(window)), found.title or "a window without a title",
		appaccess.kindOf(role, cls))


def scopeHere():
	"""The program or website the user is in, as fixes are tied to it. Main thread."""
	_focus, _window, document, app, _title = accesstools._situation()
	if document is not None:
		site = hostOf(_safe(lambda: fixruntime.pageAddress(document), "") or "")
		if site:
			return fixes.scopeOf(site=site)
	return fixes.scopeOf(app=app)


def memoriesAbout(plugin, scope, names=()):
	"""What the user asked VisionClaw to remember about this program, and what they wrote themselves on its learning
	scratchpad, as lines: the steps of the plan they are about come first. Never a fault."""
	wanted = {str(n).lower() for n in list(names) + [scope.get("app", ""), scope.get("site", "")] if n}
	lines = []
	try:
		for entry in plugin.memories.all():
			if entry.program and entry.program.lower() in wanted:
				lines.append(entry.text())
	except Exception:
		pass
	try:
		pads = getattr(plugin, "pads", None)
		for name in wanted:
			pad = pads.learning(name) if pads is not None else None
			if pad is not None:
				lines += [note.text for note in pad.notes if note.by == scratchpad.BY_YOU]
	except Exception:
		pass
	return lines


def logLines(plugin):
	"""What NVDA logged in the last minutes that may tell more about this window: errors, freezes, and the developer info
	of an object the user checked with NVDA+F1 (claw/skilllog.py). [] where the log is not read. Never a fault."""
	feed = getattr(plugin, "nvdaLogFeed", None)
	if feed is None:
		return []
	try:
		entries = feed.recent()
		if not entries:
			return []
		modules, names = feed.addons()
		return skilllog.lines(entries, LOG_KINDS, time.time(), modules, names)
	except Exception as e:
		debuglog.error("appaccess", "NVDA's log could not be read for a window that was learned", e)
		return []


def _scratch(plugin, scope, places, plan):
	"""One line on the learning scratchpad of the program: what VisionClaw knows of it, for the models that work there
	later. It takes the place of the line written before. Only where the user lets VisionClaw keep scratchpads."""
	pads = getattr(plugin, "pads", None)
	if pads is None or not scratchtools._keeping():
		return
	try:
		program = onMain(scratchtools.subjectNow) or scope.get("app") or scope.get("site") or ""
		make, made, window, advice = appaccess.counts(plan)
		word = appaccess.placesWord(scope, len(places))
		named = (": " + appaccess._joined(place.name for place in places)) if len(places) <= appaccess.NAMED_WINDOWS else (
			"; the program's access notes list them all")
		pads.learn(program,
			f"VisionClaw is making {program} accessible window by window. It has learned {len(places)} {word} of it{named}. "
			f"Its accessibility plan has {make} fixes to make, {made} made, {window} that need their {appaccess.placesWord(scope, 1)} "
			f"open and {advice} that no add-on can fix.", scratchpad.BY_VISIONCLAW, "the accessibility plan")
	except Exception as e:
		debuglog.error("appaccess", "The program's scratchpad line could not be written", e)


# --- What look_up is given (retrieval) ---

# The words of a question about the windows of a program, their problems or the plan: only then are the lines of the map
# asked, so that an everyday question is not answered with an inspection's findings.
_GATE = re.compile(
	r"\b(windows?|dialogs?|pages?|screens?|plan|fix\w*|accessib\w*|problems?|issues?|unlabell?ed|unnamed|without a name|"
	r"learn\w*|inspect\w*|found|steps?)\b", re.IGNORECASE)


def passages(plugin, question=""):
	"""The lines of the map of the program or website the user is in, as look_up's passages: the plan in numbers, every
	window learned, and every step of the plan, each saying where it is from (prompts.PROGRAM_HELP goes with an answer
	worded from them). [] when nothing was learned there. Never a fault."""
	try:
		from .claw import lookup
		scope = onMain(scopeHere)
		if not (scope.get("app") or scope.get("site")):
			return []
		with _lock:
			places, plan = mapOf(plugin, scope)
			plan = appaccess.refreshed(plan, installed(plugin, scope))
		if not places:
			return []
		origin = f"what VisionClaw learned about the {appaccess.placesWord(scope)} of {appaccess.where(scope)}"
		names = appaccess.namesOf(places)
		found = [lookup.Passage(lookup.APP, "the plan", appaccess.countText(plan, scope, places), origin, lead=True, gate=_GATE)]
		found += [lookup.Passage(lookup.APP, place.name, place.line(), origin, lead=True, gate=_GATE) for place in places]
		found += [lookup.Passage(lookup.APP, "a step of the plan", appaccess.stepLine(step, names, scope), origin, lead=True, gate=_GATE)
			for step in plan]
		return found
	except Exception as e:
		debuglog.error("appaccess", "The program's map could not be given to look_up", e)
		return []


def contextText(plugin):
	"""One sentence for the model that chooses, where the user is in a program VisionClaw is making accessible: how many
	of its windows are known and how much of the plan is left (claw/orchestrator.py, programMap). "" elsewhere. Read on
	the request's worker thread; never a fault."""
	try:
		scope = onMain(scopeHere)
		if not (scope.get("app") or scope.get("site")) or not isFollowed(plugin, scope):
			return ""
		with _lock:
			places, plan = mapOf(plugin, scope)
			plan = appaccess.refreshed(plan, installed(plugin, scope))
		return appaccess.contextText(places, plan, scope)
	except Exception as e:
		debuglog.error("appaccess", "The program's map could not be told to the model that chooses", e)
		return ""


# --- Learning one window ---

def _named(plugin, task, found, deep):
	"""Names for the groups of controls without a name in an inspection: one read before from a picture in any window of
	the program (the same control keeps its name everywhere), else, in a deep inspection, one read now from its picture
	by the model that sees. {ruleKey: name}."""
	notes = _notes(plugin)
	named, looked = {}, 0
	for finding in found.report.findings:
		for group in finding.look:
			key = accessnotes.keyOf(group.get("rule"))
			known = notes.knownName(found.scope, key)
			if known:
				named[appaccess.ruleKey(group.get("rule"))] = known
				continue
			if not deep or looked >= MAX_LOOKED:
				continue
			looked += 1
			task.check()
			name = accesstools.nameByLooking(plugin, task, found, group)
			if name:
				named[appaccess.ruleKey(group.get("rule"))] = name
	return named


def remember(plugin, task, found, how=appaccess.ASKED, deep=True):
	"""Put an inspected window or page on its program's map, and its steps into the plan. Returns (the window, every
	window known, the plan in order, the steps of this window, how many steps a memory moved forward)."""
	scope = found.scope
	ident, name, kind = onMain(identOf, found)
	where = appaccess.ref(ident)
	named = _named(plugin, task, found, deep)
	new = appaccess.stepsFrom(found.report, where, named)
	names = onMain(lambda: _names(found.where)) if found.kind == "window" else []
	with _lock:
		places, plan = mapOf(plugin, scope)
		before = next((place for place in places if place.key() == where), None)
		place = appaccess.placeFrom(found.report, ident, name, kind, how, before)
		places = appaccess.withPlace(places, place)
		plan = appaccess.merged(plan, new, where)
		plan = appaccess.refreshed(plan, installed(plugin, scope))
		plan, moved = appaccess.favoured(plan, memoriesAbout(plugin, scope, names))
		saveMap(plugin, scope, places, plan)
	_scratch(plugin, scope, places, plan)
	mine = [step for step in plan if where in step.windows]
	debuglog.log("appaccess", f"Learned {kind} {name!r} of {appaccess.where(scope)} ({how}): {len(found.report.findings)} "
		f"problems, {len(mine)} steps, {len(places)} places known.")
	return place, places, plan, mine, moved


def record(plugin, found):
	"""After a deep inspection asked for by itself (check_access): the window is put on the program's map too, so that
	every window inspected is known as part of its program. Never a fault: it only helps."""
	try:
		if not (found.scope.get("app") or found.scope.get("site")):
			return
		with _lock:
			places, _plan = mapOf(plugin, found.scope)
		# Only for a program the user asked VisionClaw to make accessible: an inspection alone starts no map.
		if places or isFollowed(plugin, found.scope):
			remember(plugin, types.SimpleNamespace(check=lambda: None), found, deep=False)
	except Exception as e:
		debuglog.error("appaccess", "An inspected window could not be put on its program's map", e)


def _inspection(plugin, task, asked, deep=True):
	"""The inspection of where the user is, made once for a request (as check_access does)."""
	target = appaccess.targetOf(asked)
	wanted = target if target in ("page", "window") else None
	found = getattr(task, "access", None)
	if (found is None or (wanted and found.kind != wanted) or (deep and not found.deep) or not onMain(accesstools._samePlace, found)):
		found = task.access = accesstools.inspect(plugin, task, target, "deep" if deep else "quick")
		found.deep = deep
	if not (found.scope.get("app") or found.scope.get("site")):
		raise ToolError("VisionClaw could not tell which program or website this is, so nothing was learned.")
	return found


# --- The tools ---

def register(plugin, add, text, onMainFn=None, confirm=None, mustAgree=None):
	"""The tools for making a whole program accessible. add and text are the helpers of nvdatools.build."""

	def learnProgram(task, asked):
		wish = appaccess.wish(asked) or {"do": appaccess.LEARN}
		do = wish["do"]
		if do in (appaccess.WINDOWS_SAID, appaccess.PLAN_SAID, appaccess.FORGET, appaccess.UNFOLLOW):
			scope = onMain(scopeHere)
			if not (scope.get("app") or scope.get("site")):
				raise ToolError("VisionClaw could not tell which program or website you are in.")
			with _lock:
				places, plan = mapOf(plugin, scope)
				plan = appaccess.refreshed(plan, installed(plugin, scope))
			if do == appaccess.WINDOWS_SAID:
				return appaccess.windowsText(places, scope)
			if do == appaccess.PLAN_SAID:
				if not places:
					return appaccess.windowsText(places, scope)
				plan, moved = appaccess.favoured(plan, memoriesAbout(plugin, scope))
				return appaccess.planText(plan, scope, places, moved)
			if do == appaccess.UNFOLLOW:
				_setFollowing(plugin, scope.get("app") or scope.get("site"), False)
				return (f"VisionClaw no longer learns the windows of {appaccess.where(scope)} by itself when you move to them. "
					"What it learned and its plan stay. To have it learn them again, say: keep learning the windows of this program.")
			# Forgetting: the map and the plan go; the fixes that were made stay in the program's add-on.
			if not places and not plan:
				return f"VisionClaw has learned no windows of {appaccess.where(scope)}, so there is nothing to forget."
			# Translators: Asked before what VisionClaw learned about a program's windows and its plan are forgotten.
			question = _(
				"Forget the {count} windows VisionClaw learned of {where} and its plan of {steps} steps? The fixes already "
				"made stay in the program's add-on.").format(count=len(places), where=appaccess.where(scope), steps=len(plan))
			# Translators: The choices before the windows of a program and its plan are forgotten.
			if plugin.clawAsk(question, [_("Forget them"), _("Keep them")]) != 0:
				raise UserSaidNo()
			with _lock:
				saveMap(plugin, scope, [], [])
			_setFollowing(plugin, scope.get("app") or scope.get("site"), False)
			return (f"Forgot the {len(places)} windows and the plan of {appaccess.where(scope)}. The fixes already made stay in "
				"its add-on; ask VisionClaw to remove that add-on to take them away.")
		found = _inspection(plugin, task, asked)
		scope = found.scope
		# Asked in words to work on the whole program: the windows the user moves to are learned too, where the setting
		# lets VisionClaw follow (pages of a website are learned when the user asks).
		_setFollowing(plugin, scope.get("app") or scope.get("site"), True)
		place, places, plan, mine, moved = remember(plugin, task, found)
		setting = _setting() if not scope.get("site") else appaccess.FOLLOW_OFF
		said = logLines(plugin)
		if do in appaccess.MAKES:
			# The fixes are made in the next step, which says what is left; here the window and the plan in numbers.
			return appaccess.learnedText(place, scope, found.report.findings, mine, plan, places, said, moved, setting,
				nextStep=False)
		if do == appaccess.PLAN:
			return (appaccess.learnedText(place, scope, found.report.findings, mine, plan, places, said, moved, setting,
				counted=False, nextStep=False) + "\n" + appaccess.planText(plan, scope, places, moved))
		return appaccess.learnedText(place, scope, found.report.findings, mine, plan, places, said, moved, setting)

	add("learn_program",
		"learn the program's window or the web page the user is in, put it on the map of the whole program with its other "
		"windows, and plan the fixes for all its accessibility problems; or say which windows are known, the plan, keep or "
		"stop learning new windows, or forget them",
		learnProgram, {"asked": text("what the user asked for, in their own words", maxLength=600, auto=True)},
		looks=True, title="Learning this window of the program", tell=VERBATIM)

	def fixProgram(task, asked):
		found = getattr(task, "access", None)
		scope = found.scope if found is not None else onMain(scopeHere)
		if not (scope.get("app") or scope.get("site")):
			raise ToolError("VisionClaw could not tell which program or website you are in.")
		with _lock:
			places, plan = mapOf(plugin, scope)
			plan = appaccess.refreshed(plan, installed(plugin, scope))
		if not places:
			raise ToolError(f"VisionClaw has learned no window of {appaccess.where(scope)} yet. Say: learn this window.")
		plan, _moved = appaccess.favoured(plan, memoriesAbout(plugin, scope))
		steps = appaccess.toMake(plan)
		watches = [step for step in installed(plugin, scope) if step.get("kind") == fixes.WATCH]
		room = max(0, MAX_WATCHES - len(watches))
		chosen, held = [], 0
		for step in steps:
			if step.fix["kind"] == fixes.WATCH:
				if room <= 0:
					held += 1
					continue
				room -= 1
			chosen.append(step)
		room = fixes.MAX_FIXES - len(installed(plugin, scope))
		if len(chosen) > room:
			held += len(chosen) - room
			chosen = chosen[:max(0, room)]
		said = []
		if chosen:
			new = [dict(step.fix, keys=[]) for step in chosen]
			said.append(accesstools.install(plugin, task, types.SimpleNamespace(scope=scope), new))
		# Hotkeys for controls of the window in front that are dragged, held or rested on: they need the window's places.
		controls = []
		if found is not None and onMain(accesstools._samePlace, found):
			for finding in found.report.findings:
				controls += finding.controls
		if controls:
			try:
				said.append(accesstools.keepControls(plugin, task, controls))
			except UserSaidNo:
				said.append("The hotkeys for the controls that are dragged or held were not made, as you said.")
			except ToolError as e:
				said.append(str(e))
		if held:
			said.append(
				f"{held} {'fix was' if held == 1 else 'fixes were'} left for later: a program keeps at most {MAX_WATCHES} fixes that "
				f"tell of a change, since each looks for its part every few seconds, and at most {fixes.MAX_FIXES} fixes in all.")
		with _lock:
			places, plan = mapOf(plugin, scope)
			plan = appaccess.refreshed(plan, installed(plugin, scope))
			plan, _moved = appaccess.favoured(plan, memoriesAbout(plugin, scope))
			saveMap(plugin, scope, places, plan)
		_scratch(plugin, scope, places, plan)
		if not chosen and not controls:
			said.append(f"Nothing of the plan for {appaccess.where(scope)} is left that an add-on can make now.")
		said.append(appaccess.leftText(plan, appaccess.namesOf(places), scope))
		return "\n".join(part for part in said if part)

	add("fix_program",
		"make every fix the plan holds for the whole program or website, from all the windows learned, in its one fixes "
		"add-on after one question, and say what is left",
		fixProgram, {"asked": text("what the user asked for, in their own words", maxLength=600, auto=True)},
		changes=True, before="learn_program", title="Making the planned accessibility fixes", tell=VERBATIM)


# --- Following the user from window to window ---

class _Stopped(Exception):
	pass


class Follower:
	"""Learns a window of a program the user asked VisionClaw to make accessible, when the user moves there and stays a
	moment. The quick inspection only: NVDA's facts, no picture, no model. say(text): VisionClaw's own speech."""

	def __init__(self, plugin, say, stopped):
		self.plugin = plugin
		self._say = say
		self._stopped = stopped
		self._generation = 0
		self._cancel = threading.Event()
		self._timer = None
		self._learning = False

	def foreground(self, obj):
		"""NVDA's foreground event, on its main thread. Never raises."""
		try:
			if _setting() == appaccess.FOLLOW_OFF:
				return
			self._generation += 1
			self._cancel.set()
			if self._timer is not None:
				self._timer.Stop()
			self._timer = wx.CallLater(int(appaccess.SETTLE_SECONDS * 1000), self._settled, self._generation)
		except Exception:
			debuglog.log("appaccess", "A window that came to the front could not be followed.")

	def _settled(self, generation):
		"""Main thread: the user stayed in the window. What it is is read here, and learning goes on in a thread."""
		try:
			if generation != self._generation or self._learning or self._busy():
				return
			_focus, window, document, app, title = accesstools._situation()
			if document is not None or not app or app == "nvda":
				return
			from . import guidetools
			if _safe(guidetools.ownWindow, False) is True:
				return
			scope = fixes.scopeOf(app=app)
			cls = _safe(lambda: window.windowClassName, "") or ""
			role = getattr(_safe(lambda: window.role), "name", "")
			ident = appaccess.windowId(cls, title, _names(window))
			here = (scope, ident, title, appaccess.kindOf(role, cls), window)
		except Exception:
			return
		self._cancel = threading.Event()
		threading.Thread(target=self._learn, args=(generation, here, self._cancel), name="visionClaw-follow", daemon=True).start()

	def _busy(self):
		task = getattr(self.plugin, "clawTask", None)
		return task is not None and not task.finished

	def _learn(self, generation, here, cancel):
		scope, ident, title, kind, window = here
		plugin = self.plugin
		try:
			if not isFollowed(plugin, scope):
				return
			with _lock:
				places, _plan = mapOf(plugin, scope)
			if not appaccess.follows(_setting(), [], scope, {place.key() for place in places}, appaccess.ref(ident)):
				return
			self._learning = True

			def check():
				if cancel.is_set() or self._stopped.is_set():
					raise _Stopped()

			waiting = types.SimpleNamespace(check=check, emit=lambda *args, **kwargs: None)
			nodes = accesstools._windowNodes(waiting, window)
			check()
			report = audit.auditWindow(nodes, title=title, app=scope.get("app", ""))
			found = accesstools.Inspection("window", scope, nodes, window, report, title, None)
			found.deep = False
			place, places, plan, mine, _moved = remember(plugin, waiting, found, how=appaccess.BY_ITSELF, deep=False)
			check()
			# Nothing is said while a request is being worked on, while another window came to the front since, or while
			# the microphone is open, which would record it.
			listening = _safe(lambda: plugin.voice.listening(), False) is True
			if _setting() == appaccess.FOLLOW_TELL and generation == self._generation and not self._busy() and not listening:
				self._say(appaccess.followedText(place, scope, report.findings, mine, appaccess.counts(plan)[0]))
		except _Stopped:
			return
		except Exception as e:
			debuglog.error("appaccess", "A window could not be learned by itself", e)
		finally:
			self._learning = False

	def terminate(self):
		self._cancel.set()
		try:
			if self._timer is not None:
				self._timer.Stop()
		except Exception:
			pass
