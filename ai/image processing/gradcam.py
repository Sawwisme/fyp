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

DENTAL_VALIDATOR_MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "dental_image_validator.keras"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "models",
    "gradcam_outputs"
)

os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
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

LAST_CONV_LAYER_NAME = "top_activation"


# =========================================================
# Image validation configuration
# =========================================================

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png"
}

MAX_FILE_SIZE_MB = 10

MIN_WIDTH = 150
MIN_HEIGHT = 150

BLUR_THRESHOLD = 25.0

MIN_BRIGHTNESS = 25
MAX_BRIGHTNESS = 235

DENTAL_CONTENT_THRESHOLD = 0.70


# =========================================================
# Load dental classifier
# =========================================================

print("Loading dental classifier...")

model = tf.keras.models.load_model(
    MODEL_PATH,
    compile=False
)

print("Dental classifier loaded successfully.")


# =========================================================
# Load optional dental-image validator
# =========================================================

dental_validator_model = None

if os.path.exists(
    DENTAL_VALIDATOR_MODEL_PATH
):

    print(
        "Loading pet dental image validator..."
    )

    dental_validator_model = (
        tf.keras.models.load_model(
            DENTAL_VALIDATOR_MODEL_PATH,
            compile=False
        )
    )

    print(
        "Pet dental image validator loaded successfully."
    )

else:

    print(
        "Pet dental image validator model not found."
    )

    print(
        "Only technical image validation will be performed."
    )


# =========================================================
# Validate file
# =========================================================

def validate_file(
    image_path
):

    if not os.path.exists(
        image_path
    ):

        return False, (
            "Image file does not exist."
        )

    extension = os.path.splitext(
        image_path
    )[1].lower()

    if extension not in (
        ALLOWED_EXTENSIONS
    ):

        return False, (
            "Unsupported image format. "
            "Please upload JPG, JPEG or PNG."
        )

    file_size_mb = (
        os.path.getsize(
            image_path
        )
        / (1024 * 1024)
    )

    if (
        file_size_mb
        > MAX_FILE_SIZE_MB
    ):

        return False, (
            f"Image file is too large. "
            f"Maximum allowed size is "
            f"{MAX_FILE_SIZE_MB} MB."
        )

    return True, (
        "File validation passed."
    )


# =========================================================
# Validate image quality
# =========================================================

def validate_image_quality(
    image_path
):

    image = cv2.imread(
        image_path
    )

    if image is None:

        return False, (
            "The uploaded file cannot be "
            "decoded as a valid image."
        )

    height, width = (
        image.shape[:2]
    )

    # -----------------------------------------------------
    # Resolution
    # -----------------------------------------------------

    if (
        width < MIN_WIDTH
        or height < MIN_HEIGHT
    ):

        return False, (
            f"Image resolution is too low. "
            f"Minimum recommended resolution "
            f"is {MIN_WIDTH}x{MIN_HEIGHT}."
        )

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    # -----------------------------------------------------
    # Blur detection
    # -----------------------------------------------------

    blur_score = cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()

    if (
        blur_score
        < BLUR_THRESHOLD
    ):

        return False, (
            f"Image appears too blurry "
            f"(blur score="
            f"{blur_score:.2f}). "
            f"Please retake the photo "
            f"with better focus."
        )

    # -----------------------------------------------------
    # Brightness detection
    # -----------------------------------------------------

    brightness = float(
        np.mean(gray)
    )

    if (
        brightness
        < MIN_BRIGHTNESS
    ):

        return False, (
            f"Image appears too dark "
            f"(brightness="
            f"{brightness:.2f}). "
            f"Please capture the image "
            f"with better lighting."
        )

    if (
        brightness
        > MAX_BRIGHTNESS
    ):

        return False, (
            f"Image appears too bright "
            f"(brightness="
            f"{brightness:.2f}). "
            f"Please avoid excessive lighting "
            f"or flash."
        )

    quality_info = {
        "width": width,
        "height": height,
        "blur_score": blur_score,
        "brightness": brightness
    }

    return True, quality_info


# =========================================================
# Load image for model
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

    original_image = (
        image.numpy()
    )

    image = tf.image.resize(
        image,
        IMAGE_SIZE
    )

    image = tf.cast(
        image,
        tf.float32
    )

    # IMPORTANT:
    # Keep image in 0-255 range.
    #
    # Your EfficientNet-B0 training pipeline
    # used the Keras EfficientNet model,
    # which already contains internal rescaling.

    input_image = tf.expand_dims(
        image,
        axis=0
    )

    return (
        original_image,
        input_image
    )


# =========================================================
# Validate pet dental image content
# =========================================================

def validate_pet_dental_content(
    input_image
):

    if (
        dental_validator_model
        is None
    ):

        return None, (
            "Dental content validation skipped "
            "because the validator model "
            "has not been trained yet."
        )

    prediction = (
        dental_validator_model.predict(
            input_image,
            verbose=0
        )
    )

    score = float(
        np.squeeze(
            prediction
        )
    )

    if (
        score
        < DENTAL_CONTENT_THRESHOLD
    ):

        return False, (
            f"The uploaded image does not "
            f"appear to contain a suitable "
            f"cat or dog dental region "
            f"(dental confidence="
            f"{score:.4f})."
        )

    return True, (
        f"Pet dental image detected "
        f"(confidence="
        f"{score:.4f})."
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

    last_conv_layer = (
        base_model.get_layer(
            LAST_CONV_LAYER_NAME
        )
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

        tape.watch(
            conv_output
        )

        x = global_pool(
            conv_output
        )

        x = dropout_layer(
            x,
            training=False
        )

        predictions = (
            prediction_layer(
                x
            )
        )

        class_score = (
            predictions[
                :,
                class_index
            ]
        )

    gradients = tape.gradient(
        class_score,
        conv_output
    )

    if gradients is None:

        raise RuntimeError(
            "Unable to calculate Grad-CAM gradients."
        )

    pooled_gradients = (
        tf.reduce_mean(
            gradients,
            axis=(0, 1, 2)
        )
    )

    conv_output = (
        conv_output[0]
    )

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

    if (
        max_value > 0
    ):

        heatmap = (
            heatmap
            / max_value
        )

    return (
        heatmap.numpy()
    )


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

    heatmap_color = (
        cv2.applyColorMap(
            heatmap_uint8,
            cv2.COLORMAP_JET
        )
    )

    heatmap_color = (
        cv2.cvtColor(
            heatmap_color,
            cv2.COLOR_BGR2RGB
        )
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
# Save combined Grad-CAM summary
# =========================================================

def save_gradcam_summary(
    original_image,
    gradcam_items,
    image_name
):

    total_images = (
        1 + len(
            gradcam_items
        )
    )

    # -----------------------------------------------------
    # Dynamic layout
    # -----------------------------------------------------

    if total_images <= 2:

        rows = 1
        cols = 2

    elif total_images <= 4:

        rows = 2
        cols = 2

    else:

        rows = 2
        cols = 3

    plt.figure(
        figsize=(
            6 * cols,
            5 * rows
        )
    )

    # -----------------------------------------------------
    # Original image
    # -----------------------------------------------------

    plt.subplot(
        rows,
        cols,
        1
    )

    plt.imshow(
        original_image
    )

    plt.title(
        "Original Image",
        fontsize=14
    )

    plt.axis(
        "off"
    )

    # -----------------------------------------------------
    # Grad-CAM panels
    # -----------------------------------------------------

    for index, item in enumerate(
        gradcam_items,
        start=2
    ):

        plt.subplot(
            rows,
            cols,
            index
        )

        plt.imshow(
            item["overlay"]
        )

        condition = (
            item["condition"]
            .capitalize()
        )

        confidence = (
            item["confidence"]
        )

        threshold = (
            item["threshold"]
        )

        plt.title(
            f"{condition}\n"
            f"Confidence: "
            f"{confidence:.2%} "
            f"| Threshold: "
            f"{threshold:.2f}",
            fontsize=13
        )

        plt.axis(
            "off"
        )

    plt.tight_layout()

    output_filename = (
        f"{image_name}_"
        f"gradcam_summary.png"
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
        "\nCombined Grad-CAM saved:"
    )

    print(
        output_path
    )

    plt.show()

    plt.close()

    return output_path


# =========================================================
# Automatic dental analysis
# =========================================================

def run_automatic_gradcam(
    image_path
):

    print(
        "\n==================================="
    )

    print(
        "Dental Image Analysis"
    )

    print(
        "==================================="
    )

    # =====================================================
    # STEP 1: File validation
    # =====================================================

    valid, message = (
        validate_file(
            image_path
        )
    )

    if not valid:

        print(
            "\nFILE VALIDATION FAILED"
        )

        print(
            message
        )

        return None

    print(
        "\nFile validation passed."
    )

    # =====================================================
    # STEP 2: Image-quality validation
    # =====================================================

    valid, quality_info = (
        validate_image_quality(
            image_path
        )
    )

    if not valid:

        print(
            "\nIMAGE QUALITY VALIDATION FAILED"
        )

        print(
            quality_info
        )

        return None

    print(
        "\nImage quality validation passed."
    )

    print(
        f"Resolution: "
        f"{quality_info['width']}x"
        f"{quality_info['height']}"
    )

    print(
        f"Blur score: "
        f"{quality_info['blur_score']:.2f}"
    )

    print(
        f"Brightness: "
        f"{quality_info['brightness']:.2f}"
    )

    # =====================================================
    # STEP 3: Load image
    # =====================================================

    (
        original_image,
        input_image
    ) = load_image(
        image_path
    )

    # =====================================================
    # STEP 4: Dental-content validation
    # =====================================================

    (
        dental_valid,
        dental_message
    ) = (
        validate_pet_dental_content(
            input_image
        )
    )

    if (
        dental_valid is False
    ):

        print(
            "\nDENTAL CONTENT VALIDATION FAILED"
        )

        print(
            dental_message
        )

        return None

    elif (
        dental_valid is True
    ):

        print(
            "\nDental content validation passed."
        )

        print(
            dental_message
        )

    else:

        print(
            "\nDental content validator unavailable."
        )

        print(
            dental_message
        )

    # =====================================================
    # STEP 5: Condition prediction
    # =====================================================

    predictions = model.predict(
        input_image,
        verbose=0
    )[0]

    print(
        "\n==================================="
    )

    print(
        "Condition Predictions"
    )

    print(
        "==================================="
    )

    positive_conditions = []

    results = {}

    for i, label in enumerate(
        LABELS
    ):

        confidence = float(
            predictions[i]
        )

        threshold = (
            THRESHOLDS[
                label
            ]
        )

        is_positive = (
            confidence
            >= threshold
        )

        status = (
            "POSITIVE"
            if is_positive
            else "NEGATIVE"
        )

        print(
            f"{label:<12} "
            f"{confidence:.4f} "
            f"(threshold="
            f"{threshold:.2f}) "
            f"{status}"
        )

        results[label] = {
            "confidence": confidence,
            "threshold": threshold,
            "positive": is_positive
        }

        if is_positive:

            positive_conditions.append(
                (
                    label,
                    confidence,
                    threshold,
                    i
                )
            )

    # =====================================================
    # STEP 6: Detected conditions
    # =====================================================

    print(
        "\n==================================="
    )

    print(
        "Detected Conditions"
    )

    print(
        "==================================="
    )

    # -----------------------------------------------------
    # No positive label fallback
    # -----------------------------------------------------

    if len(
        positive_conditions
    ) == 0:

        top_index = int(
            np.argmax(
                predictions
            )
        )

        top_label = (
            LABELS[
                top_index
            ]
        )

        top_confidence = float(
            predictions[
                top_index
            ]
        )

        top_threshold = (
            THRESHOLDS[
                top_label
            ]
        )

        print(
            "No condition exceeded "
            "its classification threshold."
        )

        print(
            f"Highest model response: "
            f"{top_label} "
            f"({top_confidence:.4f})"
        )

        print(
            "Generating Grad-CAM for "
            "the highest model response."
        )

        positive_conditions.append(
            (
                top_label,
                top_confidence,
                top_threshold,
                top_index
            )
        )

    else:

        for (
            condition,
            confidence,
            threshold,
            _
        ) in positive_conditions:

            print(
                f"- {condition}: "
                f"{confidence:.4f}"
            )

    # =====================================================
    # STEP 7: Generate Grad-CAM overlays
    # =====================================================

    image_name = (
        os.path.splitext(
            os.path.basename(
                image_path
            )
        )[0]
    )

    gradcam_items = []

    for (
        condition,
        confidence,
        threshold,
        class_index
    ) in positive_conditions:

        print(
            f"\nGenerating Grad-CAM "
            f"for: {condition}"
        )

        heatmap = (
            generate_gradcam(
                model,
                input_image,
                class_index
            )
        )

        overlay = (
            overlay_heatmap(
                original_image,
                heatmap
            )
        )

        gradcam_items.append({
            "condition": condition,
            "confidence": confidence,
            "threshold": threshold,
            "overlay": overlay
        })

    # =====================================================
    # STEP 8: Save one combined Grad-CAM summary
    # =====================================================

    summary_path = (
        save_gradcam_summary(
            original_image,
            gradcam_items,
            image_name
        )
    )

    # =====================================================
    # STEP 9: Return structured result
    # =====================================================

    return {
        "image_path": image_path,
        "quality": quality_info,
        "predictions": results,
        "gradcam_summary": summary_path
    }


# =========================================================
# Main local testing
# =========================================================

if __name__ == "__main__":

    # -----------------------------------------------------
    # LOCAL TESTING ONLY
    #
    # In the final Flutter + FastAPI system,
    # this path will be replaced by the image
    # uploaded by the Pet Owner.
    # -----------------------------------------------------

    IMAGE_PATH = os.path.join(
        BASE_DIR,
        "fyp final dataset",
        "images",
        "cat_0741.jpg"
    )

    analysis_result = (
        run_automatic_gradcam(
            IMAGE_PATH
        )
    )

    if (
        analysis_result
        is not None
    ):

        print(
            "\n==================================="
        )

        print(
            "Analysis completed successfully."
        )

        print(
            "==================================="
        )

        print(
            "\nGrad-CAM summary:"
        )

        print(
            analysis_result[
                "gradcam_summary"
            ]
        )