# RecordScrape

A powerful visual browser automation platform for recording interactions and automating data extraction through intelligent session replay.

## Features

- 🎥 **Visual Recording**: Record your browser interactions in real-time
- 🎯 **Element Selection**: Visually select DOM elements for data extraction
- 🔄 **Automated Replay**: Repeat the recorded clicks, typing and scrolling, visible or headless, with per-run page, scroll and row limits
- 📄 **Flow Files**: Export a session as a JSON file, edit or share it, and import it back
- 💾 **Data Export**: Download any run as CSV, JSON or JSONL, with chosen fields, an optional run envelope and compact or pretty JSON
- 🔌 **Latest Data API**: Pull a session's newest successful run as JSON from any other tool
- ⏰ **Scheduling**: Run a session every N minutes
- 📊 **Control Dashboard**: Overview of the last 24 hours, every run with its status, duration and error, a run viewer with table and JSON tabs, and session editing

> Sessions recorded before the Playwright recorder only reopen their URL.

## 🎥 Demo

![Recording quotes.toscrape.com in the control dashboard: pick rows and the Next button, replay across 10 pages, view and export the JSON, schedule it](docs/images/demo.gif)

One recording on [quotes.toscrape.com](https://quotes.toscrape.com/), a site built for scraping practice: two clicks pick the quotes as rows, one more adds the author column, and the Next button makes every run read all 10 pages, 100 records.

▶ [Full walkthrough video (75 s)](docs/images/demo.mp4): record, pick rows and the Next button, save, replay with run options, open the run as a table and as JSON, export JSON with the run's details, rename a column, schedule it and check the overview.

▶ Earlier video:  
https://twitter.com/Shubh3m/status/2027349108256887131

Record once → Automate forever.

<details>
<summary>The overview after that run</summary>

![RecordScrape overview: one session, one schedule, one successful run of 100 items in the last 24 hours](docs/images/dashboard.png)

</details>


## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              RecordScrape Web Dashboard                  │
│              (Flask + HTML/CSS/JS)                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   Flask API Server                       │
│  /api/sessions, /api/schedules, /api/data              │
└────┬────────────────────────────────────────────┬───────┘
     │                                             │
     ▼                                             ▼
┌─────────────────┐                    ┌──────────────────┐
│   Recorder      │                    │     Runner       │
│  (Playwright)   │                    │  (Playwright)    │
└────┬────────────┘                    └────┬─────────────┘
     │                                      │
     ▼                                      ▼
┌─────────────────────────────────────────────────────────┐
│              Storage Layer (SQLite)                      │
│  Sessions, Schedules, Extracted Data                    │
└─────────────────────────────────────────────────────────┘
```

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

1. Clone the repository:
```bash
git clone https://github.com/Shub3am/RecordScrape.git
cd RecordScrape
```

2. Install dependencies and the browser:
```bash
uv sync
uv run playwright install chromium
```

3. Run the application:
```bash
uv run python app.py
```

4. Open your browser to `http://localhost:5001`. By default the server only listens on localhost.

## Running on a Server

The server reads its settings from environment variables:

| Variable | Default | What it sets |
|----------|---------|--------------|
| `RECORDSCRAPE_HOST` | `127.0.0.1` | Address to listen on. `0.0.0.0` listens on every interface |
| `RECORDSCRAPE_PORT` | `5001` | Port to listen on |
| `RECORDSCRAPE_DATA_DIR` | current directory | Existing folder that holds `scraper.db` |
| `RECORDSCRAPE_TOKEN` | none | Secret every `/api` request must send as `Authorization: Bearer <token>` |

Listening on anything but localhost refuses to start without `RECORDSCRAPE_TOKEN`, so the API is never open to the network. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

```bash
RECORDSCRAPE_HOST=0.0.0.0 RECORDSCRAPE_TOKEN=your-token uv run python app.py
```

The dashboard asks for the token the first time the server refuses it, and keeps it in that browser. The token travels in plain text over HTTP, so put the server behind HTTPS (a reverse proxy such as Caddy or nginx) when it is reachable beyond a private network.

Recording opens a browser window on the machine running the server, so record on your own machine, export the flow, and import it on the server. Runs and schedules work there headless.

### Docker

Every release publishes an image for linux/amd64 and linux/arm64 to the GitHub Container Registry:

```bash
docker run -d --name recordscrape -p 5001:5001 \
  -e RECORDSCRAPE_TOKEN=your-token \
  -v recordscrape-data:/data \
  ghcr.io/shub3am/recordscrape:latest
```

Pin a version with a tag such as `ghcr.io/shub3am/recordscrape:1.1.0`, or build it yourself with `docker build -t recordscrape .`.

- The image is built on Microsoft's Playwright image, which carries Chromium and its system libraries. Chromium and Patchright work out of the box.
- It listens on `0.0.0.0:5001`, so `RECORDSCRAPE_TOKEN` is required. The database lives in the `/data` volume.
- Replays with **"Headless"** unticked open their window on a virtual screen (Xvfb), so sites that behave differently in headless mode still work.
- Proxy credentials referenced as `${PROXY_PASS}` are read from the container's environment: pass them with `-e PROXY_PASS=...`.
- CloakBrowser is not in the image by default, because its binary license forbids redistribution. Build your own image with it: `docker build --build-arg WITH_CLOAKBROWSER=1 -t recordscrape .`, and pass `-e CLOAKBROWSER_LICENSE_KEY=...` if your build needs one. Do not push that image to a public registry.

### Health check

`GET /healthz` needs no token and answers `200` with `{"scheduler_running": true, "browser_worker_running": true}`, or `503` once either has stopped, so a load balancer or container orchestrator can restart the server. It reveals nothing about sessions or data.

## Releases

Each version tag (`v1.1.0`) publishes a [GitHub release](https://github.com/Shub3am/RecordScrape/releases) with generated notes and the container image above, tagged `1.1.0`, `1.1` and `latest`. The image never contains CloakBrowser.

## Running tests

The tests also run on the Patchright backend, which needs its own browser:

```bash
uv run patchright install chromium
uv run pytest
```

## Usage

### Recording a Session

1. In the **Record** view, enter the URL you want to scrape, optionally a session name (it defaults to the site's host name), and click **"Start Recording"**
2. A browser window opens on that URL (see [Stealth Browsers and Proxies](#stealth-browsers-and-proxies) to pick which one)
3. Click **"Select Elements"** and click the elements you want to extract, then **"Done"** in the overlay
4. For a list of items, click **"Select Rows"** instead (see below)
5. Click **"Stop & Save"** to save the session

### Extracting a List as Rows

1. While recording, click **"Select Rows"**
2. Click the same field in two different items, for example the name of the first and the second product. Every item that repeats like them is highlighted as a row. For a plain list whose items hold only text, click two items themselves
3. Click other fields inside any highlighted row to add them as columns, then **"Done"**

![Row picker: every quote outlined as a row, the quote text and author outlined as columns](docs/images/row-picker.png)

Each run then saves one record per row, such as `{"name": "Shoe", "price": "$40"}`. A column is named after the clicked element's first CSS class; rename or remove it with **"Edit"** on the session. Elements picked with **"Select Elements"** in the same session are added to every row, keyed by their selector.

### Following a List Across Pages

After picking rows, tell RecordScrape how the list continues:

- **"Select Next Button"**, then click the page's Next button. Each run reads the rows, clicks Next, and reads again, until the button is gone or disabled, a click no longer changes the rows, or 10 pages are read.
- **"Infinite Scroll"** for a feed that loads more as you scroll. Each run scrolls to the bottom until no new rows appear, or 10 scrolls are done, then reads every row.

The last choice wins. Elements picked with **"Select Elements"** are read on the first page only. Change the 10-page or 10-scroll limit with **"Edit"** on the session, or for a single run in the replay dialog.

### Replaying & Extracting Data

1. In the **Sessions** view, click **"Replay"** on a session
2. Pick the run options and click **"Run"**:
   - **Headless** runs without a browser window
   - **Max pages** or **Max scrolls** overrides the session's pagination limit for this run only
   - **Max rows** keeps at most that many records
3. The run appears in the **Runs** view with its status, item count, duration and trigger. A failed run keeps its error
4. Click a run to open it: the **Table** and **JSON** tabs show its records, and **Copy** puts the JSON on the clipboard
5. Under **Export**, pick the format and fields, and for JSON whether to wrap it in run details and indent it, then **"Download"**

<img src="docs/images/extracted-data.png" alt="The run viewer on its JSON tab: 100 quotes with text and author, and the export panel with format, fields, run details and pretty options" width="640">

A CSV has one column per field and one line per row or picked value. A value that a spreadsheet would run as a formula (one starting with `=`, `+`, `-` or `@` that is not a plain number) gets a leading `'` so it opens as text. JSON and JSONL keep every value exactly as scraped.

### Pulling the Latest Data from Other Tools

`GET /api/sessions/<id>/data/latest` returns a session's newest successful run, as JSON unless you ask for another format. A failed run never replaces it, so a scheduled scrape that hits a down site keeps serving the last good records.

```bash
curl -H "Authorization: Bearer your-token" \
  "http://localhost:5001/api/sessions/1/data/latest?fields=author,text&envelope=1"
```

It takes the same options as a download:

| Option | Formats | What it does |
|--------|---------|--------------|
| `format` | all | `json` (the default here), `csv` or `jsonl` |
| `fields` | all | Comma-separated keys to keep, in that order. A record without one reads `""` |
| `envelope` | JSON | `1` wraps the records as `{"session", "run_id", "extracted_at", "items_count", "records"}` |
| `pretty` | JSON | `0` writes one line with no spaces. Indented by default |

An unknown option, or `envelope` or `pretty` with CSV or JSONL, is refused with a `400` rather than ignored. `GET /api/data/<run id>/export` takes the same options and downloads one run as a file.

### Exporting and Importing Flows

1. Click **"Export flow"** on a session to download it as a `.flow.json` file
2. Edit it by hand if you want: fix a selector, change a typed value, remove a step
3. Click **"Import Flow"** in the **Sessions** view and pick the file to save it as a new session

A flow file holds the start URL, the recorded steps (`click`, `input`, `scroll`), the picked elements and, if set, the row `table` and the `browser` settings. Unknown keys and files from a newer format version are refused with an error instead of being half loaded.

### Stealth Browsers and Proxies

In the **Record** view, pick the browser a session records and runs on, and an optional proxy:

![The Record view with CloakBrowser picked, human-like input ticked and a proxy URL using environment variables](docs/images/browser-settings.png)

| Browser | What it is | Install |
|---------|------------|---------|
| Chromium | Stock Playwright Chromium, the default | `uv run playwright install chromium` |
| Patchright | Playwright fork that hides common automation leaks | `uv run patchright install chromium` |
| CloakBrowser | Patched Chromium binary with its own fingerprint patches and optional human-like input | `uv sync --extra cloakbrowser`, then `uv run python -m cloakbrowser install` (about 200MB) |

- **CloakBrowser records on Patchright.** It disables the page binding the recorder reports through, so a CloakBrowser session is recorded on Patchright with the same proxy, and every run uses CloakBrowser. Newer CloakBrowser builds read a license key from `CLOAKBROWSER_LICENSE_KEY`.
- **Human-like input** (mouse paths, typing cadence) is CloakBrowser's own and can only be ticked for it.
- **Proxy URL:** `http://host:8080`, `https://host:8443` or `socks5://host:1080`. Keep credentials out of the database by referencing environment variables, `http://${PROXY_USER}:${PROXY_PASS}@host:8080`; they are read each time a browser opens, so set them before starting the server.
- **SOCKS5 with credentials is refused.** Playwright cannot authenticate to a SOCKS5 proxy, and CloakBrowser falls back to a direct connection when that fails. Use an HTTP proxy for authenticated access.
- **The proxy URL is stored exactly as typed**, and exported that way in flow files. A password typed literally ends up in the database and in every exported flow; `${ENV}` references stay references. The dashboard only shows whether a session has a proxy, never the URL.

The browser settings belong to the session: recording, manual replays and scheduled runs all use them.

### Scheduling Periodic Scraping

1. Click **"Schedule"** on a session
2. Enter how often to run it, in minutes, and save
3. Each scheduled run is headless, uses the session's own limits, and shows up in the **Runs** view with the trigger `schedule`
4. Pause, resume or delete schedules in the **Schedules** view

## Project Structure

```
RecordScrape/
├── app.py                 # Flask application & API
├── recordscrape/          # Playwright engine
│   ├── worker/            # The one thread all browser work runs on
│   ├── browsers/          # Chromium, Patchright and CloakBrowser backends
│   ├── proxies/           # Proxy URL parsing and env expansion
│   ├── recorder/          # Session recording and element picking
│   ├── flows/             # The flow file format for export and import
│   ├── runner/            # Replays a session and extracts its data
│   ├── exporters/         # CSV, JSON and JSONL writers
│   └── server_settings/   # Host, port, data dir and token from env
├── vpr/                   # Storage and scheduling
│   ├── __init__.py
│   ├── storage.py         # Sessions, runs and schedules in SQLite
│   └── scheduler.py       # Background job scheduler
├── static/
│   ├── css/
│   │   └── style.css      # Dashboard styles
│   └── js/
│       └── app.js         # Dashboard JavaScript
├── templates/
│   └── index.html         # Dashboard HTML
├── tests/                 # pytest suite
├── docs/images/           # README screenshots, demo GIF and video
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock                # Pinned dependency versions
└── LICENSE
```

## Technologies

- **Backend**: Python, Flask
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Database**: SQLite
- **Scheduling**: APScheduler
- **Browser Automation**: Playwright, with Patchright as a stealth backend

## License

MIT, see [LICENSE](LICENSE).
