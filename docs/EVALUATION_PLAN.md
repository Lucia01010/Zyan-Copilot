# M8 Evaluation Plan

## Scope

M8 first phase is offline evaluation preparation. It compares three explicitly separated systems:

1. Baseline A — LLM-only: necessary chat context only, no business tools. It is not run offline and cannot be scored without a live model run.
2. Baseline B — deterministic Rules: `app.risk_engine.assess_context` over business-tool context.
3. Proposed Agent: Qwen + business Tools + final structured synthesis; offline runs may use mock only and are never reported as live Qwen quality.

## Dataset provenance

`scripts/build_m8_evaluation_dataset.py` creates `data/generated/evaluation/m8_dataset.json` from imported SQLite data. `scene_major`, `scene_minor`, work-order types and after-sales reasons are source-derived. Rule labels are separately marked rule-derived. Manual risk/intent labels are currently unavailable; model-generated labels are never ground truth.

## Metrics

Measured metrics are limited to available evidence: dataset coverage, rule risk distribution, schema validity, tool-call records, grounding, latency and token usage when a corresponding run exists. Gold Set v1 now provides reviewed intent/risk labels for 24 DONE records, but the live comparison remains N=2 and is not evidence of general improvement. Case C is a formal Gold v1 disagreement (human HIGH; Rules CRITICAL; model MEDIUM), not an unknown label.

## Live budget policy

`TokenBudgetGuard` uses used tokens plus a conservative per-case estimate before starting the next request. It never interrupts an already-started request, but blocks the next case when the estimate would exceed the hard budget. M8 live evaluation is capped to small, explicit samples only.
