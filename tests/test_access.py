# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The deep inspection and the fixes add-on, with plain Python.

Part 1 checks the plain-code parts: telling controls apart, the findings for a page and for a window, choosing
what to fix, and putting an add-on together from fixes.
Part 2 runs a real, generated fixes add-on against a stand-in for a web page as NVDA keeps it in browse mode,
and against a stand-in window. The stand-ins behave as NVDA 2026.3.1's source says NVDA behaves; whether the
real NVDA agrees is only shown by a run inside NVDA.
"""
import sys
import types

import harness  # noqa: F401
from pagestandin import Command, El, Info, Role, State, documentClass, feedPage, post
from visionClaw.claw import audit, fixes, fixmatch, microaddons

# ---------------------------------------------------------------------------------------------------------
# Stand-ins for the NVDA modules a fixes add-on imports. The stand-in web page is in pagestandin.py.
# ---------------------------------------------------------------------------------------------------------

spoken = []
sent = []
timers = []


def fresh():
	"""Stand-ins for the NVDA modules a fixes add-on imports."""
	names = ("api controlTypes globalPluginHandler speech textInfos textInfos.offsets ui wx logHandler scriptHandler "
		"virtualBuffers browseMode NVDAObjects mouseHandler winUser").split()
	modules = {name: types.ModuleType(name) for name in names}
	modules["controlTypes"].OutputReason = types.SimpleNamespace(QUICKNAV="quicknav", FOCUS="focus")
	modules["controlTypes"].Role = Role

	class Plugin:
		def __init__(self):
			self.started = True

		def terminate(self):
			self.started = False

	modules["globalPluginHandler"].GlobalPlugin = Plugin
	modules["speech"].speakTextInfo = lambda info, reason=None: spoken.append("read: " + " ".join(info.text.split()))
	modules["speech"].speakObject = lambda obj, reason=None: spoken.append("object: " + obj.name)
	textInfos = modules["textInfos"]
	textInfos.POSITION_ALL, textInfos.POSITION_FIRST, textInfos.POSITION_CARET, textInfos.UNIT_LINE = "all", "first", "caret", "line"
	textInfos.offsets = modules["textInfos.offsets"]
	textInfos.offsets.Offsets = lambda start, end: types.SimpleNamespace(start=start, end=end)
	modules["ui"].message = spoken.append
	modules["wx"].CallLater = lambda ms, fn, *args: timers.append((fn, args)) or types.SimpleNamespace(Stop=lambda: None)
	modules["logHandler"].log = types.SimpleNamespace(
		debugWarning=lambda *a, **k: None, error=lambda *a, **k: spoken.append("LOG ERROR " + str(a[0])))
	modules["scriptHandler"].script = lambda **kwargs: (lambda fn: (setattr(fn, "gesture", kwargs["gesture"]) or fn))
	modules["virtualBuffers"].VirtualBuffer = type("VirtualBuffer", (), {})
	modules["browseMode"].reportPassThrough = lambda document: spoken.append("browse mode")
	modules["NVDAObjects"].NVDAObject = type("NVDAObject", (), {"name": ""})
	sys.modules.update(modules)
	return modules


modules = fresh()


Document = documentClass(modules["virtualBuffers"].VirtualBuffer)


def nodesOf(document, chunk=100000):
	import importlib
	runtime = importlib.import_module("visionClaw.fixruntime")
	first, last = runtime.pageRange(document)
	chunks = [runtime.pageChunk(document, at, min(last, at + chunk)) for at in range(first, last, chunk)]
	return audit.joinChunks(chunks)


# ---------------------------------------------------------------------------------------------------------
# Part 1: plain code
# ---------------------------------------------------------------------------------------------------------

# 1. Websites and their sub-sites; file names; plain text.
assert fixmatch.hostOf("https://www.Example.com:8080/a/b?c#d") == "example.com"
assert fixmatch.sameSite("facebook.com", "https://m.facebook.com/home") and fixmatch.sameSite("facebook.com", "facebook.com")
assert not fixmatch.sameSite("facebook.com", "https://notfacebook.com/") and not fixmatch.sameSite("", "https://a.com")
assert fixmatch.fileOf("https://a.com/img/Close.SVG?v=2") == "close.svg" and fixmatch.fileOf("data:image/png;base64,AAAA") == ""
assert fixmatch.plainText("  Play (k)! ") == "play k"

# 2. Rules: every key must hold; a name fits whole or as the beginning, never a long text that mentions it.
button = {"role": "BUTTON", "name": "", "text": "Pause (k)", "cls": ["ytp-play-button", "big"], "tag": "button", "states": ["FOCUSABLE"]}
assert fixmatch.matches({"role": "BUTTON", "cls": ["ytp-play-button"]}, button)
assert fixmatch.matches({"role": ["LINK", "BUTTON"], "names": ["play", "pause"]}, button)
assert not fixmatch.matches({"role": "LINK"}, button) and not fixmatch.matches({"cls": ["ytp-play-button", "small"]}, button)
assert not fixmatch.matches({"names": ["pause"]}, dict(button, text="Press pause whenever you want to stop the film for a while"))
assert not fixmatch.matches({"role": "BUTTON", "unnamed": True}, button) and fixmatch.matches({"unnamed": True, "role": "BUTTON"}, dict(button, text=""))
assert not fixmatch.matches({"notRole": ["BUTTON"], "state": "FOCUSABLE"}, button)
inner = {"role": "ARTICLE", "up": {"role": "ARTICLE", "up": None}}
assert fixmatch.matches({"role": "ARTICLE"}, inner) and not fixmatch.matches({"role": "ARTICLE", "outer": True}, inner)

# 3. A page read in one go and in small stretches gives the same controls, each once, with its whole text.
document = Document(feedPage(), "https://www.example-feed.com/home")
whole, pieces = nodesOf(document), nodesOf(document, chunk=37)
assert len(whole) == len(list(document.root.walk())) == len(pieces), (len(whole), len(pieces))
assert [n["role"] for n in whole] == [n["role"] for n in pieces]
assert [n["text"] for n in whole if n["role"] in ("BUTTON", "LINK", "HEADING")] == [n["text"] for n in pieces if n["role"] in ("BUTTON", "LINK", "HEADING")]
assert whole[0]["role"] == "DOCUMENT" and whole[1]["up"] is whole[0] and whole[1]["text"] == "Home"
# Characters that count twice in NVDA's positions are counted twice here.
assert fixmatch.nodesFromFields(["\U0001F600a", Command("controlStart", {"role": Role.BUTTON}), "b", Command("controlEnd")])[0]["start"] == 3

# 4. Names that people wrote and names a tool made up; names from code.
assert audit.telling("btn-close") and audit.telling("icon_search") and not audit.telling("x1n2onr6")
assert not audit.telling("css-1dbjc4n") and not audit.telling("_a9zs")
assert audit.stableId("search-button") and not audit.stableId(":r1a:") and not audit.stableId("ember1234") and not audit.stableId("u_0_2_xy")
assert audit.codeName({"cls": ["btn", "btn-close"]}) == "close" and audit.codeName({"cls": ["btn", "btn-primary"]}) == ""
assert audit.codeName({"ident": "playPauseBtn"}) == "play pause" and audit.codeName({"src": "icon-search.svg"}) == "search"
assert audit.cleanName("\"Search.\"\nIt shows a magnifying glass") == "Search" and audit.cleanName("unknown") == ""
assert audit.cleanName("It is a button that opens the settings of the whole program") == ""

# 5. The inspection of the page: what is counted is what is there.
report = audit.auditPage(whole, title="My feed", site="example-feed.com", browser="chrome")
found = {finding.id: finding for finding in report.findings}
assert set(found) == {"unnamed", "clickable", "feed", "media"}, set(found)
# Twelve buttons have no name: close and search are named from the page's own code, the five share buttons
# too; the five with only made-up class names cannot be told apart, so no name is claimed for them.
unnamed = found["unnamed"]
assert unnamed.text.startswith("12 buttons have no name"), unnamed.text
assert "7 of them can be given a name; 5 cannot be told apart" in unnamed.text, unnamed.text
assert sorted(fix["label"] for fix in unnamed.fixes) == ["close", "search", "share"], unnamed.fixes
assert all(fix["kind"] == fixes.NAME for fix in unnamed.fixes) and not unnamed.look
# The clickable block with a link inside is not a problem: the link can be reached.
assert found["clickable"].text.startswith("2 things can be clicked"), found["clickable"].text
# Five posts; the comments inside them are not counted as posts.
assert "feed of 5 posts" in found["feed"].text and found["feed"].fixes[0]["rule"] == {"role": "ARTICLE", "outer": True}
# The player: its buttons under either of their names, and the time by its fixed id.
media = found["media"].fixes
assert [fix["label"] for fix in media] == ["Play or pause", "Mute", "the time"], media
assert media[2] == {"kind": "read", "rule": {"role": "SECTION", "ident": "player-time"}, "label": "the time"}
text = report.text()
assert text.startswith("Checked the web page My feed on example-feed.com, in chrome. It has 5 headings, 2 links, 19 buttons and 0 form fields.")
assert "Found 4 problems." in text and "VisionClaw can fix all of them with an add-on for the website example-feed.com" in text
assert len(text) < 1500, len(text)

# 6. What changed while watching is found by comparing two looks, and only for parts with something fixed.
# A running time is not one of them: spoken every few seconds it would never stop, so it gets a key that
# reads it instead. And of a part and the box around it, only the part counts, or it would be spoken twice.
def boxed():
	page = feedPage()
	page.content[-1] = El("SECTION", El("SECTION", "3 new messages", cls="inbox-count"), cls="inbox-box")
	return page


earlier, later = boxed(), boxed()
later.content[-1].content[0].content[0] = "4 new messages"
later.content[-5].content[0] = "0:44 / 3:05"
changed = audit.auditPage(nodesOf(Document(earlier, "https://example-feed.com/")), site="example-feed.com",
	later=nodesOf(Document(later, "https://example-feed.com/")))
change = next(finding for finding in changed.findings if finding.id == "changing")
assert change.text.startswith("1 part changed while VisionClaw watched"), change.text
assert change.fixes == [{"kind": fixes.WATCH, "rule": {"role": "SECTION", "cls": ["inbox-count"]}, "label": "inbox count"}], change.fixes

# 7. Text that is only a picture: lines read from the picture that the page does not have as text.
drawn = audit.auditPage(whole, site="example-feed.com", drawn=["Home", "Season two starts tonight", "Watch tonight premiere trailer", "Episode guide and cast list"])
assert any(finding.id == "drawn" and "About 3 lines" in finding.text for finding in drawn.findings)
assert not any(f.id == "drawn" for f in audit.auditPage(whole, site="a.com", drawn=["Home", "Open the menu", "Show more"]).findings)

# 8. A plain page with nothing wrong says so, without claiming more than was checked.
plainPage = Document(El("DOCUMENT", El("HEADING", "Title\n", level="1"), "Some words.\n", El("LINK", "A link\n")), "https://plain.org/")
assert audit.auditPage(nodesOf(plainPage), title="Plain", site="plain.org").text().endswith("That does not prove everything here is easy to use.")

# 9. Choosing what to fix: by number, by what it is about, or everything.
assert [f.id for f in audit.choose(report, "fix number 3")] == ["feed"]
assert [f.id for f in audit.choose(report, "fix the second one")] == ["clickable"]
assert [f.id for f in audit.choose(report, "give the buttons names")] == ["unnamed"]
assert [f.id for f in audit.choose(report, "fix the video player")] == ["media"]
assert len(audit.choose(report, "make this page accessible")) == 4 and len(audit.choose(report, "fix all of it")) == 4
assert len(audit.choose(report, "fix the accessibility problems of this video site")) == 4
try:
	audit.choose(report, "fix number 9")
	raise AssertionError("a number that is not there must be refused")
except ValueError as e:
	assert "No fixable problem has that number" in str(e)

# 10. A window NVDA cannot read is called what it is; a window with nameless buttons gets names by control id.
blind = audit.auditWindow([{"role": "WINDOW", "name": "Game", "states": []}, {"role": "PANE", "name": "", "states": []}], "Game", "game")
assert [f.id for f in blind.findings] == ["picture"] and "list what is in the window" in blind.findings[0].advice
controls = [
	{"role": "WINDOW", "name": "Player", "states": []},
	{"role": "BUTTON", "name": "", "states": ["FOCUSABLE"], "controlId": 1001, "windowClass": "Button"},
	{"role": "BUTTON", "name": "", "states": ["FOCUSABLE"], "autoId": "btnNextTrack"},
	{"role": "BUTTON", "name": "Stop", "states": ["FOCUSABLE"], "controlId": 1003, "windowClass": "Button"},
	{"role": "STATICTEXT", "name": "Track 4 of 12", "states": [], "controlId": 2000, "windowClass": "Static"},
]
window = audit.auditWindow(controls, "Player", "player")
named = next(f for f in window.findings if f.id == "unnamed")
assert named.fixes == [{"kind": "name", "rule": {"role": "BUTTON", "autoId": "btnNextTrack"}, "label": "next track"}], named.fixes
assert named.look[0]["rule"] == {"role": "BUTTON", "controlId": 1001, "windowClass": "Button"} and named.look[0]["kind"] == "button"
assert window.summary == "Checked the window Player of the program player. NVDA knows 5 controls in it, 3 that can be used and 3 with a name."

# 11. Keys: one spelling for comparing, only real hotkeys accepted, found in the user's words, free ones chosen.
assert fixes.normKey("Alt + NVDA+P") == fixes.normKey("nvda+alt+p") == "alt+nvda+p"
assert fixes.cleanKey("nvda+ALT+p") == "NVDA+alt+p" and fixes.cleanKey("p") == "" and fixes.cleanKey("NVDA+alt") == ""
assert fixes.cleanKey("NVDA+alt+p\"); import os") == "" and fixes.cleanKey("kb:NVDA+shift+f9") == "NVDA+shift+f9"
assert fixes.keyIn("make NVDA + Alt + P press the Play button") == "NVDA+alt+P" and fixes.keyIn("press Play for me") == ""
assert fixes.freeKeys(1, {"alt+nvda+1"}) == ["NVDA+alt+2"] and fixes.freeKeys(2, set()) == ["NVDA+alt+downArrow", "NVDA+alt+upArrow"]
assert fixes.freeKeys(2, {fixes.normKey(k) for pair in fixes._PAIR_KEYS for k in pair}) is None

# 12. Fixes are cleaned to plain data; a rule that fits everything, a bad kind or a missing key is refused.
for bad, why in (
	({"kind": "press", "rule": {"role": "BUTTON"}, "label": "Play", "keys": []}, "needs 1 hotkey"),
	({"kind": "press", "rule": {}, "label": "Play", "keys": ["NVDA+alt+1"]}, "Nothing tells this control apart"),
	({"kind": "explode", "rule": {"role": "BUTTON"}, "label": "x", "keys": []}, "is not a kind of fix"),
	({"kind": "name", "rule": {"role": "BUTTON", "cls": ["a"]}, "label": "", "keys": []}, "needs a few words"),
):
	try:
		fixes.clean(bad)
		raise AssertionError(bad)
	except ValueError as e:
		assert why in str(e), e
cleaned = fixes.clean({"kind": "name", "rule": {"role": "BUTTON", "cls": ["btn-close"], "evil": "__import__('os')", "outer": 1},
	"label": "  close  ", "keys": ["whatever"], "extra": 1})
assert cleaned == {"kind": "name", "rule": {"role": "BUTTON", "cls": ["btn-close"], "outer": True}, "label": "close", "keys": []}

# 13. All fixes of the page, with keys given by code; what the add-on does is said from its data.
scope = report.scope
chosen = [fixes.clean(dict(fix, keys=fix.get("keys") or ["NVDA+alt+0"] * {"jump": 2, "press": 1, "read": 1}.get(fix["kind"], 0)))
	for finding in report.findings for fix in finding.fixes]
for fix in chosen:
	fix["keys"] = []
assert fixes.giveKeys(chosen, {"alt+nvda+1"}) == []
jumps = [fix for fix in chosen if fix["kind"] == "jump"]
assert jumps[0]["keys"] == ["NVDA+alt+downArrow", "NVDA+alt+upArrow"] and jumps[1]["keys"] == ["NVDA+alt+pageDown", "NVDA+alt+pageUp"]
assert [fix["keys"] for fix in chosen if fix["kind"] in ("press", "read")] == [["NVDA+alt+2"], ["NVDA+alt+3"], ["NVDA+alt+4"]]
said = fixes.describe(scope, chosen)
assert said[0] == "It works only on the website example-feed.com, in any browser NVDA reads in browse mode."
assert "NVDA+alt+pageDown moves to the next post, and NVDA+alt+pageUp to the previous one." in said
assert "NVDA+alt+2 presses Play or pause, wherever you are." in said and "NVDA+alt+4 reads the time." in said
assert "Buttons without a name are called close." in said and said[-1] == "Everywhere else these keys do what they always do."

# 14. The add-on that is put together passes the same check as an add-on a model wrote, and its data can be
# read back from it, so more fixes can be added later.
source = fixes.build(scope, chosen)
assert microaddons.check(source) == [], microaddons.check(source)
assert fixes.isFixes(source) and not fixes.isFixes(microaddons.TEMPLATE) and fixes.parse(microaddons.TEMPLATE) is None
assert fixes.parse(source) == (scope, chosen)
keys = [key for key, _description in microaddons.gestures(source)]
assert "NVDA+alt+2" in keys and "NVDA+alt+pageUp" in keys and len(keys) == 7, keys
# A newer fix about the same thing replaces the older one, and takes over a key that was in use.
newer = fixes.clean({"kind": "press", "rule": {"role": "BUTTON", "names": ["like"]}, "label": "Like", "keys": ["NVDA+alt+2"]})
merged = fixes.merge(chosen, [newer])
assert len(merged) == len(chosen) and merged[-1] is newer and not any(f["label"] == "Play or pause" for f in merged)
# Words from a page or a model are only ever data in the add-on: they cannot become code.
nasty = fixes.clean({"kind": "press", "rule": {"role": "BUTTON", "names": ["x'] + [__import__('os').system('calc')] + ['"]},
	"label": "a\"); import os; os.system(\"calc", "keys": ["NVDA+alt+9"]})
nastySource = fixes.build(scope, [nasty])
assert microaddons.check(nastySource) == [] and fixes.parse(nastySource)[1] == [nasty]

# 14b. The name of a website or program is only ever letters, digits, dots and hyphens, wherever it is
# written. Two websites whose names would become the same folder name get names that differ.
assert fixes.scopeOf(site="Evil.com\nimport os\n#") == {"site": "evil.comimportos"}
assert fixes.scopeOf(app="note pad\n;x") == {"app": "notepadx"}
sneaky = fixes.build({"site": "evil.com\nimport os\n#"}, [newer])
assert "import os" not in sneaky and microaddons.check(sneaky) == [] and fixes.parse(sneaky)[0] == {"site": "evil.comimportos"}
one, two = fixes.scopeOf(site="my-site.com"), fixes.scopeOf(site="my.site.com")
assert microaddons.slug(fixes.addonName(one)) == microaddons.slug(fixes.addonName(two)) == "fixes_my_site_com"
assert microaddons.slug(fixes.addonName(one, True)) != microaddons.slug(fixes.addonName(two, True))
assert len(microaddons.slug(fixes.addonName(fixes.scopeOf(site="a" * 90 + ".com"), True))) <= 40

# ---------------------------------------------------------------------------------------------------------
# Part 2: the generated add-on at work
# ---------------------------------------------------------------------------------------------------------


def load(source):
	space = {"__name__": "visionClawAddon_test"}
	exec(compile(source, "plugin.py", "exec"), space)
	return space["GlobalPlugin"]()


class Gesture:
	def send(self):
		sent.append("passed on")


def press(plugin, key):
	for name in dir(plugin):
		method = getattr(plugin, name)
		if name.startswith("script_") and getattr(method, "gesture", "") == "kb:" + key:
			return method(Gesture())
	raise AssertionError("no such key: " + key)


plugin = load(source)
focus = types.SimpleNamespace(treeInterceptor=document, appModule=types.SimpleNamespace(appName="chrome"))
modules["api"].getFocusObject = lambda: focus
posts = [el for el in document.root.content if el.role is Role.ARTICLE]

# 15. From the top of the page, the next-post key goes post by post, skipping the comments inside posts, and
# says the first line of each. This works the same in small stretches of the page.
for chunkSize in (30000, 53):
	plugin._do.__func__.__globals__["CHUNK"] = chunkSize
	document.caret = 0
	del spoken[:]
	for expected in posts:
		press(plugin, "NVDA+alt+pageDown")
		assert document.caret == expected.start, (chunkSize, document.caret, expected.start)
	assert spoken == [f"read: Post {n} by someone" for n in range(1, 6)], spoken
	press(plugin, "NVDA+alt+pageDown")
	assert spoken[-1] == "No more post below. If the page loads more as you go, try again in a moment." and document.caret == posts[-1].start
	# And back up; from inside a post, "previous" goes to that post's own start first.
	press(plugin, "NVDA+alt+pageUp")
	assert document.caret == posts[-2].start
	document.caret = posts[2].start + 20
	press(plugin, "NVDA+alt+pageUp")
	assert document.caret == posts[2].start
	document.caret = 0
	press(plugin, "NVDA+alt+pageUp")
	assert spoken[-1] == "No post above."

# 16. More posts arrive, as on a page that loads while you scroll: the same key finds them.
document.caret = posts[-1].start
document.root.content.insert(document.root.content.index(posts[-1]) + 1, post(6))
document.root.lay(0)
press(plugin, "NVDA+alt+pageDown")
assert spoken[-1] == "read: Post 6 by someone", spoken[-1]

# 17. Pressing the player's button from anywhere on the page, under whichever name it has at the moment.
pause = next(el for el in document.root.walk() if el.attrs["class"] == "ytp-play-button")
press(plugin, "NVDA+alt+2")
assert pause.activated == 1 and spoken[-1] == "Play or pause"
pause.content[0] = "Play (k)"
document.root.lay(0)
press(plugin, "NVDA+alt+2")
assert pause.activated == 2
# Reading the time; and saying so when something is not on the page.
press(plugin, "NVDA+alt+4")
assert spoken[-1] == "the time: 0:41 / 3:05", spoken[-1]
pause.content[0] = "Something else"
document.root.lay(0)
press(plugin, "NVDA+alt+2")
assert pause.activated == 2 and spoken[-1] == "Play or pause is not on this page right now."

# 18. Names: once the user is on the site, NVDA's own reading of the page carries the names, in whatever it
# reads. Controls that have a name, and controls of another kind, are left alone.
assert Document.TextInfo is Info
plugin.event_gainFocus(focus, lambda: sent.append("event passed on"))
assert sent[-1] == "event passed on" and document.TextInfo is not Info and issubclass(document.TextInfo, Info)
fields = [c.field for c in document.makeTextInfo("all").getTextWithFields() if getattr(c, "command", "") == "controlStart"]
given = [(field.get("IAccessible2::attribute_class"), field["name"]) for field in fields if field.get("alwaysReportName")]
assert given.count(("btn btn-close", "close")) == 1 and given.count(("btn icon-share", "share")) == 6 and len(given) == 8, given
assert not any(field.get("name") for field in fields if field.get("IAccessible2::attribute_class") == "x1a2b3c4 x9zzz9")
plugin.event_gainFocus(focus, lambda: None)  # a second time changes nothing more
assert document.TextInfo.__mro__[1] is Info
# Outside browse mode NVDA asks the control itself: the control gets the name there too. NVDA only asks an
# add-on whose own class has the method, so it must be in the class of an add-on that gives names.
assert "chooseNVDAObjectOverlayClasses" in type(plugin).__dict__
bare = types.SimpleNamespace(windowClassName="Chrome_RenderWidgetHostHWND", role=Role.BUTTON, name="", states=set(),
	IA2Attributes={"class": "btn btn-close", "tag": "button"})
classes = []
plugin.chooseNVDAObjectOverlayClasses(bare, classes)
assert len(classes) == 1 and classes[0]().name == "" and classes[0]()._get_name() == "close"
classes = []
plugin.chooseNVDAObjectOverlayClasses(types.SimpleNamespace(windowClassName="Edit", role=Role.BUTTON, name="", IA2Attributes={}), classes)
assert classes == []

# 18b. Two fixes add-ons for one page, one for the site and one for a part of it: each gives the page its
# names once, however often the focus moves. Without this they would wrap each other again on every move.
subPage = Document(feedPage(), "https://mail.example-feed.com/inbox")
focus.treeInterceptor = subPage
other = load(fixes.build(fixes.scopeOf(site="mail.example-feed.com"), [fixes.clean(
	{"kind": "name", "rule": {"role": "BUTTON", "ident": "search-button"}, "label": "find mail", "keys": []})]))
for _round in range(6):
	plugin.event_gainFocus(focus, lambda: None)
	other.event_gainFocus(focus, lambda: None)
assert len([cls for cls in subPage.TextInfo.__mro__ if "_visionClawFixes" in cls.__dict__]) == 2, subPage.TextInfo.__mro__
named = [c.field["name"] for c in subPage.makeTextInfo("all").getTextWithFields()
	if getattr(c, "command", "") == "controlStart" and c.field.get("alwaysReportName")]
assert named.count("close") == 1 and named.count("share") == 5 and len(named) == 7, named
other.terminate()
focus.treeInterceptor = document

# 19. On any other website, and in any other program, every key is passed on untouched and nothing is named.
elsewhere = Document(feedPage(), "https://other-site.org/")
focus.treeInterceptor = elsewhere
del sent[:]
activatedBefore = pause.activated
press(plugin, "NVDA+alt+2")
press(plugin, "NVDA+alt+pageDown")
assert sent == ["passed on", "passed on"] and elsewhere.caret == 0 and pause.activated == activatedBefore
plugin.event_gainFocus(focus, lambda: None)
assert elsewhere.TextInfo is Info
focus.treeInterceptor = None
press(plugin, "NVDA+alt+4")
assert sent[-1] == "passed on"

# 20. Turning the add-on off takes the names out of the page again.
plugin.terminate()
assert document.TextInfo is Info and plugin.started is False

# 21. A fix that fails says so and never raises: an error in a fix must not reach NVDA.
focus.treeInterceptor = document
broken = load(source)
document._activatePosition = lambda info=None: 1 / 0
pause.content[0] = "Pause (k)"
document.root.lay(0)
press(broken, "NVDA+alt+2")
assert spoken[-1] == "This fix did not work here. The page or program may have changed.", spoken[-3:]

# 22. Being told when something changes: the first look says nothing; a change is said once.
watching = load(fixes.build(scope, [fixes.clean({"kind": "watch", "rule": {"role": "SECTION", "cls": ["inbox-count"]}, "label": "Inbox", "keys": []})]))
assert timers, "an add-on that watches starts its timer"
assert "chooseNVDAObjectOverlayClasses" not in type(watching).__dict__  # no names to give: NVDA is not slowed
inbox = next(el for el in document.root.walk() if el.attrs["class"] == "inbox-count")
del spoken[:]
watching._tick()
assert spoken == []
watching._tick()
inbox.content[0] = "4 new messages"
document.root.lay(0)
watching._tick()
watching._tick()
assert spoken == ["Inbox: 4 new messages"], spoken
focus.treeInterceptor = elsewhere
inbox.content[0] = "5 new messages"
watching._tick()
assert spoken == ["Inbox: 4 new messages"]  # nothing is said while the user is somewhere else
watching.terminate()

# 23. A program's window: keys that move between its controls, press one and read one; names by control id.


class Control:
	def __init__(self, role, name="", children=(), controlId=0, value="", focusable=True):
		self.role, self.name, self.children, self.windowControlID, self.value = getattr(Role, role), name, list(children), controlId, value
		self.states = {State.FOCUSABLE} if focusable else set()
		self.windowClassName = "Button" if role == "BUTTON" else "Static"
		self.appModule = types.SimpleNamespace(appName="player")
		self.pressed = self.focused = 0

	def doAction(self):
		self.pressed += 1

	def setFocus(self):
		self.focused += 1


stop, play, status = Control("BUTTON", "Stop", controlId=1003), Control("BUTTON", "", controlId=1001), Control("STATICTEXT", "Track 4 of 12", controlId=2000, focusable=False)
windowRoot = Control("WINDOW", "Player", [Control("PANE", "", [play, stop]), status])
appScope = fixes.scopeOf(app="player")
appFixes = [fixes.clean(fix) for fix in (
	{"kind": "name", "rule": {"role": "BUTTON", "controlId": 1001, "windowClass": "Button"}, "label": "Play", "keys": []},
	{"kind": "press", "rule": {"role": "BUTTON", "controlId": 1001}, "label": "Play", "keys": ["NVDA+alt+1"]},
	{"kind": "read", "rule": {"role": "STATICTEXT", "controlId": 2000}, "label": "Track", "keys": ["NVDA+alt+2"]},
	{"kind": "jump", "rule": {"role": "BUTTON"}, "label": "button", "keys": ["NVDA+alt+downArrow", "NVDA+alt+upArrow"]},
)]
appSource = fixes.build(appScope, appFixes)
assert microaddons.check(appSource) == [] and fixes.describe(appScope, appFixes)[0] == "It works only on the program player."
app = load(appSource)
modules["api"].getFocusObject = lambda: play
modules["api"].getForegroundObject = lambda: windowRoot
press(app, "NVDA+alt+1")
assert play.pressed == 1
press(app, "NVDA+alt+2")
assert spoken[-1] == "Track: Track 4 of 12"
press(app, "NVDA+alt+downArrow")
assert stop.focused == 1
press(app, "NVDA+alt+downArrow")
assert spoken[-1] == "No more button that way." or stop.focused == 2  # the focus stand-in does not move
classes = []
app.chooseNVDAObjectOverlayClasses(play, classes)
assert len(classes) == 1 and classes[0]()._get_name() == "Play"
classes = []
app.chooseNVDAObjectOverlayClasses(stop, classes)
assert classes == []
other = Control("BUTTON", "", controlId=1001)
other.appModule = types.SimpleNamespace(appName="notepad")
app.chooseNVDAObjectOverlayClasses(other, classes)
assert classes == []
modules["api"].getFocusObject = lambda: other
del sent[:]
press(app, "NVDA+alt+1")
assert sent == ["passed on"] and play.pressed == 1

print("OK")
