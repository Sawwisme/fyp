from pathlib import Path
import pandas as pd
import tensorflow as tf


# ============================================================
# 1. PATH SETTINGS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATASET_DIR = BASE_DIR / "fyp final dataset"
IMAGES_DIR = DATASET_DIR / "images"
LABELS_FILE = DATASET_DIR / "labels_split.csv"


# ============================================================
# 2. IMAGE / TRAINING SETTINGS
# ============================================================

IMG_HEIGHT = 224
IMG_WIDTH = 224
BATCH_SIZE = 32

AUTOTUNE = tf.data.AUTOTUNE


# ============================================================
# 3. LABEL SETTINGS
# ============================================================

LABEL_COLUMNS = [
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


# ============================================================
# 4. DATA AUGMENTATION
# ============================================================

# Only used for TRAINING images
data_augmentation = tf.keras.Sequential(
    [
        tf.keras.layers.RandomFlip("horizontal"),
        tf.keras.layers.RandomRotation(0.05),
        tf.keras.layers.RandomZoom(0.10),
        tf.keras.layers.RandomTranslation(
            height_factor=0.05,
            width_factor=0.05
        ),
        tf.keras.layers.RandomContrast(0.10),
    ],
    name="data_augmentation"
)


# ============================================================
# 5. LOAD CSV
# ============================================================

def load_dataframe():
    """
    Load labels_split.csv.
    """

    df = pd.read_csv(LABELS_FILE)

    print("Dataset loaded successfully.")
    print("Total records:", len(df))

    return df


# ============================================================
# 6. LOAD ONE IMAGE
# ============================================================

def load_image(image_path):
    """
    Read an image, decode it as RGB,
    resize it to 224 x 224,
    and convert it to float32.

    EfficientNetB0 in modern Keras already includes
    its own input rescaling layer, so pixel values
    can remain in the 0-255 range.
    """

    image = tf.io.read_file(image_path)

    image = tf.io.decode_image(
        image,
        channels=3,
        expand_animations=False
    )

    image = tf.image.resize(
        image,
        [IMG_HEIGHT, IMG_WIDTH]
    )

    image = tf.cast(image, tf.float32)

    return image


# ============================================================
# 7. PROCESS ONE DATASET SAMPLE
# ============================================================

def process_sample(
    image_path,
    labels,
    masks,
    training=False
):
    """
    Load one image and return:

    image
    labels
    masks
    """

    image = load_image(image_path)

    if training:
        image = data_augmentation(
            image,
            training=True,
        )

        # Input remains in the 0–255 range used by EfficientNet.
        image = tf.image.random_brightness(
            image,
            max_delta=12.0,
        )
        
        image = tf.clip_by_value(image, 0.0, 255.0)

    labels = tf.cast(
        labels,
        tf.float32
    )

    masks = tf.cast(
        masks,
        tf.float32
    )

    return image, labels, masks


# ============================================================
# 8. CREATE TF.DATA DATASET
# ============================================================

def create_dataset(
    df,
    training=False,
    shuffle=False
):
    """
    Convert a pandas DataFrame into
    a TensorFlow tf.data.Dataset.
    """

    image_paths = [
        str(IMAGES_DIR / filename)
        for filename in df["filename"].values
    ]

    labels = df[
        LABEL_COLUMNS
    ].values.astype("float32")

    masks = df[
        MASK_COLUMNS
    ].values.astype("float32")

    dataset = tf.data.Dataset.from_tensor_slices(
        (
            image_paths,
            labels,
            masks
        )
    )

    if shuffle:
        dataset = dataset.shuffle(
            buffer_size=len(df),
            reshuffle_each_iteration=True
        )

    dataset = dataset.map(
        lambda image_path, labels, masks:
        process_sample(
            image_path,
            labels,
            masks,
            training=training
        ),
        num_parallel_calls=AUTOTUNE
    )

    dataset = dataset.batch(
        BATCH_SIZE
    )

    dataset = dataset.prefetch(
        AUTOTUNE
    )

    return dataset


# ============================================================
# 9. BUILD TRAIN / VALIDATION / TEST DATASETS
# ============================================================

def get_datasets():
    """
    Load labels_split.csv and create
    train, validation and test datasets.
    """

    df = load_dataframe()

    train_df = df[
        df["split"] == "train"
    ].copy()

    validation_df = df[
        df["split"] == "validation"
    ].copy()

    test_df = df[
        df["split"] == "test"
    ].copy()

    print("\nDataset split:")
    print("Train:", len(train_df))
    print("Validation:", len(validation_df))
    print("Test:", len(test_df))

    train_dataset = create_dataset(
        train_df,
        training=True,
        shuffle=True
    )

    validation_dataset = create_dataset(
        validation_df,
        training=False,
        shuffle=False
    )

    test_dataset = create_dataset(
        test_df,
        training=False,
        shuffle=False
    )

    return (
        train_dataset,
        validation_dataset,
        test_dataset
    )


# ============================================================
# 10. TEST PREPROCESSING
# ============================================================

if __name__ == "__main__":

    train_dataset, validation_dataset, test_dataset = (
        get_datasets()
    )

    print("\nTesting one training batch...")

    for images, labels, masks in train_dataset.take(1):

        print("\nImage batch shape:")
        print(images.shape)

        print("\nLabel batch shape:")
        print(labels.shape)

        print("\nMask batch shape:")
        print(masks.shape)

        print("\nFirst sample labels:")
        print(labels[0].numpy())

        print("\nFirst sample masks:")
        print(masks[0].numpy())

        print("\nImage value range:")
        print(
            float(tf.reduce_min(images)),
            "to",
            float(tf.reduce_max(images))
        )

    print("\nPreprocessing test completed successfully.")