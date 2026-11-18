# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what NVDA has and uses: the speech synthesizer and its voices and settings, the braille display
# and its tables, the drivers that are installed, the add-ons, and NVDA itself. Read only: nothing here changes
# anything. Every function must be called on NVDA's main thread. Each part is asked for separately and guarded,
# because NVDA versions differ and a driver may not offer everything.

import re

import config

SPEECH, BRAILLE, ADDONS, GENERAL = "speech", "braille", "addons", "general"
TOPICS = [SPEECH, BRAILLE, ADDONS, GENERAL]
MAX_NAMES = 25
_PUNCTUATION = {0: "none", 100: "some", 200: "most", 300: "all"}


def topicOf(part):
	"""Which topic a question is about, from its words."""
	text = (part or "").lower()
	if re.search(r"braille|\bcells?\b|\bdots?\b", text):
		return BRAILLE
	if re.search(r"synthesi[sz]er|synth\b|voices?|speech|speak|eloquence|espeak|sapi|onecore|pitch|\brate\b", text):
		return SPEECH
	if re.search(r"add-?ons?|plug-?ins?", text):
		return ADDONS
	return GENERAL


def _try(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def _names(pairs, limit=MAX_NAMES):
	names = [str(name) for name in pairs]
	more = f", and {len(names) - limit} more" if len(names) > limit else ""
	return ", ".join(names[:limit]) + more


def _driverSettings(driver):
	"""The settings a synthesizer or braille display driver offers, with their values now."""
	lines = []
	for setting in _try(lambda: list(driver.supportedSettings), []) or []:
		ident = _try(lambda: setting.id)
		if not ident:
			continue
		name = _try(lambda: setting.displayName) or ident
		value = _try(lambda: getattr(driver, ident))
		choices = _try(lambda: getattr(driver, f"available{ident[0].upper()}{ident[1:]}s"))
		if choices:
			shown = _try(lambda: choices[value].displayName) or value
			lines.append(f"{name}: {shown} ({len(choices)} to choose from)")
		else:
			lines.append(f"{name}: {value}")
	return lines


def speech():
	import synthDriverHandler
	synth = synthDriverHandler.getSynth()
	lines = []
	if synth is None:
		lines.append("No speech synthesizer is running.")
	else:
		lines.append(f"Speech synthesizer in use: {_try(lambda: synth.description) or synth.name} (driver name {synth.name}).")
		voices = _try(lambda: synth.availableVoices) or {}
		current = _try(lambda: voices[synth.voice].displayName) or _try(lambda: synth.voice)
		if current:
			lines.append(f"Voice in use: {current}.")
		lines += [f"{line}." for line in _driverSettings(synth)]
		if voices:
			lines.append(f"Voices of this synthesizer ({len(voices)}): {_names(v.displayName for v in voices.values())}.")
	installed = _try(synthDriverHandler.getSynthList, []) or []
	if installed:
		lines.append(f"Synthesizers installed ({len(installed)}): {_names(description for _name, description in installed)}.")
	device = _try(lambda: config.conf["audio"]["outputDevice"]) or _try(lambda: config.conf["speech"]["outputDevice"])
	if device:
		lines.append(f"Audio output device: {device}.")
	level = _try(lambda: config.conf["speech"]["symbolLevel"])
	if level is not None:
		lines.append(f"Punctuation level: {_PUNCTUATION.get(level, level)}.")
	return "\n".join(lines)


def brailleInfo():
	import braille
	lines = []
	display = _try(lambda: braille.handler.display)
	name = _try(lambda: display.name)
	if display is None or name in (None, "noBraille"):
		lines.append("No braille display is in use.")
	else:
		lines.append(f"Braille display in use: {_try(lambda: display.description) or name} (driver name {name}).")
		cells = _try(lambda: braille.handler.displaySize)
		if cells:
			lines.append(f"It has {cells} cells.")
		port = _try(lambda: config.conf["braille"][name]["port"])
		if port:
			lines.append(f"Connection: {port}.")
		lines += [f"{line}." for line in _driverSettings(display)]
	for label, key in (("Output table", "translationTable"), ("Input table", "inputTable")):
		table = _try(lambda k=key: config.conf["braille"][k])
		if table:
			shown = _try(lambda t=table: __import__("brailleTables").getTable(t).displayName) or table
			lines.append(f"{label}: {shown}.")
	for label, key in (
		("Braille follows", "tetherTo"), ("Show cursor", "showCursor"), ("Cursor blinks", "cursorBlink"),
		("Show messages", "showMessages"), ("Message timeout in seconds", "messageTimeout"),
		("Word wrap", "wordWrap"), ("Expand to computer braille at the cursor", "expandAtCursor"),
		("Read by paragraph", "readByParagraph"), ("Focus context presentation", "focusContextPresentation"),
	):
		value = _try(lambda k=key: config.conf["braille"][k])
		if value is not None:
			lines.append(f"{label}: {'on' if value is True else 'off' if value is False else value}.")
	installed = _try(lambda: braille.getDisplayList(), []) or []
	if installed:
		lines.append(f"Braille display drivers installed ({len(installed)}): {_names(d for _n, d in installed)}.")
	return "\n".join(lines)


def _classOf(thing):
	return f"{type(thing).__module__}.{type(thing).__qualname__}"


def _classNames(things):
	return ", ".join(sorted({getattr(thing, "__name__", str(thing)) for thing in things or ()}))


def speechInside():
	"""How NVDA drives the speech synthesizer in use, in the names of NVDA's own code. For the audit and for
	people who write add-ons."""
	import synthDriverHandler
	synth = synthDriverHandler.getSynth()
	if synth is None:
		return ["No speech synthesizer is running, so there is no driver to describe."]
	lines = [
		f"The driver in use is the class {_classOf(synth)}, reached as synthDriverHandler.getSynth().",
		"NVDA hands it what to say with speak(speechSequence), silences it with cancel() and pauses it with pause(switch).",
	]
	settings = [_try(lambda s=setting: s.id) for setting in _try(lambda: list(synth.supportedSettings), []) or []]
	if settings:
		lines.append(f"Its settings, each an attribute of the driver: {', '.join(s for s in settings if s)}.")
	commands = _classNames(_try(lambda: synth.supportedCommands))
	lines.append(
		f"Speech commands it understands: {commands}." if commands
		else "It lists no speech commands, so it speaks plain text only.")
	notifications = _try(lambda: len(synth.supportedNotifications), 0) or 0
	lines.append(
		f"It reports back to NVDA in {notifications} ways (synthIndexReached, synthDoneSpeaking), which say all and "
		"speech callbacks depend on." if notifications
		else "It does not report back how far it has spoken, so say all cannot follow it exactly.")
	voices = _try(lambda: len(synth.availableVoices), 0) or 0
	languages = _try(lambda: len(synth.availableLanguages), 0) or 0
	lines.append(f"It offers {voices} voices in {languages} languages.")
	mode = _try(lambda: __import__("speech").getState().speechMode)
	if mode is not None:
		lines.append(f"NVDA's speech mode now: {_try(lambda: mode.displayString) or _try(lambda: mode.name) or mode}.")
	installed = _try(synthDriverHandler.getSynthList, []) or []
	lines.append(f"Installed synthesizer drivers ({len(installed)}): {_names(f'{d} ({n})' for n, d in installed)}.")
	return lines


def brailleInside():
	"""How NVDA drives the braille display in use, in the names of NVDA's own code."""
	import braille
	handler = _try(lambda: braille.handler)
	if handler is None:
		return ["Braille is not running in this NVDA."]
	display = _try(lambda: handler.display)
	lines = [f"The braille handler is the class {_classOf(handler)}, reached as braille.handler."]
	if display is None:
		lines.append("It has no display driver now.")
	else:
		lines.append(f"The display driver in use is the class {_classOf(display)}, reached as braille.handler.display.")
		lines.append(
			f"It has {_try(lambda: display.numCells, 0)} cells in {_try(lambda: display.numRows, 1)} row or rows; NVDA "
			"writes to it with display(cells), one number of dots for each cell.")
		keys = _try(lambda: len(list(display.gestureMap.getScriptsForAllGestures())), None)
		if keys is not None:
			lines.append(f"Its own keys are tied to {keys} NVDA commands through its gestureMap.")
		settings = [_try(lambda s=setting: s.id) for setting in _try(lambda: list(display.supportedSettings), []) or []]
		if settings:
			lines.append(f"Its settings, each an attribute of the driver: {', '.join(s for s in settings if s)}.")
		lines.append(
			f"Found by itself when plugged in: {'yes' if _try(lambda: display.supportsAutomaticDetection) else 'no'}. "
			f"Safe to write to from a background thread: {'yes' if _try(lambda: display.isThreadSafe) else 'no'}.")
	lines.append(
		f"Braille is {'on' if _try(lambda: handler.enabled) else 'off'}; NVDA counts {_try(lambda: handler.displaySize, 0)} "
		f"cells; braille follows: {_try(lambda: handler.getTether()) or 'unknown'}.")
	tables = _try(lambda: len(__import__("brailleTables").listTables()), 0) or 0
	if tables:
		lines.append(f"Braille tables that can be chosen: {tables}.")
	installed = _try(lambda: braille.getDisplayList(excludeNegativeChecks=False), None) or _try(lambda: braille.getDisplayList(), []) or []
	lines.append(f"Installed braille display drivers ({len(installed)}): {_names((f'{d} ({n})' for n, d in installed), 60)}.")
	return lines


def addons():
	import addonHandler
	found = []
	for addon in _try(lambda: list(addonHandler.getAvailableAddons()), []) or []:
		name = _try(lambda a=addon: a.manifest["summary"]) or _try(lambda a=addon: a.name) or "?"
		version = _try(lambda a=addon: a.manifest["version"]) or "?"
		state = "disabled" if _try(lambda a=addon: a.isDisabled) else "enabled"
		found.append(f"{name} {version} ({state})")
	if not found:
		return "No add-ons are installed."
	return f"Add-ons installed ({len(found)}): " + "; ".join(found[:40]) + "."


def general():
	lines = []
	version = _try(lambda: __import__("buildVersion").version)
	if version:
		lines.append(f"NVDA version: {version}.")
	profiles = _try(lambda: [p.name or "normal configuration" for p in config.conf.profiles])
	if profiles:
		lines.append(f"Configuration profile in use: {profiles[-1]}.")
	layout = _try(lambda: config.conf["keyboard"]["keyboardLayout"])
	if layout:
		lines.append(f"Keyboard layout: {layout}.")
	language = _try(lambda: __import__("languageHandler").getLanguage())
	if language:
		lines.append(f"NVDA's language: {language}.")
	first = (_try(speech) or "").split("\n")[0]
	if first:
		lines.append(first)
	first = (_try(brailleInfo) or "").split("\n")[0]
	if first:
		lines.append(first)
	return "\n".join(lines) or "Nothing could be read from NVDA."


def about(topic):
	"""Everything about one topic, the most important first."""
	return {SPEECH: speech, BRAILLE: brailleInfo, ADDONS: addons}.get(topic, general)() or "Nothing could be read from NVDA."
