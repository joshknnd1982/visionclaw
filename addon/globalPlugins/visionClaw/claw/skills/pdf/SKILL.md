---
name: Read a PDF that NVDA reads badly
description: Reads a scanned or empty-sounding PDF from its picture, page by page.
when: pdf, acrobat, adobe reader, scanned document, document is empty, says blank, reads nothing in the pdf
uses: read_text, nvda_question, describe, fill_blank
---

When NVDA says the document is empty or reads only graphic, the PDF is probably a scan, and its text must be read from the picture. Read it in reading order, column by column, and say the page number when it is shown. Keep tables row by row, with each value under its heading. For writing on a scanned form, name the printed label the line or box belongs to, and say where the click went and whether the text shows there.
