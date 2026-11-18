<!-- Written from these pages, read on 2026-11-17. Microsoft Learn: "IAccessible interface"
(https://learn.microsoft.com/en-us/windows/win32/api/oleacc/nn-oleacc-iaccessible), "How Child IDs Are Used in
Parameters" (https://learn.microsoft.com/en-us/windows/win32/winauto/how-child-ids-are-used-in-parameters), "UI
Automation and Active Accessibility" (https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-msaa), "Microsoft
Active Accessibility and UI Automation Compared"
(https://learn.microsoft.com/en-us/windows/win32/winauto/microsoft-active-accessibility-and-ui-automation-compared),
"Event Constants" (https://learn.microsoft.com/en-us/windows/win32/winauto/event-constants), "What Are WinEvents?"
(https://learn.microsoft.com/en-us/windows/win32/winauto/what-are-winevents), "WinEvents and Active Accessibility"
(https://learn.microsoft.com/en-us/windows/win32/winauto/winevents-overview), "Client/Server Communication"
(https://learn.microsoft.com/en-us/windows/win32/winauto/client-server-communication), "SetWinEventHook"
(https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook), "IAccessible Proxies"
(https://learn.microsoft.com/en-us/windows/win32/winauto/iaccessible-proxies), "Architecture and Interoperability"
(https://learn.microsoft.com/en-us/windows/win32/winauto/architecture-and-interoperability), "Accessing Microsoft
Active Accessibility Servers" (https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-accessingmsaaservers),
"UI Automation and Microsoft Active Accessibility" for .NET
(https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-and-microsoft-active-accessibility),
"Control.AccessibleName" and "Control.AccessibleDescription" (learn.microsoft.com, System.Windows.Forms).
IAccessible2: the README of https://github.com/LinuxA11y/IAccessible2, and the IAccessible2 1.3 documentation at
https://accessibility.linuxfoundation.org/a11yspecs/ia2/docs/html/ (index, _general_info.html,
interface_i_accessible2.html). W3C Core Accessibility API Mappings 1.2 (https://www.w3.org/TR/core-aam-1.2/).
Firefox Source Docs, "Architecture" (https://firefox-source-docs.mozilla.org/accessible/Architecture.html).
NVDA: the NVDA User Guide (https://download.nvaccess.org/documentation/userGuide.html) and the NVDA Developer Guide
(https://download.nvaccess.org/documentation/developerGuide.html).
Each section is short on purpose: one section is one answer, and it is given to the user word for word by the
smallest models. Nothing may stand between this comment and the first heading but the title, or it becomes a
section. -->
# Microsoft Active Accessibility and IAccessible2

## What Microsoft Active Accessibility is: MSAA, the older Windows accessibility API
Microsoft Active Accessibility, or MSAA, is the accessibility API that Microsoft introduced with Windows 95. A
program, called the server, describes each piece of its window as an accessible object through the IAccessible
COM interface, and a client such as a screen reader reads it. Microsoft now calls MSAA the legacy API and
recommends UI Automation for new programs and controls.

## IAccessible: the interface every MSAA object has
IAccessible is the COM interface through which an MSAA object answers a client. Its properties give the name,
role, state, value, description, help, keyboard shortcut, default action, parent, children, focus and selection,
and its methods do the default action, select or focus, give the location, navigate, and find what is at a point
on screen. Clients find an object with AccessibleObjectFromWindow, AccessibleObjectFromPoint or
AccessibleObjectFromEvent.

## MSAA accName: the name of an object
accName is the name of the object, the text a screen reader speaks for it, and every object supports it. Setting
a name from outside with put_accName is no longer supported. In Windows Forms a program's author sets the name
with the AccessibleName property, a short label such as the text of a button or the label beside an edit box. In
UI Automation the matching property is Name.

## MSAA accRole: what kind of object it is
accRole gives the object's role, such as ROLE_SYSTEM_PUSHBUTTON, ROLE_SYSTEM_CHECKBUTTON,
ROLE_SYSTEM_RADIOBUTTON, ROLE_SYSTEM_COMBOBOX, ROLE_SYSTEM_TEXT for an edit box, ROLE_SYSTEM_LIST,
ROLE_SYSTEM_LISTITEM, ROLE_SYSTEM_MENUITEM, ROLE_SYSTEM_SLIDER or ROLE_SYSTEM_PAGETAB. Every object supports it.
The role is the main clue to what an object can do; in UI Automation it matches the ControlType.

## MSAA accState: checked, focused, unavailable and other states
accState gives the current state as flags, such as STATE_SYSTEM_CHECKED, STATE_SYSTEM_FOCUSED,
STATE_SYSTEM_FOCUSABLE, STATE_SYSTEM_EXPANDED, STATE_SYSTEM_COLLAPSED, STATE_SYSTEM_SELECTED,
STATE_SYSTEM_UNAVAILABLE for a disabled control, STATE_SYSTEM_INVISIBLE, STATE_SYSTEM_OFFSCREEN,
STATE_SYSTEM_PROTECTED for a password, and STATE_SYSTEM_READONLY. Every object supports it. A change raises
EVENT_OBJECT_STATECHANGE.

## MSAA accValue: the value of an edit box, slider or progress bar
accValue is the object's value as a string, for objects that have one, such as an edit box, slider, scroll bar,
progress bar or up-down control. put_accValue sets it where that is allowed. A change raises
EVENT_OBJECT_VALUECHANGE. In UI Automation the value comes from the Value or RangeValue pattern, and range
values are given from 0 to 100 to match MSAA.

## MSAA accDescription and accHelp: extra text about an object
accDescription is a string describing the object's visual appearance; not every object has one. Microsoft notes
it never had a clear definition, so programs put different things in it, and UI Automation has no match for it.
accHelp is the object's help text, which matches HelpText in UI Automation. In Windows Forms the description is
set with AccessibleDescription, for example for a button that shows only a picture.

## MSAA accDefaultAction and accDoDefaultAction: doing a control's action from code
accDefaultAction is a string that says what the object's default action is, and accDoDefaultAction carries that
action out. Not every object has a default action. A change of the default action raises
EVENT_OBJECT_DEFACTIONCHANGE. UI Automation clients reach these through the LegacyIAccessible pattern; UI
Automation's own way of pressing a control is the Invoke pattern.

## MSAA accChildCount, accChild and child ids: the children of an object
accChildCount gives the number of children and accChild returns one. A child is either a full accessible object
with its own IAccessible, or a simple element without an interface of its own, reached through its parent and a
number called the child id. The constant CHILDID_SELF, which is 0, means the object itself. When accChild fails
for a child id, that child is a simple element.

## WinEvents: how MSAA tells a screen reader that something changed
WinEvents are Windows' way of announcing changes. A program calls NotifyWinEvent after something has happened,
and Windows itself sends many events for standard controls. A client registers with SetWinEventHook for the
events it wants and then fetches the object with AccessibleObjectFromEvent. A hook runs either in the client's
own process, out of context, with events queued but in order, or is loaded into the program, in context.

## EVENT_OBJECT_FOCUS: an object received the keyboard focus
EVENT_OBJECT_FOCUS, value 0x8005, is sent when an object receives the keyboard focus. Windows sends it for list
views, menu bars, pop-up menus, tab controls, tree views, the window switcher and windows, and programs send it
for their own objects. In UI Automation the focus changed event takes its place.

## EVENT_OBJECT_NAMECHANGE and EVENT_OBJECT_VALUECHANGE: a name or value changed
EVENT_OBJECT_NAMECHANGE, 0x800C, means an object's name changed; Windows sends it for check boxes, buttons,
radio buttons, list views, status bars, tree views, windows and the cursor. EVENT_OBJECT_VALUECHANGE, 0x800E,
means the value changed; Windows sends it for edit boxes, headers, hot key fields, progress bars, sliders,
up-down controls and scroll bars. Programs send both for their own objects.

## EVENT_SYSTEM_FOREGROUND: another window came to the front
EVENT_SYSTEM_FOREGROUND, value 0x0003, means the foreground window changed, even to another window of the same
thread. Only Windows sends it, never a program. It carries the window's handle, OBJID_WINDOW and CHILDID_SELF.
In UI Automation the focus changed event takes its place.

## Other WinEvents: objects shown, hidden, created, destroyed, moved and live regions
EVENT_OBJECT_CREATE, EVENT_OBJECT_DESTROY, EVENT_OBJECT_SHOW and EVENT_OBJECT_HIDE report objects that appear or
go. EVENT_OBJECT_STATECHANGE reports a changed state, such as a button pressed or a control enabled or disabled.
EVENT_OBJECT_LOCATIONCHANGE reports a move or resize. EVENT_OBJECT_LIVEREGIONCHANGED, 0x8019, reports a change
in a live region, an area that changes often or by itself.

## MSAA proxies: standard Windows controls without extra work
For standard controls, menus and common controls, Windows itself makes IAccessible objects in Oleacc.dll, so
these work without effort from the program. When a client asks for an object, Windows sends the window the
WM_GETOBJECT message. If the window answers zero, it has no MSAA of its own, and Oleacc.dll makes a proxy object
that reports what it can on the window's behalf.

## The bridge between MSAA and UI Automation
UI Automation clients read programs that have only MSAA through the Microsoft Active Accessibility to UI
Automation proxy, which also gives them the LegacyIAccessible pattern. MSAA clients read UI Automation programs,
such as WPF ones, through the UI Automation to MSAA bridge, with less access. Because MSAA exposes less, the two
are not fully compatible. IAccessibleEx lets an older MSAA program add UI Automation properties and patterns.

## The limits of MSAA
MSAA has one interface with a small fixed set of properties. Its roles date from Windows 95 and cannot be
combined or extended, and it has no model of text, which makes rich documents and web pages hard. Some items
appear twice in its tree, and it cannot be extended without breaking the interface. Microsoft also says it is
slow for clients in another process, which pushed screen readers to load their code into programs.

## What IAccessible2 is: the extension of MSAA for browsers and documents
IAccessible2 is an accessibility API for Windows that adds to MSAA and fills its gaps, especially for rich
documents, office suites, spreadsheets and web browsers. It began with the need for an accessible OpenDocument
office suite for the Commonwealth of Massachusetts. Its definition is kept in the LinuxA11y/IAccessible2
repository on GitHub, and its documentation is at accessibility.linuxfoundation.org. A program must still
implement MSAA's IAccessible.

## IAccessible2 interfaces: text, tables, hyperlinks, actions and more
Besides the main IAccessible2 interface, it defines IAccessibleText for reading text and IAccessibleEditableText
for the clipboard, IAccessibleHypertext and IAccessibleHyperlink for links, IAccessibleTable2 and
IAccessibleTableCell for tables, IAccessibleAction for actions, IAccessibleValue for a number,
IAccessibleComponent for objects on screen, IAccessibleImage, IAccessibleDocument, IAccessibleRelation, and
IAccessibleApplication for the program's name and version.

## IAccessible2 relations, attributes, unique ids and extra roles
The IAccessible2 interface adds relations between objects, such as which object labels another; object
attributes, like a cell's formula; a uniqueID that stays the same for the object's life and is unique in its
window; the position in a group, used for tree items, list items and radio buttons; roles and states beyond
MSAA's; the window handle; and scrollTo, which brings an object into view. A client reaches it from IAccessible
with QueryService, not with QueryInterface.

## Which programs use IAccessible2: Chromium browsers and Firefox
NVDA's user guide says NVDA uses IAccessible2 in Chromium browsers such as Chrome and Edge when it can inject
into the browser's process, and that UI Automation there may not yet give the same access. Firefox's own
architecture notes list, for Windows, the node types MsaaAccessible, ia2Accessible and uiaRawElmProvider. The
W3C mapping rules tell browsers how to expose web pages through MSAA with IAccessible2 1.3.

## How NVDA uses MSAA and IAccessible2
NVDA's user guide lists Microsoft Active Accessibility and IAccessible2 among the interfaces NVDA supports. Its
developer guide says a control may be an MSAA object, an IAccessible2 object, a UI Automation element or a
widget of a Java program, and that an add-on changing how an MSAA control behaves inherits from
NVDAObjects.IAccessible.IAccessible. In Chromium browsers NVDA uses UI Automation only when it cannot inject to
use IAccessible2, unless set otherwise.
