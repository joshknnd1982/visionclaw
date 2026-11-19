# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - words that mean the same thing, so that what VisionClaw learned from a request in one wording is
# used for the same request in another. "Tell me all objects that are currently in the system tray" and "which
# icons are in my notification area" share almost no word, and ask the same. A small model may see that; counting
# words cannot. So each request is turned into its concepts first: every phrase of a group below becomes the
# group's name (@tray, @item, @tell), and what is left are its telling words without their endings
# (memory.wordList). Two requests are then compared by the concepts they share (planning.alike, Jaccard's index),
# and the planning notes and the next way to try are ranked by them (planning.bm25).
# Asked for by the owner on 2026-11-18: "Visionclaw must learn to generalize either through a skill, system
# prompt, memory, new python code, some sort of advanced math formulas, or a combination of all of those."
# Every group is about how a blind person works the computer with the keyboard, speech and braille, and names
# no colour, shape or other thing that only sight tells. A group only joins words that ask for the same thing; a
# word that can mean two things ("start" the program, "start" the menu) is joined only in a phrase that says
# which. No NVDA dependencies.

import re

from .memory import wordList

# (name, phrases). Longer phrases are found before shorter ones, so "start menu" is never "start" and "menu".
GROUPS = (
	# Places of Windows itself (claw/places.py).
	("@tray", ("system tray", "notification area", "systray", "tray icons", "hidden icons", "tray")),
	("@taskbar", ("taskbar", "task bar")),
	("@desktop", ("desktop",)),
	("@start", ("start menu", "start button", "start screen", "windows menu")),
	("@quicksettings", ("quick settings", "action center", "action centre")),
	("@notification", ("notification center", "notification centre", "notifications", "notification", "alerts", "toasts")),
	# What is in a place, or on the screen.
	("@item", ("objects", "object", "icons", "icon", "items", "item", "things", "thing", "entries", "entry", "elements",
		"element", "controls", "control", "shortcuts", "shortcut")),
	("@program", ("programs", "program", "applications", "application", "apps", "app", "software")),
	("@window", ("windows", "window", "dialog box", "dialog", "dialogue")),
	("@screen", ("screen", "monitor", "display")),
	("@page", ("web page", "webpage", "website", "web site", "page", "site")),
	("@file", ("files", "file", "documents", "document")),
	("@folder", ("folders", "folder", "directories", "directory")),
	("@button", ("buttons", "button")),
	("@link", ("links", "link")),
	("@field", ("fields", "field", "edit box", "text box", "box")),
	# What is wanted.
	("@tell", ("tell me", "tell", "list", "name", "say", "read out", "read", "enumerate", "report", "announce",
		"give me a list", "what are", "what is", "what's", "whats", "what", "which")),
	("@count", ("how many", "number of", "count")),
	("@open", ("open up", "open", "launch", "bring up", "pull up", "go to", "take me to")),
	("@close", ("close", "quit", "exit", "dismiss")),
	("@click", ("double click", "double-click", "right click", "right-click", "click", "activate", "tap")),
	("@describe", ("describe", "look at", "what do you see", "what does it look like")),
	("@faster", ("faster", "quicker", "speed up", "more quickly")),
	("@slower", ("slower", "slow down", "more slowly")),
	("@louder", ("louder", "turn up", "volume up", "raise the volume")),
	("@quieter", ("quieter", "softer", "turn down", "volume down", "lower the volume")),
	("@speech", ("speech", "voice", "speaking", "speak", "talking", "talk")),
	("@braille", ("braille display", "braille")),
	# Things the tray and Windows report.
	("@network", ("wi-fi", "wifi", "wireless", "internet", "network", "connection")),
	("@battery", ("battery", "charge", "charging")),
	("@volume", ("volume", "sound level", "loudness")),
	("@clock", ("clock", "time", "date")),
	("@current", ("currently", "right now", "at the moment", "now", "still", "all")),
)
_ORDER = sorted(((phrase, name) for name, phrases in GROUPS for phrase in phrases), key=lambda pair: -len(pair[0]))
_PATTERN = re.compile(r"\b(" + "|".join(re.escape(phrase) for phrase, _name in _ORDER) + r")\b", re.IGNORECASE)
_NAMES = {phrase: name for phrase, name in _ORDER}
# Concepts that say only how much or when: they make no two requests alike.
_EMPTY = frozenset(("@current",))


def tokens(text):
	"""A text as its concepts and its other telling words, in the order they come. Each phrase of a group becomes
	the group's name; the rest are telling words without their endings."""
	found = []
	at = 0
	low = " ".join(str(text or "").lower().replace("’", "'").split())
	for hit in _PATTERN.finditer(low):
		found += wordList(low[at:hit.start()])
		name = _NAMES[hit.group(1).lower()]
		if name not in _EMPTY:
			found.append(name)
		at = hit.end()
	found += wordList(low[at:])
	return found


def concepts(text):
	"""The concepts and other telling words of a text, as a set."""
	return set(tokens(text))


def text(words):
	"""Concepts and words put back into one text, for ranking by BM25 (planning.bm25 reads words of 3 letters or
	more, so a concept's @ is left out and its name kept)."""
	return " ".join(word.lstrip("@") + ("concept" if word.startswith("@") else "") for word in words)
