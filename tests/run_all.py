# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

"""Runs every test that needs no model and no NVDA. Run it before every commit:

  python tests/run_all.py

The live test, which needs the engine and a model on this computer, is run on its own:

  python tests/live_orchestrator.py
"""
import glob
import os
import py_compile
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TESTS = ("test_speaker.py", "test_busy.py", "test_core.py", "test_one_model.py", "test_prompts.py", "test_skills.py", "test_skills_window.py", "test_portable.py", "test_portable_window.py", "test_models_window.py", "test_parts.py", "test_codeplan.py", "test_understand.py", "test_pointer.py", "test_touch.py", "test_gamepad.py", "test_computer.py", "test_planning.py", "test_places.py", "test_eval_patterns.py", "test_advice.py", "test_stubborn.py", "test_modelpick.py", "test_votes.py", "test_corrections.py", "test_words_everywhere.py", "test_profiles.py", "test_followups.py", "test_dates.py", "test_voice.py", "test_ask_window.py", "test_guide.py", "test_partners.py", "test_scrolling.py", "test_working.py", "test_guides.py", "test_training.py", "test_shapes.py", "test_commands.py", "test_lookup.py", "test_learn.py", "test_memories.py", "test_memories_window.py", "test_updates.py", "test_access.py", "test_pageview.py", "test_runtime.py", "test_help.py", "test_nvda_stub.py",
	"test_ten.py", "test_ten_tools.py", "test_docformat.py", "test_shopping.py", "test_humancheck.py", "test_naming.py", "test_focus.py", "test_whole.py", "test_versions.py", "test_answers.py", "test_stream_answers.py", "test_scratchpad.py", "test_diagnose.py", "test_scratch_ways.py", "test_nvdalog.py", "test_skilllog.py",
	"test_appaccess.py", "test_focustools.py", "test_placing.py", "test_everyday_skills.py")


def main():
	failed = []
	# Every file of the add-on must at least compile.
	for path in glob.glob(os.path.join(ROOT, "addon", "**", "*.py"), recursive=True):
		try:
			py_compile.compile(path, doraise=True)
		except py_compile.PyCompileError as e:
			failed.append(os.path.relpath(path, ROOT))
			print(e.msg)
	for name in TESTS:
		result = subprocess.run([sys.executable, os.path.join(HERE, name)], cwd=HERE, capture_output=True, text=True)
		ok = result.returncode == 0 and result.stdout.strip().endswith("OK")
		print(f"{'passed' if ok else 'FAILED'}  {name}")
		if not ok:
			failed.append(name)
			print(result.stdout[-2000:], result.stderr[-3000:])
	if failed:
		sys.exit("Failed: " + ", ".join(failed))
	print("All tests passed.")


if __name__ == "__main__":
	main()
