# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A document formatted and its layout checked (claw/docformat.py, doctools.py): what the user's words ask, what
APA and MLA ask, the changes that follow and what the user is told; and the work in Microsoft Word, tried
against a stand-in for Word's interface that was written from Microsoft's own reference (wordstandin.py), because
Word is not installed where VisionClaw is built. Plain Python: no NVDA, no model, no Word.

  python tests/test_docformat.py
"""
import builtins
import sys
import types

import harness  # noqa: F401
from wordstandin import Application, Document, Para, Shape, Table
from visionClaw.claw import docformat
from visionClaw.claw.tools import ToolError

# doctools.py needs two of NVDA's modules to be importable; nothing of NVDA is used by what is tried here.
builtins._ = lambda text: text
front = {"focus": None}
for name, members in (
		("addonHandler", {"initTranslation": lambda: None}),
		("api", {"getFocusObject": lambda: front["focus"], "getForegroundObject": lambda: None})):
	module = types.ModuleType(name)
	module.__dict__.update(members)
	sys.modules[name] = module
from visionClaw import doctools  # noqa: E402

ARTICLE = (
	"Format this entire Word document in APA 7th edition style: set the font to 12-point Times New Roman, "
	"double-space all paragraphs, and apply a 0.5-inch hanging indent to the References section.")
RESUME = (
	"Check the visual layout of my resume and tell me if everything fits cleanly onto a single page without any "
	"overlapping text boxes.")
WORD_FONTS = ("Arial", "Calibri", "Georgia", "Times New Roman", "Modern", "Bahnschrift", "Impact")

# --- Lengths, fonts ---

for said, length in (
		("a 0.5-inch hanging indent", 0.5), ("half an inch", 0.5), ("a half-inch indent", 0.5), ("1 inch margins", 1.0),
		("one-inch margins", 1.0), ("margins of 2.54 cm", 1.0), ("25.4 mm", 1.0), ("1.25 inches", 1.25),
		("a quarter of an inch", 0.25), ('1" margins', 1.0), ("an inch", 1.0), ("no length here", None), ("12 point", None)):
	assert docformat.measure(said) == length, (said, docformat.measure(said))
assert docformat.inches(0.5) == "half an inch" and docformat.inches(1) == "1 inch" and docformat.inches(1.25) == "1.25 inches"
assert docformat.fontIn("set the font to times new roman") == "Times New Roman"
# A font of Word's own that is an everyday word counts only where the request says "font".
assert docformat.fontIn("format this in a modern style", WORD_FONTS) is None
assert docformat.fontIn("change the font to modern", WORD_FONTS) == "Modern"
assert docformat.fontIn("use the Bahnschrift font", WORD_FONTS) == "Bahnschrift"
assert docformat.fontIn("make a big impact with this", WORD_FONTS) is None
# Word's own spelling of a well-known font is used.
assert docformat.fontIn("in ARIAL please", ("ARIAL",)) == "ARIAL"

# --- What the words ask ---

wish = docformat.wish(ARTICLE, WORD_FONTS)
assert wish["style"] == docformat.APA7 and wish["edition"] == 7 and wish["font"] == "Times New Roman" and wish["size"] == 12, wish
assert wish["spacing"] == docformat.DOUBLE and wish["hanging"] == 0.5 and wish["section"] == ("references",), wish
assert wish["scope"] == docformat.DOCUMENT and wish["wholeDocument"] is True and wish["margins"] is None, wish
for said, expected in (
		("Format this document in MLA style", {"style": docformat.MLA9}),
		("format my essay in APA", {"style": docformat.APA7}),
		("put this paper in APA 6th edition format", {"style": docformat.APA7, "edition": 6}),
		("Double-space this document", {"spacing": docformat.DOUBLE}),
		("use single spacing and justify the text", {"spacing": docformat.SINGLE, "align": docformat.JUSTIFY}),
		("set line spacing to 1.5", {"spacing": docformat.ONE_AND_HALF}),
		("one and a half line spacing please, and 1-inch margins", {"spacing": docformat.ONE_AND_HALF, "margins": 1.0}),
		("set the margins to 1 inch", {"margins": 1.0}),
		("make the margins 2.5 cm and the font Calibri size 11", {"margins": 0.984, "font": "Calibri", "size": 11}),
		("change the font to Georgia", {"font": "Georgia"}),
		("set the font to Bahnschrift", {"font": "Bahnschrift"}),
		("indent the first line of each paragraph by half an inch", {"firstLine": 0.5}),
		("add a hanging indent of half an inch to the bibliography", {"hanging": 0.5, "section": ("bibliography",)}),
		("give the works cited a hanging indent", {"hanging": 0.5, "section": ("works cited",), "hangingAssumed": True}),
		("make the selected text 14 point Arial", {"font": "Arial", "size": 14, "scope": docformat.SELECTION}),
		("remove the space after paragraphs", {"spaceAround": 0}),
		("set the margins", {"margins": docformat.UNCLEAR}),
		("centre align everything in this document", {"align": docformat.CENTRE}),
		("left-align the whole document", {"align": docformat.LEFT}),
		("Could you double space my paper and use Times New Roman 12 pt?", {"spacing": docformat.DOUBLE, "font": "Times New Roman", "size": 12})):
	found = docformat.wish(said, WORD_FONTS)
	assert found is not None, said
	for key, value in expected.items():
		assert found[key] == value, (said, key, found[key])
	# Nothing is read into the words that they do not say.
	for key in ("font", "size", "spacing", "margins", "firstLine", "hanging", "align", "spaceAround", "style"):
		assert key in expected or found[key] is None, (said, key, found[key])
# A question, and what is about something else, is no wish to format.
for said in (
		"what font is this", "how do I double-space in Word", "Is this document double spaced?", "which font does APA want",
		"How can I set a hanging indent?", "open my recycle bin", "make NVDA talk faster", "format this in a modern style",
		"read the references section", "what are the margins of this document", "", "how to format a paper in MLA"):
	assert docformat.wish(said, WORD_FONTS) is None, said

# --- The changes that follow, and what a style adds ---

plan = docformat.plan(wish, {"font": "Calibri", "size": 11})
assert [change["what"] for change in plan["changes"]] == [
	docformat.FONT, docformat.SIZE, docformat.SPACING, docformat.MARGINS, docformat.HANGING], plan
assert [change["text"] for change in plan["changes"]] == [
	"the font: Times New Roman", "the font size: 12 point", "the line spacing: double", "the margins: 1 inch on every side",
	"a hanging indent of half an inch for the entries under References"], plan
assert docformat.changes(wish) == docformat.plan(wish)["changes"]
# APA accepts the font the document has, so it stays; nothing about a first-line indent is claimed for APA.
plan = docformat.plan(docformat.wish("format my essay in APA"), {"font": "Calibri", "size": 11})
assert [change["what"] for change in plan["changes"]] == [docformat.SPACING, docformat.MARGINS, docformat.HANGING], plan
assert plan["notes"] == ["The font is Calibri, 11 point, which APA accepts, so it stays as it is."], plan["notes"]
plan = docformat.plan(docformat.wish("format my essay in APA"), {"font": "Comic Sans MS", "size": 14})
assert [change["text"] for change in plan["changes"]][:2] == ["the font: Times New Roman", "the font size: 12 point"], plan
assert plan["notes"][0].startswith("APA accepts other fonts too: Calibri 11 point, Arial 11 point"), plan["notes"]
# A font the user names gets the size APA gives for it.
plan = docformat.plan(docformat.wish("format this document in APA with Georgia"), {"font": "Arial", "size": 14})
assert [change["text"] for change in plan["changes"]][:2] == ["the font: Georgia", "the font size: 11 point"], plan
# MLA: 12 point, the first line of body text half an inch, no gap between the entries; the font's name is left.
plan = docformat.plan(docformat.wish("Format this document in MLA style"), {"font": "Calibri", "size": 11})
assert [change["what"] for change in plan["changes"]] == [
	docformat.SIZE, docformat.SPACING, docformat.MARGINS, docformat.FIRST_LINE, docformat.HANGING], plan
assert plan["changes"][-1]["noGap"] is True and plan["changes"][-1]["section"] == ("works cited", "work cited")
assert plan["changes"][-1]["text"] == (
	"a hanging indent of half an inch for the entries under Works Cited or Work Cited, with no extra space between them")
assert "The font's name was left as it is, Calibri" in plan["notes"][0], plan["notes"]
# What the words say outright comes before what the style asks.
plan = docformat.plan(docformat.wish("format this paper in MLA with 1.5 line spacing and 2 inch margins"))
values = {change["what"]: change["value"] for change in plan["changes"]}
assert values[docformat.SPACING] == docformat.ONE_AND_HALF and values[docformat.MARGINS] == 2.0, values
# Another edition than the one known is said.
plan = docformat.plan(docformat.wish("put this paper in APA 6th edition format"))
assert plan["notes"][-1] == "You said the 6th edition; VisionClaw knows what the 7th edition asks, and used that."
# Named without a length.
plan = docformat.plan(docformat.wish("set the margins"))
assert plan["changes"] == [] and plan["unclear"] == ["the margins"]
assert docformat.unclearText(plan["unclear"]).startswith("You named the margins without saying how much")
plan = docformat.plan(docformat.wish("give the works cited a hanging indent"))
assert plan["changes"][0]["value"] == 0.5 and "half an inch was used" in plan["notes"][0], plan
# The selected text.
plan = docformat.plan(docformat.wish("give the selected paragraphs a hanging indent of 1 inch"))
assert plan["changes"][0]["text"] == "a hanging indent of 1 inch for the selected paragraphs", plan

question = docformat.question(docformat.plan(wish), "Paper.docx", wish)
assert question == (
	"Format the document Paper.docx in APA 7th edition style? This will set: the font: Times New Roman; the font size: "
	"12 point; the line spacing: double; the margins: 1 inch on every side; and a hanging indent of half an inch for "
	"the entries under References. In Word, Control+Z undoes all of it in one step."), question

# --- Google Docs: nothing is changed, the keys are said ---

docs = docformat.docsPlan(docformat.wish("double space this document, justify it and set the font to 12 point Arial"))
assert docs.startswith("Google Docs has no interface for programs like the one Word has, so VisionClaw changed nothing.")
for part in ("press Control+A", "every paragraph justified: Control+Shift+J", "Control+Shift+period", "Press Alt+/",
		"the line spacing: double", "the font: Arial", docformat.DOCS_NOT_TRIED):
	assert part in docs, (part, docs)
# Only keys every keyboard has, and nothing that needs sight.
for text in (docs, docformat.docsPlan(wish), docformat.DOCS_LAYOUT):
	assert not any(word in text.lower() for word in ("page up", "page down", "home", "insert", "f1", "click", "look at", "see ")), text

# --- Whether the words ask about the layout ---

for said, expected in (
		(RESUME, {"onePage": True, "overlap": True, "pages": False}),
		("how many pages is this document", {"onePage": False, "overlap": False, "pages": True}),
		("does my letter fit on one page", {"onePage": True, "overlap": False, "pages": False}),
		("do any text boxes overlap in this document", {"onePage": False, "overlap": True, "pages": False}),
		("is anything spilling onto a second page in my cv", {"onePage": True, "overlap": False, "pages": False})):
	assert docformat.layoutWish(said) == expected, (said, docformat.layoutWish(said))
for said in ("how is this page laid out", "change the keyboard layout to laptop", "what is the layout of this window",
		"open my resume", "make NVDA talk faster", ""):
	assert docformat.layoutWish(said) is None, said

# --- Word: a paper made up here ---


def paper(extra=(), cut=None, **options):
	"""A paper as a student would hand it in, with a list of references; cut: only its first paragraphs.
	Returns (application, document)."""
	application = Application(WORD_FONTS)
	paras = [
		Para("The Effect of Sleep on Memory", align=1), Para("Sam Rivera", align=1), Para("", lines=1),
		Para("Sleep matters for memory. This paper says why, and what was measured over three weeks.", lines=3),
		Para("Method", level=1, align=1),
		Para("Forty students took part.", lines=1),
		Para("They slept in the laboratory", listType=3), Para("Group A, eight hours", table=True),
		Para("19 November 2026"),
		Para("References", align=1),
		Para("Rivera, S. (2025). Sleep and memory. Journal of Sleep, 4(2), 10-20.", lines=2),
		Para(""),
		Para("Stone, P. (2024). Memory in students. Learning Press.", lines=1),
		Para("Appendix", align=1),
		Para("The questions that were asked are listed here.")] + list(extra)
	return application, Document(application, "Paper.docx", paras[:cut] if cut else paras, **options)


def written(document, member):
	return [entry for entry in document.log if entry[0] == member]


# The article's own request.
application, document = paper()
wish = docformat.wish(ARTICLE, doctools.fontNames(application))
assert doctools.nowOf(document, application, False) == {"font": "Calibri", "size": 11}
plan = docformat.plan(wish, doctools.nowOf(document, application, False))
results, facts = doctools.applyTo(document, application, wish, plan)
assert all(result["ok"] for result in results) and len(results) == 5, results
assert all(para.font == "Times New Roman" and para.size == 12 and para.spacing == 2 for para in document._paras)
setup = document.PageSetup
assert (setup.TopMargin, setup.BottomMargin, setup.LeftMargin, setup.RightMargin) == (72.0, 72.0, 72.0, 72.0)
# The hanging indent is on the entries under References, up to the next centred heading, and nowhere else.
hung = [para.text[:6] for para in document._paras if para.leftIndent == 36.0 and para.firstLine == -36.0]
assert hung == ["Rivera", "", "Stone,"], hung
assert all(para.leftIndent == 0 and para.firstLine == 0 for para in document._paras if para.text[:6] not in ("Rivera", "", "Stone,"))
assert results[-1]["heading"] == "References" and results[-1]["entries"] == 2, results[-1]
# One entry in Word's undo list: begun once, ended once, and everything was written while it was open.
assert application.UndoRecord.log == [("start", "VisionClaw formatting"), ("end", "VisionClaw formatting")]
assert document.log and all(entry[3] for entry in document.log), document.log
assert facts == {"undo": True, "spaceLeft": True}, facts
said = docformat.done(results, plan, wish, "Paper.docx", undo=facts["undo"], spaceLeft=facts["spaceLeft"])
assert said.startswith(
	"Formatted Paper.docx in APA 7th edition style. Set: the font: Times New Roman; the font size: 12 point; the line "
	"spacing: double; the margins: 1 inch on every side; and a hanging indent of half an inch for the entries under "
	"References: 2 entries after the heading References."), said
for part in ("extra space before or after them, which was left as it is", "APA also asks for these, which VisionClaw did not do: a title page",
		"did not say how far the first line of a paragraph is indented", "In Word, Control+Z undoes all of it in one step."):
	assert part in said, (part, said)

# MLA: the first line of body text only; no title, name, date, heading, list item, table cell or entry.
application, document = paper()
document._paras[9].text = "Works Cited"
wish = docformat.wish("Format this document in MLA style")
plan = docformat.plan(wish, doctools.nowOf(document, application, False))
results, facts = doctools.applyTo(document, application, wish, plan)
assert all(result["ok"] for result in results), results
indented = [para.text[:12] for para in document._paras if para.firstLine == 36.0]
assert indented == ["Sleep matter", "Forty studen", "The question"], indented
first = next(result for result in results if result["change"]["what"] == docformat.FIRST_LINE)
assert first["count"] == 3 and first["skipped"] == 1, first  # the date is the one short line left alone
entries = [para for para in document._paras if para.firstLine == -36.0]
assert len(entries) == 3 and all(para.before == 0 and para.after == 0 for para in entries), entries
assert all(para.size == 12 and para.font == "Calibri" for para in document._paras)
said = docformat.done(results, plan, wish, "Paper.docx", undo=True, spaceLeft=facts["spaceLeft"])
for part in ("the first line of each paragraph of body text indented by half an inch: 3 paragraphs; 1 short line that looks "
		"like a heading, a title, a name or a date was left as it is", "MLA also asks for these", "your last name and the page number"):
	assert part in said, (part, said)
assert "did not say how far" not in said

# A font Word does not have: that change is not made, the others are, and it is said.
application, document = paper()
wish = docformat.wish("set the font to Garamond and double-space this document")
plan = docformat.plan(wish)
results, facts = doctools.applyTo(document, application, wish, plan)
assert [result["ok"] for result in results] == [False, True] and results[0]["why"] == docformat.NO_SUCH_FONT
assert all(para.font == "Calibri" and para.spacing == 2 for para in document._paras)
said = docformat.done(results, plan, wish, "Paper.docx")
assert "Not done, the font: Garamond: Word on this computer has no font of that name." in said, said

# No heading for the list: the hanging indent is not put anywhere, and the user is told what to do instead.
application, document = paper()
document._paras[9].text = "Sources I used"
wish = docformat.wish("double space this and add a hanging indent of half an inch to the references")
plan = docformat.plan(wish)
results, facts = doctools.applyTo(document, application, wish, plan)
assert [result["ok"] for result in results] == [True, False], results
assert all(para.leftIndent == 0 for para in document._paras)
assert "no paragraph that says only References was found" in docformat.done(results, plan, wish, "Paper.docx")
# A heading with nothing after it.
application, document = paper(cut=10)
results, facts = doctools.applyTo(document, application, wish, plan)
assert results[1]["ok"] is False and results[1]["why"] == docformat.NOTHING_FOLLOWS, results

# Only what is selected.
application, document = paper()
document.select(4, 6)
assert doctools.hasSelection(application)
wish = docformat.wish("make the selected text 14 point Arial and give it a hanging indent of 1 inch")
plan = docformat.plan(wish, doctools.nowOf(document, application, True))
results, facts = doctools.applyTo(document, application, wish, plan)
assert all(result["ok"] for result in results), results
changed = [index for index, para in enumerate(document._paras) if para.font == "Arial"]
assert changed == [3, 4, 5] and all(document._paras[index].leftIndent == 72.0 and document._paras[index].firstLine == -72.0 for index in changed)
application, document = paper()
assert not doctools.hasSelection(application)

# Word refuses one thing: the others are still done, the undo entry is still closed.
application, document = paper()
document.refuses.add("LineSpacingRule")
wish = docformat.wish(ARTICLE, WORD_FONTS)
plan = docformat.plan(wish)
results, facts = doctools.applyTo(document, application, wish, plan)
assert [result["ok"] for result in results] == [True, True, False, True, True], results
assert results[2]["why"] == docformat.REFUSED and application.UndoRecord.log[-1][0] == "end"
assert "Not done, the line spacing: double: Word refused it." in docformat.done(results, plan, wish, "Paper.docx")


# The user stops it: that is passed on, and the undo entry is closed all the same.
class Cancelled(Exception):
	pass


def stopAfter(count):
	calls = []

	def check():
		calls.append(1)
		if len(calls) > count:
			raise Cancelled()
	return check


application, document = paper()
try:
	doctools.applyTo(document, application, wish, plan, check=stopAfter(2))
	raise AssertionError("stopping was not passed on")
except Cancelled:
	pass
assert application.UndoRecord.log == [("start", "VisionClaw formatting"), ("end", "VisionClaw formatting")]
assert not application.UndoRecord.IsRecordingCustomRecord

# A Word without undo records: the changes are made, and the user is told that undo goes step by step.
application, document = paper()
application.UndoRecord = None
results, facts = doctools.applyTo(document, application, wish, plan)
assert all(result["ok"] for result in results) and facts["undo"] is False
assert docformat.done(results, plan, wish, "Paper.docx", undo=False).endswith(docformat.UNDO_STEPS)

# More paragraphs than are gone through one by one: what needs each paragraph is not done, the rest is.
application, document = paper()
doctools.MAX_PARAGRAPHS, kept = 5, doctools.MAX_PARAGRAPHS
results, facts = doctools.applyTo(document, application, wish, plan)
doctools.MAX_PARAGRAPHS = kept
assert results[-1]["ok"] is False and results[-1]["why"] == docformat.TOO_LONG_WHY and all(r["ok"] for r in results[:-1])

# Read in small visits: no visit reads more than CHUNK paragraphs.
application, document = paper([Para(f"Sentence number {number}.") for number in range(70)])
visits = []


def counting(fn, *args):
	visits.append(getattr(fn, "__name__", "?"))
	return fn(*args)


wish2 = docformat.wish("indent the first line of each paragraph by half an inch")
results, facts = doctools.applyTo(document, application, wish2, docformat.plan(wish2), run=counting)
assert results[0]["ok"] and results[0]["count"] == 73, results  # the paper's three, and the seventy added
assert visits.count("_scan") == 3 and visits.count("_indent") == 3, visits

# What cannot be changed, and text of several fonts.
application, document = paper()
assert doctools.state(document) is None
document.ReadOnly = True
assert doctools.state(document) == docformat.READ_ONLY
document.ReadOnly, document.ProtectionType = False, 3
assert doctools.state(document) == docformat.PROTECTED
document._paras[0].font, document._paras[0].size = "Arial", 20.0
assert doctools.nowOf(document, application, False) == {"font": None, "size": None}

# Where the list ends: at the end, or before the next heading of the same kind.
facts = [{"text": text, "level": level, "align": align} for text, level, align in (
	("Intro", 1, 0), ("Body text here.", 10, 0), ("References", 1, 0), ("A. (2020).", 10, 0), ("B. (2021).", 10, 0),
	("Appendix", 1, 0), ("More.", 10, 0))]
assert doctools.sectionOf(facts, ("references",)) == (2, 4)
assert doctools.sectionOf(facts[:5], ("references",)) == (2, 4)
assert doctools.sectionOf(facts, ("works cited",)) is None
# A line of a table of contents says more than the heading, and the last one that fits is the heading.
toc = [{"text": "References 12", "level": 10, "align": 0}, {"text": "References", "level": 10, "align": 0}] + facts
assert doctools.sectionOf(toc, ("references",)) == (4, 6)

# --- Word: the layout ---

# A resume of one page: two text boxes that overlap, a picture that reaches beyond the page, a table too wide.
application = Application(WORD_FONTS)
resume = Document(
	application, "Resume.docx", [Para("Sam Rivera", align=1), Para("Experience and education follow.", lines=20)],
	shapes=(
		Shape("Text Box 2", 17, 72.0, 200.0, 200.0, 80.0), Shape("Text Box 5", 17, 250.0, 250.0, 150.0, 60.0),
		Shape("Picture 1", 13, 500.0, 300.0, 200.0, 100.0), Shape("Logo", 1, -999995, 20.0, 100.0, 40.0, across=0, down=0),
		Shape("Odd", 17, 10.0, 10.0, 50.0, 50.0, across=5, down=5)),
	tables=(Table([[140.0, 140.0, 140.0], [420.0]]), Table([[200.0, 200.0, 200.0]])))
before = list(resume.log)
layout = doctools.layoutOf(resume)
assert resume.log == before, "checking the layout changed the document"
assert layout["pages"] == 1 and layout["title"] == "Resume.docx" and layout["tables"] == 2, layout
assert layout["overlaps"] == [("Text Box 2", "Text Box 5", 1)], layout["overlaps"]
assert [shape["name"] for shape in layout["shapes"] if shape["outside"]] == ["Picture 1"], layout["shapes"]
# Centred between the margins: (612 - 90 - 90 - 100) / 2 from the left margin; 20 points below the top margin.
logo = next(shape for shape in layout["shapes"] if shape["name"] == "Logo")
assert logo["box"] == (256.0, 92.0, 356.0, 132.0), logo
assert layout["unplaced"] == 1 and layout["wide"] == [{"number": 2, "over": (600.0 - 432.0) / 72.0}], layout
said = docformat.layoutText(layout, docformat.layoutWish(RESUME))
assert said.startswith("Yes, it fits on one page: Resume.docx is 1 page long."), said
assert docformat.layoutText(layout).startswith("Resume.docx is 1 page long.")
for part in ("one covers part of the other: Text Box 2 and Text Box 5 on page 1.", "Reaching beyond the edge of the page",
		"cut off in print: Picture 1 on page 1.", "table 2, by about 2.33 inches", "Word gave no place on the page for 1 floating thing",
		"from Word's own numbers", "not from a picture"):
	assert part in said, (part, said)
# Three pages with two lines on the last; nothing floating.
application = Application(WORD_FONTS)
long = Document(application, "CV.docx", [Para("Line.", lines=40), Para("More.", lines=40), Para("End.", lines=2)])
layout = doctools.layoutOf(long)
assert layout["pages"] == 3 and layout["lastLines"] == 2 and layout["shapes"] == [] and layout["overlaps"] == [], layout
said = docformat.layoutText(layout, {"onePage": True})
assert said.startswith("No, it does not fit on one page: CV.docx is 3 pages long. The last page holds 2 lines of text. So only a little runs over onto page 3"), said
assert "The document has no text boxes, floating pictures or shapes, so nothing can overlap." in said
# Text boxes that do not touch.
application = Application(WORD_FONTS)
tidy = Document(application, "Flyer.docx", [Para("Hello.")], shapes=(
	Shape("Text Box 1", 17, 72.0, 100.0, 100.0, 50.0), Shape("Text Box 2", 17, 300.0, 100.0, 100.0, 50.0)))
said = docformat.layoutText(doctools.layoutOf(tidy))
assert "Nothing overlaps: the document has 2 floating things (2 text boxes, the rest pictures or shapes)" in said, said
# No sight words in what is said about a layout.
assert not any(word in said.lower() for word in ("look at", "as you can see", "click")), said

# --- The two tools, with stand-ins for what nvdatools.build hands over ---


class Screen:
	app, title = "winword", "Paper.docx - Word"

	def where(self):
		return self.app, self.title, None, front["focus"]


class Focus:
	def __init__(self, document, application):
		self.WinwordDocumentObject, self.WinwordApplicationObject = document, application


class Task:
	request = ""

	def check(self):
		pass


class SaidNo(Exception):
	pass


registered, asked = {}, []
answer = {"yes": True}


def add(name, description, fn, fields=None, **options):
	registered[name] = (fn, fields, options, description)


def confirm(question):
	asked.append(question)
	if not answer["yes"]:
		raise SaidNo()


screen = Screen()
doctools.register(
	add, None, lambda description, **extra: dict(type="string", description=description, **extra),
	lambda fn, *args: fn(*args), confirm, confirm, screen)
assert set(registered) == {"format_document", "check_layout"}
for name, (fn, fields, options, description) in registered.items():
	assert list(fields) == ["asked"] and fields["asked"]["auto"] is True and fields["asked"]["maxLength"] == 300, fields
	assert options["tell"] == "verbatim" and options["title"] and description, name
assert registered["format_document"][2].get("changes") is True and registered["check_layout"][2].get("looks") is True
formatDocument, checkLayout = registered["format_document"][0], registered["check_layout"][0]

# Word in front: asked first, with every change named, then done.
application, document = paper()
front["focus"] = Focus(document, application)
said = formatDocument(Task(), ARTICLE)
assert len(asked) == 1 and asked[0].startswith("Format the document Paper.docx in APA 7th edition style? This will set: the font: Times New Roman;"), asked
assert said.startswith("Formatted Paper.docx in APA 7th edition style.") and document._paras[3].font == "Times New Roman", said
# The user says no: nothing is changed.
application, document = paper()
front["focus"] = Focus(document, application)
answer["yes"] = False
try:
	formatDocument(Task(), ARTICLE)
	raise AssertionError("the no was not passed on")
except SaidNo:
	pass
assert document.log == [] and application.UndoRecord.log == []
answer["yes"] = True
# Nothing to change but something to say: no question is asked.
del asked[:]
said = formatDocument(Task(), "set the margins")
assert asked == [] and said.startswith("Nothing was changed in Paper.docx.") and "without saying how much" in said, said
# What is refused, each with a sentence.
for words, setUp, expected in (
		("make NVDA talk faster", None, docformat.NOTHING_ASKED),
		(ARTICLE, lambda: setattr(document, "ReadOnly", True), docformat.READ_ONLY),
		("make the selected text 14 point", lambda: setattr(document, "ReadOnly", False), docformat.NO_SELECTION)):
	if setUp:
		setUp()
	try:
		formatDocument(Task(), words)
		raise AssertionError(words)
	except ToolError as fault:
		assert str(fault) == expected, (words, str(fault))
assert document.log == []
# Word in front, but its interface cannot be reached.
front["focus"] = object()
for tool in (formatDocument, checkLayout):
	try:
		tool(Task(), ARTICLE)
		raise AssertionError("no interface")
	except ToolError as fault:
		assert str(fault) == docformat.NO_INTERFACE
# The layout through the tool.
front["focus"] = Focus(resume, application)
said = checkLayout(Task(), RESUME)
assert said.startswith("Yes, it fits on one page: Resume.docx is 1 page long.") and "Text Box 2 and Text Box 5" in said, said
# Google Docs: nothing is changed; the keys are said. Another program: said so.
screen.app, screen.title = "chrome", "My essay - Google Docs - Google Chrome"
said = formatDocument(Task(), ARTICLE)
assert said.startswith("Google Docs has no interface for programs") and "Press Alt+/" in said, said
assert checkLayout(Task(), RESUME) == docformat.DOCS_LAYOUT
screen.app, screen.title = "notepad", "Untitled - Notepad"
for tool in (formatDocument, checkLayout):
	try:
		tool(Task(), ARTICLE)
		raise AssertionError("not a document")
	except ToolError as fault:
		assert str(fault) == docformat.NOT_A_DOCUMENT

# --- What the two styles hold, and that every sentence is fit to be heard ---

for style in docformat.STYLES.values():
	assert style["spacing"] == docformat.DOUBLE and style["margins"] == 1.0 and style["hanging"] == 0.5, style["name"]
	assert style["alsoAsks"] and all(sentence[0].islower() or sentence[0] in "\"'" or sentence.split()[0] in ("VisionClaw",) for sentence in style["alsoAsks"])
assert docformat.STYLES[docformat.APA7]["firstLine"] is None and docformat.STYLES[docformat.MLA9]["firstLine"] == 0.5
assert ("Times New Roman", 12) in docformat.STYLES[docformat.APA7]["fonts"] and ("Calibri", 11) in docformat.STYLES[docformat.APA7]["fonts"]
for sentence in (docformat.NOT_A_DOCUMENT, docformat.NO_INTERFACE, docformat.READ_ONLY, docformat.PROTECTED, docformat.NOTHING_ASKED,
		docformat.NO_SELECTION, docformat.DOCS_NOT_TRIED, docformat.DOCS_LAYOUT, docformat.UNDO):
	assert sentence.endswith(".") and "  " not in sentence and "*" not in sentence and "#" not in sentence, sentence

print("OK")
