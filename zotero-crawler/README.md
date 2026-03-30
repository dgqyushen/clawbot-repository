# Zotero Literature Crawler

**A reusable, topic-agnostic literature crawler** that fetches papers from Semantic Scholar, checks for duplicates, and imports metadata into Zotero.

## Features

- **Semantic Scholar API**: Fast, comprehensive academic search
- **SQLite Storage**: Track seen papers, avoid duplicates
- **Zotero Integration**: Auto-import metadata (no PDF required)
- **Daily Reports**: Bark notifications with summary and paper highlights
- **Topic-Specific Configs**: Create separate keyword sets for different research areas
- **Generic Core**: The program is reusable, only the keywords are topic-specific

## Project Structure

```
zotero-crawler/
├── config/
│   ├── template.yaml          # Generic template (no keywords)
│   └── topics/               # Topic-specific configurations
│       ├── battery-research.yaml   # Your battery research keywords
│       ├── ai-ml.yaml              # AI/ML research keywords
│       └── your-topic.yaml         # Create your own!
├── src/                      # Core crawler (reusable, no hardcoded keywords)
│   ├── __init__.py
│   ├── semantic_scholar.py
│   ├── database.py
│   ├── zotero_export.py
│   └── notifier.py
├── scripts/
│   └── daily_crawl.py       # Main entry point
├── data/                    # SQLite database (auto-created)
├── logs/                    # Log files
├── tests/
│   └── test_*.py
├── requirements.txt
└── README.md
```

## Setup

### 1. Create Virtual Environment

```bash
python3 -m venv /root/.openclaw/venvs/zotero-crawler
source /root/.openclaw/venvs/zotero-crawler/bin/activate
pip install -r requirements.txt
```

### 2. Get API Keys

- **Semantic Scholar API**: Get free key from https://www.semanticscholar.org/product/api
- **Zotero API**: Get from https://www.zotero.org/settings/keys

### 3. Create Your Topic Configuration

The crawler is **generic** - you create topic-specific configs with your keywords:

```bash
# Option A: Copy the template and customize
cp config/template.yaml config/topics/my-research.yaml
# Edit config/topics/my-research.yaml with your keywords and API keys

# Option B: Use existing topic configs
# - config/topics/battery-research.yaml (Si-C anode, Na-ion battery)
# - config/topics/ai-ml.yaml (LLMs, transformers)
```

Example topic config structure:
```yaml
keywords:
  primary:
    - "your main topic"
    - "another key topic"
  secondary:
    - "related topic"
    - "peripheral interest"

api_keys:
  semantic_scholar: "your-ss-api-key"
  zotero:
    library_id: "your-zotero-id"
    api_key: "your-zotero-key"
    library_type: "user"

# ... other settings (zotero collection, notifications, etc.)
```

### 4. Run First Test

```bash
cd /root/.openclaw/workspace/projects/zotero-crawler

# Test with a specific topic
python scripts/daily_crawl.py --topic battery-research --dry-run

# Or use your custom config
python scripts/daily_crawl.py --config config/topics/my-research.yaml --dry-run
```

## Usage

### Manual Run

```bash
# Use a topic config (shortcut)
python scripts/daily_crawl.py --topic battery-research --dry-run
python scripts/daily_crawl.py --topic ai-ml

# Use a custom config file
python scripts/daily_crawl.py --config config/topics/my-research.yaml --dry-run

# Full run with Zotero import
python scripts/daily_crawl.py --topic battery-research

# Custom date range
python scripts/daily_crawl.py --topic battery-research --since 2024-01-01
```

### Cron Integration (Multiple Topics)

Run different topics on different schedules:

```bash
# Battery research - daily at 10 AM
openclaw cron add \
  --name "Battery Literature Daily" \
  --cron "0 10 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "cd /root/.openclaw/workspace/projects/zotero-crawler && /root/.openclaw/venvs/zotero-crawler/bin/python scripts/daily_crawl.py --topic battery-research" \
  --announce

# AI/ML research - weekly on Mondays at 9 AM
openclaw cron add \
  --name "AI/ML Literature Weekly" \
  --cron "0 9 * * 1" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "cd /root/.openclaw/workspace/projects/zotero-crawler && /root/.openclaw/venvs/zotero-crawler/bin/python scripts/daily_crawl.py --topic ai-ml" \
  --announce
```

Or execute directly:
```bash
cd /root/.openclaw/workspace/projects/zotero-crawler && \
/root/.openclaw/venvs/zotero-crawler/bin/python scripts/daily_crawl.py --topic battery-research
```

## Creating New Topic Configs

The crawler core is generic - create a new YAML file for each research topic:

```bash
# 1. Copy template
cp config/template.yaml config/topics/cancer-biology.yaml

# 2. Edit the new file - add your keywords and API keys
# keywords:
#   primary:
#     - "immunotherapy"
#     - "CAR-T cell"
#   secondary:
#     - "tumor microenvironment"
# zotero:
#   target_collection: "Cancer Biology"
# api_keys:
#   semantic_scholar: "your-key"
#   ...

# 3. Test
python scripts/daily_crawl.py --topic cancer-biology --dry-run

# 4. Run for real
python scripts/daily_crawl.py --topic cancer-biology
```

Each topic gets its own:
- **Keywords**: Specific to that research area
- **Zotero collection**: Papers organized by topic
- **Database tracking**: Same SQLite DB, but papers tagged by topic
- **Notification settings**: Can use different Bark keys for different teams

## Data Flow

```
1. Load config (--topic or --config)
2. Query Semantic Scholar API for each keyword
3. Check SQLite for existing DOIs (deduplication)
4. Filter new papers not yet imported
5. Import metadata to Zotero collection
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

## Reusability Principles

1. **Generic Core**: The code in `src/` has no hardcoded keywords
2. **Externalized Configs**: All topic-specific settings in YAML files
3. **Multiple Topics**: Run different configs for different research areas
4. **Shared Infrastructure**: Same database, same code, different inputs
5. **Easy Extension**: Add new topics by creating new YAML files

## License

MIT
