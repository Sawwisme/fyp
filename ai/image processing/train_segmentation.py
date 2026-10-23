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
    "dental_segmentation_unet_ce.keras"
)

IMAGE_SIZE = (256, 256)

BATCH_SIZE = 8

NUM_CLASSES = 3

EPOCHS = 30

AUTOTUNE = tf.data.AUTOTUNE


# =========================================================
# File lists
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

        name = os.path.splitext(
            filename
        )[0]

        mask_path = os.path.join(
            mask_dir,
            f"{name}.png"
        )

        if os.path.exists(
            mask_path
        ):
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

    # -------------------------
    # Image
    # -------------------------

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
    ) / 255.0


    # -------------------------
    # Mask
    # -------------------------

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


# =========================================================
# Dataset creation
# =========================================================

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
            buffer_size=len(
                image_paths
            ),
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
    val_masks,
    training=False
)


# =========================================================
# U-Net building blocks
# =========================================================

def conv_block(
    inputs,
    filters
):

    x = layers.Conv2D(
        filters,
        3,
        padding="same",
        activation="relu"
    )(
        inputs
    )

    x = layers.BatchNormalization()(
        x
    )

    x = layers.Conv2D(
        filters,
        3,
        padding="same",
        activation="relu"
    )(
        x
    )

    x = layers.BatchNormalization()(
        x
    )

    return x


def encoder_block(
    inputs,
    filters
):

    x = conv_block(
        inputs,
        filters
    )

    p = layers.MaxPooling2D(
        (2, 2)
    )(
        x
    )

    return x, p


def decoder_block(
    inputs,
    skip_features,
    filters
):

    x = layers.Conv2DTranspose(
        filters,
        2,
        strides=2,
        padding="same"
    )(
        inputs
    )

    x = layers.Concatenate()(
        [
            x,
            skip_features
        ]
    )

    x = conv_block(
        x,
        filters
    )

    return x


# =========================================================
# Build U-Net
# =========================================================

inputs = layers.Input(
    shape=(
        IMAGE_SIZE[0],
        IMAGE_SIZE[1],
        3
    )
)

s1, p1 = encoder_block(
    inputs,
    32
)

s2, p2 = encoder_block(
    p1,
    64
)

s3, p3 = encoder_block(
    p2,
    128
)

s4, p4 = encoder_block(
    p3,
    256
)

b1 = conv_block(
    p4,
    512
)

d1 = decoder_block(
    b1,
    s4,
    256
)

d2 = decoder_block(
    d1,
    s3,
    128
)

d3 = decoder_block(
    d2,
    s2,
    64
)

d4 = decoder_block(
    d3,
    s1,
    32
)

outputs = layers.Conv2D(
    NUM_CLASSES,
    1,
    padding="same",
    activation="softmax"
)(
    d4
)

model = models.Model(
    inputs,
    outputs,
    name="DentalSegmentationUNet"
)

# =========================================================
# Segmentation loss
# =========================================================

CLASS_WEIGHTS = tf.constant(
    [
        0.2,   # background
        1.5,   # gingivitis
        1.5    # calculus
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

    loss = tf.keras.losses.sparse_categorical_crossentropy(
        y_true,
        y_pred
    )

    weights = tf.gather(
        CLASS_WEIGHTS,
        y_true
    )

    loss = loss * weights

    return tf.reduce_mean(
        loss
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

    # Ignore background for Dice
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

    ce = weighted_cross_entropy(
        y_true,
        y_pred
    )

    dice = dice_loss(
        y_true,
        y_pred
    )

    return (
        ce
        + dice
    )

# =========================================================
# Compile
# =========================================================

model.compile(
    optimizer=keras.optimizers.Adam(
        learning_rate=1e-4
    ),
    loss=keras.losses.SparseCategoricalCrossentropy(),
    metrics=[
        "accuracy"
    ]
)

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
print("Training U-Net")
print("===================================")

history = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=EPOCHS,
    callbacks=callbacks
)


# =========================================================
# Load best model
# =========================================================

model = keras.models.load_model(
    MODEL_PATH,
    compile=False
)

print()
print("===================================")
print("Training completed")
print("===================================")

print(
    "Best segmentation model saved to:"
)

print(
    MODEL_PATH
)