# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Writes docs/NVDA-OBJECTS.md and tests/nvda_objects.json: every kind of control (role), every state, every class
of object, every kind of browse mode document and program NVDA has its own support for, every way of moving
NVDA has and the keys that do it, and the reasons NVDA says something, all read from NVDA's own source without
running it. VisionClaw's naming of objects without a name (claw/naming.py) sorts every role in this list, and
tests/test_naming.py fails when one is not sorted.

  python tools/write_nvda_objects.py path/to/nvda/source [version]

The source is NVDA's "source" folder, for example from
https://codeload.github.com/nvaccess/nvda/tar.gz/refs/tags/release-2026.3.1. Read it again for a newer NVDA; do
not write any of it from memory. NVDA is copyright NV Access and contributors, GPL v2 or later; the words for
the roles, states and commands are theirs.
"""
import ast
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The command categories of globalCommands.py that are ways of moving or of reading where one is.
MOVING = (
	"SCRCAT_FOCUS", "SCRCAT_OBJECTNAVIGATION", "SCRCAT_TEXTREVIEW", "SCRCAT_SYSTEMCARET", "SCRCAT_BROWSEMODE",
	"SCRCAT_MOUSE", "SCRCAT_TOUCH", "SCRCAT_MATH_NAV",
)


def read(path):
	with open(path, encoding="utf-8") as f:
		return f.read()


def text(node):
	"""The text of _("..."), pgettext("context", "...") or a plain string, or None."""
	if isinstance(node, ast.Call) and node.args:
		node = node.args[-1]
	if isinstance(node, ast.Constant) and isinstance(node.value, str):
		return node.value
	return None


def enumMembers(tree, className):
	"""The names of the members of an enum class, in order."""
	for node in ast.walk(tree):
		if isinstance(node, ast.ClassDef) and node.name == className:
			names = []
			for item in node.body:
				if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
					name = item.targets[0].id
					if name.isupper():
						names.append(name)
			return names
	return []


def labels(tree, dictName, enumName):
	"""{member name: the words NVDA says for it} from a dictionary like _roleLabels."""
	found = {}
	for node in ast.walk(tree):
		target = None
		if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
			target, value = node.target.id, node.value
		elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
			target, value = node.targets[0].id, node.value
		if target != dictName or not isinstance(value, ast.Dict):
			continue
		for key, item in zip(value.keys, value.values):
			if isinstance(key, ast.Attribute) and getattr(key.value, "id", "") == enumName:
				words = text(item)
				if words is not None:
					found[key.attr] = words
	return found


def roleSet(tree, setName):
	for node in ast.walk(tree):
		target = None
		if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
			target, value = node.target.id, node.value
		elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
			target, value = node.targets[0].id, node.value
		if target == setName and isinstance(value, (ast.Set, ast.List, ast.Tuple)):
			return [element.attr for element in value.elts if isinstance(element, ast.Attribute)]
	return []


def baseName(node):
	if isinstance(node, ast.Name):
		return node.id
	if isinstance(node, ast.Attribute):
		return f"{baseName(node.value)}.{node.attr}"
	if isinstance(node, ast.Subscript):
		return baseName(node.value)
	return "?"


def classes(source, folder):
	"""Every class defined in a folder of NVDA's source: (module, class, bases, first line of its docstring)."""
	found = []
	top = os.path.join(source, folder)
	for where, _dirs, files in os.walk(top):
		for name in sorted(files):
			if not name.endswith(".py"):
				continue
			path = os.path.join(where, name)
			module = os.path.relpath(path, source)[:-3].replace(os.sep, ".")
			if module.endswith(".__init__"):
				module = module[:-9]
			try:
				tree = ast.parse(read(path))
			except SyntaxError:
				continue
			for node in tree.body:
				if isinstance(node, ast.ClassDef):
					doc = (ast.get_docstring(node) or "").strip().splitlines()
					found.append((module, node.name, [baseName(b) for b in node.bases], doc[0] if doc else ""))
	return sorted(found)


def gestureMaps(path):
	"""{script name: [keys]} from the __gestures dictionaries of a file, and from @script(gesture=, gestures=)."""
	tree = ast.parse(read(path))
	found = {}
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.endswith("__gestures") for t in node.targets):
			if isinstance(node.value, ast.Dict):
				for key, value in zip(node.value.keys, node.value.values):
					if isinstance(key, ast.Constant) and isinstance(value, ast.Constant) and value.value:
						found.setdefault(value.value, []).append(key.value)
		if isinstance(node, ast.FunctionDef) and node.name.startswith("script_"):
			for decorator in node.decorator_list:
				if isinstance(decorator, ast.Call) and getattr(decorator.func, "id", "") == "script":
					for keyword in decorator.keywords:
						if keyword.arg == "gesture" and isinstance(keyword.value, ast.Constant):
							found.setdefault(node.name[7:], []).append(keyword.value.value)
						elif keyword.arg == "gestures" and isinstance(keyword.value, (ast.List, ast.Tuple)):
							for element in keyword.value.elts:
								if isinstance(element, ast.Constant):
									found.setdefault(node.name[7:], []).append(element.value)
	return found


def scriptDocs(path):
	"""{script name: its description} from @script(description=) and from script_x.__doc__ = _("...")."""
	tree = ast.parse(read(path))
	found = {}
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name.startswith("script_"):
			for decorator in node.decorator_list:
				if isinstance(decorator, ast.Call) and getattr(decorator.func, "id", "") == "script":
					for keyword in decorator.keywords:
						if keyword.arg == "description" and text(keyword.value):
							found[node.name[7:]] = text(keyword.value)
		if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Attribute):
			target = node.targets[0]
			if target.attr == "__doc__" and isinstance(target.value, ast.Name) and target.value.id.startswith("script_"):
				if text(node.value):
					found[target.value.id[7:]] = text(node.value)
	return found


def quickNav(path):
	"""The browse mode quick navigation keys: [(kind, key, what it does)] from the qn(...) calls of browseMode.py."""
	tree = ast.parse(read(path))
	found = []
	for node in ast.walk(tree):
		if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "qn" and node.args:
			kind = node.args[0].value if isinstance(node.args[0], ast.Constant) else "?"
			options = {keyword.arg: keyword.value for keyword in node.keywords}
			key = options.get("key")
			key = key.value if isinstance(key, ast.Constant) else None
			found.append((kind, key, text(options.get("nextDoc")) or ""))
	return found


def globalMoving(path):
	"""[(category, script, description, [keys])] of the ways of moving in globalCommands.py."""
	tree = ast.parse(read(path))
	found = []
	for node in ast.walk(tree):
		if not (isinstance(node, ast.FunctionDef) and node.name.startswith("script_")):
			continue
		for decorator in node.decorator_list:
			if not (isinstance(decorator, ast.Call) and getattr(decorator.func, "id", "") == "script"):
				continue
			options = {keyword.arg: keyword.value for keyword in decorator.keywords}
			category = getattr(options.get("category"), "id", "")
			if category not in MOVING:
				continue
			keys = []
			if isinstance(options.get("gesture"), ast.Constant):
				keys.append(options["gesture"].value)
			if isinstance(options.get("gestures"), (ast.List, ast.Tuple)):
				keys += [e.value for e in options["gestures"].elts if isinstance(e, ast.Constant)]
			found.append((category, node.name[7:], text(options.get("description")) or "", keys))
	return found


def categoryNames(path):
	tree = ast.parse(read(path))
	found = {}
	for node in tree.body:
		if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
			name = node.targets[0].id
			if name.startswith("SCRCAT_") and text(node.value):
				found[name] = text(node.value)
	found.setdefault("SCRCAT_BROWSEMODE", "Browse mode")
	return found


def keyText(gesture):
	"""NVDA's spelling of a key, as NVDA's user guide writes it: "kb:NVDA+control+f" is NVDA+Control+F."""
	kind, _sep, key = gesture.partition(":")
	device = kind.split("(")[0]
	if device != "kb":
		mode = kind[len(device):].strip("()")
		where = {"ts": "touch", "br": "braille"}.get(device, device)
		return f"{where}{' in ' + mode + ' mode' if mode else ''}: {key}"
	parts = []
	for part in key.split("+"):
		lower = part.lower()
		parts.append({"nvda": "NVDA", "control": "Control", "shift": "Shift", "alt": "Alt", "windows": "Windows"}.get(
			lower, part if len(part) > 1 else part.upper()))
	return "+".join(parts) + (" on a laptop" if "laptop" in kind else "")


def scriptWords(script):
	"""A script's name in words, where NVDA gives it no description: "moveByLine_back" is "move by line, back"."""
	spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", script).replace("_", ", ")
	return spaced[:1].upper() + spaced[1:].lower()


def main(source, version=""):
	roleTree = ast.parse(read(os.path.join(source, "controlTypes", "role.py")))
	stateTree = ast.parse(read(os.path.join(source, "controlTypes", "state.py")))
	reasonTree = ast.parse(read(os.path.join(source, "controlTypes", "outputReason.py")))
	roles = enumMembers(roleTree, "Role")
	roleWords = labels(roleTree, "_roleLabels", "Role")
	states = enumMembers(stateTree, "State")
	stateWords = labels(stateTree, "_stateLabels", "State")
	negative = labels(stateTree, "_negativeStateLabels", "State")
	reasons = enumMembers(reasonTree, "OutputReason")
	silent = roleSet(roleTree, "silentRolesOnFocus")
	clickable = roleSet(roleTree, "clickableRoles")
	objectClasses = classes(source, "NVDAObjects")
	documents = classes(source, "virtualBuffers") + [c for c in classes(source, "UIAHandler") if "browseMode" in c[0]]
	programs = sorted(name[:-3] for name in os.listdir(os.path.join(source, "appModules"))
		if name.endswith(".py") and name != "__init__.py")
	categories = categoryNames(os.path.join(source, "globalCommands.py"))
	moving = globalMoving(os.path.join(source, "globalCommands.py"))
	quick = quickNav(os.path.join(source, "browseMode.py"))
	documentKeys = {}
	for name in ("browseMode.py", "cursorManager.py", "documentBase.py", "editableText.py"):
		path = os.path.join(source, name)
		docs = scriptDocs(path)
		for script, keys in gestureMaps(path).items():
			if script.startswith(("nextHeading", "previousHeading")) or script.startswith(("next", "previous")) and any(
				script.endswith(kind[:1].upper() + kind[1:]) for kind, _key, _doc in quick):
				continue  # the quick navigation keys are listed apart
			documentKeys.setdefault(name[:-3], []).append((script, docs.get(script, ""), keys))

	fixture = {
		"nvda": version, "roles": roles, "roleWords": roleWords, "states": states, "stateWords": stateWords,
		"negativeStateWords": negative, "outputReasons": reasons, "silentRolesOnFocus": silent,
		"clickableRoles": clickable, "programs": programs,
		"objectClasses": [f"{module}.{name}" for module, name, _bases, _doc in objectClasses],
		"quickNav": [[kind, key] for kind, key, _doc in quick],
	}
	with open(os.path.join(ROOT, "tests", "nvda_objects.json"), "w", encoding="utf-8") as f:
		json.dump(fixture, f, indent="\t", ensure_ascii=False)
		f.write("\n")

	out = []
	add = out.append
	add("# Everything NVDA knows about objects, and every way of moving among them")
	add("")
	add(f"Read from the source of NVDA {version or '(version not given)'} by `tools/write_nvda_objects.py`; nothing here "
		"was written from memory. The words NVDA says for each role, state and command are NV Access's own (GPL v2 or "
		"later). VisionClaw's naming of objects without a name sorts every role below (`claw/naming.py`), and "
		"`tests/test_naming.py` fails when NVDA has a role it has not sorted. Run the tool again for a newer NVDA.")
	add("")
	add("## What an object is to NVDA")
	add("")
	add("Every control, window, document part and picture NVDA can reach is an object (an NVDAObject). NVDA asks "
		"each one for its name, its role (what kind of control it is), its states (checked, expanded, unavailable "
		"and so on), its value, its description and where it is on the screen. An object without a name is one "
		"whose program gives NVDA nothing to call it: NVDA then says only its role, such as \"button\", or a file "
		"name, such as \"icon_close.svg\". That is what VisionClaw names.")
	add("")
	add("NVDA reaches objects through these accessibility interfaces, each with its own family of classes below: "
		"IAccessible and IAccessible2 (most programs, Chrome, Edge, Firefox), UI Automation (Windows 10 and 11, "
		"Office, modern apps), Java Access Bridge (Java programs), and the window itself (Window: programs that "
		"tell NVDA nothing more).")
	add("")
	add(f"## Roles: {len(roles)} kinds of object")
	add("")
	add("The name in capitals is NVDA's own (`controlTypes.Role`); after it, the words NVDA says. "
		f"Silent on focus (NVDA does not say the role when it gets the focus): {', '.join(silent)}. "
		f"Clickable (NVDA knows how to press them): {', '.join(clickable)}.")
	add("")
	for role in roles:
		add(f"- {role}: {roleWords.get(role, '(no words)')}")
	add("")
	add(f"## States: {len(states)}")
	add("")
	add("NVDA's own name (`controlTypes.State`); the words NVDA says; and, where NVDA has them, the words for the "
		"opposite.")
	add("")
	for state in states:
		words = stateWords.get(state, "(not said)")
		add(f"- {state}: {words}" + (f"; opposite: {negative[state]}" if state in negative else ""))
	add("")
	add(f"## Why NVDA says something: {len(reasons)} reasons")
	add("")
	add("Every time NVDA reports an object or a stretch of text it gives a reason (`controlTypes.OutputReason`). "
		"VisionClaw names an object without a name when it is reported for focus, the caret, quick navigation, "
		"the mouse, the review cursor and object navigation.")
	add("")
	add(", ".join(reasons) + ".")
	add("")
	add("## Ways of moving, and their keys")
	add("")
	add("From NVDA's `globalCommands.py`, the commands of the categories that move or read where one is. Keys are "
		"the desktop layout's where a command has several; the laptop layout and touch gestures are listed too.")
	add("")
	byCategory = {}
	for category, script, description, keys in moving:
		byCategory.setdefault(category, []).append((script, description, keys))
	for category in MOVING:
		if category not in byCategory:
			continue
		add(f"### {categories.get(category, category)}")
		add("")
		for script, description, keys in sorted(byCategory[category]):
			add(f"- {description or scriptWords(script)}" + (f" ({', '.join(keyText(k) for k in keys)})" if keys else " (no key)"))
		add("")
	add("### Browse mode quick navigation")
	add("")
	add("A letter moves to the next one, Shift and the letter to the one before (`browseMode.py`). Kinds without a "
		"letter have a key only when one is given in NVDA's Input Gestures dialog.")
	add("")
	for kind, key, doc in quick:
		add(f"- {kind}: {key.upper() if key else 'no key'}" + (f", {doc}" if doc else ""))
	add("")
	titles = {
		"browseMode": "Browse mode and focus mode", "cursorManager": "Reading a document with the arrow keys",
		"documentBase": "Tables in documents", "editableText": "Edit fields and documents with a caret",
	}
	for module in ("browseMode", "cursorManager", "documentBase", "editableText"):
		entries = documentKeys.get(module)
		if not entries:
			continue
		add(f"### {titles[module]}")
		add("")
		for script, doc, keys in sorted(entries):
			add(f"- {doc or scriptWords(script)}: {', '.join(keyText(k) for k in keys)}")
		add("")
	add("### Moving that belongs to Windows and the program")
	add("")
	add("Tab and Shift+Tab move the focus to the next and the one before; Control+Tab and Control+Shift+Tab move "
		"between tabs of a window; Alt+Tab between windows; the arrow keys inside lists, trees, menus and grids. NVDA "
		"does not handle these keys: the program moves the focus and NVDA reports the object that gets it, so for "
		"NVDA they are all focus moves. In browse mode NVDA handles the arrow keys itself, and Tab moves the focus "
		"inside the page.")
	add("")
	add(f"## Browse mode documents: {len(documents)} classes")
	add("")
	add("Browse mode reads a page or document from NVDA's own copy of it (a virtual buffer), or straight from UI "
		"Automation. VisionClaw gives names to NVDA's copy of a page, so they are read without leaving browse mode.")
	add("")
	for module, name, bases, doc in documents:
		add(f"- {module}.{name}" + (f" ({', '.join(bases)})" if bases else "") + (f": {doc}" if doc else ""))
	add("")
	add(f"## Classes of objects: {len(objectClasses)}")
	add("")
	add("Every class in NVDA's `NVDAObjects` package, with the classes it is built on. NVDA chooses several of "
		"them for one object, and add-ons, VisionClaw among them, can add their own (an overlay class).")
	add("")
	for module, name, bases, doc in objectClasses:
		add(f"- {module}.{name}" + (f" ({', '.join(bases)})" if bases else "") + (f": {doc}" if doc else ""))
	add("")
	add(f"## Programs NVDA has its own support for: {len(programs)}")
	add("")
	add("NVDA's app modules (`appModules`), named by the program's file name. Other programs are read with the "
		"general support above. VisionClaw's names are kept for each program by this same name.")
	add("")
	add(", ".join(programs) + ".")
	add("")
	with open(os.path.join(ROOT, "docs", "NVDA-OBJECTS.md"), "w", encoding="utf-8") as f:
		f.write("\n".join(out))
	print(f"{len(roles)} roles, {len(states)} states, {len(reasons)} reasons, {len(objectClasses)} classes, "
		f"{len(documents)} document classes, {len(programs)} programs, {len(moving)} commands, {len(quick)} quick keys")


if __name__ == "__main__":
	if len(sys.argv) < 2:
		sys.exit(__doc__)
	main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
