import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

BASE = Path(__file__).resolve().parent
DATA = BASE / "segmentation grouped split"
REPORT = BASE / "segmentation_audit"
REPORT.mkdir(exist_ok=True)

groups = defaultdict(list)
hashes = defaultdict(list)
issues = []

for split in ("train", "validation", "test"):
    image_dir = DATA / split / "images"
    mask_dir = DATA / split / "masks"

    if not image_dir.is_dir():
        raise FileNotFoundError(image_dir)

    total = 0
    empty = 0

    for image_path in sorted(image_dir.iterdir()):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue

        total += 1
        filename = image_path.name
        reference = f"{split}/{filename}"

        original = re.sub(
            r"\.rf\.[a-fA-F0-9]+$",
            "",
            image_path.stem,
        )
        groups[original].append((split, reference))

        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        hashes[digest].append((split, reference))

        image = cv2.imread(str(image_path))
        mask_path = mask_dir / f"{image_path.stem}.png"
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

        if image is None:
            issues.append([split, filename, "Unreadable image"])
            continue

        if mask is None:
            issues.append([split, filename, "Missing/unreadable mask"])
            continue

        if image.shape[:2] != mask.shape:
            issues.append([split, filename, "Image/mask size mismatch"])

        labels = set(np.unique(mask).tolist())

        if not labels.issubset({0, 1, 2}):
            issues.append([
                split, filename, f"Unexpected mask values: {sorted(labels)}"
            ])
        elif labels == {0}:
            empty += 1
            issues.append([split, filename, "Empty mask: review annotation"])

    print(f"{split}: {total} images; {empty} empty masks")

with (REPORT / "mask_issues.csv").open(
    "w", newline="", encoding="utf-8-sig"
) as file:
    writer = csv.writer(file)
    writer.writerow(["split", "image", "issue"])
    writer.writerows(issues)

overlaps = []

for check, collection in (
    ("Same original filename", groups),
    ("Identical file contents", hashes),
):
    count = 0

    for entries in collection.values():
        if len({split for split, _ in entries}) > 1:
            count += 1
            overlaps.append(
                f"{check}:\n"
                + "\n".join(reference for _, reference in entries)
            )

    print(f"{check} across splits: {count} groups")

(REPORT / "cross_split_duplicates.txt").write_text(
    "\n\n".join(overlaps) or "No filename/exact-file overlaps found.",
    encoding="utf-8",
)

print(f"\nReports saved to: {REPORT}")
print("Empty masks need inspection; they are not automatically incorrect.")
print("This check does not detect all mirrored, cropped or similar images.")