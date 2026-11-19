# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - shopping on a web page or in a program, as plain logic. Three things:
#   1. A purchase is always asked about. Which buttons buy, book, pay or order is told from their names
#      (isPurchase); what is to be paid is read from the page word for word (totals); the question says both and
#      that this may not be possible to take back (purchaseQuestion). No model is asked, and nothing is guessed:
#      where the page states no total, the question says that none was found.
#   2. What VisionClaw never types: a card number, a security code, an expiry date, a password, a PIN, a social
#      security or bank account number (isSecret). What the user asks is written to VisionClaw's log and spoken
#      as it is typed, so these stay with the user, who types them.
#   3. The options of a product: a size, a colour, a storage size. What the user's own words ask is read by plain
#      code (optionWish): to choose one or to check which is chosen, by the option's name ("Medium", "256GB") or
#      by its colour ("the dark blue one"). Which option is meant is decided by its name first, and for a swatch
#      with no name by its colour as measured from the pixels (claw/colours.py), never by a model (pickOption).
#      Whether an option is chosen is said only from what the page itself tells NVDA; a click alone proves nothing.
# Every sentence the user is told about this is here. The gathering, measuring and pressing is shoptools.py.
# No NVDA dependencies.

import re

from . import colours

CHOOSE, CHECK = "choose", "check"
# How an option was found: by its name, by a colour its own name says, or by its colour measured from the picture.
BY_NAME, BY_LABEL_COLOUR, BY_MEASURED = "name", "label colour", "measured colour"

# --- A purchase ---

# Names that buy, book, pay or order as soon as they are pressed. Why each is here:
# - "place order", "submit order", "complete purchase", "confirm booking" and their like are the last button of a
#   checkout: after it the order exists.
# - "buy now", "buy", "buy with ..." and "order now": many shops take the saved card at once.
# - "pay", "pay now", "pay 45.99", "... and pay": money moves.
# - "book", "book now", "reserve", "reserve now": a room, a table or a seat is held in the user's name, often with
#   a fee for cancelling.
# - "purchase" as the whole name or with "now": the same as buy.
# - "place bid", "bid now": a bid binds.
# - "send money", "send payment", "transfer money": money moves.
# - "start free trial", "start subscription", "start membership": a card is charged later unless it is cancelled.
_PURCHASE = (
	r"\b(?:place|submit|complete|confirm|finish|finali[sz]e|send)\s+(?:(?:my|your|the|this)\s+)?(?:order|purchase|booking|reservation|payment)\b",
	r"\b(?:confirm|agree|continue|book|order|submit|reserve)\s*(?:and|&|\+)\s*pay\b",
	r"^\s*buy(?:\s+(?:it\s+)?now|\s+it|\s+this|\s+with\b.*|\s+tickets?|\s+for\b.*)?\s*$",
	r"\bbuy\s+(?:it\s+)?now\b",
	r"^\s*order\s+now\b|\border\s+with\s+obligation\s+to\s+pay\b",
	r"^\s*pay\b(?!\s+(?:later\s+)?(?:options|methods|info|information|details|settings)\b)",
	r"^\s*(?:book|reserve)(?:\s+(?:now|it|this|my|a|an|your|the)\b.*)?\s*$",
	r"^\s*purchase(?:\s+(?:now|it|this|tickets?))?\s*$",
	r"\b(?:place|submit|confirm)\s+(?:(?:my|your|a)\s+)?bid\b|^\s*bid\s+now\b",
	r"\b(?:send|transfer)\s+(?:money|payment|funds)\b",
	r"\bstart\s+(?:(?:my|your)\s+)?(?:free\s+)?(?:trial|subscription|membership)\b",
	r"^\s*donate(?:\s+now)?\s*$",
)
# Names that sound alike and buy nothing. Why each is here:
# - "checkout", "proceed to checkout", "continue to payment", "review order": they lead to the pages where the
#   address and the payment are given and shown; nothing is bought until the last button there.
# - "add to cart", "add to basket", "add to bag": the thing is only put aside.
# - "order history", "order details", "payment methods", "booking reference": they only show something.
# - "subscribe" alone: it is the name of newsletter sign-ups everywhere, which cost nothing.
_NOT_PURCHASE = re.compile(
	r"\b(?:history|details|status|tracking|summary|reference|confirmation|methods?|options|settings|information|help|"
	r"policy|address book|guest book)\b|\b(?:add|added)\s+to\b|\b(?:view|edit|review|update|change|cancel|track|print|"
	r"continue to|proceed to|go to|back to)\b|\bcheck ?out\b", re.IGNORECASE)
_PURCHASE_RE = tuple(re.compile(pattern, re.IGNORECASE) for pattern in _PURCHASE)
# Money as pages write it: a sign or a code before or after the number.
_SIGN = r"(?:[$£€¥₹]|\b(?:usd|eur|gbp|cad|aud|nzd|chf|jpy|inr|sek|nok|dkk|pln|rs\.?|us\$|c\$|a\$))"
_NUMBER = r"\d{1,3}(?:[,.  ]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
MONEY = re.compile(
	rf"{_SIGN}\s?(?:{_NUMBER})|(?:{_NUMBER})\s?(?:[$£€¥₹]|\b(?:usd|eur|gbp|cad|aud|nzd|chf|jpy|inr|sek|nok|dkk|pln|kr|zł|"
	r"dollars?|euros?|pounds?)\b)", re.IGNORECASE)
# The words that say a line is what is to be paid, the surest first.
_TOTAL_WORDS = (
	r"\b(?:order|grand|final|payment|booking|trip|cart|basket|estimated)\s+total\b|\btotal\s+(?:due|to pay|price|cost|amount|charge|payable)\b|"
	r"\bamount\s+(?:due|to pay|payable)\b|\bbalance\s+due\b|\b(?:you|to)\s+pay\b|\bdue\s+(?:today|now)\b",
	r"\btotal\b",
)
# A total of something else, or only a part of what is paid.
_NOT_TOTAL = re.compile(
	r"\bsub[- ]?total\b|\btotal\s+(?:savings?|saved|discount|items?|reviews?|ratings?|results?|points|miles|nights?|"
	r"guests?|passengers?|travell?ers?|rooms?|quantity|qty|weight)\b|\byou\s+saved?\b", re.IGNORECASE)
MAX_TOTALS = 3
_LINE_CHARS = 140
PURCHASE_CHOICES = ("Yes, press it", "No, do not press it")

# --- What is never typed ---

# Why each is here is in the comment at the top. "PIN code" and "pincode" alone are left out: in India that is the
# postal code. "Security question" is left out: its answer is no number that pays.
_SECRET = re.compile(
	r"\b(?:card|cc)\s*(?:number|no\b|num\b|#)|\bcard\s?number\b|\b(?:credit|debit|payment|bank)\s+card\b(?!\s+(?:holder|name|type))|"
	r"\bsecurity\s+code\b|\bcard\s+(?:verification|security|code)\b|\bcvv2?\b|\bcvc2?\b|\bcvn\b|\bcsc\b|\bcid\b|"
	r"\bexpir\w*\b|\bexp\.?\s*(?:date|month|year)\b|\bvalid\s+(?:thru|through|until)\b|\bmm\s?/\s?yy(?:yy)?\b|"
	r"\bpass\s?(?:word|code|phrase)s?\b|\bpin\b(?!\s?code)|\b(?:card|atm|debit|security|bank)\s+pin\s?code\b|"
	r"\bsocial\s+security\b|\bssn\b|\bnational\s+insurance\s+(?:number|no\b)|"
	r"\b(?:bank\s+)?account\s+(?:number|no\b|#)|\brouting\s+(?:number|no\b)|\biban\b|\bsort\s+code\b|\bswift\b|\bbic\b",
	re.IGNORECASE)
SECRET_REFUSAL = (
	"VisionClaw does not type this for you. A card number, a security code, an expiry date, a password, a PIN, or a "
	"social security or bank account number would be written to VisionClaw's log with your request and spoken as it "
	"is typed. Ask VisionClaw to put the focus in the field, then type it yourself.")

# --- The options of a product ---

# What kind of option the words speak of, when they say.
_GROUPS = (
	("size", r"\bsizes?\b"), ("colour", r"\bcolou?rs?\b|\bshades?\b"),
	("storage", r"\bstorage\b|\bcapacity\b|\bmemory\b|\b\d+\s?(?:gb|tb|mb)\b"),
	("style", r"\bstyles?\b"), ("material", r"\bmaterials?\b|\bfabrics?\b"), ("finish", r"\bfinish(?:es)?\b"),
	("fit", r"\bfit\b"), ("width", r"\bwidths?\b"), ("length", r"\blengths?\b"), ("flavour", r"\bflavou?rs?\b"),
	("scent", r"\bscents?\b"), ("model", r"\bmodels?\b"),
)
# Words that say an option is meant without saying which kind.
_OPTION_WORDS = re.compile(r"\b(options?|swatch(?:es)?|variants?|variations?|choices?)\b", re.IGNORECASE)
_ONE = re.compile(r"\bones?\b", re.IGNORECASE)
# Sizes and colours of things that are no option of a product; those are other jobs of VisionClaw.
_NOT_OPTION = re.compile(
	r"\b(fonts?|text|letters?|windows?|files?|folders?|screen|icons?|zoom|cursor|pointer|mouse|braille|speech|voice|"
	r"nvda|disk|drive|paper|margins?|pictures?|images?|photos?|highlight\w*|background|theme|dark mode|volume|"
	r"document|paragraphs?|cells?|rows?|columns?|tables?|"
	# VisionClaw's own models come in sizes too: "should I switch to a smaller model" is about them.
	r"models?|qwen|quants?|llms?|visionclaw|engine|context|graphics card|gpu|memory|ram)\b", re.IGNORECASE)
_CHECKS = re.compile(
	r"\b(?:is|are|was)\b.*\b(?:selected|chosen|picked|set|active|checked|ticked)\b"
	r"|\b(?:confirm|verify|check|make sure|ensure|see)\b.*\b(?:is|are|that|whether|if)\b.*\b(?:set|selected|chosen|picked|active)\b"
	r"|^\s*(?:which|what)\b.*\b(?:selected|chosen|picked|set|active|is it)\b"
	r"|\b(?:tell me|say)\s+(?:which|what|whether|if)\b.*\b(?:selected|chosen|picked|set|active)\b", re.IGNORECASE)
_ASKS_HOW = re.compile(r"\bhow (?:do|can|would|should|could) (?:i|we|you|one)\b|\bhow to\b", re.IGNORECASE)
_QUOTED = re.compile(r"[\"“]([^\"“”]{1,60})[\"”]|(?<!\w)['‘]([^'‘’]{1,60}?)['’](?!\w)")
# Words of a request that are no part of an option's name.
_FILLER = frozenset((
	"click", "select", "choose", "pick", "tap", "press", "hit", "set", "change", "switch", "get", "take", "want", "need",
	"i", "i'd", "id", "like", "would", "to", "the", "a", "an", "that", "this", "it", "its", "one", "ones", "option", "options",
	"swatch", "swatches", "button", "buttons", "variant", "variants", "variation", "choice", "choices", "please", "for",
	"me", "my", "on", "in", "of", "at", "page", "product", "item", "is", "are", "was", "be", "been", "selected", "chosen",
	"picked", "active", "checked", "ticked", "current", "currently", "confirm", "verify", "check", "make", "sure", "ensure",
	"see", "whether", "if", "which", "what", "tell", "say", "show", "and", "then", "now", "can", "you", "could", "with",
	"as", "so", "size", "sizes", "colour", "color", "colours", "colors", "shade", "shades", "storage", "capacity",
	"memory", "style", "styles", "finish", "material", "fabric", "fit", "width", "length", "flavour", "flavor", "scent",
	"model", "here", "there", "right", "just", "also", "go", "ahead", "do"))
# What a label says besides its name: that the option cannot be had, or that it is the chosen one.
_GONE = re.compile(r"\b(?:sold out|out of stock|unavailable|not available|currently unavailable|no longer available)\b", re.IGNORECASE)
_CHOSEN_WORD = re.compile(r"\b(?:selected|chosen|current selection|currently selected)\b", re.IGNORECASE)
# Sizes as letters and as words.
_SIZES = {
	"xxs": "extra extra small", "2xs": "extra extra small", "xs": "extra small", "s": "small", "m": "medium", "l": "large",
	"xl": "extra large", "xxl": "extra extra large", "2xl": "extra extra large", "xxxl": "extra extra extra large",
	"3xl": "extra extra extra large", "sm": "small", "med": "medium", "lg": "large", "x-large": "extra large",
	"x-small": "extra small", "xlarge": "extra large", "xsmall": "extra small"}
_LABEL_NOISE = frozenset(("size", "sizes", "colour", "color", "colours", "colors", "storage", "capacity", "option", "swatch",
	"select", "choose", "style", "variant"))
# The kinds of control an option of a product can be, by NVDA's own names for them.
OPTION_ROLES = ("RADIOBUTTON", "TOGGLEBUTTON", "BUTTON", "LISTITEM", "LINK", "GRAPHIC", "CHECKBOX", "RADIOMENUITEM",
	"TAB", "SWITCH", "MENUITEM", "TREEVIEWITEM")
# Of these, the kinds whose state says for certain whether they are chosen: without the state they are not.
STATED_ROLES = ("RADIOBUTTON", "TOGGLEBUTTON", "CHECKBOX", "RADIOMENUITEM", "TAB", "SWITCH")
CHOSEN_STATES = ("CHECKED", "SELECTED", "PRESSED", "ON")
# A swatch with no name is a short label at most; anything longer is no swatch to measure.
SWATCH_LABEL_CHARS = 30
MAX_SAID = 12
MEASURED_NOTE = "A colour said as measured was taken from the pixels of the picture; the page itself does not name it."


def isPurchase(name):
	"""Whether a button with this name buys, books, pays or orders as soon as it is pressed. "Checkout" does not:
	it only leads on; see the comments at _PURCHASE and _NOT_PURCHASE for each decision."""
	text = " ".join(str(name or "").replace(" ", " ").split())
	text = re.sub(r"\s*(?:button|link)\s*$", "", text, flags=re.IGNORECASE).strip(" .!:>›→-")
	if not text:
		return False
	# What only shows something or leads on is never a purchase, unless it also says "and pay" or "place order".
	strong = _PURCHASE_RE[0].search(text) or _PURCHASE_RE[1].search(text)
	if _NOT_PURCHASE.search(text) and not strong:
		return False
	return any(pattern.search(text) for pattern in _PURCHASE_RE)


def _lines(text):
	if isinstance(text, str):
		text = text.splitlines()
	return [" ".join(str(line or "").replace(" ", " ").split()) for line in text or ()]


def totals(lines):
	"""The lines of a page's text that state what is to be paid, word for word, the surest first, at most
	MAX_TOTALS: a line with a word for the total and an amount of money. lines: the page's text, as lines or as
	one text. Where the word and the amount stand on two lines, as pages often lay them out, both are given as one."""
	lines = [line for line in _lines(lines) if line]
	found = []
	for rank, words in enumerate(_TOTAL_WORDS):
		pattern = re.compile(words, re.IGNORECASE)
		for index, line in enumerate(lines):
			if not pattern.search(line) or _NOT_TOTAL.search(line) or len(line) > _LINE_CHARS:
				continue
			said = line
			if not MONEY.search(line):
				# The amount alone on the next line belongs to this one.
				after = lines[index + 1] if index + 1 < len(lines) else ""
				if not (MONEY.search(after) and len(after) <= 24):
					continue
				said = f"{line} {after}"
			if said not in [text for _rank, _index, text in found]:
				found.append((rank, index, said))
	found.sort(key=lambda item: (item[0], item[1]))
	return [text for _rank, _index, text in found[:MAX_TOTALS]]


def purchaseQuestion(name, found):
	"""The question before a button that buys, books or pays is pressed: its name, what the page says is to be
	paid, word for word, or that the page states no total, and that this may not be possible to take back."""
	name = " ".join(str(name or "").split()) or "this button"
	if found:
		paid = "The page says: " + " ".join(line if line[-1:] in ".!?" else line + "." for line in found)
	else:
		paid = "VisionClaw found no total on the page, so make sure you know what is to be paid."
	return f"\"{name}\" buys, books or pays. {paid} Press it? This may not be possible to take back."


def notPressed(name):
	return f"\"{name}\" was not pressed, so nothing was bought, booked or paid."


def isSecret(fieldName):
	"""Whether a field is one VisionClaw never types into: a card number, a security code, an expiry date, a
	password, a PIN, a social security or bank account number."""
	return bool(_SECRET.search(" ".join(str(fieldName or "").split())))


def _tokens(text):
	return re.findall(r"[A-Za-z0-9][A-Za-z0-9./+'-]*", text or "")


def optionWish(part):
	"""What the user's own words ask about an option of a product, or None when they speak of none:
	{"what": CHOOSE or CHECK; "name": the option's own words ("Medium", "256GB", "dark blue") or None; "colour": the
	plain name of the one colour the words name, or None; "group": the kind of option when the words say it (size,
	colour, storage, ...), or None}. A request that only asks how something is done is no wish, and neither is one
	about the size or colour of something that is no product's option: a font, a window, a file, NVDA itself."""
	text = " ".join(str(part or "").split())
	if not text or _ASKS_HOW.search(text) or _NOT_OPTION.search(text):
		return None
	low = text.lower()
	group = next((name for name, pattern in _GROUPS if re.search(pattern, low)), None)
	named = colours.wanted(text)
	# Two colours in one name, as in "rose gold", are a name and no colour to measure.
	colour = named[0] if len(named) == 1 else None
	what = CHECK if _CHECKS.search(text) else CHOOSE
	quoted = _QUOTED.search(text)
	if quoted:
		name = (quoted.group(1) or quoted.group(2)).strip(" ,.;:")
	else:
		name = " ".join(word for word in _tokens(text) if word.lower().strip("'") not in _FILLER).strip(" ,.;:")
	name = name or None
	# The words must speak of a product's option: its kind (size, colour, storage), a swatch or a variant, or a
	# colour with "one" or "option". The word option alone does not: "the Options button", "the second option"
	# and "the options menu" are things of any program, and are clicked by their names.
	# "The green one": the colour word and "one" side by side. "One of the boxes has a red border" is about no option.
	colourOne = any(re.match(r"\s+ones?\b", text[hit.end():], re.IGNORECASE) for hit in colours._ASKED.finditer(text))
	cue = (group is not None or re.search(r"\b(swatch(?:es)?|variants?|variations?)\b", low)
		or (named and (colourOne or _OPTION_WORDS.search(text))))
	if not cue:
		return None
	# The word colour alone names no option: "set it to scan in colour" is a setting of a scanner. A colour, a
	# swatch or the word option must be there with it.
	if (group == "colour" and what == CHOOSE and not named and not _OPTION_WORDS.search(text)
			and not re.search(r"\b(?:the|a|an|that|this)\s+[\w' -]{1,30}?\s+colou?r\b|\bcolou?r\s+(?:called|named)\b", low)):
		return None
	if what == CHOOSE and not name and not colour:
		return None
	if what == CHOOSE and not re.search(
			r"\b(click|select|choose|pick|tap|press|hit|set|change|switch|take|want|get|go with|i'll have)\b", low):
		return None
	return {"what": what, "name": name, "colour": colour, "group": group}


def _norm(text):
	"""A label or a name as the words that tell it apart: lower case, "256 GB" as one word, sizes written out,
	and without the words every label of its kind has."""
	low = (text or "").lower()
	low = _GONE.sub(" ", low)
	low = _CHOSEN_WORD.sub(" ", low)
	low = re.sub(r"(\d)\s+(gb|tb|mb|oz|ml|cm|mm|kg|lb|lbs)\b", r"\1\2", low)
	words = []
	for word in re.findall(r"[a-z0-9]+(?:[./-][a-z0-9]+)*", low):
		if word in _LABEL_NOISE:
			continue
		words.extend(_SIZES.get(word, word).split())
	return tuple(words)


def _nameScore(name, label):
	"""How well a label is the option that was named: 3 the same words, 2 the name's words in a row inside a
	longer label, 0 not it."""
	want, have = _norm(name), _norm(label)
	if not want or not have:
		return 0
	if want == have:
		return 3
	for start in range(len(have) - len(want) + 1):
		if have[start:start + len(want)] == want:
			return 2
	return 0


def chosenOf(role, states, label=""):
	"""Whether a control is the chosen option, from what the page says of it: True, False, or None when the page
	does not say. A radio button without its state is not chosen; a plain button or link without one is unknown."""
	states = set(states or ())
	if states & set(CHOSEN_STATES):
		return True
	if _CHOSEN_WORD.search(label or ""):
		return True
	if role in STATED_ROLES:
		return False
	if role in ("LISTITEM", "TREEVIEWITEM", "MENUITEM") and "SELECTABLE" in states:
		return False
	return None


def labelColours(label):
	"""The colours an option's own name says, as plain names: "Navy" and "Forest Green" say one, "Midnight" says
	none. A longer label that only has a colour's word in it, as "Red hot deals", is no option named by its colour:
	at least half of the label's words must belong to the colour's name."""
	named = colours.wanted(label)
	if not named:
		return []
	words = [word for word in re.findall(r"[a-z]+", _CHOSEN_WORD.sub(" ", _GONE.sub(" ", (label or "").lower()))) if word not in _LABEL_NOISE]
	if not words:
		return []
	count = 0
	for index, word in enumerate(words):
		before = f"{words[index - 1]} {word}" if index else ""
		after = f"{word} {words[index + 1]}" if index + 1 < len(words) else ""
		if colours.wanted(word) or word in ("dark", "deep", "light", "pale", "bright") or before in colours.ASKED or after in colours.ASKED:
			count += 1
	return named if count * 2 >= len(words) else []


def needsColour(control):
	"""Whether a control may be a swatch whose colour must be measured: an option's kind of control with no name,
	or a short one whose name says no colour."""
	label = control.get("label") or ""
	return control.get("role") in OPTION_ROLES and len(label) <= SWATCH_LABEL_CHARS and not labelColours(label)


def measureFirst(control):
	"""The order in which controls are measured where there are more than can be: those with no name first, then
	those inside something that is about colour, then buttons and their like, and links last."""
	inside = (control.get("group") or "").lower()
	if not (control.get("label") or "").strip():
		return 0
	if re.search(dict(_GROUPS)["colour"], inside):
		return 1
	return 3 if control.get("role") in ("LINK", "MENUITEM", "TAB", "TREEVIEWITEM") else 2


def _asOption(control):
	role = control.get("role") or ""
	label = " ".join(str(control.get("label") or "").split())
	states = control.get("states") or ()
	own = labelColours(label)
	measured = control.get("colour")
	return {
		"label": label, "colour": own[0] if own else measured,
		"measured": bool(measured) and not own, "chosen": chosenOf(role, states, label),
		"usable": "UNAVAILABLE" not in states and not _GONE.search(label), "role": role,
		"group": " ".join(str(control.get("group") or "").split()), "ref": control.get("ref")}


def asOptions(controls, wish):
	"""The controls of a page or window that can be the option the wish is about, as options. controls: [{"label":
	the name or text, "role": NVDA's name for its kind, "states": its states, "group": the name of what it is
	inside or "", "colour": its measured colour as a plain name or None, "ref": what presses it}]. Each option is
	{"label", "colour", "measured": whether the colour is from pixels, "chosen", "usable", "role", "group", "ref"}.
	By name: the controls whose label has the name. By colour: those whose label names a colour that fits, and
	those that were measured. To check: also the other options of the same group, so that the one that is chosen
	can be said; and with no name, every control of the kind of option the words say."""
	found = []
	name, colour, group = wish.get("name"), wish.get("colour"), wish.get("group")
	usable = [control for control in controls if (control.get("role") or "") in OPTION_ROLES]
	for control in usable:
		option = _asOption(control)
		fits = bool(name and _nameScore(name, option["label"]))
		if colour and (any(colours.fit(colour, own) for own in labelColours(option["label"])) or option["measured"]):
			fits = True
		if not name and not colour and group and re.search(dict(_GROUPS)[group], option["group"].lower()):
			fits = True
		if fits:
			found.append(option)
	# Where the words say the kind and some of what was found is inside something of that kind, only those count.
	if group:
		inGroup = [option for option in found if re.search(dict(_GROUPS)[group], option["group"].lower())]
		if inGroup:
			found = inGroup
	if wish.get("what") == CHECK and found:
		groups = {option["group"] for option in found if option["group"]}
		known = {id(option["ref"]) for option in found}
		for control in usable:
			inside = " ".join(str(control.get("group") or "").split())
			if inside in groups and id(control.get("ref")) not in known:
				found.append(_asOption(control))
	return found


def pickOption(wish, options):
	"""Which option the wish means: (its index, how it was found: BY_NAME, BY_LABEL_COLOUR or BY_MEASURED), or
	(None, the indexes of the options to ask about; empty when none fits). By its name first: the same words win
	over a longer label that only has them, so "Medium" is never "Medium Tall" where both are there. Then by
	colour: a colour the option's own name says, else the colour measured from its pixels."""
	name, colour = wish.get("name"), wish.get("colour")
	if name:
		scores = [_nameScore(name, option.get("label") or "") for option in options]
		best = max(scores, default=0)
		# A name that is only a colour ("red", "dark blue") is an option's name only where an option is called
		# exactly that; a longer label that merely has the word in it is not the red one.
		onlyColour = colour is not None and all(
			colours.wanted(word) or word in ("dark", "deep", "light", "pale", "bright") for word in name.lower().split())
		if best and not (onlyColour and best < 3):
			indexes = [index for index, score in enumerate(scores) if score == best]
			if len(indexes) > 1:
				# The same option twice, as a radio button and the label beside it: the one whose state is known.
				stated = [index for index in indexes if options[index].get("chosen") is not None]
				same = len({_norm(options[index].get("label") or "") for index in indexes}) == 1
				if same and len(stated) == 1:
					indexes = stated
				elif same and best == 3:
					indexes = indexes[:1]
			if len(indexes) == 1:
				return indexes[0], BY_NAME
			return None, indexes
	if colour:
		known = [option.get("colour") or "" for option in options]
		index, others = colours.closest(colour, known)
		if index is not None:
			return index, BY_MEASURED if options[index].get("measured") else BY_LABEL_COLOUR
		return None, list(others)
	return None, []


def namedExactly(wish, options):
	"""Whether one of the options has the very name that was asked for, and not only a longer name with it inside."""
	return bool(wish.get("name")) and any(_nameScore(wish["name"], option.get("label") or "") == 3 for option in options)


def optionSaid(option, number=None):
	"""An option in words: the option "Midnight", measured dark blue; an option with no name, measured red."""
	label = option.get("label") or ""
	said = f"the option \"{label}\"" if label else "an option with no name"
	if number is not None and not label:
		said += f", number {number} of those found"
	if option.get("measured") and option.get("colour"):
		said += f", measured {option['colour']}"
	if option.get("where"):
		said += f", {option['where']}"
	return said


def _measuredNote(options):
	return f" {MEASURED_NOTE}" if any(option.get("measured") and option.get("colour") for option in options) else ""


def chooseQuestion(option, number=None):
	"""Asked before an option is pressed."""
	chosen = " The page marks it as chosen already." if option.get("chosen") else ""
	return f"Choose {optionSaid(option, number)}?{chosen}"


def whichQuestion(wish):
	wanted = wish.get("name") or wish.get("colour") or "that"
	return f"More than one option fits \"{wanted}\". Which one do you mean?"


def choices(options, indexes):
	"""The options to ask about, each in words, for the user to choose from."""
	said = []
	for index in indexes:
		option = options[index]
		text = optionSaid(option, index + 1)
		said.append(text[0].upper() + text[1:])
	return said


def unusableText(option):
	return (
		f"Nothing was pressed: {optionSaid(option)} is there, but the page shows it as not available, which usually "
		"means it is sold out.")


def doneText(option, after, pictureChanged=None, number=None):
	"""What was done, and what the page says of the option now. after: whether the page marks it as chosen now
	(None when the page does not say). pictureChanged: where the page says nothing, whether the option's picture
	changed after the press (None when that could not be compared)."""
	said = f"Pressed {optionSaid(option, number)}."
	if after is True:
		said += " The page now marks it as chosen."
	elif after is False:
		said += " The page does not mark it as chosen, so the press may not have been taken. Ask to check it again."
	elif pictureChanged is True:
		said += " The page does not say whether it is chosen, but its picture changed after the press, as it does when an option is taken."
	elif pictureChanged is False:
		said += " The page does not say whether it is chosen, and nothing VisionClaw can see changed, so it may not have been taken."
	else:
		said += " The page does not say whether it is chosen, so VisionClaw cannot tell you that it is."
	return said + _measuredNote([option])


def checkText(wish, options):
	"""Whether the option the words name is chosen, or which options are, from what the page itself says. Nothing
	is pressed for this."""
	chosen = [option for option in options if option.get("chosen")]
	if wish.get("name") or wish.get("colour"):
		index, how = pickOption(wish, options)
		if index is None:
			if how:
				listed = "; ".join(choices(options, how)[:MAX_SAID])
				return f"More than one option fits \"{wish.get('name') or wish.get('colour')}\": {listed}. Say which one you mean." + _measuredNote(options)
			return noFit(wish, options, pressing=False)
		option = options[index]
		others = [other for other in chosen if other is not option]
		if option.get("chosen") is True:
			return f"Yes. The page marks {optionSaid(option)} as chosen." + _measuredNote([option])
		if option.get("chosen") is False:
			now = (" Marked as chosen now: " + ", ".join(other.get("label") or "an option with no name" for other in others[:MAX_SAID]) + "."
				if others else "")
			return f"No. The page does not mark {optionSaid(option)} as chosen.{now}" + _measuredNote([option])
		return (
			f"The page does not say whether {optionSaid(option)} is chosen: it gives NVDA no state for it. Ask what the "
			"window's picture shows there, and the model that sees pictures looks at it; a model can be wrong."
			+ _measuredNote([option]))
	if chosen:
		return "The page marks these as chosen: " + "; ".join(choices(options, [options.index(option) for option in chosen])[:MAX_SAID]) + "." + _measuredNote(chosen)
	if options:
		return (
			"The page marks none of these as chosen: " + "; ".join(choices(options, range(len(options)))[:MAX_SAID]) + "."
			+ _measuredNote(options))
	return NO_OPTIONS


def noFit(wish, options, pressing=True):
	"""Said when no option is the one the words name. pressing: whether something was to be pressed."""
	wanted = wish.get("name") or wish.get("colour") or "that"
	lead = "Nothing was pressed: " if pressing else ""
	if not options:
		said = (
			f"{lead}no option called \"{wanted}\" was found on this page or in this window, by its name or by its "
			"colour. It may be further down: scroll to the product's options and ask again.")
	else:
		listed = "; ".join(choices(options, range(len(options)))[:MAX_SAID])
		said = f"{lead}none of the options found is \"{wanted}\". Found: {listed}." + _measuredNote(options)
	return said[0].upper() + said[1:]


def comboText(wish, controls):
	"""Where a product's size or colour is chosen in a combo box, which shows only the chosen one: a sentence that
	says so, with what the box shows now, or "" when no combo box is about what was asked. controls: as for
	asOptions, each with "value" where the page gives what it shows. Choosing in a combo box by the option's name
	is not done; the sentence says how the user does it."""
	group = wish.get("group")
	for control in controls:
		if control.get("role") != "COMBOBOX":
			continue
		label = " ".join(str(control.get("label") or "").split())
		value = " ".join(str(control.get("value") or "").split())
		about = (group and re.search(dict(_GROUPS)[group], label.lower())) or (
			wish.get("name") and value and _nameScore(wish["name"], value))
		if not about:
			continue
		shows = f", which shows {value} now" if value and value != label else ""
		return (
			f"On this page that is chosen in the combo box \"{label}\"{shows}. VisionClaw does not choose in a combo box "
			"by an option's name yet: ask to go to that combo box, press Enter there so that NVDA passes your keys to "
			"it, and choose with the Up Arrow and Down Arrow keys.")
	return ""


def swatchRows(boxes, least=2):
	"""Boxes found in a picture that stand in a row as swatches do: nearly one size, on one line, with nearly even
	gaps. Returns the rows, each a list of indexes into boxes from left to right, the longest row first."""
	rows = []
	order = sorted(range(len(boxes)), key=lambda index: (boxes[index][1], boxes[index][0]))
	used = set()
	for first in order:
		if first in used:
			continue
		left, top, right, bottom = boxes[first]
		wide, tall = right - left, bottom - top
		row = [first]
		for other in order:
			if other in used or other == first:
				continue
			l, t, r, b = boxes[other]
			if abs((t + b) / 2.0 - (top + bottom) / 2.0) > tall * 0.35:
				continue
			if abs((r - l) - wide) > max(3, wide * 0.25) or abs((b - t) - tall) > max(3, tall * 0.25):
				continue
			row.append(other)
		row.sort(key=lambda index: boxes[index][0])
		# Swatches stand close together: a block far from the others on the same line is something else.
		kept = [row[0]]
		for index in row[1:]:
			gap = boxes[index][0] - boxes[kept[-1]][2]
			if gap > 3 * wide:
				if len(kept) >= least:
					break
				kept = [index]
				continue
			kept.append(index)
		if len(kept) >= least:
			rows.append(kept)
			used.update(kept)
	return sorted(rows, key=lambda row: -len(row))


def blocks(image, scale=1.0):
	"""The small blocks of one plain colour in a picture, as swatches with no names are drawn: [(left, top, right,
	bottom)] in picture pixels, from the top down and from left to right. A block differs from the picture's
	background, is of one colour all over, and is about as wide as it is high. Text, photos and large coloured
	areas are none. A swatch that shows a photo of the product, or one of the background's own colour, is not
	found this way. scale: how much larger than plain the screen draws things."""
	from PIL import Image, ImageChops
	from .scrolling import pixels
	cell = 4
	rgb = image.convert("RGB")
	across, down = rgb.size[0] // cell, rgb.size[1] // cell
	if across < 3 or down < 3:
		return []
	rgb = rgb.crop((0, 0, across * cell, down * cell))
	means = rgb.reduce(cell)
	# How much the pixels of each cell differ from the cell's own colour: almost nothing inside a plain block.
	spread = ImageChops.difference(rgb, means.resize(rgb.size, Image.NEAREST)).convert("L").reduce(cell).tobytes()
	cells = list(means.getdata())
	counts = {}
	for colour in cells:
		key = (colour[0] >> 3, colour[1] >> 3, colour[2] >> 3)
		counts[key] = counts.get(key, 0) + 1
	ground = max(counts, key=counts.get)
	back = tuple((part << 3) + 4 for part in ground)
	plain = bytearray(1 if spread[index] <= 4 and colours.distance(cells[index], back) > 45 else 0 for index in range(len(cells)))
	low, high = pixels(10, scale), pixels(72, scale)
	found = []
	for start in range(len(cells)):
		if not plain[start]:
			continue
		seed = cells[start]
		plain[start] = 0
		stack, count = [start], 0
		x0 = x1 = start % across
		y0 = y1 = start // across
		while stack:
			at = stack.pop()
			count += 1
			x, y = at % across, at // across
			x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
			for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
				if 0 <= nx < across and 0 <= ny < down:
					other = ny * across + nx
					if plain[other] and colours.distance(cells[other], seed) < 40:
						plain[other] = 0
						stack.append(other)
		wide, tall = (x1 - x0 + 1) * cell, (y1 - y0 + 1) * cell
		if not (low <= wide <= high and low <= tall <= high) or max(wide, tall) > 2.2 * min(wide, tall):
			continue
		if count < 0.55 * (x1 - x0 + 1) * (y1 - y0 + 1):
			continue
		found.append((x0 * cell, y0 * cell, (x1 + 1) * cell, (y1 + 1) * cell))
	return sorted(found, key=lambda box: (box[1] // 16, box[0]))


NO_WISH = (
	"The request does not say which option is meant. Say its name or its colour and what it is, such as: choose the "
	"Medium size, or: select the dark blue colour option.")
NO_OPTIONS = (
	"No options were found on this page or in this window. They may be further down: scroll to the product's options "
	"and ask again.")
