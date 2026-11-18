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
assert len(items(models[CODER])) == 6 and items(models[CODER])[-1].startswith("No coder model now")
assert items(models[CODER])[3] == "Qwen2.5 Coder 7B, Q4_K_M 4466 MB to download, Q6_K 5964 MB to download"
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
models[CODER].SetSelection(5)
dialog._modelChanged(CODER)
assert items(quants[CODER]) == ["No coder model, so there is no quant to choose"] and dialog._selected()[CODER] is None
models[CODER].SetSelection(3)
dialog._modelChanged(CODER)
assert dialog._selected()[CODER]["id"] == "qwen2.5-coder-7b-q6k"  # the quant chosen before is kept

# The choice is kept in the settings as the entry's id, and the files in use are told, so that the unused
# quant can be offered for removal.
dialog._finished()
app.ProcessPendingEvents()
assert conf == {"visionModel": "qwen3.5-9b-q6k", "coderModel": "qwen2.5-coder-7b-q6k"}, conf
assert chosenKeys == [["qwen3.5-9b@Q6_K", "qwen2.5-coder-7b@Q6_K"]], chosenKeys
dialog.Destroy()

# Opened again, the window shows what was chosen.
again = dialogs.ModelsDialog(None, shelf, conf, suggested, _quiet)
assert again._choices[VISION].GetSelection() == 3 and again._quantChoices[VISION].GetSelection() == 1
assert again._selected()[CODER]["id"] == "qwen2.5-coder-7b-q6k"
# Each list has a label before it, which NVDA reads, with a key of its own.
labels = [child.GetLabel() for child in again.GetChildren() if isinstance(child, wx.StaticText)]
assert labels == ["&Vision model:", "Vision model &quant:", "C&oder model:", "Coder model qu&ant:"], labels
again.Destroy()

# The window of the models on the disk asks with what removing really frees: a shared projector is freed only
# with the last quant of its model.
assert dialogs.quantWords("Q8_0") == "" and dialogs.quantLabel(shelf, {
	"id": "qwen9", "dir": "qwen9", "role": VISION, "name": "Qwen9", "files": [
		{"kind": "model", "name": "Qwen9-IQ2.gguf", "size": 2 ** 30, "sha256": "", "url": ""}]}, "Q4_K_M") == (
	"This model is offered in one file only")
print("OK")
