# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the instructions every model is given about the person it works for.
# The owner asked on 2026-11-17 for global system prompts made for the needs of blind people, after the example
# of VisionAssistantPro (Mahmood Hozhabri), which tells its model who the user is, to start with the answer,
# to read text exactly and never guess, and lets the user edit these instructions. Here they are kept in one
# place, in parts the user can rewrite in the window "How VisionClaw answers":
#   USER      who the user is: blind, listening to speech or reading braille;
#   SPEAKING  how an answer must be worded to be heard well;
#   SEEING    what matters in a picture to someone who cannot see it;
#   QUICK, DETAILED, BRIEF  what is asked for when a picture is described quickly, in detail, or in one
#             sentence (the automatic descriptions);
#   ADDON     what an add-on written on the fly must be for this user (the owner asked on 2026-11-17 that the
#             instructions, skills, memories and notes apply to add-ons written on the fly as well);
#   CODE_GUIDE, DEV_GUIDE, ADDON_HELP  what holds when lines of the downloaded developer guides come with the
#             writing of an add-on, and when an answer is made from those guides or from an installed add-on.
# The user's own instructions and the language of the answers come after them.
# The owner asked that the user can always put back the original wording after a mistake: VisionClaw's own
# wording is only ever kept here, in the code, and what the user wrote is kept beside it, so "restore" is
# forgetting what the user wrote. An empty part is VisionClaw's own wording.
#
# What gets them: every answer a model writes for the user to hear (speaking), and every description of a
# picture (seeing). A form a model fills in gets only IDENTITY: rules about wording mean nothing to a form,
# and the user's own words ("answer in French") could change the ids it must copy exactly. The same holds for
# code, notes that plain code checks word by word, and the short judgements about a control.
#
# Blind people work the mouse with NVDA's keyboard commands when they need it (the owner, 2026-11-17): so the
# rule is "no hand on the mouse, no looking", never "no mouse".
# The code-writing instructions for one kind of add-on (CODE_KINDS) are added only when the user's words ask
# for that kind, by plain code (the owner, 2026-11-17: they "must trigger when visionclaw deems each skill is
# appropriate according to user prompt").
# These are read by models of 0.8B to 9B. Every sentence is a plain rule, and there is not one example in
# them: a small model copies an example as if it were the answer. No NVDA dependencies.

import re

# Every form and judgement starts with this.
IDENTITY = "You are VisionClaw, an assistant inside the NVDA screen reader, helping a blind person."

USER = (
	"The user is blind. They hear your words through a speech synthesizer or read them on a braille display, "
	"and cannot see the screen."
)
SPEAKING = (
	"How to answer: Start with the answer itself, never with what you will do or what you were given. Use "
	"short, plain sentences. Write no Markdown, lists, tables or emoji: they are read out as noise. Copy names, "
	"file names, numbers and keys character for character, exactly as they are written; join the keys of a "
	"shortcut with plus signs. Say where something is in plain words, never as coordinates or "
	"pixels. Name a thing by its text or what it does, never only by its colour or look. Never ask the user to "
	"look for something or to move the mouse by hand. Name a controller's buttons as it names them. Give no "
	"advice that was not asked for. If you do not know something, say so instead of guessing."
)
SEEING = (
	"About pictures: Describe only what is shown. Read text exactly as it is written. If any word or number is "
	"too small or too blurry to read for certain, say that it cannot be read; never fill it in. When the picture "
	"shows that something is focused, selected, checked, highlighted or greyed out, say so. Do not guess who a "
	"person is or how old they are."
)
# Said right after what is asked, where a small model heeds it most: with it only in the instructions above,
# Qwen3.5 9B read a blurred error number as a made-up one (tests/live_prompts.py, 2026-11-17).
HONESTY = (
	" If text is too small or blurry to read, say so instead of guessing it. "
	"Do not guess who a person is or how old they are."
)
QUICK = (
	"Describe this image for a blind person in 2-3 short sentences. "
	"Say what it is, the main subjects, and read any important text." + HONESTY
)
DETAILED = (
	"Describe this image in detail for a blind person. Start with what kind of image it is, "
	"then describe the layout, people, objects, colours and actions. "
	"Read all visible text exactly as written." + HONESTY
)
BRIEF = (
	"Describe this image in one short sentence for a blind person. "
	"If it contains important text, read it." + HONESTY
)
ADDON = (
	"About the add-on: It is for this user, who works the computer from the keyboard and hears or reads "
	"everything through the screen reader. Whatever it tells the user, it says with ui.message in short, plain "
	"words. It never stops or silences speech or braille, and needs no mouse and no looking."
)
# What a kind of add-on must be for this user, added to the system prompt only when the request asks for that
# kind. Each is one plain rule about how the code is written, and no example: the coder copies an example whole.
# What the add-on does for the user (it always answers, speaks only what is new, braille) is in the code-writing
# skills (claw/skills/addon-*), chosen from the same words and sent in the user message, so nothing is said twice.
CODE_KEY = (
	"The user starts it with a key: give its script a description that says in plain words what it does, "
	"because that is how the user finds it in NVDA's list of input gestures."
)
CODE_AUTO = (
	"It works by itself: its event reacts only to the one kind of change the user asked about, and lets every "
	"other change pass to NVDA untouched."
)
CODE_PROGRAM = (
	"It is for one program or game: it checks the name of the program the control belongs to before it does "
	"anything."
)
# Added when lines of the downloaded developer guides come with the request (claw/guides.py): plain code found
# them by what the add-on is for, and the model is told what they are for. The owner asked on 2026-11-18 that
# the guides, once downloaded, be used with fitting skills, notes, memories and system prompts.
CODE_GUIDE = (
	"Lines from NVDA's developer guides come with the request: write the names of NVDA's functions and modules "
	"exactly as those lines write them, and use only the ones this add-on needs."
)
# For an answer the user hears, added when what was looked up is from the developer guides, or from an add-on
# that is installed in NVDA. Plain code sees where the lines are from (aboutFound).
DEV_GUIDE = (
	"About NVDA's developer guides: They are written for people who write add-ons, and this user may not read "
	"code. Say in plain words what a line from them means. Spell the names of functions and modules exactly as "
	"they are written, and read out no lines of code."
)
ADDON_HELP = (
	"About add-ons: When something is from an add-on that is installed in NVDA, say the name of that add-on. Say "
	"its keys exactly as its help or its command writes them. If the add-on is turned off, say so."
)
TRAINING_HELP = (
	"About training material: A line from the NVDA wiki, from AFB or from Hadley was written by others than the "
	"makers of NVDA, and some of it for an older NVDA. Say where it is from. Where NVDA's own user guide or "
	"commands say something else, they are right."
)
# How a line that was looked up begins when it is from the developer guides, from an add-on, and from the
# training material the user had downloaded (claw/lookup.py, claw/training.py).
_FOUND = (
	("devGuide", re.compile(r"From NVDA's developer guides:")),
	("addonHelp", re.compile(r"From (an add-on's help|the add-on\b)")),
	("trainingHelp", re.compile(r"From (the NVDA wiki|AFB's|Hadley's)\b")),
)
# Which words ask for which kind. Plain code decides; nothing is added when nothing fits.
CODE_KINDS = (
	("codeKey", re.compile(
		r"\b(press|key|keys|hot ?key|shortcut|gesture)\b|\b(nvda|control|ctrl|alt|shift|windows)\s*\+", re.IGNORECASE)),
	("codeAuto", re.compile(
		# "When I press a key" asks for a key, not for something that happens by itself.
		r"\b(when|whenever|every time|each time|as soon as)\b(?!\s+i\s+(press|hit|type|use))|"
		r"\b(automatic(ally)?|by itself|announce|tell me if|warn|alert|watch|monitor|appears?|changes?)\b",
		re.IGNORECASE)),
	("codeProgram", re.compile(
		r"\b(in|for|only in|inside) (this|the|my) (program|app|application|game|window|player|editor|browser)\b|"
		r"\bgames?\b|\bonly in\b", re.IGNORECASE)),
)
# The instructions every answer or description gets, the requests of the three kinds of description, and what
# each kind of add-on must be.
GLOBAL = ("user", "speaking", "seeing", "addon")
REQUESTS = ("quick", "detailed", "brief")
CODE = tuple(name for name, _words in CODE_KINDS) + ("codeGuide",)
# What an answer is told besides, by where the lines it is made from come from.
ANSWERS = tuple(name for name, _begins in _FOUND)
PARTS = GLOBAL + REQUESTS + CODE + ANSWERS
DEFAULTS = {
	"user": USER, "speaking": SPEAKING, "seeing": SEEING, "addon": ADDON, "quick": QUICK, "detailed": DETAILED,
	"brief": BRIEF, "codeKey": CODE_KEY, "codeAuto": CODE_AUTO, "codeProgram": CODE_PROGRAM, "codeGuide": CODE_GUIDE,
	"devGuide": DEV_GUIDE, "addonHelp": ADDON_HELP, "trainingHelp": TRAINING_HELP,
}
# The user's own instructions are cut to this: they are read with every answer, by models with little room.
OWN_CHARS = 500
# A rewritten part is cut to this, for the same reason.
PART_CHARS = 1000

_custom = {}
_own = ""
_language = ""


def oneLine(text, chars=None):
	"""Text as one line: lines that do not end a sentence get a full stop, so they are not run together."""
	lines = []
	for line in str(text or "").splitlines():
		line = " ".join(line.split())
		if line:
			lines.append(line if line[-1] in ".!?:;," else line + ".")
	text = " ".join(lines)
	if chars and len(text) > chars:
		text = text[:chars].rsplit(" ", 1)[0]
	return text


def configure(custom=None, own="", language=""):
	"""What the user set: custom maps a part to the user's own wording of it ("" or a missing part is
	VisionClaw's own); own is the user's own instructions; language is the name of the language to answer in,
	"" for English or when the user did not ask for NVDA's language."""
	global _custom, _own, _language
	_custom = {}
	for part, text in (custom or {}).items():
		text = oneLine(text, PART_CHARS)
		if part in DEFAULTS and text and text != DEFAULTS[part]:
			_custom[part] = text
	_own = oneLine(own, OWN_CHARS)
	_language = " ".join(str(language or "").split())


def part(name):
	"""One part as it is used now: the user's wording if they rewrote it, else VisionClaw's own."""
	return _custom.get(name) or DEFAULTS[name]


def isCustom(name):
	return name in _custom


def customized():
	"""The parts the user rewrote, in order."""
	return [name for name in PARTS if name in _custom]


def own():
	return _own


def _tail(code=False):
	text = ""
	if _own:
		text += f"\nThe user asks you to keep to this: {_own}"
	if _language:
		# In code, only what the add-on says to the user is in the user's language; names in the code are not.
		text += f"\nWrite what the add-on says to the user in {_language}." if code else f"\nAnswer in {_language}."
	return text


def _build(task, parts, code=False):
	"""The task's first line (who the model is and what it does), who the user is, the task's own rules, then the
	wording parts, the user's own instructions and the language. The order was measured with Qwen3.5 9B on
	2026-11-17: with the wording rules before the task's rules, "how do I read the title" was answered "press
	NVDA+T twice" (which spells it) 2 times in 6; with them after, 0 times in 6."""
	task = str(task or "").strip() or IDENTITY
	head, _sep, rules = task.partition("\n")
	lines = [head, part("user")] + ([rules.strip()] if rules.strip() else []) + [part(name) for name in parts]
	return "\n".join(lines) + _tail(code)


def aboutFound(found):
	"""The parts an answer is told besides, by where the lines that were looked up are from: the developer
	guides, an installed add-on. Plain code decides, and nothing is added when the lines are from neither."""
	text = str(found or "")
	return tuple(name for name, begins in _FOUND if begins.search(text))


def speaking(task="", found=""):
	"""The system prompt for an answer the user hears: the task, who the user is, how to word the answer, and,
	where what was looked up (found) is from the developer guides or an add-on, what holds for those."""
	return _build(task, ("speaking",) + aboutFound(found))


def seeing(task=""):
	"""The system prompt for describing a picture, or answering a question about one."""
	return _build(task, ("speaking", "seeing"))


def codeKinds(purpose):
	"""The kinds of add-on the user's words ask for, in order, by plain code."""
	return tuple(name for name, words in CODE_KINDS if words.search(str(purpose or "")))


def coding(task, purpose="", guided=False):
	"""The system prompt for writing, reviewing or repairing an add-on on the fly: the task's first line, who
	the user is, the task's own rules, what the add-on must be for this user and for the kinds of add-on the
	request asks for (purpose: the user's words), what holds for lines of the developer guides when some come
	with the request (guided), the user's own instructions, and the language of what the add-on says."""
	return _build(task, ("addon",) + codeKinds(purpose) + (("codeGuide",) if guided else ()), code=True)


def summary():
	"""Everything the models are told, as the user can read it, one part to a paragraph."""
	lines = [part("user"), part("speaking"), part("seeing"), part("addon")]
	if _own:
		lines.append(f"Your own instructions: {_own}")
	if _language:
		lines.append(f"Answers are in {_language}.")
	return "\n\n".join(lines)
