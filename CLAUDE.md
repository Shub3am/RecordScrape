# RecordScrape

Self-hosted tool: record a browser session in a web dashboard, pick elements, re-extract them on a schedule.

## Modules

- `app.py`: Flask server and REST API for the dashboard. Single file, no module doc.
- `vpr/`: recording, replay, scheduling and SQLite storage engine. See `vpr/CLAUDE.md`.
- `recordscrape/worker/`: the one thread and event loop that all browser work runs on. See `recordscrape/worker/CLAUDE.md`.
- `recordscrape/browsers/`: opens a browser context for the chromium or patchright backend. See `recordscrape/browsers/CLAUDE.md`.
- `templates/`, `static/`: dashboard UI, vanilla HTML/CSS/JS with no build step.
- `tests/`: pytest suite. Tests that import `app.py` must use the `app_module` fixture in `tests/test_app_routes.py`.

## Run, test, deploy

- Install: `uv sync`, then `uv run playwright install chromium` and `uv run patchright install chromium`
- Run: `uv run python app.py`, then open http://localhost:5001
- Test: `uv run pytest`
- Lint: `uv run ruff check tests recordscrape` and `uv run ruff format --check tests recordscrape`
- Deploy: none. This is a self-hosted tool, and CI (`.github/workflows/ci.yml`) only tests.

## Repo-wide rules

- The server binds to 127.0.0.1 with debug off and no CORS. Do not widen this without adding authentication.
- Dependencies go through `uv add`, never a requirements file. `uv.lock` is committed.
- Lint only covers code rewritten under the current rules. Add a module to the CI lint step when it is rewritten.
- The v2 roadmap (Playwright engine, stealth backends, proxies, CLI) lives in the plan, not here.
