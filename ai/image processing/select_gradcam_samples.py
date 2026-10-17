import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_PATH = os.path.join(
    BASE_DIR,
    "fyp final dataset",
    "labels_split.csv"
)

df = pd.read_csv(CSV_PATH)

test_df = df[df["split"] == "test"].copy()

conditions = [
    ("healthy", "mask_healthy"),
    ("plaque", "mask_plaque"),
    ("gingivitis", "mask_gingivitis"),
    ("calculus", "mask_calculus"),
]

print("\nRepresentative test samples:\n")

for condition, mask_column in conditions:

    subset = test_df[
        (test_df[condition] == 1) &
        (test_df[mask_column] == 1)
    ]

    if len(subset) == 0:
        print(f"{condition}: No valid test sample found")
        continue

    sample = subset.iloc[0]

    print(
        f"{condition:<12} "
        f"filename={sample['filename']} "
        f"species={sample['species']}"
    )