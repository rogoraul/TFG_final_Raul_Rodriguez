from __future__ import annotations

import csv
import json
from datetime import datetime
from io import StringIO
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE23_ROOT = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h4_d1"
PHASE24_ROOT = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_context_2026-05-18" / "h4_d1"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_4_h4_d1_visual_audit_2026-05-20"


PHASE23_REVIEWS = """candidate_order|candidate_id|visual_review_status|visual_quality_score|swing_degree_fit|user_review_priority|suggested_action|visual_notes
1|impulse_forex_audjpy_h4_minor_impulse_005|visually_defensible|4|good|low|keep_as_good_example|Compact bullish impulse; wave 3 is clear and wave 5 is short but natural on H4.
2|impulse_metals_xagusd_h4_minor_impulse_001|excellent_example|5|good|low|keep_as_good_example|Clean bullish 0-5 sequence with visible retracements and good Elliott readability.
3|impulse_index_hk50_h4_minor_impulse_012|visually_defensible|4|good|medium|inspect_manually_before_phase_2_5|Recognizable bullish impulse; wave 4 is deep and close to wave 1 territory.
4|impulse_forex_eurjpy_h4_minor_impulse_022|excellent_example|5|good|low|keep_as_good_example|Natural bullish five-wave structure before the later selloff.
5|impulse_forex_eurusd_h4_intermediate_impulse_007|visually_defensible|4|good|low|keep_as_good_example|Clear bearish impulse with extended wave 3 and no obvious wave 4 overlap.
6|impulse_metals_xagusd_h4_intermediate_impulse_007|excellent_example|5|good|low|keep_as_good_example|Strong broad bullish 1-2-3-4-5; one of the cleanest intermediate examples.
7|impulse_index_aus200_h4_intermediate_impulse_015|excellent_example|5|good|low|keep_as_good_example|Clear bullish impulse with natural waves 3 and 5 and visible corrections.
8|impulse_forex_eurusd_h4_intermediate_impulse_012|excellent_example|5|good|low|keep_as_good_example|Very clean bullish advance from a low, with five recognizable H4 legs.
9|impulse_forex_eurusd_h4_major_impulse_011|plausible_but_needs_review|3|too_micro|high|inspect_manually_before_phase_2_5|Bearish pattern is plausible, but too local for major; waves 4-5 are small versus wave 3.
10|impulse_metals_xpdusd_h4_major_impulse_001|plausible_but_needs_review|3|mixed|high|inspect_manually_before_phase_2_5|Valid-looking shape with violent spikes and a weak wave 5; may be a lower degree.
11|impulse_index_aus200_h4_major_impulse_013|visually_defensible|4|too_micro|medium|inspect_manually_before_phase_2_5|Good Elliott shape, but visually closer to intermediate than major.
12|impulse_forex_gbpusd_h4_major_impulse_012|excellent_example|5|good|low|keep_as_good_example|Good major bearish impulse with strong wave 3 and natural extended fifth.
13|partial_123_forex_audjpy_h4_intermediate_partial123_002|likely_false_candidate|2|too_micro|high|do_not_use_for_rules|Small bearish 1-2-3 is absorbed by the later rise; forced as intermediate.
14|partial_123_metals_xagusd_h4_intermediate_partial123_001|visually_defensible|4|good|low|keep_as_good_example|Good bullish 1-2-3 launch on XAGUSD, natural as intermediate start.
15|partial_123_index_aus200_h4_intermediate_partial123_006|likely_false_candidate|2|too_micro|high|do_not_use_for_rules|Weak bearish partial; wave 3 barely breaks before immediate bullish reversal.
16|partial_123_forex_audjpy_h4_intermediate_partial123_005|visually_defensible|4|good|low|keep_as_good_example|Clean and proportional bullish 1-2-3; fits the later H4 trend.
17|partial_123_forex_audjpy_h4_minor_partial123_002|plausible_but_needs_review|3|good|medium|inspect_manually_before_phase_2_5|More defensible as minor than intermediate, but later reversal lowers quality.
18|partial_123_metals_xagusd_h4_minor_partial123_001|visually_defensible|4|too_coarse|medium|inspect_manually_before_phase_2_5|Clean pattern, but size and duration look closer to intermediate than minor.
19|partial_123_index_aus200_h4_minor_partial123_005|visually_defensible|4|good|medium|possible_rule_candidate|Compact bullish 0-1-2-3; wave 3 confirms, though small versus context.
20|partial_123_forex_audjpy_h4_minor_partial123_005|excellent_example|5|good|high|keep_as_good_example|Clean bullish sequence; wave 2 corrects without breaking and wave 3 extends naturally.
21|partial_123_forex_audjpy_h4_major_partial123_003|excellent_example|5|good|high|keep_as_good_example|Very good major 0-1-2-3; proportions, pivots and continuation fit well.
22|partial_123_metals_xagusd_h4_major_partial123_003|excellent_example|5|good|high|keep_as_good_example|Natural major bullish read; wave 3 breaks with amplitude and precedes strong continuation.
23|partial_123_index_aus200_h4_major_partial123_006|likely_false_candidate|2|mixed|high|do_not_use_for_rules|Weak bearish 0-1-2-3; wave 3 barely exceeds wave 1 before bullish turn.
24|partial_123_forex_audjpy_h4_major_partial123_005|excellent_example|5|good|high|keep_as_good_example|Very clear major structure; waves 1, 2 and 3 respect an impulsive read.
25|abc_forex_audjpy_h4_abc_002|ambiguous|3|mixed|medium|inspect_manually_before_phase_2_5|Possible correction before a rise, but labels overlap and the A-B-C is not clean.
26|abc_metals_xagusd_h4_abc_003|likely_false_candidate|1|unclear|high|do_not_use_for_rules|Forced ABC; it labels a bullish impulse as correction with several overlapping C labels.
27|abc_index_aus200_h4_abc_006|likely_false_candidate|2|unclear|high|do_not_use_for_rules|Forced ABC; B is excessive and C does not resolve naturally.
28|abc_forex_audjpy_h4_abc_005|likely_false_candidate|2|unclear|high|do_not_use_for_rules|Too many diagonals over a bullish trend; corrective read is not natural.
29|abc_index_aus200_h4_abc_005|ambiguous|2|mixed|medium|inspect_manually_before_phase_2_5|Looks more like a partial impulse start than a clean ABC.
30|abc_forex_audjpy_h4_abc_009|likely_false_candidate|1|unclear|high|do_not_use_for_rules|Fan of lines over most of the trend; no legible H4 A-B-C.
31|abc_forex_eurjpy_h4_abc_004|likely_false_candidate|1|unclear|high|do_not_use_for_rules|Crossed and confused range; no natural A-B-C on H4.
32|abc_forex_eurusd_h4_abc_002|likely_false_candidate|2|unclear|high|do_not_use_for_rules|Congestion with multiple labels; corrective pattern is overfit.
33|abc_forex_audjpy_h4_abc_003|ambiguous|3|mixed|medium|inspect_manually_before_phase_2_5|Broad leg could be read as A-B-C, but also as impulse or partial 1-2-3.
34|abc_forex_audjpy_h4_abc_013|likely_false_candidate|1|unclear|high|do_not_use_for_rules|Too extended and crossed; turns a trend into an artificial correction.
35|abc_forex_eurjpy_h4_abc_003|ambiguous|2|mixed|medium|inspect_manually_before_phase_2_5|Possible broad correction, but selected pivots do not form a clean sequence.
36|abc_forex_eurusd_h4_abc_003|ambiguous|2|mixed|medium|inspect_manually_before_phase_2_5|Broad bearish/corrective context is possible, but repeated labels reduce naturalness.
37|near_miss_forex_audjpy_h4_intermediate_impulse_002|ambiguous|3|mixed|high|keep_as_ambiguous_example|Bearish wave 5 is clearly truncated and wave 4 overlaps; useful but not strong.
38|near_miss_metals_xagusd_h4_intermediate_impulse_003|visually_defensible|4|good|high|keep_as_ambiguous_example|Readable structure with wave 5 stalled after a deep wave 4; good truncation example.
39|near_miss_index_aus200_h4_intermediate_impulse_009|visually_defensible|4|good|high|keep_as_ambiguous_example|Coherent bullish near-miss with visible overlap and failed fifth.
40|near_miss_forex_audjpy_h4_minor_impulse_002|visually_forced|2|mixed|medium|use_as_negative_example|Tiny crowded minor leg; truncation is too obvious and pivots are noisy.
41|near_miss_metals_xagusd_h4_minor_impulse_005|ambiguous|3|mixed|medium|keep_as_ambiguous_example|Readable early impulse, but wave 5 materially fails below wave 3.
42|near_miss_index_aus200_h4_minor_impulse_005|visually_defensible|4|good|high|keep_as_ambiguous_example|Clean minor sequence; wave 5 fails while swings remain legible.
43|near_miss_forex_audjpy_h4_major_impulse_005|visually_defensible|4|good|high|keep_as_ambiguous_example|Strongest near-miss; coherent five-swing advance with only mild failure of wave 5.
44|near_miss_metals_xagusd_h4_major_impulse_003|likely_false_candidate|2|mixed|high|use_as_negative_example|Deep wave 4 crash breaks proportions; too invalid for a near-miss.
45|near_miss_index_aus200_h4_major_impulse_009|ambiguous|3|mixed|medium|inspect_manually_before_phase_2_5|Broad shape is readable but wave 4 returns near origin and wave 5 fails.
46|hard_invalid_forex_audjpy_h4_intermediate_impulse_001|hard_invalid_correct|4|good|low|use_as_negative_example|Wave 3 does not convincingly exceed wave 1 and wave 4 breaks structure.
47|hard_invalid_metals_xagusd_h4_intermediate_impulse_001|hard_invalid_correct|4|good|low|use_as_negative_example|Underpowered wave 3 and dominant wave 5; good hard-invalid negative.
48|hard_invalid_index_aus200_h4_intermediate_impulse_001|hard_invalid_correct|5|good|low|use_as_negative_example|Very clean hard invalid with origin-area breaks and oversized final leg.
49|hard_invalid_forex_audjpy_h4_minor_impulse_001|hard_invalid_correct|3|mixed|medium|use_as_negative_example|Invalidity is clear, but the minor segment is crowded.
50|hard_invalid_metals_xagusd_h4_minor_impulse_002|hard_invalid_correct|3|mixed|medium|use_as_negative_example|Several rule breaks in a cramped early section; clear but not a showcase.
51|hard_invalid_index_aus200_h4_minor_impulse_001|hard_invalid_correct|4|good|low|use_as_negative_example|Wave 2 breaks origin, wave 4 is deep, and wave 5 remains below wave 3.
52|hard_invalid_forex_audjpy_h4_major_impulse_001|hard_invalid_correct|4|good|low|use_as_negative_example|Origin break and overdeep retracement are visible; readable at major degree.
53|hard_invalid_metals_xagusd_h4_major_impulse_001|hard_invalid_correct|5|good|low|use_as_negative_example|Textbook hard invalid: wave 3 cannot exceed wave 1 and wave 5 dominates.
54|hard_invalid_index_aus200_h4_major_impulse_001|hard_invalid_correct|4|good|low|use_as_negative_example|Clear origin breaks and deep retracements; good negative example.
"""


PHASE24_REVIEWS = """candidate_order|candidate_id|d1_context_usefulness|ema_context_usefulness|ewo_context_usefulness|context_changes_phase23_reading|user_review_priority|suggested_action|context_notes
1|impulse_forex_audjpy_h4_minor_impulse_005|useful|useful|useful_for_wave_role|improves_confidence|medium|possible_rule_candidate|D1 and EMAs support the small bullish reversal; EWO turns positive, but the count remains minor.
2|impulse_metals_xagusd_h4_minor_impulse_001|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|Clean early bullish sequence inside aligned D1 trend with constructive EWO.
3|impulse_index_hk50_h4_minor_impulse_012|partially_useful|partially_useful|useful_for_wave_role|flags_transition|medium|keep_as_ambiguous_example|Bullish context helps, but broader chart later rolls over; late-cycle/transition sensitive.
4|impulse_forex_eurjpy_h4_minor_impulse_022|partially_useful|partially_useful|useful_for_wave_role|flags_transition|medium|keep_as_ambiguous_example|Completes near a top before sharp selloff; context warns against treating it as fresh continuation.
5|impulse_forex_eurusd_h4_intermediate_impulse_007|conflict_explains_case|partially_useful|useful_for_momentum_only|reframes_as_correction|high|inspect_manually_before_phase_2_5|Bearish H4 sequence conflicts with bullish D1 and is followed by strong upside.
6|impulse_metals_xagusd_h4_intermediate_impulse_007|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|Strong aligned bullish impulse with rising EMAs and positive EWO.
7|impulse_index_aus200_h4_intermediate_impulse_015|partially_useful|partially_useful|useful_for_wave_role|flags_transition|medium|keep_as_ambiguous_example|Readable count, but post-wave-5 collapse makes it a completed/terminal impulse example.
8|impulse_forex_eurusd_h4_intermediate_impulse_012|useful|partially_useful|useful_for_wave_role|improves_confidence|medium|possible_rule_candidate|Bullish D1 and EWO support the rally, though EMA confirmation arrives after the turn.
9|impulse_forex_eurusd_h4_major_impulse_011|conflict_explains_case|useful|useful_for_wave_role|flags_transition|high|inspect_manually_before_phase_2_5|Local bearish count has EMA/EWO support but conflicts with bullish D1; transition/correction candidate.
10|impulse_metals_xpdusd_h4_major_impulse_001|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|Aligned bullish major impulse with supportive EMAs and EWO.
11|impulse_index_aus200_h4_major_impulse_013|partially_useful|partially_useful|useful_for_wave_role|flags_transition|high|inspect_manually_before_phase_2_5|Plausible count but wave 5 precedes major reversal; context marks completion risk.
12|impulse_forex_gbpusd_h4_major_impulse_012|conflict_explains_case|useful|useful_for_wave_role|flags_transition|high|inspect_manually_before_phase_2_5|Bearish H4 structure has local support but D1 conflict prevents aligned-impulse reading.
13|partial_123_forex_audjpy_h4_intermediate_partial123_002|conflict_explains_case|misleading|useful_for_momentum_only|downgrades_confidence|high|do_not_use_for_rules|Bearish partial occurs against bullish D1 and broader rising structure; EWO only captures pullback momentum.
14|partial_123_metals_xagusd_h4_intermediate_partial123_001|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|Aligned bullish 1-2-3 early in a strong trend, supported by EMAs and EWO.
15|partial_123_index_aus200_h4_intermediate_partial123_006|conflict_suspicious|misleading|misleading|downgrades_confidence|high|do_not_use_for_rules|Bearish partial sits inside bullish D1 and rising EMA context; context confirms it should not be rescued.
16|partial_123_forex_audjpy_h4_intermediate_partial123_005|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|Bullish partial aligns with D1 and EWO supports developing impulse.
17|partial_123_forex_audjpy_h4_minor_partial123_002|conflict_explains_case|misleading|useful_for_momentum_only|reframes_as_correction|high|do_not_use_for_rules|Minor bearish partial is better read as pullback inside bullish D1.
18|partial_123_metals_xagusd_h4_minor_partial123_001|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|Minor bullish partial is consistent with D1 alignment, rising EMAs and positive EWO.
19|partial_123_index_aus200_h4_minor_partial123_005|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|D1 and EMAs support bullish 0-1-2-3; EWO peak fits wave 3.
20|partial_123_forex_audjpy_h4_minor_partial123_005|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|Clean bullish launch; D1, EMAs and EWO confirm the phase 2.3 reading.
21|partial_123_forex_audjpy_h4_major_partial123_003|useful|useful|useful_for_momentum_only|confirms|low|keep_as_good_example|Major bullish 0-1-2-3 reads naturally; EWO supports momentum but is less decisive than D1/EMAs.
22|partial_123_metals_xagusd_h4_major_partial123_003|useful|useful|useful_for_momentum_only|downgrades_confidence|medium|inspect_manually_before_phase_2_5|Bullish 1-2-3 is visible, but wave 3 ends in a blowoff before hard reversal.
23|partial_123_index_aus200_h4_major_partial123_006|conflict_suspicious|partially_useful|useful_for_momentum_only|downgrades_confidence|high|do_not_use_for_rules|D1/EMAs remain bullish while bearish 0-1-2-3 is flat and forced.
24|partial_123_forex_audjpy_h4_major_partial123_005|useful|useful|useful_for_wave_role|confirms|low|keep_as_good_example|Strong bullish partial with wave 2 near EMA support and wave 3 into clear impulse.
25|abc_forex_audjpy_h4_abc_002|conflict_explains_case|partially_useful|useful_for_momentum_only|reframes_as_correction|high|use_as_negative_example|Counter-D1 bearish ABC is overlapped and crowded; context does not rescue structure.
26|abc_metals_xagusd_h4_abc_003|useful|useful|useful_for_momentum_only|misleading_if_used_as_filter|high|keep_as_ambiguous_example|Bullish context is real, but ABC overlays are dense and forced.
27|abc_index_aus200_h4_abc_006|conflict_suspicious|partially_useful|useful_for_momentum_only|downgrades_confidence|high|use_as_negative_example|Bearish ABC conflicts with bullish D1/EMAs and weak sideways correction.
28|abc_forex_audjpy_h4_abc_005|useful|useful|useful_for_momentum_only|misleading_if_used_as_filter|high|keep_as_ambiguous_example|Bullish regime supports direction, but multiple ABC paths share pivots.
29|abc_index_aus200_h4_abc_005|partially_useful|useful|useful_for_momentum_only|downgrades_confidence|medium|inspect_manually_before_phase_2_5|Looks closer to minor impulse/partial than clean ABC; context does not rescue it.
30|abc_forex_audjpy_h4_abc_009|useful|useful|useful_for_momentum_only|misleading_if_used_as_filter|high|keep_as_ambiguous_example|Trend context is supportive, but ABCs overlap across the same rising leg.
31|abc_forex_eurjpy_h4_abc_004|useful|partially_useful|useful_for_momentum_only|misleading_if_used_as_filter|high|keep_as_ambiguous_example|Bullish context helps direction, but several ABCs compete for the same pivots.
32|abc_forex_eurusd_h4_abc_002|partially_useful|partially_useful|useful_for_momentum_only|downgrades_confidence|high|keep_as_ambiguous_example|Early bullish context fades into range; labels are cramped and should not be rescued.
33|abc_forex_audjpy_h4_abc_003|useful|useful|useful_for_momentum_only|misleading_if_used_as_filter|high|keep_as_ambiguous_example|Bullish regime is clear, but ABC looks more like continuation/partial 1-2-3.
34|abc_forex_audjpy_h4_abc_013|useful|useful|useful_for_momentum_only|misleading_if_used_as_filter|high|keep_as_ambiguous_example|Long bullish channel has supportive context, but ABC spans too much overlapping structure.
35|abc_forex_eurjpy_h4_abc_003|conflict_explains_case|partially_useful|useful_for_momentum_only|reframes_as_correction|high|use_as_negative_example|Bearish EWO confirms pullback, but D1 is bullish and labels are forced.
36|abc_forex_eurusd_h4_abc_003|conflict_explains_case|useful|useful_for_momentum_only|reframes_as_correction|high|keep_as_ambiguous_example|LTF EMAs/EWO support bearish pressure but D1 conflicts and ABC selection remains cluttered.
37|near_miss_forex_audjpy_h4_intermediate_impulse_002|conflict_explains_case|useful|unclear|no_change|low|use_as_negative_example|D1 and EMAs explain correction against trend; EWO later improves but does not rescue the read.
38|near_miss_metals_xagusd_h4_intermediate_impulse_003|useful|useful|useful_for_wave_role|improves_confidence|high|inspect_manually_before_phase_2_5|Very aligned context; review whether near-miss is only a fine structural rule issue.
39|near_miss_index_aus200_h4_intermediate_impulse_009|partially_useful|partially_useful|useful_for_momentum_only|flags_transition|medium|keep_as_ambiguous_example|Context supports impulse during candidate but later fall makes it a late transition example.
40|near_miss_forex_audjpy_h4_minor_impulse_002|conflict_explains_case|useful|useful_for_momentum_only|downgrades_confidence|low|use_as_negative_example|Minor read is against bullish D1; EMAs and later EWO favor discard.
41|near_miss_metals_xagusd_h4_minor_impulse_005|useful|useful|useful_for_wave_role|improves_confidence|high|inspect_manually_before_phase_2_5|Strong context support; review if deep retracement can stay as near-miss.
42|near_miss_index_aus200_h4_minor_impulse_005|partially_useful|partially_useful|unclear|no_change|medium|inspect_manually_before_phase_2_5|Context helps but inside-band/EWO make the minor reading less decisive.
43|near_miss_forex_audjpy_h4_major_impulse_005|useful|useful|useful_for_wave_role|improves_confidence|high|inspect_manually_before_phase_2_5|Major near-miss is visually clean and coherent with D1/EMAs/EWO.
44|near_miss_metals_xagusd_h4_major_impulse_003|partially_useful|partially_useful|misleading|flags_transition|medium|inspect_manually_before_phase_2_5|D1 bullish does not compensate chaotic drop; EWO negative explains correction.
45|near_miss_index_aus200_h4_major_impulse_009|useful|useful|useful_for_momentum_only|flags_transition|high|inspect_manually_before_phase_2_5|Context supports impulse until point 5 but flags late-cycle risk.
46|hard_invalid_forex_audjpy_h4_intermediate_impulse_001|partially_useful|useful|unclear|misleading_if_used_as_filter|medium|use_as_negative_example|Context favors later direction, but initial structure remains invalid.
47|hard_invalid_metals_xagusd_h4_intermediate_impulse_001|useful|useful|useful_for_wave_role|misleading_if_used_as_filter|high|inspect_manually_before_phase_2_5|Very favorable context; if hard invalid remains, reason must be structural.
48|hard_invalid_index_aus200_h4_intermediate_impulse_001|useful|useful|useful_for_momentum_only|misleading_if_used_as_filter|high|inspect_manually_before_phase_2_5|D1 and EMAs support, but overlap/transition mean hard invalid should not be rescued.
49|hard_invalid_forex_audjpy_h4_minor_impulse_001|partially_useful|partially_useful|unclear|misleading_if_used_as_filter|low|use_as_negative_example|Candidate appears before real expansion; context explains but does not change invalidation.
50|hard_invalid_metals_xagusd_h4_minor_impulse_002|conflict_explains_case|useful|misleading|downgrades_confidence|low|use_as_negative_example|Clear conflict with bullish D1; context reinforces discard.
51|hard_invalid_index_aus200_h4_minor_impulse_001|partially_useful|partially_useful|unclear|misleading_if_used_as_filter|medium|use_as_negative_example|Context explains bullish bias, but minor swing remains noisy and overlapped.
52|hard_invalid_forex_audjpy_h4_major_impulse_001|partially_useful|useful|useful_for_momentum_only|flags_transition|medium|use_as_negative_example|Context shows bullish trend arrived later; initial leg still violates impulse cleanliness.
53|hard_invalid_metals_xagusd_h4_major_impulse_001|useful|useful|useful_for_wave_role|misleading_if_used_as_filter|high|inspect_manually_before_phase_2_5|Context is aligned but structure has overlap and possible extension failure; audit without rescue.
54|hard_invalid_index_aus200_h4_major_impulse_001|useful|useful|useful_for_momentum_only|flags_transition|high|inspect_manually_before_phase_2_5|D1/EMAs/EWO support candidate, but later correction suggests transition; only structural rules could change label.
"""


BEST_PHASE23_ORDERS = {2, 4, 6, 8, 12, 14, 16, 20, 21, 24, 48, 53}
BEST_PHASE24_ORDERS = {2, 6, 10, 14, 16, 18, 20, 21, 24, 43}


def _read_pipe_table(text: str) -> pd.DataFrame:
    rows = list(csv.DictReader(StringIO(text.strip()), delimiter="|"))
    return pd.DataFrame(rows)


def _priority_rank(value: object) -> int:
    mapping = {"high": 0, "medium": 1, "low": 2}
    return mapping.get(str(value).strip().lower(), 3)


def _as_int(value: object) -> int:
    return int(float(str(value).strip()))


def _add_phase23_paths(reviews: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    merged = candidates.merge(reviews, on=["candidate_order", "candidate_id"], how="left", suffixes=("", "_review"))
    merged["chart_path_absolute"] = merged["chart_path"].apply(lambda value: str(PHASE23_ROOT / str(value)))
    return merged


def _add_phase24_paths(reviews: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    merged = candidates.merge(reviews, on=["candidate_order", "candidate_id"], how="left", suffixes=("", "_review"))
    merged["context_chart_path_absolute"] = merged["context_chart_path"].apply(lambda value: str(PHASE24_ROOT / str(value)))
    return merged


def _build_user_review(phase23: pd.DataFrame, phase24: pd.DataFrame, best_examples: pd.DataFrame) -> pd.DataFrame:
    phase23 = phase23.copy()
    phase23["review_phase"] = "phase2_3_h4_count_only"
    phase23["why_review"] = ""
    phase23.loc[pd.to_numeric(phase23["visual_quality_score"]) <= 2, "why_review"] = "low_visual_quality"
    phase23.loc[phase23["visual_review_status"].isin(["plausible_but_needs_review", "ambiguous", "visually_forced", "likely_false_candidate"]), "why_review"] = phase23["why_review"].where(
        phase23["why_review"] != "", "manual_or_doubtful_count"
    )
    phase23.loc[(phase23["review_category"] == "abc") & (phase23["visual_review_status"] != "excellent_example"), "why_review"] = phase23["why_review"].where(
        phase23["why_review"] != "", "abc_manual_review"
    )
    p23 = phase23[phase23["why_review"] != ""].rename(columns={"chart_path": "chart_path_relative"})
    p23["context_chart_path_relative"] = ""
    p23["chart_path_absolute_out"] = p23["chart_path_absolute"]
    p23["context_status"] = ""

    phase24 = phase24.copy()
    phase24["review_phase"] = "phase2_4_h4_d1_context"
    phase24["why_review"] = ""
    context_flags = {
        "conflict_explains_case",
        "conflict_suspicious",
        "misleading",
        "unclear",
    }
    phase24.loc[phase24["d1_context_usefulness"].isin(context_flags), "why_review"] = "d1_context_conflict_or_unclear"
    phase24.loc[phase24["ema_context_usefulness"].isin({"misleading", "not_useful"}), "why_review"] = phase24["why_review"].where(
        phase24["why_review"] != "", "ema_context_problem"
    )
    phase24.loc[phase24["ewo_context_usefulness"].isin({"misleading", "unclear"}), "why_review"] = phase24["why_review"].where(
        phase24["why_review"] != "", "ewo_context_problem"
    )
    phase24.loc[
        phase24["context_changes_phase23_reading"].isin(
            ["downgrades_confidence", "reframes_as_correction", "flags_transition", "misleading_if_used_as_filter"]
        ),
        "why_review",
    ] = phase24["why_review"].where(phase24["why_review"] != "", "context_changes_reading")
    phase24.loc[(phase24["review_category"] == "abc") & (phase24["suggested_action"] != "keep_as_good_example"), "why_review"] = phase24["why_review"].where(
        phase24["why_review"] != "", "abc_context_manual_review"
    )
    p24 = phase24[phase24["why_review"] != ""].rename(columns={"context_chart_path": "context_chart_path_relative"})
    p24["chart_path_relative"] = ""
    p24["chart_path_absolute_out"] = p24["context_chart_path_absolute"]
    p24["visual_review_status"] = ""
    p24["visual_quality_score"] = ""
    p24["swing_degree_fit"] = ""
    p24["context_status"] = p24["d1_context_usefulness"] + "/" + p24["context_changes_phase23_reading"]
    p24["visual_notes"] = p24["context_notes"]

    best = best_examples.copy()
    best["review_phase"] = "best_examples_for_user_validation"
    best["why_review"] = "best_positive_or_negative_example"
    best["chart_path_relative"] = best["chart_path"]
    best["context_chart_path_relative"] = best.get("context_chart_path", "")
    best["chart_path_absolute_out"] = best["chart_path_absolute"]
    best["visual_review_status"] = best.get("visual_review_status", "")
    best["visual_quality_score"] = best.get("visual_quality_score", "")
    best["swing_degree_fit"] = best.get("swing_degree_fit", "")
    best["context_status"] = best.get("d1_context_usefulness", "")
    best["user_review_priority"] = "high"
    best["suggested_action"] = best.get("suggested_action", "inspect_manually_before_phase_2_5")
    best["visual_notes"] = best.get("why_good", "")

    columns = [
        "review_phase",
        "candidate_order",
        "candidate_id",
        "review_category",
        "swing_degree",
        "chart_path_relative",
        "context_chart_path_relative",
        "chart_path_absolute_out",
        "visual_review_status",
        "visual_quality_score",
        "swing_degree_fit",
        "context_status",
        "user_review_priority",
        "suggested_action",
        "why_review",
        "visual_notes",
    ]
    combined = pd.concat(
        [p23[columns], p24[columns], best[columns]],
        ignore_index=True,
    ).drop_duplicates(subset=["review_phase", "candidate_id", "why_review"])
    combined["priority_rank"] = combined["user_review_priority"].apply(_priority_rank)
    combined["candidate_order"] = pd.to_numeric(combined["candidate_order"], errors="coerce")
    return combined.sort_values(["priority_rank", "candidate_order", "review_phase"]).drop(columns=["priority_rank"])


def _build_best_examples(phase23: pd.DataFrame, phase24: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    p23 = phase23[phase23["candidate_order"].astype(int).isin(BEST_PHASE23_ORDERS)].copy()
    p23["phase"] = "phase2_3_h4_count_only"
    p23["example_type"] = p23["suggested_action"]
    p23["why_good"] = p23["visual_notes"]
    p23["context_chart_path"] = ""
    p23["context_chart_path_absolute"] = ""
    rows.append(p23)

    p24 = phase24[phase24["candidate_order"].astype(int).isin(BEST_PHASE24_ORDERS)].copy()
    p24["phase"] = "phase2_4_h4_d1_context"
    p24["example_type"] = p24["suggested_action"]
    p24["why_good"] = p24["context_notes"]
    p24["chart_path"] = p24["context_chart_path"]
    p24["chart_path_absolute"] = p24["context_chart_path_absolute"]
    p24["visual_review_status"] = ""
    p24["visual_quality_score"] = ""
    p24["swing_degree_fit"] = ""
    rows.append(p24)

    best = pd.concat(rows, ignore_index=True, sort=False)
    output_columns = [
        "phase",
        "candidate_order",
        "candidate_id",
        "review_category",
        "swing_degree",
        "chart_path",
        "chart_path_absolute",
        "context_chart_path",
        "context_chart_path_absolute",
        "example_type",
        "visual_review_status",
        "visual_quality_score",
        "swing_degree_fit",
        "d1_context_usefulness",
        "ema_context_usefulness",
        "ewo_context_usefulness",
        "context_changes_phase23_reading",
        "why_good",
    ]
    return best[[column for column in output_columns if column in best.columns]]


def _summary(phase23: pd.DataFrame, phase24: pd.DataFrame, user_review: pd.DataFrame, best_examples: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {"metric": "phase2_3_reviewed_cases", "value": int(len(phase23))},
        {"metric": "phase2_4_reviewed_cases", "value": int(len(phase24))},
        {"metric": "user_must_review_rows", "value": int(len(user_review))},
        {"metric": "best_h4_examples_rows", "value": int(len(best_examples))},
    ]
    for status, count in phase23["visual_review_status"].value_counts().items():
        rows.append({"metric": f"phase2_3_status_{status}", "value": int(count)})
    for degree, count in phase23["swing_degree"].value_counts().items():
        rows.append({"metric": f"phase2_3_degree_{degree}", "value": int(count)})
    for category, count in phase23["review_category"].value_counts().items():
        rows.append({"metric": f"phase2_3_category_{category}", "value": int(count)})
    for value, count in phase24["d1_context_usefulness"].value_counts().items():
        rows.append({"metric": f"phase2_4_d1_{value}", "value": int(count)})
    for value, count in phase24["context_changes_phase23_reading"].value_counts().items():
        rows.append({"metric": f"phase2_4_change_{value}", "value": int(count)})
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, summary: pd.DataFrame, best_examples: pd.DataFrame) -> None:
    lines = [
        "# WaveCount H4/D1 visual audit",
        "",
        "Fecha: 2026-05-20",
        "",
        "## Alcance",
        "",
        "Se revisaron visualmente 54 graficos H4 de Fase 2.3 y 54 graficos H4/D1 de Fase 2.4.",
        "La revision fue realizada por subagentes en bloques independientes y consolidada sin cambiar reglas, datos, pivotes, grados, EMAs/EWO ni estrategias.",
        "",
        "## Resumen cuantitativo",
        "",
    ]
    for row in summary.itertuples():
        lines.append(f"- `{row.metric}`: {row.value}")
    lines.extend(
        [
            "",
            "## Lectura metodologica",
            "",
            "- H4 mejora claramente la lectura visual de impulsos y parciales `1-2-3` frente a M30/H1.",
            "- `intermediate` y algunos `major` son los grados mas utiles para H4; `minor` puede funcionar, pero con mas riesgo de microestructura.",
            "- Los ABC siguen siendo la parte mas debil: aparecen solapes, multiples rutas y etiquetas que fuerzan tendencia como correccion.",
            "- D1/EMAs/EWO ayudan como contexto blando, especialmente para confirmar impulsos alcistas o detectar correcciones contra D1.",
            "- El contexto no debe rescatar conteos visualmente malos ni hard invalidations.",
            "",
            "## Mejores ejemplos candidatos",
            "",
        ]
    )
    for row in best_examples.itertuples():
        lines.append(f"- `{row.phase}` order {int(row.candidate_order):03d} `{row.candidate_id}`: {row.why_good}")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "H4/D1 es una base visual mas prometedora para WaveCount que M30/H1, sobre todo para impulsos y parciales.",
            "Aun no conviene avanzar a Fase 2.5 hasta revisar los casos marcados en `user_must_review_h4_d1.csv`, especialmente ABC y hard invalidations con contexto D1 favorable.",
        ]
    )
    (output_dir / "WAVECOUNT_H4_D1_VISUAL_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_h4_d1_visual_audit(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    phase23_candidates = pd.read_csv(PHASE23_ROOT / "tables" / "visual_review_candidates.csv")
    phase24_candidates = pd.read_csv(PHASE24_ROOT / "tables" / "candidate_context.csv")
    phase23_reviews = _read_pipe_table(PHASE23_REVIEWS)
    phase24_reviews = _read_pipe_table(PHASE24_REVIEWS)
    for frame in [phase23_candidates, phase24_candidates, phase23_reviews, phase24_reviews]:
        frame["candidate_order"] = frame["candidate_order"].apply(_as_int)

    phase23 = _add_phase23_paths(phase23_reviews, phase23_candidates)
    phase24 = _add_phase24_paths(phase24_reviews, phase24_candidates)
    best_examples = _build_best_examples(phase23, phase24)
    user_review = _build_user_review(phase23, phase24, best_examples)
    summary = _summary(phase23, phase24, user_review, best_examples)

    phase23.to_csv(tables_dir / "phase2_3_h4_visual_audit.csv", index=False)
    phase24.to_csv(tables_dir / "phase2_4_h4_d1_context_audit.csv", index=False)
    user_review.to_csv(tables_dir / "user_must_review_h4_d1.csv", index=False)
    best_examples.to_csv(tables_dir / "best_h4_examples.csv", index=False)
    summary.to_csv(tables_dir / "h4_d1_audit_summary.csv", index=False)
    _write_report(output_dir, summary, best_examples)

    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": perf_counter() - start,
        "inputs": {
            "phase2_3": str(PHASE23_ROOT),
            "phase2_4": str(PHASE24_ROOT),
        },
        "outputs": {
            "phase2_3_h4_visual_audit": "tables/phase2_3_h4_visual_audit.csv",
            "phase2_4_h4_d1_context_audit": "tables/phase2_4_h4_d1_context_audit.csv",
            "user_must_review_h4_d1": "tables/user_must_review_h4_d1.csv",
            "best_h4_examples": "tables/best_h4_examples.csv",
            "h4_d1_audit_summary": "tables/h4_d1_audit_summary.csv",
            "report": "WAVECOUNT_H4_D1_VISUAL_AUDIT.md",
        },
        "notes": [
            "Visual audit only.",
            "No WaveCount rules were changed.",
            "No strategies, signals, MT5, dashboard, Telegram or canonical benchmark artifacts were touched.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    print(json.dumps(build_h4_d1_visual_audit(), indent=2))


if __name__ == "__main__":
    main()
