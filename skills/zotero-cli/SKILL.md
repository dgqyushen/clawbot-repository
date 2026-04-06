---
name: zotero-cli
description: Connect to Zotero library via zotero-cli tool for searching, managing, and annotating research papers. Use when the user wants to search their Zotero library, find research papers, add notes to citations, or export references.
---

# Zotero CLI Skill for OpenClaw

## 概述

通过 zotero-cli 工具连接 Zotero 文献库，实现文献搜索、管理和笔记功能。

## 配置要求

### 1. 获取 Zotero API 凭证

1. 登录 https://www.zotero.org/
2. 访问 https://www.zotero.org/settings/keys 获取 **User ID**
3. 访问 https://www.zotero.org/settings/keys/new 创建 **API Key**
   - 权限建议勾选：
     - [x] Allow library access
     - [x] Allow notes access
     - [x] Allow write access (如需添加笔记)

### 2. 配置凭证

```bash
"${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/workspace/scripts/zotero-cli.sh" configure
```

按提示输入：
- Library ID: 你的 User ID 或 Group ID
- Library Type: `user` (个人库) 或 `group` (群组库)
- API Key: 刚创建的密钥

## 使用方式

### 直接命令行

```bash
# 搜索文献
"${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/workspace/scripts/zotero-cli.sh" query "silicon anode"

# 搜索短语
"${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/workspace/scripts/zotero-cli.sh" query '"solid electrolyte interphase"'

# 布尔搜索
"${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/workspace/scripts/zotero-cli.sh" query "(Li OR Na) AND battery"

# 添加笔记
"${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/workspace/scripts/zotero-cli.sh" add-note "论文标题"

# 阅读 PDF
"${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/workspace/scripts/zotero-cli.sh" read "论文标题"
```

### 通过 OpenClaw 调用

你可以直接对我说：

> "帮我在 Zotero 里搜索硅负极相关的文献"

我会执行：
```json
{
  "command": "$OPENCLAW_STATE_DIR/workspace/scripts/zotero-cli.sh query 'silicon anode'",
  "pty": true,
  "timeout": 30
}
```

## 常用搜索语法

| 搜索 | 示例 |
|------|------|
| 简单关键词 | `zotcli query battery` |
| 精确短语 | `zotcli query "solid state"` |
| AND | `zotcli query "silicon AND anode"` |
| OR | `zotcli query "Li OR Na"` |
| 组合 | `zotcli query "(Li OR Na) AND battery"` |
| 排除 | `zotcli query "battery NOT lithium"` |
| 前缀 | `zotcli query "electro*"` |

## 工作流示例

### 文献综述工作流

1. **搜索相关文献**
   ```bash
   zotcli query "silicon anode SEI"
   ```

2. **导出引用**
   ```bash
   zotcli export --format bib > references.bib
   ```

3. **给重要论文添加笔记**
   ```bash
   zotcli add-note "论文标题"
   ```

### 每日文献追踪

可以创建 cron 任务每天早上自动搜索新文献：

```bash
openclaw cron add \
  --name "Daily Zotero Search" \
  --cron "0 9 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "搜索 Zotero 中最近添加的 battery 相关文献，并总结新入库的论文" \
  --announce
```

## 故障排除

### 命令未找到

```bash
# 检查虚拟环境
ls -la "${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/venvs/zotero/bin/zotcli"

# 手动激活环境
. "${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/venvs/zotero/bin/activate"
zotcli --help
```

### API 认证失败

```bash
# 重新配置
zotcli configure

# 检查配置
zotcli query "test" --verbose
```

### 搜索结果为空

- 确认 Zotero 库中有数据
- 检查搜索关键词拼写
- 尝试更宽泛的关键词

## 参考链接

- zotero-cli GitHub: https://github.com/jbaiter/zotero-cli
- Zotero API 文档: https://www.zotero.org/support/dev/web_api/v3/basics
- Pyzotero 文档: https://pyzotero.readthedocs.io/
