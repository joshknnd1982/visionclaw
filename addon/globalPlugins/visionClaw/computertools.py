# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the tools that work the computer itself for the user: opening a program, a folder, the Recycle
# Bin or a page of Windows Settings by its name; what the Recycle Bin holds, and emptying it; the computer's
# volume; switching to, closing, minimizing and maximizing windows; the files in the user's own folders; facts
# about the computer; locking, sleeping, restarting and shutting down; and checking whether something is on the
# screen, for a request that depends on it. Which thing is meant is read from the user's own words by plain
# code (claw/computer.py); a model at most chooses among the few things that were found.
#
# Everything Windows is asked for here is on this computer; nothing goes online.
# Windows' own structures and numbers were read on 2026-11-18 from Microsoft's pages for SHQueryRecycleBinW,
# SHQUERYRBINFO and SHEmptyRecycleBinW, and from the header files of the Windows SDK 10.0.26100 on the owner's
# computer: shellapi.h (SHQUERYRBINFO is packed to one byte only in a 32-bit program; the SHERB_ flags),
# mmdeviceapi.h and endpointvolume.h (the order of the functions of IMMDeviceEnumerator, IMMDevice and
# IAudioEndpointVolume, and their ids). When they are changed, read those again; do not write one from memory.
#
# What tests must never do for real is in functions of their own, which tests/test_nvda_stub.py replaces:
# shellOpen, emptyBin, setVolume, setMute, focusWindow, closeWindow, showWindow, power, minimizeAll, recycle.
# SHFILEOPSTRUCTW and the FO_ and FOF_ numbers for moving a file to the Recycle Bin are from the same shellapi.h.

import ctypes
import os
import shutil
import subprocess
import sys
import time
import uuid

import addonHandler
import api
import config

from . import ocr
from .claw import computer, debuglog, policy, prompts, scrolling
from .claw.catalog import VISION
from .claw.llm import clip
from .claw.tools import VERBATIM, ToolError
from .engine import prepareImage

addonHandler.initTranslation()

MAX_WINDOWS = 30
# The programs of the Start menu and the things on the desktop are read again after this many seconds.
THINGS_SECONDS = 120
# A search for files gives up after this long or this many files, and says so.
SEARCH_SECONDS = 8
SEARCH_FILES = 60000
SEARCH_DEPTH = 6
_NOT_PROGRAMS = ("uninstall", "readme", "read me", "license", "licence", "website", "web site", "homepage", "release notes",
	"changelog", "documentation", "user guide", "help", "manual", "report a bug", "support")
_things = {"at": 0.0, "found": []}
_SW_SHOWNORMAL, _SW_MAXIMIZE, _SW_MINIMIZE, _SW_RESTORE = 1, 3, 6, 9
_WM_CLOSE = 0x0010


def _safe(fn, default=None):
	try:
		return fn()
	except Exception:
		return default


# --- Opening ---

def shellOpen(target, arguments=None):
	"""Hand something to Windows to open, as a double click on it would. A place of Windows ("shell:...") is
	opened by File Explorer. Raises OSError when Windows refuses."""
	shell32 = ctypes.windll.shell32
	shell32.ShellExecuteW.restype = ctypes.c_void_p
	shell32.ShellExecuteW.argtypes = (
		ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int)
	if arguments is None and target.lower().startswith("shell:"):
		target, arguments = "explorer.exe", target
	result = shell32.ShellExecuteW(None, "open", target, arguments, None, _SW_SHOWNORMAL)
	if (result or 0) <= 32:
		raise OSError(f"Windows did not open it (its answer was {result}).")


def userFolders():
	"""The user's own folders, by the names of computer.FOLDERS, as Windows keeps them; a folder that was
	moved, as to OneDrive, is found where it is now."""
	import winreg
	home = os.path.expanduser("~")
	names = {
		"desktop": ("Desktop", "Desktop"), "documents": ("Personal", "Documents"),
		"downloads": ("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"), "pictures": ("My Pictures", "Pictures"),
		"music": ("My Music", "Music"), "videos": ("My Video", "Videos")}
	found = {}
	try:
		key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
	except OSError:
		key = None
	for name, (value, usual) in names.items():
		path = ""
		if key is not None:
			try:
				path = os.path.expandvars(str(winreg.QueryValueEx(key, value)[0]))
			except OSError:
				path = ""
		found[name] = path if path and os.path.isdir(path) else os.path.join(home, usual)
	if key is not None:
		winreg.CloseKey(key)
	return found


def _storeApps():
	"""The apps Windows lists in its Apps folder, which has the apps from the Store that the Start menu's own
	folders do not: (name, what File Explorer is given to start it). Empty when Windows cannot be asked."""
	found = []
	try:
		import comtypes
		import comtypes.client
		try:
			comtypes.CoInitialize()
			started = True
		except Exception:
			started = False
		try:
			folder = comtypes.client.CreateObject("Shell.Application").NameSpace("shell:AppsFolder")
			for item in folder.Items():
				name, path = str(item.Name or ""), str(item.Path or "")
				if name and path:
					found.append((name, "shell:AppsFolder\\" + path))
		finally:
			if started:
				comtypes.CoUninitialize()
	except Exception as e:
		debuglog.error("computer", "Windows' list of apps could not be read", e)
	return found


def gather():
	"""Everything on this computer that can be opened by its name: the places, tools and settings pages of
	Windows, the programs of the Start menu, the apps of Windows' Apps folder, and what is on the desktop."""
	if _things["found"] and time.monotonic() - _things["at"] < THINGS_SECONDS:
		return _things["found"]
	found = computer.places()
	have = {computer.slug(item["name"]) for item in found}
	folders = userFolders()
	desktops = [folders["desktop"], os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")]
	for folder in desktops:
		for name in _safe(lambda: sorted(os.listdir(folder)), []):
			if name.lower() == "desktop.ini":
				continue
			path = os.path.join(folder, name)
			shown = os.path.splitext(name)[0] if name.lower().endswith((".lnk", ".url", ".appref-ms")) else name
			found.append(computer.thing("desktop", shown, computer.ON_DESKTOP, path))
			have.add(computer.slug(shown))
	menus = [
		os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
		os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs")]
	for menu in menus:
		for folder, _folders, names in _safe(lambda: list(os.walk(menu)), []):
			for name in names:
				shown, ending = os.path.splitext(name)
				if ending.lower() not in (".lnk", ".url", ".appref-ms") or any(word in shown.lower() for word in _NOT_PROGRAMS):
					continue
				if computer.slug(shown) not in have:
					have.add(computer.slug(shown))
					found.append(computer.thing("program", shown, computer.PROGRAM, os.path.join(folder, name)))
	for name, target in _storeApps():
		if computer.slug(name) not in have and not any(word in name.lower() for word in _NOT_PROGRAMS):
			have.add(computer.slug(name))
			found.append(computer.thing("program", name, computer.PROGRAM, target))
	_things["found"], _things["at"] = found, time.monotonic()
	return found


def browserPath(exe):
	"""Where a browser's program file is, from the place Windows keeps the paths of programs, or None."""
	import winreg
	for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
		try:
			with winreg.OpenKey(root, rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as key:
				path = os.path.expandvars(str(winreg.QueryValueEx(key, "")[0])).strip('"')
				if os.path.isfile(path):
					return path
		except OSError:
			continue
	return None


# --- The Recycle Bin ---

class _SHQUERYRBINFO(ctypes.Structure):
	# shellapi.h packs its structures to one byte in a 32-bit program only.
	if ctypes.sizeof(ctypes.c_void_p) == 4:
		_pack_ = 1
	_fields_ = [("cbSize", ctypes.c_ulong), ("i64Size", ctypes.c_longlong), ("i64NumItems", ctypes.c_longlong)]


_SHERB_NOCONFIRMATION, _SHERB_NOPROGRESSUI, _SHERB_NOSOUND = 0x1, 0x2, 0x4


def binInfo():
	"""(how many items the Recycle Bin holds on all drives, their size in bytes), or None when Windows does
	not say. Only asks; changes nothing."""
	info = _SHQUERYRBINFO()
	info.cbSize = ctypes.sizeof(info)
	query = ctypes.windll.shell32.SHQueryRecycleBinW
	query.argtypes = (ctypes.c_wchar_p, ctypes.POINTER(_SHQUERYRBINFO))
	query.restype = ctypes.c_long
	if query(None, ctypes.byref(info)) == 0:
		return int(info.i64NumItems), int(info.i64Size)
	# Asked for all drives at once, some versions of Windows refuse: then drive by drive.
	count = size = 0
	answered = False
	for letter, _label, _free, _total in drives():
		info = _SHQUERYRBINFO()
		info.cbSize = ctypes.sizeof(info)
		if query(letter + "\\", ctypes.byref(info)) == 0:
			answered = True
			count += int(info.i64NumItems)
			size += int(info.i64Size)
	return (count, size) if answered else None


def emptyBin():
	"""Empty the Recycle Bin on all drives, for good. Windows asks nothing and shows nothing: the user was
	asked by VisionClaw. Raises OSError when Windows refuses."""
	empty = ctypes.windll.shell32.SHEmptyRecycleBinW
	empty.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong)
	empty.restype = ctypes.c_long
	result = empty(None, None, _SHERB_NOCONFIRMATION | _SHERB_NOPROGRESSUI | _SHERB_NOSOUND)
	if result != 0:
		raise OSError(f"Windows did not empty the Recycle Bin (its answer was {result & 0xFFFFFFFF:#x}).")


# --- Facts about the computer ---

def drives():
	"""The drives that are built in or plugged in, with what is free: (letter, label, free bytes, total bytes).
	Network drives and disc drives are left out, because asking them can take long."""
	kernel32 = ctypes.windll.kernel32
	kernel32.GetDriveTypeW.argtypes = (ctypes.c_wchar_p,)
	found = []
	mask = kernel32.GetLogicalDrives()
	for index in range(26):
		if not mask & (1 << index):
			continue
		letter = f"{chr(65 + index)}:"
		if kernel32.GetDriveTypeW(letter + "\\") not in (2, 3):  # removable, fixed
			continue
		free, total = ctypes.c_ulonglong(0), ctypes.c_ulonglong(0)
		if not kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(letter + "\\"), None, ctypes.byref(total), ctypes.byref(free)):
			continue
		label = ctypes.create_unicode_buffer(261)
		kernel32.GetVolumeInformationW(ctypes.c_wchar_p(letter + "\\"), label, 261, None, None, None, None, 0)
		found.append((letter, label.value, int(free.value), int(total.value)))
	return found


def systemDrive():
	"""(free bytes, total bytes) of the drive Windows is on, or (None, None)."""
	letter = (os.environ.get("SystemDrive") or "C:").upper()
	for drive, _label, free, total in _safe(drives, []):
		if drive == letter:
			return free, total
	return None, None


class _MEMORYSTATUSEX(ctypes.Structure):
	_fields_ = [
		("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
		("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
		("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
		("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def memory():
	"""(free bytes, total bytes) of the computer's memory."""
	status = _MEMORYSTATUSEX()
	status.dwLength = ctypes.sizeof(status)
	if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
		raise OSError("Windows did not say how much memory there is.")
	return int(status.ullAvailPhys), int(status.ullTotalPhys)


def upSeconds():
	ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
	return ctypes.windll.kernel32.GetTickCount64() // 1000


def processorText():
	import winreg
	name = ""
	try:
		with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
			name = " ".join(str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).split())
	except OSError:
		pass
	return f"The processor is {name or 'not named by Windows'}, with {computer.many(os.cpu_count() or 1, 'thread')}."


def networkText():
	"""Whether Windows says the computer is connected, and its addresses on the network. Nothing is sent."""
	import socket
	flags = ctypes.c_ulong(0)
	connected = bool(_safe(lambda: ctypes.windll.wininet.InternetGetConnectedState(ctypes.byref(flags), 0), False))
	name = socket.gethostname()
	addresses = sorted({info[4][0] for info in _safe(lambda: socket.getaddrinfo(name, None, socket.AF_INET), [])
		if not info[4][0].startswith("127.")})
	said = "Windows says this computer is connected to a network." if connected else "Windows says this computer is not connected to a network."
	if addresses:
		said += " Its address on the network is " + " and ".join(addresses) + "."
	return said + " Whether a website can be reached was not tried, because VisionClaw sends nothing by itself."


def systemText():
	version = sys.getwindowsversion()
	return (
		f"This computer is called {os.environ.get('COMPUTERNAME', 'an unknown name')}. You are signed in as "
		f"{os.environ.get('USERNAME', 'an unknown user')}. Windows is version {version.major}.{version.minor}, build {version.build}.")


# --- Windows that are open ---

def _processName(hwnd):
	user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
	pid = ctypes.c_ulong(0)
	user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
	kernel32.OpenProcess.restype = ctypes.c_void_p
	handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
	if not handle:
		return ""
	try:
		buffer = ctypes.create_unicode_buffer(520)
		size = ctypes.c_ulong(520)
		if kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, buffer, ctypes.byref(size)):
			return os.path.splitext(os.path.basename(buffer.value))[0]
		return ""
	finally:
		kernel32.CloseHandle(ctypes.c_void_p(handle))


def openWindows():
	"""The windows the user can switch to, the one in front first: {"hwnd", "title", "app", "front",
	"minimized"}. Only asks; changes nothing."""
	user32 = ctypes.windll.user32
	user32.GetForegroundWindow.restype = ctypes.c_void_p
	user32.GetWindow.restype = ctypes.c_void_p
	front = user32.GetForegroundWindow()
	found = []

	@ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
	def each(hwnd, _extra):
		handle = ctypes.c_void_p(hwnd)
		if len(found) >= MAX_WINDOWS or not user32.IsWindowVisible(handle):
			return True
		# A tool window is a floating helper, and an owned window belongs to another: neither is switched to.
		if user32.GetWindowLongW(handle, -20) & 0x80 or user32.GetWindow(handle, 4):
			return True
		# Windows keeps some windows of sleeping apps "cloaked": they count as visible and are shown nowhere.
		cloaked = ctypes.c_int(0)
		try:
			ctypes.windll.dwmapi.DwmGetWindowAttribute(handle, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
		except Exception:
			pass
		length = user32.GetWindowTextLengthW(handle)
		if cloaked.value or length <= 0:
			return True
		buffer = ctypes.create_unicode_buffer(length + 1)
		user32.GetWindowTextW(handle, buffer, length + 1)
		title = " ".join(buffer.value.split())[:90]
		if title and title != "Program Manager":
			found.append({
				"hwnd": hwnd, "title": title, "app": _safe(lambda: _processName(hwnd), ""), "front": hwnd == front,
				"minimized": bool(user32.IsIconic(handle))})
		return True

	user32.EnumWindows(each, None)
	found.sort(key=lambda window: not window["front"])
	return found


def focusWindow(hwnd):
	"""Bring a window to the front. Returns whether Windows did."""
	user32 = ctypes.windll.user32
	user32.GetForegroundWindow.restype = ctypes.c_void_p
	handle = ctypes.c_void_p(hwnd)
	if user32.IsIconic(handle):
		user32.ShowWindow(handle, _SW_RESTORE)
	user32.SetForegroundWindow(handle)
	if user32.GetForegroundWindow() != hwnd:
		# Windows lets a program bring a window to the front right after a key was pressed: Alt, down and up.
		user32.keybd_event(0x12, 0, 0, 0)
		user32.keybd_event(0x12, 0, 2, 0)
		user32.SetForegroundWindow(handle)
	time.sleep(0.3)
	return user32.GetForegroundWindow() == hwnd


def closeWindow(hwnd):
	"""Ask a window to close, as Alt+F4 would, so that it can still ask about unsaved work. Returns whether
	it is gone two seconds later."""
	user32 = ctypes.windll.user32
	user32.PostMessageW(ctypes.c_void_p(hwnd), _WM_CLOSE, 0, 0)
	for _try in range(20):
		time.sleep(0.1)
		if not user32.IsWindow(ctypes.c_void_p(hwnd)) or not user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
			return True
	return False


def showWindow(hwnd, action):
	command = {computer.MINIMIZE: _SW_MINIMIZE, computer.MAXIMIZE: _SW_MAXIMIZE, computer.RESTORE: _SW_RESTORE}[action]
	ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), command)


def pressEscape():
	from keyboardHandler import KeyboardInputGesture
	KeyboardInputGesture.fromName("escape").send()


def minimizeAll():
	"""Show the desktop, as Windows+D does."""
	from keyboardHandler import KeyboardInputGesture
	KeyboardInputGesture.fromName("windows+d").send()


# --- The computer's volume ---

class _GUID(ctypes.Structure):
	_fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]


def _guid(text):
	return _GUID.from_buffer_copy(uuid.UUID(text).bytes_le)


_CLSID_ENUMERATOR = "BCDE0395-E52F-467C-8E3D-C4579291692E"
_IID_ENUMERATOR = "A95664D2-9614-4F35-A746-DE8DB63617E6"
_IID_VOLUME = "5CDF2C82-841E-4546-9722-0CF74078229A"
_CLSCTX_ALL = 0x17
# Where each function is in its interface, counted as in the header files, after the three every interface has.
_GET_DEFAULT_ENDPOINT, _ACTIVATE, _RELEASE = 4, 3, 2
_SET_LEVEL, _GET_LEVEL, _SET_MUTE, _GET_MUTE = 7, 9, 14, 15


def _call(pointer, index, *arguments):
	"""Call the function at a place in a COM interface. Raises OSError when it fails."""
	table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
	# A plain number or fraction is passed as what it is; everything else is the address of something.
	plain = (ctypes.c_int, ctypes.c_ulong, ctypes.c_float)
	types = [ctypes.c_void_p] + [type(argument) if isinstance(argument, plain) else ctypes.c_void_p for argument in arguments]
	result = ctypes.WINFUNCTYPE(ctypes.c_long, *types)(table[index])(pointer, *arguments)
	if result < 0 and index != _RELEASE:
		raise OSError(f"Windows' sound system gave the answer {result & 0xFFFFFFFF:#x}.")
	return result


class _EndpointVolume:
	"""The volume of the device Windows plays sound through, for the length of a with block."""

	def __enter__(self):
		ole32 = ctypes.windll.ole32
		# 0 or 1: this thread uses COM from now and must end it; anything else: it did already, in another way.
		self._started = ole32.CoInitializeEx(None, 0) in (0, 1)
		self._held = []
		try:
			enumerator = ctypes.c_void_p()
			result = ole32.CoCreateInstance(
				ctypes.byref(_guid(_CLSID_ENUMERATOR)), None, _CLSCTX_ALL, ctypes.byref(_guid(_IID_ENUMERATOR)),
				ctypes.byref(enumerator))
			if result < 0 or not enumerator:
				raise OSError(f"Windows' sound system could not be reached ({result & 0xFFFFFFFF:#x}).")
			self._held.append(enumerator)
			device = ctypes.c_void_p()
			# 0, 1: the device that plays sound, for music and everything else.
			_call(enumerator, _GET_DEFAULT_ENDPOINT, ctypes.c_int(0), ctypes.c_int(1), ctypes.byref(device))
			self._held.append(device)
			self._volume = ctypes.c_void_p()
			_call(device, _ACTIVATE, ctypes.byref(_guid(_IID_VOLUME)), ctypes.c_ulong(_CLSCTX_ALL), None, ctypes.byref(self._volume))
			self._held.append(self._volume)
		except Exception:
			self.__exit__()
			raise
		return self

	def __exit__(self, *_error):
		for pointer in reversed(self._held):
			_safe(lambda: _call(pointer, _RELEASE))
		self._held = []
		if self._started:
			ctypes.windll.ole32.CoUninitialize()
			self._started = False

	def level(self):
		value = ctypes.c_float(0)
		_call(self._volume, _GET_LEVEL, ctypes.byref(value))
		return max(0, min(100, round(value.value * 100)))

	def muted(self):
		value = ctypes.c_int(0)
		_call(self._volume, _GET_MUTE, ctypes.byref(value))
		return bool(value.value)

	def setLevel(self, level):
		_call(self._volume, _SET_LEVEL, ctypes.c_float(max(0, min(100, level)) / 100.0), None)

	def setMute(self, muted):
		_call(self._volume, _SET_MUTE, ctypes.c_int(1 if muted else 0), None)


def volumeNow():
	"""(the computer's volume from 0 to 100, whether the sound is muted). Only asks."""
	with _EndpointVolume() as volume:
		return volume.level(), volume.muted()


def setVolume(level):
	with _EndpointVolume() as volume:
		volume.setLevel(level)
		return volume.level()


def setMute(muted):
	with _EndpointVolume() as volume:
		volume.setMute(muted)


# --- Locking, sleeping, restarting, shutting down ---

def power(what):
	"""Lock, sleep, restart, shut down, sign out, or call off a restart or shutdown that is waiting."""
	hidden = 0x08000000  # no console window
	shutdown = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "shutdown.exe")
	if what == computer.LOCK:
		if not ctypes.windll.user32.LockWorkStation():
			raise OSError("Windows did not lock the computer.")
	elif what == computer.SLEEP:
		ctypes.windll.powrprof.SetSuspendState(0, 0, 0)
	else:
		arguments = {
			computer.RESTART: ["/r", "/t", str(computer.POWER_WAIT)], computer.SHUTDOWN: ["/s", "/t", str(computer.POWER_WAIT)],
			computer.SIGN_OUT: ["/l"], computer.CANCEL: ["/a"]}[what]
		done = subprocess.run([shutdown] + arguments, capture_output=True, text=True, creationflags=hidden, timeout=20)
		if done.returncode != 0:
			raise OSError(" ".join((done.stderr or done.stdout or "Windows refused.").split()))


# --- Files ---

def searchFiles(wish, cancel=None):
	"""The files and folders of the user's own folders that fit a wish (computer.fileWish), in the order asked
	for: (found as computer.filesText takes them, how many fit, the folders' names, whether it stopped early)."""
	folders = userFolders()
	deep = bool(wish["words"] or wish["kinds"])
	started = time.monotonic()
	hits, seen, cut = [], 0, False
	for key in wish["folders"]:
		root = folders.get(key)
		if not root or not os.path.isdir(root):
			continue
		for folder, subfolders, names in os.walk(root):
			depth = folder[len(root):].count(os.sep)
			if not deep or depth >= SEARCH_DEPTH:
				entries = list(names) + list(subfolders)
				subfolders[:] = []
			else:
				subfolders[:] = [name for name in subfolders if not name.startswith((".", "$")) and name.lower() not in ("node_modules", "appdata")]
				entries = list(names) + list(subfolders)
			for name in entries:
				seen += 1
				if name.lower() == "desktop.ini" or not computer.fileFits(name, wish):
					continue
				path = os.path.join(folder, name)
				try:
					facts = os.stat(path)
				except OSError:
					continue
				isFolder = os.path.isdir(path)
				if isFolder and wish["kinds"]:
					continue
				hits.append((name, key.capitalize(), 0 if isFolder else facts.st_size, facts.st_mtime, isFolder, path))
			if (cancel is not None and cancel.is_set()) or seen > SEARCH_FILES or time.monotonic() - started > SEARCH_SECONDS:
				cut = True
				break
		if cut:
			break
	order = wish["order"]
	hits.sort(key=(lambda hit: -hit[3]) if order == computer.NEWEST else (lambda hit: -hit[2]) if order == computer.BIGGEST
		else (lambda hit: hit[0].lower()))
	shown = [(name, where, size, time.strftime("%B %d, %Y", time.localtime(changed)).replace(" 0", " "), isFolder)
		for name, where, size, changed, isFolder, _path in hits]
	return shown, hits, [key.capitalize() for key in wish["folders"]], cut


# --- Changing the user's files ---

class _SHFILEOPSTRUCTW(ctypes.Structure):
	# shellapi.h packs its structures to one byte in a 32-bit program only.
	if ctypes.sizeof(ctypes.c_void_p) == 4:
		_pack_ = 1
	_fields_ = [
		("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint), ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
		("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int), ("hNameMappings", ctypes.c_void_p),
		("lpszProgressTitle", ctypes.c_wchar_p)]


_FO_DELETE = 0x0003
_FOF_SILENT, _FOF_NOCONFIRMATION, _FOF_ALLOWUNDO, _FOF_NOERRORUI, _FOF_WANTNUKEWARNING = 0x0004, 0x0010, 0x0040, 0x0400, 0x4000


def recycle(path):
	"""Move a file or folder to the Recycle Bin, from where it can be brought back. Never deletes for good by
	itself: where Windows cannot put it into the Recycle Bin, Windows asks in a window of its own before it
	deletes anything. Raises OSError when Windows refuses or the user says no there."""
	operation = _SHFILEOPSTRUCTW()
	operation.wFunc = _FO_DELETE
	# The names are a list that ends with an empty one: the path, an end, and another end.
	names = ctypes.create_unicode_buffer(os.path.abspath(path) + "\0\0")
	operation.pFrom = ctypes.cast(names, ctypes.c_wchar_p)
	operation.fFlags = _FOF_ALLOWUNDO | _FOF_NOCONFIRMATION | _FOF_SILENT | _FOF_NOERRORUI | _FOF_WANTNUKEWARNING
	call = ctypes.windll.shell32.SHFileOperationW
	call.argtypes = (ctypes.POINTER(_SHFILEOPSTRUCTW),)
	call.restype = ctypes.c_int
	result = call(ctypes.byref(operation))
	if result != 0 or operation.fAnyOperationsAborted:
		raise OSError(f"Windows did not move it to the Recycle Bin (its answer was {result}).")


def placeText(path, folders):
	"""Where a file is, said by the user's own folder it is in: "Documents", or "Documents, in Taxes"."""
	folder = os.path.dirname(os.path.abspath(path))
	for key, root in folders.items():
		root = os.path.abspath(root)
		if folder == root:
			return key.capitalize()
		if folder.lower().startswith(root.lower() + os.sep):
			return f"{key.capitalize()}, in {folder[len(root) + 1:]}"
	return folder


def insideOwn(path, folders):
	"""Whether a path is inside one of the user's own folders. Nothing outside them is ever changed."""
	path = os.path.abspath(path).lower()
	return any(path.startswith(os.path.abspath(root).lower() + os.sep) for root in folders.values())


def undoFile(plugin, change, confirm):
	"""Put back what VisionClaw did to a file: a rename or a move is turned round, and something it made is
	removed again if it is still empty. Returns the sentence for the user."""
	kind = str(change["setting"]).split(":", 1)[1]
	old, new = change["old"], change["new"]
	what = change["label"]
	# With a capital at the start, and the file's own name as it is written.
	What = what[:1].upper() + what[1:]
	if not os.path.exists(new):
		plugin.changes.markUndone(change)
		return f"{What} is no longer where VisionClaw put it, so there is nothing to put back."
	if kind == "make":
		full = bool(os.listdir(new)) if os.path.isdir(new) else os.path.getsize(new) > 0
		if full:
			return f"{What} has something in it now, so it was left. To remove it, ask to delete it."
		# Translators: Asked before VisionClaw removes an empty folder or file it made. {what} is which.
		confirm(_("Remove {what} again? It is empty.").format(what=what))
		os.rmdir(new) if os.path.isdir(new) else os.remove(new)
		plugin.changes.markUndone(change)
		return f"Removed {what} again."
	if os.path.exists(old):
		return f"Something else is called {os.path.basename(old)} at the old place now, so {what} was left where it is."
	if kind == "rename":
		# Translators: Asked before VisionClaw gives a file its old name back. {what} is the file, {name} the old name.
		confirm(_("Rename {what} back to {name}?").format(what=what, name=os.path.basename(old)))
		os.rename(new, old)
		plugin.changes.markUndone(change)
		return f"{What} is called {os.path.basename(old)} again."
	# Translators: Asked before VisionClaw puts a file back. {what} is the file, {where} where it was.
	confirm(_("Put {what} back in {where}?").format(what=what, where=change.get("oldShown") or os.path.dirname(old)))
	shutil.move(new, old)
	plugin.changes.markUndone(change)
	return f"{What} is back in {change.get('oldShown') or os.path.dirname(old)}."


# --- The tools ---

def register(add, plugin, text, onMain, confirm, mustAgree, Refused, screen):
	"""Add the tools that work the computer itself. The first six arguments are the helpers of nvdatools.build;
	Refused is what a tool raises when VisionClaw will not do something; screen takes the pictures."""

	def brailleInUse():
		import braille
		name = _safe(lambda: braille.handler.display.name, "noBraille")
		return bool(name) and name != "noBraille"

	# Opening a thing by its name.
	def findThing(task, words):
		asked = computer.wanted(words)
		if not asked:
			raise ToolError("The request does not say what to open. Say its name, as in: open the Recycle Bin.")
		found, sure = computer.find(asked, computer.places())
		if not sure:
			found, sure = computer.find(asked, gather())
		task.check()
		if not found:
			# A file or folder of the user's own, by its name.
			wish = dict(computer.fileWish(asked), words=asked.split(), kinds=[], order=computer.BY_NAME)
			_shown, hits, _folders, _cut = searchFiles(wish, task.cancel)
			found = [computer.thing("file", name, computer.FOLDER if isFolder else computer.FILE, path)
				for name, _where, _size, _changed, isFolder, path in hits[:computer.MAX_FOUND]]
			for item, hit in zip(found, hits):
				item["name"] = f"{hit[0]} in {hit[1]}"
		if not found:
			raise ToolError(computer.nothingFound(asked))
		# Ids must tell the things apart.
		for number, item in enumerate(found):
			if any(other["id"] == item["id"] for other in found[:number]):
				item["id"] = f"{item['id']}-{number + 1}"
		task.things = found
		return computer.foundText(found)

	add("find_thing",
		"find what the user wants opened by its name: a program, an app, a thing on the desktop, a folder, a file of "
		"theirs, the Recycle Bin, Control Panel, or a page of Windows Settings; gives each thing's id",
		findThing, {"words": text("the name of what is to be opened, as the user said it", maxLength=120, auto=computer.wanted)},
		looks=True, title="Finding what to open")

	def openThing(task, thing, asked):
		found = getattr(task, "things", None)
		if not found:
			raise ToolError("Use find_thing first.")
		item = next((one for one in found if one["id"] == str(thing).strip()), None)
		if item is None and len(found) == 1:
			item = found[0]
		if item is None:
			raise ToolError(f"There is no thing with the id {thing}. Copy an id exactly from find_thing.")
		# Translators: Asked before VisionClaw opens a program, folder or file. {name} is its name, {kind} what it is.
		confirm(_("Open {name}, {kind}?").format(name=item["name"], kind=item["kind"]))
		try:
			shellOpen(item["target"])
		except OSError as e:
			raise ToolError(f"{item['name']} could not be opened. {e}")
		time.sleep(1.2)
		front = _safe(lambda: onMain(lambda: api.getForegroundObject().name), "") or ""
		return f"Opened {item['name']}." + (f" The window in front is now: {clip(front, 80)}." if front else "")

	add("open_thing",
		"open one thing found by find_thing, as a double click on it would: start the program, or open the folder, "
		"the file, the Recycle Bin or the settings page",
		openThing, {
			"thing": text("the id of the thing to open, from find_thing", maxLength=120),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="find_thing", title="Opening it", tell=VERBATIM)

	# The Recycle Bin.
	def binNow():
		held = binInfo()
		free, total = systemDrive()
		return held, computer.binText(held[0] if held else None, held[1] if held else 0, free, total)

	add("recycle_bin",
		"say how many things the Recycle Bin holds, how much room they take, and whether it is worth emptying",
		lambda task: binNow()[1], looks=True, title="Checking the Recycle Bin", tell=VERBATIM)

	def emptyRecycleBin(task, asked):
		held = binInfo()
		if held is None:
			raise ToolError("Windows did not say what the Recycle Bin holds, so it was left alone.")
		count, size = held
		if count <= 0:
			return "The Recycle Bin is already empty. Nothing was deleted."
		# Always asked, whatever the settings say: what is emptied cannot be brought back.
		# Translators: Asked before VisionClaw empties the Recycle Bin. {count} is the number of items, {size} their size.
		mustAgree(_(
			"Empty the Recycle Bin? It holds {count} items, {size} in all. They are deleted for good and cannot be "
			"brought back.").format(count=count, size=computer.sizeText(size)))
		try:
			emptyBin()
		except OSError as e:
			raise ToolError(str(e))
		left = binInfo()
		if left is not None and left[0] > 0:
			return (
				f"Windows emptied the Recycle Bin, but {computer.many(left[0], 'item')} are still in it. A program may "
				"be using them.")
		return f"Emptied the Recycle Bin: {computer.many(count, 'item')}, {computer.sizeText(size)}, deleted for good."

	add("empty_recycle_bin", "empty the Recycle Bin, which deletes what is in it for good; always asks first",
		emptyRecycleBin, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Emptying the Recycle Bin", tell=VERBATIM)

	# The computer's volume.
	def systemVolume(task, asked):
		wish = computer.volumeOf(asked or task.request)
		if wish is None:
			raise ToolError(
				"The request does not say what to do with the computer's volume. It can be turned up or down, set to a "
				"number of percent, muted or unmuted, or said.")
		try:
			level, muted = volumeNow()
		except OSError as e:
			raise ToolError(f"The computer's volume could not be read. {e}")
		what, _amount = wish
		if what == computer.SAY:
			return computer.volumeText(level, muted)
		if what == computer.UNMUTE:
			if not muted:
				return "The sound was not muted. " + computer.volumeText(level, muted)
			setMute(False)
			return "The sound is on again. " + computer.volumeText(level, False)
		new, held = (0, False) if what == computer.MUTE else computer.volumeNew(level, wish)
		if new < computer.QUIET:
			# NVDA speaks through the computer's sound. Without sound and without braille the user has nothing.
			if not brailleInUse():
				raise Refused(
					"Muting the computer's sound, or turning it below "
					f"{computer.QUIET} percent, would silence NVDA's speech too, and no braille display is in use. "
					+ computer.volumeText(level, muted))
			# Translators: Asked before VisionClaw mutes the computer or makes it very quiet. {level} is the new volume.
			mustAgree(_(
				"This makes the computer's sound too quiet to hear NVDA's speech: {level}. Only braille would be left. Go on?"
			).format(
				# Translators: Said in the question above when the computer's sound would be muted.
				level=_("muted") if what == computer.MUTE
				# Translators: Said in the question above when the volume would be set to a number. {number} is the number.
				else _("{number} percent").format(number=new)))
		else:
			# Translators: Asked before VisionClaw changes the computer's volume. {old} and {new} are numbers of percent.
			confirm(_("Change the computer's volume from {old} to {new} percent?").format(old=level, new=new))
		if what == computer.MUTE:
			setMute(True)
			return "The computer's sound is muted. To get it back, say: unmute the computer."
		if new == level:
			return (
				f"The computer's volume stays at {level} percent: VisionClaw does not turn it below {computer.QUIET} "
				"percent, so that NVDA's speech can still be heard. To go lower, say the number.") if held else (
				f"The computer's volume is already at {level} percent.")
		now = setVolume(new)
		if muted and what in (computer.UP, computer.SET):
			setMute(False)
		return f"The computer's volume was {level} percent and is now {now} percent." + (
			f" It was not turned lower than {computer.QUIET} percent, so that NVDA's speech can still be heard." if held else "")

	add("system_volume",
		"turn the volume of the computer itself up or down, set it to a number of percent, mute or unmute it, or say "
		"how loud it is; not the volume of NVDA's voice, which is a setting of NVDA",
		systemVolume, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Working the computer's volume", tell=VERBATIM)

	# Windows that are open.
	def listWindows(task, about):
		task.windows = openWindows()
		return computer.windowsText(task.windows)

	add("list_windows", "list the windows that are open, with the program each belongs to", listWindows,
		{"about": text("what the user asked for, in their own words", maxLength=200, auto=True)},
		looks=True, title="Listing the open windows")

	def windowAction(task, window, action, asked):
		words = asked or task.request
		if action not in computer.WINDOW_ACTIONS:
			action = computer.windowActionOf(words)
		if action == computer.MINIMIZE and computer.allWindows(words):
			# Translators: Asked before VisionClaw minimizes every window.
			confirm(_("Minimize every window and show the desktop?"))
			onMain(minimizeAll)
			return "Every window was minimized. The desktop is in front. Windows+D brings the windows back."
		windows = getattr(task, "windows", None)
		if windows is None:
			raise ToolError("Use list_windows first.")
		meant = computer.windowsMeant(words, windows)
		if len(meant) != 1:
			# The user's words name none, or several: then what the model chose from the list.
			lines = [computer.windowLine(one) for one in windows]
			reference = str(window or "").strip()
			index = next((at for at, line in enumerate(lines) if line.lower() == reference.lower()), None)
			if index is None:
				number = reference.rstrip(".")
				index = int(number) - 1 if number.isdigit() and 0 < int(number) <= len(windows) else None
			if index is None:
				picked = computer.windowsMeant(reference, windows)
				if len(picked) != 1 and action == computer.CLOSE and not meant:
					# What the user wants closed is no window of its own: a panel or a page inside the window in
					# front, as the settings of a program often are. Escape closes most of them. The window is
					# looked at before and after, so that the user is told whether anything closed.
					# Translators: Asked before VisionClaw presses Escape to close a panel inside a window.
					confirm(_(
						"No window of that name is open. It may be a panel inside the window in front. Press Escape "
						"there, which closes most panels and dialogs?"))
					box = _safe(lambda: onMain(screen.box, "window"))
					before = _safe(lambda: plugin._grab(box)) if box else None
					onMain(pressEscape)
					time.sleep(0.6)
					after = _safe(lambda: plugin._grab(box)) if box else None
					task.windows = None
					if before is None or after is None:
						return "No window of that name is open, so Escape was pressed in the window in front. Whether something closed could not be seen."
					moved = scrolling.moved(before, after) >= scrolling.MOVED_SHARE
					return "No window of that name is open, so Escape was pressed in the window in front. " + (
						"What the window shows changed, so something closed." if moved else
						"Nothing VisionClaw can see changed. It may have a Close or Back button: ask to click it.")
				if len(picked) != 1:
					raise ToolError(
						f"No open window is called \"{reference}\". Use a number or a name from list_windows.")
				meant = picked
			else:
				meant = [windows[index]]
		target = meant[0]
		name = computer.windowLine(target)
		if action == computer.CLOSE:
			# Translators: Asked before VisionClaw closes a window. {name} is its title.
			confirm(_("Close the window {name}?").format(name=name))
			gone = closeWindow(target["hwnd"])
			task.windows = None
			return f"Closed the window {name}." if gone else (
				f"The window {name} was asked to close and is still open. It may be asking whether to save something.")
		if action == computer.SWITCH:
			if focusWindow(target["hwnd"]):
				return f"Switched to the window {name}."
			raise ToolError(f"Windows did not bring the window {name} to the front. Alt+Tab switches between windows.")
		showWindow(target["hwnd"], action)
		done = {computer.MINIMIZE: "Minimized", computer.MAXIMIZE: "Maximized", computer.RESTORE: "Restored"}[action]
		return f"{done} the window {name}."

	add("window_action",
		"switch to, close, minimize, maximize or restore one of the windows from list_windows; or minimize every window",
		windowAction, {
			"window": text("the number or the name of the window, from list_windows", maxLength=120),
			"action": text("what to do with the window", enum=computer.WINDOW_ACTIONS, auto=computer.windowActionOf),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, changes=True, before="list_windows", title="Working the window", tell=VERBATIM)

	# Files in the user's own folders.
	def findFiles(task, asked):
		wish = computer.fileWish(asked or task.request)
		shown, hits, folders, cut = searchFiles(wish, task.cancel)
		task.check()
		return computer.filesText(wish, shown, folders, len(hits), cut)

	add("find_files",
		"say what is in the user's Desktop, Documents, Downloads, Pictures, Music or Videos folder, newest first, or "
		"find their files by a word of the name or by kind, such as PDF; only looks, changes nothing",
		findFiles, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		looks=True, title="Looking through your folders", tell=VERBATIM)

	# Changing the user's own files: a new folder or text file, a new name, another folder, a copy, the Recycle Bin.
	def chosenFile(job, task):
		"""The one file or folder the user means: (name, where, size, changed, isFolder, path)."""
		source = job["src"]
		if not source["words"] and not source["kinds"]:
			raise ToolError(
				"The request does not say the name of the file or folder. Say a word of its name. For the file that is "
				"selected in File Explorer, F2 renames it and Delete moves it to the Recycle Bin.")
		_shown, hits, names, cut = searchFiles(source, task.cancel)
		task.check()
		hits = computer.bestFiles(source["said"], hits)
		where = " and ".join(names) if source["named"] else "your Desktop, Documents, Downloads, Pictures, Music and Videos"
		if not hits:
			raise ToolError(
				f"No file or folder with \"{' '.join(source['words'] or source['kinds'])}\" in its name was found in {where}. "
				"Ask what is in the folder to hear the names.")
		if len(hits) == 1:
			return hits[0]
		if len(hits) > computer.MAX_TO_CHOOSE:
			raise ToolError(f"{len(hits)} files and folders in {where} fit that name. Say more of the name, or the folder it is in.")
		folders = userFolders()
		choices = [f"{name}, in {placeText(path, folders)}" for name, _where, _size, _changed, _isFolder, path in hits]
		# Translators: Asked when several files fit the name the user said. The choices are the files.
		picked = plugin.clawAsk(_("Several files fit that name. Which one do you mean?"), choices + [_("None of these")])
		task.check()
		if picked is None or picked >= len(hits):
			return None
		return hits[picked]

	def changeFile(task, asked):
		words = asked or task.request
		job = computer.fileTask(words)
		if job is None:
			raise ToolError(
				"The request does not say what to do with which file or folder. VisionClaw can make a folder or a text "
				"file, rename, move or copy a file or folder of yours, or move one to the Recycle Bin.")
		folders = userFolders()
		what = job["what"]
		if what in (computer.MAKE_FOLDER, computer.MAKE_FILE):
			name = computer.cleanName(job["new"])
			isFolder = what == computer.MAKE_FOLDER
			if not isFolder and not computer.endingOf(name):
				name += ".txt"
			kind = "folder" if isFolder else "text file"
			place = job["place"].capitalize()
			path = os.path.join(folders[job["place"]], name)
			if os.path.exists(path):
				return f"There is already something called {name} in {place}. Nothing was changed."
			# Translators: Asked before VisionClaw makes a folder or a file. {kind} is folder or text file.
			confirm(_("Make the {kind} {name} in {place}?").format(kind=kind, name=name, place=place)
				+ ("" if job["placeSaid"] else " " + _("You named no place, so it goes into Documents.")))
			try:
				os.mkdir(path) if isFolder else open(path, "x", encoding="utf-8").close()
			except OSError as e:
				raise ToolError(f"The {kind} {name} could not be made in {place}. {e}")
			plugin.changes.add("file:make", f"the {kind} {name}", "", path, "not there", f"{place}", words)
			return f"Made the {kind} {name} in {place}."
		found = chosenFile(job, task)
		if found is None:
			return "You chose none of them, so nothing was changed."
		name, _where, _size, _changed, isFolder, path = found
		if not insideOwn(path, folders):
			raise ToolError("That is not inside your own folders, so VisionClaw leaves it alone.")
		kind = "folder" if isFolder else "file"
		where = placeText(path, folders)
		if what == computer.DELETE:
			inside = ""
			if isFolder:
				count = sum(len(files) + len(dirs) for _root, dirs, files in os.walk(path))
				inside = " " + _("It is a folder with {count} things in it, and they all go with it.").format(count=count)
			# Always asked, whatever the settings say.
			# Translators: Asked before VisionClaw moves a file or folder to the Recycle Bin.
			mustAgree(_("Move the {kind} {name}, in {where}, to the Recycle Bin?").format(kind=kind, name=name, where=where)
				+ inside + " " + _("It can be brought back from there."))
			try:
				recycle(path)
			except OSError as e:
				raise ToolError(f"{name} was not deleted. {e}")
			if os.path.exists(path):
				raise ToolError(f"{name} is still in {where}: Windows did not move it to the Recycle Bin.")
			return (
				f"Moved the {kind} {name}, from {where}, to the Recycle Bin. To bring it back, open the Recycle Bin and "
				"restore it there.")
		if what == computer.RENAME:
			new = computer.renamed(name, computer.cleanName(job["new"]))
			target = os.path.join(os.path.dirname(path), new)
			if new == name:
				return f"The {kind} is already called {name}. Nothing was changed."
			if os.path.exists(target) and target.lower() != path.lower():
				return f"There is already something called {new} in {where}, so {name} was not renamed."
			# Translators: Asked before VisionClaw renames a file or folder.
			confirm(_("Rename the {kind} {name}, in {where}, to {new}?").format(kind=kind, name=name, where=where, new=new))
			try:
				os.rename(path, target)
			except OSError as e:
				raise ToolError(f"{name} could not be renamed. It may be open in a program. {e}")
			plugin.changes.add("file:rename", f"the {kind} {new}", path, target, name, new, words)
			return f"Renamed the {kind} {name}, in {where}, to {new}."
		# Moving and copying: where to.
		dest = job["dest"]
		root = folders.get(dest["key"]) if dest["key"] else None
		target = root
		if dest["words"]:
			wish = dict(computer.fileWish(""), folders=[dest["key"]] if dest["key"] else list(computer.FOLDERS), named=bool(dest["key"]),
				words=dest["words"], kinds=[], order=computer.BY_NAME)
			_shown, hits, _names, _cut = searchFiles(wish, task.cancel)
			places = [hit for hit in computer.bestFiles(" ".join(dest["words"]), [hit for hit in hits if hit[4]]) if hit[5] != path]
			if len(places) != 1:
				raise ToolError(
					(f"No folder called \"{' '.join(dest['words'])}\" was found" if not places else
						f"{len(places)} folders are called \"{' '.join(dest['words'])}\"")
					+ ". Say one of your folders, as Desktop, Documents or Downloads, or make the folder first.")
			target = places[0][5]
		if target is None:
			raise ToolError(
				f"\"{dest['said']}\" is not a folder VisionClaw knows. Say one of your folders: Desktop, Documents, Downloads, "
				"Pictures, Music or Videos, or a folder inside them by its name.")
		there = placeText(os.path.join(target, name), folders)
		goal = os.path.join(target, name)
		if os.path.abspath(target).lower() == os.path.dirname(os.path.abspath(path)).lower():
			return f"The {kind} {name} is already in {there}. Nothing was changed."
		if os.path.abspath(target).lower().startswith(os.path.abspath(path).lower() + os.sep) or os.path.abspath(target).lower() == os.path.abspath(path).lower():
			raise ToolError("A folder cannot be put into itself.")
		if os.path.exists(goal):
			return f"There is already something called {name} in {there}, so nothing was changed. Nothing is ever overwritten."
		copying = what == computer.COPY
		if copying and isFolder:
			raise ToolError("VisionClaw copies single files, not whole folders. Ask to move the folder, or copy it in File Explorer with Control+C and Control+V.")
		# Translators: Asked before VisionClaw moves or copies a file.
		confirm((_("Copy the {kind} {name} from {where} to {there}?") if copying else _("Move the {kind} {name} from {where} to {there}?")).format(
			kind=kind, name=name, where=where, there=there))
		try:
			shutil.copy2(path, goal) if copying else shutil.move(path, goal)
		except OSError as e:
			raise ToolError(f"{name} could not be {'copied' if copying else 'moved'}. It may be open in a program. {e}")
		if copying:
			return f"Copied the file {name} from {where} to {there}. To undo that, ask to delete the copy."
		plugin.changes.add("file:move", f"the {kind} {name}", path, goal, where, there, words)
		return f"Moved the {kind} {name} from {where} to {there}."

	add("change_file",
		"make a new folder or text file, rename, move or copy a file or folder of the user's, or move one to the Recycle "
		"Bin, in their Desktop, Documents, Downloads, Pictures, Music or Videos folders; asks first, overwrites nothing",
		changeFile, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Working on your file", tell=VERBATIM)

	# Facts about the computer.
	def computerInfo(task, topic):
		def programs():
			apps = []
			for window in openWindows():
				# A program whose file name says nothing, as the one that hosts the apps of Windows, is named by its title.
				app = (window["app"] or "").lower()
				name = (computer.APP_NAMES[app] or window["title"]) if app in computer.APP_NAMES else (window["app"] or window["title"])
				if name and name not in apps:
					apps.append(name)
			return ("Programs with a window open: " + ", ".join(apps) + ".") if apps else "No program has a window open."

		def uptime():
			return f"The computer has been on for {computer.spanText(upSeconds())} since it was last started."

		parts = {
			computer.DISK: lambda: computer.diskText(drives()), computer.MEMORY: lambda: computer.memoryText(*memory()),
			computer.PROCESSOR: processorText, computer.UPTIME: uptime, computer.NETWORK: networkText,
			computer.PROGRAMS: programs, computer.SYSTEM: systemText}
		if topic in parts:
			return parts[topic]()
		return " ".join(_safe(part, "") for part in (systemText, processorText, parts[computer.MEMORY], parts[computer.DISK], uptime)).strip()

	add("computer_info",
		"say a fact about the computer itself: free room on its drives, its memory, its processor, how long it has "
		"been on, whether it is connected to a network, which programs are running, its name and Windows version",
		computerInfo, {"topic": text("which fact", enum=computer.TOPICS, auto=computer.topicOf)},
		looks=True, title="Asking the computer", tell=VERBATIM)

	# Locking, sleeping, restarting, shutting down.
	def powerTool(task, asked):
		what = computer.powerOf(asked or task.request)
		if what is None:
			raise ToolError(
				"The request does not say whether to lock the computer, put it to sleep, restart it, shut it down, sign "
				"out, or call off a restart or shutdown.")
		wait = computer.POWER_WAIT
		if what != computer.CANCEL:
			# Always asked, whatever the settings say: work that is not saved can be lost, and NVDA stops speaking.
			mustAgree({
				# Translators: Asked before VisionClaw locks the computer.
				computer.LOCK: _("Lock the computer? You will need your password or PIN to get back in."),
				# Translators: Asked before VisionClaw puts the computer to sleep.
				computer.SLEEP: _("Put the computer to sleep now? NVDA is silent until you wake it."),
				# Translators: Asked before VisionClaw restarts the computer. {seconds} is how long Windows waits.
				computer.RESTART: _(
					"Restart the computer in {seconds} seconds? Work that is not saved will be lost. To call it off in "
					"that time, say: cancel the restart.").format(seconds=wait),
				# Translators: Asked before VisionClaw shuts the computer down. {seconds} is how long Windows waits.
				computer.SHUTDOWN: _(
					"Shut the computer down in {seconds} seconds? Work that is not saved will be lost. To call it off in "
					"that time, say: cancel the shutdown.").format(seconds=wait),
				# Translators: Asked before VisionClaw signs the user out of Windows.
				computer.SIGN_OUT: _("Sign out of Windows now? Every program is closed, and work that is not saved will be lost."),
			}[what])
		try:
			power(what)
		except (OSError, subprocess.SubprocessError) as e:
			if what == computer.CANCEL:
				return f"There was no restart or shutdown waiting to be called off. Windows said: {clip(str(e), 160)}"
			raise ToolError(f"Windows did not do it. {clip(str(e), 200)}")
		return {
			computer.LOCK: "The computer is locked.", computer.SLEEP: "The computer was told to sleep.",
			computer.RESTART: f"The computer restarts in {wait} seconds. To call it off, say: cancel the restart.",
			computer.SHUTDOWN: f"The computer shuts down in {wait} seconds. To call it off, say: cancel the shutdown.",
			computer.SIGN_OUT: "Signing out of Windows.", computer.CANCEL: "The restart or shutdown was called off.",
		}[what]

	add("power",
		"lock the computer, put it to sleep, restart it, shut it down, sign out of Windows, or call off a restart or "
		"shutdown that is waiting; always asks first",
		powerTool, {"asked": text("what the user asked for, in their own words", maxLength=300, auto=True)},
		changes=True, title="Locking or shutting down", tell=VERBATIM)

	# Whether something is on the screen: for a request that depends on it.
	def namesNearFocus():
		"""The names NVDA has for the things around the focus: on the desktop, its icons. Main thread."""
		names = []
		focus = api.getFocusObject()
		parent = _safe(lambda: focus.parent)
		for obj in [focus, api.getForegroundObject()] + list(_safe(lambda: parent.children[:200], []) or []):
			name = _safe(lambda: obj.name)
			if name and isinstance(name, str):
				names.append(name)
		return names

	def checkSeen(task, what, asked):
		what = " ".join(str(what or "").split()) or computer.seenWhat(asked)
		if not what:
			raise ToolError("The request does not say what to look for on the screen.")
		names = _safe(lambda: onMain(namesNearFocus), []) or []
		found = computer.seenIn(what, names)
		if found:
			return f"{computer.YES} {what} is there: NVDA finds \"{clip(found, 80)}\" where you are."
		image, _box = screen.picture("screen")
		task.check()
		lines = ocr.recognize(image) or []
		shown = [" ".join(word["text"] for word in line) for line in lines]
		found = computer.seenIn(what, shown) or computer.seenIn(what, [" ".join(shown)])
		if found:
			return f"{computer.YES} {what} is on the screen: its name is in the text that is shown."
		# Not in any text: a picture without words, as an icon. The model that sees is asked, yes or no.
		seer = policy.roleName(VISION, policy.isOneModel(plugin.runtime))
		answer = plugin.runtime.describe(
			prepareImage(image, config.conf["visionClaw"]["detailSize"]),
			f"Is this on the user's screen: {what}? Begin your answer with the one word yes or the one word no. Then say "
			"in one short sentence where it is. Say no if you are not sure.",
			60, cancel=task.cancel, system=prompts.seeing())
		task.check()
		answer = " ".join((answer or "").split())
		if answer.lower().startswith("yes"):
			return (
				f"{computer.YES} the {seer} says it sees {what} on the screen: {clip(answer, 160)} Its name is not in "
				"the text that is shown, and a model can be wrong.")
		return f"{computer.NO} {what} is not on the screen: its name is not in the text that is shown, and the {seer} does not see it."

	add("check_seen",
		"check whether something the user names is on the screen: by the names NVDA has, the text that is shown, and "
		"the picture; answers yes or no",
		checkSeen, {
			"what": text("the thing to look for, as the user named it", maxLength=80, auto=computer.seenWhat),
			"asked": text("what the user asked for, in their own words", maxLength=300, auto=True),
		}, looks=True, title="Checking whether it is on the screen", tell=VERBATIM)
