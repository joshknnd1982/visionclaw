# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The checks on the words of the final answer (tests/answercheck.py), the two evaluation sets that use them, and the
scorer (tests/eval_answers.py), without a model.

- Every rule for every answer finds what it is for, and lets a plain answer through.
- A key is one key however it is written; a key that exists nowhere is found, one that NVDA, Windows or VisionClaw
  has is not, nor one a tool found.
- VisionClaw's own sentences, written by plain code, break none of the rules.
- The sets have the form the scorer reads, name only jobs that exist, and share no request with what VisionClaw was
  tuned on.
- Whole requests that plain code decides go from their words to a judged answer with no model at all.
"""
import json
import os
import re

import harness  # noqa: F401
import answercheck as check
import eval_answers
import live_orchestrator as live
from visionClaw.claw import computer, llm, lookup, planner, places, router, understand

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.join(HERE, "eval")


def rules(answer, sources=(), oneModel=False):
	return [rule for rule, _what in check.problems(answer, sources, oneModel)]


# --- The rules for every answer ---

PLAIN = "Speech rate was 50 and is now 60. Next time you can press NVDA+control+upArrow for this."
assert rules(PLAIN) == [], check.problems(PLAIN)
assert rules("") == [check.EMPTY] and rules("   ") == [check.EMPTY]
assert check.CUT in rules("The add-ons installed are Clock and Pr ...[cut].")
assert check.CUT in rules("The page says: [12 lines left out]")
assert check.MARKDOWN in rules("**Speech rate** is 50.")
assert check.MARKDOWN in rules("The keys:\n- NVDA+t reads the title")
assert check.MARKDOWN in rules("## Keys\nNVDA+t reads the title.")
assert check.MARKDOWN in rules("Press `NVDA+t`.")
# A number in a list, as plain code numbers what it lists, is no Markdown.
assert rules("2 items in Downloads:\n1. setup.exe\n2. report.pdf") == []
for sighted in ("As you can see, there are four buttons.", "Hover over the icon to see its name.",
		"Click the blue button at the bottom.", "Look at the top of the window.", "The red button stops it."):
	assert check.SIGHTED in rules(sighted), sighted
# Places in words, and the mouse worked from the keyboard, are not sighted-only.
for fine in ("The Quit button is the last of four, at the bottom of the window.",
		"Press NVDA+numpadDivide to move the mouse to the navigator object, then NVDA+numpadEnter to click."):
	assert rules(fine) == [], (fine, check.problems(fine))
# What the user said or a tool found is not held against the answer.
assert rules("Understood as: look at the screen. The screen shows a menu.", ["look at the screen"]) == []
assert check.TWO_MODELS in rules("Both models agree on the plan.", oneModel=True)
assert check.TWO_MODELS in rules("The vision model says it is a menu.", oneModel=True)
assert rules("The vision model says it is a menu.", oneModel=False) == []
for leak in ("Based on the information found, the key is NVDA+t.", "Line 2 says the key is NVDA+t.",
		"The user asked about the title. The key is NVDA+t.", "According to the passages, press NVDA+t."):
	assert check.SCAFFOLD in rules(leak), leak
assert rules("Scrolled down. The user said: scroll down", ["Scrolled down. The user said: scroll down"]) == []
for opening in ("Sure! The time is 4:05 PM.", "Certainly. Press NVDA+t.", "Here is what I found: NVDA+t.",
		"Understood as: what time is it. Of course, it is 4:05 PM."):
	assert check.PREAMBLE in rules(opening), opening
assert rules("Understood as: what time is it. NVDA said: 4:05 PM.") == []
# A tool's own sentence that begins so is the tool's.
assert rules("Here are 2 items: setup.exe; report.pdf.", ["Here are 2 items: setup.exe; report.pdf."]) == []

# --- Keys ---

assert check.keyOf("Ctrl+S") == check.keyOf("control+s") == check.keyOf("S+Control")
assert check.keyOf("NVDA+Up Arrow") == check.keyOf("NVDA+upArrow") == check.keyOf("nvda+up")
assert check.keyOf("Windows+B") == check.keyOf("win+b")
assert check.keysIn("Press NVDA+t, then Control+Alt+N, or Alt + F4.") == {
	check.keyOf("NVDA+t"), check.keyOf("control+alt+n"), check.keyOf("alt+f4")}
assert not check.keysIn("Windows 11, C++ and 2+2 are no keys.")
known = check.knownKeys()
for real in ("NVDA+f12", "NVDA+t", "NVDA+control+escape", "Windows+B", "Alt+Tab", "NVDA+alt+c", "NVDA+shift+alt+b",
		"NVDA+upArrow", "Shift+F10"):
	assert check.keyOf(real) in known, real
made = "Press NVDA+Shift+Alt+F11 to read the title."
assert check.keyOf("NVDA+Shift+Alt+F11") not in known
assert rules(made) == [check.MADE_UP_KEY], check.problems(made)
# A key spelled out is the same key: found, and said to be spelled out; a made-up one cannot hide behind the word.
assert check.keyOf("NVDA plus control plus escape") == check.keyOf("NVDA+control+escape")
assert check.keyOf("NVDA plus up arrow") == check.keyOf("NVDA+upArrow")
assert rules("The key is NVDA plus t.") == [check.SPELLED]
assert set(rules("Press NVDA plus Shift plus Alt plus F11.")) == {check.SPELLED, check.MADE_UP_KEY}
assert check.has("The key is NVDA plus t.", "NVDA+t")
# Words that only happen to follow a modifier are no key.
assert not check.keysIn("Two plus two is four, and Alt is a key.")
# A key a tool found is no made-up key, even where NVDA has no such key: it is the program's own.
assert rules("Press Alt+Q to quit.", ["Quit (button): Alt+Q."]) == []
assert rules("Press Alt+Shift+Q to quit.", ["Quit (button): Alt+Q."]) == [check.MADE_UP_KEY]

# --- What one answer must say ---

item = {"says": [["4:05"], ["NVDA+F12"]], "never": ["5:00"]}
assert check.expected("NVDA said: 4:05 PM. Next time you can press nvda+f12 for this.", item) == []
assert check.expected("It is 4:05.", item) == [(check.MISSING, "NVDA+F12")]
assert check.expected("It is 4:05 or 5:00. Press NVDA+F12.", item) == [(check.NEVER, "5:00")]
assert check.has("Saving is done with Ctrl+S.", "Control+S") and not check.has("Press Control+O.", "Control+S")
assert check.has("Press T to open the market.", "re:\\bpress t\\b") and not check.has("Press Tab.", "re:\\bpress t\\b")
assert check.has("It’s  Space   Trader", "it's space trader")

# --- What plain code corrects in the words a model wrote (llm.nvdaKeys, llm.unframed) ---

assert llm.nvdaKeys("The key is NVDA plus t.") == "The key is NVDA+t."
assert llm.nvdaKeys("Press NVDA plus control plus escape to turn it on.") == "Press NVDA+control+escape to turn it on."
assert llm.nvdaKeys("NVDA plus up arrow, then Alt plus F11.") == "NVDA+upArrow, then Alt+F11."
assert llm.nvdaKeys("Control plus A to select all.") == "Control+A to select all."
# What is no key is left as it is: a word after "plus", an article, a key already written as NVDA writes it.
for kept in ("Hold Shift plus a click.", "Two plus two is four.", "Press NVDA+t.", "Alt plus the arrow keys.", ""):
	assert llm.nvdaKeys(kept) == kept, kept
assert llm.unframed("Based on the information found, the key is NVDA+t.") == "The key is NVDA+t."
assert llm.unframed("I could not find the refund policy in the information provided.") == (
	"I could not find the refund policy in what was looked up.")
assert llm.unframed("The information given does not say. eSpeak NG speaks.") == "What was looked up does not say. eSpeak NG speaks."
for kept in ("The page has information about refunds.", "eSpeak NG is the synthesizer.", "The passages given do not say."):
	assert llm.unframed(kept) == kept, kept
for corrected in (llm.nvdaKeys("The key is NVDA plus t."), llm.unframed("Based on the information found, press NVDA+t.")):
	assert check.problems(corrected) == [], corrected


class Scripted(object):
	"""A model that chooses the job and words the answer as Qwen3.5 4B did on 2026-11-19."""

	def __init__(self, answer):
		self.answer = answer

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False}

	def oneModel(self):
		return True

	def chat(self, role, messages, maxTokens, **options):
		system = messages[0]["content"]
		if system.startswith("You choose how VisionClaw"):
			return json.dumps({"choice": "explain_keys"})
		if "Answer the user from the information given" in system:
			# The answer copies what was looked up: the engine's setting against repeating is off for it.
			assert (options.get("options") or {}).get("dry_multiplier") == 0, options
			return self.answer
		return None


curtain = {"request": "how do i turn the screen curtain on", "says": [["NVDA+control+escape"]]}
task, asked, _state = eval_answers.runItem(
	Scripted("Based on the information found, press NVDA plus control plus escape to turn the screen curtain on."), curtain)
assert task.answer == "Press NVDA+control+escape to turn the screen curtain on.", task.answer
assert eval_answers.score(task, curtain, asked, True)["verdict"] == eval_answers.RIGHT

# --- A key nothing looked up names (llm.keysNotFound), and the answer then given in the words that were found ---

found = ["From NVDA: dateTime: reports the time. Keys: NVDA+f12.", "Window: Load Game (button): Alt+L."]
assert llm.keysNotFound("Press NVDA+F12, or Alt+L to load.", found) == []
assert llm.keysNotFound("Press NVDA+Up Arrow.", ["Keys: NVDA+upArrow."]) == []
assert llm.keysNotFound("Press Control+S to save.", found) == ["Control+S"]
assert llm.keysNotFound("Press the Jump key to move on.", found) == ["the Jump key"]
# Keys every keyboard or NVDA has, and a key the found words name, are no made-up keys.
for fine in ("Press the Enter key.", "Hold the NVDA key.", "Press the H key.", "Press the F6 key.", "Press the Tab key."):
	assert llm.keysNotFound(fine, found) == [], fine
assert llm.keysNotFound("Press the Fire key.", ["In this game the Fire key shoots."]) == []
assert check.MADE_UP_KEY in rules("Press the Jump key to move to the next item.")
assert rules("Press the Enter key.") == [] and rules("Press the Fire key.", ["the Fire key shoots"]) == []


class MakesUpAKey(Scripted):
	def chat(self, role, messages, maxTokens, **options):
		system = messages[0]["content"]
		if "Which line answers what the user asked" in messages[1]["content"]:
			return json.dumps({"line": 2})
		return super().chat(role, messages, maxTokens, **options)


task, asked, _state = eval_answers.runItem(
	MakesUpAKey("Press the Jump key, or NVDA+Shift+J, to turn the screen curtain on."), curtain)
assert "Jump key" not in task.answer and "NVDA+Shift+J" not in task.answer, task.answer
assert "NVDA+control+escape" in task.answer, task.answer
assert any("named a key that nothing looked up has" in text for _seconds, _kind, text in task.log), task.log

# --- Jobs the answer sets showed were chosen wrongly, in words of the tests' own ---

registry = live.makeRegistry(None, {})
onPage = {router.WEB: True}
for request, facts, job in (
		("how many cells does the braille display have", None, None),
		("whats the return policy here", onPage, "web_page"),
		("what are this store's delivery times", onPage, "web_page"),
		("do they ship abroad", onPage, "web_page"),
		("what would happen if I pressed NVDA+t", None, None),
		("what happens if you press alt f4", None, "nvda_question"),
		# What they must leave alone: the time on a web page, a control of the page, NVDA, the same question elsewhere.
		("what's the time here", onPage, None),
		("is there a search field here", onPage, None),
		("which voice is talking here", onPage, None),
		("whats the return policy here", None, None),
		("press alt f4", None, None)):
	assert planner.decided(request, registry, None, facts) == job, (request, planner.decided(request, registry, None, facts))
assert planner.hint("how many cells does the braille display have") == "nvda_info"
assert planner.hint("what would happen if I pressed NVDA+t") != "press_keys"
assert planner.hint("what time have you got") == "do_command" and planner.hint("what time do they open") != "do_command"
assert planner.hint("any new downloaded files") == "files" and planner.hint("what can you download for me") == "downloads_info"

# --- VisionClaw's own sentences break no rule ---

registry = live.makeRegistry(None, {})


class Asked:
	def __init__(self, request):
		self.request, self.cancel, self.listed = request, None, None


own = [
	lookup.nothingText("how do I bake bread", "spacetrader", "Space Trader - Main Menu", library=True, memories=True),
	f"{lookup.NO_ANSWER} From NVDA: title: Reports the title of the window. Keys: NVDA+t.",
	computer.binText(12, 5 << 20, 200 << 30, 500 << 30),
	understand.taken("what time is it"),
]
for asked in ("what is in the system tray", "is dropbox in the tray", "how many icons are on the taskbar",
		"read my notifications"):
	worked, said = registry.call(Asked(asked), "read_place", {"asked": asked})
	assert worked and places.wish(asked), asked
	own.append(said)
for said in own:
	assert check.problems(said, oneModel=True) == [], (said, check.problems(said, oneModel=True))

# --- The sets ---


def plainWords(text):
	return " ".join(re.sub(r"[^\w\s']", " ", text.lower()).split())


tuned = set()
with open(os.path.join(EVAL, "known.json"), encoding="utf-8") as f:
	for requests in json.load(f)["jobs"].values():
		tuned |= {plainWords(request) for request in requests}
for session in live.REQUESTS:
	tuned |= {plainWords(request) for request in session.split(" >> ")}
routing = set()
for name in os.listdir(EVAL):
	if name.startswith("requests") and name.endswith(".json"):
		with open(os.path.join(EVAL, name), encoding="utf-8") as f:
			routing |= {plainWords(item["request"]) for item in json.load(f)["requests"]}

sets = {}
# The development set, and the held-out sets, each written before anything was run on it.
for name in ("answers", "answers-held", "answers-held2", "answers-held3"):
	with open(os.path.join(EVAL, name + ".json"), encoding="utf-8") as f:
		data = json.load(f)
	assert "before anything was run" in data["about"], name
	sets[name] = data["requests"]
	assert len(data["requests"]) >= 14, name
	for entry in data["requests"]:
		assert set(entry) <= {"request", "expect", "says", "never", "facts"}, entry
		assert entry.get("says") or entry.get("never"), entry
		for group in entry.get("says", ()):
			assert isinstance(group, list) and group and all(isinstance(p, str) and p.strip() for p in group), entry
		for phrase in [p for group in entry.get("says", ()) for p in group] + list(entry.get("never", ())):
			if phrase.startswith("re:"):
				re.compile(phrase[3:])
		for allowed in entry.get("expect", ()):
			assert allowed and all(job in planner.RECIPES for job in allowed), entry
		words = plainWords(entry["request"])
		assert words not in tuned, f"{name}: \"{entry['request']}\" is a request VisionClaw was tuned on"
		assert words not in routing, f"{name}: \"{entry['request']}\" is in a set that measures choosing the job"
	assert len({plainWords(e["request"]) for e in data["requests"]}) == len(data["requests"]), name
# No request is in two of them.
every = [plainWords(e["request"]) for entries in sets.values() for e in entries]
assert len(every) == len(set(every))

# --- Whole requests that plain code decides, without a model ---


class NoModel:
	"""A runtime that answers no model call: the requests below must need none."""

	def __init__(self):
		self.calls = 0

	def hasModel(self, role):
		return True

	def entry(self, role):
		return {"thinking": False}

	def oneModel(self):
		return True

	def chat(self, role, messages, maxTokens, **options):
		self.calls += 1
		return None


development = {entry["request"]: entry for entry in sets["answers"]}
for request in ("does my recycle bin need emptying", "whats sitting in my system tray", "is dropbox in the tray",
		"what control am I on right now", "which version of visionclaw have I got"):
	runtime = NoModel()
	task, asked, _state = eval_answers.runItem(runtime, development[request])
	row = eval_answers.score(task, development[request], asked, True)
	assert runtime.calls == 0 and not asked, (request, runtime.calls, asked)
	assert row["verdict"] == eval_answers.RIGHT and row["job"] == eval_answers.RIGHT, row
# The scorer finds what is wrong in an answer: a wanted word missing, and the rules for every answer.
task, asked, _state = eval_answers.runItem(NoModel(), {"request": "does my recycle bin need emptying"})
wrongItem = {"request": "does my recycle bin need emptying", "says": [["30 items"]], "expect": [["empty_bin"]]}
row = eval_answers.score(task, wrongItem, asked, True)
assert row["verdict"] == eval_answers.WRONG and row["job"] == eval_answers.WRONG
assert row["problems"] == [[check.MISSING, "30 items"]], row
task.answer = "Sure! As you can see, the bin holds 30 items. Press NVDA+Shift+Alt+F11 to empty it."
row = eval_answers.score(task, wrongItem, asked, True)
assert {rule for rule, _what in row["problems"]} == {check.PREAMBLE, check.SIGHTED, check.MADE_UP_KEY}, row
assert "answers right" in eval_answers.summary([row], "test")

print("OK")
