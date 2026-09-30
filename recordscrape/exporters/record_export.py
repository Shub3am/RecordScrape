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
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

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


def records_as_json(json_document: list[dict] | dict, pretty: bool = True) -> str:
    """json_document is the records, or an envelope holding them. Not pretty writes one line with
    no spaces."""
    if pretty:
        return json.dumps(json_document, indent=2, ensure_ascii=False)
    return json.dumps(json_document, separators=(",", ":"), ensure_ascii=False)


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


class ExportOptions(BaseModel):
    """How one run is written. fields keeps only those keys, in that order, in every format.
    envelope and pretty only apply to JSON, and naming either with another format is refused."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    format: Literal[tuple(EXPORT_FORMATS)]
    fields: (
        tuple[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)], ...] | None
    ) = None
    envelope: bool = False
    pretty: bool = True

    @field_validator("fields", mode="before")
    @classmethod
    def split_comma_separated_fields(cls, fields):
        return fields.split(",") if isinstance(fields, str) else fields

    @field_validator("fields")
    @classmethod
    def refuse_repeated_fields(cls, fields):
        if fields is not None and len(set(fields)) != len(fields):
            raise ValueError("a field is named twice")
        return fields

    @model_validator(mode="after")
    def refuse_json_options_on_other_formats(self):
        json_only_options = sorted({"envelope", "pretty"} & self.model_fields_set)
        if json_only_options and self.format != "json":
            raise ValueError(f"{' and '.join(json_only_options)} can only be used with JSON")
        return self


def records_with_fields(records: list[dict], field_names: tuple[str, ...]) -> list[dict]:
    """A record lacking one of the fields reads "", as a CSV cell and a table column already do."""
    return [
        {field_name: record.get(field_name, "") for field_name in field_names} for record in records
    ]


def export_text(records: list[dict], export_options: ExportOptions, run_details: dict) -> str:
    """run_details are the envelope's keys besides items_count and records; only JSON with
    envelope reads them."""
    if export_options.fields is not None:
        records = records_with_fields(records, export_options.fields)
    if export_options.format == "json" and export_options.envelope:
        envelope = {**run_details, "items_count": len(records), "records": records}
        return records_as_json(envelope, export_options.pretty)
    if export_options.format == "json":
        return records_as_json(records, export_options.pretty)
    return EXPORT_FORMATS[export_options.format].write_records(records)
