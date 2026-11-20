# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - accessibility fixes for one website or one program, kept as plain data, and the add-on that is
# put together from them. A fix is one of five kinds:
#   jump   two keys that move to the next and the previous item of a kind (posts of a feed, results, videos)
#   press  one key that presses a control wherever the user is on the page or in the window
#   read   one key that reads a control's text (a time, a status, a count)
#   name   a name for controls that have none
#   watch  saying a control's text whenever it changes
# No model writes code here: a model only helps choose the fix and its words. The add-on's working part is
# fixed, tested text (fixruntime.py and fixmatch.py); this file adds the data and one small method per key.
# So what the add-on does can be said exactly, from its data. No NVDA dependencies.

import ast
import hashlib
import os
import re

JUMP, PRESS, READ, NAME, WATCH = "jump", "press", "read", "name", "watch"
KINDS = (JUMP, PRESS, READ, NAME, WATCH)
# A program made accessible window after window (claw/appaccess.py) gathers the fixes of all its windows in its one
# add-on, so it has room for more than one window needs. Names need no keys; the keys run out first (_SINGLE_KEYS).
MAX_FIXES = 80
MARK = "# VisionClaw fixes add-on"
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARTS = (
	(os.path.join(_HERE, "fixmatch.py"), "# --- matcher ---"),
	(os.path.join(os.path.dirname(_HERE), "fixruntime.py"), "# --- runtime ---"),
)
# What a rule may hold, and of which type. Anything else is dropped, so that only plain data reaches an add-on.
_RULE_TEXT = ("tag", "ident", "src", "state", "autoId", "windowClass", "level")
_RULE_LISTS = ("cls", "names", "notRole")
_RULE_FLAGS = ("unnamed", "outer")
# A rule must have at least one of these, or it would fit every control.
_TELLING = ("role", "tag", "ident", "cls", "src", "state", "controlId", "autoId", "names")
_KEY = re.compile(r"^[A-Za-z0-9]+(\+[A-Za-z0-9]+)*$")
_MODIFIERS = ("nvda", "control", "ctrl", "alt", "shift", "windows", "win")
# Keys offered when the user names none: unusual enough to be free in most programs and in NVDA itself.
_SINGLE_KEYS = tuple(f"NVDA+alt+{n}" for n in "1234567890") + tuple(f"NVDA+shift+alt+{n}" for n in "1234567890")
_PAIR_KEYS = (
	("NVDA+alt+downArrow", "NVDA+alt+upArrow"), ("NVDA+alt+pageDown", "NVDA+alt+pageUp"),
	("NVDA+shift+alt+downArrow", "NVDA+shift+alt+upArrow"), ("NVDA+shift+alt+pageDown", "NVDA+shift+alt+pageUp"),
	("NVDA+alt+rightArrow", "NVDA+alt+leftArrow"), ("NVDA+shift+alt+rightArrow", "NVDA+shift+alt+leftArrow"),
)
_KIND_NAMES = {
	"BUTTON": "buttons", "TOGGLEBUTTON": "buttons", "MENUBUTTON": "buttons", "LINK": "links", "GRAPHIC": "images",
	"EDITABLETEXT": "edit fields", "COMBOBOX": "combo boxes", "CHECKBOX": "checkboxes", "RADIOBUTTON": "radio buttons",
	"SLIDER": "sliders", "TAB": "tabs", "MENUITEM": "menu items",
}


def scopeOf(site="", app=""):
	"""Where fixes apply: one website (in any browser) or one program. Only the characters a website's or a
	program's name can have are kept, so that the name is safe wherever it is written."""
	site = re.sub(r"[^a-z0-9.-]", "", str(site or "").lower())[:100]
	if site:
		return {"site": site}
	return {"app": re.sub(r"[^A-Za-z0-9_.+-]", "", str(app or ""))[:60]}


def scopeText(scope):
	return f"the website {scope['site']}" if scope.get("site") else f"the program {scope.get('app', '')}"


def addonName(scope, apart=False):
	"""The name of the one add-on that holds all fixes for a website or program. Names are shortened and
	lose their punctuation when they become a folder, so two websites can end up with one name; apart=True
	gives a name with a mark of its own, for the website that came second."""
	place = scope.get("site") or scope.get("app") or ""
	if not apart:
		return "fixes " + place
	return f"fixes {place[:24]} {hashlib.sha1(place.encode('utf-8')).hexdigest()[:6]}"


def normKey(key):
	"""A key in one spelling, for comparing: "Alt + NVDA+p" and "nvda+alt+P" are the same key."""
	parts = [p for p in re.split(r"\s*\+\s*", str(key or "").strip().lower()) if p]
	if not parts:
		return ""
	modifiers = sorted({"control" if p == "ctrl" else "windows" if p == "win" else p for p in parts[:-1]})
	return "+".join(modifiers + [parts[-1]])


def cleanKey(key):
	"""A key as it is written into an add-on, or "" if it is not a usable key. A hotkey needs a modifier key,
	or it would take a plain letter away from the user."""
	text = "+".join(p for p in re.split(r"\s*\+\s*", str(key or "").strip()) if p)
	if text.lower().startswith("kb:"):
		text = text[3:]
	parts = text.split("+")
	if not _KEY.match(text) or len(parts) < 2 or parts[-1].lower() in _MODIFIERS:
		return ""
	if not all(p.lower() in _MODIFIERS for p in parts[:-1]):
		return ""
	return "+".join(["NVDA" if p.lower() == "nvda" else p.lower() for p in parts[:-1]] + [parts[-1]])


def keyIn(words):
	"""The hotkey named in what the user said, or ""."""
	found = re.search(
		r"\b((?:nvda|control|ctrl|alt|shift|windows|win)(?:\s*\+\s*[A-Za-z0-9]+)+)", str(words or ""), re.IGNORECASE)
	return cleanKey(found.group(1)) if found else ""


def _words(value, limit):
	return " ".join(str(value or "").split())[:limit]


def cleanRule(rule):
	"""A rule with only what a rule may hold. Raises ValueError if nothing telling is left."""
	clean = {}
	raw = rule if isinstance(rule, dict) else {}
	role = raw.get("role")
	if isinstance(role, str) and role:
		clean["role"] = _words(role, 40)
	elif isinstance(role, (list, tuple)) and role:
		clean["role"] = [_words(r, 40) for r in role if r][:8]
	for key in _RULE_TEXT:
		if raw.get(key):
			clean[key] = _words(raw[key], 120)
	for key in _RULE_LISTS:
		values = [_words(v, 80) for v in (raw.get(key) or ()) if str(v).strip()][:24]
		if values:
			clean[key] = values
	for key in _RULE_FLAGS:
		if raw.get(key):
			clean[key] = True
	if isinstance(raw.get("controlId"), int) and raw["controlId"]:
		clean["controlId"] = raw["controlId"]
	if not any(key in clean for key in _TELLING):
		raise ValueError("Nothing tells this control apart from every other control, so no fix can be made for it.")
	return clean


def clean(fix):
	"""A fix with only what a fix may hold, ready to be written into an add-on. Raises ValueError with a
	sentence a model or the user can act on."""
	kind = fix.get("kind")
	if kind not in KINDS:
		raise ValueError(f"\"{kind}\" is not a kind of fix. The kinds are: {', '.join(KINDS)}.")
	label = _words(fix.get("label"), 60)
	if not label:
		raise ValueError("A fix needs a few words that say what it is for.")
	keys = [cleanKey(key) for key in (fix.get("keys") or ())]
	wanted = {JUMP: 2, PRESS: 1, READ: 1}.get(kind, 0)
	if len(keys) != wanted or not all(keys):
		if wanted:
			raise ValueError(f"A fix of the kind {kind} needs {wanted} hotkey{'s' if wanted > 1 else ''} with a modifier key.")
		keys = []
	out = {"kind": kind, "rule": cleanRule(fix.get("rule")), "label": label, "keys": keys}
	if fix.get("guess"):
		out["guess"] = True  # the name is a guess from a picture, and the user is told so
	return out


def same(a, b):
	"""Whether two fixes are about the same thing, so that the newer replaces the older."""
	return a["kind"] == b["kind"] and a["rule"] == b["rule"]


def merge(old, new):
	"""The fixes of a website or program after new ones are added. A new fix replaces an old one about the
	same thing, and takes any key the old ones used. Raises ValueError when there would be too many."""
	taken = {normKey(key) for fix in new for key in fix["keys"]}
	kept = [fix for fix in old if not any(same(fix, n) for n in new) and not taken & {normKey(k) for k in fix["keys"]}]
	merged = kept + list(new)
	if len(merged) > MAX_FIXES:
		raise ValueError(f"That would be more than {MAX_FIXES} fixes for one website or program. Remove some first.")
	return merged


def freeKeys(count, used):
	"""count hotkeys that nothing else uses: one for a key that presses or reads, two for keys that move.
	used holds keys in the spelling of normKey. Returns a list, or None when the supply has run out."""
	taken = {normKey(key) for key in used}
	if count == 2:
		for pair in _PAIR_KEYS:
			if not taken & {normKey(key) for key in pair}:
				return list(pair)
		return None
	for key in _SINGLE_KEYS:
		if normKey(key) not in taken:
			return [key]
	return None


def giveKeys(fixes, used):
	"""Give every fix that needs keys and has none its keys, avoiding the used ones and each other's.
	Returns the fixes that could not be given keys (their kind is left without keys and they are dropped
	by the caller)."""
	taken = set(normKey(key) for key in used)
	for fix in fixes:
		taken.update(normKey(key) for key in fix.get("keys") or ())
	without = []
	for fix in fixes:
		wanted = {JUMP: 2, PRESS: 1, READ: 1}.get(fix["kind"], 0)
		if not wanted or len(fix.get("keys") or ()) == wanted:
			continue
		keys = freeKeys(wanted, taken)
		if keys is None:
			without.append(fix)
			continue
		fix["keys"] = keys
		taken.update(normKey(key) for key in keys)
	return without


def _kindName(rule):
	role = rule.get("role")
	role = role if isinstance(role, str) else (role[0] if role else "")
	return _KIND_NAMES.get(role, "controls")


def describeFix(fix):
	"""One fix in a plain sentence, taken from its data: this is what the add-on will do."""
	kind, label = fix["kind"], fix["label"]
	if kind == JUMP:
		return f"{fix['keys'][0]} moves to the next {label}, and {fix['keys'][1]} to the previous one."
	if kind == PRESS:
		return f"{fix['keys'][0]} presses {label}, wherever you are."
	if kind == READ:
		return f"{fix['keys'][0]} reads {label}."
	if kind == WATCH:
		return f"You are told when {label} changes."
	guess = " This name is a guess from its picture and can be wrong." if fix.get("guess") else ""
	return f"{_kindName(fix['rule']).capitalize()} without a name are called {label}.{guess}"


def describe(scope, fixes):
	"""What a fixes add-on does, in plain sentences for someone who cannot read code. Because the add-on is
	put together from its data, these sentences are the whole truth about it."""
	lines = [f"It works only on {scopeText(scope)}" + (", in any browser NVDA reads in browse mode." if scope.get("site") else ".")]
	names = [fix for fix in fixes if fix["kind"] == NAME]
	lines += [describeFix(fix) for fix in fixes if fix["kind"] != NAME]
	if len(names) > 3:
		sure = [fix["label"] for fix in names if not fix.get("guess")]
		guessed = [fix["label"] for fix in names if fix.get("guess")]
		if sure:
			lines.append(f"Controls without a name get these names: {', '.join(sure)}.")
		if guessed:
			lines.append(f"These names are guesses from pictures and can be wrong: {', '.join(guessed)}.")
	else:
		lines += [describeFix(fix) for fix in names]
	if any(fix["keys"] for fix in fixes):
		lines.append("Everywhere else these keys do what they always do.")
	return lines


def _part(path, mark):
	with open(path, encoding="utf-8") as f:
		text = f.read()
	head, found, body = text.partition("\n" + mark + "\n")
	if not found:
		raise ValueError(f"{os.path.basename(path)} has lost its marker line.")
	return body.strip("\n") + "\n"


def _method(index, fix):
	lines = []
	what = fix["label"]
	if fix["kind"] == JUMP:
		for step, key, word in ((1, fix["keys"][0], "Next"), (-1, fix["keys"][1], "Previous")):
			name = "next" if step > 0 else "previous"
			lines += [
				f"\t@script(description={f'{word} {what}'!r}, gesture={'kb:' + key!r})",
				f"\tdef script_fix{index}{name}(self, gesture):", f"\t\tself._do({index}, gesture, {step})", "",
			]
	elif fix["kind"] in (PRESS, READ):
		word = "Press" if fix["kind"] == PRESS else "Read"
		lines += [
			f"\t@script(description={f'{word} {what}'!r}, gesture={'kb:' + fix['keys'][0]!r})",
			f"\tdef script_fix{index}(self, gesture):", f"\t\tself._do({index}, gesture)", "",
		]
	return lines


def build(scope, fixes):
	"""The whole add-on, as one Python file, for a website's or a program's fixes. The fixes must be clean."""
	scope = scopeOf(scope.get("site", ""), scope.get("app", ""))
	if not (scope.get("site") or scope.get("app")):
		raise ValueError("Fixes need a website or a program to belong to.")
	if not fixes:
		raise ValueError("There are no fixes to put into an add-on.")
	where = scopeText(scope)
	lines = [
		MARK, f"# Accessibility fixes for {where}, put together by VisionClaw from fixed, tested parts.",
		"# The fixes are the plain data in FIXES. To change them, ask VisionClaw; do not edit this file by hand.",
		"# Licensed under the GNU General Public License, version 2 or later.", "",
		"from scriptHandler import script", "",
		f"SCOPE = {scope!r}", "FIXES = [",
	]
	lines += [f"\t{fix!r}," for fix in fixes]
	lines += ["]", "", ""]
	source = "\n".join(lines)
	for path, mark in _PARTS:
		source += _part(path, mark) + "\n\n"
	body = ["class GlobalPlugin(FixRuntime, globalPluginHandler.GlobalPlugin):", ""]
	if any(fix["kind"] == NAME for fix in fixes):
		# NVDA asks an add-on for a control's name only if this method is in the add-on's own class.
		body += ["\tdef chooseNVDAObjectOverlayClasses(self, obj, clsList):", "\t\tself._chooseOverlay(obj, clsList)", ""]
	for index, fix in enumerate(fixes):
		body += _method(index, fix)
	if len(body) == 2:
		body += ["\tpass", ""]
	return source + "\n".join(body).rstrip("\n") + "\n"


def isFixes(source):
	"""Whether an add-on's file was put together here, rather than written by the coder model."""
	return str(source or "").startswith(MARK)


def parse(source):
	"""The scope and fixes an add-on was built from, read back from its file, or None if it is not a fixes
	add-on or its data cannot be read."""
	if not isFixes(source):
		return None
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return None
	found = {}
	for node in tree.body:
		if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", "") in ("SCOPE", "FIXES"):
			try:
				found[node.targets[0].id] = ast.literal_eval(node.value)
			except (ValueError, SyntaxError):
				return None
	scope, fixes = found.get("SCOPE"), found.get("FIXES")
	if not isinstance(scope, dict) or not isinstance(fixes, list):
		return None
	try:
		return scopeOf(scope.get("site", ""), scope.get("app", "")), [clean(fix) for fix in fixes]
	except (ValueError, AttributeError, TypeError):
		return None
