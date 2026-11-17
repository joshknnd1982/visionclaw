# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - newer versions of VisionClaw itself. The list of releases is read from VisionClaw's own
# repository on GitHub, and nothing else; from it, plain code decides whether a newer version exists and which
# one file may be downloaded for it. A release can only ever point the download at its own add-on file on
# github.com, with the size and SHA-256 that GitHub reports for it, which the download then verifies.
# When the list is read is the user's choice: only when they ask, or when NVDA starts, at most once a day.
# Nothing is ever installed without the user's yes. No NVDA dependencies.

import re

from .catalog import versionTuple

REPO = "joshknnd1982/visionclaw"
# Every release is looked at, not only the one GitHub calls the latest: pre-releases are releases too.
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=20"
PAGE_URL = f"https://github.com/{REPO}/releases"
LIST_BYTES = 3000000
MANUAL, AUTO = "manual", "auto"
MODES = [MANUAL, AUTO]
# With the automatic choice, the list is read when NVDA starts, but not more often than this.
CHECK_EVERY_SECONDS = 20 * 3600
_TAG = re.compile(r"^v(\d+(?:\.\d+){1,3})$")
_DIGEST = re.compile(r"^sha256:([0-9a-f]{64})$")
MIN_BYTES, MAX_BYTES = 200000, 400 * 2 ** 20
NOTES_CHARS = 500


def _file(release, version):
	"""The add-on file of a release, as {"name", "url", "size", "sha256"}, or None if the release has no file
	that may be downloaded. Only the release's own add-on file, named for the release's version, at its own
	address on github.com, with a size and a SHA-256, counts. The SHA-256 comes from GitHub like the file
	itself: it shows that the file arrived whole and unchanged on the way, not who made it. A file without
	one is refused."""
	tag = release.get("tag_name")
	wanted = f"VisionClaw-{version}.nvda-addon"
	for asset in release.get("assets") or ():
		if not isinstance(asset, dict) or asset.get("name") != wanted:
			continue
		name, size = asset["name"], asset.get("size")
		digest = _DIGEST.match(str(asset.get("digest") or ""))
		if asset.get("browser_download_url") != f"https://github.com/{REPO}/releases/download/{tag}/{name}":
			continue
		if not isinstance(size, int) or isinstance(size, bool) or not MIN_BYTES <= size <= MAX_BYTES or not digest:
			continue
		return {"name": name, "url": asset["browser_download_url"], "size": size, "sha256": digest.group(1)}
	return None


def notesOf(body):
	"""What a release says is new, as plain text short enough to be listened to. VisionClaw's releases put it
	under a heading that begins "New in"; where there is one, only what stands under it is taken."""
	raw = str(body or "").splitlines()
	start = next((i for i, line in enumerate(raw) if re.match(r"^#+\s*new in\b", line.strip(), re.IGNORECASE)), None)
	if start is not None:
		end = next((i for i in range(start + 1, len(raw)) if raw[i].lstrip().startswith("#")), len(raw))
		raw = raw[start + 1:end]
	lines = []
	for line in raw:
		line = re.sub(r"[*_`#>]+", "", line).strip(" -\t")
		if line:
			lines.append(line)
	text = " ".join(lines)
	if len(text) > NOTES_CHARS:
		text = text[:NOTES_CHARS].rsplit(" ", 1)[0] + " ..."
	return text


def newest(releases, current):
	"""The newest release that is newer than the version in use, as a dictionary: version, name, url, size,
	sha256, notes; or None if the version in use is the newest. releases is GitHub's list. Drafts, releases
	without a proper version, and releases whose file may not be downloaded are passed over.
	Raises ValueError if what came back is not a list of releases."""
	if not isinstance(releases, list):
		raise ValueError("What GitHub answered is not a list of releases.")
	best = None
	for release in releases:
		if not isinstance(release, dict) or release.get("draft"):
			continue
		tag = _TAG.match(str(release.get("tag_name") or ""))
		if not tag:
			continue
		version = tag.group(1)
		if versionTuple(version) <= versionTuple(current) or (best and versionTuple(version) <= versionTuple(best["version"])):
			continue
		found = _file(release, version)
		if found is None:
			continue
		found.update(version=version, notes=notesOf(release.get("body")))
		best = found
	return best


def due(mode, lastChecked, now):
	"""Whether the list should be read by itself now: only with the automatic choice, and not if it was read
	within the last day. lastChecked is the time of the last reading as kept in the settings, or ""."""
	if mode != AUTO:
		return False
	try:
		last = float(lastChecked)
	except (TypeError, ValueError):
		return True
	return now - last >= CHECK_EVERY_SECONDS or now < last


def availableText(found, current):
	"""The sentence that says a newer version exists."""
	megabytes = max(1, round(found["size"] / 2 ** 20))
	text = f"VisionClaw {found['version']} is available. You have {current}. It is a download of {megabytes} MB."
	if found["notes"]:
		text += f" What is new: {found['notes']}"
	return text


def newestText(current):
	return f"You have the newest version of VisionClaw, {current}."
