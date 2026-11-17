# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the deep inspection of a web page or a program's window: what stands in the way of a screen
# reader user, said in plain sentences, and for each problem the fixes an add-on can make. Everything here is
# plain code working on plain data (the controls as dictionaries, see fixmatch.py), so the same page always
# gives the same findings and nothing is claimed that was not counted. A model is only asked for what code
# cannot know: what an icon without a name shows. No NVDA dependencies.

import json
import re

from . import fixes
from .fixmatch import labelOf, matches, plainText

# Controls a user acts on. NVDA's own names for the kinds.
INTERACTIVE = (
	"BUTTON", "LINK", "EDITABLETEXT", "PASSWORDEDIT", "COMBOBOX", "CHECKBOX", "RADIOBUTTON", "SLIDER", "TAB", "MENUITEM",
	"TOGGLEBUTTON", "SWITCH", "MENUBUTTON", "SPINBUTTON", "SPLITBUTTON", "DROPDOWNBUTTON", "TREEVIEWITEM",
)
PRESSABLE = ("BUTTON", "TOGGLEBUTTON", "MENUBUTTON", "LINK", "MENUITEM", "TAB", "SWITCH", "CHECKBOX")
# Controls whose name NVDA takes from the text inside them. The others (fields) need a name of their own.
_NAMED_BY_TEXT = ("BUTTON", "LINK", "TOGGLEBUTTON", "MENUBUTTON", "MENUITEM", "TAB", "GRAPHIC", "CHECKBOX", "RADIOBUTTON", "SWITCH")
_NEED_NAMES = tuple(role for role in INTERACTIVE if role != "TREEVIEWITEM")
_KIND_WORDS = {
	"BUTTON": "button", "TOGGLEBUTTON": "button", "MENUBUTTON": "button", "LINK": "link", "GRAPHIC": "image",
	"EDITABLETEXT": "edit field", "PASSWORDEDIT": "password field", "COMBOBOX": "combo box", "CHECKBOX": "checkbox",
	"RADIOBUTTON": "radio button", "SLIDER": "slider", "TAB": "tab", "MENUITEM": "menu item", "SWITCH": "switch",
}
# Names that say nothing about what a control does.
_GENERIC = frozenset((
	"button", "link", "image", "icon", "click here", "here", "more", "read more", "learn more", "click", "go",
	"details", "info", "this", "graphic", "img", "untitled", "unlabeled", "unlabelled",
))
# Words in a page's code that say nothing about what a control is for.
_FILLER = frozenset((
	"btn", "button", "buttons", "icon", "icons", "ico", "img", "image", "link", "svg", "png", "jpg", "gif", "nav", "navbar",
	"wrapper", "wrap", "container", "box", "item", "control", "ctrl", "widget", "component", "root", "main", "base",
	"default", "primary", "secondary", "small", "large", "medium", "big", "material", "glyphicon", "the", "and", "for",
	"action", "actions", "inner", "outer", "content", "label", "text", "class", "style", "active", "hover", "focus",
	"round", "circle", "square", "flat", "outline", "solid", "light", "dark", "white", "black", "ytp", "size",
))
# Controls of a video or audio player, by the names sites give them: (names, what to call the key's target).
_PLAYER = (
	(("play", "pause", "play pause", "play video", "pause video", "resume"), "Play or pause"),
	(("mute", "unmute", "mute video", "unmute video", "volume"), "Mute"),
	(("full screen", "fullscreen", "exit full screen", "enter full screen", "exit fullscreen"), "Full screen"),
	(("captions", "subtitles", "closed captions", "subtitles closed captions", "cc"), "Captions"),
	(("skip ad", "skip ads", "skip", "skip intro", "skip recap"), "Skip"),
	(("next", "next video", "next episode"), "Next"),
)
_TIME = re.compile(r"^\d{1,2}:\d\d(:\d\d)?(\s*/\s*\d{1,2}:\d\d(:\d\d)?)?$")
_ALL = frozenset(("all", "everything", "every", "whole", "entire", "anything", "problems", "issues", "accessible", "accessibility"))
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8}
REPORT_CHARS = 1150
MAX_LOOKS = 8


# --- What a request asks for, from its words ---

TARGETS = ["auto", "page", "window", "control"]
DEPTHS = ["deep", "quick"]
FIX_KINDS = ["press", "read", "move", "name", "announce"]


def targetOf(part):
	"""What a request wants inspected, from its words: the web page, the window, or the focused control."""
	text = (part or "").lower()
	wide = re.search(r"\b(web ?page|page|web ?site|site|window|program|app|application|game|browser)\b", text)
	if not wide and re.search(r"\b(this|the|focused|current) (button|control|icon|item|field|link|checkbox|slider|image)\b", text):
		return "control"
	if re.search(r"\b(web ?page|page|web ?site|site|browser)\b", text):
		return "page"
	if re.search(r"\b(window|program|app|application|game|dialog)\b", text):
		return "window"
	return "auto"


def depthOf(part):
	"""A request to inspect or fix problems gets the deep inspection, which watches for changes and reads the
	picture; a request for one key or one name only needs to know what is there."""
	deep = re.search(
		r"inspect|audit|check|accessib|problem|issue|deep|wrong|usable|examin|analy[sz]e|review|everything|\ball\b"
		r"|\b(fix|repair|solve|correct)\b|\bnumber \d", (part or "").lower())
	return "deep" if deep else "quick"


def kindOf(part):
	"""Which kind of fix a request asks for, from its words."""
	text = (part or "").lower()
	if re.search(r"\b(name|label|call|rename)\b", text) and not re.search(r"\bkey\b|hot ?key|shortcut", text):
		return "name"
	if re.search(r"tell me when|let me know when|announce|whenever|when(ever)? .*\bchanges?\b|\b(watch|monitor)\b|automatically|by itself", text):
		return "announce"
	if re.search(r"\b(next|previous|between|jump|move|go (from|through)|skip)\b", text):
		return "move"
	if re.search(r"\b(read|reads|say|says|speak|speaks|hear|tell me)\b", text):
		return "read"
	return "press"


# --- Reading a page that came in stretches ---

def joinChunks(chunks):
	"""One list of controls, each once and in reading order, from the stretches a long page was read in.
	A control that runs across two stretches comes twice; its parts are joined."""
	known, nodes = {}, []
	for chunk in chunks:
		for node in chunk:
			key = node.get("key")
			first = known.get(key) if key is not None else None
			if first is None:
				if key is not None:
					known[key] = node
				nodes.append(node)
				continue
			if first.get("open"):
				first["raw"] = (first.get("raw", first["text"]) + node.get("raw", node["text"]))[:600]
				first["text"] = " ".join(first["raw"].split())[:300]
				first["end"] = node.get("end", first.get("end"))
				first["open"] = node.get("open", False)
	# A control's "up" may point at a second copy of the control it is inside; point it at the first.
	for node in nodes:
		up = node.get("up")
		if up is not None and up.get("key") is not None:
			node["up"] = known.get(up["key"], up)
	return nodes


# --- What tells a control apart, and what its code calls it ---

def _hasVowel(word):
	return any(char in "aeiouy" for char in word)


def telling(token):
	"""Whether a class name from a page's code looks written by a person ("btn-close") rather than made by a
	tool ("x1n2onr6", "css-1dbjc4n"). Made-up names are shared by controls that have nothing in common, and
	change when the site is rebuilt, so nothing is hung on them."""
	parts = [p for p in re.split(r"[-_]+", token) if p]
	if not parts or len(token) > 40:
		return False
	word = False
	for part in parts:
		if part.isdigit() and len(part) <= 2:
			continue
		if not part.isalpha():
			return False
		if len(part) >= 3 and _hasVowel(part.lower()):
			word = True
	return word


def stableId(ident):
	"""Whether an id from a page's or program's code looks fixed, not counted up or made at random."""
	text = str(ident or "")
	return bool(text) and len(text) <= 60 and not re.search(r"\d{3,}|[:.\s]", text) and telling(re.sub(r"\d", "", text) or "x")


def codeWords(text):
	"""The plain words in a name from code: "playPauseBtn" gives play, pause."""
	spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(text or ""))
	found = []
	for word in re.split(r"[^A-Za-z]+", spaced):
		word = word.lower()
		if len(word) >= 3 and _hasVowel(word) and word not in _FILLER and word not in found:
			found.append(word)
	return found


def codeName(node):
	"""A name for a control from what its own code calls it, such as "close" from the class "btn-close".
	"" when the code says nothing clear."""
	sources = []
	if stableId(node.get("ident")):
		sources.append(node["ident"])
	if stableId(node.get("autoId")):
		sources.append(node["autoId"])
	sources += [token for token in node.get("cls") or () if telling(token)]
	if node.get("src"):
		sources.append(node["src"].rsplit(".", 1)[0])
	for source in sources:
		words = codeWords(source)
		if 1 <= len(words) <= 3:
			return " ".join(words)
	return ""


def signature(node):
	"""A rule that finds this control again on a later visit, from what is fixed in its code, or None when
	nothing about it is fixed. It always includes the control's kind."""
	rule = {"role": node.get("role") or ""}
	if stableId(node.get("ident")):
		rule["ident"] = node["ident"]
	elif stableId(node.get("autoId")):
		rule["autoId"] = node["autoId"]
	elif node.get("controlId"):
		rule["controlId"] = node["controlId"]
		if node.get("windowClass"):
			rule["windowClass"] = node["windowClass"]
	elif node.get("src"):
		rule["src"] = node["src"]
	else:
		tokens = [token for token in node.get("cls") or () if telling(token)][:3]
		if tokens:
			rule["cls"] = tokens
			if node.get("tag"):
				rule["tag"] = node["tag"]
		elif "-" in (node.get("tag") or ""):
			rule["tag"] = node["tag"]  # a site's own element, like ytd-video-renderer
		else:
			return None
	return rule


def cleanName(answer):
	"""A name for a control from what a vision model answered, or "" if it gave none worth using."""
	line = str(answer or "").strip().splitlines()[0] if str(answer or "").strip() else ""
	line = re.sub(r"^(name|answer|it is|this is|the|a|an)\b[:\s]*", "", line.strip(" \"'.,:;!*`"), flags=re.IGNORECASE)
	words = [word for word in re.split(r"[^\w+&-]+", line) if word]
	text = " ".join(words)
	if not 1 <= len(words) <= 4 or len(text) > 40 or plainText(text) in _GENERIC | {"unknown", "none", "unclear", "picture", "n a"}:
		return ""
	return text[0].upper() + text[1:]


def isUnnamed(node):
	if node.get("hidden"):
		return False
	if node.get("role") in _NAMED_BY_TEXT:
		return not plainText(labelOf(node))
	return not plainText(node.get("name"))


def _ruleKey(rule):
	return json.dumps(rule, sort_keys=True)


def _plural(count, word):
	if count == 1:
		return f"1 {word}"
	return f"{count} {word[:-1] + 'ies' if word.endswith('y') and not word.endswith('ey') else word + ('es' if word.endswith(('x', 's')) else 's')}"


# --- Findings ---

class Finding:
	"""One problem. text: the sentence for the user. fixes: fixes an add-on can make for it, without keys yet.
	look: controls a vision model must look at to name them, as {"rule", "nodes", "kind"}. words: what a user
	might call this problem."""

	def __init__(self, ident, text, words="", fixes=None, look=None, advice=""):
		self.id = ident
		self.text = text
		self.words = frozenset(words.split())
		self.fixes = fixes or []
		self.look = look or []
		self.advice = advice
		self.number = 0

	@property
	def fixable(self):
		return bool(self.fixes or self.look)


class Report:
	def __init__(self, kind, title, scope, summary, findings):
		self.kind = kind  # "page" or "window"
		self.title = title
		self.scope = scope
		self.summary = summary
		self.findings = findings
		for number, finding in enumerate(findings, 1):
			finding.number = number

	def text(self):
		"""The report as it is said to the user: what was checked, each problem, and what can be done."""
		lines = [self.summary]
		if not self.findings:
			lines.append(
				"None of the problems VisionClaw checks for were found. That does not prove everything here is easy to use.")
			return " ".join(lines)
		lines.append(f"Found {_plural(len(self.findings), 'problem')}.")
		used = sum(len(line) for line in lines)
		told = 0
		for finding in self.findings:
			line = f"{finding.number}. {finding.text}" + (f" {finding.advice}" if finding.advice else "")
			if told and used + len(line) > REPORT_CHARS:
				lines.append(f"And {_plural(len(self.findings) - told, 'more problem')}; ask about a number to hear it.")
				break
			lines.append(line)
			used += len(line)
			told += 1
		fixable = [finding.number for finding in self.findings if finding.fixable]
		if fixable:
			which = "all of them" if len(fixable) == len(self.findings) else "number " + ", ".join(str(n) for n in fixable)
			lines.append(
				f"VisionClaw can fix {which} with an add-on for {fixes.scopeText(self.scope)}, which stays until you "
				"have it removed. Ask for all of it to be fixed, or for one number.")
		return " ".join(lines)


def _unnamed(nodes, roles, kind):
	"""The finding for controls that have no name, with the names code can give and what a model must look at."""
	missing = [node for node in nodes if node.get("role") in roles and isUnnamed(node)]
	if not missing:
		return None
	groups, loose = {}, []
	for node in missing:
		rule = signature(node)
		if rule is None:
			loose.append(node)
			continue
		groups.setdefault(_ruleKey(rule), (rule, []))[1].append(node)
	made, look, mixed = [], [], 0
	for rule, members in groups.values():
		# A rule is only safe if everything it finds lacks a name; else it would rename what is named.
		if any(not isUnnamed(node) for node in nodes if matches(rule, node)):
			mixed += len(members)
			continue
		name = codeName(members[0])
		if name:
			made.append({"kind": fixes.NAME, "rule": rule, "label": name})
		else:
			look.append({"rule": rule, "nodes": members, "kind": _KIND_WORDS.get(members[0]["role"], "control")})
	counts = {}
	for node in missing:
		word = _KIND_WORDS.get(node["role"], "control")
		counts[word] = counts.get(word, 0) + 1
	listed = ", ".join(_plural(count, word) for word, count in sorted(counts.items(), key=lambda x: -x[1]))
	text = f"{listed} {'has' if len(missing) == 1 else 'have'} no name, so NVDA only says what kind of control it is."
	nameable = sum(len(members) for _rule, members in groups.values()) - mixed
	cannot = len(loose) + mixed
	if nameable and cannot:
		text += f" {nameable} of them can be given a name; {cannot} cannot be told apart by anything fixed in the {kind}'s code."
	elif cannot:
		text += f" Nothing fixed in the {kind}'s code tells them apart, so an add-on cannot name them reliably."
	advice = "" if nameable else "Move to one and ask VisionClaw what it shows."
	return Finding("unnamed", text, "name names unnamed unlabeled unlabelled label labels button buttons link links field "
		"fields control controls nameless", made, look[:MAX_LOOKS], advice)


def _changing(nodes, later, textOf):
	"""Controls whose text changed between two looks, without the page or program telling NVDA."""
	if not later:
		return None

	def texts(snapshot):
		found, twice = {}, set()
		for node in snapshot:
			rule = signature(node)
			if rule is None or node.get("live") or node.get("role") in ("EDITABLETEXT", "PASSWORDEDIT", "DOCUMENT"):
				continue
			text = textOf(node)
			if not text or len(text) > 120:
				continue
			key = _ruleKey(rule)
			if key in found:
				twice.add(key)
			found[key] = (rule, text, node)
		return {key: value for key, value in found.items() if key not in twice}

	before, after = texts(nodes), texts(later)
	changed = [(before[key], after[key]) for key in before if key in after and before[key][1] != after[key][1]]
	# A running time would be spoken every few seconds for ever: it gets a key that reads it instead. And of
	# a part and the box around it, only the part itself counts, or the change would be spoken twice.
	changed = [pair for pair in changed if not (_TIME.match(pair[0][1]) and _TIME.match(pair[1][1]))]
	boxes = set()
	for (_rule, _old, node), _new in changed:
		up = node.get("up")
		while up is not None:
			boxes.add(id(up))
			up = up.get("up")
	changed = [pair for pair in changed if id(pair[0][2]) not in boxes]
	if not changed:
		return None
	made = []
	for (rule, _old, node), _new in changed[:3]:
		made.append({"kind": fixes.WATCH, "rule": rule, "label": codeName(node) or "this part"})
	(_rule, old, _node), (_rule2, new, _node2) = changed[0]
	return Finding("changing",
		f"{_plural(len(changed), 'part')} changed while VisionClaw watched, without telling NVDA: for example "
		f"\"{old[:40]}\" became \"{new[:40]}\".",
		"change changes changing changed update updates updating live announce tell", made)


def _drawn(drawn, known):
	"""Text that is shown as a picture, which NVDA cannot read: lines found by reading the picture that the
	page or window does not have as text."""
	if not drawn:
		return None
	have = set(plainText(known).split())
	unread = []
	for line in drawn:
		words = [word for word in plainText(line).split() if len(word) >= 3]
		if len(words) >= 2 and sum(word in have for word in words) / len(words) < 0.4:
			unread.append(" ".join(str(line).split()))
	if len(unread) < 3:
		return None
	return Finding("drawn",
		f"About {len(unread)} lines of text are only shown as a picture, which NVDA cannot read: for example \"{unread[0][:60]}\".",
		"picture drawn image text canvas", advice="Ask VisionClaw to read the text on the screen, or to list what is in the window.")


def _generic(nodes):
	names = {}
	for node in nodes:
		if node.get("role") in INTERACTIVE:
			text = plainText(labelOf(node))
			if text in _GENERIC:
				names[text] = names.get(text, 0) + 1
	total = sum(names.values())
	if total < 3:
		return None
	worst = max(names, key=names.get)
	return Finding("generic",
		f"{_plural(total, 'control')} have a name that says nothing, such as \"{worst}\".", "generic vague",
		advice="Read the text before one to learn what it is for.")


def auditPage(nodes, title="", site="", later=None, drawn=None, browser=""):
	"""The report for a web page. nodes: its controls in reading order. later: the same a few seconds on, to
	see what changes by itself. drawn: lines of text read from the page's picture."""
	scope = fixes.scopeOf(site=site)
	count = {}
	for node in nodes:
		count[node.get("role")] = count.get(node.get("role"), 0) + 1
	size = max((node.get("end", 0) for node in nodes), default=0) - min((node.get("start", 0) for node in nodes), default=0)
	headings = count.get("HEADING", 0)
	fields = sum(count.get(role, 0) for role in ("EDITABLETEXT", "PASSWORDEDIT", "COMBOBOX", "CHECKBOX", "RADIOBUTTON", "SLIDER"))
	landmarks = sum(1 for node in nodes if node.get("landmark") or node.get("role") in ("LANDMARK", "REGION"))
	articles = [node for node in nodes if node.get("role") == "ARTICLE" or "article" in (node.get("xml") or "").split()]
	media = [node for node in nodes if node.get("tag") in ("video", "audio") or node.get("role") in ("VIDEO", "AUDIO")]
	findings = []

	found = _unnamed(nodes, _NEED_NAMES, "page")
	if found is not None:
		findings.append(found)

	# Things that react to a click but are no button or link: Tab, B and K pass them by.
	inside = set()
	for node in nodes:
		if node.get("role") in INTERACTIVE:
			up = node.get("up")
			while up is not None:
				inside.add(id(up))
				up = up.get("up")
	clickRule = {"state": "CLICKABLE", "notRole": list(INTERACTIVE), "outer": True}
	clickable = [node for node in nodes if id(node) not in inside and not node.get("hidden") and matches(clickRule, node)
		and not _within(node, INTERACTIVE)]
	if len(clickable) >= 2:
		findings.append(Finding("clickable",
			f"{len(clickable)} things can be clicked but are not buttons or links, so the Tab, B and K keys pass them by.",
			"clickable click clicked", [{"kind": fixes.JUMP, "rule": clickRule, "label": "clickable item"}]))

	outer = [node for node in articles if not _within(node, ("ARTICLE",))]
	blocks = None if len(outer) >= 3 else _blocks(nodes, size)
	if len(outer) >= 3:
		findings.append(Finding("feed",
			f"The page is a feed of {len(outer)} posts so far. More are loaded as you move down, so it has no end, and "
			"NVDA has no key that goes from post to post.",
			"post posts feed scroll scrolling scrolls article articles story stories endless infinite timeline",
			[{"kind": fixes.JUMP, "rule": {"role": "ARTICLE", "outer": True}, "label": "post"}]))
	elif blocks is not None:
		rule, members = blocks
		findings.append(Finding("blocks",
			f"Most of the page is a list of {len(members)} similar blocks, such as results, videos or products, with "
			"no key that goes from one to the next.",
			"list result results item items block blocks video videos product products card cards",
			[{"kind": fixes.JUMP, "rule": rule, "label": "item"}]))

	if media:
		findings.append(_player(nodes, media))

	found = _changing(nodes, later, labelOf)
	if found is not None:
		findings.append(found)
	found = _drawn(drawn, " ".join(labelOf(node) for node in nodes))
	if found is not None:
		findings.append(found)

	if not headings and not landmarks and size > 1500:
		findings.append(Finding("structure",
			"The page has no headings and no landmarks, so the H and D keys find nothing to jump to.", "heading headings landmark",
			advice="Ask VisionClaw to go to the part you want, or to read the page."))
	found = _generic(nodes)
	if found is not None:
		findings.append(found)
	frames = [node for node in nodes if node.get("role") in ("INTERNALFRAME", "FRAME") and not plainText(labelOf(node))]
	if frames:
		findings.append(Finding("frames", f"{_plural(len(frames), 'frame')} inside the page have no name.", "frame frames"))
	images = [node for node in nodes if node.get("role") == "GRAPHIC" and isUnnamed(node)]
	if images:
		findings.append(Finding("images", f"{_plural(len(images), 'image')} have no description.", "image images picture pictures",
			advice="Move to one and ask VisionClaw to describe it."))

	parts = [
		f"Checked the web page {title or 'without a title'}" + (f" on {site}" if site else "") + (f", in {browser}" if browser else "") + ".",
		f"It has {_plural(headings, 'heading')}, {_plural(count.get('LINK', 0), 'link')}, "
		f"{_plural(count.get('BUTTON', 0) + count.get('TOGGLEBUTTON', 0), 'button')} and {_plural(fields, 'form field')}"
		+ (f", and {_plural(landmarks, 'landmark')}" if landmarks else "") + ".",
	]
	return Report("page", title, scope, " ".join(parts), findings)


def _within(node, roles):
	up = node.get("up")
	while up is not None:
		if up.get("role") in roles:
			return True
		up = up.get("up")
	return False


def _blocks(nodes, size):
	"""The repeated block most of a page is made of, as (rule, the blocks), or None."""
	groups = {}
	for node in nodes:
		if node.get("role") in INTERACTIVE or node.get("hidden") or not node.get("tag"):
			continue
		if not node.get("cls") and "-" not in node["tag"]:
			continue
		length = node.get("end", 0) - node.get("start", 0)
		if length < 60:
			continue
		rule = {"tag": node["tag"], "outer": True}
		if node.get("cls"):
			rule["cls"] = list(node["cls"][:4])
		groups.setdefault(_ruleKey(rule), (rule, []))[1].append((length, node))
	best = None
	for rule, members in groups.values():
		members = [(length, node) for length, node in members if matches(rule, node)]
		covered = sum(length for length, _node in members)
		if len(members) >= 5 and size and covered >= 0.3 * size and (best is None or covered > best[0]):
			best = (covered, rule, [node for _length, node in members])
	return (best[1], best[2]) if best else None


def _player(nodes, media):
	"""The finding for a video or audio player: keys for the player's own buttons, and its time."""
	made = []
	for names, label in _PLAYER:
		rule = {"role": list(PRESSABLE), "names": list(names)}
		if any(matches(rule, node) for node in nodes):
			made.append({"kind": fixes.PRESS, "rule": rule, "label": label})
	for node in nodes:
		if _TIME.match(labelOf(node)) and node.get("role") not in INTERACTIVE:
			rule = signature(node)
			if rule is not None and sum(matches(rule, other) for other in nodes) == 1:
				made.append({"kind": fixes.READ, "rule": rule, "label": "the time"})
				break
	what = "a video player" if any(node.get("tag") == "video" or node.get("role") == "VIDEO" for node in media) else "an audio player"
	if made:
		text = (f"The page has {what}. Its buttons are found only by moving to them, and they are often shown only "
			"while the mouse moves.")
		return Finding("media", text, "video player play pause mute media audio movie film tv show playback", made[:5])
	return Finding("media",
		f"The page has {what}, but NVDA finds no buttons for it. They may only be shown while the mouse moves.",
		"video player media audio", advice="Most players take Space or K for play and pause, M for mute and F for full screen, "
		"after NVDA+Space switches to focus mode.")


def auditWindow(nodes, title="", app="", later=None, drawn=None, bars=(), seen=""):
	"""The report for a program's window, from the controls NVDA knows in it. bars: the scrollbars found in
	its picture, in words. seen: what the vision model says the window has that is worked with the mouse."""
	scope = fixes.scopeOf(app=app)
	acted = [node for node in nodes if node.get("role") in INTERACTIVE or "FOCUSABLE" in (node.get("states") or ())]
	named = [node for node in nodes if plainText(node.get("name"))]
	findings = []
	if len(acted) <= 1 and len(named) <= 3:
		findings.append(Finding("picture",
			"NVDA finds almost nothing in this window: the program draws its own buttons and texts, so to NVDA it is one picture.",
			"picture empty nothing drawn",
			advice="VisionClaw can still work it from its picture: ask it to list what is in the window, to click an item, or "
			"to give this program a hotkey for an item."))
	found = _unnamed(nodes, _NEED_NAMES, "program")
	if found is not None:
		findings.append(found)
	found = _changing(nodes, later, lambda node: " ".join(part for part in (node.get("name"), node.get("value")) if part))
	if found is not None:
		findings.append(found)
	found = _drawn(drawn, " ".join(f"{node.get('name', '')} {node.get('value', '')}" for node in nodes))
	if found is not None and not any(finding.id == "picture" for finding in findings):
		findings.append(found)
	found = _generic(nodes)
	if found is not None:
		findings.append(found)
	summary = (
		f"Checked the window {title or 'without a title'} of the program {app}. NVDA knows {_plural(len(nodes), 'control')} "
		f"in it, {len(acted)} that can be used and {len(named)} with a name.")
	known = sum(1 for node in nodes if node.get("role") in ("SCROLLBAR", "SLIDER"))
	visual = []
	if bars:
		visual.append("Its picture shows " + " and ".join(bars[:2]) + ".")
	if seen:
		visual.append("The vision model, which can be wrong, sees these things that are worked with the mouse: " + seen)
	if visual or known:
		if known and not bars:
			visual.insert(0, f"NVDA knows {_plural(known, 'scrollbar or slider')} in it.")
		# How to work them is the same on every screen, so it is said once, here.
		visual.append(
			"Ask VisionClaw to scroll down, up or to the end; or press NVDA+Alt+K for pointer mode, where Page Down "
			"and Page Up turn the mouse wheel and S puts the pointer on a scrollbar.")
		summary += " " + " ".join(visual)
	return Report("window", title, scope, summary, findings)


# --- What the user wants fixed ---

def choose(report, which, heard=None):
	"""The findings a user means, among those an add-on can fix: by number, by what the problem is about, or
	all of them. heard: {number: finding id} of the report the user last heard for this place; a number they
	say means the problem that had that number then, even if this report counts differently.
	Raises ValueError with a sentence that says what can be fixed."""
	fixable = [finding for finding in report.findings if finding.fixable]
	if not fixable:
		advice = " ".join(finding.advice for finding in report.findings if finding.advice)
		raise ValueError(("None of the problems found here can be fixed by an add-on. " + advice).strip()
			if report.findings else "No problems were found here, so there is nothing to fix.")
	words = plainText(which).split()
	numbers = {int(word) for word in words if word.isdigit()} | {_ORDINALS[word] for word in words if word in _ORDINALS}
	if heard and numbers:
		meant = {heard[number] for number in numbers if number in heard}
		byNumber = [finding for finding in fixable if finding.id in meant]
	else:
		byNumber = [finding for finding in fixable if finding.number in numbers]
	if byNumber:
		return byNumber
	if numbers:
		raise ValueError("No fixable problem has that number. An add-on can fix: " + _fixableText(fixable))
	if not _ALL & set(words):
		about = [finding for finding in fixable if finding.words & set(words)]
		if about:
			return about
	return fixable


def _fixableText(fixable):
	return " ".join(f"{finding.number}. {finding.text}" for finding in fixable)[:600]


# --- One fix the user asks for in words ---

# What a user may call a kind of item to move between, and the rule for it.
_GROUPS = (
	(("heading", "headings"), {"role": "HEADING"}, "heading"),
	(("link", "links"), {"role": "LINK"}, "link"),
	(("button", "buttons"), {"role": ["BUTTON", "TOGGLEBUTTON", "MENUBUTTON"]}, "button"),
	(("image", "images", "picture", "pictures", "photo", "photos", "graphic", "graphics"), {"role": "GRAPHIC"}, "image"),
	(("field", "fields", "box", "boxes", "edit"), {"role": ["EDITABLETEXT", "COMBOBOX", "CHECKBOX", "RADIOBUTTON"]}, "field"),
	(("clickable",), {"state": "CLICKABLE", "notRole": list(INTERACTIVE), "outer": True}, "clickable item"),
	(("comment", "comments", "reply", "replies"), {"role": "ARTICLE"}, "comment"),
)
_POST_WORDS = frozenset((
	"post", "posts", "article", "articles", "story", "stories", "tweet", "tweets", "result", "results", "item", "items",
	"video", "videos", "product", "products", "card", "cards", "message", "messages", "entry", "entries",
))


def groupRule(words, report, nodes):
	"""The rule for the kind of item a user wants keys to move between, as (rule, what to call one), from
	their words and what the inspection found. Raises ValueError if the words name nothing that is here."""
	said = set(plainText(words).split())
	for finding in report.findings:
		if finding.id in ("feed", "blocks") and said & (_POST_WORDS | finding.words):
			fix = finding.fixes[0]
			label = next((word.rstrip("s") for word in plainText(words).split() if word in _POST_WORDS), fix["label"])
			return fix["rule"], label
	for names, rule, label in _GROUPS:
		if said & set(names) and any(matches(rule, node) for node in nodes):
			return rule, label
	raise ValueError(
		"Nothing here fits what was asked to move between. Keys can move between posts or other repeated blocks, "
		"headings, links, buttons, images, fields, comments and clickable items, where the page or window has them.")


_TIME_WORDS = frozenset(("time", "timer", "clock", "elapsed", "duration"))
_NO_NAME_WORDS = frozenset(("button", "link", "control", "the", "this", "that", "field", "icon", "a", "an"))


def _nameWords(text):
	"""A name without the words that only say what kind of thing it is."""
	return " ".join(word for word in plainText(text).split() if word not in _NO_NAME_WORDS)


def findByName(words, nodes, roles=None):
	"""The control a user means by its name, or None. roles: the kinds to look among first."""
	wanted = _nameWords(words)
	if not wanted:
		return None
	pools = [[node for node in nodes if node.get("role") in roles]] if roles else []
	pools.append(nodes)
	for pool in pools:
		exact = [node for node in pool if _nameWords(labelOf(node)) == wanted]
		if exact:
			return exact[0]
		starts = [node for node in pool if _nameWords(labelOf(node)).startswith(wanted + " ") and len(labelOf(node)) <= len(wanted) + 24]
		if starts:
			return min(starts, key=lambda node: len(labelOf(node)))
	# A part whose text changes is named by what it is, not by its text: "the inbox count", "the time".
	said = set(wanted.split())
	for node in nodes:
		words = set(codeName(node).split())
		if words and (words == said or (len(said) >= 2 and said <= words)):
			return node
	if said & _TIME_WORDS:
		for node in nodes:
			if _TIME.match(labelOf(node)) and node.get("role") not in INTERACTIVE:
				return node
	return None


def pressRule(node):
	"""The rule for a key that presses this control, found by its name each time. A control whose name
	switches, like Play and Pause, is found under either name."""
	name = plainText(labelOf(node))
	names = [name]
	for group, _label in _PLAYER[:3]:
		if name in group:
			names = list(group)
	return {"role": node["role"], "names": names}
