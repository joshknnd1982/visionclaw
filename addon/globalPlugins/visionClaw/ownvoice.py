# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a voice of its own, which the user sets in NVDA's own Speech settings: any synthesizer, voice,
# rate, pitch and volume NVDA has. The owner said on 2026-11-18: "instead of changing the voice pitch while
# visionclaw is speaking, drop me into nvda speech settings so I can fully customise visionclaw's voice."
#
# It is done the way NVDA gives "say all" a voice of its own, read from NVDA's source (branch release-2026.3, on
# 2026-11-18; read it again before changing anything here):
#   speech/commands.py   ConfigProfileTriggerCommand(trigger, enter=True) "applies (or stops applying) a
#                        configuration profile trigger to subsequent speech".
#   speech/manager.py    The speech manager enters the trigger when that speech begins, applies the profile's
#                        speech settings, leaves it again by itself at the end of the speech or when speech is
#                        cancelled, and ignores a trigger that has no profile.
#   speech/sayAll.py     SayAllProfileTrigger(config.ProfileTrigger) with spec = "sayAll": a trigger is a class
#                        with a spec; config.conf.triggersToProfiles maps the spec to a profile's name.
#   gui/__init__.py      mainFrame.popupSettingsDialog(NVDASettingsDialog, SpeechSettingsPanel) opens the Speech
#                        settings, as NVDA's own menu does.
#   config/__init__.py   A profile is edited by turning it on by hand (manualActivateProfile): while it is on,
#                        NVDA's settings windows read from it and write to it.
# So VisionClaw's voice is one configuration profile, tied to a trigger of VisionClaw's own. To let the user set
# it, the profile is turned on by hand and NVDA's Speech settings are opened; when that window is closed, the
# profile is turned off again, and the user's own voice is back. Nothing of the user's own settings is touched.

import re

import config
import ui
import wx

from .vclog import log

SPEC = "visionClaw:voice"
PROFILE = "VisionClaw voice"
# How often it is looked whether NVDA's settings window is still open, and when the first look is.
WATCH_MS, FIRST_LOOK_MS = 1000, 2500
CUSTOMISE, REMOVE = "customise", "remove"
_REMOVE = re.compile(r"\b(remove|delete|get rid of|reset|forget|throw away)\b", re.IGNORECASE)
_CUSTOMISE = re.compile(
	r"\b(customi[sz]e|change|choose|set up|setup|pick|adjust|configure|select|give|make|want|different|another|new|"
	r"speech settings)\b", re.IGNORECASE)
_OFF = re.compile(r"\b(turn|switch)\b.{0,40}\boff\b|\b(disable|stop using|no longer use|same (voice|as nvda)|like nvda)\b", re.IGNORECASE)
_ON = re.compile(r"\b(turn|switch)\b.{0,40}\bon\b|\b(enable|use|start using)\b", re.IGNORECASE)
_ASKS = re.compile(r"^\s*(is|are|does|do|what|which|how|why|has|have)\b|\?\s*$", re.IGNORECASE)

QUESTION = (
	"VisionClaw can speak with a voice of its own, so that you can tell it from NVDA. NVDA's Speech settings will "
	"open, and whatever you choose there, the synthesizer, the voice, its rate, pitch and volume, is for VisionClaw "
	"alone, kept in an NVDA configuration profile called {name}. While that window is open, NVDA itself speaks with "
	"that voice too, so that you hear what you choose. When you close it, your own voice is back. Open it now?")
OPENED = (
	"NVDA's Speech settings are open, for VisionClaw's voice. Choose the synthesizer, voice, rate, pitch and volume "
	"you want VisionClaw to have, and press OK. Until you close that window, NVDA itself speaks with that voice too.")
CLOSED = "VisionClaw's voice is set. NVDA speaks with your own voice again, and VisionClaw with the one you chose."
SETTINGS_OPEN = "NVDA's settings window is open. Close it first, then ask again."
NOT_KEPT = (
	"This NVDA cannot keep new settings on this computer, as on a sign-in screen, so VisionClaw cannot have a voice "
	"of its own here.")


class VoiceTrigger(config.ProfileTrigger):
	"""The trigger for what VisionClaw says, as NVDA's own SayAllProfileTrigger is for say all."""

	spec = SPEC


_trigger = None


def trigger():
	global _trigger
	if _trigger is None:
		_trigger = VoiceTrigger()
	return _trigger


def profileName():
	"""The profile that holds VisionClaw's voice, or "" when the user has not set one."""
	try:
		name = config.conf.triggersToProfiles.get(SPEC)
		return name if name and name in list(config.conf.listProfiles()) else ""
	except Exception:
		return ""


def say(text, own=True):
	"""Speak and braille a message of VisionClaw's: with VisionClaw's own voice where the user has set one and has
	it on, else exactly as NVDA speaks. Braille is the same either way. Main thread."""
	if own and profileName():
		try:
			import braille
			import speech
			from speech.commands import ConfigProfileTriggerCommand
			# NVDA leaves the trigger again by itself when these words are over or speech is cancelled.
			speech.speak([ConfigProfileTriggerCommand(trigger(), True), text])
			braille.handler.message(text)
			return
		except Exception:
			# Whatever goes wrong with the voice, the words are still said.
			log.debugWarning("VisionClaw: the message could not be spoken in its own voice", exc_info=True)
	ui.message(text)


def _settingsOpen():
	"""Whether NVDA's settings window is open."""
	try:
		from gui.settingsDialogs import NVDASettingsDialog
		return any(isinstance(window, NVDASettingsDialog) for window in wx.GetTopLevelWindows())
	except Exception:
		return False


def _byHand():
	"""The name of a profile that is turned on by hand, or ""."""
	stack = list(getattr(config.conf, "profiles", None) or [None])
	return str(getattr(stack[-1], "name", "") or "") if len(stack) > 1 and getattr(stack[-1], "manual", False) else ""


def _canKeep():
	try:
		import NVDAState
		return bool(NVDAState.shouldWriteToDisk())
	except Exception:
		return True


def check():
	"""Why VisionClaw's voice cannot be set now, as a sentence, or "". Main thread."""
	if not _canKeep():
		return NOT_KEPT
	if _settingsOpen():
		return SETTINGS_OPEN
	other = _byHand()
	if other and other != profileName():
		return (
			f"The configuration profile {other} is turned on by hand. Turn it off first, in NVDA's Configuration "
			"profiles window, NVDA+Control+P, then ask again.")
	return ""


def customise(say=None):
	"""Open NVDA's Speech settings for VisionClaw's voice: the profile is made if there is none, turned on by
	hand so that the settings window reads and writes it, and turned off again when that window is closed. Only
	after the user said yes. Returns the sentence for the user. Main thread."""
	problem = check()
	if problem:
		return problem
	import gui
	from gui.settingsDialogs import NVDASettingsDialog, SpeechSettingsPanel
	conf = config.conf
	name = profileName()
	if not name:
		taken = {str(existing).lower() for existing in conf.listProfiles()}
		name = next(candidate for candidate in [PROFILE] + [f"{PROFILE} {n}" for n in range(2, 30)] if candidate.lower() not in taken)
		conf.createProfile(name)
		conf.triggersToProfiles[SPEC] = name
		conf.saveProfileTriggers()
		log.info(f"VisionClaw: made the configuration profile {name!r} for its own voice")
	conf.manualActivateProfile(name)
	try:
		# Opened as NVDA's menu opens it, then the focus is put on the Voice combo box, or the rate where the synthesizer
		# has no voices, instead of the page's first control (focustools.py).
		from . import focustools
		focustools.openAt(NVDASettingsDialog, SpeechSettingsPanel, _voiceControl)
	except Exception:
		conf.manualActivateProfile(None)
		raise
	wx.CallLater(FIRST_LOOK_MS, _watch, name, say or ui.message)
	return OPENED


def _voiceControl(panel):
	"""The control of NVDA's Speech settings for choosing a voice: the Voice combo box, else the rate slider, as NVDA names
	them (gui/settingsDialogs.py: SpeechSettingsPanel.voicePanel, AutoSettingsMixin's f"{setting.id}List" and
	f"{setting.id}Slider"); None where neither is there."""
	voices = getattr(panel, "voicePanel", None)
	return getattr(voices, "voiceList", None) or getattr(voices, "rateSlider", None)


def _watch(name, say):
	"""Once NVDA's settings window is closed, the profile is turned off again, and the user's own voice is back."""
	try:
		if _settingsOpen():
			wx.CallLater(WATCH_MS, _watch, name, say)
			return
		if _byHand() == name:
			config.conf.manualActivateProfile(None)
		say(CLOSED)
	except Exception:
		log.error("VisionClaw: the profile of its own voice could not be turned off again", exc_info=True)


def remove():
	"""Delete the profile of VisionClaw's voice. Returns whether there was one. Main thread."""
	name = profileName()
	if not name:
		return False
	config.conf.deleteProfile(name)
	return True


def wish(part):
	"""What the user's words ask of VisionClaw's own voice: CUSTOMISE (set it in NVDA's Speech settings), REMOVE,
	True (use it), False (do not use it), or None when they only ask about it."""
	text = " ".join(str(part or "").split())
	if _REMOVE.search(text):
		return REMOVE
	if _OFF.search(text):
		return False
	if _ASKS.search(text) and not _CUSTOMISE.search(text):
		return None
	if _CUSTOMISE.search(text):
		return CUSTOMISE
	if _ON.search(text):
		return True
	return None


def stateText(on):
	name = profileName()
	if not name:
		return (
			"VisionClaw speaks with NVDA's own voice now. It can have a voice of its own, which you set in NVDA's own "
			"Speech settings: any synthesizer, voice, rate, pitch and volume. To set it, say: customise VisionClaw's voice.")
	if not on:
		return (
			f"VisionClaw has a voice of its own, kept in the configuration profile {name}, but it is turned off, so "
			"VisionClaw speaks exactly as NVDA does. To use it, say: turn VisionClaw's own voice on.")
	return (
		f"VisionClaw speaks with a voice of its own, kept in the NVDA configuration profile {name}. To change it, say: "
		"customise VisionClaw's voice. To speak like NVDA again, say: turn VisionClaw's own voice off.")
