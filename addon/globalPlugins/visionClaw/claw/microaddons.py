# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - small NVDA add-ons written by the coder model: writing them, checking them before they run,
# keeping them, and packaging one as a normal .nvda-addon file.
# The check stops the mistakes small models make and code that could do damage by accident. It is not a
# sandbox: generated code runs inside NVDA once the user has said yes. No NVDA dependencies.

import ast
import json
import os
import re
import time
import zipfile

from . import prompts
from .llm import LLMError, clip
from .tools import ToolError

# Modules generated add-ons may not use: they start programs, reach the network, or change files and the system.
FORBIDDEN_MODULES = frozenset((
	"subprocess", "socket", "urllib", "http", "ftplib", "smtplib", "requests", "ctypes", "shutil", "winreg",
	"multiprocessing", "importlib", "pickle", "marshal", "tempfile", "webbrowser", "asyncio", "ssl", "pathlib",
	"glob", "sys", "builtins", "code", "pty", "signal",
))
FORBIDDEN_CALLS = frozenset(("eval", "exec", "compile", "__import__", "open", "input", "globals", "setattr", "delattr"))
FORBIDDEN_OS = frozenset((
	"system", "remove", "unlink", "rmdir", "removedirs", "rename", "replace", "popen", "startfile", "kill",
	"makedirs", "mkdir", "chmod", "putenv", "chdir",
))
# A small add-on is a few dozen lines. More than this means the model has lost its way.
MAX_LINES = 120
TEMPLATE = '''import globalPluginHandler
import api
import ui
from scriptHandler import script


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	@script(description="Says the name of the focused control", gesture="kb:NVDA+shift+f9")
	def script_sayName(self, gesture):
		obj = api.getFocusObject()
		ui.message(obj.name or "no name")

	def event_gainFocus(self, obj, nextHandler):
		try:
			if obj.appModule.appName == "notepad" and not obj.name:
				ui.message("text area")
		except Exception:
			pass
		nextHandler()
'''
# The examples shown to the coder. Each shows one thing only: a small model copies whatever it is shown, so an
# example that did two things put both into every add-on.
EXAMPLE_KEY = '''import globalPluginHandler
import api
import ui
from scriptHandler import script


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	@script(description="Says the name of the focused control", gesture="kb:NVDA+shift+f9")
	def script_sayName(self, gesture):
		obj = api.getFocusObject()
		ui.message(obj.name or "no name")
'''
EXAMPLE_EVENT = '''import globalPluginHandler
import controlTypes
import tones


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def event_gainFocus(self, obj, nextHandler):
		try:
			if obj.role == controlTypes.Role.BUTTON:
				tones.beep(660, 60)
		except Exception:
			pass
		nextHandler()
'''
_SYSTEM = (
	"You write small add-ons for the NVDA screen reader in Python. "
	"Answer with one complete Python file inside a ```python block, and nothing else.\n"
	"Rules:\n"
	"- Do exactly what is asked and nothing more. Never add a key command or an event that was not asked for.\n"
	"- Keep it short: 10 to 30 lines. No extra cases, no long comments, no imports you do not use.\n"
	"- The file defines class GlobalPlugin(globalPluginHandler.GlobalPlugin).\n"
	"- Speak with ui.message(\"text\"). Beep with tones.beep(frequency, milliseconds).\n"
	"- When the request names a key: write a method script_something(self, gesture) with the decorator "
	"@script(description=\"...\", gesture=\"kb:NVDA+shift+k\"), using the key that was asked for.\n"
	"- When the request wants something to happen by itself (when, whenever, each time): write an event, a "
	"method like event_gainFocus(self, obj, nextHandler). It must call nextHandler() at the end, and wrap its "
	"own work in try/except so NVDA keeps working.\n"
	"- Compare the kind of a control with controlTypes.Role, like obj.role == controlTypes.Role.LINK. "
	"Never compare it with a text like \"link\".\n"
	"- Limit the add-on to one program, with obj.appModule.appName == \"name\", only when the request says so.\n"
	"- Import every module you use. Import only NVDA modules and these: re, time, datetime, json, math, "
	"threading, collections, os.path.\n"
	"- Never use subprocess, the internet, eval, exec, open, or anything that deletes or writes files.\n"
	"Example of a key command, for a request that names a key:\n```python\n" + EXAMPLE_KEY + "```\n"
	"Example of an event, for a request that wants something to happen by itself:\n```python\n" + EXAMPLE_EVENT + "```"
)
# Words in a request that ask for something to happen by itself, and words that ask for a key.
_WANTS_EVENT = re.compile(
	r"\b(when|whenever|every time|each time|automatic(ally)?|by itself|as soon as|on focus|gets? the focus|"
	r"changes?|appears?|opens?|announce|tell me if|warn|alert|watch|monitor)\b", re.IGNORECASE)
_WANTS_KEY = re.compile(r"\b(press|key|keys|hot ?key|shortcut|nvda\s*\+|control\s*\+|alt\s*\+|shift\s*\+)", re.IGNORECASE)
# "when I press ..." asks for a key, not for something that happens by itself.
_ON_KEY = re.compile(r"\b(when|whenever|every time|each time|as soon as)\s+(i|you|the user)\s+(press|hit|push|use|type)\b[^,.;]*",
	re.IGNORECASE)
# Kinds of control as small models write them, and what NVDA calls them.
_ROLES = {
	"link": "LINK", "button": "BUTTON", "checkbox": "CHECKBOX", "check box": "CHECKBOX", "edit": "EDITABLETEXT",
	"editable text": "EDITABLETEXT", "edit field": "EDITABLETEXT", "list": "LIST", "list item": "LISTITEM",
	"listitem": "LISTITEM", "menu item": "MENUITEM", "menuitem": "MENUITEM", "combo box": "COMBOBOX",
	"combobox": "COMBOBOX", "radio button": "RADIOBUTTON", "radiobutton": "RADIOBUTTON", "graphic": "GRAPHIC",
	"image": "GRAPHIC", "heading": "HEADING", "tab": "TAB", "slider": "SLIDER", "dialog": "DIALOG", "window": "WINDOW",
}
_THIS_PROGRAM = re.compile(r"\b(this|the current|that) (program|app|application|window|game)\b|\bhere\b|\bin it\b",
	re.IGNORECASE)


def checkAgainst(source, purpose, facts=""):
	"""Problems that show the code does something other than what was asked: something that happens by itself
	though nothing automatic was asked for, a key nobody asked for, a limit to a program the request never
	named, a control's kind compared the wrong way. Sentences a model can act on. Empty if none.
	facts is what is known about where the user is; a program named there may be meant by "this program"."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return []
	problems = []
	events, scripts = _unasked(tree, purpose, allOfThem=True)
	if events and not _wantsEvent(purpose):
		problems.append(
			f"The request does not ask for anything to happen by itself. Remove {', '.join(events)} completely.")
	if scripts and not _WANTS_KEY.search(purpose):
		problems.append(f"The request does not ask for a key command. Remove {', '.join(scripts)} completely.")
	if not events and not scripts:
		problems.append("The add-on does nothing: it has no key command and no event. Write what was asked for.")
	wanted = purpose.lower()
	mayLimit = bool(_THIS_PROGRAM.search(purpose))
	limited = set()
	for node in ast.walk(tree):
		if not isinstance(node, ast.Compare):
			continue
		sides = [node.left] + list(node.comparators)
		texts = [side.value for side in sides if isinstance(side, ast.Constant) and isinstance(side.value, str)]
		for side in sides:
			texts += [e.value for e in getattr(side, "elts", []) if isinstance(e, ast.Constant) and isinstance(e.value, str)]
		attrs = {getattr(side, "attr", "") for side in sides}
		# The program's name may have been put in a variable first: appName = obj.appModule.appName
		if any(isinstance(side, ast.Name) and "app" in side.id.lower() for side in sides):
			attrs.add("appName")
		if "role" in attrs and texts:
			problems.append(
				f"The kind of a control is compared with the text \"{texts[0]}\". Compare it with controlTypes.Role, "
				f"like obj.role == controlTypes.Role.{texts[0].upper().replace(' ', '')}, and import controlTypes.")
		if "appName" in attrs:
			limited.update(text.lower() for text in texts)
			for program in texts:
				named = program.lower() in wanted or (mayLimit and program.lower() in facts.lower())
				if not named:
					problems.append(
						f"The request does not say it is only for the program {program}. Remove the appName check, "
						"or the add-on will not work anywhere else.")
	# The other way round: the request is for one program, but the code works everywhere.
	program = _programAsked(purpose, facts)
	if program and program.lower() not in limited:
		problems.append(
			f"The request is only for the program {program}. Act only when "
			f"api.getFocusObject().appModule.appName == \"{program}\".")
	return list(dict.fromkeys(problems))


def _limits(source):
	"""The programs an add-on's code checks for, in lower case."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return set()
	found = set()
	for node in ast.walk(tree):
		if not isinstance(node, ast.Compare):
			continue
		sides = [node.left] + list(node.comparators)
		if not any(getattr(side, "attr", "") == "appName"
				or (isinstance(side, ast.Name) and "app" in side.id.lower()) for side in sides):
			continue
		for side in sides:
			for item in [side] + list(getattr(side, "elts", [])):
				if isinstance(item, ast.Constant) and isinstance(item.value, str):
					found.add(item.value.lower())
	return found


def _programAsked(purpose, facts):
	"""The program the request is limited to: the one the user is in, if the request names it."""
	here = re.search(r"Program: ([\w.-]+?)\.?(\s|$)", facts or "")
	if here and re.search(rf"\b{re.escape(here.group(1))}\b", purpose, re.IGNORECASE):
		return here.group(1)
	return ""


def _limitTo(source, program):
	"""Make every key command and event of an add-on act only in one program, by putting a check at the start
	of each. In another program a key is passed on to that program, and an event to NVDA."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return source
	lines = source.splitlines(keepends=True)
	inserts = []
	for node in ast.walk(tree):
		if not isinstance(node, ast.FunctionDef) or not node.name.startswith(("script_", "event_")) or not node.body:
			continue
		first = node.body[0]
		indent = lines[first.lineno - 1][:first.col_offset]
		step = "\t" if indent.startswith("\t") else "    "
		if node.name.startswith("script_"):
			check = [
				f"{indent}if api.getFocusObject().appModule.appName != \"{program}\":\n",
				f"{indent}{step}gesture.send()\n", f"{indent}{step}return\n",
			]
		else:
			check = [
				f"{indent}if getattr(getattr(obj, \"appModule\", None), \"appName\", None) != \"{program}\":\n",
				f"{indent}{step}nextHandler()\n", f"{indent}{step}return\n",
			]
		inserts.append((first.lineno - 1, check))
	for at, check in sorted(inserts, reverse=True):
		lines[at:at] = check
	source = "".join(lines)
	if inserts and not re.search(r"^\s*import api\b", source, re.MULTILINE):
		source = "import api\n" + source
	return source


def _wantsEvent(purpose):
	return bool(_WANTS_EVENT.search(_ON_KEY.sub("", purpose)))


def _unasked(tree, purpose, allOfThem=False):
	"""The events and key commands in the code, as (events, scripts): all of them, or only those that the
	request did not ask for."""
	events = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("event_")]
	scripts = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("script_")]
	if allOfThem:
		return [n.name for n in events], [n.name for n in scripts]
	return ([] if _wantsEvent(purpose) else events), ([] if _WANTS_KEY.search(purpose) else scripts)


def salvage(source):
	"""A file that was cut off in the middle, because the model went on too long, is cut back to its last line
	that leaves a complete program. Nothing is changed if the file is complete or cannot be saved this way."""
	try:
		ast.parse(source)
		return source
	except SyntaxError:
		pass
	lines = source.splitlines(keepends=True)
	for end in range(len(lines) - 1, 5, -1):
		candidate = "".join(lines[:end])
		try:
			tree = ast.parse(candidate)
		except SyntaxError:
			continue
		# Worth keeping only if the add-on's class, with something in it, is still there.
		if any(isinstance(n, ast.ClassDef) and n.name == "GlobalPlugin" and any(
				isinstance(f, ast.FunctionDef) for f in n.body) for n in tree.body):
			return candidate
		break
	return source


def tidy(source, purpose, facts=""):
	"""Correct by plain rules what needs no model: take out events and key commands the request did not ask
	for, write a control's kind the way NVDA needs it, and limit the add-on to the program the request names. A small model keeps what it once wrote however often
	it is told, so code does this. Returns the source, changed or not; code that would be left empty is not
	touched, so that the coder is told instead."""
	source = salvage(source)
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return source
	lines = source.splitlines(keepends=True)
	events, scripts = _unasked(tree, purpose)
	total = len(_unasked(tree, purpose, allOfThem=True)[0]) + len(_unasked(tree, purpose, allOfThem=True)[1])
	remove = events + scripts
	if remove and len(remove) < total:
		for node in sorted(remove, key=lambda n: -n.lineno):
			first = min([d.lineno for d in node.decorator_list] + [node.lineno])
			del lines[first - 1:node.end_lineno]
		source = "".join(lines)
		try:
			tree = ast.parse(source)
		except SyntaxError:
			return "".join(source)
		lines = source.splitlines(keepends=True)
	# obj.role == "link" never matches; NVDA's kinds are controlTypes.Role.LINK and so on.
	changes = []
	for node in ast.walk(tree):
		if not isinstance(node, ast.Compare):
			continue
		sides = [node.left] + list(node.comparators)
		if not any(getattr(side, "attr", "") == "role" for side in sides):
			continue
		for side in sides:
			if isinstance(side, ast.Constant) and isinstance(side.value, str) and side.lineno == side.end_lineno:
				role = _ROLES.get(side.value.lower().strip())
				if role:
					changes.append((side.lineno, side.col_offset, side.end_col_offset, f"controlTypes.Role.{role}"))
	for lineno, start, end, text in sorted(changes, reverse=True):
		line = lines[lineno - 1]
		lines[lineno - 1] = line[:start] + text + line[end:]
	source = "".join(lines)
	if changes and not re.search(r"^\s*import controlTypes\b", source, re.MULTILINE):
		source = "import controlTypes\n" + source
	program = _programAsked(purpose, facts)
	if program and program.lower() not in _limits(source):
		source = _limitTo(source, program)
	return _addImports(_passEventsOn(source))


# NVDA's modules that add-ons use most, each imported by its own name.
_MODULES = ("ui", "api", "tones", "speech", "controlTypes", "config", "globalPluginHandler", "braille", "wx",
	"winUser", "mouseHandler", "textInfos", "scriptHandler")


def _passEventsOn(source):
	"""An event that forgets to pass the event on would silence NVDA for it: add nextHandler() at its end."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return source
	lines = source.splitlines(keepends=True)
	inserts = []
	for node in ast.walk(tree):
		if (isinstance(node, ast.FunctionDef) and node.name.startswith("event_") and node.body
				and "nextHandler" in [a.arg for a in node.args.args]
				and not any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "nextHandler" for c in ast.walk(node))):
			indent = lines[node.body[0].lineno - 1][:node.body[0].col_offset]
			inserts.append((node.end_lineno, f"{indent}nextHandler()\n"))
	for at, line in sorted(inserts, reverse=True):
		if at <= len(lines) and not lines[at - 1].endswith("\n"):
			lines[at - 1] += "\n"
		lines[at:at] = [line]
	return "".join(lines)


def _addImports(source):
	"""Import the NVDA modules the code uses but forgot to import."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return source
	imported = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			imported.update(alias.name.split(".")[0] for alias in node.names)
			imported.update(alias.asname for alias in node.names if alias.asname)
		elif isinstance(node, ast.ImportFrom):
			imported.add((node.module or "").split(".")[0])
			imported.update(alias.asname or alias.name for alias in node.names)
	used = {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
	missing = [f"import {module}\n" for module in _MODULES if module in used and module not in imported]
	if any(isinstance(n, ast.Name) and n.id == "script" for n in ast.walk(tree)) and "script" not in imported:
		missing.append("from scriptHandler import script\n")
	return "".join(missing) + source


_REVIEW_SCHEMA = {
	"type": "object",
	"properties": {"ok": {"type": "boolean"}, "problem": {"type": "string", "maxLength": 260}},
	"required": ["ok", "problem"],
}
_REVIEW_SYSTEM = (
	"You review a small NVDA screen reader add-on written by another model. Compare the code with what was asked. "
	"Say ok=true if the code would do what was asked. Say ok=false only for a real fault: it does something "
	"else, it misses a part, or it would raise an error. Name the fault in one sentence."
)
_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


def slug(name):
	"""A safe file and module name from any name."""
	text = re.sub(r"[^A-Za-z0-9]+", "_", str(name or "")).strip("_").lower()[:40]
	if not text or text[0].isdigit():
		text = "helper_" + text
	return text.rstrip("_")


def extractCode(text):
	"""The Python file from a model's answer."""
	blocks = _FENCE.findall(text or "")
	if blocks:
		return max(blocks, key=len).strip() + "\n"
	# No closing fence: the answer was cut off, or the model left the fences out.
	text = re.sub(r"^```(?:python|py)?\s*\n", "", (text or "").strip())
	return text.strip() + "\n"


def check(source):
	"""Problems that must be fixed before the code may run, as sentences a model can act on. Empty if none."""
	try:
		tree = ast.parse(source)
	except SyntaxError as e:
		return [f"Syntax error on line {e.lineno}: {e.msg}."]
	problems = []
	plugin = None
	for node in tree.body:
		if isinstance(node, ast.ClassDef) and node.name == "GlobalPlugin":
			plugin = node
	if plugin is None:
		problems.append("The file must define class GlobalPlugin(globalPluginHandler.GlobalPlugin).")
	elif not any(getattr(b, "attr", getattr(b, "id", "")) == "GlobalPlugin" for b in plugin.bases):
		problems.append("class GlobalPlugin must inherit from globalPluginHandler.GlobalPlugin.")
	imported = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Import):
			names = [alias.name for alias in node.names]
		elif isinstance(node, ast.ImportFrom):
			names = [node.module or ""]
		else:
			names = []
		for name in names:
			imported.add(name.split(".")[0])
			if name.split(".")[0] in FORBIDDEN_MODULES:
				problems.append(f"The module {name} is not allowed. Remove it.")
		if isinstance(node, ast.Call):
			fn = node.func
			if isinstance(fn, ast.Name) and fn.id in FORBIDDEN_CALLS:
				problems.append(f"{fn.id}() is not allowed. Remove it.")
			elif (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "os"
					and (fn.attr in FORBIDDEN_OS or fn.attr.startswith(("exec", "spawn")))):
				problems.append(f"os.{fn.attr}() is not allowed. Remove it.")
		if isinstance(node, ast.FunctionDef):
			args = [a.arg for a in node.args.args]
			if node.name.startswith("event_"):
				if "nextHandler" not in args:
					problems.append(f"{node.name} must take (self, obj, nextHandler).")
				elif not any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "nextHandler" for c in ast.walk(node)):
					problems.append(f"{node.name} must call nextHandler() at the end.")
			if node.name.startswith("script_") and args != ["self", "gesture"]:
				problems.append(f"{node.name} must take exactly (self, gesture).")
		if isinstance(node, ast.keyword) and node.arg == "gesture" and isinstance(node.value, ast.Constant):
			if not str(node.value.value).startswith(("kb:", "br(", "ts:")):
				problems.append(f"The gesture \"{node.value.value}\" must start with kb:, for example kb:NVDA+shift+k.")
	# Names used as modules but never imported are the commonest mistake of small models.
	used = {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
	for module in ("ui", "api", "tones", "speech", "controlTypes", "config", "globalPluginHandler", "braille", "wx",
			"winUser", "mouseHandler", "textInfos", "scriptHandler"):
		if module in used and module not in imported:
			problems.append(f"{module} is used but not imported. Add: import {module}")
	if any(isinstance(n, ast.Name) and n.id == "script" for n in ast.walk(tree)) and "scriptHandler" not in imported:
		problems.append("script is used but not imported. Add: from scriptHandler import script")
	return list(dict.fromkeys(problems))


def gestures(source):
	"""The key commands an add-on defines, as (keys, description)."""
	found = []
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return found
	for node in ast.walk(tree):
		if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "script":
			keys = {k.arg: k.value.value for k in node.keywords if isinstance(k.value, ast.Constant)}
			if keys.get("gesture"):
				found.append((str(keys["gesture"]).replace("kb:", ""), str(keys.get("description", ""))))
	return found


def _writer(params):
	"""What the model that writes the code is called: "the model" when one model does both jobs."""
	return "model" if getattr(params, "oneModel", False) else "coder model"


def _generate(llm, role, user, params, purpose=""):
	# Who the add-on is for, the user's own instructions and language come with every writing and repair.
	answer = llm.text(
		role, prompts.coding(_SYSTEM, purpose), user, maxTokens=params.codeTokens, reasoning=params.reasoning, temperature=0,
		code=True)
	return extractCode(answer)


def write(llm, task, purpose, facts, notes, params, coder, reviewer):
	"""Have the coder model write an add-on, fix what the check finds, and let the other model review it.
	facts: what is known about the user's situation. notes: knowledge about NVDA that fits the purpose.
	Returns the source. Raises ToolError if no version passes the check."""
	user = f"Write an NVDA add-on that does this: {clip(purpose, 700)}\n"
	if facts:
		user += f"What is known:\n{clip(facts, 900)}\n"
	if notes:
		user += f"Notes about NVDA that may help:\n{clip(notes, 1600)}\n"
	task.emit("detail", f"The {_writer(params)} is writing the add-on.")
	return _settle(llm, task, purpose, _generate(llm, coder, user, params, purpose), params, coder, reviewer, notes,
		facts)


def fix(llm, task, purpose, source, problems, notes, params, coder, reviewer, facts=""):
	"""Have the coder model debug an add-on that fails or does the wrong thing. problems say what went wrong:
	the error NVDA reported and where, and what the user says. Returns the corrected source, checked and
	reviewed like a new add-on. Raises ToolError if no version passes the check."""
	task.emit("detail", f"The {_writer(params)} is debugging the add-on: " + clip(problems[0], 240))
	return _settle(llm, task, purpose, repair(llm, coder, purpose, source, problems, params, notes), params, coder,
		reviewer, notes, facts)


def _settle(llm, task, purpose, source, params, coder, reviewer, notes="", facts=""):
	"""Check the code, compare it with what was asked for, have the other model review it, and send it back to
	the coder until all three pass. The checks decide; the reviewing model only advises. If it still has a
	doubt when the tries are used up, code that passes every check is kept, and the doubt is told to the user
	(task.codeDoubt) before the add-on is turned on."""
	task.codeDoubt = ""
	doubt = ""
	reviews = params.codeReviews
	for attempt in range(params.codeRepairs + 1):
		task.check()
		source = tidy(source, purpose, facts)
		problems = check(source) or checkAgainst(source, purpose, facts)
		if not problems and source.count("\n") > MAX_LINES:
			problems = [f"The file is far too long for what was asked. Write it again in under {MAX_LINES // 2} lines."]
		if not problems and reviews > 0:
			reviews -= 1
			try:
				verdict = llm.json(
					reviewer, prompts.coding(_REVIEW_SYSTEM, purpose), f"Asked for: {clip(purpose, 500)}\nCode:\n{clip(source, 5000)}",
					_REVIEW_SCHEMA, maxTokens=120, reasoning=params.reasoning,
				)
			except LLMError:
				verdict = {"ok": True}
			fault = " ".join(str(verdict.get("problem") or "").split())
			# With one model for both jobs, the review is that model reading its own code again.
			one = getattr(params, "oneModel", False)
			if not verdict.get("ok") and fault:
				task.emit("talk", (
					f"The model read its own code again and found a fault: {fault}" if one
					else f"The reviewing model found a fault in the code: {fault}"))
				problems = [fault]
				doubt = fault
			else:
				task.emit("talk", (
					"The model read its own code again: no fault found." if one
					else "The reviewing model checked the code: no fault found."))
				doubt = ""
		if not problems:
			task.codeDoubt = doubt
			return source
		if attempt == params.codeRepairs:
			break
		task.emit("detail", "Fixing the code: " + " ".join(problems[:4]))
		source = repair(llm, coder, purpose, source, problems, params, notes)
	source = tidy(source, purpose, facts)
	left = check(source) or checkAgainst(source, purpose, facts)
	if not left and source.count("\n") <= MAX_LINES:
		task.codeDoubt = doubt
		return source
	if not left:
		left = ["It is far too long for what was asked."]
	raise ToolError(f"The {_writer(params)} could not write code that passes the checks: " + " ".join(left[:3]))


def repair(llm, role, purpose, source, problems, params, notes=""):
	"""Have the coder model fix its add-on. problems are sentences, or an error message from NVDA."""
	user = (
		f"This NVDA add-on should do this: {clip(purpose, 500)}\n```python\n{clip(source, 5000)}\n```\n"
		"It has these problems:\n" + "\n".join(f"- {clip(p, 600)}" for p in problems[:6])
	)
	if notes:
		user += f"\nNotes about NVDA that may help:\n{clip(notes, 1200)}"
	user += "\nFind the cause, and write the whole corrected file."
	return _generate(llm, role, user, params, purpose)


# What an add-on reacts to, in plain words, by the name of the event in its code.
_EVENT_WORDS = {
	"gainFocus": "when the focus moves to another control",
	"loseFocus": "when a control loses the focus",
	"foreground": "when another window comes to the front",
	"nameChange": "when the name of a control changes",
	"valueChange": "when a value changes, such as a progress bar or a slider",
	"stateChange": "when a control's state changes, such as checked or pressed",
	"descriptionChange": "when the description of a control changes",
	"typedCharacter": "each time you type a character",
	"becomeNavigatorObject": "when you move with object navigation",
	"caret": "when the cursor moves in a text",
	"show": "when something appears on the screen",
	"alert": "when a program shows an alert",
	"liveRegionChange": "when a part of a page or window that updates itself changes",
	"UIA_notification": "when a program sends a notification to be announced",
}


def describe(source):
	"""What an add-on does, as plain sentences found by checking its code, for someone who cannot read code.
	These are facts about the code, not the coder's claims: its keys, what it reacts to, the programs it
	names, and whether it speaks, beeps, presses keys or clicks."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return []
	facts = []
	for keys, text in gestures(source):
		facts.append(f"It adds the key {keys}" + (f": {text.rstrip('.')}." if text else "."))
	for node in ast.walk(tree):
		if isinstance(node, ast.FunctionDef) and node.name.startswith("event_"):
			what = _EVENT_WORDS.get(node.name[6:], f"on NVDA's event {node.name[6:]}")
			facts.append(f"It acts by itself {what}.")
	programs = set()
	for node in ast.walk(tree):
		if isinstance(node, ast.Compare) and any(getattr(side, "attr", "") == "appName"
				for side in [node.left] + list(node.comparators)):
			for side in [node.left] + list(node.comparators):
				if isinstance(side, ast.Constant) and isinstance(side.value, str):
					programs.add(side.value)
				for item in getattr(side, "elts", []):
					if isinstance(item, ast.Constant) and isinstance(item.value, str):
						programs.add(item.value)
	facts.append(
		f"It works only in: {', '.join(sorted(programs))}." if programs else "It is not limited to one program.")
	calls = set()
	said = []
	for node in ast.walk(tree):
		if isinstance(node, ast.Call):
			name = getattr(node.func, "attr", getattr(node.func, "id", ""))
			owner = getattr(getattr(node.func, "value", None), "id", "")
			calls.add((owner, name))
			if (owner, name) == ("ui", "message") and node.args and isinstance(node.args[0], ast.Constant):
				said.append(str(node.args[0].value))
	if said:
		facts.append("It can say: " + "; ".join(clip(text, 60) for text in said[:4]) + ".")
	elif ("ui", "message") in calls or any(owner == "speech" for owner, _n in calls):
		facts.append("It speaks.")
	if ("tones", "beep") in calls:
		facts.append("It beeps.")
	if any(name in ("send", "fromName") or owner == "keyboardHandler" for owner, name in calls) and "KeyboardInputGesture" in source:
		facts.append("It presses keys for you.")
	if any(owner in ("mouseHandler", "winUser") for owner, _n in calls):
		facts.append("It moves or clicks the mouse.")
	return list(dict.fromkeys(facts))


class Store:
	"""Generated add-ons on disk: one folder each, with plugin.py and meta.json."""

	def __init__(self, folder):
		self.folder = folder

	def _dir(self, name):
		return os.path.join(self.folder, slug(name))

	def path(self, name):
		return os.path.join(self._dir(name), "plugin.py")

	def save(self, name, source, purpose="", enabled=True, repairs=0):
		"""repairs counts how often the add-on was corrected after failing in NVDA."""
		os.makedirs(self._dir(name), exist_ok=True)
		with open(self.path(name), "w", encoding="utf-8") as f:
			f.write(source)
		meta = {"name": slug(name), "title": str(name), "purpose": purpose, "enabled": enabled,
			"created": time.time(), "repairs": repairs}
		with open(os.path.join(self._dir(name), "meta.json"), "w", encoding="utf-8") as f:
			json.dump(meta, f, indent=1)
		return meta

	def meta(self, name):
		try:
			with open(os.path.join(self._dir(name), "meta.json"), encoding="utf-8") as f:
				return json.load(f)
		except (OSError, ValueError):
			return None

	def source(self, name):
		try:
			with open(self.path(name), encoding="utf-8") as f:
				return f.read()
		except OSError:
			return None

	def list(self):
		found = []
		try:
			names = sorted(os.listdir(self.folder))
		except OSError:
			return found
		for name in names:
			meta = self.meta(name)
			if meta and os.path.isfile(self.path(name)):
				found.append(meta)
		return found

	def setEnabled(self, name, enabled):
		meta = self.meta(name)
		if meta is None:
			return False
		meta["enabled"] = bool(enabled)
		with open(os.path.join(self._dir(name), "meta.json"), "w", encoding="utf-8") as f:
			json.dump(meta, f, indent=1)
		return True

	def remove(self, name):
		folder = self._dir(name)
		if not os.path.isdir(folder):
			return False
		for item in os.listdir(folder):
			if item in ("plugin.py", "meta.json") or item.endswith(".pyc"):
				os.remove(os.path.join(folder, item))
		try:
			os.rmdir(folder)
		except OSError:
			pass
		return True

	def package(self, name, outFolder, lastTested="2026.2"):
		"""Write a generated add-on as a normal .nvda-addon file that can be installed or shared."""
		meta, source = self.meta(name), self.source(name)
		if meta is None or source is None:
			return None
		ident = "visionClaw_" + meta["name"]
		summary = (meta.get("title") or meta["name"]).replace('"', "'")
		description = (meta.get("purpose") or summary).replace('"""', "'")
		manifest = (
			f"name = {ident}\nsummary = \"{summary}\"\ndescription = \"\"\"{description}\n"
			"Written by the VisionClaw add-on with a local AI model. Check it before sharing it.\"\"\"\n"
			"author = \"VisionClaw\"\nversion = 1.0\nminimumNVDAVersion = 2024.1\n"
			f"lastTestedNVDAVersion = {lastTested}\n"
		)
		os.makedirs(outFolder, exist_ok=True)
		out = os.path.join(outFolder, ident + ".nvda-addon")
		with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
			z.writestr("manifest.ini", manifest)
			z.writestr(f"globalPlugins/{ident}.py", source)
		return out
