"""Validation-only JSON-lines process. Never loads classifier or segmentation."""
import argparse
from contextlib import redirect_stdout
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import sys

import dental_image_validation as validation

MODEL_PATH = Path(__file__).resolve().parent / "models/dental_image_validator.keras"


@lru_cache(maxsize=1)
def get_validator():
    with redirect_stdout(sys.stderr):
        import tensorflow as tf
        return tf.keras.models.load_model(MODEL_PATH, compile=False)


def validate_batch(directory):
    directory = Path(directory).resolve(strict=True)
    if not directory.is_dir():
        raise ValueError("A private image directory is required.")
    paths = sorted(directory.iterdir())
    if not 1 <= len(paths) <= 4:
        raise ValueError("Validate between one and four photos.")

    for index, path in enumerate(paths, 1):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".jpg":
            raise ValueError("Expected prepared JPEG photos.")
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("Prepared photo exceeds the size limit.")
        valid, message = validation.validate_image_quality(str(path))
        if not valid:
            return {"status": "rejected", "stage": "quality",
                    "photo_index": index, "message": str(message)}

    validator = get_validator()
    if validator is None:
        raise RuntimeError("Dental validator is unavailable.")

    for index, path in enumerate(paths, 1):
        _, image = validation.load_image(str(path))
        valid, _ = validation.validate_pet_dental_content(image, validator)
        if valid is None:
            raise RuntimeError("Dental validation could not be completed.")
        if not valid:
            return {
                "status": "rejected", "stage": "content", "photo_index": index,
                "message": (
                    "We couldn't identify a clear view of the teeth "
                    "and gums in this follow-up photo. Choose a closer, "
                    "well-lit dental photo so your vet can review the "
                    "area. Do not force your pet's mouth open."
                ),
            }
    return {"status": "completed", "result": {"validated_images": len(paths)}}


def serve():
    for line in sys.stdin:
        identifier = None
        try:
            request = json.loads(line)
            identifier = request["id"]
            with redirect_stdout(sys.stderr):
                response = validate_batch(request["image"])
        except Exception as error:
            print(f"Follow-up validation failed: {type(error).__name__}",
                  file=sys.stderr, flush=True)
            response = {"status": "failed"}
        print(json.dumps({"id": identifier, "response": response}, allow_nan=False),
              flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        missing = [name for name in ("tensorflow", "cv2", "numpy")
                   if importlib.util.find_spec(name) is None]
        print(json.dumps({
            "status": "ready" if not missing and MODEL_PATH.is_file() else "not_ready",
            "missing_packages": missing,
            "missing_models": [] if MODEL_PATH.is_file() else [MODEL_PATH.name],
            "models_loaded": False,
        }))
        return
    if not args.serve:
        parser.error("Use --serve or --check.")
    serve()


if __name__ == "__main__":
    main()
