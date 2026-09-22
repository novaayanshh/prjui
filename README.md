# TraceUI — 8-Stage Iterative UI Generation Pipeline

TraceUI is a command-line tool that takes a natural-language prompt and produces
a refined **React component** through an 8-stage, constraint-enforcing,
iterative pipeline running on a weak, free local LLM (Ollama).

The thesis comparison: does **structure + iteration** on a weak model close the
quality gap to a one-shot frontier model — at zero cost, with full auditability?

## Three-Armed Evaluation

| Arm | Model | Pipeline | Purpose |
|-----|-------|----------|---------|
| A: Weak one-shot | Free local (Ollama) | No | Baseline (floor) |
| B: Weak + pipeline | Same free model | Full 8-stage | Our method |
| C: Strong one-shot | Paid frontier (Gemini) | No | Upper bound (ceiling) |

## The 8 Stages

```
USER PROMPT
   |
   v
  1. Requirements Analyzer --> requirements.json
   |                           |
   v                           v
  2. Domain Analyzer --------> domain.json
   |                           |
   v                           v
  3. Design Research --------> design.json
   |                           |
   v                           v
  4. Constraint Engine ------> constraints.json
   |                           |
   v                           v
  5. UI Generator -----------> .jsx component  ----+
   |                                                 |
   |  <-- loop back (up to 3x) ---------------------+
   v
  6. UI Evaluator (Playwright) --> evaluation.json
   |
   v
  7. Critic ------------------> critique.json
   |
   v
  8. Refinement Engine -------> "fix" or "stop"
                                   |
                                   v
                           FINAL .jsx UI
```

Interactive clarification layers live in Stages 1, 2, 3, 7, 8. Stages 4, 5, 6
are fully automated. Every JSON output is a signed-off "contract" between
stages.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Pipeline language | Python 3.11+ (plain, no LangChain) |
| UI output | React `.jsx` |
| UI runtime | Node.js |
| Local LLM | Ollama + `qwen2.5:7b` (Arms A & B) |
| Strong model | Gemini free tier (Arm C) |
| HTTP | `requests` |
| Browser automation | `playwright` (headless render, screenshots, text) |
| Design database | SQLite via `sqlite3` stdlib (Stages 3, 4, 5 only) |
| Validation | `jsonschema` + `utils/schema_validator.py` |
| Tests | `pytest` |

## Repo Structure

```
ui-ux/
├── pipeline.py              # CLI entry point
├── baseline.py              # One-shot runner (Arms A & C)
├── seed_db.py               # Design DB seed script
├── requirements.txt
├── .gitignore
├── schemas/
│   ├── pipeline_schemas.json   # contracts between stages
│   └── example_run.json        # worked example
├── utils/
│   ├── __init__.py
│   ├── llm_client.py        # Ollama wrapper (call, parse JSON, retry)
│   ├── db_client.py         # SQLite query functions
│   ├── interact.py          # shared clarification loop
│   └── schema_validator.py  # JSON contract validation
├── stages/
│   ├── __init__.py
│   ├── requirements_analyzer.py
│   ├── domain_analyzer.py
│   ├── design_research.py
│   ├── constraint_engine.py
│   ├── ui_generator.py
│   ├── ui_evaluator.py
│   ├── critic.py
│   └── refinement_engine.py
├── prompts/
│   └── test_prompts.json    # 15-25 prompts for the experiment
├── output/                  # generated UIs, screenshots, run logs (gitignored)
└── tests/
```

## Branch Convention

- `main` is the signed-off baseline.
- Everyone works on `phase0/<name>` branches during Phase 0, merged after review.

## Team Ownership

| Member | Owns |
|--------|------|
| Coordinator | Engine / orchestration + Stage 8 (Refinement Engine) |
| Aditya | Stages 1-3 (Context) |
| Muskaan | Stages 4-5 (Constraints + Generator) |
| Ayansh | Stage 6 (Evaluator / Playwright) |
| Disha | Stage 7 (Critic) + `baseline.py` |