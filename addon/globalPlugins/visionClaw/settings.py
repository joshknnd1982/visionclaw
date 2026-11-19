# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - settings panel in NVDA's Settings dialog.

import os

import addonHandler
import config
import gui
import wx
from gui import guiHelper

from . import clawui, padtools
from .claw import backend, busy, debuglog, memories, modelpick, policy, updates
from .claw import voice as voiceWords

addonHandler.initTranslation()

CONF_SECTION = "visionClaw"
SEARCH_IDS = ("duckduckgo", "google", "bing")
SEARCH_ENGINES = ["DuckDuckGo", "Google", "Bing"]


def backendLabels():
	return [
		# Translators: Choices for where the AI models run.
		_("Automatic: dedicated graphics card, then Vulkan, then the processor"),
		_("Dedicated graphics card"),
		_("Vulkan: any graphics chip, leaves a dedicated card free"),
		_("Processor only"),
	]


class VisionClawPanel(gui.settingsDialogs.SettingsPanel):
	# Translators: Title of the VisionClaw settings panel.
	title = _("VisionClaw")
	# Set by the global plugin.
	plugin = None

	def makeSettings(self, settingsSizer):
		c = config.conf[CONF_SECTION]
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		def checkbox(label, key):
			box = helper.addItem(wx.CheckBox(self, label=label))
			box.SetValue(c[key])
			return box

		# Translators: Label of the choice of where the AI models run.
		self.backend = helper.addLabeledControl(_("Run the models on (&graphics):"), wx.Choice, choices=backendLabels())
		self.backend.SetSelection(backend.CHOICES.index(c["backend"]) if c["backend"] in backend.CHOICES else 0)
		if self.plugin is not None:
			# Translators: Shown in settings. {devices} lists the graphics chips that were found.
			found = _("Graphics found: {devices}").format(devices=self.plugin.devicesText())
			helper.addItem(wx.StaticText(self, label=found))
		self.sideBySide = checkbox(
			# Translators: Checkbox in settings.
			_("When both models do not fit on one graphics chip, run the &second one on another chip or the "
				"processor, instead of the two taking turns"), "sideBySide")
		self.reasoning = helper.addLabeledControl(
			# Translators: Label of the choice of how much the models think before they act.
			_("How much the models &think before acting:"), wx.Choice, choices=clawui.reasoningLabels())
		self.reasoning.SetSelection(
			policy.REASONING_CHOICES.index(c["reasoning"]) if c["reasoning"] in policy.REASONING_CHOICES else 0)
		self.oneAtATime = helper.addLabeledControl(
			# Translators: Label of the choice of whether the models are asked one small question at a time.
			_("Ask the models &one small question at a time:"), wx.Choice, choices=clawui.stepwiseLabels())
		self.oneAtATime.SetSelection(
			policy.STEPWISE_CHOICES.index(c["oneAtATime"]) if c["oneAtATime"] in policy.STEPWISE_CHOICES else 0)
		self.modelPick = helper.addLabeledControl(
			# Translators: Label of the choice of who picks the model for each job (claw/modelpick.py).
			_("Which &model does each job:"), wx.Choice, choices=[
				# Translators: A choice of who picks the model for each job: the user, in the models window.
				_("The models I chose in the models window; VisionClaw only suggests"),
				# Translators: A choice of who picks the model for each job: VisionClaw, among the downloaded models.
				_("VisionClaw picks from the models on this computer for each request, without asking"),
			])
		self.modelPick.SetSelection(modelpick.CHOICES.index(c["modelPick"]) if c["modelPick"] in modelpick.CHOICES else 0)
		self.remember = helper.addLabeledControl(
			# Translators: Label of the choice of when VisionClaw keeps something the user said, as a memory.
			_("&Remember things:"), wx.Choice, choices=[
				# Translators: Choices for when VisionClaw keeps a memory.
				_("When I ask, and when I say something lasting about myself or how I like things"),
				_("Only when I ask it to remember"),
				_("Never"),
			])
		self.remember.SetSelection(memories.WHEN.index(c["remember"]) if c["remember"] in memories.WHEN else 0)
		# Translators: Button in settings that opens the window of what VisionClaw remembers, to delete some or all.
		self.memoriesBtn = helper.addItem(wx.Button(self, label=_("What VisionClaw remem&bers, to forget some or all...")))
		self.memoriesBtn.Bind(wx.EVT_BUTTON, lambda e: self._openFolder("memories"))
		# Translators: Button in settings that says which guides and lessons VisionClaw can download when asked.
		self.downloadsBtn = helper.addItem(wx.Button(self, label=_("What VisionClaw can download for you...")))
		self.downloadsBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.showDownloads() if self.plugin else None)
		# Translators: Button in settings that opens the folder of documents VisionClaw looks things up in.
		self.libraryBtn = helper.addItem(wx.Button(self, label=_("Open your li&brary of documents...")))
		self.libraryBtn.Bind(wx.EVT_BUTTON, lambda e: self._openFolder("library"))
		# Translators: Label of the choice of search engine used when the user asks to search the web.
		self.searchEngine = helper.addLabeledControl(_("Search the &web with:"), wx.Choice, choices=SEARCH_ENGINES)
		self.searchEngine.SetSelection(
			SEARCH_IDS.index(c["searchEngine"]) if c["searchEngine"] in SEARCH_IDS else 0)
		self.controller = helper.addLabeledControl(
			# Translators: Label of the choice of what VisionClaw does with a game controller.
			_("Game controller (NVDA+Alt+&J turns controller mode on and off):"), wx.Choice, choices=[
				# Translators: Choices for what VisionClaw does with a game controller.
				_("Tell me when one is connected, and listen for its View and Menu buttons held together"),
				_("Listen for its buttons, but say nothing when one is connected"),
				_("Do not look for a game controller"),
			])
		self.controller.SetSelection(padtools.CHOICES.index(c["controller"]) if c["controller"] in padtools.CHOICES else 0)
		self.speechModel = helper.addLabeledControl(
			# Translators: Label of the choice of the speech model that listens when the user asks by voice.
			_("Speech model for asking by voice (NVDA+Alt+&V listens; it is downloaded when you first use it, after a question):"),
			wx.Choice, choices=[voiceWords.label(entry) for entry in voiceWords.MODELS])
		speechIds = [entry["id"] for entry in voiceWords.MODELS]
		self.speechModel.SetSelection(
			speechIds.index(c["speechModel"]) if c["speechModel"] in speechIds else speechIds.index(voiceWords.SUGGESTED))
		self.autoFixAddons = checkbox(
			# Translators: Checkbox in settings.
			_("When an add-on VisionClaw wrote fails, have the models debug and correct it b&y themselves"),
			"autoFixAddons")
		self.confirmChanges = checkbox(
			# Translators: Checkbox in settings.
			_("Ask me before VisionClaw &changes a setting, clicks, presses keys or types"), "confirmChanges")
		self.speakProgress = checkbox(
			# Translators: Checkbox in settings.
			_("Say each step while VisionClaw works on a re&quest"), "speakProgress")
		self.statusUpdates = helper.addLabeledControl(
			# Translators: Label of the choice of when VisionClaw says by itself how far a long request, description or
			# answer is.
			_("&Status updates while VisionClaw takes long, as with a large model or high thinking (NVDA+Alt+P says one "
				"at any time):"), wx.Choice, choices=clawui.statusLabels())
		self.statusUpdates.SetSelection(
			busy.CHOICES.index(c["statusUpdates"]) if c["statusUpdates"] in busy.CHOICES else busy.CHOICES.index(busy.SUGGESTED))
		self.ownVoice = checkbox(
			# Translators: Checkbox in settings.
			_("Speak with VisionClaw's o&wn voice, once you have set one. To set it, close this window and ask "
				"VisionClaw: customise your voice"), "ownVoice")
		if self.plugin is not None:
			# Translators: Label of the box in settings that lists the models on this computer.
			self.modelsText = helper.addLabeledControl(
				_("&Models on this computer:"), wx.TextCtrl, value=self.plugin.modelsSummary(),
				size=(480, 90), style=wx.TE_MULTILINE | wx.TE_READONLY)
		self.updateCheck = helper.addLabeledControl(
			# Translators: Label of the choice of when VisionClaw looks for a newer version of itself.
			_("Look for a newer version of VisionClaw (&update):"), wx.Choice, choices=[
				# Translators: Choices for when VisionClaw looks for a newer version of itself.
				_("Only when I ask, with NVDA+Alt+U or the button below"),
				_("When NVDA starts, at most once a day, and tell me"),
			])
		self.updateCheck.SetSelection(updates.MODES.index(c["updateCheck"]) if c["updateCheck"] in updates.MODES else 0)
		# Translators: Button in settings that looks for a newer version of VisionClaw now.
		self.updateBtn = helper.addItem(wx.Button(self, label=_("Look for a newer version no&w...")))
		self.updateBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.updater.check() if self.plugin else None)
		self.debugLog = helper.addLabeledControl(
			# Translators: Label of the choice of how much VisionClaw writes into its own log.
			_("VisionClaw's own log, for finding out why something went wrong (debu&g log):"), wx.Choice, choices=[
				# Translators: Choices for how much VisionClaw writes into its own log.
				_("Detailed: every request, step, question to a model, answer and error"),
				_("Brief: requests, steps, results and errors"),
				_("Off"),
			])
		self.debugLog.SetSelection(debuglog.LEVELS.index(c["debugLog"]) if c["debugLog"] in debuglog.LEVELS else 0)
		# Translators: Button in settings that opens VisionClaw's own log.
		self.logBtn = helper.addItem(wx.Button(self, label=_("Open VisionClaw's lo&g...")))
		self.logBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.openLog() if self.plugin else None)
		# Translators: Button in settings that opens the window of VisionClaw's skills.
		self.skillsBtn = helper.addItem(wx.Button(self, label=_("Skills: read, make, change, turn off or delete th&em...")))
		self.skillsBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.showSkills(self) if self.plugin else None)
		# Translators: Button in settings that opens the folder where the user's own skills are kept.
		self.skillsFolderBtn = helper.addItem(wx.Button(self, label=_("Open the skills &folder")))
		self.skillsFolderBtn.Bind(wx.EVT_BUTTON, lambda e: self._openSkillsFolder())
		# Translators: Button in settings that opens the window where the user reads and changes how VisionClaw
		# answers, and writes instructions of their own.
		self.answersBtn = helper.addItem(wx.Button(self, label=_("&How VisionClaw answers, and your own instructions...")))
		self.answersBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.showAnswers(self) if self.plugin else None)
		# Translators: Button in settings that opens the window for seeing, removing and swapping models.
		self.manageBtn = helper.addItem(wx.Button(self, label=_("See, remove or swa&p models...")))
		self.manageBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.showManageModels() if self.plugin else None)
		# Translators: Button in settings that opens the window for choosing and downloading models.
		self.modelsBtn = helper.addItem(wx.Button(self, label=_("Choose or &download models...")))
		self.modelsBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.showDataDialog() if self.plugin else None)
		# Translators: Button in settings that makes a portable copy of VisionClaw with all its models and data.
		self.portableBtn = helper.addItem(wx.Button(self, label=_(
			"Make a portable copy of VisionClaw with everything in it, for a flash drive or another computer (e&xport)...")))
		self.portableBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.showPortable(self) if self.plugin else None)
		self.autoDescribe = checkbox(
			# Translators: Checkbox in settings.
			_("&Automatically describe images without a label, photos in chats and photos in image viewers (NVDA+Alt+G)"), "autoDescribe")
		self.readAhead = checkbox(
			# Translators: Checkbox in settings.
			_("Describe images further down the page in the bac&kground, so they are ready sooner"), "readAhead")
		self.iconLabeler = checkbox(
			# Translators: Checkbox in settings.
			_("Name buttons that have no &name, from their icon (NVDA+Alt+B)"), "iconLabeler")
		self.useOcr = checkbox(
			# Translators: Checkbox in settings.
			_("Use Windows &OCR to read screen text exactly"), "useOcr")
		self.overlayLive = checkbox(
			# Translators: Checkbox in settings.
			_("Keep the o&verlay up to date as the window changes"), "overlayLive")
		self.preload = checkbox(
			# Translators: Checkbox in settings.
			_("Get &ready when NVDA starts (fastest first description, uses memory)"), "preload")
		# Translators: Checkbox in settings.
		self.answerInNvdaLanguage = checkbox(_("Answer in NVDA's &language"), "answerInNvdaLanguage")
		# Translators: Checkbox in settings.
		self.progressBeeps = checkbox(_("Play a soft t&ick while waiting for a description"), "progressBeeps")

	def _openSkillsFolder(self):
		"""Opens the folder of the user's own skills in File Explorer. Each skill is a folder with SKILL.md in it."""
		if self.plugin is None:
			return
		folder = self.plugin.skills.folder
		try:
			self.plugin.skills.prepare()
			os.startfile(folder)
		except OSError as e:
			debuglog.error("settings", "The skills folder could not be opened", e)

	def _openFolder(self, which):
		"""Opens the folder of memories or the library in File Explorer."""
		if self.plugin is None:
			return
		try:
			if which == "library":
				self.plugin.library.prepare()
				os.startfile(self.plugin.library.folder)
			else:
				from . import memoriesui
				memoriesui.show(self.plugin)
		except OSError as e:
			debuglog.error("settings", f"The folder {which} could not be opened", e)

	def onSave(self):
		c = config.conf[CONF_SECTION]
		if self.plugin is not None:
			self.plugin.setAutoDescribe(self.autoDescribe.GetValue())
		else:
			c["autoDescribe"] = self.autoDescribe.GetValue()
		c["backend"] = backend.CHOICES[max(0, self.backend.GetSelection())]
		c["reasoning"] = policy.REASONING_CHOICES[max(0, self.reasoning.GetSelection())]
		c["oneAtATime"] = policy.STEPWISE_CHOICES[max(0, self.oneAtATime.GetSelection())]
		c["modelPick"] = modelpick.CHOICES[max(0, self.modelPick.GetSelection())]
		c["updateCheck"] = updates.MODES[max(0, self.updateCheck.GetSelection())]
		c["debugLog"] = debuglog.LEVELS[max(0, self.debugLog.GetSelection())]
		c["remember"] = memories.WHEN[max(0, self.remember.GetSelection())]
		c["controller"] = padtools.CHOICES[max(0, self.controller.GetSelection())]
		c["speechModel"] = voiceWords.MODELS[max(0, self.speechModel.GetSelection())]["id"]
		c["sideBySide"] = self.sideBySide.GetValue()
		c["autoFixAddons"] = self.autoFixAddons.GetValue()
		c["searchEngine"] = SEARCH_IDS[max(0, self.searchEngine.GetSelection())]
		c["confirmChanges"] = self.confirmChanges.GetValue()
		c["speakProgress"] = self.speakProgress.GetValue()
		c["statusUpdates"] = busy.CHOICES[max(0, self.statusUpdates.GetSelection())]
		c["ownVoice"] = self.ownVoice.GetValue()
		c["readAhead"] = self.readAhead.GetValue()
		c["iconLabeler"] = self.iconLabeler.GetValue()
		c["useOcr"] = self.useOcr.GetValue()
		c["overlayLive"] = self.overlayLive.GetValue()
		c["preload"] = self.preload.GetValue()
		c["answerInNvdaLanguage"] = self.answerInNvdaLanguage.GetValue()
		c["progressBeeps"] = self.progressBeeps.GetValue()
		if self.plugin is not None:
			self.plugin.onSettingsSaved()
