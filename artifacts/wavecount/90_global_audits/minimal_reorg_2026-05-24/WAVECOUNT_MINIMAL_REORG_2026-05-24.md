# WaveCount minimal reorg 2026-05-24

Migraci?n m?nima de artifacts vigentes de Fase 2.5.x y auditor?as globales.

- Acci?n: copia controlada, sin borrar originales.
- Alcance: solo Fase 2.5.x, auditor?a global y plan de reorganizaci?n.
- C?digo WaveCount: no reorganizado.
- Reglas/conteos/pivotes/se?ales: sin cambios.

## Rutas vigentes
- `artifacts/wavecount/05_guided_profile/phase2_5_0_guided_context_score_2026-05-24` desde `artifacts/wavecount/phase2_5_0_guided_context_score_2026-05-24`
- `artifacts/wavecount/05_guided_profile/phase2_5_1_guided_impulse_profile_2026-05-24` desde `artifacts/wavecount/phase2_5_1_guided_impulse_profile_2026-05-24`
- `artifacts/wavecount/05_guided_profile/phase2_5_2_h4_d1_expansion_2026-05-24` desde `artifacts/wavecount/phase2_5_2_guided_impulse_expansion_2026-05-24`
- `artifacts/wavecount/05_guided_profile/phase2_5_2b_h1_h4_aux_2026-05-24` desde `artifacts/wavecount/phase2_5_2b_h1_h4_aux_expansion_2026-05-24`
- `artifacts/wavecount/05_guided_profile/phase2_5_3_descriptive_stats_2026-05-24` desde `artifacts/wavecount/phase2_5_3_descriptive_stats_2026-05-24`
- `artifacts/wavecount/90_global_audits/global_audit_2026-05-24` desde `artifacts/wavecount/global_audit_2026-05-24`
- `artifacts/wavecount/90_global_audits/reorg_plan_2026-05-24` desde `artifacts/wavecount/reorg_plan_2026-05-24`

## Validaci?n de rutas
- Rutas rotas detectadas tras migraci?n: 296
- Ver detalle en `tables/broken_paths_after_migration.csv`.

## Legacy temporal
Las carpetas originales se mantienen intactas como legacy temporal para trazabilidad.

## Nota de validaci?n
Las rutas concretas referenciadas en columnas de path/chart/doc dentro de las copias nuevas resuelven correctamente. Las rutas propuestas de planes futuros no se tratan como rutas rotas.

## Documentacion actualizada
- `docs/wavecount/INDEX.md` creado como indice humano principal.
- `docs/WAVECOUNT_REORGANIZACION_MINIMA_2026-05-24.md` creado como resumen de migracion.
- Manifest, estado del TFG, roadmap y plan de reorganizacion actualizados.
