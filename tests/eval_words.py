# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""How well plain code reads requests in casual words for the add-on writer and questions about a picture, with and
without the lines of understanding.md for each (claw/understand.py, Grammar.read(text, where=...)). Plain Python: no
model, no NVDA. --misses prints what was missed, for the development sets only: never write a line from a held-out set.

  python tests/eval_words.py [addons|addons-held|pictures|pictures-held] [--misses]

For an add-on request, right means claw/codeplan.read makes exactly the expected pieces: the key, or the event, the
kind of control and the state, and whether plain code writes a beep, a fixed sentence or leaves the lines to the model.
For a question about a picture, right means claw/pictures.pieces gives the expected kinds, in order.
"""
import json
import os
import re
import sys

import harness  # noqa: F401
from visionClaw.claw import codeplan, pictures, understand

HERE = os.path.dirname(os.path.abspath(__file__))


def body(action):
	code = codeplan.plainBody(action)[0]
	if code.startswith("tones.beep"):
		return "beep"
	said = re.match(r"ui\.message\((['\"])(.*)\1\)", code)
	return f"say:{said.group(2)}" if said else "model"


def piece(found):
	if found.kind == codeplan.KEY:
		return {"kind": "key", "gesture": found.gesture.lower().removeprefix("kb:"), "body": body(found.action)}
	state = None if not found.state else (found.state[0] if found.state[1] else "!" + found.state[0])
	return {"kind": "event", "event": found.event, "role": found.role or None, "state": state, "body": body(found.action)}


def expected(item):
	return [dict(want, gesture=want["gesture"].lower()) if want.get("gesture") else want for want in item["expect"]]


def addon(text):
	found, _why = codeplan.read(text)
	return [piece(one) for one in found]


def picture(text):
	return [kind for kind, _words in pictures.pieces(text)]


class WithoutOwnLines(understand.Grammar):
	"""VisionClaw's lines without the sections for one orchestrator: what 1.11.0 had."""

	def rules(self):
		return [rule for rule in super().rules() if rule.scope is None]


def score(name, grammar, misses=False):
	"""(right, of how many), with grammar as the one every orchestrator reads with. The whole request is understood with
	the lines every request gets before the add-on writer or the look tool is reached, as in the orchestrator; the reader
	then reads it again with its own lines (codeplan.read, pictures.pieces)."""
	data = json.load(open(os.path.join(HERE, "eval", f"words-{name}.json"), encoding="utf-8"))["requests"]
	read = addon if name.startswith("addons") else picture
	right = 0
	understand.use(grammar)
	try:
		for item in data:
			text = grammar.read(item["request"]).text
			got = read(text)
			want = expected(item) if name.startswith("addons") else item["expect"]
			ok = got == want
			right += ok
			if misses and not ok:
				print(f"  miss: {item['request']!r}" + (f" understood as {text!r}" if text != item["request"] else ""))
				print(f"        got {got}\n        want {want}")
	finally:
		understand.use(None)
	return right, len(data)


def main():
	names = [arg for arg in sys.argv[1:] if not arg.startswith("--")] or ["addons", "addons-held", "pictures", "pictures-held"]
	misses = "--misses" in sys.argv
	for name in names:
		before = score(name, WithoutOwnLines(None))
		after = score(name, understand.Grammar(None), misses and not name.endswith("held"))
		print(f"{name}: {before[0]} of {before[1]} with only the lines every request gets, {after[0]} with the lines for "
			f"{'add-ons' if name.startswith('addons') else 'questions about a picture'} too")


if __name__ == "__main__":
	main()
