# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - going through an installer, or any window that is worked by pressing one button page after page:
# "Uncheck any bundled toolbars in this installer and click Next until the installation starts", "keep pressing
# Continue until it asks for my name". Many installers are drawn by their own code and tell NVDA little; and even
# a readable one hides a box that installs something extra on its third page.
# Plain code reads from the user's own words which button is pressed again and again, what ends it, and what is
# to be unchecked. Then, page after page:
#   - the page is said in one line: its title, and its check boxes with what each is set to;
#   - a checked box that offers something extra (another program, a toolbar, a changed home page or search) is
#     unchecked and named, where the user asked for that; whether it took is looked at again and said;
#   - a box or button that accepts licence terms is never pressed without a question: accepting is the user's;
#   - the button that starts the installation, and one that finishes, is always asked about first;
#   - it stops when the button is gone, when what the user waits for shows, when a press changes nothing, when
#     another program comes to the front, and after MAX_PAGES pages; and it checks in on the way.
# No model is asked: an installer's pages are few and their words plain, and a wrong press installs something.
# No NVDA dependencies. The things of a window are guide.Thing objects with one more fact, `checked` (True, False
# or None where the thing is no check box); guidetools.py and wizardtools.py make them.

import re

from . import guide

MAX_PAGES = 12
CHECK_AFTER = 5
YES_NO = ("Yes, do it", "No, stop here")
_UNTIL = re.compile(r"\b(?:until|till|up to where|up to the point where|as far as)\b\s*(.*)$", re.IGNORECASE)
_PRESS = re.compile(
	r"\b(?:click|press|hit|push|choose|select|tap|keep (?:on )?(?:clicking|pressing|hitting|choosing)|go on (?:clicking|pressing))\s+"
	r"(?:on\s+)?(?:the\s+)?[\"'‘“]?([A-Za-z][\w ]{0,28}?)[\"'’”]?(?:\s+button)?\s+"
	r"(?:until|till|again and again|over and over|repeatedly|each time|every time|on every page|on each page|as often as|"
	r"as many times as|all the way|through)\b", re.IGNORECASE)
_SETUP = re.compile(
	r"\b(installer|install(?:ation)? wizard|setup wizard|set-?up program|setup|wizard|installation)\b", re.IGNORECASE)
_THROUGH = re.compile(
	r"\b(go|get|step|walk|click|run|work|take me|guide me|help me)\b.{0,20}\bthrough\b|\bfinish\b.{0,20}\b(install\w*|setup|wizard)\b|"
	r"\b(page after page|page by page|every page|each page)\b", re.IGNORECASE)
_UNCHECK = re.compile(
	r"\b(uncheck|untick|deselect|un-?select|clear|turn off|switch off|decline|refuse|reject|say no to|skip|opt out of|"
	r"get rid of|leave out|don'?t install|do not install|without)\s+(?:any|all|every|each|the|those|these)?\s*"
	r"(?:of the\s+)?(.+?)(?=\s+(?:in|on|from) (?:this|the|that)\b|\s+and\s+(?:then\s+)?(?:click|press|hit|keep|go|get|step|run|install|finish)\b|"
	r"\s+(?:until|till)\b|[,.;]|$)", re.IGNORECASE)
# A check box or a page that offers something the user did not come for.
_OFFER = re.compile(
	r"\b(toolbars?|offers?|also install|install .{0,40}(too|as well)|additional (software|programs?|offers?|components? from)|"
	r"recommended (software|offers?|programs?)|optional (software|offers?)|sponsor\w*|partner (software|offers?)|bundle\w*|"
	r"free (scan|trial)|try .{0,30} free|set .{0,40} as (my |the |your )?(default|home ?page|search)|make .{0,40} (my|the|your) (default|"
	r"home ?page)|default (browser|search)|search (engine|provider)|browser (extension|add-?on|plug-?in)|web ?companion|"
	r"anti-?virus|security (scan|suite)|driver updater|(pc|system) (cleaner|optimi[sz]er|speed-?up)|price comparison|shopping "
	r"(assistant|helper)|coupons?|vpn)\b", re.IGNORECASE)
# What the user's words call such offers, without naming one.
_ANY_OFFER = re.compile(
	r"\b(bundle\w*|promotional|promotions?|toolbars?|offers?|extras?|extra software|additional software|adware|bloatware|"
	r"junk|crapware|sponsored|optional|third[- ]party|unwanted|other programs?|other software)\b", re.IGNORECASE)
_TERMS = re.compile(
	r"\b(i (accept|agree)|accept (the|all|these)|agree to|agree with|licen[cs]e (agreement|terms)|terms (of|and)|eula|"
	r"end[- ]user licen[cs]e)\b", re.IGNORECASE)
_NOT = re.compile(r"\b(do not|don'?t|decline|reject|refuse|disagree|not accept)\b", re.IGNORECASE)
# The button that starts what cannot be taken back, and the one that ends it.
_START = re.compile(r"^\W*(install|install now|start install\w*|begin install\w*|start|upgrade|update|repair|remove|uninstall|extract|apply)\b", re.IGNORECASE)
_END = re.compile(r"^\W*(finish|done|close|exit|launch|restart now|reboot now|complete)\b", re.IGNORECASE)
_RUNNING = re.compile(r"\b(installing|copying files|extracting|please wait|in progress|downloading|configuring|setting up)\b", re.IGNORECASE)
_DECLINE = re.compile(r"^\W*(decline|no,? thanks?|no thank you|skip|not now|maybe later|don'?t install|do not install)\b", re.IGNORECASE)
_BOXES = ("check box", "switch", "toggle button")


def _plain(text):
	return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower().replace("&", "")).strip()


def wish(part):
	"""What the user's own words ask, or None when they do not ask for a button to be pressed page after page:
	{"press": the button's name ("Next" where an installer is named and no button is); "until": what ends it, in
	the user's words, or ""; "uncheck": the words for what is to be unchecked, or ""; "offers": whether offers of
	extra software are to be unchecked}."""
	text = " ".join(str(part or "").split())
	low = text.lower()
	if re.search(r"\bhow (do|can|would|should|could) (i|we|you|one)\b|\bhow to\b", low):
		return None
	pressed = _PRESS.search(text)
	setup = bool(_SETUP.search(text))
	until = _UNTIL.search(text)
	if pressed is None and not (setup and (until or _THROUGH.search(text) or _UNCHECK.search(text))):
		return None
	unchecked = _UNCHECK.search(text)
	what = unchecked.group(2).strip() if unchecked else ""
	return {
		"press": (pressed.group(1).strip() if pressed else "Next"),
		"until": (until.group(1).strip(" .!?") if until else ""),
		"uncheck": what,
		"offers": bool(what and _ANY_OFFER.search(what)) or bool(unchecked and not what)}


def isOffer(name, wished=None):
	"""Whether a check box offers something the user did not come for: by its own words, or by the words the user
	used for what to uncheck."""
	if _TERMS.search(name or ""):
		return False
	if _OFFER.search(name or ""):
		return True
	asked = [word for word in guide._stems((wished or {}).get("uncheck", "")) if not _ANY_OFFER.fullmatch(word)]
	return bool(asked) and bool(set(asked) & set(guide._stems(name)))


def isTerms(name):
	"""Whether a thing accepts licence terms: never pressed without a question. One that declines them is not."""
	return bool(_TERMS.search(name or "")) and not _NOT.search(name or "")


def isStart(name):
	return bool(_START.match(_plain(name)))


def isEnd(name):
	return bool(_END.match(_plain(name)))


def named(thing, press):
	"""Whether a thing is the button the user named: "Next" is "Next >" and "&Next", and no "Next steps" link."""
	name, wanted = _plain(thing.name), _plain(press)
	if not name or not wanted:
		return False
	return name == wanted or (name.startswith(wanted + " ") and len(name.split()) <= len(wanted.split()) + 1 and thing.kind == "button")


def _find(things, test):
	return next((thing for thing in things if thing.usable and test(thing)), None)


def running(things, title):
	"""Whether a page looks as if the installation is under way: its words say so."""
	return bool(_RUNNING.search(title or "")) or any(_RUNNING.search(thing.name or "") for thing in things)


def reached(until, things, title):
	"""Whether what the user waits for shows on this page: every telling word of it is in the page's words. What
	waits for the installation to start is told by the page's own words for that (running)."""
	if not until:
		return False
	if re.search(r"\binstall\w*\b", until, re.IGNORECASE) and re.search(r"\b(start|begin|run|under way|going)\w*\b", until, re.IGNORECASE):
		return running(things, title)
	wanted = set(guide._stems(until)) - {"it", "show", "appear", "come", "ask", "say", "page", "window", "button", "get", "reach", "see"}
	if not wanted:
		return False
	have = set(guide._stems(title or ""))
	for thing in things:
		have |= set(guide._stems(thing.name))
	return wanted <= have


def pageText(number, things, title):
	"""A page in one line: its number and title, and its check boxes with what each is set to."""
	boxes = [thing for thing in things if thing.kind in _BOXES and thing.name]
	said = f"Page {number}" + (f", {guide._clean(title)[:70]}" if guide._clean(title) else "")
	if boxes:
		listed = ", ".join(
			f"{thing.name} ({'checked' if thing.checked else 'not checked' if thing.checked is False else 'state not known'})"
			for thing in boxes[:6])
		said += f". Check boxes: {listed}" + (f", and {len(boxes) - 6} more" if len(boxes) > 6 else "")
	return said


def startQuestion(wished, title):
	"""Asked once before anything is pressed, whatever the settings say: going through an installer changes the
	computer."""
	what = f"Press {wished['press']} on page after page of this window" + (f", {guide._clean(title)[:60]}," if guide._clean(title) else "")
	end = f" until {wished['until']}" if wished["until"] else " until that button is gone"
	more = ""
	if wished["offers"]:
		more = " A checked box that offers extra software is unchecked on the way, and named."
	elif wished["uncheck"]:
		more = f" A checked box that is about {wished['uncheck']} is unchecked on the way, and named."
	return (
		f"{what}{end}?{more} VisionClaw says what each page is, never accepts licence terms without asking you, and asks "
		"before it presses a button that starts or finishes an installation.")


def walk(wished, look, press, ask, check=None, pause=None, pages=MAX_PAGES, checkAfter=CHECK_AFTER):
	"""Go through the pages. look() gives (the things in front, the window's title, the program's name); press(thing)
	presses one; ask(question, choices) is the user's choice as an index, or None. Returns (what was done, page by
	page, as one text; the names of what was pressed)."""
	check = check or (lambda: None)
	pause = pause or (lambda: None)
	said, pressed, quiet = [], [], 0
	things, title, program = look()
	for number in range(1, pages + 1):
		check()
		page = pageText(number, things, title)
		if reached(wished["until"], things, title):
			said.append(f"{page}. This is what you were waiting for, so VisionClaw stopped here. " + guide.hereText(things, title))
			break
		done = []
		# Offers first: a box that is checked and offers something extra is unchecked, where that was asked for.
		if wished["offers"] or wished["uncheck"]:
			for thing in [one for one in things if one.usable and one.kind in _BOXES and one.checked and isOffer(one.name, wished)]:
				check()
				press(thing)
				pressed.append(thing.name)
				pause()
				after, _title, _program = look()
				now = next((one for one in after if one.name == thing.name and one.kind == thing.kind), None)
				if now is not None and now.checked is False:
					done.append(f"unchecked {thing.name}")
				else:
					done.append(f"pressed {thing.name} to uncheck it, but it does not show as unchecked: check it yourself")
				things = after
		button = _find(things, lambda thing: named(thing, wished["press"]))
		terms = [thing for thing in things if thing.usable and isTerms(thing.name) and (thing.kind in _BOXES + ("radio button",) and not thing.checked)]
		agree = _find(things, lambda thing: thing.kind == "button" and isTerms(thing.name))
		if terms or (button is None and agree is not None):
			# Accepting terms is the user's own decision, always.
			name = (terms[0] if terms else agree).name
			if ask(
					f"{page}. This page asks you to accept terms: \"{name}\". Accepting them is your decision; VisionClaw has "
					"not read them to you. Accept and go on?", ["Yes, accept and go on", "No, stop here"]) != 0:
				said.append(f"{page}{_doneText(done)}. It asks you to accept terms, \"{name}\", and you did not, so VisionClaw stopped here.")
				break
			if terms:
				press(terms[0])
				pressed.append(terms[0].name)
				pause()
				things, title, _program = look()
				done.append(f"accepted \"{name}\", as you said")
				button = _find(things, lambda thing: named(thing, wished["press"]))
			if button is None and agree is not None:
				button = _find(things, lambda thing: thing.kind == "button" and isTerms(thing.name))
				done.append("you accepted the terms")
		if button is None:
			start = _find(things, lambda thing: thing.kind == "button" and isStart(thing.name))
			end = _find(things, lambda thing: thing.kind == "button" and isEnd(thing.name))
			decline = _find(things, lambda thing: thing.kind == "button" and _DECLINE.match(_plain(thing.name)))
			if start is not None:
				if ask(
						f"{page}. There is no {wished['press']} button here; the button is {start.name}. Pressing it starts what may "
						f"not be possible to take back. Press {start.name}?", list(YES_NO)) != 0:
					said.append(f"{page}{_doneText(done)}. The next button is {start.name}; you said no, so VisionClaw stopped before it.")
					break
				press(start)
				pressed.append(start.name)
				pause()
				after, titleAfter, _program = look()
				state = "The window now says that it is under way." if running(after, titleAfter) else guide.changed(things, after, title, titleAfter)[0]
				said.append(f"{page}{_doneText(done)}; pressed {start.name}, as you said. {state} VisionClaw stops here.")
				break
			here = guide.hereText(things, title)
			if decline is not None and any(_OFFER.search(text or "") for text in [title] + [thing.name for thing in things]):
				said.append(
					f"{page}{_doneText(done)}. This page seems to offer something extra, with a button {decline.name}. VisionClaw "
					f"did not press it, because it cannot be sure what it refuses. To refuse, say: click {decline.name}. {here}")
			elif end is not None:
				said.append(f"{page}{_doneText(done)}. There is no {wished['press']} button any more; the page has {end.name}, which VisionClaw did not press. {here}")
			else:
				said.append(f"{page}{_doneText(done)}. There is no {wished['press']} button here that can be pressed, so VisionClaw stopped. {here}")
			break
		press(button)
		pressed.append(button.name)
		pause()
		check()
		after, titleAfter, programAfter = look()
		said.append(f"{page}{_doneText(done)}; pressed {button.name}.")
		if guide._clean(programAfter).lower() != guide._clean(program).lower():
			said.append(
				f"Another program is in front now, {programAfter or 'not known'}. It may be Windows asking whether this program "
				"may change the computer, which only you can answer. VisionClaw stops here; ask again when the installer is "
				"in front.")
			break
		same = guide._clean(titleAfter) == guide._clean(title) and [thing.name for thing in after] == [thing.name for thing in things]
		quiet = quiet + 1 if same else 0
		things, title = after, titleAfter
		if quiet >= 2:
			said.append(
				f"Pressing {button.name} twice changed nothing, so VisionClaw stopped. The page may want something filled in "
				"or chosen first. " + guide.hereText(things, title))
			break
		if number == pages:
			said.append(f"That was {pages} pages, the most VisionClaw goes through in one go. " + guide.hereText(things, title))
			break
		if number % checkAfter == 0 and ask(f"That was {number} pages. Go on pressing {wished['press']}?", ["Yes, go on", "No, stop here"]) != 0:
			said.append("Stopped there, as you said. " + guide.hereText(things, title))
			break
	return " ".join(said), pressed


def _doneText(done):
	return (": " + "; ".join(done)) if done else ""


NO_WISH = (
	"The request does not say which button to press page after page. Say it like this: click Next until the "
	"installation starts.")
