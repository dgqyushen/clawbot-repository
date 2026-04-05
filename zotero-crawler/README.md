# Zotero Auto Literature Tracker

自动追踪学术文献并导入 Zotero，支持按日期归档。

## 功能

- 🔍 多关键词搜索 Semantic Scholar
- 📅 按日期自动创建 Zotero 文件夹结构
- 🚫 自动去重（避免重复导入）
- 📝 完整元数据（作者、摘要、引用数、PDF 链接）
- 🔔 每日推送通知（Bark）

## Zotero 文件夹结构

```
OpenClaw-Battery-Research/
├── 2026-03-30/
├── 2026-03-31/
├── 2026-04-01/
└── ...
```

## 安装

```bash
cd /root/.openclaw/workspace/projects/zotero-crawler
poetry install
```

或使用已创建的 venv:
```bash
cd /root/.openclaw/workspace/projects/zotero-crawler
source .venv/bin/activate
```

## 配置

敏感环境变量放在当前机器的 OpenClaw home 下：`$OPENCLAW_HOME/.env`（通常是 `~/.openclaw/.env`），不要放在项目目录里。

```bash
mkdir -p ~/.openclaw
cp .env.example ~/.openclaw/.env
# 编辑 ~/.openclaw/.env
```

项目配置仍放在 `config/zotero-crawler.yaml` / `config/topics/*.yaml`，但 API key 会优先从 `~/.openclaw/.env` 读取。

## 使用

### 单次运行

```bash
# 使用 Poetry
cd /root/.openclaw/workspace/projects/zotero-crawler
poetry run python src/daily_run.py

# 或手动激活 venv
source .venv/bin/activate
cd src
python daily_run.py
```

### 定时运行（Cron）

添加到你的 OpenClaw cron jobs：

```json
{
  "schedule": "0 9 * * *",
  "command": "cd /root/.openclaw/workspace/projects/zotero-crawler && poetry run python src/daily_run.py",
  "description": "Daily Zotero literature crawl"
}
```

## 文件结构

```
zotero-crawler/
├── config/
│   └── zotero-crawler.yaml     # 配置文件
├── src/
│   ├── semantic_scholar.py     # S2 API 封装
│   ├── zotero_pusher.py        # Zotero 导入
│   ├── literature_pipeline.py  # 主流程
│   └── daily_run.py            # CLI 入口
├── data/
│   └── literature-pushed.json  # 去重缓存
├── pyproject.toml              # Poetry 配置
└── .venv/                      # Poetry 虚拟环境
```

## API 限制

- **Semantic Scholar**: 1 req/sec (免费版)
- **Zotero**: 合理频率即可，_burst 时请注意
