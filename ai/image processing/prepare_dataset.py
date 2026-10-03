from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

# Current file location
BASE_DIR = Path(__file__).resolve().parent

# Dataset paths
DATASET_DIR = BASE_DIR / "fyp final dataset"
IMAGES_DIR = DATASET_DIR / "images"
LABELS_FILE = DATASET_DIR / "labels.csv"

# Output file
OUTPUT_FILE = DATASET_DIR / "labels_split.csv"


# 1. Load labels.csv
df = pd.read_csv(LABELS_FILE)

print("Total records:", len(df))
print("Columns:")
print(df.columns.tolist())


# 2. Check whether images exist
def image_exists(filename):
    return (IMAGES_DIR / filename).exists()


df["image_exists"] = df["filename"].apply(image_exists)

missing = df[df["image_exists"] == False]

print("\nMissing images:", len(missing))

if len(missing) > 0:
    print(missing[["filename"]].head(20))
else:
    print("All images found successfully.")


# Stop if there are missing images
if len(missing) > 0:
    raise FileNotFoundError(
        "Some images listed in labels.csv are missing. "
        "Please fix them before splitting the dataset."
    )


# 3. Create stratification helper
# Combine species + positive labels
df["stratify_group"] = (
    df["species"].astype(str)
    + "_H" + df["healthy"].astype(str)
    + "_P" + df["plaque"].astype(str)
    + "_G" + df["gingivitis"].astype(str)
    + "_C" + df["calculus"].astype(str)
)


# Some combinations may have only 1 image.
# Those cannot be used directly with sklearn stratify.
group_counts = df["stratify_group"].value_counts()

rare_groups = group_counts[group_counts < 2].index

df.loc[
    df["stratify_group"].isin(rare_groups),
    "stratify_group"
] = df.loc[
    df["stratify_group"].isin(rare_groups),
    "species"
]


# 4. First split:
# 70% train
# 30% temporary
train_df, temp_df = train_test_split(
    df,
    test_size=0.30,
    random_state=42,
    stratify=df["stratify_group"]
)


# 5. Split temporary data equally:
# 15% validation
# 15% test
temp_counts = temp_df["stratify_group"].value_counts()

rare_temp_groups = temp_counts[temp_counts < 2].index

temp_df.loc[
    temp_df["stratify_group"].isin(rare_temp_groups),
    "stratify_group"
] = temp_df.loc[
    temp_df["stratify_group"].isin(rare_temp_groups),
    "species"
]


val_df, test_df = train_test_split(
    temp_df,
    test_size=0.50,
    random_state=42,
    stratify=temp_df["stratify_group"]
)


# 6. Add split column
train_df["split"] = "train"
val_df["split"] = "validation"
test_df["split"] = "test"


# 7. Combine
final_df = pd.concat(
    [train_df, val_df, test_df],
    ignore_index=True
)


# Remove helper columns
final_df = final_df.drop(
    columns=["image_exists", "stratify_group"]
)


# 8. Save
final_df.to_csv(
    OUTPUT_FILE,
    index=False
)


print("\nDataset split completed.")
print(final_df["split"].value_counts())

print("\nSaved to:")
print(OUTPUT_FILE)


# 9. Show condition distribution
labels = [
    "healthy",
    "plaque",
    "gingivitis",
    "calculus"
]

print("\nPositive labels by split:")

for split_name in ["train", "validation", "test"]:
    subset = final_df[final_df["split"] == split_name]

    print(f"\n{split_name.upper()}")
    print("Total:", len(subset))

    for label in labels:
        print(
            f"{label}:",
            int(subset[label].sum())
        )

# 10. Show distribution by species
print("\n==============================")
print("POSITIVE LABELS BY SPECIES")
print("==============================")

for split_name in ["train", "validation", "test"]:

    print(f"\n{split_name.upper()}")

    subset = final_df[
        final_df["split"] == split_name
    ]

    for species_name in ["cat", "dog"]:

        species_df = subset[
            subset["species"].str.lower() == species_name
        ]

        print(f"\n{species_name.upper()}")
        print("Total:", len(species_df))

        for label in labels:

            mask_column = f"mask_{label}"

            # Only count labels that are actually known
            known_df = species_df[
                species_df[mask_column] == 1
            ]

            positives = int(
                known_df[label].sum()
            )

            print(
                f"{label}: "
                f"{positives} positive / "
                f"{len(known_df)} known"
            )