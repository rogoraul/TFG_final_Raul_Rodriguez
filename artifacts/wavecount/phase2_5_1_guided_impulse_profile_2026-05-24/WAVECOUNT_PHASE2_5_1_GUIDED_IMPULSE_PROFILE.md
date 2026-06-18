# WaveCount Fase 2.5.1 - Perfil de impulso guiado

## Resumen

Esta fase formaliza un perfil minimo de impulso H4/D1 `intermediate` usando los candidatos `ready_for_phase251_search=yes` de Fase 2.5.0.

No busca en SQL, no recalcula pivotes, no cambia conteos base y no genera senales.

## Seeds

- `impulse_forex_eurusd_h4_intermediate_impulse_007`: score 100, EWO `supports_wave_role`, contexto `context_conflicts_but_explains`.
- `impulse_metals_xagusd_h4_intermediate_impulse_007`: score 100, EWO `supports_wave_role`, contexto `context_confirms_good_count`.
- `impulse_forex_eurusd_h4_intermediate_impulse_012`: score 100, EWO `supports_wave_role`, contexto `context_confirms_good_count`.

## Resultado de aplicacion

- `no`: 121
- `near_miss`: 13
- `yes`: 3

## Accion propuesta para 2.5.2

- `use_as_negative_example`: 74
- `exclude_from_expansion`: 38
- `manual_review_before_expansion`: 22
- `keep_as_seed_example`: 3

## Decision

El perfil guiado minimo es coherente como prototipo metodologico: selecciona solo impulsos H4/D1 `intermediate` ya validados por 2.5.0 y deja major/minor/auxiliares como contexto o subestructura.

No debe convertirse en senal ni filtro operativo. Una futura Fase 2.5.2 podria expandir la busqueda H4/D1 con galeria especifica de matches y near-misses.

## Run meta

```json
{
  "generated_at": "2026-05-24T02:03:57",
  "script": "backtests\\wavecount\\build_wavecount_guided_impulse_profile.py",
  "output_dir": "artifacts\\wavecount\\phase2_5_1_guided_impulse_profile_2026-05-24",
  "source_dir": "artifacts\\wavecount\\phase2_5_0_guided_context_score_2026-05-24",
  "rows": {
    "guided_impulse_seed_profile": 12,
    "guided_impulse_profile_matches": 137,
    "guided_impulse_near_misses": 13,
    "guided_impulse_exclusions_check": 74,
    "phase252_expansion_plan": 137,
    "guided_impulse_best_examples": 16,
    "guided_impulse_user_review_if_any": 22
  },
  "seed_check": {
    "seed_count": 3,
    "all_seed_impulses": true,
    "all_seed_h4_d1": true,
    "all_seed_intermediate": true
  },
  "match_counts": {
    "no": 121,
    "near_miss": 13,
    "yes": 3
  },
  "near_miss_reason_counts": {
    "": 124,
    "minor_substructure": 4,
    "higher_degree_context": 4,
    "auxiliary_timeframe": 4,
    "context_conflict": 1
  },
  "phase252_action_counts": {
    "use_as_negative_example": 74,
    "exclude_from_expansion": 38,
    "manual_review_before_expansion": 22,
    "keep_as_seed_example": 3
  },
  "phase250_best_examples_loaded": 30,
  "phase250_exclusions_loaded": 74,
  "missing_image_refs": [],
  "no_base_counts_modified": true,
  "no_strategy_changes": true,
  "elapsed_seconds": 0.329
}
```
