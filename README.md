# RecordScrape

A powerful visual browser automation platform for recording interactions and automating data extraction through intelligent session replay.

## Features

- 🎥 **Visual Recording**: Record your browser interactions in real-time
- 🎯 **Element Selection**: Visually select DOM elements for data extraction
- 🔄 **Automated Replay**: Repeat the recorded clicks, typing and scrolling, visible or headless, then re-extract the selected elements
- 📄 **Flow Files**: Export a session as a JSON file, edit or share it, and import it back
- ⏰ **Scheduling**: Run a session every N minutes
- 📊 **Dashboard**: Web interface for managing sessions, schedules and extracted data

> JSON/CSV export of extracted data is not implemented yet. It is on the roadmap. Sessions recorded before the Playwright recorder only reopen their URL.

## 🎥 Demo

▶ Full video:  
https://twitter.com/Shubh3m/status/2027349108256887131

Record once → Automate forever.


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

4. Open your browser to `http://localhost:5001`. The server only listens on localhost.

## Running tests

The tests also run on the Patchright backend, which needs its own browser:

```bash
uv run patchright install chromium
uv run pytest
```

## Usage

### Recording a Session

1. In **"Record New Session"**, enter the URL you want to scrape and click **"Start Recording"**
2. A Chromium window opens on that URL
3. Click **"Select Elements"** and click the elements you want to extract, then **"Done"** in the overlay
4. For a list of items, click **"Select Rows"** instead (see below)
5. Click **"Stop & Save"** to save the session

### Extracting a List as Rows

1. While recording, click **"Select Rows"**
2. Click the same field in two different items, for example the name of the first and the second product. Every item that repeats like them is highlighted as a row
3. Click other fields inside any highlighted row to add them as columns, then **"Done"**

Each run then saves one record per row, such as `{"name": "Shoe", "price": "$40"}`. A column is named after the clicked element's first CSS class; rename it in an exported flow file. Elements picked with **"Select Elements"** in the same session are added to every row, keyed by their selector.

### Replaying & Extracting Data

1. Find your session in the **"Saved Sessions"** section
2. Click **"Replay"** to run it once manually
3. Extracted data appears in **"Recent Data Extractions"**

### Exporting and Importing Flows

1. Click **"Export"** on a saved session to download it as a `.flow.json` file
2. Edit it by hand if you want: fix a selector, change a typed value, remove a step
3. Click **"Import Flow"** above the saved sessions and pick the file to save it as a new session

A flow file holds the start URL, the recorded steps (`click`, `input`, `scroll`), the picked elements and, if one was picked, the row `table`. Unknown keys and files from a newer format version are refused with an error instead of being half loaded.

### Scheduling Periodic Scraping

1. Click **"Schedule"** on any saved session
2. Enter the frequency in minutes
3. The scheduler automatically runs the session and saves data
4. View scheduled jobs in the **"Schedules"** section

## Project Structure

```
RecordScrape/
├── app.py                 # Flask application & API
├── recordscrape/          # Playwright engine
│   ├── worker/            # The one thread all browser work runs on
│   ├── browsers/          # Chromium and Patchright backends
│   ├── recorder/          # Session recording and element picking
│   ├── flows/             # The flow file format for export and import
│   └── runner/            # Re-extracts picked elements
├── vpr/                   # Storage and scheduling
│   ├── __init__.py
│   ├── storage.py         # Database management
│   └── scheduler.py       # Background job scheduler
├── static/
│   ├── css/
│   │   └── style.css      # Dashboard styles
│   └── js/
│       └── app.js         # Dashboard JavaScript
├── templates/
│   └── index.html         # Dashboard HTML
├── tests/                 # pytest suite
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
