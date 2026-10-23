import os
import json
import shutil

import cv2
import numpy as np


# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SOURCE_DIR = r"C:\Users\USER\OneDrive\Documents\fyp dataset\PawPawHealth.v1i.coco-segmentation"

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "segmentation dataset"
)

# PawPawHealth COCO category IDs
GINGIVITIS_ID = 1
CALCULUS_ID = 2

# Final mask values
BACKGROUND_VALUE = 0
GINGIVITIS_VALUE = 1
CALCULUS_VALUE = 2

VALID_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png"
)

SPLIT_MAPPING = {
    "train": "train",
    "valid": "validation",
    "test": "test"
}


# =========================================================
# Helper: create output folders
# =========================================================

def create_output_folders():

    for output_split in SPLIT_MAPPING.values():

        image_dir = os.path.join(
            OUTPUT_DIR,
            output_split,
            "images"
        )

        mask_dir = os.path.join(
            OUTPUT_DIR,
            output_split,
            "masks"
        )

        os.makedirs(
            image_dir,
            exist_ok=True
        )

        os.makedirs(
            mask_dir,
            exist_ok=True
        )


# =========================================================
# Helper: polygon segmentation to mask
# =========================================================

def draw_polygon_segmentation(
    mask,
    segmentation,
    mask_value
):

    if not isinstance(
        segmentation,
        list
    ):
        return

    for polygon in segmentation:

        if len(polygon) < 6:
            continue

        points = np.array(
            polygon,
            dtype=np.float32
        )

        points = points.reshape(
            -1,
            2
        )

        points = np.round(
            points
        ).astype(
            np.int32
        )

        cv2.fillPoly(
            mask,
            [points],
            int(mask_value)
        )


# =========================================================
# Process one COCO split
# =========================================================

def process_split(
    source_split,
    output_split
):

    print()
    print("===================================")
    print(
        f"Processing {source_split} "
        f"→ {output_split}"
    )
    print("===================================")

    split_dir = os.path.join(
        SOURCE_DIR,
        source_split
    )

    annotation_path = os.path.join(
        split_dir,
        "_annotations.coco.json"
    )

    if not os.path.exists(
        annotation_path
    ):

        raise FileNotFoundError(
            f"Annotation file not found: "
            f"{annotation_path}"
        )

    with open(
        annotation_path,
        "r",
        encoding="utf-8"
    ) as f:

        coco = json.load(
            f
        )

    # -----------------------------------------------------
    # Image lookup
    # -----------------------------------------------------

    images_by_id = {
        image["id"]: image
        for image in coco["images"]
    }

    # -----------------------------------------------------
    # Group annotations by image ID
    # -----------------------------------------------------

    annotations_by_image = {}

    for annotation in coco[
        "annotations"
    ]:

        image_id = annotation[
            "image_id"
        ]

        if image_id not in (
            annotations_by_image
        ):

            annotations_by_image[
                image_id
            ] = []

        annotations_by_image[
            image_id
        ].append(
            annotation
        )

    output_image_dir = os.path.join(
        OUTPUT_DIR,
        output_split,
        "images"
    )

    output_mask_dir = os.path.join(
        OUTPUT_DIR,
        output_split,
        "masks"
    )

    processed_count = 0
    gingivitis_images = 0
    calculus_images = 0
    empty_masks = 0

    # -----------------------------------------------------
    # Process every image
    # -----------------------------------------------------

    for image_id, image_info in (
        images_by_id.items()
    ):

        filename = image_info[
            "file_name"
        ]

        width = int(
            image_info["width"]
        )

        height = int(
            image_info["height"]
        )

        source_image_path = os.path.join(
            split_dir,
            filename
        )

        if not os.path.exists(
            source_image_path
        ):

            print(
                f"Warning: image not found: "
                f"{source_image_path}"
            )

            continue

        # -----------------------------------------
        # Create blank segmentation mask
        # -----------------------------------------

        mask = np.zeros(
            (
                height,
                width
            ),
            dtype=np.uint8
        )

        annotations = (
            annotations_by_image.get(
                image_id,
                []
            )
        )

        has_gingivitis = False
        has_calculus = False

        # -----------------------------------------
        # Draw selected diseases
        # -----------------------------------------

        for annotation in annotations:

            category_id = annotation[
                "category_id"
            ]

            segmentation = annotation.get(
                "segmentation"
            )

            if (
                category_id
                == GINGIVITIS_ID
            ):

                draw_polygon_segmentation(
                    mask,
                    segmentation,
                    GINGIVITIS_VALUE
                )

                has_gingivitis = True

            elif (
                category_id
                == CALCULUS_ID
            ):

                draw_polygon_segmentation(
                    mask,
                    segmentation,
                    CALCULUS_VALUE
                )

                has_calculus = True

        # -----------------------------------------
        # Statistics
        # -----------------------------------------

        if has_gingivitis:
            gingivitis_images += 1

        if has_calculus:
            calculus_images += 1

        if np.max(mask) == 0:
            empty_masks += 1

        # -----------------------------------------
        # Copy original image
        # -----------------------------------------

        destination_image_path = (
            os.path.join(
                output_image_dir,
                filename
            )
        )

        shutil.copy2(
            source_image_path,
            destination_image_path
        )

        # -----------------------------------------
        # Save mask
        # -----------------------------------------

        image_name = os.path.splitext(
            filename
        )[0]

        mask_filename = (
            f"{image_name}.png"
        )

        destination_mask_path = (
            os.path.join(
                output_mask_dir,
                mask_filename
            )
        )

        cv2.imwrite(
            destination_mask_path,
            mask
        )

        processed_count += 1

    # -----------------------------------------------------
    # Split summary
    # -----------------------------------------------------

    print(
        "Processed images:",
        processed_count
    )

    print(
        "Images with gingivitis:",
        gingivitis_images
    )

    print(
        "Images with calculus:",
        calculus_images
    )

    print(
        "Images with empty mask:",
        empty_masks
    )


# =========================================================
# Main
# =========================================================

create_output_folders()

for (
    source_split,
    output_split
) in SPLIT_MAPPING.items():

    process_split(
        source_split,
        output_split
    )


print()
print("===================================")
print("Segmentation dataset completed")
print("===================================")

print(
    "Output directory:"
)

print(
    OUTPUT_DIR
)

print()
print(
    "Mask values:"
)

print(
    "0 = background"
)

print(
    "1 = gingivitis"
)

print(
    "2 = calculus"
)