# Ollama Workflow Evaluation Comparison

## Mode Comparison Table

| mode | fallback_count | overall_score | analysis_quality | estimated_input_tokens | estimated_output_tokens | estimated_total_tokens | notes |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| ollama-project-challenge-only | 0 | 77.0 | medium | 4806 | 2997 | 7803 | 1 LLM step(s) completed |

## JDAnalysis Comparison

- mock: not run in this invocation.
- ollama-jd-only: not run in this invocation.
- ollama-all-llm: not run in this invocation.

## ResumeOptimize Comparison

- mock: not run in this invocation.
- ollama-resume-optimize-only: not run in this invocation.
- ollama-all-llm: not run in this invocation.

## ProjectChallenge Comparison

- mock: not run in this invocation.
- ollama-project-challenge-only: step_mode=llm, fallback_reason=none, quality_warnings=None, estimated_total_tokens=3209. llm_success_count=6, fallback_count=0, item_fallback_reasons=[], grounded_questions=6, basic_questions=1.
- ollama-all-llm: not run in this invocation.

## Cost Estimation

- input_tokens_per_run = 4806
- output_tokens_per_run = 2997
- total_tokens_per_run = 7803

Cost formula:

```text
input_cost = input_tokens / 1_000_000 * input_price_per_1m
output_cost = output_tokens / 1_000_000 * output_price_per_1m
total_cost = input_cost + output_cost
```

Example only: If input is $0.15 / 1M tokens and output is $0.60 / 1M tokens, one run costs approximately $0.002519. This is an illustrative formula, not a current price claim.

## Recommendation

- JDAnalysisAgent: not enough data from this run.
- ResumeOptimizeAgent: not enough data from this run.
- ProjectInterviewAgent: schema-valid LLM output was produced; compare specificity and evidence before enabling by default.
- For low-risk local use, a small model may be safest for classification or extraction tasks before free-form rewrite generation.
