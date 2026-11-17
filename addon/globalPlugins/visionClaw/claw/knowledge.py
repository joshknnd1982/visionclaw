# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what the models can read up on: notes about NVDA and its add-on system, in small sections that
# are found by their words. The notes are the .md files in claw/knowledge; other sources, like NVDA's own user
# guide, can be added while NVDA runs. No NVDA dependencies.

import os
import re

from .llm import clip
from .memory import score, words

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")
SECTION_CHARS = 900
_HEADING = re.compile(r"^#{1,3}\s+(.*)$", re.MULTILINE)


def sections(text, source=""):
	"""Split a Markdown text into (title, body, source) at its headings."""
	found = []
	marks = list(_HEADING.finditer(text))
	for i, mark in enumerate(marks):
		end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
		body = text[mark.end():end].strip()
		if body:
			found.append((mark.group(1).strip(), body, source))
	return found


class Knowledge:
	def __init__(self, folder=FOLDER):
		self._folder = folder
		self._sections = None
		# Sources read only when first searched: name -> function returning [(title, body, source)].
		self._lazy = {}

	def addSource(self, name, loader):
		self._lazy[name] = loader

	def replaceSource(self, name, loader):
		"""Read a source again, after what it reads from has changed."""
		if self._sections is not None:
			self._sections = [section for section in self._sections if section[2] != name]
		self._lazy[name] = loader

	def _load(self):
		if self._sections is None:
			self._sections = []
			try:
				names = sorted(os.listdir(self._folder))
			except OSError:
				names = []
			for name in names:
				if name.endswith(".md"):
					with open(os.path.join(self._folder, name), encoding="utf-8") as f:
						self._sections += sections(f.read(), name[:-3])
		for name, loader in list(self._lazy.items()):
			del self._lazy[name]
			try:
				self._sections += loader()
			except Exception:
				pass  # a source that cannot be read is simply not searched
		return self._sections

	def search(self, query, limit=3, least=0.2, sources=None):
		"""The sections that best match, as (title, body, source), best first."""
		scored = []
		for title, body, source in self._load():
			if sources and source not in sources:
				continue
			# A match in the title counts for more than one in the body.
			s = score(query, body) + 1.5 * score(query, title)
			if source == "guides":
				# The downloaded guides are long and written for programmers; VisionClaw's own short notes,
				# written for small models, win where both fit equally well.
				s *= 0.8
			if s >= least:
				scored.append((s, title, body, source))
		scored.sort(key=lambda x: -x[0])
		return [(title, body, source) for _s, title, body, source in scored[:limit]]

	def text(self, query, limit=3, chars=SECTION_CHARS, sources=None):
		"""The best matching sections as one text for a prompt, or "" if nothing matches."""
		return "\n\n".join(
			f"[{title}]\n{clip(body, chars)}" for title, body, _source in self.search(query, limit, sources=sources))

	def count(self):
		return len(self._load())


__all__ = ["Knowledge", "sections", "words"]
