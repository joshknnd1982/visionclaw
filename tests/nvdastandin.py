# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Stand-ins for NVDA's own modules, small enough for a test that drives one or two of VisionClaw's tool files
with plain Python: after `import nvdastandin`, `from visionClaw import papertools` works. Every module of NVDA that
the tool files import is a module here that has every attribute and never complains; what a test needs to be
real, it sets itself (config.conf, a function of a module). tests/test_nvda_stub.py has the full stand-in for
the whole add-on; this one is for a test of its own that must not depend on everything else loading.
"""
import builtins
import sys
import types

import harness  # noqa: F401


class _Meta(type):
	def __getattr__(cls, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return type(name, (Anything,), {})


class Anything(metaclass=_Meta):
	"""A class that has every attribute, can be called and subclassed, and never complains."""

	def __init__(self, *args, **kwargs):
		pass

	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		return Anything()

	def __call__(self, *args, **kwargs):
		return Anything()

	def __iter__(self):
		return iter(())

	def __getitem__(self, key):
		return Anything()


class Stub(types.ModuleType):
	def __getattr__(self, name):
		if name.startswith("__"):
			raise AttributeError(name)
		found = type(name, (Anything,), {})
		setattr(self, name, found)
		return found


NAMES = (
	"addonHandler", "api", "config", "controlTypes", "globalPluginHandler", "logHandler", "speech", "textInfos",
	"textInfos.offsets", "tones", "ui", "browseMode", "mouseHandler", "winUser", "keyboardHandler", "inputCore",
	"scriptHandler", "synthDriverHandler", "braille", "gui", "core", "queueHandler", "eventHandler", "UIAHandler",
	"NVDAObjects", "NVDAObjects.UIA", "NVDAObjects.IAccessible", "contentRecog", "contentRecog.uwpOcr", "contentRecog.recogUi",
	"screenCurtain", "vision", "locationHelper", "winVersion", "nvwave", "appModuleHandler", "winKernel", "cursorManager",
	"virtualBuffers", "globalVars", "languageHandler", "documentationUtils", "globalCommands", "buildVersion", "oleacc",
	"comtypes", "comtypes.client", "comtypes.automation")

builtins._ = lambda text: text
for _name in NAMES:
	if _name not in sys.modules:
		sys.modules[_name] = Stub(_name)
sys.modules["addonHandler"].initTranslation = lambda: None
sys.modules["logHandler"].log = Anything()
if not isinstance(getattr(sys.modules["config"], "conf", None), dict):
	sys.modules["config"].conf = {"visionClaw": {"useOcr": True, "detailSize": 448, "confirmChanges": True}}
conf = sys.modules["config"].conf


class Location:
	"""Where a control is on the screen, as NVDA gives it."""

	def __init__(self, left, top, right, bottom):
		self.left, self.top, self.width, self.height = left, top, right - left, bottom - top


class Tools:
	"""What a tool file's register() is given, with everything that is asked and done written down."""

	def __init__(self, plugin=None, screen=None):
		self.tools, self.asked, self.no = {}, [], False
		self.plugin, self.screen = plugin, screen

	def add(self, name, description, fn, fields=None, **options):
		self.tools[name] = (fn, fields or {}, options)

	@staticmethod
	def text(description, **extra):
		return dict({"type": "string", "description": description}, **extra)

	@staticmethod
	def onMain(fn, *args, **more):
		return fn(*args)

	def confirm(self, question):
		self.asked.append(question)
		if self.no:
			raise Refused()

	mustAgree = confirm

	def register(self, module):
		module.register(self.add, self.plugin, self.text, self.onMain, self.confirm, self.mustAgree, self.screen)
		return self

	def call(self, name, task, **form):
		return self.tools[name][0](task, **form)


class Refused(Exception):
	"""The user said no."""
