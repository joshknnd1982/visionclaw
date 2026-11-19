# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the models window (welcome, choosing and downloading models) and the description window.

import re
import threading

import addonHandler
import api
import gui
import ui
import wx
from .vclog import log

from . import checklist, net, sounds
from .claw import advice, catalog, hardcase

addonHandler.initTranslation()

# Translators: Usage guide shown after the vision data is installed.
USAGE = _(
	"How to use VisionClaw:\n"
	"NVDA+Alt+A: describe the current element.\n"
	"NVDA+Alt+W: describe the current window.\n"
	"NVDA+Alt+F: describe the whole screen.\n"
	"NVDA+Alt+D: describe the image or image file on the clipboard.\n"
	"Press a command once to hear a quick description. "
	"Press it twice quickly to get a detailed description in a window you can read, copy and close, "
	"and where you can ask questions about the image.\n"
	"NVDA+Alt+O: open the overlay, which makes a window NVDA cannot read into a list of its texts and icons. "
	"Press Enter on an item to click it, and Escape to close.\n"
	"NVDA+Alt+G: turn automatic descriptions on or off. When on, images that have no label "
	"are described as you read web pages and documents.\n"
	"NVDA+Alt+B: turn button names on or off. When on, buttons that have no name are named from their icon.\n"
	"NVDA+Alt+N: give your own name to the current button, or to the current item in the overlay.\n"
	"Press Control to stop speaking.\n"
	"NVDA+Alt+C: ask VisionClaw to do something, in plain language. For example: make NVDA speak faster, "
	"what is on my screen, how do I read the window title, press the Play button in this window, "
	"or write an add-on that beeps when a link gets the focus. "
	"Your request is planned in small steps and carried out one at a time. With two different models, the two "
	"must agree on the steps first; with one model for both jobs, that model chooses and checks its own work.\n"
	"NVDA+Alt+P: hear how far the task is. NVDA+Alt+X: stop the task.\n"
	"NVDA+Alt+K: pointer mode, to work a control NVDA cannot reach: the arrow keys move the mouse pointer, "
	"Enter clicks, A right-clicks, G holds and lets go for dragging, H says all its keys, Escape leaves. "
	"Every key of pointer mode is one that every keyboard has.\n"
	"In the overlay, G on an item picks it up and G on another item drops it there.\n"
	"NVDA+Alt+M: choose or download models.\n"
	"VisionClaw uses AI, and AI can make mistakes, so please double-check anything important.\n"
	"Everything runs on your computer. Images are never sent to the internet."
)


def _mb(n):
	return round(n / 1048576)


def quantWords(quant):
	"""What a quant means for the user, in a few plain words, or "" for one VisionClaw has no words for."""
	return {
		# Translators: Said of the Q4_K_M quant of a model in the models window.
		catalog.Q4: _("smaller and faster"),
		# Translators: Said of the Q6_K quant of a model in the models window.
		catalog.Q6: _("larger and more exact, best for writing add-ons"),
	}.get(quant, "")


def modelLabel(models, entry, suggestedId):
	"""One model in the list of models, in words: its name, each of its quants on this computer or with what is
	left to download, whether it is suggested, and whether it is one of the very smallest.
	models: the catalog. entry: any entry of the model, or None for no coder model."""
	if entry is None:
		# Translators: A choice in the list of coder models.
		return _("No coder model now: image descriptions and the overlay only")
	kinds = catalog.variants(models.entries(entry["role"]), entry)
	name = catalog.modelName(entry)
	if len(kinds) == 1 and not catalog.quantOf(entry):
		if models.isInstalled(entry):
			# Translators: A model in the list that needs no download. {name} is the model.
			label = _("{name}, on this computer").format(name=name)
		else:
			# Translators: A model in the list. {name} is the model, {size} its download size in megabytes.
			label = _("{name}, {size} MB to download").format(name=name, size=_mb(models.missingBytes(entry)))
	else:
		parts = []
		for kind in kinds:
			if models.isInstalled(kind):
				# Translators: Part of a model in the list. {quant} is a quant such as Q4_K_M.
				parts.append(_("{quant} on this computer").format(quant=catalog.quantOf(kind)))
			else:
				# Translators: Part of a model in the list. {quant} is a quant such as Q6_K, {size} megabytes.
				parts.append(_("{quant} {size} MB to download").format(
					quant=catalog.quantOf(kind), size=_mb(models.missingBytes(kind))))
		label = ", ".join([name] + parts)
	if any(kind["id"] == suggestedId for kind in kinds):
		# Translators: Added to the model that is suggested for this computer.
		label += _(", suggested")
	if entry.get("suggest") is False:
		# Translators: Added to the very smallest models in the list, which are offered but never suggested.
		label += _(", very small: fast, less accurate")
	if catalog.isEdge(entry):
		# Translators: Added to the larger model in the list that VisionClaw keeps for hard cases.
		label += _(", for hard cases: larger and slower")
	return label


def hardLabel(models, entry):
	"""One choice of the list Model for hard cases: none, or one quant of the model for hard cases with its size."""
	if entry is None:
		# Translators: The first choice of the list of models for hard cases.
		return _("None: never use a larger model for hard cases")
	if models.isInstalled(entry):
		# Translators: A model for hard cases that is on this computer. {name} is like "Qwen3 14B Q4_K_M".
		label = _("{name}, on this computer").format(name=catalog.displayName(entry))
	else:
		# Translators: A model for hard cases that is not downloaded yet. {name} is like "Qwen3 14B Q4_K_M", {size} megabytes.
		label = _("{name}, {size} MB to download").format(name=catalog.displayName(entry), size=_mb(models.missingBytes(entry)))
	if catalog.quantOf(entry) == catalog.suggestedQuant(entry):
		# Translators: Added to the quant of the model for hard cases that is suggested. The owner, 2026-11-19: Q4_K_M
		# "should be plenty good".
		label += _(", suggested")
	return label


def quantLabel(models, entry, suggestedQuant):
	"""One quant of the chosen model in the list of quants: what it means, how large its model file is, whether
	it is on this computer or what is left to download, and whether it is the suggested one."""
	if entry is None:
		# Translators: The only item of the quant list when no coder model is chosen.
		return _("No coder model, so there is no quant to choose")
	quant = catalog.quantOf(entry)
	if not quant:
		# Translators: The only item of the quant list for a model that is offered in one file only.
		return _("This model is offered in one file only")
	size = _mb(next((f["size"] for f in entry["files"] if f["kind"] == "model"), 0))
	words = quantWords(quant)
	named = f"{quant}, {words}" if words else quant
	if models.isInstalled(entry):
		# Translators: A quant in the list. {quant} is like "Q6_K, larger and more exact", {size} the file in megabytes.
		label = _("{quant}, {size} MB, on this computer").format(quant=named, size=size)
	else:
		# Translators: A quant in the list. {quant} is like "Q6_K, larger and more exact", {size} the file in
		# megabytes, {missing} what is left to download in megabytes.
		label = _("{quant}, {size} MB, {missing} MB to download").format(
			quant=named, size=size, missing=_mb(models.missingBytes(entry)))
	if quant == suggestedQuant:
		# Translators: Added to the quant that is suggested for the chosen model.
		label += _(", suggested")
	return label


def lookResult(found):
	"""What looking for newer models found, in sentences. found is what catalog.Catalog.look returns."""
	lines = []
	if found["new"]:
		# Translators: Shown after looking for newer models. {count} is how many, {names} their names.
		lines.append(_("{count} models were added to the lists: {names}.").format(
			count=len(found["new"]), names=", ".join(found["new"])))
	else:
		# Translators: Shown after looking for newer models when there are none.
		lines.append(_("There are no newer models. The lists here already offer every model on VisionClaw's list."))
	if found.get("updated"):
		# Translators: Says how old the list of models is. {date} is a date like 2026-11-17.
		lines.append(_("The list was last brought up to date on {date}.").format(date=found["updated"]))
	if found.get("tooNew"):
		# Translators: Shown when some newer models cannot be used by this version of the add-on.
		lines.append(_(
			"{count} newer models need a newer version of VisionClaw and are not offered here."
		).format(count=found["tooNew"]))
	if found.get("refused"):
		# Translators: Shown when entries of the list were not accepted.
		lines.append(_(
			"{count} entries of the list were left out, because they did not pass VisionClaw's checks."
		).format(count=found["refused"]))
	return " ".join(lines)


class ModelsDialog(wx.Dialog):
	"""Lets the user choose a vision model and a coder model, and downloads what is missing.
	Enter starts, Space reads the progress while working. Every model is always offered: the computer only
	decides which one is suggested."""

	def __init__(self, parent, models, conf, suggested, onInstalled, notes=(), onChosen=None, machine=None):
		"""models: the catalog. conf: the add-on's settings. suggested: {role: model id}.
		notes: sentences about this computer, shown under the welcome text.
		onChosen(keys) is called with the stored models the new choice uses, once they are ready.
		machine() gives (dedicated graphics memory in MB, memory in GB), for the suggestion by what the user wants to
		do; without it that button is not shown."""
		self._suggested = suggested
		self._machine = machine
		self._looking = False
		# Translators: Title of the window for choosing and downloading the models.
		super().__init__(parent, title=_("VisionClaw models"))
		self._models = models
		self._conf = conf
		self._onInstalled = onInstalled
		self._onChosen = onChosen
		self._cancel = threading.Event()
		self._working = False
		self._progress = ""
		self._entries = {}
		self._shown = {}
		self._kinds = {}
		self._lastQuant = {}
		# Translators: Welcome text of the models window.
		intro = _(
			"VisionClaw works with two AI models that run on your own computer: a vision model that looks at the "
			"screen, and a coder model that checks plans and writes add-ons. Together they carry out what you ask "
			"in plain language. Nothing you do is sent to the internet.\n\n"
			"Choose the models below. Larger models are more accurate and slower, and need more memory. "
			"All of them are offered whatever your computer is; the suggested ones are the safe choice. "
			"Every model comes in two quants, chosen in the list under it: Q4_K_M is smaller and faster, Q6_K is "
			"larger, slower and more exact, which helps most when add-ons are written for you. The choice is yours. "
			"The very small ones are for a computer that can run nothing larger: they make more mistakes, so "
			"VisionClaw asks them one small question at a time. "
			"A model is downloaded only once, and you can change your choice here at any time.\n\n"
			"The model for hard cases, under the two lists, is larger and slower. It is never used every day: only "
			"when the chosen models could not write or correct an add-on, or could not tell how a stubborn control is "
			"worked, and only after you say yes, unless you uncheck the box under it. It reads and writes text only, "
			"and may share the work between the graphics card and the processor."
		)
		if notes:
			intro += "\n\n" + "\n".join(notes)
		main = wx.BoxSizer(wx.VERTICAL)
		self.text = wx.TextCtrl(self, value=intro, size=(560, 170), style=wx.TE_MULTILINE | wx.TE_READONLY)
		main.Add(self.text, flag=wx.ALL | wx.EXPAND, border=10)
		self._choices = {}
		self._quantChoices = {}
		for role, label, quantLabelText in (
			(
				catalog.VISION,
				# Translators: Label of the list of vision models.
				_("&Vision model:"),
				# Translators: Label of the list of quants of the chosen vision model.
				_("Vision model &quant:"),
			),
			(
				catalog.CODER,
				# Translators: Label of the list of coder models.
				_("C&oder model:"),
				# Translators: Label of the list of quants of the chosen coder model.
				_("Coder model qu&ant:"),
			),
		):
			main.Add(wx.StaticText(self, label=label), flag=wx.LEFT | wx.RIGHT, border=10)
			choice = wx.Choice(self, choices=[])
			choice.Bind(wx.EVT_CHOICE, lambda e, role=role: self._modelChanged(role))
			main.Add(choice, flag=wx.ALL | wx.EXPAND, border=10)
			self._choices[role] = choice
			main.Add(wx.StaticText(self, label=quantLabelText), flag=wx.LEFT | wx.RIGHT, border=10)
			quants = wx.Choice(self, choices=[])
			quants.Bind(wx.EVT_CHOICE, lambda e: self._updateButton())
			main.Add(quants, flag=wx.ALL | wx.EXPAND, border=10)
			self._quantChoices[role] = quants
			chosen = self._conf["visionModel" if role == catalog.VISION else "coderModel"]
			self._fill(role, self._wanted(role, chosen) or self._wanted(role, suggested.get(role)))
		# Translators: Label of the list of larger models kept for hard cases.
		main.Add(wx.StaticText(self, label=_("Model for &hard cases:")), flag=wx.LEFT | wx.RIGHT, border=10)
		self._hardEntries = [None] + hardcase.candidates(self._models.entries(catalog.CODER))
		self.hardChoice = wx.Choice(self, choices=[hardLabel(self._models, e) for e in self._hardEntries])
		self.hardChoice.SetSelection(self._hardAt(self._conf.get("hardModel", "")))
		self._hardTouched = False
		self.hardChoice.Bind(wx.EVT_CHOICE, lambda e: self._hardChanged())
		main.Add(self.hardChoice, flag=wx.ALL | wx.EXPAND, border=10)
		# Translators: A check box under the list of models for hard cases.
		self.hardAsk = wx.CheckBox(self, label=_("As&k me before the model for hard cases is used"))
		self.hardAsk.SetValue(self._conf.get("hardCases", hardcase.ASK) != hardcase.ALWAYS)
		main.Add(self.hardAsk, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		self.gauge = wx.Gauge(self, range=100)
		self.gauge.Hide()
		main.Add(self.gauge, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		self.startBtn = wx.Button(self, label="")
		# Translators: Button that asks, and then looks on VisionClaw's page for models that are not offered yet.
		self.lookBtn = wx.Button(self, label=_("Look for &newer models..."))
		# Translators: Button that closes the window without downloading.
		self.closeBtn = wx.Button(self, wx.ID_CANCEL, label=_("&Later"))
		buttons.Add(self.startBtn)
		self.suggestBtn = None
		if machine is not None:
			# Translators: Button that asks what the user wants VisionClaw for, and puts the models suggested for it into
			# the lists without downloading anything.
			self.suggestBtn = wx.Button(self, label=_("&Suggest models for what I want to do..."))
			buttons.Add(self.suggestBtn, flag=wx.LEFT, border=10)
			self.suggestBtn.Bind(wx.EVT_BUTTON, lambda e: self._suggest())
		buttons.Add(self.lookBtn, flag=wx.LEFT, border=10)
		buttons.Add(self.closeBtn, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self._updateButton()
		self.SetSizerAndFit(main)
		self.CentreOnScreen()
		self.startBtn.SetDefault()
		self.startBtn.Bind(wx.EVT_BUTTON, lambda e: self._start())
		self.lookBtn.Bind(wx.EVT_BUTTON, lambda e: self._look())
		self.closeBtn.Bind(wx.EVT_BUTTON, self._onClose)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self.Bind(wx.EVT_CHAR_HOOK, self._onKey)
		self.text.SetFocus()

	def _hardAt(self, setting):
		"""Where the list of models for hard cases starts: the one chosen before, else the first on this computer when
		none was chosen yet, else None. Nothing large is chosen for download unless the user chooses it."""
		if setting == hardcase.NONE:
			return 0
		for at, entry in enumerate(self._hardEntries):
			if entry is not None and entry["id"] == setting:
				return at
		for at, entry in enumerate(self._hardEntries):
			if entry is not None and not setting and self._models.isInstalled(entry):
				return at
		return 0

	def _hardChanged(self):
		self._hardTouched = True
		self._updateButton()

	def _hardSelected(self):
		return self._hardEntries[min(max(0, self.hardChoice.GetSelection()), len(self._hardEntries) - 1)]

	def _wanted(self, role, modelId):
		"""The entry of a role's list with this id, or None. An older setting names a Q4_K_M entry by its id."""
		for entry in self._models.entries(role):
			if entry["id"] == modelId:
				return entry
		return None

	def _fill(self, role, chosen):
		"""Fill a role's two lists from the catalog, with this entry chosen (any quant of a model), or the first."""
		self._entries[role] = self._models.entries(role) + ([None] if role == catalog.CODER else [])
		self._shown[role] = catalog.models(self._entries[role])
		suggestedId = self._suggested.get(role)
		self._choices[role].Set([modelLabel(self._models, e, suggestedId) for e in self._shown[role]])
		at = 0
		for i, entry in enumerate(self._shown[role]):
			kinds = catalog.variants(self._entries[role], entry) if entry is not None else []
			if chosen is not None and any(kind["id"] == chosen["id"] for kind in kinds):
				at = i
		self._choices[role].SetSelection(at)
		self._fillQuants(role, catalog.quantOf(chosen) if chosen is not None else None)

	def _fillQuants(self, role, quant=None):
		"""Fill the list of quants for the model chosen now, with this quant chosen if the model has it, else the
		one suggested for the model."""
		model = self._shown[role][max(0, self._choices[role].GetSelection())]
		kinds = catalog.variants(self._entries[role], model) if model is not None else [None]
		self._kinds[role] = kinds
		suggestedQuant = catalog.suggestedQuant(model)
		choice = self._quantChoices[role]
		choice.Set([quantLabel(self._models, kind, suggestedQuant) for kind in kinds])
		names = [catalog.quantOf(kind) for kind in kinds]
		for wanted in (quant, suggestedQuant):
			if wanted in names:
				choice.SetSelection(names.index(wanted))
				break
		else:
			choice.SetSelection(0)
		self._updateButton()

	def _modelChanged(self, role):
		"""Another model was chosen: its quants are listed, the quant chosen before kept where the model has it."""
		before = self._kinds.get(role) or [None]
		at = max(0, self._quantChoices[role].GetSelection())
		quant = catalog.quantOf(before[min(at, len(before) - 1)])
		if quant:
			self._lastQuant[role] = quant
		# Passing over "no coder model", or a model with one file only, does not forget the quant chosen before.
		self._fillQuants(role, quant or self._lastQuant.get(role))

	def _selected(self):
		return {
			role: self._kinds[role][min(max(0, choice.GetSelection()), len(self._kinds[role]) - 1)]
			for role, choice in self._quantChoices.items()
		}

	def _toDownload(self):
		"""The chosen models that are not here yet, the model for hard cases last."""
		chosen = list(self._selected().values())
		if getattr(self, "hardChoice", None) is not None:
			chosen.append(self._hardSelected())
		found = []
		for e in chosen:
			if e is not None and not self._models.isInstalled(e) and all(e["id"] != other["id"] for other in found):
				found.append(e)
		return found

	def _missingBytes(self, entries):
		"""Bytes still to download for these models, counting a file two of them share only once."""
		seen, size = set(), 0
		for entry in entries:
			for f in entry["files"]:
				key = (entry["dir"], f["name"])
				if key not in seen:
					seen.add(key)
					only = dict(entry, files=[f])
					size += self._models.missingBytes(only)
		return size

	def _updateButton(self):
		if getattr(self, "startBtn", None) is None:
			return  # the lists are filled before the buttons are made; __init__ calls this again after them
		size =self._missingBytes(self._toDownload())
		if size:
			# Translators: Button that starts the download. {size} is in megabytes.
			self.startBtn.SetLabel(_("&Download ({size} MB)").format(size=_mb(size)))
		else:
			# Translators: Button that saves the choice of models when nothing needs downloading.
			self.startBtn.SetLabel(_("&Use these models"))

	def _after(self, fn, *args):
		# The window may be closed while the worker thread is still reporting progress.
		wx.CallAfter(lambda: fn(*args) if self else None)

	def _onKey(self, evt):
		key = evt.GetKeyCode()
		if self._working and key == wx.WXK_SPACE:
			ui.message(self._progress)
			return
		if not self._working and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and self.startBtn.IsShown() \
				and self.FindFocus() not in (self.closeBtn, self.lookBtn) and not isinstance(self.FindFocus(), wx.Choice):
			self._start()
			return
		evt.Skip()

	def _purposeLabels(self):
		return {
			# Translators: A choice of what the user wants VisionClaw for, when models are suggested.
			advice.PLAN: _("Planning and carrying out what I ask"),
			# Translators: A choice of what the user wants VisionClaw for, when models are suggested.
			advice.SEE: _("Describing pictures and the screen"),
			# Translators: A choice of what the user wants VisionClaw for, when models are suggested.
			advice.CODE: _("Writing and fixing add-ons"),
			# Translators: A choice of what the user wants VisionClaw for, when models are suggested.
			advice.FAST: _("Quick answers more than exact ones"),
			# Translators: A choice of what the user wants VisionClaw for, when models are suggested.
			advice.ACCESS: _("Making stubborn programs, controls and web pages usable"),
			# Translators: A choice of what the user wants VisionClaw for, when models are suggested.
			advice.HARD: _("A larger model for hard cases"),
			# Translators: A choice of what the user wants VisionClaw for, when models are suggested.
			advice.VOICE: _("Asking by voice"),
		}

	def _suggest(self, picked=None):
		"""Ask what the user wants VisionClaw for, say what fits this computer and why in the box at the top, and choose
		the suggested models in the lists. Nothing is downloaded or kept until the user presses the first button.
		picked: the purposes, without asking (for tests)."""
		if self._working or self._machine is None:
			return
		labels = self._purposeLabels()
		order = [ident for ident, _words, _role, _pattern in advice.PURPOSES]
		if picked is None:
			# A list of check boxes NVDA reads (checklist.py); wxPython's own question of this kind tells NVDA nothing of
			# its check boxes, so Space seemed to do nothing.
			dialog = checklist.ChecksDialog(
				self,
				# Translators: Asked before models are suggested. The user checks one or more choices.
				_("What do you want VisionClaw for most? Check one or more with Space, then press Enter."),
				# Translators: Title of the question asked before models are suggested.
				_("Suggest models"), [labels[ident] for ident in order])
			try:
				if dialog.ShowModal() != wx.ID_OK:
					return
				picked = [order[at] for at in dialog.checked()]
			finally:
				dialog.Destroy()
		dedicated, ram = self._machine()
		selected = self._selected()
		chosen = {role: entry["id"] for role, entry in selected.items() if entry is not None}
		stored = {ident for model in self._models.stored() if not model["partial"] for ident in model["ids"]}
		one = bool(selected.get(catalog.VISION) and selected.get(catalog.CODER)
			and selected[catalog.VISION].get("dir") == selected[catalog.CODER].get("dir"))
		entries = self._models.entries()
		text = advice.advise(picked or [], entries, chosen, stored, dedicated, ram, oneModel=one)
		found = advice.choices(picked or [], entries, dedicated, ram, chosen, one)
		for role in (catalog.VISION, catalog.CODER):
			if found[role] is not None:
				self._fill(role, found[role])
		if found[advice.HARD] is not None:
			self.hardChoice.SetSelection(self._hardEntries.index(found[advice.HARD]))
			self._hardTouched = True
		self._updateButton()
		self._setText(text + "\n\n" + _(
			# Translators: Said after models were suggested in the models window.
			"The lists below now show the suggested models. Nothing is downloaded or changed until you press the first "
			"button; you can still choose others."))

	def _look(self):
		"""Look for newer models, but only after the user has said yes: this is the one time VisionClaw goes
		online other than to download a model."""
		if self._working or self._looking:
			return
		# Translators: Asked before VisionClaw goes online to read the list of models.
		question = _(
			"VisionClaw will go online once, to its own page on GitHub, and read the list of Qwen models it can "
			"offer. Nothing about you, your computer or what you do is sent; GitHub sees your internet address, as "
			"any website does. Nothing is downloaded or changed except the lists in this window.\n\nLook now?"
		)
		# Translators: Title of the question asked before VisionClaw goes online to read the list of models.
		if gui.messageBox(question, _("Look for newer models"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
			return
		self._looking = True
		self.lookBtn.Disable()
		# Translators: Shown while the list of models is being read from the internet.
		self._setText(_("Looking for newer models."))
		version = ""
		try:
			version = str(addonHandler.getCodeAddon().manifest["version"])
		except Exception:
			log.debugWarning("VisionClaw: the add-on's own version could not be read", exc_info=True)
		threading.Thread(target=self._lookWork, args=(version,), name="visionClaw-look", daemon=True).start()

	def _lookWork(self, version):
		try:
			found = self._models.look(version)
		except Exception as e:
			log.warning("VisionClaw: the list of models could not be read", exc_info=True)
			self._after(self._looked, None, str(e))
			return
		self._after(self._looked, found, "")

	def _looked(self, found, error):
		self._looking = False
		self.lookBtn.Enable()
		if found is None:
			# Translators: Shown when the list of models could not be read. {error} is the reason.
			self._setText(_(
				"The list of models could not be read: {error}\n\nNothing was changed. Check your internet "
				"connection and try again later."
			).format(error=error))
			return
		if found["new"]:
			# The new models join the lists; what was selected stays selected.
			chosen = self._selected()
			for role in self._choices:
				self._fill(role, chosen[role])
			self._updateButton()
		self._setText(lookResult(found))

	def _setText(self, text, focus=True):
		self.text.SetValue(text)
		if focus:
			self.text.SetFocus()
			self.text.SetInsertionPoint(0)

	def _start(self):
		if self._working:
			return
		wanted = self._toDownload()
		if not wanted:
			self._finished()
			return
		self._working = True
		self._cancel.clear()
		self.startBtn.Hide()
		self.lookBtn.Hide()
		if self.suggestBtn is not None:
			self.suggestBtn.Hide()
		for choice in list(self._choices.values()) + list(self._quantChoices.values()) + [self.hardChoice, self.hardAsk]:
			choice.Disable()
		# Translators: Button that cancels the download.
		self.closeBtn.SetLabel(_("&Cancel"))
		self.gauge.SetValue(0)
		self.gauge.Show()
		# Translators: Reported when the download begins.
		self._progress = _("Starting download.")
		# Translators: Shown while downloading.
		self._setText(_("Downloading the models. Press Space to hear the progress."))
		self.Layout()
		self.Fit()
		threading.Thread(target=self._work, args=(wanted,), name="visionClaw-models", daemon=True).start()

	def _work(self, wanted):
		total = self._missingBytes(wanted) or 1
		state = {"before": 0}
		try:
			for entry in wanted:
				start = self._models.missingBytes(entry)
				offset = catalog.entrySize(entry) - start

				def downloaded(done, _total, entry=entry, offset=offset):
					got = state["before"] + max(0, done - offset)
					pct = min(100, got * 100 // total)
					# Translators: Download progress. {name} is the model, {pct} percent, {done} of {total} megabytes.
					self._progress = _("Downloading {name}, {pct} percent, {done} of {total} MB.").format(
						name=catalog.displayName(entry), pct=pct, done=_mb(got), total=_mb(total))
					self._after(lambda v: self.gauge.SetValue(v), pct)

				self._models.download(entry, downloaded, self._cancel)
				state["before"] += start
		except net.Cancelled:
			return
		except (OSError, ValueError) as e:
			log.error("VisionClaw: model download failed", exc_info=True)
			self._after(self._failed, str(e))
			return
		self._after(self._finished)

	def _finished(self):
		self._working = False
		chosen = self._selected()
		self._conf["visionModel"] = chosen[catalog.VISION]["id"] if chosen[catalog.VISION] else ""
		self._conf["coderModel"] = chosen[catalog.CODER]["id"] if chosen[catalog.CODER] else "none"
		hard = self._hardSelected()
		if hard is not None:
			self._conf["hardModel"] = hard["id"]
		elif self._hardTouched or self._conf.get("hardModel"):
			# Only a choice the user made says never; untouched, any model for hard cases put on the disk is used.
			self._conf["hardModel"] = hardcase.NONE
		self._conf["hardCases"] = hardcase.ASK if self.hardAsk.GetValue() else hardcase.ALWAYS
		self.gauge.Hide()
		self.startBtn.Hide()
		self.lookBtn.Hide()
		if self.suggestBtn is not None:
			self.suggestBtn.Hide()
		for choice in list(self._choices.values()) + list(self._quantChoices.values()) + [self.hardChoice, self.hardAsk]:
			choice.Disable()
		self.closeBtn.SetLabel(_("&Close"))
		# Translators: Shown when the models are ready, followed by the usage guide.
		self._setText(_("VisionClaw is ready to use.") + "\n\n" + USAGE)
		self.Layout()
		self._onInstalled()
		if self._onChosen is not None:
			keep = [catalog.storeKey(entry) for entry in list(chosen.values()) + [hard] if entry is not None]
			wx.CallAfter(self._onChosen, keep)

	def _failed(self, error):
		self._working = False
		self.gauge.Hide()
		for choice in list(self._choices.values()) + list(self._quantChoices.values()) + [self.hardChoice, self.hardAsk]:
			choice.Enable()
		# Translators: Button to retry a failed download.
		self.startBtn.SetLabel(_("&Try again"))
		self.startBtn.Show()
		self.lookBtn.Show()
		if self.suggestBtn is not None:
			self.suggestBtn.Show()
		self.closeBtn.SetLabel(_("&Close"))
		if "CERTIFICATE_VERIFY_FAILED" in error:
			# Translators: Shown when the download fails because the secure connection can't be checked.
			self._setText(_(
				"The download did not finish because Windows could not confirm the secure connection "
				"to the download server.\n\n"
				"This usually happens when the PC's date and time are wrong, when Windows Update hasn't run "
				"for a while, or when antivirus or a company network checks secure connections. "
				"Fix the date and time or run Windows Update, then press Enter to try again. "
				"The download continues from where it stopped."
			))
		else:
			# Translators: Shown when the download fails. {error} is the reason.
			self._setText(_(
				"The download did not finish: {error}\n\n"
				"Check your internet connection and press Enter to try again. "
				"The download continues from where it stopped."
			).format(error=error))
		self.Layout()

	def _onClose(self, evt):
		if self._working:
			# Keep the partial download so the next attempt resumes.
			self._cancel.set()
			# Translators: Reported when the download is cancelled.
			ui.message(_("Download cancelled."))
		self.Destroy()


def _gb(n):
	return f"{n / 1073741824:.1f}"


def modelLine(model, inUse):
	"""One stored model in words: its name, its size, and what it is used for."""
	uses = []
	if model["partial"] and not model["roles"]:
		# Translators: Said of a model whose download was not finished.
		uses.append(_("unfinished download"))
	for role, text in (
		# Translators: Said of a stored model that is the one in use for looking at the screen.
		(catalog.VISION, _("in use for vision")),
		# Translators: Said of a stored model that is the one in use for coding.
		(catalog.CODER, _("in use for coding")),
	):
		if inUse.get(role) == model["key"]:
			uses.append(text)
	if not uses:
		# Translators: Said of a stored model that VisionClaw is not using at the moment.
		uses.append(_("not in use"))
	# Translators: A model on this computer. {name} is the model, {size} its size in gigabytes, {uses} what it is used for.
	return _("{name}, {size} GB, {uses}").format(name=model["name"], size=_gb(model["bytes"]), uses=" and ".join(uses))


def modelsSummary(models, inUse):
	"""All stored models in a few lines, for the settings panel and the top of the models window."""
	if not models:
		# Translators: Shown when no model is on the computer.
		return _("No models are on this computer yet.")
	lines = [modelLine(m, inUse) for m in models]
	# Translators: The total of the models on this computer. {count} models, {size} gigabytes.
	lines.append(_("{count} models, {size} GB on disk in all.").format(
		count=len(models), size=_gb(sum(m["bytes"] for m in models))))
	return "\n".join(lines)


class ManageModelsDialog(wx.Dialog):
	"""Shows the models on this computer, and lets the user remove some or all of them and choose others."""

	def __init__(self, parent, plugin):
		# Translators: Title of the window that shows the models on this computer.
		super().__init__(parent, title=_("VisionClaw: models on this computer"))
		self._plugin = plugin
		self._models = []
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the list of models on this computer.
		main.Add(wx.StaticText(self, label=_("&Models on this computer. Check the ones you want to remove:")),
			flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.list = checklist.checkList(self)
		main.Add(self.list, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		self.total = wx.StaticText(self, label="")
		main.Add(self.total, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that removes the checked models from the computer.
		self.removeBtn = wx.Button(self, label=_("&Remove checked models"))
		# Translators: Button that removes every model from the computer.
		self.removeAllBtn = wx.Button(self, label=_("Remove &all models"))
		# Translators: Button that opens the window for choosing and downloading models.
		self.chooseBtn = wx.Button(self, label=_("&Choose or download other models..."))
		# Translators: Button that closes the window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("C&lose"))
		for button in (self.removeBtn, self.removeAllBtn, self.chooseBtn, closeBtn):
			buttons.Add(button, flag=wx.RIGHT, border=10)
		main.Add(buttons, flag=wx.ALL, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.CentreOnScreen()
		self.removeBtn.Bind(wx.EVT_BUTTON, lambda e: self._remove(checkedOnly=True))
		self.removeAllBtn.Bind(wx.EVT_BUTTON, lambda e: self._remove(checkedOnly=False))
		self.chooseBtn.Bind(wx.EVT_BUTTON, self._choose)
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())
		self.Bind(wx.EVT_ACTIVATE, lambda e: (self.refresh() if e.GetActive() else None, e.Skip()))
		self.refresh()
		self.list.SetFocus()

	def refresh(self):
		"""Read again what is on the disk; it changes when models are removed or downloaded."""
		self._models, inUse = self._plugin.modelsOnDisk()
		self.list.Set([modelLine(m, inUse) for m in self._models])
		if self._models:
			self.list.SetSelection(0)
			# Translators: The total of the models on this computer. {count} models, {size} gigabytes.
			self.total.SetLabel(_("{count} models, {size} GB on disk in all.").format(
				count=len(self._models), size=_gb(sum(m["bytes"] for m in self._models))))
		else:
			# Translators: Shown when no model is on the computer.
			self.total.SetLabel(_("No models are on this computer yet."))
		self.removeBtn.Enable(bool(self._models))
		self.removeAllBtn.Enable(bool(self._models))

	def _remove(self, checkedOnly):
		if checkedOnly:
			chosen = [self._models[i] for i in self.list.GetCheckedItems() if i < len(self._models)]
			if not chosen:
				# Translators: Reported when Remove is pressed and no model is checked.
				ui.message(_("No model is checked. Press Space on a model to check it."))
				return
		else:
			chosen = list(self._models)
		names = ", ".join(m["name"] for m in chosen)
		size = _gb(self._plugin.models.freedBy([m["key"] for m in chosen]))
		# Translators: Asked before models are removed from the computer.
		question = _(
			"Remove {names}? This frees {size} GB. A removed model can be downloaded again at any time."
		).format(names=names, size=size)
		left = len(self._models) - len(chosen)
		if not any(catalog.VISION in m["roles"] for m in self._models if m not in chosen):
			# Translators: Added to the question when no vision model would be left.
			question += " " + _("No vision model will be left, so VisionClaw cannot describe anything until you download one.")
		elif not left:
			question += ""
		gui.mainFrame.prePopup()
		try:
			# Translators: Title of the question asked before models are removed.
			answer = gui.messageBox(question, _("Remove models"), wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
		finally:
			gui.mainFrame.postPopup()
		if answer != wx.YES:
			return
		try:
			freed = self._plugin.removeModels([m["key"] for m in chosen])
		except (OSError, RuntimeError) as e:
			log.error("VisionClaw: could not remove models", exc_info=True)
			# Translators: Reported when models could not be removed. {error} is the reason.
			ui.message(_("The models could not be removed: {error}").format(error=e))
			self.refresh()
			return
		self.refresh()
		# Translators: Reported after models were removed. {size} is the space freed in gigabytes.
		ui.message(_("Removed. {size} GB freed.").format(size=_gb(freed)))

	def _choose(self, evt):
		self._plugin.showDataDialog()


class ResultDialog(wx.Dialog):
	"""Shows a description so it can be read line by line, copied and closed.
	With onAsk, it also has a box for questions about the image: onAsk(question, dialog)."""

	def __init__(self, parent, text, onAsk=None):
		# Translators: Title of the window showing a detailed description.
		super().__init__(parent, title=_("VisionClaw description"))
		self._text = text
		self._onAsk = onAsk
		self.asking = False
		main = wx.BoxSizer(wx.VERTICAL)
		self.textCtrl = wx.TextCtrl(self, value=text, size=(600, 320), style=wx.TE_MULTILINE | wx.TE_READONLY)
		main.Add(self.textCtrl, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		self.question = None
		if onAsk is not None:
			ask = wx.BoxSizer(wx.HORIZONTAL)
			# Translators: Label of the box for questions about the described image.
			ask.Add(wx.StaticText(self, label=_("&Question about this image:")), flag=wx.ALIGN_CENTER_VERTICAL)
			self.question = wx.TextCtrl(self, size=(380, -1), style=wx.TE_PROCESS_ENTER)
			ask.Add(self.question, proportion=1, flag=wx.LEFT, border=8)
			# Translators: Button that asks the typed question about the image.
			askBtn = wx.Button(self, label=_("As&k"))
			ask.Add(askBtn, flag=wx.LEFT, border=8)
			main.Add(ask, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)
			self.question.Bind(wx.EVT_TEXT_ENTER, lambda e: self.ask())
			askBtn.Bind(wx.EVT_BUTTON, lambda e: self.ask())
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that copies the description to the clipboard.
		copyBtn = wx.Button(self, label=_("&Copy"))
		# Translators: Button that closes the description window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("C&lose"))
		buttons.Add(copyBtn)
		buttons.Add(closeBtn, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.CentreOnScreen()
		copyBtn.Bind(wx.EVT_BUTTON, lambda e: api.copyToClip(self.textCtrl.GetValue(), notify=True))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())
		self.textCtrl.SetFocus()
		self.textCtrl.SetInsertionPoint(0)

	def ask(self):
		question = self.question.GetValue().strip() if self.question else ""
		if not question or self.asking or self._onAsk is None:
			return
		self.question.Clear()
		self.asking = True
		self._onAsk(question, self)

	def addAnswer(self, question, answer):
		"""Called on the GUI thread when an answer is complete."""
		self.asking = False
		if answer:
			# Translators: A question and its answer, added to the description window.
			self.appendText(_("\n\nQuestion: {question}\nAnswer: {answer}").format(question=question, answer=answer))

	def appendText(self, text):
		"""Add streamed text without moving the reading position."""
		pos = self.textCtrl.GetInsertionPoint()
		self.textCtrl.AppendText(text)
		self.textCtrl.SetInsertionPoint(pos)

	def setFinalText(self, text):
		pos = self.textCtrl.GetInsertionPoint()
		self.textCtrl.SetValue(text)
		self.textCtrl.SetInsertionPoint(min(pos, self.textCtrl.GetLastPosition()))


class StreamingResult:
	"""Opens a ResultDialog as soon as the first sentence arrives and keeps adding the rest.
	feed() and finish() are called from the worker thread."""

	_FIRST = re.compile(r"[.!?。！？]\s")

	def __init__(self, onOpened, onAsk=None):
		self._text = ""
		self._shown = 0
		self._requested = False
		self._dialog = None
		self._onOpened = onOpened
		self._onAsk = onAsk

	def feed(self, delta):
		self._text += delta
		if not self._requested:
			if self._FIRST.search(self._text) or len(self._text) > 160:
				self._requested = True
				wx.CallAfter(self._open)
		else:
			wx.CallAfter(self._sync)

	def finish(self, finalText):
		wx.CallAfter(self._finish, finalText)

	def _open(self):
		self._dialog = ResultDialog(gui.mainFrame, _streamClean(self._text), self._onAsk)
		self._shown = len(self._text)
		show(self._dialog)
		self._onOpened()

	def _sync(self):
		if self._dialog and self._shown < len(self._text):
			self._dialog.appendText(_streamClean(self._text[self._shown:]))
			self._shown = len(self._text)

	def _finish(self, finalText):
		if self._dialog is None:
			self._open()
		if self._dialog:
			self._dialog.setFinalText(finalText)
			sounds.play("done")


def _streamClean(text):
	return text.replace("**", "").replace("`", "").replace("##", "")


def show(dialog):
	"""Show a modeless dialog in front, the way NVDA's own windows appear."""
	gui.mainFrame.prePopup()
	dialog.Show()
	dialog.Raise()
	gui.mainFrame.postPopup()


class AnswersDialog(wx.Dialog):
	"""How VisionClaw answers: the user's own instructions and every part of claw/prompts.py the user may rewrite.
	A list of them, and one edit box with the chosen one's text, which can be read line by line and rewritten.
	Each can be put back to VisionClaw's original wording, and all of them at once; nothing is kept before OK.
	names: (key, name) in the order shown, the user's own instructions first under "own"; values maps each key
	to its text now; defaults maps each key to the original ("" for "own"); onSave(values) keeps them."""

	def __init__(self, parent, names, values, defaults, onSave):
		# Translators: Title of the window where the user reads and changes how VisionClaw answers.
		super().__init__(parent, title=_("How VisionClaw answers"))
		self._names = list(names)
		self._values = dict(values)
		self._defaults = dict(defaults)
		self._onSave = onSave
		self._shown = None
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the list of instructions VisionClaw follows, which the user can change.
		main.Add(wx.StaticText(self, label=_("&Instructions:")), flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.list = wx.ListBox(self, choices=[self._label(key) for key, _name in self._names], size=(600, 140))
		main.Add(self.list, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)
		# Translators: Label of the box with the words of the instruction chosen in the list.
		main.Add(wx.StaticText(self, label=_("&Words of this instruction (an empty box is the original):")),
			flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.text = wx.TextCtrl(self, size=(600, 150), style=wx.TE_MULTILINE)
		main.Add(self.text, flag=wx.LEFT | wx.RIGHT | wx.EXPAND, border=10)
		row = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that puts back VisionClaw's original wording of the instruction chosen in the list.
		self.restoreOneBtn = wx.Button(self, label=_("&Restore the original of this instruction"))
		# Translators: Button that puts back VisionClaw's original wording of every instruction, and empties the
		# user's own instructions.
		self.restoreAllBtn = wx.Button(self, label=_("Restore &all originals"))
		row.Add(self.restoreOneBtn)
		row.Add(self.restoreAllBtn, flag=wx.LEFT, border=10)
		main.Add(row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		okBtn = wx.Button(self, wx.ID_OK)
		cancelBtn = wx.Button(self, wx.ID_CANCEL)
		buttons.Add(okBtn)
		buttons.Add(cancelBtn, flag=wx.LEFT, border=10)
		main.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(main)
		self.CentreOnScreen()
		self.list.Bind(wx.EVT_LISTBOX, lambda e: self.show(self.list.GetSelection()))
		self.text.Bind(wx.EVT_TEXT, lambda e: self._edited())
		self.restoreOneBtn.Bind(wx.EVT_BUTTON, lambda e: self.restoreOne())
		self.restoreAllBtn.Bind(wx.EVT_BUTTON, lambda e: self.restoreAll())
		okBtn.Bind(wx.EVT_BUTTON, lambda e: self.save())
		cancelBtn.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())
		self.list.SetSelection(0)
		self.show(0)
		self.list.SetFocus()

	def _changed(self, key):
		text = " ".join(str(self._values.get(key) or "").split())
		return bool(text) and text != " ".join(self._defaults.get(key, "").split())

	def _label(self, key):
		name = dict(self._names)[key]
		if key == "own":
			# Translators: How the user's own instructions are listed when they wrote none, or wrote some.
			return name + (_(" (written by you)") if self._changed(key) else _(" (none)"))
		# Translators: Added to an instruction in the list when the user changed VisionClaw's original wording.
		return name + (_(" (changed)") if self._changed(key) else "")

	def show(self, index):
		"""Show the instruction at index in the edit box."""
		if index < 0:
			return
		self._shown = None  # the box is being filled, not edited
		key = self._names[index][0]
		self.text.SetValue(self._values.get(key) or self._defaults.get(key, ""))
		self._shown = key

	def _edited(self):
		if self._shown is None:
			return
		self._values[self._shown] = self.text.GetValue()
		index = [key for key, _name in self._names].index(self._shown)
		label = self._label(self._shown)
		if self.list.GetString(index) != label:
			self.list.SetString(index, label)

	def restoreOne(self):
		index = self.list.GetSelection()
		if index < 0:
			return
		key, name = self._names[index]
		self._values[key] = ""
		self.list.SetString(index, self._label(key))
		self.show(index)
		# Translators: Said after one instruction was put back to VisionClaw's original wording. {name} is it.
		ui.message(_("{name}: the original is back. Press OK to keep it.").format(name=name))

	def restoreAll(self):
		for index, (key, _name) in enumerate(self._names):
			self._values[key] = ""
			self.list.SetString(index, self._label(key))
		self.show(max(0, self.list.GetSelection()))
		# Translators: Said after every instruction was put back to VisionClaw's original wording.
		ui.message(_("Every instruction is back to the original, and your own instructions are empty. Press OK to keep it."))

	def save(self):
		values = dict(self._values)
		self.Destroy()
		self._onSave(values)
