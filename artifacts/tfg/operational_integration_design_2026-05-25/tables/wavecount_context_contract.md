# Wavecount Context Contract

| rule | design | fields_or_sources | v1_limit |
| --- | --- | --- | --- |
| source_policy | Use 2.5.6 as official bucket source and 2.5.10 as closure/policy matrix. | phase256_policy_scores.csv; phase25_final_policy_matrix.csv | No 2.5.9 bucket replacement. |
| symbol_timeframe_mapping | Map live symbol to WaveCount symbol; prefer H4/D1 context for H1/H4 ENBOLSA, attach H1/H4 auxiliary when available. | symbol, timeframe, source_scope, swing_degree | If no match, wavecount_available=false. |
| multiple_candidates | Prefer latest/current diagnostic candidate by symbol/timeframe/degree if timestamp exists; otherwise expose best policy bucket plus notes and mark selection as diagnostic. | candidate_id, phase256_policy_bucket, chart_path | Do not silently select a trade filter. |
| exclude_bucket | If bucket is exclude_from_guided_search, show as context warning only. | phase256_policy_bucket | Never block ENBOLSA signal in v1. |
| wave3_wave5 | possible_wave3/5 may be displayed and stored for study. | review_category, policy_reasons, wave diagnostics if available | Never create an order from wave role. |
| dashboard_display | Show compact badge: H4/D1 bucket, degree, context_status, prominence warning and link to chart if available. | chart_path, policy_warnings | Read-only display. |
| statistics_storage | Persist bucket, degree, source_scope, prominence, EWO/EMA labels with snapshot/trade join. | phase256 fields | Used for later study only. |
