# WaveCount Reorganization Plan 2026-05-24

## Scope

This is an audit and design plan only. No files or folders were moved, renamed or deleted.

## Main Findings

- Artifact directories inventoried: 29
- WaveCount docs inventoried: 31
- WaveCount code files inventoried: 44
- Current-table image refs broken: 1054
- Proposed mapping duplicate destinations: 0

The main organization problem is not code. It is artifact/doc navigation and path traceability after many phases.

## Recommendation

- Reorganize artifacts by phase group.
- Create a docs/wavecount index before moving docs.
- Do not move Python code in the first migration.
- Rewrite CSV image paths and regenerate Markdown indexes during the actual migration.
- Keep historical material; do not delete.

## Next Real Migration

Run a separate controlled migration phase after reviewing `tables/migration_mapping.csv`.
