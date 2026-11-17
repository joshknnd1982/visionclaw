# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Lets tests import the add-on's NVDA-free modules with plain Python.

The add-on package's own __init__.py needs NVDA, so a stand-in package with the same name and folder is
registered instead. After `import harness`, `from visionClaw.claw import catalog` works.
"""
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(ROOT, "addon", "globalPlugins", "visionClaw")
ENGINE_DIR = os.path.join(ROOT, "addon", "engine")

if "visionClaw" not in sys.modules:
	package = types.ModuleType("visionClaw")
	package.__path__ = [PLUGIN_DIR]
	sys.modules["visionClaw"] = package


def visionMateData():
	"""VisionMate's vision data on this computer (model, projector), or None. Used by the live tests."""
	folder = os.path.join(os.environ.get("APPDATA", ""), "nvda", "visionMate", "data")
	core, vision = os.path.join(folder, "core.bin"), os.path.join(folder, "vision.bin")
	return folder if os.path.isfile(core) and os.path.isfile(vision) else None
