# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Newer versions of VisionClaw: which release counts as newer, and which one file may be downloaded for it.

The releases here have the shape GitHub's API gave for VisionClaw's own releases on 2026-11-17. Nothing goes
online in this test.
"""
import harness  # noqa: F401
from visionClaw.claw import updates

BASE = "https://github.com/joshknnd1982/visionclaw/releases/download"


def asset(tag, name, size=32309238, digest="sha256:" + "8" * 64, url=None):
	return {"name": name, "size": size, "digest": digest, "browser_download_url": url or f"{BASE}/{tag}/{name}"}


def release(version, prerelease=True, draft=False, body="", assets=None, tag=None):
	tag = tag or f"v{version}"
	if assets is None:
		assets = [asset(tag, f"VisionClaw-{version}.nvda-addon"), asset(tag, "VisionClaw.nvda-addon")]
	return {"tag_name": tag, "prerelease": prerelease, "draft": draft, "body": body, "assets": assets}


# 1. The highest version wins, compared as numbers: 0.10.0 is newer than 0.9.0. Pre-releases count, because
# every VisionClaw release so far is one. The file taken is the one named for the version.
listed = [release("0.8.0"), release("0.10.0", body="* Faster.\n* **Fewer** mistakes.\n"), release("0.9.0"), release("0.7.0")]
found = updates.newest(listed, "0.7.0")
assert found == {
	"name": "VisionClaw-0.10.0.nvda-addon", "url": f"{BASE}/v0.10.0/VisionClaw-0.10.0.nvda-addon", "size": 32309238,
	"sha256": "8" * 64, "version": "0.10.0", "notes": "Faster. Fewer mistakes.", "whatsNew": "Faster.\nFewer mistakes.",
}, found
# 2. The version in use, or a lower one, is never offered; with nothing newer the answer is None.
assert updates.newest(listed, "0.10.0") is None and updates.newest(listed, "0.11") is None
assert updates.newest([release("0.7.0")], "0.7.0") is None and updates.newest([], "0.7.0") is None
assert updates.newest(listed, "0.9.5")["version"] == "0.10.0"
# A version that cannot be read, as before the add-on knows its own, counts as the lowest: a release is offered.
assert updates.newest([release("0.7.0")], "")["version"] == "0.7.0"
# 3. What is passed over: a draft, a tag that is not v and numbers, and a release whose file may not be taken.
tag = "v9.0.0"
name = "VisionClaw-9.0.0.nvda-addon"
for why, bad in (
	("a draft", release("9.0.0", draft=True)),
	("a tag that is not a version", release("9.0.0", tag="latest")),
	("a tag with words", release("9.0.0", tag="v9.0.0-beta")),
	("no files", release("9.0.0", assets=[])),
	("only the copy with the fixed name", release("9.0.0", assets=[asset(tag, "VisionClaw.nvda-addon")])),
	("a file for another version", release("9.0.0", assets=[asset(tag, "VisionClaw-9.9.9.nvda-addon")])),
	("another kind of file", release("9.0.0", assets=[asset(tag, "VisionClaw-9.0.0.exe")])),
	("a file on another server", release("9.0.0", assets=[asset(tag, name, url=f"https://example.com/{name}")])),
	("a file of another repository", release("9.0.0", assets=[asset(tag, name,
		url=f"https://github.com/someone/visionclaw/releases/download/{tag}/{name}")])),
	("a file of another release", release("9.0.0", assets=[asset(tag, name, url=f"{BASE}/v1.0.0/{name}")])),
	("no secure connection", release("9.0.0", assets=[asset(tag, name, url=f"{BASE}/{tag}/{name}".replace("https", "http"))])),
	("no checksum", release("9.0.0", assets=[asset(tag, name, digest=None)])),
	("another kind of checksum", release("9.0.0", assets=[asset(tag, name, digest="md5:" + "8" * 32)])),
	("no size", release("9.0.0", assets=[asset(tag, name, size=0)])),
	("a size that is not a number", release("9.0.0", assets=[asset(tag, name, size="32309238")])),
	("a file far too large", release("9.0.0", assets=[asset(tag, name, size=5 * 2 ** 30)])),
	("not a release at all", "v9.0.0"),
):
	assert updates.newest([bad, release("0.8.0")], "0.7.0")["version"] == "0.8.0", why
	assert updates.newest([bad], "0.7.0") is None, why
for wrong in ({"message": "Not Found"}, "nothing", None):
	try:
		updates.newest(wrong, "0.7.0")
		raise AssertionError(wrong)
	except ValueError as e:
		assert "not a list of releases" in str(e)

# 4. When the list is read by itself: never with "only when I ask"; with the automatic choice when a day has
# nearly passed, when it was never read, and when the clock was set back.
now = 1_800_000_000.0
assert not updates.due("manual", "", now) and not updates.due("manual", str(now - 10 ** 6), now)
assert updates.due("auto", "", now) and updates.due("auto", "nonsense", now)
assert not updates.due("auto", str(now - 3600), now) and updates.due("auto", str(now - 21 * 3600), now)
assert updates.due("auto", str(now + 5000), now)
assert updates.MODES == ["manual", "auto"]

# 5. What is said.
assert updates.availableText(found, "0.7.0") == (
	"VisionClaw 0.10.0 is available. You have 0.7.0. It is a download of 31 MB. What is new: Faster. Fewer mistakes.")
assert updates.availableText(dict(found, notes=""), "0.7.0").endswith("It is a download of 31 MB.")
assert updates.newestText("0.8.0") == "You have the newest version of VisionClaw, 0.8.0."
body = "VisionClaw is an add-on.\n\n## New in 0.8.0\n\n- **Updates.** A key for them.\n- Smaller steps.\n\n## What has been tested\n\n- All."
assert updates.notesOf(body) == "Updates. A key for them. Smaller steps.", updates.notesOf(body)
# In the window, what is new is in full and one point to a line, so that it can be read line by line.
assert updates.whatsNew(body) == "Updates. A key for them.\nSmaller steps.", updates.whatsNew(body)
assert updates.offerText(found, "0.7.0").splitlines() == [
	"VisionClaw 0.10.0 is available. You have 0.7.0.", "It is a download of 31 MB.", "",
	"What is new in VisionClaw 0.10.0:", "Faster.", "Fewer mistakes.", "",
	"Nothing is downloaded until you choose Download and install.",
	"When the file is here and checked, NVDA asks whether to install it, and restarts after that.",
], updates.offerText(found, "0.7.0")
assert "The release does not say what is new." in updates.offerText(dict(found, notes="", whatsNew=""), "0.7.0")
# What is new is said whole, however long.
assert updates.whatsNew("word " * 4000) == " ".join(["word"] * 4000)
long = updates.notesOf("word " * 400)
assert long == " ".join(["word"] * 400) and not long.endswith("...")
# Only VisionClaw's own repository is ever read.
assert updates.RELEASES_URL == "https://api.github.com/repos/joshknnd1982/visionclaw/releases?per_page=20"
print("OK")
