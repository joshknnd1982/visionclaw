---
name: A control that does not say its state
description: For a check box, toggle button, switch, tab or tree item whose state NVDA does not say: checked, pressed, expanded, selected, on or off.
when: does not say checked, doesn't say checked, does not say pressed, doesn't say pressed, does not say expanded, doesn't say expanded, does not say selected, doesn't say selected, does not say on or off, doesn't say on or off, toggle button, toggle switch, state is not announced, state is not read
uses: check_access, fix_access, add_fix, object_facts, describe
---

NVDA says a state only when the program reports it. Read first what is reported about the control: its kind, its states and its actions. Where a state is missing, its picture may show it; then say the state in words, such as checked or not checked, never by a colour. A lasting fix can give a key that reads the control, or announce when it changes. Say which state was missing, how sure the reading is, and what was made.
