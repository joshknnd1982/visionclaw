# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - objects without a name, or with a vague one, named on the fly by the model that sees, wherever the
# user moves: the focus, browse mode, object navigation, review and the mouse. Plain code decides which objects
# need a name (every role NVDA has is sorted here), what tells an object apart so that its name is found again,
# whether a name is sure or only probable, and keeps the names in a file the user can share with other VisionClaw
# users. No NVDA imports; the NVDA side is nametools.py.

import datetime
import json
import os
import re
import threading
import unicodedata

from . import audit, working
from .fixmatch import nodeFromField, plainText

# --- Which objects are named ---

# Every role of NVDA 2026.3.1 (tests/nvda_objects.json, read from NVDA's source by tools/write_nvda_objects.py) is in
# exactly one of these three; tests/test_naming.py fails when NVDA has one that is in none. Read the source again for
# a newer NVDA, and sort what is new.
# A control or a picture: it should have a name, and is named when it has none or a vague one.
NAMED = frozenset((
	"BUTTON", "TOGGLEBUTTON", "MENUBUTTON", "DROPDOWNBUTTON", "DROPDOWNBUTTONGRID", "SPLITBUTTON", "TREEVIEWBUTTON",
	"SPINBUTTON", "MENUITEM", "CHECKMENUITEM", "RADIOMENUITEM", "LINK", "TAB", "ICON", "DESKTOPICON", "GRAPHIC",
	"CHECKBOX", "RADIOBUTTON", "SWITCH", "COMBOBOX", "DROPLIST", "EDITABLETEXT", "PASSWORDEDIT", "RICHEDIT", "EDITBAR",
	"HOTKEYFIELD", "IPADDRESS", "DATEEDITOR", "SLIDER", "DIAL", "PROGRESSBAR", "CANVAS", "CHART", "DIAGRAM",
	"IMAGEMAP", "ANIMATION", "VIDEO", "AUDIO", "SOUND", "CLOCK", "COLORCHOOSER", "FONTCHOOSER", "FILECHOOSER",
	"CALENDAR", "EMBEDDEDOBJECT", "SHAPE", "FIGURE", "CHARTELEMENT", "THUMB", "SCROLLBAR", "INDICATOR",
))
# Holds or shows something: named only where the program made it something to press or to move to (it can be
# clicked or have the focus) and nothing in it is text. A box on a web page that is clicked, a list item that is
# only a picture, a pane that is really a control drawn by the program.
WHEN_CLICKABLE = frozenset((
	"UNKNOWN", "WINDOW", "PANE", "PANEL", "GROUPING", "SECTION", "REGION", "ARTICLE", "LISTITEM", "TREEVIEWITEM",
	"TABLECELL", "DATAITEM", "HEADERITEM", "TABLECOLUMNHEADER", "TABLEROWHEADER", "STATICTEXT", "LABEL", "PARAGRAPH",
	"LIST", "TREEVIEW", "TABLE", "DATAGRID", "TOOLBAR", "TABCONTROL", "MENU", "POPUPMENU", "TEXTFRAME", "PROPERTYPAGE",
	"OPTIONPANE", "SCROLLPANE", "LAYEREDPANE", "ROOTPANE", "INTERNALFRAME", "GLASSPANE", "VIEWPORT", "SPLITPANE",
	"DIRECTORYPANE", "DESKTOPPANE", "INPUTWINDOW", "BOX", "CAPTION", "NOTE", "FORM", "DOCUMENT", "TERMINAL",
))
# Never named: text, the structure and formatting of a document, a window's own parts that say their words, and
# NVDA's own stand-ins. Their words come from their text, or there is nothing to name.
LEFT = frozenset((
	"TITLEBAR", "DIALOG", "MENUBAR", "STATUSBAR", "TOOLTIP", "HELPBALLOON", "ALERT", "FRAME", "APPLICATION",
	"CARET", "CURSOR", "CHARACTER", "LINE", "HEADING", "HEADING1", "HEADING2", "HEADING3", "HEADING4", "HEADING5",
	"HEADING6", "HEADER", "FOOTER", "FOOTNOTE", "ENDNOTE", "BLOCKQUOTE", "LANDMARK", "TABLEROW", "TABLECOLUMN",
	"TABLEBODY", "TABLEHEADER", "TABLEFOOTER", "SEPARATOR", "WHITESPACE", "FILLER", "REDUNDANTOBJECT", "BORDER",
	"GRIP", "RULER", "INDENT", "ALIGNMENT", "BOLD", "ITALIC", "UNDERLINE", "FGCOLOR", "BGCOLOR", "STYLE", "FONTNAME",
	"FONTSIZE", "SUBSCRIPT", "SUPERSCRIPT", "MATH", "COMMENT", "DEFINITION", "DELETED_CONTENT", "INSERTED_CONTENT",
	"MARKED_CONTENT", "SUGGESTION", "PAGE", "TEAROFFMENU", "BUSY_INDICATOR",
))
# The states that make a holder something to press or move to.
CLICKABLE_STATES = frozenset(("CLICKABLE", "FOCUSABLE", "FOCUSED", "LINKED"))
# The states that make a holder something to press, not only a place to move to.
PRESSED_STATES = frozenset(("CLICKABLE", "LINKED"))
# Holders of text, data or other objects: moving to an empty one (an empty cell of a spreadsheet, an empty list, a
# page without a title) is no reason to name it. Named only where the program made it something to press.
PRESSED_ONLY = frozenset((
	"TABLECELL", "DATAITEM", "HEADERITEM", "TABLECOLUMNHEADER", "TABLEROWHEADER", "STATICTEXT", "LABEL", "PARAGRAPH",
	"CAPTION", "NOTE", "TEXTFRAME", "DOCUMENT", "TERMINAL", "FORM", "LIST", "TREEVIEW", "TABLE", "DATAGRID", "TOOLBAR",
	"TABCONTROL", "MENU", "POPUPMENU", "ARTICLE", "PROPERTYPAGE", "OPTIONPANE", "SCROLLPANE", "LAYEREDPANE", "ROOTPANE",
	"INTERNALFRAME", "GLASSPANE", "VIEWPORT", "SPLITPANE", "DIRECTORYPANE", "DESKTOPPANE", "INPUTWINDOW",
))
# Controls that are named by the words inside them, as NVDA reads them in browse mode.
BY_CONTENT = frozenset(("LINK", "BUTTON", "TOGGLEBUTTON", "MENUBUTTON", "SPLITBUTTON", "DROPDOWNBUTTON", "MENUITEM",
	"CHECKMENUITEM", "RADIOMENUITEM", "TAB", "LISTITEM", "TREEVIEWITEM", "CHECKBOX", "RADIOBUTTON", "SWITCH"))
# The states of an object that cannot be seen, so that there is no picture to name it from.
UNSEEN_STATES = frozenset(("INVISIBLE", "OFFSCREEN", "DEFUNCT"))
# Fields: what names them is usually written next to them, so the picture takes in what is before and above them.
FIELDS = frozenset(("EDITABLETEXT", "PASSWORDEDIT", "RICHEDIT", "EDITBAR", "COMBOBOX", "DROPLIST", "HOTKEYFIELD",
	"IPADDRESS", "DATEEDITOR", "SLIDER", "SPINBUTTON", "PROGRESSBAR", "SCROLLBAR"))
# Small things that are mostly an icon: a single letter or a symbol is no name for them ("X", "+", "i").
ICONLIKE = frozenset(("BUTTON", "TOGGLEBUTTON", "MENUBUTTON", "DROPDOWNBUTTON", "SPLITBUTTON", "LINK", "TAB", "ICON",
	"DESKTOPICON", "GRAPHIC", "MENUITEM", "CHECKBOX", "RADIOBUTTON", "SWITCH"))
# The words for a kind, as the model that names it is told.
_KINDS = {
	"BUTTON": "button", "TOGGLEBUTTON": "toggle button", "MENUBUTTON": "menu button", "DROPDOWNBUTTON": "drop-down button",
	"SPLITBUTTON": "split button", "SPINBUTTON": "spin button", "MENUITEM": "menu item", "CHECKMENUITEM": "menu item",
	"RADIOMENUITEM": "menu item", "LINK": "link", "TAB": "tab", "ICON": "icon", "DESKTOPICON": "icon", "GRAPHIC": "picture",
	"CHECKBOX": "check box", "RADIOBUTTON": "radio button", "SWITCH": "switch", "COMBOBOX": "combo box",
	"EDITABLETEXT": "edit field", "PASSWORDEDIT": "password field", "SLIDER": "slider", "DIAL": "dial",
	"PROGRESSBAR": "progress bar", "LISTITEM": "list item", "TREEVIEWITEM": "tree item", "TABLECELL": "table cell",
	"LIST": "list", "TABLE": "table", "TOOLBAR": "toolbar", "CANVAS": "drawing", "CHART": "chart", "FIGURE": "figure",
	"VIDEO": "video", "AUDIO": "audio player", "CALENDAR": "calendar", "SCROLLBAR": "scroll bar",
}
# Pictures: their words are vague when they only say that they are pictures. Taken from autodescribe.py, which finds
# pictures without a useful label in documents. On a button, "Picture", "Download" or "Clear" is a real name.
PICTURES = frozenset(("GRAPHIC", "ICON", "DESKTOPICON", "CANVAS", "FIGURE", "IMAGEMAP", "ANIMATION", "CHART", "DIAGRAM"))
_PICTURE_WORDS = (
	"image|img|images|graphic|graphics|picture|pic|photo|photograph|foto|icon|icons|spacer|logo|banner|untitled"
	"|unlabeled|unlabelled|unnamed|thumbnail|thumb|placeholder|blank|default|dummy|null|undefined|none"
	"|alt|alt text|no alt|pixel|transparent|clear|download|attachment|media|figure|screen shot|screenshot|svg|canvas"
)
# Any object: words that are no name at all.
_ANY_WORDS = "untitled|unlabeled|unlabelled|unnamed|placeholder|dummy|null|undefined|nil|svg|div|span|clickable|btn|img|ico"
# What each kind of object is also called; a name that only says it is no name.
_KIND_ALIASES = {
	# Only words that say nothing more than the kind: "Password" on a password field and "Menu" on a menu button are
	# what those are called (Qwen3.5 4B's right answer "Password" was dropped while "password" was here, 2026-11-19).
	"BUTTON": "button|btn", "TOGGLEBUTTON": "button|toggle", "MENUBUTTON": "button", "SPLITBUTTON": "button",
	"DROPDOWNBUTTON": "button|drop down|dropdown", "LINK": "link|url|href", "TAB": "tab", "CHECKBOX": "checkbox|check box",
	"RADIOBUTTON": "radio|radio button|option", "EDITABLETEXT": "edit|text|textbox|text box|input|field|edit field|text field",
	"PASSWORDEDIT": "edit|input|field", "COMBOBOX": "combo|combobox|select|dropdown|drop down", "MENUITEM": "menu item|item",
	"LISTITEM": "item|list item", "SLIDER": "slider|range", "SWITCH": "switch|toggle",
}


def _wordsPattern(words):
	return re.compile(rf"^\W*(?:(?:{words})[\s_-]*)*\d*\W*$", re.IGNORECASE)


_ANY_VAGUE = _wordsPattern(_ANY_WORDS)
_PICTURE_VAGUE = _wordsPattern(_PICTURE_WORDS)
_KIND_VAGUE = {role: _wordsPattern(words + "|" + _ANY_WORDS) for role, words in _KIND_ALIASES.items()}
# A file name, a web address or a code number.
_FILEISH = re.compile(
	r"\.(png|jpe?g|gif|webp|svg|bmp|ico|avif|tiff?|heic)(\?.*)?\s*$"
	r"|^\s*(img|dsc|dscn|pxl|screenshot|screen shot|photo|image|whatsapp image|pexels|unsplash)[\s_-]*\d"
	r"|^\s*https?://\S*\s*$"
	r"|^\s*[0-9a-f-]{16,}\s*$",
	re.IGNORECASE,
)
# A name from the program's code rather than for people: "button1", "btnClose", "img_4021", "ic_settings_24". A word
# written as one with a capital inside ("iPhone", "eBay") is a name: only the prefixes programmers use count.
_CODE_NAME = re.compile(
	r"^(?:[a-z]{3,}[_-]?\d+"
	r"|(?:btn|img|ic|ico|icon|button|lbl|label|txt|chk|cb|rb|nav|menu|ctrl|lnk|pic|tab|sw|tgl)[A-Z0-9_-]\w*"
	r"|[A-Za-z]+(?:_[A-Za-z0-9]+)+)$")


def known(role):
	"""Whether a role of NVDA is sorted here."""
	return role in NAMED or role in WHEN_CLICKABLE or role in LEFT


def kindWord(role):
	return _KINDS.get(role, "control")


def _letters(text):
	"""The letters and digits of a text, without the characters an icon font draws (Unicode's private use area)."""
	return [char for char in str(text or "") if char.isalnum() and unicodedata.category(char) != "Co"]


def vague(name, role=""):
	"""Whether a name says nothing a person can use: none, only spaces, symbols, emoji or the characters of an icon
	font, a file name, a web address, a code, a word that is only a kind of control ("button", "image"), a name from
	the program's code ("btnClose"), or a single letter on something that is mostly an icon."""
	text = " ".join(str(name or "").split())
	if not text:
		return True
	if len(text) > 200:
		return False
	letters = _letters(text)
	if not letters:
		return True
	if _FILEISH.search(text) or _CODE_NAME.match(text):
		return True
	if role in ICONLIKE and len(letters) == 1:
		return True
	if role in PICTURES:
		return bool(_PICTURE_VAGUE.match(text))
	if (_KIND_VAGUE.get(role) or _ANY_VAGUE).match(text):
		return True
	return plainText(text) in (kindWord(role), role.lower())


def clickable(states, role=""):
	"""Whether a holder is something to press or move to; for one of PRESSED_ONLY, something to press."""
	need = PRESSED_STATES if role in PRESSED_ONLY else CLICKABLE_STATES
	return any(state in need for state in states or ())


# --- Truly without a name ---
#
# The owner said on 2026-11-19: "make sure it only labels objects, states, roles, etcetera, which are **truly**
# unlabeled", after object names had named buttons and objects that the accessibility interfaces of Windows and the
# browsers already name. vague() above judges a name a model, the text in a picture or a shared file gives, before it
# is used; it is strict on purpose. Whether an object needs a name at all is the opposite question, and is answered
# far more narrowly here: whatever the program or page gives NVDA is its label, however short or odd.

# Characters NVDA cannot say: never printed, spaces, joiners, marks that only change another character, and the
# private use area, where icon fonts keep their pictures.
_UNSAID = frozenset(("Co", "Cn", "Cc", "Cf", "Cs", "Zs", "Zl", "Zp", "Mn", "Me"))
# Words a program gives only by a mistake in its code: there was no label to give.
_NO_LABEL = re.compile(r"^\W*(?:undefined|null|nil|\[object object\]|unlabeled|unlabelled|unnamed|no name|untitled)\W*$",
	re.IGNORECASE)
# The words NVDA itself says for a kind of object; a name made only of them adds nothing to what NVDA says.
_ROLE_ONLY = {
	"BUTTON": "button|btn", "TOGGLEBUTTON": "button|toggle button", "MENUBUTTON": "button|menu button",
	"SPLITBUTTON": "button|split button", "DROPDOWNBUTTON": "button|drop down button|dropdown button", "LINK": "link",
	"TAB": "tab", "CHECKBOX": "checkbox|check box", "RADIOBUTTON": "radio button|radio", "SWITCH": "switch",
	"EDITABLETEXT": "edit|edit field|text field|textbox|text box|input", "PASSWORDEDIT": "edit|password edit|input",
	"COMBOBOX": "combo box|combobox|dropdown|drop down", "MENUITEM": "menu item", "SLIDER": "slider",
	"SPINBUTTON": "spin button", "PROGRESSBAR": "progress bar", "SCROLLBAR": "scroll bar|scrollbar",
}
_ROLE_ONLY_PATTERN = {role: re.compile(rf"^\W*(?:{words})\W*$", re.IGNORECASE) for role, words in _ROLE_ONLY.items()}
# Pictures without a label of their own, as screen readers have always called them: their name is their file, a web
# address, a code, or a word that only says they are pictures.
_UNLABELLED_PICTURES = frozenset(("GRAPHIC", "IMAGEMAP", "FIGURE", "CANVAS", "CHART", "DIAGRAM", "ANIMATION"))
# Only what says it is a picture; "logo", "banner" or "download" say a little more, and are a label.
_PICTURE_ONLY = _wordsPattern(
	"image|img|images|graphic|graphics|picture|pic|photo|photograph|foto|icon|spacer|thumbnail|thumb|placeholder|blank"
	"|dummy|alt|alt text|no alt|pixel|transparent|figure|screen shot|screenshot|svg|canvas|untitled|unlabeled|unlabelled"
	"|unnamed")
_HEX_CODE = re.compile(r"^\s*[0-9a-f-]{16,}\s*$", re.IGNORECASE)


def said(text):
	"""The characters of a text that NVDA can say: letters, digits, punctuation, signs and emoji, without the pictures of
	an icon font and the characters that are never printed."""
	return "".join(char for char in str(text or "") if unicodedata.category(char) not in _UNSAID)


def unlabelled(name, role=""):
	"""Whether the name an accessibility interface gives an object is no label at all, so that the object is truly
	unlabelled: nothing, or only what NVDA cannot say (spaces, the pictures of an icon font, characters never printed);
	a word a program gives only by a mistake ("undefined", "null", "unlabeled"); only the word NVDA says for its kind
	anyway ("button" on a button); on a control, a long code of hexadecimal digits; and on a picture, the file it was
	made from, a web address or a word that only says it is a picture. Everything else is its label, however short or
	odd: one letter or digit (a page number, a key of an on-screen keyboard), a sign such as + or ×, an emoji, a file
	name in a list of files, a name from the program's code such as btnClose."""
	text = " ".join(str(name or "").split())
	if not said(text).strip():
		return True
	if len(text) > 200:
		return False
	if _NO_LABEL.match(text) and role in NAMED:
		return True
	pattern = _ROLE_ONLY_PATTERN.get(role)
	if pattern is not None and pattern.match(text):
		return True
	if role in _UNLABELLED_PICTURES:
		return bool(_FILEISH.search(text) or _PICTURE_ONLY.match(text))
	return role in NAMED and bool(_HEX_CODE.match(text))


def labelled(name, role="", others=()):
	"""Whether an object has a label from the accessibility interfaces: its own name, or any of others, which are what
	the interfaces say of it besides: its description (a tooltip, aria-describedby, the title of a web page's element,
	UI Automation's help text), the hint written in an empty field (placeholder), and the name of the object that
	labels it (labelledBy)."""
	if not unlabelled(name, role):
		return True
	return any(not unlabelled(other) for other in others or () if other)


def interfaceName(role, label="", inside=""):
	"""The label the accessibility interfaces give an object whose own name is no label, said as it is, without a model:
	the name of the object that labels it (labelledBy, which NVDA does not say by itself), else, for a control named by
	what it holds (BY_CONTENT), the words of the objects inside it, which NVDA reads in browse mode but not on the focus.
	"" when neither is a label."""
	for text in (label, inside if role in BY_CONTENT else ""):
		text = " ".join(str(text or "").split())
		if text and not unlabelled(text):
			return text[:150].rstrip()
	return ""


def wanted(role, states=(), name="", text="", hidden=False, others=(), holds=False):
	"""Whether an object is truly unlabelled and so is named by the model: its role is one that is named, it can be
	seen, nothing the interfaces say of it is a label (labelled, with others), a control named by what is inside it
	(BY_CONTENT) has no words inside it, and a holder (WHEN_CLICKABLE) is something to press or move to (clickable),
	holds no other objects (holds) and has no text of its own. text: the words inside it, as NVDA reads them."""
	if hidden or role not in NAMED and role not in WHEN_CLICKABLE:
		return False
	if any(state in UNSEEN_STATES for state in states or ()):
		return False
	if labelled(name, role, others):
		return False
	if role in WHEN_CLICKABLE:
		return not holds and clickable(states, role) and unlabelled(text, role)
	if role in BY_CONTENT:
		return unlabelled(text, role)
	return True


# --- What tells an object apart ---

RULE = "rule:"
PICTURE = re.compile(r"^[0-9a-f]{20}$")


def ruleFor(node, dialog=""):
	"""What finds this object again in its program or on its website, from what is fixed in its own code, or None.
	Only what belongs to one object: its id, its automation id, the file of its picture, or, inside a dialog with a
	title, its control number. Class names are shared by unrelated objects, so a name is never hung on them."""
	role = node.get("role") or ""
	if audit.stableId(node.get("ident")):
		return {"role": role, "ident": node["ident"]}
	if audit.stableId(node.get("autoId")):
		return {"role": role, "autoId": node["autoId"]}
	if node.get("src"):
		return {"role": role, "src": node["src"]}
	if node.get("controlId") and dialog:
		return {"role": role, "controlId": node["controlId"], "windowClass": node.get("windowClass") or "",
			"dialog": " ".join(str(dialog).split())[:80]}
	return None


def ruleKey(rule):
	return None if not rule else RULE + json.dumps(rule, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fieldNode(field):
	"""A control of a web page in browse mode, as plain facts, from NVDA's facts about it."""
	return nodeFromField(field)


def webScope(address):
	"""Where a name on a web page is kept: "site:example.com", or None."""
	from .fixmatch import hostOf
	host = hostOf(address)
	return f"site:{host}" if host and "." in host else None


def placeWords(scope):
	"""A scope in words: "the website example.com", "the program spotify"."""
	scope = str(scope or "")
	if scope.startswith("site:"):
		return f"the website {scope[5:]}"
	return f"the program {scope or 'unknown'}"


# --- Browse mode: which controls of a stretch of a page need a name ---

def fieldOthers(field):
	"""What NVDA's copy of a page says of a control besides its name: its description (aria-describedby, the title of
	the element) and the hint written in an empty field (placeholder; NVDA keeps it only while the field is empty, the
	browser always)."""
	field = field or {}
	return [str(field.get(key) or "") for key in ("description", "placeholder", "IAccessible2::attribute_placeholder")]


def insideControl(entry):
	"""Whether a control of a stretch of a page is inside a link, a button or another control named by what it holds,
	at any depth."""
	up = entry.get("up")
	while up is not None:
		if up["node"]["role"] in BY_CONTENT:
			return True
		up = up.get("up")
	return False


def candidates(commands, limit=2):
	"""The controls in a stretch of a web page, as NVDA gives it in browse mode (texts, and fields that start and end),
	that are truly unlabelled (wanted): [(field, node, before, after)], up to limit, in reading order. A picture that is
	part of a link, a button or another control is left: that control is the one named, where it needs a name. before
	and after are the named controls around it, each (kind, name), for the model that names it."""
	stack, found, named = [], [], []
	for command in commands:
		if isinstance(command, str):
			for entry in stack:
				if len(entry["text"]) < 300:
					entry["text"] += command
			continue
		kind = getattr(command, "command", None)
		if kind == "controlStart":
			field = command.field
			node = nodeFromField(field)
			entry = {"field": field, "node": node, "text": "", "up": stack[-1] if stack else None, "at": len(named)}
			stack.append(entry)
			if node["name"] and not vague(node["name"], node["role"]):
				named.append((kindWord(node["role"]), node["name"]))
			found.append(entry)
		elif kind == "controlEnd" and stack:
			stack.pop()
	out = []
	for entry in found:
		node = entry["node"]
		text = " ".join(entry["text"].split())
		holds = any(other["up"] is entry for other in found)
		if not wanted(node["role"], node["states"], node["name"], text, node["hidden"], fieldOthers(entry["field"]), holds):
			continue
		if node["role"] in PICTURES and insideControl(entry):
			continue  # a picture that is part of a link, a button or another control: that control is what is named
		before = named[max(0, entry["at"] - working.NEIGHBOURS):entry["at"]]
		after = named[entry["at"]:entry["at"] + working.NEIGHBOURS]
		out.append((entry["field"], node, before, after))
		if len(out) >= limit:
			break
	return out


# --- How sure a name is ---

def _words(text):
	return [word for word in plainText(text).split() if word]


def _alike(one, other):
	return one == other or min(len(one), len(other)) >= 4 and (one.startswith(other) or other.startswith(one))


def sure(name, read="", code=""):
	"""Whether a name is sure rather than probable: the text read in the object's own picture says it, or what the
	object's own code calls it agrees with it. A name the model gave from an icon alone is only probable."""
	words = _words(name)
	if not words:
		return False
	seen = _words(read)
	if seen and len(seen) <= len(words) + 2 and all(any(_alike(word, other) for other in seen) for word in words):
		return True
	called = _words(code)
	return bool(called) and any(_alike(word, other) for word in words for other in called if len(other) >= 3)


def readName(read):
	"""A name from the text read in an object's own picture, where it is short and made of words: "" otherwise."""
	words = str(read or "").split()
	if not 1 <= len(words) <= 4:
		return ""
	if sum(len(_letters(word)) for word in words) < 2 or any(not _letters(word) for word in words):
		return ""
	text = " ".join(words).strip(" .:;,")
	return text if not vague(text) else ""


def withoutKind(name, role=""):
	"""A name without the word for the object's kind at its end, which NVDA says itself right after the name: "Search
	field" on an edit field is Search, "Shuffle toggle button" on a toggle button is Shuffle. Nothing is taken where
	nothing would be left. A state is not taken off: "Delete selected" is a name."""
	text = " ".join(str(name or "").split())
	if not text:
		return ""
	kinds = [word for word in (_ROLE_ONLY.get(role, "").split("|") + [kindWord(role)]) if word and word != "control"]
	if role in ("EDITABLETEXT", "PASSWORDEDIT", "COMBOBOX"):
		kinds += ["field", "box"]
	for kind in sorted(set(kinds), key=len, reverse=True):
		if text.lower().endswith(" " + kind):
			text = text[:-len(kind)].rstrip(" ,;:-")
			break
	return text


def decide(modelName, read="", code="", role=""):
	"""(name, sure) from what the model that sees answered, the text read in the object's own picture, and what its
	code calls it. The model's name first; where it gave none, the text in the picture, then the code's words; each
	of those alone is only probable. ("", False) when nothing gave a name. A model's name that is itself vague is no
	name: asked about a field with nothing around it, Qwen3.5 4B answered "Edit field" (tests/live_object_names.py,
	2026-11-19)."""
	modelName = withoutKind(modelName, role)
	if modelName and vague(modelName, role):
		modelName = ""
	if modelName:
		return modelName, sure(modelName, read, code)
	text = readName(read)
	if text:
		return text, bool(code) and sure(text, "", code)
	words = audit.codeWords(code) if code else []
	if words:
		name = " ".join(words[:3])
		return name[:1].upper() + name[1:], False
	return "", False


PROBABLY = "probably {name}"
# Who gave a name.
YOU, PERSON, MODEL = "you", "person", "model"


def spoken(entry, probably=PROBABLY):
	"""The name as NVDA says it: as it is where a person gave it or it is sure, else with "probably" before it."""
	if not entry or not entry.get("name"):
		return ""
	if entry.get("by") in (YOU, PERSON) or entry.get("sure"):
		return entry["name"]
	return probably.format(name=entry["name"])


def overrides(entry):
	"""Whether a saved name is said even where the object has a label of its own: a name the user gave, or one the user
	asked the model for. A name the model gave by itself is said only where the object is truly unlabelled."""
	return bool(entry) and (entry.get("by") == YOU or bool(entry.get("asked")))


def question(role, around=""):
	"""The question about the picture of one object without a name: working.nameQuestion, measured with drawn buttons.
	A field is shown with what is before and above it (pictureBox). A sentence for fields that said where its label
	usually is was measured on 2026-11-19 with Qwen3.5 4B and changed nothing (10 of 11 drawn fields with it and
	without, tests/live_object_names.py), so it is not added."""
	return working.nameQuestion(kindWord(role), around)


def pictureBox(role, box, bounds=None):
	"""The part of the screen to show the model: the object with a little room around it, and for a field what is
	before and above it too, kept inside bounds (left, top, right, bottom) where they are known. Sizes are shares of
	the object, never fixed pixels."""
	left, top, right, bottom = box
	width, height = right - left, bottom - top
	if role in FIELDS:
		# Eight times its height before it, whatever its width: a narrow field such as a spin box has its label
		# beside it too (with its own width, "Quantity" was cut to "antity", seen on 2026-11-19).
		left -= max(height * 8, 1)
		top -= height
		right += max(1, height // 4)
		bottom += max(1, height // 4)
	else:
		margin = max(2, min(width, height) // 4)
		left, top, right, bottom = left - margin, top - margin, right + margin, bottom + margin
	if bounds:
		left, top = max(left, bounds[0]), max(top, bounds[1])
		right, bottom = min(right, bounds[2]), min(bottom, bounds[3])
	return (left, top, right, bottom)


def billions(modelName):
	"""How many billion parameters a model has, from its name ("Qwen3.5 9B" is 9), or None."""
	found = re.search(r"(\d+(?:\.\d+)?)\s*B\b", str(modelName or ""))
	return float(found.group(1)) if found else None


# The largest model that is suggested for naming objects on the fly: the owner said on 2026-11-19 that, because
# these are fixes made as the user moves, a small model, 7B or less, is best.
SMALL_ENOUGH = 7


FIRST_SAID = ("This is said once: object names are accessibility fixes made on the fly, as you move, so a small model, "
	"{size}B or smaller, is best for them: it names an object quickly.")
FIRST_LARGER = "The {model} you use now, {name}, is larger, so names may come slowly."
FIRST_CHOOSE = "You can choose another model in the models window, NVDA+Alt+M."


def firstTimeText(modelName="", modelWord="vision model", said=FIRST_SAID, larger=FIRST_LARGER, choose=FIRST_CHOOSE):
	"""What is said once, the first time object names are turned on: that a small model is best for them, and the
	model in use where it is larger. A suggestion: nothing is changed. modelWord is policy.roleName's word, "model"
	when one model does both jobs. The sentences are given translated by the NVDA side."""
	text = said.format(size=SMALL_ENOUGH)
	size = billions(modelName)
	if size is not None and size > SMALL_ENOUGH:
		text += " " + larger.format(model=modelWord, name=modelName)
	return text + " " + choose


# --- The names kept ---

# Names guessed by a model kept for each program or website. Older ones are dropped first.
MAX_GUESSES = 2000
SHARE_FORMAT = 1
MAX_SHARED = 20000
MAX_SHARED_BYTES = 5 * 1024 * 1024
MAX_NAME = 60
_RULE_KEYS = {"role": str, "ident": str, "autoId": str, "src": str, "controlId": int, "windowClass": str, "dialog": str}
_SCOPE = re.compile(r"^(site:[a-z0-9.-]{1,120}|[\w .+-]{1,80})$")
_TEXT_KEY = re.compile(r"^t:.{1,200}$", re.DOTALL)


def cleanName(name):
	"""A name as it is kept: one line, no characters that are not printed, at most MAX_NAME characters; or ""."""
	text = "".join(char if unicodedata.category(char)[0] != "C" else " " for char in str(name or ""))
	text = " ".join(text.split())
	return text[:MAX_NAME].rstrip()


def checkKey(key):
	"""Whether a kept key is one of VisionClaw's: a picture's (20 hexadecimal characters), a text of the overlay
	("t:..."), or a rule of plain facts."""
	key = str(key or "")
	if PICTURE.match(key) or _TEXT_KEY.match(key) and len(key) <= 202:
		return True
	if not key.startswith(RULE) or len(key) > 400:
		return False
	try:
		rule = json.loads(key[len(RULE):])
	except ValueError:
		return False
	if not isinstance(rule, dict) or not rule or "role" not in rule:
		return False
	for name, value in rule.items():
		kind = _RULE_KEYS.get(name)
		if kind is None or not isinstance(value, kind) or isinstance(value, bool):
			return False
		if kind is str and len(value) > 120:
			return False
	return True


class NameStore:
	"""The names of objects, for each program ("spotify") and website ("site:example.com"), in one JSON file that
	survives restarts and updates. Each place has "user" (names the user gave) and "guess" (every other name), key to
	name, as VisionClaw 1.12 and older kept them, so that an older VisionClaw still reads the file; and "about", key to
	{"by", "sure", "role", "saved"}. A name the user gave always wins; a model's guess never replaces a name a person
	gave."""

	def __init__(self, path):
		self._path = path
		self._lock = threading.RLock()
		self._data = {}
		self._dirty = False
		self.version = 0
		try:
			with open(path, encoding="utf-8") as f:
				data = json.load(f)
			if isinstance(data, dict):
				self._data = {scope: entry for scope, entry in data.items() if isinstance(entry, dict)}
		except FileNotFoundError:
			pass
		except (OSError, ValueError):
			self.readFailed = True

	def _place(self, scope, make=True):
		scope = scope or "?"
		entry = self._data.get(scope)
		if entry is None and make:
			entry = self._data[scope] = {}
		if entry is not None:
			for part in ("user", "guess", "about"):
				if not isinstance(entry.get(part), dict):
					entry[part] = {}
		return entry

	def _changed(self):
		self._dirty = True
		self.version += 1

	def get(self, scope, key):
		"""(name, byUser), or (None, False): as VisionClaw 1.12 asked."""
		found = self.entry(scope, key)
		if not found:
			return None, False
		return found["name"], found["by"] == YOU

	def entry(self, scope, key):
		"""{"name", "by", "sure", "role"} for a key, or None."""
		if not key:
			return None
		with self._lock:
			place = self._place(scope, make=False)
			if not place:
				return None
			about = place["about"].get(key) or {}
			if key in place["user"]:
				return {"name": place["user"][key], "by": YOU, "sure": True, "role": about.get("role", "")}
			name = place["guess"].get(key)
			if not name:
				return None
			by = about.get("by") if about.get("by") in (PERSON, MODEL) else MODEL
			found = {"name": name, "by": by, "sure": bool(about.get("sure")), "role": about.get("role", "")}
			if about.get("asked"):
				found["asked"] = True
			return found

	def overriding(self, scope=None):
		"""Whether a place has names that are said even where the object has a label of its own (overrides): names the
		user gave, and names the user asked the model for. Without a place: whether any place has."""
		kinds = self.overrideKinds()
		return bool(kinds) if scope is None else scope in kinds

	def overrideKinds(self, scope=None):
		"""How the overrides of a place are kept: a set of "rule" (by what the object's code calls it) and "picture" (by
		its picture). Without a place: {place: kinds} for every place that has any. Counted again only when the names
		change."""
		with self._lock:
			if getattr(self, "_overridingAt", None) != self.version:
				self._overridingAt = self.version
				places = {}
				for place, entry in self._data.items():
					if not isinstance(entry, dict):
						continue
					about = entry.get("about") if isinstance(entry.get("about"), dict) else {}
					keys = list(entry.get("user") or {}) + [key for key, facts in about.items()
						if isinstance(facts, dict) and facts.get("asked") and key in (entry.get("guess") or {})]
					kinds = {"rule" if str(key).startswith(RULE) else "picture" for key in keys}
					if kinds:
						places[place] = kinds
				self._overridingPlaces = places
			if scope is None:
				return self._overridingPlaces
			return self._overridingPlaces.get(scope, set())

	def setUser(self, scope, key, name, role=""):
		"""A name the user gave; an empty name takes the user's name away."""
		name = cleanName(name)
		with self._lock:
			place = self._place(scope)
			if name:
				place["user"][key] = name
				place["about"][key] = {"by": YOU, "sure": True, "role": role, "saved": _today()}
			else:
				place["user"].pop(key, None)
				if key not in place["guess"]:
					place["about"].pop(key, None)
			self._changed()
		self.save()

	def setGuess(self, scope, key, name, sure=False, role="", by=MODEL, asked=False):
		"""A name a model gave, or a person in a shared file (by=PERSON). It never replaces the user's own name, and a
		model's never replaces a person's. asked: the user asked the model for this name (NVDA+Shift+Alt+B), so it is
		said even where the object has a label of its own, and a name the model gives by itself never replaces it.
		Returns whether it was kept."""
		name = cleanName(name)
		if not name or not key:
			return False
		with self._lock:
			place = self._place(scope)
			if key in place["user"]:
				return False
			old = place["about"].get(key) or {}
			if by == MODEL and key in place["guess"] and (old.get("by") == PERSON or old.get("asked") and not asked):
				return False
			place["guess"].pop(key, None)
			place["guess"][key] = name
			place["about"][key] = {"by": by, "sure": bool(sure), "role": role, "saved": _today()}
			if asked:
				place["about"][key]["asked"] = True
			guesses = place["guess"]
			if len(guesses) > MAX_GUESSES:
				for oldKey in list(guesses):
					if len(guesses) <= MAX_GUESSES:
						break
					if (place["about"].get(oldKey) or {}).get("by") != PERSON:
						guesses.pop(oldKey)
						place["about"].pop(oldKey, None)
			self._changed()
		return True

	def forget(self, scope, key):
		with self._lock:
			place = self._place(scope, make=False)
			if not place:
				return False
			found = place["user"].pop(key, None) is not None
			found = place["guess"].pop(key, None) is not None or found
			place["about"].pop(key, None)
			if found:
				self._changed()
		self.save()
		return found

	def forgetPlace(self, scope):
		with self._lock:
			found = self._data.pop(scope, None) is not None
			if found:
				self._changed()
		self.save()
		return found

	def places(self):
		"""[(scope, how many names)], the places with names, by their words."""
		with self._lock:
			found = []
			for scope, place in self._data.items():
				count = len(set(place.get("user") or {}) | set(place.get("guess") or {}))
				if count:
					found.append((scope, count))
		return sorted(found, key=lambda item: placeWords(item[0]).lower())

	def entries(self, scope):
		"""[(key, entry)] of one place, by name."""
		with self._lock:
			place = self._place(scope, make=False)
			if not place:
				return []
			keys = list(place["user"]) + [key for key in place["guess"] if key not in place["user"]]
		found = [(key, self.entry(scope, key)) for key in keys]
		return sorted([item for item in found if item[1]], key=lambda item: item[1]["name"].lower())

	# --- Sharing ---

	def shared(self, scopes, maker=""):
		"""The names of some places as a file to give to other VisionClaw users: plain data, no code. A name the user
		gave goes as a person's."""
		names = []
		for scope in scopes:
			for key, found in self.entries(scope):
				names.append({"place": scope, "key": key, "name": found["name"], "sure": bool(found["sure"]),
					"by": PERSON if found["by"] in (YOU, PERSON) else MODEL, "role": found.get("role") or ""})
		return {"visionclaw-names": SHARE_FORMAT, "made": _today(), "maker": maker, "names": names}

	def addShared(self, data):
		"""Names from a file another VisionClaw user shared (readShared). Never replaces the user's own names, nor a
		name a person gave; replaces a model's guess with a person's name or a sure one. Returns (added, replaced,
		kept)."""
		added = replaced = kept = 0
		for item in readShared(data):
			old = self.entry(item["place"], item["key"])
			if old is None:
				self.setGuess(item["place"], item["key"], item["name"], item["sure"], item["role"], item["by"])
				added += 1
			elif old["by"] == MODEL and not old["sure"] and (item["by"] == PERSON or item["sure"]):
				self.setGuess(item["place"], item["key"], item["name"], item["sure"], item["role"], item["by"])
				replaced += 1
			else:
				kept += 1
		self.save()
		return added, replaced, kept

	def save(self):
		with self._lock:
			if not self._dirty:
				return True
			data = json.dumps(self._data, ensure_ascii=False)
			self._dirty = False
		tmp = self._path + ".tmp"
		try:
			with open(tmp, "w", encoding="utf-8") as f:
				f.write(data)
			os.replace(tmp, self._path)
			return True
		except OSError:
			with self._lock:
				self._dirty = True
			return False


def readShared(data):
	"""The names in a shared file, checked: only plain text and numbers of the kinds VisionClaw keeps, nothing else.
	Raises ValueError with a sentence for the user when the file is not one."""
	if isinstance(data, (bytes, bytearray)):
		if len(data) > MAX_SHARED_BYTES:
			raise ValueError("This file is too big to be a file of names.")
		data = data.decode("utf-8-sig", "replace")
	if isinstance(data, str):
		if len(data) > MAX_SHARED_BYTES:
			raise ValueError("This file is too big to be a file of names.")
		try:
			data = json.loads(data)
		except ValueError:
			raise ValueError("This is not a file of names that VisionClaw shared.") from None
	if not isinstance(data, dict) or data.get("visionclaw-names") != SHARE_FORMAT or not isinstance(data.get("names"), list):
		raise ValueError("This is not a file of names that VisionClaw shared, or it comes from a newer VisionClaw.")
	names = data["names"]
	if len(names) > MAX_SHARED:
		raise ValueError(f"This file has more than {MAX_SHARED} names, which is more than VisionClaw takes.")
	clean = []
	for item in names:
		if not isinstance(item, dict):
			continue
		place, key, name = item.get("place"), item.get("key"), cleanName(item.get("name"))
		role = item.get("role") if isinstance(item.get("role"), str) and re.match(r"^[A-Z_0-9]{0,30}$", item["role"]) else ""
		if not (isinstance(place, str) and _SCOPE.match(place) and checkKey(key) and name and not vague(name, role)):
			continue
		by = PERSON if item.get("by") == PERSON else MODEL
		clean.append({"place": place, "key": key, "name": name, "sure": item.get("sure") is True, "by": by, "role": role})
	return clean


def _today():
	return datetime.date.today().isoformat()


def describe(entry):
	"""Who gave a name and how sure it is, in words, for the names window."""
	if entry["by"] == YOU:
		return "your name"
	if entry["by"] == PERSON:
		return "shared by a person"
	text = "read from its picture, sure" if entry.get("sure") else "guessed by the model, said with probably"
	return "asked for by you, " + text if entry.get("asked") else text
