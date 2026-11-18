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

ANSWER = (
	"\n\nAnswer this for a blind person, who cannot see the picture. Look at the picture again for the answer. "
	"You may use what you know to explain what is shown: what a thing is, what it is for, what a word, symbol "
	"or colour means, which item is highlighted or selected, where something is, and what could be done next. "
	"Read out any text that matters, exactly as it is written. If the picture does not show what is asked, say "
	"that it is not in the picture, and then say what you can about it from what you know, saying that this is "
	"not from the picture. Never make up something as if it were shown. Answer in 1 to 4 short sentences."
)
MAX_TOKENS = 260
