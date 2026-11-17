# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools for making a website, a program's window or one control usable for good:
#   check_access   a deep inspection, and the report of what stands in the way and what can be fixed
#   fix_access     makes the fixes for the problems found, as one add-on per website or program
#   add_fix        one fix the user asks for in words: a key that presses or reads something, keys that move
#                  between items, a name for a control, or being told when something changes
#   addon_info     what an add-on installed in this NVDA is, what its commands are, and what its help says
# Code inspects, decides what is a problem, and puts the add-on together from fixed, tested parts. The models
# choose what the user means and name icons from their pictures; they never write this add-on's code.
# The functions run on the task's worker thread; everything that touches NVDA is passed to NVDA's main thread.

import html
import os
import re
import sys
import time

import addonHandler
import api
import config
import inputCore
from logHandler import log

from . import fixruntime, nvdainfo, ocr
from .claw import audit, fixes, match, microaddons, web
from .claw.fixmatch import hostOf, labelOf, matches, nodeFromObject, plainText
from .claw.llm import clip
from .claw.tools import VERBATIM, ToolError
from .engine import prepareImage
from .nvdatools import UserSaidNo, _safe, onMain

addonHandler.initTranslation()

# A long page is read a stretch at a time, so NVDA stays responsive and the task can be stopped in between.
PAGE_CHUNK = 60000
MAX_PAGE_NODES = 8000
MAX_WINDOW_NODES = 1500
WINDOW_SECONDS = 8
SLICE_SECONDS = 0.12
# How long to wait before the second look that shows what changes by itself.
CHANGE_WAIT_SECONDS = 2.5
MAX_NAMES_BY_LOOKING = 8
# How long a number the user heard in a report still means that report's problem.
HEARD_SECONDS = 1800
_KIND_OF = {"press": fixes.PRESS, "read": fixes.READ, "move": fixes.JUMP, "name": fixes.NAME, "announce": fixes.WATCH}
_THIS = re.compile(r"\b(this|that|focused|current|it)\b", re.IGNORECASE)
# The user's own words say that the control with the focus is meant.
_FOCUSED = re.compile(
	r"\b(focused|this|current|that)\s+(button|control|link|field|icon|item|image|checkbox|slider|tab|one)\b", re.IGNORECASE)
_ADDON_PARTS = (
	("globalPlugins", "commands that work everywhere"), ("appModules", "support for these programs"),
	("synthDrivers", "speech synthesizers"), ("brailleDisplayDrivers", "braille display drivers"),
	("visionEnhancementProviders", "vision helpers"),
)


targetOf, depthOf, kindOf = audit.targetOf, audit.depthOf, audit.kindOf


class Inspection:
	"""What one inspection found. kind: "page" or "window". nodes: the controls. where: the page (NVDA's
	browse mode document) or the window."""

	def __init__(self, kind, scope, nodes, where, report, title, focus):
		self.kind, self.scope, self.nodes, self.where = kind, scope, nodes, where
		self.report, self.title, self.focus = report, title, focus
		self.extra = ""
		self.deep = False


def _situation():
	"""Where the user is. Main thread."""
	focus = api.getFocusObject()
	window = api.getForegroundObject()
	document = getattr(focus, "treeInterceptor", None)
	if document is not None and not (_safe(lambda: fixruntime.isPage(document)) and getattr(document, "isReady", True)):
		document = None
	app = _safe(lambda: window.appModule.appName) or _safe(lambda: focus.appModule.appName) or ""
	title = _safe(lambda: document.rootNVDAObject.name) if document is not None else _safe(lambda: window.name)
	return focus, window, document, app, " ".join(str(title or "").split())


def _pageNodes(task, document):
	"""Every control of a page, read a stretch at a time."""
	first, last = onMain(fixruntime.pageRange, document)
	chunks, at, count = [], first, 0
	while at < last and count < MAX_PAGE_NODES:
		task.check()
		stop = min(last, at + PAGE_CHUNK)
		found = onMain(fixruntime.pageChunk, document, at, stop)
		chunks.append(found)
		count += len(found)
		at = stop
	return audit.joinChunks(chunks)


def _windowNodes(task, root):
	"""Every control NVDA knows in a window, gathered in short turns on NVDA's main thread."""
	walker = fixruntime.windowNodes(root, limit=MAX_WINDOW_NODES, seconds=3600)
	nodes = []

	def turn():
		end = time.monotonic() + SLICE_SECONDS
		for node in walker:
			nodes.append(node)
			if time.monotonic() > end:
				return False
		return True

	deadline = time.monotonic() + WINDOW_SECONDS
	while not onMain(turn) and time.monotonic() < deadline:
		task.check()
	return nodes


def _drawn(plugin, box):
	"""The lines of text in a picture of the page or window, for finding text NVDA cannot read."""
	if not config.conf["visionClaw"]["useOcr"] or box is None:
		return []
	try:
		lines = ocr.recognize(plugin._grab(box))
	except Exception:
		log.debugWarning("VisionClaw: the picture could not be read for the inspection", exc_info=True)
		return []
	return [line for line in ocr.rowsText(lines).splitlines() if line.strip()]


def _boxOf(obj):
	"""The place of a control on the screen, or None if it is not showing. Main thread."""
	if obj is None or _safe(lambda: obj.hasIrrelevantLocation, True):
		return None
	place = _safe(lambda: obj.location)
	if not place or place.width < 8 or place.height < 8:
		return None
	return (place.left, place.top, place.left + place.width, place.top + place.height)


def _controlOf(inspection, node):
	"""NVDA's own object for a control of the inspection. Main thread."""
	if node.get("obj") is not None:
		return node["obj"]
	key = node.get("key")
	if key is None or inspection.kind != "page":
		return None
	return _safe(lambda: inspection.where.getNVDAObjectFromIdentifier(int(key[0]), int(key[1])))


def _focusedNode(inspection):
	"""The control of the inspection that has the focus, or None. Main thread."""
	focus = api.getFocusObject()
	if inspection.kind == "page":
		ident = _safe(lambda: inspection.where.getIdentifierFromNVDAObject(focus))
		if not ident:
			return None
		for node in inspection.nodes:
			key = node.get("key")
			if key is not None and (int(key[0]), int(key[1])) == (int(ident[0]), int(ident[1])):
				return node
		return None
	for node in inspection.nodes:
		if node.get("obj") == focus:
			return node
	return nodeFromObject(focus)


def controlText(inspection):
	"""What NVDA knows about the focused control, and what can be done for it, in plain sentences. Main thread."""
	focus = api.getFocusObject()
	role = _safe(lambda: focus.role.displayString) or "control"
	name = " ".join(str(_safe(lambda: focus.name) or "").split())
	lines = [f"The focused control is a {role}" + (f" called {name}." if name else " with no name, so NVDA only says what kind it is.")]
	value = _safe(lambda: focus.value)
	if value:
		lines.append(f"Its value is {clip(str(value), 80)}.")
	described = _safe(lambda: focus.description)
	if described:
		lines.append(f"Its description is {clip(str(described), 120)}.")
	states = sorted(_safe(lambda s=state: s.displayString) or "" for state in (_safe(lambda: focus.states) or ()))
	if any(states):
		lines.append("NVDA reports it as: " + ", ".join(s for s in states if s) + ".")
	shortcut = _safe(lambda: focus.keyboardShortcut)
	if shortcut:
		lines.append(f"Its own shortcut key is {shortcut}.")
	node = _focusedNode(inspection)
	rule = audit.signature(node) if node is not None else None
	if rule is None:
		lines.append(
			"Nothing fixed in the code of the page or program tells it apart from other controls, so an add-on "
			"cannot name it or watch it reliably. A key can still press it if it has a name.")
	else:
		same = sum(matches(rule, other) for other in inspection.nodes) or 1
		lines.append(
			"It can be found again on a later visit" + (f", together with {same - 1} controls like it." if same > 1 else ".")
			+ " So VisionClaw can give it a name, make a key that presses or reads it, or tell you when it changes.")
	return " ".join(lines)


def inspect(plugin, task, target="auto", depth="deep"):
	"""Inspect where the user is. Raises ToolError when the target is not there."""
	focus, window, document, app, title = onMain(_situation)
	if target == "page" and document is None:
		raise ToolError(
			"The user is not in a web page that NVDA reads in browse mode. Move into the page first, or check the "
			"program's window instead.")
	deep = depth == "deep"
	if document is not None and target != "window":
		site = hostOf(onMain(fixruntime.pageAddress, document))
		task.emit("detail", "Reading every control of the page.")
		nodes = _pageNodes(task, document)
		later = drawn = None
		if deep and len(nodes) <= 4000:
			drawn = _drawn(plugin, onMain(lambda: _boxOf(document.rootNVDAObject)))
			task.emit("detail", "Watching the page for a moment, to see what changes by itself.")
			_wait(task, CHANGE_WAIT_SECONDS)
			later = _pageNodes(task, document)
		report = audit.auditPage(nodes, title=title, site=site, later=later, drawn=drawn, browser=app)
		found = Inspection("page", fixes.scopeOf(site=site), nodes, document, report, title, focus)
		if not site:
			found.extra = "This page has no web address, so fixes cannot be tied to it."
		return found
	task.emit("detail", "Reading every control NVDA knows in the window.")
	nodes = _windowNodes(task, window)
	later = drawn = None
	if deep:
		drawn = _drawn(plugin, onMain(plugin.clawScreen.box, "window"))
		_wait(task, CHANGE_WAIT_SECONDS)
		later = _windowNodes(task, window)
	report = audit.auditWindow(nodes, title=title, app=app, later=later, drawn=drawn)
	return Inspection("window", fixes.scopeOf(app=app), nodes, window, report, title, focus)


def _samePlace(inspection):
	"""Whether the user is still in the page or window an inspection was made of. Main thread."""
	_focus, window, document, _app, _title = _situation()
	if inspection.kind == "page":
		return document is inspection.where and hostOf(fixruntime.pageAddress(document)) == inspection.scope.get("site", "")
	return bool(_safe(lambda: window == inspection.where, False))


def _wait(task, seconds):
	deadline = time.monotonic() + seconds
	while time.monotonic() < deadline:
		task.check()
		time.sleep(0.1)


def usedKeys(plugin):
	"""Every key NVDA, its add-ons and VisionClaw's app helpers already use where the user is, in the spelling
	fixes.normKey gives. Main thread."""
	used = set()
	focus = api.getFocusObject()
	mappings = inputCore.manager.getAllGestureMappings(obj=focus, ancestors=api.getFocusAncestors())
	for scripts in mappings.values():
		for info in scripts.values():
			for gesture in info.gestures:
				if gesture.startswith("kb") and ":" in gesture:
					used.add(fixes.normKey(gesture.split(":", 1)[1]))
	for bindings in getattr(plugin.helpers, "_bindings", {}).values():
		for identifier in bindings:
			used.add(fixes.normKey(identifier.split(":", 1)[-1]))
	return used


def nameByLooking(plugin, task, inspection, group):
	"""A name for controls that have none, from what the vision model sees in their picture, or "".
	Where several controls share what tells them apart, two are looked at; only if both get the same name do
	they all get it. Otherwise they look different, and one name for all would be wrong."""
	members = group["nodes"]
	names = []
	for node in members[:2]:
		task.check()
		box = onMain(lambda n=node: _boxOf(_controlOf(inspection, n)))
		if box is None:
			continue
		try:
			image = plugin._grab((box[0] - 6, box[1] - 6, box[2] + 6, box[3] + 6))
			answer = plugin.runtime.describe(
				prepareImage(image, config.conf["visionClaw"]["detailSize"]),
				f"This picture shows one {group['kind']} that has no name. What does it do or show? Answer with only "
				"one to three words that would be a good name for it. If you cannot tell, answer: unknown.",
				24, cancel=task.cancel)
		except Exception:
			# No picture, for example while the screen curtain is on: this control stays without a name, and
			# the fixes that need no picture are still made. A task the user stopped is still stopped.
			task.check()
			log.debugWarning("VisionClaw: a control could not be named from its picture", exc_info=True)
			continue
		name = audit.cleanName(answer)
		task.emit("talk", f"The vision model looked at a {group['kind']} without a name and calls it: {name or 'unknown'}")
		names.append(name)
	if not names or not names[0]:
		return ""
	if len(members) > 1 and (len(names) < 2 or plainText(names[0]) != plainText(names[1])):
		return ""
	return names[0]


def install(plugin, task, inspection, new, notes=()):
	"""Add fixes to the add-on of a website or program, after the user has agreed, and turn it on.
	Returns the sentence that says what was made."""
	scope = inspection.scope
	if not (scope.get("site") or scope.get("app")):
		raise ToolError("Fixes belong to one website or one program, and this place is neither.")
	store = plugin.helpers.store
	# One add-on per website or program. Two websites whose names come out the same as a folder name
	# ("my-site.com" and "my.site.com") must not share one: the second gets a name with a mark of its own.
	for apart in (False, True):
		name = fixes.addonName(scope, apart)
		ident = microaddons.slug(name)
		oldSource = store.source(ident)
		parsed = fixes.parse(oldSource) if oldSource else None
		if parsed is None or parsed[0] == scope:
			break
	if oldSource and parsed is None:
		raise ToolError(
			f"There is already an add-on called {ident} that was not put together from fixes. Remove it first.")
	old = parsed[1] if parsed else []
	notes = list(notes)
	without = fixes.giveKeys(new, onMain(usedKeys, plugin))
	if without:
		notes.append(f"{len(without)} of the fixes got no hotkey, because none was free, and were left out.")
	try:
		cleaned = [fixes.clean(fix) for fix in new if not any(fix is left for left in without)]
		if not cleaned:
			raise ToolError("No hotkey is free for this, so nothing was made.")
		merged = fixes.merge(old, cleaned)
		source = fixes.build(scope, merged)
	except ValueError as e:
		raise ToolError(str(e))
	problems = microaddons.check(source)
	if problems:
		raise ToolError("The add-on could not be put together: " + " ".join(problems[:3]))
	where = fixes.scopeText(scope)
	facts = " ".join(fixes.describe(scope, cleaned))
	# Translators: Asked before accessibility fixes are turned on. {facts} are plain sentences about them.
	question = _(
		"VisionClaw can make these fixes for {where}, as an add-on that stays until you have it removed. {facts} "
	).format(where=where, facts=facts)
	if old:
		# Translators: Added to the question when fixes for this website or program exist already.
		question += _("They join the {count} fixes already made for it. ").format(count=len(old))
	# Translators: The end of the question asked before accessibility fixes are turned on.
	question += _("Turn them on?")
	# Translators: The choices when accessibility fixes are ready.
	if plugin.clawAsk(question, [_("Turn them on"), _("Do not make them")]) != 0:
		raise UserSaidNo()
	oldMeta = store.meta(ident) or {}
	purpose = clip(f"Accessibility fixes for {where}: " + "; ".join(fix["label"] for fix in merged), 300)
	store.save(name, source, purpose)
	try:
		onMain(plugin.helpers.loadAddon, ident)
	except Exception as e:
		log.error("VisionClaw: the fixes add-on did not start", exc_info=True)
		if oldSource:
			store.save(name, oldSource, oldMeta.get("purpose", ""))
			_safe(lambda: onMain(plugin.helpers.loadAddon, ident))
		else:
			store.remove(ident)
		raise ToolError(f"The fixes could not be turned on: {type(e).__name__}: {e}")
	made = " ".join(fixes.describeFix(fix) for fix in cleaned[:6])
	more = f" And {len(cleaned) - 6} more." if len(cleaned) > 6 else ""
	return (
		f"Made {len(cleaned)} {'fix' if len(cleaned) == 1 else 'fixes'} for {where}. {made}{more} "
		+ (" ".join(notes) + " " if notes else "")
		+ f"They are in the add-on {ident} and stay until you ask VisionClaw to remove that add-on."
	)


_ANY_ADDON = frozenset(("", "all", "any", "list", "every", "installed", "add on", "add ons", "addon", "addons", "the add on"))
_ADDON_FILLER = frozenset(("add", "on", "ons", "addon", "nvda", "for", "the", "and", "of"))
_WANTS_KEYS = re.compile(r"\b(keys?|shortcuts?|commands?|gestures?|press|how (do|can|to))\b", re.IGNORECASE)


def _addonOf(wanted, about):
	"""The installed add-on a request means, or None. The user's own words decide first: an add-on whose name
	is in them. What a model wrote as the name is only used when the words name none. Main thread."""
	addons = list(addonHandler.getAvailableAddons())
	summaries = [str(_safe(lambda a=a: a.manifest["summary"]) or a.name) for a in addons]
	said = set(plainText(f"{about} {wanted}").split())
	best = None
	for i, addon in enumerate(addons):
		for name in (summaries[i], match.label(addon.name)):
			parts = set(plainText(name).split()) - _ADDON_FILLER
			# Every telling word of its name is in the request, or its first word is: "the Clock add-on".
			first = next((word for word in plainText(name).split() if word not in _ADDON_FILLER), "")
			if parts and (parts <= said or (len(first) >= 4 and first in said)):
				if best is None or len(parts) > best[0]:
					best = (len(parts), i)
	if best is not None:
		return addons[best[1]], summaries[best[1]]
	if plainText(wanted) in _ANY_ADDON:
		return None, ""
	index = match.best(wanted, summaries, least=0.75)
	if index is None:
		index = match.best(wanted, [a.name for a in addons], least=0.75)
	return (addons[index], summaries[index]) if index is not None else (None, "")


def _docText(addon):
	path = _safe(lambda: addon.getDocFilePath())
	if not path or not os.path.isfile(path):
		return ""
	with open(path, encoding="utf-8", errors="replace") as f:
		page = f.read(400000)
	page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.DOTALL | re.IGNORECASE)
	page = re.sub(r"</(p|h[1-6]|li|tr|div)>|<br\s*/?>", "\n", page, flags=re.IGNORECASE)
	return html.unescape(re.sub(r"<[^>]+>", " ", page))


def addonText(wanted, about):
	"""What an installed add-on is and offers, in sentences that are said to the user as they are, so that a
	key is never retold wrongly. What comes first depends on what was asked: its keys, or what it does.
	Main thread."""
	addon, summary = _addonOf(wanted, about)
	if addon is None:
		if plainText(wanted) in _ANY_ADDON or re.search(r"\b(all|any|which|installed|list|every)\b", str(about).lower()):
			return nvdainfo.addons()
		raise ToolError(f"No installed add-on is called \"{wanted}\". {nvdainfo.addons()}")
	manifest = addon.manifest
	state = "disabled" if _safe(lambda: addon.isDisabled) else ("on" if _safe(lambda: addon.isRunning, True) else "installed but not running")
	first = (
		f"The add-on {summary}, version {_safe(lambda: manifest['version']) or 'unknown'}, "
		f"by {clip(str(_safe(lambda: manifest['author']) or 'an unknown author'), 80)}, is {state}.")
	does = []
	described = " ".join(str(_safe(lambda: manifest["description"]) or "").split())
	if described:
		does.append("It says about itself: " + clip(described, 350))
	for folder, what in _ADDON_PARTS:
		path = os.path.join(addon.path, folder)
		if os.path.isdir(path):
			names = sorted({n.split(".")[0] for n in os.listdir(path) if not n.startswith(("_", "."))})
			does.append(f"It has {what}" + (f": {', '.join(names[:12])}." if folder != "globalPlugins" and names else "."))
	keys = []
	if state == "on":
		commands = _addonCommands(addon)
		if commands:
			keys.append("Its commands where you are now: " + "; ".join(commands[:14]) + ".")
		else:
			keys.append("It has no commands of its own where you are now.")
	else:
		keys.append("Its commands are not available while it is not on.")
	about = " ".join(str(about or "").split())
	doc = _safe(lambda: _docText(addon)) or ""
	helpText = ["From its help: " + web.passages(doc, about or summary, chars=500, blockChars=250)] if doc.strip() else []
	wantsKeys = bool(_WANTS_KEYS.search(about))
	return "\n".join([first] + (keys + helpText if wantsKeys else does + keys + helpText))


def _addonCommands(addon):
	"""The commands an add-on adds where the user is, each with its keys. Main thread."""
	root = os.path.join(os.path.normcase(addon.path), "")
	focus = api.getFocusObject()
	mappings = inputCore.manager.getAllGestureMappings(obj=focus, ancestors=api.getFocusAncestors())
	found = []
	for scripts in mappings.values():
		for info in scripts.values():
			module = sys.modules.get(getattr(info.cls, "__module__", ""))
			path = os.path.normcase(str(getattr(module, "__file__", "") or ""))
			if not path.startswith(root):
				continue
			keys = []
			for gesture in info.gestures:
				shown = _safe(lambda g=gesture: inputCore.getDisplayTextForGestureIdentifier(g)[1])
				if shown and gesture.startswith("kb") and shown not in keys:
					keys.append(shown)
			found.append(f"{info.displayName} ({' or '.join(keys) if keys else 'no key assigned'})")
	return found


def addonSections():
	"""The help texts of the add-ons that are on, in sections, so that the models can read up on them."""
	found = []
	for addon in list(addonHandler.getRunningAddons()):
		summary = str(_safe(lambda a=addon: a.manifest["summary"]) or addon.name)
		text = _safe(lambda a=addon: _docText(a)) or ""
		blocks = [" ".join(block.split()) for block in re.split(r"\n\s*\n", text)]
		for block in [b for b in blocks if len(b) > 60][:30]:
			found.append((f"The add-on {summary}", block[:1200], "addons"))
	return found


def register(plugin, add, text):
	"""Add the tools to the registry. add and text are the helpers of nvdatools.build."""
	plugin.knowledge.addSource("addons", addonSections)

	def inspection(task):
		found = getattr(task, "access", None)
		if found is None:
			raise ToolError("Use check_access first.")
		return found

	def checkAccess(task, target, depth):
		found = getattr(task, "access", None)
		wanted = target if target in ("page", "window") else None
		# One inspection serves a whole request: "inspect this, then fix number 2" must not count twice.
		# It is made again when the user has moved to another page or window in between.
		if (found is None or (wanted and found.kind != wanted) or (depth == "deep" and not found.deep)
				or not onMain(_samePlace, found)):
			found = task.access = inspect(plugin, task, target, depth)
			found.deep = depth == "deep"
		step = task.steps[task.current] if 0 <= task.current < len(task.steps) else None
		if step is None or step.recipe in (None, "check_access"):
			# This report is told to the user. A number they say later means a problem of this report.
			plugin.accessHeard = (found.scope, {finding.number: finding.id for finding in found.report.findings}, time.monotonic())
		if target == "control":
			return onMain(controlText, found)
		return (found.report.text() + " " + found.extra).strip()

	add("check_access",
		"inspect the web page, the program's window or the focused control in depth for what stands in the way "
		"of a screen reader user, and say what an add-on can fix",
		checkAccess, {
			"target": text("what to inspect; auto is the web page if the user is in one, else the window", enum=audit.TARGETS,
				auto=targetOf),
			"depth": text("deep also watches for changes and reads the picture; quick only reads the controls",
				enum=audit.DEPTHS, auto=depthOf),
		}, looks=True, title="Inspecting for accessibility problems", tell=VERBATIM)

	def fixAccess(task, which):
		found = inspection(task)
		heard = getattr(plugin, "accessHeard", None)
		numbers = heard[1] if heard and heard[0] == found.scope and time.monotonic() - heard[2] < HEARD_SECONDS else None
		try:
			chosen = audit.choose(found.report, which, numbers)
		except ValueError as e:
			raise ToolError(str(e))
		new, notes, looked = [], [], 0
		for finding in chosen:
			new += [dict(fix) for fix in finding.fixes]
			unnamed = 0
			for group in finding.look:
				if looked >= MAX_NAMES_BY_LOOKING:
					unnamed += len(group["nodes"])
					continue
				looked += 1
				name = nameByLooking(plugin, task, found, group)
				if name:
					new.append({"kind": fixes.NAME, "rule": group["rule"], "label": name, "guess": True})
				else:
					unnamed += len(group["nodes"])
			if unnamed:
				notes.append(
					f"{unnamed} controls without a name were left as they are: they are not showing on the screen, "
					"or their pictures did not say clearly what they are.")
		if not new:
			raise ToolError(
				"Nothing could be fixed for this: " + (" ".join(notes) or "no fix is known for it.")
				+ " Move to a control and say what it should be called, or ask for a key for something by its name.")
		return install(plugin, task, found, new, notes)

	add("fix_access",
		"fix the accessibility problems that check_access found, with an add-on for this website or program that "
		"stays until the user has it removed",
		fixAccess, {
			"which": text("which problems to fix, in the user's words: all of them, or the number of one", maxLength=200,
				auto=True),
		}, changes=True, before="check_access", title="Making the accessibility fixes")

	def addFix(task, kind, item, key, name, asked):
		found = inspection(task)
		nodes = found.nodes
		name = " ".join(str(name or "").split())
		notes = []
		if kind == "move":
			try:
				rule, label = audit.groupRule(item, found.report, nodes)
			except ValueError as e:
				raise ToolError(str(e))
			return install(plugin, task, found, [{"kind": fixes.JUMP, "rule": rule, "label": label, "keys": []}], notes)
		# The user's own words decide whether the focused control is meant, whatever a model wrote as the item.
		node = None
		if _FOCUSED.search(asked or "") or _THIS.search(item):
			if kind == "name" or not audit.findByName(item, nodes):
				node = onMain(_focusedNode, found)
		if node is None:
			node = audit.findByName(item, nodes, audit.PRESSABLE if kind == "press" else None)
		if node is None:
			names = list(dict.fromkeys(labelOf(n) for n in nodes if n.get("role") in audit.INTERACTIVE and labelOf(n)))
			raise ToolError(
				f"Nothing called \"{item}\" was found here. Give the control's own name, or move to it first and call "
				"it the focused control. Controls here: " + clip(", ".join(names[:25]) or "none with a name", 500))
		shown = labelOf(node)
		if kind == "press" and shown:
			rule = audit.pressRule(node)
		else:
			rule = audit.signature(node)
			if rule is None:
				raise ToolError(
					f"Nothing fixed in the code of the {found.kind} tells this control apart from the others, so this "
					"kind of fix cannot be made for it reliably.")
		if kind == "name":
			if not name or plainText(name) == plainText(shown):
				raise ToolError("The new name is missing. Give the name the control should have in the field name.")
			count = sum(matches(rule, other) for other in nodes)
			if count > 1:
				notes.append(f"{count} controls here are the same to the page's code, so all of them get this name.")
			label = name
		elif kind == "press":
			label = name if name and len(name) <= 40 else (shown or audit.codeName(node) or " ".join(item.split()[:4]))
		else:
			# What is read or watched changes its text, so it is called by what its code calls it, not by its text now.
			label = name if name and len(name) <= 40 else (audit.codeName(node) or " ".join(item.split()[:4]))
		wanted = fixes.cleanKey(key)
		keys = []
		if wanted and kind in ("press", "read"):
			if fixes.normKey(wanted) in onMain(usedKeys, plugin):
				notes.append(f"{wanted} already does something else in NVDA here, so another key was chosen.")
			else:
				keys = [wanted]
		return install(plugin, task, found, [{"kind": _KIND_OF[kind], "rule": rule, "label": clip(label, 60), "keys": keys}], notes)

	add("add_fix",
		"make one lasting fix for this website or program: a key that presses a control, a key that reads one, "
		"keys that move between posts or other items, a name for a control, or being told when something changes",
		addFix, {
			"kind": text("the kind of fix", enum=audit.FIX_KINDS, auto=kindOf),
			"item": text("what the fix is about: the control's name as the user said it, the focused control, or for "
				"move the kind of item, in a few words", maxLength=80),
			"key": text("the hotkey the user named, or empty to have a free one chosen", maxLength=30, auto=fixes.keyIn),
			"name": text("for the kind name: the new name. Otherwise empty", maxLength=60),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="check_access", title="Making the fix")

	add("addon_info",
		"say what an add-on installed in this NVDA does, whether it is on, what its commands and keys are, and what "
		"its help says",
		lambda task, addon, about: onMain(addonText, addon, about), {
			"addon": text("the name of the add-on, or all for the list of add-ons", maxLength=60),
			"about": text("what the user wants to know about it", maxLength=200, auto=True),
		}, looks=True, title="Looking at the add-on", tell=VERBATIM)
