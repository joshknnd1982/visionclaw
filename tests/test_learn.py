# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Learning about a program from the internet, the notes kept of it, and the questions answered from them.
Plain Python: no NVDA, no model, and no internet. The internet here is a dictionary of addresses, and every
request that is made is written down, so that the test shows exactly what would be sent and to whom.

  python tests/test_learn.py
"""
import json
import os
import tempfile
import threading

import harness  # noqa: F401
from visionClaw.claw import learn, lookup, orchestrator, planner, policy, tools
from visionClaw.claw import task as taskModule
from visionClaw.claw.llm import LLMError

# --- A small internet ---
ARTICLE = (
	"Notepad++ is a text and source-code editor for use with Microsoft Windows. It supports tabbed editing.\n\n"
	"== History ==\nIt was first released in 2003 by Don Ho.\n\n"
	"== Features ==\nNotepad++ has syntax highlighting and macros. Press Ctrl+F to find text and Ctrl+H to replace it. "
	"Tabs can be closed with Ctrl+W.\n\n== References ==\nA list of sources that is long enough to be a section of its own, "
	"but says nothing about how the program is used at all.")
MANUAL_HOME = """<html><head><title>Notepad++ User Manual</title></head><body>
<nav><a href="/docs/getting-started/">Getting started</a> <a href="/docs/editing/">Editing</a>
<a href="/docs/license/">Copyright &amp; License</a> <a href="/download/">Download the manual</a>
<a href="https://elsewhere.example.com/docs/shortcuts/">Shortcuts on another website</a>
<a href="/docs/user-interface/#tabs">User Interface</a> <a href="/docs/editing/#top">Editing again</a></nav>
<h1>Notepad++ User Manual</h1><p>Welcome to the manual. Choose a chapter.</p></body></html>"""
EDITING = """<html><head><title>Editing | Notepad++ User Manual</title><script>var secret = "Ctrl+Alt+Delete";</script></head><body>
<h1>Editing</h1><p>This chapter is about editing text in Notepad++.</p>
<h2>Keyboard shortcuts for lines</h2>
<table><tr><th>Key</th><th>What it does</th></tr>
<tr><td>Ctrl+D</td><td>Duplicate the current line</td></tr>
<tr><td>Ctrl+L</td><td>Cut the current line</td></tr>
<tr><td>Ctrl+Shift+Up</td><td>Move the current line up</td></tr></table>
<h2>Cookie notice</h2><p>We use cookies. Press Ctrl+Shift+Delete in your browser to clear them, or press F5 to reload, as you like.</p>
<h2>Column mode</h2><p>Hold Alt+Shift and press the arrow keys to select a column of text. Then type to change every line at once.</p>
</body></html>"""
GETTING_STARTED = "<html><body><h1>Installation</h1><p>Notepad++ is installed with an installer. There is nothing more to say here.</p></body></html>"
INTERFACE = """<html><head><title>User Interface</title></head><body><h2>Tabs</h2>
<p>Press Ctrl+Tab to go to the next tab and Ctrl+Shift+Tab to go to the one before. Press Ctrl+W to close the tab.</p></body></html>"""
SITE_HOME = """<html><head><title>Notepad++</title></head><body><h2>Features</h2>
<p>Notepad++ is free. Press F11 for full screen and F12 for post-it mode. Press Ctrl+N for a new file.</p>
<a href="/news/">News</a> <a href="/donate/">Donate</a></body></html>"""
INTERNET = {
	"https://en.wikipedia.org/w/api.php?action=query&list=search": json.dumps({"query": {"search": [
		{"title": "Windows Notepad"}, {"title": "Notepad++"}, {"title": "Notepad (disambiguation)"}]}}),
	"https://en.wikipedia.org/w/api.php?action=query&prop=pageprops": json.dumps({"query": {"pages": {"1": {
		"title": "Notepad++", "pageprops": {"wikibase_item": "Q2033"}, "extract": ARTICLE}}}}),
	"https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity=Q2033&property=P2078": json.dumps(
		{"claims": {"P2078": [{"mainsnak": {"datavalue": {"value": "https://manual.example.org/"}}}]}}),
	"https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity=Q2033&property=P856": json.dumps(
		{"claims": {"P856": [{"mainsnak": {"datavalue": {"value": "https://npp.example.org/"}}}]}}),
	"https://manual.example.org/docs/getting-started/": GETTING_STARTED,
	"https://manual.example.org/docs/editing/": EDITING,
	"https://manual.example.org/docs/user-interface/": INTERFACE,
	"https://manual.example.org/": MANUAL_HOME,
	"https://npp.example.org/": SITE_HOME,
}


def internet(pages=INTERNET, asked=None):
	asked = [] if asked is None else asked

	def fetch(url, hosts=None):
		asked.append((url, hosts))
		host = url.split("/")[2]
		if hosts is not None and host not in hosts:
			raise ValueError("The answer came from a place it may not come from.")
		for start, body in pages.items():
			if url.startswith(start):
				if isinstance(body, Exception):
					raise body
				return body
		raise OSError(f"no such page: {url}")
	return fetch, asked


# --- Which program, and what it is called ---
assert learn.candidates("notepad++", "Notepad++", "new 1 - Notepad++") == ["Notepad++", "new 1"]
# What only names what runs the program is no name for it: a Java game is known by its window's title.
assert learn.candidates("javaw", "OpenJDK Platform binary", "Space Trader") == ["Space Trader", "javaw"]
assert learn.candidates("explorer", "Microsoft\u00ae Windows\u00ae Operating System", "Documents - File Explorer") == [
	"File Explorer", "Documents", "Windows File Explorer"]
assert learn.candidates("game", "", "") == ["game"] and learn.candidates("", "", "") == ["this program"]
for said, name in (
	("Learn about this program", ""), ("learn about this game, it is called Space Trader", "Space Trader"),
	("Learn about Notepad++", "Notepad++"), ("learn this app", ""), ("make notes on the program Audacity", "Audacity"),
	("learn about the program I am in", ""), ("Learn about Audacity from the internet", "Audacity"),
	("study this game online", ""), ("add this page to the notes on Notepad++", "Notepad++"),
	("research the game called Stardew Valley.", "Stardew Valley"), ("learn about it", ""),
):
	assert learn.saidName(said) == name, (said, learn.saidName(said))
assert learn.meansInFront("learn about this game, it is called Space Trader", "Space Trader")
assert learn.meansInFront("learn about this program", "") and not learn.meansInFront("Learn about Audacity", "Audacity")
assert learn.slug("Notepad++") == "notepad" and learn.slug("Stardew Valley") == "stardew-valley" and learn.slug("") == "program"
assert learn.searchWords("Audacity") == "Audacity software" and learn.searchWords("Doom", learn.GAME) == "Doom video game"
# A page about Notepad is not a page about Notepad++, and the other way round.
assert learn.isAbout("Notepad++ - Wikipedia", "Notepad++") and not learn.isAbout("Windows Notepad", "Notepad++")
assert learn.isAbout("Windows Notepad", "Notepad") and not learn.isAbout("Notepad++", "Notepad")
assert not learn.isAbout("Anything at all", "") and learn.isAbout("Stardew Valley (video game)", "stardew valley")
assert learn.wikiTitles(json.loads(INTERNET["https://en.wikipedia.org/w/api.php?action=query&list=search"]), "Notepad++") == ["Notepad++"]
assert learn.wikiTitles({"query": {"search": [{"title": "Audacity (band)"}, {"title": "Audacity (audio editor)"}, {"title": "Audacity"}]}},
	"Audacity")[0] in ("Audacity (band)", "Audacity (audio editor)", "Audacity")
assert learn.wikiTitles({}, "x") == [] and learn.addresses({}) == [] and learn.wikiArticle({}) == ("", "")
# Only web pages of text over https are read: no videos, no files, nothing that wants an account.
for url, ok in (
	("https://example.org/help", True), ("http://example.org/help", False), ("https://www.youtube.com/watch?v=1", False),
	("https://example.org/manual.pdf", False), ("javascript:alert(1)", False), ("https://m.facebook.com/x", False),
	("file:///c:/windows", False), ("https://localhost/x", False),
):
	assert learn.usable(url) == ok, url
# The links of a program's website that are worth reading: its own, about using it, the likeliest first.
assert learn.links(MANUAL_HOME, "https://manual.example.org/") == [
	("Getting started", "https://manual.example.org/docs/getting-started/"),
	("User Interface", "https://manual.example.org/docs/user-interface/"),
	("Editing", "https://manual.example.org/docs/editing/")], learn.links(MANUAL_HOME, "https://manual.example.org/")
assert learn.links(SITE_HOME, "https://npp.example.org/") == []

# --- Learning: what is asked, of whom, and what is kept ---
fetch, asked = internet()
told = []
result = learn.study("Notepad++", learn.PROGRAM, fetch, tell=told.append)
# Every request, in order. The program's name goes to Wikipedia; Wikidata is asked for two addresses by the
# number Wikipedia gave; the rest are pages of the program's own manual and website. Nothing else is sent.
assert [url for url, _hosts in asked] == [
	"https://en.wikipedia.org/w/api.php?action=query&list=search&srlimit=5&format=json&srsearch=Notepad%2B%2B+software",
	"https://en.wikipedia.org/w/api.php?action=query&prop=pageprops%7Cextracts&ppprop=wikibase_item&explaintext=1"
	"&redirects=1&format=json&titles=Notepad%2B%2B",
	"https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity=Q2033&property=P2078",
	"https://www.wikidata.org/w/api.php?action=wbgetclaims&format=json&entity=Q2033&property=P856",
	"https://manual.example.org/",
	"https://manual.example.org/docs/getting-started/",
	"https://manual.example.org/docs/user-interface/",
	"https://manual.example.org/docs/editing/",
	"https://npp.example.org/",
], asked
assert result["asked"] == [url for url, _hosts in asked]
# Wikipedia and Wikidata may only answer from their own servers; no search engine is asked at all.
assert [hosts for _url, hosts in asked[:4]] == [learn.WIKI_HOSTS] * 2 + [learn.WIKIDATA_HOSTS] * 2
assert not any("duckduckgo" in url or "google" in url or "bing" in url for url, _hosts in asked)
assert told == [
	"Asking Wikipedia about Notepad++.", "Asking Wikidata for the website and the manual of Notepad++.",
	"Reading manual.example.org on manual.example.org.", "Reading Getting started on manual.example.org.",
	"Reading User Interface on manual.example.org.", "Reading Editing on manual.example.org.",
	"Reading npp.example.org on npp.example.org."], told
assert result["intro"].startswith("Notepad++ is a text and source-code editor") and result["introUrl"] == "https://en.wikipedia.org/wiki/Notepad%2B%2B"
kept = [(learn.hostOf(page["url"]), [heading for heading, _body, _notes in page["sections"]]) for page in result["pages"]]
assert kept == [
	("en.wikipedia.org", ["Features"]), ("manual.example.org", ["Tabs"]),
	("manual.example.org", ["Keyboard shortcuts for lines", "Column mode"]), ("npp.example.org", ["Features"])], kept
# The cookie notice has keys in it and is left out all the same; a script's text is never read.
everything = json.dumps(result)
assert "cookies" not in everything and "secret" not in everything and "Ctrl+Alt+Delete" not in everything
assert ("Getting started on manual.example.org", "nothing in it is about keys or how to use it") in result["failed"]
# A table's row keeps the key with what it does.
lines = dict((heading, body) for page in result["pages"] for heading, body, _notes in page["sections"])
assert "| Ctrl+D | Duplicate the current line" in lines["Keyboard shortcuts for lines"], lines

# --- The notes, as a file the user can read, change and delete ---
with tempfile.TemporaryDirectory() as folder:
	store = learn.Notes(os.path.join(folder, "notes"))
	assert store.listed() == [] and store.read("notepad++") == "" and store.forProgram("notepad++") == ""
	assert store.listText().startswith("VisionClaw has no notes on any program yet.")
	text = learn.notesText(result, "notepad++", today="2026-11-17")
	path = store.save("notepad++", text)
	assert path == os.path.join(folder, "notes", "notepad.md") and os.path.isfile(path)
	assert text.splitlines()[0] == "# Notes on Notepad++ (program notepad++)"
	assert "Made by VisionClaw on 2026-11-17 from pages on the internet, for the program Notepad++. They may be wrong" in text
	assert "\n## What Notepad++ is\n\nNotepad++ is a text and source-code editor" in text
	assert "\n## Column mode\n\nHold Alt+Shift and press the arrow keys to select a column of text." in text
	assert "\nSource: https://manual.example.org/docs/editing/\n" in text and "\nSource: https://en.wikipedia.org/wiki/Notepad%2B%2B\n" in text
	assert store.listed() == [("notepad", "Notepad++", "2026-11-17", 6)], store.listed()
	assert store.nameOf("notepad++") == "Notepad++" and store.forProgram("notepad++") == "notepad"
	assert store.forProgram("npp", ["Notepad++"]) == "notepad" and store.forProgram("audacity", ["Audacity"]) == ""
	assert store.find("delete the notes on Notepad++") == ["notepad"] and store.find("delete the notes on Audacity") == []
	assert store.listText() == (
		f"VisionClaw has notes on 1 program: Notepad++, 6 notes from 2026-11-17. They are Markdown files in the folder {store.folder}.")
	told = learn.summary(result, path)
	assert told.startswith(
		"VisionClaw learned about the program Notepad++. It read 3 websites (en.wikipedia.org, manual.example.org, "
		f"npp.example.org) and kept 6 notes, in the file {path}. Not used: Getting started on manual.example.org. "
		"The notes are from the internet and may be wrong."), told
	assert told.endswith("To remove the notes, ask: delete the notes on this program.")

	# --- Questions are answered from the notes, with the website each is from ---
	notes = learn.passages(store.read("notepad++"), "Notepad++")
	assert all(passage.source == lookup.APP for passage in notes) and len(notes) >= 6
	here = lookup.Passage(lookup.APP, "The program in front", "The program in front is notepad++.", "the program notepad++", here=True)
	pool = notes + [here, lookup.Passage(lookup.SYSTEM, "Copy, cut, paste", "Control+C copies and Control+V pastes.")]
	found = lookup.resultText(lookup.about("How do I duplicate the current line?", pool))
	assert found.startswith(
		"From the notes on Notepad++, from manual.example.org: Keyboard shortcuts for lines. Key, What it does; "
		"Ctrl+D, Duplicate the current line;"), found
	found = lookup.resultText(lookup.about("how do I select a column of text", pool))
	assert found.startswith("From the notes on Notepad++, from manual.example.org: Column mode. Hold Alt+Shift"), found
	# What the program is, is part of where the user is.
	found = lookup.resultText(lookup.about("What is this program?", pool))
	assert found.splitlines() == [
		"From the notes on Notepad++, from en.wikipedia.org: What Notepad++ is. Notepad++ is a text and source-code "
		"editor for use with Microsoft Windows. It supports tabbed editing.",
		"From the program notepad++: The program in front is notepad++."], found
	assert lookup.about("how do I bake a cake", pool) == []

	# --- The user changes the notes, a page is added to them, and they are deleted ---
	with open(path, "a", encoding="utf-8") as f:
		f.write("\n## My own note\n\nI use Ctrl+Q to comment a line out.\n")
	extra = learn.fromPage("Notepad++", learn.PROGRAM, "https://tips.example.net/npp", "Tips", learn.textToMarkdown(
		"Tips for Notepad++\nSearching\nPress Ctrl+F to find and F3 to find the next one. Press Ctrl+G to go to a line.\n"
		"About us\nWe are a small team that likes text editors very much indeed, and this says nothing of keys.", ["Searching", "About us"]))
	assert [(heading, notes) for heading, _body, notes in extra["pages"][0]["sections"]] == [("Searching", None)]
	store.save("notepad++", learn.merged(store.read("notepad++"), extra, "notepad++"))
	after = store.read("notepad++")
	assert "I use Ctrl+Q to comment a line out." in after and after.rstrip().endswith("Source: https://tips.example.net/npp")
	assert store.listed()[0][3] == 8 and "\n## Column mode\n" in after
	assert learn.merged("", extra, "notepad++", today="2026-11-17").startswith("# Notes on Notepad++ (program notepad++)")
	assert learn.fromPage("X", learn.PROGRAM, "u", "t", "A page with nothing of use in it.")["pages"] == []
	assert store.remove("notepad++") and not os.path.exists(path) and store.listed() == [] and not store.remove("notepad++")

# --- When the internet says no ---
# A program Wikipedia does not know: nothing is kept, and the user is told what they can do instead.
fetch, asked = internet({"https://en.wikipedia.org/w/api.php?action=query&list=search": json.dumps({"query": {"search": [
	{"title": "Quokka"}, {"title": "Zebra"}]}})})
nothing = learn.study("Zzyzx Editor", learn.PROGRAM, fetch)
assert not learn.learned(nothing) and len(asked) == 1
assert learn.summary(nothing, "") == (
	"VisionClaw looked for Zzyzx Editor on the internet and found nothing it could use, so no notes were kept. What went "
	"wrong: Wikipedia: it has no article that is clearly about the program Zzyzx Editor. You can still open a page "
	"about it in your browser and ask: add this page to the notes on Zzyzx Editor.")
# An article with the right name that is not about anything run on a computer is not taken either.
pages = dict(INTERNET)
pages["https://en.wikipedia.org/w/api.php?action=query&prop=pageprops"] = json.dumps({"query": {"pages": {"1": {
	"title": "Notepad++", "pageprops": {"wikibase_item": "Q1"}, "extract": "Notepad++ is a river in the north of a far country."}}}})
fetch, asked = internet(pages)
assert not learn.learned(learn.study("Notepad++", learn.PROGRAM, fetch)) and len(asked) == 2
# A server that says "too many requests" is given one pause and asked once more; a page that fails is left out.
tries = []
fetchAll, _asked = internet()


def busy(url, hosts=None):
	tries.append(url)
	if "list=search" in url and len(tries) == 1:
		raise OSError("HTTP Error 429: Too Many Requests")
	if url.endswith("/docs/editing/"):
		raise OSError("timed out")
	return fetchAll(url, hosts)


result = learn.study("Notepad++", learn.PROGRAM, busy, cancel=threading.Event(), wait=0)
assert tries[0] == tries[1] and learn.learned(result) and ("Editing on manual.example.org", "OSError: timed out") in result["failed"]
# Stopping the request stops the learning before the next page is asked for.
stop = threading.Event()
fetch, asked = internet()
try:
	learn.study("Notepad++", learn.PROGRAM, lambda url, hosts=None: (stop.set(), fetch(url, hosts))[1], cancel=stop)
	raise AssertionError("a stopped request must not go on reading pages")
except taskModule.Cancelled:
	assert len(asked) == 1


# --- The model's part, and what plain code lets through ---
class Scripted:
	"""A model that answers each question with the next of its scripted answers."""

	def __init__(self, *answers):
		self.answers, self.asked = list(answers), []

	def json(self, role, system, user, schema, maxTokens=300, **more):
		self.asked.append((system, user, schema))
		answer = self.answers.pop(0)
		if isinstance(answer, Exception):
			raise answer
		return answer


# It says which of the names plain code found the program is known by, and what kind of thing it is.
llm = Scripted({"name": "Space Trader", "kind": "game"})
assert learn.identify(llm, "vision", "javaw", "OpenJDK Platform binary", "Space Trader", "button \"New Game\"") == ("Space Trader", "game")
system, user, schema = llm.asked[0]
assert schema["properties"]["name"]["enum"] == ["Space Trader", "javaw"] and schema["properties"]["kind"]["enum"] == ["game", "program", "utility"]
assert "Window title: Space Trader" in user and "The focus is on: button \"New Game\"" in user
# A name the user said is the name; the model only says what kind of thing it is.
llm = Scripted({"name": "Audacity", "kind": "program"})
assert learn.identify(llm, "vision", "", "", "", "", ["Audacity"]) == ("Audacity", "program")
assert llm.asked[0][2]["properties"]["name"]["enum"] == ["Audacity"] and "Program file" not in llm.asked[0][1]
# Without an answer, the likeliest name and "program" are taken.
assert learn.identify(Scripted(LLMError("no answer")), "vision", "notepad++", "Notepad++", "new 1 - Notepad++") == ("Notepad++", "program")
assert learn.identify(None, "vision", "notepad++", "Notepad++", "") == ("Notepad++", "program")
# It writes the notes; a note with a key the page does not have, or with words the page does not have, is dropped.
body = "Press Ctrl+D to duplicate the current line. Press Ctrl+L to cut the current line."
written = learn.checked([
	"Ctrl+D duplicates the current line.", "Ctrl+L cuts the current line.", "Ctrl+K deletes the current line.",
	"The quokka is a small marsupial found in Australia.", "- ctrl + d duplicates the current line", "Ctrl+D duplicates the current line.", ""],
	body)
assert written == ["Ctrl+D duplicates the current line.", "Ctrl+L cuts the current line.", "ctrl + d duplicates the current line"], written
llm = Scripted({"notes": ["Ctrl+D duplicates the current line.", "Press F9 to save the line."]})
assert learn.writeNotes(llm, "vision", "Notepad++", "Lines", body) == ["Ctrl+D duplicates the current line."]
assert "Program: Notepad++\nSection: Lines\nText:\nPress Ctrl+D" in llm.asked[0][1] and "Copy every key exactly" in llm.asked[0][0]
# Nothing that stands in the text: then the page's own words are kept instead.
assert learn.writeNotes(Scripted({"notes": ["Press F9 to save."]}), "vision", "N", "Lines", body) is None
assert learn.writeNotes(Scripted({"notes": []}), "vision", "N", "Lines", body) is None
assert learn.writeNotes(Scripted(LLMError("cut off")), "vision", "N", "Lines", body) is None
# In the file, a section the model wrote is a list of points; one it did not is the page's own text.
fetch, asked = internet()
result = learn.study("Notepad++", learn.PROGRAM, fetch, write=lambda heading, text: (
	["Ctrl+D duplicates the current line."] if heading.startswith("Keyboard") else None))
text = learn.notesText(result, "notepad++", today="2026-11-17")
assert "\n## Keyboard shortcuts for lines\n\n- Ctrl+D duplicates the current line.\n\nSource: https://manual.example.org/docs/editing/\n" in text
assert "\n## Column mode\n\nHold Alt+Shift" in text
assert "1 of them were put into short points by the model and checked against the page." in learn.summary(result, "x.md")
assert lookup.resultText(lookup.about("how do I duplicate a line", learn.passages(text, "Notepad++"))) == (
	"From the notes on Notepad++, from manual.example.org: Keyboard shortcuts for lines. Ctrl+D duplicates the current line.")

# --- What "this" means: a model chooses among what plain code offers ---
assert lookup.pointsAt("what does this do") and lookup.pointsAt("how do I close it") and not lookup.pointsAt("how do I copy text")
choices = [("the program", "notepad Notepad"), ("the window", "Untitled - Notepad"), ("the control that has the focus", "check box \"Word wrap\"")]
llm = Scripted({"about": 3})
assert lookup.referent(llm, "vision", "what does this do", choices) == 2
assert "3. the control that has the focus: check box \"Word wrap\"" in llm.asked[0][1] and llm.asked[0][2]["properties"]["about"]["enum"] == [1, 2, 3]
assert lookup.referent(Scripted(LLMError("x")), "vision", "what does this do", choices) is None
assert lookup.referent(Scripted(), "vision", "what is this", [("the program", "notepad"), ("the window", "")]) == 0  # one thing: no question
# Where the question says itself what it means, plain code knows, and no model is asked.
for question, meant in (
	("What is this program?", lookup.PROGRAM_MEANT), ("how do I close this window", lookup.WINDOW_MEANT),
	("what does this button do", lookup.CONTROL_MEANT), ("what is the focused control for", lookup.CONTROL_MEANT),
	("how do I play this game", lookup.PROGRAM_MEANT), ("what does this do", ""), ("how do I close it", ""),
):
	assert lookup.saysWhich(question) == meant, (question, lookup.saysWhich(question))
# The name of what is meant is what a question that names nothing is about; in a question that names
# something it only breaks ties.
assert lookup.asked("what does this do", "Word wrap") == ({"word", "wrap"}, set())
assert lookup.asked("how do I close this", "Untitled Notepad") == ({"clos", "untitl", "notepad"}, {"untitl", "notepad"})
keys = lookup.Passage(lookup.WINDOW, "Keys of the controls in this window", "Word wrap (check box): Alt+W; Zoom in (button): Control+Plus.", "this window")
focus = lookup.Passage(lookup.WINDOW, "The control that has the focus", "The focus is on: check box \"Word wrap\".", "this window", here=True)
closing = lookup.Passage(lookup.SYSTEM, "Closing a window", "Alt+F4 closes the window in use.")
pool = [keys, focus, closing]
assert lookup.about("what does this do", pool) == [focus]  # nothing named, nobody asked what "this" is
assert lookup.about("what does this do", pool, extra="Word wrap") == [focus, keys]
assert lookup.about("how do I close this", pool, extra="Untitled Notepad")[0] is closing

# --- A capable model picks the line that answers; a very small one is given nothing to choose ---
both = "From NVDA: review_copy: Copies with the review cursor. Keys: NVDA+f10.\nFrom Windows: Copy, cut, paste. Control+C copies."
assert lookup.pickable(both) == both.splitlines() and lookup.pickable("From NVDA: one line.") == ["From NVDA: one line."]
assert lookup.pickable(lookup.nothingText("how do I bake a cake")) == [] and lookup.pickable("") == []
assert lookup.pickable("From the program notepad: It is notepad.\nFrom this window: Its title.") == []
assert lookup.quoted(both, both.splitlines()[1]) == "From Windows: Copy, cut, paste. Control+C copies."
assert lookup.quoted(both) == both.replace("\n", " ") and lookup.quoted(both, "not a line of it") == both.replace("\n", " ")
assert lookup.nothingText("how do I bake a cake", "notepad", "Untitled", notes=False).endswith(
	"VisionClaw has no notes on this program yet. Ask it to learn about this program, and it reads up on it on the "
	"internet after asking you.")
assert "VisionClaw's notes on the program" in lookup.nothingText("how do I bake a cake", "notepad", "Untitled", notes=True)

registry = tools.Registry()
registry.add(tools.Tool(lookup.TOOL, "answer a question", lambda task, question: both,
	{"question": {"type": "string", "description": "the question", "auto": True}}, looks=True, title="Asking"))
registry.add(tools.Tool(tools.ANSWER, "tell the user the result", lambda task: ""))


class Model:
	def __init__(self, capable):
		self.capable, self.prompts = capable, []

	def oneModel(self):
		return True

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"id": "m", "name": "Model"} if self.capable else {"id": "m", "name": "Model", "suggest": False}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		user = messages[-1]["content"]
		self.prompts.append(user)
		schema = options["response_format"]["json_schema"]["schema"]["properties"]
		if "choice" in schema:
			return json.dumps({"choice": "explain_keys"})
		if "line" in schema:
			assert schema["line"]["enum"] == [0, 1, 2] and "or 0 if none does" in user
			return json.dumps({"line": self.line})
		raise AssertionError(f"an unexpected question to the model: {user}")


for capable, line, answer in (
	(True, 2, "From Windows: Copy, cut, paste. Control+C copies."), (False, 2, both.replace("\n", " ")),
	# The model read both lines and says neither answers: that is said, and the nearest is marked as that.
	(True, 0, "Nothing that was found answers that. The nearest thing found, which may not be what you want: " + both.replace("\n", " ")),
):
	model = Model(capable)
	model.line = line
	runner = orchestrator.Orchestrator(model, registry, lambda question, choices: 0, lambda: "Program: notepad. Window title: Untitled.")
	runner.stepwise = lambda: "always"
	task = runner.run(taskModule.Task("How do I copy text?"))
	assert task.state == taskModule.DONE and task.answer == answer, (capable, task.answer)
	# The same question asked again is a small model's vote (claw/llm.py), not a question of another kind.
	assert len(set(model.prompts)) == (2 if capable else 1)
	if capable:
		assert "Where the user is: Program: notepad. Window title: Untitled." in model.prompts[1]
		assert "2. From Windows: Copy, cut, paste. Control+C copies." in model.prompts[1]

# --- The plan ---
for request, recipe in (
	("Learn about this program", "learn_app"), ("learn about this game from the internet", "learn_app"),
	("Study this app and make notes", "learn_app"), ("Learn about Notepad++", "learn_app"), ("make notes on this utility", "learn_app"),
	("research this game online", "learn_app"), ("Delete the notes on this program", "forget_notes"),
	("delete all your notes", "forget_notes"), ("forget the notes on Audacity", "forget_notes"),
	("Which notes do you have?", "app_notes"), ("open the notes on this program", "app_notes"),
	("Add this page to the notes on Notepad++", "note_page"), ("how do I duplicate a line", "explain_keys"),
	("search the web for the weather", "search_web"), ("what does this do", "nvda_question"),
):
	assert planner.hint(request) == recipe, (request, planner.hint(request))
for recipe, steps in (("learn_app", ("learn_app",)), ("note_page", ("note_page",)), ("app_notes", ("app_notes",)), ("forget_notes", ("forget_notes",))):
	assert planner.RECIPES[recipe][2] == steps
assert policy.AUTO == "auto"

print("OK")
