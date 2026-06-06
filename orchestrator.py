"""
orchestrator.py

Agentic patterns:
  - @function_tool  -> Planner, Evaluator, Search (agents-as-tools)
  - handoff         -> OrchestratorAgent -> WriterAgent (research to writing)
  - direct call     -> EmailAgent called explicitly after we have the report

Architecture note:
  We do NOT chain Writer -> Email via handoff because the Email agent's
  confirmation string would become final_output, overwriting the ReportData
  we need to display in the UI.

  Instead:
    1. OrchestratorAgent researches, then hands off to WriterAgent
    2. We capture WriterAgent's ReportData via Runner.run_streamed final_output
       (Writer is now the terminal agent, so final_output is correct)
    3. We call EmailAgent separately with Runner.run() if send_email_after=True
"""

import asyncio
import json
import logging
from agents import (
    Agent, Runner, handoff, function_tool,
    trace, gen_trace_id,
)

from models import (
    ResearchState, ResearchStatus,
    WebSearchPlan, SufficiencyEvaluation,
    ClarificationPlan, ReportData,
)
from clarification_agent import clarification_agent
from planner_agent import planner_agent
from evaluator_agent import evaluator_agent
from search_agent import search_agent
from writer_agent import writer_agent
from email_agent import email_agent

logger = logging.getLogger(__name__)

MAX_ROUNDS = 3


# ── Tools ─────────────────────────────────────────────────────────────────────

@function_tool
async def plan_searches(query_with_gaps: str) -> str:
    """
    Generate targeted web search queries for the given research query.

    Args:
        query_with_gaps: The enriched research query, optionally including
                         gap context from a previous evaluation round.
    Returns:
        JSON string of WebSearchPlan.
    """
    result = await Runner.run(planner_agent, query_with_gaps)
    plan = result.final_output_as(WebSearchPlan)
    return plan.model_dump_json()


@function_tool
async def run_searches(queries_json: str) -> str:
    """
    Execute a batch of web searches in parallel and return combined summaries.

    Args:
        queries_json: JSON array of objects with 'query' and 'reason' keys.
                      Example: '[{"query": "AI trends 2025", "reason": "overview"}]'
    Returns:
        Combined search summaries separated by '---'.
    """
    items = json.loads(queries_json)

    async def _one(item: dict) -> str | None:
        prompt = f"Search term: {item['query']}\nReason for searching: {item['reason']}"
        try:
            result = await Runner.run(search_agent, prompt)
            return str(result.final_output)
        except Exception as e:
            print(f"Search failed for '{item['query']}': {e}")
            return None

    tasks = [asyncio.create_task(_one(item)) for item in items]
    gathered = await asyncio.gather(*tasks)
    results = [r for r in gathered if r is not None]
    return "\n\n---\n\n".join(results)


@function_tool
async def evaluate_sufficiency(evaluation_input: str) -> str:
    """
    Score research quality and identify any remaining gaps.

    Args:
        evaluation_input: The query plus all search results so far,
                          including the current round number.
    Returns:
        JSON string of SufficiencyEvaluation.
    """
    result = await Runner.run(evaluator_agent, evaluation_input)
    evaluation = result.final_output_as(SufficiencyEvaluation)
    return evaluation.model_dump_json()


# ── Orchestrator Agent ────────────────────────────────────────────────────────
# Handoff: OrchestratorAgent -> WriterAgent only.
# WriterAgent is the terminal agent so final_output = ReportData.

ORCHESTRATOR_INSTRUCTIONS = f"""You are a research orchestrator. Your job is to conduct
multi-round web research on a given query and then hand off to the Writer Agent.

Tools available:
- plan_searches        -> generates targeted search queries
- run_searches         -> executes searches in parallel
- evaluate_sufficiency -> scores coverage and depth, identifies gaps

Research loop:
1. Call plan_searches with the full research query
2. Call run_searches with the plan (JSON array with 'query' and 'reason' keys)
3. Call evaluate_sufficiency with: query + round number + ALL results so far
4. Check evaluation:
   - is_sufficient=true OR round={MAX_ROUNDS} -> go to step 5
   - is_sufficient=false AND round<{MAX_ROUNDS} -> plan_searches with gaps, repeat
5. Hand off to the Writer Agent with the query and ALL accumulated search results.

Format for run_searches:
'[{{"query": "search term", "reason": "why this matters"}}]'

Do NOT write the report yourself. Hand off to the Writer when done."""

orchestrator_agent = Agent(
    name="OrchestratorAgent",
    instructions=ORCHESTRATOR_INSTRUCTIONS,
    tools=[plan_searches, run_searches, evaluate_sufficiency],
    handoffs=[handoff(writer_agent)],   # Writer is terminal — no further handoff
    model="gpt-4o-mini",
)


# ── Report extraction helper ──────────────────────────────────────────────────

def _try_parse_report(raw) -> ReportData | None:
    """Parse ReportData from whatever shape the SDK returns."""
    if isinstance(raw, ReportData):
        return raw
    if isinstance(raw, dict):
        try:
            return ReportData(**raw)
        except Exception:
            pass
    if isinstance(raw, str):
        cleaned = raw.strip()
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        try:
            return ReportData(**json.loads(cleaned))
        except Exception:
            pass
    return None


# ── ResearchRunner ────────────────────────────────────────────────────────────

class ResearchRunner:

    async def get_clarifications(self, query: str) -> ClarificationPlan:
        result = await Runner.run(clarification_agent, f"Research query: {query}")
        return result.final_output_as(ClarificationPlan)

    async def run(self, state: ResearchState, send_email_after: bool = False):
        """
        Stream the Orchestrator -> Writer chain, then optionally call Email.
        WriterAgent is the terminal agent so streamed.final_output = ReportData.
        Email is called separately afterwards to avoid polluting final_output.
        """
        trace_id = gen_trace_id()

        with trace("Deep Research", trace_id=trace_id):
            yield f"Trace: https://platform.openai.com/traces/trace?trace_id={trace_id}"

            initial_message = (
                f"{state.enriched_query}\n\n"
                "Please conduct thorough research and produce a comprehensive report."
            )

            current_agent = "OrchestratorAgent"
            round_num = 0

            streamed = Runner.run_streamed(
                orchestrator_agent,
                initial_message,
                max_turns=50,
            )

            async for event in streamed.stream_events():
                etype = event.type

                # ── Agent transitions ──────────────────────────────────────
                if etype == "agent_updated_stream_event":
                    new_name = event.new_agent.name
                    if new_name != current_agent:
                        current_agent = new_name
                        icon = "✍️" if "writer" in new_name.lower() else "📧"
                        yield f"{icon} Handoff -> {new_name}"
                        if "writer" in new_name.lower():
                            state.status = ResearchStatus.WRITING

                # ── Tool calls and results ─────────────────────────────────
                elif etype == "run_item_stream_event":
                    item = event.item

                    if item.type == "tool_call_item":
                        raw = getattr(item, "raw_item", None)
                        tool_name = (
                            getattr(item, "name", None)
                            or getattr(raw, "name", None)
                            or ""
                        )
                        if tool_name == "plan_searches":
                            round_num += 1
                            yield f"Round {round_num} - Planning searches..."
                            state.status = ResearchStatus.PLANNING
                        elif tool_name == "run_searches":
                            yield "Running searches in parallel..."
                            state.status = ResearchStatus.SEARCHING
                        elif tool_name == "evaluate_sufficiency":
                            yield "Evaluating research sufficiency..."
                            state.status = ResearchStatus.EVALUATING

                    elif item.type == "tool_call_output_item":
                        output = getattr(item, "output", "") or ""
                        try:
                            data = json.loads(output)
                            if "coverage_score" in data:
                                c, d, ok = data["coverage_score"], data["depth_score"], data["is_sufficient"]
                                yield f"Coverage: {c}/10 | Depth: {d}/10 - {'Sufficient' if ok else 'More research needed'}"
                                if ok:
                                    yield data.get("reasoning", "")
                                elif data.get("gaps"):
                                    yield f"Gaps: {', '.join(data['gaps'][:3])}"
                            elif "searches" in data:
                                yield f"Plan ready - {len(data['searches'])} searches queued"
                        except (json.JSONDecodeError, TypeError):
                            if output and len(output) > 100:
                                yield f"Searches complete - {output.count('---') + 1} results gathered"

            # ── Extract report from Writer's final_output ──────────────────
            report = _try_parse_report(streamed.final_output)

            if report is None:
                logger.error(
                    "Failed to parse ReportData — type=%s value=%.400s",
                    type(streamed.final_output).__name__,
                    str(streamed.final_output),
                )
                yield "Could not extract report. Check logs for details."
                return

            state.report = report
            state.status = ResearchStatus.COMPLETE
            yield "Report complete!"
            yield f"__REPORT__{report.markdown_report}"
            yield f"__SUMMARY__{report.short_summary}"
            yield f"__FOLLOWUP__{','.join(report.follow_up_questions)}"

            # ── Email: separate call after report is safely captured ───────
            if send_email_after:
                yield "Sending email..."
                state.status = ResearchStatus.EMAILING
                try:
                    await Runner.run(email_agent, report.markdown_report)
                    yield "Email sent!"
                except Exception as e:
                    yield f"Email failed: {e}"
