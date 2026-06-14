# Profile Review Quality Comparison

case_id | deterministic verdict | llm verdict | improvement | risk | final recommendation
--- | --- | --- | --- | --- | ---
ai_agent_backend | strong | strong | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
embedded_stm32 | strong | strong | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
ml_audio_asr | strong | strong | LLM path produced usable suggestion decisions without increasing confirmed coverage. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
finance_fa_analysis | strong | strong | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
mixed_language_resume | strong | strong | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
weak_resume | acceptable | acceptable | No meaningful LLM improvement observed. | No notable LLM-specific risk increase. | keep deterministic as default review baseline
anker_ai_health_algorithm | strong | strong | LLM path produced usable suggestion decisions without increasing confirmed coverage. | unsupported suggestions were discarded by grounding checks; one or more item enrichments fell back | keep deterministic as default review baseline
realistic_noisy_chinese_resume | strong | strong | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks; one or more item enrichments fell back | keep deterministic as default review baseline
realistic_business_resume_unstructured | acceptable | acceptable | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
