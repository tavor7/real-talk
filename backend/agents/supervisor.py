"""
SupervisorAgent: Orchestrates flow, decides which sub-agent to invoke, aggregates response.
"""
from typing import Any

from .planner import ProgramPlanner
from .scenario_architect import ScenarioArchitect
from .user_evaluation import UserEvaluation
from .critic import SystemCritic


class SupervisorAgent:
    def __init__(self):
        self.planner = ProgramPlanner()
        self.scenario = ScenarioArchitect()
        self.user_eval = UserEvaluation()
        self.critic = SystemCritic()

    def run(self, prompt: str, context: dict[str, Any]) -> tuple[str, list[dict]]:
        """Run: ProgramPlanner -> ScenarioArchitect -> UserEvaluation (first line) -> SystemCritic. Aggregate steps."""
        all_steps = []
        user_profile = context.get("user_profile") or {}
        scenario_hint = context.get("scenario") or prompt
        conversation_history = context.get("conversation_history") or []

        # 1. ProgramPlanner
        plan, steps1 = self.planner.run(prompt, context)
        all_steps.extend(steps1)

        # 2. ScenarioArchitect
        scenario_out, steps2 = self.scenario.run(plan, user_profile, scenario_hint, context)
        all_steps.extend(steps2)
        scenario_out.setdefault("scenario", "Casual conversation")
        scenario_out.setdefault("dialogue_seed", ["Hey! What's up?"])

        # 3. UserEvaluation: first agent reply (seed or response to user)
        ctx = {**context, "user_profile": user_profile, "conversation_history": conversation_history}
        if not conversation_history:
            # Start conversation: generate opening line that fits scenario + user profile (no generic "Hey! What's up?")
            eval_out, steps3 = self.user_eval.run("", scenario_out, ctx, is_first_turn=True)
        else:
            last_user = next((m["content"] for m in reversed(conversation_history) if m.get("role") == "user"), prompt)
            eval_out, steps3 = self.user_eval.run(last_user, scenario_out, ctx)
        all_steps.extend(steps3)
        reply = eval_out.get("reply", "Let's start! Say something casual.")

        # 4. SystemCritic
        dialogue_for_critic = list(conversation_history)
        if conversation_history:
            dialogue_for_critic.append({"role": "user", "content": prompt or "..."})
        dialogue_for_critic.append({"role": "assistant", "content": reply})
        critic_out, steps4 = self.critic.run(dialogue_for_critic, context)
        all_steps.extend(steps4)

        # Final response
        if not conversation_history:
            final = f"[Scenario: {scenario_out.get('scenario', '')}]\n\n{reply}\n\nYour turn!"
        else:
            final = reply
        if eval_out.get("summary"):
            final = f"{final}\n\n[Summary] {eval_out['summary']}"
        if critic_out.get("summary"):
            final = f"{final}\n\n[Summary] {critic_out['summary']}"
        return final, all_steps, reply
