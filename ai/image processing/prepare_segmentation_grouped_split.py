import os
import re
import random
import shutil
from collections import defaultdict

import cv2
import numpy as np


# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SOURCE_DIR = os.path.join(
    BASE_DIR,
    "segmentation dataset"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "segmentation grouped split"
)

SEED = 42

TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10

VALID_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png"
)

random.seed(SEED)


# =========================================================
# Helper: get original image name
# =========================================================

def get_original_name(filename):

    name = os.path.splitext(
        filename
    )[0]

    name = re.sub(
        r"\.rf\.[a-fA-F0-9]+$",
        "",
        name
    )

    return name


# =========================================================
# Clean output
# =========================================================

if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)


for split_name in [
    "train",
    "validation",
    "test"
]:

    os.makedirs(
        os.path.join(
            OUTPUT_DIR,
            split_name,
            "images"
        ),
        exist_ok=True
    )

    os.makedirs(
        os.path.join(
            OUTPUT_DIR,
            split_name,
            "masks"
        ),
        exist_ok=True
    )


# =========================================================
# Collect all image-mask pairs
# =========================================================

groups = defaultdict(list)

for source_split in [
    "train",
    "validation",
    "test"
]:

    image_dir = os.path.join(
        SOURCE_DIR,
        source_split,
        "images"
    )

    mask_dir = os.path.join(
        SOURCE_DIR,
        source_split,
        "masks"
    )

    if not os.path.exists(image_dir):
        continue

    for filename in os.listdir(image_dir):

        if not filename.lower().endswith(
            VALID_EXTENSIONS
        ):
            continue

        image_path = os.path.join(
            image_dir,
            filename
        )

        stem = os.path.splitext(
            filename
        )[0]

        mask_path = os.path.join(
            mask_dir,
            f"{stem}.png"
        )

        if not os.path.exists(mask_path):
            continue

        original_name = get_original_name(
            filename
        )

        groups[
            original_name
        ].append(
            {
                "filename": filename,
                "image_path": image_path,
                "mask_path": mask_path
            }
        )


# =========================================================
# Determine group category
# =========================================================

group_records = []

for original_name, samples in groups.items():

    has_gingivitis = False
    has_calculus = False

    for sample in samples:

        mask = cv2.imread(
            sample["mask_path"],
            cv2.IMREAD_GRAYSCALE
        )

        if mask is None:
            continue

        if np.any(mask == 1):
            has_gingivitis = True

        if np.any(mask == 2):
            has_calculus = True

    if has_gingivitis and has_calculus:
        category = "both"

    elif has_gingivitis:
        category = "gingivitis_only"

    elif has_calculus:
        category = "calculus_only"

    else:
        category = "background"

    group_records.append(
        {
            "original_name": original_name,
            "samples": samples,
            "category": category
        }
    )


# =========================================================
# Group by category
# =========================================================

category_groups = {
    "both": [],
    "gingivitis_only": [],
    "calculus_only": [],
    "background": []
}

for record in group_records:

    category_groups[
        record["category"]
    ].append(
        record
    )


# =========================================================
# Split grouped originals
# =========================================================

split_groups = {
    "train": [],
    "validation": [],
    "test": []
}

for category, records in category_groups.items():

    random.shuffle(records)

    total = len(records)

    train_count = int(
        total * TRAIN_RATIO
    )

    val_count = int(
        total * VAL_RATIO
    )

    train_records = records[
        :train_count
    ]

    val_records = records[
        train_count:
        train_count + val_count
    ]

    test_records = records[
        train_count + val_count:
    ]

    split_groups[
        "train"
    ].extend(
        train_records
    )

    split_groups[
        "validation"
    ].extend(
        val_records
    )

    split_groups[
        "test"
    ].extend(
        test_records
    )

    print()
    print("==============================")
    print(category)
    print("==============================")

    print(
        "Unique originals:",
        total
    )

    print(
        "Train originals:",
        len(train_records)
    )

    print(
        "Validation originals:",
        len(val_records)
    )

    print(
        "Test originals:",
        len(test_records)
    )


# =========================================================
# Copy files
# =========================================================

file_counts = {
    "train": 0,
    "validation": 0,
    "test": 0
}

for split_name, records in split_groups.items():

    random.shuffle(records)

    image_output_dir = os.path.join(
        OUTPUT_DIR,
        split_name,
        "images"
    )

    mask_output_dir = os.path.join(
        OUTPUT_DIR,
        split_name,
        "masks"
    )

    for record in records:

        for sample in record[
            "samples"
        ]:

            image_destination = os.path.join(
                image_output_dir,
                sample["filename"]
            )

            stem = os.path.splitext(
                sample["filename"]
            )[0]

            mask_destination = os.path.join(
                mask_output_dir,
                f"{stem}.png"
            )

            shutil.copy2(
                sample["image_path"],
                image_destination
            )

            shutil.copy2(
                sample["mask_path"],
                mask_destination
            )

            file_counts[
                split_name
            ] += 1


# =========================================================
# Final summary
# =========================================================

print()
print("===================================")
print("GROUPED SEGMENTATION SPLIT COMPLETE")
print("===================================")

print(
    "Unique original groups:",
    len(group_records)
)

print()

for split_name in [
    "train",
    "validation",
    "test"
]:

    print(
        f"{split_name}: "
        f"{len(split_groups[split_name])} originals, "
        f"{file_counts[split_name]} files"
    )

print()

print(
    "Output directory:"
)

print(
    OUTPUT_DIR
)