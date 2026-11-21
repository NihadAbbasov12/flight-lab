"""Reading CSV files into flight records and error messages."""

import csv
import os

from validator import to_record, validate_row


def read_data_lines(path: str) -> list[tuple[int, str]]:
    """Return (line number, text) for every data line of one CSV file.

    Line numbers are 1-based physical line numbers, so the header, blank
    lines and comment lines are counted even though they are skipped here.
    Reading the file line by line handles both "\\n" and "\\r\\n" endings;
    the line ending is removed from the text.
    """
    with open(path, encoding="utf-8-sig", newline="") as file:
        lines = list(file)

    data_lines = []
    for number, line in enumerate(lines, start=1):
        text = line.rstrip("\r\n")
        if number == 1:
            continue  # the header is never validated
        if not text.strip():
            continue  # blank line
        if text.lstrip().startswith("#"):
            continue  # comment line
        data_lines.append((number, text))
    return data_lines


def split_line(text: str) -> list[str]:
    """Split one line into fields with the csv module."""
    try:
        return next(csv.reader([text]))
    except (csv.Error, StopIteration):
        return []  # a line csv cannot split is reported as WRONG_FIELD_COUNT


def printable(text: str) -> str:
    """Escape characters that would break a log line (form feed, NUL, ...)."""
    return "".join(ch if ch.isprintable() else repr(ch)[1:-1] for ch in text)


def parse_files(paths: list[str], airports: set[str]) -> tuple[list[dict], list[str]]:
    """Process the CSV files in the order given.

    Return (records, errors):
      records - valid flight records, in input order
      errors  - one message per invalid row, in input order, formatted as
                "<file name>:<line number>: <ERROR_CODE> | <free text>"
                (base file name only, no timestamp or level, no newline)

    Also performs the DUPLICATE_FLIGHT check across all the files.
    Does not write any files and does not log anything itself.
    """
    records = []
    errors = []
    seen = set()  # (flight_id, departure_datetime) of every valid row so far

    for path in paths:
        file_name = printable(os.path.basename(path))
        for line_number, text in read_data_lines(path):
            fields = split_line(text)
            error = validate_row(fields, airports)
            if error is None:
                record = to_record(fields)
                key = (record["flight_id"], record["departure_datetime"])
                if key in seen:
                    error = "DUPLICATE_FLIGHT"
                else:
                    seen.add(key)
                    records.append(record)
            if error is not None:
                errors.append(f"{file_name}:{line_number}: {error} | {printable(text)}")

    return records, errors
