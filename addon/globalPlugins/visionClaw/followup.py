# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - follow-up questions in the description window.
# VisionMate only answered questions that could be answered from the picture alone, and replied "I can only
# answer questions about this image" to the rest. A small model that is asked "is this question about the
# image?" says no far too often: asked about the highlighted item on the desktop, or what an icon is for, it
# refused. A blind person asks exactly such questions, because what a sighted person takes in at a glance has
# to be asked for: what is selected, where something is, what a thing is for, what to do next. So nothing is
# refused any more. Every question goes to the vision model with the picture, the model may use what it knows
# to explain what is shown, and the one rule left is honesty: what the picture does not show is said to be
# not shown, never guessed.
#
# What to do next is often a key, and a model that only sees a picture makes one up: asked how to read the
# title of the window, Qwen3.5 9B answered "press Alt and then S" (tests/live_followup.py, 2026-11-18). The
# owner asked on 2026-11-18 that what VisionClaw has to look things up in also serve the features that came
# from VisionMate. So a question that asks how something is done, or which key does it, is given the one
# command of NVDA that it is about, with its key, found by plain code among the commands that work where the
# user is (known).
#
# It is kept this narrow because of what was measured the same day. Lines from the user guide and from the
# developer guides were tried too: a line that was not about the question was repeated by the model as the
# answer, with its key, and a passage of the developer guides made it invent a key where before it had said,
# rightly, that the picture does not show this. A command that has a key and that has nearly every word the
# question names was right every time. A question about what the picture shows is given nothing, and is
# asked exactly as before. No NVDA dependencies.

import re

from .claw import lookup

ANSWER = (
	"\n\nAnswer this for a blind person, who cannot see the picture. Look at the picture again for the answer. "
	"You may use what you know to explain what is shown: what a thing is, what it is for, what a word, symbol "
	"or colour means, which item is highlighted or selected, where something is, and what could be done next. "
	"Read out any text that matters, exactly as it is written. If the picture does not show what is asked, say "
	"that it is not in the picture, and then say what you can about it from what you know, saying that this is "
	"not from the picture. Never make up something as if it were shown. Answer in 1 to 4 short sentences."
)
MAX_TOKENS = 260
# What begins the command found on this computer, in the question the model is sent.
KNOWN_HEAD = (
	"NVDA has this command, which is not from the picture. If it answers the question, give its key exactly as "
	"it is written here. If it does not, say that you are not sure of the key; never make one up:"
)
KNOWN_CHARS = 300
# How much of what the question names a command must have, by the weight of the words: the rare word, which
# says what is meant, counts for most. "The next heading" is not answered by a command that moves to the next
# of something else.
KNOWN_COVER = 0.7
# A question that asks how something is done, or which key does it. What the picture shows is not asked so.
_HOW = re.compile(
	r"\bhow (do|can|would|should|could|to)\b|\b(what|which) (key|keys|shortcut|shortcuts|command|commands)\b"
	r"|\bis there (a|an) (key|shortcut|command)\b|\bwith the keyboard\b|\bwhat do i press\b", re.IGNORECASE)


def asksHow(question):
	"""Whether a question about a described picture asks how something is done with the keyboard: only such a
	question is looked up. A question about writing add-ons is not: it is VisionClaw's to answer, from the
	developer guides, when it is asked in the Ask VisionClaw window."""
	return bool(_HOW.search(question or "")) and not lookup.isDeveloper(question)


def known(question, passages, chars=KNOWN_CHARS, cover=KNOWN_COVER):
	"""The line to add to a question about a described picture: the one command of NVDA the question is about,
	with its key; "" when the question is about the picture itself or no command fits. passages: NVDA's
	commands where the user is, as asktools.commandPassages gives them. A command fits when it has a key, when
	it is the best found for the question's words, when the question says a word of the command's own name,
	and when it has at least two of the words that name something and all of them but one at most: so "the
	title of this window" finds the command that reports the title, and "which control has the focus" finds
	none rather than the command that switches to focus mode."""
	if not asksHow(question) or not passages:
		return ""
	said, light = lookup.asked(question)
	naming = said - light
	if len(naming) < 2:
		# "How do I get to that button" names one thing, and half of NVDA's commands have that word.
		return ""
	keyed = [passage for passage in passages if passage.command and "no key assigned" not in passage.text]
	for passage in lookup.about(question, keyed, limit=1, cover=cover):
		named, other = passage.words()
		shared = naming & (named | other)
		# A word of the command's own name must be in the question: a command that only happens to say the
		# same words in its description is about something else.
		if naming & named and len(shared) >= 2 and len(naming - shared) <= 1:
			return "\n\n" + KNOWN_HEAD + "\n- " + _once(passage, chars)
	return ""


def _once(passage, chars):
	"""A command as one line: what it does when its key is pressed once, and its key. What a second or third
	press does is left out: given all of it, the model said "press NVDA+T twice" for reading the title, which
	spells it."""
	what, found, keys = passage.text.rpartition(" Keys: ")
	if not found:
		return passage.line(chars)
	first = lookup._SENTENCE.split(what)[0].rstrip(";")
	return f"From {passage.origin}: {lookup.shorten(first, chars)} Keys: {keys}"
