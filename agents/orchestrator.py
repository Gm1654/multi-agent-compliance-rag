"""Orchestrator agent: classify queries and route to specialist agents."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from agents.auditor_agent import run_auditor
from agents.llm_client import generate_json
from agents.researcher_agent import run_researcher
from agents.troubleshooter_agent import run_troubleshooter

AgentName = Literal["researcher", "auditor", "troubleshooter"]


@dataclass
class OrchestratorPlan:
    query: str
    agents: list[AgentName]
    reasoning: str
    proposed_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrchestratorResult:
    query: str
    plan: OrchestratorPlan
    researcher: dict[str, Any] | None = None
    auditor: dict[str, Any] | None = None
    troubleshooter: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "plan": self.plan.to_dict(),
            "researcher": self.researcher,
            "auditor": self.auditor,
            "troubleshooter": self.troubleshooter,
        }


def classify_query(query: str) -> OrchestratorPlan:
    prompt = f"""You are an orchestrator for a hydraulic press maintenance assistant.
Choose the MINIMUM set of specialist agents needed to answer the query.
Default to ONE agent unless the query explicitly requires more.

Available agents:
- researcher: equipment manuals — operating procedures, specifications, limits, maintenance steps
- auditor: safety/compliance information AND judgment — regulatory requirements, safety feature definitions, inspection requirements, safety device descriptions (e.g., Gate Safety Plug, Safety Block, two-hand control), AND compliance judgment calls (whether a proposed or ongoing action is permitted)
- troubleshooter: fault diagnosis and similar past repair cases from maintenance logs

Return ONLY valid JSON:
{{
  "agents": ["researcher"],
  "reasoning": "short explanation",
  "proposed_action": "specific action to audit, or null if not an audit question"
}}

Routing rules (apply in strict order):

1. MANDATORY THREE-AGENT RULE (M01 pattern):
   - Select ALL THREE ["researcher", "auditor", "troubleshooter"] IF AND ONLY IF the query BOTH:
     (a) reports an active physical fault symptom or breakdown (e.g., ram drift, spongy handle, sudden pressure drop, fluid leak, grinding noise), AND
     (b) asks an explicit real-time operational safety question (e.g., "Is it safe to keep using?", "Can I continue operating today?").
   - EXCLUSIONS from Rule 1:
     - Pure regulatory or compliance policy questions ("Is it compliant...", "Is it allowed under regulations...", "Is it compliant to keep using...") are auditor ONLY (see Rule 3), even if a malfunction is named as context.
     - Normal operating visual/limit indicators (e.g., "red ring showing", gauge scale markings, stroke travel limit line) are NOT fault symptoms; queries asking if you can continue pumping when a limit indicator appears belong to researcher + auditor (see Rule 4).

2. DO NOT ADD AGENTS SPECULATIVELY:
   - Do NOT add troubleshooter merely because a symptom word (e.g., "spongy", "drift", "leak", "cycle pressure") appears in a procedural ("how to bleed/repair") or compliance context. Troubleshooter is ONLY for diagnosing an active fault or searching past repair logs.
   - Do NOT add researcher just because a fault is reported, UNLESS manual steps/specs are explicitly requested or Rule 1 applies.
   - Do NOT add auditor just because a task involves maintenance, UNLESS an explicit safety/compliance permission ruling is requested or Rule 1 applies.

3. SINGLE-AGENT DEFAULT — pick exactly ONE agent if Rule 1 does not apply and only one intent is present:
   - researcher ONLY: How-to guides, maintenance procedures, specifications, operating limits, or "what does the manual say" (e.g., "How do I bleed spongy lines?", "What is the oil capacity?").
   - auditor ONLY:
     (a) Regulatory compliance, safety standards, inspection requirements, policy questions, or compliance determinations ("Is it compliant to keep using...", "Is X compliant?", "Do we need written safety info?").
     (b) Factual questions about safety devices, safety features, or regulatory definitions from compliance documents (e.g., "What is a Gate Safety Plug?", "What are the required safety features on a press machine?", "What is a Safety Block?", "What are the 7 safety features connected to the electrical control unit?"). These are definition/information lookups from the compliance PDF — NOT manual lookups.
     Set proposed_action to null for (b) cases since there is no action to audit.
   - troubleshooter ONLY: Diagnosing why an active fault occurs or finding past repair cases without asking for manual procedures or safety compliance rulings (e.g., "Why is the ram drifting?", "Have we fixed a leaky valve before?").

4. TWO-AGENT INTENTS (Only when two distinct intents are explicitly requested):
   - researcher + auditor: Questions about reaching visual operating/stroke limits or procedures where safety compliance clearance is asked (e.g., "piston red ring is starting to show — can I keep pumping?", "red ring is showing — can I continue?").
   - researcher + troubleshooter: Explicitly asks BOTH for manual steps/specs AND past repair history.
   - troubleshooter + auditor: Explicitly asks BOTH to diagnose a fault AND for a compliance clearance (where manual procedures are not needed).

5. Keep agent list unique. Prefer fewer agents over more.

User query:
{query}
"""

    parsed = generate_json(prompt, thinking_level="minimal")
    raw_agents = parsed.get("agents", ["researcher"])
    allowed = {"researcher", "auditor", "troubleshooter"}
    agents = [agent for agent in raw_agents if agent in allowed]
    if not agents:
        agents = ["researcher"]

    return OrchestratorPlan(
        query=query,
        agents=agents,
        reasoning=parsed.get("reasoning", ""),
        proposed_action=parsed.get("proposed_action"),
    )


def run_orchestrator(query: str) -> OrchestratorResult:
    plan = classify_query(query)
    result = OrchestratorResult(query=query, plan=plan)

    if "researcher" in plan.agents:
        result.researcher = run_researcher(query).to_dict()

    if "auditor" in plan.agents:
        result.auditor = run_auditor(
            query, proposed_action=plan.proposed_action
        ).to_dict()

    if "troubleshooter" in plan.agents:
        result.troubleshooter = run_troubleshooter(query).to_dict()

    return result


if __name__ == "__main__":
    import sys

    test_query = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "The ram drifts down and feels spongy. Is it safe to keep using the press?"
    )
    output = run_orchestrator(test_query)
    print(json.dumps(output.to_dict(), indent=2))
