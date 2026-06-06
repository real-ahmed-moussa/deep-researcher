from agents import Agent
from models import WebSearchPlan

HOW_MANY_SEARCHES = 5

INSTRUCTIONS = f"""You are a research planning specialist. Given a query (and optional context 
about what has already been searched), generate {HOW_MANY_SEARCHES} targeted web search queries 
to best answer the research question.

When research gaps are provided (in follow-up rounds), focus your searches specifically on 
filling those gaps rather than re-covering already-researched ground.

Each search query should:
- Be specific enough to return useful results
- Target a distinct angle (don't generate near-duplicate queries)
- Be 3-8 words, optimised for search engine retrieval"""

planner_agent = Agent(
    name="PlannerAgent",
    instructions=INSTRUCTIONS,
    model="gpt-4o-mini",
    output_type=WebSearchPlan,
)
