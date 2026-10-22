import os
import random
import shutil

# source
SOURCE_DIR = r"C:\Users\USER\Downloads\images\images"

DEST_DIR = r"C:\Users\USER\OneDrive\Documents\GitHub\fyp\ai\image processing\dental_validator_dataset\invalid_non_dental"

NUM_IMAGES = 1500
SEED = 42

random.seed(SEED)

os.makedirs(DEST_DIR, exist_ok=True)

valid_extensions = (
    ".jpg",
    ".jpeg",
    ".png"
)

all_images = [
    f for f in os.listdir(SOURCE_DIR)
    if f.lower().endswith(valid_extensions)
]

print("Total source images:", len(all_images))

if len(all_images) < NUM_IMAGES:
    selected_images = all_images
else:
    selected_images = random.sample(
        all_images,
        NUM_IMAGES
    )

for filename in selected_images:
    source_path = os.path.join(
        SOURCE_DIR,
        filename
    )

    dest_path = os.path.join(
        DEST_DIR,
        filename
    )

    shutil.copy2(
        source_path,
        dest_path
    )

print(
    f"Copied {len(selected_images)} images."
)

print(
    "Destination:",
    DEST_DIR
)