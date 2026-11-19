# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A stand-in for Microsoft Word's interface for programs, for tests/test_docformat.py. Word is not installed on
the computer VisionClaw is built on, so doctools.py is tried against this.

Written on 2026-11-19 from Microsoft's own reference for Word (learn.microsoft.com/office/vba/api/), the same
pages doctools.py names at its top: Application (FontNames, UndoRecord, Selection), UndoRecord (StartCustomRecord,
EndCustomRecord, IsRecordingCustomRecord), Document (Name, ReadOnly, ProtectionType, Content, Paragraphs, Range,
PageSetup, ComputeStatistics, Shapes, Tables), Range (Start, End, Text, Font, ParagraphFormat, Paragraphs,
Information, ListFormat, Cells), Paragraph (Range, OutlineLevel, Alignment, FirstLineIndent, LeftIndent, Format),
Font (Name, Size), ParagraphFormat (LineSpacingRule, SpaceBefore, SpaceAfter, FirstLineIndent, LeftIndent,
Alignment), PageSetup (the four margins, PageWidth, PageHeight), Shape (Name, Type, Left, Top, Width, Height,
RelativeHorizontalPosition, RelativeVerticalPosition, Anchor), Cell (RowIndex, Width).

Like Word: collections count from 1 and are asked with Count and Item; text of several fonts has the name "" and
the size 9999999 (wdUndefined), and so has any paragraph setting that differs between the paragraphs of a range;
a member that Word does not have cannot be set. Unlike Word: pages are made by counting lines, and nothing is drawn.
Everything that is set is written down in the document's `log`, with whether an undo record was open.
"""

UNDEFINED = 9999999
LETTER = (612.0, 792.0)  # 8.5 by 11 inches, at 72 points to the inch


class _Strict:
	"""Only the members Microsoft's pages name can be set: a misspelt member is an error here as it is in Word."""
	_MEMBERS = ()

	def __setattr__(self, name, value):
		if not name.startswith("_") and name not in self._MEMBERS:
			raise AttributeError(f"{type(self).__name__} has no member {name}")
		object.__setattr__(self, name, value)


class Collection:
	def __init__(self, items):
		self._items = list(items)

	@property
	def Count(self):
		return len(self._items)

	def Item(self, index):
		if not 1 <= index <= len(self._items):
			raise IndexError("The requested member of the collection does not exist.")
		return self._items[index - 1]


class Para:
	"""One paragraph as the stand-in keeps it. lines: how many lines it takes on the page."""

	def __init__(self, text, level=10, align=0, table=False, listType=0, lines=1, font="Calibri", size=11.0):
		self.text, self.level, self.align, self.table, self.listType, self.lines = text, level, align, table, listType, lines
		self.font, self.size = font, float(size)
		self.firstLine = self.leftIndent = self.before = 0.0
		self.after = 8.0
		self.spacing = 0
		self.start = self.end = self.page = self.line = 0


_FORMAT = {
	"LineSpacingRule": "spacing", "SpaceBefore": "before", "SpaceAfter": "after", "FirstLineIndent": "firstLine",
	"LeftIndent": "leftIndent", "Alignment": "align"}


class _View(_Strict):
	"""Settings read from and written to every paragraph a range covers."""
	_FIELDS = {}
	_MIXED = UNDEFINED

	def __init__(self, document, paras, start, end):
		object.__setattr__(self, "_document", document)
		object.__setattr__(self, "_paras", paras)
		object.__setattr__(self, "_span", (start, end))

	def __getattr__(self, name):
		if name not in self._FIELDS:
			raise AttributeError(f"{type(self).__name__} has no member {name}")
		values = {getattr(para, self._FIELDS[name]) for para in self._paras}
		return values.pop() if len(values) == 1 else self._MIXED

	def __setattr__(self, name, value):
		if name not in self._FIELDS:
			raise AttributeError(f"{type(self).__name__} has no member {name}")
		self._document._refuse(name)
		for para in self._paras:
			setattr(para, self._FIELDS[name], value)
		self._document._wrote(name, value, self._span)


class ParagraphFormat(_View):
	_FIELDS = _FORMAT


class Font(_View):
	_FIELDS = {"Name": "font", "Size": "size"}

	def __getattr__(self, name):
		value = _View.__getattr__(self, name)
		return "" if name == "Name" and value == UNDEFINED else value


class ListFormat:
	def __init__(self, paras):
		self._paras = paras

	@property
	def ListType(self):
		return self._paras[0].listType if self._paras else 0


class Range(_Strict):
	_MEMBERS = ("Start", "End")

	def __init__(self, document, start, end):
		object.__setattr__(self, "_document", document)
		self.Start, self.End = start, end

	def _covered(self):
		paras = self._document._paras
		if self.End <= self.Start:
			return [para for para in paras if para.start <= self.Start < para.end][:1] or paras[-1:]
		return [para for para in paras if para.start < self.End and para.end > self.Start]

	@property
	def Text(self):
		return self._document._text()[self.Start:self.End]

	@property
	def Font(self):
		return Font(self._document, self._covered(), self.Start, self.End)

	@property
	def ParagraphFormat(self):
		return ParagraphFormat(self._document, self._covered(), self.Start, self.End)

	@property
	def Paragraphs(self):
		return Collection(Paragraph(self._document, para) for para in self._covered())

	@property
	def ListFormat(self):
		return ListFormat(self._covered())

	@property
	def Cells(self):
		return Collection(())

	def Information(self, kind):
		"""wdActiveEndPageNumber 3, the horizontal and vertical place on the page 5 and 6, the line number 10,
		wdWithInTable 12."""
		covered = self._covered()
		if not covered:
			return -1
		first, last = covered[0], covered[-1]
		page = self._document.PageSetup
		if kind == 3:
			return last.page
		if kind == 5:
			return page.LeftMargin
		if kind == 6:
			return page.TopMargin + (first.line - first.lines) * 14.0
		if kind == 10:
			return last.line
		if kind == 12:
			return first.table
		raise ValueError(f"The stand-in does not know Information({kind}).")


class Paragraph(_Strict):
	_MEMBERS = ("Alignment", "FirstLineIndent", "LeftIndent")

	def __init__(self, document, para):
		object.__setattr__(self, "_document", document)
		object.__setattr__(self, "_para", para)

	@property
	def Range(self):
		return Range(self._document, self._para.start, self._para.end)

	@property
	def Format(self):
		return ParagraphFormat(self._document, [self._para], self._para.start, self._para.end)

	@property
	def OutlineLevel(self):
		return self._para.level

	def __getattr__(self, name):
		if name in self._MEMBERS:
			return getattr(self._para, _FORMAT[name])
		raise AttributeError(f"Paragraph has no member {name}")

	def __setattr__(self, name, value):
		if name not in self._MEMBERS:
			raise AttributeError(f"Paragraph has no member {name}")
		self._document._refuse(name)
		setattr(self._para, _FORMAT[name], value)
		self._document._wrote(name, value, (self._para.start, self._para.end))


class PageSetup(_Strict):
	_MEMBERS = ("TopMargin", "BottomMargin", "LeftMargin", "RightMargin", "PageWidth", "PageHeight")

	def __init__(self, document, margin=90.0, size=LETTER):
		object.__setattr__(self, "_document", document)
		for name, value in (("TopMargin", 72.0), ("BottomMargin", 72.0), ("LeftMargin", margin), ("RightMargin", margin),
				("PageWidth", size[0]), ("PageHeight", size[1])):
			object.__setattr__(self, name, value)

	def __setattr__(self, name, value):
		if name not in self._MEMBERS:
			raise AttributeError(f"PageSetup has no member {name}")
		self._document._refuse(name)
		object.__setattr__(self, name, float(value))
		self._document._wrote(name, float(value), None)


class Shape:
	"""A floating thing. kind: 17 a text box, 13 a picture, 1 a drawn shape (MsoShapeType). across and down: what
	Left and Top are measured from (0 the margin, 1 the page; for down also 2 the paragraph it is anchored to)."""

	def __init__(self, name, kind, left, top, width, height, across=1, down=1, anchor=0):
		self.Name, self.Type, self.Left, self.Top, self.Width, self.Height = name, kind, left, top, width, height
		self.RelativeHorizontalPosition, self.RelativeVerticalPosition = across, down
		self._anchor = anchor
		self.Anchor = None


class Cell:
	def __init__(self, row, width):
		self.RowIndex, self.Width = row, width


class _TableRange:
	def __init__(self, cells):
		self.Cells = Collection(cells)


class Table:
	"""rows: the widths of the cells of each row, in points."""

	def __init__(self, rows):
		self.Range = _TableRange(Cell(number, width) for number, row in enumerate(rows, 1) for width in row)


class UndoRecord:
	def __init__(self):
		self.IsRecordingCustomRecord = False
		self.CustomRecordName = ""
		self.log = []

	def StartCustomRecord(self, Name=""):
		self.IsRecordingCustomRecord, self.CustomRecordName = True, Name[:64]
		self.log.append(("start", Name[:64]))

	def EndCustomRecord(self):
		self.IsRecordingCustomRecord = False
		self.log.append(("end", self.CustomRecordName))


class Selection:
	def __init__(self):
		self._document, self._span = None, (0, 0)

	@property
	def Range(self):
		return Range(self._document, *self._span)


class Application:
	def __init__(self, fonts=("Arial", "Calibri", "Georgia", "Times New Roman", "Modern", "Bahnschrift")):
		self.FontNames = Collection(fonts)
		self.UndoRecord = UndoRecord()
		self.Selection = Selection()


class Document:
	"""paras: the paragraphs, in order. linesPerPage: how many lines fit on a page."""

	def __init__(self, application, name, paras, linesPerPage=40, shapes=(), tables=(), margin=90.0):
		self._application, self._paras, self._linesPerPage = application, list(paras), linesPerPage
		self.Name, self.ReadOnly, self.ProtectionType = name, False, -1
		self.PageSetup = PageSetup(self, margin)
		self.log = []
		# A member that Word is made to refuse, to try what happens then.
		self.refuses = set()
		at = 0
		for para in self._paras:
			para.start, para.end = at, at + len(para.text) + 1
			at = para.end
		for shape in shapes:
			shape.Anchor = Range(self, self._paras[shape._anchor].start, self._paras[shape._anchor].start)
		self.Shapes = Collection(shapes)
		self.Tables = Collection(tables)
		self.Paragraphs = Collection(Paragraph(self, para) for para in self._paras)
		application.Selection._document = self
		self._lay()

	def _lay(self):
		"""Put the paragraphs on pages by counting lines. A paragraph's `line` is the number of its last line on
		its page, as Word's status bar counts lines."""
		page, used = 1, 0
		for para in self._paras:
			if used + para.lines > self._linesPerPage and used:
				page, used = page + 1, 0
			used += para.lines
			para.page, para.line = page, used
		self._pages = page

	def _text(self):
		return "".join(para.text + "\r" for para in self._paras)

	def _refuse(self, member):
		if member in self.refuses:
			raise OSError(f"Word refused to set {member}.")

	def _wrote(self, member, value, span):
		self.log.append((member, value, span, getattr(self._application.UndoRecord, "IsRecordingCustomRecord", False)))

	def select(self, first, last):
		"""Select the paragraphs numbered first to last, counted from 1."""
		self._application.Selection._span = (self._paras[first - 1].start, self._paras[last - 1].end)

	@property
	def Content(self):
		return Range(self, 0, self._paras[-1].end if self._paras else 0)

	def Range(self, Start=None, End=None):
		whole = self.Content
		return Range(self, whole.Start if Start is None else Start, whole.End if End is None else End)

	def ComputeStatistics(self, Statistic, IncludeFootnotesAndEndnotes=False):
		"""wdStatisticLines 1, wdStatisticPages 2, wdStatisticParagraphs 4."""
		if Statistic == 2:
			return self._pages
		if Statistic == 1:
			return sum(para.lines for para in self._paras)
		if Statistic == 4:
			return len(self._paras)
		raise ValueError(f"The stand-in does not know ComputeStatistics({Statistic}).")
