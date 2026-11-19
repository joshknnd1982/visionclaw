# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Writes what is new into VisionClaw's help files, from the changelog in addon/manifest.ini.

Usage:
  python tools/write_help.py            writes the parts
  python tools/write_help.py --check    only says whether they are up to date; exit code 1 if not

The help page that NVDA opens (addon/doc/en/readme.html) and the README each have one part between the markers
NEWS_START and NEWS_END. It says which version the help is for and what is new in the newest NEWS_COUNT versions,
point by point, in the changelog's own words. The rest of each file is written by hand and must explain every
feature (tests/test_help.py checks that). build.py refuses to build while this part is out of date.
"""
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "addon", "manifest.ini")
HTML = os.path.join(ROOT, "addon", "doc", "en", "readme.html")
README = os.path.join(ROOT, "README.md")
# The newest version and the one before it: someone who skipped a version still hears what came with it.
NEWS_COUNT = 2
NEWS_START = "<!-- news: written by tools/write_help.py from manifest.ini; do not change it by hand -->"
NEWS_END = "<!-- /news -->"
_HEAD = re.compile(r"^(?:New in|What was new in|In)\s+(\d+(?:\.\d+)+)\b.*:\s*$")


def manifestText():
	with open(MANIFEST, encoding="utf-8") as f:
		return f.read()


def version(text=None):
	return re.search(r"^version\s*=\s*(\S+)", text or manifestText(), re.M).group(1)


def sections(text=None):
	"""The changelog as [(version, [line, ...])], newest first. A line that began with "* " is a point, kept as
	("point", words); any other line is kept as ("plain", words)."""
	text = text or manifestText()
	changelog = text.split('changelog = """', 1)[1].split('"""', 1)[0]
	found = []
	for line in changelog.splitlines():
		line = line.strip()
		head = _HEAD.match(line)
		if head:
			found.append((head.group(1), []))
		elif found and line:
			if line.startswith("* "):
				found[-1][1].append(("point", line[2:].strip()))
			else:
				found[-1][1].append(("plain", line))
	return found


def _heading(index, number):
	return f"What is new in {number}" if index == 0 else f"What was new in {number}"


def htmlNews(text=None):
	text = text or manifestText()
	parts = [NEWS_START, f"<p>This help is for VisionClaw {html.escape(version(text))}.</p>"]
	for index, (number, lines) in enumerate(sections(text)[:NEWS_COUNT]):
		parts.append(f"<h2>{_heading(index, number)}</h2>")
		points = [words for kind, words in lines if kind == "point"]
		plain = [words for kind, words in lines if kind == "plain"]
		if points:
			parts.append("<ul>")
			parts.extend(f"<li>{html.escape(words, quote=False)}</li>" for words in points)
			parts.append("</ul>")
		parts.extend(f"<p>{html.escape(words, quote=False)}</p>" for words in plain)
	parts.append("<p>How to use each of these is explained in its own part of this page, further down.</p>")
	parts.append(NEWS_END)
	return "\n".join(parts)


def markdownNews(text=None):
	text = text or manifestText()
	parts = [NEWS_START, f"This README is for VisionClaw {version(text)}.", ""]
	for index, (number, lines) in enumerate(sections(text)[:NEWS_COUNT]):
		parts.append(f"## {_heading(index, number)}")
		parts.append("")
		parts.extend(f"- {words}" if kind == "point" else words for kind, words in lines)
		parts.append("")
	parts.append("How to use each of these is explained in its own part of this README, further down.")
	parts.append(NEWS_END)
	return "\n".join(parts)


def replaced(fileText, block):
	"""fileText with its part between the markers replaced by block; None when the markers are missing."""
	start = fileText.find(NEWS_START)
	end = fileText.find(NEWS_END)
	if start < 0 or end < start:
		return None
	return fileText[:start] + block + fileText[end + len(NEWS_END):]


def _read(path):
	with open(path, encoding="utf-8") as f:
		return f.read()


def wanted():
	"""{path: (now, as it should be)} for both help files."""
	text = manifestText()
	result = {}
	for path, block in ((HTML, htmlNews(text)), (README, markdownNews(text))):
		now = _read(path)
		result[path] = (now, replaced(now, block))
	return result


def stale():
	"""The help files whose part on what is new is missing or out of date, as sentences."""
	problems = []
	for path, (now, should) in wanted().items():
		name = os.path.relpath(path, ROOT)
		if should is None:
			problems.append(f"{name} has no markers for what is new")
		elif now != should:
			problems.append(f"{name} does not say what is new in {version()}")
	return problems


def main():
	if "--check" in sys.argv:
		problems = stale()
		for problem in problems:
			print(problem)
		sys.exit(1 if problems else 0)
	for path, (now, should) in wanted().items():
		if should is None:
			sys.exit(f"{os.path.relpath(path, ROOT)} has no markers for what is new: put {NEWS_START} and {NEWS_END} in it.")
		if should != now:
			with open(path, "w", encoding="utf-8", newline="\n") as f:
				f.write(should)
			print(f"Wrote what is new in {version()} into {os.path.relpath(path, ROOT)}")
		else:
			print(f"{os.path.relpath(path, ROOT)} is up to date")


if __name__ == "__main__":
	main()
