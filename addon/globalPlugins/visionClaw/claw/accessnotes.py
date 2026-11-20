# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what it found about a stubborn program or website, kept as a Markdown file the user can read, change and
# delete. The owner asked on 2026-11-19 that VisionClaw use "memory markdown file usage" to get the most out of its small
# models "when fixing the most stubborn accessibility issues with various windows, apps, controls, control states,
# objects, object states, roles, classes, window states ... including all kinds of website objects and controls".
#
# One file for each program or website, in the folder access of VisionClaw's data, written by plain code only: how a
# control is worked, as the models agreed or as the model for hard cases settled it; a name read from a control's
# picture; what drew the window (its class); and what each inspection found, in one line. No model writes a line.
#
# What it is used for, each by plain code:
#   - known(): a control whose way was agreed before is not put to the models again: the same answer, at once, and no
#     chance of a different guess the second time (a small model does not always answer alike);
#   - forModels(): the few lines that fit a request go to the models that judge a control or write an add-on for this
#     program, as what was found here before;
#   - the user reads it: a line says what was found, when, and how sure it was.
# Each line ends with the rule that finds the control again, in brackets. A line the user changed or deleted is read as
# it now is. Lines are only ever added; the file never grows beyond MAX_LINES lines of findings. No NVDA dependencies.
#
# Two more sections make the file the program's map (claw/appaccess.py): every window or page of the program or website
# that VisionClaw learned, and the plan to fix all of them. Plain code writes them whole each time (entries, setEntries),
# with what finds a window or a fix again in brackets; a line the user deleted stays deleted.

import datetime
import json
import os
import re

FOLDER = "access"
MAX_LINES = 120
MAX_FOR_MODELS = 4
WAYS, NAMES, KIND, FOUND = "How controls are worked", "Names read from pictures", "What the window is", "What inspections found"
# The program's map (claw/appaccess.py): its windows and pages, and the plan to fix them.
WINDOWS, PLAN = "Windows and pages learned", "The plan to fix it"
SECTIONS = (WAYS, NAMES, KIND, FOUND, WINDOWS, PLAN)
# The sections MAX_LINES counts. The map has limits of its own (appaccess.MAX_WINDOWS, MAX_STEPS).
FINDINGS = (WAYS, NAMES, KIND, FOUND)
HEAD = (
	"VisionClaw writes this file from what it found when it inspected this {what} on this computer, so that the next "
	"inspection and the models that write add-ons for it can use it. It may be wrong. You may change or delete any "
	"line, or the whole file: VisionClaw only adds lines, and reads the file as it is.")
# How sure a line is, as the words at its end say.
AGREED, SETTLED, ONE = "agreed", "settled by the model for hard cases", "one model's answer, not sure"
_LINE = re.compile(r"^- (\d{4}-\d\d-\d\d): (.+?)(?: \[(\{.*\})\])?\s*$")
# How keepName writes a name, so that knownName can read it back.
_NAMED = re.compile(r"\bis called (.+?), from its picture\.?$")


def fileName(scope):
	"""The file of a program or website: its name with only safe characters."""
	name = scope.get("site") or scope.get("app") or ""
	name = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name)).strip("._")[:60]
	return f"{name}.md" if name else ""


def keyOf(rule, role="", name=""):
	"""What finds a control again: the rule from what is fixed in its code (audit.signature), or else its kind and
	name. None when it has neither, since a line about "a button" would fit every button."""
	if rule:
		return {key: rule[key] for key in sorted(rule)}
	name = " ".join(str(name or "").split())[:60]
	return {"name": name, "role": str(role or "")} if name else None


# Words that tell nothing about which control or program a line is about.
_PLAIN = frozenset((
	"the", "and", "for", "with", "that", "this", "from", "its", "not", "one", "when", "what", "which", "control", "controls",
	"without", "name", "called", "picture", "agreed", "sure", "model", "models", "answer", "click", "add", "addon", "write",
	"says", "say", "make", "add-on", "key", "keys", "button"))


def _telling(text):
	return {word for word in re.findall(r"[a-z][a-z0-9]{2,}", str(text or "").lower()) if word not in _PLAIN}


def _same(a, b):
	return bool(a) and bool(b) and json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


class AccessNotes:
	"""The notes of every program and website, one Markdown file each, in a folder."""

	def __init__(self, folder):
		self.folder = folder

	def path(self, scope):
		name = fileName(scope)
		return os.path.join(self.folder, name) if name else ""

	def _read(self, scope):
		"""{section: [(day, text, key or None)]}, as the file is now. A file that cannot be read is no notes."""
		path = self.path(scope)
		found = {section: [] for section in SECTIONS}
		if not path:
			return found
		try:
			with open(path, encoding="utf-8") as f:
				lines = f.read().splitlines()
		except (OSError, ValueError):
			return found
		section = None
		for line in lines:
			if line.startswith("## "):
				section = line[3:].strip()
				continue
			match = _LINE.match(line.strip())
			if match and section in found:
				key = None
				if match.group(3):
					try:
						key = json.loads(match.group(3))
					except ValueError:
						key = None
				found[section].append((match.group(1), match.group(2).strip(), key if isinstance(key, dict) else None))
		return found

	def _write(self, scope, found):
		path = self.path(scope)
		if not path:
			return False
		what = f"website {scope['site']}" if scope.get("site") else f"program {scope.get('app', '')}"
		lines = [f"# What VisionClaw found in the {what}", "", HEAD.format(what=what.split(" ")[0]), ""]
		for section in SECTIONS:
			if not found[section]:
				continue
			lines += [f"## {section}", ""]
			for day, text, key in found[section]:
				lines.append(f"- {day}: {text}" + (f" [{json.dumps(key, sort_keys=True)}]" if key else ""))
			lines.append("")
		try:
			os.makedirs(self.folder, exist_ok=True)
			with open(path, "w", encoding="utf-8", newline="\n") as f:
				f.write("\n".join(lines))
			return True
		except (OSError, ValueError):
			return False

	def _add(self, scope, section, text, key=None, today=None, replace=False):
		"""Add one line. A line about the same control in the same section is not added twice: with replace, the
		newer takes its place; else the older stays. Never raises: the notes only help."""
		try:
			text = " ".join(str(text or "").split())[:300].rstrip(".") + "."
			if not text.strip(". ") or not self.path(scope):
				return False
			found = self._read(scope)
			day = today or datetime.date.today().isoformat()
			lines = found[section]
			for at, (_day, old, oldKey) in enumerate(lines):
				if (key and _same(key, oldKey)) or (not key and old == text):
					if not replace or old == text:
						return False
					lines[at] = (day, text, key)
					return self._write(scope, found)
			lines.append((day, text, key))
			total = sum(len(found[name]) for name in FINDINGS)
			while total > MAX_LINES and found[FOUND]:
				found[FOUND].pop(0)  # the oldest summaries go first; what was found about a control stays
				total -= 1
			return self._write(scope, found)
		except Exception:
			return False

	# --- What is kept ---

	def keepWay(self, scope, key, calling, way, how, today=None):
		"""How a control is worked. how: AGREED, SETTLED or ONE. Only a sure answer is used again (known)."""
		if key is None or not way:
			return False
		return self._add(scope, WAYS, f"{calling}: {way}. {how}", key, today, replace=how in (AGREED, SETTLED))

	def keepName(self, scope, key, kind, name, today=None):
		"""A name read from the picture of a control that has none."""
		if key is None or not name:
			return False
		return self._add(scope, NAMES, f"a {kind} without a name is called {name}, from its picture", key, today)

	def keepKind(self, scope, text, today=None):
		"""What drew the window, as one sentence (working.toolkitOf)."""
		return self._add(scope, KIND, text, None, today)

	def keepFound(self, scope, text, today=None):
		"""What one inspection found, in one line."""
		return self._add(scope, FOUND, text, None, today)

	# --- The program's map: whole sections, written by plain code (claw/appaccess.py) ---

	def entries(self, scope, section):
		"""The lines of one section as [(day, text, key or None)], as the file is now."""
		return list(self._read(scope).get(section) or [])

	def setEntries(self, scope, section, lines):
		"""Write one section whole, as [(day, text, key or None)], and leave the others as they are. Nothing of a line
		is cut. Returns whether it was written; never raises."""
		try:
			if not self.path(scope):
				return False
			found = self._read(scope)
			found[section] = [(day, " ".join(str(text or "").split()), key) for day, text, key in lines if str(text or "").strip()]
			return self._write(scope, found)
		except Exception:
			return False

	# --- What is used ---

	def known(self, scope, key):
		"""The way a control is worked, as agreed or settled before for this key, or None."""
		if key is None:
			return None
		for _day, text, oldKey in reversed(self._read(scope)[WAYS]):
			if _same(key, oldKey) and (text.endswith(AGREED + ".") or text.endswith(SETTLED + ".")):
				way = text.rsplit(": ", 1)[-1].split(". ", 1)[0].strip(". ")
				return way or None
		return None

	def knownName(self, scope, key):
		"""The name read before from the picture of a control that has none, in any window of this program, for this key,
		or "". A control named in one window keeps that name in every other window it is in."""
		if key is None:
			return ""
		for _day, text, oldKey in reversed(self._read(scope)[NAMES]):
			found = _NAMED.search(text)
			if _same(key, oldKey) and found:
				return found.group(1).strip()
		return ""

	def forModels(self, scope, words="", limit=MAX_FOR_MODELS, strict=False):
		"""The few lines that fit a request, for a model that judges a control or writes an add-on for this place:
		the lines that share a word with the request first, then the newest, without the rules in brackets. strict:
		only lines that share a telling word with the request, as for the writer of an add-on, which copies what it
		is given. "" when there are none."""
		found = self._read(scope)
		lines = [text for section in (WAYS, NAMES, KIND) for _day, text, _key in found[section]]
		if not lines:
			return ""
		wanted = _telling(words)
		ranked = sorted(enumerate(lines), key=lambda pair: (-len(wanted & _telling(pair[1])), -pair[0]))
		chosen = [text for _at, text in ranked[:limit] if not strict or wanted & _telling(text)]
		if not chosen:
			return ""
		return "Found in this place before, on this computer:\n" + "\n".join(f"- {text}" for text in chosen)

	def text(self, scope):
		"""The whole file, or "" when there is none."""
		path = self.path(scope)
		try:
			with open(path, encoding="utf-8") as f:
				return f.read()
		except (OSError, ValueError):
			return ""

	def forget(self, scope):
		"""Delete the file of one place. Returns whether there was one."""
		path = self.path(scope)
		try:
			os.remove(path)
			return True
		except (OSError, ValueError):
			return False
