# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the latest guides for people who write for NVDA, kept on this computer as Markdown for the
# models to read up in: the NVDA Developer Guide from NV Access, and the NVDA Add-on Development Guide from
# the NVDA add-ons community. They are downloaded only when the user asks and has said yes; the addresses are
# fixed here and nothing but the two requests is sent. What comes back is text for reading, never run.
#
# The owner asked on 2026-11-18 that, once the guides are on the computer, VisionClaw make real use of them:
# in what it retrieves, in its skills, in what it remembers and in its system prompts. So the guides are read
# here in three ways, each by plain code:
#   sections  the guides cut at their headings, never inside a code example, as plain sentences without the
#             code: what a question is answered from, and what is spoken to the user;
#   facts     the single lines of a guide that say what one thing of NVDA is or does, such as a function with
#             what it gives back. The model that writes an add-on is given the few of them that fit the
#             request and name something VisionClaw's own notes do not, never a whole code example: a small
#             model copies an example whole, and a line that repeats what it was told already misleads it;
#   stored    which guides are here, from which day, and whether an older VisionClaw kept them.
# A fact whose name the running NVDA no longer has is left out by whoever can ask NVDA (nvdatools), because a
# guide written by volunteers also describes older versions of NVDA.
# No NVDA dependencies.

import datetime
import json
import os
import re
import textwrap
from html.parser import HTMLParser

from . import lookup

SOURCE = "guides"
SOURCES = (
	{"id": "nvda-developer-guide", "title": "NVDA Developer Guide", "by": "NV Access",
		"url": "https://download.nvaccess.org/documentation/developerGuide.html", "html": True},
	{"id": "nvda-addon-development-guide", "title": "NVDA Add-on Development Guide", "by": "the NVDA add-ons community",
		"url": "https://raw.githubusercontent.com/wiki/nvdaaddons/DevGuide/NVDA-Add-on-Development-Guide.md", "html": False},
)
# The only places a guide may come from, also after a redirect.
HOSTS = ("download.nvaccess.org", "www.nvaccess.org", "raw.githubusercontent.com")
MAX_BYTES = 3000000
# A guide shorter than this is not a guide: an error page, or an empty answer.
MIN_CHARS = 5000
# How the guides are kept. 1: as VisionClaw 1.1.0 and older kept them, where a code example that was written
# indented lost its indentation and its comments were taken for headings. 2: every code example between
# fences, as it was written.
FORMAT = 2
RECORD = "guides.json"
# Guides that come with every build of VisionClaw, as Markdown (the owner, 2026-11-18: "since everything is in
# markdown, all guides and all training material, just include it with every build of the addon ... then
# every visionclaw user gets it, even if the guides get a little out of date"). A text that is put into the
# add-on is published to every user, so only what its owner allows to be passed on may be here: MAY_SHIP names
# those sources and says by what right. The NVDA Developer Guide is under the GNU General Public License,
# version 2 or later, like VisionClaw. The NVDA Add-on Development Guide states no licence, so it is not
# shipped and is downloaded when the user asks, as before; it is added here on the day its authors say yes.
# A copy the user downloaded is newer and is used in place of the one that came with VisionClaw.
SHIPPED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shipped", "guides")
MAY_SHIP = {"nvda-developer-guide": "GNU General Public License, version 2 or later"}
# After this many days the user is told, when they ask about the guides, that newer ones may exist. Nothing
# is ever downloaded because of it.
OLD_DAYS = 180
# The line that begins what the model that writes an add-on is given from the guides. The code-writing
# instructions about the guides (prompts.CODE_GUIDE) are added when a message has it.
CODER_HEAD = "From NVDA's developer guides, with every name written exactly as NVDA has it:"
CODER_FACTS = 3
CODER_CHARS = 420
FACT_CHARS = 200
_SKIPPED = ("script", "style", "head", "nav", "noscript", "svg")
_BLOCKS = ("p", "div", "section", "article", "ul", "ol", "dl", "table", "blockquote", "tr", "dt", "dd")
_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^(#{1,4})\s+(.*\S)\s*$")
_LIST = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_INDENTED = re.compile(r"^(\t| {4})\s*\S")
_ROW_RULE = re.compile(r"^\s*\|?\s*:?-{2,}")
# A line of Python that stands in the text without a fence, as in guides kept by an older VisionClaw.
_CODE_LINE = re.compile(
	r"^(import \w|from \w[\w.]* import |class \w+\s*[(:]|def \w+\s*\(|@\w|return\b|try:|except\b.*:|else:|finally:|"
	r"(if|elif|for|while|with) .*:\s*(#.*)?$|[\w.\[\]\"']+\s*[-+]?=\s*\S|[\w.]+\(.*\)\s*(#.*)?$|[)\]}],?$|#\s?\w|"
	r"\w[\w.]*\($|[\"'][^\"']*[\"']\s*:|\w+\s*=\s*[\[{(]$)")


class _ToMarkdown(HTMLParser):
	def __init__(self):
		super().__init__(convert_charrefs=True)
		self.out = []
		self._skip = 0
		self._pre = 0

	def handle_starttag(self, tag, attrs):
		if tag in _SKIPPED:
			self._skip += 1
		elif self._skip:
			return
		elif re.fullmatch(r"h[1-6]", tag):
			self.out.append("\n\n" + "#" * int(tag[1]) + " ")
		elif tag == "pre":
			self._pre += 1
			self.out.append("\n\n```\n")
		elif tag == "li":
			self.out.append("\n- ")
		elif tag == "br":
			self.out.append("\n")
		elif tag in ("td", "th"):
			self.out.append(" | ")
		elif tag == "code" and not self._pre:
			self.out.append("`")
		elif tag in _BLOCKS:
			self.out.append("\n\n")

	def handle_endtag(self, tag):
		if tag in _SKIPPED:
			self._skip = max(0, self._skip - 1)
		elif self._skip:
			return
		elif tag == "pre" and self._pre:
			self._pre -= 1
			self.out.append("\n```\n\n")
		elif tag == "code" and not self._pre:
			self.out.append("`")
		elif re.fullmatch(r"h[1-6]", tag) or tag in _BLOCKS:
			self.out.append("\n\n")

	def handle_data(self, data):
		if self._skip:
			return
		self.out.append(data if self._pre else re.sub(r"\s+", " ", data))


def toMarkdown(html):
	"""A web page as Markdown: its headings, paragraphs, lists and code, without scripts, styles and menus."""
	parser = _ToMarkdown()
	parser.feed(html)
	parser.close()
	return tidy("".join(parser.out))


def tidy(text):
	"""Markdown with its lines trimmed and no more than one empty line in a row. Code is left as it is: what is
	between fences, and a code example written the older way, indented after an empty line, which is put
	between fences here so that its indentation, which Python needs, is kept."""
	lines, inCode, empty, block = [], False, 0, None

	def close():
		while block and not block[-1]:
			block.pop()
		lines.extend(["```"] + textwrap.dedent("\n".join(block)).split("\n") + ["```", ""])

	for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
		if block is not None:
			if not raw.strip():
				block.append("")
				continue
			if _INDENTED.match(raw):
				block.append(raw.rstrip())
				continue
			close()
			block, empty = None, 1
		if _FENCE.match(raw):
			inCode = not inCode
		elif not inCode and _INDENTED.match(raw) and (empty or not lines) and not _LIST.match(raw):
			# Indented after an empty line, and not an item of a list inside a list: a code example.
			block = [raw.rstrip()]
			continue
		if not inCode:
			line = raw.strip()
			# A heading's own anchor mark, as wikis and NVDA's pages add them.
			if line.startswith("#"):
				line = re.sub(r"\s*(\{#[^}]*\}|¶)\s*$", "", line)
		else:
			line = raw.rstrip()
		empty = empty + 1 if not line else 0
		if empty <= 1:
			lines.append(line)
	if block is not None:
		close()
	return "\n".join(lines).strip() + "\n"


def _isContents(body):
	"""Whether a section is only a list of the headings that follow: it names everything and says nothing."""
	lines = [line for line in body.split("\n") if line.strip()]
	return len(lines) >= 8 and all(_LIST.match(line) and not line.rstrip().endswith(".") for line in lines)


def cut(markdown, old=False):
	"""A guide as (heading, body) at its headings. A line that begins with # inside a code example is a comment
	of the code and not a heading. old: the guide was kept by an older VisionClaw, which left such examples
	without a fence; there only a heading of the second level or below is taken for one, since a comment
	begins with one #. A list of contents is left out."""
	found, title, body, inCode = [], None, [], False

	def keep():
		text = "\n".join(body).strip()
		if title and text and not _isContents(text):
			found.append((title, text))

	for line in markdown.split("\n"):
		if _FENCE.match(line):
			inCode = not inCode
		mark = None if inCode else _HEADING.match(line)
		if mark and not (old and len(mark.group(1)) == 1):
			keep()
			title, body = _plain(mark.group(2)), []
		else:
			body.append(line)
	keep()
	return found


def _plain(text):
	"""A line of Markdown as it is said: a link as its words, no marks for code or emphasis."""
	text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
	text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
	text = re.sub(r"(\*\*|__|`)", "", text)
	return " ".join(text.split())


def _row(line):
	"""The cells of a table's row, or None when the line is not one."""
	if "|" not in line or _ROW_RULE.match(line):
		return None
	cells = [_plain(cell) for cell in line.strip().strip("|").split("|")]
	cells = [cell for cell in cells if cell]
	return cells if len(cells) >= 2 else None


def _sentence(text):
	text = text.strip()
	return text if not text or text[-1] in ".!?:;" else text + "."


def prose(body, old=False):
	"""What a section says, as plain sentences for a model to read and for speech: without its code examples,
	a list's items and a table's rows each as a sentence. old: also without lines of code that stand in the
	text with no fence around them."""
	lines, inCode = [], False
	for line in body.split("\n"):
		if _FENCE.match(line):
			inCode = not inCode
			continue
		line = line.strip()
		if inCode or not line or _ROW_RULE.match(line) or (old and _CODE_LINE.match(line)):
			continue
		cells = _row(line) if line.startswith("|") or line.count("|") >= 2 else None
		if cells:
			lines.append(_sentence(": ".join(cells[:2]) + ("" if len(cells) < 3 else ". " + ". ".join(cells[2:]))))
		elif _LIST.match(line):
			lines.append(_sentence(_plain(_LIST.sub("", line))))
		else:
			lines.append(_plain(re.sub(r"^#+\s*", "", line)))
	return " ".join(line for line in lines if line)


# --- Single facts, for the model that writes an add-on ---

# A name of NVDA as code writes it: a dotted name, a call, an event or a script.
_NAME = re.compile(
	r"(?<![\w./\\-])((?:event|script)_\w+|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+(?:\([^()]*\))?|[A-Za-z_]\w*\([^()]*\))")
# What looks like a dotted name and is a file, an address or an abbreviation.
_NOT_NAMES = frozenset((
	"ini", "py", "pyd", "pyc", "md", "txt", "html", "htm", "com", "org", "net", "io", "dll", "exe", "json", "po", "pot",
	"mo", "zip", "wav", "ogg", "png", "ico", "dic", "tpl", "yml", "yaml", "toml", "cfg", "bat", "cmd", "g", "e", "etc"))
_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+`?([A-Za-z_][\w.]*(?:\([^)]*\))?)`?\s*(?::|,| - | – | — )\s*(\S.*)$")
_CAMEL = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
# Words every request for an add-on has, which say nothing about which fact fits.
_EVERY = frozenset(("add", "addon", "write", "creat", "pres", "key", "say", "tell", "speak", "program", "nvda"))
# Words of names that say nothing about which name is meant: getFocusObject is about the focus.
_IN_EVERY_NAME = frozenset(("get", "set", "is", "has", "object", "obj", "self", "handler", "event", "script", "on"))
# The two kinds of fact: an item of a list that begins with a name and says what it is, and a row of a table
# that says what is wanted and how it is written. An item says more about its name, so of two facts about one
# name the item is given.
ITEM, ROW = 0, 1
# Not NVDA's own: Python's modules and functions, which the guides mention in passing, and what a small
# add-on must not use (microaddons.check). No fact about them is given: the facts are for NVDA's names.
NOT_FOR_ADDONS = frozenset((
	"os", "sys", "ctypes", "subprocess", "importlib", "shutil", "hasattr", "open", "eval", "exec", "time", "threading",
	"collections", "datetime", "re", "json", "math", "urllib", "len", "print", "something"))


class Fact:
	"""One line of a guide about one thing of NVDA. names: the names it writes as code has them. kind: ITEM or
	ROW. task: the part that says in words what the thing is for. guide and heading say where it is from."""

	__slots__ = ("text", "names", "kind", "task", "guide", "heading", "_words")

	def __init__(self, text, names, kind=ITEM, task="", guide="", heading=""):
		self.text = text
		self.names = tuple(names)
		self.kind = kind
		self.task = task
		self.guide = guide
		self.heading = heading
		self._words = None

	def words(self):
		"""(the words of its own name, taken apart where a capital letter begins a word, without those nearly
		every name has; the words that say what it is for)."""
		if self._words is None:
			last = self.names[0].split("(")[0].rsplit(".", 1)[-1]
			named = wordsOf(" ".join(_CAMEL.findall(last.replace("_", " ")))) - _IN_EVERY_NAME
			self._words = (named, wordsOf(lookup._KEY.sub(" ", self.task)))
		return self._words

	def __repr__(self):
		return f"Fact({self.text[:60]!r})"


def wordsOf(text):
	"""The telling words of a text, as facts and requests are compared."""
	return lookup.textWords(text)


def namesIn(text):
	"""The names of NVDA's code a line writes, without what is a file or a web address."""
	found = []
	for hit in _NAME.finditer(text or ""):
		name = hit.group(1)
		bare = name.split("(")[0]
		if bare.rsplit(".", 1)[-1].lower() in _NOT_NAMES or re.fullmatch(r"[\d.]+", bare) or bare.lower().startswith("www."):
			continue
		if name not in found:
			found.append(name)
	return found


def _fact(text, names, kind, task, guide, heading):
	text = _sentence(_plain(text))
	if len(text) > FACT_CHARS:
		# A fact is one line. A longer one is cut at the end of a sentence, and left out when its first is too long.
		kept = ""
		for sentence in re.split(r"(?<=[.!?])\s+", text):
			if len(kept) + len(sentence) + 1 > FACT_CHARS:
				break
			kept = f"{kept} {sentence}".strip()
		text = kept
	names = [name for name in names if name.split("(")[0] in text]
	return Fact(text, names, kind, _plain(task), guide, heading) if names and len(text) >= 25 else None


def factsIn(body, guide="", heading=""):
	"""The lines of a section that say what one thing of NVDA is or does: an item of a list that begins with a
	name of NVDA's code, and a row of a table that writes one. Never a line of an example, and never a sentence
	of the running text, which says little without the sentences around it."""
	found, inCode = [], False
	for line in body.split("\n"):
		if _FENCE.match(line):
			inCode = not inCode
			continue
		line = line.strip()
		if inCode or not line or _ROW_RULE.match(line) or line.startswith("#"):
			continue
		item = _ITEM.match(line)
		fact = None
		if item:
			if namesIn(item.group(1)):
				fact = _fact(f"{item.group(1)}: {item.group(2)}", [item.group(1)], ITEM, item.group(2), guide, heading)
		else:
			cells = _row(line)
			# A row says what is wanted in its first cell, in words, and how it is written in the next. A row
			# that begins with a single word is a row of some other table, which says nothing on its own.
			if cells and not namesIn(cells[0]) and len(wordsOf(cells[0])) >= 2:
				text = ": ".join(cells[:2]) + ("" if len(cells) < 3 else ". " + ". ".join(cells[2:]))
				fact = _fact(text, namesIn(" ".join(cells[1:])), ROW, cells[0], guide, heading)
		if fact:
			found.append(fact)
	return found


def fits(fact, asked):
	"""How well a fact fits the words of a request, 0 when it does not.
	An item of a list, which begins with a name, fits by that name: the request has more than half of a name of
	several words; or a word of the name and a word of what the name is for; or, where the name is a function
	that is called, all of it. So "copy to the clipboard" finds copyToClip and "beep" finds tones.beep, while
	"window" alone does not find windowClassName.
	Any fact fits by what it is for: the request has two or more of those words, and at least half of them. So
	"the title of the window" finds "title of the active window", and "the time" does not find "the current
	time in seconds"."""
	named, task = fact.words()
	shared = asked & named
	score = 0.0
	if shared and fact.kind == ITEM:
		also = asked & (task - named)
		byName = len(shared) / len(named)
		if (byName > 0.5 and len(named) > 1) or (also and byName >= 0.5) or (byName == 1.0 and "(" in fact.names[0]):
			score = 2 * byName + (0.5 if also else 0.0)
	if len(asked & task) >= 2 and len(asked & task) * 2 >= len(task):
		score = max(score, 1 + len(asked & task) / len(task))
	return score


def _tail(name):
	"""A name as code most often writes it: its last two parts, api.getFocusObject of x.api.getFocusObject."""
	return ".".join(name.split("(")[0].split(".")[-2:])


def fitting(facts, purpose, limit=CODER_FACTS, exists=None, known=""):
	"""The facts that fit what an add-on is for (fits), best first, by plain code; none when none fits.
	exists(name) says whether the running NVDA has a name: True, False, or None when it cannot tell; a fact
	with a name NVDA no longer has is left out, and so is one about something a small add-on must not use. Of
	the facts about one name, one is given: the one that says most about it.
	known: what the model is told anyway, its instructions and VisionClaw's own notes for this request. A fact
	about a name that is in there already is left out: measured with Qwen2.5 Coder 1.5B on 2026-11-18, a line
	of the guides that only repeated the notes made the model write a key command where an event was asked
	for, and a line that named an event the notes did not have made it write the event."""
	asked = wordsOf(lookup._KEY.sub(" ", str(purpose or ""))) - _EVERY
	if not asked or not facts:
		return []
	scored = []
	for at, fact in enumerate(facts):
		score = fits(fact, asked)
		if score:
			scored.append((-score, fact.kind, len(fact.text), at))
	chosen = []
	for _score, _kind, _size, at in sorted(scored):
		fact = facts[at]
		bare = [name.split("(")[0] for name in fact.names]
		if any(name.split(".")[0] in NOT_FOR_ADDONS for name in bare):
			continue
		if exists is not None and any(exists(name) is False for name in bare):
			continue
		if known and any(_tail(name) in known for name in bare):
			continue
		if any(kept.names[0].split("(")[0] == bare[0] for kept in chosen):
			continue
		chosen.append(fact)
		if len(chosen) >= limit:
			break
	return chosen


def coderText(facts, purpose, exists=None, chars=CODER_CHARS, known=""):
	"""What the model that writes or repairs an add-on is given from the guides: a few single lines that fit
	the request and say something it is not told anyway (known), or "" when there is none."""
	lines = []
	for fact in fitting(facts, purpose, exists=exists, known=known):
		line = f"- {fact.text}"
		if sum(len(kept) + 1 for kept in lines) + len(line) > chars:
			break
		lines.append(line)
	return "\n".join([CODER_HEAD] + lines) if lines else ""


# --- Keeping them ---

def _path(folder, source):
	return os.path.join(folder, source["id"] + ".md")


def update(folder, fetch, cancel=None, today=None):
	"""Download every guide and keep it as Markdown. fetch(url) returns the text at an address, or raises.
	A guide that cannot be fetched or does not look like a guide leaves the copy that is there untouched.
	Returns {"got": [(title, how many sections)], "failed": [(title, why)]}."""
	os.makedirs(folder, exist_ok=True)
	got, failed = [], []
	for source in SOURCES:
		if cancel is not None and cancel.is_set():
			break
		try:
			text = fetch(source["url"])
			markdown = toMarkdown(text) if source["html"] else tidy(text)
			count = len(cut(markdown))
			if len(markdown) < MIN_CHARS or count < 5:
				raise ValueError("what came back is not the guide")
		except Exception as e:
			failed.append((source["title"], f"{type(e).__name__}: {e}"[:160]))
			continue
		tmp = _path(folder, source) + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			f.write(markdown)
		os.replace(tmp, _path(folder, source))
		got.append((source["title"], count))
	if got:
		kept = stored(folder)
		day = today or datetime.date.today().isoformat()
		for title, count in got:
			kept[title] = {"date": day, "sections": count, "format": FORMAT}
		with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as f:
			json.dump(kept, f, indent=1)
	return {"got": got, "failed": failed}


def stored(folder):
	"""The guides on this computer: {title: {"date", "sections", "format"}}."""
	try:
		with open(os.path.join(folder, RECORD), encoding="utf-8") as f:
			found = json.load(f)
		return found if isinstance(found, dict) else {}
	except (OSError, ValueError):
		return {}


def _isOld(kept, source):
	info = kept.get(source["title"])
	return not isinstance(info, dict) or info.get("format", 1) < FORMAT


def shipped(source):
	"""The path of the copy of a guide that came with VisionClaw, or "" when it has none."""
	if not SHIPPED or source["id"] not in MAY_SHIP:
		return ""
	path = _path(SHIPPED, source)
	return path if os.path.isfile(path) else ""


def shippedRecord():
	"""What came with VisionClaw: {title: {"date", "sections", "format", "licence"}}."""
	return stored(SHIPPED) if SHIPPED else {}


def _read(folder):
	"""Every guide that is here as (source, its sections as (heading, body), kept the older way or not): the
	copy the user downloaded, or else the one that came with VisionClaw."""
	kept, found = stored(folder), []
	for source in SOURCES:
		path, old = _path(folder, source), _isOld(kept, source)
		if not os.path.isfile(path):
			path, old = shipped(source), False
		if not path:
			continue
		try:
			with open(path, encoding="utf-8") as f:
				text = f.read()
		except (OSError, UnicodeDecodeError):
			continue
		found.append((source, cut(text, old), old))
	return found


def load(folder):
	"""Every section of the guides on this computer, as (title, body, source), for the knowledge search and
	for questions: what each section says in plain sentences, without its code examples."""
	found = []
	for source, sections, old in _read(folder):
		for heading, body in sections:
			text = prose(body, old)
			if text:
				found.append((f"{source['title']}: {heading}", text, SOURCE))
	return found


def facts(folder):
	"""Every single fact of the guides on this computer (factsIn)."""
	found, seen = [], set()
	for source, sections, _old in _read(folder):
		for heading, body in sections:
			for fact in factsIn(body, source["title"], heading):
				if fact.text not in seen:
					seen.add(fact.text)
					found.append(fact)
	return found


class Guides:
	"""The guides on this computer, read once and again after they changed."""

	def __init__(self, folder):
		self.folder = folder
		self._facts = None

	def facts(self):
		if self._facts is None:
			self._facts = facts(self.folder)
		return self._facts

	def reload(self):
		self._facts = None

	def here(self):
		"""Whether any guide is on this computer: downloaded, or come with VisionClaw."""
		return any(os.path.isfile(_path(self.folder, source)) or shipped(source) for source in SOURCES)

	def has(self, ident):
		"""Whether one guide is here, by its id: downloaded, or come with VisionClaw."""
		return any(
			source["id"] == ident and (os.path.isfile(_path(self.folder, source)) or bool(shipped(source)))
			for source in SOURCES)

	def downloaded(self):
		"""Whether the user downloaded any guide: only those can be deleted."""
		return any(os.path.isfile(_path(self.folder, source)) for source in SOURCES)

	def forCoder(self, purpose, exists=None, known=""):
		return coderText(self.facts(), purpose, exists, known=known)


def remove(folder):
	"""Delete the guides from this computer. Only the files VisionClaw itself kept there are deleted. Returns
	the titles of the guides that were deleted."""
	gone = []
	for source in SOURCES:
		for path in (_path(folder, source), _path(folder, source) + ".tmp"):
			try:
				os.remove(path)
				if path.endswith(".md"):
					gone.append(source["title"])
			except OSError:
				pass
	try:
		os.remove(os.path.join(folder, RECORD))
	except OSError:
		pass
	return gone


def summary(result):
	"""What an update did, in sentences."""
	lines = []
	for title, count in result["got"]:
		lines.append(f"Downloaded the {title} and kept it as Markdown, {count} sections.")
	for title, why in result["failed"]:
		lines.append(f"The {title} could not be downloaded ({why}); an earlier copy, if there is one, is still used.")
	if result["got"]:
		lines.append(
			"VisionClaw now looks things up in them when you ask about writing for NVDA, and when it writes or "
			"corrects an add-on for you it is given the lines of them that fit. A downloaded guide is used in place "
			"of the one that came with VisionClaw.")
	return " ".join(lines) or "Nothing was downloaded."


def _age(date, today=None):
	"""How many days ago a day was, or None when it is not a day."""
	try:
		then = datetime.date.fromisoformat(str(date))
	except ValueError:
		return None
	return ((today or datetime.date.today()) - then).days


def storedText(folder, today=None):
	"""Which guides are on this computer, from when, and where, in sentences for the user. Plain code says
	this; no model is asked."""
	kept = {title: info for title, info in stored(folder).items() if isinstance(info, dict)}
	came = {title: info for title, info in shippedRecord().items() if isinstance(info, dict)}
	here = [source for source in SOURCES if os.path.isfile(_path(folder, source))]
	withIt = [source for source in SOURCES if source not in here and shipped(source)]
	missing = [source for source in SOURCES if source not in here and source not in withIt]
	if not here and not withIt:
		return (
			"No developer guides are on this computer yet. Ask VisionClaw to get the latest NVDA developer guides; it "
			"asks before it goes online.")
	lines, oldest, older = [], 0, False
	for source in here:
		info = kept.get(source["title"], {})
		days = _age(info.get("date"), today)
		when = "from an unknown day" if days is None else "downloaded today" if days <= 0 else (
			f"downloaded on {info['date']}, {days} {'day' if days == 1 else 'days'} ago")
		lines.append(f"The {source['title']} by {source['by']}, {when}.")
		oldest = max(oldest, days or 0)
		older = older or info.get("format", 1) < FORMAT
	for source in withIt:
		day = came.get(source["title"], {}).get("date")
		lines.append(f"The {source['title']} by {source['by']} came with VisionClaw" + (f", as it was on {day}." if day else "."))
	text = " ".join(lines)
	if here:
		text += f" What was downloaded is kept as Markdown files, which you can read, in the folder {folder}."
	if withIt:
		text += f" What came with VisionClaw is in the folder {SHIPPED}."
	if missing:
		text += (
			f" The {' and the '.join(source['title'] for source in missing)} does not come with VisionClaw, because its "
			"authors have not said that it may be passed on. Ask VisionClaw to get the latest NVDA developer guides "
			"to download it; it asks before it goes online.")
	text += (
		" VisionClaw looks things up in them when you ask about writing for NVDA, and gives the lines that fit to "
		"the writing of an add-on.")
	if older:
		text += (
			" They were kept by an older VisionClaw, which lost the indentation of some code examples. Ask VisionClaw "
			"to get the latest NVDA developer guides to have them kept as they were written.")
	elif oldest > OLD_DAYS:
		text += (
			" Newer ones may exist by now. Ask VisionClaw to get the latest NVDA developer guides if you want them; "
			"it never downloads them by itself.")
	return text
