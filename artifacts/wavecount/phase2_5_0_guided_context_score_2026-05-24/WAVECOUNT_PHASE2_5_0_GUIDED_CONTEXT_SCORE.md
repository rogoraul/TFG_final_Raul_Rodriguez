# WaveCount Fase 2.5.0 - Guided Context Score

## Resumen

Esta fase aplica una capa de scoring/contexto sobre candidatos WaveCount existentes. No recalcula pivotes, no cambia conteos base y no genera senales.

El `guided_quality_score` es una puntuacion metodologica de lectura estructural. No es probabilidad de ganar ni expectativa de rentabilidad.

## Distribucion de calidad

- `exclude`: 74
- `high_quality_context`: 29
- `experimental_only`: 23
- `usable_but_provisional`: 10
- `ambiguous_context`: 1

## Readiness 2.5.1

- `no`: 80
- `manual_review`: 54
- `yes`: 3

## Politica aplicada

- H4/D1 + `intermediate` es la base principal.
- H1/H4 es auxiliar.
- M30/H1 es microestructura/banco de fallos.
- EMAs 50/150, D1/HTF y EWO 5-35 son contexto blando.
- EWO se interpreta por comportamiento relativo/contextual, no por umbrales absolutos fijos.
- ABC solo entra si tiene padre/contexto razonable.
- Parciales 1-2-3 e incertidumbre de onda 5 son provisionales.

## Cierre

Fase 2.5.0 deja preparada la entrada para una Fase 2.5.1 de busqueda mas guiada, todavia sin senales. Los casos `high_quality_context` y algunos `usable_but_provisional` son los candidatos metodologicamente mas limpios.

## Run meta

```json
{
  "generated_at": "2026-05-24T01:45:05",
  "script": "backtests\\wavecount\\build_wavecount_guided_context_score.py",
  "output_dir": "artifacts\\wavecount\\phase2_5_0_guided_context_score_2026-05-24",
  "source_dirs": {
    "readiness": "artifacts\\wavecount\\phase2_4_5_pre_phase25_closure_2026-05-24",
    "h4_closure": "artifacts\\wavecount\\phase2_3_4_h4_d1_visual_closure_2026-05-23",
    "context": "artifacts\\wavecount\\phase2_4_2_context_quality_audit_2026-05-23",
    "corrections": "artifacts\\wavecount\\phase2_4_4_contextual_corrections_2026-05-24",
    "wave5": "artifacts\\wavecount\\phase2_3_1_wave5_endpoint_2026-05-21",
    "partial123": "artifacts\\wavecount\\phase2_3_2_partial123_2026-05-21",
    "degree": "artifacts\\wavecount\\phase2_3_3_degree_calibration_2026-05-23"
  },
  "rows": {
    "guided_context_candidates": 137,
    "guided_quality_summary": 29,
    "ewo_role_context": 137,
    "ema_htf_context_policy": 137,
    "abc_contextual_integration": 29,
    "phase251_search_readiness": 137,
    "guided_context_exclusions": 74,
    "guided_context_best_examples": 30,
    "guided_context_user_review_if_any": 40
  },
  "guided_quality_bucket_counts": {
    "exclude": 74,
    "high_quality_context": 29,
    "experimental_only": 23,
    "usable_but_provisional": 10,
    "ambiguous_context": 1
  },
  "phase251_readiness_counts": {
    "no": 80,
    "manual_review": 54,
    "yes": 3
  },
  "source_candidate_counts": {
    "h4_d1": 54,
    "auxiliary": 54,
    "abc_contextual": 29
  },
  "readiness_components_used": 17,
  "missing_image_refs": [],
  "no_base_counts_modified": true,
  "no_strategy_changes": true,
  "elapsed_seconds": 0.49
}
```
