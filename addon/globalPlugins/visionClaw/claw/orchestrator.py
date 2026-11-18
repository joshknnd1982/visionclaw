# Copyright (C) 2026 Josh Kennedy
# This file is licensed under the GNU General Public License, version 2 or later.
# See LICENSE for the full terms.

# VisionClaw - the orchestration layer. Runs one request from start to finish:
# break it into bite-size steps, choose how hard to think, get both models to agree, run the steps one at a
# time, check the result, tell the user what really happened, and remember what was learned.
# No NVDA dependencies.

from . import agent, consensus, debuglog, lookup, pageview, planner, policy, prompts, shapes
from . import memories as memoriesModule
from . import skills as skillsModule
from . import task as taskModule
from .catalog import CODER, VISION
from .llm import LLM, LLMError, clip, plainSpeech
from .runtime import ModelMissing
from .tools import ANSWER, SUMMARIZE, VERBATIM
from ..engine import EngineError

# The task of an answer. Who the user is and how an answer is worded come from prompts.speaking, which the user
# can rewrite; these rules stay, because they keep the answer to what really happened.
_ANSWER_TASK = (
	"You are VisionClaw, an assistant inside the NVDA screen reader. Answer the user from the information given.\n"
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
# For a model that is not one of the very smallest: it may also say that no line answers the question. A very
# small model is never given that choice; it takes it at random.
_JUDGE_SYSTEM = (
	prompts.IDENTITY + " You are given what the user asked, where they are, and numbered lines that were looked up. Choose the line that tells the user "
	"how to do what they asked or answers their question, by its number. A line that is about something else, "
	"even if it shares words with the question, does not answer it. If no line answers the question, choose 0."
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
	memory: lessons from earlier tasks, or None.
	Set after it is made: memories, the user's own memories (claw/memories.py), or None; program() gives the
	program in front; remembering() says when memories may be kept without being asked (memories.WHEN)."""

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
		self.memories = None
		# offer(request, recipes) gives a sentence about what can be downloaded, or ""; set by the add-on.
		self.offer = None
		self.program = lambda: ""
		self.remembering = lambda: memoriesModule.AUTO
		# The skills: VisionClaw's own and the user's (claw/skills.py), or None.
		self.skills = None
		# facts() gives where the user is as plain facts for the router (router.WEB and so on); set by the add-on.
		self.facts = lambda: {}

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
		# Where the user is, as plain facts for the router (claw/router.py). Unknown hides nothing.
		try:
			task.facts = dict(self.facts() or {})
		except Exception as e:
			debuglog.error("router", "Where the user is could not be found out for the router", e)
			task.facts = {}
		# The skills that fit the request, chosen by plain code from its words. One with steps of its own, whose
		# starting words the request has word for word, is the plan: the user's own, or one VisionClaw ships.
		task.skills = self._chooseSkills(task, request)
		ownPlan = skillsModule.planned(task.skills, request)
		found = self._skillPlan(task, ownPlan, request) if ownPlan is not None else None
		if found is not None:
			steps, how, recipes = found
		else:
			steps, how, recipes = consensus.agree(
				llm, task, request, context, self.registry, params, self.askUser, self.lead, self.other)
		task.steps = steps
		# Only the skills that speak about a step of this plan are kept and named: "turn off the game skill"
		# has the word game, but the game skill says nothing about turning a skill off.
		task.skills = [skill for skill in task.skills
			if planner.OTHER in recipes or any(skillsModule.applies(skill, recipe) for recipe in recipes)]
		if task.skills:
			task.emit(taskModule.DETAIL, "Skills used: " + "; ".join(skill.name for skill in task.skills) + ".")
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
		}.get(how) or f"Following the skill {ownPlan.name}"
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
		kept = self._keep(task)
		if kept:
			answer = f"{answer.rstrip()}\n{kept}" if answer else kept
		# One sentence, said once, that something which fits this request can be downloaded (claw/offers.py).
		offered = self._offered(task, request, recipes)
		if offered:
			answer = f"{answer.rstrip()}\n{offered}" if answer else offered
		task.answer = answer
		task.emit(taskModule.ANSWER, answer)
		task.setState(taskModule.DONE, "Finished.")

	def _chooseSkills(self, task, request):
		"""The skills that fit a request, by its words. A skill only helps, so a fault here never ends the request."""
		if self.skills is None:
			return []
		try:
			return self.skills.choose(request)
		except Exception as e:
			debuglog.error("skills", "The skills could not be chosen", e)
			return []

	def _skillPlan(self, task, skill, request):
		"""The steps a skill sets out, each a proven recipe given the skill's own words for it, or None when none
		of its recipes can be used here. Returns (steps, how, recipes)."""
		available = planner.available(self.registry)
		steps, recipes = [], []
		for recipe, words in skill.steps:
			if recipe in available:
				steps += planner.recipeSteps(recipe, words or request, self.registry)
				recipes.append(recipe)
		if not steps:
			return None
		task.emit(taskModule.TALK, (
			f"\"{request}\": following the skill {skill.name}, step by step as it is written: "
			+ "; ".join(planner.label(recipe) for recipe in recipes) + "."))
		return steps + [planner.answerStep()], "skill", recipes

	def _helpWanted(self):
		"""What the user asked to be remembered about how much help an answer gives; a fault never ends the
		request, because this only helps."""
		if self.memories is None:
			return []
		try:
			return self.memories.helpWanted()
		except Exception as e:
			debuglog.error("memories", "The memories about answers could not be read", e)
			return []

	def _context(self, request):
		parts = []
		try:
			where = self.situation()
		except Exception:
			where = ""
		if where:
			parts.append(where)
		if self.memories is not None:
			try:
				mine = self.memories.recall(request, self.program())
			except Exception as e:
				debuglog.error("memories", "The memories could not be read for the request", e)
				mine = []
			if mine:
				debuglog.log("memories", f"Given with the request: {mine}")
				parts.append("The user asked VisionClaw to remember:\n" + "\n".join(f"- {text}" for text in mine))
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
			# A step that depends on a check is done only if the check said so; if the check itself did not work,
			# nobody knows, and the step is left out as one that could not be done.
			gate = step.onlyIf
			if gate is not None and gate.status != taskModule.STEP_DONE:
				step.status, step.result = taskModule.SKIPPED, "What it depends on could not be checked."
				index += 1
				continue
			if gate is not None and not gate.holds:
				step.status, step.result = taskModule.NOT_NEEDED, "What it depends on did not hold."
				index += 1
				continue
			# A step whose groundwork failed cannot work either: clicking needs the list of items.
			needs = self.registry.get(step.tool).before
			if needs and any(
					s.tool == needs and s.part == step.part and s.status in (taskModule.STEP_FAILED, taskModule.SKIPPED)
					for s in steps[:index]):
				step.status, step.result = taskModule.SKIPPED, "The step before it did not work."
				index += 1
				continue
			task.current = index
			# What the chosen skills say about this kind of step, for the models that work on it.
			step.guide = skillsModule.guide(getattr(task, "skills", ()), step.recipe)
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
			if worked and step.test is not None:
				step.holds = bool(step.test(step.result))
				task.emit(taskModule.DETAIL, "That holds, so what depends on it is done." if step.holds
					else "That does not hold, so what depends on it is left out.")
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
			if step.status == taskModule.NOT_NEEDED:
				# Said once for each thing that was left out, right after what the check found.
				note = f"So this was not done: {clip(step.part or step.title, 120)}."
				if note not in told:
					told.append(note)
				continue
			if step.status != taskModule.STEP_DONE:
				continue
			if step.test is not None:
				# A check's answer is told in plain code's own words, whatever its tool usually does with a result.
				told.append(step.said(step.result, step.holds) if step.said else step.result)
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
			guide = skillsModule.guide(getattr(task, "skills", ()), anyRecipe={s.recipe for s in self._work(task)})
			if guide:
				user += f"\n{guide}"
			# How much help the user said they want, kept among their memories, goes with every answer.
			wanted = self._helpWanted()
			if wanted:
				user += "\nThe user asked VisionClaw to remember this about answers:\n" + "\n".join(f"- {line}" for line in wanted)
			try:
				summary = llm.text(self.lead, prompts.speaking(_ANSWER_TASK, found=user), user, maxTokens=params.answerTokens, reasoning=params.reasoning)
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
			# Already ranked by plain code, the best first. A very small model is given nothing to choose; a
			# capable one says which of the few lines answers the question, knowing where the user is.
			picked = self._pick(llm, part, lookup.pickable(result))
			if picked is None:
				# The model read what was found and says none of it answers. That is said, with the nearest
				# thing marked as what it is, instead of being given as the answer.
				return f"{lookup.NO_ANSWER} {clip(lookup.quoted(result), 420)}"
			return clip(lookup.quoted(result, picked), 800)
		if toolName == "read_page" and pageview.asksGist(part):
			# "Summarize this page" asks for no line of the page but for all of it in short. A model that must not
			# put things into its own words gets the beginning of each part, word for word, from plain code.
			gist = pageview.gist(result)
			if gist:
				return gist
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

	def _pick(self, llm, part, lines):
		"""The line that answers a question, chosen by a model that is not one of the very smallest, which
		also says when none does: then None. "" when there is nothing to choose or nobody to choose."""
		try:
			entry = self.runtime.entry(self.lead) or {}
		except Exception:
			entry = {}
		if not lines or entry.get("suggest") is False:
			return ""
		try:
			where = self.situation()
		except Exception:
			where = ""
		numbered = "\n".join(f"{number}. {clip(line, 300)}" for number, line in enumerate(lines, 1))
		user = f"The user asked: \"{clip(part, 300)}\"\n" + (f"Where the user is: {clip(where, 300)}\n" if where else "") + (
			f"Lines found:\n{numbered}\nWhich line answers what the user asked? Give its number, or 0 if none does.")
		try:
			chosen = int(llm.json(self.lead, _JUDGE_SYSTEM, user, {
				"type": "object", "properties": {"line": {"type": "integer", "enum": list(range(0, len(lines) + 1))}},
				"required": ["line"]}, maxTokens=20).get("line"))
		except (LLMError, TypeError, ValueError):
			return ""
		if chosen == 0:
			return None
		return lines[chosen - 1] if 1 <= chosen <= len(lines) else ""

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

	def _offered(self, task, request, recipes):
		"""What the user is told once about what can be downloaded, after a request that it fits and that was
		done; "" when there is nothing to say. Plain code decides, and a fault never ends the request."""
		if self.offer is None or self._allFailed(task):
			return ""
		try:
			said = self.offer(request, [recipe for recipe in recipes if recipe]) or ""
		except Exception as e:
			debuglog.error("offers", "What can be downloaded could not be offered", e)
			return ""
		if said:
			debuglog.log("offers", f"Said once after {request!r}: {said!r}")
		return said

	def _keep(self, task):
		"""Keeps what the user said about themselves or how they like things done, when nothing else in the
		request kept it and they allow it; returns the sentence that tells them, or "". Plain code decides; a
		memory never ends a request."""
		if self.memories is None:
			return ""
		try:
			when = self.remembering()
			steps = [(step.tool, step.status == taskModule.STEP_DONE) for step in task.steps]
			fact = memoriesModule.worthKeeping(task.request, when, steps, self._changes)
			if not fact:
				return ""
			entry, replaced = self.memories.add(fact, asked=fact, program="")
		except Exception as e:
			debuglog.error("memories", "A memory could not be kept", e)
			return ""
		return (
			f"VisionClaw will remember this: {entry.text()}"
			+ (" It replaces what it remembered before about the same thing." if replaced else "")
			+ " To make it forget, say forget that.")

	def _changes(self, tool):
		try:
			return bool(self.registry.get(tool).changes)
		except Exception:
			return False

	def _learn(self, task):
		if self.memory is None:
			return
		for step in task.steps:
			if step.lesson:
				self.memory.add(step.lesson, topic=task.request[:120])
