# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the models VisionClaw can use, which of them are on this computer, and downloading them.
# Every download is pinned to one revision and checked against its SHA-256. No NVDA dependencies.

import os

from .. import net

VISION, CODER = "vision", "coder"
_HF = "https://huggingface.co/{repo}/resolve/{rev}/{name}"


def _file(repo, rev, name, size, sha256, kind="model"):
	return {"kind": kind, "name": name, "size": size, "sha256": sha256, "url": _HF.format(repo=repo, rev=rev, name=name)}


_Q35_2B = ("unsloth/Qwen3.5-2B-GGUF", "f6d5376be1edb4d416d56da11e5397a961aca8ae")
_Q35_4B = ("unsloth/Qwen3.5-4B-GGUF", "e87f176479d0855a907a41277aca2f8ee7a09523")
_Q35_9B = ("unsloth/Qwen3.5-9B-GGUF", "3885219b6810b007914f3a7950a8d1b469d598a5")
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
CATALOG = [
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


def entrySize(entry):
	return sum(f["size"] for f in entry["files"])


class Catalog:
	"""modelsDir holds one folder per downloaded model. visionMateDir is VisionMate's data folder, or None."""

	def __init__(self, modelsDir, visionMateDir=None):
		self.modelsDir = modelsDir
		self._visionMateDir = visionMateDir

	def _visionMatePaths(self):
		if not self._visionMateDir:
			return None
		core = os.path.join(self._visionMateDir, "core.bin")
		vision = os.path.join(self._visionMateDir, "vision.bin")
		return (core, vision) if os.path.isfile(core) and os.path.isfile(vision) else None

	def entries(self, role=None):
		"""Every model that can be chosen, the ones to download first."""
		found = [e for e in CATALOG if role in (None, e["role"])]
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
		for entry in CATALOG:
			if entry["dir"] in seen:
				continue
			seen.append(entry["dir"])
			family = [e for e in CATALOG if e["dir"] == entry["dir"]]
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
			names = {f["name"] for e in CATALOG if e["dir"] == key for f in e["files"]}
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
		for other in CATALOG:
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
	"""The catalog id to offer first: the larger model only where it clearly fits."""
	roomy = (dedicatedMb or 0) >= 11000 or (memoryGb or 0) >= 30
	for entry in CATALOG:
		if entry["role"] == role and entry["small"] != roomy:
			return entry["id"]
	return next(e["id"] for e in CATALOG if e["role"] == role)
