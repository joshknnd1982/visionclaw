# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - breaks a request into bite-size steps for small models.
#   1. The request is split into its separate parts ("turn off typing echo and set punctuation to all" is two).
#   2. Each part is matched to a recipe: a fixed, proven list of steps, one tool each.
#   3. Only a part that fits no recipe is planned freely by the model, and that plan is repaired by plain rules.
# A small model is good at choosing between a few named options and poor at inventing a plan, so it is asked
# to choose. No NVDA dependencies.

import re

from . import direct, gamepad, pointer, policy, touch
from .llm import LLMError, clip
from .task import Step
from .tools import ANSWER

# --- Recipes ---

OTHER = "other"
# name: (a few words for the user; what the user wants, for the model that chooses; the tools, in order)
RECIPES = {
	"change_setting": (
		"change an NVDA setting",
		"change how NVDA speaks or behaves: speed, voice, volume, pitch, punctuation, typing echo, or another setting",
		("find_setting", "set_setting")),
	"do_command": (
		"run an NVDA command now",
		"do one thing NVDA has a command for, now: read the window title, say the time or battery, start reading, "
		"open the NVDA menu",
		("find_command", "run_command")),
	# Both ask NVDA first, then the program in front, then its window, then Windows (asktools.py), and answer
	# from what is about the question. A question is never put to NVDA's commands alone: "how can I use the
	# keyboard to navigate my desktop" was answered with the command that switches the keyboard layout.
	"explain_keys": (
		"tell you which keys to use",
		"tell the user which keys or which command to use for something, in NVDA, in the program in front or in "
		"Windows; questions like how do I ...",
		("look_up",)),
	"nvda_question": (
		"answer a question about NVDA, this program or Windows",
		"answer a question about NVDA, the program in front, its window or Windows: what something is, what a "
		"key does, how something works, or which windows are open",
		("look_up",)),
	"describe": (
		"look at the screen and describe it",
		"say what the screen, the window, a picture or a control looks like or shows",
		("look",)),
	"read_text": (
		"read out the text that is shown",
		"read out the exact text shown in the window or on the screen",
		("read_text",)),
	"click": (
		"click an item in the window",
		"click, double-click, right-click, middle-click or hover over a button, link or other item, or press it "
		"and hold it down for some seconds, in the window in front or on the web page; also with a key held down "
		"or at a place on the item",
		("list_items", "click_item")),
	"press_keys": (
		"press keys in the program",
		"press keyboard keys in the program in front",
		("press_keys",)),
	"type_text": (
		"type text into the program",
		"type text into the program in front",
		("type_text",)),
	"make_hotkey": (
		"give this program a hotkey",
		"give this program a hotkey that clicks something or reads something in its window",
		("list_items", "create_helper")),
	"name_button": (
		"give the focused button a name",
		"give the focused button, which has no useful name, a name",
		("name_control",)),
	"write_addon": (
		"write an add-on",
		"write an NVDA add-on: new behaviour such as speaking or beeping when something happens, "
		"or anything the other choices cannot do",
		("create_addon",)),
	"list_made": (
		"list what VisionClaw has made",
		"list only what VisionClaw itself has made: its hotkey helpers and the small add-ons it wrote",
		("list_helpers",)),
	"remove_made": (
		"remove something VisionClaw made",
		"remove a helper or add-on VisionClaw made",
		("list_helpers", "remove_helper")),
	"open_website": (
		"open a website",
		"open a website or a web address in the browser",
		("web_open",)),
	"search_web": (
		"search the web",
		"search the web for something and say what was found",
		("web_search", "read_page")),
	"web_page": (
		"read the web page and answer",
		"answer a question about the web page that is open in the browser, or summarize it",
		("read_page",)),
	"page_outline": (
		"say how the web page is laid out",
		"list the headings of the web page, or say how the page is laid out and what is on it",
		("page_outline",)),
	"go_to": (
		"move to a place on the web page",
		"move NVDA's reading position to a heading, section, link or field of the web page, to read on from there",
		("list_items", "go_to_item")),
	"page_navigate": (
		"go back, forward or reload",
		"go back or forward one page in the browser, or reload the page",
		("page_navigate",)),
	"fill_field": (
		"type into a field",
		"type text into a named field or box, such as a search box or a field of a form",
		("list_items", "fill_field")),
	"nvda_info": (
		"tell you what NVDA has and uses",
		"say which speech synthesizer, voice, braille display, braille table, driver or version NVDA has or "
		"uses and how they are set, or which add-ons are installed in NVDA",
		("nvda_info",)),
	"visionclaw_models": (
		"tell you which AI models VisionClaw uses",
		"say which AI model or models VisionClaw itself, the assistant, has installed, downloaded or stored and "
		"is using or running, how big they are, and where they run",
		("model_info",)),
	"switch_driver": (
		"switch the speech synthesizer or braille display",
		"switch NVDA to a different speech synthesizer or a different braille display",
		("nvda_info", "switch_driver")),
	"fix_addon": (
		"debug and correct an add-on",
		"fix, debug or change an add-on VisionClaw wrote that fails or does not do what it should",
		("list_helpers", "repair_addon")),
	"undo_change": (
		"put a setting back",
		"undo a change VisionClaw made: put a setting back to what it was before, restore it, revert it",
		("undo_change",)),
	"list_changes": (
		"say what VisionClaw has changed",
		"say which settings VisionClaw has changed",
		("list_changes",)),
	"save_addon": (
		"save an add-on as a file",
		"save an add-on VisionClaw wrote as a file that can be installed for good or shared",
		("list_helpers", "export_addon")),
	"check_access": (
		"inspect this page or window for accessibility problems",
		"inspect the web page, the program's window or the focused control in depth, and report what makes it "
		"hard to use with a screen reader and what can be fixed",
		("check_access",)),
	"fix_access": (
		"fix the accessibility problems here with an add-on",
		"fix the accessibility problems of the website or program the user is in, all of them or the one they "
		"name, with an add-on that stays; make a website or a program accessible",
		("check_access", "fix_access")),
	"add_fix": (
		"add one lasting fix for this website or program",
		"for the website or program the user is in, make one lasting fix they describe: a key that presses or "
		"reads a control by its name, keys that move between posts, results or other items, a name for a control "
		"that has none, or being told when a part of it changes",
		("check_access", "add_fix")),
	"addon_question": (
		"answer a question about an installed add-on",
		"say what one add-on installed in NVDA does, whether it is on, which keys it has, or how to use it; or "
		"which of the installed add-ons can do something the user wants",
		("addon_info",)),
	"coach": (
		"coach you with the lessons of NVDA Coach",
		"coach, teach or train the user in NVDA with the add-on NVDA Coach: open it, give a hint, a step or a whole "
		"lesson from it, say which lessons it has or how far the user is; only when the user asks to be coached, "
		"taught or trained, or for a lesson or a hint",
		("coach",)),
	"drag": (
		"drag something with the mouse",
		"drag an item with the mouse onto another item or in a direction, or move a slider",
		("list_items", "drag_item")),
	"work_control": (
		"let the arrow keys work a dial or slider",
		"let the arrow keys work a dial, knob, custom slider or other control that is only worked by dragging it "
		"with the mouse, and say what it shows",
		("work_control",)),
	"update_visionclaw": (
		"look for a newer version of VisionClaw",
		"look for a newer version of VisionClaw itself, the add-on, and get it; check whether VisionClaw is up to date",
		("check_update",)),
	"update_guides": (
		"download the latest NVDA developer guides",
		"download the latest NVDA developer guide and add-on development guide from the internet, for the models "
		"to read up in",
		("update_guides",)),
	"guides_info": (
		"say which developer guides are on this computer",
		"say which NVDA developer guides VisionClaw has downloaded, how old they are and where they are kept, or "
		"open their folder; not a question about what the guides say",
		("guides_info",)),
	"remove_guides": (
		"delete the developer guides from this computer",
		"delete the downloaded NVDA developer guides from this computer",
		("remove_guides",)),
	"downloads_info": (
		"say what VisionClaw can download for you",
		"say what VisionClaw can download for the user on request, guides, lessons and notes, whether each is here "
		"already, and what to say to get it; not for downloading it",
		("downloads_info",)),
	"update_training": (
		"download free material that teaches NVDA",
		"download free material that teaches NVDA from the internet, the NVDA wiki, the lessons of the American "
		"Foundation for the Blind and the workshops of Hadley, to look things up in",
		("update_training",)),
	"training_info": (
		"say which training material is on this computer",
		"say which training material about NVDA VisionClaw has downloaded, how old it is and where it and NVDA's "
		"own help are kept as Markdown files, or open the folder; not a question about what the material says",
		("training_info",)),
	"remove_training": (
		"delete the training material from this computer",
		"delete the downloaded NVDA training material from this computer",
		("remove_training",)),
	"scroll": (
		"scroll with the mouse wheel",
		"scroll what the window shows up, down, left or right with the mouse wheel, a little, a page or to the "
		"end, where the keyboard does not scroll it; or zoom in or out with the wheel",
		("scroll_view",)),
	# What is worked neither by a click nor by a drag from one thing to another (claw/pointer.py).
	"gesture": (
		"swipe or draw a gesture with the mouse",
		"swipe, flick or draw a line, a circle or another shape with the mouse button held down, on an item or in "
		"the window, where a program is worked by gestures",
		("draw_gesture",)),
	"timed_click": (
		"click when something changes, or many times in a row",
		"watch an item and click it as soon as it changes or appears, or click it many times in a row in a steady "
		"rhythm; for games and controls where the moment of the click matters",
		("timed_click",)),
	# What no mouse pointer does (claw/touch.py, claw/direct.py): fingers, pressure, and a game that reads the
	# mouse directly. And a game controller as a way to work any window (claw/gamepad.py).
	"touch": (
		"touch the screen as fingers would",
		"touch the screen as fingers would: pinch or spread with two fingers, swipe with two or more fingers, turn "
		"with two fingers, double tap, or touch and hold, on an item or in the window, for a program worked by touch",
		("touch_gesture",)),
	"pressure": (
		"press as hard as you say, like a pen",
		"press on something lightly, firmly or with a pressure the user names, or draw a line with pressure, as a "
		"pen does, for a drawing program or a control that feels how hard it is pressed",
		("pen_stroke",)),
	"turn_view": (
		"turn or look in a game by moving the mouse itself",
		"turn left or right, look up or down, turn around or aim in a game whose view follows the mouse, by moving "
		"the mouse itself",
		("turn_view",)),
	"mouse_way": (
		"say or keep how this program uses the mouse",
		"say or keep how the mouse is moved in the program or game in front: that it draws a pointer of its own, "
		"that the mouse turns the view, that direct mouse movement is too fast or too slow, or the usual way again",
		("mouse_way",)),
	"controller_info": (
		"tell you about the game controller",
		"say whether a game controller, gamepad or joystick is connected, and what its buttons, sticks and "
		"triggers do",
		("controller_info",)),
	"controller_mode": (
		"turn controller mode on or off",
		"turn controller mode on or off, so that a connected game controller works the mouse pointer in any window",
		("controller_mode",)),
	"keyboard_mouse": (
		"let you work the mouse pointer with the keyboard",
		"turn on pointer mode, so the user can work a control, canvas or game that has nothing to list: the arrow "
		"keys move the mouse pointer, and keys click, right-click, drag, hover and click when something changes",
		("pointer_mode",)),
	"where_am_i": (
		"say where you are",
		"say which program, window and control the user is in",
		("focus_info",)),
	"object_facts": (
		"say what NVDA knows about a control",
		"give the technical facts of one control or window on the screen, for the focused control, the navigator "
		"object, the window in front or what is under the mouse: its kind, states, position and size, window "
		"class, process",
		("object_info",)),
	"inside_nvda": (
		"look inside NVDA's program code",
		"say what a function, class, module, object or value inside NVDA's own program code or an add-on's code "
		"is, how it is called, and what it holds or gives back now; for people who write add-ons",
		("find_nvda", "inspect_nvda")),
	"audit_nvda": (
		"list everything in this NVDA",
		"make a full audit of this NVDA: count and list every command, module, function, class and object it "
		"has, and how it works its speech synthesizer and braille display, and save the list as a file",
		("audit_nvda",)),
	# Skills: how and when VisionClaw does a kind of job (claw/skills.py). The user's own are made in words or in
	# the skills window.
	"add_skill": (
		"make a new skill",
		"make a new skill: teach VisionClaw, in the user's own words, how or when to do a kind of job, kept for "
		"later requests",
		("add_skill",)),
	"list_skills": (
		"say which skills VisionClaw has",
		"say which skills VisionClaw has, or open the skills window",
		("list_skills",)),
	"show_skill": (
		"say what one skill does",
		"say what one skill does, when it is used and what it tells VisionClaw",
		("list_skills", "show_skill")),
	"manage_skill": (
		"delete, turn off or turn on a skill",
		"delete one of the user's skills, or turn a skill off or on",
		("list_skills", "manage_skill")),
	"learn_app": (
		"learn about this program from the internet",
		"go online and learn about the program or game the user is in, or one they name, and keep notes on it; "
		"only when the user asks to learn about, study or research a program, or to make notes on it",
		("learn_app",)),
	"note_page": (
		"add this web page to the notes on a program",
		"add what the web page that is open in the browser says to the notes on a program the user names",
		("note_page",)),
	"app_notes": (
		"say which notes VisionClaw has, or open them",
		"say which programs VisionClaw has notes on, or open the notes on a program so the user can read them",
		("app_notes",)),
	"forget_notes": (
		"delete notes on a program",
		"delete the notes VisionClaw made about a program: the one named, the one the user is in, or all of them",
		("forget_notes",)),
	"visionclaw_log": (
		"open VisionClaw's log",
		"open VisionClaw's own debug log, the file that records what VisionClaw did and every error, to find "
		"out why something went wrong",
		("show_log",)),
	# What the user asks VisionClaw to remember, kept as Markdown files (claw/memories.py), and the user's
	# library of documents that questions are also answered from (claw/library.py).
	"remember": (
		"remember something for you",
		"keep something the user asks VisionClaw to remember for later: about themselves, how they like things done, "
		"a program, or where something is",
		("remember",)),
	"memories": (
		"say what VisionClaw remembers",
		"say what VisionClaw remembers that the user asked it to remember, or open the list of memories",
		("memories",)),
	"forget_memory": (
		"forget something VisionClaw remembers",
		"delete something VisionClaw remembers: what the user names, the last thing it remembered, or everything",
		("forget_memory",)),
	"library": (
		"say what is in your library of documents",
		"say which documents are in VisionClaw's library, or open the library's folder so the user can add some",
		("library",)),
}
# Words that point to a recipe. Checked in this order; the first that matches is the hint given to the model,
# and the choice when the model fails.
_HINTS = (
	# Skills. First: the word "skill" can hardly mean anything else.
	("manage_skill", r"\b(delete|remove|forget|erase|get rid of|turn off|turn on|switch off|switch on|disable|enable|stop using|start using)\b.*\bskills?\b"),
	("show_skill", r"\b(read|show|explain|describe|tell me about|what does|what is)\b.*\b(the|my) [\w' -]{1,60} skill\b|\bskill (called|named)\b"),
	("list_skills", r"\b(which|what|list|show|open|how many)\b.*\bskills\b|\bskills (window|folder|list)\b"),
	("add_skill", r"\b(make|create|add|write|teach|save|new)\b.*\bskills?\b"),
	("update_visionclaw", r"\b(update|upgrade|updates|new version|newer version|latest version|up to date)\b.*\bvisionclaw\b"
		r"|\bvisionclaw\b.*\b(update|updates|upgrade|new version|newer version|latest version|up to date)\b"
		r"|\b(check|look) for (an? |any )?(updates?|new(er)? version)\b"),
	# What can be downloaded at all. Before the hints for downloading one thing, which its words also have.
	("downloads_info", r"\bwhat\b.{0,40}\b(can|could|may|would) (you|visionclaw)\b.{0,20}\b(download|fetch|get from the internet|get for me)\b"
		r"|\bwhat (else )?(can|could) (you|visionclaw) (learn from|read up in|get me)\b"
		r"|\b(what|which) (other |more )?(guides|help|materials?|lessons|documentation)\b.{0,30}\b(can|could)\b.{0,20}\b(download\w*|get)\b"
		r"|\bwhat (is|are) (there|available) to download\b|\bdownloadable\b|\bcan be downloaded\b"),
	# Free material that teaches NVDA, downloaded when asked: deleting it, getting it, and what is here. Before
	# the hints for being coached, which the words training and lessons would otherwise set off.
	("remove_training", r"\b(delete|remove|erase|get rid of|throw away)\b.*\b(training|learning|teaching) (material|materials|pages|files|resources)\b"
		r"|\b(delete|remove|erase)\b.*\b(afb|hadley|wiki)\b.*\b(lessons?|pages?|material|workshops?)\b"),
	("update_training", r"\b(download|get|pull|fetch|update|refresh|renew)\b.*\b(training|learning|teaching) (material|materials|pages|files|resources)\b"
		r"|\b(download|fetch)\b.*\b(tutorials|lessons|workshops|training)\b"
		r"|\b(download|get|fetch|update)\b.*\b(nvda wiki|wiki pages?|afb|hadley)\b"),
	("training_info", r"^(?!.*\b(says?|said|about|explain|mean|tell me how|how (do|can|to)|teach)\b).*("
		r"\b(which|what|do i have|have i got|do you have|have you got|are|is|how old|when|where|open|show|list)\b.*"
		r"\b(training|learning|teaching) (material|materials|pages|files|resources)\b"
		r"|\b(where|which)\b.*\b(markdown|md) files\b)"),
	# The developer guides themselves: deleting them, getting them, and which ones are here. What the guides say
	# about something is a question, and goes to the hints for questions below.
	("remove_guides", r"\b(delete|remove|erase|get rid of|throw away)\b.*\b(developer|development|dev)\b.*\bguides?\b"),
	("update_guides", r"\b(download|get|pull|fetch|update|refresh|renew)\b.*\b(developer|development|dev)\b.*\bguides?\b"
		r"|\b(developer|development|dev) guides?\b.*\b(up to date|latest|newest|download|update)\b"),
	("guides_info", r"^(?!.*\b(says?|said|about|explain|mean|tell me how|how (do|can|to)|write|according)\b).*("
		r"\b(which|do i have|have i got|do you have|have you got|are|is|how old|when|where|open|show|list)\b.*"
		r"\b(developer|development|dev)\b.*\bguides?\b"
		r"|\b(developer|development|dev) guides?\b.*\b(downloaded|installed|stored|kept|saved|on (this|my) computer|here|old|from)\b)"),
	# Notes on programs, learned from the internet. Before everything that the words page, list or remove
	# would otherwise set off.
	("forget_notes", r"\b(delete|remove|forget|erase|clear|get rid of)\b.*\bnotes?\b"),
	# Memories: what is remembered, then keeping one, then forgetting one. "Don't forget" keeps one.
	("memories", r"\b(what|which|anything)\b.{0,20}\byou (remember|remembered|know about me|memori[sz]ed)\b"
		r"|\b(list|show|open|read|see)\b.{0,30}\bmemor(y|ies)\b"),
	# "Forget everything you remember" forgets; "don't forget that ..." keeps.
	("forget_memory", r"^(?!.*\b(don'?t|do not) forget\b).*\bforget\b|\b(delete|remove|erase|clear)\b.*\bmemor(y|ies)\b"),
	("remember", r"\b(remember|memori[sz]e|don'?t forget|do not forget|keep in mind|bear in mind|"
		r"(make|take) a note that|note that)\b"
		# Only a statement and nothing more: "I'm new to NVDA. How do I ...?" is a question, and what it says
		# about the user is kept after it is answered (orchestrator._keep).
		r"|^\s*(please )?(call me|my name is|i am new to|i'm new to)\b[^?.!;]*[.!]?\s*$"),
	("library", r"\b(my|your|visionclaw'?s|the) library\b|\blibrary (folder|of documents)\b"),
	("note_page", r"\b(add|put|save|keep)\b.*\b(page|site|article)\b.*\bnotes?\b"
		r"|\bnotes?\b.*\bfrom (this|the) (web ?page|page|web ?site|site|article)\b"),
	("app_notes", r"\b(which|what|list|show|open|read)\b.*\bnotes\b"),
	("learn_app", r"\b(learn|study|research|read up)\b.*\b(app|application|program|game|utility|software|tool|this|it)\b"
		r"|\b(make|take|write|create)\b.*\bnotes\b|\blearn (about|how to use)\b"),
	# A game controller. A button of it as a hotkey first; then the mode; then anything asked about it. Before
	# the hints that "turn on", "how do I" and "click" would otherwise set off.
	("make_hotkey", r"\b(make|let|have|set|bind|assign|map|give)\b.*\b(button|trigger|bumper|shoulder|d-?pad)\b.*"
		r"\b(controller|game ?pad|joy ?pad|joystick)\b"
		r"|\b(make|let|have|set|bind|assign|map)\b.*\b(controller|game ?pad|joy ?pad|joystick)('s)?\b.*"
		r"\b(button|trigger|bumper|shoulder|d-?pad)\b.*\b(click|press|read|say|hover|hold)\b"),
	("controller_mode", r"\b(controller|game ?pad|joy ?pad|joystick) mode\b"
		r"|\b(turn|switch)\b.{0,12}\b(on|off)\b.*\b(controller|game ?pad|joy ?pad|joystick)\b"
		r"|\b(use|work|move|control|operate|drive|steer)\b.*\b(mouse|pointer|cursor|computer|pc|windows?|screen|nvda|program|app)\b.*"
		r"\bwith (my |the |a |an |this )?(xbox |game |playstation )?(controller|game ?pad|joy ?pad|joystick)\b"
		r"|\b(controller|game ?pad|joy ?pad|joystick)\b.*\b(as|like|instead of) (a |the |my )?mouse\b"
		r"|\b(start|stop) using (my |the |a )?(xbox |game )?(controller|game ?pad|joy ?pad|joystick)\b"),
	("controller_info", r"\b(is|are|do i have|have i|which|what|any|can you (see|find|detect)|detect\w*|check|find|how)\b.*"
		r"\b(controller|game ?pad|joy ?pad|joystick)s?\b"
		r"|\b(controller|game ?pad|joy ?pad|joystick)s?\b.*\b(connected|plugged|detected|found|there|buttons?|triggers?|sticks?)\b"),
	# How a game uses the mouse: kept for the program. Before the hints that "mouse" and "pointer" set off.
	("mouse_way", r"\bown (mouse )?(pointer|cursor)\b|\b(pointer|cursor) of its own\b|\breads? the mouse (directly|itself)\b"
		r"|\bdirect(ly)? mouse\b|\bmouse\b.{0,20}\bdirectly\b|\braw (mouse|input)\b|\bmouse ?look\b|\bcaptures? the mouse\b"
		r"|\bmouse (turns?|moves?|rotates?|steers?|controls?) the (view|camera|character|player|aim|crosshairs?)\b"
		r"|\b(normal|usual|ordinary|windows'?s?) (mouse )?(pointer|cursor) again\b"
		r"|\bhow (does|is) (this|the) (game|program|app)\b.*\b(mouse|pointer)\b"),
	# Fingers: a pinch, a spread, a number of fingers, a touch that is held. Before the mouse's own gestures,
	# the click that holds, and the wheel that zooms.
	("touch", r"\bpinch(es|ed|ing)?\b|\b(one|two|three|four|five|[1-5])[- ]finger(s|ed)?\b"
		r"|\bwith (a|one|two|three|four|five|both|my|[1-5]) fingers?\b|\bmulti-?touch\b|\btouch gestures?\b"
		r"|\btouch(es)? and holds?\b|\b(double|triple)[- ]tap\b|\btouch ?screen\b"
		r"|\bspread(s|ing)? (it |them |the \w+ )?(out|apart|with)\b"),
	# How hard: a pen's pressure. Before the mouse's gestures and clicks.
	("pressure", r"\bpressure\b|\b(pen|stylus)\b.*\b(press|draw|stroke|line|write|sign|tap|touch|eras\w+)\b"
		r"|\b(press|push|draw|tap|touch|stroke)\w*\b.{0,60}\b(harder|hard|lightly|softly|firmly|gently|lighter|softer)\b"
		r"|\b(hard|firm|light|soft|gentle) (press|touch|stroke)\b|\bforce (touch|click|press)\b"),
	# A view that follows the mouse. "Turn up the volume" and "look up the weather" are not meant.
	("turn_view", r"^(?!.*\b(volume|speed|rate|pitch|sound|music|voice|brightness|heating|lights?)\b).*("
		r"\bturn (the (view|camera|character|player) )?(to the |a little |slightly |sharply |all the way |a bit |a lot |far |right )?"
		r"(left|right|around|round)\b"
		r"|\blook (a little |slightly |a bit |a lot |far |straight |further )?(left|right|around|behind|up|down)\b"
		r"(?! (the|a(?! (little|bit|lot)\b)|an|my|this|that|what|how|for|on|in|at|it|its|their|where|who|which|whether|if)\b)"
		r"|\b(aim|face|steer) (a little |slightly |a bit |a lot |further )?(to the )?(left|right|up|down|higher|lower)\b"
		r"|\bmove the (mouse|camera|view|crosshairs?|aim) (itself |directly )?(a little |a lot |a bit )?(to the )?(left|right|up|down)\b"
		r"|\bturn (the |my )?(view|camera)\b)"),
	# A control that is dragged or turned: the arrow keys take over. Before the hotkey, mouse and drag hints.
	("work_control", r"\b(dial|knob|fader)s?\b"
		r"|\barrow keys?\b.*\b(work|turn|move|operate|control)\b.*\b(slider|control|lever)\b"
		r"|\b(work|turn|operate|move)\b.*\b(slider|control|lever)\b.*\b(arrow keys?|keyboard|keys)\b"
		r"|\b(used|worked|operated|moved) (only )?by (clicking and )?dragging\b"),
	# All of NVDA at once. Before the inspection of a page or window, which the word "audit" also means.
	("audit_nvda", r"^(?!.*\b(page|site|web|window|button|control)\b).*(\b(audit|inventory)\b.*\bnvda\b"
		r"|\bnvda\b.*\b(audit|inventory)\b"
		r"|\b(list|count|show)\b.*\b(every|all|everything)\b.*\b(in|inside|of)\b.*\bnvda\b"
		r"|\beverything (that is )?(in|inside) nvda\b)"),
	# VisionClaw's own log; NVDA's log viewer is an NVDA command.
	("visionclaw_log", r"\bvisionclaw('s)? (debug |error )?log\b|\b(debug|error) log\b"
		r"|\blog\b.*\b(of|from|for) visionclaw\b"),
	# Something inside NVDA's code, by its kind or by a dotted name like api.getFocusObject. Before the
	# add-on hints, which the word "code" would otherwise set off.
	("inside_nvda", r"\b(function|method|class|module|python object)s?\b.*\b(nvda|add-?on)('s)?\b"
		r"|\b(nvda|add-?on)('s)?\b.*\b(functions?|methods?|class(es)?|modules?|python objects?|source code)\b"
		r"|\b[a-z_]\w*\.(get|is|has|set)[a-z_]\w+|\binside nvda('s)? (code|program)\b"),
	("save_addon", r"\b(save|export|package|share)\b.*\badd-?on"),
	("list_changes", r"\bwhat\b.*\b(did|have|has)\b.*\b(you|visionclaw)\b.*\bchanged?\b|\bwhich settings\b.*\bchanged\b"),
	("undo_change", r"\b(undo|revert|restore)\b|\b(put|change|set|turn)\b.*\bback\b|\bback to (what|how|the way)\b"
		r"|\bas it was\b|\bwhat it was before\b"),
	# Fixing a website or a program, not an add-on: "fix the add-on ..." stays with fix_addon below.
	# These three are kept narrow on purpose: each needs words that can hardly mean anything else, because a
	# hint is what the model is told the words suggest, and the choice when the model fails.
	("fix_access", r"^(?!.*\b(fix|repair|correct|debug) (the |my |that |this )?add-?on\b)(?=.*("
		r"\b(fix|repair)\b.*\baccessib\w*"
		r"|\b(fix|repair) (this|the|that) (web ?page|page|web ?site|site|window|program|app|game)\b"
		r"|\b(fix|repair) (everything|all of (it|them)|(it|them) all|number \d+|problem \d+)\b"
		r"|\b(fix|repair)\b.*\b(unlabell?ed|unnamed|nameless)\b"
		r"|\b(fix|repair)\b.*\b(buttons?|links?|controls?|fields?|images?)\b.*\b(no|without|missing)\b.*\b(names?|labels?)\b"
		r"|\b(fix|repair)\b.*\b(on|of) (this|the) (web ?page|page|web ?site|site)\b"
		r"|\bmake\b.*\b(page|web ?site|site|window|program|app|game)\b.*\b(accessible|usable|easier to use)\b"
		r"|\bmake (it|this|that) (more |fully )?accessible\b"
		r"|^(please )?fix (it|them|these|those)( all)?( please)?[.!]?$))"),
	("check_access", r"\b(inspect|audit)\b|\bdeep(ly)? (inspection|look|check|scan|query)\b"
		r"|\b(check|scan|test|analy[sz]e|review|query|examine)\b.*\b(accessib\w*|usab\w*)\b"
		r"|\baccessib\w* (problems?|issues?|check|report)\b|\bis (this|the) .*\baccessible\b|\bhow accessible\b"
		r"|\bwrong with (this|the) (web ?page|page|web ?site|site|window|program|app|button|control)\b"),
	("add_fix", r"\b(make|give|add|create|set up)\b.*\b(keys?|hot ?keys?|shortcuts?)\b.*\b(page|web ?site|site|posts?|feed|videos?|player|results?)\b"
		r"|\b(make|give|add|create|set up)\b.*\b(page|web ?site|site)\b.*\b(keys?|hot ?keys?|shortcuts?)\b"
		r"|\b(make|let|have)\b.*\b(nvda|control|ctrl|alt|shift)\s*\+\s*\w+.*\b(press|click|read|say|activate)\b"
		r"|\b(tell me|announce|let me know)\b.*\bwhen\b.*\b(changes?|updates?|arrives?)\b"
		r"|^(please )?(name|label|rename)\b.*\b(on|for|in) (this|the) (web ?page|page|web ?site|site)\b"),
	# A click at the right moment, or many in a rhythm. Before the add-on hints, which "when it changes" would
	# otherwise set off; it needs a click and a moment or a count, so "tell me when it changes" is not meant.
	("timed_click", r"\b(click|tap|hit)\b.*\b(when|as soon as|the moment|once)\b.*\b(changes?|appears?|shows?|lights?|turns?"
		r"|moves?|flashes|blinks?|comes?|pops?|starts?|stops?|reaches|fills?|is (ready|there|green|red|lit|full|on|off))\b"
		r"|\b(click|tap)\b.*\b(\d+|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty|fifty|hundred) times\b"
		r"|\b(click|tap)\b.*\b(repeatedly|rapidly|over and over|again and again|in (a|time|rhythm)|on the beat|as fast as)\b"
		r"|\bkeep (on )?clicking\b|\b(click|press|tap|hit)\b.*\bat the right (moment|time)\b"),
	("fix_addon", r"\b(fix|repair|correct|debug)\b.*\badd-?on|\badd-?on\b.*\b(does(n't| not) work|is broken|stopped working|fails|wrong)\b"),
	("remove_made", r"\b(remove|delete|get rid of)\b.*\b(helper|hot ?key|add-?on)"),
	("list_made", r"\b(list|show|which|what)\b.*\b(helpers?|add-?ons?)\b.*\b(you|visionclaw)\b.*\b(made?|wrote|writes?|written|created?|built|build)\b"
		r"|\b(list|show|which|what)\b.*\b(you|visionclaw)\b.*\b(made|wrote|written|created|built)\b"),
	("write_addon", r"\b(write|make|create|build|code|program)\b.*\b(add-?on|plug-?in|code|script)\b|every time|whenever|automatically|when (a|an|the|i) .* (gets?|gains?|changes?|appears?|opens?)"),
	("make_hotkey", r"hot ?key|shortcut (key )?(for|to|that)|\bkey (for|to|that)\b"),
	("name_button", r"\b(name|label|call)\b.*\b(button|control|icon)|unlabel|no label|has no name"),
	("switch_driver", r"\b(switch|change|use|set)\b.*\b(synthesi[sz]ers?|synths?|braille (display|driver))\b"
		r"|\b(switch|change) to (espeak|one ?core|sapi|eloquence|no speech|no braille)"),
	("page_navigate", r"\b(go|navigate|move|take me)\s+(back|forward)\b|\b(previous|last|next) page\b|\b(reload|refresh)\b"),
	("page_outline", r"\b(headings|outline|laid out|layout|structure)\b"),
	("go_to", r"\b(go|jump|move|take me|skip)\b.*\b(to|down to)\b.*\b(heading|section|part|link|field|box|form|main content|comments?)\b"),
	("search_web", r"\b(search|look up|google)\b.*\b(web|internet|online|for)\b"),
	("open_website", r"\b(open|go to|visit|load|browse to)\b.*(\w\.[a-z]{2,}\b|web ?site|web ?page|\burl\b)"),
	("fill_field", r"\b(type|enter|write|fill|put)\b.*\b(in|into)\b.*\b(field|box|form|search)\b"),
	# One add-on, named: "the Clock add-on". Questions about add-ons in general stay with nvda_info below.
	# Being coached, taught or trained in NVDA, with the add-on NVDA Coach where it is installed. Only where the
	# user's own words ask for it; "how do I ..." stays a question.
	("coach", r"\bnvda coach\b|\bcoach(ing)? me\b|\b(teach|train|tutor) me\b|\bgive me (a |some |another )?(hint|lesson|clue)s?\b"
		r"|\b(a|an|the|my|next|another|first|whole|full) (nvda )?(lesson|tutorial)s?\b|\b(which|what|how many) lessons\b"
		r"|\bhints? (for|about|on)\b|\bjust a hint\b|\b(start|open|continue|resume) (the |my |nvda )?(coach|training|lessons?)\b"),
	("addon_question", r"\b(is there|are there|do i have|have i got|which|what|any)\b.{0,30}\badd-?ons?\b.{0,12}\b(for|that|to|can|could|lets?|helps?)\b"
		r"|\bwhich of my add-?ons\b|\b(use|using|with) (an|my|one of my|any of my) add-?ons?\b"),
	("addon_question", r"\b(what|how|which|tell me|explain|help|does|is)\b.*\b(the|my) [\w .-]{0,40}add-?on\b(?!s)"
		r"|\b(about|use|using) (the|my) [\w .-]{0,40}add-?on\b(?!s)"),
	("nvda_info", r"\b(which|what|list|show|tell me|do i have)\b.*\b(synthesi[sz]ers?|synths?|voices?|braille|drivers?|add-?ons?|version)\b"),
	# VisionClaw's own models. After nvda_info, so that the model of a braille display stays there; and not for
	# a model that is shown in a picture or named on a page.
	("visionclaw_models", r"^(?!.*\b(picture|image|photo|screen|window|page|site|article|car|phone|printer)\b)(?=.*("
		r"\b(which|what|list|show|tell me|do i have|do you have|how many|how big|how large|is|are|name)\b.*\b(models?|qwen|llms?)\b"
		r"|\b(models?|qwen|llms?)\b.*\b(installed|downloaded|stored|loaded|running|in use|being used|chosen|selected)\b"
		r"|\bwhat (ai|a\.i\.) (is|are)\b|\bwhich (ai|a\.i\.)\b))"),
	("explain_keys", r"how (do|can|would|to) |what (key|keys|command|shortcut)|which (key|keys|command)|shortcut for"),
	("keyboard_mouse", r"\bpointer mode\b|\bmouse (mode|keys)\b|\b(keyboard|arrow keys?)\b.*\b(mouse|pointer)\b"
		r"|\b(mouse|pointer)\b.*\b(keyboard|arrow keys?)\b|\bkeyboard[- ](navigable|accessible)\b"),
	# A line or shape drawn with the button down. Before the drag and scroll hints.
	("gesture", r"\bswip(e|es|ed|ing)\b|\bflick(s|ed|ing)?\b|\b(mouse )?gestures?\b"
		r"|\bdraw(s|ing)?\b.*\b(circle|line|tick|check ?mark|zig-?zag|square|triangle|cross|letter|shape)\b"),
	# Holding the button down, the middle button, and a key held during a click are clicks; said before the
	# hints that "volume" or "control" would otherwise set off.
	("click", r"\b(press|click|tap|push)(es)? and hold\b|\bhold(ing)? (down|the (left )?(mouse )?button)\b|\blong[- ](press|click)\b"
		r"|\bmiddle[- ](click|button)\b|\btriple[- ]click\b|\b(ctrl|control|shift|alt)\s*[-+ ]\s*click\b"),
	("drag", r"\bdrag\b|\bslider\b|\bdrop\b.*\b(on|onto|into)\b"),
	("scroll", r"\bscroll(s|ed|ing)?\b|\bmouse wheel\b|\bzoom(s|ed|ing)? (in|out)\b"),
	("change_setting", r"speed|rate\b|faster|slower|louder|quieter|volume|pitch|voice|punctuation|echo|braille|setting|turn (on|off)|switch (on|off)|enable|disable|stop (saying|reading|announcing|speaking)"),
	("click", r"\bright[- ]click\b|\bdouble[- ]click\b|\bhover\b|\bpoint (at|to)\b"),
	("click", r"\b(click|press|push|activate|select|choose|start|open)\b.*\b(button|link|item|menu|tab|icon|game|option)|\bclick\b"),
	("press_keys", r"\bpress\b.*\b(key|enter|escape|tab|control|alt|shift|f\d+)\b"),
	("type_text", r"\btype\b|\bwrite\b.*\binto\b"),
	# The facts NVDA holds about one object. Kept narrow: "report the navigator object" is an NVDA command.
	("object_facts", r"\b(properties|property|attributes?|facts|details|everything|all)\b.*\b(about|of|on)\b.*"
		r"\b(control|object|button|element|field|focus)\b"
		r"|\b(window class|class name|control id|window handle|process id|automation id|role|states|coordinates)\b"
		r".*\b(of|for)\b.*\b(this|the|focused|current|navigator|control|object|button|window)\b"
		r"|\bwhat does nvda know about\b"),
	("do_command", r"\b(read|say|speak|tell me|report)\b.*\b(title|time|date|battery|clipboard|status|focus)\b|say all|start reading"
		r"|\b(give|get|tell|check|what('s| is| are))\b.*\b(time|date|battery)\b|\bwhat (time|day|date) is it\b"
		r"|\bhow (much|full|low|empty) (is )?(the |my )?(battery|power|charge)\b|\bbattery (level|left|status|charge)\b"),
	("read_text", r"\bread\b.*\b(text|everything)\b|\bread (me )?(the |this |all of the )?(whole )?(window|screen)\b"),
	("web_page", r"\b(this|the|current) (web ?page|page|web ?site|site|article)\b|summari[sz]e"),
	("describe", r"what('s| is| does)? .*(look|show|screen|window|picture|image|photo)|describe|look at|colou?r|what do you see|on (the|my) screen"),
	("where_am_i", r"where am i|which (program|app|window|control)\b|what (program|app|window) (is|am)"),
	("nvda_question", r"what (is|are|does)|explain|tell me about|why"),
	# Any other question is looked up, not planned freely: a small model plans a question badly.
	("nvda_question", r"^(what|which|who|where|when|how)\b|^(can|could|does|do|is|are|should|will)\b.*\?\s*$"),
)
_CONNECTORS = re.compile(r"\b(and|then|also|after that|afterwards|plus)\b|[;]|,\s*(and|then)?", re.IGNORECASE)
MAX_PARTS = 4
# A part that speaks of "it" cannot be understood without the part before it.
_REFERS_BACK = re.compile(r"\b(it|its|they|them|their|that one|this one)\b", re.IGNORECASE)

_SPLIT_SCHEMA = {
	"type": "object",
	"properties": {
		"parts": {"type": "array", "minItems": 1, "maxItems": MAX_PARTS, "items": {"type": "string", "maxLength": 200}},
	},
	"required": ["parts"],
}
_SPLIT_SYSTEM = (
	"You split a request made to a screen reader assistant into the separate things the user wants done, in order.\n"
	"Rules: Keep the user's own words. Each part must be understandable alone, so repeat what a part refers to. "
	"If the request is one thing, give one part. Never add anything the user did not ask for. "
	"Do not split one action into smaller actions.\n"
	"Examples:\n"
	"Request: Turn off the typing echo and set punctuation to all\n"
	"parts: [\"Turn off the typing echo\", \"Set punctuation to all\"]\n"
	"Request: Make NVDA talk faster\n"
	"parts: [\"Make NVDA talk faster\"]\n"
	"Request: Look at this window and tell me what the buttons are\n"
	"parts: [\"Look at this window and tell me what the buttons are\"]\n"
	"Request: Click Options, then tell me what the new window shows\n"
	"parts: [\"Click Options\", \"Tell me what the new window shows\"]"
)


def hint(part):
	"""The recipe a part's words point to, or OTHER."""
	text = part.lower()
	for name, pattern in _HINTS:
		if re.search(pattern, text):
			return name
	return OTHER


def label(recipe):
	"""A recipe in a few words, for telling the user."""
	return RECIPES[recipe][0] if recipe in RECIPES else "work out the steps itself"


def recipeSteps(recipe, part, registry):
	"""The steps of a recipe for one part of the request. Code fills in what it can from the part's own words."""
	return [Step(registry.get(name).title, name, part, part, recipe=recipe) for name in RECIPES[recipe][2]]


def available(registry):
	"""The recipes whose tools all exist."""
	return {name: recipe for name, recipe in RECIPES.items() if registry.has(recipe[2])}


def split(llm, role, request, note=""):
	"""The separate things a request asks for, in order."""
	request = " ".join(request.split())
	if len(request) < 200 and not _CONNECTORS.search(request):
		return [request]  # clearly one thing: no model needed
	user = f"Request: {clip(request, 800)}"
	if note:
		user += f"\n{note}"
	try:
		found = llm.json(role, _SPLIT_SYSTEM, user, _SPLIT_SCHEMA, maxTokens=220)
	except LLMError:
		return [request]
	parts = [" ".join(str(p).split()) for p in found.get("parts") or [] if str(p).strip()]
	# A part that is not in the request at all was made up; then the request is kept whole.
	words = set(re.findall(r"[a-z0-9]{3,}", request.lower()))
	for part in parts:
		mine = set(re.findall(r"[a-z0-9]{3,}", part.lower()))
		if mine and len(mine & words) / len(mine) < 0.5:
			return [request]
	return settle(parts[:MAX_PARTS]) or [request]


def settle(parts):
	"""Make every part understandable alone, by plain rules, since small models split too eagerly.
	A fragment of one or two words ("search", "press it") belongs to the part before it. A part that speaks of
	"it" is given the part before it as its background."""
	settled, plain = [], []
	for part in parts:
		if settled and len(part.split()) < 3:
			settled[-1] = f"{settled[-1]} and {part[0].lower()}{part[1:]}"
			plain[-1] = settled[-1]
		elif settled and _REFERS_BACK.search(part):
			settled.append(f"{part} (this follows: {plain[-1]})")
			plain.append(part)
		else:
			settled.append(part)
			plain.append(part)
	return settled


def classify(llm, role, part, context, registry, note=""):
	"""The recipe that fits a part of the request, or OTHER."""
	recipes = available(registry)
	guess = hint(part)
	if guess not in recipes:
		guess = OTHER
	lines = "\n".join(f"- {name}: {text}" for name, (_label, text, _tools) in recipes.items())
	system = (
		"You choose how VisionClaw, an assistant inside the NVDA screen reader for a blind person, should handle "
		"one thing the user asked for. Choose the one that fits best:\n" + lines
		+ f"\n- {OTHER}: none of the above fits"
	)
	schema = {
		"type": "object",
		"properties": {"choice": {"type": "string", "enum": list(recipes) + [OTHER]}},
		"required": ["choice"],
	}
	user = f"The user asked: \"{clip(part, 400)}\"\n"
	if context:
		user += f"What is known: {clip(context, 400)}\n"
	if guess != OTHER:
		user += f"Its words suggest: {guess}.\n"
	if note:
		user += f"{note}\n"
	user += "Which one fits?"
	try:
		return fitted(llm.json(role, system, user, schema, maxTokens=40)["choice"], part, guess)
	except (LLMError, KeyError):
		return guess


# Recipes whose tool reads everything it needs from the user's own words. Plain code can tell that such a
# recipe cannot be meant: the words name no moment and no count, or no direction and no shape.
_NEEDS = {
	"timed_click": pointer.timingOf, "gesture": pointer.gestureOf, "touch": touch.touchOf, "pressure": touch.penOf,
	"turn_view": direct.turnOf}


def fitted(choice, part, guess):
	"""A model's choice of recipe, corrected where plain code can tell that it cannot be meant: then what the
	words point to is taken. Measured with Qwen3.5 9B and Qwen2.5 Coder 1.5B on 2026-11-18: "press and hold the
	New Game button for 2 seconds" was sent to the click at the right moment by both, twice."""
	needs = _NEEDS.get(choice)
	if needs is not None and needs(part) is None and guess != choice:
		return guess
	# A button of a game controller that is to be made to do something is a hotkey, and nothing to do now:
	# "Make the X button on my controller click the New Game button" must never click that button. With the
	# hotkey among their choices both real models chose it (2026-11-18); this holds when one does not.
	if guess == "make_hotkey" and choice != guess and gamepad.buttonOf(part) is not None:
		return guess
	return choice


def complexity(recipes):
	"""How demanding a request is, from the recipes its parts use."""
	if len(recipes) >= 3 or OTHER in recipes or "write_addon" in recipes:
		return policy.COMPLEX
	if len(recipes) == 2 or any(len(RECIPES[r][2]) > 1 for r in recipes if r in RECIPES):
		return policy.MODERATE
	return policy.SIMPLE


def quickTriage(request):
	"""A first sorting of a request from its words alone, before any model is asked."""
	parts = [p for p in _CONNECTORS.split(request) if p and len(p.strip()) > 8] or [request]
	recipes = [hint(p) for p in parts[:MAX_PARTS]]
	return {
		"kind": recipes[0],
		"complexity": complexity(recipes),
		"needs_vision": any(r in ("describe", "click", "make_hotkey", "read_text", "fix_access", "check_access", "touch", "pressure") for r in recipes),
		"needs_code": "write_addon" in recipes,
	}


# --- Plans ---

def _freeSchema(toolNames, maxSteps):
	return {
		"type": "object",
		"properties": {
			"steps": {
				"type": "array", "minItems": 1, "maxItems": maxSteps,
				"items": {
					"type": "object",
					"properties": {
						"tool": {"type": "string", "enum": toolNames},
						"detail": {"type": "string", "maxLength": 200},
					},
					"required": ["tool", "detail"],
				},
			},
		},
		"required": ["steps"],
	}


def _freeSystem(registry, maxSteps):
	return (
		"You plan the work of VisionClaw, an assistant inside the NVDA screen reader for a blind person.\n"
		"Break what the user asked for into small steps. Rules:\n"
		"- Each step uses exactly one tool and does one small thing.\n"
		"- Look before you act: find a setting before changing it, find a command before running it, "
		"list the items in a window before clicking one.\n"
		"- Do only what was asked. Use as few steps as possible.\n"
		"- Prefer the simplest tool that does the job. Write an add-on only when no other tool can do it.\n"
		f"- Use at most {maxSteps} steps. detail says exactly what to do in that step, in plain words.\n\n"
		"Tools:\n" + registry.listText()
	)


def freeSteps(llm, role, part, context, registry, params, note=""):
	"""A plan written by the model, for a part that fits no recipe. Repaired by plain rules."""
	names = [n for n in registry.names() if n != ANSWER]
	user = f"The user asked: \"{clip(part, 600)}\"\n"
	if context:
		user += f"What is known:\n{clip(context, 700)}\n"
	if note:
		user += f"{note}\n"
	user += "Write the steps."
	found = llm.json(
		role, _freeSystem(registry, params.maxSteps), user, _freeSchema(names, params.maxSteps),
		maxTokens=params.planTokens, reasoning=params.reasoning,
	)
	return normalize(found.get("steps") or [], registry, params.maxSteps, part)


def normalize(rawSteps, registry, maxSteps, part=""):
	"""Repair a model's plan by plain rules, so that it can be run. Returns a list of Step, without the answer."""
	steps = []
	for raw in rawSteps[:maxSteps]:
		tool = registry.get(raw.get("tool"))
		if tool is None or tool.name == ANSWER:
			continue
		detail = " ".join(str(raw.get("detail") or "").split())
		if steps and steps[-1].tool == tool.name and steps[-1].detail == detail:
			continue  # the same step twice in a row
		# A step that needs something found first gets that step put before it.
		if tool.before and registry.get(tool.before) and not any(s.tool == tool.before for s in steps):
			steps.append(Step(registry.get(tool.before).title, tool.before, detail, part))
		steps.append(Step(tool.title, tool.name, detail, part))
	return steps


def planText(steps):
	return "\n".join(f"{i}. {s.title} [{s.tool}]" for i, s in enumerate(steps, 1))


def detailText(steps):
	return "\n".join(f"{i}. {s.title} [{s.tool}] {s.detail}" for i, s in enumerate(steps, 1))


def answerStep():
	return Step("Telling you the result", ANSWER, "say what was done or found, in plain words")


def plan(llm, role, request, context, registry, params, note=""):
	"""Break a request into steps. note is extra guidance, like another model's objection to an earlier plan.
	Returns (steps, recipes): the steps end with the answer; recipes are the recipe names used, one per part."""
	steps, used = [], []
	for part in split(llm, role, request, note):
		recipe = classify(llm, role, part, context, registry, note)
		used.append(recipe)
		if recipe == OTHER:
			steps += freeSteps(llm, role, part, context, registry, params, note)
			continue
		steps += recipeSteps(recipe, part, registry)
	return steps + [answerStep()], used


def revise(llm, role, request, context, steps, objection, registry, params):
	"""Plan again, taking another model's objection into account."""
	note = (
		f"An earlier plan was:\n{detailText(steps)}\n"
		f"A reviewer found this problem with it: {clip(objection, 300)}\nChoose again so that the problem is fixed."
	)
	return plan(llm, role, request, context, registry, params, note)


_RETHINK_SCHEMA = {
	"type": "object",
	"properties": {"change": {"type": "boolean"}, "why": {"type": "string", "maxLength": 160}},
	"required": ["change", "why"],
}


def rethink(llm, role, request, results, remaining, registry, params):
	"""After a step that looked at something, in a plan the model wrote itself: should the rest change?
	Returns new steps (ending with the answer) or None."""
	system = (
		"You check a plan while it runs, for an assistant inside the NVDA screen reader. "
		"Say change=true only if what was just found shows that the remaining steps cannot work or would do "
		"the wrong thing. If they still fit, say change=false."
	)
	user = (
		f"Request: \"{clip(request, 500)}\"\nFound so far:\n{clip(results, 1200)}\n"
		f"Remaining steps:\n{detailText(remaining)}"
	)
	found = llm.json(role, system, user, _RETHINK_SCHEMA, maxTokens=80)
	if not found.get("change"):
		return None
	note = (
		f"Already done and found:\n{clip(results, 1200)}\nThe old remaining steps no longer fit because: "
		f"{found.get('why', '')}\nWrite only the steps that are still needed."
	)
	return freeSteps(llm, role, request, "", registry, params, note) + [answerStep()]
