<!-- Written from these pages, read on 2026-11-17. W3C: "Accessible Rich Internet Applications (WAI-ARIA) 1.2"
(https://www.w3.org/TR/wai-aria-1.2/), ARIA Authoring Practices Guide, "Read Me First"
(https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/), "Using ARIA", a discontinued W3C draft kept for reference
(https://www.w3.org/TR/using-aria/), "Core Accessibility API Mappings 1.2" (https://www.w3.org/TR/core-aam-1.2/).
Microsoft Learn: "Automation Element Property Identifiers"
(https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-automation-element-propids).
NVDA: the NVDA User Guide (https://download.nvaccess.org/documentation/userGuide.html), Advanced settings.
Each section is short on purpose: one section is one answer, and it is given to the user word for word by the
smallest models. Nothing may stand between this comment and the first heading but the title, or it becomes a
section. -->
# WAI-ARIA for web pages

## What WAI-ARIA is: roles, states and properties for web pages
WAI-ARIA, Accessible Rich Internet Applications, is a W3C specification that adds meaning to web content so that
assistive technology can present it correctly. It is mainly for authors who build their own widgets out of plain
elements. It adds to HTML and SVG and does not replace them: native HTML should be used where it fits. These
notes follow version 1.2.

## ARIA roles, states and properties: what each one is
A role, set with the role attribute, says what kind of thing an element is, such as button or menuitem, and does
not change as the user works. States, such as aria-checked or aria-busy, change through the user or the page.
Properties, such as aria-label or aria-valuemax, describe the element or hold a value and change less often,
though some, like aria-valuenow, change often.

## The accessibility tree and accessibility APIs: how a screen reader sees a web page
The browser turns the page into an accessibility tree, a tree of objects that represents the structure of the
user interface, and offers it through the platform's accessibility API, such as MSAA, UI Automation or AT-SPI.
ARIA changes what goes into that tree, and so what a screen reader is told. It does not change how the page
works: ARIA adds no keyboard behavior or styling.

## Kinds of ARIA roles: widgets, structure, landmarks, live regions and windows
Widget roles are controls, from simple ones like button, checkbox and slider to containers like combobox, grid,
listbox, menu, tree and tablist. Document structure roles, like article, list, table, heading and figure,
organize content. Landmark roles mark regions to move between. Live region roles mark areas that update by
themselves. The window roles are dialog and alertdialog. Abstract roles exist only for the specification and
must not be used.

## ARIA landmarks: banner, navigation, main and the other regions of a page
Landmark roles mark the regions of a page so that a screen reader user can move between them. They are banner,
complementary, contentinfo, form, main, navigation, region and search.

## ARIA button role and aria-pressed: buttons and toggle buttons
The button role is for something that does an action when clicked or pressed, and it must have an accessible
name. With aria-pressed it becomes a toggle button: true means pressed, false means not pressed, and mixed means
the things it controls do not all agree. Without aria-pressed it is not a toggle button. A button may also carry
aria-expanded and aria-haspopup when it opens something.

## ARIA checkbox role and aria-checked: checked, not checked or mixed
The checkbox role is for something that can be checked, and it must have aria-checked and a name. The value is
true, false or mixed, mixed meaning partly checked, which only three-state controls such as checkboxes support;
radio buttons, switches and radio menu items treat mixed as false. When aria-checked is not set at all, the
element cannot be checked.

## ARIA tab, tablist and tabpanel roles: tabbed pages
A tablist is a list of tab elements. Each tab is a label that chooses which panel is shown, and a tabpanel holds
the content of one tab. A tab must be inside or owned by a tablist, and its aria-selected is false unless set.
The panel should be tied to its tab, by aria-controls on the tab or aria-labelledby on the panel, and it must
have a name. A tablist is horizontal unless set otherwise.

## ARIA menu and menuitem roles: menus on a web page
A menu offers a list of choices and must contain menuitem, menuitemcheckbox or menuitemradio elements, which may
be grouped. The page's own script should move the focus among the items. A menuitem is one choice in a menu or
menubar; it must have a name, it may be disabled with aria-disabled, and with aria-haspopup it can open a
submenu. A menu is vertical unless set otherwise.

## ARIA dialog role: a window inside a web page
A dialog is a window that belongs to the main window of a web application. The author must give it a name with
aria-label or aria-labelledby, should put at least one focusable element in it, and should move the focus into a
modal dialog when it is shown. The other window role is alertdialog.

## ARIA combobox role: an input with a pop-up list
A combobox is an input that controls a pop-up, which is a listbox, tree, grid or dialog, to help set its value.
It must have aria-controls, aria-expanded and a name, and its aria-haspopup is listbox unless set. With
autocompletion the author must set aria-autocomplete. By common convention Down Arrow moves into the pop-up, and
a separate button that opens the pop-up should not be in the Tab order.

## ARIA listbox and option roles: choosing from a list
A listbox lets the user choose one or more items from a list. It contains option elements, directly or in
groups, and the page's script should manage the focus among them. It is vertical unless aria-orientation says
otherwise, it may allow several choices with aria-multiselectable, and it must have a name.

## ARIA slider role: choosing a value from a range
A slider is an input where the user chooses a value from within a range. The author must set aria-valuenow.
aria-valuemin is 0 and aria-valuemax is 100 unless set, and the slider is horizontal unless aria-orientation
says otherwise. It must have a name.

## ARIA grid role: a table you move through with the arrow keys
A grid is a composite widget of rows and cells in which some or all cells can be focused and moved between in
two directions, for example with the arrow keys. It must contain row elements, directly or in row groups, may be
multi-selectable or read-only, and must have a name. A cell that holds one simple widget, such as a checkbox or
button, may let that widget take the focus.

## aria-label and aria-labelledby: giving an element its name
aria-label gives an element its accessible name as a string, for when no visible text fits. aria-labelledby
takes the name from other elements on the page, by their ids, and is preferred when the label text is already on
the page. When both are present, browsers use aria-labelledby. The name becomes accName in MSAA and Name in UI
Automation, and aria-labelledby also becomes a labelled-by relation in IAccessible2 and LabeledBy in UI
Automation.

## aria-describedby: a longer description of an element
aria-describedby points, by id, to one or more elements that describe the element. It is for information longer
than a label. NVDA's user guide also has a setting, "Report aria-description always", for descriptions that come
from the aria-description attribute.

## aria-expanded: whether something is open or closed
aria-expanded says whether a grouping element that this element owns or controls is expanded or collapsed: true,
false, or not set. It is used on focusable elements that open and close content, such as a tree item or a
button. If the content is elsewhere on the page, aria-controls points to it. A change shows in UI Automation as
a change of ExpandCollapseState, and in MSAA as a state change.

## aria-hidden: hiding an element from screen readers
aria-hidden="true" removes an element and everything inside it from the accessibility API, so screen readers do
not see it. It must be used with care: if visible content is hidden this way, the same meaning and function must
be available another way. It must never be put on a focusable element or on an ancestor of a visible control, or
users may land on something that seems to do nothing.

## aria-disabled: a control that is shown but cannot be used
aria-disabled="true" says that the element and its focusable descendants are disabled: they can be perceived but
not edited or operated. The author should also make it look disabled. ARIA 1.2 deprecates it as a global
attribute and will limit it to certain roles. A change shows in UI Automation as a change of IsEnabled.

## ARIA live regions: aria-live polite and assertive
A live region is a part of a page that updates by itself and that assistive technology should announce.
aria-live says how: off, the default, presents changes only when the user is in the region; polite presents them
at the next good moment; assertive presents them at once and may clear speech already waiting, so authors should
use it only when interrupting is needed. In UI Automation this becomes LiveSetting Polite or Assertive.

## ARIA alert and status roles: important and advisory messages
The alert role is a live region with important, usually urgent information; it is assertive and atomic unless
set, and the focus need not move to it. The status role is a live region with advisory information not important
enough for an alert; it is polite and atomic, and should not take the focus when it changes. The other live
region roles are log, marquee and timer.

## The first rule of ARIA: use native HTML first
The W3C note "Using ARIA", now a discontinued draft kept for reference, says: if a native HTML element or
attribute already has the meaning and behavior needed, use it instead of adding ARIA to another element. The
exceptions are a native feature that is missing or poorly supported, a design that cannot use it, or HTML
lacking it. Its other rules: do not change native meaning unless needed, make every ARIA control work by
keyboard, and never hide focusable elements.

## No ARIA is better than bad ARIA: a role is a promise
The ARIA Authoring Practices Guide warns that wrong ARIA misleads screen reader users. A role is a promise:
giving an element the button role promises that the page's script makes it behave like a button, including from
the keyboard, because ARIA adds no keyboard behavior. ARIA can also hide meaning: aria-label replaces a link's
visible text as its name, and role="log" on a table stops it being seen as a table.

## How browsers pass ARIA to screen readers on Windows: MSAA, IAccessible2 and UI Automation
The W3C's Core Accessibility API Mappings tell browsers how to expose ARIA through each platform's API; on
Windows that is MSAA with IAccessible2 1.3, and UI Automation. For example, a button becomes
ROLE_SYSTEM_PUSHBUTTON in MSAA and a Button in UI Automation, a checkbox ROLE_SYSTEM_CHECKBUTTON and CheckBox, a
dialog ROLE_SYSTEM_DIALOG and a Pane, and an alert a Group with LiveSetting Assertive in UI Automation.

## UI Automation AriaRole and AriaProperties: the ARIA values themselves
UI Automation has two properties for web content. AriaRole is a string with the element's ARIA role.
AriaProperties is a string of ARIA states and properties as name and value pairs separated by semicolons, such
as checked=true;disabled=false. A browser may also put a translated word for the ARIA role into
LocalizedControlType.

## How NVDA uses ARIA
NVDA's user guide has a "Report live regions" setting, enabled by default, which also shows changes of live
regions in braille; turning it off goes back to reporting them in speech only, as NVDA 2023.1 and earlier did.
Its Annotations settings add experimental support for ARIA annotations: NVDA+D reports a summary of the details
at the caret, and one option reports aria-description always.
