import json
import math
import os
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pydantic import ValidationError
from app.schemas.clinic_discovery import ClinicSelectionData

import jwt
from fastapi import HTTPException

from app.config import JWT_ALGORITHM, JWT_ISSUER, JWT_SECRET_KEY
from app.schemas.clinic_discovery import DiscoveredClinic


OVERPASS_URL = os.getenv(
    "OSM_OVERPASS_URL",
    "https://overpass-api.de/api/interpreter",
)

SELECTION_AUDIENCE = "vetdental-clinic-selection"

_cache = OrderedDict()
_lock = Lock()
_last_request = float("-inf")
_search_running = False


def normalize_clinic(element: dict) -> dict | None:
    osm_type = element.get("type")
    osm_id = element.get("id")
    tags = element.get("tags") or {}

    if (
        osm_type not in {"node", "way", "relation"}
        or not isinstance(osm_id, int)
        or osm_id <= 0
        or tags.get("amenity") != "veterinary"
    ):
        return None

    coordinates = element if osm_type == "node" else element.get("center", {})

    try:
        latitude = float(coordinates["lat"])
        longitude = float(coordinates["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None

    street = " ".join(
        str(tags.get(key) or "").strip()
        for key in ("addr:housenumber", "addr:street")
    ).strip()

    address_parts = [
        street,
        str(tags.get("addr:suburb") or "").strip(),
        str(tags.get("addr:city") or "").strip(),
        str(tags.get("addr:postcode") or "").strip(),
        str(tags.get("addr:state") or "").strip(),
    ]

    address = str(tags.get("addr:full") or "").strip()

    if not address:
        address = ", ".join(part for part in address_parts if part)

    return {
        "osm_type": osm_type,
        "osm_id": osm_id,
        "clinic_name": str(
            tags.get("name")
            or tags.get("name:en")
            or "Unnamed veterinary clinic"
        ).strip()[:150],
        "address": address[:255] or None,
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
    }


def sign_selection(clinic: dict) -> str:
    now = datetime.now(timezone.utc)

    return jwt.encode(
        {
            "iss": JWT_ISSUER,
            "aud": SELECTION_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=10),
            "purpose": "clinic_selection",
            "clinic": clinic,
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def search_clinics(latitude: float, longitude: float):
    global _last_request, _search_running

    # Rounded search centres allow nearby requests to share cached results.
    latitude = round(latitude, 3)
    longitude = round(longitude, 3)
    key = (latitude, longitude)
    now = monotonic()

    with _lock:
        cached = _cache.get(key)

        if cached and now - cached[0] < 300:
            _cache.move_to_end(key)
            return cached[1]

        if _search_running or now - _last_request < 8:
            raise HTTPException(
                status_code=429,
                detail="Please wait a few seconds before searching again.",
                headers={"Retry-After": "8"},
            )

        _search_running = True
        _last_request = now

    try:
        query = (
            "[out:json][timeout:15];"
            f'nwr(around:3000,{latitude},{longitude})'
            '["amenity"="veterinary"];'
            "out body center 50;"
        )

        request = Request(
            OVERPASS_URL,
            data=urlencode({"data": query}).encode("utf-8"),
            headers={
                "User-Agent": "VetDental-FYP/1.0",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read(2_000_001)

            if len(raw) > 2_000_000:
                raise ValueError("Response too large")

            payload = json.loads(raw.decode("utf-8"))

            if (
                not isinstance(payload, dict)
                or payload.get("remark")
                or not isinstance(payload.get("elements"), list)
            ):
                raise ValueError("Incomplete map response")

        except (URLError, TimeoutError, ValueError):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Clinic search is temporarily unavailable. "
                    "Please try again later."
                ),
            ) from None

        results = []
        seen = set()

        for element in payload["elements"]:
            if not isinstance(element, dict):
                continue

            clinic = normalize_clinic(element)

            if clinic is None:
                continue

            identity = (clinic["osm_type"], clinic["osm_id"])

            if identity in seen:
                continue

            seen.add(identity)

            result = DiscoveredClinic(
                **clinic,
                selection_token=sign_selection(clinic),
            )

            results.append(result.model_dump())

        results.sort(key=lambda item: item["clinic_name"].casefold())

        with _lock:
            _cache[key] = (monotonic(), results)
            _cache.move_to_end(key)

            while len(_cache) > 128:
                _cache.popitem(last=False)

        return results

    finally:
        with _lock:
            _search_running = False


def verify_selection(token: str) -> ClinicSelectionData:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            audience=SELECTION_AUDIENCE,
            options={
                "require": [
                    "iss",
                    "aud",
                    "iat",
                    "exp",
                    "purpose",
                    "clinic",
                ]
            },
        )

        if payload["purpose"] != "clinic_selection":
            raise ValueError("Invalid purpose")

        return ClinicSelectionData.model_validate(payload["clinic"])

    except (
        jwt.InvalidTokenError,
        ValidationError,
        ValueError,
        TypeError,
    ):
        raise HTTPException(
            status_code=400,
            detail="Clinic selection expired or is invalid. Search again.",
        ) from None

def search_clinics_by_name(query_text: str):
    global _last_request, _search_running

    query_text = " ".join(query_text.split())

    if not 3 <= len(query_text) <= 150:
        raise HTTPException(
            status_code=400,
            detail="Enter between 3 and 150 characters.",
        )

    key = ("name", query_text.casefold())
    now = monotonic()

    with _lock:
        cached = _cache.get(key)

        if cached and now - cached[0] < 300:
            _cache.move_to_end(key)
            return cached[1]

        if _search_running or now - _last_request < 8:
            raise HTTPException(
                status_code=429,
                detail="Please wait a few seconds before searching again.",
                headers={"Retry-After": "8"},
            )

        _search_running = True
        _last_request = now

    try:
        parameters = urlencode({
            "q": query_text,
            "countrycode": "MY",
            "osm_tag": "amenity:veterinary",
            "limit": 10,
        })

        endpoint = os.getenv(
            "OSM_PHOTON_URL",
            "https://photon.komoot.io/api/",
        )

        request = Request(
            f"{endpoint}?{parameters}",
            headers={
                "User-Agent": "VetDental-FYP/1.0",
                "Accept": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read(1_000_001)

            if len(raw) > 1_000_000:
                raise ValueError("Response too large")

            payload = json.loads(raw.decode("utf-8"))

            if (
                not isinstance(payload, dict)
                or not isinstance(payload.get("features"), list)
            ):
                raise ValueError("Invalid search response")

        except (URLError, TimeoutError, ValueError):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Clinic search is unavailable. Try later or "
                    "use the manual clinic entry option."
                ),
            ) from None

        results = []
        seen = set()

        for feature in payload["features"]:
            if not isinstance(feature, dict):
                continue

            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}

            if (
                properties.get("osm_key") != "amenity"
                or properties.get("osm_value") != "veterinary"
                or geometry.get("type") != "Point"
            ):
                continue

            coordinates = geometry.get("coordinates") or []

            if len(coordinates) < 2:
                continue

            osm_type = {
                "N": "node",
                "W": "way",
                "R": "relation",
            }.get(str(properties.get("osm_type", "")).upper())

            element = {
                "type": osm_type,
                "id": properties.get("osm_id"),
                "tags": {
                    "amenity": "veterinary",
                    "name": properties.get("name"),
                    "addr:housenumber": properties.get("housenumber"),
                    "addr:street": properties.get("street"),
                    "addr:city": properties.get("city"),
                    "addr:postcode": properties.get("postcode"),
                    "addr:state": properties.get("state"),
                },
            }

            point = {
                "lat": coordinates[1],
                "lon": coordinates[0],
            }

            if osm_type == "node":
                element.update(point)
            else:
                element["center"] = point

            clinic = normalize_clinic(element)

            if clinic is None:
                continue

            identity = (clinic["osm_type"], clinic["osm_id"])

            if identity in seen:
                continue

            seen.add(identity)

            results.append(
                DiscoveredClinic(
                    **clinic,
                    selection_token=sign_selection(clinic),
                ).model_dump()
            )

        with _lock:
            _cache[key] = (monotonic(), results)
            _cache.move_to_end(key)

            while len(_cache) > 128:
                _cache.popitem(last=False)

        return results

    finally:
        with _lock:
            _search_running = False