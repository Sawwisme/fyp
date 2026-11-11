import math


def extract_segmentation_metrics(segmentation):
    if not isinstance(segmentation, dict):
        segmentation = {}

    result = {
        "basis": "analysed_image_pixels",
    }

    for key in (
        "gingivitis_area_percent",
        "calculus_area_percent",
        "total_disease_area_percent",
    ):
        value = segmentation.get(key)

        valid = (
            type(value) in (int, float)
            and math.isfinite(value)
            and 0 <= value <= 100
        )

        result[key] = round(float(value), 2) if valid else None

    return result