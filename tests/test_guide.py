# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Working through a task when the usual path is not clear (claw/guide.py): which requests ask for it and what
the user wants, which things of a window are about it, and the walk itself on a program made up by the test that
answers to presses: every step asked about, a check-in on a longer task, staying in one program, stopping when
told, and saying what was done. Plain Python. The tool is driven in tests/test_nvda_stub.py.

  python tests/test_guide.py
"""
import harness  # noqa: F401
from visionClaw.claw import guide, planner

G = guide

# --- Which requests ask to be worked through, and what the user wants ---

GOALS = {
	"I'm stuck, I want to attach a file to this email": "attach a file to this email",
	"Walk me through exporting this as a PDF": "exporting this as a PDF",
	"I can't find how to change the font here": "change the font here",
	"I don't know how to save this document": "save this document",
	"The usual way doesn't work, I want to print this": "print this",
	"help me get this done: send this form": "send this form",
	"Guide me through sharing this folder, step by step": "sharing this folder",
	"I am stuck. I can't figure out how to reply to this message": "reply to this message",
}
for said, goal in GOALS.items():
	assert G.asks(said), said
	assert G.goalOf(said) == goal, (said, G.goalOf(said))
	assert planner.hint(said) == "work_through", (said, planner.hint(said))
# Questions, requests to be taught, and requests that name nothing to do stay what they were.
for said, recipe in {
		"How do I read the title of this window?": "explain_keys", "teach me how to use NVDA": "coach",
		"walk me through this page": "explore_page", "open notepad": "open_thing", "what is on my screen": "describe"}.items():
	assert not G.asks(said) and planner.hint(said) == recipe, (said, G.asks(said), planner.hint(said))
assert not G.asks("I'm stuck") and G.goalOf("I'm stuck") == ""
# A request that says the user is stuck stays one thing, with its commas and its "and": no model is asked to split
# it, and none is asked what to do with it.


class _Registry:
	def has(self, names):
		return True

	def get(self, name):
		return object()


for said in GOALS:
	assert planner.split(None, None, said) == [said], (said, planner.split(None, None, said))
	assert planner.decided(said, _Registry()) == "work_through", said
assert planner.split(None, None, "I'm stuck, I want to attach a file and send it, then close the window") == [
	"I'm stuck, I want to attach a file and send it, then close the window"]

# --- Which things of a window are about what is wanted ---

T = G.Thing
mail = [
	T("File", "menu item", "file", "Alt+F"), T("Message", "tab", "message"), T("Insert", "tab", "insert", "Alt+N"),
	T("Send", "button", "send", "Alt+S"), T("To", "edit field", "to"), T("Subject", "edit field", "subject"),
	T("Discard", "button", "discard"), T("Options", "tab", "options")]
ranked = G.rank("attach a file to this email", mail)
assert [thing.name for _points, thing in ranked][:2] == ["File", "Insert"], [(p, t.name) for p, t in ranked]
# "Attach File" itself, once it shows, is plain code's own choice: clearly about it, and well ahead.
shown = mail + [T("Attach File", "button", "attach", "Alt+N, A, F"), T("Pictures", "button", "pictures"), T("Link", "button", "link")]
ranked = G.rank("attach a file to this email", shown, done=["Insert"], fresh=["Attach File", "Pictures", "Link"])
assert G.sure(ranked) is not None and G.sure(ranked).name == "Attach File", [(p, t.name) for p, t in ranked]
assert all(thing.name != "Insert" for _points, thing in ranked)  # what was pressed is not offered again
# Words that mean the same in menus: export for save, settings for options, a paperclip for attach.
assert G.score("save this as a pdf", "Export") > 0 and G.score("change the settings", "Options") > 0
assert G.score("attach a file", "Paperclip") > 0 and G.score("print this", "Zoom") == 0 and G.score("", "File") == 0
# Greyed out things, and things without a name, are never offered.
assert G.rank("print this", [T("Print", "button", "p", usable=False), T("", "button", "x")]) == []
# Nothing is about it: what opens more of the program is offered, a menu, More, Tools.
more = G.rank("rotate the picture", [T("Home", "tab", "h"), T("More", "button", "m"), T("Tools", "menu item", "t"), T("OK", "button", "o")])
assert [thing.name for _points, thing in more] == ["More", "Tools"] and G.sure(more) is None
assert G.isFinal("Send") and G.isFinal("Delete message") and not G.isFinal("Attach File")
assert G.stepQuestion(2, T("Send", "button", "s", "Alt+S"), "send this form") == (
	"Step 2: Send button looks like the way to send this form. Its key is Alt+S. Pressing it may not be possible to take "
	"back. Press it for you?")
assert G.tellText(T("Insert", "tab", "i", "Alt+N")) == "Insert tab: its key is Alt+N."
assert "has no key of its own" in G.tellText(T("Paperclip", "button", "p"))
assert T("Save button", "button").said() == "Save button" and T("Save", "button").said() == "Save button"
what, new = G.changed(mail, shown, "Untitled - Message", "Untitled - Message")
assert what == "New here: Attach File button, Pictures button, Link button." and new == ["Attach File", "Pictures", "Link"], what
what, new = G.changed(mail, mail, "A", "B")
assert what == "The window in front is now B." and new == []
assert G.changed(mail, mail, "A", "A")[0] == "Nothing new showed that VisionClaw can find."

# --- The walk, on a program made up by the test ---


class Program:
	"""A mail program: pressing Insert shows the things of that tab, pressing Attach File opens a file window."""

	def __init__(self, leaves=False, dead=False):
		self.things, self.title, self.name = list(mail), "Untitled - Message", "outlook"
		self.pressed, self.leaves, self.dead = [], leaves, dead

	def look(self):
		return list(self.things), self.title, self.name

	def press(self, thing):
		self.pressed.append(thing.name)
		if self.dead:
			return
		if thing.name == "Insert":
			self.things = mail + [T("Attach File", "button", "attach", "Alt+N, A, F"), T("Pictures", "button", "pictures"), T("Link", "button", "link")]
		elif thing.name == "File":
			self.things = [T("Save As", "menu item", "saveas"), T("Print", "menu item", "print"), T("Options", "menu item", "o")]
		elif thing.name == "Attach File":
			self.things = [T("Browse This PC", "menu item", "browse"), T("Recent Items", "menu item", "recent")]
			if self.leaves:
				self.name, self.title = "explorer", "Open"


def walk(program, goal, answers, choices=None):
	asked, offered = [], []
	answers = list(answers)

	def ask(question, options):
		asked.append((question, options))
		return answers.pop(0) if answers else G.STOP

	def choose(goal, things):
		offered.append([thing.name for thing in things])
		wanted = (choices or [None]).pop(0) if choices else None
		return next((at for at, thing in enumerate(things) if thing.name == wanted), None)
	said, pressed = G.walk(goal, program.look, program.press, choose, ask)
	return said, pressed, asked, offered


GOAL = "attach a file to this email"
# 1. Two things could lead there, File and Insert: a model chooses. Then Attach File shows, plain code is sure of
#    it, and no model is asked. Every step is asked about before it is taken.
program = Program()
said, pressed, asked, offered = walk(program, GOAL, [G.YES, G.YES, G.STOP], ["Insert"])
assert pressed == ["Insert", "Attach File"] and len(offered) == 1 and offered[0][:2] == ["File", "Insert"], (pressed, offered)
assert asked[0] == ("Step 1: Insert tab looks like the way to attach a file to this email. Its key is Alt+N. Press it for you?", list(G.CHOICES))
assert asked[1][0].startswith("Step 2: Attach File button looks like the way"), asked[1]
assert said.startswith("Step 1: pressed Insert tab. New here: Attach File button, Pictures button, Link button. Step 2: pressed Attach File button."), said
# 2. "Only tell me": nothing is pressed, and the user is told the thing and its key.
program = Program()
said, pressed, asked, offered = walk(program, GOAL, [G.TELL], ["Insert"])
assert pressed == [] and program.pressed == [] and said == "The next step is Insert tab: its key is Alt+N.", said
# 3. Stopped: nothing is pressed, and what the step would have been is said.
program = Program()
said, pressed, asked, offered = walk(program, GOAL, [G.STOP], ["Insert"])
assert pressed == [] and said == "Stopped before step 1, which would have been Insert tab.", said
# 4. A model that says none of them leads there: nothing is pressed, and the nearest things are named.
program = Program()
said, pressed, asked, offered = walk(program, GOAL, [G.YES], [None])
assert pressed == [] and asked == [] and said.startswith("Nothing here is clearly the way to attach a file to this email. The nearest things are: File menu item, Insert tab"), said
# 5. It stays in one program: when a step brings another program to the front, it stops and says so.
program = Program(leaves=True)
said, pressed, asked, offered = walk(program, GOAL, [G.YES, G.YES, G.YES], ["Insert"])
assert pressed == ["Insert", "Attach File"] and "Another program is in front now, explorer." in said, said
assert said.endswith("Ask again there to go on.") and len(asked) == 2
# 6. Nothing here is about what is wanted, and nothing opens more: said, with what is there.
bare = Program()
bare.things = [T("To", "edit field", "to"), T("Subject", "edit field", "subject"), T("Send", "button", "send")]
said, pressed, asked, offered = walk(bare, "rotate the picture", [G.YES])
assert pressed == [] and said.startswith("VisionClaw finds nothing here that is about this: rotate the picture."), said
assert "What can be used here: To edit field, Subject edit field, Send button." in said, said
# Where a menu or a tab could hold it, those are offered, and a model that says none of them leads there ends it.
said, pressed, asked, offered = walk(Program(), "rotate the picture", [G.YES], [None])
assert pressed == [] and offered == [["File", "Insert", "Options"]] and said.startswith("Nothing here is clearly the way to rotate the picture."), said
# 7. Presses that bring up nothing new: after two of them it stops.
program = Program(dead=True)
said, pressed, asked, offered = walk(program, GOAL, [G.YES] * 6, ["Insert", "File"])
assert len(pressed) == 2 and "The last two steps brought up nothing new, so VisionClaw stopped." in said, (pressed, said)
# 8. A check-in on a longer task: after three steps it asks whether to go on, and a no ends it there.


class Deep(Program):
	"""A program in which every press shows one more thing that is about the goal."""

	def __init__(self):
		super().__init__()
		self.things = [T("Export step 1", "button", 1)]

	def press(self, thing):
		self.pressed.append(thing.name)
		self.things = [T(f"Export step {len(self.pressed) + 1}", "button", len(self.pressed) + 1)]


program = Deep()
said, pressed, asked, offered = walk(program, "export this", [G.YES, G.YES, G.YES, 1])
assert len(pressed) == 3 and asked[3] == ("That was 3 steps towards this: export this. Go on?", list(G.GO_ON)), asked[3]
assert "Stopped there, as you said." in said
program = Deep()
said, pressed, asked, offered = walk(program, "export this", [G.YES] * 20)
assert len(pressed) == G.MAX_STEPS and f"That was {G.MAX_STEPS} steps, the most VisionClaw takes in one go." in said, len(pressed)
# The request is stopped: nothing more is pressed.


class Stopped(Exception):
	pass


def stop():
	raise Stopped()


program = Program()
try:
	G.walk(GOAL, program.look, program.press, lambda goal, things: 1, lambda question, options: G.YES, stop)
	raise AssertionError("a stopped request went on")
except Stopped:
	assert program.pressed == []
# The tools that work the window in front, and so never VisionClaw's own windows.
assert {"click_item", "press_keys", "type_text", "set_control", "pick_date", "work_through"} <= G.OFF_LIMITS
for sentence in (G.NOT_OWN, G.NO_GOAL):
	assert not any(mark in sentence for mark in "*`_#"), sentence

print("OK")
