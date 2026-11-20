# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - NVDA's own log, read by plain code, only when the user asks. The owner said on 2026-11-19: "I also want
# visionclaw to have access to the various logs of nvda itself, info, debug, etcetera. and based on this, make relevant
# skills that the end-user can greatly benefit from", and: "however, if nvda logging is disabled, then such skills can't be
# used until user turns on some sort of nvda logging in nvda settings currently under privacy." And the same day: "visionclaw
# can query the various nvda logs to get all kinds of realtime info. this is for new visionclaw skills, system prompts,
# future features, etcetera." What follows from it:
#   - Nothing here runs by itself: not at start-up, not after an error, not as a step a model planned. Plain code reads the
#     user's words (wish) and only then is the log read (nvdalogtools.py).
#   - PRIVACY. NVDA's log at the level Input/output holds every key typed and everything spoken or shown in braille
#     ("Input: kb(desktop):v"), and the debug levels may hold more. So entries of the levels IO, DEBUG and DEBUG_UNREDACTED
#     (and any level NVDA does not name) are counted and never kept: parse() drops their lines as it reads them. They are
#     never read out, never given to a model, never written to VisionClaw's own log (claw/debuglog.py). Only ERROR,
#     CRITICAL, WARNING, DEBUGWARNING and INFO entries are read. tests/test_nvdalog.py checks it.
#   - VisionClaw never changes NVDA's logging level (nvdatools._SKIP_KEYS has "loggingLevel"). When the log is off, it says
#     so, where it is turned on, and offers to open that settings panel, which changes nothing.
#   - A model may say what ONE chosen error means, only when the user asks what an error means or why it happened
#     (EXPLAIN_TASK, through prompts.speaking); that is said to be the model's and possibly wrong. Everything else is plain
#     code: which errors, how often, from where, which add-on, freezes, the speech synthesizer, the sound and the braille
#     display, how the run before ended, the level, and what NVDA wrote just now.
#
# Meant to be used again, by later skills and features: everything below returns plain data or sentences and needs no NVDA.
#   parse(lines, check)          the entries of a log; private ones keep no lines
#   stamp(entries, lastWritten)  each entry's time as seconds since the epoch (NVDA writes the time of day only)
#   entriesSince(entries, since, until)   the entries of a stretch of time, for "what just happened"
#   facts(entries, modules)      what NVDA reported, one plain dict each: when, kind, group, the sentence, the add-on
#   errors(entries, modules)     the errors, each once, newest first, with how often and where from
#   freezes(entries, modules)    every time NVDA stopped responding, how long, and where it was working
#   ending(entries)              how a run ended: closed, crashed, Windows shut down, frozen, or not told
#   counted(entries)             how many private entries there were, never what they said
#   session(entries)             when this run started and was ready, which NVDA, Windows, add-ons turned off
#   devInfos(entries)            every "Developer info for navigator object" (NVDA+f1) as a dict of its fields
#   objectFacts(info)            the facts that tell one such object apart, as one plain sentence
#   inputHelp(entries, modules)  every key tried in input help, with its command and whose command it is
#   factsFor(entries, kind)      the facts of one kind of skills.LOG_KINDS (errors, add-ons, speech, audio, braille, freezes,
#                                session, settings, objects, input help, remote), each with its time
#   troubleText(entries)         a few plain sentences on errors, driver fallbacks and freezes, "" where there are none
#   asksTrouble(text)            whether the user's words ask why something in NVDA went wrong
#   wish(text)                   what the user's own words ask of NVDA's log, or None
#
# What NVDA writes was read from NVDA's own source (branch release-2026.3.1), never written from memory:
#   logHandler.py         the levels, the form of an entry ("{levelname} - {codepath} ({asctime}) - {threadName}
#                         ({thread}):" then the message), the time as HH:MM:SS.mmm, nvda-old.log kept from the run before,
#                         NullHandler in secure mode or with --no-logging, isLogLevelForced, "external:" before a codepath
#                         of code outside NVDA
#   nvda.pyw              "Starting NVDA version ..." first, "NVDA exit" last when NVDA closes normally, "core failure",
#                         "Prior NVDA exited without releasing mutex ..."
#   core.py               "NVDA initialized", "Exiting", "Windows session ending", "Restarting unsafely", "Error terminating
#                         ...", "Add-ons are disabled. Restart NVDA to enable them.", "Windows version: ..."
#   watchdog.py           "Starting freeze recovery after X seconds.", "Core frozen in stack! (X seconds)" every 15 seconds
#                         of a freeze, then "Listing stacks for Python threads:", "Recovered from freeze after X seconds.",
#                         "Crash loop detected (N crashes in T seconds). ..."
#   utils/_crashHandler.py   "NVDA crashed! ..." (CRITICAL), "Restarting due to crash"
#   synthDriverHandler.py "Loaded synthDriver X", "setSynth failed for X", "Error while importing SynthDriver X", "Falling
#                         back to previous synthDriver X", "Searching for next synthDriver", "Falling back to next
#                         synthDriver X", "Invalid voice: X"
#   braille/brailleHandler.py   "Loaded braille display driver 'X', current display has N cells.", "Error initializing
#                         display driver 'X'", "Braille display unavailable. Disabling", "Error displaying cells. Disabling
#                         display", "Error terminating previous display driver", "Invalid translation table (X), falling
#                         back to default (Y).", "Braille cells are shorter than the display size. ...", and, only at Debug
#                         warning, "Couldn't initialize display driver 'X'"
#   nvwave.py             "Couldn't open specified or default audio device. There may be no audio devices.", "Error playing
#                         wave file", and, only at Debug warning, "Unable to play wave file as the render endpoint was not
#                         found." and "Error feeding audio"
#   addonHandler/__init__.py   "Error loading Addon from path: ...", at Debug warning "Add-on X is considered
#                         incompatible"; an add-on's folder is addons\<id>, with ".pendingInstall" while it is installed
#   globalPluginHandler.py, appModuleHandler.py   "Error importing global plugin X", "Error initializing global plugin X",
#                         "error in appModule 'X'"
#   globalCommands.py     "Developer info for navigator object:" then one "field: value" a line (NVDA+f1), the fields read
#                         from NVDAObjects/__init__.py, NVDAObjects/window/__init__.py, NVDAObjects/IAccessible/__init__.py,
#                         NVDAObjects/UIA/__init__.py and appModuleHandler.py (_get_devInfo of each)
#   inputCore.py          "Input help: gesture X, bound to script Y on Z" (_handleInputHelp), Z as scriptHandler's
#                         getScriptLocation writes it, "module.Class"
#   core.py, UIAHandler/__init__.py, mathPres/MathCAT/MathCAT.py, updateCheck.py, _remoteClient/*.py   "Java Access Bridge
#                         support initialized", "Java Access Bridge not available", "UIAutomation: X", "UIA disabled in
#                         configuration", "MathCAT X installed.", "Performing automatic update check", NVDA Remote's
#                         "Successfully connected as leader", "Control connector connected", and the others listed below
#   config/__init__.py    "Loading config: X", "Error loading base configuration; ...", "Not writing profile, either --secure
#                         or --launcher args present", "Error saving configuration", "Reverted to saved configuration" (core.py,
#                         for a revert and for factory defaults alike), "Base configuration saved", "Saved configuration
#                         profile X", "Profile triggers saved". A profile
#                         switched to, an app module loaded and an add-on loaded are written only at the Debug level, which
#                         VisionClaw never reads.
#   gui/settingsDialogs.py   the category "Privacy and Security", the combo box "Logging level", NVDA's own question before
#                         a level above Info ("may record sensitive information such as typed input, speech output ..."),
#                         and the combo box unavailable while the level is forced
# When NVDA changes one of these, read its source again; do not write a message from memory. No NVDA dependencies.

import os
import re
import time

from .diagnose import whichNumber
from .memory import words

# --- Levels ---

LEVELS = {
	"DEBUG_UNREDACTED": 5, "DEBUG": 10, "IO": 12, "DEBUGWARNING": 15, "INFO": 20, "WARNING": 30, "ERROR": 40,
	"CRITICAL": 50, "OFF": 100}
# The only levels whose entries are read. Every other entry is counted and nothing of it is kept.
READ = frozenset(("CRITICAL", "ERROR", "WARNING", "DEBUGWARNING", "INFO"))
PRIVATE = frozenset(("IO", "DEBUG", "DEBUG_UNREDACTED"))
# What NVDA's Privacy and Security settings call each level in the combo box Logging level (NVDA's user guide).
LEVEL_NAMES = {
	"OFF": "Disabled", "INFO": "Info", "DEBUGWARNING": "Debug warning", "IO": "Input/output", "DEBUG": "Debug",
	"DEBUG_UNREDACTED": "Debug (unredacted)"}
LOG_FILE, OLD_FILE = "nvda.log", "nvda-old.log"
# How much of the end of a log is read at most: a log at a debug level can be very large.
MAX_READ = 8 << 20
# "Just now", when the user says nothing more: this many seconds before the request.
JUST_NOW = 120
# How many of the last entries of the run before are said.
LAST_ENTRIES = 4

# --- What the user asks ---

ERRORS, EXPLAIN, ADDONS, FREEZES, DRIVERS, LAST_RUN, RECENT, LEVEL, SETTINGS, WHERE = (
	"errors", "explain", "addons", "freezes", "drivers", "lastRun", "recent", "level", "settings", "where")
SESSION, OBJECT, INPUT_HELP, SAVED, PARTS = "session", "object", "inputHelp", "saved", "parts"
# For RECENT: since when.
JUST, SINCE_REQUEST, SINCE_READ = "just", "sinceRequest", "sinceRead"

_NV = r"nvda(?:'s|s)?"
_LOG = (
	rf"(?:{_NV} (?:own )?(?:log|logs|log files?|logging|error log)|(?:log|logs|log file) (?:of|from) nvda|nvda[- ]old(?:\.log)?"
	r"|nvda\.log|(?:the )?(?:old|previous|last) nvda log)")
_OWN = re.compile(r"\b(?:your|yourself|visionclaw'?s?|vision claw'?s?)\b")
# A question about what VisionClaw does with NVDA's log is looked up in VisionClaw's notes (knowledge/visionclaw-nvdalog.md):
# "does VisionClaw change NVDA's logging level" reads nothing.
_ABOUT_US = re.compile(
	r"\bhow (?:does|do|can|will|would) (?:you|visionclaw)\b.{0,30}\b(?:read|use|see|handle|treat|get|look at)\b.{0,20}\bnvda'?s? "
	r"(?:log|logs|logging)\b"
	r"|\b(?:does|do|can|will|would) (?:you|visionclaw) (?:ever )?(?:change|send|upload|keep|store|share|turn)\b.{0,30}"
	r"\bnvda'?s? (?:log|logs|logging)\b"
	r"|\bwhat can (?:you|visionclaw) do with\b.{0,20}\bnvda'?s? (?:log|logs)\b")
_SETTINGS = re.compile(
	rf"\b(?:turn|switch|set|change|raise|lower|enable|disable|start|stop|put)\b.{{0,25}}\b{_NV} (?:own )?(?:debug )?(?:log|logs|"
	r"logging|log level|logging level)\b"
	r"|\b(?:turn|switch) (?:on|off) (?:the )?(?:nvda'?s? |nvda )?(?:debug )?logging\b"
	r"|\b(?:enable|disable|start|stop) (?:the )?(?:nvda'?s? |nvda )?(?:debug )?logging\b"
	r"|\b(?:set|change|raise|lower|adjust) (?:the |nvda'?s? )?(?:logging|log) level\b"
	r"|\b(?:open|show|go to|take me to|bring up)\b.{0,15}\b(?:nvda'?s? )?(?:logging|log level|logging level) (?:settings?|options?|"
	r"combo ?box)\b"
	r"|\bwhere\b.{0,30}\b(?:logging level|log level)\b")
_LEVEL = re.compile(
	r"\b(?:what(?:'s| is)|which|tell me|say)\b.{0,15}\b(?:nvda'?s? )?(?:logging|log) level\b"
	rf"|\bis {_NV} (?:log|logging) (?:on|off|enabled|disabled|turned on|turned off|switched on|switched off|working)\b"
	r"|\bis nvda (?:logging|keeping a log|writing (?:a |its )?log)\b|\b(?:does|is) nvda (?:keep|write)s? (?:a |its )?log\b"
	r"|\bis (?:nvda'?s? )?(?:debug )?logging (?:on|off|enabled|disabled)\b")
_WHERE = re.compile(
	rf"\bwhere (?:is|are|can i find|do i find|does nvda (?:keep|save|write|put))\b.{{0,15}}\b{_NV} (?:own )?(?:log|logs|log files?)\b"
	rf"|\b{_NV} log (?:file )?(?:location|folder|path)\b|\bwhere\b.{{0,30}}\bnvda(?:[- ]old)?\.log\b")
# The log viewer itself, or the key for it: NVDA's own command, or a question about keys.
_VIEWER = re.compile(
	rf"\b(?:open|show|bring up|pop up|display|view)\b.{{0,15}}\b(?:{_NV} (?:own )?(?:log|log viewer|log file)|(?:the )?log viewer)\b"
	r"|\b(?:key|keys|shortcut|hot ?key|command)\b.{0,30}\blog\b")
_ERROR_WORDS = re.compile(r"\b(?:errors?|exceptions?|tracebacks?|warnings?|problems?|crash\w*|freez\w*|froze|frozen|trouble)\b")
_EXPLAIN = re.compile(
	r"\bexplain\b|\bmean(?:s|ing)?\b|\bwhat caused\b|\bwhat causes\b|\bcause of\b"
	r"|\bwhy (?:did|does|do|is|was) (?:that |this |the |it |nvda'?s? |the last |nvda'?s? last )?(?:error|exception|warning)\b"
	r"|\bwhy\b.{0,40}\b(?:error|exception|warning) (?:happen|happened|occur|occurred|come up|came up)\b")
_ADDONS = re.compile(
	r"\b(?:which|what) add-?ons?\b(?! (?:can|could|should|would|will|helps?|lets?|do i|to|for)\b).{0,50}\b(?:errors?|crash\w*|freez\w*|froze|hang|hangs|hung|break\w*|broke|caus\w*|"
	r"problems?|trouble|slow\w*|lag\w*|fail\w*)\b"
	r"|\b(?:is|are|could|might|can) (?:an |any |some |one of (?:my |the )?)?add-?ons? (?:be )?(?:causing|breaking|crashing|"
	r"freezing|slowing|messing|making nvda)\b"
	r"|\badd-?ons?\b.{0,30}\b(?:causing|breaking|crashing|freezing|slowing down)\b.{0,20}\bnvda\b"
	rf"|\badd-?on (?:errors?|crash(?:es)?|problems?|trouble)\b.{{0,30}}\b{_NV}\b"
	rf"|\b{_LOG}\b.{{0,40}}\badd-?ons?\b|\badd-?ons?\b.{{0,40}}\b{_LOG}"
	rf"|\b(?:errors?|crash(?:es)?|problems?) (?:from|of|caused by) (?:an |any |my |which )?add-?ons?\b.{{0,40}}\b{_NV}\b")
_HANG = (r"(?:freez\w*|froze|frozen|hang|hangs|hanging|hung|locks? up|locked up|locking up|stall\w*|stops? responding|"
	r"stopped responding|unresponsive|not responding)")
_FREEZES = re.compile(
	rf"\bnvda(?:'s)? (?:\w+ ){{0,3}}?{_HANG}\b(?!\s+up\b)"
	r"|\bnvda (?:is |keeps |has been |started |starts |gets |got )?(?:lag|lags|lagging|laggy)\b"
	rf"|\b(?:freez\w*|froze|frozen|hangs?|hung|lockups?|lags?|lagging)\b.{{0,25}}\b(?:in|of|from) {_LOG}")
_DRIVER_WORDS = r"(?:synth\w*|speech synthesi[sz]er|voices?|audio(?: device| output)?|sound (?:card|device|output)|braille(?: display)?)"
_DRIVERS = re.compile(
	r"\bwhy did (?:my |the |nvda'?s? )?(?:voice|synth\w*|speech synthesi[sz]er|speech) change\b"
	r"|\b(?:which|what) (?:braille display|synth\w*|speech synthesi[sz]er|voice) did nvda (?:load|use|pick|choose|fall back to|"
	r"switch to)\b|"
	rf"\b{_DRIVER_WORDS}\b.{{0,40}}\b(?:errors?|trouble|problems?|fail\w*|crash\w*)\b.{{0,30}}\b{_LOG}"
	rf"|\b{_LOG}\b.{{0,40}}\b{_DRIVER_WORDS}\b"
	r"|\b(?:did|has|have|why did|why does|why do|why has) (?:my |the |nvda'?s? )?(?:speech )?(?:synth\w*|braille display|audio device|"
	r"sound card|sound device)\b.{0,20}\b(?:fail\w*|crash\w*|stop(?:ped)? working|disconnect\w*|errors?|go away|went away|"
	r"drop(?:ped)? out)\b"
	r"|\b(?:synth\w*|speech synthesi[sz]er|braille display) (?:errors?|crash(?:es|ed)?|fail(?:ed|ure|ures|s)?)\b")
_LAST_RUN = re.compile(
	r"\b(?:why|how|when) did nvda (?:just )?(?:crash|close|quit|exit|restart|shut ?down|die|end|go away|turn off|stop running)\b"
	r"|\bdid nvda (?:just )?(?:crash|close by itself|restart by itself|quit by itself|exit by itself|close on its own|"
	r"restart on its own)\b"
	r"|\bnvda (?:crashed|keeps crashing|kept crashing|has crashed|just crashed|closed by itself|restarted by itself|quit by itself|"
	r"shut down by itself|closed on its own|restarted on its own|exited unexpectedly|closed unexpectedly|restarted unexpectedly)\b"
	r"|\bwhy (?:does|do|did) nvda keep (?:crashing|closing|restarting|quitting)\b"
	r"|\b(?:the )?last time nvda (?:crashed|closed|ended|exited|quit|restarted|ran|was running)\b"
	rf"|\b{_NV} (?:old|previous|last) (?:log|session|run)\b|\b(?:old|previous|last) nvda (?:log|session|run)\b|\bnvda[- ]old\b"
	r"|\bwhat happened (?:when|before|as|just before) nvda (?:crashed|closed|restarted|quit|exited|shut down|ended)\b"
	r"|\bdid nvda (?:close|exit|shut down|quit|end)\b.{0,25}\b(?:properly|normally|cleanly|right|ok|okay|correctly)\b")
_SESSION = re.compile(
	r"\bwhen did nvda (?:start|load|come up|begin|last start)\b|\bwhen was nvda (?:started|restarted|last started|loaded)\b"
	r"|\bhow long has nvda been (?:running|on|up|going|open)\b|\bhow long (?:is|has) nvda (?:been )?(?:running|up)\b"
	rf"|\b{_NV} (?:uptime|session)\b"
	r"|\b(?:was|is|did|has) nvda\b.{0,30}\bwith(?:out)? (?:all )?(?:the |my |any )?add-?ons?\b")
_OBJECT = re.compile(
	r"\bdev(?:eloper)? ?info(?:rmation)?\b"
	r"|\b(?:last|previous|two|both|newest) (?:two )?objects? (?:i |you )?(?:checked|looked at|inspected|examined)\b"
	r"|\bcompare\b.{0,30}\bobjects?\b"
	r"|\bnvda(?:\+| plus | )f1\b.{0,40}\b(?:say|said|show|showed|shows|told|logged|wrote|found)\b")
_COMPARE = re.compile(r"\bcompare\b|\bdiffer\w*\b|\bdifference\b|\b(?:last|previous|newest) two\b|\bboth objects\b")
_INPUT_HELP = re.compile(
	r"^(?!\s*(?:please\s+)?(?:can you\s+|could you\s+)?(?:turn|switch|toggle|start|stop|enable|disable|open|close|exit|leave|"
	r"enter|use|how|what is|what's)\b)(?=.*\binput help\b).*\b(?:tried|try|pressed|press|last|keys? i|which keys|what keys|list|"
	r"log|logged|belong\w*|whose|add-?ons?)\b"
	r"|\b(?:that|the last|the) (?:key|command|gesture|keystroke|shortcut)s? i (?:just )?(?:tried|pressed|checked)\b.{0,40}"
	r"\b(?:belong\w*|add-?on|whose|from|which|what)\b"
	r"|\b(?:which|what) add-?on\b.{0,30}\b(?:that|the last|this) (?:key|command|keystroke|shortcut|gesture)\b"
	r"|\bwhose (?:key|command|shortcut) (?:was|is) (?:that|it)\b")
_LAST_KEY = re.compile(r"\b(?:the )?last (?:key|command|gesture|keystroke|shortcut|one)\b|\bthat (?:key|command|gesture|keystroke|shortcut)\b")
_SAVED = re.compile(
	r"^\s*(?:please\s+)?(?:when|did|were|was|has|have|why|is|are)\b.{0,40}\b(?:settings|configuration|config|profiles?)\b.{0,25}"
	r"\b(?:saved|save|reverted|revert|reset|restored|loaded|load|lost|written)\b"
	r"|\b(?:when|did|has|have)\b.{0,10}\bnvda (?:last )?(?:save|saved|revert|reverted|reset|load|loaded)\b.{0,20}"
	r"\b(?:settings|configuration|config|profiles?)\b")
_PARTS = re.compile(
	r"\bnvda remote\b(?!.{0,15}\badd-?on\b).{0,30}\b(?:connect\w*|disconnect\w*|status|session|working|running)\b"
	r"|\b(?:is|am i|are we|was)\b.{0,20}\b(?:nvda )?remote\b(?! desktop| access to)(?!.{0,15}\bdesktop\b).{0,15}\b(?:connected|session)\b"
	r"|\bjava (?:access bridge|support)\b.{0,30}\b(?:start\w*|initiali[sz]\w*|working|available|load\w*|on|running)\b"
	r"|\b(?:did|is|was|does)\b.{0,20}\bjava\b.{0,20}\b(?:start\w*|work\w*|available|support\w*|load\w*)\b"
	r"|\b(?:which|what) (?:version of )?(?:ui automation|uia)\b.{0,20}\b(?:version|interface|does nvda use|is nvda using)\b"
	r"|\b(?:ui automation|uia) (?:version|interface)\b"
	r"|\bmathcat\b.{0,30}\b(?:installed|version|loaded|working|on)\b"
	r"|\b(?:did|has|when did) nvda (?:last )?check(?:ed)? for (?:an? )?updates?\b|\bnvda'?s? update check\b")
_RECENT = re.compile(
	r"\bwhat (?:did|has) nvda (?:just )?(?:log|logged|write|written|record|recorded|note|noted)\b"
	rf"|\b(?:anything|something|what'?s|what is) new in {_LOG}"
	rf"|\bnew (?:entries|lines|things) in {_LOG}"
	rf"|\b{_LOG}\b.{{0,50}}\b(?:just now|right now|since|lately|recently|last few|a minute ago|a moment ago|when i pressed|"
	r"just happened)\b"
	rf"|\b(?:just now|recently|lately|a moment ago)\b.{{0,40}}\b{_LOG}"
	r"|\bwhat (?:just )?happened\b.{0,25}\b(?:in|to|with|inside) nvda\b"
	r"|\bwhat (?:was|is) nvda (?:just )?doing\b|\bwhat did nvda (?:just )?do\b")
_SINCE_REQUEST = re.compile(r"\bsince (?:my|the) (?:last|previous) (?:request|question|command)\b|\bsince i (?:last )?asked\b")
_SINCE_READ = re.compile(
	r"\b(?:anything|something|what'?s|what is) new\b|\bsince (?:you|visionclaw) (?:last )?(?:checked|read|looked)\b"
	r"|\bsince (?:the )?last time\b|\bnew (?:entries|lines|things)\b")
_ERRORS = re.compile(
	r"\b(?:read|check|look (?:at|in|through|into)|go through|search|scan|summari[sz]e|anything (?:wrong|bad|odd|interesting|"
	r"unusual|new)|what(?:'s| is| are| does)?|any|tell me|are there|have there been|how many|list|show me (?:the |any )?"
	rf"(?:errors?|problems?|warnings?))\b.{{0,40}}\b{_LOG}"
	rf"|\b{_NV} (?:errors?|exceptions?|tracebacks?|warnings?)\b(?! sounds?\b| beeps?\b| tones?\b)"
	rf"|\b(?:errors?|exceptions?|warnings?) (?:in|of|from|that) {_NV}\b(?! sounds?\b)"
	r"|\b(?:has|have|did|does) nvda (?:had|have|got|logged|thrown|throw|given|shown)\b.{0,15}\b(?:errors?|exceptions?|problems?)\b"
	r"|\bnvda (?:had|has|is having|keeps having|threw|logged|gave|is giving|keeps giving|reported) (?:any |an? |some |lots of "
	r"|many )?(?:errors?|exceptions?)\b"
	r"|\b(?:why|what)\b.{0,40}\bnvda(?:'s)? (?:\w+ ){0,4}?error (?:sound|beep|tone|noise)s?\b")
_NOT_ERRORS = re.compile(r"\b(?:turn|switch|stop|disable|enable|mute|silence)\b.{0,30}\berror (?:sound|beep|tone|noise)")
_ASKING_WORDS = words(
	"read check look at in through into go search scan summarize summarise anything wrong bad odd interesting unusual new what "
	"whats is are does any tell me there have been how many list show error errors exception exceptions traceback tracebacks "
	"warning warnings problem problems crash crashes crashed freeze freezes froze frozen hang hung lag nvda nvdas log logs "
	"logging file files level own why did do explain mean means meaning cause caused causes happen happened just now since last "
	"previous old run session add addon addons add-on add-ons which causing breaking first second third newest latest oldest "
	"number please can could would you your the one this that keep keeps kept having had has")


def _said(text):
	return " ".join(str(text or "").replace("’", "'").split())


def wish(text):
	"""What the user's own words ask of NVDA's own log, or None where they ask nothing of it: a dictionary with do (ERRORS,
	EXPLAIN, ADDONS, FREEZES, DRIVERS, LAST_RUN, RECENT, LEVEL, SETTINGS, WHERE, SESSION, OBJECT, INPUT_HELP, SAVED, PARTS),
	since (for RECENT), which (a number, 1 the newest, -1 the oldest, or None), about (the telling words that are not asking
	words), field and compare (for OBJECT), and last (for INPUT_HELP). Kept narrow: the words must name NVDA's log, NVDA's
	errors, freezes or crashes, an add-on causing trouble, NVDA's logging level, NVDA's session, its developer info, keys
	tried in input help, its settings saved or put back, NVDA Remote, Java or UI Automation. VisionClaw's own log ("your
	log") is diagnose.wish's; opening NVDA's log viewer, or a key for it, is NVDA's own command; turning input help on is
	NVDA's own command; "what is its window class" without the developer info is about the object the user is on."""
	said = _said(text)
	low = said.lower()
	if not said:
		return None
	if _OWN.search(low) and not re.search(r"\bnvda", low):
		return None
	if _ABOUT_US.search(low):
		return None
	found = None
	if _SETTINGS.search(low):
		found = SETTINGS
	elif _LEVEL.search(low):
		found = LEVEL
	elif _WHERE.search(low):
		found = WHERE
	elif _VIEWER.search(low) and not _ERROR_WORDS.search(low):
		return None
	elif _OBJECT.search(low):
		found = OBJECT
	elif _INPUT_HELP.search(low):
		found = INPUT_HELP
	elif _EXPLAIN.search(low) and re.search(r"\b(?:error|errors|exception|traceback|warning)\b", low) and (
			re.search(rf"\b{_LOG}", low) or re.search(r"\bnvda", low)):
		found = EXPLAIN
	elif _SAVED.search(low):
		found = SAVED
	elif _PARTS.search(low):
		found = PARTS
	elif _SESSION.search(low):
		found = SESSION
	elif _ADDONS.search(low):
		found = ADDONS
	elif _FREEZES.search(low):
		found = FREEZES
	elif _DRIVERS.search(low):
		found = DRIVERS
	elif _LAST_RUN.search(low):
		found = LAST_RUN
	elif _RECENT.search(low):
		found = RECENT
	elif _ERRORS.search(low) and not _NOT_ERRORS.search(low):
		found = ERRORS
	if found is None:
		return None
	since = None
	if found == RECENT:
		since = SINCE_REQUEST if _SINCE_REQUEST.search(low) else SINCE_READ if _SINCE_READ.search(low) else JUST
	return {"do": found, "since": since, "which": whichNumber(low), "about": " ".join(sorted(words(said) - _ASKING_WORDS)),
		"field": objectField(low) if found == OBJECT else None, "compare": bool(found == OBJECT and _COMPARE.search(low)),
		"last": bool(found == INPUT_HELP and _LAST_KEY.search(low))}


# --- Reading a log ---

_HEAD = re.compile(
	r"^(?P<level>[A-Z][A-Z_]*|Level \d+) - (?P<codepath>.*?) \((?P<clock>\d{2}:\d{2}:\d{2}\.\d{3})\) - (?P<thread>.*) "
	r"\((?P<ident>\d+)\):$")
_FRAME = re.compile(r'^\s*File "(?P<path>[^"]+)", line (?P<line>\d+), in (?P<function>.+?)\s*$')
_THREAD_STACK = re.compile(r"^Python stack for thread \d+ \((?P<name>.*)\):$")
_ADDON_FOLDER = re.compile(r"[\\/]addons[\\/](?P<id>[^\\/]+?)(?:\.pendingInstall)?(?:[\\/]|$)", re.IGNORECASE)
# A line of what was typed or shown in braille, as NVDA writes it at the Input/output level (inputCore.py, brailleHandler.py).
# Such lines never stand in an entry that is read; should one ever, it is left out all the same.
_PRIVATE_LINE = re.compile(r"^(?:Input: |Braille window dots: )")


class Entry:
	"""One entry of NVDA's log. lines: the message and what follows it (a traceback), and nothing at all for a private level;
	clock: the time of day as NVDA wrote it; when: seconds since the epoch, once stamp() has worked it out."""

	__slots__ = ("level", "codepath", "clock", "thread", "lines", "when")

	def __init__(self, level, codepath, clock, thread, lines=None):
		self.level = level
		self.codepath = codepath if level in READ else ""
		self.clock = clock
		self.thread = thread if level in READ else ""
		self.lines = lines if lines is not None else []
		self.when = None

	@property
	def private(self):
		return self.level not in READ

	@property
	def message(self):
		return self.lines[0].strip() if self.lines else ""

	def seconds(self):
		hours, minutes, rest = self.clock.split(":")
		return int(hours) * 3600 + int(minutes) * 60 + float(rest)

	def __repr__(self):
		return f"Entry({self.level}, {self.clock}, {self.message[:40]!r})"


def _lines(source):
	if isinstance(source, str):
		return source.splitlines()
	return source


def parse(source, check=None):
	"""The entries of NVDA's log, in the order they were written. source: the text, or lines of it. Lines before the first
	entry (as when only the end of a file was read) are left out. The lines of a private entry are dropped as they are read:
	nothing of what was typed or spoken is kept. check: called now and then, to stop a long read when the user stops."""
	entries = []
	current = None
	for number, raw in enumerate(_lines(source)):
		if check is not None and number % 5000 == 4999:
			check()
		line = raw.rstrip("\r\n")
		head = _HEAD.match(line)
		if head:
			level = head.group("level")
			current = Entry(level, head.group("codepath"), head.group("clock"), head.group("thread"))
			entries.append(current)
			continue
		if current is None or current.private:
			continue
		current.lines.append("" if _PRIVATE_LINE.match(line) else line)
	return entries


def counted(entries):
	"""How many entries of each private level there were: {level: count}. Their words were never kept."""
	found = {}
	for entry in entries:
		if entry.private:
			found[entry.level] = found.get(entry.level, 0) + 1
	return found


def privateText(entries):
	"""One sentence on what was only counted, or ""."""
	total = sum(counted(entries).values())
	if not total:
		return ""
	return (f"{total} {'entry' if total == 1 else 'entries'} of the levels that hold what you type, what NVDA says and NVDA's "
		f"debug notes {'was' if total == 1 else 'were'} only counted; VisionClaw never reads them.")


def stamp(entries, lastWritten):
	"""Each entry's time, as seconds since the epoch. NVDA writes only the time of day, so the date is worked out backwards
	from lastWritten (when the file was last written, or now): the last entry is on that day, unless its time of day is
	later than lastWritten's, and a jump back of more than twelve hours between two entries is a new day. A whole day
	without a single entry cannot be seen."""
	if not entries:
		return entries
	anchor = time.localtime(lastWritten)
	midnight = time.mktime((anchor.tm_year, anchor.tm_mon, anchor.tm_mday, 0, 0, 0, 0, 0, -1))
	anchorSeconds = lastWritten - midnight
	day = midnight
	later = None
	for entry in reversed(entries):
		try:
			seconds = entry.seconds()
		except ValueError:
			continue
		if later is None:
			if seconds > anchorSeconds + 300:
				day = _dayBefore(day)
		elif seconds - later > 43200:
			day = _dayBefore(day)
		entry.when = day + seconds
		later = seconds
	return entries


def _dayBefore(midnight):
	before = time.localtime(midnight - 43200)
	return time.mktime((before.tm_year, before.tm_mon, before.tm_mday, 0, 0, 0, 0, 0, -1))


def entriesSince(entries, since=None, until=None):
	"""The entries written from since up to until (seconds since the epoch; None leaves that end open). Entries whose time
	is not known are left out where a stretch of time is asked for."""
	found = []
	for entry in entries:
		if since is None and until is None:
			found.append(entry)
		elif entry.when is not None and (since is None or entry.when >= since) and (until is None or entry.when <= until):
			found.append(entry)
	return found


# --- Where an entry comes from ---

def trace(entry):
	"""The frames of an entry's last traceback, or of its stack trace: [(path, line, function)], the outermost first."""
	lines = entry.lines
	start = None
	for at in range(len(lines) - 1, -1, -1):
		if lines[at].strip() in ("Traceback (most recent call last):", "Stack trace:"):
			start = at
			break
	if start is None:
		return []
	frames = []
	for line in lines[start + 1:]:
		found = _FRAME.match(line)
		if found:
			frames.append((found.group("path"), int(found.group("line")), found.group("function")))
	return frames


def exception(entry):
	"""The last line of an entry's traceback, as Python wrote it ("OSError: [WinError 5] Access is denied"), or ""."""
	lines = entry.lines
	start = next((at for at in range(len(lines) - 1, -1, -1) if lines[at].strip() == "Traceback (most recent call last):"), None)
	if start is None:
		return ""
	for line in reversed(lines[start + 1:]):
		if line.strip() and not line[:1].isspace():
			return line.strip()
	return ""


def threadStacks(entry):
	"""The stacks of "Listing stacks for Python threads:" (watchdog.py, the crash handler): {thread name: frames}."""
	stacks = {}
	current = None
	for line in entry.lines:
		head = _THREAD_STACK.match(line.strip())
		if head:
			current = stacks.setdefault(head.group("name"), [])
			continue
		found = _FRAME.match(line)
		if found and current is not None:
			current.append((found.group("path"), int(found.group("line")), found.group("function")))
	return stacks


def addonOfPath(path):
	"""The id of the add-on whose folder a file is in (...\\addons\\<id>\\...), or ""."""
	found = _ADDON_FOLDER.search(str(path or ""))
	return found.group("id") if found else ""


def addonOfCodepath(codepath, modules=None):
	"""The add-on of a codepath NVDA wrote for code outside itself ("external:globalPlugins.clock.GlobalPlugin.script_x"),
	by modules ({"globalPlugins.clock": "clock"}, from the add-ons' folders), or ""."""
	if not str(codepath or "").startswith("external:"):
		return ""
	name = codepath[len("external:"):]
	for prefix in sorted(modules or {}, key=len, reverse=True):
		if name == prefix or name.startswith(prefix + "."):
			return modules[prefix]
	return ""


def addonOf(entry, modules=None, frames=None):
	"""The add-on an entry comes from: the last add-on of its traceback (the one whose code was running when it failed),
	else its codepath, else ""."""
	frames = trace(entry) if frames is None else frames
	for path, _line, _function in reversed(frames):
		found = addonOfPath(path)
		if found:
			return found
	return addonOfCodepath(entry.codepath, modules)


def addonPlace(frames, addon):
	"""Where in an add-on's own files something happened: (file inside the add-on, line, function) of its last frame there."""
	for path, line, function in reversed(frames):
		if addonOfPath(path) == addon:
			normal = str(path).replace("\\", "/")
			found = re.search(r"/addons/[^/]+/(.*)$", normal, re.IGNORECASE)
			return (found.group(1) if found else os.path.basename(normal)), line, function
	return None


def addonName(addon, names=None):
	"""An add-on as the user knows it: its name from its manifest, with its id where they differ."""
	if not addon:
		return ""
	name = (names or {}).get(addon) or (names or {}).get(addon.lower()) or ""
	if addon.lower() == "visionclaw":
		return "VisionClaw itself"
	if name and name.lower() != addon.lower():
		return f"{name} ({addon})"
	return name or addon


# --- What NVDA reported, in plain words ---

SPEECH, AUDIO, BRAILLE, START, END, FREEZE, CRASH, ADDON, CONFIG, OTHER = (
	"speech", "audio", "braille", "start", "end", "freeze", "crash", "addon", "config", "other")
# What other parts of NVDA report (Java, UI Automation, MathCAT, updates), NVDA Remote, the developer info, input help.
PARTS_GROUP, REMOTE, OBJECT_GROUP, INPUT_GROUP = "parts", "remote", "object", "input"


def _braille(name):
	name = name.strip("'\"")
	return "no braille display" if name == "noBraille" else name


def _seconds(text):
	try:
		value = float(text)
	except (TypeError, ValueError):
		return str(text)
	if value >= 90:
		return f"about {round(value / 60)} minutes"
	if value >= 10:
		return f"about {round(value)} seconds"
	return f"{round(value, 1):g} seconds"


# (kind, group, levels, pattern on the message, the sentence). Every message was read from NVDA's source (the header).
_FACTS = (
	("started", START, ("INFO",), r"^Starting NVDA version (?P<version>\S+)", lambda m: f"NVDA {m['version']} started."),
	("initialized", START, ("INFO",), r"^NVDA initialized$", lambda m: "NVDA finished starting."),
	("windows", START, ("INFO",), r"^Windows version: (?P<version>.+)$", lambda m: f"NVDA runs on Windows {m['version']}."),
	("addonsOff", ADDON, ("INFO",), r"^Add-ons are disabled\. Restart NVDA to enable them\.$",
		lambda m: "NVDA was started with all add-ons turned off."),
	("exiting", END, ("INFO",), r"^Exiting$", lambda m: "NVDA began to close."),
	("exited", END, ("INFO",), r"^NVDA exit$", lambda m: "NVDA closed normally."),
	("sessionEnding", END, ("INFO",), r"^Windows session ending$",
		lambda m: "Windows was shutting down, restarting or signing out, so NVDA closed."),
	("restartUnsafe", END, ("INFO",), r"^Restarting unsafely$", lambda m: "NVDA restarted at once, without closing properly."),
	("coreFailure", CRASH, ("CRITICAL",), r"^core failure$", lambda m: "NVDA's core failed, and NVDA closed."),
	("crashed", CRASH, ("CRITICAL",), r"^NVDA crashed!", lambda m: "NVDA crashed."),
	("restartCrash", CRASH, ("INFO",), r"^Restarting due to crash$", lambda m: "NVDA restarted itself after the crash."),
	("crashLoop", CRASH, ("ERROR",), r"^Crash loop detected \((?P<count>\d+) crashes in (?P<seconds>\d+) seconds\)",
		lambda m: f"NVDA crashed {m['count']} times in {m['seconds']} seconds, so it stopped restarting itself after a crash "
		"until that stops."),
	("mutex", END, ("ERROR",), r"^Prior NVDA exited without releasing mutex",
		lambda m: "The NVDA that ran before did not close properly; NVDA advises restarting the computer."),
	("freezeStart", FREEZE, ("INFO",), r"^Starting freeze recovery after (?P<seconds>[\d.]+) seconds\.$",
		lambda m: f"NVDA stopped responding, and began to recover after {_seconds(m['seconds'])}."),
	("frozen", FREEZE, ("ERROR",), r"^Core frozen in stack! \((?P<seconds>[\d.]+) seconds\)",
		lambda m: f"NVDA had been frozen for {_seconds(m['seconds'])}."),
	("recovered", FREEZE, ("INFO",), r"^Recovered from freeze after (?P<seconds>[\d.]+) seconds\.$",
		lambda m: f"NVDA recovered after being frozen for {_seconds(m['seconds'])}."),
	("synthLoaded", SPEECH, ("INFO",), r"^Loaded synthDriver (?P<name>\S+)$",
		lambda m: f"NVDA loaded the speech synthesizer {m['name']}."),
	("synthFailed", SPEECH, ("ERROR",), r"^setSynth failed for (?P<name>\S+)",
		lambda m: f"The speech synthesizer {m['name']} could not be started."),
	("synthImport", SPEECH, ("ERROR",), r"^Error while importing SynthDriver (?P<name>\S+)",
		lambda m: f"The speech synthesizer {m['name']} could not be loaded at all."),
	("synthBack", SPEECH, ("INFO",), r"^Falling back to previous synthDriver (?P<name>\S+)",
		lambda m: f"NVDA went back to the speech synthesizer it had before, {m['name']}."),
	("synthSearch", SPEECH, ("INFO",), r"^Searching for next synthDriver$",
		lambda m: "NVDA looked for another speech synthesizer that works."),
	("synthNext", SPEECH, ("INFO",), r"^Falling back to next synthDriver (?P<name>\S+)",
		lambda m: f"NVDA tried the speech synthesizer {m['name']} instead."),
	("badVoice", SPEECH, ("WARNING",), r"^Invalid voice: (?P<voice>.+)$",
		lambda m: f"The voice {m['voice']} could not be used by the speech synthesizer."),
	("audioDevice", AUDIO, ("WARNING",), r"^Couldn't open specified or default audio device\.",
		lambda m: "NVDA could not open the sound output device that was chosen, or the default one; there may be no sound device."),
	("waveFailed", AUDIO, ("ERROR",), r"^Error playing wave file$", lambda m: "NVDA could not play one of its sounds."),
	("noEndpoint", AUDIO, ("DEBUGWARNING",), r"^Unable to play wave file as the render endpoint was not found\.$",
		lambda m: "NVDA found no sound output device to play a sound on."),
	("feedFailed", AUDIO, ("DEBUGWARNING",), r"^Error feeding audio$",
		lambda m: "Sound could not be sent to the sound output device."),
	("brailleLoaded", BRAILLE, ("INFO",),
		r"^Loaded braille display driver (?P<name>'[^']*'|\S+), current display has (?P<cells>\d+) cells\.$",
		lambda m: "NVDA is set to no braille display." if _braille(m["name"]) == "no braille display" else
		f"NVDA loaded the braille display driver {_braille(m['name'])}, with {m['cells']} cells."),
	("brailleFailed", BRAILLE, ("ERROR",), r"^Error initializing display driver (?P<name>'[^']*'|\S+)",
		lambda m: f"The braille display driver {_braille(m['name'])} could not be started."),
	("brailleDetect", BRAILLE, ("DEBUGWARNING",), r"^Couldn't initialize display driver (?P<name>'[^']*'|\S+)",
		lambda m: f"Automatic detection found a braille display for {_braille(m['name'])}, but its driver could not be started."),
	("brailleGone", BRAILLE, ("ERROR",), r"^Braille display unavailable\. Disabling",
		lambda m: "The braille display stopped answering, so NVDA stopped using it."),
	("brailleCells", BRAILLE, ("ERROR",), r"^Error displaying cells\. Disabling display",
		lambda m: "NVDA could not show text on the braille display, so it stopped using it."),
	("brailleClose", BRAILLE, ("ERROR",), r"^Error terminating previous display driver",
		lambda m: "The braille display driver used before could not be closed properly."),
	("brailleTable", BRAILLE, ("ERROR",),
		r"^Invalid translation table \((?P<table>[^)]*)\), falling back to default \((?P<fallback>[^)]*)\)\.",
		lambda m: f"The braille table {m['table']} could not be used, so NVDA went back to {m['fallback']}."),
	("brailleShort", BRAILLE, ("WARNING",), r"^Braille cells are shorter than the display size\.",
		lambda m: "Fewer braille cells were sent than the display has; NVDA left the rest blank."),
	("configSaved", CONFIG, ("INFO",), r"^Base configuration saved$", lambda m: "NVDA saved its settings."),
	("profileSaved", CONFIG, ("INFO",), r"^Saved configuration profile (?P<name>.+)$",
		lambda m: f"NVDA saved the configuration profile {m['name']}."),
	("triggersSaved", CONFIG, ("INFO",), r"^Profile triggers saved$",
		lambda m: "NVDA saved which programs switch to which configuration profile."),
	("badLevel", CONFIG, ("WARNING",), r"^invalid setting for logging level: (?P<level>.+)$",
		lambda m: "NVDA's logging level setting was not valid, so NVDA set it to Info."),
	("addonLoad", ADDON, ("ERROR",), r"^Error loading Addon from path: (?P<path>.+)$",
		lambda m: f"The add-on in the folder {addonOfPath(m['path']) or os.path.basename(m['path'].rstrip(chr(92) + '/'))} "
		"could not be loaded."),
	("incompatible", ADDON, ("DEBUGWARNING",), r"^Add-on (?P<name>\S+) is considered incompatible",
		lambda m: f"NVDA found the add-on {m['name']} not made for this version of NVDA, so it is blocked."),
	("pluginImport", ADDON, ("ERROR",), r"^Error importing global plugin (?P<name>\S+)",
		lambda m: f"The part {m['name']} of an add-on could not be loaded."),
	("pluginStart", ADDON, ("ERROR",), r"^Error initializing global plugin",
		lambda m: "A part of an add-on could not be started."),
	("appModule", ADDON, ("ERROR",), r"^error in appModule '(?P<name>[^']+)'",
		lambda m: f"NVDA's support for the program {m['name']} had an error."),
	("terminate", END, ("ERROR",), r"^Error terminating (?P<name>.+)$",
		lambda m: f"A part of NVDA, {m['name']}, did not close properly."),
	("python", START, ("INFO",), r"^Using Python version (?P<version>\S+)", lambda m: f"NVDA uses Python {m['version']}."),
	("configDir", START, ("INFO",), r"^Config dir: (?P<path>.+)$", lambda m: f"NVDA keeps its settings in {m['path']}."),
	("scratchpad", START, ("INFO",), r"^Developer Scratchpad mode enabled$",
		lambda m: "NVDA's developer scratchpad is turned on, so it also loads code from its scratchpad folder."),
	("configLoading", CONFIG, ("INFO",), r"^Loading config: (?P<path>.+)$",
		lambda m: f"NVDA loaded its settings from {m['path']}."),
	("configCorrupt", CONFIG, ("ERROR",), r"^Error loading base configuration; the base configuration file will be reinitialized\."
		r"(?: A copy of your previous configuration file will be saved at (?P<backup>.+))?",
		lambda m: "NVDA could not read its settings file, so it started with new settings"
		+ (f"; it kept a copy of the old file at {m['backup']}." if m.get("backup") else ".")),
	("notWriting", CONFIG, ("INFO",), r"^Not writing profile, either --secure or --launcher args present$",
		lambda m: "NVDA did not save its settings, because it runs in secure mode or from its launcher."),
	("saveReadOnly", CONFIG, ("WARNING",), r"^Error saving configuration; probably read only file system",
		lambda m: "NVDA could not save its settings; the folder they are kept in may not be writable."),
	("saveFailed", CONFIG, ("WARNING",), r"^Error saving configuration$", lambda m: "NVDA could not save its settings."),
	("configReverted", CONFIG, ("INFO",), r"^Reverted to saved configuration$",
		lambda m: "NVDA put back its saved settings, or its factory defaults; it writes the same line for both."),
	("triggersFailed", CONFIG, ("ERROR",), r"^Error loading profile triggers",
		lambda m: "NVDA could not read which programs switch to which configuration profile."),
	("jabOn", PARTS_GROUP, ("INFO",), r"^Java Access Bridge support initialized$", lambda m: "NVDA's support for Java programs started."),
	("jabMissing", PARTS_GROUP, ("WARNING",), r"^Java Access Bridge not available$",
		lambda m: "NVDA's support for Java programs is not available: the Java Access Bridge was not found."),
	("jabFailed", PARTS_GROUP, ("ERROR",), r"^Error initializing Java Access Bridge support",
		lambda m: "NVDA's support for Java programs could not be started."),
	("uiaVersion", PARTS_GROUP, ("INFO",), r"^UIAutomation: (?P<interface>\S+)$",
		lambda m: f"NVDA uses UI Automation through Windows' interface {m['interface']}."),
	("uiaOff", PARTS_GROUP, ("WARNING",), r"^UIA disabled in configuration$", lambda m: "UI Automation is turned off in NVDA's settings."),
	("uiaFailed", PARTS_GROUP, ("ERROR",), r"^Error initializing UIA support", lambda m: "NVDA's UI Automation support could not be started."),
	("mathcat", PARTS_GROUP, ("INFO",), r"^MathCAT (?P<version>\S+) installed\.", lambda m: f"MathCAT {m['version']} is installed for math."),
	("updateCheck", PARTS_GROUP, ("INFO",), r"^Performing automatic update check$", lambda m: "NVDA checked for an update of itself."),
	("updateDownload", PARTS_GROUP, ("ERROR",), r"^Error downloading ", lambda m: "NVDA could not download an update of itself."),
	("remoteStart", REMOTE, ("INFO",), r"^Initializing NVDA Remote client$", lambda m: "NVDA Remote got ready."),
	("remoteConnecting", REMOTE, ("INFO",), r"^Initiating connection as (?P<mode>\S+) to ",
		lambda m: "NVDA Remote began to connect, " + ("to control the other computer." if m["mode"] in ("master", "leader")
		else "to let this computer be controlled." if m["mode"] in ("slave", "follower") else f"as {m['mode']}.")),
	("remoteLeader", REMOTE, ("INFO",), r"^Successfully connected as leader$",
		lambda m: "NVDA Remote connected; this computer controls the other one."),
	("remoteLeaderEnding", REMOTE, ("INFO",), r"^Leader session disconnecting$",
		lambda m: "NVDA Remote began to end the session in which this computer controls the other one."),
	("remoteLeaderEnded", REMOTE, ("INFO",), r"^Leader session disconnected$",
		lambda m: "NVDA Remote ended the session in which this computer controls the other one."),
	("remoteFollower", REMOTE, ("INFO",), r"^Control connector connected$",
		lambda m: "NVDA Remote connected; this computer can be controlled from the other one."),
	("remoteFollowerEnded", REMOTE, ("INFO",), r"^Control connector disconnected$",
		lambda m: "NVDA Remote ended the session in which this computer is controlled."),
	("remoteClient", REMOTE, ("INFO",), r"^Client connected: ", lambda m: "Another computer joined the NVDA Remote session."),
	("remoteLeaderLeft", REMOTE, ("INFO",), r"^Leader client disconnected: ",
		lambda m: "The controlling computer left the NVDA Remote session."),
	("remoteLost", REMOTE, ("INFO",), r"^Transport disconnected from follower session$",
		lambda m: "The connection of the NVDA Remote session was lost."),
	("remoteDisconnect", REMOTE, ("INFO",), r"^Disconnecting from remote session$", lambda m: "NVDA Remote was disconnected."),
	("remoteFailed", REMOTE, ("ERROR",), r"^Failed to connect to \S+$", lambda m: "NVDA Remote could not connect to the server."),
	("remoteRetry", REMOTE, ("WARNING",), r"^Failed to connect to \S+\. Retrying\.$",
		lambda m: "NVDA Remote could not connect, and is trying again."),
	("remoteCertificate", REMOTE, ("WARNING",), r"^Certificate validation failed for ",
		lambda m: "The NVDA Remote server's certificate could not be checked."),
	("remoteVersion", REMOTE, ("ERROR",), r"^Protocol version mismatch detected with relay server$",
		lambda m: "The NVDA Remote server works with another version of NVDA Remote."),
	("remoteSecure", REMOTE, ("ERROR",), r"^Creating new Remote Access connections is not allowed in Secure Mode\.",
		lambda m: "NVDA Remote cannot connect while NVDA runs in secure mode."),
	("remoteKeysOn", REMOTE, ("INFO",), r"^Remote key control enabled$",
		lambda m: "Your keys now go to the other computer, through NVDA Remote."),
	("remoteKeysOff", REMOTE, ("INFO",), r"^Remote key control disabled$",
		lambda m: "Your keys stay on this computer again."),
	("devInfo", OBJECT_GROUP, ("INFO",), r"^Developer info for navigator object:", lambda m: "NVDA wrote the developer info of an object."),
	("noDevInfo", OBJECT_GROUP, ("INFO",), r"^No developer info for navigator object$",
		lambda m: "NVDA had no developer info for the navigator object."),
	("inputHelp", INPUT_GROUP, ("INFO",), r"^Input help: gesture (?P<gesture>.+?)(?:, bound to script (?P<script>\S+)(?: on (?P<location>\S+))?)?$",
		lambda m: f"In input help, {keyWords(m['gesture'])} was pressed" + (f": the command {m['script']}." if m.get("script")
		else ", which runs no command there.")),
)
# Facts whose entry's traceback says why: that reason is said after the fact.
_WITH_REASON = frozenset(("synthFailed", "synthImport", "brailleFailed", "brailleGone", "brailleCells", "pluginImport", "pluginStart",
	"jabFailed", "uiaFailed", "configCorrupt"))
_FACT_PATTERNS = [(kind, group, levels, re.compile(pattern), say) for kind, group, levels, pattern, say in _FACTS]
# Entries that are part of another fact and say nothing of their own: the stacks after a freeze or a crash, and the
# configuration NVDA writes when it starts (it is settings, and is not read out).
_NOT_FACTS = re.compile(r"^(?:Listing stacks for Python threads:|Config loaded |Config before schema update)")


def factOf(entry, modules=None):
	"""What one readable entry reports, as a plain dict, or None for a private entry or one that says nothing of its own:
	{clock, when, level, kind, group, said, addon}. A known message is said in plain words; another error or warning is
	said as NVDA wrote its first line; other info is kind "info"."""
	if entry.private:
		return None
	message = entry.message
	if _NOT_FACTS.match(message):
		return None
	frames = trace(entry)
	addon = addonOf(entry, modules, frames)
	for kind, group, levels, pattern, say in _FACT_PATTERNS:
		if entry.level not in levels:
			continue
		found = pattern.match(message)
		if found:
			said = say(found.groupdict())
			reason = exception(entry) if kind in _WITH_REASON else ""
			if reason:
				said += f" The reason NVDA wrote: {reason}"
			return {"clock": entry.clock[:8], "when": entry.when, "level": entry.level, "kind": kind, "group": group,
				"said": said, "addon": addon}
	if entry.level in ("ERROR", "CRITICAL"):
		what = message or exception(entry) or entry.codepath
		return {"clock": entry.clock[:8], "when": entry.when, "level": entry.level, "kind": "error", "group": OTHER,
			"said": f"An error: {what.rstrip('.:')}.", "addon": addon}
	if entry.level == "WARNING":
		return {"clock": entry.clock[:8], "when": entry.when, "level": entry.level, "kind": "warning", "group": OTHER,
			"said": f"A warning: {message.rstrip('.:')}.", "addon": addon}
	return {"clock": entry.clock[:8], "when": entry.when, "level": entry.level, "kind": "info" if entry.level == "INFO" else "note",
		"group": OTHER, "said": message, "addon": addon}


def facts(entries, modules=None):
	"""What NVDA reported, one plain dict for each readable entry that says something of its own, in the order written."""
	return [fact for fact in (factOf(entry, modules) for entry in entries) if fact is not None]


def isOwn(fact_or_entry, modules=None):
	"""Whether something in NVDA's log was written by VisionClaw itself."""
	if isinstance(fact_or_entry, Entry):
		addon = addonOf(fact_or_entry, modules)
	else:
		addon = fact_or_entry.get("addon", "")
	return str(addon).lower() == "visionclaw"


# --- Errors ---

_VARYING = re.compile(r"0x[0-9a-f]+|\d+(?:\.\d+)?", re.IGNORECASE)
_NOT_ERRORS_HERE = ("frozen", "crashed", "coreFailure", "crashLoop")


class Problem:
	"""One error of NVDA's log, each kind once: what, how often, when first and last, where it came from."""

	def __init__(self, entry, frames, exceptionLine, addon):
		self.level = entry.level
		self.message = entry.message or exceptionLine or (
			"Python could not finish cleaning up something" if entry.codepath.startswith("Exception ignored in")
			else entry.codepath)
		self.codepath = entry.codepath
		self.frames = frames
		self.exception = exceptionLine
		self.addon = addon
		self.count = 1
		self.first = self.last = entry.clock[:8]
		self.firstWhen = self.lastWhen = entry.when
		self.order = 0
		self.kind = "error"

	def key(self):
		place = self.frames[-1] if self.frames else ("", 0, "")
		return (_VARYING.sub("#", self.message), self.exception.split(":", 1)[0], os.path.basename(str(place[0])), place[2],
			"" if self.frames else self.codepath)

	def __repr__(self):
		return f"Problem({self.message[:40]!r}, {self.count}, {self.addon!r})"


def errors(entries, modules=None):
	"""The errors and critical errors of a log, each kind once, the newest first, with how often. Freezes and crashes are
	told by freezes() and ending(), not here."""
	grouped = {}
	for order, entry in enumerate(entries):
		if entry.level not in ("ERROR", "CRITICAL"):
			continue
		fact = factOf(entry, modules)
		if fact and fact["kind"] in _NOT_ERRORS_HERE:
			continue
		frames = trace(entry)
		problem = Problem(entry, frames, exception(entry), addonOf(entry, modules, frames))
		problem.order = order
		problem.kind = fact["kind"] if fact else "error"
		if problem.kind != "error":
			# A message NVDA's source names is said in its plain words: "setSynth failed for sapi5" is a synthesizer that
			# could not be started.
			problem.message = fact["said"].split(" The reason NVDA wrote:")[0].rstrip(".")
		key = problem.key()
		if key in grouped:
			old = grouped[key]
			old.count += 1
			old.last, old.lastWhen, old.order = problem.last, problem.lastWhen, order
			old.frames, old.exception = problem.frames or old.frames, problem.exception or old.exception
		else:
			grouped[key] = problem
	return sorted(grouped.values(), key=lambda problem: problem.order, reverse=True)


def byAddon(problems):
	"""How many errors came from each add-on, the most first: [(add-on id, errors in all, kinds)]."""
	found = {}
	for problem in problems:
		if problem.addon:
			total, kinds = found.get(problem.addon, (0, 0))
			found[problem.addon] = (total + problem.count, kinds + 1)
	return sorted(((addon, total, kinds) for addon, (total, kinds) in found.items()), key=lambda item: (-item[1], item[0]))


# NVDA's own parts as a person says them, by the first name of NVDA's code a codepath begins with.
_NVDA_PARTS = {
	"speech": "speech", "synthDriverHandler": "the speech synthesizer", "synthDrivers": "the speech synthesizers",
	"braille": "braille", "brailleDisplayDrivers": "the braille display drivers", "brailleTables": "braille tables",
	"nvwave": "sound output", "tones": "beeps", "NVDAObjects": "the controls it reads", "virtualBuffers": "browse mode",
	"browseMode": "browse mode", "treeInterceptorHandler": "browse mode", "cursorManager": "the review of text",
	"UIAHandler": "UI Automation", "IAccessibleHandler": "IAccessible", "JABHandler": "Java programs",
	"appModules": "a program's support", "appModuleHandler": "programs' support", "config": "settings", "gui": "its windows",
	"watchdog": "the freeze watch", "core": "its core", "inputCore": "input", "keyboardHandler": "the keyboard",
	"mouseHandler": "the mouse", "touchHandler": "touch", "addonHandler": "add-ons", "globalCommands": "its commands",
	"scriptHandler": "its commands", "_remoteClient": "NVDA Remote", "mathPres": "math", "updateCheck": "updates",
	"textInfos": "text", "editableText": "edit fields", "eventHandler": "events", "api": "its core", "winConsoleHandler": "consoles",
	"screenCurtain": "the screen curtain", "vision": "vision", "_magnifier": "the magnifier", "documentBase": "documents",
	"globalPluginHandler": "add-ons", "unhandled exception": "an error nothing caught"}


def partOf(codepath):
	"""The part of NVDA a codepath is in, as a person says it: "browse mode", "the speech synthesizer"."""
	name = str(codepath or "")[len("external:"):] if str(codepath or "").startswith("external:") else str(codepath or "")
	if name in _NVDA_PARTS:
		return _NVDA_PARTS[name]
	if " " in name or not name:
		return "code NVDA could not name"
	return _NVDA_PARTS.get(name.split(".")[0], name.split(".")[0])


def fileWords(relative):
	"""A file of an add-on as the user hears it: a name with two underscores on each side is said in words."""
	relative = str(relative or "")
	if relative.endswith("/__init__.py"):
		return f"the main file of its folder {relative[:-len('/__init__.py')]}"
	return f"its file {relative}"


def whereText(problem, names=None, detail=False):
	"""Where an error came from, in a sentence: the add-on and its function, or NVDA's own part. detail: also the file and
	line of the add-on, and NVDA's codepath, for one error the user asked about."""
	if problem.addon:
		place = addonPlace(problem.frames, problem.addon)
		said = f"From the add-on {addonName(problem.addon, names)}"
		if place:
			said += f", in its function {place[2]}"
			if detail:
				said += f", in {fileWords(place[0])}, line {place[1]}"
		return said + "."
	if problem.codepath.startswith("external:"):
		return "From code outside NVDA that VisionClaw cannot match to an installed add-on" + (
			f": {problem.codepath[len('external:'):]}." if detail else ".")
	if problem.codepath:
		return f"In NVDA's own part for {partOf(problem.codepath)}" + (f", {problem.codepath}." if detail else ".")
	return ""


def problemText(problem, names=None, detail=False):
	"""One error in plain sentences. detail: with Python's own words for it, and the file and line, for one error the user
	asked about; a list says neither, as code and file paths are no help when listening to many."""
	said = [f"{problem.message.rstrip('.:')}."]
	if problem.count == 1:
		said.append(f"Once, at {problem.last}.")
	else:
		said.append(f"{problem.count} times, the first at {problem.first} and the last at {problem.last}.")
	where = whereText(problem, names, detail)
	if where:
		said.append(where)
	if detail and problem.exception and problem.exception.rstrip(".") != problem.message.rstrip("."):
		said.append(f"Python's error: {problem.exception}")
	return " ".join(said)


def addonsSummary(problems, names=None):
	"""Which add-ons the errors come from, in a sentence, or "" when there are no errors."""
	if not problems:
		return ""
	total = sum(problem.count for problem in problems)
	fromAddons = byAddon(problems)
	if not fromAddons:
		return "None of them comes from an add-on: they happened in NVDA's own code."
	parts = [f"{count} from {addonName(addon, names)}" for addon, count, _kinds in fromAddons]
	inAddons = sum(count for _addon, count, _kinds in fromAddons)
	rest = total - inAddons
	tail = f", and {rest} in NVDA's own code" if rest else ""
	return f"Of the {total} errors, " + ", ".join(parts) + tail + "."


def errorsText(problems, names=None, run="this run", about=""):
	"""The errors of a log, the newest first, every one of them, with which add-ons they come from first."""
	if not problems:
		return f"NVDA's log of {run} has no errors."
	total = sum(problem.count for problem in problems)
	lines = [f"NVDA's log of {run} has {len(problems)} different errors, {total} in all, the newest first." if len(problems) > 1
		else f"NVDA's log of {run} has one error" + (f", {total} times." if total > 1 else ".")]
	summary = addonsSummary(problems, names)
	if summary:
		lines.append(summary)
	for number, problem in enumerate(problems, 1):
		lines.append(f"{number}. {problemText(problem, names)}")
	if any(problem.addon.lower() == "visionclaw" for problem in problems if problem.addon):
		lines.append("To look into the errors of VisionClaw itself, ask VisionClaw what errors are in its own log.")
	lines.append("To hear what one of them means, ask VisionClaw to explain NVDA's error by its number.")
	return "\n".join(lines)


def addonNamed(about, names=None):
	"""The add-on the user's words name, by its id or its name, or ""."""
	said = words(about)
	if not said:
		return ""
	plain = set(re.findall(r"[a-z0-9]+", str(about).lower()))
	for addon, name in sorted((names or {}).items(), key=lambda item: -len(str(item[1]))):
		named = words(name)
		if addon.lower() in plain or (named and named <= said):
			return addon
	return ""


def addonsText(problems, freezeList, names=None, run="this run", about=""):
	"""Which add-ons NVDA's errors and freezes come from: the most useful answer when an add-on breaks NVDA."""
	named = addonNamed(about, names)
	if named:
		own = [problem for problem in problems if problem.addon == named]
		if not own:
			return f"NVDA's log of {run} has no errors from the add-on {addonName(named, names)}."
		return errorsText(own, names, run).replace(f"NVDA's log of {run} has", f"From the add-on {addonName(named, names)}, NVDA's log of {run} has", 1)
	fromAddons = byAddon(problems)
	frozenIn = {}
	for freeze in freezeList:
		if freeze.addon:
			frozenIn[freeze.addon] = frozenIn.get(freeze.addon, 0) + 1
	if not fromAddons and not frozenIn:
		if not problems:
			return f"NVDA's log of {run} has no errors, and no add-on was working when NVDA froze."
		return (f"NVDA's log of {run} has {sum(p.count for p in problems)} errors, and none of them comes from an add-on: they "
			"happened in NVDA's own code.")
	lines = []
	if fromAddons:
		lines.append(f"Errors in NVDA's log of {run} that come from add-ons, the most first:")
		for number, (addon, total, kinds) in enumerate(fromAddons, 1):
			newest = next(problem for problem in problems if problem.addon == addon)
			lines.append(f"{number}. {addonName(addon, names)}: {total} {'error' if total == 1 else 'errors'}"
				+ (f" of {kinds} kinds" if kinds > 1 else "") + f". The newest, at {newest.last}: {newest.message.rstrip('.:')}.")
		rest = sum(p.count for p in problems if not p.addon)
		if rest:
			lines.append(f"{rest} more {'error' if rest == 1 else 'errors'} happened in NVDA's own code.")
	for addon, times in sorted(frozenIn.items(), key=lambda item: -item[1]):
		lines.append(f"While NVDA was frozen, it was working in the add-on {addonName(addon, names)}"
			+ (f", {times} times." if times > 1 else ", once."))
	lines.append("An add-on can be turned off in NVDA's Add-on Store, to see whether the trouble stops; VisionClaw never turns "
		"one off itself.")
	return "\n".join(lines)


# --- Freezes ---

class Freeze:
	"""One time NVDA stopped responding: when it began, the longest time it said it was frozen, whether it recovered and
	after how long, and where NVDA's main thread was working (the add-on, or NVDA's own function)."""

	def __init__(self, clock, when, seconds):
		self.clock = clock
		self.when = when
		self.seconds = seconds
		self.severe = False
		self.recovered = None
		self.addon = ""
		self.function = ""
		self.program = ""


def freezes(entries, modules=None):
	"""Every time NVDA stopped responding, in the order they happened (watchdog.py)."""
	found = []
	current = None
	lastWasFreeze = False
	for entry in entries:
		if entry.private:
			continue
		message = entry.message
		if entry.level == "INFO" and message.startswith("Starting freeze recovery after"):
			seconds = _number(message)
			current = Freeze(entry.clock[:8], entry.when, seconds)
			found.append(current)
			lastWasFreeze = False
		elif entry.level == "ERROR" and message.startswith("Core frozen in stack!"):
			if current is None or current.recovered is not None:
				current = Freeze(entry.clock[:8], entry.when, 0.0)
				found.append(current)
			current.severe = True
			current.seconds = max(current.seconds or 0.0, _number(message))
			lastWasFreeze = True
		elif entry.level == "INFO" and message.startswith("Listing stacks for Python threads:") and lastWasFreeze and current:
			stack = threadStacks(entry).get("MainThread", [])
			for path, _line, function in reversed(stack):
				addon = addonOfPath(path)
				if addon:
					current.addon, current.function = addon, function
					break
			if not current.addon and stack:
				current.function = stack[-1][2]
			for path, _line, _function in reversed(stack):
				program = re.search(r"(?:^|[\\/])appModules[\\/](\w+)\.pyc?$", str(path))
				if program:
					current.program = program.group(1)
					break
			lastWasFreeze = False
		elif entry.level == "INFO" and message.startswith("Recovered from freeze after") and current is not None:
			current.recovered = _number(message)
			current.seconds = max(current.seconds or 0.0, current.recovered)
			current = None
			lastWasFreeze = False
		else:
			lastWasFreeze = False
	return found


def _number(message):
	found = re.search(r"(\d+(?:\.\d+)?) seconds", message)
	return float(found.group(1)) if found else 0.0


def freezesText(freezeList, names=None, run="this run"):
	"""The freezes of a log in plain sentences."""
	if not freezeList:
		return f"NVDA's log of {run} shows no time that NVDA stopped responding."
	count = len(freezeList)
	longest = max(freezeList, key=lambda freeze: freeze.seconds or 0.0)
	lines = [f"NVDA's log of {run} shows {'one time' if count == 1 else f'{count} times'} that NVDA stopped responding."]
	lines.append(("It lasted" if count == 1 else "The longest lasted") + f" {_seconds(longest.seconds)}, from {longest.clock}.")
	severe = sum(1 for freeze in freezeList if freeze.severe)
	if severe:
		lines.append(("It was" if count == 1 else f"{severe} of them were") + " long enough for NVDA to write that its core was frozen.")
	working = {}
	for freeze in freezeList:
		if freeze.addon:
			working[freeze.addon] = working.get(freeze.addon, 0) + 1
	for addon, times in sorted(working.items(), key=lambda item: -item[1]):
		lines.append(f"While NVDA was frozen it was working in the add-on {addonName(addon, names)}"
			+ (f", {times} times." if times > 1 else "."))
	programs = sorted({freeze.program for freeze in freezeList if freeze.program and not freeze.addon})
	if not working and programs:
		lines.append(f"While it was frozen, it was working in NVDA's own support for the program {', '.join(programs)}.")
	elif not working and any(freeze.function for freeze in freezeList):
		lines.append("While it was frozen, it was working in NVDA's own code, not in an add-on.")
	if freezeList[-1].recovered is None:
		lines.append(f"The last one, from {freezeList[-1].clock}, has no recovery written after it: NVDA was still frozen when "
			"this log ends.")
	if not severe and not working:
		lines.append("Which add-on or part of NVDA was working is written only after a freeze of more than 15 seconds.")
	return "\n".join(lines)


# --- The speech synthesizer, the sound and the braille display ---

_DRIVER_GROUPS = (SPEECH, AUDIO, BRAILLE)


def driverFacts(entries, groups=_DRIVER_GROUPS, modules=None):
	"""What NVDA reported about the speech synthesizer, the sound output and the braille display, in the order written."""
	return [fact for fact in facts(entries, modules) if fact["group"] in groups]


def groupsAsked(about):
	"""Which of the speech synthesizer, the sound and the braille display the user's words name; all three where none."""
	said = str(about or "").lower()
	asked = []
	if re.search(r"\b(synth\w*|voices?|speech|speak\w*|talk\w*|silent)\b", said):
		asked.append(SPEECH)
	if re.search(r"\b(audio|sound\w*|speakers?|headphones?|device)\b", said):
		asked.append(AUDIO)
	if re.search(r"\bbraille\b|\bdisplay\b|\bcells?\b", said):
		asked.append(BRAILLE)
	return tuple(asked) or _DRIVER_GROUPS


_TROUBLE = frozenset((
	"synthFailed", "synthImport", "synthBack", "synthSearch", "synthNext", "badVoice", "audioDevice", "waveFailed",
	"noEndpoint", "feedFailed", "brailleFailed", "brailleDetect", "brailleGone", "brailleCells", "brailleClose",
	"brailleTable", "brailleShort"))


def driversText(found, level="", run="this run", groups=_DRIVER_GROUPS):
	"""NVDA's speech synthesizer, sound and braille display as its log tells them: the trouble in the order it happened,
	and what NVDA loaded last."""
	named = {SPEECH: "the speech synthesizer", AUDIO: "the sound output", BRAILLE: "the braille display"}
	what = " or ".join(named[group] for group in groups)
	trouble = [fact for fact in found if fact["kind"] in _TROUBLE]
	lines = []
	if trouble:
		lines.append(f"Trouble with {what} in NVDA's log of {run}, in the order it happened:")
		lines.extend(f"At {fact['clock']}: {fact['said']}" for fact in trouble)
	else:
		lines.append(f"NVDA's log of {run} has no trouble with {what}.")
	loaded = [fact for fact in found if fact["kind"] == "synthLoaded"]
	if loaded and SPEECH in groups:
		lines.append(f"The last speech synthesizer NVDA loaded, at {loaded[-1]['clock']}, is "
			f"{loaded[-1]['said'][len('NVDA loaded the speech synthesizer '):].rstrip('.')}.")
	shown = [fact for fact in found if fact["kind"] == "brailleLoaded"]
	if shown and BRAILLE in groups:
		lines.append(f"The last braille display setting NVDA loaded, at {shown[-1]['clock']}: {shown[-1]['said']}")
	if level == "INFO" and AUDIO in groups:
		lines.append("At the level Info, NVDA does not write that it found no sound device to play a sound on, nor sound "
			"that could not be sent to the device; those are written from the level Debug warning.")
	return "\n".join(lines)


# --- How a run ended ---

CLOSED, CRASHED, WINDOWS_ENDED, FROZE, NOT_TOLD, LOG_OFF, CORE_FAILED, CLOSING = (
	"closed", "crashed", "windowsEnded", "froze", "notTold", "logOff", "coreFailed", "closing")


def crashWork(entries, modules=None, names=None):
	"""The add-on NVDA's main thread was working in when NVDA crashed, from the stacks the crash handler lists after
	"NVDA crashed!", as the user knows it, or ""."""
	crashedAt = None
	for at, entry in enumerate(entries):
		if entry.level == "CRITICAL" and entry.message.startswith("NVDA crashed!"):
			crashedAt = at
	if crashedAt is None:
		return ""
	for entry in entries[crashedAt + 1:crashedAt + 4]:
		if entry.level == "INFO" and entry.message.startswith("Listing stacks for Python threads:"):
			for path, _line, _function in reversed(threadStacks(entry).get("MainThread", [])):
				addon = addonOfPath(path)
				if addon:
					return addonName(addon, names)
			return ""
	return ""


def ending(entries, modules=None, names=None):
	"""How a run ended, from its log: {how, said, version, started, lastClock}. Plain code; the log's own words decide."""
	readable = [entry for entry in entries if not entry.private]
	found = facts(readable, modules)
	kinds = [fact["kind"] for fact in found]
	version = next((fact["said"][len("NVDA "):-len(" started.")] for fact in found if fact["kind"] == "started"), "")
	started = next((fact["clock"] for fact in found if fact["kind"] == "started"), "")
	lastClock = (entries[-1].clock[:8] if entries else "")
	freezeList = freezes(entries, modules)
	if "crashed" in kinds:
		at = next(fact for fact in reversed(found) if fact["kind"] == "crashed")
		said = f"NVDA crashed, at {at['clock']}."
		working = crashWork(entries, modules, names)
		if working:
			said += f" When it crashed, NVDA's main thread was working in the add-on {working}."
		if "restartCrash" in kinds:
			said += " It then restarted itself."
		return {"how": CRASHED, "said": said, "version": version, "started": started, "lastClock": lastClock}
	if "coreFailure" in kinds:
		at = next(fact for fact in reversed(found) if fact["kind"] == "coreFailure")
		return {"how": CORE_FAILED, "said": f"NVDA's core failed at {at['clock']}, and NVDA closed.", "version": version,
			"started": started, "lastClock": lastClock}
	if "sessionEnding" in kinds:
		at = next(fact for fact in reversed(found) if fact["kind"] == "sessionEnding")
		said = f"Windows was shutting down, restarting or signing out at {at['clock']}, and NVDA was closed with it."
		if "exited" in kinds:
			said += " NVDA wrote that it closed normally."
		return {"how": WINDOWS_ENDED, "said": said, "version": version, "started": started, "lastClock": lastClock}
	if "exited" in kinds:
		at = next(fact for fact in reversed(found) if fact["kind"] == "exited")
		return {"how": CLOSED, "said": f"NVDA closed normally, at {at['clock']}.", "version": version, "started": started,
			"lastClock": lastClock}
	if "exiting" in kinds:
		at = next(fact for fact in reversed(found) if fact["kind"] == "exiting")
		return {"how": CLOSING, "said": f"NVDA began to close normally at {at['clock']}, but its log ends at {lastClock}, before "
			"NVDA wrote that it had closed: it may have hung while closing.", "version": version, "started": started,
			"lastClock": lastClock}
	if freezeList and freezeList[-1].recovered is None:
		return {"how": FROZE, "said": f"NVDA was frozen from {freezeList[-1].clock} until its log ends, at {lastClock}: it was "
			"closed or restarted while it was frozen.", "version": version, "started": started, "lastClock": lastClock}
	if started and "windows" not in kinds and "initialized" not in kinds:
		return {"how": LOG_OFF, "said": "That log stops while NVDA was starting, before NVDA wrote which Windows it runs on. That "
			"is how the log looks when NVDA's logging level was Disabled, so how that run ended cannot be told from it.",
			"version": version, "started": started, "lastClock": lastClock}
	return {"how": NOT_TOLD, "said": f"The log does not say that NVDA closed: it stops at {lastClock}, without NVDA's last "
		"line, NVDA exit. That happens when NVDA was ended from outside, for instance by the task manager, when the computer "
		"lost power or was turned off, or when NVDA stopped before it could write.",
		"version": version, "started": started, "lastClock": lastClock}


def lastRunText(entries, names=None, modules=None):
	"""The run before this one (nvda-old.log): which NVDA, how it ended, its errors and freezes, and its last entries."""
	if not entries:
		return "NVDA's log of the run before, nvda-old.log, is not there or is empty."
	end = ending(entries, modules, names)
	lines = []
	if end["version"]:
		lines.append(f"The run before this one was NVDA {end['version']}, started at {end['started']}.")
	lines.append(end["said"])
	problems = errors(entries, modules)
	if problems:
		total = sum(problem.count for problem in problems)
		lines.append(f"It had {total} {'error' if total == 1 else 'errors'}." + (" " + addonsSummary(problems, names)
			if byAddon(problems) else ""))
		newest = problems[0]
		lines.append(f"The last error, at {newest.last}: {newest.message.rstrip('.:')}. {whereText(newest, names, True)}".rstrip())
	else:
		lines.append("It had no errors.")
	freezeList = freezes(entries, modules)
	if freezeList:
		lines.append(freezesText(freezeList, names, "the run before").replace("NVDA's log of the run before shows ", "It shows ", 1))
	shown = [fact for fact in facts([entry for entry in entries if not entry.private], modules)
		if fact["kind"] not in ("windows",)][-LAST_ENTRIES:]
	if shown:
		lines.append("Its last entries, the last one last: " + " ".join(f"At {fact['clock']}: {_sentence(fact['said'])}"
			for fact in shown))
	private = privateText(entries)
	if private:
		lines.append(private)
	return "\n".join(lines)


def _sentence(text):
	text = str(text or "").strip()
	return text if text.endswith((".", "!", "?")) else text + "."


# --- What NVDA wrote just now ---

def window(since, begun, previousEnd=None):
	"""The stretch of time a question about what just happened is about: (from, to, words). begun: when the request was
	made (what VisionClaw does for it is left out); previousEnd: when the request before it ended, or None."""
	if since == SINCE_REQUEST and previousEnd:
		return previousEnd, begun, f"since your last request ended, at {_clockOf(previousEnd)}"
	start = begun - JUST_NOW
	if previousEnd and previousEnd > start:
		return previousEnd, begun, f"since your last request ended, at {_clockOf(previousEnd)}"
	return start, begun, f"in the {JUST_NOW // 60} minutes before you asked"


def _clockOf(when):
	return time.strftime("%H:%M:%S", time.localtime(when))


def recentText(entries, stretch, modules=None, names=None):
	"""What NVDA wrote in a stretch of time, in plain words, in the order written. VisionClaw's own entries are left out and
	counted; private ones are only counted."""
	found = facts([entry for entry in entries if not entry.private], modules)
	own = [fact for fact in found if isOwn(fact)]
	found = [fact for fact in found if not isOwn(fact)]
	told = [fact for fact in found if fact["kind"] != "info" and fact["kind"] != "note"]
	plain = len(found) - len(told)
	if not found and not own and not counted(entries):
		return f"NVDA wrote nothing to its log {stretch}."
	lines = []
	if told:
		lines.append(f"What NVDA wrote to its log {stretch}, in order:")
		for fact in told:
			fromAddon = f" From the add-on {addonName(fact['addon'], names)}." if fact["addon"] and fact["kind"] in ("error", "warning") else ""
			lines.append(f"At {fact['clock']}: {_sentence(fact['said'])}{fromAddon}")
	else:
		lines.append(f"NVDA wrote no error, warning or change of its speech, sound or braille {stretch}.")
	if plain:
		lines.append(f"{plain} more {'entry' if plain == 1 else 'entries'} of plain information, such as what NVDA or an add-on "
			"noted while it worked.")
	if own:
		lines.append(f"{len(own)} {'entry' if len(own) == 1 else 'entries'} written by VisionClaw itself "
			f"{'is' if len(own) == 1 else 'are'} left out.")
	private = privateText(entries)
	if private:
		lines.append(private)
	return "\n".join(lines)


# --- The logging level ---

def levelName(state):
	"""The level NVDA logs at now, as its name in logHandler ("INFO"), from state (see levelText)."""
	effective = state.get("effective")
	if isinstance(effective, int):
		for name, number in LEVELS.items():
			if number == effective:
				return name
	return str(state.get("configured") or "INFO").upper()


def isOff(state):
	"""Whether NVDA writes no log now: the level is OFF, secure mode, no file, or no file being written."""
	return (levelName(state) == "OFF" or bool(state.get("secure")) or not state.get("file") or state.get("writing") is False)


_LEVEL_SAYS = {
	"INFO": "NVDA writes its errors, warnings and basic information such as what it loads; that is enough for VisionClaw to "
		"find NVDA's errors, freezes and crashes.",
	"DEBUGWARNING": "NVDA writes what Info writes, and warnings that are not caused by severe errors.",
	"IO": "NVDA also writes every key you press and everything it says and shows in braille. VisionClaw only counts those "
		"lines and never reads them. If you are concerned about privacy, set it back to Info when you are done.",
	"DEBUG": "NVDA also writes what you type, what it says, and its debug notes. VisionClaw only counts those lines and never "
		"reads them. If you are concerned about privacy, set it back to Info when you are done.",
	"DEBUG_UNREDACTED": "NVDA writes everything Debug writes and does not hide secrets such as passwords. VisionClaw only "
		"counts those lines and never reads them; NVDA advises this level only for a short time.",
}
WHERE_SETTING = ("NVDA's logging level is in NVDA's settings: the category Privacy and Security, the combo box Logging level. "
	"NVDA+control+g opens NVDA's settings; then choose Privacy and Security in the list of categories.")
ABOVE_INFO = ("Info is enough for errors. A level above Info makes NVDA ask its own question first, because it may record "
	"what you type and what NVDA says.")
NEVER_CHANGED = "VisionClaw never changes NVDA's logging level itself."


def offText(state):
	"""Why NVDA writes no log now, and how the user turns it on. Plain words; nothing is changed."""
	if state.get("secure"):
		return ("NVDA runs in secure mode here, as on the sign-in screen, and writes no log in secure mode, so VisionClaw has "
			"nothing to read.")
	if state.get("forced"):
		return ("NVDA's log is off, because NVDA was started with its logging turned off from its command line. The Logging "
			"level combo box in NVDA's settings is unavailable until NVDA is started again in the usual way, from the Start "
			"menu or its desktop shortcut.")
	if levelName(state) == "OFF":
		return ("NVDA's log is off: its logging level is Disabled, so NVDA writes nothing while it runs apart from a brief "
			"message at start-up, and VisionClaw has nothing to read. " + WHERE_SETTING + " " + ABOVE_INFO + " " + NEVER_CHANGED)
	return ("NVDA could not open its log file, so it writes nothing, and VisionClaw has nothing to read. Restarting NVDA "
		"usually opens it again.")


def canOffer(state):
	"""Whether opening NVDA's Privacy and Security settings would help: not in secure mode, and not while the level is
	forced, when the combo box is unavailable."""
	return not state.get("secure") and not state.get("forced")


def levelText(state):
	"""NVDA's logging level now, and whether it is forced, in plain words."""
	if isOff(state):
		return offText(state)
	name = levelName(state)
	said = [f"NVDA's logging level is {LEVEL_NAMES.get(name, name)}.", _LEVEL_SAYS.get(name, "")]
	configured = str(state.get("configured") or "").upper()
	if state.get("forced"):
		said.append("It was set when NVDA was started, from its command line or with Restart with debug logging enabled in "
			"NVDA's Exit dialog, so the Logging level combo box in NVDA's settings is unavailable until NVDA is restarted "
			"normally.")
	elif configured and configured != name and configured in LEVEL_NAMES:
		said.append(f"The setting says {LEVEL_NAMES[configured]}.")
	said.append(f"NVDA writes its log to the file {state.get('file')}.")
	return " ".join(part for part in said if part)


def settingsText(state):
	"""The answer to a request to change NVDA's logging level: where it is, what the levels mean, and that VisionClaw does
	not change it."""
	if state.get("secure") or state.get("forced"):
		return offText(state) if isOff(state) else levelText(state)
	name = levelName(state)
	return " ".join((
		NEVER_CHANGED + f" It is {LEVEL_NAMES.get(name, name)} now.", WHERE_SETTING, ABOVE_INFO,
		"Input/output and the debug levels write what you type and what NVDA says, so set the level back to Info when you "
		"are done."))


def locationText(state):
	"""Where NVDA's log is, and NVDA's own keys for it (NVDA's user guide, Log Viewer)."""
	if isOff(state) and not state.get("file"):
		return offText(state)
	folder = os.path.dirname(str(state.get("file") or ""))
	said = [f"NVDA's log of this run is the file {state.get('file')}."]
	if folder:
		said.append(f"The log of the run before is {os.path.join(folder, OLD_FILE)}, in the same folder.")
	said.append("NVDA's own log viewer shows it: in the NVDA menu, which NVDA+n opens, under Tools, View log. NVDA+f1 opens the "
		"log viewer too, after writing facts about the object you are on. NVDA+control+shift+f1 pressed once marks a starting "
		"point, and pressed again copies what NVDA logged since then to the clipboard, which helps with a bug report.")
	return " ".join(said)


OFFER = "Open NVDA's Privacy and Security settings now, at the Logging level combo box?"


# --- One error explained by a model ---

EXPLAIN_TASK = (
	"You are VisionClaw, an assistant inside the NVDA screen reader. You read one error from NVDA's own log and tell the user "
	"in a few plain sentences what it most likely means.\n"
	"Rules: Say what NVDA or the add-on was doing, what went wrong, and whether it is harmless or stops something the user "
	"does. Use only the error given. Name the add-on when one is given. Do not write code. If the cause cannot be told from "
	"it, say so.")


def chosen(problems, want, names=None):
	"""The error a request is about: by its number (1 the newest), by an add-on or other words that name it, else the newest."""
	if not problems:
		return None
	which = (want or {}).get("which")
	if which:
		return problems[which - 1] if 0 < which <= len(problems) else problems[-1] if which == -1 else None
	about = words((want or {}).get("about", ""))
	if about:
		addon = addonNamed(" ".join(about), names)
		if addon:
			own = [problem for problem in problems if problem.addon == addon]
			if own:
				return own[0]
		scored = []
		for at, problem in enumerate(problems):
			said = words(f"{problem.message} {problem.exception} {problem.codepath} "
				f"{' '.join(function for _p, _l, function in problem.frames)}")
			shared = len(about & said)
			if shared:
				scored.append((-shared, at))
		if scored:
			return problems[min(scored)[1]]
	return problems[0]


def modelFacts(problem, names=None, clip=None):
	"""What the model is told of one error: the error, Python's error, where it went, the add-on. Only an error entry, which
	is of a level that is read. clip: llm.clip, for how much of the trace a model reads."""
	lines = [f"Error in NVDA's log: {problem.message}"]
	if problem.exception:
		lines.append(f"Python's error: {problem.exception}")
	if problem.count > 1:
		lines.append(f"It happened {problem.count} times.")
	if problem.addon:
		lines.append(f"It came from the add-on {addonName(problem.addon, names)}.")
	elif problem.codepath:
		lines.append(f"Where NVDA wrote it from: {problem.codepath}")
	if problem.frames:
		where = "; ".join(
			f"{(addonPlace([frame], addonOfPath(frame[0])) or (os.path.basename(str(frame[0]).replace(chr(92), '/')),))[0]} "
			f"line {frame[1]} in {frame[2]}" for frame in problem.frames[-6:])
		lines.append("Where it went, the last place last: " + (clip(where, 900) if clip else where))
	return "\n".join(lines)


# --- Your NVDA session ---

def session(entries):
	"""This run as its log tells it: {version, started, startedWhen, ready, windows, python, configDir, addonsOff,
	scratchpad}. What the log does not say is "" or False."""
	found = {"version": "", "started": "", "startedWhen": None, "ready": "", "windows": "", "python": "", "configDir": "",
		"addonsOff": False, "scratchpad": False}
	for entry in entries:
		if entry.private or entry.level != "INFO":
			continue
		message = entry.message
		started = re.match(r"^Starting NVDA version (\S+)", message)
		if started and not found["version"]:
			found["version"], found["started"], found["startedWhen"] = started.group(1), entry.clock[:8], entry.when
		elif message == "NVDA initialized" and not found["ready"]:
			found["ready"] = entry.clock[:8]
		elif message.startswith("Windows version: "):
			found["windows"] = message[len("Windows version: "):].strip()
		elif message.startswith("Using Python version "):
			found["python"] = message[len("Using Python version "):].split()[0]
		elif message.startswith("Config dir: "):
			found["configDir"] = message[len("Config dir: "):].strip()
		elif message == "Add-ons are disabled. Restart NVDA to enable them.":
			found["addonsOff"] = True
		elif message == "Developer Scratchpad mode enabled":
			found["scratchpad"] = True
	return found


def durationWords(seconds):
	"""A length of time as a person says it: "3 hours and 12 minutes", "2 days and 4 hours", "under a minute"."""
	try:
		seconds = int(seconds)
	except (TypeError, ValueError):
		return ""
	if seconds < 60:
		return "under a minute"
	days, rest = divmod(seconds, 86400)
	hours, rest = divmod(rest, 3600)
	minutes = rest // 60

	def unit(count, name):
		return f"{count} {name}" + ("" if count == 1 else "s")

	if days:
		return unit(days, "day") + (f" and {unit(hours, 'hour')}" if hours else "")
	if hours:
		return unit(hours, "hour") + (f" and {unit(minutes, 'minute')}" if minutes else "")
	return unit(minutes, "minute")


def sessionText(entries, old=None, now=None, modules=None, names=None):
	"""This run of NVDA in plain sentences, and how the run before ended (nvda-old.log): the plan's "Your NVDA session"."""
	found = session(entries)
	lines = []
	if found["version"]:
		said = f"This run of NVDA, version {found['version']}, started at {found['started']}"
		said += f", and was ready at {found['ready']}." if found["ready"] else "."
		lines.append(said)
		if found["startedWhen"] and now:
			lines.append(f"It has been running for {durationWords(now - found['startedWhen'])}.")
	else:
		lines.append("This run's log does not say when NVDA started: VisionClaw read only its end.")
	if found["windows"]:
		lines.append(f"It runs on Windows {found['windows']}" + (f", with Python {found['python']}." if found["python"] else "."))
	lines.append("It was started with all add-ons turned off." if found["addonsOff"] else "It was started with its add-ons.")
	if found["scratchpad"]:
		lines.append("NVDA's developer scratchpad is turned on.")
	if old is not None:
		if old:
			lines.append("The run before: " + ending(old, modules, names)["said"])
		else:
			lines.append("NVDA's log of the run before is not there.")
	return "\n".join(lines)


# --- Objects: NVDA's developer info (NVDA+f1) ---

# What each field of the developer info is, as a person says it, by its name in lowercase.
FIELD_WORDS = {
	"name": "name", "role": "kind", "roletext": "kind as the program words it", "states": "states", "isfocusable": "can take the focus",
	"hasfocus": "has the focus", "description": "description", "location": "place on the screen", "value": "value",
	"processid": "process number", "python object": "Python object", "python class mro": "Python classes", "textinfo": "text support",
	"appmodule": "program", "appmodule.productname": "product name", "appmodule.productversion": "product version",
	"appmodule.apparchitecture": "architecture", "windowhandle": "window handle", "windowclassname": "window class",
	"windowcontrolid": "control ID", "windowstyle": "window style", "extendedwindowstyle": "extended window style",
	"windowthreadid": "window's thread", "windowtext": "window text", "displaytext": "text drawn in the window",
	"iaccessibleobject": "IAccessible object", "iaccessiblechildid": "IAccessible child ID", "iaccessible accname": "IAccessible name",
	"iaccessible accrole": "IAccessible role", "iaccessible accstate": "IAccessible states",
	"iaccessible accdescription": "IAccessible description", "iaccessible accvalue": "IAccessible value",
	"iaccessible2 windowhandle": "IAccessible2 window handle", "iaccessible2 uniqueid": "IAccessible2 unique ID",
	"iaccessible2 role": "IAccessible2 role", "iaccessible2 states": "IAccessible2 states",
	"iaccessible2 attributes": "IAccessible2 attributes", "iaccessible2 relations": "IAccessible2 relations",
	"uiaelement": "UI Automation element", "uia automationid": "automation ID", "uia frameworkid": "framework",
	"uia runtimeid": "UI Automation runtime ID", "uia providerdescription": "UI Automation provider",
	"uia classname": "UI Automation class name", "uia patterns available": "UI Automation patterns", "framework": "framework"}
# Fields whose name is a plural: "its states are".
_PLURAL = frozenset(("states", "uia patterns available", "iaccessible accstate", "iaccessible2 states", "python class mro",
	"iaccessible2 attributes", "iaccessible2 relations"))
# Fields that hold what is typed into a control: never said for a protected (password) field.
_TYPED = frozenset(("value", "windowtext", "displaytext", "iaccessible accvalue"))
# Fields that differ between any two objects or are only numbers of the moment: left out of "all of it" and comparisons.
_NOISE = frozenset((
	"python object", "uiaelement", "iaccessibleobject", "iaccessible event parameters", "processid", "windowthreadid",
	"windowhandle", "iaccessible2 windowhandle", "uia runtimeid", "iaccessible2 uniqueid", "appmodule.helperlocalbindinghandle",
	"windowstyle", "extendedwindowstyle", "textinfo", "python class mro", "location", "iaccessible2 relations",
	"iaccessible2 attributes", "hasfocus"))
# The words of a question, to the field it asks about. The first that fits.
_FIELDS = (
	(r"\bautomation ?id\b", "uia automationid"), (r"\bframework\b|\bmade with\b|\bbuilt with\b|\btoolkit\b", "framework"),
	(r"\buia class\b|\bui automation class\b", "uia classname"), (r"\bwindow class\b|\bclass name\b", "windowclassname"),
	(r"\bcontrol id\b", "windowcontrolid"), (r"\bwindow handle\b|\bhwnd\b", "windowhandle"), (r"\bwindow style\b", "windowstyle"),
	(r"\bwindow text\b", "windowtext"), (r"\bpatterns?\b", "uia patterns available"), (r"\bprovider\b", "uia providerdescription"),
	(r"\bruntime id\b", "uia runtimeid"), (r"\bunique id\b", "iaccessible2 uniqueid"), (r"\bchild id\b", "iaccessiblechildid"),
	(r"\bacc ?role\b|\biaccessible role\b|\bmsaa role\b", "iaccessible accrole"),
	(r"\bacc ?state\b|\bmsaa states?\b|\biaccessible states?\b", "iaccessible accstate"), (r"\bacc ?name\b", "iaccessible accname"),
	(r"\battributes\b", "iaccessible2 attributes"), (r"\bpython class\w*\b|\bmro\b|\boverlay\b", "python class mro"),
	(r"\bproduct version\b|\bprogram'?s? version\b", "appmodule.productversion"), (r"\bproduct name\b", "appmodule.productname"),
	(r"\barchitecture\b|\b(?:32|64)[- ]?bit\b", "appmodule.apparchitecture"),
	(r"\bapp ?module\b|\bwhich program\b|\bprocess\b", "appmodule"), (r"\bstates?\b", "states"),
	(r"\brole\b|\bwhat kind\b|\bcontrol type\b", "role"), (r"\bdescription\b", "description"), (r"\bvalue\b", "value"),
	(r"\blocation\b|\bposition\b|\bwhere (?:is|was) it\b", "location"), (r"\bfocusable\b|\btake (?:the )?focus\b", "isfocusable"),
	(r"\bname\b|\bcalled\b|\blabel\b", "name"))
_ROLE_WORDS = {
	"EDITABLETEXT": "edit field", "PASSWORDEDIT": "password field", "CHECKBOX": "check box", "RADIOBUTTON": "radio button",
	"COMBOBOX": "combo box", "MENUITEM": "menu item", "MENUBAR": "menu bar", "POPUPMENU": "menu", "LISTITEM": "list item",
	"TREEVIEW": "tree view", "TREEVIEWITEM": "tree view item", "TOGGLEBUTTON": "toggle button", "STATICTEXT": "text",
	"PROPERTYPAGE": "property page", "TABCONTROL": "tab control", "SPLITBUTTON": "split button", "MENUBUTTON": "menu button",
	"DROPDOWNBUTTON": "drop-down button", "SPINBUTTON": "spin button", "SCROLLBAR": "scroll bar", "STATUSBAR": "status bar",
	"TOOLBAR": "tool bar", "PROGRESSBAR": "progress bar", "TABLECELL": "table cell", "TABLEROW": "table row",
	"COLUMNHEADER": "column header", "ROWHEADER": "row header", "DATAITEM": "data item", "HEADERITEM": "header item",
	"GRAPHIC": "graphic", "FRAME": "frame", "UNKNOWN": "unknown kind"}


def objectField(text):
	"""The field of the developer info the user's words ask about, or None for all of it."""
	low = str(text or "").lower()
	for pattern, field in _FIELDS:
		if re.search(pattern, low):
			return field
	return None


def _value(raw):
	"""A field's value as NVDA wrote it, read back: a quoted string unquoted, None as "", the rest as it is."""
	raw = str(raw or "").strip()
	cut = raw.endswith(" (truncated)")
	if cut:
		raw = raw[:-len(" (truncated)")]
	if raw == "None":
		return ""
	if raw[:1] in ("'", '"') and raw[-1:] == raw[:1]:
		try:
			import ast
			value = ast.literal_eval(raw)
			if isinstance(value, str):
				raw = value
		except (ValueError, SyntaxError):
			pass
	return raw + (" (NVDA wrote only its beginning)" if cut else "")


def devInfos(entries):
	"""Every "Developer info for navigator object" in the entries, oldest first: {clock, when, fields: {field in lowercase:
	value}}. NVDA writes one when NVDA+f1 is pressed (globalCommands.py), at the level Info."""
	found = []
	for entry in entries:
		if entry.private or entry.level != "INFO" or not entry.message.startswith("Developer info for navigator object:"):
			continue
		fields = {}
		for line in entry.lines[1:]:
			key, sep, value = line.partition(": ")
			if sep and key.strip():
				fields.setdefault(key.strip().lower(), _value(value))
		found.append({"clock": entry.clock[:8], "when": entry.when, "fields": fields})
	return found


def _protected(fields):
	return "PROTECTED" in str(fields.get("states", "")).upper() or str(fields.get("role", "")).upper() == "PASSWORDEDIT"


def roleWords(role):
	role = str(role or "").strip().upper()
	return _ROLE_WORDS.get(role, role.lower().replace("_", " ")) if role else ""


def _classes(fields):
	return re.findall(r"<class '([\w.]+)'>", str(fields.get("python class mro", "")))


def frameworkOf(fields):
	"""How the program tells NVDA about the object, and its framework, in words: "UI Automation, framework WPF"."""
	interface = ""
	classes = " ".join(_classes(fields)).lower()
	if any(key.startswith("uia ") for key in fields):
		interface = "UI Automation"
	elif "iaccessible2 uniqueid" in fields or "iaccessible2 role" in fields:
		interface = "IAccessible2"
	elif "iaccessible accrole" in fields:
		interface = "IAccessible, also called MSAA"
	elif "nvdaobjects.jab" in classes:
		interface = "the Java Access Bridge"
	framework = str(fields.get("uia frameworkid", "") or "")
	if framework.lower().startswith("exception"):
		framework = ""
	if interface and framework:
		return f"{interface}, framework {framework}"
	return interface or (f"framework {framework}" if framework else "")


def _program(fields):
	found = re.search(r"appName='([^']*)'", str(fields.get("appmodule", "")))
	return found.group(1) if found else ""


def _overlay(fields, modules=None, names=None):
	"""An add-on whose class NVDA uses for the object, in words, or ""."""
	for name in _classes(fields):
		addon = addonOfCodepath("external:" + name, modules)
		if addon:
			return f"NVDA treats it with a class of the add-on {addonName(addon, names)}, {name.rsplit('.', 1)[-1]}."
	return ""


def _fieldText(fields, field):
	"""One field as a sentence part: "its window class is Button", "it has no automation ID"."""
	words_ = FIELD_WORDS.get(field, field)
	if field in _TYPED and _protected(fields):
		return f"its {words_} is not said, because it is a protected field"
	if field == "framework":
		value = frameworkOf(fields)
		return f"it is shown to NVDA through {value}" if value else "the developer info does not say its framework"
	if field == "role":
		value = roleWords(fields.get("role"))
	elif field == "states":
		value = ", ".join(state.strip().lower() for state in str(fields.get("states", "")).split(",") if state.strip())
	elif field == "appmodule":
		value = _program(fields)
	elif field in ("isfocusable", "hasfocus"):
		value = str(fields.get(field, "") or "")
		if value in ("True", "False"):
			yes = value == "True"
			if field == "isfocusable":
				return "it can take the focus" if yes else "it cannot take the focus"
			return "it has the focus" if yes else "it does not have the focus"
	else:
		value = str(fields.get(field, "") or "")
	if not value or value.lower().startswith("exception"):
		return f"it has no {words_}" if field in fields else f"the developer info has no {words_}"
	return f"its {words_} {'are' if field in _PLURAL else 'is'} {value}"


def objectText(info, field=None, modules=None, names=None):
	"""One developer info in plain words: one field, or all of it but the numbers of the moment. Never what is typed into a
	protected field."""
	if not info:
		return ("NVDA's log of this run has no developer info. Press NVDA+f1 on an object: NVDA writes everything it knows "
			"about it to its log and opens its log viewer, which Escape closes. Then ask again.")
	fields = info["fields"]
	if field:
		said = _fieldText(fields, field)
		return f"In the developer info NVDA wrote at {info['clock']}, {said}."
	kind = roleWords(fields.get("role")) or "object"
	name = fields.get("name", "")
	program = _program(fields)
	lines = [f"The developer info NVDA wrote at {info['clock']} is for the {kind}" + (f" \"{name}\"" if name else " without a name")
		+ (f", in the program {program}." if program else ".")]
	for key in ("states", "description", "value", "isfocusable", "framework", "windowclassname", "windowcontrolid",
			"uia automationid", "uia classname", "uia patterns available", "iaccessible accrole",
			"iaccessible2 role", "appmodule.productname", "appmodule.productversion", "appmodule.apparchitecture"):
		if key == "framework" or key in fields:
			value = _fieldText(fields, key)
			if not value.startswith("the developer info has no") and not (key in ("description", "value") and value.startswith("it has no")):
				lines.append(value[:1].upper() + value[1:] + ".")
	overlay = _overlay(fields, modules, names)
	if overlay:
		lines.append(overlay)
	lines.append("Handles, process numbers and styles are left out; ask for one by its name to hear it.")
	return "\n".join(lines)


def compareText(older, newer):
	"""What differs between two developer infos, field by field, in plain words."""
	if not older or not newer:
		return ("NVDA's log of this run has fewer than two developer infos. Press NVDA+f1 on each object you want to compare, "
			"then ask again.")
	a, b = older["fields"], newer["fields"]
	keys = [key for key in list(a) + [key for key in b if key not in a] if key not in _NOISE]
	changed = []
	for key in keys:
		if key in _TYPED and (_protected(a) or _protected(b)):
			continue
		before, after = (_fieldText(a, key) if key in a else ""), (_fieldText(b, key) if key in b else "")
		if before != after:
			words_ = FIELD_WORDS.get(key, key)
			first = before.split(" is ", 1)[1] if " is " in before else "nothing"
			second = after.split(" is ", 1)[1] if " is " in after else "nothing"
			changed.append(f"its {words_}: {first} before, {second} now")
	head = f"Between the developer info written at {older['clock']} and the one at {newer['clock']}"
	if not changed:
		return head + ", nothing differs but the numbers of the moment, such as handles."
	return head + ", " + ("one thing differs" if len(changed) == 1 else f"{len(changed)} things differ") + ": " + "; ".join(changed) + "."


def objectFacts(info):
	"""The few facts that tell an object apart, as one plain sentence: its kind and name, the program, the automation ID,
	the window class, the framework. Never its value or what is typed into it. "" where there is nothing to say."""
	try:
		fields = (info or {}).get("fields") or {}
		if not fields:
			return ""
		kind = roleWords(fields.get("role")) or "object"
		name = str(fields.get("name", "") or "")
		said = f"The {kind}" + (f" \"{name}\"" if name else " without a name")
		program = _program(fields)
		if program:
			said += f" in the program {program}"
		parts = []
		automation = str(fields.get("uia automationid", "") or "")
		if automation and not automation.lower().startswith("exception"):
			parts.append(f"automation ID {automation}")
		windowClass = str(fields.get("windowclassname", "") or "")
		if windowClass and not windowClass.lower().startswith("exception"):
			parts.append(f"window class {windowClass}")
		framework = frameworkOf(fields)
		if framework:
			parts.append(f"shown through {framework}")
		return said + (": " + ", ".join(parts) if parts else "") + "."
	except Exception:
		return ""


# --- Input help: which command a key runs, and whose it is ---

def keyWords(gesture):
	"""A gesture as NVDA names it in the log ("kb(desktop):NVDA+t") in words: "NVDA+t"."""
	kind, sep, key = str(gesture or "").partition(":")
	if not sep:
		return str(gesture or "")
	key = re.sub(r"(?i)\bnvda\+", "NVDA+", key)
	if kind.startswith("kb"):
		layout = kind[3:-1] if kind.startswith("kb(") else ""
		return key + (f", in the {layout} keyboard layout" if layout and layout != "desktop" else "")
	if kind.startswith("br"):
		return f"{key} on the braille display"
	if kind.startswith("ts"):
		return f"the touch gesture {key}"
	return str(gesture)


_INPUT_LINE = re.compile(r"^Input help: gesture (?P<gesture>.+?)(?:, bound to script (?P<script>\S+)(?: on (?P<location>\S+))?)?$")


def inputHelp(entries, modules=None):
	"""Every key tried in input help (inputCore.py), in order: {clock, when, key, gesture, script, location, addon}. location
	is where the command lives as NVDA writes it ("globalPlugins.clock.GlobalPlugin"); addon the installed add-on it is
	in, by modules."""
	found = []
	for entry in entries:
		if entry.private or entry.level != "INFO":
			continue
		line = _INPUT_LINE.match(entry.message)
		if not line:
			continue
		location = line.group("location") or ""
		found.append({"clock": entry.clock[:8], "when": entry.when, "key": keyWords(line.group("gesture")),
			"gesture": line.group("gesture"), "script": line.group("script") or "", "location": location,
			"addon": addonOfCodepath("external:" + location, modules) if location else ""})
	return found


def ownerWords(item, names=None):
	"""Whose command a key runs, in words."""
	location = item.get("location", "")
	if item.get("addon"):
		return f"the add-on {addonName(item['addon'], names)}"
	if location.startswith("globalCommands"):
		return "NVDA itself"
	if location.startswith("appModules."):
		return f"NVDA's own support for the program {location.split('.')[1]}"
	if location.startswith("globalPlugins."):
		return f"the global plugin {location.split('.')[1]}, which VisionClaw cannot match to an installed add-on"
	if location.startswith(("browseMode", "virtualBuffers", "cursorManager", "treeInterceptorHandler", "documentBase")):
		return "NVDA's browse mode"
	if location:
		return "NVDA itself, for the control you were on"
	return ""


def keySaid(item, names=None, describe=None):
	"""One key tried in input help in words: "NVDA+t, which runs the command ..., of NVDA itself"."""
	script = item["script"]
	if not script:
		return f"{item['key']}, which runs no command there"
	cls = item["location"].rsplit(".", 1)[-1] if item["location"] else ""
	what = (describe or {}).get((cls, script)) or (describe or {}).get(script) or ""
	command = f"the command {what.rstrip('.')}" if what else f"the command {script}"
	owner = ownerWords(item, names)
	return f"{item['key']}, which runs {command}" + (f", of {owner}" if owner else "")


def inputHelpText(items, names=None, last=False, describe=None):
	"""The keys tried in input help in plain words: the last one, or all of them in order. describe: {(class, script) or
	script: the command's description}, from the running NVDA, so that a command is said by what it does."""
	if not items:
		return ("NVDA's log of this run has no keys tried in input help. NVDA+1 turns input help on and off; while it is on, "
			"every key you press is said and written to the log instead of being carried out. Then ask again.")

	def said(item):
		return keySaid(item, names, describe)

	if last:
		item = items[-1]
		return f"The last key you tried in input help, at {item['clock']}, was {said(item)}."
	lines = [f"Keys you tried in input help in this run, in order: {len(items)}."]
	lines.extend(f"{number}. At {item['clock']}: {said(item)}." for number, item in enumerate(items, 1))
	return "\n".join(lines)


# --- Settings and profiles ---

_SAVED_KINDS = ("configLoading", "configCorrupt", "configSaved", "profileSaved", "triggersSaved", "configReverted", "notWriting",
	"saveReadOnly", "saveFailed", "triggersFailed", "badLevel")


def savedText(entries, modules=None):
	"""When NVDA's settings and profiles were loaded, saved or put back, from its log, in order."""
	found = [fact for fact in facts(entries, modules) if fact["kind"] in _SAVED_KINDS]
	if not found:
		return "NVDA's log of this run says nothing about its settings being loaded, saved or put back."
	lines = ["What NVDA's log of this run says about its settings, in order:"]
	lines.extend(f"At {fact['clock']}: {fact['said']}" for fact in found)
	saved = [fact for fact in found if fact["kind"] == "configSaved"]
	lines.append(f"The last time NVDA saved its settings was at {saved[-1]['clock']}." if saved else
		"NVDA has not saved its settings in this run; NVDA+control+c saves them.")
	return "\n".join(lines)


# --- Other parts of NVDA ---

REMOTE_PART, JAVA_PART, UIA_PART, MATH_PART, UPDATE_PART = "remote", "java", "uia", "mathcat", "update"
_PART_WORDS = (
	(REMOTE_PART, r"\bremote\b"), (JAVA_PART, r"\bjava\b"), (UIA_PART, r"\bui automation\b|\buia\b"), (MATH_PART, r"\bmathcat\b|\bmath\b"),
	(UPDATE_PART, r"\bupdates?\b"))
_PART_KINDS = {
	JAVA_PART: ("jabOn", "jabMissing", "jabFailed"), UIA_PART: ("uiaVersion", "uiaOff", "uiaFailed"), MATH_PART: ("mathcat",),
	UPDATE_PART: ("updateCheck", "updateDownload")}
_PART_NONE = {
	REMOTE_PART: "NVDA's log of this run says nothing about NVDA Remote, so it has not connected in this run.",
	JAVA_PART: "NVDA's log of this run does not say whether its support for Java programs started.",
	UIA_PART: "NVDA's log of this run does not say which UI Automation interface it uses.",
	MATH_PART: "NVDA's log of this run does not mention MathCAT.",
	UPDATE_PART: "NVDA's log of this run has no update check."}


def partsAsked(text):
	"""Which other parts of NVDA the user's words ask about; all of them where none is named."""
	low = str(text or "").lower()
	return tuple(part for part, pattern in _PART_WORDS if re.search(pattern, low)) or tuple(part for part, _p in _PART_WORDS)


def remoteState(found):
	"""NVDA Remote's state from the newest of its facts: "leader", "follower", "off" or "" when the log says nothing."""
	for fact in reversed(found):
		if fact["kind"] == "remoteLeader":
			return "leader"
		if fact["kind"] == "remoteFollower":
			return "follower"
		if fact["kind"] in ("remoteLeaderEnded", "remoteFollowerEnded", "remoteLost", "remoteDisconnect", "remoteFailed"):
			return "off"
	return ""


def partsText(entries, asked="", modules=None):
	"""NVDA Remote, Java, UI Automation, MathCAT and update checks as NVDA's log tells them, newest first for each."""
	found = facts(entries, modules)
	lines = []
	for part in partsAsked(asked):
		if part == REMOTE_PART:
			remote = [fact for fact in found if fact["group"] == REMOTE]
			if not remote:
				lines.append(_PART_NONE[part])
				continue
			state = remoteState(remote)
			lines.append({"leader": "NVDA Remote is connected, and this computer controls the other one.",
				"follower": "NVDA Remote is connected, and this computer can be controlled from the other one.",
				"off": "NVDA Remote is not connected now."}.get(state, "NVDA's log does not say whether NVDA Remote is connected."))
			lines.append(f"The last thing NVDA's log says about it, at {remote[-1]['clock']}: {remote[-1]['said']}")
			continue
		mine = [fact for fact in found if fact["kind"] in _PART_KINDS[part]]
		lines.append(f"At {mine[-1]['clock']}: {mine[-1]['said']}" if mine else _PART_NONE[part])
	return "\n".join(lines)


# --- Trouble, for other parts of VisionClaw ---

_TROUBLE_ASK = re.compile(
	r"\bwhy\b.{0,40}\b(?:speech|voice|synth\w*|braille|sound|audio|nvda)\b.{0,30}\b(?:stop\w*|go(?:ne)? silent|went silent|quiet|"
	r"not (?:talking|speaking|working|responding)|cut(?:s|ting)? out|disconnect\w*|crash\w*|freez\w*|froze|hang\w*|lag\w*|slow\w*|"
	r"fail\w*|break\w*|broke|disappear\w*)\b"
	r"|\bnvda\b.{0,20}\b(?:keeps|kept|is) (?:freezing|hanging|crashing|lagging|stopping|going silent|cutting out|being slow)\b"
	r"|\bnvda (?:froze|crashed|went silent|stopped (?:talking|speaking|working|responding)|is (?:so |very |really )?slow)\b",
	re.IGNORECASE)


def asksTrouble(text):
	"""Whether the user's own words ask why something in NVDA went wrong: speech or braille that stopped, NVDA slow, frozen
	or crashed. Plain code; never raises."""
	try:
		return bool(_TROUBLE_ASK.search(_said(text)))
	except Exception:
		return False


def troubleText(entries, modules=None, names=None):
	"""A few plain sentences about the errors, driver fallbacks and freezes in these entries, each with the add-on or the
	part of NVDA it comes from; "" where there are none. Only readable entries are used. Never raises."""
	try:
		readable = [entry for entry in entries or () if not getattr(entry, "private", True)]
		said = []
		problems = [problem for problem in errors(readable, modules) if problem.kind not in _TROUBLE]
		if problems:
			total = sum(problem.count for problem in problems)
			parts = []
			for problem in problems:
				source = (f"from the add-on {addonName(problem.addon, names)}" if problem.addon
					else f"in NVDA's own part for {partOf(problem.codepath)}")
				parts.append(f"{problem.message.rstrip('.:')}, {source}" + (f", {problem.count} times" if problem.count > 1 else ""))
			said.append(("NVDA wrote an error: " if total == 1 else f"NVDA wrote {total} errors: ") + "; ".join(parts) + ".")
		fallbacks = [fact for fact in driverFacts(readable, modules=modules) if fact["kind"] in _TROUBLE]
		if fallbacks:
			said.append(" ".join(_sentence(fact["said"].split(" The reason NVDA wrote:")[0]) for fact in fallbacks))
		froze = freezes(readable, modules)
		if froze:
			longest = max(froze, key=lambda freeze: freeze.seconds or 0.0)
			where = next((f", while it was working in the add-on {addonName(freeze.addon, names)}" for freeze in froze if freeze.addon), "")
			said.append(("NVDA stopped responding once" if len(froze) == 1 else f"NVDA stopped responding {len(froze)} times")
				+ f", the longest for {_seconds(longest.seconds)}{where}.")
		return " ".join(said)
	except Exception:
		return ""


# What a skill may want from NVDA's log (skills.LOG_KINDS), and the facts of each kind.
LOG_KINDS = ("errors", "add-ons", "speech", "audio", "braille", "freezes", "session", "settings", "objects", "input help", "remote")


def factsFor(entries, kind, modules=None, names=None, describe=None):
	"""The facts of one kind of skills.LOG_KINDS in these entries, in the order written, one plain dict each: {clock (the
	time of day NVDA wrote), when (seconds since the epoch, once stamp() worked it out, else None), level, kind, group,
	said (a plain sentence), addon (the add-on's id, or "")}. Only readable entries are used. [] for a kind it does not
	know. Never raises."""
	try:
		readable = [entry for entry in entries or () if not getattr(entry, "private", True)]
		if kind == "objects":
			return [{"clock": info["clock"], "when": info["when"], "level": "INFO", "kind": "devInfo", "group": OBJECT_GROUP,
				"said": objectFacts(info) or "NVDA wrote the developer info of an object.", "addon": ""}
				for info in devInfos(readable)]
		if kind == "input help":
			return [{"clock": item["clock"], "when": item["when"], "level": "INFO", "kind": "inputHelp", "group": INPUT_GROUP,
				"said": f"In input help, {keySaid(item, names, describe)}.", "addon": item["addon"]}
				for item in inputHelp(readable, modules)]
		found = facts(readable, modules)
		if kind == "errors":
			return [fact for fact in found if fact["level"] in ("ERROR", "CRITICAL")]
		if kind == "add-ons":
			return [fact for fact in found if fact["addon"] or fact["group"] == ADDON]
		if kind in ("speech", "audio", "braille"):
			return [fact for fact in found if fact["group"] == kind]
		if kind == "freezes":
			return [fact for fact in found if fact["group"] == FREEZE]
		if kind == "session":
			return [fact for fact in found if fact["group"] in (START, END, CRASH)]
		if kind == "settings":
			return [fact for fact in found if fact["kind"] in _SAVED_KINDS]
		if kind == "remote":
			return [fact for fact in found if fact["group"] == REMOTE]
		return []
	except Exception:
		return []
