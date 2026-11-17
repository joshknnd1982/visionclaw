# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - plain helpers for using the web through the user's own browser: finding a web address in what
# the user said, building a search address, and choosing the passages of a long page that matter for a
# question, so that a small model is given little to read. No NVDA dependencies.

import re
import urllib.parse

from .memory import score

ENGINES = {
	"duckduckgo": "https://duckduckgo.com/?q={}",
	"google": "https://www.google.com/search?q={}",
	"bing": "https://www.bing.com/search?q={}",
}
DEFAULT_ENGINE = "duckduckgo"
_ADDRESS = re.compile(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d+)?(?:[/?#][^\s\"'<>]*)?", re.IGNORECASE)
# Only web pages are opened. These would run programs or scripts, or open files.
_NOT_WEB = re.compile(r"^\s*(javascript|data|vbscript|file|about|shell|mailto|ms-[a-z-]+|chrome|edge)\s*:", re.IGNORECASE)
_SEARCH_START = re.compile(
	r"^\s*(please\s+)?(can you\s+)?(search|look up|google|find|check)"
	r"(\s+(on\s+)?(the\s+)?(web|internet|net)|\s+online)?(\s+(for|about))?\s+", re.IGNORECASE)
_SEARCH_END = re.compile(r"\s+(on|in|using)\s+(the\s+)?(web|internet|net|google|bing|duckduckgo)\s*[.!?]*$|\s+online\s*[.!?]*$",
	re.IGNORECASE)


def addressIn(part):
	"""The web address in what the user said, or "" if there is none."""
	found = _ADDRESS.search(part or "")
	return found.group(0).rstrip(".,;:!?)") if found else ""


def normalizeAddress(address):
	"""A complete web address that is safe to hand to the browser. Raises ValueError with a sentence a model
	can act on."""
	text = str(address or "").strip().strip("\"'<>")
	if _NOT_WEB.match(text) or ("://" in text and not text.lower().startswith(("http://", "https://"))):
		raise ValueError("Only web addresses that start with http or https can be opened.")
	if not text or " " in text or "." not in text:
		raise ValueError(f"\"{address}\" is not a web address. Give one like example.com, or search the web instead.")
	if not text.lower().startswith(("http://", "https://")):
		text = "https://" + text
	return text


def searchWords(part):
	"""What to search for, from what the user said: "search the web for cheap flights online" is "cheap flights"."""
	words = _SEARCH_END.sub("", _SEARCH_START.sub("", part or "", count=1), count=1)
	return " ".join(words.split()).strip(" .!?\"'")


def searchUrl(engine, words):
	template = ENGINES.get(engine, ENGINES[DEFAULT_ENGINE])
	return template.format(urllib.parse.quote_plus(words))


def passages(text, about, chars=1400, blockChars=350):
	"""The parts of a page's text that matter for a question, in page order, within a length a small model can
	read. A short page is given whole. A long one gives its beginning and the blocks whose words match."""
	lines = [" ".join(line.split()) for line in str(text or "").splitlines()]
	lines = [line for line in lines if line]
	whole = "\n".join(lines)
	if len(whole) <= chars:
		return whole
	blocks, current = [], ""
	for line in lines:
		while len(line) > blockChars:  # one very long paragraph is cut into pieces
			if current:
				blocks.append(current)
				current = ""
			blocks.append(line[:blockChars])
			line = line[blockChars:]
		if current and len(current) + len(line) + 1 > blockChars:
			blocks.append(current)
			current = line
		else:
			current = f"{current}\n{line}" if current else line
	if current:
		blocks.append(current)
	scored = sorted(((score(about, block), i) for i, block in enumerate(blocks)), reverse=True)
	chosen = {0}
	used = len(blocks[0])
	for value, i in scored:
		if value <= 0 or i in chosen:
			continue
		if used + len(blocks[i]) > chars:
			continue
		chosen.add(i)
		used += len(blocks[i])
	if len(chosen) == 1:
		return whole[:chars].rstrip() + " ..."  # nothing matched: the beginning of the page
	out, last = [], None
	for i in sorted(chosen):
		if last is not None and i != last + 1:
			out.append("...")
		out.append(blocks[i])
		last = i
	return "\n".join(out)
