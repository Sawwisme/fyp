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

DATASET_DIR = "/content/segmentation grouped split"

TRAIN_IMAGE_DIR = os.path.join(
    DATASET_DIR,
    "train",
    "images"
)

TRAIN_MASK_DIR = os.path.join(
    DATASET_DIR,
    "train",
    "masks"
)

VAL_IMAGE_DIR = os.path.join(
    DATASET_DIR,
    "validation",
    "images"
)

VAL_MASK_DIR = os.path.join(
    DATASET_DIR,
    "validation",
    "masks"
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
    "dental_segmentation_mobilenet_unet.keras"
)

IMAGE_SIZE = (256, 256)
BATCH_SIZE = 8
NUM_CLASSES = 3
EPOCHS = 30

AUTOTUNE = tf.data.AUTOTUNE


# =========================================================
# File pairs
# =========================================================

def get_file_pairs(
    image_dir,
    mask_dir
):

    image_paths = []
    mask_paths = []

    for filename in sorted(
        os.listdir(image_dir)
    ):

        if not filename.lower().endswith(
            (".jpg", ".jpeg", ".png")
        ):
            continue

        image_path = os.path.join(
            image_dir,
            filename
        )

        stem = os.path.splitext(
            filename
        )[0]

        mask_path = os.path.join(
            mask_dir,
            f"{stem}.png"
        )

        if os.path.exists(mask_path):

            image_paths.append(
                image_path
            )

            mask_paths.append(
                mask_path
            )

    return image_paths, mask_paths


train_images, train_masks = get_file_pairs(
    TRAIN_IMAGE_DIR,
    TRAIN_MASK_DIR
)

val_images, val_masks = get_file_pairs(
    VAL_IMAGE_DIR,
    VAL_MASK_DIR
)

print(
    "Train samples:",
    len(train_images)
)

print(
    "Validation samples:",
    len(val_images)
)


# =========================================================
# Load image + mask
# =========================================================

def load_image_mask(
    image_path,
    mask_path
):

    image = tf.io.read_file(
        image_path
    )

    image = tf.image.decode_image(
        image,
        channels=3,
        expand_animations=False
    )

    image.set_shape(
        [None, None, 3]
    )

    image = tf.image.resize(
        image,
        IMAGE_SIZE
    )

    image = tf.cast(
        image,
        tf.float32
    )

    # MobileNetV2 expects [-1, 1]
    image = keras.applications.mobilenet_v2.preprocess_input(
        image
    )


    mask = tf.io.read_file(
        mask_path
    )

    mask = tf.image.decode_png(
        mask,
        channels=1
    )

    mask = tf.image.resize(
        mask,
        IMAGE_SIZE,
        method="nearest"
    )

    mask = tf.cast(
        mask,
        tf.int32
    )

    return image, mask


def create_dataset(
    image_paths,
    mask_paths,
    training=False
):

    dataset = tf.data.Dataset.from_tensor_slices(
        (
            image_paths,
            mask_paths
        )
    )

    if training:

        dataset = dataset.shuffle(
            len(image_paths),
            seed=42
        )

    dataset = dataset.map(
        load_image_mask,
        num_parallel_calls=AUTOTUNE
    )

    dataset = dataset.batch(
        BATCH_SIZE
    )

    dataset = dataset.prefetch(
        AUTOTUNE
    )

    return dataset


train_ds = create_dataset(
    train_images,
    train_masks,
    training=True
)

val_ds = create_dataset(
    val_images,
    val_masks
)


# =========================================================
# MobileNetV2 encoder
# =========================================================

base_model = keras.applications.MobileNetV2(
    input_shape=(
        IMAGE_SIZE[0],
        IMAGE_SIZE[1],
        3
    ),
    include_top=False,
    weights="imagenet"
)


# Skip connection layers
layer_names = [
    "block_1_expand_relu",   # 128x128
    "block_3_expand_relu",   # 64x64
    "block_6_expand_relu",   # 32x32
    "block_13_expand_relu",  # 16x16
    "block_16_project"       # 8x8
]

encoder_outputs = [
    base_model.get_layer(name).output
    for name in layer_names
]

encoder = keras.Model(
    inputs=base_model.input,
    outputs=encoder_outputs
)

# First stage: freeze encoder
encoder.trainable = False


# =========================================================
# Decoder block
# =========================================================

def upsample_block(
    filters
):

    return keras.Sequential(
        [
            layers.Conv2DTranspose(
                filters,
                3,
                strides=2,
                padding="same",
                activation="relu"
            ),

            layers.BatchNormalization(),

            layers.Conv2D(
                filters,
                3,
                padding="same",
                activation="relu"
            ),

            layers.BatchNormalization()
        ]
    )


# =========================================================
# Build MobileNetV2 U-Net
# =========================================================

inputs = layers.Input(
    shape=(
        IMAGE_SIZE[0],
        IMAGE_SIZE[1],
        3
    )
)

skips = encoder(
    inputs
)

x = skips[-1]

skip_connections = reversed(
    skips[:-1]
)

decoder_filters = [
    256,
    128,
    64,
    32
]

for filters, skip in zip(
    decoder_filters,
    skip_connections
):

    x = upsample_block(
        filters
    )(
        x
    )

    x = layers.Concatenate()(
        [
            x,
            skip
        ]
    )


# Final 16 -> 32 -> 64 -> 128 -> 256
x = layers.Conv2DTranspose(
    16,
    3,
    strides=2,
    padding="same",
    activation="relu"
)(
    x
)

outputs = layers.Conv2D(
    NUM_CLASSES,
    1,
    padding="same",
    activation="softmax"
)(
    x
)

model = models.Model(
    inputs=inputs,
    outputs=outputs,
    name="DentalMobileNetV2UNet"
)


# =========================================================
# Combined loss
# =========================================================

CLASS_WEIGHTS = tf.constant(
    [
        0.2,
        1.5,
        1.5
    ],
    dtype=tf.float32
)


def weighted_cross_entropy(
    y_true,
    y_pred
):

    y_true = tf.squeeze(
        y_true,
        axis=-1
    )

    y_true = tf.cast(
        y_true,
        tf.int32
    )

    loss = keras.losses.sparse_categorical_crossentropy(
        y_true,
        y_pred
    )

    weights = tf.gather(
        CLASS_WEIGHTS,
        y_true
    )

    return tf.reduce_mean(
        loss * weights
    )


def dice_loss(
    y_true,
    y_pred
):

    y_true = tf.squeeze(
        y_true,
        axis=-1
    )

    y_true = tf.one_hot(
        tf.cast(
            y_true,
            tf.int32
        ),
        depth=NUM_CLASSES
    )

    y_true = tf.cast(
        y_true,
        tf.float32
    )

    y_true_fg = y_true[
        ...,
        1:
    ]

    y_pred_fg = y_pred[
        ...,
        1:
    ]

    intersection = tf.reduce_sum(
        y_true_fg * y_pred_fg,
        axis=[1, 2]
    )

    denominator = (
        tf.reduce_sum(
            y_true_fg,
            axis=[1, 2]
        )
        +
        tf.reduce_sum(
            y_pred_fg,
            axis=[1, 2]
        )
    )

    dice = (
        2.0 * intersection + 1e-6
    ) / (
        denominator + 1e-6
    )

    return 1.0 - tf.reduce_mean(
        dice
    )


def combined_loss(
    y_true,
    y_pred
):

    return (
        weighted_cross_entropy(
            y_true,
            y_pred
        )
        +
        dice_loss(
            y_true,
            y_pred
        )
    )


# =========================================================
# Compile
# =========================================================

model.compile(
    optimizer=keras.optimizers.Adam(
        learning_rate=1e-4
    ),
    loss=combined_loss,
    metrics=[
        "accuracy"
    ]
)

model.summary()


# =========================================================
# Callbacks
# =========================================================

callbacks = [
    keras.callbacks.ModelCheckpoint(
        MODEL_PATH,
        monitor="val_loss",
        save_best_only=True,
        verbose=1
    ),

    keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=5,
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
# Train
# =========================================================

print()
print("===================================")
print("Training MobileNetV2 U-Net")
print("===================================")

history = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=EPOCHS,
    callbacks=callbacks
)


print()
print("===================================")
print("Training completed")
print("===================================")

print(
    "Best model saved to:"
)

print(
    MODEL_PATH
)