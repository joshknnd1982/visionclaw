# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The window that makes a portable copy (portableui.py) with the real wxPython and stand-ins for NVDA's gui
and ui: what it says goes into the copy, the questions and refusals for each place, and what it says when the
copy is made or stopped. The copy itself is run without its progress bar. Skipped when wxPython is not
installed. Nothing is shown on the screen.

  python tests/test_portable_window.py
"""
import os
import sys
import tempfile
import threading
import types
import zipfile

import harness  # noqa: F401

try:
	import wx
except ImportError:
	print("wxPython is not installed; skipped.\nOK")
	sys.exit(0)

said, answers, opened = [], [], []
gui = types.ModuleType("gui")
gui.mainFrame = types.SimpleNamespace(prePopup=lambda: None, postPopup=lambda: None,
	onCreatePortableCopyCommand=lambda evt: opened.append("NVDA's window"))
gui.messageBox = lambda text, *args, **kwargs: said.append(text) or (answers.pop(0) if answers else wx.OK)
sys.modules["gui"] = gui
sys.modules["ui"] = types.SimpleNamespace(message=lambda text: said.append(text))
import builtins  # noqa: E402
builtins._ = getattr(builtins, "_", None) or (lambda text: text)
sys.modules["addonHandler"] = types.SimpleNamespace(initTranslation=lambda: None,
	getCodeAddon=lambda: types.SimpleNamespace(manifest={"version": "9.9.9"}))

from visionClaw import portableui  # noqa: E402
from visionClaw.claw import portable  # noqa: E402

work = tempfile.mkdtemp()
addonDir = os.path.join(work, "addons", "visionClaw")


def write(path, text="x"):
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as f:
		f.write(text)


write(os.path.join(addonDir, "manifest.ini"), "name = visionClaw")
write(os.path.join(addonDir, "data", "models", "q", "model.gguf"), "m" * 3000)
write(os.path.join(addonDir, "data", "memories", "one.md"), "remembered")
write(os.path.join(addonDir, "data", "training", "afb", "lesson.md"), "a lesson")
write(os.path.join(addonDir, "data", "something-new", "file.md"), "whatever the user keeps there")
plugin = types.SimpleNamespace(addonDir=addonDir, dataDir=os.path.join(addonDir, "data"),
	portableSettings=lambda: {"visionModel": "qwen3.5-9b", "updateLastCheck": "5"})
app = wx.App(False)
dialog = portableui.PortableDialog(None, plugin)

# What goes in is said in words: everything, each part with its size, also a folder VisionClaw has no name for.
summary = dialog.summary.GetValue()
assert "nothing left out" in summary and "VisionClaw 9.9.9" in summary and "4 files" in summary, summary
assert "the models: 2.9 KB" in summary and "what you asked VisionClaw to remember" in summary, summary
assert "something-new" in summary and "the training material" in summary, summary
assert "keep their copyright" in summary and "FAT32" in summary, summary
for words in ("click", "look at", "as you can see", "hover"):
	assert words not in summary.lower(), words

started = []
dialog._start = lambda kind, place, found, extras, total: started.append((kind, place, found, extras, total))


def make(folder, kind):
	del said[:]
	dialog.folder.SetValue(folder)
	dialog.kind.SetSelection(kind)
	dialog._make()


# No folder, a folder inside VisionClaw itself: said, nothing started.
make("", portableui.FILE)
assert said and "Choose a folder" in said[0] and not started
make(os.path.join(addonDir, "data"), portableui.FILE)
assert "inside VisionClaw itself" in said[0] and not started

# One file: its name says it is the portable one, and the settings go with it.
out = os.path.join(work, "stick")
os.makedirs(out)
portableui.fileSystemOf = lambda folder: "exFAT"
make(out, portableui.FILE)
kind, place, found, extras, total = started.pop()
assert kind == portableui.FILE and place == os.path.join(out, "VisionClaw-9.9.9-portable.nvda-addon"), place
assert {arc for _f, arc, _s in found} >= {"manifest.ini", "data/models/q/model.gguf", "data/something-new/file.md"}
assert '"visionModel": "qwen3.5-9b"' in extras["data/carried-settings.json"].decode() and "updateLastCheck" not in \
	extras["data/carried-settings.json"].decode()
# The file is made, and the window says where it is and that NVDA asks before it installs it.
size = portable.writeBundle(found, place, extras, threading.Event())
dialog._stop = threading.Event()
del said[:]
dialog._finished(kind, place, size, None)
assert "Done." in said[0] and place in said[0] and "NVDA asks before it installs it" in said[0], said
assert dialog._stop is None
with zipfile.ZipFile(place) as z:
	assert "data/carried-settings.json" in z.namelist()
# There already: asked before it is replaced; no means nothing happens.
answers.append(wx.NO)
make(out, portableui.FILE)
assert "Replace it?" in said[0] and not started

# FAT32 cannot hold the file; a full drive has no room. Both are said, with sizes, and nothing starts.
portableui.fileSystemOf = lambda folder: "FAT32"
real = portable.FAT_LIMIT
portable.FAT_LIMIT = 100
answers.append(wx.YES)
make(out, portableui.FILE)
assert "FAT32" in said[-1] and "erases everything" in said[-1] and not started, said
portable.FAT_LIMIT = real
portableui.fileSystemOf = lambda folder: "NTFS"
realCheck = portable.check
portable.check = lambda bundle, sizes, free, fs: (portable.NO_SPACE, 10 * 1024 ** 3)
answers.append(wx.YES)
make(out, portableui.FILE)
assert "not enough room" in said[-1] and "10.0 GB" in said[-1] and not started, said
portable.check = realCheck

# Into a portable NVDA: none there, and NVDA's own window is offered; an installed NVDA is refused.
answers.append(wx.YES)
make(out, portableui.INTO_NVDA)
assert "no NVDA in this folder" in said[0] and not started
installed = os.path.join(work, "Program Files", "NVDA")
write(os.path.join(installed, "nvda.exe"))
write(os.path.join(installed, "uninstall.exe"))
make(installed, portableui.INTO_NVDA)
assert "installed on this computer" in said[0] and not started
# A portable NVDA on the drive: VisionClaw goes into its add-ons; one that has VisionClaw is asked about first.
nvda = os.path.join(out, "NVDA")
write(os.path.join(nvda, "nvda.exe"))
make(out, portableui.INTO_NVDA)
kind, place, found, extras, total = started.pop()
assert kind == portableui.INTO_NVDA and place == os.path.join(nvda, "userConfig", "addons", "visionClaw"), place
portable.copyTo(found, place, extras)
answers.append(wx.NO)
make(out, portableui.INTO_NVDA)
assert "has VisionClaw already" in said[0] and not started
answers.append(wx.YES)
make(out, portableui.INTO_NVDA)
assert started.pop()[1] == place
del said[:]
dialog._finished(portableui.INTO_NVDA, place, (0, 5), None)
assert "Start that NVDA with nvda.exe" in said[0] and "5 files were there already" in said[0], said
# Stopped partway, the user is told to make it again to finish it.
del said[:]
dialog._finished(portableui.INTO_NVDA, place, None, portable.Stopped())
assert "Stopped partway" in said[0] and "skipped" in said[0], said
del said[:]
dialog._finished(portableui.FILE, place, None, portable.Stopped())
assert said[0] == "Stopped. Nothing was left behind.", said

# Closing while the copy runs is refused with a sentence; afterwards it closes.
dialog._stop = threading.Event()
veto = []
dialog._onClose(types.SimpleNamespace(Veto=lambda: veto.append(True)))
assert veto and "still being made" in said[-1]
dialog._stop = None
# NVDA's own window for a portable NVDA opens from the button.
dialog._openNvdaWindow()
app.ProcessPendingEvents()
wx.CallAfter(app.ExitMainLoop)
app.MainLoop()
assert opened == ["NVDA's window"] * 2, opened  # once after the question above, once from the button
print("OK")
