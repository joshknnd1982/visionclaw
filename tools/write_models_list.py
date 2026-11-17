# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Writes models.json, the list of offered models that is published on VisionClaw's page on GitHub.

The add-on reads that file only when the user presses "Look for newer models" in the models window and says
yes. The list is written from the built-in catalog, so the two can never disagree:

  python tools/write_models_list.py

Run it after every change to CATALOG in addon/globalPlugins/visionClaw/claw/catalog.py, and set LIST_UPDATED
there to the day the catalog was last compared with what the Qwen team has published. tests/test_parts.py
fails while models.json and the catalog differ.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import harness  # noqa: E402,F401
from visionClaw.claw import catalog  # noqa: E402

PATH = os.path.join(ROOT, "models.json")


def text():
	return json.dumps(catalog.publishedList(), indent=1) + "\n"


if __name__ == "__main__":
	with open(PATH, "w", encoding="utf-8", newline="\n") as f:
		f.write(text())
	print(f"Wrote {PATH}: {len(catalog.CATALOG)} models, list of {catalog.LIST_UPDATED}.")
