<!-- Written from these pages, read on 2026-11-17. Oracle: "Java Access Bridge Overview" for Java SE 21
(https://docs.oracle.com/en/java/javase/21/access/java-access-bridge-overview.html), "Enabling and Testing Java
Access Bridge" for Java SE 21 (https://docs.oracle.com/en/java/javase/21/access/enabling-and-testing-java-access-bridge.html),
"Java Accessibility Overview" for Java SE 21
(https://docs.oracle.com/en/java/javase/21/access/java-accessibility-overview.html), "Enabling and Testing Java
Access Bridge" for Java SE 8 (https://docs.oracle.com/javase/8/docs/technotes/guides/access/enable_and_test.html),
"Accessibility Guide" for Java SE 8 (https://docs.oracle.com/javase/8/docs/technotes/guides/access/index.html).
NVDA: the NVDA User Guide (https://download.nvaccess.org/documentation/userGuide.html), the NVDA Developer Guide
(https://download.nvaccess.org/documentation/developerGuide.html), NVDA's source files source/JABHandler.py and
source/NVDAState.py (https://github.com/nvaccess/nvda). Other toolkits: Qt, "Accessibility"
(https://doc.qt.io/qt-6/accessible.html) and "Accessibility for QWidget Applications"
(https://doc.qt.io/qt-6/accessible-qwidget.html); Electron, "Accessibility"
(https://www.electronjs.org/docs/latest/tutorial/accessibility); Microsoft, "Xbox Accessibility Guideline 106: Screen
narration" (https://learn.microsoft.com/en-us/xbox/accessibility/xbox-accessibility-guidelines/106).
Each section is short on purpose: one section is one answer, and it is given to the user word for word by the
smallest models. Nothing may stand between this comment and the first heading but the title, or it becomes a
section. -->
# The Java Access Bridge and other toolkits

## What the Java Access Bridge is
The Java Access Bridge is Oracle's technology that makes Java programs visible to assistive technology on
Windows. Java programs describe themselves through the Java Accessibility API, the package javax.accessibility.
A Windows screen reader talks to the bridge's Windows DLLs, these talk through Java libraries to the Java
Virtual Machine and the program, and the answers come back the same way.

## Why Java programs need the Java Access Bridge to work with NVDA
Windows screen readers need a way to talk to the Java Accessibility API, and the Java Access Bridge gives them
that. Oracle says support for the Java Accessibility API is built into Swing components. Oracle's guide for Java
8 names NVDA among the assistive technologies that work with the bridge, from NVDA 2011.3 on 64-bit Windows, and
suggests testing with a Swing program such as the SwingSet2 demo.

## Turning on the Java Access Bridge with jabswitch
The Java Access Bridge is off by default. To turn it on, run jabswitch -enable from the bin folder of the
installed Java; Oracle writes it as %JAVA_HOME%\bin\jabswitch -enable. The command jabswitch -disable turns it
off again. After turning it on, restart the screen reader and any Java programs that were running.

## Turning on the Java Access Bridge in the Ease of Access Center
Oracle's guide for Java 8 says: open Control Panel, Ease of Access, Ease of Access Center, or press Windows+U.
Choose "Use the computer without a display". Under "Other programs installed", check "Enable Java Access
Bridge"; it may be further down. The Ease of Access Center cannot turn the bridge off again; use jabswitch
-disable for that.

## Java Access Bridge 32-bit and 64-bit: which Java to install
The 32-bit Java runtime gives the bridge only to 32-bit assistive technology, and the 64-bit runtime only to
64-bit assistive technology, so Oracle recommends installing both. On 64-bit Windows the bridge's files are
WindowsAccessBridge-32.dll and WindowsAccessBridge-64.dll; on 32-bit Windows it is WindowsAccessBridge.dll. The
bridge has been part of the Java runtime since Java 7 update 6.

## Testing the Java Access Bridge: jaccessinspector and jaccesswalker
Since JDK 11 the bin folder of the JDK has two tools: jaccessinspector shows the accessibility information of
objects in a running Java program, and jaccesswalker shows the tree of a program's components. They replace the
older Java Ferret and Java Monkey, which are still used for 32-bit programs.

## The Java Accessibility API and the Java Accessibility Utilities
Java SE has three accessibility parts: the Java Access Bridge; the Java Accessibility API in
javax.accessibility, part of the Java Foundation Classes; and the Java Accessibility Utilities in
com.sun.java.accessibility.util. The utilities help assistive technology find the objects that implement the
API, load support into the Java Virtual Machine, and follow events, such as which window has the focus.

## How NVDA uses the Java Access Bridge
NVDA's user guide lists the Java Access Bridge among the interfaces NVDA supports. NVDA's source shows that it
loads its own copy of windowsaccessbridge.dll from its program folder, and that an installed NVDA, outside
secure screens, turns the bridge on for the user when it is off, by writing
assistive_technologies=com.sun.java.accessibility.AccessBridge into the file .accessibility.properties in the
user's home folder.

## Qt programs on Windows
Qt's documentation says Qt exposes a program's interface to screen readers through each platform's own
accessibility APIs, and that its accessibility support was first built for MSAA. Ready-made widgets give enough
information to be usable. A custom widget needs its own QAccessibleInterface, usually by inheriting
QAccessibleWidget, and should send accessibility events when it changes.

## Electron programs
Electron's documentation says accessibility in an Electron program works much like in a website, since both are
HTML, and that it exposes Chrome's accessibility tree. Electron turns its accessibility features on when it
finds assistive technology such as JAWS, and a program can also turn them on with
app.setAccessibilitySupportEnabled. NVDA's user guide says NVDA reaches Chromium browsers through IAccessible2,
using UI Automation only when needed.

## Games and screen readers
Microsoft's Xbox Accessibility Guideline 106 asks that a game's core text, such as menus, options, the HUD and
changes of state, either support the screen readers of the platform or be spoken by the game through a speech
synthesizer. Microsoft's examples include games, such as Forza Horizon 4 and Minecraft, that speak their own
menus and notifications when screen narration is turned on.
