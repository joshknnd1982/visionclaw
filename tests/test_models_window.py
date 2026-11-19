# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The models window (dialogs.ModelsDialog) with the real wxPython and stand-ins for NVDA: every model is offered
in Q4_K_M and Q6_K, chosen with the keyboard in two lists; the suggestion is marked, never forced; the choice is
kept in the settings; an older setting without a quant means Q4_K_M; a projector already on the disk is not
counted again. Skipped when wxPython is not installed. Nothing is shown on the screen and nothing is downloaded."""
import sys
import tempfile
import types

import harness  # noqa: F401

try:
	import wx
except ImportError:
	print("wxPython is not installed; skipped.\nOK")
	sys.exit(0)

said = []
_quiet = lambda *args, **kwargs: None  # noqa: E731
sys.modules["logHandler"] = types.SimpleNamespace(log=types.SimpleNamespace(
	debug=_quiet, debugWarning=_quiet, info=_quiet, warning=_quiet, error=_quiet, exception=_quiet))
gui = types.ModuleType("gui")
gui.mainFrame = types.SimpleNamespace(prePopup=_quiet, postPopup=_quiet)
gui.messageBox = lambda question, *args, **kwargs: said.append(question) or wx.NO
sys.modules["gui"] = gui
sys.modules["ui"] = types.SimpleNamespace(message=lambda text: said.append(text))
sys.modules.setdefault("api", types.ModuleType("api"))
import builtins  # noqa: E402
builtins._ = getattr(builtins, "_", None) or (lambda text: text)
sys.modules.setdefault("addonHandler", types.SimpleNamespace(initTranslation=_quiet))

from visionClaw import dialogs  # noqa: E402
from visionClaw.claw import catalog  # noqa: E402
from visionClaw.claw.catalog import CODER, VISION  # noqa: E402


class Shelf(catalog.Catalog):
	"""A catalog whose disk holds the files named in onDisk, as (folder, file name)."""

	def __init__(self, onDisk):
		super().__init__(tempfile.mkdtemp())
		self.onDisk = set(onDisk)

	def _has(self, entry, f):
		return (entry["dir"], f["name"]) in self.onDisk


def mb(n):
	return round(n / 1048576)


def items(choice):
	return [choice.GetString(at) for at in range(choice.GetCount())]


app = wx.App(False)
two = catalog.Catalog("nowhere").get("qwen3.5-2b")
# Qwen3.5 2B Q4_K_M with its projector is on the disk, from before there were quants.
shelf = Shelf([("qwen3.5-2b", f["name"]) for f in two["files"]])
conf = {"visionModel": "qwen3.5-2b", "coderModel": ""}
suggested = {VISION: catalog.recommend(VISION, 8, 0), CODER: catalog.recommend(CODER, 8, 0)}
assert suggested == {VISION: "qwen3.5-2b", CODER: "qwen2.5-coder-1.5b"}
chosenKeys = []
dialog = dialogs.ModelsDialog(None, shelf, conf, suggested, _quiet, (), chosenKeys.append)
models, quants = dialog._choices, dialog._quantChoices

# Every model is offered once in the list of models, the 7B and 9B included, and each says its quants.
assert items(models[VISION]) == [
	"Qwen3.5 0.8B, Q4_K_M 703 MB to download, Q6_K 805 MB to download, very small: fast, less accurate",
	"Qwen3.5 2B, Q4_K_M on this computer, Q6_K 1502 MB to download, suggested",
	"Qwen3.5 4B, Q4_K_M 3255 MB to download, Q6_K 4004 MB to download",
	"Qwen3.5 9B, Q4_K_M 6293 MB to download, Q6_K 7988 MB to download",
], items(models[VISION])
assert len(items(models[CODER])) == 7 and items(models[CODER])[-1].startswith("No coder model now")
assert items(models[CODER])[3] == "Qwen2.5 Coder 7B, Q4_K_M 4466 MB to download, Q6_K 5964 MB to download"
# The model for hard cases is offered in the coder list too, the user's choice, and says what it is.
assert items(models[CODER])[5] == (
	f"Qwen3 14B, Q4_K_M {mb(9001752960)} MB to download, Q6_K {mb(12121937248)} MB to download, for hard cases: larger "
	"and slower"), items(models[CODER])[5]
# Its own list under the coder's: none is chosen at first, so nothing of 9 GB is added to the download unasked.
hard = dialog.hardChoice
assert items(hard) == [
	"None: never use a larger model for hard cases", f"Qwen3 14B Q4_K_M, {mb(9001752960)} MB to download, suggested",
	f"Qwen3 14B Q6_K, {mb(12121937248)} MB to download"], items(hard)
assert hard.GetSelection() == 0 and dialog._hardSelected() is None and dialog.hardAsk.GetValue()
# The older setting, without a quant, is Qwen3.5 2B in Q4_K_M: what the user had goes on working unchanged.
assert models[VISION].GetSelection() == 1 and quants[VISION].GetSelection() == 0
assert dialog._selected()[VISION]["id"] == "qwen3.5-2b"
# The quants of the chosen model, in plain words with their sizes; the suggested one is marked.
assert items(quants[VISION]) == [
	"Q4_K_M, smaller and faster, 1222 MB, on this computer, suggested",
	"Q6_K, larger and more exact, best for writing add-ons, 1502 MB, 1502 MB to download",
], items(quants[VISION])
# With no coder chosen yet, the suggested coder and its suggested quant are chosen first.
assert dialog._selected()[CODER]["id"] == "qwen2.5-coder-1.5b"
assert dialog.startBtn.GetLabel() == f"&Download ({mb(1117320768)} MB)"

# The user takes Q6_K for vision: only its own file is to download, the projector is on the disk already.
quants[VISION].SetSelection(1)
dialog._updateButton()
assert dialog._selected()[VISION]["id"] == "qwen3.5-2b-q6k"
assert dialog.startBtn.GetLabel() == f"&Download ({mb(1574961408 + 1117320768)} MB)", dialog.startBtn.GetLabel()
# Another model keeps the quant the user chose; a model of a role is always offered in both quants.
models[VISION].SetSelection(3)
dialog._modelChanged(VISION)
assert dialog._selected()[VISION]["id"] == "qwen3.5-9b-q6k" and quants[VISION].GetCount() == 2
assert items(quants[VISION])[0].endswith(", suggested") and not items(quants[VISION])[1].endswith(", suggested")
for at in range(models[CODER].GetCount() - 1):
	models[CODER].SetSelection(at)
	dialog._modelChanged(CODER)
	assert [catalog.quantOf(e) for e in dialog._kinds[CODER]] == ["Q4_K_M", "Q6_K"], at
models[CODER].SetSelection(3)
dialog._modelChanged(CODER)
quants[CODER].SetSelection(1)
assert dialog._selected()[CODER]["id"] == "qwen2.5-coder-7b-q6k"
# No coder model: there is nothing to choose in the quant list, and that is said.
models[CODER].SetSelection(6)
dialog._modelChanged(CODER)
assert items(quants[CODER]) == ["No coder model, so there is no quant to choose"] and dialog._selected()[CODER] is None
models[CODER].SetSelection(3)
dialog._modelChanged(CODER)
assert dialog._selected()[CODER]["id"] == "qwen2.5-coder-7b-q6k"  # the quant chosen before is kept

# The choice is kept in the settings as the entry's id, and the files in use are told, so that the unused
# quant can be offered for removal.
before = dialog._missingBytes(dialog._toDownload())
# The user chooses the model for hard cases in Q4_K_M: it joins the download, and the box says it is asked about.
hard.SetSelection(1)
dialog._hardChanged()
assert dialog._toDownload()[-1]["id"] == "qwen3-14b" and dialog._missingBytes(dialog._toDownload()) == before + 9001752960
dialog.hardAsk.SetValue(False)
dialog._finished()
app.ProcessPendingEvents()
assert conf == {"visionModel": "qwen3.5-9b-q6k", "coderModel": "qwen2.5-coder-7b-q6k", "hardModel": "qwen3-14b",
	"hardCases": "always"}, conf
assert chosenKeys == [["qwen3.5-9b@Q6_K", "qwen2.5-coder-7b@Q6_K", "qwen3-14b"]], chosenKeys
dialog.Destroy()

# Opened again, the window shows what was chosen.
again = dialogs.ModelsDialog(None, shelf, conf, suggested, _quiet)
assert again._choices[VISION].GetSelection() == 3 and again._quantChoices[VISION].GetSelection() == 1
assert again._selected()[CODER]["id"] == "qwen2.5-coder-7b-q6k"
# Each list has a label before it, which NVDA reads, with a key of its own.
labels = [child.GetLabel() for child in again.GetChildren() if isinstance(child, wx.StaticText)]
assert labels == ["&Vision model:", "Vision model &quant:", "C&oder model:", "Coder model qu&ant:", "Model for &hard cases:"], labels
assert again._hardSelected()["id"] == "qwen3-14b" and not again.hardAsk.GetValue()
again.Destroy()
# Never chosen, a model for hard cases already on the disk is the one shown; "none" chosen stays none.
withHard = Shelf(list(shelf.onDisk) + [("qwen3-14b", "Qwen3-14B-Q6_K.gguf")])
seen = dialogs.ModelsDialog(None, withHard, {"visionModel": "qwen3.5-2b", "coderModel": ""}, suggested, _quiet)
assert seen._hardSelected()["id"] == "qwen3-14b-q6k" and items(seen.hardChoice)[2] == "Qwen3 14B Q6_K, on this computer"
assert items(seen.hardChoice)[1].endswith(", suggested")  # Q4_K_M is suggested, as for every model
seen._finished()
seen.Destroy()
never = {"visionModel": "qwen3.5-2b", "coderModel": "", "hardModel": "none"}
closed = dialogs.ModelsDialog(None, withHard, never, suggested, _quiet)
assert closed._hardSelected() is None
closed._finished()
assert never["hardModel"] == "none"
closed.Destroy()

# Suggested for what the user wants to do (the owner, 2026-11-19: "suggest model type based on hardware and the task"):
# the button is there only where the computer can be told, the reasons go into the box at the top, the suggested models
# into the lists, and nothing is downloaded or kept until the first button is pressed.
assert dialogs.ModelsDialog(None, shelf, {"visionModel": "qwen3.5-2b", "coderModel": ""}, suggested, _quiet).suggestBtn is None
asked = {"visionModel": "qwen3.5-2b", "coderModel": ""}
window = dialogs.ModelsDialog(None, shelf, asked, suggested, _quiet, machine=lambda: (8151, 31))
assert window.suggestBtn.GetLabel() == "&Suggest models for what I want to do..."
window._suggest(["access"])
text = window.text.GetValue()
assert text.startswith("This computer has 8 GB of graphics memory and 31 GB of memory. For making stubborn programs"), text
assert "For hard cases" in text and text.endswith("you can still choose others."), text
assert window._selected()[VISION]["id"] == "qwen3.5-9b" and window._hardSelected()["id"] == "qwen3-14b"
assert asked == {"visionModel": "qwen3.5-2b", "coderModel": ""}  # nothing kept yet
assert window._toDownload()[-1]["id"] == "qwen3-14b"
# On a small computer the larger model for hard cases is not put into the list, and that is said.
small = dialogs.ModelsDialog(None, shelf, {"visionModel": "qwen3.5-2b", "coderModel": ""}, suggested, _quiet, machine=lambda: (4096, 8))
small._suggest(["code", "hard"])
assert small._hardSelected() is None and "no larger model is suggested" in small.text.GetValue()
assert small._selected()[CODER]["id"] == "qwen2.5-coder-1.5b", small._selected()[CODER]["id"]
assert len(window._purposeLabels()) == len(__import__("visionClaw.claw.advice", fromlist=["x"]).PURPOSES)

# The question before models are suggested is a list of check boxes NVDA reads (the owner, 2026-11-19: "It won't let
# me check and uncheck items in the listbox"). wx.MultiChoiceDialog's list tells NVDA nothing about its check boxes,
# so it is NVDA's own CustomCheckListBox, with the question as its label and the first choice selected.
from visionClaw import checklist  # noqa: E402
assert checklist.checkListClass() is wx.CheckListBox  # no NVDA here: the plain one


class CustomCheckListBox(wx.CheckListBox):
	"""Stands in for NVDA's gui.nvdaControls.CustomCheckListBox, which reports each item's check box to NVDA."""


gui.nvdaControls = types.SimpleNamespace(CustomCheckListBox=CustomCheckListBox)
assert checklist.checkListClass() is CustomCheckListBox
labels = window._purposeLabels()
order = [ident for ident, _words, _role, _pattern in __import__("visionClaw.claw.advice", fromlist=["x"]).PURPOSES]
question = checklist.ChecksDialog(window, "What do you want VisionClaw for most?", "Suggest models",
	[labels[ident] for ident in order])
assert type(question.list) is CustomCheckListBox and question.list.GetSelection() == 0
assert [child.GetLabel() for child in question.GetChildren() if isinstance(child, wx.StaticText)] == [
	"What do you want VisionClaw for most?"]
assert question.list.GetCount() == len(order) and question.checked() == []
question.list.Check(4)
question.list.Check(0)
question.list.Check(4, False)
question.list.Check(2)
assert question.checked() == [0, 2]
assert question.FindWindow(wx.ID_OK) and question.FindWindow(wx.ID_CANCEL)
question.Destroy()
# Asked for real, what the user checked is what is suggested for; Cancel changes nothing.
answers = []


class Answered(checklist.ChecksDialog):
	def ShowModal(self):
		self.Hide()
		for at in answers[0][1]:
			self.list.Check(at)
		return answers.pop(0)[0]


checklist.ChecksDialog, plain = Answered, checklist.ChecksDialog
before = window.text.GetValue()
answers.append((wx.ID_CANCEL, [0]))
window._suggest()
assert window.text.GetValue() == before and not answers
answers.append((wx.ID_OK, [order.index("access")]))
window.text.SetValue("")
window._suggest()
assert window.text.GetValue().startswith("This computer has 8 GB of graphics memory and 31 GB of memory. For making stubborn"), (
	window.text.GetValue())
checklist.ChecksDialog = plain
del gui.nvdaControls
# Every list of check boxes in VisionClaw is made by checklist.py: the window of models on the disk, the memories
# window and a new skill's jobs too. Neither wx.MultiChoiceDialog nor a plain wx.CheckListBox is used anywhere else.
import os  # noqa: E402
import re  # noqa: E402
plugin = os.path.dirname(dialogs.__file__)
for name in sorted(os.listdir(plugin)):
	if name.endswith(".py") and name != "checklist.py":
		with open(os.path.join(plugin, name), encoding="utf-8") as f:
			source = f.read()
		assert not re.search(r"wx\.(MultiChoiceDialog|CheckListBox)\b|CustomCheckListBox", source), name
window.Destroy()
small.Destroy()

# The window of the models on the disk asks with what removing really frees: a shared projector is freed only
# with the last quant of its model.
assert dialogs.quantWords("Q8_0") == "" and dialogs.quantLabel(shelf, {
	"id": "qwen9", "dir": "qwen9", "role": VISION, "name": "Qwen9", "files": [
		{"kind": "model", "name": "Qwen9-IQ2.gguf", "size": 2 ** 30, "sha256": "", "url": ""}]}, "Q4_K_M") == (
	"This model is offered in one file only")
print("OK")
