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
# Load trained model
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
# Find final convolutional layer inside EfficientNet
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

    # EfficientNet backbone
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

    # Model from EfficientNet input
    # to final conv layer
    conv_model = tf.keras.Model(
        inputs=base_model.input,
        outputs=last_conv_layer.output
    )

    # Get classifier layers after EfficientNet
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

        # Disable dropout during inference
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
        conv_output
        * pooled_gradients,
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
# Run Grad-CAM
# =========================================================

def run_gradcam(
    image_path,
    target_condition
):

    if target_condition not in LABELS:
        raise ValueError(
            f"Invalid condition: {target_condition}"
        )

    original_image, input_image = load_image(
        image_path
    )

    predictions = model.predict(
        input_image,
        verbose=0
    )[0]

    print("\nPredictions:")

    for i, label in enumerate(LABELS):

        confidence = float(
            predictions[i]
        )

        threshold = THRESHOLDS[label]

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

    class_index = LABELS.index(
        target_condition
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

    # =====================================================
    # Display result
    # =====================================================

    plt.figure(figsize=(10, 4))

    plt.subplot(1, 2, 1)
    plt.imshow(original_image)
    plt.title("Original Image")
    plt.axis("off")

    plt.subplot(1, 2, 2)
    plt.imshow(overlay)
    plt.title(
        f"Grad-CAM: {target_condition}"
    )
    plt.axis("off")

    plt.tight_layout()
    plt.show()


# =========================================================
# Example usage
# =========================================================

if __name__ == "__main__":

    IMAGE_PATH = os.path.join(
        BASE_DIR,
        "test_image.jpg"
    )

    TARGET_CONDITION = "gingivitis"

    run_gradcam(
        IMAGE_PATH,
        TARGET_CONDITION
    )