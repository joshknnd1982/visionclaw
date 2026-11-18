# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""An audit of NVDA's own source, read without running any of it: every module, class, function and command,
the speech synthesizer drivers, the braille display drivers, and the places where add-ons can listen in
(extension points). It answers "what is there for VisionClaw to know about and reach?" for one NVDA version.

  python tools/audit_nvda_source.py path/to/nvda/source [report.json]

Prints the totals. With a second argument, the whole audit is written there as JSON.
NVDA is copyright NV Access and contributors, GPL v2 or later.
"""
import ast
import json
import os
import sys

EXTENSION_KINDS = ("Action", "Filter", "Decider", "AccumulatingDecider", "Chain")


def text(node):
	if isinstance(node, ast.Call) and node.args:
		node = node.args[0]
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value
	return None


def baseNames(cls):
	names = []
	for base in cls.bases:
		while isinstance(base, ast.Attribute):
			names.append(base.attr)
			base = base.value
		if isinstance(base, ast.Name):
			names.append(base.id)
	return names


def scriptOf(function):
	"""(description, gestures) of a script_ method, from its @script decorator or its docstring."""
	description, gestures = ast.get_docstring(function) or "", []
	for decorator in function.decorator_list:
		if isinstance(decorator, ast.Call) and getattr(decorator.func, "id", getattr(decorator.func, "attr", "")) == "script":
			options = {keyword.arg: keyword.value for keyword in decorator.keywords}
			description = text(options.get("description")) or description
			if text(options.get("gesture")):
				gestures.append(text(options["gesture"]))
			if isinstance(options.get("gestures"), (ast.Tuple, ast.List)):
				gestures += [text(item) for item in options["gestures"].elts if text(item)]
	return description, gestures


def audit(root):
	found = {
		"modules": [], "classes": 0, "functions": 0, "methods": 0, "scripts": [], "synthDrivers": [],
		"brailleDrivers": [], "extensionPoints": [], "unreadable": [],
	}
	for folder, _dirs, files in os.walk(root):
		for name in sorted(files):
			if not name.endswith(".py"):
				continue
			path = os.path.join(folder, name)
			module = os.path.relpath(path, root)[:-3].replace(os.sep, ".")
			if module.endswith(".__init__"):
				module = module[:-9]
			try:
				with open(path, encoding="utf-8") as f:
					tree = ast.parse(f.read())
			except (SyntaxError, UnicodeDecodeError) as e:
				found["unreadable"].append(f"{module}: {e}")
				continue
			found["modules"].append(module)
			for node in tree.body:
				if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
					found["functions"] += 1
				elif isinstance(node, (ast.Assign, ast.AnnAssign)):
					value = node.value
					maker = getattr(value, "func", None)
					if isinstance(maker, ast.Subscript):
						maker = maker.value  # Filter[int]() is a Filter
					kind = getattr(maker, "attr", getattr(maker, "id", ""))
					if isinstance(value, ast.Call) and kind in EXTENSION_KINDS:
						targets = node.targets if isinstance(node, ast.Assign) else [node.target]
						for target in targets:
							if isinstance(target, ast.Name):
								found["extensionPoints"].append(f"{module}.{target.id} ({kind})")
			for node in ast.walk(tree):
				if not isinstance(node, ast.ClassDef):
					continue
				found["classes"] += 1
				bases = baseNames(node)
				if "SynthDriver" in bases and module.startswith(("synthDrivers", "_synthDrivers32")):
					found["synthDrivers"].append(f"{module}.{node.name}")
				if "BrailleDisplayDriver" in bases:
					found["brailleDrivers"].append(f"{module}.{node.name}")
				for item in node.body:
					if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
						continue
					found["methods"] += 1
					if item.name.startswith("script_"):
						description, gestures = scriptOf(item)
						found["scripts"].append({
							"module": module, "class": node.name, "name": item.name[7:],
							"description": description, "gestures": gestures,
						})
	return found


def main(root, target=None):
	found = audit(root)
	scripts = found["scripts"]
	described = [s for s in scripts if s["description"]]
	print(f"Modules: {len(found['modules'])}")
	print(f"Classes: {found['classes']}")
	print(f"Functions outside classes: {found['functions']}")
	print(f"Methods: {found['methods']}")
	print(f"Commands (script_ methods): {len(scripts)}, of which {len(described)} have a description")
	print(f"  in globalCommands: {sum(1 for s in scripts if s['module'] == 'globalCommands')}")
	print(f"  elsewhere: {sum(1 for s in scripts if s['module'] != 'globalCommands')}")
	print(f"Speech synthesizer drivers: {len(found['synthDrivers'])}: {', '.join(found['synthDrivers'])}")
	print(f"Braille display drivers: {len(found['brailleDrivers'])}")
	print(f"Extension points: {len(found['extensionPoints'])}")
	if found["unreadable"]:
		print(f"Could not be read: {found['unreadable']}")
	if target:
		with open(target, "w", encoding="utf-8", newline="\n") as f:
			json.dump(found, f, indent=1)
		print(f"The whole audit is in {target}")


if __name__ == "__main__":
	main(*sys.argv[1:3])
