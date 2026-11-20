# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the user put exactly where they asked to be, and checked at every step (claw/placing.py reads the words).
# "Put me on page two of the Advanced dialog, in the Proxy edit field": the window is found or opened, then the page,
# then the control; after each step what NVDA reports is read again, and the next step is taken only where the last
# one really landed. The user is never left somewhere they did not ask for without being told where they are, and how
# to get on from there. Four places, the surest first:
#   1. a web page in browse mode: NVDA's own quick navigation items. A field the user wants to type in is activated the
#      way NVDA's Enter does (focus mode in the field); anything else gets NVDA's reading position, as quick navigation
#      moves it, so that nothing is pressed. Read from NVDA 2026.3.1's browseMode.py: TextInfoQuickNavItem.activate calls
#      _activatePosition, which for an editable object sets the focus and passThrough (focus mode), and for a button
#      presses it (_activateNVDAObject); moveTo leaves focus mode and sets the selection.
#   2. a window NVDA knows: its controls by kind and label, on the page of its tabs or of a list of categories, found
#      on another page where the user named none, or by the text that labels a field without a name of its own;
#   3. a window NVDA cannot read, or a game: the window's picture, read by VisionClaw's overlay, which is then opened
#      with its cursor on the item, so that the arrow keys and Enter work it; said to be read from a picture;
#   4. where nothing fits, the user is told what there is and stays where they are.
# The focus is put with focustools.focusOn and checked; only a field, a list, a tree or a combo box is ever clicked to
# take the focus, because a click there changes nothing, while a click on a button would press it.
# What is learned: where a control was found is written on the program's learning scratchpad by plain code, and read
# again next time with what the user asked VisionClaw to remember.

import time

import addonHandler
import api
import config

from . import computertools, controltools, fixruntime, focustools, mousetools, webtools
from .claw import colours, debuglog, focus as focusWords, placing, planning
from .claw.llm import uncut
from .claw.tools import VERBATIM, ToolError

addonHandler.initTranslation()

SETTLE = 0.45
WINDOW_SECONDS = 3.0
OVERLAY_SECONDS = 6.0
# How many controls the user chooses among in one question.
MAX_ASKED = 9
# A window with fewer controls NVDA can name than this tells NVDA almost nothing (also claw/landing.py).
FEW_NAMED = 3
# The roles of what labels a field that has no name of its own.
_LABELS = ("STATICTEXT", "LABEL")
# How a list of categories that stands for pages is called (NVDA's own settings window has one).
_CATEGORY_WORDS = ("categor", "page", "section", "setting", "option")


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


def _kindOfNode(node):
	role = node.get("role") or ""
	kind = placing.kindOf(role)
	# A document is a field only where it can be typed in; most are the frame of a page or a viewer.
	if role in ("DOCUMENT", "TERMINAL") and "EDITABLE" not in (node.get("states") or ()):
		return ""
	return kind


def controlsHere():
	"""The controls of the window in front that can be worked, in reading order, as plain items: {"label", "kind",
	"role", "roleText", "states", "value", "obj"}; a field without a name of its own gets the text that labels it, which
	is said to be so. Main thread."""
	nodes = controltools._nodes()
	items, lastText = [], ""
	for node in nodes:
		role = node.get("role") or ""
		if role in _LABELS:
			lastText = controltools._label(node)
			continue
		kind = _kindOfNode(node)
		if not kind:
			continue
		obj = node["obj"]
		label = controltools._label(node)
		byText = False
		if not label and kind in placing.CLICK_SAFE and lastText:
			label, byText = lastText, True
		items.append({"label": label, "kind": kind, "role": role, "roleText": _safe(lambda: obj.role.displayString, "") or "",
			"states": list(node.get("states") or ()), "value": node.get("value") or "", "obj": obj, "byText": byText})
		lastText = ""
	return items


def pagesHere():
	"""The pages of the window in front: its tabs, or the items of a list of categories at its side, as NVDA's own
	settings have. [(name, object, shown)], and the kind ("tab" or "category"). Main thread."""
	tabs = controltools.pagesOf()
	if tabs:
		return tabs, "tab"
	nodes = controltools._nodes()
	for node in nodes:
		if node.get("role") != "LIST" or not any(word in (controltools._label(node) or "").lower() for word in _CATEGORY_WORDS):
			continue
		items = [(controltools._label(child), child["obj"], "SELECTED" in (child.get("states") or ()))
			for child in nodes if child.get("up") is node and child.get("role") == "LISTITEM" and controltools._label(child)]
		if items:
			return items, "category"
	return [], ""


def showPage(obj, kind):
	"""Show a page: a tab is pressed with its own action, a category is given the focus, which selects it. Main thread."""
	if kind == "category":
		obj.setFocus()
		return
	fixruntime.pressObject(obj)


def spot(count=True):
	"""Where the user is, as plain facts (claw/landing.py, claw/troubles.py): the program, the window's title and kind,
	the focused control's kind, name, states and value, whether a web page is in browse mode (True), in focus mode (False)
	or none (None), and, where count is True, how many controls of the window NVDA can name. Never a fault. Main thread."""
	facts = {}
	try:
		fg = api.getForegroundObject()
		focus = api.getFocusObject()
		facts.update({
			"app": _safe(lambda: fg.appModule.appName, "") or "",
			"title": " ".join(str(_safe(lambda: fg.name, "") or "").split()),
			"windowRole": _safe(lambda: fg.role.name, "") or "",
			"focusRole": _safe(lambda: focus.role.name, "") or "",
			"focusRoleText": _safe(lambda: focus.role.displayString, "") or "",
			"focusName": " ".join(str(_safe(lambda: focus.name, "") or "").split()),
			"focusStates": [getattr(state, "name", str(state)) for state in (_safe(lambda: focus.states, ()) or ())],
			"focusValue": " ".join(str(_safe(lambda: focus.value, "") or "").split())[:80],
			"focusDescription": " ".join(str(_safe(lambda: focus.description, "") or "").split())[:150],
		})
		document = webtools.page()
		facts["browse"] = None if document is None else not bool(getattr(document, "passThrough", False))
		if document is not None:
			facts["pageTitle"] = webtools.title(document)
		from . import guidetools
		facts["own"] = bool(_safe(guidetools.ownWindow, False))
		if count:
			named = controlsCount = 0
			for node in fixruntime.windowNodes(fg, limit=150, seconds=0.3):
				if node.get("name"):
					named += 1
				if _kindOfNode(node):
					controlsCount += 1
			facts["named"], facts["controls"] = named, controlsCount
			# What a sighted person sees at once in a dialog: its default button, and the text of its message.
			if facts["windowRole"] == "DIALOG":
				texts, default = [], ""
				for node in fixruntime.windowNodes(fg, limit=60, seconds=0.2):
					if node.get("role") in _LABELS and node.get("name") and len(texts) < 2:
						texts.append(node["name"])
					if "DEFAULT" in (node.get("states") or ()) and node.get("name") and not default:
						default = node["name"]
				facts["message"], facts["defaultButton"] = " ".join(texts)[:300], default
	except Exception as e:
		debuglog.error("place", "Where the user is could not be read", e)
	return facts


def placeContext():
	"""What kind of place the window in front is, for choosing the most helpful item: a game, a dialog. Main thread."""
	fg = api.getForegroundObject()
	app = _safe(lambda: fg.appModule.appName, "") or ""
	where = planning.place(app, _safe(lambda: fg.name, "") or "", _safe(lambda: fg.windowClassName, "") or "")
	return {"game": "game" in where, "dialog": _safe(lambda: fg.role.name, "") == "DIALOG" or "dialog" in where}


def _isOverlay(focus):
	try:
		from . import overlay
		return isinstance(focus, overlay.OverlayDocument)
	except Exception:
		return False


def register(add, plugin, text, onMain, confirm, screen):
	"""Add the tool that puts the user where they ask to be. The first five arguments are the helpers of nvdatools.build."""

	def cancelOf(task):
		return getattr(task, "cancel", None)

	def whereNow():
		now = focustools.focusName(onMain)
		app, title, _fg, _focus = onMain(screen.where)
		return (f"the {now}" if now else "an object NVDA cannot name") + (f", in the window \"{title}\"" if title else "") + (
			f" of {app}" if app and app != "?" else "")

	def choose(task, labels, question):
		"""The user picks one of several that fit: the index, or None for none of them. Asked whatever the settings say:
		being put on the wrong control is worse than a question."""
		shown = labels[:MAX_ASKED]
		# Translators: The last choice when VisionClaw asks which of several controls the user means.
		chosen = plugin.clawAsk(question, shown + [_("None of these")])
		if chosen is None or chosen >= len(shown):
			return None
		return chosen

	# --- 1. The window ---

	def toWindow(task, name):
		"""(True, sentence) when the window in front is the one named, after it was brought to the front or opened
		where needed; (False, sentence) when it could not be, and nothing else is done."""
		app, title, _fg, _focus = onMain(screen.where)
		if placing.windowFits(title, name):
			return True, ""
		for window in _safe(computertools.openWindows, []) or []:
			if not window.get("front") and placing.windowFits(window.get("title"), name):
				task.check()
				computertools.focusWindow(window["hwnd"])
				_app, now, _fg, _focus = onMain(screen.where)
				if placing.windowFits(now, name):
					return True, f"The window \"{now}\" was brought to the front."
				return False, f"The window \"{window['title']}\" is open, but Windows did not bring it to the front. You are on {whereNow()}."
		nodes = onMain(controltools._nodes)
		openers = [node for node in nodes if node.get("role") in ("BUTTON", "MENUITEM", "LINK", "SPLITBUTTON", "MENUBUTTON")
			and controltools._label(node)]
		index = placing.opener([controltools._label(node) for node in openers], name)
		if index is None:
			return False, (
				f"No window called \"{name}\" is open, and the window in front, \"{title}\", has no button that opens it. "
				f"Nothing was changed, and you are still on {whereNow()}. Open that window, then ask again.")
		label = controltools._label(openers[index])
		# Translators: Asked before VisionClaw presses a button that opens a window. {label} is the button, {name} the window.
		confirm(_("Press {label} to open the {name} window?").format(label=label, name=name))
		onMain(fixruntime.pressObject, openers[index]["obj"])
		end = time.monotonic() + WINDOW_SECONDS
		now = title
		while time.monotonic() < end:
			task.check()
			time.sleep(0.15)
			_app, now, _fg, _focus = onMain(screen.where)
			if now != title and placing.windowFits(now, name):
				return True, f"{label} was pressed, and the window \"{now}\" opened."
		if now != title:
			return True, f"{label} was pressed, and the window \"{now}\" opened."
		return False, f"{label} was pressed, but no new window came up. You are on {whereNow()}."

	# --- 2. The page ---

	def toPage(task, page):
		"""(True, sentence, the page's name) once the page is shown; (False, sentence, "") where it is not."""
		pages, kind = onMain(pagesHere)
		names = [name for name, _obj, _shown in pages]
		index = placing.pickPage(names, page)
		if not pages:
			return False, "The window in front has no pages with tabs, and no list of pages VisionClaw can find.", ""
		if index is None:
			asked = f"page {page['number']}" if page.get("number") else f"the page {page.get('name')}"
			return False, (f"The window has no {asked}. Its pages are: " + ", ".join(names) + "."), ""
		name, obj, shown = pages[index]
		if shown:
			return True, "", name
		task.check()
		onMain(showPage, obj, kind)
		time.sleep(SETTLE)
		after, _kind = onMain(pagesHere)
		if any(n == name and isShown for n, _o, isShown in after):
			return True, f"The page {name} is shown.", name
		return False, f"VisionClaw pressed the page {name}, but the window does not show it as chosen.", ""

	def onOtherPages(task, found):
		"""The controls that fit on the other pages of the window, the first page that has them shown: (items, page)."""
		pages, kind = onMain(pagesHere)
		start = next((page for page in pages if page[2]), None)
		for name, obj, shown in pages:
			if shown:
				continue
			task.check()
			onMain(showPage, obj, kind)
			time.sleep(SETTLE)
			items = onMain(controlsHere)
			picks = placing.pickControls(items, found)
			if picks:
				return items, picks, name
		if start is not None and pages:
			onMain(showPage, start[1], kind)
			time.sleep(SETTLE)
		return [], [], ""

	# --- 3. The control ---

	def placeOn(task, item, where):
		"""Put the focus on a control NVDA knows and check it. Returns the sentence for the user."""
		obj, kind = item["obj"], item["kind"]
		said = item.get("roleText") or placing.KIND_SAID.get(kind, "control")
		label = item.get("label") or ""
		named = f"{said} \"{label}\"" if label else said
		landed = focustools.focusOn(obj, onMain, cancelOf(task))
		clicked = False
		if not landed and kind in placing.CLICK_SAFE:
			place = _safe(lambda: onMain(lambda: obj.location))
			if place and place.width > 0 and place.height > 0:
				# A click in a field, a list or a tree only puts the focus there. The mouse pointer is put back after it.
				old = mousetools.position()
				mousetools._onMain(lambda: mousetools.click(place.left + place.width // 2, place.top + place.height // 2))
				time.sleep(SETTLE)
				_safe(lambda: mousetools.moveTo(*old))
				landed = bool(onMain(lambda: focustools.isFocus(obj, api.getFocusObject())))
				clicked = landed
		if not landed:
			_safe(lambda: onMain(api.setNavigatorObject, obj))
			return (f"The program did not let the focus move to the {named}{where}, so the focus stays on {whereNow()}. "
				"NVDA's navigator object is on it, so NVDA's object review reads it. Moving there with Tab or the arrow keys "
				"may still work.")
		states = onMain(controltools.statesOf, obj)
		value = onMain(controltools.valueOf, obj)
		lines = [f"You are on the {named}{where}."]
		if item.get("byText"):
			lines.append(f"It has no name of its own; the text \"{label}\" stands before it.")
		about = focusWords.stateWords(states, item.get("role") or "")
		if value and kind != "check":
			lines.append(f"It shows {value}.")
		elif kind in placing.TYPED and not value:
			lines.append("It is empty.")
		if about:
			lines.append("It is " + ", ".join(about) + ".")
		if clicked:
			lines.append("The program took the focus only with a click inside it, which changes nothing there.")
		use = focusWords.useText(item.get("role") or "", states)
		if use:
			lines.append(use)
		return " ".join(lines)

	def wherePlaced(page, title):
		parts = []
		if page:
			parts.append(f"on the page {page}")
		if title:
			parts.append(f"in the window \"{title}\"")
		return (", " + ", ".join(parts)) if parts else ""

	# --- On a web page ---

	def onWeb(task, found):
		result = onMain(webtools.pageItems)
		if result is None:
			return None
		kinds = {web: kind for kind, _w, _r, webKinds, _o in placing.KINDS for web in webKinds}
		items = [{"label": item.get("plain") or "", "kind": kinds.get(item.get("kind"), "")} for item in result.items]
		if found.get("best"):
			ranked = placing.helpful(items, {"words": found.get("asked", ""), "typing": found.get("typing")})
			picks = [ranked[0][0]] if ranked else []
			reason = ranked[0][1] if ranked else ""
		else:
			picks, reason = placing.pickControls(items, found), ""
		if not picks:
			there = placing.listText([item["label"] for item in items if not found.get("kind") or item["kind"] == found["kind"]][:30],
				found.get("kind") or "")
			return (f"Nothing on the web page fits {placing.wantedText(found)}. Nothing was moved; NVDA's reading position is where "
				"it was."
				+ (f" {there}" if there else ""))
		if len(picks) > 1:
			# Translators: Asked when several controls of a web page fit what the user named.
			index = choose(task, [result.items[i]["text"] for i in picks], _("Which one do you mean?"))
			if index is None:
				return "You chose none of them, so nothing was moved."
			picks = [picks[index]]
		item = result.items[picks[0]]
		kind = items[picks[0]]["kind"]
		document = onMain(webtools.page)
		task.check()
		if found.get("typing") and kind in placing.TYPED:
			onMain(lambda: item["web"].activate())
			time.sleep(SETTLE)
			ok = onMain(lambda: bool(getattr(webtools.page(), "passThrough", False))
				and focustools.isFocus(item["web"].obj, api.getFocusObject()))
			if ok:
				return (f"You are in the {item['text']}, in focus mode: type, and NVDA reads what you type. Escape goes back "
					"to browse mode." + (f" Chosen because {reason}." if reason else ""))
			now = whereNow()
			return (f"VisionClaw went into the {item['text']} the way Enter does, but NVDA's focus is on {now}, not in it. "
				"Press Enter to go into it yourself.")
		onMain(webtools.moveTo, item)
		time.sleep(0.15)
		ok = onMain(lambda: _atItem(document, item["web"]))
		if ok is False:
			return f"VisionClaw moved NVDA's reading position to the {item['text']}, but it is not there now. You are on {whereNow()}."
		use = "Press Enter to use it." if kind in ("button", "link", "check", "radio") else "Press Enter to go into it."
		return (f"NVDA's reading position is on the {item['text']}, in browse mode. {use}"
			+ (f" Chosen because {reason}." if reason else ""))

	# --- In a window NVDA cannot read, or a game: its picture ---

	def pictureItems():
		"""The window's items read from its picture, as the overlay reads them, and the picture: (result, image)."""
		from contentRecog import RecogImageInfo
		from . import ocr, overlay
		app, title, _fg, _focus = onMain(screen.where)
		image, box = screen.picture("window")
		lines = ocr.recognize(image)
		recognizer = overlay.OverlayRecognizer(plugin, app, live=False, underCurtain=False, title=title)
		info = RecogImageInfo.createFromRecognizer(box[0], box[1], box[2] - box[0], box[3] - box[1], recognizer)
		return recognizer._makeResult(image, lines, info), image

	def seen(image, items):
		"""What a sighted person sees of each item, measured from the picture: whether the program marks it, whether it is
		larger than most, and whether its colour stands out from the window's. Plain code; nothing is guessed."""
		from . import overlay
		marked = _safe(lambda: overlay.findHighlighted(image, items))
		back = _safe(lambda: colours.ground(image))
		heights = sorted(item["box"][3] - item["box"][1] for item in items) or [0]
		median = heights[len(heights) // 2]
		facts = []
		for index, item in enumerate(items):
			left, top, right, bottom = item["box"]
			main = _safe(lambda: colours.main(image, item["box"], most=1), []) or []
			colour = main[0][0] if main else ""
			plain = colours.family(colour) if colour else ""
			standsOut = bool(plain) and plain not in ("black", "white", "grey") and (back is None or colours.family(back) != plain)
			facts.append({"marked": index == marked, "large": median > 0 and bottom - top >= 1.6 * median,
				"colourful": colour if standsOut else "", "warning": plain == "red" and item.get("kind") == "text"})
		return facts

	def onPicture(task, found):
		try:
			result, image = pictureItems()
		except Exception as e:
			debuglog.error("place", "The window's picture could not be read", e)
			return None
		raw = list(result.items)
		if not raw:
			return None
		kinds = {role: kind for kind, _w, _r, _web, roles in placing.KINDS for role in roles}
		facts = seen(image, raw)
		items = [dict(facts[index], label=item.get("plain") or item.get("name") or item.get("text") or "",
			kind=kinds.get(item.get("role") or "", ""), value="") for index, item in enumerate(raw)]
		reason = ""
		if found.get("best"):
			ranked = placing.helpful(items, dict(onMain(placeContext), words=found.get("asked", ""), typing=found.get("typing")))
			picks = [ranked[0][0]] if ranked else []
			reason = ranked[0][1] if ranked else ""
		else:
			picks = placing.pickControls(items, found)
		if not picks:
			return None
		if len(picks) > 1:
			# Translators: Asked when several items read from a window's picture fit what the user named.
			index = choose(task, [raw[i]["text"] for i in picks], _("Which one do you mean? These were read from the window's picture."))
			if index is None:
				return "You chose none of them, so nothing was moved."
			picks = [picks[index]]
		item = raw[picks[0]]
		task.check()
		# The overlay makes the window workable from the keyboard: it is opened with its cursor on the item.
		plugin._overlayItem = item["text"]
		onMain(plugin.openOverlay, True)
		end = time.monotonic() + OVERLAY_SECONDS
		on = False
		while time.monotonic() < end and not on:
			task.check()
			time.sleep(0.2)
			on = bool(onMain(lambda: _overlayOn(item["text"])))
		chosen = f" Chosen because {reason}." if reason else ""
		if on:
			return (f"This window tells NVDA almost nothing, so VisionClaw read it from its picture and opened the overlay, "
				f"with its cursor on {item['text']}.{chosen} The arrow keys move between the items it found, Enter clicks the "
				"one you are on, and Escape closes the overlay. What was read from a picture can be wrong.")
		if onMain(lambda: _isOverlay(api.getFocusObject())):
			return (f"This window tells NVDA almost nothing, so VisionClaw opened the overlay, which reads it from its picture. "
				f"{item['text']} is among its items, but the cursor is not on it yet: the arrow keys move to it.{chosen}")
		return (f"VisionClaw found {item['text']} in the window's picture, but the overlay did not open. Press NVDA+Alt+O to "
			"open it; it reads the window from its picture.")

	# --- The tool ---

	def known(found, app):
		"""What the user asked VisionClaw to remember, and the program's learning scratchpad, as lines: where a control is."""
		lines = []
		memories = getattr(plugin, "memories", None)
		if memories is not None:
			lines += [_safe(memory.text, "") for memory in (_safe(lambda: memories.all(), []) or [])]
		pads = getattr(plugin, "pads", None)
		if pads is not None and app and app != "?":
			pad = _safe(lambda: pads.learning(app))
			lines += [note.text for note in (_safe(lambda: pad.notes, []) or [])] if pad is not None else []
		return [line for line in lines if line]

	def learnRoute(found, item, page, title, app):
		"""Where a control was found, written on the program's learning scratchpad by plain code, where the user lets
		VisionClaw keep scratchpads. A fault here is no fault."""
		pads = getattr(plugin, "pads", None)
		# "?" is a program NVDA could not name: nothing is written for it.
		if pads is None or not page or not app or app == "?" or not item.get("label"):
			return
		try:
			if not config.conf["visionClaw"]["scratchpads"]:
				return
			from .claw import scratchpad
			line = placing.routeLine(item["label"], item.get("roleText") or placing.KIND_SAID.get(item["kind"], "control"), page, title)
			if line:
				pads.learn(app, line, scratchpad.BY_VISIONCLAW, f"\"{uncut(found.get('asked', ''))}\"")
		except Exception as e:
			debuglog.error("place", "Where the control is could not be written on the scratchpad", e)

	def goTo(task, asked):
		found = placing.wish(asked or task.request)
		if found is None:
			raise ToolError(
				"The request does not say where to put the user. Name the control, its kind, the page of the dialog or the "
				"window, in the user's own words.")
		found["asked"] = asked or task.request
		app, title, _fg, _focus = onMain(screen.where)
		said = []
		# What was learned before says on which page or in which window a control is, where the words do not.
		if found.get("label") and not found.get("page") and found.get("window") is None:
			route = placing.routeFrom(known(found, app), found)
			if route:
				found["page"] = route.get("page")
				if route.get("window") and not placing.windowFits(title, route["window"]):
					found["window"] = route["window"]
				said.append("Where it is was found in what VisionClaw learned or you asked it to remember.")
		# A web page, where no window or page of a dialog is named.
		if found.get("window") is None and found.get("page") is None and onMain(webtools.page) is not None:
			done = onWeb(task, found)
			if done is not None:
				return " ".join(said + [done])
		if found.get("window"):
			ok, sentence = toWindow(task, found["window"])
			if sentence:
				said.append(sentence)
			if not ok:
				return " ".join(said)
			app, title, _fg, _focus = onMain(screen.where)
		pageName = ""
		if found.get("page"):
			ok, sentence, pageName = toPage(task, found["page"])
			if sentence:
				said.append(sentence)
			if not ok:
				return " ".join(said + [f"Nothing else was done; you are on {whereNow()}."])
		wantsControl = found.get("kind") or found.get("label") or found.get("nth") is not None or found.get("best")
		if not wantsControl:
			# A page or a window alone: the user is told where the focus is, and how to get into the page.
			return " ".join(said + [f"You are on {whereNow()}. Tab moves into the page, through its controls."])
		task.check()
		items = onMain(controlsHere)
		reason = ""
		if found.get("best"):
			context = dict(onMain(placeContext), words=found["asked"], typing=found.get("typing"))
			ranked = placing.helpful(items, context)
			picks = [ranked[0][0]] if ranked else []
			reason = ranked[0][1] if ranked else ""
		else:
			picks = placing.pickControls(items, found)
		if not picks and not pageName and not found.get("best"):
			others, morePicks, otherPage = onOtherPages(task, found)
			if morePicks:
				items, picks, pageName = others, morePicks, otherPage
				said.append(f"It is on the page {otherPage}, which is shown now.")
		named = len([item for item in items if item.get("label")])
		if not picks and named < FEW_NAMED:
			# The window tells NVDA almost nothing: its picture is read, and the user is put on the item there.
			done = onPicture(task, found)
			if done is not None:
				return " ".join(said + [done])
		if not picks:
			there = placing.listText([item["label"] for item in items
				if not found.get("kind") or item["kind"] == found["kind"]][:30], found.get("kind") or "")
			return " ".join(said + [
				f"Nothing here fits {placing.wantedText(found)}" + (f", on the page {pageName}" if pageName else "") + ".",
				there or "", f"Nothing else was moved; you are on {whereNow()}."]).replace("  ", " ").strip()
		if len(picks) > 1:
			labels = [f"{items[i]['label'] or 'no name'} {items[i].get('roleText') or placing.KIND_SAID.get(items[i]['kind'], '')}".strip()
				for i in picks]
			# Translators: Asked when several controls of a window fit what the user named.
			index = choose(task, labels, _("Several controls fit. Which one do you mean?"))
			if index is None:
				return " ".join(said + [f"You chose none of them, so the focus stays on {whereNow()}."])
			picks = [picks[index]]
		item = items[picks[0]]
		_app, title, _fg, _focus = onMain(screen.where)
		sentence = placeOn(task, item, wherePlaced(pageName, title))
		if reason:
			sentence += f" Chosen because {reason}."
		said.append(sentence)
		if sentence.startswith("You are on") and pageName:
			learnRoute(found, item, pageName, title, app)
		task.items = None
		return " ".join(part for part in said if part)

	add("go_to_control",
		"put the user exactly where they ask to be, in the program, dialog, game or web page in front: a window or dialog "
		"(opened with its button where needed), a page of it by number or name, and a control by its kind and label; or, "
		"where they name none, the control most likely to help. Checks after every step that NVDA's focus is really there",
		goTo, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		title="Putting you there", tell=VERBATIM)


def _overlayOn(text):
	"""Whether NVDA is in the overlay with its cursor on the item with this text. Main thread."""
	focus = api.getFocusObject()
	if not _isOverlay(focus):
		return False
	try:
		result, item = focus._currentItem()
		return item is not None and item.get("text") == text
	except Exception:
		return False


def _atItem(document, node):
	"""Whether NVDA's reading position in a page is on a quick navigation item: True, False, or None when it cannot be
	told. Main thread."""
	try:
		import textInfos
		selection = document.makeTextInfo(textInfos.POSITION_SELECTION)
		info = node.textInfo
		return info.compareEndPoints(selection, "startToStart") <= 0 and info.compareEndPoints(selection, "endToStart") > 0
	except Exception:
		return None
