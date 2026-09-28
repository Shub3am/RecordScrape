"""
Turns one run's extracted records into the text of a CSV, JSON or JSONL download. Table records
and flat picked-element rows are both lists of flat dicts, so each format has one writer for both.
Must not know about storage, Flask or browsers.
"""

import csv
import io
import json
from collections.abc import Callable
from dataclasses import dataclass


def records_as_csv(records: list[dict]) -> str:
    """Header is every key in first-seen order across all records; a record lacking one writes ""."""
    column_names = list(dict.fromkeys(key for record in records for key in record))
    csv_text = io.StringIO()
    csv_writer = csv.DictWriter(csv_text, fieldnames=column_names, restval="")
    csv_writer.writeheader()
    csv_writer.writerows(records)
    return csv_text.getvalue()


def records_as_json(records: list[dict]) -> str:
    return json.dumps(records, indent=2, ensure_ascii=False)


def records_as_jsonl(records: list[dict]) -> str:
    return "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)


@dataclass(frozen=True)
class ExportFormat:
    write_records: Callable[[list[dict]], str]
    file_extension: str
    mimetype: str


EXPORT_FORMATS = {
    "csv": ExportFormat(records_as_csv, "csv", "text/csv"),
    "json": ExportFormat(records_as_json, "json", "application/json"),
    "jsonl": ExportFormat(records_as_jsonl, "jsonl", "application/jsonl"),
}
