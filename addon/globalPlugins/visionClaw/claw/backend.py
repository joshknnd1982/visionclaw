# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - where the models run: a dedicated graphics card, any graphics chip through Vulkan, or the
# processor. The engine reaches every graphics chip through Vulkan; a dedicated card is simply the fastest of them.
# No NVDA dependencies.

import collections
import re
import subprocess

AUTO, DEDICATED, VULKAN, CPU = "auto", "dedicated", "vulkan", "cpu"
CHOICES = (AUTO, DEDICATED, VULKAN, CPU)
CREATE_NO_WINDOW = 0x08000000

# id is what the engine calls the device, like "Vulkan0". Memory is in MiB.
Device = collections.namedtuple("Device", "id name totalMb freeMb dedicated")
# kind is DEDICATED, VULKAN or CPU. device is a Device, or None for the processor.
Backend = collections.namedtuple("Backend", "kind device")

_DEVICE_LINE = re.compile(r"^\s*([A-Za-z]+\d+):\s*(.+?)\s*\((\d+)\s*MiB,\s*(\d+)\s*MiB free\)\s*$", re.MULTILINE)
# Not real graphics hardware.
_SOFTWARE = ("llvmpipe", "swiftshader", "microsoft basic", "software", "lavapipe", "warp")
_DEDICATED = re.compile(
	r"nvidia|geforce|quadro|\brtx\b|\bgtx\b|tesla"
	r"|radeon\s*(\(tm\)\s*)?(rx|pro\s*w|vii)\b|firepro|\brx\s?\d{3,4}"
	r"|arc\s*(\(tm\)\s*)?(pro\s*)?[ab]\d{3}",
	re.IGNORECASE,
)


def isDedicated(name):
	"""Whether a graphics adapter is a separate card, from its name. Built-in chips such as "Radeon 780M Graphics",
	"Intel UHD Graphics" and "Intel Arc Graphics" are not."""
	return bool(_DEDICATED.search(name or ""))


def parseDevices(text):
	"""Devices from the engine's --list-devices output."""
	devices = []
	for m in _DEVICE_LINE.finditer(text or ""):
		name = m.group(2)
		if any(s in name.lower() for s in _SOFTWARE):
			continue
		devices.append(Device(m.group(1), name, int(m.group(3)), int(m.group(4)), isDedicated(name)))
	return devices


def listDevices(exe, timeout=30):
	"""Ask the engine which graphics devices it can use. An empty list if there are none or it cannot say."""
	try:
		out = subprocess.run(
			[exe, "--list-devices"], capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW,
			stdin=subprocess.DEVNULL,
		)
	except (OSError, subprocess.SubprocessError):
		return []
	return parseDevices((out.stdout + out.stderr).decode("utf-8", "replace"))


def plan(choice, devices):
	"""The backends to try, best first. The last one is always the processor.
	auto, dedicated: the dedicated card, then another graphics chip through Vulkan, then the processor.
	vulkan: a built-in graphics chip if there is one (this leaves a dedicated card free), else any chip.
	cpu: the processor only."""
	dedicated = sorted((d for d in devices if d.dedicated), key=lambda d: -d.totalMb)
	builtIn = [d for d in devices if not d.dedicated]
	chain = []
	if choice in (AUTO, DEDICATED):
		chain += [Backend(DEDICATED, d) for d in dedicated[:1]]
		chain += [Backend(VULKAN, d) for d in builtIn[:1]]
	elif choice == VULKAN:
		chain += [Backend(VULKAN, d) for d in (builtIn or dedicated)[:1]]
		if builtIn and dedicated:
			chain.append(Backend(DEDICATED, dedicated[0]))
	chain.append(Backend(CPU, None))
	return chain


def key(backend):
	"""A short name for a backend, used to remember which ones failed."""
	return backend.kind if backend.device is None else f"{backend.kind}:{backend.device.id}"


def describe(backend):
	"""A backend in words, for telling the user where a model runs."""
	if backend.device is None:
		return "the processor"
	kind = "dedicated graphics card" if backend.device.dedicated else "built-in graphics chip, through Vulkan"
	return f"{backend.device.name} ({kind})"


def engineArgs(backend, hasProjector):
	"""Engine arguments that put the model on this backend."""
	if backend.kind == CPU:
		return ["-ngl", "0", "--device", "none"] + (["--no-mmproj-offload"] if hasProjector else [])
	return ["-ngl", "99", "--device", backend.device.id]
