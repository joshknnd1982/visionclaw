# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the working part of every fixes add-on. A fixes add-on belongs to one website or one program
# and holds a list of fixes as plain data; this code carries them out: keys that move between items, press a
# control or read one, names for controls that have none, and telling the user when something changes.
# No model writes any of it. claw/fixes.py copies everything below the marker line into the add-on, after the
# add-on's SCOPE and FIXES and the matcher from claw/fixmatch.py, so a saved add-on needs nothing of VisionClaw.
# VisionClaw's own inspection imports this file too, so that it sees a page exactly as the add-on will.
# Because the text is checked like any generated add-on, it must not use ctypes, setattr or files.

from .claw.fixmatch import matches, nodeFromField, nodeFromObject, nodesFromFields, sameSite

# Only so that this file can be read on its own; an add-on brings its own.
SCOPE = {}
FIXES = []

# --- runtime ---
import time
import weakref

import api
import controlTypes
import globalPluginHandler  # noqa: F401 - the add-on's own class, written after this text, is built on it
import speech
import textInfos
import textInfos.offsets
import ui
import wx
from logHandler import log

# How much of a page is read in one go, in characters, and how many controls are looked through at most.
CHUNK = 30000
PAGE_LIMIT = 6000
WINDOW_LIMIT = 700
WINDOW_SECONDS = 1.5
WATCH_MS = 2500
SEEK_SECONDS = 30
# Looking again for a control that is being watched is done with smaller limits, since it repeats.
SEEK_PAGE_LIMIT = 2000
SEEK_WINDOW_LIMIT = 300
SEEK_WINDOW_SECONDS = 0.5
MAX_TROUBLE = 3
READ_CHARS = 600
BROWSER_WINDOWS = ("Chrome_", "Mozilla")


def isPage(document):
	"""Whether this is a web page as NVDA builds it for Chrome, Edge, Brave, Firefox and others."""
	import virtualBuffers
	return isinstance(document, virtualBuffers.VirtualBuffer)


def pageAddress(document):
	try:
		return str(document.documentConstantIdentifier or "")
	except Exception:
		return ""


def pageRange(document):
	whole = document.makeTextInfo(textInfos.POSITION_ALL)
	return whole._startOffset, whole._endOffset


def pageChunk(document, start, end):
	"""The controls in one stretch of the page."""
	info = document.makeTextInfo(textInfos.offsets.Offsets(start, end))
	return nodesFromFields(info.getTextWithFields(), start)


def pageNodes(document, start=None, end=None, backward=False, chunk=None):
	"""The controls of a page in reading order from start on, or backwards from end, each one once.
	The page is read a stretch at a time, so that a search can stop early on a very long page."""
	chunk = chunk or CHUNK
	first, last = pageRange(document)
	seen = set()
	at = (first if start is None else max(first, start)) if not backward else (last if end is None else min(last, end))
	while (at > first) if backward else (at < last):
		low, high = (max(first, at - chunk), at) if backward else (at, min(last, at + chunk))
		nodes = pageChunk(document, low, high)
		for node in (reversed(nodes) if backward else nodes):
			key = node.get("key")
			if key is not None:
				if key in seen:
					continue
				seen.add(key)
			yield node
		at = low if backward else high


def locate(document, node):
	"""Where a control really starts and ends in the page, and its whole text if the stretch cut it."""
	key = node.get("key")
	if not key:
		raise LookupError("the control has no identifier")
	probe = document.makeTextInfo(textInfos.POSITION_FIRST)
	start, end = probe._getOffsetsFromFieldIdentifier(int(key[0]), int(key[1]))
	node["start"], node["end"] = start, end
	if node.get("open"):
		inside = document.makeTextInfo(textInfos.offsets.Offsets(start, min(end, start + 400)))
		node["text"] = " ".join((inside.text or "").split())
		node["open"] = False
	return node


def findOnPage(document, rule, after=None, before=None, limit=None):
	"""The first control of the page that fits a rule: from the top, after a position, or the nearest one
	before a position. None if there is none, or none among the first so many controls."""
	looked = 0
	for node in pageNodes(document, start=after, end=before, backward=before is not None):
		looked += 1
		if looked > (limit or PAGE_LIMIT):
			break
		if node.get("hidden"):
			continue
		try:
			if node.get("open") and rule.get("names"):
				# Its text was cut off; fetch all of it before its name is compared.
				rest = dict(rule)
				del rest["names"]
				if not matches(rest, node):
					continue
				locate(document, node)
			if not matches(rule, node):
				continue
			locate(document, node)
		except Exception:
			continue
		if after is not None and node["start"] <= after:
			continue
		if before is not None and node["start"] >= before:
			continue
		return node
	return None


def pageInfo(document, node):
	return document.makeTextInfo(textInfos.offsets.Offsets(node["start"], node["end"]))


def textOnPage(document, node):
	return " ".join((pageInfo(document, node).text or "").split())[:READ_CHARS]


def goTo(document, node):
	"""Put NVDA's reading position on a control of the page and say its first line, as quick navigation does."""
	info = pageInfo(document, node)
	if getattr(document, "passThrough", False):
		import browseMode
		document.passThrough = False
		browseMode.reportPassThrough(document)
	place = info.copy()
	place.collapse()
	document._set_selection(place, reason=controlTypes.OutputReason.QUICKNAV)
	said = info.copy()
	said.collapse()
	said.move(textInfos.UNIT_LINE, 1, endPoint="end")
	if said.compareEndPoints(info, "endToEnd") > 0:
		said.setEndPoint(info, "endToEnd")
	speech.speakTextInfo(said, reason=controlTypes.OutputReason.QUICKNAV)


def activateOnPage(document, node):
	"""Press a control of the page the way Enter does in browse mode."""
	document._activatePosition(info=pageInfo(document, node))


def windowNodes(root, limit=WINDOW_LIMIT, seconds=WINDOW_SECONDS):
	"""The controls of a program's window, as NVDA knows them, from the top down. Stops at a number of
	controls and after a time, because some programs have very many or answer slowly."""
	deadline = time.monotonic() + seconds
	stack = [(root, None)]
	count = 0
	while stack and count < limit and time.monotonic() < deadline:
		obj, up = stack.pop()
		node = nodeFromObject(obj, up)
		count += 1
		yield node
		if "INVISIBLE" in node["states"]:
			continue
		try:
			children = list(obj.children)
		except Exception:
			children = []
		for child in reversed(children):
			stack.append((child, node))


def pressObject(obj):
	"""Press a control of a window: with its own action, or with one click in its middle."""
	try:
		obj.doAction()
		return
	except Exception:
		pass
	import mouseHandler
	import winUser
	place = obj.location
	old = winUser.getCursorPos()
	winUser.setCursorPos(place.left + place.width // 2, place.top + place.height // 2)
	mouseHandler.doPrimaryClick()
	wx.CallLater(150, winUser.setCursorPos, old[0], old[1])


class FixRuntime:
	"""Carries out the FIXES of this add-on, inside its SCOPE only. Outside it every key is passed on to the
	program, and nothing else is done. Nothing here may let an error reach NVDA."""

	scriptCategory = "VisionClaw fixes"

	def __init__(self):
		super().__init__()
		self._alive = True
		self._trouble = 0
		self._names = [fix for fix in FIXES if fix["kind"] == "name"]
		self._nameRoles = set()
		for fix in self._names:
			role = fix["rule"].get("role") or ()
			self._nameRoles.update((role,) if isinstance(role, str) else role)
		self._watches = [(index, fix) for index, fix in enumerate(FIXES) if fix["kind"] == "watch"]
		self._patched = []
		self._sites = {}
		self._onSite = False
		self._overlays = {}
		self._watched = {}
		self._heard = {}
		self._sought = {}
		self._timer = wx.CallLater(WATCH_MS, self._tick) if self._watches else None

	def terminate(self):
		self._alive = False
		timer, self._timer = self._timer, None
		try:
			if timer is not None:
				timer.Stop()
			for ref, base in self._patched:
				document = ref()
				# Only if this add-on's class is the outermost. If another add-on has wrapped it since, it is
				# left in place, and gives no names any more because this add-on is no longer alive.
				if document is not None and document.TextInfo.__dict__.get("_visionClawFixes") is self:
					document.TextInfo = base
		except Exception:
			pass
		self._patched = []
		super().terminate()

	def _hadTrouble(self):
		self._trouble += 1
		log.debugWarning("VisionClaw fixes: a fix had a problem", exc_info=True)
		if self._trouble == MAX_TROUBLE:
			log.error("VisionClaw fixes: too many problems; names and announcements are switched off")

	# --- Where the user is ---

	def _where(self):
		"""The page or window the fixes are for, if the user is in it; else None."""
		focus = api.getFocusObject()
		if SCOPE.get("site"):
			document = getattr(focus, "treeInterceptor", None)
			if document is None or not isPage(document) or not sameSite(SCOPE["site"], pageAddress(document)):
				return None
			return document
		try:
			app = focus.appModule.appName
		except Exception:
			return None
		return api.getForegroundObject() if app == SCOPE.get("app") else None

	# --- Keys ---

	def _do(self, index, gesture, step=0):
		"""Carry out the fix a key belongs to. step is 1 or -1 for the two keys of a fix that moves."""
		try:
			place = self._where()
		except Exception:
			place = None
		if place is None:
			gesture.send()
			return
		fix = FIXES[index]
		try:
			if SCOPE.get("site"):
				self._onPage(place, fix, step)
			else:
				self._inWindow(place, fix, step)
		except Exception:
			log.error("VisionClaw fixes: a key could not do its work", exc_info=True)
			ui.message("This fix did not work here. The page or program may have changed.")

	def _onPage(self, document, fix, step):
		rule, label = fix["rule"], fix.get("label") or "item"
		if fix["kind"] == "jump":
			caret = document.makeTextInfo(textInfos.POSITION_CARET)._startOffset
			node = findOnPage(document, rule, after=caret) if step > 0 else findOnPage(document, rule, before=caret)
			if node is None and step > 0:
				ui.message("No more {} below. If the page loads more as you go, try again in a moment.".format(label))
			elif node is None:
				ui.message("No {} above.".format(label))
			else:
				goTo(document, node)
			return
		node = findOnPage(document, rule)
		if node is None:
			ui.message("{} is not on this page right now.".format(label))
		elif fix["kind"] == "press":
			ui.message(label)
			activateOnPage(document, node)
		else:
			text = textOnPage(document, node)
			ui.message("{}: {}".format(label, text) if text else "{} is empty.".format(label))

	def _inWindow(self, root, fix, step):
		rule, label = fix["rule"], fix.get("label") or "item"
		focus = api.getFocusObject() if fix["kind"] == "jump" else None
		found, here, index = [], None, 0
		for node in windowNodes(root):
			if focus is not None and here is None and node["obj"] == focus:
				here = index
			if matches(rule, node):
				found.append((index, node))
				if focus is None:
					break
			index += 1
		if not found:
			ui.message("{} is not in this window right now.".format(label))
			return
		if fix["kind"] == "jump":
			if here is None:
				node = found[0][1] if step > 0 else found[-1][1]
			else:
				ahead = [node for at, node in found if at > here] if step > 0 else [node for at, node in found if at < here]
				if not ahead:
					ui.message("No more {} that way.".format(label))
					return
				node = ahead[0] if step > 0 else ahead[-1]
			obj = node["obj"]
			if "FOCUSABLE" in node["states"]:
				obj.setFocus()
			else:
				api.setNavigatorObject(obj)
				speech.speakObject(obj, reason=controlTypes.OutputReason.FOCUS)
			return
		node = found[0][1]
		if fix["kind"] == "press":
			ui.message(label)
			pressObject(node["obj"])
		else:
			text = " ".join(part for part in (node["name"], node.get("value") or "") if part)
			ui.message("{}: {}".format(label, text) if text else "{} is empty.".format(label))

	# --- Names for controls that have none ---

	def event_gainFocus(self, obj, nextHandler):
		try:
			if self._names and SCOPE.get("site") and self._trouble < MAX_TROUBLE:
				self._prepare(getattr(obj, "treeInterceptor", None))
		except Exception:
			self._hadTrouble()
		nextHandler()

	def _prepare(self, document):
		"""Note whether the user is on the site, and give its page the names."""
		if document is None or not isPage(document):
			self._onSite = False
			return
		if self._hasPatched(document):
			self._onSite = True
			return
		now = time.monotonic()
		known = self._sites.get(id(document))
		if known is None or now - known[0] > 3:
			if len(self._sites) > 50:
				self._sites.clear()
			known = self._sites[id(document)] = (now, sameSite(SCOPE["site"], pageAddress(document)))
		self._onSite = known[1]
		if known[1]:
			self._patch(document)

	def _hasPatched(self, document):
		"""Whether this add-on has already given this page its names. Another fixes add-on, for a site that
		this page also belongs to, may have wrapped the page's class as well, before or after this one; so
		every class in the line is looked at, not only the outermost."""
		for cls in getattr(document.TextInfo, "__mro__", ()):
			if cls.__dict__.get("_visionClawFixes") is self:
				return True
		return False

	def _patch(self, document):
		"""In browse mode NVDA reads a page from its own copy of it. This adds the names to what NVDA reads
		from that copy, for this page only; NVDA's own work is done first and left as it is."""
		base = document.TextInfo
		plugin = self

		class NamedTextInfo(base):
			_visionClawFixes = plugin

			def _normalizeControlField(self, attrs):
				attrs = super()._normalizeControlField(attrs)
				plugin._nameField(attrs)
				return attrs

		document.TextInfo = NamedTextInfo
		self._patched.append((weakref.ref(document), base))

	def _nameField(self, attrs):
		if self._trouble >= MAX_TROUBLE or not self._alive:
			return
		try:
			if attrs.get("name"):
				return
			role = getattr(attrs.get("role"), "name", "")
			if self._nameRoles and role not in self._nameRoles:
				return
			node = nodeFromField(attrs)
			for fix in self._names:
				if matches(fix["rule"], node):
					attrs["name"] = fix["label"]
					attrs["alwaysReportName"] = True
					return
		except Exception:
			self._hadTrouble()

	def _chooseOverlay(self, obj, clsList):
		"""Outside browse mode NVDA asks the control itself for its name. This gives the name there.
		NVDA only asks an add-on whose own class has a method chooseNVDAObjectOverlayClasses, not one that
		inherits it, so claw/fixes.py writes that method into the add-on's class when it has names to give,
		and it calls this one."""
		if not self._names or self._trouble >= MAX_TROUBLE:
			return
		try:
			if SCOPE.get("site"):
				if not self._onSite or not str(obj.windowClassName or "").startswith(BROWSER_WINDOWS):
					return
			elif obj.appModule.appName != SCOPE.get("app"):
				return
			if self._nameRoles and getattr(obj.role, "name", "") not in self._nameRoles:
				return
			if obj.name:
				return
			node = nodeFromObject(obj)
			for fix in self._names:
				if matches(fix["rule"], node):
					clsList.insert(0, self._overlay(fix["label"]))
					return
		except Exception:
			self._hadTrouble()

	def _overlay(self, label):
		found = self._overlays.get(label)
		if found is None:
			from NVDAObjects import NVDAObject

			class NamedControl(NVDAObject):
				def _get_name(self):
					return label

			found = self._overlays[label] = NamedControl
		return found

	# --- Telling the user when something changes ---

	def _tick(self):
		try:
			if self._alive and self._trouble < MAX_TROUBLE:
				self._watch()
		except Exception:
			self._hadTrouble()
		if self._alive and self._timer is not None:
			self._timer = wx.CallLater(WATCH_MS, self._tick)

	def _watch(self):
		place = self._where()
		if place is None:
			return
		for index, fix in self._watches:
			text = self._watchedText(place, index, fix["rule"])
			if text is None:
				continue
			old = self._heard.get(index)
			self._heard[index] = text
			if old is not None and old != text and text:
				ui.message("{}: {}".format(fix.get("label") or "Changed", text))

	def _watchedText(self, place, index, rule):
		"""The text now of the control a fix watches, or None while it cannot be found. The control is looked
		for once and then only asked for its text, which costs almost nothing; it is looked for again, but not
		more often than every few seconds, when it has gone."""
		kept = self._watched.get(index)
		if kept is not None:
			try:
				if SCOPE.get("site"):
					return textOnPage(place, locate(place, dict(kept)))
				obj = kept["obj"]
				return " ".join(part for part in (str(obj.name or ""), str(obj.value or "")) if part)
			except Exception:
				self._watched.pop(index, None)
		now = time.monotonic()
		if now - self._sought.get(index, 0) < SEEK_SECONDS:
			return None
		self._sought[index] = now
		if SCOPE.get("site"):
			node = findOnPage(place, rule, limit=SEEK_PAGE_LIMIT)
			if node is None:
				return None
			self._watched[index] = {"key": node["key"]}
			return textOnPage(place, node)
		for node in windowNodes(place, SEEK_WINDOW_LIMIT, SEEK_WINDOW_SECONDS):
			if matches(rule, node):
				self._watched[index] = node
				return " ".join(part for part in (node["name"], node.get("value") or "") if part)
		return None
