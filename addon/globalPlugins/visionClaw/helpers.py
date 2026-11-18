# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what VisionClaw has made for the user and keeps between sessions:
# app helpers (hotkeys for one program that click or read an item found by name in the window's picture), and
# small add-ons written by the coder model, loaded into NVDA without a restart.

import functools
import importlib.util
import json
import os
import threading
import traceback

import api
import globalPluginHandler
import inputCore
import ui
import wx
from .vclog import log

import addonHandler

from .claw import dragcontrol, match, microaddons, pointer

addonHandler.initTranslation()

CLICK, READ = "click", "read"
# How often an add-on is corrected by itself after failing, before it is turned off and the user is told.
MAX_AUTO_REPAIRS = 3


class Helpers:
	def __init__(self, plugin, folder):
		self._plugin = plugin
		self._path = os.path.join(folder, "helpers.json")
		self.store = microaddons.Store(os.path.join(folder, "addons"))
		self._lock = threading.Lock()
		# {program name: {normalized key: {"key", "action", "item"}}}
		self._bindings = {}
		self._loaded = {}
		# Add-ons that failed while running: what went wrong, and which are paused until they are corrected.
		self.errors = {}
		self._paused = set()
		try:
			with open(self._path, encoding="utf-8") as f:
				data = json.load(f)
			if isinstance(data, dict):
				self._bindings = data
		except FileNotFoundError:
			pass
		except (OSError, ValueError):
			log.warning("VisionClaw: could not read the app helpers", exc_info=True)

	# --- App helpers ---

	@staticmethod
	def keyId(key):
		"""NVDA's own spelling of a key, like "kb:alt+nvda+1", or None if it is not a key."""
		from keyboardHandler import KeyboardInputGesture
		try:
			KeyboardInputGesture.fromName(key.strip().replace(" ", ""))
			return inputCore.normalizeGestureIdentifier("kb:" + key.strip().replace(" ", ""))
		except Exception:
			return None

	def _save(self):
		try:
			tmp = self._path + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				json.dump(self._bindings, f, indent=1)
			os.replace(tmp, self._path)
		except OSError:
			log.warning("VisionClaw: could not save the app helpers", exc_info=True)

	def add(self, app, key, keyId, action, item):
		with self._lock:
			self._bindings.setdefault(app, {})[keyId] = {"key": key, "action": action, "item": item}
			self._save()

	def addBinding(self, app, keyId, binding):
		"""Keep a helper given as data. Used for controls that the arrow keys work."""
		with self._lock:
			self._bindings.setdefault(app, {})[keyId] = dict(binding)
			self._save()

	def binding(self, app, keyId):
		return self._bindings.get(app, {}).get(keyId) or {}

	def patch(self, app, keyId, values):
		"""Change what is kept of a helper, if it is still there."""
		with self._lock:
			kept = self._bindings.get(app, {}).get(keyId)
			if kept is None or all(kept.get(name) == value for name, value in values.items()):
				return
			kept.update(values)
			self._save()

	def scriptFor(self, gesture):
		"""The helper for a pressed key in the program in front, as a script, or None."""
		if not self._bindings:
			return None
		try:
			app = api.getForegroundObject().appModule.appName
		except Exception:
			return None
		bindings = self._bindings.get(app)
		if not bindings:
			return None
		for identifier in gesture.normalizedIdentifiers:
			binding = bindings.get(identifier)
			if binding is not None:
				if binding.get("action") == dragcontrol.ACTION:
					# A control kept for a website works only on that website; elsewhere the key is the program's.
					from . import controlkeys
					if binding.get("site") and controlkeys.siteNow() != binding["site"]:
						return None

					def script_controlHelper(gesture, binding=binding, identifier=identifier, app=app):
						self._plugin.controlKeys.takeSaved(app, identifier, binding)
					return script_controlHelper

				if binding.get("action") in (pointer.HOVER, pointer.HOLD) and binding.get("site"):
					from . import controlkeys
					if controlkeys.siteNow() != binding["site"]:
						return None

				def script_appHelper(gesture, binding=binding, identifier=identifier, app=app):
					if binding.get("action") == pointer.HOLD and self._plugin.pointerMode.letGo():
						return  # the second press of a hotkey that holds the mouse button down lets it go
					threading.Thread(
						target=self._run, args=(binding, app, identifier), name="visionClaw-helper", daemon=True).start()
				return script_appHelper
		return None

	def _place(self, binding, app, keyId):
		"""Where a hotkey's thing is on the screen now, as (point, name), for a hotkey that rests the pointer on
		it or holds it down. Raises LookupError with what to tell the user. Worker thread."""
		if binding.get("share") or binding.get("find"):
			# Found in an inspection: kept as a rule, a name in the picture, or a share of the window.
			from . import controlkeys, mousetools
			control = controlkeys.resolve(self._plugin, app, keyId, binding)
			box = mousetools._onMain(self._plugin.controlKeys._box)
			return dragcontrol.pointOf(control["share"], box), control.get("name") or binding.get("item") or ""
		result = self._plugin.clawScreen.items()
		index = match.best(binding["item"], self._plugin.clawScreen.names(result))
		if index is None:
			# Translators: Reported when an app helper's item is not in the window. {item} is its name.
			raise LookupError(_("{item} is not in this window right now.").format(item=binding["item"]))
		from . import mousetools
		point = mousetools._onMain(lambda: self._plugin.clawScreen.pointOf(result, result.items[index]))
		if point is None:
			raise LookupError(_("{item} is not in this window right now.").format(item=binding["item"]))
		return point, result.items[index]["text"]

	def _pointed(self, binding, app, keyId):
		"""A hotkey that rests the pointer on its thing and says what appears, or holds the mouse button down on
		it until the hotkey or Escape is pressed again."""
		from . import mousetools
		try:
			point, name = self._place(binding, app, keyId)
		except LookupError as e:
			wx.CallAfter(ui.message, str(e))
			return
		except Exception:
			log.error("VisionClaw: app helper failed", exc_info=True)
			wx.CallAfter(ui.message, _("VisionClaw could not read this window."))
			return
		mode = self._plugin.pointerMode
		if binding["action"] == pointer.HOLD:
			wx.CallAfter(mode.keepDown, point, name)
			return
		box = mousetools._onMain(mode._box)
		before, after = mousetools.rest(self._plugin._grab, box, point)
		found, text = mousetools.appearedText(before, after)
		# Translators: Spoken when a hotkey rested the mouse pointer on something and nothing new showed.
		wx.CallAfter(ui.message, text or (
			_("{name}: the window could not be looked at.").format(name=name) if found is None
			else _("{name}: something appeared, but no new text could be read.").format(name=name) if found
			else _("{name}: nothing appeared.").format(name=name)))

	def _run(self, binding, app="", keyId=""):
		"""Find the helper's item in the window as it looks now, and click or read it."""
		if binding.get("action") in (pointer.HOVER, pointer.HOLD):
			self._pointed(binding, app, keyId)
			return
		try:
			result = self._plugin.clawScreen.items()
		except Exception:
			log.error("VisionClaw: app helper failed", exc_info=True)
			# Translators: Reported when an app helper could not read the window.
			wx.CallAfter(ui.message, _("VisionClaw could not read this window."))
			return
		names = self._plugin.clawScreen.names(result)
		index = match.best(binding["item"], names)
		if index is None:
			# Translators: Reported when an app helper's item is not in the window. {item} is its name.
			wx.CallAfter(ui.message, _("{item} is not in this window right now.").format(item=binding["item"]))
			return
		item = result.items[index]
		if binding["action"] != READ:
			# click, double click or right click, as the helper was made
			wx.CallAfter(self._plugin.clawScreen.click, result, item, binding["action"])
			wx.CallAfter(ui.message, item["text"])
		else:
			following = result.items[index + 1]["text"] if index + 1 < len(result.items) else ""
			wx.CallAfter(ui.message, f"{item['text']} {following}".strip())

	# --- Add-ons written by the coder model ---

	def loadAddon(self, name):
		"""Check and start a stored add-on. Must be called on NVDA's main thread. Raises if it cannot start."""
		ident = microaddons.slug(name)
		source = self.store.source(ident)
		if source is None:
			raise LookupError(f"There is no add-on called {name}.")
		problems = microaddons.check(source)
		if problems:
			raise ValueError(" ".join(problems))
		self.unloadAddon(ident)
		spec = importlib.util.spec_from_file_location("visionClawAddon_" + ident, self.store.path(ident))
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		self._guard(module.GlobalPlugin, ident)
		self._paused.discard(ident)
		instance = module.GlobalPlugin()
		running = globalPluginHandler.runningPlugins
		running.add(instance) if hasattr(running, "add") else running.append(instance)
		self._loaded[ident] = instance
		self.store.setEnabled(ident, True)
		return instance

	def _guard(self, cls, ident):
		"""Put a guard around every key command and event of a generated add-on, so that an error in it never
		reaches NVDA: the error is caught and kept, NVDA's own handling still runs, the add-on is paused, and
		VisionClaw is told so the models can debug it."""
		for name in dir(cls):
			original = getattr(cls, name)
			if name.startswith(("script_", "event_")) and callable(original):
				setattr(cls, name, self._guarded(original, ident, name))

	def _guarded(self, original, ident, name):
		isEvent = name.startswith("event_")

		@functools.wraps(original)
		def guarded(instance, *args, **kwargs):
			nextHandler = args[1] if isEvent and len(args) > 1 and callable(args[1]) else None
			passedOn = []
			if nextHandler is not None:
				def once():
					passedOn.append(True)
					nextHandler()
				args = (args[0], once) + args[2:]
			if ident in self._paused:
				if nextHandler is not None:
					nextHandler()
				return None
			try:
				return original(instance, *args, **kwargs)
			except Exception as e:
				self._failed(ident, name, e, traceback.format_exc())
				# A failed event handler must not swallow the event: NVDA and other add-ons still get it.
				if nextHandler is not None and not passedOn:
					nextHandler()
				return None
		return guarded

	def _failed(self, ident, where, error, trace):
		first = ident not in self._paused
		self._paused.add(ident)
		entries = self.errors.setdefault(ident, [])
		entries.append({"where": where, "error": f"{type(error).__name__}: {error}", "trace": trace[-1500:]})
		del entries[:-5]
		log.error(f"VisionClaw: the add-on {ident} failed in {where}: {error}")
		if first:
			self._plugin.onAddonFailed(ident)

	def turnOff(self, name):
		"""Stop an add-on and keep it off after a restart. Main thread."""
		self.unloadAddon(name)
		self.store.setEnabled(microaddons.slug(name), False)

	def unloadAddon(self, name):
		instance = self._loaded.pop(microaddons.slug(name), None)
		if instance is None:
			return False
		running = globalPluginHandler.runningPlugins
		try:
			running.discard(instance) if hasattr(running, "discard") else running.remove(instance)
		except (KeyError, ValueError):
			pass
		try:
			instance.terminate()
		except Exception:
			log.debugWarning("VisionClaw: an add-on did not stop cleanly", exc_info=True)
		return True

	def loadEnabled(self):
		"""Start the add-ons that were on when NVDA last ran."""
		for meta in self.store.list():
			if meta.get("enabled"):
				try:
					self.loadAddon(meta["name"])
				except Exception as e:
					# An add-on that no longer starts, for example after an NVDA update, is debugged like one
					# that fails while running.
					self._failed(meta["name"], "starting", e, traceback.format_exc())

	def terminate(self):
		for name in list(self._loaded):
			self.unloadAddon(name)

	# --- Both ---

	def appLines(self, app):
		"""The hotkeys VisionClaw made for one program, as sentences."""
		lines = []
		for binding in dict(self._bindings.get(app, {})).values():
			if binding.get("action") == dragcontrol.ACTION:
				lines.append(f"{dragcontrol.describe(binding)}.")
			else:
				lines.append(f"{binding['key']} does {binding['action']} \"{binding['item']}\".")
		return lines

	def listText(self):
		lines = []
		for app, bindings in sorted(self._bindings.items()):
			for binding in bindings.values():
				if binding.get("action") == dragcontrol.ACTION:
					lines.append(f"App helper in {app}: {dragcontrol.describe(binding)}.")
					continue
				lines.append(f"App helper in {app}: {binding['key']} does {binding['action']} \"{binding['item']}\".")
		for meta in self.store.list():
			state = "on" if meta["name"] in self._loaded else "off"
			keys = microaddons.gestures(self.store.source(meta["name"]) or "")
			keyText = " Keys: " + ", ".join(k for k, _d in keys) + "." if keys else ""
			lines.append(f"Add-on {meta['name']} ({state}): {meta.get('purpose', '')}.{keyText}")
		return "\n".join(lines)

	def remove(self, name):
		"""Remove an add-on by name, or an app helper by its key. Main thread. Returns whether one was found."""
		ident = microaddons.slug(name)
		if self.store.meta(ident) is not None:
			self.unloadAddon(ident)
			return self.store.remove(ident)
		keyId = self.keyId(name)
		with self._lock:
			for app, bindings in list(self._bindings.items()):
				for identifier, binding in list(bindings.items()):
					if identifier == keyId or match.plain(binding["key"]) == match.plain(name):
						del bindings[identifier]
						if not bindings:
							del self._bindings[app]
						self._save()
						return True
		return False

	def export(self, name, folder):
		return self.store.package(name, folder)
