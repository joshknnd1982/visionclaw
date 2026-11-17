# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the latest guides for people who write for NVDA, kept on this computer as Markdown for the
# models to read up in: the NVDA Developer Guide from NV Access, and the NVDA Add-on Development Guide from
# the NVDA add-ons community. They are downloaded only when the user asks and has said yes; the addresses are
# fixed here and nothing but the two requests is sent. What comes back is text for reading, never run.
# No NVDA dependencies.

import datetime
import json
import os
import re
from html.parser import HTMLParser

from .knowledge import sections

SOURCE = "guides"
SOURCES = (
	{"id": "nvda-developer-guide", "title": "NVDA Developer Guide", "by": "NV Access",
		"url": "https://download.nvaccess.org/documentation/developerGuide.html", "html": True},
	{"id": "nvda-addon-development-guide", "title": "NVDA Add-on Development Guide", "by": "the NVDA add-ons community",
		"url": "https://raw.githubusercontent.com/wiki/nvdaaddons/DevGuide/NVDA-Add-on-Development-Guide.md", "html": False},
)
# The only places a guide may come from, also after a redirect.
HOSTS = ("download.nvaccess.org", "www.nvaccess.org", "raw.githubusercontent.com")
MAX_BYTES = 3000000
# A guide shorter than this is not a guide: an error page, or an empty answer.
MIN_CHARS = 5000
_SKIPPED = ("script", "style", "head", "nav", "noscript", "svg")
_BLOCKS = ("p", "div", "section", "article", "ul", "ol", "dl", "table", "blockquote", "tr", "dt", "dd")


class _ToMarkdown(HTMLParser):
	def __init__(self):
		super().__init__(convert_charrefs=True)
		self.out = []
		self._skip = 0
		self._pre = 0

	def handle_starttag(self, tag, attrs):
		if tag in _SKIPPED:
			self._skip += 1
		elif self._skip:
			return
		elif re.fullmatch(r"h[1-6]", tag):
			self.out.append("\n\n" + "#" * int(tag[1]) + " ")
		elif tag == "pre":
			self._pre += 1
			self.out.append("\n\n```\n")
		elif tag == "li":
			self.out.append("\n- ")
		elif tag == "br":
			self.out.append("\n")
		elif tag in ("td", "th"):
			self.out.append(" | ")
		elif tag == "code" and not self._pre:
			self.out.append("`")
		elif tag in _BLOCKS:
			self.out.append("\n\n")

	def handle_endtag(self, tag):
		if tag in _SKIPPED:
			self._skip = max(0, self._skip - 1)
		elif self._skip:
			return
		elif tag == "pre" and self._pre:
			self._pre -= 1
			self.out.append("\n```\n\n")
		elif tag == "code" and not self._pre:
			self.out.append("`")
		elif re.fullmatch(r"h[1-6]", tag) or tag in _BLOCKS:
			self.out.append("\n\n")

	def handle_data(self, data):
		if self._skip:
			return
		self.out.append(data if self._pre else re.sub(r"\s+", " ", data))


def toMarkdown(html):
	"""A web page as Markdown: its headings, paragraphs, lists and code, without scripts, styles and menus."""
	parser = _ToMarkdown()
	parser.feed(html)
	parser.close()
	return tidy("".join(parser.out))


def tidy(text):
	"""Markdown with its lines trimmed and no more than one empty line in a row. Code is left as it is."""
	lines, inCode, empty = [], False, 0
	for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
		if line.strip().startswith("```"):
			inCode = not inCode
		if not inCode:
			line = line.strip()
			# A heading's own anchor mark, as wikis and NVDA's pages add them.
			if line.startswith("#"):
				line = re.sub(r"\s*(\{#[^}]*\}|¶)\s*$", "", line)
		else:
			line = line.rstrip()
		empty = empty + 1 if not line else 0
		if empty <= 1:
			lines.append(line)
	return "\n".join(lines).strip() + "\n"


def _path(folder, source):
	return os.path.join(folder, source["id"] + ".md")


def update(folder, fetch, cancel=None, today=None):
	"""Download every guide and keep it as Markdown. fetch(url) returns the text at an address, or raises.
	A guide that cannot be fetched or does not look like a guide leaves the copy that is there untouched.
	Returns {"got": [(title, how many sections)], "failed": [(title, why)]}."""
	os.makedirs(folder, exist_ok=True)
	got, failed = [], []
	for source in SOURCES:
		if cancel is not None and cancel.is_set():
			break
		try:
			text = fetch(source["url"])
			markdown = toMarkdown(text) if source["html"] else tidy(text)
			count = len(sections(markdown))
			if len(markdown) < MIN_CHARS or count < 5:
				raise ValueError("what came back is not the guide")
		except Exception as e:
			failed.append((source["title"], f"{type(e).__name__}: {e}"[:160]))
			continue
		tmp = _path(folder, source) + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			f.write(markdown)
		os.replace(tmp, _path(folder, source))
		got.append((source["title"], count))
	if got:
		kept = stored(folder)
		day = today or datetime.date.today().isoformat()
		for title, count in got:
			kept[title] = {"date": day, "sections": count}
		with open(os.path.join(folder, "guides.json"), "w", encoding="utf-8") as f:
			json.dump(kept, f, indent=1)
	return {"got": got, "failed": failed}


def stored(folder):
	"""The guides on this computer: {title: {"date", "sections"}}."""
	try:
		with open(os.path.join(folder, "guides.json"), encoding="utf-8") as f:
			found = json.load(f)
		return found if isinstance(found, dict) else {}
	except (OSError, ValueError):
		return {}


def load(folder):
	"""Every section of the guides on this computer, as (title, body, source), for the knowledge search."""
	found = []
	for source in SOURCES:
		try:
			with open(_path(folder, source), encoding="utf-8") as f:
				found += [(f"{source['title']}: {title}", body, SOURCE) for title, body, _s in sections(f.read())]
		except OSError:
			continue
	return found


def summary(result):
	"""What an update did, in sentences."""
	lines = []
	for title, count in result["got"]:
		lines.append(f"Downloaded the {title} and kept it as Markdown, {count} sections.")
	for title, why in result["failed"]:
		lines.append(f"The {title} could not be downloaded ({why}); an earlier copy, if there is one, is still used.")
	if result["got"]:
		lines.append("The models now read up in it when they plan, answer questions about NVDA, and write add-ons.")
	return " ".join(lines) or "Nothing was downloaded."


def storedText(folder):
	kept = stored(folder)
	if not kept:
		return "No developer guides have been downloaded yet. Ask VisionClaw to get the latest NVDA developer guides."
	return " ".join(f"The {title} from {info.get('date', 'an unknown day')}, {info.get('sections', 0)} sections." for title, info in kept.items())
