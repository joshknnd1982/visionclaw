# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Working the computer itself, requests that depend on something, long requests split by plain rules, and the
router. Plain Python: no NVDA, no model, and nothing on the real computer is opened, emptied or changed. The
tools here are stand-ins with the forms of the real ones; the real ones are driven in tests/test_nvda_stub.py.

  python tests/test_computer.py
"""
import json
import re

import harness  # noqa: F401
from visionClaw.claw import computer, controls, lookup, orchestrator, planner, pointer, router, shapes, skills, tools
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw import task as taskModule

# --- Sizes and times in words ---

assert computer.sizeText(0) == "0 bytes" and computer.sizeText(2048) == "2 KB" and computer.sizeText(5 << 20) == "5 MB"
assert computer.sizeText(3 << 30) == "3.0 GB" and computer.sizeText(725 << 30) == "725 GB"
assert computer.spanText(90) == "1 minute" and computer.spanText(3 * 3600 + 600) == "3 hours and 10 minutes"
assert computer.spanText(86400 + 9 * 3600) == "1 day and 9 hours"

# --- What is to be opened, from the user's own words ---

for said, name in (
	("open my recycle bin please", "recycle bin"), ("Go into my windows settings", "windows settings"),
	("launch google chrome", "google chrome"), ("open the start menu", "start menu"),
	("take me to my downloads folder", "downloads folder"), ("Could you open Notepad for me?", "notepad"),
	("open gmail.com in my google chrome", "gmail com"), ("start steam", "steam"),
	("If you see recycle bin, open it (this follows: Look at my screen)", "if you see recycle bin open it"),
):
	assert computer.wanted(said) == name, (said, computer.wanted(said))

# A name with the ending of a file is a file, and no address of a website or VisionClaw's notes on a program.
# Measured with Qwen3.5 9B on 2026-11-18: "Open report.pdf." ended in a question about opening a website.
for said, recipe in (
		("Open report.pdf.", "open_thing"), ("open notes.txt", "open_thing"), ("Open budget 2026.xlsx", "open_thing"),
		("open bbc.co.uk", "open_website"), ("go to gmail.com", "open_website"), ("visit example.org", "open_website"),
		("open report.pdf on the website example.com", "open_website"), ("open the notes on this program", "app_notes")):
	assert planner.hint(said) == recipe, (said, planner.hint(said))
assert computer.namesFile("Open report.pdf.") and not computer.namesFile("open bbc.co.uk") and not computer.namesFile("open notepad")

PLACES = computer.places()
assert len({item["id"] for item in PLACES}) == len(PLACES)
for item in PLACES:
	# Only what is fixed in the code is ever opened for a place: a folder of Windows, a settings page, a tool.
	assert item["target"].startswith(("shell:", "ms-settings:")) or re.fullmatch(r"[a-z]+\.exe", item["target"]), item
	assert not re.search(r"\s", item["id"]), item
THINGS = PLACES + [
	computer.thing("desktop", "Firefox", computer.ON_DESKTOP, r"C:\Users\x\Desktop\Firefox.lnk"),
	computer.thing("desktop", "Zoom Workplace", computer.ON_DESKTOP, r"C:\Users\x\Desktop\Zoom Workplace.lnk"),
	computer.thing("program", "Google Chrome", computer.PROGRAM, r"C:\Start\Google Chrome.lnk"),
	computer.thing("program", "Word 2021", computer.PROGRAM, r"C:\Start\Word 2021.lnk"),
	computer.thing("program", "WordPad", computer.PROGRAM, r"C:\Start\WordPad.lnk"),
	computer.thing("program", "Space Trader", computer.PROGRAM, r"C:\Start\Space Trader.lnk"),
	computer.thing("program", "Space Trader Editor", computer.PROGRAM, r"C:\Start\Space Trader Editor.lnk"),
]
for said, ids, sure in (
	("recycle bin", ["place-recycle-bin"], True), ("trash", ["place-recycle-bin"], True),
	("windows settings", ["settings"], True), ("bluetooth settings", ["settings-bluetooth"], True),
	("downloads folder", ["place-downloads"], True), ("firefox", ["desktop-firefox"], True),
	("chrome", ["program-google-chrome"], False), ("zoom", ["desktop-zoom-workplace"], False),
	# "Word" is in the name of one program as a word of its own; WordPad only begins with it.
	("word", ["program-word-2021"], False),
	# One name said word for word shuts out a longer one that has it.
	("space trader", ["program-space-trader"], True),
	("trader", ["program-space-trader", "program-space-trader-editor"], False),
	# Nothing is opened for a word that names nothing, or for "it".
	("my holiday plans", [], False), ("it", [], False), ("", [], False),
):
	found, certain = computer.find(said, THINGS)
	assert [item["id"] for item in found] == ids and certain == sure, (said, [item["id"] for item in found], certain)
lines = computer.foundText(computer.find("trader", THINGS)[0])
assert shapes.idsIn(lines) == ["program-space-trader", "program-space-trader-editor"], lines
assert "ask to click it instead" in computer.nothingFound("my holiday plans")
assert computer.browserOf("go to gmail.com in my google chrome") == ("chrome.exe", "Google Chrome")
assert computer.browserOf("open bbc.co.uk with firefox") == ("firefox.exe", "Firefox")
assert computer.browserOf("open bbc.co.uk") is None and computer.browserOf("what is the cutting edge") is None

# --- The Recycle Bin ---

assert computer.binText(0, 0) == "The Recycle Bin is empty. There is nothing to empty."
small = computer.binText(12, 5 << 20, 200 << 30, 500 << 30)
assert small.startswith("The Recycle Bin holds 12 items, 5 MB in all. It does not need emptying for room"), small
big = computer.binText(300, 3 << 30, 200 << 30, 500 << 30)
assert "It is worth emptying: that would free 3.0 GB." in big and big.endswith("To empty it, say: empty the Recycle Bin."), big
# Little room left on the drive: then a few hundred megabytes are worth it too.
tight = computer.binText(40, 300 << 20, 4 << 30, 500 << 30)
assert "worth emptying" in tight and "which is little" in tight, tight
assert computer.binText(1, 100).startswith("The Recycle Bin holds 1 item, 100 bytes in all.")
assert computer.binText(None, 0) == "Windows did not say what the Recycle Bin holds."
assert [computer.binState(text) for text in (computer.binText(0, 0), small, big, "x")] == ["empty", "some", "worth", ""]
for said, empties in (
	("empty the recycle bin", True), ("Empty my trash please", True), ("delete everything in the recycle bin", True),
	("check and see if my recycle bin needs to be emptied or not", False), ("should I empty the recycle bin?", False),
	("how do I empty the recycle bin", False), ("is the recycle bin empty", False), ("empty the cart", False),
):
	assert computer.emptiesBin(said) == empties, said
for said, asks in (
	("check and see if my recycle bin needs to be emptied or not", True), ("is my recycle bin full", True),
	("how much is in the trash", True), ("See if it needs to be emptied or not (this follows: Check my recycle bin)", True),
	("drag the file onto the trash", False), ("restore my essay from the recycle bin", False),
	("open the recycle bin", False), ("how do I empty the recycle bin", False), ("what is on my screen", False),
):
	assert computer.asksAboutBin(said) == asks, said

# --- The computer's volume ---

for said, wish in (
	("turn down my system volume", (computer.DOWN, 10)), ("turn the computer's volume up a lot", (computer.UP, 25)),
	("lower the system volume a little", (computer.DOWN, 5)), ("raise the computer volume by 20", (computer.UP, 20)),
	("set the system volume to 40 percent", (computer.SET, 40)), ("mute my computer", (computer.MUTE, 0)),
	("unmute the computer", (computer.UNMUTE, 0)), ("what is the volume of my computer", (computer.SAY, 0)),
	# NVDA's own volume is a setting of NVDA, and a bare "volume" stays what it was before: NVDA's.
	("turn down the volume", None), ("make nvda's volume lower", None), ("make the voice louder", None),
):
	assert computer.volumeOf(said) == wish, (said, computer.volumeOf(said))
assert computer.volumeNew(40, (computer.DOWN, 10)) == (30, False)
# Turning down stops where NVDA's speech can still be heard.
assert computer.volumeNew(15, (computer.DOWN, 10)) == (10, True) and computer.volumeNew(10, (computer.DOWN, 10)) == (10, True)
assert computer.volumeNew(95, (computer.UP, 10)) == (100, False) and computer.volumeNew(40, (computer.SET, 5)) == (5, False)
assert computer.volumeText(20, False) == "The computer's volume is at 20 percent."
assert computer.volumeText(20, True).endswith("and the sound is muted.")

# --- Locking, sleeping, restarting, shutting down ---

for said, what in (
	("restart my computer", computer.RESTART), ("shut down the computer", computer.SHUTDOWN),
	("turn off my pc", computer.SHUTDOWN), ("lock my computer", computer.LOCK), ("put the laptop to sleep", computer.SLEEP),
	("log off", computer.SIGN_OUT), ("sign out of windows", computer.SIGN_OUT), ("cancel the shutdown", computer.CANCEL),
	# Nothing of NVDA's, of a program's or of a website's is meant, and no question about how.
	("restart nvda", None), ("sign out of gmail", None), ("turn off the typing echo", None), ("close the program", None),
	("how do I restart my computer", None), ("shut down the browser", None), ("lock the screen curtain add-on", None),
):
	assert computer.powerOf(said) == what, (said, computer.powerOf(said))

# --- Windows that are open ---

WINDOWS = [
	{"hwnd": 1, "title": "Inbox (3) - sam@example.com - Gmail - Google Chrome", "app": "chrome", "front": True, "minimized": False},
	{"hwnd": 2, "title": "Settings", "app": "ApplicationFrameHost", "front": False, "minimized": False},
	{"hwnd": 3, "title": "notes.txt - Notepad", "app": "notepad", "front": False, "minimized": True},
	{"hwnd": 4, "title": "Document1 - Word", "app": "WINWORD", "front": False, "minimized": False},
]
listing = computer.windowsText(WINDOWS)
assert listing.splitlines()[0] == "4 windows open:" and listing.splitlines()[1].endswith("Google Chrome, in front"), listing
# A program is named as people call it, and only where the title does not already say which it is.
assert listing.splitlines()[2] == "2. Settings" and listing.splitlines()[4] == "4. Document1 - Word", listing
assert computer.windowLine({"title": "Untitled", "app": "msedge"}) == "Untitled (microsoft edge)"
assert "3. notes.txt - Notepad, minimized" in listing and computer.windowsText([]) == "No windows are open."
for said, hwnds in (
	("close windows settings", [2]), ("switch to notepad", [3]), ("switch to google chrome", [1]), ("close chrome", [1]),
	("minimize microsoft word", [4]), ("close the gmail window", [1]), ("close this window", [1]), ("close it", [1]),
	("switch to the spreadsheet", []), ("Settings, in front", [2]),
):
	assert [window["hwnd"] for window in computer.windowsMeant(said, WINDOWS)] == hwnds, (said, computer.windowsMeant(said, WINDOWS))
for said, action in (
	("close windows settings", computer.CLOSE), ("switch to notepad", computer.SWITCH), ("minimize chrome", computer.MINIMIZE),
	("make this window full screen", computer.MAXIMIZE), ("restore notepad", computer.RESTORE), ("quit word", computer.CLOSE),
):
	assert computer.windowActionOf(said) == action, said
assert computer.allWindows("minimize all windows") and computer.allWindows("show me the desktop")
assert not computer.allWindows("list everything inside nvda") and not computer.allWindows("close this window")
assert computer.listed("notepad", listing) and computer.listed("settings", listing) and not computer.listed("firefox", listing)

# --- Files in the user's folders ---

wish = computer.fileWish("what is in my downloads folder")
assert wish["folders"] == ["downloads"] and wish["named"] and not wish["words"] and wish["order"] == computer.NEWEST
wish = computer.fileWish("find the file named budget")
assert wish["folders"] == list(computer.FOLDERS) and wish["words"] == ["budget"] and wish["order"] == computer.BY_NAME
wish = computer.fileWish("how many pdfs are in my documents")
assert wish["folders"] == ["documents"] and wish["kinds"] == ["pdf"] and wish["count"] and not wish["words"]
wish = computer.fileWish("find my tax return spreadsheet")
assert wish["kinds"] == ["spreadsheet"] and wish["words"] == ["tax", "return"]
assert computer.fileFits("Tax Return 2025.xlsx", wish) and not computer.fileFits("Tax Return 2025.pdf", wish)
assert not computer.fileFits("holiday.xlsx", wish)
wish = computer.fileWish("what is in my downloads folder")
text = computer.filesText(wish, [("setup.exe", "Downloads", 5 << 20, "November 18, 2026", False), ("Old", "Downloads", 0, "May 2, 2025", True)],
	["Downloads"], 2)
assert text == (
	"2 items in Downloads. The newest first:\n1. setup.exe, 5 MB, in Downloads, changed November 18, 2026\n"
	"2. Old, a folder, in Downloads, changed May 2, 2025"), text
assert computer.filesText(wish, [], ["Downloads"], 0) == "No item was found in Downloads."
assert computer.filesText(computer.fileWish("find the file named budget"), [], ["Desktop"], 0).startswith(
	"Nothing with budget in its name was found in your Desktop, Documents")
assert computer.filesText(computer.fileWish("how many pdfs are in my documents"), [("a.pdf", "Documents", 1, "x", False)] * 3,
	["Documents"], 3) == "3 pdf files in Documents."

# --- Changing the user's files ---

for said, what, words, new in (
	("create a folder called Taxes in my documents", computer.MAKE_FOLDER, None, "Taxes"),
	("make a new folder named Holiday Photos on my desktop", computer.MAKE_FOLDER, None, "Holiday Photos"),
	("create a text file called shopping list in my documents", computer.MAKE_FILE, None, "shopping list"),
	("rename the file budget to Budget 2026", computer.RENAME, ["budget"], "Budget 2026"),
	("rename budget.xlsx in my documents to Budget Final", computer.RENAME, ["budget", "xlsx"], "Budget Final"),
	("move the file report.pdf from my downloads to my documents", computer.MOVE, ["report", "pdf"], ""),
	("copy the file budget to my desktop", computer.COPY, ["budget"], ""),
	("put the document letter on my desktop", computer.MOVE, ["letter"], ""),
	("delete the file old notes", computer.DELETE, ["old", "notes"], ""),
	("delete notes.txt", computer.DELETE, ["notes", "txt"], ""),
	("move the file old notes to the recycle bin", computer.DELETE, ["old", "notes"], ""),
	("delete this file", computer.DELETE, [], ""),
):
	found = computer.fileTask(said)
	assert found and found["what"] == what and found["new"] == new and (found["src"]["words"] if found["src"] else None) == words, (said, found)
assert computer.fileTask("create a folder called Taxes")["place"] == "documents" and not computer.fileTask("create a folder called Taxes")["placeSaid"]
assert computer.fileTask("make a new folder named Holiday Photos on my desktop")["place"] == "desktop"
dest = computer.fileTask("move report.pdf to the Taxes folder in my documents")["dest"]
assert (dest["key"], dest["words"]) == ("documents", ["taxes"]), dest
assert computer.fileTask("move the file report.pdf from my downloads to my documents")["src"]["folders"] == ["downloads"]
# The words must speak of a file, a folder or a document, or write a name with its ending. Everything else that
# is deleted, moved, copied or renamed stays what it was.
for said in ("delete the notes on this program", "copy the window title to the clipboard", "move the mouse to the left",
		"how do I rename a file", "remove the developer guides", "delete everything in the recycle bin", "rename this control Play",
		"Move to the next heading", "empty the recycle bin", "open the file budget", "delete the helper NVDA+alt+1", "make a file",
		"forget everything you remember", "delete the game skill", "copy the file path to the clipboard"):
	assert computer.fileTask(said) is None, (said, computer.fileTask(said))
assert computer.cleanName("  'Tax Return'. ") == "Tax Return" and computer.cleanName("Budget 2026") == "Budget 2026"
for bad in ("a/b", "con", "x" * 130, "", 'say "hi"', "what?*"):
	try:
		computer.cleanName(bad)
	except ValueError:
		continue
	raise AssertionError(bad)
assert computer.renamed("budget.xlsx", "Budget Final") == "Budget Final.xlsx" and computer.renamed("budget.xlsx", "plan.pdf") == "plan.pdf"
assert computer.renamed("Old", "Archive") == "Archive" and computer.endingOf("Setup.EXE") == ".exe" and computer.endingOf("notes") == ""
# A name that is exactly what was said shuts out those that merely have the word.
HITS = [("budget.xlsx", "Documents"), ("Budget notes.txt", "Documents"), ("Budget draft.txt", "Downloads")]
assert computer.bestFiles("the file budget", HITS) == [HITS[0]] and computer.bestFiles("budget.xlsx", HITS) == [HITS[0]]
assert computer.bestFiles("bud", HITS) == HITS

# --- Facts about the computer ---

for said, topic in (
	("how much disk space do I have left", computer.DISK), ("how much memory does my computer have", computer.MEMORY),
	("which processor do I have", computer.PROCESSOR), ("how long has my computer been on", computer.UPTIME),
	("am I connected to the internet", computer.NETWORK), ("which programs are running", computer.PROGRAMS),
	("what is my computer name", computer.SYSTEM), ("tell me about my computer", computer.OVERVIEW),
):
	assert computer.topicOf(said) == topic and computer.aboutComputer(said), (said, computer.topicOf(said))
assert computer.diskText([("C:", "Acer", 725 << 30, 952 << 30)]) == "Drive C: (Acer) has 725 GB free of 952 GB, 76 percent."
assert computer.diskText([("D:", "", 2 << 30, 100 << 30)]).endswith("2 percent. That is little.")
assert computer.memoryText(21 << 30, 31 << 30) == "The computer has 31 GB of memory. 32 percent of it is in use, and 21 GB is free."

# --- Requests that depend on something ---

for said, kind, what, state, then in (
	("If you see recycle bin, open it", computer.SEEN, "recycle bin", True, "open recycle bin"),
	("if you see the recycle bin on my desktop open it", computer.SEEN, "recycle bin", True, "open recycle bin"),
	("open the recycle bin if you see it", computer.SEEN, "recycle bin", True, "open the recycle bin"),
	("If there is a Steam icon on my desktop, double-click it", computer.SEEN, "Steam icon", True, "double-click Steam icon"),
	("if the recycle bin is on my screen, open it and tell me what is in it", computer.SEEN, "recycle bin", True,
		"open recycle bin and tell me what is in it"),
	("If you see recycle bin, open it (this follows: Look at my screen)", computer.SEEN, "recycle bin", True, "open recycle bin"),
	("if firefox is open, close it", computer.RUNNING, "firefox", True, "close firefox"),
	("if notepad isn't running, start it", computer.RUNNING, "notepad", False, "start notepad"),
	("if my recycle bin is not empty, empty it", computer.BIN_IS, "the Recycle Bin", "some", "empty the recycle bin"),
	("if the recycle bin needs emptying, tell me", computer.BIN_IS, "the Recycle Bin", "worth", "tell me"),
	("If the trash is empty, say so", computer.BIN_IS, "the Recycle Bin", "empty", "say so"),
):
	found = computer.condition(said)
	assert found and (found["kind"], found["what"], found["state"], found["then"]) == (kind, what, state, then), (said, found)
# Any other "if" is left to be planned as before.
for said in ("if it rains, tell me", "tell me if the page has loaded", "what if I press escape", "open notepad"):
	assert computer.condition(said) is None, (said, computer.condition(said))
assert computer.onlyTells("tell me") and computer.onlyTells("Let me know.") and not computer.onlyTells("tell me what is in it")
assert computer.seenIn("recycle bin", ["Firefox", "Recycle Bin", "Steam"]) == "Recycle Bin"
assert computer.seenIn("Steam icon", ["This PC  Steam  iTunes"]) and computer.seenIn("recycle bin", ["Recycle", "Bin"]) is None
assert computer.seenIn("recycle bin", ["Recycle Bin item 3 of 41"]) and computer.seenIn("bin", ["Cabinet"]) is None
assert computer.says("Yes: it is there.") and not computer.says("No: it is not there.") and not computer.says("")

# --- A named control of the program in front ---

for said, what, name, steps in (
	("turn on my nvidia gpu for this program", controls.ON, "nvidia gpu", controls.STEPS),
	("In this multipage dialog, turn on my nvidia gpu for this program", controls.ON, "nvidia gpu", controls.STEPS),
	("Turn off the media keys on my keyboard", controls.OFF, "media keys", controls.STEPS),
	("Turn the volume up a bit", controls.UP, "volume", controls.FEW),
	("Turn the equalizer down", controls.DOWN, "equalizer", controls.STEPS),
	("turn the bass all the way up in this app", controls.UP, "bass", controls.TO_END),
	("lower the brightness a lot", controls.DOWN, "brightness", controls.MANY),
	("enable dark mode in this program", controls.ON, "dark mode", controls.STEPS),
	("uncheck stay signed in", controls.OFF, "stay signed", controls.STEPS),
):
	found = controls.wish(said)
	assert found and (found["what"], found["name"], found["steps"]) == (what, name, steps), (said, found)
found = controls.wish("set the brightness to 70 percent in this program")
assert (found["what"], found["name"], found["value"], found["percent"]) == (controls.SET, "brightness", 70, True), found
# Nothing to set: a question about how, something that names no control, or says nothing to do with one.
for said in ("how do I turn on dark mode", "what is on my screen", "close settings", "turn it on", "open the volume mixer"):
	assert controls.wish(said) is None, (said, controls.wish(said))
assert controls.inApp("turn on my nvidia gpu for this program") and controls.inApp("In this multipage dialog, turn on x")
assert not controls.inApp("turn off the typing echo") and not controls.inApp("turn down my system volume")
LABELS = ["Start with Windows", "Volume", "Use NVIDIA GPU (high performance)", "Enable media keys", "Media key volume step", "OK"]
for name, indexes in (
	("nvidia gpu", [2]), ("media keys", [3]), ("start with windows", [0]),
	# "Volume" is the name of one control and a word in the name of another: the one it names wins.
	("volume", [1]), ("equalizer", []), ("keys", [3]), ("", []),
):
	assert controls.pick(name, LABELS) == indexes, (name, controls.pick(name, LABELS))
# Among controls that fit equally, the kind the wish is for wins: a slider for up and down.
assert controls.pick("gain", ["Gain", "Gain"], prefer=[1]) == [1] and controls.pick("gain", ["Gain", "Gain"]) == [0, 1]
assert controls.checked(["FOCUSABLE", "CHECKED"]) is True and controls.checked(["FOCUSABLE"]) is False
assert controls.checked(["HALFCHECKED"]) is None and controls.stepsText(controls.TO_END) == "all the way"

# --- Long requests are split by plain rules, where they can tell for certain ---

for request, parts in (
	("first, look at my screen. If you see recycle bin, open it.", ["Look at my screen", "If you see recycle bin, open it"]),
	("Go into my windows settings, turn down my system volume, close windows settings, then go to gmail.com in my "
		"google chrome and tell me how many emails I have.",
		["Go into my windows settings", "Turn down my system volume", "Close windows settings",
			"Go to gmail.com in my google chrome", "Tell me how many emails I have"]),
	("Turn off the typing echo and set punctuation to all.", ["Turn off the typing echo", "Set punctuation to all"]),
	("Click Options, then tell me what the window shows.", ["Click Options", "Tell me what the window shows"]),
	("Inspect this window for accessibility problems, then fix number 2.",
		["Inspect this window for accessibility problems", "Fix number 2"]),
	("Empty the recycle bin and restart my computer", ["Empty the recycle bin", "Restart my computer"]),
	("Open my downloads folder. What is the newest file there?", ["Open my downloads folder", "What is the newest file there?"]),
	("Please open notepad, then switch to firefox", ["Please open notepad", "Switch to firefox"]),
	# The owner's examples of work inside a program. "Adjust the volume and turn it up a bit" is one thing to do
	# with the volume; a button that is found before more is done is found to be clicked; and where something
	# is, said first, stays with what follows it.
	("find the settings button in this inaccessible app, then adjust the volume and turn it up a bit and turn the "
		"equalizer down, then close settings.",
		["Find and click the settings button in this inaccessible app", "Turn the volume up a bit", "Turn the equalizer down",
			"Close settings"]),
	("find the settings button, and then in this multipage dialog, turn on my nvidia gpu for this program, and turn off "
		"the media keys on my keyboard.",
		["Find and click the settings button", "In this multipage dialog, turn on my nvidia gpu for this program",
			"Turn off the media keys on my keyboard"]),
	# "It" is said as the thing the part before names, where plain code can tell which thing.
	("Open notepad and maximize it", ["Open notepad", "Maximize notepad"]),
	# Left to the model as before: one thing; a part that says "it"; a report on what was just looked at; text of
	# the user's own that has commas and "and"; a first part that is no thing to do.
	("Make NVDA talk faster", None),
	("If you see recycle bin, open it", None),
	("ask nvda to give me the current time and then the date.", None),
	("Look at this window and tell me what the buttons are", None),
	("I'm new to NVDA. How do I read the title of this window?", None),
	("This program has a dial that is only used by clicking and dragging. Make it work with the keyboard.", None),
	("What braille display do I have, and how many cells does it have?", None),
	("Open notepad, type hello world, then close it", None),
	("Do a deep query of this control and tell me how a sighted person works it.", None),
	("Make a new skill: when I ask about recipes, read the ingredients first, with their amounts exactly.", None),
	("Type garden gloves into the search box and search.", None),
	("Write an add-on that beeps when a link gets the focus, and say hello", None),
	("Remember that my display is a Focus 40, and tell me the time", None),
):
	assert planner.plainSplit(request) == parts, (request, planner.plainSplit(request))
assert planner.MAX_PARTS == 8


class NoModel:
	"""A model that must not be asked."""

	def json(self, *args, **kwargs):
		raise AssertionError("a model was asked")


# A request plain rules split, and one thing that depends on something, are not put to a model for splitting.
assert planner.split(NoModel(), "vision", "Empty the recycle bin and restart my computer") == [
	"Empty the recycle bin", "Restart my computer"]
assert planner.split(NoModel(), "vision", "If you see recycle bin, open it") == ["If you see recycle bin, open it"]

# --- Which recipe the words point to ---

for request, recipe in (
	("check and see if my recycle bin needs to be emptied or not", "recycle_bin"),
	("See if it needs to be emptied or not (this follows: Check my recycle bin)", "recycle_bin"),
	("is my recycle bin full?", "recycle_bin"), ("empty the recycle bin", "empty_bin"), ("empty my trash", "empty_bin"),
	("open the recycle bin", "open_thing"), ("Go into my windows settings", "open_thing"),
	("open my documents folder", "open_thing"), ("take me to my downloads", "open_thing"),
	("open bluetooth settings", "open_thing"), ("open firefox", "open_thing"), ("launch google chrome", "open_thing"),
	("start steam", "open_thing"), ("run notepad", "open_thing"),
	("turn down my system volume", "system_volume"), ("mute my computer", "system_volume"),
	("set the computer's volume to 30 percent", "system_volume"),
	("close windows settings", "window"), ("switch to firefox", "window"), ("minimize all windows", "window"),
	("show me the desktop", "window"), ("maximize this window", "window"), ("close this window", "window"),
	("what is in my downloads folder", "files"), ("find the file named budget", "files"),
	("how many pdfs are in my documents", "files"), ("what is the newest file in downloads", "files"),
	("how much disk space do I have left", "computer_info"), ("how much memory does my computer have", "computer_info"),
	("which programs are running", "computer_info"), ("am I connected to the internet", "computer_info"),
	("restart my computer", "power"), ("shut down the computer", "power"), ("lock my computer", "power"),
	("create a folder called Taxes in my documents", "file_task"), ("rename the file budget to Budget 2026", "file_task"),
	("move the file report.pdf from my downloads to my documents", "file_task"), ("delete the file old notes", "file_task"),
	("delete notes.txt", "file_task"), ("copy the file budget to my desktop", "file_task"),
	("delete the notes on this program", "forget_notes"), ("Copy the window title to the clipboard.", planner.OTHER),
	("Delete the developer guides.", "remove_guides"), ("save the add-on hello key as a file", "save_addon"),
	("cancel the shutdown", "power"),
	# What these words meant before, they still mean.
	("turn down the volume", "change_setting"), ("make the voice louder", "change_setting"),
	("drag the file onto the trash", "drag"), ("how do I empty the recycle bin", "explain_keys"),
	("How do I close this program?", "explain_keys"), ("How do I rename a file?", "explain_keys"),
	("open bbc.co.uk", "open_website"), ("Open the VisionClaw log.", "visionclaw_log"), ("Open NVDA Coach.", "coach"),
	("open the Options menu", "click"), ("start reading", "do_command"), ("How much battery is left?", "do_command"),
	("restart nvda", planner.hint("restart nvda")), ("What is in my library?", "library"),
	("Which windows are open?", "nvda_question"), ("list everything inside nvda", "audit_nvda"),
	("Click the New Game button.", "click"), ("Search the web for pictures of cats", "search_web"),
	("go to gmail.com in my google chrome", "open_website"), ("open it", planner.hint("open it")),
):
	assert planner.hint(request) == recipe, (request, planner.hint(request))
assert planner.hint("restart nvda") != "power" and planner.hint("open it") != "open_thing"
# A named control of the program in front: where the words say "this program", or right after a click or
# another control there. Alone, the same words mean what they always meant: NVDA's own setting.
for request, before, recipe in (
	("Find and click the settings button in this inaccessible app", None, "click"),
	("Click the Settings button.", None, "click"), ("find the settings button", None, "click"),
	("Turn the volume up a bit", "click", "set_control"), ("Turn the equalizer down", "set_control", "set_control"),
	("In this multipage dialog, turn on my nvidia gpu for this program", "click", "set_control"),
	("turn on my nvidia gpu for this program", None, "set_control"),
	("Turn off the media keys on my keyboard", "set_control", "set_control"),
	("Turn the volume up a bit", None, "change_setting"), ("Turn off the typing echo", None, "change_setting"),
	("Turn off the typing echo", "change_setting", "change_setting"), ("Close settings", "set_control", "window"),
	("turn down my system volume", "click", "system_volume"),
):
	assert planner.hint(request, before) == recipe, (request, before, planner.hint(request, before))
# Something that is only to be found is pointed at; found before more is done, it is clicked.
assert pointer.actionOf("find the settings button") == pointer.HOVER
assert pointer.actionOf("Find and click the settings button") == pointer.CLICK and pointer.actionOf("Click Options") == pointer.CLICK
# After a part that opens a web page, a part that only asks something asks it of that page.
assert planner.hint("tell me how many emails I have") == planner.OTHER
assert planner.hint("tell me how many emails I have", "open_website") == "web_page"
assert planner.hint("what does it say about refunds", "search_web") == "web_page"
assert planner.hint("turn down my system volume", "open_website") == "system_volume"
# A model's choice is corrected where plain code can tell: the words are sure, or the choice cannot be meant.
assert planner.fitted("nvda_question", "check and see if my recycle bin needs to be emptied or not", "recycle_bin") == "recycle_bin"
assert planner.fitted("change_setting", "Go into my windows settings", "open_thing") == "open_thing"
assert planner.fitted("change_setting", "turn down my system volume", "system_volume") == "system_volume"
assert planner.fitted("remember", "See if it needs to be emptied or not (this follows: Check my recycle bin)", "recycle_bin") == "recycle_bin"
assert planner.fitted("remember", "what is on my screen", "describe") == "describe"
assert planner.fitted("remember", "Remember that my display is a Focus 40", "remember") == "remember"
assert planner.fitted("power", "turn off the typing echo", "change_setting") == "change_setting"
assert planner.fitted("empty_bin", "is my recycle bin full", "recycle_bin") == "recycle_bin"
assert planner.fitted("click", "open firefox", "open_thing") == "click"  # not sure: the model's choice stands
assert planner.fitted("forget_notes", "delete notes.txt", "file_task") == "file_task"
assert planner.fitted("file_task", "delete the notes on this program", "forget_notes") == "forget_notes"

# --- The router: what a model is offered ---

ALL = list(planner.RECIPES)
NOWHERE = {router.WEB: False, router.CONTROLLER: False, router.DIRECT: False}
IN_BROWSER = dict(NOWHERE, **{router.WEB: True})
WEB_ONLY = ("web_page", "page_outline", "go_to", "page_navigate", "fill_field")


def offeredFor(part, facts=NOWHERE, before=None):
	return router.route(part, ALL, facts, before, planner.hinted(part, before), planner.needsFor(part, before))


plain = offeredFor("Make NVDA speak a little faster")
# The everyday core is always offered; what needs a web page, a controller or words of its own is not.
for name in ("change_setting", "do_command", "explain_keys", "nvda_question", "describe", "read_text", "click", "press_keys",
		"type_text", "write_addon", "open_website", "search_web", "where_am_i"):
	assert name in plain and name not in router.GATES, name
for name in WEB_ONLY + ("controller_info", "controller_mode", "power", "empty_bin", "recycle_bin", "system_volume", "touch",
		"pressure", "turn_view", "timed_click", "gesture", "remember", "add_skill", "learn_app", "update_guides", "coach"):
	assert name not in plain, name
assert len(plain) < len(ALL) / 3, (len(plain), len(ALL))
# A browser in front: what works a web page is offered, whatever the words.
inBrowser = offeredFor("Make NVDA speak a little faster", IN_BROWSER)
assert all(name in inBrowser for name in WEB_ONLY) and "controller_mode" not in inBrowser
# No browser in front, but the part before opens a page, or the words speak of one.
assert all(name in offeredFor("tell me how many emails I have", NOWHERE, "open_website") for name in WEB_ONLY)
assert "web_page" in offeredFor("What does this page say about refunds?") and "go_to" in offeredFor("Take me to the heading Refund policy")
assert "page_navigate" in offeredFor("Go back to the previous page.") and "fill_field" in offeredFor("Type garden gloves into the search box and search.")
# A controller: when one is connected, or named.
assert "controller_mode" in offeredFor("Make NVDA speak a little faster", dict(NOWHERE, **{router.CONTROLLER: True}))
assert "controller_info" in offeredFor("Is a game controller connected?")
# A fact that could not be found out hides nothing; a fact that is plainly no does.
assert "mouse_way" not in offeredFor("what now", NOWHERE) and "mouse_way" in offeredFor("what now", dict(NOWHERE, **{router.DIRECT: True}))
# What reads everything from the words is offered exactly when the words say it.
assert "power" in offeredFor("restart my computer") and "power" not in offeredFor("restart the game")
assert "touch" in offeredFor("Pinch the Options button with two fingers.") and "turn_view" in offeredFor("Turn left.")
assert "remember" in offeredFor("Remember that my display is a Focus 40") and "remember" in offeredFor("I prefer short answers")
# A named control of the program in front is offered where the words say so or right after a click there, and
# not for words that alone mean NVDA's own setting.
assert "set_control" in offeredFor("turn on my nvidia gpu for this program") and "set_control" in offeredFor("Turn the volume up a bit", NOWHERE, "click")
assert "set_control" not in offeredFor("Turn off the typing echo") and "change_setting" in offeredFor("Turn the volume up a bit", NOWHERE, "click")
# With no facts at all, as when where the user is could not be found out, nothing is hidden for the place.
assert all(name in router.route("what now", ALL, {}, None, (), planner._NEEDS) for name in WEB_ONLY + ("controller_mode", "mouse_way"))
# What the planner's own patterns find in the words is always offered, wherever the user is.
for request in (
	"check and see if my recycle bin needs to be emptied or not", "Go into my windows settings", "close windows settings",
	"turn down my system volume", "Which developer guides do I have?", "Open the VisionClaw log.", "Which skills do you have?",
	"Do a full audit of NVDA.", "What does the Clock add-on do?", "Let the arrow keys work the volume dial.", "Scroll down a page.",
	"Drag the New Game button onto the Quit button.", "What did you change?", "Undo that.", "Is VisionClaw up to date?",
	"Which speech synthesizer am I using?", "What model is installed?", "Give me a hint about browse mode.",
	"Make this control keyboard navigable.", "Fix the accessibility problems on this page.", "What can you download for me?",
	"Learn about this game", "Forget that.", "What do you remember about me?", "What is in my library?",
	"Give this program a hotkey, NVDA+alt+1, that clicks the Options button.", "Name the focused button Share on this website.",
	"What is the window class of the focused control?", "Tell me everything NVDA knows about this control.",
	"What does the function api.getFocusObject do?", "List the add-ons you have made.", "Which add-ons do I have?",
	"The add-on hello key does not work, it says nothing. Fix it.", "This game has its own mouse pointer.",
	"what is in my downloads folder", "how much disk space do I have left", "switch to firefox", "open firefox",
):
	pointed = planner.hint(request)
	assert pointed != planner.OTHER and pointed in offeredFor(request), (request, pointed)
# In a plan a model writes itself, the tools of what was left out are left out too; a tool no recipe uses stays.
names = ["look", "read_page", "page_navigate", "controller_mode", "check_seen", "find_setting", "power"]
kept = router.tools(names, planner.RECIPES, set(plain))
# Reading a page stays: searching the web, which is always offered, reads the page it finds.
assert kept == ["look", "read_page", "check_seen", "find_setting"], kept
assert router.tools(names, planner.RECIPES, set(inBrowser)) == ["look", "read_page", "page_navigate", "check_seen", "find_setting"]
assert router.offeredText(14, 83).startswith("Offered for this: 14 of 83 kinds of request") and router.offeredText(83, 83) == ""
assert router.closed(["a", "b", "c"], ["b"]) == ["a", "c"]

# --- Whole requests, with stand-in tools and a scripted model ---

V = tools.VERBATIM


def text(description, **extra):
	return dict({"type": "string", "description": description}, **extra)


def makeRegistry(state):
	reg = tools.Registry()

	def add(name, description, fn, fields=None, **options):
		reg.add(tools.Tool(name, description, fn, fields, **options))

	asked = {"asked": text("what the user asked for", auto=True)}
	add("look", "look at the screen", lambda task, target, question: "The desktop shows a grid of icons.", {
		"target": text("what", enum=["window", "screen"], auto=lambda part: "screen"), "question": text("what to find out", auto=True),
	}, looks=True, title="Looking at the screen", tell=V)

	def checkSeen(task, what, asked):
		state.setdefault("checked", []).append(what)
		if computer.seenIn(what, state.get("screen", [])):
			return f"{computer.YES} {what} is on the screen: its name is in the text that is shown."
		return f"{computer.NO} {what} is not on the screen: its name is not in the text that is shown."

	add("check_seen", "check whether something is on the screen", checkSeen, {
		"what": text("the thing", auto=computer.seenWhat), "asked": text("what the user asked for", auto=True),
	}, looks=True, title="Checking whether it is on the screen", tell=V)

	def findThing(task, words):
		found, _sure = computer.find(computer.wanted(words), THINGS)
		if not found:
			raise tools.ToolError(computer.nothingFound(words))
		task.things = found
		return computer.foundText(found)

	add("find_thing", "find what the user wants opened by its name", findThing,
		{"words": text("the name", auto=computer.wanted)}, looks=True, title="Finding what to open")

	def openThing(task, thing, asked):
		item = next(one for one in task.things if one["id"] == thing)
		state.setdefault("opened", []).append(item["target"])
		return f"Opened {item['name']}."

	add("open_thing", "open one thing found by find_thing", openThing,
		{"thing": text("the id"), "asked": text("what the user asked for", auto=True)},
		changes=True, before="find_thing", title="Opening it", tell=V)
	add("recycle_bin", "say what the Recycle Bin holds", lambda task: computer.binText(*state.get("bin", (0, 0))),
		looks=True, title="Checking the Recycle Bin", tell=V)

	def emptyIt(task, asked):
		state["emptied"] = True
		return "Emptied the Recycle Bin: 3 items, 5 MB, deleted for good."

	add("empty_recycle_bin", "empty the Recycle Bin", emptyIt, asked, changes=True, title="Emptying the Recycle Bin", tell=V)

	def volume(task, asked):
		wish = computer.volumeOf(asked)
		new, _held = computer.volumeNew(state.get("volume", 40), wish)
		old, state["volume"] = state.get("volume", 40), new
		return f"The computer's volume was {old} percent and is now {new} percent."

	add("system_volume", "the volume of the computer itself", volume, asked, changes=True, title="Working the computer's volume", tell=V)

	def listWindows(task, about):
		task.windows = state.get("windows", WINDOWS)
		return computer.windowsText(task.windows)

	add("list_windows", "list the windows that are open", listWindows, {"about": text("what the user asked for", auto=True)},
		looks=True, title="Listing the open windows")

	def windowAction(task, window, action, asked):
		meant = computer.windowsMeant(asked, task.windows)
		state.setdefault("windowed", []).append((action, meant[0]["title"] if len(meant) == 1 else window))
		return f"Closed the window {meant[0]['title'] if len(meant) == 1 else window}."

	add("window_action", "switch to, close, minimize, maximize or restore a window", windowAction, {
		"window": text("the window"), "action": text("what", enum=computer.WINDOW_ACTIONS, auto=computer.windowActionOf),
		"asked": text("what the user asked for", auto=True),
	}, changes=True, before="list_windows", title="Working the window", tell=V)

	def webOpen(task, address, asked):
		state.setdefault("web", []).append((address, computer.browserOf(asked)))
		return "Opened the web page Inbox (3) - Gmail."

	add("web_open", "open a web address", webOpen, {
		"address": text("the address", auto=lambda part: re.search(r"[a-z0-9-]+\.[a-z]{2,}", part.lower()).group(0)),
		"asked": text("what the user asked for", auto=True)}, title="Opening the web page", tell=V)
	add("read_page", "read the web page", lambda task, about: "From the web page Inbox (3) - Gmail:\nYou have 3 unread emails.",
		{"about": text("the question", auto=True)}, looks=True, title="Reading the web page", tell=V)
	add("find_setting", "find an NVDA setting", lambda task, words: "speech.rate: speech: rate. Now: 50. Allowed: a number from 0 to 100.",
		{"words": text("keywords", auto=True)}, looks=True, title="Finding the setting")
	add("look_up", "ask NVDA, the program, the window and Windows", lambda task, question: "From NVDA: nothing.",
		{"question": text("the question", auto=True)}, looks=True, title="Asking")
	add("remember", "keep something", lambda task, fact, asked: state.setdefault("kept", []).append(fact) or "Kept.",
		{"fact": text("the fact", auto=True), "asked": text("asked", auto=True)}, title="Remembering", tell=V)
	add(tools.ANSWER, "tell the user the result", lambda task: "")
	return reg


class Scripted:
	"""A model that chooses what the test says for each part, and the first allowed answer in a form."""

	def __init__(self, choices):
		self.choices = choices
		self.chosen = []  # (the part, how many kinds it was offered)
		self.forms = 0

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False}

	def chat(self, role, messages, maxTokens, onText=None, cancel=None, options=None, raw=False, info=None, context=None):
		system, user = messages[0]["content"], messages[1]["content"]
		schema = options["response_format"]["json_schema"]["schema"]["properties"]
		if "parts" in schema:
			raise AssertionError("the model was asked to split: " + user)
		if "choice" in schema:
			part = re.search(r'The user asked: "(.*?)"\n', user).group(1)
			offered = schema["choice"]["enum"]
			self.chosen.append((part, len(offered)))
			wanted = self.choices[part]
			if isinstance(wanted, list):
				wanted = wanted.pop(0) if len(wanted) > 1 else wanted[0]
			assert wanted in offered, (part, wanted, offered)
			return json.dumps({"choice": wanted})
		self.forms += 1
		return json.dumps({name: (spec.get("enum") or ["x"])[0] for name, spec in schema.items()})


def run(request, choices=None, facts=NOWHERE, **state):
	state = dict(state)
	asked = []
	model = Scripted(choices or {})
	orch = orchestrator.Orchestrator(model, makeRegistry(state), lambda question, options: asked.append(question) or 0,
		lambda: "Program: explorer. Window title: Program Manager.", None)
	orch.facts = lambda: facts
	task = orch.run(taskModule.Task(request))
	return task, state, model, asked


def statuses(task):
	return [(step.tool, step.status) for step in task.steps]


# 1. The request that failed for the owner. The Recycle Bin is on the screen: it is opened, by its name through
#    Windows, and the user is told what was done, not which key to press.
task, state, model, asked = run(
	"first, look at my screen. If you see recycle bin, open it.", {"Look at my screen": "describe"},
	screen=["Firefox", "Recycle Bin", "Steam"])
assert task.state == taskModule.DONE, task.log
assert statuses(task) == [("look", "done"), ("check_seen", "done"), ("find_thing", "done"), ("open_thing", "done"), ("answer", "done")]
assert state["checked"] == ["recycle bin"] and state["opened"] == ["shell:RecycleBinFolder"], state
assert task.answer == (
	"The desktop shows a grid of icons. Yes: recycle bin is on the screen: its name is in the text that is shown. "
	"Opened Recycle Bin."), task.answer
# Only the looking was put to the model; what to open was said by the words, and the only thing found was taken.
assert [part for part, _count in model.chosen] == ["Look at my screen"] * 2 and model.forms == 0, (model.chosen, model.forms)
assert task.steps[1].holds is True and task.steps[2].onlyIf is task.steps[1] and task.steps[0].onlyIf is None
# 2. The Recycle Bin is not on the screen: nothing is opened, and that is said as what it is, not as a failure.
task, state, model, asked = run(
	"first, look at my screen. If you see recycle bin, open it.", {"Look at my screen": "describe"}, screen=["Firefox", "Steam"])
assert task.state == taskModule.DONE and "opened" not in state
assert statuses(task)[1:4] == [("check_seen", "done"), ("find_thing", "not needed"), ("open_thing", "not needed")], statuses(task)
assert task.answer == (
	"The desktop shows a grid of icons. No: recycle bin is not on the screen: its name is not in the text that is shown. "
	"So this was not done: Open recycle bin."), task.answer
assert "could not be done" not in task.answer
# 3. The second request that failed: answered from Windows' own count, and no model is asked anything.
task, state, model, asked = run("check and see if my recycle bin needs to be emptied or not.", bin=(12, 5 << 20))
assert statuses(task) == [("recycle_bin", "done"), ("answer", "done")] and not model.chosen and not model.forms
assert task.answer.startswith("The Recycle Bin holds 12 items, 5 MB in all. It does not need emptying for room"), task.answer
assert any("your words say it: check the Recycle Bin" in entry for _t, _kind, entry in task.log), task.log
# 4. A model that sends a part about the Recycle Bin to remembering is corrected: nothing is kept as a memory.
task, state, model, asked = run("Is my recycle bin getting full or what?", bin=(0, 0))
assert statuses(task)[0] == ("recycle_bin", "done") and "kept" not in state
assert task.answer == "The Recycle Bin is empty. There is nothing to empty."
# 5. The request of five things: split by plain rules, each thing with its own steps, in order.
long = ("Go into my windows settings, turn down my system volume, close windows settings, then go to gmail.com in my "
	"google chrome and tell me how many emails I have.")
task, state, model, asked = run(long, {
	"Close windows settings": "window", "Go to gmail.com in my google chrome": "open_website",
	"Tell me how many emails I have": "web_page"}, volume=40)
assert task.state == taskModule.DONE, task.log
assert [step.tool for step in task.steps] == [
	"find_thing", "open_thing", "system_volume", "list_windows", "window_action", "web_open", "read_page", "answer"], task.steps
assert all(step.status == taskModule.STEP_DONE for step in task.steps), statuses(task)
assert state["opened"] == ["ms-settings:"] and state["volume"] == 30, state
assert state["windowed"] == [(computer.CLOSE, "Settings")], state
assert state["web"] == [("gmail.com", ("chrome.exe", "Google Chrome"))], state
assert task.answer == (
	"Opened Windows Settings. The computer's volume was 40 percent and is now 30 percent. Closed the window Settings. "
	"Opened the web page Inbox (3) - Gmail. From the web page Inbox (3) - Gmail: You have 3 unread emails."), task.answer
# Opening Settings and the volume were said by the words, and what is asked right after a web page was opened is
# asked of that page; only the two things in between were put to the models, each with a short list.
asked_ = [part for part, _count in model.chosen]
assert asked_ == ["Close windows settings"] * 2 + ["Go to gmail.com in my google chrome"] * 2, asked_
assert planner.decided("Tell me how many emails I have", makeRegistry({}), "open_website") == "web_page"
assert planner.decided("Tell me how many emails I have", makeRegistry({})) is None
# A named control right after a click in the program is decided by plain code too, unless a word is NVDA's own.
assert planner.decided("Turn the volume up a bit", reg10 := makeRegistry({}), "click") is None  # no set_control tool here
assert planner._NVDAS_OWN.search("Turn off the typing echo") and not planner._NVDAS_OWN.search("Turn the equalizer down")
assert all(count < 30 for _part, count in model.chosen), model.chosen
assert any(entry.startswith("Offered for this:") for _t, kind, entry in task.log if kind == taskModule.DETAIL)
# 6. Something that depends on the Recycle Bin: emptied only when something is in it.
task, state, model, asked = run("If my recycle bin is not empty, empty it.", bin=(3, 5 << 20))
assert statuses(task) == [("recycle_bin", "done"), ("empty_recycle_bin", "done"), ("answer", "done")] and state.get("emptied")
assert task.answer.endswith("Emptied the Recycle Bin: 3 items, 5 MB, deleted for good."), task.answer
task, state, model, asked = run("If my recycle bin is not empty, empty it.", bin=(0, 0))
assert statuses(task)[1] == ("empty_recycle_bin", "not needed") and not state.get("emptied")
assert task.answer == "The Recycle Bin is empty. There is nothing to empty. So this was not done: Empty the recycle bin.", task.answer
# Only to be told: the check's own answer is all, and there is nothing that was "not done".
task, state, model, asked = run("If the recycle bin needs emptying, tell me.", bin=(300, 3 << 30))
assert statuses(task) == [("recycle_bin", "done"), ("answer", "done")] and "worth emptying" in task.answer
# 7. Something that depends on a window being open.
task, state, model, asked = run("If notepad is open, close it.", {"Close notepad": "window"})
assert [step.tool for step in task.steps] == ["list_windows", "list_windows", "window_action", "answer"]
assert state["windowed"] == [(computer.CLOSE, "notes.txt - Notepad")] and task.answer.startswith("A window of notepad is open."), task.answer
task, state, model, asked = run("If firefox is open, close it.", {"Close firefox": "window"})
assert "windowed" not in state and task.answer == "No window of firefox is open. So this was not done: Close firefox.", task.answer
# 8. A check that could not be made leaves what depends on it undone, and says that it could not be done.
task, state, model, asked = run("If you see recycle bin, open it.", screen=["Recycle Bin"])
reg = makeRegistry({})
reg.add(tools.Tool("check_seen", "check", lambda task, what, asked: (_ for _ in ()).throw(tools.ToolError("No picture.")),
	{"what": text("the thing", auto=computer.seenWhat), "asked": text("asked", auto=True)}, looks=True, title="Checking"))
orch = orchestrator.Orchestrator(Scripted({}), reg, lambda question, options: orchestrator.SKIP, lambda: "", None)
task = orch.run(taskModule.Task("If you see recycle bin, open it."))
assert statuses(task)[:3] == [("check_seen", "skipped"), ("find_thing", "skipped"), ("open_thing", "skipped")], statuses(task)
assert "This could not be done" in task.answer, task.answer
# 9. Where nothing among what was offered fits, the model is offered everything, once.
model = Scripted({"Do the thing with the page": [planner.OTHER, "web_page"]})
choice = planner.classify(
	__import__("visionClaw.claw.llm", fromlist=["LLM"]).LLM(model, taskModule.Task("x")), "vision", "Do the thing with the page",
	"", makeRegistry({}), facts={})
assert choice == "web_page" and [count for _part, count in model.chosen][0] < [count for _part, count in model.chosen][1], model.chosen

# 10. The owner's request inside a program: four things in order, each with its own steps.
reg = makeRegistry({})
done = []
reg.add(tools.Tool("list_items", "list what can be clicked", lambda task, about: "2 items in the window:\n1. Settings button\n2. Play button",
	{"about": text("what is looked for", auto=True)}, looks=True, title="Listing what is there"))
reg.add(tools.Tool("click_item", "click one item", lambda task, item, action, asked: done.append(("click", item, action)) or f"Clicked {item}.", {
	"item": text("the item"), "action": text("what", enum=pointer.ACTIONS, auto=pointer.actionOf), "asked": text("asked", auto=True),
}, changes=True, before="list_items", title="Clicking the item", tell=V))
reg.add(tools.Tool("set_control", "set a named control", lambda task, asked: done.append(("set", controls.wish(asked)["name"], controls.wish(asked)["what"])) or f"Set {controls.wish(asked)['name']}.",
	{"asked": text("asked", auto=True)}, changes=True, title="Setting the control", tell=V))
model = Scripted({
	"Find and click the settings button in this inaccessible app": "click", "Turn the volume up a bit": "set_control",
	"Turn the equalizer down": "set_control", "Close settings": "window"})
orch = orchestrator.Orchestrator(model, reg, lambda question, options: 0, lambda: "Program: soundstudio.", None)
orch.facts = lambda: NOWHERE
task = orch.run(taskModule.Task(
	"find the settings button in this inaccessible app, then adjust the volume and turn it up a bit and turn the equalizer "
	"down, then close settings."))
assert task.state == taskModule.DONE, task.log
assert [step.tool for step in task.steps] == [
	"list_items", "click_item", "set_control", "set_control", "list_windows", "window_action", "answer"], task.steps
assert done == [("click", "Settings button", pointer.CLICK), ("set", "volume", controls.UP), ("set", "equalizer", controls.DOWN)], done
assert task.answer.startswith("Clicked Settings button. Set volume. Set equalizer."), task.answer

# --- The skills and the notes that go with all this ---

lib = skills.Skills(__import__("tempfile").mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
for request, slug in (
	("check and see if my recycle bin needs to be emptied or not", "work-the-computer"),
	("turn down my system volume", "work-the-computer"), ("how much disk space do I have left", "work-the-computer"),
	("rename the file budget to Budget 2026", "work-the-computer"), ("create a folder called Taxes in my documents", "work-the-computer"),
	("turn on my nvidia gpu for this program", "control-in-a-program"),
	("find the settings button in this inaccessible app", "control-in-a-program"),
):
	assert slug in [skill.slug for skill in lib.choose(request)], (request, [skill.slug for skill in lib.choose(request)])
for request in ("Make NVDA speak a little faster", "What is on my screen?", "open bbc.co.uk"):
	assert not {"work-the-computer", "control-in-a-program"} & {skill.slug for skill in lib.choose(request)}, request
# The notes answer questions about what VisionClaw does on the computer, and only those.
sections = [(title, body) for title, body, source in Knowledge().everything() if source == "visionclaw-computer"]
assert len(sections) == 11, len(sections)
for title, body in sections:
	assert len(body) <= 360 and (":" in title or "," in title), (title, len(body))
gate = lookup.NOTES["visionclaw-computer"][2]
for question in ("Can you empty my recycle bin?", "How do I check the recycle bin?", "Can VisionClaw open programs for me?",
		"How do I turn down the system volume?", "Can I ask for several things at once?", "What can you do?"):
	assert gate.search(question), question
for question in ("How do I read the title of this window?", "What is browse mode?", "How do I copy text?"):
	assert not gate.search(question), question

print("OK")
