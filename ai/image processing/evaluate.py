import os
import numpy as np
import pandas as pd
import tensorflow as tf

from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    confusion_matrix
)

# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.join(BASE_DIR, "fyp final dataset")
IMAGE_DIR = os.path.join(DATASET_DIR, "images")
CSV_PATH = os.path.join(DATASET_DIR, "labels_split.csv")

MODEL_PATH = os.path.join(BASE_DIR, "models", "dental_classifier.keras")

IMAGE_SIZE = (224, 224)

LABELS = [
    "healthy",
    "plaque",
    "gingivitis",
    "calculus"
]

MASK_COLUMNS = [
    "mask_healthy",
    "mask_plaque",
    "mask_gingivitis",
    "mask_calculus"
]


# =========================================================
# Load model
# =========================================================

print("\n===================================")
print("Loading trained model")
print("===================================")

model = tf.keras.models.load_model(
    MODEL_PATH,
    compile=False
)

print("Model loaded successfully.")
print("Model path:", MODEL_PATH)


# =========================================================
# Load dataset CSV
# =========================================================

print("\n===================================")
print("Loading dataset information")
print("===================================")

df = pd.read_csv(CSV_PATH)

print("Total records:", len(df))
print(df["split"].value_counts())


# =========================================================
# Image preprocessing
# =========================================================

def load_image(filename):
    image_path = os.path.join(IMAGE_DIR, filename)

    image = tf.io.read_file(image_path)
    image = tf.image.decode_image(
        image,
        channels=3,
        expand_animations=False
    )

    image = tf.image.resize(image, IMAGE_SIZE)
    image = tf.cast(image, tf.float32)

    # IMPORTANT:
    # Keep range 0-255 because Keras EfficientNetB0
    # already contains its own internal rescaling.

    return image


# =========================================================
# Predict a dataframe split
# =========================================================

def predict_split(split_df):
    images = []

    for filename in split_df["filename"]:
        image = load_image(filename)
        images.append(image)

    images = tf.stack(images)

    predictions = model.predict(
        images,
        batch_size=32,
        verbose=1
    )

    labels = split_df[LABELS].values.astype(np.float32)
    masks = split_df[MASK_COLUMNS].values.astype(np.float32)

    return labels, masks, predictions


# =========================================================
# Separate validation and test data
# =========================================================

validation_df = df[df["split"] == "validation"].reset_index(drop=True)
test_df = df[df["split"] == "test"].reset_index(drop=True)

print("\nValidation samples:", len(validation_df))
print("Test samples:", len(test_df))


# =========================================================
# Validation predictions
# =========================================================

print("\n===================================")
print("Predicting validation set")
print("===================================")

val_y_true, val_masks, val_predictions = predict_split(validation_df)


# =========================================================
# Find best threshold for each condition
# =========================================================

print("\n===================================")
print("Threshold tuning")
print("===================================")

threshold_candidates = np.arange(0.10, 0.91, 0.05)

best_thresholds = []

for i, label in enumerate(LABELS):

    known = val_masks[:, i] == 1

    y_true = val_y_true[known, i]
    y_prob = val_predictions[known, i]

    best_threshold = 0.50
    best_f1 = -1

    for threshold in threshold_candidates:

        y_pred = (y_prob >= threshold).astype(int)

        score = f1_score(
            y_true,
            y_pred,
            zero_division=0
        )

        if score > best_f1:
            best_f1 = score
            best_threshold = threshold

    best_thresholds.append(best_threshold)

    positive_count = int(np.sum(y_true))
    negative_count = int(len(y_true) - positive_count)

    print(
        f"{label:<12} "
        f"threshold={best_threshold:.2f} "
        f"validation_F1={best_f1:.4f} "
        f"positive={positive_count} "
        f"negative={negative_count}"
    )


# =========================================================
# Test predictions
# =========================================================

print("\n===================================")
print("Predicting test set")
print("===================================")

test_y_true, test_masks, test_predictions = predict_split(test_df)


# =========================================================
# Per-condition evaluation
# =========================================================

print("\n===================================")
print("FINAL TEST RESULTS")
print("===================================")

results = []

for i, label in enumerate(LABELS):

    known = test_masks[:, i] == 1

    y_true = test_y_true[known, i]
    y_prob = test_predictions[known, i]

    threshold = best_thresholds[i]

    y_pred = (y_prob >= threshold).astype(int)

    precision = precision_score(
        y_true,
        y_pred,
        zero_division=0
    )

    recall = recall_score(
        y_true,
        y_pred,
        zero_division=0
    )

    f1 = f1_score(
        y_true,
        y_pred,
        zero_division=0
    )

    accuracy = accuracy_score(
        y_true,
        y_pred
    )

    positive_support = int(np.sum(y_true))
    known_support = len(y_true)

    results.append({
        "condition": label,
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "accuracy": accuracy,
        "positive_support": positive_support,
        "known_samples": known_support
    })

    print(f"\nCondition: {label}")
    print(f"Threshold: {threshold:.2f}")
    print(f"Known samples: {known_support}")
    print(f"Positive samples: {positive_support}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1-score:  {f1:.4f}")
    print(f"Accuracy:  {accuracy:.4f}")

    print("Confusion Matrix:")
    print(
        confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1]
        )
    )

# =========================================================
# Species-wise evaluation
# =========================================================

print("\n===================================")
print("SPECIES-WISE TEST RESULTS")
print("===================================")

species_list = ["cat", "dog"]

for species in species_list:

    print(f"\n========== {species.upper()} ==========")

    species_df = test_df[
        test_df["species"].str.lower() == species
    ].reset_index(drop=True)

    if len(species_df) == 0:
        print("No samples found.")
        continue

    species_y_true, species_masks, species_predictions = predict_split(species_df)

    for i, label in enumerate(LABELS):

        known = species_masks[:, i] == 1

        # Skip unsupported / unknown labels
        if np.sum(known) == 0:
            print(f"\nCondition: {label}")
            print("Not supported / no known labels for this species.")
            continue

        y_true = species_y_true[known, i]
        y_prob = species_predictions[known, i]

        threshold = best_thresholds[i]

        y_pred = (y_prob >= threshold).astype(int)

        precision = precision_score(
            y_true,
            y_pred,
            zero_division=0
        )

        recall = recall_score(
            y_true,
            y_pred,
            zero_division=0
        )

        f1 = f1_score(
            y_true,
            y_pred,
            zero_division=0
        )

        accuracy = accuracy_score(
            y_true,
            y_pred
        )

        positive_support = int(np.sum(y_true))
        known_support = len(y_true)

        print(f"\nCondition: {label}")
        print(f"Threshold: {threshold:.2f}")
        print(f"Known samples: {known_support}")
        print(f"Positive samples: {positive_support}")
        print(f"Precision: {precision:.4f}")
        print(f"Recall:    {recall:.4f}")
        print(f"F1-score:  {f1:.4f}")
        print(f"Accuracy:  {accuracy:.4f}")

# =========================================================
# Save evaluation results
# =========================================================

results_df = pd.DataFrame(results)

OUTPUT_PATH = os.path.join(
    BASE_DIR,
    "models",
    "evaluation_results.csv"
)

results_df.to_csv(
    OUTPUT_PATH,
    index=False
)

print("\n===================================")
print("Evaluation completed")
print("===================================")

print(results_df.to_string(index=False))

print("\nResults saved to:")
print(OUTPUT_PATH)