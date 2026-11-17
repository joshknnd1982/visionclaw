# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A stand-in for a web page as NVDA keeps it in browse mode, for the tests of the inspection and the fixes.

A page is a tree of elements (El). Asked for a stretch of the page, it gives what NVDA 2026.3.1's source says
NVDA gives: texts, and a mark where each control starts and ends, every control closed at the end of the
stretch whether or not it goes on, and the controls a stretch begins inside given again at its start.
"""
import enum
import types

from visionClaw.claw import fixmatch

Role = enum.Enum("Role", "DOCUMENT BUTTON LINK HEADING ARTICLE SECTION GRAPHIC EDITABLETEXT STATICTEXT VIDEO GROUPING PANE WINDOW")
State = enum.Enum("State", "FOCUSABLE CLICKABLE INVISIBLE")


class Command:
	def __init__(self, command, field=None):
		self.command, self.field = command, field


class El:
	count = 0

	def __init__(self, role, *content, tag="", cls="", ident="", name="", states=(), level="", xml="", src=""):
		El.count += 1
		self.id = El.count
		self.role, self.content, self.name, self.states = getattr(Role, role), list(content), name, states
		self.attrs = {"tag": tag, "class": cls, "id": ident, "xml-roles": xml, "src": src}
		self.level = level
		self.start = self.end = 0
		self.activated = 0
		# Where it is on the screen, for a picture of it.
		self.hasIrrelevantLocation = False
		self.location = types.SimpleNamespace(left=10, top=10, width=24, height=24)

	def raw(self):
		"""The facts as NVDA's browser part gives them, before NVDA has worked on them."""
		field = {"_role": self.role, "_states": {getattr(State, s) for s in self.states}, "uniqueID": ("7", str(self.id))}
		field.update({f"IAccessible2::attribute_{key}": value for key, value in self.attrs.items() if value})
		if self.name:
			field["name"] = self.name
		if self.level:
			field["level"] = self.level
		return field

	def lay(self, at):
		"""Give every element its place in the page's text."""
		self.start = at
		for item in self.content:
			at = at + fixmatch._units(item) if isinstance(item, str) else item.lay(at)
		if at == self.start:
			at += 1  # NVDA gives an empty control one space, so that it can be reached
		self.end = at
		return at

	def walk(self):
		yield self
		for item in self.content:
			if not isinstance(item, str):
				yield from item.walk()

	def text(self):
		return "".join(item if isinstance(item, str) else item.text() for item in self.content) or " "


class Info:
	"""A stretch of the page, with the few things of NVDA's text ranges that the add-on uses."""

	def __init__(self, document, position):
		self.obj = document
		root = document.root
		if position == "all":
			self._startOffset, self._endOffset = root.start, root.end
		elif position == "first":
			self._startOffset = self._endOffset = root.start
		elif position == "caret":
			self._startOffset = self._endOffset = document.caret
		else:
			self._startOffset, self._endOffset = position.start, position.end

	def _normalizeControlField(self, attrs):
		attrs["role"], attrs["states"] = attrs.pop("_role"), attrs.pop("_states")
		return attrs

	def getTextWithFields(self):
		commands = []

		def render(el):
			if el.end <= self._startOffset or el.start >= self._endOffset:
				return
			commands.append(Command("controlStart", self._normalizeControlField(el.raw())))
			at = el.start
			if not el.content:
				commands.append(" ")
			for item in el.content:
				if isinstance(item, str):
					low, high = max(at, self._startOffset), min(at + len(item), self._endOffset)
					if low < high:
						commands.append(item[low - at:high - at])
					at += len(item)
				else:
					render(item)
					at = item.end
			commands.append(Command("controlEnd"))

		render(self.obj.root)
		return commands

	@property
	def text(self):
		return self.obj.root.text()[self._startOffset:self._endOffset]

	def _getOffsetsFromFieldIdentifier(self, docHandle, ident):
		for el in self.obj.root.walk():
			if el.id == ident and docHandle == 7:
				return el.start, el.end
		raise LookupError

	@property
	def NVDAObjectAtStart(self):
		best = None
		for el in self.obj.root.walk():
			if el.start <= self._startOffset < el.end:
				best = el
		return best

	def copy(self):
		other = Info(self.obj, "first")
		other._startOffset, other._endOffset = self._startOffset, self._endOffset
		return other

	def collapse(self):
		self._endOffset = self._startOffset

	def move(self, unit, count, endPoint=None):
		text = self.obj.root.text()
		end = text.find("\n", self._endOffset)
		self._endOffset = len(text) if end < 0 else end
		return 1

	def compareEndPoints(self, other, which):
		return self._endOffset - other._endOffset

	def setEndPoint(self, other, which):
		self._endOffset = other._endOffset


def documentClass(base):
	"""The stand-in page as a class that NVDA's stand-in for a web page class is the base of."""

	class Document(base):
		TextInfo = Info
		passThrough = False
		isReady = True

		def __init__(self, root, address, title=""):
			self.root, self.documentConstantIdentifier, self.caret = root, address, 0
			self.rootNVDAObject = types.SimpleNamespace(
				name=title, hasIrrelevantLocation=False, location=types.SimpleNamespace(left=0, top=0, width=800, height=600))
			root.lay(0)

		def getNVDAObjectFromIdentifier(self, docHandle, ident):
			return next((el for el in self.root.walk() if el.id == ident), None)

		def getIdentifierFromNVDAObject(self, obj):
			return (7, obj.id)

		def makeTextInfo(self, position):
			return self.TextInfo(self, position)

		def _set_selection(self, info, reason=None):
			self.caret = info._startOffset

		def _activatePosition(self, info=None):
			info.NVDAObjectAtStart.activated += 1

	return Document


def post(n):
	return El("ARTICLE", El("HEADING", f"Post {n} by someone\n", level="2"), f"The words of post number {n}.\n",
		El("BUTTON", cls="x1a2b3c4 x9zzz9"), El("BUTTON", cls="btn icon-share"), El("BUTTON", "Like", cls="x1a2b3c4"),
		El("ARTICLE", f"A comment under post {n}.\n", xml="article"), xml="article")


def feedPage():
	return El("DOCUMENT",
		El("LINK", "Home\n"), El("BUTTON", cls="btn btn-close"), El("BUTTON", ident="search-button"),
		El("SECTION", "Open the menu\n", states=("CLICKABLE",)), El("SECTION", "Show more\n", states=("CLICKABLE",)),
		El("SECTION", El("LINK", "Inside a clickable block\n"), states=("CLICKABLE",)),
		*[post(n) for n in range(1, 6)],
		El("SECTION", "0:41 / 3:05", ident="player-time"), El("VIDEO", tag="video"),
		El("BUTTON", "Pause (k)", cls="ytp-play-button"), El("BUTTON", "Mute", cls="ytp-mute-button"),
		El("SECTION", "3 new messages", cls="inbox-count"),
	)
