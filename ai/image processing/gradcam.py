import os
import cv2
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from classification_policy import apply_species_policy

class ImageValidationError(ValueError):
    def __init__(self, stage, message):
        super().__init__(message)
        self.stage = stage


# =========================================================
# Configuration
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "dental_classifier_grouped_candidate.keras"
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
    "plaque": 0.35,
    "gingivitis": 0.60,
    "calculus": 0.80,
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
# Calculate Grad-CAM attention spread
# =========================================================

def calculate_gradcam_spread(
    heatmap,
    activation_threshold=0.5
):
    """
    Calculate percentage of strongly activated
    Grad-CAM pixels.

    heatmap must be normalized to 0-1.
    """

    heatmap = np.asarray(
        heatmap,
        dtype=np.float32
    )

    heatmap = np.clip(
        heatmap,
        0.0,
        1.0
    )

    active_pixels = np.sum(
        heatmap >= activation_threshold
    )

    total_pixels = heatmap.size

    if total_pixels == 0:
        return 0.0

    spread_percent = (
        active_pixels
        / total_pixels
        * 100.0
    )

    return round(
        float(spread_percent),
        2
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
    image_name,
):
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable

    palette = {
        "plaque": "#32d9ff",
        "gingivitis": "#ff596e",
        "calculus": "#ffd43b",
    }

    height, width = original_image.shape[:2]

    items = [
        item for item in gradcam_items
        if item["condition"] in palette
        and item["confidence"] >= item["threshold"]
    ]

    maps = []

    for item in items:
        heatmap = np.asarray(
            item["heatmap"],
            dtype=np.float32,
        )

        heatmap = np.nan_to_num(
            heatmap,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )

        heatmap = cv2.resize(
            heatmap,
            (width, height),
        )

        maps.append(np.clip(heatmap, 0.0, 1.0))

    original = original_image.astype(np.float32) / 255.0

    if maps:
        # Preserve the strongest attention at each pixel.
        merged = np.max(np.stack(maps), axis=0)
        heatmap_colour = plt.get_cmap("jet")(merged)[..., :3]

        display_image = np.clip(
            original * 0.65 + heatmap_colour * 0.35,
            0.0,
            1.0,
        )
    else:
        display_image = original

    fig, ax = plt.subplots(figsize=(10, 9))

    ax.imshow(display_image)
    ax.axis("off")
    ax.set_title(
        "Combined Grad-CAM heatmap",
        fontsize=17,
        pad=15,
    )

    boxes = []

    for item, heatmap in zip(items, maps):
        condition = item["condition"]
        colour = palette[condition]

        active = (heatmap >= 0.6).astype(np.uint8)

        contours, _ = cv2.findContours(
            active,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        contours = [
            contour for contour in contours
            if cv2.contourArea(contour)
            >= height * width * 0.002
        ]

        if not contours:
            continue

        # Show the strongest substantial region for each condition.
        contour = max(contours, key=cv2.contourArea)
        x, y, box_width, box_height = cv2.boundingRect(contour)

        ax.add_patch(
            plt.Rectangle(
                (x, y),
                box_width,
                box_height,
                fill=False,
                edgecolor=colour,
                linewidth=1.8,
                linestyle=(
                    "--" if condition == "calculus" else "-"
                ),
            )
        )

        boxes.append((
            condition,
            x,
            y,
            box_width,
            box_height,
        ))

    if maps:
        colour_bar = fig.colorbar(
            ScalarMappable(
                norm=Normalize(0, 1),
                cmap="jet",
            ),
            ax=ax,
            fraction=0.04,
            pad=0.025,
            shrink=0.8,
        )

        colour_bar.set_ticks([0, 0.5, 1])
        colour_bar.set_ticklabels([
            "Lower",
            "Medium",
            "Higher",
        ])
        colour_bar.set_label(
            "Relative model attention",
            labelpad=10,
        )

    if items:
        score_text = "   |   ".join(
            f'{item["condition"].capitalize()}: '
            f'{item["confidence"]:.1%}'
            for item in items
        )

        fig.text(
            0.5,
            0.078,
            "Model scores — " + score_text,
            ha="center",
            fontsize=10,
        )
    else:
        fig.text(
            0.5,
            0.078,
            "No disease prediction exceeded its threshold.",
            ha="center",
            fontsize=10,
        )

    fig.text(
        0.5,
        0.045,
        "Boxes identify model-attention regions, "
        "not confirmed disease locations.",
        ha="center",
        fontsize=9,
    )

    fig.text(
        0.5,
        0.024,
        "Heatmap colours indicate relative attention, "
        "not disease type or severity.",
        ha="center",
        fontsize=9,
    )

    fig.tight_layout(rect=(0, 0.12, 1, 1))

    # Place labels after fixing the layout, so collision checks
    # use their actual displayed dimensions.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    image_bounds = ax.get_window_extent(renderer)
    placed_labels = []

    for condition, x, y, box_width, box_height in boxes:
        colour = palette[condition]
        placed = False

        # Prefer beside the box. Use an inside position if
        # there is insufficient space near an image edge.
        anchors = [
            (x + box_width + 6, y + 5, "left"),
            (x - 6, y + 5, "right"),
            (
                min(x + box_width - 8, width - 8),
                y + 8,
                "right",
            ),
            (max(x + 8, 8), y + 8, "left"),
        ]

        for shift in (0, 24, 48, 72, 96):
            for text_x, text_y, alignment in anchors:
                label = ax.text(
                    text_x,
                    text_y + shift,
                    f"{condition.capitalize()} attention",
                    ha=alignment,
                    va="top",
                    fontsize=10,
                    color="white",
                    bbox={
                        "boxstyle": "round,pad=0.35",
                        "facecolor": "#162331",
                        "edgecolor": colour,
                        "linewidth": 1.5,
                        "alpha": 0.96,
                    },
                )

                fig.canvas.draw()

                bounds = (
                    label.get_bbox_patch()
                    .get_window_extent(renderer)
                )

                fits = (
                    bounds.x0 >= image_bounds.x0
                    and bounds.x1 <= image_bounds.x1
                    and bounds.y0 >= image_bounds.y0
                    and bounds.y1 <= image_bounds.y1
                )

                overlaps = any(
                    bounds.overlaps(previous)
                    for previous in placed_labels
                )

                if fits and not overlaps:
                    placed_labels.append(
                        bounds.expanded(1.03, 1.15)
                    )
                    placed = True
                    break

                label.remove()

            if placed:
                break

        if not placed:
            print(
                f"Label omitted due to limited space: {condition}"
            )

    output_path = os.path.join(
        OUTPUT_DIR,
        f"{image_name}_gradcam_summary.png",
    )

    fig.savefig(
        output_path,
        dpi=160,
        bbox_inches="tight",
    )
    plt.close(fig)

    print("Combined Grad-CAM saved:", output_path)
    return output_path

# =========================================================
# Automatic dental analysis
# =========================================================

def run_automatic_gradcam(
    image_path,
    raise_on_rejection=False,
    species=None,
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

        if raise_on_rejection:
            raise ImageValidationError("file", message)

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

        if raise_on_rejection:
            raise ImageValidationError("quality", quality_info)

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

        if raise_on_rejection:
            raise ImageValidationError("content", dental_message)

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

       # STEP 5: Classification and species coverage
    predictions = model.predict(
        input_image,
        verbose=0,
    )[0]

    raw_results = {}

    for i, label in enumerate(LABELS):
        confidence = float(predictions[i])
        threshold = float(THRESHOLDS[label])

        raw_results[label] = {
            "confidence": confidence,
            "threshold": threshold,
            "positive": confidence >= threshold,
        }

    results = apply_species_policy(raw_results, species)

    # STEP 6: Only assessed, positive conditions get Grad-CAM.
    # Do not fall back to an unsupported or below-threshold class.
    positive_conditions = []

    for i, label in enumerate(LABELS):
        item = results[label]

        if not item["assessed"]:
            status = "NOT ASSESSED"
        elif item["positive"] is True:
            status = "POSITIVE"
            positive_conditions.append((
                label,
                item["confidence"],
                item["threshold"],
                i,
            ))
        else:
            status = "NEGATIVE"

        print(
            f"{label:<12} "
            f"{item['confidence']:.4f} "
            f"(threshold={item['threshold']:.2f}) "
            f"{status}"
        )

    if not positive_conditions:
        print(
            "No supported classification passed its threshold. "
            "No class-specific heatmap will be generated."
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

# -----------------------------------------------------
# Calculate Grad-CAM attention spread
# -----------------------------------------------------

        gradcam_spread_percent = (
            calculate_gradcam_spread(
                heatmap,
                activation_threshold=0.5
            )
        )

        print(
            f"Grad-CAM attention spread: "
            f"{gradcam_spread_percent:.2f}%"
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
            "gradcam_spread_percent": gradcam_spread_percent,
            "overlay": overlay,
            "heatmap": heatmap,
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
    "gradcam_items": [
        {
            "condition": item["condition"],
            "confidence": item["confidence"],
            "threshold": item["threshold"],
            "gradcam_spread_percent":
                item["gradcam_spread_percent"]
        }
        for item in gradcam_items
    ],

    "_heatmaps": {
        item["condition"]: item["heatmap"]
        for item in gradcam_items
        if item["condition"] in {
            "plaque",
            "gingivitis",
            "calculus",
        }
        and item["confidence"] >= item["threshold"]
    },

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