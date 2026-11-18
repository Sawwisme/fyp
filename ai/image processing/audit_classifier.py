import csv
import hashlib
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageOps


BASE = Path(__file__).resolve().parent
DATASET = BASE / "fyp final dataset"
IMAGE_DIR = DATASET / "images"
LABEL_FILE = DATASET / "labels_split.csv"

OUTPUT = (
    BASE
    / "classifier_audit"
    / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
)

CONDITIONS = [
    "healthy",
    "plaque",
    "gingivitis",
    "calculus",
]

VALID_SPLITS = {"train", "validation", "test"}


def save_csv(name, fields, rows):
    with (OUTPUT / name).open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def difference_hash(image):
    small = image.convert("L").resize(
        (9, 8),
        Image.Resampling.LANCZOS,
    )
    pixels = [
        small.getpixel((x, y))
        for y in range(8)
        for x in range(9)
    ]

    result = 0

    for y in range(8):
        for x in range(8):
            result = (result << 1) | int(
                pixels[y * 9 + x] > pixels[y * 9 + x + 1]
            )

    return result


def known_labels(row):
    result = {}

    for condition in CONDITIONS:
        value = row[condition].strip()
        mask = row[f"mask_{condition}"].strip()

        if value not in {"0", "1"} or mask not in {"0", "1"}:
            raise ValueError(
                f"Invalid label or mask for {condition}"
            )

        # Unknown labels must not become negative examples.
        result[condition] = int(value) if mask == "1" else None

    return result


def label_disagreements(first, second):
    return [
        condition
        for condition in CONDITIONS
        if first["known"][condition] is not None
        and second["known"][condition] is not None
        and first["known"][condition]
        != second["known"][condition]
    ]


def pair_record(first, second, kind, distance=""):
    disagreements = label_disagreements(first, second)

    return {
        "filename_a": first["filename"],
        "split_a": first["split"],
        "species_a": first["species"],
        "filename_b": second["filename"],
        "split_b": second["split"],
        "species_b": second["species"],
        "cross_split": first["split"] != second["split"],
        "kind": kind,
        "hash_distance": distance,
        "known_label_disagreements": ", ".join(disagreements),
        "species_disagreement": first["species"] != second["species"],
    }


def main():
    with LABEL_FILE.open(
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        required = {
            "filename",
            "species",
            "split",
            *CONDITIONS,
            *(f"mask_{name}" for name in CONDITIONS),
        }

        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                "Missing CSV columns: " + ", ".join(sorted(missing))
            )

        rows = list(reader)

    OUTPUT.mkdir(parents=True, exist_ok=False)

    issues = []
    records = []
    seen_names = defaultdict(list)
    counts = defaultdict(lambda: [0, 0])
    root = IMAGE_DIR.resolve()

    for line, row in enumerate(rows, start=2):
        filename = row["filename"].strip()
        split = row["split"].strip().lower()
        species = row["species"].strip().lower()

        seen_names[filename].append(split)

        def issue(message):
            issues.append({
                "csv_line": line,
                "filename": filename,
                "split": split,
                "issue": message,
            })

        if split not in VALID_SPLITS:
            issue("Invalid split")
            continue

        if species not in {"cat", "dog"}:
            issue("Unknown species")
            continue

        try:
            known = known_labels(row)
        except ValueError as error:
            issue(str(error))
            continue

        source = row.get("sources", "unknown")
        key = (split, species, source)
        counts[key][0] += 1
        counts[key][1] += int(known["healthy"] == 1)

        positive_diseases = [
            name
            for name in CONDITIONS[1:]
            if known[name] == 1
        ]

        if known["healthy"] == 1 and positive_diseases:
            issue(
                "Healthy-positive and known disease-positive: "
                + ", ".join(positive_diseases)
            )

        path = (root / filename).resolve()

        if not path.is_relative_to(root) or not path.is_file():
            issue("Missing image or invalid image path")
            continue

        try:
            with Image.open(path) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")

                digest = hashlib.sha256()
                digest.update(str(image.size).encode("ascii"))
                digest.update(image.tobytes())

                record = {
                    "filename": filename,
                    "split": split,
                    "species": species,
                    "known": known,
                    "pixel_hash": digest.hexdigest(),
                    "hash": difference_hash(image),
                    "mirror_hash": difference_hash(
                        ImageOps.mirror(image)
                    ),
                }

                records.append(record)

        except Exception as error:
            issue(f"Image could not be read: {type(error).__name__}")

    for filename, splits in seen_names.items():
        if len(splits) > 1:
            issues.append({
                "csv_line": "",
                "filename": filename,
                "split": ", ".join(splits),
                "issue": "Repeated filename in label CSV",
            })

    exact_pairs = []
    similar_pairs = []

    for first, second in combinations(records, 2):
        if first["pixel_hash"] == second["pixel_hash"]:
            exact_pairs.append(
                pair_record(first, second, "identical_pixels")
            )
            continue

        distance = min(
            (first["hash"] ^ second["hash"]).bit_count(),
            (first["hash"] ^ second["mirror_hash"]).bit_count(),
        )

        # Review candidates only: similarity is not proof of duplication.
        if distance <= 4:
            similar_pairs.append(
                pair_record(
                    first,
                    second,
                    "visual_similarity_candidate",
                    distance,
                )
            )

    pair_fields = [
        "filename_a", "split_a", "species_a",
        "filename_b", "split_b", "species_b",
        "cross_split", "kind", "hash_distance",
        "known_label_disagreements",
        "species_disagreement",
    ]

    save_csv(
        "label_and_file_issues.csv",
        ["csv_line", "filename", "split", "issue"],
        issues,
    )
    save_csv("exact_duplicate_pairs.csv", pair_fields, exact_pairs)
    save_csv("similar_image_pairs.csv", pair_fields, similar_pairs)

    distribution = [
        {
            "split": split,
            "species": species,
            "source": source,
            "images": count[0],
            "healthy_images": count[1],
        }
        for (split, species, source), count in sorted(counts.items())
    ]

    save_csv(
        "source_distribution.csv",
        ["split", "species", "source", "images", "healthy_images"],
        distribution,
    )

    print("CSV rows:", len(rows))
    print("Readable image records:", len(records))
    print("Label/file issues:", len(issues))
    print("Exact duplicate pairs:", len(exact_pairs))
    print(
        "Exact duplicate pairs across splits:",
        sum(pair["cross_split"] for pair in exact_pairs),
    )
    print("Visual similarity candidates:", len(similar_pairs))
    print(
        "Similarity candidates across splits:",
        sum(pair["cross_split"] for pair in similar_pairs),
    )
    print("Reports:", OUTPUT)
    print("Original images, labels and models were not changed.")
    print("Review similarity candidates before treating them as duplicates.")


if __name__ == "__main__":
    main()