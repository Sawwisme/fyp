import os
import random
import shutil

# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SOURCE_DIR = os.path.join(
    BASE_DIR,
    "dental validator dataset"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "dental validator split"
)

CLASSES = [
    "invalid non dental",
    "valid dental"
]

TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10

SEED = 42

VALID_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
)

random.seed(SEED)


# =========================================================
# Remove old split folder if it exists
# =========================================================

if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)


# =========================================================
# Create folders
# =========================================================

for split in [
    "train",
    "validation",
    "test"
]:

    for class_name in CLASSES:

        folder = os.path.join(
            OUTPUT_DIR,
            split,
            class_name
        )

        os.makedirs(
            folder,
            exist_ok=True
        )


# =========================================================
# Split each class
# =========================================================

for class_name in CLASSES:

    class_dir = os.path.join(
        SOURCE_DIR,
        class_name
    )

    if not os.path.exists(class_dir):
        raise FileNotFoundError(
            f"Class folder not found: {class_dir}"
        )

    images = []

    # -----------------------------------------------------
    # Search recursively
    # -----------------------------------------------------

    for root, dirs, files in os.walk(
        class_dir
    ):

        for filename in files:

            if filename.lower().endswith(
                VALID_EXTENSIONS
            ):

                full_path = os.path.join(
                    root,
                    filename
                )

                images.append(
                    full_path
                )

    # -----------------------------------------------------
    # Shuffle after collecting all images
    # -----------------------------------------------------

    random.shuffle(
        images
    )

    total = len(images)

    train_count = int(
        total * TRAIN_RATIO
    )

    val_count = int(
        total * VAL_RATIO
    )

    train_images = images[
        :train_count
    ]

    val_images = images[
        train_count:
        train_count + val_count
    ]

    test_images = images[
        train_count + val_count:
    ]

    print()
    print("==============================")
    print(class_name)
    print("==============================")

    print(
        "Total:",
        total
    )

    print(
        "Train:",
        len(train_images)
    )

    print(
        "Validation:",
        len(val_images)
    )

    print(
        "Test:",
        len(test_images)
    )

    # -----------------------------------------------------
    # Copy images
    # -----------------------------------------------------

    split_groups = {
        "train": train_images,
        "validation": val_images,
        "test": test_images
    }

    for split_name, source_paths in split_groups.items():

        destination_dir = os.path.join(
            OUTPUT_DIR,
            split_name,
            class_name
        )

        for index, source_path in enumerate(
            source_paths
        ):

            filename = os.path.basename(
                source_path
            )

            destination_path = os.path.join(
                destination_dir,
                filename
            )

            # Prevent accidental overwrite if two source
            # folders contain files with the same filename
            if os.path.exists(
                destination_path
            ):

                name, extension = os.path.splitext(
                    filename
                )

                destination_path = os.path.join(
                    destination_dir,
                    f"{name}_{index}{extension}"
                )

            shutil.copy2(
                source_path,
                destination_path
            )


# =========================================================
# Finished
# =========================================================

print()
print("===================================")
print("Dataset split completed")
print("===================================")

print(
    "Output:"
)

print(
    OUTPUT_DIR
)