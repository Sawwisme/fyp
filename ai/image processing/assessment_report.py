"""Presentation of existing assessment outputs; no inference or score changes."""
from pathlib import Path
import math
import textwrap

import cv2
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def save_combined_analysis_summary(
    image_path,
    gradcam_summary_path,
    segmentation_output_path,
    severity_result,
    output_dir=None,
    *,
    calculus_colour="#FFD600",
):
    navy, blue, muted = "#172333", "#2549C7", "#5A687E"
    images = []
    for path in (image_path, segmentation_output_path, gradcam_summary_path):
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Unable to read report image: {path}")
        images.append(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    def percent(key):
        value = severity_result.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return "Not available"
        if not math.isfinite(value) or not 0 <= value <= 100:
            return "Not available"
        return f"{value:.2f}%"

    conditions = severity_result.get("disease_conditions", [])
    conditions = conditions if isinstance(conditions, (list, tuple)) else []
    conditions = [str(item).replace("_", " ").capitalize() for item in conditions]
    condition_text = ", ".join(conditions) or "No condition flagged in this photo"
    severity = str(severity_result.get("severity") or "Not available")
    severity_colour = {
        "severe": "#FFE2E6", "moderate": "#FFF0CC", "mild": "#E8EDFF",
    }.get(severity.lower(), "#E8EDFF")

    fig = plt.figure(figsize=(11, 16), facecolor="#F0F3F9")

    def card(x, y, width, height, colour="white", border="#DEE5F0"):
        patch = FancyBboxPatch(
            (x, y), width, height,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            transform=fig.transFigure,
            facecolor=colour, edgecolor=border, linewidth=0.8,
        )
        fig.add_artist(patch)
        patch.set_zorder(0)

    def text(x, y, value, size=11, colour=navy, weight="normal", **kwargs):
        return fig.text(x, y, value, fontsize=size, color=colour,
                        fontweight=weight, va="top", **kwargs)

    def image_panel(bounds, image):
        ax = fig.add_axes(bounds, zorder=2)
        ax.imshow(image)
        ax.set_axis_off()

    try:
        text(0.055, 0.958, "DENTAL ASSESSMENT", 23, weight="bold")
        text(0.055, 0.928, "Your photo. Your screening reference.", 11, muted)
        text(0.945, 0.955, "VetDental", 15, blue, "bold", ha="right")

        card(0.05, 0.797, 0.90, 0.096, navy, navy)
        text(0.072, 0.875, "ESTIMATED SEVERITY", 9, "#C6D3E8", "bold")
        text(0.072, 0.851, severity, 28, severity_colour, "bold")
        text(0.435, 0.875, "POSSIBLE FINDINGS", 9, "#C6D3E8", "bold")
        text(0.435, 0.849, textwrap.fill(condition_text, 38),
             14, "white", "bold", linespacing=1.5)
        text(0.055, 0.780, "AI screening reference - a veterinary review can confirm its meaning.", 9, muted)

        metrics = [
            ("GINGIVITIS REGION", "gingivitis_area_percent", "#C83149"),
            ("CALCULUS REGION", "calculus_area_percent", "#8A6500"),
            ("MAX. ATTENTION SPREAD", "max_gradcam_spread_percent", blue),
        ]
        for index, (label, key, colour) in enumerate(metrics):
            x = 0.05 + index * 0.308
            card(x, 0.689, 0.284, 0.065)
            text(x + 0.016, 0.741, label, 8, muted, "bold")
            text(x + 0.016, 0.721, percent(key), 22, colour, "bold")
        text(0.055, 0.673, "Region values use the analysed image area. These percentages are not disease probabilities.", 8.5, muted)

        card(0.05, 0.432, 0.434, 0.221)
        card(0.516, 0.432, 0.434, 0.221)
        text(0.068, 0.640, "01  Original photo", 12, weight="bold")
        text(0.534, 0.640, "02  Predicted regions", 12, weight="bold")
        image_panel([0.064, 0.462, 0.406, 0.158], images[0])
        image_panel([0.530, 0.462, 0.406, 0.158], images[1])
        text(0.068, 0.450, "Uploaded dental photo", 8.5, muted)
        text(0.534, 0.450, "Red: gingivitis", 8.5, "#C83149", "bold")
        colour_name = "Green" if calculus_colour.lower() == "#00ff00" else "Yellow"
        text(0.739, 0.450, f"{colour_name}: calculus", 8.5,
             "#267B45" if colour_name == "Green" else "#8A6500", "bold")

        card(0.05, 0.102, 0.90, 0.298)
        text(0.068, 0.386, "03  Model attention", 12, weight="bold")
        text(0.068, 0.365, "Attention shows where the classifier focused; it does not confirm disease boundaries.", 8.5, muted)
        image_panel([0.068, 0.116, 0.864, 0.234], images[2])

        text(0.055, 0.079, "HOW TO READ THIS REPORT", 9, blue, "bold")
        text(0.055, 0.063,
             "Segmentation colours identify predicted regions. Heatmap colours show attention strength.\n"
             "An unflagged photo does not rule out a problem. Keep this report for your veterinarian.",
             9, muted, linespacing=1.6)

        directory = Path(output_dir) if output_dir else (
            Path(__file__).resolve().parent / "models" / "analysis_outputs"
        )
        directory.mkdir(parents=True, exist_ok=True)
        output_path = directory / f"{Path(image_path).stem}_analysis_summary.png"
        fig.savefig(output_path, dpi=150, facecolor=fig.get_facecolor())
        return str(output_path)
    finally:
        plt.close(fig)
