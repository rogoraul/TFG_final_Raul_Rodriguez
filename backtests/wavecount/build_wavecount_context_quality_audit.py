from __future__ import annotations

import argparse
import json
import shutil
import textwrap
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_H4_CONTEXT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_context_2026-05-18" / "h4_d1"
DEFAULT_AUX_CONTEXT_DIR = REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_context_2026-05-18" / "h1_m30"
DEFAULT_PHASE23_CLOSURE_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_4_h4_d1_visual_closure_2026-05-23"
)
DEFAULT_PREVIOUS_H4_AUDIT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_3_2_4_h4_d1_visual_audit_2026-05-20"
)
DEFAULT_AUX_VISUAL_AUDIT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_1_context_visual_audit_2026-05-19"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT / "artifacts" / "wavecount" / "phase2_4_2_context_quality_audit_2026-05-23"
)

H4_CONTEXT_REVIEW_OVERRIDES: dict[int, dict[str, str]] = {
    1: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "D1/EMAs/EWO acompanan, pero 2.3.4 lo dejo como micro/ambiguo. No debe subir a ejemplo bueno solo por contexto.",
    },
    2: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "Contexto alcista y EWO positivo, pero el conteo es minor/local. Sirve como subestructura, no regla principal.",
    },
    3: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "ema_transition_support",
        "context_notes_integrated": "EMAs ayudan a ver transicion y EWO acompana el tramo, pero el conteo sigue profundo/dudoso.",
    },
    4: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "EMAs/D1 confirman, pero la estructura es local y luego gira fuerte. El contexto puede dar falsa seguridad.",
    },
    5: {
        "context_review_status": "context_conflicts_but_explains",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_wave_role",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "yes_but_needs_manual_validation",
        "phase25_rule_candidate": "ema_transition_support",
        "context_notes_integrated": "Buen impulso bajista H4 contra D1 alcista. Util para correccion contra HTF; D1 no debe ser filtro duro.",
    },
    6: {
        "context_review_status": "context_confirms_good_count",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_wave_role",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_soft_rule",
        "phase25_rule_candidate": "htf_alignment_soft_filter;ewo_wave3_momentum_support",
        "context_notes_integrated": "Mejor caso: conteo limpio, EMAs y D1 alineados, EWO acompana expansion. Buen ejemplo para memoria.",
    },
    7: {
        "context_review_status": "context_misleading",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "useful_for_divergence_or_wave5_loss",
        "htf_usefulness": "partially_useful",
        "quality_filter_candidate": "no_misleading",
        "phase25_rule_candidate": "ewo_wave5_divergence_warning",
        "context_notes_integrated": "EMAs/D1 apoyan, pero no anticipan bien la caida posterior. EWO avisa mejor que las medias. No filtro duro.",
    },
    8: {
        "context_review_status": "context_confirms_good_count",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_wave_role",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_soft_rule",
        "phase25_rule_candidate": "ema_transition_support;ewo_wave3_momentum_support",
        "context_notes_integrated": "Muy buen caso: transicion alcista clara, EWO expansivo, D1 acompana. Candidato fuerte para regla blanda.",
    },
    9: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "H4 bajista y EWO bajista explican el tramo, pero 2.3.4 lo excluyo por forma/grado. No rescatar.",
    },
    10: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_but_needs_manual_validation",
        "phase25_rule_candidate": "ewo_wave3_momentum_support",
        "context_notes_integrated": "Contexto alcista fuerte, pero grafico con spikes y onda 5 debil. Util como ambiguo, no regla limpia.",
    },
    11: {
        "context_review_status": "context_improves_confidence",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_but_needs_manual_validation",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "Contexto acompana un conteo visualmente bueno, aunque el grado parece mas intermediate que major.",
    },
    12: {
        "context_review_status": "context_conflicts_but_explains",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_wave_role",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "ewo_wave3_momentum_support",
        "context_notes_integrated": "Buen tramo bajista local contra D1 alcista. EWO ayuda, pero D1 indica que no es alineacion principal.",
    },
    13: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "neutral",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "no_too_noisy",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Parcial bajista pequeno contra D1 alcista y luego absorbido. EWO confirma bajada local, pero no lo salva.",
    },
    14: {
        "context_review_status": "context_confirms_good_count",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_wave_role",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_soft_rule",
        "phase25_rule_candidate": "htf_alignment_soft_filter;ewo_wave3_momentum_support",
        "context_notes_integrated": "Buen partial 1-2-3: EMAs/D1/EWO apoyan el arranque. Sirve como ejemplo de contexto util.",
    },
    15: {
        "context_review_status": "context_conflicts_suspicious",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_soft_rule",
        "phase25_rule_candidate": "ema_band_ambiguity_penalty",
        "context_notes_integrated": "Contexto bullish/inside band contradice el parcial bearish debil. Aqui el contexto ayuda a descartarlo.",
    },
    16: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_wave_role",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Contexto lo haria parecer bueno, pero 2.3.4 lo excluyo. Caso clave: EMAs/EWO/D1 no deben rescatar por si solos.",
    },
    17: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "neutral",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "no_too_noisy",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Muy parecido al 13 pero mas minor. Sirve como correccion local, no como partial util para metodologia.",
    },
    18: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_wave_role",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_but_needs_manual_validation",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "Visualmente limpio y contexto alcista, pero 2.3.4 lo dejo como ambiguo/minor_substructure. Buen auxiliar, no regla principal.",
    },
    19: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "A favor de regimen, pero minor sigue siendo subestructura. No convertir en regla fuerte.",
    },
    20: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "Contexto acompana, pero el parcial es muy local. Util como ejemplo de subonda.",
    },
    21: {
        "context_review_status": "context_improves_confidence",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_but_needs_manual_validation",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "Major mas defendible; EMAs y D1 ayudan, EWO acompana pero no define por si solo.",
    },
    22: {
        "context_review_status": "context_confirms_good_count",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_wave_role",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_soft_rule",
        "phase25_rule_candidate": "ewo_wave3_momentum_support",
        "context_notes_integrated": "Buen ejemplo: 1-2-3 precede continuacion fuerte; EWO/EMAs ayudan de verdad.",
    },
    23: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "misleading_if_hard_filter",
        "quality_filter_candidate": "no_misleading",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Correctamente excluido: conflicto HTF y estructura debil. El contexto no lo rescata.",
    },
    24: {
        "context_review_status": "context_confirms_good_count",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_soft_rule",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "Buen parcial major; contexto confirma sin forzar. Candidato bueno para regla blanda.",
    },
    25: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "partially_useful",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "ABC legacy/experimental. Puede sugerir correccion, pero no es limpio.",
    },
    26: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "misleading",
        "ewo_usefulness": "misleading",
        "htf_usefulness": "misleading_if_hard_filter",
        "quality_filter_candidate": "no_misleading",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "ABC legacy con maraña/duplicados. Contexto alcista no debe rescatarlo.",
    },
    27: {
        "context_review_status": "context_conflicts_suspicious",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "useful_transition_context",
        "quality_filter_candidate": "no_misleading",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "ABC legacy; conflicto HTF confirma que no debe usarse como ejemplo limpio.",
    },
    28: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "misleading",
        "ewo_usefulness": "misleading",
        "htf_usefulness": "misleading_if_hard_filter",
        "quality_filter_candidate": "no_misleading",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "ABC muy sobrepuesto. Contexto fuerte alcista no arregla la mala geometria.",
    },
    29: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "partially_useful",
        "htf_usefulness": "partially_useful",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Algo mas legible, pero sigue legacy. No usar para reglas.",
    },
    30: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "misleading",
        "ewo_usefulness": "misleading",
        "htf_usefulness": "misleading_if_hard_filter",
        "quality_filter_candidate": "no_misleading",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "ABC legacy saturado; no rescatable.",
    },
    31: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "noisy",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "misleading_if_hard_filter",
        "quality_filter_candidate": "no_misleading",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "ABC en lateralidad/solapes; experimental.",
    },
    32: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "partially_useful",
        "htf_usefulness": "partially_useful",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Contexto posterior bajista ayuda a leer correccion, pero ABC dibujado no es fiable.",
    },
    33: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "partially_useful",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Mejor que otros ABC, pero sigue con duplicidad/legacy. No pasar a reglas.",
    },
    34: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "misleading",
        "ewo_usefulness": "misleading",
        "htf_usefulness": "misleading_if_hard_filter",
        "quality_filter_candidate": "no_misleading",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "ABC legacy demasiado cargado; contexto acompana tendencia, no ABC.",
    },
    35: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "partially_useful",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Puede verse como correccion contra HTF, pero la estructura ABC no queda limpia.",
    },
    36: {
        "context_review_status": "context_explains_ambiguity",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "partially_useful",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Contexto bajista posterior aporta lectura, pero ABC legacy no debe cerrar metodologia.",
    },
    37: {
        "context_review_status": "context_conflicts_but_explains",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "partially_useful",
        "htf_usefulness": "useful_correction_context",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "El conflicto HTF explica por que no debe ser impulso limpio.",
    },
    38: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Muy tentador por tendencia, pero sigue near-miss. No rescatar.",
    },
    39: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Contexto acompana, pero Fase 2.3.4 lo excluyo. Mantener como ambiguo/near-miss.",
    },
    40: {
        "context_review_status": "context_conflicts_suspicious",
        "ema_usefulness": "noisy",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "useful_transition_context",
        "quality_filter_candidate": "no_too_noisy",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Minor demasiado micro y conflicto HTF. Buen negativo.",
    },
    41: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "partially_useful",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Microestructura dentro de tendencia fuerte; no regla.",
    },
    42: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "partially_useful",
        "quality_filter_candidate": "no_too_noisy",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Forzado/micro; el contexto no corrige la forma.",
    },
    43: {
        "context_review_status": "context_improves_confidence",
        "ema_usefulness": "useful_quality_filter",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "yes_but_needs_manual_validation",
        "phase25_rule_candidate": "htf_alignment_soft_filter",
        "context_notes_integrated": "Near-miss major bastante util como caso ambiguo fuerte, no como impulso limpio.",
    },
    44: {
        "context_review_status": "context_misleading",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "useful_for_divergence_or_wave5_loss",
        "htf_usefulness": "partially_useful",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "ewo_wave5_divergence_warning",
        "context_notes_integrated": "EWO avisa perdida/ruptura violenta; no rescatar como impulso.",
    },
    45: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Parece ordenado, pero estaba excluido por discriminacion de grado. No rescatar.",
    },
    46: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Hard invalid correcto; contexto alcista lo hace tentador, pero no invalida la invalidacion.",
    },
    47: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Buen ejemplo negativo: momentum/trend apoyan, pero regla dura manda.",
    },
    48: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Correcto como negativo metodologico.",
    },
    49: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "partially_useful",
        "quality_filter_candidate": "no_too_noisy",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Minor y hard invalid; contexto no aporta calidad suficiente.",
    },
    50: {
        "context_review_status": "context_conflicts_but_explains",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "useful_transition_context",
        "quality_filter_candidate": "no_too_noisy",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Conflicto HTF refuerza que no se use.",
    },
    51: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "partially_useful",
        "ewo_usefulness": "noisy",
        "htf_usefulness": "partially_useful",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Invalidacion correcta; no usar como filtro positivo.",
    },
    52: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Major visualmente atractivo, pero hard invalid sigue siendo hard invalid.",
    },
    53: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Contexto alcista no debe rescatar la invalidacion.",
    },
    54: {
        "context_review_status": "context_should_not_rescue_count",
        "ema_usefulness": "useful_trend_context",
        "ewo_usefulness": "useful_for_momentum_phase",
        "htf_usefulness": "useful_regime_filter",
        "quality_filter_candidate": "no_context_only",
        "phase25_rule_candidate": "do_not_use_as_rule",
        "context_notes_integrated": "Buen negativo: EMAs/EWO acompanan, pero la estructura sigue invalida.",
    },
}


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def _string(value: Any, default: str = "") -> str:
    if pd.isna(value):
        return default
    text = str(value)
    if text.lower() in {"nan", "none"}:
        return default
    return text


def _rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _resolve_chart(base_dir: Path, chart_path: str) -> Path:
    raw = Path(chart_path)
    if raw.is_absolute():
        return raw
    return base_dir / raw


def _copy_with_annotation(source: Path, target: Path, lines: list[str]) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        image = image.convert("RGB")
        width, height = image.size
        font = ImageFont.load_default()
        wrapped: list[str] = []
        for line in lines:
            wrapped.extend(textwrap.wrap(line, width=150) or [""])
        line_height = 15
        pad = 10
        banner_height = pad * 2 + line_height * len(wrapped)
        canvas = Image.new("RGB", (width, height + banner_height), "white")
        canvas.paste(image, (0, banner_height))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, 0, width, banner_height), fill=(248, 250, 252), outline=(203, 213, 225))
        y = pad
        for line in wrapped:
            draw.text((pad, y), line, fill=(15, 23, 42), font=font)
            y += line_height
        canvas.save(target)


def _write_image_index(csv_path: Path, title: str, image_columns: list[str]) -> None:
    if not csv_path.exists():
        return
    frame = _read_csv(csv_path)
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("Sin filas.")
    for _, row in frame.iterrows():
        label_bits = [
            _string(row.get("candidate_order")),
            _string(row.get("candidate_id")),
            _string(row.get("context_review_status")),
            _string(row.get("final_phase23_decision")),
        ]
        label = " | ".join(bit for bit in label_bits if bit)
        lines.append(f"## {label}")
        note = _string(row.get("context_notes")) or _string(row.get("aux_notes")) or _string(row.get("visual_notes"))
        if note:
            lines.append("")
            lines.append(note)
        for column in image_columns:
            path_text = _string(row.get(column))
            if not path_text:
                continue
            path = Path(path_text)
            if not path.is_absolute():
                path = (REPO_ROOT / path).resolve()
            lines.append("")
            lines.append(f"![{label}]({path.as_posix()})")
        lines.append("")
    csv_path.with_suffix(".md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _map_ema(value: str, phase23_decision: str, old_suggested_action: str) -> str:
    value = value.lower()
    if value == "useful":
        return "useful_quality_filter" if phase23_decision == "keep_as_good_example" else "useful_trend_context"
    if value == "partially_useful":
        return "partially_useful"
    if value in {"not_useful", "unclear"}:
        return "neutral"
    if value == "misleading":
        return "misleading"
    if old_suggested_action in {"use_as_negative_example", "do_not_use_for_rules"}:
        return "noisy"
    return "neutral"


def _map_ewo(value: str, context_notes: str) -> str:
    value = value.lower()
    notes = context_notes.lower()
    if value == "useful_for_wave_role":
        if "diverg" in notes or "wave 5" in notes or "quinta" in notes or "trunc" in notes:
            return "useful_for_divergence_or_wave5_loss"
        return "useful_for_wave_role"
    if value == "useful_for_momentum_only":
        return "useful_for_momentum_phase"
    if value in {"partially_useful", "promising_but_needs_review"}:
        return "partially_useful"
    if value in {"unclear", "too_noisy"}:
        return "noisy"
    if value in {"misleading", "not_supported"}:
        return "misleading"
    return "partially_useful"


def _map_htf(value: str, trend_label: str) -> str:
    value = value.lower()
    trend_label = trend_label.lower()
    if value == "useful":
        if trend_label == "correction_against_htf":
            return "useful_correction_context"
        return "useful_regime_filter"
    if value == "partially_useful":
        return "partially_useful"
    if value == "conflict_explains_case":
        return "useful_transition_context"
    if value == "conflict_suspicious":
        return "misleading_if_hard_filter"
    if value == "misleading":
        return "misleading_if_hard_filter"
    return "neutral"


def _context_status(
    phase23_decision: str,
    review_category: str,
    trend_label: str,
    old_change: str,
    old_suggested_action: str,
) -> str:
    if review_category == "abc":
        return "context_should_not_rescue_count"
    if phase23_decision == "exclude_from_phase25_rules":
        if old_suggested_action in {"keep_as_good_example", "possible_rule_candidate"}:
            return "context_should_not_rescue_count"
        return "context_not_useful"
    if phase23_decision == "keep_as_negative_example":
        return "context_should_not_rescue_count"
    if old_change == "misleading_if_used_as_filter":
        return "context_misleading"
    if old_change == "flags_transition":
        return "context_flags_transition"
    if "conflict" in trend_label:
        if old_change in {"reframes_as_correction", "downgrades_confidence"}:
            return "context_conflicts_but_explains"
        return "context_conflicts_suspicious"
    if phase23_decision == "keep_as_good_example":
        return "context_confirms_good_count" if old_change == "confirms" else "context_improves_confidence"
    if phase23_decision == "keep_as_ambiguous_example":
        return "context_explains_ambiguity"
    return "context_not_useful"


def _quality_candidate(context_status: str, phase23_decision: str, ema: str, ewo: str, htf: str) -> str:
    if context_status == "context_should_not_rescue_count":
        return "no_misleading"
    if context_status in {"context_misleading", "context_conflicts_suspicious"}:
        return "no_misleading"
    if phase23_decision == "keep_as_good_example" and (
        ema.startswith("useful") or ewo.startswith("useful") or htf.startswith("useful")
    ):
        return "yes_soft_rule"
    if phase23_decision == "keep_as_ambiguous_example" and context_status == "context_explains_ambiguity":
        return "yes_but_needs_manual_validation"
    if "noisy" in {ema, ewo, htf}:
        return "no_too_noisy"
    return "no_context_only"


def _phase25_rule(context_status: str, ema: str, ewo: str, htf: str, trend_label: str) -> str:
    if context_status in {"context_should_not_rescue_count", "context_misleading", "context_not_useful"}:
        return "do_not_use_as_rule"
    if htf == "useful_regime_filter":
        return "htf_alignment_soft_filter"
    if htf in {"useful_correction_context", "useful_transition_context"}:
        return "ema_transition_support"
    if ema == "useful_quality_filter":
        return "ema_band_ambiguity_penalty" if "unclear" in trend_label else "htf_alignment_soft_filter"
    if ewo == "useful_for_wave_role":
        return "ewo_wave3_momentum_support"
    if ewo == "useful_for_divergence_or_wave5_loss":
        return "ewo_wave5_divergence_warning"
    if ewo == "useful_for_momentum_phase":
        return "ewo_correction_momentum_warning"
    return "do_not_use_as_rule"


def _build_h4_audit(h4_context_dir: Path, phase23_dir: Path, previous_audit_dir: Path, output_dir: Path) -> pd.DataFrame:
    context = _read_csv(h4_context_dir / "tables" / "candidate_context.csv")
    closure = _read_csv(phase23_dir / "tables" / "h4_d1_visual_closure.csv")
    previous = _read_csv(previous_audit_dir / "tables" / "phase2_4_h4_d1_context_audit.csv")

    closure_cols = [
        "candidate_id",
        "manual_visual_status",
        "visual_quality_score",
        "degree_policy",
        "wave5_diagnostic",
        "partial123_diagnostic",
        "final_phase23_decision",
        "final_notes",
        "reviewed_chart_path",
    ]
    closure_join = closure[[column for column in closure_cols if column in closure.columns]].copy()
    previous_cols = [
        "candidate_id",
        "d1_context_usefulness",
        "ema_context_usefulness",
        "ewo_context_usefulness",
        "context_changes_phase23_reading",
        "user_review_priority",
        "suggested_action",
        "context_notes",
    ]
    previous_join = previous[[column for column in previous_cols if column in previous.columns]].copy()
    frame = context.merge(closure_join, on="candidate_id", how="left").merge(previous_join, on="candidate_id", how="left")

    reviewed_rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        phase23_decision = _string(row.get("final_phase23_decision"), "not_found")
        review_category = _string(row.get("review_category"))
        trend_label = _string(row.get("trend_context_label"))
        old_change = _string(row.get("context_changes_phase23_reading"))
        old_action = _string(row.get("suggested_action"))
        old_notes = _string(row.get("context_notes"))
        ema = _map_ema(_string(row.get("ema_context_usefulness")), phase23_decision, old_action)
        ewo = _map_ewo(_string(row.get("ewo_context_usefulness")), old_notes)
        htf = _map_htf(_string(row.get("d1_context_usefulness")), trend_label)
        status = _context_status(phase23_decision, review_category, trend_label, old_change, old_action)
        quality = _quality_candidate(status, phase23_decision, ema, ewo, htf)
        rule = _phase25_rule(status, ema, ewo, htf, trend_label)

        override = H4_CONTEXT_REVIEW_OVERRIDES.get(int(row["candidate_order"]))
        if override:
            status = override["context_review_status"]
            ema = override["ema_usefulness"]
            ewo = override["ewo_usefulness"]
            htf = override["htf_usefulness"]
            quality = override["quality_filter_candidate"]
            rule = override["phase25_rule_candidate"]
            old_notes = override["context_notes_integrated"]

        source_chart = _resolve_chart(h4_context_dir, _string(row.get("context_chart_path")) or _string(row.get("chart_path")))
        folder = "h4_d1_reviewed"
        if status in {"context_should_not_rescue_count", "context_misleading", "context_conflicts_suspicious"}:
            folder = "misleading_context_examples"
        elif quality.startswith("yes") or phase23_decision == "keep_as_good_example":
            folder = "best_context_examples"
        reviewed_chart = output_dir / "charts" / folder / source_chart.name
        annotation_lines = [
            f"2.4.2 | {row['candidate_order']} {row['candidate_id']}",
            f"2.3.4={phase23_decision} | context={status} | EMA={ema} | EWO={ewo} | HTF={htf}",
            f"rule_candidate={rule} | quality={quality}",
            textwrap.shorten(old_notes or _string(row.get("context_reason")), width=180, placeholder="..."),
        ]
        _copy_with_annotation(source_chart, reviewed_chart, annotation_lines)

        reviewed_rows.append(
            {
                **row.to_dict(),
                "phase": "h4_d1_main",
                "context_source_dir": _rel_to_repo(h4_context_dir),
                "phase23_closure_dir": _rel_to_repo(phase23_dir),
                "chart_path": str(source_chart.resolve()),
                "context_chart_path": str(source_chart.resolve()),
                "source_context_chart_path": str(source_chart.resolve()),
                "reviewed_context_chart_path": str(reviewed_chart.resolve()),
                "context_review_status": status,
                "ema_usefulness": ema,
                "ewo_usefulness": ewo,
                "htf_usefulness": htf,
                "quality_filter_candidate": quality,
                "phase25_rule_candidate": rule,
                "context_notes_integrated": old_notes,
                "context_rule_safety_note": _rule_safety_note(status, phase23_decision, review_category),
                "must_user_review": _must_review(status, phase23_decision, review_category, old_change),
            }
        )
    return pd.DataFrame(reviewed_rows)


def _rule_safety_note(status: str, phase23_decision: str, review_category: str) -> str:
    if review_category == "abc":
        return "ABC legacy/integrated view remains experimental; use the ABC fix line, not this gallery, for ABC methodology."
    if status == "context_should_not_rescue_count":
        return "Context can explain the move but must not rescue a downgraded/excluded/invalid count."
    if phase23_decision == "keep_as_good_example":
        return "Candidate can support a soft context rule, not a hard filter."
    if phase23_decision == "keep_as_ambiguous_example":
        return "Context may explain ambiguity; it does not promote the count to a clean example."
    return "Diagnostic context only."


def _must_review(status: str, phase23_decision: str, review_category: str, old_change: str) -> str:
    if review_category == "abc":
        return "no"
    if phase23_decision == "keep_as_good_example" and status in {"context_conflicts_suspicious", "context_misleading"}:
        return "yes"
    if phase23_decision == "exclude_from_phase25_rules" and status == "context_should_not_rescue_count":
        return "no"
    if old_change == "misleading_if_used_as_filter":
        return "no"
    return "no"


def _build_aux_audit(aux_context_dir: Path, aux_visual_dir: Path, output_dir: Path) -> pd.DataFrame:
    context = _read_csv(aux_context_dir / "tables" / "candidate_context.csv")
    visual_path = aux_visual_dir / "tables" / "visual_case_reviews.csv"
    visual = _read_csv(visual_path) if visual_path.exists() else pd.DataFrame()
    visual = visual.rename(columns={"\ufeffcandidate_id": "candidate_id"})
    visual_cols = [
        "candidate_id",
        "visual_review_status",
        "visual_quality_score",
        "ema_context_usefulness",
        "ewo_context_usefulness",
        "htf_ltf_context_usefulness",
        "likely_problem_if_any",
        "suggested_action",
        "visual_notes",
        "ewo_rule_assessment",
    ]
    visual_join = visual[[column for column in visual_cols if column in visual.columns]].copy() if not visual.empty else visual
    frame = context.merge(visual_join, on="candidate_id", how="left", suffixes=("", "_visual"))

    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        timeframe = _string(row.get("timeframe"))
        review_status = _string(row.get("visual_review_status"))
        category = _string(row.get("review_category"))
        old_action = _string(row.get("suggested_action"))
        notes = _string(row.get("visual_notes")) or _string(row.get("context_reason"))
        ema = _map_ema(_string(row.get("ema_context_usefulness")), "auxiliary", old_action)
        ewo = _map_ewo(_string(row.get("ewo_context_usefulness")), notes)
        htf = _map_htf(_string(row.get("htf_ltf_context_usefulness")), _string(row.get("trend_context_label")))
        status = _aux_context_status(timeframe, category, review_status, old_action)
        quality = _aux_quality(status, timeframe, review_status, old_action)
        rule = _aux_rule(status, timeframe, ema, ewo, htf)

        source_chart = _resolve_chart(aux_context_dir, _string(row.get("context_chart_path")) or _string(row.get("chart_path")))
        target_folder = "auxiliary_h1_h4_m30_h1"
        if status in {"context_misleading", "context_should_not_rescue_count"}:
            target_folder = "misleading_context_examples"
        reviewed_chart = output_dir / "charts" / target_folder / source_chart.name
        annotation_lines = [
            f"2.4.2 auxiliary | {row['candidate_order']} {row['candidate_id']}",
            f"timeframe={timeframe}/{row.get('htf_timeframe', '')} | context={status} | EMA={ema} | EWO={ewo} | HTF={htf}",
            f"rule_candidate={rule} | quality={quality}",
            textwrap.shorten(notes, width=180, placeholder="..."),
        ]
        _copy_with_annotation(source_chart, reviewed_chart, annotation_lines)

        rows.append(
            {
                **row.to_dict(),
                "phase": "auxiliary_h1_h4_m30_h1",
                "chart_path": str(source_chart.resolve()),
                "context_chart_path": str(source_chart.resolve()),
                "source_context_chart_path": str(source_chart.resolve()),
                "reviewed_context_chart_path": str(reviewed_chart.resolve()),
                "context_review_status": status,
                "ema_usefulness": ema,
                "ewo_usefulness": ewo,
                "htf_usefulness": htf,
                "quality_filter_candidate": quality,
                "phase25_rule_candidate": rule,
                "aux_notes": notes,
                "auxiliary_policy": "H1/H4 can refine H4/D1; M30/H1 is microstructure/failure-bank only.",
            }
        )
    return pd.DataFrame(rows)


def _aux_context_status(timeframe: str, category: str, review_status: str, action: str) -> str:
    if category == "abc":
        return "context_should_not_rescue_count"
    if action in {"use_as_negative_example", "do_not_use_for_rules"}:
        return "context_should_not_rescue_count"
    if timeframe == "M30":
        return "context_not_useful" if review_status in {"visually_forced", "likely_false_candidate"} else "context_explains_ambiguity"
    if review_status in {"visually_defensible", "excellent_example"}:
        return "context_confirms_good_count"
    if review_status in {"plausible_but_needs_review", "ambiguous"}:
        return "context_explains_ambiguity"
    if review_status in {"visually_forced", "likely_false_candidate"}:
        return "context_misleading"
    return "context_not_useful"


def _aux_quality(status: str, timeframe: str, review_status: str, action: str) -> str:
    if status in {"context_should_not_rescue_count", "context_misleading"}:
        return "no_misleading"
    if timeframe == "M30":
        return "no_too_noisy"
    if review_status in {"visually_defensible", "excellent_example"} and action in {
        "keep_as_good_example",
        "possible_rule_candidate",
    }:
        return "yes_but_needs_manual_validation"
    return "no_context_only"


def _aux_rule(status: str, timeframe: str, ema: str, ewo: str, htf: str) -> str:
    if status in {"context_should_not_rescue_count", "context_misleading", "context_not_useful"}:
        return "do_not_use_as_rule"
    if timeframe == "M30":
        return "do_not_use_as_rule"
    if htf.startswith("useful"):
        return "htf_alignment_soft_filter"
    if ewo.startswith("useful_for_wave_role"):
        return "ewo_wave3_momentum_support"
    if ema.startswith("useful"):
        return "ema_transition_support"
    return "do_not_use_as_rule"


def _subset(frame: pd.DataFrame, query: str) -> pd.DataFrame:
    return frame.query(query).copy() if not frame.empty else frame.copy()


def _summary_rows(h4: pd.DataFrame, aux: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows.append({"metric": "h4_d1_cases", "value": len(h4)})
    rows.append({"metric": "auxiliary_cases", "value": len(aux)})
    rows.append({"metric": "h4_d1_htf_lookahead_violations", "value": int((h4["htf_lookahead_safe"].astype(str) != "True").sum())})
    if not aux.empty and "htf_lookahead_safe" in aux.columns:
        rows.append({"metric": "aux_htf_lookahead_violations", "value": int((aux["htf_lookahead_safe"].astype(str) != "True").sum())})
    for label, count in h4["context_review_status"].value_counts().items():
        rows.append({"metric": f"h4_context_status_{label}", "value": int(count)})
    for label, count in h4["quality_filter_candidate"].value_counts().items():
        rows.append({"metric": f"h4_quality_candidate_{label}", "value": int(count)})
    for label, count in h4["phase25_rule_candidate"].value_counts().items():
        rows.append({"metric": f"h4_rule_candidate_{label}", "value": int(count)})
    for label, count in aux["context_review_status"].value_counts().items():
        rows.append({"metric": f"aux_context_status_{label}", "value": int(count)})
    return pd.DataFrame(rows)


def _write_report(output_dir: Path, h4: pd.DataFrame, aux: pd.DataFrame, summary: pd.DataFrame, elapsed: float) -> None:
    h4_good = int((h4["quality_filter_candidate"] == "yes_soft_rule").sum())
    h4_soft_review = int((h4["quality_filter_candidate"] == "yes_but_needs_manual_validation").sum())
    h4_rescue = int((h4["context_review_status"] == "context_should_not_rescue_count").sum())
    aux_m30 = int((aux["timeframe"].astype(str) == "M30").sum()) if "timeframe" in aux.columns else 0
    lines = [
        "# WaveCount Fase 2.4.2 - auditoria de contexto/calidad",
        "",
        "Fecha: 2026-05-23",
        "",
        "## Alcance",
        "",
        "Se cruza la galeria Fase 2.4 con el cierre visual Fase 2.3.4.",
        "No se cambian conteos, pivotes, grados, EMAs/EWO, estrategias ni backtests.",
        "",
        "## Resultados H4/D1",
        "",
        f"- Casos H4/D1 revisados: {len(h4)}.",
        f"- Casos donde el contexto puede ser regla blanda: {h4_good}.",
        f"- Casos donde el contexto ayuda pero necesita validacion manual futura: {h4_soft_review}.",
        f"- Casos que el contexto no debe rescatar: {h4_rescue}.",
        "",
        "## Lectura",
        "",
        "- EMAs 50/150 aportan mas como contexto de regimen y ambiguedad que como filtro duro.",
        "- D1/HTF ayuda a distinguir impulso alineado, correccion contra regimen y transicion, pero puede llegar tarde.",
        "- EWO 5-35 es util para momentum de onda 3 y perdida/divergencia de onda 5, pero no debe cambiar conteos cerrados.",
        "- ABC sigue experimental en la vista integrada: no debe usarse para reglas Fase 2.5 hasta una seleccion limpia.",
        "- Fase 2.4 no rescata conteos excluidos en 2.3.4.",
        "",
        "## Control auxiliar",
        "",
        f"- Casos auxiliares H1/M30 revisados: {len(aux)}.",
        f"- Casos M30 dentro del control auxiliar: {aux_m30}.",
        "- H1/H4 puede refinar lectura; M30/H1 queda como microestructura o banco de fallos.",
        "",
        "## Decision",
        "",
        "H4/D1 Fase 2.4 queda cerrada como capa de contexto diagnostico.",
        "Tiene sentido pasar despues a Fase 2.5 solo con reglas blandas, no con filtros duros.",
        "",
        "## Validacion",
        "",
        f"- Tiempo de ejecucion: {elapsed:.2f}s.",
        "- Las tablas CSV tienen indices Markdown para abrir imagenes rapidamente.",
    ]
    (output_dir / "WAVECOUNT_PHASE2_4_2_CONTEXT_QUALITY_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_context_quality_audit(
    h4_context_dir: Path = DEFAULT_H4_CONTEXT_DIR,
    aux_context_dir: Path = DEFAULT_AUX_CONTEXT_DIR,
    phase23_closure_dir: Path = DEFAULT_PHASE23_CLOSURE_DIR,
    previous_h4_audit_dir: Path = DEFAULT_PREVIOUS_H4_AUDIT_DIR,
    aux_visual_audit_dir: Path = DEFAULT_AUX_VISUAL_AUDIT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    started_at = datetime.now().isoformat(timespec="seconds")
    start = perf_counter()
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for folder in [
        "h4_d1_reviewed",
        "auxiliary_h1_h4_m30_h1",
        "best_context_examples",
        "misleading_context_examples",
    ]:
        (output_dir / "charts" / folder).mkdir(parents=True, exist_ok=True)

    h4 = _build_h4_audit(h4_context_dir, phase23_closure_dir, previous_h4_audit_dir, output_dir)
    aux = _build_aux_audit(aux_context_dir, aux_visual_audit_dir, output_dir)

    context_rule_candidates = h4[
        h4["phase25_rule_candidate"].ne("do_not_use_as_rule")
        & h4["quality_filter_candidate"].isin(["yes_soft_rule", "yes_but_needs_manual_validation"])
        & h4["final_phase23_decision"].ne("exclude_from_phase25_rules")
    ].copy()
    context_misleading = pd.concat(
        [
            h4[h4["context_review_status"].isin(["context_misleading", "context_conflicts_suspicious"])],
            aux[aux["context_review_status"].isin(["context_misleading"])],
        ],
        ignore_index=True,
    )
    confirms_good = h4[h4["context_review_status"].isin(["context_confirms_good_count", "context_improves_confidence"])].copy()
    explains_ambiguous = h4[h4["context_review_status"].eq("context_explains_ambiguity")].copy()
    should_not_rescue = pd.concat(
        [
            h4[h4["context_review_status"].eq("context_should_not_rescue_count")],
            aux[aux["context_review_status"].eq("context_should_not_rescue_count")],
        ],
        ignore_index=True,
    )
    must_review = h4[h4["must_user_review"].eq("yes")].copy()
    readiness = pd.DataFrame(
        [
            {
                "scope": "H4/D1",
                "phase24_closed": True,
                "phase25_ready": True,
                "primary_timeframe_policy": "H4/D1 primary; H1/H4 auxiliary; M30/H1 microstructure/failure-bank.",
                "allowed_next_step": "Fase 2.5 can test soft guided search; no hard filters and no signals.",
                "main_risk": "Using context to rescue visually downgraded counts or legacy ABC candidates.",
            }
        ]
    )
    summary = _summary_rows(h4, aux)

    outputs = {
        "h4_d1_context_quality_audit": h4,
        "h1_h4_m30_h1_aux_context_audit": aux,
        "context_rule_candidates": context_rule_candidates,
        "context_misleading_cases": context_misleading,
        "context_confirms_good_counts": confirms_good,
        "context_explains_ambiguous_counts": explains_ambiguous,
        "context_should_not_rescue_counts": should_not_rescue,
        "user_must_review_context_cases": must_review,
        "phase25_context_readiness": readiness,
        "context_quality_summary": summary,
    }
    for name, frame in outputs.items():
        frame.to_csv(tables_dir / f"{name}.csv", index=False)
        _write_image_index(
            tables_dir / f"{name}.csv",
            name.replace("_", " ").title(),
            ["reviewed_context_chart_path", "source_context_chart_path", "reviewed_chart_path"],
        )

    elapsed = perf_counter() - start
    _write_report(output_dir, h4, aux, summary, elapsed)
    meta = {
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_seconds": elapsed,
        "inputs": {
            "h4_context_dir": _rel_to_repo(h4_context_dir),
            "aux_context_dir": _rel_to_repo(aux_context_dir),
            "phase23_closure_dir": _rel_to_repo(phase23_closure_dir),
            "previous_h4_audit_dir": _rel_to_repo(previous_h4_audit_dir),
            "aux_visual_audit_dir": _rel_to_repo(aux_visual_audit_dir),
        },
        "rows": {name: int(len(frame)) for name, frame in outputs.items()},
        "outputs": {name: _rel_to_repo(tables_dir / f"{name}.csv") for name in outputs},
        "notes": [
            "No counting rules were changed.",
            "No strategy, signal, MT5 or benchmark artifact was changed.",
            "Charts are annotated copies of the current Phase 2.4 context images.",
            "The authoritative Phase 2.3 base is phase2_3_4_h4_d1_visual_closure_2026-05-23.",
        ],
    }
    (output_dir / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WaveCount Phase 2.4.2 context quality audit.")
    parser.add_argument("--h4-context-dir", type=Path, default=DEFAULT_H4_CONTEXT_DIR)
    parser.add_argument("--aux-context-dir", type=Path, default=DEFAULT_AUX_CONTEXT_DIR)
    parser.add_argument("--phase23-closure-dir", type=Path, default=DEFAULT_PHASE23_CLOSURE_DIR)
    parser.add_argument("--previous-h4-audit-dir", type=Path, default=DEFAULT_PREVIOUS_H4_AUDIT_DIR)
    parser.add_argument("--aux-visual-audit-dir", type=Path, default=DEFAULT_AUX_VISUAL_AUDIT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta = build_context_quality_audit(
        h4_context_dir=args.h4_context_dir,
        aux_context_dir=args.aux_context_dir,
        phase23_closure_dir=args.phase23_closure_dir,
        previous_h4_audit_dir=args.previous_h4_audit_dir,
        aux_visual_audit_dir=args.aux_visual_audit_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
