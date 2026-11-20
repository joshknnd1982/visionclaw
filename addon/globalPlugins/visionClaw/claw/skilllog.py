# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what NVDA's own log tells the skills. The owner said on 2026-11-19: "all existing skills and system prompts
# should be able to query the log to get even more info and be even more useful and powerful for what the end-user will
# want to ask visionclaw to do", and "combine that with updated system prompts, too."
# Every skill names in its SKILL.md what it wants from NVDA's log (log:, skills.LOG_KINDS): errors, add-ons, speech,
# audio, braille, freezes, session, settings, objects (NVDA's developer info after NVDA+F1), input help, remote. When a
# skill is used for a request, plain code takes from what NVDA logged in the last minutes the facts of those kinds
# (nvdalog.factsFor), the newest first, at most MAX_LINES, and they go where the skill's sentences go: to the steps of its
# jobs and to the answer. Each line begins with HEAD, so the answer's system prompt gets prompts.NVDA_LOG_HELP. When
# nothing of those kinds was logged, nothing is added: a small model reads a few lines that fit, or none.
# Only what nvdalog may read: never the levels IO, DEBUG and DEBUG_UNREDACTED, never what VisionClaw logged itself. Never
# a fault. No NVDA dependencies.

from . import debuglog, nvdalog, prompts

# How far back the facts are taken: errors explain what just went wrong, the rest say what NVDA did lately.
ERRORS_SECONDS = 120
RECENT_SECONDS = 600
# At most this many lines go with a step or an answer.
MAX_LINES = 3
HEAD = "From NVDA's log"


def kindsFor(skills, applies, recipe=None, anyRecipe=None):
	"""The log kinds of the skills that speak about this recipe (or any of anyRecipe, for the answer), in order, each once.
	applies(skill, recipe) is skills.applies."""
	kinds = []
	for skill in skills or ():
		fits = (any(applies(skill, r) for r in anyRecipe) if anyRecipe is not None else applies(skill, recipe))
		if fits:
			kinds += [kind for kind in getattr(skill, "log", ()) if kind not in kinds]
	return kinds


def _ago(seconds):
	seconds = max(0, int(seconds))
	if seconds < 60:
		return "just now"
	minutes = round(seconds / 60)
	return f"{minutes} minute{'s' if minutes != 1 else ''} ago"


def lines(entries, kinds, now, modules=None, names=None, limit=MAX_LINES):
	"""The lines of NVDA's log for these kinds: facts written in the last RECENT_SECONDS (errors: ERRORS_SECONDS), the
	newest first, each once, never VisionClaw's own, at most limit, each "From NVDA's log, 2 minutes ago: ...". [] when
	there are none. Never raises."""
	try:
		found = []
		for kind in kinds or ():
			window = ERRORS_SECONDS if kind == "errors" else RECENT_SECONDS
			for fact in nvdalog.factsFor(entries, kind, modules, names):
				when = fact.get("when")
				said = " ".join(str(fact.get("said") or "").split())
				if not said or when is None or now - when > window or now - when < -5 or nvdalog.isOwn(fact, modules):
					continue
				# The add-on a line came from is named, so that the user and the model know whose it is.
				addon = str(fact.get("addon") or "")
				name = (names or {}).get(addon) or addon
				if name and name.lower() not in said.lower():
					said = f"{said.rstrip('.')}, from the add-on {name}."
				found.append((when, said))
		found.sort(key=lambda item: -item[0])
		chosen, seen = [], set()
		for when, said in found:
			if said in seen:
				continue
			seen.add(said)
			chosen.append(f"{HEAD}, {_ago(now - when)}: {said}")
			if len(chosen) >= limit:
				break
		return chosen
	except Exception as e:
		debuglog.error("nvdalog", "The facts of NVDA's log could not be chosen for a skill", e)
		return []


def objectLines(entries, program, now, purpose="", limit=1):
	"""For the model that writes an add-on: the facts NVDA logged in its developer info (NVDA+F1) about objects of this
	program in the last RECENT_SECONDS, newest first, as one plain sentence each (nvdalog.objectFacts), under HEAD. Only
	where what the add-on is for names a control or "this", since an add-on that is not about one control is not helped.
	"" when there are none. Never a value of the object: that may be what was typed."""
	if not _AT_CONTROL(purpose):
		return ""
	try:
		program = " ".join(str(program or "").split()).lower()
		chosen = []
		for info in reversed(nvdalog.devInfos(entries)):
			when = info.get("when")
			if when is None or now - when > RECENT_SECONDS:
				continue
			said = nvdalog.objectFacts(info)
			fields = info.get("fields") or {}
			# devInfos keeps the fields' names in lower case.
			made = " ".join(str(fields.get("appmodule.productname") or fields.get("appmodule") or "").split()).lower()
			if not said or (program and made and program not in made and made not in program):
				continue
			chosen.append(said)
			if len(chosen) >= limit:
				break
		return "\n".join([prompts.LOG_HEAD] + chosen) if chosen else ""
	except Exception as e:
		debuglog.error("nvdalog", "The developer info in NVDA's log could not be read for an add-on", e)
		return ""


def _AT_CONTROL(purpose):
	"""Whether what an add-on is for points at one control: a kind of control, or this, that or it."""
	words = " " + " ".join(str(purpose or "").lower().split()) + " "
	return any(f" {word} " in words or f" {word}s " in words for word in _CONTROL_WORDS)


_CONTROL_WORDS = ("this", "that", "it", "button", "control", "field", "edit", "list", "slider", "checkbox", "check box",
	"combo", "tab", "menu", "link", "item", "tree", "grid", "cell", "dial", "knob", "fader", "object", "element", "window",
	"dialog", "toolbar", "pane", "panel", "box")
