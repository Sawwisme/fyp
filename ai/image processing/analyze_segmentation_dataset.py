import os
import cv2
import numpy as np


# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATASET_DIR = os.path.join(
    BASE_DIR,
    "segmentation split"
)

SPLITS = [
    "train",
    "validation",
    "test"
]

CLASS_NAMES = {
    0: "background",
    1: "gingivitis",
    2: "calculus"
}


# =========================================================
# Analyse one split
# =========================================================

def analyse_split(split_name):

    mask_dir = os.path.join(
        DATASET_DIR,
        split_name,
        "masks"
    )

    mask_files = [
        f
        for f in os.listdir(mask_dir)
        if f.lower().endswith(".png")
    ]

    total_images = len(mask_files)

    total_pixels = 0

    class_pixels = {
        0: 0,
        1: 0,
        2: 0
    }

    category_counts = {
        "background_only": 0,
        "gingivitis_only": 0,
        "calculus_only": 0,
        "both": 0
    }

    gingivitis_areas = []
    calculus_areas = []
    total_lesion_areas = []

    for filename in mask_files:

        mask_path = os.path.join(
            mask_dir,
            filename
        )

        mask = cv2.imread(
            mask_path,
            cv2.IMREAD_GRAYSCALE
        )

        if mask is None:
            continue

        total_pixels += mask.size

        for class_id in range(3):

            class_pixels[class_id] += np.sum(
                mask == class_id
            )

        gingivitis_pixels = np.sum(
            mask == 1
        )

        calculus_pixels = np.sum(
            mask == 2
        )

        has_gingivitis = (
            gingivitis_pixels > 0
        )

        has_calculus = (
            calculus_pixels > 0
        )

        if (
            has_gingivitis
            and has_calculus
        ):
            category_counts[
                "both"
            ] += 1

        elif has_gingivitis:

            category_counts[
                "gingivitis_only"
            ] += 1

        elif has_calculus:

            category_counts[
                "calculus_only"
            ] += 1

        else:

            category_counts[
                "background_only"
            ] += 1

        image_pixels = mask.size

        gingivitis_ratio = (
            gingivitis_pixels
            / image_pixels
        )

        calculus_ratio = (
            calculus_pixels
            / image_pixels
        )

        lesion_ratio = (
            gingivitis_pixels
            + calculus_pixels
        ) / image_pixels

        if has_gingivitis:
            gingivitis_areas.append(
                gingivitis_ratio
            )

        if has_calculus:
            calculus_areas.append(
                calculus_ratio
            )

        if lesion_ratio > 0:
            total_lesion_areas.append(
                lesion_ratio
            )

    # =====================================================
    # Print split results
    # =====================================================

    print()
    print("===================================")
    print(
        f"{split_name.upper()} SPLIT"
    )
    print("===================================")

    print(
        "Total images:",
        total_images
    )

    print()

    print("Image categories:")

    for category, count in category_counts.items():

        percentage = (
            count
            / total_images
            * 100
        )

        print(
            f"{category}: "
            f"{count} "
            f"({percentage:.2f}%)"
        )

    print()
    print("Pixel distribution:")

    for class_id in range(3):

        percentage = (
            class_pixels[class_id]
            / total_pixels
            * 100
        )

        print(
            f"{CLASS_NAMES[class_id]}: "
            f"{class_pixels[class_id]} "
            f"({percentage:.4f}%)"
        )

    print()

    if gingivitis_areas:

        print(
            "Gingivitis area:"
        )

        print(
            f"Average: "
            f"{np.mean(gingivitis_areas) * 100:.4f}%"
        )

        print(
            f"Minimum: "
            f"{np.min(gingivitis_areas) * 100:.4f}%"
        )

        print(
            f"Maximum: "
            f"{np.max(gingivitis_areas) * 100:.4f}%"
        )

    print()

    if calculus_areas:

        print(
            "Calculus area:"
        )

        print(
            f"Average: "
            f"{np.mean(calculus_areas) * 100:.4f}%"
        )

        print(
            f"Minimum: "
            f"{np.min(calculus_areas) * 100:.4f}%"
        )

        print(
            f"Maximum: "
            f"{np.max(calculus_areas) * 100:.4f}%"
        )

    print()

    if total_lesion_areas:

        print(
            "Total lesion area:"
        )

        print(
            f"Average: "
            f"{np.mean(total_lesion_areas) * 100:.4f}%"
        )

        print(
            f"Minimum: "
            f"{np.min(total_lesion_areas) * 100:.4f}%"
        )

        print(
            f"Maximum: "
            f"{np.max(total_lesion_areas) * 100:.4f}%"
        )


# =========================================================
# Run
# =========================================================

print()
print("===================================")
print("SEGMENTATION DATASET ANALYSIS")
print("===================================")

for split_name in SPLITS:

    analyse_split(
        split_name
    )

print()
print("===================================")
print("Analysis completed")
print("===================================")