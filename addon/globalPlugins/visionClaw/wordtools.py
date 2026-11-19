# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the user's own words as a tool: a word or phrase taught in words ("when I say shh, I mean stop
# talking"), listed, and forgotten (claw/understand.py). They are kept in the Markdown file understanding.md of
# VisionClaw's data folder, which the user can read and change, and from then on every request is understood with
# them, before VisionClaw decides what to do; the answer then begins "Understood as". Nothing is learned by a model
# and nothing goes online.

import addonHandler

from .claw import understand
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()


def register(plugin, add, text, confirm, mustAgree):
	"""The tool for the user's own words. add and text are the helpers of nvdatools.build."""
	grammar = plugin.understanding

	def listed():
		words = grammar.own()
		if not words:
			return (
				"You have not taught VisionClaw any words of your own yet. To teach one, say for example: when I say "
				"shh, I mean stop talking.")
		lines = "\n".join(f"{number}. \"{said}\" means \"{meant}\"" for number, (said, meant) in enumerate(words, 1))
		return (f"You have taught VisionClaw {len(words)} word{'s' if len(words) != 1 else ''} of your own:\n{lines}\n"
			"To forget one, say forget the word, and then the word.")

	def myWords(task, action, asked):
		wish = understand.wishOf(asked) or {"what": action if action in understand.ACTIONS else understand.TEACH}
		what = wish["what"]
		if what == understand.LIST:
			return listed()
		if what == understand.FORGET_ALL:
			words = grammar.own()
			if not words:
				return "There are no words of yours to forget."
			# Translators: Asked before VisionClaw forgets every word the user taught it. {count} is how many.
			mustAgree(_("Forget all {count} words you taught VisionClaw?").format(count=len(words)))
			gone = grammar.forget(None)
			return f"VisionClaw forgot all {len(gone)} words you taught it. Your words are understood as they are again."
		if what == understand.FORGET:
			said = wish.get("said", "")
			if not said:
				raise ToolError("The word to forget was not found in the request.")
			known = [s for s, _m in grammar.own() if s.lower() == understand.cleanSaid(said).lower()]
			if not known:
				taught = ", ".join(f"\"{s}\"" for s, _m in grammar.own())
				return f"No word \"{said}\" was taught to VisionClaw." + (f" The words taught are: {taught}." if taught else "")
			# Translators: Asked before VisionClaw forgets one word the user taught it.
			confirm(_("Forget the word \"{said}\"?").format(said=known[0]))
			gone = grammar.forget(said)
			return f"VisionClaw forgot the word \"{gone[0][0]}\". It no longer means \"{gone[0][1]}\"."
		said, meant = understand.cleanSaid(wish.get("said", "")), understand.cleanMeant(wish.get("meant", ""))
		if not said or not meant:
			raise ToolError("The word and what it means were not both found in the request.")
		problem = understand.refusal(said, meant)
		if problem:
			# Said to the user as it is: nothing in the form can change it.
			return problem + " Nothing was kept."
		# Translators: Asked before VisionClaw keeps a word the user teaches it. {said} is the user's word, {meant}
		# what it is to mean.
		confirm(_("From now on, when you say \"{said}\", VisionClaw will understand \"{meant}\". Keep this?").format(
			said=said, meant=meant))
		try:
			replaced = grammar.teach(said, meant)
		except ValueError as e:
			return f"{e} Nothing was kept."
		except OSError as e:
			raise ToolError(f"The word could not be saved: {e}")
		return (f"From now on, \"{said}\" is understood as \"{meant}\"."
			+ (" It replaces what that word meant before." if replaced else "")
			+ f" To undo it, say forget the word {said}.")

	add("my_words",
		"teach VisionClaw a word or phrase of the user's own that is to mean something else from now on, list the words "
		"taught, or forget one or all of them",
		myWords, {
			"action": text("teach a new word, list the words taught, forget one word, or forget all of them",
				enum=list(understand.ACTIONS), auto=understand.actionOf),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, title="Your own words", tell=VERBATIM)
