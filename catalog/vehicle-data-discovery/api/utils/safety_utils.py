"""Safety calculation utilities for autonomous driving."""
import logging

logger = logging.getLogger(__name__)


def calculate_safety_weighted_target(cluster):
    """
    Safety-grade target calculation for autonomous driving.
    Addresses the "long tail" risk problem in autonomous driving.

    Implements the risk-adaptive formula:
    Test_Target = Count × max(Uniqueness, Target_Multiplier)

    Risk Level Logic:
    - Critical (>0.8): Zero-skip policy - similarity is ignored for safety
    - High (0.5-0.8): Stability priority - minimum 80% sampling for corner cases
    - Routine (<0.5): Efficiency priority - aggressive DTO reduction allowed

    Args:
        cluster: DiscoveredCluster object with scene_count, average_risk_score, uniqueness_score

    Returns:
        Dict with test_target, rationale, safety_override flag, and dto_value
    """
    try:
        total_scenes = cluster.scene_count
        risk_score = getattr(cluster, 'average_risk_score', 0.5)
        uniqueness_score = getattr(cluster, 'uniqueness_score', 0.7)

        if risk_score > 0.8:
            target_multiplier = 1.0
            risk_rationale = f"Critical risk ({risk_score:.2f}) → Testing ALL scenes (safety override)"
            safety_override = True
        elif risk_score >= 0.5:
            target_multiplier = 0.8
            risk_rationale = f"High risk ({risk_score:.2f}) → Minimum 80% testing required"
            safety_override = False
        else:
            target_multiplier = uniqueness_score * 0.7
            risk_rationale = f"Routine risk ({risk_score:.2f}) → DTO efficiency enabled"
            safety_override = False

        safety_target = int(total_scenes * max(uniqueness_score, target_multiplier))
        scenes_saved = total_scenes - safety_target
        dto_value = safety_target * 30

        logger.info(f"Safety calculation: {total_scenes} scenes → {safety_target} target ({risk_rationale})")

        return {
            "test_target": safety_target,
            "risk_rationale": risk_rationale,
            "safety_override": safety_override,
            "scenes_saved": max(0, scenes_saved),
            "dto_value": dto_value,
            "risk_score": risk_score,
            "target_multiplier": target_multiplier
        }

    except Exception as e:
        logger.error(f"Safety calculation failed for cluster: {str(e)}")
        fallback_target = getattr(cluster, 'scene_count', 50)
        return {
            "test_target": fallback_target,
            "risk_rationale": "Safety fallback: Testing all scenes due to calculation error",
            "safety_override": True,
            "scenes_saved": 0,
            "dto_value": fallback_target * 30,
            "risk_score": 1.0,
            "target_multiplier": 1.0
        }


def calculate_safety_based_coverage_target(actual_scenes, risk_score, uniqueness_score):
    """
    Calculate coverage matrix target for safety-based analysis.

    Args:
        actual_scenes: Current number of scenes in category
        risk_score: Risk level of the category
        uniqueness_score: Diversity within category

    Returns:
        Target scene count for coverage analysis
    """
    try:
        if risk_score > 0.8:
            min_required = max(200, actual_scenes)
        elif risk_score > 0.5:
            min_required = max(100, actual_scenes)
        else:
            min_required = max(50, actual_scenes)

        if uniqueness_score < 0.3:
            diversity_multiplier = 1.5
        else:
            diversity_multiplier = 1.0

        coverage_target = int(min_required * diversity_multiplier)
        return max(actual_scenes, coverage_target)

    except Exception as e:
        logger.error(f"Coverage target calculation failed: {str(e)}")
        return actual_scenes
