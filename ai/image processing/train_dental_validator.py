import os
import tensorflow as tf
import keras
from keras import layers, models


# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

SPLIT_DIR = "/content/dental validator split"

TRAIN_DIR = os.path.join(
    SPLIT_DIR,
    "train"
)

VAL_DIR = os.path.join(
    SPLIT_DIR,
    "validation"
)

TEST_DIR = os.path.join(
    SPLIT_DIR,
    "test"
)

MODEL_DIR = os.path.join(
    BASE_DIR,
    "models"
)

os.makedirs(
    MODEL_DIR,
    exist_ok=True
)

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "dental_image_validator.keras"
)

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 32
SEED = 42


# =========================================================
# Check dataset paths
# =========================================================

print("Training directory:")
print(TRAIN_DIR)

print("\nValidation directory:")
print(VAL_DIR)

print("\nTest directory:")
print(TEST_DIR)

for path in [
    TRAIN_DIR,
    VAL_DIR,
    TEST_DIR
]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset directory not found: {path}"
        )


# =========================================================
# Load training dataset
# =========================================================

train_ds = keras.utils.image_dataset_from_directory(
    TRAIN_DIR,
    image_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE,
    label_mode="binary",
    shuffle=True,
    seed=SEED
)


# =========================================================
# Load validation dataset
# =========================================================

val_ds = keras.utils.image_dataset_from_directory(
    VAL_DIR,
    image_size=IMAGE_SIZE,
    batch_size=BATCH_SIZE,
    label_mode="binary",
    shuffle=False
)

print(
    "\nClass names:",
    train_ds.class_names
)

# IMPORTANT:
# Expected:
# ['invalid non dental', 'valid dental']
#
# This means:
# invalid non dental = 0
# valid dental       = 1

if train_ds.class_names != [
    "invalid non dental",
    "valid dental"
]:
    raise ValueError(
        "Unexpected class order. "
        f"Found: {train_ds.class_names}"
    )


AUTOTUNE = tf.data.AUTOTUNE

train_ds = train_ds.prefetch(
    AUTOTUNE
)

val_ds = val_ds.prefetch(
    AUTOTUNE
)


# =========================================================
# Data augmentation
# =========================================================

augmentation = keras.Sequential([
    layers.RandomFlip(
        "horizontal"
    ),
    layers.RandomRotation(
        0.05
    ),
    layers.RandomZoom(
        0.10
    ),
    layers.RandomContrast(
        0.10
    )
])


# =========================================================
# Build MobileNetV2
# =========================================================

base_model = keras.applications.MobileNetV2(
    input_shape=(
        224,
        224,
        3
    ),
    include_top=False,
    weights="imagenet"
)

base_model.trainable = False


inputs = layers.Input(
    shape=(
        224,
        224,
        3
    ),
    name="dental_image"
)

x = augmentation(
    inputs
)

x = keras.applications.mobilenet_v2.preprocess_input(
    x
)

x = base_model(
    x,
    training=False
)

x = layers.GlobalAveragePooling2D()(
    x
)

x = layers.Dropout(
    0.3
)(
    x
)

outputs = layers.Dense(
    1,
    activation="sigmoid",
    name="dental_probability"
)(
    x
)

model = models.Model(
    inputs=inputs,
    outputs=outputs,
    name="PetDentalImageValidator"
)


# =========================================================
# Compile Stage 1
# =========================================================

model.compile(
    optimizer=keras.optimizers.Adam(
        learning_rate=1e-3
    ),
    loss="binary_crossentropy",
    metrics=[
        "accuracy",
        keras.metrics.Precision(
            name="precision"
        ),
        keras.metrics.Recall(
            name="recall"
        )
    ]
)

model.summary()


# =========================================================
# Callback factory
# =========================================================

def create_callbacks():

    return [
        keras.callbacks.ModelCheckpoint(
            MODEL_PATH,
            monitor="val_loss",
            save_best_only=True,
            verbose=1
        ),

        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=4,
            restore_best_weights=True,
            verbose=1
        ),

        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            min_lr=1e-6,
            verbose=1
        )
    ]


# =========================================================
# Stage 1
# =========================================================

print(
    "\n==================================="
)

print(
    "Stage 1: Train classification head"
)

print(
    "==================================="
)

history_stage1 = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=12,
    callbacks=create_callbacks()
)


# =========================================================
# Stage 2: Fine-tune MobileNetV2
# =========================================================

print(
    "\n==================================="
)

print(
    "Stage 2: Fine-tuning MobileNetV2"
)

print(
    "==================================="
)

base_model.trainable = True


# Freeze most layers
for layer in base_model.layers[:-20]:
    layer.trainable = False


# Keep Batch Normalization frozen
for layer in base_model.layers:

    if isinstance(
        layer,
        layers.BatchNormalization
    ):
        layer.trainable = False


model.compile(
    optimizer=keras.optimizers.Adam(
        learning_rate=1e-5
    ),
    loss="binary_crossentropy",
    metrics=[
        "accuracy",
        keras.metrics.Precision(
            name="precision"
        ),
        keras.metrics.Recall(
            name="recall"
        )
    ]
)


history_stage2 = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=8,
    callbacks=create_callbacks()
)


# =========================================================
# Load best saved model
# =========================================================

print(
    "\nLoading best validator model..."
)

model = keras.models.load_model(
    MODEL_PATH
)


# =========================================================
# Validation evaluation
# =========================================================

print(
    "\n==================================="
)

print(
    "Validation Results"
)

print(
    "==================================="
)

results = model.evaluate(
    val_ds,
    verbose=1
)

for metric_name, value in zip(
    model.metrics_names,
    results
):
    print(
        f"{metric_name}: {value:.4f}"
    )


print(
    "\n==================================="
)

print(
    "Training completed"
)

print(
    "==================================="
)

print(
    "Best dental validator saved to:"
)

print(
    MODEL_PATH
)