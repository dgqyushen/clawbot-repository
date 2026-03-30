# Zotero Literature Crawler

Daily literature crawler that fetches papers from Semantic Scholar, checks for duplicates, and imports metadata into Zotero.

## Features

- **Semantic Scholar API**: Fast, comprehensive academic search
- **SQLite Storage**: Track seen papers, avoid duplicates
- **Zotero Integration**: Auto-import metadata (no PDF required)
- **Daily Reports**: Bark notifications with summary and paper highlights
- **Configurable Keywords**: YAML-based topic management

## Project Structure

```
zotero-crawler/
├── config/
│   └── keywords.yaml          # Search keywords configuration
├── src/
│   ├── __init__.py
│   ├── semantic_scholar.py   # SS API client
│   ├── database.py           # SQLite storage & deduplication
│   ├── zotero_export.py     # Zotero API/RDF export
│   └── notifier.py          # Bark notification helper
├── scripts/
│   └── daily_crawl.py       # Main entry point
├── tests/
│   └── test_*.py           # Unit tests
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Setup

### 1. Create Virtual Environment

```bash
python3 -m venv /root/.openclaw/venvs/zotero-crawler
source /root/.openclaw/venvs/zotero-crawler/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `config/keywords.yaml` and add your keys:
- **Semantic Scholar API**: Get free key from https://www.semanticscholar.org/product/api
- **Zotero API**: Get from https://www.zotero.org/settings/keys

### 3. Configure Keywords

Edit `config/keywords.yaml` to set your research topics.

### 4. Run First Test

```bash
cd /root/.openclaw/workspace/projects/zotero-crawler
python scripts/daily_crawl.py --dry-run
```

## Usage

### Manual Run

```bash
# Dry run (no import, just report)
python scripts/daily_crawl.py --dry-run

# Full run with Zotero import
python scripts/daily_crawl.py

# Custom date range
python scripts/daily_crawl.py --since 2024-01-01
```

### Cron Integration

The script is designed to run via OpenClaw cron:

```bash
openclaw cron add \
  --name "Daily Literature Crawl" \
  --cron "0 10 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "Run zotero literature crawler for today" \
  --announce
```

Or execute directly:
```bash
cd /root/.openclaw/workspace/projects/zotero-crawler && \
/root/.openclaw/venvs/zotero-crawler/bin/python scripts/daily_crawl.py
```

## Data Flow

```
1. Load keywords from config
2. Query Semantic Scholar API
3. Check SQLite for existing DOIs (deduplication)
4. Filter new papers
5. Import metadata to Zotero via API
6. Send Bark notification with summary
7. Update SQLite with newly imported papers
```

## Notification Format

```
📚 Daily Literature Update - 2026-03-30

Found 5 new papers for Si-C anode research:

1. "High-performance silicon-carbon composite..."
   Journal: Nature Energy | 2024
   Cited: 45 times
   💡 Highlight: Novel 3D structure improves cycling stability

2. "Solid electrolyte interphase engineering..."
   ...

All papers imported to Zotero folder: "Daily Auto-Import"
```

## License

MIT
