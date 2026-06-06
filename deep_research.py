import asyncio
import gradio as gr
from dotenv import load_dotenv

from models import ResearchState, ClarificationPlan
from orchestrator import ResearchRunner

load_dotenv(override=True)

orchestrator = ResearchRunner()

# ── Helpers ────────────────────────────────────────────────────────────────────

def make_question_rows(plan: ClarificationPlan):
    """Return (label, visibility) pairs for up to 4 question rows."""
    questions = plan.questions[:4] if plan.needs_clarification else []
    rows = []
    for i in range(4):
        if i < len(questions):
            rows.append((questions[i].question, True))
        else:
            rows.append(("", False))
    return rows


# ── Phase 1: Analyse query ─────────────────────────────────────────────────────

async def analyse_query(query: str):
    """Call clarification agent; update question rows and phase visibility."""
    if not query.strip():
        yield (
            gr.update(),                              # query_box
            gr.update(visible=False),                 # clarify_panel
            gr.update(visible=False),                 # start_btn
            *[gr.update(visible=False, label="") for _ in range(4)],  # q rows
            "Please enter a research topic first.",   # status
        )
        return

    yield (
        gr.update(interactive=False),
        gr.update(visible=False),
        gr.update(visible=False),
        *[gr.update(visible=False) for _ in range(4)],
        "🤔 Analysing your query...",
    )

    plan = await orchestrator.get_clarifications(query)
    rows = make_question_rows(plan)

    updates = []
    for label, visible in rows:
        updates.append(gr.update(label=label, visible=visible, value=""))

    if plan.needs_clarification:
        status = f"💬 {plan.reasoning}\n\nPlease answer the questions below, then click **Start Research**."
        yield (
            gr.update(interactive=True),
            gr.update(visible=True),
            gr.update(visible=True),
            *updates,
            status,
        )
    else:
        status = f"✅ {plan.reasoning}\n\nQuery is clear — ready to start research!"
        yield (
            gr.update(interactive=True),
            gr.update(visible=False),
            gr.update(visible=True),
            *updates,
            status,
        )


# ── Phase 2: Run research ──────────────────────────────────────────────────────

async def run_research(
    query, send_email,
    a0, a1, a2, a3,
    q0_label, q1_label, q2_label, q3_label,
):
    """Collect answers, build ResearchState, stream progress."""
    answers_raw = [a0, a1, a2, a3]
    labels_raw  = [q0_label, q1_label, q2_label, q3_label]

    clarifications = {
        label: answer
        for label, answer in zip(labels_raw, answers_raw)
        if label and answer and answer.strip()
    }

    state = ResearchState(query=query, clarifications=clarifications)

    progress_log = ""
    report_md    = ""
    summary_txt  = ""
    followups    = []

    async for chunk in orchestrator.run(state, send_email_after=send_email):
        if chunk.startswith("__REPORT__"):
            report_md = chunk[len("__REPORT__"):]
        elif chunk.startswith("__SUMMARY__"):
            summary_txt = chunk[len("__SUMMARY__"):]
        elif chunk.startswith("__FOLLOWUP__"):
            raw = chunk[len("__FOLLOWUP__"):]
            followups = [q.strip() for q in raw.split(",") if q.strip()]
        else:
            progress_log += chunk + "\n"

        followup_md = ""
        if followups:
            followup_md = "### 💡 Suggested Follow-up Questions\n" + "\n".join(
                f"- {q}" for q in followups
            )

        yield (
            progress_log,
            summary_txt,
            report_md,
            followup_md,
            gr.update(visible=bool(report_md)),
        )


# ── Build UI ───────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Source+Sans+3:wght@300;400;600&display=swap');

:root {
    --ink:      #0f1117;
    --paper:    #f7f4ef;
    --accent:   #c8502a;
    --mid:      #6b6560;
    --rule:     #d9d4cc;
    --code-bg:  #1e1e2e;
}

body, .gradio-container {
    background: var(--paper) !important;
    font-family: 'Source Sans 3', sans-serif !important;
    color: var(--ink) !important;
}

/* Masthead */
#masthead {
    border-bottom: 3px double var(--ink);
    padding-bottom: 1rem;
    margin-bottom: 1.5rem;
    text-align: center;
}
#masthead h1 {
    font-family: 'Playfair Display', Georgia, serif !important;
    font-size: 2.8rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
    margin: 0 !important;
    color: var(--ink) !important;
}
#masthead .dateline {
    font-size: 0.75rem;
    color: var(--mid);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-top: 0.25rem;
}

/* Section labels */
.section-label {
    font-family: 'Source Sans 3', sans-serif;
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--mid);
    border-top: 1px solid var(--rule);
    padding-top: 0.5rem;
    margin-bottom: 0.5rem;
}

/* Inputs */
textarea, input[type=text] {
    background: white !important;
    border: 1px solid var(--rule) !important;
    border-radius: 0 !important;
    font-family: 'Source Sans 3', sans-serif !important;
    font-size: 1rem !important;
    color: var(--ink) !important;
}
textarea:focus, input[type=text]:focus {
    border-color: var(--ink) !important;
    box-shadow: none !important;
}

/* Buttons */
button.primary {
    background: var(--ink) !important;
    color: var(--paper) !important;
    border-radius: 0 !important;
    font-family: 'Source Sans 3', sans-serif !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    border: none !important;
    padding: 0.6rem 1.5rem !important;
    transition: background 0.2s !important;
}
button.primary:hover { background: var(--accent) !important; }

button.secondary {
    background: transparent !important;
    color: var(--ink) !important;
    border: 1px solid var(--ink) !important;
    border-radius: 0 !important;
    font-family: 'Source Sans 3', sans-serif !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}

/* Progress log */
#progress-box textarea {
    font-family: 'Source Sans 3', monospace !important;
    font-size: 0.85rem !important;
    background: #faf8f5 !important;
    border-left: 3px solid var(--accent) !important;
    color: var(--mid) !important;
}

/* Report output */
#report-out {
    background: white;
    border: 1px solid var(--rule);
    padding: 2rem;
}
#report-out h1, #report-out h2, #report-out h3 {
    font-family: 'Playfair Display', serif !important;
    color: var(--ink) !important;
}
#report-out h2 { border-bottom: 1px solid var(--rule); padding-bottom: 0.3rem; }

/* Summary callout */
#summary-box {
    border-left: 4px solid var(--accent);
    padding: 1rem 1.5rem;
    background: #fdf5f2;
    font-style: italic;
    font-size: 1.05rem;
    color: var(--ink);
    margin-bottom: 1rem;
}

/* Clarify panel */
#clarify-panel {
    background: #faf8f5;
    border: 1px solid var(--rule);
    padding: 1.25rem;
}

/* Checkbox */
label.svelte-1gfkn6j { color: var(--ink) !important; }
"""

with gr.Blocks(css=CSS, title="Deep Researcher") as ui:

    # ── State stores for question labels (so run_research can read them) ──────
    q0_label_state = gr.State("")
    q1_label_state = gr.State("")
    q2_label_state = gr.State("")
    q3_label_state = gr.State("")

    # ── Masthead ──────────────────────────────────────────────────────────────
    gr.HTML("""
    <div id="masthead">
        <h1>Deep Researcher</h1>
        <div class="dateline">Autonomous · Multi-Round · Adaptive</div>
    </div>
    """)

    # ── Query input row ───────────────────────────────────────────────────────
    with gr.Row():
        with gr.Column(scale=5):
            gr.HTML('<div class="section-label">Research Query</div>')
            query_box = gr.Textbox(
                placeholder="What would you like to research?",
                label="",
                lines=2,
            )
        with gr.Column(scale=1, min_width=140):
            gr.HTML('<div class="section-label">&nbsp;</div>')
            analyse_btn = gr.Button("Analyse Query", variant="secondary")

    # ── Status message ────────────────────────────────────────────────────────
    status_md = gr.Markdown("", elem_id="status-md")

    # ── Clarification panel (hidden until needed) ─────────────────────────────
    with gr.Column(visible=False, elem_id="clarify-panel") as clarify_panel:
        gr.HTML('<div class="section-label">Clarifying Questions</div>')
        q0 = gr.Textbox(label="", visible=False, lines=1)
        q1 = gr.Textbox(label="", visible=False, lines=1)
        q2 = gr.Textbox(label="", visible=False, lines=1)
        q3 = gr.Textbox(label="", visible=False, lines=1)

    # ── Options + Start ───────────────────────────────────────────────────────
    with gr.Row(visible=False) as start_row:
        send_email_cb = gr.Checkbox(label="Send report by email when complete", value=False)
        start_btn = gr.Button("Start Research", variant="primary")

    gr.HTML("<hr style='border:none;border-top:1px solid #d9d4cc;margin:1.5rem 0'>")

    # ── Progress log ──────────────────────────────────────────────────────────
    gr.HTML('<div class="section-label">Research Progress</div>')
    progress_box = gr.Textbox(
        label="",
        lines=8,
        interactive=False,
        elem_id="progress-box",
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    with gr.Column(visible=False) as report_panel:
        gr.HTML('<div class="section-label">Executive Summary</div>')
        summary_box = gr.Markdown("", elem_id="summary-box")

        gr.HTML('<div class="section-label">Full Report</div>')
        report_out = gr.Markdown("", elem_id="report-out")

        gr.HTML('<div class="section-label">Follow-up Questions</div>')
        followup_out = gr.Markdown("")

    # ── Wire up: Analyse ──────────────────────────────────────────────────────
    async def _analyse(query):
        # Wraps analyse_query to also update the label state stores
        async for updates in analyse_query(query):
            # updates = (query_box, clarify_panel, start_row, q0,q1,q2,q3, status)
            qbox, cpanel, srow, uq0, uq1, uq2, uq3, status = updates

            # Extract labels from the updates for state
            l0 = uq0.get("label", "") if isinstance(uq0, dict) else ""
            l1 = uq1.get("label", "") if isinstance(uq1, dict) else ""
            l2 = uq2.get("label", "") if isinstance(uq2, dict) else ""
            l3 = uq3.get("label", "") if isinstance(uq3, dict) else ""

            yield qbox, cpanel, srow, uq0, uq1, uq2, uq3, status, l0, l1, l2, l3

    analyse_btn.click(
        fn=_analyse,
        inputs=[query_box],
        outputs=[
            query_box, clarify_panel, start_row,
            q0, q1, q2, q3,
            status_md,
            q0_label_state, q1_label_state, q2_label_state, q3_label_state,
        ],
    )
    query_box.submit(
        fn=_analyse,
        inputs=[query_box],
        outputs=[
            query_box, clarify_panel, start_row,
            q0, q1, q2, q3,
            status_md,
            q0_label_state, q1_label_state, q2_label_state, q3_label_state,
        ],
    )

    # ── Wire up: Research ─────────────────────────────────────────────────────
    start_btn.click(
        fn=run_research,
        inputs=[
            query_box, send_email_cb,
            q0, q1, q2, q3,
            q0_label_state, q1_label_state, q2_label_state, q3_label_state,
        ],
        outputs=[progress_box, summary_box, report_out, followup_out, report_panel],
    )

if __name__ == "__main__":
    ui.launch(inbrowser=True)
