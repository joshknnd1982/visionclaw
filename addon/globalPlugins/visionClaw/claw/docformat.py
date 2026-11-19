# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - formatting a document and checking its layout, as plain logic: what the user's own words ask
# ("format this document in APA style", "double-space all paragraphs", "a half-inch hanging indent for the
# References", "does my resume fit on one page"), what a style such as APA or MLA asks, the list of changes that
# follows, and every sentence the user is told. A model writes nothing here. doctools.py does the work in
# Microsoft Word through Word's own interface; this file knows nothing of Word or NVDA.
#
# What the two styles ask was read, not remembered, on 2026-11-19:
#   APA 7th edition, from Purdue University's Online Writing Lab (OWL), because APA's own pages
#   (apastyle.apa.org/style-grammar-guidelines/paper-format and its pages on font, line spacing, margins, paragraph
#   format and page header) answer a program with a challenge, which is not worked around:
#     owl.purdue.edu/owl/research_and_citation/apa_style/apa_formatting_and_style_guide/general_format.html
#       (margins of 1 inch on all sides; double-spaced; the fonts recommended; the page header; the title page)
#     .../apa_formatting_and_style_guide/reference_list_basic_rules.html
#       (the label References, bold and centred, on a new page; a hanging indent of one-half inch; double-spaced;
#       entries in the order of the alphabet)
#     .../apa_formatting_and_style_guide/apa_headings_and_seriation.html (the five levels of heading)
#   None of these pages says how far the first line of a paragraph of body text is indented in APA, so VisionClaw
#   sets no first-line indent for APA unless the user asks for one, and says so.
#   MLA 9th edition, from Purdue's OWL as well; MLA's own page (style.mla.org/formatting-papers) only points to
#   a sample chapter elsewhere:
#     owl.purdue.edu/owl/research_and_citation/mla_style/mla_formatting_and_style_guide/mla_general_format.html
#       (margins of 1 inch; double-spaced; a legible font, Times New Roman as the example, 12 point; the first
#       line of a paragraph one-half inch from the left margin; the header with last name and page number; the
#       heading and title of the first page; no title page)
#     .../mla_formatting_and_style_guide/mla_works_cited_page_basic_format.html
#       (the label Works Cited, centred; double-spaced with no extra space between entries; lines after the
#       first indented by 0.5 inches; on a separate page at the end)
# Google Docs' keys were read on the same day from Google's own page "Keyboard shortcuts for Google Docs"
# (support.google.com/docs/answer/179738): it lists keys for selecting all, the tool finder, alignment, indenting,
# normal text and headings, and font size one step up or down; it lists none for line spacing, the name of the
# font or a hanging indent.
# When a style or Google's keys are brought up to date, read the pages again; do not write from memory.
# No NVDA dependencies.

import re

APA7, MLA9 = "apa7", "mla9"
SINGLE, ONE_AND_HALF, DOUBLE = "single", "1.5", "double"
LEFT, CENTRE, RIGHT, JUSTIFY = "left", "centre", "right", "justify"
FONT, SIZE, SPACING, SPACE_AROUND, MARGINS, ALIGN, FIRST_LINE, HANGING = (
	"font", "size", "spacing", "spaceAround", "margins", "align", "firstLine", "hanging")
DOCUMENT, SELECTION = "document", "selection"
# What a part of the request names without saying how much: the user is told to say how much.
UNCLEAR = "unclear"
# The words a list of sources is headed with. A paragraph that says exactly one of these begins that section.
HEADINGS = ("references", "reference list", "works cited", "work cited", "bibliography")

# name: what the style asks. A value of None is something the pages read did not say; it is left as it is.
STYLES = {
	APA7: {
		"name": "APA 7th edition", "family": "APA", "edition": 7,
		# The fonts Purdue's page lists as recommended; it says the manual requires no single one of them.
		"fonts": (("Times New Roman", 12), ("Calibri", 11), ("Arial", 11), ("Georgia", 11), ("Lucida Sans Unicode", 10),
			("Computer Modern", 10)),
		"font": "Times New Roman", "size": 12, "spacing": DOUBLE, "margins": 1.0, "firstLine": None, "hanging": 0.5,
		"headings": ("references",), "entriesNoGap": False,
		"alsoAsks": (
			"a title page: the title in bold, centred, in the upper half of the page, then your name and where you study "
			"or work; a student's paper adds the course, the instructor and the date it is due",
			"the page number at the top right of every page; a paper for publication also has its title in capital "
			"letters at the top left",
			"the word References in bold and centred, at the top of a new page, with the entries in the order of the "
			"alphabet by the first author's last name",
			"headings in APA's five levels: level 1 centred and bold, level 2 at the left margin and bold, level 3 at the "
			"left margin in bold italics, levels 4 and 5 indented, bold, ending with a full stop, level 5 in italics too",
		),
		"notRead": (
			"VisionClaw's sources for APA did not say how far the first line of a paragraph is indented, so that was left "
			"as it is. You can ask for it: indent the first line of each paragraph by half an inch."),
	},
	MLA9: {
		"name": "MLA 9th edition", "family": "MLA", "edition": 9,
		# MLA asks for a legible font and names Times New Roman as an example; which font is legible is not for
		# plain code to judge, so the font's name is left unless the user names one.
		"fonts": None,
		"font": None, "size": 12, "spacing": DOUBLE, "margins": 1.0, "firstLine": 0.5, "hanging": 0.5,
		"headings": ("works cited", "work cited"), "entriesNoGap": True,
		"alsoAsks": (
			"no title page; at the top left of the first page your name, your instructor's name, the course and the date, "
			"each on a line of its own",
			"the title centred, not bold, not underlined and not in capital letters",
			"your last name and the page number at the top right of every page, half an inch from the top",
			"the words Works Cited centred, not bold, on a page of their own at the end",
		),
		"notRead": "",
	},
}
# Fonts that are known by their name alone. Any other font of Word's own list counts only where the request says
# "font": Word has fonts called Modern, Script, Roman, System and Impact, which are everyday words too.
COMMON_FONTS = (
	"Times New Roman", "Arial", "Calibri", "Georgia", "Cambria", "Verdana", "Tahoma", "Courier New", "Garamond",
	"Helvetica", "Lucida Sans Unicode", "Computer Modern", "Aptos", "Century Gothic", "Book Antiqua",
	"Palatino Linotype", "Segoe UI", "Comic Sans MS", "Consolas", "Trebuchet MS", "Arial Narrow", "Century Schoolbook")
_QUESTION = re.compile(
	r"^\W*(?:what|which|why|where|when|who|how)\b|\bhow (?:do|can|would|should|could|does|did) (?:i|we|you|one)\b|\bhow to\b"
	r"|^\W*(?:is|are|does|did|was|were)\b", re.IGNORECASE)
_APA = re.compile(r"\bapa\b", re.IGNORECASE)
_MLA = re.compile(r"\bmla\b", re.IGNORECASE)
_EDITION = re.compile(
	r"\b(\d{1,2})(?:st|nd|rd|th)?[- ]edition\b|\bedition\s+(\d{1,2})\b|\b(?:apa|mla)\s*(\d{1,2})\b", re.IGNORECASE)
_SIZE = re.compile(
	r"(?<![\d.])(\d{1,2}(?:\.5)?)\s*-?\s*(?:pt|pts|points?)\b(?!\s*(?:hanging|indent|margin|first|of space|space))"
	r"|\b(?:font\s+)?size\s+(?:of\s+|to\s+|at\s+)?(\d{1,2}(?:\.5)?)\b(?!\s*(?:inch|cm|mm|percent|%))", re.IGNORECASE)
_HALF_SPACING = re.compile(
	r"\b1\.5[- ]?(?:line[- ]?)?spac\w*|\bone[- ]and[- ]a[- ]half[- ]?(?:line[- ]?)?spac\w*|\bspace[- ]and[- ]a[- ]half\b"
	r"|\b(?:line[- ]?)?spacing\b[^,.;:]{0,20}?(?<![\d.])(?:1\.5|one and a half)\b(?!\s*-?\s*(?:inch|cm|mm|pt|point))",
	re.IGNORECASE)
_DOUBLE_SPACING = re.compile(
	r"\bdouble[- ]?spac\w*|\bdouble[- ]line[- ]spac\w*"
	r"|\b(?:line[- ]?)?spacing\b[^,.;:]{0,20}?\b(?:double|2(?:\.0)?(?![\d.]))(?!\s*-?\s*(?:inch|cm|mm|pt|point))", re.IGNORECASE)
_SINGLE_SPACING = re.compile(
	r"\bsingle[- ]?spac\w*|\bsingle[- ]line[- ]spac\w*"
	r"|\b(?:line[- ]?)?spacing\b[^,.;:]{0,20}?\b(?:single|1(?:\.0)?(?![\d.]))(?!\s*-?\s*(?:inch|cm|mm|pt|point))", re.IGNORECASE)
_SPACE_AROUND = re.compile(
	r"\b(?:remove|delete|no|without|take out|take away|get rid of|strip)\b[^,.;:]{0,30}?\b(?:spaces?|spacing|gaps?)\b"
	r"[^,.;:]{0,20}?\b(?:before|after|between|around)\b[^,.;:]{0,20}?\bparagraphs?\b", re.IGNORECASE)
_ALIGNS = (
	(JUSTIFY, re.compile(r"\bjustif\w+\b", re.IGNORECASE)),
	(LEFT, re.compile(r"\bleft[- ]align\w*|\balign\w*\b[^,.;:]{0,30}?\bleft\b|\bflush left\b", re.IGNORECASE)),
	(RIGHT, re.compile(r"\bright[- ]align\w*|\balign\w*\b[^,.;:]{0,30}?\bright\b|\bflush right\b", re.IGNORECASE)),
	(CENTRE, re.compile(
		r"\bcent(?:er|re)[- ]align\w*|\balign\w*\b[^,.;:]{0,30}?\bcent(?:er|re)\b"
		r"|\bcent(?:er|re)\b\s+(?:all|every|each|the)?\s*(?:the\s+)?(?:text|everything|paragraphs?|document|selection|it)\b", re.IGNORECASE)),
)
_SELECTION = re.compile(
	r"\b(?:selected|selection|highlighted|this paragraph|these paragraphs|the paragraph i'?m in|what i (?:have )?selected)\b",
	re.IGNORECASE)
_HANGING = re.compile(r"\bhanging[- ]indent\w*", re.IGNORECASE)
_FIRST_LINE = re.compile(
	r"\bfirst[- ]line indent\w*|\bindent\w*\b[^,.;:]{0,12}?\bfirst lines?\b|\bindent\w* (?:each|every|all|the) paragraphs?\b"
	r"|\bparagraph indent\w*", re.IGNORECASE)
_MARGINS = re.compile(r"\bmargins?\b", re.IGNORECASE)
_AMOUNT = r"(\d+(?:\.\d+)?|\.\d+|half(?: an?| of an?)?|a half|one half|a quarter(?: of an?)?|quarter|one|an?)"
_UNIT = r"(inch(?:es)?|in\b|\"|cm\b|centimet(?:er|re)s?|mm\b|millimet(?:er|re)s?)"
_MEASURE = re.compile(rf"(?<![\w.]){_AMOUNT}\s*-?\s*{_UNIT}", re.IGNORECASE)
# Where a part of the request about one thing ends and the next begins.
_CLAUSES = re.compile(r"[,;:]|\band\b|\bthen\b|\balso\b", re.IGNORECASE)
_SECTION = re.compile(
	r"\b(?:to|in|for|on|under|of)\s+(?:the\s+|my\s+|our\s+)?([a-z][a-z ]{2,40}?)\s+(?:section|page|list|entries|part|heading)\b",
	re.IGNORECASE)
_DOC_WORDS = (
	r"(?:documents?|docs?|papers?|essays?|reports?|resum(?:e|" + chr(0xe9) + r")s?|cvs?|letters?|thes[ie]s|dissertations?|manuscripts?|"
	r"articles?|assignments?|proposals?|flyers?|fliers?|brochures?|newsletters?|leaflets?|handouts?|posters?|memos?|word)")
_LAYOUT = re.compile(
	r"\blayouts?\b|\bfits?\b|\bfitting\b|\boverlap\w*\b|\btext ?box(?:es)?\b|\bhow many pages\b|\bpage count\b"
	r"|\bnumber of pages\b|\bspill\w*\b|\bruns? over\b|\b(?:one|single|second|extra|blank) page\b", re.IGNORECASE)
_ONE_PAGE = re.compile(
	r"\b(?:on|onto|to|in|into|within)\s+(?:a\s+|one\s+)?(?:single\s+)?(?:1\s+)?page\b|\bone page\b|\bsingle page\b"
	r"|\b(?:second|extra|blank) page\b|\bspill\w*\b|\bruns? over\b", re.IGNORECASE)
_OVERLAP = re.compile(r"\boverlap\w*\b|\btext ?box(?:es)?\b|\bon top of each other\b|\bcollid\w+\b", re.IGNORECASE)
_PAGES = re.compile(r"\bhow many pages\b|\bpage count\b|\bnumber of pages\b|\bhow long is\b", re.IGNORECASE)
_AMOUNTS = {"half": 0.5, "a half": 0.5, "one half": 0.5, "quarter": 0.25, "one": 1.0, "a": 1.0, "an": 1.0}
# Word's own number for "not one value": what it gives for the size of text in several sizes.
MIXED = 9999999
# The hanging indent both styles ask for a list of sources, in inches (read on both of Purdue's pages).
HANGING_USUAL = 0.5
# Said about a change that did not work, after its name.
NO_SUCH_FONT = "Word on this computer has no font of that name"
REFUSED = "Word refused it"
NOTHING_FOLLOWS = "nothing follows that heading"
TOO_LONG_WHY = "the document has more paragraphs than VisionClaw goes through one by one"


def _clean(text):
	return " ".join(str(text or "").split())


def measure(text):
	"""The first length a text names, in inches, or None: "0.5-inch", "half an inch", "1 inch", "2.5 cm"."""
	found = _MEASURE.search(text or "")
	if not found:
		return None
	amount, unit = found.group(1).lower(), found.group(2).lower()
	if amount.startswith("half") or amount in ("a half", "one half"):
		value = 0.5
	elif "quarter" in amount:
		value = 0.25
	elif amount in _AMOUNTS:
		value = _AMOUNTS[amount]
	else:
		value = float(amount)
	if unit.startswith(("cm", "centi")):
		value /= 2.54
	elif unit.startswith(("mm", "milli")):
		value /= 25.4
	return round(value, 3) if 0 < value <= 10 else None


def fontIn(text, fonts=()):
	"""The font a request names, written as Word writes it, or None. fonts: the names of Word's own fonts, where
	the caller has them. A font that is not one of the well-known ones counts only where the request says "font"."""
	low = _clean(text).lower()
	saysFont = bool(re.search(r"\b(?:fonts?|typefaces?)\b", low))
	known = {name.lower(): name for name in COMMON_FONTS}
	# Word's own spelling of a well-known font wins over this file's.
	other = {}
	for name in fonts or ():
		name = str(name)
		if name.lower() in known:
			known[name.lower()] = name
		elif len(name) >= 4:
			other[name.lower()] = name
	pools = [known] + ([other] if saysFont else [])
	for pool in pools:
		for key in sorted(pool, key=len, reverse=True):
			if re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", low):
				return pool[key]
	return None


def _sectionIn(clause):
	"""The heading words a clause names for a hanging indent, or None: "to the References section"."""
	low = clause.lower()
	for words in sorted(HEADINGS, key=len, reverse=True):
		if re.search(rf"\b{re.escape(words)}\b", low):
			return (words,)
	found = _SECTION.search(low)
	if found:
		words = found.group(1).strip()
		if words not in ("whole", "entire", "this", "that", "same", "last", "first", "next"):
			return (words,)
	return None


def wish(part, fonts=()):
	"""What the user's own words ask to be formatted, or None when they ask for nothing of the kind or only ask a
	question: {"style": APA7, MLA9 or None; "edition": the number of the edition they said, or None; "font";
	"size" in points; "spacing": SINGLE, ONE_AND_HALF or DOUBLE; "spaceAround": 0 when the space before and after
	paragraphs is to go; "margins", "firstLine", "hanging" in inches, or UNCLEAR when named without a length;
	"section": the heading words a hanging indent is for, or None; "align"; "scope": DOCUMENT or SELECTION;
	"wholeDocument"}. What the words say outright always comes before what a style asks (plan)."""
	text = _clean(part)
	if not text or _QUESTION.search(text):
		return None
	style = APA7 if _APA.search(text) else MLA9 if _MLA.search(text) else None
	edition = None
	said = _EDITION.search(text)
	if said and style:
		edition = int(next(group for group in said.groups() if group))
	found = {
		"style": style, "edition": edition, "font": fontIn(text, fonts), "size": None, "spacing": None, "spaceAround": None,
		"margins": None, "firstLine": None, "hanging": None, "section": None, "align": None}
	size = _SIZE.search(text)
	if size:
		points = float(size.group(1) or size.group(2))
		if 6 <= points <= 72:
			found["size"] = int(points) if points == int(points) else points
	if _HALF_SPACING.search(text):
		found["spacing"] = ONE_AND_HALF
	elif _DOUBLE_SPACING.search(text):
		found["spacing"] = DOUBLE
	elif _SINGLE_SPACING.search(text):
		found["spacing"] = SINGLE
	if _SPACE_AROUND.search(text):
		found["spaceAround"] = 0
	for align, pattern in _ALIGNS:
		if pattern.search(text):
			found["align"] = align
			break
	# A length belongs to the thing named in the same part of the sentence. "One and a half" is no "and" to split at.
	for clause in _CLAUSES.split(re.sub(r"\bone and a half\b", "1.5", text, flags=re.IGNORECASE)):
		if not clause or not clause.strip():
			continue
		length = measure(clause)
		if _HANGING.search(clause):
			# Named without a length, it is the half inch that APA and MLA both ask for a list of sources; plan says so.
			found["hanging"] = length if length is not None else HANGING_USUAL
			found["hangingAssumed"] = length is None and style is None
			found["section"] = _sectionIn(clause) or found["section"]
		elif _FIRST_LINE.search(clause):
			found["firstLine"] = length if length is not None else UNCLEAR
		elif _MARGINS.search(clause):
			found["margins"] = length if length is not None else UNCLEAR
	if not any(found[key] is not None for key in found if key not in ("edition", "section", "hangingAssumed")):
		return None
	found["scope"] = SELECTION if _SELECTION.search(text) else DOCUMENT
	found["wholeDocument"] = found["scope"] == DOCUMENT
	return found


def inches(value):
	"""A length in words: half an inch, 1 inch, 1.25 inches."""
	if abs(value - 0.5) < 0.001:
		return "half an inch"
	if abs(value - 0.25) < 0.001:
		return "a quarter of an inch"
	if abs(value - 1) < 0.001:
		return "1 inch"
	return f"{round(value, 2):g} inches"


def _sectionName(section):
	return " or ".join(words.title() for words in section)


_SPACING_WORDS = {SINGLE: "single", ONE_AND_HALF: "one and a half lines", DOUBLE: "double"}
_ALIGN_WORDS = {LEFT: "aligned at the left", CENTRE: "centred", RIGHT: "aligned at the right", JUSTIFY: "justified"}


def changeText(change):
	"""One change in a few words, for the question and for the answer."""
	what, value = change["what"], change["value"]
	if what == FONT:
		return f"the font: {value}"
	if what == SIZE:
		return f"the font size: {value:g} point"
	if what == SPACING:
		return f"the line spacing: {_SPACING_WORDS[value]}"
	if what == SPACE_AROUND:
		return "no extra space before or after paragraphs"
	if what == MARGINS:
		return f"the margins: {inches(value)} on every side"
	if what == ALIGN:
		return f"every paragraph {_ALIGN_WORDS[value]}"
	if what == FIRST_LINE:
		if change.get("selected"):
			return f"the first line of each selected paragraph indented by {inches(value)}"
		return f"the first line of each paragraph of body text indented by {inches(value)}"
	if change.get("selected") or not change.get("section"):
		return f"a hanging indent of {inches(value)} for the selected paragraphs"
	gap = ", with no extra space between them" if change.get("noGap") else ""
	return f"a hanging indent of {inches(value)} for the entries under {_sectionName(change['section'])}{gap}"


def plan(asked, now=None):
	"""What is to be changed, in order, from what the words ask and what their style asks:
	{"changes": [{"what", "value", "text", and for a hanging indent "section" and "noGap"}], "notes": sentences
	about what stays as it is, "unclear": the things named without a length}. now: {"font", "size"} of the text as
	it is, where the caller could read them: a font the style accepts is left alone."""
	style = STYLES.get(asked.get("style"))
	now = now or {}
	changes, notes, unclear = [], [], []
	selected = asked.get("scope") == SELECTION

	def add(what, value, **more):
		change = dict(what=what, value=value, **more)
		if selected and what in (FIRST_LINE, HANGING):
			change["selected"] = True
		change["text"] = changeText(change)
		changes.append(change)

	font, size = asked.get("font"), asked.get("size")
	if style:
		accepted = style["fonts"]
		current = (str(now.get("font") or "").lower(), now.get("size"))
		if font is None and size is None and accepted and any(
				current == (name.lower(), points) for name, points in accepted):
			notes.append(
				f"The font is {now['font']}, {now['size']:g} point, which {style['family']} accepts, so it stays as it is.")
		else:
			if font is None and size is None:
				font, size = style["font"], style["size"]
				if font is None and now.get("font"):
					notes.append(
						f"{style['family']} asks for a font that is easy to read, such as Times New Roman. The font's name was "
						f"left as it is, {now['font']}; name a font if you want another.")
				elif accepted:
					notes.append(
						f"{style['family']} accepts other fonts too: " + ", ".join(f"{name} {points} point" for name, points in accepted[1:]) + ".")
			elif size is None:
				# The size the style gives for the font the user named, where it names one.
				size = next((points for name, points in accepted or () if name.lower() == font.lower()), style["size"])
			if size is not None and now.get("size") == size and font is None:
				size = None
	if font is not None:
		add(FONT, font)
	if size is not None:
		add(SIZE, size)
	spacing = asked.get("spacing") or (style["spacing"] if style else None)
	if spacing:
		add(SPACING, spacing)
	if asked.get("spaceAround") is not None:
		add(SPACE_AROUND, 0)
	margins = asked.get("margins")
	if margins == UNCLEAR:
		unclear.append("the margins")
	elif margins is not None or style:
		add(MARGINS, margins if margins is not None else style["margins"])
	if asked.get("align"):
		add(ALIGN, asked["align"])
	firstLine = asked.get("firstLine")
	if firstLine == UNCLEAR:
		unclear.append("the first-line indent")
	elif firstLine is not None or (style and style["firstLine"] is not None):
		add(FIRST_LINE, firstLine if firstLine is not None else style["firstLine"])
	hanging = asked.get("hanging")
	if hanging == UNCLEAR:
		unclear.append("the hanging indent")
	elif hanging is not None or style:
		section = asked.get("section") or (style["headings"] if style else HEADINGS)
		add(HANGING, hanging if hanging is not None else style["hanging"], section=tuple(section),
			noGap=bool(style and style["entriesNoGap"]))
		if asked.get("hangingAssumed"):
			notes.append(
				"You gave no length for the hanging indent, so half an inch was used, which is what APA and MLA both ask "
				"for a list of sources.")
	if style and asked.get("edition") and asked["edition"] != style["edition"]:
		notes.append(
			f"You said the {ordinal(asked['edition'])} edition; VisionClaw knows what the {ordinal(style['edition'])} edition "
			"asks, and used that.")
	return {"changes": changes, "notes": notes, "unclear": unclear}


def changes(asked, now=None):
	"""The ordered list of changes for a wish (plan has the notes too)."""
	return plan(asked, now)["changes"]


def ordinal(number):
	last = number % 100
	ending = "th" if 10 < last < 14 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
	return f"{number}{ending}"


def many(count, one, more=None):
	return f"{count} {one if count == 1 else (more or one + 's')}"


def _listed(parts):
	parts = [part for part in parts if part]
	if len(parts) < 2:
		return "".join(parts)
	return "; ".join(parts[:-1]) + "; and " + parts[-1]


# --- What the user is asked and told about formatting ---

UNDO = "In Word, Control+Z undoes all of it in one step."
UNDO_STEPS = "In Word, Control+Z undoes it, one change at a time."
NOT_A_DOCUMENT = (
	"The program in front is not Microsoft Word or Google Docs, so there is no document here to format. Put the "
	"document in front and ask again.")
NO_INTERFACE = (
	"Word did not let VisionClaw reach the document. This happens while a dialog of Word is open, while the document "
	"is shown in Protected View, or when the focus is not in the document. Press Escape, move into the text, and ask again.")
READ_ONLY = (
	"This document is read-only, so nothing was changed. Save it under another name, or choose Enable Editing if Word "
	"offers it, and ask again.")
PROTECTED = "This document is protected against changes, so nothing was changed. Its owner has to take the protection off."
NOTHING_ASKED = (
	"The request does not say how to format the document. Name a style, APA or MLA, or say what to set: the font, "
	"the font size, the line spacing, the margins, a first-line indent or a hanging indent.")
NO_SELECTION = "Nothing is selected in the document, so there is nothing to format. Select the text first, or ask for the whole document."
STOPPED = "You stopped it. What had been changed up to then stays changed; in Word, Control+Z undoes it."
TOO_LONG = (
	"The document has more paragraphs than VisionClaw goes through one by one, so what needs each paragraph looked "
	"at was not done.")


def unclearText(unclear):
	"""What was named without a length."""
	return (
		"You named " + " and ".join(unclear) + " without saying how much, so that was left as it is. Say a length, "
		"such as half an inch or 1 inch.")


def noFont(name):
	return f"Word on this computer has no font called {name}, so the font was left as it is."


def question(planned, title, asked):
	"""The question before anything is changed: every change is named."""
	style = STYLES.get(asked.get("style"))
	where = "the selected text" if asked.get("scope") == SELECTION else (f"the document {title}" if title else "this document")
	lead = f"Format {where} in {style['name']} style?" if style else f"Format {where}?"
	return f"{lead} This will set: {_listed(change['text'] for change in planned['changes'])}. {UNDO}"


def resultText(result):
	"""One change as it went: {"change", "ok", and what doctools found: "why", "count", "skipped", "heading",
	"entries", "spaceLeft"}."""
	change = result["change"]
	what = change["what"]
	if not result.get("ok"):
		why = result.get("why") or "Word refused it"
		return f"Not done, {change['text']}: {why}."
	if what == FIRST_LINE:
		said = f"{change['text']}: {many(result.get('count', 0), 'paragraph')}"
		if result.get("skipped"):
			one = result["skipped"] == 1
			said += (
				f"; {many(result['skipped'], 'short line')} that {'looks' if one else 'look'} like a heading, a title, a "
				f"name or a date {'was left as it is' if one else 'were left as they are'}")
		return said
	if what == HANGING and not change.get("selected"):
		return (
			f"{change['text']}: {many(result.get('entries', 0), 'entry', 'entries')} after the heading "
			f"{result.get('heading') or _sectionName(change['section'])}")
	return change["text"]


def noSection(section):
	"""Why a hanging indent was not applied: the heading was not found."""
	return (
		f"no paragraph that says only {_sectionName(section)} was found, so VisionClaw cannot tell where that list "
		"begins. Select the entries of the list and ask for a hanging indent for the selected text instead")


def done(results, planned, asked, title, undo=True, spaceLeft=None):
	"""What was done, in the order it was asked: what changed, what did not and why, what stays as it is, what the
	style also asks, and how to undo."""
	style = STYLES.get(asked.get("style"))
	where = "the selected text" if asked.get("scope") == SELECTION else (title or "the document")
	went = [resultText(result) for result in results if result.get("ok")]
	failed = [resultText(result) for result in results if not result.get("ok")]
	lines = []
	if went:
		lead = f"Formatted {where} in {style['name']} style." if style else f"Formatted {where}."
		lines.append(f"{lead} Set: {_listed(went)}.")
	else:
		lines.append(f"Nothing was changed in {where}.")
	lines.extend(failed)
	lines.extend(planned["notes"])
	if planned["unclear"]:
		lines.append(unclearText(planned["unclear"]))
	if spaceLeft:
		lines.append(
			"Paragraphs in this document also have extra space before or after them, which was left as it is. To take "
			"it out, say: remove the space before and after paragraphs.")
	if style and went:
		lines.append(
			f"{style['family']} also asks for these, which VisionClaw did not do: " + "; ".join(style["alsoAsks"]) + ".")
		if style["notRead"] and not any(result["change"]["what"] == FIRST_LINE for result in results):
			lines.append(style["notRead"])
	if went:
		lines.append(UNDO if undo else UNDO_STEPS)
	return "\n".join(lines)


# --- Google Docs: no interface like Word's, so the user is told the keys ---

DOCS_KEYS = {
	LEFT: "Control+Shift+L", CENTRE: "Control+Shift+E", RIGHT: "Control+Shift+R", JUSTIFY: "Control+Shift+J"}
DOCS_NOT_TRIED = (
	"VisionClaw does not type into Google Docs' tool finder by itself yet: that could not be tried in a real "
	"browser, and a key pressed in the wrong place would type into your document.")
DOCS_LAYOUT = (
	"Google Docs does not give a program the number of pages or the places of text boxes the way Word does, so "
	"VisionClaw cannot measure the layout there. Two ways that work: download the document as a Word file, open it "
	"in Word and ask again; or ask VisionClaw to describe the window, and the model that sees pictures says what the "
	"page shows, which is a model's reading and not a measurement.")


def docsPlan(asked, now=None):
	"""For a document in Google Docs: nothing is changed; the user is told which of the things asked for have a
	key of Google Docs' own, and how to find the others in its tool finder. From Google's own page of shortcuts."""
	planned = plan(asked, now)
	keyed, searched, sized = [], [], ""
	for change in planned["changes"]:
		what, value = change["what"], change["value"]
		if what == ALIGN:
			keyed.append(f"{change['text']}: {DOCS_KEYS[value]}")
		elif what == SIZE:
			sized = (
				f"For {change['text']}, Google Docs has no key that sets a size by its number: Control+Shift+period makes "
				"the selected text one step larger, Control+Shift+comma one step smaller.")
		else:
			searched.append(change["text"])
	lines = [
		"Google Docs has no interface for programs like the one Word has, so VisionClaw changed nothing. This is "
		"how to do it with Google Docs' own keys."]
	if asked.get("scope") != SELECTION:
		lines.append("First press Control+A to select the whole document.")
	if keyed:
		lines.append("With a key: " + "; ".join(keyed) + ".")
	if sized:
		lines.append(sized)
	if searched:
		lines.append(
			"For the rest, Google Docs lists no key: " + "; ".join(searched) + ". Press Alt+/ to open its tool finder, "
			"type a few words for what you want, such as the font's name, line spacing or indentation, then choose from "
			"what it finds with the arrow keys and press Enter.")
	style = STYLES.get(asked.get("style"))
	if style:
		lines.append(f"{style['family']} also asks for: " + "; ".join(style["alsoAsks"]) + ".")
	if planned["unclear"]:
		lines.append(unclearText(planned["unclear"]))
	lines.append(DOCS_NOT_TRIED)
	return "\n".join(lines)


# --- The layout: pages, what is on the last page, what overlaps ---

def layoutWish(part):
	"""Whether the words ask about a document's layout, and what: {"onePage", "overlap", "pages"}, or None. The
	words must speak of a document, a page count or fitting on a page; "how is this page laid out" is about a web
	page and is none of this."""
	text = _clean(part)
	if not text or not _LAYOUT.search(text):
		return None
	onePage, overlap, pages = bool(_ONE_PAGE.search(text)), bool(_OVERLAP.search(text)), bool(_PAGES.search(text))
	document = bool(re.search(rf"\b{_DOC_WORDS}\b", text, re.IGNORECASE))
	# Text boxes that overlap are a thing of a document, whatever the document is called.
	boxes = bool(re.search(r"\btext ?box(?:es)?\b", text, re.IGNORECASE) and re.search(r"\boverlap\w*\b|\bon top of\b|\bcollid\w+\b", text, re.IGNORECASE))
	if not (document or pages or boxes or (onePage and re.search(r"\bfits?\b|\bfitting\b", text, re.IGNORECASE))):
		return None
	if re.search(r"\b(?:web ?page|website|site|browser|window|screen|keyboard)\b", text, re.IGNORECASE) and not document:
		return None
	return {"onePage": onePage, "overlap": overlap, "pages": pages}


def _kind(shape):
	return shape.get("kind") or "shape"


def _named(shape):
	name = shape.get("name") or ""
	return f"{_kind(shape)} {name}".strip() if not name.lower().startswith(_kind(shape)) else name


def layoutText(facts, asks=None):
	"""A document's layout in plain words, from Word's own numbers (doctools.layoutOf): {"title", "pages",
	"lastLines": lines of text on the last page or None, "tables": how many, "wide": [{"number", "over" in
	inches}], "shapes": [{"name", "kind", "page", "box" or None, "outside"}], "overlaps": [(name, name, page)],
	"unplaced": how many shapes Word gave no place for}. Whether it fits on one page is said first."""
	asks = asks or {}
	title = facts.get("title") or "The document"
	pages = facts.get("pages")
	lines = []
	if not pages or pages < 1:
		lines.append(f"Word did not say how many pages {title} has.")
	elif pages == 1:
		lines.append(f"{'Yes, it fits on one page: ' if asks.get('onePage') else ''}{title} is 1 page long.")
	else:
		lead = "No, it does not fit on one page: " if asks.get("onePage") else ""
		said = f"{lead}{title} is {pages} pages long."
		last = facts.get("lastLines")
		if last is not None and last > 0:
			said += f" The last page holds {many(last, 'line')} of text."
			if last <= 4:
				said += (
					f" So only a little runs over onto page {pages}: slightly smaller margins, a smaller font size or a few "
					"words less would bring it back by a page.")
		lines.append(said)
	shapes = facts.get("shapes") or []
	overlaps = facts.get("overlaps") or []
	outside = [shape for shape in shapes if shape.get("outside")]
	boxes = sum(1 for shape in shapes if _kind(shape) == "text box")
	if overlaps:
		pairs = "; ".join(f"{first} and {second} on page {page}" if page else f"{first} and {second}" for first, second, page in overlaps[:5])
		more = f", and {len(overlaps) - 5} more" if len(overlaps) > 5 else ""
		lines.append(f"These take up some of the same space on the page, so one covers part of the other: {pairs}{more}.")
	elif shapes:
		lines.append(
			f"Nothing overlaps: the document has {many(len(shapes), 'floating thing')} "
			f"({many(boxes, 'text box', 'text boxes')}, the rest pictures or shapes), and no two of them share any space.")
	else:
		lines.append("The document has no text boxes, floating pictures or shapes, so nothing can overlap.")
	if outside:
		lines.append(
			"Reaching beyond the edge of the page, so part would be cut off in print: "
			+ ", ".join(f"{_named(shape)} on page {shape['page']}" if shape.get("page") else _named(shape) for shape in outside[:5]) + ".")
	wide = facts.get("wide") or []
	if wide:
		lines.append(
			"Wider than the space between the margins: " + ", ".join(
				f"table {table['number']}, by about {inches(table['over'])}" for table in wide[:5]) + ".")
	elif facts.get("tables"):
		lines.append(f"{many(facts['tables'], 'table')}: none is wider than the space between the margins.")
	if facts.get("unplaced"):
		lines.append(
			f"Word gave no place on the page for {many(facts['unplaced'], 'floating thing')}, so "
			f"{'it was' if facts['unplaced'] == 1 else 'they were'} not compared with the others.")
	if facts.get("cut"):
		lines.append("The document has more floating things or tables than VisionClaw compares; only the first were looked at.")
	lines.append(
		"This comes from Word's own numbers for the document as it would be printed, not from a picture. Text that "
		"is too long for its own text box is not something Word reports this way.")
	return "\n".join(lines)
