"""Running queries against the flight database."""

from validator import FIELDS, parse_datetime

TEXT_KEYS = ("flight_id", "origin", "destination")
DATETIME_KEYS = ("departure_datetime", "arrival_datetime")
NUMBER_KEYS = ("price", "min_price")
ORDERS = ("asc", "desc")


def is_number(value) -> bool:
    """True for a JSON number. bool is a subclass of int, but not a number here."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_valid_query(query) -> bool:
    """Check that a query only uses allowed keys with values of the right type."""
    if not isinstance(query, dict):
        return False
    for key, value in query.items():
        if key in TEXT_KEYS:
            valid = isinstance(value, str)
        elif key in DATETIME_KEYS:
            valid = parse_datetime(value) is not None
        elif key in NUMBER_KEYS:
            valid = is_number(value)
        elif key == "sort_by":
            valid = isinstance(value, str) and value in FIELDS
        elif key == "order":
            valid = isinstance(value, str) and value in ORDERS
        elif key == "limit":
            valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else:
            valid = False  # unknown key
        if not valid:
            return False
    # "order" is only allowed together with "sort_by"
    return "order" not in query or "sort_by" in query


def matches(flight: dict, query: dict) -> bool:
    """True if the flight passes every condition of a valid query (AND)."""
    for key in TEXT_KEYS:
        if key in query and flight[key] != query[key]:
            return False
    # The datetimes always have the zero-padded layout YYYY-MM-DD HH:MM,
    # so comparing the strings gives the same result as comparing the times.
    if "departure_datetime" in query and flight["departure_datetime"] < query["departure_datetime"]:
        return False
    if "arrival_datetime" in query and flight["arrival_datetime"] > query["arrival_datetime"]:
        return False
    if "price" in query and not flight["price"] <= query["price"]:
        return False
    if "min_price" in query and not flight["price"] >= query["min_price"]:
        return False
    return True


def run_query(db: list[dict], query: dict) -> dict:
    """Return one response entry for one query object.

    Valid query:   {"query": query, "matches": [...]}
    Invalid query: {"query": query, "error": "INVALID_QUERY", "matches": []}
    """
    if not is_valid_query(query):
        return {"query": query, "error": "INVALID_QUERY", "matches": []}

    found = [flight for flight in db if matches(flight, query)]
    if "sort_by" in query:
        # sorted() is stable, also with reverse=True, so flights with equal
        # values keep their database order in both directions.
        sort_key = query["sort_by"]
        found = sorted(found, key=lambda flight: flight[sort_key],
                       reverse=query.get("order", "asc") == "desc")
    if "limit" in query:
        found = found[:query["limit"]]
    return {"query": query, "matches": found}


def run_queries(db: list[dict], queries: dict | list) -> list[dict]:
    """Accept one query object or a list of them; always return a list."""
    if not isinstance(queries, list):
        queries = [queries]
    return [run_query(db, query) for query in queries]
