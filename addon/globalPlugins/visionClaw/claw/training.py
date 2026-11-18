# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - free material that teaches NVDA, kept on this computer as Markdown and looked things up in.
# The owner asked on 2026-11-18 that VisionClaw "search and apply info from all nvda user guides, help
# documentation and free training material that it can find and download, converting it to markdown". What is
# free was looked for that day by fetching every address, and the owner said yes to three sources, by name:
#   the NVDA wiki on GitHub (written by NVDA's community; no licence is stated): coming to NVDA from JAWS and
#     from Window-Eyes, the ribbon of Office, which programs work with NVDA, more voices, NVDA's log;
#   the American Foundation for the Blind's "Learn NVDA", eight lessons from 2016, as their transcripts
#     (copyright AFB; its page says "we encourage you to share them");
#   Hadley's "NVDA Screen Reader Series", four workshops, as their transcripts (copyright Hadley).
# NVDA's own user guide is not here: it comes with NVDA, in the user's language, and is read from there.
#
# The rules are those of the developer guides (claw/guides.py). The material is downloaded only when the
# user asks for exactly this and has said yes to a question that names every site and how many requests are
# sent; the addresses and the servers are fixed here; nothing is sent but the requests, which carry nothing
# about the user; what comes back is text to read, never run. VisionClaw's own code asks no search engine: a
# source is added here, by hand, after the owner's yes, and never found by the add-on itself.
#
# Two of the three sources keep their copyright. So what is downloaded is kept for the user's own reading on
# this computer, each file says at its top where it is from and whose it is, nothing of it is passed on, and
# an answer made from it says where it is from. It was written by others than NV Access, and some of it for
# an older NVDA: it is asked after NVDA's own help and never instead of it, and each page only about what it
# is about (its gate), so that a lesson from 2016 does not answer what NVDA's user guide of today answers.
# No NVDA dependencies.

import datetime
import json
import os
import re

from . import guides, lookup

SOURCE = "training"
RECORD = "training.json"
MAX_BYTES = 1500000
# A page shorter than this is not the page: an error page, or a site that was rebuilt.
MIN_CHARS = 1500
OLD_DAYS = 365
# What the user must name for a page to be asked. A page that has no gate is asked about anything.
_JAWS = re.compile(r"\bjaws\b|\bjfw\b|\bfreedom scientific\b", re.IGNORECASE)
_WINDOW_EYES = re.compile(r"\bwindow[- ]?eyes\b", re.IGNORECASE)
_RIBBON = re.compile(r"\bribbons?\b", re.IGNORECASE)
_WORKS_WITH = re.compile(
	r"\b(supported|supports?|compatib\w+|works? (well )?with|work in|which (programs?|apps?|applications?|browsers?))\b",
	re.IGNORECASE)
_VOICES = re.compile(r"\b(voices?|synthesi[sz]ers?|eloquence|vocali[sz]er|e-?speak|sapi|one ?core|text to speech|tts)\b", re.IGNORECASE)
_LOG = re.compile(r"\b(logs?|log file|crash\w*|dumps?|froze|freez\w+|debug\w*)\b", re.IGNORECASE)
# Lessons for someone who is new to NVDA: asked when the user asks to learn or be taught, says they are new,
# or names the lessons. Any other question is answered by NVDA's own help, which is of today.
_LEARNING = re.compile(
	r"\b(learn\w*|lessons?|tutorials?|training|teach\w*|train me|coach\w*|beginners?|new to|never used|first time|"
	r"getting started|get started|start(ing)? out|basics?|introduction|afb|american foundation|hadley|workshops?|"
	r"step by step|walk me through|explain\w*)\b", re.IGNORECASE)

WIKI = "https://raw.githubusercontent.com/wiki/nvaccess/nvda/"
AFB = "https://afb.org/blindness-and-low-vision/using-technology/assistive-technology-videos/learn-nvda/"
HADLEY = "https://hadleyhelps.org/workshops/nvda-screen-reader-series/"
# Each source: what it is called where the user is told an answer is from it, whose it is, and its pages as
# (the name of the file it is kept in, what the page is called, its address, what must be named for it to be
# asked). stop: headings after which a page has only the site's own menus and offers.
SETS = (
	{"id": "nvda-wiki", "title": "the NVDA wiki", "by": "NVDA's community, on GitHub", "rights": "No licence is stated.",
		"html": False, "stop": (), "pages": (
			("switching-from-jaws", "Switching from JAWS to NVDA", WIKI + "SwitchingFromJawsToNVDA.md", _JAWS),
			("switching-from-window-eyes", "Switching from Window-Eyes to NVDA", WIKI + "Switching-from-Window-Eyes-to-NVDA.md", _WINDOW_EYES),
			("office-ribbon", "Using the ribbon of Office with NVDA", WIKI + "Using-the-Ribbon-with-NVDAListTagged(UserArticles).md", _RIBBON),
			("application-support", "Which programs work with NVDA", WIKI + "Application-Support.md", _WORKS_WITH),
			("extra-voices", "More voices for NVDA", WIKI + "ExtraVoices.md", _VOICES),
			("log-files", "NVDA's log files and crash dumps", WIKI + "LogFilesAndCrashDumps.md", _LOG),
		)},
	{"id": "afb-learn-nvda", "title": "AFB's Learn NVDA lessons, from 2016", "by": "the American Foundation for the Blind",
		"rights": "Copyright American Foundation for the Blind. Kept here for your own reading.",
		"html": True, "stop": ("Learn NVDA", "Take Action Today"), "pages": (
			("installing-nvda", "Installing NVDA", AFB + "installing-nvda", _LEARNING),
			("windows-basics-1", "Windows basics, part 1", AFB + "windows-basics", _LEARNING),
			("windows-basics-2", "Windows basics, part 2", AFB + "windows-basics-0", _LEARNING),
			("windows-basics-3", "Windows basics, part 3", AFB + "windows-basics-1", _LEARNING),
			("hotkeys-1", "Hotkeys and review, part 1", AFB + "hotkeys-and", _LEARNING),
			("hotkeys-2", "Hotkeys and review, part 2", AFB + "hotkeys-and-0", _LEARNING),
			("using-the-internet", "Using the internet", AFB + "using-internet", _LEARNING),
			("installing-firefox", "Installing Firefox", AFB + "installing-firefox", _LEARNING),
		)},
	{"id": "hadley-nvda", "title": "Hadley's NVDA workshops", "by": "Hadley",
		"rights": "Copyright Hadley. Kept here for your own reading.",
		"html": True, "stop": (
			"Handouts", "Websites", "NVDA Screen Reader Series", "Explore", "Members also liked",
			"Join the Hadley Community", "Need some help?"), "pages": (
			("getting-started", "Getting started", HADLEY + "getting-started", _LEARNING),
			("customizing-how-nvda-speaks", "Customizing how NVDA speaks", HADLEY + "customizing-how-nvda-speaks", _LEARNING),
			("useful-shortcuts", "Useful shortcuts", HADLEY + "useful-shortcuts", _LEARNING),
			("everyday-tasks", "Everyday tasks", HADLEY + "everyday-tasks", _LEARNING),
		)},
)
# The only servers a page may come from, also after a redirect.
HOSTS = ("raw.githubusercontent.com", "afb.org", "www.afb.org", "hadleyhelps.org", "www.hadleyhelps.org")
_SPEAKER = re.compile(r"^(\[[^\]]{1,40}\]|[A-Z][\w.' -]{1,30}:)\s+")
_MAIN = re.compile(r"<main\b.*?</main>", re.DOTALL | re.IGNORECASE)
_NOT_TEXT = re.compile(r"<(header|footer|aside|form|iframe|button|select|figure)\b.*?</\1>", re.DOTALL | re.IGNORECASE)


def comesFrom(texts):
	"""The other screen readers that what the user asked VisionClaw to remember about themselves names, as
	words: with them, the page for people who come from that screen reader is asked without its being named
	in every question."""
	said = " ".join(str(text) for text in texts or ())
	return [name for name, gate in (("JAWS", _JAWS), ("Window-Eyes", _WINDOW_EYES)) if gate.search(said)]


def pageCount():
	return sum(len(source["pages"]) for source in SETS)


def question():
	"""What the user is asked before anything is downloaded: every site by name, and how many requests."""
	parts = [f"{len(source['pages'])} pages of {source['title']} by {source['by']}" for source in SETS]
	return (
		"Download free material that teaches NVDA? It is " + "; ".join(parts) + f". {pageCount()} requests are sent, to "
		"raw.githubusercontent.com, afb.org and hadleyhelps.org, with nothing about you or this computer. The "
		"pages are kept on this computer as text, for your own reading and for VisionClaw to look things up in.")


def lessonText(page, stop=()):
	"""The text of a lesson's web page as paragraphs: what is in the main part of the page, without the
	site's menus, forms and players, up to the first heading after which only the site's own offers follow
	(stop). A transcript's speaker marks are taken off. A piece that only begins what a later piece says in
	full is left out."""
	main = _MAIN.search(page or "")
	body = main.group(0) if main else (page or "")
	previous = None
	while previous != body:
		previous, body = body, _NOT_TEXT.sub(" ", body)
	pieces = []
	for heading, text in guides.cut(guides.toMarkdown(body)):
		if heading.strip() in stop:
			break
		paragraphs = []
		for paragraph in re.split(r"\n\s*\n", text):
			paragraph = _SPEAKER.sub("", guides.prose(paragraph)).strip()
			if paragraph:
				paragraphs.append(paragraph)
		if paragraphs:
			pieces.append(paragraphs)
	kept = []
	for at, paragraphs in enumerate(pieces):
		start = " ".join(paragraphs)[:120]
		if any(" ".join(later).startswith(start) and len(" ".join(later)) > len(" ".join(paragraphs)) for later in pieces[at + 1:]):
			continue
		kept += paragraphs
	return "\n\n".join(kept)


def _head(source, title, url, today):
	return (
		f"# {title}\n\nFrom {source['title']}, by {source['by']}. {source['rights']} Downloaded by VisionClaw on {today} "
		f"from {url}. It was not written by NV Access and may describe an older NVDA.\n\n")


def _folder(folder, source):
	return os.path.join(folder, source["id"])


def _path(folder, source, name):
	return os.path.join(_folder(folder, source), name + ".md")


def update(folder, fetch, cancel=None, today=None):
	"""Download every page and keep it as Markdown. fetch(url) returns the text at an address, or raises. A
	page that cannot be fetched or does not look like the page leaves the copy that is there untouched.
	Returns {"got": [(what the source is called, how many of its pages)], "failed": [(page, why)]}."""
	day = today or datetime.date.today().isoformat()
	got, failed = [], []
	kept = stored(folder)
	for source in SETS:
		count = 0
		for name, title, url, _gate in source["pages"]:
			if cancel is not None and cancel.is_set():
				break
			try:
				text = fetch(url)
				if source["html"]:
					body = lessonText(text, source["stop"])
				else:
					# The wiki's page is Markdown already; it is kept as it is, with its lists and tables.
					body = guides.tidy(text).strip()
				if len(body) < MIN_CHARS:
					raise ValueError("what came back is not the page")
			except Exception as e:
				failed.append((f"{title}, from {source['title']}", f"{type(e).__name__}: {e}"[:160]))
				continue
			os.makedirs(_folder(folder, source), exist_ok=True)
			tmp = _path(folder, source, name) + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				f.write(_head(source, title, url, day) + body + "\n")
			os.replace(tmp, _path(folder, source, name))
			count += 1
		if count:
			got.append((source["title"], count))
			kept[source["id"]] = {"date": day, "pages": count}
	if got:
		os.makedirs(folder, exist_ok=True)
		with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as f:
			json.dump(kept, f, indent=1)
	return {"got": got, "failed": failed}


def stored(folder):
	"""What is on this computer: {the source's id: {"date", "pages"}}."""
	try:
		with open(os.path.join(folder, RECORD), encoding="utf-8") as f:
			found = json.load(f)
		return found if isinstance(found, dict) else {}
	except (OSError, ValueError):
		return {}


def here(folder):
	"""Whether any page is on this computer."""
	return any(
		os.path.isfile(_path(folder, source, name)) for source in SETS for name, _title, _url, _gate in source["pages"])


def _pages(folder):
	"""Every page that is here as (source, the page's title, its gate, its sections as (heading, sentences))."""
	found = []
	for source in SETS:
		for name, title, _url, gate in source["pages"]:
			try:
				with open(_path(folder, source, name), encoding="utf-8") as f:
					text = f.read()
			except (OSError, UnicodeDecodeError):
				continue
			# The lines at the top say where the page is from; they are for the user, not part of the lesson.
			body = text.split("\n\n", 2)[2] if text.startswith("# ") and text.count("\n\n") >= 2 else text
			sections = [(heading, guides.prose(part)) for heading, part in guides.cut(f"## {title}\n\n{body}")]
			found.append((source, title, gate, [(heading, said) for heading, said in sections if said]))
	return found


def load(folder):
	"""Every section of the material as (title, body, source), for the knowledge search."""
	return [
		(f"{title}: {heading}" if heading != title else title, said, SOURCE)
		for _source, title, _gate, sections in _pages(folder) for heading, said in sections]


def passages(folder):
	"""The material as small passages for answering a question (claw/lookup.py): each says which source it is
	from, is asked only about what its page is about, and comes after NVDA's own help among equals."""
	found = []
	for source, title, gate, sections in _pages(folder):
		for heading, said in sections:
			name = f"{title}: {heading}" if heading != title else title
			for at, piece in enumerate(lookup.chunks(said)):
				found.append(lookup.Passage(lookup.TRAINING, name, piece, source["title"], lead=at == 0, gate=gate))
	return found


def remove(folder):
	"""Delete the material from this computer: only the files VisionClaw itself kept. Returns what the sources
	whose pages were deleted are called."""
	gone = []
	for source in SETS:
		deleted = False
		for name, _title, _url, _gate in source["pages"]:
			for path in (_path(folder, source, name), _path(folder, source, name) + ".tmp"):
				try:
					os.remove(path)
					deleted = deleted or path.endswith(".md")
				except OSError:
					pass
		try:
			os.rmdir(_folder(folder, source))
		except OSError:
			pass
		if deleted:
			gone.append(source["title"])
	try:
		os.remove(os.path.join(folder, RECORD))
	except OSError:
		pass
	return gone


def summary(result):
	"""What an update did, in sentences."""
	lines = [f"Downloaded {count} {'page' if count == 1 else 'pages'} of {title} and kept them as Markdown." for title, count in result["got"]]
	if result["failed"]:
		lines.append(
			f"{len(result['failed'])} could not be downloaded; an earlier copy, if there is one, is still used: "
			+ "; ".join(f"{page} ({why})" for page, why in result["failed"][:4]) + ".")
	if result["got"]:
		lines.append(
			"VisionClaw now looks things up in them when you ask to learn or be taught something in NVDA, or ask about "
			"what a page is about, such as coming from JAWS. NVDA's own user guide is still asked first.")
	return " ".join(lines) or "Nothing was downloaded."


def storedText(folder, today=None):
	"""Which material is on this computer, from when, and where, in sentences for the user. Plain code says
	this; no model is asked."""
	kept = {ident: info for ident, info in stored(folder).items() if isinstance(info, dict)}
	lines, oldest = [], 0
	for source in SETS:
		count = sum(1 for name, _title, _url, _gate in source["pages"] if os.path.isfile(_path(folder, source, name)))
		if not count:
			continue
		days = guides._age(kept.get(source["id"], {}).get("date"), today)
		when = "from an unknown day" if days is None else "downloaded today" if days <= 0 else (
			f"downloaded on {kept[source['id']]['date']}, {days} {'day' if days == 1 else 'days'} ago")
		lines.append(f"{count} {'page' if count == 1 else 'pages'} of {source['title']}, by {source['by']}, {when}.")
		oldest = max(oldest, days or 0)
	if not lines:
		return (
			"No training material is on this computer yet. Ask VisionClaw to get the free NVDA training material; it "
			"says which sites it is from and asks before it goes online.")
	text = " ".join(lines) + f" They are kept as Markdown files, which you can read, in the folder {folder}."
	text += (
		" VisionClaw looks things up in them when you ask to learn or be taught something in NVDA, or about what a "
		"page is about. NVDA's own user guide is asked first.")
	if oldest > OLD_DAYS:
		text += " Ask VisionClaw to get the free NVDA training material again if you want newer copies; it never does so by itself."
	return text
