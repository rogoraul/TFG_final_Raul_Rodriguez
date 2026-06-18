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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_4_visual_reaudit_2026-05-19"
PHASE23_ROOT = REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_visual_review_2026-05-17" / "h1_m30"
PHASE24_ROOT = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_context_2026-05-18" / "h1_m30"


PHASE23_ROWS = """phase|candidate_order|candidate_id|review_category|swing_degree|chart_path|visual_count_status|visual_quality_score|degree_fit|likely_problem_if_any|should_user_review|user_review_priority|suggested_action|good_example_rank|visual_notes
phase2_3_visual_review|1|impulse_forex_audjpy_h1_minor_impulse_013|impulse|minor|charts\\impulses\\001_impulse_forex_audjpy_h1_minor_impulse_013.png|plausible_but_needs_review|3|mixed|wave 5 ends before the clearer local high; later candles look like the same extension|yes|medium|review_manually||0-1-2-3-4 reads well, but the fifth looks premature.
phase2_3_visual_review|2|impulse_metals_xagusd_h1_minor_impulse_019|impulse|minor|charts\\impulses\\002_impulse_metals_xagusd_h1_minor_impulse_019.png|excellent_example|5|good||no|low|use_as_good_example||Clean bearish impulse: clear alternation, wave 4 does not invade wave 1, and wave 5 prints a new low.
phase2_3_visual_review|3|impulse_index_aus200_h1_minor_impulse_006|impulse|minor|charts\\impulses\\003_impulse_index_aus200_h1_minor_impulse_006.png|visually_forced|2|mixed|wave 5 cuts the decline before the dominant visual low|yes|high|use_as_ambiguous_example||Internal count is readable until wave 4, but wave 5 sits inside a larger bearish continuation.
phase2_3_visual_review|4|impulse_forex_audjpy_h1_minor_impulse_015|impulse|minor|charts\\impulses\\004_impulse_forex_audjpy_h1_minor_impulse_015.png|excellent_example|5|good||no|low|use_as_good_example|1|Very good bullish impulse: wave 3 is strong, wave 4 is clean, and wave 5 reaches the visible high.
phase2_3_visual_review|5|impulse_forex_audjpy_h1_intermediate_impulse_009|impulse|intermediate|charts\\impulses\\005_impulse_forex_audjpy_h1_intermediate_impulse_009.png|visually_defensible|4|mixed|waves 0-1-2 are small relative to waves 3-5 for intermediate degree|yes|medium|review_manually||Valid visual count, but the early proportionality is a bit micro compared with the final leg.
phase2_3_visual_review|6|impulse_metals_xauusd_h1_intermediate_impulse_013|impulse|intermediate|charts\\impulses\\006_impulse_metals_xauusd_h1_intermediate_impulse_013.png|excellent_example|5|good||no|low|use_as_good_example||Proportional bearish impulse: wave 3 breaks well, wave 4 corrects without invasion, and wave 5 marks the final low.
phase2_3_visual_review|7|impulse_index_aus200_h1_intermediate_impulse_004|impulse|intermediate|charts\\impulses\\007_impulse_index_aus200_h1_intermediate_impulse_004.png|plausible_but_needs_review|3|mixed|wave 5 ends before a visually relevant bearish continuation|yes|high|review_manually||The 0-4 sequence is defensible, but wave 5 does not exhaust the later move.
phase2_3_visual_review|8|impulse_forex_eurjpy_m30_intermediate_impulse_005|impulse|intermediate|charts\\impulses\\008_impulse_forex_eurjpy_m30_intermediate_impulse_005.png|visually_forced|2|mixed|0-1 drags through a long drift and wave 5 misses the more natural later low|yes|high|use_as_ambiguous_example||A bearish 1-2-3-4-5 can be seen, but the first leg and final low are weak visually.
phase2_3_visual_review|9|impulse_metals_xagusd_h1_major_impulse_009|impulse|major|charts\\impulses\\009_impulse_metals_xagusd_h1_major_impulse_009.png|excellent_example|5|good||no|low|use_as_good_example|3|Very clear major bearish impulse: broad pivots, strong wave 3, brief wave 4 and final low at wave 5.
phase2_3_visual_review|10|impulse_index_aus200_h1_major_impulse_002|impulse|major|charts\\impulses\\010_impulse_index_aus200_h1_major_impulse_002.png|likely_false_candidate|2|too_micro|for major degree, wave 5 stops too early and misses the later larger low|yes|high|use_as_negative_example||Could be a smaller impulse, but as major it is visually incomplete.
phase2_3_visual_review|11|impulse_index_aus200_h1_major_impulse_010|impulse|major|charts\\impulses\\011_impulse_index_aus200_h1_major_impulse_010.png|excellent_example|5|good||no|low|use_as_good_example||Good major bearish impulse: balanced pivots and wave 5 reaches a new low before rebound.
phase2_3_visual_review|12|impulse_index_hk50_m30_major_impulse_003|impulse|major|charts\\impulses\\012_impulse_index_hk50_m30_major_impulse_003.png|plausible_but_needs_review|3|mixed|wave 5 ends before a lower later low; possible premature finish|yes|medium|review_manually||The 0-5 structure exists, but it is not the most natural end of the whole bearish swing.
phase2_3_visual_review|13|partial_123_forex_audjpy_h1_intermediate_partial123_009|partial_123|intermediate|charts\\partials\\013_partial_123_forex_audjpy_h1_intermediate_partial123_009.png|excellent_example|5|good||no|low|use_as_good_example||Clean bullish 1-2-3 partial; wave 2 respects origin and wave 3 breaks with visible continuity.
phase2_3_visual_review|14|partial_123_metals_xagusd_h1_intermediate_partial123_003|partial_123|intermediate|charts\\partials\\014_partial_123_metals_xagusd_h1_intermediate_partial123_003.png|excellent_example|5|good||no|low|use_as_good_example|2|Very clear bearish partial: 0 high, strong wave 1 decline, clear wave 2 rebound and broad wave 3 extension.
phase2_3_visual_review|15|partial_123_index_aus200_h1_intermediate_partial123_001|partial_123|intermediate|charts\\partials\\015_partial_123_index_aus200_h1_intermediate_partial123_001.png|too_micro|2|too_micro|the 1-2-3 is a small topping zigzag, not a convincing intermediate launch|yes|high|use_as_negative_example||Wave 3 barely exceeds wave 1 and price reverses strongly right after.
phase2_3_visual_review|16|partial_123_forex_audjpy_h1_intermediate_partial123_011|partial_123|intermediate|charts\\partials\\016_partial_123_forex_audjpy_h1_intermediate_partial123_011.png|excellent_example|5|good||no|low|use_as_good_example||Very clean bullish 1-2-3 partial: visible wave 1, ordered wave 2 and wave 3 reaches the main high.
phase2_3_visual_review|17|partial_123_forex_audjpy_h1_minor_partial123_007|partial_123|minor|charts\\partials\\017_partial_123_forex_audjpy_h1_minor_partial123_007.png|ambiguous|2|mixed|wave 3 barely improves on wave 1; looks more like corrective range than impulsive start|yes|medium|use_as_ambiguous_example||Fits minor degree, but lacks visual breakout after wave 2.
phase2_3_visual_review|18|partial_123_metals_xagusd_h1_minor_partial123_002|partial_123|minor|charts\\partials\\018_partial_123_metals_xagusd_h1_minor_partial123_002.png|visually_defensible|4|mixed|0-3 is clear, but wave 3 acts as a terminal top before a strong decline|yes|medium|review_manually||Good geometric 1-2-3, but not ideal as a clean continuation template.
phase2_3_visual_review|19|partial_123_index_aus200_h1_minor_partial123_001|partial_123|minor|charts\\partials\\019_partial_123_index_aus200_h1_minor_partial123_001.png|excellent_example|5|good||no|low|use_as_good_example||Clean bullish 0-1-2-3; wave 2 is proportional and wave 3 marks a clear high before reversal.
phase2_3_visual_review|20|partial_123_forex_audjpy_h1_minor_partial123_013|partial_123|minor|charts\\partials\\020_partial_123_forex_audjpy_h1_minor_partial123_013.png|visually_defensible|4|good|pivots 1 and 2 are close and small versus 2-3|no|low|use_as_good_example||Defensible bullish 1-2-3; compact start, but wave 3 breaks clearly and minor degree fits.
phase2_3_visual_review|21|partial_123_forex_audjpy_h1_major_partial123_007|partial_123|major|charts\\partials\\021_partial_123_forex_audjpy_h1_major_partial123_007.png|excellent_example|5|good||no|low|use_as_good_example|2|Very clear major bullish 1-2-3; 0-1-2 prepares a broad impulse into wave 3 without forced pivots.
phase2_3_visual_review|22|partial_123_metals_xagusd_h1_major_partial123_006|partial_123|major|charts\\partials\\022_partial_123_metals_xagusd_h1_major_partial123_006.png|excellent_example|5|good||no|low|use_as_good_example||Clear major bullish 1-2-3; 0 is a visible bottom, 2 respects structure, and 3 completes a clean advance.
phase2_3_visual_review|23|partial_123_index_aus200_h1_major_partial123_002|partial_123|major|charts\\partials\\023_partial_123_index_aus200_h1_major_partial123_002.png|excellent_example|5|good||no|low|use_as_good_example|1|Very clean major bearish 1-2-3; 0 high, wave 1 decline, wave 2 pullback, and wave 3 new low.
phase2_3_visual_review|24|partial_123_forex_eurusd_h1_major_partial123_002|partial_123|major|charts\\partials\\024_partial_123_forex_eurusd_h1_major_partial123_002.png|excellent_example|5|good||no|low|use_as_good_example|3|Clear bearish 1-2-3; major swings are coherent and wave 3 is visually well supported.
phase2_3_visual_review|25|abc_forex_audjpy_h1_abc_009|abc|intermediate|charts\\abc\\025_abc_forex_audjpy_h1_abc_009.png|plausible_but_needs_review|3|mixed|multiple ABC sequences overlap and the exact candidate is not isolated|yes|high|review_manually||The central ABC is plausible, but too many crossed labels make it weak as clean evidence.
phase2_3_visual_review|26|abc_metals_xagusd_h1_abc_003|abc|intermediate|charts\\abc\\026_abc_metals_xagusd_h1_abc_003.png|ambiguous|2|unclear|repeated A/B/C paths and crossed diagonals prevent isolating the sequence|yes|high|do_not_use_for_rules||ABC reading is unreliable in this image; labels dominate the visual structure.
phase2_3_visual_review|27|abc_index_aus200_h1_abc_004|abc|intermediate|charts\\abc\\027_abc_index_aus200_h1_abc_004.png|ambiguous|2|unclear|several bearish ABC routes overlap and target leg is not unambiguous|yes|high|do_not_use_for_rules||A broad bearish move exists, but repeated labels make the exact count ambiguous.
phase2_3_visual_review|28|abc_forex_audjpy_h1_abc_011|abc|intermediate|charts\\abc\\028_abc_forex_audjpy_h1_abc_011.png|visually_defensible|4|good|extra overlays remain, though the main right-side ABC is traceable|yes|low|review_manually||Defensible intermediate bullish ABC, but it needs a cleaner isolated chart.
phase2_3_visual_review|29|abc_forex_audjpy_h1_abc_007|abc|minor|charts\\abc\\029_abc_forex_audjpy_h1_abc_007.png|plausible_but_needs_review|3|mixed|minor ABC is plausible but many close labels cross the same area|yes|medium|use_as_ambiguous_example||Useful for discussing overlap, too busy for a good positive example.
phase2_3_visual_review|30|abc_metals_xagusd_h1_abc_002|abc|minor|charts\\abc\\030_abc_metals_xagusd_h1_abc_002.png|too_coarse|2|too_coarse|for minor degree, it covers too large a silver swing with contradictory ABC labels|yes|high|use_as_negative_example||Visible movement is larger than minor; overlapping paths argue against positive rule use.
phase2_3_visual_review|31|abc_index_aus200_h1_abc_006|abc|minor|charts\\abc\\031_abc_index_aus200_h1_abc_006.png|too_coarse|2|too_coarse|minor count covers a broad selloff and C is far from a local oscillation|yes|high|use_as_negative_example||Too large for minor and repeated A/B labels make the reading forced.
phase2_3_visual_review|32|abc_forex_audjpy_h1_abc_013|abc|minor|charts\\abc\\032_abc_forex_audjpy_h1_abc_013.png|plausible_but_needs_review|3|mixed|bullish ABC is plausible but closer to intermediate scale; crossed diagonals remain|yes|medium|use_as_ambiguous_example||0-A-B-C can be understood, but not clean enough for a positive example.
phase2_3_visual_review|33|abc_metals_xagusd_h1_abc_006|abc|major|charts\\abc\\033_abc_metals_xagusd_h1_abc_006.png|visually_defensible|4|good|main candidate is readable but overlaps with previous ABC overlays|yes|low|review_manually||Defensible major bullish ABC from the March low to C, but needs an isolated chart.
phase2_3_visual_review|34|abc_index_aus200_h1_abc_002|abc|major|charts\\abc\\034_abc_index_aus200_h1_abc_002.png|visually_defensible|4|good|previous A/B labels repeat, though main bearish ABC is visible|yes|low|review_manually||Major bearish leg into C is coherent, but not as clean as the partial 1-2-3 cases.
phase2_3_visual_review|35|abc_forex_eurusd_h1_abc_002|abc|major|charts\\abc\\035_abc_forex_eurusd_h1_abc_002.png|ambiguous|2|mixed|too many repeated routes and labels; A/B/C is not isolated reliably|yes|high|do_not_use_for_rules||Bearish context exists, but the image cannot support a single clear ABC.
phase2_3_visual_review|36|abc_forex_gbpusd_h1_abc_003|abc|major|charts\\abc\\036_abc_forex_gbpusd_h1_abc_003.png|visually_defensible|4|good|right-side major ABC is legible, but early overlays pollute the view|yes|medium|review_manually||Defensible 0-A-B-C from March low, useful only if reviewed in a cleaner isolated chart.
phase2_3_visual_review|37|near_miss_forex_audjpy_h1_intermediate_impulse_011|near_miss|intermediate|charts\\impulses\\037_near_miss_forex_audjpy_h1_intermediate_impulse_011.png|visually_defensible|4|good|wave 4 enters wave 1 territory and wave 5 remains below wave 3|yes|medium|use_as_ambiguous_example||Broad and legible count; good bullish near-miss due to truncation and fourth-wave overlap.
phase2_3_visual_review|38|near_miss_metals_xagusd_h1_intermediate_impulse_003|near_miss|intermediate|charts\\impulses\\038_near_miss_metals_xagusd_h1_intermediate_impulse_003.png|visually_defensible|4|good|wave 4 overlaps wave 1 and wave 5 does not break the wave 3 extreme|yes|medium|use_as_ambiguous_example||Readable bearish sequence; good near-miss although truncated fifth reduces impulse quality.
phase2_3_visual_review|39|near_miss_index_aus200_h1_intermediate_impulse_008|near_miss|intermediate|charts\\impulses\\039_near_miss_index_aus200_h1_intermediate_impulse_008.png|plausible_but_needs_review|3|mixed|wave 3 dominates and wave 5 is a small reaction rather than continuation|yes|high|review_manually||Bearish count is understandable, but it feels like rebound after a strong leg rather than clean full impulse.
phase2_3_visual_review|40|near_miss_forex_audjpy_h1_minor_impulse_007|near_miss|minor|charts\\impulses\\040_near_miss_forex_audjpy_h1_minor_impulse_007.png|visually_forced|2|mixed|lateral/corrective segment; wave 5 adds no clear extension|yes|low|use_as_negative_example||Too fitted inside range noise; do not use for positive rules.
phase2_3_visual_review|41|near_miss_metals_xagusd_h1_minor_impulse_002|near_miss|minor|charts\\impulses\\041_near_miss_metals_xagusd_h1_minor_impulse_002.png|plausible_but_needs_review|3|too_coarse|wave 3 absorbs nearly the whole move and wave 5 is weak versus the later turn|yes|medium|review_manually||Interesting near-miss, but too dependent on one dominant swing for minor degree.
phase2_3_visual_review|42|near_miss_index_aus200_h1_minor_impulse_012|near_miss|minor|charts\\impulses\\042_near_miss_index_aus200_h1_minor_impulse_012.png|visually_defensible|4|good|wave 5 does not exceed wave 3, leaving a truncated structure|yes|medium|use_as_ambiguous_example||Good compact bearish near-miss; failed fifth is visible without indicators.
phase2_3_visual_review|43|near_miss_forex_audjpy_h1_major_impulse_007|near_miss|major|charts\\impulses\\043_near_miss_forex_audjpy_h1_major_impulse_007.png|visually_defensible|4|good|wave 4 retraces deeply and wave 5 stays below wave 3|yes|medium|use_as_ambiguous_example||Broad major reading; useful as almost-valid but truncated impulse.
phase2_3_visual_review|44|near_miss_metals_xagusd_h1_major_impulse_006|near_miss|major|charts\\impulses\\044_near_miss_metals_xagusd_h1_major_impulse_006.png|visually_defensible|4|good|wave 4 invades wave 1 and wave 5 does not reach wave 3 high|yes|medium|use_as_ambiguous_example||One of the clearest near-misses; main swings are well separated.
phase2_3_visual_review|45|near_miss_index_aus200_h1_major_impulse_006|near_miss|major|charts\\impulses\\045_near_miss_index_aus200_h1_major_impulse_006.png|visually_defensible|4|good|wave 4 overlaps wave 1 and wave 5 fails before wave 3 extreme|yes|medium|use_as_ambiguous_example||Clean major bearish near-miss; good ambiguous case.
phase2_3_visual_review|46|hard_invalid_forex_audjpy_h1_intermediate_impulse_001|hard_invalid|intermediate|charts\\invalidations\\046_hard_invalid_forex_audjpy_h1_intermediate_impulse_001.png|hard_invalid_correct|5|good|wave 2 breaks origin and wave 4 invalidates again|no|low|use_as_negative_example||Very clear negative; no defensible impulse despite readable swings.
phase2_3_visual_review|47|hard_invalid_metals_xagusd_h1_intermediate_impulse_001|hard_invalid|intermediate|charts\\invalidations\\047_hard_invalid_metals_xagusd_h1_intermediate_impulse_001.png|hard_invalid_correct|5|good|wave 2 exceeds origin and there are multiple strong overlaps|no|low|use_as_negative_example||Excellent negative control; invalidation is directly visible in price and labels.
phase2_3_visual_review|48|hard_invalid_index_aus200_h1_intermediate_impulse_001|hard_invalid|intermediate|charts\\invalidations\\048_hard_invalid_index_aus200_h1_intermediate_impulse_001.png|hard_invalid_correct|4|mixed|more topping range than impulse; wave 3 is short and wave 5 fails|no|low|use_as_negative_example||Good negative, less clean as intermediate because labeled region is congestion.
phase2_3_visual_review|49|hard_invalid_forex_audjpy_h1_minor_impulse_001|hard_invalid|minor|charts\\invalidations\\049_hard_invalid_forex_audjpy_h1_minor_impulse_001.png|hard_invalid_correct|4|mixed|wave 4 breaks impulse reading and mixes unequal swing sizes|no|low|use_as_negative_example||Clear negative; useful, though early waves and 4-5 have different scale.
phase2_3_visual_review|50|hard_invalid_metals_xagusd_h1_minor_impulse_001|hard_invalid|minor|charts\\invalidations\\050_hard_invalid_metals_xagusd_h1_minor_impulse_001.png|hard_invalid_correct|5|good|wave 3 does not exceed wave 1 and wave 4 breaks impulse logic|no|low|use_as_negative_example||Very good minor negative control; labels show several violations clearly.
phase2_3_visual_review|51|hard_invalid_index_aus200_h1_minor_impulse_001|hard_invalid|minor|charts\\invalidations\\051_hard_invalid_index_aus200_h1_minor_impulse_001.png|hard_invalid_correct|4|good|wave 3 is short and wave 5 does not confirm a new extreme|no|low|use_as_negative_example||Valid negative; reads as topping range more than impulse.
phase2_3_visual_review|52|hard_invalid_forex_audjpy_h1_major_impulse_001|hard_invalid|major|charts\\invalidations\\052_hard_invalid_forex_audjpy_h1_major_impulse_001.png|hard_invalid_correct|5|good|wave 2 breaks origin and wave 5 does not exceed wave 3|no|low|use_as_negative_example||Very clear major negative; scale and pivots fit well for demonstrating invalidation.
phase2_3_visual_review|53|hard_invalid_metals_xagusd_h1_major_impulse_001|hard_invalid|major|charts\\invalidations\\053_hard_invalid_metals_xagusd_h1_major_impulse_001.png|hard_invalid_correct|5|good|wave 2 breaks origin and later sequence accumulates overlaps|no|low|use_as_negative_example||Excellent major negative; robust and easy to justify without indicators.
phase2_3_visual_review|54|hard_invalid_index_aus200_h1_major_impulse_001|hard_invalid|major|charts\\invalidations\\054_hard_invalid_index_aus200_h1_major_impulse_001.png|hard_invalid_correct|4|good|wave 3 does not exceed wave 1 and wave 5 is corrective rebound before breakdown|no|low|use_as_negative_example||Good major negative; structure breaks as topping range turns into decline.
"""


PHASE24_ROWS = """phase|candidate_order|candidate_id|review_category|swing_degree|context_chart_path|context_review_status|ema_usefulness|ewo_usefulness|htf_ltf_usefulness|context_changes_phase23_reading|should_user_review|user_review_priority|suggested_action|good_context_example_rank|visual_notes
phase2_4_context|1|impulse_forex_audjpy_h1_minor_impulse_013|impulse|minor|charts\\impulses\\001_impulse_forex_audjpy_h1_minor_impulse_013.png|context_confirms|useful|useful_for_wave_role|useful|false|no|low|use_as_good_context_example||EMAs turn bullish during the 0-5; price stays above band, EWO supports wave 3/5, and HTF/LTF validate the impulse.
phase2_4_context|2|impulse_metals_xagusd_h1_minor_impulse_019|impulse|minor|charts\\impulses\\002_impulse_metals_xagusd_h1_minor_impulse_019.png|context_conflict_suspicious|partially_useful|useful_for_momentum_only|conflict_suspicious|true|yes|high|review_manually||Bearish count sits in choppy rebound; EMA/HTF do not validate the same count cleanly.
phase2_4_context|3|impulse_index_aus200_h1_minor_impulse_006|impulse|minor|charts\\impulses\\003_impulse_index_aus200_h1_minor_impulse_006.png|context_explains_ambiguity|useful|useful_for_wave_role|conflict_explains_case|true|no|low|use_as_ambiguous_context||Local bearish impulse is supported by LTF/EWO, but H4 bullish reframes it as correction against HTF.
phase2_4_context|4|impulse_forex_audjpy_h1_minor_impulse_015|impulse|minor|charts\\impulses\\004_impulse_forex_audjpy_h1_minor_impulse_015.png|context_confirms|useful|useful_for_wave_role|useful|false|no|low|use_as_good_context_example||Bullish 0-5 remains above EMAs with HTF aligned; EWO expands during impulse and cools late.
phase2_4_context|5|impulse_forex_audjpy_h1_intermediate_impulse_009|impulse|intermediate|charts\\impulses\\005_impulse_forex_audjpy_h1_intermediate_impulse_009.png|context_confirms|useful|useful_for_wave_role|useful|false|no|low|use_as_good_context_example||AUDJPY intermediate structure gets clear bullish support from EMAs, EWO and HTF.
phase2_4_context|6|impulse_metals_xauusd_h1_intermediate_impulse_013|impulse|intermediate|charts\\impulses\\006_impulse_metals_xauusd_h1_intermediate_impulse_013.png|context_explains_ambiguity|partially_useful|useful_for_wave_role|conflict_explains_case|true|no|low|use_as_ambiguous_context||Bearish 0-5 is locally valid, but HTF bullish makes it counter-context.
phase2_4_context|7|impulse_index_aus200_h1_intermediate_impulse_004|impulse|intermediate|charts\\impulses\\007_impulse_index_aus200_h1_intermediate_impulse_004.png|context_explains_ambiguity|useful|useful_for_wave_role|conflict_explains_case|true|no|low|use_as_ambiguous_context||LTF and EWO support bearish wave 3; HTF bullish explains correction or early reversal.
phase2_4_context|8|impulse_forex_eurjpy_m30_intermediate_impulse_005|impulse|intermediate|charts\\impulses\\008_impulse_forex_eurjpy_m30_intermediate_impulse_005.png|context_confirms|useful|useful_for_wave_role|useful|false|no|low|use_as_good_context_example|1|Clean context example: EMA50 turns under EMA150, EWO sinks at wave 3, and H1 confirms bearish bias.
phase2_4_context|9|impulse_metals_xagusd_h1_major_impulse_009|impulse|major|charts\\impulses\\009_impulse_metals_xagusd_h1_major_impulse_009.png|context_confirms|useful|useful_for_wave_role|useful|false|no|low|use_as_good_context_example|3|Major bearish count is well contextualized by price below band, negative EWO and aligned HTF/LTF.
phase2_4_context|10|impulse_index_aus200_h1_major_impulse_002|impulse|major|charts\\impulses\\010_impulse_index_aus200_h1_major_impulse_002.png|context_explains_ambiguity|useful|useful_for_wave_role|conflict_explains_case|true|no|low|use_as_ambiguous_context||LTF/EWO support bearish count, but H4 bullish changes it to correction against higher frame.
phase2_4_context|11|impulse_index_aus200_h1_major_impulse_010|impulse|major|charts\\impulses\\011_impulse_index_aus200_h1_major_impulse_010.png|context_partially_supports|useful|useful_for_momentum_only|useful|true|yes|high|review_manually||Bearish context aligns, but 0-5 is late and choppy; EWO does not separate wave role well.
phase2_4_context|12|impulse_index_hk50_m30_major_impulse_003|impulse|major|charts\\impulses\\012_impulse_index_hk50_m30_major_impulse_003.png|context_partially_supports|partially_useful|useful_for_momentum_only|partially_useful|true|yes|medium|review_manually||Looks more like correction after strong rise; EMAs turn late and later rebound weakens rule value.
phase2_4_context|13|partial_123_forex_audjpy_h1_intermediate_partial123_009|partial_123|intermediate|charts\\partials\\013_partial_123_forex_audjpy_h1_intermediate_partial123_009.png|context_confirms|useful|useful_for_wave_role|useful|false|no|low|use_as_good_context_example|2|Very clear bullish partial: wave 3 launches above EMAs, EWO rises, HTF H4 aligns.
phase2_4_context|14|partial_123_metals_xagusd_h1_intermediate_partial123_003|partial_123|intermediate|charts\\partials\\014_partial_123_metals_xagusd_h1_intermediate_partial123_003.png|context_explains_ambiguity|useful|useful_for_wave_role|conflict_explains_case|true|no|low|use_as_ambiguous_context||Strong bearish 1-2-3 from top; local context confirms drop, HTF bullish frames it as violent correction.
phase2_4_context|15|partial_123_index_aus200_h1_intermediate_partial123_001|partial_123|intermediate|charts\\partials\\015_partial_123_index_aus200_h1_intermediate_partial123_001.png|context_confirms|useful|useful_for_momentum_only|useful|false|no|low|use_as_good_context_example||Context supports early bullish partial, but EWO is more directional than wave-role specific.
phase2_4_context|16|partial_123_forex_audjpy_h1_intermediate_partial123_011|partial_123|intermediate|charts\\partials\\016_partial_123_forex_audjpy_h1_intermediate_partial123_011.png|context_confirms|useful|useful_for_wave_role|useful|false|no|low|use_as_good_context_example||Vertical bullish partial with bullish EMAs and positive EWO during acceleration.
phase2_4_context|17|partial_123_forex_audjpy_h1_minor_partial123_007|partial_123|minor|charts\\partials\\017_partial_123_forex_audjpy_h1_minor_partial123_007.png|context_conflicts_but_useful|partially_useful|useful_for_wave_role|conflict_explains_case|true|yes|medium|review_manually||Bullish 1-2-3 starts with bearish LTF alignment but HTF/EWO explain transition.
phase2_4_context|18|partial_123_metals_xagusd_h1_minor_partial123_002|partial_123|minor|charts\\partials\\018_partial_123_metals_xagusd_h1_minor_partial123_002.png|context_partially_supports|partially_useful|useful_for_wave_role|partially_useful|true|yes|medium|review_manually||EWO/HTF support wave 3 spike, but EMAs lag and later fall prevents clean rule use.
phase2_4_context|19|partial_123_index_aus200_h1_minor_partial123_001|partial_123|minor|charts\\partials\\019_partial_123_index_aus200_h1_minor_partial123_001.png|context_partially_supports|partially_useful|useful_for_momentum_only|partially_useful|softens_confidence|yes|medium|use_as_ambiguous_context||EMAs and HTF support local bullish 1-2-3, but it is near exhaustion before a strong turn.
phase2_4_context|20|partial_123_forex_audjpy_h1_minor_partial123_013|partial_123|minor|charts\\partials\\020_partial_123_forex_audjpy_h1_minor_partial123_013.png|context_confirms|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example|1|Excellent context example: 1-2-3 starts after base, breaks EMAs, EWO stays positive and HTF/LTF align.
phase2_4_context|21|partial_123_forex_audjpy_h1_major_partial123_007|partial_123|major|charts\\partials\\021_partial_123_forex_audjpy_h1_major_partial123_007.png|context_confirms|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example||Major bullish count captures broad impulse; EMAs align and EWO confirms strength.
phase2_4_context|22|partial_123_metals_xagusd_h1_major_partial123_006|partial_123|major|charts\\partials\\022_partial_123_metals_xagusd_h1_major_partial123_006.png|context_explains_ambiguity|partially_useful|useful_for_wave_role|conflict_explains_case|clarifies_transition_case|yes|medium|use_as_ambiguous_context||Good transition case: bullish 1-2-3 crosses from bearish EMAs and EWO improves.
phase2_4_context|23|partial_123_index_aus200_h1_major_partial123_002|partial_123|major|charts\\partials\\023_partial_123_index_aus200_h1_major_partial123_002.png|context_conflicts_but_useful|useful|useful_for_wave_role|conflict_explains_case|reframes_as_counter_htf_move|no|low|use_as_ambiguous_context||Strong bearish 1-2-3 from previously bullish area; context frames it as reversal/correction.
phase2_4_context|24|partial_123_forex_eurusd_h1_major_partial123_002|partial_123|major|charts\\partials\\024_partial_123_forex_eurusd_h1_major_partial123_002.png|context_confirms|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example|2|Clean bearish example: price below EMAs, falling alignment, negative EWO and HTF aligned.
phase2_4_context|25|abc_forex_audjpy_h1_abc_009|abc|intermediate|charts\\abc\\025_abc_forex_audjpy_h1_abc_009.png|context_partially_supports|useful|useful_for_wave_role|useful|downgrades_to_cluttered_but_supported|yes|medium|use_as_ambiguous_context||Bullish context is good, but too many ABC paths overlap; context supports bias, not unique count.
phase2_4_context|26|abc_metals_xagusd_h1_abc_003|abc|intermediate|charts\\abc\\026_abc_metals_xagusd_h1_abc_003.png|context_conflicts_but_useful|useful|useful_for_wave_role|conflict_explains_case|reframes_as_counter_htf_move|yes|medium|use_as_ambiguous_context||Local bearish ABC is plausible, but HTF conflict and overlays force ambiguity.
phase2_4_context|27|abc_index_aus200_h1_abc_004|abc|intermediate|charts\\abc\\027_abc_index_aus200_h1_abc_004.png|context_conflicts_but_useful|useful|useful_for_wave_role|conflict_explains_case|needs_manual_count_selection|yes|high|review_manually||Bearish context after top is convincing, but several ABCs overlap; not rule-clean.
phase2_4_context|28|abc_forex_audjpy_h1_abc_011|abc|intermediate|charts\\abc\\028_abc_forex_audjpy_h1_abc_011.png|context_confirms|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example||Defensible bullish ABC with EMAs turning bullish, positive EWO and HTF support.
phase2_4_context|29|abc_forex_audjpy_h1_abc_007|abc|minor|charts\\abc\\029_abc_forex_audjpy_h1_abc_007.png|context_explains_ambiguity|partially_useful|useful_for_momentum_only|conflict_explains_case|clarifies_transition_case|yes|medium|use_as_ambiguous_context||Base/transition case; EMAs are not clean for minor ABC but EWO/HTF explain later bullish start.
phase2_4_context|30|abc_metals_xagusd_h1_abc_002|abc|minor|charts\\abc\\030_abc_metals_xagusd_h1_abc_002.png|context_partially_supports|partially_useful|useful_for_momentum_only|partially_useful|softens_confidence|yes|medium|use_as_ambiguous_context||Minor bullish ABC fits rebound, but later large fall and late EMA support reduce confidence.
phase2_4_context|31|abc_index_aus200_h1_abc_006|abc|minor|charts\\abc\\031_abc_index_aus200_h1_abc_006.png|context_explains_ambiguity|useful|useful_for_wave_role|conflict_explains_case|needs_manual_count_selection|yes|high|review_manually||Context explains bearish break, but overlapping minor ABCs make the count non-clean.
phase2_4_context|32|abc_forex_audjpy_h1_abc_013|abc|minor|charts\\abc\\032_abc_forex_audjpy_h1_abc_013.png|context_confirms|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example||Good minor bullish ABC context; some overlap remains but EMAs/EWO/HTF help.
phase2_4_context|33|abc_metals_xagusd_h1_abc_006|abc|major|charts\\abc\\033_abc_metals_xagusd_h1_abc_006.png|context_explains_ambiguity|partially_useful|useful_for_wave_role|conflict_explains_case|clarifies_transition_case|yes|medium|use_as_ambiguous_context||Major bullish ABC/recovery context; EMAs lag and overlays make it contextual, not normative.
phase2_4_context|34|abc_index_aus200_h1_abc_002|abc|major|charts\\abc\\034_abc_index_aus200_h1_abc_002.png|context_conflicts_but_useful|useful|useful_for_wave_role|conflict_explains_case|reframes_as_counter_htf_move|no|low|use_as_ambiguous_context||Major bearish ABC from highs; EMAs/EWO confirm fall while HTF bullish frames conflict.
phase2_4_context|35|abc_forex_eurusd_h1_abc_002|abc|major|charts\\abc\\035_abc_forex_eurusd_h1_abc_002.png|context_confirms|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example|3|Good bearish aligned context: below EMAs, bearish alignment, negative EWO and bearish HTF.
phase2_4_context|36|abc_forex_gbpusd_h1_abc_003|abc|major|charts\\abc\\036_abc_forex_gbpusd_h1_abc_003.png|context_conflict_suspicious|useful|useful_for_momentum_only|conflict_suspicious|downgrades_to_countertrend_bounce|yes|high|use_as_negative_example||ABC bullish is against bearish EMAs/HTF; EWO only confirms local bounce.
phase2_4_context|37|near_miss_forex_audjpy_h1_intermediate_impulse_011|near_miss|intermediate|charts\\impulses\\037_near_miss_forex_audjpy_h1_intermediate_impulse_011.png|context_partially_supports|useful|useful_for_wave_role|useful|no_change|no|low|use_as_ambiguous_context||Context supports bullish direction and wave 3 momentum but does not erase 4-1 overlap/truncated fifth.
phase2_4_context|38|near_miss_metals_xagusd_h1_intermediate_impulse_003|near_miss|intermediate|charts\\impulses\\038_near_miss_metals_xagusd_h1_intermediate_impulse_003.png|context_conflicts_but_useful|useful|useful_for_wave_role|conflict_explains_case|counter_htf_reframe|yes|medium|use_as_ambiguous_context||LTF bearish/EWO support the leg, but H4 bullish makes it counter-HTF correction.
phase2_4_context|39|near_miss_index_aus200_h1_intermediate_impulse_008|near_miss|intermediate|charts\\impulses\\039_near_miss_index_aus200_h1_intermediate_impulse_008.png|context_explains_ambiguity|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example|3|Bearish context reinforces selloff; EWO marks wave 3 low and rebound explains failed fifth.
phase2_4_context|40|near_miss_forex_audjpy_h1_minor_impulse_007|near_miss|minor|charts\\impulses\\040_near_miss_forex_audjpy_h1_minor_impulse_007.png|context_explains_ambiguity|partially_useful|useful_for_momentum_only|conflict_explains_case|downgrade|yes|medium|use_as_ambiguous_context||Small bullish 0-5 is range/base inside LTF-HTF conflict, not rule-quality impulse.
phase2_4_context|41|near_miss_metals_xagusd_h1_minor_impulse_002|near_miss|minor|charts\\impulses\\041_near_miss_metals_xagusd_h1_minor_impulse_002.png|context_misleading|misleading|useful_for_wave_role|conflict_suspicious|downgrade|yes|high|use_as_negative_example||EMA/HTF bullish context should not rescue deep wave 4 and failed wave 5; useful warning case.
phase2_4_context|42|near_miss_index_aus200_h1_minor_impulse_012|near_miss|minor|charts\\impulses\\042_near_miss_index_aus200_h1_minor_impulse_012.png|context_partially_supports|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example|2|Bearish context and EWO wave 3 trough support the reading while preserving failed fifth warning.
phase2_4_context|43|near_miss_forex_audjpy_h1_major_impulse_007|near_miss|major|charts\\impulses\\043_near_miss_forex_audjpy_h1_major_impulse_007.png|context_partially_supports|useful|useful_for_wave_role|useful|no_change|no|low|use_as_good_context_example|1|Best bullish near-miss context: EMAs/EWO/HTF support direction but do not erase truncated wave 5.
phase2_4_context|44|near_miss_metals_xagusd_h1_major_impulse_006|near_miss|major|charts\\impulses\\044_near_miss_metals_xagusd_h1_major_impulse_006.png|context_explains_ambiguity|partially_useful|useful_for_wave_role|partially_useful|downgrade|yes|medium|use_as_ambiguous_context||EWO supports wave 3 high, but deep wave 4, lower-high wave 5 and later decline keep it ambiguous.
phase2_4_context|45|near_miss_index_aus200_h1_major_impulse_006|near_miss|major|charts\\impulses\\045_near_miss_index_aus200_h1_major_impulse_006.png|context_explains_ambiguity|partially_useful|useful_for_wave_role|useful|no_change|no|low|use_as_ambiguous_context||Bearish backdrop supports context, but EWO rebound into 4-5 highlights failed continuation.
phase2_4_context|46|hard_invalid_forex_audjpy_h1_intermediate_impulse_001|hard_invalid|intermediate|charts\\invalidations\\046_hard_invalid_forex_audjpy_h1_intermediate_impulse_001.png|context_conflicts_but_useful|partially_useful|useful_for_momentum_only|conflict_explains_case|keep_hard_invalid|yes|medium|use_as_negative_example||HTF bullish explains why candidate appears, but broken wave rules dominate.
phase2_4_context|47|hard_invalid_metals_xagusd_h1_intermediate_impulse_001|hard_invalid|intermediate|charts\\invalidations\\047_hard_invalid_metals_xagusd_h1_intermediate_impulse_001.png|context_conflicts_but_useful|useful|useful_for_momentum_only|conflict_explains_case|keep_hard_invalid|no|low|use_as_negative_example||LTF/EWO show selloff, HTF bullish frames it countertrend, and wave 2 origin break is decisive.
phase2_4_context|48|hard_invalid_index_aus200_h1_intermediate_impulse_001|hard_invalid|intermediate|charts\\invalidations\\048_hard_invalid_index_aus200_h1_intermediate_impulse_001.png|context_misleading|misleading|useful_for_momentum_only|conflict_suspicious|downgrade|yes|high|use_as_negative_example||Bullish EMA/HTF lag at a top can falsely support the candidate; EWO weakens before collapse.
phase2_4_context|49|hard_invalid_forex_audjpy_h1_minor_impulse_001|hard_invalid|minor|charts\\invalidations\\049_hard_invalid_forex_audjpy_h1_minor_impulse_001.png|context_misleading|partially_useful|useful_for_momentum_only|partially_useful|keep_hard_invalid|yes|high|use_as_negative_example||High context score may tempt acceptance, but wave rules are broken; EMAs/EWO describe later momentum only.
phase2_4_context|50|hard_invalid_metals_xagusd_h1_minor_impulse_001|hard_invalid|minor|charts\\invalidations\\050_hard_invalid_metals_xagusd_h1_minor_impulse_001.png|context_conflict_suspicious|misleading|useful_for_momentum_only|conflict_suspicious|keep_hard_invalid|yes|medium|use_as_negative_example||EMA/H4 oppose bearish label; EWO final drop does not repair invalid wave structure.
phase2_4_context|51|hard_invalid_index_aus200_h1_minor_impulse_001|hard_invalid|minor|charts\\invalidations\\051_hard_invalid_index_aus200_h1_minor_impulse_001.png|context_misleading|misleading|useful_for_momentum_only|conflict_suspicious|downgrade|yes|high|use_as_negative_example||Bullish EMAs/HTF align with invalid count while EWO weakens and price collapses.
phase2_4_context|52|hard_invalid_forex_audjpy_h1_major_impulse_001|hard_invalid|major|charts\\invalidations\\052_hard_invalid_forex_audjpy_h1_major_impulse_001.png|context_conflicts_but_useful|partially_useful|useful_for_momentum_only|conflict_explains_case|keep_hard_invalid|yes|medium|use_as_negative_example||Useful as bullish base context, but marked count has wave 2/wave 4 breaks.
phase2_4_context|53|hard_invalid_metals_xagusd_h1_major_impulse_001|hard_invalid|major|charts\\invalidations\\053_hard_invalid_metals_xagusd_h1_major_impulse_001.png|context_conflicts_but_useful|useful|useful_for_momentum_only|conflict_explains_case|keep_hard_invalid|no|low|use_as_negative_example||LTF bearish context is useful, but H4 conflict and wave 2 origin break keep it invalid.
phase2_4_context|54|hard_invalid_index_aus200_h1_major_impulse_001|hard_invalid|major|charts\\invalidations\\054_hard_invalid_index_aus200_h1_major_impulse_001.png|context_conflict_suspicious|useful|misleading|conflict_suspicious|keep_hard_invalid|yes|high|use_as_negative_example||LTF EMA rejects bullish count, but H4/EWO can mislead before price breaks down.
"""


def _read_pipe_table(text: str) -> pd.DataFrame:
    reader = csv.DictReader(StringIO(text.strip()), delimiter="|")
    rows = list(reader)
    return pd.DataFrame(rows)


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"yes", "true", "1", "high"}


def _priority_rank(value: Any) -> int:
    mapping = {"high": 0, "1": 0, "medium": 1, "2": 1, "low": 2, "3": 2, "none": 3, "": 3}
    return mapping.get(str(value).strip().lower(), 3)


def _with_absolute_chart_paths(df: pd.DataFrame, root: Path, chart_column: str) -> pd.DataFrame:
    df = df.copy()
    df[f"{chart_column}_absolute"] = df[chart_column].apply(lambda value: str(root / str(value)))
    return df


def _build_user_review(phase23: pd.DataFrame, phase24: pd.DataFrame) -> pd.DataFrame:
    p23 = phase23.copy()
    p23["review_phase"] = "phase2_3_count_only"
    p23["why_review"] = p23.apply(
        lambda row: "manual_flag_or_low_quality" if _boolish(row["should_user_review"]) or int(row["visual_quality_score"]) <= 3 else "",
        axis=1,
    )
    p23 = p23[p23["why_review"] != ""].rename(columns={"chart_path": "chart_path_relative"})
    p23["chart_path_absolute"] = p23["chart_path_relative"].apply(lambda value: str(PHASE23_ROOT / str(value)))
    p23["priority_rank"] = p23["user_review_priority"].apply(_priority_rank)
    p23 = p23[
        [
            "review_phase",
            "candidate_order",
            "candidate_id",
            "review_category",
            "swing_degree",
            "chart_path_relative",
            "chart_path_absolute",
            "visual_count_status",
            "visual_quality_score",
            "degree_fit",
            "likely_problem_if_any",
            "user_review_priority",
            "suggested_action",
            "why_review",
            "visual_notes",
            "priority_rank",
        ]
    ]

    p24 = phase24.copy()
    p24["review_phase"] = "phase2_4_context"
    p24["why_review"] = p24.apply(
        lambda row: "manual_flag_or_context_conflict"
        if _boolish(row["should_user_review"]) or str(row["context_review_status"]) in {"context_misleading", "context_conflict_suspicious"}
        else "",
        axis=1,
    )
    p24 = p24[p24["why_review"] != ""].rename(columns={"context_chart_path": "chart_path_relative"})
    p24["chart_path_absolute"] = p24["chart_path_relative"].apply(lambda value: str(PHASE24_ROOT / str(value)))
    p24["priority_rank"] = p24["user_review_priority"].apply(_priority_rank)
    p24["visual_count_status"] = p24["context_review_status"]
    p24["visual_quality_score"] = ""
    p24["degree_fit"] = ""
    p24["likely_problem_if_any"] = p24["context_changes_phase23_reading"]
    p24 = p24[
        [
            "review_phase",
            "candidate_order",
            "candidate_id",
            "review_category",
            "swing_degree",
            "chart_path_relative",
            "chart_path_absolute",
            "visual_count_status",
            "visual_quality_score",
            "degree_fit",
            "likely_problem_if_any",
            "user_review_priority",
            "suggested_action",
            "why_review",
            "visual_notes",
            "priority_rank",
        ]
    ]

    combined = pd.concat([p23, p24], ignore_index=True)
    combined["candidate_order"] = pd.to_numeric(combined["candidate_order"], errors="coerce")
    return combined.sort_values(["priority_rank", "candidate_order", "review_phase"]).drop(columns=["priority_rank"])


def _build_best_examples(phase23: pd.DataFrame, phase24: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    phase23_good = {
        4: "best clean bullish impulse without indicators",
        6: "clean bearish intermediate impulse without indicators",
        9: "clean major bearish impulse without indicators",
        14: "clean bearish partial 1-2-3 without indicators",
        23: "clean major bearish partial 1-2-3 without indicators",
        24: "clean EURUSD major bearish partial 1-2-3 without indicators",
    }
    phase24_good = {
        8: "best context-confirmed bearish impulse with EMA/EWO/HTF",
        13: "clean context-confirmed bullish partial 1-2-3",
        20: "very clear context-confirmed bullish minor partial 1-2-3",
        24: "clean context-confirmed bearish partial 1-2-3",
        43: "best near-miss showing context supports direction without rescuing truncation",
    }
    for order, reason in phase23_good.items():
        row = phase23[pd.to_numeric(phase23["candidate_order"]) == order].iloc[0].to_dict()
        rows.append(
            {
                "phase": "phase2_3_count_only",
                "candidate_order": order,
                "candidate_id": row["candidate_id"],
                "review_category": row["review_category"],
                "swing_degree": row["swing_degree"],
                "chart_path": str(PHASE23_ROOT / row["chart_path"]),
                "example_type": row["visual_count_status"],
                "why_good": reason,
                "notes": row["visual_notes"],
            }
        )
    for order, reason in phase24_good.items():
        row = phase24[pd.to_numeric(phase24["candidate_order"]) == order].iloc[0].to_dict()
        rows.append(
            {
                "phase": "phase2_4_context",
                "candidate_order": order,
                "candidate_id": row["candidate_id"],
                "review_category": row["review_category"],
                "swing_degree": row["swing_degree"],
                "chart_path": str(PHASE24_ROOT / row["context_chart_path"]),
                "example_type": row["context_review_status"],
                "why_good": reason,
                "notes": row["visual_notes"],
            }
        )
    return pd.DataFrame(rows)


def _summary(phase23: pd.DataFrame, phase24: pd.DataFrame, user_review: pd.DataFrame, best_examples: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {"metric": "phase2_3_reviewed_cases", "value": len(phase23)},
        {"metric": "phase2_4_reviewed_cases", "value": len(phase24)},
        {"metric": "phase2_3_user_review_cases", "value": int(phase23["should_user_review"].apply(_boolish).sum())},
        {"metric": "phase2_4_user_review_cases", "value": int(phase24["should_user_review"].apply(_boolish).sum())},
        {"metric": "combined_user_review_rows", "value": len(user_review)},
        {"metric": "best_example_rows", "value": len(best_examples)},
    ]
    for status, count in phase23["visual_count_status"].value_counts().items():
        rows.append({"metric": f"phase2_3_status_{status}", "value": int(count)})
    for status, count in phase24["context_review_status"].value_counts().items():
        rows.append({"metric": f"phase2_4_status_{status}", "value": int(count)})
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, summary: pd.DataFrame, best_examples: pd.DataFrame, user_review: pd.DataFrame) -> None:
    lines = [
        "# WaveCount compressed visual reaudit",
        "",
        "Fecha: 2026-05-19",
        "",
        "## Alcance",
        "",
        "Se revisaron con subagentes los 54 graficos comprimidos de Fase 2.3 y los 54 graficos comprimidos de Fase 2.4.",
        "Fase 2.3 evalua conteo visual sin indicadores. Fase 2.4 evalua si EMAs 50/150, EWO 5-35 y HTF/LTF ayudan o contradicen.",
        "",
        "No se cambiaron reglas, datos, pivotes, grados, EMAs/EWO, estrategias ni backtests.",
        "",
        "## Resultados",
        "",
    ]
    for _, row in summary.iterrows():
        lines.append(f"- `{row['metric']}`: {row['value']}")
    lines.extend(["", "## Mejores ejemplos propuestos", ""])
    for _, row in best_examples.iterrows():
        lines.append(f"- `{row['phase']}` order {row['candidate_order']} `{row['candidate_id']}`: {row['why_good']}")
    lines.extend(
        [
            "",
            "## Casos que debe revisar el usuario",
            "",
            f"`user_must_review_compressed.csv` contiene {len(user_review)} filas priorizadas.",
            "Prioridad practica: revisar primero high, despues medium. En Fase 2.3 revisar conteo puro; en Fase 2.4 revisar si contexto cambia la lectura.",
            "",
            "## Decision",
            "",
            "La Fase 2.3 comprimida debe revisarse primero. Los mejores ejemplos positivos salen de impulsos y parciales 1-2-3; los ABC siguen necesitando graficos aislados porque las etiquetas se solapan.",
            "La Fase 2.4 comprimida confirma que EMAs/EWO/HTF son utiles como contexto blando, pero no deben rescatar conteos visualmente malos o invalidaciones duras.",
        ]
    )
    (output_dir / "WAVECOUNT_COMPRESSED_REAUDIT_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_reaudit(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    phase23 = _with_absolute_chart_paths(_read_pipe_table(PHASE23_ROWS), PHASE23_ROOT, "chart_path")
    phase24 = _with_absolute_chart_paths(_read_pipe_table(PHASE24_ROWS), PHASE24_ROOT, "context_chart_path")
    phase23["candidate_order"] = pd.to_numeric(phase23["candidate_order"], errors="raise").astype(int)
    phase24["candidate_order"] = pd.to_numeric(phase24["candidate_order"], errors="raise").astype(int)

    if len(phase23) != 54:
        raise RuntimeError(f"phase2_3 expected 54 rows, got {len(phase23)}")
    if len(phase24) != 54:
        raise RuntimeError(f"phase2_4 expected 54 rows, got {len(phase24)}")
    if set(phase23["candidate_id"]) != set(phase24["candidate_id"]):
        raise RuntimeError("phase2_3 and phase2_4 candidate_id sets differ")

    user_review = _build_user_review(phase23, phase24)
    best_examples = _build_best_examples(phase23, phase24)
    summary = _summary(phase23, phase24, user_review, best_examples)

    phase23.to_csv(tables_dir / "phase2_3_visual_reaudit.csv", index=False)
    phase24.to_csv(tables_dir / "phase2_4_context_reaudit.csv", index=False)
    user_review.to_csv(tables_dir / "user_must_review_compressed.csv", index=False)
    best_examples.to_csv(tables_dir / "best_examples_compressed.csv", index=False)
    summary.to_csv(tables_dir / "compressed_reaudit_summary.csv", index=False)
    _write_report(output_dir, summary, best_examples, user_review)

    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": perf_counter() - start,
        "phase2_3_rows": len(phase23),
        "phase2_4_rows": len(phase24),
        "user_must_review_rows": len(user_review),
        "best_example_rows": len(best_examples),
        "outputs": {
            "phase2_3_visual_reaudit": "tables/phase2_3_visual_reaudit.csv",
            "phase2_4_context_reaudit": "tables/phase2_4_context_reaudit.csv",
            "user_must_review_compressed": "tables/user_must_review_compressed.csv",
            "best_examples_compressed": "tables/best_examples_compressed.csv",
            "summary": "tables/compressed_reaudit_summary.csv",
            "report": "WAVECOUNT_COMPRESSED_REAUDIT_REPORT.md",
        },
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    meta = build_reaudit()
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
