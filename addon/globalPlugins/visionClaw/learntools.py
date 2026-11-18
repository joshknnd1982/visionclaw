# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - learning about the program or game the user is in, and the notes that are kept of it.
# "Learn about this program": the program in front is identified, a model says which of its names it is known
# by and what kind of thing it is, the user is asked, and then Wikipedia, Wikidata and the program's own
# website are read (claw/learn.py); a model writes short notes from each useful section and plain code keeps
# those that stand in the text. "Add this page to the notes on ...": the page open in the user's own browser
# is read through NVDA, with nothing going online. The notes are Markdown files the user can open and delete;
# questions are answered from them by look_up (asktools.py).

import os

import addonHandler

from . import asktools, net, updater, webtools
from .claw import debuglog, learn, policy
from .claw import task as taskModule
from .claw.catalog import VISION
from .claw.llm import LLM
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()

# A page is given up on after this long.
FETCH_SECONDS = 15


def agent():
	"""What a request calls itself. Wikipedia asks programs to say what they are; nothing about the user or
	the computer is in it."""
	version = updater.currentVersion()
	return f"VisionClaw{f'/{version}' if version else ''} (NVDA screen reader add-on)"


def fetch(url, hosts=None):
	return net.fetchText(url, timeout=FETCH_SECONDS, limit=learn.PAGE_BYTES, hosts=hosts, agent=agent(), textOnly=True)


def register(plugin, add, text, onMain, confirm):
	"""The tools for learning about a program. add, text, onMain and confirm are the helpers of nvdatools.build."""
	notes = plugin.appNotes

	def writer(task, llm, name):
		"""How a section becomes short notes: by the model, unless it is one of the very smallest, which make
		things up; then the page's own words are kept."""
		entry = plugin.runtime.entry(VISION) or {}
		if entry.get("suggest") is False:
			return None

		def write(heading, body):
			task.emit(taskModule.DETAIL, f"Writing notes on: {heading}.")
			return learn.writeNotes(llm, VISION, name, heading, body)
		return write

	def nowAndNotes():
		"""The program in front, and the file name of its notes if there are any."""
		who = onMain(asktools.programNow)
		ident = notes.forProgram(who["app"], learn.candidates(who["app"], who["product"], who["title"]))
		return who, ident

	def learnApp(task, name, asked):
		said = " ".join(str(name or "").split())
		inFront = learn.meansInFront(asked, said)
		llm = LLM(plugin.runtime, task)
		model = policy.roleName(VISION, policy.isOneModel(plugin.runtime))
		if inFront:
			who = onMain(asktools.programNow)
			name, kind = learn.identify(
				llm, VISION, who["app"], who["product"], who["title"], who["focus"], [said] if said else None)
			ident = learn.slug(who["app"])
			task.emit(taskModule.TALK, (
				f"The program in front is {who['app']}"
				+ (f", with the window {who['title']}" if who["title"] else "")
				+ f". The {model} takes it to be the {kind} {name}."))
		else:
			name, kind = learn.identify(llm, VISION, "", "", "", "", [said])
			ident = learn.slug(said)
		old = notes.read(ident)
		# Going online is always asked about, whatever the settings say, and the question says what is sent.
		# Translators: Asked before VisionClaw goes online to learn about a program. {name} is the program.
		question = _(
			"VisionClaw will go online to learn about {name}. It sends the name {name} to Wikipedia, asks Wikidata for "
			"the address of its website and its manual, and then reads up to {pages} help pages straight from that "
			"website. No search engine is used. Nothing else about you or your computer is sent; each of these sees "
			"your internet address, as it would in your browser. What is read is kept as notes in a file on this "
			"computer, which you can delete whenever you like."
		).format(name=name, pages=learn.MAX_PAGES)
		if old:
			# Translators: Added to the question when there are notes on the program already.
			question += " " + _("The notes VisionClaw already has on it are replaced.")
		# Translators: The end of the question before VisionClaw goes online to learn about a program.
		question += " " + _("Go online now?")
		# Translators: The choices before VisionClaw goes online to learn about a program.
		if plugin.clawAsk(question, [_("Yes, go online"), _("No")]) != 0:
			return "You said no, so VisionClaw did not go online and no notes were made."
		task.check()
		result = learn.study(
			name, kind, fetch, task.cancel, lambda sentence: task.emit(taskModule.DETAIL, sentence), writer(task, llm, name))
		debuglog.log("learn", (
			f"Learned about {name} ({kind}). Requests went to: {result['asked']}. Kept: "
			f"{[(page['url'], len(page['sections'])) for page in result['pages']]}. Not used: {result['failed']}"))
		if not learn.learned(result):
			return learn.summary(result, "")
		path = notes.save(ident, learn.notesText(result, ident))
		return learn.summary(result, path, replaced=bool(old))

	add("learn_app",
		"go online, after asking, and learn about the program or game the user is in, or one they name: what it "
		"is, its keys and how it is used, from Wikipedia and the program's own website, kept as notes on this "
		"computer; only when the user asks to learn about, study or research a program",
		learnApp, {
			"name": text("the program's name if the user said it, otherwise empty", maxLength=60, auto=learn.saidName),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, title="Learning about the program", tell=VERBATIM)

	def notePage(task, name, asked):
		found = onMain(webtools.pageText)
		if found is None:
			raise ToolError(
				"The user is not in a web page. They open a page about the program in their browser first, and ask again from there.")
		title, body = found
		address = onMain(lambda: webtools.address(webtools.page())) or ""
		headings = [label for _level, label, _node in (onMain(webtools.headings) or [])]
		said = " ".join(str(name or "").split())
		known = notes.find(asked) or notes.find(said)
		if not said and not known:
			raise ToolError(
				"The request does not say which program the page is about. The user says it, as in: add this page to "
				"the notes on, and then the program's name.")
		ident = known[0] if known else learn.slug(said)
		program = next((kept for file, kept, _day, _count in notes.listed() if file == ident), said)
		llm = LLM(plugin.runtime, task)
		result = learn.fromPage(
			program, learn.PROGRAM, address, title, learn.textToMarkdown(body, headings), writer(task, llm, program))
		if not result["pages"]:
			return (
				f"The page {title or 'in the browser'} has nothing about keys or about how {program} is used that "
				"VisionClaw could find, so nothing was added to the notes.")
		count = len(result["pages"][0]["sections"])
		# Translators: Asked before a web page is added to the notes on a program. {count} is a number.
		confirm(_("Add {count} notes from the page {title} to the notes on {program}?").format(
			count=count, title=title or address, program=program))
		path = notes.save(ident, learn.merged(notes.read(ident), result, ident))
		return (
			f"Added {count} {'note' if count == 1 else 'notes'} from the page {title or address} to the notes on "
			f"{program}, in the file {path}. Nothing was fetched from the internet for this: the page was read as "
			"your browser shows it.")

	add("note_page",
		"add what the web page open in the user's browser says to the notes on a program the user names; reads "
		"the page as the browser shows it and fetches nothing",
		notePage, {
			"name": text("the name of the program the page is about, as the user said it", maxLength=60, auto=learn.saidName),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, title="Adding the page to the notes", tell=VERBATIM)

	def appNotes(task, asked):
		who, mine = nowAndNotes()
		named = notes.find(asked)
		wanted = named[0] if named else mine
		low = (asked or "").lower()
		if wanted and any(word in low.split() for word in ("open", "show", "read", "see", "edit")):
			path = notes.path(wanted)
			try:
				os.startfile(path)
			except OSError as e:
				raise ToolError(f"The notes could not be opened ({e}). They are the file {path}.")
			return f"The notes are open in a window. They are the file {path}. You can change or delete them there."
		told = notes.listText()
		if notes.listed():
			told += (
				f" There are notes on the program you are in, {who['app']}." if mine
				else f" There are none on the program you are in, {who['app']}; ask VisionClaw to learn about this program.")
		return told

	add("app_notes",
		"say which programs VisionClaw has notes on, made from the internet, or open the notes on a program",
		appNotes, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking at the notes", tell=VERBATIM)

	def forgetNotes(task, which):
		kept = notes.listed()
		if not kept:
			return "VisionClaw has no notes on any program, so there is nothing to delete."
		low = f" {(which or '').lower()} "
		if any(word in low for word in (" all ", " every ", " everything ")):
			chosen = [ident for ident, _name, _day, _count in kept]
		else:
			_who, mine = nowAndNotes()
			chosen = notes.find(which) or ([mine] if mine else [])
		if not chosen:
			return (
				"VisionClaw has no notes on the program you are in, and the request names none of those it has. "
				+ notes.listText())
		names = [name for ident, name, _day, _count in kept if ident in chosen]
		# Translators: Asked before notes on programs are deleted. {names} are the programs.
		confirm(_("Delete the notes on {names}? The files are removed from this computer.").format(names=", ".join(names)))
		gone = [name for ident, name, _day, _count in kept if ident in chosen and notes.remove(ident)]
		if not gone:
			raise ToolError("The notes could not be deleted. Their files are in the folder " + notes.folder + ".")
		return f"Deleted the notes on {', '.join(gone)}. " + (
			"VisionClaw has no notes left." if len(gone) == len(kept) else notes.listText())

	add("forget_notes",
		"delete the notes VisionClaw made about a program: the one the user names, the one they are in, or all",
		forgetNotes, {"which": text("which notes to delete, in the user's words", maxLength=300, auto=True)},
		changes=True, title="Deleting the notes", tell=VERBATIM)
