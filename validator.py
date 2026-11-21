"""Row validation: airport list loading, single-row checks, record building."""

import math
import re
from datetime import datetime

# Column order of every data row, also the keys of a flight record.
FIELDS = ("flight_id", "origin", "destination",
          "departure_datetime", "arrival_datetime", "price")

# The character classes are written out on purpose: \d, str.isalnum() and
# str.isupper() also accept non-ASCII characters such as "Ā" or "é".
FLIGHT_ID_RE = re.compile(r"[A-Za-z0-9]{2,8}")
AIRPORT_RE = re.compile(r"[A-Z]{3}")
DATETIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}")
DATETIME_FORMAT = "%Y-%m-%d %H:%M"


def load_airports(path: str) -> set[str]:
    """Read an airport list file and return the set of codes.

    One code per line. Strip whitespace; skip blank lines and lines
    starting with '#'.
    """
    airports = set()
    with open(path, encoding="utf-8-sig") as file:
        for line in file:
            code = line.strip()
            if code and not code.startswith("#"):
                airports.add(code)
    return airports


def parse_datetime(text) -> datetime | None:
    """Return the datetime for an exact "YYYY-MM-DD HH:MM" string, else None.

    The regular expression checks the layout (zero padding, one space),
    because strptime() alone also accepts "2025-1-5 9:3". strptime() then
    rejects dates and times that do not exist, like 2025-02-30 or 24:00.
    """
    if not isinstance(text, str) or not DATETIME_RE.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, DATETIME_FORMAT)
    except ValueError:
        return None


def parse_price(text: str) -> float | None:
    """Return the price as a finite float, or None if it is not a number."""
    try:
        price = float(text)
    except ValueError:
        return None
    return price if math.isfinite(price) else None


def validate_row(fields: list[str], airports: set[str]) -> str | None:
    """Check one CSV row (fields as returned by csv.reader, not yet stripped).

    Return None if the row is valid, otherwise the error code of the
    FIRST failing check (checks 1-11 in the specification, in order).
    Does not check for duplicates.
    """
    if len(fields) != len(FIELDS):
        return "WRONG_FIELD_COUNT"

    values = [field.strip() for field in fields]
    if not all(values):
        return "MISSING_FIELD"
    flight_id, origin, destination, departure, arrival, price = values

    if not FLIGHT_ID_RE.fullmatch(flight_id):
        return "INVALID_FLIGHT_ID"
    if not AIRPORT_RE.fullmatch(origin) or origin not in airports:
        return "INVALID_ORIGIN"
    if not AIRPORT_RE.fullmatch(destination) or destination not in airports:
        return "INVALID_DESTINATION"
    if origin == destination:
        return "SAME_ORIGIN_DESTINATION"

    departure_time = parse_datetime(departure)
    if departure_time is None:
        return "INVALID_DEPARTURE"
    arrival_time = parse_datetime(arrival)
    if arrival_time is None:
        return "INVALID_ARRIVAL"
    if arrival_time <= departure_time:
        return "ARRIVAL_NOT_AFTER_DEPARTURE"

    price_value = parse_price(price)
    if price_value is None:
        return "INVALID_PRICE"
    if price_value <= 0:
        return "NON_POSITIVE_PRICE"
    return None


def to_record(fields: list[str]) -> dict:
    """Turn a valid row into a flight record dictionary.

    Keys: flight_id, origin, destination, departure_datetime,
    arrival_datetime (stripped strings) and price (float).
    """
    record = dict(zip(FIELDS, (field.strip() for field in fields)))
    record["price"] = float(record["price"])
    return record
