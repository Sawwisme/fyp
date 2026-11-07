def estimate_severity(
    detected_conditions,
    gradcam_spreads=None,
    gingivitis_area_percent=0.0,
    calculus_area_percent=0.0
):
    """
    Hybrid rule-based severity estimation.

    detected_conditions:
        list[str]
        Example:
        ["plaque", "gingivitis", "calculus"]

    gradcam_spreads:
        dict[str, float]
        Example:
        {
            "plaque": 4.08,
            "gingivitis": 10.20,
            "calculus": 4.08
        }

    gingivitis_area_percent:
        float

    calculus_area_percent:
        float

    Returns:
        dict
    """

    if gradcam_spreads is None:
        gradcam_spreads = {}

    detected_conditions = [
        condition.lower()
        for condition in detected_conditions
    ]

    disease_conditions = [
        condition
        for condition in detected_conditions
        if condition in [
            "plaque",
            "gingivitis",
            "calculus"
        ]
    ]

    # -----------------------------------------------------
    # No disease detected
    # -----------------------------------------------------

    if not disease_conditions:
        return {
            "severity": "None",
            "disease_conditions": [],
            "condition_count": 0,
            "gradcam_category": "Not applicable",
            "segmentation_category": "Not applicable",
            "gingivitis_area_percent": round(float(gingivitis_area_percent), 2),
            "calculus_area_percent": round(float(calculus_area_percent), 2),
            "max_gradcam_spread_percent": 0.0,
            "segmentation_area_percent": 0.0,
            "reason": "No dental disease condition was detected."
        }

    # -----------------------------------------------------
    # Grad-CAM overall attention
    # -----------------------------------------------------

    relevant_spreads = [
        float(
            gradcam_spreads.get(
                condition,
                0.0
            )
        )
        for condition in disease_conditions
    ]

    max_gradcam_spread = (
        max(relevant_spreads)
        if relevant_spreads
        else 0.0
    )

    if max_gradcam_spread < 8.0:
        gradcam_category = "Localized"

    elif max_gradcam_spread <= 20.0:
        gradcam_category = "Moderate"

    else:
        gradcam_category = "Widespread"

    # -----------------------------------------------------
    # Segmentation extent
    # -----------------------------------------------------

    segmentation_area = (
        gingivitis_area_percent
        + calculus_area_percent
    )

    segmentation_area = max(
        0.0,
        min(
            segmentation_area,
            100.0
        )
    )

    if segmentation_area < 5.0:
        segmentation_category = "Small"

    elif segmentation_area <= 15.0:
        segmentation_category = "Medium"

    else:
        segmentation_category = "Large"

    # -----------------------------------------------------
    # Base severity from disease burden
    # -----------------------------------------------------

    condition_count = len(
        disease_conditions
    )

    if condition_count == 1:
        severity_level = 1

    elif condition_count == 2:
        severity_level = 2

    else:
        severity_level = 2

    # -----------------------------------------------------
    # Grad-CAM adjustment
    # -----------------------------------------------------

    if (
        gradcam_category == "Widespread"
        and severity_level < 3
    ):
        severity_level += 1

    # -----------------------------------------------------
    # Segmentation adjustment
    # Supporting evidence only
    # -----------------------------------------------------

    if (
        segmentation_category == "Large"
        and severity_level < 3
    ):
        severity_level += 1

    # Multiple conditions + meaningful visual involvement
    if (
        condition_count >= 2
        and severity_level < 3
        and (
            gradcam_category
            in [
                "Moderate",
                "Widespread"
            ]
            or segmentation_category
            in [
                "Medium",
                "Large"
            ]
        )
    ):
        severity_level += 1

    severity_level = min(
        severity_level,
        3
    )

    severity_map = {
        1: "Mild",
        2: "Moderate",
        3: "Severe"
    }

    severity = severity_map[
        severity_level
    ]

    # -----------------------------------------------------
    # Explanation
    # -----------------------------------------------------

    reasons = []

    reasons.append(
        f"{condition_count} dental disease condition(s) "
        f"detected: "
        f"{', '.join(disease_conditions)}."
    )

    reasons.append(
        f"Maximum Grad-CAM attention spread: "
        f"{max_gradcam_spread:.2f}% "
        f"({gradcam_category})."
    )

    reasons.append(
        f"Estimated segmentation area: "
        f"{segmentation_area:.2f}% "
        f"({segmentation_category})."
    )

    return {
        "severity": severity,

        "disease_conditions":
            disease_conditions,

        "condition_count":
            condition_count,

        "max_gradcam_spread_percent":
            round(
                max_gradcam_spread,
                2
            ),

        "gradcam_category":
            gradcam_category,

        "segmentation_area_percent":
            round(
                segmentation_area,
                2
            ),

        "segmentation_category":
            segmentation_category,

        "gingivitis_area_percent":
            round(
                gingivitis_area_percent,
                2
            ),

        "calculus_area_percent":
            round(
                calculus_area_percent,
                2
            ),

        "reason":
            " ".join(
                reasons
            )
    }


# =========================================================
# Local test
# =========================================================

if __name__ == "__main__":

    result = estimate_severity(
        detected_conditions=[
            "plaque",
            "gingivitis",
            "calculus"
        ],

        gradcam_spreads={
            "plaque": 4.08,
            "gingivitis": 10.20,
            "calculus": 4.08
        },

        gingivitis_area_percent=1.60,
        calculus_area_percent=0.27
    )

    print(result)