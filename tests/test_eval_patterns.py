# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""The planner's patterns, measured without a model, against requests whose job is known.

tests/eval/known.json holds 312 requests VisionClaw handled rightly; the three evaluation sets hold requests in words
it was never tuned on when they were written (tests/eval_routing.py scores them with the real model). This test fails
when a change to the patterns names the wrong job for more of them than on 2026-11-19, so that a pattern that helps one
wording cannot quietly break others. Raise the numbers when a change measurably helps; never lower them without
saying why in docs/STATUS.md.

  python tests/test_eval_patterns.py
"""
import json
import os

import harness  # noqa: F401
from visionClaw.claw import planner

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval")
# The first pattern's job, right for at least this many, on 2026-11-19.
LEAST = {"known": 293, "requests": 120, "requests2": 80, "requests3": 51}

known = json.load(open(os.path.join(HERE, "known.json"), encoding="utf-8"))["jobs"]
right = [text for job, texts in known.items() for text in texts if planner.hint(text) == job]
assert len(right) >= LEAST["known"], f"known requests: {len(right)} named rightly, before {LEAST['known']}"
seen = {text.lower() for texts in known.values() for text in texts}
for name in ("requests", "requests2", "requests3"):
	items = json.load(open(os.path.join(HERE, name + ".json"), encoding="utf-8"))["requests"]
	for item in items:
		assert item["request"].lower() not in seen, f"{item['request']!r} is known: an evaluation set must stay unseen"
		assert all(job in planner.RECIPES for part in item["expect"] for job in part), item
	one = [item for item in items if len(item["expect"]) == 1]
	count = sum(planner.hint(item["request"]) in item["expect"][0] for item in one)
	assert count >= LEAST[name], f"{name}: {count} named rightly, before {LEAST[name]}"
# A how-question is answered with keys, and a why-question is answered: nothing is done.
for said, job in (("what's the shortcut to get to the address bar", "explain_keys"), ("how can I jump between headings", "explain_keys"),
		("why does nvda say clickable all the time", "nvda_question"), ("how do I get to the system tray", "explain_keys")):
	assert planner.hint(said) == job, (said, planner.hint(said))
# The model's choice stands where the words point to it too, or where only a pattern for any question points elsewhere.
assert planner.challenger("what windows do I have open", "nvda_question") is None
assert planner.challenger("click the attack button every second", "timed_click") is None
assert planner.challenger("send control s to this program", "do_command") == "press_keys"
print("OK")
