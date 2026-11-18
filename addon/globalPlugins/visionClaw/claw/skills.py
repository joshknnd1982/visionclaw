# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - skills: short instruction files, after SmallClaw's SKILL.md, that teach VisionClaw how and when
# to do a kind of job the way a blind person needs it done. A skill is a folder with one SKILL.md in it:
#
#   ---
#   name: Describe a photo
#   description: what the skill is for, in one line
#   when: photo, picture, selfie            the words that start it, separated by commas
#   uses: describe                          the recipes it is for (planner.RECIPES), separated by commas
#   steps:                                  optional: a fixed list of recipes, each with the words it is given
#   - where_am_i
#   - describe: say what this window shows
#   ---
#   Plain sentences that say how the job is done well.
#
# Plain code chooses the skill, by its words (choose); no model is asked which skill fits. The chosen skill's
# sentences are given, clipped, to the models where they write: the forms of its recipes' steps, the question
# put to the vision model, the add-on the coder writes, and the answer the user hears. A skill with steps is a
# plan of the user's own, or one VisionClaw ships: when the request has one of its starting phrases word for
# word, its steps are run as they are, each one a proven recipe, and no model plans anything.
#
# VisionClaw comes with its own skills (the folder skills next to this file); the user's are kept in
# VisionClaw's data folder, where they survive updates. A skill of the user's with the name of one of
# VisionClaw's takes its place, so a built-in skill is changed by saving a copy, and put back by deleting that
# copy. Any skill can be turned off. A skill is text, never code: it can only say how the tools are used, and
# every tool still asks before it changes anything. No NVDA dependencies.

import json
import os
import re
import shutil
import threading

from . import debuglog
from .llm import clip
from .memory import wordList

FILE = "SKILL.md"
BUILT_IN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
STATE = "skills.json"
YOURS, OURS = "yours", "built-in"
README = "README.md"
README_TEXT = """# Your VisionClaw skills

Each skill is a folder in this folder, with one file in it called SKILL.md. The easiest way to make, change,
turn off or delete a skill is the skills window: press NVDA+Alt+I. You can also ask VisionClaw in words, for
instance to make a new skill, to list the skills, or to delete one.

A SKILL.md file is plain text. It starts with a few lines between two lines of three dashes:

    ---
    name: the name of the skill
    description: what it is for, in one line
    when: the words in a request that start it, separated by commas
    uses: the jobs it is for, separated by commas; leave this line out for every job
    ---
    Then, in plain sentences, what VisionClaw should do or keep to for this kind of job.

A skill is text, never a program. It can only tell VisionClaw how to work; VisionClaw still asks you before it
changes anything. Your skill with the same name as one of VisionClaw's own takes its place.
"""

NAME_CHARS = 60
DESCRIPTION_CHARS = 200
PHRASE_CHARS = 60
MAX_PHRASES = 16
MAX_STEPS = 6
STEP_WORDS_CHARS = 200
INSTRUCTION_CHARS = 1500
MAX_SKILLS = 300
# How much of a skill's sentences a model is given with a step, and with the answer.
GUIDE_CHARS = 520
# How many skills are used with one request, at most.
MAX_CHOSEN = 2

_FENCE = re.compile(r"^\s*---\s*$")
_KEY = re.compile(r"^([A-Za-z][\w -]*?)\s*:\s*(.*)$")
_STEP = re.compile(r"^\s*(?:[-*]|\d+[.)])\s*([a-z_]+)\s*(?::\s*(.*))?$")
_HEADING = re.compile(r"^\s*#+\s*(.+?)\s*$")
_ALIASES = {
	"triggers": "when", "trigger": "when", "keywords": "when", "trigger words": "when", "starts when": "when",
	"recipes": "uses", "recipe": "uses", "use": "uses", "for": "uses", "title": "name"}


class SkillError(Exception):
	"""A skill that cannot be read or saved. The message says why, in plain words."""


class Skill:
	"""One skill. slug: its folder name. source: YOURS or OURS. on: whether it is used."""

	def __init__(self, name, description="", when=(), uses=(), steps=(), instructions="", slug="", source=YOURS,
			path=""):
		self.name = " ".join(str(name or "").split())[:NAME_CHARS]
		self.description = " ".join(str(description or "").split())[:DESCRIPTION_CHARS]
		self.when = _phrases(when)
		self.uses = tuple(_names(uses))
		self.steps = tuple(
			(recipe, " ".join(str(words or "").split())[:STEP_WORDS_CHARS]) for recipe, words in steps)[:MAX_STEPS]
		self.instructions = str(instructions or "").strip()[:INSTRUCTION_CHARS]
		self.slug = slug or slugOf(self.name)
		self.source = source
		self.path = path
		self.on = True
		# Set by Skills when one of the user's skills takes the place of a built-in skill of the same name.
		self.replaces = False

	def __repr__(self):
		return f"Skill({self.slug}, {self.source}, on={self.on})"


def slugOf(name):
	"""A folder name for a skill, from its name."""
	return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")[:50] or "skill"


def _phrases(value):
	if isinstance(value, str):
		value = value.split(",")
	found = []
	for phrase in value or ():
		phrase = " ".join(str(phrase).strip(" .;\"'").split()).lower()[:PHRASE_CHARS]
		if phrase and phrase not in found:
			found.append(phrase)
	return tuple(found[:MAX_PHRASES])


def _names(value):
	if isinstance(value, str):
		value = value.split(",")
	found = []
	for name in value or ():
		name = str(name).strip().lower().replace(" ", "_")
		if name and name not in found:
			found.append(name)
	return found


# --- SKILL.md ---

def parse(text, slug="", source=YOURS, path=""):
	"""A Skill from the text of a SKILL.md. Without the lines between --- at the top, a Markdown heading
	gives the name and the rest is the instructions."""
	lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").split("\n")
	head, body = {}, lines
	if lines and _FENCE.match(lines[0]):
		end = next((i for i in range(1, len(lines)) if _FENCE.match(lines[i])), None)
		if end is None:
			raise SkillError("The lines at the top of the skill start with three dashes but never end with them.")
		head, body = _head(lines[1:end]), lines[end + 1:]
	if "name" not in head:
		for i, line in enumerate(body):
			if line.strip():
				heading = _HEADING.match(line)
				if heading:
					head["name"] = heading.group(1)
					body = body[i + 1:]
				break
	if not head.get("name"):
		raise SkillError("The skill has no name.")
	return Skill(
		head.get("name"), head.get("description", ""), head.get("when", ""), head.get("uses", ""),
		head.get("steps", ()), "\n".join(body).strip(), slug, source, path)


def _head(lines):
	"""The lines between the dashes, as a dictionary. A key with nothing after it takes the indented or listed
	lines below it, as steps or as a list."""
	head, key = {}, None
	for line in lines:
		if not line.strip() or line.lstrip().startswith("#"):
			continue
		step = _STEP.match(line) if key else None
		if step and (line[:1] in " \t-*" or line.lstrip()[:1].isdigit()):
			if key == "steps":
				head.setdefault("steps", []).append((step.group(1), step.group(2) or ""))
			else:
				items = head.get(key) or []
				head[key] = (items if isinstance(items, list) else [items]) + [line.strip(" -*\t")]
			continue
		match = _KEY.match(line.strip())
		if not match:
			continue
		key = match.group(1).strip().lower()
		key = _ALIASES.get(key, key)
		value = match.group(2).strip().strip("\"'")
		if key == "steps":
			head["steps"] = []
		elif value.startswith("[") and value.endswith("]"):
			head[key] = [part.strip().strip("\"'") for part in value[1:-1].split(",")]
		else:
			head[key] = value
	return head


def toText(skill):
	"""The SKILL.md of a skill."""
	lines = ["---", f"name: {skill.name}"]
	if skill.description:
		lines.append(f"description: {skill.description}")
	lines.append(f"when: {', '.join(skill.when)}")
	if skill.uses:
		lines.append(f"uses: {', '.join(skill.uses)}")
	if skill.steps:
		lines.append("steps:")
		lines += [f"- {recipe}: {words}" if words else f"- {recipe}" for recipe, words in skill.steps]
	lines += ["---", "", skill.instructions.strip(), ""]
	return "\n".join(lines)


def check(skill, recipes):
	"""What is wrong with a skill, in plain sentences; empty when nothing is. recipes: the names of the recipes
	that can be used."""
	problems = []
	if not skill.name:
		problems.append("It has no name.")
	if not skill.when:
		problems.append("It has no words that start it.")
	for phrase in skill.when:
		if not wordList(phrase):
			problems.append(
				f"The words \"{phrase}\" are too common to tell this skill apart. Give words that name what it is about.")
	for name in skill.uses:
		if name not in recipes:
			problems.append(f"It is for \"{name}\", which is not something VisionClaw can do.")
	for recipe, _words in skill.steps:
		if recipe not in recipes:
			problems.append(f"One of its steps is \"{recipe}\", which is not something VisionClaw can do.")
	if not skill.instructions and not skill.steps:
		problems.append("It says nothing about how the job is done, and it has no steps.")
	return problems


# --- Choosing ---

def _plain(text):
	return " " + re.sub(r"[^a-z0-9']+", " ", str(text or "").lower()).strip() + " "


def _hit(phrase, request, words, plain):
	"""How well one starting phrase fits a request: 0 when it does not. A phrase of one word fits a request
	with that word in any form ("photos" for "photo"). A phrase of several words fits where it is word for word,
	or, when two or more of its words tell what it is about, where all of those are, in any order. A phrase
	whose only telling word is an everyday one ("can't read", "new to nvda") must be there word for word,
	or it would start the skill for every request with that word. Longer phrases fit better."""
	telling = set(wordList(phrase))
	if not telling:
		return 0.0
	if _plain(phrase) in plain:
		return len(phrase.split()) + 0.5
	if (len(telling) >= 2 or len(phrase.split()) == 1) and telling <= words:
		return float(len(telling))
	return 0.0


def score(skill, request):
	words, plain = set(wordList(request)), _plain(request)
	return max((_hit(phrase, request, words, plain) for phrase in skill.when), default=0.0)


def exact(skill, request):
	"""Whether the request has one of the skill's starting phrases word for word."""
	plain = _plain(request)
	return any(wordList(phrase) and _plain(phrase) in plain for phrase in skill.when)


def applies(skill, recipe):
	"""Whether a skill speaks about a step of this recipe. A step a model planned itself (recipe None) is
	told every chosen skill."""
	return recipe is None or not skill.uses or recipe in skill.uses


def guide(chosen, recipe=None, chars=GUIDE_CHARS, anyRecipe=None):
	"""The sentences of the chosen skills that are about a step of this recipe, for a model to follow; "" when
	none are. anyRecipe: a set of recipes, for the answer, which is about all the steps."""
	texts = []
	for skill in chosen or ():
		fits = (any(applies(skill, r) for r in anyRecipe) if anyRecipe is not None else applies(skill, recipe))
		if fits and skill.instructions:
			texts.append(f"Follow the skill \"{skill.name}\": " + " ".join(skill.instructions.split()))
	if not texts:
		return ""
	share = max(120, chars // len(texts))
	return "\n".join(clip(text, share).replace(" ...[cut]", "") for text in texts)


def planned(chosen, request):
	"""The skill whose steps are run as they are, or None: one with steps, whose starting phrase is in the
	request word for word."""
	for skill in chosen or ():
		if skill.steps and exact(skill, request):
			return skill
	return None


ADDON_JOBS = frozenset(("write_addon", "fix_addon"))


def addonGuide(lib, purpose):
	"""The sentences of the skills about writing add-ons that fit what an add-on is for; "" when none do or
	there are no skills. For the coder when there is no step to take them from, as when VisionClaw corrects an
	add-on by itself. Never raises: a skill only helps."""
	if lib is None:
		return ""
	try:
		return guide(lib.choose(purpose), anyRecipe=ADDON_JOBS)
	except Exception as e:
		debuglog.error("skills", "The skills for an add-on could not be chosen", e)
		return ""


def stepGuide(task):
	"""The skill sentences for the step a task is on; "" when there are none."""
	try:
		return task.steps[task.current].guide or ""
	except (AttributeError, IndexError, TypeError):
		return ""


# --- The skills on this computer ---

class Skills:
	"""VisionClaw's own skills and the user's. folder: the user's skills; builtIn: VisionClaw's own."""

	def __init__(self, folder, builtIn=BUILT_IN, recipes=None):
		self.folder = folder
		self.builtIn = builtIn
		# The names of the recipes that can be used; a skill for anything else is not used.
		self.recipes = recipes
		self._lock = threading.RLock()
		self._skills = None
		self._off = None

	# Loading

	def _read(self, folder, source):
		found = {}
		try:
			names = sorted(os.listdir(folder))
		except OSError:
			return found
		for name in names:
			path = os.path.join(folder, name, FILE)
			if not os.path.isfile(path):
				continue
			try:
				with open(path, encoding="utf-8") as f:
					skill = parse(f.read(), name, source, path)
			except (OSError, UnicodeDecodeError, SkillError) as e:
				debuglog.error("skills", f"The skill in {path} could not be read", e)
				continue
			found[name] = skill
		return found

	def _statePath(self):
		return os.path.join(self.folder, STATE)

	def prepare(self):
		"""Make the user's skills folder, with a file that says how a skill is written, and return its path."""
		os.makedirs(self.folder, exist_ok=True)
		readme = os.path.join(self.folder, README)
		if not os.path.exists(readme):
			try:
				with open(readme, "w", encoding="utf-8") as f:
					f.write(README_TEXT)
			except OSError as e:
				debuglog.error("skills", "The note on writing skills could not be written", e)
		return self.folder

	def _load(self):
		with self._lock:
			if self._skills is None:
				ours = self._read(self.builtIn, OURS)
				yours = self._read(self.folder, YOURS)
				for slug, skill in yours.items():
					skill.replaces = slug in ours
				merged = dict(ours)
				merged.update(yours)
				try:
					with open(self._statePath(), encoding="utf-8") as f:
						self._off = set(json.load(f).get("off") or ())
				except (OSError, ValueError, AttributeError):
					self._off = set()
				for slug, skill in merged.items():
					skill.on = slug not in self._off
				self._skills = merged
			return self._skills

	def reload(self):
		with self._lock:
			self._skills = None
		return self.all()

	def all(self):
		"""Every skill, in order of its name."""
		return sorted(self._load().values(), key=lambda s: s.name.lower())

	def get(self, slug):
		return self._load().get(slug)

	def builtInCopy(self, slug):
		"""VisionClaw's own skill of this folder name, even when one of the user's takes its place."""
		return self._read(self.builtIn, OURS).get(slug)

	def find(self, said):
		"""The skill a few words name, or None: by its name, then by its folder name, then by most shared words."""
		said = " ".join(str(said or "").lower().split()).strip(" .\"'")
		if not said:
			return None
		skills = self.all()
		for skill in skills:
			if skill.name.lower() == said or skill.slug == slugOf(said):
				return skill
		for skill in skills:
			if said in skill.name.lower():
				return skill
		wanted = set(wordList(said))
		best, most = None, 0
		for skill in skills:
			shared = len(wanted & set(wordList(skill.name)))
			if shared > most:
				best, most = skill, shared
		return best if most and most * 2 >= len(wanted) else None

	def usable(self, skill):
		return skill.on and (self.recipes is None or not check(skill, self.recipes))

	def choose(self, request, limit=MAX_CHOSEN):
		"""The skills that fit a request, best first, by their starting words. Plain code; no model."""
		scored = []
		for skill in self._load().values():
			if not self.usable(skill):
				continue
			found = score(skill, request)
			if found:
				# Among equals, the user's own skill comes first.
				scored.append((-found, 0 if skill.source == YOURS else 1, skill.name.lower(), skill))
		scored.sort(key=lambda item: item[:3])
		chosen = [item[3] for item in scored[:limit]]
		if chosen:
			debuglog.log("skills", f"Skills chosen for {request!r}: {[skill.slug for skill in chosen]}")
		return chosen

	# Changing

	def _saveState(self):
		os.makedirs(self.folder, exist_ok=True)
		with open(self._statePath(), "w", encoding="utf-8") as f:
			json.dump({"off": sorted(self._off)}, f, indent=1)

	def setOn(self, slug, on):
		with self._lock:
			self._load()
			if on:
				self._off.discard(slug)
			else:
				self._off.add(slug)
			self._saveState()
			skill = self._skills.get(slug)
			if skill:
				skill.on = bool(on)

	def save(self, skill, replace=""):
		"""Keep a skill of the user's. replace: the folder name of the skill it is a new version of, "" for a new
		skill. A skill with the name of one of VisionClaw's own takes its place. Returns the saved Skill."""
		problems = check(skill, self.recipes) if self.recipes is not None else []
		if problems:
			raise SkillError(" ".join(problems))
		with self._lock:
			skills = self._load()
			yours = [s for s in skills.values() if s.source == YOURS]
			slug = replace or skill.slug or slugOf(skill.name)
			if not replace:
				taken = skills.get(slug)
				if taken is not None and taken.source == YOURS:
					number = 2
					while skills.get(f"{slug}-{number}") is not None:
						number += 1
					slug = f"{slug}-{number}"
				if len(yours) >= MAX_SKILLS:
					raise SkillError(f"You have {len(yours)} skills, which is as many as VisionClaw keeps. Delete one first.")
			path = os.path.join(self.folder, slug, FILE)
			os.makedirs(os.path.dirname(path), exist_ok=True)
			skill.slug, skill.source, skill.path = slug, YOURS, path
			with open(path, "w", encoding="utf-8") as f:
				f.write(toText(skill))
			debuglog.log("skills", f"Saved the skill {slug} to {path}")
			self._skills = None
			return self.get(slug)

	def remove(self, slug):
		"""Delete one of the user's skills. A built-in skill cannot be deleted, only turned off; one of the
		user's that took its place is deleted, and VisionClaw's own comes back. Returns what happened, in words."""
		with self._lock:
			skill = self._load().get(slug)
			if skill is None:
				raise SkillError("There is no such skill.")
			if skill.source != YOURS:
				raise SkillError("This skill comes with VisionClaw. It can be turned off, but not deleted.")
			folder = os.path.dirname(skill.path)
			# Only a folder inside the user's skills folder is ever deleted.
			if os.path.dirname(os.path.abspath(folder)) != os.path.abspath(self.folder):
				raise SkillError("This skill is not in your skills folder.")
			shutil.rmtree(folder, ignore_errors=True)
			debuglog.log("skills", f"Deleted the skill {slug}")
			self._skills = None
			ours = self.get(slug)
			return (f"Your skill {skill.name} was deleted. VisionClaw's own skill of that name is used again."
				if ours is not None else f"Your skill {skill.name} was deleted.")

	def importText(self, text, fileName=""):
		"""Keep a skill from the text of a SKILL.md or other Markdown file someone shared. Returns the Skill."""
		skill = parse(text, slugOf(os.path.splitext(os.path.basename(fileName))[0]) if fileName else "")
		skill.slug = slugOf(skill.name)
		return self.save(skill)


def describe(skill, label=None):
	"""Everything about a skill, as the user reads or hears it. label(recipe) says a recipe in words."""
	say = label or (lambda name: name)
	lines = [skill.name + (f": {skill.description}" if skill.description else "")]
	where = "Yours" if skill.source == YOURS else "Comes with VisionClaw"
	if skill.replaces:
		where = "Yours, in place of VisionClaw's own skill of this name"
	lines.append(f"{where}. {'On' if skill.on else 'Off'}.")
	lines.append("Used when your request says: " + "; ".join(skill.when) + ".")
	if skill.uses:
		lines.append("For: " + "; ".join(say(name) for name in skill.uses) + ".")
	if skill.steps:
		lines.append("Its steps, run when your request has one of those words exactly:")
		lines += [f"{number}. {say(recipe)}" + (f": {words}" if words else "")
			for number, (recipe, words) in enumerate(skill.steps, 1)]
	if skill.instructions:
		lines.append("What it tells VisionClaw:")
		lines.append(skill.instructions)
	return "\n".join(lines)
