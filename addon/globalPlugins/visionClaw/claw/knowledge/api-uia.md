<!-- Written from these pages, read on 2026-11-17. Microsoft Learn: "UI Automation Overview"
(https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview), "UI Automation Tree Overview"
(https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-treeoverview), "UI Automation Control Patterns Overview"
(https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview), "UI Automation Control Types
Overview" (https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controltypesoverview), "Automation Element
Property Identifiers" (https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-automation-element-propids),
"UI Automation Events Overview" (https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-eventsoverview and
https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-events-overview), "Event Identifiers"
(https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-event-ids), the control pattern pages Invoke, Value,
RangeValue, Toggle, ExpandCollapse, SelectionItem, Scroll, ScrollItem, Window, LegacyIAccessible
(https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-implementing<name>), "About the Text and TextRange
Control Patterns" (https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-about-text-and-textrange-patterns),
"UI Automation and Active Accessibility" (https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-msaa),
"Architecture and Interoperability" (https://learn.microsoft.com/en-us/windows/win32/winauto/architecture-and-interoperability),
"UiaRaiseNotificationEvent", "NotificationKind", "AutomationNotificationProcessing" and "LiveSetting"
(learn.microsoft.com API reference), "WPF: Setting the accessible name on a button" and "on a custom control"
(https://learn.microsoft.com/en-us/accessibility-tools-docs/items/wpf/button_name and customcontrol_name), "WinForms:
Setting the accessible name on a control" (https://learn.microsoft.com/en-us/accessibility-tools-docs/items/winforms/control_name),
"Control.AccessibleName Property" (https://learn.microsoft.com/en-us/dotnet/api/system.windows.forms.control.accessiblename).
NVDA: the NVDA User Guide (https://download.nvaccess.org/documentation/userGuide.html), Advanced settings.
Each section is short on purpose: one section is one answer, and it is given to the user word for word by the
smallest models. Nothing may stand between this comment and the first heading but the title, or it becomes a
section. -->
# Microsoft UI Automation

## What UI Automation is: Microsoft's accessibility API for Windows
UI Automation, often written UIA, is Microsoft's accessibility framework for Windows. It lets screen readers and
other assistive technology, and also automated test scripts, learn about the controls on the desktop and work
them without the mouse or keyboard. Microsoft calls it the newer model and Microsoft Active Accessibility the
legacy one. Since Windows 7 it has a COM interface for programs written in C and C++.

## UI Automation providers and clients: who gives the information and who reads it
A provider is the part of a program or control that tells UI Automation about its controls and carries out
commands. A client is a program that asks, such as a screen reader. Between them sits the UI Automation core,
UIAutomationCore.dll, which carries the requests between the processes. Providers implement the interfaces in
UIAutomationCore.h, and clients use the interfaces in UIAutomationClient.h.

## The UI Automation tree: the desktop, windows and the controls inside them
UI Automation shows everything on screen as a tree. The root is the desktop, its children are the program
windows, and inside them are menus, buttons, toolbars, list boxes and their items. The tree is built only as far
as a client asks for it, and it changes as controls appear and disappear. Microsoft's Inspect tool, part of the
Windows SDK, shows the tree.

## UI Automation raw view, control view and content view
The tree can be seen in three standard views. The raw view is everything, close to how the program is built. The
control view keeps only elements whose IsControlElement is true: things that inform the user or can be used, and
containers such as toolbars and menus, but not panels used only for layout. The content view keeps only those
that are also content elements, the information itself, which matters most to a screen reader.

## UI Automation elements: one object for each piece of the screen
Every piece of a window, from the whole window down to one list item, is an automation element, reached through
the IUIAutomationElement interface. Each element has properties, such as its name and control type, and may
support control patterns, which say what can be done with it. Elements are compared by their RuntimeId, which is
unique on the desktop while the element exists but may be reused later.

## UI Automation control types: button, check box, edit, list and the others
The ControlType property says what kind of control an element is, such as Button, CheckBox, ComboBox, Edit,
Hyperlink, List, ListItem, Menu, MenuItem, ProgressBar, RadioButton, Slider, Tab, TabItem, Table, Text, Tree,
TreeItem or Window. An element has exactly one control type, and each type comes with patterns and properties it
must support. A control that fits none is given the Custom type.

## UI Automation Name property: what a control is called
Name is the text a screen reader speaks for a control. Microsoft says it should match the label on screen, such
as Browse for a button labelled Browse, without the ampersand of the access key and without the type, so not
"Browse button". A control shown only as a picture should get a short name saying what it does: the Start button
is named Start, not a description of the logo. Name need not be unique.

## UI Automation AutomationId: a fixed identifier for a control
AutomationId is a string that identifies an element. When present it should be the same in every language of the
program and unique among its siblings, though not across the desktop. It is mainly for test scripts. It is
optional, and Microsoft warns that it may change between versions of a program, so a client should assume
nothing about its value.

## UI Automation LocalizedControlType: the kind of control in words
LocalizedControlType is the control type in words, in lowercase and in the program's language, such as "button".
The framework fills it in for the standard types. A control of the Custom type must give its own words, for
example "color picker". Screen readers often speak the name followed by this word, which is why the name must
not repeat the type.

## UI Automation ClassName and FrameworkId: which toolkit made a control
ClassName is the class name the control's developer gave it. Its form depends on the provider and is not
standard, but it can confirm that a client is looking at the expected control. FrameworkId names the user
interface framework behind the element, with values such as Win32, WinForm and DirectUI, so that a client can
treat elements of different frameworks differently.

## UI Automation IsKeyboardFocusable, HasKeyboardFocus and IsEnabled
IsKeyboardFocusable is true when the element can take the keyboard focus, and HasKeyboardFocus is true when it
has the focus now. IsEnabled says whether the control can be used at all; when a parent is disabled, its
children are taken to be disabled too.

## UI Automation HelpText property: hints and placeholder text
HelpText is a help string for a control. Microsoft gives placeholder text in an edit box, such as "Type text
here for search", as a good use of it, and says such text is not good enough to serve as the control's Name.
When pressing a control has side effects, Microsoft says to describe them in HelpText. It should be in the
program's language.

## UI Automation BoundingRectangle and IsOffscreen: where a control is and whether it is shown
BoundingRectangle is the rectangle around the element, in physical screen pixels; it may include points that
cannot be clicked, and it is empty when the item shows nothing. IsOffscreen is true when the element is scrolled
out of view or collapsed away, as in a closed menu or tree or a minimized window. Another window covering it
does not change IsOffscreen.

## UI Automation control patterns: what can be done with a control
A control pattern is a set of properties, methods and events for one ability of a control, such as being
pressed, toggled, expanded or scrolled. A client asks an element which patterns it supports and then uses them.
Patterns and control types are not one to one: a combo box supports both ExpandCollapse and Selection, and some
patterns come and go, like Scroll in an edit box that scrolls only when it is full.

## UI Automation Invoke pattern: pressing a button from code
The Invoke pattern is for controls that do one action and keep no state, such as buttons, toolbar buttons and
links. Its one method, Invoke, does what a click or Enter would do, and it returns at once without waiting,
which matters when it opens a modal dialog. Controls that keep a state, such as check boxes and radio buttons,
use Toggle or selection instead. An invoked element may vanish from the tree at once.

## UI Automation Value pattern: reading and setting text or a value
The Value pattern is for controls whose value is a string and not a point in a range, such as a date picker or
an edit box whose content can be changed. It has the Value and IsReadOnly properties and the SetValue method. It
does not give formatting or parts of the text; that is the Text pattern. Before SetValue is used, the control
must be enabled and not read-only.

## UI Automation RangeValue pattern: sliders, spin boxes and progress bars
RangeValue is for controls set to a number within a range, such as a slider, a spin box of years or months, or a
progress bar. It gives Value, Minimum, Maximum, SmallChange, LargeChange and IsReadOnly, and its SetValue method
sets the number directly. The scroll bars of a container use RangeValue, not Scroll.

## UI Automation Toggle pattern: check boxes and switches that stay on or off
Toggle is for controls that cycle through states and keep one, such as check boxes and checkable menu items.
ToggleState is On, Off or, where supported, Indeterminate, and the Toggle method moves to the next state in that
order. There is no method to set a state directly. A radio button does not use Toggle, because it cannot cycle
through its states.

## UI Automation ExpandCollapse pattern: opening and closing menus, trees and combo boxes
ExpandCollapse is for controls that open to show more and close to hide it, such as menu items, tree items and
combo boxes. ExpandCollapseState is Collapsed, Expanded, PartiallyExpanded or LeafNode, which means there is
nothing to open. The Expand and Collapse methods open and close it. In a combo box the combo box itself has this
pattern, not its parts; in a menu or a tree the items have it, not the parent.

## UI Automation SelectionItem pattern: choosing an item in a list
SelectionItem is for items that can be chosen inside a container, such as list items and radio buttons.
IsSelected says whether the item is chosen, Select chooses it alone, AddToSelection and RemoveFromSelection
change a multiple choice, and SelectionContainer gives the container. Events tell when an item is selected, or
added to or removed from the selection.

## UI Automation Selection pattern: list boxes and combo boxes that hold a choice
The Selection pattern is for containers whose items can be selected, such as list boxes and combo boxes. It
tells which items are selected and, through CanSelectMultiple, whether more than one may be. Its items support
the SelectionItem pattern.

## UI Automation Scroll and ScrollItem patterns: scrolling a list or bringing an item into view
Scroll is for a container that can scroll its contents, with or without scroll bars. It gives the horizontal and
vertical position as a percentage from 0 to 100, how much is visible, whether each direction can scroll, and the
methods Scroll and SetScrollPercent; a direction that cannot scroll reports -1. ScrollItem is for an item
inside, and its method ScrollIntoView brings the item into view.

## UI Automation Text pattern: reading documents and edit boxes
The Text pattern gives read-only access to the text of edit boxes and documents through text ranges: the whole
text, the selection, the visible part, and attributes such as font name and color. A client can move through it
by character, word, line or paragraph. Edit and Document controls must support it. It does not change text; that
is done with the Value pattern, by typing, or with the TextEdit pattern.

## UI Automation Grid and Table patterns: rows, columns and cells
Grid is for controls laid out in rows and columns that can report the number of rows and columns and fetch a
cell, such as the large icon view of Windows Explorer or a simple table in Word. Each cell supports GridItem.
Table is for a grid that also has header information, and its items support TableItem. Spreadsheet and
SpreadsheetItem add to these for spreadsheet cells.

## UI Automation Window pattern: windows and dialogs
The Window pattern is for top-level program windows, child windows of a multiple-document program, modal dialogs
and balloon help. It says whether a window is modal or topmost, whether it can be minimized or maximized, and
its visual state, and it can close the window or change that state. Window opened and window closed events go
with it. Tooltips and the drop-downs of menus and combo boxes normally lack it.

## UI Automation LegacyIAccessible pattern: the older MSAA information
LegacyIAccessible lets a UI Automation client read the Microsoft Active Accessibility facts of a control: name,
role, state, value, description, help, keyboard shortcut and default action, and use DoDefaultAction, Select and
SetValue. No program implements it itself. UI Automation supplies it for controls that have Microsoft Active
Accessibility of their own, and it is not available for controls built on UI Automation.

## UI Automation events: how a screen reader learns that something changed
Programs raise events when something happens, and clients such as screen readers register for the events they
want. The kinds are property changes, element actions such as a button being invoked, structure changes,
desktop-wide changes such as the focus moving or a window closing, and notifications. Unlike the older WinEvents
they are not broadcast, and each event carries the element that raised it.

## UI Automation focus changed event: following the keyboard focus
The focus changed event, UIA_AutomationFocusChangedEventId, is raised when the focus moves from one element to
another. Microsoft's .NET pages note that it is raised by the UI Automation system itself, not by providers. It
stands for the older WinEvents EVENT_OBJECT_FOCUS and EVENT_SYSTEM_FOREGROUND.

## UI Automation property changed event: a name, value or state changed
A property changed event is raised when a property of an element or of one of its patterns changes, for example
ToggleState when a check box is checked or unchecked, or a Name or Value. A client registers for the properties
it cares about. Microsoft notes that some of these events can arrive although nothing really changed, so a
client may need to check before acting.

## UI Automation structure changed event: controls added or removed
The structure changed event, UIA_StructureChangedEventId, is raised when the tree changes because items become
visible, are hidden or are removed. It stands for the older WinEvents for objects that are created, destroyed,
shown, hidden or moved to another parent.

## UI Automation notification event: a program asks for something to be announced
In an NVDA add-on it is event_UIA_notification(self, obj, nextHandler, displayString=None, **kwargs). The text
to say is displayString, not obj.name. Call nextHandler() at its end.
Since Windows 10 version 1709 a program can call UiaRaiseNotificationEvent to send a notification with a text.
NotificationKind says what happened: ItemAdded, ItemRemoved, ActionCompleted, ActionAborted or Other.
NotificationProcessing says what to do with several: ImportantAll, ImportantMostRecent, All, MostRecent, or
CurrentThenMostRecent, which lets the current one finish and then keeps only the newest.

## UI Automation LiveRegionChanged event and LiveSetting: announcing changes away from the focus
A live region is an element whose content changes and should be announced although it does not have the focus.
When its content changes the program raises UIA_LiveRegionChangedEventId, available since Windows 8. Its
LiveSetting property says how to tell the user: Off sends nothing, Polite does not interrupt the user, and
Assertive interrupts the user.

## Fixing a missing name in WPF or XAML: AutomationProperties.Name
In WPF many controls take their name from their Content or Text, but lists, combo boxes, data grids, progress
bars, images and custom controls often have none. Microsoft's advice to the program's author is to point the
control at its visible label with AutomationProperties.LabeledBy, referring to a TextBlock, or, when there is no
label, to set AutomationProperties.Name to a short translated text. The name must not contain the type of
control.

## Fixing a missing name in Windows Forms: AccessibleName
In Windows Forms many controls use their Text as the name, but a ComboBox, ListBox, ListView, PictureBox,
ProgressBar, TabControl, TextBox or TreeView needs more. If a Label describes the control, the program's author
gives the control the TabIndex right after the label's, and the label's text becomes the name. Otherwise the
author sets AccessibleName to a translated text. AccessibleDescription and AccessibleRole can be set too.

## UI Automation and Microsoft Active Accessibility working together
UI Automation has proxies so that its clients can read standard Win32 controls and programs that support only
Microsoft Active Accessibility; the Microsoft Active Accessibility proxy is the last fallback for any window. In
the other direction a bridge lets older Microsoft Active Accessibility clients read UI Automation programs.
Because the older model exposes less, the two are not fully compatible.

## How NVDA uses UI Automation
NVDA's user guide lists UI Automation among the accessibility interfaces NVDA supports. Its Advanced settings
choose whether UI Automation is used for Microsoft Word documents and, as an experiment, for Excel spreadsheets;
whether it is used in the Windows Console, where Automatic uses it from Windows 11 22H2 on; and when it is used
in Microsoft Edge and other Chromium browsers, where it may not yet give the same access as IAccessible2.

## NVDA's setting for UI Automation events: Selective or Global
In NVDA's Advanced settings, "Registration for UI Automation events and property changes" is Automatic by
default, which means Selective on Windows 11 22H2 and later and Global before. Selective registers for most
events only at the focus, which is faster, though on older Windows the focus may be lost in some controls such
as Task Manager and the emoji panel. Global is more reliable but much slower, especially in Visual Studio.
