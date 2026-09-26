"""
Tests for the flow file format.
They pin that a recorded session survives export and import, and that a malformed file is refused.
"""

import json

import pytest
from pydantic import ValidationError

from recordscrape.flows import (
    FlowFile,
    flow_file_json,
    flow_from_recorded_session,
    recorded_session_from_flow,
)

CARD_TABLE = {
    "rowSelector": "ul.results > li.card",
    "rowFallbackSelectors": ["body > ul:nth-of-type(1) > li"],
    "columns": [
        {
            "name": "name",
            "selector": "h2.name",
            "fallbackSelectors": [":scope > h2:nth-of-type(1)"],
            "attribute": "textContent",
        },
        {"name": "link", "selector": "a.more", "fallbackSelectors": [], "attribute": "href"},
    ],
}


def recorded_search_session(search_url):
    """Shaped like SessionRecorder.stop() output, timestamps and picker display fields included."""
    return {
        "url": search_url,
        "actions": [
            {"type": "navigate", "url": search_url, "timestamp": 1.0},
            {
                "type": "input",
                "selector": "#query",
                "fallbackSelectors": ["input"],
                "value": "shoes",
                "timestamp": 2.0,
            },
            {
                "type": "input",
                "selector": "#gift",
                "fallbackSelectors": [],
                "value": "on",
                "checked": True,
                "timestamp": 3.0,
            },
            {"type": "click", "selector": "#apply", "fallbackSelectors": [], "timestamp": 4.0},
            {"type": "scroll", "x": 0, "y": 0, "timestamp": 5.0},
        ],
        "selectors": [
            {
                "selector": "#summary",
                "fallbackSelectors": ["p"],
                "tagName": "P",
                "attribute": "textContent",
                "preview": "shoes|true...",
            }
        ],
        "table": CARD_TABLE,
    }


def valid_flow_file():
    return {
        "formatVersion": 1,
        "name": "Search",
        "startUrl": "https://shop.example/search",
        "steps": [{"type": "click", "selector": "#apply", "fallbackSelectors": []}],
        "pickedElements": [{"selector": "h1", "fallbackSelectors": [], "attribute": "textContent"}],
    }


def test_exported_session_imports_back_without_display_fields():
    recorded_session = recorded_search_session("https://shop.example/search")

    flow_text = flow_file_json(flow_from_recorded_session("Search", recorded_session))
    imported_session = recorded_session_from_flow(FlowFile.model_validate_json(flow_text))

    assert imported_session == {
        "url": "https://shop.example/search",
        "actions": [
            {
                "type": "input",
                "selector": "#query",
                "fallbackSelectors": ["input"],
                "value": "shoes",
            },
            {
                "type": "input",
                "selector": "#gift",
                "fallbackSelectors": [],
                "value": "on",
                "checked": True,
            },
            {"type": "click", "selector": "#apply", "fallbackSelectors": []},
            {"type": "scroll", "x": 0, "y": 0},
        ],
        "selectors": [
            {"selector": "#summary", "fallbackSelectors": ["p"], "attribute": "textContent"}
        ],
        "table": CARD_TABLE,
    }
    assert "checked" not in json.loads(flow_text)["steps"][0]


def test_vpr_session_exports_only_its_start_url_and_picked_elements():
    vpr_session = {
        "url": "https://shop.example/search",
        "actions": [
            {"type": "navigate", "url": "https://shop.example/search", "timestamp": 1},
            {"type": "click", "selector": "#vpr-overlay", "timestamp": 2},
        ],
        "selectors": [{"selector": "h1", "tagName": "H1", "attribute": "textContent"}],
        "table": None,
    }

    flow = flow_from_recorded_session("Old", vpr_session)

    assert flow.steps == []
    assert flow.pickedElements[0].fallbackSelectors == []
    assert "table" not in json.loads(flow_file_json(flow))


def test_flow_without_a_table_imports_as_a_session_without_one():
    imported_session = recorded_session_from_flow(FlowFile.model_validate(valid_flow_file()))

    assert imported_session["table"] is None


@pytest.mark.parametrize(
    "broken_key, broken_value",
    [
        ("formatVersion", 2),
        ("steps", [{"type": "hover", "selector": "#apply", "fallbackSelectors": []}]),
        ("steps", [{"type": "click", "selector": "#apply"}]),
        ("steps", [{"type": "click", "selector": "#apply", "fallbackSelectors": [], "wait": 5}]),
        ("steps", [{"type": "navigate", "url": "https://shop.example/other"}]),
        ("table", {**CARD_TABLE, "columns": []}),
        ("table", {**CARD_TABLE, "columns": [CARD_TABLE["columns"][0]] * 2}),
        ("table", {**CARD_TABLE, "columns": [{**CARD_TABLE["columns"][0], "index": 0}]}),
    ],
    ids=[
        "newer-version",
        "unknown-step-type",
        "missing-fallbacks",
        "unknown-key",
        "navigate-step",
        "table-without-columns",
        "duplicate-column-names",
        "unknown-column-key",
    ],
)
def test_malformed_flow_file_is_refused(broken_key, broken_value):
    broken_flow = {**valid_flow_file(), broken_key: broken_value}

    with pytest.raises(ValidationError):
        FlowFile.model_validate(broken_flow)
