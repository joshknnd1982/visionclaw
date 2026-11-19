# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - object names, the NVDA side of claw/naming.py. An object without a name, or with a vague one, is named
# by the model that sees, the moment the user reaches it, however they move: the focus (Tab, Shift+Tab, Control+Tab,
# the arrow keys in lists and menus), browse mode (the arrow keys, quick navigation, the elements list), object
# navigation, the review cursor and the mouse. The name is saved, and NVDA says it from then on, everywhere.
#
# Where NVDA asks an object for its name (read from NVDA 2026.3.1's source on 2026-11-19):
# - Outside browse mode NVDA asks the object itself, through NVDAObject.name, for speech, braille, object navigation,
#   review, the mouse and touch. A global plugin's chooseNVDAObjectOverlayClasses is called for every object NVDA
#   makes, if the plugin's own class has that method (NVDAObjects/__init__.py); the class put first here asks the
#   object's own class for its name and gives the saved one where that is vague.
# - In browse mode NVDA reads a page from its own copy of it (virtualBuffers): every control's facts pass through
#   VirtualBufferTextInfo._normalizeControlField, also for quick navigation and the elements list
#   (VirtualBufferQuickNavItem.label reads _getControlFieldAttribs, which reads getTextWithFields). The page's
#   TextInfo class is wrapped, as fixruntime.py does for fixes, and the saved name is given there.
# - What the user reaches: NVDA asks for the name of the object it is about to report; the focus, the navigator
#   object and the mouse's object are then looked at. In browse mode speech.speakTextInfo is called for every move of
#   the caret, the review cursor, quick navigation, the focus and the mouse, with that reason; VisionClaw already
#   wraps it (__init__.py, _speakTextInfo).
# Nothing here may let an error reach NVDA: a fault ends in the log, and NVDA's own name is used.

import collections
import os
import threading
import time
import weakref

import addonHandler
import api
import config
import textInfos
import wx

from . import labels, ocr
from .claw import accessnotes, audit, naming, prompts, working
from .claw.catalog import VISION
from .claw.fixmatch import fileOf, hostOf
from .claw.llm import LLM
from .claw.task import Cancelled, Task
from .engine import prepareImage
from .vclog import log

addonHandler.initTranslation()

# After NVDA asks for a name, wait this long before looking at where the user is, so that a quick run of key presses
# names only where they stop.
CHECK_MS = 250
# Browse mode scrolls a control into view after the caret moves; wait for that before its picture is taken.
BROWSE_DELAY_MS = 150
AHEAD_DELAY_MS = 1000
AHEAD_LINES = 40
AHEAD_COUNT = 3
# Objects next to the one reached, in the same group, named before the user gets there.
SIBLINGS = 4
MAX_SIBLINGS_LOOKED = 30
# Objects waiting to be named; the one reached last goes first, and the oldest is dropped.
MAX_PENDING = 8
# An object the model could not name is not asked about again for this long.
TRY_AGAIN_SECONDS = 300
SESSION_SIZE = 4000
MIN_SIDE = 4
MAX_TROUBLE = 50


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def roleOf(obj):
	return _safe(lambda: obj.role.name, "")


def statesOf(obj):
	return [getattr(state, "name", str(state)) for state in _safe(lambda: obj.states, ()) or ()]


def facts(obj):
	"""What an object's own code says about it, as plain facts (claw/fixmatch.py nodeFromObject without its name,
	which would ask this module again)."""
	def get(name, default=""):
		try:
			value = getattr(obj, name, default)
		except Exception:
			return default
		return default if value is None else value

	web = get("IA2Attributes", None)
	if not hasattr(web, "get"):
		web = {}
	controlId = get("windowControlID", 0)
	return {
		"role": roleOf(obj), "name": "", "text": "", "tag": str(web.get("tag") or "").lower(),
		"cls": str(web.get("class") or "").split(), "ident": str(web.get("id") or ""), "src": fileOf(web.get("src")),
		"states": statesOf(obj), "controlId": controlId if isinstance(controlId, int) else 0,
		"autoId": str(get("UIAAutomationId")), "windowClass": str(get("windowClassName")),
	}


def identity(obj):
	"""What tells this object apart from the others while NVDA runs. A control of a web page is the same in browse mode
	and outside it: NVDA's copy of a page knows it by the window and its IAccessible2 unique number, as the object does."""
	uid = _safe(lambda: obj.IA2UniqueID)
	if uid is not None:
		# As virtualBuffers/gecko_ia2.py getIdentifierFromNVDAObject: the window handle and the unique number.
		return ("web", _safe(lambda: obj.windowHandle), uid)
	element = _safe(lambda: obj.UIAElement)
	if element is not None:
		runtime = _safe(lambda: tuple(element.GetRuntimeId()))
		if runtime:
			return ("uia",) + runtime
	child = _safe(lambda: obj.IAccessibleChildID, 0)
	handle = _safe(lambda: obj.windowHandle, 0)
	if isinstance(child, int) and child > 0:
		return ("acc", handle, child, roleOf(obj))
	location = _safe(lambda: tuple(obj.location))
	return ("at", handle, roleOf(obj), location) if location else None


def baseName(obj):
	"""An object's name before VisionClaw's, so that reading a related object never asks object names again."""
	if obj is None:
		return ""
	own = getattr(obj, "visionClawBaseName", None)
	return str((_safe(own, "") if own is not None else _safe(lambda: obj.name, "")) or "")


# The objects inside an object whose words are read, at most; and how long what was read holds for one object.
INSIDE_LOOKED = 6
WORDS_SECONDS = 2


def interfaceWords(obj, role):
	"""What the accessibility interfaces say of an object besides its own name, read once for each object NVDA makes:
	"label", the name of the object that labels it (NVDAObject.labeledBy: UI Automation's LabeledBy, IAccessible2's
	labelled-by relation); "inside", the names of the first objects inside it; "others", its description (a tooltip,
	aria-describedby, UI Automation's help text) and the hint written in a web page's field (placeholder); "holds",
	whether it has objects inside it; "text", the words inside it and, for a holder, its value; "given", the label to say
	from these (naming.interfaceName)."""
	cached = obj.__dict__.get("_visionClawWords")
	now = time.monotonic()
	if cached is not None and now - cached["at"] < WORDS_SECONDS:
		return cached
	label = _safe(lambda: obj.labeledBy)
	labelText = baseName(label) if label is not None and label is not obj and not _safe(lambda: label == obj, False) else ""
	words, child = [], _safe(lambda: obj.firstChild)
	holds = child is not None
	for _i in range(INSIDE_LOOKED):
		if child is None:
			break
		name = baseName(child)
		if name and not naming.unlabelled(name, roleOf(child)):
			words.append(name)
		child = _safe(lambda c=child: c.next)
	inside = " ".join(" ".join(words).split())[:200]
	web = _safe(lambda: obj.IA2Attributes)
	others = [str(_safe(lambda: obj.description, "") or ""), str(web.get("placeholder") or "") if hasattr(web, "get") else ""]
	text = inside
	if role in naming.WHEN_CLICKABLE:
		value = _safe(lambda: obj.value, "")
		if isinstance(value, str) and value.strip():
			text = (value + " " + text).strip()
	found = {"label": labelText, "inside": inside, "others": others + [labelText], "holds": holds, "text": text,
		"given": naming.interfaceName(role, labelText, inside), "at": now}
	obj.__dict__["_visionClawWords"] = found
	return found


def boxOf(location):
	if not location or location[2] < MIN_SIDE or location[3] < MIN_SIDE:
		return None
	return (location[0], location[1], location[0] + location[2], location[1] + location[3])


def scopeOf(obj):
	"""Where a name is kept: the website of a web page's control, else the program."""
	document = _safe(lambda: obj.treeInterceptor)
	address = _safe(lambda: document.documentConstantIdentifier) if document is not None else None
	return naming.webScope(address) or _safe(lambda: obj.appModule.appName) or "?"


def dialogTitle():
	foreground = _safe(api.getForegroundObject)
	if foreground is not None and roleOf(foreground) == "DIALOG":
		return _safe(lambda: foreground.name) or ""
	return ""


class Namer:
	"""Names objects for one running VisionClaw. plugin gives the picture of the screen (_grabOrReport), the queue of
	work in the background (_queueBackground), the runtime of the models, the board of what VisionClaw is busy with,
	the saved names (labels) and speaking (speak)."""

	def __init__(self, plugin, speak, isOn, probably=naming.PROBABLY, onWay=None):
		self.plugin = plugin
		# Called when the model is asked for the name of the object the user is on: a short beep, so that on a slower
		# computer the user knows a name is coming.
		self._onWay = onWay
		self.store = plugin.labels
		self._speak = speak
		self._isOn = isOn
		self.probably = probably
		self.on = False
		self._lock = threading.RLock()
		self._session = collections.OrderedDict()
		self._sessionVersion = 0
		self._tried = {}
		self._looked = {}
		self._pending = collections.OrderedDict()
		self._jobQueued = False
		self._jobSerial = 0
		self._checkQueued = False
		self._recent = collections.deque(maxlen=12)
		self._patched = []
		self._scopes = {}
		self._browseGeneration = 0
		self._trouble = 0
		self._alive = True
		self._cls = self._overlayClass()
		self.refresh()

	def refresh(self):
		try:
			self.on = bool(self._isOn())
		except Exception:
			self.on = False

	def terminate(self):
		self._alive = False
		self.on = False
		for ref, base in self._patched:
			document = ref()
			try:
				if document is not None and document.TextInfo.__dict__.get("_visionClawNames") is self:
					document.TextInfo = base
			except Exception:
				pass
		self._patched = []

	def _hadTrouble(self):
		self._trouble += 1
		log.debugWarning("VisionClaw: naming an object had a problem", exc_info=True)
		if self._trouble == MAX_TROUBLE:
			log.error("VisionClaw: object names had too many problems and stop until NVDA restarts")

	@property
	def working(self):
		return self.on and self._alive and self._trouble < MAX_TROUBLE

	# --- Outside browse mode: the object itself ---

	def _overlayClass(self):
		from NVDAObjects import NVDAObject
		namer = self

		class VisionClawNamed(NVDAObject):
			"""Gives the saved name of an object that has none, or a vague one (VisionClaw's object names)."""

			def _get_name(self):
				base = super()._get_name()
				try:
					return namer.nameFor(self, base)
				except Exception:
					namer._hadTrouble()
					return base

			def visionClawBaseName(self):
				"""The name the object's own classes give, before VisionClaw's."""
				return super()._get_name()

		return VisionClawNamed

	def chooseOverlay(self, obj, clsList):
		if not self.working:
			return
		try:
			role = roleOf(obj)
			if role in naming.NAMED or role in naming.WHEN_CLICKABLE:
				clsList.insert(0, self._cls)
		except Exception:
			self._hadTrouble()

	def nameFor(self, obj, base):
		"""The name NVDA says for an object: its own label wherever it has one; else the label the interfaces give
		elsewhere (interfaceWords); else, where it is truly unlabelled, its saved name, or the model is asked. A name the
		user gave or asked the model for (naming.overrides) is said in every case."""
		if not self.working:
			return base
		role = roleOf(obj)
		states = statesOf(obj)
		if not naming.unlabelled(base, role) or role in naming.WHEN_CLICKABLE and not naming.clickable(states, role):
			return self._overridden(obj, base)
		words = interfaceWords(obj, role)
		found = self.known(obj)
		if naming.overrides(found):
			return naming.spoken(found, self.probably)
		if not naming.wanted(role, states, base, words["text"], others=words["others"], holds=words["holds"]):
			return words["given"] or base
		if found:
			return naming.spoken(found, self.probably)
		self._noticed(obj)
		return base

	def _overridden(self, obj, base):
		"""An object with a label of its own: its label, unless the user gave it a name or asked the model for one. Only
		in a program or website that has such names is anything looked up: by what this run of NVDA knows of the object,
		by what its code calls it, and, for the object the user is on, by its picture (_consider)."""
		if not self.store.overriding():
			return base
		kinds = self.store.overrideKinds(scopeOf(obj))
		if not kinds:
			return base
		found = self.known(obj) if "rule" in kinds else self._sessionEntry(identity(obj))
		if naming.overrides(found):
			return naming.spoken(found, self.probably)
		if found is None and "picture" in kinds:
			self._noticed(obj)
		return base

	def known(self, obj):
		"""The saved name of an object, from this run of NVDA or from what its code says, or None."""
		stamp = (self.store.version, self._sessionVersion)
		cached = obj.__dict__.get("_visionClawKnown")
		if cached is not None and cached[0] == stamp:
			return cached[1]
		ident = identity(obj)
		found = self._sessionEntry(ident)
		if found is None:
			rule = naming.ruleFor(facts(obj), dialogTitle())
			if rule is not None:
				found = self.store.entry(scopeOf(obj), naming.ruleKey(rule))
		obj.__dict__["_visionClawKnown"] = (stamp, found)
		return found

	def _remember(self, ident, scope, keys):
		"""This run of NVDA knows the object ident by these keys of its place, so that its name is found again at once
		however it was found the first time. The name itself is always read from the store: a name changed or
		forgotten in the names window is said as it is now."""
		if ident is None:
			return
		keys = [key for key in keys if key]
		with self._lock:
			if keys:
				self._session[ident] = (scope, keys)
				self._session.move_to_end(ident)
				while len(self._session) > SESSION_SIZE:
					self._session.popitem(last=False)
			else:
				self._session.pop(ident, None)
			self._sessionVersion += 1

	def _sessionEntry(self, ident):
		if ident is None:
			return None
		with self._lock:
			known = self._session.get(ident)
		if known is None:
			return None
		scope, keys = known
		for key in keys:
			found = self.store.entry(scope, key)
			if found:
				return found
		return None

	def _noticed(self, obj):
		self._recent.append(id(obj))
		if not self._checkQueued:
			self._checkQueued = True
			wx.CallAfter(lambda: wx.CallLater(CHECK_MS, self._check))

	def _check(self):
		"""Look at where the user is: the focus, the navigator object, and the mouse's object if NVDA just reported it."""
		self._checkQueued = False
		if not self.working or not self.plugin._dataReady():
			return
		seen = []
		mouse = _safe(api.getMouseObject)
		for obj, speak in ((api.getFocusObject(), True), (api.getNavigatorObject(), True), (mouse, True)):
			if obj is None or any(obj is other for other in seen):
				continue
			if obj is mouse and id(obj) not in self._recent:
				continue
			seen.append(obj)
			try:
				if self._consider(obj, speak) and speak:
					self._siblingsAhead(obj)
			except Exception:
				self._hadTrouble()

	def _consider(self, obj, speak, first=True):
		"""Name an object if it needs a name: at once from a saved picture, else by the model in the background.
		Returns whether it needed one."""
		if not hasattr(obj, "visionClawBaseName"):
			return False
		role = roleOf(obj)
		words = interfaceWords(obj, role)
		if not naming.wanted(role, statesOf(obj), _safe(obj.visionClawBaseName, ""), words["text"], others=words["others"],
				holds=words["holds"]):
			if speak:
				self._overrideByPicture(obj, role)
			return False
		if role in naming.PICTURES and self._insideControl(obj):
			return False
		if self.known(obj):
			return False
		ident = identity(obj)
		if ident is None or self._waiting(ident):
			return True
		box = boxOf(_safe(lambda: obj.location))
		if box is None:
			return False
		scope = scopeOf(obj)
		node = facts(obj)
		rule = naming.ruleFor(node, dialogTitle())
		window = boxOf(_safe(lambda: api.getForegroundObject().location))
		target = self._pictured(role, box, window, speak)
		if target is None:
			return False
		found = self.store.entry(scope, target["key"])
		if found:
			ruleKey = naming.ruleKey(rule)
			if ruleKey and not self.store.entry(scope, ruleKey):
				# Found by its picture: from now on by its code too, which holds when the picture changes.
				if found["by"] == naming.YOU:
					self.store.setUser(scope, ruleKey, found["name"], role)
				else:
					self.store.setGuess(scope, ruleKey, found["name"], found["sure"], role, found["by"])
			self._remember(ident, scope, [target["key"], ruleKey])
			self._said(obj, found, speak)
			return True
		before, after = self._around(obj)
		title = _safe(lambda: api.getForegroundObject().name) or ""
		place = scope[5:] if scope.startswith("site:") else scope
		target.update({
			"kind": "object", "ident": ident, "role": role, "scope": scope, "rule": rule, "code": audit.codeName(node),
			"around": working.aroundText(place, scope.startswith("site:"), title, before, after),
			"neighbours": before + after, "others": [place, title], "obj": obj,
		})
		self._want(target, first)
		return True

	def _overrideByPicture(self, obj, role):
		"""The object the user is on has a label of its own, and its program keeps names the user gave or asked for by
		their picture: look for its picture among them, once for each object and each change of the names while NVDA
		runs. Found, the name is said and kept for this run, so that NVDA says it from then on."""
		scope = scopeOf(obj)
		if role not in naming.NAMED and role not in naming.WHEN_CLICKABLE:
			return
		if "picture" not in self.store.overrideKinds(scope):
			return
		ident = identity(obj)
		if ident is None or self._sessionEntry(ident) is not None:
			return
		with self._lock:
			if self._looked.get(ident) == self.store.version:
				return
			if len(self._looked) > SESSION_SIZE:
				self._looked.clear()
			self._looked[ident] = self.store.version
		box = boxOf(_safe(lambda: obj.location))
		if box is None:
			return
		target = self._pictured(role, box, boxOf(_safe(lambda: api.getForegroundObject().location)), False)
		if target is None:
			return
		found = self.store.entry(scope, target["key"])
		if naming.overrides(found):
			self._remember(ident, scope, [target["key"]])
			self._said(obj, found, True)

	@staticmethod
	def _insideControl(obj):
		"""Whether a picture is part of a button, a link or another control named by what it holds: that control is the
		one named, where it needs a name (as naming.insideControl in browse mode)."""
		up = obj
		for _i in range(3):
			up = _safe(lambda o=up: o.parent)
			if up is None:
				return False
			if roleOf(up) in naming.BY_CONTENT:
				return True
		return False

	def _around(self, obj):
		"""The named objects just before and after one, as (kind, name), for the model that names it."""
		def walk(step):
			found, other = [], obj
			for _i in range(6):
				other = _safe(lambda o=other: getattr(o, step))
				if other is None or len(found) >= working.NEIGHBOURS:
					break
				name = _safe(lambda o=other: o.name) or ""
				if name and not naming.vague(name, roleOf(other)):
					found.append((naming.kindWord(roleOf(other)), name))
			return found
		return list(reversed(walk("previous"))), walk("next")

	def _siblingsAhead(self, obj):
		"""Name the objects next to this one in its group that need a name, in the background, so that their names are
		ready when the user gets there."""
		parent = _safe(lambda: obj.parent)
		if parent is None or (_safe(lambda: parent.childCount, 0) or 0) > MAX_SIBLINGS_LOOKED:
			return
		queued = 0
		for other in _safe(lambda: parent.children, []) or []:
			if queued >= SIBLINGS:
				break
			if other == obj:
				continue
			if self._consider(other, speak=False, first=False):
				queued += 1

	# --- The picture ---

	def _pictured(self, role, box, window, speak):
		"""The picture the model is shown and the key of the object's own picture, or None where there is no picture
		(the screen curtain is on, or the object is not on the screen)."""
		wide = naming.pictureBox(role, box, window)
		if wide[2] - wide[0] < MIN_SIDE or wide[3] - wide[1] < MIN_SIDE:
			return None
		image = self.plugin._grabOrReport(wide, quiet=True)
		if image is None:
			return None
		left, top = box[0] - wide[0], box[1] - wide[1]
		own = image.crop((max(0, left), max(0, top), min(image.width, left + box[2] - box[0]),
			min(image.height, top + box[3] - box[1])))
		if own.width < MIN_SIDE or own.height < MIN_SIDE:
			return None
		return {"image": image, "own": own, "key": labels.imageKey(own), "speak": speak}

	# --- Waiting objects, and the work in the background ---

	def _waiting(self, ident):
		with self._lock:
			if ident in self._pending:
				return True
			tried = self._tried.get(ident)
			return tried is not None and time.monotonic() - tried < TRY_AGAIN_SECONDS

	def _want(self, target, first=True, beep=True):
		with self._lock:
			ident = target["ident"]
			self._pending[ident] = target
			self._pending.move_to_end(ident, last=first)
			while len(self._pending) > MAX_PENDING:
				self._pending.popitem(last=False)
		if beep and target.get("speak") and self._onWay is not None:
			try:
				self._onWay()
			except Exception:
				log.debugWarning("VisionClaw: the beep for a name on its way failed", exc_info=True)
		self._kick()

	def _kick(self):
		with self._lock:
			if self._jobQueued or not self._pending:
				return
			self._jobSerial += 1
			self._jobQueued = True
			serial = self._jobSerial
		queued = self.plugin._queueBackground(self._job, ("names", serial), first=True)
		if not queued:
			with self._lock:
				self._jobQueued = False

	def _job(self, cancel):
		"""Name the object reached last that is still waiting. Runs in VisionClaw's background thread, which gives way
		to anything the user asks for."""
		with self._lock:
			target = None
			while self._pending:
				ident, target = self._pending.popitem(last=True)
				# A name the user asked for is looked for also while object names are off.
				if self.working or target.get("asked") and self._alive:
					break
				target = None
			if target is None:
				self._jobQueued = False
				return True
		board = getattr(self.plugin, "board", None)
		job = None
		if target.get("speak") and board is not None:
			job = board.begin(
				# Translators: What VisionClaw is doing, as a status update says it: "Still naming the object".
				_("naming the object"), self.plugin._seeing(_("The {model} is looking at the object.")), cancel=cancel)
		try:
			result = self._name(target, cancel)
		except Cancelled:
			result = None
		except Exception:
			log.error("VisionClaw: an object could not be named", exc_info=True)
			result = ("", False)
		finally:
			if board is not None:
				board.end(job, said=False)
		if result is None:
			with self._lock:
				if ident not in self._pending:
					self._pending[ident] = target
					self._pending.move_to_end(ident, last=True)
			return False  # stopped: the background thread tries again later
		name, sure = result
		asked = bool(target.get("asked"))
		if name:
			entry = {"name": name, "by": naming.MODEL, "sure": sure, "role": target["role"]}
			if asked:
				entry["asked"] = True
			self.store.setGuess(target["scope"], target["key"], name, sure, target["role"], asked=asked)
			if target.get("rule") is not None:
				self.store.setGuess(target["scope"], naming.ruleKey(target["rule"]), name, sure, target["role"], asked=asked)
			self._remember(ident, target["scope"], [target["key"], naming.ruleKey(target.get("rule"))])
			wx.CallAfter(self._named, target, entry)
		else:
			with self._lock:
				self._tried[ident] = time.monotonic()
				if len(self._tried) > SESSION_SIZE:
					self._tried.clear()
			if asked:
				# Translators: Said when the user asked the model to name an object (NVDA+Shift+Alt+B) and it gave no name.
				wx.CallAfter(self._speak, _("The model could not tell from its picture what this is."))
		with self._lock:
			self._jobQueued = False
		wx.CallAfter(self._kick)
		return True

	def _name(self, target, cancel):
		"""(name, sure) for one object, from the model that sees, the text in the object's own picture, and what its
		code calls it; ("", False) when none of them gives a name. None when stopped."""
		read = ""
		lines = ocr.recognize(target["own"]) if config.conf["visionClaw"].get("useOcr", True) else None
		if cancel.is_set():
			return None
		if lines:
			read = " ".join(ocr.linesText(lines).split())
		task = Task("name an object without a name")
		task.cancel = cancel
		llm = LLM(self.plugin.runtime, task)
		entry = _safe(lambda: self.plugin.runtime.entry(VISION))
		jpeg = prepareImage(target["image"], config.conf["visionClaw"]["detailSize"])
		role = target["role"]

		def ask(around):
			answer = llm.json(VISION, prompts.seeing(working.NAME_SYSTEM), naming.question(role, around),
				working.NAME_SCHEMA, maxTokens=24, image=jpeg)
			return audit.cleanName(answer.get("name") if isinstance(answer, dict) else answer)

		try:
			modelName = working.named(ask, entry, target["around"], target["neighbours"], target["others"])
		except Cancelled:
			return None
		except Exception:
			if cancel.is_set():
				return None
			log.debugWarning("VisionClaw: the model could not name an object", exc_info=True)
			modelName = ""
		if cancel.is_set():
			return None
		return naming.decide(modelName, read, target["code"], role)

	def _named(self, target, entry):
		"""Main thread: the name has come. Said if the user is still there; kept in the notes on the program."""
		try:
			if target.get("rule") is not None:
				# The notes on the program or website, which the models are given (as accesstools.accessNotes).
				notes = getattr(self.plugin, "_accessNotes", None)
				if notes is None:
					notes = self.plugin._accessNotes = accessnotes.AccessNotes(
						os.path.join(self.plugin.dataDir, accessnotes.FOLDER))
				scope = target["scope"]
				where = {"site": scope[5:]} if scope.startswith("site:") else {"app": scope}
				notes.keepName(where, accessnotes.keyOf(target["rule"]), naming.kindWord(target["role"]), entry["name"])
		except Exception:
			log.debugWarning("VisionClaw: a name could not be kept in the notes", exc_info=True)
		if target.get("asked"):
			# The user asked for this name: it is said wherever they are now, with what follows from names being off.
			text = naming.spoken(entry, self.probably)
			if not self.working:
				# Translators: Said after a name the user asked the model for, while object names are off.
				text += ". " + _("Object names are off, so it is said only now; NVDA+Alt+B turns them on.")
			self._speak(text)
			if target["kind"] == "field":
				document = target["document"]()
				if document is not None:
					_safe(lambda: __import__("braille").handler.handleCaretMove(document))
			else:
				_safe(lambda: __import__("braille").handler.handleUpdate(target["obj"]))
			return
		if not target.get("speak"):
			return
		if target["kind"] == "field":
			if target["generation"] == self._browseGeneration:
				self._speak(naming.spoken(entry, self.probably))
				document = target["document"]()
				if document is not None:
					_safe(lambda: __import__("braille").handler.handleCaretMove(document))
			return
		obj = target["obj"]
		if _safe(lambda: obj == api.getFocusObject() or obj == api.getNavigatorObject(), False):
			self._said(obj, entry, True)

	def _said(self, obj, entry, speak):
		if speak:
			self._speak(naming.spoken(entry, self.probably))
		_safe(lambda: __import__("braille").handler.handleUpdate(obj))

	# --- Browse mode ---

	def prepare(self, document):
		"""Give a page in browse mode its saved names, by wrapping its TextInfo class (as fixruntime.py does)."""
		if not self.working or document is None or not hasattr(document, "getNVDAObjectFromIdentifier"):
			return
		try:
			for cls in getattr(document.TextInfo, "__mro__", ()):
				if cls.__dict__.get("_visionClawNames") is self:
					return
			base = document.TextInfo
			if "_normalizeControlField" not in dir(base):
				return
			namer = self

			class NamedTextInfo(base):
				_visionClawNames = namer

				def _normalizeControlField(self, attrs):
					attrs = super()._normalizeControlField(attrs)
					try:
						namer.fieldName(self.obj, attrs)
					except Exception:
						namer._hadTrouble()
					return attrs

			document.TextInfo = NamedTextInfo
			self._patched = [(ref, old) for ref, old in self._patched if ref() is not None]
			self._patched.append((weakref.ref(document), base))
		except Exception:
			self._hadTrouble()

	def _scope(self, document):
		key = id(document)
		now = time.monotonic()
		known = self._scopes.get(key)
		if known is None or now - known[0] > 5:
			if len(self._scopes) > 100:
				self._scopes.clear()
			address = _safe(lambda: document.documentConstantIdentifier)
			scope = naming.webScope(address) or _safe(lambda: document.rootNVDAObject.appModule.appName) or "?"
			known = self._scopes[key] = (now, scope)
		return known[1]

	@staticmethod
	def fieldIdent(attrs):
		try:
			return ("web", int(attrs["controlIdentifier_docHandle"]), int(attrs["controlIdentifier_ID"]))
		except (KeyError, TypeError, ValueError):
			return None

	def fieldName(self, document, attrs):
		"""Give a control of NVDA's copy of a page its saved name, where it is truly unlabelled; and the name the user gave
		it or asked the model for, wherever it is."""
		if not self.working:
			return
		role = getattr(attrs.get("role"), "name", "")
		if role not in naming.NAMED and role not in naming.WHEN_CLICKABLE:
			return
		states = [getattr(s, "name", str(s)) for s in attrs.get("states") or ()]
		if naming.labelled(attrs.get("name"), role, naming.fieldOthers(attrs)) or (
				role in naming.WHEN_CLICKABLE and not naming.clickable(states, role)):
			if not self.store.overriding():
				return
			found = self._fieldEntry(document, attrs)
			if not naming.overrides(found):
				return
		else:
			found = self._fieldEntry(document, attrs)
		if found:
			attrs["name"] = naming.spoken(found, self.probably)
			attrs["alwaysReportName"] = True

	def _fieldEntry(self, document, attrs):
		found = self._sessionEntry(self.fieldIdent(attrs))
		if found is None:
			rule = naming.ruleFor(naming.fieldNode(attrs))
			if rule is not None:
				found = self.store.entry(self._scope(document), naming.ruleKey(rule))
		return found

	def reachedText(self, info, reason):
		"""NVDA has just spoken a stretch of a page in browse mode, for a move of the caret, the review cursor, quick
		navigation, the focus or the mouse: name the controls in it that need a name, and some a little further on."""
		if not self.working or not self.plugin._dataReady():
			return
		document = getattr(info, "obj", None)
		if document is None or not hasattr(document, "getNVDAObjectFromIdentifier"):
			return
		self.prepare(document)
		self._browseGeneration += 1
		generation = self._browseGeneration
		found = naming.candidates(info.getTextWithFields(), limit=2)
		if found:
			wx.CallLater(BROWSE_DELAY_MS, self._fields, document, found, generation, True)
		wx.CallLater(AHEAD_DELAY_MS, self._ahead, info, generation)

	def _ahead(self, info, generation):
		if generation != self._browseGeneration or not self.working:
			return
		try:
			ahead = info.copy()
			ahead.collapse(end=True)
			ahead.move(textInfos.UNIT_LINE, AHEAD_LINES, endPoint="end")
			found = naming.candidates(ahead.getTextWithFields(), limit=AHEAD_COUNT * 2)
		except Exception:
			log.debugWarning("VisionClaw: looking ahead for objects to name failed", exc_info=True)
			return
		self._fields(info.obj, found, generation, False, limit=AHEAD_COUNT)

	def _fields(self, document, found, generation, speak, limit=None):
		"""Main thread: name controls of a page found in browse mode."""
		if not self.working:
			return
		window = boxOf(_safe(lambda: api.getForegroundObject().location))
		scope = self._scope(document)
		title = _safe(lambda: document.rootNVDAObject.name) or ""
		place = scope[5:] if scope.startswith("site:") else scope
		queued = 0
		targets = []
		for field, node, before, after in found:
			if limit is not None and queued >= limit:
				break
			try:
				ident = self.fieldIdent(field)
				if ident is None or self._waiting(ident):
					continue
				if self._sessionEntry(ident) is not None:
					continue
				obj = document.getNVDAObjectFromIdentifier(ident[1], ident[2])
				box = boxOf(_safe(lambda: obj.location))
				if box is None or window is not None and not (
						box[0] >= window[0] and box[1] >= window[1] and box[2] <= window[2] and box[3] <= window[3]):
					continue
				target = self._pictured(node["role"], box, window, speak)
				if target is None:
					continue
				rule = naming.ruleFor(node)
				saved = self.store.entry(scope, target["key"])
				if saved:
					self._remember(ident, scope, [target["key"]])
					if speak and generation == self._browseGeneration:
						self._speak(naming.spoken(saved, self.probably))
					continue
				target.update({
					"kind": "field", "ident": ident, "role": node["role"], "scope": scope, "rule": rule,
					"code": audit.codeName(node), "around": working.aroundText(place, scope.startswith("site:"), title,
						before, after),
					"neighbours": list(before) + list(after), "others": [place, title], "generation": generation,
					"document": weakref.ref(document),
				})
				targets.append(target)
				queued += 1
			except Exception:
				self._hadTrouble()
		# The one reached last is named first: so that a line's controls are named in reading order, the first is put
		# in last. One beep for them all.
		for at, target in enumerate(reversed(targets) if speak else targets):
			self._want(target, first=speak, beep=at == len(targets) - 1)

	# --- What the user names ---

	def current(self):
		"""The object or page control where the user is, to be named by them: a dict with "ident", "role", "scope",
		"keys" (where its name is kept), "name" (as it is now said, without "probably") and "base"; or a sentence
		that says why there is none."""
		focus = api.getFocusObject()
		document = getattr(focus, "treeInterceptor", None)
		if document is not None and hasattr(document, "getNVDAObjectFromIdentifier") and not getattr(document, "passThrough", True):
			return self._currentField(document)
		obj = api.getNavigatorObject()
		role = roleOf(obj)
		if role not in naming.NAMED and role not in naming.WHEN_CLICKABLE:
			# Translators: Said when the object at the review position cannot be given a name. {kind} is what NVDA calls
			# it, such as "heading".
			return _("This {kind} is read from its own text, so it is not given a name.").format(
				kind=_safe(lambda: obj.role.displayString, role.lower()))
		scope = scopeOf(obj)
		keys = []
		rule = naming.ruleFor(facts(obj), dialogTitle())
		if rule is not None:
			keys.append(naming.ruleKey(rule))
		box = boxOf(_safe(lambda: obj.location))
		if box is not None:
			image = self.plugin._grabOrReport(box, quiet=True)
			if image is not None:
				keys.append(labels.imageKey(image))
		if not keys:
			# Translators: Said when an object cannot be named because nothing tells it apart and it is not on the screen.
			return _("This object cannot be named: it is not on the screen, and nothing in its program tells it apart.")
		base = _safe(obj.visionClawBaseName, "") if hasattr(obj, "visionClawBaseName") else (_safe(lambda: obj.name) or "")
		found = self.known(obj) if hasattr(obj, "visionClawBaseName") else None
		return {"ident": identity(obj), "role": role, "scope": scope, "keys": keys, "base": base,
			"name": found["name"] if found else ("" if naming.unlabelled(base, role) else base)}

	def _currentField(self, document):
		info = document.makeTextInfo(textInfos.POSITION_CARET)
		info.expand(textInfos.UNIT_CHARACTER)
		field = None
		for command in info.getTextWithFields():
			if isinstance(command, textInfos.FieldCommand) and command.command == "controlStart":
				role = getattr(command.field.get("role"), "name", "")
				if role in naming.NAMED or role in naming.WHEN_CLICKABLE:
					field = command.field
		if field is None:
			# Translators: Said when NVDA+Alt+N is pressed in browse mode where there is no control or picture.
			return _("There is no control or picture here to name. Move to one first, then press NVDA+Alt+N.")
		ident = self.fieldIdent(field)
		node = naming.fieldNode(field)
		scope = self._scope(document)
		keys = []
		rule = naming.ruleFor(node)
		if rule is not None:
			keys.append(naming.ruleKey(rule))
		obj = _safe(lambda: document.getNVDAObjectFromIdentifier(ident[1], ident[2])) if ident else None
		box = boxOf(_safe(lambda: obj.location)) if obj is not None else None
		if box is not None:
			image = self.plugin._grabOrReport(box, quiet=True)
			if image is not None:
				keys.append(labels.imageKey(image))
		if not keys:
			return _("This object cannot be named: it is not on the screen, and nothing in its program tells it apart.")
		found = self._sessionEntry(ident)
		name = node["name"]
		if found:
			name = found["name"]
		elif name.startswith(self.probably.format(name="")):
			name = name[len(self.probably.format(name="")):]
		return {"ident": ident, "role": node["role"], "scope": scope, "keys": keys, "base": node["name"],
			"name": "" if naming.unlabelled(name, node["role"]) else name}

	def giveName(self, here, name):
		"""Keep the name the user gave the object or control where they are; an empty name takes theirs away."""
		for key in here["keys"]:
			self.store.setUser(here["scope"], key, name, here["role"])
		self._remember(here["ident"], here["scope"], here["keys"])

	# --- A name the user asks the model for ---

	def askHere(self):
		"""Ask the model that sees for a name for the object or page control where the user is, because the user asked
		(NVDA+Shift+Alt+B): also where object names are off, where it has a label of its own, and where the model could
		not name it before. The name is said when it comes, and kept so that it is said there from then on, while object
		names are on. Returns None when the model has been asked, else a sentence that says why it cannot be."""
		if not self._alive or self._trouble >= MAX_TROUBLE:
			# Translators: Said when object names stopped after too many problems.
			return _("Object names had too many problems and are stopped until NVDA restarts.")
		focus = api.getFocusObject()
		document = getattr(focus, "treeInterceptor", None)
		if document is not None and hasattr(document, "getNVDAObjectFromIdentifier") and not getattr(document, "passThrough", True):
			target = self._askField(document)
		else:
			target = self._askObject(api.getNavigatorObject())
		if isinstance(target, str):
			return target
		target["asked"] = True
		with self._lock:
			self._tried.pop(target["ident"], None)
		self._want(target, first=True)
		return None

	def _askObject(self, obj):
		role = roleOf(obj)
		if obj is None or role not in naming.NAMED and role not in naming.WHEN_CLICKABLE:
			# Translators: Said when NVDA+Shift+Alt+B is pressed on something read from its own text, such as a heading.
			# {kind} is what NVDA calls it.
			return _("This {kind} is read from its own text, so it is not given a name.").format(
				kind=_safe(lambda: obj.role.displayString, role.lower() or "object"))
		box = boxOf(_safe(lambda: obj.location))
		if box is None:
			# Translators: Said when the object to be named by the model is not on the screen.
			return _("This object is not on the screen, so there is no picture to name it from.")
		window = boxOf(_safe(lambda: api.getForegroundObject().location))
		target = self._pictured(role, box, window, True)
		if target is None:
			return self._noPicture()
		ident = identity(obj) or ("asked", role, box)
		scope = scopeOf(obj)
		node = facts(obj)
		before, after = self._around(obj)
		title = _safe(lambda: api.getForegroundObject().name) or ""
		place = scope[5:] if scope.startswith("site:") else scope
		target.update({
			"kind": "object", "ident": ident, "role": role, "scope": scope, "rule": naming.ruleFor(node, dialogTitle()),
			"code": audit.codeName(node), "around": working.aroundText(place, scope.startswith("site:"), title, before, after),
			"neighbours": before + after, "others": [place, title], "obj": obj,
		})
		return target

	def _askField(self, document):
		info = document.makeTextInfo(textInfos.POSITION_CARET)
		info.expand(textInfos.UNIT_CHARACTER)
		field = None
		for command in info.getTextWithFields():
			if isinstance(command, textInfos.FieldCommand) and command.command == "controlStart":
				role = getattr(command.field.get("role"), "name", "")
				if role in naming.NAMED or role in naming.WHEN_CLICKABLE:
					field = command.field
		ident = self.fieldIdent(field) if field is not None else None
		if ident is None:
			# Translators: Said when NVDA+Shift+Alt+B is pressed in browse mode where there is no control or picture.
			return _("There is no control or picture here to name. Move to one first, then press NVDA+Shift+Alt+B.")
		node = naming.fieldNode(field)
		obj = _safe(lambda: document.getNVDAObjectFromIdentifier(ident[1], ident[2]))
		box = boxOf(_safe(lambda: obj.location)) if obj is not None else None
		if box is None:
			return _("This object is not on the screen, so there is no picture to name it from.")
		window = boxOf(_safe(lambda: api.getForegroundObject().location))
		target = self._pictured(node["role"], box, window, True)
		if target is None:
			return self._noPicture()
		scope = self._scope(document)
		title = _safe(lambda: document.rootNVDAObject.name) or ""
		place = scope[5:] if scope.startswith("site:") else scope
		target.update({
			"kind": "field", "ident": ident, "role": node["role"], "scope": scope, "rule": naming.ruleFor(node),
			"code": audit.codeName(node), "around": working.aroundText(place, scope.startswith("site:"), title),
			"neighbours": [], "others": [place, title], "generation": self._browseGeneration,
			"document": weakref.ref(document),
		})
		return target

	@staticmethod
	def _noPicture():
		# Translators: Said when the picture of the object to be named could not be taken, as when the screen curtain
		# is on.
		return _("A picture of it could not be taken. If the screen curtain is on, turn it off for a moment and try again.")
