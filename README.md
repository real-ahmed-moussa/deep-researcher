# 📌 Deep Researcher

> Autonomous system that plans, searches, evaluates, and writes comprehensive research reports through dynamically orchestrated LLM agents.

## 📖 Overview

- Implements a fully agentic research pipeline where an OrchestratorAgent makes all control-flow decisions — when to search, when to evaluate, and when to stop — based on measured research quality rather than hardcoded steps.
- Uses three distinct agentic patterns from the OpenAI Agents SDK: `@function_tool` (Planner, Search, and Evaluator exposed as callable tools), `handoff` (Orchestrator → Writer as the terminal agent), and direct invocation (EmailAgent called separately after the report is captured to preserve the correct `final_output`).
- Runs as a Gradio web app locally and deploys to HuggingFace Spaces via a dedicated `app.py` entry point, with a custom newspaper-style CSS theme using Playfair Display headings and an editorial color palette.
- EmailAgent is intentionally excluded from the handoff chain: chaining it would overwrite the `ReportData` object with an email confirmation string, breaking UI display — so it is called as a separate `Runner.run()` after the report is safely captured.

## 🏢 Business Impact

Deep Researcher replaces the tedious cycle of manual web searches, tab management, and manual synthesis with a single query that autonomously produces a structured, sourced, 1000+ word report. For analysts, consultants, and researchers who regularly need rapid background briefings, this pipeline cuts hours of information gathering to minutes while ensuring coverage and depth are scored objectively before synthesis begins. The optional SendGrid integration means finished reports land directly in a recipient's inbox without any manual export step, and full execution tracing in the OpenAI traces dashboard gives complete visibility into every agent decision.

## 🚀 Features

✅ **Adaptive Research Loop:** OrchestratorAgent runs up to 3 rounds of plan → search → evaluate, stopping early when EvaluatorAgent scores coverage ≥7 and depth ≥6 — avoiding wasted compute once research is sufficient.  
✅ **Human-in-the-Loop Scoping:** ClarificationAgent surfaces up to 4 targeted questions before research begins, injecting user answers into every downstream prompt for more focused, relevant results.  
✅ **Parallel Search Execution:** All 5 planned queries in each round run concurrently via `asyncio.gather`, so a full round of searches completes in the time of a single sequential search.  
✅ **Scored Quality Evaluation:** EvaluatorAgent scores each round on coverage (1–10) and depth (1–10) with explicit gap identification, driving gap-targeted query planning in subsequent rounds rather than re-covering explored ground.  
✅ **Structured Report Output:** WriterAgent produces a Pydantic-validated `ReportData` containing an executive summary, full Markdown report (1000+ words), and follow-up questions — all streamed live to the UI as they generate.  
✅ **Email Delivery:** EmailAgent converts the finished Markdown report to styled HTML and sends it via SendGrid, with every step of the entire pipeline traceable in the OpenAI traces dashboard.  

## ⚙️ Tech Stack

| Technology                  | Purpose                                                                    |
| --------------------------- | -------------------------------------------------------------------------- |
| `Python`                    | Primary language for all agents, orchestration logic, and the UI           |
| `openai-agents`             | Agent creation, `@function_tool`, `handoff`, `Runner`, and streaming events |
| `gpt-4o-mini`               | Underlying LLM powering all seven agents                                   |
| `WebSearchTool`             | Built-in Agents SDK tool used by SearchAgent for live web queries          |
| `gradio`                    | Streaming web UI with clarification panel, progress log, and report display |
| `pydantic`                  | Structured output validation for all agent return types                    |
| `asyncio`                   | Concurrent execution of parallel search tasks within each research round   |
| `sendgrid`                  | HTML email delivery of finished reports via EmailAgent                     |
| `python-dotenv`             | Loading API keys and email credentials from `.env`                         |

## 📂 Project Structure

<pre>
📦 Deep Researcher
 ┣ 📂 tests
 ┃ ┣ 📜 __init__.py
 ┃ ┗ 📜 test_models.py
 ┣ 📜 app.py
 ┣ 📜 clarification_agent.py
 ┣ 📜 deep_research.py
 ┣ 📜 email_agent.py
 ┣ 📜 evaluator_agent.py
 ┣ 📜 models.py
 ┣ 📜 orchestrator.py
 ┣ 📜 planner_agent.py
 ┣ 📜 requirements.txt
 ┣ 📜 search_agent.py
 ┣ 📜 writer_agent.py
 ┣ 📜 LICENSE
 ┗ 📜 README.md
</pre>

> **Why two entry points?** `deep_research.py` builds the Gradio UI and is the local launch target (`python deep_research.py`). `app.py` is the HuggingFace Spaces entry point — it imports and launches the same `ui` object, keeping deployment configuration separate from UI logic.

## 🛠️ Installation

1️⃣ **Clone the repository**
<pre>
git clone https://github.com/real-ahmed-moussa/deep-researcher.git
cd deep-researcher
</pre>

2️⃣ **Create and activate a virtual environment**
<pre>
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
</pre>

3️⃣ **Install dependencies**
<pre>
pip install -r requirements.txt
</pre>

4️⃣ **Configure environment variables**
<pre>
cp .env.example .env
# Open .env and fill in:
#   OPENAI_API_KEY   — required for all agents (GPT-4o-mini access)
#   SENDGRID_API_KEY — optional, required only for email delivery
#   EMAIL_FROM       — verified SendGrid sender address
#   EMAIL_TO         — report recipient address
</pre>

5️⃣ **Run the app**
<pre>
python deep_research.py
</pre>

6️⃣ **Run unit tests (no API key required)**
<pre>
pytest tests/ -v
</pre>

## 📊 Results

- **Task:** Autonomous multi-round web research with adaptive stopping, producing structured long-form reports from a single natural-language query.
- **Pipeline completeness:** All 7 agent roles fully implemented — Clarification, Orchestration, Planning, Search, Evaluation, Writing, and Email delivery — each returning a Pydantic-validated structured output type.
- **Search throughput:** Up to 15 web searches per run (5 queries × up to 3 rounds), with all within-round queries executing in parallel via `asyncio.gather`.
- **Quality threshold:** Adaptive stopping triggers when EvaluatorAgent scores coverage ≥7 and depth ≥6, with a pragmatic override at round 3 to prevent diminishing-return searches.
- **Test coverage:** 17 unit tests across all Pydantic models and `ResearchState` logic pass with no API key required, verifying data contracts independently of LLM calls.

## 📝 License

This project is shared for portfolio purposes only and may not be used for commercial purposes without permission.