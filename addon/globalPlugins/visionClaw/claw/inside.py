# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - everything inside the running NVDA, found by describing it. NVDA is made of several hundred
# modules with thousands of functions, classes and values, and the add-ons bring more; no list written in
# advance can hold them. So the list is made from the running program itself: every module that is loaded,
# and everything it has, with the first line of its own help text. A request is then matched against that
# list in plain words, and what is found can be looked at closely: what it is, how it is called, and, for a
# value or a function that only reports something, what it holds now.
# This module only reads. It works on whatever modules it is handed, so it is tested with plain Python.
# No NVDA dependencies.

import enum
import inspect
import pkgutil
import re
import sys

from . import match, ranking
from .memory import words

MAX_FOUND = 6
MAX_ENTRIES = 120000
MODULE, CLASS, FUNCTION, METHOD, PROPERTY, VALUE = "module", "class", "function", "method", "property", "value"
# Python's own modules and the libraries NVDA is built with are not NVDA: they are left out of the list.
_NOT_NVDA = frozenset((
	"wx", "comtypes", "PIL", "numpy", "markdown", "nh3", "requests", "urllib3", "certifi", "idna", "serial",
	"charset_normalizer", "hid", "cryptography", "cffi", "pycparser", "lxml", "bs4", "soupsieve", "configobj",
	"validate", "typing_extensions", "packaging", "win32api", "win32con", "pywintypes", "pythoncom", "win32com",
	"mdx_truly_sane_lists", "mdx_gh_links", "fast_diff_match_patch", "schedule", "pkg_resources", "setuptools",
	"diff_match_patch", "google", "six", "attr", "attrs", "yaml", "pycaw", "psutil", "opuslib", "websockets",
	"builtins", "__main__", "_distutils_hack", "sitecustomize",
))
_PLAIN = (str, int, float, bool, bytes, tuple, list, dict, set, frozenset, type(None))
# A function that only reports something: its name begins like this and it needs nothing to be called.
_REPORTS = re.compile(r"^(get|is|has)[A-Z_]")
_DOTTED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")


class Entry:
	__slots__ = ("name", "kind", "summary", "named", "other")

	def __init__(self, name, kind, summary):
		self.name = name
		self.kind = kind
		self.summary = summary
		parts = name.split(".")
		# The thing's own name counts for more than the names of what it is in.
		self.named = words(match.label(parts[-1]))
		self.other = words(f"{match.label(' '.join(parts[:-1]))} {summary} {kind}")

	def line(self):
		return f"{self.name}: {self.kind}. {self.summary}".rstrip(". ") + "."


def firstLine(doc, limit=160):
	"""The first sentence of a help text, as one line."""
	text = " ".join(str(doc or "").split())
	if not text:
		return ""
	# Epydoc and Sphinx fields are for tools, not for reading.
	text = re.split(r"\s[@:](param|type|return|returns|rtype|raise|raises|ivar|cvar|var|note)\b", text)[0]
	sentence = re.split(r"(?<=[.!?])\s", text)[0]
	return sentence[:limit].rstrip()


def signature(thing):
	try:
		return str(inspect.signature(thing))
	except (TypeError, ValueError):
		return ""


def isNvda(name, stdlib=None):
	"""Whether a loaded module belongs to NVDA or an add-on, and not to Python or a library."""
	stdlib = stdlib if stdlib is not None else getattr(sys, "stdlib_module_names", frozenset())
	root = name.split(".")[0]
	return bool(root) and not root.startswith("_") and root not in stdlib and root not in _NOT_NVDA


def _own(module, value):
	"""Whether something was made in this module, and not only brought into it from another."""
	return getattr(value, "__module__", None) == getattr(module, "__name__", None)


def _classEntries(prefix, cls):
	found = []
	for name, value in list(vars(cls).items()):
		if name.startswith("__"):
			continue
		if name.startswith("_get_") and callable(value):
			# NVDA's way of writing a property: _get_name is the property "name".
			found.append(Entry(f"{prefix}.{name[5:]}", PROPERTY, firstLine(getattr(value, "__doc__", ""))))
		elif name.startswith("_"):
			continue
		elif isinstance(value, property):
			found.append(Entry(f"{prefix}.{name}", PROPERTY, firstLine(value.__doc__)))
		elif isinstance(value, (staticmethod, classmethod)) or inspect.isfunction(value):
			function = getattr(value, "__func__", value)
			found.append(Entry(f"{prefix}.{name}", METHOD, f"{name}{signature(function)}. {firstLine(function.__doc__)}"))
	return found


def moduleEntries(module):
	"""Everything one module has, as entries: itself, its functions, its classes with their methods and
	properties, and its plain values."""
	name = getattr(module, "__name__", "")
	found = [Entry(name, MODULE, firstLine(getattr(module, "__doc__", "")))]
	try:
		members = list(vars(module).items())
	except Exception:
		return found
	for attr, value in members:
		if attr.startswith("_"):
			continue
		full = f"{name}.{attr}"
		try:
			if inspect.ismodule(value):
				continue
			if inspect.isclass(value):
				if _own(module, value):
					found.append(Entry(full, CLASS, firstLine(value.__doc__)))
					found += _classEntries(full, value)
			elif inspect.isroutine(value):
				if _own(module, value):
					found.append(Entry(full, FUNCTION, f"{attr}{signature(value)}. {firstLine(value.__doc__)}"))
			elif isinstance(value, _PLAIN) or isinstance(value, enum.Enum):
				found.append(Entry(full, VALUE, f"A {type(value).__name__}"))
			elif _own(module, type(value)) or getattr(type(value), "__module__", "").startswith(name + "."):
				# One object made from the module's own class, like braille.handler, the one braille handler.
				# What it holds is listed with it, so that braille.handler.display can be found by its name.
				found.append(Entry(full, VALUE, f"The module's {type(value).__name__} object. {firstLine(type(value).__doc__)}"))
				for inner in list(getattr(value, "__dict__", {})):
					if not inner.startswith("_"):
						found.append(Entry(f"{full}.{inner}", VALUE, f"Held by the {type(value).__name__} object"))
		except Exception:
			continue
	return found


NOT_LOADED = "A module that is not loaded yet; looking at it loads it"


def unloaded(modules, stdlib=None):
	"""The names of the modules that belong to the loaded NVDA packages and are not loaded themselves: the
	drivers of synthesizers and braille displays that are not in use, the modules of programs that are not
	running. Only their names are read; nothing is loaded here."""
	found = []
	for name, module in sorted(list(modules.items())):
		paths = getattr(module, "__path__", None)
		if module is None or not paths or not isNvda(name, stdlib):
			continue
		try:
			for info in pkgutil.iter_modules(list(paths)):
				full = f"{name}.{info.name}"
				if not info.name.startswith("_") and full not in modules and full not in found:
					found.append(full)
		except Exception:
			continue
	return found


def index(modules, stdlib=None):
	"""The list of everything in the given loaded modules that belongs to NVDA or an add-on, and the names of
	the modules of those packages that are not loaded. modules: {name: module}, like sys.modules."""
	found = []
	for name, module in sorted(list(modules.items())):
		if module is None or not isNvda(name, stdlib):
			continue
		try:
			found += moduleEntries(module)
		except Exception:
			continue
		if len(found) >= MAX_ENTRIES:
			break
	found += [Entry(name, MODULE, NOT_LOADED) for name in unloaded(modules, stdlib)]
	return found


def counts(entries):
	"""How many of each kind a list of entries has, and how many of its methods are commands."""
	found = {kind: 0 for kind in (MODULE, CLASS, FUNCTION, METHOD, PROPERTY, VALUE)}
	found["notLoaded"] = found["commands"] = 0
	for entry in entries:
		found[entry.kind] += 1
		if entry.kind == MODULE and entry.summary == NOT_LOADED:
			found["notLoaded"] += 1
		if entry.kind == METHOD and entry.name.rsplit(".", 1)[-1].startswith("script_"):
			found["commands"] += 1
	return found


def auditText(title, sections, entries):
	"""The whole audit as a text to keep and read: what was found, in sections of lines, then every entry.
	sections: (heading, lines) pairs."""
	parts = [f"# {title}", ""]
	for heading, lines in sections:
		parts += [f"## {heading}", ""] + [str(line) for line in lines] + [""]
	parts += ["## Everything inside, by name", ""]
	parts += [entry.line() for entry in sorted(entries, key=lambda e: e.name.lower())]
	return "\n".join(parts) + "\n"


def namesIn(text):
	"""The dotted names a request writes out, like api.getFocusObject."""
	return _DOTTED.findall(str(text or ""))


def search(entries, asked, limit=MAX_FOUND):
	"""The entries a request is about, best first. A name the request writes out in full comes first."""
	byName = {}
	for entry in entries:
		byName.setdefault(entry.name.lower(), entry)
	exact = []
	for name in namesIn(asked):
		hit = byName.get(name.lower())
		if hit is not None and hit not in exact:
			exact.append(hit)
	said = words(match.label(str(asked or "").replace(".", " ")))
	ranked = [entries[i] for i in ranking.rank(said, [(e.named, e.other) for e in entries], limit)]
	return (exact + [entry for entry in ranked if entry not in exact])[:limit]


def reports(name, thing):
	"""Whether a function only reports something and can be called with nothing: getFocusObject, isRunning."""
	if not callable(thing) or inspect.isclass(thing) or not _REPORTS.match(name):
		return False
	try:
		parameters = inspect.signature(thing).parameters.values()
	except (TypeError, ValueError):
		return False
	return all(
		p.default is not inspect.Parameter.empty or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD) for p in parameters)


def publicNames(thing, limit=40):
	"""The names of what something has, without the private ones; NVDA's _get_ properties by their own names."""
	names = []
	for name in dir(thing):
		if name.startswith("_get_"):
			name = name[5:]
		elif name.startswith("_"):
			continue
		if name not in names:
			names.append(name)
	shown = ", ".join(names[:limit])
	return shown + (f", and {len(names) - limit} more" if len(names) > limit else "")


def _short(value, limit):
	text = " ".join(repr(value).split())
	return text if len(text) <= limit else text[:limit].rstrip() + " ..."


def describe(value, limit=300):
	"""A value in words: what it is and what it holds. For an object NVDA reads, its name and kind."""
	try:
		if value is None:
			return "nothing (None)"
		if isinstance(value, bool):
			return "yes (True)" if value else "no (False)"
		if isinstance(value, enum.Enum):
			return f"{type(value).__name__}.{value.name}"
		if isinstance(value, (str, int, float, bytes)):
			return _short(value, limit)
		if isinstance(value, dict):
			return f"a dictionary with {len(value)} entries: {_short(dict(list(value.items())[:8]), limit)}"
		if isinstance(value, (list, tuple, set, frozenset)):
			return f"a {type(value).__name__} with {len(value)} items: {_short(list(value)[:8], limit)}"
		if inspect.isgenerator(value):
			return "a generator; its items are made one at a time when asked for"
		kind = f"{type(value).__module__}.{type(value).__qualname__}"
		role = getattr(value, "role", None)
		if role is not None and hasattr(value, "name"):
			name = " ".join(str(getattr(value, "name", "") or "").split())[:80]
			roleName = getattr(role, "displayString", None) or getattr(role, "name", None) or str(role)
			return f"an object NVDA reads: {roleName}" + (f" called \"{name}\"" if name else " without a name") + f" ({kind})"
		return f"a {kind} object. It has: {publicNames(value, 25)}"
	except Exception as e:
		return f"something that could not be read ({type(e).__name__})"
