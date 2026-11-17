# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - telling the controls of a web page or a window apart by plain rules.
# A control is a plain dictionary (a "node"); a rule is a plain dictionary of what the control must have.
# The inspection uses these functions to find problems, and the same text is copied into every fixes add-on,
# so an add-on finds a control exactly the way the inspection found it. Everything below the marker line is
# copied; it must stay free of imports and of anything from NVDA.

# --- matcher ---

TEXT_KEPT = 300


def plainText(text):
	"""Lower case, with everything that is not a letter or digit turned into one space."""
	out = []
	for char in str(text or "").lower():
		out.append(char if char.isalnum() else " ")
	return " ".join("".join(out).split())


def labelOf(node):
	"""What a control is called: its name, or else the text inside it."""
	return node.get("name") or node.get("text") or ""


def hostOf(address):
	"""The site of a web address: "https://www.example.com/a?b" is "example.com"."""
	text = str(address or "").strip().lower()
	if "://" in text:
		text = text.split("://", 1)[1]
	for mark in "/?#":
		text = text.split(mark, 1)[0]
	text = text.rsplit("@", 1)[-1].split(":", 1)[0]
	return text[4:] if text.startswith("www.") else text


def sameSite(site, address):
	"""Whether a web address belongs to a site, including the site's own sub-sites."""
	host = hostOf(address)
	return bool(site) and bool(host) and (host == site or host.endswith("." + site))


def fileOf(address):
	"""The file name at the end of an address, such as "close.svg"; "" where there is none worth keeping."""
	text = str(address or "").strip()
	if not text or text.lower().startswith(("data:", "blob:")):
		return ""
	for mark in "?#":
		text = text.split(mark, 1)[0]
	name = text.rstrip("/").rsplit("/", 1)[-1].lower()
	return name if "." in name and len(name) <= 60 else ""


def _oneOf(wanted, value):
	if isinstance(wanted, str):
		return value == wanted
	return value in wanted


def matches(rule, node):
	"""Whether a control fits a rule. Every key the rule has must hold:
	role (one or several), notRole, tag, ident, cls (all of them), src, state, level, controlId, autoId,
	windowClass, unnamed (no name at all), names (its name is, or starts with, one of these), and outer (it is
	not inside another control that fits the same rule)."""
	role = rule.get("role")
	if role and not _oneOf(role, node.get("role")):
		return False
	if node.get("role") in (rule.get("notRole") or ()):
		return False
	for key in ("tag", "ident", "src", "controlId", "autoId", "windowClass"):
		if rule.get(key) and rule[key] != node.get(key):
			return False
	wanted = rule.get("cls")
	if wanted:
		have = node.get("cls") or ()
		for name in wanted:
			if name not in have:
				return False
	if rule.get("state") and rule["state"] not in (node.get("states") or ()):
		return False
	if rule.get("level") and str(rule["level"]) != str(node.get("level") or ""):
		return False
	if rule.get("unnamed") and plainText(labelOf(node)):
		return False
	names = rule.get("names")
	if names:
		text = plainText(labelOf(node))
		found = False
		for name in names:
			wantedName = plainText(name)
			# The whole name, or its beginning: "play" fits "Play (k)" but not a long text that mentions play.
			if wantedName and (text == wantedName or (text.startswith(wantedName + " ") and len(text) <= len(wantedName) + 24)):
				found = True
				break
		if not found:
			return False
	if rule.get("outer"):
		inner = dict(rule)
		inner["outer"] = False
		up = node.get("up")
		while up is not None:
			if matches(inner, up):
				return False
			up = up.get("up")
	return True


def nodeFromField(field):
	"""A control of a web page, from the facts NVDA keeps about it in browse mode. This is the same in Chrome,
	Edge, Brave and Firefox, because NVDA builds all of their pages the same way."""
	role = field.get("role")
	states = field.get("states") or ()
	return {
		"role": getattr(role, "name", str(role or "")),
		"name": " ".join(str(field.get("name") or "").split()),
		"text": "",
		"tag": str(field.get("IAccessible2::attribute_tag") or "").lower(),
		"cls": str(field.get("IAccessible2::attribute_class") or "").split(),
		"ident": str(field.get("IAccessible2::attribute_id") or ""),
		"src": fileOf(field.get("IAccessible2::attribute_src")),
		"states": [getattr(state, "name", str(state)) for state in states],
		"level": str(field.get("level") or ""),
		"landmark": str(field.get("landmark") or ""),
		"xml": str(field.get("IAccessible2::attribute_xml-roles") or ""),
		"live": str(field.get("IAccessible2::attribute_live") or field.get("IAccessible2::attribute_container-live") or ""),
		"hidden": bool(field.get("isHidden")),
		"key": field.get("uniqueID"),
	}


def _units(text):
	"""The length of a text as NVDA's page positions count it, where some characters count twice."""
	extra = 0
	for char in text:
		if ord(char) > 0xFFFF:
			extra += 1
	return len(text) + extra


def nodesFromFields(commands, offset=0):
	"""The controls in a stretch of a web page, in reading order, from what NVDA gives for that stretch: texts,
	and marks where a control starts and ends. Each control gets the text inside it (its beginning), where it
	starts and ends, and the control it is inside ("up"). A control that reaches the end of the stretch is
	marked "open": it may go on, so its text and end may not be complete."""
	nodes, stack, position = [], [], offset
	for command in commands:
		if isinstance(command, str):
			for node in stack:
				if len(node["text"]) < TEXT_KEPT:
					node["text"] += command
			position += _units(command)
			continue
		kind = getattr(command, "command", None)
		if kind == "controlStart":
			node = nodeFromField(command.field)
			node["start"] = position
			node["up"] = stack[-1] if stack else None
			stack.append(node)
			nodes.append(node)
		elif kind == "controlEnd" and stack:
			node = stack.pop()
			node["end"] = position
	for node in stack:
		node["end"] = position
	for node in nodes:
		# NVDA closes every control at the end of a stretch, whether or not the control goes on. So a control
		# that ends exactly where the stretch ends may be cut.
		if node["end"] == position:
			node["open"] = True
		# The text as it came is kept too: a control that runs on into the next stretch is joined from it.
		node["raw"] = node["text"]
		node["text"] = " ".join(node["text"].split())[:TEXT_KEPT]
	return nodes


def nodeFromObject(obj, up=None):
	"""A control of a program's window, from what NVDA knows about it. A property NVDA cannot give is left
	empty; nothing here may raise."""
	def get(name, default=""):
		try:
			value = getattr(obj, name, default)
		except Exception:
			return default
		return default if value is None else value

	role = get("role", None)
	states = get("states", ()) or ()
	web = get("IA2Attributes", None)
	if not hasattr(web, "get"):
		web = {}
	controlId = get("windowControlID", 0)
	return {
		"role": getattr(role, "name", str(role or "")),
		"name": " ".join(str(get("name")).split()),
		"text": "",
		"value": " ".join(str(get("value")).split())[:TEXT_KEPT],
		"tag": str(web.get("tag") or "").lower(),
		"cls": str(web.get("class") or "").split(),
		"ident": str(web.get("id") or ""),
		"src": fileOf(web.get("src")),
		"states": [getattr(state, "name", str(state)) for state in states],
		"level": "",
		"landmark": "",
		"xml": str(web.get("xml-roles") or ""),
		"live": str(web.get("live") or ""),
		"hidden": False,
		"controlId": controlId if isinstance(controlId, int) else 0,
		"autoId": str(get("UIAAutomationId")),
		"windowClass": str(get("windowClassName")),
		"obj": obj,
		"up": up,
	}
