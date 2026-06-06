from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional


class ResearchStatus(str, Enum):
    IDLE = "idle"
    CLARIFYING = "clarifying"
    PLANNING = "planning"
    SEARCHING = "searching"
    EVALUATING = "evaluating"
    WRITING = "writing"
    EMAILING = "emailing"
    COMPLETE = "complete"


class ClarificationQuestion(BaseModel):
    question: str = Field(description="A focused clarifying question for the user.")
    reason: str = Field(description="Why this question improves research quality.")
    category: str = Field(description="Category: scope | depth | format | audience | timeframe")


class ClarificationPlan(BaseModel):
    needs_clarification: bool = Field(
        description="Whether the query needs clarification before searching."
    )
    questions: list[ClarificationQuestion] = Field(
        description="List of clarifying questions to ask the user. Empty if needs_clarification=False."
    )
    reasoning: str = Field(
        description="Brief explanation of why clarification is or isn't needed."
    )


class WebSearchItem(BaseModel):
    reason: str = Field(description="Reasoning for why this search matters.")
    query: str = Field(description="The search term to use.")


class WebSearchPlan(BaseModel):
    searches: list[WebSearchItem] = Field(description="List of web searches to perform.")


class SufficiencyEvaluation(BaseModel):
    is_sufficient: bool = Field(
        description="Whether the research gathered so far is sufficient to write a comprehensive report."
    )
    coverage_score: int = Field(
        description="Score 1-10: how well the key angles of the query are covered."
    )
    depth_score: int = Field(
        description="Score 1-10: how well claims are backed by multiple sources."
    )
    gaps: list[str] = Field(
        description="List of remaining gaps or unanswered angles. Empty if sufficient."
    )
    reasoning: str = Field(
        description="Brief explanation of the sufficiency decision."
    )
    suggested_queries: list[str] = Field(
        description="Additional search queries to fill gaps. Empty if sufficient."
    )


class ReportData(BaseModel):
    short_summary: str = Field(description="A short 2-3 sentence summary of the findings.")
    markdown_report: str = Field(description="The full detailed report in markdown format.")
    follow_up_questions: list[str] = Field(description="Suggested topics to research further.")


class ResearchState:
    """Mutable state object passed through the research pipeline."""

    def __init__(self, query: str, clarifications: dict[str, str] | None = None):
        self.original_query = query
        self.clarifications: dict[str, str] = clarifications or {}
        self.search_results: list[str] = []
        self.rounds_completed: int = 0
        self.status: ResearchStatus = ResearchStatus.IDLE
        self.report: Optional[ReportData] = None
        self.evaluation_history: list[SufficiencyEvaluation] = []

    @property
    def enriched_query(self) -> str:
        """Returns the query enriched with any clarification answers."""
        if not self.clarifications:
            return self.original_query
        clarification_text = "\n".join(
            f"- {q}: {a}" for q, a in self.clarifications.items()
        )
        return (
            f"Original query: {self.original_query}\n"
            f"Additional context from user:\n{clarification_text}"
        )

    @property
    def search_results_summary(self) -> str:
        return "\n\n---\n\n".join(self.search_results)
