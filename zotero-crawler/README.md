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
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 配置

编辑 `config/zotero-crawler.yaml`：

```yaml
keywords:
  - "sodium iron sulfate"
  - "Na-ion battery"

api_keys:
  semantic_scholar: "your-s2-api-key"

zotero:
  library_id: "12345678"
  api_key: "your-zotero-api-key"
  main_collection: "OpenClaw-Battery-Research"
```

## 使用

### 单次运行

```bash
source venv/bin/activate
cd src
python -c "from literature_pipeline import run_pipeline_from_config; run_pipeline_from_config('../config/zotero-crawler.yaml')"
```

### 定时运行（Cron）

添加到你的 OpenClaw cron jobs：

```json
{
  "schedule": "0 9 * * *",
  "command": "cd /root/.openclaw/workspace/projects/zotero-crawler && venv/bin/python src/daily_run.py",
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
└── requirements.txt
```

## API 限制

- **Semantic Scholar**: 1 req/sec (免费版)
- **Zotero**: 合理频率即可，_burst 时请注意
