# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Whether Windows really takes the fingers and the pen that VisionClaw makes. This is the one test that
touches the real computer, so it does nothing unless it is told to:

    python tests/live_touch.py            says what it would do, and does nothing
    python tests/live_touch.py --window   only opens and closes its own small window; nothing is touched
    python tests/live_touch.py --yes      really touches and presses, inside its own window only

With --yes it opens a small window of its own in the top left corner of the main screen, which never takes
the focus. Inside that window, and nowhere else, it has Windows touch the screen with two fingers that
pinch, and press with a pen whose pressure rises. The window writes down what Windows then tells it: how
many fingers, a pen or not, and how hard. Then it closes. Windows may put the mouse pointer away while the
touch lasts; moving the mouse brings it back. NVDA says nothing, because the focus does not move; on a
computer with a touch screen and NVDA's touch support on, NVDA takes the fingers for itself and the window
sees none, which is why VisionClaw puts NVDA's touch support aside for a gesture.
Read what it prints: "pinch" must show two fingers that came closer, and "pen" a pressure that rose.
"""
import ctypes
import logging
import sys
import threading
import time
import types
from ctypes import wintypes

# The add-on's file needs NVDA's log; here Python's own stands in.
logger = logging.getLogger("live_touch")
logger.debugWarning = logger.warning
sys.modules.setdefault("logHandler", types.SimpleNamespace(log=logger))

import harness  # noqa: E402,F401
from visionClaw import touchinput  # noqa: E402
from visionClaw.claw import touch  # noqa: E402

LEFT, TOP, WIDTH, HEIGHT = 40, 40, 420, 320
WM_CLOSE, WM_DESTROY = 0x0010, 0x0002
WM_POINTERUPDATE, WM_POINTERDOWN, WM_POINTERUP = 0x0245, 0x0246, 0x0247
WS_POPUP, WS_VISIBLE = 0x80000000, 0x10000000
WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x00000008, 0x00000080, 0x08000000
PT_TOUCH, PT_PEN = 2, 3

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
	wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
	ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


class WNDCLASSEXW(ctypes.Structure):
	_fields_ = [
		("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
		("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HANDLE),
		("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE), ("lpszMenuName", wintypes.LPCWSTR),
		("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HANDLE)]


# What the window was told: (what happened, which finger or pen, its kind, how hard, where).
seen = []


def windowProc(hwnd, message, wParam, lParam):
	if message in (WM_POINTERDOWN, WM_POINTERUPDATE, WM_POINTERUP):
		pointer = wParam & 0xFFFF
		kind = ctypes.c_uint32()
		user32.GetPointerType(pointer, ctypes.byref(kind))
		pressure, x, y = 0, 0, 0
		if kind.value == PT_TOUCH:
			info = touchinput._POINTER_TOUCH_INFO()
			if user32.GetPointerTouchInfo(pointer, ctypes.byref(info)):
				pressure, x, y = info.pressure, info.pointerInfo.ptPixelLocation.x, info.pointerInfo.ptPixelLocation.y
		elif kind.value == PT_PEN:
			info = touchinput._POINTER_PEN_INFO()
			if user32.GetPointerPenInfo(pointer, ctypes.byref(info)):
				pressure, x, y = info.pressure, info.pointerInfo.ptPixelLocation.x, info.pointerInfo.ptPixelLocation.y
		what = {WM_POINTERDOWN: "down", WM_POINTERUPDATE: "move", WM_POINTERUP: "up"}[message]
		seen.append((what, pointer, kind.value, pressure, x, y))
		return 0
	if message == WM_DESTROY:
		user32.PostQuitMessage(0)
		return 0
	return user32.DefWindowProcW(hwnd, message, wParam, lParam)


def openWindow():
	"""A small window of this test's own, on top, that never takes the focus."""
	proc = WNDPROC(windowProc)
	instance = kernel32.GetModuleHandleW(None)
	cls = WNDCLASSEXW()
	cls.cbSize, cls.lpfnWndProc, cls.hInstance, cls.lpszClassName = ctypes.sizeof(WNDCLASSEXW), proc, instance, "VisionClawLiveTouch"
	cls.hbrBackground = 6  # the colour of a plain window
	if not user32.RegisterClassExW(ctypes.byref(cls)):
		raise ctypes.WinError(ctypes.get_last_error())
	hwnd = user32.CreateWindowExW(
		WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, "VisionClawLiveTouch", "VisionClaw touch test",
		WS_POPUP | WS_VISIBLE, LEFT, TOP, WIDTH, HEIGHT, None, None, instance, None)
	if not hwnd:
		raise ctypes.WinError(ctypes.get_last_error())
	return hwnd, proc  # the procedure must be kept, or Python frees it while Windows still calls it


def pump(hwnd, work):
	"""Run the window until the work is done, then close it."""
	failed = []

	def run():
		try:
			time.sleep(0.4)
			work()
			time.sleep(0.4)
		except Exception as e:
			failed.append(e)
		finally:
			user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)

	threading.Thread(target=run, daemon=True).start()
	message = wintypes.MSG()
	while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
		user32.TranslateMessage(ctypes.byref(message))
		user32.DispatchMessageW(ctypes.byref(message))
	if failed:
		raise failed[0]


def main():
	box = (LEFT, TOP, LEFT + WIDTH, TOP + HEIGHT)
	place = (LEFT + WIDTH // 2, TOP + HEIGHT // 2)
	if "--yes" not in sys.argv and "--window" not in sys.argv:
		print(__doc__)
		print(f"It would touch and press only inside the window at {box} on the main screen. Nothing was done.")
		return
	hwnd, proc = openWindow()
	if "--yes" not in sys.argv:
		pump(hwnd, lambda: None)
		print("The window was opened and closed. Nothing was touched.")
		return
	pinch = touch.touchOf("pinch with two fingers")
	line = touch.penOf("draw a line to the right with the pressure rising")
	results = {}

	def work():
		before = len(seen)
		try:
			touchinput.fingers(touch.strokes(pinch, place, box), pinch["pressure"])
			results["pinch"] = "done"
		except touchinput.Refused as e:
			results["pinch"] = f"refused: {e}"
		time.sleep(0.5)
		results["pinchSeen"] = seen[before:]
		before = len(seen)
		try:
			touchinput.strokesWithPen(touch.penStrokes(line, place, box), False, 0.012)
			results["pen"] = "done"
		except touchinput.Refused as e:
			results["pen"] = f"refused: {e}"
		time.sleep(0.5)
		results["penSeen"] = seen[before:]

	pump(hwnd, work)
	touchinput.close()
	fingers = results.get("pinchSeen", [])
	touching = [entry for entry in fingers if entry[2] == PT_TOUCH]
	ids = sorted({entry[1] for entry in touching})
	print(f"pinch: {results.get('pinch')}. The window was told of {len(touching)} touches by {len(ids)} fingers.")
	if len(ids) >= 2:
		first = [entry for entry in touching if entry[0] == "down"]
		last = [entry for entry in touching if entry[0] == "up"]
		if len(first) >= 2 and len(last) >= 2:
			print(f"  They began {abs(first[0][4] - first[1][4])} pixels apart and ended {abs(last[0][4] - last[1][4])} pixels apart.")
		print(f"  How hard they pressed, as Windows reports it: {sorted({entry[3] for entry in touching})}")
	strokes = [entry for entry in results.get("penSeen", []) if entry[2] == PT_PEN]
	print(f"pen: {results.get('pen')}. The window was told of {len(strokes)} pen reports.")
	if strokes:
		pressures = [entry[3] for entry in strokes if entry[0] != "up"]
		print(f"  Its pressure went from {pressures[0]} to {max(pressures)} of {touch.FULL}, over {len(pressures)} reports.")
	other = [entry for entry in seen if entry[2] not in (PT_TOUCH, PT_PEN)]
	if other:
		print(f"  {len(other)} reports were of another kind, such as the mouse: {sorted({entry[2] for entry in other})}")
	ok = len(ids) >= 2 and len(strokes) > 5 and max(entry[3] for entry in strokes) > strokes[0][3]
	print("Windows took the fingers and the pen as VisionClaw makes them." if ok else "NOT AS EXPECTED: read the lines above.")


if __name__ == "__main__":
	main()
