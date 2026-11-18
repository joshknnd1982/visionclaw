# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - letting the user know what VisionClaw can download for them. The owner said on 2026-11-18, of
# the guides and the training material that do not come with the add-on: "visionclaw must provide a way for
# the user to know that these are downloadable on request. otherwise the user may never know what help and
# guides visionclaw can get for the user".
#
# Three ways, all of them plain code and none of them a model's words:
#   the overview: asked for in words ("what can you download for me") or with a button in the settings, it
#     names everything that can be downloaded, whether it is here already, and the words that get it;
#   one sentence after an answer, where it fits: after a request about writing an add-on, that the guide for
#     that can be downloaded; after a request to learn or be taught, that lessons can be; after the first
#     question of any kind, that there is an overview to ask for;
#   and each of these sentences is said once and then never again (kept in a small file), so that being
#     told does not turn into being nagged. Nothing is ever downloaded because of a sentence: the user asks,
#     and is asked first.
# No NVDA dependencies.

import datetime
import json
import os
import re

from . import lookup, training

GUIDES, TRAINING, OVERVIEW = "guides", "training", "overview"
# The words that get each thing, as the user can say them.
ASK_OVERVIEW = "what can you download for me"
ASK_GUIDES = "get the latest NVDA developer guides"
ASK_TRAINING = "get the free NVDA training material"
# Requests that are about downloading or about what is here already: nothing is offered after them.
ABOUT_DOWNLOADS = frozenset((
	"downloads_info", "update_guides", "guides_info", "remove_guides", "update_training", "training_info", "remove_training",
	"learn_app", "update_visionclaw"))
WRITES_ADDONS = frozenset(("write_addon", "fix_addon"))
QUESTIONS = frozenset(("explain_keys", "nvda_question", "addon_question", "coach"))
_OTHER_READER = re.compile(r"\b(jaws|window[- ]?eyes)\b", re.IGNORECASE)
SENTENCES = {
	GUIDES: (
		"This is said once: VisionClaw can download the NVDA Add-on Development Guide, which helps it when it writes "
		f"add-ons and answers questions about them. To get it, say: {ASK_GUIDES}. It asks you first."),
	TRAINING: (
		"This is said once: VisionClaw can download free lessons that teach NVDA, from the NVDA wiki, the American "
		f"Foundation for the Blind and Hadley. To get them, say: {ASK_TRAINING}. It asks you first."),
	OVERVIEW: (
		"This is said once: VisionClaw can download more guides and lessons to help you with. To hear which, ask: "
		f"{ASK_OVERVIEW}."),
}


def overview(have):
	"""Everything VisionClaw can download for the user, whether it is here already, and the words that get it.
	have: {"devGuide": the NVDA Developer Guide is here, "addonGuide": the NVDA Add-on Development Guide is,
	"training": the training material is}. Said as it is."""
	if have.get("devGuide") and have.get("addonGuide"):
		guides = "Both are on this computer; asking again gets the latest."
	elif have.get("devGuide"):
		guides = "The NVDA Developer Guide is on this computer; the NVDA Add-on Development Guide is not yet."
	else:
		guides = "Neither is on this computer yet."
	lessons = "It is on this computer; asking again gets the latest." if have.get("training") else "It is not on this computer yet."
	return "\n".join((
		"VisionClaw can get these for you from the internet. Each is downloaded only when you ask for it, and it asks "
		"you first.",
		"The NVDA developer guides, which help when you ask about writing for NVDA and when VisionClaw writes an add-on "
		f"for you. {guides} Say: {ASK_GUIDES}.",
		"Free material that teaches NVDA: pages of the NVDA wiki for people who come from JAWS or Window-Eyes and about "
		"the ribbon of Office, more voices and NVDA's log, the lessons of the American Foundation for the Blind, and "
		f"Hadley's workshops. {lessons} Say: {ASK_TRAINING}.",
		"Notes about the program or game you are in, from Wikipedia and the program's own website. Say: learn about "
		"this program.",
		"A newer version of VisionClaw. Say: check for updates.",
		"Newer AI models: in the models window, the button Look for newer models.",
		"To hear what is on this computer already, say: which developer guides do I have, or: which training material "
		"do I have.",
	))


class Offers:
	"""Which of the sentences have been said, kept in a file so that each is said once."""

	def __init__(self, path):
		self._path = path
		self._said = None

	def said(self):
		if self._said is None:
			try:
				with open(self._path, encoding="utf-8") as f:
					found = json.load(f)
				self._said = dict(found) if isinstance(found, dict) else {}
			except (OSError, ValueError):
				self._said = {}
		return self._said

	def _mark(self, which, today=None):
		self.said()[which] = today or datetime.date.today().isoformat()
		try:
			os.makedirs(os.path.dirname(self._path), exist_ok=True)
			with open(self._path, "w", encoding="utf-8") as f:
				json.dump(self._said, f, indent=1)
		except OSError:
			pass  # then it may be said once more in another session, which does no harm

	def fitting(self, request, recipes, have):
		"""Which sentence fits a request that was just answered, or "": the one about the guide for add-ons
		after a request about writing one, the one about lessons after a request to learn or be taught or one
		that names another screen reader, the one about the overview after any other question. Only what is not
		here yet is offered, and nothing after a request that was itself about downloading."""
		recipes = set(recipes or ())
		if recipes & ABOUT_DOWNLOADS:
			return ""
		said = self.said()
		request = str(request or "")
		if GUIDES not in said and not have.get("addonGuide") and (recipes & WRITES_ADDONS or lookup.isDeveloper(request)):
			return GUIDES
		asksToLearn = training._LEARNING.search(request) or _OTHER_READER.search(request) or "coach" in recipes
		if TRAINING not in said and not have.get("training") and asksToLearn and recipes & QUESTIONS:
			return TRAINING
		if OVERVIEW not in said and recipes & QUESTIONS and not (have.get("addonGuide") and have.get("training")):
			return OVERVIEW
		return ""

	def next(self, request, recipes, have, today=None):
		"""The one sentence to say after an answer, or "". It is said once: saying it is remembered. Never
		raises, because this only helps."""
		try:
			which = self.fitting(request, recipes, have)
			if not which:
				return ""
			self._mark(which, today)
			return SENTENCES[which]
		except Exception:
			return ""
