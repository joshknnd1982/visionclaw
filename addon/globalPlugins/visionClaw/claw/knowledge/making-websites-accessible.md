# Making websites, programs and controls usable for good

## How to choose a way to fix a website or a program
Inspect first with check_access. It reads every control NVDA knows of the web page or the window, watches
for a moment to see what changes by itself, and compares the picture with the text. It reports the problems
in plain sentences and says which of them an add-on can fix. Then fix_access makes those fixes, all of them
or the one the user names. For one wish the user describes in words, such as a key that presses Play, use
add_fix. Write an add-on with the coder model only for behaviour that none of these fixes can give.

## The five kinds of fix
Every fix belongs to one website, in any browser, or to one program. Jump: two keys that move to the next
and the previous item of a kind, such as the posts of a feed, search results, videos or clickable things.
Press: one key that presses a control found by its name, wherever the user is on the page or in the window.
Read: one key that reads a control's text, such as a time, a status or a count. Name: a name for controls
that have none. Watch: saying a control's text whenever it changes. The fixes of one website or program are
kept together in one add-on, called fixes and then the site or program. It stays until the user has it
removed with remove_helper, and export_addon saves it as a file to install for good or to share.

## Why these fixes are not written by a model
The add-on is put together by plain code from fixed, tested parts and the list of fixes as data. So what
it does can be told to the user exactly, before it is turned on, and a small model cannot break it. This is
why repair_addon refuses such an add-on: there is no model-written code in it to correct. To change a fix,
make it again with add_fix; the newer fix replaces the older one about the same thing.

## Web pages that load more as you scroll: feeds, timelines, endless lists
Sites like Facebook add posts while the user moves down, so the page has no end and NVDA's place can jump.
A feed marks each post as an article. check_access counts the posts and offers keys that go from post to
post; comments inside a post are skipped. When the last loaded post is reached, the key says that no more
are loaded yet; moving there makes the site load more, and the same key finds them a moment later.

## Video, TV and audio sites
A player's buttons are often shown only while the mouse moves, and their names switch, as Play and Pause do.
check_access finds the player's buttons by all the names sites give them and offers one key each for play or
pause, mute, full screen and captions, and a key that reads the time. When NVDA finds no buttons at all,
the player's own keys usually work after NVDA+Space switches to focus mode: Space or K for play and pause,
M for mute, F for full screen, the arrow keys to move in the film.

## Controls without a name on a web page or in a program
A name can only be given reliably to a control that something fixed in the code tells apart: an id, a class
name a person wrote, a picture's file name, a control id or an automation id. Class names made by a tool,
like x1n2onr6, are shared by unrelated controls and change when the site is rebuilt, so nothing is hung on
them. Where the code names the control, like btn-close, that name is used. Where it does not, the vision
model looks at the control's picture, and the user is told the name is a guess. Controls that nothing tells
apart are left as they are, and the report says how many.

## Things that can be clicked but are not buttons or links
Many sites make a plain block of text clickable. NVDA says clickable, but Tab and the B and K keys pass it
by. check_access counts these and offers keys that move from one clickable thing to the next.

## Windows NVDA cannot read at all
When NVDA finds almost nothing in a window, the program draws itself and no add-on can name what NVDA
cannot see. Use the picture instead: list_items and click_item, an app helper hotkey with create_helper, or
pointer mode.

## Add-ons installed in NVDA
nvda_info with the topic addons lists every installed add-on with its version and whether it is on.
addon_info tells about one add-on: what it says about itself, what it adds, its commands with their keys
where the user is now, and what its help says about a question. An add-on's commands are NVDA commands, so
find_command finds them and run_command runs them; its settings are found with find_setting when the add-on
keeps them in NVDA's configuration.
