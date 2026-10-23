import os
import random
import cv2
import numpy as np
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

IMAGE_DIR = os.path.join(
    BASE_DIR,
    "segmentation dataset",
    "train",
    "images"
)

MASK_DIR = os.path.join(
    BASE_DIR,
    "segmentation dataset",
    "train",
    "masks"
)

NUM_SAMPLES = 6
SEED = 42

random.seed(SEED)

# Find images with masks
samples = []

for filename in os.listdir(IMAGE_DIR):

    if filename.lower().endswith(
        (".jpg", ".jpeg", ".png")
    ):

        name = os.path.splitext(
            filename
        )[0]

        mask_path = os.path.join(
            MASK_DIR,
            f"{name}.png"
        )

        if os.path.exists(mask_path):
            samples.append(filename)

selected = random.sample(
    samples,
    min(NUM_SAMPLES, len(samples))
)

for filename in selected:

    image_path = os.path.join(
        IMAGE_DIR,
        filename
    )

    name = os.path.splitext(
        filename
    )[0]

    mask_path = os.path.join(
        MASK_DIR,
        f"{name}.png"
    )

    image = cv2.imread(image_path)
    image = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2RGB
    )

    mask = cv2.imread(
        mask_path,
        cv2.IMREAD_GRAYSCALE
    )

    # Visualization mask only
    visual_mask = np.zeros(
        (
            mask.shape[0],
            mask.shape[1],
            3
        ),
        dtype=np.uint8
    )

    # Gingivitis = red
    visual_mask[
        mask == 1
    ] = [255, 0, 0]

    # Calculus = green
    visual_mask[
        mask == 2
    ] = [0, 255, 0]

    overlay = cv2.addWeighted(
        image,
        0.65,
        visual_mask,
        0.35,
        0
    )

    plt.figure(
        figsize=(15, 5)
    )

    plt.subplot(
        1,
        3,
        1
    )

    plt.imshow(image)
    plt.title("Original")
    plt.axis("off")

    plt.subplot(
        1,
        3,
        2
    )

    plt.imshow(visual_mask)
    plt.title(
        "Mask\nRed = Gingivitis | Green = Calculus"
    )
    plt.axis("off")

    plt.subplot(
        1,
        3,
        3
    )

    plt.imshow(overlay)
    plt.title("Overlay")
    plt.axis("off")

    plt.tight_layout()
    plt.show()