# WaveCount Fase 2.5.2b - H1/H4 auxiliar y prominencia

## Resumen

Esta fase revisa H1/H4 como expansion auxiliar y anade diagnostico de escala/prominencia para detectar conteos demasiado pequenos para su timeframe.

No genera senales, no cambia reglas base y no modifica estrategias.

## Resultado H1/H4

- `no`: 42
- `near_miss_aux`: 8
- `yes_aux`: 4

## Prominencia

- `not_applicable`: 84
- `better_as_lower_tf_substructure`: 8
- `ambiguous_scale`: 6
- `too_small_for_timeframe`: 6
- `acceptable_for_timeframe`: 4

## AUS200 H4

El caso `impulse_exp252_index_aus200_h4_intermediate_impulse_020` queda documentado como caso de baja duracion relativa/prominencia temporal para H4 y conflicto de contexto. Debe mantenerse como near-miss/riesgo, no como seed.

## Decision

H1/H4 aporta como auxiliar y zoom de subestructura, pero no sustituye H4/D1 como base principal. El diagnostico de prominencia puede entrar como penalizacion blanda futura.

## Run meta

```json
{
  "generated_at": "2026-05-24T03:04:42",
  "script": "backtests\\wavecount\\build_wavecount_h1_h4_aux_expansion.py",
  "output_dir": "artifacts\\wavecount\\phase2_5_2b_h1_h4_aux_expansion_2026-05-24",
  "phase252_dir": "artifacts\\wavecount\\phase2_5_2_guided_impulse_expansion_2026-05-24",
  "expansion_scope": "h1_h4_auxiliary_windows",
  "symbols": [
    "EURUSD.r",
    "GBPUSD.r",
    "USDJPY.r",
    "AUDJPY.r",
    "EURJPY.r",
    "GBPJPY.r",
    "XAUUSD.r",
    "XAGUSD.r",
    "XPTUSD",
    "XPDUSD",
    "AUS200",
    "HK50",
    "US500",
    "US30"
  ],
  "ltf_rows_per_symbol": 1100,
  "htf_rows": 520,
  "phase23_meta": {
    "charts_ok": 54
  },
  "phase24_meta": {
    "charts_ok": 54
  },
  "rows": {
    "aux_expansion_scope": 1,
    "h1_h4_aux_candidates": 54,
    "h1_h4_aux_matches": 4,
    "h1_h4_aux_near_misses": 8,
    "h1_h4_aux_negatives": 42,
    "prominence_diagnostics": 108,
    "h4_suspicious_scale_cases": 8,
    "aus200_h4_case_review": 1,
    "visual_aux_review": 54,
    "ewo_aux_review": 6,
    "ema_htf_aux_review": 6,
    "phase253_aux_recommendation": 3,
    "user_must_review_if_any": 13
  },
  "aux_match_counts": {
    "no": 42,
    "near_miss_aux": 8,
    "yes_aux": 4
  },
  "aux_near_miss_reason_counts": {
    "": 46,
    "minor_substructure": 4,
    "higher_degree_context": 4
  },
  "scale_fit_counts": {
    "not_applicable": 84,
    "better_as_lower_tf_substructure": 8,
    "ambiguous_scale": 6,
    "too_small_for_timeframe": 6,
    "acceptable_for_timeframe": 4
  },
  "visual_aux_status_counts": {
    "not_usable": 33,
    "useful_lower_tf_substructure": 11,
    "good_negative_example": 9,
    "good_aux_structure": 1
  },
  "aus200_h4_scale_label": "too_small_for_timeframe",
  "missing_image_refs": [],
  "no_strategy_changes": true,
  "no_signals_generated": true,
  "no_base_rules_changed": true,
  "elapsed_seconds": 862.533
}
```
