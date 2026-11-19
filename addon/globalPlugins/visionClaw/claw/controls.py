# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - setting a named control of the program in front: "turn on my NVIDIA GPU for this program", "turn
# the equalizer down", "turn the volume up a bit", "set the brightness to 70 percent". Which control is meant and
# what is to be done with it are read from the user's own words by plain code; the control is then looked for by
# its name in what NVDA knows of the window, on the other pages of a dialog, and in the window's picture
# (controltools.py). A model writes nothing here. No NVDA dependencies.

import re

from . import computer

ON, OFF, UP, DOWN, SET = "on", "off", "up", "down", "set"
# How many steps "up" or "down" is, by the words that say how much.
STEPS, FEW, MANY, TO_END = 2, 1, 5, 99
_PLACE_LEAD = re.compile(
	r"^\s*(?:in|on|inside|within|at|under|from) (?:this|the|that|my|its) [\w' -]{1,50}?,\s*", re.IGNORECASE)
_OFF = re.compile(
	r"\b(turn|switch|toggle)\b.{0,70}\boff\b|\b(disable|uncheck|untick|deselect|deactivate|clear the check)\w*\b", re.IGNORECASE)
_ON = re.compile(
	r"\b(turn|switch|toggle)\b.{0,70}\bon\b(?! (my|the|this|your) )|\b(turn|switch) on\b|\b(enable|tick|activate)\w*\b"
	r"|\bcheck (the |my )?(box|check ?box|option)\b|\bcheck\b.{0,40}\b(box|check ?box)\b", re.IGNORECASE)
_UP = re.compile(r"\b(up|higher|louder|brighter|faster|more|increase|raise|boost)\b", re.IGNORECASE)
_DOWN = re.compile(r"\b(down|lower|quieter|dimmer|darker|slower|less|decrease|reduce|drop)\b", re.IGNORECASE)
_TO = re.compile(r"\b(?:to|at)\s+(\d{1,4})\s*(percent|%)?", re.IGNORECASE)
_FEW = re.compile(r"\b(a bit|a little|a little bit|slightly|a touch|a tad|a notch|one step|a step)\b", re.IGNORECASE)
_MANY = re.compile(r"\b(a lot|much|way|far|lots|a great deal|several steps)\b", re.IGNORECASE)
_END = re.compile(r"\b(all the way|fully|completely|as far as it goes|maximum|minimum|to the (top|bottom|max|min|end))\b", re.IGNORECASE)
# Words that say what to do or where, and are no part of a control's name.
_NOT_NAME = frozenset((
	"turn", "switch", "toggle", "set", "adjust", "change", "make", "put", "move", "slide", "bring", "push", "pull", "drag",
	"on", "off", "up", "down", "higher", "lower", "louder", "quieter", "brighter", "dimmer", "darker", "faster", "slower",
	"more", "less", "increase", "decrease", "raise", "reduce", "boost", "drop", "enable", "disable", "check", "uncheck", "tick",
	"untick", "activate", "deactivate", "select", "deselect", "the", "my", "a", "an", "it", "its", "this", "that", "for", "in",
	"of", "to", "at", "and", "then", "please", "bit", "little", "slightly", "lot", "much", "way", "far", "all", "fully",
	"completely", "percent", "option", "setting", "settings", "checkbox", "box", "slider", "control", "value", "level",
	"program", "app", "application", "game", "window", "dialog", "here", "by", "with", "so", "that", "is", "be", "should",
	"multipage", "multi", "page", "inaccessible", "first", "now", "just", "also", "can", "you", "could", "would", "want", "i",
	"me", "use", "using", "maximum", "minimum", "top", "bottom", "end", "goes", "as", "notch", "step", "steps", "touch", "tad",
	# The kind of control, and that it is only drawn, are no part of what it is called.
	"knob", "dial", "fader", "rotary", "graphical", "drawn", "visual"))
# Words that say the program in front is meant, not NVDA or Windows.
_IN_APP = re.compile(
	r"\b(in|for|of|on|inside) (this|the current|that) (app|application|program|game|window|dialog|page|panel|tab|settings|"
	r"multi-?page dialog|[\w-]+ dialog)\b|\bthis (app|program|game)'?s\b|\b(in|inside) here\b|\bin (its|the) settings\b", re.IGNORECASE)
# Words in a control's own label that say nothing about which control it is.
_PLAIN_LABEL = frozenset((
	"enable", "enabled", "use", "allow", "show", "turn", "on", "off", "the", "a", "an", "of", "for", "to", "and", "in", "with",
	"my", "your", "this", "when", "is", "are", "be", "option", "setting", "mode"))
CHECKED_STATES = ("CHECKED", "PRESSED", "ON")
CHECKABLE = ("CHECKBOX", "TOGGLEBUTTON", "SWITCH", "RADIOBUTTON", "CHECKMENUITEM", "RADIOMENUITEM")
TURNED = ("SLIDER", "SPINBUTTON", "SCROLLBAR", "DIAL")
PAGES = ("TAB",)
MAX_PAGES = 12


def _words(text):
	return re.findall(r"[a-z0-9]+", str(text or "").lower())


def inApp(part):
	"""Whether the user's own words say that something of the program in front is meant."""
	return bool(_IN_APP.search(computer.own(part)))


def wish(part):
	"""What the user's own words ask of a named control, or None when they name none or say nothing to do:
	{"what": ON, OFF, UP, DOWN or SET; "name": the words that name the control; "names": the separate controls
	those words may stand for where they join several with "and" ("UI narration and subtitles"), else the one
	name; "steps": how many steps up or down (TO_END for all the way); "value": the number for SET; "percent":
	whether the number is a share}."""
	text = _PLACE_LEAD.sub("", computer.own(part))
	low = text.lower()
	if re.search(r"\bhow (do|can|would|should|could) (i|we|you|one)\b|\bhow to\b", low):
		return None
	number = _TO.search(low)
	off, on = bool(_OFF.search(low)), bool(_ON.search(low))
	up, down = bool(_UP.search(low)), bool(_DOWN.search(low))
	if number:
		what = SET
	elif off != on:
		what = OFF if off else ON
	elif up != down:
		what = UP if up else DOWN
	else:
		return None
	steps = TO_END if _END.search(low) else FEW if _FEW.search(low) else MANY if _MANY.search(low) else STEPS
	rest = _TO.sub(" ", low)
	rest = re.sub(r"\b(for|in|of|on|inside) (this|the current|that|my) (app|application|program|game|window|dialog|page|panel|tab)\b", " ", rest)
	rest = re.sub(r"\bon (my|the|this) (keyboard|computer|pc|laptop|screen)\b", " ", rest)
	name = " ".join(word for word in _words(rest) if word not in _NOT_NAME)
	if not name:
		return None
	# The whole name is tried first by the tool: a control may really be called "Narration and subtitles".
	names = [" ".join(word for word in _words(chunk) if word not in _NOT_NAME) for chunk in re.split(r"\s+(?:and|plus)\s+|\s*[,&]\s*", rest)]
	names = [one for one in names if one]
	return {"what": what, "name": name, "names": names if len(names) > 1 else [name], "steps": steps,
		"value": int(number.group(1)) if number else None, "percent": bool(number and number.group(2))}


def pick(name, labels, prefer=()):
	"""Which of a window's controls a name means: the indexes of the best, several when they fit equally.
	labels: each control's own name. prefer: indexes of the kinds the wish is for (a check box for on and off, a
	slider for up and down); among equals they win. A control fits when the user's words are its name, when
	every word the user said is in its name, or when most of what its name tells is in the user's words."""
	wanted = _words(name)
	if not wanted:
		return []
	asked = set(wanted)
	scored = []
	for index, label in enumerate(labels):
		words = _words(label)
		if not words:
			continue
		telling = [word for word in words if word not in _PLAIN_LABEL] or words
		shared = asked & set(words)
		if not shared:
			continue
		if words == wanted or telling == wanted:
			score = 4
		elif asked <= set(words):
			score = 3
		elif len(shared & set(telling)) / len(set(telling)) >= 0.6 and len(shared) / len(asked) >= 0.5:
			score = 2
		else:
			continue
		scored.append((-score, 0 if index in prefer else 1, len(words), index))
	if not scored:
		return []
	scored.sort()
	best = scored[0][:2]
	return [index for score, preferred, _length, index in scored if (score, preferred) == best]


def checked(states):
	"""Whether a control that is on or off is on, from the states NVDA gives; None where they do not say."""
	states = set(states or ())
	if "HALFCHECKED" in states:
		return None
	return bool(states & set(CHECKED_STATES))


def onOff(value):
	return "on" if value else "off"


def stepsText(steps):
	return "all the way" if steps >= TO_END else computer.many(steps, "step")
