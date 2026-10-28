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