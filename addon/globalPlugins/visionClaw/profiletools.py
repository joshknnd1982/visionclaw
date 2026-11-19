# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - an NVDA setting changed only for the program in front, with NVDA's own configuration profiles.
# What a request asks for is read by claw/profiles.py; this file does what NVDA itself does in its window
# "Configuration profiles" when a new profile is made for the current application.
#
# Read from NVDA's source, branch release-2026.3, on 2026-11-18; read it again before changing anything here:
#   config/__init__.py     ConfigManager: a change is written to the profile activated last (profiles[-1],
#                          AggregatedSection._getUpdateSection); createProfile(name) makes an empty profile and
#                          raises ValueError when the name is taken; triggersToProfiles maps "app:<name>" to a
#                          profile's name and is saved with saveProfileTriggers(); deleteProfile(name) also takes
#                          its triggers away; a profile turned on by hand always stays on top of the triggered
#                          ones; the sections in BASE_ONLY_SECTIONS cannot be in a profile; nothing is made
#                          when NVDAState.shouldWriteToDisk() says no; an entered trigger does nothing while
#                          profileTriggersEnabled is False or the triggers are suspended.
#   appModuleHandler.py    handleAppSwitch: when a program comes to the front, NVDA makes
#                          AppProfileTrigger(appName), keeps it on the program's module as _configProfileTrigger
#                          and calls enter(); when the program leaves the front, it calls exit() on it.
#   gui/configProfiles.py  NewProfileDialog.onOk: createProfile, triggersToProfiles[spec] = name,
#                          saveProfileTriggers, enableProfileTriggers; the profile then starts to apply when the
#                          program gets the focus again.
#
# A profile that was only just made does not apply until its program gets the focus again. VisionClaw is asked
# while the program is in front, so it enters the program's trigger the way handleAppSwitch does. Before every
# write it is checked that the program's profile is the one NVDA writes to; if it is not, nothing is written.
# Every function here runs on NVDA's main thread.

import time

import api
import config

from .claw import profiles
from .vclog import log


class NotPossible(Exception):
	"""A setting cannot be kept for this program now. The message is a sentence for the user; nothing changed."""


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def front():
	"""The program in front as NVDA knows it: (its module, facts for claw/profiles.py)."""
	focus = _safe(api.getFocusObject)
	fg = _safe(api.getForegroundObject)
	module = _safe(lambda: focus.appModule) or _safe(lambda: fg.appModule)
	facts = {
		"app": str(_safe(lambda: module.appName) or ""),
		"product": str(_safe(lambda: module.productName) or ""),
		"title": str(_safe(lambda: fg.name) or ""),
	}
	return module, facts


# A question to the user is a window of NVDA. While it is open the program is not in front, and NVDA has turned
# the program's profile off; when it closes, NVDA needs a moment to notice that the program is in front again.
SETTLE_SECONDS = 3.0
SETTLE_STEP = 0.1


def settle(isBack, check=None, seconds=None):
	"""Wait until isBack() says that the program is in front again, as NVDA sees it; at most a few seconds.
	check() ends the wait when the request is stopped. Returns whether it is back. Not on the main thread."""
	deadline = time.monotonic() + (SETTLE_SECONDS if seconds is None else seconds)
	while True:
		if isBack():
			return True
		if time.monotonic() >= deadline:
			return False
		if check is not None:
			check()
		time.sleep(SETTLE_STEP)


def _name(profile):
	return getattr(profile, "name", None)


def _stack():
	"""The profiles that are on, the one NVDA writes to last; a list with None where NVDA does not say."""
	return list(getattr(config.conf, "profiles", None) or [None])


def top():
	"""The name of the profile NVDA writes changes to now; None for its normal configuration."""
	return _name(_stack()[-1])


def manual():
	"""The name of a profile the user turned on by hand, or ""."""
	stack = _stack()
	return str(_name(stack[-1]) or "") if len(stack) > 1 and getattr(stack[-1], "manual", False) else ""


def _canWrite():
	try:
		import NVDAState
		return bool(NVDAState.shouldWriteToDisk())
	except Exception:
		return True


def baseOnly(settingId):
	"""Whether NVDA keeps a setting the same for every program."""
	section = str(settingId).split(".")[0]
	return section in getattr(config.conf, "BASE_ONLY_SECTIONS", ())


def mapped(app):
	"""The profile NVDA turns on for a program, or None. A profile whose file is gone counts as none."""
	name = _safe(lambda: config.conf.triggersToProfiles.get("app:" + app))
	if name and name in list(config.conf.listProfiles()):
		return name
	return None


def check(named, settingId):
	"""Before the user is asked: the program in front, the profile it has (or None) and its facts. Raises
	NotPossible with the reason when a setting cannot be kept for this program."""
	module, facts = front()
	app = facts["app"].lower()
	if module is None or app in profiles.NOT_A_PROGRAM:
		raise NotPossible(profiles.NO_PROGRAM)
	if named and not profiles.fits(named, facts):
		raise NotPossible(profiles.notHere(named, profiles.shown(facts)))
	if baseOnly(settingId):
		raise NotPossible(profiles.BASE_ONLY)
	if not _canWrite():
		raise NotPossible(profiles.READ_ONLY)
	if not getattr(config.conf, "profileTriggersEnabled", True):
		raise NotPossible(profiles.TRIGGERS_OFF)
	byHand = manual()
	if byHand:
		raise NotPossible(profiles.manualOn(byHand))
	return module, facts, mapped(facts["app"])


def _enter(module):
	"""Make NVDA apply the profile of the program in front now, as it does when the program gets the focus
	(appModuleHandler.handleAppSwitch)."""
	import appModuleHandler
	old = getattr(module, "_configProfileTrigger", None)
	if old is not None:
		old.exit()
	trigger = module._configProfileTrigger = appModuleHandler.AppProfileTrigger(module.appName)
	trigger.enter()


def activate(module):
	"""The profile of the program in front, made if there is none, and on top so that NVDA writes to it.
	Returns (its name, whether it was made now). Raises NotPossible, with nothing left behind, when NVDA does
	not turn it on."""
	conf = config.conf
	app = module.appName
	name = mapped(app)
	created = False
	if name is None:
		name = profiles.profileName(app, list(conf.listProfiles()))
		conf.createProfile(name)
		conf.triggersToProfiles["app:" + app] = name
		conf.saveProfileTriggers()
		created = True
		log.info(f"VisionClaw: made the configuration profile {name!r} for the program {app!r}")
	try:
		if top() != name:
			_enter(module)
	except Exception:
		log.error("VisionClaw: the program's configuration profile could not be turned on", exc_info=True)
	if top() != name:
		if created:
			forget(name)
		raise NotPossible(profiles.notActive(profiles.shown({"app": app, "product": _safe(lambda: module.productName)})))
	return name, created


def onTop():
	"""What NVDA writes changes to now: (the program's own profile that is on, or ""; a profile turned on by hand,
	or ""; the program's module; its facts)."""
	module, facts = front()
	byHand = manual()
	name = top()
	app = facts["app"]
	own = name if name and not byHand and name == mapped(app) else ""
	return own, byHand, module, facts


def writeBase(module, setting, raw=None, value=None):
	"""Write a setting into NVDA's normal configuration while the program in front has a profile of its own that
	is on. The program's trigger is left and entered again, as NVDA does when the program loses and gets the
	focus, so that for the moment of the write NVDA's normal configuration is the one it writes to; if it is
	not, nothing is written. raw: the new value as the user or a model wrote it, read against the normal
	configuration's own value; value: the value itself. Returns (what it was, as shown; what it was; the new
	value; what it is, as shown; the program's own value as shown, where it has one and keeps it, else "")."""
	import appModuleHandler
	trigger = getattr(module, "_configProfileTrigger", None)
	if trigger is None:
		raise NotPossible(profiles.OTHER_PROFILE)
	trigger.exit()
	try:
		if top() is not None:
			raise NotPossible(profiles.OTHER_PROFILE)
		old, before = setting.shown(), setting.read()
		new = setting.parse(raw) if value is None else value
		setting.write(new)
		now = setting.shown()
	finally:
		again = module._configProfileTrigger = appModuleHandler.AppProfileTrigger(module.appName)
		again.enter()
	own = setting.shown() if setting.read() != new else ""
	return old, before, new, now, own


def _profileData(name):
	"""What a profile holds, as nested dictionaries: as NVDA has it in memory when it was used in this session,
	else from its file. {} when it cannot be read."""
	try:
		return config.conf.getProfile(name)
	except Exception:
		pass
	try:
		import NVDAState
		from configobj import ConfigObj
		return ConfigObj(NVDAState.WritePaths.getProfileConfigFile(name), encoding="UTF-8")
	except Exception:
		return {}


def holders(path, besides=""):
	"""The programs whose own profile holds a value for a setting, by the setting's place in NVDA's
	configuration; besides: a profile that is left out. Only looks; a profile that cannot be read holds nothing."""
	found = []
	if not path:
		return found
	existing = set(config.conf.listProfiles())
	for spec, name in sorted(dict(config.conf.triggersToProfiles).items()):
		app = profiles.appOf(spec)
		if not app or name not in existing or name == besides:
			continue
		node = _profileData(name)
		try:
			for part in path:
				node = node[part]
		except (KeyError, TypeError):
			continue
		if not hasattr(node, "items"):
			found.append(profiles.SAID.get(app.lower(), app))
	return found


def forget(name):
	"""Take away a profile that was made a moment ago and holds nothing."""
	try:
		config.conf.deleteProfile(name)
	except Exception:
		log.error(f"VisionClaw: the configuration profile {name!r} could not be taken away again", exc_info=True)


def write(name, setting, value):
	"""Write a setting into a program's profile. Only when that profile is the one NVDA writes to at this
	moment; otherwise nothing is written and NotPossible is raised."""
	if top() != name:
		raise NotPossible(profiles.notActive(name))
	setting.write(value)


def listed(changes):
	"""Every program that has a profile of its own: [(program, profile, on now, [what VisionClaw changed there])].
	changes: the changes VisionClaw made that still stand."""
	found = []
	active = {str(_name(profile)) for profile in config.conf.profiles[1:]}
	existing = set(config.conf.listProfiles())
	for spec, name in sorted(dict(config.conf.triggersToProfiles).items()):
		app = profiles.appOf(spec)
		if not app or name not in existing:
			continue
		mine = [
			f"{change['label']} from {change['oldShown']} to {change['newShown']}."
			for change in changes if change.get("profile") == name]
		found.append((app, name, name in active, mine))
	return found


def profileFor(named):
	"""For a request to remove a program's settings: (program as said to the user, its profile or None).
	named: the program the user named, or "" for the one in front."""
	_module, facts = front()
	if not named or profiles.fits(named, facts):
		app = facts["app"]
		return profiles.shown(facts), (mapped(app) if app.lower() not in profiles.NOT_A_PROGRAM else None)
	wanted = profiles.ALIASES.get(" ".join(named.lower().split()), "".join(named.lower().split()))
	for spec, name in dict(config.conf.triggersToProfiles).items():
		app = profiles.appOf(spec)
		if app and (app.lower() == wanted or app.lower() == named.lower() or str(name).lower() == named.lower()):
			return named, (name if name in list(config.conf.listProfiles()) else None)
	return named, None


def remove(name):
	"""Delete a program's profile, and with it NVDA's trigger for it."""
	if not _canWrite():
		raise NotPossible(profiles.READ_ONLY)
	config.conf.deleteProfile(name)
	log.info(f"VisionClaw: deleted the configuration profile {name!r}")
