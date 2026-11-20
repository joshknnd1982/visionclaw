---
name: Choose a date in a calendar
description: For choosing a date in a calendar or date picker that cannot be worked with the keyboard.
when: date picker, in this calendar, in the calendar, pick a date, choose a date, departure date, arrival date, check-in date, calendar
uses: pick_date
log: errors, objects
lands: told
---

Say which date was chosen, with its weekday, in the words of the result. Where the result says the calendar was read from the window's picture, tell the user to check the date field: move to it with tab and read it with NVDA+tab. Where no calendar was found, say that it must be showing first, and that alt+down arrow opens the calendar of many date fields. Never say a date was chosen unless the result says so.
