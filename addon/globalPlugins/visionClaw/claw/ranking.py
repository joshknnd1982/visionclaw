# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - which of many things a request is about: NVDA's commands, or the functions and classes inside
# NVDA. Counting shared words alone is not enough. Asked for "the current time", a dozen commands share the
# word "current" and one is about the time; the word that few of them have is the one that tells. So a word
# counts for more the fewer things have it, and for more again when it is in a thing's own name. What is found
# is cut off where it stops being close to the best, so that a small model is shown a few good candidates and
# not six that merely share a word. No NVDA dependencies.

import math

# A word in a thing's own name counts this much more than a word in its description.
NAME_WEIGHT = 1.5
# What is kept must score at least this share of the best.
SHARE = 0.6


# A word that only asks ("say", "report") counts this much of a word that names what is asked for.
LIGHT_WEIGHT = 0.4


def rank(asked, entries, limit=6, share=SHARE, light=()):
	"""asked: the telling words of the request, as a set.
	entries: one (words of its name, words of its description) pair of sets for each thing.
	light: words of the request that only ask. They count for less, and where the request also names
	something, a thing must share a word that names.
	Returns the indexes of the things the request is about, best first; empty when nothing shares a word."""
	asked = set(asked)
	light = set(light) & asked
	naming = asked - light
	if not asked or not entries:
		return []
	have = {}
	for named, other in entries:
		for word in asked & (set(named) | set(other)):
			have[word] = have.get(word, 0) + 1
	total = len(entries)
	weight = {
		word: math.log(1 + total / count) * (LIGHT_WEIGHT if word in light else 1.0) for word, count in have.items()}
	scored = []
	for index, (named, other) in enumerate(entries):
		named, other = set(named), set(other)
		inName = asked & named
		inRest = (asked & other) - inName
		if not inName and not inRest:
			continue
		if naming and not naming & (inName | inRest):
			continue
		score = sum(weight[word] * NAME_WEIGHT for word in inName) + sum(weight[word] for word in inRest)
		# Among equals, the thing that is about less is more likely the thing that was meant.
		scored.append((-score, len(named | other), index))
	if not scored:
		return []
	scored.sort()
	best = -scored[0][0]
	return [index for score, _size, index in scored if -score >= best * share][:limit]
