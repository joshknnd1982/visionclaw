# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - a drawn knob, dial or slider set to a number: "turn the Mix knob down to 35 percent". Where a
# program offers a control's value to Windows, the number is simply set (controltools.py). A control that is only
# drawn, as in many audio plug-ins, offers nothing: a sighted person drags it and watches the number next to it.
# Here that is done the same way, by plain code: the control is moved one step, the text around it is read before
# and after, the number that changed is the control's own, and the steps go on, large while far away and small
# when near, until the number is the one asked for or as near as the control's own steps allow.
# Nothing is assumed about the control: which way is up is learned from the first step that changes the number,
# and how far a step goes is measured, never guessed. Where no number shows, or the number is in another unit than
# the one asked for, that is said and nothing more is tried: the arrow keys of work_control stay for that.
# No model is asked. No NVDA dependencies; the callers give the two things that touch the screen: read() gives
# the lines of text around the control, stroke(direction, size) moves it one step and says whether it moved.

import re

# The sizes of a step, the same names as claw/dragcontrol.py.
STEP, FINE, FAR = "step", "fine", "far"
# How a search ended.
REACHED, NEAREST, NO_NUMBER, OTHER_UNIT, STUCK, LIMIT, SEVERAL = "reached", "nearest", "no number", "other unit", "stuck", "limit", "several"
# Never more strokes than this for one request.
MAX_STROKES = 48
_NUMBER = re.compile(
	r"(?<![\w.])([-−+]?\d{1,5}(?:[.,]\d{1,3})?)\s*(%|percent|db|dbfs|hz|khz|ms|sec|s|st|ct|bpm|x)?(?![\w])", re.IGNORECASE)
_PERCENT = ("%", "percent")


def _shape(line):
	"""A line of text without its numbers: what stays the same when the number in it changes."""
	return " ".join(_NUMBER.sub("#", str(line)).lower().split())


def numbers(lines):
	"""The numbers in some lines of text, in reading order: [(value, unit as it is written or "", the line without
	its numbers)]."""
	found = []
	for line in lines or ():
		shape = _shape(line)
		for hit in _NUMBER.finditer(str(line)):
			raw = hit.group(1).replace("\u2212", "-").replace(",", ".")
			try:
				value = float(raw)
			except ValueError:
				continue
			found.append((value, hit.group(2) or "", shape))
	return found


def fresh(before, after):
	"""The numbers that are in the text now and were not there before: what a step changed."""
	left = [item[:2] for item in numbers(before)]
	found = []
	for item in numbers(after):
		if item[:2] in left:
			left.remove(item[:2])
		else:
			found.append(item)
	return found


def _fits(unit, percent):
	"""Whether a number's unit is the one that was asked for. A number without a unit may be either."""
	if not unit:
		return True
	return unit.lower() in _PERCENT if percent else unit.lower() not in _PERCENT


def _own(items, name, shape=None):
	"""Which of several numbers is the control's own: the one in the line that names the control, else the one in
	the line the control's number stood in before. None when that does not tell them apart."""
	if len(items) == 1:
		return items[0]
	words = " ".join(str(name or "").lower().split())
	if words:
		named = [item for item in items if f" {words} " in f" {item[2]} "]
		if len(named) == 1:
			return named[0]
	if shape:
		same = [item for item in items if item[2] == shape]
		if len(same) == 1:
			return same[0]
	return None


def initial(lines, percent, name=""):
	"""The control's number before anything was moved, when the text around it has exactly one number it can be:
	(value, unit, its line without numbers), or None."""
	found = [item for item in numbers(lines) if _fits(item[1], percent)]
	units = [item for item in found if item[1]] if percent else found
	return _own(units or found, name) if (units or found) else None


def reading(before, after, percent, name="", shape=None):
	"""The control's number after a step, from the text before and after it: (value, unit, its line without
	numbers, whether it was the only number that changed); None when no number changed; SEVERAL when several
	changed and neither the control's name nor the line its number is known to stand in tells which is its own.
	shape: that line, given only once a step has shown it for certain."""
	changed = fresh(before, after)
	if not changed:
		return None
	fitting = [item for item in changed if _fits(item[1], percent)] or changed
	units = [item for item in fitting if item[1]] or fitting
	found = _own(units, name, shape)
	# With it: whether it was the only number that changed, which makes its line known for certain.
	return found + (len(units) == 1,) if found is not None else SEVERAL


def tolerance(wanted):
	"""How near the number must be to count as the one asked for: it must be that number as it is shown, so 34.6
	is not 35."""
	return 0.05


def seek(wanted, percent, read, stroke, check=None, limit=MAX_STROKES, name=""):
	"""Move a control until the number shown at it is the one asked for. read() gives the lines of text around the
	control; stroke(direction, size) moves it one step (direction 1 or -1; size STEP, FINE or FAR) and gives whether
	anything moved; name is what the control is called, which tells its number from others that change with it.
	Returns {"why": how it ended, "now": the number last read or None, "unit", "first": the number before,
	"strokes": how many steps were made}."""
	lines = read()
	known = initial(lines, percent, name)
	now, unit, shape = known if known else (None, "", None)
	first = now
	near = tolerance(wanted)
	# Which way the control answers to "up": 1 as asked, -1 the other way round. Learned from the first change.
	sense = None
	gain = {}
	strokes = stuck = crossed = 0
	size = None
	best = None
	made = []
	# The line the control's number stands in counts as known once a step changed that number alone, or the
	# control's name is in it. Before that it is only the one number that happened to be there.
	certain = bool(known and name and f" {' '.join(name.lower().split())} " in f" {shape} ")

	def result(why):
		return {"why": why, "now": now, "unit": unit, "first": first, "strokes": strokes}

	def undo():
		"""Take back the steps made so far, the last first, as well as can be: the control is left where it was."""
		for direction, size in reversed(made):
			stroke(-direction, size)
		del made[:]

	while strokes < limit:
		if check is not None:
			check()
		if now is not None:
			if abs(now - wanted) <= near:
				return result(REACHED)
			if best is None or abs(now - wanted) < abs(best - wanted):
				best = now
			away = abs(wanted - now)
			direction = (1 if wanted > now else -1) * (sense or 1)
			# The largest step that is not known to go further than what is left; a small one when nothing is known yet.
			if size is None:
				size = FINE
			else:
				fitting = [kind for kind in (FAR, STEP, FINE) if kind in gain and gain[kind] <= away * 1.2]
				untried = [kind for kind in (STEP, FAR) if kind not in gain]
				if fitting:
					size = fitting[0]
					# A larger step that was never tried may fit better when the way left is long.
					if untried and away > 3 * gain[size]:
						size = untried[0]
				else:
					size = FINE
		else:
			direction, size = 1, FINE
		moved = stroke(direction, size)
		strokes += 1
		made.append((direction, size))
		after = read()
		new = reading(lines, after, percent, name, shape if certain else None)
		lines = after
		if new == SEVERAL:
			undo()
			return result(SEVERAL)
		if new is None:
			stuck += 1
			# Nothing changed in the text: at its end, or it shows no number. Once more with a larger step, then stop.
			if stuck >= 2 or (not moved and now is None and strokes >= 2):
				if now is None:
					undo()
					return result(NO_NUMBER)
				return result(STUCK)
			if now is None:
				size = STEP
			continue
		stuck = 0
		value, newUnit, newShape, alone = new
		if not _fits(newUnit, percent):
			now, unit = value, newUnit
			# Back to where it was, as well as can be, and read again what it shows there.
			undo()
			back = reading(lines, read(), percent, name, newShape)
			if back not in (None, SEVERAL):
				now, unit = back[0], back[1]
			return result(OTHER_UNIT)
		if shape is not None and newShape != shape and not certain:
			# The number that changed is not the one taken for the control's before anything moved: that one was
			# another control's, so what the control showed before is not known.
			first = None
			now = None
		shape = newShape
		certain = certain or alone or bool(name and f" {' '.join(name.lower().split())} " in f" {shape} ")
		if now is not None:
			# A number is being followed: what was done so far is wanted, and is not taken back.
			del made[:]
		if now is not None and value != now:
			change = value - now
			if sense is None:
				sense = 1 if (change > 0) == (direction > 0) else -1
			gain[size] = abs(change)
			# Past the number that was asked for: the next steps are small. Past it twice with the smallest step:
			# the control cannot stand on that number, and the nearer side is where it stays.
			if (now - wanted) * (value - wanted) < 0:
				crossed += 1
				if size == FINE and crossed >= 2:
					now, unit = value, newUnit or unit
					if abs(now - wanted) > abs(best - wanted):
						stroke(-direction, FINE)
						strokes += 1
						back = reading(lines, read(), percent, name, shape)
						if back not in (None, SEVERAL):
							now = back[0]
					return result(NEAREST if abs(now - wanted) > near else REACHED)
		now, unit = value, newUnit or unit
	return result(LIMIT)


def _said(value, unit):
	number = f"{value:g}"
	return f"{number} percent" if unit.lower() in _PERCENT else f"{number} {unit}".strip()


def askedText(wanted, percent):
	return f"{wanted:g} percent" if percent else f"{wanted:g}"


def text(name, wanted, percent, outcome):
	"""What happened, for the user: what the control showed, what it shows now, and how sure that is."""
	asked = askedText(wanted, percent)
	now, unit, why = outcome["now"], outcome["unit"], outcome["why"]
	steps = f"{outcome['strokes']} {'step' if outcome['strokes'] == 1 else 'steps'}"
	read = "This number was read from the picture next to the control after every step."
	if why == REACHED:
		was = f" It showed {_said(outcome['first'], unit)} before." if outcome["first"] is not None and outcome["first"] != now else ""
		return f"{name} now shows {_said(now, unit)}, which is what was asked for.{was} It took {steps} with the mouse. {read}"
	if why == NEAREST:
		return (
			f"{name} now shows {_said(now, unit)}. It does not stand on {asked}: its smallest step goes past it, so this is "
			f"as near as it goes. It took {steps} with the mouse. {read}")
	if why == OTHER_UNIT:
		return (
			f"{name} shows its value as {_said(now, unit)}, not as {'a percentage' if percent else 'a plain number'}, and "
			f"VisionClaw does not know how the two relate. Nothing was left changed. Say the value the way the control "
			f"shows it, or ask to turn {name} up or down.")
	if why == SEVERAL:
		return (
			f"Several numbers changed in the picture when {name} was moved one step, so VisionClaw cannot tell which is its "
			f"own. It was moved one small step and back again. Ask to work {name} with the arrow keys: each press says "
			"what changed.")
	if why == NO_NUMBER:
		return (
			f"No number shows at {name} that changes when it is moved, so it cannot be set to {asked} by reading. It was "
			f"moved a little and back again, as well as can be. Ask to work {name} with the arrow keys; W there asks the "
			"model that sees what it shows.")
	if why == STUCK:
		return (
			f"{name} stopped changing at {_said(now, unit)}, before {asked}: it seems to be at its end, or the number can no "
			f"longer be read. It took {steps} with the mouse. {read}")
	return (
		f"{name} shows {_said(now, unit) if now is not None else 'no number VisionClaw can read'} after {steps}, which is "
		f"where VisionClaw stops trying. It was asked to show {asked}. {read}")


def question(name, wanted, percent):
	"""Asked before a control that is only in a window's picture is moved to a number."""
	return (
		f"Set {name} to {askedText(wanted, percent)} with the mouse? NVDA cannot read this control, so VisionClaw first "
		"finds out how it is worked, then moves it a step at a time and reads the number shown at it after each step.")
