# WaveCount Phase 2.5.5 Soft Policy Visual Audit

Generated at: 2026-05-24T18:17:33

## Scope

Auditoria visual selectiva de la politica blanda 2.5.4.
No genera senales, no ejecuta backtests y no cambia reglas de pivotes/conteos.

## Exclusion Ratio

- Total scored rows: 108
- Excluded rows: 90
- Excluded share: 83.33%

## Visual Sample

- Selected cases: 37
- Selected excluded cases: 24
- Questionable/false-negative risks: 0
- False-positive risks among kept buckets: 1

## Decision

El ratio 90/108 parece razonable en composicion: la mayoria de exclusiones vienen de `no`, negativos, baja prominencia, contexto misleading o estructuras auxiliares. La auditoria visual no sugiere que la politica sea demasiado estricta; al contrario, detecta al menos un caso mantenido como provisional que parece demasiado pequeno para H4/D1. La siguiente fase deberia ajustar pesos/buckets de prominencia, no relajar la exclusion global.

## Tables

- `tables/exclusion_ratio_diagnostics.csv`
- `tables/visual_audit_selection.csv`
- `tables/visual_policy_case_review.csv`
- `tables/exclusion_bucket_audit.csv`
- `tables/policy_false_negative_risks.csv`
- `tables/policy_false_positive_risks.csv`
- `tables/weight_adjustment_candidates.csv`
- `tables/phase256_recommendation.csv`
- `tables/user_review_if_any.csv`
