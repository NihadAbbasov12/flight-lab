"""Flight Schedule Parser and Query Tool - command-line entry point.

Run from the project folder, for example:
    python flight_parser.py -i data/db.csv -a data/airports.txt
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime

from csv_loader import parse_files
from query import run_queries
from validator import load_airports

# Student details: plain ASCII, no spaces or underscores.
STUDENT_ID = "251ADB076"
FIRST_NAME = "Nihad"
LAST_NAME = "Abbasov"

DEFAULT_DATABASE = "db.json"
LOG_FILE_NAME = "errors.log"
LOGGER_NAME = "flight_parser"


class FlightToolError(Exception):
    """An expected runtime problem: printed as 'Error: ...', exit code 1."""


# ---------------------------------------------------------------- output

def write_line(stream, text: str) -> None:
    """Print text as exactly one line, even if the console cannot show every character."""
    text = " ".join(text.splitlines())
    try:
        print(text, file=stream)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "ascii"
        print(text.encode(encoding, "backslashreplace").decode(encoding), file=stream)


def say(text: str) -> None:
    """Progress and summary messages go to stdout."""
    write_line(sys.stdout, text)


def print_error(text: str) -> None:
    write_line(sys.stderr, "Error: " + text)


def reason(exc: Exception) -> str:
    """A short description of why a file could not be read or written."""
    if isinstance(exc, UnicodeDecodeError):
        return "the file is not valid UTF-8 text"
    if isinstance(exc, OSError) and exc.strerror:
        return exc.strerror
    return str(exc)


# ---------------------------------------------------------------- arguments

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flight_parser.py",
        description="Validate flight schedule CSV files, store the valid flights "
                    "in a JSON database and run queries against it.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-i", dest="csv_file", metavar="FILE",
                        help="parse a single CSV file")
    source.add_argument("-d", dest="csv_folder", metavar="FOLDER",
                        help="parse every .csv file in a folder, in sorted name order")
    source.add_argument("-j", dest="json_db", metavar="FILE",
                        help="load an existing JSON database instead of parsing CSV files")
    parser.add_argument("-a", dest="airports", metavar="FILE",
                        help="airport list file (required with -i and -d)")
    parser.add_argument("-o", dest="output", metavar="FILE",
                        help=f"output path for the JSON database (default: {DEFAULT_DATABASE}); "
                             "only with -i or -d")
    parser.add_argument("-q", dest="queries", metavar="FILE",
                        help="run the queries in this JSON file")
    parser.add_argument("-r", dest="response_dir", metavar="FOLDER",
                        help="folder for the query response file (default: current directory)")
    return parser


def parse_arguments(argv):
    """Return (args, None), or (None, exit code) after -h or a usage error.

    argparse ends the program with SystemExit (code 0 for -h, code 2 for
    usage errors). main() has to return the code instead, so it is caught.
    """
    if argv is not None:
        argv = [os.fspath(arg) if isinstance(arg, os.PathLike) else arg for arg in argv]
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.json_db is None and args.airports is None:
            parser.error("argument -a is required with -i and -d")
        if args.json_db is not None and args.output is not None:
            parser.error("argument -o is only allowed with -i or -d")
    except SystemExit as exit_request:
        code = exit_request.code
        if code is None:
            code = 0
        elif not isinstance(code, int):
            code = 2
        return None, code
    return args, None


# ---------------------------------------------------------------- files

def read_json_file(path: str, what: str):
    try:
        with open(path, encoding="utf-8-sig") as file:
            return json.load(file)
    except (OSError, UnicodeDecodeError) as exc:
        raise FlightToolError(f"cannot read {what} file {path}: {reason(exc)}") from None
    except json.JSONDecodeError as exc:
        raise FlightToolError(f"{what} file {path} is not valid JSON ({exc})") from None


def write_json_file(path: str, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")
    except OSError as exc:
        raise FlightToolError(f"cannot write {path}: {reason(exc)}") from None


def read_airports(path: str) -> set[str]:
    try:
        return load_airports(path)
    except (OSError, UnicodeDecodeError) as exc:
        raise FlightToolError(f"cannot read airport list {path}: {reason(exc)}") from None


def find_csv_files(folder: str) -> list[str]:
    """Return the .csv files directly inside a folder (no sub-folders), sorted by name."""
    try:
        names = sorted(os.listdir(folder))
    except OSError as exc:
        raise FlightToolError(f"cannot read folder {folder}: {reason(exc)}") from None
    paths = [os.path.join(folder, name) for name in names
             if name.endswith(".csv") and os.path.isfile(os.path.join(folder, name))]
    if not paths:
        raise FlightToolError(f"no .csv files found in folder {folder}")
    return paths


def read_csv_files(paths: list[str], airports: set[str]) -> tuple[list[dict], list[str]]:
    try:
        return parse_files(paths, airports)
    except OSError as exc:
        raise FlightToolError(f"cannot read CSV file {exc.filename}: {reason(exc)}") from None
    except UnicodeDecodeError:
        raise FlightToolError("a CSV file is not valid UTF-8 text") from None


# ---------------------------------------------------------------- program steps

def parse_csv_input(args) -> list[dict]:
    """-i / -d: parse the CSV files, write the database and errors.log."""
    db_path = args.output if args.output is not None else DEFAULT_DATABASE
    log_path = os.path.join(os.path.dirname(db_path), LOG_FILE_NAME)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    try:
        handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    except OSError as exc:
        raise FlightToolError(f"cannot create {log_path}: {reason(exc)}") from None
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)

    try:
        airports = read_airports(args.airports)
        if args.csv_file is not None:
            paths = [args.csv_file]
        else:
            paths = find_csv_files(args.csv_folder)
        flights, errors = read_csv_files(paths, airports)
        for message in errors:
            logger.warning(message)
        logger.info("Parsed %d file(s): %d valid row(s), %d invalid row(s)",
                    len(paths), len(flights), len(errors))
        write_json_file(db_path, flights)
    except FlightToolError as problem:
        logger.error("%s", " ".join(str(problem).splitlines()))
        raise
    finally:
        # The handler must not outlive this run: main() can be called many
        # times in one process, also when it returns early with an error.
        logger.removeHandler(handler)
        handler.close()

    say(f"Parsed {len(paths)} file(s): {len(flights)} valid row(s), {len(errors)} invalid row(s).")
    say(f"Database written to {db_path}, invalid rows logged to {log_path}.")
    return flights


def load_database(path: str) -> list[dict]:
    """-j: load an existing JSON database."""
    data = read_json_file(path, "database")
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise FlightToolError(f"database {path} must be a JSON array of objects")
    say(f"Loaded {len(data)} flight(s) from {path}.")
    return data


def response_file_name() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"response_{STUDENT_ID}_{FIRST_NAME}_{LAST_NAME}_{stamp}.json"


def answer_queries(flights: list[dict], query_path: str, response_dir: str | None) -> None:
    """-q: run the queries and write exactly one response file."""
    queries = read_json_file(query_path, "query")
    one_object = isinstance(queries, dict)
    list_of_objects = isinstance(queries, list) and all(isinstance(q, dict) for q in queries)
    if not (one_object or list_of_objects):
        raise FlightToolError(f"query file {query_path} must contain a JSON object "
                              "or an array of objects")

    entries = run_queries(flights, queries)
    path = os.path.join(response_dir or os.curdir, response_file_name())
    write_json_file(path, entries)
    invalid = sum(1 for entry in entries if "error" in entry)
    say(f"Ran {len(entries)} query(ies), {invalid} invalid. Response written to {path}.")


def main(argv: list[str] | None = None) -> int:
    """Run the whole program and return the exit code (0, 1 or 2).

    argv is the argument list without the program name.
    None means use sys.argv[1:] (argparse does this for you).
    Do not call sys.exit() inside main(); return the code instead.
    """
    args, exit_code = parse_arguments(argv)
    if args is None:
        return exit_code

    try:
        if args.json_db is not None:
            flights = load_database(args.json_db)
        else:
            flights = parse_csv_input(args)
        if args.queries is not None:
            answer_queries(flights, args.queries, args.response_dir)
    except FlightToolError as problem:
        print_error(str(problem))
        return 1
    except Exception as problem:  # never end with a traceback
        print_error(f"unexpected problem: {problem!r}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
