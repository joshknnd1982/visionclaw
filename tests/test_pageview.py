# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Exploring a web page and finding what stops a form, with plain Python.

Part 1 checks the plain code (claw/pageview.py) on pages read through the stand-in for NVDA's browse mode
(pagestandin.py): what a page has, where its main part begins, which of NVDA's keys are named, and which fields
and messages are found to be in the way of a form.
Part 2 runs the two tools (pagetools.py) against the same stand-in, with stand-ins for NVDA's modules.
The stand-in gives what NVDA 2026.3.1's source says NVDA gives. Whether a real browser marks its fields the
same way is only shown by a run inside NVDA: this has not been done.
"""
import builtins
import enum
import importlib
import os
import re
import sys
import types

import harness  # noqa: F401
import pagestandin
from visionClaw.claw import pageview, tools

# The kinds of control and the states these pages need, by NVDA's own names. The stand-in's own lists are
# shorter; they are widened here, for this test only.
ROLES = (
	"DOCUMENT BUTTON LINK HEADING ARTICLE SECTION GRAPHIC EDITABLETEXT STATICTEXT VIDEO GROUPING PANE WINDOW "
	"PASSWORDEDIT COMBOBOX CHECKBOX RADIOBUTTON SWITCH SPINBUTTON SLIDER DATEEDITOR TABLE LIST LISTITEM ALERT "
	"LANDMARK REGION PARAGRAPH TOGGLEBUTTON MENUBUTTON SPLITBUTTON DROPDOWNBUTTON FORM")
# Read from controlTypes.State of the NVDA installed on this computer (2026.3.1) on 2026-11-18.
NVDA_STATES = (
	"AUTOCOMPLETE BUSY CHECKABLE CHECKED CLICKABLE COLLAPSED CROPPED DEFUNCT DRAGGABLE DRAGGING DROPTARGET EDITABLE "
	"EXPANDED FOCUSABLE FOCUSED HALFCHECKED HALF_PRESSED HASCOMMENT HASFORMULA HASLONGDESC HASNOTE HASPOPUP "
	"HASPOPUP_DIALOG HASPOPUP_GRID HASPOPUP_LIST HASPOPUP_TREE HAS_ARIA_DETAILS ICONIFIED INDETERMINATE INTERNAL_LINK "
	"INVALID_ENTRY INVISIBLE LINKED MODAL MULTILINE MULTISELECTABLE OBSCURED OFFSCREEN OVERFLOWING PINNED PRESSED "
	"PROTECTED READONLY REQUIRED SELECTABLE SELECTED SORTED SORTED_ASCENDING SORTED_DESCENDING UNAVAILABLE UNLOCKED "
	"VISITED").split()
pagestandin.Role = enum.Enum("Role", ROLES)
pagestandin.State = enum.Enum("State", " ".join(NVDA_STATES))
El, Role = pagestandin.El, pagestandin.Role

# ---------------------------------------------------------------------------------------------------------
# Stand-ins for the NVDA modules the tools import.
# ---------------------------------------------------------------------------------------------------------

spoken, logged = [], []
names = ("api controlTypes globalPluginHandler speech textInfos textInfos.offsets ui wx logHandler virtualBuffers "
	"browseMode addonHandler config").split()
modules = {name: types.ModuleType(name) for name in names}
modules["controlTypes"].OutputReason = types.SimpleNamespace(QUICKNAV="quicknav", FOCUS="focus")
modules["controlTypes"].Role = Role
modules["globalPluginHandler"].GlobalPlugin = type("GlobalPlugin", (), {})
textInfos = modules["textInfos"]
textInfos.POSITION_ALL, textInfos.POSITION_FIRST, textInfos.POSITION_CARET, textInfos.UNIT_LINE = "all", "first", "caret", "line"
textInfos.offsets = modules["textInfos.offsets"]
textInfos.offsets.Offsets = lambda start, end: types.SimpleNamespace(start=start, end=end)
modules["ui"].message = spoken.append
modules["logHandler"].log = types.SimpleNamespace(
	debug=lambda *a, **k: None, debugWarning=lambda *a, **k: logged.append(a[0]), info=lambda *a, **k: None,
	warning=lambda *a, **k: logged.append(a[0]), error=lambda *a, **k: logged.append("ERROR " + str(a[0])))
modules["virtualBuffers"].VirtualBuffer = type("VirtualBuffer", (), {})
modules["browseMode"].reportPassThrough = lambda document: spoken.append("browse mode")
modules["addonHandler"].initTranslation = lambda: None
modules["config"].conf = {"visionClaw": {"useOcr": True}}
sys.modules.update(modules)
builtins._ = lambda text: text
# The add-on's own reading of text in a picture needs Windows' recognizer; a stand-in gives the lines.
pictureLines, grabbed = [], []
ocrModule = types.ModuleType("visionClaw.ocr")
ocrModule.recognize = lambda image: list(pictureLines)
ocrModule.rowsText = lambda lines: "\n".join(lines)
sys.modules["visionClaw.ocr"] = ocrModule

fixruntime = importlib.import_module("visionClaw.fixruntime")
pagetools = importlib.import_module("visionClaw.pagetools")
audit = importlib.import_module("visionClaw.claw.audit")


class Info(pagestandin.Info):
	"""The stand-in's stretch of a page, with the landmark put in the way NVDA's own code for browsers does it
	(virtualBuffers/gecko_ia2.py, _normalizeControlField, read on 2026-11-18)."""

	def _normalizeControlField(self, attrs):
		attrs = super()._normalizeControlField(attrs)
		xmlRoles = str(attrs.get("IAccessible2::attribute_xml-roles", "")).split(" ")
		landmark = next((role for role in xmlRoles if role in pageview.LANDMARKS), None)
		if landmark:
			attrs["landmark"] = landmark
		return attrs


Document = pagestandin.documentClass(modules["virtualBuffers"].VirtualBuffer)
Document.TextInfo = Info


def nodesOf(document, chunk=100000):
	first, last = fixruntime.pageRange(document)
	return audit.joinChunks([fixruntime.pageChunk(document, at, min(last, at + chunk)) for at in range(first, last, chunk)])


def page(*content, address="https://www.example-shop.com/order", title="Order form"):
	return Document(El("DOCUMENT", *content), address, title)


# ---------------------------------------------------------------------------------------------------------
# Part 1: plain code
# ---------------------------------------------------------------------------------------------------------

# 1. Every kind of control and every state this code names is one NVDA has, and its landmarks are NVDA's.
here = os.path.dirname(os.path.abspath(__file__))
nvdaRoles = re.search(r'NVDA_ROLES = \((.*?)\)\.split\(\)', open(os.path.join(here, "test_working.py"), encoding="utf-8").read(), re.S)
nvdaRoles = set(re.findall(r"[A-Z_0-9]{3,}", nvdaRoles.group(1)))
assert len(nvdaRoles) == 156, len(nvdaRoles)
used = set(pageview.FIELDS) | set(pageview.TYPED) | set(pageview.CHECKED) | set(pageview.BUTTONS) | {
	"LINK", "TABLE", "LIST", "GRAPHIC", "ALERT", "GROUPING", "HEADING", "RADIOBUTTON", "COMBOBOX"}
assert used <= nvdaRoles, used - nvdaRoles
source = open(os.path.join(harness.PLUGIN_DIR, "claw", "pageview.py"), encoding="utf-8").read()
for state in set(re.findall(r'"([A-Z_]{5,})" (?:not )?in (?:states|_states)', source)):
	assert state in NVDA_STATES, state
assert {"REQUIRED", "INVALID_ENTRY", "CHECKED", "UNAVAILABLE", "READONLY", "INVISIBLE"} <= set(NVDA_STATES)
assert pageview.LANDMARKS["contentinfo"] == "content info" and len(pageview.LANDMARKS) == 8
assert pageview.FITS < tools.RESULT_CHARS

# 2. A well-built page: what it has, its landmarks in order, where the main part begins, and the keys.
shop = page(
	El("SECTION", El("LINK", "Example Shop\n"), El("BUTTON", "Basket\n"), xml="banner"),
	El("SECTION", *[El("LINK", f"{name}\n") for name in ("Home", "Products", "Offers", "Help")], xml="navigation", name="Main menu"),
	El("SECTION",
		El("HEADING", "Winter boots\n", level="1"),
		"Warm boots for cold days.\n",
		*[item for n in range(1, 5) for item in (El("HEADING", f"Boot number {n}\n", level="2"), El("LINK", f"See boot {n}\n"))],
		El("HEADING", "Sizes\n", level="3"),
		El("TABLE", "Size 40 41 42\n"),
		El("LIST", El("LISTITEM", "Free delivery\n"), El("LISTITEM", "Thirty days to send back\n")),
		El("GRAPHIC", name="A brown boot"),
		El("EDITABLETEXT", name="Search the shop"), El("COMBOBOX", "Brown", name="Colour"),
		El("BUTTON", "Search\n"), El("BUTTON", "Hidden\n", states=("INVISIBLE",)),
		xml="main"),
	El("SECTION", El("LINK", "Contact\n"), xml="contentinfo"),
	title="Winter boots")
text = pageview.explore(nodesOf(shop), title="Winter boots", site="example-shop.com")
lines = text.splitlines()
assert lines[0] == (
	"The web page Winter boots on example-shop.com has 6 headings, 4 landmarks, 10 links, 2 buttons, 2 form fields, "
	"1 table, 1 list and 1 picture."), lines[0]
assert lines[1] == "Landmarks in order: banner, with 1 link; navigation, Main menu, with 4 links; main, with 4 links; content info, with 1 link.", lines[1]
assert lines[2] == "The main landmark begins with the heading at level 1, Winter boots.", lines[2]
assert lines[3] == "Headings: 1 at level 1, 4 at level 2 and 1 at level 3.", lines[3]
assert lines[4] == "The first headings: Winter boots; Boot number 1; Boot number 2; Boot number 3; Boot number 4; Sizes.", lines[4]
assert lines[5] == "The navigation landmark Main menu has these links: Home, Products, Offers, Help.", lines[5]
assert lines[6] == "Form fields: Search the shop, edit field; Colour, combo box.", lines[6]
assert lines[7] == "How to move on this page:"
moving = lines[8:]
assert moving[0] == "The quickest way to the main part: press 1, which moves to the heading at level 1."
assert "H moves to the next heading, Shift+H to the one before." in moving
assert "Most headings, 4 of them, are at level 2: 2 moves between just these." in moving
assert "D moves to the next landmark, Shift+D to the one before." in moving
assert any(line.startswith("F moves to the next form field.") for line in moving)
assert any(line.startswith("T moves to the next table.") and "Control+Alt+Arrow keys" in line for line in moving)
assert "L moves to the next list, I to the next list item." in moving
assert moving[-1].startswith("NVDA+F7 lists the links, headings, form fields, buttons and landmarks")
assert not any(line.startswith("P moves") for line in moving), "a page with headings needs no paragraph key"
assert "Hidden" not in text and len(text) <= pageview.FITS, len(text)
# Read in small stretches, the page is the same page.
assert pageview.explore(nodesOf(shop, chunk=41), title="Winter boots", site="example-shop.com") == text

# 3. The keys named are NVDA's own. Where NVDA is installed on this computer, its user guide is asked.
guide = r"C:\Program Files\NVDA\documentation\en\userGuide.html"
if os.path.isfile(guide):
	import html
	said = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", open(guide, encoding="utf-8").read())).split())
	for needed in ("h: heading", "l: list", "i: list item", "t: table", "f: form field", "d: landmark", "text paragraph",
			"Browse mode elements list NVDA+f7", "control+alt+rightArrow", "1 to 9: headings at levels 1 to 9",
			"press enter or space to switch to focus mode", "Pressing escape will switch back to browse mode"):
		assert needed in said, needed
	guideChecked = True
else:
	guideChecked = False

# 4. A page with nothing to move by says so, and names the key that still helps.
bare = page("Only words here.\n", El("PARAGRAPH", "And more words.\n"), title="Notes")
text = pageview.explore(nodesOf(bare), title="Notes")
assert text.startswith("The web page Notes has no headings, landmarks, links, buttons or form fields") and "press P" in text

# 5. Links only: no heading key and no landmark key is named, the paragraph key is.
linksOnly = page(*[El("LINK", f"Story {n}\n") for n in range(1, 4)], title="News")
text = pageview.explore(nodesOf(linksOnly), title="News")
assert "has 3 links." in text and "The page marks no main landmark and has no headings." in text
assert "P moves to the next paragraph" in text and "H moves" not in text and "D moves" not in text

# 6. No main landmark, but a heading at level 1; and a main landmark without a heading at level 1.
text = pageview.explore(nodesOf(page(El("HEADING", "Welcome\n", level="1"), El("HEADING", "News\n", level="2"))))
assert text.startswith("This web page has 2 headings.") and "The page marks no main landmark. Its heading at level 1 is Welcome." in text
assert "press 1," in text
text = pageview.explore(nodesOf(page(El("SECTION", El("HEADING", "Results\n", level="2"), xml="main"))))
assert "The main landmark begins with the heading at level 2, Results." in text
assert "press D until NVDA says main landmark" in text and "press 1," not in text

# 7. A form with three fields and nothing else is called a form, and F comes first.
text = pageview.explore(nodesOf(page(*[El("EDITABLETEXT", name=name) for name in ("First name", "Last name", "Email")])))
assert "This page is mostly a form: press F to move to its first field." in text

# 8. A very long page is shortened by plain code, the lists first; the keys at the end stay.
long = page(
	El("SECTION", *[El("LINK", f"A fairly long name of a link in the menu, number {n}\n") for n in range(30)], xml="navigation"),
	El("SECTION", *[El("HEADING", f"A heading with a good many words in it to fill the line, number {n}\n", level="2") for n in range(40)],
		*[El("EDITABLETEXT", name=f"A field with a long label that goes on for a while, number {n}", states=("REQUIRED",)) for n in range(20)],
		El("TABLE", "x"), El("LIST", "y"), xml="main"))
text = pageview.explore(nodesOf(long), title="A very long title of a page " * 2, site="example.com")
assert len(text) <= pageview.FITS, len(text)
assert text.splitlines()[-1].startswith("NVDA+F7") and "How to move on this page:" in text

# 9. What stops a form: marked fields, required and empty ones, and the page's messages, each with its field.
form = page(
	El("SECTION", "Please correct the errors below.\n", xml="alert"),
	El("EDITABLETEXT", "Josh", name="First name", states=("REQUIRED",)),
	El("EDITABLETEXT", "josh at example", name="Email", states=("REQUIRED", "INVALID_ENTRY")),
	El("SECTION", "Enter an email address with an @ sign.\n", cls="field-error"),
	El("PASSWORDEDIT", name="Password", states=("REQUIRED",)),
	El("EDITABLETEXT", name="Middle name"),
	El("COMBOBOX", "Select a country", name="Country", states=("REQUIRED",)),
	El("COMBOBOX", "Blue", name="Colour", states=("REQUIRED",)),
	El("GROUPING",
		El("RADIOBUTTON", name="By post", states=("REQUIRED",)), El("RADIOBUTTON", name="By courier", states=("REQUIRED",)),
		name="Delivery"),
	El("GROUPING",
		El("RADIOBUTTON", name="Card", states=("REQUIRED",)), El("RADIOBUTTON", name="Invoice", states=("REQUIRED", "CHECKED")),
		name="Payment"),
	El("SECTION", El("EDITABLETEXT", "12", name="Card number"), cls="form-group has-error"),
	El("EDITABLETEXT", name="Voucher", states=("REQUIRED", "UNAVAILABLE")),
	El("EDITABLETEXT", name="Customer number", states=("REQUIRED", "READONLY")),
	El("SECTION", "An old message nobody sees.\n", cls="error", states=("INVISIBLE",)),
	El("CHECKBOX", name="I agree to the terms", states=("REQUIRED",)),
	El("CHECKBOX", name="Send me news"),
	El("SWITCH", name="Remember me", states=("REQUIRED", "CHECKED")),
	El("BUTTON", "Send\n"))
nodes = nodesOf(form)
found = pageview.trouble(nodes)
assert [item["text"] for item in found.items] == [
	"Email, edit field, required", "Password, password field, required", "Country, combo box, required",
	"By post, radio button, required", "Card number, edit field", "I agree to the terms, checkbox, required"], [item["text"] for item in found.items]
assert found.items[0]["why"] == ["is marked as not valid"] and found.items[0]["says"] == ["Enter an email address with an @ sign."]
assert found.items[1]["why"] == ["must be filled in and is empty"]
assert found.items[2]["why"] == ["must have a choice and none seems to be made"]
assert found.items[3]["why"] == ["one of these radio buttons must be chosen and none is"]
assert found.items[4]["why"] == ["is marked by the page as wrong"]
assert found.items[5]["why"] == ["must be checked and is not"]
assert found.notes == ["Please correct the errors below."], found.notes
assert found.first["name"] == "Email" and found.fields == 14, found.fields
text = pageview.troubleText(found, moved=True)
lines = text.splitlines()
assert lines[0] == "6 fields may be stopping this form."
assert lines[1] == "1. Email, edit field, required: is marked as not valid. The page says: Enter an email address with an @ sign."
assert lines[2] == "2. Password, password field, required: must be filled in and is empty."
assert lines[6] == "6. I agree to the terms, checkbox, required: must be checked and is not."
assert lines[7] == "The page also says: Please correct the errors below."
assert lines[8] == "NVDA's reading position is now on the first of them, Email. Press Enter to go into it, and Escape to come back to reading."
assert pageview.troubleText(found).splitlines()[-1] == "Press F to move from field to field, Shift+F to move back."
assert len(text) <= pageview.FITS
# The same form read in small stretches gives the same findings.
assert pageview.troubleText(pageview.trouble(nodesOf(form, chunk=53)), moved=True) == text

# 10. A message stands with the field before it; one above a field, without being an alert, with that field;
# one far from every field belongs to the whole form. A box marked as wrong around two fields marks neither.
near = page(
	El("SECTION", "Too short.\n", cls="invalid-feedback"),
	El("EDITABLETEXT", "ab", name="User name"),
	"A long stretch of other words. " * 12,
	El("SECTION", El("EDITABLETEXT", "x", name="Street"), El("EDITABLETEXT", "y", name="Town"), cls="has-error"),
	"More words that have nothing to do with it. " * 8,
	El("SECTION", "The form could not be sent.\n", cls="error"))
found = pageview.trouble(nodesOf(near))
assert [(item["text"], item["why"], item["says"]) for item in found.items] == [("User name, edit field", [], ["Too short."])], found.items
assert found.notes == ["The form could not be sent."]
assert pageview.troubleText(found).splitlines()[0:2] == ["1 field may be stopping this form.", "1. User name, edit field. The page says: Too short."]
# A message inside a message is said once, the inner one.
nested = page(El("EDITABLETEXT", "1", name="Age"), El("SECTION", El("SECTION", "Enter your age in years.\n", cls="error"), cls="errors"))
assert pageview.trouble(nodesOf(nested)).items[0]["says"] == ["Enter your age in years."]

# 11. Nothing found: said plainly, with how many fields were looked at; lines from the picture where there are any.
fine = page(El("EDITABLETEXT", "Josh", name="Name", states=("REQUIRED",)), El("CHECKBOX", name="Agree", states=("REQUIRED", "CHECKED")))
found = pageview.trouble(nodesOf(fine))
assert not found.items and not found.notes and found.first is None
text = pageview.troubleText(found)
assert text.startswith("Looked at the 2 form fields of this page. None is marked as not valid or as required and empty")
assert "Ask VisionClaw to describe the window" in text
drawn = pageview.errorLines(["Sign in", "Password must contain a number", "Email", "This field is required", "Password must contain a number", "ok"])
assert drawn == ["Password must contain a number", "This field is required"], drawn
text = pageview.troubleText(found, drawn=drawn)
assert "In the picture of the page, these lines may say why: Password must contain a number. This field is required." in text
assert "describe the window" not in text
assert pageview.errorLines(["Terrorism in the news", "A required taste"]) == ["A required taste"]  # whole words only
assert pageview.troubleText(pageview.trouble(nodesOf(bare))).startswith("This page has no form fields that NVDA can read")

# 12. Many fields in trouble: as many as fit are said, and how many more there are.
many = page(*[El("EDITABLETEXT", name=f"A required field with quite a long label, the one with number {n}", states=("REQUIRED",)) for n in range(30)])
text = pageview.troubleText(pageview.trouble(nodesOf(many)), moved=True)
assert text.startswith("30 fields may be stopping this form.") and "And 22 more; press F to move from field to field." in text
assert len(text) <= pageview.FITS, len(text)

# ---------------------------------------------------------------------------------------------------------
# Part 2: the tools
# ---------------------------------------------------------------------------------------------------------

made = {}


def add(name, description, fn, fields=None, **options):
	made[name] = types.SimpleNamespace(fn=fn, description=description, fields=fields or {}, options=options)


class Task:
	checks = 0

	def check(self):
		Task.checks += 1


plugin = types.SimpleNamespace(_grab=lambda box: grabbed.append(box) or "picture")
pagetools.register(add, plugin, lambda description, **extra: dict(extra, type="string", description=description), lambda fn, *args: fn(*args))
assert set(made) == {"explore_page", "form_trouble"}
for tool in made.values():
	# Both only find things out, say their result as it is, and need nothing from a model.
	assert tool.options["looks"] and tool.options["tell"] == tools.VERBATIM and not tool.fields and not tool.options.get("changes")

focus = types.SimpleNamespace(treeInterceptor=None)
modules["api"].getFocusObject = lambda: focus

# 13. Not in a web page: both say so in a way that leads on.
for name in made:
	try:
		made[name].fn(Task())
		raise AssertionError("should have been refused")
	except tools.ToolError as e:
		assert "not in a web page" in str(e)

# 14. Exploring the page the user is in, read a stretch at a time, with the request's stop looked at.
focus.treeInterceptor = shop
pagetools.PAGE_CHUNK = 60
text = made["explore_page"].fn(Task())
assert text.startswith("The web page Winter boots on example-shop.com has 6 headings, 4 landmarks, 10 links")
assert Task.checks > 3 and shop.caret == 0, "exploring moves nothing"

# 15. The form: what is wrong is said, and NVDA's reading position is on the first field in trouble. A page
# that was in focus mode is put back into browse mode, and that is announced.
focus.treeInterceptor = form
form.passThrough = True
text = made["form_trouble"].fn(Task())
email = next(el for el in form.root.walk() if el.name == "Email")
assert form.caret == email.start and form.passThrough is False and spoken == ["browse mode"], (form.caret, spoken)
assert "NVDA's reading position is now on the first of them, Email." in text and not grabbed, "no picture is needed when the page says it"

# 16. Nothing marked: the text in the page's picture is read for what is wrong, unless reading pictures is off.
focus.treeInterceptor = fine
pictureLines[:] = ["Welcome back", "Your password is incorrect"]
text = made["form_trouble"].fn(Task())
assert "these lines may say why: Your password is incorrect." in text and grabbed == [(0, 0, 800, 600)] and fine.caret == 0
modules["config"].conf["visionClaw"]["useOcr"] = False
assert "describe the window" in made["form_trouble"].fn(Task()) and len(grabbed) == 1
modules["config"].conf["visionClaw"]["useOcr"] = True

# 17. A picture that cannot be read, and a position that cannot be moved, are no fault: the answer still comes.
ocrModule.recognize = lambda image: (_ for _ in ()).throw(RuntimeError("no recognizer"))
assert "describe the window" in made["form_trouble"].fn(Task())
focus.treeInterceptor = form
form._set_selection = lambda info, reason=None: (_ for _ in ()).throw(RuntimeError("cannot move"))
text = made["form_trouble"].fn(Task())
assert text.startswith("6 fields may be stopping this form.") and text.splitlines()[-1].startswith("Press F to move")
assert any("could not be read" in line for line in logged) and any("could not be put" in line for line in logged)

# 18. The gist of a page, word for word: each heading with the first sentence under it. Menus, which are rows of
# short lines without a sentence, are left out; nothing is rephrased; a page without sentences gives nothing.
shopText = (
	"From the web page Example Shop:\nExample Shop\nWelcome to our shop. We sell garden tools.\nRefund policy\n"
	"You can return any product within 30 days for a full refund.\nOpening hours\nWe are open Monday to Friday from nine to five.")
assert pageview.gist(shopText) == (
	"The page in its own words, the beginning of each part: Example Shop: Welcome to our shop. Refund policy: You can "
	"return any product within 30 days for a full refund. Opening hours: We are open Monday to Friday from nine to five.")
newsText = (
	"Home\nWorld\nSport\nBig storm hits the coast\nA storm with winds of 90 miles an hour reached the coast on Monday night. "
	"Thousands lost power.\nA second paragraph that is not the beginning of a part.\n...\nWhat happens next\n"
	"Crews expect to restore power by Friday.\nContact us\nAbout")
assert pageview.gist(newsText) == (
	"The page in its own words, the beginning of each part: Big storm hits the coast: A storm with winds of 90 miles an "
	"hour reached the coast on Monday night. What happens next: Crews expect to restore power by Friday.")
assert pageview.gist("Home\nAbout\nContact") == "" and pageview.gist("") == ""
longText = "\n".join(f"Part {n}\nThis is the first sentence of part number {n}, and it is a fairly long one. More." for n in range(40))
assert len(pageview.gist(longText)) <= pageview.GIST_CHARS + len(pageview.GIST_LEAD) + 1
assert pageview.gist(longText).startswith(pageview.GIST_LEAD + " Part 0: This is the first sentence of part number 0")
for words, asks in (("Summarize this page.", True), ("what is this page about", True), ("give me the gist", True),
		("What does this page say about refunds?", False), ("Take me to the heading Refund policy.", False)):
	assert pageview.asksGist(words) is asks, words

print("The user guide of the NVDA on this computer was asked for the keys." if guideChecked else "NVDA is not installed here: the keys were not compared with its user guide.")
print("OK")
