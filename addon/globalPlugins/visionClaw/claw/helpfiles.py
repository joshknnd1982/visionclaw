# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the help that is on this computer already, kept as Markdown files: NVDA's own user guide, its
# list of what is new, and the help of every add-on. The owner said on 2026-11-18: "all guides, wikis, and
# other materials should be converted to markdown (md) files to make it as easy as possible for visionclaw
# and its local AI models to work and interact with and learn from". The developer guides, the training
# material, the notes on programs and the memories are Markdown already; this is the rest.
#
# A page of help is turned into Markdown once, and again when the page it was made from has changed or is
# another one, as after an update of NVDA or of an add-on, or when NVDA's language was changed. From then on
# VisionClaw reads the Markdown file, so what it looks things up in and what the user can open and read are
# the same text. Each file says at its top what it was made from. Nothing here goes online, and a file that
# cannot be written is no fault: the page is then read as it is. No NVDA dependencies.

import os
import re

MADE_FROM = "Made by VisionClaw from "
_HEADING = re.compile(r"^## (.*)$")


def _oneLine(text):
	return " ".join(str(text or "").split())


def toMarkdown(title, source, sections):
	"""A page of help as Markdown: its title, the file it was made from, then every section under a heading of
	its own, its text as sentences on one line."""
	lines = [f"# {_oneLine(title)}", "", f"{MADE_FROM}{source}", ""]
	for heading, body in sections:
		body = _oneLine(body)
		# A line of text that begins like a heading would be taken for one when the file is read again.
		lines += [f"## {_oneLine(heading)}", "", ("\\" + body) if body.startswith("#") else body, ""]
	return "\n".join(lines)


def fromMarkdown(text):
	"""The sections of a file toMarkdown wrote, as (heading, text)."""
	found, heading, body = [], None, []
	for line in str(text or "").split("\n"):
		mark = _HEADING.match(line)
		if mark:
			if heading is not None and body:
				found.append((heading, " ".join(body)))
			heading, body = mark.group(1), []
		elif heading is not None and line.strip():
			body.append(line[1:] if line.startswith("\\#") else line)
	if heading is not None and body:
		found.append((heading, " ".join(body)))
	return found


def madeFrom(text):
	"""The file a Markdown file says it was made from, or ""."""
	for line in str(text or "").split("\n", 6)[:6]:
		if line.startswith(MADE_FROM):
			return line[len(MADE_FROM):].strip()
	return ""


def kept(source, dest, title, make):
	"""The sections of a page of help, read from its Markdown file. The file is made first when it is not
	there, is older than the page, or was made from another page. source: the page as it is on this computer.
	make(text of the page) gives its sections as (heading, text). Returns the sections; [] when there is no
	page. Never raises for a file that cannot be written: the page is then read as it is."""
	if not source or not os.path.isfile(source):
		return []
	try:
		if os.path.isfile(dest) and os.path.getmtime(dest) >= os.path.getmtime(source):
			with open(dest, encoding="utf-8") as f:
				text = f.read()
			if os.path.normcase(madeFrom(text)) == os.path.normcase(str(source)):
				return fromMarkdown(text)
	except (OSError, UnicodeDecodeError):
		pass
	with open(source, encoding="utf-8", errors="replace") as f:
		sections = [(heading, _oneLine(body)) for heading, body in make(f.read()) if _oneLine(heading) and _oneLine(body)]
	try:
		os.makedirs(os.path.dirname(dest), exist_ok=True)
		tmp = dest + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			f.write(toMarkdown(title, source, sections))
		os.replace(tmp, dest)
	except OSError:
		pass
	return [(_oneLine(heading), body) for heading, body in sections]


def fileName(name):
	"""A file name for the help of something, from its name."""
	return re.sub(r"[^A-Za-z0-9._-]+", "-", str(name or "")).strip("-.")[:60] or "help"


def listText(folder):
	"""Which help is kept as Markdown in a folder, in a sentence for the user."""
	found = []
	for base, _folders, files in os.walk(folder):
		found += [os.path.join(base, name) for name in files if name.endswith(".md")]
	if not found:
		return (
			"NVDA's own help has not been turned into Markdown files yet. That is done the first time you ask "
			f"VisionClaw a question. The files will be in the folder {folder}.")
	addons = sum(1 for path in found if os.path.basename(os.path.dirname(path)) == "addons")
	own = len(found) - addons
	return (
		f"NVDA's own help is kept as {own} Markdown {'file' if own == 1 else 'files'}"
		+ (f", and the help of {addons} {'add-on' if addons == 1 else 'add-ons'} as one file each" if addons else "")
		+ f", in the folder {folder}. They are made from the help that came with NVDA and the add-ons, and made "
		"again when that changes.")
