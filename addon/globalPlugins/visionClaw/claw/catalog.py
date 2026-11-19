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
#
# Every built-in model is offered in two quants, and the user chooses (the owner, 2026-11-18: "user has final
# say"): Q4_K_M, smaller and faster, and Q6_K, larger and closer to the model as it was trained. Each quant is an
# entry of its own, so that an older VisionClaw can read the published list; the two entries of a model share
# its folder, and with it the vision projector file, which is downloaded once.

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
# Qwen3 14B, the model for hard cases (the owner, 2026-11-19: "capped at 9b parameter models, with edge cases using a
# 14b parameter model"). Read from Hugging Face's API on 2026-11-19: no Qwen model of 10 to 16 billion parameters sees
# pictures (Qwen3.5, 3.6 and 3.8 go from 9B to 27B; Qwen3-VL from 8B to 32B), so the model for hard cases reads and
# writes text only: what NVDA and Windows report about a control, and add-ons. Qwen's own conversion, one file per quant.
_Q3_14B = ("Qwen/Qwen3-14B-GGUF", "530227a7d994db8eca5ab5ced2fb692b614357fd")

_Q35_2B_MODEL = _file(*_Q35_2B, "Qwen3.5-2B-Q4_K_M.gguf", 1280835840,
	"aaf42c8b7c3cab2bf3d69c355048d4a0ee9973d48f16c731c0520ee914699223")
_Q35_4B_MODEL = _file(*_Q35_4B, "Qwen3.5-4B-Q4_K_M.gguf", 2740937888,
	"00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4")
_Q35_9B_MODEL = _file(*_Q35_9B, "Qwen3.5-9B-Q4_K_M.gguf", 5680522464,
	"03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8")

# The quants a model is offered in. Q4_K_M is smaller and faster; Q6_K is larger, slower, and closer to the model
# as it was trained, which matters most for exact names in code. The user chooses either for any model.
Q4, Q6 = "Q4_K_M", "Q6_K"
QUANTS = (Q4, Q6)
DEFAULT_QUANT = Q4
# The quant suggested first for a model, where measuring showed one other than DEFAULT_QUANT clearly better:
# {id of the model's Q4_K_M entry: quant}. Only a suggestion: every quant of every model is always offered.
SUGGESTED_QUANTS = {}

# The Q6_K files, read from Hugging Face's API at the same pinned revisions on 2026-11-18. The 4B and 9B files
# are shared by the vision entry and the entry used for coding, like their Q4_K_M files.
_Q6_FILES = {
	"qwen3.5-0.8b": _file(*_Q35_08B, "Qwen3.5-0.8B-Q6_K.gguf", 639029504,
		"8408c5c222111cec253682b49eece2a02ed641ded68490001ec4ee160e71098e"),
	"qwen3.5-2b": _file(*_Q35_2B, "Qwen3.5-2B-Q6_K.gguf", 1574961408,
		"fc90339420b4298887aafb307a4291c55440b730133bbffe6ba9630503dcb548"),
	"qwen3.5-4b": _file(*_Q35_4B, "Qwen3.5-4B-Q6_K.gguf", 3525956768,
		"fdedd781c9ce676ab66b018ca247ff78e8a33c98098a822c1e2d5075e7718f66"),
	"qwen3.5-9b": _file(*_Q35_9B, "Qwen3.5-9B-Q6_K.gguf", 7458301152,
		"91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59"),
	"qwen2.5-coder-0.5b": _file(*_C05, "qwen2.5-coder-0.5b-instruct-q6_k.gguf", 650379136,
		"c2adc7ad8b1733efd153af0f6c0364fd8fffce020a4ddf64fb8846b800c4a4e6"),
	"qwen2.5-coder-1.5b": _file(*_C15, "qwen2.5-coder-1.5b-instruct-q6_k.gguf", 1464178752,
		"9b05dce8089197c866b9f76e1db45de8617cda98d9d06059958cb8ad32c56dfa"),
	"qwen2.5-coder-7b": _file(*_C7, "qwen2.5-coder-7b-instruct-q6_k.gguf", 6254198784,
		"46291ddea1bfb608fe63d9a1907eea6918bda87a7626593edc4bf97c5fd73f9d"),
	# Read on 2026-11-19 at the same revision as its Q4_K_M file.
	"qwen3-14b": _file(*_Q3_14B, "Qwen3-14B-Q6_K.gguf", 12121937248,
		"ec1f1d1421d7636a23e17645cac6fda39ee4b5f1f11e42eb09238089705ef699"),
}
_Q6_FILES["qwen3.5-4b-coder"] = _Q6_FILES["qwen3.5-4b"]
_Q6_FILES["qwen3.5-9b-coder"] = _Q6_FILES["qwen3.5-9b"]

# Every model is always offered, whatever the computer and whichever graphics option is chosen: the user decides.
# The computer only decides which model is suggested first.
# dir: the folder the files are kept in. Two entries with the same dir share their files, so Qwen3.5 4B is
#   downloaded once even when it is used for both vision and coding.
# thinking: the model has its own thinking mode that can be switched on and off.
# memoryGb: about how much memory it uses while loaded. maxContext: the largest context VisionClaw gives it.
# suggest: False for a model that is offered but never suggested first, because it is very small.
# edge: True for a model kept for hard cases: larger than VisionClaw's everyday models, offered always, never suggested
#   for everyday use, and used for one step when the chosen models could not do a hard job, after the user says yes
#   (claw/hardcase.py). It may not fit on the graphics card; then it is split between the card and the processor.
# quant: which quant its weights file is (QUANTS). The entries of one model in other quants follow it.
# The models of one role are listed from the smallest to the largest.
_Q4_ENTRIES = [
	{
		"id": "qwen3.5-0.8b", "quant": Q4, "dir": "qwen3.5-0.8b", "role": VISION, "name": "Qwen3.5 0.8B", "small": True,
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
		"id": "qwen3.5-2b", "quant": Q4, "dir": "qwen3.5-2b", "role": VISION, "name": "Qwen3.5 2B", "small": True,
		"thinking": True, "memoryGb": 2.6, "maxContext": 16384, "licence": "Apache 2.0", "source": _Q35_2B[0],
		"files": [
			_Q35_2B_MODEL,
			_file(*_Q35_2B, "mmproj-F16.gguf", 668227264,
				"7035e9cb8d7c6a9681d07eef9a364783e86ea4cd73faab2eabb4f43a101830c7", "mmproj"),
		],
	},
	{
		"id": "qwen3.5-4b", "quant": Q4, "dir": "qwen3.5-4b", "role": VISION, "name": "Qwen3.5 4B", "small": False,
		"thinking": True, "memoryGb": 4.4, "maxContext": 16384, "licence": "Apache 2.0", "source": _Q35_4B[0],
		"files": [
			_Q35_4B_MODEL,
			_file(*_Q35_4B, "mmproj-F16.gguf", 672423616,
				"cd88edcf8d031894960bb0c9c5b9b7e1fea6ebee02b9f7ce925a00d12891f864", "mmproj"),
		],
	},
	{
		"id": "qwen3.5-9b", "quant": Q4, "dir": "qwen3.5-9b", "role": VISION, "name": "Qwen3.5 9B", "small": False,
		"thinking": True, "memoryGb": 7.6, "maxContext": 16384, "licence": "Apache 2.0", "source": _Q35_9B[0],
		"files": [
			_Q35_9B_MODEL,
			_file(*_Q35_9B, "mmproj-F16.gguf", 918166080,
				"f70dc3509053962b0d0d3ee8a7eacebf5d60aa560cad78254ae8698516ae029f", "mmproj"),
		],
	},
	{
		"id": "qwen2.5-coder-0.5b", "quant": Q4, "dir": "qwen2.5-coder-0.5b", "role": CODER, "name": "Qwen2.5 Coder 0.5B",
		"small": True, "suggest": False, "thinking": False, "memoryGb": 1.0, "maxContext": 32768,
		"licence": "Apache 2.0", "source": _C05[0],
		"files": [
			_file(*_C05, "qwen2.5-coder-0.5b-instruct-q4_k_m.gguf", 491400064,
				"1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32"),
		],
	},
	{
		"id": "qwen2.5-coder-1.5b", "quant": Q4, "dir": "qwen2.5-coder-1.5b", "role": CODER, "name": "Qwen2.5 Coder 1.5B",
		"small": True, "thinking": False, "memoryGb": 1.8, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _C15[0],
		"files": [
			_file(*_C15, "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf", 1117320768,
				"cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046"),
		],
	},
	{
		"id": "qwen3.5-4b-coder", "quant": Q4, "dir": "qwen3.5-4b", "role": CODER, "name": "Qwen3.5 4B, used for coding",
		"small": False, "thinking": True, "memoryGb": 3.8, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _Q35_4B[0], "files": [_Q35_4B_MODEL],
	},
	{
		"id": "qwen2.5-coder-7b", "quant": Q4, "dir": "qwen2.5-coder-7b", "role": CODER, "name": "Qwen2.5 Coder 7B",
		"small": False, "thinking": False, "memoryGb": 5.8, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _C7[0],
		"files": [
			_file(*_C7, "qwen2.5-coder-7b-instruct-q4_k_m.gguf", 4683073536,
				"509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c"),
		],
	},
	{
		"id": "qwen3.5-9b-coder", "quant": Q4, "dir": "qwen3.5-9b", "role": CODER, "name": "Qwen3.5 9B, used for coding",
		"small": False, "thinking": True, "memoryGb": 7.0, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _Q35_9B[0], "files": [_Q35_9B_MODEL],
	},
	{
		# memoryGb: the file (8.4 GB), what 8192 tokens of context take (40 layers, 8 key and value heads of 128:
		# 1.25 GB) and the engine's working memory.
		"id": "qwen3-14b", "quant": Q4, "dir": "qwen3-14b", "role": CODER, "name": "Qwen3 14B", "small": False,
		"edge": True, "thinking": True, "memoryGb": 10.4, "maxContext": 32768, "licence": "Apache 2.0",
		"source": _Q3_14B[0],
		"files": [
			_file(*_Q3_14B, "Qwen3-14B-Q4_K_M.gguf", 9001752960,
				"500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0"),
		],
	},
]


def _inQuant(entry, quant, modelFile):
	"""The entry of a model in another quant: the same folder and projector, another weights file, more memory."""
	old = next(f for f in entry["files"] if f["kind"] == "model")
	head, sep, tail = entry["name"].partition(", ")
	return dict(
		entry, id=f"{entry['id']}-{quant.replace('_', '').lower()[:3]}", quant=quant, name=f"{head} {quant}{sep}{tail}",
		memoryGb=round(entry["memoryGb"] + (modelFile["size"] - old["size"]) / 2 ** 30 + 0.05, 1),
		files=[modelFile] + [f for f in entry["files"] if f["kind"] != "model"])


CATALOG = []
for _entry in _Q4_ENTRIES:
	CATALOG.append(_entry)
	CATALOG.append(_inQuant(_entry, Q6, _Q6_FILES[_entry["id"]]))
del _entry

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
LIST_UPDATED = "2026-11-19"
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
_QUANT = re.compile(r"^[A-Z][A-Z0-9_]{1,11}$")


def _namesQuant(fileName, quant):
	"""Whether a file's name says it is in this quant, as a part of the name of its own: Q6_K is not Q6_K_XL."""
	return re.search(rf"(^|[-_.]){re.escape(quant)}([-.]|$)", fileName.upper()) is not None


def quantOf(entry):
	"""The quant of a model's weights file: what its entry says, else what the file's name says, else ""."""
	if not entry:
		return ""
	if entry.get("quant"):
		return entry["quant"]
	for f in entry.get("files", ()):
		if f["kind"] == "model":
			for quant in QUANTS:
				if _namesQuant(f["name"], quant):
					return quant
	return ""


def isEdge(entry):
	"""Whether a model is kept for hard cases (the entry's edge), and so never suggested or picked for everyday use."""
	return bool(entry) and entry.get("edge") is True


def _modelKey(entry):
	return (entry["role"], entry["dir"] or entry["id"])


def variants(entries, entry):
	"""The entries of one model for one role, one for each quant it is offered in, in the order of QUANTS."""
	if entry is None:
		return []
	found = [e for e in entries if e is not None and _modelKey(e) == _modelKey(entry)]
	order = lambda e: QUANTS.index(quantOf(e)) if quantOf(e) in QUANTS else len(QUANTS)  # noqa: E731
	return sorted(found, key=order) or [entry]


def variant(entries, entry, quant):
	"""The entry of the same model in this quant, or None."""
	return next((e for e in variants(entries, entry) if quantOf(e) == quant), None)


def models(entries):
	"""Every model once, in the order of the list, whatever quants it is offered in: the first entry of each."""
	found, seen = [], set()
	for entry in entries:
		key = None if entry is None else _modelKey(entry)
		if key not in seen:
			seen.add(key)
			found.append(entry)
	return found


def modelName(entry):
	"""A model's name without its quant, as the user chooses the model."""
	quant = quantOf(entry)
	return entry["name"].replace(f" {quant}", "") if quant else entry["name"]


def displayName(entry):
	"""A model's name with its quant, as it is said when one file of it is meant: Qwen3.5 2B Q6_K."""
	quant, name = quantOf(entry), entry["name"]
	if not quant or quant in name:
		return name
	head, sep, tail = name.partition(", ")
	return f"{head} {quant}{sep}{tail}"


def suggestedQuant(entry):
	"""The quant suggested first for a model: DEFAULT_QUANT, unless measuring showed another clearly better."""
	if entry is None:
		return DEFAULT_QUANT
	first = variant(CATALOG, entry, DEFAULT_QUANT)
	return SUGGESTED_QUANTS.get(first["id"] if first else "", DEFAULT_QUANT)


def storeKey(entry):
	"""What a model's files on the disk are known by: its folder, with the quant for any but DEFAULT_QUANT."""
	if not entry.get("dir"):
		return entry["id"]
	quant = quantOf(entry)
	return entry["dir"] if quant in ("", DEFAULT_QUANT) else f"{entry['dir']}@{quant}"


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
	quant = raw.get("quant", "")
	_need(quant == "" or (isinstance(quant, str) and _QUANT.match(quant)), "the quant is not a quant's name")
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
	_need(not quant or any(_namesQuant(f["name"], quant) for f in clean if f["kind"] == "model"),
		"the quant is not the model file's")
	entry = {
		"id": ident, "dir": folder, "role": raw["role"], "name": name, "small": bool(raw.get("small")),
		"thinking": bool(raw.get("thinking")), "memoryGb": float(memory), "maxContext": context, "licence": LICENCE,
		"source": source, "files": clean,
	}
	if raw.get("suggest") is False:
		entry["suggest"] = False
	if raw.get("edge") is True:
		entry["edge"] = True
	if needs:
		entry["minVersion"] = needs
	if quant:
		entry["quant"] = quant
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

	def _rows(self):
		"""The models that can be on the disk: one for each folder and quant, as dictionaries with key, dir,
		entries, own (the names of the files only this quant uses) and shared (the files every quant of the folder
		uses, such as the vision projector)."""
		everything = self.all()
		folders = []
		for entry in everything:
			if entry["dir"] not in folders:
				folders.append(entry["dir"])
		rows = []
		for folder in folders:
			groups = []
			for entry in everything:
				if entry["dir"] != folder:
					continue
				group = next((g for g in groups if g[0] == quantOf(entry)), None)
				if group is None:
					groups.append((quantOf(entry), [entry]))
				else:
					group[1].append(entry)
			names = [{f["name"] for e in members for f in e["files"]} for _q, members in groups]
			shared = set.intersection(*names) if len(names) > 1 else set()
			for (quant, members), owned in zip(groups, names):
				rows.append({
					"key": storeKey(members[0]), "dir": folder, "entries": members,
					"own": sorted(owned - shared), "shared": sorted(shared),
				})
		return rows

	def _onDisk(self, folder, names):
		"""(bytes, whether any of it is an unfinished download) of these files of a folder."""
		size, partial = 0, False
		for name in names:
			for path, unfinished in ((os.path.join(self.modelsDir, folder, name), False),
					(os.path.join(self.modelsDir, folder, name + ".part"), True)):
				try:
					size += os.path.getsize(path)
					partial = partial or unfinished
				except OSError:
					pass
		return size, partial

	def stored(self):
		"""The models on this computer's disk, one for each folder and quant, as dictionaries:
		key (what to pass to removeStored), name, bytes, roles (what it can be used for now), ids (the catalog
		entries that are complete), and partial (a download that was not finished).
		One file can serve two roles: Qwen3.5 4B with its projector is a vision model and a coder model. A file
		the quants of a folder share, the vision projector, is counted with the first of them on the disk."""
		found = []
		byFolder = {}
		for row in self._rows():
			byFolder.setdefault(row["dir"], []).append((row,) + self._onDisk(row["dir"], row["own"]))
		for folder, rows in byFolder.items():
			sharedSize, sharedPartial = self._onDisk(folder, rows[0][0]["shared"])
			present = [r for r in rows if r[1]] or (rows[:1] if sharedSize else [])
			for at, (row, size, partial) in enumerate(present):
				if at == 0:
					size, partial = size + sharedSize, partial or sharedPartial
				complete = [e for e in row["entries"] if self.isInstalled(e)]
				found.append({
					"key": row["key"], "name": displayName(row["entries"][0]), "bytes": size,
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

	def freedBy(self, keys):
		"""How many bytes removing these stored models would free: a shared file only when no quant of its
		folder is left."""
		keys = set(keys)
		freed = sum(m["bytes"] for m in self.stored() if m["key"] == VISIONMATE_ID and m["key"] in keys)
		byFolder = {}
		for row in self._rows():
			byFolder.setdefault(row["dir"], []).append(row)
		for folder, rows in byFolder.items():
			if not any(r["key"] in keys for r in rows):
				continue
			freed += sum(self._onDisk(folder, r["own"])[0] for r in rows if r["key"] in keys)
			if not any(self._onDisk(folder, r["own"])[0] for r in rows if r["key"] not in keys):
				freed += self._onDisk(folder, rows[0]["shared"])[0]
		return freed

	def removeStored(self, key):
		"""Delete one stored model: the files of its quant, and the files its folder's quants share once no other
		quant is left. Returns the bytes freed. Raises OSError if a file cannot be deleted, for example because
		an engine still has it open."""
		if key == VISIONMATE_ID:
			paths = list(self._visionMatePaths() or ()) + [os.path.join(self._visionMateDir or "", "data.json")]
			folder = None
		else:
			rows = self._rows()
			row = next((r for r in rows if r["key"] == key), None)
			if row is None:
				return 0
			folder = os.path.join(self.modelsDir, row["dir"])
			names = list(row["own"])
			others = [r for r in rows if r["dir"] == row["dir"] and r["key"] != key]
			if not any(self._onDisk(row["dir"], r["own"])[0] for r in others):
				names += row["shared"]
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
	"""The catalog id to offer first: the larger model only where it clearly fits, in the suggested quant. Only
	built-in models are suggested, since those are the ones that were tried, and never the very smallest."""
	roomy = (dedicatedMb or 0) >= 11000 or (memoryGb or 0) >= 30
	choices = [e for e in CATALOG if e["role"] == role and e.get("suggest", True) and not isEdge(e)
		and quantOf(e) == DEFAULT_QUANT]
	chosen = next((e for e in choices if e["small"] != roomy), choices[0])
	# The quant too is only a suggestion: Q4_K_M, unless measuring showed another clearly better for this model.
	return (variant(CATALOG, chosen, suggestedQuant(chosen)) or chosen)["id"]
