# Search Quality Legacy Baseline

Runtime profile: `legacy_deterministic_v1`
Fixture: `search-quality-v2.1`
Cases: 8
Digest: `sha256:90636ba0250cedc8231121a18f8a1cfa4661606aee73927d73f6152b848484e5`

| Case | Pool recall | Eligible recall | Precision@5 | nDCG@5 | Violations | Duplicates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| technical_ai_intern | 1.000 (4/4) | 1.000 (3/3) | 0.600 (3/5) | 1.000 (9/9) | 1.0 | 0.0 |
| bilingual_role_alias | 1.000 (4/4) | 1.000 (4/4) | 0.800 (4/5) | 0.838 (8/10) | 0.0 | 0.0 |
| hard_constraint_supply_chain | 1.000 (5/5) | 1.000 (4/4) | 0.800 (4/5) | 0.988 (10/10) | 1.0 | 0.0 |
| multi_location | 0.667 (2/3) | 0.667 (2/3) | 0.400 (2/5) | 0.947 (9/9) | 0.0 | 0.0 |
| missing_jd_culture | 1.000 (5/5) | 1.000 (5/5) | 1.000 (5/5) | 1.000 (10/10) | 0.0 | 0.0 |
| cross_source_repost | 1.000 (4/4) | 1.000 (4/4) | 1.000 (5/5) | 0.713 (7/10) | 0.0 | 1.0 |
| stale_date_unknown | 1.000 (5/5) | 1.000 (5/5) | 1.000 (5/5) | 1.000 (10/10) | 0.0 | 0.0 |
| partial_failure_culture | 1.000 (5/5) | 1.000 (5/5) | 1.000 (5/5) | 1.000 (10/10) | 0.0 | 0.0 |

This baseline is deterministic and offline. Timing, absolute paths, URLs, and generated timestamps are excluded from equality checks.
