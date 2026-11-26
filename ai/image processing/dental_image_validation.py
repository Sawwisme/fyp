"""Shared quality/preprocessing/content checks; importing does not load models."""
import cv2
import numpy as np

IMAGE_SIZE = (224, 224)
MIN_WIDTH = 150
MIN_HEIGHT = 150
BLUR_THRESHOLD = 25.0
MIN_BRIGHTNESS = 25
MAX_BRIGHTNESS = 235
DENTAL_CONTENT_THRESHOLD = 0.7

def validate_image_quality(image_path):
    image = cv2.imread(image_path)

    if image is None:
        return (
            False,
            "We couldn't open this photo. Choose another "
            "original JPG or PNG image.",
        )

    height, width = image.shape[:2]

    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return (
            False,
            "This photo is too small to assess clearly. "
            "Use the original photo or take a new close-up "
            "instead of enlarging this image.",
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(
        gray, cv2.CV_64F
    ).var()

    if blur_score < BLUR_THRESHOLD:
        return (
            False,
            "The teeth and gums aren't clear enough in this "
            "photo. Hold the camera steady, tap to focus on "
            "the teeth, and retake it.",
        )

    brightness = float(np.mean(gray))

    if brightness < MIN_BRIGHTNESS:
        return (
            False,
            "This photo is too dark to assess reliably. "
            "Move to a brighter area and retake it with "
            "the teeth and gumline visible.",
        )

    if brightness > MAX_BRIGHTNESS:
        return (
            False,
            "This photo is too bright to assess reliably. "
            "Avoid direct flash or glare and retake it "
            "in softer lighting.",
        )

    quality_info = {
        "width": width,
        "height": height,
        "blur_score": blur_score,
        "brightness": brightness,
    }

    return True, quality_info

def load_image(image_path):
    import tensorflow as tf
    image = tf.io.read_file(image_path)
    image = tf.image.decode_image(image, channels=3, expand_animations=False)
    original_image = image.numpy()
    image = tf.image.resize(image, IMAGE_SIZE)
    image = tf.cast(image, tf.float32)
    input_image = tf.expand_dims(image, axis=0)
    return (original_image, input_image)

def validate_pet_dental_content(input_image, dental_validator_model):
    if dental_validator_model is None:
        return (None, 'Dental content validation skipped because the validator model has not been trained yet.')
    prediction = dental_validator_model.predict(input_image, verbose=0)
    score = float(np.squeeze(prediction))
    if not np.isfinite(score) or not 0 <= score <= 1:
        raise ValueError('Invalid dental validation score.')
    if score < DENTAL_CONTENT_THRESHOLD:
        return (False, f'The uploaded image does not appear to contain a suitable cat or dog dental region (dental confidence={score:.4f}).')
    return (True, f'Pet dental image detected (confidence={score:.4f}).')
