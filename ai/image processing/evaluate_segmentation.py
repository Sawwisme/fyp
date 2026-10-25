import os
import numpy as np
import tensorflow as tf
import keras
import cv2

# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

TEST_IMAGE_DIR = os.path.join(
    BASE_DIR,
    "segmentation grouped split",
    "test",
    "images"
)

TEST_MASK_DIR = os.path.join(
    BASE_DIR,
    "segmentation grouped split",
    "test",
    "masks"
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "dental_segmentation_unet_ce.keras"
)

IMAGE_SIZE = (256, 256)

NUM_CLASSES = 3

CLASS_NAMES = {
    0: "background",
    1: "gingivitis",
    2: "calculus"
}


# =========================================================
# Load model
# =========================================================

print("\n===================================")
print("Loading segmentation model")
print("===================================")

model = keras.models.load_model(
    MODEL_PATH,
    compile=False
)

print("Model loaded successfully.")


# =========================================================
# Get test pairs
# =========================================================

def get_file_pairs():

    pairs = []

    for filename in sorted(
        os.listdir(TEST_IMAGE_DIR)
    ):

        if not filename.lower().endswith(
            (".jpg", ".jpeg", ".png")
        ):
            continue

        image_path = os.path.join(
            TEST_IMAGE_DIR,
            filename
        )

        name = os.path.splitext(
            filename
        )[0]

        mask_path = os.path.join(
            TEST_MASK_DIR,
            f"{name}.png"
        )

        if os.path.exists(mask_path):

            pairs.append(
                (
                    image_path,
                    mask_path,
                    filename
                )
            )

    return pairs


pairs = get_file_pairs()

print(
    "Test samples:",
    len(pairs)
)


# =========================================================
# Load image
# =========================================================

def load_image(
    image_path
):

    image = tf.io.read_file(
        image_path
    )

    image = tf.image.decode_image(
        image,
        channels=3,
        expand_animations=False
    )

    image = tf.image.resize(
        image,
        IMAGE_SIZE
    )

    image = tf.cast(
        image,
        tf.float32
    ) / 255.0

    return image


# =========================================================
# Load mask
# =========================================================

def load_mask(
    mask_path
):

    mask = cv2.imread(
        mask_path,
        cv2.IMREAD_GRAYSCALE
    )

    mask = cv2.resize(
        mask,
        IMAGE_SIZE,
        interpolation=cv2.INTER_NEAREST
    )

    return mask.astype(
        np.int32
    )


# =========================================================
# Dice and IoU
# =========================================================

def dice_score(
    y_true,
    y_pred,
    class_id
):

    true_mask = (
        y_true == class_id
    )

    pred_mask = (
        y_pred == class_id
    )

    intersection = np.logical_and(
        true_mask,
        pred_mask
    ).sum()

    denominator = (
        true_mask.sum()
        + pred_mask.sum()
    )

    if denominator == 0:
        return None

    return (
        2.0 * intersection
        / denominator
    )


def iou_score(
    y_true,
    y_pred,
    class_id
):

    true_mask = (
        y_true == class_id
    )

    pred_mask = (
        y_pred == class_id
    )

    intersection = np.logical_and(
        true_mask,
        pred_mask
    ).sum()

    union = np.logical_or(
        true_mask,
        pred_mask
    ).sum()

    if union == 0:
        return None

    return (
        intersection
        / union
    )


# =========================================================
# Evaluation
# =========================================================

dice_results = {
    0: [],
    1: [],
    2: []
}

iou_results = {
    0: [],
    1: [],
    2: []
}

pixel_correct = 0
pixel_total = 0


print("\n===================================")
print("Evaluating test set")
print("===================================")

for index, (
    image_path,
    mask_path,
    filename
) in enumerate(pairs):

    image = load_image(
        image_path
    )

    input_image = tf.expand_dims(
        image,
        axis=0
    )

    prediction = model.predict(
        input_image,
        verbose=0
    )[0]

    predicted_mask = np.argmax(
        prediction,
        axis=-1
    ).astype(
        np.int32
    )

    true_mask = load_mask(
        mask_path
    )

    pixel_correct += np.sum(
        predicted_mask
        == true_mask
    )

    pixel_total += true_mask.size

    for class_id in range(
        NUM_CLASSES
    ):

        dice = dice_score(
            true_mask,
            predicted_mask,
            class_id
        )

        iou = iou_score(
            true_mask,
            predicted_mask,
            class_id
        )

        if dice is not None:
            dice_results[
                class_id
            ].append(
                dice
            )

        if iou is not None:
            iou_results[
                class_id
            ].append(
                iou
            )

    print(
        f"Processed "
        f"{index + 1}/{len(pairs)}: "
        f"{filename}"
    )


# =========================================================
# Final results
# =========================================================

pixel_accuracy = (
    pixel_correct
    / pixel_total
)

print()
print("===================================")
print("FINAL SEGMENTATION TEST RESULTS")
print("===================================")

print(
    f"Pixel Accuracy: "
    f"{pixel_accuracy:.4f}"
)

class_dice_scores = []
class_iou_scores = []

for class_id in range(
    NUM_CLASSES
):

    dice_values = dice_results[
        class_id
    ]

    iou_values = iou_results[
        class_id
    ]

    mean_dice = (
        np.mean(dice_values)
        if len(dice_values) > 0
        else 0
    )

    mean_iou = (
        np.mean(iou_values)
        if len(iou_values) > 0
        else 0
    )

    class_dice_scores.append(
        mean_dice
    )

    class_iou_scores.append(
        mean_iou
    )

    print()
    print(
        f"Class: "
        f"{CLASS_NAMES[class_id]}"
    )

    print(
        f"Dice: "
        f"{mean_dice:.4f}"
    )

    print(
        f"IoU : "
        f"{mean_iou:.4f}"
    )

    print(
        f"Evaluated samples: "
        f"{len(dice_values)}"
    )


# =========================================================
# Foreground average
# =========================================================

foreground_dice = np.mean(
    [
        class_dice_scores[1],
        class_dice_scores[2]
    ]
)

foreground_iou = np.mean(
    [
        class_iou_scores[1],
        class_iou_scores[2]
    ]
)

print()
print("===================================")
print("Foreground Performance")
print("===================================")

print(
    f"Mean Disease Dice: "
    f"{foreground_dice:.4f}"
)

print(
    f"Mean Disease IoU : "
    f"{foreground_iou:.4f}"
)

print()
print("Evaluation completed.")