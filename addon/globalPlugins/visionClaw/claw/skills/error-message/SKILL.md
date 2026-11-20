---
name: Understand an error or a message that popped up
description: Reads a message box or error exactly, says what it means and what the buttons do.
when: error, error message, popped up, warning, message box, alert, something went wrong, crashed, what does this message mean, dialog box
uses: read_text, describe, nvda_question, where_am_i
log: errors, freezes
---

Read the message exactly first, including any error number. Then name the buttons it offers, in order. Then say in plain words what the message means and what each button would most likely do, and say when that is a guess. Do not press any button unless the user asks.
