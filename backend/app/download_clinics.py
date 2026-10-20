import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.clinic_discovery_service import normalize_clinic


STATE_CODES = {
    "Johor": "MY-01",
    "Kedah": "MY-02",
    "Kelantan": "MY-03",
    "Melaka": "MY-04",
    "Negeri Sembilan": "MY-05",
    "Pahang": "MY-06",
    "Pulau Pinang": "MY-07",
    "Perak": "MY-08",
    "Perlis": "MY-09",
    "Selangor": "MY-10",
    "Terengganu": "MY-11",
    "Sabah": "MY-12",
    "Sarawak": "MY-13",
    "W.P. Kuala Lumpur": "MY-14",
    "W.P. Labuan": "MY-15",
    "W.P. Putrajaya": "MY-16",
}

DATA_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "data" / "clinics"
)


def download(state):
    code = STATE_CODES[state]

    query = (
        '[out:json][timeout:90];'
        f'area["ISO3166-2"="{code}"]->.state;'
        'nwr["amenity"="veterinary"](area.state);'
        'out center;'
    )

    request = Request(
        os.getenv(
            "OSM_OVERPASS_URL",
            "https://overpass-api.de/api/interpreter",
        ),
        data=urlencode({"data": query}).encode("utf-8"),
        headers={
            "User-Agent": "VetDental-FYP/1.0",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    print(f"Downloading clinics for {state}...", flush=True)

    with urlopen(request, timeout=120) as response:
        raw = response.read(10_000_001)

    if len(raw) > 10_000_000:
        raise ValueError("Download exceeded the size limit.")

    payload = json.loads(raw.decode("utf-8"))

    if (
        not isinstance(payload, dict)
        or payload.get("remark")
        or not isinstance(payload.get("elements"), list)
    ):
        raise ValueError("The map service returned incomplete data.")

    clinics = {}

    for element in payload["elements"]:
        if not isinstance(element, dict):
            continue

        clinic = normalize_clinic(element)

        if clinic is not None:
            identity = (
                clinic["osm_type"],
                clinic["osm_id"],
            )
            clinics[identity] = clinic

    if not clinics:
        raise ValueError(
            "No clinics returned. Existing saved data was kept."
        )

    records = sorted(
        clinics.values(),
        key=lambda clinic: clinic["clinic_name"].casefold(),
    )

    document = {
        "state": state,
        "state_code": code,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "source": "OpenStreetMap contributors",
        "clinics": records,
    }

    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)

    destination = DATA_DIRECTORY / f"{code}.json"
    temporary = destination.with_suffix(".json.tmp")

    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(destination)

    print(f"Saved {len(records)} clinics.")
    print(f"File: {destination}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--state",
        required=True,
        choices=list(STATE_CODES),
    )
    arguments = parser.parse_args()

    try:
        download(arguments.state)
    except (URLError, TimeoutError, ValueError, OSError) as error:
        print(f"Download failed: {type(error).__name__}: {error}")
        print("Existing saved clinic files were not replaced.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()