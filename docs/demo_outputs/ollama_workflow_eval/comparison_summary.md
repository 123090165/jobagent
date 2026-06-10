# Ollama Workflow Evaluation Comparison

## Mode Comparison Table

| mode | fallback_count | overall_score | analysis_quality | estimated_input_tokens | estimated_output_tokens | estimated_total_tokens | notes |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| mock | 0 | 77.0 | medium | 3999 | 3062 | 7061 | deterministic baseline |

## JDAnalysis Comparison

- mock: step_mode=mock, fallback_reason=none, estimated_total_tokens=857. required_skills=9, keywords=9.
- ollama-jd-only: not run in this invocation.
- ollama-all-llm: not run in this invocation.

## ResumeOptimize Comparison

- mock: step_mode=mock, fallback_reason=none, estimated_total_tokens=3425. rewrite_suggestions=6, jd_targeted_bullets=2.
- ollama-resume-optimize-only: not run in this invocation.
- ollama-all-llm: not run in this invocation.

## ProjectChallenge Comparison

- mock: step_mode=mock, fallback_reason=none, estimated_total_tokens=2779. grounded_questions=8, basic_questions=2.
- ollama-project-challenge-only: not run in this invocation.
- ollama-all-llm: not run in this invocation.

## Cost Estimation

- input_tokens_per_run = 3999
- output_tokens_per_run = 3062
- total_tokens_per_run = 7061

Cost formula:

```text
input_cost = input_tokens / 1_000_000 * input_price_per_1m
output_cost = output_tokens / 1_000_000 * output_price_per_1m
total_cost = input_cost + output_cost
```

Example only: If input is $0.15 / 1M tokens and output is $0.60 / 1M tokens, one run costs approximately $0.002437. This is an illustrative formula, not a current price claim.

## Recommendation

- Ollama modes were not run in this invocation, so model suitability cannot be judged yet.
- The harness is ready for local model testing; next run `--mode all` after configuring Ollama.
- If a 0.5B model falls back often, first try JSON repair or a larger local model before changing agent prompts.
