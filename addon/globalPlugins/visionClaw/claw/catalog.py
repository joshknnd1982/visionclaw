# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the models VisionClaw can use, which of them are on this computer, and downloading them.
# Every download is pinned to one revision and checked against its SHA-256. No NVDA dependencies.
#
# Which models are offered: the ones built in below, and those of a list the user can have fetched from
# VisionClaw's own page on GitHub (LIST_URL), so that newer Qwen models can be offered without a new version
# of the add-on. The list is only fetched when the user asks for it and says yes. Every model in it is checked
# as strictly as the built-in ones are written: only Qwen models, only from Hugging Face, only from known
# publishers, pinned to one revision, with the size and SHA-256 of every file, which the download verifies.

import json
import os
import re

from .. import net

VISION, CODER = "vision", "coder"
_HF = "https://huggingface.co/{repo}/resolve/{rev}/{name}"


def _file(repo, rev, name, size, sha256, kind="model"):
	return {"kind": kind, "name": name, "size": size, "sha256": sha256, "url": _HF.format(repo=repo, rev=rev, name=name)}


_Q35_08B = ("unsloth/Qwen3.5-0.8B-GGUF", "6ab461498e2023f6e3c1baea90a8f0fe38ab64d0")
_Q35_2B = ("unsloth/Qwen3.5-2B-GGUF", "f6d5376be1edb4d416d56da11e5397a961aca8ae")
_Q35_4B = ("unsloth/Qwen3.5-4B-GGUF", "e87f176479d0855a907a41277aca2f8ee7a09523")
_Q35_9B = ("unsloth/Qwen3.5-9B-GGUF", "3885219b6810b007914f3a7950a8d1b469d598a5")
_C05 = ("Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF", "ebb2015119c907b064c512bf053e945850b5875f")
_C15 = ("Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF", "f86cb2c1fa58255f8052cc32aeede1b7482d4361")
_C7 = ("Qwen/Qwen2.5-Coder-7B-Instruct-GGUF", "13fb94bfda8c8cf22497dc57b78f391a9acb426a")

_Q35_2B_MODEL = _file(*_Q35_2B, "Qwen3.5-2B-Q4_K_M.gguf", 1280835840,
	"aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223")
_Q35_4B_MODEL = _file(*_Q35_4B, "Qwen3.5-4B-Q4_K_M.gguf", 2740937888,
	"00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4")
_Q35_9B_MODEL = _file(*_Q35_9B, "Qwen3.5-9B-Q4_K_M.gguf", 5680522464,
	"03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8")

# Every model is always offered, whatever the computer and whichever graphics option is chosen: the user decides.
# The computer only decides which model is suggested first.
# dir: the folder the files are kept in. Two entries with the same dir share their files, so Qwen3.5 4B is
#   downloaded once even when it is used for both vision and coding.
# thinking: the model has its own thinking mode that can be switched on and off.
# memoryGb: about how much memory it uses while loaded. maxContext: the largest context VisionClaw gives it.
# suggest: False for a model that is offered but never suggested first, because it is very small.
# The models of one role are listed from the smallest to the largest.
CATALOG = [
	{
		"id": "qwen3.5-0.8b", "dir": "qwen3.5-0.8b", "role": VISION, "name": "Qwen3.5 0.8B", "small": True,
		"suggest": False, "thinking": True, "memoryGb": 1.4, "maxContext": 16384, "licence": "Apache 2.0",
		"source": _Q35_08B[0],
		"files": [
			_file(*_Q35_08B, "Qwen3.5-0.8B-Q4_K_M.gguf", 532517120,
				"bd258782e35f7f458f8aced1adc053e6e92e89bc735ba3be89d38a06121dc517"),
			_file(*_Q35_08B, "mmproj-F16.gguf", 204987232,
				"56e4c6cfe73b0c82e3e82bc518d7591997e61d81f723fc41a586f4fa69ea2453", "mmproj"),
		],
	},
	{
		"id": "qwen3.5-2b", "dir": "qwen3.5-2b", "role": VISION, "name": "Qwen3.5 2B", "small": True,
		"thinking": True, "memoryGb": 2.6, "maxContext": 16384, "licence": "Apache 2.0", "source": _Q35_2B[0],
		"files": [
			_Q35_2B_MODEL,
			_file(*_Q35_2B, "mmproj-F16.gguf", 668227264,
				"7035e9cb8d7c6a9681d07eef9a364783e86ea4cd73faab2eabb4f43a101830c7", "mmproj"),
		],
	},
	{
		"id": "qwen3.5-4b", "dir": "qwen3.5-4b", "role": VISION, "name": "Qwen3.5 4B", "small": False,
		"thinking": True, "memoryGb": 4.4, "maxContext": 16384, "licence": "Apache 2.0", "source": _Q35_4B[0],
		"files": [
			_Q35_4B_MODEL,
			_file(*_Q35_4B, "mmproj-F16.gguf", 672423616,
				"cd88edcf8d031894960bb0c9c5b9b7e1fea6ebee02b9f7ce925a00d12891f864", "mmproj"),
		],
	},
	{
		"id": "qwen3.5-9b", "dir": "qwen3.5-9b", "role": VISION, "name": "Qwen3.5 9B", "small": False,
		"thinking": True, "memoryGb": 7.6, "maxContext": 16384, "licence": "Apache 2.0", "source": _Q35_9B[0],
		"files": [
			_Q35_9B_MODEL,
			_file(*_Q35_9B, "mmproj-F16.gguf", 918166080,
				"f70dc3509053962b0d0d3ee8a7eacebf5d60aa560cad78254ae8698516ae029f", "mmproj"),
		],
	},
	{
		"id": "qwen2.5-coder-0.5b", "dir": "qwen2.5-coder-0.5b", "role": CODER, "name": "Qwen2.5 Coder 0.5B",
		"small": True, "suggest": False, "thinking": False, "memoryGb": 1.0, "maxContext": 32768,
		"licence": "Apache 2.0", "source": _C05[0],
		"files": [
			_file(*_C05, "qwen2.5-coder-0.5b-instruct-q4_k_m.gguf", 491400064,
				"1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32"),
		],
	},
	{
		"id": "qwen2.5-coder-1.5b", "dir": "qwen2.5-coder-1.5b", "role": CODER, "name": "Qwen2.5 Coder 1.5B",
		"small": True, "thinking": False, "memoryGb": 1.8, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _C15[0],
		"files": [
			_file(*_C15, "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf", 1117320768,
				"cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046"),
		],
	},
	{
		"id": "qwen3.5-4b-coder", "dir": "qwen3.5-4b", "role": CODER, "name": "Qwen3.5 4B, used for coding",
		"small": False, "thinking": True, "memoryGb": 3.8, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _Q35_4B[0], "files": [_Q35_4B_MODEL],
	},
	{
		"id": "qwen2.5-coder-7b", "dir": "qwen2.5-coder-7b", "role": CODER, "name": "Qwen2.5 Coder 7B",
		"small": False, "thinking": False, "memoryGb": 5.8, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _C7[0],
		"files": [
			_file(*_C7, "qwen2.5-coder-7b-instruct-q4_k_m.gguf", 4683073536,
				"509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c"),
		],
	},
	{
		"id": "qwen3.5-9b-coder", "dir": "qwen3.5-9b", "role": CODER, "name": "Qwen3.5 9B, used for coding",
		"small": False, "thinking": True, "memoryGb": 7.0, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _Q35_9B[0], "files": [_Q35_9B_MODEL],
	},
]

# VisionMate's vision data (Qwen3-VL 2B), if that add-on downloaded it on this computer. It is used where it is.
VISIONMATE_ID = "visionmate-data"
_VISIONMATE = {
	"id": VISIONMATE_ID, "dir": None, "role": VISION,
	"name": "Qwen3-VL 2B (already on this computer, from VisionMate)",
	"small": True, "thinking": False, "memoryGb": 2.6, "maxContext": 16384, "licence": "Apache 2.0",
	"source": "VisionMate", "files": [],
}


# --- The list of offered models that the user can have fetched ---

# VisionClaw's own page. Nothing but this one file is ever read from it.
LIST_URL = "https://raw.githubusercontent.com/joshknnd1982/visionclaw/main/models.json"
LIST_FORMAT = 1
# When the list in this version was last brought up to date with what the Qwen team has published.
LIST_UPDATED = "2026-11-17"
LIST_BYTES = 400000
MAX_OFFERED = 40
# Who may publish the files: the Qwen team itself, and Unsloth, whose conversions the built-in models use.
PUBLISHERS = ("Qwen", "unsloth")
LICENCE = "Apache 2.0"
_ID = re.compile(r"^qwen[a-z0-9.-]{1,44}$")
_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,100}\.gguf$")
_FILE_URL = re.compile(
	r"^https://huggingface\.co/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/resolve/([0-9a-f]{40})/([A-Za-z0-9._-]+)$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^\d+(\.\d+){0,3}$")


def entrySize(entry):
	return sum(f["size"] for f in entry["files"])


def versionTuple(text):
	"""A version like "0.4.0" as numbers that can be compared. Anything else counts as the lowest."""
	text = str(text or "").strip()
	return tuple(int(part) for part in text.split(".")) if _VERSION.match(text) else ()


def _need(ok, why):
	if not ok:
		raise ValueError(why)


def checkEntry(raw):
	"""A model from a fetched list, as an entry like the built-in ones, with only what an entry may hold.
	Raises ValueError if anything about it is not as it must be. The rules are those the built-in entries
	follow: a Qwen model under the Apache 2.0 licence, every file a .gguf from Hugging Face, from a known
	publisher, pinned to one revision, with its size and SHA-256."""
	_need(isinstance(raw, dict), "not an entry")
	ident, folder = raw.get("id"), raw.get("dir")
	_need(isinstance(ident, str) and _ID.match(ident), "the id is not a Qwen model's")
	_need(isinstance(folder, str) and _ID.match(folder), "the folder name is not allowed")
	_need(raw.get("role") in (VISION, CODER), "the role is unknown")
	name = raw.get("name")
	_need(isinstance(name, str) and 3 <= len(name) <= 60 and name.isprintable() and "qwen" in name.lower(), "the name is not allowed")
	_need(raw.get("licence") == LICENCE, "the licence is not Apache 2.0")
	source = raw.get("source")
	_need(isinstance(source, str) and source.count("/") == 1 and source.split("/")[0] in PUBLISHERS, "the publisher is not known")
	memory, context = raw.get("memoryGb"), raw.get("maxContext")
	_need(isinstance(memory, (int, float)) and not isinstance(memory, bool) and 0.3 <= memory <= 64, "the memory figure is not allowed")
	_need(isinstance(context, int) and not isinstance(context, bool) and 2048 <= context <= 131072, "the context size is not allowed")
	needs = raw.get("minVersion", "")
	_need(needs == "" or (isinstance(needs, str) and _VERSION.match(needs)), "the version it needs is not a version")
	files = raw.get("files")
	_need(isinstance(files, list) and 1 <= len(files) <= 2, "the files are missing")
	clean = []
	for f in files:
		_need(isinstance(f, dict) and f.get("kind") in ("model", "mmproj"), "a file's kind is unknown")
		fileName, size, sha, url = f.get("name"), f.get("size"), f.get("sha256"), f.get("url")
		_need(isinstance(fileName, str) and _FILE_NAME.match(fileName), "a file's name is not allowed")
		_need(isinstance(size, int) and not isinstance(size, bool) and 50 * 2 ** 20 <= size <= 40 * 2 ** 30, "a file's size is not allowed")
		_need(isinstance(sha, str) and _SHA256.match(sha), "a file has no SHA-256")
		found = _FILE_URL.match(url) if isinstance(url, str) else None
		_need(found is not None, "a file's address is not a pinned Hugging Face address")
		_need(f"{found.group(1)}/{found.group(2)}" == source and found.group(4) == fileName, "a file's address does not fit the entry")
		clean.append({"kind": f["kind"], "name": fileName, "size": size, "sha256": sha, "url": url})
	kinds = [f["kind"] for f in clean]
	_need(kinds.count("model") == 1, "there must be exactly one model file")
	_need(kinds.count("mmproj") == (1 if raw["role"] == VISION and len(clean) == 2 else 0), "the projector file does not fit the role")
	_need(raw["role"] == CODER or len(clean) == 2, "a vision model needs its projector file")
	entry = {
		"id": ident, "dir": folder, "role": raw["role"], "name": name, "small": bool(raw.get("small")),
		"thinking": bool(raw.get("thinking")), "memoryGb": float(memory), "maxContext": context, "licence": LICENCE,
		"source": source, "files": clean,
	}
	if raw.get("suggest") is False:
		entry["suggest"] = False
	if needs:
		entry["minVersion"] = needs
	return entry


def _fits(entry, others):
	"""Whether an entry can share its folder with the entries that already use it: a file of the same name
	must be the same file."""
	for other in others:
		if other["dir"] != entry["dir"]:
			continue
		for f in entry["files"]:
			for g in other["files"]:
				if f["name"] == g["name"] and (f["size"], f["sha256"]) != (g["size"], g["sha256"]):
					return False
	return True


def readList(data, version=""):
	"""The models of a fetched list that may be offered beside the built-in ones, as
	(entries, how many need a newer VisionClaw, how many were refused, the date the list gives).
	version is this VisionClaw's. A model that is built in is left out without a word. Raises ValueError if the
	list as a whole cannot be read."""
	_need(isinstance(data, dict) and data.get("format") == LIST_FORMAT and isinstance(data.get("models"), list),
		"The list is not in a form this version of VisionClaw can read.")
	builtIn = {entry["id"] for entry in CATALOG}
	entries, tooNew, refused = [], 0, 0
	for raw in data["models"][:200]:
		try:
			entry = checkEntry(raw)
		except ValueError:
			refused += 1
			continue
		if entry["id"] in builtIn or any(entry["id"] == e["id"] for e in entries):
			continue
		if not _fits(entry, CATALOG + entries) or len(entries) >= MAX_OFFERED:
			refused += 1
		elif versionTuple(entry.get("minVersion")) > versionTuple(version):
			tooNew += 1
		else:
			entries.append(entry)
	updated = data.get("updated")
	return entries, tooNew, refused, updated if isinstance(updated, str) and len(updated) <= 20 and updated.isprintable() else ""


def publishedList():
	"""The list as it is published on VisionClaw's page: every built-in model, so that an older VisionClaw is
	offered the models a newer one has built in. models.json in the repository must be exactly this."""
	return {"format": LIST_FORMAT, "updated": LIST_UPDATED, "models": [
		{key: value for key, value in entry.items()} for entry in CATALOG]}


class Catalog:
	"""modelsDir holds one folder per downloaded model. visionMateDir is VisionMate's data folder, or None."""

	def __init__(self, modelsDir, visionMateDir=None):
		self.modelsDir = modelsDir
		self._visionMateDir = visionMateDir
		self._offered = None

	def _listPath(self):
		return os.path.join(self.modelsDir, "offered.json")

	def offered(self):
		"""The models from the list that was last fetched, beyond the built-in ones. The saved list is checked
		again each time it is read, like a fresh one."""
		if self._offered is None:
			self._offered = []
			try:
				with open(self._listPath(), encoding="utf-8") as f:
					saved = json.load(f)
				self._offered = readList(saved, saved.get("forVersion", ""))[0]
			except (OSError, ValueError, AttributeError):
				pass
		return self._offered

	def all(self):
		"""Every model that can be offered: the built-in ones, then those of the fetched list."""
		return CATALOG + self.offered()

	def look(self, version="", fetch=None):
		"""Fetch the list of offered models from VisionClaw's page and keep it. Only ever called when the user
		asked for it. fetch(url) returns the list as Python data. Returns a dictionary: new (the names of models
		not offered before), tooNew and refused (how many), updated (the list's date).
		Raises OSError if the page cannot be reached, ValueError if the list cannot be read."""
		if fetch is None:
			fetch = lambda url: net.fetchJson(url, limit=LIST_BYTES)  # noqa: E731
		data = fetch(LIST_URL)
		entries, tooNew, refused, updated = readList(data, version)
		before = {entry["id"] for entry in self.offered()}
		os.makedirs(self.modelsDir, exist_ok=True)
		tmp = self._listPath() + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			json.dump({"format": LIST_FORMAT, "updated": updated, "forVersion": str(version), "models": entries}, f, indent=1)
		os.replace(tmp, self._listPath())
		self._offered = entries
		return {
			"new": [entry["name"] for entry in entries if entry["id"] not in before], "tooNew": tooNew,
			"refused": refused, "updated": updated,
		}

	def _visionMatePaths(self):
		if not self._visionMateDir:
			return None
		core = os.path.join(self._visionMateDir, "core.bin")
		vision = os.path.join(self._visionMateDir, "vision.bin")
		return (core, vision) if os.path.isfile(core) and os.path.isfile(vision) else None

	def entries(self, role=None):
		"""Every model that can be chosen, the ones to download first."""
		found = [e for e in self.all() if role in (None, e["role"])]
		if role in (None, VISION) and self._visionMatePaths():
			found.append(_VISIONMATE)
		return found

	def get(self, modelId):
		for entry in self.entries():
			if entry["id"] == modelId:
				return entry
		return None

	def _path(self, entry, f):
		return os.path.join(self.modelsDir, entry["dir"], f["name"])

	def _has(self, entry, f):
		try:
			return os.path.getsize(self._path(entry, f)) == f["size"]
		except OSError:
			return False

	def isInstalled(self, entry):
		if entry["id"] == VISIONMATE_ID:
			return self._visionMatePaths() is not None
		return all(self._has(entry, f) for f in entry["files"])

	def installed(self, role):
		return [e for e in self.entries(role) if self.isInstalled(e)]

	def selected(self, role, preferredId=None):
		"""The model to use for a role: the user's choice if it is installed, else the first installed one."""
		installed = self.installed(role)
		for entry in installed:
			if entry["id"] == preferredId:
				return entry
		return installed[0] if installed else None

	def paths(self, entry):
		"""(model file, vision projector file or None)."""
		if entry["id"] == VISIONMATE_ID:
			return self._visionMatePaths()
		model = mmproj = None
		for f in entry["files"]:
			if f["kind"] == "mmproj":
				mmproj = self._path(entry, f)
			else:
				model = self._path(entry, f)
		return model, mmproj

	def fileSize(self, entry):
		"""Bytes on disk of an installed model."""
		return sum(os.path.getsize(p) for p in self.paths(entry) if p)

	def missingBytes(self, entry):
		"""How much is left to download, counting what an interrupted download already got."""
		left = 0
		for f in entry["files"]:
			if self._has(entry, f):
				continue
			try:
				left += max(0, f["size"] - os.path.getsize(self._path(entry, f) + ".part"))
			except OSError:
				left += f["size"]
		return left

	def download(self, entry, onProgress=None, cancel=None):
		"""Download what is missing of a model. Calls onProgress(doneBytes, totalBytes) over all its files.
		Raises net.Cancelled, OSError, or ValueError if a file arrives damaged."""
		os.makedirs(os.path.join(self.modelsDir, entry["dir"]), exist_ok=True)
		total = entrySize(entry)
		before = 0
		for f in entry["files"]:
			if not self._has(entry, f):
				def progress(done, _total, before=before):
					if onProgress is not None:
						onProgress(before + done, total)
				net.download(f["url"], self._path(entry, f), f["size"], f["sha256"], progress, cancel)
			before += f["size"]
			if onProgress is not None:
				onProgress(before, total)

	def stored(self):
		"""The models on this computer's disk, one for each folder of model files, as dictionaries:
		key (what to pass to removeStored), name, bytes, roles (what it can be used for now), ids (the catalog
		entries that are complete), and partial (a download that was not finished).
		One folder can serve two roles: Qwen3.5 4B with its projector is a vision model and a coder model."""
		found = []
		seen = []
		everything = self.all()
		for entry in everything:
			if entry["dir"] in seen:
				continue
			seen.append(entry["dir"])
			family = [e for e in everything if e["dir"] == entry["dir"]]
			names = {f["name"] for e in family for f in e["files"]}
			size, partial = 0, False
			for name in sorted(names):
				for path, unfinished in ((os.path.join(self.modelsDir, entry["dir"], name), False),
						(os.path.join(self.modelsDir, entry["dir"], name + ".part"), True)):
					try:
						size += os.path.getsize(path)
						partial = partial or unfinished
					except OSError:
						pass
			if not size:
				continue
			complete = [e for e in family if self.isInstalled(e)]
			found.append({
				"key": entry["dir"], "name": entry["name"], "bytes": size,
				"roles": sorted({e["role"] for e in complete}, reverse=True), "ids": [e["id"] for e in complete],
				"partial": partial or not complete,
			})
		paths = self._visionMatePaths()
		if paths:
			found.append({
				"key": VISIONMATE_ID, "name": "Qwen3-VL 2B, VisionMate's vision data",
				"bytes": sum(os.path.getsize(p) for p in paths), "roles": [VISION], "ids": [VISIONMATE_ID],
				"partial": False,
			})
		return found

	def removeStored(self, key):
		"""Delete one stored model with everything in its folder that belongs to it. Returns the bytes freed.
		Raises OSError if a file cannot be deleted, for example because an engine still has it open."""
		if key == VISIONMATE_ID:
			paths = list(self._visionMatePaths() or ()) + [os.path.join(self._visionMateDir or "", "data.json")]
			folder = None
		else:
			folder = os.path.join(self.modelsDir, key)
			names = {f["name"] for e in self.all() if e["dir"] == key for f in e["files"]}
			paths = [os.path.join(folder, n + end) for n in names for end in ("", ".part")]
		freed = 0
		for path in paths:
			try:
				size = os.path.getsize(path)
			except OSError:
				continue
			os.remove(path)
			freed += size
		if folder:
			try:
				os.rmdir(folder)
			except OSError:
				pass  # something else is in the folder; it is left alone
		return freed

	def remove(self, entry):
		"""Delete a downloaded model, keeping any file another installed model shares."""
		if entry["id"] == VISIONMATE_ID:
			return
		shared = set()
		for other in self.all():
			if other is not entry and other["dir"] == entry["dir"] and self.isInstalled(other):
				shared.update(f["name"] for f in other["files"])
		for f in entry["files"]:
			if f["name"] in shared:
				continue
			for path in (self._path(entry, f), self._path(entry, f) + ".part"):
				try:
					os.remove(path)
				except OSError:
					pass


def recommend(role, memoryGb=None, dedicatedMb=0):
	"""The catalog id to offer first: the larger model only where it clearly fits. Only built-in models are
	suggested, since those are the ones that were tried, and never the very smallest."""
	roomy = (dedicatedMb or 0) >= 11000 or (memoryGb or 0) >= 30
	choices = [e for e in CATALOG if e["role"] == role and e.get("suggest", True)]
	for entry in choices:
		if entry["small"] != roomy:
			return entry["id"]
	return choices[0]["id"]
