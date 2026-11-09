import os
import cv2
import matplotlib.pyplot as plt

from gradcam import run_automatic_gradcam
from segmentation_inference import run_segmentation
from severity_estimation import estimate_severity


# =========================================================
# Save combined analysis summary
# =========================================================

def save_combined_analysis_summary(
    image_path,
    gradcam_summary_path,
    segmentation_output_path,
    severity_result,
    output_dir=None
):
    original = cv2.imread(
        image_path
    )

    if original is None:
        raise ValueError(
            f"Unable to read original image: {image_path}"
        )

    original = cv2.cvtColor(
        original,
        cv2.COLOR_BGR2RGB
    )

    gradcam_summary = cv2.imread(
        gradcam_summary_path
    )

    if gradcam_summary is None:
        raise ValueError(
            f"Unable to read Grad-CAM summary: "
            f"{gradcam_summary_path}"
        )

    gradcam_summary = cv2.cvtColor(
        gradcam_summary,
        cv2.COLOR_BGR2RGB
    )

    segmentation = cv2.imread(
        segmentation_output_path
    )

    if segmentation is None:
        raise ValueError(
            f"Unable to read segmentation output: "
            f"{segmentation_output_path}"
        )

    segmentation = cv2.cvtColor(
        segmentation,
        cv2.COLOR_BGR2RGB
    )

    # =====================================================
    # Create figure
    # =====================================================

    plt.figure(
        figsize=(16, 12)
    )

    # -----------------------------------------------------
    # Original image
    # -----------------------------------------------------

    plt.subplot(
        2,
        2,
        1
    )

    plt.imshow(
        original
    )

    plt.title(
        "Original Image",
        fontsize=14
    )

    plt.axis(
        "off"
    )

    # -----------------------------------------------------
    # Grad-CAM
    # -----------------------------------------------------

    plt.subplot(
        2,
        2,
        2
    )

    plt.imshow(
        gradcam_summary
    )

    plt.title(
        "Grad-CAM Attention",
        fontsize=14
    )

    plt.axis(
        "off"
    )

    # -----------------------------------------------------
    # Segmentation
    # -----------------------------------------------------

    plt.subplot(
        2,
        2,
        3
    )

    plt.imshow(
        segmentation
    )

    plt.title(
        "Segmentation\n"
        "Red = Gingivitis | Green = Calculus",
        fontsize=14
    )

    plt.axis(
        "off"
    )

    # -----------------------------------------------------
    # Severity result
    # -----------------------------------------------------

    plt.subplot(
        2,
        2,
        4
    )

    plt.axis(
        "off"
    )

    disease_conditions = (
        severity_result.get(
            "disease_conditions",
            []
        )
    )

    if disease_conditions:
        conditions_text = ", ".join(
            condition.capitalize()
            for condition
            in disease_conditions
        )
    else:
        conditions_text = (
            "No disease condition detected"
        )

    severity_text = (
        f"Estimated Severity\n"
        f"{severity_result['severity']}\n\n"

        f"Detected Conditions\n"
        f"{conditions_text}\n\n"

        f"Grad-CAM Attention\n"
        f"Category: "
        f"{severity_result['gradcam_category']}\n"
        f"Maximum Spread: "
        f"{severity_result['max_gradcam_spread_percent']:.2f}%\n\n"

        f"Segmentation Reference\n"
        f"Category: "
        f"{severity_result['segmentation_category']}\n"
        f"Estimated Area: "
        f"{severity_result['segmentation_area_percent']:.2f}%\n\n"

        f"Gingivitis Area: "
        f"{severity_result['gingivitis_area_percent']:.2f}%\n"
        f"Calculus Area: "
        f"{severity_result['calculus_area_percent']:.2f}%"
    )

    plt.text(
        0.05,
        0.95,
        severity_text,
        fontsize=14,
        verticalalignment="top"
    )

    plt.tight_layout()

    # =====================================================
    # Output folder
    # =====================================================

    base_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    output_dir = output_dir or os.path.join(
        base_dir,
        "models",
        "analysis_outputs"
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    image_name = os.path.splitext(
        os.path.basename(
            image_path
        )
    )[0]

    output_path = os.path.join(
        output_dir,
        f"{image_name}_analysis_summary.png"
    )

    # =====================================================
    # Save
    # =====================================================

    plt.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight"
    )

    plt.show()

    plt.close()

    return output_path


# =========================================================
# Complete dental analysis pipeline
# =========================================================

def analyze_dental_image(
    image_path,
    output_dir=None,
    raise_on_rejection=False,
):
    """
    Run complete dental image analysis.

    Pipeline:
    1. File / image validation
    2. Dental image validation
    3. Disease classification
    4. Grad-CAM generation
    5. Segmentation
    6. Hybrid severity estimation
    7. Combined analysis summary

    Returns:
        dict or None
    """

    print(
        "\n==================================="
    )

    print(
        "Complete Dental Analysis"
    )

    print(
        "==================================="
    )

    # =====================================================
    # STEP 1:
    # Classification + Grad-CAM
    # =====================================================

    gradcam_result = run_automatic_gradcam(
        image_path,
        raise_on_rejection=raise_on_rejection,
    )

    if gradcam_result is None:

        print(
            "\nDental analysis stopped because "
            "image validation failed."
        )

        return None

    # =====================================================
    # STEP 2:
    # Get detected disease conditions
    # =====================================================

    detected_conditions = []

    predictions = (
        gradcam_result[
            "predictions"
        ]
    )

    for condition, result in (
        predictions.items()
    ):

        if (
            condition != "healthy"
            and result["positive"]
        ):

            detected_conditions.append(
                condition
            )

    # =====================================================
    # STEP 3:
    # Get Grad-CAM spread values
    # =====================================================

    gradcam_spreads = {}

    for item in (
        gradcam_result[
            "gradcam_items"
        ]
    ):

        condition = (
            item[
                "condition"
            ]
        )

        if condition != "healthy":

            gradcam_spreads[
                condition
            ] = (
                item[
                    "gradcam_spread_percent"
                ]
            )

    # =====================================================
    # STEP 4:
    # Segmentation
    # =====================================================

    segmentation_result = (
        run_segmentation(
            image_path
        )
    )

    gingivitis_area = (
        segmentation_result[
            "gingivitis_area_percent"
        ]
    )

    calculus_area = (
        segmentation_result[
            "calculus_area_percent"
        ]
    )

    # =====================================================
    # STEP 5:
    # Severity estimation
    # =====================================================

    severity_result = (
        estimate_severity(

            detected_conditions=
                detected_conditions,

            gradcam_spreads=
                gradcam_spreads,

            gingivitis_area_percent=
                gingivitis_area,

            calculus_area_percent=
                calculus_area
        )
    )

    # =====================================================
    # STEP 6:
    # Generate combined summary
    # =====================================================

    combined_summary_path = (
        save_combined_analysis_summary(

            image_path,

            gradcam_result[
                "gradcam_summary"
            ],

            segmentation_result[
                "segmentation_output"
            ],

            severity_result,
            output_dir=output_dir
        )
    )

    # =====================================================
    # STEP 7:
    # Build final structured result
    # =====================================================

    final_result = {

        "image_path":
            image_path,

        "predictions":
            predictions,

        "detected_conditions":
            detected_conditions,

        "gradcam": {

            "items":
                gradcam_result[
                    "gradcam_items"
                ],

            "summary":
                gradcam_result[
                    "gradcam_summary"
                ]
        },

        "segmentation":
            segmentation_result,

        "severity":
            severity_result,

        "analysis_summary":
            combined_summary_path
    }

    # =====================================================
    # Print final result
    # =====================================================

    print(
        "\n==================================="
    )

    print(
        "FINAL DENTAL ANALYSIS RESULT"
    )

    print(
        "==================================="
    )

    # -----------------------------------------------------
    # Detected conditions
    # -----------------------------------------------------

    print(
        "\nDetected conditions:"
    )

    if detected_conditions:

        for condition in (
            detected_conditions
        ):

            print(
                f"- {condition}"
            )

    else:

        print(
            "- No disease condition detected"
        )

    # -----------------------------------------------------
    # Grad-CAM
    # -----------------------------------------------------

    print(
        "\nGrad-CAM attention:"
    )

    if gradcam_spreads:

        for condition, spread in (
            gradcam_spreads.items()
        ):

            print(
                f"- {condition}: "
                f"{spread:.2f}%"
            )

    else:

        print(
            "- No disease Grad-CAM result"
        )

    # -----------------------------------------------------
    # Segmentation
    # -----------------------------------------------------

    print(
        "\nSegmentation:"
    )

    print(
        f"- Gingivitis area: "
        f"{gingivitis_area:.2f}%"
    )

    print(
        f"- Calculus area: "
        f"{calculus_area:.2f}%"
    )

    print(
        f"- Total estimated area: "
        f"{segmentation_result['total_disease_area_percent']:.2f}%"
    )

    # -----------------------------------------------------
    # Severity
    # -----------------------------------------------------

    print(
        "\nEstimated severity:"
    )

    print(
        severity_result[
            "severity"
        ]
    )

    print(
        "\nReason:"
    )

    print(
        severity_result[
            "reason"
        ]
    )

    # -----------------------------------------------------
    # Combined result
    # -----------------------------------------------------

    print(
        "\nCombined analysis summary:"
    )

    print(
        combined_summary_path
    )

    return final_result


# =========================================================
# Local testing
# =========================================================

if __name__ == "__main__":

    BASE_DIR = os.path.dirname(
        os.path.abspath(__file__)
    )

    IMAGE_PATH = os.path.join(
        BASE_DIR,
        "fyp final dataset",
        "images",
        "cat_0741.jpg"
    )

    result = (
        analyze_dental_image(
            IMAGE_PATH
        )
    )