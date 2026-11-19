# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - which version of something is installed: VisionClaw itself, NVDA, one add-on of NVDA, or the program
# in front. The owner asked on 2026-11-19 "tell me the version of visionclaw I have installed?" and was read the list
# of all 25 add-ons: the words "tell me ... version" had set off the pattern for what NVDA has, the model chose it, and
# that job reads out every add-on. The owner said what must happen instead: find the add-on in question, get its
# version, "give me what I asked for and no more, no assuming I want more unless I say I am a beginner screen reader
# user or some variation of that".
#
# So plain code reads from the user's own words that a version is asked for, and of what (wish); the NVDA side reads
# the version from the running NVDA, the add-on's own manifest or the program (versiontools.py); and the answer is
# one sentence for each thing that was asked about (answer). Only where the user says they are new to this, in the
# request or in what they asked VisionClaw to remember, does a sentence follow on where to find it themselves next
# time (beginner). No model is asked. No NVDA imports.

import re

VISIONCLAW, NVDA, NAMED, PROGRAM = "visionclaw", "nvda", "named", "program"
# What the add-on's state is called when it is not on (claw/addons.py: ON, OFF, WAITING).
_OFF, _WAITING = "turned off", "installed but not running"

# The words ask which version something is.
_ASKS = re.compile(r"\bversions?\b|\b(which|what) (build|release)\b", re.IGNORECASE)
# Words with which a version is no question about what is installed here: a newer one (update_visionclaw), what is
# new in one (NVDA's own list of what is new), what something needs or supports, an add-on to be written, a key, a
# model of VisionClaw's (model_info), Windows (the computer's facts), Python, the guides and the training material.
_NOT = re.compile(
	r"\b(update\w*|upgrad\w*|newer|newest|latest|up[- ]?to[- ]?date|out[- ]?of[- ]?date|outdated|new versions?|"
	r"downgrad\w*|roll(ed|ing)? back|download\w*|reinstall\w*|(re)?install (the|a|an|version|v?\d)|what'?s new|whats new|new in|changes?|changed|"
	r"changelog|change log|release notes|fixed|fixes|needs?|requires?|required|support\w*|compatib\w*|works? with|"
	r"minimum|write|writes|make|create|build an?|code|script|hot ?keys?|keys?|shortcuts?|press\w*|when|whenever|"
	r"remove|uninstall|delete|disable|enable|turn (on|off)|switch|models?|qwen|llm|python|windows|guides?|training|"
	r"lessons?|materials?|(does|do|did) (nvda|visionclaw|it|this) (use|ship|come with|include|bundle)|"
	# A version of a file or a document, and version control, are something else.
	r"version (control|history)|versioning|git|previous|older|earlier|old versions?|other versions?|another version|"
	r"different versions?|restore|recover|files?|documents?)\b", re.IGNORECASE)
# The user says they are new to this. The owner's words: "unless I say I am a beginner screen reader user or some
# variation of that". The same words in a memory ("You are new to NVDA") count too.
_BEGINNER = re.compile(
	r"\b(beginners?|novices?|newbies?|new (to|with|at) (nvda|screen ?readers?|computers?|windows|visionclaw|add-?ons?|"
	r"using|(this|it|all this)(?=\s*[.,!?;:]|\s*$))|(i'?m|i am|you'?re|you are|we'?re|we are) (still |quite |very |really |totally |"
	r"completely )?(new(?=\s*[.,!?;:]|\s*$| here\b| users?\b| at this\b)|learning (nvda|to use|a screen ?reader|"
	r"screen ?readers?|computers?|the computer|this|it)\b)|never used (nvda|a screen ?reader|screen ?readers?|a computer)|"
	r"first time (using|with|on) (nvda|a screen ?reader|screen ?readers?|a computer)|"
	r"just (started|starting|began|beginning) (with |using |to use |on )?(nvda|a screen ?reader|screen ?readers?)|"
	r"learning (nvda|to use|a screen ?reader|screen ?readers?))", re.IGNORECASE)
# What the beginner words are taken out with, so that "screen reader" in "a beginner screen reader user" does not name
# NVDA as a thing to tell the version of.
_BEGINNER_WORDS = re.compile(
	r"\b(an? )?(complete |total |real |absolute )?(beginners?|novices?|newbies?)( (screen ?readers?|nvda|computer|blind))*"
	r"( users?)?\b|\bnew (to|with|at) (nvda|screen ?readers?|computers?|this|it|all this|windows|visionclaw|add-?ons?|"
	r"using)( (nvda|screen ?readers?|computers?))?( users?)?\b|\bnever used (nvda|a screen ?reader|screen ?readers?|"
	r"a computer)( before)?\b|\bfirst time (using|with|on) (nvda|a screen ?reader|screen ?readers?|a computer)\b|"
	r"\bjust (started|starting|began|beginning) (with |using |to use |on )?(nvda|a screen ?reader|screen ?readers?)\b|"
	r"\blearning (nvda|to use|a screen ?reader|screen ?readers?)\b|\b(i'?m|i am) (still |quite |very |really |totally |"
	r"completely )?(new|learning)\b", re.IGNORECASE)
# Asking politely, which names nobody: "can you tell me", "do you know".
_POLITE = re.compile(
	r"\b(can|could|would|will|won'?t) you( please)?( (tell|say|check|know|find|give|show|let|get|read|look|see))?\b"
	r"|\b(do|did) you (know|remember)\b|^\W*((hey|ok|okay) )?vision ?claw\s*[,:]", re.IGNORECASE)
# The program in front, named by where it is.
_THIS_PROGRAM = re.compile(
	r"\b(this|the current|my current|the) (program|app|application|game|software)\b"
	r"|\b(program|app|application|game|software) (i'?m|i am) (in|using|on)\b|\bthe (program|app|window) in front\b",
	re.IGNORECASE)
_PROGRAM_WORDS = re.compile(r"\b(program|app|application|game|software)\b", re.IGNORECASE)
# VisionClaw itself, as the user may write it; "you" and "your" only where nothing else is named.
_VISIONCLAW = re.compile(r"^vision ?claw$", re.IGNORECASE)
_YOU = re.compile(r"\b(you|your|yours|yourself)\b", re.IGNORECASE)
_NVDA_WORDS = frozenset(("nvda", "screen", "reader", "screenreader", "nvdas"))
# Words between the names of two things: "NVDA and VisionClaw", "NVDA as well as VisionClaw".
_APART = frozenset(("and", "plus", "&", "also", "both"))
_AS_WELL_AS = re.compile(r"\bas well as\b", re.IGNORECASE)
# Words that name no thing whose version is asked.
_FILLER = frozenset("""
	what whats which tell me say give show check find out get report read let know want like would could can will please
	do does did i you my mine your yours yourself have has got having is are was were am be been being the a an of for
	on in at to this that these those it its version versions number numbers exact current currently running run using
	use used install installed set put here now right today copy computer pc machine laptop just only s m d ll ve re there any one
	ones add addon addons add-on add-ons plugin plug-in plugins plug-ins extension extensions program app application
	game software front so if whether into about info information release build called named by from with see look up
	wondering wonder curious kind sort quick quickly hey ok okay as thing things
	user users kindly need actually exactly precisely we our us them they he she his her
""".split())
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_]*(?:-[A-Za-z0-9.+_]+)*|&|,|;")
_NUMBER = re.compile(r"^v?\d+(\.\d+)*\.?$", re.IGNORECASE)


def beginner(*texts):
	"""Whether the user says they are new to this, in the request or in what they asked VisionClaw to remember."""
	return any(_BEGINNER.search(str(text or "")) for text in texts)


def _groups(text):
	"""The names in the words, as groups of words between "and" and commas, each in the user's own spelling."""
	groups, current = [], []
	tokens = _TOKEN.findall(_AS_WELL_AS.sub(" and ", text))
	i = 0
	while i < len(tokens):
		token = tokens[i]
		low = token.lower().rstrip(".")
		if low in (",", ";") or low in _APART:
			if current:
				groups.append(current)
			current = []
		elif low == "vision" and i + 1 < len(tokens) and tokens[i + 1].lower() == "claw":
			current.append("VisionClaw")
			i += 1
		elif low not in _FILLER and not _NUMBER.match(low):
			current.append(token.rstrip("."))
		i += 1
	if current:
		groups.append(current)
	return groups


def wish(part):
	"""What the user's words ask the version of, or None where they ask no such thing: {"things": [(kind, name)],
	"beginner": the words say the user is new to this, "program": the words name a program}. kind is VISIONCLAW,
	NVDA, NAMED (an add-on or the program in front, called by name) or PROGRAM (the program in front)."""
	text = " ".join(str(part or "").split())
	if not _ASKS.search(text):
		return None
	asked = _BEGINNER_WORDS.sub(" ", text)
	if _NOT.search(asked):
		return None
	asked = _POLITE.sub(" ", asked)
	programWords = bool(_PROGRAM_WORDS.search(asked))
	things = []
	for group in _groups(asked):
		words = [word.lower() for word in group]
		if any(_VISIONCLAW.match(word) for word in words) or "visionclaw's" in words:
			thing = (VISIONCLAW, "VisionClaw")
		elif all(word in _NVDA_WORDS for word in words):
			thing = (NVDA, "NVDA")
		else:
			thing = (NAMED, " ".join(group))
		if thing not in things:
			things.append(thing)
	if not things and _THIS_PROGRAM.search(asked):
		things.append((PROGRAM, ""))
	if not things and _YOU.search(asked):
		things.append((VISIONCLAW, "VisionClaw"))
	if not things:
		return None
	return {"things": things, "beginner": beginner(text), "program": programWords}


def _versionSaid(name, version, state=""):
	if not version:
		return f"{name} does not say which version it is."
	said = f"{name} is version {version}."
	if state == _OFF:
		said += " It is turned off."
	elif state == _WAITING:
		said += " It is installed but not running."
	return said


def answer(found, isBeginner=False):
	"""What the user is told: one sentence for each thing asked about, and nothing more, unless the user said they are
	new to this; then one sentence each on where to find it themselves next time. found: one dict for each thing, as
	versiontools reads it: kind, name, version, state, found (False where no add-on and no program has the name),
	front (the name of the program in front)."""
	lines, kinds = [], []
	for thing in found:
		kind, name = thing.get("kind"), str(thing.get("name") or "").strip()
		version = str(thing.get("version") or "").strip()
		if kind == VISIONCLAW:
			lines.append(_versionSaid("VisionClaw", version))
		elif kind == NVDA:
			lines.append(_versionSaid("NVDA", version))
		elif not thing.get("found"):
			front = str(thing.get("front") or "").strip()
			lines.append(
				f"No add-on called \"{name}\" is installed in NVDA"
				+ (f", and the program in front is {front}" if front else "")
				+ ". To hear the version of another program, move to it and ask again.")
			continue
		elif kind == PROGRAM or thing.get("program"):
			lines.append(_versionSaid(name or "The program in front", version)
				if version else f"{name or 'The program in front'} does not tell NVDA which version it is.")
		else:
			lines.append(_versionSaid(name, version, thing.get("state", "")))
		kinds.append(PROGRAM if (kind == PROGRAM or thing.get("program")) else kind)
	if isBeginner:
		lines += [_NEXT_TIME[kind] for kind in dict.fromkeys(kinds) if kind in _NEXT_TIME]
	return "\n".join(lines) or "Nothing was found to tell the version of."


# For someone new to this, where to find the version themselves next time. Keys as NVDA names them; the menus were
# read from NVDA 2026.3.1 on this computer (gui/__init__: the NVDA menu's Help with About, Tools with the Add-on Store)
# and from its user guide ("Press NVDA+n to open the NVDA menu, then t for tools, then a for Add-on Store").
_NEXT_TIME = {
	VISIONCLAW: (
		"A version number says which release you have; a higher number is newer. To look for a newer VisionClaw, "
		"press NVDA+Alt+U."),
	NVDA: "To see NVDA's version yourself, press NVDA+N for the NVDA menu, then H for Help, and choose About.",
	NAMED: (
		"To see every add-on with its version yourself, press NVDA+N for the NVDA menu, then T for Tools, then A for "
		"the Add-on Store; the Installed add-ons tab lists them."),
	PROGRAM: "In many programs, Alt then H opens the Help menu, whose About item says the version.",
}
