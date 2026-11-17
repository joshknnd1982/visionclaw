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
