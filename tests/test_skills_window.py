# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The skills window (skillsui.py) with the real wxPython and stand-ins for NVDA's gui and ui: the list shows
every skill, the chosen one is shown whole, turning off and on, making a skill with a step, changing a built-in
skill keeps the user's copy, deleting asks first and only the user's own, a skill file is shown before it is
taken in. Skipped when wxPython is not installed. Nothing is shown on the screen.

  python tests/test_skills_window.py
"""
import os
import sys
import tempfile
import types

import harness  # noqa: F401

try:
	import wx
except ImportError:
	print("wxPython is not installed; skipped.\nOK")
	sys.exit(0)

said, answers = [], []


class BoxSizerHelper:
	"""Stands in for NVDA's gui.guiHelper.BoxSizerHelper: a label, then the control, one under the other."""

	def __init__(self, parent, orientation=wx.VERTICAL):
		self.parent = parent
		self.sizer = wx.BoxSizer(orientation)

	def addLabeledControl(self, label, cls, **kwargs):
		self.sizer.Add(wx.StaticText(self.parent, label=label))
		control = cls(self.parent, **kwargs)
		self.sizer.Add(control)
		return control

	def addItem(self, item):
		self.sizer.Add(item)
		return item

	def addDialogDismissButtons(self, buttons):
		self.sizer.Add(buttons)


gui = types.ModuleType("gui")
gui.mainFrame = types.SimpleNamespace(prePopup=lambda: None, postPopup=lambda: None)
gui.messageBox = lambda question, *args, **kwargs: said.append(question) or answers.pop(0)
gui.guiHelper = types.SimpleNamespace(BoxSizerHelper=BoxSizerHelper)
sys.modules["gui"] = gui
sys.modules["ui"] = types.SimpleNamespace(message=lambda text: said.append(text))
import builtins  # noqa: E402
builtins._ = getattr(builtins, "_", None) or (lambda text: text)
sys.modules.setdefault("addonHandler", types.SimpleNamespace(initTranslation=lambda: None))

from visionClaw import skillsui  # noqa: E402
from visionClaw.claw import planner, skills  # noqa: E402

app = wx.App(False)
folder = os.path.join(tempfile.mkdtemp(), "skills")
lib = skills.Skills(folder, recipes=set(planner.RECIPES))
dialog = skillsui.SkillsDialog(None, lib)


def choose(slug):
	dialog.list.SetSelection(next(i for i, skill in enumerate(dialog._shown) if skill.slug == slug))
	dialog._showChosen()


# Every skill is listed, in order of its name, and the chosen one is shown whole.
items = [dialog.list.GetString(at) for at in range(dialog.list.GetCount())]
assert len(items) == len(lib.all()) >= 30 and items == sorted(items, key=str.lower), items
assert dialog.total.GetLabel().startswith(f"{len(items)} skills, 0 of them yours, 0 turned off"), dialog.total.GetLabel()
choose("chart")
about = dialog.about.GetValue()
assert about.startswith("Understand a chart, graph or diagram:") and "Comes with VisionClaw. On." in about, about
assert "Used when your request says: chart;" in about and "What it tells VisionClaw:" in about
# A built-in skill cannot be deleted.
assert not dialog.deleteBtn.IsEnabled()

# Turned off, then on: the list and the button say so.
dialog._toggle()
assert said[-1] == "Understand a chart, graph or diagram is off." and not lib.get("chart").on
assert "Understand a chart, graph or diagram (off)" in dialog.list.GetString(dialog.list.GetSelection())
assert dialog.onBtn.GetLabel() == "&Turn on"
dialog._toggle()
assert lib.get("chart").on and dialog.onBtn.GetLabel() == "&Turn off"

# The window that makes a skill: every part has a field; the steps come from a list of jobs.
edit = skillsui.EditSkillDialog(dialog)
edit.name.SetValue("Morning")
edit.when.SetValue("good morning")
edit.instructions.SetValue("Say each thing in a few words.")
edit._steps.append(("do_command", "what time is it"))
edit._steps.append(("where_am_i", ""))
edit._showSteps()
assert edit.stepList.GetString(0) == "1. run an NVDA command now: what time is it", edit.stepList.GetString(0)
edit.stepList.SetSelection(1)
edit._move(-1)
assert edit._steps[0] == ("where_am_i", "")
edit.uses.Check(edit._recipes.index("do_command"))
made = edit.skill()
assert made.when == ("good morning",) and made.uses == ("do_command",) and len(made.steps) == 2
assert not skills.check(made, planner.RECIPES)
# Without starting words it is not complete, and the window says why.
edit.when.SetValue("")
answers.append(wx.OK)
edit._onOk(types.SimpleNamespace(Skip=lambda: said.append("closed")))
assert said[-1] == "It has no words that start it." and "closed" not in said
edit.Destroy()
saved = lib.save(made)
dialog.refresh(select=saved.slug)
assert dialog._chosen().slug == "morning" and "Morning (yours)" in dialog.list.GetString(dialog.list.GetSelection())
assert dialog.deleteBtn.IsEnabled() and dialog.deleteBtn.GetLabel() == "&Delete"

# A built-in skill changed is kept as the user's copy; deleting the copy brings VisionClaw's own back.
copy = lib.save(skills.Skill("Understand a chart, graph or diagram", "", "chart", ("describe",), (), "Highest first."),
	replace="chart")
dialog.refresh(select="chart")
assert dialog.deleteBtn.IsEnabled() and dialog.deleteBtn.GetLabel() == "&Delete your copy"
assert "in place of VisionClaw's own" in dialog.about.GetValue()
answers.append(wx.YES)
dialog._delete()
assert said[-2].startswith("Delete your copy of Understand a chart") and "used again" in said[-1]
assert lib.get("chart").source == skills.OURS

# Deleting asks first; a no keeps the skill.
choose("morning")
answers.append(wx.NO)
dialog._delete()
assert said[-1].startswith("Delete your skill Morning?") and lib.get("morning") is not None
answers.append(wx.YES)
dialog._delete()
assert lib.get("morning") is None and said[-1] == "Your skill Morning was deleted."

# The folder the button opens is made, with a note on writing skills in it.
assert os.path.isfile(os.path.join(lib.prepare(), skills.README))
dialog.Destroy()
print("OK")
