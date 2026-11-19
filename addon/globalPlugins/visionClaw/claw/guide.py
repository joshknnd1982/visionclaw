# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - working through a task with the user when the usual path is not clear: "I'm stuck, I want to
# attach a file to this email", "walk me through exporting this as a PDF", "I can't find how to change the font
# here". VisionClaw looks at what the program in front offers, finds the thing that leads to what the user wants,
# says what it is and which key reaches it, presses it if the user says yes, looks again at what that brought
# up, and goes on from there, one step at a time.
# What is plain logic is here: what the user wants, in their own words; which of the things in the window are
# about it; what changed after a step; and the walk itself, with its rules:
#   - every step is asked about before it is taken, and the user can have it only told, or stop;
#   - after a few steps VisionClaw checks in before it goes on;
#   - it stays in one program: when a step brings another program to the front, it stops and says so;
#   - its own windows, and NVDA's, are never worked;
#   - at the end it says what it did, in order, and what is in front now.
# A model is asked only to choose among the few things plain code found, and only where plain code is not sure.
# What reads the window and presses things is in guidetools.py. No NVDA dependencies.

import re

MAX_STEPS = 8
# After this many steps VisionClaw asks whether to go on.
CHECK_AFTER = 3
MAX_OFFERED = 8
YES, TELL, STOP = 0, 1, 2
CHOICES = ("Yes, press it", "No, only tell me where it is", "Stop here")
GO_ON = ("Yes, go on", "No, stop here")

# Words that say the user is stuck or wants to be led, and are no part of what they want.
_STUCK = re.compile(
	r"\b(i(?:'m| am)? (?:really |totally |completely )?stuck(?: here| on this| with this)?|get (?:me )?unstuck|"
	r"(?:please |can you |could you )?(?:walk|guide|lead|take|talk) me through|work (?:me )?through|step by step|"
	r"i (?:can'?t|cannot|can not|could not|couldn'?t) (?:find|figure out|work out|see|tell) (?:how|where|the way|a way)(?: to| i)?|"
	r"i (?:don'?t|do not) know (?:how|where)(?: to| i)?|i (?:am|'m) (?:trying|not able|unable) to|i want to|i need to|"
	r"i would like to|i'd like to|help me (?:get|do|finish|complete) (?:this|that|it)(?: done)?|help me(?: to| with)?|(?:the )?usual (?:way|path|key|keys|shortcut) (?:does not|doesn'?t|isn'?t|is not|won'?t) "
	r"work(?:ing)?|(?:and )?(?:it|that|this) (?:does not|doesn'?t|won'?t) work|how (?:do|can|would) i|(?:can|could) you|please)\b",
	re.IGNORECASE)
# The words that make a request one to be worked through: the user says they are stuck, or asks to be led.
_ASKS = re.compile(
	r"\bi(?:'m| am) (?:really |totally |completely )?stuck\b|\bget (?:me )?unstuck\b|\b(?:walk|guide|lead|talk) me through\b"
	r"|\bwork (?:me )?through\b|\bstep by step\b"
	r"|\bi (?:can'?t|cannot|can not|couldn'?t) (?:find|figure out|work out|see) (?:how|where|the way|a way)\b"
	r"|\bi (?:don'?t|do not) know (?:how|where) to\b"
	r"|\bhelp me (?:get|do|finish|complete|with) (?:this|that|it)\b"
	r"|\b(?:the )?usual (?:way|path|key|keys|shortcut) (?:does not|doesn'?t|isn'?t|is not|won'?t) work", re.IGNORECASE)
_SMALL = frozenset((
	"a", "an", "the", "this", "that", "these", "those", "my", "your", "its", "it", "to", "in", "on", "at", "of", "for", "with",
	"from", "into", "as", "and", "or", "but", "so", "is", "are", "be", "do", "does", "i", "me", "here", "there", "now", "just",
	"how", "where", "what", "which", "way", "thing", "things", "something", "some", "any", "can", "get", "want", "need", "use",
	"make", "program", "app", "application", "window", "page", "site", "one", "new", "up", "out", "then", "when", "if"))
# Words that mean the same thing in a program's menus as in what people say.
_ALIKE = (
	("attach", "attachment", "attachments", "paperclip", "insert", "add"), ("save", "export", "download"),
	("open", "load", "browse"), ("print", "printer", "printing"), ("settings", "options", "preferences", "configure", "configuration", "setup"),
	("send", "submit", "post"), ("search", "find", "look"), ("delete", "remove", "trash", "erase"), ("copy", "duplicate"),
	("font", "fonts", "typeface", "format", "formatting"), ("picture", "image", "photo", "photos", "pictures", "images"),
	("new", "create", "compose", "write"), ("reply", "answer", "respond"), ("share", "sharing", "invite"), ("sign", "log", "login", "signin"),
	("close", "exit", "quit"), ("help", "support"), ("edit", "change", "modify", "rename"), ("pdf", "export"), ("more", "menu", "tools"),
	("zoom", "magnify", "size"), ("account", "profile"), ("upload", "attach"), ("next", "continue", "forward"), ("back", "previous"))
_GROUPS = {}
for _group in _ALIKE:
	for _word in _group:
		_GROUPS.setdefault(_word, set()).update(_group)
# Things that open more of a program when nothing in sight is about what is wanted.
_OPENERS = re.compile(r"^(more|more options|more actions|menu|main menu|tools|options|settings|file|edit|insert|view|format|\.\.\.|…)$", re.IGNORECASE)
# Things whose press cannot be taken back: the question says so.
_FINAL = re.compile(
	r"\b(delete|remove|erase|discard|send|submit|pay|buy|purchase|order|confirm|sign out|log out|format|reset|uninstall|"
	r"unsubscribe|close account|empty)\b", re.IGNORECASE)
# Kinds of thing that can be pressed, by NVDA's own names for them, and what each is called.
KINDS = {
	"BUTTON": "button", "MENUITEM": "menu item", "MENUBUTTON": "menu button", "TAB": "tab", "LINK": "link", "CHECKBOX": "check box",
	"RADIOBUTTON": "radio button", "COMBOBOX": "combo box", "TOGGLEBUTTON": "toggle button", "SPLITBUTTON": "split button",
	"DROPDOWNBUTTON": "drop-down button", "TREEVIEWITEM": "tree item", "LISTITEM": "list item", "CHECKMENUITEM": "menu item",
	"RADIOMENUITEM": "menu item", "MENU": "menu", "SWITCH": "switch", "ICON": "icon", "EDITABLETEXT": "edit field"}
NAME_CHARS = 70
LIST_SHOWN = 8


def _clean(text):
	return " ".join(str(text or "").split())


def asks(part):
	"""Whether the user's own words say that they are stuck or want to be led through something, and name what:
	"walk me through this page" names nothing to do, and is a request to explore the page."""
	return bool(_ASKS.search(_clean(part))) and bool(_stems(goalOf(part)))


def goalOf(part):
	"""What the user wants done, in their own words, without the words that say they are stuck: "I'm stuck, I want
	to attach a file to this email" gives "attach a file to this email"."""
	text = re.sub(r"\(this follows:.*?\)\s*$", "", _clean(part))
	rest = _STUCK.sub(" ", text)
	rest = re.sub(r"^[\s,.:;!?-]+|[\s,.:;!?-]+$", "", " ".join(rest.split()))
	rest = re.sub(r"\s+([,.;:!?])", r"\1", rest)
	return rest


def _stems(text):
	"""The telling words of a text, each without its ending."""
	found = []
	for word in re.findall(r"[a-z0-9]+", str(text or "").lower()):
		if word in _SMALL or len(word) < 2:
			continue
		for ending in ("ing", "es", "ed", "s"):
			if word.endswith(ending) and len(word) - len(ending) >= 3:
				word = word[:-len(ending)]
				break
		found.append(word)
	return found


def _alike(word):
	"""A word with the words that mean the same in menus, as stems."""
	group = set(_GROUPS.get(word, ()))
	for other in list(_GROUPS):
		if _stems(other)[:1] == [word]:
			group |= _GROUPS[other]
	return {stem for other in group | {word} for stem in (_stems(other) or [other])}


class Thing:
	"""One thing of a window that can be used: its name, its kind in words, what presses it, its key where the
	program gives it one, and whether it can be used now."""

	def __init__(self, name, kind="", ref=None, key="", usable=True):
		self.name, self.kind, self.ref, self.key, self.usable = _clean(name)[:NAME_CHARS], kind, ref, _clean(key), usable

	def said(self):
		"""The thing as it is said: the Attach File button."""
		kind = self.kind if self.kind and self.kind.lower() not in self.name.lower() else ""
		return f"{self.name} {kind}".strip()


def score(goal, name):
	"""How much a thing's name is about what the user wants: the share of the goal's telling words that the name
	has, itself or as a word that means the same, with a little more for a name that is all about it."""
	wanted, has = _stems(goal), set(_stems(name))
	if not wanted or not has:
		return 0.0
	own = sum(1 for word in wanted if word in has)
	near = sum(1 for word in wanted if word not in has and _alike(word) & has)
	if not own and not near:
		return 0.0
	about = (own + 0.6 * near) / len(wanted)
	focus = (own + near) / len(has)
	return round(about * 0.75 + focus * 0.25, 3)


def rank(goal, things, done=(), fresh=()):
	"""The things that are about what the user wants, the best first, at most MAX_OFFERED: (score, thing).
	done: names that were pressed already, which are not offered again. fresh: names that were not there before the
	last step; they count a little more, because they are what the step brought up. Where nothing is about it, the
	things that open more of the program are offered: a menu, More, Tools."""
	done = {name.lower() for name in done}
	fresh = {name.lower() for name in fresh}
	scored, seen = [], set()
	for thing in things:
		low = thing.name.lower()
		if not thing.name or not thing.usable or low in done or low in seen:
			continue
		seen.add(low)
		points = score(goal, thing.name)
		if points > 0:
			scored.append((points + (0.08 if low in fresh else 0.0), thing))
	if not scored:
		scored = [(0.05, thing) for thing in things if thing.usable and thing.name.lower() not in done and _OPENERS.match(thing.name)]
	scored.sort(key=lambda found: -found[0])
	return scored[:MAX_OFFERED]


def sure(ranked):
	"""The thing plain code is sure of: one that is clearly about what is wanted, and well ahead of the next. None
	where a model, or the user, must choose."""
	if not ranked or ranked[0][0] < 0.5:
		return None
	if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.15:
		return None
	return ranked[0][1]


def isFinal(name):
	"""Whether pressing a thing with this name may do something that cannot be taken back."""
	return bool(_FINAL.search(name or ""))


def stepQuestion(number, thing, goal):
	text = f"Step {number}: {thing.said()} looks like the way to {goal}."
	if thing.key:
		text += f" Its key is {thing.key}."
	if isFinal(thing.name):
		text += " Pressing it may not be possible to take back."
	return text + " Press it for you?"


def tellText(thing):
	"""How the user gets to a thing themselves."""
	if thing.key:
		return f"{thing.said()}: its key is {thing.key}."
	return (
		f"{thing.said()} has no key of its own that the program tells NVDA. Move to it with Tab, or ask VisionClaw to "
		f"click {thing.name}.")


def changed(before, after, titleBefore, titleAfter):
	"""What a step brought up, in a sentence: another window, and the things that were not there before; and the
	names of those things."""
	old = {thing.name.lower() for thing in before}
	new = [thing for thing in after if thing.name and thing.name.lower() not in old]
	parts = []
	if _clean(titleAfter) and _clean(titleAfter) != _clean(titleBefore):
		parts.append(f"The window in front is now {_clean(titleAfter)[:80]}.")
	if new:
		names = ", ".join(thing.said() for thing in new[:LIST_SHOWN])
		more = f", and {len(new) - LIST_SHOWN} more" if len(new) > LIST_SHOWN else ""
		parts.append(f"New here: {names}{more}.")
	if not parts:
		parts.append("Nothing new showed that VisionClaw can find.")
	return " ".join(parts), [thing.name for thing in new]


def hereText(things, title):
	"""What is in front, for when nothing is about what the user wants."""
	named = [thing.said() for thing in things if thing.name and thing.usable][:LIST_SHOWN]
	where = f"The window in front is {_clean(title)[:80]}. " if _clean(title) else ""
	if not named:
		return where + "VisionClaw finds nothing in it that can be pressed."
	return where + "What can be used here: " + ", ".join(named) + ("." if len(named) < LIST_SHOWN else ", and more.")


NOT_OWN = (
	"One of VisionClaw's own windows is in front. VisionClaw does not work its own windows: their controls are "
	"yours. Switch to the program you want help with and ask again.")
# The tools that work the window in front: none of them is used on VisionClaw's own windows.
OFF_LIMITS = frozenset((
	"click_item", "press_keys", "type_text", "drag_item", "scroll_view", "draw_gesture", "timed_click", "touch_gesture",
	"pen_stroke", "set_control", "pick_date", "work_control", "fill_field", "work_through", "name_control"))
NO_GOAL = "Say what you want to get done, in your own words, and VisionClaw works through it with you."


def walk(goal, look, press, choose, ask, check=None, pause=None, steps=MAX_STEPS, checkAfter=CHECK_AFTER):
	"""Work through a task. look() gives (the things in front, the window's title, the program's name);
	press(thing) presses one; choose(goal, things) is a model's choice among a few things, as an index, or None
	for none of them; ask(question, choices) is the user's choice, as an index, or None. Returns the sentences
	that say what was done and where things stand, and the names of what was pressed."""
	check = check or (lambda: None)
	pause = pause or (lambda: None)
	things, title, program = look()
	said, pressed, fresh, quiet = [], [], [], 0
	for number in range(1, steps + 1):
		check()
		ranked = rank(goal, things, pressed, fresh)
		if not ranked:
			said.append(f"VisionClaw finds nothing here that is about this: {goal}. " + hereText(things, title))
			break
		candidates = [thing for _points, thing in ranked]
		thing = sure(ranked)
		if thing is None:
			index = choose(goal, candidates) if len(candidates) > 1 or ranked[0][0] < 0.5 else 0
			if index is None or not 0 <= index < len(candidates):
				said.append(
					f"Nothing here is clearly the way to {goal}. The nearest things are: "
					+ ", ".join(one.said() for one in candidates[:LIST_SHOWN]) + ".")
				break
			thing = candidates[index]
		answer = ask(stepQuestion(number, thing, goal), list(CHOICES))
		if answer == TELL:
			said.append(f"The next step is {tellText(thing)}")
			break
		if answer != YES:
			said.append(f"Stopped before step {number}, which would have been {thing.said()}.")
			break
		press(thing)
		pressed.append(thing.name)
		pause()
		check()
		after, titleAfter, programAfter = look()
		what, fresh = changed(things, after, title, titleAfter)
		said.append(f"Step {number}: pressed {thing.said()}. {what}")
		if _clean(programAfter).lower() != _clean(program).lower():
			# It stays in one program: what comes next is in another one, and that is the user's to decide.
			said.append(
				f"Another program is in front now, {programAfter or 'not known'}. VisionClaw works through a task in one "
				"program and stops here. Ask again there to go on.")
			break
		quiet = quiet + 1 if not fresh and _clean(titleAfter) == _clean(title) else 0
		things, title = after, titleAfter
		if quiet >= 2:
			said.append("The last two steps brought up nothing new, so VisionClaw stopped. " + hereText(things, title))
			break
		if number == steps:
			said.append(f"That was {steps} steps, the most VisionClaw takes in one go. " + hereText(things, title))
			break
		if number % checkAfter == 0:
			# A check-in on a longer task: go on only if the user says so.
			if ask(f"That was {number} steps towards this: {goal}. Go on?", list(GO_ON)) != 0:
				said.append("Stopped there, as you said. " + hereText(things, title))
				break
	return " ".join(said), pressed
