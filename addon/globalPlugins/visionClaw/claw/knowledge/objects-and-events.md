# NVDA objects and events

## Getting the focused control, the navigator object, the window
import api. api.getFocusObject() is the control with the keyboard focus. api.getNavigatorObject() is where
object navigation is. api.getForegroundObject() is the window in front, and its name is the window's title:
api.getForegroundObject().name. api.getDesktopObject() is the desktop. api.copyToClip("text") copies text to the
clipboard.

## Properties of a control, object attributes
obj.name is its label. obj.role is its kind, like controlTypes.Role.BUTTON. obj.states is a set, like
controlTypes.State.CHECKED. obj.value is its value, such as a slider's position or an edit field's text.
obj.description is extra text. obj.location has left, top, width, height in screen pixels.
obj.windowClassName and obj.windowControlID identify the control inside its program.
obj.appModule.appName is the program's name, like "notepad". Any of these can be None.

## Moving between controls, parent, children, next, previous
obj.parent is the containing control. obj.children is a list of the controls inside it.
obj.firstChild, obj.lastChild, obj.next and obj.previous move around. Loop with a limit, because trees
can be very large:
```python
child = obj.firstChild
count = 0
while child and count < 50:
	count += 1
	child = child.next
```

## Roles and states, controlTypes
import controlTypes. Common roles: Role.BUTTON, Role.EDITABLETEXT, Role.CHECKBOX, Role.RADIOBUTTON,
Role.COMBOBOX, Role.LIST, Role.LISTITEM, Role.MENUITEM, Role.LINK, Role.GRAPHIC, Role.WINDOW, Role.PANE,
Role.DIALOG, Role.TAB, Role.SLIDER, Role.STATICTEXT, Role.UNKNOWN. Common states: State.CHECKED,
State.SELECTED, State.FOCUSED, State.UNAVAILABLE, State.EXPANDED, State.COLLAPSED, State.PRESSED.
obj.role.displayString is the role's name in the user's language.

## Events, reacting when focus moves
An event is a method of the plugin. It gets the object and nextHandler, and must call nextHandler() so
NVDA and other add-ons still handle the event:
```python
def event_gainFocus(self, obj, nextHandler):
	try:
		if obj.role == controlTypes.Role.BUTTON and not obj.name:
			ui.message("unnamed button")
	except Exception:
		pass
	nextHandler()
```

## Other events: name change, value change, window in front, typing
event_nameChange(self, obj, nextHandler) runs when a control's label changes.
event_valueChange(self, obj, nextHandler) runs when its value changes, like a progress bar.
event_foreground(self, obj, nextHandler) runs when a new window comes to the front.
event_becomeNavigatorObject(self, obj, nextHandler) runs when object navigation moves.
event_typedCharacter(self, obj, nextHandler, ch) runs for each typed character.
event_stateChange(self, obj, nextHandler) runs when a state like checked changes.
event_UIA_notification(self, obj, nextHandler, displayString=None, **kwargs) runs when a program sends a UI
Automation notification; the text to say is displayString.

## Reading the status bar of the window in front
api.getStatusBar() is the status bar of the window in front, or None when it has none. api.getStatusBarText(bar)
is all of its text: its name and the names and values of its parts. A program often shows amounts, line
numbers and progress there.

## Giving a control a better name, overlay classes, relabelling
To change what NVDA says for some controls, give them your own class:
```python
from NVDAObjects import NVDAObject

class NamedButton(NVDAObject):
	def _get_name(self):
		return "Play"

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if obj.appModule.appName == "player" and obj.windowControlID == 1001:
			clsList.insert(0, NamedButton)
```
Pick the controls by appName together with windowControlID, windowClassName or role.

## Announcing when something on the screen changes, live regions, progress
Remember the last value and speak only when it changed, so NVDA does not repeat itself:
```python
def event_valueChange(self, obj, nextHandler):
	try:
		if obj.appModule.appName == "installer" and obj.value != getattr(self, "_last", None):
			self._last = obj.value
			ui.message(str(obj.value))
	except Exception:
		pass
	nextHandler()
```

## Reading the text of a control, text info
```python
import textInfos
info = obj.makeTextInfo(textInfos.POSITION_ALL)
text = info.text
```
POSITION_CARET is the caret, POSITION_SELECTION the selection. Not every control has text; wrap in
try/except (NotImplementedError, RuntimeError).
