# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A stand-in for NVDA's configuration with its configuration profiles, for tests without NVDA.

Written from NVDA's own source (config/__init__.py and appModuleHandler.py, branch release-2026.3, read on
2026-11-18), so that it behaves as NVDA does in what matters to VisionClaw:

  - the profiles that are on are a stack; a value is read from the one turned on last that has it, and a change
    is written to the one turned on last;
  - a profile turned on by hand always stays on top of the ones that programs turn on;
  - createProfile makes an empty profile and raises ValueError when the name is taken; deleteProfile takes the
    profile's triggers away with it and raises LookupError when there is none;
  - a program's trigger is "app:" and the name of its file; entering a trigger whose profile is not in
    triggersToProfiles does nothing, and neither does any trigger while triggers are switched off;
  - the sections in BASE_ONLY_SECTIONS are always read from, and written to, the normal configuration.

It is a stand-in: what NVDA really does is only known from a run inside NVDA.
"""


class Profile(dict):
	def __init__(self, name):
		super().__init__()
		self.name, self.manual, self.triggered = name, False, False


class Section:
	"""One section of the configuration as it counts now, over all the profiles that are on."""

	def __init__(self, manager, path):
		self._manager, self._path = manager, path

	def _layers(self):
		"""This section in every profile that is on, the one turned on last first; None where it has none."""
		found = []
		for profile in reversed(self._manager.profiles):
			node = profile
			for part in self._path:
				node = node.get(part) if isinstance(node, dict) else None
				if node is None:
					break
			found.append(node if isinstance(node, dict) else None)
		return found

	def __getitem__(self, key):
		layers = self._layers()
		if self._path and self._path[0] in self._manager.BASE_ONLY_SECTIONS:
			layers = layers[-1:]
		isSection = False
		for layer in layers:
			if layer is None or key not in layer:
				continue
			if isinstance(layer[key], dict):
				isSection = True
				continue
			return layer[key]
		if isSection:
			return Section(self._manager, self._path + (key,))
		raise KeyError(key)

	def get(self, key, default=None):
		try:
			return self[key]
		except KeyError:
			return default

	def __contains__(self, key):
		try:
			self[key]
			return True
		except KeyError:
			return False

	def __setitem__(self, key, value):
		base = self._path and self._path[0] in self._manager.BASE_ONLY_SECTIONS
		node = self._manager.profiles[0] if base else self._manager.profiles[-1]
		for part in self._path:
			node = node.setdefault(part, {})
		node[key] = value
		self._manager.writes.append((self._manager.profiles[0 if base else -1].name, ".".join(self._path + (key,)), value))

	def items(self):
		keys = []
		for layer in self._layers():
			for key in layer or ():
				if key not in keys:
					keys.append(key)
		return [(key, self[key]) for key in keys]


class Manager:
	"""NVDA's config.conf. base: the normal configuration, a dict of sections that makes a section's default
	values when it is first asked for (the Conf of tests/test_nvda_stub.py), or a plain dict."""

	BASE_ONLY_SECTIONS = {"general", "update", "development", "addonStore", "remote", "math", "screenCurtain"}

	def __init__(self, base, spec=None):
		normal = Profile(None)
		self._base = base
		self.spec = spec if spec is not None else getattr(base, "spec", {})
		self.profiles = [normal]
		self._files = {}
		self.triggersToProfiles = {}
		self.profileTriggersEnabled = True
		self.saved = 0
		self.switches = 0
		# (the profile written to, or None for the normal configuration; the setting; the value), in order.
		self.writes = []
		self.canWrite = True
		normal.update(base)
		self._normal = normal

	def __getitem__(self, key):
		if key not in self._normal:
			# The normal configuration makes a section's default values when it is first asked for.
			self._normal[key] = self._base[key]
		return Section(self, (key,))

	def __contains__(self, key):
		return key in self._normal or key in self.spec

	def listProfiles(self):
		return iter(sorted(self._files))

	def createProfile(self, name):
		if not self.canWrite:
			return
		if not name:
			raise ValueError("Missing name.")
		if name in self._files:
			raise ValueError("A profile with the same name already exists: %s" % name)
		self._files[name] = Profile(name)

	def deleteProfile(self, name):
		if not self.canWrite:
			return
		if name not in self._files:
			raise LookupError("No such profile: %s" % name)
		profile = self._files.pop(name)
		for spec in [spec for spec, mapped in self.triggersToProfiles.items() if mapped == name]:
			del self.triggersToProfiles[spec]
		self.saveProfileTriggers()
		if profile in self.profiles:
			self.profiles.remove(profile)
			self.switches += 1

	def saveProfileTriggers(self):
		self.saved += 1

	def getProfile(self, name):
		return self._files[name]

	def manualActivateProfile(self, name):
		if len(self.profiles) > 1 and self.profiles[-1].manual:
			self.profiles.pop().manual = False
		if name:
			profile = self._files[name]
			profile.manual = True
			self.profiles.append(profile)
		self.switches += 1

	def _triggerProfileEnter(self, trigger):
		if not self.profileTriggersEnabled:
			return
		profile = trigger._profile = self._files[trigger.profileName]
		profile.triggered = True
		if len(self.profiles) > 1 and self.profiles[-1].manual:
			self.profiles.insert(-1, profile)
		else:
			self.profiles.append(profile)
		self.switches += 1

	def _triggerProfileExit(self, trigger):
		if not self.profileTriggersEnabled:
			return
		profile = trigger._profile
		if profile is None:
			return
		profile.triggered = False
		if profile in self.profiles:
			self.profiles.remove(profile)
			self.switches += 1

	def disableProfileTriggers(self):
		self.profileTriggersEnabled = False
		keep = self.profiles[-1] if len(self.profiles) > 1 and self.profiles[-1].manual else None
		self.profiles[1:] = [keep] if keep else []

	def enableProfileTriggers(self):
		self.profileTriggersEnabled = True


def triggerClass(holder):
	"""NVDA's AppProfileTrigger, for the configuration that holder() gives."""

	class AppProfileTrigger:
		def __init__(self, appName):
			self.spec = "app:%s" % appName
			self.profileName = None
			self._profile = None

		def enter(self):
			conf = holder()
			try:
				self.profileName = conf.triggersToProfiles[self.spec]
			except KeyError:
				self.profileName = None
				return
			try:
				conf._triggerProfileEnter(self)
			except Exception:
				pass  # NVDA writes this to its log and goes on

		def exit(self):
			if not self.profileName:
				return
			holder()._triggerProfileExit(self)

	return AppProfileTrigger


class Module:
	"""A program as NVDA knows it."""

	def __init__(self, appName, productName=""):
		self.appName, self.productName = appName, productName
		self._configProfileTrigger = None


def switch(trigger, old, new):
	"""What NVDA does when another program comes to the front (appModuleHandler.handleAppSwitch)."""
	if old is not None and old._configProfileTrigger is not None:
		old._configProfileTrigger.exit()
		old._configProfileTrigger = None
	if new is not None:
		new._configProfileTrigger = trigger(new.appName)
		new._configProfileTrigger.enter()
