# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - one "log" for the add-on's NVDA-side files. Whatever they report goes to NVDA's log as before,
# and to VisionClaw's own log as well (claw/debuglog.py), which is written whatever NVDA's logging level is.
# An error is written there with the place in the code where it happened.

from logHandler import log as _nvda

from .claw import debuglog

AREA = "addon"


class _Both:
	def _own(self, text, kwargs, always=False):
		try:
			if kwargs.get("exc_info"):
				debuglog.error(AREA, text)
			elif always:
				debuglog.log(AREA, text)
			else:
				debuglog.detail(AREA, text)
		except Exception:
			pass

	def debug(self, text, *args, **kwargs):
		self._own(text, kwargs)
		return _nvda.debug(text, *args, **kwargs)

	def debugWarning(self, text, *args, **kwargs):
		self._own(text, kwargs)
		return _nvda.debugWarning(text, *args, **kwargs)

	def info(self, text, *args, **kwargs):
		self._own(text, kwargs, always=True)
		return _nvda.info(text, *args, **kwargs)

	def warning(self, text, *args, **kwargs):
		self._own(f"Warning: {text}", kwargs, always=True)
		return _nvda.warning(text, *args, **kwargs)

	def error(self, text, *args, **kwargs):
		if kwargs.get("exc_info"):
			self._own(text, kwargs)
		else:
			debuglog.error(AREA, text)
		return _nvda.error(text, *args, **kwargs)

	def exception(self, text="", *args, **kwargs):
		debuglog.error(AREA, text)
		return _nvda.exception(text, *args, **kwargs)

	def __getattr__(self, name):
		# Everything else, like isEnabledFor, is NVDA's own.
		return getattr(_nvda, name)


log = _Both()
