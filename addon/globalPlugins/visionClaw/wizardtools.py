# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tool that goes through an installer, or any window worked by pressing one button page after
# page: "uncheck any bundled toolbars in this installer and click Next until the installation starts". What is
# asked is read from the user's own words, and the rules of the walk are plain code (claw/wizard.py): every page
# is said, offers of extra software are unchecked and named, licence terms are never accepted without a question,
# and the button that starts the installation is always asked about. No model is asked.
# The window is looked at the way working through a task looks at it (guidetools.lookAt): what the page or the
# program itself tells NVDA first, the window's picture where NVDA knows next to nothing of it.
# Going through an installer changes the computer, so the first question is always asked, whatever the settings say.

import time

import addonHandler

from . import guidetools
from .claw import guide, wizard
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()

# How long a page is given to show after a button was pressed.
SETTLE_SECONDS = 1.0


def register(add, plugin, text, onMain, confirm, mustAgree, screen):
	def stepThrough(task, asked):
		wished = wizard.wish(asked or task.request)
		if wished is None:
			raise ToolError(wizard.NO_WISH)
		if onMain(guidetools.ownWindow):
			return guide.NOT_OWN
		_program, title = onMain(guidetools.inFront)
		mustAgree(wizard.startQuestion(wished, title))
		said, pressed = wizard.walk(
			wished, lambda: guidetools.lookAt(task, onMain, screen),
			lambda thing: guidetools.pressThing(task, thing, onMain), plugin.clawAsk, task.check,
			lambda: time.sleep(SETTLE_SECONDS))
		task.items = None  # the window has changed
		return said or "VisionClaw found nothing to press in the window in front."

	add("step_through",
		"go through an installer or a set-up window page after page: press one button, such as Next, again and again "
		"until something is reached; uncheck boxes that offer extra software; ask before terms are accepted and before "
		"the installation starts",
		stepThrough, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Going through the pages", tell=VERBATIM)
