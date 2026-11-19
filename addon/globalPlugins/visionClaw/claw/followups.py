# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a request that follows the one before it: "do that again", "say that again", "a bit more",
# "too fast", "and the pitch?", "the same in Word", "open the second one". Such a request cannot be understood
# alone. Plain code tells that it is one, and writes it out in full where it can do so for certain: the same
# request again, the same the other way, the same in another program. Where it cannot, a model writes it out
# from the request before and its answer, and plain code checks that every word of what it wrote was said by
# the user or by VisionClaw; otherwise the model's words are not used. The user is always told what the request
# was taken as. Kept only while NVDA runs; nothing is written to the disk. No NVDA dependencies.

import re

from . import computer

# How long after a request the next one may lean on it without saying so in clear words.
FOLLOW_SECONDS = 600
# "Open it" may mean what has the focus. It is taken to follow the request before only for this long.
SOON_SECONDS = 180
# Kinds of follow-up.
SAY_AGAIN, AGAIN, AGAIN_IN, MORE, OTHER_WAY, DIRECTION, ABOUT, REFERS = (
	"say again", "again", "again in", "more", "other way", "direction", "about", "refers")
# What plain code writes out by itself, and what needs a model.
PLAIN = (SAY_AGAIN, AGAIN, AGAIN_IN, MORE, OTHER_WAY, DIRECTION)
# A follow-up that says clearly that it leans on the request before ("and the pitch?", "the second one") can
# never be used as it stands; one that only may ("open it") can.
REWRITE_CHARS = 300

_POLITE = r"(?:(?:please|ok|okay|now|and|so|then|hey|well)[, ]+)*"
_END = r"(?:[, ]+(?:please|for me|now|thanks|thank you))*\s*[.!?]*\s*$"
_SAY_AGAIN = re.compile(
	rf"^\s*{_POLITE}(?:(?:can|could|would) you )?(?:say|read|tell me|speak) (?:that|it|this|the (?:last |same )?answer)"
	rf"(?: to me)?(?: again| once more| one more time){_END}"
	rf"|^\s*{_POLITE}(?:(?:can|could|would) you )?repeat (?:that|it|the (?:last |same )?answer|yourself)"
	rf"(?: to me)?(?: again| once more| one more time)?{_END}"
	rf"|^\s*{_POLITE}what did you (?:just )?say{_END}|^\s*{_POLITE}(?:come again|pardon|sorry|what|what was that|say again){_END}"
	rf"|^\s*{_POLITE}i (?:did not|didn't) (?:hear|catch|get|understand) (?:that|it|you){_END}", re.IGNORECASE)
_AGAIN = re.compile(
	rf"^\s*{_POLITE}(?:(?:can|could|would) you )?(?:do|try|run|make) (?:that|it|this|the same(?: thing)?)"
	rf"(?: again| once more| one more time| once again){_END}"
	rf"|^\s*{_POLITE}(?:again|once more|one more time|same again|the same again|redo(?: that| it)?|retry(?: that| it)?"
	rf"|try again|try (?:that|it) again|do it over|repeat (?:that|the last|my last) request){_END}", re.IGNORECASE)
_AGAIN_IN = re.compile(
	rf"^\s*{_POLITE}(?:(?:can|could|would) you )?(?:do )?(?:that|it|this|the same(?: thing)?|same)(?: again| too| also)?"
	rf" (?:in|for|with|on) (?P<where>[\w.+'& -]{{1,60}}?)(?: again| too| also| as well)?{_END}", re.IGNORECASE)
_MORE = re.compile(
	rf"^\s*{_POLITE}(?:(?:a|one) (?:little|bit|tad|touch|notch|step) |even |still |much |a lot |some )?"
	rf"(?:more|further|keep going|go on|more of that|more of the same){_END}", re.IGNORECASE)
_OTHER_WAY = re.compile(
	rf"^\s*{_POLITE}(?:that(?: is|'s| was) |that's |it(?: is|'s| was) |way )?(?:too much|not so much|not that much|too far|"
	rf"less|a (?:little|bit) less|the other way(?: round| around)?|the opposite|other direction|back a (?:bit|little|step)|"
	rf"go back a (?:bit|little|step)){_END}", re.IGNORECASE)
# Words that say a direction, each with its opposite.
_PAIRS = (
	("faster", "slower"), ("quicker", "slower"), ("louder", "quieter"), ("higher", "lower"), ("up", "down"),
	("more", "less"), ("increase", "decrease"), ("raise", "lower"), ("bigger", "smaller"), ("larger", "smaller"),
	("brighter", "darker"), ("brighter", "dimmer"), ("on", "off"), ("enable", "disable"), ("mute", "unmute"),
	("forward", "back"), ("forwards", "backwards"), ("next", "previous"), ("left", "right"), ("maximize", "restore"),
	("check", "uncheck"), ("show", "hide"), ("expand", "collapse"), ("open", "close"))
_OPPOSITE = {}
for _one, _two in _PAIRS:
	_OPPOSITE.setdefault(_one, _two)
	_OPPOSITE.setdefault(_two, _one)
# "Too fast" asks for slower: what the user finds there is too much of.
_TOO = {
	"fast": "slower", "quick": "slower", "slow": "faster", "loud": "quieter", "quiet": "louder", "soft": "louder",
	"high": "lower", "low": "higher", "big": "smaller", "large": "smaller", "small": "bigger", "bright": "darker",
	"dark": "brighter", "dim": "brighter"}
_DIRECTION = re.compile(
	rf"^\s*{_POLITE}(?:(?:make|turn) it )?(?:(?:a|one) (?:little|bit|tad|touch|notch|step) |even |still |much |a lot |way )?"
	rf"(?P<way>faster|quicker|slower|louder|quieter|higher|lower|bigger|larger|smaller|brighter|darker|dimmer)"
	rf"(?: still| again| than that| please)?{_END}"
	rf"|^\s*{_POLITE}(?:that(?: is|'s| was) |that's |it(?: is|'s| was) )?(?:still |way |much |a bit |a little |far )?too "
	rf"(?P<too>fast|quick|slow|loud|quiet|soft|high|low|big|large|small|bright|dark|dim){_END}", re.IGNORECASE)
# A request that begins by leaning on the one before it.
_ABOUT = re.compile(
	rf"^\s*(?:(?:and|or|but) (?:what about |how about |for |in |on |with |also |now )?|what about |how about |same for |"
	rf"same with |also (?=the |my |for |in )|and$)(?P<what>.+?){_END}", re.IGNORECASE)
# Words that can only mean something said before.
_STRONG = re.compile(
	r"\b(the (first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|next|other|same|previous) (one|ones|two|three)"
	r"|(that|this|the other|another|each|either|which) one|those ones|all of (them|those|these)|them all|both of them"
	r"|number (one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})\b(?! (times|percent|steps)))\b", re.IGNORECASE)
_WEAK = re.compile(r"\b(it|them|that|those|these|there|its|their|one)\b", re.IGNORECASE)
# Requests that say "that" and are understood as they are: they have jobs of their own.
_OWN_JOB = re.compile(
	r"\b(undo|revert|restore|forget|remember|memori[sz]e|don'?t forget|what is that|what's that|what is this|"
	r"put (it|that) back|stop (it|that)|cancel (it|that))\b", re.IGNORECASE)
_QUESTION = re.compile(
	r"^\s*(?:what|which|who|where|when|how|why|is|are|do|does|did|can|could|will|would|should)\b|\?\s*$", re.IGNORECASE)
_CONNECTS = re.compile(r"\b(and|then|after that)\b|[;,]", re.IGNORECASE)
# Small words a rewritten request may have though nobody said them.
_GLUE = frozenset((
	"the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and", "or", "my", "me", "is", "are", "this", "that",
	"it", "its", "from", "by", "as", "be", "do", "does", "what", "which", "how", "please", "file", "folder", "called",
	"named", "window", "program", "setting", "button", "link", "one", "now", "again", "also", "about", "i", "you", "into",
	"up", "down", "out", "off", "onto", "there", "here", "then", "all", "them", "these", "those", "item", "page", "can",
	"tell", "say", "show", "open", "click", "read", "go", "set", "make", "turn", "change", "find", "want", "have", "has",
	"was", "were", "will", "would", "should", "could", "than", "so", "if", "not", "no", "yes", "more", "less"))
_POINTING = frozenset((
	"first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "last", "next", "other",
	"same", "previous", "number", "ones", "another", "each", "either", "both", "two", "three", "four", "five", "too", "well"))
SYSTEM = (
	"You help VisionClaw, an assistant inside the NVDA screen reader for a blind person. The user made a request, got "
	"an answer, and now says something that may lean on them. Write what the user wants now as one full request that "
	"can be understood alone. Rules: Use the user's own words wherever you can. Where the new request says it, that, "
	"them, the same, or the first, second or last one, write the thing that is meant, with the exact name it has in "
	"the earlier request or its answer. Add nothing that was not said. If the new request can already be understood "
	"alone, copy it unchanged.")
# The same asked about another thing: the smallest question that does it. The model is given the earlier request
# and the new thing, and writes the earlier request again about the new thing.
ABOUT_SYSTEM = (
	"You help VisionClaw, an assistant inside the NVDA screen reader for a blind person. The user made a request, and "
	"now wants the same for another thing. Write the earlier request again, with the new thing in the place of what "
	"it was about. Keep every other word of the earlier request. Add nothing else.")
# A thing meant by its place in a list ("the third one") or by "it", where the answer names things.
THING_SYSTEM = (
	"You help VisionClaw, an assistant inside the NVDA screen reader for a blind person. The user got an answer that "
	"names things, and now speaks of one of them without its name: the first, second or last one, or it. Write the "
	"new request again with the exact name of that thing, as the answer has it, in the place of those words. Keep "
	"every other word of the new request. Add nothing else.")
SCHEMA = {
	"type": "object",
	"properties": {"request": {"type": "string", "maxLength": REWRITE_CHARS}},
	"required": ["request"],
}
NOTHING_BEFORE = "There is no earlier request in this session, so there is nothing to do again. Say what you want in full."
NOTHING_SAID = "VisionClaw has not answered anything yet in this session."


class Last:
	"""The request before this one: what was asked, written out in full; what was answered; when it ended, on
	a clock that only goes forward; and whether it was done."""

	def __init__(self, request, answer="", when=0.0, done=True):
		self.request = " ".join(str(request or "").split())
		self.answer = " ".join(str(answer or "").split())
		self.when = when
		self.done = done


def _clean(text):
	return " ".join(str(text or "").split())


# --- A thing meant by its place in the list of the last answer ---

_PLACES = {
	"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "sixth": 5, "seventh": 6, "eighth": 7, "ninth": 8,
	"tenth": 9, "last": -1, "one": 0, "two": 1, "three": 2, "four": 3, "five": 4, "six": 5, "seven": 6, "eight": 7,
	"nine": 8, "ten": 9}
_NTH = re.compile(
	r"\b(?:the )?(?P<word>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last)"
	r"(?: (?:one|ones|item|thing|file|folder|window|link|button|result|entry|program|heading|line|option))?\b"
	r"|\b(?:number|item|no\.?) (?P<number>one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})\b", re.IGNORECASE)
_NUMBERED = re.compile(r"(?:^|(?<=[\s:]))(\d{1,2})\.\s+(.+?)(?=\s+\d{1,2}\.\s+\S|$)")
NAME_CHARS = 80


def listed(answer):
	"""The things an answer lists with numbers, in order: "1. setup.exe, 5 MB ... 2. report.pdf, 120 KB ..." gives
	setup.exe and report.pdf. Each is the item's text up to its first comma. [] when the answer has no list that
	counts 1, 2, 3."""
	found = _NUMBERED.findall(_clean(answer))
	if len(found) < 2 or [int(number) for number, _text in found] != list(range(1, len(found) + 1)):
		return []
	names = []
	for _number, text in found:
		name = text.split(", ")[0].strip().rstrip(".;").strip()
		if not name or len(name) > NAME_CHARS:
			return []
		names.append(name)
	return names


def nth(request, last):
	"""For a request that names a thing by its place ("open the second one"): (the request with the thing's name in
	its place, "") when the last answer lists things with numbers; (None, a sentence) when it lists fewer than that;
	(None, "") when plain code cannot tell."""
	text = _clean(request)
	hit = _NTH.search(text)
	if hit is None:
		return None, ""
	names = listed(last.answer)
	if not names:
		return None, ""
	word = (hit.group("word") or hit.group("number")).lower()
	index = _PLACES.get(word)
	if index is None:
		index = int(word) - 1
	if not -1 <= index < len(names):
		return None, f"The answer before listed {len(names)} things, so there is no such one. Say its name, or its number up to {len(names)}."
	full = (text[:hit.start()] + names[index] + text[hit.end():]).strip()
	# "And the second one?" alone says nothing to do: that is no request plain code can stand behind.
	# The user's own words must begin a thing to do; the name put in may itself look like one ("report.pdf").
	if not computer.STARTS_ACT.match(text):
		return None, ""
	return full, ""


def _words(text):
	return re.findall(r"[a-z0-9][a-z0-9+#'.-]*[a-z0-9+#]|[a-z0-9]", str(text or "").lower())


def isQuestion(request):
	return bool(_QUESTION.search(_clean(request)))


def kind(request, last=None, age=None):
	"""What kind of follow-up a request is, or None for a request that stands alone. age: the seconds since the
	request before ended, or None when there was none. A request that leans on the one before in clear words
	counts whenever it comes; one that only may lean on it counts while the one before is recent."""
	text = _clean(request)
	if not text:
		return None
	if _SAY_AGAIN.match(text):
		return SAY_AGAIN
	if _AGAIN.match(text):
		return AGAIN
	if last is None or age is None:
		return None
	recent, soon = age <= FOLLOW_SECONDS, age <= SOON_SECONDS
	if _OWN_JOB.search(text):
		return None
	if recent and _AGAIN_IN.match(text):
		return AGAIN_IN
	if recent and _MORE.match(text):
		return MORE
	if recent and _OTHER_WAY.match(text):
		return OTHER_WAY
	if recent and _DIRECTION.match(text):
		return DIRECTION
	count = len(text.split())
	about = _ABOUT.match(text)
	if about and not _STRONG.search(text):
		# "And also turn off the typing echo" is a whole request with a word in front of it.
		what = about.group("what")
		if computer.STARTS_ACT.match(what) and len(what.split()) >= 2 and not _WEAK.search(what):
			return None
	if recent and count <= 14 and (about or _STRONG.search(text)):
		return ABOUT if about and not _STRONG.search(text) else REFERS
	if soon and count <= 5 and _WEAK.search(text) and not _CONNECTS.search(text):
		return REFERS
	return None


def opposite(request):
	"""A request with its direction turned round: "make NVDA speak faster" becomes "make NVDA speak slower".
	None when it names no direction, or more than one."""
	text = _clean(request)
	# A question asks for nothing that has a direction: "what is on my screen" is not turned into "off".
	if isQuestion(text):
		return None
	switched = re.search(r"\b(turn|switch|toggle|put|set)\w*\b", text, re.IGNORECASE)
	hits = [
		hit for hit in re.finditer(r"[A-Za-z]+", text)
		if hit.group(0).lower() in _OPPOSITE and (switched or hit.group(0).lower() not in ("on", "off"))]
	# "Turn the volume up" has one; "turn it on and the volume up" has two, and which is meant is not known.
	if len(hits) != 1:
		return None
	hit = hits[0]
	return text[:hit.start()] + _matchCase(hit.group(0), _OPPOSITE[hit.group(0).lower()]) + text[hit.end():]


def _matchCase(old, new):
	return new.capitalize() if old[:1].isupper() else new


def toward(request, way):
	"""A request with its direction set to the one the user now names: after "make the pitch higher", "lower"
	gives "make the pitch lower". None when the request has no word of that kind."""
	text = _clean(request)
	way = way.lower()
	for hit in re.finditer(r"[A-Za-z]+", text):
		word = hit.group(0).lower()
		if word == way:
			return text
		if word in _OPPOSITE and (_OPPOSITE[word] == way or _OPPOSITE.get(way) == word or _sameKind(word, way)):
			return text[:hit.start()] + _matchCase(hit.group(0), way) + text[hit.end():]
	return None


def _sameKind(one, two):
	"""Whether two direction words are about the same thing: quicker and faster, up and higher, down and lower."""
	kinds = (
		{"faster", "quicker", "slower"}, {"louder", "quieter"}, {"higher", "lower", "up", "down", "raise"},
		{"bigger", "larger", "smaller"}, {"brighter", "darker", "dimmer"})
	return any(one in group and two in group for group in kinds)


def _inProgram(last, where):
	"""The request before, done again for another program."""
	where = re.sub(r"^(?:the|my)\s+(?=\w)", "", _clean(where), flags=re.IGNORECASE).strip(" .!?")
	if not where or re.fullmatch(r"(it|that|this|there|here|me|you|us)", where, re.IGNORECASE):
		return None
	previous = last.request
	if isQuestion(previous):
		# A question is asked again about the other program; nothing is switched to.
		return f"{previous.rstrip(' ?.!')} in {where}?"
	from . import profiles
	scoped = profiles.scopeOf(previous)
	if scoped is not None:
		# A setting for one program can only be changed while that program is in front.
		rest = profiles.without(previous).rstrip(" .!?")
		return f"Switch to {where}. {rest[:1].upper() + rest[1:]} only in this program."
	return f"Switch to {where}. {previous[:1].upper() + previous[1:]}"


def resolve(request, last, age=None):
	"""What plain code makes of a request that follows the one before it:
	(kind, the request written out in full or None, what to tell the user at once or "").
	kind None: the request stands alone. A kind in PLAIN with a request: plain code is certain. ABOUT or REFERS, or
	a PLAIN kind with no request: a model must write it out (`question`), or the request is kept as it is."""
	found = kind(request, last, age)
	if found is None:
		return None, None, ""
	if found == SAY_AGAIN:
		return found, None, (last.answer if last is not None and last.answer else NOTHING_SAID)
	if last is None:
		return found, None, NOTHING_BEFORE
	text = _clean(request)
	if found == AGAIN:
		return found, last.request, ""
	if found == AGAIN_IN:
		return found, _inProgram(last, _AGAIN_IN.match(text).group("where")), ""
	if found == MORE:
		return found, last.request, ""
	if found == OTHER_WAY:
		return found, opposite(last.request), ""
	if found == DIRECTION:
		hit = _DIRECTION.match(text)
		way = hit.group("way") or _TOO[hit.group("too").lower()]
		return found, toward(last.request, way), ""
	if found == REFERS:
		# "The second one": the thing with that number in the list of the last answer, by plain code.
		full, tell = nth(bare(text), last)
		if full or tell:
			return found, full, tell
	if found == ABOUT:
		# "And maximize it", after "open notepad": what "it" is, is told by the rules that tell it inside one
		# request ("open notepad and maximize it").
		return found, _joined(last.request, _ABOUT.match(text).group("what")), ""
	return found, None, ""


def _joined(before, what):
	"""A thing to do with "it", written with the thing the request before names; None where plain rules cannot
	tell which thing that is."""
	if not _WEAK.search(what) or not computer.STARTS_ACT.match(what):
		return None
	from . import planner
	try:
		parts = planner.plainSplit(f"{before.rstrip(' .!?')} and {what.rstrip(' .!?')}")
	except Exception:
		return None
	if not parts or len(parts) < 2 or _WEAK.search(parts[-1]):
		return None
	return parts[-1]


def newThing(request):
	"""What a follow-up of the kind "and the pitch?" is about: "the pitch"."""
	hit = _ABOUT.match(_clean(request))
	return _clean(hit.group("what")).rstrip(" ?.!") if hit else ""


def strong(request):
	"""Whether a follow-up says clearly that it leans on the request before: then it cannot be used as it stands."""
	text = _clean(request)
	return bool(_ABOUT.match(text) or _STRONG.search(text) or _DIRECTION.match(text))


def ask(request, last, found):
	"""(the system text, the question) for the model that writes a follow-up out in full: the smallest question
	that fits its kind."""
	thing = newThing(request)
	if found == ABOUT and thing and computer.STARTS_ACT.match(thing) and _WEAK.search(thing):
		# "And open it": a thing to do with something the answer names.
		found = REFERS
	if found == ABOUT and thing:
		return ABOUT_SYSTEM, (
			f"The earlier request: \"{last.request[:400]}\"\nThe new thing: \"{newThing(request)[:200]}\"\n"
			"Write the earlier request again about the new thing.")
	if found == REFERS:
		return THING_SYSTEM, (
			f"The answer: \"{last.answer[:700]}\"\nThe new request: \"{bare(request)[:300]}\"\n"
			"Write the new request with the name of the thing that is meant.")
	return SYSTEM, question(request, last)


def question(request, last):
	"""The question to a model that writes a follow-up out in full."""
	return (
		f"The earlier request: \"{last.request[:400]}\"\n"
		f"Its answer: \"{last.answer[:700]}\"\n"
		f"The user now says: \"{_clean(request)[:300]}\"\n"
		"Write what the user wants now as one full request.")


def checked(written, request, last, mustChange=False):
	"""A model's full request, if plain code can stand behind it: every word of it was said by the user, now or
	before, or by VisionClaw in its answer, and it is not the answer itself or empty. mustChange: the follow-up
	leans on the request before in clear words, so a copy of it is no full request. Else None."""
	written = _clean(written).strip("\"' ")
	if not written or len(written) > REWRITE_CHARS:
		return None
	plain = lambda text: " ".join(_words(text))  # noqa: E731
	if mustChange and plain(written) in (plain(request), plain(bare(request))):
		return None
	said = set(_words(request)) | set(_words(last.request)) | set(_words(last.answer))
	mine = _words(written)
	if not mine:
		return None
	made = [word for word in mine if word not in said and word not in _GLUE and not _stemIn(word, said)]
	if made:
		return None
	# The request before, copied, is no follow-up to it.
	if written.lower().rstrip(" .!?") == last.request.lower().rstrip(" .!?"):
		return None
	# It must hold something of what the user said now, or it is the old request again and not a follow-up. Words
	# that only point ("the second one") are written out as what they point to, and need not be in it.
	now = set(_words(request)) - _GLUE - _POINTING
	if now and not (now & set(mine)) and not any(_stemIn(word, set(mine)) for word in now):
		return None
	# An answer copied back is no request.
	if len(mine) > 8 and _clean(last.answer).lower().startswith(written.lower()[:60]):
		return None
	return written


def _stemIn(word, said):
	"""Whether a word is one that was said, in another form: files and file, opened and open."""
	for ending in ("'s", "es", "s", "ed", "ing", "d"):
		if word.endswith(ending) and len(word) - len(ending) >= 3 and word[:-len(ending)] in said:
			return True
	return any(word + ending in said for ending in ("s", "es", "ed", "ing", "'s"))


def background(last):
	"""The request before and its answer, as what is known, for a follow-up that could not be written out in
	full: the model that chooses what to do is told them, and the request itself stays as the user said it."""
	return (
		f"The request before this one was: \"{last.request[:200]}\". Its answer was: \"{last.answer[:300]}\". "
		"This request may lean on them.")


def bare(request):
	"""A request without the word it leans on the one before with: "and open it" is "open it"."""
	text = _clean(request)
	rest = re.sub(r"^(?:and|or|but|also|then|so)\b[, ]+", "", text, count=1, flags=re.IGNORECASE)
	return rest if len(rest.split()) >= 2 else text


def taken(said, full):
	"""What the user is told about how their words were understood."""
	return f"Understood as: {full.rstrip()}" + ("" if full.rstrip()[-1:] in ".!?" else ".")
