# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""How a control is worked, arrow keys for controls that are dragged, and the downloaded developer guides.

Plain Python: what NVDA's facts say about how a sighted person works a control, which controls are left for
the models, how two answers are settled, which remedy fits; the drags and values behind the arrow keys, and
whether a drawn dial changed; a web page turned into Markdown, and guides fetched by a stand-in for the
internet. The dial is a drawing and the internet is a function: nothing here shows how real programs answer.
"""
import math
import os
import tempfile

from PIL import Image, ImageDraw

import harness  # noqa: F401
from visionClaw.claw import dragcontrol, guides, working
from visionClaw.claw.knowledge import Knowledge

# --- How a control is worked, from NVDA's facts ---

assert working.byRole({"role": "BUTTON"}) == working.CLICK and working.byRole({"role": "EDITABLETEXT"}) == working.TYPE
assert working.byRole({"role": "COMBOBOX"}) == working.CHOOSE and working.byRole({"role": "DIAL"}) == working.AROUND
# Which way a slider lies is told by its shape.
assert working.byRole({"role": "SLIDER"}, (0, 0, 200, 20)) == working.SIDEWAYS
assert working.byRole({"role": "SLIDER"}, (0, 0, 20, 200)) == working.UPDOWN
assert working.byRole({"role": "PANE"}) is None and working.byRole({"role": "GRAPHIC"}) is None


def node(role, name="", states=(), up=None, **more):
	return dict({"role": role, "name": name, "text": "", "states": list(states), "up": up}, **more)


root = node("WINDOW", "Mixer")
titleBar = node("TITLEBAR", up=root)
close = node("BUTTON", "Close", up=titleBar)
play = node("BUTTON", "Play", up=root)
ok = node("BUTTON", "OK", ["FOCUSABLE"], up=root)
volume = node("SLIDER", "Volume", up=root)
gain = node("SLIDER", "Gain", ["FOCUSABLE"], up=root)
knob = node("PANE", "", ["FOCUSABLE"], up=root)
label = node("STATICTEXT", "Master", up=root)
hidden = node("BUTTON", "Ghost", ["INVISIBLE"], up=root)
found = working.survey([root, titleBar, close, play, ok, volume, gain, knob, label, hidden])
# The title bar's button is as it should be; a button and a slider that never take the focus are mouse only;
# the pane whose kind says nothing is left for the models; what is not showing is not counted at all.
assert found["mouseOnly"] == [play, volume] and found["unsure"] == [knob], found
assert found["ways"] == {working.CLICK: 3, working.SIDEWAYS: 2}, found["ways"]
assert working.waysText(found["ways"]) == (
	"Of the controls whose kind NVDA can tell, with a mouse 3 are clicked, 2 are dragged sideways.")
# On a web page browse mode presses links and buttons itself, so only what is dragged counts as mouse only,
# and a part of the page that the page says is clicked is left for the models.
page = node("DOCUMENT", "Shop")
link = node("LINK", "Home", up=page)
card = node("SECTION", "Blue shirt", ["CLICKABLE"], up=page)
inner = node("STATICTEXT", "Blue shirt", ["CLICKABLE"], up=link)
range_ = node("SLIDER", "Price", up=page)
found = working.survey([page, link, card, inner, range_], page=True)
assert found["mouseOnly"] == [range_] and found["unsure"] == [card], found

# What a deep query says outright is decided by plain code, whatever kind NVDA calls the control.
assert working.byFacts({"role": "PANE", "range": {"now": 1.0, "low": 0.0, "high": 9.0}, "box": (0, 0, 20, 200)}) == working.UPDOWN
assert working.byFacts({"role": "PANE", "patterns": ["a value in a range"], "box": (0, 0, 200, 20)}) == working.SIDEWAYS
assert working.byFacts({"role": "PANE", "patterns": ["invoke"]}) == working.CLICK
assert working.byFacts({"role": "SECTION", "actions": ["click"]}) == working.CLICK
assert working.byFacts({"role": "SECTION", "web": {"tag": "div", "xml-roles": "slider"}}) == working.SIDEWAYS
assert working.byFacts({"role": "PANE", "patterns": ["a value as text"], "states": ["FOCUSABLE"]}) == working.TYPE
assert working.byFacts({"role": "PANE", "patterns": ["a value as text"], "states": ["READONLY"]}) is None
assert working.byFacts({"role": "PANE", "name": "Ready"}) is None
# A bare window gives the coder model nothing to reason from, so it is not asked.
assert not working.telling({"role": "PANE", "name": "", "states": [], "windowClass": "UnityWndClass"})
assert working.telling({"role": "PANE", "name": "Ready"}) and working.telling({"role": "PANE", "states": ["READONLY"]})

# Two answers are settled: the same is sure; two ways of turning are sure enough, since trying tells which;
# a real difference is said; one answer alone is not sure.
assert working.settle(working.CLICK, working.CLICK) == (working.CLICK, True, "both models")
assert working.settle(working.AROUND, working.UPDOWN) == (working.AROUND, True, "both models")
assert working.settle(working.AROUND, working.CLICK) == (working.AROUND, False, "the vision model; the coder model says click")
assert working.settle(None, working.TYPE) == (working.TYPE, False, "the coder model")
assert working.settle(working.UNSURE, None) == (working.UNSURE, False, "neither model")
# The remedy follows from how it is worked and whether the keyboard reaches it.
assert working.remedy(working.AROUND, False) == working.ARROW_KEYS and working.remedy(working.SIDEWAYS, True) == working.NOTHING
assert working.remedy(working.CLICK, False) == working.PRESS_KEY and working.remedy(working.CLICK, True) == working.NOTHING
assert working.remedy(working.DRAG_TO, False) == working.ADVICE and working.remedy(working.SHOWS, False) == working.NOTHING
# What a model wrote is matched to a way; anything else is no answer.
assert working.wayFrom({"way": "turn in a circle"}) == working.AROUND and working.wayFrom("Drag sideways.") == working.SIDEWAYS
assert working.wayFrom("double click") == working.DOUBLE and working.wayFrom("press it hard") is None
assert set(working.JUDGE_SCHEMA["properties"]["way"]["enum"]) == set(working.WAYS)
# The class of a window says what draws it.
assert working.toolkitOf("UnityWndClass")[0] == "the Unity game engine" and working.toolkitOf("JUCE_19a3b")[0].startswith("JUCE")
assert working.toolkitOf("Notepad") == ("", "") and working.toolkitOf("x", "WPF")[0] == "Windows Presentation Foundation"
# The facts of a deep query, in sentences.
text = working.factsText({
	"role": "PANE", "roleText": "pane", "name": "", "states": ["FOCUSABLE"], "focusable": True, "actions": ["click"],
	"patterns": ["a value in a range"], "range": {"now": 3.0, "low": 0.0, "high": 10.0, "readOnly": False},
	"api": "Windows UI Automation", "windowClass": "JUCE_1", "drawn": "Gain 3", "under": ("BUTTON", "Bypass"),
})
assert text.startswith("It is reported as: pane, with no name. Its states: focusable. It takes the keyboard focus.")
assert "Its value runs from 0 to 10 and stands at 3, and can be set without the mouse." in text
assert "which is JUCE, used by music programs and plug-ins." in text and "from NVDA's off-screen model: Gain 3." in text
assert "At its middle, Windows itself finds: button Bypass." in text, text

# --- Controls that are worked by neither a click nor a drag ---

# What a control's own name or description says about how it is worked, in words that can hardly mean
# anything else. A button called Hold, as on a telephone, is clicked.
for name, way in (
	("Hold to record", working.HOLD), ("Press and hold to delete", working.HOLD), ("Push-to-talk", working.HOLD),
	("Long press for more", working.HOLD), ("Hold", None), ("Hold call", None),
	("Hover for details", working.HOVER), ("Mouse over a bar to see its value", working.HOVER),
	("Swipe to unlock", working.GESTURE), ("Slide to confirm", working.GESTURE), ("Sign here", working.GESTURE),
	("Draw your signature", working.GESTURE), ("Signature pad", working.GESTURE),
	("Click when the bar is green", working.TIMED), ("Stop at the right moment", working.TIMED), ("Reaction test", working.TIMED),
	("Play", None), ("Draw", None), ("", None),
):
	assert working.bySaid({"name": name}) == way, (name, working.bySaid({"name": name}))
assert working.bySaid({"name": "Record", "description": "Hold down to record a voice message"}) == working.HOLD
# Wordings the real coder models did not understand (tests/live_working.py, 2026-11-18), so plain code knows them.
assert working.bySaid({"name": "Microphone", "description": "Keep the mouse button down on this while you speak"}) == working.HOLD
assert working.bySaid({"name": "Sketch", "description": "Sketch with the mouse"}) == working.GESTURE
# Its own words count before a click that Windows offers, and after a value that can be set.
assert working.byFacts({"role": "BUTTON", "name": "Hold to record", "patterns": ["invoke"]}) == working.HOLD
assert working.byFacts({"role": "PANE", "name": "Slide to unlock", "range": {"now": 0.0, "low": 0.0, "high": 1.0}}) == working.SIDEWAYS
# In the survey such a control is told apart whether or not it takes the focus: Enter clicks a button, it does
# not keep it down. On a web page as well, where NVDA presses buttons itself.
record = node("BUTTON", "Hold to record", ["FOCUSABLE"], up=root)
pad = node("PANE", "Signature pad", ["FOCUSABLE"], up=root)
note = node("STATICTEXT", "Hold to record a message", up=root)
found = working.survey([root, record, pad, note, ok])
assert found["special"] == [(record, working.HOLD), (pad, working.GESTURE)] and found["unsure"] == [], found
assert found["ways"] == {working.HOLD: 1, working.GESTURE: 1, working.CLICK: 1}, found["ways"]
assert working.survey([page, node("BUTTON", "Hold to talk", ["FOCUSABLE"], up=page)], page=True)["special"][0][1] == working.HOLD
assert working.waysText({working.HOLD: 1, working.HOVER: 2}) == (
	"Of the controls whose kind NVDA can tell, with a mouse 2 are pointed at without a click, 1 is pressed and held down.")
# What can be done for each: a hotkey that rests the pointer or holds the button, also on a control that takes
# the focus; for the others, what to ask VisionClaw, and the keys of pointer mode.
assert working.remedy(working.HOVER, True) == working.REST_KEY and working.remedy(working.HOLD, True) == working.HOLD_KEY
for way in (working.GESTURE, working.TIMED, working.PAD):
	assert working.remedy(way, True) == working.ADVICE and working.remedy(way, False) == working.ADVICE
for way, words in ((working.HOVER, "T does the same"), (working.HOLD, "G holds the mouse button"),
		(working.GESTURE, "the arrow keys draw"), (working.TIMED, "C clicks what is under the pointer"),
		(working.PAD, "move it in any direction with the arrow keys")):
	assert words in working.adviceFor(way) and "NVDA+Alt+K" in working.adviceFor(way), way
assert "25 times a second" in working.adviceFor(working.TIMED)  # what it cannot do is said
assert set(working.SPECIAL) <= set(working.WAYS) and working.WAYS[-1] == working.UNSURE
# The models are told every way in a line of its own, and may answer with each.
for way in working.WAYS:
	assert f"{way}:" in working.VISION_SYSTEM, way
	assert way in working.CODER_SYSTEM and working.wayFrom({"way": way}) == way, way
assert working.settle(working.HOVER, working.HOVER) == (working.HOVER, True, "both models")
assert working.settle(working.HOLD, working.CLICK) == (working.HOLD, False, "the vision model; the coder model says click")

# --- Every kind of control NVDA has ---

# NVDA's own kinds, read from controlTypes.Role of the NVDA installed on this computer on 2026-11-18. Each is
# known: how it is worked, that it only holds or shows something, or that it is left for the models to look at.
NVDA_ROLES = (
	"ALERT ALIGNMENT ANIMATION APPLICATION ARTICLE AUDIO BGCOLOR BLOCKQUOTE BOLD BORDER BOX BUSY_INDICATOR BUTTON "
	"CALENDAR CANVAS CAPTION CARET CHARACTER CHART CHARTELEMENT CHECKBOX CHECKMENUITEM CLOCK COLORCHOOSER COMBOBOX "
	"COMMENT CURSOR DATAGRID DATAITEM DATEEDITOR DEFINITION DELETED_CONTENT DESKTOPICON DESKTOPPANE DIAGRAM DIAL "
	"DIALOG DIRECTORYPANE DOCUMENT DROPDOWNBUTTON DROPDOWNBUTTONGRID DROPLIST EDITABLETEXT EDITBAR EMBEDDEDOBJECT "
	"ENDNOTE FGCOLOR FIGURE FILECHOOSER FILLER FONTCHOOSER FONTNAME FONTSIZE FOOTER FOOTNOTE FORM FRAME GLASSPANE "
	"GRAPHIC GRIP GROUPING HEADER HEADERITEM HEADING HEADING1 HEADING2 HEADING3 HEADING4 HEADING5 HEADING6 HELPBALLOON HOTKEYFIELD ICON IMAGEMAP INDENT INDICATOR "
	"INPUTWINDOW INSERTED_CONTENT INTERNALFRAME IPADDRESS ITALIC LABEL LANDMARK LAYEREDPANE LINE LINK LIST LISTITEM "
	"MARKED_CONTENT MATH MENU MENUBAR MENUBUTTON MENUITEM NOTE OPTIONPANE PAGE PANE PANEL PARAGRAPH PASSWORDEDIT "
	"POPUPMENU PROGRESSBAR PROPERTYPAGE RADIOBUTTON RADIOMENUITEM REDUNDANTOBJECT REGION RICHEDIT ROOTPANE RULER "
	"SCROLLBAR SCROLLPANE SECTION SEPARATOR SHAPE SLIDER SOUND SPINBUTTON SPLITBUTTON SPLITPANE STATICTEXT STATUSBAR "
	"STYLE SUBSCRIPT SUGGESTION SUPERSCRIPT SWITCH TAB TABCONTROL TABLE TABLEBODY TABLECELL TABLECOLUMN "
	"TABLECOLUMNHEADER TABLEFOOTER TABLEHEADER TABLEROW TABLEROWHEADER TEAROFFMENU TERMINAL TEXTFRAME THUMB TITLEBAR "
	"TOGGLEBUTTON TOOLBAR TOOLTIP TREEVIEW TREEVIEWBUTTON TREEVIEWITEM UNDERLINE UNKNOWN VIDEO VIEWPORT WHITESPACE "
	"WINDOW"
).split()
assert len(NVDA_ROLES) == len(set(NVDA_ROLES)) == 156, len(NVDA_ROLES)
assert [role for role in NVDA_ROLES if not working.knownRole(role)] == []
# A kind is in one place only: it is worked in a known way, or it only holds or shows, or it is looked at.
assert not set(working._BY_ROLE) & working._PASSIVE and not working._OPEN & (set(working._BY_ROLE) | working._PASSIVE)
assert working.byRole({"role": "DESKTOPICON"}) == working.DOUBLE and working.byRole({"role": "CHECKMENUITEM"}) == working.CLICK
assert working.byRole({"role": "DROPLIST"}) == working.CHOOSE and working.byRole({"role": "IPADDRESS"}) == working.TYPE
assert working.byRole({"role": "GRIP"}) == working.PAD and working.byRole({"role": "VIDEO"}) is None
# The part that is dragged: the bar between two panes, which stands upright, is dragged sideways.
assert working.byRole({"role": "THUMB"}, (300, 0, 306, 400)) == working.SIDEWAYS
assert working.byRole({"role": "THUMB"}, (0, 200, 400, 206)) == working.UPDOWN and working.byRole({"role": "THUMB"}) is None
assert working.byFacts({"role": "THUMB", "box": (300, 0, 306, 400)}) == working.SIDEWAYS
# A picture, a video or an embedded program in a window is something for the models to look at.
video = node("VIDEO", "", up=root)
embedded = node("EMBEDDEDOBJECT", "", up=root)
assert working.survey([root, video, embedded, label])["unsure"] == [video, embedded]
# What Windows, the page's code and NVDA's states say outright, beyond a click and a value.
assert working.byFacts({"role": "PANE", "patterns": ["drag"]}) == working.DRAG_TO
assert working.byFacts({"role": "SECTION", "web": {"tag": "div", "draggable": "true"}}) == working.DRAG_TO
assert working.byFacts({"role": "PANE", "patterns": ["move and resize"]}) == working.PAD
assert working.byFacts({"role": "PANE", "patterns": ["scroll"]}) == working.WHEEL
assert working.byFacts({"role": "PANE", "patterns": ["select"]}) == working.CLICK
assert working.byFacts({"role": "SECTION", "web": {"tag": "div", "haspopup": "menu"}}) == working.CHOOSE
assert working.byFacts({"role": "SECTION", "web": {"tag": "div", "xml-roles": "menuitemcheckbox"}}) == working.CLICK
assert working.byFacts({"role": "SECTION", "web": {"tag": "div", "xml-roles": "progressbar"}}) == working.SHOWS
assert working.byFacts({"role": "SECTION", "web": {"xml-roles": "separator"}, "box": (300, 0, 306, 400)}) == working.SIDEWAYS
assert working.byFacts({"role": "SECTION", "states": ["DRAGGABLE"]}) == working.DRAG_TO
assert working.byFacts({"role": "SECTION", "states": ["EDITABLE", "FOCUSABLE"]}) == working.TYPE
assert working.byFacts({"role": "SECTION", "states": ["EDITABLE", "READONLY"]}) is None
assert working.byFacts({"role": "SECTION", "states": ["HASPOPUP"]}) == working.CHOOSE
assert working.byFacts({"role": "SECTION", "states": ["CHECKABLE"]}) == working.CLICK
assert working.byFacts({"role": "SECTION", "states": ["COLLAPSED"]}) == working.CLICK

# --- Arrow keys for a control that is dragged ---

assert dragcontrol.methodOf("the dial is dragged in a circle") == dragcontrol.AROUND
assert dragcontrol.methodOf("drag it up and down") == dragcontrol.UPDOWN and dragcontrol.methodOf("it moves sideways") == dragcontrol.SIDEWAYS
assert dragcontrol.methodOf("use the mouse wheel on it") == dragcontrol.WHEEL and dragcontrol.methodOf("the volume dial") is None
assert dragcontrol.kindWord("the volume knob") == "dial" and dragcontrol.kindWord("the fader") == "slider"
assert dragcontrol.kindWord("this thing") == "control"
assert dragcontrol.atPointer("work what is under the mouse pointer") and not dragcontrol.atPointer("the volume dial")
assert dragcontrol.wantsKept("give me a hotkey for the dial") and not dragcontrol.wantsKept("turn the dial")
# The wheel is tried first, because it presses nothing; around comes last; a value Windows offers comes before all.
assert dragcontrol.order() == [dragcontrol.WHEEL, dragcontrol.UPDOWN, dragcontrol.SIDEWAYS, dragcontrol.AROUND]
assert dragcontrol.order("drag sideways", hasValue=True)[:3] == [dragcontrol.VALUE, dragcontrol.WHEEL, dragcontrol.SIDEWAYS]
# One key press is one short drag from the control's place; twice the pixels at twice the scaling.
stroke = dragcontrol.stroke(dragcontrol.UPDOWN, 1, dragcontrol.STEP)
assert stroke[0] == (0, 0) and stroke[-1] == (0, -8) and len(stroke) >= 3, stroke
assert dragcontrol.stroke(dragcontrol.UPDOWN, 1, dragcontrol.STEP, 2.0)[-1] == (0, -16)
assert dragcontrol.stroke(dragcontrol.SIDEWAYS, -1, dragcontrol.FAR)[-1] == (-32, 0)
assert dragcontrol.stroke(dragcontrol.UPDOWN, -1, dragcontrol.FINE)[-1] == (0, 2)
# Around: from the top of the rim, along the rim, clockwise for up.
arc = dragcontrol.stroke(dragcontrol.AROUND, 1, dragcontrol.STEP, 1.0, 20)
assert arc[0] == (0, -20) and arc[-1][0] > 0 and all(abs(math.hypot(x, y) - 20) <= 1 for x, y in arc), arc
assert dragcontrol.stroke(dragcontrol.AROUND, -1, dragcontrol.STEP, 1.0, 20)[-1][0] < 0
# A value Windows offers is moved by a share of its range, by the control's own step where it has one.
assert dragcontrol.nextValue(50, 0, 100, 1, dragcontrol.STEP) == 55 and dragcontrol.nextValue(98, 0, 100, 1, dragcontrol.FAR) == 100
assert dragcontrol.nextValue(5, 0, 10, -1, dragcontrol.FINE, small=1) == 4 and dragcontrol.nextValue(0, 0, 0, 1, dragcontrol.STEP) == 0
assert dragcontrol.valueText(5, 0, 20) == "25 percent"


def dial(angle, size=96):
	"""A drawing of a round dial whose mark points at an angle."""
	image = Image.new("L", (size, size), 230)
	draw = ImageDraw.Draw(image)
	draw.ellipse((18, 18, size - 18, size - 18), fill=90)
	middle = size // 2
	draw.line((middle, middle, middle + 26 * math.sin(angle), middle - 26 * math.cos(angle)), fill=250, width=5)
	return image


# Whether the control changed is told from its picture.
assert dragcontrol.changed(dial(0.0), dial(0.0)) == 0.0
assert dragcontrol.changed(dial(0.0), dial(0.5)) >= dragcontrol.CHANGED
assert dragcontrol.changed(dial(0.0), dial(0.12)) >= dragcontrol.CHANGED  # one fine step still shows
# The text that is new after a turn is what the control now shows.
assert dragcontrol.newText(["Volume", "-6.0 dB"], ["Volume", "-5.5 dB"]) == "-5.5 dB"
assert dragcontrol.newText(["Volume"], ["Volume"]) == "" and dragcontrol.newText(None, ["a", "b"]) == "a b"
# A place is kept as a share of the window, so it is found again when the window is moved or resized.
share = dragcontrol.shareOf((300, 250), (100, 100, 500, 400))
assert share == (0.5, 0.5) and dragcontrol.pointOf(share, (0, 0, 1000, 800)) == (500, 400)
assert dragcontrol.around((10, 10), 96, (0, 0, 800, 600)) == (0, 0, 96, 96)
assert dragcontrol.around((790, 300), (320, 220), (0, 0, 800, 600)) == (480, 190, 800, 410)
# The name of a dial is often the text beside it: the thing to hold is the icon joined to it or next to it.
items = [
	{"kind": "icon", "box": (10, 10, 50, 50), "text": "knob icon"},
	{"kind": "text", "box": (100, 10, 220, 40), "textBox": (140, 10, 220, 40), "text": "Pan"},
	{"kind": "text", "box": (20, 56, 44, 68), "text": "Gain"},
	{"kind": "text", "box": (400, 400, 460, 414), "text": "Status"},
]
assert dragcontrol.handleOf(items, 0) == (30, 30, 14)
assert dragcontrol.handleOf(items, 1)[:2] == (120, 25)  # the part of the item that is not its text
assert dragcontrol.handleOf(items, 2) == (30, 30, 14)  # the icon right above the text
assert dragcontrol.handleOf(items, 3) == (430, 407, 0)  # nothing near: the text itself
# Every key does something known; the help names the way it is worked.
assert {command[0] for command in dragcontrol.KEYS.values()} == {"turn", "end", "read", "look", "method", "keep", "help", "exit"}
said = dragcontrol.helpText("Volume", "dial", dragcontrol.UPDOWN)
assert said.startswith("The arrow keys now work Volume, a dial, by dragging it up and down.") and "Escape gives the arrow keys back." in said
assert dragcontrol.describe({"key": "NVDA+alt+3", "name": "Volume", "method": dragcontrol.WHEEL}) == (
	"NVDA+alt+3 takes hold of Volume, so the arrow keys work it with the mouse wheel")

# --- The developer guides ---

PAGE = (
	"<html><head><title>x</title><style>p {color: red}</style></head><body><nav><a href='#a'>Contents</a></nav>"
	"<h1>NVDA Developer Guide</h1><p>This guide   explains <code>globalPluginHandler</code> &amp; more.</p>"
	"<h2 id='events'>Events</h2><ul><li>gainFocus</li><li>nameChange</li></ul>"
	"<pre>def event_gainFocus(self, obj, nextHandler):\n\tnextHandler()</pre>"
	"<script>alert(1)</script><h3>Scripts</h3><p>A script is bound to a gesture.</p></body></html>"
)
markdown = guides.toMarkdown(PAGE)
assert markdown.startswith("# NVDA Developer Guide\n\nThis guide explains `globalPluginHandler` & more.\n\n## Events\n"), markdown
assert "- gainFocus\n- nameChange" in markdown and "```\ndef event_gainFocus(self, obj, nextHandler):\n\tnextHandler()\n```" in markdown
assert "alert" not in markdown and "Contents" not in markdown and "color" not in markdown and "### Scripts" in markdown
assert guides.tidy("## Events {#events}\n\n\n\ntext  \n") == "## Events\n\ntext\n"

folder = tempfile.mkdtemp()
LONG = "".join(f"<h2>Part {n}</h2><p>{'Words about part %d. ' % n * 40}</p>" for n in range(12))
WIKI = "".join(f"## Topic {n}\n\n{'The wiki says things about topic %d. ' % n * 30}\n\n" for n in range(10))
asked = []


def fetch(url):
	asked.append(url)
	return "<html><body><h1>Guide</h1>" + LONG + "</body></html>" if url.endswith(".html") else WIKI


result = guides.update(folder, fetch, today="2026-11-17")
assert asked == [source["url"] for source in guides.SOURCES] and all(url.startswith("https://") for url in asked)
assert result == {"got": [("NVDA Developer Guide", 12), ("NVDA Add-on Development Guide", 10)], "failed": []}, result
assert guides.summary(result).startswith("Downloaded the NVDA Developer Guide and kept it as Markdown, 12 sections.")
assert guides.stored(folder)["NVDA Developer Guide"] == {"date": "2026-11-17", "sections": 12}
loaded = guides.load(folder)
assert len(loaded) == 22 and loaded[0][0] == "NVDA Developer Guide: Part 0" and loaded[0][2] == "guides", loaded[0]
# A guide that cannot be fetched, or an answer that is not a guide, leaves the earlier copy in place.


def broken(url):
	if url.endswith(".html"):
		raise OSError("no connection")
	return "Not found"


result = guides.update(folder, broken)
assert result["got"] == [] and [title for title, _why in result["failed"]] == ["NVDA Developer Guide", "NVDA Add-on Development Guide"]
assert "could not be downloaded" in guides.summary(result) and len(guides.load(folder)) == 22
assert all(source["url"].split("/")[2] in guides.HOSTS for source in guides.SOURCES)
# The guides are searched with VisionClaw's own notes, and read again after an update.
knowledge = Knowledge(tempfile.mkdtemp())
knowledge.addSource("guides", lambda: guides.load(folder))
assert knowledge.search("topic 3 wiki")[0][0].startswith("NVDA Add-on Development Guide: Topic")
os.remove(os.path.join(folder, "nvda-addon-development-guide.md"))
knowledge.replaceSource("guides", lambda: guides.load(folder))
assert all("Add-on Development" not in title for title, _body, _source in knowledge.search("topic 3 wiki"))

print("OK")
