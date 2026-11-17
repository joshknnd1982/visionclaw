# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Narrowing what a model may write, and asking the very smallest models one small question at a time.

Plain Python with a scripted stand-in for the model: which answers the results so far allow for a field, the
form the engine is given, a form filled in one field at a time where each answer narrows the next, an answer
that only repeats the question being asked again, and an answer made of what was looked up, word for word.
What a real small model does with these questions is measured by tests/live_orchestrator.py, not here.
"""
import harness  # noqa: F401
from visionClaw.claw import agent, orchestrator, policy, shapes, tools
from visionClaw.claw import task as taskModule

FOUND = (
	"speech.rate: Speech rate. Now: 50. Allowed: a number from 0 to 100.\n"
	"speech.symbolLevel: Punctuation level. Now: some. Allowed: one of: none, some, most, all.\n"
	"keyboard.speakTypedCharacters: Speak typed characters. Now: on. Allowed: on or off."
)
LISTED = "4 items in the window:\n1. New Game button\n2. Load Game button\n3. Options button\n4. Qu ...[cut]"

# --- What the results allow ---

assert shapes.idsIn(FOUND) == ["speech.rate", "speech.symbolLevel", "keyboard.speakTypedCharacters"]
# A list that was cut off ends in a line that is not whole; it is not offered.
assert shapes.namesIn(LISTED) == ["New Game button", "Load Game button", "Options button"]
assert shapes.valueShape(shapes.lineOf(FOUND, "speech.rate")) == {"pattern": shapes.NUMBER_PATTERN}
assert shapes.valueShape(shapes.lineOf(FOUND, "speech.symbolLevel")) == {"enum": ["none", "some", "most", "all"]}
assert shapes.valueShape(shapes.lineOf(FOUND, "keyboard.speakTypedCharacters")) == {"enum": ["on", "off"]}
assert shapes.valueShape("something: text") == {} and shapes.idsIn("Nothing was found.") == []
# A result that is not only a list of ids narrows nothing: a list with one id missing would shut the right one out.
assert shapes.idsIn("Found these:\n" + FOUND) == [] and shapes.idsIn("globalCommands/title[1]: Reads the title.") == ["globalCommands/title[1]"]
assert shapes.namesIn("\n".join(f"{n}. Item {n}" for n in range(1, 40))) == []


def step(tool, result="", status=taskModule.STEP_DONE, part=""):
	made = taskModule.Step(tool.replace("_", " "), tool, part=part, recipe="x")
	made.status, made.result = status, result
	return made


steps = [step("find_setting", FOUND), step("set_setting", status=taskModule.PENDING)]
# The id may only be one that was found. What the value may be depends on the setting, so it is only known
# once the setting is: from the form so far, or when only one setting was found.
assert shapes.shapes("set_setting", ["setting", "value"], steps, 1) == {"setting": {"enum": shapes.idsIn(FOUND)}}
assert shapes.shapes("set_setting", ["value"], steps, 1, {"setting": "keyboard.speakTypedCharacters"}) == {"value": {"enum": ["on", "off"]}}
one = [step("find_setting", "speech.rate: Speech rate. Now: 50. Allowed: a number from 0 to 100."), steps[1]]
assert shapes.shapes("set_setting", ["setting", "value"], one, 1) == {
	"setting": {"enum": ["speech.rate"]}, "value": {"pattern": shapes.NUMBER_PATTERN}}
assert shapes.shapes("click_item", ["item", "action"], [step("list_items", LISTED), step("click_item")], 1) == {
	"item": {"enum": ["New Game button", "Load Game button", "Options button"]}}
# A step that failed, or a tool without a source, narrows nothing.
assert shapes.shapes("set_setting", ["setting"], [step("find_setting", FOUND, taskModule.STEP_FAILED), steps[1]], 1) == {}
assert shapes.shapes("type_text", ["textToType"], steps, 1) == {}

# --- The form the engine is given ---

setTool = tools.Tool("set_setting", "change one NVDA setting", lambda task, setting, value, asked: f"{setting} is now {value}.", {
	"setting": {"type": "string", "description": "the id of the setting, copied from find_setting", "maxLength": 80},
	"value": {"type": "string", "description": "the new value", "maxLength": 60},
	"asked": {"type": "string", "description": "what the user asked for, in their own words", "maxLength": 300, "auto": True},
}, changes=True, before="find_setting")
schema = setTool.schema(("asked",), {"setting": {"enum": ["speech.rate"]}})
assert schema["properties"]["setting"] == {"type": "string", "enum": ["speech.rate"]} and schema["properties"]["value"]["maxLength"] == 60
assert setTool.fieldText("setting", {"enum": ["a", "b"]}) == "setting: the id of the setting, copied from find_setting One of: a, b."
assert "A number only" in setTool.fieldText("value", {"pattern": shapes.NUMBER_PATTERN})
assert "One of: speech.rate." in setTool.formText(("asked",), {"setting": {"enum": ["speech.rate"]}})

# --- An answer that only repeats the question ---

assert shapes.echoes("the id of the setting, copied from find_setting", "set_setting", "setting", "the id of the setting, copied from find_setting")
assert shapes.echoes("set_setting", "set_setting", "setting", "the id") and shapes.echoes("", "t", "n", "d")
assert shapes.echoes("the control's name as the user", "add_fix", "item", "the control's name as the user said it, or the focused control")
assert not shapes.echoes("speech.rate", "set_setting", "setting", "the id of the setting, copied from find_setting")
assert not shapes.echoes("Play button", "add_fix", "item", "the control's name as the user said it")


class Scripted:
	"""A stand-in for the models: gives the next scripted answer and writes down what it was asked."""

	def __init__(self, answers):
		self.answers, self.calls = list(answers), []

	def json(self, role, system, user, schema, maxTokens=300, reasoning="off", image=None):
		self.calls.append((system, user, schema, maxTokens))
		return self.answers.pop(0)


# --- One field at a time ---

registry = tools.Registry()
registry.add(tools.Tool("find_setting", "find settings", lambda task, words: FOUND, {
	"words": {"type": "string", "description": "keywords", "auto": True}}, looks=True))
registry.add(setTool)
# Add-on, add on and addon are one word: the list of add-ons answers a question that writes it any way.
listed = "Add-ons installed (2): Clock and calendar 2.1 (enabled); NVDA Remote 2.6 (disabled)."
for question in ("Which add-ons do I have?", "what addons do i have", "list my add ons"):
	assert shapes.quote(question, listed)[0] == [listed], question
assert shapes.notMentioned("which add-ons do I have") == "What was looked up does not mention addons."
small = policy.select({"complexity": "simple"}, "off")._replace(oneByOne=True)
assert small.oneByOne and not policy.select({"complexity": "simple"}, "off").oneByOne
task = taskModule.Task("The typing echo, please")
steps = [step("find_setting", FOUND, part="The typing echo, please"), step("set_setting", status=taskModule.PENDING, part="The typing echo, please")]
llm = Scripted([{"setting": "keyboard.speakTypedCharacters"}, {"value": "off"}])
assert agent.runStep(llm, task, registry, task.request, steps, 1, small) and steps[1].result == "keyboard.speakTypedCharacters is now off."
# Two small questions, one value each. The first could only be an id that was found; the second, once the
# setting was known, only on or off. The user's own words were filled in by code.
assert len(llm.calls) == 2 and all(call[0] == agent._FIELD_SYSTEM and call[3] <= agent.FIELD_TOKENS for call in llm.calls)
assert llm.calls[0][2]["properties"] == {"setting": {"type": "string", "enum": shapes.idsIn(FOUND)}}, llm.calls[0][2]
assert llm.calls[1][2]["properties"] == {"value": {"type": "string", "enum": ["on", "off"]}}, llm.calls[1][2]
assert "Already filled in: setting = keyboard.speakTypedCharacters" in llm.calls[1][1] and "Fill in one thing. value:" in llm.calls[1][1]
assert "Fill in one thing. setting:" in llm.calls[0][1] and "asked" not in llm.calls[0][2]["properties"]

# What the user's own words already say is not asked of the model at all: here only which setting is meant.
llm = Scripted([{"setting": "keyboard.speakTypedCharacters"}])
steps = [step("find_setting", FOUND, part="Turn off the typing echo"), step("set_setting", status=taskModule.PENDING, part="Turn off the typing echo")]
assert agent.runStep(llm, taskModule.Task("Turn off the typing echo"), registry, "Turn off the typing echo", steps, 1, small)
assert steps[1].result == "keyboard.speakTypedCharacters is now off." and len(llm.calls) == 1
llm = Scripted([{"setting": "speech.symbolLevel"}])
steps = [step("find_setting", FOUND, part="Set punctuation to all"), step("set_setting", status=taskModule.PENDING, part="Set punctuation to all")]
assert agent.runStep(llm, taskModule.Task("Set punctuation to all"), registry, "Set punctuation to all", steps, 1, small)
assert steps[1].result == "speech.symbolLevel is now all." and len(llm.calls) == 1
llm = Scripted([{"setting": "speech.rate"}])
steps = [step("find_setting", FOUND, part="Speak a little faster"), step("set_setting", status=taskModule.PENDING, part="Speak a little faster")]
assert agent.runStep(llm, taskModule.Task("Speak a little faster"), registry, "Speak a little faster", steps, 1, small)
assert steps[1].result == "speech.rate is now +10." and len(llm.calls) == 1

# A free answer that repeats the question is asked for once more, in general words.
nameTool = tools.Tool("name_control", "name the focused button", lambda task, name: f"Named {name}.", {
	"name": {"type": "string", "description": "the new name for the button", "maxLength": 40}}, changes=True)
registry.add(nameTool)
llm = Scripted([{"name": "the new name for the button"}, {"name": "Play"}])
steps = [step("name_control", status=taskModule.PENDING, part="Call this button Play")]
assert agent.runStep(llm, taskModule.Task("Call this button Play"), registry, "Call this button Play", steps, 0, small)
assert steps[0].result == "Named Play." and len(llm.calls) == 2 and "That answer repeated the question." in llm.calls[1][1]

# If it repeats the question a second time, the user's own words are put in: they are at least true.
llm = Scripted([{"name": "the new name for the button"}, {"name": "new name for the button, please"}])
steps = [step("name_control", status=taskModule.PENDING, part="Call this button Play")]
assert agent.runStep(llm, taskModule.Task("Call this button Play"), registry, "Call this button Play", steps, 0, small)
assert steps[0].result == "Named Call this button Play."

# With a model that fills in a whole form at once, the form is narrowed all the same.
whole = policy.select({"complexity": "simple"}, "off")
llm = Scripted([{"setting": "speech.rate", "value": "+10"}])
steps = [step("find_setting", FOUND, part="Speak faster"), step("set_setting", status=taskModule.PENDING, part="Speak faster")]
assert agent.runStep(llm, taskModule.Task("Speak faster"), registry, "Speak faster", steps, 1, whole)
assert len(llm.calls) == 1 and llm.calls[0][0] == agent._FORM_SYSTEM
assert llm.calls[0][2]["properties"]["setting"] == {"type": "string", "enum": shapes.idsIn(FOUND)}
assert "One of: speech.rate, speech.symbolLevel, keyboard.speakTypedCharacters." in llm.calls[0][1]

# And there too, what the user's words say is filled in by code: with one setting found, only its id is asked.
llm = Scripted([{"setting": "speech.rate"}])
steps = [step("find_setting", "speech.rate: Speech rate. Now: 50. Allowed: a number from 0 to 100.", part="Speak much slower"),
	step("set_setting", status=taskModule.PENDING, part="Speak much slower")]
assert agent.runStep(llm, taskModule.Task("Speak much slower"), registry, "Speak much slower", steps, 1, whole)
assert steps[1].result == "speech.rate is now -25." and list(llm.calls[0][2]["properties"]) == ["setting"]

# --- What the user's own words already say ---

assert shapes.numberSaid("Make NVDA speak a little faster") == "+10" and shapes.numberSaid("speak much slower") == "-25"
assert shapes.numberSaid("set the rate to 70") == "70" and shapes.numberSaid("raise the pitch by 5") == "+5"
assert shapes.numberSaid("make it slightly quieter") == "-5" and shapes.numberSaid("change the speech rate") is None
assert shapes.numberSaid("volume 40 percent") == "40" and shapes.numberSaid("faster, no, slower") is None
assert shapes.onOffSaid("Turn off the typing echo") == "off" and shapes.onOffSaid("switch the typing echo on") == "on"
assert shapes.onOffSaid("Disable the beep on capitals") == "off" and shapes.onOffSaid("stop saying typed characters") == "off"
# "On" as a plain word asks for nothing, and words that pull both ways are left to the model.
assert shapes.onOffSaid("the beep on capitals") is None and shapes.onOffSaid("turn it on, not off") is None
assert shapes.optionSaid("Set punctuation to all", ["none", "some", "most", "all"]) == "all"
assert shapes.optionSaid("punctuation level most", ["none", "some", "most", "all"]) == "most"
assert shapes.optionSaid("turn off all punctuation", ["none", "some", "most", "all"]) is None
names = ["New Game button", "Load Game button", "Options button", "Quit button"]
assert shapes.namesSaid("Drag the New Game button onto the Quit button.", names) == ["New Game button", "Quit button"]
assert shapes.namesSaid("Click Options", names) == []
listed = [step("list_items", "4 items in the window:\n" + "\n".join(f"{n}. {name}" for n, name in enumerate(names, 1))), step("drag_item")]
drag = "Drag the New Game button onto the Quit button."
assert shapes.said("drag_item", "item", drag, listed, 1) == "New Game button" and shapes.said("drag_item", "to", drag, listed, 1) == "Quit button"
# One thing and a direction: the direction stays in the user's words, which the tool reads itself.
assert shapes.said("drag_item", "to", "Drag the Options button right a little", listed, 1) == "Drag the Options button right a little"
assert shapes.said("drag_item", "item", "Drag the Options button right a little", listed, 1) is None
assert shapes.said("click_item", "item", "Click the Load Game button", [listed[0], step("click_item")], 1) == "Load Game button"
assert shapes.said("click_item", "item", "Click Options", [listed[0], step("click_item")], 1) is None
assert shapes.said("type_text", "textToType", "type hello", listed, 1) is None
assert shapes.echoes("Give the control's name as the user said it", "add_fix", "item", "what the fix is about: the control's name as the user said it, the focused control")

# --- When the mode is used ---

assert policy.stepwise("auto", {"suggest": False}) and not policy.stepwise("auto", {"name": "Qwen3.5 4B"})
assert policy.stepwise("always", {"name": "Qwen3.5 4B"}) and not policy.stepwise("never", {"suggest": False})
assert not policy.stepwise("auto", None)

# --- Answers made of what was looked up ---

PAGE = (
	"Example Shop\nWelcome to our shop. We sell garden tools.\nRefund policy\n"
	"You can return any product within 30 days for a full refund.\nContact\nWrite to us by mail."
)
lines, asked = shapes.quote("What does this page say about refunds?", PAGE)
assert asked == {"refund"} and lines[0] == "Refund policy. You can return any product within 30 days for a full refund.", (asked, lines)
assert shapes.quote("What is the weather in Boston?", PAGE)[0] == []
assert shapes.notMentioned("What is the weather in Boston?") == "What was looked up does not mention weather or boston."
keys = "title: Reports the title of the current window. Keys: NVDA+t.\ndateTime: Reports the current time. Keys: NVDA+f12."
assert shapes.quote("How do I read the title of this window?", keys)[0] == ["title: Reports the title of the current window. Keys: NVDA+t."]
# Words that only say that something was searched for are not what was asked about.
assert shapes.quote("Search the web for the weather in Boston.", "From the web page Example Shop:\n" + PAGE)[0] == []

orch = orchestrator.Orchestrator(None, registry, lambda q, c: 0)
# Nothing that was looked up mentions it: said so, and no model is asked at all.
llm = Scripted([])
assert orch._quoted(llm, "What is the weather in Boston?", PAGE, "read_page") == "What was looked up does not mention weather or boston."
# One line mentions it: that line, word for word, without a model.
assert orch._quoted(llm, "What does this page say about refunds?", PAGE, "read_page").startswith("Refund policy. You can return")
# Several lines mention it: the model only chooses among them.
llm = Scripted([{"line": 2}])
answer = orch._quoted(llm, "What does the shop sell and what is its refund policy?", PAGE, "read_page")
assert answer in shapes.quote("What does the shop sell and what is its refund policy?", PAGE)[0] and len(llm.calls) == 1
assert llm.calls[0][2]["properties"]["line"]["enum"][0] == 1
# What the vision model saw is told as it is.
assert orch._quoted(Scripted([]), "What is on my screen?", "A game menu with four buttons.", "look") == "A game menu with four buttons."

print("OK")
