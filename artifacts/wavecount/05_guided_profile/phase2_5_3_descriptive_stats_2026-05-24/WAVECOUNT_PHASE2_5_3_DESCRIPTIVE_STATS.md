# WaveCount Phase 2.5.3 Descriptive Stats

Generated at: 2026-05-24T12:06:31

## Scope

This phase consolidates descriptive statistics from WaveCount 2.5.0, 2.5.1, 2.5.2 and 2.5.2b.
It does not generate signals, does not run backtests and does not change pivots, degrees or count rules.

## Main Counts

- H4/D1 yes: 3
- H4/D1 near_miss: 9
- H4/D1 no: 42
- H1/H4 yes_aux: 4
- H1/H4 near_miss_aux: 8
- H1/H4 no: 42

## Prominence

- Prominence problem cases: 20
- Recommendation: move prominence/size to a soft penalty candidate in Phase 2.5.4.

## EWO / EMA / HTF

- EWO remains useful as contextual momentum / wave-role support, not as autonomous wave label.
- EMA 50/150 and HTF remain useful as soft context, not as hard validation.

## Decision

- H4/D1 intermediate remains the primary WaveCount base.
- H1/H4 remains auxiliary / zoom / substructure.
- Phase 2.5.4 should formalize soft prominence, EWO and EMA/HTF policies without creating signals.

## Tables

- `tables/dataset_inventory.csv`
- `tables/classification_stats_h4_d1.csv`
- `tables/classification_stats_h1_h4.csv`
- `tables/prominence_stats.csv`
- `tables/ewo_stats.csv`
- `tables/ema_htf_stats.csv`
- `tables/phase254_readiness_matrix.csv`

## Charts

- `charts/classification_summary.png`
- `charts/prominence_distribution.png`
- `charts/ewo_summary.png`
- `charts/ema_htf_summary.png`
- `charts/readiness_matrix.png`
