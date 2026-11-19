# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - understanding the user's own words the way a text adventure does.
# The owner said on 2026-11-19: "visionclaw must have skills and system prompts, memory and rag to understand the
# different ways a user may request something, like how inform text adventures understand different things in
# different ways." Inform reads "x lamp" and "examine the lamp" as one action because its author wrote
# 'Understand "x" as examining' and 'Understand "look at [something]" as examining'. VisionClaw does the same
# before it decides what to do: the words of a request are rewritten, by plain code, into the plain words that
# VisionClaw's patterns and its small models know, following lines written in Markdown:
#   - VisionClaw's own lines, in claw/understanding.md, which comes with every build;
#   - the user's own words, taught in words ("when I say shh, I mean stop talking") and kept in the file
#     understanding.md of VisionClaw's data folder, which the user can read and change. They come first.
# A line is - "these words", "or these" mean "those words". [x] stands for any words, kept as they are, [keys] for
# a key combination, [thing] for a named button, link or other item, [window] for a window or a dialog.
# Where a line may change something is said by its section: at the start or the end of a request only (words
# said for nothing), anywhere (spellings, and words that mean the same), or only where something to do begins
# (ways of saying what to do: "fire up" is "open" at the start, and nowhere else).
# What must stay the user's own is never changed: words in quotes, text to be typed, a name given, what is to be
# searched for, web addresses and file names, keys, and every request that asks VisionClaw to remember, to make a
# skill, or to understand a word. A small model reads plain words better than slang; plain code does the
# rewriting, and the user is told how they were understood whenever the meaning of a word was changed.
# No model is asked, nothing is learned from a model, and nothing goes online. No NVDA dependencies.

import os
import re

from . import debuglog

BUILT_IN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "understanding.md")
# The user's own words, in VisionClaw's data folder.
OWN_NAME = "understanding.md"
# The sections of a file of words, by the words their headings begin with.
START, END, SPELLING, SAME, TO_DO, OWN = "start", "end", "spelling", "same", "to do", "own"
NOTHING = (START, END)
_SECTIONS = (("said for nothing at the start", START), ("said for nothing at the end", END), ("spellings", SPELLING),
	("same meaning", SAME), ("ways to say what to do", TO_DO), ("your own words", OWN))
# Changes of these kinds change what a word means, and the user is told: "Understood as: ...".
SAID = (SAME, TO_DO, OWN)
# Where else than in a whole request a line applies. The owner said on 2026-11-19: "all visionclaw orchestrators must
# follow suit and also be flexible and adaptable and understand the meaning of the various ways a user may make
# various requests." A section whose heading ends with ", in add-ons" applies only where the add-on writer reads a
# request into pieces (claw/codeplan.py); ", in questions about a picture" only where a question about the screen
# is read into its parts (claw/pictures.py). There, the lines every request gets apply too; elsewhere these never.
ADDON, PICTURE = "add-ons", "pictures"
_SCOPES = ((", in add-ons", ADDON), (", in questions about a picture", PICTURE))
# What a taught word may be.
MIN_LETTERS = 2
MAX_SAID = 60
MAX_MEANT = 200
_OWN_HEAD = (
	"# Your own words\n\n"
	"VisionClaw understands each of these words of yours as the words after \"means\", before it decides what to do.\n"
	"You taught them by saying, for example, \"when I say shh, I mean stop talking\". To make VisionClaw forget one,\n"
	"say \"forget the word shh\", or delete its line here.\n\n")

_SPACE = re.compile(r"\s+")
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})
_LINE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")
_PHRASE = re.compile(r'"([^"]*)"')
_MEANS = re.compile(r'\bmeans?\s+"([^"]*)"\s*$')

# Keys, as words say them: "control c", "ctrl+shift+escape", "nvda plus t", "alt f4", and keys that have a name.
_MOD = r"(?:nvda|control|ctrl|alt|shift|windows|win)"
_KEY = (r"(?:f\d{1,2}|enter|return|escape|esc|tab|space(?:bar)?|delete|del|backspace|home|end|page ?up|page ?down|"
	r"insert|(?:up|down|left|right)(?: arrow)?|[a-z0-9])")
_JOIN = r"\s*(?:\+|\bplus\b|-|\s)\s*"
_COMBO = rf"\b{_MOD}(?:{_JOIN}{_MOD}){{0,3}}{_JOIN}{_KEY}\b"
_NAMED = r"\b(?:f\d{1,2}|enter|return|escape|esc|tab|space ?bar|backspace|delete|page ?up|page ?down|insert)\b"
# A span of words that is never changed is put aside as a mark of its own while the lines are applied: ⟦n⟧, or
# ⟦nk⟧ for keys, so that [keys] can still take it.
_MARK = re.compile(r"⟦(\d+)(k?)⟧")
_ANY_MARK = r"⟦\d+k?⟧"
# Where one thing to do begins, before a way of saying it.
_LEAD = (r"(?P<lead>^|[.!?;:,]\s*|\b(?:and|then|also|please|now|just|but|so|first|next)\s+"
	r"|\b(?:can|could|would|will) (?:you|ya|u)\s+(?:please\s+)?|\bi (?:want|need) you to\s+)")
# Where a phrase of [x] ends: the end of what is said in one go.
_CLAUSE_END = r"(?=\s*(?:[.,;!?:]|\band\b|\bthen\b|$))"
_TOKENS = {
	"x": r"[^.,;!?:]+?",
	"keys": rf"(?:{_COMBO}|{_NAMED}|⟦\d+k⟧)",
	"thing": (r"(?:(?:the|a|an|this|that|my)\s+)?(?:[\w'⟦⟧-]+\s+){0,4}?"
		r"(?:button|link|tab|icon|checkbox|check box|menu item|option|item|box)s?\b"),
	"window": (r"(?:this|the|that|my|current|active)\s+(?:window|dialog box|dialog|dialogue|pop-?up|program|app|"
		r"application|tab|message box|message)\b"),
}
_TOKEN = re.compile(r"\[(x|keys|thing|window)\]")
# What is never changed, by where it begins: text to be typed, a name, what is to be searched for. Each runs to
# the end of what is said in one go.
_KEEP_AFTER = re.compile(
	rf"{_LEAD}(?:type|write|enter|dictate|insert|paste)(?:\s+(?:in|out|down))?\s+"
	r"|\b(?:called|named|titled|labell?ed|name it|call it|label it|rename it to|that says|which says|saying)\s+"
	r"|\b(?:search(?: the web| the internet| online)? for|look up|google|bing|search up)\s+",
	re.IGNORECASE)
_QUOTED = re.compile(r'"[^"]*"|(?<![\w])\'[^\']+\'(?![\w])')
_DOTTED = re.compile(r"\b[\w-]+(?:\.[\w-]+)+\b")
# Requests whose words are kept as they were said: what is remembered, a skill, a word taught.
_OWN_WORDS = re.compile(
	r"\b(remember|memori[sz]e|keep in mind|bear in mind|note that|don'?t forget|do not forget|skills?|when i say|"
	r"if i say|i mean|means?|taught|teach|understand|unlearn)\b", re.IGNORECASE)


class Rule:
	"""One line of a file of words: phrases that mean one thing, where they may stand, and the kind of line."""

	def __init__(self, phrases, meant, kind, scope=None):
		self.phrases = [p for p in phrases if p.strip()]
		self.meant = meant
		self.kind = kind
		# None: every request; ADDON or PICTURE: only where that is read (Grammar.read(where=...)).
		self.scope = scope
		self.patterns = [_compile(phrase, kind) for phrase in self.phrases]

	def __repr__(self):
		return f"Rule({self.phrases!r} -> {self.meant!r}, {self.kind}" + (f", {self.scope})" if self.scope else ")")


def _edge(text, start):
	"""What keeps a phrase from matching inside a longer word."""
	if start:
		return r"(?<![\w'-])" if text[:1].isalnum() else ""
	return r"(?![\w'-])" if text[-1:].isalnum() else ""


def _compile(phrase, kind):
	"""A phrase as a pattern. Its words may be separated by any spaces; its tokens take words of their kind."""
	phrase = " ".join(phrase.lower().split())
	pieces, at, used = [], 0, set()
	for found in _TOKEN.finditer(phrase):
		literal = phrase[at:found.start()]
		if literal.strip():
			pieces.append(re.escape(literal.strip()).replace(r"\ ", r"\s+"))
		name = found.group(1)
		if name in used:
			raise ValueError(f"[{name}] twice in one phrase: {phrase!r}")
		used.add(name)
		token = _TOKENS[name]
		# [x] at the end of a phrase takes the rest of what is said in one go.
		if name == "x" and found.end() >= len(phrase.rstrip()):
			token += _CLAUSE_END
		pieces.append(f"(?P<{name}>{token})")
		at = found.end()
	literal = phrase[at:]
	if literal.strip():
		pieces.append(re.escape(literal.strip()).replace(r"\ ", r"\s+"))
	body = r"\s+".join(pieces)
	plain = _TOKEN.sub("", phrase).strip()
	start = _edge(phrase, True) if not phrase.startswith("[") else ""
	end = _edge(phrase, False) if not phrase.endswith("]") else ""
	if kind in NOTHING:
		return re.compile(rf"(?:{body}){end}" if plain else body, re.IGNORECASE)
	if kind == TO_DO:
		return re.compile(rf"{_LEAD}{body}{end}", re.IGNORECASE)
	return re.compile(rf"{start}{body}{end}", re.IGNORECASE)


def parse(text, kind=None):
	"""The rules of a file of words. kind: the kind of every line, for the user's own file; else each section's
	heading says it. A line that cannot be read is left out and written to the log."""
	rules, current, scope = [], kind, None
	for line in (text or "").splitlines():
		heading = re.match(r"^\s*##\s+(.*)$", line)
		if heading and kind is None:
			name = heading.group(1).strip().lower()
			current = next((value for begins, value in _SECTIONS if name.startswith(begins)), None)
			scope = next((value for ends, value in _SCOPES if name.rstrip(" .").endswith(ends)), None)
			continue
		found = _LINE.match(line)
		if not found or current is None:
			continue
		body = found.group(1).translate(_QUOTES)
		means = _MEANS.search(body)
		phrases = _PHRASE.findall(body[:means.start()] if means else body)
		meant = means.group(1) if means else ""
		if not phrases or (current not in NOTHING and not means):
			continue
		try:
			rules.append(Rule(phrases, meant, current, scope))
		except (ValueError, re.error) as e:
			debuglog.error("understand", f"A line of words could not be read: {line!r}", e)
	return rules


class Reading:
	"""What was made of a request: text, the request as it is understood; changes, (said, meant, kind) for every
	line that changed something; said, whether the meaning of a word was changed, so that the user is told."""

	def __init__(self, text, changes):
		self.text = text
		self.changes = changes

	@property
	def said(self):
		return any(kind in SAID for _said, _meant, kind in self.changes)

	@property
	def changed(self):
		return bool(self.changes)


def _keep(text, where=None):
	"""The spans that are never changed, each put aside as a mark. Returns (text with marks, the spans). In an add-on,
	"that says" is what the add-on does, not a name: there only quotes, addresses, file names and keys are kept."""
	spans = []

	def mark(value, keys=False):
		spans.append(value)
		return f"⟦{len(spans) - 1}{'k' if keys else ''}⟧"

	text = _QUOTED.sub(lambda m: mark(m.group(0)), text)
	# What follows a word that begins text to be typed, a name, or a search runs to the end of what is said.
	out, at = [], 0
	for found in (_KEEP_AFTER.finditer(text) if where != ADDON else ()):
		if found.start() < at:
			continue
		rest = re.match(r"[^.,;!?]*", text[found.end():]).group(0)
		tail = re.search(r"\s+(?:and|then)\s.*$", rest)
		kept = rest[:tail.start()] if tail else rest
		if not kept.strip():
			continue
		out.append(text[at:found.end()])
		out.append(mark(kept.rstrip()) + kept[len(kept.rstrip()):])
		at = found.end() + len(kept)
	text = "".join(out) + text[at:]
	text = _DOTTED.sub(lambda m: mark(m.group(0)), text)
	text = re.sub(_COMBO, lambda m: mark(m.group(0), keys=True), text, flags=re.IGNORECASE)
	return text, spans


def _back(text, spans):
	"""The spans put back where their marks are."""
	for _again in range(3):
		if not _MARK.search(text):
			break
		text = _MARK.sub(lambda m: spans[int(m.group(1))] if int(m.group(1)) < len(spans) else "", text)
	return text


def _fill(meant, found):
	"""The meaning of a line with the words its tokens took."""
	def put(token):
		try:
			return found.group(token.group(1)) or ""
		except IndexError:
			return ""
	return _TOKEN.sub(put, meant)


def _apply(rule, text, changes, spans):
	for pattern in rule.patterns:
		def replace(found):
			lead = found.groupdict().get("lead") or ""
			new = lead + _fill(rule.meant, found)
			changes.append((_back(found.group(0)[len(lead):], spans).strip(), _back(new[len(lead):], spans).strip(), rule.kind))
			return new
		text = pattern.sub(replace, text)
	return text


def _words(rules, kind):
	phrases = sorted({p.lower() for rule in rules if rule.kind == kind for p in rule.phrases}, key=len, reverse=True)
	return "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in phrases)


def _trim(rules, text, changes):
	"""Words said for nothing, taken away at the start and the end, as often as they stand there. At least two
	words are always left."""
	first, last = _words(rules, START), _words(rules, END)
	start = re.compile(rf"^\s*(?:{first})(?![\w'-])\s*[,.!:;-]*\s*", re.IGNORECASE) if first else None
	end = re.compile(rf"[\s,]*(?<![\w'-])(?:{last})\s*(?P<mark>[.!?]*)\s*$", re.IGNORECASE) if last else None
	for _again in range(4):
		found = start.match(text) if start else None
		if not found or len(text[found.end():].split()) < 2:
			break
		changes.append((found.group(0).strip(" ,.!:;-"), "", START))
		text = text[found.end():]
	for _again in range(4):
		found = end.search(text) if end else None
		if not found or len(text[:found.start()].split()) < 2:
			break
		changes.append((found.group(0).strip(" ,.!?"), "", END))
		text = text[:found.start()].rstrip(" ,") + found.group("mark")
	return text


class Grammar:
	"""VisionClaw's own lines and the user's own words. folder: VisionClaw's data folder, or None (then only the
	lines that come with VisionClaw). The files are read again when they change, so a line the user writes into
	their file counts at once."""

	def __init__(self, folder=None, builtIn=BUILT_IN):
		self.folder = folder
		self.builtIn = builtIn
		self._read = {}

	@property
	def ownPath(self):
		return os.path.join(self.folder, OWN_NAME) if self.folder else None

	def _rules(self, path, kind=None):
		if not path:
			return []
		try:
			stamp = os.path.getmtime(path)
		except OSError:
			return []
		kept = self._read.get(path)
		if kept and kept[0] == stamp:
			return kept[1]
		try:
			with open(path, encoding="utf-8") as f:
				rules = parse(f.read(), kind)
		except (OSError, UnicodeDecodeError) as e:
			debuglog.error("understand", f"The words in {path} could not be read", e)
			rules = []
		self._read[path] = (stamp, rules)
		return rules

	def rules(self):
		"""Every rule, the user's own first."""
		return self._rules(self.ownPath, OWN) + self._rules(self.builtIn)

	def read(self, request, where=None):
		"""The request as it is understood (a Reading). where: ADDON or PICTURE where the add-on writer or a question
		about a picture is read; then that section's lines apply too. Never raises: a fault leaves the request as it was
		said."""
		try:
			return self._understand(request, where)
		except Exception as e:
			debuglog.error("understand", f"{request!r} could not be read for its words", e)
			return Reading(" ".join(str(request or "").split()), [])

	def _understand(self, request, where=None):
		said = _SPACE.sub(" ", str(request or "").translate(_QUOTES)).strip()
		rules = [rule for rule in self.rules() if rule.scope is None or rule.scope == where]
		changes = []
		nothing = [rule for rule in rules if rule.kind in NOTHING]
		if _OWN_WORDS.search(said):
			# What is remembered, a skill and a word taught keep the user's own words; only a greeting is taken away.
			text = _trim(nothing, said, changes)
			return Reading(text if text.strip() else said, changes)
		text, spans = _keep(said, where)
		for rule in rules:
			if rule.kind == OWN:
				text = _apply(rule, text, changes, spans)
		text = _trim(nothing, text, changes)
		for kind in (SPELLING, SAME, TO_DO):
			for rule in rules:
				if rule.kind == kind:
					text = _apply(rule, text, changes, spans)
		text = _SPACE.sub(" ", _back(text, spans)).strip()
		if len(text) < 2:
			return Reading(said, [])
		if text == said:
			changes = []
		return Reading(text, changes)

	def trimmed(self, text):
		"""Text without the words said for nothing at its start and end (a greeting, please, thanks), and nothing else
		changed: the user's own way of saying a thing, as it is kept from a correction (claw/corrections.py)."""
		try:
			said = _SPACE.sub(" ", str(text or "").translate(_QUOTES)).strip()
			trimmed = _trim([rule for rule in self.rules() if rule.kind in NOTHING], said, [])
			return trimmed.strip(" .!?,;:") or said
		except Exception as e:
			debuglog.error("understand", f"{text!r} could not be trimmed", e)
			return " ".join(str(text or "").split())

	# --- The user's own words ---

	def own(self):
		"""The user's own words, as (said, meant)."""
		return [(rule.phrases[0], rule.meant) for rule in self._rules(self.ownPath, OWN)]

	def teach(self, said, meant):
		"""Keep a word of the user's. A word that was taught before is replaced. Returns True if it replaced one.
		Raises ValueError with a sentence for the user when the word cannot be kept."""
		said, meant = cleanSaid(said), cleanMeant(meant)
		problem = refusal(said, meant)
		if problem:
			raise ValueError(problem)
		kept = [(s, m) for s, m in self.own() if s.lower() != said.lower()]
		replaced = len(kept) != len(self.own())
		self._write(kept + [(said, meant)])
		return replaced

	def forget(self, said=None):
		"""Forget one word of the user's, or all of them when said is None. Returns what was forgotten, as
		(said, meant)."""
		words = self.own()
		if said is None:
			gone, kept = words, []
		else:
			wanted = cleanSaid(said).lower()
			gone = [(s, m) for s, m in words if s.lower() == wanted]
			kept = [(s, m) for s, m in words if s.lower() != wanted]
		if gone:
			self._write(kept)
		return gone

	def _write(self, words):
		if not self.ownPath:
			raise ValueError("VisionClaw has no data folder to keep your words in.")
		os.makedirs(self.folder, exist_ok=True)
		lines = "".join(f"- \"{s}\" means \"{m}\"\n" for s, m in words)
		temporary = self.ownPath + ".new"
		with open(temporary, "w", encoding="utf-8") as f:
			f.write(_OWN_HEAD + lines)
		os.replace(temporary, self.ownPath)
		self._read.pop(self.ownPath, None)


_CURRENT = [None]


def use(grammar):
	"""The grammar every part of VisionClaw reads words with: VisionClaw's own lines and the user's own words. Set by
	the add-on when it starts."""
	_CURRENT[0] = grammar


def current():
	"""The grammar set by the add-on, or VisionClaw's own lines alone when none was set (in tests, and before start)."""
	if _CURRENT[0] is None:
		_CURRENT[0] = Grammar(None)
	return _CURRENT[0]


def cleanSaid(text):
	return " ".join(str(text or "").translate(_QUOTES).strip(" \"'.,!?;:").split())


def cleanMeant(text):
	return " ".join(str(text or "").translate(_QUOTES).strip(" \"'.,!?;:").replace('"', "'").split())


_EVERYDAY = frozenset((
	"the a an and or but it its this that these those to of in on at for with is are be do does did i you me my "
	"your we us he she they them what which who how why when where yes no not please".split()))


def refusal(said, meant):
	"""Why a word cannot be taught, as a sentence for the user, or ""."""
	if sum(ch.isalnum() for ch in said) < MIN_LETTERS:
		return "That word is too short to be understood safely. Teach a word of at least two letters."
	if len(said) > MAX_SAID:
		return f"That is too long to be one word of yours. Keep it under {MAX_SAID} letters."
	if not meant or len(meant) > MAX_MEANT:
		return "Say what the word means, in a few words."
	if said.lower() == meant.lower():
		return "That word already means itself."
	if all(word in _EVERYDAY for word in said.lower().split()):
		return (f"\"{said}\" is in nearly every request, so it cannot be given another meaning. "
			"Choose a word of your own.")
	if '"' in said or "\n" in said or "\n" in meant:
		return "A word of yours cannot hold quotation marks or line breaks."
	return ""


# --- What the user's words ask of their own words ---

TEACH, LIST, FORGET, FORGET_ALL = "teach", "list", "forget", "forget all"
ACTIONS = [TEACH, LIST, FORGET, FORGET_ALL]
_Q = r"(?P<q>[\"']?)"
_TEACH = (
	re.compile(rf"^(?:from now on,?\s*)?(?:when(?:ever)?|if) i (?:say|type|write)\s+{_Q}(?P<said>[^\"]+?)(?P=q)\s*,?\s*"
		r"(?:i mean|that means|it means|i want you to|i want|please|do|then do|understand(?: it as| that as)?|take it as)\s+"
		r"(?P<meant>.+?)[.!]?$", re.IGNORECASE),
	re.compile(r"^(?:please\s+)?(?:understand|take|treat|read)\s+(?P<q>[\"'])(?P<said>.+?)(?P=q)\s+(?:as|to mean)\s+"
		r"(?:meaning\s+)?(?P<meant>.+?)[.!]?$", re.IGNORECASE),
	re.compile(r"^(?:please\s+)?understand\s+(?P<q>)(?P<said>[\w' -]{2,40}?)\s+(?:as|to mean)\s+(?:meaning\s+)?"
		r"(?P<meant>.+?)[.!]?$", re.IGNORECASE),
	re.compile(rf"^by\s+{_Q}(?P<said>[^\"]+?)(?P=q)\s*,?\s*i mean\s+(?P<meant>.+?)[.!]?$", re.IGNORECASE),
	re.compile(r"^(?:from now on,?\s*)?(?P<q>[\"'])(?P<said>.+?)(?P=q)\s+(?:means|should mean|will mean|is short for)\s+"
		r"(?P<meant>.+?)[.!]?$", re.IGNORECASE),
	re.compile(r"^from now on,?\s*(?P<q>)(?P<said>[\w' -]{2,40}?)\s+(?:means|should mean|will mean|is short for)\s+"
		r"(?P<meant>.+?)[.!]?$", re.IGNORECASE),
)
_FORGET_ALL = re.compile(
	r"\b(?:forget|delete|remove|clear|unlearn|erase)\b.{0,20}\b(?:all|every|each)\b.{0,20}\b(?:words?|phrases?|meanings?)\b"
	r".{0,30}\b(?:taught|told|gave|teach|of mine|my own|i (?:said|made))\b"
	r"|\b(?:forget|delete|remove|clear|unlearn|erase) (?:all )?(?:of )?my (?:own )?words\b"
	r"|\bunlearn (?:all|everything)\b", re.IGNORECASE)
_FORGET = (
	re.compile(rf"\b(?:forget|unlearn|delete|remove|stop understanding)\b(?: the| my)? (?:word|phrase|meaning|words)"
		rf"(?: of)?\s+{_Q}(?P<said>[^\"]+?)(?P=q)[.!]?$", re.IGNORECASE),
	re.compile(rf"\bforget what i (?:taught you|told you|said) about\s+{_Q}(?P<said>[^\"]+?)(?P=q)[.!]?$", re.IGNORECASE),
	re.compile(r"\b(?:forget|unlearn)\s+(?P<q>[\"'])(?P<said>.+?)(?P=q)[.!]?$", re.IGNORECASE),
	re.compile(rf"\bstop understanding\s+{_Q}(?P<said>[^\"]+?)(?P=q)\s+as\b", re.IGNORECASE),
)
_LIST = re.compile(
	r"\b(?:which|what|list|show|tell me|read)\b.{0,30}\b(?:words?|phrases?|meanings?)\b.{0,30}"
	r"\b(?:taught|told|gave|teach|of mine|my own|understand from me|i (?:made|said))\b"
	r"|\bmy own words\b|\bwords (?:that )?i (?:taught|told|gave) you\b", re.IGNORECASE)


def wishOf(part):
	"""What the user's words ask of their own words: {"what": TEACH, "said", "meant"}, {"what": FORGET, "said"},
	{"what": FORGET_ALL}, {"what": LIST}, or None when they ask nothing of them."""
	text = " ".join(str(part or "").translate(_QUOTES).split()).strip()
	if not text:
		return None
	if _FORGET_ALL.search(text):
		return {"what": FORGET_ALL}
	for pattern in _FORGET:
		found = pattern.search(text)
		if found:
			return {"what": FORGET, "said": cleanSaid(found.group("said"))}
	if _LIST.search(text):
		return {"what": LIST}
	for pattern in _TEACH:
		found = pattern.search(text)
		if found:
			said, meant = cleanSaid(found.group("said")), cleanMeant(found.group("meant"))
			if said and meant:
				return {"what": TEACH, "said": said, "meant": meant}
	return None


def actionOf(part):
	"""The action a request asks of the user's own words, for the tool's form: teach when nothing is clear."""
	wish = wishOf(part)
	return wish["what"] if wish else TEACH


def taken(text):
	"""What the user is told about how their words were understood."""
	text = text.rstrip()
	return f"Understood as: {text}" + ("" if text[-1:] in ".!?" else ".")


def changesText(reading):
	"""The changes of a reading in words, for VisionClaw's log and the user's progress."""
	parts = []
	for said, meant, kind in reading.changes:
		parts.append(f"\"{said}\" left out" if kind in NOTHING else f"\"{said}\" as \"{meant}\"")
	return "; ".join(parts)
