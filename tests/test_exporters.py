"""
Tests for the extracted-record exporters.
They pin that both record shapes a run saves come out as valid CSV, JSON and JSONL.
"""

import csv
import io
import json

import pytest
from pydantic import ValidationError

from recordscrape.exporters import (
    ExportOptions,
    export_text,
    records_as_csv,
    records_as_json,
    records_as_jsonl,
)

TABLE_RECORDS = [
    {"name": "Shoe", "price": "$40"},
    {"name": 'Hat, "wool"\nsize M', "price": ""},
    {"name": "Café", "colour": "red"},
]

PICKED_ELEMENT_ROWS = [
    {"selector": "h1", "value": "Hello", "attribute": "textContent", "index": 0, "tag": "h1"},
]


def test_csv_header_lists_every_key_and_a_missing_one_reads_empty():
    csv_text = records_as_csv(TABLE_RECORDS)

    assert csv_text.splitlines()[0] == "name,price,colour"
    assert list(csv.DictReader(io.StringIO(csv_text))) == [
        {"name": "Shoe", "price": "$40", "colour": ""},
        {"name": 'Hat, "wool"\nsize M', "price": "", "colour": ""},
        {"name": "Café", "price": "", "colour": "red"},
    ]


def test_csv_writes_picked_element_rows_with_their_numbers():
    csv_text = records_as_csv(PICKED_ELEMENT_ROWS)

    assert csv_text == "selector,value,attribute,index,tag\r\nh1,Hello,textContent,0,h1\r\n"


def test_csv_cells_a_spreadsheet_would_run_as_formulas_are_written_as_text():
    scraped_records = [
        {"=cmd": '=HYPERLINK("http://evil.example")', "price": "-5", "note": "+1 more"},
        {"=cmd": "@SUM(A1)", "price": "-1.50", "note": "-inf"},
    ]

    csv_rows = list(csv.reader(io.StringIO(records_as_csv(scraped_records))))

    assert csv_rows == [
        ["'=cmd", "price", "note"],
        ['\'=HYPERLINK("http://evil.example")', "-5", "'+1 more"],
        ["'@SUM(A1)", "-1.50", "'-inf"],
    ]


def test_csv_of_no_records_is_a_blank_header_line():
    assert records_as_csv([]) == "\r\n"


def test_json_keeps_records_and_non_ascii_text():
    json_text = records_as_json(TABLE_RECORDS)

    assert json.loads(json_text) == TABLE_RECORDS
    assert "Café" in json_text


def test_jsonl_writes_one_record_per_line():
    jsonl_text = records_as_jsonl(TABLE_RECORDS)

    assert jsonl_text.endswith("\n")
    assert [json.loads(line) for line in jsonl_text.splitlines()] == TABLE_RECORDS
    assert records_as_jsonl([]) == ""


RUN_DETAILS = {"session": "Cards", "run_id": 7, "extracted_at": "2026-09-30 12:00:00"}


def test_fields_keep_only_those_keys_in_that_order_in_every_format():
    export_options = ExportOptions.model_validate({"format": "json", "fields": "price, name"})
    csv_options = ExportOptions.model_validate({"format": "csv", "fields": "price,name"})

    exported_records = json.loads(export_text(TABLE_RECORDS, export_options, RUN_DETAILS))
    csv_rows = list(csv.reader(io.StringIO(export_text(TABLE_RECORDS, csv_options, RUN_DETAILS))))

    assert [list(record) for record in exported_records] == [["price", "name"]] * 3
    assert exported_records[2] == {"price": "", "name": "Café"}
    assert csv_rows[0] == ["price", "name"]


def test_json_envelope_wraps_records_in_the_run_details():
    export_options = ExportOptions.model_validate({"format": "json", "envelope": "1"})

    envelope = json.loads(export_text(TABLE_RECORDS, export_options, RUN_DETAILS))

    assert envelope == {**RUN_DETAILS, "items_count": 3, "records": TABLE_RECORDS}


def test_json_that_is_not_pretty_is_one_line_without_spaces():
    export_options = ExportOptions.model_validate({"format": "json", "pretty": "0"})

    json_text = export_text([{"name": "Shoe"}], export_options, RUN_DETAILS)

    assert json_text == '[{"name":"Shoe"}]'


@pytest.mark.parametrize(
    "export_query",
    [
        {"format": "xlsx"},
        {"format": "csv", "envelope": "1"},
        {"format": "jsonl", "pretty": "0"},
        {"format": "json", "fields": "name,name"},
        {"format": "json", "fields": "name,,price"},
        {"format": "json", "pretty": "maybe"},
        {"format": "json", "download": "1"},
    ],
)
def test_export_options_refuse_unknown_or_mismatched_options(export_query):
    with pytest.raises(ValidationError):
        ExportOptions.model_validate(export_query)
