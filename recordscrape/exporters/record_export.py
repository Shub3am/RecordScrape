"""
Turns one run's extracted records into the text of a CSV, JSON or JSONL download. Table records
and flat picked-element rows are both lists of flat dicts, so each format has one writer for both.
Must not know about storage, Flask or browsers.
"""

import csv
import io
import json
import re
from collections.abc import Callable
from dataclasses import dataclass

# Spreadsheets run a cell starting with one of these as a formula, and scraped text comes from
# pages anyone can write. A leading apostrophe makes Excel, LibreOffice and Google Sheets show the
# cell as text (OWASP CSV injection guidance).
FORMULA_TRIGGER_CHARACTERS = ("=", "+", "-", "@", "\t", "\r")
# Not float(): it also accepts "-inf", "nan" and "1_0", which spreadsheets do not read as numbers.
SIGNED_NUMBER = re.compile(r"[+-](\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")


def spreadsheet_safe_cell(cell_value):
    """Returns the value with an apostrophe in front when a spreadsheet would run it as a formula.
    A plain number such as -5 is left as is, because spreadsheets read it as a number."""
    if not isinstance(cell_value, str) or not cell_value.startswith(FORMULA_TRIGGER_CHARACTERS):
        return cell_value
    if SIGNED_NUMBER.fullmatch(cell_value):
        return cell_value
    return "'" + cell_value


def records_as_csv(records: list[dict]) -> str:
    """Header is every key in first-seen order across all records; a record lacking one writes ""."""
    column_names = list(dict.fromkeys(key for record in records for key in record))
    csv_text = io.StringIO()
    csv_writer = csv.DictWriter(csv_text, fieldnames=column_names, restval="")
    csv_writer.writerow({name: spreadsheet_safe_cell(name) for name in column_names})
    csv_writer.writerows(
        {key: spreadsheet_safe_cell(value) for key, value in record.items()} for record in records
    )
    return csv_text.getvalue()


def records_as_json(records: list[dict]) -> str:
    return json.dumps(records, indent=2, ensure_ascii=False)


def records_as_jsonl(records: list[dict]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)


@dataclass(frozen=True)
class ExportFormat:
    write_records: Callable[[list[dict]], str]
    mimetype: str


# Each format's name is also its file extension.
EXPORT_FORMATS = {
    "csv": ExportFormat(records_as_csv, "text/csv"),
    "json": ExportFormat(records_as_json, "application/json"),
    "jsonl": ExportFormat(records_as_jsonl, "application/jsonl"),
}
