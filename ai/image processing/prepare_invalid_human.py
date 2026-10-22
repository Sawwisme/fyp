import os
import random
import shutil

SOURCE_DIR = r"C:\Users\USER\Downloads\img_align_celeba\img_align_celeba"

DEST_DIR = r"C:\Users\USER\OneDrive\Documents\GitHub\fyp\ai\image processing\dental validator dataset\invalid non dental"

NUM_IMAGES = 200
SEED = 42

random.seed(SEED)

os.makedirs(DEST_DIR, exist_ok=True)

valid_extensions = (
    ".jpg",
    ".jpeg",
    ".png"
)

all_images = []

for root, dirs, files in os.walk(SOURCE_DIR):
    for filename in files:
        if filename.lower().endswith(valid_extensions):
            all_images.append(
                os.path.join(root, filename)
            )

print("Total source images:", len(all_images))

if len(all_images) == 0:
    print("No images found. Check SOURCE_DIR.")
    exit()

selected_images = random.sample(
    all_images,
    min(NUM_IMAGES, len(all_images))
)

for source_path in selected_images:

    filename = os.path.basename(source_path)

    # Add prefix to avoid duplicate filenames
    new_filename = f"human_{filename}"

    dest_path = os.path.join(
        DEST_DIR,
        new_filename
    )

    shutil.copy2(
        source_path,
        dest_path
    )

print(
    f"Copied {len(selected_images)} human face images."
)

print(
    "Destination:",
    DEST_DIR
)