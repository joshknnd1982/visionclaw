# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the user's own library: documents the user puts into a folder, such as the manual of a program
# or a game, a page of notes or a guide, which VisionClaw then looks things up in, with NVDA, the program in
# front, its window and Windows (claw/lookup.py). This is VisionClaw's retrieval: every source is cut into
# small passages, plain code finds those that are about the question, and only those are shown to the model
# that answers. Markdown, plain text, web pages saved as files and Word documents are read; nothing in them is
# run, and nothing is fetched. A document whose name names the program in front counts as that program's.
# No NVDA dependencies.

import html
import os
import re
import threading
import zipfile

from . import debuglog, lookup
from .knowledge import sections as markdownSections

KINDS = (".md", ".markdown", ".txt", ".text", ".html", ".htm", ".docx")
MAX_FILES = 300
MAX_BYTES = 8 * 1024 * 1024
# A plain text without headings is cut into sections of about this many characters, at blank lines.
TEXT_SECTION = 1500
README = "README.txt"
_README_TEXT = (
	"This is VisionClaw's library.\n\n"
	"Put documents here that VisionClaw should look things up in: the manual of a program or a game, a guide, "
	"your own notes. VisionClaw reads Markdown (.md), plain text (.txt), web pages saved as files (.html) and Word "
	"documents (.docx), and uses them when you ask it a question, together with NVDA, the program you are in and "
	"Windows. Folders inside this folder are read too.\n\n"
	"Nothing in these files is run, and nothing is sent anywhere. To take a document out, delete it or move it "
	"out of this folder.\n")
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def nameOf(path):
	"""A document's name as the user hears it: its file name without the ending, with - and _ as spaces."""
	return " ".join(re.sub(r"[-_]+", " ", os.path.splitext(os.path.basename(path))[0]).split())


def textSections(text, title):
	"""A plain text as (title, body): at lines that look like headings where it has them, else in pieces at
	blank lines."""
	text = (text or "").replace("\r\n", "\n")
	lines = text.split("\n")
	found, heading, body = [], title, []

	def close():
		joined = " ".join(" ".join(body).split())
		if joined:
			found.append((heading, joined))

	for at, line in enumerate(lines):
		stripped = line.strip()
		underline = at + 1 < len(lines) and re.match(r"^\s*(=+|-+)\s*$", lines[at + 1]) and stripped
		numbered = re.match(r"^\d+(\.\d+)*\.?\s+[A-Z]\S", stripped) and len(stripped) < 80 and not stripped.endswith(".")
		shouting = stripped.isupper() and 3 < len(stripped) < 70 and re.search(r"[A-Z]{3}", stripped)
		if underline or numbered or shouting:
			close()
			heading, body = stripped.rstrip(":"), []
		elif re.match(r"^\s*(=+|-+)\s*$", line) and at and lines[at - 1].strip():
			continue
		else:
			body.append(stripped)
	close()
	if len(found) >= 3:
		return found
	# No headings: pieces of about TEXT_SECTION characters, at blank lines.
	found, piece = [], ""
	for paragraph in re.split(r"\n\s*\n", text):
		paragraph = " ".join(paragraph.split())
		if piece and len(piece) + len(paragraph) > TEXT_SECTION:
			found.append((title, piece))
			piece = ""
		piece = f"{piece} {paragraph}".strip()
	if piece:
		found.append((title, piece))
	return found


def docxSections(path, title):
	"""A Word document as (title, body), at its headings. Read from the file's own XML; nothing in it is run."""
	from xml.etree import ElementTree
	with zipfile.ZipFile(path) as archive:
		info = archive.getinfo("word/document.xml")
		if info.file_size > MAX_BYTES * 4:
			raise ValueError("The document is too large.")
		root = ElementTree.fromstring(archive.read(info))
	found, heading, body = [], title, []
	for paragraph in root.iter(_WORD_NS + "p"):
		style = paragraph.find(f"{_WORD_NS}pPr/{_WORD_NS}pStyle")
		name = style.get(_WORD_NS + "val", "") if style is not None else ""
		text = "".join(node.text or "" for node in paragraph.iter(_WORD_NS + "t")).strip()
		if not text:
			continue
		if re.match(r"(?i)^(heading|title)\s*\d*$", name):
			if body:
				found.append((heading, " ".join(body)))
			heading, body = text, []
		else:
			body.append(text)
	if body:
		found.append((heading, " ".join(body)))
	return found


def read(path):
	"""A document as (title, body) sections, by its kind."""
	title = nameOf(path)
	ending = os.path.splitext(path)[1].lower()
	if os.path.getsize(path) > MAX_BYTES:
		raise ValueError(f"It is larger than {MAX_BYTES // (1024 * 1024)} MB.")
	if ending == ".docx":
		return docxSections(path, title)
	with open(path, encoding="utf-8", errors="replace") as f:
		text = f.read()
	if ending in (".html", ".htm"):
		found = lookup.htmlSections(text)
		if not found:
			body = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", re.sub(
				r"<(script|style)\b.*?</\1>", " ", text, flags=re.DOTALL | re.IGNORECASE))).split())
			found = [(title, body)] if body else []
		return found
	if ending in (".md", ".markdown"):
		found = [(heading, body) for heading, body, _source in markdownSections(text)]
		return found or textSections(text, title)
	return textSections(text, title)


def mentions(name, program):
	"""Whether a document's name names a program: "Notepad++ manual" names notepad++, "reaper user guide"
	names reaper."""
	low = f" {' '.join(re.findall(r'[a-z0-9+]+', (name or '').lower()))} "
	for said in program if isinstance(program, (list, tuple)) else (program,):
		said = " ".join(re.findall(r"[a-z0-9+]+", (said or "").lower()))
		if len(said) >= 3 and f" {said} " in low:
			return True
	return False


class Library:
	"""The documents in one folder and the folders inside it."""

	def __init__(self, folder):
		self.folder = folder
		self._lock = threading.Lock()
		# path -> ((modified, size), sections or None, why it could not be read)
		self._read = {}

	def prepare(self):
		"""Makes the folder, with a file that says what it is for."""
		try:
			os.makedirs(self.folder, exist_ok=True)
			readme = os.path.join(self.folder, README)
			if not os.path.exists(readme):
				with open(readme, "w", encoding="utf-8", newline="\r\n") as f:
					f.write(_README_TEXT)
		except OSError as e:
			debuglog.error("library", "The library folder could not be made", e)

	def files(self):
		"""The documents, by their paths, in a fixed order."""
		found = []
		for top, folders, names in os.walk(self.folder):
			folders.sort()
			for name in sorted(names):
				if name.lower().endswith(KINDS) and name != README and not name.startswith(("~$", ".")):
					found.append(os.path.join(top, name))
					if len(found) >= MAX_FILES:
						return found
		return found

	def documents(self):
		"""Every document as (path, its sections, why it could not be read or ""). A document is read again
		only when it changed."""
		result = []
		with self._lock:
			paths = self.files()
			for gone in set(self._read) - set(paths):
				del self._read[gone]
			for path in paths:
				try:
					stat = os.stat(path)
					stamp = (stat.st_mtime, stat.st_size)
				except OSError:
					continue
				known = self._read.get(path)
				if not known or known[0] != stamp:
					try:
						known = (stamp, read(path), "")
					except Exception as e:
						debuglog.error("library", f"The document {path} could not be read", e)
						known = (stamp, [], str(e) or type(e).__name__)
					self._read[path] = known
				result.append((path, known[1], known[2]))
		return result

	def passages(self, program=()):
		"""Every document as passages for lookup. Those whose names name the program in front are that
		program's."""
		found = []
		for path, sections, _why in self.documents():
			name = nameOf(path)
			mine = mentions(name, program)
			source = lookup.APP if mine else lookup.LIBRARY
			origin = f"your library, {name}"
			for title, body in sections:
				# The document's name counts as part of every heading in it: a question about "Space Trader"
				# finds what its manual says, though the manual does not say "Space Trader" on every page.
				named = lookup.textWords(f"{title} {name}")
				for at, piece in enumerate(lookup.chunks(body)):
					found.append(lookup.Passage(
						source, title if title != name else "", piece, origin, lead=at == 0, named=named))
		return found

	def sections(self):
		"""Every section of every document as (title, body, source), as claw/knowledge.py has them."""
		return [
			(title, body, "library") for _path, sections, _why in self.documents() for title, body in sections]

	def listText(self):
		"""What is in the library, in a few sentences for the user."""
		documents = self.documents()
		if not documents:
			return (
				f"VisionClaw's library is empty. It is the folder {self.folder}. Put documents there, such as the "
				"manual of a program or a game, as Markdown, text, saved web pages or Word documents, and VisionClaw "
				"looks things up in them when you ask a question.")
		good = [(path, sections) for path, sections, why in documents if not why and sections]
		bad = [(path, why) for path, _sections, why in documents if why or not _sections]
		text = (
			f"VisionClaw's library has {len(good)} {'document' if len(good) == 1 else 'documents'}: "
			+ ", ".join(nameOf(path) for path, _sections in good[:20]) + ("" if len(good) <= 20 else ", and more") + ".")
		if bad:
			text += " Could not be read: " + "; ".join(
				f"{nameOf(path)} ({why or 'nothing in it to read'})" for path, why in bad[:5]) + "."
		return text + f" The library is the folder {self.folder}."


# The notes on accessibility interfaces, for an add-on whose purpose names one.
API_NOTES = ("api-uia", "api-msaa-ia2", "api-aria", "api-java-access-bridge")
# All that is added for the model that writes an add-on fits in this many characters: it is a small model.
CODER_CHARS = 900


# The notes on NVDA a passage of the library may lead to.
NVDA_NOTES = ("objects-and-events", "addon-development")


def nvdaNote(knowledge, text, chars=320):
	"""The section of the notes on NVDA that a text is about, or "": the best found whose heading has at least
	two of its telling words in the text, and at least half of them, so that a passage about saving a game is
	not given the note on pressing keys."""
	said = lookup.textWords(text)
	for title, body, _source in knowledge.search(text, 3, sources=NVDA_NOTES):
		heading = lookup.textWords(title)
		shared = heading & said
		if len(shared) >= 2 and len(shared) * 2 >= len(heading):
			return f"[{title}]\n{body[:chars].rsplit(' ', 1)[0] if len(body) > chars else body}"
	return ""


def forCoder(kept, shelf, knowledge, purpose, program=(), chars=CODER_CHARS):
	"""What the model that writes or repairs an NVDA add-on is told besides its own notes: what the user asked
	VisionClaw to remember that belongs with the add-on (their keys, their synthesizer, the program it is
	for), what the user's library says about it, and, when the purpose names an accessibility interface, the
	one section of the notes on it that fits best. Each part is found by plain code; a part that cannot be
	read is left out, because this only helps. Goes into the model's message, never into its system prompt.
	Returns "" or text that begins with a new line."""
	names = list(program) if isinstance(program, (list, tuple)) else [program] if program else []
	parts = []
	try:
		lines = kept.recall(purpose, names[0] if names else "", limit=3, chars=360) if kept is not None else []
		if lines:
			parts.append("What the user asked VisionClaw to remember:\n" + "\n".join(f"- {line}" for line in lines))
	except Exception as e:
		debuglog.error("library", "The memories could not be read for the add-on", e)
	try:
		found = lookup.about(purpose, shelf.passages(names), limit=2, program=names) if shelf is not None else []
		found = [passage for passage in found if passage.source in (lookup.LIBRARY, lookup.APP)]
		if found:
			parts.append("From the user's library:\n" + lookup.resultText(found, budget=360))
			# What the library says can name a thing the request does not, such as where a program shows an
			# amount; NVDA's note on that thing is added when the passage has most of the words of its heading.
			said = " ".join(f"{passage.title} {passage.text}" for passage in found)
			note = nvdaNote(knowledge, said) if knowledge is not None else ""
			if note:
				parts.append("About this in NVDA:\n" + note)
	except Exception as e:
		debuglog.error("library", "The library could not be read for the add-on", e)
	try:
		if knowledge is not None and lookup._API.search(purpose or ""):
			text = knowledge.text(purpose, limit=1, chars=320, sources=API_NOTES)
			if text:
				parts.append("About the accessibility interface:\n" + text)
	except Exception as e:
		debuglog.error("library", "The notes on accessibility interfaces could not be read for the add-on", e)
	text = "\n".join(parts)
	if len(text) > chars:
		text = text[:chars].rsplit("\n", 1)[0]
	return f"\n{text}" if text else ""


__all__ = ["Library", "read", "textSections", "docxSections", "nameOf", "mentions", "forCoder"]
