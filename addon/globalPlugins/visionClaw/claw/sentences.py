# Copyright (C) 2026 Athiban Vijay
# Modified for VisionClaw, 2026, by Josh Kennedy: taken out of the add-on's SentenceSpeaker into a module of its own,
# so that the answer to a request is cut the same way as a description; and the choice to say it whole.
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - text that a model is still writing, cut into pieces that can be spoken one at a time: a sentence, a
# line, or at the start a long first clause, so that speech begins before the model has finished. Or, where the user
# turned that off (the setting "streamAnswers"), all of it at once when the model has finished: on a slow computer
# speech can stutter while the model writes. Only imports re, so that tests/test_speaker.py can load it by its path.
# No NVDA dependencies.

import re


class Sentences:
	"""Streamed text cut into pieces to be spoken. say(piece) is called with each piece, and gives back whether
	anything of it was said (a piece that is only a Markdown mark says nothing). whole: nothing is given until
	flush(), and then all of it at once."""

	_END = re.compile(r"(\S*)[.!?。！？](?=\s)|\n")
	# Shorter pieces are joined with the next one, so list labels like "Phone number:" are not spoken alone.
	MIN_CHARS = 30
	# A long first sentence is started at a comma once it is this long, so speech begins sooner.
	FIRST_CLAUSE_CHARS = 60
	_CLAUSE = re.compile(r",(?=\s)")

	def __init__(self, say, whole=False):
		self._say = say
		self.whole = bool(whole)
		self._buf = ""
		# Whether anything was said yet.
		self.started = False

	def feed(self, delta):
		self._buf += delta or ""
		if self.whole:
			return
		pos = 0
		while True:
			m = self._END.search(self._buf, pos)
			if not m:
				self._firstClause()
				return
			pos = m.end()
			word = m.group(1) or ""
			# "R." "Nr." "Tel." are abbreviations or initials, not sentence ends.
			if 0 < len(word) <= 3 and word[0].isupper():
				continue
			if len(self._buf[:pos].strip()) < self.MIN_CHARS:
				continue
			self._give(self._buf[:pos])
			self._buf = self._buf[pos:]
			pos = 0

	def _firstClause(self):
		if self.started or len(self._buf) < self.FIRST_CLAUSE_CHARS:
			return
		commas = [m.end() for m in self._CLAUSE.finditer(self._buf) if m.end() >= self.MIN_CHARS]
		if commas:
			self._give(self._buf[:commas[-1]])
			self._buf = self._buf[commas[-1]:]

	def flush(self):
		"""Say what is left: the end of the last sentence, or everything when the text is said whole."""
		text, self._buf = self._buf, ""
		self._give(text)

	def drop(self):
		"""Forget what was not said yet: the model is asked again from the start."""
		self._buf = ""

	def _give(self, text):
		if text.strip() and self._say(text):
			self.started = True
