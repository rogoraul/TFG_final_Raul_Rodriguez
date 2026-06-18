from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_context_2026-05-18" / "h1_m30"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_1_context_visual_audit_2026-05-19"


RAW_VISUAL_REVIEWS = """candidate_order,candidate_id,visual_review_status,visual_quality_raw,ema_context_usefulness,ewo_context_usefulness,htf_ltf_context_usefulness,inferred_wave_role_from_ewo,likely_problem_if_any,should_user_review_raw,user_review_priority_raw,suggested_action,visual_notes,ewo_rule_assessment
1,impulse_forex_audjpy_h1_minor_impulse_013,visually_defensible,82,useful,useful_for_wave_role,useful,bullish impulse with late momentum peak,wave 5 may be the strongest leg instead of wave 3,no,low,keep_as_good_example,Natural bullish 1-2-3-4-5 after EMA compression; 3 and 5 ride above EMA50/150 and HTF agrees. Count is defensible but the final high looks more like the momentum climax than a clean weaker fifth.,usable_soft_rule
2,impulse_metals_xagusd_h1_minor_impulse_019,visually_forced,30,partially_useful,unclear,conflict_suspicious,weak bearish submove after bullish EWO phase,labels compress a choppy pullback into five waves,yes,high,use_as_negative_example,Bearish count sits inside noisy sideways decline after a bullish rebound; 0-2 are crowded and 3-5 do not separate cleanly. EMA context is bearish locally but HTF conflict and weak structure make it poor for rules.,too_noisy
3,impulse_index_aus200_h1_minor_impulse_006,visually_defensible,78,useful,useful_for_wave_role,conflict_explains_case,bearish wave 3 momentum confirmation,HTF bullish conflict makes it a countertrend impulse,yes,medium,possible_rule_candidate,The bearish 1-2-3-4-5 is visually coherent: wave 3 is the sharp break under both EMAs and wave 5 extends lower. Context says correction against HTF rather than clean trend continuation.,usable_soft_rule
4,impulse_forex_audjpy_h1_minor_impulse_015,visually_defensible,88,useful,useful_for_wave_role,useful,bullish impulse with EWO crest near 3-5 zone,minor ambiguity between wave 3 and extended wave 5,no,low,keep_as_good_example,Best AUDJPY minor example in this block: 0-1-2 launches from basing area, wave 3 breaks trend cleanly and 4 is shallow. EMAs and HTF support the bullish reading.,usable_soft_rule
5,impulse_forex_audjpy_h1_intermediate_impulse_009,visually_defensible,80,useful,useful_for_wave_role,useful,bullish expansion with sustained positive EWO,intermediate scale may overmerge minor swings,no,low,keep_as_good_example,Same rally works at intermediate scale, with a reasonable 1-2 base and strong continuation to 5. EWO is positive through the advance, though the strongest oscillator reading arrives late.,usable_soft_rule
6,impulse_metals_xauusd_h1_intermediate_impulse_013,plausible_but_needs_review,61,useful,useful_for_wave_role,conflict_explains_case,bearish impulse after failed rebound,wave 4 to 5 spans too much later chop,yes,medium,inspect_manually_before_phase_2_5,Bearish direction is supported by EMAs and later price action, but the fifth is selected far after the first decline and feels stitched across congestion. Useful as a counter-HTF case, not a clean template.,promising_but_needs_review
7,impulse_index_aus200_h1_intermediate_impulse_004,plausible_but_needs_review,72,useful,useful_for_wave_role,conflict_explains_case,bearish third-wave selloff,0-1-2 placement is visually awkward,yes,medium,possible_rule_candidate,The major drop into wave 3 is convincing and EWO goes deeply negative, but the first two waves are cramped around the top. Keep for review as a bearish correction against bullish HTF.,promising_but_needs_review
8,impulse_forex_eurjpy_m30_intermediate_impulse_005,plausible_but_needs_review,76,useful,useful_for_wave_role,useful,bearish wave 3 momentum trough,wave 5 is delayed after a broad corrective stretch,yes,medium,possible_rule_candidate,Bearish count is mostly natural: wave 3 is the momentum break below EMAs and 4 is a clear rebound. The fifth low is distant and lower-momentum, which is plausible Elliott behavior but needs manual acceptance.,usable_soft_rule
9,impulse_metals_xagusd_h1_major_impulse_009,plausible_but_needs_review,74,useful,useful_for_wave_role,useful,bearish continuation with negative EWO after wave 2,wave 3 and 5 are visually separated by noisy consolidation,yes,medium,possible_rule_candidate,Large bearish structure is coherent and aligned with EMA/HTF context. It is less clean than AUS200 because the middle segment contains overlapping chop before the final low.,promising_but_needs_review
10,impulse_index_aus200_h1_major_impulse_002,visually_defensible,80,useful,useful_for_wave_role,conflict_explains_case,bearish impulse with deep negative EWO,HTF conflict means it should be labelled countertrend,yes,medium,possible_rule_candidate,Good bearish five-wave candidate: sharp wave 3 visible wave 4 rebound and lower wave 5. The oscillator supports bearish momentum but HTF bullish context should prevent treating it as a clean aligned setup.,usable_soft_rule
11,impulse_index_aus200_h1_major_impulse_010,ambiguous,58,partially_useful,useful_for_momentum_only,useful,bearish lower-high sequence inside congestion,too small and choppy for major impulse status,yes,high,inspect_manually_before_phase_2_5,This looks more like a late corrective subdivision after the main drop than a standalone major impulse. EMAs are bearish but the waves are compressed and overlapping.,too_noisy
12,impulse_index_hk50_m30_major_impulse_003,plausible_but_needs_review,64,partially_useful,useful_for_wave_role,useful,bearish correction after EWO positive climax,bearish count starts immediately after strong bullish thrust,yes,medium,inspect_manually_before_phase_2_5,The 0-5 decline is readable but it follows a powerful bullish move and looks more corrective than impulsive. EWO helps identify momentum rollover not a rule-grade bearish impulse by itself.,promising_but_needs_review
13,partial_123_forex_audjpy_h1_intermediate_partial123_009,visually_defensible,84,useful,useful_for_wave_role,useful,bullish 1-2-3 launch with rising EWO,no major issue,no,low,keep_as_good_example,Clean bullish partial: 0-1-2 forms a base near EMAs and 3 starts the breakout leg. EWO turns positive and keeps expanding after the 2 low.,usable_soft_rule
14,partial_123_metals_xagusd_h1_intermediate_partial123_003,visually_defensible,87,useful,useful_for_wave_role,conflict_explains_case,bearish 1-2-3 crash with strong EWO confirmation,HTF conflict but visually strong,yes,medium,possible_rule_candidate,Very strong bearish partial: 0 top 1 selloff 2 rebound 3 capitulation low. EWO supports the role clearly; use as a counter-HTF but visually high-quality example.,usable_soft_rule
15,partial_123_index_aus200_h1_intermediate_partial123_001,visually_forced,46,partially_useful,useful_for_momentum_only,useful,small bullish push near prior high,partial 1-2-3 is tiny and precedes a large bearish reversal,yes,high,use_as_negative_example,Bullish partial is too local and shallow relative to the surrounding structure. EMAs and HTF are bullish but the subsequent collapse makes the visual candidate weak for rule discovery.,too_noisy
16,partial_123_forex_audjpy_h1_intermediate_partial123_011,visually_defensible,83,useful,useful_for_wave_role,useful,bullish partial with extended wave 3,third leg may be overextended but direction is clear,no,low,keep_as_good_example,Good bullish partial where 3 captures the breakout to the rally high. EMA alignment and EWO expansion make the context genuinely useful.,usable_soft_rule
17,partial_123_forex_audjpy_h1_minor_partial123_007,ambiguous,57,not_useful,useful_for_momentum_only,conflict_suspicious,bullish rebound inside choppy correction,EMA label conflicts with actual flat-to-bearish local structure,yes,high,inspect_manually_before_phase_2_5,The 0-1-2-3 shape exists but it is embedded in messy post-drop consolidation and the EMA context is not convincing. EWO confirms a bounce more than a robust wave role.,too_noisy
18,partial_123_metals_xagusd_h1_minor_partial123_002,plausible_but_needs_review,62,partially_useful,useful_for_wave_role,useful,bullish 1-2-3 into blowoff high,wave 3 is too large relative to tiny 1-2 base,yes,medium,inspect_manually_before_phase_2_5,Bullish direction and EWO support are real but the count stretches a small early 1-2 into a very large third wave ending at the prior major peak. Useful for review risky as automatic rule evidence.,promising_but_needs_review
19,partial_123_index_aus200_h1_minor_partial123_001,plausible_but_needs_review,55,partially_useful,useful_for_momentum_only,conflict_suspicious,late_minor_bullish_exhaustion_before_bearish_reversal,wave 3 is only marginally above wave 1 and candidate sits at local top before strong selloff,yes,medium,inspect_manually_before_phase_2_5,Small bullish 1-2-3 is visible above both EMAs but candles immediately roll into a much larger bearish leg; useful as exhaustion case more than clean continuation.,too_noisy
20,partial_123_forex_audjpy_h1_minor_partial123_013,visually_defensible,82,useful,useful_for_wave_role,useful,bullish_momentum_expansion_after_base,minor 1 is small but structure resolves cleanly into higher high,no,low,keep_as_good_example,Clear basing near flat EMAs shallow 2 then decisive 3 into the later AUDJPY rally; EMA 50/150 and HTF both help explain the continuation.,usable_soft_rule
21,partial_123_forex_audjpy_h1_major_partial123_007,visually_defensible,78,useful,useful_for_wave_role,useful,major_bullish_impulse_leg,wave 0-1 segment is small relative to very extended 2-3 leg,no,low,keep_as_good_example,Major 1-2-3 captures the real bullish expansion from range to trend; EWO turns and expands with the move although the first leg is visually modest.,usable_soft_rule
22,partial_123_metals_xagusd_h1_major_partial123_006,plausible_but_needs_review,70,partially_useful,useful_for_wave_role,partially_useful,bullish_recovery_inside_choppy_broader_downtrend,candidate is counter to nearby EMA bearish pressure and later fails into new lows,yes,medium,keep_as_ambiguous_example,The 0-1-2-3 swing is readable and EWO improves into 3 but price is still under/around bearish EMA context and the post-3 action weakens the bullish interpretation.,promising_but_needs_review
23,partial_123_index_aus200_h1_major_partial123_002,visually_defensible,76,useful,useful_for_wave_role,conflict_explains_case,bearish_impulse_start_against_bullish_htf,HTF bullish conflict means this is better as reversal/countertrend example than normal aligned impulse,yes,medium,possible_rule_candidate,Bearish 0-1-2-3 is visually strong: lower high at 2 sharp break into 3 EMA rollover begins; conflict label is real and explains risk.,promising_but_needs_review
24,partial_123_forex_eurusd_h1_major_partial123_002,visually_defensible,84,useful,useful_for_wave_role,useful,bearish_impulse_continuation,none material; candidate is one of the cleaner bearish partials,no,low,keep_as_good_example,Clean bearish sequence below falling EMA 50/150: 0 high 1 drop 2 lower high 3 lower low; EWO negative/weak around the sell leg supports the role.,usable_soft_rule
25,abc_forex_audjpy_h1_abc_009,visually_forced,38,misleading,useful_for_momentum_only,unclear,bullish_impulse_mislabeled_as_abc_cluster,ABC labels overlap several impulse subwaves and do not isolate a correction,yes,high,use_as_negative_example,Purple paths jump across multiple nested swings; the dominant visible story is bullish impulse and continuation not a clean corrective ABC.,not_supported
26,abc_metals_xagusd_h1_abc_003,visually_forced,30,partially_useful,useful_for_momentum_only,conflict_suspicious,large_selloff_and_rebound_chop_not_clean_abc,too many overlapping ABC alternatives around a crash leg; labels mix correction and impulse,yes,high,use_as_negative_example,The central XAGUSD drop is impulsive-looking while the ABC overlays cross several degrees and make the correction role unclear.,not_supported
27,abc_index_aus200_h1_abc_004,ambiguous,46,partially_useful,useful_for_momentum_only,conflict_explains_case,bearish_impulse_with_possible_internal_corrections,candidate ABCs are crowded and partially duplicate the bearish impulse,yes,high,inspect_manually_before_phase_2_5,There is a real bearish move after the top but the ABC labels sit on both the topping chop and the decline so correction versus impulse is blurred.,too_noisy
28,abc_forex_audjpy_h1_abc_011,visually_forced,35,misleading,useful_for_momentum_only,unclear,bullish_breakout_impulse_not_correction,C is placed at the strongest breakout high making ABC resemble an impulse leg,yes,high,use_as_negative_example,The price action from B to C is the main bullish thrust; treating it as corrective C is visually weak despite aligned EMA context.,not_supported
29,abc_forex_audjpy_h1_abc_007,visually_forced,32,misleading,useful_for_momentum_only,conflict_suspicious,range_noise_before_bullish_impulse,minor ABC labels are stacked inside sideways chop and then attach to later impulse,yes,high,use_as_negative_example,Multiple A/B/C marks cluster around AUDJPY range noise; the later C at the major high reads as impulse completion rather than correction.,not_supported
30,abc_metals_xagusd_h1_abc_002,visually_forced,28,misleading,useful_for_momentum_only,unclear,bearish_impulse_cascade_mislabeled_as_abc,ABC labels span too many degrees and confuse crash leg with correction,yes,high,use_as_negative_example,The huge drop from the XAGUSD high dominates the chart; purple paths are tangled and do not define a defensible minor bullish correction.,not_supported
31,abc_index_aus200_h1_abc_006,ambiguous,42,partially_useful,useful_for_momentum_only,conflict_explains_case,bearish_leg_with_nested_corrective_noise,ABC paths overlap the same bearish impulse and several sub-swings,yes,high,inspect_manually_before_phase_2_5,Some downtrend corrections are visible but labels are dense and the final C reaches the major selloff low making the structure too broad for clean ABC use.,too_noisy
32,abc_forex_audjpy_h1_abc_013,visually_forced,34,misleading,useful_for_momentum_only,unclear,bullish_impulse_continuation_mislabeled_as_correction,candidate turns the main breakout into C rather than separating correction from impulse,yes,high,use_as_negative_example,AUDJPY trend context is bullish but the ABC overlay treats trend expansion as corrective; visually poor for ABC rule extraction.,not_supported
33,abc_metals_xagusd_h1_abc_006,visually_forced,31,partially_useful,useful_for_momentum_only,unclear,mixed_rebound_and_selloff_structure_without_clean_abc,labels crisscross major swings and include both rebound and decline legs,yes,high,use_as_negative_example,XAGUSD has usable swings but the marked ABC candidates are tangled across degrees; EWO shows momentum phases not a stable corrective signature.,not_supported
34,abc_index_aus200_h1_abc_002,plausible_but_needs_review,58,partially_useful,useful_for_wave_role,conflict_explains_case,bearish_reversal_leg_after_top,top-side ABC is compressed and could be a bearish 1-2-3 instead,yes,medium,inspect_manually_before_phase_2_5,This is cleaner than most ABCs: a top small retrace and sharp C/down leg are visible; still it may be better classified as bearish impulse start.,promising_but_needs_review
35,abc_forex_eurusd_h1_abc_002,ambiguous,50,useful,useful_for_momentum_only,useful,bearish_continuation_with_internal_corrections,several ABC labels ride the dominant downtrend rather than one clear correction,yes,medium,keep_as_ambiguous_example,EURUSD bearish EMA context is excellent but the purple structures blend continuation legs and pullbacks; useful ambiguous case not clean ABC exemplar.,too_noisy
36,abc_forex_gbpusd_h1_abc_003,ambiguous,44,partially_useful,useful_for_momentum_only,conflict_suspicious,bearish_drift_with_corrective_bounces,score and HTF conflict are weak; labels are crowded inside declining channel,yes,high,do_not_use_for_rules,GBPUSD has bearish pressure below EMAs but the ABC markings are overloaded and do not separate the correction from the broader decline cleanly.,not_supported
37,near_miss_forex_audjpy_h1_intermediate_impulse_011,visually_defensible,8,useful,useful_for_wave_role,useful,EWO peak supports wave 3; negative trough marks wave 4; renewed positive supports weak wave 5,wave 5 is modest after a very deep wave 4 but structure is readable,no,low,possible_rule_candidate,Clean AUDJPY bullish sequence: strong 0-3 advance above rising EMAs deep 4 into EMA area then recovery to 5.,usable_soft_rule
38,near_miss_metals_xagusd_h1_intermediate_impulse_003,plausible_but_needs_review,6,partially_useful,useful_for_wave_role,conflict_explains_case,EWO flips sharply negative into wave 3 and weakens on corrective bounces,bearish count fights bullish HTF and begins after a spike; useful as correction-against-HTF case,yes,medium,keep_as_ambiguous_example,Bearish impulse is visually plausible from the spike high but the initial pivoting is violent and HTF conflict matters.,promising_but_needs_review
39,near_miss_index_aus200_h1_intermediate_impulse_008,ambiguous,5,partially_useful,useful_for_wave_role,useful,large negative EWO trough fits wave 3 but wave 5 lacks bearish momentum,wave 5 is truncated or not a true fifth; rebound into 4 is too dominant,yes,high,inspect_manually_before_phase_2_5,AUS200 bearish context is real but the orange count ends with a higher low after a large rebound.,promising_but_needs_review
40,near_miss_forex_audjpy_h1_minor_impulse_007,visually_forced,4,misleading,unclear,conflict_suspicious,EWO is mixed around a choppy corrective basin not a clean bullish impulse signature,minor bullish count is embedded in sideways/down chop while EMAs do not support clean upside,yes,high,do_not_use_for_rules,The five labels overfit local swings before the real later bullish expansion; context says transition not impulse.,too_noisy
41,near_miss_metals_xagusd_h1_minor_impulse_002,visually_forced,4,partially_useful,useful_for_momentum_only,partially_useful,positive EWO confirms early rally strength but not a coherent five-wave completion,wave 5 is a lower high after a collapse; the count resembles a failed rebound,yes,high,use_as_negative_example,The huge 2-3 leg is visually obvious but the post-3 collapse makes the 4-5 section poor for a bullish impulse.,too_noisy
42,near_miss_index_aus200_h1_minor_impulse_012,ambiguous,5,partially_useful,useful_for_wave_role,useful,negative EWO supports the main selloff into wave 3 but wave 5 has little downside confirmation,fifth wave is truncated and occurs during rebound stabilization,yes,medium,keep_as_ambiguous_example,Bearish setting is valid yet the selected minor pivots make the final leg look like a failed continuation.,promising_but_needs_review
43,near_miss_forex_audjpy_h1_major_impulse_007,plausible_but_needs_review,7,useful,useful_for_wave_role,useful,EWO maximum aligns with wave 3 and positive recovery supports wave 5 attempt,major wave 5 is below wave 3 so completion is visually truncated,yes,medium,possible_rule_candidate,Good large bullish context after basing but the 0-1-2 setup is broad and wave 5 does not exceed wave 3.,promising_but_needs_review
44,near_miss_metals_xagusd_h1_major_impulse_006,ambiguous,5,partially_useful,useful_for_momentum_only,partially_useful,EWO supports the rally into wave 3 but not the weak lower-high wave 5,looks more like corrective recovery inside a broader XAGUSD decline,yes,high,keep_as_ambiguous_example,The count captures a tradable upswing but EMAs and later selloff make it weak as a bullish impulse template.,too_noisy
45,near_miss_index_aus200_h1_major_impulse_006,likely_false_candidate,4,partially_useful,useful_for_wave_role,useful,negative EWO confirms wave 3 selloff but rejects the final bearish continuation,wave 5 is a higher low and the structure reverses before confirming continuation,yes,high,use_as_negative_example,Bearish trend context is strong but this candidate is visually a failed fifth rather than a clean impulse.,not_supported
46,hard_invalid_forex_audjpy_h1_intermediate_impulse_001,hard_invalid_correct,8,partially_useful,useful_for_wave_role,conflict_suspicious,EWO supports the wave 3 high but cannot rescue wave 4 breaking the impulse geometry,wave 4 drops below wave 2 area in bullish labeling; invalidation is visually clear,no,low,use_as_negative_example,Strong negative example: attractive bullish peaks exist but the internal overlap makes the count invalid.,usable_soft_rule
47,hard_invalid_metals_xagusd_h1_intermediate_impulse_001,hard_invalid_correct,8,useful,useful_for_wave_role,conflict_explains_case,EWO is positive into the invalid wave 2 spike then strongly negative into the selloff,for bearish count wave 2 exceeds the wave 0 origin; hard invalid is clean,no,low,use_as_negative_example,Excellent hard-invalid bearish example: the apparent selloff is real but the rebound high breaks the starting level.,usable_soft_rule
48,hard_invalid_index_aus200_h1_intermediate_impulse_001,hard_invalid_correct,7,partially_useful,useful_for_momentum_only,partially_useful,EWO fades before the labeled late highs and turns negative into the breakdown,bullish count sits on topping distribution; wave 4 overlap and weak 5 make invalidation credible,no,medium,use_as_negative_example,AUS200 labels mark a topping range above EMAs; the later selloff confirms this is not a defensible bullish impulse.,promising_but_needs_review
49,hard_invalid_forex_audjpy_h1_minor_impulse_001,hard_invalid_correct,7,partially_useful,unclear,useful,EWO is not granular enough for the tiny 0-3 swings but later strength supports only the broad move,minor pivots are too tight; wave 4 breaks the prior corrective base,yes,medium,use_as_negative_example,Useful negative at minor scale though the first four labels are noisy and visually compressed.,too_noisy
50,hard_invalid_metals_xagusd_h1_minor_impulse_001,visually_forced,6,partially_useful,useful_for_momentum_only,conflict_explains_case,EWO confirms directional volatility but not a stable minor five-wave bearish structure,labels mix a bullish spike and bearish collapse; wave 4/5 placement is forced,yes,high,inspect_manually_before_phase_2_5,Hard invalid label is reasonable but as a rule example it is messy because pivots span opposite regimes.,too_noisy
51,hard_invalid_index_aus200_h1_minor_impulse_001,hard_invalid_correct,7,partially_useful,useful_for_momentum_only,partially_useful,EWO loses upside support before the labeled final high and turns negative afterward,minor bullish count fails structurally before a major selloff,no,medium,use_as_negative_example,Good invalid example for bullish counts in topping conditions; EMAs still look supportive but momentum disagrees.,promising_but_needs_review
52,hard_invalid_forex_audjpy_h1_major_impulse_001,hard_invalid_correct,8,partially_useful,useful_for_wave_role,conflict_suspicious,EWO identifies the real wave 3 strength and later recovery but wave 4 geometry invalidates the count,major bullish count has wave 4 below wave 2 and wave 5 below wave 3,no,low,use_as_negative_example,Clear hard invalid: visually tempting bullish structure yet the deep fourth wave breaks the Elliott constraint.,usable_soft_rule
53,hard_invalid_metals_xagusd_h1_major_impulse_001,hard_invalid_correct,8,useful,useful_for_wave_role,conflict_explains_case,EWO positive into invalid wave 2 and deeply negative into wave 3 supports using momentum as context,bearish wave 2 exceeds wave 0; invalidation is clean despite later bearish follow-through,no,low,use_as_negative_example,Strong negative example: the bearish move after wave 2 is real but the count must be rejected structurally.,usable_soft_rule
54,hard_invalid_index_aus200_h1_major_impulse_001,hard_invalid_correct,7,partially_useful,useful_for_momentum_only,conflict_suspicious,EWO gives weak support to the early bullish phase and then deteriorates before breakdown,bullish wave 3 fails to exceed wave 1 and the count occurs inside topping context,yes,medium,use_as_negative_example,Useful hard invalid for major scale: the selected highs form distribution rather than a valid bullish impulse.,promising_but_needs_review
"""


SOFT_RULE_ROWS = [
    {
        "rule_id": "SR1",
        "rule_candidate": "HTF/LTF aligned with EMA 50/150 plus EWO expansion can support impulse search.",
        "status": "usable_soft_rule",
        "supporting_cases": "1,4,5,13,16,20,21,24,37",
        "do_not_make_hard_because": "Some valid-looking cases have late EWO peaks or counter-HTF context.",
    },
    {
        "rule_id": "SR2",
        "rule_candidate": "EWO expansion after wave 2 is useful for detecting wave 3 in partial 1-2-3 candidates.",
        "status": "usable_soft_rule",
        "supporting_cases": "13,14,16,20,21,23,24",
        "do_not_make_hard_because": "EWO can lag or remain useful only as momentum context.",
    },
    {
        "rule_id": "SR3",
        "rule_candidate": "EWO peak or trough in the central leg can support wave 3 identification.",
        "status": "usable_soft_rule",
        "supporting_cases": "3,7,8,10,37,38,39,47,53",
        "do_not_make_hard_because": "Several impulses have the strongest reading late or in wave 5.",
    },
    {
        "rule_id": "SR4",
        "rule_candidate": "EWO loss/divergence in the last leg is promising for wave 5 or failed fifth detection.",
        "status": "promising_but_needs_review",
        "supporting_cases": "37,39,42,43,45,48,51,54",
        "do_not_make_hard_because": "The visual meaning depends on whether the fifth is valid, truncated or false.",
    },
    {
        "rule_id": "SR5",
        "rule_candidate": "HTF conflict should increase ambiguity or mark countertrend/reversal context, not automatically reject the count.",
        "status": "usable_soft_rule",
        "supporting_cases": "3,10,14,23,38,46,52",
        "do_not_make_hard_because": "Several conflict/correction cases are visually defensible and useful.",
    },
    {
        "rule_id": "SR6",
        "rule_candidate": "Price inside or around EMA band should raise ambiguity instead of invalidating a count.",
        "status": "promising_but_needs_review",
        "supporting_cases": "1,13,17,20,37,43",
        "do_not_make_hard_because": "Band behavior differs between bases, pullbacks and chop.",
    },
    {
        "rule_id": "SR7",
        "rule_candidate": "Current ABC selection should not guide Phase 2.5 rules until the ABC search is redesigned.",
        "status": "usable_soft_rule",
        "supporting_cases": "25,26,28,29,30,32,33,36",
        "do_not_make_hard_because": "Most ABC charts look forced or tangled across degrees.",
    },
    {
        "rule_id": "SR8",
        "rule_candidate": "Hard Elliott invalidations remain structural; EWO/EMA context cannot rescue them.",
        "status": "usable_soft_rule",
        "supporting_cases": "46,47,48,49,51,52,53,54",
        "do_not_make_hard_because": "This is already a hard structural rule; context only explains why a tempting count still fails.",
    },
]


def _normalise_score(raw_score: Any) -> int:
    value = float(raw_score)
    if value > 10:
        if value <= 20:
            return 1
        if value <= 40:
            return 2
        if value <= 60:
            return 3
        if value <= 80:
            return 4
        return 5
    if value <= 2:
        return 1
    if value <= 4:
        return 2
    if value <= 6:
        return 3
    if value <= 8:
        return 4
    return 5


def _read_reviews() -> pd.DataFrame:
    header, *rows = RAW_VISUAL_REVIEWS.strip().splitlines()
    columns = header.split(",")
    parsed_rows: list[list[str]] = []
    for line_no, row in enumerate(rows, start=2):
        body, ewo_rule_assessment = row.rsplit(",", 1)
        parts = body.split(",", 12)
        if len(parts) != 13:
            raise RuntimeError(f"Invalid embedded visual review row at line {line_no}: {row}")
        parsed_rows.append([*parts, ewo_rule_assessment])
    reviews = pd.DataFrame(parsed_rows, columns=columns)
    reviews["candidate_order"] = pd.to_numeric(reviews["candidate_order"], errors="raise").astype(int)
    reviews["visual_quality_raw"] = pd.to_numeric(reviews["visual_quality_raw"], errors="raise")
    reviews["visual_quality_score"] = reviews["visual_quality_raw"].apply(_normalise_score)
    return reviews


def _load_candidates(input_dir: Path) -> pd.DataFrame:
    candidates = pd.read_csv(input_dir / "tables" / "candidate_context.csv")
    candidates["candidate_order"] = pd.to_numeric(candidates["candidate_order"], errors="raise").astype(int)
    candidates = candidates.rename(columns={"context_chart_path": "chart_path"})
    return candidates


def _review_triggers(row: pd.Series) -> str:
    triggers: list[str] = []
    if row["trend_context_label"] == "conflict_with_htf":
        triggers.append("conflict_with_htf")
    if int(row["visual_quality_score"]) <= 2:
        triggers.append("low_visual_quality")
    if row["trend_context_label"] in {"conflict_with_htf", "correction_against_htf"} and row["visual_review_status"] in {
        "visually_defensible",
        "plausible_but_needs_review",
    }:
        triggers.append("context_contradiction_but_visual_good")
    if "mislabeled" in str(row["inferred_wave_role_from_ewo"]) or "mislabeled" in str(row["likely_problem_if_any"]):
        triggers.append("ewo_or_visual_role_mismatch")
    if int(row["candidate_order"]) in {4, 13, 24}:
        triggers.append("top_positive_methodology_example")
    return "|".join(triggers)


def _final_should_review(row: pd.Series) -> str:
    if _review_triggers(row):
        return "yes"
    if row["should_user_review_raw"] == "yes":
        return "yes"
    return "no"


def _final_priority(row: pd.Series) -> str:
    triggers = _review_triggers(row)
    if "low_visual_quality" in triggers or row["user_review_priority_raw"] == "high":
        return "high"
    if triggers or row["user_review_priority_raw"] == "medium":
        return "medium"
    return "low"


def build_visual_case_reviews(input_dir: Path) -> pd.DataFrame:
    candidates = _load_candidates(input_dir)
    reviews = _read_reviews()
    merged = candidates.merge(
        reviews,
        on=["candidate_order", "candidate_id"],
        how="left",
        validate="one_to_one",
    )
    if merged["visual_review_status"].isna().any():
        missing = merged[merged["visual_review_status"].isna()]["candidate_id"].tolist()
        raise RuntimeError(f"Missing visual reviews for candidates: {missing}")
    merged["review_trigger"] = merged.apply(_review_triggers, axis=1)
    merged["should_user_review"] = merged.apply(_final_should_review, axis=1)
    merged["user_review_priority"] = merged.apply(_final_priority, axis=1)
    columns = [
        "candidate_id",
        "chart_path",
        "review_category",
        "symbol",
        "timeframe",
        "swing_degree",
        "direction",
        "trend_context_label",
        "context_score",
        "visual_review_status",
        "visual_quality_score",
        "visual_quality_raw",
        "ema_context_usefulness",
        "ewo_context_usefulness",
        "htf_ltf_context_usefulness",
        "inferred_wave_role_from_ewo",
        "likely_problem_if_any",
        "should_user_review",
        "user_review_priority",
        "suggested_action",
        "visual_notes",
        "ewo_rule_assessment",
        "review_trigger",
        "candidate_order",
    ]
    return merged[[column for column in columns if column in merged.columns]].sort_values("candidate_order")


def build_ewo_wave_role_review(visual_reviews: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "candidate_order",
        "candidate_id",
        "review_category",
        "symbol",
        "timeframe",
        "swing_degree",
        "direction",
        "inferred_wave_role_from_ewo",
        "ewo_context_usefulness",
        "ewo_rule_assessment",
        "visual_quality_score",
        "visual_notes",
    ]
    return visual_reviews[columns].copy()


def build_user_must_review(visual_reviews: pd.DataFrame) -> pd.DataFrame:
    subset = visual_reviews[visual_reviews["review_trigger"].astype(str).ne("")].copy()
    subset = subset.sort_values(["user_review_priority", "candidate_order"], ascending=[True, True])
    priority_order = {"high": 0, "medium": 1, "low": 2}
    subset["_priority_order"] = subset["user_review_priority"].map(priority_order).fillna(9)
    subset = subset.sort_values(["_priority_order", "candidate_order"]).drop(columns=["_priority_order"])
    return subset


def build_summary(visual_reviews: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {"metric": "visual_cases_reviewed", "value": int(len(visual_reviews))},
        {"metric": "unique_candidates", "value": int(visual_reviews["candidate_id"].nunique())},
        {"metric": "conflict_with_htf_cases", "value": int((visual_reviews["trend_context_label"] == "conflict_with_htf").sum())},
        {"metric": "user_must_review_cases", "value": int((visual_reviews["review_trigger"].astype(str) != "").sum())},
        {"metric": "mean_visual_quality_score_1_5", "value": round(float(visual_reviews["visual_quality_score"].mean()), 4)},
    ]
    for column in [
        "visual_review_status",
        "ema_context_usefulness",
        "ewo_context_usefulness",
        "htf_ltf_context_usefulness",
        "ewo_rule_assessment",
        "review_category",
    ]:
        for key, value in visual_reviews[column].value_counts().items():
            rows.append({"metric": f"{column}_{key}", "value": int(value)})
    return pd.DataFrame(rows)


def write_report(output_dir: Path, visual_reviews: pd.DataFrame, summary: pd.DataFrame) -> None:
    status_counts = visual_reviews["visual_review_status"].value_counts().to_dict()
    category_quality = visual_reviews.groupby("review_category")["visual_quality_score"].mean().round(2).to_dict()
    ewo_counts = visual_reviews["ewo_rule_assessment"].value_counts().to_dict()
    must_review_count = int((visual_reviews["review_trigger"].astype(str) != "").sum())
    lines = [
        "# WaveCount Phase 2.4.1 - visual audit context",
        "",
        "Fecha: 2026-05-19",
        "",
        "## Resumen",
        "",
        "Se revisaron visualmente los 54 graficos vigentes referenciados por `candidate_context.csv` / `run_meta.json`.",
        "No se cambiaron reglas de conteo, no se generaron senales y no se avanzo a Fase 2.5.",
        "",
        "## Resultados",
        "",
        f"- casos revisados: {len(visual_reviews)}",
        f"- distribucion visual: {status_counts}",
        f"- calidad media por categoria: {category_quality}",
        f"- evaluacion EWO: {ewo_counts}",
        f"- casos para revision obligatoria del usuario: {must_review_count}",
        "",
        "## Lectura metodologica",
        "",
        "- Los impulsos y parciales 1-2-3 tienen varios ejemplos visualmente defendibles.",
        "- El EWO 5-35 parece util para inferir onda 3, descarga de onda 4 y posibles quintas debiles o fallidas.",
        "- Los ABC actuales son la parte mas debil: muchos graficos parecen impulsos o subondas etiquetadas como correcciones.",
        "- Las invalidaciones duras son buenos ejemplos negativos: el contexto puede explicar, pero no rescatar, un conteo estructuralmente invalido.",
        "",
        "## Decision",
        "",
        "EMAs/HTF/EWO son aptos como reglas blandas para una futura Fase 2.5, pero no como reglas duras.",
        "Antes de implementar busqueda guiada conviene revisar `user_must_review.csv`, especialmente los conflictos HTF y los ABC forzados.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_4_1_VISUAL_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_visual_audit(input_dir: Path = DEFAULT_INPUT_DIR, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    visual_reviews = build_visual_case_reviews(input_dir)
    conflict_reviews = visual_reviews[visual_reviews["trend_context_label"] == "conflict_with_htf"].copy()
    ewo_review = build_ewo_wave_role_review(visual_reviews)
    soft_rules = pd.DataFrame(SOFT_RULE_ROWS)
    user_must_review = build_user_must_review(visual_reviews)
    summary = build_summary(visual_reviews)

    visual_reviews.to_csv(tables_dir / "visual_case_reviews.csv", index=False)
    ewo_review.to_csv(tables_dir / "ewo_wave_role_review.csv", index=False)
    conflict_reviews.to_csv(tables_dir / "conflict_cases_review.csv", index=False)
    user_must_review.to_csv(tables_dir / "user_must_review.csv", index=False)
    soft_rules.to_csv(tables_dir / "phase2_5_soft_rule_candidates.csv", index=False)
    summary.to_csv(tables_dir / "context_visual_audit_summary.csv", index=False)
    write_report(output_dir, visual_reviews, summary)

    elapsed_seconds = perf_counter() - start
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed_seconds,
        "input_dir": str(input_dir),
        "reviewed_cases": int(len(visual_reviews)),
        "conflict_cases": int(len(conflict_reviews)),
        "user_must_review_cases": int(len(user_must_review)),
        "outputs": {
            "visual_case_reviews": "tables/visual_case_reviews.csv",
            "ewo_wave_role_review": "tables/ewo_wave_role_review.csv",
            "conflict_cases_review": "tables/conflict_cases_review.csv",
            "user_must_review": "tables/user_must_review.csv",
            "phase2_5_soft_rule_candidates": "tables/phase2_5_soft_rule_candidates.csv",
            "context_visual_audit_summary": "tables/context_visual_audit_summary.csv",
            "report": "WAVECOUNT_PHASE2_4_1_VISUAL_AUDIT.md",
        },
        "notes": [
            "The 54 current charts were visually reviewed in three independent blocks.",
            "Scores were normalised to 1-5 because reviewers used mixed raw scales.",
            "No counting rules, strategies, backtests, MT5, signals, dashboard or Telegram integration were changed.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.4.1 visual audit artifacts.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_visual_audit(input_dir=args.input_dir, output_dir=args.output_dir)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
