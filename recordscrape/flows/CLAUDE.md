# recordscrape/flows

## Owns

The flow file: the versioned JSON form of a recorded session that people export, edit, share and import. Its pydantic models are the only definition of what a valid step or picked element looks like, and it converts between a flow and the recorded-session dict (`url`, `actions`, `selectors`, `table`) that storage saves and the runner replays.

## Must not know about

Storage, Flask, browsers, the worker or the recorder's page scripts. Callers read and write the files; this module only validates and converts.

## Entry points

- `FlowFile.model_validate_json(text)` or `FlowFile.model_validate(parsed_json)` to load a file. Both raise pydantic's `ValidationError` on a bad file.
- `flow_from_recorded_session(name, recorded_session)` and `flow_file_json(flow)` to export.
- `recorded_session_from_flow(flow)` to import.
- `recorded_by_vpr(actions)` to recognise a session recorded under vpr.

## Invariants and gotchas

- Keys are camelCase because the recorder's step keys (`fallbackSelectors`) are, and the runner reads imported steps unchanged.
- `formatVersion` accepts only 1. A reader never half-loads a file from a newer version.
- Every model forbids unknown keys, so a typo in a hand-edited file is an error.
- Step types are `click`, `input` and `scroll` only. `navigate` is refused: the recorder records it only for the start URL, which `startUrl` holds, and the runner skips it, so a hand-written one would be silently ignored.
- `fallbackSelectors` is required on steps. The runner treats a click or input without it as a vpr session and skips all replay.
- `checked` is left out or null on inputs that are not checkboxes or radios. Dumps use `exclude_unset` only to keep files and stored steps the same shape as recorded ones.
- `value` may be null: the recorder records a contenteditable field that way, and the runner cannot replay it.
- `table` is optional and holds at most one row table. Its column names must be unique because each one becomes a key in every extracted record. A session without a table exports without the key, so a reader from before row tables still loads the file; one with a table is refused by that reader as an unknown key, which is why `formatVersion` stayed 1.
- Export drops timestamps and the picker's `tagName` and `preview`, which nothing reads. A vpr session exports no steps and empty fallback lists, which matches how the runner treats it.

## Who calls it

`app.py` for the export and import routes, and `recordscrape/runner/` for `recorded_by_vpr`.
