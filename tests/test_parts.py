# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Checks the building blocks: the model catalog and resumable verified downloads, forgiving matching,
the check that generated add-ons must pass, writing and repairing an add-on, storing and packaging one,
and the knowledge base."""
import copy
import hashlib
import json
import os
import re
import tempfile
import threading
import zipfile

import harness  # noqa: F401
import rangeserver
from visionClaw import net
from visionClaw.claw import catalog, changes, drivers, match, microaddons, policy, web
from visionClaw.claw import task as taskModule
from visionClaw.claw.catalog import CODER, VISION
from visionClaw.claw.knowledge import Knowledge
from visionClaw.claw.llm import plainSpeech
from visionClaw.claw.tools import ToolError

# --- The catalog ---

ids = [e["id"] for e in catalog.CATALOG]
assert len(ids) == len(set(ids))
for entry in catalog.CATALOG:
	assert entry["role"] in (VISION, CODER) and entry["files"]
	kinds = [f["kind"] for f in entry["files"]]
	assert kinds.count("model") == 1 and (entry["role"] == CODER or kinds.count("mmproj") == 1), entry["id"]
	for f in entry["files"]:
		assert f["url"].startswith("https://huggingface.co/") and "/resolve/" in f["url"] and "/main/" not in f["url"]
		assert len(f["sha256"]) == 64 and f["size"] > 100 * 2 ** 20
# Every model is offered, whatever the computer: the computer only changes which one is suggested.
assert catalog.recommend(VISION, 8, 0) == "qwen3.5-2b" and catalog.recommend(CODER, 8, 0) == "qwen2.5-coder-1.5b"
assert catalog.recommend(VISION, 64, 0) == "qwen3.5-4b" and catalog.recommend(CODER, 16, 12000) == "qwen3.5-4b-coder"
assert {"qwen2.5-coder-7b", "qwen3.5-9b"} <= set(ids)
# Several small sizes of each kind are offered, the smallest first; the very smallest are never the suggestion.
assert [e["id"] for e in catalog.CATALOG if e["role"] == VISION] == [
	"qwen3.5-0.8b", "qwen3.5-0.8b-q6k", "qwen3.5-2b", "qwen3.5-2b-q6k", "qwen3.5-4b", "qwen3.5-4b-q6k", "qwen3.5-9b",
	"qwen3.5-9b-q6k"]
assert [e["id"] for e in catalog.CATALOG if e["role"] == CODER][:4] == [
	"qwen2.5-coder-0.5b", "qwen2.5-coder-0.5b-q6k", "qwen2.5-coder-1.5b", "qwen2.5-coder-1.5b-q6k"]
for memory, card in ((2, 0), (8, 0), (16, 4000)):
	assert catalog.recommend(VISION, memory, card) == "qwen3.5-2b" and catalog.recommend(CODER, memory, card) == "qwen2.5-coder-1.5b"

# Downloading: a model of two files from a local server, the first download cut off half way.
served = tempfile.mkdtemp()
blobs = {"model.gguf": os.urandom(3 * 2 ** 20 + 123), "mmproj.gguf": os.urandom(2 ** 20)}
for name, data in blobs.items():
	with open(os.path.join(served, name), "wb") as f:
		f.write(data)
base, server = rangeserver.serve(served, failAfterBytes=2 ** 20 + 5)
entry = {
	"id": "test", "dir": "test", "role": VISION, "name": "Test", "small": True, "thinking": False,
	"memoryGb": 1, "maxContext": 4096,
	"files": [
		{"kind": kind, "name": name, "size": len(blobs[name]), "sha256": hashlib.sha256(blobs[name]).hexdigest(),
			"url": f"{base}/{name}"}
		for kind, name in (("model", "model.gguf"), ("mmproj", "mmproj.gguf"))
	],
}
models = catalog.Catalog(tempfile.mkdtemp())
total = catalog.entrySize(entry)
assert not models.isInstalled(entry) and models.missingBytes(entry) == total
try:
	models.download(entry)
	raise AssertionError("the cut-off download should have failed")
except OSError:
	pass
assert 0 < models.missingBytes(entry) < total  # what arrived is kept
progress = []
models.download(entry, lambda done, size: progress.append((done, size)))
assert models.isInstalled(entry) and models.missingBytes(entry) == 0
assert progress[-1] == (total, total) and all(a[0] <= b[0] for a, b in zip(progress, progress[1:]))
model, projector = models.paths(entry)
assert open(model, "rb").read() == blobs["model.gguf"] and open(projector, "rb").read() == blobs["mmproj.gguf"]
# A damaged file is refused.
bad = dict(entry, id="bad", dir="bad", files=[dict(entry["files"][1], sha256="0" * 64)])
try:
	models.download(bad)
	raise AssertionError("a damaged download should have been refused")
except ValueError:
	pass
assert not models.isInstalled(bad)
# Cancelling stops a download.
stop = threading.Event()
stop.set()
other = dict(entry, id="other", dir="other")
try:
	models.download(other, cancel=stop)
	raise AssertionError("a cancelled download should have stopped")
except net.Cancelled:
	pass
# A model that shares its file with another is not downloaded twice, and removing one keeps the shared file.
coder = dict(entry, id="test-coder", role=CODER, files=entry["files"][:1])
assert models.isInstalled(coder) and models.missingBytes(coder) == 0
server.shutdown()
# VisionMate's vision data, where it exists, is offered without a download.
folder = tempfile.mkdtemp()
assert catalog.VISIONMATE_ID not in [e["id"] for e in catalog.Catalog(folder, folder).entries(VISION)]
for name in ("core.bin", "vision.bin"):
	open(os.path.join(folder, name), "wb").close()
reuse = catalog.Catalog(folder, folder)
assert reuse.selected(VISION)["id"] == catalog.VISIONMATE_ID and reuse.paths(reuse.selected(VISION))[0].endswith("core.bin")

# --- The models on the disk: what is stored, what it can be used for, and removing it ---

real = list(catalog.CATALOG)
try:
	def small(ident, folder, role, files):
		return {"id": ident, "dir": folder, "role": role, "name": ident.upper(), "small": True, "thinking": False,
			"memoryGb": 1, "maxContext": 4096,
			"files": [{"kind": kind, "name": name, "size": size, "sha256": "0" * 64, "url": ""} for kind, name, size in files]}
	catalog.CATALOG[:] = [
		small("big", "big", VISION, [("model", "big.gguf", 30), ("mmproj", "big-eyes.gguf", 10)]),
		small("tiny", "tiny", CODER, [("model", "tiny.gguf", 5)]),
		small("big-coder", "big", CODER, [("model", "big.gguf", 30)]),
		small("other", "other", CODER, [("model", "other.gguf", 7)]),
	]
	folder = tempfile.mkdtemp()
	disk = catalog.Catalog(folder)
	assert disk.stored() == []

	def put(path, size):
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "wb") as f:
			f.write(b"x" * size)
	put(os.path.join(folder, "big", "big.gguf"), 30)
	put(os.path.join(folder, "tiny", "tiny.gguf"), 5)
	put(os.path.join(folder, "other", "other.gguf.part"), 3)
	found = {m["key"]: m for m in disk.stored()}
	# One folder is one stored model, whatever it can be used for. Without its projector the big model can
	# only be used for coding; a download that was not finished is shown as such.
	assert list(found) == ["big", "tiny", "other"], list(found)
	assert found["big"]["roles"] == [CODER] and found["big"]["ids"] == ["big-coder"] and found["big"]["bytes"] == 30
	assert found["tiny"]["roles"] == [CODER] and not found["tiny"]["partial"]
	assert found["other"]["roles"] == [] and found["other"]["partial"] and found["other"]["bytes"] == 3
	put(os.path.join(folder, "big", "big-eyes.gguf"), 10)
	big = disk.stored()[0]
	assert big["roles"] == [VISION, CODER] and big["ids"] == ["big", "big-coder"] and big["bytes"] == 40
	# Removing one leaves the others; removing frees what was there, the unfinished download included.
	assert disk.removeStored("tiny") == 5 and not os.path.exists(os.path.join(folder, "tiny"))
	assert disk.removeStored("other") == 3 and disk.removeStored("other") == 0
	assert [m["key"] for m in disk.stored()] == ["big"] and disk.selected(VISION)["id"] == "big"
	assert disk.removeStored("big") == 40 and disk.stored() == [] and disk.selected(VISION) is None
	# VisionMate's vision data is listed too, and can be removed like the others.
	mate = tempfile.mkdtemp()
	for name, size in (("core.bin", 20), ("vision.bin", 8), ("data.json", 2), ("NOTICE.txt", 4)):
		put(os.path.join(mate, name), size)
	withMate = catalog.Catalog(folder, mate)
	assert [(m["key"], m["bytes"], m["roles"]) for m in withMate.stored()] == [(catalog.VISIONMATE_ID, 28, [VISION])]
	assert withMate.removeStored(catalog.VISIONMATE_ID) == 30 and withMate.stored() == []
	assert os.path.exists(os.path.join(mate, "NOTICE.txt"))
finally:
	catalog.CATALOG[:] = real

# --- Quants: every model in Q4_K_M and Q6_K, the user's choice (the owner, 2026-11-18) ---

assert catalog.QUANTS == ("Q4_K_M", "Q6_K") and catalog.DEFAULT_QUANT == "Q4_K_M"
fours = [e for e in catalog.CATALOG if catalog.quantOf(e) == catalog.Q4]
assert len(fours) == 10 and len(catalog.CATALOG) == 20
for four in fours:
	six = catalog.variant(catalog.CATALOG, four, catalog.Q6)
	# Every model, the 7B and 9B included, can be had as Q6_K: from the same publisher, at the same revision,
	# in the same folder, with the same vision projector, so that the projector is downloaded once.
	assert six is not None and six["id"] == four["id"] + "-q6k", four["id"]
	assert (six["role"], six["dir"], six["source"], six["thinking"], six["maxContext"], six.get("suggest", True)) == (
		four["role"], four["dir"], four["source"], four["thinking"], four["maxContext"], four.get("suggest", True))
	fourModel, sixModel = (next(f for f in e["files"] if f["kind"] == "model") for e in (four, six))
	assert sixModel["url"].rsplit("/", 1)[0] == fourModel["url"].rsplit("/", 1)[0], four["id"]
	assert catalog._namesQuant(sixModel["name"], "Q6_K") and sixModel["size"] > fourModel["size"]
	assert [f for f in six["files"] if f["kind"] == "mmproj"] == [f for f in four["files"] if f["kind"] == "mmproj"]
	assert six["memoryGb"] > four["memoryGb"]
	assert catalog.modelName(six) == catalog.modelName(four) == four["name"]
	assert catalog.displayName(four).startswith(four["name"].split(",")[0] + " Q4_K_M")
	assert catalog.variants(catalog.CATALOG, six) == [four, six] and catalog.storeKey(four) == four["dir"]
	assert catalog.storeKey(six) == four["dir"] + "@Q6_K"
assert catalog.displayName(catalog.CATALOG[-3]) == "Qwen3.5 9B Q6_K, used for coding"
# The model for hard cases (the owner, 2026-11-19: "capped at 9b parameter models, with edge cases using a 14b parameter
# model"): Qwen3 14B, Qwen's own files, in both quants like every model, for the coder's job, never suggested, and
# every everyday model is 9B or smaller.
edges = [e for e in catalog.CATALOG if catalog.isEdge(e)]
assert [e["id"] for e in edges] == ["qwen3-14b", "qwen3-14b-q6k"] and [catalog.quantOf(e) for e in edges] == ["Q4_K_M", "Q6_K"]
assert all(e["role"] == CODER and e["source"] == "Qwen/Qwen3-14B-GGUF" and e["licence"] == "Apache 2.0" for e in edges)
assert all(catalog.checkEntry(e)["edge"] is True for e in edges)
assert catalog.displayName(edges[1]) == "Qwen3 14B Q6_K" and edges[0]["memoryGb"] > 9 and edges[1]["memoryGb"] > edges[0]["memoryGb"]
assert all(float(re.search(r"(\d+(?:\.\d+)?)B", e["name"]).group(1)) <= 9 for e in catalog.CATALOG if not catalog.isEdge(e))
for role in (VISION, CODER):
	for memory, card in ((8, 0), (31, 8192), (64, 24576), (128, 49152)):
		assert not catalog.isEdge(next(e for e in catalog.CATALOG if e["id"] == catalog.recommend(role, memory, card))), (role, memory, card)
# A list that says nothing of edge has none; a fetched entry keeps it only as True.
assert "edge" not in catalog.checkEntry(dict(edges[0], edge="yes")) and "edge" not in catalog.checkEntry(fours[0])
assert catalog.models(catalog.CATALOG) == fours
# What a file is, when an older list does not say: from its name, where Q6_K_XL is not Q6_K.
assert catalog.quantOf({"files": [{"kind": "model", "name": "qwen2.5-coder-1.5b-instruct-q6_k.gguf"}]}) == "Q6_K"
assert catalog.quantOf({"files": [{"kind": "model", "name": "Qwen3.5-2B-UD-Q6_K_XL.gguf"}]}) == ""
assert catalog.quantOf(None) == ""
# The suggestion stays Q4_K_M, whatever the computer; a model measured better in Q6_K would be suggested so.
assert catalog.recommend(VISION, 64, 0) == "qwen3.5-4b" and catalog.suggestedQuant(catalog.CATALOG[3]) == "Q4_K_M"
catalog.SUGGESTED_QUANTS["qwen2.5-coder-1.5b"] = "Q6_K"
try:
	assert catalog.recommend(CODER, 8, 0) == "qwen2.5-coder-1.5b-q6k" and catalog.recommend(VISION, 8, 0) == "qwen3.5-2b"
finally:
	del catalog.SUGGESTED_QUANTS["qwen2.5-coder-1.5b"]
# A quant a list names must be its file's.
sixEntry = copy.deepcopy(catalog.variant(catalog.CATALOG, catalog.CATALOG[2], catalog.Q6))
assert catalog.checkEntry(sixEntry)["quant"] == "Q6_K"
for wrong in ("Q4_K_M", "q6_k", "Q6", "../x", 6):
	try:
		catalog.checkEntry(dict(sixEntry, quant=wrong))
		raise AssertionError(wrong)
	except ValueError:
		pass
assert "quant" not in catalog.checkEntry(dict(sixEntry, quant=""))

# The user's choice is kept as the entry's id. An older setting, made before there were quants, names the
# Q4_K_M entry and goes on meaning it; a Q6_K choice is used when it is on the disk.


class Everything(catalog.Catalog):
	def isInstalled(self, entry):
		return entry["id"] != catalog.VISIONMATE_ID


from visionClaw.claw import runtime  # noqa: E402
everything = Everything(tempfile.mkdtemp())
for setting, wanted in (("qwen3.5-2b", "Q4_K_M"), ("qwen3.5-2b-q6k", "Q6_K"), ("qwen3.5-9b-q6k", "Q6_K")):
	chosen = runtime.ModelRuntime("engine", everything, lambda: {"visionModel": setting}).entry(VISION)
	assert chosen["id"] == setting and catalog.quantOf(chosen) == wanted, setting
coderChosen = runtime.ModelRuntime("engine", everything, lambda: {"coderModel": "qwen2.5-coder-7b-q6k"}).entry(CODER)
assert coderChosen["id"] == "qwen2.5-coder-7b-q6k" and coderChosen["files"][0]["name"].endswith("q6_k.gguf")
# The same model in two quants is two files: never one model doing both jobs by mistake.
mixed = runtime.ModelRuntime("engine", everything, lambda: {"visionModel": "qwen3.5-4b", "coderModel": "qwen3.5-4b-coder-q6k"})
assert not mixed.oneModel()
same = runtime.ModelRuntime("engine", everything, lambda: {"visionModel": "qwen3.5-4b-q6k", "coderModel": "qwen3.5-4b-coder-q6k"})
assert same.oneModel()

# On the disk: a folder holding both quants is two stored models. The projector they share is downloaded once,
# counted once, and removed only with the last of them.
real = list(catalog.CATALOG)
try:
	def tiny(ident, quant, files):
		return {"id": ident, "dir": "pair", "role": VISION, "name": "Qwen Pair", "small": True, "thinking": False,
			"memoryGb": 1, "maxContext": 4096, "quant": quant,
			"files": [{"kind": kind, "name": name, "size": size, "sha256": "0" * 64, "url": ""} for kind, name, size in files]}
	catalog.CATALOG[:] = [
		tiny("pair", "Q4_K_M", [("model", "pair-Q4_K_M.gguf", 20), ("mmproj", "eyes.gguf", 6)]),
		tiny("pair-q6k", "Q6_K", [("model", "pair-Q6_K.gguf", 30), ("mmproj", "eyes.gguf", 6)]),
	]
	folder = tempfile.mkdtemp()
	disk = catalog.Catalog(folder)

	def put(name, size):
		os.makedirs(os.path.join(folder, "pair"), exist_ok=True)
		with open(os.path.join(folder, "pair", name), "wb") as f:
			f.write(b"x" * size)
	put("pair-Q4_K_M.gguf", 20)
	put("eyes.gguf", 6)
	four, six = catalog.CATALOG
	# Switching to Q6_K downloads only its own file: the projector is already there.
	assert disk.isInstalled(four) and disk.missingBytes(six) == 30
	assert [(m["key"], m["name"], m["bytes"]) for m in disk.stored()] == [("pair", "Qwen Pair Q4_K_M", 26)]
	put("pair-Q6_K.gguf", 30)
	found = disk.stored()
	assert [(m["key"], m["name"], m["bytes"], m["ids"]) for m in found] == [
		("pair", "Qwen Pair Q4_K_M", 26, ["pair"]), ("pair@Q6_K", "Qwen Pair Q6_K", 30, ["pair-q6k"])], found
	assert disk.freedBy(["pair"]) == 20 and disk.freedBy(["pair@Q6_K"]) == 30 and disk.freedBy(["pair", "pair@Q6_K"]) == 56
	# Removing the quant no longer used keeps the projector for the other.
	assert disk.removeStored("pair") == 20 and disk.isInstalled(six) and not disk.isInstalled(four)
	assert [(m["key"], m["bytes"]) for m in disk.stored()] == [("pair@Q6_K", 36)]
	assert disk.freedBy(["pair@Q6_K"]) == 36
	assert disk.removeStored("pair@Q6_K") == 36 and disk.stored() == [] and not os.path.exists(os.path.join(folder, "pair"))
finally:
	catalog.CATALOG[:] = real

# --- Newer models: the list the user can have fetched ---

# Every built-in model follows the rules a fetched one must follow, and the published list is the catalog.
for entry in catalog.CATALOG:
	assert catalog.checkEntry(copy.deepcopy(entry)) == entry, entry["id"]
with open(os.path.join(harness.ROOT, "models.json"), encoding="utf-8") as f:
	published = json.load(f)
assert published == catalog.publishedList(), "models.json differs from the catalog: run python tools/write_models_list.py"
assert published["updated"] == catalog.LIST_UPDATED and catalog.LIST_URL.startswith(
	"https://raw.githubusercontent.com/joshknnd1982/visionclaw/main/")
# A VisionClaw that has every model of the list built in is offered nothing new by it.
assert catalog.readList(published, "0.4.0") == ([], 0, 0, catalog.LIST_UPDATED)


def newer(**changes):
	"""A model that is not built in, as a later list might carry it."""
	repo, rev = "Qwen/Qwen9-1B-GGUF", "a" * 40
	entry = {
		"id": "qwen9-1b", "dir": "qwen9-1b", "role": VISION, "name": "Qwen9 1B", "small": True, "thinking": True,
		"memoryGb": 1.5, "maxContext": 16384, "licence": "Apache 2.0", "source": repo,
		"files": [
			{"kind": "model", "name": "Qwen9-1B-Q4_K_M.gguf", "size": 600 * 2 ** 20, "sha256": "1" * 64,
				"url": f"https://huggingface.co/{repo}/resolve/{rev}/Qwen9-1B-Q4_K_M.gguf"},
			{"kind": "mmproj", "name": "mmproj-F16.gguf", "size": 200 * 2 ** 20, "sha256": "2" * 64,
				"url": f"https://huggingface.co/{repo}/resolve/{rev}/mmproj-F16.gguf"},
		],
	}
	entry.update(changes)
	return entry


def withFile(index, **changes):
	entry = newer()
	entry["files"][index].update(changes)
	return entry


good = newer()
assert catalog.checkEntry(dict(good, extra="dropped", suggest=False)) == dict(good, suggest=False)
later = dict(published, updated="2027-03-01", models=published["models"] + [good, newer(id="qwen9-9b", dir="qwen9-9b", minVersion="9.0")])
assert catalog.readList(later, "0.4.0") == ([good], 1, 0, "2027-03-01")
assert catalog.readList(later, "9.1")[1] == 0 and len(catalog.readList(later, "9.1")[0]) == 2
assert catalog.versionTuple("0.4.0") < catalog.versionTuple("0.10") and catalog.versionTuple("nonsense") == ()
# What the list may not do. Each of these is refused, and the rest of the list is still used.
base = "https://huggingface.co/Qwen/Qwen9-1B-GGUF/resolve/" + "a" * 40
for why, bad in (
	("another server", withFile(0, url="https://example.com/Qwen/Qwen9-1B-GGUF/resolve/" + "a" * 40 + "/Qwen9-1B-Q4_K_M.gguf")),
	("no secure connection", withFile(0, url=base.replace("https", "http") + "/Qwen9-1B-Q4_K_M.gguf")),
	("not pinned to a revision", withFile(0, url=base.replace("a" * 40, "main") + "/Qwen9-1B-Q4_K_M.gguf")),
	("another file than it says", withFile(0, url=base + "/other.gguf")),
	("another repository than it says", withFile(0, url=base.replace("Qwen9-1B-GGUF", "Else-GGUF") + "/Qwen9-1B-Q4_K_M.gguf")),
	("an address with more in it", withFile(0, url=base + "/Qwen9-1B-Q4_K_M.gguf?download=true")),
	("no checksum", withFile(0, sha256="")),
	("a short checksum", withFile(1, sha256="abc")),
	("no size", withFile(0, size=0)),
	("a size that is not a number", withFile(0, size="600")),
	("a file that is not a model file", withFile(0, name="setup.exe", url=base + "/setup.exe")),
	("a path in a file name", withFile(0, name="..\\evil.gguf")),
	("a path as the folder", newer(dir="../../startup")),
	("an unknown publisher", newer(source="someone/Qwen9-1B-GGUF")),
	("not a Qwen model", newer(id="llama-9", dir="llama-9", name="Llama 9")),
	("another licence", newer(licence="Research only")),
	("a vision model without its projector", dict(newer(), files=newer()["files"][:1])),
	("two model files", dict(newer(), files=[newer()["files"][0], dict(newer()["files"][0], name="b.gguf", url=base + "/b.gguf")])),
	("an unknown role", newer(role="admin")),
	("a silly memory figure", newer(memoryGb=9999)),
	("a version that is not one", newer(minVersion="latest")),
	("not an entry at all", "qwen9-1b"),
	# A file of the same name in a built-in model's folder must be that same file.
	("a different file in a built-in folder", newer(id="qwen3.5-2b-x", dir="qwen3.5-2b", source="unsloth/Qwen3.5-2B-GGUF", files=[
		dict(catalog.CATALOG[1]["files"][0], sha256="3" * 64), catalog.CATALOG[1]["files"][1]])),
):
	entries, tooNew, refused, _updated = catalog.readList({"format": 1, "models": [bad, good]}, "0.4.0")
	assert entries == [good] and refused == 1 and tooNew == 0, why
for wrong in ({"format": 2, "models": []}, {"format": 1}, [], "list", {"format": 1, "models": "x"}):
	try:
		catalog.readList(wrong, "0.4.0")
		raise AssertionError(wrong)
	except ValueError as e:
		assert "cannot read" in str(e) or "can read" in str(e), e

# Looking: only the one fixed address is read; what was found is kept, offered beside the built-in models,
# and checked again when it is read from the disk.
folder = tempfile.mkdtemp()
asked = []
shelf = catalog.Catalog(folder)
assert shelf.offered() == [] and len(shelf.entries(VISION)) == 8
found = shelf.look("0.4.0", lambda url: asked.append(url) or copy.deepcopy(later))
assert asked == [catalog.LIST_URL]
assert found == {"new": ["Qwen9 1B"], "tooNew": 1, "refused": 0, "updated": "2027-03-01"}, found
assert [e["id"] for e in catalog.models(shelf.entries(VISION))] == [
	"qwen3.5-0.8b", "qwen3.5-2b", "qwen3.5-4b", "qwen3.5-9b", "qwen9-1b"]
assert shelf.get("qwen9-1b") == good and catalog.recommend(VISION, 8, 0) == "qwen3.5-2b"
assert shelf.look("0.4.0", lambda url: copy.deepcopy(later))["new"] == []  # nothing is new the second time
again = catalog.Catalog(folder)
assert again.get("qwen9-1b") == good
# Its files are found on the disk and removed like any model's.
os.makedirs(os.path.join(folder, "qwen9-1b"))
with open(os.path.join(folder, "qwen9-1b", "Qwen9-1B-Q4_K_M.gguf.part"), "wb") as f:
	f.write(b"x" * 9)
assert [(m["key"], m["bytes"], m["partial"]) for m in again.stored()] == [("qwen9-1b", 9, True)]
assert again.removeStored("qwen9-1b") == 9 and not os.path.exists(os.path.join(folder, "qwen9-1b"))
# A saved list that was changed on the disk to point somewhere else is not trusted.
with open(os.path.join(folder, "offered.json"), encoding="utf-8") as f:
	saved = json.load(f)
saved["models"][0]["files"][0]["url"] = "https://example.com/evil.gguf"
with open(os.path.join(folder, "offered.json"), "w", encoding="utf-8") as f:
	json.dump(saved, f)
assert catalog.Catalog(folder).offered() == [] and catalog.Catalog(folder).get("qwen9-1b") is None
# A page that cannot be reached, or a list that cannot be read, changes nothing.
for failure in (OSError("no connection"), ValueError("not a list")):
	def broken(url, failure=failure):
		raise failure
	try:
		shelf.look("0.4.0", broken)
		raise AssertionError("must not pass")
	except (OSError, ValueError):
		assert shelf.get("qwen9-1b") == good
# The list is a small file: a longer answer is refused before it is read as a list.
listFile = os.path.join(folder, "list.json")
with open(listFile, "w", encoding="utf-8") as f:
	json.dump(later, f)
address = "file:///" + listFile.replace(os.sep, "/")
assert net.fetchJson(address, limit=catalog.LIST_BYTES) == later
try:
	net.fetchJson(address, limit=100)
	raise AssertionError("a long answer must be refused")
except ValueError as e:
	assert "longer than it may be" in str(e)

# --- Forgiving matching ---

items = ["Space Trader - Main Menu heading", "New Game button", "Load Game button", "Options button", "Quit button"]
assert match.itemIndex("2", items) == 1 and match.itemIndex("item 4.", items) == 3 and match.itemIndex("9", items) is None
assert match.itemIndex("new game", items) == 1 and match.itemIndex("the Quit button", items) == 4
assert match.itemIndex("Optoins", items) == 3 and match.itemIndex("Save", items) is None
assert match.toNumber("80") == 80 and match.toNumber("/80") == 80 and match.toNumber("80%", 50, 0, 100) == 80
assert match.toNumber("+10", 50, 0, 100) == 60 and match.toNumber("-10", 5, 0, 100) == 0
for wrong in ("fast", "250"):
	try:
		match.toNumber(wrong, 50, 0, 100)
		raise AssertionError(wrong)
	except ValueError:
		pass
assert match.toBool("On") is True and match.toBool("disabled") is False and match.toBool("maybe") is None
assert match.toOption("ALL", ["none", "some", "most", "all"]) == "all"
assert match.label("speakTypedWords") == "speak typed words"
assert plainSpeech("Seen:\n- A **game** menu\n- Four buttons") == "Seen: A game menu, Four buttons."

# --- The web: addresses, searches, and the passages of a page that matter ---

assert web.addressIn("please open bbc.co.uk for me") == "bbc.co.uk"
assert web.addressIn("go to https://example.com/a?b=1.") == "https://example.com/a?b=1"
assert web.addressIn("open the BBC website") == ""
assert web.normalizeAddress("bbc.co.uk") == "https://bbc.co.uk" and web.normalizeAddress("http://a.org/x") == "http://a.org/x"
assert web.normalizeAddress("localhost.example:8080/x") == "https://localhost.example:8080/x"
for bad in ("javascript:alert(1)", "file:///c:/windows/system32", "ftp://a.org", "the bbc", "", "data:text/html,x"):
	try:
		web.normalizeAddress(bad)
		raise AssertionError(bad)
	except ValueError:
		pass
assert web.searchWords("Search the web for cheap flights to Rome online.") == "cheap flights to Rome"
assert web.searchWords("look up the weather in Boston") == "the weather in Boston"
assert web.searchWords("google NVDA add-on development") == "NVDA add-on development"
assert web.searchUrl("google", "a b&c") == "https://www.google.com/search?q=a+b%26c"
assert web.searchUrl("nothing", "x").startswith("https://duckduckgo.com/")
assert web.passages("Short page.\n\nTwo lines.", "anything") == "Short page.\nTwo lines."
long = "\n".join(["News today"] + [f"Paragraph {i} talks about football results." for i in range(80)]
	+ ["The library opens at nine and closes at five on weekdays."] + [f"Advert {i} for shoes." for i in range(80)])
found = web.passages(long, "When does the library open?")
assert found.startswith("News today") and "library opens at nine" in found and "..." in found and len(found) <= 1500
assert web.passages(long, "zzzz").startswith("News today") and len(web.passages(long, "zzzz")) <= 1410

# --- What VisionClaw changed, and putting it back ---

log = changes.ChangeLog(os.path.join(tempfile.mkdtemp(), "changes.json"))
assert log.pending() == [] and log.text() == ""
log.add("speech.rate", "speech rate", 50, 60, "50", "60", "speak faster")
log.add("keyboard.speakTypedCharacters", "keyboard speak typed characters", True, False, "on", "off", "no typing echo")
assert [c["setting"] for c in log.pending()] == ["keyboard.speakTypedCharacters", "speech.rate"]  # newest first
assert "Speech rate: from 50 to 60" in log.text() and "Keyboard speak typed characters: from on to off" in log.text()


def known(change):
	return changes.words(change["label"] + " " + change["setting"].replace(".", " "))


assert changes.choose("undo that", log.pending(), known)[0]["setting"] == "keyboard.speakTypedCharacters"
assert changes.choose("put the speech rate back to what it was", log.pending(), known)[0]["setting"] == "speech.rate"
assert changes.choose("restore the voice pitch to what it was before you changed it", log.pending(), known) == (None, "other")
assert changes.choose("undo that", [], known) == (None, "nothing")
assert changes.meant("restore it to what it was before you changed it") == set()
log.markUndone(log.pending()[0])
again = changes.ChangeLog(log._path)  # kept between sessions
assert [c["setting"] for c in again.pending()] == ["speech.rate"] and again.pending()[0]["old"] == 50

# --- Keeping speech and braille alive ---

S, D = drivers.SYNTH, drivers.DISPLAY
assert drivers.judge(S, "espeak", "oneCore", None) == (drivers.FINE, "")
assert drivers.judge(S, "silence", "espeak", None)[0] == drivers.REFUSE
assert drivers.judge(S, "silence", "espeak", "noBraille")[0] == drivers.REFUSE
assert drivers.judge(S, "silence", "espeak", "freedomScientific")[0] == drivers.WARN
assert drivers.judge(D, "noBraille", "espeak", "freedomScientific")[0] == drivers.WARN
assert drivers.judge(D, "noBraille", "silence", "freedomScientific")[0] == drivers.REFUSE
assert drivers.judge(D, "noBraille", None, "freedomScientific")[0] == drivers.REFUSE
assert drivers.judge(D, "freedomScientific", "espeak", "noBraille") == (drivers.FINE, "")
notes = drivers.DriverNotes(os.path.join(tempfile.mkdtemp(), "drivers.json"))
assert notes.warning(S, "sapi5") == "" and drivers.judge(S, "sapi5", "espeak", None, notes)[0] == drivers.FINE
notes.record(S, "sapi5", drivers.FAILED)
notes.record(S, "sapi5", drivers.FAILED)
notes.record(S, "sapi5", drivers.REVERTED)
verdict, why = drivers.judge(S, "sapi5", "espeak", None, notes, "Microsoft Speech API")
assert verdict == drivers.WARN, why
assert why == ("Earlier on this computer, Microsoft Speech API could not be started 2 times and was switched back "
	"once because it was not confirmed to work."), why
notes.record(S, "sapi5", drivers.WORKED)
assert notes.warning(S, "sapi5").endswith("The last time it worked.")
again = drivers.DriverNotes(notes._path)  # kept between sessions
assert again.get(S, "sapi5")["failed"] == 2 and again.problems(S) and not again.problems(D)
assert drivers.judgeVolume(50, None)[0] == drivers.FINE and drivers.judgeVolume(3, None)[0] == drivers.REFUSE
assert drivers.judgeVolume(3, "freedomScientific")[0] == drivers.WARN
assert drivers.kindOf("switch my braille display to Focus") == D and drivers.kindOf("use eSpeak") == S

# --- The check generated add-ons must pass ---

assert microaddons.check(microaddons.TEMPLATE) == []
assert microaddons.gestures(microaddons.TEMPLATE) == [("NVDA+shift+f9", "Says the name of the focused control")]
HEAD = "import globalPluginHandler\nimport ui\n\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n"
for source, expected in (
	("def x(:\n", "Syntax error"),
	("import ui\n", "must define class GlobalPlugin"),
	("import subprocess\n" + HEAD + "\tpass\n", "subprocess is not allowed"),
	("from urllib import request\n" + HEAD + "\tpass\n", "urllib is not allowed"),
	(HEAD + "\tdef script_a(self, gesture):\n\t\topen('x', 'w')\n", "open() is not allowed"),
	(HEAD + "\tdef script_a(self, gesture):\n\t\texec('x')\n", "exec() is not allowed"),
	("import os\n" + HEAD + "\tdef script_a(self, gesture):\n\t\tos.remove('x')\n", "os.remove() is not allowed"),
	(HEAD + "\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message('x')\n", "must call nextHandler()"),
	(HEAD + "\tdef event_gainFocus(self, obj):\n\t\tpass\n", "must take (self, obj, nextHandler)"),
	(HEAD + "\tdef script_a(self):\n\t\tpass\n", "must take exactly (self, gesture)"),
	(HEAD + "\tdef script_a(self, gesture):\n\t\ttones.beep(440, 50)\n", "tones is used but not imported"),
	(HEAD + "\t@script(description='x', gesture='NVDA+k')\n\tdef script_a(self, gesture):\n\t\tpass\n", "must start with kb:"),
):
	problems = microaddons.check(source)
	assert any(expected in p for p in problems), (expected, problems)
assert microaddons.slug("Beep on Links!") == "beep_on_links" and microaddons.slug("9 lives") == "helper_9_lives"
fenced = "Here it is:\n```python\nimport ui\n```\nDone."
assert microaddons.extractCode(fenced) == "import ui\n" and microaddons.extractCode("```python\nimport ui\n") == "import ui\n"


# --- Writing an add-on: the coder writes, the check finds a fault, the coder repairs, the other model reviews ---

class FakeLLM:
	def __init__(self, texts, verdicts):
		self.texts, self.verdicts, self.calls = list(texts), list(verdicts), []

	def text(self, role, system, user, **options):
		self.calls.append((role, user))
		return self.texts.pop(0)

	def json(self, role, system, user, schema, **options):
		self.calls.append((role, user))
		return self.verdicts.pop(0)


# A fault that plain code cannot correct, so the coder model has to: something that is not allowed.
broken = ("```python\n" + HEAD
	+ "\tdef event_gainFocus(self, obj, nextHandler):\n\t\texec('x')\n\t\tui.message('link')\n\t\tnextHandler()\n```")
fixed = "```python\n" + HEAD + "\tdef event_gainFocus(self, obj, nextHandler):\n\t\tui.message('link')\n\t\tnextHandler()\n```"
params = policy.select({"complexity": "complex", "needs_code": True})
task = taskModule.Task("write an add-on")
llm = FakeLLM([broken, fixed], [{"ok": True, "problem": ""}])
source = microaddons.write(llm, task, "say link when a link gets the focus, anywhere", "Program: firefox", "", params, CODER, VISION)
assert microaddons.check(source) == [] and "nextHandler()" in source
assert [role for role, _u in llm.calls] == [CODER, CODER, VISION]
assert "exec() is not allowed" in llm.calls[1][1]
# The reviewing model finds a fault: the coder is sent back once more.
llm = FakeLLM([fixed, fixed], [{"ok": False, "problem": "It speaks for every control, not only links."}, {"ok": True, "problem": ""}])
microaddons.write(llm, task, "say link when a link gets the focus, anywhere", "", "", params, CODER, VISION)
assert "not only links" in llm.calls[2][1]
# The checks decide; the reviewing model only advises. Code that passes every check is kept even if the
# reviewer still doubts it when the tries are used up, and the doubt is kept for the user.
no = {"ok": False, "problem": "It might be too loud."}
llm = FakeLLM([fixed] * 10, [no, no])
kept = microaddons.write(llm, task, "say link when a link gets the focus, anywhere", "", "", params, CODER, VISION)
assert microaddons.check(kept) == [] and task.codeDoubt == "It might be too loud."
# Code that never passes is refused, not run.
llm = FakeLLM([broken] * 10, [])
try:
	microaddons.write(llm, task, "x", "", "", params, CODER, VISION)
	raise AssertionError("code that fails the check must be refused")
except ToolError as e:
	assert "exec() is not allowed" in str(e)

# --- Does the code do what was asked, and only that? ---

KEY_ONLY = microaddons.EXAMPLE_KEY
EVENT_ONLY = microaddons.EXAMPLE_EVENT
assert microaddons.check(KEY_ONLY) == [] and microaddons.check(EVENT_ONLY) == []
assert microaddons.checkAgainst(KEY_ONLY, "Say the name of the focused control when I press NVDA+shift+F9") == []
assert microaddons.checkAgainst(EVENT_ONLY, "Beep when a button gets the focus") == []
# Something that happens by itself, though only a key was asked for.
found = microaddons.checkAgainst(microaddons.TEMPLATE, "Say hello when I press NVDA+shift+H")
assert any("does not ask for anything to happen by itself. Remove event_gainFocus" in p for p in found), found
assert any("only for the program notepad" in p for p in found), found
# A key nobody asked for.
found = microaddons.checkAgainst(microaddons.TEMPLATE, "Beep whenever a link gets the focus")
assert any("does not ask for a key command. Remove script_sayName" in p for p in found), found
# A program limit is fine when the request names the program, or says "this program" and the facts name it.
assert not any("only for the program" in p for p in microaddons.checkAgainst(
	microaddons.TEMPLATE, "In Notepad, say text area when the focus moves, and the name on NVDA+shift+F9"))
assert not any("only for the program" in p for p in microaddons.checkAgainst(
	microaddons.TEMPLATE, "In this program, announce text area when the focus moves; key NVDA+shift+F9",
	"Program: notepad. Window title: Untitled."))
# A control's kind compared with a text never matches.
wrongRole = EVENT_ONLY.replace("obj.role == controlTypes.Role.BUTTON", "obj.role == \"link\"")
found = microaddons.checkAgainst(wrongRole, "Beep when a link gets the focus")
assert any("controlTypes.Role.LINK" in p for p in found), found
assert any("does nothing" in p for p in microaddons.checkAgainst(HEAD + "\tpass\n", "Say hello on NVDA+shift+H"))

# --- What plain code corrects, without asking a model ---

# An event nobody asked for is taken out; the key command stays, and the result passes every check.
tidied = microaddons.tidy(microaddons.TEMPLATE, "Say the name of the focused control when I press NVDA+shift+F9")
assert "event_gainFocus" not in tidied and "script_sayName" in tidied and microaddons.check(tidied) == []
assert microaddons.checkAgainst(tidied, "Say the name of the focused control when I press NVDA+shift+F9") == []
# A key nobody asked for is taken out, with its decorator; the event stays.
tidied = microaddons.tidy(microaddons.TEMPLATE, "Say text area whenever the focus moves in Notepad")
assert "script_sayName" not in tidied and "@script" not in tidied and "event_gainFocus" in tidied
assert microaddons.check(tidied) == []
# "when I press" asks for a key, not for something that happens by itself.
assert not microaddons._wantsEvent("Say hello when I press NVDA+shift+H")
assert microaddons._wantsEvent("Say hello when a window opens") and microaddons._wantsEvent("Beep whenever a link gets the focus")
# A control's kind written as a text is rewritten the way NVDA needs it, and the import is added.
noImport = EVENT_ONLY.replace("import controlTypes\n", "").replace("obj.role == controlTypes.Role.BUTTON", "obj.role == 'link'")
tidied = microaddons.tidy(noImport, "Beep when a link gets the focus")
assert "obj.role == controlTypes.Role.LINK" in tidied and tidied.startswith("import controlTypes\n"), tidied
assert microaddons.check(tidied) == [] and microaddons.checkAgainst(tidied, "Beep when a link gets the focus") == []
# Code that would be left with nothing is not touched, so that the coder is told what is wrong instead.
assert microaddons.tidy(KEY_ONLY, "Beep when a link gets the focus") == KEY_ONLY
# A request for one program, and code that works everywhere: the limit is asked for.
found = microaddons.checkAgainst(KEY_ONLY, "In notepad, say the name on NVDA+shift+F9", "Program: notepad. Window title: x.")
assert any("only for the program notepad" in p and "appName" in p for p in found), found

# ... and plain code puts the limit in: in another program the key is passed on, the event goes to NVDA.
tidied = microaddons.tidy(KEY_ONLY, "In notepad, say the name on NVDA+shift+F9", "Program: notepad. Window title: x.")
assert 'if api.getFocusObject().appModule.appName != "notepad":' in tidied and "gesture.send()" in tidied
assert microaddons.check(tidied) == []
assert microaddons.checkAgainst(tidied, "In notepad, say the name on NVDA+shift+F9", "Program: notepad.") == []
spaces = EVENT_ONLY.replace("\t", "    ")
tidied = microaddons.tidy(spaces, "Beep when a button gets the focus in notepad", "Program: notepad.")
assert '        if getattr(getattr(obj, "appModule", None), "appName", None) != "notepad":\n            nextHandler()' in tidied
assert tidied.startswith("import api\n") and microaddons.check(tidied) == []
# A request that names no program gets no limit.
assert microaddons.tidy(KEY_ONLY, "Say the name on NVDA+shift+F9", "Program: notepad.") == KEY_ONLY

# A forgotten import is added, and an event that forgot to pass the event on is made to.
forgetful = (
	"import globalPluginHandler\n\n\nclass GlobalPlugin(globalPluginHandler.GlobalPlugin):\n\n"
	"\tdef event_gainFocus(self, obj, nextHandler):\n\t\tif obj.role == controlTypes.Role.LINK:\n\t\t\ttones.beep(880, 80)\n")
assert len(microaddons.check(forgetful)) == 3
tidied = microaddons.tidy(forgetful, "Beep when a link gets the focus")
assert microaddons.check(tidied) == [] and tidied.rstrip().endswith("\t\tnextHandler()"), tidied
assert tidied.startswith("import tones\nimport controlTypes\n"), tidied
assert microaddons.tidy(EVENT_ONLY, "Beep when a button gets the focus") == EVENT_ONLY  # nothing to correct

# A file cut off in the middle, because the model went on too long, is cut back to a complete program.
cutOff = KEY_ONLY + "\t\tif obj.role == 1:\n\t\t\tui.message(\"one\")\n\t\tif obj.role == 2:\n"
assert any("Syntax error" in p for p in microaddons.check(cutOff))
saved = microaddons.salvage(cutOff)
assert microaddons.check(saved) == [] and "ui.message(\"one\")" in saved and "obj.role == 2" not in saved
assert microaddons.salvage(KEY_ONLY) == KEY_ONLY and microaddons.salvage("def x(:") == "def x(:"
assert microaddons.check(microaddons.tidy(cutOff, "Say the name on NVDA+shift+F9")) == []

# A model that writes one line over and over is stopped, and the repeated lines are dropped.
from visionClaw.engine import CodeGuard  # noqa: E402
guard = CodeGuard()
assert guard.feed("import ui\n\n\ndef a():\n\tpass\n") and guard.feed("\n\ndef b():\n\tpass\n")
stopped = [guard.feed("\t# Say the time\n") for _ in range(6)]
assert stopped[:4] == [True] * 4 and stopped[4] is False
assert guard.finish().count("# Say the time") == 0 and guard.finish().startswith("import ui")
guard = CodeGuard()
assert all(guard.feed(f"x{i} = {i}\n") for i in range(CodeGuard.MAX_LINES)) and not guard.feed("one = 1\n")

# --- What an add-on does, in plain words, found by checking its code ---

facts = microaddons.describe(microaddons.TEMPLATE)
assert "It adds the key NVDA+shift+f9: Says the name of the focused control." in facts, facts
assert "It acts by itself when the focus moves to another control." in facts
assert "It works only in: notepad." in facts and "It can say: text area." in facts, facts
plain = microaddons.describe(HEAD + "\tdef script_a(self, gesture):\n\t\ttones.beep(440, 50)\n")
assert "It is not limited to one program." in plain and "It beeps." in plain, plain
assert microaddons.describe("def x(:") == []

# --- Debugging an add-on: the error goes to the coder, and the result is checked and reviewed again ---

llm = FakeLLM([broken, fixed], [{"ok": True, "problem": ""}])
problems = ["When it ran in NVDA, event_gainFocus failed with AttributeError: 'NoneType' object has no attribute 'name'."]
corrected = microaddons.fix(llm, task, "say link when a link gets the focus, anywhere", source, problems, "Check for None.", params, CODER, VISION)
assert microaddons.check(corrected) == [] and [role for role, _u in llm.calls] == [CODER, CODER, VISION]
assert "AttributeError" in llm.calls[0][1] and "Check for None." in llm.calls[0][1] and "Find the cause" in llm.calls[0][1]
assert "exec() is not allowed" in llm.calls[1][1]  # the corrected file is checked like a new one

# --- Keeping and packaging add-ons ---

store = microaddons.Store(tempfile.mkdtemp())
store.save("Link Beeper", source, "say link when a link gets the focus, anywhere")
assert [m["name"] for m in store.list()] == ["link_beeper"] and store.source("Link Beeper") == source
assert store.setEnabled("link_beeper", False) and store.meta("link_beeper")["enabled"] is False
package = store.package("link_beeper", tempfile.mkdtemp())
with zipfile.ZipFile(package) as z:
	assert sorted(z.namelist()) == ["globalPlugins/visionClaw_link_beeper.py", "manifest.ini"]
	manifest = z.read("manifest.ini").decode()
	assert "name = visionClaw_link_beeper" in manifest and "minimumNVDAVersion = 2024.1" in manifest
assert store.remove("link_beeper") and store.list() == [] and not store.remove("link_beeper")

# --- The knowledge base ---

knowledge = Knowledge()
assert knowledge.count() >= 25
for query, expected in (
	("hotkey key command script gesture", "Key commands"),
	("react when the focus moves to a control", "Events, reacting when focus moves"),
	("button without a name", "Unlabelled buttons and icons"),
	("game that NVDA cannot read", "Games"),
	("click the mouse at a position", "Clicking the mouse"),
):
	titles = [title for title, _body, _source in knowledge.search(query, limit=3)]
	assert any(expected in title for title in titles), (query, titles)
assert knowledge.text("zzzz qqqq") == ""
knowledge.addSource("guide", lambda: [("Screen curtain", "The screen curtain makes the screen black for privacy.", "guide")])
assert "privacy" in knowledge.text("screen curtain black")
print("OK")
