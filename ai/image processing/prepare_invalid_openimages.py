import os
import shutil
import fiftyone.zoo as foz

DEST_DIR = r"C:\Users\USER\OneDrive\Documents\GitHub\fyp\ai\image processing\dental validator dataset\invalid non dental"

os.makedirs(DEST_DIR, exist_ok=True)

classes = [
    "Car",
    "Chair",
    "Food",
    "Tree",
    "House",
    "Bottle"
]

dataset = foz.load_zoo_dataset(
    "open-images-v6",
    split="validation",
    label_types=["detections"],
    classes=classes,
    max_samples=300,
    shuffle=True,
    seed=42
)

count = 0

for sample in dataset:
    source_path = sample.filepath

    filename = os.path.basename(source_path)
    new_filename = f"openimages_{count}_{filename}"

    dest_path = os.path.join(
        DEST_DIR,
        new_filename
    )

    shutil.copy2(
        source_path,
        dest_path
    )

    count += 1

print(f"Copied {count} Open Images samples.")
print("Destination:", DEST_DIR)