"""
Signal Scorer & Driver Selector

Takes raw signals from all extractors, scores them,
selects the top contributing factors, and computes overall confidence.

Rules:
    - Minimum strength threshold: 0.3
    - Max drivers: 4
    - Enforce category diversity (max 2 from same category)
    - Overall confidence = weighted avg of signal strengths × confidences × data quality
"""


STRENGTH_THRESHOLD = 0.3
MAX_DRIVERS = 4
MAX_PER_CATEGORY = 2


def score_and_select_drivers(signals: list[dict], data_quality: dict) -> dict:
    """
    Score all signals and select top drivers.

    Args:
        signals: list of raw signal dicts from all extractors
        data_quality: {macro_fresh, events_available, missing_fields, confidence_adjustment}

    Returns:
        {
            drivers: [...top scored factors...],
            all_signals_count: int,
            overall_confidence: float,
            confidence_breakdown: {data_quality, signal_agreement, final}
        }
    """
    if not signals:
        return {
            "drivers": [],
            "all_signals_count": 0,
            "overall_confidence": 0.2,
            "confidence_breakdown": {
                "data_quality": data_quality.get("confidence_adjustment", 0.5),
                "signal_agreement": 0.0,
                "final": 0.2,
            },
        }

    # Step 1: Filter weak signals
    strong_signals = [s for s in signals if s.get("strength", 0) >= STRENGTH_THRESHOLD]

    if not strong_signals:
        # If no strong signals, take top 2 by strength anyway
        strong_signals = sorted(signals, key=lambda s: s.get("strength", 0), reverse=True)[:2]

    # Step 2: Score each signal (composite score = strength × confidence)
    for s in strong_signals:
        s["composite_score"] = round(s.get("strength", 0) * s.get("confidence", 0), 4)

    # Step 3: Sort by composite score descending
    strong_signals.sort(key=lambda s: s["composite_score"], reverse=True)

    # Step 4: Select top drivers with category diversity
    selected = []
    category_counts = {}

    for s in strong_signals:
        cat = s.get("category", "unknown")
        if category_counts.get(cat, 0) >= MAX_PER_CATEGORY:
            continue
        if len(selected) >= MAX_DRIVERS:
            break

        selected.append(s)
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # Step 5: Compute confidence
    dq_factor = data_quality.get("confidence_adjustment", 0.8)

    if selected:
        # Weighted average of confidence × strength
        total_weight = sum(s["composite_score"] for s in selected)
        if total_weight > 0:
            weighted_conf = sum(s["confidence"] * s["composite_score"] for s in selected) / total_weight
        else:
            weighted_conf = 0.5

        # Signal agreement: do most signals point the same direction?
        impacts = [s["impact"] for s in selected if s["impact"] != "neutral"]
        if impacts:
            positive_count = impacts.count("positive")
            negative_count = impacts.count("negative")
            dominant = max(positive_count, negative_count)
            agreement = dominant / len(impacts)
        else:
            agreement = 0.5
    else:
        weighted_conf = 0.3
        agreement = 0.5

    final_confidence = round(weighted_conf * agreement * dq_factor, 4)
    final_confidence = max(0.1, min(final_confidence, 0.95))

    return {
        "drivers": selected,
        "all_signals_count": len(signals),
        "overall_confidence": final_confidence,
        "confidence_breakdown": {
            "data_quality": round(dq_factor, 4),
            "signal_agreement": round(agreement, 4),
            "final": final_confidence,
        },
    }


def compute_data_quality(
    has_indicators: bool,
    has_macro: bool,
    has_events: bool,
    macro_fresh: bool,
    missing_fields: list[str] = None,
) -> dict:
    """
    Compute data quality metrics that influence confidence.
    """
    quality_score = 1.0

    if not has_indicators:
        quality_score -= 0.3
    if not has_macro:
        quality_score -= 0.15
    elif not macro_fresh:
        quality_score -= 0.08
    if not has_events:
        quality_score -= 0.05
    if missing_fields:
        quality_score -= len(missing_fields) * 0.02

    quality_score = max(0.3, min(quality_score, 1.0))

    return {
        "macro_fresh": macro_fresh,
        "events_available": has_events,
        "missing_fields": missing_fields or [],
        "confidence_adjustment": round(quality_score, 4),
    }
