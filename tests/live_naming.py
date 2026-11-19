# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""A real vision model names controls without a name from their picture, three ways: as VisionClaw asked before
2026-11-19 (a free answer, no instructions), with the instructions and the short form (working.NAME_SYSTEM,
NAME_SCHEMA), and with those and where the control is (working.aroundText: the program, the window's title, the named
controls just before and after it). The pictures are drawn by the test: sixteen icon buttons as toolbars have them,
and an empty one that shows nothing. The icons, the places and the names that count as right were written on
2026-11-19 before anything was run on them. A name that copies a control around it is counted as wrong.

  python -u tests/live_naming.py MODELS [visionId] [--second]
"""
import sys

from PIL import Image, ImageDraw

import harness
from live_orchestrator import OneModelCatalog
from visionClaw.claw import audit, prompts, runtime, working
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import VISION
from visionClaw.claw.llm import LLM
from visionClaw.engine import prepareImage

OLD_PROMPT = (
	"This picture shows one button that has no name. What does it do or show? Answer with only one to three words that "
	"would be a good name for it. If you cannot tell, answer: unknown.")
INK = (40, 40, 48)


def canvas():
	image = Image.new("RGB", (64, 64), (243, 243, 246))
	draw = ImageDraw.Draw(image)
	draw.rounded_rectangle((2, 2, 61, 61), radius=8, outline=(190, 190, 200), width=1)
	return image, draw


def play(d):
	d.polygon(((22, 16), (22, 48), (48, 32)), fill=INK)


def pause(d):
	d.rectangle((20, 16, 28, 48), fill=INK)
	d.rectangle((36, 16, 44, 48), fill=INK)


def gear(d):
	for x0, y0, x1, y1 in ((28, 8, 36, 18), (28, 46, 36, 56), (8, 28, 18, 36), (46, 28, 56, 36)):
		d.rectangle((x0, y0, x1, y1), fill=INK)
	for points in (((14, 18), (18, 14), (24, 20), (20, 24)), ((50, 18), (46, 14), (40, 20), (44, 24)),
			((14, 46), (18, 50), (24, 44), (20, 40)), ((50, 46), (46, 50), (40, 44), (44, 40))):
		d.polygon(points, fill=INK)
	d.ellipse((16, 16, 48, 48), fill=INK)
	d.ellipse((26, 26, 38, 38), fill=(243, 243, 246))


def magnifier(d):
	d.ellipse((12, 12, 38, 38), outline=INK, width=5)
	d.line((35, 35, 52, 52), fill=INK, width=7)


def trash(d):
	d.rectangle((14, 14, 50, 18), fill=INK)
	d.rectangle((26, 9, 38, 14), outline=INK, width=2)
	d.polygon(((17, 20), (47, 20), (44, 54), (20, 54)), outline=INK, width=3)
	for x in (26, 32, 38):
		d.line((x, 26, x, 48), fill=INK, width=2)


def floppy(d):
	d.polygon(((12, 10), (46, 10), (54, 18), (54, 54), (12, 54)), fill=INK)
	d.rectangle((20, 10, 42, 24), fill=(243, 243, 246))
	d.rectangle((34, 13, 39, 21), fill=INK)
	d.rectangle((18, 34, 48, 54), fill=(230, 230, 236))


def plus(d):
	d.rectangle((28, 12, 36, 52), fill=INK)
	d.rectangle((12, 28, 52, 36), fill=INK)


def close(d):
	d.line((16, 16, 48, 48), fill=INK, width=7)
	d.line((48, 16, 16, 48), fill=INK, width=7)


def pencil(d):
	d.polygon(((40, 10), (54, 24), (24, 54), (10, 54), (10, 40)), fill=INK)
	d.line((36, 16, 48, 28), fill=(243, 243, 246), width=2)


def speaker(d):
	d.rectangle((10, 24, 20, 40), fill=INK)
	d.polygon(((20, 24), (32, 12), (32, 52), (20, 40)), fill=INK)
	d.arc((30, 22, 44, 42), -60, 60, fill=INK, width=3)
	d.arc((30, 14, 54, 50), -60, 60, fill=INK, width=3)


def hamburger(d):
	for y in (18, 30, 42):
		d.rectangle((12, y, 52, y + 5), fill=INK)


def heart(d):
	d.ellipse((12, 14, 34, 36), fill=INK)
	d.ellipse((30, 14, 52, 36), fill=INK)
	d.polygon(((13, 30), (51, 30), (32, 52)), fill=INK)


def bell(d):
	d.pieslice((14, 10, 50, 50), 180, 360, fill=INK)
	d.rectangle((14, 30, 50, 42), fill=INK)
	d.rectangle((10, 42, 54, 46), fill=INK)
	d.ellipse((28, 46, 36, 54), fill=INK)


def house(d):
	d.polygon(((32, 10), (8, 32), (56, 32)), fill=INK)
	d.rectangle((16, 32, 48, 54), fill=INK)
	d.rectangle((28, 40, 36, 54), fill=(243, 243, 246))


def download(d):
	d.rectangle((28, 8, 36, 34), fill=INK)
	d.polygon(((18, 30), (46, 30), (32, 44)), fill=INK)
	d.rectangle((12, 48, 52, 53), fill=INK)


def lock(d):
	d.arc((20, 8, 44, 34), 180, 360, fill=INK, width=5)
	d.line((22, 20, 22, 30), fill=INK, width=5)
	d.line((42, 20, 42, 30), fill=INK, width=5)
	d.rounded_rectangle((14, 28, 50, 56), radius=4, fill=INK)
	d.ellipse((29, 36, 35, 42), fill=(243, 243, 246))


def empty(d):
	pass


# (the icon, how it is drawn, the program or website, is it a website, the window's title, before it, after it,
# the words of which one makes a right name; none for the empty one, which must be named nothing)
PICTURES = (
	("play", play, "vlc", False, "song.mp3 - VLC media player", [("button", "Previous")], [("button", "Next"), ("button", "Stop")],
		("play", "start", "resume")),
	("pause", pause, "vlc", False, "song.mp3 - VLC media player", [("button", "Previous")], [("button", "Stop")], ("pause",)),
	("gear", gear, "Spotify", False, "Spotify Premium", [("button", "Home"), ("button", "Search")], [("button", "Profile")],
		("settings", "setting", "preferences", "options", "configure", "configuration", "setup")),
	("magnifier", magnifier, "OUTLOOK", False, "Inbox - Outlook", [("button", "New mail")], [("button", "Settings")],
		("search", "find", "magnify", "zoom")),
	("trash", trash, "OUTLOOK", False, "Inbox - Outlook", [("button", "Reply"), ("button", "Forward")], [("button", "Archive")],
		("delete", "remove", "trash", "bin", "discard")),
	("floppy disk", floppy, "notepad++", False, "new 1 - Notepad++", [("button", "New"), ("button", "Open")], [("button", "Close")],
		("save",)),
	("plus", plus, "Teams", False, "Chat | Microsoft Teams", [("tab", "Chat")], [("button", "Filter")],
		("add", "new", "create", "plus", "compose", "start")),
	("cross", close, "firefox", False, "Settings - Mozilla Firefox", [("tab", "Settings")], [("button", "New tab")],
		("close", "cancel", "exit", "dismiss", "clear")),
	("pencil", pencil, "mail.google.com", True, "Inbox - Gmail", [("button", "Main menu")], [("link", "Inbox")],
		("edit", "compose", "write", "rename", "draw", "pencil", "new")),
	("speaker", speaker, "Zoom", False, "Zoom Meeting", [("button", "Start video")], [("button", "Participants")],
		("volume", "sound", "audio", "speaker", "mute", "unmute")),
	("three lines", hamburger, "example.com", True, "Example Shop", [("link", "Skip to content")], [("link", "Shop")],
		("menu", "navigation", "more")),
	("heart", heart, "instagram.com", True, "Instagram", [("link", "Profile")], [("button", "Comment"), ("button", "Share")],
		("like", "favourite", "favorite", "love")),
	("bell", bell, "github.com", True, "GitHub", [("button", "Search")], [("button", "Create new"), ("button", "Your profile")],
		("notification", "notifications", "alert", "alerts", "bell", "reminder", "reminders")),
	("house", house, "explorer", False, "Documents - File Explorer", [("button", "Back"), ("button", "Up")], [("button", "Refresh")],
		("home",)),
	("arrow into a tray", download, "drive.google.com", True, "My Drive - Google Drive", [("button", "Share")],
		[("button", "More actions")], ("download", "save", "export")),
	("padlock", lock, "KeePass", False, "Database.kdbx - KeePass", [("button", "Save")], [("button", "Search")],
		("lock", "unlock", "secure", "security", "private", "password", "locked")),
	("nothing", empty, "game", False, "Space Trader", [("button", "New Game")], [("button", "Quit")], ()),
)


# A second set, drawn and written on 2026-11-19 after the first was run and the rule (working.named: only a model that
# is not small is told where the control is; a copied name is asked again, then dropped) was made from it, before
# anything was run on this set. Run it with --second.
def refresh(d):
	d.arc((12, 12, 52, 52), 30, 330, fill=INK, width=6)
	d.polygon(((44, 6), (56, 20), (40, 22)), fill=INK)


def share(d):
	for x, y in ((46, 14), (16, 32), (46, 50)):
		d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=INK)
	d.line((46, 14, 16, 32), fill=INK, width=4)
	d.line((16, 32, 46, 50), fill=INK, width=4)


def camera(d):
	d.rounded_rectangle((8, 20, 56, 52), radius=6, fill=INK)
	d.rectangle((22, 14, 38, 20), fill=INK)
	d.ellipse((22, 26, 42, 46), fill=(243, 243, 246))
	d.ellipse((27, 31, 37, 41), fill=INK)


def microphone(d):
	d.rounded_rectangle((24, 8, 40, 38), radius=8, fill=INK)
	d.arc((16, 20, 48, 46), 0, 180, fill=INK, width=4)
	d.line((32, 46, 32, 54), fill=INK, width=4)
	d.line((22, 55, 42, 55), fill=INK, width=4)


def star(d):
	d.polygon(((32, 6), (39, 24), (58, 24), (43, 36), (49, 56), (32, 44), (15, 56), (21, 36), (6, 24), (25, 24)), fill=INK)


def printer(d):
	d.rectangle((18, 8, 46, 22), outline=INK, width=3)
	d.rounded_rectangle((8, 22, 56, 44), radius=4, fill=INK)
	d.rectangle((18, 38, 46, 56), fill=(243, 243, 246), outline=INK, width=3)


def paperclip(d):
	d.arc((20, 6, 44, 30), 180, 360, fill=INK, width=4)
	d.line((20, 18, 20, 46), fill=INK, width=4)
	d.line((44, 18, 44, 40), fill=INK, width=4)
	d.arc((20, 34, 36, 58), 0, 180, fill=INK, width=4)
	d.line((36, 46, 36, 22), fill=INK, width=4)


def envelope(d):
	d.rectangle((8, 16, 56, 48), outline=INK, width=4)
	d.line((8, 16, 32, 36, 56, 16), fill=INK, width=4)


def calendar(d):
	d.rectangle((10, 14, 54, 54), outline=INK, width=4)
	d.rectangle((10, 14, 54, 24), fill=INK)
	d.line((20, 8, 20, 18), fill=INK, width=4)
	d.line((44, 8, 44, 18), fill=INK, width=4)
	for x in (18, 30, 42):
		for y in (30, 42):
			d.rectangle((x, y, x + 5, y + 5), fill=INK)


def person(d):
	d.ellipse((22, 8, 42, 28), fill=INK)
	d.pieslice((10, 30, 54, 74), 180, 360, fill=INK)


def info(d):
	d.ellipse((8, 8, 56, 56), outline=INK, width=4)
	d.ellipse((29, 16, 35, 22), fill=INK)
	d.rectangle((29, 27, 35, 46), fill=INK)


def help(d):
	d.ellipse((8, 8, 56, 56), outline=INK, width=4)
	d.arc((22, 15, 42, 33), 180, 60, fill=INK, width=5)
	d.line((34, 31, 32, 38), fill=INK, width=5)
	d.ellipse((29, 42, 35, 48), fill=INK)


def funnel(d):
	d.polygon(((8, 12), (56, 12), (36, 34), (36, 54), (28, 48), (28, 34)), fill=INK)


def corners(d):
	for (x, y), (dx, dy) in (((10, 10), (1, 1)), ((54, 10), (-1, 1)), ((10, 54), (1, -1)), ((54, 54), (-1, -1))):
		d.line((x, y, x + 14 * dx, y), fill=INK, width=5)
		d.line((x, y, x, y + 14 * dy), fill=INK, width=5)


def undo(d):
	d.arc((16, 18, 54, 52), 200, 360, fill=INK, width=6)
	d.arc((16, 18, 54, 52), 0, 90, fill=INK, width=6)
	d.polygon(((8, 26), (24, 14), (26, 34)), fill=INK)


def wifi(d):
	for box in ((6, 14, 58, 66), (16, 24, 48, 56), (26, 34, 38, 46)):
		d.arc(box, 225, 315, fill=INK, width=5)
	d.ellipse((29, 46, 35, 52), fill=INK)


PICTURES2 = (
	("circular arrow", refresh, "chrome", False, "New Tab - Google Chrome", [("button", "Back"), ("button", "Forward")],
		[("edit", "Address and search bar")], ("refresh", "reload", "update", "sync")),
	("three joined dots", share, "youtube.com", True, "Video - YouTube", [("button", "Like"), ("button", "Dislike")],
		[("button", "Download")], ("share",)),
	("camera", camera, "Zoom", False, "Zoom Meeting", [("button", "Unmute")], [("button", "Participants")],
		("video", "camera", "photo", "picture", "screenshot", "capture")),
	("microphone", microphone, "Teams", False, "Meeting | Microsoft Teams", [("button", "Camera")], [("button", "Share")],
		("microphone", "mic", "mute", "unmute", "record", "voice", "audio", "dictate")),
	("star", star, "chrome", False, "Recipes - Google Chrome", [("edit", "Address and search bar")], [("button", "Extensions")],
		("bookmark", "favourite", "favorite", "star", "favorites", "favourites")),
	("printer", printer, "WINWORD", False, "Letter.docx - Word", [("button", "Save")], [("button", "Undo")], ("print",)),
	("paperclip", paperclip, "OUTLOOK", False, "Untitled - Message", [("button", "Send")], [("button", "Insert picture")],
		("attach", "attachment", "attachments", "add attachment", "clip")),
	("envelope", envelope, "example.com", True, "Contact us - Example", [("link", "Phone")], [("link", "Map")],
		("mail", "email", "e-mail", "message", "contact", "inbox")),
	("calendar", calendar, "OUTLOOK", False, "Inbox - Outlook", [("button", "Mail")], [("button", "People")],
		("calendar", "date", "schedule", "events")),
	("person", person, "github.com", True, "GitHub", [("button", "Notifications")], [("button", "Create new")],
		("profile", "account", "user", "sign in", "login", "me", "avatar")),
	("letter i in a circle", info, "Spotify", False, "Spotify Premium", [("button", "Play")], [("slider", "Volume")],
		("info", "information", "about", "details")),
	("question mark in a circle", help, "notepad++", False, "new 1 - Notepad++", [("button", "Settings")], [("button", "Close")],
		("help", "question", "support", "faq")),
	("funnel", funnel, "EXCEL", False, "Budget.xlsx - Excel", [("button", "Sort")], [("button", "Clear")], ("filter",)),
	("four corners", corners, "vlc", False, "film.mp4 - VLC media player", [("button", "Stop")], [("slider", "Volume")],
		("fullscreen", "full screen", "maximize", "expand", "full")),
	("curved arrow back", undo, "WINWORD", False, "Letter.docx - Word", [("button", "Save")], [("button", "Redo")],
		("undo", "back", "revert")),
	("signal arcs", wifi, "explorer", False, "Taskbar", [("button", "Volume")], [("button", "Clock")],
		("wi-fi", "wifi", "wireless", "network", "internet", "signal", "connection")),
	("nothing", empty, "Steam", False, "Steam", [("button", "Library")], [("button", "Store")], ()),
)


def picture(draw):
	image, d = canvas()
	draw(d)
	return image


def rightly(name, wanted, around):
	words = set(audit.plainText(name).split())
	if not wanted:
		return not name
	if any(audit.plainText(name) == audit.plainText(other) for _kind, other in around):
		return False  # a copy of a control around it
	joined = audit.plainText(name).replace(" ", "")
	# "Wi-Fi" is wifi: a name is also compared with its words joined, and a wanted name of two words or with a hyphen
	# ("wi-fi", "full screen") may stand inside it. A plain word must be one of the name's own words.
	return bool(words & set(wanted)) or any(
		(want.replace("-", "").replace(" ", "") in joined) if ("-" in want or " " in want)
		else want == joined for want in wanted)


def main():
	sys.stdout.reconfigure(errors="replace")
	folder = sys.argv[1] if len(sys.argv) > 1 else "no-models-folder"
	cat = OneModelCatalog(folder, harness.visionMateData())
	chosen = {"backend": "auto", "visionModel": sys.argv[2] if len(sys.argv) > 2 else "", "coderModel": ""}
	rt = runtime.ModelRuntime(harness.ENGINE_DIR, cat, lambda: chosen)
	if rt.entry(VISION) is None:
		sys.exit("No model found.")
	print("vision:", rt.entry(VISION)["name"], flush=True)
	llm = LLM(rt, taskModule.Task("naming controls"))
	scores = {"before": 0, "form": 0, "around": 0, "rule": 0}
	pictures = PICTURES2 if "--second" in sys.argv else PICTURES
	entry = rt.entry(VISION)
	try:
		for what, draw, place, isSite, title, before, after, wanted in pictures:
			image = prepareImage(picture(draw), 448)
			answers = {}
			answers["before"] = audit.cleanName(rt.describe(image, OLD_PROMPT, 24))
			def ask(around, image=image):
				answer = llm.json(VISION, prompts.seeing(working.NAME_SYSTEM), working.nameQuestion("button", around),
					working.NAME_SCHEMA, maxTokens=24, image=image)
				return audit.cleanName(answer.get("name"))

			told = working.aroundText(place, isSite, title, before, after)
			answers["form"], answers["around"] = ask(""), ask(told)
			# What VisionClaw does (accesstools.nameByLooking): working.named, with the answers above where it asks the same.
			given = {"": answers["form"], told: answers["around"]}
			answers["rule"] = working.named(lambda around: given[around], entry, told, before + after, [place, title])
			line = []
			for label in ("before", "form", "around", "rule"):
				ok = rightly(answers[label], wanted, before + after)
				scores[label] += ok
				line.append(f"{label} {'ok' if ok else 'MISS'} {answers[label]!r}")
			print(f"{what}: " + "; ".join(line), flush=True)
	finally:
		rt.stop()
	total = len(pictures)
	print(f"Named rightly of {total}: as before {scores['before']}; with the instructions and the form {scores['form']}; "
		f"with where it is too {scores['around']}; as VisionClaw now asks {scores['rule']}.")


if __name__ == "__main__":
	main()
