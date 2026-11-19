# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Checks how streamed text is split into spoken pieces, and that it is said whole when the user chose that."""
import importlib.util
import os
import re
import threading

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "addon", "globalPlugins", "visionClaw", "__init__.py")
src = open(SRC, encoding="utf-8").read()
# How the pieces are cut is claw/sentences.py, which only imports re, so it is loaded by its path.
spec = importlib.util.spec_from_file_location(
	"sentences", os.path.join(os.path.dirname(SRC), "claw", "sentences.py"))
sentences = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sentences)
out = []
ns = {"re": re, "_speak": out.append, "sentences": sentences}
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

# Said whole, the user's choice for a slow computer: nothing until the model has finished, then all of it at once,
# with the same pieces of Markdown left out; onFirst when it is spoken, not when the text begins to arrive.
del out[:]
first = []
sp = ns["SentenceSpeaker"](threading.Event(), onFirst=lambda: first.append(len(out)), whole=True)
assert sp.whole
for ch in text:
	sp.feed(ch)
assert out == [] and first == [] and not sp.spokeAnything
sp.flush()
assert len(out) == 1 and first == [0] and sp.spokeAnything, out
assert "**" not in out[0] and out[0].startswith("The VAT number:") and out[0].endswith("four items. Done."), out[0]
# What was written before the model was asked again from the start is forgotten, streamed or whole.
for whole in (False, True):
	del out[:]
	sp = ns["SentenceSpeaker"](threading.Event(), whole=whole)
	sp.feed("Half a sente")
	sp.drop()
	sp.feed("A whole new description, written again from the start.")
	sp.flush()
	assert " ".join(out) == "A whole new description, written again from the start.", (whole, out)

# The splitter itself: a long first sentence is begun at a comma, an abbreviation does not end a sentence, a piece
# that says nothing does not count as begun, and a stream cut into any pieces gives the same words.
pieces = []
cut = sentences.Sentences(lambda piece: pieces.append(piece) or True)
cut.feed("To read the title of the window you are in right now, press NVDA+t, and to hear it spelled")
assert pieces == ["To read the title of the window you are in right now, press NVDA+t,"], pieces
assert cut.started
cut.feed(", press it twice. Dr. Smith wrote this. ")
cut.flush()
assert pieces[1:] == [" and to hear it spelled, press it twice.", " Dr. Smith wrote this. "], pieces
said = []
quiet = sentences.Sentences(lambda piece: said.append(piece) and False)
quiet.feed("**\n")
quiet.flush()
assert not quiet.started
long = " ".join(f"Sentence number {n} of a long answer, which goes on for a while." for n in range(40))
for size in (1, 3, 17, 500):
	pieces = []
	cut = sentences.Sentences(lambda piece: pieces.append(piece) or True)
	for at in range(0, len(long), size):
		cut.feed(long[at:at + size])
	cut.flush()
	assert "".join(pieces) == long and len(pieces) > 10, (size, len(pieces))
print("OK")
