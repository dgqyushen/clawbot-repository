# Zotero Crawler — Bug Fix SPEC

## 目标

修复 `projects/zotero-crawler/` 中的重复爬取、过滤失效、Zotero 去重缺失等问题。

---

## 现状

```
爬取流程：
1. search_multiple_keywords() — 8 keywords × 7天 × 20篇
2. LiteraturePipeline.run() — 搜索→过滤→去重→写DB→生成review文件
3. execute_review.py — 手动review后导入Zotero
```

**两条独立去重链未对齐：**
- DedupStore (literature-pushed.json) — 只在 execute_review import 成功时更新
- PaperDatabase (papers.db) — 记录所有进过 pipeline 的论文
- Zotero — 无去重检查

---

## Bug 列表与修复方案

### BUG-1：Pipeline 重跑导致重复进 review（严重）

**问题：** `run()` Step 5 把论文写进 DB，但 dedup cache 没更新。如果 review 完成前再次运行爬虫，同一批论文会被当作 new，重新生成 review 文件，导致重复 approve。

**修复：** 在 dedup cache JSON 结构中增加 `pending` 状态层：

```python
# JSON 结构改为：
{
  "pushed": ["paper_id_1", "paper_id_2"],      # 已import
  "pending": ["paper_id_3", "paper_id_4"],     # review中
  "last_updated": "..."
}
```

- `DedupStore.is_new()` 只查 `pushed`
- `run()` 写 DB 后自动把 paper_id 写入 `pending`
- `execute_review.py` import 成功后：pending→pushed；skipped 时：pending→pushed（标记为 skipped）

**文件：** `src/literature_pipeline.py`，`src/execute_review.py`，`src/database.py`

---

### BUG-2：Zotero 无去重检查（严重）

**问题：** `ZoteroPusher.add_paper_to_collection()` 直接 `create_items()`，不检查目标 collection 是否已有该 paper。

**修复：** 在 `add_paper_to_collection()` 开头，调用 `zot.collection_items(collection_key)` 遍历已有条目，查 paper_id / DOI 是否存在。若存在则跳过并记录 warning。

**备选（更快）：** 在 `ensure_collection_path()` 返回后，维护一个本地 `collection_paper_ids` 缓存（dict: collection_key → set），每次 create 后更新缓存，下次 create 前先查缓存。

**文件：** `src/zotero_pusher.py`

---

### BUG-3：`citation_filter_age_days` 配置不生效（中等）

**问题：** `QualityFilter.__init__()` 签名有 `citation_filter_age_days`，但 `configure()` 调用时没传，用的是默认值 365，完全绕过了 YAML 配置。

**修复：** `configure()` 中从 `quality_config` 取出该值并传入。

**文件：** `src/literature_pipeline.py`

---

### BUG-4：`journal_whitelist` 顶层配置是死代码（中等）

**问题：** YAML 顶层有 `journal_whitelist`（74个期刊），但 `configure()` 只读 `quality_filters.journal_whitelist`（空列表），顶层配置永不生效。

**修复：** `configure()` 中，把 YAML top-level 的 `journal_whitelist` 合并到 `quality_filters.journal_whitelist`：

```python
top_level_whitelist = config.get('journal_whitelist', [])
qf_whitelist = quality_config.get('journal_whitelist', [])
quality_config['journal_whitelist'] = list(set(top_level_whitelist + qf_whitelist))
```

同时删除 YAML 顶层的 `journal_whitelist`（保持单一数据源）。

**文件：** `config/zotero-crawler.yaml`，`src/literature_pipeline.py`

---

### BUG-5：`journal_blacklist` 子串匹配误伤（中等）

**问题：** `"Science"` 在 blacklist，会匹配掉 `"Science Advances"`；`"Cell"` 会匹配 `"Cell Reports Physical Science"`。

**修复：** 改为**空格分词后的完整词匹配**：

```python
venue_words = set(venue_lower.split())
# 匹配条件：blacklisted 必须是 venue_words 的一个完整词
for blacklisted in self.journal_blacklist:
    black_words = set(blacklisted.split())
    if black_words.issubset(venue_words) or blacklisted in venue_words:
        return False
```

**文件：** `src/literature_pipeline.py`

---

### BUG-6：`excluded_keywords` 子串匹配过于激进（轻微）

**问题：** `"silicon"` 会匹配 `"siliconized"`，`"titanium"` 会匹配 `"titanium dioxide"`。

**修复：** 改用词边界 `\b` 正则匹配：

```python
import re
self.excluded_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b') for kw in excluded_keywords]

def matches(self, paper):
    text = (paper.title + ' ' + (paper.abstract or '')).lower()
    for pattern in self.excluded_patterns:
        if pattern.search(text):
            return False
```

**文件：** `src/literature_pipeline.py`

---

### BUG-7：`venue` 为空时直接放行（轻微）

**问题：** `is_quality_venue()` 中 `if not venue: return True`，任何 preprint 都绕过白名单。

**修复：** 无 venue 时走白名单逻辑（return False 如果有白名单），或要求 `require_venue: true` 才放行。配置加一个旗标控制。

**文件：** `src/literature_pipeline.py`

---

### BUG-8：`search_history` 表死代码（清理）

**问题：** DB 有 `search_history` 表但从未写入。

**修复：** 删除 `database.py` 中 `record_search()` 方法和 `search_history` 表相关代码；删除 `execute_review.py` 中多余的 `run_pipeline_from_config` import。

**文件：** `src/database.py`，`src/execute_review.py`

---

### BUG-9：review 文件无限积累（清理）

**问题：** `data/reviews/` 从不清理。

**修复：** 在 `execute_review.py` 末尾，清理 30 天前的 review JSON+MD 文件：

```python
import time
review_dir = Path(config_path).parent / 'data' / 'reviews'
cutoff = time.time() - 30 * 86400
for f in review_dir.glob('review_*.json'):
    if f.stat().st_mtime < cutoff:
        f.unlink()
        f.with_suffix('.md').unlink(missing_ok=True)
```

**文件：** `src/execute_review.py`

---

## 不修改的项（留待后续）

以下配置项存在但本次不实现，留空或忽略：
- `quality_filters.min_author_hindex` — 需要作者级别 h-index 查询，API 不直接支持
- `quality_filters.required_venues` — 需要 venue 级别过滤，API 返回 venue 字段但不支持多 venue 查询

---

## 验收标准

1. 连续两次运行 `run_pipeline_from_config`，第二次不会产生重复的 review 文件条目
2. `execute_review.py` 执行后，Zotero 中不出现重复论文
3. YAML 顶层的 `journal_whitelist` 生效（用空列表测试：配置无 whitelist 时，有 venue 论文应被过滤）
4. `journal_blacklist` 中的 `"Science"` 不再误杀 `"Science Advances"`
5. review 文件超过 30 天后自动删除
6. `search_history` 表相关代码已删除

---

## 文件清单

```
projects/zotero-crawler/
├── config/zotero-crawler.yaml       # 删除顶层 journal_whitelist
├── src/
│   ├── literature_pipeline.py         # BUG-1,3,4,5,6,7
│   ├── database.py                   # BUG-8
│   ├── execute_review.py              # BUG-1,8,9
│   └── zotero_pusher.py              # BUG-2
```

---

## 测试方法

修改后执行一次完整 pipeline（不带 import），检查：
1. `data/literature-pushed.json` 中 `pending` 列表非空
2. 再次执行同一 pipeline，确认 review 文件中无重复论文
3. `journal_blacklist` 中的短词不再误伤完整期刊名
