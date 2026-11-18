# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - learning about the program or game the user is in, from the internet, and keeping what was
# learned as short notes in Markdown on this computer. The owner asked for this on 2026-11-17. It goes online
# only when the user asks for it and has said yes to a question that says what is sent: the program's name,
# to Wikipedia; a request to Wikidata for the address of the program's own website and manual; and requests
# to that website for a few of its help pages. No search engine is asked: their pages are made for people
# and turn programs away, and that is not to be worked around. What comes back is text to read, never run.
# A model says what the program is called and what kind of thing it is, and writes the notes, one section
# of a page at a time; plain code keeps only notes whose keys and words are in the page. A page the user has
# open in their own browser can be added to the notes too. The notes are files the user can read, change and
# delete. No NVDA dependencies.

import datetime
import html
import json
import os
import re
import time
import urllib.parse

from . import lookup
from . import task as taskModule
from .guides import toMarkdown
from .knowledge import sections
from .llm import LLMError, clip
from .memory import words

# Wikipedia says what a program is, and Wikidata gives the address of its own website and of its manual.
# These two are asked through the doors they keep open for programs, and nothing else is.
WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php?action=query&list=search&srlimit=5&format=json&srsearch={}"
WIKI_ARTICLE_URL = (
	"https://en.wikipedia.org/w/api.php?action=query&prop=pageprops%7Cextracts&ppprop=wikibase_item&explaintext=1"
	"&redirects=1&format=json&titles={}")
WIKI_PAGE_URL = "https://en.wikipedia.org/wiki/{}"
WIKI_HOSTS = ("en.wikipedia.org",)
WIKIDATA_URL = "https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity={}&property={}"
WIKIDATA_HOSTS = ("www.wikidata.org",)
# What Wikidata calls the official website and the user manual of a thing.
WEBSITE, MANUAL = "P856", "P2078"
# How many pages of the program's own website are read, and how long a page may be.
MAX_PAGES = 6
LINKS_EACH = 4
PAGE_BYTES = 2000000
# How much of a page is kept: its most useful sections, each cut to a length.
SECTIONS_PER_PAGE = 6
MAX_SECTIONS = 20
SECTION_CHARS = 1500
INTRO_CHARS = 1200
# How long to wait when a server says there were too many requests, before asking it once more.
WAIT_SECONDS = 4.0
GAME, PROGRAM, UTILITY = "game", "program", "utility"
KINDS = (GAME, PROGRAM, UTILITY)
# Pages that cannot be read as text, need an account, or turn programs like this one away.
_SKIP_HOSTS = (
	"youtube.com", "youtu.be", "facebook.com", "instagram.com", "tiktok.com", "twitter.com", "x.com", "pinterest.com",
	"reddit.com", "linkedin.com", "quora.com", "duckduckgo.com", "twitch.tv", "discord.com", "discord.gg",
)
_SKIP_ENDINGS = (".pdf", ".zip", ".exe", ".msi", ".rar", ".7z", ".mp4", ".mp3", ".png", ".jpg", ".jpeg", ".gif", ".docx")
# What a program's product name says when it says nothing: the name of what runs it.
_NO_NAME = re.compile(
	r"microsoft.{0,3}windows.{0,3}operating system|openjdk|java\(tm\)|java platform|^python|^electron$"
	r"|application frame host|^unknown$", re.IGNORECASE)
_KNOWN = {"explorer": "Windows File Explorer", "applicationframehost": ""}
_TITLE_PARTS = re.compile(r"\s+[-–—|]\s+|:\s+")
# A key or a combination of keys, as pages write them.
_COMBO = re.compile(
	r"\b(?:ctrl|control|alt|shift|cmd|command|win|windows|fn|option|nvda|insert)\s*\+\s*(?:[a-z0-9]+|\S)(?:\s*\+\s*(?:[a-z0-9]+|\S))*"
	r"|\bf(?:[1-9]|1[0-2])\b", re.IGNORECASE)
_KEY_WORD = re.compile(
	r"\b(?:arrow keys?|space ?bar|enter|escape|esc|tab|backspace|page (?:up|down)|press(?:ing|es)?|shortcuts?|hot ?keys?)\b",
	re.IGNORECASE)
# A link on a program's website that leads to something worth reading, and one that does not.
_USEFUL_LINK = re.compile(
	r"shortcut|hot ?key|keyboard|key ?bind|getting[- ]started|quick[- ]?start|user[- ]?(guide|manual|interface)|manual"
	r"|\bguide\b|tutorial|basics|how[- ]to|accessib|screen[- ]reader|controls|gameplay|\bhelp\b|\bdocs?\b"
	r"|documentation|\bfaq\b|editing|navigat|commands|features|\bwiki\b|support", re.IGNORECASE)
_USELESS_LINK = re.compile(
	r"download|donat|press|blog|news|forum|store|shop|buy|pricing|login|sign|account|career|job|privacy|terms|licen[sc]e"
	r"|contact|about|team|release|changelog|history|contribut|translat|sponsor|merch", re.IGNORECASE)
# What the opening of a Wikipedia article says when the article is about something run on a computer.
_SOFTWARE = re.compile(
	r"software|program|application|\bapp\b|video game|\bgame\b|editor|browser|player|utility|\btool\b|client|operating"
	r"|emulator|plug-?in|library|simulator|suite|messenger|platform|launcher|screen reader", re.IGNORECASE)
_USEFUL_HEADING = re.compile(
	r"shortcut|hot ?key|keyboard|key ?bind|\bkeys?\b|controls?\b|commands?|navigat|getting started|how to|basics|tutorial"
	r"|guide|tips|accessib|screen reader|blind|gameplay|playing|overview|introduction|features|menu|beginner",
	re.IGNORECASE)
_JUNK_HEADING = re.compile(
	r"cookie|privacy|newsletter|subscribe|comment|related|share|about the author|advert|sponsor|sign in|log in|footer"
	r"|leave a reply|you may also|popular|trending|recent posts|categories|\btags\b|references|external links|see also"
	r"|contents|navigation menu|follow us|download our|more from", re.IGNORECASE)
_DEICTIC = re.compile(
	r"^(this|that|it|its|the current|my current|current|here|i|i'm|what|where|whatever|in front|the (program|app|game|one))\b",
	re.IGNORECASE)
_SAID = re.compile(r"\b(?:called|named)\s+[\"“']?(.+?)[\"”']?\s*[.!?]*$", re.IGNORECASE)
_ABOUT = re.compile(
	r"\b(?:learn|study|research|read up|notes?)\b.*?\b(?:about|on|for)\s+(?:how to use\s+)?(?:the\s+)?"
	r"(?:(?:program|app|application|game|utility|tool)\s+)?[\"“']?(.+?)[\"”']?\s*[.!?]*$", re.IGNORECASE)
_ONLINE = re.compile(
	r"\s*,?\s*\b(from|on|using|with|by searching)\s+(the\s+)?(internet|web|net)\b.*$|\s+online\b.*$", re.IGNORECASE)
_IN_FRONT = re.compile(r"\b(this|current|here|in front|i am in|i'm in|it is called|it's called)\b", re.IGNORECASE)

_IDENTIFY_SYSTEM = (
	"You help a blind person learn the program they are using. You are told what Windows and the screen reader "
	"report about the program in front. Choose the name by which this program is known, the one to search the "
	"internet for, and say what kind of thing it is."
)
_NOTES_SYSTEM = (
	"You make short notes for a blind person who is learning to use a program with the keyboard and a screen "
	"reader. You are given one section of a web page about the program. Write what is useful in it as short "
	"notes, one fact to a note: what a key does, how something is done, what something is.\n"
	"Rules: Use only what the text says. Copy every key exactly as the text writes it. Leave out advertising, "
	"opinions, things done only with a mouse, and anything that is not about using the program. If the text has "
	"nothing useful, give no notes."
)
_NOTES_SCHEMA = {
	"type": "object",
	"properties": {"notes": {"type": "array", "maxItems": 10, "items": {"type": "string", "maxLength": 220}}},
	"required": ["notes"],
}


# --- Which program, and what to search for ---

def slug(name):
	"""A file name for a program's notes, from its name."""
	return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")[:60] or "program"


def saidName(part):
	"""The program a request names itself, as in "learn about Audacity" or "it is called Space Trader", or ""
	when the request means the program in front without naming it."""
	text = _ONLINE.sub("", " ".join(str(part or "").split()))
	for pattern in (_SAID, _ABOUT):
		hit = pattern.search(text)
		if hit:
			name = hit.group(1).strip(" .,!?\"'")
			if name and not _DEICTIC.match(name) and len(name) <= 60:
				return name
	return ""


def meansInFront(part, said):
	"""Whether a request is about the program the user is in, also when it says what it is called."""
	return not said or bool(_IN_FRONT.search(part or ""))


def candidates(app, product, title):
	"""The names a program could be known by, the likeliest first: what its maker called it, the parts of its
	window's title, and the name of its file. A product name that only names what runs the program, such as
	Java, is left out."""
	found = []

	def add(name):
		name = " ".join(str(name or "").split()).strip(" -|:")
		if name and len(name) <= 60 and name.lower() not in (known.lower() for known in found):
			found.append(name)

	if product and not _NO_NAME.search(product):
		add(product)
	parts = [part for part in _TITLE_PARTS.split(title or "") if part.strip()]
	if parts:
		add(parts[-1])
		add(parts[0])
	add(_KNOWN.get(str(app or "").lower(), app))
	return found[:4] or ["this program"]


def identify(llm, role, app, product, title, focus="", names=None):
	"""(name, kind) of the program in front. The model chooses among the names plain code found and among the
	three kinds; where it cannot, the likeliest name and "program" are taken. names: the name the user said,
	when they said one; then the model only says what kind of thing it is."""
	names = list(names or candidates(app, product, title))
	if llm is None:
		return names[0], PROGRAM
	schema = {
		"type": "object",
		"properties": {"name": {"type": "string", "enum": names}, "kind": {"type": "string", "enum": list(KINDS)}},
		"required": ["name", "kind"],
	}
	user = (
		(f"Program file: {app}\nProduct name: {product or 'not reported'}\nWindow title: {title or 'none'}\n" if app else "")
		+ (f"The focus is on: {clip(focus, 160)}\n" if focus else "")
		+ f"The possible names: {'; '.join(names)}\nWhich name is the program known by, and is it a game, a program or a utility?")
	try:
		found = llm.json(role, _IDENTIFY_SYSTEM, user, schema, maxTokens=40)
	except LLMError:
		return names[0], PROGRAM
	name = found.get("name") if found.get("name") in names else names[0]
	return name, found.get("kind") if found.get("kind") in KINDS else PROGRAM


def searchWords(name, kind=PROGRAM):
	"""What Wikipedia is searched for: the name, and a word that tells a program from other things of that name."""
	return f"{name} video game" if kind == GAME else f"{name} software"


# --- What comes back ---

def usable(url):
	"""Whether an address is a web page that can be read as text: https, and not a video, a file or a place
	that wants an account."""
	parts = urllib.parse.urlsplit(url or "")
	host = (parts.hostname or "").lower()
	if parts.scheme != "https" or not host or "." not in host:
		return False
	if any(host == skipped or host.endswith("." + skipped) for skipped in _SKIP_HOSTS):
		return False
	return not parts.path.lower().endswith(_SKIP_ENDINGS)


def hostOf(url):
	host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
	return host[4:] if host.startswith("www.") else host


def links(page, base, limit=LINKS_EACH):
	"""The links of a page that lead to help worth reading, on the same website, the likeliest first:
	(what the link says, its address)."""
	found, seen = [], {base.split("#")[0].rstrip("/")}
	for hit in re.finditer(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", page or "", re.DOTALL | re.IGNORECASE):
		said = " ".join(html.unescape(re.sub(r"<[^>]+>", "", hit.group(2))).split())
		url = urllib.parse.urljoin(base, html.unescape(hit.group(1))).split("#")[0]
		if not usable(url) or hostOf(url) != hostOf(base) or url.rstrip("/") in seen:
			continue
		what = f"{said} {urllib.parse.urlsplit(url).path}"
		if not _USEFUL_LINK.search(what) or _USELESS_LINK.search(what):
			continue
		seen.add(url.rstrip("/"))
		# A link that names keys or getting started is worth more than one that only says "docs".
		worth = len(re.findall(r"shortcut|hot ?key|keyboard|getting[- ]started|quick[- ]?start|accessib|controls|user[- ]?interface",
			what, re.IGNORECASE))
		found.append((-worth, len(found), clip(said, 80), url))
	found.sort()
	return [(said, url) for _worth, _at, said, url in found[:limit]]


def nameWords(name):
	"""The words of a program's name that a page about it must have."""
	return [word for word in re.findall(r"[a-z0-9+#]+", str(name or "").lower())
		if len(word) >= 2 and word not in ("the", "for", "and", "of", "game", "app", "windows", "microsoft")]


def isAbout(text, name):
	"""Whether a text is about a program: it has every word of the program's name, whole. Notepad++ is not
	Notepad, and C# is not C."""
	low = str(text or "").lower()
	wanted = nameWords(name)
	return bool(wanted) and all(re.search(rf"(?<![a-z0-9+#]){re.escape(word)}(?![a-z0-9+#])", low) for word in wanted)


def wikiTitles(found, name):
	"""The Wikipedia articles that could be about the program, from the answer to a search: those whose title
	has the program's name. Better no article than one about something else."""
	try:
		hits = found["query"]["search"]
	except (KeyError, TypeError):
		return []
	titles = [str(hit.get("title") or "") for hit in hits
		if isAbout(str(hit.get("title") or ""), name) and "disambiguation" not in str(hit.get("title") or "").lower()]
	# A title that is the name itself, or the name with what it is in brackets, comes before a longer one.
	plain = " ".join(str(name).lower().split())
	titles.sort(key=lambda title: re.sub(r"\s*\(.*?\)\s*$", "", title).lower() != plain)
	return titles[:3]


def wikiArticle(found):
	"""(the article's text as Markdown, its Wikidata id) from the answer to a request for an article."""
	try:
		pages = found["query"]["pages"]
	except (KeyError, TypeError):
		return "", ""
	for page in pages.values():
		raw = str(page.get("extract") or "")
		if raw.strip():
			# Wikipedia's plain text marks a heading as "== Features ==".
			markdown = re.sub(r"^(={2,4})\s*(.+?)\s*=+\s*$", lambda hit: "#" * len(hit.group(1)) + " " + hit.group(2), raw, flags=re.MULTILINE)
			return markdown, str((page.get("pageprops") or {}).get("wikibase_item") or "")
	return "", ""


def addresses(found):
	"""The web addresses in Wikidata's answer about one property of a thing."""
	kept = []
	try:
		for claims in found["claims"].values():
			for claim in claims:
				value = claim["mainsnak"].get("datavalue", {}).get("value")
				if isinstance(value, str) and usable(value) and value not in kept:
					kept.append(value)
	except (KeyError, TypeError, AttributeError):
		pass
	return kept


def pageTitle(page):
	hit = re.search(r"<title[^>]*>(.*?)</title>", page or "", re.DOTALL | re.IGNORECASE)
	return clip(" ".join(html.unescape(re.sub(r"<[^>]+>", "", hit.group(1))).split()), 120) if hit else ""


def _cut(body, chars=SECTION_CHARS):
	"""A section's text within a length, ending at the end of a line."""
	kept, size = [], 0
	for line in str(body or "").splitlines():
		line = " ".join(line.split())
		if not line:
			continue
		if size + len(line) > chars and kept:
			break
		kept.append(line[:chars])
		size += len(line) + 1
	return "\n".join(kept)


def pageSections(markdown, title=""):
	"""The sections of a page that help someone learn the program: those that name keys, and those whose
	heading says they are about keys, getting started or accessibility. Menus, cookie notices and the like are
	left out. Returns (heading, text) in the page's order, the most useful few."""
	found = sections(markdown)
	if not found:
		found = [(title or "The page", markdown, "")]
	scored = []
	for at, (heading, body, _source) in enumerate(found):
		if _JUNK_HEADING.search(heading) or len(body) < 40:
			continue
		# A key that is written out tells more than a word like "press".
		keys = 2 * len(_COMBO.findall(body)) + len(_KEY_WORD.findall(body))
		score = min(12, keys) + (4 if _USEFUL_HEADING.search(heading) else 0)
		if score >= 3:
			scored.append((score, at, heading, _cut(body)))
	scored.sort(key=lambda entry: (-entry[0], entry[1]))
	kept = sorted(scored[:SECTIONS_PER_PAGE], key=lambda entry: entry[1])
	return [(clip(heading, 100), body) for _score, _at, heading, body in kept]


# --- Notes a model writes, and what plain code lets through ---

def _keysIn(text):
	return {re.sub(r"\s+", "", hit.group(0).lower()).replace("ctrl+", "control+") for hit in _COMBO.finditer(text or "")}


def checked(notes, body):
	"""The notes of a model that stand in the text they were made from: every key a note names is in the text,
	and most of its words are. A note that fails is dropped; a model that adds a key has made it up."""
	inText, textWords = _keysIn(body), words(body)
	kept = []
	for note in notes or ():
		note = " ".join(str(note or "").split()).strip("-* ")
		mine = words(note)
		if len(note) < 8 or not mine or note in kept:
			continue
		if not _keysIn(note) <= inText:
			continue
		if len(mine & textWords) / len(mine) < 0.6:
			continue
		kept.append(note)
	return kept


def writeNotes(llm, role, name, heading, body):
	"""Short notes on one section of a page, written by a model and checked by plain code. None when the model
	gives none that stand in the text; then the text itself is kept."""
	user = f"Program: {name}\nSection: {heading}\nText:\n{clip(body, SECTION_CHARS)}\nWrite the notes."
	try:
		found = llm.json(role, _NOTES_SYSTEM, user, _NOTES_SCHEMA, maxTokens=520)
	except LLMError:
		return None
	return checked(found.get("notes"), body) or None


# --- Going online ---

def study(name, kind, fetch, cancel=None, tell=None, write=None, wait=WAIT_SECONDS):
	"""Find out about a program and read what is found. fetch(url, hosts) returns the text at an address, from
	those servers only when hosts is given, or raises. tell(sentence) is told what is being done.
	write(heading, text) may turn a section into a list of short notes, or return None to keep the text.
	Returns a dictionary: name, kind, intro, introUrl, pages [{url, title, sections [(heading, text, notes)]}],
	asked [every address a request went to], failed [(what, why)]."""
	result = {"name": name, "kind": kind, "intro": "", "introUrl": "", "pages": [], "asked": [], "failed": []}
	tell = tell or (lambda sentence: None)

	def get(url, hosts=None, what=""):
		if cancel is not None and cancel.is_set():
			raise taskModule.Cancelled()
		result["asked"].append(url)
		for again in (True, False):
			try:
				return fetch(url, hosts)
			except Exception as e:
				if type(e).__name__ == "Cancelled":
					raise
				# "Too many requests": the server asks for a pause. It gets one, once, and then its answer stands.
				if again and "429" in str(e):
					if cancel is not None:
						cancel.wait(wait)
						if cancel.is_set():
							raise taskModule.Cancelled()
					else:
						time.sleep(wait)
					continue
				result["failed"].append((what or hostOf(url), f"{type(e).__name__}: {e}"[:120]))
				return None

	def keep(url, title, markdown):
		"""Keep the useful sections of a page. Returns how many were kept."""
		room = MAX_SECTIONS - sum(len(page["sections"]) for page in result["pages"])
		kept = []
		for heading, body in pageSections(markdown, title)[:max(0, room)]:
			if any(body == other for page in result["pages"] for _h, other, _n in page["sections"]):
				continue
			if cancel is not None and cancel.is_set():
				raise taskModule.Cancelled()
			kept.append((heading, body, write(heading, body) if write is not None else None))
		if kept:
			result["pages"].append({"url": url, "title": title, "sections": kept})
		return len(kept)

	# What it is, from Wikipedia, when Wikipedia has an article with its name that is about a program.
	tell(f"Asking Wikipedia about {name}.")
	item = ""
	answer = get(WIKI_SEARCH_URL.format(urllib.parse.quote_plus(searchWords(name, kind))), WIKI_HOSTS, "Wikipedia")
	for title in wikiTitles(_json(answer), name) if answer else ():
		article = get(WIKI_ARTICLE_URL.format(urllib.parse.quote(title)), WIKI_HOSTS, "Wikipedia")
		markdown, item = wikiArticle(_json(article)) if article else ("", "")
		opening = " ".join(markdown.split("\n#", 1)[0].split())
		if not opening or not _SOFTWARE.search(opening[:700]):
			item = ""
			continue
		address = WIKI_PAGE_URL.format(urllib.parse.quote(title.replace(" ", "_")))
		result["intro"], result["introUrl"] = lookup.shorten(opening, INTRO_CHARS), address
		keep(address, f"Wikipedia: {title}", markdown)
		break
	if not result["intro"]:
		result["failed"].append(("Wikipedia", f"it has no article that is clearly about the {kind} {name}"))
	# Its own website and manual, whose addresses Wikidata keeps, and the help pages they link to.
	starts = []
	if item:
		tell(f"Asking Wikidata for the website and the manual of {name}.")
		for what in (MANUAL, WEBSITE):
			claims = get(WIKIDATA_URL.format(item, what), WIKIDATA_HOSTS, "Wikidata")
			starts += [url for url in addresses(_json(claims))[:1] if url not in starts] if claims else []
	read, queue = 0, [(hostOf(url), url, True) for url in starts]
	seen = set()
	while queue and read < MAX_PAGES and sum(len(page["sections"]) for page in result["pages"]) < MAX_SECTIONS:
		said, url, isStart = queue.pop(0)
		if url.rstrip("/") in seen:
			continue
		seen.add(url.rstrip("/"))
		read += 1
		tell(f"Reading {said or 'a page'} on {hostOf(url)}.")
		page = get(url, None, hostOf(url) if isStart else f"{said} on {hostOf(url)}")
		if not page:
			continue
		if "<" not in page[:3000]:
			result["failed"].append((hostOf(url), "it is not a web page of text"))
			continue
		kept = keep(url, pageTitle(page) or said, toMarkdown(page))
		if isStart:
			# The pages of its own website that say how it is used come next, before the next website.
			queue[:0] = [(text, link, False) for text, link in links(page, url)]
		elif not kept:
			result["failed"].append((f"{said} on {hostOf(url)}", "nothing in it is about keys or how to use it"))
	return result


def fromPage(name, kind, url, title, markdown, write=None):
	"""What a page the user has open says, as a result like study's, to be added to a program's notes."""
	result = {"name": name, "kind": kind, "intro": "", "introUrl": "", "pages": [], "asked": [], "failed": []}
	kept = [(heading, body, write(heading, body) if write is not None else None)
		for heading, body in pageSections(markdown, title)]
	if kept:
		result["pages"].append({"url": url, "title": title, "sections": kept})
	return result


def textToMarkdown(body, headings):
	"""A page's plain text with its headings marked, so that it can be taken apart at them."""
	wanted = {" ".join(str(label).split()) for label in headings if str(label).strip()}
	return "\n".join(f"## {line}" if " ".join(line.split()) in wanted else line for line in str(body or "").splitlines())


def _json(text):
	try:
		return json.loads(text)
	except (TypeError, ValueError):
		return {}


def learned(result):
	"""Whether anything was found that is worth keeping."""
	return bool(result["intro"] or result["pages"])


# --- The notes, as a file ---

def notesText(result, app="", today=None):
	"""What was learned, as Markdown: what the program is, then one section for each useful part of a page,
	as short notes where a model wrote them and as the page's own words where not, each with where it is from."""
	name = result["name"]
	day = today or datetime.date.today().isoformat()
	lines = [
		f"# Notes on {name}" + (f" (program {app})" if app else ""),
		"",
		f"Made by VisionClaw on {day} from pages on the internet, for the {result['kind']} {name}. They may be "
		"wrong or out of date. This file is yours: change it, or delete it, or ask VisionClaw to delete the notes on "
		"this program.",
	]
	if result["intro"]:
		lines += ["", f"## What {name} is", "", result["intro"], "", f"Source: {result['introUrl']}"]
	for page in result["pages"]:
		for heading, body, notes in page["sections"]:
			lines += ["", f"## {heading}", ""]
			lines += [f"- {note}" for note in notes] if notes else [body]
			lines += ["", f"Source: {page['url']}"]
	return "\n".join(lines) + "\n"


def merged(old, result, app="", today=None):
	"""A program's notes with what a page gave added at the end. Notes that are there are kept as they are,
	also what the user wrote into them."""
	if not old.strip():
		return notesText(result, app, today)
	lines = [old.rstrip("\n")]
	for page in result["pages"]:
		for heading, body, notes in page["sections"]:
			lines += ["", f"## {heading}", ""]
			lines += [f"- {note}" for note in notes] if notes else [body]
			lines += ["", f"Source: {page['url']}"]
	return "\n".join(lines) + "\n"


def summary(result, path, replaced=False):
	"""What was done, in sentences for the user."""
	name = result["name"]
	if not learned(result):
		why = "; ".join(f"{what}: {reason}" for what, reason in result["failed"][:4])
		return (
			f"VisionClaw looked for {name} on the internet and found nothing it could use, so no notes were kept."
			+ (f" What went wrong: {why}." if why else "")
			+ " You can still open a page about it in your browser and ask: add this page to the notes on "
			f"{name}.")
	count = sum(len(page["sections"]) for page in result["pages"]) + (1 if result["intro"] else 0)
	if not result["pages"]:
		places = ["en.wikipedia.org"]
	places = list(dict.fromkeys(hostOf(page["url"]) for page in result["pages"]))
	written = sum(1 for page in result["pages"] for _h, _b, notes in page["sections"] if notes)
	text = (
		f"VisionClaw learned about the {result['kind']} {name}. It read {len(places)} "
		f"{'website' if len(places) == 1 else 'websites'} ({', '.join(places)}) and kept {count} "
		f"{'note' if count == 1 else 'notes'}"
		+ (", replacing the notes it had" if replaced else "") + f", in the file {path}. ")
	if written:
		text += f"{written} of them were put into short points by the model and checked against the page. "
	skipped = list(dict.fromkeys(what for what, _why in result["failed"]))
	if skipped:
		text += f"Not used: {', '.join(skipped[:4])}. "
	return text + (
		"The notes are from the internet and may be wrong. Now ask your questions about it, such as how to do "
		"something or which key does something. To remove the notes, ask: delete the notes on this program.")


class Notes:
	"""The notes on this computer, one Markdown file for each program."""

	def __init__(self, folder):
		self.folder = folder

	def path(self, ident):
		return os.path.join(self.folder, slug(ident) + ".md")

	def save(self, ident, text):
		os.makedirs(self.folder, exist_ok=True)
		tmp = self.path(ident) + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			f.write(text)
		os.replace(tmp, self.path(ident))
		return self.path(ident)

	def read(self, ident):
		try:
			with open(self.path(ident), encoding="utf-8") as f:
				return f.read()
		except OSError:
			return ""

	def listed(self):
		"""The notes there are: (file name without its ending, the program's name, the day, how many notes)."""
		try:
			names = sorted(name for name in os.listdir(self.folder) if name.endswith(".md"))
		except OSError:
			return []
		found = []
		for name in names:
			text = self.read(name[:-3])
			head = re.match(r"# Notes on (.+?)(?: \(program [^)]*\))?\s*$", text.splitlines()[0] if text else "")
			day = re.search(r"\bon (\d{4}-\d{2}-\d{2})\b", text[:600])
			found.append((name[:-3], head.group(1) if head else name[:-3], day.group(1) if day else "", len(parse(text))))
		return found

	def find(self, said):
		"""The notes a request names, by the program's name or its file's, as their file names."""
		low = f" {' '.join(re.findall(r'[a-z0-9+#]+', str(said or '').lower()))} "
		return [ident for ident, name, _day, _count in self.listed()
			if f" {' '.join(re.findall(r'[a-z0-9+#]+', name.lower()))} " in low or f" {ident} " in low]

	def forProgram(self, app, names=()):
		"""The notes for the program in front: those kept under its file's name, or under one of its names."""
		if self.read(app):
			return slug(app)
		wanted = {str(name).lower() for name in names if name}
		return next((ident for ident, name, _day, _count in self.listed() if name.lower() in wanted), "")

	def nameOf(self, ident):
		"""The name of the program a file of notes is about."""
		return next((name for file, name, _day, _count in self.listed() if file == slug(ident)), "")

	def remove(self, ident):
		try:
			os.remove(self.path(ident))
			return True
		except OSError:
			return False

	def listText(self):
		found = self.listed()
		if not found:
			return (
				"VisionClaw has no notes on any program yet. Ask it to learn about the program you are in, and it "
				"goes online for it after asking you.")
		return (
			f"VisionClaw has notes on {len(found)} {'program' if len(found) == 1 else 'programs'}: "
			+ "; ".join(f"{name}, {count} notes" + (f" from {day}" if day else "") for _ident, name, day, count in found)
			+ f". They are Markdown files in the folder {self.folder}.")


def parse(text):
	"""The notes of a file as (heading, text, the address it is from), without the file's own heading."""
	found = []
	for heading, body, _source in sections(text or ""):
		if heading.startswith("Notes on "):
			continue
		source = re.search(r"^Source: (\S+)\s*$", body, re.MULTILINE)
		body = re.sub(r"^Source: \S+\s*$", "", body, flags=re.MULTILINE).strip()
		if body:
			found.append((heading, body, source.group(1) if source else ""))
	return found


def passages(text, name):
	"""A program's notes as passages for answering questions, each saying which website it is from. A row of a
	table and a point of a list become sentences, so that a key stays with what it does."""
	found = []
	for heading, body, source in parse(text):
		lines = []
		for line in body.splitlines():
			line = re.sub(r"\s*\|\s*", ", ", line).strip(" ,-*")
			if line:
				lines.append(line if line[-1] in ".!?;:" else line + ";")
		origin = f"the notes on {name}" + (f", from {hostOf(source)}" if source else "")
		whatItIs = heading.lower().startswith("what ") and heading.lower().endswith(" is")
		for at, piece in enumerate(lookup.chunks(" ".join(lines))):
			found.append(lookup.Passage(lookup.APP, heading, piece, origin, here=whatItIs and at == 0, lead=at == 0))
	return found
