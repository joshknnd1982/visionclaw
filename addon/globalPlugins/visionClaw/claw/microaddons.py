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
_SYSTEM = (
	"You write small add-ons for the NVDA screen reader in Python. "
	"Answer with one complete Python file inside a ```python block, and nothing else.\n"
	"Rules:\n"
	"- The file defines class GlobalPlugin(globalPluginHandler.GlobalPlugin).\n"
	"- Speak with ui.message(\"text\"). Beep with tones.beep(frequency, milliseconds).\n"
	"- A key command is a method named script_something(self, gesture) with the decorator "
	"@script(description=\"...\", gesture=\"kb:NVDA+shift+k\").\n"
	"- An event is a method like event_gainFocus(self, obj, nextHandler). It must call nextHandler() at the end, "
	"and wrap its own work in try/except so NVDA keeps working.\n"
	"- To act only in one program, check obj.appModule.appName, for example \"notepad\".\n"
	"- Import only NVDA modules and these: re, time, datetime, json, math, threading, collections, os.path.\n"
	"- Never use subprocess, the internet, eval, exec, open, or anything that deletes or writes files.\n"
	"- Keep it short and simple. Do exactly what is asked and nothing more.\n"
	"Example of a correct file:\n```python\n" + TEMPLATE + "```"
)
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


def _generate(llm, role, user, params):
	answer = llm.text(role, _SYSTEM, user, maxTokens=params.codeTokens, reasoning=params.reasoning, temperature=0.1, code=True)
	return extractCode(answer)


def write(llm, task, purpose, facts, notes, params, coder, reviewer):
	"""Have the coder model write an add-on, fix what the check finds, and let the other model review it.
	facts: what is known about the user's situation. notes: knowledge about NVDA that fits the purpose.
	Returns the source. Raises ToolError if no version passes the check."""
	user = f"Write an NVDA add-on that does this: {clip(purpose, 700)}\n"
	if facts:
		user += f"What is known:\n{clip(facts, 700)}\n"
	if notes:
		user += f"Notes about NVDA that may help:\n{clip(notes, 1600)}\n"
	task.emit("detail", "The coder model is writing the add-on.")
	source = _generate(llm, coder, user, params)
	reviews = params.codeReviews
	for attempt in range(params.codeRepairs + 1):
		task.check()
		problems = check(source)
		if not problems and reviews > 0:
			reviews -= 1
			try:
				verdict = llm.json(
					reviewer, _REVIEW_SYSTEM, f"Asked for: {clip(purpose, 500)}\nCode:\n{clip(source, 5000)}",
					_REVIEW_SCHEMA, maxTokens=120, reasoning=params.reasoning,
				)
			except LLMError:
				verdict = {"ok": True}
			fault = " ".join(str(verdict.get("problem") or "").split())
			if not verdict.get("ok") and fault:
				task.emit("talk", f"The reviewing model found a fault in the code: {fault}")
				problems = [fault]
			else:
				task.emit("talk", "The reviewing model checked the code: no fault found.")
		if not problems:
			return source
		if attempt == params.codeRepairs:
			break
		task.emit("detail", "Fixing the code: " + " ".join(problems[:4]))
		source = repair(llm, coder, purpose, source, problems, params)
	raise ToolError("The coder model could not write code that passes the checks: " + " ".join(check(source)[:3]))


def repair(llm, role, purpose, source, problems, params):
	"""Have the coder model fix its add-on. problems are sentences, or an error message from NVDA."""
	user = (
		f"This NVDA add-on should do this: {clip(purpose, 500)}\n```python\n{clip(source, 5000)}\n```\n"
		"It has these problems:\n" + "\n".join(f"- {clip(p, 500)}" for p in problems[:6])
		+ "\nWrite the whole corrected file."
	)
	return _generate(llm, role, user, params)


class Store:
	"""Generated add-ons on disk: one folder each, with plugin.py and meta.json."""

	def __init__(self, folder):
		self.folder = folder

	def _dir(self, name):
		return os.path.join(self.folder, slug(name))

	def path(self, name):
		return os.path.join(self._dir(name), "plugin.py")

	def save(self, name, source, purpose="", enabled=True):
		os.makedirs(self._dir(name), exist_ok=True)
		with open(self.path(name), "w", encoding="utf-8") as f:
			f.write(source)
		meta = {"name": slug(name), "title": str(name), "purpose": purpose, "enabled": enabled, "created": time.time()}
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
