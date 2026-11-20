# Words VisionClaw understands

VisionClaw reads what you say the way a text adventure reads its player: some words are understood as other
words that mean the same, before VisionClaw decides what to do. "Take a peek at the screen" is understood as
"look at the screen", and "kill the typing echo" as "turn off the typing echo". When the meaning of your words
was changed, the answer begins with "Understood as", so you always know how you were understood.

This file comes with VisionClaw and is read every time a request begins. Your own words are kept apart, in the
file understanding.md in VisionClaw's data folder: say "when I say shh, I mean stop talking", and VisionClaw
keeps it there. Your own words always come first.

How a line is written: - "these words", "or these" mean "those words". [x] stands for any words, which are
kept as they are; [keys] for a key combination; [thing] for a button, link, tab, icon or other item named in
your words; [window] for this window, the dialog, the program and the like. Words in quotes, text you ask to
have typed, a name you give, what is to be searched for, and what you ask VisionClaw to remember are never
changed.

## Said for nothing at the start

Taken away only at the very start of a request.

- "hey visionclaw", "hi visionclaw", "hello visionclaw", "ok visionclaw", "okay visionclaw", "visionclaw"
- "hey there", "hey", "hi", "hello", "ok so", "okay so", "so", "um", "umm", "uh", "erm", "er", "ugh", "oh", "ah", "well", "alright", "all right", "please"

## Said for nothing at the end

Taken away only at the very end of a request.

- "for me please", "for me", "please", "thanks", "thank you", "thx", "cheers", "if you can", "if you could", "if you don't mind", "if possible", "real quick", "for a sec", "when you get a chance", "down there", "up there", "over there"

## Spellings

Changed wherever they stand. Said to nobody, because the meaning stays the same.

- "gimme" means "give me"
- "lemme" means "let me"
- "wanna" means "want to"
- "gonna" means "going to"
- "gotta" means "have to"
- "dunno" means "don't know"
- "ya", "u" mean "you"
- "ur" means "your"
- "pls", "plz" mean "please"
- "whats" means "what's"
- "wheres" means "where's"
- "hows" means "how's"
- "dont" means "don't"
- "cant" means "can't"
- "wont" means "won't"
- "doesnt" means "doesn't"
- "isnt" means "isn't"
- "where'd" means "where did"
- "what'd" means "what did"
- "how'd" means "how did"
- "pic", "pict", "piccy" mean "picture"
- "pics", "pix" mean "pictures"
- "an add on", "an addon" mean "an add-on"
- "the add on", "the addon" mean "the add-on"
- "my add on", "my addon" mean "my add-on"
- "this add on", "this addon" mean "this add-on"
- "that add on", "that addon" mean "that add-on"
- "add ons", "addons" mean "add-ons"
- "what's on screen" means "what's on the screen"
- "what is on screen" means "what is on the screen"

## Same meaning

Changed wherever they stand, and said in the answer.

- "quicker", "speedier", "snappier", "zippier" mean "faster"
- "softer" means "quieter"
- "only speak words when I type", "only say words when I type", "speak only words when I type", "only speak whole words when I type", "only read words as I type", "just speak words when I type" mean "turn on speak typed words and turn off speak typed characters"
- "only speak characters when I type", "only speak letters when I type", "speak only characters when I type", "just speak letters when I type" mean "turn on speak typed characters and turn off speak typed words"
- "a tad", "a smidge", "a smidgen", "a hair", "a wee bit", "a little bit", "a tiny bit", "a teeny bit" mean "a bit"
- "way too", "far too", "much too", "waaay too", "wayyy too" mean "too"
- "what on earth", "what the heck", "what in the world" mean "what"
- "where on earth", "where the heck", "where in the world" mean "where"
- "how on earth", "how the heck", "how in the world" mean "how"
- "why on earth", "why the heck", "why in the world" mean "why"
- "who on earth", "who the heck" mean "who"
- "which on earth" means "which"
- "the bin", "the trash", "the trash can", "the wastebasket", "the waste basket", "the rubbish bin", "the recycling bin" mean "the recycle bin"
- "my bin", "my trash", "my trash can", "my wastebasket", "my rubbish bin" mean "my recycle bin"
- "your brain", "your brains" mean "your AI model"
- "which brain" means "which AI model"
- "what brain" means "what AI model"
- "is blaring", "is deafening", "is booming", "is screaming", "is ear-splitting" mean "is too loud"
- "too squeaky", "too shrill", "too high-pitched" mean "pitched too high"
- "the arrows" means "the arrow keys"
- "my arrows" means "my arrow keys"
- "steer the mouse" means "move the mouse"
- "steer the pointer" means "move the pointer"
- "shut up about", "quit going on about", "stop going on about", "quit saying", "quit announcing", "quit reading out" mean "stop announcing"
- "what have you got on me", "what do you have on me", "what've you got on me" mean "what do you know about me"
- "have I got" means "do I have"
- "the button that says [x]", "the button labelled [x]", "the button labeled [x]", "the button called [x]", "the button named [x]" mean "the [x] button"
- "the link that says [x]", "the link called [x]", "the link named [x]" mean "the [x] link"
- "the tab that says [x]", "the tab called [x]", "the tab named [x]" mean "the [x] tab"
- "the icon that says [x]", "the icon called [x]", "the icon named [x]" mean "the [x] icon"
- "the checkbox that says [x]", "the check box that says [x]" mean "the [x] checkbox"
- "where the main stuff starts", "where the main bit starts", "where the main part starts", "where the main content starts", "where the main stuff begins", "where the main part begins" mean "the main content"
- "going on about", "banging on about", "rambling on about", "rambling about" mean "about"

## Ways to say what to do

Changed only where something to do begins: at the start of a request, or after "and", "then", a comma, "please" or "could you". Said in the answer.

- "take a peek at", "have a peek at", "sneak a peek at", "peek at", "take a glance at", "have a glance at", "glance at", "eyeball", "have a look at", "take a look at", "look over" mean "look at"
- "check out the screen", "check out my screen", "check out this screen" mean "look at the screen"
- "check out this window", "check out the window" mean "look at this window"
- "check out this picture", "check out the picture", "check out this photo", "check out the photo", "check out this image", "check out the image", "check out this pic" mean "look at this picture"
- "check out this chart", "check out the chart", "check out this graph", "check out the graph" mean "look at this chart"
- "give [x] a look", "give [x] a once-over", "give [x] the once-over" mean "look at [x]"
- "fire up", "boot up", "spin up", "start up", "load up", "pull up", "bring up", "open up", "pop open", "crack open" mean "open"
- "get rid of [window]", "kill [window]", "ditch [window]", "shut [window]", "x out of [window]", "exit out of [window]", "close out of [window]", "close out [window]" mean "close [window]"
- "smack [thing]", "whack [thing]", "bash [thing]", "jab [thing]", "poke [thing]", "hit [thing]", "tap on [thing]", "hit on [thing]" mean "click [thing]"
- "give [thing] a click", "give [thing] a press", "give [thing] a poke", "give [thing] a tap" mean "click [thing]"
- "punch in [keys]", "punch [keys]", "do a [keys]", "do [keys]", "hit [keys]", "key in [keys]", "tap [keys]" mean "press [keys]"
- "key in [x]", "punch in [x]" mean "type [x]"
- "google [x]", "bing [x]", "search up [x]", "search online for [x]", "search the internet for [x]" mean "search the web for [x]"
- "head back", "hop back", "pop back" mean "go back"
- "head forward", "hop forward" mean "go forward"
- "head to", "head over to", "hop over to", "hop to", "zip to", "pop over to", "navigate over to", "skip ahead to" mean "go to"
- "drop me into [x]", "plonk me into [x]", "stick me into [x]", "pop me into [x]", "pop me in [x]", "plop me in [x]" mean "put me in [x]"
- "land me on [x]", "plonk me on [x]", "pop me on [x]", "plop me on [x]", "park me on [x]" mean "put me on [x]"
- "shift the focus to [x]", "shift focus to [x]", "bring the focus to [x]", "get the focus onto [x]", "get the focus on [x]", "get my focus on [x]", "focus me on [x]" mean "put the focus on [x]"
- "kill [x]", "nix [x]", "shut off [x]", "knock off [x]" mean "turn off [x]"
- "crank up [x]", "bump up [x]", "pump up [x]", "jack up [x]", "ramp up [x]" mean "turn up [x]"
- "crank down [x]", "dial down [x]", "tone down [x]", "knock down [x]" mean "turn down [x]"
- "take back [x]", "roll back [x]" mean "undo [x]"
- "remind me what [x] does" means "what does [x] do"
- "remind me what [x] is" means "what is [x]"
- "remind me how to [x]", "any idea how to [x]", "do you know how to [x]", "got any idea how to [x]" mean "how do I [x]"
- "remind me how I [x]", "any idea how I [x]", "do you know how I [x]", "how would one [x]" mean "how do I [x]"
- "what's the trick to [x]", "what's the secret to [x]", "is there a way to [x]", "is there a quick way to [x]" mean "how do I [x]"
- "what's the trick for [x]", "what's the secret for [x]" mean "what's the shortcut for [x]"
- "fill me in on [x]", "clue me in on [x]", "give me the lowdown on [x]", "tell me all about [x]" mean "tell me about [x]"
- "where did [x] go", "where has [x] gone", "where did I put [x]", "where did I save [x]" mean "find [x]"
- "lock up [x]" means "lock [x]"
- "dump the recycle bin", "clear out the recycle bin", "clean out the recycle bin", "flush the recycle bin", "purge the recycle bin", "wipe the recycle bin", "dump my recycle bin", "clear out my recycle bin", "clean out my recycle bin" mean "empty the recycle bin"

## Same meaning, in add-ons

Only where VisionClaw reads a request for an add-on into its pieces: what the add-on says or does, and when. The
lines above apply there too. Words in quotes, the words the add-on is to say, and keys are never changed.

- "pings me", "beeps at me", "beep at me", "dings me", "dings at me" mean "beeps"
- "makes nvda ding", "makes nvda beep", "make nvda ding", "make nvda beep" mean "beeps"
- "makes nvda say", "make nvda say" mean "says"
- "yells", "shouts", "hollers", "bellows", "blurts out", "blurts", "calls out", "pipes up", "whispers", "sings out" mean "says"
- "yell", "shout", "holler", "bellow", "blurt out", "blurt", "call out", "pipe up", "whisper" mean "say"
- "chimes", "bleeps", "pings", "boops", "chirps", "squeaks", "blips", "clicks softly", "goes ding", "goes beep", "goes boop" mean "beeps"
- "chime", "bleep", "ping", "boop", "chirp", "squeak", "blip", "click softly" mean "beep"
- "makes a sound", "makes a noise", "plays a sound", "makes a beep", "sounds a tone" mean "beeps"
- "make a sound", "make a noise", "play a sound", "sound a tone" mean "beep"
- "focus hits", "focus jumps to", "focus jumps onto" mean "focus lands on"
- "when i focus [thing]", "whenever i focus [thing]" mean "when [thing] gets the focus"
- "end up on", "end up at" mean "land on"
- "gets ticked" means "gets checked"
- "is ticked" means "is checked"
- "gets unticked" means "gets unchecked"
- "is unticked" means "is unchecked"
- "becomes greyed out", "becomes grayed out" mean "becomes disabled"
- "gets switched on", "gets turned on" mean "gets pressed"
- "gets switched off", "gets turned off" mean "gets unpressed"
- "goes busy" means "becomes busy"
- "comes in" means "arrives"
- "gets opened up" means "gets expanded"

## Ways to say what to do, in add-ons

- "whip up", "knock together", "rig up", "throw together", "cook up" mean "make"

## Same meaning, in questions about a picture

Only where VisionClaw reads a question about a picture or the screen into its parts, to know what kind of answer it
wants. The lines above apply there too.

- "make out" means "read"
- "lettering" means "text"
- "hue", "colouring", "coloring" mean "colour"
- "tally up", "tally" mean "count"
- "scribbled", "scrawled", "jotted down", "jotted" mean "written"
- "trendline", "trend line" mean "trend"
- "lit up" means "highlighted"
