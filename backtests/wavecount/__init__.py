"""WaveCount research utilities.

This package is intentionally isolated from ENBOLSA, Menendez, RiskGuard and
Live Watcher. Phase 1 only provides causal pivot detection and offline visual
inspection helpers.
"""

from .wavecount_config import PivotConfig
from .wavecount_pivots import (
    PIVOT_STATES,
    compute_atr,
    detect_causal_pivots,
    extract_pivot_events,
)
from .wavecount_structure import (
    StructuralPivotConfig,
    build_structural_pivots,
    build_structural_pivots_by_group,
)
from .wavecount_degrees import (
    DEFAULT_SWING_DEGREES,
    SwingDegreeSpec,
    build_swing_degrees,
    is_monotonic_by_degree,
)
from .wavecount_counts import (
    CountConfig,
    build_candidate_counts,
)
from .wavecount_counts_review import (
    InvalidationReviewConfig,
    build_invalidations_review,
    build_rule_severity_summary,
)
from .wavecount_impulse_diagnostics import (
    ImpulseDiagnosticsConfig,
    build_impulse_diagnostics,
)
from .wavecount_wave5_endpoint import (
    Wave5EndpointConfig,
    diagnose_candidate_row,
    diagnose_wave5_endpoint,
)
from .wavecount_partial123 import (
    Partial123Config,
    diagnose_partial123,
    diagnose_partial123_candidate_row,
)
from .wavecount_context import (
    WaveContextConfig,
    align_htf_context,
    build_candidate_context,
    calculate_ewo_5_35,
    calculate_wave_context,
    classify_ema_alignment,
    classify_transition,
)

__all__ = [
    "PIVOT_STATES",
    "PivotConfig",
    "compute_atr",
    "detect_causal_pivots",
    "extract_pivot_events",
    "StructuralPivotConfig",
    "build_structural_pivots",
    "build_structural_pivots_by_group",
    "DEFAULT_SWING_DEGREES",
    "SwingDegreeSpec",
    "build_swing_degrees",
    "is_monotonic_by_degree",
    "CountConfig",
    "build_candidate_counts",
    "InvalidationReviewConfig",
    "build_invalidations_review",
    "build_rule_severity_summary",
    "ImpulseDiagnosticsConfig",
    "build_impulse_diagnostics",
    "Wave5EndpointConfig",
    "diagnose_candidate_row",
    "diagnose_wave5_endpoint",
    "Partial123Config",
    "diagnose_partial123",
    "diagnose_partial123_candidate_row",
    "WaveContextConfig",
    "align_htf_context",
    "build_candidate_context",
    "calculate_ewo_5_35",
    "calculate_wave_context",
    "classify_ema_alignment",
    "classify_transition",
]
