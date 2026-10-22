import os
import numpy as np
import keras

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SPLIT_DIR = os.path.join(
    BASE_DIR,
    "dental validator split"
)

VAL_DIR = os.path.join(
    SPLIT_DIR,
    "validation"
)

TEST_DIR = os.path.join(
    SPLIT_DIR,
    "test"
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "dental_image_validator.keras"
)

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32


# =========================================================
# Load datasets
# =========================================================

val_ds = keras.utils.image_dataset_from_directory(
    VAL_DIR,
    image_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE,
    label_mode="binary",
    shuffle=False
)

test_ds = keras.utils.image_dataset_from_directory(
    TEST_DIR,
    image_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE,
    label_mode="binary",
    shuffle=False
)

print(
    "\nValidation classes:",
    val_ds.class_names
)

print(
    "Test classes:",
    test_ds.class_names
)


# =========================================================
# Check class order
# =========================================================

EXPECTED_CLASSES = [
    "invalid non dental",
    "valid dental"
]

if val_ds.class_names != EXPECTED_CLASSES:
    raise ValueError(
        f"Unexpected validation class order: "
        f"{val_ds.class_names}"
    )

if test_ds.class_names != EXPECTED_CLASSES:
    raise ValueError(
        f"Unexpected test class order: "
        f"{test_ds.class_names}"
    )


# =========================================================
# Load model
# =========================================================

print(
    "\nLoading validator model..."
)

model = keras.models.load_model(
    MODEL_PATH,
    compile=False
)

print(
    "Model loaded successfully."
)


# =========================================================
# Prediction helper
# =========================================================

def get_predictions(dataset):

    y_true = []
    y_scores = []

    for images, labels in dataset:

        predictions = model.predict(
            images,
            verbose=0
        )

        y_scores.extend(
            predictions.flatten()
        )

        y_true.extend(
            labels.numpy().flatten()
        )

    return (
        np.array(y_true, dtype=int),
        np.array(y_scores)
    )


# =========================================================
# Validation predictions
# =========================================================

print(
    "\n==================================="
)

print(
    "Validation Threshold Tuning"
)

print(
    "==================================="
)

val_y_true, val_scores = get_predictions(
    val_ds
)


# =========================================================
# Find best threshold
# =========================================================

threshold_candidates = np.arange(
    0.10,
    0.91,
    0.05
)

best_threshold = 0.50
best_f1 = -1

for threshold in threshold_candidates:

    val_y_pred = (
        val_scores >= threshold
    ).astype(int)

    f1 = f1_score(
        val_y_true,
        val_y_pred,
        zero_division=0
    )

    print(
        f"Threshold={threshold:.2f} "
        f"F1={f1:.4f}"
    )

    if f1 > best_f1:

        best_f1 = f1
        best_threshold = threshold


print(
    "\nBest threshold:"
)

print(
    f"{best_threshold:.2f}"
)

print(
    f"Validation F1: {best_f1:.4f}"
)


# =========================================================
# Final test predictions
# =========================================================

print(
    "\n==================================="
)

print(
    "FINAL TEST EVALUATION"
)

print(
    "==================================="
)

test_y_true, test_scores = get_predictions(
    test_ds
)

test_y_pred = (
    test_scores >= best_threshold
).astype(int)


# =========================================================
# Metrics
# =========================================================

accuracy = accuracy_score(
    test_y_true,
    test_y_pred
)

precision = precision_score(
    test_y_true,
    test_y_pred,
    zero_division=0
)

recall = recall_score(
    test_y_true,
    test_y_pred,
    zero_division=0
)

f1 = f1_score(
    test_y_true,
    test_y_pred,
    zero_division=0
)

cm = confusion_matrix(
    test_y_true,
    test_y_pred,
    labels=[0, 1]
)


print(
    f"\nThreshold: {best_threshold:.2f}"
)

print(
    f"Accuracy : {accuracy:.4f}"
)

print(
    f"Precision: {precision:.4f}"
)

print(
    f"Recall   : {recall:.4f}"
)

print(
    f"F1 Score : {f1:.4f}"
)


print(
    "\nConfusion Matrix:"
)

print(
    cm
)


print(
    "\nClassification Report:"
)

print(
    classification_report(
        test_y_true,
        test_y_pred,
        target_names=[
            "Invalid / Non-dental",
            "Valid Pet Dental"
        ],
        zero_division=0
    )
)


# =========================================================
# Misclassified images
# =========================================================

print(
    "\n==================================="
)

print(
    "Misclassified Images"
)

print(
    "==================================="
)

file_paths = test_ds.file_paths

error_count = 0

for (
    path,
    true_label,
    predicted_label,
    score
) in zip(
    file_paths,
    test_y_true,
    test_y_pred,
    test_scores
):

    if true_label != predicted_label:

        error_count += 1

        print(
            f"\nImage: {path}"
        )

        print(
            f"True label: {true_label}"
        )

        print(
            f"Predicted label: "
            f"{predicted_label}"
        )

        print(
            f"Dental probability: "
            f"{score:.4f}"
        )


if error_count == 0:

    print(
        "\nNo misclassified test images."
    )

else:

    print(
        f"\nTotal misclassified images: "
        f"{error_count}"
    )


print(
    "\n==================================="
)

print(
    "Evaluation completed"
)

print(
    "==================================="
)