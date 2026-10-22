import os
import sys
import numpy as np
import tensorflow as tf
import keras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "dental_image_validator.keras"
)

IMAGE_SIZE = (224, 224)

# Start with 0.5 for testing.
# We can tune this later based on test results.
THRESHOLD = 0.5


def load_image(image_path):
    img = tf.keras.utils.load_img(
        image_path,
        target_size=IMAGE_SIZE
    )

    img_array = tf.keras.utils.img_to_array(img)

    img_array = np.expand_dims(
        img_array,
        axis=0
    )

    return img_array


def predict_image(model, image_path):
    img_array = load_image(image_path)

    prediction = model.predict(
        img_array,
        verbose=0
    )[0][0]

    print("\n==============================")
    print("Dental Image Validator")
    print("==============================")
    print("Image:", image_path)
    print(f"Dental probability: {prediction:.4f}")

    if prediction >= THRESHOLD:
        print("Result: VALID PET DENTAL IMAGE")
    else:
        print("Result: INVALID / NON-DENTAL IMAGE")

    print("==============================")


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print(
            "Usage: python test_dental_validator.py <image_path>"
        )
        sys.exit()

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print("Image not found:", image_path)
        sys.exit()

    print("Loading model...")

    model = keras.models.load_model(
        MODEL_PATH
    )

    predict_image(
        model,
        image_path
    )