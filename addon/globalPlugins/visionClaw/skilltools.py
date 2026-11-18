# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - skills in words: making one, listing them, reading one, turning one off or on, and deleting one,
# all from the Ask VisionClaw window (claw/skills.py says what a skill is). What a new skill tells VisionClaw
# is the user's own words, cut by plain code to what comes after "make a skill"; a model only gives it a short
# name and picks out the words that start it, and plain code keeps only starting words the user really said.
# The skills window (skillsui.py) does all of this too, with the steps a skill can have.

import os
import re

import addonHandler
import wx

from .claw import planner, skills as skillsModule
from .claw.memory import wordList
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()

# The words before what a new skill tells VisionClaw: "please make a new skill called Recipes: ...".
_LEAD = re.compile(
	r"^\s*(?:please\s+)?(?:can you\s+|could you\s+|would you\s+|i want\s+|i'd like\s+)?(?:to\s+)?"
	r"(?:make|create|add|write|teach|save|set up)\s+(?:me\s+|you\s+|visionclaw\s+)?(?:an?\s+|the\s+)?(?:new\s+)?"
	r"skills?\b(?:\s+(?:called|named)\s+[\"']?[^:,.\"']{1,60}[\"']?)?\s*(?:[:,.-]\s*|\s+(?:that|which|so that|for|to)\b\s*)?",
	re.IGNORECASE)
_ALL = re.compile(r"\b(all|every|everything)\b", re.IGNORECASE)
# The words of a request about skills that say nothing about which skill is meant.
_ABOUT = frozenset(wordList(
	"skill skills delete remove forget erase turn off switch disable enable stop start using read show explain "
	"describe tell about called named which list open window folder many have does"))


def ownWords(asked):
	"""What a new skill tells VisionClaw: the user's own words after "make a skill", unchanged."""
	text = " ".join(str(asked or "").split())
	rest = _LEAD.sub("", text, count=1).strip()
	return rest[:1].upper() + rest[1:] if rest else text


def keptPhrases(when, asked):
	"""The starting words a model picked, kept only where every telling word of them is in the user's request."""
	said = set(wordList(asked))
	kept = []
	for phrase in skillsModule._phrases(when):
		telling = set(wordList(phrase))
		if telling and telling <= said and phrase not in kept:
			kept.append(phrase)
	return kept


def actionOf(asked):
	low = f" {str(asked or '').lower()} "
	if re.search(r"\b(turn on|switch on|enable|start using|use again)\b", low):
		return "turn on"
	if re.search(r"\b(turn off|switch off|disable|stop using|pause)\b", low):
		return "turn off"
	return "delete"


def register(plugin, add, text, onMain, confirm):
	"""The skill tools. add, text, onMain and confirm are the helpers of nvdatools.build."""

	def library():
		return plugin.skills

	def meant(asked, said=""):
		"""The skill the user's own words name, else the one the model wrote."""
		lib = library()
		found = None
		words = set(wordList(asked)) - _ABOUT
		if words:
			# The user's words decide. First a skill whose short name, its folder name, they say whole ("the
			# game skill" is the skill game, not every skill with "game" in its name); then the skill with most
			# of its name in them, and among equals the one whose name says least else.
			best, most = None, (0, 0)
			for skill in lib.all():
				short = set(wordList(skill.slug.replace("-", " ")))
				named = set(wordList(skill.name))
				rank = (len(short) if short and short <= words else 0, len(words & named))
				if rank > most or (rank == most and best is not None and rank[1]
						and len(named) < len(set(wordList(best.name)))):
					best, most = skill, rank
			found = best if most[1] or most[0] else None
		return found or lib.find(said)

	def addSkill(task, name, when, asked):
		instructions = ownWords(asked)
		phrases = keptPhrases(when, asked)
		if not phrases:
			# The name, if the user said it, is the least that can start the skill.
			phrases = keptPhrases(name, asked)
		if not phrases:
			raise ToolError("Say in the request which words should make VisionClaw use this skill.")
		skill = skillsModule.Skill(" ".join(str(name or "").split()) or phrases[0].capitalize(), "", phrases, (),
			(), instructions)
		problems = skillsModule.check(skill, planner.RECIPES)
		if problems:
			raise ToolError(" ".join(problems))
		# Translators: Asked before VisionClaw keeps a new skill. {name} is its name, {words} the words that start
		# it, {instructions} what it tells VisionClaw, in the user's own words.
		confirm(_(
			"Save a new skill called {name}? It is used when your request says: {words}. It tells VisionClaw: "
			"{instructions}").format(name=skill.name, words="; ".join(skill.when), instructions=skill.instructions))
		try:
			saved = library().save(skill)
		except (skillsModule.SkillError, OSError) as e:
			raise ToolError(f"The skill could not be saved: {e}")
		return (
			f"Saved the skill {saved.name}. It is used when your request says: {'; '.join(saved.when)}. "
			"You can read, change, turn off or delete it in the skills window, NVDA+alt+i.")

	add("add_skill",
		"make a new skill: what the user says VisionClaw should do, kept and used whenever later requests have "
		"its starting words", addSkill, {
			"name": text("a short name for the new skill, in two to five words", maxLength=60),
			"when": text(
				"the words of the user's request that should start the skill, separated by commas", maxLength=200),
			"asked": text("what the user asked for, in their own words", maxLength=1000, auto=True),
		}, changes=True, title="Making the skill", tell=VERBATIM)

	def listSkills(task, asked):
		lib = library()
		low = str(asked or "").lower()
		if re.search(r"\bfolder\b", low):
			folder = lib.folder
			try:
				lib.prepare()
				os.startfile(folder)
			except OSError as e:
				raise ToolError(f"The folder could not be opened ({e}). It is {folder}.")
			return f"Your skills folder is open. It is {folder}. Each skill is a folder with a file SKILL.md in it."
		if re.search(r"\b(open|window)\b", low):
			wx.CallAfter(plugin.showSkills)
			return "The skills window is open."
		every = lib.all()
		if not every:
			return "VisionClaw has no skills."
		words = set(wordList(asked)) - _ABOUT
		named = [s for s in every if words & set(wordList(s.name))] if words else []
		shown = named or every
		yours = sum(1 for s in every if s.source == skillsModule.YOURS)
		off = sum(1 for s in every if not s.on)
		head = (f"{len(named)} of VisionClaw's {len(every)} skills fit those words:" if named else
			f"VisionClaw has {len(every)} skills, {yours} of them yours"
			+ (f", {off} turned off" if off else "") + ":")
		lines = [head] + [
			f"{number}. {s.name}" + (" (yours)" if s.source == skillsModule.YOURS else "") + ("" if s.on else " (off)")
			for number, s in enumerate(shown, 1)]
		return "\n".join(lines)

	add("list_skills",
		"say which skills VisionClaw has, or open the skills window or the folder of the user's skills",
		listSkills, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking at the skills", tell=VERBATIM)

	def showSkill(task, skill, asked):
		found = meant(asked, skill)
		if found is None:
			raise ToolError(f"There is no skill called \"{skill}\". Use a name from list_skills.")
		return skillsModule.describe(found, planner.label)

	add("show_skill", "say what one skill does, when it is used and what it tells VisionClaw", showSkill, {
		"skill": text("the name of the skill, from list_skills", maxLength=80),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
	}, looks=True, before="list_skills", title="Reading the skill", tell=VERBATIM)

	def manageSkill(task, skill, action, asked):
		lib = library()
		if action == "delete" and _ALL.search(asked or ""):
			raise ToolError("Skills are deleted one at a time. Name the skill to delete.")
		found = meant(asked, skill)
		if found is None:
			raise ToolError(f"There is no skill called \"{skill}\". Use a name from list_skills.")
		if action == "turn on":
			lib.setOn(found.slug, True)
			return f"The skill {found.name} is on."
		if action == "delete" and found.source != skillsModule.YOURS:
			# Translators: Asked when the user wants to delete a skill that comes with VisionClaw. {name} is its name.
			confirm(_("The skill {name} comes with VisionClaw and cannot be deleted. Turn it off instead?").format(
				name=found.name))
			lib.setOn(found.slug, False)
			return f"The skill {found.name} comes with VisionClaw, so it was turned off. It can be turned on again."
		if action == "turn off":
			lib.setOn(found.slug, False)
			return f"The skill {found.name} is off. It can be turned on again."
		# Translators: Asked before one of the user's skills is deleted. {name} is its name.
		confirm(_("Delete your skill {name}? Its file is removed from this computer.").format(name=found.name))
		try:
			return lib.remove(found.slug)
		except (skillsModule.SkillError, OSError) as e:
			raise ToolError(f"The skill could not be deleted: {e}")

	add("manage_skill", "delete one of the user's skills, or turn a skill off or on", manageSkill, {
		"skill": text("the name of the skill, from list_skills", maxLength=80),
		"action": text("what to do with it", enum=["delete", "turn off", "turn on"], auto=actionOf),
		"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
	}, changes=True, before="list_skills", title="Changing the skill", tell=VERBATIM)
