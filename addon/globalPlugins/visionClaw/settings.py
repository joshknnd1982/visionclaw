# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - settings panel in NVDA's Settings dialog.

import addonHandler
import config
import gui
import wx
from gui import guiHelper

from . import clawui
from .claw import backend, policy

addonHandler.initTranslation()

CONF_SECTION = "visionClaw"


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
		self.confirmChanges = checkbox(
			# Translators: Checkbox in settings.
			_("Ask me before VisionClaw &changes a setting, clicks, presses keys or types"), "confirmChanges")
		self.speakProgress = checkbox(
			# Translators: Checkbox in settings.
			_("Say each step while VisionClaw works on a re&quest"), "speakProgress")
		# Translators: Button in settings that opens the window for choosing and downloading models.
		self.modelsBtn = helper.addItem(wx.Button(self, label=_("Choose or download &models...")))
		self.modelsBtn.Bind(wx.EVT_BUTTON, lambda e: self.plugin.showDataDialog() if self.plugin else None)
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

	def onSave(self):
		c = config.conf[CONF_SECTION]
		if self.plugin is not None:
			self.plugin.setAutoDescribe(self.autoDescribe.GetValue())
		else:
			c["autoDescribe"] = self.autoDescribe.GetValue()
		c["backend"] = backend.CHOICES[max(0, self.backend.GetSelection())]
		c["reasoning"] = policy.REASONING_CHOICES[max(0, self.reasoning.GetSelection())]
		c["sideBySide"] = self.sideBySide.GetValue()
		c["confirmChanges"] = self.confirmChanges.GetValue()
		c["speakProgress"] = self.speakProgress.GetValue()
		c["readAhead"] = self.readAhead.GetValue()
		c["iconLabeler"] = self.iconLabeler.GetValue()
		c["useOcr"] = self.useOcr.GetValue()
		c["overlayLive"] = self.overlayLive.GetValue()
		c["preload"] = self.preload.GetValue()
		c["answerInNvdaLanguage"] = self.answerInNvdaLanguage.GetValue()
		c["progressBeeps"] = self.progressBeeps.GetValue()
		if self.plugin is not None:
			self.plugin.onSettingsSaved()
