# Benchmark significance ENBOLSA artifacts

Canonical output:

```text
artifacts/benchmark-significance/enbolsa/final/
```

Canonical report:

```text
artifacts/benchmark-significance/enbolsa/final/reports/BENCHMARKS_ENBOLSA_REPORT.md
```

The retained `partial-*` directories are reproducible per-block inputs. The
`final/` folder is the only canonical output for TFG conclusions.

Any ad-hoc run outside `final/` (for example `manual-run/` if the direct runner
is executed without an explicit `--output-root`) must be treated as
non-canonical work output.

The final folder is the only location intended for TFG conclusions. It avoids
global equity/drawdown charts and separates:

- canonical block portfolio metrics,
- aggregate metrics across independent blocks,
- trade-pool metrics.

Visual review notebook:

```text
artifacts/benchmark-significance/enbolsa/final/BENCHMARKS_ENBOLSA_REVIEW.ipynb
```
