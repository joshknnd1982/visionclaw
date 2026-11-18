# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - two tools for the web page the user is in, both read from what NVDA itself keeps of the page in
# browse mode, so nothing is guessed from a picture and nothing leaves the computer:
#   explore_page   says how the page is laid out and how to move on it: its landmarks, where the main part
#                  begins, its headings, the links of its navigation, its form fields, and NVDA's own keys that
#                  fit this page (claw/pageview.py).
#   form_trouble   says what may be stopping a form: fields marked as not valid, fields that must be filled in
#                  and are empty, and the page's error messages, each with its field; then puts NVDA's reading
#                  position on the first of them and says so. Where the page tells NVDA nothing, the text in the
#                  page's picture is read for lines that say what is wrong.
# Neither changes anything on the page. Every function that touches NVDA runs on NVDA's main thread.

import addonHandler
import api
import config
import controlTypes

from . import fixruntime, ocr
from .claw import audit, fixmatch, pageview
from .claw.tools import VERBATIM, ToolError
from .vclog import log

addonHandler.initTranslation()

# A page is read a stretch at a time, so that NVDA stays responsive and the request can be stopped.
PAGE_CHUNK = 30000
MAX_PAGE_NODES = 6000
NOT_A_PAGE = (
	"The user is not in a web page. This works in a web page in a browser; open one first. For another window, use "
	"check_access, look or read_text.")


def _where():
	"""The web page the user is in, with its title and address, or None. Main thread."""
	try:
		document = api.getFocusObject().treeInterceptor
	except Exception:
		return None
	try:
		if document is None or not fixruntime.isPage(document) or not getattr(document, "isReady", True):
			return None
	except Exception:
		return None
	try:
		title = " ".join(str(document.rootNVDAObject.name or "").split())
	except Exception:
		title = ""
	return document, title, fixruntime.pageAddress(document)


def pageNodes(task, document, onMain):
	"""Every control of the page as plain data, read a stretch at a time."""
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


def _moveTo(document, node):
	"""Put NVDA's reading position on a control of the page, without speaking: the answer names it. Main thread."""
	fixruntime.locate(document, node)
	info = fixruntime.pageInfo(document, node)
	if getattr(document, "passThrough", False):
		import browseMode
		document.passThrough = False
		browseMode.reportPassThrough(document)
	place = info.copy()
	place.collapse()
	document._set_selection(place, reason=controlTypes.OutputReason.QUICKNAV)


def _drawnLines(plugin, document, onMain):
	"""The lines of text in a picture of the page, or [] where no picture can be read."""
	if not config.conf["visionClaw"]["useOcr"]:
		return []

	def box():
		root = document.rootNVDAObject
		if getattr(root, "hasIrrelevantLocation", False):
			return None
		place = root.location
		if not place or place.width < 8 or place.height < 8:
			return None
		return (place.left, place.top, place.left + place.width, place.top + place.height)

	try:
		area = onMain(box)
		if area is None:
			return []
		return [line for line in ocr.rowsText(ocr.recognize(plugin._grab(area))).splitlines() if line.strip()]
	except Exception:
		log.debugWarning("VisionClaw: the picture of the page could not be read for the form's errors", exc_info=True)
		return []


def register(add, plugin, text, onMain):
	"""Add the tools. add and text are nvdatools' own; onMain runs a function on NVDA's main thread."""

	def page(task):
		found = onMain(_where)
		if found is None:
			raise ToolError(NOT_A_PAGE)
		document, title, address = found
		return document, title, address, pageNodes(task, document, onMain)

	def explorePage(task):
		_document, title, address, nodes = page(task)
		return pageview.explore(nodes, title=title, site=fixmatch.hostOf(address))

	add("explore_page",
		"say how the web page the user is in is laid out and how to move on it: landmarks, where the main part "
		"begins, headings, the navigation's links, form fields, and the NVDA keys that fit this page",
		explorePage, looks=True,
		# Translators: Progress message while VisionClaw reads how a web page is laid out.
		title=_("Exploring the page"), tell=VERBATIM)

	def formTrouble(task):
		document, _title, _address, nodes = page(task)
		found = pageview.trouble(nodes)
		moved, drawn = False, []
		if found.first is not None:
			try:
				onMain(_moveTo, document, found.first)
				moved = True
			except Exception:
				# The answer still says what is wrong; only the reading position stays where it was.
				log.error("VisionClaw: the reading position could not be put on the field in trouble", exc_info=True)
		elif not found.notes:
			task.check()
			drawn = pageview.errorLines(_drawnLines(plugin, document, onMain))
		return pageview.troubleText(found, moved=moved, drawn=drawn)

	add("form_trouble",
		"find out why a form on the web page will not send or submit: fields marked as not valid, required fields "
		"that are empty, and the page's error messages; then move NVDA's reading position to the first of them",
		formTrouble, looks=True,
		# Translators: Progress message while VisionClaw looks for what is stopping a form on a web page.
		title=_("Looking for what stops the form"), tell=VERBATIM)
