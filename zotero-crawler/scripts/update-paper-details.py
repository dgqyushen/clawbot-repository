#!/usr/bin/env python3
"""
更新已导入论文的完整日期格式 (YYYY-MM-DD)
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/projects/zotero-crawler/src')

import requests
from pyzotero import zotero

# Zotero配置
library_id = "14021209"
api_key = "1lio7Ai65J0B1wsmBRAXL0ju"
semantic_api_key = "2OucdpP9Ry4rtlJfkhsjWa8mDqRpjSi88Lp2XPVj"

# 论文paper_id到Zotero item_key的映射
papers = {
    '74393c3f2bcebe18e2410564311dac70b45d3949': 'FPD6ERD7',
    '1751f8dacae46784c13059d1ed1f3c0d04694e95': '5MSGMXCK',
    '99d172cd483b224da4979097ea421aabdffb5489': 'MX2CX4X9',
}

zot = zotero.Zotero(library_id, 'user', api_key)

for paper_id, item_key in papers.items():
    try:
        # 从Semantic Scholar获取完整数据
        url = f'https://api.semanticscholar.org/graph/v1/paper/{paper_id}'
        params = {'fields': 'paperId,title,abstract,publicationDate,tldr'}
        headers = {'x-api-key': semantic_api_key}
        resp = requests.get(url, params=params, headers=headers)
        data = resp.json()
        
        pub_date = data.get('publicationDate')  # YYYY-MM-DD format
        tldr = data.get('tldr', {}).get('text') if data.get('tldr') else None
        abstract = data.get('abstract') or tldr
        
        # 获取当前Zotero条目
        item = zot.item(item_key)
        if not item:
            print(f"❌ Item {item_key} not found")
            continue
        
        updated = False
        
        # 更新日期为完整格式
        if pub_date:
            item['data']['date'] = pub_date
            print(f"📅 Updated date: {pub_date}")
            updated = True
        
        # 更新摘要 (如果之前为空，且有TLDR)
        current_abstract = item['data'].get('abstractNote', '')
        if not current_abstract and abstract:
            item['data']['abstractNote'] = abstract
            print(f"📝 Added abstract/TLDR")
            updated = True
        
        if updated:
            zot.update_item(item)
            title = item['data'].get('title', 'Unknown')[:50]
            print(f"✅ Updated {item_key}: {title}...")
        else:
            print(f"⏭️  No changes for {item_key}")
            
    except Exception as e:
        print(f"❌ Failed to update {item_key}: {e}")

print("\nDone!")
