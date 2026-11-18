# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the skills window (NVDA+Alt+I). A list of every skill, VisionClaw's own and the user's; below it a
# read-only box with everything about the chosen one, which can be read line by line; and buttons to make a new
# skill, change the chosen one, turn it off or on, delete it, take in a skill file someone shared, and open the
# folder where the user's skills are kept. A skill is text, never code, so nobody has to read code here.
# The window that makes or changes a skill has a field for each part, and the steps are chosen from a list of
# what VisionClaw can do, each with the words it is given.

import os

import addonHandler
import gui
import ui
import wx

from .claw import planner, skills as skillsModule

addonHandler.initTranslation()


def _ask(parent, question, title, style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION):
	gui.mainFrame.prePopup()
	try:
		return gui.messageBox(question, title, style, parent)
	finally:
		gui.mainFrame.postPopup()


def _tell(parent, message, title):
	_ask(parent, message, title, wx.OK | wx.ICON_INFORMATION)


class SkillsDialog(wx.Dialog):
	"""Every skill, and what can be done with the chosen one. skills: a claw.skills.Skills."""

	def __init__(self, parent, skills):
		# Translators: Title of the window that lists VisionClaw's skills.
		super().__init__(parent, title=_("VisionClaw: skills"))
		self._skills = skills
		self._shown = []
		main = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label of the list of skills.
		main.Add(wx.StaticText(self, label=_("&Skills:")), flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.list = wx.ListBox(self, size=(560, 220))
		main.Add(self.list, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		# Translators: Label of the box that shows everything about the chosen skill.
		main.Add(wx.StaticText(self, label=_("&About this skill:")), flag=wx.LEFT | wx.RIGHT, border=10)
		self.about = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(560, 200))
		main.Add(self.about, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		self.total = wx.StaticText(self, label="")
		main.Add(self.total, flag=wx.LEFT | wx.RIGHT, border=10)
		buttons = wx.GridSizer(cols=4, hgap=8, vgap=8)
		# Translators: Button that makes a new skill.
		self.newBtn = wx.Button(self, label=_("&New skill..."))
		# Translators: Button that changes the chosen skill.
		self.changeBtn = wx.Button(self, label=_("C&hange..."))
		# Translators: Button that turns the chosen skill off, or on when it is off.
		self.onBtn = wx.Button(self, label=_("&Turn off"))
		# Translators: Button that deletes the chosen skill.
		self.deleteBtn = wx.Button(self, label=_("&Delete"))
		# Translators: Button that takes in a skill file someone shared.
		self.importBtn = wx.Button(self, label=_("&Import a skill file..."))
		# Translators: Button that opens the folder where the user's skills are kept.
		self.folderBtn = wx.Button(self, label=_("Open the skills &folder"))
		# Translators: Button that reads the skills again from the disk, after files were changed by hand.
		self.reloadBtn = wx.Button(self, label=_("&Read the skills again"))
		# Translators: Button that closes the window.
		closeBtn = wx.Button(self, wx.ID_CLOSE, label=_("C&lose"))
		for button in (self.newBtn, self.changeBtn, self.onBtn, self.deleteBtn, self.importBtn, self.folderBtn,
				self.reloadBtn, closeBtn):
			buttons.Add(button, flag=wx.EXPAND)
		main.Add(buttons, flag=wx.ALL | wx.EXPAND, border=10)
		self.SetSizerAndFit(main)
		self.SetEscapeId(wx.ID_CLOSE)
		self.CentreOnScreen()
		self.list.Bind(wx.EVT_LISTBOX, lambda e: self._showChosen())
		self.list.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self._change())
		self.newBtn.Bind(wx.EVT_BUTTON, lambda e: self._new())
		self.changeBtn.Bind(wx.EVT_BUTTON, lambda e: self._change())
		self.onBtn.Bind(wx.EVT_BUTTON, lambda e: self._toggle())
		self.deleteBtn.Bind(wx.EVT_BUTTON, lambda e: self._delete())
		self.importBtn.Bind(wx.EVT_BUTTON, lambda e: self._import())
		self.folderBtn.Bind(wx.EVT_BUTTON, lambda e: self._folder())
		self.reloadBtn.Bind(wx.EVT_BUTTON, lambda e: self.refresh(reload=True))
		closeBtn.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
		self.Bind(wx.EVT_CLOSE, lambda e: self.Destroy())
		self.refresh()
		self.list.SetFocus()

	# Showing

	@staticmethod
	def _line(skill):
		# Translators: Marks a skill of the user's own in the list of skills.
		mine = _("yours") if skill.source == skillsModule.YOURS else ""
		# Translators: Marks a skill that is turned off in the list of skills.
		off = _("off") if not skill.on else ""
		marks = ", ".join(mark for mark in (mine, off) if mark)
		return f"{skill.name} ({marks})" if marks else skill.name

	def refresh(self, reload=False, select=None):
		"""Read the skills again and show them; select: the folder name of the skill to choose."""
		chosen = select or (self._chosen().slug if self._chosen() else None)
		self._shown = self._skills.reload() if reload else self._skills.all()
		self.list.Set([self._line(skill) for skill in self._shown])
		index = next((i for i, skill in enumerate(self._shown) if skill.slug == chosen), 0)
		if self._shown:
			self.list.SetSelection(index)
		yours = sum(1 for skill in self._shown if skill.source == skillsModule.YOURS)
		off = sum(1 for skill in self._shown if not skill.on)
		# Translators: The count of skills under the list. {count} skills, {yours} of the user's, {off} turned off.
		self.total.SetLabel(_("{count} skills, {yours} of them yours, {off} turned off.").format(
			count=len(self._shown), yours=yours, off=off))
		self._showChosen()

	def _chosen(self):
		index = self.list.GetSelection() if self._shown else wx.NOT_FOUND
		return self._shown[index] if index != wx.NOT_FOUND and index < len(self._shown) else None

	def _showChosen(self):
		skill = self._chosen()
		self.about.SetValue(skillsModule.describe(skill, planner.label) if skill else "")
		self.changeBtn.Enable(skill is not None)
		self.onBtn.Enable(skill is not None)
		# Translators: Button that turns the chosen skill on, shown when it is off.
		self.onBtn.SetLabel(_("&Turn on") if skill is not None and not skill.on else _("&Turn off"))
		self.deleteBtn.Enable(skill is not None and skill.source == skillsModule.YOURS)
		if skill is not None and skill.replaces:
			# Translators: Button that deletes the user's copy of a built-in skill, so that VisionClaw's own is used.
			self.deleteBtn.SetLabel(_("&Delete your copy"))
		else:
			self.deleteBtn.SetLabel(_("&Delete"))

	# Doing

	def _new(self):
		self._edit(None)

	def _change(self):
		skill = self._chosen()
		if skill is not None:
			self._edit(skill)

	def _edit(self, skill):
		dialog = EditSkillDialog(self, skill)
		try:
			while dialog.ShowModal() == wx.ID_OK:
				made = dialog.skill()
				# A skill that comes with VisionClaw is changed by keeping the user's copy in its place.
				replace = skill.slug if skill is not None else ""
				try:
					saved = self._skills.save(made, replace=replace)
				except (skillsModule.SkillError, OSError) as e:
					# Translators: Title of the message when a skill cannot be saved.
					_tell(self, str(e), _("The skill was not saved"))
					continue
				self.refresh(select=saved.slug)
				# Translators: Reported when a skill was saved. {name} is its name.
				ui.message(_("Saved the skill {name}.").format(name=saved.name))
				break
		finally:
			dialog.Destroy()
		self.list.SetFocus()

	def _toggle(self):
		skill = self._chosen()
		if skill is None:
			return
		wasOn = skill.on
		self._skills.setOn(skill.slug, not wasOn)
		self.refresh(select=skill.slug)
		if wasOn:
			# Translators: Reported when a skill was turned off. {name} is its name.
			ui.message(_("{name} is off.").format(name=skill.name))
		else:
			# Translators: Reported when a skill was turned on. {name} is its name.
			ui.message(_("{name} is on.").format(name=skill.name))

	def _delete(self):
		skill = self._chosen()
		if skill is None or skill.source != skillsModule.YOURS:
			return
		if skill.replaces:
			# Translators: Asked before the user's copy of a built-in skill is deleted. {name} is its name.
			question = _("Delete your copy of {name}? VisionClaw's own skill of that name is used again.").format(name=skill.name)
		else:
			# Translators: Asked before one of the user's skills is deleted. {name} is its name.
			question = _("Delete your skill {name}? Its file is removed from this computer.").format(name=skill.name)
		# Translators: Title of the question asked before a skill is deleted.
		if _ask(self, question, _("Delete the skill")) != wx.YES:
			return
		try:
			said = self._skills.remove(skill.slug)
		except (skillsModule.SkillError, OSError) as e:
			# Translators: Title of the message when a skill cannot be deleted.
			_tell(self, str(e), _("The skill was not deleted"))
			return
		self.refresh(select=skill.slug)
		ui.message(said)

	def _import(self):
		# Translators: Title of the window for choosing a skill file to take in.
		with wx.FileDialog(self, _("Choose a skill file"),
				# Translators: The kinds of file shown when choosing a skill file.
				wildcard=_("Skill files (*.md)|*.md|All files (*.*)|*.*"),
				style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as chooser:
			if chooser.ShowModal() != wx.ID_OK:
				return
			path = chooser.GetPath()
		try:
			with open(path, encoding="utf-8") as f:
				text = f.read(200000)
			skill = skillsModule.parse(text)
		except (OSError, UnicodeDecodeError, skillsModule.SkillError) as e:
			# Translators: Title of the message when a skill file cannot be read.
			_tell(self, str(e), _("The skill file was not taken in"))
			return
		# What a shared file tells VisionClaw is shown before it is kept, in its own words.
		# Translators: Asked before a skill from a file is kept. {about} is everything about it.
		question = _("Take in this skill?\n\n{about}").format(about=skillsModule.describe(skill, planner.label))
		# Translators: Title of the question asked before a skill from a file is kept.
		if _ask(self, question, _("Import a skill")) != wx.YES:
			return
		try:
			saved = self._skills.save(skill)
		except (skillsModule.SkillError, OSError) as e:
			_tell(self, str(e), _("The skill file was not taken in"))
			return
		self.refresh(select=saved.slug)
		# Translators: Reported when a skill from a file was kept. {name} is its name.
		ui.message(_("Took in the skill {name}.").format(name=saved.name))

	def _folder(self):
		folder = self._skills.folder
		try:
			self._skills.prepare()
			os.startfile(folder)
		except OSError as e:
			# Translators: Title of the message when the skills folder cannot be opened.
			_tell(self, f"{e}\n{folder}", _("The folder could not be opened"))


class EditSkillDialog(wx.Dialog):
	"""Makes a new skill, or changes one. Every part has its own field; the steps are chosen from a list."""

	def __init__(self, parent, skill=None):
		if skill is None:
			# Translators: Title of the window that makes a new skill.
			title = _("New skill")
		else:
			# Translators: Title of the window that changes a skill. {name} is its name.
			title = _("Change the skill {name}").format(name=skill.name)
		super().__init__(parent, title=title)
		self._recipes = list(planner.RECIPES)
		self._steps = list(skill.steps) if skill else []
		main = wx.BoxSizer(wx.VERTICAL)
		helper = gui.guiHelper.BoxSizerHelper(self, orientation=wx.VERTICAL)
		# Translators: Label of the field for a skill's name.
		self.name = helper.addLabeledControl(_("&Name:"), wx.TextCtrl)
		# Translators: Label of the field that says in one line what a skill is for.
		self.description = helper.addLabeledControl(_("What it is &for, in one line:"), wx.TextCtrl)
		# Translators: Label of the field with the words that start a skill.
		self.when = helper.addLabeledControl(_("&Words in a request that start it, separated by commas:"), wx.TextCtrl)
		# Translators: Label of the list of the kinds of job a skill is for.
		self.uses = helper.addLabeledControl(
			_("&Jobs it is for (check none for every job):"), wx.CheckListBox,
			choices=[planner.label(name) for name in self._recipes])
		# Translators: Label of the field with what a skill tells VisionClaw.
		self.instructions = helper.addLabeledControl(
			_("What it tells &VisionClaw, in plain sentences:"), wx.TextCtrl, style=wx.TE_MULTILINE, size=(520, 140))
		# Translators: Label of the list of a skill's steps.
		self.stepList = helper.addLabeledControl(
			_("&Steps, run as they are when a request has its words exactly (may be empty):"), wx.ListBox, size=(520, 100))
		stepButtons = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Button that adds a step to a skill.
		self.addStepBtn = wx.Button(self, label=_("&Add a step..."))
		# Translators: Button that removes the chosen step of a skill.
		self.removeStepBtn = wx.Button(self, label=_("&Remove the step"))
		# Translators: Button that moves the chosen step one place earlier.
		self.upBtn = wx.Button(self, label=_("Move &up"))
		# Translators: Button that moves the chosen step one place later.
		self.downBtn = wx.Button(self, label=_("Move do&wn"))
		for button in (self.addStepBtn, self.removeStepBtn, self.upBtn, self.downBtn):
			stepButtons.Add(button, flag=wx.RIGHT, border=8)
		helper.addItem(stepButtons)
		helper.addDialogDismissButtons(self.CreateButtonSizer(wx.OK | wx.CANCEL))
		main.Add(helper.sizer, flag=wx.ALL | wx.EXPAND, border=10)
		self.SetSizerAndFit(main)
		self.CentreOnScreen()
		if skill is not None:
			self.name.SetValue(skill.name)
			self.description.SetValue(skill.description)
			self.when.SetValue(", ".join(skill.when))
			self.instructions.SetValue(skill.instructions)
			for name in skill.uses:
				if name in self._recipes:
					self.uses.Check(self._recipes.index(name))
		self._showSteps()
		self.addStepBtn.Bind(wx.EVT_BUTTON, lambda e: self._addStep())
		self.removeStepBtn.Bind(wx.EVT_BUTTON, lambda e: self._removeStep())
		self.upBtn.Bind(wx.EVT_BUTTON, lambda e: self._move(-1))
		self.downBtn.Bind(wx.EVT_BUTTON, lambda e: self._move(1))
		self.Bind(wx.EVT_BUTTON, self._onOk, id=wx.ID_OK)
		self.name.SetFocus()

	def _showSteps(self, select=None):
		self.stepList.Set([
			f"{number}. {planner.label(recipe)}" + (f": {words}" if words else "")
			for number, (recipe, words) in enumerate(self._steps, 1)])
		if self._steps:
			self.stepList.SetSelection(min(select if select is not None else 0, len(self._steps) - 1))
		for button in (self.removeStepBtn, self.upBtn, self.downBtn):
			button.Enable(bool(self._steps))
		self.addStepBtn.Enable(len(self._steps) < skillsModule.MAX_STEPS)

	def _addStep(self):
		# Translators: Asked when a step is added to a skill: what the step does.
		with wx.SingleChoiceDialog(self, _("What should this step do?"), _("Add a step"),
				[planner.label(name) for name in self._recipes]) as chooser:
			if chooser.ShowModal() != wx.ID_OK:
				return
			recipe = self._recipes[chooser.GetSelection()]
		# Translators: Asked when a step is added to a skill: the words the step is given.
		with wx.TextEntryDialog(self, _(
				"The words this step is given, as you would ask for it alone. Leave it empty to give it your "
				"whole request."), _("Add a step")) as entry:
			if entry.ShowModal() != wx.ID_OK:
				return
			words = " ".join(entry.GetValue().split())
		self._steps.append((recipe, words))
		self._showSteps(select=len(self._steps) - 1)
		self.stepList.SetFocus()

	def _removeStep(self):
		index = self.stepList.GetSelection()
		if index != wx.NOT_FOUND:
			del self._steps[index]
			self._showSteps(select=index)

	def _move(self, by):
		index = self.stepList.GetSelection()
		other = index + by
		if index == wx.NOT_FOUND or not 0 <= other < len(self._steps):
			return
		self._steps[index], self._steps[other] = self._steps[other], self._steps[index]
		self._showSteps(select=other)

	def skill(self):
		return skillsModule.Skill(
			self.name.GetValue(), self.description.GetValue(), self.when.GetValue(),
			[self._recipes[i] for i in self.uses.GetCheckedItems()], self._steps, self.instructions.GetValue())

	def _onOk(self, event):
		problems = skillsModule.check(self.skill(), planner.RECIPES)
		if problems:
			# Translators: Title of the message that says what is missing or wrong in a skill.
			_tell(self, "\n".join(problems), _("The skill is not complete"))
			return
		event.Skip()
