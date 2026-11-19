# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""VisionClaw's help files explain every feature, and say what is new in the version they come with.

The owner said on 2026-11-18: "all help files should always reflect all visionclaw features, explain them,
including what is new in the very latest addon and how to use the new features." The help files are the page
NVDA opens from the Add-on Store (addon/doc/en/readme.html) and the README. This test fails when:
- the part on what is new is not the one tools/write_help.py writes from the manifest's changelog;
- a key of VisionClaw, of pointer mode, of a held dial or of the overlay is not in the help;
- a setting in VisionClaw's settings panel is not in the help, by its own label;
- a kind of request (planner.RECIPES) has no words in HELP below, or those words are not in both files.
A new recipe needs a line in HELP: words a user would say for it, written into both files with what it does.
"""
import html
import os
import re
import sys

import harness  # noqa: F401
from visionClaw.claw import dragcontrol, planner, pointer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLUGIN = os.path.join(ROOT, "addon", "globalPlugins", "visionClaw")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import write_help  # noqa: E402

# For every kind of request, words that must be in both help files.
HELP = {
	"change_setting": "speak a little faster",
	"do_command": "what time is it",
	"explain_keys": "how do i read the title of this window",
	"nvda_question": "what does nvda+t do",
	"describe": "what is on my screen",
	"read_text": "read the text in this window",
	"click": "press the play button in this window",
	"press_keys": "press control+s",
	"type_text": "type garden gloves into the search box",
	"make_hotkey": "give this program a hotkey that clicks send",
	"name_button": "call this button play",
	"write_addon": "write an add-on that beeps when a link gets the focus",
	"list_made": "list what you have made",
	"remove_made": "remove the add-on",
	"open_website": "open bbc.co.uk",
	"search_web": "search the web for the weather in boston",
	"web_page": "what does this page say about refunds",
	"explore_page": "explore this page",
	"page_outline": "the headings of the page",
	"go_to": "read on from there",
	"page_navigate": "go back, forward or reload",
	"fill_field": "type into a field",
	"form_trouble": "why won't this form submit",
	"nvda_info": "which speech synthesizer am i using",
	"visionclaw_models": "what model is installed",
	"switch_driver": "switch my speech synthesizer to espeak",
	"fix_addon": "fix the add-on",
	"undo_change": "undo that",
	"teach_words": "when i say shh, i mean stop talking",
	"list_changes": "what did you change",
	"program_settings": "only in this program",
	"remove_program_settings": "remove the settings for this program",
	"save_addon": "as a file",
	"check_access": "do a deep inspection of this website",
	"fix_access": "fix all of it",
	"add_fix": "give this site keys to move between posts",
	"addon_question": "what does the clock add-on do",
	"coach": "give me a hint about browse mode",
	"drag": "drag the file onto the trash",
	"work_control": "let the arrow keys work the volume dial",
	"update_visionclaw": "check for a new version of visionclaw",
	"update_guides": "get the latest nvda developer guides",
	"guides_info": "which developer guides do i have",
	"remove_guides": "delete the developer guides",
	"downloads_info": "what can you download for me",
	"update_training": "get the free nvda training material",
	"training_info": "which training material do i have",
	"remove_training": "delete the training material",
	"scroll": "scroll down a page",
	"gesture": "draw a circle",
	"timed_click": "click the go button as soon as it changes",
	"touch": "pinch the map",
	"pressure": "press hard on the drum pad",
	"turn_view": "look up a little",
	"mouse_way": "this game has its own mouse pointer",
	"controller_info": "is a controller connected",
	"controller_mode": "controller mode",
	"keyboard_mouse": "make this control keyboard navigable",
	"where_am_i": "what can i do here",
	"about_focus": "what does this button do",
	"object_facts": "tell me everything nvda knows about this control",
	"inside_nvda": "what does the function api.getfocusobject do",
	"audit_nvda": "do a full audit of nvda",
	"add_skill": "make a new skill",
	"list_skills": "which skills do you have",
	"show_skill": "what does the email skill say",
	"manage_skill": "turn off the game skill",
	"learn_app": "learn about this program",
	"note_page": "add this page to the notes on",
	"app_notes": "which notes do you have",
	"forget_notes": "delete the notes on this program",
	"visionclaw_log": "open the visionclaw log",
	"remember": "remember that i use a braille display with 40 cells",
	"memories": "what do you remember",
	"forget_memory": "forget that",
	"library": "what is in my library",
	"open_thing": "open notepad",
	"windows_part": "open the start menu",
	"read_place": "what is in my system tray",
	"model_advice": "which model should i use for describing pictures",
	"recycle_bin": "check and see if my recycle bin needs to be emptied",
	"empty_bin": "empty the recycle bin",
	"system_volume": "turn down my system volume",
	"window": "switch to firefox",
	"files": "what is in my downloads folder",
	"computer_info": "how much disk space do i have left",
	"set_control": "in this dialog, turn on my nvidia gpu for this program",
	"file_task": "create a folder called taxes in my documents",
	"pick_date": "pick 14 march 2027 in this calendar",
	"classic_speech": "set classicspeech to advanced",
	"jaws_help": "what is jaws's insert+f7 in nvda",
	"work_through": "i'm stuck, i want to attach a file to this email",
	"own_voice": "customise visionclaw's voice",
	"voice_info": "can i ask you by voice",
	"get_voice": "download the speech model",
	"remove_voice": "delete the speech model",
	"power": "shut down the computer",
	# The ten things that used to need sighted help (docs/PLAN-ten-scenarios.md).
	"look_picture": "what does the latest picture in this chat say",
	"fill_blank": "click the line next to full name and type my name",
	"step_through": "click next until the installation starts",
	"format_document": "format this document in apa style",
	"check_layout": "does my resume fit on one page",
	"human_check": "click the verify you are human box",
	"pick_option": "select the dark blue colour option",
	"pick_seat": "find a free window seat near the front",
}


def plain(text):
	"""A help file as plain lower-case words: no tags, no Markdown marks, one space between words."""
	text = re.sub(r"<[^>]+>", " ", text)
	text = html.unescape(text)
	text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
	text = re.sub(r"\*\*|\*|`", "", text)
	return re.sub(r"\s+", " ", text).lower()


def read(path):
	with open(path, encoding="utf-8") as f:
		return f.read()


def section(text, heading):
	"""The part of readme.html under the heading of level 2 that begins with heading, as plain words with their
	case kept."""
	found = re.search(r"<h2>" + re.escape(heading) + r".*?</h2>(.*?)(?=<h2>|</body>)", text, re.S)
	assert found, f"readme.html has no part {heading!r}"
	return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", found.group(1))))


def settingLabels():
	"""Every label of VisionClaw's settings panel, as the user hears it, without its accelerator and what is in
	brackets."""
	source = read(os.path.join(PLUGIN, "settings.py"))
	labels = re.findall(r"(?:addLabeledControl|checkbox)\(\s*(?:#[^\n]*\n\s*)*_\(\s*\"([^\"]+)\"", source)
	labels += re.findall(r"label=_\(\s*\"([^\"]+)\"", source)
	result = []
	for label in labels:
		label = label.replace("&", "")
		label = re.split(r"\s*\(|\.\.\.|\. ", label)[0].strip().rstrip(":").strip()
		if label:
			result.append(label)
	return result


htmlText = read(write_help.HTML)
readmeText = read(write_help.README)
files = {"readme.html": plain(htmlText), "README.md": plain(readmeText)}

# What is new: the part written from the changelog, for the version in the manifest.
problems = write_help.stale()
assert not problems, " ".join(problems) + ". Run python tools/write_help.py."
current = write_help.version()
newest = write_help.sections()[0]
assert newest[0] == current, f"the changelog's newest part is for {newest[0]}, the manifest says {current}"
assert newest[1], f"the changelog says nothing new for {current}"
for name, text in files.items():
	assert f"what is new in {current}" in text, name
	assert f"visionclaw {current}" in text, name
	for kind, words in newest[1]:
		assert plain(words)[:80] in text, (name, words[:80])
# The part is written fresh from a made-up changelog, so a new version is put in by the tool alone.
made = 'version = 9.1.0\nchangelog = """X\nNew in 9.1.0:\n* A & B "here".\nStated plainly: C.\nNew in 9.0.0:\n* D.\nIn 8.0.0:\n* E.\n"""'
block = write_help.htmlNews(made)
assert "VisionClaw 9.1.0" in block and "What is new in 9.1.0" in block and "What was new in 9.0.0" in block, block
assert "<li>A &amp; B \"here\".</li>" in block and "<p>Stated plainly: C.</p>" in block and "8.0.0" not in block, block
block = write_help.markdownNews(made)
assert "## What is new in 9.1.0" in block and "- A & B \"here\"." in block and "8.0.0" not in block, block
assert write_help.replaced("a" + write_help.NEWS_START + "old" + write_help.NEWS_END + "b", "new") == "anewb"
assert write_help.replaced("no markers", "new") is None
# Nothing in the help may still say an old version is the one it is for.
for name, text in files.items():
	for old in re.findall(r"this is version (\d+(?:\.\d+)+)|status: version (\d+(?:\.\d+)+)", text):
		number = old[0] or old[1]
		assert number == current, f"{name} says it is version {number}"

# Every key VisionClaw gives NVDA.
keys = sorted(set(re.findall(r'gesture="kb:NVDA\+alt\+(\w)"', read(os.path.join(PLUGIN, "__init__.py")))))
assert len(keys) >= 17, keys
for key in keys:
	for name, text in files.items():
		assert f"nvda+alt+{key}" in text, (name, key)
# The read-only box "How to use VisionClaw" in the models window names every key too.
usage = re.search(r"\nUSAGE = _\((.*?)\n\)", read(os.path.join(PLUGIN, "dialogs.py")), re.S)
assert usage, "USAGE was not found in dialogs.py"
usage = usage.group(1).lower()
for key in keys:
	assert f"nvda+alt+{key}" in usage, f"the models window's How to use VisionClaw does not name NVDA+Alt+{key.upper()}"
# The commands without a key are named there, with where a key is given.
assert "input gestures" in usage and "own voice" in usage and "remembers" in usage, usage


def letters(table, extra=()):
	"""The letter keys of a mode, upper case, as the help names them."""
	found = set()
	for gesture in table:
		if gesture in extra:
			continue
		key = gesture.split(":", 1)[1].split("+")[-1]
		if len(key) == 1 and key.isalpha():
			found.add(key.upper())
	return found


def named(part, letter):
	return re.search(r"(?<![\w+])" + letter + r"(?![\w'])", part)


pointerPart = section(htmlText, "Working the mouse from the keyboard")
for letter in letters(pointer.KEYS, pointer.EXTRA_KEYS):
	assert named(pointerPart, letter), f"pointer mode's key {letter} is not in the help"
dialPart = section(htmlText, "Dials, knobs and sliders")
for letter in letters(dragcontrol.KEYS, dragcontrol.EXTRA_KEYS):
	assert named(dialPart, letter), f"the key {letter} of a held dial is not in the help"
overlayKeys = re.findall(r'"(kb:[^"]+)":\s*"\w+"', read(os.path.join(PLUGIN, "overlay.py")))
assert "kb:g" in overlayKeys and "kb:h" in overlayKeys, overlayKeys
overlayPart = section(htmlText, "Programs and games NVDA cannot read")
for letter in letters(overlayKeys):
	assert named(overlayPart, letter), f"the overlay's key {letter} is not in the help"

# Every setting, by its own label.
labels = settingLabels()
assert len(labels) >= 30, labels
for label in labels:
	for name, text in files.items():
		assert plain(label) in text, (name, label)

# Every kind of request.
missing = sorted(set(planner.RECIPES) - set(HELP))
assert not missing, f"these kinds of request have no words in HELP: {missing}"
assert not set(HELP) - set(planner.RECIPES), sorted(set(HELP) - set(planner.RECIPES))
for recipe, words in HELP.items():
	for name, text in files.items():
		assert words in text, f"{name} does not explain {recipe}: no {words!r}"

print("OK")
