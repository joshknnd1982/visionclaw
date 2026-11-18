# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - shows what is new when the add-on is installed or updated, and keeps the data folder when NVDA
# deletes the add-on's folder.
#
# Everything VisionClaw keeps is in the folder "data" inside the add-on's folder (claw/portable.py). NVDA
# deletes that folder at the next start after VisionClaw was updated or removed, and calls onUninstall just
# before. There the data folder is moved into the newer version's folder, or, when VisionClaw was removed,
# into NVDA's configuration folder, where a later install takes it in again. Nothing is deleted.

import importlib.util
import os

import addonHandler
import gui
import wx

addonHandler.initTranslation()


def _showWhatsNew(version, changelog):
	# Translators: Title of the window shown after VisionClaw is installed or updated. {version} is the version.
	title = _("What's new in VisionClaw {version}").format(version=version)
	gui.mainFrame.prePopup()
	try:
		gui.messageBox(changelog, title, wx.OK | wx.ICON_INFORMATION)
	finally:
		gui.mainFrame.postPopup()


def onInstall():
	manifest = addonHandler.getCodeAddon().manifest
	changelog = (manifest.get("changelog") or "").strip()
	if changelog:
		wx.CallAfter(_showWhatsNew, manifest["version"], changelog)


def _portable(addonDir):
	"""claw/portable.py of this add-on, loaded by its path: it needs nothing of NVDA."""
	path = os.path.join(addonDir, "globalPlugins", "visionClaw", "claw", "portable.py")
	spec = importlib.util.spec_from_file_location("visionClawPortableTask", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def onUninstall():
	from logHandler import log
	try:
		import globalVars
		addonDir = os.path.dirname(os.path.abspath(__file__))
		went = _portable(addonDir).carryOver(addonDir, globalVars.appArgs.configPath)
		if went:
			log.info(f"VisionClaw: its data folder was moved to {went} before NVDA deleted {addonDir}")
	except Exception:
		log.error("VisionClaw: the data folder could not be moved before the add-on's folder is deleted", exc_info=True)
