# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The memories window (memoriesui.py) with the real wxPython and stand-ins for NVDA's gui and ui: the list
shows every memory, the selected one is shown whole, Forget checked deletes only the checked ones after a
question, Forget all deletes the rest, and a no deletes nothing. Skipped when wxPython is not installed.
Nothing is shown on the screen.

  python tests/test_memories_window.py
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
gui = types.ModuleType("gui")
gui.mainFrame = types.SimpleNamespace(prePopup=lambda: None, postPopup=lambda: None)
gui.messageBox = lambda question, *args, **kwargs: said.append(question) or answers.pop(0)
sys.modules["gui"] = gui
sys.modules["ui"] = types.SimpleNamespace(message=lambda text: said.append(text))
import builtins  # noqa: E402
builtins._ = getattr(builtins, "_", None) or (lambda text: text)
sys.modules.setdefault("addonHandler", types.SimpleNamespace(initTranslation=lambda: None))

from visionClaw import memoriesui  # noqa: E402
from visionClaw.claw import memories  # noqa: E402

app = wx.App(False)
kept = memories.Memories(os.path.join(tempfile.mkdtemp(), "memories"))
kept.add("my braille display is a Focus 40", asked="remember that my braille display is a Focus 40")
kept.add("I prefer short answers")
kept.add("in this game the map key is M", program="spacetrader")
gui.mainFrame = None
dialog = memoriesui.MemoriesDialog(None, kept)
gui.mainFrame = types.SimpleNamespace(prePopup=lambda: None, postPopup=lambda: None)

# The newest first, each saying what it is about.
items = [dialog.list.GetString(at) for at in range(dialog.list.GetCount())]
assert len(items) == 3 and items[0].startswith("In spacetrader: In this game the map key is M. (about a program"), items
assert items[2].startswith("Your braille display is a Focus 40. (about you"), items
assert "3 things" in dialog.total.GetLabel()
# The selected memory is shown whole, with the user's own words and its file.
dialog.list.SetSelection(2)
dialog._showDetail()
detail = dialog.detail.GetValue()
assert "Your braille display is a Focus 40." in detail and "In your words: remember that my braille display" in detail
assert "Kept in the file:" in detail, detail

# Nothing checked: nothing is asked and nothing deleted.
dialog._forget(checkedOnly=True)
assert said[-1].startswith("No memory is checked") and len(kept.all()) == 3
# Checked, and the user says no: nothing is deleted.
dialog.list.Check(1)
answers.append(wx.NO)
dialog._forget(checkedOnly=True)
assert said[-1].startswith("Forget the 1 checked memories?") and len(kept.all()) == 3
# Checked, and the user says yes: only that one goes, and the index follows.
answers.append(wx.YES)
dialog._forget(checkedOnly=True)
assert [entry.title for entry in kept.all()] == ["Your braille display is a Focus 40.", "In this game the map key is M."]
assert said[-1] == "Forgotten: 1." and dialog.list.GetCount() == 2
assert "short answers" not in open(os.path.join(kept.folder, memories.INDEX), encoding="utf-8").read()
# Forget all and start over.
answers.append(wx.YES)
dialog._forget(checkedOnly=False)
assert said[-2].startswith("Forget everything VisionClaw remembers, 2 memories, and start over?")
assert kept.all() == [] and said[-1].startswith("Forgotten. VisionClaw remembers nothing now")
assert dialog.list.GetCount() == 0 and not dialog.forgetAllBtn.IsEnabled()
assert "Nothing yet." in open(os.path.join(kept.folder, memories.INDEX), encoding="utf-8").read()
dialog.Destroy()
print("OK")
