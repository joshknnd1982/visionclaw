# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Free material that teaches NVDA, downloaded when the user asks (claw/training.py), and the help that is on
the computer already kept as Markdown files (claw/helpfiles.py). Plain Python: no NVDA, no model, and nothing
online: the pages are made up here and handed over by a stand-in for the internet.

What is checked: only the sources the owner said yes to, over https, from the servers named; the question
that is asked first names every site and the number of requests; a lesson's web page is kept without the
site's menus and offers, a wiki page as it is; each file says where it is from and whose it is; a page that
is not the page leaves the earlier copy; each page is asked only about what it is about, and after NVDA's own
help; what the user said about themselves once opens the page for it; the instructions and skills that go
with it; a page of help kept as Markdown gives the same sections when it is read again, and is made again
when its page changes; and where the requests are sent.

  python tests/test_training.py
"""
import datetime
import os
import re
import tempfile
import time

import harness  # noqa: F401
from visionClaw.claw import helpfiles, lookup, memories, planner, prompts, skills, training

# --- 1. Only what the owner said yes to ---

assert [source["id"] for source in training.SETS] == ["nvda-wiki", "afb-learn-nvda", "hadley-nvda"]
assert training.HOSTS == ("raw.githubusercontent.com", "afb.org", "www.afb.org", "hadleyhelps.org", "www.hadleyhelps.org")
urls = [url for source in training.SETS for _name, _title, url, _gate in source["pages"]]
assert len(urls) == training.pageCount() == 18 and len(set(urls)) == 18
assert all(url.startswith("https://") and url.split("/")[2] in training.HOSTS for url in urls), urls
names = [f"{source['id']}/{name}" for source in training.SETS for name, _title, _url, _gate in source["pages"]]
assert len(set(names)) == len(names) and all(re.fullmatch(r"[a-z0-9/-]+", name) for name in names), names
asked = training.question()
assert asked.startswith("Download free material that teaches NVDA?") and "18 requests are sent" in asked
for said in ("the NVDA wiki", "American Foundation for the Blind", "Hadley", "raw.githubusercontent.com", "afb.org", "hadleyhelps.org",
		"nothing about you"):
	assert said in asked, said
# Every page has something that must be named for it to be asked: none of this answers just anything.
assert all(gate is not None for source in training.SETS for _n, _t, _u, gate in source["pages"])

# --- 2. A lesson's web page: the lesson, without the site around it ---

LESSON = (
	"<html><head><title>Lesson | Site</title></head><body><header><h2>Main Menu</h2><a href='/'>Home</a></header>"
	"<nav><h2>Breadcrumb</h2></nav><main><h1>Learn NVDA: Windows Basics</h1><form><input name='q'><button>Search</button></form>"
	"<iframe src='https://video.example/1'></iframe><h2>Transcript</h2><p>Intro: Welcome to the lesson.</p>"
	"<h3>Windows Basics</h3><p>Narrator: Press the Windows key to open the Start menu, then type the name of a program.</p>"
	+ "".join(f"<p>[Ricky] In part {n} we press Alt+Tab to move between the open windows, and NVDA says each one.</p>" for n in range(30))
	+ "<h2>Learn NVDA</h2><ul><li><a href='/next'>Next lesson</a></li></ul><h2>Take Action Today</h2><p>Donate now.</p>"
	"</main><footer><h2>Follow Us</h2></footer></body></html>")
text = training.lessonText(LESSON, ("Learn NVDA", "Take Action Today"))
assert "Press the Windows key to open the Start menu, then type the name of a program." in text
assert "In part 3 we press Alt+Tab" in text and text.count("\n\n") >= 30
# No menus, forms, players or offers, and no speaker marks before what is said.
for gone in ("Main Menu", "Breadcrumb", "Search", "Donate", "Next lesson", "Follow Us", "Narrator:", "[Ricky]", "Intro:"):
	assert gone not in text, gone
# A teaser that only begins what the full text says is left out.
TEASER = (
	"<main><h1>Useful Shortcuts</h1><p>[Ricky] Hi, today we learn a few NVDA shortcuts that give us the info we need.</p>"
	"<h2>Resources</h2><p>[Ricky] Hi, today we learn a few NVDA shortcuts that give us the info we need. The first one is "
	"NVDA+T, which reads the title of the window.</p><h3>Handouts</h3><p>Quick-start guide (PDF)</p></main>")
text = training.lessonText(TEASER, ("Handouts",))
assert text == "Hi, today we learn a few NVDA shortcuts that give us the info we need. The first one is NVDA+T, which reads the title of the window.", text

# --- 3. Downloading: kept as Markdown with where it is from; a page that is not the page changes nothing ---

WIKI_PAGE = (
	"# Switching from JAWS\n\n## Cursors\n\nThe JAWS cursor is called object navigation with the review cursor in NVDA.\n\n"
	"| JAWS | NVDA |\n|---|---|\n| Insert+T | NVDA+T |\n\n"
	+ "".join(f"## Part {n}\n\n{'Words for people who come from the other screen reader, part %d. ' % n * 12}\n\n" for n in range(6)))
RIBBON = "## The ribbon\n\nPress Alt to reach the ribbon, then the arrow keys to move along its tabs.\n\n" + "More about tabs and groups. " * 80
fetched = []


def fetch(url):
	fetched.append(url)
	if url.startswith(training.WIKI):
		return RIBBON if "Ribbon" in url else WIKI_PAGE
	return LESSON


folder = tempfile.mkdtemp()
result = training.update(folder, fetch, today="2026-11-18")
assert fetched == urls, fetched
assert result == {"got": [("the NVDA wiki", 6), ("AFB's Learn NVDA lessons, from 2016", 8), ("Hadley's NVDA workshops", 4)], "failed": []}, result
assert training.here(folder) and training.stored(folder)["afb-learn-nvda"] == {"date": "2026-11-18", "pages": 8}
with open(os.path.join(folder, "afb-learn-nvda", "windows-basics-1.md"), encoding="utf-8") as f:
	kept = f.read()
assert kept.startswith("# Windows basics, part 1\n\nFrom AFB's Learn NVDA lessons, from 2016, by the American Foundation for the Blind. "), kept[:200]
assert "Copyright American Foundation for the Blind. Kept here for your own reading." in kept and "afb.org" in kept
assert "It was not written by NV Access and may describe an older NVDA." in kept
with open(os.path.join(folder, "nvda-wiki", "switching-from-jaws.md"), encoding="utf-8") as f:
	kept = f.read()
# A page of the wiki is Markdown already and is kept as it is, with its table.
assert "No licence is stated." in kept and "| Insert+T | NVDA+T |" in kept and "## Cursors" in kept
told = training.summary(result)
assert told.startswith("Downloaded 6 pages of the NVDA wiki and kept them as Markdown.") and "NVDA's own user guide is still asked first." in told
assert "the models" not in told.lower()
said = training.storedText(folder, datetime.date(2026, 11, 20))
assert "8 pages of AFB's Learn NVDA lessons, from 2016, by the American Foundation for the Blind, downloaded on 2026-11-18, 2 days ago." in said, said
assert folder in said and "never does so by itself" not in said
assert "never does so by itself" in training.storedText(folder, datetime.date(2028, 1, 1))


def broken(url):
	if "afb.org" in url:
		raise OSError("no connection")
	return "<html><body>Just a moment...</body></html>"


before = os.path.getmtime(os.path.join(folder, "hadley-nvda", "getting-started.md"))
result = training.update(folder, broken, today="2026-12-01")
assert result["got"] == [] and len(result["failed"]) == 18, result
assert "18 could not be downloaded; an earlier copy" in training.summary(result)
assert os.path.getmtime(os.path.join(folder, "hadley-nvda", "getting-started.md")) == before
assert training.stored(folder)["hadley-nvda"]["date"] == "2026-11-18"

# --- 4. Asked only about what a page is about, and after NVDA's own help ---

passages = training.passages(folder)
assert passages and all(passage.source == lookup.TRAINING and passage.gate is not None for passage in passages)
assert {passage.origin for passage in passages} == {"the NVDA wiki", "AFB's Learn NVDA lessons, from 2016", "Hadley's NVDA workshops"}
own = lookup.fromSections([("Start Menu", "The Windows key opens the Start menu, where you type the name of a program.", "userGuide")])
found = lookup.about("What is the NVDA name for the JAWS cursor?", own + passages)
assert found and found[0].origin == "the NVDA wiki" and "object navigation with the review cursor" in found[0].text, found
# The same question without the word JAWS is not answered from the page for people who come from JAWS ...
assert not any(passage.origin == "the NVDA wiki" for passage in lookup.about("What is the review cursor in object navigation?", own + passages))
# ... unless the user said once that they come from JAWS, and VisionClaw remembers it.
assert training.comesFrom(["You come from JAWS.", "Your braille display is a Focus 40."]) == ["JAWS"]
assert training.comesFrom(["Your braille display is a Focus 40."]) == []
found = lookup.about("What is the review cursor in object navigation?", own + passages, program=["notepad"] + training.comesFrom(["You used JAWS before."]))
assert any(passage.origin == "the NVDA wiki" for passage in found), found
# A lesson is for someone who asks to learn; any other question is NVDA's own to answer.
found = lookup.about("How do I open the Start menu and type the name of a program?", own + passages)
assert [passage.origin for passage in found] == ["NVDA's user guide"], [passage.origin for passage in found]
found = lookup.about("Teach me how to open the Start menu and type the name of a program.", own + passages)
assert found[0].origin == "NVDA's user guide" and any(passage.origin.startswith("AFB's") for passage in found), [p.origin for p in found]
assert any(passage.origin == "the NVDA wiki" for passage in lookup.about("How do I reach the ribbon and move along its tabs?", own + passages))
# What a line begins with is how the instruction for it is chosen, for every source there is.
for source in training.SETS:
	assert prompts.aboutFound(f"From {source['title']}: a lesson.") == ("trainingHelp",), source["title"]
assert prompts.TRAINING_HELP in prompts.speaking("Task.", found="1. From Hadley's NVDA workshops: Useful shortcuts.")
assert prompts.TRAINING_HELP not in prompts.speaking("Task.", found="1. From NVDA's user guide: Browse Mode.")
# For the knowledge search, the same pages as sections.
sections = training.load(folder)
assert all(source == training.SOURCE for _title, _body, source in sections)
assert any(title == "Switching from JAWS to NVDA: Cursors" and "Insert+T: NVDA+T" in body for title, body, _source in sections), sections[:3]

assert training.remove(folder) == ["the NVDA wiki", "AFB's Learn NVDA lessons, from 2016", "Hadley's NVDA workshops"]
assert not training.here(folder) and training.passages(folder) == [] and training.stored(folder) == {}
assert not os.path.exists(os.path.join(folder, "afb-learn-nvda")) and training.remove(folder) == []
assert training.storedText(folder).startswith("No training material is on this computer yet.")

# --- 5. What the user says about themselves is kept, and where the requests are sent ---

for said in ("I used to use JAWS.", "I'm coming from JAWS.", "I am a former Window-Eyes user.", "I sometimes use a game controller.",
		"I use a trackpad on my laptop."):
	assert memories.lasting(said) == memories.YOU, said
assert memories.worthKeeping("I'm coming from JAWS. How do I read the title?", memories.AUTO, [], lambda tool: False)

SENT = {
	"get the free NVDA training material": "update_training",
	"download the NVDA wiki and the AFB lessons": "update_training",
	"update the training material": "update_training",
	"which training material do I have?": "training_info",
	"open the training material folder": "training_info",
	"where are the markdown files": "training_info",
	"delete the training material": "remove_training",
	"get the latest NVDA developer guides": "update_guides",
	"teach me object navigation": "coach",
	"give me a lesson on browse mode": "coach",
	"what does the training material say about browse mode": "nvda_question",
}
for request, recipe in SENT.items():
	assert planner.hint(request) == recipe, (request, planner.hint(request))

lib = skills.Skills(tempfile.mkdtemp(), recipes=set(planner.RECIPES))
for request, slug in {
		"I'm coming from JAWS, what is the JAWS cursor called here": "coming-from-another-screen-reader",
		"I am using my real mouse, where is the OK button": "hand-on-the-mouse",
		"I have a trackpad, how do I hear what is under the pointer": "hand-on-the-mouse",
		"which training material do I have": "training-material"}.items():
	chosen = [skill.slug for skill in lib.choose(request)]
	assert slug in chosen, (request, chosen)
mouse = skills.guide(lib.choose("I am using my real mouse, where is the OK button"), "explain_keys")
assert "do not send them back to the keyboard" in mouse and "NVDA+M" in mouse, mouse
for request in ("what time is it", "read the title", "turn off the typing echo"):
	assert not lib.choose(request), (request, lib.choose(request))

# --- 6. The help that is on the computer already, kept as Markdown ---

helpDir = tempfile.mkdtemp()
page = os.path.join(helpDir, "userGuide.html")
PAGE = (
	"<html><body><h1>User Guide</h1><p>Contents of the guide, which names everything and says nothing itself.</p>"
	"<h2>Browse Mode</h2><p>Web pages are read in browse mode, where the arrow keys move through the page.</p>"
	"<table><tr><th>Name</th><th>Key</th></tr><tr><td>Find</td><td>NVDA+control+f</td></tr></table>"
	"<h2># A heading with a mark</h2><p>#hashtags at the start of a line are kept as text and are no heading.</p></body></html>")
with open(page, "w", encoding="utf-8") as f:
	f.write(PAGE)
dest = os.path.join(helpDir, "kept", "nvda-user-guide.md")
made = []


def make(text):
	made.append(len(text))
	return lookup.htmlSections(text)


first = helpfiles.kept(page, dest, "NVDA's user guide", make)
assert first == [(title, " ".join(body.split())) for title, body in lookup.htmlSections(PAGE)] and len(first) == 2, first
with open(dest, encoding="utf-8") as f:
	written = f.read()
assert written.startswith(f"# NVDA's user guide\n\n{helpfiles.MADE_FROM}{page}\n\n## Browse Mode\n\nWeb pages are read in browse mode"), written[:200]
assert "Find, NVDA+control+f" in written and helpfiles.madeFrom(written) == page
# Read again, it is the same, and the page is not turned into Markdown a second time.
assert helpfiles.kept(page, dest, "NVDA's user guide", make) == first and len(made) == 1
assert helpfiles.fromMarkdown(helpfiles.toMarkdown("T", "x", first)) == first
# When the page changes, as after an update of NVDA, the file is made again.
time.sleep(0.05)
with open(page, "w", encoding="utf-8") as f:
	f.write(PAGE.replace("the arrow keys move through the page", "the arrow keys move through the page as through a document"))
os.utime(page, (time.time() + 5, time.time() + 5))
again = helpfiles.kept(page, dest, "NVDA's user guide", make)
assert len(made) == 2 and "as through a document" in again[0][1]
# Another page for the same file, as after NVDA's language was changed: made again too.
other = os.path.join(helpDir, "benutzerhandbuch.html")
with open(other, "w", encoding="utf-8") as f:
	f.write("<html><body><h1>Handbuch</h1><p>Inhalt des Handbuchs, der alles nennt und selbst nichts sagt.</p><h2>Lesemodus</h2>"
		"<p>Webseiten werden im Lesemodus gelesen, in dem die Pfeiltasten durch die Seite gehen.</p></body></html>")
os.utime(dest, (time.time() + 60, time.time() + 60))
assert helpfiles.kept(other, dest, "NVDA's user guide", make)[0][0] == "Lesemodus" and len(made) == 3
# No page: nothing. A file that cannot be written: the page is read as it is.
assert helpfiles.kept(os.path.join(helpDir, "none.html"), dest, "x", make) == []
blocked = os.path.join(page, "cannot", "be.md")
assert helpfiles.kept(page, blocked, "NVDA's user guide", make) == again
assert helpfiles.fileName("clock & calendar/2") == "clock-calendar-2" and helpfiles.fileName("") == "help"
assert "has not been turned into Markdown files yet" in helpfiles.listText(os.path.join(helpDir, "empty"))
os.makedirs(os.path.join(helpDir, "kept", "addons"))
with open(os.path.join(helpDir, "kept", "addons", "clock.md"), "w", encoding="utf-8") as f:
	f.write("# The help of the add-on Clock\n")
told = helpfiles.listText(os.path.join(helpDir, "kept"))
assert told.startswith("NVDA's own help is kept as 1 Markdown file, and the help of 1 add-on as one file each, in the folder"), told

# --- 7. Letting the user know what can be downloaded: the overview, and one sentence said once ---

from visionClaw.claw import offers  # noqa: E402

nothingHere = {"devGuide": True, "addonGuide": False, "training": False}
told = offers.overview(nothingHere)
assert told.startswith("VisionClaw can get these for you from the internet. Each is downloaded only when you ask for it, and it asks you first.")
assert "The NVDA Developer Guide is on this computer; the NVDA Add-on Development Guide is not yet." in told
assert "It is not on this computer yet. Say: get the free NVDA training material." in told
for said in ("JAWS", "American Foundation for the Blind", "Hadley", "learn about this program", "check for updates"):
	assert said in told, said
assert len(told) < 1400 and "Both are on this computer" in offers.overview({"devGuide": True, "addonGuide": True, "training": True})
# Every sentence the user is told to say is sent where it says.
for words, recipe in (
		(offers.ASK_OVERVIEW, "downloads_info"), (offers.ASK_GUIDES, "update_guides"), (offers.ASK_TRAINING, "update_training"),
		("learn about this program", "learn_app"), ("check for updates", "update_visionclaw"),
		("which developer guides do I have", "guides_info"), ("which training material do I have", "training_info"),
		("What guides can VisionClaw download?", "downloads_info"), ("what help can you get for me from the internet", "downloads_info")):
	assert planner.hint(words) == recipe, (words, planner.hint(words))
assert offers.ASK_GUIDES in told and offers.ASK_TRAINING in told and offers.ASK_OVERVIEW in offers.SENTENCES[offers.OVERVIEW]

path = os.path.join(tempfile.mkdtemp(), "offered.json")
once = offers.Offers(path)
# After a request about writing an add-on: the guide for that, when it is not here.
said = once.next("Write an add-on that beeps when a link gets the focus", ["write_addon"], nothingHere, today="2026-11-18")
assert said == offers.SENTENCES[offers.GUIDES] and said.startswith("This is said once: ") and offers.ASK_GUIDES in said and "asks you first" in said
# Said once: not again, also not in another session.
assert once.next("Write an add-on that says hello", ["write_addon"], nothingHere) == ""
assert offers.Offers(path).next("Fix the add-on", ["fix_addon"], nothingHere) == "" and offers.Offers(path).said() == {offers.GUIDES: "2026-11-18"}
# After a request to learn, or one that names another screen reader: the lessons.
assert once.next("Teach me how to read a web page", ["nvda_question"], nothingHere) == offers.SENTENCES[offers.TRAINING]
assert once.next("I come from JAWS, how do I read the title", ["explain_keys"], nothingHere) != offers.SENTENCES[offers.TRAINING]
# After any other question: that there is an overview to ask for. Then nothing more, ever.
assert once.next("How do I read the title?", ["explain_keys"], nothingHere) == ""  # the JAWS question above was told of the overview
assert sorted(once.said()) == [offers.GUIDES, offers.OVERVIEW, offers.TRAINING]
for request, recipes in (("How do I read the status bar?", ["explain_keys"]), ("Teach me browse mode", ["coach"]), ("Write an add-on", ["write_addon"])):
	assert once.next(request, recipes, nothingHere) == "", request
# What is here already is not offered, nothing is offered after a request that was itself about downloading
# or that changes a setting, and a file that cannot be written does not end anything.
fresh = offers.Offers(os.path.join(tempfile.mkdtemp(), "offered.json"))
everything = {"devGuide": True, "addonGuide": True, "training": True}
assert fresh.next("Write an add-on that beeps", ["write_addon"], everything) == ""
assert fresh.next("Teach me how to read a web page", ["nvda_question"], everything) == ""
assert fresh.next("get the latest NVDA developer guides", ["update_guides"], nothingHere) == ""
assert fresh.next("what can you download for me", ["downloads_info"], nothingHere) == ""
assert fresh.next("Make NVDA talk faster", ["change_setting"], nothingHere) == "" and fresh.said() == {}
assert fresh.next("Teach me how to read a web page", ["nvda_question"], nothingHere) == offers.SENTENCES[offers.TRAINING]
blocked = offers.Offers(os.path.join(path, "cannot", "be.json"))
assert blocked.next("How do I read the title?", ["explain_keys"], nothingHere) == offers.SENTENCES[offers.OVERVIEW]
# Nothing in what is said names a model, and each sentence says how to get the thing.
for sentence in offers.SENTENCES.values():
	assert not re.search(r"\bmodels?\b", sentence, re.IGNORECASE) and ("say: " in sentence or "ask: " in sentence), sentence

print("OK")
