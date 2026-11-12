import os
import cv2
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt


# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "dental_segmentation_mobilenet_unet.keras"
)

IMAGE_SIZE = (256, 256)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "models",
    "segmentation_outputs"
)

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


# =========================================================
# Load segmentation model
# =========================================================

print("Loading segmentation model...")

model = tf.keras.models.load_model(
    MODEL_PATH,
    compile=False
)

print("Segmentation model loaded successfully.")


# =========================================================
# Load image
# =========================================================

def load_segmentation_image(image_path):
    original_image = cv2.imread(str(image_path))

    if original_image is None:
        raise ValueError(f"Unable to read image: {image_path}")

    image = tf.io.decode_image(
        tf.io.read_file(str(image_path)),
        channels=3,
        expand_animations=False,
    )

    image = tf.image.resize(image, IMAGE_SIZE)
    image = tf.cast(image, tf.float32)

    # MobileNetV2 expects [-1, 1].
    image = tf.keras.applications.mobilenet_v2.preprocess_input(
        image
    )

    input_image = image[None, ...].numpy()

    return original_image, input_image
# =========================================================
# Predict segmentation
# =========================================================

def predict_segmentation(
    image_path
):
    (
        original_image,
        input_image
    ) = load_segmentation_image(
        image_path
    )

    prediction = model.predict(
        input_image,
        verbose=0
    )[0]

    predicted_mask = np.argmax(
        prediction,
        axis=-1
    ).astype(
        np.uint8
    )

    total_pixels = predicted_mask.size

    gingivitis_pixels = np.sum(
        predicted_mask == 1
    )

    calculus_pixels = np.sum(
        predicted_mask == 2
    )

    gingivitis_area_percent = (
        gingivitis_pixels
        / total_pixels
        * 100.0
    )

    calculus_area_percent = (
        calculus_pixels
        / total_pixels
        * 100.0
    )

    total_disease_area_percent = (
        gingivitis_area_percent
        + calculus_area_percent
    )

    return {
        "original_image": original_image,
        "mask": predicted_mask,

        "gingivitis_area_percent": round(
            float(gingivitis_area_percent),
            2
        ),

        "calculus_area_percent": round(
            float(calculus_area_percent),
            2
        ),

        "total_disease_area_percent": round(
            float(total_disease_area_percent),
            2
        )
    }


# =========================================================
# Create coloured segmentation mask
# =========================================================

def create_colored_mask(
    mask
):
    height, width = mask.shape

    colored_mask = np.zeros(
        (
            height,
            width,
            3
        ),
        dtype=np.uint8
    )

    # Gingivitis = Red
    colored_mask[
        mask == 1
    ] = [255, 0, 0]

    # Calculus = Yellow
    colored_mask[
        mask == 2
    ] = [255, 214, 0]

    return colored_mask


# =========================================================
# Create overlay
# =========================================================

def create_overlay(
    original_image,
    mask,
    alpha=0.4
):
    height, width = (
        original_image.shape[:2]
    )

    colored_mask = (
        create_colored_mask(
            mask
        )
    )

    colored_mask = cv2.resize(
        colored_mask,
        (
            width,
            height
        ),
        interpolation=cv2.INTER_NEAREST
    )

    original_rgb = cv2.cvtColor(
        original_image,
        cv2.COLOR_BGR2RGB
    )

    overlay = cv2.addWeighted(
        original_rgb,
        1.0,
        colored_mask,
        alpha,
        0
    )

    return overlay


# =========================================================
# Save segmentation result
# =========================================================

def save_segmentation_result(
    image_path,
    result
):
    image_name = os.path.splitext(
        os.path.basename(
            image_path
        )
    )[0]

    overlay = create_overlay(
        result["original_image"],
        result["mask"]
    )

    overlay_bgr = cv2.cvtColor(
        overlay,
        cv2.COLOR_RGB2BGR
    )

    output_path = os.path.join(
        OUTPUT_DIR,
        f"{image_name}_segmentation.png"
    )

    cv2.imwrite(
        output_path,
        overlay_bgr
    )

    plt.figure(figsize=(8, 8))

    plt.imshow(
        overlay
    )

    plt.title(
        "Dental Segmentation Result\n"
        "Red = Gingivitis | Yellow = Calculus"
    )

    plt.axis("off")

    plt.tight_layout()

    plt.show()

    return output_path


# =========================================================
# Main analysis
# =========================================================

def run_segmentation(
    image_path
):
    print(
        "\n==================================="
    )

    print(
        "Dental Segmentation Analysis"
    )

    print(
        "==================================="
    )

    result = predict_segmentation(
        image_path
    )

    print(
        f"\nGingivitis estimated area: "
        f"{result['gingivitis_area_percent']:.2f}%"
    )

    print(
        f"Calculus estimated area: "
        f"{result['calculus_area_percent']:.2f}%"
    )

    print(
        f"Total estimated disease area: "
        f"{result['total_disease_area_percent']:.2f}%"
    )

    output_path = (
        save_segmentation_result(
            image_path,
            result
        )
    )

    print(
        "\nSegmentation overlay saved:"
    )

    print(
        output_path
    )

    return {
        "_mask": result["mask"],

        "gingivitis_area_percent":
            result[
                "gingivitis_area_percent"
            ],

        "calculus_area_percent":
            result[
                "calculus_area_percent"
            ],

        "total_disease_area_percent":
            result[
                "total_disease_area_percent"
            ],

        "segmentation_output":
            output_path
    }


# =========================================================
# Local testing
# =========================================================

if __name__ == "__main__":

    IMAGE_PATH = os.path.join(
        BASE_DIR,
        "fyp final dataset",
        "images",
        "cat_0741.jpg"
    )

    analysis_result = (
        run_segmentation(
            IMAGE_PATH
        )
    )