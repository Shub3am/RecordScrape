# Visual Data Scraper

A powerful tool for recording browser interactions and automating data extraction through visual session replay.

## Features

- 🎥 **Visual Recording**: Record your browser interactions in real-time
- 🎯 **Element Selection**: Visually select DOM elements for data extraction
- 🔄 **Automated Replay**: Replay sessions in headless mode for data scraping
- ⏰ **Scheduling**: Set up periodic scraping with customizable intervals
- 📊 **Dashboard**: Modern web interface for managing sessions and schedules
- 💾 **Data Export**: Export scraped data in JSON/CSV formats

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Web Dashboard                         │
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

1. Clone the repository:
```bash
git clone <repository-url>
cd RecordBrowser
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Open your browser to `http://localhost:5000`

## Usage

### Recording a Session

1. Click **"Record New Session"** in the dashboard
2. Enter the URL you want to scrape
3. Browser opens - perform your actions (navigate, click, scroll)
4. Use the visual selector overlay to mark elements for extraction
5. Click **"Stop Recording"** to save the session

### Replaying & Extracting Data

1. Find your session in the **"Saved Sessions"** section
2. Click **"Replay"** to run it once manually
3. Extracted data appears in **"Data Exports"**
4. Download as JSON or CSV

### Scheduling Periodic Scraping

1. Click **"Schedule"** on any saved session
2. Set the frequency (minutes, hours, days)
3. The scheduler automatically runs the session and saves data
4. View scheduled jobs in the **"Schedules"** section

## Project Structure

```
RecordBrowser/
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
└── requirements.txt
```

## Technologies

- **Backend**: Python, Flask, Selenium WebDriver
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **Database**: SQLite
- **Scheduling**: APScheduler
- **Browser Automation**: Selenium + WebDriver Manager

## License

MIT
