# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the orchestration policy: how much each model may think and write, and how hard to try, chosen
# for each request from what kind of request it is and from the user's reasoning setting.
# The context size itself is chosen per model call, in llm.py, from the length of that call.
# No NVDA dependencies.

import collections

from .catalog import CODER, VISION
from .llm import HIGH, LEVELS, LOW, MEDIUM, OFF

AUTO = "auto"
REASONING_CHOICES = (AUTO,) + LEVELS
SIMPLE, MODERATE, COMPLEX = "simple", "moderate", "complex"

# Who does what. The vision model is the general-purpose one, so it plans and fills in tool forms; the coder
# model reviews the plan, gives hints when a step is stuck, checks the result, and writes all code.
LEAD, OTHER = VISION, CODER
ROLE_NAMES = {VISION: "vision model", CODER: "coder model"}

Params = collections.namedtuple("Params", (
	"reasoning",     # off, low, medium, high
	"maxSteps",      # most steps in a plan
	"planTokens",    # most tokens for writing a plan
	"formTokens",    # most tokens for filling in one tool form
	"answerTokens",  # most tokens for the final answer
	"codeTokens",    # most tokens for a generated add-on
	"retries",       # tries to fix a failed step before asking for help
	"replans",       # times the rest of the plan may be rewritten after looking
	"codeRepairs",   # tries to fix generated code that fails its checks
	"codeReviews",   # times the other model reviews generated code
	"verify",        # whether the other model checks the result at the end
	"oneByOne",      # ask for one field at a time and answer with quotes: for the very smallest models
))
Params.__new__.__defaults__ = (False,)
STEPWISE_CHOICES = (AUTO, "always", "never")


def stepwise(choice, entry):
	"""Whether the model that fills in the forms is asked one small question at a time. choice: the user's
	setting; Automatic means: for a very small model. entry: that model's entry in the catalog."""
	if choice == "always":
		return True
	if choice == "never":
		return False
	return bool(entry) and entry.get("suggest") is False

_AUTO_LEVEL = {SIMPLE: OFF, MODERATE: LOW, COMPLEX: MEDIUM}
_BY_LEVEL = {
	#        plan form answer code retries replans repairs reviews verify
	OFF:    (380, 180, 220, 1000, 1, 0, 2, 0, False),
	LOW:    (480, 220, 280, 1300, 2, 1, 2, 1, True),
	MEDIUM: (640, 280, 380, 1700, 2, 2, 3, 1, True),
	HIGH:   (860, 340, 520, 2300, 3, 2, 4, 2, True),
}
_MAX_STEPS = {SIMPLE: 4, MODERATE: 6, COMPLEX: 8}


def level(triage, userReasoning=AUTO):
	"""The reasoning level for a request. The user's choice wins; otherwise harder requests get more."""
	if userReasoning in LEVELS:
		return userReasoning
	chosen = _AUTO_LEVEL.get(triage.get("complexity"), LOW)
	if triage.get("needs_code") and chosen != HIGH:
		chosen = LEVELS[LEVELS.index(chosen) + 1]  # code is where small models need the most care
	return chosen


def select(triage, userReasoning=AUTO):
	chosen = level(triage, userReasoning)
	plan, form, answer, code, retries, replans, repairs, reviews, verify = _BY_LEVEL[chosen]
	return Params(
		chosen, _MAX_STEPS.get(triage.get("complexity"), 6), plan, form, answer, code, retries, replans, repairs,
		reviews, verify,
	)


__all__ = ["AUTO", "REASONING_CHOICES", "STEPWISE_CHOICES", "stepwise", "LEAD", "OTHER", "ROLE_NAMES", "Params", "level", "select",
	"SIMPLE", "MODERATE", "COMPLEX", "OFF", "LOW", "MEDIUM", "HIGH"]
