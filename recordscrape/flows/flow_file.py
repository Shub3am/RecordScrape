"""
The flow file: the versioned JSON form of a recorded session that people export, edit, share and
import, and its conversion to and from the recorded-session dict that storage and the runner use.
Must not know about storage, Flask, browsers or the worker.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FLOW_FORMAT_VERSION = 1


class FlowFileModel(BaseModel):
    # A typo in a hand-edited file must fail loudly, not be ignored.
    model_config = ConfigDict(extra="forbid")


class ClickStep(FlowFileModel):
    type: Literal["click"]
    selector: str
    fallbackSelectors: list[str]


class InputStep(FlowFileModel):
    type: Literal["input"]
    selector: str
    fallbackSelectors: list[str]
    # None for a contenteditable field, which has no value property. The runner cannot replay it.
    value: str | None
    # Only checkboxes and radios carry it.
    checked: bool | None = None


class ScrollStep(FlowFileModel):
    type: Literal["scroll"]
    x: float
    y: float


class PickedElement(FlowFileModel):
    selector: str
    fallbackSelectors: list[str]
    attribute: str


class TableColumn(FlowFileModel):
    name: str
    selector: str
    fallbackSelectors: list[str]
    attribute: str


class RowTable(FlowFileModel):
    rowSelector: str
    rowFallbackSelectors: list[str]
    columns: list[TableColumn] = Field(min_length=1)

    @field_validator("columns")
    @classmethod
    def refuse_duplicate_column_names(cls, columns: list[TableColumn]) -> list[TableColumn]:
        column_names = [column.name for column in columns]
        if len(set(column_names)) != len(column_names):
            raise ValueError(
                "column names must be unique: each one is a key in every extracted row"
            )
        return columns


class FlowFile(FlowFileModel):
    formatVersion: Literal[FLOW_FORMAT_VERSION]
    name: str
    startUrl: str
    steps: list[Annotated[ClickStep | InputStep | ScrollStep, Field(discriminator="type")]]
    pickedElements: list[PickedElement]
    table: RowTable | None = None


def recorded_by_vpr(recorded_steps: list[dict]) -> bool:
    """vpr's clicks and inputs are the only ones without fallbackSelectors. vpr never replayed its
    actions, and they include clicks on its own overlay, so its sessions only reopen the start URL."""
    return any(
        "fallbackSelectors" not in recorded_step
        for recorded_step in recorded_steps
        if recorded_step["type"] in ("click", "input")
    )


def flow_from_recorded_session(flow_name: str, recorded_session: dict) -> FlowFile:
    """Keeps what replay reads. Drops timestamps, the picker's display fields, the start URL's
    navigate step (startUrl holds it) and every step of a vpr session. A session without a row table
    exports without the `table` key, so readers from before row tables still load it."""
    recorded_steps = recorded_session["actions"]
    replayable_steps = (
        []
        if recorded_by_vpr(recorded_steps)
        else [
            {key: value for key, value in recorded_step.items() if key != "timestamp"}
            for recorded_step in recorded_steps
            if recorded_step["type"] != "navigate"
        ]
    )
    return FlowFile(
        formatVersion=FLOW_FORMAT_VERSION,
        name=flow_name,
        startUrl=recorded_session["url"],
        steps=replayable_steps,
        pickedElements=[
            {
                "selector": picked_element["selector"],
                "fallbackSelectors": picked_element.get("fallbackSelectors", []),
                "attribute": picked_element["attribute"],
            }
            for picked_element in recorded_session["selectors"]
        ],
        **({} if recorded_session["table"] is None else {"table": recorded_session["table"]}),
    )


def flow_file_json(flow: FlowFile) -> str:
    """The file's text, leaving out `checked` on inputs that are not checkboxes or radios."""
    return flow.model_dump_json(indent=2, exclude_unset=True)


def recorded_session_from_flow(flow: FlowFile) -> dict:
    """Returns the {url, actions, selectors, table} dict that storage saves and the runner replays."""
    return {
        "url": flow.startUrl,
        "actions": [step.model_dump(exclude_unset=True) for step in flow.steps],
        "selectors": [picked_element.model_dump() for picked_element in flow.pickedElements],
        "table": None if flow.table is None else flow.table.model_dump(),
    }
