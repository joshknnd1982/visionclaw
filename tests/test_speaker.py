# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Checks how streamed text is split into spoken pieces."""
import os
import re
import threading

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "addon", "globalPlugins", "visionClaw", "__init__.py")
src = open(SRC, encoding="utf-8").read()
out = []
ns = {"re": re, "_speak": out.append}
exec(src[src.index("_MARKDOWN ="):src.index("class GlobalPlugin")], ns)

text = (
	'The VAT number:\n"MwSt Nr.: 430 234"\nPhone number:\n"Tel.: 033 853 67 16"\n'
	"**Email:** a@b.ch. The name is Familie R. Müller, printed at the top. "
	"The total is CHF 54.50 for four items. Done."
)
sp = ns["SentenceSpeaker"](threading.Event())
for ch in text:  # one character at a time, like the worst-case stream
	sp.feed(ch)
sp.flush()
for o in out:
	print(repr(o))
assert all("**" not in o for o in out)
assert not any(o.endswith("R.") or o.endswith("Tel.:") for o in out)
assert any("54.50 for four items." in o for o in out)

# onFirst is called once, just before the first piece is spoken: from then on a key that silences NVDA stops the
# description. Not when the text only begins to arrive, nor when nothing is spoken.
del out[:]
first = []
sp = ns["SentenceSpeaker"](threading.Event(), onFirst=lambda: first.append(len(out)))
sp.feed("A short")
assert first == [] and out == []
sp.feed(" start of a description that goes on. And more of it follows here.")
assert first == [0] and len(out) == 1, (first, out)
sp.feed(" Another sentence that is long enough to be said. ")
sp.flush()
assert first == [0] and len(out) >= 2, (first, out)
stopped = threading.Event()
stopped.set()
sp = ns["SentenceSpeaker"](stopped, onFirst=lambda: first.append("stopped"))
sp.feed("A description that was stopped before it was spoken. ")
sp.flush()
assert "stopped" not in first
print("OK")
