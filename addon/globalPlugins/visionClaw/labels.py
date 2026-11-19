# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - remembers names for icons, buttons and every other object without a name, per program and website.
# Names the user gives always win over names a model guessed. The store itself is claw/naming.py's NameStore, which
# keeps the file as VisionClaw 1.12 and older wrote it, so that an older VisionClaw still reads it.

import hashlib

from .claw import naming
from .vclog import log

# Guessed names kept per app. Older ones are dropped first.
MAX_GUESSES_PER_APP = naming.MAX_GUESSES


def imageKey(image):
	"""Identifies a picture of an icon by its pixels."""
	return hashlib.sha1(image.convert("RGB").tobytes() + repr(image.size).encode()).hexdigest()[:20]


class LabelStore(naming.NameStore):
	"""Saved in a small file, so names survive restarts and add-on updates."""

	def __init__(self, path):
		super().__init__(path)
		if getattr(self, "readFailed", False):
			log.warning("VisionClaw: could not read saved names")

	def save(self):
		if not super().save():
			log.warning("VisionClaw: could not save names")
