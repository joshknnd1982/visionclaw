---
name: Find what I downloaded
description: For finding a file that was just downloaded: the newest files in the Downloads folder, and opening or moving one.
when: where did my download go, where is my download, find my download, what did i just download
uses: files, open_thing, file_task, web_page
steps:
- files: what is the newest file in my downloads folder
log: errors
lands: moved
---

Say the newest files in the Downloads folder first, each with its name, kind and when it arrived. Open a file or the folder only when the user asks, and say which program opens it. Moving, renaming or deleting a file is asked about first, and a deleted file goes to the Recycle Bin. A downloaded file that installs or runs a program is opened only after a question that says it can change the computer.
