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

from . import computer, controls, dates, debuglog, direct, gamepad, guide, memories, partners, places, pointer, policy, profiles, router, touch, understand
from . import docformat, focus, humancheck, images, paper, seats, shopping, versions, wizard
from .llm import LLMError, clip, uncut
from .task import Step
from .tools import ANSWER

# --- Recipes ---

OTHER = "other"
# Words that point to a setting of NVDA.
_SETTING_WORDS = (
	r"speed|rate\b|faster|slower|louder|quieter|volume|pitch|voice|punctuation|echo|braille|setting|turn (on|off)|"
	r"switch (on|off)|enable|disable|stop (saying|reading|announcing|speaking)|as i type|typed (words|characters|letters)|"
	r"capital letters|capitals\b|\b(speak|say|announce|read) (words|characters|letters|capitals|punctuation)\b"
	r"|\b(every|each) (letter|character|key|word)s? i (type|press|write)\b|\b(letters|characters|words|keys) (that )?i (type|press)\b"
	r"|\bwhat i type\b|\b(hear|say|speak|announce)\w*\b.{0,20}\bi type\b"
	r"|\b(i want|i'd like|i would like|let me|i need) to (hear|be told)\b|\b(stop|don'?t|do not) (keep )?(hearing|telling me|saying|announcing|reading out)\b")
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
	# The page as a whole, before its headings alone: how it is laid out and how to move on it, from what NVDA
	# itself keeps of the page (claw/pageview.py). Plain code, no model, nothing sent anywhere.
	"explore_page": (
		"explain how the web page is laid out and how to move on it",
		"give an overview of the web page: how it is laid out, its landmarks, where its main part begins, what is "
		"on it, and which NVDA keys move best on it",
		("explore_page",)),
	"page_outline": (
		"list the headings of the web page",
		"list the headings of the web page in order, with their levels",
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
	"form_trouble": (
		"find out what is stopping a form",
		"find out why a form on the web page will not send or submit: which fields are marked as wrong, which "
		"required fields are empty, what the page's error messages say; and move to the first of them",
		("form_trouble",)),
	"nvda_info": (
		"tell you what NVDA has and uses",
		"say which speech synthesizer, voice, braille display, braille table, driver or version NVDA has or "
		"uses and how they are set, or which add-ons are installed in NVDA",
		("nvda_info",)),
	# Which version of VisionClaw, NVDA, one add-on or the program in front is installed, read by plain code from the
	# words (claw/versions.py) and answered with that version alone.
	"version_info": (
		"tell you which version of something is installed",
		"say which version of VisionClaw itself, of NVDA, of one add-on installed in NVDA or of the program in front is "
		"installed here; only the version that was asked for",
		("version_info",)),
	"visionclaw_models": (
		"tell you which AI models VisionClaw uses",
		"say which AI model or models VisionClaw itself, the assistant, has installed, downloaded or stored and "
		"is using or running, how big they are, and where they run",
		("model_info",)),
	# Which model fits what the user wants to do (claw/advice.py): suggested, never switched.
	"model_advice": (
		"suggest which AI model to use for what you want to do",
		"suggest which of VisionClaw's own AI models, or which size or quant of them, fits what the user wants to do best: "
		"planning and carrying out tasks, describing pictures, writing add-ons, or speed; whether to switch to a smaller, "
		"larger or different model; only a suggestion, nothing is changed",
		("model_advice",)),
	"switch_driver": (
		"switch the speech synthesizer or braille display",
		"switch NVDA to a different speech synthesizer or a different braille display",
		("nvda_info", "switch_driver")),
	"fix_addon": (
		"debug and correct an add-on",
		"fix, debug or change an add-on VisionClaw wrote that fails or does not do what it should",
		("list_helpers", "repair_addon")),
	"undo_change": (
		"put back what VisionClaw changed",
		"undo a change VisionClaw made: put a setting back to what it was before, restore it, revert it, or put back "
		"a file it renamed, moved or made",
		("undo_change",)),
	"list_changes": (
		"say what VisionClaw has changed",
		"say which settings VisionClaw has changed",
		("list_changes",)),
	# NVDA settings that one program has for itself (claw/profiles.py). Changing one is change_setting: plain
	# code reads "only in this program" from the user's words.
	"program_settings": (
		"say which programs have NVDA settings of their own",
		"say which programs have NVDA settings of their own, kept in NVDA's configuration profiles, or whether the "
		"program in front has; not for changing a setting",
		("program_settings",)),
	"remove_program_settings": (
		"remove a program's own NVDA settings",
		"delete the NVDA settings one program has for itself, its configuration profile, so that NVDA behaves there "
		"as it does everywhere else",
		("remove_program_settings",)),
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
	# Questions about the control the user is on, read by plain code from the words (claw/focus.py) and answered from
	# NVDA's own facts: "what is the focused control", "what does this button do", "is this checkbox checked".
	"about_focus": (
		"tell you about the control you are on",
		"say what the focused control, the item the user is on, the navigator object or what is under the mouse is: "
		"its kind and name, what it does, whether it is checked, pressed or expanded, its value and its keys",
		("about_focus",)),
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
	# The computer itself, worked for the user (claw/computer.py): things opened by their name, the Recycle Bin,
	# the computer's volume, the windows that are open, the user's files, facts about the computer, its power.
	"open_thing": (
		"open a program, folder or settings page by its name",
		"open or start something on the computer by its name, wherever the user is: a program or app, a folder such "
		"as Documents or Downloads, a file, the Recycle Bin, Control Panel, or Windows Settings and its pages; not "
		"a button or item in the window in front, and not a website",
		("find_thing", "open_thing")),
	"windows_part": (
		"open the Start menu or another part of Windows",
		"open a part of Windows itself that is in no program's window: the Start menu or Start button, Windows "
		"search, the taskbar, the notification area or system tray, quick settings, the notification center, Task "
		"View, the Run dialog, the Quick Link menu, clipboard history or the emoji panel",
		("windows_part",)),
	# What is in a part of Windows itself, read from what Windows tells screen readers, word for word, by plain
	# code (claw/places.py): the icons of the system tray, the programs on the taskbar, the icons on the desktop;
	# the Start menu, quick settings and the notification center are opened with their key first and left open.
	"read_place": (
		"say what is in the system tray, on the taskbar or another part of Windows",
		"say what is in a part of Windows itself that is in no program's window, without opening a program: the icons "
		"in the system tray or notification area, also the hidden ones, the programs on the taskbar, the icons on the "
		"desktop, the notifications, quick settings or the Start menu; also how many there are, or whether one is there",
		("read_place",)),
	"recycle_bin": (
		"check the Recycle Bin",
		"say how full the Recycle Bin is, how much it holds, and whether it needs to be emptied",
		("recycle_bin",)),
	"empty_bin": (
		"empty the Recycle Bin",
		"empty the Recycle Bin now, which deletes what is in it for good",
		("empty_recycle_bin",)),
	"system_volume": (
		"change or say the computer's volume",
		"turn the volume of the computer itself, the system volume, up or down, set it, mute or unmute it, or say "
		"how loud it is; not the volume of NVDA's voice",
		("system_volume",)),
	"window": (
		"switch to, close or resize a window",
		"switch to another open window or program, or close, minimize, maximize or restore a window, or minimize "
		"every window",
		("list_windows", "window_action")),
	"files": (
		"look through your folders and files",
		"say what is in the user's Desktop, Documents, Downloads, Pictures, Music or Videos folder, which file is "
		"the newest or how many there are, or find a file of theirs by its name or kind",
		("find_files",)),
	"computer_info": (
		"tell you about the computer",
		"say a fact about the computer itself: free disk space, memory, processor, how long it has been on, whether "
		"it is connected to a network, which programs are running, its name",
		("computer_info",)),
	"set_control": (
		"set a named control of this program",
		"in the program or dialog in front, turn a named option, check box or switch on or off, or turn a named slider "
		"or value up or down or to a number; looks through the pages of the dialog for it; not a setting of NVDA",
		("set_control",)),
	"file_task": (
		"make, rename, move, copy or delete a file or folder",
		"make a new folder or text file, rename, move or copy a file or folder of the user's, or delete one by moving "
		"it to the Recycle Bin, in their Desktop, Documents, Downloads, Pictures, Music or Videos folders",
		("change_file",)),
	# A date chosen in a calendar that takes no keys (claw/dates.py). The date is read from the user's own words.
	"pick_date": (
		"choose a date in a calendar",
		"choose a date the user names in a calendar or date picker that is showing in the web page or window in "
		"front, by pressing the calendar's buttons for the month and the day",
		("pick_date",)),
	# Two add-ons VisionClaw works together with when they are running (claw/partners.py).
	"classic_speech": (
		"work the add-on ClassicSpeech for you",
		"with the add-on ClassicSpeech: change how much NVDA says about each control, the verbosity level Beginner, "
		"Intermediate or Advanced; list or switch its speech and sound schemes, or turn them on or off; open its voice "
		"profiles, schemes or settings window; or say how it is set",
		("classic_speech",)),
	"jaws_help": (
		"say what a JAWS keystroke or command is in NVDA",
		"with the add-on JAWS Migration Assistant: say what a JAWS keystroke or a JAWS command is in NVDA, what was "
		"brought over from JAWS, or which commands that add-on has; only when the user names JAWS",
		("jaws_help",)),
	# Working through a task when the usual path is not clear (claw/guide.py), in the program in front.
	"work_through": (
		"work through a task with you, step by step",
		"work through a task with the user in the program or web page in front when they are stuck, cannot find how "
		"to do something, or the usual way does not work: finds the next thing to press, says its key, presses it if "
		"they say yes, and goes on step by step",
		("work_through",)),
	"own_voice": (
		"give VisionClaw a voice of its own",
		"give VisionClaw a voice of its own, set in NVDA's Speech settings, so that it can be told from NVDA: customise "
		"it, turn it on or off, remove it, or say whether it has one; not NVDA's own voice",
		("own_voice",)),
	# Asking by voice (claw/voice.py): whether it is set up, getting the speech model, deleting it.
	"voice_info": (
		"say whether you can ask by voice",
		"say whether asking VisionClaw by voice, by speaking into the microphone, is set up, which speech model it "
		"listens with, and how to speak a request; not about NVDA's own voice",
		("voice_info",)),
	"get_voice": (
		"download the speech model for asking by voice",
		"download the speech model that lets the user ask VisionClaw by voice, or set asking by voice up",
		("get_voice",)),
	"remove_voice": (
		"delete the speech model for asking by voice",
		"delete the speech model for asking by voice from this computer",
		("remove_voice",)),
	# The user's own words, understood as other words from then on (claw/understand.py): taught, listed, forgotten.
	"teach_words": (
		"understand a word of yours",
		"teach VisionClaw a word or phrase of the user's own that is to mean something else from now on, say which "
		"words were taught, or forget one",
		("my_words",)),
	"power": (
		"lock, restart or shut down the computer",
		"lock the computer, put it to sleep, restart it, shut it down or sign out of Windows, or call off a restart "
		"or shutdown that is waiting",
		("power",)),
	# What a sighted helper was needed for, done on this computer (docs/PLAN-ten-scenarios.md). Each of these is
	# read from the user's own words by plain code (its function in _NEEDS), so it is offered only where the words
	# ask for it, and where they do no model is asked.
	"look_picture": (
		"look at one picture on the page or in the window",
		"look at one picture on the web page or in the window in front and answer a question about it: the latest "
		"picture in a chat, a screenshot or meme someone sent, a product's photo, the photos of a gallery; reads its "
		"text, says what it shows, measures its colours",
		("look_picture",)),
	"fill_blank": (
		"click a line or box on a form that is only a picture, and type on it",
		"on a scanned or flattened PDF, or another form that is only a picture: click the printed line or check box "
		"that belongs to a label, and type the user's text there",
		("fill_blank",)),
	"step_through": (
		"go through an installer page after page",
		"press one button, such as Next, on page after page of an installer or set-up window until something is "
		"reached, unchecking boxes that offer extra software on the way",
		("step_through",)),
	"format_document": (
		"format the document",
		"format the Microsoft Word document in front: a style such as APA or MLA, or its font, font size, line "
		"spacing, margins, alignment, first-line indent or hanging indent; in Google Docs, say which keys do it",
		("format_document",)),
	"check_layout": (
		"check the document's layout",
		"say how many pages the Word document in front has, whether it fits on one page, and whether text boxes, "
		"pictures or tables overlap or reach beyond the page",
		("check_layout",)),
	"human_check": (
		"help with a check that asks whether you are a person",
		"for a check on a web page that asks whether the user is a person (a captcha): say which kind it is and the "
		"ways through it that need no sight, press its check box, say what each square of a puzzle shows, and click "
		"the squares the user names",
		("human_check",)),
	"pick_option": (
		"choose an option of a product, or say which is chosen",
		"on a shop's page, choose a size, colour, storage or style option by its name or by its measured colour, or "
		"say which option is chosen now",
		("pick_option",)),
	"pick_seat": (
		"find and choose a seat on a seat map",
		"on a seat map, find the free seats that fit what the user wants (window, aisle, front, a row), say the best "
		"few, and click one after asking",
		("pick_seat",)),
}
# The step that checks what a request depends on ("if you see the Recycle Bin, open it") is no recipe: plain
# code puts it before the steps of what is to be done (`conditional`).
IF = "if"
# The patterns that match nearly any question, or anything that names something shown (see _WEAK).
_DESCRIBE_ANY = (
	r"what('s| is| does)? .*(look|show|screen|window|picture|image|photo)|describe|look at|colou?r|what do you see|on (the|my) screen")
_QUESTION_ANY = r"what (is|are|does)|explain|tell me about|why"
_QUESTION_START = r"^(what|which|who|where|when|how)\b|^(can|could|does|do|is|are|should|will)\b.*\?\s*$"
# A key or key combination of the program in front, as "alt f4", "control+s", "shift tab": pressed in the program.
# One with the NVDA key is a command of NVDA.
_KEYS = re.compile(
	r"\b(?:control|ctrl|alt|shift|windows|win)\s*(?:\+|plus|-|\s)\s*(?:(?:control|ctrl|alt|shift)\s*(?:\+|plus|-|\s)\s*)?"
	r"(?:f\d{1,2}|enter|return|escape|esc|tab|space|delete|backspace|home|end|up|down|left|right|page ?up|page ?down|[a-z0-9])\b",
	re.IGNORECASE)
# A name of NVDA's own code, as speech.speak or api.getFocusObject, and not a web address or a file.
_DOTTED = re.compile(r"\b(?!www\b)([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b", re.IGNORECASE)
_NOT_CODE = frozenset((
	"com", "org", "net", "edu", "gov", "io", "co", "uk", "de", "fr", "ca", "au", "txt", "pdf", "doc", "docx", "xls", "xlsx",
	"exe", "mp3", "mp4", "wav", "jpg", "jpeg", "png", "gif", "zip", "html", "htm", "md", "csv", "json", "ini", "lnk"))


def _codeName(part):
	"""Whether the words ask about a name of NVDA's own code: "what does speech.speak do"."""
	text = part.lower()
	return any(found.group(2) not in _NOT_CODE for found in _DOTTED.finditer(text)) and bool(
		re.search(r"\b(do|does|did|return|returns|mean|means|code|source|call|calls|function|method|work|works)\b", text))


# Every fact NVDA has about one object, or a technical one: object_facts, before a plain question about the control
# the user is on (about_focus).
_OBJECT_FACTS = (
	r"\b(properties|property|attributes?|facts|details|everything|all)\b.*\b(about|of|on)\b.*"
	r"\b(control|object|button|element|field|focus)\b"
	r"|\b(window class|class name|control id|window handle|process id|automation id|role|states|coordinates)\b"
	r".*\b(of|for)\b.*\b(this|the|focused|current|navigator|control|object|button|window)\b"
	r"|\bwhat does nvda know about\b")


# NVDA's focus mode and browse mode switched now, with NVDA's own command. A wish about how the switch sounds is a
# setting. Sure (decided): asked to choose, Qwen3.5 4B sent "go into focus mode please" to the settings.
_MODE_SWITCH = (
	r"^\W*(?:please\s+)?(?:can you\s+|could you\s+)?(?:switch|go|change|toggle|flip|put me|get me)\b.{0,20}"
	r"\b(?:focus|browse|forms?) mode\b(?!.*\b(?:say|saying|says|announc\w*|beep\w*|sound\w*|speak\w*|when|whenever|always)\b)")


# Words that point to a recipe. Checked in this order; the first that matches is the hint given to the model,
# and the choice when the model fails.
_HINTS = (
	# The jobs of docs/PLAN-ten-scenarios.md. Each has a function that reads what is asked from the user's own
	# words and gives None where they do not ask for it, so these rows name a job only where the words do.
	("step_through", lambda part: wizard.wish(part) is not None),
	("fill_blank", lambda part: paper.wish(part) is not None),
	("format_document", lambda part: docformat.wish(part) is not None),
	("check_layout", lambda part: docformat.layoutWish(part) is not None),
	("human_check", humancheck.about),
	("pick_seat", lambda part: seats.seatWish(part) is not None),
	("pick_option", lambda part: shopping.optionWish(part) is not None and not guide.asks(part)),
	("look_picture", lambda part: images.meant(part) is not None),
	# A question about the control the user is on: what it is, what it does, its state, its keys (claw/focus.py).
	# Asked on 2026-11-19 after "tell me about the focused control" set off the pattern for NVDA's commands below.
	("about_focus", lambda part: focus.wish(part) is not None and not re.search(_OBJECT_FACTS, part.lower())),
	# Which version of something is installed: the version alone (claw/versions.py). Asked on 2026-11-19 after "tell me
	# the version of visionclaw I have installed?" set off the pattern for what NVDA has, which reads out every add-on.
	("version_info", lambda part: versions.wish(part) is not None),
	# A field of a form that is marked only by a red border: what is stopping the form is found, and the reading
	# position is put there (pagetools measures the picture where the page tells NVDA nothing).
	("form_trouble", r"\b(fields?|box(es)?|forms?)\b.{0,60}\b(red (border|outline|box|line|frame)|(outlined|highlighted|marked|circled) in red)\b"
		r"|\bred (border|outline|frame)\b.{0,60}\b(fields?|box(es)?|forms?)\b"),
	# A file or folder of the user's that is made, renamed, moved, copied or deleted. First of all: the words must
	# speak of a file, a folder or a document, or write a name with its ending, and then "delete the file
	# notes.txt" is not about VisionClaw's notes on a program.
	("file_task", lambda part: computer.fileTask(part) is not None),
	# A word of the user's own, taught, listed or forgotten: "when I say shh, I mean stop talking". Before memories,
	# which "forget" would otherwise set off. Only where the words can hardly mean anything else (understand.wishOf).
	("teach_words", lambda part: understand.wishOf(part) is not None),
	# The settings a program has for itself, in NVDA's configuration profiles: taking them away, and which
	# programs have some. Changing one is change_setting, below, with "only in this program" in the words.
	# A date to be chosen in a calendar: the words name a calendar or a date field, and a date. Before everything
	# that the words set, click, next and open would otherwise start.
	("pick_date", lambda part: dates.wish(part) is not None),
	# ClassicSpeech and the JAWS Migration Assistant: only where the add-on is running, and the words are about it.
	("classic_speech", lambda part: partners.has(partners.CLASSIC) and partners.classicWish(part) is not None),
	("jaws_help", lambda part: partners.has(partners.JAWS) and partners.jawsWish(part) is not None),
	# VisionClaw's own voice. Before NVDA's own voice and pitch, which are settings.
	("own_voice", r"\b(visionclaw'?s?|your|its) own (voice|pitch)\b|\b(voice|pitch) of (your|its|visionclaw'?s) own\b"
		r"|\b(visionclaw'?s|your) (voice|pitch)\b.{0,40}\b(lower|different|deeper|same|normal|on|off)\b"
		r"|\b(customi[sz]e|change|choose|set up|pick|adjust|configure|select|remove|delete|reset)\b.{0,30}\b(visionclaw'?s?|your) (own )?voice\b"
		r"|\b(give|make)\b.{0,12}\b(visionclaw|you|yourself)\b.{0,20}\b(a |its |an? )?(own |different |another |new )?voice\b"
		r"|\ba (different|another|separate) voice for (you|visionclaw)\b"
		r"|\b(lower|deeper|different|own) (voice|pitch) (when|while|for) (you|visionclaw)\b"
		r"|\b(tell|telling|distinguish)\b.{0,30}\b(you|visionclaw)\b.{0,20}\b(apart|from nvda)\b"),
	# Being stuck, or asking to be led through something, in the program in front.
	("work_through", guide.asks),
	# Asking by voice. NVDA's own voice is a setting, and "which voices" is asked of NVDA: these need the
	# microphone, speaking to VisionClaw, dictating, or the speech model named.
	("remove_voice", r"\b(delete|remove|get rid of|erase|uninstall)\b.{0,30}\b(speech|asr|speech[- ]recognition|voice[- ]input) model\b"
		r"|\b(delete|remove|get rid of|erase)\b.{0,20}\bspeech recognition\b"),
	("get_voice", r"\b(download|get|install|fetch|set up)\b.{0,30}\b(speech|asr|speech[- ]recognition|voice[- ]input) model\b"
		r"|\bset up\b.{0,30}\b(asking|requests?|talking|speaking|dictat\w+)\b.{0,20}\b(by|with) (my )?voice\b"
		r"|\bset up (voice input|dictation|speech recognition)\b"),
	("voice_info", r"\b(ask|asking|talk|talking|speak|speaking|tell|say)\b.{0,40}\b(you|visionclaw|requests?|things)\b.{0,20}"
		r"\b(by|with|using) (my )?voice\b"
		r"|\b(can|could|may) i (just )?(speak|talk|dictate)\b.{0,30}\b(to you|to visionclaw|my requests?|instead of typing)\b"
		r"|\b(voice input|speech recognition|dictation|dictate)\b|\bspeech model\b|\bmicrophone\b"
		r"|\b(listen|hear)\b.{0,20}\b(to )?(me|my voice)\b"),
	("remove_program_settings", profiles.removes),
	("program_settings", profiles.asks),
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
	# "Remember me" on a form is the name of a box, not something to keep.
	("remember", r"\b(remember(?! me (box|check ?box|tick ?box|option|button|field|switch|toggle)\b)|memori[sz]e|"
		r"don'?t forget|do not forget|keep in mind|bear in mind|(make|take) a note that|note that)\b"
		# Only a statement and nothing more: "I'm new to NVDA. How do I ...?" is a question, and what it says
		# about the user is kept after it is answered (orchestrator._keep).
		r"|^\s*(please )?(call me|my name is|i am new to|i'm new to)\b[^?.!;]*[.!]?\s*$"),
	("library", r"\b(my|your|visionclaw'?s|the) library\b|\blibrary (folder|of documents)\b"),
	# The computer itself. Each of these is decided by plain code from words that can hardly mean anything else
	# (claw/computer.py), and none of them is meant by a question about how something is done. Locking and
	# shutting down first; emptying the Recycle Bin before opening it and before asking about it; the computer's
	# own volume before NVDA's, which is a setting.
	("power", lambda part: computer.powerOf(part) is not None),
	# A part of Windows itself, opened with its own key: the Start menu, the taskbar, the notification area. Before
	# the click, which "click the windows start button" would otherwise set off, and before the settings pages of
	# Windows, which "notifications" and "taskbar" also name. Only where the words are sure.
	# What is in a part of Windows itself: the icons of the system tray, the programs on the taskbar, the icons on
	# the desktop. Before the part of Windows that is opened, which "show me the icons in the system tray" would
	# otherwise set off, and before every way of looking at the window in front, which cannot show it. Measured in
	# the owner's NVDA on 2026-11-18: "tell me all objects that are currently in the system tray." was sent to the
	# description of the desktop's picture, which answered "I cannot see the system tray in this image".
	# A thing inside such a part, to be clicked: "click the volume icon in the system tray". Before the part of
	# Windows, which these words would otherwise open, and is listed from that part (nvdatools list_items).
	("click", lambda part: places.clicksIn(part) is not None),
	("read_place", places.asks),
	("windows_part", lambda part: computer.windowsPart(part) is not None),
	("empty_bin", computer.emptiesBin),
	("system_volume", lambda part: computer.volumeOf(part) is not None),
	("window", lambda part: computer.allWindows(part) and computer.aboutWindow(part)),
	("open_thing", computer.opensPlace),
	("recycle_bin", computer.asksAboutBin),
	("note_page", r"\b(add|put|save|keep)\b.*\b(page|site|article)\b.*\bnotes?\b"
		r"|\bnotes?\b.*\bfrom (this|the) (web ?page|page|web ?site|site|article)\b"),
	("app_notes", lambda part: bool(re.search(r"\b(which|what|list|show|open|read)\b.*\bnotes\b", part.lower()))
		and not computer.namesFile(part)),
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
	("visionclaw_log", r"\bvisionclaw('s)? (debug |error )?log\b|\b(debug|error) log\b|\byour (own )?(debug |error )?log( file)?\b"
		r"|\blog\b.*\b(of|from|for) visionclaw\b"),
	# Something inside NVDA's code, by its kind or by a dotted name like api.getFocusObject. Before the
	# add-on hints, which the word "code" would otherwise set off.
	("inside_nvda", _codeName),
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
		r"|\bkeep (on )?clicking\b|\b(click|press|tap|hit)\b.*\bat the right (moment|time)\b"
		r"|\b(click|tap|hit)\b.*\bevery (\d+ |few |other |half a )?(second|seconds|minute|minutes|beat)\b"),
	("fix_addon", r"\b(fix|repair|correct|debug)\b.*\badd-?on|\badd-?on\b.*\b(does(n't| not) work|is broken|stopped working|fails|wrong)\b"),
	("remove_made", r"\b(remove|delete|get rid of)\b.*\b(helper|hot ?key|add-?on)"),
	("list_made", r"\b(list|show|which|what)\b.*\b(helpers?|add-?ons?)\b.*\b(you|visionclaw)\b.*\b(made?|wrote|writes?|written|created?|built|build)\b"
		r"|\b(list|show|which|what)\b.*\b(you|visionclaw)\b.*\b(made|wrote|written|created|built)\b"),
	("write_addon", r"\b(write|make|create|build|code|program)\b.*\b(add-?on|plug-?in|code|script)\b|every time|whenever|automatically|when (a|an|the|i) .* (gets?|gains?|changes?|appears?|opens?)"),
	("make_hotkey", r"hot ?key|shortcut (key )?(for|to|that)|\bkey (for|to|that)\b"),
	("name_button", r"\b(name|label|call)\b.*\b(button|control|icon)|unlabel|no label|has no name"),
	("switch_driver", r"\b(switch|change|use|set)\b.*\b(synthesi[sz]ers?|synths?|braille (display|driver))\b"
		r"|\b(switch|change) to (espeak|one ?core|sapi|eloquence|no speech|no braille)"),
	("window", r"^\W*(please\s+)?(go|switch|get|take me) back to (?!(the |my )?(previous|last|page|top|start|beginning|main|home|"
		r"where|it|that|this|work|sleep|bed)\b)(the |my )?[a-z][\w.+-]*( [a-z][\w.+-]*)?\s*[.!]?\s*$"),
	("page_navigate", r"\b(go|navigate|move|take me)\s+(back|forward)\b|\b(previous|last|next) page\b|\b(reload|refresh)\b"),
	# What stops a form. Before everything that the words page, field, form, find and wrong would otherwise set
	# off. Narrow: a form or its fields, and that something is wrong, required or will not be sent.
	("form_trouble", r"\bforms?\b.{0,60}\b(won'?t|will not|doesn'?t|does not|can'?t|cannot|refus\w+|fail\w*|not)\b.{0,30}"
		r"\b(submit\w*|send\w*|sent|go through|going through|work\w*|accept\w*|sav\w+|continu\w+)\b"
		r"|\b(why|what)\b.{0,60}\b(can'?t|cannot|won'?t|will not|doesn'?t|does not)\b.{0,40}"
		r"\b(submit|send|sign up|register|check ?out)\b.{0,30}\b(forms?|page|order|it|this)\b"
		r"|\b(what|which|where|find|show|any)\b.{0,40}\b(errors?|mistakes?|wrong|missing|invalid|not valid)\b.{0,40}\b(forms?|fields?)\b"
		r"|\b(won'?t|will not|doesn'?t|does not|can'?t|cannot)\b.{0,30}\bforms?\b.{0,20}\b(submit|send|go through|work|save|continue)\b"
		r"|\b(which|what) (fields?|boxes) (are|is|do i|did i|must i|have i)\b.{0,30}\b(required|missing|empty|wrong|not valid|invalid|fill\w*|forg[eo]t\w*|miss(ed)?)\b"
		r"|\b(required|invalid|empty|missing) fields?\b|\bform (errors?|trouble|problems?)\b"
		r"|\b(errors?|mistakes?) (in|on|with) (this|the|my) form\b"),
	# The page as a whole: how it is laid out and how to move on it. Its headings alone stay with the outline.
	# "Layout" and "structure" alone mean the page only where nothing else is named: the keyboard layout is a
	# setting of NVDA, and a window is described from its picture.
	("explore_page", r"^(?!.*\b(keyboard|window|dialog|program|app|application|document|desktop|braille|screen|table|file|folder)\b)"
		r".*\b(laid out|layout|structure)\b"
		r"|\b(landmarks?|page explorer)\b"
		r"|\b(explore|overview of|tour of|walk me through|orient me|get around|move around|find my way|navigate)\b.{0,40}"
		r"\b(page|web ?page|site|web ?site)\b"
		r"|\b(best|quickest|fastest|easiest) way\b.{0,50}\b(page|web ?page|site|web ?site)\b"
		r"|\bwhat('s| is) on (this|the) (web ?page|page|web ?site|site)\b"
		r"|\bwhere (is|does) the main (content|part)\b"),
	("page_outline", r"\b(headings|outline)\b"),
	("go_to", r"\b(go|jump|move|take me|skip)\b.*\b(to|down to)\b.*\b(heading|section|part|link|field|box|form|main content|comments?)\b"),
	("search_web", r"\b(search|look up|google)\b.*\b(web|internet|online|for)\b"),
	("open_website", lambda part: bool(re.search(
		r"\b(open|go to|visit|load|browse to)\b.*(\w\.[a-z]{2,}\b|web ?site|web ?page|\burl\b)", part.lower()))
		and not (computer.namesFile(part) and not re.search(r"web ?site|web ?page|\burl\b|\bwww\.|https?:", part.lower()))),
	("fill_field", r"\b(type|enter|write|fill|put)\b.*\b(in|into)\b.*\b(field|box|form|search)\b"
		r"|\b(apply|use|enter|redeem|add)\b.{0,20}\b(promo(?:tion(?:al)?)?|coupon|discount|voucher|gift)\s+code\b"),
	# Which model to use or switch to: a suggestion (claw/advice.py). Before add-ons, NVDA's drivers and the models that are installed,
	# which "which model is best for writing add-ons" would otherwise set off.
	("model_advice", r"^(?!.*\b(picture|image|photo|screen|window|page|site|article|car|phone|printer|braille)\b.*\bmodel\b)(?=.*("
		r"\b(which|what)\b.{0,20}\b(models?|qwen|size|quant)\b.{0,40}\b(should|best|better|recommend\w*|suggest\w*|use for|for (coding|pictures|planning)|switch)\b"
		r"|\b(should|would|could) (i|we|you)\b.{0,30}\b(switch|change|use|try|go)\b.{0,30}\b(models?|qwen|smaller|larger|bigger|quant)\b"
		r"|\b(suggest|recommend|advise)\w*\b.{0,30}\b(models?|qwen|quant)\b"
		r"|\b(smaller|bigger|larger|faster|better|different|other) (ai )?(models?|qwen)\b"
		r"|\b(models?|qwen)\b.{0,30}\b(too slow|slow|faster|best for|better for)\b))"),
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
	("files", computer.aboutFiles),
	("computer_info", computer.aboutComputer),
	# NVDA's focus mode and browse mode are switched with NVDA's own command: "switch to focus mode" is no window
	# (tests/eval/requests5.json, 2026-11-19). A wish about how the switch sounds stays a setting.
	("do_command", _MODE_SWITCH),
	("window", computer.aboutWindow),
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
	# A button, link, tab or icon that is named and is to be clicked or found, whatever it is called: "click the
	# Settings button" is a click, though the word setting is in it. Finding one points the mouse at it.
	("click", r"\b(click|double[- ]click|press|push|activate|find and click)\b (on )?(the |a |an |my |that |this )?[\w' -]{1,40}?\b(button|link|tab|icon)\b"
		r"|^\s*(please )?(can you )?(find|locate|where is|where's|point (at|to))\b (me )?(the |a |an |my )?[\w' -]{1,40}?\b(button|link|tab|icon)\b"),
	("change_setting", _SETTING_WORDS),
	("do_command", r"\bnvda('?s)? (menu|speech viewer|python console|log viewer|elements list|braille viewer)\b"),
	("click", r"\bright[- ]click\b|\bdouble[- ]click\b|\bhover\b|\bpoint (at|to)\b"),
	("click", r"\b(click|press|push|activate|select|choose|start|open)\b.*\b(button|link|item|menu|tab|icon|game|option|tool|preset|"
		r"toggle|swatch|mode)|\bclick\b"),
	# A program, folder or file opened by its name. After everything above that the word open also starts, and
	# never for "it" or "this", which is the thing that has the focus.
	("open_thing", r"^\s*(please )?(can you |could you )?(open|launch|fire up)\b( up)? (?!(it|this|that|them|these|those|"
		r"the (selected|focused|current|highlighted|first|next|last))\b)"
		r"|^\s*(please )?(can you |could you )?(start|run)\b( up)? (?!\w+ing\b|(it|this|that|over|again|now|a new|the new)\b)"
		r"(the |my )?[\w.+'-]+( [\w.+'-]+){0,2}\s*[.!]?\s*$"),
	("press_keys", r"\bpress\b.*\b(key|enter|escape|tab|control|alt|shift|f\d+)\b"),
	("press_keys", lambda part: bool(_KEYS.search(part)) and not re.search(r"\bnvda\b", part, re.IGNORECASE)),
	# Typing is asked for as a thing to do: "type hello", "write ... into". "Every letter I type" is a setting.
	("type_text", r"^\W*(please\s+)?(can you\s+|could you\s+)?(type|enter)\b|\b(type|write)\b.*\b(in|into)\b"
		r"|^\W*(please\s+)?(can you\s+|could you\s+)?write (?!an? (add-?on|script|skill|note)\b)"),
	# The facts NVDA holds about one object. Kept narrow: "report the navigator object" is an NVDA command.
	("object_facts", _OBJECT_FACTS),
	("do_command", r"\b(read|say|speak|tell me|report)\b.*\b(title|time|date|battery|clipboard|status|focus(ed)?)\b|say all|start reading"
		r"|\b(give|get|tell|check|what('s| is| are))\b.*\b(time|date|battery)\b|\bwhat (time|day|date) is it\b"
		r"|\bwhat('s| is) (on|in) (the |my )?clipboard\b"
		r"|\bhow (much|full|low|empty) (is )?(the |my )?(battery|power|charge)\b|\bbattery (level|left|status|charge)\b"),
	# What a game or a drawn window shows in a grid or a panel is looked at, and its text read with it.
	("describe", r"\b(read|tell me|say|what (?:is|are)|list)\b.{0,160}\b(inventory|stats|skill points?|equipped|scoreboard|leaderboard|"
		r"health bar|hud)\b"),
	("read_text", r"\bread\b.*\b(text|everything)\b|\bread (me )?(the |this |all of the )?(whole )?(window|screen)\b"
		r"|\bwhat (does|do) (the |this |that )?(text|message|dialog|window|screen|label|error)\b.{0,30}\bsay\b"),
	("describe", r"^\W*(please\s+)?(can you\s+|could you\s+)?describe\b"),
	("web_page", r"\b(this|the|current) (web ?page|page|web ?site|site|article)\b|summari[sz]e"),
	("describe", _DESCRIBE_ANY),
	("where_am_i", r"where am i|which (program|app|window|control)\b|what (program|app|window|control|field|button|element) (is|am|are)\b"),
	("nvda_question", _QUESTION_ANY),
	# Any other question is looked up, not planned freely: a small model plans a question badly.
	("nvda_question", _QUESTION_START),
)
# The patterns that only say that the words ask something or name something shown. Pointing elsewhere than a
# model's choice, they are too weak to question it (`challenger`).
_WEAK = frozenset((_DESCRIBE_ANY, _QUESTION_ANY, _QUESTION_START))
# An NVDA setting changed for one program only stays with change_setting: "turn off the typing echo only in this
# program" is no control inside the program.
_FOR_ONE_PROGRAM = (OTHER, "change_setting", "nvda_question", "explain_keys", "work_control", "drag", "scroll")
_CONNECTORS = re.compile(r"\b(and|then|also|after that|afterwards|plus)\b|[;]|,\s*(and|then)?", re.IGNORECASE)
MAX_PARTS = 8
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


# After one of these, a part that only asks something asks it of the web page that is then open: "go to
# example.com and tell me how many messages I have".
_ON_THE_WEB = ("open_website", "search_web", "page_navigate", "go_to", "fill_field", "web_page")
# After one of these the user is inside something of the program in front, and "turn the volume up a bit" means
# the control there, not NVDA's own setting.
_INSIDE = ("click", "set_control")
_ONLY_ASKS = re.compile(
	r"^\s*(please\s+)?(tell me|say|read|what|which|who|how many|how much|is there|are there|do i have|does it|"
	r"summari[sz]e|count|list|check)\b", re.IGNORECASE)


# A question about how something is done or which key does it, at the start of a sentence. It is answered with the
# keys, and nothing is done: "what's the shortcut to get to the address bar" is no hotkey to be made, and "how can I
# jump between headings" is no list of headings. Measured on the held-out set (tests/eval) on 2026-11-18: these
# words had sent such questions to the job a word in them named.
_HOW = re.compile(
	rf"(?:^|[.!?]\s+){computer._POLITE}(?:how (?:do|can|would|should|could|might) (?:i|we|you|one)\b|how to\b"
	r"|what(?:'s| is| are)? (?:the )?(?:keyboard )?(?:key|keys|shortcut|shortcuts|hot ?key|command) (?:to|for)\b"
	r"|which (?:key|keys|command|shortcut)\b)", re.IGNORECASE)
_WHY = re.compile(rf"(?:^|[.!?]\s+){computer._POLITE}why (?:does|do|is|are|did|can't|won't|doesn't|isn't|is it)\b", re.IGNORECASE)
# What a how-question may still be: a question of its own kind, or being led through the task.
_ANSWERS = (
	"explain_keys", "nvda_question", "work_through", "coach", "addon_question", "jaws_help", "voice_info", "own_voice",
	"program_settings", "web_page", "explore_page", "form_trouble", "classic_speech", "controller_info", "mouse_way", "human_check")


_TURNED_THING = re.compile(r"\b(knobs?|dials?|faders?|sliders?|rotary)\b", re.IGNORECASE)
# Words that say the program, window or page in front is meant.
_IN_FRONT = re.compile(
	r"\b(in|inside|within|on|of|from)\s+(this|the)\s+(?:[\w+-]+\s+){0,2}(plug-?in|program|app|application|window|launcher|game|"
	r"dialog|installer|panel|vst)\b", re.IGNORECASE)
_OPENS_INSIDE = re.compile(
	r"^\s*(?:please\s+)?(?:open|go to|go into|show|bring up|switch to|enter)\s+(?:the|its|my|this)\s+[\w' +&-]{2,50}?"
	r"(?:\s+(?:in|inside|within|on|of|from)\s+(?:this|the)\s+[\w' +-]{2,40})?\s*[.!]?\s*$", re.IGNORECASE)
_CHOOSES_INSIDE = re.compile(r"^\s*(?:please\s+)?(?:select|choose|pick|activate)\s+(?:the|a|an|my|this)\s+\S", re.IGNORECASE)


def hint(part, before=None):
	"""The recipe a part's words point to, or OTHER. before: the recipe of the part before it, or None."""
	text = part.lower()
	found = OTHER
	for name, pattern in _HINTS:
		if pattern(part) if callable(pattern) else re.search(pattern, text):
			found = name
			break
	if found not in _ANSWERS and _HOW.search(computer.own(part)):
		return "explain_keys"
	# "Why does NVDA say clickable all the time" asks for a reason; it is answered, and nothing is done.
	if found not in _ANSWERS and _WHY.search(computer.own(part)):
		return "nvda_question"
	if before in _ON_THE_WEB and found in (OTHER, "nvda_question") and _ONLY_ASKS.match(computer.own(part)):
		return "web_page"
	# A setting of NVDA for one program only: the words narrow it down ("only in", "when I'm in"), or name
	# something that is NVDA's own to set. Then it is no control of the program.
	if found in _FOR_ONE_PROGRAM and profiles.scopeOf(part) is not None:
		rest = profiles.without(computer.own(part))
		if re.search(_SETTING_WORDS, rest.lower()) and (profiles.restricts(part) or _NVDAS_OWN.search(rest)):
			return "change_setting"
	# A knob, dial, fader or slider that is to show a number is set to it; taking hold of it for the arrow keys
	# is for turning it by ear. "Turn the Mix knob down to 35 percent."
	if found in (OTHER, "work_control", "drag", "change_setting", "scroll", "click") and _TURNED_THING.search(text):
		wished = controls.wish(part)
		if (wished is not None and wished["what"] == controls.SET and not profiles.everywhere(part)
				and not _NVDAS_OWN.search(part)):
			return "set_control"
	# In the program in front, right after a click there or where the words say "in this launcher": "open the
	# Settings menu" and "select the Warm Vocal preset" are clicks on things of that program. They are not NVDA's
	# settings and not a program opened by its name; a place of Windows that is named stays what it is.
	if (before in _INSIDE or _IN_FRONT.search(text)) and not computer.opensPlace(part):
		own = computer.own(part)
		if found in ("change_setting", "open_thing", OTHER) and _OPENS_INSIDE.match(own):
			return "click"
		if found == OTHER and _CHOOSES_INSIDE.match(own):
			return "click"
	# A named control of the program in front: where the words say "in this program", or right after a click or
	# another control there. What can hardly mean anything else, as the computer's own volume, stays what it is.
	if (found in (OTHER, "change_setting", "click", "drag", "work_control", "nvda_question", "scroll")
			and (controls.inApp(part) or before in _INSIDE) and controls.wish(part) is not None
			and not profiles.everywhere(part)):
		return "set_control"
	return found


def strongly(part, before=None):
	"""The recipes the words point to by more than a pattern for any question: what a model's choice may stand on."""
	text = part.lower()
	found = {name for name, pattern in _HINTS if pattern not in _WEAK
		and (pattern(part) if callable(pattern) else re.search(pattern, text))}
	first = hint(part, before)
	if first != OTHER and not any(name == first and pattern in _WEAK and re.search(pattern, text) for name, pattern in _HINTS):
		found.add(first)
	found.discard(OTHER)
	return found


def challenger(part, choice, before=None):
	"""The recipe the user's own words point to strongly enough to question a model's choice, or None. Measured on
	the held-out set (tests/eval) on 2026-11-18: of 9 questions to the user, the model had chosen rightly in 6 and the
	first pattern was wrong. So the model's choice stands where the words point to it too, or where only a pattern
	for any question points elsewhere; the user is asked only where the words point clearly elsewhere."""
	guess = hint(part, before)
	if guess in (OTHER, choice):
		return None
	strong = strongly(part, before)
	if choice in strong or guess not in strong:
		return None
	return guess


def onlyLooks(recipe, registry):
	"""Whether every step of a recipe only finds something out and changes nothing. Between two such ways the user is
	not asked to choose: one is tried, and the other where the first does not answer (consensus, orchestrator)."""
	if recipe not in RECIPES:
		return False
	try:
		tools = [registry.get(name) for name in RECIPES[recipe][2]]
	except KeyError:
		return False
	return bool(tools) and all(tool.looks and not tool.changes for tool in tools)


# Ways that answer from a picture, which a model reads; every other way that looks answers from what NVDA, the program
# or Windows says, which is certain.
_PICTURE_WAYS = ("describe", "look_picture")


def firstWay(chosen, words):
	"""Of two ways that only look, (the one tried first, the one tried when it does not answer): the model's choice
	first, since where the user was asked the model had been right more often (2026-11-18, 6 of 9); but a picture comes
	after a way that reads NVDA's or Windows' own facts, which are certain where a picture is a model's reading."""
	if chosen in _PICTURE_WAYS and words not in _PICTURE_WAYS:
		return words, chosen
	return chosen, words


def label(recipe):
	"""A recipe in a few words, for telling the user."""
	return RECIPES[recipe][0] if recipe in RECIPES else "work out the steps itself"


def recipeSteps(recipe, part, registry):
	"""The steps of a recipe for one part of the request. Code fills in what it can from the part's own words."""
	return [Step(registry.get(name).title, name, part, part, recipe=recipe) for name in RECIPES[recipe][2]]


def available(registry):
	"""The recipes whose tools all exist."""
	return {name: recipe for name, recipe in RECIPES.items() if registry.has(recipe[2])}


# Where one thing to do ends and the next begins, by plain rules. A small model splits a long request badly,
# and a request of five things is five chances to. So what plain code can tell is not asked of a model: an end
# of a sentence, "then", a comma and "and" before a word that begins a thing to do.
_SENTENCE = re.compile(r"(?<=[.!?;])\s+")
_THEN = re.compile(r"\s*[,;]?\s*\b(?:and then|then|after that|afterwards|finally|lastly)\b,?\s*", re.IGNORECASE)
_COMMA = re.compile(r"\s*,\s*(?:and\s+)?")
_AND_ACT = re.compile(rf"\s+and\s+(?=(?:please\s+)?{computer.ACT}\b)", re.IGNORECASE)
_LEADING = re.compile(
	r"^\s*(?:(?:first(?: of all)?|firstly|secondly|next|finally|lastly|then|and|also|now|ok|okay)\b[, ]+)+", re.IGNORECASE)
# "In this dialog, turn on ...": where something is, said before what to do. It belongs to what follows it.
_PLACE_LEAD = re.compile(r"^\s*(?:in|on|inside|within|at|under|from) (?:this|the|that|my|its) [\w' -]{1,50}$", re.IGNORECASE)
_PLACE_START = re.compile(r"^\s*(?:in|on|inside|within|at|under|from) (?:this|the|that|my|its) [\w' -]{1,50}?,\s*", re.IGNORECASE)
# Verbs that only point at a thing: "adjust the volume and turn it up" is one thing to do, with the volume.
_POINTS = re.compile(r"^\s*(?:please\s+)?(adjust|find|locate|select|pick|choose|take|change|look for|go to)\s+", re.IGNORECASE)
# Verbs that are done to a thing that is named right after them: "open notepad", "adjust the volume". Only
# after one of these is "it" in the next part taken to be that thing. "Do a deep query of this control and tell
# me how a sighted person works it" names no thing this way, and is left to the model.
_VERB_LEAD = re.compile(
	r"^\s*(?:please\s+)?(?:open|launch|start|run|find|locate|adjust|select|pick|choose|click|press|close|minimi[sz]e|"
	r"maximi[sz]e|restore|switch to|go to|go into|bring up|show|take|change|turn on|turn off|mute|unmute|play|pause|stop|"
	r"copy|rename|install|focus|expand|collapse)\s+(?:on\s+)?", re.IGNORECASE)
_IT = re.compile(r"\b(it|them)\b", re.IGNORECASE)
# "Find the settings button" before more things to do: it is found to be used.
_FIND_IT = re.compile(r"^(\s*(?:please\s+)?)find\b(?=.*\b(button|link|tab|icon|menu|option|item)\b)", re.IGNORECASE)
_SUBORDINATE = re.compile(
	r"^\s*(if|when|whenever|while|after|before|once|as|since|because|unless|although|in|on|at|for|with)\b", re.IGNORECASE)
_QUESTION = re.compile(r"^\s*(what|which|who|where|when|how|is|are|do|does|can|could|will|should)\b", re.IGNORECASE)
_REPORTS = re.compile(r"^\s*(?:please\s+)?(tell|say|read|describe|report|list|summari[sz]e|count)\b", re.IGNORECASE)
# What only looks: a report joined to it by "and" is about what was looked at, and stays with it.
_LOOKS = ("read_place", "describe", "read_text", "where_am_i", "about_focus", "check_access", "page_outline", "explore_page", "form_trouble", "web_page", "nvda_question", "explain_keys",
	"look_picture", "check_layout")
# Recipes whose words are the user's own text, which may hold commas and "and" of its own.
_WHOLE = ("learn_app", "write_addon", "add_skill", "add_fix", "work_through", "teach_words", "step_through", "format_document", "pick_seat",
	"human_check", "look_picture",
	# One question about the control the user is on, in several clauses: "what's the focused control and what does it
	# do" was split by the model and "what does it do" looked up alone (tests/eval/requests5.json, 2026-11-19).
	# claw/focus.py takes no request that also asks for something to be done.
	"about_focus")
# Recipes that are kept whole where plain rules find nothing to split: their tools read the whole of what was said.
# Where plain rules do split ("click the Medium size swatch, select the dark blue colour option"), each part stands.
_WHOLE_UNSPLIT = ("fill_blank", "pick_option", "check_layout", "form_trouble")
# What is wrong, then one short wish about it that says "it" or "that": "..., make it stop", "..., fix that".
_COMPLAINT = re.compile(
	r"^(?!\s*(?:please\s+)?(?:can you\s+)?(?:open|close|click|press|type|turn|set|go|switch|start|find|read|tell|show)\b)"
	r"[^,;.]{8,},\s*(?:please\s+)?(?:make|get|have|let)\s+(?:it|that|this|them|nvda)\s+(?:stop|quieter|slower|faster|be quiet)\b[^,;.]*[.!]?\s*$"
	r"|^[^,;.]{8,},\s*(?:please\s+)?(?:stop|fix|change|undo|turn off)\s+(?:it|that|this)\b[^,;.]*[.!]?\s*$", re.IGNORECASE)
_FREE_TEXT = (
	"write_addon", "add_skill", "remember", "fix_addon", "add_fix", "make_hotkey", "type_text", "fill_field", "search_web",
	"learn_app", "name_button")


# "Check and see", "go and look", "try and find": one thing said with two words, not two things to do.
_ONE_THING = re.compile(
	r"\b(check|look|go|try|go ahead|have a look|take a look)\s+and\s+(?=(?:see|check|look|find out|tell me)\b)", re.IGNORECASE)
_JOINED = " \u2060and\u2060 "
# What is said in quotes is one thing, whatever commas and "and" it holds: a label printed on a form, a name.
_IN_QUOTES = re.compile(
	r"\"[^\"]{1,80}\"|\u201c[^\u201d]{1,80}\u201d|(?<![\w])'[^']{1,80}'(?![\w])|\u2018[^\u2019]{1,80}\u2019")
_COMMA_MARK = "\u2063"
# A name of two words joined by "and" before the kind of thing it names: the Fill and Sign tool.
_NAMED_AND = re.compile(
	r"\b([A-Z][\w-]*)\s+and\s+(?=[A-Z][\w-]*(?:\s+[\w-]+){0,2}?\s+(?:tool|button|menu|tab|option|dialog|window|panel|page|box|mode|"
	r"icon|link|command|item|feature|section|pane)\b)")
_TYPES_ON_IT = re.compile(
	r"^\s*(?:then\s+)?(?:(?:type|write|enter|put|print|fill in)\b|(?:click|press|tap)\s+(?:on\s+)?(?:there|it|that)\b)", re.IGNORECASE)


def _isCondition(text):
	return computer.condition(_LEADING.sub("", text)) is not None


def plainSplit(request):
	"""The separate things a request asks for, where plain rules can tell them apart for certain; else None,
	and the request is split as before. Every thing after the first must begin with a word that begins a
	thing to do, or be a question in a sentence of its own, and must not say "it": a part that needs the part
	before it to be understood is left to the model. A thing that depends on something ("if you see the
	Recycle Bin, open it") is kept whole."""
	pieces = []
	# What is in quotes, and a name such as Fill and Sign, is never split: its commas and its "and" are put aside.
	request = _IN_QUOTES.sub(lambda hit: hit.group(0).replace(",", _COMMA_MARK).replace(" and ", _JOINED), " ".join(request.split()))
	request = _NAMED_AND.sub(lambda hit: hit.group(1) + _JOINED, request)
	# The "and" of "check and see" is put aside, so that nothing is split there, and put back afterwards.
	for sentence in _SENTENCE.split(_ONE_THING.sub(lambda hit: hit.group(1) + _JOINED, " ".join(request.split()))):
		sentence = sentence.strip().rstrip(".!;").strip()
		if not sentence:
			continue
		if _isCondition(sentence):
			pieces.append((_LEADING.sub("", sentence), "sentence"))
			continue
		how = "sentence"
		for chunk in _THEN.split(sentence):
			chunk = _LEADING.sub("", chunk or "").strip()
			if not chunk:
				continue
			fragments, lead = [], ""
			for fragment in _COMMA.split(chunk):
				# A place said first belongs to what follows it.
				if _PLACE_LEAD.match(fragment or "") and not computer.STARTS_ACT.match(fragment):
					lead = fragment.strip() + ", "
					continue
				fragments.append(lead + (fragment or ""))
				lead = ""
			for fragment in fragments:
				for last in _AND_ACT.split(fragment or ""):
					last = _LEADING.sub("", last).strip().rstrip(".!;").strip()
					if last:
						pieces.append((last, how))
						how = "and"
				how = "comma"
			how = "then"
	if len(pieces) < 2:
		return None
	pieces = [(text.replace(_JOINED, " and ").replace(_COMMA_MARK, ","), how) for text, how in pieces]
	# What is typed belongs to the line it is typed on: "click the line next to Name and type my name" is one thing.
	joined = []
	for text, how in pieces:
		if joined and how == "and" and _TYPES_ON_IT.match(text) and paper.wish(joined[-1][0]) is not None:
			joined[-1] = (f"{joined[-1][0]} and {text}", joined[-1][1])
		else:
			joined.append((text, how))
	pieces = _resolved(joined)
	if len(pieces) < 2:
		return None
	for index, (text, how) in enumerate(pieces):
		if _isCondition(text):
			continue
		if len(text.split()) < 2:
			return None
		# Where something is, said first, is no part of what begins the thing to do.
		start = _PLACE_START.sub("", text)
		if index == 0:
			if not computer.STARTS_ACT.match(start) or (_SUBORDINATE.match(text) and start == text):
				return None
			continue
		if _REFERS_BACK.search(text):
			return None
		if not computer.STARTS_ACT.match(start) and not (how == "sentence" and _QUESTION.match(text)):
			return None
		before = hint(pieces[index - 1][0])
		if how != "sentence" and before in _FREE_TEXT:
			return None
		if how == "and" and _REPORTS.match(text) and before in _LOOKS:
			return None
	# Something that is found before more is done is found to be used: its button is clicked.
	texts = [text if index == len(pieces) - 1 else _FIND_IT.sub(r"\1find and click", text, count=1)
		for index, (text, _how) in enumerate(pieces)]
	return [(text[:1].upper() + text[1:]).replace(_JOINED, " and ") for text in texts]


def _resolved(pieces):
	"""Pieces in which "it" is said as the thing the piece before names, where plain code can tell which thing:
	"open notepad and maximize it" becomes two things to do with notepad, and "adjust the volume and turn it up"
	one, because adjusting only points at the volume. A piece whose "it" cannot be told is left as it is, and
	then the whole request is left to the model."""
	found = []
	for text, how in pieces:
		if found and how != "sentence" and _IT.search(text) and not _isCondition(text) and not _isCondition(found[-1][0]):
			before = found[-1][0]
			thing = _VERB_LEAD.sub("", _PLACE_START.sub("", before), count=1).strip()
			if thing and thing != before and len(thing.split()) <= 6 and not _IT.search(thing):
				said = _IT.sub(thing, text, count=1)
				if _POINTS.match(before):
					found[-1] = (said, found[-1][1])
				else:
					found.append((said, how))
				continue
		found.append((text, how))
	return found


def conditional(part, registry):
	"""For a part that depends on something plain code can find out: (the step that checks it, the things to
	do if it holds, in the user's words); None for any other part. The step carries `test`, which says from the
	step's result whether the condition holds, and `said`, which makes the sentence the user is told."""
	found = computer.condition(_LEADING.sub("", computer.own(part)))
	if found is None:
		return None
	kind, what, state = found["kind"], found["what"], found["state"]
	if kind == computer.SEEN:
		tool, title = "check_seen", f"Checking whether {what} is on the screen"
		test, said = computer.says, (lambda result, holds: result)
	elif kind == computer.BIN_IS:
		tool, title = "recycle_bin", "Checking the Recycle Bin"
		wanted = {"empty": ("empty",), "some": ("some", "worth"), "worth": ("worth",)}[state]
		test, said = (lambda result: computer.binState(result) in wanted), (lambda result, holds: result)
	else:
		tool, title = "list_windows", f"Checking whether {what} is open"
		test = lambda result: computer.listed(what, result) == state
		said = lambda result, holds: (
			f"A window of {what} is open." if computer.listed(what, result) else f"No window of {what} is open.")
	if registry.get(tool) is None:
		return None
	step = Step(title, tool, found["asked"], found["asked"], recipe=IF)
	step.test, step.said = test, said
	then = found["then"]
	if computer.onlyTells(then):
		return step, []
	return step, plainSplit(then) or [then[:1].upper() + then[1:]]


def split(llm, role, request, note=""):
	"""The separate things a request asks for, in order."""
	request = " ".join(request.split())
	# "Make NVDA speak faster, only in this program": the words that say for which program are no thing to do of
	# their own. Split off after a comma, they were taken for a request to describe the screen, and the setting
	# was changed in every program (measured with Qwen3.5 9B on 2026-11-18). So they are put aside before the
	# request is split, and given back to every part that changes a setting of NVDA.
	# "I'm stuck, I want to attach a file to this email" is one thing: being stuck is no thing to do of its own.
	# Split at its comma by a model, "I'm stuck" was taken for a question and the rest was planned freely, and a
	# button was clicked that nobody asked for (measured with Qwen3.5 9B on 2026-11-18).
	if guide.asks(request):
		return [request]
	# One job told in several clauses: "find out about this game online and take notes" is learning about it, and
	# split at "and take" each half went to learning (measured on the held-out set on 2026-11-18).
	if hint(request) in _WHOLE:
		return [request]
	# "NVDA keeps saying every word I type, make it stop": what is wrong, then what to do about it. One request;
	# split, each half changed the setting (measured on the second held-out set on 2026-11-18).
	if _COMPLAINT.match(request):
		return [request]
	scope = profiles.scopeOf(request)
	if scope is not None:
		rest = profiles.without(request)
		parts = split(llm, role, rest, note) if rest and rest != request else []
		if len(parts) == 1 and hint(parts[0]) == "change_setting":
			return [request]  # one thing: it stays in the user's own words
		if any(hint(part) == "change_setting" for part in parts):
			words = scope["words"]
			words = words if words.startswith("I ") or words.startswith("I'") else words[:1].lower() + words[1:]
			return [f"{part.rstrip(' .!?,;')} {words}" if hint(part) == "change_setting" else part for part in parts]
	plain = plainSplit(request)
	if plain:
		return plain[:MAX_PARTS]
	if _isCondition(request):
		return [request]  # one thing that depends on something: kept whole
	# What plain rules cannot split, and what the job's own function reads from the words as a whole: one thing,
	# kept in the user's own words. Measured with Qwen3.5 9B on 2026-11-19 (tests/eval/requests-ten.json): split by
	# the model, "this pdf is just a scan, click the line beside Full Name and type Jordan Lee" typed the name as a
	# job of its own, and "one of the boxes on this form has a red border, take me to it" went looking for "it".
	if hint(request) in _WHOLE_UNSPLIT:
		return [request]
	if len(request) < 200 and not _CONNECTORS.search(_ONE_THING.sub(r"\1 ", request)):
		return [request]  # clearly one thing: no model needed
	user = f"Request: {uncut(request)}"
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


def hinted(part, before=None):
	"""Every recipe that some pattern finds in a part's words, not only the first. The router offers them all."""
	text = part.lower()
	found = {name for name, pattern in _HINTS if (pattern(part) if callable(pattern) else re.search(pattern, text))}
	found.add(hint(part, before))
	found.discard(OTHER)
	return found


def decided(part, registry, before=None):
	"""The recipe for a part whose words can hardly mean anything else, or None: then no model is asked."""
	guess = hint(part, before)
	if guess in available(registry) and (guess in _SURE or (guess == "open_thing" and computer.opensPlace(part))):
		return guess
	if guess == "do_command" and guess in available(registry) and re.search(_MODE_SWITCH, part.lower()):
		return guess
	# Right after a web page was opened, a part that only asks something asks it of that page. Measured with
	# Qwen3.5 9B on 2026-11-18: asked to choose for "tell me how many emails I have" after "go to gmail.com", it
	# chose to describe the screen, twice, and the user had to decide.
	if guess == "web_page" and guess in available(registry) and before in _ON_THE_WEB and hint(part) in (OTHER, "nvda_question"):
		return guess
	# A thing inside a part of Windows, to be clicked: the words name it and the place, and no window has it.
	if guess == "click" and guess in available(registry) and places.clicksIn(part) is not None:
		return guess
	# Right after a click in a program, "open the Settings menu" is a click there too (see hint).
	if (guess == "click" and guess in available(registry) and before in _INSIDE and hint(part) != "click"
			and _OPENS_INSIDE.match(computer.own(part))):
		return guess
	# A named control of the program in front, where the words say "this program" or right after a click or
	# another control there, and nothing in the words is NVDA's own. Measured the same day: after "find and
	# click the settings button", the model sent "turn the volume up a bit" to NVDA's settings, twice.
	if guess == "set_control" and guess in available(registry) and not _NVDAS_OWN.search(part):
		return guess
	return None


# Words for what is NVDA's own to set. With one of them, a model chooses and the user is asked when in doubt.
_NVDAS_OWN = re.compile(
	r"\b(nvda|screen ?reader|speech|speak\w*|voice|synth\w*|punctuation|echo|typing|typed|braille|pitch|rate|speed|"
	r"say\w*|announc\w*|read\w*|beep\w*|add-?ons?)\b", re.IGNORECASE)


def offered(part, registry, facts=None, before=None, also=()):
	"""The recipes a model is given to choose from for a part: those that fit where the user is and what they
	said (claw/router.py). also: recipes that are offered whatever the router says: the jobs of the skills that
	fit, and what worked before for a request like it (claw/planning.py)."""
	recipes = available(registry)
	return router.route(part, list(recipes), facts, before, hinted(part, before) | set(also), needsFor(part, before))


def needsFor(part, before=None):
	"""What the router asks of the recipes whose tools read everything from the user's words. A named control
	of the program in front is offered where the words say so, or right after a click there: "turn off the
	typing echo" alone is NVDA's own setting, and is not offered as a control of the program."""
	inside = controls.inApp(part) or before in _INSIDE
	return dict(_NEEDS, set_control=lambda part: controls.wish(part) if inside else None)


def _choose(llm, role, part, context, recipes, names, guess, note, brief=""):
	lines = "\n".join(f"- {name}: {recipes[name][1]}" for name in names)
	system = (
		"You choose how VisionClaw, an assistant inside the NVDA screen reader for a blind person, should handle "
		"one thing the user asked for. Choose the one that fits best:\n" + lines
		+ f"\n- {OTHER}: none of the above fits"
	)
	schema = {
		"type": "object",
		"properties": {"choice": {"type": "string", "enum": list(names) + [OTHER]}},
		"required": ["choice"],
	}
	user = f"The user asked: \"{uncut(part)}\"\n"
	if context:
		user += f"What is known: {clip(context, 400)}\n"
	if brief:
		user += f"{clip(brief, 600)}\n"
	if guess != OTHER:
		user += f"Its words suggest: {guess}.\n"
	if note:
		user += f"{note}\n"
	user += "Which one fits?"
	return llm.json(role, system, user, schema, maxTokens=40)["choice"]


def classify(llm, role, part, context, registry, note="", before=None, facts=None, brief="", also=()):
	"""The recipe that fits a part of the request, or OTHER. before: the recipe of the part before it.
	facts: where the user is, for the router. The model is given only what fits there and what the words name;
	when it finds nothing among that, it is given everything, once. brief: what plain code found that helps
	(claw/planning.py); also: recipes offered whatever the router says."""
	recipes = available(registry)
	guess = hint(part, before)
	if guess not in recipes:
		guess = OTHER
	sure = decided(part, registry, before)
	if sure is not None:
		return sure
	names = offered(part, registry, facts, before, also)
	if guess != OTHER and guess not in names:
		names.append(guess)
	try:
		choice = _choose(llm, role, part, context, recipes, names, guess, note, brief)
		if choice == OTHER and len(names) < len(recipes):
			debuglog.log("router", f"Nothing among {len(names)} offered kinds fit {part!r}; all {len(recipes)} are offered once.")
			choice = _choose(llm, role, part, context, recipes, list(recipes), guess, note, brief)
		return fitted(choice, part, guess)
	except (LLMError, KeyError):
		return guess


# Recipes whose tool reads everything it needs from the user's own words. Plain code can tell that such a
# recipe cannot be meant: the words name no moment and no count, or no direction and no shape.
_NEEDS = {
	"timed_click": pointer.timingOf, "gesture": pointer.gestureOf, "touch": touch.touchOf, "pressure": touch.penOf,
	"turn_view": direct.turnOf, "power": computer.powerOf, "system_volume": computer.volumeOf,
	"windows_part": lambda part: computer.windowsPart(part, loose=True),
	"read_place": places.wish,
	"set_control": controls.wish,
	"file_task": computer.fileTask,
	"empty_bin": lambda part: computer.emptiesBin(part) or None,
	"remove_program_settings": lambda part: profiles.removes(part) or None,
	"pick_date": dates.wish,
	"work_through": lambda part: guide.asks(part) or None,
	"classic_speech": lambda part: partners.classicWish(part) if partners.has(partners.CLASSIC) else None,
	"jaws_help": lambda part: partners.jawsWish(part) if partners.has(partners.JAWS) else None,
	"program_settings": lambda part: profiles.asks(part) or None,
	"recycle_bin": lambda part: computer.asksAboutBin(part) or None,
	# Remembering is only meant where the words ask for it or say something lasting about the user. A real
	# model sent "see if it needs to be emptied or not" there, and the request was kept as a memory.
	"remember": lambda part: (memories.asksToRemember(part) or memories.lasting(part)) or None,
	"teach_words": understand.wishOf,
	# The jobs of docs/PLAN-ten-scenarios.md: each is offered only where its own function finds it in the words.
	"step_through": wizard.wish, "fill_blank": paper.wish, "format_document": docformat.wish,
	"check_layout": docformat.layoutWish, "human_check": lambda part: humancheck.about(part) or None, "pick_seat": seats.seatWish,
	"pick_option": lambda part: None if guide.asks(part) else shopping.optionWish(part), "look_picture": images.meant,
	"about_focus": focus.wish, "version_info": versions.wish}
# Recipes the words point to that can hardly mean anything else: locking and shutting down, the Recycle Bin, the
# computer's own volume. Where the words point to one of them, it is taken, whatever a model chose. Each of
# their tools asks the user before it changes anything.
_SURE = ("power", "windows_part", "read_place", "empty_bin", "recycle_bin", "system_volume", "file_task", "pick_date", "work_through",
	"teach_words", "step_through", "fill_blank", "format_document", "check_layout", "human_check", "pick_seat", "pick_option",
	"look_picture", "about_focus", "version_info")


# Words that only ask something, at the start: a question, or "tell me". Asked of nothing on the screen and fitting no
# job, they are looked up (fitted).
_ASKED = re.compile(
	rf"^\W*{computer._POLITE}(?:tell me|what|which|who|whose|when|where|why|how|"
	r"(?:is|are|was|were|do|does|did)\s+(?:i|you|it|this|that|these|those|there|the|my|we|they|he|she|any|a|an)\b)\b",
	re.IGNORECASE)


def fitted(choice, part, guess):
	"""A model's choice of recipe, corrected where plain code can tell that it cannot be meant: then what the
	words point to is taken. Measured with Qwen3.5 9B and Qwen2.5 Coder 1.5B on 2026-11-18: "press and hold the
	New Game button for 2 seconds" was sent to the click at the right moment by both, twice."""
	needs = _NEEDS.get(choice)
	if needs is not None and needs(part) is None and guess != choice:
		return guess
	# A question the model finds no job for is looked up, not planned freely: a small model plans a question badly, and
	# a free plan for "what's 15 times 12" clicked a search result and ended in a question to the user (Qwen3.5 4B,
	# tests/eval/requests6.json, 2026-11-19). Looking up changes nothing.
	if choice == OTHER and (guess == "nvda_question" or _ASKED.match(computer.own(part))):
		return "nvda_question"
	# The model found nothing that fits, and the words point to a job whose tool reads everything it needs from
	# them, and finds it there: "turn around in the game". Measured on the held-out set on 2026-11-18.
	if choice == OTHER and guess in _NEEDS and _NEEDS[guess](part) is not None:
		return guess
	# A button of a game controller that is to be made to do something is a hotkey, and nothing to do now:
	# "Make the X button on my controller click the New Game button" must never click that button. With the
	# hotkey among their choices both real models chose it (2026-11-18); this holds when one does not.
	if guess == "make_hotkey" and choice != guess and gamepad.buttonOf(part) is not None:
		return guess
	if choice != guess and (guess in _SURE or (guess == "open_thing" and computer.opensPlace(part))):
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
		"needs_vision": any(r in ("describe", "click", "make_hotkey", "read_text", "fix_access", "check_access", "touch", "pressure",
			"look_picture", "human_check") for r in recipes),
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


def _freeSystem(registry, maxSteps, names=None):
	listed = registry.listText() if names is None else "\n".join(
		f"- {name}: {registry.get(name).description}" for name in names)
	return (
		"You plan the work of VisionClaw, an assistant inside the NVDA screen reader for a blind person.\n"
		"Break what the user asked for into small steps. Rules:\n"
		"- Each step uses exactly one tool and does one small thing.\n"
		"- Look before you act: find a setting before changing it, find a command before running it, "
		"list the items in a window before clicking one.\n"
		"- Do only what was asked. Use as few steps as possible.\n"
		"- Prefer the simplest tool that does the job. Write an add-on only when no other tool can do it.\n"
		f"- Use at most {maxSteps} steps. detail says exactly what to do in that step, in plain words.\n\n"
		"Tools:\n" + listed
	)


def freeSteps(llm, role, part, context, registry, params, note="", facts=None, before=None):
	"""A plan written by the model, for a part that fits no recipe. Repaired by plain rules. With facts, the
	model is given only the tools that fit where the user is and what they said (claw/router.py)."""
	names = [n for n in registry.names() if n != ANSWER]
	if facts is not None:
		names = router.tools(names, available(registry), set(offered(part, registry, facts, before)))
	user = f"The user asked: \"{uncut(part)}\"\n"
	if context:
		user += f"What is known:\n{clip(context, 700)}\n"
	if note:
		user += f"{note}\n"
	user += "Write the steps."
	found = llm.json(
		role, _freeSystem(registry, params.maxSteps, names), user, _freeSchema(names, params.maxSteps),
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
		f"Request: \"{uncut(request)}\"\nFound so far:\n{clip(results, 1200)}\n"
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
