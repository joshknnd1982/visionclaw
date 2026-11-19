# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the two tools for a document: format_document ("format this document in APA style", "double-space
# all paragraphs", "a half-inch hanging indent for the References") and check_layout ("does my resume fit on one
# page", "do any text boxes overlap"). What the words ask, what a style asks and every sentence the user hears
# are in claw/docformat.py; this file does the work in Microsoft Word, through Word's own interface for programs,
# the one NVDA itself uses. No model is asked, no picture is taken and no key is pressed: the document's own
# numbers are read and set.
#
# How Word is reached was read from NVDA's source on 2026-11-19 (branch release-2026.3,
# source/NVDAObjects/window/winword.py and source/NVDAObjects/UIA/wordDocument.py): the document that has the
# focus is a WordDocument, which gives WinwordDocumentObject and WinwordApplicationObject; NVDA gets them with
# oleacc.AccessibleObjectFromWindow(the document's window, winUser.OBJID_NATIVEOM, IDispatch) wrapped in
# comtypes.client.dynamic.Dispatch, whose .document and .application they are; the window is the one of class
# "_WwG" in Word's thread (NVDAHelper.localLib.findWindowWithClassInThread). The class NVDA uses when it reads
# Word through UI Automation inherits the same getters, so both ways of reading Word give them. Read it again
# before changing this; do not write from memory.
#
# Every member of Word's interface used here, and every number that stands for a choice, was read on 2026-11-19
# from Microsoft's own reference for Word (learn.microsoft.com/office/vba/api/, the pages word.<name>):
#   wdlinespacing (single 0, one and a half 1, double 2), wdparagraphalignment (left 0, centre 1, right 2,
#   justify 3), wdstatistic (lines 1, pages 2), wdinformation (page of the end 3, horizontal place on the page 5,
#   vertical place 6, line number 10, inside a table 12), wdoutlinelevel (body text 10), wdprotectiontype (none
#   -1), wdlisttype (no list 0), wdconstants (undefined 9999999), wdrelativehorizontalposition (margin 0, page 1,
#   column 2, character 3), wdrelativeverticalposition (margin 0, page 1, paragraph 2, line 3), wdshapeposition
#   (top -999999, left -999998, bottom -999997, right -999996, centre -999995), office.msoshapetype (linked
#   picture 11, picture 13, text box 17);
#   font.name, font.size (points), paragraphformat.linespacingrule, .spaceafter, .firstlineindent ("use a
#   negative value to set a hanging indent"), .leftindent, paragraph.outlinelevel, paragraph.firstlineindent,
#   pagesetup.topmargin and .pagewidth (points), application.inchestopoints (1 inch is 72 points),
#   application.fontnames, application.undorecord with undorecord.startcustomrecord and .endcustomrecord (one
#   entry in Word's undo list for everything between them; Microsoft's advice is to end every record),
#   document.range, document.computestatistics, document.readonly, document.protectiontype, document.shapes (the
#   floating things of the main text, not of headers and footers), shape.left, shape.top, shape.anchor,
#   cell.width, cell.rowindex, range.cells, listformat.listtype.
# Word is not installed where this was written: it was tried against tests/wordstandin.py, which was written
# from the same pages. Nothing here has run in Word.

import re

import addonHandler
import api

from .claw import docformat
from .claw.tools import PASSED_ON, PASSED_ON_KINDS, VERBATIM, ToolError

addonHandler.initTranslation()

WORD, DOCS, OTHER = "word", "docs", "other"
# Word's numbers for its choices, as Microsoft's pages give them (see the top of this file).
LINE_SPACING = {docformat.SINGLE: 0, docformat.ONE_AND_HALF: 1, docformat.DOUBLE: 2}
ALIGNMENT = {docformat.LEFT: 0, docformat.CENTRE: 1, docformat.RIGHT: 2, docformat.JUSTIFY: 3}
ALIGN_LEFT, ALIGN_CENTRE, ALIGN_JUSTIFY = 0, 1, 3
STATISTIC_PAGES = 2
INFO_PAGE, INFO_ACROSS, INFO_DOWN, INFO_LINE, INFO_IN_TABLE = 3, 5, 6, 10, 12
BODY_TEXT = 10
NO_PROTECTION = -1
NO_LIST = 0
UNDEFINED = 9999999
ACROSS_MARGIN, ACROSS_PAGE, ACROSS_COLUMN, ACROSS_CHARACTER = 0, 1, 2, 3
DOWN_MARGIN, DOWN_PAGE, DOWN_PARAGRAPH, DOWN_LINE = 0, 1, 2, 3
SHAPE_TOP, SHAPE_LEFT, SHAPE_BOTTOM, SHAPE_RIGHT, SHAPE_CENTRE = -999999, -999998, -999997, -999996, -999995
# Anything at or below this is one of Word's words for a place, not a number of points.
SHAPE_WORDS = -999990
LINKED_PICTURE, PICTURE, TEXT_BOX = 11, 13, 17
POINTS_PER_INCH = 72.0
# The name of the one entry in Word's undo list.
UNDO_NAME = "VisionClaw formatting"
# How many paragraphs are read or changed in one visit to NVDA's main thread, so that NVDA never stops answering;
# and how many of each thing are looked at before VisionClaw says the document is too large for it.
CHUNK = 30
MAX_PARAGRAPHS, MAX_SHAPES, MAX_TABLES, MAX_CELLS = 3000, 60, 30, 400
# A paragraph of body text is a sentence: it is long, or ends as a sentence does. A short line that does not is a
# title, a name, a date or a heading, and is left alone.
BODY_CHARS = 60
# What may follow the full stop of a sentence: a closing quotation mark, straight or curled, or a bracket.
_CLOSERS = "\"')]" + chr(0x201d) + chr(0x2019)
_SENTENCE_END = re.compile("[.?!][" + re.escape(_CLOSERS) + "]*$")
_DOCS_TITLE = re.compile(r"\bgoogle docs\b", re.IGNORECASE)
_WHOLE = (docformat.FONT, docformat.SIZE, docformat.SPACING, docformat.SPACE_AROUND, docformat.MARGINS, docformat.ALIGN)


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def _direct(fn, *args):
	return fn(*args)


def _arg(obj, name, *args):
	"""A member of Word's that takes something in brackets, such as Information(3). Through the interface NVDA
	uses, some of these answer to a call and some only to square brackets, so both are tried."""
	member = getattr(obj, name)
	try:
		return member(*args)
	except Exception as fault:
		try:
			return member[args[0] if len(args) == 1 else args]
		except Exception:
			raise fault


def _points(inchesValue):
	return float(inchesValue) * POINTS_PER_INCH


# --- Reaching Word ---

def _windowObject(fg):
	"""Word's own object for the document window, got the way NVDA gets it. None when it cannot be reached."""
	try:
		import comtypes.automation
		import comtypes.client
		import NVDAHelper
		import oleacc
		import winUser
		handle = NVDAHelper.localLib.findWindowWithClassInThread(fg.windowThreadID, "_WwG", True)
		if not handle:
			return None
		found = oleacc.AccessibleObjectFromWindow(handle, winUser.OBJID_NATIVEOM, interface=comtypes.automation.IDispatch)
		return comtypes.client.dynamic.Dispatch(found)
	except Exception:
		return None


def wordObjects():
	"""(Word's document, Word's application) for the document in front, or (None, None). Main thread."""
	focus = api.getFocusObject()
	document = _safe(lambda: focus.WinwordDocumentObject)
	application = _safe(lambda: focus.WinwordApplicationObject) if document is not None else None
	if document is None or application is None:
		window = _windowObject(api.getForegroundObject())
		document = _safe(lambda: window.document) if window is not None else None
		application = _safe(lambda: window.application) if window is not None else None
	if document is None or application is None:
		return None, None
	return document, application


def _address():
	"""The address of the web page in front, or "". Main thread."""
	try:
		from . import webtools
		return webtools.address(webtools.page()) or ""
	except Exception:
		return ""


def front(screen):
	"""What is in front: (WORD, DOCS or OTHER; the document's name or the window's title; Word's document;
	Word's application). Main thread."""
	app, title, _fg, _focus = screen.where()
	if (app or "").lower() == "winword":
		document, application = wordObjects()
		name = _safe(lambda: str(document.Name), "") if document is not None else ""
		return WORD, name or title or "", document, application
	if _DOCS_TITLE.search(title or "") or "docs.google.com/document" in _address():
		return DOCS, title or "", None, None
	return OTHER, title or "", None, None


# --- What a document is like before anything is changed ---

def fontNames(application):
	"""The names of the fonts Word has on this computer, or [] when Word does not say."""
	def read():
		names = application.FontNames
		return [str(names.Item(index)) for index in range(1, int(names.Count) + 1)]
	return _safe(read, [])


def state(document):
	"""Why the document cannot be changed, as a sentence, or None when it can."""
	if _safe(lambda: int(document.ProtectionType), NO_PROTECTION) != NO_PROTECTION:
		return docformat.PROTECTED
	if _safe(lambda: bool(document.ReadOnly), False):
		return docformat.READ_ONLY
	return None


def target(document, application, selection):
	"""The text that is to be formatted: the whole of the document's main text, or what is selected."""
	return application.Selection.Range if selection else document.Content


def hasSelection(application):
	found = application.Selection.Range
	return int(found.End) > int(found.Start)


def nowOf(document, application, selection):
	"""The font and size of the text as it is: {"font", "size"}; None for either where the text has several."""
	found = target(document, application, selection)
	name = _safe(lambda: str(found.Font.Name), "") or None
	size = _safe(lambda: float(found.Font.Size))
	if size is None or size >= UNDEFINED - 1 or size <= 0:
		size = None
	elif size == int(size):
		size = int(size)
	return {"font": name, "size": size}


# --- Changing the document ---

def _startUndo(application):
	"""Begin the one entry in Word's undo list. Returns Word's object for it, or None where Word has none."""
	try:
		record = application.UndoRecord
		record.StartCustomRecord(UNDO_NAME)
		return record
	except Exception:
		return None


def _endUndo(record):
	if record is not None:
		_safe(record.EndCustomRecord)


def _setWhole(document, application, where, change):
	"""One change that is the same for all of the text. Returns why it was not done, or None."""
	what, value = change["what"], change["value"]
	if what == docformat.FONT:
		known = fontNames(application)
		if known and value.lower() not in (name.lower() for name in known):
			return docformat.NO_SUCH_FONT
		where.Font.Name = next((name for name in known if name.lower() == value.lower()), value)
	elif what == docformat.SIZE:
		where.Font.Size = float(value)
	elif what == docformat.SPACING:
		where.ParagraphFormat.LineSpacingRule = LINE_SPACING[value]
	elif what == docformat.SPACE_AROUND:
		where.ParagraphFormat.SpaceBefore = 0
		where.ParagraphFormat.SpaceAfter = 0
	elif what == docformat.MARGINS:
		setup = document.PageSetup
		setup.TopMargin = setup.BottomMargin = setup.LeftMargin = setup.RightMargin = _points(value)
	elif what == docformat.ALIGN:
		where.ParagraphFormat.Alignment = ALIGNMENT[value]
	return None


def _scan(document, first, count, deep):
	"""What is needed to know of some paragraphs, the first numbered 1: their text, outline level, alignment and
	where they begin and end; with deep also whether each is in a table or a list."""
	paragraphs = document.Paragraphs
	found = []
	for index in range(first, first + count):
		paragraph = paragraphs.Item(index)
		where = paragraph.Range
		facts = {
			"text": str(where.Text or "").strip(), "level": _safe(lambda: int(paragraph.OutlineLevel), BODY_TEXT),
			"align": _safe(lambda: int(paragraph.Alignment), ALIGN_LEFT), "start": int(where.Start), "end": int(where.End)}
		if deep:
			facts["table"] = bool(_safe(lambda: _arg(where, "Information", INFO_IN_TABLE), False))
			facts["list"] = _safe(lambda: int(where.ListFormat.ListType), NO_LIST) != NO_LIST
		found.append(facts)
	return found


def _paragraphs(document, deep, run, check):
	"""Every paragraph's facts, read a few at a time, or None when there are too many."""
	total = run(lambda: int(document.Paragraphs.Count))
	if total > MAX_PARAGRAPHS:
		return None
	found = []
	for first in range(1, total + 1, CHUNK):
		check()
		found.extend(run(_scan, document, first, min(CHUNK, total - first + 1), deep))
	return found


def _plain(text):
	return re.sub(r"[^a-z ]", "", text.lower()).strip()


def sectionOf(paragraphs, headings):
	"""Where a list of sources is: (the index of its heading, the index of its last paragraph), counted from 0, or
	None. The heading is the last paragraph that says only one of the heading words; a line of a table of contents
	says more. The list ends at the document's end, or before the next heading of the same kind."""
	wanted = {_plain(words) for words in headings}
	at = next((index for index in range(len(paragraphs) - 1, -1, -1) if _plain(paragraphs[index]["text"]) in wanted), None)
	if at is None:
		return None
	heading = paragraphs[at]
	last = len(paragraphs) - 1
	for index in range(at + 1, len(paragraphs)):
		other = paragraphs[index]
		if not other["text"]:
			continue
		same = (other["level"] == heading["level"] if heading["level"] != BODY_TEXT
			else heading["align"] == ALIGN_CENTRE and other["align"] == ALIGN_CENTRE and other["level"] == BODY_TEXT
				and len(other["text"]) < BODY_CHARS)
		if same:
			last = index - 1
			break
	return at, last


def isBody(facts):
	"""Whether a paragraph is plain body text, which a first-line indent is for: no heading, not centred or at the
	right, not in a table or a list, and a sentence rather than a short line such as a title, a name or a date."""
	text = facts["text"]
	if not text or facts["level"] != BODY_TEXT or facts["align"] not in (ALIGN_LEFT, ALIGN_JUSTIFY):
		return False
	if facts.get("table") or facts.get("list"):
		return False
	return len(text) >= BODY_CHARS or bool(_SENTENCE_END.search(text))


def _indent(document, numbers, points):
	paragraphs = document.Paragraphs
	for number in numbers:
		paragraphs.Item(number).FirstLineIndent = points


def _span(document, start, end):
	"""The text between two places in the document, as Word's own object for it."""
	return document.Range(start, end)


def _firstLine(where, points):
	where.ParagraphFormat.FirstLineIndent = points


def _hang(where, points, noGap):
	"""A hanging indent: every line but the first begins further in. Word wants the whole paragraph moved in and
	its first line moved back out by the same length."""
	form = where.ParagraphFormat
	form.LeftIndent = points
	form.FirstLineIndent = -points
	if noGap:
		form.SpaceBefore = 0
		form.SpaceAfter = 0


def _spaceLeft(where):
	form = where.ParagraphFormat
	return any(abs(float(value)) > 0.01 for value in (form.SpaceBefore, form.SpaceAfter))


def applyTo(document, application, asked, planned, run=_direct, check=lambda: None):
	"""Make the planned changes (docformat.plan) to a Word document. Returns (what happened with each change, as
	docformat.resultText wants it; {"undo": whether it is one entry in Word's undo list, "spaceLeft": whether
	paragraphs still have extra space around them after their line spacing was set}).
	run(fn, *args) runs something where Word may be talked to (NVDA's main thread); check() raises when the user
	stopped the request. One change that fails does not stop the others, and is said."""
	selection = asked.get("scope") == docformat.SELECTION
	results, scanned = [], {}
	record = run(_startUndo, application)
	try:
		where = run(target, document, application, selection)

		def paragraphs():
			if "all" not in scanned:
				deep = any(change["what"] == docformat.FIRST_LINE for change in planned["changes"])
				scanned["all"] = _paragraphs(document, deep, run, check)
			return scanned["all"]

		for change in planned["changes"]:
			check()
			what, result = change["what"], {"change": change, "ok": True}
			try:
				if what in _WHOLE:
					why = run(_setWhole, document, application, where, change)
					if why:
						result.update(ok=False, why=why)
				elif selection:
					points = _points(change["value"])
					if what == docformat.FIRST_LINE:
						run(_firstLine, where, points)
					else:
						run(_hang, where, points, False)
				elif what == docformat.FIRST_LINE:
					found = paragraphs()
					if found is None:
						result.update(ok=False, why=docformat.TOO_LONG_WHY)
					else:
						sources = sectionOf(found, docformat.HEADINGS)
						inSources = range(sources[0], sources[1] + 1) if sources else ()
						numbers = [index + 1 for index, facts in enumerate(found) if index not in inSources and isBody(facts)]
						skipped = sum(
							1 for index, facts in enumerate(found) if index not in inSources and facts["text"]
							and facts["level"] == BODY_TEXT and facts["align"] in (ALIGN_LEFT, ALIGN_JUSTIFY)
							and not facts.get("table") and not facts.get("list") and not isBody(facts))
						for first in range(0, len(numbers), CHUNK):
							check()
							run(_indent, document, numbers[first:first + CHUNK], _points(change["value"]))
						result.update(count=len(numbers), skipped=skipped)
				else:
					found = paragraphs()
					sources = sectionOf(found, change["section"]) if found is not None else None
					if found is None:
						result.update(ok=False, why=docformat.TOO_LONG_WHY)
					elif sources is None:
						result.update(ok=False, why=docformat.noSection(change["section"]))
					elif sources[1] <= sources[0]:
						result.update(ok=False, why=docformat.NOTHING_FOLLOWS)
					else:
						at, last = sources
						span = run(_span, document, found[at + 1]["start"], found[last]["end"])
						run(_hang, span, _points(change["value"]), bool(change.get("noGap")))
						result.update(
							heading=found[at]["text"], entries=sum(1 for facts in found[at + 1:last + 1] if facts["text"]))
			except Exception as fault:
				# Stopping is passed on; anything else is this one change that did not work.
				if type(fault).__name__ in PASSED_ON or isinstance(fault, PASSED_ON_KINDS):
					raise
				result.update(ok=False, why=docformat.REFUSED)
			results.append(result)
		spaceLeft = False
		if any(result["ok"] and result["change"]["what"] == docformat.SPACING for result in results) and not any(
				result["change"]["what"] == docformat.SPACE_AROUND for result in results):
			spaceLeft = bool(_safe(lambda: run(_spaceLeft, where), False))
	finally:
		run(_endUndo, record)
	return results, {"undo": record is not None, "spaceLeft": spaceLeft}


# --- The layout, from Word's own numbers ---

def _number(value):
	"""A length Word gave, in points, or None where Word has no single value for it."""
	try:
		value = float(value)
	except (TypeError, ValueError):
		return None
	return None if abs(value) >= UNDEFINED - 1 else value


def _pageFacts(document):
	setup = document.PageSetup
	page = {
		"width": _safe(lambda: _number(setup.PageWidth)), "height": _safe(lambda: _number(setup.PageHeight)),
		"left": _safe(lambda: _number(setup.LeftMargin)), "right": _safe(lambda: _number(setup.RightMargin)),
		"top": _safe(lambda: _number(setup.TopMargin)), "bottom": _safe(lambda: _number(setup.BottomMargin))}
	end = max(0, int(document.Content.End) - 1)
	lastLine = _safe(lambda: int(_arg(_span(document, end, end), "Information", INFO_LINE)))
	return {
		"title": _safe(lambda: str(document.Name), "") or "", "pages": _safe(lambda: int(document.ComputeStatistics(STATISTIC_PAGES))),
		"lastLines": lastLine if lastLine and lastLine > 0 else None, "page": page,
		"shapeCount": _safe(lambda: int(document.Shapes.Count), 0), "tables": _safe(lambda: int(document.Tables.Count), 0)}


def _across(value, relative, width, page, anchor):
	"""How far from the left edge of the page a floating thing begins, in points, or None where that cannot be
	told from Word's numbers."""
	if None in (page["width"], page["left"], page["right"]):
		return None
	area = ((0.0, page["width"]) if relative == ACROSS_PAGE
		else (page["left"], page["width"] - page["right"]) if relative in (ACROSS_MARGIN, ACROSS_COLUMN) else None)
	if value <= SHAPE_WORDS:
		if area is None or value not in (SHAPE_LEFT, SHAPE_CENTRE, SHAPE_RIGHT):
			return None
		return area[0] if value == SHAPE_LEFT else area[1] - width if value == SHAPE_RIGHT else area[0] + (area[1] - area[0] - width) / 2
	if area is not None:
		return area[0] + value
	if relative == ACROSS_CHARACTER:
		base = _safe(lambda: float(_arg(anchor, "Information", INFO_ACROSS)), -1)
		return base + value if base >= 0 else None
	return None


def _down(value, relative, height, page, anchor):
	"""How far from the top edge of the page a floating thing begins, in points, or None."""
	if None in (page["height"], page["top"], page["bottom"]):
		return None
	area = ((0.0, page["height"]) if relative == DOWN_PAGE
		else (page["top"], page["height"] - page["bottom"]) if relative == DOWN_MARGIN else None)
	if value <= SHAPE_WORDS:
		if area is None or value not in (SHAPE_TOP, SHAPE_CENTRE, SHAPE_BOTTOM):
			return None
		return area[0] if value == SHAPE_TOP else area[1] - height if value == SHAPE_BOTTOM else area[0] + (area[1] - area[0] - height) / 2
	if area is not None:
		return area[0] + value
	if relative in (DOWN_PARAGRAPH, DOWN_LINE):
		base = _safe(lambda: float(_arg(anchor, "Information", INFO_DOWN)), -1)
		return base + value if base >= 0 else None
	return None


def _shapes(document, first, count, page):
	"""Some of the document's floating things, the first numbered 1: name, kind, page, and the box each takes up
	on its page in points from the page's top left corner, or None where Word's numbers do not give it."""
	shapes = document.Shapes
	found = []
	for index in range(first, first + count):
		shape = shapes.Item(index)
		kind = _safe(lambda: int(shape.Type))
		facts = {
			"name": _safe(lambda: str(shape.Name), "") or f"number {index}",
			"kind": "text box" if kind == TEXT_BOX else "picture" if kind in (PICTURE, LINKED_PICTURE) else "shape",
			"page": None, "box": None, "outside": False}
		try:
			width, height = float(shape.Width), float(shape.Height)
			anchor = shape.Anchor
			facts["page"] = _safe(lambda: int(_arg(anchor, "Information", INFO_PAGE)))
			left = _across(float(shape.Left), int(shape.RelativeHorizontalPosition), width, page, anchor)
			top = _down(float(shape.Top), int(shape.RelativeVerticalPosition), height, page, anchor)
			if left is not None and top is not None:
				facts["box"] = (left, top, left + width, top + height)
				facts["outside"] = (left < -1 or top < -1 or left + width > page["width"] + 1 or top + height > page["height"] + 1)
		except Exception:
			pass
		found.append(facts)
	return found


def _tableWidth(document, number):
	"""How wide a table is at its widest row, in points, or None where Word does not say."""
	cells = document.Tables.Item(number).Range.Cells
	rows = {}
	for index in range(1, min(int(cells.Count), MAX_CELLS) + 1):
		cell = cells.Item(index)
		width = _number(cell.Width)
		row = int(cell.RowIndex)
		rows[row] = None if width is None or rows.get(row, 0) is None else rows.get(row, 0) + width
	widths = [width for width in rows.values() if width is not None]
	return max(widths) if widths else None


def overlapping(shapes):
	"""Which floating things take up some of the same space on the same page: [(name, name, page)]."""
	found = []
	for index, first in enumerate(shapes):
		for second in shapes[index + 1:]:
			if first["box"] is None or second["box"] is None or first["page"] != second["page"]:
				continue
			across = min(first["box"][2], second["box"][2]) - max(first["box"][0], second["box"][0])
			down = min(first["box"][3], second["box"][3]) - max(first["box"][1], second["box"][1])
			if across > 2 and down > 2:
				found.append((first["name"], second["name"], first["page"]))
	return found


def layoutOf(document, run=_direct, check=lambda: None):
	"""A Word document's layout as facts for docformat.layoutText. Only reads; nothing is changed."""
	facts = run(_pageFacts, document)
	page = facts.pop("page")
	count = facts.pop("shapeCount")
	shapes = []
	for first in range(1, min(count, MAX_SHAPES) + 1, 10):
		check()
		shapes.extend(run(_shapes, document, first, min(10, min(count, MAX_SHAPES) - first + 1), page))
	wide = []
	room = page["width"] - page["left"] - page["right"] if None not in (page["width"], page["left"], page["right"]) else None
	for number in range(1, min(facts["tables"], MAX_TABLES) + 1):
		check()
		width = _safe(lambda: run(_tableWidth, document, number))
		if width is not None and room is not None and width > room + 2:
			wide.append({"number": number, "over": (width - room) / POINTS_PER_INCH})
	facts.update(
		shapes=shapes, overlaps=overlapping(shapes), wide=wide, unplaced=sum(1 for shape in shapes if shape["box"] is None),
		cut=count > MAX_SHAPES or facts["tables"] > MAX_TABLES)
	return facts


# --- The tools ---

def register(add, plugin, text, onMain, confirm, mustAgree, screen):
	"""Add the two tools for a document. The arguments are the helpers of nvdatools.build."""

	def formatDocument(task, asked):
		words = asked or task.request
		kind, title, document, application = onMain(front, screen)
		if kind == OTHER:
			raise ToolError(docformat.NOT_A_DOCUMENT)
		if kind == DOCS:
			found = docformat.wish(words)
			if found is None:
				raise ToolError(docformat.NOTHING_ASKED)
			return docformat.docsPlan(found)
		if document is None:
			raise ToolError(docformat.NO_INTERFACE)
		found = docformat.wish(words, onMain(fontNames, application))
		if found is None:
			raise ToolError(docformat.NOTHING_ASKED)
		refusal = onMain(state, document)
		if refusal:
			raise ToolError(refusal)
		selection = found["scope"] == docformat.SELECTION
		if selection and not _safe(lambda: onMain(hasSelection, application), False):
			raise ToolError(docformat.NO_SELECTION)
		task.check()
		planned = docformat.plan(found, onMain(nowOf, document, application, selection))
		if not planned["changes"]:
			return docformat.done([], planned, found, title)
		# Everything that will be changed is named in the question; Word's own undo takes all of it back.
		confirm(docformat.question(planned, title, found))
		results, facts = applyTo(document, application, found, planned, run=onMain, check=task.check)
		return docformat.done(results, planned, found, title, undo=facts["undo"], spaceLeft=facts["spaceLeft"])

	add("format_document",
		"format the Microsoft Word document in front: a style such as APA or MLA, or the font, the font size, the line "
		"spacing, the margins, the alignment, a first-line indent or a hanging indent for the list of sources; for a "
		"document in Google Docs it says which keys do it",
		formatDocument, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Formatting the document", tell=VERBATIM)

	def checkLayout(task, asked):
		words = asked or task.request
		kind, _title, document, _application = onMain(front, screen)
		if kind == OTHER:
			raise ToolError(docformat.NOT_A_DOCUMENT)
		if kind == DOCS:
			return docformat.DOCS_LAYOUT
		if document is None:
			raise ToolError(docformat.NO_INTERFACE)
		facts = layoutOf(document, run=onMain, check=task.check)
		return docformat.layoutText(facts, docformat.layoutWish(words) or {})

	add("check_layout",
		"say how many pages the Microsoft Word document in front has, whether it fits on one page, and whether its text "
		"boxes, pictures or tables overlap or reach beyond the page, from Word's own numbers",
		checkLayout, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Checking the layout", tell=VERBATIM)
