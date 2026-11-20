# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - where the user is when a request ends, checked by plain code and said in words. The owner said on
# 2026-11-19: "The user can't just be thrown randomly into a dialog box or left in the middle of nowhere on a website
# either in browse mode or focus mode or in any app or game ... or just left helpless in some inaccessible window", and
# "consider what a sighted person would see and do ... then adapt that to a screen reader user". A sighted person sees
# at once where a job left them: which window came up, what its message says, which button is the default, whether a
# page is being read or typed in. So, at the start and at the end of every request the add-on reads where the user is
# (gototools.spot), and plain code compares the two:
#   - Where the focus moved, the user is told where it is now: the program, the window, the control, browse mode or
#     focus mode, and for a dialog that came up its message and its default button.
#   - Where it moved during a request that only looked, that is said too, with the way back: a look must not move the
#     user, and when it did, the user hears it rather than finding out later.
#   - Where the place tells NVDA almost nothing (no focus, a pane without a name in a window of few named controls),
#     the user is told the ways VisionClaw has to read and work it, and the way back.
# What each skill expects is its "lands:" line (claw/skills.py): stay (the job only looks), moved (said when the focus
# moved, the default), told (always said: the job leaves the user where they go on working). No NVDA dependencies.

STAY, MOVED, TOLD = "stay", "moved", "told"
LANDS = (STAY, MOVED, TOLD)
# Tools whose own result already says where the user is: nothing is said twice.
TELLS_ITSELF = frozenset(("go_to_control", "about_focus", "focus_info", "go_to_item", "form_trouble", "work_through", "step_through"))
# Kinds of focus that say nothing about where the user is when they have no name.
_NOWHERE = frozenset(("", "UNKNOWN", "PANE", "WINDOW", "CLIENT", "GROUPING", "PANEL", "FILLER", "LAYEREDPANE", "ROOTPANE",
	"SCROLLPANE", "INTERNALFRAME", "APPLICATION", "FRAME", "CANVAS"))
# A window with fewer controls NVDA can name than this tells NVDA almost nothing (gototools.FEW_NAMED).
FEW_NAMED = 3
# The overlay's key, the key of NVDA that says where the focus is, and the key back to the window before. Keys of
# VisionClaw, NVDA and Windows said as they are.
OVERLAY_KEY = "NVDA+Alt+O"
FOCUS_KEY = "NVDA+Tab"
BACK_KEY = "Alt+Tab"


def _place(facts):
	return (facts.get("app") or "", facts.get("title") or "")


def moved(before, after):
	"""Whether the user is somewhere else at the end: another program or window, another control, or another mode of a
	web page. Unknown facts move nothing."""
	if not before or not after:
		return False
	if _place(before) != _place(after):
		return True
	if (before.get("focusRole"), before.get("focusName")) != (after.get("focusRole"), after.get("focusName")):
		return True
	return before.get("browse") != after.get("browse")


def otherWindow(before, after):
	return bool(before and after and _place(before) != _place(after))


def nowhere(facts):
	"""Whether the focus is on nothing that says where the user is: a pane, a window or nothing at all, without a name of
	its own (the window's title, which a game's window often gives its only object, is no name of its own)."""
	role, name = facts.get("focusRole") or "", facts.get("focusName") or ""
	return role in _NOWHERE and (not name or name == (facts.get("title") or ""))


def lost(facts):
	"""Whether the place tells NVDA almost nothing: "unreadable" for no focus NVDA can name in a window with few named
	controls, "nowhere" for no focus NVDA can name in a window that has more; "" when the user is somewhere NVDA can say."""
	if not facts or facts.get("own"):
		return ""
	if nowhere(facts):
		named = facts.get("named")
		if named is not None and named < FEW_NAMED:
			return "unreadable"
		return "nowhere"
	return ""


def placeText(facts):
	"""Where the user is, in one sentence: the control, the window and the program, and the mode of a web page."""
	role = facts.get("focusRoleText") or ""
	name = facts.get("focusName") or ""
	what = f"the {role} \"{name}\"" if role and name else f"\"{name}\"" if name else f"a {role} with no name" if role else (
		"no control NVDA can name")
	where = []
	if facts.get("title"):
		where.append(f"in the window \"{facts['title']}\"")
	if facts.get("app"):
		where.append(f"of {facts['app']}")
	text = f"You are on {what}" + (" " + " ".join(where) if where else "")
	if facts.get("browse") is True:
		text += ", in browse mode"
	elif facts.get("browse") is False:
		text += ", in focus mode"
	value = facts.get("focusValue") or ""
	if value and value != name:
		text += f"; it shows {value}"
	return text + "."


def dialogText(before, after):
	"""What a sighted person sees at once when a dialog comes up: its message and its default button."""
	if after.get("windowRole") != "DIALOG" or not otherWindow(before, after):
		return ""
	parts = []
	if after.get("message"):
		parts.append(f"It says: {after['message']}")
	if after.get("defaultButton"):
		parts.append(f"Its default button, which Enter presses, is {after['defaultButton']}.")
	if not parts:
		return ""
	return "A dialog came up. " + " ".join(part if part.endswith(".") else part + "." for part in parts)


def wayBack(before):
	if not before or not before.get("title"):
		return ""
	return f"{BACK_KEY} goes back to \"{before['title']}\"."


def lostText(kind, before):
	"""The ways VisionClaw has to read and work a place that tells NVDA almost nothing, and the way back."""
	if kind == "unreadable":
		text = (f"This window tells NVDA almost nothing. Press {OVERLAY_KEY} for VisionClaw's overlay, which reads it from "
			"its picture so the arrow keys and Enter work it, or ask VisionClaw to put you on the most useful item here.")
	else:
		text = (f"The focus is on nothing NVDA can name. Press Tab to move to a control, {FOCUS_KEY} to hear where the "
			"focus is, or ask VisionClaw to put you on the most useful control here.")
	back = wayBack(before)
	return f"{text} {back}".strip()


def expected(lands, looksOnly):
	"""What the request expects of where the user ends: TOLD where a skill says so, STAY where every step only looked
	(and no skill says otherwise), else MOVED."""
	lands = set(lands or ())
	if TOLD in lands:
		return TOLD
	if looksOnly:
		return STAY
	return MOVED


def sentence(before, after, expect=MOVED, toldAlready=False):
	"""What the user is told at the end of a request about where they are, or "". before and after: the facts at the
	start and at the end. expect: STAY, MOVED or TOLD. toldAlready: a step's own result said where the user is."""
	if not after or after.get("own"):
		return ""
	if before and before.get("own"):
		# VisionClaw's own window was still in front when the request began: where the user was is not known.
		before = None
	gone = moved(before, after)
	kind = lost(after)
	if toldAlready and not kind:
		return ""
	if not gone and not kind and expect != TOLD:
		return ""
	lines = []
	if gone and expect == STAY:
		lines.append("While VisionClaw looked, the focus moved.")
	lines.append(placeText(after))
	if gone:
		said = dialogText(before, after)
		if said:
			lines.append(said)
	if kind:
		lines.append(lostText(kind, before if otherWindow(before, after) else None))
	elif gone and expect == STAY and otherWindow(before, after):
		back = wayBack(before)
		if back:
			lines.append(back)
	return " ".join(lines)
