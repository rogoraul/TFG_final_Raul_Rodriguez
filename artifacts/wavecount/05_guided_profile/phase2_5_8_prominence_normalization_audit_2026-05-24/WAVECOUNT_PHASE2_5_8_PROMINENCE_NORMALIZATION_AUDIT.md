# WaveCount Phase 2.5.8 - Prominence Normalization Audit

Fase offline/descriptiva. No cambia la politica 2.5.6, no recalcula conteos base y no genera senales.

## Decision

- decision: `use_robust_window_prominence_next`
- phase256_still_valid: `True`
- recommended_phase259_metric: `robust_window_prominence_p05_p95 plus symbol/timeframe/degree percentiles`

## Lectura metodologica

- La prominencia agregada por grupo puede mezclar grados/timeframes; esta fase separa grupo, scope, timeframe, grado y simbolo.
- La ventana visual completa sigue siendo una metrica offline, no live-ready.
- Metals se audita aparte porque habia medianas H4/D1 claramente mas bajas que Forex Majors e Index.
- EWO/EMAs/HTF no se convierten en reglas duras.

## Tablas clave

- `tables/prominence_aggregation_audit.csv`
- `tables/prominence_alternative_metrics.csv`
- `tables/metals_h4_d1_prominence_audit.csv`
- `tables/prominence_policy_recommendation.csv`

## Resumen grupo/timeframe/grado

| resolved_market_group | source_scope | timeframe | swing_degree | candidate_count | prominence_vs_window_median | visual_window_prominence_median | robust_window_prominence_p05_p95_median | atr_normalized_count_size_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Forex Majors | h1_h4 | H1 | intermediate | 8 | 0.171621 | 0.1716213126000461 | 0.2247342416529427 | 6.810951772022056 |
| Forex Majors | h1_h4 | H1 | major | 8 | 0.286474 | 0.2864738166018746 | 0.3751310076358732 | 9.886724335144404 |
| Forex Majors | h1_h4 | H1 | minor | 8 | 0.102961 | 0.10296135376171964 | 0.13482557269052264 | 6.488217522658515 |
| Forex Majors | h4_d1 | H4 | intermediate | 16 | 0.148368 | 0.1517797179314977 | 0.18274686324982176 | 7.161662817551975 |
| Forex Majors | h4_d1 | H4 | major | 16 | 0.205604 | 0.37127826281620774 | 0.44702901578145915 | 14.117608188204912 |
| Forex Majors | h4_d1 | H4 | minor | 16 | 0.162861 | 0.1746138347884491 | 0.21023975418121138 | 6.833738591112507 |
| Index | h1_h4 | H1 | intermediate | 5 | 0.240335 | 0.24033505154639176 | 0.33392120175823425 | 11.234939759036163 |
| Index | h1_h4 | H1 | major | 5 | 0.311727 | 0.3117268041237109 | 0.43311280807140345 | 15.485139460448028 |
| Index | h1_h4 | H1 | minor | 5 | 0.240335 | 0.24033505154639176 | 0.33392120175823425 | 11.234939759036163 |
| Index | h4_d1 | H4 | intermediate | 10 | 0.281982 | 0.14994690265486718 | 0.2535757614456291 | 4.809862391521809 |
| Index | h4_d1 | H4 | major | 10 | 0.29659 | 0.29658997050147345 | 0.5015643956324602 | 7.394643545279413 |
| Index | h4_d1 | H4 | minor | 10 | 0.281982 | 0.14994690265486718 | 0.2535757614456291 | 4.093318608503558 |
| Metals | h1_h4 | H1 | intermediate | 5 | 0.180173 | 0.18017266836903084 | 0.2846564883401168 | 7.689472569370908 |
| Metals | h1_h4 | H1 | major | 5 | 0.15257 | 0.15257004881268782 | 0.24104685085723546 | 12.700061970667198 |
| Metals | h1_h4 | H1 | minor | 5 | 0.180173 | 0.18017266836903084 | 0.2846564883401168 | 7.971813022128686 |
| Metals | h4_d1 | H4 | intermediate | 10 | 0.040204500000000004 | 0.03877622622973829 | 0.0576280519090466 | 11.862005519779258 |
| Metals | h4_d1 | H4 | major | 10 | 0.053223 | 0.03877622622973829 | 0.0576280519090466 | 11.862005519779258 |
| Metals | h4_d1 | H4 | minor | 10 | 0.0361555 | 0.043295207353869866 | 0.06434402466138563 | 9.818140486474197 |

## Metals H4/D1

| diagnosis | count |
| --- | --- |
| alternative_metrics_unavailable | 15 |
| visual_window_too_large_possible | 14 |
| metals_prominence_acceptable_in_this_case | 1 |
