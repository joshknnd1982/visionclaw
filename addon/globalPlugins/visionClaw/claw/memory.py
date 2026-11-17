# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - what VisionClaw has learned on this computer: short lessons kept between sessions and found
# again by their words when a similar request comes. No NVDA dependencies.

import json
import os
import re
import threading
import time

MAX_LESSONS = 300
MAX_CHARS = 400
_WORD = re.compile(r"[a-z0-9_]{3,}")
_COMMON = frozenset((
	"the and for with that this from have has was were are not but you your can will use using when then "
	"what how why which into out make made does did nvda user step tool please want need set change turn "
	"little bit more less very just some any all get put let now here there").split())
_SUFFIXES = ("ing", "est", "er", "ed", "ly", "s")
# A lesson loses half its weight in this many days, so newer lessons win.
_HALF_LIFE_DAYS = 60


def stem(word):
	"""A word without its ending, so "faster" matches "fast" and "speaking" matches "speak"."""
	for suffix in _SUFFIXES:
		if word.endswith(suffix) and len(word) - len(suffix) >= 3:
			return word[:-len(suffix)]
	return word


def wordList(text):
	"""The telling words of a text in the order they come, without their endings."""
	return [stem(w) for w in _WORD.findall((text or "").lower()) if w not in _COMMON]


def words(text):
	"""The telling words of a text, without their endings."""
	return set(wordList(text))


def score(query, text, extra=0.0):
	"""How well a text matches a query: the share of the query's words found in it."""
	q = words(query)
	if not q:
		return 0.0
	return len(q & words(text)) / len(q) + extra


class Memory:
	def __init__(self, path):
		self._path = path
		self._lock = threading.Lock()
		self._lessons = None

	def _load(self):
		if self._lessons is None:
			try:
				with open(self._path, encoding="utf-8") as f:
					self._lessons = [x for x in json.load(f) if isinstance(x, dict) and x.get("text")]
			except (OSError, ValueError):
				self._lessons = []
		return self._lessons

	def _save(self):
		try:
			os.makedirs(os.path.dirname(self._path), exist_ok=True)
			tmp = self._path + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				json.dump(self._lessons, f, indent=1)
			os.replace(tmp, self._path)
		except OSError:
			pass

	def add(self, text, topic=""):
		"""Keep a lesson. One that says nearly the same as an old lesson replaces it."""
		text = " ".join(str(text or "").split())[:MAX_CHARS]
		if len(text) < 8:
			return False
		with self._lock:
			lessons = self._load()
			mine = words(text)
			for old in lessons:
				theirs = words(old["text"])
				if mine and theirs and len(mine & theirs) / len(mine | theirs) > 0.8:
					lessons.remove(old)
					break
			lessons.append({"text": text, "topic": topic, "time": time.time()})
			del lessons[:-MAX_LESSONS]
			self._save()
		return True

	def search(self, query, limit=3, least=0.25):
		"""The lessons that best match a request, best first."""
		now = time.time()
		with self._lock:
			scored = []
			for lesson in self._load():
				age = max(0.0, now - lesson.get("time", now)) / 86400
				s = score(query, lesson["text"] + " " + lesson.get("topic", "")) * 0.5 ** (age / _HALF_LIFE_DAYS)
				if s >= least:
					scored.append((s, lesson["text"]))
		scored.sort(key=lambda x: -x[0])
		return [text for _s, text in scored[:limit]]

	def forget(self, unwanted):
		"""Drop the lessons for which unwanted(text) is true. Returns how many were dropped."""
		with self._lock:
			lessons = self._load()
			kept = [lesson for lesson in lessons if not unwanted(lesson["text"])]
			dropped = len(lessons) - len(kept)
			if dropped:
				self._lessons = kept
				self._save()
		return dropped

	def all(self):
		with self._lock:
			return [lesson["text"] for lesson in self._load()]

	def clear(self):
		with self._lock:
			self._lessons = []
			self._save()
