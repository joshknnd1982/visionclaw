---
name: Get through an installer or setup wizard
description: Reads each page of a setup wizard, points out extra software, and moves on only when asked.
when: setup wizard, install wizard, installation wizard, installer window, setup program, licence agreement, license agreement, next button, finish button
uses: read_text, describe, click, step_through
---

For each page, say its title and the main text in short. Name every checkbox and whether it is checked, and point out any that add extra software, toolbars or change the browser. Name the button that moves on. Never accept a licence, press Install or uncheck anything unless the user asked.
