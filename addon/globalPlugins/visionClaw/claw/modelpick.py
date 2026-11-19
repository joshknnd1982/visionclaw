# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - which model does each job, when the user lets VisionClaw pick. The owner said on 2026-11-19: "clever
# model suggestions for the user to choose depending on job, or let visionclaw pick with silent autosuggestions."
# The user chooses in the settings (the setting "Which model does each job"):
#   - MINE, the default: the models the user chose in the models window do every job, as always. VisionClaw only
#     suggests when asked (claw/advice.py, the job model_advice) and marks its suggestion in the models window. Asked
#     which models it uses, it also says which models on this computer it would pick, where they differ from the
#     user's (suggestionText): a suggestion that is never spoken by itself.
#   - AUTO: before every request VisionClaw picks, among the models that are on this computer, the one for each job,
#     without a question and without a word: the pick is written to VisionClaw's log, said with the progress
#     (NVDA+Alt+P), and said when the user asks which model VisionClaw uses (pickedText).
# How it picks, by plain code, never by a model (a model does not know itself):
#   - Accuracy first, as the owner asked of everything: the largest model that runs on the dedicated graphics card
#     with room to spare; with none that fits there, the largest that fits the computer's memory.
#   - A faster model only where the user said they want speed (a memory such as "the 9B is too slow for me"), and
#     only for a request that plain code does not find hard (planner.complexity: at most two things, each of a kind
#     VisionClaw knows), with no picture and no code in it.
#   - Writing code: the largest model for code that fits on the graphics card beside the model that plans, or the
#     model that plans itself when it can write code too, which loads nothing more.
#   - Everything else of the second job (checking a plan, hints, reviews): the model that plans, when it can do both,
#     so that nothing more is loaded; else the model for code that is already loaded; else the smallest suggested.
#   - The user's own review counts: a model with which requests went badly on this computer (planning.Outcomes) is
#     passed over while another can do the job.
#   - Nothing is downloaded, and a model the user has not downloaded is never picked. A model that is only for hard
#     cases (catalog entries marked "edge") is never picked here: it is used only after a question, for a hard case.
#   - Of one model in two quants, the quant the user chose wins; else Q4_K_M, which is suggested.
# Nothing is hidden or taken away: every model stays in the models window, and the user can go back to their own
# choice at any time. No NVDA dependencies.

import re

from .catalog import CODER, DEFAULT_QUANT, VISION, quantOf

MINE, AUTO = "mine", "auto"
CHOICES = (MINE, AUTO)
# Room left over on a dedicated graphics card beside a model, in GB (as advice.HEADROOM).
HEADROOM = 0.2
# Without a graphics card that holds it, a model must fit in this share of the computer's memory.
MEMORY_SHARE = 0.45
# How many requests with a model on this computer before how they went counts, and below which share of requests
# that went well (Laplace's rule) a model is passed over.
LEAST_SEEN = 5
POOR = 0.5
# Words in what the user asked VisionClaw to remember that say they want speed, and that a model is too slow.
_SPEED = re.compile(
	r"\b(too slow|slow for me|faster answers?|answer(s)? faster|quick(er)? answers?|speed matters|prefer speed|"
	r"rather (have it )?fast)\b", re.IGNORECASE)
# Words of a request that ask about a picture or the screen, and that ask for code.
_PICTURE = re.compile(
	r"\b(describe|picture|photo|image|screenshot|screen|chart|graph|diagram|what do you see|look at|looks? like|"
	r"colou?r|read the text in)\b", re.IGNORECASE)
_CODE = re.compile(r"\b(add-?on|addon|script|code|program it|plugin)\b", re.IGNORECASE)

PLAN, SEE, CODE, CHECK = "plan", "see", "code", "check"
_JOB_WORDS = {
	PLAN: "planning what to do", SEE: "planning and looking at pictures", CODE: "writing code",
	CHECK: "checking the plan"}


class Pick:
	"""What was picked for a request: ids of the catalog for each role, and why, in plain words."""

	def __init__(self, vision=None, coder=None, why=None, jobs=()):
		self.vision = vision
		self.coder = coder
		self.why = dict(why or {})
		self.jobs = tuple(jobs)

	def ids(self):
		return {VISION: (self.vision or {}).get("id", ""), CODER: (self.coder or {}).get("id", "")}

	def __bool__(self):
		return self.vision is not None

	def __repr__(self):
		return f"Pick({self.ids()}, {self.jobs})"


def _modelFile(entry):
	return next((f["name"] for f in entry.get("files", ()) if f.get("kind") == "model"), entry.get("id", ""))


def sameFile(one, two):
	"""Whether two entries of the catalog are one model file: then one engine does both jobs."""
	return bool(one and two) and one.get("dir") == two.get("dir") and _modelFile(one) == _modelFile(two)


def name(entry):
	return str((entry or {}).get("name", (entry or {}).get("id", ""))).split(", used for")[0]


def jobsOf(request, triage=None):
	"""The jobs a request needs, from its words and plain code's first sorting of it (planner.quickTriage)."""
	triage = triage or {}
	jobs = [PLAN]
	text = str(request or "")
	if triage.get("needs_vision") or _PICTURE.search(text):
		jobs.append(SEE)
	jobs.append(CODE if triage.get("needs_code") or _CODE.search(text) else CHECK)
	return jobs


def wantsSpeed(remembered):
	"""Whether what the user asked VisionClaw to remember says they want answers faster."""
	return any(_SPEED.search(str(text)) for text in remembered or ())


def _fitsCard(entry, dedicatedMb, used=0.0):
	return dedicatedMb > 0 and dedicatedMb / 1024 - used >= entry.get("memoryGb", 99) + HEADROOM


def _fitsMemory(entry, ramGb):
	return entry.get("memoryGb", 99) <= max(1.0, (ramGb or 0) * MEMORY_SHARE)


def _record(entry, outcomes):
	good, bad = (outcomes or {}).get(entry["id"].replace("-coder", ""), (0, 0))
	return good, bad


def _poor(entry, outcomes):
	good, bad = _record(entry, outcomes)
	return good + bad >= LEAST_SEEN and (good + 1) / (good + bad + 2) < POOR


def _usable(entries, installed, role):
	"""The models of a role that are on this computer and may be picked, one entry for each model file."""
	return [entry for entry in entries
		if entry.get("role") == role and entry.get("id") in installed and not entry.get("edge")
		and "memoryGb" in entry]


def _oneQuant(models, chosen, loaded):
	"""Of a model in two quants, one: the one already loaded, else the one the user chose, else the suggested quant."""
	byModel = {}
	for entry in models:
		key = (entry.get("dir"), entry.get("role"))
		byModel.setdefault(key, []).append(entry)
	kept = []
	for group in byModel.values():
		group.sort(key=lambda entry: (
			entry["id"] not in loaded, entry["id"] not in chosen, quantOf(entry) != DEFAULT_QUANT))
		kept.append(group[0])
	return kept


def _largest(models):
	return max(models, key=lambda entry: (entry.get("memoryGb", 0), entry.get("suggest", True) is not False)) if models else None


def _smallestSuggested(models):
	suggested = [entry for entry in models if entry.get("suggest", True) is not False] or models
	return min(suggested, key=lambda entry: entry.get("memoryGb", 0)) if suggested else None


def _planner(models, dedicatedMb, ramGb, outcomes, fast):
	"""The model that plans (and looks at pictures), with why."""
	good = [entry for entry in models if not _poor(entry, outcomes)] or models
	onCard = [entry for entry in good if _fitsCard(entry, dedicatedMb)]
	if fast:
		quick = _smallestSuggested(onCard or good)
		if quick is not None:
			return quick, "you asked for faster answers, and this request is not a hard one: the fastest suggested model here"
	if onCard:
		return _largest(onCard), "the largest model here that fits your graphics card, which runs it fastest"
	inMemory = [entry for entry in good if _fitsMemory(entry, ramGb)]
	if inMemory:
		return _largest(inMemory), (
			"the largest model here that fits your computer's memory; without room on a graphics card it runs slower")
	return _smallestSuggested(good), "the smallest model here, as none fits the graphics card or the memory well"


def _coder(models, planner, wantsCode, dedicatedMb, ramGb, outcomes, loaded):
	"""The model for the second job, with why. planner: the model picked to plan."""
	twin = next((entry for entry in models if sameFile(entry, planner)), None)
	good = [entry for entry in models if not _poor(entry, outcomes)] or models
	if wantsCode:
		used = planner.get("memoryGb", 0) if _fitsCard(planner, dedicatedMb) else 0.0
		beside = [entry for entry in good if entry is not twin and _fitsCard(entry, dedicatedMb, used)]
		candidates = beside + ([twin] if twin is not None else [])
		best = _largest(candidates)
		if best is not None:
			return best, ("the model that plans, which writes code too, so nothing more is loaded" if best is twin
				else "the largest model for code that fits on your graphics card beside the model that plans")
		inMemory = [entry for entry in good if _fitsMemory(entry, ramGb)]
		if inMemory:
			return _largest(inMemory), "the largest model for code that fits your computer's memory; it runs slower"
		return _smallestSuggested(good), "the smallest model for code here"
	if twin is not None:
		return twin, "the model that plans checks its own plan, so nothing more is loaded"
	running = [entry for entry in good if entry["id"] in loaded]
	if running:
		return running[0], "the model for code that is loaded already"
	return _smallestSuggested(good), "the smallest suggested model for code here, which loads fastest"


def pick(request, entries, installed, dedicatedMb, ramGb, triage=None, loaded=(), chosen=(), outcomes=None,
		remembered=()):
	"""The models for a request (a Pick), or an empty Pick when no model for planning is on this computer.
	entries: the catalog; installed: the ids on the disk; dedicatedMb: the dedicated graphics card's memory, 0 for
	none; ramGb: the computer's memory; triage: planner.quickTriage of the request; loaded: the ids loaded now;
	chosen: the ids the user chose; outcomes: {model id: (good, bad)} on this computer; remembered: what the user
	asked VisionClaw to remember."""
	installed, loaded, chosen = set(installed or ()), set(loaded or ()), set(chosen or ())
	triage = triage or {}
	jobs = jobsOf(request, triage)
	planners = _oneQuant(_usable(entries, installed, VISION), chosen, loaded)
	coders = _oneQuant(_usable(entries, installed, CODER), chosen, loaded)
	if not planners:
		return Pick(jobs=jobs)
	fast = (wantsSpeed(remembered) and SEE not in jobs and CODE not in jobs
		and triage.get("complexity", "simple") != "complex")
	planner, planWhy = _planner(planners, dedicatedMb, ramGb, outcomes, fast)
	why = {VISION: planWhy}
	coder = None
	if coders:
		coder, codeWhy = _coder(coders, planner, CODE in jobs, dedicatedMb, ramGb, outcomes, loaded)
		why[CODER] = codeWhy
	return Pick(planner, coder, why, jobs)


def pickedText(picked):
	"""What was picked, in sentences for the user; "" when nothing was."""
	if not picked:
		return ""
	planner, coder = picked.vision, picked.coder
	job = _JOB_WORDS[SEE if SEE in picked.jobs else PLAN]
	lines = [f"For {job}, VisionClaw picked {name(planner)}: {picked.why.get(VISION, '')}."]
	if coder is not None:
		second = _JOB_WORDS[CODE if CODE in picked.jobs else CHECK]
		if sameFile(coder, planner):
			lines.append(f"For {second}, the same model: {picked.why.get(CODER, '')}.")
		else:
			lines.append(f"For {second}, {name(coder)}: {picked.why.get(CODER, '')}.")
	return " ".join(lines)


def suggestionText(everyday, forCode, chosen):
	"""For a user who chose the models themselves: which models on this computer VisionClaw would pick, in sentences,
	where they differ from the chosen ones; "" when they are the same or nothing was picked. Said only when the user
	asks which models VisionClaw uses, never by itself. everyday: the pick for a request without code; forCode: the
	pick for writing an add-on; chosen: {VISION: id, CODER: id}."""
	chosen = chosen or {}
	lines = []
	planner = everyday.vision if everyday else None
	if planner is not None and planner["id"] != chosen.get(VISION):
		lines.append(f"For planning and pictures it would pick {name(planner)}: {everyday.why.get(VISION, '')}.")
	coder = forCode.coder if forCode else None
	if coder is not None and coder["id"] != chosen.get(CODER):
		if sameFile(coder, forCode.vision):
			lines.append(f"For writing code it would use {name(coder)} too: {forCode.why.get(CODER, '')}.")
		else:
			lines.append(f"For writing code it would pick {name(coder)}: {forCode.why.get(CODER, '')}.")
	if not lines:
		return ""
	return ("Of the models on this computer, VisionClaw would choose differently. " + " ".join(lines)
		+ " To let it pick for each request, choose \"VisionClaw picks\" under \"Which model does each job\" in "
		"VisionClaw's settings; nothing changes until you do.")


def settingText(choice):
	"""How the models are picked now, in one sentence, for the answer about VisionClaw's models."""
	if choice == AUTO:
		return ("VisionClaw picks the model for each job itself, from the models on this computer, without asking; "
			"to use the models you chose instead, change \"Which model does each job\" in VisionClaw's settings.")
	return ""


__all__ = ["MINE", "AUTO", "CHOICES", "Pick", "pick", "pickedText", "suggestionText", "settingText", "jobsOf", "wantsSpeed",
	"sameFile"]
