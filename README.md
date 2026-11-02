# Daily News Briefing App (Powered by Sarvam AI)

An automated audio briefing application that curates news across multiple channels (RSS feeds, Bluesky journalist handles, public Telegram channels, and optional X/Twitter accounts), deduplicates and clusters top stories from the last 24 hours, generates grounded radio-style spoken summaries with **mandatory spoken source attribution** using **Sarvam AI LLM**, synthesizes a continuous master MP3 audio briefing using **Sarvam TTS (`bulbul:v3`)**, and serves it on a responsive web player.

---

## 🏛️ Architecture Overview

```
                                      ┌────────────────┐
                                      │  sources.yaml  │
                                      └───────┬────────┘
                                              │
    ┌──────────────┬──────────────────────────┼─────────────────────────┐
    │              │                          │                         │
┌───▼───┐     ┌────▼─────┐             ┌──────▼──────┐           ┌──────▼──────┐
│  RSS  │     │ Bluesky  │             │  Telegram   │           │  X/Twitter  │
│ Feeds │     │ Accounts │             │   Channels  │           │  (Optional) │
└───┬───┘     └────┬─────┘             └──────┬──────┘           └──────┬──────┘
    │              │                          │                         │
    └──────────────┴─────────────┬────────────┴─────────────────────────┘
                                 │
                     ┌───────────▼───────────┐
                     │ Deduplicator & Ranker │ (24h filter, story clustering)
                     └───────────┬───────────┘
                                 │ Top N Grouped Stories
                     ┌───────────▼───────────┐
                     │   Sarvam AI Chat LLM  │ (sarvam-105b-conversations)
                     │ (Spoken Attribution)  │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │  Sarvam TTS (Bulbul)  │ (bulbul:v3 with speaker 'shreya')
                     │  Audio Assembler MP3  │
                     └───────────┬───────────┘
                                 │
                     ┌───────────┴───────────┐
                     ▼                       ▼
            [ data/output/*.mp3 ]   [ data/output/*.json ]
                     │                       │
                     └───────────┬───────────┘
                                 ▼
                     ┌───────────────────────┐
                     │    Web Delivery App   │ (http://localhost:8080)
                     │ Audio Player + Cards  │
                     └───────────────────────┘
```

---

## 🚀 Key Features

1. **Multi-Source Ingestion**:
   - **RSS Feeds**: Supports major news outlets (e.g. *The Hindu*, *NDTV*, *Reuters*, *BBC*).
   - **Bluesky Handles**: Ingests public journalist feeds via AT Protocol XRPC API without needing authentication.
   - **Public Telegram Channels**: Ingests public channel messages without requiring bot tokens.
   - **X / Twitter**: Optional official API v2 ingestor behind a configuration flag.

2. **Deduplication & Ranking**:
   - Discards items older than 24 hours.
   - Clusters stories covering the same event using token-overlap similarity.
   - Ranks stories by cross-verification count (stories covered by multiple outlets rank higher).

3. **Spoken Source Attribution (Radio Style)**:
   - Every spoken story verbally names its source out loud (e.g., *"According to The Hindu..."* or *"Reported by NDTV..."*).
   - If multiple sources cover a story, up to 2-3 are credited.
   - Social media posts are explicitly flagged with warning phrasing (*"This is an unconfirmed post from..."*).

4. **Sarvam AI Sovereign Speech Synthesis**:
   - Powered by `bulbul:v3` text-to-speech with natural Indian-English voice cadence.
   - Modular caching: avoids re-synthesizing previously converted stories on rerun.
   - Joins intro, transition phrases, story clips, and outro into a single continuous MP3 stream.

5. **Web Player Delivery**:
   - Modern, mobile-ready web UI with custom audio controls.
   - Displays full transcripts with clickable direct links and platform badges for every source.

---

## 📁 Project Structure

```
sarvam/
├── .env                     # Private API keys (SARVAM_API_KEY)
├── .env.example             # Template for environment variables
├── .gitignore               # Excludes secrets, caches, and binaries
├── requirements.txt         # Python dependencies
├── sources.yaml             # Central configuration for all sources & parameters
├── sources/                 # Modular ingestors
│   ├── base.py              # Data structures (NewsItem, GroupedStory, SourceMetadata)
│   ├── rss.py               # RSS/Atom feed parser
│   ├── bluesky.py           # Bluesky public XRPC feed fetcher
│   ├── telegram.py          # Telegram public preview scraper
│   └── twitter.py           # X/Twitter API v2 client (optional)
├── core/
│   ├── cache.py             # File-based caching for summaries & audio clips
│   ├── deduplicator.py      # 24h filter, clustering & story ranking
│   ├── summarizer.py        # Sarvam LLM prompt engine & attribution enforcer
│   └── tts.py               # Sarvam TTS (Bulbul) synthesizer & MP3 stitcher
├── web/
│   ├── app.py               # Lightweight HTTP server for UI and audio streaming
│   └── static/
│       └── index.html       # Responsive audio player & transcript UI
├── data/
│   ├── cache/               # Intermediate hashes and audio clip fragments
│   └── output/              # Daily MP3 briefings and JSON transcripts
└── generate_briefing.py     # Main CLI orchestration pipeline
```

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.10+ (tested with Python 3.12)
- Sarvam AI API subscription key

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure `.env`
Create `.env` (or copy from `.env.example`):
```ini
SARVAM_API_KEY=your_sarvam_api_key_here
PORT=8080

# Optional: if twitter source is enabled
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
```

---

## ⚙️ Adding & Configuring Sources

Edit [`sources.yaml`](file:///c:/Users/harsh/OneDrive/Desktop/sarvam/sources.yaml) to customize your briefing:

```yaml
briefing:
  top_stories: 8                 # Number of top stories to keep
  hours_window: 24               # Recency window in hours
  language_code: "en-IN"         # Speech language code
  tts_speaker: "shreya"          # Speakers: shreya, aditya, ritu, priya, rohan, etc.
  tts_model: "bulbul:v3"         # Latest Sarvam TTS model
  llm_model: "sarvam-105b-conversations"

sources:
  rss:
    enabled: true
    feeds:
      - name: "The Hindu - National"
        url: "https://www.thehindu.com/news/national/feeder/default.rss"
      - name: "NDTV Top Stories"
        url: "https://feeds.feedburner.com/ndtvnews-top-stories"

  bluesky:
    enabled: true
    accounts:
      - name: "BBC News"
        handle: "bbcnews.bsky.social"

  telegram:
    enabled: true
    channels:
      - name: "Telegram News"
        channel: "telegram"

  twitter:
    enabled: false               # Set true and supply TWITTER_BEARER_TOKEN in .env
    accounts:
      - name: "Reuters Tech"
        handle: "ReutersTech"
```

---

## 🏃 Running the Application

### 1. Generate Today's Briefing
Run the pipeline:
```bash
python generate_briefing.py
```
This fetches news, summarizes with spoken attribution, generates `data/output/briefing_<date>.mp3` and `data/output/latest.mp3`.

### 2. Launch the Web Briefing Player
Start the web viewer:
```bash
python web/app.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser to listen to the briefing and browse the verified source links.

---

## ⏰ Automated Daily Morning Scheduling

### Linux / macOS (crontab)
To generate the briefing every morning at 7:00 AM:
```bash
0 7 * * * cd /path/to/sarvam && /usr/bin/python3 generate_briefing.py >> /path/to/sarvam/briefing.log 2>&1
```

### Windows (Task Scheduler via PowerShell)
To run every day at 7:00 AM:
```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "generate_briefing.py" -WorkingDirectory "C:\Users\harsh\OneDrive\Desktop\sarvam"
$trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM
Register-ScheduledTask -TaskName "DailySarvamNewsBriefing" -Action $action -Trigger $trigger -Description "Generates Daily Sarvam AI Audio News Briefing"
```
