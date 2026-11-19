# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - which version of something is installed, read from the running NVDA: NVDA's own version
# (buildVersion.version), an add-on's version from its own manifest (addonHandler), VisionClaw's from its manifest,
# and the program in front from what its app module says of it (productName, productVersion). What the user asks the
# version of is read from their own words by plain code (claw/versions.py); the answer is that version alone, and
# where the user says they are new to this, where to find it themselves next time. Nothing is changed and no model
# is asked. Every function that touches NVDA runs on NVDA's main thread.

import addonHandler
import api

from .claw import match, versions
from .claw.fixmatch import plainText
from .claw.tools import VERBATIM, ToolError
from .nvdatools import _safe

addonHandler.initTranslation()

# The add-on's own name in its manifest.
OWN_NAME = "visionClaw"


def ownVersion():
	"""VisionClaw's own version, from the manifest of the copy that is running, not of one waiting to be installed.
	Main thread."""
	copies = [a for a in (_safe(lambda: list(addonHandler.getAvailableAddons()), []) or []) if _safe(lambda a=a: a.name) == OWN_NAME]
	addon = next((a for a in copies if not _safe(lambda a=a: a.isPendingInstall, False)), None)
	if addon is None:
		addon = _safe(addonHandler.getCodeAddon)
	version = _safe(lambda: addon.manifest["version"]) if addon is not None else None
	return version if isinstance(version, str) else ""


def front():
	"""The program in front: (what it is called, its version, its own name in NVDA). Main thread."""
	module = _safe(lambda: api.getForegroundObject().appModule)
	if module is None:
		return "", "", ""
	product = " ".join(str(_safe(lambda: module.productName) or "").split())
	version = " ".join(str(_safe(lambda: module.productVersion) or "").split())
	app = str(_safe(lambda: module.appName) or "").strip()
	return product or app, version, app


def isFront(name, program):
	"""Whether a name the user said is the program in front."""
	said = set(plainText(name).split()) - {"nvda"}
	shown, _version, app = program
	if not said or not (shown or app):
		return False
	return said <= set(plainText(f"{shown} {app}").split()) or match.best(name, [n for n in (shown, app) if n], least=0.8) is not None


def facts(wish):
	"""What is known of each thing the user asked the version of, for versions.answer. Main thread."""
	from . import accesstools
	found = []
	program = None
	for kind, name in wish["things"]:
		if kind == versions.NVDA:
			found.append({"kind": kind, "version": str(_safe(lambda: __import__("buildVersion").version) or "")})
			continue
		if kind == versions.VISIONCLAW:
			found.append({"kind": kind, "version": ownVersion()})
			continue
		if program is None:
			program = front()
		inFront = {"kind": kind, "name": program[0], "version": program[1], "found": True, "program": True}
		if kind == versions.PROGRAM or (wish.get("program") and isFront(name, program)):
			found.append(inFront)
			continue
		# An add-on of that name first: the user's own words decide which one (accesstools._addonOf).
		addon, summary = accesstools._addonOf(name, name)
		if addon is not None:
			found.append({
				"kind": kind, "name": summary, "version": str(_safe(lambda: addon.manifest["version"]) or ""),
				"state": accesstools._addonState(addon), "found": True})
		elif isFront(name, program):
			found.append(inFront)
		else:
			found.append({"kind": kind, "name": name, "found": False, "front": program[0]})
	return found


def register(plugin, add, text, onMain):
	"""Add the tool. add and text are nvdatools' own; onMain runs a function on NVDA's main thread."""

	def versionInfo(task, asked):
		wish = versions.wish(asked) or versions.wish(task.request)
		if wish is None:
			raise ToolError(
				"The words name nothing to tell the version of. Name VisionClaw, NVDA, an add-on, or say this program.")
		# Only where the user says they are new to this, in the request or in what they asked VisionClaw to remember,
		# is more than the version said. The owner, 2026-11-19: "no assuming I want more unless I say I am a beginner".
		remembered = _safe(lambda: [entry.text() for entry in plugin.memories.all()], []) or []
		isBeginner = wish["beginner"] or versions.beginner(task.request, *remembered)
		return versions.answer(onMain(facts, wish), isBeginner)

	add("version_info",
		"say which version of VisionClaw, of NVDA, of one add-on installed in NVDA or of the program in front is "
		"installed here; only the version that was asked for",
		versionInfo, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Finding the version", tell=VERBATIM)
