# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the web, through the user's own browser and NVDA's browse mode. NVDA already knows a page as
# links, headings, buttons and form fields; these functions read that, so nothing has to be guessed from a
# picture. Every function here must be called on NVDA's main thread.

import os

import api
import textInfos

from .claw import match

# NVDA's names for kinds of page element, and what to call each in a list.
KINDS = (
	("link", "link"), ("button", "button"), ("edit", "edit field"), ("comboBox", "combo box"),
	("checkBox", "checkbox"), ("radioButton", "radio button"), ("heading", "heading"),
)
FIELD_KINDS = ("edit field", "combo box")
MAX_ITEMS = 500
LABEL_CHARS = 70


class WebItems:
	"""The links, buttons and fields of a page, in the same shape as the overlay's result for a window."""

	web = True

	def __init__(self, items, title):
		self.items = items
		self.title = title


def page():
	"""The web page or other browse mode document the user is in, or None."""
	try:
		import browseMode
		document = api.getFocusObject().treeInterceptor
	except Exception:
		return None
	if isinstance(document, browseMode.BrowseModeDocumentTreeInterceptor) and getattr(document, "isReady", True):
		return document
	return None


def title(document):
	try:
		return (document.rootNVDAObject.name or "").strip()
	except Exception:
		return ""


def address(document):
	try:
		return str(document.documentConstantIdentifier or "")
	except Exception:
		return ""


def _label(node):
	return " ".join(str(getattr(node, "label", "") or "").split())[:LABEL_CHARS]


def headings():
	"""The page's headings in page order, as (level, label, node), or None if not in a page.
	The level is 0 where NVDA does not say it."""
	document = page()
	if document is None:
		return None
	# NVDA gives the headings of each level separately; their order on the page comes from asking for all.
	levels = {}
	for level in range(1, 7):
		try:
			for node in document._iterNodesByType(f"heading{level}"):
				levels.setdefault(_label(node), []).append(level)
		except Exception:
			continue
	found = []
	try:
		nodes = list(document._iterNodesByType("heading"))
	except Exception:
		nodes = []
	for node in nodes[:MAX_ITEMS]:
		label = _label(node)
		if label:
			known = levels.get(label)
			found.append((known.pop(0) if known else 0, label, node))
	return found


def moveTo(item):
	"""Put NVDA's reading position on an item of the page, and have NVDA say it, as quick navigation does."""
	node = item["web"]
	node.moveTo()
	try:
		node.report()
	except Exception:
		pass  # the position has moved; only the announcement is missing


def pageItems():
	"""The links, buttons and form fields of the page the user is in, in page order, or None if not in a page."""
	document = page()
	if document is None:
		return None
	items = []
	for nodeType, kind in KINDS:
		try:
			for node in document._iterNodesByType(nodeType):
				label = " ".join(str(node.label or "").split())[:LABEL_CHARS]
				if label:
					items.append({"text": f"{label} {kind}", "plain": label, "kind": kind, "web": node})
				if len(items) >= MAX_ITEMS:
					break
		except Exception:
			continue  # this kind of element is not known to this kind of document
	return WebItems(items, title(document))


def pageText():
	"""(title, text) of the page the user is in, from its main heading on where it has one, or None."""
	document = page()
	if document is None:
		return None
	whole = document.makeTextInfo(textInfos.POSITION_ALL)
	text = whole.text or ""
	# Most pages begin with menus and banners; the first main heading is where the content starts.
	try:
		heading = next(iter(document._iterNodesByType("heading1")), None)
		if heading is not None:
			rest = heading.textInfo.copy()
			rest.setEndPoint(whole, "endToEnd")
			if len(rest.text or "") > 200:
				text = rest.text
	except Exception:
		pass
	return title(document), text


def activate(item):
	"""Follow a link, press a button, or go into a field, the way Enter does in browse mode."""
	item["web"].activate()


def fieldIndex(reference, items):
	"""Which form field a model means, by number in the list or by name, among the fields only."""
	fields = [i for i, item in enumerate(items) if item.get("kind") in FIELD_KINDS]
	index = match.itemIndex(reference, [items[i]["plain"] for i in range(len(items))])
	if index is not None and index in fields:
		return index
	found = match.best(reference, [items[i]["plain"] for i in fields])
	if found is not None:
		return fields[found]
	# "the search box" on a page with one field means that field.
	return fields[0] if len(fields) == 1 else None


def openAddress(url):
	"""Open a web address in the user's default browser. The address must already be checked."""
	if not url.lower().startswith(("http://", "https://")) or any(c in url for c in " \"'<>"):
		raise ValueError("Not a web address.")
	os.startfile(url)
