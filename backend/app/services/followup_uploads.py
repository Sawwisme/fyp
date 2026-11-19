import logging
from tempfile import TemporaryDirectory
from threading import Event, Lock
from app.services.model_process_client import ModelProcessClient
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000

# Outside the publicly served web directory.
UPLOAD_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "private_uploads"
    / "followups"
)


def prepare_photo(upload: UploadFile) -> bytes:
    raw = upload.file.read(MAX_FILE_BYTES + 1)

    if not raw:
        raise HTTPException(422, "The uploaded image is empty.")

    if len(raw) > MAX_FILE_BYTES:
        raise HTTPException(
            413,
            "Each photo must be 8 MB or smaller.",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            with Image.open(BytesIO(raw)) as original:
                if original.format not in {"JPEG", "PNG", "WEBP"}:
                    raise HTTPException(
                        422,
                        "Use JPEG, PNG or WebP photos.",
                    )

                if (
                    original.width * original.height
                    > MAX_IMAGE_PIXELS
                ):
                    raise HTTPException(
                        422,
                        "The photo is too large. "
                        "Choose a smaller image.",
                    )

                original.load()
                image = ImageOps.exif_transpose(original)
                image.thumbnail((2000, 2000))

                # Flatten transparency onto white and strip metadata.
                rgba = image.convert("RGBA")
                clean = Image.new("RGB", rgba.size, "white")
                clean.paste(rgba, mask=rgba.getchannel("A"))

                output = BytesIO()
                clean.save(
                    output,
                    format="JPEG",
                    quality=85,
                    optimize=True,
                )

                return output.getvalue()

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise HTTPException(
            422,
            "The photo could not be read. Choose another image.",
        ) from error


def save_photo(content: bytes) -> str:
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}.jpg"
    target = UPLOAD_DIRECTORY / filename

    try:
        with target.open("xb") as output:
            output.write(content)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    return filename

# A single validation-only child process per API process. Requests are serialised
# because ModelProcessClient's JSON-lines protocol is not multiplexed.
_validation_lock = Lock()
_validation_client = None
_validation_stopping = Event()
_validation_logger = logging.getLogger(__name__)


def close_followup_validator():
    global _validation_client
    _validation_stopping.set()
    with _validation_lock:
        if _validation_client is not None:
            _validation_client.close()
            _validation_client = None


def validate_prepared_photos(photos):
    global _validation_client
    if not photos:
        return
    if len(photos) > 4:
        raise HTTPException(422, "Submit up to four photos at a time.")
    if _validation_stopping.is_set():
        raise HTTPException(503, "Photo validation is stopping. Please try again later.")
    if not _validation_lock.acquire(timeout=5):
        raise HTTPException(503, "Photo validation is busy. Please try again shortly.")
    try:
        if _validation_stopping.is_set():
            raise HTTPException(503, "Photo validation is stopping. Please try again later.")
        if _validation_client is None:
            runner = (Path(__file__).resolve().parents[3]
                      / "ai" / "image processing" / "followup_validation_runner.py")
            _validation_client = ModelProcessClient(runner, timeout=120)

        with TemporaryDirectory(prefix="vetdental-followup-") as directory:
            folder = Path(directory)
            for index, content in enumerate(photos, 1):
                (folder / f"photo-{index}.jpg").write_bytes(content)
            result = _validation_client.run(
                folder, folder, _validation_stopping,
            )

        if result.get("status") == "rejected":
            index = result.get("photo_index")
            message = result.get("message")
            if type(index) is not int or not 1 <= index <= len(photos):
                raise RuntimeError("Invalid validation response.")
            if not isinstance(message, str) or not message.strip():
                raise RuntimeError("Missing photo validation explanation.")
            raise HTTPException(422, f"Photo {index}: {message[:400]}")

        details = result.get("result")
        if (result.get("status") != "completed"
                or not isinstance(details, dict)
                or type(details.get("validated_images")) is not int
                or details["validated_images"] != len(photos)):
            raise RuntimeError("Incomplete photo validation.")
    except HTTPException:
        raise
    except Exception:
        _validation_logger.exception("Follow-up photo validation unavailable")
        if _validation_client is not None:
            _validation_client.close()
            _validation_client = None
        raise HTTPException(
            503, "Photo validation could not be completed. Please try again shortly."
        ) from None
    finally:
        _validation_lock.release()
