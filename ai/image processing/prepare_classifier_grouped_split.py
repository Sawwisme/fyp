import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.model_selection import GroupShuffleSplit


BASE = Path(__file__).resolve().parent
DATASET = BASE / "fyp final dataset"

AUDIT = (
    BASE
    / "classifier_audit"
    / "20261117_123558_755403"
)

OUTPUT = (
    BASE
    / "classifier_grouped_split"
    / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
)

CONDITIONS = [
    "healthy",
    "plaque",
    "gingivitis",
    "calculus",
]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), reader.fieldnames


def write_csv(path, rows, fields):
    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    rows, original_fields = read_csv(
        DATASET / "labels_split.csv"
    )

    filenames = [row["filename"] for row in rows]

    if len(filenames) != len(set(filenames)):
        raise ValueError(
            "Duplicate filenames in label CSV. Resolve them first."
        )

    issues, _ = read_csv(
        AUDIT / "label_and_file_issues.csv"
    )

    if issues:
        raise ValueError(
            "The audit contains label/file issues. Resolve them first."
        )

    parent = {name: name for name in filenames}

    def find(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(first, second):
        first = find(first)
        second = find(second)

        if first != second:
            parent[second] = first

    # Conservative grouping: similarity candidates stay together.
    # This does not assert that every candidate pair is a duplicate.
    for report in (
        "exact_duplicate_pairs.csv",
        "similar_image_pairs.csv",
    ):
        pairs, _ = read_csv(AUDIT / report)

        for pair in pairs:
            first = pair["filename_a"]
            second = pair["filename_b"]

            if first not in parent or second not in parent:
                raise ValueError(
                    "Audit filenames do not match the current dataset."
                )

            union(first, second)

    groups = defaultdict(list)

    for row in rows:
        groups[find(row["filename"])].append(row)

    usable = []
    quarantined = []
    conflicting_groups = 0

    for root, members in groups.items():
        reasons = []

        if len({row["species"] for row in members}) > 1:
            reasons.append("species disagreement")

        for condition in CONDITIONS:
            known_values = {
                row[condition]
                for row in members
                if row[f"mask_{condition}"] == "1"
            }

            if len(known_values) > 1:
                reasons.append(
                    f"known {condition} label disagreement"
                )

        group_id = f"group:{root}"

        if reasons:
            conflicting_groups += 1

        for row in members:
            item = dict(row)
            item["previous_split"] = row["split"]
            item["group_id"] = group_id

            if reasons:
                item["exclusion_reason"] = "; ".join(reasons)
                quarantined.append(item)
            else:
                usable.append(item)

    if len({row["group_id"] for row in usable}) < 10:
        raise ValueError("Too few usable groups for splitting.")

    indices = np.arange(len(usable))
    group_ids = np.array([
        row["group_id"] for row in usable
    ])

    # Approximately 70% train, 15% validation, 15% test.
    # Fractions are assigned by group, so image counts vary.
    train_validation, test = next(
        GroupShuffleSplit(
            n_splits=1,
            test_size=0.15,
            random_state=42,
        ).split(indices, groups=group_ids)
    )

    train_local, validation_local = next(
        GroupShuffleSplit(
            n_splits=1,
            test_size=0.15 / 0.85,
            random_state=43,
        ).split(
            train_validation,
            groups=group_ids[train_validation],
        )
    )

    assignments = {
        "train": train_validation[train_local],
        "validation": train_validation[validation_local],
        "test": test,
    }

    for split, selected_indices in assignments.items():
        for index in selected_indices:
            usable[index]["split"] = split

    group_splits = defaultdict(set)

    for row in usable:
        group_splits[row["group_id"]].add(row["split"])

    if any(len(splits) != 1 for splits in group_splits.values()):
        raise AssertionError("A group crosses dataset splits.")

    OUTPUT.mkdir(parents=True, exist_ok=False)

    fields = original_fields + ["previous_split", "group_id"]

    write_csv(
        OUTPUT / "labels_grouped_split.csv",
        usable,
        fields,
    )

    write_csv(
        OUTPUT / "quarantined_groups.csv",
        quarantined,
        fields + ["exclusion_reason"],
    )

    print("Original images:", len(rows))
    print("Usable images:", len(usable))
    print("Excluded candidate groups:", conflicting_groups)
    print("Images in excluded groups:", len(quarantined))

    for split in ("train", "validation", "test"):
        selected = [
            row for row in usable
            if row["split"] == split
        ]

        healthy = Counter(
            row["species"]
            for row in selected
            if row["healthy"] == "1"
            and row["mask_healthy"] == "1"
        )

        print(
            f"{split}: {len(selected)} images; "
            f"healthy cats={healthy['cat']}; "
            f"healthy dogs={healthy['dog']}"
        )

    print("Cross-split candidate groups: 0")
    print("Output:", OUTPUT)
    print("Original dataset, labels and model were not changed.")


if __name__ == "__main__":
    main()