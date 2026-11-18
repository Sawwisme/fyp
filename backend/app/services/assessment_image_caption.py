from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo


def _font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass

    return ImageFont.load_default()


def _wrap(draw, text, font, width):
    lines = []
    current = ""

    for word in text.split():
        candidate = f"{current} {word}".strip()

        if current and draw.textlength(
            candidate,
            font=font,
        ) > width:
            lines.append(current)
            current = word
        else:
            current = candidate

    if current:
        lines.append(current)

    return lines


def caption_assessment_image(path, summary, image_kind):
    path = Path(path)
    decision = summary.get("decision") or {}
    severity = summary.get("severity") or {}

    status = decision.get("status")

    if status == "inconclusive":
        title = "INCONCLUSIVE - no overall severity assigned"
        colour = "#FFF0D5"
    elif status == "healthy_pattern":
        title = "SCREENING RESULT - no supported disease flags"
        colour = "#E8F4EE"
    elif status == "disease_flags":
        title = (
            "EXPERIMENTAL SEVERITY: "
            + str(severity.get("label", "Unavailable"))
        )
        colour = "#EAF0FF"
    else:
        title = "INTERPRETATION UNAVAILABLE"
        colour = "#EEF0F4"

    meanings = {
        "heatmap": (
            "Heatmap colours show classifier attention, "
            "not disease severity or confirmed disease locations."
        ),
        "segmentation": (
            "Red: segmentation-predicted gingivitis regions. "
            "Yellow: segmentation-predicted calculus regions. "
            "Segmentation is a separate model and does not override "
            "classifier coverage or veterinary findings."
        ),
        "summary": (
            "Heatmap: classifier attention. "
            "Red outlines: segmentation-predicted gingivitis regions. "
            "Yellow outlines: segmentation-predicted calculus regions. "
            "Segmentation is a separate model and does not override "
            "classifier coverage or veterinary findings."
        ),
    }

    not_assessed = decision.get("not_assessed_conditions", [])

    if isinstance(not_assessed, list):
        names = [
            name
            for name in not_assessed
            if isinstance(name, str)
        ]

        if names:
            coverage_note = (
                " Classifier not assessed: "
                + ", ".join(names)
                + ". Any displayed segmentation regions do not "
                "constitute a classifier finding for these conditions."
            )

            meanings = {
                kind: text + coverage_note
                for kind, text in meanings.items()
            }

    with Image.open(path) as source:
        # Avoid stacking the caption if the helper is called twice.
        if source.info.get("vetdental_caption") == "v1":
            return

        image = source.convert("RGB")

    width = image.width
    padding = max(16, width // 45)

    title_font = _font(max(16, min(34, width // 38)))
    body_font = _font(max(12, min(24, width // 55)))

    draw = ImageDraw.Draw(image)

    body = (
        str(decision.get("reason") or "")
        + " "
        + meanings.get(image_kind, "")
    ).strip()

    title_lines = _wrap(
        draw, title, title_font, width - 2 * padding
    )
    body_lines = _wrap(
        draw, body, body_font, width - 2 * padding
    )

    title_height = title_font.getbbox("Ag")[3] + 10
    body_height = body_font.getbbox("Ag")[3] + 8

    header_height = (
        padding * 2
        + len(title_lines) * title_height
        + 8
        + len(body_lines) * body_height
    )

    canvas = Image.new(
        "RGB",
        (width, image.height + header_height),
        colour,
    )
    canvas.paste(image, (0, header_height))

    draw = ImageDraw.Draw(canvas)
    y = padding

    for line in title_lines:
        draw.text(
            (padding, y),
            line,
            font=title_font,
            fill="#172333",
        )
        y += title_height

    y += 8

    for line in body_lines:
        draw.text(
            (padding, y),
            line,
            font=body_font,
            fill="#34435A",
        )
        y += body_height

    metadata = PngInfo()
    metadata.add_text("vetdental_caption", "v1")

    temporary = path.with_name(path.stem + ".caption.tmp.png")

    try:
        canvas.save(temporary, format="PNG", pnginfo=metadata)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)