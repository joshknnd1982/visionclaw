# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Writes tests/nvda_commands.json: the name, description and keys of every command in NVDA's own
globalCommands.py, read from NVDA's source without running it. The tests use it to check that a request finds
the right command among all the real ones.

  python tools/write_command_fixture.py path/to/nvda/source/globalCommands.py

NVDA is copyright NV Access and contributors, GPL v2 or later; the descriptions are theirs.
"""
import ast
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def text(node):
	"""The text of _("...") or of a plain string, or None."""
	if isinstance(node, ast.Call) and node.args:
		node = node.args[0]
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value
	return None


def main(path):
	with open(path, encoding="utf-8") as f:
		tree = ast.parse(f.read())
	found = []
	for node in ast.walk(tree):
		if not isinstance(node, ast.FunctionDef) or not node.name.startswith("script_"):
			continue
		for decorator in node.decorator_list:
			if not (isinstance(decorator, ast.Call) and getattr(decorator.func, "id", "") == "script"):
				continue
			options = {keyword.arg: keyword.value for keyword in decorator.keywords}
			description = text(options.get("description"))
			if not description:
				continue
			gestures = []
			if "gesture" in options and text(options["gesture"]):
				gestures.append(text(options["gesture"]))
			if isinstance(options.get("gestures"), (ast.Tuple, ast.List)):
				gestures += [text(item) for item in options["gestures"].elts if text(item)]
			category = options.get("category")
			found.append({
				"name": node.name[7:], "description": description,
				"category": getattr(category, "id", "") if category is not None else "", "gestures": gestures,
			})
	target = os.path.join(ROOT, "tests", "nvda_commands.json")
	with open(target, "w", encoding="utf-8", newline="\n") as f:
		json.dump(found, f, indent=1)
		f.write("\n")
	print(f"{len(found)} commands written to {target}")


if __name__ == "__main__":
	main(sys.argv[1])
