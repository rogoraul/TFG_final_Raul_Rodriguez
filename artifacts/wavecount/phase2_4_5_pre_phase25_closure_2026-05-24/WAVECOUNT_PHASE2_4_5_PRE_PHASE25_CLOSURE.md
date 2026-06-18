# WaveCount Fase 2.4.5 - Cierre pre-Fase 2.5

## Resumen ejecutivo

WaveCount queda listo para disenar Fase 2.5 como busqueda guiada por contexto, todavia sin senales ni filtros operativos. La base principal debe ser H4/D1 con grado `intermediate`; `major` queda como contexto o grado superior, y `minor` como subestructura.

La fase no recalcula pivotes, conteos ni senales. Solo consolida decisiones ya auditadas y crea una matriz de trazabilidad.

## Politica sintetica

- `primary_visual_base`: 1 componentes.
- `case_bank_and_substructure`: 1 componentes.
- `microstructure_only`: 1 componentes.
- `primary_degree`: 1 componentes.
- `higher_degree_context`: 1 componentes.
- `substructure_or_failure_bank`: 1 componentes.
- `candidate_rule_input`: 1 componentes.
- `provisional_context`: 1 componentes.
- `context_only`: 1 componentes.
- `uncertainty_label`: 1 componentes.
- `manual_or_experimental`: 1 componentes.
- `soft_context_only`: 1 componentes.
- `soft_quality_filter`: 1 componentes.
- `momentum_role_support`: 1 componentes.
- `regime_context`: 1 componentes.
- `not_ready_as_rule`: 1 componentes.
- `exclude_from_phase25_rules`: 1 componentes.

## Decision pre-2.5

- H4/D1 entra como base principal.
- H1/H4 y M30/H1 quedan auxiliares.
- EMAs 50/150, EWO 5-35 y HTF/D1 entran solo como contexto blando.
- ABC no puede usarse aislado: necesita padre/contexto razonable.
- Parciales 1-2-3 e incertidumbre de onda 5 se mantienen como estados provisionales, nunca senales.
- Correcciones complejas y alternancia completa quedan como trabajo futuro.

## Mejores ejemplos

- `impulse_metals_xagusd_h4_intermediate_impulse_007` (h4_d1_count_only): Muy buen ejemplo H4: onda 3 amplia y onda 5 natural. User: bien.
- `impulse_index_aus200_h4_intermediate_impulse_015` (h4_d1_count_only): Estructura H4 limpia con onda 3 suficiente y 4-5 legibles.
- `partial_123_metals_xagusd_h4_major_partial123_003` (h4_d1_count_only): Major muy solido, con onda 3 amplia y continuacion fuerte. Diagnostico mecanico invalidated_after_3 no se aplica como downgrade duro porque la revision visual muestra continuidad o estructura defendible.
- `partial_123_forex_audjpy_h4_major_partial123_005` (h4_d1_count_only): Muy buen 1-2-3 alcista de grado superior. Diagnostico mecanico belongs_to_prior_wave_45 no se aplica como downgrade duro porque la revision visual muestra continuidad o estructura defendible. User: bien.
- `impulse_forex_eurusd_h4_intermediate_impulse_012` (h4_d1_count_only): Onda 3 clara; tramo algo corto pero defendible. User: bien.
- `impulse_forex_eurusd_h4_intermediate_impulse_007` (h4_d1_count_only): Impulso bajista defendible, escala H4 correcta.
- `partial_123_metals_xagusd_h4_intermediate_partial123_001` (h4_d1_count_only): Buen 1-2-3 alcista con onda 3 visible y continuacion posterior. Diagnostico mecanico partial_123_too_lax no se aplica como downgrade duro porque la revision visual muestra continuidad o estructura defendible. User: bien.
- `impulse_index_aus200_h4_major_impulse_013` (h4_d1_count_only): Bueno visualmente, pero similar al intermediate; tratar como contexto superior.
- `impulse_metals_xagusd_h4_intermediate_impulse_007` (context_confirms_good_count): Mejor caso: conteo limpio, EMAs y D1 alineados, EWO acompana expansion. Buen ejemplo para memoria.
- `partial_123_metals_xagusd_h4_major_partial123_003` (context_confirms_good_count): Buen ejemplo: 1-2-3 precede continuacion fuerte; EWO/EMAs ayudan de verdad.

## Validacion

- Script de cierre ejecutado correctamente.
- CSV principales generados.
- No se han modificado conteos base ni artifacts anteriores.
- No se han cambiado estrategias.

## Archivos generados

- `tables/phase25_readiness_matrix.csv`
- `tables/phase25_inputs_policy.csv`
- `tables/phase25_rule_candidates.csv`
- `tables/phase25_soft_context_features.csv`
- `tables/phase25_exclusions.csv`
- `tables/phase25_future_work.csv`
- `tables/phase25_best_examples.csv`
- `tables/phase25_risk_register.csv`
- `tables/phase25_user_review_if_any.csv`

## Run meta

```json
{
  "generated_at": "2026-05-24T01:11:44",
  "script": "backtests\\wavecount\\build_wavecount_phase25_readiness.py",
  "output_dir": "artifacts\\wavecount\\phase2_4_5_pre_phase25_closure_2026-05-24",
  "source_dirs": {
    "h4_closure": "artifacts\\wavecount\\phase2_3_4_h4_d1_visual_closure_2026-05-23",
    "context": "artifacts\\wavecount\\phase2_4_2_context_quality_audit_2026-05-23",
    "abc_quality": "artifacts\\wavecount\\phase2_4_3_abc_quality_audit_2026-05-23",
    "contextual_corrections": "artifacts\\wavecount\\phase2_4_4_contextual_corrections_2026-05-24",
    "wave5": "artifacts\\wavecount\\phase2_3_1_wave5_endpoint_2026-05-21",
    "partial123": "artifacts\\wavecount\\phase2_3_2_partial123_2026-05-21",
    "degree": "artifacts\\wavecount\\phase2_3_3_degree_calibration_2026-05-23"
  },
  "rows": {
    "phase25_readiness_matrix": 17,
    "phase25_inputs_policy": 6,
    "phase25_rule_candidates": 8,
    "phase25_soft_context_features": 5,
    "phase25_exclusions": 5,
    "phase25_future_work": 4,
    "phase25_best_examples": 18,
    "phase25_risk_register": 6,
    "phase25_user_review_if_any": 11
  },
  "readiness_policy_counts": {
    "primary_visual_base": 1,
    "case_bank_and_substructure": 1,
    "microstructure_only": 1,
    "primary_degree": 1,
    "higher_degree_context": 1,
    "substructure_or_failure_bank": 1,
    "candidate_rule_input": 1,
    "provisional_context": 1,
    "context_only": 1,
    "uncertainty_label": 1,
    "manual_or_experimental": 1,
    "soft_context_only": 1,
    "soft_quality_filter": 1,
    "momentum_role_support": 1,
    "regime_context": 1,
    "not_ready_as_rule": 1,
    "exclude_from_phase25_rules": 1
  },
  "contextual_correction_policy_counts": {
    "exclude_not_correction": 12,
    "manual_contextual_review_only": 8,
    "experimental_unknown_parent": 5,
    "usable_contextual_correction": 4
  },
  "missing_image_refs": [],
  "elapsed_seconds": 0.204,
  "no_base_counts_modified": true,
  "no_strategy_changes": true
}
```
