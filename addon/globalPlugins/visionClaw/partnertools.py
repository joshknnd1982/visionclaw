# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - working together with two add-ons when they are running in the same NVDA (claw/partners.py): the
# JAWS Migration Assistant and ClassicSpeech. Neither has an interface for other add-ons, so what VisionClaw
# uses of them is named here, as read from their source on 2026-11-18. Read their source again before changing
# this; do not write a name from memory. Every reach into them is wrapped: where a newer version keeps
# something differently, VisionClaw says so and changes nothing.
#
# JAWS Migration Assistant 1.63 (github.com/joshknnd1982/jawsMigrator, MIT). Only read, never written:
#   globalPlugins.jawsMigrator                 the plugin; LAYER_COMMANDS: (gestures, script, key name, words)
#     GlobalPlugin._jawsKeymap()               (JAWS, {NVDA gesture: [(JAWS key, script, section)]}, script
#                                              descriptions, layout, layer starts) or None; reads JAWS's files
#   globalPlugins.jawsMigrator.jawsKeyMap      pure data: SCRIPT_MAP, QUICK_NAV_MAP {JAWS script: (module, class,
#                                              NVDA script, description)}; getNvdaTargets(script, jawsKey);
#                                              jawsKeyToNvdaGesture(jawsKey, layout)
#   globalPlugins.jawsMigrator.jawsDocs        describe(docs, script)
#   globalPlugins.jawsMigrator.state           get("lastMigration"): {"when", "jaws", "target", ...}
#
# ClassicSpeech 1.16 (github.com/joshknnd1982/classicspeech-nvda, GPL v2). Changed only with its own calls:
#   globalPlugins.classicSpeech                the plugin; processor.set_profile(name) sets the verbosity level;
#                                              script_openClassicSpeech... open its windows
#   config.conf["classicSpeech"]["defaultProfile"]   the level: Beginner, Intermediate or Advanced
#   globalPlugins._speech_core.schemes.store   schemes_root(), load_scheme_folders(root) -> (schemes, folders),
#                                              runtime_data().data {"enabled", "activeScheme"},
#                                              set_schemes_enabled(bool), cycle_active_scheme(),
#                                              SchemeStore().set_active_scheme(name) then .apply()
#   Its own rule (AGENTS.md): a window is never opened from inside NVDA's handling of a key or a queued call;
#   wx.CallAfter is used.

import sys

import addonHandler
import config
import wx

from .claw import partners
from .claw.llm import uncut
from .claw.tools import VERBATIM, ToolError
from .vclog import log

addonHandler.initTranslation()

JAWS_MODULE, CLASSIC_MODULE = "globalPlugins.jawsMigrator", "globalPlugins.classicSpeech"
STORE_MODULE = "globalPlugins._speech_core.schemes.store"


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def running(module):
	"""The running plugin of an add-on, by the module it is in, or None."""
	try:
		import globalPluginHandler
		for plugin in list(globalPluginHandler.runningPlugins):
			if str(type(plugin).__module__).startswith(module):
				return plugin
	except Exception:
		pass
	return None


def refresh():
	"""Tell claw/partners.py which of the two add-ons are running now. Returns their names."""
	here = [name for name, module in ((partners.JAWS, JAWS_MODULE), (partners.CLASSIC, CLASSIC_MODULE)) if running(module) is not None]
	partners.setInstalled(here)
	return here


def _module(name):
	return sys.modules.get(name)


# --- ClassicSpeech ---

def classicState():
	"""What ClassicSpeech is set to: (level, schemes on, the scheme in use, the names of all schemes). A part that
	cannot be read is None. Main thread."""
	level = _safe(lambda: str(config.conf["classicSpeech"]["defaultProfile"]))
	store = _module(STORE_MODULE)
	data = _safe(lambda: dict(store.runtime_data().data)) or {}
	names = _safe(lambda: list(store.load_scheme_folders(store.schemes_root())[0])) or []
	return level, data.get("enabled"), data.get("activeScheme"), names


def classicText(commands=()):
	"""ClassicSpeech as it is set now, in sentences. commands: its commands with their keys, as lines."""
	level, on, active, names = classicState()
	lines = ["ClassicSpeech is running."]
	if level:
		lines.append(f"Its verbosity level is {level}: {partners.LEVEL_SAYS.get(level, '')}".rstrip(": "))
	if names:
		lines.append(
			f"Speech and sound schemes are {'on' if on else 'off'}" + (f", and the scheme in use is {active}" if active else "")
			+ f". Schemes here: {', '.join(names[:12])}.")
	lines.append(
		"VisionClaw can change these when you ask: set ClassicSpeech to Advanced, say less about each control, which "
		"schemes do I have, switch to a scheme by its name, turn schemes off, open voice profiles.")
	if commands:
		lines.append("Its commands: " + " ".join(commands[:8]))
	return " ".join(lines)


def setLevel(plugin, name):
	plugin.processor.set_profile(name)


def setScheme(name):
	store = _module(STORE_MODULE)
	schemes = store.SchemeStore()
	schemes.set_active_scheme(name)
	schemes.apply()


def setSchemesOn(on):
	_module(STORE_MODULE).set_schemes_enabled(bool(on))


def undoClassic(plugin, change, confirm):
	"""Put back what VisionClaw changed in ClassicSpeech. Returns the sentence for the user."""
	classic = running(CLASSIC_MODULE)
	if classic is None:
		return partners.CLASSIC_MISSING
	kind = str(change["setting"]).split(":", 1)[1]
	old = change["old"]
	# Translators: Asked before VisionClaw puts something of the add-on ClassicSpeech back to what it was.
	confirm(_("Put {what} back to {old}, as it was before VisionClaw changed it?").format(what=change["label"], old=change["oldShown"]))
	try:
		if kind == "level":
			setLevel(classic, old)
		elif kind == "scheme":
			setScheme(old)
		else:
			setSchemesOn(old)
	except Exception:
		log.error("VisionClaw: ClassicSpeech could not be put back", exc_info=True)
		return partners.CLASSIC_CHANGED
	plugin.changes.markUndone(change)
	return f"{change['label'][:1].upper() + change['label'][1:]} is back to {change['oldShown']}, as it was before."


# --- The JAWS Migration Assistant ---

def _nvdaKeys(commands, scriptName):
	"""The keys NVDA has for one of its commands, in words, from VisionClaw's own list of NVDA's commands."""
	for command in commands or ():
		if getattr(command, "scriptName", "") == scriptName and getattr(command, "keys", None):
			return " or ".join(command.keys)
	return ""


def _targetsText(keyMap, script, jawsKey, commands):
	"""What a JAWS command is in NVDA, in sentences; "" when the JAWS Migration Assistant knows no NVDA command."""
	said = []
	for _module_, _cls, nvdaScript, description in keyMap.getNvdaTargets(script, jawsKey) or ():
		keys = _nvdaKeys(commands, nvdaScript)
		said.append(f"{str(description).rstrip('.')}" + (f", with {keys}" if keys else ", which has no key of its own in NVDA") + ".")
	return " ".join(said)


def jawsKeyText(plugin, key, commands):
	"""What a JAWS keystroke does in JAWS and what that is in NVDA. Main thread."""
	keyMap = _module(JAWS_MODULE + ".jawsKeyMap")
	docsModule = _module(JAWS_MODULE + ".jawsDocs")
	found = plugin._jawsKeymap()
	if not found:
		return partners.NO_KEYMAP
	_jaws, reverse, docs, layout, _starts = found
	import inputCore
	entries = []
	for where in (layout, "desktop", "laptop", "common"):
		gesture = keyMap.jawsKeyToNvdaGesture(key, where if where in ("desktop", "laptop") else "common")
		if gesture:
			entries = reverse.get(inputCore.normalizeGestureIdentifier(gesture).lower()) or []
			if entries:
				break
	shown = "+".join(part.capitalize() for part in key.split("+"))
	if not entries:
		return (
			f"JAWS's own key map on this computer has nothing for {shown}, or the JAWS Migration Assistant does not know "
			"that key. To try it: press NVDA+Shift+J, then K, then the JAWS keystroke.")
	lines = []
	for jawsKey, script, _section in entries[:3]:
		what = docsModule.describe(docs, script)
		nvda = _targetsText(keyMap, script, jawsKey, commands)
		lines.append(
			f"In JAWS, {shown} is: {what}." + (f" In NVDA that is: {nvda}" if nvda else " NVDA has no command of its own for that."))
	return " ".join(lines)


def jawsCommandText(words, commands):
	"""What a JAWS command, named in words, is in NVDA. Needs no JAWS on the computer."""
	keyMap = _module(JAWS_MODULE + ".jawsKeyMap")
	names = {}
	for table in (keyMap.SCRIPT_MAP, keyMap.QUICK_NAV_MAP):
		for name, target in table.items():
			names.setdefault(name, str(target[3]))
	found = partners.matchCommand(words, names)
	if not found:
		return (
			f"The JAWS Migration Assistant knows no JAWS command that fits these words: {uncut(words)}. Say the JAWS "
			"keystroke instead, such as Insert+F7, or press NVDA+Shift+J, then K, then the JAWS keystroke.")
	lines = []
	for name in found:
		nvda = _targetsText(keyMap, name, None, commands)
		if nvda:
			lines.append(f"JAWS's command {name}: in NVDA that is: {nvda}")
	return " ".join(lines) or "NVDA has no command of its own for that."


def jawsInfoText():
	"""What the JAWS Migration Assistant brought over, and the commands of its layer."""
	module = _module(JAWS_MODULE)
	state = _module(JAWS_MODULE + ".state")
	last = _safe(lambda: state.get("lastMigration")) or {}
	lines = ["The JAWS Migration Assistant is running."]
	if isinstance(last, dict) and last.get("when"):
		lines.append(
			f"Its last migration was on {str(last.get('when'))[:10]}, from {last.get('jaws') or 'JAWS'}, into "
			f"{last.get('target') or 'NVDA'}. Its report opens with NVDA+Shift+J, then R.")
	else:
		lines.append("It has not brought anything over from JAWS on this computer yet. NVDA+Shift+J, then M opens it.")
	layer = _safe(lambda: list(module.LAYER_COMMANDS)) or []
	if layer:
		lines.append("After NVDA+Shift+J, these keys: " + " ".join(f"{key}: {str(words).rstrip('.')}." for _g, _script, key, words in layer))
	lines.append("Ask VisionClaw what any JAWS keystroke is in NVDA, such as: what is JAWS's Insert+F7 in NVDA.")
	return uncut(" ".join(lines))


def register(add, plugin, text, onMain, confirm, commands):
	"""Add the two tools. add, text and confirm are nvdatools' own; commands() gives NVDA's commands."""
	asked = {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)}

	def classicSpeech(task, asked):
		classic = running(CLASSIC_MODULE)
		if classic is None:
			return partners.CLASSIC_MISSING
		wish = partners.classicWish(asked or task.request) or {"what": partners.INFO}
		what = wish["what"]
		try:
			level, on, active, names = onMain(classicState)
			if what == partners.OPEN:
				script = getattr(classic, wish["script"])
				# As ClassicSpeech's own rule says: a window is opened with wx.CallAfter.
				wx.CallAfter(script, None)
				return f"Opened {wish['said']}."
			if what == partners.LEVEL:
				new = wish.get("level") or partners.nextLevel(level, wish["step"])
				if new is None:
					return f"ClassicSpeech's verbosity level is {level} already, and there is none beyond it. {partners.LEVEL_SAYS.get(level, '')}"
				if new == level:
					return f"ClassicSpeech's verbosity level is {level} already. {partners.LEVEL_SAYS.get(level, '')}"
				# Translators: Asked before VisionClaw changes the verbosity level of the add-on ClassicSpeech.
				confirm(_("Change ClassicSpeech's verbosity level from {old} to {new}? {says}").format(
					old=level, new=new, says=partners.LEVEL_SAYS.get(new, "")))
				onMain(setLevel, classic, new)
				plugin.changes.add("classicspeech:level", "ClassicSpeech's verbosity level", level, new, level, new, asked or task.request)
				return f"ClassicSpeech's verbosity level was {level} and is now {new}. {partners.LEVEL_SAYS.get(new, '')}"
			if what == partners.SCHEMES:
				if not names:
					return "ClassicSpeech has no speech and sound schemes that VisionClaw can find."
				return (
					f"Speech and sound schemes are {'on' if on else 'off'}. The scheme in use is {active}. ClassicSpeech has "
					f"{len(names)}: {', '.join(names[:20])}. To use another, say: switch to the scheme, and its name.")
			if what == partners.SCHEMES_ON:
				if bool(on) == wish["on"]:
					return f"Speech and sound schemes are {'on' if on else 'off'} already."
				# Translators: Asked before VisionClaw turns the speech and sound schemes of the add-on ClassicSpeech on or off.
				confirm(_("Turn ClassicSpeech's speech and sound schemes {state}?").format(state="on" if wish["on"] else "off"))
				onMain(setSchemesOn, wish["on"])
				plugin.changes.add("classicspeech:schemes", "ClassicSpeech's speech and sound schemes", bool(on), wish["on"],
					"on" if on else "off", "on" if wish["on"] else "off", asked or task.request)
				return f"ClassicSpeech's speech and sound schemes are now {'on' if wish['on'] else 'off'}."
			if what in (partners.SCHEME, partners.NEXT):
				if what == partners.NEXT:
					new = names[(names.index(active) + 1) % len(names)] if active in names and names else None
				else:
					new = partners.pickName(wish["name"], names)
				if new is None:
					return (
						"VisionClaw could not tell which scheme you mean. ClassicSpeech has: " + ", ".join(names[:20])
						+ ". Say: switch to the scheme, and one of these names.")
				if new == active:
					return f"The scheme {new} is in use already."
				# Translators: Asked before VisionClaw switches the speech and sound scheme of the add-on ClassicSpeech.
				confirm(_("Switch ClassicSpeech's speech and sound scheme from {old} to {new}?").format(old=active, new=new))
				onMain(setScheme, new)
				plugin.changes.add("classicspeech:scheme", "ClassicSpeech's speech and sound scheme", active, new, active, new, asked or task.request)
				return f"ClassicSpeech's speech and sound scheme was {active} and is now {new}." + (
					"" if on else " Schemes are turned off, so it is not heard until you say: turn schemes on.")
			lines = [command.line() for command in commands() if str(command.source).startswith(CLASSIC_MODULE) and command.keys]
			return uncut(onMain(classicText, lines))
		except ToolError:
			raise
		except (AttributeError, KeyError, ImportError, TypeError) as e:
			log.error(f"VisionClaw: ClassicSpeech could not be worked ({type(e).__name__}: {e})", exc_info=True)
			return partners.CLASSIC_CHANGED

	add("classic_speech",
		"with the add-on ClassicSpeech: change how much NVDA says about each control (Beginner, Intermediate, "
		"Advanced), list or switch its speech and sound schemes or turn them on or off, open its windows, or say how "
		"it is set",
		classicSpeech, asked, title="Working ClassicSpeech", tell=VERBATIM)

	def jawsHelp(task, asked):
		migrator = running(JAWS_MODULE)
		if migrator is None:
			return partners.JAWS_MISSING
		wish = partners.jawsWish(asked or task.request) or {"what": partners.INFO}
		try:
			known = commands()
			if wish["what"] == partners.KEY:
				return uncut(onMain(jawsKeyText, migrator, wish["key"], known))
			if wish["what"] == partners.COMMAND:
				return uncut(onMain(jawsCommandText, wish["words"], known))
			return onMain(jawsInfoText)
		except (AttributeError, KeyError, ImportError, TypeError, ValueError) as e:
			log.error(f"VisionClaw: the JAWS Migration Assistant could not be asked ({type(e).__name__}: {e})", exc_info=True)
			return (
				"This version of the JAWS Migration Assistant keeps that in another way than VisionClaw knows. Its own "
				"helper still works: press NVDA+Shift+J, then K, then the JAWS keystroke.")

	add("jaws_help",
		"with the add-on JAWS Migration Assistant: say what a JAWS keystroke or a JAWS command is in NVDA, what was "
		"brought over from JAWS, or which commands that add-on has",
		jawsHelp, asked, looks=True, title="Asking the JAWS Migration Assistant", tell=VERBATIM)
