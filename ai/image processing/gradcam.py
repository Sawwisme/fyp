import os
import cv2
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt

# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "dental_classifier.keras"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "models",
    "gradcam_outputs"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

IMAGE_SIZE = (224, 224)

LABELS = [
    "healthy",
    "plaque",
    "gingivitis",
    "calculus"
]

THRESHOLDS = {
    "healthy": 0.35,
    "plaque": 0.25,
    "gingivitis": 0.45,
    "calculus": 0.60
}


# =========================================================
# Load model
# =========================================================

print("Loading model...")

model = tf.keras.models.load_model(
    MODEL_PATH,
    compile=False
)

print("Model loaded successfully.")


# =========================================================
# Load image
# =========================================================

def load_image(image_path):

    image = tf.io.read_file(image_path)

    image = tf.image.decode_image(
        image,
        channels=3,
        expand_animations=False
    )

    original_image = image.numpy()

    image = tf.image.resize(
        image,
        IMAGE_SIZE
    )

    image = tf.cast(
        image,
        tf.float32
    )

    input_image = tf.expand_dims(
        image,
        axis=0
    )

    return original_image, input_image


# =========================================================
# Find last convolutional layer
# =========================================================

def find_last_conv_layer(base_model):

    for layer in reversed(base_model.layers):

        try:
            output_shape = layer.output.shape

            if len(output_shape) == 4:
                return layer.name

        except:
            continue

    raise ValueError(
        "No convolutional layer found."
    )


# =========================================================
# Generate Grad-CAM
# =========================================================

def generate_gradcam(
    model,
    input_image,
    class_index
):

    base_model = model.get_layer(
        "efficientnetb0"
    )

    last_conv_layer_name = find_last_conv_layer(
        base_model
    )

    print(
        "Using last convolutional layer:",
        last_conv_layer_name
    )

    last_conv_layer = base_model.get_layer(
        last_conv_layer_name
    )

    conv_model = tf.keras.Model(
        inputs=base_model.input,
        outputs=last_conv_layer.output
    )

    global_pool = model.get_layer(
        "global_average_pooling2d"
    )

    dropout_layer = model.get_layer(
        "dropout"
    )

    prediction_layer = model.get_layer(
        "condition_predictions"
    )

    with tf.GradientTape() as tape:

        conv_output = conv_model(
            input_image
        )

        tape.watch(conv_output)

        x = global_pool(
            conv_output
        )

        x = dropout_layer(
            x,
            training=False
        )

        predictions = prediction_layer(
            x
        )

        class_score = predictions[
            :,
            class_index
        ]

    gradients = tape.gradient(
        class_score,
        conv_output
    )

    pooled_gradients = tf.reduce_mean(
        gradients,
        axis=(0, 1, 2)
    )

    conv_output = conv_output[0]

    heatmap = tf.reduce_sum(
        conv_output * pooled_gradients,
        axis=-1
    )

    heatmap = tf.maximum(
        heatmap,
        0
    )

    max_value = tf.reduce_max(
        heatmap
    )

    if max_value > 0:
        heatmap = heatmap / max_value

    return heatmap.numpy()


# =========================================================
# Overlay heatmap
# =========================================================

def overlay_heatmap(
    original_image,
    heatmap,
    alpha=0.4
):

    height, width = (
        original_image.shape[:2]
    )

    heatmap = cv2.resize(
        heatmap,
        (width, height)
    )

    heatmap_uint8 = np.uint8(
        255 * heatmap
    )

    heatmap_color = cv2.applyColorMap(
        heatmap_uint8,
        cv2.COLORMAP_JET
    )

    heatmap_color = cv2.cvtColor(
        heatmap_color,
        cv2.COLOR_BGR2RGB
    )

    overlay = cv2.addWeighted(
        original_image,
        1 - alpha,
        heatmap_color,
        alpha,
        0
    )

    return overlay


# =========================================================
# Save Grad-CAM result
# =========================================================

def save_gradcam_result(
    original_image,
    overlay,
    condition,
    confidence,
    image_name
):

    plt.figure(
        figsize=(10, 4)
    )

    plt.subplot(
        1,
        2,
        1
    )

    plt.imshow(
        original_image
    )

    plt.title(
        "Original Image"
    )

    plt.axis(
        "off"
    )

    plt.subplot(
        1,
        2,
        2
    )

    plt.imshow(
        overlay
    )

    plt.title(
        f"Grad-CAM: {condition}\n"
        f"Confidence: {confidence:.4f}"
    )

    plt.axis(
        "off"
    )

    plt.tight_layout()

    output_filename = (
        f"{image_name}_{condition}_gradcam.png"
    )

    output_path = os.path.join(
        OUTPUT_DIR,
        output_filename
    )

    plt.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight"
    )

    print(
        "Saved:",
        output_path
    )

    plt.show()

    plt.close()


# =========================================================
# Automatic multi-label Grad-CAM
# =========================================================

def run_automatic_gradcam(
    image_path
):

    original_image, input_image = load_image(
        image_path
    )

    predictions = model.predict(
        input_image,
        verbose=0
    )[0]

    print("\nPredictions:")

    positive_conditions = []

    for i, label in enumerate(
        LABELS
    ):

        confidence = float(
            predictions[i]
        )

        threshold = THRESHOLDS[
            label
        ]

        status = (
            "POSITIVE"
            if confidence >= threshold
            else "NEGATIVE"
        )

        print(
            f"{label:<12} "
            f"{confidence:.4f} "
            f"(threshold={threshold:.2f}) "
            f"{status}"
        )

        if confidence >= threshold:

            positive_conditions.append(
                (
                    label,
                    confidence,
                    i
                )
            )

    print("\nDetected positive conditions:")

    if len(
        positive_conditions
    ) == 0:

        print(
            "No condition exceeded its threshold."
        )

        return

    for condition, confidence, class_index in positive_conditions:

        print(
            f"- {condition}: "
            f"{confidence:.4f}"
        )

    image_name = os.path.splitext(
        os.path.basename(
            image_path
        )
    )[0]

    # =====================================================
    # Generate Grad-CAM for every positive condition
    # =====================================================

    for condition, confidence, class_index in positive_conditions:

        print(
            f"\nGenerating Grad-CAM for: "
            f"{condition}"
        )

        heatmap = generate_gradcam(
            model,
            input_image,
            class_index
        )

        overlay = overlay_heatmap(
            original_image,
            heatmap
        )

        save_gradcam_result(
            original_image,
            overlay,
            condition,
            confidence,
            image_name
        )


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    IMAGE_PATH = os.path.join(
        BASE_DIR,
        "fyp final dataset",
        "images",
        "cat_0741.jpg"
    )

    run_automatic_gradcam(
        IMAGE_PATH
    )