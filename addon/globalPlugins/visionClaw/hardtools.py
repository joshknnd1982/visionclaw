# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the model for hard cases, on NVDA's side: which one is on this computer, asking the user first, and
# using it for one piece of work only (claw/hardcase.py says what a hard case is). The everyday models come back with
# the next request.

import addonHandler
import config
from .vclog import log

from .claw import debuglog, hardcase
from .claw.catalog import CODER

addonHandler.initTranslation()


def _conf():
	return config.conf["visionClaw"]


def chosen(plugin):
	"""The model for hard cases that is on this computer and may be used, or None."""
	try:
		models = plugin.runtime.catalog
		return hardcase.chosen(models.entries(CODER), _conf()["hardModel"], models.isInstalled)
	except Exception:
		log.debugWarning("VisionClaw: the model for hard cases could not be found", exc_info=True)
		return None


def missing(plugin):
	"""Where a model for hard cases can be had, when none is on this computer and the user did not turn it off; else
	"". Said after a hard case failed."""
	try:
		if _conf()["hardModel"] == hardcase.NONE or chosen(plugin) is not None:
			return ""
		return hardcase.missingText(plugin.runtime.catalog.entries(CODER))
	except Exception:
		return ""


def attempt(plugin, task, why, work):
	"""Do work() once more with the model for hard cases, after asking the user unless they chose to be asked never.
	why: the sentence that says why the case is hard (hardcase.ADDON and the others). Returns (True, what work
	returned), or (False, a sentence for the user) when it was not tried: none on this computer, or the user said no.
	Errors of work() itself are passed on, as the everyday models' would be. Where the user's own words ask for the
	model for hard cases, nothing is asked."""
	entry = chosen(plugin)
	if entry is None:
		return False, missing(plugin)
	# Asked for in the user's own words ("fix it with the model for hard cases"), it is used without a question.
	if _conf()["hardCases"] != hardcase.ALWAYS and not hardcase.asked(getattr(task, "request", "")):
		# Translators: Choices when VisionClaw offers to try a hard case again with its larger model.
		choices = [_("Yes, try it with the larger model"), _("No")]
		if plugin.clawAsk(hardcase.question(entry, why), choices) != 0:
			debuglog.log("hard", f"The user did not want the model for hard cases: {why}")
			return False, ""
	task.check()
	debuglog.log("hard", f"Using the model for hard cases, {hardcase.name(entry)}: {why}")
	task.emit("talk", hardcase.startText(entry))
	with plugin.runtime.hardCase(entry):
		return True, work()
