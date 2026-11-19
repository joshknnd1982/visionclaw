# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Stand-ins for the NVDA modules a small generated add-on uses, which write down what the add-on did: what it said,
how it beeped, which keys it passed on. A generated add-on is run against them to see whether it does what was asked,
without NVDA. Used by tests/test_codeplan.py and tests/live_codeplan.py.
"""
import ast
import sys
import types

def _roles():
	"""Every kind of control NVDA has: the list tests/test_working.py read from the installed NVDA's controlTypes.Role."""
	import re
	import os
	text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_working.py"), encoding="utf-8").read()
	block = text[text.index("NVDA_ROLES = ("):]
	block = block[:block.index(").split()")]
	return tuple(re.findall(r"[A-Z][A-Z_0-9]+", block.split("(", 1)[1]))


ROLES = _roles()
STATES = ("CHECKED", "PRESSED", "SELECTED", "EXPANDED", "COLLAPSED", "UNAVAILABLE", "BUSY", "FOCUSED", "READONLY")


def control(name="OK", role="BUTTON", app="notepad", states=(), value=None):
	"""A control as an add-on sees it."""
	# What NVDA's controls have (NVDAObjects), so that an add-on is judged by what it does, not by a stand-in's gaps.
	return types.SimpleNamespace(name=name, role=role, states=set(states), value=value, description="",
		appModule=types.SimpleNamespace(appName=app, productName=app, appModuleName=app), windowClassName="Edit",
		windowControlID=15, windowHandle=1, windowText=name, processID=1, parent=None, children=[], childCount=0,
		next=None, previous=None, firstChild=None, lastChild=None, location=(0, 0, 100, 20), keyboardShortcut="",
		roleText=None, isFocusable=True, hasFocus=True, indexInParent=0, positionInfo={})


class Fake:
	"""What an add-on did, and the modules it is given."""

	def __init__(self, focus=None, foreground=None):
		self.said, self.beeps, self.sent, self.spoken = [], [], [], []
		self.focus = focus or control()
		self.foreground = foreground or control("Inbox - Mail", "WINDOW", self.focus.appModule.appName)

	def modules(self):
		fake = self
		base = types.ModuleType("globalPluginHandler")
		base.GlobalPlugin = type("GlobalPlugin", (), {"__init__": lambda self: None})
		ui = types.ModuleType("ui")
		ui.message = lambda text, *a, **k: fake.said.append(str(text))
		tones = types.ModuleType("tones")
		tones.beep = lambda frequency, length, *a, **k: fake.beeps.append(frequency)
		api = types.ModuleType("api")
		api.getFocusObject = lambda: fake.focus
		api.getNavigatorObject = lambda: fake.focus
		api.getForegroundObject = lambda: fake.foreground
		api.getClipData = lambda: "clipboard text"
		controlTypes = types.ModuleType("controlTypes")
		controlTypes.Role = types.SimpleNamespace(**{name: name for name in ROLES})
		controlTypes.State = types.SimpleNamespace(**{name: name for name in STATES})
		controlTypes.ROLE_BUTTON, controlTypes.ROLE_LINK = "BUTTON", "LINK"
		scriptHandler = types.ModuleType("scriptHandler")
		scriptHandler.script = lambda *a, **keys: (lambda fn: fn)
		speech = types.ModuleType("speech")
		speech.speakMessage = lambda text, *a, **k: fake.said.append(str(text))
		speech.speak = lambda seq, *a, **k: fake.said.append(" ".join(str(x) for x in seq))
		speech.speakText = speech.speakMessage
		speech.cancelSpeech = lambda: None
		braille = types.ModuleType("braille")
		braille.handler = types.SimpleNamespace(message=lambda text: fake.spoken.append(str(text)))
		return {"globalPluginHandler": base, "ui": ui, "tones": tones, "api": api, "controlTypes": controlTypes,
			"scriptHandler": scriptHandler, "speech": speech, "braille": braille}


def load(source, fake):
	"""The add-on made from source, with NVDA's modules stood in for. Raises what the add-on raises when it is made."""
	saved = {name: sys.modules.get(name) for name in fake.modules()}
	sys.modules.update(fake.modules())
	try:
		space = {"__name__": "generated"}
		exec(compile(source, "addon", "exec"), space)
		return space["GlobalPlugin"]()
	finally:
		for name, module in saved.items():
			if module is None:
				sys.modules.pop(name, None)
			else:
				sys.modules[name] = module


def scripts(source):
	"""The key commands of an add-on: {key in lower case, without "kb:": method name}."""
	found = {}
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.FunctionDef):
			for decorator in node.decorator_list:
				if isinstance(decorator, ast.Call):
					for keyword in decorator.keywords:
						if keyword.arg == "gesture" and isinstance(keyword.value, ast.Constant):
							found[str(keyword.value.value).lower().replace("kb:", "")] = node.name
	return found


def press(plugin, source, key, fake):
	"""Press a key of the add-on. Returns False when the add-on has no such key."""
	name = scripts(source).get(key.lower().replace("kb:", ""))
	if name is None:
		return False
	getattr(plugin, name)(types.SimpleNamespace(send=lambda: fake.sent.append(key)))
	return True


def event(plugin, name, obj, fake, **extra):
	"""Send an event to the add-on. Returns how often NVDA was passed the event on, or None when it has no such event."""
	method = getattr(plugin, f"event_{name}", None)
	if method is None:
		return None
	passed = []
	method(obj, lambda: passed.append(1), **extra)
	return len(passed)
