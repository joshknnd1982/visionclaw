# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The user put exactly where they asked to be (claw/placing.py), told where they are at the end of a request
(claw/landing.py), and offered help where a place tells NVDA little (claw/troubles.py). Plain Python: what the words ask,
which page and control fit, which item is most likely to help, the way there learned and read again, what is said at the
end of a request and when, what is trouble, when an offer is made, taken, refused and allowed again; and which job the
planner gives each request. The tool itself, against stand-ins for NVDA, is in tests/test_nvda_stub.py.

  python tests/test_placing.py
"""
import os
import tempfile

import harness  # noqa: F401
from visionClaw.claw import landing, placing, planner, skills, tools, troubles
from visionClaw.claw import orchestrator as orchestratorModule
from visionClaw.claw import task as taskModule

# 1. What the words ask: the window, the page by number or name, the kind of control, its label, which one, typing.
wish = placing.wish("put me on page two in the advanced dialog in the proxy edit field")
assert wish["window"] == "advanced" and wish["page"] == {"number": 2} and wish["kind"] == "field" and wish["label"] == "proxy", wish
assert wish["typing"] and not wish["best"]
wish = placing.wish("Put me in the edit field labelled Proxy server on page 2 of the Advanced dialog")
assert (wish["window"], wish["page"], wish["kind"], wish["label"]) == ("advanced", {"number": 2}, "field", "Proxy server"), wish
assert placing.wish("take me to the Connection tab")["page"] == {"name": "connection"}
assert placing.wish("take me to the third tab")["page"] == {"number": 3}
assert placing.wish("go to the last page of this dialog")["page"] == {"number": -1}
wish = placing.wish("move the focus to the Save button")
assert (wish["kind"], wish["label"]) == ("button", "save"), wish
assert placing.wish("put the cursor in the search box")["label"] == "search"
assert placing.wish("go to the second check box")["nth"] == 2 and placing.wish("go to the last button")["nth"] == -1
assert placing.wish("put me on the 'Enable logging' check box")["label"] == "Enable logging"
wish = placing.wish("put me in the Options window on the Audio page on the master volume slider")
assert (wish["window"], wish["page"], wish["kind"], wish["label"]) == ("options", {"name": "audio"}, "slider", "master volume"), wish
assert placing.wish("switch to the General tab and put me on the first combo box")["kind"] == "combo"
assert placing.wish("I want to be in the email field so I can type")["typing"]
assert placing.wish("put me somewhere useful in this window")["best"]
assert placing.wish("put me on the most useful control in this dialog")["best"]
# What is no place to be put: a question, a part of a page, a web address, a part of Windows, something to be typed or
# clicked besides, a field found by what stops its form, and a window alone with no place in it.
for said in ("where is the proxy field", "how do I get to the advanced tab", "jump to the comments section",
		"take me to the start menu", "take me to wikipedia.org", "type hello into the search field",
		"Put my focus in the first required field that I still need to complete.", "go to the Accessibility dialog",
		"go to the next heading", "click the OK button", "turn on the proxy", "what is the focused control",
		"put the search box in the top right corner, please explain where it is", "go to gmail"):
	assert placing.wish(said) is None, (said, placing.wish(said))

# 2. Which page: by number among the tabs in order, the last one, or by name; none where it is not there.
pages = ["General", "Connection", "Advanced"]
assert placing.pickPage(pages, {"number": 2}) == 1 and placing.pickPage(pages, {"number": -1}) == 2
assert placing.pickPage(pages, {"name": "advanced"}) == 2 and placing.pickPage(pages, {"number": 5}) is None
assert placing.pickPage(pages, {"name": "privacy"}) is None
# Which window: every telling word of the name is in its title.
assert placing.windowFits("Advanced Settings", "advanced") and not placing.windowFits("Network settings", "advanced")
assert placing.windowFits("anything", "") and placing.windowFits("anything", None)
# Which button opens it: the one whose label ends in three dots wins among equals.
assert placing.opener(["Advanced", "Advanced...", "OK"], "advanced") == 1
assert placing.opener(["OK", "Cancel"], "advanced") is None

# 3. Which controls fit: the kind and the label, the nth of the kind, a label of a control of another kind.
items = [{"label": "Name", "kind": "field"}, {"label": "Proxy server", "kind": "field"}, {"label": "Port", "kind": "field"},
	{"label": "Use a proxy", "kind": "check"}, {"label": "OK", "kind": "button"}, {"label": "Cancel", "kind": "button"}]
assert placing.pickControls(items, {"kind": "field", "label": "proxy server"}) == [1]
assert placing.pickControls(items, {"kind": "field", "label": "", "nth": 2}) == [1]
assert placing.pickControls(items, {"kind": "button", "label": "", "nth": -1}) == [5]
assert placing.pickControls(items, {"kind": "button", "label": ""}) == [4, 5]
# "The proxy box" is a check box here: the label is found among the other kinds when the kind said has none.
assert placing.pickControls(items, {"kind": "field", "label": "use a proxy"}) == [3]
assert placing.pickControls(items, {"kind": "slider", "label": "volume"}) == []

# 4. The most helpful item where none is named, by what a sighted person's eye goes to first, said in words.
ranked = placing.helpful(items + [{"label": "Delete", "kind": "button", "states": ["UNAVAILABLE"]}],
	{"words": "", "dialog": True})
assert ranked[0][0] == 4 and "usual way on" in ranked[0][1], ranked[:2]
assert 6 not in [index for index, _reason in ranked]  # an unavailable item is never chosen
assert placing.helpful(items, {"words": "set the port", "dialog": True})[0][0] == 2  # the words of the request first
assert placing.helpful(items, {"words": "", "typing": True})[0][0] == 0  # where to type, the first field
marked = [dict(item) for item in items]
marked[5]["marked"] = True
assert placing.helpful(marked, {"words": ""})[0][0] == 5  # what the program marks as current
game = [{"label": "Options", "kind": "button"}, {"label": "Continue", "kind": "button"}, {"label": "Quit", "kind": "button"}]
best = placing.helpful(game, {"words": "", "game": True})[0]
assert best[0] == 1 and "game usually goes on" in best[1], best
seen = [{"label": "Help", "kind": "button"}, {"label": "Sign up", "kind": "button", "large": True, "colourful": "blue"}]
best = placing.helpful(seen, {"words": ""})[0]
assert best[0] == 1 and "larger" in best[1], best
assert "green" in placing.helpful([{"label": "Help", "kind": "button"}, {"label": "Go", "kind": "button", "colourful": "green"}],
	{"words": ""})[0][1]

# 5. The way there, learned as a line and read again from it, or from a memory in the user's words.
line = placing.routeLine("Proxy server", "edit field", "Connection", "Advanced Settings")
assert line == 'The edit field "Proxy server" is on the page Connection of the window "Advanced Settings".', line
route = placing.routeFrom(["Something else entirely.", line], {"label": "proxy server"})
assert route == {"window": "Advanced Settings", "page": {"name": "Connection"}}, route
route = placing.routeFrom(["The proxy field is on page 2 of the advanced dialog"], {"label": "proxy"})
assert route == {"window": "advanced", "page": {"number": 2}}, route
assert placing.routeFrom([line], {"label": "port"}) is None and placing.routeFrom([line], {"label": ""}) is None

# 6. What the user asked for, said back in words.
assert placing.wantedText(placing.wish("put me on page two in the advanced dialog in the proxy edit field")) == (
	'the edit field "proxy" on page 2 in the advanced window')
assert placing.listText(["Host", "Port"], "field") == 'The edit fields there: "Host", "Port".'

# 7. Where the user is at the end of a request: said where the focus moved, where a look moved it, where a skill says
# so, and where the place tells NVDA almost nothing; nothing where nothing moved.
here = {"app": "notepad", "title": "notes.txt - Notepad", "focusRole": "EDITABLETEXT", "focusRoleText": "edit",
	"focusName": "Text editor", "browse": None, "named": 12}
dialog = {"app": "notepad", "title": "Save As", "windowRole": "DIALOG", "focusRole": "EDITABLETEXT",
	"focusRoleText": "edit", "focusName": "File name:", "focusValue": "notes.txt", "browse": None, "named": 30,
	"message": "Where do you want to save it?", "defaultButton": "Save"}
assert landing.sentence(here, here) == ""
said = landing.sentence(here, dialog)
assert said.startswith('You are on the edit "File name:" in the window "Save As" of notepad; it shows notes.txt.'), said
assert "A dialog came up. It says: Where do you want to save it?" in said and "Its default button, which Enter presses, is Save." in said
said = landing.sentence(here, dialog, landing.STAY)
assert said.startswith("While VisionClaw looked, the focus moved.") and 'Alt+Tab goes back to "notes.txt - Notepad".' in said, said
assert landing.sentence(here, here, landing.TOLD).startswith('You are on the edit "Text editor"')
assert landing.sentence(here, dialog, landing.MOVED, toldAlready=True) == ""
game = {"app": "mygame", "title": "My Game", "focusRole": "PANE", "focusName": "My Game", "named": 0}
said = landing.sentence(here, game)
assert "This window tells NVDA almost nothing. Press NVDA+Alt+O" in said and 'Alt+Tab goes back to "notes.txt - Notepad".' in said, said
# Lost is said even where a step said where the user is: the user is never left without the way on.
assert "almost nothing" in landing.sentence(here, game, toldAlready=True)
page = dict(here, app="firefox", title="Shop - Firefox", focusRole="DOCUMENT", focusRoleText="document", focusName="Shop", browse=True)
assert landing.sentence(here, page).endswith('of firefox, in browse mode.')
assert landing.sentence(page, dict(page, browse=False, focusRole="EDITABLETEXT", focusName="Search")).endswith("in focus mode.")
assert landing.sentence(here, dict(game, own=True)) == "" and landing.sentence(None, here) == ""
# Where VisionClaw's own window was still in front at the start, nothing is said unless the user is lost.
assert landing.sentence(dict(here, own=True), dialog) == "" and "almost nothing" in landing.sentence(dict(here, own=True), game)
assert landing.expected(["told"], True) == landing.TOLD and landing.expected([], True) == landing.STAY
assert landing.expected(["stay"], False) == landing.MOVED

# 8. The same at the end of a whole request: the orchestrator reads where the user is at the start and at the end.
registry = tools.Registry()
registry.add(tools.Tool("look", "looks", lambda task: "", looks=True))
registry.add(tools.Tool("press", "presses", lambda task: "", changes=True))
registry.add(tools.Tool("go_to_control", "puts", lambda task: ""))
runner = orchestratorModule.Orchestrator(None, registry, lambda question, choices: 0)
spots = [dialog]
runner.spot = lambda count=True: spots[0]


def landedAfter(toolNames, chosen=()):
	task = taskModule.Task("x")
	task.steps = [taskModule.Step(name, name) for name in toolNames]
	task.skills = list(chosen)
	task.spotBefore = here
	return runner._landed(task)


assert landedAfter(["press"]).startswith('You are on the edit "File name:"')
assert landedAfter(["look"]).startswith("While VisionClaw looked, the focus moved.")
assert landedAfter(["go_to_control"]) == ""  # the tool said where the user is itself
spots[0] = here
assert landedAfter(["press"]) == ""
lib = skills.Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
assert landedAfter(["look"], [lib.get("bearings")]).startswith('You are on the edit "Text editor"')
runner.spot = lambda count=True: (_ for _ in ()).throw(RuntimeError("NVDA did not answer"))
assert landedAfter(["press"]) == ""  # never a fault
runner.spot = lambda count=True: None
assert landedAfter(["press"]) == ""

# 9. Every built-in skill says where its job leaves the user, in a word VisionClaw knows.
for skill in lib.all():
	assert skill.lands in skills.LANDS, (skill.slug, skill.lands)
	assert f"lands: {skill.lands}" in skills.toText(skill)
assert lib.get("describe-photo").lands == "stay" and lib.get("put-me-there").lands == "told"
assert skills.check(skills.Skill("x", when="paint a wall", uses="describe", instructions="Do it.", lands="somewhere"),
	set(planner.RECIPES))
assert [skill.slug for skill in lib.choose("put me on page two of the advanced dialog in the proxy edit field")] == ["put-me-there"]
assert "offered-help" in [skill.slug for skill in lib.choose(troubles.requestFor(troubles.UNREADABLE, {}))]

# 10. Which job: being put somewhere is decided by plain code, kept whole, and not taken from other jobs.
for said in ("put me on page two in the advanced dialog in the proxy edit field", "move the focus to the Save button",
		"take me to the Connection tab", "put me on the most useful control in this dialog",
		"open the advanced dialog, go to page two and put me in the proxy field"):
	assert planner.hint(said) == "go_to_control", (said, planner.hint(said))
assert planner.split(None, None, "open the advanced dialog, go to page two and put me in the proxy field") == [
	"open the advanced dialog, go to page two and put me in the proxy field"]
for said, job in (("jump to the comments section", "go_to"), ("take me to the start menu", "windows_part"),
		("what is the focused control", "about_focus"),
		("Put my focus in the first required field that I still need to complete.", "form_trouble")):
	assert planner.hint(said) == job, (said, planner.hint(said))
for said in (troubles.requestFor(troubles.UNREADABLE, {}), troubles.requestFor(troubles.NO_FOCUS, {})):
	assert planner.hint(said) == "go_to_control" and placing.wish(said)["best"], said
assert planner.hint(troubles.requestFor(troubles.LOG_ERRORS, {})) == "nvda_log"

# 11. Trouble where the user is: a window that tells NVDA almost nothing, a dialog with nothing focused, a control without
# a label (not while object names are on), errors NVDA logged; nothing in VisionClaw's own windows, in a program the
# user is having made accessible, or where NVDA can say where the user is.
assert troubles.detect(game) == troubles.UNREADABLE
nothing = dict(dialog, focusRole="DIALOG", focusName="Save As", controls=6)
assert troubles.detect(nothing) == troubles.NO_FOCUS
button = dict(here, focusRole="BUTTON", focusRoleText="button", focusName="", focusStates=["FOCUSABLE", "FOCUSED"])
assert troubles.detect(button) == troubles.UNLABELLED and troubles.detect(button, namesOn=True) is None
assert troubles.detect(dict(button, focusDescription="Send the message")) is None  # the description is its label
assert troubles.detect(here) is None and troubles.detect(here, errors=3) == troubles.LOG_ERRORS
assert troubles.detect(dict(game, own=True)) is None and troubles.detect(game, followed=True) is None
assert troubles.detect({}) is None
said = troubles.offerText(troubles.UNREADABLE, game)
assert said == ("This window tells NVDA almost nothing. VisionClaw can read it from its picture and put you on the most useful "
	"item: press NVDA+Alt+Y. Ignore this to say no; press NVDA+Alt+Y twice for no more offers in mygame."), said
assert troubles.requestFor(troubles.UNLABELLED, button) == ""

# 12. When an offer is made: once for a place and a kind, not too soon after the last, never in a program the user said
# no to; taken once, and only while it is fresh; refused programs kept in a file and allowed again.
now = [1000.0]
folder = tempfile.mkdtemp(prefix="vcoffers-")
path = os.path.join(folder, troubles.FILE)
offers = troubles.Offers(path, clock=lambda: now[0])
assert offers.due(troubles.UNREADABLE, game)
offers.offered(troubles.UNREADABLE, game)
assert not offers.due(troubles.UNREADABLE, game)  # once for this place
other = dict(game, title="Options")
assert not offers.due(troubles.UNREADABLE, other)  # not too soon after the last
now[0] += troubles.QUIET_SECONDS
assert offers.due(troubles.UNREADABLE, other)
kind, facts = offers.take()
assert kind == troubles.UNREADABLE and facts["app"] == "mygame" and offers.take() is None  # taken once
offers.offered(troubles.UNREADABLE, other)
now[0] += troubles.TAKE_SECONDS + 1
assert offers.take() is None  # too old to take
offers.decline("MyGame")
assert troubles.Offers(path).declined == {"mygame"}  # kept in the file
now[0] += troubles.QUIET_SECONDS
assert not offers.due(troubles.NO_FOCUS, dict(nothing, app="mygame"))
assert offers.allow("mygame") and not offers.allow("mygame") and troubles.Offers(path).declined == set()
assert troubles.Offers(os.path.join(folder, "missing", troubles.FILE)).declined == set()
print("OK")
