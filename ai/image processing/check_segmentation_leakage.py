import os
import re
from collections import defaultdict


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATASET_DIR = os.path.join(
    BASE_DIR,
    "segmentation grouped split"
)

SPLITS = [
    "train",
    "validation",
    "test"
]


def get_original_name(filename):

    name = os.path.splitext(
        filename
    )[0]

    # Remove Roboflow generated hash
    # Example:
    # 11A_jpg.rf.075bb51c4d0a1f0f26a2c030a7e3acd8
    #
    # becomes:
    # 11A_jpg

    name = re.sub(
        r"\.rf\.[a-fA-F0-9]+$",
        "",
        name
    )

    return name


# =========================================================
# Collect originals by split
# =========================================================

split_originals = {}

for split_name in SPLITS:

    image_dir = os.path.join(
        DATASET_DIR,
        split_name,
        "images"
    )

    originals = defaultdict(
        list
    )

    for filename in os.listdir(
        image_dir
    ):

        if not filename.lower().endswith(
            (
                ".jpg",
                ".jpeg",
                ".png"
            )
        ):
            continue

        original_name = get_original_name(
            filename
        )

        originals[
            original_name
        ].append(
            filename
        )

    split_originals[
        split_name
    ] = originals


# =========================================================
# Basic information
# =========================================================

for split_name in SPLITS:

    originals = split_originals[
        split_name
    ]

    total_files = sum(
        len(files)
        for files in originals.values()
    )

    print()
    print(
        "==================================="
    )

    print(
        split_name.upper()
    )

    print(
        "==================================="
    )

    print(
        "Files:",
        total_files
    )

    print(
        "Unique original images:",
        len(originals)
    )


# =========================================================
# Check overlap
# =========================================================

def check_overlap(
    split_a,
    split_b
):

    originals_a = set(
        split_originals[
            split_a
        ].keys()
    )

    originals_b = set(
        split_originals[
            split_b
        ].keys()
    )

    overlap = sorted(
        originals_a.intersection(
            originals_b
        )
    )

    print()
    print(
        f"{split_a} ↔ {split_b}"
    )

    print(
        "Overlapping originals:",
        len(overlap)
    )

    if overlap:

        print()
        print(
            "Examples:"
        )

        for original in overlap[:20]:

            print()
            print(
                original
            )

            print(
                f"  {split_a}:"
            )

            for f in split_originals[
                split_a
            ][original]:

                print(
                    f"    {f}"
                )

            print(
                f"  {split_b}:"
            )

            for f in split_originals[
                split_b
            ][original]:

                print(
                    f"    {f}"
                )


print()
print(
    "==================================="
)
print(
    "DATA LEAKAGE CHECK"
)
print(
    "==================================="
)

check_overlap(
    "train",
    "validation"
)

check_overlap(
    "train",
    "test"
)

check_overlap(
    "validation",
    "test"
)