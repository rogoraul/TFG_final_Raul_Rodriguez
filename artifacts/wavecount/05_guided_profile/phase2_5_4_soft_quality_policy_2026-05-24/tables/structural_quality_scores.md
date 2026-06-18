# structural_quality_scores

## 1. impulse_exp252_forex_audjpy_h4_minor_impulse_004
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: ambiguous_structure
- final_soft_quality_bucket: ambiguous_structure
- prominence_policy_label: better_as_lower_tf_substructure
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; H4/D1 primary scope; visual_status=near_miss_useful; diagnostic suggests lower timeframe / substructure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1939; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: minor is substructure; H4/D1 near_miss stays provisional; better handled as lower-timeframe substructure

![001_impulse_exp252_forex_audjpy_h4_minor_impulse_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/001_impulse_exp252_forex_audjpy_h4_minor_impulse_004.png)

## 2. impulse_exp252_metals_xagusd_h4_minor_impulse_004
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: low_prominence_vs_window
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; H4/D1 primary scope; visual_status=near_miss_useful; too_small_for_timeframe from prominence diagnostics; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.001086; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: minor is substructure; H4/D1 near_miss stays provisional; count is too small or short relative to visible window

![002_impulse_exp252_metals_xagusd_h4_minor_impulse_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/002_impulse_exp252_metals_xagusd_h4_minor_impulse_004.png)

## 3. impulse_exp252_index_aus200_h4_minor_impulse_028
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: low_prominence_vs_window
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; H4/D1 primary scope; visual_status=near_miss_useful; too_small_for_timeframe from prominence diagnostics; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-10.15; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning
- policy_warnings: minor is substructure; H4/D1 near_miss stays provisional; count is too small or short relative to visible window; htf_conflict_warning

![003_impulse_exp252_index_aus200_h4_minor_impulse_028.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/003_impulse_exp252_index_aus200_h4_minor_impulse_028.png)

## 4. impulse_exp252_forex_audjpy_h4_minor_impulse_022
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: low_prominence_vs_window
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; H4/D1 primary scope; visual_status=near_miss_useful; too_small_for_timeframe from prominence diagnostics; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-0.05223; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: minor is substructure; H4/D1 near_miss stays provisional; count is too small or short relative to visible window; EWO supports momentum but not full wave role

![004_impulse_exp252_forex_audjpy_h4_minor_impulse_022.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/004_impulse_exp252_forex_audjpy_h4_minor_impulse_022.png)

## 5. impulse_exp252_forex_audjpy_h4_intermediate_impulse_002
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: high_quality_structure
- final_soft_quality_bucket: high_quality_structure
- prominence_policy_label: acceptable_for_timeframe
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; H4/D1 primary scope; degree=intermediate; H4/D1 profile match=yes; visual_status=strong_match; structure size is acceptable for the reviewed timeframe; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1939; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True

![005_impulse_exp252_forex_audjpy_h4_intermediate_impulse_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/matches/005_impulse_exp252_forex_audjpy_h4_intermediate_impulse_002.png)

## 6. impulse_exp252_metals_xagusd_h4_intermediate_impulse_002
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: usable_provisional_structure
- final_soft_quality_bucket: usable_provisional_structure
- prominence_policy_label: low_prominence_vs_window
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; H4/D1 primary scope; degree=intermediate; H4/D1 profile match=yes; visual_status=strong_match; too_small_for_timeframe from prominence diagnostics; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.001086; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: count is too small or short relative to visible window

![006_impulse_exp252_metals_xagusd_h4_intermediate_impulse_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/matches/006_impulse_exp252_metals_xagusd_h4_intermediate_impulse_002.png)

## 7. impulse_exp252_index_aus200_h4_intermediate_impulse_020
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: low_prominence_vs_window
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; H4/D1 primary scope; degree=intermediate; too_small_for_timeframe from prominence diagnostics; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-10.15; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count
- policy_warnings: H4/D1 near_miss stays provisional; visual_status=false_positive_risk; count is too small or short relative to visible window; htf_conflict_warning; context_must_not_rescue_bad_count

![007_impulse_exp252_index_aus200_h4_intermediate_impulse_020.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/007_impulse_exp252_index_aus200_h4_intermediate_impulse_020.png)

## 8. impulse_exp252_forex_eurjpy_h4_intermediate_impulse_007
- source_scope: h4_d1
- symbol: EURJPY.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: usable_provisional_structure
- final_soft_quality_bucket: usable_provisional_structure
- prominence_policy_label: ambiguous_scale
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; H4/D1 primary scope; degree=intermediate; H4/D1 profile match=yes; visual_status=strong_match; scale diagnostic is ambiguous; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.05803; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: scale is ambiguous

![008_impulse_exp252_forex_eurjpy_h4_intermediate_impulse_007.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/matches/008_impulse_exp252_forex_eurjpy_h4_intermediate_impulse_007.png)

## 9. impulse_exp252_forex_eurusd_h4_major_impulse_016
- source_scope: h4_d1
- symbol: EURUSD.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: usable_provisional_structure
- final_soft_quality_bucket: usable_provisional_structure
- prominence_policy_label: acceptable_for_timeframe
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; H4/D1 primary scope; visual_status=near_miss_useful; structure size is acceptable for the reviewed timeframe; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.0007587; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: major is higher-degree context; H4/D1 near_miss stays provisional

![009_impulse_exp252_forex_eurusd_h4_major_impulse_016.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/009_impulse_exp252_forex_eurusd_h4_major_impulse_016.png)

## 10. impulse_exp252_metals_xagusd_h4_major_impulse_002
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: usable_provisional_structure
- final_soft_quality_bucket: usable_provisional_structure
- prominence_policy_label: ambiguous_scale
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; H4/D1 primary scope; visual_status=near_miss_useful; scale diagnostic is ambiguous; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1927; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: major is higher-degree context; H4/D1 near_miss stays provisional; scale is ambiguous

![010_impulse_exp252_metals_xagusd_h4_major_impulse_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/010_impulse_exp252_metals_xagusd_h4_major_impulse_002.png)

## 11. impulse_exp252_index_aus200_h4_major_impulse_016
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: major
- structural_quality_policy: usable_provisional_structure
- final_soft_quality_bucket: usable_provisional_structure
- prominence_policy_label: acceptable_for_timeframe
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; H4/D1 primary scope; visual_status=near_miss_useful; structure size is acceptable for the reviewed timeframe; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-13.55; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning
- policy_warnings: major is higher-degree context; H4/D1 near_miss stays provisional; htf_conflict_warning

![011_impulse_exp252_index_aus200_h4_major_impulse_016.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/011_impulse_exp252_index_aus200_h4_major_impulse_016.png)

## 12. impulse_exp252_forex_eurusd_h4_major_impulse_029
- source_scope: h4_d1
- symbol: EURUSD.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: low_prominence_vs_window
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; H4/D1 primary scope; visual_status=near_miss_useful; too_small_for_timeframe from prominence diagnostics; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.001054; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning
- policy_warnings: major is higher-degree context; H4/D1 near_miss stays provisional; count is too small or short relative to visible window; htf_conflict_warning

![012_impulse_exp252_forex_eurusd_h4_major_impulse_029.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/near_misses/012_impulse_exp252_forex_eurusd_h4_major_impulse_029.png)

## 13. partial_123_exp252_forex_audjpy_h4_intermediate_partial123_002
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1117; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![013_partial_123_exp252_forex_audjpy_h4_intermediate_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/013_partial_123_exp252_forex_audjpy_h4_intermediate_partial123_002.png)

## 14. partial_123_exp252_metals_xagusd_h4_intermediate_partial123_002
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.5657; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![014_partial_123_exp252_metals_xagusd_h4_intermediate_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/014_partial_123_exp252_metals_xagusd_h4_intermediate_partial123_002.png)

## 15. partial_123_exp252_index_aus200_h4_intermediate_partial123_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=6.54; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![015_partial_123_exp252_index_aus200_h4_intermediate_partial123_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/015_partial_123_exp252_index_aus200_h4_intermediate_partial123_001.png)

## 16. partial_123_exp252_forex_audjpy_h4_intermediate_partial123_004
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1939; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![016_partial_123_exp252_forex_audjpy_h4_intermediate_partial123_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/016_partial_123_exp252_forex_audjpy_h4_intermediate_partial123_004.png)

## 17. partial_123_exp252_forex_audjpy_h4_minor_partial123_002
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.01996; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![017_partial_123_exp252_forex_audjpy_h4_minor_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/017_partial_123_exp252_forex_audjpy_h4_minor_partial123_002.png)

## 18. partial_123_exp252_metals_xagusd_h4_minor_partial123_002
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.19; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![018_partial_123_exp252_metals_xagusd_h4_minor_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/018_partial_123_exp252_metals_xagusd_h4_minor_partial123_002.png)

## 19. partial_123_exp252_index_aus200_h4_minor_partial123_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=6.54; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![019_partial_123_exp252_index_aus200_h4_minor_partial123_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/019_partial_123_exp252_index_aus200_h4_minor_partial123_001.png)

## 20. partial_123_exp252_forex_audjpy_h4_minor_partial123_004
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1117; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![020_partial_123_exp252_forex_audjpy_h4_minor_partial123_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/020_partial_123_exp252_forex_audjpy_h4_minor_partial123_004.png)

## 21. partial_123_exp252_forex_audjpy_h4_major_partial123_002
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1939; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![021_partial_123_exp252_forex_audjpy_h4_major_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/021_partial_123_exp252_forex_audjpy_h4_major_partial123_002.png)

## 22. partial_123_exp252_metals_xagusd_h4_major_partial123_002
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.001086; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![022_partial_123_exp252_metals_xagusd_h4_major_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/022_partial_123_exp252_metals_xagusd_h4_major_partial123_002.png)

## 23. partial_123_exp252_index_aus200_h4_major_partial123_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=6.54; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![023_partial_123_exp252_index_aus200_h4_major_partial123_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/023_partial_123_exp252_index_aus200_h4_major_partial123_001.png)

## 24. partial_123_exp252_forex_audjpy_h4_major_partial123_005
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.3213; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=False; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; htf_conflict_warning; context_must_not_rescue_bad_count

![024_partial_123_exp252_forex_audjpy_h4_major_partial123_005.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/024_partial_123_exp252_forex_audjpy_h4_major_partial123_005.png)

## 25. abc_exp252_forex_audjpy_h4_intermediate_abc_002
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1117; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![025_abc_exp252_forex_audjpy_h4_intermediate_abc_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/025_abc_exp252_forex_audjpy_h4_intermediate_abc_002.png)

## 26. abc_exp252_metals_xagusd_h4_intermediate_abc_002
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.5657; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![026_abc_exp252_metals_xagusd_h4_intermediate_abc_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/026_abc_exp252_metals_xagusd_h4_intermediate_abc_002.png)

## 27. abc_exp252_index_aus200_h4_intermediate_abc_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=6.54; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![027_abc_exp252_index_aus200_h4_intermediate_abc_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/027_abc_exp252_index_aus200_h4_intermediate_abc_001.png)

## 28. abc_exp252_forex_audjpy_h4_intermediate_abc_004
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1939; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![028_abc_exp252_forex_audjpy_h4_intermediate_abc_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/028_abc_exp252_forex_audjpy_h4_intermediate_abc_004.png)

## 29. abc_exp252_forex_audjpy_h4_minor_abc_004
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1117; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![029_abc_exp252_forex_audjpy_h4_minor_abc_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/029_abc_exp252_forex_audjpy_h4_minor_abc_004.png)

## 30. abc_exp252_metals_xagusd_h4_minor_abc_004
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.5657; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![030_abc_exp252_metals_xagusd_h4_minor_abc_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/030_abc_exp252_metals_xagusd_h4_minor_abc_004.png)

## 31. abc_exp252_index_aus200_h4_minor_abc_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=6.54; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![031_abc_exp252_index_aus200_h4_minor_abc_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/031_abc_exp252_index_aus200_h4_minor_abc_001.png)

## 32. abc_exp252_forex_audjpy_h4_minor_abc_006
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1939; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![032_abc_exp252_forex_audjpy_h4_minor_abc_006.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/032_abc_exp252_forex_audjpy_h4_minor_abc_006.png)

## 33. abc_exp252_forex_audjpy_h4_major_abc_002
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1939; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![033_abc_exp252_forex_audjpy_h4_major_abc_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/033_abc_exp252_forex_audjpy_h4_major_abc_002.png)

## 34. abc_exp252_metals_xagusd_h4_major_abc_002
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.001086; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![034_abc_exp252_metals_xagusd_h4_major_abc_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/034_abc_exp252_metals_xagusd_h4_major_abc_002.png)

## 35. abc_exp252_index_aus200_h4_major_abc_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=6.54; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![035_abc_exp252_index_aus200_h4_major_abc_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/035_abc_exp252_index_aus200_h4_major_abc_001.png)

## 36. abc_exp252_forex_audjpy_h4_major_abc_005
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.3213; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=False; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; htf_conflict_warning; context_must_not_rescue_bad_count

![036_abc_exp252_forex_audjpy_h4_major_abc_005.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/036_abc_exp252_forex_audjpy_h4_major_abc_005.png)

## 37. near_miss_exp252_forex_audjpy_h4_intermediate_impulse_004
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=medium_small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.03629; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![037_near_miss_exp252_forex_audjpy_h4_intermediate_impulse_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/037_near_miss_exp252_forex_audjpy_h4_intermediate_impulse_004.png)

## 38. near_miss_exp252_metals_xagusd_h4_intermediate_impulse_004
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.05813; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![038_near_miss_exp252_metals_xagusd_h4_intermediate_impulse_004.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/038_near_miss_exp252_metals_xagusd_h4_intermediate_impulse_004.png)

## 39. near_miss_exp252_index_aus200_h4_intermediate_impulse_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; end_ewo_direction=negative; end_ewo_slope=-2.571; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![039_near_miss_exp252_index_aus200_h4_intermediate_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/039_near_miss_exp252_index_aus200_h4_intermediate_impulse_001.png)

## 40. near_miss_exp252_forex_audjpy_h4_minor_impulse_006
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=medium_small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.03629; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![040_near_miss_exp252_forex_audjpy_h4_minor_impulse_006.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/040_near_miss_exp252_forex_audjpy_h4_minor_impulse_006.png)

## 41. near_miss_exp252_metals_xagusd_h4_minor_impulse_006
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.05813; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![041_near_miss_exp252_metals_xagusd_h4_minor_impulse_006.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/041_near_miss_exp252_metals_xagusd_h4_minor_impulse_006.png)

## 42. near_miss_exp252_index_aus200_h4_minor_impulse_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; end_ewo_direction=negative; end_ewo_slope=-2.571; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; minor is substructure; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![042_near_miss_exp252_index_aus200_h4_minor_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/042_near_miss_exp252_index_aus200_h4_minor_impulse_001.png)

## 43. near_miss_exp252_forex_audjpy_h4_major_impulse_002
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.001086; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![043_near_miss_exp252_forex_audjpy_h4_major_impulse_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/043_near_miss_exp252_forex_audjpy_h4_major_impulse_002.png)

## 44. near_miss_exp252_metals_xagusd_h4_major_impulse_006
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=medium_small; input_label=unclear; end_ewo_direction=negative; end_ewo_slope=0.7878; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=inside_band; htf_match=True; ltf_match=True; price_inside_ema_band_adds_ambiguity; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; price_inside_ema_band_adds_ambiguity; context_must_not_rescue_bad_count

![044_near_miss_exp252_metals_xagusd_h4_major_impulse_006.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/044_near_miss_exp252_metals_xagusd_h4_major_impulse_006.png)

## 45. near_miss_exp252_index_aus200_h4_major_impulse_001
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; end_ewo_direction=negative; end_ewo_slope=-2.571; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; major is higher-degree context; H4/D1 profile match=no; visual_status=not_usable; EWO context is unclear or unavailable; context_must_not_rescue_bad_count

![045_near_miss_exp252_index_aus200_h4_major_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/045_near_miss_exp252_index_aus200_h4_major_impulse_001.png)

## 46. hard_invalid_exp252_forex_audjpy_h4_intermediate_impulse_001
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=medium_small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.04829; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: hard_invalid_not_primary_profile; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![046_hard_invalid_exp252_forex_audjpy_h4_intermediate_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/046_hard_invalid_exp252_forex_audjpy_h4_intermediate_impulse_001.png)

## 47. hard_invalid_exp252_metals_xagusd_h4_intermediate_impulse_001
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.2396; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: hard_invalid_not_primary_profile; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![047_hard_invalid_exp252_metals_xagusd_h4_intermediate_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/047_hard_invalid_exp252_metals_xagusd_h4_intermediate_impulse_001.png)

## 48. hard_invalid_exp252_index_aus200_h4_intermediate_impulse_002
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: H4/D1 primary scope; degree=intermediate; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-35.16; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![048_hard_invalid_exp252_index_aus200_h4_intermediate_impulse_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/048_hard_invalid_exp252_index_aus200_h4_intermediate_impulse_002.png)

## 49. hard_invalid_exp252_forex_audjpy_h4_minor_impulse_001
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.0908; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: hard_invalid_not_primary_profile; minor is substructure; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![049_hard_invalid_exp252_forex_audjpy_h4_minor_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/049_hard_invalid_exp252_forex_audjpy_h4_minor_impulse_001.png)

## 50. hard_invalid_exp252_metals_xagusd_h4_minor_impulse_001
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.09709; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: hard_invalid_not_primary_profile; minor is substructure; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![050_hard_invalid_exp252_metals_xagusd_h4_minor_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/050_hard_invalid_exp252_metals_xagusd_h4_minor_impulse_001.png)

## 51. hard_invalid_exp252_index_aus200_h4_minor_impulse_002
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-35.16; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; minor is substructure; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![051_hard_invalid_exp252_index_aus200_h4_minor_impulse_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/051_hard_invalid_exp252_index_aus200_h4_minor_impulse_002.png)

## 52. hard_invalid_exp252_forex_audjpy_h4_major_impulse_001
- source_scope: h4_d1
- symbol: AUDJPY.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.09464; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; major is higher-degree context; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![052_hard_invalid_exp252_forex_audjpy_h4_major_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/052_hard_invalid_exp252_forex_audjpy_h4_major_impulse_001.png)

## 53. hard_invalid_exp252_metals_xagusd_h4_major_impulse_001
- source_scope: h4_d1
- symbol: XAGUSD.r
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; relative_structure_size=small; input_label=unclear; end_ewo_direction=positive; end_ewo_slope=-0.09997; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: hard_invalid_not_primary_profile; major is higher-degree context; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![053_hard_invalid_exp252_metals_xagusd_h4_major_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/053_hard_invalid_exp252_metals_xagusd_h4_major_impulse_001.png)

## 54. hard_invalid_exp252_index_aus200_h4_major_impulse_002
- source_scope: h4_d1
- symbol: AUS200
- timeframe: H4
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: ewo_unclear_or_unavailable
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: H4/D1 primary scope; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=unclear; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-35.16; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; major is higher-degree context; H4/D1 profile match=no; visual_status=good_negative_example; EWO context is unclear or unavailable; htf_conflict_warning

![054_hard_invalid_exp252_index_aus200_h4_major_impulse_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24/charts/negatives/054_hard_invalid_exp252_index_aus200_h4_major_impulse_002.png)

## 55. impulse_aux252b_forex_audjpy_h1_minor_impulse_007
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: better_as_lower_tf_substructure
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; visual_status=useful_lower_tf_substructure; diagnostic suggests lower timeframe / substructure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.06173; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning
- policy_warnings: H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 near_miss_aux; better handled as lower-timeframe substructure; htf_conflict_warning

![001_impulse_aux252b_forex_audjpy_h1_minor_impulse_007.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_near_misses/001_impulse_aux252b_forex_audjpy_h1_minor_impulse_007.png)

## 56. impulse_aux252b_metals_xagusd_h1_minor_impulse_005
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: experimental_only
- final_soft_quality_bucket: experimental_only
- prominence_policy_label: better_as_lower_tf_substructure
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; visual_status=useful_lower_tf_substructure; diagnostic suggests lower timeframe / substructure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.4272; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 near_miss_aux; better handled as lower-timeframe substructure

![002_impulse_aux252b_metals_xagusd_h1_minor_impulse_005.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_near_misses/002_impulse_aux252b_metals_xagusd_h1_minor_impulse_005.png)

## 57. impulse_aux252b_index_aus200_h1_minor_impulse_014
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: experimental_only
- final_soft_quality_bucket: experimental_only
- prominence_policy_label: better_as_lower_tf_substructure
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; visual_status=useful_lower_tf_substructure; diagnostic suggests lower timeframe / substructure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-9.233; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning
- policy_warnings: H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 near_miss_aux; better handled as lower-timeframe substructure; htf_conflict_warning

![003_impulse_aux252b_index_aus200_h1_minor_impulse_014.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_near_misses/003_impulse_aux252b_index_aus200_h1_minor_impulse_014.png)

## 58. impulse_aux252b_forex_audjpy_h1_minor_impulse_016
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: experimental_only
- final_soft_quality_bucket: experimental_only
- prominence_policy_label: better_as_lower_tf_substructure
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; visual_status=useful_lower_tf_substructure; diagnostic suggests lower timeframe / substructure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.2022; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 near_miss_aux; better handled as lower-timeframe substructure

![004_impulse_aux252b_forex_audjpy_h1_minor_impulse_016.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_near_misses/004_impulse_aux252b_forex_audjpy_h1_minor_impulse_016.png)

## 59. impulse_aux252b_forex_audjpy_h1_intermediate_impulse_016
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: auxiliary_substructure
- final_soft_quality_bucket: auxiliary_substructure
- prominence_policy_label: ambiguous_scale
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; degree=intermediate; H1/H4 auxiliary match=yes_aux; visual_status=good_aux_structure; scale diagnostic is ambiguous; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.2648; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: H1/H4 is auxiliary, not primary; scale is ambiguous

![005_impulse_aux252b_forex_audjpy_h1_intermediate_impulse_016.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_matches/005_impulse_aux252b_forex_audjpy_h1_intermediate_impulse_016.png)

## 60. impulse_aux252b_metals_xagusd_h1_intermediate_impulse_036
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: auxiliary_substructure
- final_soft_quality_bucket: auxiliary_substructure
- prominence_policy_label: better_as_lower_tf_substructure
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; degree=intermediate; H1/H4 auxiliary match=yes_aux; visual_status=useful_lower_tf_substructure; diagnostic suggests lower timeframe / substructure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_momentum_only; end_ewo_direction=negative; end_ewo_slope=0.4893; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=below_band; htf_match=True; ltf_match=True
- policy_warnings: H1/H4 is auxiliary, not primary; better handled as lower-timeframe substructure; EWO supports momentum but not full wave role

![006_impulse_aux252b_metals_xagusd_h1_intermediate_impulse_036.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_matches/006_impulse_aux252b_metals_xagusd_h1_intermediate_impulse_036.png)

## 61. impulse_aux252b_index_aus200_h1_intermediate_impulse_007
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: auxiliary_substructure
- final_soft_quality_bucket: auxiliary_substructure
- prominence_policy_label: better_as_lower_tf_substructure
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; degree=intermediate; H1/H4 auxiliary match=yes_aux; visual_status=useful_lower_tf_substructure; diagnostic suggests lower timeframe / substructure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=9.231; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: H1/H4 is auxiliary, not primary; better handled as lower-timeframe substructure

![007_impulse_aux252b_index_aus200_h1_intermediate_impulse_007.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_matches/007_impulse_aux252b_index_aus200_h1_intermediate_impulse_007.png)

## 62. impulse_aux252b_forex_audjpy_h1_intermediate_impulse_022
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: auxiliary_substructure
- final_soft_quality_bucket: auxiliary_substructure
- prominence_policy_label: better_as_lower_tf_substructure
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; degree=intermediate; H1/H4 auxiliary match=yes_aux; visual_status=useful_lower_tf_substructure; diagnostic suggests lower timeframe / substructure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-0.06506; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: H1/H4 is auxiliary, not primary; better handled as lower-timeframe substructure; EWO supports momentum but not full wave role

![008_impulse_aux252b_forex_audjpy_h1_intermediate_impulse_022.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_matches/008_impulse_aux252b_forex_audjpy_h1_intermediate_impulse_022.png)

## 63. impulse_aux252b_forex_audjpy_h1_major_impulse_006
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: auxiliary_substructure
- final_soft_quality_bucket: auxiliary_substructure
- prominence_policy_label: ambiguous_scale
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: structure=impulse; visual_status=useful_lower_tf_substructure; scale diagnostic is ambiguous; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.2648; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True
- policy_warnings: H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 near_miss_aux; scale is ambiguous

![009_impulse_aux252b_forex_audjpy_h1_major_impulse_006.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_near_misses/009_impulse_aux252b_forex_audjpy_h1_major_impulse_006.png)

## 64. impulse_aux252b_metals_xagusd_h1_major_impulse_025
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: auxiliary_substructure
- final_soft_quality_bucket: auxiliary_substructure
- prominence_policy_label: acceptable_for_timeframe
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; visual_status=useful_lower_tf_substructure; structure size is acceptable for the reviewed timeframe; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.01036; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=above_band; htf_match=False; ltf_match=True; htf_conflict_warning
- policy_warnings: H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 near_miss_aux; htf_conflict_warning

![010_impulse_aux252b_metals_xagusd_h1_major_impulse_025.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_near_misses/010_impulse_aux252b_metals_xagusd_h1_major_impulse_025.png)

## 65. impulse_aux252b_index_aus200_h1_major_impulse_028
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: major
- structural_quality_policy: auxiliary_substructure
- final_soft_quality_bucket: auxiliary_substructure
- prominence_policy_label: ambiguous_scale
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; visual_status=useful_lower_tf_substructure; scale diagnostic is ambiguous; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-49.28; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning
- policy_warnings: H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 near_miss_aux; scale is ambiguous; htf_conflict_warning

![011_impulse_aux252b_index_aus200_h1_major_impulse_028.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_near_misses/011_impulse_aux252b_index_aus200_h1_major_impulse_028.png)

## 66. impulse_aux252b_forex_audjpy_h1_major_impulse_017
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: experimental_only
- final_soft_quality_bucket: experimental_only
- prominence_policy_label: ambiguous_scale
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: structure=impulse; visual_status=useful_lower_tf_substructure; scale diagnostic is ambiguous; relative_structure_size=medium_small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-0.06231; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning
- policy_warnings: H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 near_miss_aux; scale is ambiguous; EWO supports momentum but not full wave role; htf_conflict_warning

![012_impulse_aux252b_forex_audjpy_h1_major_impulse_017.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_near_misses/012_impulse_aux252b_forex_audjpy_h1_major_impulse_017.png)

## 67. partial_123_aux252b_forex_audjpy_h1_intermediate_partial123_002
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1089; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![013_partial_123_aux252b_forex_audjpy_h1_intermediate_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/013_partial_123_aux252b_forex_audjpy_h1_intermediate_partial123_002.png)

## 68. partial_123_aux252b_metals_xagusd_h1_intermediate_partial123_001
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.5814; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![014_partial_123_aux252b_metals_xagusd_h1_intermediate_partial123_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/014_partial_123_aux252b_metals_xagusd_h1_intermediate_partial123_001.png)

## 69. partial_123_aux252b_index_aus200_h1_intermediate_partial123_003
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=23.39; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![015_partial_123_aux252b_index_aus200_h1_intermediate_partial123_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/015_partial_123_aux252b_index_aus200_h1_intermediate_partial123_003.png)

## 70. partial_123_aux252b_forex_audjpy_h1_intermediate_partial123_005
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.06173; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; htf_conflict_warning; context_must_not_rescue_bad_count

![016_partial_123_aux252b_forex_audjpy_h1_intermediate_partial123_005.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/016_partial_123_aux252b_forex_audjpy_h1_intermediate_partial123_005.png)

## 71. partial_123_aux252b_forex_audjpy_h1_minor_partial123_002
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1089; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![017_partial_123_aux252b_forex_audjpy_h1_minor_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/017_partial_123_aux252b_forex_audjpy_h1_minor_partial123_002.png)

## 72. partial_123_aux252b_metals_xagusd_h1_minor_partial123_001
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1999; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![018_partial_123_aux252b_metals_xagusd_h1_minor_partial123_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/018_partial_123_aux252b_metals_xagusd_h1_minor_partial123_001.png)

## 73. partial_123_aux252b_index_aus200_h1_minor_partial123_007
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=18.82; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![019_partial_123_aux252b_index_aus200_h1_minor_partial123_007.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/019_partial_123_aux252b_index_aus200_h1_minor_partial123_007.png)

## 74. partial_123_aux252b_forex_audjpy_h1_minor_partial123_007
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.1632; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; htf_conflict_warning; context_must_not_rescue_bad_count

![020_partial_123_aux252b_forex_audjpy_h1_minor_partial123_007.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/020_partial_123_aux252b_forex_audjpy_h1_minor_partial123_007.png)

## 75. partial_123_aux252b_forex_audjpy_h1_major_partial123_001
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.06173; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; htf_conflict_warning; context_must_not_rescue_bad_count

![021_partial_123_aux252b_forex_audjpy_h1_major_partial123_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/021_partial_123_aux252b_forex_audjpy_h1_major_partial123_001.png)

## 76. partial_123_aux252b_metals_xagusd_h1_major_partial123_002
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-1.43; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=inside_band; htf_match=False; ltf_match=False; price_inside_ema_band_adds_ambiguity; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; price_inside_ema_band_adds_ambiguity; htf_conflict_warning; context_must_not_rescue_bad_count

![022_partial_123_aux252b_metals_xagusd_h1_major_partial123_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/022_partial_123_aux252b_metals_xagusd_h1_major_partial123_002.png)

## 77. partial_123_aux252b_index_aus200_h1_major_partial123_003
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=9.231; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![023_partial_123_aux252b_index_aus200_h1_major_partial123_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/023_partial_123_aux252b_index_aus200_h1_major_partial123_003.png)

## 78. partial_123_aux252b_forex_audjpy_h1_major_partial123_006
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1501; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: partial_123_is_provisional_context_only; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![024_partial_123_aux252b_forex_audjpy_h1_major_partial123_006.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/024_partial_123_aux252b_forex_audjpy_h1_major_partial123_006.png)

## 79. abc_aux252b_forex_audjpy_h1_intermediate_abc_002
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1089; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![025_abc_aux252b_forex_audjpy_h1_intermediate_abc_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/025_abc_aux252b_forex_audjpy_h1_intermediate_abc_002.png)

## 80. abc_aux252b_metals_xagusd_h1_intermediate_abc_003
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.4272; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![026_abc_aux252b_metals_xagusd_h1_intermediate_abc_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/026_abc_aux252b_metals_xagusd_h1_intermediate_abc_003.png)

## 81. abc_aux252b_index_aus200_h1_intermediate_abc_003
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=23.39; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![027_abc_aux252b_index_aus200_h1_intermediate_abc_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/027_abc_aux252b_index_aus200_h1_intermediate_abc_003.png)

## 82. abc_aux252b_forex_audjpy_h1_intermediate_abc_005
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.06173; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; htf_conflict_warning; context_must_not_rescue_bad_count

![028_abc_aux252b_forex_audjpy_h1_intermediate_abc_005.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/028_abc_aux252b_forex_audjpy_h1_intermediate_abc_005.png)

## 83. abc_aux252b_forex_audjpy_h1_minor_abc_002
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1089; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![029_abc_aux252b_forex_audjpy_h1_minor_abc_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/029_abc_aux252b_forex_audjpy_h1_minor_abc_002.png)

## 84. abc_aux252b_metals_xagusd_h1_minor_abc_005
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.08954; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![030_abc_aux252b_metals_xagusd_h1_minor_abc_005.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/030_abc_aux252b_metals_xagusd_h1_minor_abc_005.png)

## 85. abc_aux252b_index_aus200_h1_minor_abc_003
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=23.39; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![031_abc_aux252b_index_aus200_h1_minor_abc_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/031_abc_aux252b_index_aus200_h1_minor_abc_003.png)

## 86. abc_aux252b_forex_audjpy_h1_minor_abc_007
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.1632; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; htf_conflict_warning; context_must_not_rescue_bad_count

![032_abc_aux252b_forex_audjpy_h1_minor_abc_007.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/032_abc_aux252b_forex_audjpy_h1_minor_abc_007.png)

## 87. abc_aux252b_forex_audjpy_h1_major_abc_001
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.06173; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; htf_conflict_warning; context_must_not_rescue_bad_count

![033_abc_aux252b_forex_audjpy_h1_major_abc_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/033_abc_aux252b_forex_audjpy_h1_major_abc_001.png)

## 88. abc_aux252b_metals_xagusd_h1_major_abc_002
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-1.43; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=inside_band; htf_match=False; ltf_match=False; price_inside_ema_band_adds_ambiguity; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; price_inside_ema_band_adds_ambiguity; htf_conflict_warning; context_must_not_rescue_bad_count

![034_abc_aux252b_metals_xagusd_h1_major_abc_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/034_abc_aux252b_metals_xagusd_h1_major_abc_002.png)

## 89. abc_aux252b_index_aus200_h1_major_abc_003
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=9.231; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![035_abc_aux252b_index_aus200_h1_major_abc_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/035_abc_aux252b_index_aus200_h1_major_abc_003.png)

## 90. abc_aux252b_forex_audjpy_h1_major_abc_006
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.1501; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: abc_requires_parent_context; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![036_abc_aux252b_forex_audjpy_h1_major_abc_006.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/036_abc_aux252b_forex_audjpy_h1_major_abc_006.png)

## 91. near_miss_aux252b_forex_audjpy_h1_intermediate_impulse_005
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-0.3061; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; EWO supports momentum but not full wave role; htf_conflict_warning

![037_near_miss_aux252b_forex_audjpy_h1_intermediate_impulse_005.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/037_near_miss_aux252b_forex_audjpy_h1_intermediate_impulse_005.png)

## 92. near_miss_aux252b_metals_xagusd_h1_intermediate_impulse_003
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=1.156; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![038_near_miss_aux252b_metals_xagusd_h1_intermediate_impulse_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/038_near_miss_aux252b_metals_xagusd_h1_intermediate_impulse_003.png)

## 93. near_miss_aux252b_index_aus200_h1_intermediate_impulse_003
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-2.569; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=not_usable; EWO supports momentum but not full wave role; context_must_not_rescue_bad_count

![039_near_miss_aux252b_index_aus200_h1_intermediate_impulse_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/039_near_miss_aux252b_index_aus200_h1_intermediate_impulse_003.png)

## 94. near_miss_aux252b_forex_audjpy_h1_minor_impulse_009
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-0.05136; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=above_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; EWO supports momentum but not full wave role; htf_conflict_warning; context_must_not_rescue_bad_count

![040_near_miss_aux252b_forex_audjpy_h1_minor_impulse_009.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/040_near_miss_aux252b_forex_audjpy_h1_minor_impulse_009.png)

## 95. near_miss_aux252b_metals_xagusd_h1_minor_impulse_012
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-0.03389; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; EWO supports momentum but not full wave role; htf_conflict_warning

![041_near_miss_aux252b_metals_xagusd_h1_minor_impulse_012.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/041_near_miss_aux252b_metals_xagusd_h1_minor_impulse_012.png)

## 96. near_miss_aux252b_index_aus200_h1_minor_impulse_003
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-2.569; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=not_usable; EWO supports momentum but not full wave role; context_must_not_rescue_bad_count

![042_near_miss_aux252b_index_aus200_h1_minor_impulse_003.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/042_near_miss_aux252b_index_aus200_h1_minor_impulse_003.png)

## 97. near_miss_aux252b_forex_audjpy_h1_major_impulse_019
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.004586; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=True; htf_conflict_warning; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; htf_conflict_warning; context_must_not_rescue_bad_count

![043_near_miss_aux252b_forex_audjpy_h1_major_impulse_019.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/043_near_miss_aux252b_forex_audjpy_h1_major_impulse_019.png)

## 98. near_miss_aux252b_metals_xagusd_h1_major_impulse_002
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_momentum_only; end_ewo_direction=positive; end_ewo_slope=-0.9911; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=above_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; EWO supports momentum but not full wave role; htf_conflict_warning

![044_near_miss_aux252b_metals_xagusd_h1_major_impulse_002.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/044_near_miss_aux252b_metals_xagusd_h1_major_impulse_002.png)

## 99. near_miss_aux252b_index_aus200_h1_major_impulse_007
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=12.93; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_must_not_rescue_bad_count; context_support_on_no_profile_is_not_validation
- policy_warnings: near_miss_not_primary_profile; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=not_usable; context_must_not_rescue_bad_count

![045_near_miss_aux252b_index_aus200_h1_major_impulse_007.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/045_near_miss_aux252b_index_aus200_h1_major_impulse_007.png)

## 100. hard_invalid_aux252b_forex_audjpy_h1_intermediate_impulse_001
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.1675; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=False; htf_conflict_warning; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=good_negative_example; htf_conflict_warning

![046_hard_invalid_aux252b_forex_audjpy_h1_intermediate_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/046_hard_invalid_aux252b_forex_audjpy_h1_intermediate_impulse_001.png)

## 101. hard_invalid_aux252b_metals_xagusd_h1_intermediate_impulse_001
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.4272; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=good_negative_example

![047_hard_invalid_aux252b_metals_xagusd_h1_intermediate_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/047_hard_invalid_aux252b_metals_xagusd_h1_intermediate_impulse_001.png)

## 102. hard_invalid_aux252b_index_aus200_h1_intermediate_impulse_001
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: intermediate
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: degree=intermediate; no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=23.39; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; H1/H4 profile match=no; visual_status=good_negative_example

![048_hard_invalid_aux252b_index_aus200_h1_intermediate_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/048_hard_invalid_aux252b_index_aus200_h1_intermediate_impulse_001.png)

## 103. hard_invalid_aux252b_forex_audjpy_h1_minor_impulse_001
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_correction_context
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: prominence_vs_window < 0.18; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=negative; end_ewo_slope=-0.1675; input_label=explains_correction; trend_context_label=correction_against_htf; ema_band=below_band; htf_match=False; ltf_match=False; htf_conflict_warning; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=good_negative_example; htf_conflict_warning

![049_hard_invalid_aux252b_forex_audjpy_h1_minor_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/049_hard_invalid_aux252b_forex_audjpy_h1_minor_impulse_001.png)

## 104. hard_invalid_aux252b_metals_xagusd_h1_minor_impulse_001
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; soft_threshold_candidate: duration_vs_window < 0.08; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.5814; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=good_negative_example

![050_hard_invalid_aux252b_metals_xagusd_h1_minor_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/050_hard_invalid_aux252b_metals_xagusd_h1_minor_impulse_001.png)

## 105. hard_invalid_aux252b_index_aus200_h1_minor_impulse_001
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: minor
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; relative_structure_size=medium_small; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=23.39; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; minor is substructure; H1/H4 profile match=no; visual_status=good_negative_example

![051_hard_invalid_aux252b_index_aus200_h1_minor_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/051_hard_invalid_aux252b_index_aus200_h1_minor_impulse_001.png)

## 106. hard_invalid_aux252b_forex_audjpy_h1_major_impulse_001
- source_scope: h1_h4
- symbol: AUDJPY.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: momentum_context_only
- ema_htf_policy_label: ema_htf_misleading_warning
- policy_reasons: no prominence penalty available for this structure; input_label=supports_momentum_only; end_ewo_direction=negative; end_ewo_slope=0.07697; input_label=misleading; trend_context_label=conflict_with_htf; ema_band=below_band; htf_match=False; ltf_match=False; htf_conflict_warning
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=good_negative_example; EWO supports momentum but not full wave role; htf_conflict_warning

![052_hard_invalid_aux252b_forex_audjpy_h1_major_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/052_hard_invalid_aux252b_forex_audjpy_h1_major_impulse_001.png)

## 107. hard_invalid_aux252b_metals_xagusd_h1_major_impulse_001
- source_scope: h1_h4
- symbol: XAGUSD.r
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=0.3068; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=good_negative_example

![053_hard_invalid_aux252b_metals_xagusd_h1_major_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/053_hard_invalid_aux252b_metals_xagusd_h1_major_impulse_001.png)

## 108. hard_invalid_aux252b_index_aus200_h1_major_impulse_001
- source_scope: h1_h4
- symbol: AUS200
- timeframe: H1
- swing_degree: major
- structural_quality_policy: exclude_from_guided_search
- final_soft_quality_bucket: exclude_from_guided_search
- prominence_policy_label: prominence_not_applicable
- ewo_policy_label: relative_wave_role_support
- ema_htf_policy_label: ema_htf_context_support
- policy_reasons: no prominence penalty available for this structure; input_label=supports_wave_role; momentum_matches_direction=True; end_ewo_direction=positive; end_ewo_slope=9.231; input_label=supports_context; trend_context_label=impulse_with_htf; ema_band=above_band; htf_match=True; ltf_match=True; context_support_on_no_profile_is_not_validation
- policy_warnings: hard_invalid_not_primary_profile; H1/H4 is auxiliary, not primary; major is higher-degree context; H1/H4 profile match=no; visual_status=good_negative_example

![054_hard_invalid_aux252b_index_aus200_h1_major_impulse_001.png](C:/Users/ralr1/Desktop/CD/TFG/TFG-Raul_Rodriguez/artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24/charts/h1_h4_negatives/054_hard_invalid_aux252b_index_aus200_h1_major_impulse_001.png)
