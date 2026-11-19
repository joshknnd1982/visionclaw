# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - an NVDA setting changed only for one program: "make NVDA speak faster, only in this program",
# "turn off the typing echo just in Notepad", "when I'm in Word, set punctuation to all". NVDA does this with a
# configuration profile that it turns on by itself whenever that program is in front. Whether a request asks for
# this, and for which program, is read from the user's own words by plain code; a model writes nothing here.
# What NVDA itself does with profiles is in profiletools.py. No NVDA dependencies.

import re

# The words that say a program: "this program", "this app", "here".
_THIS = r"(?:this|the current|the present|that) (?:app|application|program|game|window|one)"
_HERE_WORD = r"here"
# Words that narrow something down to one place.
_ONLY = r"(?:only|just|solely|exclusively)"
_IN = r"(?:in|for|inside|within|on|with)"
_WHILE = (
	r"(?:when|while|whenever|as long as)\s+(?:i am|i'm|im|i)\s*(?:am\s+)?(?:in|inside|using|use|working in|work in|"
	r"working with|work with|running|run|playing|play|on)")
# A program's name, as the user writes it: one to four words, which may have a dot, a plus or a digit.
_NAME = r"([A-Za-z0-9](?:[\w.+'&-]*[\w+])?(?: [A-Za-z0-9](?:[\w.+'&-]*[\w+])?){0,3}?)"
# A name ends at the end, at a mark, or at a word that begins what is to be done: a request that was spoken has
# no comma after "when I am in Word".
_END = (
	r"(?=\s*(?:$|[.,;!?]|\b(?:and|but|not|please|only|set|turn|make|change|switch|speak|say|read|use|raise|lower|put|"
	r"stop|start|let|have|keep|enable|disable|announce|report|beep|mute|talk|i want|i need|i would|i'd|nvda should)\b))")
# The ways of saying it, the surest first. Each has the program in group "this" (the one in front), "here", or
# "name" (a program the user names).
_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
	rf"[,;]?\s*\b(?:but\s+)?{_ONLY}\s+{_WHILE}\s+(?:(?P<this>{_THIS})|(?P<here>{_HERE_WORD})|(?P<name>{_NAME})){_END}",
	rf"[,;]?\s*\b{_WHILE}\s+(?:(?P<this>{_THIS})|(?P<here>{_HERE_WORD})|(?P<name>{_NAME}))\s*,?\s*(?:{_ONLY})?{_END}",
	rf"[,;]?\s*\b(?:but\s+)?{_ONLY}\s+{_IN}\s+(?:(?P<this>{_THIS})|(?P<here>{_HERE_WORD})|(?P<name>{_NAME})){_END}",
	rf"[,;]?\s*\b{_IN}\s+(?:(?P<this>{_THIS})|(?P<name>{_NAME}))\s+{_ONLY}\b",
	rf"[,;]?\s*\b(?:but\s+)?{_ONLY}\s+(?P<here>{_HERE_WORD})\b",
	rf"[,;]?\s*\b(?P<here>{_HERE_WORD})\s+{_ONLY}\b",
	rf"[,;]?\s*\b{_IN}\s+(?P<this>{_THIS})(?:'s)?\b(?!\s+(?:dialog|window|settings|options|menu))",
))
# The pattern above that has no "only" in it: "when I'm in Word, ...".
_WHILE_ALONE = 1
_NOT_FIRST = frozenset(("a", "an", "my", "your", "any", "every", "each", "all", "some", "no", "one", "it", "its"))
# After the place, what only says once more that nowhere else is meant.
_NOWHERE_ELSE = re.compile(
	r"[,;]?\s*\b(?:and|but)?\s*(?:not|nowhere|no where)\s+(?:anywhere\s+)?(?:else|elsewhere|everywhere(?: else)?)\b", re.IGNORECASE)
# What follows "only in" and is no program: a mode, a kind of control, a kind of text. "Speak typed characters
# only in edit fields" is a value of a setting, and nothing about a program.
_NOT_PROGRAMS = frozenset((
	"mode", "modes", "field", "fields", "box", "boxes", "document", "documents", "letter", "letters", "word", "words",
	"character", "characters", "line", "lines", "table", "tables", "list", "lists", "link", "links", "heading", "headings",
	"capital", "capitals", "number", "numbers", "form", "forms", "menu", "menus", "dialog", "dialogs", "page", "pages",
	"braille", "speech", "caps", "text", "texts", "controls", "control", "buttons", "button", "cells", "cell", "rows", "row",
	"columns", "column", "sentences", "sentence", "paragraphs", "paragraph", "editors", "terminals", "consoles", "browsers",
	"case", "cases", "way", "time", "times", "moment", "now", "then", "there", "it", "them", "that", "this", "these", "those",
	"everything", "anything", "something", "nothing", "all", "general", "nvda", "windows", "english", "second", "seconds",
	"minute", "minutes", "bit", "little", "part", "parts", "half", "key", "keys", "keyboard", "mouse", "arrow", "arrows",
	"lock", "screen", "display", "headphones", "speakers", "laptop", "computer", "internet", "web", "typing", "reading",
	"writing", "editing", "browsing", "morning", "evening", "night", "work", "home", "bed", "meetings", "meeting", "call",
	"calls", "hurry", "rush", "doubt", "trouble", "fact", "order", "place", "front", "focus", "background"))
# Words that narrow a request down, wherever they stand: when no program could be read after them, the user is
# told that the change is for every program.
NARROWS = re.compile(r"\b(?:only|just)\s+(?:in|for|inside|within|when|while|on)\b", re.IGNORECASE)
# What a program is called by people, and the name of its file, which is what NVDA knows it by.
ALIASES = {
	"word": "winword", "microsoft word": "winword", "ms word": "winword", "excel": "excel", "microsoft excel": "excel",
	"powerpoint": "powerpnt", "power point": "powerpnt", "outlook": "outlook", "onenote": "onenote", "access": "msaccess",
	"edge": "msedge", "microsoft edge": "msedge", "chrome": "chrome", "google chrome": "chrome", "firefox": "firefox",
	"mozilla firefox": "firefox", "file explorer": "explorer", "explorer": "explorer", "windows explorer": "explorer",
	"notepad": "notepad", "notepad++": "notepad++", "command prompt": "cmd", "the command prompt": "cmd",
	"terminal": "windowsterminal", "windows terminal": "windowsterminal", "powershell": "powershell",
	"vs code": "code", "visual studio code": "code", "vscode": "code", "visual studio": "devenv", "teams": "ms-teams",
	"microsoft teams": "ms-teams", "thunderbird": "thunderbird", "calculator": "calculatorapp", "paint": "mspaint",
	"wordpad": "wordpad", "skype": "skype", "zoom": "zoom", "discord": "discord", "spotify": "spotify", "vlc": "vlc",
	"itunes": "itunes", "audacity": "audacity", "reaper": "reaper", "winamp": "winamp", "foobar": "foobar2000",
	"brave": "brave", "opera": "opera", "vivaldi": "vivaldi", "telegram": "telegram", "whatsapp": "whatsapp",
	"acrobat": "acrobat", "adobe reader": "acrord32", "task manager": "taskmgr", "settings": "systemsettings",
}
# What a program is called when the user is told about it, where the name of its file or what its maker calls
# the product would mislead: a profile for winword is for Word, not for all of "Microsoft Office".
SAID = {
	"winword": "Word", "excel": "Excel", "powerpnt": "PowerPoint", "outlook": "Outlook", "onenote": "OneNote",
	"msaccess": "Access", "msedge": "Microsoft Edge", "explorer": "File Explorer", "notepad": "Notepad", "cmd": "Command Prompt",
	"windowsterminal": "Windows Terminal", "code": "Visual Studio Code", "devenv": "Visual Studio", "ms-teams": "Microsoft Teams",
	"calculatorapp": "Calculator", "mspaint": "Paint", "taskmgr": "Task Manager", "systemsettings": "Settings",
	"acrord32": "Adobe Reader",
}
# NVDA's own windows: a profile for them is no profile for a program.
NOT_A_PROGRAM = ("nvda", "nvda_slave", "nvda_dmp", "unknown", "")
NAME_CHARS = 60


def _words(text):
	return re.findall(r"[a-z0-9+#]+", str(text or "").lower())


def _find(part):
	"""(match, kind) of the words that say one program, or (None, None)."""
	text = " ".join(str(part or "").split())
	for number, pattern in enumerate(_PATTERNS):
		for hit in pattern.finditer(text):
			groups = hit.groupdict()
			if groups.get("this") or groups.get("here"):
				return hit, "front"
			name = (groups.get("name") or "").strip()
			words = _words(name)
			if words[:1] == ["the"]:
				words = words[1:]  # "the command prompt"
			known = " ".join(words) in ALIASES  # "Word" is a program, though "words" are not
			if not words or (not known and (words[-1] in _NOT_PROGRAMS or words[0] in _NOT_FIRST)):
				continue
			# "When I use caps lock" names no program. Without "only", a name must be written as one, with a
			# capital, or be a program everybody knows.
			if number == _WHILE_ALONE and not (name[:1].isupper() or known):
				continue
			return hit, "named"
	return None, None


# "Stop announcing capital letters in Word": a program named at the end or the beginning, with no "only". That is
# taken for a program only where the name is one: a program everybody knows, or the program that is in front.
_PLAIN_IN = (
	re.compile(rf"[,;]?\s*\b(?:in|inside|within)\s+(?:the\s+)?(?P<name>{_NAME})\s*[.!?]*\s*$", re.IGNORECASE),
	re.compile(rf"^\s*(?:in|inside|within)\s+(?:the\s+)?(?P<name>{_NAME})\s*,\s*", re.IGNORECASE),
)
# Words that say every program is meant: "speak words as I type in every application".
_EVERYWHERE = re.compile(
	r"[,;]?\s*\b(?:everywhere|globally|system[- ]wide|(?:in|for|across|on) (?:every|all|all the|all of the|all my|all of my|each) "
	r"(?:applications?|apps?|programs?|windows?)|in every (?:one|place)|(?:in|for) (?:every|all) of them|"
	r"(?:not|and not) (?:only|just) (?:in|for) (?:this|that) (?:app|application|program|game|one))\b", re.IGNORECASE)


def _plainIn(text, facts=None):
	"""The match of a program named with "in" alone, where the name is a program's; None otherwise."""
	for pattern in _PLAIN_IN:
		hit = pattern.search(text)
		if hit is None:
			continue
		name = hit.group("name").strip()
		words = _words(name)
		if not words or words[0] in _NOT_FIRST:
			continue
		known = " ".join(words) in ALIASES
		if known and name[:1].isupper() or (facts is not None and facts.get("app") and fits(name, facts)
				and (known or words[-1] not in _NOT_PROGRAMS)):
			return hit
	return None


def everywhere(part):
	"""Whether the user's own words say that every program is meant, and not one. "Only in Excel, not
	everywhere" says the opposite."""
	return bool(_EVERYWHERE.search(_NOWHERE_ELSE.sub(" ", " ".join(str(part or "").split()))))


def scopeOf(part, facts=None):
	"""Whether a request asks for something only in one program: None, or {"program": "" for the program in
	front, else the name the user said; "words": the words that said it}. facts: the program in front, where
	that is known; then "in" and its name alone is enough ("stop announcing capitals in Space Trader")."""
	text = " ".join(str(part or "").split())
	hit, kind = _find(text)
	if hit is None:
		hit, kind = _plainIn(text, facts), "named"
	if hit is None or everywhere(text):
		return None
	name = "" if kind == "front" else re.sub(r"^the\s+", "", hit.group("name").strip(), flags=re.IGNORECASE)
	return {"program": name[:NAME_CHARS], "words": " ".join(hit.group(0).strip(" ,;").split())}


def restricts(part):
	"""Whether the words narrow the request down with "only", "just" or "when I am in": then it is a setting
	of NVDA for that program, and no control inside the program."""
	hit, _kind = _find(part)
	if hit is None:
		return False
	return bool(re.search(rf"\b{_ONLY}\b|\b(?:when|while|whenever|as long as)\b", hit.group(0), re.IGNORECASE))


def without(part, facts=None):
	"""A request without the words that say for which program: what is left names the setting. "Turn off the
	typing echo only in Word" must not be looked up with the word "word", which is in the name of another
	setting."""
	text = " ".join(str(part or "").split())
	hit, _kind = _find(text)
	if hit is None:
		hit = _plainIn(text, facts)
	if hit is None or everywhere(text):
		# "In every application" names no setting either.
		rest = _EVERYWHERE.sub(" ", text)
	else:
		rest = text[:hit.start()] + " " + _NOWHERE_ELSE.sub(" ", text[hit.end():], count=1)
	rest = re.sub(r"\s+([.,;!?])", r"\1", " ".join(rest.split())).strip(" ,;")
	return rest or text


def fits(name, facts):
	"""Whether a program the user named is the one in front. facts: its file's name without the ending ("app"),
	what its maker calls it ("product"), and its window's title ("title")."""
	said = " ".join(_words(name))
	if not said:
		return True
	app = " ".join(_words(facts.get("app")))
	if not app:
		return False
	if said == app or ALIASES.get(said) == facts.get("app", "").lower() or said.replace(" ", "") == app.replace(" ", ""):
		return True
	asked = set(said.split())
	for known in (facts.get("product"), facts.get("title")):
		words = set(_words(known))
		if words and asked <= words:
			return True
	# "Notepad" for notepad++, "code" for a file called code: the name begins the file's name.
	return len(said) >= 4 and app.startswith(said.replace(" ", ""))


def shown(facts):
	"""What a program is called when the user is told about it: what its maker calls it, else its file's name."""
	product = " ".join(str(facts.get("product") or "").split())
	app = str(facts.get("app") or "").strip()
	if app.lower() in SAID:
		return SAID[app.lower()]
	if product and len(product) <= 40 and not re.search(r"\b(operating system|runtime|framework)\b", product, re.IGNORECASE):
		return product
	return app or "this program"


def profileName(app, taken):
	"""The name of the configuration profile for a program: the program's own name, as NVDA suggests it in its
	own window; another one where a profile of that name is there already and belongs to something else."""
	taken = {str(name).lower() for name in taken or ()}
	base = re.sub(r'[\\/:*?"<>|]+', "_", str(app or "").strip()) or "program"
	if base.lower() not in taken:
		return base
	for number in range(1, 50):
		name = f"{base} (VisionClaw)" if number == 1 else f"{base} (VisionClaw {number})"
		if name.lower() not in taken:
			return name
	raise ValueError("No name is free for a configuration profile.")


def appOf(spec):
	"""The program a trigger of NVDA is for ("app:notepad" gives "notepad"), or "" for another kind of trigger."""
	spec = str(spec or "")
	return spec[4:] if spec.startswith("app:") and len(spec) > 4 else ""


# --- What the user is told ---

def notHere(name, front):
	return (
		f"You said this is for {name}, and the program in front is {front}. VisionClaw changes a setting for one "
		f"program only while that program is in front, so that it is never changed in the wrong place. Switch to "
		f"{name} and ask again there. To change the setting everywhere, ask again without naming a program.")


def question(program, created):
	"""What is put before the question about the change, so the user knows what will be made."""
	if created:
		return (
			f"This is only for {program}. NVDA does that with a configuration profile, which it turns on by itself "
			f"whenever {program} is in front. There is none for {program} yet, so VisionClaw will make one.")
	return f"This is only for {program}, in the configuration profile NVDA already has for it."


def done(label, old, new, program, profile, created):
	said = f"Only in {program}: {label} was {old} and is now {new}. In other programs it is as it was."
	if created:
		said += (
			f" NVDA keeps this in a new configuration profile called {profile}, which it turns on by itself whenever "
			f"{program} is in front.")
	else:
		said += f" It is kept in the configuration profile {profile}."
	return said + " To put it back, say undo that while you are in this program."


BASE_ONLY = (
	"NVDA keeps this setting the same for every program; it cannot be different in one program. Nothing was changed. "
	"To change it everywhere, ask again without naming a program.")
READ_ONLY = (
	"This NVDA cannot keep new settings on this computer, as on a sign-in screen or when it runs from an installer, "
	"so it cannot keep a setting for one program. Nothing was changed.")
TRIGGERS_OFF = (
	"In this NVDA the configuration profiles that turn on by themselves are switched off for now, so a setting for "
	"one program would not take effect. Nothing was changed. They are switched on again in NVDA's Configuration "
	"profiles window, NVDA+Control+P, with the check box Temporarily disable all triggers, or by restarting NVDA.")
NO_PROGRAM = (
	"No program is in front that NVDA could keep a setting for. Switch to the program and ask again there.")


def whichQuestion(label, old, new, program):
	"""Asked where the program in front has settings of its own and the user did not say which is meant."""
	return (
		f"{program} has NVDA settings of its own. Change {label} from {old} to {new} only in {program}, or everywhere?")


def whichChoices(program):
	return [f"Only in {program}", "Everywhere", "Nothing: leave it as it is"]


def everywhereDone(label, old, new, program="", own=""):
	"""What is said after a setting was changed for every program. program and own: the program in front, where
	it keeps a value of its own for this setting, and that value."""
	said = f"Everywhere: {label} was {old} and is now {new}."
	if program and own:
		said += (
			f" {program} has a value of its own for this, {own}, and keeps it. To change that too, say it again and "
			"add: only in this program.")
	return said


def othersKeep(programs):
	"""Added to an answer when programs have a value of their own for the setting that was changed."""
	if not programs:
		return ""
	names = programs[0] if len(programs) == 1 else ", ".join(programs[:-1]) + " and " + programs[-1]
	verb = "has a value of its own for this and keeps it" if len(programs) == 1 else "have values of their own for this and keep them"
	return f" {names} {verb}."


def manualTakes(name):
	return (
		f"The configuration profile {name} is turned on by hand, so NVDA keeps this change in that profile, and it "
		"counts while that profile is on.")


OTHER_PROFILE = (
	"Another configuration profile is in use besides this program's own, so VisionClaw cannot reach NVDA's normal "
	"configuration now. Nothing was changed. NVDA+Control+P opens NVDA's Configuration profiles window, where it can "
	"be turned off.")


def manualOn(name):
	return (
		f"The configuration profile {name} was turned on by hand, and while it is on NVDA writes every change into "
		f"it, and it counts before the profile of any program. So nothing was changed. Turn it off first: press "
		f"NVDA+Control+P for NVDA's Configuration profiles window, choose {name} and press the button Manual "
		"deactivate. Then ask again.")


def notActive(program):
	return (
		f"NVDA did not turn on the configuration profile for {program}, so the setting was not changed, here or "
		"anywhere. Switch to another window and back to this program, then ask again.")


def undoElsewhere(label, program):
	return (
		f"{label[:1].upper() + label[1:]} was changed only for {program}. VisionClaw puts a program's own setting back "
		f"while that program is in front, so that nothing is changed in the wrong place. Switch to {program} and "
		"say undo that.")


def listText(found, front=""):
	"""Which programs have settings of their own. found: [(program, profile, active now, [what VisionClaw changed
	there, in sentences])]."""
	if not found:
		return (
			"No program has NVDA settings of its own; NVDA behaves the same in every program. To change one, say what "
			"you want and add: only in this program.")
	lines = []
	for program, profile, active, changed in found:
		line = f"{program}: its own settings are in the configuration profile {profile}"
		line += ", which is on now." if active else "."
		if changed:
			line += " VisionClaw changed there: " + " ".join(changed)
		lines.append(line)
	count = len(found)
	head = "One program has NVDA settings of its own." if count == 1 else f"{count} programs have NVDA settings of their own."
	return head + "\n" + "\n".join(lines) + (
		"\nTo change one, say what you want and add: only in this program. NVDA's own window for these is "
		"Configuration profiles, NVDA+Control+P.")


def removeQuestion(program, profile):
	return (
		f"Delete the configuration profile {profile}, which holds NVDA's settings for {program} alone? {program} "
		"will then behave like every other program. This cannot be undone.")


def removed(program, profile):
	return f"The configuration profile {profile} was deleted. NVDA now behaves in {program} as it does everywhere else."


def noProfile(program):
	return f"{program} has no NVDA settings of its own, so there is nothing to remove."


# --- Which request is about this ---

_REMOVE = re.compile(
	r"\b(remove|delete|forget|clear|reset|get rid of|throw away|drop)\b.{0,40}\b(settings?|profile|configuration)\b.{0,30}"
	r"\b(for|of|in|from)\b"
	r"|\b(remove|delete|get rid of)\b.{0,30}\b(configuration|config|nvda('s)?) profile\b"
	r"|\bmake\b.{0,50}\b(behave|sound|work|act|speak|talk)\b.{0,20}\b(like|as)\b.{0,20}\b(everywhere|every other|all (the )?other|"
	r"other programs|the rest|anywhere else)\b"
	r"|\b(same|like) (as )?(everywhere|every other program|all other programs)\b.{0,20}\bagain\b", re.IGNORECASE)
_ASKS = re.compile(
	r"\b(which|what|list|show|tell me|do any|does any|are there)\b.{0,40}\b(programs?|apps?|applications?)\b.{0,40}"
	r"\b(own|different|special|separate|their|its)\b.{0,20}\b(settings?|profiles?|configuration)\b"
	r"|\b(does|has|is there|do i have)\b.{0,60}\b(own|different|special|separate)\b.{0,12}\b(nvda )?(settings?|profile|configuration)\b"
	r"|\b(which|what|list|show|tell me|how many|are there|do i have)\b.{0,30}\bconfiguration profiles?\b"
	r"|\b(is|are)\b.{0,20}\b(configuration )?profiles?\b.{0,20}\b(active|on|in use|used)\b", re.IGNORECASE)
_HOW = re.compile(r"\bhow (do|can|would|should|could) (i|we|you|one)\b|\bhow to\b", re.IGNORECASE)


def removes(part):
	"""Whether a request asks to take a program's own settings away again."""
	text = " ".join(str(part or "").split())
	if _HOW.search(text) or not _REMOVE.search(text):
		return False
	# A profile, or settings "for this program": the settings of a named control or of a file are not meant.
	return bool(re.search(r"\bprofiles?\b", text, re.IGNORECASE) or scopeOf(text) is not None or re.search(
		rf"\b(for|of|in|from) ({_THIS}|[A-Z][\w+.]*)", text) or re.search(r"\beverywhere|other programs?|the rest\b", text, re.IGNORECASE))


def asks(part):
	"""Whether a request asks which programs have settings of their own."""
	text = " ".join(str(part or "").split())
	return bool(_ASKS.search(text)) and not _HOW.search(text) and not removes(text)


def namedIn(part):
	"""The program a request to remove names, or "" for the one in front."""
	text = " ".join(str(part or "").split())
	found = scopeOf(text)
	if found is not None:
		return found["program"]
	hit = re.search(rf"\b(?:for|of|in|from)\s+(?:(?:{_THIS})|{_NAME})\s*(?:$|[.,;!?]|\bplease\b)", text, re.IGNORECASE)
	name = (hit.group(1) or "").strip() if hit else ""
	# "The settings for Excel": the program is what follows the last of these words.
	name = re.split(r"\b(?:for|of|in|from)\s+", name, flags=re.IGNORECASE)[-1].strip()
	words = _words(name)

	def noProgram(words):
		return not words or (" ".join(words) not in ALIASES and words[-1] in _NOT_PROGRAMS)

	if noProgram(words):
		hit = re.search(rf"\bmake\s+{_NAME}\s+(?:behave|sound|work|act|speak|talk)\b", text, re.IGNORECASE)
		name = (hit.group(1) or "").strip() if hit else ""
		if noProgram(_words(name)) or re.fullmatch(_THIS, name, re.IGNORECASE):
			return ""
	return re.sub(r"^the\s+", "", name, flags=re.IGNORECASE)[:NAME_CHARS]
