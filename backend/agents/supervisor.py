"""
SupervisorAgent: Orchestrates conversation flow with optimized pipeline.
First turn: ProgramPlanner -> RAGQueryRephraser -> ScenarioArchitect -> ConversationPartner
Subsequent turns (from 2nd): optionally CriticGate -> [Critic] -> ConversationPartner (reuses scenario)
"""
from typing import Any
import json

from .planner import ProgramPlanner
from .scenario_architect import ScenarioArchitect
from .conversation_partner import ConversationPartner
from .critic import SystemCritic
from .llm_helper import call_llm, parse_json_from_llm, extract_answer_section

# Pre-defined message when Critic decides to end the conversation
CRITIC_END_MESSAGE = "Alright, based on our conversation I think we should wrap it up here! See below for a quick evaluation of how you did and your level."

# Phrases that suggest the user may want to end (fast path: skip CriticGate LLM when none match)
END_PHRASES = (
    "goodbye", "bye", "see you", "see ya", "see u", "gotta go", "have to go", "got to go",
    "let's stop", "that's it", "talk later", "catch you", "i'm done", "we're done", "im done",
    "good night", "goodnight", "take care", "peace out", "peace", "later", "ttyl", "gtg",
    "g2g", "brb", "stop", "end", "finish", "enough", "that's all", "thats all",
)


class SupervisorAgent:
    def __init__(self):
        self.planner = ProgramPlanner()
        self.scenario = ScenarioArchitect()
        self.conversation_partner = ConversationPartner()
        self.critic = SystemCritic()
    
    def _rephrase_rag_query(self, scenario_hint: str, plan: dict, user_profile: dict) -> tuple[str, dict]:
        """Rephrase scenario hint + plan into an optimized RAG query for Reddit retrieval.
        Returns (rephrased_query, step_info) for logging."""
        learning_objective = plan.get("learning_objective", scenario_hint)
        key_vocabulary = plan.get("key_vocabulary", [])
        goals = user_profile.get("goals", "")
        
        vocab_str = ", ".join(key_vocabulary[:5]) if key_vocabulary else ""
        
        system = (
            "You are an expert at crafting search queries for retrieving authentic real-life conversations. \n\n"
            "Output only a concise, single-line, natural language search query optimized for finding relevant, informal conversations. "
            "At the end, add: ANSWER: {the search query}"
        )
        
        user = (
            f"Query subject: {scenario_hint}\n"
            f"Think step by step."
            f"At the end, extract: ANSWER: {{the search query}}"
        )
        
        response, full = call_llm(system, user, "RAGQueryRephraser")
        # Extract only the ANSWER section, discarding reasoning steps
        answer_only = extract_answer_section(response)
        rephrased_query = answer_only.strip() if answer_only else scenario_hint
        
        step_info = {
            "module": "RAGQueryRephraser",
            "prompt": {"system": system, "user": user},
            "response": full
        }
        
        return rephrased_query, step_info

    def _looks_like_farewell(self, last_user_message: str) -> bool:
        """Fast heuristic: True if the message might be ending the conversation (then we run CriticGate LLM)."""
        if not last_user_message or not last_user_message.strip():
            return False
        lower = last_user_message.strip().lower()
        # Very short message (1-4 words) that could be a sign-off
        words = lower.split()
        if len(words) <= 4 and any(p in lower for p in ("bye", "later", "peace", "stop", "done", "enough")):
            return True
        return any(phrase in lower for phrase in END_PHRASES)

    def _should_call_critic(
        self, scenario_hint: str, scenario_out: dict, last_user_message: str, conversation_history: list
    ) -> tuple[bool, list[dict]]:
        """Decide whether to invoke the Critic. Uses fast path: skip LLM when message clearly isn't a farewell."""
        # Fast path: if last message doesn't look like a farewell, skip CriticGate LLM (saves ~3-5s per turn)
        """
        if not self._looks_like_farewell(last_user_message):
            step_info = {"module": "CriticGate", "prompt": {"fast_path": True, "reason": "no farewell phrase"}, "response": "Skipped (fast path): reply via ConversationPartner only."}
            return False, [step_info]
        """
        # Otherwise run LLM to decide (user might be ending or diverging)
        scenario_desc = scenario_out.get("scenario", scenario_hint) or scenario_hint
        history_str = "\n".join(
            f"{m.get('role', '')}: {m.get('content', '')}" for m in conversation_history[-4:]
        )
        system = (
            "You are a conversation monitor. Output ONLY valid JSON: call_critic (boolean), reason (string).\n"
            "Set call_critic TRUE only if the user is clearly ending the conversation (goodbye, bye, leaving) or conversation clearly off-topic.\n"
            "Otherwise FALSE. At the end add: ANSWER: {json}"
        )
        user = (
            f"Scenario: {scenario_desc}\nLast user message: \"{last_user_message}\"\nRecent:\n{history_str}\n\n"
            "Call Critic? ANSWER: {\"call_critic\": true/false, \"reason\": \"...\"}"
        )
        response, full = call_llm(system, user, "CriticGate")
        step_info = {"module": "CriticGate", "prompt": {"system": system, "user": user}, "response": full}
        answer_only = extract_answer_section(response)
        out = parse_json_from_llm(answer_only)
        call_critic = bool(out.get("call_critic", False))
        return call_critic, [step_info]

    def run(self, prompt: str, context: dict[str, Any]) -> tuple[str, list[dict], str, dict, bool]:
        """Run conversation pipeline.
        First turn: ProgramPlanner -> RAGQueryRephraser -> ScenarioArchitect -> ConversationPartner
        Subsequent turns: CriticGate -> [Critic if needed] -> ConversationPartner (reuses scenario)
        
        Returns: (final_response, steps, reply, generated_scenario, conversation_ended_by_critic)
        """
        all_steps = []
        user_profile = context.get("user_profile") or {}
        conversation_history = context.get("conversation_history") or []
        is_first_turn = not conversation_history
        conversation_ended_by_critic = False

        # Determine scenario: use explicit scenario if provided, otherwise use user prompt
        scenario_hint = context.get("scenario") or prompt

        # ADD CURRENT USER PROMPT TO CONVERSATION HISTORY (for subsequent turns)
        if not is_first_turn and prompt:
            conversation_history = list(conversation_history)  # Make a copy to avoid mutating original
            conversation_history.append({"role": "user", "content": prompt})
            print(f"[DEBUG] Added current prompt to conversation_history. New length: {len(conversation_history)}")

        # Build enhanced context for all agents
        enhanced_context = {
            **context,
            "user_profile": user_profile,
            "conversation_history": conversation_history,
            "scenario": scenario_hint,
        }

        # FIRST TURN ONLY: Run planning agents to create scenario
        if is_first_turn:
            # 1. ProgramPlanner with full context (user profile, scenario, conversation history)
            plan, steps1 = self.planner.run(prompt, enhanced_context)
            all_steps.extend(steps1)

            # 2. RAGQueryRephraser: optimize scenario hint + plan into a better search query
            rephrased_rag_query, rag_step = self._rephrase_rag_query(scenario_hint, plan, user_profile)
            all_steps.append(rag_step)

            # Add rephrased query to context so ScenarioArchitect uses it
            enhanced_context["rephrased_rag_query"] = rephrased_rag_query

            # 3. ScenarioArchitect with plan details, scenario, and optimized RAG query
            scenario_out, steps2 = self.scenario.run(plan, user_profile, scenario_hint, enhanced_context)
            all_steps.extend(steps2)
            scenario_out.setdefault("scenario", "Casual conversation")

            # Store the generated scenario in context for future turns
            enhanced_context["generated_scenario"] = scenario_out
        else:
            # SUBSEQUENT TURNS: Reuse scenario from context (passed from routes.py via Supabase or frontend)
            scenario_out = context.get("generated_scenario") or {"scenario": "Casual conversation"}
            enhanced_context["generated_scenario"] = scenario_out

        # EVERY TURN: ConversationPartner generates response based on scenario
        if is_first_turn:
            # Start conversation: generate opening line based on scenario
            partner_out, steps3 = self.conversation_partner.run("", scenario_out, enhanced_context, is_first_turn=True)
            all_steps.extend(steps3)
            reply = partner_out.get("reply", "Let's start! Say something casual.")
            final = reply
            return final, all_steps, reply, scenario_out, False

        # SUBSEQUENT TURNS (from 2nd): Gate -> optionally Critic -> ConversationPartner
        user_messages = [m["content"] for m in conversation_history if m.get("role") == "user"]
        last_user = user_messages[-1] if user_messages else prompt
        print(f"[DEBUG] Conversation history length: {len(conversation_history)}")
        print(f"[DEBUG] Found {len(user_messages)} user messages in history")

        # Gate: CriticGate decides on every user message whether to invoke the Critic
        call_critic, gate_steps = self._should_call_critic(
            scenario_hint, scenario_out, last_user, conversation_history
        )
        all_steps.extend(gate_steps)

        if call_critic:
            # Critic decides: end conversation or continue with feedback
            scenario_desc = scenario_out.get("scenario", scenario_hint) or scenario_hint
            critic_result, critic_steps = self.critic.run(
                scenario_desc, conversation_history, last_user, enhanced_context
            )
            all_steps.extend(critic_steps)

            if critic_result.get("end_conversation"):
                # End: pre-defined message and signal so routes call UserEvaluation
                conversation_ended_by_critic = True
                reply = CRITIC_END_MESSAGE
                final = reply
                return final, all_steps, reply, scenario_out, conversation_ended_by_critic

            # Continue: pass Critic feedback to ConversationPartner
            feedback = (critic_result.get("feedback") or "").strip()
            if feedback:
                enhanced_context["critic_feedback"] = feedback

        # Generate reply (with optional critic_feedback in context)
        partner_out, steps3 = self.conversation_partner.run(last_user, scenario_out, enhanced_context)
        all_steps.extend(steps3)
        reply = partner_out.get("reply", "Let's start! Say something casual.")
        final = reply

        return final, all_steps, reply, scenario_out, conversation_ended_by_critic
