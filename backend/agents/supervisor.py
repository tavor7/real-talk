"""
SupervisorAgent: Orchestrates conversation flow with optimized pipeline.
First turn: ProgramPlanner -> RAGQueryRephraser -> ScenarioArchitect -> ConversationPartner
Subsequent turns: ConversationPartner only (reuses generated scenario)
"""
from typing import Any
import json

from .planner import ProgramPlanner
from .scenario_architect import ScenarioArchitect
from .conversation_partner import ConversationPartner
from .llm_helper import call_llm, parse_json_from_llm, extract_answer_section


class SupervisorAgent:
    def __init__(self):
        self.planner = ProgramPlanner()
        self.scenario = ScenarioArchitect()
        self.conversation_partner = ConversationPartner()
    
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

    def run(self, prompt: str, context: dict[str, Any]) -> tuple[str, list[dict], str, dict]:
        """Run conversation pipeline.
        First turn: ProgramPlanner -> RAGQueryRephraser -> ScenarioArchitect -> ConversationPartner
        Subsequent turns: ConversationPartner only (reuses scenario from context)
        
        Returns: (final_response, steps, reply, generated_scenario)
        """
        all_steps = []
        user_profile = context.get("user_profile") or {}
        conversation_history = context.get("conversation_history") or []
        is_first_turn = not conversation_history
        
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
        else:
            # Continue conversation: respond to user's last message
            # Extract LAST user message from conversation history (now includes current prompt)
            user_messages = [m["content"] for m in conversation_history if m.get("role") == "user"]
            last_user = user_messages[-1] if user_messages else prompt
            print(f"[DEBUG] Conversation history length: {len(conversation_history)}")
            print(f"[DEBUG] Found {len(user_messages)} user messages in history")
            if user_messages:
                print(f"[DEBUG] First user message: {user_messages[0][:50] if user_messages[0] else '(empty)'}...")
                print(f"[DEBUG] Last user message (current prompt): {last_user[:50] if last_user else '(empty)'}...")
            partner_out, steps3 = self.conversation_partner.run(last_user, scenario_out, enhanced_context)
        
        all_steps.extend(steps3)
        reply = partner_out.get("reply", "Let's start! Say something casual.")

        # Final response
        if is_first_turn:
            final = f"[Scenario: {scenario_out.get('scenario', '')}]\n\n{reply}\n\nYour turn!"
        else:
            final = reply
        
        return final, all_steps, reply, scenario_out
