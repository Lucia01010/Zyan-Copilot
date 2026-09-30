# Competition Demo Metrics

This is a preliminary summary of already measured evaluation data. It is not a large-scale benchmark.

## Measured live sample

- Live evaluation sample: **N=3**, guarded run only; cases covered Case C, LOW and CRITICAL scenarios.
- Provider/model: real Qwen `qwen3.7-plus`; no mock fallback in that live run.
- Agent structured-output validity: 3/3 (1.00).
- Evidence grounding: 3/3 (1.00).
- Unsupported business facts: 0.
- Repair rate: 0; finish reason was `stop` for all three Agent outputs.
- Preliminary intent major/minor/combined accuracy: 1.00 / 1.00 / 1.00 (N=3, taxonomy-normalized).
- Preliminary risk accuracy: Rules 0.67, LLM-only 1.00, Agent model 1.00, Hybrid final risk 1.00 (N=3).
- Agent average total tokens: 13,013; historical Agent average: 19,585; measured reduction approximately 33.6%.
- Agent average latency: 20,892 ms; LLM-only average latency: 6,780 ms.

## Interpretation limits

- N=3 is preliminary and must not be presented as population-level accuracy.
- `human_required_tools` was not annotated, so tool-selection accuracy and required-tool recall are not measurable.
- Planning/tool-loop/final-synthesis token splits were not persisted in that run; only provider total/input/output usage is measured.
- Demo cached mode is not live Qwen output and must be labeled as such in a recording.
