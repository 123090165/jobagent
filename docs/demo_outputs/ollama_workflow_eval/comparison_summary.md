# Ollama Workflow Evaluation Comparison

## Mode Comparison Table

| mode | fallback_count | overall_score | analysis_quality | estimated_input_tokens | estimated_output_tokens | estimated_total_tokens | notes |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| mock | 0 | 77.0 | medium | 3999 | 3062 | 7061 | deterministic baseline |
| ollama-jd-only | 0 | 27.0 | medium | 5195 | 3987 | 9182 | 1 LLM step(s) completed |
| ollama-resume-optimize-only | 0 | 77.0 | medium | 3999 | 2979 | 6978 | 1 LLM step(s) completed |
| ollama-project-challenge-only | 1 | 77.0 | medium | 3999 | 3062 | 7061 | 1 fallback step(s); inspect fallback_reason |
| ollama-all-llm | 1 | 27.0 | medium | 5195 | 4373 | 9568 | 1 fallback step(s); inspect fallback_reason |

## JDAnalysis Comparison

- mock: step_mode=mock, fallback_reason=none, estimated_total_tokens=857. required_skills=9, keywords=9.
- ollama-jd-only: step_mode=llm, fallback_reason=none, estimated_total_tokens=1039. required_skills=4, keywords=7.
- ollama-all-llm: step_mode=llm, fallback_reason=none, estimated_total_tokens=1039. required_skills=4, keywords=7.

## ResumeOptimize Comparison

- mock: step_mode=mock, fallback_reason=none, estimated_total_tokens=3425. rewrite_suggestions=6, jd_targeted_bullets=2.
- ollama-resume-optimize-only: step_mode=llm, fallback_reason=none, estimated_total_tokens=3342. rewrite_suggestions=6, jd_targeted_bullets=1.
- ollama-all-llm: step_mode=llm, fallback_reason=none, estimated_total_tokens=5197. rewrite_suggestions=6, jd_targeted_bullets=4.

## ProjectChallenge Comparison

- mock: step_mode=mock, fallback_reason=none, estimated_total_tokens=2779. grounded_questions=8, basic_questions=2.
- ollama-project-challenge-only: step_mode=fallback, fallback_reason=ValidationError, estimated_total_tokens=2779. grounded_questions=8, basic_questions=2.
- ollama-all-llm: step_mode=fallback, fallback_reason=LLMServiceError, estimated_total_tokens=3332. grounded_questions=8, basic_questions=2.

## Cost Estimation

- input_tokens_per_run = 5195
- output_tokens_per_run = 4373
- total_tokens_per_run = 9568

Cost formula:

```text
input_cost = input_tokens / 1_000_000 * input_price_per_1m
output_cost = output_tokens / 1_000_000 * output_price_per_1m
total_cost = input_cost + output_cost
```

Example only: If input is $0.15 / 1M tokens and output is $0.60 / 1M tokens, one run costs approximately $0.003403. This is an illustrative formula, not a current price claim.

## Recommendation

- JDAnalysisAgent: schema-valid LLM output was produced; compare specificity and evidence before enabling by default.
- ResumeOptimizeAgent: schema-valid LLM output was produced; compare specificity and evidence before enabling by default.
- ProjectInterviewAgent: fallback occurred (ValidationError); prefer JSON repair, stricter output validation, or a larger model.
- For low-risk local use, a small model may be safest for classification or extraction tasks before free-form rewrite generation.
