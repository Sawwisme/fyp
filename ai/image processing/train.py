from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf

from preprocessing import (
    get_datasets,
    LABEL_COLUMNS,
    LABELS_FILE
)


# ============================================================
# 1. SETTINGS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

BEST_MODEL_PATH = MODEL_DIR / "dental_classifier.keras"

NUM_CLASSES = 4

INITIAL_EPOCHS = 15
FINE_TUNE_EPOCHS = 10

INITIAL_LEARNING_RATE = 1e-3
FINE_TUNE_LEARNING_RATE = 1e-5


# ============================================================
# 2. PREPARE LABEL + MASK FORMAT FOR TRAINING
# ============================================================

def pack_dataset(dataset):
    """
    preprocessing.py currently returns:

    image, labels, masks

    Keras training will use:

    image,
    [labels + masks]

    Example:
    labels = [0, 1, 1, 0]
    masks  = [1, 1, 1, 0]

    packed =
    [0, 1, 1, 0, 1, 1, 1, 0]
    """

    return dataset.map(
        lambda images, labels, masks: (
            images,
            tf.concat([labels, masks], axis=1)
        ),
        num_parallel_calls=tf.data.AUTOTUNE
    )


# ============================================================
# 3. CALCULATE CLASS WEIGHTS
# ============================================================

def calculate_positive_weights():
    """
    Calculate positive-class weights using only
    labels where mask = 1.

    This helps with class imbalance.
    """

    df = pd.read_csv(LABELS_FILE)

    train_df = df[
        df["split"] == "train"
    ].copy()

    weights = []

    print("\nPositive class weights:")

    for label in LABEL_COLUMNS:

        mask_col = f"mask_{label}"

        known = train_df[
            train_df[mask_col] == 1
        ]

        positive = int(
            known[label].sum()
        )

        negative = len(known) - positive

        if positive == 0:
            weight = 1.0
        else:
            weight = negative / positive

        # Avoid extreme weight values
        weight = max(1.0, float(weight))

        weights.append(weight)

        print(
            f"{label}: "
            f"positive={positive}, "
            f"negative={negative}, "
            f"weight={weight:.3f}"
        )

    return tf.constant(
        weights,
        dtype=tf.float32
    )


POSITIVE_WEIGHTS = calculate_positive_weights()


# ============================================================
# 4. MASKED WEIGHTED BINARY CROSS ENTROPY
# ============================================================

def masked_weighted_binary_crossentropy(y_true, y_pred):
    """
    y_true contains:

    first 4 values:
    [healthy, plaque, gingivitis, calculus]

    next 4 values:
    [mask_healthy, mask_plaque,
     mask_gingivitis, mask_calculus]

    mask = 1:
        include in loss

    mask = 0:
        ignore
    """

    labels = y_true[:, :NUM_CLASSES]
    masks = y_true[:, NUM_CLASSES:]

    y_pred = tf.clip_by_value(
        y_pred,
        tf.keras.backend.epsilon(),
        1.0 - tf.keras.backend.epsilon()
    )

    positive_loss = (
        -labels
        * tf.math.log(y_pred)
        * POSITIVE_WEIGHTS
    )

    negative_loss = (
        -(1.0 - labels)
        * tf.math.log(1.0 - y_pred)
    )

    loss = positive_loss + negative_loss

    # Ignore unknown labels
    loss = loss * masks

    total_known_labels = tf.reduce_sum(masks)

    return tf.reduce_sum(loss) / (
        total_known_labels
        + tf.keras.backend.epsilon()
    )


# ============================================================
# 5. MASKED METRICS
# ============================================================

def masked_binary_accuracy(y_true, y_pred):

    labels = y_true[:, :NUM_CLASSES]
    masks = y_true[:, NUM_CLASSES:]

    predictions = tf.cast(
        y_pred >= 0.5,
        tf.float32
    )

    correct = tf.cast(
        tf.equal(labels, predictions),
        tf.float32
    )

    correct = correct * masks

    return (
        tf.reduce_sum(correct)
        /
        (
            tf.reduce_sum(masks)
            + tf.keras.backend.epsilon()
        )
    )


masked_binary_accuracy.__name__ = "masked_accuracy"


# ============================================================
# 6. BUILD EFFICIENTNET-B0
# ============================================================

def build_model():

    inputs = tf.keras.Input(
        shape=(224, 224, 3),
        name="dental_image"
    )

    base_model = tf.keras.applications.EfficientNetB0(
        include_top=False,
        weights="imagenet",
        input_tensor=inputs
    )

    # Stage 1:
    # freeze pretrained EfficientNet
    base_model.trainable = False

    x = base_model(
        inputs,
        training=False
    )

    x = tf.keras.layers.GlobalAveragePooling2D()(
        x
    )

    x = tf.keras.layers.Dropout(
        0.3
    )(x)

    outputs = tf.keras.layers.Dense(
        NUM_CLASSES,
        activation="sigmoid",
        name="condition_predictions"
    )(x)

    model = tf.keras.Model(
        inputs=inputs,
        outputs=outputs,
        name="VeterinaryDentalEfficientNetB0"
    )

    return model, base_model


# ============================================================
# 7. CALLBACKS
# ============================================================

def get_callbacks():

    return [

        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(BEST_MODEL_PATH),
            monitor="val_loss",
            save_best_only=True,
            verbose=1
        ),

        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=5,
            restore_best_weights=True,
            verbose=1
        ),

        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=1e-7,
            verbose=1
        )
    ]


# ============================================================
# 8. MAIN TRAINING
# ============================================================

def main():

    print("\n===================================")
    print("Loading datasets")
    print("===================================")

    train_dataset, validation_dataset, test_dataset = (
        get_datasets()
    )

    train_dataset = pack_dataset(
        train_dataset
    )

    validation_dataset = pack_dataset(
        validation_dataset
    )

    test_dataset = pack_dataset(
        test_dataset
    )

    print("\n===================================")
    print("Building EfficientNet-B0")
    print("===================================")

    model, base_model = build_model()

    model.summary()

    # ========================================================
    # STAGE 1 - TRAIN CLASSIFICATION HEAD
    # ========================================================

    print("\n===================================")
    print("STAGE 1: Train classification head")
    print("===================================")

    model.compile(
        optimizer=tf.keras.optimizers.Adam(
            learning_rate=INITIAL_LEARNING_RATE
        ),
        loss=masked_weighted_binary_crossentropy,
        metrics=[
            masked_binary_accuracy
        ]
    )

    history_stage1 = model.fit(
        train_dataset,
        validation_data=validation_dataset,
        epochs=INITIAL_EPOCHS,
        callbacks=get_callbacks()
    )

    # ========================================================
    # STAGE 2 - FINE TUNE EFFICIENTNET
    # ========================================================

    print("\n===================================")
    print("STAGE 2: Fine-tuning EfficientNet")
    print("===================================")

    base_model.trainable = True

    # Keep most layers frozen.
    # Fine-tune only approximately the last 20 layers.
    for layer in base_model.layers[:-20]:
        layer.trainable = False

    # Keep Batch Normalization layers frozen
    for layer in base_model.layers:

        if isinstance(
            layer,
            tf.keras.layers.BatchNormalization
        ):
            layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(
            learning_rate=FINE_TUNE_LEARNING_RATE
        ),
        loss=masked_weighted_binary_crossentropy,
        metrics=[
            masked_binary_accuracy
        ]
    )

    history_stage2 = model.fit(
        train_dataset,
        validation_data=validation_dataset,
        epochs=FINE_TUNE_EPOCHS,
        callbacks=get_callbacks()
    )

    # ========================================================
    # TEST DATASET
    # ========================================================

    print("\n===================================")
    print("Testing final model")
    print("===================================")

    test_results = model.evaluate(
        test_dataset,
        verbose=1
    )

    print("\nTest results:")

    for name, value in zip(
        model.metrics_names,
        test_results
    ):
        print(
            f"{name}: {value:.4f}"
        )

    print("\n===================================")
    print("Training completed")
    print("===================================")

    print(
        "\nBest model saved to:"
    )

    print(
        BEST_MODEL_PATH
    )


# ============================================================
# 9. RUN
# ============================================================

if __name__ == "__main__":
    main()