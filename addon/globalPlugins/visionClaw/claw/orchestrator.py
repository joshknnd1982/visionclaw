# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the orchestration layer. Runs one request from start to finish:
# break it into bite-size steps, choose how hard to think, get both models to agree, run the steps one at a
# time, check the result, tell the user what really happened, and remember what was learned.
# No NVDA dependencies.

from . import agent, consensus, debuglog, lookup, planner, policy, shapes
from . import task as taskModule
from .catalog import CODER, VISION
from .llm import LLM, LLMError, clip, plainSpeech
from .runtime import ModelMissing
from .tools import ANSWER, SUMMARIZE, VERBATIM
from ..engine import EngineError

_ANSWER_SYSTEM = (
	"You are VisionClaw, an assistant inside the NVDA screen reader. Answer the user from the information given. "
	"They are blind and will hear your words spoken, so use short, plain sentences and no lists or symbols.\n"
	"Rules: Use only the information given; never add anything that is not in it. "
	"Answer exactly what the user asked. Information may come in several pieces that say where they are from; "
	"use the pieces that are about the question and leave out the others. Each numbered piece stands alone: "
	"never put steps from two pieces together into one way of doing something. "
	"If it names keys for a command, say the keys. If the information does not answer the question, say that "
	"you could not find it. Do not mention tools, steps, forms or models. Do not say that anything was changed."
)
_PICK_SYSTEM = (
	"You are VisionClaw, an assistant inside the NVDA screen reader. You are given what a user asked and some "
	"numbered lines that were looked up. You choose the one line that answers the user best, by its number."
)
_VERIFY_SCHEMA = {
	"type": "object",
	"properties": {"done": {"type": "boolean"}, "missing": {"type": "string", "maxLength": 200}},
	"required": ["done", "missing"],
}
_VERIFY_SYSTEM = (
	"You check finished work for an assistant inside the NVDA screen reader. Compare the request with the results. "
	"Say done=true if the request was carried out or answered. Say done=false only if a clear part of the request "
	"was not done, and name that part in missing. Judge only from the results; do not guess."
)
SKIP, RETRY, STOP = 0, 1, 2


class Orchestrator:
	"""runtime: the two models, or one model that does both jobs. registry: the tools.
	askUser(question, choices) returns the index the user chose, or None.
	situation() returns a short text about where the user is (app, window, focused control), or "".
	memory: lessons from earlier tasks, or None."""

	def __init__(self, runtime, registry, askUser, situation=None, memory=None, lead=policy.LEAD,
			other=policy.OTHER):
		self.runtime = runtime
		self.registry = registry
		self.askUser = askUser
		self.situation = situation or (lambda: "")
		self.memory = memory
		self.lead = lead
		self.other = other
		# The user's choice of whether the models are asked one small question at a time: auto, always, never.
		self.stepwise = lambda: policy.AUTO

	def _oneByOne(self):
		try:
			return policy.stepwise(self.stepwise(), self.runtime.entry(self.lead))
		except Exception:
			return False

	def run(self, task):
		"""Carry out a task. Never raises: the outcome is in task.state and task.answer."""
		debuglog.log("task", f"New request: {task.request!r}. Reasoning setting: {task.reasoning}.")
		try:
			self._run(task)
		except taskModule.Cancelled:
			task.setState(taskModule.CANCELLED, "Stopped.")
		except consensus.Declined:
			task.setState(taskModule.CANCELLED, "Cancelled. Nothing was changed.")
		except ModelMissing as e:
			task.missing = e.role
			task.emit(taskModule.ERROR, f"The {policy.ROLE_NAMES[e.role]} has not been downloaded yet.")
			task.setState(taskModule.FAILED, "A model is missing.")
		except EngineError as e:
			if task.cancel.is_set():
				task.setState(taskModule.CANCELLED, "Stopped.")
			else:
				debuglog.error("task", "The engine failed during the request", e)
				task.emit(taskModule.ERROR, f"The task could not be finished: {e}")
				task.setState(taskModule.FAILED, "The task failed.")
		except Exception as e:  # a bug must be reported to the user, not left as silence
			debuglog.error("task", "A fault inside VisionClaw ended the request", e)
			task.emit(taskModule.ERROR, (
				f"VisionClaw ran into a problem: {type(e).__name__}: {e}"
				+ (" Where it happened is written in VisionClaw's log." if debuglog.on() else "")))
			task.setState(taskModule.FAILED, "The task failed.")
			raise
		finally:
			debuglog.log("task", (
				f"Request ended as {task.state} after {task.seconds()} seconds. "
				f"Steps: {[(step.tool, step.status) for step in task.steps]}. Answer: {task.answer!r}"))
		return task

	# --- The stages ---

	def _run(self, task):
		for role in (VISION, CODER):
			if not self.runtime.hasModel(role):
				raise ModelMissing(role)
		llm = LLM(self.runtime, task)
		request = " ".join(task.request.split())

		task.setState(taskModule.UNDERSTANDING, "Understanding your request.")
		# A first idea of how hard this is, from its words; corrected once the plan is known.
		small = self._oneByOne()
		# One model for both jobs: then nothing may be called an agreement between two models.
		one = policy.isOneModel(self.runtime)
		params = task.params = policy.select(planner.quickTriage(request), task.reasoning)._replace(
			oneByOne=small, oneModel=one)
		context = self._context(request)
		steps, how, recipes = consensus.agree(
			llm, task, request, context, self.registry, params, self.askUser, self.lead, self.other)
		task.steps = steps
		params = task.params = policy.select(
			{"complexity": planner.complexity(recipes), "needs_code": "write_addon" in recipes}, task.reasoning,
		)._replace(oneByOne=small, oneModel=one)
		if one:
			task.emit(taskModule.DETAIL, "One model does both jobs here. It chooses what to do, and it checks its own work.")
		if small:
			task.emit(taskModule.DETAIL, "The model is asked one small question at a time, and answers are quoted from what was looked up.")
		task.emit(taskModule.DETAIL, (
			f"Parts of the request: {', '.join(recipes)}. Reasoning level: {params.reasoning}."
		))
		agreed = {
			consensus.AGREED: "The plan is ready" if one else "Both models agree on the plan",
			consensus.REVISED: "The model corrected its plan" if one else "Both models agree on a corrected plan",
			consensus.USER_CHOSE: "Using the plan you chose",
		}[how]
		task.setState(taskModule.WORKING, f"{agreed}: {len(steps)} steps.")

		# Every model has been used by now, so each has its place.
		where = getattr(self.runtime, "whereText", lambda: "")()
		if where:
			task.emit(taskModule.DETAIL, where)

		self._runSteps(llm, task, request, params)
		answer = self._answer(llm, task, request, params)
		# A plan the model wrote itself is checked by the other model; recipes report their own failures.
		if params.verify and planner.OTHER in recipes and not self._allFailed(task):
			answer = self._verify(llm, task, request, params, answer)

		self._learn(task)
		task.answer = answer
		task.emit(taskModule.ANSWER, answer)
		task.setState(taskModule.DONE, "Finished.")

	def _context(self, request):
		parts = []
		try:
			where = self.situation()
		except Exception:
			where = ""
		if where:
			parts.append(where)
		if self.memory is not None:
			lessons = self.memory.search(request)
			if lessons:
				parts.append("Lessons from earlier tasks:\n" + "\n".join(f"- {text}" for text in lessons))
		return "\n".join(parts)

	def _runSteps(self, llm, task, request, params, start=0):
		replans = params.replans
		index = start
		while index < len(task.steps):
			task.check()
			steps = task.steps
			step = steps[index]
			if step.tool == ANSWER:
				break  # always last; written by _answer
			# A step whose groundwork failed cannot work either: clicking needs the list of items.
			needs = self.registry.get(step.tool).before
			if needs and any(
					s.tool == needs and s.part == step.part and s.status in (taskModule.STEP_FAILED, taskModule.SKIPPED)
					for s in steps[:index]):
				step.status, step.result = taskModule.SKIPPED, "The step before it did not work."
				index += 1
				continue
			task.current = index
			task.emit(taskModule.STEP, f"Step {index + 1} of {len(steps)}: {step.title}.")
			worked = agent.runStep(llm, task, self.registry, request, steps, index, params, self.lead, self.other)
			if not worked:
				choice = self._onFailure(task, step)
				if choice == RETRY:
					step.status = taskModule.PENDING
					continue
				if choice == STOP:
					raise taskModule.Cancelled()
				step.status = taskModule.SKIPPED
			# After finding something out, the rest of a plan the model wrote itself may no longer fit.
			remaining = [s for s in steps[index + 1:] if s.tool != ANSWER]
			if (worked and replans and remaining and self.registry.get(step.tool).looks
					and all(s.recipe is None for s in remaining)):
				replans -= 1
				self._rethink(llm, task, request, index, params)
			index += 1

	def _onFailure(self, task, step):
		task.setState(taskModule.WAITING, f"A step did not work: {step.title}. Waiting for your choice.")
		question = (
			f"This step did not work: {step.title}. The problem: {clip(step.result, 300)} What should VisionClaw do?"
		)
		choice = self.askUser(question, ["Skip this step and go on", "Try this step again", "Stop the task"])
		task.check()
		task.setState(taskModule.WORKING, "Going on.")
		return STOP if choice is None else choice

	def _rethink(self, llm, task, request, index, params):
		steps = task.steps
		remaining = steps[index + 1:]
		try:
			changed = planner.rethink(
				llm, self.lead, request, agent.resultsText(steps, index + 1), remaining, self.registry, params)
			if changed is None or planner.planText(changed) == planner.planText(remaining):
				return
			# A changed plan needs the other model's agreement too; without it the agreed plan stays.
			agrees, problem = consensus.review(llm, self.other, request, steps[:index + 1] + changed, self.registry, params)
		except LLMError:
			return
		if not agrees and params.oneModel:
			task.emit(taskModule.TALK, (
				"The model wanted to change the rest of the plan, but on checking the change it found a problem: "
				f"{problem} Keeping the plan."
			))
			return
		if not agrees:
			task.emit(taskModule.TALK, (
				f"The {policy.ROLE_NAMES[self.lead]} wanted to change the rest of the plan, but the "
				f"{policy.ROLE_NAMES[self.other]} did not agree: {problem} Keeping the agreed plan."
			))
			return
		task.steps = steps[:index + 1] + changed
		task.emit(taskModule.TALK, (
			"The model changed the rest of the plan:\n" if params.oneModel
			else "Both models agreed to change the rest of the plan:\n") + planner.planText(task.steps))
		task.emit(taskModule.STATE, f"The plan changed after looking. Now {len(task.steps)} steps.")

	@staticmethod
	def _work(task):
		return [s for s in task.steps if s.tool != ANSWER]

	def _allFailed(self, task):
		work = self._work(task)
		return bool(work) and not any(s.status == taskModule.STEP_DONE for s in work)

	def _outcome(self, task):
		"""What really happened, taken from the steps:
		(sentences for the user as they are, information a model must put in words, what could not be done)."""
		told, info, failed = [], [], []
		task.infoTools = []
		work = self._work(task)
		for i, step in enumerate(work):
			lastOfPart = i + 1 == len(work) or work[i + 1].part != step.part
			if step.status in (taskModule.STEP_FAILED, taskModule.SKIPPED):
				what = step.part or step.title
				if what not in failed:
					failed.append(what)
				continue
			if step.status != taskModule.STEP_DONE:
				continue
			tool = self.registry.get(step.tool)
			if tool.tell == SUMMARIZE and lastOfPart and lookup.isNothing(step.result):
				# Nothing that was looked up is about the question: plain code says so, as it is. A model
				# that is handed nothing makes something up.
				told.append(step.result)
			elif tool.tell == VERBATIM and (tool.changes or lastOfPart):
				# Two parts answered by the same look are said once: "how big is the model, and is it loaded".
				if tool.changes or step.result not in told:
					told.append(step.result)
			elif tool.tell == SUMMARIZE and lastOfPart:
				info.append((step.part or task.request, step.result))
				task.infoTools.append(step.tool)
		return told, info, failed

	def _answer(self, llm, task, request, params):
		"""Tell the user the result. What tools did is said in the tools' own words, so nothing is claimed that
		did not happen; only information that was looked up is put into words by a model."""
		task.check()
		steps = task.steps
		last = len(steps) - 1
		task.current = last
		task.emit(taskModule.STEP, f"Step {last + 1} of {len(steps)}: {steps[last].title}.")
		told, info, failed = self._outcome(task)
		pieces = list(told)
		if info and params.oneByOne:
			# A very small model is not asked to put what was found into its own words: it makes things up.
			pieces += [self._quoted(llm, part, result, tool) for (part, result), tool in zip(info, task.infoTools)]
		elif info:
			user = "\n\n".join(
				f"The user asked: \"{clip(part, 300)}\"\nInformation found:\n{clip(lookup.numbered(result), 1200)}"
				for part, result in info) + (
					"\n\nAnswer each of these questions, in order." if len(info) > 1 else "\n\nAnswer the user.")
			try:
				summary = llm.text(self.lead, _ANSWER_SYSTEM, user, maxTokens=params.answerTokens, reasoning=params.reasoning)
			except LLMError:
				summary = ""
			pieces.append(" ".join((summary or "").split()) or " ".join(result for _part, result in info))
		if failed:
			pieces.append("This could not be done: " + "; ".join(clip(f, 120) for f in failed) + ".")
		answer = " ".join(plainSpeech(p) for p in pieces if p) or "Nothing was done."
		steps[last].status, steps[last].result = taskModule.STEP_DONE, answer
		return answer

	def _quoted(self, llm, part, result, toolName):
		"""An answer made of what was looked up, word for word: the line that mentions what was asked. Plain
		code finds the lines; where there are several, the model only chooses among them."""
		if toolName in shapes.AS_IS:
			return clip(result, 700)
		if toolName == lookup.TOOL:
			# Already ranked by plain code, the best first: nothing is left for a model to choose.
			return clip(lookup.quoted(result), 800)
		lines, _asked = shapes.quote(part, result)
		if not lines:
			return shapes.notMentioned(part)
		chosen = 0
		if len(lines) > 1:
			numbered = "\n".join(f"{number}. {clip(line, 240)}" for number, line in enumerate(lines, 1))
			try:
				chosen = int(llm.json(
					self.lead, _PICK_SYSTEM,
					f"The user asked: \"{clip(part, 300)}\"\nLines found:\n{numbered}\nWhich line answers what the user asked? Give its number.",
					{"type": "object", "properties": {"line": {"type": "integer", "enum": list(range(1, len(lines) + 1))}},
						"required": ["line"]}, maxTokens=20).get("line") or 1) - 1
			except (LLMError, TypeError, ValueError):
				chosen = 0
		return clip(lines[max(0, min(len(lines) - 1, chosen))], 500)

	def _verify(self, llm, task, request, params, answer):
		"""The other model checks the result; with one model for both jobs, that model does, with the checker's
		question. If a part is missing, a few more steps are planned and run, once."""
		task.setState(taskModule.CHECKING, "Checking the result.")
		results = agent.resultsText(task.steps, len(task.steps))
		user = f"Request: \"{clip(request, 600)}\"\nResults:\n{clip(results, 1500)}\nWas the request carried out?"
		try:
			found = llm.json(self.other, _VERIFY_SYSTEM, user, _VERIFY_SCHEMA, maxTokens=100, reasoning=params.reasoning)
		except LLMError:
			return answer
		missing = " ".join(str(found.get("missing") or "").split())
		checker = policy.roleName(self.other, params.oneModel)
		if found.get("done") or not missing:
			task.emit(taskModule.TALK, f"The {checker} checked the result: complete.")
			return answer
		task.emit(taskModule.TALK, f"The {checker} checked the result: still missing: {missing}")
		try:
			extra, _recipes = planner.plan(llm, self.lead, missing, "", self.registry, params)
			agrees, _problem = consensus.review(llm, self.other, missing, extra, self.registry, params)
		except LLMError:
			agrees, extra = False, []
		if not agrees or len(extra) < 2:
			return answer + f" One part may not be complete: {missing}"
		task.emit(taskModule.TALK, (
			"Steps for the missing part:\n" if params.oneModel
			else "Both models agreed on steps for the missing part:\n") + planner.planText(extra))
		done = self._work(task)
		task.steps = done + extra
		task.setState(taskModule.WORKING, f"Doing the missing part: {len(extra) - 1} more steps.")
		self._runSteps(llm, task, request, params, start=len(done))
		return self._answer(llm, task, request, params)

	def _learn(self, task):
		if self.memory is None:
			return
		for step in task.steps:
			if step.lesson:
				self.memory.add(step.lesson, topic=task.request[:120])
