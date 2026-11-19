# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - which of its models fits what the user wants to do, suggested by plain code; the user decides. The
# owner said on 2026-11-19: "if I should switch to smaller or different qwen variants according to user reviews and my
# available listed visionclaw qwen model choices; for planning, orchestrating, generalization, performing tasks,
# picture describing, coding, depending on what I wish to do, visionclaw should suggest what kind of switch I should
# make, then let the final decision up to me."
#
# What a suggestion stands on, and nothing else:
#   - what the user wants to do, read from their own words (purposesOf);
#   - the models of VisionClaw's catalog, their size and what each job uses, and which are on the disk;
#   - this computer: the memory of its dedicated graphics card and its memory;
#   - what was measured with real models and recorded in docs/STATUS.md (MEASURED), word for word, with its day;
#   - the user's own reviews: how requests went with each model on this computer (planning.Outcomes), and what the
#     user asked VisionClaw to remember about the models.
# A model is never asked: a model does not know itself, and would praise whatever it is. VisionClaw goes online for
# nothing here; reviews from the internet would need the owner's yes for a source, like every other.
# Nothing is changed: the answer ends with where the user chooses, the models window (NVDA+Alt+M). No NVDA dependencies.
#
# The owner said on 2026-11-19: "ensure visionclaw can suggest model type based on hardware and the task the user wishes
# to perform", with everyday models "capped at 9b parameter models, with edge cases using a 14b parameter model", in
# Q4_K_M or Q6_K. So besides the model for each job, a suggestion says: whether the model for hard cases (Qwen3 14B,
# claw/hardcase.py) runs on this computer and how; whether the graphics card has room for the Q6_K of the suggested model;
# and, for asking by voice, which speech model, which comes in Q8_0 only.

import re

from . import voice
from .catalog import CODER, VISION, DEFAULT_QUANT, Q6, isEdge, quantOf, variant

PLAN, SEE, CODE, FAST = "plan", "see", "code", "fast"
ACCESS, HARD, VOICE = "access", "hard", "voice"
PURPOSES = (
	(PLAN, "planning and carrying out what you ask", VISION,
		r"\b(plan\w*|orchestrat\w*|choos\w*|understand\w*|generali[sz]\w*|smart\w*|clever\w*|agent\w*|tasks?|multi-?step|"
		r"carry\w* out|perform\w*|do(ing)? things|follow\w*|reason\w*|think\w*|accura\w*|right job)\b"),
	(SEE, "describing pictures and the screen", VISION,
		r"\b(pictures?|photos?|images?|describ\w*|screens?|see\w*|vision|visual\w*|look\w*|ocr|charts?|games?)\b"),
	(CODE, "writing and fixing add-ons", CODER,
		r"\b(cod(e|es|ing)|coder|add-?ons?|scripts?|programming|python|fix\w* add-?ons?)\b"),
	(FAST, "answering faster", VISION,
		r"\b(fast\w*|quick\w*|speed\w*|slow\w*|lag\w*|wait\w*|respon\w*|smaller|lighter|less memory)\b"),
	(ACCESS, "making stubborn programs, controls and web pages usable", VISION,
		r"\b(in)?accessib\w*|\b(stubborn|unlabel+ed|unnamed|custom controls?|widgets?|controls?|web ?pages?|websites?|"
		r"fix\w* (this |a |the )?(program|app|window|site|page))\b"),
	(HARD, "hard cases", CODER,
		r"\b(hard(est)?|difficult|tough|edge cases?|stubborn|14 ?b)\b"),
	(VOICE, "asking by voice", None,
		r"\b(voice|speak\w*|spoken|dictat\w*|microphone|mic|asr|speech (model|recogni\w*))\b"),
)
_WORDS = {ident: words for ident, words, _role, _pattern in PURPOSES}

# Measured with real models in VisionClaw's own tests and recorded in docs/STATUS.md. Only what was run goes here,
# with its day; a model with nothing here is said to be not measured yet. (catalog id, purpose, sentence)
MEASURED = (
	("qwen3.5-9b", PLAN,
		"On 2026-11-19, as one model for both jobs, it chose the right job for 58 of 65 requests in words it had never "
		"seen, and carried out all 213 requests of VisionClaw's full test"),
	("qwen3.5-9b", SEE, "On 2026-11-18 it said rightly how each of 12 drawn controls is worked"),
	("qwen3.5-4b", PLAN, "On 2026-11-17, with Qwen3.5 9B as the coder, it handled 20 of 21 requests of the full test rightly"),
	("qwen2.5-coder-1.5b", CODE,
		"On 2026-11-18 its add-ons passed VisionClaw's checks 12 of 12 times in Q4_K_M, and 9 of 12 in Q6_K"),
	("qwen3-14b", HARD,
		"On 2026-11-19, in Q4_K_M shared between a graphics card of 8 GB and the processor, nine add-ons it wrote piece by "
		"piece all did what was asked, where those of the 9B did 8, in about the same time; of twelve controls a program "
		"draws itself it told 6 rightly, as the 9B did, with fewer wrong guesses, about 17 seconds each"),
)
# The least memory a dedicated graphics card should have left over beside a model, in GB. Qwen3.5 9B (7.6 GB) ran
# on the owner's card of 8 GB on 2026-11-19.
HEADROOM = 0.2
# How many requests with a model on this computer before how they went is said.
LEAST_SEEN = 5
# Words that ask for a larger model: the everyday models are suggested for them, and the model for hard cases is named.
_LARGER = re.compile(r"\b(bigger|biggest|larger|largest|more (capable|powerful)|most (capable|powerful))\b", re.IGNORECASE)
# Memory left for Windows and NVDA beside the model for hard cases, in GB, when what the card cannot hold goes to the
# computer's memory.
HARD_SPARE = 4.0


def purposesOf(words):
	"""What the user wants to do, from their own words: a list of purposes, or all three main ones. A list of purposes
	chosen in the models window is taken as it is."""
	if isinstance(words, (list, tuple)):
		chosen = [ident for ident, _words, _role, _pattern in PURPOSES if ident in words]
		return chosen or [PLAN, SEE, CODE]
	text = " ".join(str(words or "").lower().split())
	found = [ident for ident, _words, _role, pattern in PURPOSES if re.search(pattern, text)]
	return found or [PLAN, SEE, CODE]


def _models(entries, role):
	"""The models a job can use every day, each once, in the suggested quant, from the smallest to the largest. The
	model for hard cases is not one of them."""
	seen, models = set(), []
	for entry in entries:
		if entry.get("role") != role or quantOf(entry) != DEFAULT_QUANT or entry["id"] in seen or isEdge(entry):
			continue
		seen.add(entry["id"])
		models.append(entry)
	return sorted(models, key=lambda entry: entry.get("memoryGb", 0))


def _name(entry):
	return str(entry.get("name", entry.get("id", ""))).split(", used for")[0]


def fitsCard(entry, dedicatedMb):
	"""Whether a model runs on the dedicated graphics card with room to spare."""
	return dedicatedMb / 1024 >= entry.get("memoryGb", 99) + HEADROOM


def pick(purpose, entries, dedicatedMb, ramGb, chosen=None, oneModel=False):
	"""The model VisionClaw suggests for a purpose, as (entry, why), or (None, why)."""
	if purpose == HARD:
		return hardPick(entries, dedicatedMb, ramGb)
	if purpose == VOICE:
		return voice.model(voice.SUGGESTED), "the smaller speech model, measured in VisionClaw's own tests; it runs on the processor"
	role = {PLAN: VISION, SEE: VISION, CODE: CODER, FAST: VISION, ACCESS: VISION}[purpose]
	models = _models(entries, role)
	suggested = [entry for entry in models if entry.get("suggest", True) is not False]
	onCard = [entry for entry in suggested if fitsCard(entry, dedicatedMb)]
	if purpose == FAST:
		fast = [entry for entry in suggested if not entry.get("small")] if dedicatedMb else suggested
		choice = (fast or suggested or models)[0] if (fast or suggested or models) else None
		return choice, "the smallest that is still suggested: faster, and a little less exact"
	if purpose == CODE:
		current = next((entry for entry in models if entry["id"] == (chosen or {}).get(CODER)), None)
		if oneModel and current is not None and fitsCard(current, dedicatedMb):
			return current, "one model for both jobs is loaded only once, and it fits your graphics card"
		coders = [entry for entry in suggested if entry["id"].startswith("qwen2.5-coder")]
		roomy = [entry for entry in coders if fitsCard(entry, dedicatedMb)]
		if roomy:
			return roomy[-1], "the largest model made for code that fits your graphics card"
		return (coders[0] if coders else None), "a small model made for code, measured in VisionClaw's own tests"
	if onCard and purpose == ACCESS:
		return onCard[-1], (
			"the largest that fits your graphics card: it reads the pictures of controls that report nothing, and says how "
			"each is worked")
	if onCard:
		return onCard[-1], "the largest that fits your graphics card, which runs it fastest"
	inMemory = [entry for entry in suggested if entry.get("memoryGb", 99) <= max(1.0, ramGb * 0.45)]
	if inMemory:
		return inMemory[-1], "the largest that fits your computer's memory; without a graphics card big enough, it runs slower"
	return (suggested[0] if suggested else None), "the smallest that is suggested"


def hardPick(entries, dedicatedMb, ramGb):
	"""The model for hard cases in the suggested quant, and how it would run here, as (entry, why); (None, why) when this
	computer cannot hold it."""
	models = [entry for entry in entries if isEdge(entry) and quantOf(entry) == DEFAULT_QUANT]
	if not models:
		return None, "there is no model for hard cases in the list"
	entry = models[0]
	need, card = entry.get("memoryGb", 99), (dedicatedMb or 0) / 1024
	if card and fitsCard(entry, dedicatedMb):
		return entry, "it fits your graphics card whole"
	if card + max(0.0, ramGb - HARD_SPARE) < need:
		return None, (
			f"it needs about {need:.0f} GB, more than your graphics card and memory can spare; the everyday models do "
			"every case")
	if card:
		return entry, (
			"it is larger than your graphics card, so it is shared between the card and the processor: slower, and used "
			"only for hard cases")
	return entry, "with no graphics card it runs on the processor alone: slow, and used only for hard cases"


def quantText(entry, dedicatedMb, entries):
	"""Whether the graphics card has room for the Q6_K of the suggested model, in a sentence, or ""."""
	if entry is None or not dedicatedMb:
		return ""
	six = variant(entries, entry, Q6)
	if six is None:
		return ""
	if fitsCard(six, dedicatedMb):
		return (f"Your graphics card also has room for the Q6_K of {_name(entry)}, larger and closer to the model as it "
			"was trained; it was not measured better, so Q4_K_M is suggested.")
	return (f"The Q6_K of {_name(entry)} does not fit your graphics card whole: it would be shared with the processor "
		"and answer more slowly.")


def _measured(entry, purpose):
	purpose = SEE if purpose == ACCESS else purpose
	said = [sentence for ident, about, sentence in MEASURED if ident == entry["id"].replace("-coder", "") and about == purpose]
	return f"Measured: {said[0]}." if said else "It has not been measured in VisionClaw's tests yet."


def _seen(entry, outcomes):
	good, bad = (outcomes or {}).get(entry["id"].replace("-coder", ""), (0, 0))
	if good + bad < LEAST_SEEN:
		return ""
	return f"On this computer, requests with it went well {good} of {good + bad} times."


def _hardSentence(entry, why, stored):
	if entry is None:
		return f"For hard cases: no larger model is suggested, as {why}."
	where = (" It is on your disk already." if entry["id"] in (stored or ()) else
		f" It is not on your disk yet: about {entry.get('memoryGb', 0):.0f} GB while it runs.")
	return (
		f"For hard cases, such as an add-on the everyday models could not write or a control they could not tell: "
		f"{_name(entry)}, as {why}. It is used only after you say yes, and reads and writes text only; choose it in the "
		f"list Model for hard cases.{where} {_measured(entry, HARD)}")


def _voiceSentence(entry, ramGb, speech):
	where = " It is on your disk already." if entry["id"] in (speech or ()) else ""
	larger = voice.model("qwen3-asr-1.7b")
	more = (f" {larger['name']} is larger, about {larger['memoryGb']:.0f} GB while it runs, and was not measured."
		if larger is not None and ramGb >= 12 else "")
	return (
		f"For asking by voice: {entry['name']}, the smaller speech model, measured in VisionClaw's own tests: 24 of 24 "
		f"requests heard word for word. It runs on the processor, about {entry['memoryGb']:.0f} GB, only while you speak."
		f"{where}{more} The speech models come only as Q8_0: there is no Q4_K_M or Q6_K of them.")


def choices(words, entries, dedicatedMb, ramGb, chosen=None, oneModel=False):
	"""The models the suggestion would choose for what the user wants to do, for the models window to show:
	{VISION: entry or None, CODER: entry or None, HARD: entry or None}. Nothing is chosen for the user by it."""
	purposes = purposesOf(words)
	found = {VISION: None, CODER: None, HARD: None}
	for purpose in purposes:
		entry, _why = pick(purpose, entries, dedicatedMb, ramGb, chosen, oneModel)
		if purpose == HARD:
			found[HARD] = entry
		elif purpose == CODE:
			found[CODER] = found[CODER] or entry
		elif purpose != VOICE:
			found[VISION] = found[VISION] or entry
	if ACCESS in purposes and found[HARD] is None:
		found[HARD] = hardPick(entries, dedicatedMb, ramGb)[0]
	return found


def advise(words, entries, chosen, stored, dedicatedMb, ramGb, outcomes=None, remembered=(), oneModel=False, speech=()):
	"""What VisionClaw suggests for what the user wants to do, in sentences. chosen: {VISION: id, CODER: id};
	stored: the catalog ids on the disk; outcomes: {model id: (good, bad)} on this computer; remembered: what the
	user asked VisionClaw to remember about models; speech: the speech models on the disk. Nothing is changed by it."""
	chosen = chosen or {}
	byId = {entry["id"]: entry for entry in entries}
	parts = []
	parts.append(
		f"This computer has {dedicatedMb / 1024:.0f} GB of graphics memory and {ramGb:.0f} GB of memory." if dedicatedMb
		else f"This computer has no dedicated graphics card, and {ramGb:.0f} GB of memory.")
	purposes = purposesOf(words)[:3]
	# The user's own review: a model they said is too slow brings the faster choice in.
	if FAST not in purposes and any(re.search(r"\b(too )?slow\b", str(text), re.IGNORECASE) for text in remembered or ()):
		purposes.append(FAST)
	quantFor = None
	for purpose in purposes:
		if purpose == HARD:
			parts.append(_hardSentence(*hardPick(entries, dedicatedMb, ramGb), stored))
			continue
		if purpose == VOICE:
			parts.append(_voiceSentence(voice.model(voice.SUGGESTED), ramGb, speech))
			continue
		role = VISION if purpose in (PLAN, SEE, FAST, ACCESS) else CODER
		current = byId.get(chosen.get(role, ""))
		entry, why = pick(purpose, entries, dedicatedMb, ramGb, chosen, oneModel)
		if entry is None:
			continue
		quantFor = quantFor or entry
		sameModel = current is not None and _name(current) == _name(entry)
		head = (f"For {_WORDS[purpose]}: keep {_name(entry)}, which you use now"
			if sameModel else f"For {_WORDS[purpose]}: VisionClaw suggests {_name(entry)}"
			+ (f" in place of {_name(current)}" if current is not None else ""))
		where = "" if sameModel else (" It is on your disk already." if entry["id"] in (stored or ()) else
			f" It is not on your disk yet: about {entry.get('memoryGb', 0):.1f} GB while it runs.")
		parts.append(f"{head}, as {why}.{where} {_measured(entry, purpose)} {_seen(entry, outcomes)}".strip())
	if (ACCESS in purposes or _LARGER.search(str(words or ""))) and HARD not in purposes:
		parts.append(_hardSentence(*hardPick(entries, dedicatedMb, ramGb), stored))
	if remembered:
		parts.append("You asked VisionClaw to remember: " + "; ".join(remembered[:3]) + ".")
	if purposes != [VOICE]:
		parts.append(quantText(quantFor, dedicatedMb, entries))
		parts.append(
			"Each model comes as Q4_K_M, smaller and faster, or Q6_K, larger; Q4_K_M is suggested, as Q6_K was not "
			"measured better.")
	# The last sentence, where the user chooses, is never the part that is cut.
	tail = "VisionClaw only suggests and has changed nothing: to choose, press NVDA+Alt+M, the models window."
	text = " ".join(" ".join(part.split()) for part in parts if part)
	room = 1400 - len(tail) - 1
	if len(text) > room:
		text = text[:room].rsplit(". ", 1)[0] + "."
	return f"{text} {tail}"


def remembers(texts):
	"""Of what the user asked VisionClaw to remember, what is about its models: their names, size or speed."""
	return [text for text in texts or () if re.search(r"\b(models?|qwen|\d+(\.\d+)?b\b|too slow|too fast|quant)", str(text), re.IGNORECASE)]
