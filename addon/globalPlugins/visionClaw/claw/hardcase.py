# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the model for hard cases. The owner said on 2026-11-19: "all offered qwen AI models from the smallest to
# the largest, capped at 9b parameter models, with edge cases using a 14b parameter model." So VisionClaw's everyday
# models stay at 9 billion parameters or fewer, and one larger model, Qwen3 14B (catalog entries with "edge"), is kept
# for the cases the chosen models could not do:
#   - an add-on that could not be written so that it passes the checks, or that would not start;
#   - an add-on VisionClaw wrote that fails again after it was corrected before;
#   - a control of a stubborn program where the picture and what is reported say different things about how it is
#     worked, or where neither could tell.
# Plain code decides that a case is hard; the user decides whether the larger model is used (the setting hardCases:
# ask first, the default, or always), and which one (hardModel: "" any on the disk, "none" never, or a catalog id).
# It is slower, may be split between the graphics card and the processor, and reads and writes text only: no Qwen model
# of that size sees pictures. Everything it writes is checked by plain code as before. No NVDA dependencies.

import re

from .catalog import QUANTS, displayName, isEdge, quantOf
from .working import UNSURE, WAYS

ASK, ALWAYS = "ask", "always"
CHOICES = (ASK, ALWAYS)
NONE = "none"

# Why a case is hard, in the words the question to the user begins with.
ADDON = "The add-on could not be written so that it passes VisionClaw's checks."
START = "The add-on could not be made to start."
FIX_AGAIN = "This add-on was corrected before and fails again."
FIX = "The add-on could not be corrected so that it passes VisionClaw's checks."
ASKED = "You asked for the model for hard cases."
JUDGE = "For {count} of the controls, what is shown and what is reported say different things, or neither could tell."
NAME = "For {count} of the controls without a name, nothing could be read from their picture."


# The user's own words that ask for the model for hard cases: then it is used without the question, since they asked.
_ASKED = re.compile(
	r"\b(model for (the )?hard cases|hard[- ]case model|(the )?(14 ?b|fourteen ?b)( model)?|qwen ?3 14 ?b|"
	r"(with|use|using|try) the (larger|bigger|biggest|largest) model)\b", re.IGNORECASE)


def asked(words):
	"""Whether the user's own words ask for the model for hard cases."""
	return bool(_ASKED.search(str(words or "")))


def candidates(entries):
	"""The models for hard cases among these entries, in the order of QUANTS (Q4_K_M first)."""
	found = [entry for entry in entries or () if isEdge(entry)]
	return sorted(found, key=lambda entry: QUANTS.index(quantOf(entry)) if quantOf(entry) in QUANTS else len(QUANTS))


def chosen(entries, setting, installed):
	"""The model for hard cases that is used, or None. entries: the catalog's entries. setting: the user's choice,
	"" for any one on the disk, NONE for never, or a catalog id. installed(entry): whether it is on the disk."""
	setting = str(setting or "")
	if setting == NONE:
		return None
	models = candidates(entries)
	if setting:
		wanted = [entry for entry in models if entry["id"] == setting]
		return wanted[0] if wanted and installed(wanted[0]) else None
	return next((entry for entry in models if installed(entry)), None)


def name(entry):
	return displayName(entry)


def question(entry, why):
	"""What the user is asked before the model for hard cases is used."""
	return (
		f"{why} VisionClaw has a larger model for hard cases on this computer, {name(entry)}. It is slower: loading it "
		"and its answer may take a few minutes, and the models you use every day are unloaded meanwhile. It reads and "
		"writes text only, and its work is checked like any other. Try once more with it?")


def startText(entry):
	"""What the user is told when the model for hard cases starts on a case."""
	return f"Asking the model for hard cases, {name(entry)}. This may take a few minutes; NVDA+Alt+X stops it."


def missingText(entries):
	"""Said after a hard case failed and no model for hard cases is on the disk: where to get one."""
	models = candidates(entries)
	if not models:
		return ""
	return (
		f"A larger model for hard cases, {displayName(models[0]).rsplit(' ', 1)[0]}, may do it. It can be downloaded in "
		"the models window, NVDA+Alt+M, in the list Model for hard cases.")


def isHardJudgement(judged):
	"""Whether a judgement of how a control is worked is a hard case: the picture and the facts disagree, or neither
	could tell, and the facts say something a model can reason from. judged: what accesstools.judge returns."""
	if not judged or judged.get("sure"):
		return False
	return bool(judged.get("telling"))


def settles(seen, thought, hard):
	"""How the answer of the model for hard cases (made from what is reported) settles one control, as (way, sure):
	where it agrees with one of the two answers before (from the picture, from the facts), that answer is sure; where
	neither before could tell, its answer stands alone and is not sure; where it says something a third, or cannot
	tell either, nothing changes: (None, False)."""
	hard = hard if hard in WAYS and hard != UNSURE else None
	seen = seen if seen in WAYS and seen != UNSURE else None
	thought = thought if thought in WAYS and thought != UNSURE else None
	if hard is None:
		return None, False
	if hard in (seen, thought):
		return hard, True
	if seen is None and thought is None:
		return hard, False
	return None, False
