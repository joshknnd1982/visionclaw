---
name: Read a table or spreadsheet
description: Reads tables and spreadsheets row by row with their headings, and names the keys to move in them.
when: table, spreadsheet, excel, cells, cell, columns, rows, row, column, worksheet
uses: describe, read_text, explain_keys, nvda_question
log: errors, objects
lands: stay
---

Say how many rows and columns there are and the column headings. Read one row at a time, each value with its heading, exactly. Say when cells are empty or merged. NVDA moves between the cells of a table with control+alt and the arrow keys.
