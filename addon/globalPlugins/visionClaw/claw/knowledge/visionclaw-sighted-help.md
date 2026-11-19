<!-- Written on 2026-11-19 from VisionClaw's own code: claw/paper.py and papertools.py (a form that is only a
picture), claw/wizard.py and wizardtools.py (an installer page after page), claw/images.py and picturetools.py (one
picture of a page or a chat), claw/docformat.py and doctools.py (a Word document formatted and its layout
checked), claw/humancheck.py and checktools.py (a check that asks whether you are a person), claw/shopping.py,
claw/seats.py and shoptools.py (options, seats, and the question before a purchase), claw/target.py and
controltools.py (a drawn knob set to a number), claw/colours.py and pagetools.py (a form's fields outlined in red).
When the code changes, read it again and bring these up to date; do not write them from memory. Each section is
short on purpose: one section is one answer, and it is given to the user word for word by the smallest models.
Nothing may stand between this comment and the first heading but the title, or it becomes a section. -->
# VisionClaw doing what a sighted helper was needed for

## A scanned PDF or a form that is only a picture: clicking a line or a box and typing on it
Say: click the line next to Full Name and type my name; click the dotted line labelled Signature; check the box
next to Yes in this scanned form. VisionClaw finds the label in the picture's text and its line or box in the
pixels, asks, clicks and types, and says whether the text shows there. It never signs for you. In Adobe Acrobat,
choose the Fill and Sign tool first.

## An installer or setup wizard: pressing Next page after page, and unchecking offers
Say: uncheck any bundled toolbars in this installer and click Next until the installation starts. VisionClaw asks
once, says each page with its check boxes, unchecks and names boxes that offer extra software, never accepts
licence terms without asking you, and asks before the button that starts the installation.

## A picture in a chat, a meme, a screenshot someone sent, a product photo, the photos of a gallery
Say: what does the latest picture in this chat say; read the text in the latest image and explain the joke; look
at the product photo, is this jacket navy blue or black. VisionClaw finds that one picture, cuts it out, and asks
the model that sees about it alone, one question at a time. A colour is measured from the pixels first.

## Formatting a Word document: APA, MLA, font, line spacing, margins, hanging indent
Say: format this document in APA style; double-space this document; set the font to Times New Roman 12 point;
give the References a half inch hanging indent. VisionClaw asks with every change named and changes it through
Word itself; one Control+Z in Word takes it all back. In Google Docs it tells you the keys instead.

## Whether a document fits on one page, how many pages it has, and text boxes that overlap
Say: does my resume fit on one page; how many pages is this document; are any text boxes overlapping. VisionClaw
reads Word's own numbers: the pages, how much is on the last page, tables wider than the page, and text boxes or
pictures that overlap or reach beyond the page. Nothing is changed.

## A captcha or a check that asks whether you are a person: I'm not a robot, verify you are human
Say: what kind of check is this; click the verify you are human box; what do the squares show; select squares 1,
4 and 7, then verify; get an audio challenge. VisionClaw makes the check readable and workable, and you answer
it: it never chooses squares for you. The site's own audio challenge is the surer way where it works.

## Shopping: choosing a size or colour option, a swatch with no name, and what is chosen
Say: select the dark blue colour option; pick the large size; is the 256GB option selected. An option is chosen
by its name, a swatch with no name by its measured colour, and VisionClaw then says what the page marks as
chosen. Before a button that buys or pays is pressed, the page's total is read to you and you are always asked.

## A seat map: finding a free window or aisle seat and choosing it
Say: find a free window seat near the front; is seat 14C free; pick an aisle seat in an exit row. VisionClaw
reads the seats from their names, or from the map's picture and legend, says the best few with the reason for
each, and clicks one only after asking. Where the map does not say where the wing is, it says so.

## A drawn knob, dial or fader set to a number, as in an audio plug-in
Say: turn the Mix knob down to 35 percent. Where NVDA cannot read the knob, VisionClaw moves it a step at a time
and reads the number shown next to it after every step, until it is the number you asked for or as near as the
knob goes. Where no number shows, it says so and leaves the knob where it was.

## A form that will not send when the only sign is a red border or red text
Say: why won't this form submit. Where the page tells NVDA nothing, VisionClaw measures the picture of the page:
a field outlined in red and a line written in red are named, and NVDA's reading position is put on the first.
Only the fields on the screen are measured: scroll and ask again for the rest.

## Card numbers, passwords and security codes are never typed by VisionClaw
VisionClaw does not type a card number, a security code, an expiry date, a password or a PIN for you. What you
ask is written to VisionClaw's log and spoken as it is typed. Ask VisionClaw to put the focus in the field, then
type it yourself.
