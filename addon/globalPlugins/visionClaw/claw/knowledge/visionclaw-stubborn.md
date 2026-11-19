<!-- Written on 2026-11-19 from VisionClaw's own code: accesstools.py (the inspection, judging how a control is worked,
naming a control from its picture), claw/accessnotes.py (what is kept about a program or website), claw/hardcase.py and
hardtools.py (the model for hard cases), claw/advice.py (which model fits), claw/fixes.py (the kinds of lasting fix) and
the skills in claw/skills. When the code changes, read it again and bring these up to date; do not write them from
memory. Each section is short on purpose: one section is one answer, and it is given to the user word for word by the
smallest models.
Nothing may stand between this comment and the first heading but the title, or it becomes a section. -->
# VisionClaw and stubborn programs, controls and web pages

## How VisionClaw makes a stubborn program, control or web page usable
Say: check this program, or check this page. VisionClaw reads every control NVDA knows, asks the models only about
what the facts do not say, and reports the worst problem first. Then say: fix them. The simplest remedy comes first: a
name, a key that presses or reads a control, a lasting fix; pointer mode, NVDA+Alt+K; an add-on last.

## A control that does not say whether it is checked, pressed, expanded or selected
NVDA says a state only when the program reports it. Say: check this program. The report names controls whose state is
missing. A lasting fix gives a key that reads the control, or says it whenever it changes. A state read from the
picture is said in words and said to be read from the picture.

## A control NVDA reads as pane, unknown, group, text or clickable
What NVDA calls a control comes from the program and from the class of its window, which tells the toolkit or game
engine that drew it. A deep check finds out how each such control is worked: from what Windows reports first, then by
the models, from its picture and from the facts. Say: check this window deeply.

## A web page control built from plain parts: custom drop-downs, menus, tabs, sliders
Some pages build controls from plain parts that tell NVDA nothing or take no keys. Say: check this page. Lasting fixes
for the website give a part a name, a key that presses it, a key that jumps to it, or a key that reads it. They hang
only on what the page's code keeps the same, and work in any browser.

## What VisionClaw remembers about a stubborn program: its access notes
VisionClaw keeps what it found about each program and website in a Markdown file in the folder access of its data
folder: how controls are worked, names read from pictures, what drew the window. A control agreed on before is not put
to the models again. The file is yours: change or delete any line or the whole file.

## The model for hard cases: when VisionClaw uses the larger model
When the everyday models could not write or correct an add-on, or could not tell how a control is worked, VisionClaw
offers its model for hard cases, Qwen3 14B. It asks first, is slower, reads and writes text only, and its work is
checked like any other. Choose it in the models window, NVDA+Alt+M, in the list Model for hard cases.

## A name for a control without one, read from its picture
Say: check this program, then fix them. The model that sees is shown the control's picture and told the program, the
window and the named controls around it, and answers with one to three words. Two controls that share a look must get
the same name, or none is given. Every name is offered before it is kept.

## Which model fits stubborn programs and hard cases
Ask: which model is best for stubborn programs, or which model for hard cases. VisionClaw suggests from your graphics
card and memory: the largest everyday model that fits, at most 9B, and whether the 14B model for hard cases runs here,
on the card, shared with the processor, or not at all. It changes nothing; you choose with NVDA+Alt+M.

## A window that is hidden, behind another window, or takes no focus
Ask: where am I. VisionClaw says which window is in front and where the focus is. Say: switch to, and the window's
name, to bring it to the front. alt+tab goes through the open windows, NVDA+t reads the title, NVDA+tab the focus.
