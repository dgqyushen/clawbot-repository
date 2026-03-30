# Security Best Practices

## API Key Management

This project handles sensitive API keys. Follow these guidelines to keep your credentials secure.

### ❌ Never Commit API Keys

API keys (Bark, Zotero, Semantic Scholar) should **never** be committed to version control.

### ✅ Recommended Approaches

#### Option 1: Environment Variables (Recommended for CI/CD)

Set environment variables before running the crawler:

```bash
export SEMANTIC_SCHOLAR_API_KEY="your_ss_key"
export ZOTERO_API_KEY="your_zotero_key"
export ZOTERO_LIBRARY_ID="14021209"
export BARK_KEY="your_bark_key"

python scripts/daily_crawl.py --topic battery-research
```

Or use a `.env` file (included in `.gitignore`):

```bash
cp .env.example .env
# Edit .env with your keys
```

#### Option 2: Local Config File (Recommended for Development)

Create `config/local.yaml` with your real keys:

```bash
cp config/local.yaml.example config/local.yaml
# Edit config/local.yaml with your keys
```

This file is in `.gitignore` and will not be committed.

#### Option 3: Shell Wrapper Script

Create a wrapper script that exports keys:

```bash
#!/bin/bash
# run-crawler.sh
export SEMANTIC_SCHOLAR_API_KEY="..."
export ZOTERO_API_KEY="..."
export BARK_KEY="..."

python scripts/daily_crawl.py --topic battery-research "$@"
```

### 🔒 Priority Order

Configuration is loaded in this priority (highest first):

1. **Environment variables** - `BARK_KEY`, `ZOTERO_API_KEY`, etc.
2. **Local config** - `config/local.yaml` (git-ignored)
3. **Topic config** - `config/topics/*.yaml` (placeholders expanded)
4. **Template defaults** - `config/template.yaml`

### ⚠️ If You Accidentally Committed Keys

1. **Immediately rotate (revoke) the exposed keys:**
   - Zotero: https://www.zotero.org/settings/keys
   - Bark: Regenerate device key in app settings
   - Semantic Scholar: Request new key from their API page

2. **Remove from Git history** (requires force push):
   ```bash
   # Install git-filter-repo
   pip install git-filter-repo
   
   # Remove sensitive file from history
   git filter-repo --path config/local.yaml --invert-paths
   
   # Force push (coordinate with team)
   git push origin main --force
   ```

3. **Update .gitignore** to prevent future commits:
   ```
   config/local.yaml
   .env
   secrets.yaml
   ```

### 📝 Template Config Files

Topic configs in `config/topics/*.yaml` use placeholder syntax:

```yaml
api_keys:
  semantic_scholar: "${SEMANTIC_SCHOLAR_API_KEY}"
  zotero:
    api_key: "${ZOTERO_API_KEY}"

notification:
  bark_key: "${BARK_KEY}"
```

These are safe to commit as they contain no real credentials.

### 🔍 Verification

Before committing, verify no secrets are present:

```bash
# Search for API key patterns
grep -r "[a-zA-Z0-9]\{20,\}" config/topics/

# Check for Bark keys (24 chars)
grep -rE "[A-Za-z0-9]{24}" config/

# Ensure local.yaml is not staged
git status | grep local.yaml
```

### 🚨 Pre-commit Hook (Optional)

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Prevent committing files with "local" in name
if git diff --cached --name-only | grep -E "local.*\.yaml|\.env$"; then
    echo "Error: Attempting to commit local config with potential secrets"
    exit 1
fi
```
