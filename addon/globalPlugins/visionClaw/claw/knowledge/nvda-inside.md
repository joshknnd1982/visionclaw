# How NVDA is built inside: commands, objects, speech and braille

## What NVDA is made of, how many commands, modules, functions
These notes were written from the source of NVDA 2026.3.1: 609 modules, about 1,800 classes, 1,570 functions
outside classes, 6,900 methods, 509 commands, 6 speech synthesizer drivers, 24 braille display drivers and 38
extension points. The names are NVDA's own. The tool audit_nvda counts and lists what the running NVDA has,
with its add-ons; find_nvda finds any of it by a description, and inspect_nvda shows what it is and holds now.

## Commands, scripts, gestures, how a key runs a command
A command is a method whose name begins with script_, on NVDA's global commands (globalCommands.commands), a
global plugin, an app module, a tree interceptor such as a web page in browse mode, or the control itself.
A key press becomes an input gesture (inputCore.InputGesture; for the keyboard
keyboardHandler.KeyboardInputGesture). inputCore.manager finds the script for the gesture, asking the focused
control first and NVDA's global commands last, and scriptHandler.executeScript(script, gesture) runs it. A
script always gets a gesture. scriptHandler.getLastScriptRepeatCount() tells a script that it was pressed
twice or three times quickly: that is how one key says the time on the first press and the date on the second.

## Commands without a description, hidden commands, how many commands
NVDA 2026.3.1 has 509 commands: 267 in globalCommands and 242 elsewhere, for Word, Excel, PowerPoint, browse
mode, the caret and more. 318 have a description and are listed in the Input Gestures dialog, which
inputCore.manager.getAllGestureMappings() gives with their keys. 191 have no description and are listed
nowhere; find_command finds those too, by their names, after the described ones.

## Objects, NVDAObject, what NVDA knows about a control
Everything NVDA reads is an NVDAObject (NVDAObjects.NVDAObject). Windows reports controls in several ways and
NVDA has a class for each: NVDAObjects.UIA for UI Automation, NVDAObjects.IAccessible for MSAA and
IAccessible2 as browsers use, NVDAObjects.JAB for Java, NVDAObjects.window for a bare window. api holds the
ones in use: api.getFocusObject(), api.getNavigatorObject(), api.getForegroundObject(), api.getMouseObject(),
api.getDesktopObject(), api.getFocusAncestors(). The tool object_info reads every fact of one of them.
controlTypes.Role and controlTypes.State are the kinds and states. textInfos gives an object's text piece by
piece. A treeInterceptor, such as a virtual buffer, stands between the user and a document.

## Functions and modules, where to look for something in NVDA
api: the objects in use and the clipboard. ui: ui.message(text) speaks and brailles a message,
ui.browseableMessage shows a text window. speech: everything spoken. braille: everything on the braille
display. config: config.conf holds every setting. eventHandler and the event_ methods: what happens when focus
moves or a value changes. core: NVDA's main loop, core.callLater. addonHandler: the add-ons. gui: NVDA's
windows and settings panels. tones.beep and nvwave.playWaveFile: sounds. extensionPoints: the places where
add-ons listen in.

## Speech, how NVDA speaks text, speech sequence, speak
What NVDA says is a speech sequence: a list of text strings and speech commands. speech.speak(sequence)
passes it through speech.extensions.filter_speechSequence, tells speech.extensions.pre_speech, applies the
symbol level and the speech dictionaries (speech.processText), and gives it to the speech manager
(speech.manager.SpeechManager). The manager queues it by priority (speech.priorities.SpeechPriority: NORMAL,
NEXT, NOW) and calls getSynth().speak(sequence) on the synthesizer driver. speech.speakMessage(text),
speech.speakText, speech.speakObject and speech.speakTextInfo all end in speech.speak.
speech.cancelSpeech() silences at once; speech.pauseSpeech(True) pauses.

## Speech synthesizer driver, TTS engine, SynthDriver, voices, how NVDA talks to a synthesizer
The driver is a class called SynthDriver, built on synthDriverHandler.SynthDriver, in a module of the
synthDrivers package. It has name and description. check() says whether it can run. speak(speechSequence),
cancel() and pause(switch) do the work. supportedSettings lists its settings: voice, variant, rate, rate boost,
pitch, inflection, volume; each is an attribute of the driver. availableVoices and availableVariants list the
choices. supportedCommands says which speech commands it understands; supportedNotifications which it reports
back. synthDriverHandler.getSynth() is the driver in use, getSynthList() the installed ones, setSynth(name)
switches. NVDA 2026.3.1 ships espeak, oneCore, sapi5, sapi4 (32 bit), mssp and silence; add-ons bring more.

## How the synthesizer reports back, index, say all, done speaking
The driver tells NVDA how far it has spoken through synthDriverHandler.synthIndexReached and that it has
finished through synthDriverHandler.synthDoneSpeaking. Say all, and functions that are called when speech
reaches a place, depend on them. A driver that reports neither cannot be followed exactly.

## Speech commands inside a speech sequence, pitch, rate, language, pauses, beeps
From speech.commands: IndexCommand marks a place the synthesizer reports back. CharacterModeCommand spells.
LangChangeCommand switches language. BreakCommand pauses. PitchCommand, RateCommand and VolumeCommand change
the voice for what follows. PhonemeCommand gives a pronunciation. EndUtteranceCommand ends an utterance.
CallbackCommand calls a function when speech gets there; BeepCommand beeps and WaveFileCommand plays a sound
at that point. A driver ignores the commands it does not list in supportedCommands.

## Listening in on speech, extension points for speech
speech.extensions has pre_speech, pre_speechQueued, speechCanceled, pre_speechCanceled, post_speechPaused and
filter_speechSequence, which may change what is spoken. synthDriverHandler has synthChanged and
pre_synthSpeak. Register with .register(function) and always unregister again.

## Braille, how NVDA shows text on a braille display, braille handler
braille.handler is the one BrailleHandler. It holds the display driver (braille.handler.display), the number
of cells (displaySize, displayDimensions), what braille follows (getTether, setTether: focus, review or
automatic), and whether braille is on (enabled). When focus or the caret moves, the handler is told
(handleGainFocus, handleCaretMove, handleReviewMove, handleUpdate). It builds regions of text
(braille.regions), translates them with the liblouis table (louisHelper.translate, tables in brailleTables),
and writes the cells with display.display(cells). braille.handler.message(text) shows a message for a while.
scrollForward, scrollBack and routeTo(position) are what the display's keys do.

## Braille display driver, BrailleDisplayDriver, cells, ports, how NVDA talks to a braille display
The driver is a class built on braille.display.driver.BrailleDisplayDriver (also reachable as
braille.BrailleDisplayDriver) in a module of the brailleDisplayDrivers package. It has name and description.
check() says whether the display can be there. numCells, numRows and numCols give its size. display(cells)
shows the dots, one number per cell. gestureMap ties its keys to NVDA commands. getPossiblePorts() lists USB,
Bluetooth and serial ports. supportsAutomaticDetection says whether bdDetect finds it by itself.
braille.display.getDisplayList() lists the installed drivers; braille.handler.setDisplayByName(name) switches.
NVDA 2026.3.1 ships 24 drivers, among them freedomScientific, hims, handyTech, brailliantB, baum, alva,
papenmeier, eurobraille, seika, hidBrailleStandard, brltty and noBraille.

## Keys on a braille display, braille input, typing braille
Keys pressed on the display arrive as braille.BrailleDisplayGesture and run commands like any key. Braille
typed on the display goes through braille.input.handler (also brailleInput.handler).

## Listening in on braille, extension points for braille
braille.extensions has pre_writeCells (the cells about to be written), displayChanged, displaySizeChanged,
filter_displaySize, filter_displayDimensions and decide_enabled.

## Never cut off speech and braille, switching synthesizer or display in code
Changing the synthesizer or the braille display can leave a blind person with neither. VisionClaw only does
it through switch_driver, which asks first and switches back unless the user confirms that it works. Code
that calls setSynth or setDisplayByName directly must not be written.
