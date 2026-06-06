"""
Unit tests for models.py — no API key required.
Run with: pytest tests/ -v
"""

import pytest
from models import (
    ClarificationPlan,
    ClarificationQuestion,
    ReportData,
    ResearchState,
    ResearchStatus,
    SufficiencyEvaluation,
    WebSearchItem,
    WebSearchPlan,
)


# ── ResearchState ─────────────────────────────────────────────────────────────

class TestResearchState:

    def test_enriched_query_no_clarifications(self):
        state = ResearchState(query="What is quantum computing?")
        assert state.enriched_query == "What is quantum computing?"

    def test_enriched_query_with_clarifications(self):
        state = ResearchState(
            query="AI trends",
            clarifications={
                "Timeframe": "2024–2025",
                "Audience": "executives",
            },
        )
        result = state.enriched_query
        assert "Original query: AI trends" in result
        assert "Timeframe: 2024–2025" in result
        assert "Audience: executives" in result

    def test_default_status_is_idle(self):
        state = ResearchState(query="test")
        assert state.status == ResearchStatus.IDLE

    def test_default_report_is_none(self):
        state = ResearchState(query="test")
        assert state.report is None

    def test_search_results_summary_empty(self):
        state = ResearchState(query="test")
        assert state.search_results_summary == ""

    def test_search_results_summary_joins_with_separator(self):
        state = ResearchState(query="test")
        state.search_results = ["Result A", "Result B", "Result C"]
        summary = state.search_results_summary
        assert "Result A" in summary
        assert "Result B" in summary
        assert summary.count("---") == 2

    def test_clarifications_defaults_to_empty_dict(self):
        state = ResearchState(query="test")
        assert state.clarifications == {}

    def test_status_transitions(self):
        state = ResearchState(query="test")
        for status in ResearchStatus:
            state.status = status
            assert state.status == status


# ── Pydantic models ───────────────────────────────────────────────────────────

class TestClarificationPlan:

    def test_no_clarification_needed(self):
        plan = ClarificationPlan(
            needs_clarification=False,
            questions=[],
            reasoning="Query is specific enough.",
        )
        assert not plan.needs_clarification
        assert plan.questions == []

    def test_with_questions(self):
        q = ClarificationQuestion(
            question="What is the target audience?",
            reason="Changes depth and tone of the report.",
            category="audience",
        )
        plan = ClarificationPlan(
            needs_clarification=True,
            questions=[q],
            reasoning="Audience is ambiguous.",
        )
        assert plan.needs_clarification
        assert len(plan.questions) == 1
        assert plan.questions[0].category == "audience"


class TestWebSearchPlan:

    def test_empty_searches(self):
        plan = WebSearchPlan(searches=[])
        assert plan.searches == []

    def test_multiple_searches(self):
        items = [
            WebSearchItem(query="AI safety 2025", reason="Overview"),
            WebSearchItem(query="LLM alignment techniques", reason="Technical depth"),
        ]
        plan = WebSearchPlan(searches=items)
        assert len(plan.searches) == 2
        assert plan.searches[0].query == "AI safety 2025"


class TestSufficiencyEvaluation:

    def test_sufficient_evaluation(self):
        ev = SufficiencyEvaluation(
            is_sufficient=True,
            coverage_score=8,
            depth_score=7,
            gaps=[],
            reasoning="Good coverage across all angles.",
            suggested_queries=[],
        )
        assert ev.is_sufficient
        assert ev.coverage_score == 8

    def test_insufficient_evaluation_has_gaps(self):
        ev = SufficiencyEvaluation(
            is_sufficient=False,
            coverage_score=5,
            depth_score=4,
            gaps=["Historical context missing", "No primary sources"],
            reasoning="Shallow on several angles.",
            suggested_queries=["topic history site:edu", "topic primary research"],
        )
        assert not ev.is_sufficient
        assert len(ev.gaps) == 2
        assert len(ev.suggested_queries) == 2


class TestReportData:

    def test_report_data_fields(self):
        report = ReportData(
            short_summary="A concise two-sentence summary.",
            markdown_report="# Title\n\nBody text.",
            follow_up_questions=["What next?", "How does X relate to Y?"],
        )
        assert report.short_summary.startswith("A concise")
        assert "# Title" in report.markdown_report
        assert len(report.follow_up_questions) == 2


# ── ResearchStatus enum ───────────────────────────────────────────────────────

class TestResearchStatus:

    def test_all_statuses_are_strings(self):
        for status in ResearchStatus:
            assert isinstance(status.value, str)

    def test_status_values(self):
        assert ResearchStatus.IDLE == "idle"
        assert ResearchStatus.COMPLETE == "complete"
        assert ResearchStatus.WRITING == "writing"
