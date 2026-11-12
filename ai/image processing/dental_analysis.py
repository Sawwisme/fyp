import os
import cv2
import matplotlib.pyplot as plt
from pathlib import Path

import numpy as np

from matplotlib.lines import Line2D
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from gradcam import run_automatic_gradcam
from segmentation_inference import run_segmentation
from severity_estimation import estimate_severity


# =========================================================
# Save combined analysis summary
# =========================================================

def save_combined_analysis_summary(
    image_path,
    heatmaps,
    mask,
    output_dir=None,
):
    original = cv2.imread(str(image_path))

    if original is None:
        raise ValueError(f"Unable to read image: {image_path}")

    rgb = cv2.cvtColor(original, cv2.COLOR_BGR2RGB)
    height, width = rgb.shape[:2]

    # Match the segmentation mask to the original photo.
    mask = np.asarray(mask)

    if mask.ndim != 2 or not np.isin(mask, [0, 1, 2]).all():
        raise ValueError(
            "Expected a segmentation mask with classes 0, 1 and 2."
        )

    mask = cv2.resize(
        mask.astype(np.uint8),
        (width, height),
        interpolation=cv2.INTER_NEAREST,
    )

    maps = []

    for condition, values in heatmaps.items():
        if condition not in {"plaque", "gingivitis", "calculus"}:
            continue

        values = np.asarray(values, dtype=np.float32)

        if values.ndim != 2 or values.size == 0:
            raise ValueError(
                "Expected a two-dimensional Grad-CAM map."
            )

        values = np.nan_to_num(
            values,
            nan=0,
            posinf=0,
            neginf=0,
        )

        values = cv2.resize(
            values,
            (width, height),
            interpolation=cv2.INTER_LINEAR,
        )

        maps.append(np.clip(values, 0, 1))

    display = rgb.astype(np.float32) / 255.0

    has_attention = bool(maps) and any(
        np.any(values > 0)
        for values in maps
    )

    if has_attention:
        # Show the strongest disease attention at each pixel.
        merged = np.max(np.stack(maps), axis=0)
        colours = plt.get_cmap("jet")(merged)[..., :3]

        # Stronger attention gets a stronger overlay.
        # Zero attention leaves the original photo unchanged.
        # Stronger visual overlay; raw scores remain unchanged.
        alpha = (0.65 * np.sqrt(merged))[..., None]

        display = np.clip(
            display * (1 - alpha) + colours * alpha,
            0,
            1,
        )

    figure_height = max(
        5,
        min(10, 10 * height / width),
    ) + 1

    fig, ax = plt.subplots(
        figsize=(10, figure_height),
    )

    try:
        fig.patch.set_facecolor("#F3F5FA")

        ax.imshow(display)
        ax.set_axis_off()

        ax.set_title(
            "Model attention + predicted regions",
            fontsize=15,
            color="#172333",
            pad=15,
            fontweight="bold",
        )

        classes = [
            (1, "#FF0000"),
            (2, "#FFD600"),
        ]

        for class_id, colour in classes:
            binary = (mask == class_id).astype(np.uint8)

            contours, _ = cv2.findContours(
                binary,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE,
            )

            for contour in contours:
                if len(contour) < 3:
                    continue

                points = contour[:, 0, :]
                points = np.vstack([points, points[0]])

                ax.plot(
                    points[:, 0],
                    points[:, 1],
                    color="black",
                    linewidth=3.5,
                )

                ax.plot(
                    points[:, 0],
                    points[:, 1],
                    color=colour,
                    linewidth=1.8,
                )

        if has_attention:
            bar = fig.colorbar(
                ScalarMappable(
                    norm=Normalize(0, 1),
                    cmap="jet",
                ),
                ax=ax,
                fraction=0.035,
                pad=0.02,
                shrink=0.8,
            )

            bar.set_label(
                "Relative model attention",
                fontsize=9,
            )

            bar.set_ticks(
                [0, 0.5, 1],
                labels=["Lower", "Medium", "Higher"],
            )

            bar.ax.tick_params(labelsize=8)

        else:
            fig.text(
                0.5,
                0.105,
                "No disease attention map is available for this photo.",
                ha="center",
                fontsize=9,
                color="#53627A",
            )

        fig.legend(
            handles=[
                Line2D(
                    [0],
                    [0],
                    color="#FF0000",
                    lw=3,
                    label="Gingivitis region",
                ),
                Line2D(
                    [0],
                    [0],
                    color="#FFD600",
                    lw=3,
                    label="Calculus region",
                ),
            ],
            loc="lower center",
            bbox_to_anchor=(0.5, 0.055),
            ncol=2,
            frameon=False,
        )

        fig.text(
            0.5,
            0.025,
            "Heatmap = model attention. "
            "Outlines = segmentation predictions, not confirmed disease.",
            ha="center",
            fontsize=8,
            color="#53627A",
        )

        fig.subplots_adjust(
            left=0.02,
            right=0.95,
            top=0.90,
            bottom=0.15,
        )

        directory = (
            Path(output_dir)
            if output_dir
            else Path(__file__).resolve().parent
            / "models"
            / "analysis_outputs"
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        target = directory / (
            f"{Path(image_path).stem}_analysis_summary.png"
        )

        fig.savefig(
            target,
            dpi=160,
            facecolor=fig.get_facecolor(),
        )

        return str(target)

    finally:
        plt.close(fig)
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

    combined_summary_path = save_combined_analysis_summary(
        image_path,
        heatmaps=gradcam_result.pop("_heatmaps"),
        mask=segmentation_result.pop("_mask"),
        output_dir=output_dir,
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