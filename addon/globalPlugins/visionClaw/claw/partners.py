# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - two add-ons of the owner's that VisionClaw works together with when they are installed: the JAWS
# Migration Assistant (jawsMigrator, MIT) and ClassicSpeech (GPL v2). The owner said on 2026-11-18: "if the jaws
# migrator addon and classicSpeech addon are installed, visionclaw will be even more powerful! let it take
# advantage of both of those addons too."
#   With the JAWS Migration Assistant: what a JAWS keystroke or a JAWS command is in NVDA, from that add-on's own
#   knowledge of both; what its last migration brought over; and the commands of its layer.
#   With ClassicSpeech: its verbosity level and its speech and sound schemes changed by asking, which JAWS's own
#   assistant says it cannot do yet for JAWS's schemes and voice profiles; and its windows opened by name.
# Here is the plain logic: what the user's words ask of each. Neither add-on has an interface for other add-ons;
# what VisionClaw reads and calls in them was read from their source on 2026-11-18 (jawsMigrator 1.63,
# ClassicSpeech 1.16) and is named in partnertools.py. Nothing of theirs is copied into VisionClaw, nothing of
# the JAWS Migration Assistant's is ever written, and ClassicSpeech is changed only with the calls its own
# commands and windows make. Without the add-on, its job is not offered at all. No NVDA dependencies.

import re

JAWS, CLASSIC = "jawsMigrator", "ClassicSpeech"
_here = set()


def setInstalled(names):
	"""Told by the add-on before each request: which of the two are running in this NVDA."""
	_here.clear()
	_here.update(name for name in names if name in (JAWS, CLASSIC))


def has(name):
	return name in _here


def _clean(text):
	return " ".join(str(text or "").split())


# --- ClassicSpeech ---

LEVELS = ("Beginner", "Intermediate", "Advanced")
# What each level says of a control, read from ClassicSpeech's own verbosity.py.
LEVEL_SAYS = {
	"Beginner": "NVDA says everything about a control: its name, kind, state, position, description and key.",
	"Intermediate": "NVDA says a control's name, kind, state and position, and leaves out its description and key.",
	"Advanced": "NVDA says a control's name and state, and leaves out its kind, position, description and key.",
}
INFO, LEVEL, SCHEMES, SCHEME, SCHEMES_ON, NEXT, OPEN = "info", "level", "schemes", "scheme", "schemes on", "next", "open"
# ClassicSpeech's windows, by the words people use, and the name of its own command that opens each.
WINDOWS = (
	(r"\bvoice profiles?\b", "script_openClassicSpeechVoiceProfiles", "ClassicSpeech's Voice Profiles"),
	(r"\b(speech and sound |sound |speech )?schemes?\b", "script_openClassicSpeechSchemes", "ClassicSpeech's Speech and Sound Schemes"),
	(r"\b(web|browse mode)\b", "script_openClassicSpeechWebBrowseSettings", "ClassicSpeech's Web and Browse Mode settings"),
	(r"\b(user )?guide\b|\bhelp\b|\bmanual\b", "script_openClassicSpeechUserGuide", "ClassicSpeech's user guide"),
	(r"\bsettings\b|\boptions\b|\bclassic ?speech\b", "script_openClassicSpeechSettings", "ClassicSpeech's settings"),
)
_ABOUT_CLASSIC = re.compile(
	r"\bclassic ?speech\b|\b(speech and sound|sound|speech) schemes?\b|\bvoice profiles?\b|\bverbosity\b"
	r"|\b(beginner|intermediate|advanced) (level|verbosity|mode|profile)\b|\bschemes?\b.{0,20}\b(on|off|next|switch|which|list)\b"
	r"|\b(which|what|list|next|switch|use|turn)\b.{0,30}\bschemes?\b", re.IGNORECASE)
_OPENS = re.compile(r"^\s*(please\s+)?(open|show|bring up|go to|take me to|launch)\b", re.IGNORECASE)
_LEVEL = re.compile(r"\b(beginner|intermediate|advanced)\b", re.IGNORECASE)
_LESS = re.compile(r"\b(less (wordy|verbose|verbosity|chatty|talkative|detail)|say less|fewer words|shorter|more (advanced|terse|brief))\b", re.IGNORECASE)
_MORE = re.compile(r"\b(more (wordy|verbose|verbosity|detail|talkative)|say more|more words)\b", re.IGNORECASE)
_SCHEMES_SWITCH = re.compile(
	r"\b(turn|switch)\b.{0,12}\b(speech and sound |sound |speech )?schemes?\b.{0,6}\b(on|off)\b"
	r"|\b(turn|switch) (on|off)\b.{0,16}\bschemes?\b|\b(enable|disable)\b.{0,16}\bschemes?\b", re.IGNORECASE)
_NEXT = re.compile(r"\bnext\b.{0,24}\bscheme\b", re.IGNORECASE)
_LISTS = re.compile(r"\b(which|what|list|how many|name)\b.{0,40}\bschemes?\b|\bschemes?\b.{0,20}\b(do i have|are there|is (on|active|in use))\b", re.IGNORECASE)
_USES = re.compile(
	r"\b(?:switch to|change to|use|activate|select|choose|pick|load|set)\s+(?:the\s+)?(?:scheme\s+)?(?:called\s+|named\s+)?(?P<name>.+?)"
	r"(?:\s+(?:speech and sound |sound |speech )?scheme)?\s*[.!?]*\s*$", re.IGNORECASE)


def classicWish(part):
	"""What the user's words ask of ClassicSpeech, or None when they are not about it:
	{"what": INFO, LEVEL (with "level", or "step" +1 for less and -1 for more), SCHEMES, SCHEME (with "name", the
	words that may name one), SCHEMES_ON (with "on"), NEXT, or OPEN (with "script" and "said")}."""
	text = _clean(part)
	if not _ABOUT_CLASSIC.search(text):
		return None
	if _OPENS.match(text):
		for pattern, script, said in WINDOWS:
			if re.search(pattern, text, re.IGNORECASE):
				return {"what": OPEN, "script": script, "said": said}
	found = _LEVEL.search(text)
	if found and not re.search(r"\bscheme", text, re.IGNORECASE):
		return {"what": LEVEL, "level": found.group(1).capitalize()}
	if _LESS.search(text):
		return {"what": LEVEL, "step": 1}
	if _MORE.search(text):
		return {"what": LEVEL, "step": -1}
	switch = _SCHEMES_SWITCH.search(text)
	if switch:
		return {"what": SCHEMES_ON, "on": not re.search(r"\b(off|disable)\b", switch.group(0), re.IGNORECASE)}
	if _NEXT.search(text):
		return {"what": NEXT}
	if _LISTS.search(text):
		return {"what": SCHEMES}
	uses = _USES.search(text)
	if uses and re.search(r"\bscheme", text, re.IGNORECASE):
		return {"what": SCHEME, "name": _clean(uses.group("name"))}
	return {"what": INFO}


def pickName(words, names):
	"""Which of several names the user's words mean: the one that is in the words whole, the longest first; else
	the one whose every word is in them. None where none or more than one fits."""
	low = " " + " ".join(re.findall(r"[a-z0-9]+", str(words or "").lower())) + " "
	whole = [name for name in names if " " + " ".join(re.findall(r"[a-z0-9]+", name.lower())) + " " in low]
	if whole:
		longest = max(len(name) for name in whole)
		best = [name for name in whole if len(name) == longest]
		return best[0] if len(best) == 1 else None
	asked = set(low.split())
	partly = [name for name in names if set(re.findall(r"[a-z0-9]+", name.lower())) and set(re.findall(r"[a-z0-9]+", name.lower())) <= asked]
	return partly[0] if len(partly) == 1 else None


def nextLevel(now, step):
	"""The level one step on from this one: +1 says less, -1 says more; None at the end."""
	at = LEVELS.index(now) if now in LEVELS else 0
	return LEVELS[at + step] if 0 <= at + step < len(LEVELS) else None


CLASSIC_MISSING = (
	"ClassicSpeech is not running in this NVDA. With it, VisionClaw can change how much NVDA says about each control "
	"and switch speech and sound schemes when you ask. It is at github.com/joshknnd1982/classicspeech-nvda.")
CLASSIC_CHANGED = (
	"This version of ClassicSpeech keeps that in another way than VisionClaw knows, so VisionClaw changed nothing. Its "
	"own windows do it: NVDA menu, Preferences, ClassicSpeech.")

# --- The JAWS Migration Assistant ---

KEY, COMMAND = "key", "command"
_JAWS = re.compile(r"\bjaws(?:'s|')?\b", re.IGNORECASE)
_MIGRATION = re.compile(
	r"\b(migrat\w+|import\w*|brought over|bring over|came over|carried over|transferr?ed|backup|layer)\b", re.IGNORECASE)
# A question about a JAWS command names it as one. "What is the JAWS cursor called in NVDA" asks about an idea,
# and is answered from NVDA's help and the notes for people who come from JAWS, as before (measured with Qwen3.5
# 9B on 2026-11-18: sent to the JAWS Migration Assistant, it would have been answered with a keystroke).
_NAMES_COMMAND = re.compile(r"\b(commands?|keystrokes?|hot ?keys?|shortcuts?|scripts?)\b", re.IGNORECASE)
_MOD = r"(?:insert|ins|jaws ?key|caps ?lock|control|ctrl|alt|shift|windows|win)"
_MAIN = (
	r"(?:f\d{1,2}|[a-z0-9]|up ?arrow|down ?arrow|left ?arrow|right ?arrow|page ?up|page ?down|home|end|tab|enter|escape|esc|"
	r"space(?:bar)?|backspace|delete|num ?pad ?\d|num ?pad ?(?:plus|minus|slash|star|enter)|comma|period|semicolon|slash|"
	r"apostrophe|dash|equals|grave|left ?bracket|right ?bracket|backslash)")
_KEYSTROKE = re.compile(rf"\b((?:{_MOD}\s*(?:\+|-|\s)\s*)+{_MAIN})\b", re.IGNORECASE)
# Short forms people write, as JAWS's own key maps write them. A key VisionClaw does not know how JAWS writes is
# left as the user wrote it; the JAWS Migration Assistant then says whether it knows it.
_TOKENS = {"ins": "insert", "ctrl": "control", "win": "windows", "esc": "escape", "space": "spacebar"}
_FILLER = frozenset((
	"what", "is", "the", "a", "an", "in", "nvda", "jaws", "jaws's", "for", "of", "to", "equivalent", "version", "command",
	"commands", "key", "keys", "keystroke", "shortcut", "does", "do", "how", "i", "which", "s", "its", "called", "name", "like",
	"with", "as", "that", "and", "on", "my", "me", "please", "now", "use", "used", "did", "was", "it"))


def jawsKey(text):
	"""A JAWS keystroke written in a text, in the form JAWS's own key maps write it: "insert+f7"; "" for none."""
	hit = _KEYSTROKE.search(_clean(text))
	if not hit:
		return ""
	raw = hit.group(1).lower()
	# Names of two words are one key: "caps lock", "up arrow", "num pad 5".
	raw = re.sub(r"\b(jaws|caps|up|down|left|right|page|space|num) (key|lock|arrow|up|down|bar|bracket|pad)\b", r"\1\2", raw)
	raw = re.sub(r"\bnumpad (\w+)\b", r"numpad\1", raw)
	tokens = [_TOKENS.get(token, token) for token in re.split(r"[\s+\-]+", raw) if token]
	# "The JAWS key Insert+F7": the JAWS key is named, and then which key it is.
	if "jawskey" in tokens and ("insert" in tokens or "capslock" in tokens):
		tokens.remove("jawskey")
	return "+".join(tokens)


def jawsWish(part):
	"""What the user's words ask about JAWS, or None when they do not name JAWS:
	{"what": KEY with "key"; COMMAND with "words", what the JAWS command is called; or INFO}. None too for a
	question about JAWS that names no keystroke, no command and nothing of the migration."""
	text = _clean(part)
	if not _JAWS.search(text):
		return None
	key = jawsKey(text)
	if key:
		return {"what": KEY, "key": key}
	if _MIGRATION.search(text):
		return {"what": INFO}
	if not _NAMES_COMMAND.search(text):
		return None
	words = [word for word in re.findall(r"[a-z0-9']+", text.lower()) if word not in _FILLER]
	if words:
		return {"what": COMMAND, "words": " ".join(words)}
	return {"what": INFO}


def matchCommand(words, names):
	"""The JAWS commands a few words may mean, the best first, at most three. names: {JAWS's name for a command,
	in lower case and one word: what it does in NVDA, in words}. A name that the words spell out wins; else the
	commands whose description has most of the words."""
	asked = re.findall(r"[a-z0-9]+", str(words or "").lower())
	if not asked:
		return []
	joined = "".join(asked)
	if joined in names:
		return [joined]
	scored = []
	for name, description in names.items():
		has = set(re.findall(r"[a-z0-9]+", str(description).lower()))
		shared = sum(1 for word in asked if word in has or word in name)
		if shared and shared / len(asked) >= 0.6:
			scored.append((-shared / len(asked), len(name), name))
	return [name for _score, _length, name in sorted(scored)[:3]]


JAWS_MISSING = (
	"The JAWS Migration Assistant is not running in this NVDA. With it, VisionClaw can say what any JAWS keystroke or "
	"JAWS command is in NVDA. It is at github.com/joshknnd1982/jawsMigrator.")
NO_KEYMAP = (
	"JAWS's own key map was not found on this computer, so VisionClaw cannot look that keystroke up. The JAWS "
	"Migration Assistant can still tell you: press NVDA+Shift+J, then K, then the JAWS keystroke.")
