# RecordScrape

A powerful visual browser automation platform for recording interactions and automating data extraction through intelligent session replay.

## Features

- 🎥 **Visual Recording**: Record your browser interactions in real-time
- 🎯 **Element Selection**: Visually select DOM elements for data extraction
- 🔄 **Automated Replay**: Reopen the recorded URL, visible or headless, and re-extract the selected elements
- ⏰ **Scheduling**: Run a session every N minutes
- 📊 **Dashboard**: Web interface for managing sessions, schedules and extracted data

> Replay does not yet repeat recorded clicks or typing, and JSON/CSV export is not implemented yet. Both are on the roadmap.

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
│   Recorder      │                    │    Replayer      │
│  (Selenium UI)  │                    │  (Headless)      │
└────┬────────────┘                    └────┬─────────────┘
     │                                      │
     ▼                                      ▼
┌─────────────────────────────────────────────────────────┐
│              Storage Layer (SQLite)                      │
│  Sessions, Schedules, Extracted Data                    │
└─────────────────────────────────────────────────────────┘
```

## Installation

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Google Chrome.

1. Clone the repository:
```bash
git clone https://github.com/Shub3am/RecordScrape.git
cd RecordScrape
```

2. Install dependencies:
```bash
uv sync
```

3. Run the application:
```bash
uv run python app.py
```

4. Open your browser to `http://localhost:5001`. The server only listens on localhost.

## Running tests

```bash
uv run pytest
```

## Usage

### Recording a Session

1. In **"Record New Session"**, enter the URL you want to scrape and click **"Start Recording"**
2. A Chrome window opens on that URL
3. Click **"Select Elements"** and click the elements you want to extract, then **"Done Selecting"** in the overlay
4. Click **"Stop & Save"** to save the session

### Replaying & Extracting Data

1. Find your session in the **"Saved Sessions"** section
2. Click **"Replay"** to run it once manually
3. Extracted data appears in **"Recent Data Extractions"**

### Scheduling Periodic Scraping

1. Click **"Schedule"** on any saved session
2. Enter the frequency in minutes
3. The scheduler automatically runs the session and saves data
4. View scheduled jobs in the **"Schedules"** section

## Project Structure

```
RecordScrape/
├── app.py                 # Flask application & API
├── vpr/                   # Visual Page Recorder package
│   ├── __init__.py
│   ├── recorder.py        # Session recording engine
│   ├── replayer.py        # Headless replay engine
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

- **Backend**: Python, Flask, Selenium WebDriver
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Database**: SQLite
- **Scheduling**: APScheduler
- **Browser Automation**: Selenium + WebDriver Manager

## License

MIT, see [LICENSE](LICENSE).
