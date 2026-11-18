# NVDA add-on development

## What an NVDA add-on is, files and folders
An add-on is a folder with a manifest.ini file and Python code. Code that works everywhere goes in
globalPlugins/name.py. Code for one program goes in appModules/programName.py, where programName is the
program's exe name without .exe. VisionClaw writes global plugins, because they can be loaded without
restarting NVDA. A global plugin can still act in only one program by checking obj.appModule.appName.

## Global plugin skeleton, minimal add-on
```python
import globalPluginHandler
import ui
from scriptHandler import script

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	@script(description="Says hello", gesture="kb:NVDA+shift+h")
	def script_hello(self, gesture):
		ui.message("Hello")
```
The class must be named GlobalPlugin and inherit from globalPluginHandler.GlobalPlugin.

## Key commands, scripts, gestures, hotkeys, shortcuts
A key command is a method named script_name(self, gesture) with the @script decorator from scriptHandler.
gesture is the key, for example "kb:NVDA+shift+k", "kb:control+alt+1", "kb:NVDA+f9". Use several keys with
gestures=["kb:NVDA+k", "kb:NVDA+shift+k"]. Key names: NVDA, control, alt, shift, windows, f1 to f12,
upArrow, downArrow, leftArrow, rightArrow, home, end, pageUp, pageDown, enter, space, escape, tab,
numpad1. Choose keys with NVDA+shift or NVDA+alt and a letter or function key, so they do not clash with
NVDA's own commands. To let the key go on to the program, call gesture.send().

## Pressing a key twice, repeat count
```python
import scriptHandler
count = scriptHandler.getLastScriptRepeatCount()
if count == 0:
	ui.message("pressed once")
else:
	ui.message("pressed twice")
```

## Speaking, messages, beeps, braille output
ui.message("text") speaks and brailles a message. Use it for everything the user should hear.
tones.beep(frequency, milliseconds) plays a beep, for example tones.beep(880, 80); import tones.
speech.cancelSpeech() stops speech; import speech. ui.browseableMessage("long text", "Title") shows a
long text in a window the user can read with the arrow keys.

## Running something later, timers, delays
Never call time.sleep in a script or event: it freezes NVDA. To do something later use
wx.CallLater(milliseconds, function, arguments); import wx. To run something on NVDA's main thread from
another thread use wx.CallAfter(function, arguments).

## Clean up when the add-on is unloaded, terminate
```python
def terminate(self):
	# stop timers, remove anything the add-on registered
	super().terminate()
```

## Sending keys to a program, simulating key presses
```python
from keyboardHandler import KeyboardInputGesture
KeyboardInputGesture.fromName("control+s").send()
```
Use this to press keys for the user, for example to give a program a shortcut it lacks.

## Clicking the mouse at a place on the screen
```python
import winUser
import mouseHandler
winUser.setCursorPos(x, y)
mouseHandler.doPrimaryClick()
```
x and y are screen pixels. obj.location gives left, top, width, height of a control; click its middle
with x = left + width // 2 and y = top + height // 2.

## Controllers, touch, pressure and moving the mouse itself are not for an add-on
An add-on VisionClaw writes cannot use a controller's buttons, touch the screen as fingers do, press with a
pen's pressure or move the mouse itself: all of these need ctypes, which the check of generated code refuses.
VisionClaw does them itself. A controller's button that should click or say something is made as a hotkey of
the program, not as an add-on. An add-on only speaks, with ui.message, about what such input changed.

## Reading and changing NVDA settings from code, config
import config. Settings are read as config.conf["section"]["key"], for example
config.conf["keyboard"]["speakTypedCharacters"]. Speech rate, pitch and volume belong to the synthesizer:
```python
import synthDriverHandler
synth = synthDriverHandler.getSynth()
synth.rate = 60
```

## Mistakes to avoid in add-ons
Always import every module you use: ui, api, tones, controlTypes. Always call nextHandler() in events.
Wrap event code in try/except, because objects can disappear at any moment. Do not use time.sleep.
Do not print(); use ui.message. Compare roles with controlTypes.Role.BUTTON, not with text.
Check that obj is not None before using it. Keep scripts fast.
