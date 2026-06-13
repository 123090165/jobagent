# Profile Review Quality Comparison

case_id | deterministic verdict | llm verdict | improvement | risk | final recommendation
--- | --- | --- | --- | --- | ---
ai_agent_backend | strong | strong | LLM path produced usable suggestion decisions without increasing confirmed coverage. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
embedded_stm32 | acceptable | acceptable | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
ml_audio_asr | failed | needs_review | LLM path changed overall evaluation verdict. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
finance_fa_analysis | failed | needs_review | LLM path changed overall evaluation verdict. | No notable LLM-specific risk increase. | keep deterministic as default review baseline
mixed_language_resume | strong | strong | LLM path produced usable suggestion decisions without increasing confirmed coverage. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
weak_resume | acceptable | acceptable | No meaningful LLM improvement observed. | No notable LLM-specific risk increase. | keep deterministic as default review baseline
anker_ai_health_algorithm | failed | failed | No meaningful LLM improvement observed. | No notable LLM-specific risk increase. | keep deterministic as default review baseline
realistic_noisy_chinese_resume | strong | strong | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
realistic_business_resume_unstructured | failed | failed | No meaningful LLM improvement observed. | unsupported suggestions were discarded by grounding checks | keep deterministic as default review baseline
