# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""NVDA's own log, read by plain code (claw/nvdalog.py), with made-up logs in NVDA's own form. Plain Python.

What is checked: what the user's words ask, and that nothing else is taken; that entries of the levels IO, DEBUG and
DEBUG_UNREDACTED keep nothing and reach no sentence and no model; errors grouped, with the add-on they come from; freezes
and where NVDA was working; the speech synthesizer, the sound and the braille display; how a run ended; what NVDA wrote in
a stretch of time; the logging level and the log turned off; the planner's routing; the skills. The real nvda.log of this
computer is never read.

  python tests/test_nvdalog.py
"""
import re
import tempfile
import time

import harness  # noqa: F401
from visionClaw.claw import nvdalog, planner, skills

# --- What the user's own words ask ---

ASKS = {
	"check NVDA's log": nvdalog.ERRORS,
	"has nvda had any errors today": nvdalog.ERRORS,
	"any errors in nvda": nvdalog.ERRORS,
	"what's in nvda's log": nvdalog.ERRORS,
	"why does nvda keep making an error sound": nvdalog.ERRORS,
	"why did that error happen in NVDA's log": nvdalog.EXPLAIN,
	"explain NVDA error 2": nvdalog.EXPLAIN,
	"what does the first error in NVDA's log mean": nvdalog.EXPLAIN,
	"which add-on is causing errors": nvdalog.ADDONS,
	"is an add-on breaking NVDA": nvdalog.ADDONS,
	"which addon makes nvda slow": nvdalog.ADDONS,
	"errors from the clock add-on in nvda's log": nvdalog.ADDONS,
	"NVDA froze": nvdalog.FREEZES,
	"why does nvda keep freezing": nvdalog.FREEZES,
	"how often does nvda freeze": nvdalog.FREEZES,
	"nvda keeps lagging": nvdalog.FREEZES,
	"nvda stopped responding again": nvdalog.FREEZES,
	"why did my braille display disconnect": nvdalog.DRIVERS,
	"did my synthesizer fail": nvdalog.DRIVERS,
	"any synthesizer errors in NVDA's log": nvdalog.DRIVERS,
	"did NVDA crash": nvdalog.LAST_RUN,
	"why did nvda crash": nvdalog.LAST_RUN,
	"what happened the last time nvda closed": nvdalog.LAST_RUN,
	"why does nvda keep crashing": nvdalog.LAST_RUN,
	"read nvda-old.log": nvdalog.LAST_RUN,
	"what just happened in nvda": nvdalog.RECENT,
	"what did nvda just log": nvdalog.RECENT,
	"what was nvda doing just now": nvdalog.RECENT,
	"anything new in nvda's log": nvdalog.RECENT,
	"what did nvda log since my last request": nvdalog.RECENT,
	"what is NVDA's logging level": nvdalog.LEVEL,
	"is nvda logging my keystrokes": nvdalog.LEVEL,
	"is nvda's log on": nvdalog.LEVEL,
	"turn on NVDA's logging": nvdalog.SETTINGS,
	"how do I turn on NVDA's log": nvdalog.SETTINGS,
	"set nvda's logging level to debug": nvdalog.SETTINGS,
	"where do I change the logging level": nvdalog.SETTINGS,
	"where is nvda's log file": nvdalog.WHERE,
}
for said, do in ASKS.items():
	want = nvdalog.wish(said)
	assert want and want["do"] == do, (said, want)
assert nvdalog.wish("what just happened in nvda")["since"] == nvdalog.JUST
assert nvdalog.wish("what did nvda log since my last request")["since"] == nvdalog.SINCE_REQUEST
assert nvdalog.wish("anything new in nvda's log")["since"] == nvdalog.SINCE_READ
assert nvdalog.wish("explain NVDA error 2")["which"] == 2
assert nvdalog.wish("what does the first error in NVDA's log mean")["which"] == 1
assert "clock" in nvdalog.wish("errors from the clock add-on in nvda's log")["about"]
# Everything else is no wish: VisionClaw's own log, NVDA's log viewer and its keys, a setting, a question about VisionClaw.
for said in (
		"what errors are in your log", "show me your log", "open your log file", "open the visionclaw log", "turn off visionclaw's log",
		"why did my last request fail", "what errors have you had", "open NVDA's log", "open the nvda log viewer",
		"what's the key to open NVDA's log", "what does NVDA+F1 do", "turn off the nvda error sound", "which add-ons do I have",
		"which of my addons are switched off", "which add-on can help me read error messages", "fix the add-on",
		"my beeping add-on is broken, sort it out", "the add-on you made doesn't work, fix it", "what does the error message say",
		"read the error message in this dialog", "hang up the call", "how do I hang up a call in teams", "nvda is too slow",
		"is there an nvda setting for audio lag", "NVDA stopped talking in Word", "my braille display stopped working",
		"does visionclaw change nvda's logging level", "how does visionclaw read nvda's log", "what time is it", "", None):
	assert nvdalog.wish(said) is None, (said, nvdalog.wish(said))

# --- The planner: NVDA's log is its own job; VisionClaw's own log and NVDA's keys stay where they were ---

for said in ASKS:
	assert planner.hint(said) == "nvda_log", (said, planner.hint(said))
	assert planner._NEEDS["nvda_log"](said) is not None
for said, job in (
		("what errors are in your log", "own_errors"), ("why did my last request fail", "own_errors"),
		("show me your log", "visionclaw_log"), ("open your log file", "visionclaw_log"), ("open the nvda log viewer", "do_command"),
		("what's the key to open NVDA's log", "explain_keys"), ("what does NVDA+F1 do", "nvda_question"),
		("turn off the nvda error sound", "change_setting"), ("which add-ons do I have", "nvda_info"),
		("fix the add-on", "fix_addon"), ("what does the error message say", "read_text")):
	assert planner.hint(said) == job, (said, planner.hint(said))
# Nothing is offered to a model for words that do not ask for NVDA's log, and the job is sure where they do.
assert planner._NEEDS["nvda_log"]("turn off typing echo") is None
assert "nvda_log" in planner._SURE and "nvda_log" in planner._WHOLE and "nvda_log" in planner._ANSWERS
assert planner.RECIPES["nvda_log"][2] == ("nvda_log",)

# --- Made-up logs in NVDA's own form (logHandler.Formatter) ---

ADDONS = r"C:\Users\sam\AppData\Roaming\nvda\addons"
PRIVATE_WORDS = ("hunter2", "SECRETTOKEN123", "kb(desktop):p", "Speaking", "my secret password", "Braille window dots")
CURRENT = rf"""INFO - __main__ (09:00:00.100) - MainThread (1000):
Starting NVDA version 2026.3.1 AMD64
INFO - core.main (09:00:00.500) - MainThread (1000):
Config dir: C:\Users\sam\AppData\Roaming\nvda
INFO - core.main (09:00:01.000) - MainThread (1000):
Windows version: Windows 11 24H2 (10.0.26100) workstation
INFO - synthDriverHandler.setSynth (09:00:02.000) - MainThread (1000):
Loaded synthDriver oneCore
INFO - braille.brailleHandler.BrailleHandler._setDisplay (09:00:02.100) - MainThread (1000):
Loaded braille display driver 'noBraille', current display has 0 cells.
INFO - core.main (09:00:03.000) - MainThread (1000):
NVDA initialized
IO - inputCore.InputManager.executeGesture (09:01:00.000) - Thread-5 (_run) (1500):
Input: kb(desktop):p
IO - speech.speech.speak (09:01:00.100) - MainThread (1000):
Speaking ['my secret password is hunter2']
DEBUG - someModule.f (09:01:01.000) - MainThread (1000):
token=SECRETTOKEN123
ERROR - Exception ignored in: <function f at 0x000001> (09:01:01.500) - MainThread (1000):
DEBUG_UNREDACTED - someModule.g (09:01:02.000) - MainThread (1000):
password hunter2
Level 7 - someModule.h (09:01:02.500) - MainThread (1000):
Braille window dots: 1 2 3 hunter2
ERROR - external:globalPlugins.clock.GlobalPlugin.script_sayTime (09:02:00.000) - MainThread (1000):
Error in script_sayTime
Traceback (most recent call last):
  File "scriptHandler.pyc", line 300, in executeScript
  File "{ADDONS}\clock\globalPlugins\clock\__init__.py", line 42, in script_sayTime
    self.speakTime()
  File "{ADDONS}\clock\globalPlugins\clock\__init__.py", line 60, in speakTime
    return int(text)
ValueError: invalid literal for int() with base 10: 'ten'
ERROR - external:globalPlugins.clock.GlobalPlugin.script_sayTime (09:03:00.000) - MainThread (1000):
Error in script_sayTime
Traceback (most recent call last):
  File "scriptHandler.pyc", line 300, in executeScript
  File "{ADDONS}\clock\globalPlugins\clock\__init__.py", line 42, in script_sayTime
    self.speakTime()
  File "{ADDONS}\clock\globalPlugins\clock\__init__.py", line 60, in speakTime
    return int(text)
ValueError: invalid literal for int() with base 10: 'eleven'
ERROR - external:globalPlugins.weather.GlobalPlugin.event_gainFocus (09:03:30.000) - MainThread (1000):
The weather could not be read
ERROR - speech.speech.speak (09:04:00.000) - MainThread (1000):
Error in speech
Traceback (most recent call last):
  File "speech\speech.pyc", line 10, in speak
TypeError: an int was wanted
WARNING - nvwave.WavePlayer.open (09:05:00.000) - MainThread (1000):
Couldn't open specified or default audio device. There may be no audio devices.
ERROR - synthDriverHandler.setSynth (09:05:01.000) - MainThread (1000):
setSynth failed for sapi5
Traceback (most recent call last):
  File "synthDriverHandler.pyc", line 520, in setSynth
OSError: [WinError -2147221164] Class not registered
INFO - synthDriverHandler.setSynth (09:05:01.100) - MainThread (1000):
Falling back to previous synthDriver oneCore
INFO - synthDriverHandler.setSynth (09:05:01.200) - MainThread (1000):
Loaded synthDriver oneCore
INFO - watchdog.waitForFreezeRecovery (09:06:00.000) - watchdog (2000):
Starting freeze recovery after 10.5 seconds.
ERROR - watchdog.waitForFreezeRecovery (09:06:15.000) - watchdog (2000):
Core frozen in stack! (25.6 seconds)
INFO - watchdog.waitForFreezeRecovery (09:06:15.001) - watchdog (2000):
Listing stacks for Python threads:
Python stack for thread 1000 (MainThread):
  File "nvda.pyw", line 300, in <module>
  File "core.pyc", line 900, in main
  File "{ADDONS}\slowThing\appModules\notepad.py", line 12, in event_gainFocus
    time.sleep(30)

Python stack for thread 2000 (watchdog):
  File "watchdog.pyc", line 190, in _watcher
INFO - watchdog.waitForFreezeRecovery (09:06:30.000) - watchdog (2000):
Recovered from freeze after 40.2 seconds.
ERROR - braille.brailleHandler.BrailleHandler.handleDisplayUnavailable (09:07:00.000) - MainThread (1000):
Braille display unavailable. Disabling
Traceback (most recent call last):
  File "braille\brailleHandler.pyc", line 610, in _writeCells
OSError: the device is gone
INFO - external:globalPlugins.visionClaw.GlobalPlugin.script_ask (09:08:00.000) - MainThread (1000):
VisionClaw: a request began
INFO - config.ConfigManager.save (09:08:30.000) - MainThread (1000):
Base configuration saved
"""
NAMES = {"clock": "Clock and Calendar", "slowThing": "Slow Thing", "weather": "Weather Plus", "visionClaw": "VisionClaw"}
MODULES = {"globalPlugins.clock": "clock", "appModules.notepad": "slowThing", "globalPlugins.weather": "weather",
	"globalPlugins.visionClaw": "visionClaw"}

entries = nvdalog.parse(CURRENT)
assert len(entries) == 27, len(entries)
# Privacy: an entry of a private level keeps no line, no codepath and no thread name; "Level 7" is not a level that is read.
private = [entry for entry in entries if entry.private]
assert {entry.level for entry in private} == {"IO", "DEBUG", "DEBUG_UNREDACTED", "Level 7"}
assert all(entry.lines == [] and entry.codepath == "" and entry.thread == "" for entry in private)
assert nvdalog.counted(entries) == {"IO": 2, "DEBUG": 1, "DEBUG_UNREDACTED": 1, "Level 7": 1}
assert nvdalog.privateText(entries).startswith("5 entries of the levels that hold what you type")
# A line of what was typed never stands in an entry that is read; should one, it is left out all the same.
leaked = nvdalog.parse("INFO - x.y (10:00:00.000) - MainThread (1):\nnoted\nInput: kb(desktop):p\n")
assert leaked[0].lines == ["noted", ""]
# Lines before the first entry (the end of a large file was read) are left out.
assert nvdalog.parse("line cut in two\nINFO - x.y (10:00:00.000) - MainThread (1):\nNVDA initialized\n")[0].message == "NVDA initialized"
# A thread's name with parentheses of its own.
assert entries[6].clock == "09:01:00.000" and entries[6].level == "IO"

# --- Errors, grouped, newest first, with the add-on they come from ---

problems = nvdalog.errors(entries, MODULES)
assert [problem.message for problem in problems] == [
	"The braille display stopped answering, so NVDA stopped using it", "The speech synthesizer sapi5 could not be started",
	"Error in speech", "The weather could not be read", "Error in script_sayTime", "Python could not finish cleaning up something"], problems
assert [problem.kind for problem in problems] == ["brailleGone", "synthFailed", "error", "error", "error", "error"]
clock = problems[4]
assert clock.count == 2 and clock.first == "09:02:00" and clock.last == "09:03:00" and clock.addon == "clock"
assert clock.exception == "ValueError: invalid literal for int() with base 10: 'eleven'"
assert nvdalog.addonPlace(clock.frames, "clock") == ("globalPlugins/clock/__init__.py", 60, "speakTime")
# An add-on's own log.error, with no traceback, is told by its module (the add-on's folders, from the running NVDA).
assert problems[3].addon == "weather" and nvdalog.addonOfCodepath("external:globalPlugins.weather.GlobalPlugin.x", MODULES) == "weather"
assert problems[3].addon and nvdalog.addonOfCodepath("external:globalPlugins.weatherTwo.x", MODULES) == ""
assert nvdalog.addonOfPath(r"C:\x\nvda\addons\clock.pendingInstall\globalPlugins\clock.py") == "clock"
assert nvdalog.byAddon(problems) == [("clock", 2, 1), ("weather", 1, 1)]
said = nvdalog.errorsText(problems, NAMES)
assert said.startswith("NVDA's log of this run has 6 different errors, 7 in all, the newest first.\n"
	"Of the 7 errors, 2 from Clock and Calendar (clock), 1 from Weather Plus (weather), and 4 in NVDA's own code.\n"
	"1. The braille display stopped answering, so NVDA stopped using it. Once, at 09:07:00. In NVDA's own part for braille.\n"
	"2. The speech synthesizer sapi5 could not be started. Once, at 09:05:01. In NVDA's own part for the speech synthesizer.\n"), said
assert ("5. Error in script_sayTime. 2 times, the first at 09:02:00 and the last at 09:03:00. From the add-on Clock and Calendar "
	"(clock), in its function speakTime.\n") in said
assert said.endswith("To hear what one of them means, ask VisionClaw to explain NVDA's error by its number.")
# A list says no code and no file path; one error asked about says both.
assert "Python's error" not in said and "__init__" not in said and "0x" not in said
detail = nvdalog.problemText(problems[4], NAMES, detail=True)
assert detail.endswith("From the add-on Clock and Calendar (clock), in its function speakTime, in the main file of its folder "
	"globalPlugins/clock, line 60. Python's error: ValueError: invalid literal for int() with base 10: 'eleven'"), detail
assert nvdalog.partOf("virtualBuffers.gecko_ia2.Gecko_ia2.x") == "browse mode" and nvdalog.partOf("unhandled exception") == (
	"an error nothing caught")
# A freeze and a crash are told apart, not as errors.
assert all("Core frozen" not in problem.message for problem in problems)
said = nvdalog.addonsText(problems, nvdalog.freezes(entries, MODULES), NAMES)
assert said.startswith("Errors in NVDA's log of this run that come from add-ons, the most first:\n1. Clock and Calendar (clock): "
	"2 errors. The newest, at 09:03:00: Error in script_sayTime.\n2. Weather Plus (weather): 1 error."), said
assert "4 more errors happened in NVDA's own code." in said
assert "While NVDA was frozen, it was working in the add-on Slow Thing (slowThing), once." in said
assert "VisionClaw never turns one off itself." in said
# One add-on named in the words: its errors alone.
named = nvdalog.addonsText(problems, [], NAMES, about="clock")
assert named.startswith("From the add-on Clock and Calendar (clock), NVDA's log of this run has one error, 2 times."), named
assert nvdalog.addonNamed("weather", NAMES) == "weather" and nvdalog.addonNamed("speech", NAMES) == ""
assert nvdalog.addonName("visionClaw", NAMES) == "VisionClaw itself"
# The error a request is about: by its number, by an add-on, else the newest.
assert nvdalog.chosen(problems, {"which": 5}) is clock and nvdalog.chosen(problems, {"which": None, "about": "clock"}, NAMES) is clock
assert nvdalog.chosen(problems, {"which": None, "about": ""}) is problems[0] and nvdalog.chosen([], {}) is None
# What a model is told of one error: the error alone, never a private line.
told = nvdalog.modelFacts(clock, NAMES)
assert told.startswith("Error in NVDA's log: Error in script_sayTime\nPython's error: ValueError") and "Clock and Calendar" in told
assert "globalPlugins/clock/__init__.py line 60 in speakTime" in told
assert nvdalog.EXPLAIN_TASK.startswith("You are VisionClaw") and "for example" not in nvdalog.EXPLAIN_TASK.lower()

# --- Freezes ---

found = nvdalog.freezes(entries, MODULES)
assert len(found) == 1 and found[0].severe and found[0].recovered == 40.2 and found[0].addon == "slowThing"
assert found[0].function == "event_gainFocus" and found[0].clock == "09:06:00"
said = nvdalog.freezesText(found, NAMES)
assert said == ("NVDA's log of this run shows one time that NVDA stopped responding.\nIt lasted about 40 seconds, from 09:06:00.\n"
	"It was long enough for NVDA to write that its core was frozen.\nWhile NVDA was frozen it was working in the add-on Slow "
	"Thing (slowThing)."), said
assert nvdalog.freezesText([], NAMES) == "NVDA's log of this run shows no time that NVDA stopped responding."
short = nvdalog.freezes(nvdalog.parse(
	"INFO - watchdog.w (10:00:00.000) - watchdog (2):\nStarting freeze recovery after 1.5 seconds.\n"
	"INFO - watchdog.w (10:00:02.000) - watchdog (2):\nRecovered from freeze after 2.0 seconds.\n"))
assert "is written only after a freeze of more than 15 seconds" in nvdalog.freezesText(short)

# --- The speech synthesizer, the sound and the braille display ---

drivers = nvdalog.driverFacts(entries, modules=MODULES)
said = nvdalog.driversText(drivers, "INFO")
assert said.startswith("Trouble with the speech synthesizer or the sound output or the braille display in NVDA's log of this "
	"run, in the order it happened:\nAt 09:05:00: NVDA could not open the sound output device that was chosen, or the default "
	"one; there may be no sound device.\nAt 09:05:01: The speech synthesizer sapi5 could not be started. The reason NVDA wrote: "
	"OSError: [WinError -2147221164] Class not registered\nAt 09:05:01: NVDA went back to the speech synthesizer it had before, "
	"oneCore.\nAt 09:07:00: The braille display stopped answering, so NVDA stopped using it. The reason NVDA wrote: OSError: the "
	"device is gone"), said
assert "The last speech synthesizer NVDA loaded, at 09:05:01, is oneCore." in said
assert "NVDA is set to no braille display." in said
assert "from the level Debug warning" in said
assert nvdalog.groupsAsked("why did my braille display disconnect") == (nvdalog.BRAILLE,)
assert nvdalog.groupsAsked("did my synthesizer fail") == (nvdalog.SPEECH,)
braille = nvdalog.driversText(nvdalog.driverFacts(entries, (nvdalog.BRAILLE,), MODULES), "DEBUGWARNING", groups=(nvdalog.BRAILLE,))
assert braille.startswith("Trouble with the braille display") and "sapi5" not in braille and "Debug warning" not in braille

# --- How a run ended (nvda-old.log) ---

CRASHED = rf"""INFO - __main__ (22:00:00.000) - MainThread (100):
Starting NVDA version 2026.3.1 AMD64
INFO - core.main (22:00:01.000) - MainThread (100):
Windows version: Windows 11
INFO - core.main (22:00:02.000) - MainThread (100):
NVDA initialized
IO - inputCore.InputManager.executeGesture (23:59:58.000) - MainThread (100):
Input: kb(desktop):hunter2
ERROR - external:globalPlugins.clock.GlobalPlugin.event_gainFocus (23:59:59.000) - MainThread (100):
Error in event_gainFocus
Traceback (most recent call last):
  File "{ADDONS}\clock\globalPlugins\clock\__init__.py", line 80, in event_gainFocus
KeyError: 'name'
CRITICAL - watchdog._crashHandler (23:59:59.500) - MainThread (100):
NVDA crashed! Minidump written to C:\Users\sam\AppData\Local\Temp\nvda_crash.dmp
INFO - watchdog._crashHandler (00:00:00.100) - MainThread (100):
Listing stacks for Python threads:
Python stack for thread 100 (MainThread):
  File "{ADDONS}\clock\globalPlugins\clock\__init__.py", line 81, in event_gainFocus
INFO - watchdog._crashHandler (00:00:00.200) - MainThread (100):
Restarting due to crash
"""
old = nvdalog.parse(CRASHED)
end = nvdalog.ending(old, MODULES, NAMES)
assert end["how"] == nvdalog.CRASHED and end["version"] == "2026.3.1" and end["started"] == "22:00:00"
assert end["said"] == ("NVDA crashed, at 23:59:59. When it crashed, NVDA's main thread was working in the add-on Clock and "
	"Calendar (clock). It then restarted itself."), end
said = nvdalog.lastRunText(old, NAMES, MODULES)
assert said.startswith("The run before this one was NVDA 2026.3.1, started at 22:00:00.\nNVDA crashed, at 23:59:59."), said
assert ("It had 1 error. Of the 1 errors, 1 from Clock and Calendar (clock).\nThe last error, at 23:59:59: Error in "
	"event_gainFocus. From the add-on Clock and Calendar (clock), in its function event_gainFocus") in said, said
assert "Its last entries, the last one last: " in said and "At 00:00:00: NVDA restarted itself after the crash." in said
assert said.endswith("1 entry of the levels that hold what you type, what NVDA says and NVDA's debug notes was only counted; "
	"VisionClaw never reads them.")
# The date is worked out backwards: the crash just before midnight is on the day before the last entry.
lastWritten = time.mktime((2026, 11, 19, 0, 0, 1, 0, 0, -1))
nvdalog.stamp(old, lastWritten)
assert time.localtime(old[-1].when)[:3] == (2026, 11, 19) and time.localtime(old[5].when)[:3] == (2026, 11, 18)
assert time.localtime(old[0].when)[3:5] == (22, 0)
NORMAL = ("INFO - __main__ (08:00:00.000) - MainThread (1):\nStarting NVDA version 2026.3.1 AMD64\n"
	"INFO - core.main (08:00:01.000) - MainThread (1):\nWindows version: Windows 11\n"
	"INFO - core.main (08:00:02.000) - MainThread (1):\nNVDA initialized\n"
	"INFO - core.main (18:00:00.000) - MainThread (1):\nExiting\n"
	"INFO - __main__ (18:00:01.000) - MainThread (1):\nNVDA exit\n")
assert nvdalog.ending(nvdalog.parse(NORMAL))["said"] == "NVDA closed normally, at 18:00:01."
assert nvdalog.lastRunText(nvdalog.parse(NORMAL)).split("\n")[2] == "It had no errors."
WINDOWS = NORMAL.replace("Exiting\n", "Windows session ending\n").replace("INFO - __main__ (18:00:01.000) - MainThread (1):\nNVDA exit\n", "")
assert nvdalog.ending(nvdalog.parse(WINDOWS))["how"] == nvdalog.WINDOWS_ENDED
FROZEN = NORMAL.split("INFO - core.main (18:00:00.000)")[0] + (
	"INFO - watchdog.w (17:00:00.000) - watchdog (2):\nStarting freeze recovery after 10.0 seconds.\n"
	"ERROR - watchdog.w (17:00:15.000) - watchdog (2):\nCore frozen in stack! (25.0 seconds)\n")
end = nvdalog.ending(nvdalog.parse(FROZEN))
assert end["how"] == nvdalog.FROZE and end["said"].startswith("NVDA was frozen from 17:00:00 until its log ends, at 17:00:15")
assert "has no recovery written after it" in nvdalog.freezesText(nvdalog.freezes(nvdalog.parse(FROZEN)), run="the run before")
LOG_OFF = ("INFO - __main__ (08:00:00.000) - MainThread (1):\nStarting NVDA version 2026.3.1 AMD64\n"
	"INFO - core.main (08:00:00.500) - MainThread (1):\nConfig dir: C:\\Users\\sam\\AppData\\Roaming\\nvda\n")
assert nvdalog.ending(nvdalog.parse(LOG_OFF))["how"] == nvdalog.LOG_OFF
CUT_OFF = NORMAL.split("INFO - core.main (18:00:00.000)")[0]
end = nvdalog.ending(nvdalog.parse(CUT_OFF))
assert end["how"] == nvdalog.NOT_TOLD and "without NVDA's last line, NVDA exit" in end["said"]
assert nvdalog.lastRunText([]) == "NVDA's log of the run before, nvda-old.log, is not there or is empty."

# --- What NVDA wrote in a stretch of time ---

nvdalog.stamp(entries, time.mktime((2026, 11, 19, 9, 10, 0, 0, 0, -1)))
begun = time.mktime((2026, 11, 19, 9, 8, 40, 0, 0, -1))
start, until, stretch = nvdalog.window(nvdalog.JUST, begun, previousEnd=None)
assert until == begun and start == begun - nvdalog.JUST_NOW and stretch == "in the 2 minutes before you asked"
recent = nvdalog.entriesSince(entries, start, until)
assert recent and recent[0].clock >= "09:06:40" and recent[-1].clock <= "09:08:40", recent
said = nvdalog.recentText(recent, stretch, MODULES, NAMES)
assert said == ("What NVDA wrote to its log in the 2 minutes before you asked, in order:\nAt 09:07:00: The braille display stopped "
	"answering, so NVDA stopped using it. The reason NVDA wrote: OSError: the device is gone.\nAt 09:08:30: NVDA saved its "
	"settings.\n1 entry written by VisionClaw itself is left out."), said
previous = time.mktime((2026, 11, 19, 9, 4, 30, 0, 0, -1))
start, until, stretch = nvdalog.window(nvdalog.SINCE_REQUEST, begun, previous)
assert start == previous and stretch.startswith("since your last request ended, at 09:04:30")
said = nvdalog.recentText(nvdalog.entriesSince(entries, start, until), stretch, MODULES, NAMES)
assert said.split("\n")[1] == ("At 09:05:00: NVDA could not open the sound output device that was chosen, or the default one; there "
	"may be no sound device."), said
assert "At 09:06:00: NVDA stopped responding, and began to recover after about 10 seconds." in said
assert "1 entry written by VisionClaw itself is left out." in said and "VisionClaw: a request began" not in said
assert "At 09:06:30: NVDA recovered after being frozen for about 40 seconds." in said
assert nvdalog.recentText([], "just now") == "NVDA wrote nothing to its log just now."
facts = nvdalog.facts(entries, MODULES)
assert facts[0] == {"clock": "09:00:00", "when": entries[0].when, "level": "INFO", "kind": "started", "group": nvdalog.START,
	"said": "NVDA 2026.3.1 started.", "addon": ""}
assert all(fact["level"] in nvdalog.READ for fact in facts)
assert [fact["kind"] for fact in facts if fact["group"] == nvdalog.SPEECH] == ["synthLoaded", "synthFailed", "synthBack", "synthLoaded"]
assert nvdalog.isOwn(next(fact for fact in facts if fact["said"] == "VisionClaw: a request began"))

# --- Nothing private reaches any sentence ---

everything = "\n".join([
	nvdalog.errorsText(problems, NAMES), nvdalog.addonsText(problems, found, NAMES), nvdalog.freezesText(found, NAMES),
	nvdalog.driversText(drivers, "INFO"), nvdalog.lastRunText(old, NAMES, MODULES),
	nvdalog.recentText(entries, "today", MODULES, NAMES), nvdalog.modelFacts(clock, NAMES),
	"\n".join(fact["said"] for fact in nvdalog.facts(entries + old, MODULES))]
	+ [nvdalog.problemText(problem, NAMES) for problem in problems])
for word in PRIVATE_WORDS:
	assert word not in everything, word

# --- The logging level, and the log turned off ---

ON = {"configured": "INFO", "effective": 20, "forced": False, "secure": False, "file": r"C:\Temp\nvda.log", "writing": True}
assert not nvdalog.isOff(ON) and nvdalog.levelName(ON) == "INFO"
said = nvdalog.levelText(ON)
assert said.startswith("NVDA's logging level is Info. NVDA writes its errors, warnings and basic information") and said.endswith(
	r"NVDA writes its log to the file C:\Temp\nvda.log.")
IO = dict(ON, configured="IO", effective=12)
assert "VisionClaw only counts those lines and never reads them" in nvdalog.levelText(IO)
FORCED = dict(ON, effective=10, forced=True)
assert nvdalog.levelText(FORCED).startswith("NVDA's logging level is Debug.") and "Restart with debug logging enabled" in nvdalog.levelText(FORCED)
OFF = dict(ON, configured="OFF", effective=100)
assert nvdalog.isOff(OFF) and nvdalog.canOffer(OFF)
said = nvdalog.offText(OFF)
assert said.startswith("NVDA's log is off: its logging level is Disabled") and "the category Privacy and Security, the combo box "
assert "Logging level" in said and "Info is enough for errors." in said and said.endswith("VisionClaw never changes NVDA's logging level itself.")
assert nvdalog.levelText(OFF) == said
SECURE = dict(ON, secure=True, writing=False, file="")
assert nvdalog.isOff(SECURE) and not nvdalog.canOffer(SECURE) and nvdalog.offText(SECURE).startswith("NVDA runs in secure mode")
NO_LOGGING = dict(ON, forced=True, writing=False, file="")
assert nvdalog.isOff(NO_LOGGING) and not nvdalog.canOffer(NO_LOGGING) and "started with its logging turned off" in nvdalog.offText(NO_LOGGING)
NO_FILE = dict(ON, file="", writing=False)
assert nvdalog.offText(NO_FILE).startswith("NVDA could not open its log file")
said = nvdalog.settingsText(ON)
assert said.startswith("VisionClaw never changes NVDA's logging level itself. It is Info now. NVDA's logging level is in NVDA's "
	"settings: the category Privacy and Security, the combo box Logging level. NVDA+control+g opens NVDA's settings"), said
said = nvdalog.locationText(ON)
assert said.startswith(r"NVDA's log of this run is the file C:\Temp\nvda.log. The log of the run before is C:\Temp\nvda-old.log")
assert "NVDA+f1" in said and "NVDA+control+shift+f1" in said
# The levels as NVDA's settings name them, and as logHandler.py numbers them.
assert nvdalog.LEVELS["IO"] == 12 and nvdalog.LEVELS["DEBUGWARNING"] == 15 and nvdalog.LEVELS["OFF"] == 100
assert nvdalog.READ == {"CRITICAL", "ERROR", "WARNING", "DEBUGWARNING", "INFO"} and not (nvdalog.READ & nvdalog.PRIVATE)

# --- The plan's parts (docs/PLAN-nvda-log.md): what the user asks ---

PARTS_ASKS = {
	"when did nvda start": nvdalog.SESSION, "how long has nvda been running": nvdalog.SESSION,
	"was nvda started with add-ons disabled": nvdalog.SESSION, "did nvda close properly last time": nvdalog.LAST_RUN,
	"why did my voice change": nvdalog.DRIVERS, "which braille display did nvda load": nvdalog.DRIVERS,
	"what did the developer info say": nvdalog.OBJECT, "what is its window class in the developer info": nvdalog.OBJECT,
	"which framework does the dev info say": nvdalog.OBJECT, "compare the last two objects I checked": nvdalog.OBJECT,
	"what did nvda+f1 show": nvdalog.OBJECT, "which keys did I try in input help": nvdalog.INPUT_HELP,
	"what was the last key I tried in input help": nvdalog.INPUT_HELP, "which add-on does that key belong to": nvdalog.INPUT_HELP,
	"when were my settings last saved": nvdalog.SAVED, "did nvda save my profile": nvdalog.SAVED,
	"were my settings reverted": nvdalog.SAVED, "is nvda remote connected": nvdalog.PARTS, "did java support start": nvdalog.PARTS,
	"which ui automation version does nvda use": nvdalog.PARTS, "is mathcat installed": nvdalog.PARTS,
	"did nvda check for updates": nvdalog.PARTS}
for said, do in PARTS_ASKS.items():
	want = nvdalog.wish(said)
	assert want and want["do"] == do, (said, want)
	assert planner.hint(said) == "nvda_log", (said, planner.hint(said))
assert nvdalog.wish("what is its window class in the developer info")["field"] == "windowclassname"
assert nvdalog.wish("which framework does the dev info say")["field"] == "framework"
assert nvdalog.wish("compare the last two objects I checked")["compare"] is True
assert nvdalog.wish("what was the last key I tried in input help")["last"] is True
assert nvdalog.wish("which keys did I try in input help")["last"] is False
# Left where they were: the object the user is on, input help turned on or explained, NVDA's version, the computer's remote desktop.
for said, job in (
		("what is the window class of this control", "object_facts"), ("what is the window class of the focused object", "object_facts"),
		("what is input help", "nvda_question"), ("how do I use input help", "explain_keys"), ("which version of nvda is running", "version_info"),
		("what version of nvda do I have", "version_info"), ("how many cells has my braille display got", "nvda_info"),
		("what synthesizer am I using", "nvda_info"), ("check for updates", "update_visionclaw")):
	assert nvdalog.wish(said) is None and planner.hint(said) == job, (said, nvdalog.wish(said), planner.hint(said))
for said in ("turn on input help", "save my settings", "restart nvda with add-ons disabled", "is the remote desktop connected",
		"how long has it been running"):
	assert nvdalog.wish(said) is None, (said, nvdalog.wish(said))

# --- 1. The session ---

now = time.mktime((2026, 11, 19, 12, 30, 0, 0, 0, -1))
nvdalog.stamp(entries, time.mktime((2026, 11, 19, 9, 10, 0, 0, 0, -1)))
found = nvdalog.session(entries)
assert found["version"] == "2026.3.1" and found["started"] == "09:00:00" and found["ready"] == "09:00:03" and not found["addonsOff"]
said = nvdalog.sessionText(entries, old, now, MODULES, NAMES)
assert said.startswith("This run of NVDA, version 2026.3.1, started at 09:00:00, and was ready at 09:00:03.\nIt has been running "
	"for 3 hours and 29 minutes.\nIt runs on Windows Windows 11 24H2 (10.0.26100) workstation.\nIt was started with its add-ons.\n"
	"The run before: NVDA crashed, at 23:59:59."), said
assert nvdalog.durationWords(30) == "under a minute" and nvdalog.durationWords(90061) == "1 day and 1 hour"
assert "NVDA began to close normally at 18:00:00" in nvdalog.ending(nvdalog.parse(NORMAL.split("INFO - __main__ (18:00:01.000)")[0]))["said"]
OFF_ADDONS = NORMAL.replace("NVDA initialized\n", "NVDA initialized\nINFO - core.main (08:00:02.500) - MainThread (1):\n"
	"Add-ons are disabled. Restart NVDA to enable them.\n")
assert "It was started with all add-ons turned off." in nvdalog.sessionText(nvdalog.parse(OFF_ADDONS))

# --- 3. Objects: the developer info of NVDA+f1 ---

DEVINFO = r"""INFO - globalCommands.GlobalCommands.script_navigatorObject_devInfo (10:00:00.000) - MainThread (1000):
Developer info for navigator object:
name: 'Save'
role: BUTTON
processID: 4242
roleText: None
states: FOCUSABLE, FOCUSED
isFocusable: True
hasFocus: True
Python object: <NVDAObjects.UIA.UIA object at 0x0000021F>
Python class mro: (<class 'NVDAObjects.UIA.UIA'>, <class 'globalPlugins.clock.SaveButton'>, <class 'NVDAObjects.window.Window'>)
description: ''
location: RectLTWH(left=10, top=20, width=80, height=30)
value: None
TextInfo: <class 'NVDAObjects.NVDAObjectTextInfo'>
appModule: AppModule(appModules.notepad, appName='notepad', processID=4242)
appModule.productName: 'Microsoft Windows Operating System'
appModule.productVersion: '10.0.26100.1'
appModule.helperLocalBindingHandle: c_void_p(123)
appModule.appArchitecture: 'AMD64'
windowHandle: 132456
windowClassName: 'Button'
windowControlID: 1
windowStyle: 1342242816
extendedWindowStyle: 4
windowThreadID: 9999
windowText: 'Save'
displayText: 'Save'
UIAElement: <POINTER(IUIAutomationElement) ptr=0x1 at 2>
UIA automationID: SaveButton
UIA frameworkID: Win32
UIA runtimeID: (42, 132456)
UIA providerDescription: [pid:4242,providerId:0x0 Main:Nested]
UIA className: Button
UIA patterns available: Invoke, LegacyIAccessible
INFO - globalCommands.GlobalCommands.script_navigatorObject_devInfo (10:00:30.000) - MainThread (1000):
Developer info for navigator object:
name: 'Password'
role: EDITABLETEXT
states: FOCUSABLE, PROTECTED
isFocusable: True
value: 'hunter2secret'
appModule: AppModule(appModules.notepad, appName='notepad', processID=4242)
windowClassName: 'Edit'
windowText: 'hunter2secret'
UIA automationID: PasswordBox
UIA frameworkID: Win32
UIA className: Edit
INFO - inputCore.InputManager._handleInputHelp (10:01:00.000) - MainThread (1000):
Input help: gesture kb(desktop):NVDA+t, bound to script title on globalCommands.GlobalCommands
INFO - inputCore.InputManager._handleInputHelp (10:01:05.000) - MainThread (1000):
Input help: gesture kb(desktop):NVDA+shift+v, bound to script sayDate on globalPlugins.clock.GlobalPlugin
INFO - inputCore.InputManager._handleInputHelp (10:01:09.000) - MainThread (1000):
Input help: gesture kb(desktop):control+q
INFO - inputCore.InputManager._handleInputHelp (10:01:12.000) - MainThread (1000):
Input help: gesture kb(laptop):NVDA+shift+f, bound to script reportFormatting on globalCommands.GlobalCommands
INFO - config.ConfigManager._loadConfig (10:02:00.000) - MainThread (1000):
Loading config: C:\Users\sam\AppData\Roaming\nvda\nvda.ini
INFO - config.ConfigManager.save (10:03:00.000) - MainThread (1000):
Base configuration saved
INFO - config.ConfigManager.save (10:03:00.100) - MainThread (1000):
Saved configuration profile Word
INFO - core.resetConfiguration (10:04:00.000) - MainThread (1000):
Reverted to saved configuration
INFO - core.main (10:05:00.000) - MainThread (1000):
Java Access Bridge support initialized
INFO - UIAHandler.UIAHandler.MTAThreadFunc (10:05:01.000) - UIAHandler.MTAThread (3000):
UIAutomation: IUIAutomation6
INFO - _remoteClient.client.RemoteClient.connect (10:06:00.000) - MainThread (1000):
Initiating connection as master to example.org:6837
INFO - _remoteClient.client.RemoteClient.onConnectedAsLeader (10:06:01.000) - MainThread (1000):
Successfully connected as leader
"""
more = nvdalog.parse(DEVINFO)
infos = nvdalog.devInfos(more)
assert len(infos) == 2 and infos[0]["fields"]["uia automationid"] == "SaveButton" and infos[0]["fields"]["name"] == "Save"
assert infos[0]["fields"]["value"] == "" and infos[0]["fields"]["windowclassname"] == "Button"
assert nvdalog.frameworkOf(infos[0]["fields"]) == "UI Automation, framework Win32"
assert nvdalog.objectFacts(infos[0]) == ("The button \"Save\" in the program notepad: automation ID SaveButton, window class Button, "
	"shown through UI Automation, framework Win32.")
assert nvdalog.objectFacts(None) == "" and nvdalog.objectFacts({"fields": {}}) == ""
said = nvdalog.objectText(infos[0], None, MODULES, NAMES)
assert said.startswith("The developer info NVDA wrote at 10:00:00 is for the button \"Save\", in the program notepad.\nIts states are "
	"focusable, focused.\nIt can take the focus.\nIt is shown to NVDA through UI Automation, framework Win32."), said
assert "Its automation ID is SaveButton." in said and "Its UI Automation patterns are Invoke, LegacyIAccessible." in said
assert "NVDA treats it with a class of the add-on Clock and Calendar (clock), SaveButton." in said
assert "132456" not in said and "0x" not in said
assert nvdalog.objectText(infos[0], "windowclassname") == "In the developer info NVDA wrote at 10:00:00, its window class is Button."
assert nvdalog.objectText(infos[0], "framework") == ("In the developer info NVDA wrote at 10:00:00, it is shown to NVDA through UI "
	"Automation, framework Win32.")
assert nvdalog.objectText(None).startswith("NVDA's log of this run has no developer info. Press NVDA+f1 on an object")
# What is typed into a protected field is never said, alone, in all of it, or compared.
assert nvdalog.objectText(infos[1], "value") == ("In the developer info NVDA wrote at 10:00:30, its value is not said, because it is a "
	"protected field.")
compared = nvdalog.compareText(infos[0], infos[1])
assert compared.startswith("Between the developer info written at 10:00:00 and the one at 10:00:30, ") and (
	"its automation ID: SaveButton before, PasswordBox now" in compared and "its name: Save before, Password now" in compared), compared
assert nvdalog.compareText(infos[0], None).startswith("NVDA's log of this run has fewer than two developer infos.")
for text in (nvdalog.objectText(infos[1], None, MODULES, NAMES), compared, nvdalog.objectFacts(infos[1]),
		"\n".join(fact["said"] for fact in nvdalog.facts(more))):
	assert "hunter2secret" not in text, text

# --- 4. Input help ---

keys = nvdalog.inputHelp(more, MODULES)
assert [item["key"] for item in keys] == ["NVDA+t", "NVDA+shift+v", "control+q", "NVDA+shift+f, in the laptop keyboard layout"]
assert keys[1]["addon"] == "clock" and keys[0]["addon"] == "" and keys[2]["script"] == ""
DESCRIBE = {("GlobalCommands", "title"): "Reports the title of the current application or foreground window."}
said = nvdalog.inputHelpText(keys, NAMES, last=True, describe=DESCRIBE)
assert said == ("The last key you tried in input help, at 10:01:12, was NVDA+shift+f, in the laptop keyboard layout, which runs the "
	"command reportFormatting, of NVDA itself."), said
said = nvdalog.inputHelpText(keys, NAMES, describe=DESCRIBE)
assert said.split("\n")[:4] == ["Keys you tried in input help in this run, in order: 4.",
	"1. At 10:01:00: NVDA+t, which runs the command Reports the title of the current application or foreground window, of NVDA itself.",
	"2. At 10:01:05: NVDA+shift+v, which runs the command sayDate, of the add-on Clock and Calendar (clock).",
	"3. At 10:01:09: control+q, which runs no command there."], said
assert nvdalog.inputHelpText([]).startswith("NVDA's log of this run has no keys tried in input help. NVDA+1 turns input help on")

# --- 5. Freezes: the program NVDA was working for ---

APP_FREEZE = ("INFO - watchdog.w (11:00:00.000) - watchdog (2):\nStarting freeze recovery after 10.0 seconds.\n"
	"ERROR - watchdog.w (11:00:15.000) - watchdog (2):\nCore frozen in stack! (25.0 seconds)\n"
	"INFO - watchdog.w (11:00:15.001) - watchdog (2):\nListing stacks for Python threads:\nPython stack for thread 1 (MainThread):\n"
	'  File "appModules\\winword.py", line 40, in event_caret\n'
	"INFO - watchdog.w (11:00:20.000) - watchdog (2):\nRecovered from freeze after 30.0 seconds.\n")
froze = nvdalog.freezes(nvdalog.parse(APP_FREEZE))
assert froze[0].program == "winword" and not froze[0].addon
assert "While it was frozen, it was working in NVDA's own support for the program winword." in nvdalog.freezesText(froze)

# --- 6. Settings and profiles ---

said = nvdalog.savedText(more)
assert said == ("What NVDA's log of this run says about its settings, in order:\nAt 10:02:00: NVDA loaded its settings from "
	"C:\\Users\\sam\\AppData\\Roaming\\nvda\\nvda.ini.\nAt 10:03:00: NVDA saved its settings.\nAt 10:03:00: NVDA saved the "
	"configuration profile Word.\nAt 10:04:00: NVDA put back its saved settings, or its factory defaults; it writes the same line "
	"for both.\nThe last time NVDA saved its settings was at 10:03:00."), said
assert nvdalog.savedText([]).startswith("NVDA's log of this run says nothing about its settings")

# --- 7. NVDA Remote, Java, UI Automation ---

said = nvdalog.partsText(more, "is nvda remote connected")
assert said == ("NVDA Remote is connected, and this computer controls the other one.\nThe last thing NVDA's log says about it, at "
	"10:06:01: NVDA Remote connected; this computer controls the other one."), said
assert "example.org" not in nvdalog.partsText(more)
said = nvdalog.partsText(more, "did java support start and which ui automation version")
assert said == ("At 10:05:00: NVDA's support for Java programs started.\nAt 10:05:01: NVDA uses UI Automation through Windows' "
	"interface IUIAutomation6."), said
assert nvdalog.partsText([], "is nvda remote connected") == ("NVDA's log of this run says nothing about NVDA Remote, so it has not "
	"connected in this run.")
assert nvdalog.remoteState(nvdalog.facts(nvdalog.parse(
	"INFO - x (1:00:00.000) - MainThread (1):\nControl connector connected\n".replace("1:00", "01:00")))) == "follower"

# --- Trouble, for other parts of VisionClaw ---

said = nvdalog.troubleText(entries, MODULES, NAMES)
assert said.startswith("NVDA wrote 5 errors: Error in speech, in NVDA's own part for speech; The weather could not be read, from "
	"the add-on Weather Plus (weather); Error in script_sayTime, from the add-on Clock and Calendar (clock), 2 times; Python could "
	"not finish cleaning up something, in NVDA's own part for code NVDA could not name."), said
assert ("NVDA could not open the sound output device that was chosen, or the default one; there may be no sound device. The speech "
	"synthesizer sapi5 could not be started. NVDA went back to the speech synthesizer it had before, oneCore.") in said
assert said.endswith("NVDA stopped responding once, the longest for about 40 seconds, while it was working in the add-on Slow Thing "
	"(slowThing).")
assert nvdalog.troubleText(nvdalog.parse(NORMAL)) == "" and nvdalog.troubleText(None) == "" and nvdalog.troubleText([object()]) == ""
for word in PRIVATE_WORDS:
	assert word not in said
for asked in ("why did speech stop", "why is NVDA slow", "NVDA keeps freezing", "why did my braille display stop working",
		"nvda crashed", "why did the voice go silent"):
	assert nvdalog.asksTrouble(asked), asked
for asked in ("what time is it", "turn off typing echo", "why does nvda say clickable", None, ""):
	assert not nvdalog.asksTrouble(asked), asked

# --- The facts of each kind a skill may want (skills.LOG_KINDS), each with its time ---

assert nvdalog.LOG_KINDS == skills.LOG_KINDS
both = entries + more
nvdalog.stamp(both, time.mktime((2026, 11, 19, 10, 7, 0, 0, 0, -1)))
EXPECTED = {
	"errors": "The speech synthesizer sapi5 could not be started. The reason NVDA wrote: OSError: [WinError -2147221164] Class not registered",
	"add-ons": "An error: Error in script_sayTime.", "speech": "NVDA loaded the speech synthesizer oneCore.",
	"audio": "NVDA could not open the sound output device that was chosen, or the default one; there may be no sound device.",
	"braille": "NVDA is set to no braille display.", "freezes": "NVDA recovered after being frozen for about 40 seconds.",
	"session": "NVDA 2026.3.1 started.", "settings": "NVDA saved the configuration profile Word.",
	"objects": ("The button \"Save\" in the program notepad: automation ID SaveButton, window class Button, shown through UI "
		"Automation, framework Win32."),
	"input help": "In input help, NVDA+shift+v, which runs the command sayDate, of the add-on Clock and Calendar (clock).",
	"remote": "NVDA Remote connected; this computer controls the other one."}
for kind in nvdalog.LOG_KINDS:
	found = nvdalog.factsFor(both, kind, MODULES, NAMES)
	assert found and all(fact["clock"] and fact["when"] for fact in found), kind
	assert EXPECTED[kind] in [fact["said"] for fact in found], (kind, [fact["said"] for fact in found])
	assert not any(word in fact["said"] for fact in found for word in PRIVATE_WORDS + ("hunter2secret",)), kind
assert nvdalog.factsFor(both, "the weather") == [] and nvdalog.factsFor(None, "errors") == []

# --- The skills ---

lib = skills.Skills(tempfile.mkdtemp(prefix="vcskills-"), recipes=set(planner.RECIPES))
OURS = ("nvda-log-errors", "add-on-breaking-nvda", "nvda-froze", "nvda-crashed", "nvda-logging-level", "what-just-happened",
	"nvda-developer-info", "key-in-input-help", "speech-or-braille-in-the-log")
for slug in OURS:
	skill = lib.get(slug)
	assert skill is not None and not skills.check(skill, set(planner.RECIPES)) and "nvda_log" in skill.uses, slug
	assert len(skill.instructions) <= skills.GUIDE_CHARS and not re.search(r"[*#`_]|^\s*-", skill.instructions, re.M), slug
	assert "for example" not in skill.instructions.lower() and "e.g." not in skill.instructions.lower(), slug
for said, slug in (
		("check NVDA's log", "nvda-log-errors"), ("is an add-on breaking NVDA", "add-on-breaking-nvda"), ("NVDA froze", "nvda-froze"),
		("nvda keeps freezing", "nvda-froze"), ("did NVDA crash", "nvda-crashed"), ("what is NVDA's logging level", "nvda-logging-level"),
		("how do I turn on debug logging", "nvda-logging-level"), ("what just happened in nvda", "what-just-happened"),
		("anything new in nvda's log", "what-just-happened"), ("what did the developer info say", "nvda-developer-info"),
		("which keys did I try in input help", "key-in-input-help"), ("which add-on does that key belong to", "key-in-input-help"),
		("why did my voice change", "speech-or-braille-in-the-log"), ("synthesizer error", "speech-or-braille-in-the-log")):
	assert [skill.slug for skill in lib.choose(said)][:1] == [slug], (said, [skill.slug for skill in lib.choose(said)])
for said in ("what time is it", "turn off the typing echo", "Undo that", "Read the error message", "NVDA stopped talking in Word",
		"what errors are in your log", "which add-on can tell me the weather", "how many cells has my braille display got",
		"what is the window class of this control"):
	assert not set(OURS) & {skill.slug for skill in lib.choose(said)}, (said, [skill.slug for skill in lib.choose(said)])
# A skill of these chosen for another job's words says nothing to that job: its sentences go only to its own jobs.
for said, job in (("turn on input help", "do_command"), ("change my voice to david", "switch_driver")):
	chosen = [skill for skill in lib.choose(said) if skill.slug in OURS]
	assert not skills.guide(chosen, job), (said, job)
for slug in OURS:
	assert lib.get(slug).log, slug  # what each wants from NVDA's log (skills.LOG_KINDS)

print("OK")
